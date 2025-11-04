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
from bs4 import BeautifulSoup
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional

load_dotenv()

DATACENTER_CHANNELS = {
    "https://www.datacenterdynamics.com/en/news/?term=the-energy-and-sustainability-channel": "Energy & Sustainability",
    "https://www.datacenterdynamics.com/en/news/?term=the-investment-and-markets-channel": "Investment & Markets",
    "https://www.datacenterdynamics.com/en/news/?term=the-cloud-and-hybrid-channel": "Cloud & Hybrid",
}

DATACENTER_URLS = list(DATACENTER_CHANNELS.keys())

CATEGORY_AI_NEWS = "ai_news"
CATEGORY_DATACENTER = "datacenterdynamics"

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

def generate_summary(
    articles: List[Dict],
    gemini_key: str,
    intro_text: str = "최근 48시간 인기 AI 기사 목록입니다",
    summary_label: str = "AI 기사",
    limit: int = 10,
) -> str:
    """Gemini API를 사용하여 한국어 요약 생성"""
    if not articles:
        return "📭 요약할 기사가 없습니다."

    selected = articles[:limit]
    bullet_lines = []
    for idx, article in enumerate(selected):
        title = article.get('title') or f"제목 미확인 {idx + 1}"
        url = article.get('url') or article.get('link')
        if not url:
            continue
        source_info = article.get('source')
        if isinstance(source_info, dict):
            source_name = source_info.get('name')
        else:
            source_name = None
        source_name = source_name or article.get('source_name') or "출처 미상"
        bullet_lines.append(f"- {title} ({source_name}) - {url}")

    if not bullet_lines:
        return "📭 요약할 기사가 없습니다."

    bullets = "\n".join(bullet_lines)

    client = genai.Client(api_key=gemini_key)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=f"""다음은 {intro_text}:

{bullets}

각 기사를 다음 형식으로 한국어 요약하세요:

📰 [기사 번호]. [기사 제목] ([언론사])
📝 [3문장 한국어 요약]
🔗 [원문 링크]

각 기사 사이에 빈 줄을 추가하여 구분하세요. 총 {len(selected)}개 {summary_label} 기사를 요약하세요."""
    )
    return response.text.strip()


def parse_datacenter_datetime(raw_value: Optional[str]) -> Optional[dt.datetime]:
    """DatacenterDynamics 날짜 문자열 파싱"""
    if not raw_value:
        return None
    raw_value = raw_value.strip()
    # iso8601 보정
    if raw_value.endswith("Z"):
        raw_value = raw_value[:-1] + "+00:00"
    try:
        return dt.datetime.fromisoformat(raw_value)
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(raw_value)
        if parsed:
            return parsed
    except (TypeError, ValueError):
        pass
    for fmt in [
        "%B %d, %Y",
        "%B %d, %Y %H:%M",
        "%d %B %Y",
        "%d %B %Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
    ]:
        try:
            return dt.datetime.strptime(raw_value, fmt)
        except ValueError:
            continue
    return None


def fetch_article_metadata(url: str) -> Dict[str, Optional[str]]:
    """기사 본문에서 메타데이터 추출"""
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    title = None
    title_tag = soup.find("meta", attrs={"property": "og:title"})
    if title_tag and title_tag.get("content"):
        title = title_tag["content"].strip()
    if not title:
        h1_tag = soup.find("h1")
        if h1_tag:
            title = h1_tag.get_text(strip=True)

    description = None
    desc_tag = soup.find("meta", attrs={"name": "description"})
    if desc_tag and desc_tag.get("content"):
        description = desc_tag["content"].strip()

    published_raw = None
    meta_time = soup.find("meta", attrs={"property": "article:published_time"})
    if meta_time and meta_time.get("content"):
        published_raw = meta_time["content"].strip()
    if not published_raw:
        time_tag = soup.find("time")
        if time_tag:
            published_raw = time_tag.get("datetime") or time_tag.get_text(strip=True)

    published_dt = parse_datacenter_datetime(published_raw)
    if published_dt and published_dt.tzinfo is None:
        published_dt = published_dt.replace(tzinfo=dt.timezone.utc)

    return {
        "title": title,
        "description": description,
        "published_at": published_dt.isoformat() if published_dt else None,
    }


