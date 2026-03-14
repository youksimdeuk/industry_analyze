"""
pdf_extractor.py — Google Drive PDF 다운로드 + 텍스트/이미지 추출

흐름:
  1. Google Drive에서 PDF 다운로드 (bytes)
  2. pymupdf로 텍스트 추출
  3. pymupdf로 이미지 추출 (최소 크기 필터링)
  4. gpt-4o로 이미지 분석 → 설명 텍스트 생성
  5. raw_text에 이미지 설명 추가 (GPT가 아티클 생성 시 활용)
"""

import io
import base64
import fitz  # PyMuPDF
from openai import OpenAI
from config import OPENAI_API_KEY

VISION_MODEL   = 'gpt-4o'
MIN_IMAGE_BYTES = 15000   # 아이콘·로고 등 작은 이미지 제외
MAX_IMAGES      = 10      # PDF당 최대 분석 이미지 수

openai_client = OpenAI(api_key=OPENAI_API_KEY, timeout=120.0, max_retries=0)


# =====================================================
# PDF 다운로드
# =====================================================

def download_pdf(drive_service, file_id: str) -> bytes:
    """Google Drive에서 PDF 파일 다운로드 → bytes"""
    from googleapiclient.http import MediaIoBaseDownload
    buffer = io.BytesIO()
    request = drive_service.files().get_media(fileId=file_id)
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue()


# =====================================================
# 이미지 분석 (gpt-4o 비전)
# =====================================================

def _analyze_image(image_data: bytes, ext: str) -> str:
    """gpt-4o로 차트/표/그래프 이미지 분석 → 핵심 인사이트 설명"""
    mime_map = {
        'png': 'image/png', 'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg', 'gif': 'image/gif', 'webp': 'image/webp',
    }
    mime = mime_map.get(ext.lower(), 'image/png')
    b64 = base64.b64encode(image_data).decode('utf-8')

    try:
        resp = openai_client.chat.completions.create(
            model=VISION_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "이 차트/표/그래프를 분석하세요.\n"
                            "- 핵심 수치, 트렌드, 비교 데이터를 구체적으로 설명\n"
                            "- 투자자 관점에서 중요한 인사이트 중심으로\n"
                            "- 2~4문장으로 요약"
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                    },
                ],
            }],
            max_completion_tokens=500,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"  [비전] 이미지 분석 실패: {e}")
        return ''


# =====================================================
# 메인: PDF 추출
# =====================================================

def extract_from_pdf(drive_service, file_id: str):
    """
    Google Drive PDF → 텍스트 + 이미지 추출

    반환:
        raw_text : str  — 본문 텍스트 + 이미지 설명이 추가된 전체 원문
        images   : list[dict]  — [{'data': bytes, 'ext': str, 'page': int, 'description': str}, ...]
    """
    print("  [PDF] 다운로드 중...")
    pdf_bytes = download_pdf(drive_service, file_id)
    print(f"  [PDF] {len(pdf_bytes):,} bytes 수신")

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    # ── 텍스트 추출 ──
    text_parts = []
    for page in doc:
        text = page.get_text()
        if text.strip():
            text_parts.append(text)
    raw_text = '\n'.join(text_parts)
    print(f"  [PDF] 텍스트 {len(raw_text):,}자 추출 ({doc.page_count}페이지)")

    # ── 이미지 추출 ──
    images = []
    seen_xrefs = set()

    for page_num, page in enumerate(doc):
        if len(images) >= MAX_IMAGES:
            break
        for img_info in page.get_images(full=True):
            xref = img_info[0]
            if xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)
            try:
                base_image = doc.extract_image(xref)
                img_data = base_image['image']
                img_ext  = base_image['ext']
                if len(img_data) < MIN_IMAGE_BYTES:
                    continue  # 아이콘·로고 등 제외
                images.append({
                    'data':        img_data,
                    'ext':         img_ext,
                    'page':        page_num + 1,
                    'description': '',
                    'wp_url':      None,
                })
                if len(images) >= MAX_IMAGES:
                    break
            except Exception:
                continue

    doc.close()
    print(f"  [PDF] 이미지 {len(images)}개 추출")

    # ── gpt-4o 이미지 분석 ──
    for i, img in enumerate(images):
        print(f"  [비전] 이미지 {i + 1}/{len(images)} 분석 중 (p.{img['page']})...")
        desc = _analyze_image(img['data'], img['ext'])
        img['description'] = desc
        if desc:
            raw_text += f"\n\n[이미지 분석 — {i + 1}번 차트/표 (p.{img['page']})]\n{desc}"

    return raw_text, images
