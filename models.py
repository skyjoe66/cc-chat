"""Database models for Claude Code Chat."""

import sqlite3
import uuid
from datetime import datetime
from typing import Optional
from contextlib import contextmanager

DATABASE_PATH = "claude_chat.db"


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Initialize the database with required tables."""
    with get_db() as conn:
        cursor = conn.cursor()

        # Users table - stores authenticated users
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                anthropic_user_id TEXT UNIQUE,
                email TEXT,
                name TEXT,
                created_at TEXT NOT NULL,
                last_login_at TEXT
            )
        """)

        # Conversations table - stores chat sessions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Messages table - stores individual messages
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
        """)

        # Create indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations(updated_at)")

        conn.commit()


class User:
    """User model for authenticated users."""

    def __init__(self, id: str, anthropic_user_id: str, email: Optional[str] = None,
                 name: Optional[str] = None, created_at: Optional[str] = None,
                 last_login_at: Optional[str] = None):
        self.id = id
        self.anthropic_user_id = anthropic_user_id
        self.email = email
        self.name = name
        self.created_at = created_at or datetime.utcnow().isoformat()
        self.last_login_at = last_login_at

    @classmethod
    def create(cls, anthropic_user_id: str, email: Optional[str] = None,
               name: Optional[str] = None) -> "User":
        """Create a new user."""
        user = cls(
            id=str(uuid.uuid4()),
            anthropic_user_id=anthropic_user_id,
            email=email,
            name=name,
            created_at=datetime.utcnow().isoformat()
        )

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (id, anthropic_user_id, email, name, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (user.id, user.anthropic_user_id, user.email, user.name, user.created_at))
            conn.commit()

        return user

    @classmethod
    def get_by_anthropic_id(cls, anthropic_user_id: str) -> Optional["User"]:
        """Get user by Anthropic user ID."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE anthropic_user_id = ?", (anthropic_user_id,))
            row = cursor.fetchone()

            if row:
                return cls(**dict(row))
        return None

    @classmethod
    def get_by_id(cls, user_id: str) -> Optional["User"]:
        """Get user by ID."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()

            if row:
                return cls(**dict(row))
        return None

    def update_last_login(self):
        """Update user's last login timestamp."""
        self.last_login_at = datetime.utcnow().isoformat()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET last_login_at = ? WHERE id = ?",
                (self.last_login_at, self.id)
            )
            conn.commit()

    def to_dict(self) -> dict:
        """Convert user to dictionary."""
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "created_at": self.created_at
        }


class Conversation:
    """Conversation model for chat sessions."""

    def __init__(self, id: str, user_id: str, title: Optional[str] = None,
                 created_at: Optional[str] = None, updated_at: Optional[str] = None):
        self.id = id
        self.user_id = user_id
        self.title = title
        self.created_at = created_at or datetime.utcnow().isoformat()
        self.updated_at = updated_at or self.created_at

    @classmethod
    def create(cls, user_id: str, title: Optional[str] = None) -> "Conversation":
        """Create a new conversation."""
        now = datetime.utcnow().isoformat()
        conversation = cls(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=title or "New Conversation",
            created_at=now,
            updated_at=now
        )

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO conversations (id, user_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (conversation.id, conversation.user_id, conversation.title,
                  conversation.created_at, conversation.updated_at))
            conn.commit()

        return conversation

    @classmethod
    def get_by_id(cls, conversation_id: str) -> Optional["Conversation"]:
        """Get conversation by ID."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,))
            row = cursor.fetchone()

            if row:
                return cls(**dict(row))
        return None

    @classmethod
    def get_by_user(cls, user_id: str, limit: int = 50) -> list["Conversation"]:
        """Get all conversations for a user, ordered by most recent."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM conversations
                WHERE user_id = ?
                ORDER BY updated_at DESC
                LIMIT ?
            """, (user_id, limit))
            rows = cursor.fetchall()

            return [cls(**dict(row)) for row in rows]

    def update_title(self, title: str):
        """Update conversation title."""
        self.title = title
        self.updated_at = datetime.utcnow().isoformat()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                (self.title, self.updated_at, self.id)
            )
            conn.commit()

    def touch(self):
        """Update the conversation's updated_at timestamp."""
        self.updated_at = datetime.utcnow().isoformat()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (self.updated_at, self.id)
            )
            conn.commit()

    def delete(self):
        """Delete the conversation and all its messages."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (self.id,))
            cursor.execute("DELETE FROM conversations WHERE id = ?", (self.id,))
            conn.commit()

    def get_messages(self) -> list["Message"]:
        """Get all messages in this conversation."""
        return Message.get_by_conversation(self.id)

    def to_dict(self, include_messages: bool = False) -> dict:
        """Convert conversation to dictionary."""
        result = {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

        if include_messages:
            result["messages"] = [msg.to_dict() for msg in self.get_messages()]

        return result


class Message:
    """Message model for individual chat messages."""

    def __init__(self, id: str, conversation_id: str, role: str, content: str,
                 created_at: Optional[str] = None):
        self.id = id
        self.conversation_id = conversation_id
        self.role = role  # 'user' or 'assistant'
        self.content = content
        self.created_at = created_at or datetime.utcnow().isoformat()

    @classmethod
    def create(cls, conversation_id: str, role: str, content: str) -> "Message":
        """Create a new message."""
        message = cls(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role=role,
            content=content,
            created_at=datetime.utcnow().isoformat()
        )

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO messages (id, conversation_id, role, content, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (message.id, message.conversation_id, message.role,
                  message.content, message.created_at))
            conn.commit()

        # Touch the conversation to update its updated_at
        conversation = Conversation.get_by_id(conversation_id)
        if conversation:
            conversation.touch()

        return message

    @classmethod
    def get_by_conversation(cls, conversation_id: str) -> list["Message"]:
        """Get all messages in a conversation, ordered by creation time."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC
            """, (conversation_id,))
            rows = cursor.fetchall()

            return [cls(**dict(row)) for row in rows]

    def to_dict(self) -> dict:
        """Convert message to dictionary."""
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at
        }
