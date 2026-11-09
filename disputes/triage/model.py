"""Model access for R7 and R9: replay (the default) or live Gemini.

Replay reads the answer from recordings/<dispute_id>.json, so every run
repeats exactly and needs no key. The recordings are authored SPECIMEN
fixtures in the shape a model returns; they are not captured live output.

Live mode (DISPUTES_MODEL_MODE=live) sends the same prompt to Gemini with
GEMINI_API_KEY and GEMINI_MODEL, as the rest of this POC does. Only synthetic,
already-masked data is sent.

Every call logs one `model_call` line with token counts, never model text.
"""
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from triage import RECORDINGS_DIR, load_yaml
from triage.log import log_event


class ModelUnavailable(Exception):
    """No recording in replay mode, or the live call failed."""


def estimate_tokens(text: str) -> int:
    """About four characters per token: good enough to compare two prompts."""
    return max(1, round(len(text) / 4))


def call_cost(tokens_in: int, tokens_out: int) -> float:
    card = load_yaml("price_card.yaml")
    return round(tokens_in / 1e6 * card["input_usd_per_million"]
                 + tokens_out / 1e6 * card["output_usd_per_million"], 6)


def _replay(dispute_id: str, call: str) -> dict:
    path = RECORDINGS_DIR / f"{dispute_id}.json"
    if not path.exists():
        raise ModelUnavailable(f"no recording for {dispute_id}")
    recording = json.loads(path.read_text(encoding="utf-8")).get(call)
    if recording is None:
        raise ModelUnavailable(f"no {call} recording for {dispute_id}")
    return recording


def _live(prompt: str) -> dict:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    model = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
    if not key or not re.fullmatch(r"[a-zA-Z0-9._-]{1,80}", model):
        raise ModelUnavailable("Gemini is not configured")
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                       "generationConfig": {"temperature": 0.2,
                                            "maxOutputTokens": 400}}).encode("utf-8")
    request = Request("https://generativelanguage.googleapis.com/v1beta/models/"
                      + model + ":generateContent", data=body, method="POST",
                      headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with urlopen(request, timeout=25) as response:
            result = json.loads(response.read(200000).decode("utf-8"))
        text = "\n".join(p.get("text", "") for p in
                         result["candidates"][0]["content"]["parts"]).strip()
        usage = result.get("usageMetadata", {})
        return {"text": text, "tokens_in": usage.get("promptTokenCount", 0),
                "tokens_out": usage.get("candidatesTokenCount", 0)}
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError, IndexError) as exc:
        raise ModelUnavailable("Gemini call failed") from exc


def complete(dispute_id: str, call: str, prompt: str) -> dict:
    """Run one model call ("summary" or "category") and log its cost."""
    mode = os.environ.get("DISPUTES_MODEL_MODE", "replay").lower()
    answer = _live(prompt) if mode == "live" else _replay(dispute_id, call)
    cost = call_cost(answer["tokens_in"], answer["tokens_out"])
    log_event("model_call", dispute_id=dispute_id, call=call, mode=mode,
              tokens_in=answer["tokens_in"], tokens_out=answer["tokens_out"],
              prompt_tokens_est=estimate_tokens(prompt), cost_usd=cost)
    return {**answer, "cost_usd": cost, "prompt_tokens_est": estimate_tokens(prompt)}
