"""The local web page an analyst uses (FLOOR-3), on Python's standard library.

    python -m kyc.interface              (replay, the default)
    python -m kyc.interface --mode live  (within the live-run cap only)

Open http://localhost:8000, type an application ID and click Run. The page
shows the status, reasons, recommendation, sources and "Pending analyst
review". It has no approve or reject control (hard rule H1).
"""
import argparse
import html
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from kyc.log_config import log_event, setup_logging
from kyc.model_client import ModelUnavailable, ReplayMissing
from kyc.routing import run_case
from kyc.rules import display_text
from kyc.settings import setting

logger = logging.getLogger("kyc.interface")

HOST = "127.0.0.1"
PORT = 8000
PENDING_BANNER = "Pending analyst review"
NOT_FOUND_TEXT = "No application with this ID. Nothing was checked."
REPLAY_MISSING_TEXT = "No recording for this ID in replay mode."


def render_result(result: dict) -> str:
    """The result block; every value is escaped with html.escape."""
    lines = [
        "Status: " + display_text(result["status"]),
        "Reasons: " + (", ".join(result["reasons"]) or "none"),
        "Recommendation: " + result["summary"],
        "Sources: " + (", ".join(result["sources"]) or "none"),
    ]
    paragraphs = [f"<p>{html.escape(line)}</p>" for line in lines]
    paragraphs.insert(0, f"<p>Model mode: {html.escape(result.get('model_mode', 'unknown'))}</p>")
    policy = result.get("policy_search", {})
    if policy.get("mode") == "azure":
        if policy.get("outcome") == "ok":
            label = ("Live model received these policy sections" if policy.get("model_received_policy")
                     else "Live policy search; model summary is replayed and was not grounded in these results")
            paragraphs.append(f"<p>{html.escape(label)}:</p><ul>" + "".join(
                f"<li>{html.escape(s['section_id'])} v{html.escape(s['version'])}: "
                f"{html.escape(s['title'])}</li>" for s in policy.get("sections", [])) + "</ul>")
        else:
            paragraphs.append("<p><strong>Policy search unavailable or no sections matched; "
                              "recommendation held for analyst review.</strong></p>")
    paragraphs.append(f"<p><strong>{PENDING_BANNER}</strong></p>")
    return "\n".join(paragraphs)


def render_page(application_id: str = "", result: dict | None = None,
                message: str = "") -> str:
    """The whole page: the Application ID box, the Run button, the result."""
    body = render_result(result) if result else \
        (f"<p>{html.escape(message)}</p>" if message else "")
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Puffin &amp; Pine Bank KYC</title></head>
<body>
<h1>Business onboarding check (SPECIMEN data)</h1>
<form action="/run" method="get">
<label for="application_id">Application ID</label>
<input id="application_id" name="application_id"
 value="{html.escape(application_id)}">
<button type="submit">Run</button>
</form>
{body}
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    mode = "replay"

    def do_GET(self) -> None:
        url = urlparse(self.path)
        application_id = parse_qs(url.query).get("application_id", [""])[0]
        result, message = None, ""
        if url.path == "/run" and application_id:
            try:
                result = run_case(application_id, self.mode)
            except ReplayMissing:
                message = REPLAY_MISSING_TEXT
            except ModelUnavailable:
                message = "Live model unavailable. No result was generated; check instructor configuration."
            if result is None and not message:
                message = NOT_FOUND_TEXT
        page = render_page(application_id, result, message).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(page)

    def log_message(self, format, *args) -> None:
        """One http_request line per request, the path without its query."""
        log_event(logger, "http_request", path=urlparse(self.path).path,
                  status_code=args[1] if len(args) > 1 else "")


class Server(HTTPServer):
    # On Windows, address reuse would let a second server share the port
    # silently; without it a busy port fails with WinError 10048.
    allow_reuse_address = os.name != "nt"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Start the analyst page.")
    parser.add_argument("--mode", choices=["replay", "live"])
    args = parser.parse_args(argv)
    setup_logging()
    Handler.mode = setting("KYC_MODE", args.mode)
    server = Server((HOST, PORT), Handler)
    log_event(logger, "interface_start", mode=Handler.mode, host=HOST,
              port=PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
