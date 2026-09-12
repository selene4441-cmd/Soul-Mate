from __future__ import annotations

import enum


class BehaviorEventType(str, enum.Enum):
    BROWSE = "browse"
    DWELL = "dwell"
    LIKE = "like"
    SWIPE = "swipe"


class ElicitationKind(str, enum.Enum):
    SINGLE_CHOICE = "single_choice"
    MULTI_CHOICE = "multi_choice"

