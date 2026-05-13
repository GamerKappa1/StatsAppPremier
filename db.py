import psycopg2
import psycopg2.extras
from psycopg2 import pool
import os
from typing import Optional
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")

from models import Match, PlayerStats, TeamResult

IGNORED_SEASONS: set[str] = set()  # legacy fallback, now DB-backed

_pool: pool.SimpleConnectionPool | None = None


def _get_pool() -> pool.SimpleConnectionPool:
    global _pool
    if _pool is None or _pool.closed:
        _pool = pool.SimpleConnectionPool(
            minconn=1,
            maxconn=5,
            dsn=os.getenv("DATABASE_URL"),
        )
    return _pool


class _PooledConnection:
    """Context manager that borrows a connection from the pool and returns it on exit."""
    def __init__(self):
        self._conn = None

    def __enter__(self):
        self._conn = _get_pool().getconn()
        return self._conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self._conn.rollback()
        _get_pool().putconn(self._conn)
        return False


def get_connection():
    return _PooledConnection()


def close_pool() -> None:
    global _pool
    if _pool and not _pool.closed:
        _pool.closeall()
        _pool = None


def _ignored_filter() -> tuple[str, list]:
    """Returns a SQL fragment and params to exclude ignored seasons."""
    ignored = get_ignored_seasons()
    if not ignored:
        return "", []
    placeholders = ",".join(["%s"] * len(ignored))
    return f" AND m.season_id NOT IN ({placeholders})", list(ignored)


