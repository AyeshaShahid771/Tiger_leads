import os
import secrets
from datetime import datetime, timedelta

from dotenv import load_dotenv
from jose import jwt

load_dotenv()

# JWT settings
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-here")
# Change this in production
ALGORITHM = "HS256"

# Access token expiry (short-lived for security)
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # default 24 hours


# Refresh token expiry (long-lived)
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Legacy support for ACCESS_TOKEN_EXPIRE_HOURS
env_val = os.getenv("JWT_ACCESS_TOKEN_EXPIRE_HOURS")
if env_val is None or env_val == "":
    ACCESS_TOKEN_EXPIRE_HOURS = None
else:
    try:
        ACCESS_TOKEN_EXPIRE_HOURS = int(env_val)
    except Exception:
        # Fallback to None (no expiry) on parse error
        ACCESS_TOKEN_EXPIRE_HOURS = None


def create_access_token(data: dict, expires_delta: timedelta = None):
    """Create a JWT access token (short-lived).

    Args:
        data: Payload data to encode in the token
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT access token
    """
    to_encode = data.copy()
    now = datetime.utcnow()
    to_encode.update({"iat": int(now.timestamp())})
    to_encode.update({"type": "access"})  # Mark token type

    # Use custom expiry if provided, otherwise use configured expiry
    if expires_delta:
        expire = now + expires_delta
    elif ACCESS_TOKEN_EXPIRE_HOURS is not None and ACCESS_TOKEN_EXPIRE_HOURS > 0:
        # Legacy support
        expire = now + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    else:
        # Default: 15 minutes
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": int(expire.timestamp())})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> tuple[str, datetime]:
    """Create a JWT refresh token (long-lived) and return token + expiry.

    Args:
        data: Payload data to encode in the token

    Returns:
        Tuple of (encoded_jwt, expires_at_datetime)
    """
    to_encode = data.copy()
    now = datetime.utcnow()
    expire = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    # Add unique token ID for tracking
    to_encode.update(
        {
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
            "type": "refresh",  # Mark token type
            "jti": secrets.token_urlsafe(32),  # Unique token ID
        }
    )

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt, expire


def verify_token(token: str):
    """Verify and decode a JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.JWTError:
        return None
