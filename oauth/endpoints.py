"""OAuth 2.1 endpoints for MCP server authentication.

This module contains all OAuth-related endpoints:
- Discovery metadata (/.well-known/*)
- Client registration (/register)
- Authorization flow (/authorize, /login, /signup, /consent)
- Token endpoint (/token)
"""

import secrets
import hashlib
import base64
import time
import logging

from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse

from oauth.stores import (
    registered_clients,
    authorization_codes,
    pending_authorizations,
    authenticated_sessions,
)
from oauth.jwt_utils import (
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
    ACCESS_TOKEN_EXPIRE_SECONDS,
)
from oauth.templates import LOGIN_PAGE, SIGNUP_PAGE, CONSENT_PAGE

logger = logging.getLogger(__name__)

# Router for OAuth endpoints
router = APIRouter(tags=["oauth"])

# These will be set by init_oauth_routes()
_server_url: str = ""
_supabase = None


def init_oauth_routes(server_url: str, supabase_client):
    """Initialize OAuth routes with server URL and Supabase client.

    Must be called before including the router in the app.
    """
    global _server_url, _supabase
    _server_url = server_url
    _supabase = supabase_client


# ============== OAuth 2.1 Discovery Endpoints ==============


@router.get("/.well-known/oauth-protected-resource")
async def oauth_protected_resource():
    """OAuth 2.0 Protected Resource Metadata (RFC 9728)."""
    return {
        "resource": _server_url,
        "authorization_servers": [_server_url],
        "scopes_supported": ["mcp:tools", "mcp:read"],
        "bearer_methods_supported": ["header"],
        "resource_documentation": f"{_server_url}/docs",
    }


@router.get("/.well-known/oauth-authorization-server")
async def oauth_authorization_server():
    """OAuth 2.0 Authorization Server Metadata (RFC 8414)."""
    return {
        "issuer": _server_url,
        "authorization_endpoint": f"{_server_url}/authorize",
        "token_endpoint": f"{_server_url}/token",
        "registration_endpoint": f"{_server_url}/register",
        "scopes_supported": ["mcp:tools", "mcp:read"],
        "response_types_supported": ["code"],
        "response_modes_supported": ["query"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "token_endpoint_auth_methods_supported": ["none", "client_secret_post"],
        "code_challenge_methods_supported": ["S256"],
        "service_documentation": f"{_server_url}/docs",
    }


# ============== Client Registration ==============


@router.post("/register")
async def register_client(request: Request):
    """OAuth 2.0 Dynamic Client Registration (RFC 7591)."""
    try:
        data = await request.json()
    except Exception:
        data = {}

    client_id = secrets.token_urlsafe(24)
    client_secret = secrets.token_urlsafe(32)
    logger.info(
        f"[REGISTER] Client registration request: {data.get('client_name', 'MCP Client')}"
    )

    client_info = {
        "client_id": client_id,
        "client_secret": client_secret,
        "client_name": data.get("client_name", "MCP Client"),
        "redirect_uris": data.get(
            "redirect_uris", ["https://chatgpt.com/connector_platform_oauth_redirect"]
        ),
        "grant_types": data.get("grant_types", ["authorization_code", "refresh_token"]),
        "response_types": data.get("response_types", ["code"]),
        "token_endpoint_auth_method": data.get("token_endpoint_auth_method", "none"),
        "created_at": int(time.time()),
    }

    registered_clients[client_id] = client_info
    logger.info(f"[REGISTER] Client registered: {client_id[:8]}...")

    return JSONResponse(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "client_name": client_info["client_name"],
            "redirect_uris": client_info["redirect_uris"],
            "grant_types": client_info["grant_types"],
            "response_types": client_info["response_types"],
            "token_endpoint_auth_method": client_info["token_endpoint_auth_method"],
        },
        status_code=201,
    )


# ============== Authorization Flow ==============


