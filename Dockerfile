FROM python:3.12-slim

WORKDIR /app
COPY ./app /app
COPY .env /app
COPY requirements.txt .

RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "news_api:app", "--host", "0.0.0.0", "--port", "8000"]
