import logging
import time

import bleach
import markdown
from openai import APIStatusError, OpenAI, RateLimitError

from db import settings

logger = logging.getLogger(__name__)
MODEL = settings.OPENAI_MODEL or "gpt-4o-mini"
SYSTEM_PROMPT = "You are a financial risk analyst. Write a concise Korean report based only on supplied data."
ALLOWED_TAGS = set(bleach.sanitizer.ALLOWED_TAGS) | {
    "p", "br", "h1", "h2", "h3", "h4", "table", "thead", "tbody", "tr", "th", "td", "pre", "code"
}
ALLOWED_ATTRIBUTES = {"a": ["href", "title", "rel"], "td": ["colspan", "rowspan"], "th": ["colspan", "rowspan"]}


def _build_user_prompt(data: dict) -> str:
    company = data.get("company_info", {}) or {}
    insolvency = data.get("insolvency_data", {}) or {}
    return (
        f"회사: {company.get('company_name', '-') } ({company.get('ticker', '-')})\n"
        f"부실확률: {insolvency.get('percent', '-')} / 상태: {insolvency.get('status', '-')}\n"
        "400~700자 분량으로 요약, 위험 요인, 시사점을 작성하세요. 데이터가 없으면 추정하지 마세요."
    )


def _safe_html(markdown_text: str) -> str:
    rendered = markdown.markdown(markdown_text, extensions=["fenced_code", "tables"])
    return bleach.clean(rendered, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, protocols=["http", "https", "mailto"], strip=True)


def generate_report(data: dict) -> str:
    """Generate and sanitize an AI report; unavailable AI never prevents app operation."""
    api_key = (settings.OPENAI_API_KEY or "").strip()
    if not api_key:
        return "<p class='muted'>AI 리포트는 현재 사용할 수 없습니다. OPENAI_API_KEY를 설정해 주세요.</p>"

    # Create the client only when this feature is actually invoked.
    client = OpenAI(api_key=api_key, base_url=settings.OPENAI_API_BASE)
    for attempt in range(3):
        try:
            response = client.responses.create(
                model=MODEL,
                input=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": _build_user_prompt(data)}],
                max_output_tokens=550,
            )
            return _safe_html((response.output_text or "").strip())
        except RateLimitError:
            time.sleep(1 + attempt)
        except APIStatusError as exc:
            logger.warning("OpenAI returned status %s", exc.status_code)
            return "<p class='error'>AI 리포트를 지금 생성할 수 없습니다. 잠시 후 다시 시도해 주세요.</p>"
        except Exception:
            logger.exception("AI report generation failed")
            return "<p class='error'>AI 리포트를 지금 생성할 수 없습니다. 잠시 후 다시 시도해 주세요.</p>"
    return "<p class='error'>AI 요청이 제한되었습니다. 잠시 후 다시 시도해 주세요.</p>"
