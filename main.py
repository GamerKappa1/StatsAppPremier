"""
Command-line interface for the Premier Tracker backend.

Usage examples:
    python main.py init
    python main.py add-player "PlayerName" "TAG" --region eu
    python main.py sync
    python main.py stats
    python main.py map-stats --season <season_id>
"""

import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def cmd_init(_args) -> None:
    from db import init_db
    init_db()
    print("✓ Database initialised.")


def cmd_add_player(args) -> None:
    from db import init_db, add_tracked_player
    from api import get_puuid

    init_db()
    name, tag = args.name, args.tag

    print(f"Looking up {name}#{tag} …")
    puuid = get_puuid(name, tag, region=args.region)
    if not puuid:
        print("✗ Could not resolve PUUID – check name/tag/region.", file=sys.stderr)
        sys.exit(1)

    add_tracked_player(puuid, name, tag)
    print(f"✓ Added {name}#{tag}  (puuid={puuid})")


def cmd_sync(args) -> None:
    from db import init_db, get_tracked_players
    from api import sync_all_tracked

    init_db()
    players = get_tracked_players()
    if not players:
        print("No tracked players yet. Use `add-player` first.")
        return

    print(f"Syncing {len(players)} player(s) …\n")
    summary = sync_all_tracked(players, region=args.region, size=args.size)

    total_saved = 0
    for player, counts in summary.items():
        print(f"  {player:30s}  fetched={counts['fetched']}  saved={counts['saved']}")
        total_saved += counts["saved"]
    print(f"\n✓ Done. {total_saved} new match(es) stored.")


def cmd_stats(args) -> None:
    from db import init_db, get_tracked_players, get_player_stats_aggregated

    init_db()
    players = get_tracked_players()
    if not players:
        print("No tracked players.")
        return

    season = _resolve_season(getattr(args, "season", None))
    print(f"\n{'Player':<25} {'GP':>4} {'W%':>6} {'KD':>6} {'HS%':>7} {'Avg K':>7} {'Avg D':>6} {'Avg A':>6}")
    print("─" * 74)

    for p in players:
        s = get_player_stats_aggregated(p["puuid"], season_id=season)
        if not s:
            print(f"  {p['name']}#{p['tag']:<20}  – no data")
            continue
        name = f"{p['name']}#{p['tag']}"
        print(
            f"  {name:<23} {s['matches_played']:>4}  "
            f"{s['win_rate']:>5.1f}%  {s['kd']:>5.2f}  "
            f"{s['hs_percent']:>5.1f}%  {s['avg_kills']:>5.1f}  "
            f"{s['avg_deaths']:>5.1f}  {s['avg_assists']:>5.1f}"
        )


def cmd_seasons(_args) -> None:
    from db import init_db, get_known_seasons
    init_db()
    seasons = get_known_seasons()
    if not seasons:
        print("No matches synced yet.")
        return
    print("\nKnown season IDs in DB:")
    for s in seasons:
        print(f"  {s}")


def _resolve_season(season_arg: str | None) -> str | None:
    """Resolve 'current' to the latest season_id in the DB, pass through everything else."""
    if season_arg and season_arg.lower() == "current":
        from db import get_known_seasons
        seasons = get_known_seasons()
        if not seasons:
            print("No matches synced yet – can't resolve 'current'.")
            return None
        resolved = seasons[0]   # already ordered DESC, so first = newest
        print(f"  (current season → {resolved})")
        return resolved
    return season_arg


def cmd_history(args) -> None:
    from db import init_db, get_match_history

    init_db()
    season = _resolve_season(getattr(args, "season", None))
    rows = get_match_history(season_id=season, limit=args.limit)
    if not rows:
        print("No match data yet.")
        return

    for m in rows:
        result_color = "✓" if m["result"] == "W" else "✗"
        print(f"\n  {result_color} {m['result']}  {m['map_name']:<12}  {m['score']}  ({m['rounds']} rounds)  –  {m['date']}")
        print(f"  {'Player':<22} {'Team':<5} {'Agent':<12} {'KDA':>10} {'KD':>6} {'HS%':>6} {'Score':>7}")
        print("  " + "─" * 74)
        for p in sorted(m["players"], key=lambda x: x["score"], reverse=True):
            print(
                f"  {p['name']:<22} {p['team']:<5} {p['agent']:<12} "
                f"{p['kda']:>10} {p['kd']:>6.2f} {p['hs_percent']:>5.1f}%  {p['score']:>6}"
            )


def cmd_agent_stats(args) -> None:
    from db import init_db, get_tracked_players, get_agent_stats

    init_db()
    players = get_tracked_players()
    if not players:
        print("No tracked players.")
        return

    season = _resolve_season(getattr(args, "season", None))

    for p in players:
        rows = get_agent_stats(p["puuid"], season_id=season)
        if not rows:
            continue
        name = f"{p['name']}#{p['tag']}"
        print(f"\n  {name}")
        print(f"  {'Agent':<15} {'Picks':>5} {'Pick%':>6} {'W%':>6} {'KD':>6} {'HS%':>6}")
        print("  " + "─" * 48)
        for r in rows:
            print(
                f"  {r['agent']:<15} {r['picks']:>5}  "
                f"{r['pick_rate']:>5.1f}%  {r['win_rate']:>5.1f}%  "
                f"{r['kd']:>5.2f}  {r['hs_percent']:>5.1f}%"
            )


def cmd_map_stats(args) -> None:
    from db import init_db, get_map_stats

    init_db()
    season = _resolve_season(getattr(args, "season", None))
    rows = get_map_stats(season_id=season)
    if not rows:
        print("No match data yet.")
        return

    print(f"\n{'Map':<20} {'GP':>4} {'W':>4} {'L':>4} {'W%':>6}")
    print("─" * 42)
    for r in rows:
        print(f"  {r['map_name']:<18} {r['total']:>4} {r['wins']:>4} {r['losses']:>4}  {r['win_rate']:>5.1f}%")


# ─── Parser ───────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Premier Tracker – backend CLI")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Initialise the database")

    ap = sub.add_parser("add-player", help="Add a player to track")
    ap.add_argument("name", help="Riot name (without #tag)")
    ap.add_argument("tag",  help="Riot tag (without #)")
    ap.add_argument("--region", default="eu")

    sp = sub.add_parser("sync", help="Fetch new matches for all tracked players")
    sp.add_argument("--region", default="eu")
    sp.add_argument("--size",   type=int, default=10, help="Matches per player to check")

    stp = sub.add_parser("stats", help="Print aggregated player stats")
    stp.add_argument("--season", default=None, help="Filter by season_id")

    sub.add_parser("seasons", help="List all season IDs found in the DB")

    hp = sub.add_parser("history", help="Show recent match history with per-player stats")
    hp.add_argument("--season", default=None)
    hp.add_argument("--limit", type=int, default=10, help="Number of matches to show")

    agp = sub.add_parser("agent-stats", help="Per-agent pickrate and stats per player")
    agp.add_argument("--season", default=None)

    mp = sub.add_parser("map-stats", help="Print win/loss per map")
    mp.add_argument("--season", default=None)

    return p


def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()

    dispatch = {
        "init":       cmd_init,
        "add-player": cmd_add_player,
        "sync":       cmd_sync,
        "stats":      cmd_stats,
        "seasons":    cmd_seasons,
        "history":     cmd_history,
        "agent-stats": cmd_agent_stats,
        "map-stats":  cmd_map_stats,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()