"""
Circuit breaker pattern for fault tolerance
Protects against cascading failures in feed connections
"""

from enum import Enum
from datetime import datetime, timedelta
import logging
from typing import Optional

from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class CircuitState(str, Enum):
    """States of the circuit breaker"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered


class CircuitBreaker:
    """
    Circuit breaker for fault tolerance
    
    Pattern:
    - CLOSED: Normal operation, requests go through
    - OPEN: Too many failures, requests are rejected
    - HALF_OPEN: Testing if service recovered
    """
    
    def __init__(
        self,
        venue: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception,
    ):
        self.venue = venue
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        # State tracking
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._opened_at: Optional[datetime] = None

    def record_success(self) -> None:
        """
        Record successful request
        """
        self._failure_count = 0
        
        # Transition from HALF_OPEN to CLOSED
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= 2:  # 2 successful requests to close
                self._close()
                logger.info(f"Circuit breaker for {self.venue} closed (recovered)")
        
        elif self._state == CircuitState.CLOSED:
            self._success_count = 0

    def record_failure(self, exception: Optional[Exception] = None) -> None:
        """
        Record failed request
        """
        self._last_failure_time = datetime.utcnow()
        self._failure_count += 1
        self._success_count = 0
        
        logger.warning(
            f"Circuit breaker for {self.venue}: failure {self._failure_count}/{self.failure_threshold}"
        )
        
        # Transition from HALF_OPEN to OPEN
        if self._state == CircuitState.HALF_OPEN:
            self.open()
            logger.error(f"Circuit breaker for {self.venue} re-opened (still failing)")
        
        # Transition from CLOSED to OPEN
        elif self._state == CircuitState.CLOSED:
            if self._failure_count >= self.failure_threshold:
                self.open()
                logger.error(
                    f"Circuit breaker for {self.venue} opened "
                    f"(threshold {self.failure_threshold} reached)"
                )

    def open(self) -> None:
        """
        Open circuit (reject requests)
        """
        self._state = CircuitState.OPEN
        self._opened_at = datetime.utcnow()
        self._failure_count = 0

    def _close(self) -> None:
        """
        Close circuit (resume normal operation)
        """
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._opened_at = None

    def _half_open(self) -> None:
        """
        Half-open circuit (test recovery)
        """
        self._state = CircuitState.HALF_OPEN
        self._success_count = 0
        logger.info(f"Circuit breaker for {self.venue} half-open (testing recovery)")

    def call(self, func, *args, **kwargs):
        """
        Execute function through circuit breaker
        """
        if self._state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._half_open()
            else:
                raise CircuitBreakerOpen(
                    f"Circuit breaker for {self.venue} is open"
                )
        
        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except self.expected_exception as e:
            self.record_failure(e)
            raise

    async def call_async(self, func, *args, **kwargs):
        """
        Execute async function through circuit breaker
        """
        if self._state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._half_open()
            else:
                raise CircuitBreakerOpen(
                    f"Circuit breaker for {self.venue} is open"
                )
        
        try:
            result = await func(*args, **kwargs)
            self.record_success()
            return result
        except self.expected_exception as e:
            self.record_failure(e)
            raise

    def _should_attempt_reset(self) -> bool:
        """
        Check if enough time has passed to attempt recovery
        """
        if not self._opened_at:
            return False
        
        elapsed = (datetime.utcnow() - self._opened_at).total_seconds()
        return elapsed >= self.recovery_timeout

    def is_open(self) -> bool:
        """Check if circuit is open"""
        return self._state == CircuitState.OPEN

    def is_closed(self) -> bool:
        """Check if circuit is closed"""
        return self._state == CircuitState.CLOSED

    def is_half_open(self) -> bool:
        """Check if circuit is half-open"""
        return self._state == CircuitState.HALF_OPEN

    @property
    def state(self) -> CircuitState:
        """Get current state"""
        return self._state

    @property
    def failure_count(self) -> int:
        """Get current failure count"""
        return self._failure_count

    def __repr__(self) -> str:
        return (
            f"CircuitBreaker(venue={self.venue}, state={self._state}, "
            f"failures={self._failure_count}/{self.failure_threshold})"
        )


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open"""
    pass
