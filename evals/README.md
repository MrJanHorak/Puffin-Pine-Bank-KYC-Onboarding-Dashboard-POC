# Evaluation scope

Run `python evals/run_course_evals.py` after installing requirements. The runner adapts the copied Day 7 `reference_cases.yaml` to Pineway's deterministic KYC adapter. It checks expected status and reasons, selected tool calls, party-screening coverage, tool-call limits, and expected review cases where specified. It isolates the synthetic review-case store for every case.

The original replay-summary trajectory, original full `routing.run_case` flow, live policy search and Gemini responses are **not** run by this adapter. Cases requiring those paths are marked `SKIPPED`, not passed. The runner is not a full validation of the course hard-rule suite or the end-to-end system.

The current local run produced 10 passes, zero failures and one skipped case (`EV-0212`, original summary ordering). These results apply to the included synthetic dataset and code, not to real bank data. The independently executed `python -m unittest -v` suite checks the Gemini protocol with mocked responses, policy failure, two simultaneous screening matches, reviewer actions, offline extraction and citation rejection. A human must still test actual Gemini behavior, policy relevance and live failures in Skillable.
