"""Model access: replay (the default) or live.

Replay reads the model's answers from a recording, so every run repeats
exactly and needs no key. A recording is one JSON line per model call, in
recordings/current/<application_id>__<faults or none>[__<fields hash>].jsonl;
KYC_RECORDINGS in .env names another folder. Each recorded call keeps a hash
of what the build sent; when today's build sends something else (a changed
prompt, a changed tool result) replay logs WARNING replay_divergence.

Live mode sends the same request to the Claude API with MODEL_API_KEY and
MODEL_NAME_LARGE. Live runs cost money
and stay within the course's live-run cap.

Every call writes one `model_call` line with token counts, never model text.
"""
import hashlib
import json
import logging
import time
import urllib.request
import uuid
from pathlib import Path

from kyc import STARTER_ROOT
from kyc.log_config import log_event
from kyc.settings import setting

logger = logging.getLogger("kyc.model_client")

PROMPT_FILE = STARTER_ROOT / "prompts" / "agent_instructions.md"
API_URL = "https://api.anthropic.com/v1/messages"


class ReplayMissing(Exception):
    """No recording exists for this application, faults and fields."""

    def __init__(self, recording_key: str):
        super().__init__(recording_key)
        self.recording_key = recording_key


class ModelUnavailable(Exception):
    """A live model request could not complete; no response details are exposed."""


def sha8(value) -> str:
    """The first 8 hex characters of the sha256 of a JSON value."""
    text = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


def recording_key(application_id: str, faults=(), fields=None) -> str:
    """The recording file name, without .jsonl ('-' stands for ':')."""
    key = f"{application_id}__{'+'.join(faults).replace(':', '-') or 'none'}"
    return key + (f"__{sha8(fields)}" if fields else "")


def prompt_version(text: str) -> str:
    """The value of the prompt file's `Version:` line."""
    for line in text.splitlines():
        if line.startswith("Version:"):
            return line.split(":", 1)[1].strip()
    return "unversioned"


class ModelClient:
    """One run's model calls, replayed or live."""

    def __init__(self, application_id: str, mode: str = "replay", faults=(),
                 fields=None, recordings: str | None = None):
        self.application_id = application_id
        self.mode = mode
        self.instructions = PROMPT_FILE.read_text(encoding="utf-8")
        self.prompt_version = prompt_version(self.instructions)
        self.key = recording_key(application_id, faults, fields)
        self.recorded = []
        if mode == "replay":
            folder = Path(recordings or setting("KYC_RECORDINGS"))
            if not folder.is_absolute():
                folder = STARTER_ROOT / folder
            path = folder / f"{self.key}.jsonl"
            if path.exists():
                self.recorded = [json.loads(line) for line in
                                 path.read_text(encoding="utf-8").splitlines()]
        self.step = 0
        # The recorded run's ID in replay, so a replay logs the same ID.
        self.correlation_id = (self.recorded[0]["correlation_id"]
                               if self.recorded else uuid.uuid4().hex[:12])

    def next(self, call_name: str, task: dict) -> dict:
        """The model's answer to one call: a tool request or a final answer."""
        self.step += 1
        request = {"instructions": self.instructions, "call_name": call_name,
                   "task": task}
        started = time.perf_counter()
        if self.mode == "live":
            answer, tokens_in, tokens_out = self.live(request)
            model = setting("MODEL_NAME_LARGE")
            latency = int((time.perf_counter() - started) * 1000)
        else:
            if self.step > len(self.recorded):
                log_event(logger, "replay_missing", level=logging.WARNING,
                          recording_key=self.key,
                          application_id=self.application_id)
                raise ReplayMissing(self.key)
            line = self.recorded[self.step - 1]
            if line["request_sha"] != sha8(request):
                log_event(logger, "replay_divergence", level=logging.WARNING,
                          step=self.step, application_id=self.application_id)
            answer, model = line["response"], line["model"]
            tokens_in, tokens_out = line["tokens_in"], line["tokens_out"]
            latency = line["latency_ms"]
        log_event(logger, "model_call", step=self.step, call_name=call_name,
                  application_id=self.application_id, model=model,
                  mode=self.mode, tokens_in=tokens_in, tokens_out=tokens_out,
                  latency_ms=latency, prompt_version=self.prompt_version)
        return answer

    def live(self, request: dict) -> tuple[dict, int, int]:
        """One Claude API call; the reply must be one JSON object."""
        if not setting("MODEL_API_KEY") or not setting("MODEL_NAME_LARGE"):
            raise ModelUnavailable("Live model credentials or model name are missing.")
        body = {
            "model": setting("MODEL_NAME_LARGE"),
            "max_tokens": 2000,
            "system": request["instructions"],
            "messages": [{"role": "user", "content": json.dumps(
                {"call_name": request["call_name"],
                 "task": request["task"]})}],
        }
        http = urllib.request.Request(
            API_URL, data=json.dumps(body).encode("utf-8"), method="POST",
            headers={"content-type": "application/json",
                     "x-api-key": setting("MODEL_API_KEY"),
                     "anthropic-version": "2023-06-01"})
        try:
            with urllib.request.urlopen(http, timeout=120) as response:
                reply = json.loads(response.read())
            text = "".join(block.get("text", "") for block in reply["content"]
                           if block.get("type") == "text")
            usage = reply["usage"]
            tokens_in = (usage.get("input_tokens", 0)
                         + usage.get("cache_read_input_tokens", 0)
                         + usage.get("cache_creation_input_tokens", 0))
            start, end = text.find("{"), text.rfind("}")
            answer = json.loads(text[start:end + 1])
            if not isinstance(answer, dict):
                raise ValueError("Expected a JSON object")
            return answer, tokens_in, usage["output_tokens"]
        except (OSError, ValueError, KeyError, TypeError):
            raise ModelUnavailable("Live model request failed or returned an invalid response.") from None
