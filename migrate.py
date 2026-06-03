"""
migrate.py — Supabase industry_posts 테이블 스키마 마이그레이션

실행: python migrate.py

환경변수 필요:
- SUPABASE_URL
- SUPABASE_SERVICE_ROLE_KEY
- DATABASE_URL (선택) — 직접 postgres 연결 시
"""

import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SUPABASE_URL              = (os.getenv('SUPABASE_URL') or '').strip()
SUPABASE_SERVICE_ROLE_KEY = (os.getenv('SUPABASE_SERVICE_ROLE_KEY') or '').strip()
DATABASE_URL              = (os.getenv('DATABASE_URL') or '').strip()

MIGRATION_SQL = """
CREATE TABLE IF NOT EXISTS industry_posts (
  id               BIGSERIAL PRIMARY KEY,
  industry_name    TEXT        NOT NULL,
  period_key       TEXT        NOT NULL,
  doc_id           TEXT,
  content_ko       TEXT,
  content_en       TEXT,
  blog_summary_ko  TEXT,
  wp_ko_url        TEXT,
  wp_en_url        TEXT,
  slug             TEXT,
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  updated_at       TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (industry_name, period_key)
);

-- 중복 판정 기준을 '월(period_key)'에서 PDF 파일 고유ID(doc_id)로 전환
ALTER TABLE industry_posts ADD COLUMN IF NOT EXISTS doc_id TEXT;

-- doc_id 기준 upsert(on_conflict=doc_id)를 위한 유니크 인덱스
-- 일반 유니크 인덱스: Postgres는 NULL을 서로 다른 값으로 취급하므로
-- 과거 행(doc_id IS NULL) 여러 개도 허용된다.
-- (부분 인덱스 WHERE 절은 PostgREST on_conflict 추론과 충돌하므로 사용하지 않는다)
DROP INDEX IF EXISTS industry_posts_doc_id_key;
CREATE UNIQUE INDEX IF NOT EXISTS industry_posts_doc_id_key
  ON industry_posts (doc_id);

-- 기존 월별 유니크 제약은 doc_id 기준 upsert와 충돌할 수 있어 제거
ALTER TABLE industry_posts DROP CONSTRAINT IF EXISTS industry_posts_industry_name_period_key_key;
"""

def run_via_postgres():
    """DATABASE_URL 있을 경우 psycopg2로 직접 실행"""
    try:
        import psycopg2
    except ImportError:
        return False

    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(MIGRATION_SQL)
        conn.close()
        print("✅ 마이그레이션 완료 (psycopg2)")
        return True
    except Exception as e:
        print(f"❌ psycopg2 실행 실패: {e}")
        return False


def run_via_supabase_rpc():
    """Supabase Python SDK의 rpc로 exec_sql 시도"""
    try:
        from supabase import create_client
    except ImportError:
        return False

    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return False

    try:
        client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        client.rpc('exec_sql', {'sql': MIGRATION_SQL}).execute()
        print("✅ 마이그레이션 완료 (Supabase RPC)")
        return True
    except Exception as e:
        print(f"  [RPC] exec_sql 실패 (대시보드 직접 실행 필요): {e}")
        return False


def print_manual_instructions():
    print("\n" + "="*55)
    print("  Supabase 대시보드에서 직접 실행하세요")
    print("="*55)
    print("  1. https://supabase.com → 프로젝트 선택")
    print("  2. 좌측 SQL Editor 클릭")
    print("  3. 아래 SQL 붙여넣고 실행:")
    print("-"*55)
    print(MIGRATION_SQL.strip())
    print("="*55 + "\n")


if __name__ == '__main__':
    print("industry_posts 테이블 마이그레이션 시작...")

    if DATABASE_URL and run_via_postgres():
        sys.exit(0)

    if run_via_supabase_rpc():
        sys.exit(0)

    print_manual_instructions()
