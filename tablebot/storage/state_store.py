from __future__ import annotations

import pickle
from pathlib import Path

from tablebot.config import STATE_DIR
from tablebot.models import TableState


def _state_path(server_id: str, channel_id: str) -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return STATE_DIR / f"{server_id}_{channel_id}.pkl"


def load_state(server_id: str, channel_id: str) -> TableState:
    with _state_path(server_id, channel_id).open("rb") as fh:
        return pickle.load(fh)


def save_state(server_id: str, channel_id: str, state: TableState) -> None:
    with _state_path(server_id, channel_id).open("wb") as fh:
        pickle.dump(state, fh)


def state_exists(server_id: str, channel_id: str) -> bool:
    return _state_path(server_id, channel_id).exists()
