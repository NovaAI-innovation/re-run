# Pydantic AI Telegram Bot

A modular Telegram bot that integrates with Google's Gemini LLM using Pydantic AI framework, featuring **persistent conversational awareness** for natural, context-aware conversations.

## Features

- 🤖 **AI-Powered Conversations**: Leverages Google's Gemini model through Pydantic AI
- 📱 **Telegram Integration**: Seamless Telegram bot interface with command support
- 💾 **Persistent Conversations**: Maintains conversation history and context across bot restarts
- 🧠 **Contextual Responses**: AI remembers previous messages for more natural conversations
- 📊 **Conversation Management**: Commands to view stats, clear history, and manage conversations
- 🗄️ **Flexible Storage**: Support for both JSON file storage and database storage (SQLite/PostgreSQL)
- ⚡ **Auto-Summarization**: Automatically creates conversation summaries for efficient context management
- ⚙️ **Configurable Settings**: Environment-based configuration with validation
- 🔒 **Robust Error Handling**: Comprehensive error handling and logging
- 🚀 **Modern Python**: Built with Python 3.11+ features and type hints

## Project Structure

```
├── src/
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py          # Configuration management with persistence settings
│   ├── bot/
│   │   ├── __init__.py
│   │   └── telegram_bot.py      # Telegram bot with conversation commands
│   ├── agent/
│   │   ├── __init__.py
│   │   └── ai_agent.py          # AI agent with conversation context integration
│   ├── persistence/             # NEW: Conversation persistence system
│   │   ├── __init__.py
│   │   ├── models.py           # Pydantic data models for conversations
│   │   ├── interface.py        # Abstract persistence interface
│   │   ├── json_storage.py     # JSON file storage implementation
│   │   ├── db_storage.py       # Database storage implementation
│   │   ├── database.py         # SQLAlchemy database models
│   │   ├── manager.py          # High-level conversation management
│   │   └── factory.py          # Storage factory for different backends
│   └── __init__.py
├── tests/
│   └── __init__.py
├── main.py                      # Application entry point
├── test_persistence.py          # Persistence tests
├── requirements.txt             # Dependencies (includes SQLAlchemy)
├── example.env                  # Environment variables template
└── README.md
```

## Setup

1. **Clone and install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Create environment file**:
   Copy `example.env` to `.env` and fill in your API keys:
   ```bash
   cp example.env .env
   ```

   Then edit the `.env` file with your actual credentials:
   ```env
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
   GOOGLE_API_KEY=your_google_api_key_here
   ```

3. **Run the bot**:
   ```bash
   python main.py
   ```

## Bot Commands

- `/start` - Initialize the bot and get a welcome message
- `/help` - Display available commands and usage instructions
- `/status` - Check the current status of the bot and AI agent
- `/clear` - Clear your conversation history and start fresh
- `/stats` - View your conversation statistics
- `/history` - Display recent conversation history

## Configuration

The bot uses environment variables for configuration. Copy `example.env` to `.env` and update the values:

### Required Environment Variables

- `TELEGRAM_BOT_TOKEN`: Your Telegram bot token from @BotFather
- `GOOGLE_API_KEY`: Your Google AI API key for Gemini model access

### Optional Environment Variables

**Core Settings:**
- `GEMINI_MODEL`: Gemini model to use (default: google-gla:gemini-1.5-flash)
- `SYSTEM_PROMPT`: Custom system prompt for the AI
- `MAX_RESPONSE_LENGTH`: Maximum length of AI responses (default: 4096)
- `LOG_LEVEL`: Logging level (default: INFO)
- `POLLING_INTERVAL`: Bot polling interval in seconds (default: 1)
- `MAX_REQUESTS_PER_MINUTE`: Rate limiting (default: 60)
- `REQUEST_TIMEOUT`: Request timeout in seconds (default: 30)

