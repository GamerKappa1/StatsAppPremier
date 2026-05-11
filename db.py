import sqlite3
from pathlib import Path
from typing import Optional
from models import Match, PlayerStats, TeamResult

DB_PATH = Path(__file__).parent / "data" / "premier.db"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS matches (
                match_id            TEXT PRIMARY KEY,
                map_name            TEXT NOT NULL,
                game_start          INTEGER NOT NULL,
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
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
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
                added_at    INTEGER NOT NULL DEFAULT (strftime('%s','now'))
            );

            CREATE INDEX IF NOT EXISTS idx_mp_match  ON match_players(match_id);
            CREATE INDEX IF NOT EXISTS idx_mp_puuid  ON match_players(puuid);
            CREATE INDEX IF NOT EXISTS idx_m_season  ON matches(season_id);
            CREATE INDEX IF NOT EXISTS idx_m_map     ON matches(map_name);
        """)


# ─── Write ────────────────────────────────────────────────────────────────────

def upsert_match(match: Match) -> None:
    with get_connection() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO matches VALUES (
                :match_id, :map_name, :game_start, :game_start_readable,
                :game_length, :season_id, :mode, :mode_id, :rounds_played,
                :region, :cluster,
                :red_won, :red_rounds_won, :red_rounds_lost,
                :blue_won, :blue_rounds_won, :blue_rounds_lost
            )
        """, {
            "match_id":            match.match_id,
            "map_name":            match.map_name,
            "game_start":          match.game_start,
            "game_start_readable": match.game_start_readable,
            "game_length":         match.game_length,
            "season_id":           match.season_id,
            "mode":                match.mode,
            "mode_id":             match.mode_id,
            "rounds_played":       match.rounds_played,
            "region":              match.region,
            "cluster":             match.cluster,
            "red_won":             int(match.red.has_won),
            "red_rounds_won":      match.red.rounds_won,
            "red_rounds_lost":     match.red.rounds_lost,
            "blue_won":            int(match.blue.has_won),
            "blue_rounds_won":     match.blue.rounds_won,
            "blue_rounds_lost":    match.blue.rounds_lost,
        })

        for ps in match.players:
            conn.execute("""
                INSERT OR IGNORE INTO players(puuid, name, tag) VALUES (?, ?, ?)
            """, (ps.puuid, ps.name, ps.tag))

            conn.execute("""
                INSERT OR IGNORE INTO match_players (
                    match_id, puuid, team_color, agent, score,
                    kills, deaths, assists, headshots, bodyshots, legshots,
                    damage_made, damage_received,
                    economy_spent_overall, economy_spent_average,
                    loadout_value_overall, loadout_value_average
                ) VALUES (
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?,
                    ?, ?,
                    ?, ?
                )
            """, (
                match.match_id, ps.puuid, ps.team_color, ps.agent, ps.score,
                ps.kills, ps.deaths, ps.assists,
                ps.headshots, ps.bodyshots, ps.legshots,
                ps.damage_made, ps.damage_received,
                ps.economy_spent_overall, ps.economy_spent_average,
                ps.loadout_value_overall, ps.loadout_value_average,
            ))


def add_tracked_player(puuid: str, name: str, tag: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO players(puuid, name, tag) VALUES (?, ?, ?)",
            (puuid, name, tag),
        )
        conn.execute(
            "INSERT OR IGNORE INTO tracked_players(puuid) VALUES (?)",
            (puuid,),
        )


