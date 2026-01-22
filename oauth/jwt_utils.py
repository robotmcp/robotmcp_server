"""JWT utilities for OAuth access tokens.

Provides stateless token generation and validation using PyJWT.
Tokens survive server restarts since validation is done via signature verification,
not by looking up tokens in an in-memory store.
"""

import os
import secrets
import logging
from pathlib import Path
from typing import Optional
import jwt

logger = logging.getLogger(__name__)

# JWT configuration
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_SECONDS = 24 * 60 * 60  # 24 hours
REFRESH_TOKEN_EXPIRE_SECONDS = 30 * 24 * 60 * 60  # 30 days

# Secret key storage
_jwt_secret: Optional[str] = None
SECRET_FILE = Path.home() / ".robotmcp-server" / "jwt_secret"


def _get_or_create_secret() -> str:
    """Get JWT secret from file, or create one if it doesn't exist.

    The secret is stored in ~/.robotmcp-server/jwt_secret
    This ensures tokens remain valid across server restarts.
    """
    global _jwt_secret

    if _jwt_secret:
        return _jwt_secret

    # Check environment variable first (for production deployments)
    env_secret = os.getenv("JWT_SECRET")
    if env_secret:
        _jwt_secret = env_secret
        logger.info("[JWT] Using JWT_SECRET from environment")
        return _jwt_secret

    # Check file
    if SECRET_FILE.exists():
        try:
            _jwt_secret = SECRET_FILE.read_text().strip()
            if _jwt_secret:
                logger.info("[JWT] Loaded JWT secret from file")
                return _jwt_secret
        except IOError:
            pass

    # Generate new secret
    _jwt_secret = secrets.token_urlsafe(64)

    # Save to file
    try:
        SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
        SECRET_FILE.write_text(_jwt_secret)
        os.chmod(SECRET_FILE, 0o600)  # Owner read/write only
        logger.info("[JWT] Generated and saved new JWT secret")
    except IOError as e:
        logger.warning(f"[JWT] Could not save JWT secret to file: {e}")

    return _jwt_secret


def create_access_token(
    user_id: str,
    user_email: str,
    client_id: str,
    scope: str,
    issuer: str,
    expires_in: int = ACCESS_TOKEN_EXPIRE_SECONDS,
) -> str:
    """Create a JWT access token.

    Args:
        user_id: The user's unique identifier
        user_email: The user's email address
        client_id: The OAuth client ID
        scope: The granted OAuth scope
        issuer: The token issuer (server URL)
        expires_in: Token lifetime in seconds (default 24 hours)

    Returns:
        A signed JWT token string
    """
    import time

    secret = _get_or_create_secret()
    now = int(time.time())

    payload = {
        "sub": user_id,  # Subject (user ID) - standard claim
        "email": user_email,  # User email
        "client_id": client_id,  # OAuth client
        "scope": scope,  # OAuth scope
        "iss": issuer,  # Issuer - standard claim
        "iat": now,  # Issued at - standard claim
        "exp": now + expires_in,  # Expiration - standard claim
        "type": "access",  # Token type
    }

    token = jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)
    return token


def create_refresh_token(
    user_id: str,
    user_email: str,
    client_id: str,
    scope: str,
    issuer: str,
    expires_in: int = REFRESH_TOKEN_EXPIRE_SECONDS,
) -> str:
    """Create a JWT refresh token.

    Args:
        user_id: The user's unique identifier
        user_email: The user's email address
        client_id: The OAuth client ID
        scope: The granted OAuth scope
        issuer: The token issuer (server URL)
        expires_in: Token lifetime in seconds (default 30 days)

    Returns:
        A signed JWT token string
    """
    import time

    secret = _get_or_create_secret()
    now = int(time.time())

    payload = {
        "sub": user_id,  # Subject (user ID)
        "email": user_email,  # User email
        "client_id": client_id,  # OAuth client
        "scope": scope,  # OAuth scope
        "iss": issuer,  # Issuer
        "iat": now,  # Issued at
        "exp": now + expires_in,  # Expiration
        "type": "refresh",  # Token type
    }

    token = jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)
    return token


def verify_access_token(token: str, issuer: str = None) -> Optional[dict]:
    """Verify and decode a JWT access token.

    Args:
        token: The JWT token string
        issuer: Expected issuer (optional, for additional validation)

    Returns:
        The decoded token payload if valid, None otherwise.
        The payload contains: sub, email, client_id, scope, iss, iat, exp, type
    """
    secret = _get_or_create_secret()

    try:
        options = {"require": ["exp", "sub"]}
        if issuer:
            payload = jwt.decode(
                token,
                secret,
                algorithms=[JWT_ALGORITHM],
                options=options,
                issuer=issuer,
            )
        else:
            payload = jwt.decode(
                token, secret, algorithms=[JWT_ALGORITHM], options=options
            )

        # Verify it's an access token
        if payload.get("type") != "access":
            logger.debug("[JWT] Token is not an access token")
            return None

        return payload

    except jwt.ExpiredSignatureError:
        logger.debug("[JWT] Token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.debug(f"[JWT] Invalid token: {e}")
        return None


def verify_refresh_token(token: str, issuer: str = None) -> Optional[dict]:
    """Verify and decode a JWT refresh token.

    Args:
        token: The JWT token string
        issuer: Expected issuer (optional)

    Returns:
        The decoded token payload if valid, None otherwise.
    """
    secret = _get_or_create_secret()

    try:
        options = {"require": ["exp", "sub"]}
        if issuer:
            payload = jwt.decode(
                token,
                secret,
                algorithms=[JWT_ALGORITHM],
                options=options,
                issuer=issuer,
            )
        else:
            payload = jwt.decode(
                token, secret, algorithms=[JWT_ALGORITHM], options=options
            )

        # Verify it's a refresh token
        if payload.get("type") != "refresh":
            logger.debug("[JWT] Token is not a refresh token")
            return None

        return payload

    except jwt.ExpiredSignatureError:
        logger.debug("[JWT] Refresh token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.debug(f"[JWT] Invalid refresh token: {e}")
        return None
