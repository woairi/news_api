#!/usr/bin/env python3
"""AI 뉴스 요약 웹 서비스"""
import os
import sqlite3
import datetime as dt
from typing import List, Dict, Optional
from fastapi import FastAPI, HTTPException, Form, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
import hashlib
import json
from dotenv import load_dotenv
import sys
sys.path.append('.')
try:
    from send_ai_news import (
        run_news_bot,
        ensure_summary_table,
        CATEGORY_AI_NEWS,
        CATEGORY_DATACENTER,
    )
except ImportError:
    print("Warning: send_ai_news module not found, manual send feature disabled")
    run_news_bot = None
    ensure_summary_table = None
    CATEGORY_AI_NEWS = "ai_news"
    CATEGORY_DATACENTER = "datacenterdynamics"

load_dotenv()

# FastAPI 앱 생성
app = FastAPI(title="AI News Summary Service", version="1.0.0")
security = HTTPBasic()

# 정적 파일 마운트
app.mount("/static", StaticFiles(directory="static"), name="static")

# 설정 페이지 접근을 위한 간단한 세션 관리
session_tokens = set()

# 관리자 패스워드 (환경변수에서 읽거나 기본값 사용)
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

def mask_sensitive_value(value: str, show_chars: int = 4) -> str:
    """민감한 정보를 마스킹 처리"""
    if not value or len(value) <= show_chars:
        return "*" * len(value) if value else "(설정되지 않음)"
    return value[:show_chars] + "*" * (len(value) - show_chars)

def generate_session_token() -> str:
    """세션 토큰 생성"""
    return secrets.token_urlsafe(32)

def verify_session(token: str) -> bool:
    """세션 토큰 검증"""
    return token in session_tokens

# 데이터베이스 경로
def get_db_path():
    return '/app/data/news_summaries.db' if os.path.exists('/app/data') else 'news_summaries.db'

# 데이터베이스 초기화
def init_db():
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    if ensure_summary_table:
        ensure_summary_table(cursor)
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                summary TEXT NOT NULL,
                articles_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                category TEXT NOT NULL DEFAULT 'ai_news'
            )
        ''')
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_summaries_date_category
            ON summaries(date, category)
        ''')
    conn.commit()
    conn.close()

# 요약 저장
def save_summary(date: str, summary: str, articles: List[Dict], category: str = CATEGORY_AI_NEWS, ai_provider: str = "gemini"):
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    if ensure_summary_table:
        ensure_summary_table(cursor)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                summary TEXT NOT NULL,
                articles_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                category TEXT NOT NULL DEFAULT 'ai_news',
                ai_provider TEXT NOT NULL DEFAULT 'gemini'
            )
        """)
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_summaries_date_category
            ON summaries(date, category)
        """)
    cursor.execute('''
        INSERT INTO summaries (date, summary, articles_json, category, ai_provider)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(date, category) DO UPDATE SET
            summary=excluded.summary,
            articles_json=excluded.articles_json,
            ai_provider=excluded.ai_provider,
            created_at=CURRENT_TIMESTAMP
    ''', (date, summary, json.dumps(articles, ensure_ascii=False), category, ai_provider))
    conn.commit()
    conn.close()

# 요약 조회
def get_summary(date: str, category: str = CATEGORY_AI_NEWS) -> Optional[Dict]:
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute(
        'SELECT summary, articles_json, ai_provider FROM summaries WHERE date = ? AND category = ?',
        (date, category)
    )
    result = cursor.fetchone()
    conn.close()

    if result:
        return {
            'date': date,
            'summary': result[0],
            'articles': json.loads(result[1]),
            'category': category,
            'ai_provider': result[2] if len(result) > 2 else 'gemini'
        }
    return None

# 모든 요약 날짜 조회
def get_all_dates(category: Optional[str] = None) -> List[str]:
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    if category:
        cursor.execute(
            'SELECT DISTINCT date FROM summaries WHERE category = ? ORDER BY date DESC',
            (category,)
        )
    else:
        cursor.execute('SELECT DISTINCT date FROM summaries ORDER BY date DESC')
    dates = [row[0] for row in cursor.fetchall()]
    conn.close()
    return dates


