"""Authentication system for Claude Code Chat using Anthropic OAuth tokens."""

import os
import uuid
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from functools import wraps

import requests
from flask import request, jsonify, g

from models import User

# In-memory session storage
# Format: {session_token: {user_id, anthropic_token, created_at, expires_at}}
sessions = {}

# Session configuration
SESSION_DURATION_HOURS = int(os.getenv("SESSION_DURATION_HOURS", 24))
ANTHROPIC_API_BASE = "https://api.anthropic.com"


def generate_session_token() -> str:
    """Generate a secure session token."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Hash a token for secure storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def validate_anthropic_token(token: str) -> Optional[dict]:
    """
    Validate an Anthropic OAuth token by making a test API request.

    Returns user info dict if valid, None if invalid.
    """
    headers = {
        "x-api-key": token,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }

    try:
        # Make a minimal API request to validate the token
        # Using the messages API with a tiny request
        response = requests.post(
            f"{ANTHROPIC_API_BASE}/v1/messages",
            headers=headers,
            json={
                "model": "claude-3-haiku-20240307",
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "hi"}]
            },
            timeout=10
        )

        if response.status_code == 200:
            # Token is valid - extract user info from response if available
            # For now, we use a hash of the token as user identifier
            token_hash = hash_token(token)
            return {
                "anthropic_user_id": token_hash[:32],  # Use first 32 chars of hash as ID
                "email": None,  # Anthropic doesn't expose email via API key auth
                "name": None
            }
        elif response.status_code == 401:
            return None
        else:
            # Other errors (rate limit, etc.) - token might still be valid
            # But we'll reject to be safe
            return None

    except requests.RequestException:
        return None


def validate_anthropic_oauth_token(token: str) -> Optional[dict]:
    """
    Validate an Anthropic OAuth token.

    OAuth tokens start with 'ant-oa-' prefix and work differently from API keys.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "anthropic-version": "2023-06-01",
        "anthropic-beta": "oauth-2025-04-20",
        "content-type": "application/json"
    }

    try:
        # Test the OAuth token with a minimal request
        response = requests.post(
            f"{ANTHROPIC_API_BASE}/v1/messages",
            headers=headers,
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "hi"}]
            },
            timeout=10
        )

        if response.status_code == 200:
            token_hash = hash_token(token)
            return {
                "anthropic_user_id": f"oauth_{token_hash[:28]}",
                "email": None,
                "name": None
            }
        else:
            return None

    except requests.RequestException:
        return None


def authenticate_token(token: str) -> Optional[dict]:
    """
    Authenticate a token - supports both API keys and OAuth tokens.

    Returns user info dict if valid, None if invalid.
    """
    if not token:
        return None

    # Check token type and validate accordingly
    if token.startswith("ant-oa-") or token.startswith("sk-ant-oa"):
        # OAuth token
        return validate_anthropic_oauth_token(token)
    elif token.startswith("sk-ant-"):
        # Standard API key
        return validate_anthropic_token(token)
    else:
        # Try as API key first, then OAuth
        result = validate_anthropic_token(token)
        if result:
            return result
        return validate_anthropic_oauth_token(token)


def create_session(user_id: str, anthropic_token: str) -> str:
    """Create a new session for a user."""
    session_token = generate_session_token()
    now = datetime.utcnow()
    expires_at = now + timedelta(hours=SESSION_DURATION_HOURS)

    sessions[session_token] = {
        "user_id": user_id,
        "anthropic_token": anthropic_token,
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat()
    }

    return session_token


def get_session(session_token: str) -> Optional[dict]:
    """Get session data if valid and not expired."""
    if session_token not in sessions:
        return None

    session = sessions[session_token]
    expires_at = datetime.fromisoformat(session["expires_at"])

    if datetime.utcnow() > expires_at:
        # Session expired, remove it
        del sessions[session_token]
        return None

    return session


def delete_session(session_token: str) -> bool:
    """Delete a session (logout)."""
    if session_token in sessions:
        del sessions[session_token]
        return True
    return False


def cleanup_expired_sessions():
    """Remove all expired sessions from memory."""
    now = datetime.utcnow()
    expired = [
        token for token, session in sessions.items()
        if datetime.fromisoformat(session["expires_at"]) < now
    ]
    for token in expired:
        del sessions[token]
    return len(expired)


def get_current_user() -> Optional[User]:
    """Get the currently authenticated user from the request context."""
    return getattr(g, 'current_user', None)


def get_current_session() -> Optional[dict]:
    """Get the current session data from the request context."""
    return getattr(g, 'current_session', None)


def require_auth(f):
    """Decorator to require authentication for an endpoint."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check for session token in Authorization header or cookie
        auth_header = request.headers.get("Authorization", "")
        session_token = None

        if auth_header.startswith("Bearer "):
            session_token = auth_header[7:]
        else:
            session_token = request.cookies.get("session_token")

        if not session_token:
            return jsonify({"success": False, "error": "Authentication required"}), 401

        session = get_session(session_token)
        if not session:
            return jsonify({"success": False, "error": "Invalid or expired session"}), 401

        user = User.get_by_id(session["user_id"])
        if not user:
            return jsonify({"success": False, "error": "User not found"}), 401

        # Store in request context
        g.current_user = user
        g.current_session = session
        g.session_token = session_token

        return f(*args, **kwargs)
    return decorated_function


def optional_auth(f):
    """Decorator for optional authentication - sets user if authenticated, but doesn't require it."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        session_token = None

        if auth_header.startswith("Bearer "):
            session_token = auth_header[7:]
        else:
            session_token = request.cookies.get("session_token")

        if session_token:
            session = get_session(session_token)
            if session:
                user = User.get_by_id(session["user_id"])
                if user:
                    g.current_user = user
                    g.current_session = session
                    g.session_token = session_token

        return f(*args, **kwargs)
    return decorated_function
