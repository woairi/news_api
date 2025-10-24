# AI News Bot 🤖

AI 뉴스 수집 및 한국어 요약 시스템 - 매일 AI 관련 뉴스를 자동 수집하여 한국어 요약을 생성하고 이메일과 텔레그램으로 배포하는 자동화 봇입니다.

## 🌟 주요 기능

- **자동 뉴스 수집**: NewsAPI를 통해 최신 AI 관련 뉴스 48시간 분량 수집
- **AI 요약 생성**: Google Gemini API를 사용한 한국어 요약 자동 생성
- **멀티 채널 배포**: 이메일(SMTP) + 텔레그램 동시 발송
- **웹 인터페이스**: 과거 요약 조회 및 관리자 기능 제공
- **수동 전송**: 웹 UI에서 즉시 텔레그램 메시지 전송 가능
- **스케줄링**: Docker + Cron을 통한 매일 자동 실행 (오전 7:35 KST)

## 🏗️ 시스템 아키텍처

```
┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐
│   NewsAPI       │───▶│  AI News Bot │───▶│   배포 채널      │
│   (뉴스 수집)    │    │              │    │  • 이메일       │
└─────────────────┘    │              │    │  • 텔레그램     │
                       │              │    └─────────────────┘
┌─────────────────┐    │              │    ┌─────────────────┐
│ Google Gemini   │───▶│              │───▶│   SQLite DB     │
│ (한국어 요약)    │    │              │    │  (요약 저장)     │
└─────────────────┘    └──────────────┘    └─────────────────┘
                              │
                       ┌──────────────┐
                       │ 웹 인터페이스   │
                       │ (FastAPI)    │
                       └──────────────┘
```

## 🚀 빠른 시작

### 1. 필요한 환경변수 설정

`.env` 파일을 생성하고 다음 내용을 입력하세요:

```env
# API 키
NEWS_API_KEY=your_newsapi_key
GEMINI_API_KEY=your_gemini_key

# 텔레그램 봇
TG_TOKEN=your_telegram_bot_token
TG_CHAT=your_telegram_chat_id

# 이메일 설정 (SMTP)
SMTP_HOST=your_smtp_server
SMTP_PORT=587
SMTP_USER=your_email_username
SMTP_PASS=your_email_password
EMAIL_TO=recipient_email_address

# 스케줄링 & 관리
CRON_TIME=35 7  # 크론 실행 시간 (분 시간) - 현재: 매일 오전 7시 35분 KST
ADMIN_PASSWORD=your_admin_password  # 웹 관리자 페이지 접근용 (기본값: admin123)
```

### 2. Docker로 실행

```bash
# 서비스 빌드 및 시작
docker compose up --build -d

# 로그 확인
docker compose logs -f

# 서비스 중지
docker compose down
```

### 3. 웹 인터페이스 접속

- 메인 페이지: http://localhost:8001/
- 관리자 로그인: http://localhost:8001/admin/login
- 관리자 설정: http://localhost:8001/admin/settings

## 🎯 사용 방법

### 자동 실행
- 매일 오전 7:35 (KST)에 크론으로 자동 실행
- 뉴스 수집 → 요약 생성 → 이메일/텔레그램 발송 → DB 저장

### 수동 실행

#### 명령어로 실행
```bash
# 컨테이너 내부에서 직접 실행
docker exec ai-news-bot python3 /app/send_ai_news.py

# 로컬에서 실행 (개발 시)
python send_ai_news.py
```