def convert_utc_to_kst(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        utc_dt = dt.datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc)
        kst_dt = utc_dt.astimezone(dt.timezone(dt.timedelta(hours=9)))
        return kst_dt.strftime("%Y-%m-%d %H:%M:%S KST")
    except ValueError:
        return value


def get_summary_status() -> Dict[str, Dict[str, Optional[str]]]:
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute('''
        SELECT
            category,
            MAX(date) AS latest_date,
            MAX(created_at) AS latest_created_at,
            COUNT(*) AS total_count
        FROM summaries
        GROUP BY category
    ''')
    stats = {}
    for category, latest_date, latest_created, total_count in cursor.fetchall():
        stats[category] = {
            'latest_date': latest_date,
            'latest_created_at': latest_created,
            'latest_created_at_kst': convert_utc_to_kst(latest_created),
            'total_count': total_count,
        }
    cursor.execute('SELECT MAX(created_at) FROM summaries')
    last_run = cursor.fetchone()[0]
    conn.close()
    return {
        'categories': stats,
        'last_run': last_run,
        'last_run_kst': convert_utc_to_kst(last_run),
    }

# 데이터베이스 초기화
init_db()

# Pydantic 모델
class SummaryResponse(BaseModel):
    date: str
    summary: str
    articles: List[Dict]

# API 엔드포인트
@app.get("/")
async def read_root():
    """메인 페이지 (SPA Entry Point)"""
    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/api/dates")
async def get_dates(category: Optional[str] = None):
    target_category = category or CATEGORY_AI_NEWS
    return get_all_dates(target_category)

@app.get("/api/today")
async def get_today():
    """서버의 오늘 날짜를 반환"""
    return {"today": dt.datetime.now().strftime("%Y-%m-%d")}

@app.get("/api/status")
async def get_status():
    return get_summary_status()

@app.get("/api/summary/{date}")
async def get_summary_by_date(date: str, category: Optional[str] = None):
    target_category = category or CATEGORY_AI_NEWS
    summary = get_summary(date, target_category)
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")
    return summary

@app.post("/api/summary")
async def save_summary_endpoint(date: str, summary: str, articles: List[Dict], category: Optional[str] = None):
    save_summary(date, summary, articles, category or CATEGORY_AI_NEWS)
    return {"message": "Summary saved successfully"}

# 설정 페이지 관련 엔드포인트
@app.get("/admin/login")
async def admin_login_page():
    """관리자 로그인 페이지"""
    with open("static/login.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.post("/admin/login")
async def admin_login(password: str = Form(...)):
    """관리자 로그인 처리"""
    if password == ADMIN_PASSWORD:
        token = generate_session_token()
        session_tokens.add(token)
        return {"token": token, "message": "로그인 성공"}
    else:
        raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다")

@app.get("/admin/settings")
async def admin_settings():
    """관리자 설정 페이지"""
    with open("static/settings.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/admin/api/env")
async def get_env_vars(request: Request):
    """환경변수 조회 API (인증 필요)"""
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    token = auth_header.replace("Bearer ", "")
    if not verify_session(token):
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")
    
    # 환경변수 수집 및 마스킹
    env_vars = {
        # 이메일 설정
        "SMTP_HOST": os.getenv("SMTP_HOST", ""),
        "SMTP_PORT": os.getenv("SMTP_PORT", ""),
        "SMTP_USER": os.getenv("SMTP_USER", ""),
        "SMTP_PASS": mask_sensitive_value(os.getenv("SMTP_PASS", "")),
        "EMAIL_TO": os.getenv("EMAIL_TO", ""),

        # 텔레그램 설정
        "TG_TOKEN": mask_sensitive_value(os.getenv("TG_TOKEN", "")),
        "TG_CHAT": os.getenv("TG_CHAT", ""),

        # API 키
        "NEWS_API_KEY": mask_sensitive_value(os.getenv("NEWS_API_KEY", "")),
        "GEMINI_API_KEY": mask_sensitive_value(os.getenv("GEMINI_API_KEY", "")),
        "PERPLEXITY_API_KEY": mask_sensitive_value(os.getenv("PERPLEXITY_API_KEY", "")),

        # AI Provider 설정
        "AI_PROVIDER": os.getenv("AI_PROVIDER", "gemini"),

        # 뉴스 검색 설정
        "NEWS_KEYWORDS": os.getenv("NEWS_KEYWORDS", "AI OR ChatGPT OR GPT-4 OR Claude OR Gemini"),

        # 기타 설정
        "CRON_TIME": os.getenv("CRON_TIME", ""),
        "ADMIN_PASSWORD": "설정됨" if os.getenv("ADMIN_PASSWORD") else "(기본값: admin123)"
    }

    return env_vars

@app.post("/admin/api/send-telegram")
async def send_telegram_manual(request: Request):
    """수동 텔레그램 전송 API (인증 필요)"""
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="인증이 필요합니다")
    
    token = auth_header.replace("Bearer ", "")
    if not verify_session(token):
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")
    
    try:
        # send_ai_news 모듈 import 체크
        if 'run_news_bot' not in globals():
            raise HTTPException(status_code=500, detail="뉴스봇 모듈을 로드할 수 없습니다")
        
        # 뉴스봇 실행 (텔레그램만 전송, 이메일은 전송 안함)
        result = run_news_bot(send_email_flag=False, send_telegram_flag=True)
        
        if result['success']:
            return {
                "success": True,
                "message": f"텔레그램 전송 완료! {result['articles_count']}개 기사 요약",
                "summary_preview": result['summary'][:200] + "..."
            }
        else:
            raise HTTPException(status_code=500, detail=result['message'])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"텔레그램 전송 실패: {str(e)}")

