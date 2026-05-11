from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PlayerStats:
    puuid: str
    name: str
    tag: str
    team_color: str          # "Red" or "Blue"
    agent: str
    score: int
    kills: int
    deaths: int
    assists: int
    headshots: int
    bodyshots: int
    legshots: int
    damage_made: int
    damage_received: int
    economy_spent_overall: int
    economy_spent_average: float
    loadout_value_overall: int
    loadout_value_average: float

    @property
    def kd(self) -> float:
        return round(self.kills / self.deaths, 2) if self.deaths > 0 else float(self.kills)

    @property
    def hs_percent(self) -> float:
        total = self.headshots + self.bodyshots + self.legshots
        return round((self.headshots / total) * 100, 1) if total > 0 else 0.0

    @property
    def kda(self) -> str:
        return f"{self.kills}/{self.deaths}/{self.assists}"


@dataclass
class TeamResult:
    color: str               # "Red" or "Blue"
    has_won: bool
    rounds_won: int
    rounds_lost: int


@dataclass
class Match:
    match_id: str
    map_name: str
    game_start: int          # unix timestamp
    game_start_readable: str
    game_length: int         # seconds
    season_id: str
    mode: str
    mode_id: str
    rounds_played: int
    region: str
    cluster: str
    red: TeamResult
    blue: TeamResult
    players: list[PlayerStats] = field(default_factory=list)

    def team_of(self, puuid: str) -> Optional[TeamResult]:
        """Return the TeamResult for the team a given player was on."""
        for p in self.players:
            if p.puuid == puuid:
                color = p.team_color.lower()
                return self.red if color == "red" else self.blue
        return None

    def won_by(self, puuid: str) -> Optional[bool]:
        team = self.team_of(puuid)
        return team.has_won if team else None