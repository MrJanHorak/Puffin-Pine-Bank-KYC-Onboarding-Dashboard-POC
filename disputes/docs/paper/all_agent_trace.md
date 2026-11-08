# A supplied all-agent trace of DSP-14 (SPECIMEN, Task 6 stretch)

An alternative design, where a model agent decides every step for the same dispute. Compare it with the build's trace: `get_dispute → get_transactions → open_review_case → model:summary`.

| Step | Who picked it | Call | Note |
| --- | --- | --- | --- |
| 1 | model | `get_dispute` | |
| 2 | model | `get_transactions` | |
| 3 | model | `search_policy("unauthorised")` | Not needed for this category |
| 4 | model | reasoning: "customer says not them, likely fraud" | 1 model call |
| 5 | model | `get_transactions` again | Repeated lookup |
| 6 | model | `open_review_case` | Same outcome as the build |
| 7 | model | summary | 1 model call |

Six model turns instead of one, and the fraud routing depends on the model noticing the claim. Which rung is each design on, and what would you need to measure before climbing?
