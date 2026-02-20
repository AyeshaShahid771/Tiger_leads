"""
Rate Limiting Utilities

Provides simple in-memory rate limiting for authentication endpoints.
Tracks attempts by IP address and email to prevent brute force attacks.
"""

import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, Request


class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self):
        # Store attempts: key -> list of timestamps
        self.attempts = defaultdict(list)
        self.cleanup_interval = 300  # Cleanup every 5 minutes
        self.last_cleanup = time.time()
    
    def _cleanup_old_attempts(self):
        """Remove old attempts to prevent memory buildup."""
        current_time = time.time()
        if current_time - self.last_cleanup < self.cleanup_interval:
            return
        
        # Remove entries older than 1 hour
        cutoff = current_time - 3600
        keys_to_remove = []
        
        for key, timestamps in self.attempts.items():
            # Filter out old timestamps
            self.attempts[key] = [ts for ts in timestamps if ts > cutoff]
            # Mark empty entries for removal
            if not self.attempts[key]:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.attempts[key]
        
        self.last_cleanup = current_time
    
    def is_allowed(
        self,
        key: str,
        max_attempts: int = 5,
        window_seconds: int = 300
    ) -> tuple[bool, Optional[int]]:
        """Check if a request is allowed based on rate limits.
        
        Args:
            key: Unique identifier for rate limiting (e.g., IP or email)
            max_attempts: Maximum number of attempts allowed
            window_seconds: Time window in seconds
            
        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        self._cleanup_old_attempts()
        
        current_time = time.time()
        cutoff_time = current_time - window_seconds
        
        # Get recent attempts for this key
        recent_attempts = [
            ts for ts in self.attempts[key]
            if ts > cutoff_time
        ]
        
        # Update attempts list
        self.attempts[key] = recent_attempts
        
        # Check if limit exceeded
        if len(recent_attempts) >= max_attempts:
            # Calculate when the oldest attempt will expire
            oldest_attempt = min(recent_attempts)
            retry_after = int(oldest_attempt + window_seconds - current_time)
            return False, max(retry_after, 1)
        
        # Record this attempt
        self.attempts[key].append(current_time)
        return True, None
    
    def reset(self, key: str):
        """Reset rate limit for a specific key."""
        if key in self.attempts:
            del self.attempts[key]


# Global rate limiter instance
rate_limiter = RateLimiter()


def check_rate_limit(
    identifier: str,
    max_attempts: int = 5,
    window_seconds: int = 300,
    error_message: str = "Too many requests. Please try again later."
):
    """Check rate limit and raise HTTPException if exceeded.
    
    Args:
        identifier: Unique identifier for rate limiting
        max_attempts: Maximum attempts allowed
        window_seconds: Time window in seconds
        error_message: Custom error message
        
    Raises:
        HTTPException: If rate limit is exceeded
    """
    is_allowed, retry_after = rate_limiter.is_allowed(
        identifier, max_attempts, window_seconds
    )
    
    if not is_allowed:
        raise HTTPException(
            status_code=429,
            detail=f"{error_message} Retry after {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)}
        )


async def rate_limit_by_ip(
    request: Request,
    max_attempts: int = 5,
    window_seconds: int = 300
):
    """Dependency for rate limiting by IP address.
    
    Usage:
        @router.post("/endpoint", dependencies=[Depends(rate_limit_by_ip)])
    """
    # Get client IP
    client_ip = request.client.host if request.client else "unknown"
    
    # Also check X-Forwarded-For header for proxied requests
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
    
    check_rate_limit(
        f"ip:{client_ip}",
        max_attempts=max_attempts,
        window_seconds=window_seconds,
        error_message="Too many requests from your IP address"
    )


def rate_limit_by_email(email: str, max_attempts: int = 5, window_seconds: int = 300):
    """Rate limit by email address.
    
    Usage:
        rate_limit_by_email(email, max_attempts=5, window_seconds=300)
    """
    check_rate_limit(
        f"email:{email.lower()}",
        max_attempts=max_attempts,
        window_seconds=window_seconds,
        error_message=f"Too many requests for {email}"
    )


def rate_limit_by_identifier(
    identifier: str,
    max_attempts: int = 5,
    window_seconds: int = 300
):
    """Generic rate limiter by any identifier.
    
    Usage:
        rate_limit_by_identifier("otp:user@example.com", max_attempts=5, window_seconds=300)
    """
    check_rate_limit(
        identifier,
        max_attempts=max_attempts,
        window_seconds=window_seconds
    )
