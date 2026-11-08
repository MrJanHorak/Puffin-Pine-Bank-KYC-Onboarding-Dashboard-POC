"""Circuit breaker for screen_watchlist (Day 9).

CLOSED: calls go through. After FAILURE_THRESHOLD failures in a row it goes
OPEN: calls stop, and the case ends SCREENING_UNAVAILABLE, a pending status.
After COOLDOWN_SECONDS one test call is allowed (HALF_OPEN); success closes
it again. This is a teaching model: the production fallback and kill switch
are CTD-built.
"""
import logging
import time

from kyc.log_config import log_event

logger = logging.getLogger("kyc.circuit_breaker")

FAILURE_THRESHOLD = 3    # failures in a row before the breaker opens
COOLDOWN_SECONDS = 30    # wait before one test call is allowed


class CircuitBreaker:
    def __init__(self, application_id: str, tool: str = "screen_watchlist"):
        self.application_id = application_id
        self.tool = tool
        self.state = "CLOSED"
        self.failures = 0
        self.opened_at = 0.0

    def move_to(self, state: str) -> None:
        """Change state and log it; opening is a WARNING."""
        level = logging.WARNING if state == "OPEN" else logging.INFO
        log_event(logger, "breaker_state", level=level, tool=self.tool,
                  application_id=self.application_id,
                  from_state=self.state, to_state=state)
        self.state = state

    def allow_call(self) -> bool:
        """True when a call may go to the tool."""
        if self.state == "OPEN":
            if time.monotonic() - self.opened_at < COOLDOWN_SECONDS:
                return False
            self.move_to("HALF_OPEN")
        return True

    def record_success(self) -> None:
        self.failures = 0
        if self.state == "HALF_OPEN":
            self.move_to("CLOSED")

    def record_failure(self) -> None:
        self.failures += 1
        if self.state == "HALF_OPEN" or self.failures >= FAILURE_THRESHOLD:
            self.opened_at = time.monotonic()
            self.move_to("OPEN")
