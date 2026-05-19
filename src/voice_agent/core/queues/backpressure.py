"""Backpressure policy names for queue consumers."""

from enum import StrEnum


class BackpressurePolicy(StrEnum):
    BLOCK = "block"
    DROP_OLDEST = "drop_oldest"
    DROP_STALE_SEQUENCE = "drop_stale_sequence"
    DROP_METRICS = "drop_metrics"
