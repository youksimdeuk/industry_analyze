"""
industry_wp_en_generator.py — 영어 산업분석 WordPress 아티클 생성
SEO + AEO (Answer Engine Optimization) 적용 — Foreign investor perspective
"""

import json
import re
from openai import OpenAI
from config import OPENAI_API_KEY

openai_client = OpenAI(api_key=OPENAI_API_KEY, timeout=180.0, max_retries=0)
OPENAI_MODEL   = 'gpt-5-mini'
FALLBACK_MODEL = 'gpt-5-mini'


# =====================================================
# 유틸
# =====================================================

def _call_openai(prompt, max_tokens=16000, model=None):
    primary = model or OPENAI_MODEL
    models_to_try = [primary] if primary == FALLBACK_MODEL else [primary, FALLBACK_MODEL]
    for m in models_to_try:
        for attempt in range(1, 4):
            try:
                resp = openai_client.chat.completions.create(
                    model=m,
                    messages=[{"role": "user", "content": prompt}],
                    max_completion_tokens=max_tokens,
                )
                return resp.choices[0].message.content.strip()
            except Exception as e:
                print(f"  [OpenAI] {m} {attempt}/3 failed: {e}")
    return ''


def _call_openai_json(prompt, max_tokens=6000):
    for model in [OPENAI_MODEL, FALLBACK_MODEL]:
        for use_json in (True, False):
            for attempt in range(1, 4):
                try:
                    kwargs = {
                        'model': model,
                        'messages': [{"role": "user", "content": prompt}],
                        'max_completion_tokens': max_tokens,
                    }
                    if use_json:
                        kwargs['response_format'] = {"type": "json_object"}
                    resp = openai_client.chat.completions.create(**kwargs)
                    text = resp.choices[0].message.content.strip()
                    start, end = text.find('{'), text.rfind('}')
                    if start != -1 and end > start:
                        return json.loads(text[start:end + 1])
                except Exception as e:
                    print(f"  [OpenAI JSON] {model} {attempt}/3 failed: {e}")
    return {}


def _slugify(text):
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    return text.strip('-')[:80]


# =====================================================
# Step 1: GPT 목차 설계 (EN)
# =====================================================

def generate_toc_en(industry_name, deep_research_text):
    """Generate dynamic EN TOC based on deep research content"""
    prompt = f"""You are an SEO/AEO expert editor targeting global equity investors.
Analyze the deep research content about '{industry_name}' and design an optimal blog article structure.

IMPORTANT: All output must be in English only. Do not use Korean or any other language.
The industry name may be in Korean — translate it conceptually and use English equivalents in all titles.

Rules:
1. Create 5–8 H2 sections tailored to this specific industry (no fixed templates)
2. Add 1–3 H3 subsections under H2 where needed
3. Must include: Investment Thesis (or Catalysts), Key Risks, FAQ
4. SEO: arrange sections to match informational + commercial search intent
5. AEO: include clear Q&A structure that AI engines can cite
6. Each section: include an anchor id (lowercase hyphen)
7. All section titles, subtitles, and FAQ topics must be in English — no Korean characters allowed

Deep research content (first 3000 chars):
{deep_research_text[:3000]}

Return JSON only:
{{
  "toc": [
    {{"h2": "Section Title", "anchor": "section-anchor", "h3": ["Subsection1", "Subsection2"]}},
    ...
  ],
  "faq_topics": ["FAQ topic 1", "FAQ topic 2", "FAQ topic 3", "FAQ topic 4", "FAQ topic 5"]
}}"""
    result = _call_openai_json(prompt, max_tokens=4000)
    return result.get('toc', []), result.get('faq_topics', [])


# =====================================================
# Step 2: SEO/AEO 메타 (EN)
# =====================================================