@app.post("/admin/api/send-full")
async def send_full_manual(request: Request):
    """수동 전체 전송 API (이메일 + 텔레그램) (인증 필요)"""
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="인증이 필요합니다")

    token = auth_header.replace("Bearer ", "")
    if not verify_session(token):
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")

    try:
        # send_ai_news 모듈 import 체크
        if 'run_news_bot' not in globals():
            raise HTTPException(status_code=500, detail="뉴스봇 모듈을 로드할 수 없습니다")

        # 뉴스봇 실행 (이메일 + 텔레그램 모두 전송)
        result = run_news_bot(send_email_flag=True, send_telegram_flag=True)

        if result['success']:
            return {
                "success": True,
                "message": f"이메일 + 텔레그램 전송 완료! {result['articles_count']}개 기사 요약",
                "summary_preview": result['summary'][:200] + "..."
            }
        else:
            raise HTTPException(status_code=500, detail=result['message'])

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"전송 실패: {str(e)}")

@app.post("/admin/api/update-keywords")
async def update_keywords(request: Request):
    """뉴스 검색 키워드 업데이트 API (인증 필요)"""
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="인증이 필요합니다")

    token = auth_header.replace("Bearer ", "")
    if not verify_session(token):
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")

    try:
        # 요청 본문에서 키워드 추출
        body = await request.json()
        new_keywords = body.get('keywords', '').strip()

        if not new_keywords:
            raise HTTPException(status_code=400, detail="키워드가 비어있습니다")

        # .env 파일 경로 결정
        env_path = '/app/.env' if os.path.exists('/app/.env') else '.env'

        # .env 파일 읽기
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # NEWS_KEYWORDS 라인 찾아서 업데이트
        updated = False
        for i, line in enumerate(lines):
            if line.strip().startswith('NEWS_KEYWORDS='):
                lines[i] = f'NEWS_KEYWORDS={new_keywords}\n'
                updated = True
                break

        # NEWS_KEYWORDS가 없으면 추가
        if not updated:
            # NEWS_API_KEY 다음에 추가
            for i, line in enumerate(lines):
                if line.strip().startswith('NEWS_API_KEY='):
                    lines.insert(i + 1, '\n')
                    lines.insert(i + 2, '# --- 뉴스 검색 키워드 (OR로 구분, 복잡한 쿼리는 괄호 사용 가능) ---\n')
                    lines.insert(i + 3, f'NEWS_KEYWORDS={new_keywords}\n')
                    break

        # .env 파일 저장
        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)

        # 환경변수 다시 로드
        load_dotenv(override=True)

        return {
            "success": True,
            "message": "키워드가 성공적으로 저장되었습니다. 다음 뉴스 수집부터 적용됩니다.",
            "keywords": new_keywords
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"키워드 업데이트 실패: {str(e)}")

