"""
copy_secrets.py — stock_analyze GitHub 시크릿을 industry_analyze로 복사

방법: stock_analyze 시크릿 이름 목록을 가져오고,
      각 값을 로컬 환경변수 또는 직접 입력으로 받아 industry_analyze에 설정.
"""

import os
import sys
import base64
import requests
from nacl import encoding, public

GH_TOKEN   = os.getenv('GH_TOKEN', '')
SRC_REPO   = 'youksimdeuk/stock_analyze'
DST_REPO   = 'youksimdeuk/industry_analyze'

HEADERS = {
    'Authorization': f'Bearer {GH_TOKEN}',
    'Accept': 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
}

# industry_analyze 워크플로우에 필요한 시크릿 목록
REQUIRED_SECRETS = [
    'OPENAI_API_KEY',
    'GOOGLE_CREDENTIALS_JSON',
    'GOOGLE_TOKEN_JSON',
    'WP_URL',
    'WP_USERNAME',
    'WP_APP_PASSWORD',
    'SUPABASE_URL',
    'SUPABASE_SERVICE_ROLE_KEY',
    'PUBLISH_WEBHOOK_URL',
]


def get_repo_public_key(repo):
    """대상 레포의 공개키 조회 (시크릿 암호화용)"""
    r = requests.get(
        f'https://api.github.com/repos/{repo}/actions/secrets/public-key',
        headers=HEADERS,
    )
    r.raise_for_status()
    data = r.json()
    return data['key_id'], data['key']


def encrypt_secret(public_key_b64, secret_value):
    """GitHub 방식으로 시크릿 값 암호화"""
    pk = public.PublicKey(public_key_b64.encode(), encoding.Base64Encoder())
    box = public.SealedBox(pk)
    encrypted = box.encrypt(secret_value.encode())
    return base64.b64encode(encrypted).decode()


def set_secret(repo, key_id, public_key_b64, secret_name, secret_value):
    """대상 레포에 시크릿 설정"""
    encrypted = encrypt_secret(public_key_b64, secret_value)
    r = requests.put(
        f'https://api.github.com/repos/{repo}/actions/secrets/{secret_name}',
        headers=HEADERS,
        json={'encrypted_value': encrypted, 'key_id': key_id},
    )
    return r.status_code in (201, 204)


def get_src_secret_names(repo):
    """소스 레포 시크릿 이름 목록 조회 (값은 읽을 수 없음)"""
    r = requests.get(
        f'https://api.github.com/repos/{repo}/actions/secrets',
        headers=HEADERS,
    )
    r.raise_for_status()
    return [s['name'] for s in r.json().get('secrets', [])]


if __name__ == '__main__':
    if not GH_TOKEN:
        print("❌ GH_TOKEN 환경변수가 없습니다.")
        sys.exit(1)

    print(f"\n소스: {SRC_REPO}")
    print(f"대상: {DST_REPO}\n")

    # 소스 시크릿 목록 확인
    try:
        src_names = get_src_secret_names(SRC_REPO)
        print(f"stock_analyze 시크릿 목록: {', '.join(src_names)}\n")
    except Exception as e:
        print(f"⚠️  소스 시크릿 목록 조회 실패: {e}")
        src_names = []

    # 대상 레포 공개키
    key_id, pub_key = get_repo_public_key(DST_REPO)

    success, skipped = 0, 0

    for name in REQUIRED_SECRETS:
        # 1순위: 로컬 환경변수
        value = os.getenv(name, '').strip()

        # 2순위: 직접 입력
        if not value:
            hint = '(stock_analyze에 있음)' if name in src_names else '(선택사항 — 없으면 Enter)'
            value = input(f"  {name} {hint}: ").strip()

        if not value:
            print(f"  ⏭  {name} 스킵")
            skipped += 1
            continue

        ok = set_secret(DST_REPO, key_id, pub_key, name, value)
        if ok:
            print(f"  ✅ {name} 설정 완료")
            success += 1
        else:
            print(f"  ❌ {name} 설정 실패")

    print(f"\n완료: 성공 {success}개 / 스킵 {skipped}개")
