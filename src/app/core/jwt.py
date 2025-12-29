import os
from datetime import datetime, timedelta

from dotenv import load_dotenv
from jose import jwt

load_dotenv()

# JWT settings
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-here")
# Change this in production
ALGORITHM = "HS256"

# Token expiry behaviour:
# - If the environment variable `JWT_ACCESS_TOKEN_EXPIRE_HOURS` is NOT set,
#   tokens will be created without an `exp` claim (i.e. they will not expire).
# - If `JWT_ACCESS_TOKEN_EXPIRE_HOURS` is set to a positive integer, tokens
#   will include an `exp` claim with that lifetime (hours).
# - If set to 0 or a non-positive integer, the `exp` claim will be omitted.
env_val = os.getenv("JWT_ACCESS_TOKEN_EXPIRE_HOURS")
if env_val is None or env_val == "":
    ACCESS_TOKEN_EXPIRE_HOURS = None
else:
    try:
        ACCESS_TOKEN_EXPIRE_HOURS = int(env_val)
    except Exception:
        # Fallback to None (no expiry) on parse error
        ACCESS_TOKEN_EXPIRE_HOURS = None


def create_access_token(data: dict):
    """Create a JWT token. By default tokens do not expire unless
    `JWT_ACCESS_TOKEN_EXPIRE_HOURS` is set to a positive integer.
    """
    to_encode = data.copy()
    if ACCESS_TOKEN_EXPIRE_HOURS is not None and ACCESS_TOKEN_EXPIRE_HOURS > 0:
        expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
        to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str):
    """Verify and decode a JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.JWTError:
        return None
