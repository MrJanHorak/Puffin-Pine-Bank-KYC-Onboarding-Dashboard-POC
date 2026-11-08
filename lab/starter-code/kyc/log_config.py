"""Logging for every script: console text plus JSON lines in logs/run.jsonl.

Every message reads `event=<name> key=value ...`. The console shows
`<time> <LEVEL> <logger> <message>`; the JSON file holds one object per line
with ts, level, logger and event first. Only IDs, codes, counts and times
are logged, never names, dates of birth, document numbers or model text
(hard rule H5).
"""
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

CONSOLE_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"

_correlation_id = None
_handlers: list[logging.Handler] = []


def set_correlation_id(value: str | None) -> None:
    """Name the run every following line belongs to (None outside a run)."""
    global _correlation_id
    _correlation_id = value


def format_value(value) -> str:
    """How a value prints in a key=value message."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(str(item) for item in value) + "]"
    if isinstance(value, float):
        # Two places where that is exact (0.40); more only when needed (0.225).
        text = f"{value:.2f}"
        return text if float(text) == value else repr(round(value, 6))
    return str(value)


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO,
              **fields) -> None:
    """Log one `event=<event> key=value ...` line, fields in given order."""
    parts = [f"event={event}"]
    parts += [f"{key}={format_value(value)}" for key, value in fields.items()]
    logger.log(level, " ".join(parts))


def parse_value(key: str, text: str):
    """Turn one logged value back into a JSON value; IDs always stay text."""
    if key.endswith("_id") or key.endswith("_ids"):
        if text.startswith("[") and text.endswith("]"):
            return [item for item in text[1:-1].split(",") if item]
        return text
    if text in ("true", "false"):
        return text == "true"
    if text == "None":
        return None
    if text.startswith("[") and text.endswith("]"):
        return [item for item in text[1:-1].split(",") if item]
    for kind in (int, float):
        try:
            return kind(text)
        except ValueError:
            pass
    return text


def parse_message(message: str) -> dict:
    """Read the key=value pairs of one message back into a dict."""
    fields = {}
    for token in message.split():
        key, sep, value = token.partition("=")
        if sep:
            fields[key] = parse_value(key, value)
    return fields


class JsonLinesHandler(logging.FileHandler):
    """Appends one JSON object per `event=` line to run.jsonl."""

    def emit(self, record: logging.LogRecord) -> None:
        fields = parse_message(record.getMessage())
        if "event" not in fields:
            return
        stamp = datetime.fromtimestamp(record.created, tz=timezone.utc)
        line = {
            "ts": stamp.strftime("%Y-%m-%dT%H:%M:%S.%f")[:23] + "Z",
            "level": record.levelname,
            "logger": record.name,
            "event": fields.pop("event"),
            "correlation_id": fields.pop("correlation_id", _correlation_id),
        }
        if "application_id" in fields:  # the subject comes next
            line["application_id"] = fields.pop("application_id")
        line.update(fields)
        self.stream.write(json.dumps(line) + "\n")
        self.flush()


def setup_logging(log_dir: str = "logs") -> Path:
    """Send INFO and above to the console (stderr) and <log_dir>/run.jsonl."""
    root = logging.getLogger()
    for handler in _handlers:
        root.removeHandler(handler)
        handler.close()
    _handlers.clear()
    folder = Path(log_dir)
    folder.mkdir(parents=True, exist_ok=True)
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(logging.Formatter(CONSOLE_FORMAT))
    json_file = JsonLinesHandler(folder / "run.jsonl", encoding="utf-8")
    for handler in (console, json_file):
        root.addHandler(handler)
        _handlers.append(handler)
    root.setLevel(logging.INFO)
    return folder / "run.jsonl"
