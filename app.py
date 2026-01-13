"""Claude Code Chat - A web frontend for Claude Code CLI with authentication and sessions."""

import os
import subprocess

from flask import Flask, render_template, request, jsonify, make_response
from dotenv import load_dotenv

from models import init_db, User, Conversation, Message
from auth import (
    authenticate_token, create_session, get_session, delete_session,
    require_auth, optional_auth, get_current_user, get_current_session,
    cleanup_expired_sessions
)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", os.urandom(24))

# Configuration
TIMEOUT = int(os.getenv("CLAUDE_TIMEOUT", 120))
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "You are a helpful assistant. Be concise and clear.")

# Initialize database on startup
init_db()


# ============================================================================
# Authentication Endpoints
# ============================================================================

@app.route("/api/auth/login", methods=["POST"])
def login():
    """
    Authenticate with an Anthropic token (API key or OAuth token).

    Request body: { "token": "sk-ant-..." or "ant-oa-..." }
    Response: { "success": true, "user": {...}, "session_token": "..." }
    """
    try:
        data = request.get_json()
        token = data.get("token", "").strip()

        if not token:
            return jsonify({"success": False, "error": "Token is required"}), 400

        # Validate the token with Anthropic
        user_info = authenticate_token(token)
        if not user_info:
            return jsonify({"success": False, "error": "Invalid token"}), 401

        # Get or create user
        user = User.get_by_anthropic_id(user_info["anthropic_user_id"])
        if not user:
            user = User.create(
                anthropic_user_id=user_info["anthropic_user_id"],
                email=user_info.get("email"),
                name=user_info.get("name")
            )

        user.update_last_login()

        # Create session
        session_token = create_session(user.id, token)

        response = make_response(jsonify({
            "success": True,
            "user": user.to_dict(),
            "session_token": session_token
        }))

        # Also set as cookie for convenience
        response.set_cookie(
            "session_token",
            session_token,
            httponly=True,
            samesite="Lax",
            max_age=86400  # 24 hours
        )

        return response

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/auth/logout", methods=["POST"])
@require_auth
def logout():
    """Log out the current user and invalidate their session."""
    from flask import g
    session_token = getattr(g, 'session_token', None)
    if session_token:
        delete_session(session_token)

    response = make_response(jsonify({"success": True}))
    response.delete_cookie("session_token")
    return response


@app.route("/api/auth/verify", methods=["GET"])
@require_auth
def verify():
    """Verify the current session and return user info."""
    user = get_current_user()
    return jsonify({
        "success": True,
        "user": user.to_dict()
    })


@app.route("/api/auth/me", methods=["GET"])
@optional_auth
def me():
    """Get current user info if authenticated."""
    user = get_current_user()
    if user:
        return jsonify({
            "authenticated": True,
            "user": user.to_dict()
        })
    return jsonify({"authenticated": False})


# ============================================================================
# Conversation Endpoints
# ============================================================================

@app.route("/api/conversations", methods=["GET"])
@require_auth
def list_conversations():
    """List all conversations for the current user."""
    user = get_current_user()
    conversations = Conversation.get_by_user(user.id)
    return jsonify({
        "success": True,
        "conversations": [c.to_dict() for c in conversations]
    })


@app.route("/api/conversations", methods=["POST"])
@require_auth
def create_conversation():
    """Create a new conversation."""
    user = get_current_user()
    data = request.get_json() or {}
    title = data.get("title", "New Conversation")

    conversation = Conversation.create(user_id=user.id, title=title)
    return jsonify({
        "success": True,
        "conversation": conversation.to_dict()
    }), 201


@app.route("/api/conversations/<conversation_id>", methods=["GET"])
@require_auth
def get_conversation(conversation_id):
    """Get a specific conversation with its messages."""
    user = get_current_user()
    conversation = Conversation.get_by_id(conversation_id)

    if not conversation:
        return jsonify({"success": False, "error": "Conversation not found"}), 404

    if conversation.user_id != user.id:
        return jsonify({"success": False, "error": "Access denied"}), 403

    return jsonify({
        "success": True,
        "conversation": conversation.to_dict(include_messages=True)
    })


