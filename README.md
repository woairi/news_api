# AI News Bot 🤖

AI 뉴스 수집 및 한국어 요약 시스템 - 매일 AI 관련 뉴스를 자동 수집하여 한국어 요약을 생성하고 이메일과 텔레그램으로 배포하는 자동화 봇입니다.

## 🌟 주요 기능

- **자동 뉴스 수집**: NewsAPI를 통해 최신 AI 관련 뉴스 48시간 분량 수집
- **데이터센터 특화 요약**: DatacenterDynamics 주요 채널(에너지·투자·클라우드)에서 전일 기사 수집·요약, 웹/메신저 동시 제공
- **AI 요약 생성**: Google Gemini API를 사용한 한국어 요약 자동 생성
- **멀티 채널 배포**: 이메일(SMTP) + 텔레그램 동시 발송
- **웹 인터페이스**: AI/Datacenter 탭, 전일 대비 Datacenter 안내, KST 기준 상태 패널, 2열 요약·날짜 레이아웃 등으로 가독성 향상
- **수동 전송**: 웹 UI에서 즉시 텔레그램 메시지 전송 가능
- **스케줄링**: Docker + Cron을 통한 매일 자동 실행 (오전 7:35 KST)

## 🚀 빠른 시작

### 1. 저장소 복제

```bash
git clone https://github.com/your-username/ai-news-bot.git
cd ai-news-bot
```

### 2. 필요한 환경변수 설정

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

### 3. 의존성 설치

```bash
pip install -r requirements.txt
```

### 4. Docker로 실행

```bash
# 서비스 빌드 및 시작
docker compose up --build -d

# 로그 확인
docker compose logs -f

# 서비스 중지
docker compose down
```

### 5. 웹 인터페이스 접속

- 메인 페이지: http://localhost:8001/
- 관리자 로그인: http://localhost:8001/admin/login
- 관리자 설정: http://localhost:8001/admin/settings

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

## 📝 변경 사항

자세한 변경 내역은 [CHANGELOG.md](CHANGELOG.md) 파일을 참고하세요.

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