@router.get("/authorize")
async def authorize(
    request: Request,
    response_type: str = "code",
    client_id: str = "",
    redirect_uri: str = "",
    scope: str = "mcp:tools",
    state: str = "",
    code_challenge: str = "",
    code_challenge_method: str = "S256",
):
    """OAuth 2.0 Authorization Endpoint - redirects to login."""
    logger.info(
        f"[AUTHORIZE] Authorization request: client_id={client_id[:8] if client_id else 'none'}..., scope={scope}"
    )
    if response_type != "code":
        return JSONResponse({"error": "unsupported_response_type"}, status_code=400)

    # Generate session ID and store OAuth params
    session_id = secrets.token_urlsafe(32)
    pending_authorizations[session_id] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "created_at": int(time.time()),
        "expires_at": int(time.time()) + 600,  # 10 minutes
    }
    logger.info(
        f"[AUTHORIZE] Session created: {session_id[:8]}..., redirecting to login"
    )

    # Redirect to login page
    return RedirectResponse(url=f"/login?session={session_id}", status_code=302)


@router.get("/login")
async def login_page(session: str = "", registered: str = ""):
    """Show login form."""
    logger.info(
        f"[LOGIN] Login page requested: session={session[:8] if session else 'none'}..."
    )
    if not session or session not in pending_authorizations:
        return HTMLResponse("<h1>Invalid or expired session</h1>", status_code=400)

    # Check if session expired
    auth_data = pending_authorizations[session]
    if time.time() > auth_data["expires_at"]:
        del pending_authorizations[session]
        return HTMLResponse(
            "<h1>Session expired. Please try again.</h1>", status_code=400
        )

    # Show success message if user just registered
    success_msg = ""
    if registered == "1":
        success_msg = (
            '<div class="success">Account created successfully! Please sign in.</div>'
        )

    return HTMLResponse(
        LOGIN_PAGE.format(session=session, error="", success=success_msg)
    )


@router.post("/login")
async def login_submit(
    session: str = Form(...), email: str = Form(...), password: str = Form(...)
):
    """Handle login form submission."""
    if not session or session not in pending_authorizations:
        return HTMLResponse("<h1>Invalid or expired session</h1>", status_code=400)

    auth_data = pending_authorizations[session]
    if time.time() > auth_data["expires_at"]:
        del pending_authorizations[session]
        return HTMLResponse(
            "<h1>Session expired. Please try again.</h1>", status_code=400
        )

    # Authenticate with Supabase
    if not _supabase:
        # Fallback: accept any login if Supabase not configured
        authenticated_sessions[session] = {"email": email, "user_id": "demo-user"}
        return RedirectResponse(url=f"/consent?session={session}", status_code=302)

    try:
        response = _supabase.auth.sign_in_with_password(
            {"email": email, "password": password}
        )

        if response.user:
            logger.info(f"[LOGIN] User authenticated: {response.user.email}")
            authenticated_sessions[session] = {
                "email": response.user.email,
                "user_id": response.user.id,
            }
            return RedirectResponse(url=f"/consent?session={session}", status_code=302)
        else:
            logger.info(
                f"[LOGIN] Login failed: invalid credentials for session {session[:8]}..."
            )
            error_html = '<div class="error">Invalid email or password</div>'
            return HTMLResponse(
                LOGIN_PAGE.format(session=session, error=error_html, success="")
            )
    except Exception as e:
        logger.info(
            f"[LOGIN] Login failed: authentication error for session {session[:8]}..."
        )
        error_html = f'<div class="error">Authentication failed: {str(e)}</div>'
        return HTMLResponse(
            LOGIN_PAGE.format(session=session, error=error_html, success="")
        )


@router.get("/signup")
async def signup_page(session: str = ""):
    """Show signup form."""
    logger.info(
        f"[SIGNUP] Signup page requested: session={session[:8] if session else 'none'}..."
    )
    if not session or session not in pending_authorizations:
        return HTMLResponse("<h1>Invalid or expired session</h1>", status_code=400)

    # Check if session expired
    auth_data = pending_authorizations[session]
    if time.time() > auth_data["expires_at"]:
        del pending_authorizations[session]
        return HTMLResponse(
            "<h1>Session expired. Please try again.</h1>", status_code=400
        )

    return HTMLResponse(SIGNUP_PAGE.format(session=session, error=""))


