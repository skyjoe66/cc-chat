// Claude Code Chat - Frontend Application with Authentication

const state = {
    user: null,
    sessionToken: null,
    conversations: [],
    currentConversationId: null,
    chatHistory: [],
    isLoading: false,
    sidebarOpen: window.innerWidth > 768,
};

// DOM Elements - Login
const loginScreen = document.getElementById('login-screen');
const loginForm = document.getElementById('login-form');
const tokenInput = document.getElementById('token-input');
const loginBtn = document.getElementById('login-btn');
const loginError = document.getElementById('login-error');

// DOM Elements - Main App
const mainApp = document.getElementById('main-app');
const sidebar = document.getElementById('sidebar');
const conversationList = document.getElementById('conversation-list');
const newChatBtn = document.getElementById('new-chat-btn');
const logoutBtn = document.getElementById('logout-btn');
const toggleSidebarBtn = document.getElementById('toggle-sidebar');
const deleteChatBtn = document.getElementById('delete-chat');

// DOM Elements - Chat
const chatMessages = document.getElementById('chat-messages');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');

// Thinking phrases for loading state
const thinkingPhrases = [
    'Thinking...',
    'Pondering...',
    'Contemplating...',
    'Processing...',
    'Analyzing...',
    'Considering...',
    'Formulating...',
    'Computing...',
    'Reasoning...',
    'Reflecting...',
];

function getRandomThinkingPhrase() {
    return thinkingPhrases[Math.floor(Math.random() * thinkingPhrases.length)];
}

// ============================================================================
// API Helpers
// ============================================================================

async function apiRequest(url, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers,
    };

    if (state.sessionToken) {
        headers['Authorization'] = `Bearer ${state.sessionToken}`;
    }

    const response = await fetch(url, {
        ...options,
        headers,
    });

    return response.json();
}

// ============================================================================
// Authentication
// ============================================================================

async function checkAuthStatus() {
    try {
        const data = await apiRequest('/api/auth/me');
        if (data.authenticated) {
            state.user = data.user;
            // Try to get session token from localStorage
            state.sessionToken = localStorage.getItem('session_token');
            showMainApp();
            await loadConversations();
        } else {
            showLoginScreen();
        }
    } catch {
        showLoginScreen();
    }
}

async function login(token) {
    setLoginLoading(true);
    loginError.textContent = '';

    try {
        const data = await apiRequest('/api/auth/login', {
            method: 'POST',
            body: JSON.stringify({ token }),
        });

        if (data.success) {
            state.user = data.user;
            state.sessionToken = data.session_token;
            localStorage.setItem('session_token', data.session_token);
            showMainApp();
            await loadConversations();
        } else {
            loginError.textContent = data.error || 'Login failed';
        }
    } catch (error) {
        loginError.textContent = 'Connection error. Please try again.';
    } finally {
        setLoginLoading(false);
    }
}

async function logout() {
    try {
        await apiRequest('/api/auth/logout', { method: 'POST' });
    } catch {
        // Ignore errors during logout
    }

    state.user = null;
    state.sessionToken = null;
    state.conversations = [];
    state.currentConversationId = null;
    state.chatHistory = [];
    localStorage.removeItem('session_token');
    showLoginScreen();
}

function setLoginLoading(loading) {
    loginBtn.disabled = loading;
    tokenInput.disabled = loading;
    loginBtn.querySelector('.btn-text').style.display = loading ? 'none' : 'inline';
    loginBtn.querySelector('.btn-loading').style.display = loading ? 'inline' : 'none';
}

function showLoginScreen() {
    loginScreen.style.display = 'flex';
    mainApp.style.display = 'none';
    tokenInput.value = '';
    loginError.textContent = '';
    tokenInput.focus();
}

function showMainApp() {
    loginScreen.style.display = 'none';
    mainApp.style.display = 'flex';
    chatInput.focus();
}

// ============================================================================
// Conversations
// ============================================================================

async function loadConversations() {
    try {
        const data = await apiRequest('/api/conversations');
        if (data.success) {
            state.conversations = data.conversations;
            renderConversationList();
        }
    } catch (error) {
        console.error('Failed to load conversations:', error);
    }
}

