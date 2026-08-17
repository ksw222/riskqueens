from fastapi.testclient import TestClient

import main
from services import ai_report


class BrokenSession:
    def query(self, *args, **kwargs):
        raise OSError("database is unavailable")


def broken_db():
    yield BrokenSession()


def test_import_and_public_assets():
    client = TestClient(main.app)
    assert client.get("/docs").status_code == 200
    assert client.get("/static/styles.css").status_code == 200
    assert client.get("/", follow_redirects=False).status_code in (302, 307)


def test_dashboard_survives_database_failure_and_none_beneish():
    main.app.dependency_overrides[main.get_db] = broken_db
    try:
        response = TestClient(main.app).get("/company/003230")
    finally:
        main.app.dependency_overrides.clear()
    assert response.status_code == 200
    assert 'data-count="-"' in response.text


def test_probability_is_presented_as_percent(monkeypatch):
    data = main._fallback_data("003230")
    data["default_prob"] = 0.6
    data["insolvency_data"] = {"percent": "60.0%", "status": "위험"}
    monkeypatch.setattr(main, "resolve_stock_code", lambda corp_id, db: corp_id)
    monkeypatch.setattr(main, "get_company_detail", lambda code, db: data)
    response = TestClient(main.app).get("/company/003230")
    assert response.status_code == 200
    assert "60.0%" in response.text


def test_ai_key_absence_and_html_sanitization(monkeypatch):
    monkeypatch.setattr(ai_report.settings, "OPENAI_API_KEY", None)
    assert "OPENAI_API_KEY" in ai_report.generate_report({})
    assert "<script>" not in ai_report._safe_html("# ok\n<script>alert(1)</script>")
