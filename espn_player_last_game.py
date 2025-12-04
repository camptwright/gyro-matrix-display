from __future__ import annotations

import json
import requests
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple


LEAGUE_CONFIG = {
    "nfl": {"sport": "football", "league": "nfl"},
    "nba": {"sport": "basketball", "league": "nba"},
    "nhl": {"sport": "hockey", "league": "nhl"},
}


class ESPNError(Exception):
    """Custom exception for ESPN-related errors."""
    pass


def get_league_config(league: str) -> Dict[str, str]:
    league = league.lower()
    if league not in LEAGUE_CONFIG:
        raise ESPNError(f"Unsupported league '{league}'. Use nfl, nba, or nhl.")
    return LEAGUE_CONFIG[league]


def fetch_json(url: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Wrapper around requests.get with simple error handling."""
    resp = requests.get(url, params=params, timeout=10)
    if not resp.ok:
        raise ESPNError(f"Request failed ({resp.status_code}) for URL: {resp.url}")
    try:
        return resp.json()
    except ValueError as e:
        raise ESPNError(f"Failed to parse JSON from {resp.url}: {e}") from e


# ---------- Team matching helpers ----------

def _normalize_team_string(s: str) -> str:
    """Uppercase, letters+digits only, no spaces/punctuation."""
    return "".join(ch for ch in s.upper() if ch.isalnum())


def _team_matches(team_info: Dict[str, Any], user_team_input: str) -> bool:
    """
    Allow matching by:
      - abbreviation (e.g. LAR)
      - full team name (e.g. Los Angeles Rams)
      - nickname (e.g. Rams -> RAMS)
    """
    if not user_team_input:
        return False

    q_raw = user_team_input.strip().upper()
    q_norm = _normalize_team_string(user_team_input)

    candidates = []

    # Common ESPN fields
    candidates.append(team_info.get("abbreviation") or "")
    candidates.append(team_info.get("shortDisplayName") or "")
    candidates.append(team_info.get("displayName") or "")
    candidates.append(team_info.get("name") or "")
    candidates.append(team_info.get("nickname") or "")

    for cand in candidates:
        if not cand:
            continue
        c_raw = cand.upper()
        c_norm = _normalize_team_string(cand)

        # Exact abbreviation / exact name match
        if q_raw == c_raw or q_norm == c_norm:
            return True

        # Let "RAMS" match "Los Angeles Rams" etc.
        if q_norm and q_norm in c_norm:
            return True

    return False


# ---------- Find latest game for team ----------

def find_latest_team_game_event(
    league: str,
    team_query: str,
    max_days_back: int = 30,
) -> Tuple[str, Dict[str, Any], str]:
    """
    Use the ESPN scoreboard endpoint to find the most recent (or current) game
    for a given team (abbrev, full name, or nickname), and return:
        (event_id, event_json, canonical_team_abbrev)

    We SKIP games whose status.state is "pre" (future/pregame),
    so we only consider in-progress or completed games.
    """
    cfg = get_league_config(league)
    sport = cfg["sport"]
    league_code = cfg["league"]

    today = datetime.now(timezone.utc).date()

    for days_back in range(max_days_back + 1):
        target_date = today - timedelta(days=days_back)
        date_str = target_date.strftime("%Y%m%d")

        scoreboard_url = (
            f"https://site.api.espn.com/apis/site/v2/sports/"
            f"{sport}/{league_code}/scoreboard"
        )
        data = fetch_json(scoreboard_url, params={"dates": date_str})

        events = data.get("events", [])
        for event in events:
            # Skip future/pregame
            state = (
                event.get("status", {})
                .get("type", {})
                .get("state", "")
            )
            if state.lower() == "pre":
                continue

            competitions = event.get("competitions", [])
            if not competitions:
                continue

            comp = competitions[0]
            competitors = comp.get("competitors", [])

            for team in competitors:
                team_info = team.get("team", {}) or {}
                if _team_matches(team_info, team_query):
                    event_id = event.get("id")
                    if not event_id:
                        continue
                    canonical_abbrev = (team_info.get("abbreviation") or "").upper()
                    return event_id, event, canonical_abbrev

    raise ESPNError(
        f"No in-progress or completed game found for team '{team_query}' "
        f"in the last {max_days_back} days."
    )


# ---------- Fetch game summary ----------

def fetch_game_summary(league: str, event_id: str) -> Dict[str, Any]:
    """
    Fetch the game summary (includes boxscore) for the given event ID.
    """
    cfg = get_league_config(league)
    sport = cfg["sport"]
    league_code = cfg["league"]

    summary_url = (
        f"http://site.api.espn.com/apis/site/v2/sports/"
        f"{sport}/{league_code}/summary"
    )
    data = fetch_json(summary_url, params={"event": event_id})

    # Uncomment for debugging:
    # print(json.dumps(data, indent=2))

    return data


# ---------- Player + stats helpers ----------

def _match_player_name(athlete: Dict[str, Any], player_name: str) -> bool:
    """
    Check if the given ESPN 'athlete' object matches the desired player name.
    We compare to fullName, displayName, and shortName (case-insensitive).
    """
    name_lower = player_name.lower()
    candidates = [
        athlete.get("fullName"),
        athlete.get("displayName"),
        athlete.get("shortName"),
    ]
    for c in candidates:
        if c and c.lower() == name_lower:
            return True
    # Slightly fuzzy: allow player_name to be substring
    for c in candidates:
        if c and name_lower in c.lower():
            return True
    return False


def _match_team_abbrev_in_context(
    context: Dict[str, Any],
    team_abbrev: str
) -> bool:
    """
    Try to verify that the stat object belongs to the requested team by looking
    for a team abbreviation in the nearby JSON fields.
    """
    team_abbrev = team_abbrev.upper()

    # Direct 'team' field
    team = context.get("team")
    if isinstance(team, dict):
        abbrev = team.get("abbreviation") or team.get("shortDisplayName")
        if abbrev and abbrev.upper().startswith(team_abbrev):
            return True

    # Sometimes athlete has a team object
    athlete = context.get("athlete")
    if isinstance(athlete, dict):
        team = athlete.get("team")
        if isinstance(team, dict):
            abbrev = team.get("abbreviation") or team.get("shortDisplayName")
            if abbrev and abbrev.upper().startswith(team_abbrev):
                return True

    return False


def _extract_stats_from_node(node: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generic fallback: Convert an ESPN stats/summary node into a nicer dict: {stat_name: value}.
    Works for structures with 'statistics' or 'stats' keys where each entry is a dict.
    """
    stats: Dict[str, Any] = {}

    # 'statistics' is common in some ESPN boxscores
    if "statistics" in node and isinstance(node["statistics"], list):
        for stat in node["statistics"]:
            if not isinstance(stat, dict):
                continue
            key = stat.get("abbreviation") or stat.get("name") or stat.get("label")
            value = stat.get("displayValue") or stat.get("value")
            if key and value is not None:
                stats[str(key)] = value

    # Some endpoints use 'stats' as a list of dicts
    if "stats" in node and isinstance(node["stats"], list):
        for stat in node["stats"]:
            if not isinstance(stat, dict):
                continue
            key = stat.get("abbreviation") or stat.get("name") or stat.get("label")
            value = stat.get("displayValue") or stat.get("value")
            if key and value is not None:
                stats[str(key)] = value

    return stats


# ---------- Boxscore["players"] parser (NFL/NBA/NHL) ----------

def _find_player_stats_from_boxscore_players(
    boxscore: Dict[str, Any],
    player_name: str,
    team_abbrev: str
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Generic parser for ESPN sports that use:
      boxscore["players"] = [
        {
          "team": {...},
          "statistics": [
            {
              "name": "...",
              "labels": [...],
              "athletes": [
                {
                  "athlete": {...},
                  "stats": ["val1", "val2", ...]
                }, ...
              ]
            }, ...
          ]
        }, ...
      ]

    Used for NBA, NFL, NHL (and likely others).
    """
    players_groups = boxscore.get("players", [])
    team_abbrev = team_abbrev.upper()

    for group in players_groups:
        team_info = group.get("team") or {}
        abbrev = (team_info.get("abbreviation") or "").upper()
        if abbrev != team_abbrev:
            continue

        statistics = group.get("statistics", [])
        combined_stats: Dict[str, Any] = {}
        athlete_info: Dict[str, Any] | None = None

        for stat_group in statistics:
            labels = stat_group.get("labels") or stat_group.get("names") or []
            stat_group_name = (
                stat_group.get("name")
                or stat_group.get("type")
                or stat_group.get("displayName")
                or ""
            )
            athletes = stat_group.get("athletes", [])

            for entry in athletes:
                athlete = entry.get("athlete") or {}
                if not _match_player_name(athlete, player_name):
                    continue

                # First match: store athlete info
                if athlete_info is None:
                    athlete_info = athlete

                values = entry.get("stats") or []
                for label, value in zip(labels, values):
                    key = str(label)
                    if key in combined_stats and stat_group_name:
                        # Avoid clashes by prefixing with group name
                        key = f"{stat_group_name}_{key}"
                    combined_stats[key] = value

        if athlete_info is not None and combined_stats:
            return athlete_info, combined_stats

    raise ESPNError(
        f"Could not find boxscore['players'] stats for '{player_name}' on team '{team_abbrev}'."
    )


# ---------- Generic recursive fallback ----------

def _recursive_find_player_stats_generic(
    summary: Dict[str, Any],
    player_name: str,
    team_abbrev: str
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Old generic recursive search; used as a fallback for weird cases.
    """
    matches: List[Tuple[Dict[str, Any], Dict[str, Any]]] = []

    def traverse(obj: Any):
        if isinstance(obj, dict):
            if "athlete" in obj and isinstance(obj["athlete"], dict):
                athlete = obj["athlete"]
                if _match_player_name(athlete, player_name):
                    if _match_team_abbrev_in_context(obj, team_abbrev):
                        stats = _extract_stats_from_node(obj)
                        if stats:
                            matches.append((athlete, stats))

            for v in obj.values():
                traverse(v)

        elif isinstance(obj, list):
            for item in obj:
                traverse(item)

    root = summary.get("boxscore", summary)
    traverse(root)

    if not matches:
        raise ESPNError(
            f"Could not find stats for '{player_name}' on team '{team_abbrev}'. (generic search)"
        )

    best_athlete, best_stats = max(matches, key=lambda x: len(x[1]))
    return best_athlete, best_stats


# ---------- Main stat lookup ----------

def find_player_stats_in_summary(
    league: str,
    summary: Dict[str, Any],
    player_name: str,
    team_abbrev: str
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Main entry point to get player stats from a game summary.

    Strategy:
      * If boxscore['players'] is present (NBA/NFL/NHL), use that parser.
      * If that fails, fall back to the generic recursive search.
    """
    boxscore = summary.get("boxscore", {})

    if "players" in boxscore:
        try:
            return _find_player_stats_from_boxscore_players(
                boxscore,
                player_name,
                team_abbrev,
            )
        except ESPNError:
            # Fall through to generic search
            pass

    return _recursive_find_player_stats_generic(
        summary,
        player_name,
        team_abbrev,
    )


# ---------- Output formatting ----------

def pretty_print_player_stats(
    league: str,
    event: Dict[str, Any],
    athlete: Dict[str, Any],
    stats: Dict[str, Any]
) -> None:
    """
    Print a human-readable summary of the player’s latest/current game.
    """
    game_name = event.get("name") or event.get("shortName") or "Unknown matchup"
    event_date = event.get("date")
    try:
        if event_date:
            dt = datetime.fromisoformat(event_date.replace("Z", "+00:00"))
            event_date = dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        pass

    status = (
        event.get("status", {})
        .get("type", {})
        .get("name", "")
    )

    print("\n==============================")
    print(f"League  : {league.upper()}")
    print(f"Game    : {game_name}")
    print(f"Date    : {event_date}")
    print(f"Status  : {status}")
    print("------------------------------")
    print(f"Player  : {athlete.get('fullName') or athlete.get('displayName')}")
    team = athlete.get("team", {})
    if team:
        print(f"Team    : {team.get('displayName') or team.get('abbreviation')}")
    print("------------------------------")
    print("Stats for this game:")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print("==============================\n")


# ---------- CLI ----------

def main():
    print("=== ESPN Player Last Game Stats ===")
    league = input("Enter league (nfl/nba/nhl): ").strip().lower()
    team_input = input("Enter team (abbrev/name/nickname, e.g. DAL, LAL, RAMS): ").strip()
    player_name = input("Enter player name (e.g. Luka Doncic): ").strip()

    try:
        event_id, event, canonical_abbrev = find_latest_team_game_event(
            league,
            team_input
        )
        print(
            f"\nFound event {event_id} for team {canonical_abbrev} "
            f"(matched from '{team_input}'). Fetching summary..."
        )

        summary = fetch_game_summary(league, event_id)

        athlete, stats = find_player_stats_in_summary(
            league,
            summary,
            player_name,
            canonical_abbrev,
        )

        pretty_print_player_stats(league, event, athlete, stats)

    except ESPNError as e:
        print(f"\n[ERROR] {e}")
    except requests.RequestException as e:
        print(f"\n[NETWORK ERROR] {e}")
    except Exception as e:
        print(f"\n[UNEXPECTED ERROR] {e}")


if __name__ == "__main__":
    main()