def generate_seo_meta_en(industry_name, toc, deep_research_text):
    """Generate EN SEO metadata"""
    toc_summary = ' > '.join([s.get('h2', '') for s in toc])
    prompt = f"""Generate SEO metadata for an English-language blog article about the '{industry_name}' industry,
targeting global equity investors.

IMPORTANT: All output must be in English only. Do not use Korean anywhere.
The industry name may be in Korean — translate it to English for the title, keyword, and slug.

TOC structure: {toc_summary}

Deep research excerpt (first 1000 chars):
{deep_research_text[:1000]}

Rules:
- focus_keyword: high-search-volume English keyword (e.g. "HBM memory market outlook 2025") — English only
- seo_title: under 60 chars, English only, focus_keyword near the front, include year
- meta_description: under 155 chars, include focus_keyword, include a compelling CTA
- slug: lowercase English with hyphens, max 50 chars
- tags: 10–15 tags covering industry, technology, countries, companies, themes

Return JSON only:
{{
  "focus_keyword": "...",
  "seo_title": "...",
  "meta_description": "...",
  "slug": "...",
  "tags": ["tag1", "tag2", ...]
}}"""
    return _call_openai_json(prompt, max_tokens=1000)


# =====================================================
# Step 3: 본문 섹션별 생성 (EN)
# =====================================================

def _build_toc_html_en(toc):
    """TOC HTML block with anchor links"""
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

    return (
        '<div class="toc-box" style="background:#f0f4f8;border-left:4px solid #1a3a5c;'
        'padding:16px 20px;margin:24px 0;border-radius:4px;">'
        '<p style="font-weight:bold;margin:0 0 8px;color:#1a3a5c;">📋 Table of Contents</p>'
        f'<ul style="margin:0;padding-left:20px;">{"".join(items)}</ul>'
        '</div>'
    )


def _build_faq_html_en(faq_list):
    """FAQ HTML block (AEO optimized)"""
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
        '<h2 style="margin-top:0;color:#1a3a5c;">Frequently Asked Questions</h2>'
        + ''.join(items) +
        '</div>'
    )


def generate_intro_en(industry_name, deep_research_text, focus_keyword):
    """Executive summary / intro paragraph — AI snippet optimized"""
    prompt = f"""Write a 3-sentence introduction for an English blog article about '{industry_name}' industry analysis,
targeting global equity investors.

IMPORTANT: Write in English only. Do not use Korean.

Rules:
- Include '{focus_keyword}' within the first 100 characters of sentence 1
- Deliver a direct, factual answer about the industry's current state (AI snippet optimization)
- Include at least one specific figure (market size, CAGR, or key metric)
- Output 3 sentences only (no headers, no extra text)

Deep research content:
{deep_research_text[:2000]}"""
    return _call_openai(prompt, max_tokens=600)


def generate_section_content_en(industry_name, section, deep_research_text, focus_keyword, images=None):
    """Generate one H2 section body (with H3 subsections)"""
    h2 = section.get('h2', '')
    h3_list = section.get('h3', [])
    anchor = section.get('anchor', _slugify(h2))

    h3_instruction = ''
    if h3_list:
        h3_instruction = f"\n- Must include these H3 subsections: {', '.join(h3_list)}"

    image_instruction = ''
    if images:
        img_lines = '\n'.join(
            f'  • Image{i + 1} (URL: {img["wp_url"]}): {img["description"]}'
            for i, img in enumerate(images)
            if img.get('wp_url') and img.get('description')
        )
        if img_lines:
            image_instruction = (
                f"\n- If any image below is relevant to this section, embed it:\n{img_lines}"
                "\n- Embed format: <figure style=\"margin:16px 0;\"><img src=\"URL\" alt=\"description\" "
                "style=\"max-width:100%;height:auto;\"><figcaption style=\"font-size:12px;"
                "color:#6b7280;text-align:center;\">description</figcaption></figure>"
            )

    prompt = f"""Write the [{h2}] section for an English '{industry_name}' industry analysis article
targeting global equity investors.

IMPORTANT: Write in English only. Do not use Korean anywhere — not in headings, paragraphs, or tables.

Rules:
- First paragraph (2–3 sentences): direct answer to what this section covers (AEO: AI citation ready)
- Include specific numbers (market size, growth rates, market share) with years
- Use HTML tables for data comparisons
- No vague generalities ("various", "continuous", etc.)
- Include insights relevant to equity investors
- Naturally include '{focus_keyword}' 1–2 times{h3_instruction}{image_instruction}
- Output in HTML (H3 as <h3>, paragraphs as <p>, tables as <table>)
- Do NOT include the H2 title tag — body only

Deep research reference:
{deep_research_text[:4000]}

Write the [{h2}] section body only:"""
    content = _call_openai(prompt, max_tokens=4000)

    return (
        f'<h2 id="{anchor}">{h2}</h2>\n'
        f'{content}\n'
    )


