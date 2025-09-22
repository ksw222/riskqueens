import time
from openai import OpenAI, RateLimitError, APIStatusError
from db import settings
import markdown

client = OpenAI(api_key=settings.OPENAI_API_KEY, base_url=settings.OPENAI_API_BASE)
MODEL = settings.OPENAI_MODEL or "gpt-4o-mini"

SYSTEM_PROMPT = """\
당신은 제1금융권 은행에서 여신사후관리를 맡고있는 전문 재무 애널리스트입니다. 한국어로 간결하고 읽기 쉬운 보고서를 작성하세요.
- 톤: 중립, 요약 위주, 불필요한 수사는 배제
- 섹션: 핵심요약(3~5줄) / 부실위험평가 / 지표진단 / 리스크 요인 / 시사점
- 표기: 수치는 단위와 함께 표기(%, 배), 출처는 '내부 산출'로 명시
"""

# ai_report.py


def generate_report(data: dict) -> str:
    user_prompt = build_user_prompt(
        data.get("company_info", {}),
        data.get("insolvency_data", {}),
        data.get("risk_factor", {}),
        data.get("benchmark", {}),
    )

    for attempt in range(3):
        try:
            resp = client.responses.create(
                model=MODEL,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_output_tokens=550,
            )
            md_text = (resp.output_text or "").strip()
            # 마크다운 → HTML 변환
            html = markdown.markdown(md_text, extensions=["fenced_code", "tables"])
            return html

        except Exception as e:
            return f"[오류] 보고서 생성 중 예외 발생: {e}"


def build_user_prompt(company_info: dict, insolvency_data: dict, risk_factor: dict, benchmark: dict) -> str:
    name = company_info.get("company_name") or "-"
    ticker = company_info.get("ticker") or "-"
    market = company_info.get("market_type") or "-"
    founded = company_info.get("founded_year") or "-"
    prob = insolvency_data.get("percent") or "-"
    status = insolvency_data.get("status") or "-"
    icr = (risk_factor or {}).get("이자보상배율", "-")
    debt = (risk_factor or {}).get("부채비율", "-")
    roa  = (risk_factor or {}).get("ROA", "-")
    cat_names = [c["name"] for c in (benchmark or {}).get("categories", [])]

    return f"""회사: {name} ({ticker}, {market}, 설립연도 {founded})
부실확률: {prob} / 상태: {status}
핵심 지표: 이자보상배율 {icr}, 부채비율 {debt}, ROA {roa}
벤치마크 카테고리: {", ".join(cat_names) if cat_names else "-"}
요청: 위 정보를 바탕으로 섹션 구조에 맞춘 400~700자 내외의 요약 보고서를 작성.
불확실한 값은 추정하지 말고 '데이터 없음'이라고 표시.
"""

def generate_report(data: dict) -> str:
    user_prompt = build_user_prompt(
        data.get("company_info", {}),
        data.get("insolvency_data", {}),
        data.get("risk_factor", {}),
        data.get("benchmark", {}),
    )

    # 간단 백오프 재시도
    for attempt in range(3):
        try:
            resp = client.responses.create(
                model=MODEL,
                input=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_output_tokens=550,   # 테스트 땐 낮춰 비용/리밋 완화
            )
            return (resp.output_text or "").strip()

        except RateLimitError as e:
            # 순간적인 초과일 때만 재시도. 잔액 부족이면 아래 메시지로 빠짐.
            if "insufficient_quota" in str(e).lower():
                return ("[알림] OpenAI 프로젝트의 크레딧/요금 한도가 부족해 보고서를 생성할 수 없습니다. "
                        "Billing에서 결제수단 또는 크레딧을 추가하고, 키가 올바른 프로젝트에 속해 있는지 확인하세요.")
            # 429이지만 일시적일 수 있으니 짧게 대기 후 재시도
            time.sleep(1 + attempt)

        except APIStatusError as e:
            # 기타 4xx/5xx
            return f"[오류] OpenAI 호출 실패: {e.status_code} {getattr(e, 'message', '')}".strip()

        except Exception as e:
            return f"[오류] 보고서 생성 중 예외 발생: {e}"

    return "[오류] 일시적인 제한으로 보고서 생성에 실패했습니다. 잠시 후 다시 시도하세요."

    # # SDK 버전에 따라 안전 추출
    # try:
    #     return resp.output_text.strip()
    # except Exception:
    #     if hasattr(resp, "choices") and resp.choices:
    #         msg = getattr(resp.choices[0], "message", None)
    #         if msg and getattr(msg, "content", None):
    #             return msg.content.strip()
    #     return ""
