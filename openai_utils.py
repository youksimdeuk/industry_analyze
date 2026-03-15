"""
openai_utils.py — OpenAI 호출 공통 유틸
"""

import json
import re
from openai import OpenAI
from config import OPENAI_API_KEY

openai_client = OpenAI(api_key=OPENAI_API_KEY, timeout=180.0, max_retries=0)
OPENAI_MODEL   = 'gpt-5-mini'
FALLBACK_MODEL = 'gpt-5-mini'


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
                print(f"  [OpenAI] {m} {attempt}/3 실패: {e}")
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
                    print(f"  [OpenAI JSON] {model} {attempt}/3 실패: {e}")
    return {}


def _slugify(text):
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    return text.strip('-')[:80]
