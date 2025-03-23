import os
import requests
import json
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

# ✅ .env 로드
load_dotenv()

# ✅ 환경 변수
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
PPLX_API_KEY = os.getenv("PPLX_API_KEY")
NEWS_QUERY = os.getenv("NEWS_QUERY", "LLM OR ChatGPT OR Gemini OR Claude")

PPLX_API_URL = "https://api.perplexity.ai/chat/completions"
HEADERS = {
    "Authorization": f"Bearer {PPLX_API_KEY}",
    "Content-Type": "application/json"
}

KST = timezone(timedelta(hours=9))

# ✅ 로그 기록
def write_log(message):
    now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    with open("news_summary.log", "a", encoding="utf-8") as log_file:
        log_file.write(f"[{now_kst}] {message}\n")

write_log("✅ 뉴스 요약 시작")

# ✅ 24시간 이내 뉴스 가져오기
today = datetime.now(KST)
yesterday = today - timedelta(days=2)
from_date = yesterday.strftime("%Y-%m-%dT%H:%M:%SZ")
to_date = today.strftime("%Y-%m-%dT%H:%M:%SZ")

news_url = (
    f"https://newsapi.org/v2/everything?"
    f"q={NEWS_QUERY}&"
    f"language=en&"
    f"sortBy=popularity&"
    f"from={from_date}&to={to_date}&"
    f"apiKey={NEWS_API_KEY}"
)

news_response = requests.get(news_url)
news_data = news_response.json()

# ✅ 뉴스 원본 저장
raw_filename = f"news_{today.strftime('%Y-%m-%d')}.json"
with open(raw_filename, "w", encoding="utf-8") as f:
    json.dump(news_data, f, indent=4, ensure_ascii=False)
write_log(f"✅ 원본 뉴스 저장: {raw_filename}")

articles = news_data.get("articles", [])[:10]  # 최대 10개 기사

# ✅ Perplexity 요약 함수 (참조 제거)
def get_perplexity_summary(prompt, lang="en"):
    system_content = (
        "You are an expert AI news summarizer. Be precise and concise. "
        "DO NOT include any references like [1], [2], or citations."
        if lang == "en" else
        "당신은 AI 뉴스 요약가입니다. 핵심만 간결하게 요약해 주세요. "
        "참고번호나 출처 표시([1], [2] 등)는 절대 넣지 마세요."
    )
    payload = {
        "model": "sonar",
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 300,
        "temperature": 0.2,
        "top_p": 0.9,
        "stream": False
    }
    try:
        response = requests.post(PPLX_API_URL, json=payload, headers=HEADERS, timeout=30)
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        write_log(f"❌ Perplexity 요약 실패: {e}")
        return "요약 실패"

# ✅ 뉴스 1개 처리 (영/한 병렬 실행)
def summarize_article(article):
    title = article["title"]
    description = article.get("description", "")
    url_link = article["url"]
    full_content = f"Title: {title}\nDescription: {description}"

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_en = executor.submit(get_perplexity_summary, f"Summarize this news article in two sentences:\n{full_content}", "en")
        future_ko = executor.submit(get_perplexity_summary, f"다음 뉴스를 한국어로 두 문장으로 요약해 주세요:\n{full_content}", "ko")
        en_summary = future_en.result()
        ko_summary = future_ko.result()

    return {
        "title": title,
        "summary_en": en_summary,
        "summary_ko": ko_summary,
        "url": url_link
    }

# ✅ 전체 뉴스 병렬 요약
summarized_news = []
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = [executor.submit(summarize_article, article) for article in articles]
    for future in as_completed(futures):
        summarized_news.append(future.result())

# ✅ 결과 저장
summary_filename = f"summarized_news_{today.strftime('%Y-%m-%d')}.json"
with open(summary_filename, "w", encoding="utf-8") as f:
    json.dump(summarized_news, f, indent=4, ensure_ascii=False)

write_log(f"✅ 뉴스 요약 완료! 파일 저장: {summary_filename}")
print(f"✅ 뉴스 요약 완료! 파일 저장: {summary_filename}")
