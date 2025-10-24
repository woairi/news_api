FROM python:3.11-slim

# 시스템 타임존을 Asia/Seoul 로 설정
ENV TZ=Asia/Seoul
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# dependency 설치
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# 소스 복사
COPY send_ai_news.py /app/send_ai_news.py
COPY web_app.py /app/web_app.py
COPY .env /app/.env

# 크론 설치
RUN apt-get update && apt-get install -y cron && rm -rf /var/lib/apt/lists/*

# 로그 파일 생성
RUN touch /var/log/cron.log

# 데이터베이스 디렉토리 생성
RUN mkdir -p /app/data

# 시작 스크립트 생성
RUN echo '#!/bin/bash\n\
cd /app\n\
\n\
# .env 파일에서 CRON_TIME 읽기 (기본값: 40 8)\n\
CRON_TIME=${CRON_TIME:-"40 8"}\n\
\n\
# 크론용 환경변수 파일 생성\n\
cat .env | grep -v \"^#\" | grep -v \"^$\" | sed \"s/#.*//\" | sed \"s/[[:space:]]*$//\" > /app/.env.clean\n\
\n\
# 환경변수를 포함한 크론 작업 설정\n\
echo "$CRON_TIME * * * cd /app && export $(cat /app/.env.clean | xargs) && /usr/local/bin/python3 /app/send_ai_news.py >> /var/log/cron.log 2>&1" > /etc/cron.d/news-cron\n\
chmod 0644 /etc/cron.d/news-cron\n\
crontab /etc/cron.d/news-cron\n\
\n\
echo "크론 작업이 $CRON_TIME 에 설정되었습니다."\n\
\n\
# 웹앱과 크론 서비스 시작\n\
python web_app.py &\n\
cron -f' > /app/start.sh && chmod +x /app/start.sh

# 컨테이너 시작 시 웹서비스와 크론 함께 실행
CMD ["/app/start.sh"]