async function loadConversation(conversationId) {
    try {
        const data = await apiRequest(`/api/conversations/${conversationId}`);
        if (data.success) {
            state.currentConversationId = conversationId;
            state.chatHistory = data.conversation.messages || [];
            renderChatHistory();
            updateActiveConversation();
            deleteChatBtn.style.display = 'flex';

            // Close sidebar on mobile after selecting
            if (window.innerWidth <= 768) {
                toggleSidebar(false);
            }
        }
    } catch (error) {
        console.error('Failed to load conversation:', error);
    }
}

async function deleteConversation(conversationId) {
    if (!confirm('Are you sure you want to delete this conversation?')) {
        return;
    }

    try {
        const data = await apiRequest(`/api/conversations/${conversationId}`, {
            method: 'DELETE',
        });

        if (data.success) {
            if (state.currentConversationId === conversationId) {
                startNewConversation();
            }
            await loadConversations();
        }
    } catch (error) {
        console.error('Failed to delete conversation:', error);
    }
}

function startNewConversation() {
    state.currentConversationId = null;
    state.chatHistory = [];
    deleteChatBtn.style.display = 'none';
    updateActiveConversation();
    showWelcomeMessage();
    chatInput.focus();

    // Close sidebar on mobile
    if (window.innerWidth <= 768) {
        toggleSidebar(false);
    }
}

function renderConversationList() {
    if (state.conversations.length === 0) {
        conversationList.innerHTML = `
            <div class="conversation-empty">
                <p>No conversations yet</p>
                <p>Start chatting to create one!</p>
            </div>
        `;
        return;
    }

    conversationList.innerHTML = state.conversations.map(conv => {
        const date = new Date(conv.updated_at);
        const dateStr = formatDate(date);
        const isActive = conv.id === state.currentConversationId;

        return `
            <div class="conversation-item${isActive ? ' active' : ''}" data-id="${conv.id}">
                <span class="title">${escapeHtml(conv.title)}</span>
                <span class="date">${dateStr}</span>
            </div>
        `;
    }).join('');

    // Add click handlers
    conversationList.querySelectorAll('.conversation-item').forEach(item => {
        item.addEventListener('click', () => {
            const id = item.dataset.id;
            loadConversation(id);
        });
    });
}

function updateActiveConversation() {
    conversationList.querySelectorAll('.conversation-item').forEach(item => {
        if (item.dataset.id === state.currentConversationId) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });
}

function formatDate(date) {
    const now = new Date();
    const diff = now - date;
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (days === 0) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } else if (days === 1) {
        return 'Yesterday';
    } else if (days < 7) {
        return date.toLocaleDateString([], { weekday: 'short' });
    } else {
        return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    }
}

// ============================================================================
// Sidebar
// ============================================================================

function toggleSidebar(open) {
    if (typeof open === 'boolean') {
        state.sidebarOpen = open;
    } else {
        state.sidebarOpen = !state.sidebarOpen;
    }

    if (window.innerWidth <= 768) {
        if (state.sidebarOpen) {
            sidebar.classList.add('open');
        } else {
            sidebar.classList.remove('open');
        }
    } else {
        if (state.sidebarOpen) {
            sidebar.classList.remove('collapsed');
        } else {
            sidebar.classList.add('collapsed');
        }
    }
}

// ============================================================================
// Chat UI
// ============================================================================

function showWelcomeMessage() {
    chatMessages.innerHTML = `
        <div class="chat-welcome">
            <h2>Welcome to Claude Code Chat</h2>
            <p>Ask me anything! I'm powered by Claude Code CLI.</p>
            <ul>
                <li>Get help with coding questions</li>
                <li>Debug issues in your projects</li>
                <li>Learn new concepts and techniques</li>
                <li>Generate code snippets</li>
            </ul>
        </div>
    `;
}