def init_db() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS matches (
                    match_id            TEXT PRIMARY KEY,
                    map_name            TEXT NOT NULL,
                    game_start          BIGINT NOT NULL,
                    game_start_readable TEXT NOT NULL,
                    game_length         INTEGER NOT NULL,
                    season_id           TEXT NOT NULL,
                    mode                TEXT NOT NULL,
                    mode_id             TEXT NOT NULL,
                    rounds_played       INTEGER NOT NULL,
                    region              TEXT NOT NULL,
                    cluster             TEXT NOT NULL,
                    red_won             INTEGER NOT NULL,
                    red_rounds_won      INTEGER NOT NULL,
                    red_rounds_lost     INTEGER NOT NULL,
                    blue_won            INTEGER NOT NULL,
                    blue_rounds_won     INTEGER NOT NULL,
                    blue_rounds_lost    INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS players (
                    puuid   TEXT PRIMARY KEY,
                    name    TEXT NOT NULL,
                    tag     TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS match_players (
                    id                      SERIAL PRIMARY KEY,
                    match_id                TEXT NOT NULL REFERENCES matches(match_id),
                    puuid                   TEXT NOT NULL REFERENCES players(puuid),
                    team_color              TEXT NOT NULL,
                    agent                   TEXT NOT NULL,
                    score                   INTEGER NOT NULL,
                    kills                   INTEGER NOT NULL,
                    deaths                  INTEGER NOT NULL,
                    assists                 INTEGER NOT NULL,
                    headshots               INTEGER NOT NULL,
                    bodyshots               INTEGER NOT NULL,
                    legshots                INTEGER NOT NULL,
                    damage_made             INTEGER NOT NULL,
                    damage_received         INTEGER NOT NULL,
                    economy_spent_overall   INTEGER NOT NULL,
                    economy_spent_average   REAL NOT NULL,
                    loadout_value_overall   INTEGER NOT NULL,
                    loadout_value_average   REAL NOT NULL,
                    UNIQUE(match_id, puuid)
                );

                CREATE TABLE IF NOT EXISTS tracked_players (
                    puuid       TEXT PRIMARY KEY REFERENCES players(puuid),
                    added_at    BIGINT NOT NULL DEFAULT extract(epoch from now())::bigint
                );

                CREATE TABLE IF NOT EXISTS ignored_seasons (
                    season_id   TEXT PRIMARY KEY,
                    added_at    BIGINT NOT NULL DEFAULT extract(epoch from now())::bigint
                );

                CREATE INDEX IF NOT EXISTS idx_mp_match  ON match_players(match_id);
                CREATE INDEX IF NOT EXISTS idx_mp_puuid  ON match_players(puuid);
                CREATE INDEX IF NOT EXISTS idx_m_season  ON matches(season_id);
                CREATE INDEX IF NOT EXISTS idx_m_map     ON matches(map_name);
            """)
        conn.commit()


# ─── Write ────────────────────────────────────────────────────────────────────

def upsert_match(match: Match) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO matches VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s
                ) ON CONFLICT DO NOTHING
            """, (
                match.match_id, match.map_name, match.game_start,
                match.game_start_readable, match.game_length, match.season_id,
                match.mode, match.mode_id, match.rounds_played,
                match.region, match.cluster,
                int(match.red.has_won), match.red.rounds_won, match.red.rounds_lost,
                int(match.blue.has_won), match.blue.rounds_won, match.blue.rounds_lost,
            ))

            for ps in match.players:
                cur.execute("""
                    INSERT INTO players(puuid, name, tag) VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (ps.puuid, ps.name, ps.tag))

                cur.execute("""
                    INSERT INTO match_players (
                        match_id, puuid, team_color, agent, score,
                        kills, deaths, assists, headshots, bodyshots, legshots,
                        damage_made, damage_received,
                        economy_spent_overall, economy_spent_average,
                        loadout_value_overall, loadout_value_average
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT DO NOTHING
                """, (
                    match.match_id, ps.puuid, ps.team_color, ps.agent, ps.score,
                    ps.kills, ps.deaths, ps.assists,
                    ps.headshots, ps.bodyshots, ps.legshots,
                    ps.damage_made, ps.damage_received,
                    ps.economy_spent_overall, ps.economy_spent_average,
                    ps.loadout_value_overall, ps.loadout_value_average,
                ))
        conn.commit()


def add_tracked_player(puuid: str, name: str, tag: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO players(puuid, name, tag) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                (puuid, name, tag),
            )
            cur.execute(
                "INSERT INTO tracked_players(puuid) VALUES (%s) ON CONFLICT DO NOTHING",
                (puuid,),
            )
        conn.commit()


def remove_tracked_player(puuid: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tracked_players WHERE puuid = %s", (puuid,))
        conn.commit()


# ─── Ignored seasons ──────────────────────────────────────────────────────────

def get_ignored_seasons() -> set[str]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT season_id FROM ignored_seasons")
            return {row[0] for row in cur.fetchall()}


def ignore_season(season_id: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO ignored_seasons(season_id) VALUES (%s) ON CONFLICT DO NOTHING",
                (season_id,),
            )
        conn.commit()


def unignore_season(season_id: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ignored_seasons WHERE season_id = %s", (season_id,))
        conn.commit()


# ─── Read ─────────────────────────────────────────────────────────────────────

def _fetchall(cur) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _fetchone(cur) -> Optional[dict]:
    cols = [d[0] for d in cur.description]
    row  = cur.fetchone()
    return dict(zip(cols, row)) if row else None


def match_exists(match_id: str) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM matches WHERE match_id = %s", (match_id,))
            return cur.fetchone() is not None


def get_tracked_players() -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p.puuid, p.name, p.tag
                FROM tracked_players tp
                JOIN players p ON p.puuid = tp.puuid
                ORDER BY p.name
            """)
            return _fetchall(cur)


def get_matches(season_id: Optional[str] = None, map_name: Optional[str] = None) -> list[dict]:
    query  = "SELECT * FROM matches WHERE 1=1"
    params = []
    if season_id:
        query += " AND season_id = %s"
        params.append(season_id)
    if map_name:
        query += " AND map_name = %s"
        params.append(map_name)
    query += " ORDER BY game_start DESC"
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return _fetchall(cur)


def get_player_stats_aggregated(
    puuid: str,
    season_id: Optional[str] = None,
    map_name: Optional[str] = None,
) -> Optional[dict]:
    base_query = """
        SELECT
            p.name,
            p.tag,
            COUNT(DISTINCT mp.match_id)                         AS matches_played,
            SUM(CASE
                WHEN mp.team_color = 'Red'  AND m.red_won  = 1 THEN 1
                WHEN mp.team_color = 'Blue' AND m.blue_won = 1 THEN 1
                ELSE 0
            END)                                                AS wins,
            SUM(mp.kills)                                       AS total_kills,
            SUM(mp.deaths)                                      AS total_deaths,
            SUM(mp.assists)                                     AS total_assists,
            SUM(mp.headshots)                                   AS total_headshots,
            SUM(mp.bodyshots)                                   AS total_bodyshots,
            SUM(mp.legshots)                                    AS total_legshots,
            SUM(mp.score)                                       AS total_score,
            SUM(mp.damage_made)                                 AS total_damage_made,
            ROUND(AVG(mp.kills)::numeric,   2)                  AS avg_kills,
            ROUND(AVG(mp.deaths)::numeric,  2)                  AS avg_deaths,
            ROUND(AVG(mp.assists)::numeric, 2)                  AS avg_assists
        FROM match_players mp
        JOIN players p ON p.puuid = mp.puuid
        JOIN matches  m ON m.match_id = mp.match_id
        WHERE mp.puuid = %s
    """
    params: list = [puuid]
    filters = []
    if season_id:
        filters.append("m.season_id = %s")
        params.append(season_id)
    if map_name:
        filters.append("m.map_name = %s")
        params.append(map_name)
    ign_sql, ign_params = _ignored_filter()
    if ign_sql:
        filters.append(ign_sql.lstrip(" AND "))
        params.extend(ign_params)

    query = base_query
    if filters:
        query += " AND " + " AND ".join(filters)
    query += " GROUP BY p.name, p.tag"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            row = _fetchone(cur)
    if not row or not row["matches_played"]:
        return None
    total_shots    = (row["total_headshots"] + row["total_bodyshots"] + row["total_legshots"]) or 1
    row["hs_percent"] = round(row["total_headshots"] / total_shots * 100, 1)
    row["kd"]         = round(row["total_kills"] / row["total_deaths"], 2) if row["total_deaths"] else float(row["total_kills"])
    row["win_rate"]   = round(row["wins"] / row["matches_played"] * 100, 1) if row["matches_played"] else 0.0
    return row


def get_map_stats(season_id: Optional[str] = None) -> list[dict]:
    query = """
        SELECT
            map_name,
            COUNT(*)                            AS total,
            SUM(CASE
                WHEN EXISTS (
                    SELECT 1 FROM match_players mp2
                    JOIN tracked_players tp ON tp.puuid = mp2.puuid
                    WHERE mp2.match_id = m.match_id
                      AND ((mp2.team_color='Red' AND m.red_won=1)
                        OR (mp2.team_color='Blue' AND m.blue_won=1))
                ) THEN 1 ELSE 0
            END)                                AS wins
        FROM matches m
        WHERE 1=1
    """
    params: list = []
    if season_id:
        query += " AND m.season_id = %s"
        params.append(season_id)
    ign_sql, ign_params = _ignored_filter()
    query += ign_sql
    params.extend(ign_params)
    query += " GROUP BY map_name ORDER BY total DESC"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = _fetchall(cur)
    result = []
    for r in rows:
        r["losses"]   = r["total"] - r["wins"]
        r["win_rate"] = round(r["wins"] / r["total"] * 100, 1) if r["total"] else 0.0
        result.append(r)
    return result


def get_agent_stats(
    puuid: str,
    season_id: Optional[str] = None,
    map_name: Optional[str] = None,
) -> list[dict]:
    base_query = """
        SELECT
            mp.agent,
            COUNT(*)                                        AS picks,
            SUM(CASE
                WHEN mp.team_color = 'Red'  AND m.red_won  = 1 THEN 1
                WHEN mp.team_color = 'Blue' AND m.blue_won = 1 THEN 1
                ELSE 0
            END)                                            AS wins,
            ROUND(AVG(mp.kills)::numeric,   2)              AS avg_kills,
            ROUND(AVG(mp.deaths)::numeric,  2)              AS avg_deaths,
            ROUND(AVG(mp.assists)::numeric, 2)              AS avg_assists,
            SUM(mp.headshots)                               AS total_headshots,
            SUM(mp.bodyshots)                               AS total_bodyshots,
            SUM(mp.legshots)                                AS total_legshots
        FROM match_players mp
        JOIN matches m ON m.match_id = mp.match_id
        WHERE mp.puuid = %s
    """
    params: list = [puuid]
    filters = []
    if season_id:
        filters.append("m.season_id = %s")
        params.append(season_id)
    if map_name:
        filters.append("m.map_name = %s")
        params.append(map_name)
    ign_sql, ign_params = _ignored_filter()
    if ign_sql:
        filters.append(ign_sql.lstrip(" AND "))
        params.extend(ign_params)

    query = base_query
    if filters:
        query += " AND " + " AND ".join(filters)
    query += " GROUP BY mp.agent ORDER BY picks DESC"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(DISTINCT match_id) FROM match_players WHERE puuid = %s", (puuid,))
            total_matches = cur.fetchone()[0] or 1
            cur.execute(query, params)
            rows = _fetchall(cur)

    result = []
    for r in rows:
        total_shots    = (r["total_headshots"] + r["total_bodyshots"] + r["total_legshots"]) or 1
        r["hs_percent"] = round(r["total_headshots"] / total_shots * 100, 1)
        r["win_rate"]   = round(r["wins"] / r["picks"] * 100, 1) if r["picks"] else 0.0
        r["pick_rate"]  = round(r["picks"] / total_matches * 100, 1)
        r["kd"]         = round(r["avg_kills"] / r["avg_deaths"], 2) if r["avg_deaths"] else float(r["avg_kills"])
        result.append(r)
    return result


def get_match_history(
    season_id: Optional[str] = None,
    map_name: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    query = """
        SELECT
            m.match_id,
            m.map_name,
            m.game_start_readable,
            m.rounds_played,
            m.red_won,
            m.red_rounds_won,
            m.blue_rounds_won,
            mp.puuid,
            p.name,
            p.tag,
            mp.team_color,
            mp.agent,
            mp.kills,
            mp.deaths,
            mp.assists,
            mp.headshots,
            mp.bodyshots,
            mp.legshots,
            mp.score
        FROM matches m
        JOIN match_players mp ON mp.match_id = m.match_id
        JOIN tracked_players tp ON tp.puuid = mp.puuid
        JOIN players p ON p.puuid = mp.puuid
        WHERE 1=1
    """
    params: list = []
    if season_id:
        query += " AND m.season_id = %s"
        params.append(season_id)
    if map_name:
        query += " AND m.map_name = %s"
        params.append(map_name)
    ign_sql, ign_params = _ignored_filter()
    query += ign_sql
    params.extend(ign_params)
    query += f" ORDER BY m.game_start DESC LIMIT {limit * 10}"

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = _fetchall(cur)

    matches: dict[str, dict] = {}
    order:   list[str]       = []
    for r in rows:
        mid = r["match_id"]
        if mid not in matches:
            won = (r["red_won"] == 1 and r["team_color"] == "Red") or \
                  (r["red_won"] == 0 and r["team_color"] == "Blue")
            matches[mid] = {
                "match_id": mid,
                "map_name": r["map_name"],
                "date":     r["game_start_readable"],
                "score":    f"{r['red_rounds_won']}-{r['blue_rounds_won']}",
                "rounds":   r["rounds_played"],
                "result":   "W" if won else "L",
                "players":  [],
            }
            order.append(mid)

        total_shots = (r["headshots"] + r["bodyshots"] + r["legshots"]) or 1
        matches[mid]["players"].append({
            "name":       f"{r['name']}#{r['tag']}",
            "team":       r["team_color"],
            "agent":      r["agent"],
            "kda":        f"{r['kills']}/{r['deaths']}/{r['assists']}",
            "kd":         round(r["kills"] / r["deaths"], 2) if r["deaths"] else float(r["kills"]),
            "hs_percent": round(r["headshots"] / total_shots * 100, 1),
            "score":      r["score"],
        })

    return [matches[mid] for mid in order[:limit]]


def get_known_seasons() -> list[str]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT season_id FROM matches ORDER BY season_id DESC")
            return [row[0] for row in cur.fetchall()]