#### 웹 인터페이스에서 실행
1. 관리자 페이지 접속 (http://localhost:8001/admin/settings)
2. 관리자 비밀번호로 로그인
3. "📱 텔레그램 전송" 버튼 클릭

### 웹 인터페이스 기능
- **메인 페이지**: 최근 요약 조회 및 날짜별 검색
- **관리자 페이지**: 환경변수 확인 및 수동 전송 기능
- **API 엔드포인트**: 
  - `/api/dates` - 요약 가능한 날짜 목록
  - `/api/summary/{date}` - 특정 날짜 요약 조회
  - `/api/today` - 오늘 요약 조회

## 🛠️ 개발 환경 설정

### 로컬 개발

```bash
# 의존성 설치
pip install -r requirements.txt

# 웹 개발 서버 시작
uvicorn web_app:app --host 0.0.0.0 --port 8001 --reload

# 뉴스 봇 단독 실행
python send_ai_news.py
```

### Docker 개발

```bash
# 개발 모드로 시작 (볼륨 마운트)
docker compose up --build

# 컨테이너 내부 접속
docker exec -it ai-news-bot bash

# 크론 로그 실시간 모니터링
docker exec ai-news-bot tail -f /var/log/cron.log
```

## 📁 프로젝트 구조

```
ai-news-bot/
├── 📄 send_ai_news.py      # 메인 봇 로직 (뉴스 수집, 요약, 배포)
├── 📄 web_app.py           # FastAPI 웹 인터페이스
├── 📄 requirements.txt     # Python 의존성
├── 📄 Dockerfile          # Docker 이미지 정의
├── 📄 docker-compose.yml  # Docker 서비스 구성
├── 📄 .env                # 환경변수 설정
├── 📁 data/               # SQLite 데이터베이스 저장
│   └── news_summaries.db
├── 📁 logs/               # 크론 로그 저장
└── 📄 CLAUDE.md           # AI 어시스턴트용 개발 가이드
```

## 🗄️ 데이터베이스 스키마

SQLite 데이터베이스 (`data/news_summaries.db`):

```sql
CREATE TABLE summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,              -- 요약 날짜 (YYYY-MM-DD)
    summary TEXT NOT NULL,           -- 한국어 요약 내용
    articles_json TEXT NOT NULL,     -- 원본 뉴스 기사 JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 🔧 주요 기술 스택

| 구분 | 기술 | 용도 |
|------|------|------|
| **언어** | Python 3.11 | 메인 개발 언어 |
| **AI** | Google Gemini API | 한국어 요약 생성 |
| **뉴스** | NewsAPI | AI 뉴스 수집 |
| **웹** | FastAPI + Uvicorn | 웹 인터페이스 |
| **DB** | SQLite | 요약 데이터 저장 |
| **배포** | Docker + Docker Compose | 컨테이너화 |
| **스케줄링** | Cron | 정기 실행 |
| **알림** | Telegram Bot API + SMTP | 메시지 배포 |

## 📝 주요 의존성

```
google-genai>=0.4.0      # Google Gemini API 클라이언트
requests>=2.31.0         # HTTP 요청 처리
python-dotenv>=1.0.1     # 환경변수 관리
fastapi>=0.104.0         # 웹 프레임워크
uvicorn>=0.24.0          # ASGI 서버
python-multipart>=0.0.6  # 폼 데이터 처리
```

## 🔍 트러블슈팅

### 크론이 실행되지 않는 경우

```bash
# 환경변수 확인
docker exec ai-news-bot cat /app/.env.clean

# 환경변수 파일 재생성 (필요시)
docker exec ai-news-bot bash -c "cd /app && cat .env | grep -v '^#' | grep -v '^$' | sed 's/#.*//' | sed 's/[[:space:]]*$//' > .env.clean"

# 크론 설정 확인
docker exec ai-news-bot crontab -l

# 크론 로그 확인
docker exec ai-news-bot cat /var/log/cron.log
```

### 환경변수 문제

- `.env` 파일에 trailing space가 없는지 확인
- 주석이 변수 파싱을 방해하지 않는지 확인
- 모든 필수 변수가 설정되었는지 assertion 에러 메시지로 확인

### 웹 인터페이스 접속 불가

```bash
# 컨테이너 상태 확인
docker compose ps

# 포트 바인딩 확인
docker compose logs ai-news-bot

# 웹 서버 직접 실행 (디버깅)
uvicorn web_app:app --host 0.0.0.0 --port 8001 --reload
```

## 🤝 기여하기

1. 이 저장소를 포크하세요
2. 기능 브랜치를 생성하세요 (`git checkout -b feature/amazing-feature`)
3. 변경사항을 커밋하세요 (`git commit -m 'Add amazing feature'`)
4. 브랜치에 푸시하세요 (`git push origin feature/amazing-feature`)
5. Pull Request를 생성하세요

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 `LICENSE` 파일을 참조하세요.

## 📞 지원

문제가 발생했거나 질문이 있으시면 이슈를 생성해 주세요.

---

**🌐 웹사이트**: https://news.hyung.life/  
**📱 실시간 AI 뉴스 요약을 확인하세요!**