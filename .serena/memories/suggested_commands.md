# AI News Bot - Suggested Commands

## 개발 및 테스트 명령어

### 로컬 개발
```bash
# 의존성 설치
pip install -r requirements.txt

# 메인 봇 직접 실행 (테스트용)
python send_ai_news.py

# 웹 인터페이스만 실행 (개발용)
python web_app.py
# 또는 FastAPI 개발서버로
uvicorn web_app:app --host 0.0.0.0 --port 8001 --reload
```

### Docker 운영
```bash
# 빌드 및 실행 (프로덕션)
docker compose up --build -d

# 로그 확인
docker compose logs -f

# 서비스 중지
docker compose down

# 컨테이너 내부 크론 로그 확인
docker exec ai-news-bot cat /var/log/cron.log

# 크론 설정 확인
docker exec ai-news-bot crontab -l

# 수동 실행 (테스트)
docker exec ai-news-bot python3 /app/send_ai_news.py
```

### 웹 인터페이스 테스트
```bash
# API 엔드포인트 테스트
curl http://localhost:8001/
curl http://localhost:8001/api/dates
curl http://localhost:8001/api/summary/2024-01-01
```

### 시스템 유틸리티 (Linux)
```bash
# 기본 파일 시스템 명령어
ls -la          # 파일 목록
cd directory    # 디렉토리 이동
grep pattern    # 텍스트 검색
find . -name    # 파일 검색
tail -f logs/   # 로그 모니터링

# Git 버전 관리
git status      # 상태 확인
git add .       # 변경사항 스테이징
git commit -m   # 커밋
git push        # 원격 저장소 푸시
```