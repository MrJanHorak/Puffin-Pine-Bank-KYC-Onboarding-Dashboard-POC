# Pineway | Puffin & Pine onboarding POC

An analyst-facing **synthetic training prototype** with two distinct experiences:

1. **Course KYC workbench:** uses the copied lab KYC data layer, screening, deterministic rules, review-case tool and Day 4 Azure AI Search client. It can run a bounded, read-only Gemini tool workflow on the resulting course case.
2. **Application queue:** the original three simplified dashboard cases with predetermined outcomes. Their Gemini button is a simple summary, not the course agent. These PP cases are not mapped to the lab fixtures.

The bank and all fixtures are fictional. Never use real customer data. This is a local teaching POC, without production authentication or bank integrations.

## Setup in Skillable

Python 3.10 or later and package installation access are required. In PowerShell, from the repository folder:

    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    Copy-Item .env.example .env

Edit .env locally, without pasting keys into chat or committing the file. The app loads it at startup; environment variables already set in the shell take precedence. Set GEMINI_API_KEY for Gemini. The default GEMINI_MODEL is gemini-3.1-flash-lite; select a model available to your project and review [Google pricing and quota](https://ai.google.dev/gemini-api/docs/pricing). Google says free-tier content may be used to improve products. Only synthetic data should be sent.

For the Day 4 index set KYC_POLICY_SEARCH=azure, AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_INDEX, and AZURE_SEARCH_QUERY_KEY to authorized **query** settings. KYC_POLICY_AS_OF_DATE defaults to the course's fixed synthetic review date. With KYC_POLICY_SEARCH=off, the deterministic lab checks still run, but policy is not checked and the policy-dependent recommendation is held. .env.example shows all settings. Never use an admin key.

Start with `python app.py` and open http://127.0.0.1:8080. If the port is busy, set `$env:PORT = '8081'` before starting. Stop the server with Ctrl+C. Restart after editing .env. The browser never receives the keys. .env, the local case database and review-case state are ignored by Git; if you choose a custom ONBOARDING_DB path inside the repo, ignore that file as well.

## Course walkthrough

In **Course KYC workbench**, enter a synthetic course application ID and run course checks:

- SPECIMEN-APP-5154: no flags in the included fixture.
- SPECIMEN-APP-5155: compliance review with PEP and jurisdiction reasons.
- SPECIMEN-APP-5192: missing proof of address; a pending status.

The server loads the case from the included course files, runs the course's circuit-breaker screening function across the applicant and every director and beneficial owner, evaluates the course rules, and uses the course tool to create idempotent draft review cases for compliance reasons. The interface shows statuses, reason codes, screened party IDs and review-case IDs. It never approves or rejects an application.

When configured, the existing Day 4 client performs a read-only query and the UI displays the returned section IDs, versions and titles. Search failure or zero applicable sections holds policy-dependent output. A configured Gemini key enables **Run Gemini tool workflow**: Gemini must request both the course assessment and policy status through two read-only tools before an advisory response is shown. The server bounds calls and validates names and arguments. Gemini cannot approve, reject, change a case, or skip deterministic screening and review routing. Missing required data or unavailable screening holds the AI summary, even when compliance-review status takes precedence. If search is enabled but fails, the AI summary is held. If search is off, a summary can still be requested but must disclose that policy was not checked; the policy-dependent recommendation remains held.

When policy retrieval succeeds, synthetic policy text and limited synthetic case facts are sent to Gemini. Returned text and citations are unverified: an analyst must inspect them. The model tool trace is shown, and no model output is used to determine status. The search client uses the lab's fixed query, synthetic jurisdiction and effective-date filter; results still need a relevance check.

## Provenance and limitations

lab/starter-code/kyc and lab/starter-code/config are copied from concept-week-2/live-prototype; lab/fixtures/data contains the required synthetic KYC CSVs. lab_bridge.py adapts the original data layer, routing.screen_every_party, rules, tools.open_review_case, and policy_search.search_policy. gemini_agent.py adds the bounded Gemini function-calling loop. The full original routing.run_case replay/Claude workflow and all original gates and evals are **not** invoked by this adapter; this is not a claim that the original course floor is fully satisfied. The document extraction pipeline remains separate.

The course Azure Search integration and Gemini workflow have not been verified live in Skillable. A previous local search attempt in the separate prototype returned HTTP 403. Current tests mock Gemini and search; verify connectivity, policy relevance, generated citations, and failure scenarios in the lab before demonstrating live use. Real watchlists, OCR, customer messaging, core banking, and actual onboarding decisions are not implemented.

The application queue retains its own local SQLite state. Its activity entries are per case; the sidebar Activity and Reports entries and the filter are placeholders. To reset the demonstration, stop the server and delete demo.sqlite3 and the state folder; this removes local demo history and review cases.

## Tests

After installing requirements, run `python -m unittest -v`. Tests cover case routing, pending states, policy failure, Gemini tool-loop boundaries and the simplified dashboard. The course code is a teaching implementation, not production-ready security or compliance controls.

See [the internal brand guide](branding/BRAND-GUIDE.md) for the fictional identity and logo assets.
