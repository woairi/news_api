# AI News Bot - Dependencies & APIs

## Python Dependencies
```
google-genai>=0.4.0      # Google Gemini API 클라이언트 (OpenAI 대체)
requests>=2.31.0         # HTTP 요청 (NewsAPI, Telegram)
python-dotenv>=1.0.1     # 환경변수 관리
fastapi>=0.104.0         # 웹 프레임워크
uvicorn>=0.24.0          # ASGI 서버
python-multipart>=0.0.6  # 폼 데이터 처리
```

## 외부 API 연동
### NewsAPI
- 뉴스 데이터 수집
- 지난 48시간 AI 관련 뉴스 검색
- API 키: `NEWS_API_KEY`

### Google Gemini API
- 한국어 요약 생성
- OpenAI에서 Gemini로 변경됨
- API 키: `GEMINI_API_KEY`

### Telegram Bot API
- 요약 메시지 배포
- 토큰: `TG_TOKEN`
- 채팅 ID: `TG_CHAT`

### SMTP 이메일
- 요약 이메일 발송
- 설정: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`
- 수신자: `EMAIL_TO`

## 데이터베이스
- **SQLite** (`data/news_summaries.db`)
- 테이블: `summaries`
- 스키마:
  ```sql
  CREATE TABLE summaries (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      date TEXT NOT NULL,
      summary TEXT NOT NULL,
      articles_json TEXT NOT NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  )
  ```