@router.post("/signup")
async def signup_submit(
    session: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
):
    """Handle signup form submission."""
    if not session or session not in pending_authorizations:
        return HTMLResponse("<h1>Invalid or expired session</h1>", status_code=400)

    auth_data = pending_authorizations[session]
    if time.time() > auth_data["expires_at"]:
        del pending_authorizations[session]
        return HTMLResponse(
            "<h1>Session expired. Please try again.</h1>", status_code=400
        )

    # Validate passwords match
    if password != confirm_password:
        error_html = '<div class="error">Passwords do not match</div>'
        return HTMLResponse(SIGNUP_PAGE.format(session=session, error=error_html))

    # Validate password length
    if len(password) < 6:
        error_html = '<div class="error">Password must be at least 6 characters</div>'
        return HTMLResponse(SIGNUP_PAGE.format(session=session, error=error_html))

    # Create account with Supabase
    if not _supabase:
        # Fallback: just redirect to login if Supabase not configured
        return RedirectResponse(
            url=f"/login?session={session}&registered=1", status_code=302
        )

    try:
        response = _supabase.auth.sign_up({"email": email, "password": password})

        if response.user:
            logger.info(f"[SIGNUP] Account created: {email}")
            return RedirectResponse(
                url=f"/login?session={session}&registered=1", status_code=302
            )
        else:
            logger.info(
                f"[SIGNUP] Account creation failed for session: {session[:8]}..."
            )
            error_html = '<div class="error">Failed to create account</div>'
            return HTMLResponse(SIGNUP_PAGE.format(session=session, error=error_html))
    except Exception as e:
        error_msg = str(e)
        if "already registered" in error_msg.lower():
            logger.info(
                f"[SIGNUP] Signup failed: email already exists for session: {session[:8]}..."
            )
            error_html = (
                '<div class="error">An account with this email already exists</div>'
            )
        else:
            logger.info(
                f"[SIGNUP] Signup failed: {error_msg[:50]} for session: {session[:8]}..."
            )
            error_html = f'<div class="error">Signup failed: {error_msg}</div>'
        return HTMLResponse(SIGNUP_PAGE.format(session=session, error=error_html))


# ============== Consent ==============


@router.get("/consent")
async def consent_page(session: str = ""):
    """Show consent/authorization page."""
    if not session or session not in pending_authorizations:
        return HTMLResponse("<h1>Invalid or expired session</h1>", status_code=400)

    if session not in authenticated_sessions:
        return RedirectResponse(url=f"/login?session={session}", status_code=302)

    user_info = authenticated_sessions[session]
    logger.info(f"[CONSENT] Consent page shown to user: {user_info.get('email')}")
    return HTMLResponse(
        CONSENT_PAGE.format(
            session=session, user_email=user_info.get("email", "Unknown")
        )
    )


@router.post("/consent")
async def consent_submit(session: str = Form(...), action: str = Form(...)):
    """Handle consent form submission."""
    from urllib.parse import urlencode

    if not session or session not in pending_authorizations:
        return HTMLResponse("<h1>Invalid or expired session</h1>", status_code=400)

    auth_data = pending_authorizations[session]
    redirect_uri = auth_data["redirect_uri"]
    state = auth_data.get("state", "")

    if action == "deny":
        # User denied access
        logger.info(f"[CONSENT] User denied access for session: {session[:8]}...")
        del pending_authorizations[session]
        if session in authenticated_sessions:
            del authenticated_sessions[session]

        params = {"error": "access_denied", "error_description": "User denied access"}
        if state:
            params["state"] = state
        return RedirectResponse(
            url=f"{redirect_uri}?{urlencode(params)}", status_code=302
        )

    # User approved - generate authorization code
    user_info = authenticated_sessions.get(session, {})
    logger.info(f"[CONSENT] User granted consent: {user_info.get('email')}")
    auth_code = secrets.token_urlsafe(32)

    authorization_codes[auth_code] = {
        "client_id": auth_data["client_id"],
        "redirect_uri": auth_data["redirect_uri"],
        "scope": auth_data["scope"],
        "code_challenge": auth_data["code_challenge"],
        "code_challenge_method": auth_data["code_challenge_method"],
        "user_id": user_info.get("user_id"),
        "user_email": user_info.get("email"),
        "created_at": int(time.time()),
        "expires_at": int(time.time()) + 600,  # 10 minutes
    }
    logger.info(
        f"[CONSENT] Authorization code issued for client: {auth_data['client_id'][:8]}..."
    )

    # Clean up session data
    del pending_authorizations[session]
    if session in authenticated_sessions:
        del authenticated_sessions[session]

    # Redirect back with code
    params = {"code": auth_code}
    if state:
        params["state"] = state
    return RedirectResponse(url=f"{redirect_uri}?{urlencode(params)}", status_code=302)


# ============== Token Endpoint ==============


