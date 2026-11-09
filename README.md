# Pineway | Puffin & Pine onboarding POC

An analyst-facing **synthetic training prototype** with two distinct experiences:

1. **KYC case review:** uses the copied lab KYC data layer, screening, deterministic rules, review-case tool and Day 4 Azure AI Search client. It can run a bounded, read-only Gemini tool workflow on the resulting course case.
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

In **KYC case review**, choose or enter a synthetic application ID and select **Run checks**. The included applications.csv contains 200 original application records, numbered SPECIMEN-APP-5001 through SPECIMEN-APP-5200. One additional synthetic application, SPECIMEN-APP-5201, is assembled from the CASE-A document pack without changing the original course CSVs. For example:

- SPECIMEN-APP-5154: no flags in the included fixture.
- SPECIMEN-APP-5155: compliance review with PEP and jurisdiction reasons.
- SPECIMEN-APP-5192: missing proof of address; a pending status.
- SPECIMEN-APP-5201: linked to CASE-A documents; pending because proof-of-address extraction needs review and other required evidence is missing.

The **Application directory** lists these 201 records and lets an analyst search, filter and explicitly run checks on a case. The four dashboard cards filter that same directory. Status counts are based on the most recent checks recorded in this local database, not on the mere existence of a CSV record. Existing checks from versions before the directory was added cannot be reconstructed and appear as **Not checked** until rerun. A change to the local course sources or rules, or a review edit to the linked example, marks affected results **Needs recheck**. Each checked case appears in its highest-priority status. **No rule flags** is not approval and does not establish that policy has been validated. The separate three scenario cards lower down are not included in directory counts.

Choose **Open case** in the directory to see the synthetic company, parties and document metadata. For the 200 original cases, the **Update case fields** section uses the course data layer's four supported overrides: application date, incorporation date, proof-of-address date and first director name. Save an edit, then run checks again to see the lab rules and screening use it. The original CSV remains unchanged; overrides and an audit trail are local to this demo and can be reverted. A missing source document cannot be created through an override. If the underlying source case changes, an override is held until it is reviewed and saved again or reverted. These edits do not verify real evidence. The CSV document references are metadata, not viewable files; the separate linked example SPECIMEN-APP-5201 is the case with a document pack and analyst-review flow.

The server loads the case from the included course files, runs the course's circuit-breaker screening function across the applicant and every director and beneficial owner, evaluates the course rules, and uses the course tool to create idempotent draft review cases for compliance reasons. Each potentially matched party gets a separate review record and candidate evidence. The intended workflow is that an onboarding analyst raises the issue and a compliance reviewer investigates. The demo lets a user record an acknowledgment, escalation or compliance finding; it does not authenticate roles, send assignments or notifications, close the review, clear a match or decide the application.

When configured, the existing Day 4 client performs a read-only query and the UI displays the returned section IDs, versions and titles. Search failure or zero applicable sections holds policy-dependent output. A configured Gemini key enables **Run Gemini tool workflow**: Gemini must request both the course assessment and policy status through two read-only tools before an advisory response is shown. The server bounds calls and validates names and arguments. Gemini cannot approve, reject, change a case, or skip deterministic screening and review routing. Missing required data or unavailable screening holds the AI summary, even when compliance-review status takes precedence. If search is enabled but fails, the AI summary is held. If search is off, a summary can still be requested but must disclose that policy was not checked; the policy-dependent recommendation remains held.

When policy retrieval succeeds, synthetic policy text and limited synthetic case facts are sent to Gemini. Returned sections can be expanded. Policy excerpts and model responses support basic Markdown formatting; raw HTML is escaped and model-generated links are not clickable. Formatting does not change the underlying source text or citation checks. The model output is held if it uses certain decision phrases or cites a policy ID not in the returned sections; these checks are conservative and incomplete. The model tool trace is shown, and no model output determines status. The search client uses the lab's fixed query, synthetic jurisdiction and effective-date filter; the analyst must still check relevance and citations. Recommendations remain held even when retrieval succeeds.

