from fastapi import FastAPI, Request, HTTPException
from fastapi.templating import Jinja2Templates
import json
import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from fastapi.responses import JSONResponse
import subprocess

# ✅ .env 로드
load_dotenv()

app = FastAPI()

# ✅ Jinja2 템플릿 설정
templates = Jinja2Templates(directory="templates")

# ✅ 환경변수
SERVER_PORT = int(os.getenv("SERVER_PORT", 8001))
KST = timezone(timedelta(hours=9))

# ✅ 로그 기록 함수
def write_log(message):
    now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    with open("news_api.log", "a", encoding="utf-8") as log_file:
        log_file.write(f"[{now_kst}] {message}\n")

# ✅ 특정 날짜의 뉴스 데이터 불러오기
def load_news_by_date(date_str: str):
    filename = f"summarized_news_{date_str}.json"
    if not os.path.exists(filename):
        write_log(f"❌ No news data for {date_str}")
        raise HTTPException(status_code=404, detail=f"No news data available for {date_str}.")
    with open(filename, "r", encoding="utf-8") as f:
        write_log(f"✅ Loaded news data for {date_str}")
        return json.load(f)

# ✅ 요청 로그 기록 (IP, User-Agent)
def log_request(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get('user-agent', 'unknown')
    write_log(f"Request from {client_ip}, User-Agent: {user_agent}")

# ✅ JSON API (날짜별 제공)
@app.get("/news/{date}")
def get_news_by_date(date: str, request: Request):
    log_request(request)
    news = load_news_by_date(date)
    return {"date": date, "news": news}

# ✅ 웹 페이지 출력 (날짜별 뉴스 조회)
@app.get("/")
def read_news(request: Request, date: str = None):
    if not date:
        date = datetime.now(KST).strftime("%Y-%m-%d")  # KST 기준 오늘 날짜
    try:
        news = load_news_by_date(date)
    except HTTPException:
        news = []
    log_request(request)
    write_log(f"✅ HTML view loaded for date: {date}")
    return templates.TemplateResponse("news.html", {
        "request": request,
        "news": news,
        "selected_date": date,
        "keyword": ""
    })

# ✅ 필터 검색 (키워드로 뉴스 검색)
@app.get("/filter")
def filter_news(request: Request, date: str, keyword: str):
    try:
        news = load_news_by_date(date)
    except HTTPException:
        news = []

    filtered_news = [
        item for item in news
        if keyword.lower() in item["title"].lower()
        or keyword.lower() in item.get("summary_en", "").lower()
        or keyword in item.get("summary_ko", "")
    ]

    log_request(request)
    write_log(f"✅ Filter applied: date={date}, keyword={keyword}")
    return templates.TemplateResponse("news.html", {
        "request": request,
        "news": filtered_news,
        "selected_date": date,
        "keyword": keyword
    })

# ✅ 필텔레그램 보내기
@app.post("/send_telegram")
async def send_telegram():
    try:
        result = subprocess.run(["python", "telegram_sender.py"], capture_output=True, text=True)
        if result.returncode != 0:
            return JSONResponse(status_code=500, content={"message": "전송 실패", "error": result.stderr})
        return JSONResponse(status_code=200, content={"message": "전송 성공"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": f"오류 발생: {e}"})

# ✅ 서버 실행
if __name__ == "__main__":
    import uvicorn
    write_log(f"✅ FastAPI 서버 시작 on port {SERVER_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)