**Conversation Persistence:**
- `PERSISTENCE_ENABLED`: Enable/disable conversation persistence (default: true)
- `PERSISTENCE_TYPE`: Storage type - "json" or "database" (default: json)
- `JSON_STORAGE_DIR`: Directory for JSON storage (default: data/conversations)
- `DATABASE_URL`: Database URL for database storage (default: sqlite:///data/conversations.db)
- `MAX_CONVERSATIONS_PER_USER`: Max conversations to keep per user (default: 100)
- `CONTEXT_WINDOW_SIZE`: Number of messages to include in context (default: 10)
- `AUTO_SUMMARIZE_THRESHOLD`: Messages count to trigger auto-summarization (default: 50)
- `CLEANUP_OLD_DATA_DAYS`: Days to keep old conversation data (default: 30)

## Storage Options

### JSON Storage (Default)
- **Pros**: Simple, no database required, easy to inspect and backup
- **Cons**: Not suitable for high-concurrency scenarios
- **Best for**: Personal bots, development, small-scale deployments

### Database Storage
- **Pros**: Better performance, ACID compliance, suitable for production
- **Cons**: Requires database setup and management
- **Supported**: SQLite (simple), PostgreSQL (production)
- **Best for**: Production deployments, multiple users, high message volume

## Conversation Features

- **🧠 Context Awareness**: Bot remembers conversation history for more natural responses
- **📚 Auto-Summarization**: Long conversations are automatically summarized to maintain context efficiently  
- **👤 User Isolation**: Each user has their own conversation history
- **🔄 Session Persistence**: Conversations persist across bot restarts
- **📊 Statistics Tracking**: Track conversation metrics per user
- **🧹 History Management**: Users can clear their history or view recent messages

## Architecture

This project follows a clean architecture with separated concerns:

- **`main.py`**: Application entry point and orchestration
- **`src/config/`**: Configuration management with Pydantic
- **`src/agent/`**: AI agent implementation using Pydantic AI with conversation context
- **`src/bot/`**: Telegram bot implementation with conversation management commands
- **`src/persistence/`**: Complete conversation persistence system
  - **Abstract Interface**: Supports multiple storage backends
  - **JSON Storage**: File-based storage with caching and async operations
  - **Database Storage**: SQLAlchemy-based with PostgreSQL/SQLite support
  - **Conversation Manager**: High-level API for conversation operations
- **`tests/`**: Unit tests and test utilities

## Testing

Run the conversation persistence tests:

```bash
python test_persistence.py
```

Run all tests using pytest:

```bash
python -m pytest tests/ -v
```

## Usage Examples

1. **Start a conversation**: The bot remembers everything you discuss
2. **Natural follow-ups**: Ask "What did we talk about?" and the bot will remember
3. **Check your stats**: Use `/stats` to see your conversation metrics
4. **Clear history**: Use `/clear` to start fresh when needed
5. **View recent history**: Use `/history` to see your recent messages

## Development

### Best Practices Implemented

- **Modular Design**: Clean separation of concerns with dedicated persistence layer
- **Type Safety**: Full type hints using Pydantic models throughout
- **Error Handling**: Comprehensive exception handling with logging
- **Configuration Validation**: Pydantic-based configuration validation
- **Database Best Practices**: SQLAlchemy with proper session management and context managers
- **Async Support**: Full async/await support for better performance
- **Context7 Integration**: Used Context7 for SQLAlchemy and Pydantic best practices
- **Graceful Shutdown**: Proper cleanup on termination signals
- **Documentation**: Comprehensive inline documentation and docstrings

### Code Quality
```bash
# Format code
black src/ tests/

# Lint code
flake8 src/ tests/

# Type checking
mypy src/
```

## License

This project is open source and available under the MIT License.

---

**Note**: This implementation provides a complete, production-ready conversation persistence system that maintains context across bot restarts, enables natural conversational flow, and supports both simple JSON storage and robust database backends.