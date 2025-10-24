#!/usr/bin/env python3
"""AI 뉴스 요약 후 이메일·텔레그램 발송 스크립트"""
import os, requests, smtplib, datetime as dt
from email.mime.text import MIMEText
from email.header import Header
from dotenv import load_dotenv
import urllib.parse
import json
import google.genai as genai
import sqlite3

load_dotenv()

def get_env_vars():
    """환경변수 로드 및 검증"""
    env_vars = {
        'NEWS_KEY': os.getenv("NEWS_API_KEY"),
        'GEMINI_KEY': os.getenv("GEMINI_API_KEY"),
        'TG_TOKEN': os.getenv("TG_TOKEN"),
        'TG_CHAT': os.getenv("TG_CHAT"),
        'SMTP_HOST': os.getenv("SMTP_HOST"),
        'SMTP_PORT': int(os.getenv("SMTP_PORT", 587)),
        'SMTP_USER': os.getenv("SMTP_USER"),
        'SMTP_PASS': os.getenv("SMTP_PASS"),
        'EMAIL_TO': os.getenv("EMAIL_TO")
    }
    
    required_vars = ['NEWS_KEY', 'GEMINI_KEY', 'TG_TOKEN', 'TG_CHAT', 'SMTP_USER', 'SMTP_PASS', 'EMAIL_TO']
    missing_vars = [var for var in required_vars if not env_vars[var]]
    
    if missing_vars:
        raise ValueError(f"[env] 다음 환경변수가 설정되지 않았습니다: {', '.join(missing_vars)}")
    
    return env_vars

def fetch_news(news_key):
    """뉴스 API에서 AI 관련 뉴스 수집"""
    from_date = (dt.datetime.utcnow() - dt.timedelta(hours=48)).strftime("%Y-%m-%d")
    news_url = (
        "https://newsapi.org/v2/everything?q=AI%20AND%20(NVIDIA%20OR%20OpenAI%20OR%20Gemini%20OR%20LLM)"
        f"&from={from_date}&sortBy=popularity&pageSize=20&language=en&apiKey={news_key}"
    )
    response = requests.get(news_url, timeout=30)
    response.raise_for_status()
    return response.json().get("articles", [])

def generate_summary(articles, gemini_key):
    """Gemini API를 사용하여 한국어 요약 생성"""
    bullets = "\n".join(f"- {a['title']} ({a['source']['name']}) - {a['url']}" for a in articles[:10])
    
    client = genai.Client(api_key=gemini_key)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"""다음은 최근 48시간 인기 AI 기사 목록입니다:

{bullets}

각 기사를 다음 형식으로 한국어 요약하여 총 10개 기사 요약을 작성하세요:

📰 [기사 번호]. [기사 제목] ([언론사])
📝 [3문장 한국어 요약]
🔗 [원문 링크]

각 기사 사이에 빈 줄을 추가하여 구분하세요."""
    )
    return response.text.strip()

def save_summary_to_db(date, summary_text, articles_list):
    """데이터베이스에 요약 저장"""
    db_path = '/app/data/news_summaries.db' if os.path.exists('/app/data') else 'news_summaries.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            summary TEXT NOT NULL,
            articles_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        INSERT OR REPLACE INTO summaries (date, summary, articles_json)
        VALUES (?, ?, ?)
    ''', (date, summary_text, json.dumps(articles_list, ensure_ascii=False)))
    conn.commit()
    conn.close()

def send_email(summary, env_vars):
    """이메일 전송"""
    email_content = f"""🌐 웹사이트에서 보기: https://news.hyung.life

{summary}

---
📱 언제든지 웹사이트에서 지난 요약들을 확인할 수 있습니다.
🔗 https://news.hyung.life"""

    msg = MIMEText(email_content, "plain", "utf-8")
    msg["Subject"] = Header("📬 AI 뉴스 요약 (48h)", "utf-8")
    msg["From"] = env_vars['SMTP_USER']
    msg["To"] = env_vars['EMAIL_TO']
    
    with smtplib.SMTP(env_vars['SMTP_HOST'], env_vars['SMTP_PORT']) as smtp:
        smtp.starttls()
        smtp.login(env_vars['SMTP_USER'], env_vars['SMTP_PASS'])
        smtp.sendmail(env_vars['SMTP_USER'], [env_vars['EMAIL_TO']], msg.as_string())

def send_telegram(summary, env_vars):
    """텔레그램 메시지 전송"""
    # 웹사이트 링크를 포함한 메시지 생성
    telegram_message = f"""🌐 웹사이트에서 보기: https://news.hyung.life

{summary}

---
📱 언제든지 웹사이트에서 지난 요약들을 확인할 수 있습니다.
🔗 https://news.hyung.life"""
    
    tg_url = f"https://api.telegram.org/bot{env_vars['TG_TOKEN']}/sendMessage"
    payload = {
        'chat_id': env_vars['TG_CHAT'],
        'text': telegram_message,
        'parse_mode': 'HTML'
    }
    response = requests.post(tg_url, json=payload, timeout=30)
    response.raise_for_status()
    return response

def run_news_bot(send_email_flag=True, send_telegram_flag=True):
    """메인 뉴스봇 실행 함수"""
    try:
        # 환경변수 로드
        env_vars = get_env_vars()
        
        # 뉴스 수집
        print("[1/5] 뉴스 수집 중...")
        articles = fetch_news(env_vars['NEWS_KEY'])
        if not articles:
            raise ValueError("수집된 뉴스 기사가 없습니다")
        
        # 요약 생성
        print("[2/5] AI 요약 생성 중...")
        summary = generate_summary(articles, env_vars['GEMINI_KEY'])
        
        # 데이터베이스 저장
        print("[3/5] 데이터베이스 저장 중...")
        today = dt.datetime.now().strftime("%Y-%m-%d")
        save_summary_to_db(today, summary, articles[:10])
        
        # 이메일 전송
        if send_email_flag:
            print("[4/5] 이메일 전송 중...")
            send_email(summary, env_vars)
            print(f"[메일] 전송 완료 → {env_vars['EMAIL_TO']}")
        
        # 텔레그램 전송
        if send_telegram_flag:
            print("[5/5] 텔레그램 전송 중...")
            resp = send_telegram(summary, env_vars)
            print("[텔레그램] 전송 완료:", resp.status_code)
        
        return {
            'success': True,
            'message': '뉴스 수집 및 전송이 완료되었습니다',
            'summary': summary,
            'articles_count': len(articles)
        }
        
    except Exception as e:
        error_msg = f"오류 발생: {str(e)}"
        print(f"[오류] {error_msg}")
        return {
            'success': False,
            'message': error_msg
        }

# 스크립트 직접 실행시에만 실행
if __name__ == "__main__":

    # 기존 스크립트 로직 실행
    result = run_news_bot()
    if not result['success']:
        exit(1)
