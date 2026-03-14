"""
Supabase DB 연동 모듈

테이블:
- industry_posts : 산업분석 콘텐츠 원본
- publish_runs   : 채널별 발행 이력 (wp_ko / wp_en / ...)

환경변수 SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY 없으면 모든 함수는 None 반환 후 조용히 skip.
"""

from config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

_client = None


def get_db():
    """Supabase 클라이언트 반환. 환경변수 없으면 None."""
    global _client
    if _client is not None:
        return _client
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return None
    try:
        from supabase import create_client
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        return _client
    except Exception as e:
        print(f"  [DB] Supabase 연결 실패 (DB 저장 스킵): {e}")
        return None


# ──────────────────────────────────────────────────────────
# industry_posts
# ──────────────────────────────────────────────────────────

def get_post_id(industry_name: str, period_key: str):
    """industry_posts에서 id 조회. 없으면 None."""
    db = get_db()
    if db is None:
        return None
    try:
        res = (
            db.table("industry_posts")
            .select("id")
            .eq("industry_name", industry_name)
            .eq("period_key", period_key)
            .limit(1)
            .execute()
        )
        return res.data[0]["id"] if res.data else None
    except Exception as e:
        print(f"  [DB] industry_posts 조회 실패 (스킵): {e}")
        return None


# ──────────────────────────────────────────────────────────
# publish_runs
# ──────────────────────────────────────────────────────────

def log_publish(post_id: str, channel: str, status: str,
                url=None, error=None):
    """
    publish_runs에 발행 이력 기록.
    channel: wp_ko / wp_en
    status:  success / failed
    """
    db = get_db()
    if db is None or not post_id:
        return
    try:
        db.table("publish_runs").insert({
            "post_id": post_id,
            "channel": channel,
            "status":  status,
            "url":     url,
            "error":   error,
        }).execute()
    except Exception as e:
        print(f"  [DB] publish_runs 기록 실패 (스킵): {e}")