@app.route("/api/conversations/<conversation_id>", methods=["PATCH"])
@require_auth
def update_conversation(conversation_id):
    """Update a conversation (e.g., rename)."""
    user = get_current_user()
    conversation = Conversation.get_by_id(conversation_id)

    if not conversation:
        return jsonify({"success": False, "error": "Conversation not found"}), 404

    if conversation.user_id != user.id:
        return jsonify({"success": False, "error": "Access denied"}), 403

    data = request.get_json() or {}
    if "title" in data:
        conversation.update_title(data["title"])

    return jsonify({
        "success": True,
        "conversation": conversation.to_dict()
    })


@app.route("/api/conversations/<conversation_id>", methods=["DELETE"])
@require_auth
def delete_conversation(conversation_id):
    """Delete a conversation and all its messages."""
    user = get_current_user()
    conversation = Conversation.get_by_id(conversation_id)

    if not conversation:
        return jsonify({"success": False, "error": "Conversation not found"}), 404

    if conversation.user_id != user.id:
        return jsonify({"success": False, "error": "Access denied"}), 403

    conversation.delete()
    return jsonify({"success": True})


# ============================================================================
# Chat Endpoint (Updated with authentication and persistence)
# ============================================================================

@app.route("/api/chat", methods=["POST"])
@require_auth
def chat():
    """
    Chat with Claude using Claude Code CLI.

    Request body: {
        "message": "user message",
        "conversation_id": "optional - will create new if not provided"
    }
    """
    try:
        user = get_current_user()
        session = get_current_session()
        data = request.get_json()
        message = data.get("message", "")
        conversation_id = data.get("conversation_id")

        if not message:
            return jsonify({"success": False, "error": "No message provided"}), 400

        # Get or create conversation
        conversation = None
        if conversation_id:
            conversation = Conversation.get_by_id(conversation_id)
            if conversation and conversation.user_id != user.id:
                return jsonify({"success": False, "error": "Access denied"}), 403

        if not conversation:
            # Create new conversation with first message as title
            title = message[:50] + "..." if len(message) > 50 else message
            conversation = Conversation.create(user_id=user.id, title=title)

        # Get conversation history
        history = conversation.get_messages()

        # Build prompt with conversation history
        prompt = f"{SYSTEM_PROMPT}\n\n"

        if history:
            prompt += "Previous conversation:\n"
            for msg in history:
                role = "User" if msg.role == "user" else "Assistant"
                prompt += f"{role}: {msg.content}\n\n"

        prompt += f"User: {message}"

        # Save user message
        Message.create(
            conversation_id=conversation.id,
            role="user",
            content=message
        )

        # Set the Anthropic token from the session for the CLI
        env = os.environ.copy()
        anthropic_token = session.get("anthropic_token")
        if anthropic_token:
            # Check if it's an OAuth token or API key and set appropriate env var
            if anthropic_token.startswith("ant-oa-") or anthropic_token.startswith("sk-ant-oa"):
                env["CLAUDE_CODE_OAUTH_TOKEN"] = anthropic_token
            else:
                env["ANTHROPIC_API_KEY"] = anthropic_token

        # Use Claude Code CLI in print mode (-p)
        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            env=env
        )

        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or "Claude Code failed"
            return jsonify({"success": False, "error": error_msg}), 500

        assistant_response = result.stdout.strip()

        # Save assistant response
        Message.create(
            conversation_id=conversation.id,
            role="assistant",
            content=assistant_response
        )

        return jsonify({
            "success": True,
            "response": assistant_response,
            "conversation_id": conversation.id
        })

    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "error": "Request timed out"}), 500
    except FileNotFoundError:
        return jsonify({"success": False, "error": "Claude Code CLI not found. Please install it first."}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================================
# Legacy/Public Endpoints
# ============================================================================

@app.route("/")
def index():
    """Main chat interface."""
    return render_template("index.html")


@app.route("/health")
def health():
    """Health check endpoint."""
    # Cleanup expired sessions periodically
    cleanup_expired_sessions()
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 5007))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    app.run(host=host, port=port, debug=debug)
