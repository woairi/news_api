# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

### Running the AI News Bot
```bash
# Direct Python execution (for testing)
python send_ai_news.py

# Using Docker (production)
docker-compose up --build

# Web interface only (development)
python web_app.py
```

### Docker Operations
```bash
# Build and start services (use 'docker compose' not 'docker-compose')
docker compose up --build -d

# View logs (includes cron and web logs)
docker compose logs -f

# Stop services
docker compose down

# Check cron execution logs
docker exec ai-news-bot cat /var/log/cron.log

# Check current cron configuration
docker exec ai-news-bot crontab -l

# Manual script execution for testing
docker exec ai-news-bot python3 /app/send_ai_news.py
```

### Web Interface Testing
```bash
# Start FastAPI development server
uvicorn web_app:app --host 0.0.0.0 --port 8001 --reload

# Access web interface
curl http://localhost:8001/
curl http://localhost:8001/api/dates
curl http://localhost:8001/api/summary/2024-01-01
```

### Troubleshooting Common Issues

#### Cron Not Executing
If the daily cron job fails to run:
```bash
# Check if environment variables are properly loaded in cron
docker exec ai-news-bot cat /app/.env.clean

# If .env.clean is empty, regenerate it
docker exec ai-news-bot bash -c "cd /app && cat .env | grep -v '^#' | grep -v '^$' | sed 's/#.*//' | sed 's/[[:space:]]*$//' > .env.clean"

# Update cron configuration with proper environment loading
docker exec ai-news-bot bash -c "echo '35 7 * * * cd /app && export \$(cat /app/.env.clean | xargs) && /usr/local/bin/python3 /app/send_ai_news.py >> /var/log/cron.log 2>&1' > /etc/cron.d/news-cron"
docker exec ai-news-bot chmod 0644 /etc/cron.d/news-cron
docker exec ai-news-bot crontab /etc/cron.d/news-cron
```

#### Environment Variable Issues
- Ensure `.env` file doesn't have trailing spaces in values
- Comments in `.env` file should not interfere with variable parsing
- Check that all required variables are set using assertion error messages

### Dependencies
```bash
# Install Python dependencies
pip install -r requirements.txt
```

## Architecture Overview

This is a dual-component AI news aggregation system:

1. **News Collection & Summarization**: `send_ai_news.py` fetches AI news and generates Korean summaries
2. **Web Interface**: `web_app.py` provides a FastAPI-based web UI for viewing historical summaries
3. **Containerized Deployment**: Docker setup with cron scheduling and persistent data storage

### Core Components

**`send_ai_news.py`** (Main Bot Logic):
- Fetches AI-related news from NewsAPI (last 48 hours)
- Uses Google Gemini API for Korean summarization
- Distributes via email (SMTP) and Telegram
- Stores summaries in SQLite database
- Runs on cron schedule (current: 7:35 AM KST)

**`web_app.py`** (Web Interface):
- FastAPI application with HTML frontend
- Displays historical news summaries by date
- Admin settings page for environment variable viewing
- SQLite database integration for persistent storage
- Responsive design with date picker and recent summaries

**Docker Architecture**:
- Single container running both web service and cron
- Persistent volumes for logs (`./logs`) and database (`./data`)
- Timezone set to Asia/Seoul
- Port 8001 exposed for web interface

### Database Schema
SQLite database (`data/news_summaries.db`):
```sql
CREATE TABLE summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    summary TEXT NOT NULL,
    articles_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

### Required Environment Variables
```
# News & AI APIs
NEWS_API_KEY=your_newsapi_key
GEMINI_API_KEY=your_gemini_key

# Telegram Bot
TG_TOKEN=your_telegram_bot_token
TG_CHAT=your_telegram_chat_id

# Email (SMTP)
SMTP_HOST=your_smtp_server
SMTP_PORT=587
SMTP_USER=your_email_username
SMTP_PASS=your_email_password
EMAIL_TO=recipient_email_address

# Scheduling & Admin
CRON_TIME=35 7  # 크론 실행 시간 (분 시간) - 현재 설정: 매일 오전 7시 35분 KST
ADMIN_PASSWORD=your_admin_password  # 웹 관리자 페이지 접근용 (기본값: admin123)
```

### Key Dependencies
- `google-genai>=0.4.0` - Google Gemini API client (replaced OpenAI)
- `requests>=2.31.0` - HTTP requests for NewsAPI and Telegram
- `python-dotenv>=1.0.1` - Environment variable management
- `fastapi>=0.104.0` - Web framework for admin interface
- `uvicorn>=0.24.0` - ASGI server
- `python-multipart>=0.0.6` - Form data handling

### Web Interface Access
- Main page: `http://localhost:8001/`
- Admin login: `http://localhost:8001/admin/login`
- Admin settings: `http://localhost:8001/admin/settings`
- API endpoints: `/api/dates`, `/api/summary/{date}`, `/api/today`

The system is designed for automated daily news digest delivery with a web interface for historical viewing and system administration.