from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class TableState:
    metadata: pd.DataFrame
    all_players_raw: pd.DataFrame
    all_players: pd.DataFrame
    commands: pd.DataFrame
    raw_races_dfs: list[pd.DataFrame]
    processed_races_dfs: list[pd.DataFrame]
