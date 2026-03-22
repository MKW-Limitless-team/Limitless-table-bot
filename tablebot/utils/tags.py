from __future__ import annotations

import itertools
import re
import unicodedata

import numpy as np


MII_NAME_SUBSTITUTIONS = {
    "¥": "Y",
    "€": "E",
    "£": "E",
    "$": "S",
    "§": "S",
    "@": "A",
    "©": "C",
    "®": "R",
    "ø": "O",
    "Ø": "O",
    "ß": "B",
    "á": "A",
    "à": "A",
    "ä": "A",
    "é": "E",
    "è": "E",
    "ë": "E",
    "í": "I",
    "ì": "I",
    "ï": "I",
    "ó": "O",
    "ò": "O",
    "ö": "O",
    "ú": "U",
    "ù": "U",
    "ü": "U",
    "α": "A",
}


def normalize_name(mii_name: str, num_players_per_team: int = 0) -> str:
    if not mii_name:
        return "BLANK NAME"

    name = "Player" if mii_name.lower() == "no name" else mii_name.strip()
    if num_players_per_team != 5:
        for special_char, replacement in MII_NAME_SUBSTITUTIONS.items():
            name = name.replace(special_char, replacement)
        name = unicodedata.normalize("NFKD", name).encode("ASCII", "ignore").decode()
        name = re.sub(r"[^\w]", "", name)

    if not name.strip():
        return "BLANK NAME"

    return name if num_players_per_team == 5 else name.upper()


def get_tag_candidates(mii_name: str, num_players_per_team: int = 0) -> set[str]:
    tags: set[str] = set()
    name = (mii_name or "").strip()

    match = re.match(r"\[([A-Za-z0-9]+)\]", name)
    if match:
        tags.add(match.group(1).upper())

    for size in (4, 3, 2, 1):
        if size == 1 and match:
            continue
        tags.add(normalize_name(name[:size], num_players_per_team))

    return tags


def calc_tag_similarity(name1: str, name2: str, num_players_per_team: int = 0) -> int:
    shared = get_tag_candidates(name1, num_players_per_team) & get_tag_candidates(name2, num_players_per_team)
    if not shared:
        return 0
    return max(len(tag) for tag in shared)


def get_tag_similarity_matrix(mii_names_list: list[str], num_players_per_team: int = 0) -> np.ndarray:
    matrix = np.zeros((len(mii_names_list), len(mii_names_list)))
    for i in range(len(mii_names_list)):
        for j in range(i + 1, len(mii_names_list)):
            score = calc_tag_similarity(mii_names_list[i], mii_names_list[j], num_players_per_team)
            matrix[i][j] = matrix[j][i] = score
    return matrix


def guess_tag(mii_names: list[str], group_indices: tuple[int, ...], num_players_per_team: int = 0) -> str:
    counter: dict[str, int] = {}
    for idx in group_indices:
        for tag in get_tag_candidates(mii_names[idx], num_players_per_team):
            counter[tag] = counter.get(tag, 0) + 1
    if not counter:
        return "Unknown Tag"
    return max(counter.items(), key=lambda item: (item[1], len(item[0])))[0]


def greedy_grouping(sim_matrix: np.ndarray, team_size: int, num_teams: int) -> list[tuple[int, ...]]:
    ungrouped = set(range(len(sim_matrix)))
    groups: list[tuple[int, ...]] = []

    while len(groups) < num_teams and ungrouped:
        best_start = max(ungrouped, key=lambda i: sum(sim_matrix[i][j] for j in ungrouped if i != j))
        group = [best_start]
        ungrouped.remove(best_start)

        while len(group) < team_size and ungrouped:
            best_candidate = max(ungrouped, key=lambda j: sum(sim_matrix[j][k] for k in group))
            group.append(best_candidate)
            ungrouped.remove(best_candidate)

        groups.append(tuple(group))

    return groups


def assign_tags_to_groups(mii_names: list[str], groups: list[tuple[int, ...]], num_players_per_team: int = 0) -> dict[int, str]:
    return {
        idx: guess_tag(mii_names, group, num_players_per_team)
        for group in groups
        for idx in group
    }
