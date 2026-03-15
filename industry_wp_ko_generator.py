"""
industry_wp_ko_generator.py — 한국어 산업분석 WordPress 아티클 생성
SEO + AEO (Answer Engine Optimization) 적용
"""

import re
from openai_utils import _call_openai, _call_openai_json, _slugify


# =====================================================
# Step 1: GPT 목차 설계
# =====================================================

def generate_toc(industry_name, deep_research_text):
    """딥리서치 내용을 분석해 최적 목차(H2/H3) 동적 생성"""
    prompt = f"""당신은 SEO/AEO 전문 편집자입니다.
아래 '{industry_name}' 산업 딥리서치 원문을 분석해 한국어 투자자용 블로그 글의 목차를 설계하세요.

규칙:
1. 이 산업의 특성과 원문 내용에 맞는 H2 섹션을 5~8개 구성 (고정 템플릿 금지)
2. 각 H2 아래 필요 시 H3 소섹션 1~3개 추가
3. 반드시 포함해야 할 섹션: 투자 포인트(또는 투자 논거), 핵심 리스크, FAQ
4. 검색 의도(정보성/상업성)에 맞는 섹션 순서로 배열
5. FAQ 섹션은 명확한 Q&A 구조로 구성
6. 각 섹션에 어울리는 앵커 id(영문 소문자 하이픈) 포함
7. 섹션 제목에 "SEO", "AEO", "AI 인용", "투자자용" 같은 내부 라벨 절대 포함 금지

딥리서치 원문 (앞 3000자):
{deep_research_text[:3000]}

JSON으로만 반환:
{{
  "toc": [
    {{"h2": "섹션 제목", "anchor": "section-anchor", "h3": ["소섹션1", "소섹션2"]}},
    ...
  ],
  "faq_topics": ["FAQ 주제1", "FAQ 주제2", "FAQ 주제3", "FAQ 주제4", "FAQ 주제5"]
}}"""
    result = _call_openai_json(prompt, max_tokens=4000)
    return result.get('toc', []), result.get('faq_topics', [])


# =====================================================
# Step 2: SEO/AEO 메타 생성
# =====================================================

def generate_seo_meta(industry_name, toc, deep_research_text):
    """focus keyword, seo_title, meta_description, slug, tags 생성"""
    toc_summary = ' > '.join([s.get('h2', '') for s in toc])
    prompt = f"""한국어 투자자 대상 '{industry_name}' 산업분석 블로그 글의 SEO 메타를 생성하세요.

목차 구조: {toc_summary}

딥리서치 핵심 내용 (앞 1000자):
{deep_research_text[:1000]}

규칙:
- focus_keyword: 검색량 높은 핵심 키워드 1개 (예: "HBM 반도체 시장 전망")
- seo_title: 60자 이내, focus_keyword 앞 배치, 연도 포함
- meta_description: 150자 이내, focus_keyword 포함, 클릭 유도 문구 포함
- slug: 영문 소문자 하이픈 (한글 금지, 40자 이내)
- tags: 산업명·세부기술·국가·관련주제 포함 10~15개

JSON으로만 반환:
{{
  "focus_keyword": "...",
  "seo_title": "...",
  "meta_description": "...",
  "slug": "...",
  "tags": ["태그1", "태그2", ...]
}}"""
    return _call_openai_json(prompt, max_tokens=1000)


# =====================================================
# Step 3: 본문 섹션별 생성
# =====================================================

def _build_toc_html(toc):
    """목차 HTML 블록 (앵커 링크)"""
    items = []
    for sec in toc:
        anchor = sec.get('anchor', _slugify(sec.get('h2', '')))
        h2 = sec.get('h2', '')
        items.append(f'<li><a href="#{anchor}">{h2}</a>')
        h3_list = sec.get('h3', [])
        if h3_list:
            sub = ''.join(f'<li>{s}</li>' for s in h3_list)
            items.append(f'<ul>{sub}</ul>')
        items.append('</li>')

    toc_html = (
        '<div class="toc-box" style="background:#f0f4f8;border-left:4px solid #1a3a5c;'
        'padding:16px 20px;margin:24px 0;border-radius:4px;">'
        '<p style="font-weight:bold;margin:0 0 8px;color:#1a3a5c;">📋 목차</p>'
        f'<ul style="margin:0;padding-left:20px;">{"".join(items)}</ul>'
        '</div>'
    )
    return toc_html


