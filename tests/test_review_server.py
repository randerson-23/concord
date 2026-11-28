"""The local review server (item 16d): `handle` tested directly, plus one socket smoke test."""

from __future__ import annotations

import json
import threading
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import pytest
from test_review import folder  # noqa: F401  (fixture)

from concord.review import card_ids
from concord.review_server import MAX_BODY, handle, make_server

TOKEN = "tok-123"
PORT = 5555
NOW = datetime(2026, 11, 28, 12, 30, 5, tzinfo=UTC)
HOST = {"host": f"127.0.0.1:{PORT}"}


def _req(root: Path, method: str, target: str, body: bytes = b"", headers=HOST):
    return handle(method, target, headers, body, root=root, token=TOKEN, port=PORT, now=NOW)


def _post(root: Path, path: str, **fields: str):
    body = urllib.parse.urlencode(fields).encode()
    return _req(root, "POST", f"{path}?t={TOKEN}", body)


def _cards(root: Path) -> list[str]:
    return card_ids(json.loads((root / "review.json").read_text()))


def _decisions(root: Path) -> dict:
    return json.loads((root / "decisions.json").read_text())


def test_page_has_a_form_per_card_and_escapes(folder: Path) -> None:  # noqa: F811
    status, headers, body = _req(folder, "GET", f"/?t={TOKEN}")
    html = body.decode()
    assert status == 200 and headers["Content-Type"].startswith("text/html")
    assert html.count('action="/decide?t=tok-123"') == len(_cards(folder))
    assert 'href="style.css?t=tok-123"' in html and "/apply?t=tok-123" in html
    assert "<script>" not in html
    css = _req(folder, "GET", f"/style.css?t={TOKEN}")
    assert css[0] == 200 and b".card" in css[2]


def test_accept_reject_and_correct_write_decisions_json(folder: Path) -> None:  # noqa: F811
    a, b, c = _cards(folder)[:3]
    r = _post(folder, "/decide", card=a, decision="accept", reviewer="ryan", note="ok")
    assert r[0] == 303 and r[1]["Location"] == f"/?t={TOKEN}"
    _post(folder, "/decide", card=b, decision="reject", reviewer="ryan")
    _post(
        folder, "/decide", card=c, decision="correct", reviewer="ryan", field="fix_tag", value="7"
    )
    d = _decisions(folder)
    assert d[a] == {
        "decision": "accept",
        "reviewer": "ryan",
        "at": "2026-11-28T12:30:05Z",
        "note": "ok",
    }
    assert d[b]["decision"] == "reject" and "corrections" not in d[b]
    assert d[c]["corrections"] == {"fix_tag": "7"}
    # deciding again changes only that card
    _post(folder, "/decide", card=a, decision="reject", reviewer="sam")
    d2 = _decisions(folder)
    assert d2[a]["decision"] == "reject" and d2[b] == d[b] and d2[c] == d[c]
    assert "Decision: reject" in _req(folder, "GET", f"/?t={TOKEN}")[2].decode()


def test_bad_requests_name_the_field(folder: Path) -> None:  # noqa: F811
    card = _cards(folder)[0]
    assert _post(folder, "/decide", card="nope", decision="accept", reviewer="r")[0] == 400
    assert b"card:" in _post(folder, "/decide", card="nope", decision="accept", reviewer="r")[2]
    assert b"decision:" in _post(folder, "/decide", card=card, decision="maybe", reviewer="r")[2]
    assert b"reviewer:" in _post(folder, "/decide", card=card, decision="accept", reviewer=" ")[2]
    assert b"field:" in _post(folder, "/decide", card=card, decision="correct", reviewer="r")[2]
    assert not (folder / "decisions.json").exists()


def test_token_host_size_and_unknown_routes(folder: Path) -> None:  # noqa: F811
    assert _req(folder, "GET", "/")[0] == 403
    assert _req(folder, "GET", "/?t=wrong")[0] == 403
    assert _req(folder, "POST", "/decide", b"card=x")[0] == 403
    assert (
        _req(folder, "GET", f"/site/index.html?t={TOKEN}", headers={"host": "evil.test"})[0] == 400
    )
    assert _req(folder, "GET", f"/?t={TOKEN}", headers={"host": f"localhost:{PORT + 1}"})[0] == 400
    assert _req(folder, "GET", f"/?t={TOKEN}", headers={"host": f"localhost:{PORT}"})[0] == 200
    big = b"a" * (MAX_BODY + 1)
    assert _req(folder, "POST", f"/decide?t={TOKEN}", big)[0] == 413
    assert _req(folder, "GET", f"/nothing?t={TOKEN}")[0] == 404
    assert _req(folder, "DELETE", f"/?t={TOKEN}")[0] == 404
    assert _req(folder, "POST", f"/other?t={TOKEN}")[0] == 404


def test_paths_cannot_leave_the_folder(folder: Path, tmp_path: Path) -> None:  # noqa: F811
    secret = tmp_path / "secret.txt"
    secret.write_text("top secret")
    (folder / "site" / "leak").symlink_to(secret)
    for rel in ("../review.json", "../../secret.txt", "leak", "%2e%2e/review.json"):
        status, _, body = _req(folder, "GET", f"/site/{rel}?t={TOKEN}")
        assert status == 404 and b"secret" not in body
    status, headers, body = _req(folder, "GET", f"/site/index.html?t={TOKEN}")
    assert status == 200 and headers["Content-Type"].startswith("text/html")
    assert _req(folder, "GET", f"/site/?t={TOKEN}")[0] == 200  # the folder's index.html


def test_apply_rebuilds_and_a_second_apply_is_byte_identical(folder: Path) -> None:  # noqa: F811
    items = json.loads((folder / "review.json").read_text())
    lint = _cards(folder)[next(i for i, it in enumerate(items) if it["reason"] == "lint_error")]
    _post(folder, "/decide", card=lint, decision="accept", reviewer="ryan")
    before = (folder / "spec.json").read_bytes()
    assert _req(folder, "POST", f"/apply?t={TOKEN}")[0] == 303
    after = (folder / "spec.json").read_bytes()
    assert after != before and b'"accepted"' in after
    snap = {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file()}
    _req(folder, "POST", f"/apply?t={TOKEN}")
    assert snap == {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file()}
    html = _req(folder, "GET", f"/?t={TOKEN}")[2].decode()
    assert "Last apply: 1 applied" in html


def test_smoke_over_a_real_socket(folder: Path) -> None:  # noqa: F811
    server, token = make_server(folder, 0)
    assert server.server_address[0] == "127.0.0.1"
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{port}"
        with urllib.request.urlopen(f"{base}/?t={token}", timeout=10) as resp:
            assert resp.status == 200 and b"Review" in resp.read()
        with pytest.raises(urllib.error.HTTPError) as err:
            urllib.request.urlopen(f"{base}/", timeout=10)
        assert err.value.code == 403
        card = _cards(folder)[0]
        data = urllib.parse.urlencode(
            {"card": card, "decision": "accept", "reviewer": "ryan"}
        ).encode()
        with urllib.request.urlopen(f"{base}/decide?t={token}", data, timeout=10) as resp:
            assert resp.status == 200  # urllib followed the 303 back to the page
        assert _decisions(folder)[card]["decision"] == "accept"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
