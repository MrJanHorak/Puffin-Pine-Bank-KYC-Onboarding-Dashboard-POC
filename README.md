# Pineway | Business onboarding workspace

Pineway is a proof of concept for helping Puffin & Pine Bank's onboarding analysts review business applications. It brings case records, synthetic screening, rule results, policy evidence and optional Gemini assistance into one workspace so an analyst can investigate a case and document their review.

**Proof of concept:** Puffin & Pine and all included records are fictional. Do not use real customer data. Screening uses a synthetic watchlist; the application does not authenticate users, connect to bank systems, or approve or reject applications. A person remains responsible for the decision.

## What it does

- Browse, search and filter 201 synthetic applications; dashboard and report counts open the corresponding queue.
- Run deterministic KYC checks, inspect the results and recorded tool steps, and review screening and policy sources before requesting an AI summary.
- Record analyst review notes for a current no-flags check, or record actions on compliance review cases. Reviews are local and do not constitute an onboarding decision.
- Ask Gemini questions about retrieved policy, or review and ask about the supporting documents linked to application `SPECIMEN-APP-5201`. AI answers are advisory and source citations are checked against the supplied text.
- Edit selected application fields locally and rerun checks. The original records remain unchanged.

The app runs locally with Python and SQLite. Gemini and Azure AI Search are optional external services. Without their configuration, the local checks still work; policy answers require both services. See [Provenance and limitations](#provenance-and-limitations) for course integration and implementation boundaries.

## Setup in Skillable

Python 3.10 or later and package installation access are required. In PowerShell, from the repository folder:

    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    Copy-Item .env.example .env

Edit .env locally, without pasting keys into chat or committing the file. The app loads it at startup; environment variables already set in the shell take precedence. Set GEMINI_API_KEY for Gemini. The default GEMINI_MODEL is gemini-3.1-flash-lite; select a model available to your project and review [Google pricing and quota](https://ai.google.dev/gemini-api/docs/pricing). Google says free-tier content may be used to improve products. Only synthetic data should be sent.

For policy search set KYC_POLICY_SEARCH=azure, AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_INDEX, and AZURE_SEARCH_QUERY_KEY to authorized **query** settings. KYC_POLICY_AS_OF_DATE defaults to the fixed synthetic review date. With KYC_POLICY_SEARCH=off, the deterministic checks still run, but policy is not checked and the policy-dependent recommendation is held. .env.example shows all settings. Never use an admin key.

Start with `python app.py` and open http://127.0.0.1:8080. If the port is busy, set `$env:PORT = '8081'` before starting. Stop the server with Ctrl+C. Restart after editing .env. The browser never receives the keys. .env, the local case database and review-case state are ignored by Git; if you choose a custom ONBOARDING_DB path inside the repo, ignore that file as well.

## Using the workspace

Choose an application in the queue and select **Run checks** in the case view. The included applications.csv contains 200 original application records, numbered SPECIMEN-APP-5001 through SPECIMEN-APP-5200. One additional synthetic application, SPECIMEN-APP-5201, is assembled from the CASE-A document pack without changing the original course CSVs. For example:

- SPECIMEN-APP-5154: no flags in the included fixture.
- SPECIMEN-APP-5155: compliance review with PEP and jurisdiction reasons.
- SPECIMEN-APP-5192: missing proof of address; a pending status.
- SPECIMEN-APP-5201: linked to CASE-A documents; pending because proof-of-address extraction needs review and other required evidence is missing.

The **application queue** lists these 201 records and lets an analyst search, filter and explicitly run checks on a case. The dashboard cards and report counts filter that queue. Status counts reflect the most recent checks recorded locally, not all records that could be checked. A change to source files or rules, or a review edit to the linked example, marks affected results **Needs recheck**. Each checked case appears in its highest-priority status. **No rule flags** is not approval and does not establish that policy has been validated.

After **Run checks**, expand **Check results** to inspect the outcome, reasons, returned screening outcomes, policy availability and recorded tool steps. Detailed policy and compliance review records appear farther down the case. A no-flags run can be marked reviewed with notes; the review remains in history but is no longer current after another run or a case change. **Generate case summary** runs fresh checks before calling Gemini, so a prior review will no longer be current. The latest status persists across refreshes; rerun checks to see the detailed results again.

Choose a case in the queue to see the synthetic company, parties and document metadata. For the 200 original cases, **Edit application details** uses the course data layer's four supported overrides: application date, incorporation date, proof-of-address date and first director name. Save an edit, then run checks again to see the lab rules and screening use it. The original CSV remains unchanged; overrides and an audit trail are local to this demo and can be reverted. A missing source document cannot be created through an override. If the underlying source case changes, an override is held until it is reviewed and saved again or reverted. These edits do not verify real evidence. The CSV document references are metadata, not viewable files; the linked example SPECIMEN-APP-5201 is the case with a document pack and analyst-review flow.

The server loads the case from the included course files, runs the course's circuit-breaker screening function across the applicant and every director and beneficial owner, evaluates the course rules, and uses the course tool to create idempotent draft review cases for compliance reasons. Each potentially matched party gets a separate review record and candidate evidence. The intended workflow is that an onboarding analyst raises the issue and a compliance reviewer investigates. The demo lets a user record an acknowledgment, escalation or compliance finding; it does not authenticate roles, send assignments or notifications, close the review, clear a match or decide the application.

When configured, the search client performs a read-only query and the UI displays the returned section IDs, versions and titles. Search failure or zero applicable sections holds policy-dependent output. A configured Gemini key enables **Generate case summary**: Gemini must request both the assessment and policy status through two read-only tools before an advisory response is shown. The server bounds calls and validates names and arguments. Gemini cannot approve, reject, change a case, or skip deterministic screening and review routing. Missing required data or unavailable screening holds the AI summary, even when compliance-review status takes precedence. If search is enabled but fails, the AI summary is held. If search is off, a summary can still be requested but must disclose that policy was not checked; the policy-dependent recommendation remains held.

When policy retrieval succeeds, synthetic policy text and limited synthetic case facts are sent to Gemini. Returned sections can be expanded. Policy excerpts and model responses support basic Markdown formatting; raw HTML is escaped and model-generated links are not clickable. Formatting does not change the underlying source text or citation checks. The model output is held if it uses certain decision phrases or cites a policy ID not in the returned sections; these checks are conservative and incomplete. No model output determines status. Case checks use the lab's fixed search query. Policy questions use the question's search terms with the same synthetic jurisdiction and effective-date filters. Search results may be irrelevant or incomplete; the analyst must check the citations. Recommendations remain held even when retrieval succeeds.

## Ask about evidence

After running a case, use **Ask about policy** to search the index for the question and ask about the returned policy text. The retrieved section IDs are visible even when an answer is held. An answer may be unavailable if search is off, the index lacks relevant text, or Gemini cannot support a citation. Document age at onboarding is not necessarily the same as the frequency of later customer reviews. For SPECIMEN-APP-5201, choose **Review supporting documents** to inspect the CASE-A pack and ask about its extracted fields. PDF fields come from the text layer; scanned documents use provided simulated OCR sidecars. CASE-B and CASE-C remain available in the document fixtures but are not linked to applications or shown as separate cases. Select a source link to inspect the synthetic PDF or image.

For 5201, the application date is a stated synthetic assumption. The original ownership declaration names two owners, but the pack contains only one identity document and does not establish the director list or PEP declarations. Low-confidence address fields are not accepted as verified KYC data. Select **Review supporting documents**, inspect the source and record reviewed values for the three flagged fields. To exercise missing evidence, inspect and attach the invented A5 supplemental record, then explicitly record its review. The record is a synthetic teaching aid, not a real passport or official registry record. Each action is recorded locally and marks existing checks stale; select **Run checks** to recompute using reviewed values without changing the original documents or CSVs. A source change invalidates a prior correction. Until all required evidence is reviewed the case remains pending; even with no flags the recommendation is held for an analyst. The demo has no role authentication and does not decide an application.

Both question features send the question and selected synthetic evidence to Gemini. The service checks that each returned source ID exists and its quoted text occurs in that source; this does not verify the answer's reasoning, relevance or truth. Low-confidence fields are flagged for human review. Answers are held if the model cannot provide valid citations or returns certain decision language. Never submit real documents, secrets or customer information.

## Prompts, tools and retrieval

The prompts used by the current onboarding workspace are Python strings in the application code; they are not separate prompt files or editable in the interface. The table below follows the analyst's actions to their implementation.

| Workspace action | Code to inspect | What it does |
| --- | --- | --- |
| **Generate case summary** | [`gemini_agent.py`](gemini_agent.py), `TOOLS` and `run_agent()` | Defines the two read-only Gemini function declarations, constructs the instruction, and runs a bounded tool-calling loop. The instruction asks for case evidence, relevant policy IDs and next human actions. The server requires calls to both `get_kyc_assessment` and `get_policy_evidence` before accepting a summary. This action first runs fresh case checks. |
| **Ask about policy** and **Ask about supporting evidence** | [`evidence_qa.py`](evidence_qa.py), `answer_question()` | Builds a separate Gemini prompt containing the analyst's question and selected evidence. It requests a JSON answer, source IDs and exact quotations, or an insufficient-evidence response. Both question features use this same prompt; they are separate from the summary agent's tool loop. |
| Find policy for checks or a question | [`lab/starter-code/kyc/policy_search.py`](lab/starter-code/kyc/policy_search.py), `search_policy()` | Sends a read-only query to the configured Azure AI Search index. Case checks use the fixed query `high-risk jurisdiction company due diligence` and request up to three results. A policy question supplies plain search terms from the question and requests up to five. Both use the applicant's synthetic jurisdiction, the configured effective date, current status and entity filters. Retrieval is a search request, not a separate Gemini prompt. |
| Select and prepare evidence | [`app.py`](app.py), `/api/questions/policy` and `/api/questions/document`; [`lab_bridge.py`](lab_bridge.py), `retrieve_policy()` and `policy_for_case()` | Routes the question, obtains policy sections or extracted document fields and passes them to the Q&A prompt. Retrieved policy text comes from the configured index, not from a policy manual bundled in this POC. |
| Read document evidence | [`document_bridge.py`](document_bridge.py) and [`document_lab/starter-code/kit/extract.py`](document_lab/starter-code/kit/extract.py) | Uses the offline extractor and the supplied PDF text or simulated OCR sidecars. Human-reviewed values are overlaid for the linked case. This extraction step is not a Gemini retrieval prompt. |
| Check generated output | [`output_checks.py`](output_checks.py) and [`evidence_qa.py`](evidence_qa.py) | Applies limited decision-language and policy-ID checks to summaries; Q&A also validates that a citation ID was supplied and its quotation matches the source text. These checks do not establish that an answer is correct or that a source is applicable. |

The older [`assistant()` in `app.py`](app.py) is retained for the legacy standalone sample-case endpoint; it is not the summary agent used by the current 201-case workspace. Model selection and credentials are configured through [`.env.example`](.env.example). The copied course routing code also contains its own model workflow, but the current workspace uses the Gemini adapter described above rather than invoking that full workflow.

When changing prompts or retrieval, review the corresponding validation and tests as well: [`test_lab_bridge.py`](test_lab_bridge.py), [`test_enhancements.py`](test_enhancements.py) and [`test_http.py`](test_http.py). Prompt wording and quote matching are safeguards with limits, not a substitute for analyst review or live testing against the configured index and model.

### How context is managed

*Context* is the information supplied to the model for a particular request: the instructions, the selected case results or evidence, and, where relevant, the analyst's question. The workspace builds this context on the server for each request; it does not send the entire application queue or maintain a continuing chat history between questions.

**Case summary.** The server reruns the selected application's deterministic checks before contacting Gemini. During the bounded tool loop, `get_kyc_assessment` returns the assessment, including the application ID, status, reason codes, screening outcomes, review-case details and any ownership paths or case notes. It excludes the policy object, recorded tool trace and review-action history from that tool response. `get_policy_evidence` separately returns the policy-search status and the sections retrieved for the case, including their content. Gemini sees both the instructions and the tool responses in the current tool conversation; it does not directly search the index or run screening. The model is instructed to treat tool output as data, and both tool calls are required before a summary is accepted. An unavailable policy search, missing required data or incomplete screening holds the summary; an unconfigured policy search is disclosed in the result.

**Policy questions.** The server takes the selected application's jurisdiction and the analyst's question, then searches the configured index using the applicable filters. It sends the question and returned section IDs, titles, versions and full section text to the Q&A prompt. The search asks for at most five sections; it does not guarantee their relevance or completeness. The model is asked to use only those sources and provide exact quotations. The server checks that quoted text appears in the cited source, then displays the retrieved sources for the analyst to inspect.

**Document questions.** The offline extractor reads the selected synthetic document pack and constructs evidence entries from extracted field values. For the linked case, valid human-reviewed corrections and an attached synthetic supporting record are included when available. The Q&A prompt receives the question and all available extracted field entries, with source descriptions, confidence and review-required indicators. These entries can include synthetic names, dates and other identity fields; the application does not send the original PDF or image bytes to Gemini for this feature. A low-confidence entry can still be supplied as context, so the analyst must inspect its source and review status.

**Boundaries and limitations.** Only synthetic data should be used. Prompts instruct Gemini to treat supplied evidence and questions as data, but instructions alone cannot guarantee prompt-injection resistance. The application checks Q&A citation IDs and exact quotes, and applies limited output checks; those checks do not prove the answer follows from the source. Search is filtered and result counts are capped, but there is no explicit input-token budget, semantic reranking or guarantee that the most relevant evidence was returned. The summary tool conversation is bounded to five model turns and six tool calls; Q&A is a separate single model request. Gemini and Azure availability, quotas and the configured index affect results.

## Provenance and limitations

lab/starter-code/kyc and lab/starter-code/config are copied from concept-week-2/live-prototype; lab/fixtures/data contains the required synthetic KYC CSVs. lab_bridge.py adapts the original data layer, routing.screen_every_party, rules, tools.open_review_case, and policy_search.search_policy. The review tool's idempotency key was extended to include party ID. gemini_agent.py adds the bounded Gemini function-calling loop. document_lab includes the Day 12 offline extraction components, schema, and synthetic documents, but does not run the full Day 12 case-management pipeline. The full original routing.run_case replay/Claude workflow and all original gates and evals are **not** invoked by this adapter; this is not a claim that the original course floor is fully satisfied.

An earlier version's Azure Search and Gemini tool workflow were observed working for one synthetic case in Skillable. Question-based policy retrieval and recent interface changes require live verification in Skillable; local tests mock external services. Real watchlists, live OCR, customer messaging, core banking, and actual onboarding decisions are not implemented.

The three earlier standalone PP sample scenarios are not shown in the queue: they used different predetermined checks and do not have equivalent case records. Their local database entries and legacy endpoints remain for compatibility.

The application queue retains local SQLite state. Activity includes application checks, case edits and review actions; Reports shows local application counts, not bank performance. To reset the demonstration, stop the server and delete demo.sqlite3 and the state folder; this removes local demo history, check results and review cases.

## Tests

After installing requirements, run `python -m unittest -v` and `python evals/run_course_evals.py`. If Node.js is available, `node tests/frontend-smoke.cjs` checks the async document-loading and form controls. The evaluation adapts applicable Day 7 reference cases to the deterministic KYC adapter and explicitly skips replay-specific checks; it does not evaluate Gemini or live search. Tests cover case routing, multiple matches, review actions, pending states, citation validation, policy failure and the simplified dashboard. Neither tests nor the heuristic output filter prove that model text is safe or supported. The course code is a teaching implementation, not production-ready security or compliance controls.

See [LAB-ALIGNMENT.md](LAB-ALIGNMENT.md) for the day-by-day mapping and remaining gaps, and [the internal brand guide](branding/BRAND-GUIDE.md) for the fictional identity and logo assets.
