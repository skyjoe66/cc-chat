# Claude Code Chat

A web frontend for chatting with Claude via the [Claude Code CLI](https://github.com/anthropics/claude-code) with authentication and persistent conversations.

![Claude Code Chat](https://img.shields.io/badge/Claude-Code%20Chat-e94560)
![Python](https://img.shields.io/badge/Python-3.8+-blue)
![Flask](https://img.shields.io/badge/Flask-3.0+-green)

## Features

- **Authentication** - Login with your Anthropic API key or OAuth token
- **Persistent Conversations** - Chat history saved to SQLite database
- **Conversation Management** - Create, switch between, and delete conversations
- **Clean, modern chat interface** with sidebar navigation
- **Markdown rendering** in responses (code blocks, lists, links, etc.)
- **Mobile-responsive design** with collapsible sidebar
- **Dark theme** by default
- **In-memory sessions** - Fast session management (sessions cleared on restart)

## Prerequisites

Before you begin, ensure you have the following installed:

1. **Python 3.8 or higher**
   ```bash
   python --version
   ```

2. **Claude Code CLI** - This app requires the Claude Code CLI to be installed.

   Install Claude Code:
   ```bash
   npm install -g @anthropics/claude-code
   ```

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/cc-chat.git
cd cc-chat
```

### 2. Create a Virtual Environment (Recommended)

```bash
# Create virtual environment
python -m venv venv

# Activate it
# On Linux/macOS:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment (Optional)

Copy the example environment file and customize if needed:

```bash
cp .env.example .env
```

Edit `.env` to customize settings:

```bash
# Server settings
HOST=0.0.0.0
PORT=5007
DEBUG=false

# Claude settings
CLAUDE_TIMEOUT=120
SYSTEM_PROMPT=You are a helpful assistant. Be concise and clear.

# Security (optional - generates random key if not set)
SECRET_KEY=your-secret-key-here

# Session duration (hours)
SESSION_DURATION_HOURS=24
```

### 5. Run the Application

```bash
python app.py
```

The app will be available at: `http://localhost:5007`

## Authentication

When you first access the application, you'll be prompted to enter your Anthropic credentials:

### Using an API Key
1. Go to [Anthropic Console](https://console.anthropic.com/settings/keys)
2. Create a new API key
3. Enter the key (starts with `sk-ant-`) in the login form

### Using an OAuth Token
If you have an Anthropic OAuth token (from Claude Code CLI authentication), you can use that as well.

The application validates your token by making a minimal API request to Anthropic. Once authenticated, your session is stored in memory and persists for 24 hours (configurable).

## Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Host to bind the server to |
| `PORT` | `5007` | Port number for the server |
| `DEBUG` | `false` | Enable Flask debug mode |
| `CLAUDE_TIMEOUT` | `120` | Timeout in seconds for Claude responses |
| `SYSTEM_PROMPT` | `You are a helpful assistant...` | System prompt sent with each request |
| `SECRET_KEY` | (random) | Flask secret key for sessions |
| `SESSION_DURATION_HOURS` | `24` | How long sessions remain valid |

## Usage

1. Open your browser to `http://localhost:5007`
2. Enter your Anthropic API key or OAuth token
3. Start a new conversation or select an existing one from the sidebar
4. Type your message and press Enter or click Send
5. Your conversations are automatically saved

### Keyboard Shortcuts

- **Enter** - Send message
- **Shift+Enter** - New line in message

### Sidebar Features

- **New Chat** - Start a fresh conversation
- **Conversation List** - Click to switch between saved conversations
- **Sign Out** - Log out and clear your session

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/login` | Login with Anthropic token |
| `POST` | `/api/auth/logout` | Logout and invalidate session |
| `GET` | `/api/auth/verify` | Verify current session |
| `GET` | `/api/auth/me` | Get current user info |

### Conversations

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/conversations` | List all conversations |
| `POST` | `/api/conversations` | Create a new conversation |
| `GET` | `/api/conversations/:id` | Get conversation with messages |
| `PATCH` | `/api/conversations/:id` | Update conversation (rename) |
| `DELETE` | `/api/conversations/:id` | Delete a conversation |

### Chat

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/chat` | Send a message (creates conversation if needed) |

## Project Structure

```
cc-chat/
├── app.py                 # Flask application with all routes
├── models.py              # SQLite database models (User, Conversation, Message)
├── auth.py                # Authentication and session management
├── requirements.txt       # Python dependencies
├── .env.example          # Example environment configuration
├── .gitignore            # Git ignore file
├── README.md             # This file
├── claude_chat.db        # SQLite database (created on first run)
├── templates/
│   └── index.html        # Main HTML template
└── static/
    ├── css/
    │   └── style.css     # Styles
    └── js/
        └── app.js        # Frontend JavaScript
```

## Data Storage

- **Sessions** - Stored in memory (cleared on server restart)
- **Users** - Stored in SQLite (`claude_chat.db`)
- **Conversations** - Stored in SQLite (`claude_chat.db`)
- **Messages** - Stored in SQLite (`claude_chat.db`)

## Running in Production

For production deployments, consider:

1. **Use a production WSGI server** like Gunicorn:
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:5007 app:app
   ```

2. **Set a strong SECRET_KEY** in your `.env` file

3. **Use a reverse proxy** like Nginx

4. **Enable HTTPS** for secure communication

5. **Consider Redis** for session storage if you need persistence across restarts

### Example Nginx Configuration

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5007;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
    }
}
```

## Running with Docker (Optional)

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install Node.js for Claude Code CLI
RUN apt-get update && apt-get install -y nodejs npm && \
    npm install -g @anthropics/claude-code && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create volume for persistent database
VOLUME /app/data

EXPOSE 5007

CMD ["python", "app.py"]
```

Build and run:

```bash
docker build -t cc-chat .
docker run -p 5007:5007 -v cc-chat-data:/app/data cc-chat
```

## Troubleshooting

### "Invalid token" on login

1. Make sure you're using a valid Anthropic API key (starts with `sk-ant-`)
2. Check that your API key has not been revoked
3. Ensure you have API access on your Anthropic account

### "Claude Code CLI not found"

Ensure Claude Code is installed globally:
```bash
npm install -g @anthropics/claude-code
```

And that your PATH includes npm global binaries:
```bash
# Check if claude is in PATH
which claude
```

### "Request timed out"

Increase the timeout in your `.env`:
```bash
CLAUDE_TIMEOUT=180
```

### Session expired

Sessions are stored in memory and will be lost when the server restarts. Simply log in again with your API key.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - feel free to use this project for any purpose.

## Acknowledgments

- Powered by [Claude Code CLI](https://github.com/anthropics/claude-code)
- Built with [Flask](https://flask.palletsprojects.com/)
