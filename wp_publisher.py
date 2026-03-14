"""
wp_publisher.py — 산업분석 WordPress REST API 발행 (draft)
"""

import json
import os
import requests
from datetime import datetime
from requests.auth import HTTPBasicAuth

from config import WP_URL, WP_USERNAME, WP_APP_PASSWORD

_WP_BASE_URL = os.getenv('WP_BASE_URL') or WP_URL
_WP_USER     = os.getenv('WP_USER') or WP_USERNAME

KO_CATEGORY_NAME = '산업분석'
EN_CATEGORY_NAME = 'Industry Analysis'

LOG_FILE = 'wp_publish_log.jsonl'


def _auth():
    return HTTPBasicAuth(_WP_USER, WP_APP_PASSWORD)


def _api(path):
    return f"{_WP_BASE_URL.rstrip('/')}/wp-json/wp/v2/{path}"


# =====================================================
# 카테고리 / 태그
# =====================================================

def get_or_create_category(name):
    r = requests.get(
        _api('categories'),
        params={'search': name, 'per_page': 10},
        auth=_auth(), timeout=15,
    )
    r.raise_for_status()
    for item in r.json():
        if item.get('name') == name:
            return item['id']
    r = requests.post(_api('categories'), json={'name': name}, auth=_auth(), timeout=15)
    r.raise_for_status()
    return r.json()['id']


def get_or_create_tags(tag_names):
    tag_ids = []
    for name in tag_names:
        if not name:
            continue
        r = requests.get(
            _api('tags'),
            params={'search': name, 'per_page': 5},
            auth=_auth(), timeout=15,
        )
        r.raise_for_status()
        matched = next((x for x in r.json() if x.get('name') == name), None)
        if matched:
            tag_ids.append(matched['id'])
        else:
            r = requests.post(_api('tags'), json={'name': name}, auth=_auth(), timeout=15)
            if r.status_code in (200, 201):
                tag_ids.append(r.json()['id'])
    return tag_ids


# =====================================================
# Yoast SEO 메타 설정
# =====================================================

def _set_yoast_meta(post_id, seo_data):
    """Yoast SEO 플러그인 메타 업데이트 (REST API)"""
    meta_payload = {
        'meta': {
            '_yoast_wpseo_title':    seo_data.get('seo_title', ''),
            '_yoast_wpseo_metadesc': seo_data.get('meta_description', ''),
            '_yoast_wpseo_focuskw':  seo_data.get('focus_keyword', ''),
        }
    }
    try:
        r = requests.post(
            _api(f'posts/{post_id}'),
            json=meta_payload,
            auth=_auth(), timeout=15,
        )
        if r.status_code not in (200, 201):
            print(f"  [Yoast] 메타 설정 실패 (무시): {r.status_code}")
    except Exception as e:
        print(f"  [Yoast] 예외 (무시): {e}")


# =====================================================
# Schema.org JSON-LD 삽입
# =====================================================

def _build_schema_jsonld(article_data, lang='ko'):
    """Article + FAQPage JSON-LD 생성"""
    schemas = []

    # Article 스키마
    article_schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": article_data.get('title', ''),
        "description": article_data.get('meta_description', ''),
        "datePublished": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
        "inLanguage": "ko-KR" if lang == 'ko' else "en-US",
        "author": {"@type": "Organization", "name": "산업분석 리서치"},
        "publisher": {"@type": "Organization", "name": "산업분석 리서치"},
    }
    schemas.append(article_schema)

    # FAQPage 스키마
    faq_items = article_data.get('faq_list', [])
    if faq_items:
        faq_schema = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": item.get('q', ''),
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": item.get('a', '')
                    }
                }
                for item in faq_items if item.get('q') and item.get('a')
            ]
        }
        if faq_schema['mainEntity']:
            schemas.append(faq_schema)

    if not schemas:
        return ''

    parts = [
        f'<script type="application/ld+json">\n{json.dumps(s, ensure_ascii=False, indent=2)}\n</script>'
        for s in schemas
    ]
    return '\n'.join(parts)


# =====================================================
# 이미지 미디어 업로드
# =====================================================