def remove_tracked_player(puuid: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM tracked_players WHERE puuid = ?", (puuid,))


# ─── Read ─────────────────────────────────────────────────────────────────────

def match_exists(match_id: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM matches WHERE match_id = ?", (match_id,)
        ).fetchone()
        return row is not None


def get_tracked_players() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT p.puuid, p.name, p.tag
            FROM tracked_players tp
            JOIN players p ON p.puuid = tp.puuid
            ORDER BY p.name
        """).fetchall()
        return [dict(r) for r in rows]


def get_matches(season_id: Optional[str] = None, map_name: Optional[str] = None) -> list[dict]:
    query = "SELECT * FROM matches WHERE 1=1"
    params: list = []
    if season_id:
        query += " AND season_id = ?"
        params.append(season_id)
    if map_name:
        query += " AND map_name = ?"
        params.append(map_name)
    query += " ORDER BY game_start DESC"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_player_stats_aggregated(
    puuid: str,
    season_id: Optional[str] = None,
    map_name: Optional[str] = None,
) -> Optional[dict]:
    """Aggregate stats for a single tracked player across matches."""
    query = """
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
            ROUND(AVG(mp.kills), 2)                             AS avg_kills,
            ROUND(AVG(mp.deaths), 2)                            AS avg_deaths,
            ROUND(AVG(mp.assists), 2)                           AS avg_assists
        FROM match_players mp
        JOIN players p ON p.puuid = mp.puuid
        JOIN matches  m ON m.match_id = mp.match_id
        WHERE mp.puuid = ?
    """
    params: list = [puuid]
    if season_id:
        query += " AND m.season_id = ?"
        params.append(season_id)
    if map_name:
        query += " AND m.map_name = ?"
        params.append(map_name)

    with get_connection() as conn:
        row = conn.execute(query, params).fetchone()
        if not row or row["matches_played"] == 0:
            return None
        d = dict(row)
        total_shots = (d["total_headshots"] + d["total_bodyshots"] + d["total_legshots"]) or 1
        d["hs_percent"] = round(d["total_headshots"] / total_shots * 100, 1)
        d["kd"] = round(d["total_kills"] / d["total_deaths"], 2) if d["total_deaths"] else float(d["total_kills"])
        d["win_rate"] = round(d["wins"] / d["matches_played"] * 100, 1) if d["matches_played"] else 0.0
        return d


def get_map_stats(season_id: Optional[str] = None) -> list[dict]:
    """Win/loss breakdown per map."""
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
        query += " AND m.season_id = ?"
        params.append(season_id)
    query += " GROUP BY map_name ORDER BY total DESC"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["losses"] = d["total"] - d["wins"]
            d["win_rate"] = round(d["wins"] / d["total"] * 100, 1) if d["total"] else 0.0
            result.append(d)
        return result


def get_agent_stats(
    puuid: str,
    season_id: Optional[str] = None,
    map_name: Optional[str] = None,
) -> list[dict]:
    """
    Per-agent breakdown for a single player.
    Returns one row per agent, ordered by picks descending.
    """
    query = """
        SELECT
            mp.agent,
            COUNT(*)                                AS picks,
            SUM(CASE
                WHEN mp.team_color = 'Red'  AND m.red_won  = 1 THEN 1
                WHEN mp.team_color = 'Blue' AND m.blue_won = 1 THEN 1
                ELSE 0
            END)                                    AS wins,
            ROUND(AVG(mp.kills),   2)               AS avg_kills,
            ROUND(AVG(mp.deaths),  2)               AS avg_deaths,
            ROUND(AVG(mp.assists), 2)               AS avg_assists,
            SUM(mp.headshots)                       AS total_headshots,
            SUM(mp.bodyshots)                       AS total_bodyshots,
            SUM(mp.legshots)                        AS total_legshots
        FROM match_players mp
        JOIN matches m ON m.match_id = mp.match_id
        WHERE mp.puuid = ?
    """
    params: list = [puuid]
    if season_id:
        query += " AND m.season_id = ?"
        params.append(season_id)
    if map_name:
        query += " AND m.map_name = ?"
        params.append(map_name)
    query += " GROUP BY mp.agent ORDER BY picks DESC"

    with get_connection() as conn:
        total_matches = (conn.execute(
            "SELECT COUNT(DISTINCT match_id) FROM match_players WHERE puuid = ?", (puuid,)
        ).fetchone()[0]) or 1

        rows = conn.execute(query, params).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            total_shots = (d["total_headshots"] + d["total_bodyshots"] + d["total_legshots"]) or 1
            d["hs_percent"] = round(d["total_headshots"] / total_shots * 100, 1)
            d["win_rate"]   = round(d["wins"] / d["picks"] * 100, 1) if d["picks"] else 0.0
            d["pick_rate"]  = round(d["picks"] / total_matches * 100, 1)
            d["kd"]         = round(d["avg_kills"] / d["avg_deaths"], 2) if d["avg_deaths"] else float(d["avg_kills"])
            result.append(d)
        return result


def get_match_history(
    season_id: Optional[str] = None,
    map_name: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """
    Recent matches with per-match stats for all tracked players.
    Returns matches ordered newest first, each with a 'players' list
    containing only tracked players who appeared in that match.
    """
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
        query += " AND m.season_id = ?"
        params.append(season_id)
    if map_name:
        query += " AND m.map_name = ?"
        params.append(map_name)
    query += f" ORDER BY m.game_start DESC LIMIT {limit * 10}"  # over-fetch for grouping

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    # Group rows by match, preserving newest-first order
    matches: dict[str, dict] = {}
    order:   list[str]       = []
    for r in rows:
        mid = r["match_id"]
        if mid not in matches:
            won = (r["red_won"] == 1 and r["team_color"] == "Red") or \
                  (r["red_won"] == 0 and r["team_color"] == "Blue")
            matches[mid] = {
                "match_id":    mid,
                "map_name":    r["map_name"],
                "date":        r["game_start_readable"],
                "score":       f"{r['red_rounds_won']}-{r['blue_rounds_won']}",
                "rounds":      r["rounds_played"],
                "result":      "W" if r["red_won"] == 1 and r["team_color"] == "Red"
                               else "W" if r["red_won"] == 0 and r["team_color"] == "Blue"
                               else "L",
                "players":     [],
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

    # Re-derive result per match correctly (use first tracked player's team)
    for mid, m in matches.items():
        pass  # result already set correctly above

    return [matches[mid] for mid in order[:limit]]


def get_known_seasons() -> list[str]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT season_id FROM matches ORDER BY season_id DESC"
        ).fetchall()
        return [r["season_id"] for r in rows]