## Ask about evidence

In the KYC case review, use **Ask about retrieved policy** to ask a question about the returned policy text. **Document evidence assistant** uses the synthetic practice pack: choose CASE-A, CASE-B or CASE-C and load the fields extracted by the Day 12 offline extractor. PDF fields come from the text layer; scanned documents use provided simulated OCR sidecars. CASE-A is explicitly linked to the new example SPECIMEN-APP-5201; CASE-B and CASE-C are not linked to KYC applications. Run 5201 and select **View linked documents**, or choose CASE-A in the document assistant. Click a field's source link to inspect the synthetic PDF or image. Then ask a question about the extracted fields.

For 5201, the application date is a stated synthetic assumption. The original ownership declaration names two owners, but the pack contains only one identity document and does not establish the director list or PEP declarations. Low-confidence address fields are not accepted as verified KYC data. Select **View linked documents**, inspect the source and record reviewed values for the three flagged fields. To exercise missing evidence, inspect and attach the invented A5 supplemental record, then explicitly record its review. The record is a synthetic teaching aid, not a real passport or official registry record. Each action is recorded locally; KYC checks rerun using reviewed values without changing the original documents or CSVs. A source change invalidates a prior correction. Until all required evidence is reviewed the case remains pending; even with no flags the recommendation is held for an analyst. The demo has no role authentication and does not decide an application.

Both question features send the question and selected synthetic evidence to Gemini. The service checks that each returned source ID exists and its quoted text occurs in that source; this does not verify the answer's reasoning, relevance or truth. Low-confidence fields are flagged for human review. Answers are held if the model cannot provide valid citations or returns certain decision language. Never submit real documents, secrets or customer information.

## Provenance and limitations

lab/starter-code/kyc and lab/starter-code/config are copied from concept-week-2/live-prototype; lab/fixtures/data contains the required synthetic KYC CSVs. lab_bridge.py adapts the original data layer, routing.screen_every_party, rules, tools.open_review_case, and policy_search.search_policy. The review tool's idempotency key was extended to include party ID. gemini_agent.py adds the bounded Gemini function-calling loop. document_lab includes the Day 12 offline extraction components, schema, and synthetic documents, but does not run the full Day 12 case-management pipeline. The full original routing.run_case replay/Claude workflow and all original gates and evals are **not** invoked by this adapter; this is not a claim that the original course floor is fully satisfied.

The prior version's Azure Search and Gemini tool workflow were observed working for one synthetic case in Skillable. The new Q&A, reviewer actions and safety checks have only been tested locally with mocked Gemini; verify them in Skillable. Real watchlists, live OCR, customer messaging, core banking, and actual onboarding decisions are not implemented.

The application directory and separate sample scenarios retain local SQLite state. Activity includes sample-case actions and course review actions; Reports shows local directory and separate sample counts, not bank performance. To reset the demonstration, stop the server and delete demo.sqlite3 and the state folder; this removes local demo history, check results and review cases.

## Tests

After installing requirements, run `python -m unittest -v` and `python evals/run_course_evals.py`. If Node.js is available, `node tests/frontend-smoke.cjs` checks the async document-loading and form controls. The evaluation adapts applicable Day 7 reference cases to the deterministic KYC adapter and explicitly skips replay-specific checks; it does not evaluate Gemini or live search. Tests cover case routing, multiple matches, review actions, pending states, citation validation, policy failure and the simplified dashboard. Neither tests nor the heuristic output filter prove that model text is safe or supported. The course code is a teaching implementation, not production-ready security or compliance controls.

See [LAB-ALIGNMENT.md](LAB-ALIGNMENT.md) for the day-by-day mapping and remaining gaps, and [the internal brand guide](branding/BRAND-GUIDE.md) for the fictional identity and logo assets.