def extract_datacenter_articles(html: str) -> List[Dict]:
    """DatacenterDynamics 목록 페이지에서 기사 후보 추출"""
    soup = BeautifulSoup(html, "html.parser")
    articles = []
    seen_urls = set()

    def register_article(title: Optional[str], url: Optional[str], published_raw: Optional[str], description: Optional[str]):
        if not url:
            return
        absolute_url = urllib.parse.urljoin("https://www.datacenterdynamics.com", url)
        if absolute_url in seen_urls:
            return
        seen_urls.add(absolute_url)
        published_dt = parse_datacenter_datetime(published_raw)
        if published_dt and published_dt.tzinfo is None:
            published_dt = published_dt.replace(tzinfo=dt.timezone.utc)
        articles.append({
            "title": (title or "제목 미확인").strip(),
            "url": absolute_url,
            "published_at": published_dt.isoformat() if published_dt else None,
            "source_name": "DatacenterDynamics",
            "snippet": description.strip() if description else None,
        })

    # JSON-LD 우선 사용
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        script_text = script.string
        if not script_text:
            continue
        try:
            data = json.loads(script_text)
        except json.JSONDecodeError:
            continue

        stack = [data]
        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                type_value = current.get("@type")
                if isinstance(type_value, list):
                    type_candidates = [str(t) for t in type_value]
                else:
                    type_candidates = [str(type_value)] if type_value else []

                if any("Article" in t for t in type_candidates):
                    candidate_url = current.get("url") or (
                        current.get("mainEntityOfPage", {})).get("@id")
                    register_article(
                        current.get("headline") or current.get("name"),
                        candidate_url,
                        current.get("datePublished") or current.get("dateModified"),
                        current.get("description"),
                    )
                else:
                    for value in current.values():
                        if isinstance(value, (dict, list)):
                            stack.append(value)
            elif isinstance(current, list):
                stack.extend(current)

    # HTML 구조 파싱 (JSON-LD 누락 대비)
    if not articles:
        for container in soup.find_all(["article", "div", "li"]):
            link_tag = container.find("a", href=True)
            if not link_tag:
                continue
            href = link_tag["href"]
            if "/en/news/" not in href:
                continue
            title = link_tag.get_text(strip=True)
            time_tag = container.find("time")
            published_raw = None
            if time_tag:
                published_raw = time_tag.get("datetime") or time_tag.get_text(strip=True)
            description = None
            para = container.find("p")
            if para:
                description = para.get_text(strip=True)
            register_article(title, href, published_raw, description)

    return articles


def fetch_datacenter_articles() -> List[Dict]:
    """DatacenterDynamics 채널별 어제 기사 수집"""
    target_date = (dt.datetime.utcnow() - dt.timedelta(days=1)).date()
    collected: Dict[str, Dict] = {}

    for url in DATACENTER_URLS:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        candidates = extract_datacenter_articles(response.text)
        channel_name = DATACENTER_CHANNELS.get(url, "DatacenterDynamics")

        for candidate in candidates:
            published_iso = candidate.get("published_at")
            published_dt = parse_datacenter_datetime(published_iso) if published_iso else None
            if not published_dt and candidate.get("url"):
                metadata = fetch_article_metadata(candidate["url"])
                candidate["published_at"] = metadata.get("published_at")
                if metadata.get("title") and metadata["title"] != "제목 미확인":
                    candidate["title"] = metadata["title"]
                if not candidate.get("snippet") and metadata.get("description"):
                    candidate["snippet"] = metadata["description"]
                published_dt = parse_datacenter_datetime(candidate.get("published_at")) if candidate.get("published_at") else None

            if not published_dt:
                continue
            published_date = published_dt.date()
            if published_date != target_date:
                continue

            candidate["published_at"] = published_dt.isoformat()
            candidate["source"] = {"name": "DatacenterDynamics"}
            candidate["channel"] = channel_name
            collected[candidate["url"]] = candidate

    articles = list(collected.values())
    articles.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    return articles

