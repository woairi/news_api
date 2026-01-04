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
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI 뉴스 요약 서비스</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
                color: #333;
            }
            
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                overflow: hidden;
            }
            
            .header {
                background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
                color: white;
                padding: 40px 20px;
                text-align: center;
            }

            .header-status {
                margin-top: 25px;
                display: flex;
                flex-direction: column;
                gap: 16px;
                align-items: center;
            }
            
            .header h1 {
                font-size: 2.5em;
                margin-bottom: 10px;
                font-weight: 700;
            }
            
            .header p {
                font-size: 1.1em;
                opacity: 0.9;
            }
            
            .calendar-container {
                padding: 24px 20px;
                background: #f8f9fa;
                border-radius: 20px;
                box-shadow: 0 12px 24px rgba(0,0,0,0.08);
            }
            
            .calendar-container h3 {
                font-size: 1.4em;
                margin-bottom: 20px;
                color: #2c3e50;
            }
            
            .date-buttons {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                justify-content: center;
            }

            .recent-dates-section .date-buttons {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 8px;
                max-height: 220px;
                overflow-y: auto;
                padding-right: 6px;
            }

            .recent-dates-section .date-buttons::-webkit-scrollbar {
                width: 6px;
            }

            .recent-dates-section .date-buttons::-webkit-scrollbar-thumb {
                background: rgba(102, 126, 234, 0.35);
                border-radius: 3px;
            }

            .date-button {
                padding: 12px 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 25px;
                cursor: pointer;
                font-size: 0.9em;
                font-weight: 500;
                transition: all 0.3s ease;
                box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
            }

            .recent-dates-section .date-button {
                width: 100%;
                padding: 10px 14px;
                min-width: 0;
            }
            
            .date-button:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
            }
            
            .date-button:active {
                transform: translateY(0);
            }
            
            .summary-container {
                padding: 30px 20px;
                min-height: 400px;
            }

            .summary-tabs {
                display: flex;
                gap: 12px;
                justify-content: center;
                margin-bottom: 20px;
                flex-wrap: wrap;
            }

            .tab-button {
                padding: 10px 20px;
                border-radius: 25px;
                border: 2px solid #667eea;
                background: white;
                color: #667eea;
                font-size: 0.95em;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
            }

            .tab-button:hover {
                background: rgba(102, 126, 234, 0.1);
            }

            .tab-button.active {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
            }

            .date-button.active {
                outline: 2px solid rgba(255, 255, 255, 0.9);
            }

            .date-button.latest {
                border: 2px solid rgba(102, 126, 234, 0.6);
            }

            .tab-info {
                text-align: center;
                font-size: 0.9em;
                color: #555;
                margin-top: 10px;
                margin-bottom: 20px;
            }

            .tab-info strong {
                color: #2c3e50;
            }
            
            .loading {
                text-align: center;
                color: #666;
                font-size: 1.1em;
                padding: 40px;
            }
            
            .summary-header {
                text-align: center;
                margin-bottom: 30px;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border-radius: 15px;
                font-size: 1.3em;
                font-weight: 600;
            }
            
            .article-item {
                margin: 25px 0;
                padding: 25px;
                background: white;
                border-radius: 15px;
                border-left: 5px solid #667eea;
                box-shadow: 0 5px 15px rgba(0,0,0,0.08);
                transition: transform 0.3s ease;
            }

            .article-item:hover {
                transform: translateY(-3px);
                box-shadow: 0 8px 25px rgba(0,0,0,0.15);
            }

            .article-header {
                display: flex;
                gap: 12px;
                align-items: center;
                flex-wrap: wrap;
                margin-bottom: 12px;
            }

            .article-index {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                min-width: 36px;
                padding: 6px 10px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border-radius: 999px;
                font-weight: 700;
                font-size: 0.9em;
            }

            .article-title {
                font-size: 1.2em;
                font-weight: 700;
                color: #2c3e50;
                margin: 0;
                line-height: 1.4;
                flex: 1;
                line-height: 1.4;
            }

            .article-source {
                padding: 6px 12px;
                background: rgba(102, 126, 234, 0.12);
                color: #4c5bd4;
                border-radius: 999px;
                font-size: 0.85em;
                font-weight: 600;
            }

            .ai-provider-badge {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                min-width: 32px;
                padding: 4px 10px;
                background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%);
                color: white;
                border-radius: 999px;
                font-weight: 700;
                font-size: 0.75em;
                letter-spacing: 0.5px;
            }

            .ai-provider-badge.perplexity {
                background: linear-gradient(135deg, #e67e22 0%, #f39c12 100%);
            }

            .article-summary {
                font-size: 1em;
                line-height: 1.6;
                color: #555;
                margin-bottom: 15px;
            }
            
            .article-link {
                display: inline-block;
                padding: 10px 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white !important;
                text-decoration: none;
                border-radius: 25px;
                font-size: 0.9em;
                font-weight: 500;
                transition: all 0.3s ease;
                box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
            }
            
            .article-link:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
            }
            
            .no-summaries {
                text-align: center;
                color: #666;
                font-size: 1.1em;
                padding: 40px;
            }
            
            .date-selection-grid {
                display: grid;
                grid-template-columns: 1fr;
                gap: 24px;
            }

            .status-grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 16px;
                margin-bottom: 0;
            }

            .status-card {
                background: rgba(255, 255, 255, 0.96);
                border-radius: 15px;
                padding: 18px 20px;
                box-shadow: 0 6px 20px rgba(0,0,0,0.08);
                border-left: 5px solid #667eea;
                display: flex;
                flex-direction: column;
                gap: 8px;
                min-width: 220px;
            }

            .status-card.datacenterdynamics {
                border-left-color: #2ecc71;
            }

            .status-title {
                font-weight: 700;
                color: #1f2a44;
                display: flex;
                align-items: center;
                gap: 8px;
                font-size: 1.05em;
            }

            .status-info {
                font-size: 0.95em;
                color: #1f2a44;
                font-weight: 600;
            }

            .status-info strong {
                color: #1f2a44;
                font-weight: 700;
            }

            .header .status-card .status-info {
                color: #1f2a44;
                font-weight: 600;
            }

            .header .status-card .status-info strong {
                color: #1f2a44;
                font-weight: 700;
            }

            .header-status > .status-info {
                color: rgba(255, 255, 255, 0.9);
                font-weight: 600;
            }

            .header-status > .status-info strong {
                color: #ffffff;
            }

            .layout-grid {
                display: grid;
                grid-template-columns: minmax(0, 2fr) minmax(260px, 1fr);
                gap: 24px;
                margin-top: 30px;
            }

            .layout-main {
                display: flex;
                flex-direction: column;
                gap: 20px;
            }

            .layout-side {
                display: flex;
                width: 100%;
            }

            .layout-side .calendar-container {
                width: 100%;
            }
            
            .recent-dates-section {
                padding: 20px;
                background: rgba(255, 255, 255, 0.7);
                border-radius: 15px;
                border: 2px solid #e9ecef;
            }
            
            .older-dates-section {
                padding: 20px;
                background: rgba(255, 255, 255, 0.7);
                border-radius: 15px;
                border: 2px solid #e9ecef;
            }
            
            .recent-dates-section h3,
            .older-dates-section h3 {
                font-size: 1.4em;
                margin-bottom: 20px;
                color: #2c3e50;
                text-align: center;
            }
            
            .calendar-section {
                display: flex;
                gap: 15px;
                justify-content: center;
                align-items: center;
                margin-bottom: 15px;
                flex-wrap: wrap;
            }
            
            .date-buttons {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                justify-content: center;
            }
            
            .date-picker {
                padding: 12px 15px;
                border: 2px solid #667eea;
                border-radius: 10px;
                font-size: 1em;
                background: white;
                color: #2c3e50;
                cursor: pointer;
                transition: all 0.3s ease;
            }
            
            .date-picker:focus {
                outline: none;
                border-color: #764ba2;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
            }
            
            .search-button {
                padding: 12px 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 10px;
                cursor: pointer;
                font-size: 1em;
                font-weight: 500;
                transition: all 0.3s ease;
                box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
            }
            
            .search-button:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
            }
            
            .older-dates-info {
                text-align: center;
                color: #666;
                font-size: 0.9em;
                margin-top: 10px;
            }
            
            /* 모바일 반응형 */
            @media (max-width: 1024px) {
                .layout-grid {
                    grid-template-columns: 1fr;
                }

                .layout-side {
                    margin-top: 15px;
                }

                .status-grid {
                    grid-template-columns: 1fr;
                }
            }

            @media (max-width: 768px) {
                body {
                    padding: 10px;
                }
                
                .header h1 {
                    font-size: 2em;
                }
                
                .header p {
                    font-size: 1em;
                }
                
                .calendar-container,
                .summary-container {
                    padding: 20px 15px;
                }

                .layout-side {
                    margin-top: 10px;
                }

                .date-selection-grid {
                    grid-template-columns: 1fr;
                    gap: 20px;
                }
                
                .recent-dates-section,
                .older-dates-section {
                    padding: 15px;
                }
                
                .date-button {
                    padding: 10px 15px;
                    font-size: 0.8em;
                }
                
                .article-item {
                    padding: 20px;
                    margin: 20px 0;
                }
                
                .article-title {
                    font-size: 1.1em;
                }
                
                .article-summary {
                    font-size: 0.9em;
                }
            }
            
            @media (max-width: 480px) {
                .header {
                    padding: 30px 15px;
                }
                
                .header h1 {
                    font-size: 1.8em;
                }
                
                .date-buttons {
                    gap: 8px;
                }

                .status-grid {
                    grid-template-columns: 1fr;
                }
                
                .date-button {
                    padding: 8px 12px;
                    font-size: 0.75em;
                }
                
                .article-item {
                    padding: 15px;
                }
                
                .calendar-section {
                    flex-direction: column;
                    gap: 10px;
                }
                
                .date-picker,
                .search-button {
                    width: 100%;
                    max-width: 300px;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📰 AI & Datacenter 뉴스 요약</h1>
                <p>AI와 데이터센터 뉴스를 한눈에 확인하세요</p>
                <div style="margin-top: 15px;">
                    <a href="/admin/login" style="color: rgba(255,255,255,0.8); text-decoration: none; font-size: 0.9em; border: 1px solid rgba(255,255,255,0.3); padding: 8px 16px; border-radius: 15px; transition: all 0.3s ease;" onmouseover="this.style.background='rgba(255,255,255,0.1)'" onmouseout="this.style.background='transparent'">⚙️ 시스템 설정</a>
                </div>
                <div class="header-status">
                    <div class="status-grid" id="statusGrid">
                        <div class="status-card" data-category="ai_news">
                            <div class="status-title">🤖 AI 뉴스</div>
                            <div class="status-info">기준일: <strong id="status-ai-date">-</strong></div>
                            <div class="status-info">업데이트: <strong id="status-ai-run">-</strong></div>
                        </div>
                        <div class="status-card datacenterdynamics" data-category="datacenterdynamics">
                            <div class="status-title">📊 DatacenterDynamics</div>
                            <div class="status-info">전일 기준일: <strong id="status-dc-date">-</strong></div>
                            <div class="status-info">업데이트: <strong id="status-dc-run">-</strong></div>
                        </div>
                    </div>
                    <div class="status-info">최근 실행 시각: <strong id="status-last-run">-</strong></div>
                </div>
            </div>

            <div class="layout-grid">
                <div class="layout-main">
                    <div class="summary-container">
                        <div class="summary-tabs">
                            <button class="tab-button active" id="tab-ai_news" onclick="switchCategory('ai_news')">🤖 AI 뉴스</button>
                            <button class="tab-button" id="tab-datacenterdynamics" onclick="switchCategory('datacenterdynamics')">📊 DatacenterDynamics</button>
                        </div>
                        <div class="tab-info" id="tabInfo">최근 48시간 인기 AI 기사 요약을 확인하세요.</div>
                        <div id="summaryContent">
                            <p class="loading">📋 날짜를 선택하면 요약을 확인할 수 있습니다</p>
                        </div>
                    </div>
                </div>
                <aside class="layout-side">
                    <div class="calendar-container">
                        <div class="date-selection-grid">
                            <div class="recent-dates-section">
                                <h3>📅 최근 일주일 요약</h3>
                                <div class="date-buttons" id="recentButtons"></div>
                            </div>

                            <div class="older-dates-section">
                                <h3>📅 이전 날짜 선택</h3>
                                <div class="calendar-section">
                                    <input type="date" id="datePicker" class="date-picker">
                                    <button class="search-button" onclick="searchByDate()">🔍 조회</button>
                                </div>
                                <div class="older-dates-info">
                                    <p>일주일 이전 날짜는 달력에서 선택하세요</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </aside>
            </div>
        </div>

        <script>
            const CATEGORY_TITLES = {
                'ai_news': 'AI 뉴스 요약',
                'datacenterdynamics': 'DatacenterDynamics 요약'
            };
            const TAB_BASE_MESSAGES = {
                'ai_news': '최근 48시간 인기 AI 기사 요약을 확인하세요.',
                'datacenterdynamics': 'DatacenterDynamics 요약은 전일 기사 기준으로 제공됩니다.'
            };
            let currentCategory = 'ai_news';
            let currentSelectedDate = null;
            let availableDates = [];
            let latestDateByCategory = {};
            let statusData = {};
            const tabInfoElement = document.getElementById('tabInfo');
            const statusElements = {
                aiDate: document.getElementById('status-ai-date'),
                aiRun: document.getElementById('status-ai-run'),
                dcDate: document.getElementById('status-dc-date'),
                dcRun: document.getElementById('status-dc-run'),
                lastRun: document.getElementById('status-last-run'),
            };

            function updateActiveTab() {
                document.querySelectorAll('.tab-button').forEach(button => {
                    const tabId = `tab-${currentCategory}`;
                    if (button.id === tabId) {
                        button.classList.add('active');
                    } else {
                        button.classList.remove('active');
                    }
                });
            }

            function highlightSelectedDateButtons() {
                const buttons = document.querySelectorAll('.date-button');
                buttons.forEach(button => {
                    if (button.textContent === currentSelectedDate) {
                        button.classList.add('active');
                    } else {
                        button.classList.remove('active');
                    }
                });
            }

            function updateTabInfo(summaryDate = null) {
                if (!tabInfoElement) return;
                const baseMessage = TAB_BASE_MESSAGES[currentCategory] || '';
                if (summaryDate) {
                    if (currentCategory === 'datacenterdynamics') {
                        tabInfoElement.innerHTML = `${baseMessage} <strong>(요약 기준일: ${summaryDate})</strong>`;
                    } else {
                        tabInfoElement.innerHTML = `${baseMessage} <strong>(요약 생성일: ${summaryDate})</strong>`;
                    }
                    return;
                }

                const latest = latestDateByCategory[currentCategory];
                if (latest) {
                    if (currentCategory === 'datacenterdynamics') {
                        tabInfoElement.innerHTML = `${baseMessage} <strong>(가장 최근 기준일: ${latest})</strong>`;
                    } else {
                        tabInfoElement.innerHTML = `${baseMessage} <strong>(가장 최근 생성일: ${latest})</strong>`;
                    }
                } else {
                    tabInfoElement.textContent = baseMessage;
                }
            }

            function applyStatusToUI() {
                const categories = statusData.categories || {};
                const aiStatus = categories['ai_news'] || {};
                const dcStatus = categories['datacenterdynamics'] || {};
                if (statusElements.aiDate) {
                    statusElements.aiDate.textContent = aiStatus.latest_date || '-';
                }
                if (statusElements.aiRun) {
                    statusElements.aiRun.textContent = aiStatus.latest_created_at_kst || aiStatus.latest_created_at || '-';
                }
                if (statusElements.dcDate) {
                    statusElements.dcDate.textContent = dcStatus.latest_date || '-';
                }
                if (statusElements.dcRun) {
                    statusElements.dcRun.textContent = dcStatus.latest_created_at_kst || dcStatus.latest_created_at || '-';
                }
                if (statusElements.lastRun) {
                    statusElements.lastRun.textContent = statusData.last_run_kst || statusData.last_run || '-';
                }
            }

            async function loadStatus() {
                try {
                    const response = await fetch('/api/status');
                    if (!response.ok) {
                        throw new Error('status fetch failed');
                    }
                    statusData = await response.json();
                    const categories = statusData.categories || {};
                    Object.entries(categories).forEach(([category, info]) => {
                        if (info && info.latest_date) {
                            latestDateByCategory[category] = info.latest_date;
                        }
                    });
                    applyStatusToUI();
                    updateTabInfo();
                } catch (error) {
                    console.warn('상태 정보를 불러오지 못했습니다', error);
                }
            }

            // 날짜 필터링 함수
            function filterDates(dates) {
                const now = new Date();
                const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
                
                const recent = [];
                const older = [];
                
                dates.forEach(dateStr => {
                    const date = new Date(dateStr);
                    if (date >= sevenDaysAgo) {
                        recent.push(dateStr);
                    } else {
                        older.push(dateStr);
                    }
                });
                
                return { recent, older };
            }

            async function switchCategory(category) {
                currentCategory = category;
                updateActiveTab();
                currentSelectedDate = null;
                document.getElementById('summaryContent').innerHTML = '<p class="loading">📡 요약을 불러오는 중...</p>';
                updateTabInfo();
                await loadDates();
                await loadTodaySummary();
            }
            
            // 날짜 버튼 로드
            async function loadDates() {
                try {
                    const response = await fetch(`/api/dates?category=${currentCategory}`);
                    const dates = await response.json();
                    availableDates = dates;
                    latestDateByCategory[currentCategory] = dates.length > 0 ? dates[0] : null;
                    const container = document.getElementById('recentButtons');
                    const categoryLabel = CATEGORY_TITLES[currentCategory] || '선택한';
                    
                    if (dates.length === 0) {
                        container.innerHTML = `<p class="no-summaries">${categoryLabel} 기록이 없습니다</p>`;
                        return;
                    }
                    
                    const { recent, older } = filterDates(dates);
                    
                    if (recent.length === 0) {
                        container.innerHTML = '<p class="no-summaries">최근 일주일 요약이 없습니다</p>';
                    } else {
                        container.innerHTML = recent.map((date, index) => 
                            `<button class="date-button${index === 0 ? ' latest' : ''}" data-date="${date}" onclick="loadSummary('${date}')">${date}</button>`
                        ).join('');
                    }
                    if (!currentSelectedDate && dates.length > 0) {
                        await loadSummary(dates[0]);
                    } else {
                        highlightSelectedDateButtons();
                    }
                    
                    // 달력 최대 날짜 설정 (가장 오래된 날짜까지)
                    const datePicker = document.getElementById('datePicker');
                    if (older.length > 0) {
                        const oldestDate = older[older.length - 1];
                        datePicker.min = oldestDate;
                    }
                    // 서버에서 오늘 날짜 가져와서 설정
                    try {
                        const todayResponse = await fetch('/api/today');
                        const todayData = await todayResponse.json();
                        datePicker.max = todayData.today;
                    } catch (error) {
                        const today = new Date().toISOString().split('T')[0];
                        datePicker.max = today;
                    }
                    
                } catch (error) {
                    console.error('날짜 로드 실패:', error);
                    document.getElementById('recentButtons').innerHTML = '<p class="no-summaries">날짜 로드에 실패했습니다</p>';
                }
            }
            
            // 달력에서 날짜 선택 조회
            async function searchByDate() {
                const datePicker = document.getElementById('datePicker');
                const selectedDate = datePicker.value;
                
                if (!selectedDate) {
                    alert('날짜를 선택해주세요');
                    return;
                }
                
                // 선택된 날짜가 최근 7일 이내인지 확인
                const now = new Date();
                const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
                const selected = new Date(selectedDate);
                
                if (selected >= sevenDaysAgo) {
                    alert('최근 일주일 날짜는 위의 버튼을 사용해주세요');
                    return;
                }
                
                await loadSummary(selectedDate);
            }

            // 요약 파싱 및 표시
            function parseSummary(summaryText) {
                const lines = summaryText.split('\\n');
                const articles = [];
                let currentArticle = null;
                const headerPattern = /^(\\d+)\\.\\s*(.+?)(?:\\s*\\(([^)]+)\\))?$/;
                
                for (const line of lines) {
                    const trimmed = line.trim();
                    if (!trimmed) continue;
                    
                    if (trimmed.startsWith('📰')) {
                        if (currentArticle) {
                            articles.push(currentArticle);
                        }
                        const headerText = trimmed.replace('📰', '').trim();
                        let index = null;
                        let titleText = headerText;
                        let source = '';
                        const match = headerText.match(headerPattern);
                        if (match) {
                            index = match[1];
                            titleText = match[2].trim();
                            source = match[3] ? match[3].trim() : '';
                        }
                        currentArticle = {
                            title: titleText,
                            summary: '',
                            link: '',
                            index,
                            source,
                        };
                    } else if (trimmed.startsWith('📝')) {
                        if (currentArticle) {
                            currentArticle.summary = trimmed.replace('📝', '').trim();
                        }
                    } else if (trimmed.startsWith('🔗')) {
                        if (currentArticle) {
                            currentArticle.link = trimmed.replace('🔗', '').trim();
                        }
                    }
                }
                
                if (currentArticle) {
                    articles.push(currentArticle);
                }
                
                return articles;
            }

            // 요약 로드
            async function loadSummary(date) {
                const container = document.getElementById('summaryContent');
                container.innerHTML = '<p class="loading">📡 요약을 불러오는 중...</p>';
                
                try {
                    const response = await fetch(`/api/summary/${date}?category=${currentCategory}`);
                    if (!response.ok) {
                        throw new Error('요약을 찾을 수 없습니다');
                    }

                    const data = await response.json();
                    const articles = parseSummary(data.summary);
                    const categoryLabel = CATEGORY_TITLES[currentCategory] || 'AI 뉴스 요약';

                    // AI Provider 뱃지 생성
                    const aiProvider = data.ai_provider || 'gemini';
                    const providerClass = aiProvider === 'perplexity' ? 'perplexity' : '';
                    const providerLabel = aiProvider === 'perplexity' ? 'P' : 'G';
                    const providerBadge = `<span class="ai-provider-badge ${providerClass}" title="${aiProvider === 'perplexity' ? 'Perplexity Sonar' : 'Google Gemini'}">${providerLabel}</span>`;

                    let html = `<div class="summary-header">📅 ${data.date} ${categoryLabel} ${providerBadge}</div>`;
                    
                    if (articles.length === 0) {
                        const message = (data.summary || '파싱할 수 있는 기사가 없습니다').replace(/\\n/g, '<br>');
                        html += `<p class="no-summaries">${message}</p>`;
                    } else {
                        articles.forEach((article, index) => {
                            const displayIndex = article.index || String(index + 1);
                            const sourceBadge = article.source ? `<span class="article-source">${article.source}</span>` : '';
                            const summaryBlock = article.summary ? `<div class="article-summary">${article.summary}</div>` : '';
                            const linkBlock = article.link ? `<a href="${article.link}" class="article-link" target="_blank" rel="noopener noreferrer">🔗 원문 보기</a>` : '';
                            html += `
                                <div class="article-item">
                                    <div class="article-header">
                                        <span class="article-index">#${displayIndex}</span>
                                        <div class="article-title">${article.title}</div>
                                        ${sourceBadge}
                                    </div>
                                    ${summaryBlock}
                                    ${linkBlock}
                                </div>
                            `;
                        });
                    }
                    
                    container.innerHTML = html;
                    currentSelectedDate = date;
                    highlightSelectedDateButtons();
                    updateTabInfo(data.date);
                } catch (error) {
                    console.error('요약 로드 실패:', error);
                    container.innerHTML = '<p class="no-summaries">❌ 요약을 불러오는데 실패했습니다</p>';
                    currentSelectedDate = null;
                    highlightSelectedDateButtons();
                    updateTabInfo();
                }
            }

            // 오늘 날짜 요약 자동 로드
            async function loadTodaySummary() {
                try {
                    // 서버에서 오늘 날짜 가져오기
                    const todayResponse = await fetch('/api/today');
                    const todayData = await todayResponse.json();
                    const today = todayData.today;
                    
                    const response = await fetch(`/api/summary/${today}?category=${currentCategory}`);
                    if (response.ok) {
                        await loadSummary(today);
                    } else if (availableDates.length > 0) {
                        await loadSummary(availableDates[0]);
                    } else {
                        document.getElementById('summaryContent').innerHTML = '<p class="no-summaries">오늘 날짜에는 저장된 요약이 없습니다</p>';
                        currentSelectedDate = null;
                        highlightSelectedDateButtons();
                        updateTabInfo();
                    }
                } catch (error) {
                    console.log('오늘 요약이 없습니다');
                    if (availableDates.length > 0) {
                        await loadSummary(availableDates[0]);
                    } else {
                        document.getElementById('summaryContent').innerHTML = '<p class="no-summaries">오늘 날짜에는 저장된 요약이 없습니다</p>';
                        currentSelectedDate = null;
                        highlightSelectedDateButtons();
                        updateTabInfo();
                    }
                }
            }
            
            // 페이지 로드 시 기본 탭 상태 설정 후 데이터 로드
            async function initializePage() {
                updateActiveTab();
                updateTabInfo();
                await loadStatus();
                await loadDates();
                await loadTodaySummary();
            }

            initializePage();
        </script>
    </body>
    </html>
    """)

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
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head>
        <title>관리자 로그인 - AI 뉴스 요약</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }
            .login-container {
                background: white;
                border-radius: 20px;
                padding: 40px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                width: 100%;
                max-width: 400px;
            }
            .login-header {
                text-align: center;
                margin-bottom: 30px;
            }
            .login-header h1 {
                font-size: 2em;
                color: #2c3e50;
                margin-bottom: 10px;
            }
            .login-header p {
                color: #666;
            }
            .form-group {
                margin-bottom: 20px;
            }
            .form-group label {
                display: block;
                margin-bottom: 8px;
                color: #2c3e50;
                font-weight: 500;
            }
            .form-group input {
                width: 100%;
                padding: 12px 15px;
                border: 2px solid #e9ecef;
                border-radius: 10px;
                font-size: 1em;
                transition: border-color 0.3s ease;
            }
            .form-group input:focus {
                outline: none;
                border-color: #667eea;
            }
            .login-button {
                width: 100%;
                padding: 15px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 1em;
                font-weight: 500;
                cursor: pointer;
                transition: transform 0.3s ease;
            }
            .login-button:hover {
                transform: translateY(-2px);
            }
            .error-message {
                color: #e74c3c;
                text-align: center;
                margin-top: 15px;
                display: none;
            }
            .back-link {
                text-align: center;
                margin-top: 20px;
            }
            .back-link a {
                color: #667eea;
                text-decoration: none;
            }
        </style>
    </head>
    <body>
        <div class="login-container">
            <div class="login-header">
                <h1>🔐 관리자 로그인</h1>
                <p>시스템 설정을 확인하려면 로그인하세요</p>
            </div>
            <form id="loginForm" onsubmit="handleLogin(event)">
                <div class="form-group">
                    <label for="password">비밀번호</label>
                    <input type="password" id="password" name="password" required>
                </div>
                <button type="submit" class="login-button">로그인</button>
                <div id="errorMessage" class="error-message">비밀번호가 올바르지 않습니다.</div>
            </form>
            <div class="back-link">
                <a href="/">← 메인 페이지로 돌아가기</a>
            </div>
        </div>
        
        <script>
            async function handleLogin(event) {
                event.preventDefault();
                const password = document.getElementById('password').value;
                const errorMessage = document.getElementById('errorMessage');
                
                try {
                    const response = await fetch('/admin/login', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                        body: `password=${encodeURIComponent(password)}`
                    });
                    
                    if (response.ok) {
                        const data = await response.json();
                        sessionStorage.setItem('admin_token', data.token);
                        window.location.href = '/admin/settings';
                    } else {
                        errorMessage.style.display = 'block';
                        document.getElementById('password').value = '';
                    }
                } catch (error) {
                    errorMessage.style.display = 'block';
                }
            }
        </script>
    </body>
    </html>
    """)

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
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head>
        <title>시스템 설정 - AI 뉴스 요약</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
                color: #333;
            }
            .container {
                max-width: 1000px;
                margin: 0 auto;
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                overflow: hidden;
            }
            .header {
                background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
                color: white;
                padding: 30px 20px;
                text-align: center;
            }
            .header h1 {
                font-size: 2em;
                margin-bottom: 10px;
            }
            .nav-buttons {
                display: flex;
                gap: 10px;
                justify-content: center;
                margin-top: 20px;
            }
            .nav-button {
                padding: 10px 20px;
                background: rgba(255,255,255,0.2);
                color: white;
                border: none;
                border-radius: 20px;
                cursor: pointer;
                text-decoration: none;
                transition: background 0.3s ease;
            }
            .nav-button:hover {
                background: rgba(255,255,255,0.3);
            }
            .send-button {
                background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%);
            }
            .send-button:hover {
                background: linear-gradient(135deg, #229954 0%, #27ae60 100%);
            }
            .status-message {
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 15px 20px;
                border-radius: 10px;
                color: white;
                font-weight: 500;
                z-index: 1000;
                opacity: 0;
                transform: translateX(100%);
                transition: all 0.3s ease;
            }
            .status-message.show {
                opacity: 1;
                transform: translateX(0);
            }
            .status-success {
                background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%);
            }
            .status-error {
                background: linear-gradient(135deg, #e74c3c 0%, #c0392b 100%);
            }
            .status-info {
                background: linear-gradient(135deg, #3498db 0%, #2980b9 100%);
            }
            .content {
                padding: 30px 20px;
            }
            .section {
                margin-bottom: 30px;
                padding: 20px;
                background: #f8f9fa;
                border-radius: 15px;
                border-left: 5px solid #667eea;
            }
            .section h2 {
                color: #2c3e50;
                margin-bottom: 15px;
                font-size: 1.3em;
            }
            .env-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 15px;
                margin-top: 15px;
            }
            .env-item {
                background: white;
                padding: 15px;
                border-radius: 10px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }
            .env-label {
                font-weight: 600;
                color: #2c3e50;
                margin-bottom: 5px;
            }
            .env-value {
                font-family: 'Courier New', monospace;
                background: #f1f3f4;
                padding: 8px 12px;
                border-radius: 5px;
                word-break: break-all;
                font-size: 0.9em;
            }
            .status-indicator {
                display: inline-block;
                width: 10px;
                height: 10px;
                border-radius: 50%;
                margin-right: 8px;
            }
            .status-ok { background: #27ae60; }
            .status-error { background: #e74c3c; }
            .loading {
                text-align: center;
                color: #666;
                padding: 20px;
            }
            @media (max-width: 768px) {
                .env-grid { grid-template-columns: 1fr; }
                .nav-buttons { flex-direction: column; align-items: center; }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>⚙️ 시스템 설정</h1>
                <p>AI 뉴스 봇 환경변수 및 시스템 상태</p>
                <div class="nav-buttons">
                    <a href="/" class="nav-button">📰 메인 페이지</a>
                    <button class="nav-button" onclick="sendTelegramManual()">📱 텔레그램 전송</button>
                    <button class="nav-button" onclick="logout()">🚪 로그아웃</button>
                    <button class="nav-button" onclick="refreshData()">🔄 새로고침</button>
                </div>
            </div>
            
            <div class="content">
                <div id="loadingMessage" class="loading">
                    📡 환경변수 정보를 불러오는 중...
                </div>
                
                <div id="settingsContent" style="display: none;">
                    <div class="section">
                        <h2>📧 이메일 설정</h2>
                        <div class="env-grid" id="emailSettings"></div>
                    </div>
                    
                    <div class="section">
                        <h2>📱 텔레그램 설정</h2>
                        <div class="env-grid" id="telegramSettings"></div>
                    </div>
                    
                    <div class="section">
                        <h2>🔑 API 키 설정</h2>
                        <div class="env-grid" id="apiSettings"></div>
                    </div>

                    <div class="section">
                        <h2>🤖 AI 요약 Provider 설정</h2>
                        <p style="color: #666; margin-bottom: 15px; font-size: 0.9em;">
                            뉴스 요약에 사용할 AI 모델을 선택합니다.
                        </p>
                        <div style="background: white; padding: 15px; border-radius: 10px;">
                            <div style="margin-bottom: 10px;">
                                <label for="aiProviderSelect" style="display: block; margin-bottom: 8px; font-weight: 600; color: #2c3e50;">AI Provider</label>
                                <select id="aiProviderSelect"
                                        style="width: 100%; padding: 12px; border: 2px solid #e9ecef; border-radius: 8px; font-size: 1em; background: white; cursor: pointer;">
                                    <option value="gemini">Google Gemini</option>
                                    <option value="perplexity">Perplexity Sonar</option>
                                </select>
                            </div>
                            <div style="margin-top: 10px; display: flex; gap: 10px; align-items: center;">
                                <button onclick="updateAIProvider()"
                                        style="padding: 10px 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 500; transition: transform 0.3s ease;"
                                        onmouseover="this.style.transform='translateY(-2px)'"
                                        onmouseout="this.style.transform='translateY(0)'">
                                    💾 Provider 저장
                                </button>
                            </div>
                            <div style="margin-top: 10px; font-size: 0.85em; color: #666;">
                                <strong>참고:</strong><br>
                                • Google Gemini: 빠르고 정확한 요약<br>
                                • Perplexity Sonar: 웹 검색 기반 컨텍스트 이해
                            </div>
                        </div>
                    </div>

                    <div class="section">
                        <h2>🔍 뉴스 검색 키워드</h2>
                        <p style="color: #666; margin-bottom: 15px; font-size: 0.9em;">
                            뉴스 검색에 사용할 키워드를 설정합니다. OR, AND, 괄호를 사용하여 복잡한 검색 쿼리를 만들 수 있습니다.
                        </p>
                        <div style="background: white; padding: 15px; border-radius: 10px;">
                            <textarea id="keywordsInput"
                                      style="width: 100%; min-height: 80px; padding: 12px; border: 2px solid #e9ecef; border-radius: 8px; font-family: 'Courier New', monospace; font-size: 0.95em; resize: vertical;"
                                      placeholder="예: AI OR ChatGPT OR (Machine Learning AND Deep Learning)"></textarea>
                            <div style="margin-top: 10px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
                                <button onclick="updateKeywords()"
                                        style="padding: 10px 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 500; transition: transform 0.3s ease;"
                                        onmouseover="this.style.transform='translateY(-2px)'"
                                        onmouseout="this.style.transform='translateY(0)'">
                                    💾 키워드 저장
                                </button>
                                <button onclick="testKeywords()"
                                        style="padding: 10px 20px; background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%); color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 500; transition: transform 0.3s ease;"
                                        onmouseover="this.style.transform='translateY(-2px)'"
                                        onmouseout="this.style.transform='translateY(0)'">
                                    🧪 키워드 테스트
                                </button>
                                <button onclick="resetKeywords()"
                                        style="padding: 10px 20px; background: #6c757d; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 500; transition: transform 0.3s ease;"
                                        onmouseover="this.style.transform='translateY(-2px)'"
                                        onmouseout="this.style.transform='translateY(0)'">
                                    🔄 원래 값으로
                                </button>
                            </div>
                            <div id="testResults" style="margin-top: 15px; display: none; padding: 15px; background: #e8f5e9; border-radius: 8px; border-left: 4px solid #27ae60;">
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                                    <h4 style="margin: 0; color: #27ae60;">🧪 테스트 결과</h4>
                                    <button onclick="closeTestResults()" style="background: none; border: none; cursor: pointer; font-size: 1.2em; color: #666;">✕</button>
                                </div>
                                <div id="testResultsContent"></div>
                            </div>
                            <div style="margin-top: 10px; font-size: 0.85em; color: #666;">
                                <strong>예시:</strong><br>
                                • AI OR ChatGPT OR GPT-4<br>
                                • (Artificial Intelligence) AND (Machine Learning)<br>
                                • Twice OR SAF OR (Methanol AND Ship)
                            </div>
                        </div>
                    </div>

                    <div class="section">
                        <h2>⏰ 스케줄 설정</h2>
                        <div class="env-grid" id="scheduleSettings"></div>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            let originalKeywords = '';

            function checkAuth() {
                const token = sessionStorage.getItem('admin_token');
                if (!token) {
                    window.location.href = '/admin/login';
                    return false;
                }
                return token;
            }

            function logout() {
                sessionStorage.removeItem('admin_token');
                window.location.href = '/admin/login';
            }

            function createEnvItem(label, value, description = '') {
                const isSet = value && value !== '(설정되지 않음)';
                return `
                    <div class="env-item">
                        <div class="env-label">
                            <span class="status-indicator ${isSet ? 'status-ok' : 'status-error'}"></span>
                            ${label}
                        </div>
                        <div class="env-value">${value || '(설정되지 않음)'}</div>
                        ${description ? `<div style="font-size: 0.8em; color: #666; margin-top: 5px;">${description}</div>` : ''}
                    </div>
                `;
            }

            async function loadSettings() {
                const token = checkAuth();
                if (!token) return;
                
                try {
                    const response = await fetch('/admin/api/env', {
                        headers: { 'Authorization': `Bearer ${token}` }
                    });
                    
                    if (!response.ok) {
                        if (response.status === 401) {
                            logout();
                            return;
                        }
                        throw new Error('설정을 불러올 수 없습니다');
                    }
                    
                    const data = await response.json();
                    
                    // 이메일 설정
                    document.getElementById('emailSettings').innerHTML = 
                        createEnvItem('SMTP 호스트', data.SMTP_HOST, 'SMTP 서버 주소') +
                        createEnvItem('SMTP 포트', data.SMTP_PORT, 'SMTP 서버 포트') +
                        createEnvItem('발신자 이메일', data.SMTP_USER, '이메일 발송 계정') +
                        createEnvItem('이메일 비밀번호', data.SMTP_PASS, '앱 비밀번호 또는 계정 비밀번호') +
                        createEnvItem('수신자 이메일', data.EMAIL_TO, '뉴스 요약을 받을 이메일');
                    
                    // 텔레그램 설정
                    document.getElementById('telegramSettings').innerHTML = 
                        createEnvItem('봇 토큰', data.TG_TOKEN, '텔레그램 봇 API 토큰') +
                        createEnvItem('채팅 ID', data.TG_CHAT, '메시지를 받을 채팅 ID');
                    
                    // API 키 설정
                    document.getElementById('apiSettings').innerHTML =
                        createEnvItem('NewsAPI 키', data.NEWS_API_KEY, '뉴스 수집용 API 키') +
                        createEnvItem('Gemini API 키', data.GEMINI_API_KEY, 'Google Gemini API 키') +
                        createEnvItem('Perplexity API 키', data.PERPLEXITY_API_KEY, 'Perplexity Sonar API 키');

                    // AI Provider 설정
                    const aiProvider = data.AI_PROVIDER || 'gemini';
                    document.getElementById('aiProviderSelect').value = aiProvider;
                    
                    // 스케줄 설정
                    document.getElementById('scheduleSettings').innerHTML =
                        createEnvItem('크론 시간', data.CRON_TIME, '실행 시간 (분 시간 형식)') +
                        createEnvItem('관리자 비밀번호', data.ADMIN_PASSWORD ? '설정됨' : '(기본값)', '이 설정 페이지 접근용');

                    // 뉴스 검색 키워드 표시
                    originalKeywords = data.NEWS_KEYWORDS || '';
                    document.getElementById('keywordsInput').value = originalKeywords;

                    document.getElementById('loadingMessage').style.display = 'none';
                    document.getElementById('settingsContent').style.display = 'block';

                } catch (error) {
                    document.getElementById('loadingMessage').innerHTML = '❌ 설정 로드 실패: ' + error.message;
                }
            }

            function resetKeywords() {
                document.getElementById('keywordsInput').value = originalKeywords;
                showStatusMessage('🔄 키워드가 원래 값으로 복원되었습니다', 'info', 3000);
            }

            async function updateKeywords() {
                const token = checkAuth();
                if (!token) return;

                const keywords = document.getElementById('keywordsInput').value.trim();
                if (!keywords) {
                    showStatusMessage('⚠️ 키워드를 입력해주세요', 'error', 3000);
                    return;
                }

                showStatusMessage('💾 키워드 저장 중...', 'info');

                try {
                    const response = await fetch('/admin/api/update-keywords', {
                        method: 'POST',
                        headers: {
                            'Authorization': `Bearer ${token}`,
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ keywords: keywords })
                    });

                    const result = await response.json();

                    if (response.ok && result.success) {
                        originalKeywords = keywords;
                        showStatusMessage(`✅ ${result.message}`, 'success', 5000);
                    } else {
                        showStatusMessage(`❌ 저장 실패: ${result.message || '알 수 없는 오류'}`, 'error', 5000);
                    }
                } catch (error) {
                    showStatusMessage(`❌ 네트워크 오류: ${error.message}`, 'error', 5000);
                }
            }

            function closeTestResults() {
                document.getElementById('testResults').style.display = 'none';
            }

            async function updateAIProvider() {
                const token = checkAuth();
                if (!token) return;

                const aiProvider = document.getElementById('aiProviderSelect').value;

                showStatusMessage('💾 AI Provider 저장 중...', 'info');

                try {
                    const response = await fetch('/admin/api/update-ai-provider', {
                        method: 'POST',
                        headers: {
                            'Authorization': `Bearer ${token}`,
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ ai_provider: aiProvider })
                    });

                    const result = await response.json();

                    if (response.ok && result.success) {
                        showStatusMessage(`✅ ${result.message}`, 'success', 5000);
                    } else {
                        showStatusMessage(`❌ 저장 실패: ${result.message || '알 수 없는 오류'}`, 'error', 5000);
                    }
                } catch (error) {
                    showStatusMessage(`❌ 네트워크 오류: ${error.message}`, 'error', 5000);
                }
            }

            async function testKeywords() {
                const token = checkAuth();
                if (!token) return;

                const keywords = document.getElementById('keywordsInput').value.trim();
                if (!keywords) {
                    showStatusMessage('⚠️ 키워드를 입력해주세요', 'error', 3000);
                    return;
                }

                showStatusMessage('🧪 키워드 테스트 중... (최대 30초 소요)', 'info');

                const testResultsDiv = document.getElementById('testResults');
                const testResultsContent = document.getElementById('testResultsContent');
                testResultsDiv.style.display = 'none';

                try {
                    const response = await fetch('/admin/api/test-keywords', {
                        method: 'POST',
                        headers: {
                            'Authorization': `Bearer ${token}`,
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ keywords: keywords })
                    });

                    const result = await response.json();

                    if (response.ok && result.success) {
                        showStatusMessage('✅ 테스트 완료!', 'success', 3000);

                        let html = `
                            <div style="margin-bottom: 10px;">
                                <strong>검색 키워드:</strong> <code style="background: white; padding: 2px 6px; border-radius: 3px;">${keywords}</code>
                            </div>
                            <div style="margin-bottom: 10px;">
                                <strong>수집된 기사 수:</strong> <span style="font-size: 1.2em; font-weight: bold; color: #27ae60;">${result.count}개</span>
                            </div>
                        `;

                        if (result.count > 0) {
                            html += `<div style="margin-top: 15px;">
                                <strong>샘플 기사 제목 (최대 5개):</strong>
                                <ul style="margin-top: 8px; padding-left: 20px;">`;

                            result.sample_titles.forEach(title => {
                                html += `<li style="margin-bottom: 5px;">${title}</li>`;
                            });

                            html += `</ul></div>`;
                        } else {
                            html += `<div style="margin-top: 10px; padding: 10px; background: #fff3cd; border-radius: 5px; color: #856404;">
                                ⚠️ 해당 키워드로 최근 48시간 내 기사를 찾을 수 없습니다. 다른 키워드를 시도해보세요.
                            </div>`;
                        }

                        testResultsContent.innerHTML = html;
                        testResultsDiv.style.display = 'block';
                        testResultsDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                    } else {
                        showStatusMessage(`❌ 테스트 실패: ${result.message || '알 수 없는 오류'}`, 'error', 5000);
                    }
                } catch (error) {
                    showStatusMessage(`❌ 네트워크 오류: ${error.message}`, 'error', 5000);
                }
            }
            
            function refreshData() {
                document.getElementById('loadingMessage').style.display = 'block';
                document.getElementById('settingsContent').style.display = 'none';
                document.getElementById('loadingMessage').innerHTML = '📡 환경변수 정보를 새로고침하는 중...';
                loadSettings();
            }
            
            function showStatusMessage(message, type = 'info', duration = 5000) {
                const statusMessage = document.getElementById('statusMessage');
                statusMessage.textContent = message;
                statusMessage.className = `status-message status-${type} show`;
                
                setTimeout(() => {
                    statusMessage.classList.remove('show');
                }, duration);
            }
            
            async function sendTelegramManual() {
                const token = checkAuth();
                if (!token) return;
                
                showStatusMessage('📱 텔레그램 메시지 전송 중...', 'info');
                
                try {
                    const response = await fetch('/admin/api/send-telegram', {
                        method: 'POST',
                        headers: { 'Authorization': `Bearer ${token}` }
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok && result.success) {
                        showStatusMessage(`✅ ${result.message}`, 'success', 7000);
                    } else {
                        showStatusMessage(`❌ 전송 실패: ${result.message || '알 수 없는 오류'}`, 'error', 7000);
                    }
                } catch (error) {
                    showStatusMessage(`❌ 네트워크 오류: ${error.message}`, 'error', 7000);
                }
            }
            
            async function sendFullManual() {
                const token = checkAuth();
                if (!token) return;
                
                if (!confirm('이메일과 텔레그램으로 동시에 전송하시겠습니까?')) {
                    return;
                }
                
                showStatusMessage('📧📱 전체 전송 중...', 'info');
                
                try {
                    const response = await fetch('/admin/api/send-full', {
                        method: 'POST',
                        headers: { 'Authorization': `Bearer ${token}` }
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok && result.success) {
                        showStatusMessage(`✅ ${result.message}`, 'success', 7000);
                    } else {
                        showStatusMessage(`❌ 전송 실패: ${result.message || '알 수 없는 오류'}`, 'error', 7000);
                    }
                } catch (error) {
                    showStatusMessage(`❌ 네트워크 오류: ${error.message}`, 'error', 7000);
                }
            }
            
            // 페이지 로드 시 설정 불러오기
            loadSettings();
        </script>
        
        <!-- 상태 메시지 알림 -->
        <div id="statusMessage" class="status-message"></div>
    </body>
    </html>
    """)

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
