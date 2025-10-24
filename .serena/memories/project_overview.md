# AI News Bot - Project Overview

## Purpose
AI 뉴스 수집 및 한국어 요약 시스템으로, 매일 AI 관련 뉴스를 자동 수집하여 Gemini API로 한국어 요약 생성 후 이메일과 텔레그램으로 배포하는 시스템

## Tech Stack
- **Python 3.11** - 메인 언어
- **Google Gemini API** - AI 요약 생성 
- **NewsAPI** - 뉴스 수집
- **SQLite** - 요약 저장용 데이터베이스
- **FastAPI** - 웹 인터페이스
- **Docker** - 컨테이너 배포
- **Cron** - 스케줄링

## Core Components
1. **send_ai_news.py** - 메인 봇 로직 (뉴스 수집, 요약, 배포)
2. **web_app.py** - FastAPI 기반 웹 인터페이스
3. **Docker** - 크론과 웹서비스 통합 컨테이너

## Architecture
- 단일 컨테이너에서 웹서비스와 크론 동시 실행
- 매일 07:35 KST에 자동 실행
- SQLite DB에 요약 저장하여 웹에서 조회 가능
- 이메일(SMTP) + 텔레그램 이중 배포