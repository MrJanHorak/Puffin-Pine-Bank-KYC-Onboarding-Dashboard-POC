# Lab-to-POC alignment

This is a teaching POC with fictional data. A copied module is listed as integrated only where the POC actually calls it; other course materials remain learning resources, not proof of functionality.

| Day | Lab concept | Where it appears in Pineway | Remaining work |
| --- | --- | --- | --- |
| 1 | Scope, source-of-truth and data readiness | The course CSV data layer supplies the 200 original cases; one explicitly separate example is assembled from synthetic documents. | No measured bank process baseline or validated real data access. |
| 2 | Specification, review and eval habits | README, small automated tests, checked-in reference cases. | This does not reproduce the lesson's full engineering workflow. |
| 3 | PRD, rules and cost | The course `kyc.rules` evaluates the lab case pack; missing data holds the case. The 200 original records support the data layer's four exercise overrides, with local audit and recheck. | Token/cost tracking and the original full PRD acceptance suite are not integrated. |
| 4 | Context and retrieval | The course `policy_search` client queries the configured Azure index; retrieved sections feed a read-only Gemini tool. | Fixed training query; relevance and model claims need human validation. |
| 5 | Tool contracts and safe writes | The course screening and review-case tools run in code; the agent has bounded read-only tools. Reviewer actions use a separate scoped adapter. | The original full tool/MCP suite and multi-process/production controls are not integrated. |
| 6 | Autonomy and POC floor | Analyst workspace displays status, reasons, screening and sources; the model cannot execute a decision action. | The full original floor validator and `routing.run_case` agent/replay path are not invoked. |
| 7 | Evals and red teaming | `evals/run_course_evals.py` runs applicable reference cases against the adapter; unit tests exercise several boundaries. | One reference trajectory is skipped; no complete live Gemini red-team or original full-suite claim. |
| 8 | Risk and approvals | Missing or unverified evidence holds the linked case. Reviewer actions are explicit and cannot approve, reject or clear a match. | Full original gate engine, access control, output validation and responsible-AI review are not implemented. |
| 9 | Runtime, monitoring and cost | Local Python app, a synthetic screening circuit breaker and visible activity/report counts. | No live operational alerting, token/cost measurements, SLOs or tested deployment architecture. |
| 10 | Handoff and runbook | README and this alignment guide record setup, operation and limitations. | A full current handoff, ownership map, pilot decision and operational runbook are still needed. |
| 11–12 | Document extraction and review | The original offline `kit.extract.OfflineExtractor`, `kit.review.review_items` and schema read CASE-A/B/C. The linked 5201 example supports explicit analyst corrections and synthetic supplement review. | No live Document Intelligence, arbitrary upload, full original case-management pipeline or real client documents. |

The linked review adapter records synthetic data in local SQLite. It is not the original `CaseManagementAPI` and is not exposed to Gemini as a write tool. Source files and course CSVs are unchanged. Reviewer confirmation is simulated without authentication; source matching and a local record do not prove an identity or make the application approved.
