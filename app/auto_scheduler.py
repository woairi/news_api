import os
import schedule
import time
import subprocess
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import requests

load_dotenv()
SEND_TIME = os.getenv("SEND_TIME", "07:00")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
KST = timezone(timedelta(hours=9))

# ✅ 텔레그램 알림 전송 함수
def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": f"🚨 [AI 뉴스 시스템 에러 발생] 🚨\n{message}",
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        write_log(f"❌ 텔레그램 알림 실패: {e}")

# ✅ 로그 기록
def write_log(message):
    now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    with open("auto_scheduler.log", "a", encoding="utf-8") as log_file:
        log_file.write(f"[{now_kst}] {message}\n")

write_log(f"✅ 스케줄러 시작 - 매일 {SEND_TIME} KST 실행")

# ✅ 실행 작업 (뉴스 요약 + 텔레그램 전송)
def job():
    try:
        write_log("✅ 뉴스 요약 시작")
        result1 = subprocess.run(["python", "news_summary.py"], capture_output=True, text=True)
        write_log(result1.stdout)
        write_log(result1.stderr)
        if result1.returncode != 0:
            raise Exception("news_summary.py 실행 실패")

        write_log("✅ 텔레그램 전송 시작")
        result2 = subprocess.run(["python", "telegram_sender.py"], capture_output=True, text=True)
        write_log(result2.stdout)
        write_log(result2.stderr)
        if result2.returncode != 0:
            raise Exception("telegram_sender.py 실행 실패")

        write_log("✅ 오늘 작업 완료\n")

    except Exception as e:
        error_message = f"❌ 스케줄러 작업 실패: {e}"
        write_log(error_message)
        send_telegram_alert(error_message)

# ✅ 스케줄 등록
schedule.every().day.at(SEND_TIME).do(job)

while True:
    schedule.run_pending()
    time.sleep(30)


