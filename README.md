# AI 뉴스 요약 & 텔레그램 자동 전송 서비스

## ✅ 구성
- FastAPI 웹 서비스 (뉴스 요약 열람)
- 매일 AI 뉴스 요약 및 텔레그램 전송 (Perplexity API 사용)
- `.env`로 키 관리 및 뉴스 키워드/시간 설정
- Docker로 배포 및 자동 실행

## ✅ 실행 방법
### 1. Docker 이미지 빌드 및 실행
```bash
docker-compose up -d --build
