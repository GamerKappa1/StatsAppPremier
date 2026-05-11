"""
Henrik Dev API client  –  https://docs.henrikdev.xyz/valorant
Fetches recent matches for a player and persists new ones to the DB.
"""

import time
import logging
import requests
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).parent / ".env")

from models import Match, PlayerStats, TeamResult
from db import match_exists, upsert_match

log = logging.getLogger(__name__)

BASE_URL = "https://api.henrikdev.xyz"
API_KEY  = os.getenv("HENRIK_API_KEY", "")


# ─── HTTP helpers ─────────────────────────────────────────────────────────────

def _headers() -> dict:
    return {"Authorization": API_KEY} if API_KEY else {}


def _get(url: str, params: Optional[dict] = None, retries: int = 3) -> Optional[dict]:
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=_headers(), params=params, timeout=10)
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 5))
                log.warning("Rate limited – waiting %ds", wait)
                time.sleep(wait)
                continue
            if resp.status_code == 404:
                log.warning("404 for %s", url)
                return None
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            log.error("Request failed (attempt %d/%d): %s", attempt + 1, retries, exc)
            time.sleep(2 ** attempt)
    return None


# ─── Lookup helpers ───────────────────────────────────────────────────────────

def get_puuid(name: str, tag: str, region: str = "eu") -> Optional[str]:
    """Resolve a Riot ID to a PUUID."""
    url = f"{BASE_URL}/valorant/v1/account/{name}/{tag}"
    data = _get(url, params={"region": region})
    if data and data.get("status") == 200:
        return data["data"].get("puuid")
    return None


def get_account_by_puuid(puuid: str) -> Optional[dict]:
    url = f"{BASE_URL}/valorant/v1/by-puuid/account/{puuid}"
    data = _get(url)
    if data and data.get("status") == 200:
        return data["data"]
    return None


# ─── Parsing ──────────────────────────────────────────────────────────────────

def _parse_match(raw: dict) -> Optional[Match]:
    """Convert raw Henrik API response dict into a Match datamodel."""
    try:
        meta = raw["metadata"]
        teams_raw = raw["teams"]
        players_raw = raw["players"]["all_players"]

        red_raw  = teams_raw["red"]
        blue_raw = teams_raw["blue"]

        red  = TeamResult("Red",  bool(red_raw["has_won"]),  red_raw["rounds_won"],  red_raw["rounds_lost"])
        blue = TeamResult("Blue", bool(blue_raw["has_won"]), blue_raw["rounds_won"], blue_raw["rounds_lost"])

        players: list[PlayerStats] = []
        for p in players_raw:
            stats    = p.get("stats", {})
            economy  = p.get("economy", {})
            spent    = economy.get("spent", {})
            loadout  = economy.get("loadout_value", {})

            players.append(PlayerStats(
                puuid=p["puuid"],
                name=p["name"],
                tag=p["tag"],
                team_color=p["team"],          # "Red" / "Blue"
                agent=p["character"],
                score=stats.get("score", 0),
                kills=stats.get("kills", 0),
                deaths=stats.get("deaths", 0),
                assists=stats.get("assists", 0),
                headshots=stats.get("headshots", 0),
                bodyshots=stats.get("bodyshots", 0),
                legshots=stats.get("legshots", 0),
                damage_made=p.get("damage_made", 0),
                damage_received=p.get("damage_recieved", 0),  # note typo in API
                economy_spent_overall=spent.get("overall", 0),
                economy_spent_average=float(spent.get("average", 0)),
                loadout_value_overall=loadout.get("overall", 0),
                loadout_value_average=float(loadout.get("average", 0)),
            ))

        return Match(
            match_id=meta["matchid"],
            map_name=meta["map"],
            game_start=meta["game_start"],
            game_start_readable=meta["game_start_patched"],
            game_length=meta["game_length"],
            season_id=meta["season_id"],
            mode=meta["mode"],
            mode_id=meta["mode_id"],
            rounds_played=meta["rounds_played"],
            region=meta["region"],
            cluster=meta["cluster"],
            red=red,
            blue=blue,
            players=players,
        )
    except (KeyError, TypeError) as exc:
        log.error("Failed to parse match: %s", exc)
        return None


# ─── Main fetch + sync logic ──────────────────────────────────────────────────

def sync_recent_matches(
    name: str,
    tag: str,
    region: str = "eu",
    mode: str = "premier",
    size: int = 10,
) -> tuple[int, int]:
    """
    Fetch the last `size` matches for `name#tag` via the v3 endpoint and
    persist any that are new. v3 returns full match data directly so no
    second per-match request is needed.

    Returns (fetched, saved) counts.
    """
    url = f"{BASE_URL}/valorant/v3/matches/{region}/{name}/{tag}"
    params = {"mode": mode, } # "size": size
    data = _get(url, params=params)

    if not data or data.get("status") != 200:
        log.error("Failed to fetch match history for %s#%s", name, tag)
        return 0, 0

    entries = data.get("data", [])
    fetched = len(entries)
    saved   = 0

    for raw_match in entries:
        mid = raw_match.get("metadata", {}).get("matchid")
        if not mid:
            continue
        if match_exists(mid):
            log.debug("Match %s already in DB – skipping", mid)
            continue

        match = _parse_match(raw_match)
        if match:
            upsert_match(match)
            saved += 1
            log.info("Saved match %s (%s – %s)", mid, match.map_name, match.game_start_readable)

    return fetched, saved


def sync_all_tracked(tracked_players: list[dict], region: str = "eu", size: int = 10) -> dict:
    """
    Sync recent matches for every tracked player.
    Deduplication happens at the DB level – each match is only stored once
    even if multiple tracked players appeared in it.

    `tracked_players` is a list of dicts with keys: puuid, name, tag
    Returns a summary dict.
    """
    summary = {}

    for player in tracked_players:
        name  = player["name"]
        tag   = player["tag"]
        label = f"{name}#{tag}"
        log.info("Syncing %s …", label)

        fetched, saved = sync_recent_matches(name, tag, region=region, size=size)
        summary[label] = {"fetched": fetched, "saved": saved}

    return summary