def _build_faq_html(faq_list):
    """FAQ HTML 블록 (AEO 최적화)"""
    if not faq_list:
        return ''
    items = []
    for item in faq_list:
        q = item.get('q', '')
        a = item.get('a', '')
        if not q or not a:
            continue
        items.append(
            f'<div class="faq-item" style="margin-bottom:16px;">'
            f'<p style="font-weight:bold;color:#1a3a5c;margin:0 0 4px;">Q. {q}</p>'
            f'<p style="margin:0;color:#374151;">A. {a}</p>'
            f'</div>'
        )
    if not items:
        return ''
    return (
        '<div class="faq-section" style="background:#f9fafb;border:1px solid #e5e7eb;'
        'padding:20px;border-radius:6px;margin:32px 0;">'
        '<h2 style="margin-top:0;color:#1a3a5c;">자주 묻는 질문 (FAQ)</h2>'
        + ''.join(items) +
        '</div>'
    )


def generate_intro(industry_name, deep_research_text, focus_keyword):
    """AI 스니펫 최적화 도입부 (3문장, focus_keyword 첫 100자 내 포함)"""
    prompt = f"""'{industry_name}' 산업분석 한국어 블로그 글의 도입부를 3문장으로 작성하세요.

규칙:
- 첫 문장 100자 이내에 반드시 '{focus_keyword}' 포함
- 산업의 핵심 현황을 직접 답변 형태로 (AI 스니펫 최적화)
- 한국 투자자의 관심을 끄는 수치나 트렌드 1개 포함
- 3문장만 출력 (다른 설명 없이)

딥리서치 핵심 내용:
{deep_research_text[:2000]}"""
    return _call_openai(prompt, max_tokens=600)


def generate_section_content(industry_name, section, deep_research_text, focus_keyword, images=None):
    """H2 섹션 1개의 본문 생성 (H3 포함)"""
    h2 = section.get('h2', '')
    h3_list = section.get('h3', [])
    anchor = section.get('anchor', _slugify(h2))

    h3_instruction = ''
    if h3_list:
        h3_instruction = f"\n- 다음 소섹션(H3)을 반드시 포함: {', '.join(h3_list)}"

    image_instruction = ''
    if images:
        img_lines = '\n'.join(
            f'  • 이미지{i + 1} (URL: {img["wp_url"]}): {img["description"]}'
            for i, img in enumerate(images)
            if img.get('wp_url') and img.get('description')
        )
        if img_lines:
            image_instruction = (
                f"\n- 아래 이미지 중 이 섹션과 관련 있는 것이 있으면 본문에 삽입하세요:\n{img_lines}"
                "\n- 삽입 형식: <figure style=\"margin:16px 0;\"><img src=\"URL\" alt=\"설명\" "
                "style=\"max-width:100%;height:auto;\"><figcaption style=\"font-size:12px;"
                "color:#6b7280;text-align:center;\">설명</figcaption></figure>"
            )

    prompt = f"""'{industry_name}' 산업분석 글의 [{h2}] 섹션 본문을 작성하세요.

규칙:
- 섹션 첫 문단(2~3문장)은 핵심 답변을 직접 제시 (AEO: AI가 인용하기 좋은 형태)
- 구체적 수치(시장 규모, 성장률, 점유율 등)와 연도 반드시 포함
- 데이터 비교는 HTML 테이블로 구조화
- 모호한 일반론 금지 ("다양한", "지속적인" 등)
- 한국 투자자 관점의 인사이트 포함
- '{focus_keyword}' 키워드 자연스럽게 1~2회 포함{h3_instruction}{image_instruction}
- HTML 형식으로 출력 (H3는 <h3> 태그 사용, 단락은 <p>, 테이블은 <table>)

딥리서치 원문 참고:
{deep_research_text[:4000]}

[{h2}] 섹션만 작성하세요 (H2 제목 태그 제외, 본문만):"""
    content = _call_openai(prompt, max_tokens=4000)

    return (
        f'<h2 id="{anchor}">{h2}</h2>\n'
        f'{content}\n'
    )


