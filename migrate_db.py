#!/usr/bin/env python3
"""데이터베이스 마이그레이션: ai_provider 컬럼 추가"""
import sqlite3
import os

def migrate_database():
    """기존 데이터베이스에 ai_provider 컬럼 추가"""
    # DB 경로 결정 logic matching web_app.py mostly, but checking where file actually is
    if os.path.exists('/app/data/news_summaries.db'):
        db_path = '/app/data/news_summaries.db'
    elif os.path.exists('news_summaries.db'):
        db_path = 'news_summaries.db'
    elif os.path.exists('data/news_summaries.db'):
        db_path = 'data/news_summaries.db'
    else:
        # Default to root if creating new
        db_path = 'news_summaries.db'

    if not os.path.exists(db_path):
        print(f"[정보] 데이터베이스 파일이 없습니다: {db_path}")
        return

    print(f"[1/3] 데이터베이스 연결 중: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 현재 컬럼 확인
    print("[2/3] 테이블 구조 확인 중...")
    try:
        columns = {row[1] for row in cursor.execute('PRAGMA table_info(summaries)')}
    except sqlite3.OperationalError:
        print("[오류] summaries 테이블을 찾을 수 없습니다.")
        return
        
    print(f"[정보] 현재 컬럼: {columns}")

    # category 컬럼 추가
    if 'category' not in columns:
        print("[2-1/3] category 컬럼 추가 중...")
        try:
            cursor.execute("ALTER TABLE summaries ADD COLUMN category TEXT NOT NULL DEFAULT 'ai_news'")
            # 기존 데이터 인덱스 생성
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_summaries_date_category ON summaries(date, category)")
            conn.commit()
            print("[완료] ✅ category 컬럼이 성공적으로 추가되었습니다!")
        except Exception as e:
            print(f"[오류] category 컬럼 추가 실패: {e}")

    # ai_provider 컬럼 추가
    if 'ai_provider' not in columns:
        print("[3/3] ai_provider 컬럼 추가 중...")
        cursor.execute("ALTER TABLE summaries ADD COLUMN ai_provider TEXT NOT NULL DEFAULT 'gemini'")
        cursor.execute("UPDATE summaries SET ai_provider = 'gemini' WHERE ai_provider IS NULL OR TRIM(ai_provider) = ''")
        conn.commit()
        print("[완료] ✅ ai_provider 컬럼이 성공적으로 추가되었습니다!")
    else:
        print("[정보] ai_provider 컬럼이 이미 존재합니다. 마이그레이션을 건너뜁니다.")

    conn.close()
    print("\n[마이그레이션 완료] 데이터베이스가 업데이트되었습니다.")

if __name__ == "__main__":
    migrate_database()