def upload_media(image_data: bytes, filename: str, ext: str) -> str:
    """이미지를 WordPress 미디어 라이브러리에 업로드. source_url 반환 (실패 시 '')"""
    if not _WP_BASE_URL or not _WP_USER or not WP_APP_PASSWORD:
        return ''
    mime_map = {
        'png': 'image/png', 'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg', 'gif': 'image/gif', 'webp': 'image/webp',
    }
    mime = mime_map.get(ext.lower(), 'image/png')
    try:
        r = requests.post(
            _api('media'),
            data=image_data,
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"',
                'Content-Type': mime,
            },
            auth=_auth(),
            timeout=30,
        )
        if r.status_code in (200, 201):
            url = r.json().get('source_url', '')
            print(f"  [WP Media] 업로드 완료: {filename}")
            return url
        else:
            print(f"  [WP Media] 업로드 실패: {r.status_code}")
    except Exception as e:
        print(f"  [WP Media] 업로드 오류: {e}")
    return ''


# =====================================================
# 인증 사전 체크
# =====================================================

def check_wp_auth() -> bool:
    """WP 인증 확인. 성공 True, 실패 False (에러 메시지 출력)."""
    if not _WP_BASE_URL or not _WP_USER or not WP_APP_PASSWORD:
        print("  [WP] 자격증명 미설정 — 발행 스킵")
        return False
    try:
        r = requests.get(
            _api('users/me'),
            auth=_auth(), timeout=10,
        )
        if r.ok:
            name = r.json().get('name', '(unknown)')
            print(f"  [WP] 인증 성공: {name}")
            return True
        try:
            wp_error = r.json()
            print(f"  [WP] 인증 실패 {r.status_code} — code: {wp_error.get('code')} / {wp_error.get('message')}")
        except ValueError:
            print(f"  [WP] 인증 실패 {r.status_code}")
        return False
    except Exception as e:
        print(f"  [WP] 인증 체크 오류: {e}")
        return False


# =====================================================
# 발행 (draft)
# =====================================================

def publish_industry_draft(article, lang='ko'):
    """산업분석 글을 WordPress 임시저장(draft)으로 발행.
    반환: 발행된 포스트 URL (string) 또는 None
    """
    if not _WP_BASE_URL or not _WP_USER or not WP_APP_PASSWORD:
        print("  [WP] 설정 없음 — 발행 스킵")
        return None

    category_name = KO_CATEGORY_NAME if lang == 'ko' else EN_CATEGORY_NAME
    cat_id  = get_or_create_category(category_name)
    tag_ids = get_or_create_tags(article.get('tags', []))

    # Schema JSON-LD를 본문 앞에 삽입
    schema_html = _build_schema_jsonld(article, lang=lang)
    content = (schema_html + '\n' if schema_html else '') + article.get('content', '')

    payload = {
        'title':      article.get('title', ''),
        'content':    content,
        'status':     'draft',           # 임시저장
        'slug':       article.get('slug', ''),
        'categories': [cat_id],
        'tags':       tag_ids,
        'excerpt':    article.get('meta_description', ''),
    }

    r = requests.post(_api('posts'), json=payload, auth=_auth(), timeout=30)
    if not r.ok:
        try:
            wp_error = r.json()
            raise requests.HTTPError(
                f"{r.status_code} {r.reason} — WP code: {wp_error.get('code')} / {wp_error.get('message')}",
                response=r,
            )
        except (ValueError, KeyError):
            r.raise_for_status()
    post = r.json()
    post_id  = post['id']
    post_url = post.get('link', '')

    # Yoast SEO 메타 설정
    _set_yoast_meta(post_id, {
        'seo_title':       article.get('seo_title', ''),
        'meta_description': article.get('meta_description', ''),
        'focus_keyword':   article.get('focus_keyword', ''),
    })

    # 발행 로그
    log_entry = {
        'ts':       datetime.now().isoformat(),
        'lang':     lang,
        'title':    article.get('title', ''),
        'post_id':  post_id,
        'url':      post_url,
        'slug':     article.get('slug', ''),
        'keyword':  article.get('focus_keyword', ''),
    }
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    except Exception:
        pass

    print(f"  ✅ [{lang.upper()}] 임시저장 완료: {post_url}")
    return post_url