def generate_faq(industry_name, faq_topics, deep_research_text):
    """FAQ Q&A 생성 (AEO 최적화)"""
    topics_str = '\n'.join(f'- {t}' for t in faq_topics)
    prompt = f"""'{industry_name}' 산업에 대해 한국 투자자가 자주 묻는 질문과 답변을 작성하세요.

FAQ 주제:
{topics_str}

규칙:
- 각 답변은 2~4문장, 핵심만 직접 답변 (AI 답변 엔진 최적화)
- 구체적 수치나 근거 포함
- 투자 권유 표현 금지

딥리서치 참고:
{deep_research_text[:3000]}

JSON으로만 반환:
{{"faq": [{{"q": "질문1", "a": "답변1"}}, ...]}}"""
    result = _call_openai_json(prompt, max_tokens=6000)
    return result.get('faq', [])


# =====================================================
# 메인: 한국어 아티클 조립
# =====================================================

def generate_ko_article(industry_name, deep_research_text, related_posts=None, images=None):
    """한국어 산업분석 아티클 전체 생성
    반환: dict (title, content, seo_title, meta_description, focus_keyword,
                 slug, tags, faq_list)
    images: list of {'wp_url': str, 'description': str} — WP 업로드된 이미지
    """
    print(f"  [KO] 목차 설계 중...")
    toc, faq_topics = generate_toc(industry_name, deep_research_text)
    if not toc:
        print("  [KO] 목차 생성 실패")
        return {}

    print(f"  [KO] SEO 메타 생성 중...")
    seo = generate_seo_meta(industry_name, toc, deep_research_text)

    focus_keyword = seo.get('focus_keyword', f'{industry_name} 전망')
    seo_title     = seo.get('seo_title', f'{industry_name} 산업분석 {__import__("datetime").datetime.now().year}')
    meta_desc     = seo.get('meta_description', '')
    slug          = seo.get('slug', '') or _slugify(f'{industry_name}-industry-analysis')
    tags          = seo.get('tags', [industry_name])

    print(f"  [KO] 도입부 생성 중...")
    intro = generate_intro(industry_name, deep_research_text, focus_keyword)

    print(f"  [KO] 본문 {len(toc)}개 섹션 생성 중...")
    section_htmls = []
    for i, sec in enumerate(toc, 1):
        print(f"    섹션 {i}/{len(toc)}: {sec.get('h2', '')}")
        section_htmls.append(
            generate_section_content(industry_name, sec, deep_research_text, focus_keyword, images=images)
        )

    print(f"  [KO] FAQ 생성 중...")
    faq_list = generate_faq(industry_name, faq_topics, deep_research_text)

    # ── 내부링크 블록 ──
    internal_links_html = ''
    if related_posts:
        links = ''.join(
            f'<li><a href="{p.get("url", "#")}">{p.get("title", "")}</a></li>'
            for p in related_posts[:5] if p.get('title')
        )
        if links:
            internal_links_html = (
                '<div style="background:#f0f4f8;padding:16px;border-radius:6px;margin:32px 0;">'
                '<p style="font-weight:bold;margin:0 0 8px;">📌 관련 기업분석</p>'
                f'<ul>{links}</ul></div>'
            )

    # ── 본문 조립 ──
    toc_html = _build_toc_html(toc)
    faq_html = _build_faq_html(faq_list)

    content_parts = [
        # 도입 요약 박스 (AI 스니펫용)
        '<div class="summary-box" style="background:#e8f0fe;border-left:4px solid #1a73e8;'
        'padding:16px 20px;margin:0 0 24px;border-radius:4px;">',
        f'<p style="font-weight:bold;margin:0 0 4px;color:#1a3a5c;">📌 핵심 요약</p>',
        f'<p style="margin:0;">{intro}</p>',
        '</div>',
        toc_html,
        '\n'.join(section_htmls),
        faq_html,
        internal_links_html,
        # 면책 고지
        '<p style="font-size:11px;color:#9ca3af;margin-top:40px;border-top:1px solid #e5e7eb;padding-top:12px;">'
        '※ 본 글은 투자 참고용 정보이며, 투자 권유가 아닙니다. 투자 결정은 본인의 판단과 책임 하에 이루어져야 합니다.'
        '</p>',
    ]
    content = '\n'.join(content_parts)

    return {
        'title':            seo_title,
        'content':          content,
        'seo_title':        seo_title,
        'meta_description': meta_desc,
        'focus_keyword':    focus_keyword,
        'slug':             slug,
        'tags':             tags,
        'faq_list':         faq_list,
    }