function renderChatHistory() {
    if (state.chatHistory.length === 0) {
        showWelcomeMessage();
        return;
    }

    chatMessages.innerHTML = '';
    state.chatHistory.forEach(msg => {
        addMessage(msg.role, msg.content);
    });
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function formatMarkdown(text) {
    // Handle code blocks first (```)
    text = text.replace(/```(\w*)\n?([\s\S]*?)```/g, (match, lang, code) => {
        return `<pre><code class="language-${lang}">${escapeHtml(code.trim())}</code></pre>`;
    });

    // Handle inline code (`)
    text = text.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Handle bold (**)
    text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

    // Handle italic (*)
    text = text.replace(/\*([^*]+)\*/g, '<em>$1</em>');

    // Handle links [text](url)
    text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

    // Handle line breaks and paragraphs
    const paragraphs = text.split(/\n\n+/);
    text = paragraphs.map(p => {
        // Check if it's a code block (already wrapped in pre)
        if (p.startsWith('<pre>')) {
            return p;
        }
        // Check if it's a list
        if (p.match(/^[\s]*[-*]\s/m)) {
            const items = p.split(/\n/).map(line => {
                const match = line.match(/^[\s]*[-*]\s(.+)/);
                return match ? `<li>${match[1]}</li>` : line;
            }).join('');
            return `<ul>${items}</ul>`;
        }
        // Check if it's a numbered list
        if (p.match(/^[\s]*\d+\.\s/m)) {
            const items = p.split(/\n/).map(line => {
                const match = line.match(/^[\s]*\d+\.\s(.+)/);
                return match ? `<li>${match[1]}</li>` : line;
            }).join('');
            return `<ol>${items}</ol>`;
        }
        // Regular paragraph
        return `<p>${p.replace(/\n/g, '<br>')}</p>`;
    }).join('');

    return text;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function addMessage(role, content, isLoading = false) {
    const messageEl = document.createElement('div');
    messageEl.className = `chat-message ${role}${isLoading ? ' loading' : ''}`;

    if (role === 'assistant' && !isLoading) {
        messageEl.innerHTML = formatMarkdown(content);
    } else if (isLoading) {
        messageEl.innerHTML = `<em>${content}</em>`;
    } else {
        messageEl.textContent = content;
    }

    chatMessages.appendChild(messageEl);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    return messageEl;
}

async function sendMessage(message) {
    if (state.isLoading) return;

    state.isLoading = true;
    setInputState(false);

    // Add user message to UI
    addMessage('user', message);

    // Remove welcome message if it exists
    const welcome = chatMessages.querySelector('.chat-welcome');
    if (welcome) {
        welcome.remove();
    }

    // Add loading message
    const loadingEl = addMessage('assistant', getRandomThinkingPhrase(), true);

    try {
        const data = await apiRequest('/api/chat', {
            method: 'POST',
            body: JSON.stringify({
                message,
                conversation_id: state.currentConversationId,
            }),
        });

        if (data.success) {
            // Update loading message with response
            loadingEl.classList.remove('loading');
            loadingEl.innerHTML = formatMarkdown(data.response);

            // Update state
            state.chatHistory.push({ role: 'user', content: message });
            state.chatHistory.push({ role: 'assistant', content: data.response });

            // Update conversation ID if new
            if (data.conversation_id && data.conversation_id !== state.currentConversationId) {
                state.currentConversationId = data.conversation_id;
                deleteChatBtn.style.display = 'flex';
                await loadConversations();
            }
        } else {
            loadingEl.innerHTML = `<em>Error: ${data.error}</em>`;
        }
    } catch (error) {
        loadingEl.innerHTML = `<em>Error: ${error.message}</em>`;
    }

    state.isLoading = false;
    setInputState(true);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function setInputState(enabled) {
    chatInput.disabled = !enabled;
    sendBtn.disabled = !enabled;
    if (enabled) {
        chatInput.focus();
    }
}

function autoResize() {
    chatInput.style.height = 'auto';
    chatInput.style.height = Math.min(chatInput.scrollHeight, 200) + 'px';
}

// ============================================================================
// Event Listeners
// ============================================================================

// Login form
loginForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const token = tokenInput.value.trim();
    if (token) {
        login(token);
    }
});

// Logout
logoutBtn.addEventListener('click', logout);

// New chat
newChatBtn.addEventListener('click', startNewConversation);

// Toggle sidebar
toggleSidebarBtn.addEventListener('click', () => toggleSidebar());

// Delete conversation
deleteChatBtn.addEventListener('click', () => {
    if (state.currentConversationId) {
        deleteConversation(state.currentConversationId);
    }
});

// Chat form
chatForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const message = chatInput.value.trim();
    if (message && !state.isLoading) {
        chatInput.value = '';
        autoResize();
        sendMessage(message);
    }
});

chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        chatForm.dispatchEvent(new Event('submit'));
    }
});

chatInput.addEventListener('input', autoResize);

// Window resize handler
window.addEventListener('resize', () => {
    if (window.innerWidth > 768) {
        sidebar.classList.remove('open');
        if (state.sidebarOpen) {
            sidebar.classList.remove('collapsed');
        }
    }
});

// ============================================================================
// Initialize
// ============================================================================

// Check auth status on load
checkAuthStatus();