def generate_faq_en(industry_name, faq_topics, deep_research_text):
    """Generate FAQ Q&A pairs (AEO optimized)"""
    topics_str = '\n'.join(f'- {t}' for t in faq_topics)
    prompt = f"""Generate FAQ entries for a '{industry_name}' industry analysis article targeting global investors.

IMPORTANT: Write in English only. Do not use Korean.

FAQ topics:
{topics_str}

Rules:
- Each answer: 2–4 sentences, direct and factual (AI answer engine optimization)
- Include specific data or evidence
- No investment advice or buy/sell recommendations

Deep research reference:
{deep_research_text[:3000]}

Return JSON only:
{{"faq": [{{"q": "Question 1", "a": "Answer 1"}}, ...]}}"""
    result = _call_openai_json(prompt, max_tokens=6000)
    return result.get('faq', [])


# =====================================================
# 메인: 영어 아티클 조립
# =====================================================

def generate_en_article(industry_name, deep_research_text, related_posts=None, images=None):
    """Generate full English industry analysis article.
    Returns: dict (title, content, seo_title, meta_description, focus_keyword,
                    slug, tags, faq_list)
    images: list of {'wp_url': str, 'description': str} — WP uploaded images
    """
    print(f"  [EN] Designing TOC...")
    toc, faq_topics = generate_toc_en(industry_name, deep_research_text)
    if not toc:
        print("  [EN] TOC generation failed")
        return {}

    print(f"  [EN] Generating SEO metadata...")
    seo = generate_seo_meta_en(industry_name, toc, deep_research_text)

    focus_keyword = seo.get('focus_keyword', f'{industry_name} market outlook')
    seo_title     = seo.get('seo_title', f'{industry_name} Industry Analysis {__import__("datetime").datetime.now().year}')
    meta_desc     = seo.get('meta_description', '')
    slug          = seo.get('slug', '') or _slugify(f'{industry_name}-industry-analysis-en')
    tags          = seo.get('tags', [industry_name])

    print(f"  [EN] Generating introduction...")
    intro = generate_intro_en(industry_name, deep_research_text, focus_keyword)

    print(f"  [EN] Generating {len(toc)} sections...")
    section_htmls = []
    for i, sec in enumerate(toc, 1):
        print(f"    Section {i}/{len(toc)}: {sec.get('h2', '')}")
        section_htmls.append(
            generate_section_content_en(industry_name, sec, deep_research_text, focus_keyword, images=images)
        )

    print(f"  [EN] Generating FAQ...")
    faq_list = generate_faq_en(industry_name, faq_topics, deep_research_text)

    # ── Internal links ──
    internal_links_html = ''
    if related_posts:
        links = ''.join(
            f'<li><a href="{p.get("url", "#")}">{p.get("title", "")}</a></li>'
            for p in related_posts[:5] if p.get('title')
        )
        if links:
            internal_links_html = (
                '<div style="background:#f0f4f8;padding:16px;border-radius:6px;margin:32px 0;">'
                '<p style="font-weight:bold;margin:0 0 8px;">📌 Related Company Analysis</p>'
                f'<ul>{links}</ul></div>'
            )

    # ── Assemble content ──
    toc_html = _build_toc_html_en(toc)
    faq_html = _build_faq_html_en(faq_list)

    content_parts = [
        # Executive summary box (AI snippet)
        '<div class="summary-box" style="background:#e8f0fe;border-left:4px solid #1a73e8;'
        'padding:16px 20px;margin:0 0 24px;border-radius:4px;">',
        '<p style="font-weight:bold;margin:0 0 4px;color:#1a3a5c;">📌 Executive Summary</p>',
        f'<p style="margin:0;">{intro}</p>',
        '</div>',
        toc_html,
        '\n'.join(section_htmls),
        faq_html,
        internal_links_html,
        # Disclaimer
        '<p style="font-size:11px;color:#9ca3af;margin-top:40px;border-top:1px solid #e5e7eb;padding-top:12px;">'
        'Disclaimer: This article is for informational purposes only and does not constitute investment advice. '
        'All investment decisions should be made at the investor\'s own discretion and risk.'
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
