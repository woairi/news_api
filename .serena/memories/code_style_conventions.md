# AI News Bot - Code Style & Conventions

## Python Code Style
- **Python 3.11** 기준 코드 작성
- **snake_case** 변수명과 함수명 사용
- **UPPER_CASE** 상수 및 환경변수 사용
- **타입 힌트** 없음 (현재 코드베이스 기준)
- **Docstring** 없음 (간단한 스크립트 구조)

## 파일 구조 패턴
```
send_ai_news.py     # 메인 로직 - 단일 파일에 모든 기능
web_app.py          # FastAPI 앱 - 단일 파일 구조
requirements.txt    # 의존성 관리
.env               # 환경변수
docker-compose.yml # 컨테이너 설정
Dockerfile         # 이미지 빌드 설정
```

## 환경변수 네이밍
```
NEWS_API_KEY    # API 키들
GEMINI_API_KEY
TG_TOKEN        # 텔레그램 봇 토큰
TG_CHAT         # 텔레그램 채팅 ID
SMTP_*          # 이메일 설정들
CRON_TIME       # 크론 실행 시간
ADMIN_PASSWORD  # 웹 관리자 비밀번호
```

## 데이터베이스 패턴
- **SQLite** 사용
- `data/news_summaries.db` 경로
- 단일 테이블 구조 (`summaries`)
- 날짜별 요약 저장

## API 응답 패턴
- FastAPI 기본 구조 사용
- JSON 응답 형태
- Pydantic 모델 사용 (`SummaryResponse`)
- RESTful 엔드포인트 설계