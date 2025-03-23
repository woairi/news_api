import feedparser
import requests
import json
from datetime import datetime, timedelta
import pytz

# ✅ Perplexity API 설정
PPLX_API_URL = "https://api.perplexity.ai/chat/completions"
PPLX_API_KEY = "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"
HEADERS = {
    "Authorization": f"Bearer {PPLX_API_KEY}",
    "Content-Type": "application/json"
}

# ✅ Google News RSS
rss_url = "https://news.google.com/rss/search?q=AI+OR+LLM+OR+ChatGPT+OR+Gemini+OR+Claude&hl=ko&gl=KR&ceid=KR:ko"
feed = feedparser.parse(rss_url)

# ✅ 시간 필터 (24시간 내)
KST = pytz.timezone('Asia/Seoul')
now = datetime.now(KST)
yesterday = now - timedelta(days=1)

articles = []
for entry in feed.entries:
    try:
        published_dt = datetime(*entry.published_parsed[:6], tzinfo=pytz.utc).astimezone(KST)
    except:
        continue
    if yesterday <= published_dt <= now:
        articles.append({
            "title": entry.title,
            "description": entry.summary,
            "url": entry.link,
            "published": published_dt.strftime("%Y-%m-%d %H:%M")
        })

print(f"✅ 수집 기사 수: {len(articles)}개")

# ✅ 중요도 평가 함수
def get_importance_score(title, description):
    content = f"제목: {title}\n내용: {description[:2000]}\n이 뉴스의 중요도를 1~10점으로 숫자만 반환해 주세요. 이유 설명 없이 숫자만 주세요."
    payload = {
        "model": "sonar",
        "messages": [
            {"role": "system", "content": "너는 엄격한 AI 뉴스 평가자야. 중요한 뉴스면 10점, 덜 중요하면 1점 줘. 구별이 가게 점수를 줘."},
            {"role": "user", "content": content}
        ],
        "max_tokens": 10,
        "temperature": 0.2,
        "top_p": 0.9,
        "stream": False
    }
    try:
        response = requests.post(PPLX_API_URL, json=payload, headers=HEADERS, timeout=30)
        score_str = response.json()["choices"][0]["message"]["content"].strip()
        score = int(''.join(filter(str.isdigit, score_str)))  # 숫자만 추출
    except Exception as e:
        print(f"❌ 중요도 평가 실패: {e}")
        score = 0
    return score

# ✅ 기사별 중요도 평가
for article in articles:
    print(f"🎯 중요도 평가 중: {article['title']}")
    article["importance"] = get_importance_score(article["title"], article["description"])
    print(f"➡️ 중요도: {article['importance']}점")

# ✅ 중요도 순으로 정렬 후 상위 10개 뽑기
articles.sort(key=lambda x: x["importance"], reverse=True)
top_10 = articles[:10]

# ✅ 결과 저장
output_file = f"important_news_{now.strftime('%Y-%m-%d')}.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(top_10, f, indent=4, ensure_ascii=False)

print(f"✅ 중요도 상위 10개 기사 저장 완료 → {output_file}")

