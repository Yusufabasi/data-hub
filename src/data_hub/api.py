"""HTTP API and question page.

Run:  HUB_DB=hub.db HUB_TOKENS='{"<token>": {"user": "amina", "role": "finance"}}' \
      uvicorn --factory data_hub.api:app_from_env

Tokens come from the environment. This is a demo-grade scheme (static bearer tokens); a real
deployment would put the company's SSO in front and map identities to roles.
"""

from __future__ import annotations

import hmac
import json
import os
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from data_hub.generate import AnthropicGenerator, RuleBasedGenerator, SqlGenerator
from data_hub.policy import ROLES
from data_hub.service import MAX_QUESTION_CHARS, ask, read_audit

STATIC = Path(__file__).with_name("static")


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)


def create_app(
    db_path: Path, tokens: dict[str, dict[str, str]], generator: SqlGenerator
) -> FastAPI:
    for token, principal in tokens.items():
        if principal.get("role") not in ROLES or not principal.get("user") or len(token) < 8:
            raise ValueError("each token needs a user, a known role, and at least 8 characters")

    app = FastAPI(title="Data Hub", docs_url=None, redoc_url=None)

    def principal(authorization: str | None = Header(default=None)) -> dict[str, str]:
        scheme, _, supplied = (authorization or "").partition(" ")
        if scheme.lower() == "bearer" and supplied:
            for token, who in tokens.items():
                if hmac.compare_digest(token.encode(), supplied.encode()):
                    return who
        raise HTTPException(status_code=401, detail="missing or invalid token")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html")

    @app.post("/ask")
    def ask_endpoint(body: AskRequest, who: dict[str, str] = Depends(principal)) -> dict:
        answer = ask(body.question, who["role"], who["user"], db_path, generator)
        return {
            "ok": answer.ok,
            "role": who["role"],
            "sql": answer.sql,
            "columns": answer.columns,
            "rows": answer.rows,
            "truncated": answer.truncated,
            "error": answer.error,
        }

    @app.get("/audit")
    def audit(who: dict[str, str] = Depends(principal)) -> list[dict]:
        if who["role"] != "admin":
            raise HTTPException(status_code=403, detail="admin only")
        return read_audit(db_path)

    return app


def app_from_env() -> FastAPI:
    generator: SqlGenerator = (
        AnthropicGenerator(os.environ.get("HUB_MODEL", "claude-haiku-5-5"))
        if os.environ.get("HUB_GENERATOR") == "anthropic"
        else RuleBasedGenerator()
    )
    return create_app(Path(os.environ["HUB_DB"]), json.loads(os.environ["HUB_TOKENS"]), generator)
