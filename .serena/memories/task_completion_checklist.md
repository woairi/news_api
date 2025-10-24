# AI News Bot - Task Completion Checklist

## 코드 변경 후 확인사항

### 1. 기본 테스트
```bash
# 메인 스크립트 실행 테스트
python send_ai_news.py

# 웹앱 실행 테스트
python web_app.py
```

### 2. Docker 테스트
```bash
# 컨테이너 빌드 및 실행 확인
docker compose up --build -d

# 서비스 상태 확인
docker compose ps

# 로그 확인
docker compose logs
```

### 3. 환경변수 검증
```bash
# .env 파일 문법 확인 (공백, 주석 등)
cat .env | grep -v '^#' | grep -v '^$'

# 컨테이너 내부 환경변수 정리 확인
docker exec ai-news-bot cat /app/.env.clean
```

### 4. 크론 작업 검증
```bash
# 크론 설정 확인
docker exec ai-news-bot crontab -l

# 수동 실행으로 크론 작업 테스트
docker exec ai-news-bot python3 /app/send_ai_news.py
```

### 5. 웹 인터페이스 검증
```bash
# API 엔드포인트 테스트
curl http://localhost:8001/api/dates
curl http://localhost:8001/api/today

# 웹페이지 접속 확인
curl http://localhost:8001/
```

## 주의사항
- 환경변수 값에 후행 공백 없도록 주의
- .env 파일의 주석이 파싱에 영향주지 않도록 확인
- 데이터베이스 경로 `/app/data` 권한 확인
- 타임존이 Asia/Seoul로 설정되어 있는지 확인

## 문제 해결
- 크론 실행 안될 때: 환경변수 로딩 문제 확인
- 웹앱 접속 안될 때: 포트 8001 바인딩 확인
- DB 오류시: `/app/data` 디렉토리 권한 및 존재 여부 확인