"""
industry_main.py — 산업분석 자동화 메인
워크플로우:
  1. 구글 드라이브 '산업분석' 폴더에서 '*-산업분석.pdf' 탐색
  2. PDF 텍스트 추출 + 이미지 gpt-4o 분석
  3. 한국어 아티클 생성 → WordPress draft 발행
  4. 영어 아티클 생성 → WordPress draft 발행
  5. 블로그 요약 생성 → Supabase 저장
"""

import os
import sys
import json
import time
import requests
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from config import (
    OPENAI_API_KEY,
    GOOGLE_CREDENTIALS_PATH, GOOGLE_TOKEN_PATH,
    GOOGLE_CREDENTIALS_JSON, GOOGLE_TOKEN_JSON,
    WP_URL, WP_USERNAME, WP_APP_PASSWORD,
    PUBLISH_WEBHOOK_URL,
    SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY,
)
from industry_wp_ko_generator import generate_ko_article, _slugify
from industry_wp_en_generator import generate_en_article
from industry_blog_generator import generate_blog_post
from wp_publisher import publish_industry_draft, upload_media
from pdf_extractor import extract_from_pdf

SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
]

# 처리 완료 기록 파일
PROCESSED_LOG = 'processed_docs.json'


# =====================================================
# Google 인증
# =====================================================

