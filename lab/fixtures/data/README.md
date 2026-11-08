# Lab data (SPECIMEN)

SPECIMEN: synthetic training data for Puffin & Pine Bank. Every name, ID and number is invented. No real person, company, bank, country or watchlist appears. Puffin & Pine Bank is a made-up bank.

These files are the lab set for the Puffin & Pine Bank course labs. Every lab ships the same copy, so results compare across days.

## Markers

- Every CSV file starts with a line beginning `# SPECIMEN:`. Programs that read the files skip lines that start with `#`.
- Every ID starts with `SPECIMEN-`, and every person or company name starts with `SPECIMEN `.
- Passport numbers read `SPECIMEN-PP-` plus seven digits.
- Countries use the codes XA to XJ, with invented names.
- Money is in XTS, the currency code set aside for testing.
- Dates are written YYYY-MM-DD.
- ID numbers in this set run from 5000 to 8999, for example SPECIMEN-APP-5007. Review cases are numbered from SPECIMEN-RC-5001.

## Files

| File | What it is |
|---|---|
| `kyc_applications_sample.csv` | A flat extract from the onboarding portal: one row per exported application, 14 columns. It is a copy taken for analysis, not the system of record. |
| `aml_alerts_extract.csv` | An extract of the AML alert queue: one row per exported alert, 12 columns. Money is in XTS. |
| `applications.csv` | The onboarding system of record: one row per application. channel is PORTAL or RM; portal_status is SUBMITTED, IN_REVIEW or RESUBMITTED; resubmission_of names the earlier application when there is one. |
| `parties.csv` | Every party on each application: the applicant company, its directors, its beneficial owners and any intermediate owning companies. ownership_pct is the share the party holds in the company named in owned_via_party_id; a blank owned_via_party_id means the share is held directly in the applicant company. declared_pep is Y or N. |
| `documents.csv` | Document metadata (no images ship): passports, proof of address, certificates of incorporation and ownership declarations. document_date is the date printed on a proof of address or a declaration. |
| `watchlist.csv` | The Global Designations List (SPECIMEN): invented sanctions and PEP (politically exposed person) entries. No real list or person appears. |
| `jurisdictions.csv` | The ten invented countries on codes XA to XJ, each with a risk tier: LOW, MEDIUM or HIGH. |
| `aml_transactions.csv` | Bank account transactions behind the alerts. alert_id names the alert a transaction raised and is blank otherwise. counterparty_country_code is blank for cash deposits. |
| `screening_results.csv` | Lab-only file (the lesson set has no copy): the last watchlist screening recorded for each applicant company, director and beneficial owner. screening_id reuses the party's number; list_version names the Global Designations List (SPECIMEN) version used; outcome is NO_MATCH or POSSIBLE_MATCH. |
| `manifest.json` | The set name, generator version, a hash of the seed, and the sha256 hash and row count of each file. |

Do not edit these files. Lesson and lab copies are checked against `manifest.json`.
