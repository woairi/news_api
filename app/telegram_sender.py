import os
import requests
import json
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# ✅ .env 로드
load_dotenv()

# ✅ 환경변수
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
KST = timezone(timedelta(hours=9))

# ✅ 로그 기록 함수
def write_log(message):
    now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    with open("telegram_sender.log", "a", encoding="utf-8") as log_file:
        log_file.write(f"[{now_kst}] {message}\n")

write_log("✅ 텔레그램 전송 시작")

# ✅ 오늘 날짜 기준 요약 파일 읽기
today = datetime.now(KST).strftime("%Y-%m-%d")
summary_file = f"summarized_news_{today}.json"

if not os.path.exists(summary_file):
    write_log(f"❌ 요약 파일 없음: {summary_file}")
    print(f"❌ 요약 파일 없음: {summary_file}")
    exit()

with open(summary_file, "r", encoding="utf-8") as f:
    summarized_news = json.load(f)

# ✅ 텔레그램 전송 함수
def send_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        write_log("✅ 텔레그램 전송 성공")
    else:
        write_log(f"❌ 텔레그램 전송 실패: {response.text}")

# ✅ 전체 기사 하나로 묶기 (한글 요약만)
message = f"*📅 {today} AI 뉴스 요약 (한글)*\n\n"
for idx, news in enumerate(summarized_news, 1):
    message += f"*{idx}. {news['title']}*\n"
    message += f"🇰🇷 {news['summary_ko']}\n"
    message += f"🔗 [기사 보기]({news['url']})\n\n"

# ✅ 최종 전송
send_message(message)
print("✅ 텔레그램 전송 완료 (한글 요약만, 하나의 메시지로)")
