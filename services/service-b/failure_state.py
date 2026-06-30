import random
import time
from typing import Literal

FailureMode = Literal["latency", "error", "cpu_spike", "none"]


class FailureState:
    def __init__(self) -> None:
        self.mode: FailureMode = "none"
        self.magnitude: int = 0

    def set(self, mode: FailureMode, magnitude: int) -> None:
        self.mode = mode
        self.magnitude = max(0, magnitude)

    def apply(self) -> None:
        if self.mode == "none" or self.magnitude == 0:
            return

        if self.mode == "latency":
            time.sleep(self.magnitude / 1000.0)
            return

        if self.mode == "cpu_spike":
            deadline = time.perf_counter() + (self.magnitude / 1000.0)
            while time.perf_counter() < deadline:
                pass
            return

        if self.mode == "error":
            if random.randint(1, 100) <= min(self.magnitude, 100):
                raise RuntimeError("Injected failure: error mode triggered")


failure_state = FailureState()
