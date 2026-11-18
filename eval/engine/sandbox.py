"""Sandbox client: in-memory API only. Never hits production or real SMS/payments."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from fastapi.testclient import TestClient

from app.main import app
from app.store import store

FORBIDDEN_HOST_FRAGMENTS = (
    "accessla.org",
    "stripe.com",
    "twilio.com",
    "sendgrid.com",
    "livekit.cloud",
)

PRODUCTION_API_HOST = "access-la-flexagents-api.vercel.app"


@contextmanager
def sandbox_client(*, allow_prod: bool = False) -> Iterator[TestClient]:
    """Yield a TestClient against the local FastAPI app with a fresh store.

    Chaos is forced off. Admin reset is available for isolation between runs.
    """

    if allow_prod:
        raise RuntimeError(
            "Production / live customer channels are blocked in automated evals."
        )
    store.reset()
    with TestClient(app) as client:
        client.headers.update({"X-Spectac-Chaos": "off"})
        yield client
    store.reset()


def assert_not_production_url(url: str) -> None:
    lowered = (url or "").lower()
    if PRODUCTION_API_HOST in lowered and "sandbox" not in lowered:
        # Local TestClient paths are relative; absolute prod URLs are rejected.
        raise RuntimeError(f"Blocked production URL in eval: {url}")
    for fragment in FORBIDDEN_HOST_FRAGMENTS:
        if fragment in lowered:
            raise RuntimeError(f"Blocked external host in eval: {url}")


def is_destructive_path(method: str, path: str) -> bool:
    method_u = method.upper()
    path_l = path.lower()
    if method_u == "POST" and path_l.rstrip("/").endswith("/admin/reset"):
        # Allowed only as an explicit sandbox fixture, never as an agent tool.
        return True
    if method_u in {"DELETE"} and "/cases/" in path_l:
        return True
    return False