@app.post("/admin/api/update-ai-provider")
async def update_ai_provider(request: Request):
    """AI Provider 업데이트 API (인증 필요)"""
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="인증이 필요합니다")

    token = auth_header.replace("Bearer ", "")
    if not verify_session(token):
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")

    try:
        # 요청 본문에서 provider 추출
        body = await request.json()
        new_provider = body.get('ai_provider', 'gemini').strip().lower()

        if new_provider not in ['gemini', 'perplexity']:
            raise HTTPException(status_code=400, detail="유효하지 않은 AI Provider입니다. 'gemini' 또는 'perplexity'를 선택하세요.")

        # .env 파일 경로 결정
        env_path = '/app/.env' if os.path.exists('/app/.env') else '.env'

        # .env 파일 읽기
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # AI_PROVIDER 라인 찾아서 업데이트
        updated = False
        for i, line in enumerate(lines):
            if line.strip().startswith('AI_PROVIDER='):
                lines[i] = f'AI_PROVIDER={new_provider}\n'
                updated = True
                break

        # AI_PROVIDER가 없으면 추가
        if not updated:
            # GEMINI_API_KEY 다음에 추가
            for i, line in enumerate(lines):
                if line.strip().startswith('GEMINI_API_KEY='):
                    lines.insert(i + 1, '\n')
                    lines.insert(i + 2, '# --- AI Provider 선택 (gemini 또는 perplexity) ---\n')
                    lines.insert(i + 3, f'AI_PROVIDER={new_provider}\n')
                    break

        # .env 파일 저장
        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)

        # 환경변수 다시 로드
        load_dotenv(override=True)

        provider_name = "Google Gemini" if new_provider == "gemini" else "Perplexity Sonar"

        return {
            "success": True,
            "message": f"AI Provider가 {provider_name}(으)로 변경되었습니다. 다음 뉴스 수집부터 적용됩니다.",
            "ai_provider": new_provider
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Provider 업데이트 실패: {str(e)}")

@app.post("/admin/api/test-keywords")
async def test_keywords(request: Request):
    """뉴스 검색 키워드 테스트 API (인증 필요)"""
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="인증이 필요합니다")

    token = auth_header.replace("Bearer ", "")
    if not verify_session(token):
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다")

    try:
        # 요청 본문에서 키워드 추출
        body = await request.json()
        test_keywords_str = body.get('keywords', '').strip()

        if not test_keywords_str:
            raise HTTPException(status_code=400, detail="키워드가 비어있습니다")

        # send_ai_news 모듈 import 체크
        if 'run_news_bot' not in globals():
            raise HTTPException(status_code=500, detail="뉴스봇 모듈을 로드할 수 없습니다")

        # 뉴스 API 키 가져오기
        news_api_key = os.getenv("NEWS_API_KEY")
        if not news_api_key:
            raise HTTPException(status_code=500, detail="NEWS_API_KEY가 설정되지 않았습니다")

        # send_ai_news.py의 fetch_news 함수 import
        from send_ai_news import fetch_news

        # 테스트용으로 뉴스 수집 (요약 생성이나 전송은 하지 않음)
        articles = fetch_news(news_api_key, test_keywords_str)

        # 결과 생성
        count = len(articles)
        sample_titles = []

        if count > 0:
            # 최대 5개의 샘플 타이틀 추출
            for article in articles[:5]:
                title = article.get('title', '제목 없음')
                source_info = article.get('source')
                if isinstance(source_info, dict):
                    source_name = source_info.get('name', '출처 미상')
                else:
                    source_name = '출처 미상'
                sample_titles.append(f"{title} ({source_name})")

        return {
            "success": True,
            "count": count,
            "sample_titles": sample_titles,
            "keywords": test_keywords_str
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"키워드 테스트 실패: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