def ensure_summary_table(cursor: sqlite3.Cursor) -> None:
    """요약 저장 테이블과 스키마를 확보"""
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
    columns = {row[1] for row in cursor.execute('PRAGMA table_info(summaries)')}
    if 'category' not in columns:
        cursor.execute("ALTER TABLE summaries ADD COLUMN category TEXT NOT NULL DEFAULT 'ai_news'")
    else:
        cursor.execute("UPDATE summaries SET category = 'ai_news' WHERE category IS NULL OR TRIM(category) = ''")

    # 중복 레코드 정리: 동일한 날짜/카테고리의 최신(id 최대) 레코드만 유지
    cursor.execute('''
        DELETE FROM summaries
        WHERE id NOT IN (
            SELECT MAX(id) FROM summaries GROUP BY date, category
        )
    ''')
    cursor.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_summaries_date_category
        ON summaries(date, category)
    ''')


def save_summary_to_db(date, summary_text, articles_list, category: str = CATEGORY_AI_NEWS):
    """데이터베이스에 요약 저장"""
    db_path = '/app/data/news_summaries.db' if os.path.exists('/app/data') else 'news_summaries.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    ensure_summary_table(cursor)
    cursor.execute('''
        INSERT INTO summaries (date, summary, articles_json, category)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(date, category) DO UPDATE SET
            summary=excluded.summary,
            articles_json=excluded.articles_json,
            created_at=CURRENT_TIMESTAMP
    ''', (date, summary_text, json.dumps(articles_list, ensure_ascii=False), category))
    conn.commit()
    conn.close()

def send_email(summary_map: Dict[str, str], env_vars):
    """이메일 전송"""
    sections = []
    ai_summary = summary_map.get(CATEGORY_AI_NEWS)
    if ai_summary:
        sections.append(ai_summary)

    dc_summary = summary_map.get(CATEGORY_DATACENTER)
    if dc_summary:
        sections.append("📊 DatacenterDynamics 요약\n\n" + dc_summary)

    if not sections:
        return

    body = "\n\n\n".join(sections)
    email_content = f"""🌐 웹사이트에서 보기: https://news.hyung.life

{body}

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

def build_telegram_message(title: str, summary: str) -> str:
    """텔레그램 메시지 포맷"""
    heading = f"{title}\n\n" if title else ""
    return f"""🌐 웹사이트에서 보기: https://news.hyung.life

{heading}{summary}

---
📱 언제든지 웹사이트에서 지난 요약들을 확인할 수 있습니다.
🔗 https://news.hyung.life"""


def send_telegram(summary_map: Dict[str, str], env_vars):
    """텔레그램 메시지 전송"""
    tg_url = f"https://api.telegram.org/bot{env_vars['TG_TOKEN']}/sendMessage"
    max_length = 4096

    message_order = [
        (CATEGORY_AI_NEWS, "🤖 AI 뉴스 요약"),
        (CATEGORY_DATACENTER, "📊 DatacenterDynamics 요약"),
    ]

    last_response = None
    for category, title in message_order:
        summary = summary_map.get(category)
        if not summary:
            continue
        telegram_message = build_telegram_message(title, summary)
        if len(telegram_message) <= max_length:
            payload = {
                'chat_id': env_vars['TG_CHAT'],
                'text': telegram_message,
                'parse_mode': 'HTML'
            }
            response = requests.post(tg_url, json=payload, timeout=60)
            response.raise_for_status()
            last_response = response
        else:
            parts = [telegram_message[i:i+max_length] for i in range(0, len(telegram_message), max_length)]
            for part in parts:
                payload = {
                    'chat_id': env_vars['TG_CHAT'],
                    'text': part,
                    'parse_mode': 'HTML'
                }
                response = requests.post(tg_url, json=payload, timeout=60)
                response.raise_for_status()
                last_response = response

    return last_response

def run_news_bot(send_email_flag=True, send_telegram_flag=True):
    """메인 뉴스봇 실행 함수"""
    try:
        # 환경변수 로드
        env_vars = get_env_vars()
        
        # 뉴스 수집
        print("[1/7] AI 뉴스 수집 중...")
        ai_articles = fetch_news(env_vars['NEWS_KEY'])
        if not ai_articles:
            raise ValueError("수집된 AI 뉴스 기사가 없습니다")

        # AI 요약 생성
        print("[2/7] AI 요약 생성 중...")
        ai_summary = generate_summary(
            ai_articles,
            env_vars['GEMINI_KEY'],
            intro_text="최근 48시간 인기 AI 기사 목록입니다",
            summary_label="AI 뉴스",
        )

        # DatacenterDynamics 수집
        print("[3/7] DatacenterDynamics 기사 수집 중...")
        dc_articles = []
        dc_summary = None
        try:
            dc_articles = fetch_datacenter_articles()
            print(f"[정보] DatacenterDynamics 기사 {len(dc_articles)}건 수집")
        except Exception as fetch_error:
            print(f"[경고] DatacenterDynamics 수집 실패: {fetch_error}")

        # DatacenterDynamics 요약 생성
        print("[4/7] DatacenterDynamics 요약 생성 중...")
        if dc_articles:
            dc_summary = generate_summary(
                dc_articles,
                env_vars['GEMINI_KEY'],
                intro_text="DatacenterDynamics에서 어제 발행된 데이터센터 관련 기사 목록입니다",
                summary_label="DatacenterDynamics",
            )
        else:
            dc_summary = "📭 어제 날짜에 요약할 DatacenterDynamics 기사가 없습니다."

        # 데이터베이스 저장
        print("[5/7] 데이터베이스 저장 중...")
        today = dt.datetime.now().strftime("%Y-%m-%d")
        save_summary_to_db(today, ai_summary, ai_articles[:10], category=CATEGORY_AI_NEWS)
        save_summary_to_db(today, dc_summary, dc_articles[:10], category=CATEGORY_DATACENTER)

        summary_map = {
            CATEGORY_AI_NEWS: ai_summary,
            CATEGORY_DATACENTER: dc_summary,
        }

        # 이메일 전송
        if send_email_flag:
            print("[6/7] 이메일 전송 중...")
            send_email(summary_map, env_vars)
            print(f"[메일] 전송 완료 → {env_vars['EMAIL_TO']}")
        
        # 텔레그램 전송
        if send_telegram_flag:
            print("[7/7] 텔레그램 전송 중...")
            resp = send_telegram(summary_map, env_vars)
            if resp is not None:
                print("[텔레그램] 전송 완료:", resp.status_code)
        
        return {
            'success': True,
            'message': '뉴스 수집 및 전송이 완료되었습니다',
            'summary': ai_summary,
            'articles_count': len(ai_articles),
            'datacenter_articles_count': len(dc_articles),
            'datacenter_summary': dc_summary,
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
