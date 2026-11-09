# Card dispute triage assistant (SPECIMEN)

A small build you extend across the programme, one task per course topic. It triages a Puffin & Pine Bank card dispute: it proposes a **queue** (fraud or general), a **reviewer** (senior or standard) and a **readiness** (ready, needs info, lookup unavailable), keeps every reason, and drafts a case summary. It never grants, denies or files anything. An analyst decides.

Puffin & Pine is a made-up bank. Every name, ID, rule and number here is invented for training.

The requirements are in the sample PRD your instructors shared. The ten tasks are in [docs/tasks.md](docs/tasks.md).

## Setup

From the repository root, after the POC's own setup (`.venv`, `pip install -r requirements.txt`):

    cd disputes
    python -m unittest discover -s tests -v

Nothing here needs an API key. Model answers replay from `recordings/`. To call Gemini instead, set `DISPUTES_MODEL_MODE=live` and `GEMINI_API_KEY` in `.env`; only synthetic, masked data is sent.

## Commands (run from `disputes/`)

| What | Command |
| --- | --- |
| Triage one dispute | `python -m triage.run DSP-31` |
| Triage with a search outage | `python -m triage.run DSP-34 --fault search_policy:unavailable` |
| Run all 40 eval cases | `python -m evals.run` |
| Run some cases | `python -m evals.run DSP-21 DSP-34` |
| Scan the log for personal data | `python scripts/scan_log.py logs/run.jsonl` |
| Cost per dispute from the log | `python scripts/cost_report.py logs/run.jsonl` |
| The page | from the repo root: `python app.py`, then open http://127.0.0.1:8080/disputes |

## What's where

| Path | What it is |
| --- | --- |
| `triage/data_layer.py` | Reads the data files; masks card numbers on load (H8) |
| `triage/rules.py` | Rules R1 to R6, in code |
| `triage/tools.py` | The five tools |
| `triage/model.py` | Replay or live Gemini for R7 and R9; logs tokens and cost |
| `triage/pipeline.py` | Runs one dispute end to end and sets the three outputs (R10, R11) |
| `evals/cases.jsonl`, `evals/run.py` | The 40 labelled cases and the runner |
| `data/`, `config/`, `policy_manual/` | SPECIMEN data, rules config, six policy sections |
| `docs/` | Task list, templates and paper materials |

Some cases fail on purpose until you complete the tasks. `evals/run.py` tells you which, and why.