@router.post("/token")
async def token(
    request: Request,
    grant_type: str = Form(None),
    code: str = Form(None),
    redirect_uri: str = Form(None),
    client_id: str = Form(None),
    client_secret: str = Form(None),
    code_verifier: str = Form(None),
    refresh_token: str = Form(None),
):
    """OAuth 2.0 Token Endpoint."""
    # Handle form data or JSON
    if grant_type is None:
        try:
            data = await request.json()
            grant_type = data.get("grant_type")
            code = data.get("code")
            client_id = data.get("client_id")
            code_verifier = data.get("code_verifier")
            refresh_token = data.get("refresh_token")
        except Exception:
            return JSONResponse({"error": "invalid_request"}, status_code=400)

    logger.info(
        f"[TOKEN] Token request: grant_type={grant_type}, client_id={client_id[:8] if client_id else 'none'}..."
    )

    if grant_type == "authorization_code":
        if not code or code not in authorization_codes:
            logger.info("[TOKEN] Token request failed: invalid authorization code")
            return JSONResponse({"error": "invalid_grant"}, status_code=400)

        auth_data = authorization_codes[code]

        # Check expiration
        if time.time() > auth_data["expires_at"]:
            del authorization_codes[code]
            logger.info("[TOKEN] Token request failed: authorization code expired")
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "Code expired"},
                status_code=400,
            )

        # Verify PKCE
        if auth_data.get("code_challenge") and code_verifier:
            expected = (
                base64.urlsafe_b64encode(
                    hashlib.sha256(code_verifier.encode()).digest()
                )
                .rstrip(b"=")
                .decode()
            )

            if expected != auth_data["code_challenge"]:
                logger.info("[TOKEN] Token request failed: PKCE verification failed")
                return JSONResponse(
                    {
                        "error": "invalid_grant",
                        "error_description": "PKCE verification failed",
                    },
                    status_code=400,
                )

        # Generate JWT tokens (stateless - no storage needed)
        user_id = auth_data.get("user_id") or ""
        user_email = auth_data.get("user_email") or ""
        scope = auth_data["scope"]
        expires_in = ACCESS_TOKEN_EXPIRE_SECONDS  # 24 hours

        new_access_token = create_access_token(
            user_id=user_id,
            user_email=user_email,
            client_id=client_id or "",
            scope=scope,
            issuer=_server_url,
            expires_in=expires_in,
        )

        new_refresh_token = create_refresh_token(
            user_id=user_id,
            user_email=user_email,
            client_id=client_id or "",
            scope=scope,
            issuer=_server_url,
        )

        logger.info(f"[TOKEN] JWT access token created for user: {user_email}")

        # Clean up used code
        del authorization_codes[code]

        return JSONResponse(
            {
                "access_token": new_access_token,
                "token_type": "Bearer",
                "expires_in": expires_in,
                "refresh_token": new_refresh_token,
                "scope": auth_data["scope"],
            }
        )

    elif grant_type == "refresh_token":
        # Verify the refresh token (JWT-based, stateless)
        token_data = verify_refresh_token(refresh_token, issuer=_server_url)

        if not token_data:
            logger.info("[TOKEN] Refresh token failed: invalid or expired token")
            return JSONResponse(
                {
                    "error": "invalid_grant",
                    "error_description": "Invalid or expired refresh token",
                },
                status_code=400,
            )

        # Extract user info from the verified token
        user_id = token_data.get("sub", "")
        user_email = token_data.get("email", "")
        scope = token_data.get("scope", "mcp:tools")
        expires_in = ACCESS_TOKEN_EXPIRE_SECONDS  # 24 hours

        # Generate new JWT tokens
        new_access_token = create_access_token(
            user_id=user_id,
            user_email=user_email,
            client_id=client_id or "",
            scope=scope,
            issuer=_server_url,
            expires_in=expires_in,
        )

        new_refresh_token = create_refresh_token(
            user_id=user_id,
            user_email=user_email,
            client_id=client_id or "",
            scope=scope,
            issuer=_server_url,
        )

        logger.info(
            f"[TOKEN] JWT refresh successful for user: {user_email}, client: {client_id[:8] if client_id else 'none'}..."
        )

        return JSONResponse(
            {
                "access_token": new_access_token,
                "token_type": "Bearer",
                "expires_in": expires_in,
                "refresh_token": new_refresh_token,
                "scope": scope,
            }
        )

    return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)
