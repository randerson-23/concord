"""``concord review OUT_DIR --serve``: a local server for clearing review cards (item 16d, D33).

All behaviour is in :func:`handle`, a pure function of the request, so tests need no sockets; the
``http.server`` class is a thin wrapper. The server binds 127.0.0.1 only, requires a random token on
every request, checks the Host header (DNS rebinding), caps bodies at 64 KiB, and serves nothing
outside the folder. No JavaScript: the page is plain forms. Stdlib only.
"""

from __future__ import annotations

import hmac
import json
import mimetypes
import secrets
from collections.abc import Mapping
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlsplit

from concord.decisions import DECISIONS, apply_to_folder, atomic_write
from concord.review import REVIEW_CSS, card_ids, load_context, render_review
from concord.site import STYLE_CSS

MAX_BODY = 64 * 1024
Response = tuple[int, dict[str, str], bytes]


def _text(status: int, message: str) -> Response:
    return status, {"Content-Type": "text/plain; charset=utf-8"}, (message + "\n").encode()


def _redirect(token: str) -> Response:
    return 303, {"Location": f"/?t={quote(token)}", "Content-Length": "0"}, b""


def _form(body: bytes) -> dict[str, str]:
    try:
        parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    except UnicodeDecodeError as exc:
        raise ValueError("body: expected UTF-8 form data") from exc
    return {k: v[-1] for k, v in parsed.items()}


def _read_decisions(root: Path) -> dict[str, Any]:
    path = root / "decisions.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a JSON object keyed by card id")
    return data


def _page(root: Path, token: str) -> Response:
    items, pages, spec = load_context(root)
    decisions = _read_decisions(root)
    applied_file = root / "applied.json"
    applied = json.loads(applied_file.read_text()) if applied_file.is_file() else None
    reviewers = [d.get("reviewer", "") for d in decisions.values() if isinstance(d, dict)]
    live = {
        "token": token,
        "decisions": decisions,
        "applied": applied,
        "reviewer": reviewers[-1] if reviewers else "",
    }
    html = render_review(items, pages, spec, live)["index.html"]
    return 200, {"Content-Type": "text/html; charset=utf-8"}, html.encode("utf-8")


def _decide(root: Path, token: str, body: bytes, now: datetime) -> Response:
    try:
        form = _form(body)
    except ValueError as exc:
        return _text(400, str(exc))
    items, _, _ = load_context(root)
    if form.get("card") not in set(card_ids(items)):
        return _text(400, f"card: unknown card id {form.get('card')!r}")
    decision = form.get("decision", "")
    if decision not in DECISIONS:
        return _text(400, f"decision: expected one of {list(DECISIONS)}, got {decision!r}")
    reviewer = form.get("reviewer", "").strip()
    if not reviewer:
        return _text(400, "reviewer: required")
    entry: dict[str, Any] = {
        "decision": decision,
        "reviewer": reviewer,
        "at": now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if form.get("note", "").strip():
        entry["note"] = form["note"].strip()
    if decision == "correct":
        field_name, value = form.get("field", "").strip(), form.get("value", "")
        if not field_name:
            return _text(400, "field: required for a correction")
        entry["corrections"] = {field_name: value}
    decisions = _read_decisions(root)
    decisions[form["card"]] = entry  # every other key is left exactly as it was
    atomic_write(root / "decisions.json", (json.dumps(decisions, indent=2) + "\n").encode())
    return _redirect(token)


def _serve_file(root: Path, rel: str) -> Response:
    base = (root / "site").resolve()  # only the rebuilt site, not review.json or decisions.json
    target = (base / rel).resolve()
    if target.is_dir():
        target = target / "index.html"
    if base not in target.parents or not target.is_file():
        return _text(404, "not found")
    ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    if ctype.startswith("text/") or ctype.endswith(("javascript", "json")):
        ctype += "; charset=utf-8"
    return 200, {"Content-Type": ctype}, target.read_bytes()


def handle(
    method: str,
    target: str,
    headers: Mapping[str, str],
    body: bytes,
    *,
    root: str | Path,
    token: str,
    port: int,
    now: datetime | None = None,
) -> Response:
    """Answer one request. ``target`` is the raw request path with its query string."""
    folder = Path(root)
    host = headers.get("host", headers.get("Host", ""))
    if host not in (f"127.0.0.1:{port}", f"localhost:{port}"):
        return _text(400, f"Host: expected 127.0.0.1:{port} or localhost:{port}")
    url = urlsplit(target)
    given = parse_qs(url.query).get("t", [""])[0]
    if not hmac.compare_digest(given.encode(), token.encode()):
        return _text(403, "forbidden: a valid token (?t=...) is required")
    if len(body) > MAX_BODY:
        return _text(413, f"body larger than {MAX_BODY} bytes")
    path = url.path
    try:
        if method == "GET":
            if path == "/":
                return _page(folder, token)
            if path == "/style.css":
                css = (STYLE_CSS + REVIEW_CSS).encode()
                return 200, {"Content-Type": "text/css; charset=utf-8"}, css
            if path.startswith("/site/"):
                return _serve_file(folder, path[len("/site/") :])
        elif method == "POST":
            if path == "/decide":
                return _decide(folder, token, body, now or datetime.now(UTC))
            if path == "/apply":
                apply_to_folder(folder)
                return _redirect(token)
    except (ValueError, OSError) as exc:
        return _text(500, f"error: {exc}")
    return _text(404, "not found")


def make_server(root: str | Path, port: int = 0, token: str | None = None) -> tuple[Any, str]:
    """A server bound to 127.0.0.1 (not yet serving) and its token."""
    secret = token or secrets.token_urlsafe(16)
    folder = Path(root)

    class Handler(BaseHTTPRequestHandler):
        def _go(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            body = b"" if length > MAX_BODY else self.rfile.read(length)
            if length > MAX_BODY:
                body = b"x" * (MAX_BODY + 1)  # handle() answers 413 without reading the rest
            status, hdrs, out = handle(
                self.command,
                self.path,
                {k.lower(): v for k, v in self.headers.items()},
                body,
                root=folder,
                token=secret,
                port=self.server.server_address[1],
            )
            self.send_response(status)
            for k, v in hdrs.items():
                self.send_header(k, v)
            if "Content-Length" not in hdrs:
                self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        do_GET = do_POST = _go

        def log_message(self, format: str, *args: Any) -> None:
            return  # the URL carries the token; keep it out of logs

    return ThreadingHTTPServer(("127.0.0.1", port), Handler), secret


def serve(root: str | Path, port: int = 0) -> None:
    server, token = make_server(root, port)
    print(
        f"serving {root} at http://127.0.0.1:{server.server_address[1]}/?t={token}  (Ctrl-C stops)"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("stopped")
    finally:
        server.server_close()
