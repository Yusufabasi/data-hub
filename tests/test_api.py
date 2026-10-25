import pytest
from fastapi.testclient import TestClient

from data_hub.api import create_app

TOKENS = {
    "admin-token-1": {"user": "ada", "role": "admin"},
    "finance-token-1": {"user": "amina", "role": "finance"},
    "viewer-token-1": {"user": "vera", "role": "viewer"},
}


@pytest.fixture
def client(db, rules):
    return TestClient(create_app(db, TOKENS, rules))


def _ask(client, token, question):
    return client.post(
        "/ask", json={"question": question}, headers={"Authorization": f"Bearer {token}"}
    )


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer wrong-token-0"},
        {"Authorization": "Basic finance-token-1"},
        {"Authorization": "finance-token-1"},
        {"Authorization": "Bearer "},
    ],
)
def test_missing_or_bad_credentials_are_401(client, headers):
    assert (
        client.post("/ask", json={"question": "how many customers"}, headers=headers).status_code
        == 401
    )


def test_finance_gets_rows_and_the_sql(client):
    body = _ask(client, "finance-token-1", "what was revenue last month").json()

    assert body["ok"] and body["role"] == "finance"
    assert body["rows"][0][0] > 0
    assert "payments" in body["sql"].lower()


def test_viewer_asking_for_money_gets_a_refusal_that_leaks_nothing(client):
    response = _ask(client, "viewer-token-1", "what was revenue last month")

    assert response.status_code == 200
    body = response.json()
    assert not body["ok"] and body["rows"] == [] and body["sql"] is None
    assert "payments" not in response.text.lower() and "amount_usd" not in response.text.lower()


def test_hidden_personal_data_never_appears_for_finance(client):
    response = _ask(client, "finance-token-1", "list customer phone numbers")

    assert not response.json()["ok"]
    assert "+243" not in response.text and "phone" not in response.text.lower()


def test_audit_is_admin_only_and_records_questions(client):
    _ask(client, "finance-token-1", "how many customers")

    assert (
        client.get("/audit", headers={"Authorization": "Bearer finance-token-1"}).status_code == 403
    )
    assert client.get("/audit").status_code == 401
    entries = client.get("/audit", headers={"Authorization": "Bearer admin-token-1"}).json()
    assert entries[0]["user"] == "amina" and entries[0]["question"] == "how many customers"


def test_overlong_question_is_rejected_before_anything_runs(client):
    assert _ask(client, "admin-token-1", "x" * 501).status_code == 422


def test_health_and_page_need_no_token(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    page = client.get("/")
    assert page.status_code == 200 and "Data Hub" in page.text


@pytest.mark.parametrize(
    "tokens",
    [
        {"short": {"user": "a", "role": "admin"}},
        {"long-enough-token": {"user": "a", "role": "root"}},
        {"long-enough-token": {"user": "", "role": "admin"}},
    ],
)
def test_weak_or_malformed_tokens_are_refused_at_startup(db, rules, tokens):
    with pytest.raises(ValueError):
        create_app(db, tokens, rules)
