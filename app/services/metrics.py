from time import perf_counter
from typing import Any


class MetricsRecorder:
    def __init__(self):
        self._counts: dict[str, int] = {}
        self._durations: dict[str, list[float]] = {}

    def increment(self, name: str, value: int = 1) -> None:
        self._counts[name] = self._counts.get(name, 0) + value

    def observe(self, name: str, value: float) -> None:
        self._durations.setdefault(name, []).append(value)

    def snapshot(self) -> dict[str, Any]:
        return {
            "counts": dict(self._counts),
            "durations": {key: sum(values) / len(values) if values else 0 for key, values in self._durations.items()},
        }


metrics = MetricsRecorder()
