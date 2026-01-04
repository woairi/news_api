#!/usr/bin/env python3
"""데이터베이스 마이그레이션: ai_provider 컬럼 추가"""
import sqlite3
import os

def migrate_database():
    """기존 데이터베이스에 ai_provider 컬럼 추가"""
    db_path = '/app/data/news_summaries.db' if os.path.exists('/app/data') else 'data/news_summaries.db'

    if not os.path.exists(db_path):
        print(f"[정보] 데이터베이스 파일이 없습니다: {db_path}")
        print("[정보] 새로운 데이터베이스가 자동으로 생성됩니다.")
        return

    print(f"[1/3] 데이터베이스 연결 중: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 현재 컬럼 확인
    print("[2/3] 테이블 구조 확인 중...")
    columns = {row[1] for row in cursor.execute('PRAGMA table_info(summaries)')}
    print(f"[정보] 현재 컬럼: {columns}")

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
