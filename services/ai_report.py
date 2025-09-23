# ai_report.py
import time
import markdown
from openai import OpenAI, RateLimitError, APIStatusError
from db import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_API_BASE)
MODEL = settings.OPENAI_MODEL or "gpt-4o-mini"

SYSTEM_PROMPT = (
    "당신은 제1금융권 은행 여신사후관리 애널리스트입니다. 한국어로 간결한 보고서를 작성하세요.\n"
    "- 톤: 중립, 요약 위주\n"
    "- 섹션: 핵심요약(3~5줄) / 부실위험평가 / 지표진단 / 리스크 요인 / 시사점\n"
    "- 표기: 수치에 단위(%, 배), 출처 '내부 산출'\n"
)

def _build_user_prompt(data: dict) -> str:
    ci  = data.get("company_info", {}) or {}
    ins = data.get("insolvency_data", {}) or {}
    rf  = data.get("risk_factor", {}) or {}
    bm  = data.get("benchmark", {}) or {}

    name    = ci.get("company_name", "-")
    ticker  = ci.get("ticker", "-")
    market  = ci.get("market_type", "-")
    founded = ci.get("founded_year", "-")

    prob   = ins.get("percent", "-")
    status = ins.get("status", "-")

    icr  = rf.get("이자보상배율", "-")
    debt = rf.get("부채비율", "-")
    roa  = rf.get("ROA", "-")

    cats = ", ".join([c["name"] for c in bm.get("categories", [])]) or "-"

    return (
        f"회사: {name} ({ticker}, {market}, 설립연도 {founded})\n"
        f"부실확률: {prob} / 상태: {status}\n"
        f"핵심 지표: 이자보상배율 {icr}, 부채비율 {debt}, ROA {roa}\n"
        f"벤치마크 카테고리: {cats}\n"
        "요청: 위 정보를 바탕으로 400~700자 내외의 요약 보고서를 섹션 구조에 맞춰 작성. "
        "불확실한 값은 추정하지 말고 '데이터 없음'으로 표기."
    )

def generate_report(data: dict) -> str:
    """보고서 HTML을 반환합니다."""
    user_prompt = _build_user_prompt(data)

    for attempt in range(3):
        try:
            resp = client.responses.create(
                model=MODEL,
                input=[{"role": "system", "content": SYSTEM_PROMPT},
                       {"role": "user",   "content": user_prompt}],
                max_output_tokens=550,
            )
            md = (resp.output_text or "").strip()
            return markdown.markdown(md, extensions=["fenced_code", "tables"])

        except RateLimitError as e:
            if "insufficient_quota" in str(e).lower():
                return "<p class='muted'>[알림] 크레딧/요금 한도 부족으로 보고서를 생성할 수 없습니다.</p>"
            time.sleep(1 + attempt)
        except APIStatusError as e:
            return f"<p class='error'>[오류] OpenAI 호출 실패: {e.status_code}</p>"
        except Exception as e:
            return f"<p class='error'>[오류] 보고서 생성 중 예외: {e}</p>"

    return "<p class='error'>[오류] 일시적 제한으로 실패했습니다.</p>"
