"""
industry_blog_generator.py — 블로그용 산업분석 요약 포스트 생성

산업 특성에 따라 GPT가 섹션 구조를 동적으로 설계.
(반도체 → 공급망/수율/HBM, 바이오 → 임상/FDA/파이프라인 등)
WP 전체 분석 링크로 블로그 → WordPress 유입 유도.
"""

import json
from openai import OpenAI
from config import OPENAI_API_KEY

openai_client = OpenAI(api_key=OPENAI_API_KEY, timeout=120.0, max_retries=0)
BLOG_MODEL = 'gpt-5-mini'


# =====================================================
# GPT: 구조 설계 + 내용 생성 (1-shot)
# =====================================================

def _generate_blog_content(industry_name, deep_research_text, focus_keyword):
    """
    딥리서치 원문을 분석해 이 산업에 맞는 블로그 섹션을 동적 설계하고 내용까지 생성.
    반환: dict
    """
    prompt = f"""당신은 투자 블로그 에디터입니다.
아래 '{industry_name}' 산업 딥리서치 원문을 읽고, 이 산업의 특성에 맞는 블로그 요약 포스트를 설계하고 작성하세요.

딥리서치 원문 (앞 5000자):
{deep_research_text[:5000]}

규칙:
1. 도입부(2~3문장): '{focus_keyword}'를 자연스럽게 포함, {industry_name}을 2회 이상 언급, 구체적 수치 1개 이상, 구어체
2. 섹션 3~5개: 이 산업의 핵심 이슈에 맞게 직접 설계 (고정 템플릿 금지)
   - 예) 반도체: 공급망/수율/HBM/AI수요 등
   - 예) 바이오: 임상단계/FDA승인/파이프라인 등
   - 예) 2차전지: 소재/완성차 협력/중국경쟁 등
   - 각 섹션 제목에 어울리는 이모지 1개 포함
   - 각 섹션 내용: 2~4개 불릿, 구체적 수치/기업명/국가 포함
3. 마무리_질문(1문장): 독자 의견 유도, {industry_name} 포함, "~어떻게 보시나요?" 형식

JSON으로만 반환:
{{
  "도입부": "...",
  "섹션": [
    {{
      "제목": "🚀 섹션 제목",
      "불릿": ["내용1", "내용2", "내용3"]
    }},
    ...
  ],
  "마무리_질문": "..."
}}"""

    for attempt in range(1, 4):
        try:
            resp = openai_client.chat.completions.create(
                model=BLOG_MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                max_completion_tokens=3000,
            )
            text = resp.choices[0].message.content.strip()
            start, end = text.find('{'), text.rfind('}')
            if start != -1 and end > start:
                return json.loads(text[start:end + 1])
        except Exception as e:
            print(f"  [블로그] GPT {attempt}/3 실패: {e}")
    return {}


# =====================================================
# 블로그 포스트 조립
# =====================================================

def generate_blog_post(
    industry_name: str,
    deep_research_text: str,
    focus_keyword: str,
    tags: list,
    wp_url: str,
    period_key: str,
) -> str:
    """
    블로그용 산업분석 요약 포스트 생성.
    반환: plain text (붙여넣기용)
    """
    print(f"  [블로그] 산업 특성 기반 구조 설계 중...")
    data = _generate_blog_content(industry_name, deep_research_text, focus_keyword)

    if not data:
        print("  [블로그] 생성 실패 — 스킵")
        return ''

    intro      = data.get('도입부', '').strip()
    sections   = data.get('섹션', [])
    closing_q  = data.get('마무리_질문', f'{industry_name} 전망을 어떻게 보시나요?').strip()

    hashtags = ' '.join(
        f'#{t}' for t in ([industry_name, '산업분석', '투자', '주식', '전망'] + (tags or []))[:15]
    )

    L = []

    L.append(f"📊 {industry_name} 전망 | {period_key} 산업분석 요약")
    L.append("")

    if intro:
        L.append(intro)
        L.append("")

    for sec in sections:
        title  = sec.get('제목', '').strip()
        bullets = sec.get('불릿', [])
        if not title:
            continue
        L.append(title)
        L.append("")
        for b in bullets:
            L.append(f"  • {b.strip()}")
        L.append("")

    L.append(f"{industry_name} 전망은 글로벌 수요 흐름과 정책 변화에 따라 달라질 수 있습니다.")
    L.append(closing_q)
    L.append("")

    if wp_url:
        L.append(f"🔗 {industry_name} 전체 산업분석 보기")
        L.append(f"👉 {wp_url}")
        L.append("")

    L.append(hashtags)

    return "\n".join(L)