def get_google_creds():
    """Google OAuth 인증 — credentials/token 파일 또는 환경변수 Secrets"""
    if GOOGLE_CREDENTIALS_JSON:
        with open(GOOGLE_CREDENTIALS_PATH, 'w', encoding='utf-8') as f:
            f.write(GOOGLE_CREDENTIALS_JSON)
    if GOOGLE_TOKEN_JSON:
        with open(GOOGLE_TOKEN_PATH, 'w', encoding='utf-8') as f:
            f.write(GOOGLE_TOKEN_JSON)

    if not os.path.exists(GOOGLE_CREDENTIALS_PATH):
        raise FileNotFoundError(
            f"Google credentials 파일 없음: {GOOGLE_CREDENTIALS_PATH}\n"
            "GOOGLE_CREDENTIALS_PATH 또는 GOOGLE_CREDENTIALS_JSON을 설정하세요."
        )

    creds = None
    if os.path.exists(GOOGLE_TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(GOOGLE_TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(GOOGLE_CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(GOOGLE_TOKEN_PATH, 'w') as f:
            f.write(creds.to_json())
    return creds


# =====================================================
# 구글 드라이브 / 독스 처리
# =====================================================

def find_industry_docs(drive_service):
    """구글 드라이브 '산업분석' 폴더에서 *-산업분석.pdf 탐색"""
    # 1) '산업분석' 폴더 ID 조회
    folder_res = drive_service.files().list(
        q="name='산업분석' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id, name)",
    ).execute()
    folders = folder_res.get('files', [])

    if folders:
        folder_id = folders[0]['id']
        query = (
            f"'{folder_id}' in parents and "
            "name contains '-산업분석' and mimeType='application/pdf' and trashed=false"
        )
    else:
        # 폴더 없으면 전체 드라이브에서 탐색
        query = "name contains '-산업분석' and mimeType='application/pdf' and trashed=false"

    results = drive_service.files().list(
        q=query,
        fields="files(id, name, modifiedTime)",
        orderBy="modifiedTime desc",
    ).execute()
    files = results.get('files', [])
    print(f"  [Drive] '*-산업분석.pdf' {len(files)}개 발견")
    return files


def extract_industry_name(doc_name):
    """'산업명-산업분석.pdf' → '산업명' 추출"""
    name = doc_name
    if name.lower().endswith('.pdf'):
        name = name[:-4]
    if name.endswith('-산업분석'):
        return name[:-len('-산업분석')].strip()
    return name.strip()


# =====================================================
# 처리 완료 기록 관리
# =====================================================

def load_processed():
    """처리 완료된 doc_id 목록 로드"""
    if os.path.exists(PROCESSED_LOG):
        try:
            with open(PROCESSED_LOG, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_processed(processed):
    with open(PROCESSED_LOG, 'w', encoding='utf-8') as f:
        json.dump(processed, f, ensure_ascii=False, indent=2)


# =====================================================
# Supabase 저장
# =====================================================

def save_to_supabase(industry_name, period_key, content_ko='', content_en='',
                     wp_ko_url=None, wp_en_url=None, slug=None, blog_summary_ko=''):
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        print("  [Supabase] 환경변수 없음 — 저장 스킵")
        return
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/industry_posts"
    headers = {
        'apikey':        SUPABASE_SERVICE_ROLE_KEY,
        'Authorization': f'Bearer {SUPABASE_SERVICE_ROLE_KEY}',
        'Content-Type':  'application/json',
        'Prefer':        'resolution=merge-duplicates',
    }
    payload = {
        'industry_name':    industry_name,
        'period_key':       period_key,
        'content_ko':       content_ko,
        'content_en':       content_en,
        'wp_ko_url':        wp_ko_url,
        'wp_en_url':        wp_en_url,
        'slug':             slug,
        'blog_summary_ko':  blog_summary_ko,
    }
    try:
        r = requests.post(
            f"{url}?on_conflict=industry_name,period_key",
            json=payload, headers=headers, timeout=15,
        )
        if r.status_code in (200, 201):
            print(f"  ✅ Supabase 저장 완료: {industry_name} ({period_key})")
        else:
            print(f"  ⚠️ Supabase 저장 실패: {r.status_code} {r.text[:200]}")
    except Exception as e:
        print(f"  ⚠️ Supabase 저장 오류: {e}")


# =====================================================
# 알림 Webhook
# =====================================================

def _send_notification(industry_name, ko_url, en_url):
    if not PUBLISH_WEBHOOK_URL:
        return
    try:
        msg = (
            f"[산업분석] {industry_name} 임시저장 완료\n"
            f"KO: {ko_url or '발행 실패'}\n"
            f"EN: {en_url or '발행 실패'}"
        )
        payload = {'content': msg} if 'discord.com' in PUBLISH_WEBHOOK_URL else {'text': msg}
        requests.post(PUBLISH_WEBHOOK_URL, json=payload, timeout=10)
    except Exception as e:
        print(f"  [알림] Webhook 실패 (무시): {e}")


# =====================================================
# 단일 문서 처리
# =====================================================

def process_doc(drive_service, doc_id, doc_name):
    """하나의 구글 독스를 처리해 KO/EN WordPress draft 발행"""
    industry_name = extract_industry_name(doc_name)
    period_key    = datetime.now().strftime('%Y-%m')

    print(f"\n{'='*50}")
    print(f"산업분석 시작: {industry_name}")
    print(f"{'='*50}")

    # ── PDF 텍스트 + 이미지 추출 ──
    print("\n[1/5] PDF 원문 추출 중...")
    try:
        raw_text, images = extract_from_pdf(drive_service, doc_id)
    except Exception as e:
        print(f"  ❌ PDF 추출 실패: {e}")
        return False
    if not raw_text or len(raw_text.strip()) < 200:
        print("  ❌ 문서 내용이 너무 짧거나 비어 있습니다. 건너뜀.")
        return False
    print(f"  ✅ {len(raw_text):,}자 추출 완료 (이미지 {len(images)}개)")

    # ── WP 이미지 업로드 ──
    if images and WP_URL and WP_USERNAME and WP_APP_PASSWORD:
        print(f"\n  [WP Media] 이미지 {len(images)}개 업로드 중...")
        for i, img in enumerate(images):
            filename = f"{_slugify(industry_name)}-img{i + 1}.{img['ext']}"
            url = upload_media(img['data'], filename, img['ext'])
            img['wp_url'] = url or None
    wp_images = [img for img in images if img.get('wp_url')]

    ko_url = en_url = ko_slug = None
    ko_content = en_content = ''
    blog_summary_ko = ''
    ko_article = None

    # ── 한국어 아티클 ──
    print("\n[2/5] 한국어 아티클 생성 중...")
    try:
        ko_article = generate_ko_article(industry_name, raw_text, images=wp_images)
        if ko_article:
            ko_content = ko_article.get('content', '')
            if WP_URL and WP_USERNAME and WP_APP_PASSWORD:
                ko_url  = publish_industry_draft(ko_article, lang='ko')
                ko_slug = ko_article.get('slug')
                print(f"  ✅ KO 임시저장: {ko_url}")
                print(f"  포커스 키워드: {ko_article.get('focus_keyword', '-')}")
            else:
                print("  [KO] WP 설정 없음 — 발행 스킵")
    except Exception as e:
        print(f"  ⚠️ KO 아티클 생성/발행 실패: {e}")

    time.sleep(1)

    # ── 영어 아티클 ──
    print("\n[3/5] 영어 아티클 생성 중...")
    try:
        en_article = generate_en_article(industry_name, raw_text, images=wp_images)
        if en_article:
            en_content = en_article.get('content', '')
            if WP_URL and WP_USERNAME and WP_APP_PASSWORD:
                en_url = publish_industry_draft(en_article, lang='en')
                print(f"  ✅ EN 임시저장: {en_url}")
                print(f"  Focus keyword: {en_article.get('focus_keyword', '-')}")
            else:
                print("  [EN] WP 설정 없음 — 발행 스킵")
    except Exception as e:
        print(f"  ⚠️ EN 아티클 생성/발행 실패: {e}")

    # ── 블로그 요약 생성 ──
    print("\n[4/5] 블로그 요약 포스트 생성 중...")
    try:
        if ko_article:
            blog_summary_ko = generate_blog_post(
                industry_name=industry_name,
                deep_research_text=raw_text,
                focus_keyword=ko_article.get('focus_keyword', f'{industry_name} 전망'),
                tags=ko_article.get('tags', []),
                wp_url=ko_url or '',
                period_key=period_key,
            )
            if blog_summary_ko:
                print(f"  ✅ 블로그 요약 생성 완료 ({len(blog_summary_ko)}자)")
            else:
                print("  ⚠️ 블로그 요약 생성 실패")
    except Exception as e:
        print(f"  ⚠️ 블로그 요약 생성 오류: {e}")

    # ── Supabase 저장 ──
    print("\n[5/5] Supabase 저장 중...")
    save_to_supabase(
        industry_name, period_key,
        content_ko=ko_content,
        content_en=en_content,
        wp_ko_url=ko_url,
        wp_en_url=en_url,
        slug=ko_slug,
        blog_summary_ko=blog_summary_ko,
    )

    # ── 알림 ──
    _send_notification(industry_name, ko_url, en_url)

    print(f"\n✅ {industry_name} 처리 완료!")
    return True


# =====================================================
# 메인 실행
# =====================================================

def run_all():
    force = (os.getenv('FORCE_REANALYZE') or '').strip().lower() in {'1', 'true', 'yes', 'y'}
    target_id = (os.getenv('TARGET_DOC_ID') or '').strip()

    print("구글 계정 인증 중...")
    creds = get_google_creds()
    drive_service = build('drive', 'v3', credentials=creds)  # 1회 생성 후 재사용

    processed = load_processed()

    summary = {'found': 0, 'processed': 0, 'skipped': 0, 'failed': 0}

    # 특정 문서 직접 지정 모드
    if target_id:
        print(f"\n[직접실행] TARGET_DOC_ID 지정됨: {target_id}")
        meta = drive_service.files().get(fileId=target_id, fields='id,name').execute()
        doc_name = meta.get('name', target_id)
        summary['found'] = 1
        if target_id in processed and not force:
            print(f"  이미 처리됨. 건너뜀 (FORCE_REANALYZE 미지정)")
            summary['skipped'] += 1
            return summary
        ok = process_doc(drive_service, target_id, doc_name)
        if ok:
            processed[target_id] = {'name': doc_name, 'ts': datetime.now().isoformat()}
            save_processed(processed)
            summary['processed'] += 1
        else:
            summary['failed'] += 1
        return summary

    # 자동 탐색 모드
    docs = find_industry_docs(drive_service)
    if not docs:
        print("  '산업분석' 폴더에 *-산업분석.pdf 파일이 없습니다.")
        return summary

    summary['found'] = len(docs)
    for doc in docs:
        doc_id   = doc['id']
        doc_name = doc['name']
        if doc_id in processed and not force:
            print(f"  [{doc_name}] 이미 처리됨. 건너뜀.")
            summary['skipped'] += 1
            continue
        try:
            ok = process_doc(drive_service, doc_id, doc_name)
            if ok:
                processed[doc_id] = {'name': doc_name, 'ts': datetime.now().isoformat()}
                save_processed(processed)
                summary['processed'] += 1
            else:
                summary['failed'] += 1
        except Exception as e:
            print(f"  [{doc_name}] 오류: {e}")
            summary['failed'] += 1

    print(
        f"\n[요약] found={summary['found']}, processed={summary['processed']}, "
        f"skipped={summary['skipped']}, failed={summary['failed']}"
    )
    return summary


if __name__ == '__main__':
    if not OPENAI_API_KEY:
        print("[오류] OPENAI_API_KEY가 설정되지 않았습니다.")
        sys.exit(1)
    run_all()
