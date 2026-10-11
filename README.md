# Government procurement hiring dashboard

Public workforce-planning view of procurement roles posted on [Careers@Gov](https://jobs.careers.gov.sg/), built only from the open dataset published by [OpenGovSG](https://github.com/opengovsg/careersgovsg-jobs-data).

The site is static. A scheduled GitHub Action downloads the latest extract, keeps a history of postings after they leave Careers@Gov, classifies procurement roles with rules stored in YAML, and republishes the dashboard to GitHub Pages. There is no application server, database, or paid API.

This repository does not hold applicant, résumé, or candidate information.

## What the dashboard answers

It is a one-glance page for a department head following procurement hiring across government.

- How many procurement postings are there, how many are open now, and how many close this week?
- Is hiring picking up? New postings per quarter, compared with the previous quarter. Year-on-year turns on automatically once there is a full year of complete quarters.
- Which agencies hire the most procurement staff?
- What do agencies ask for in the job text (GeBIZ, contract management, analytics, sustainability, and so on), and is that changing?
- How many roles offer no permanent option, and how much experience is asked for?
- Which postings are behind each number? Every posting links to Careers@Gov and can be expanded to show the full archived text with the matched keywords highlighted.

One status toggle (All, Open now, Closed) and the period, agency, and keyword filters drive every number, chart, sentence, and the table. **Print summary** prints the summary on one A4 landscape page, with the keyword table on a second page.

## Architecture

```text
Careers@Gov
  -> OpenGovSG jobs CSV (data/job-listings.csv)
  -> GitHub Actions, weekdays 4:30pm Singapore time
  -> Python: validate, update history, classify
  -> data/historical/jobs_history.csv
  -> docs/data/dashboard_data.json   numbers and tags for the page
  -> docs/data/job_text.json         full posting text, loaded on demand
  -> docs/data/keywords/*.csv        one cross-reference list per keyword
  -> GitHub Pages
```

Python runs only in GitHub Actions (or on your machine). The published site is HTML, CSS, and JavaScript. Charts use Apache ECharts, stored in this repository so the page does not call a CDN when someone opens it.

## Run it locally

Requirements: Python 3.11 or newer, and git if you want to replay upstream history.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
```

Seed history from upstream snapshots (once). This clones the OpenGovSG repository, which is a few hundred megabytes. Bad old files are skipped. If the clone fails, the script continues from the current CSV.

```bash
python -m scripts.bootstrap_history
```

Later refreshes only pull the current file:

```bash
python -m scripts.run_pipeline
```

After editing anything in `config/`, rebuild every output from the stored history without downloading. First-seen, last-seen, and listing status are not touched.

```bash
python -m scripts.rebuild_outputs
```

Serve the site from `docs/` so the JSON loads. Opening `index.html` as a file will not work.

```bash
python -m http.server 41731 --directory docs
```

Then open `http://127.0.0.1:41731/`.

A second run on the same Singapore calendar day, with an unchanged source file, exits without rewriting the dashboard.

## Deploy on GitHub Pages

The live site has to be a **public** repository. GitHub Pages on a private repository is a paid feature, and this project does not use paid hosting.

1. Push this repository to GitHub.
2. In **Settings → Actions → General**, allow Actions to read and write. The refresh workflow cannot commit new data if the organisation forces the token to read-only.
3. In **Settings → Pages → Build and deployment**, set **Source** to **GitHub Actions**.
4. Open **Actions → Refresh procurement dashboard → Run workflow** for the first successful publish.
5. Confirm the scheduled run. The cron is `30 8 * * 1-5`, which is 08:30 UTC, Monday to Friday: **4:30pm Singapore time**. GitHub sometimes starts scheduled jobs later than the cron time. The workflow runs after the upstream afternoon update (about 3:10pm Singapore time).
6. The site is published at `https://<github-username>.github.io/<repository-name>/`.

The refresh workflow commits data as `github-actions[bot]` only when the historical file or the dashboard JSON changed, then deploys Pages in that same job. A bot commit does not start a second workflow, which is why deploy is not a separate step waiting on `push`.

Edits you push yourself under `docs/` are published by **Deploy GitHub Pages**.

### If a run fails

- The workflow stops before it replaces committed data. The last good dashboard stays up.
- An empty file, a failed download, missing columns, or a row count below 500 is an error.
- A drop of more than half the previous row count is also an error. If the upstream file really shrank, run the workflow manually and set **Allow a source row-count drop** to true. An empty file still fails.
- Scheduled workflows are disabled after 60 days without repository activity. A normal weekday change keeps the repository active. If GitHub turns the schedule off, make any commit and re-enable the workflow.

## Data refresh

| When | What |
| --- | --- |
| About 10:10am and 3:10pm Singapore time, weekdays | OpenGovSG refreshes its dataset |
| 4:30pm Singapore time, weekdays | This repository processes the afternoon extract |
| Any time | **Actions → Refresh procurement dashboard → Run workflow** |

Dates in the pipeline use Asia/Singapore, not the UTC clock on the runner.

## Classification

Rules live in `config/` and are loaded at runtime. You can change them without editing Python. After a change, run `python -m scripts.rebuild_outputs`, or let the next GitHub Action run pick it up. Invalid YAML or an invalid keyword pattern fails the run before it replaces the dashboard.

### Keywords

`config/keywords.yml`

Each keyword has an id, a label, one or more regular expressions (case-insensitive, `\b` for word boundaries), and the parts of the posting to search: `title`, `responsibilities`, `requirements`, `description`. Generic terms common to most government postings (audit and compliance, stakeholder management, qualifications) are marked `generic`, are searched only in the duties and requirements, and are listed last.

Every run writes:

- `docs/data/keywords/<id>.csv`: every procurement posting that mentions the keyword, open and closed. Columns include status, whether it is a core or duties-only match, agency, title, contract type, minimum years, dates, the words matched, where they matched, a snippet around the first match, the posting link, and the full text of each part where the keyword appeared. Files are UTF-8 with a byte-order mark so Excel opens them cleanly.
- `docs/data/keywords/index.csv`: every keyword with its patterns, where it is searched, and its counts.

The files are rebuilt from the full history each run and committed, so git history shows how each list changed. They are also linked from the dashboard. A keyword removed from the config has its file deleted on the next run.

The **Change** column compares the share of new postings that mention a keyword in two complete quarters. It shows a direction only when both quarters have enough new postings and the share moves by enough percentage points (`keyword_trend` in `config/dashboard.yml`).

### Dashboard rules

`config/dashboard.yml`

- Contract type mapping from the source employment type, and which labels count as “no permanent option”.
- Minimum-experience bands.
- Closing-soon window (7 days).
- When a quarter change is called an increase or decrease: both quarters need at least 5 postings, and the gap must be at least 3 postings and 10%.

Quarters are calendar quarters. A quarter is compared only when every day of it is inside the history. The first quarter of history (from 9 February 2026) and the current quarter (“to date”) are shown but not compared.

### Minimum experience

`experienceStatedMinYears` is the highest minimum the posting states anywhere: “at least 3 years” in the requirements outranks a structured 0–8 range. The description is read only when the requirements are empty, values above 20 are ignored (“over 50 years of service”), and a posting labelled Entry level counts as 0.

### Procurement relevance

`config/procurement_taxonomy.yml`

A posting is included when any of these is true:

- The title contains a strong term: procurement, purchasing, strategic sourcing, tendering.
- The source field or functional area is Procurement.
- The title contains a medium phrase such as contract management, supplier management, or supplier contracts. The word “sourcing” counts only beside another procurement term.
- The duties contain a strong phrase such as “manage procurement”, “procurement of”, “tender management”, or “strategic sourcing”.

A single boilerplate mention of government procurement policy is not enough. Two weak words such as “tender” and “vendor” are not enough. “Contract employee”, “employment contract”, commercialisation, and “commercial affairs” are excluded unless the title or field is already high-confidence.

The processed file records `procurementMatchScore`, `procurementMatchedTerms`, and `procurementMatchBasis` (`title`, `field`, or `duty_phrase`).

On a recent extract this includes some roles whose main work is not procurement but whose duties mention buying goods or services. That is an accepted limit of the balanced rule. The dashboard hides those duties-only matches until **More options → Include roles that mention procurement only in the duties** is checked. The default population is core procurement: a procurement term in the title, or a Procurement field. Reset returns to that default.

### Sector, career level, and competencies (data files only)

These classifiers still run and their columns stay in `data/processed/procurement_jobs.csv`, but they are no longer shown on the dashboard. Over 90% of core roles came out as Other / Unclassified for sector and Broad for career level, so the charts said little. The keyword table and the minimum-experience bands replace them.

#### Sector

`config/sector_taxonomy.yml`

Sectors: ICT / Digital / Technology, Built Environment / Infrastructure / Construction, General Goods & Services / Corporate, Healthcare, Defence / Security, Professional Services, Facilities / Estate, Transport / Engineering, and Other / Unclassified.

The title and duties must clear a score, and the winner must lead the next sector by a set margin. Agency name is never used. Uncertain roles stay Other / Unclassified.

#### Career level

`config/experience_rules.yml`

Level is taken from explicit years, not from words like “senior” in the title.

| Evidence | Level |
| --- | --- |
| Fresh graduates, no experience required, or the label Entry level | Fresh Graduate / Entry Level |
| A narrow range inside 1–3 years | Early Career |
| A narrow range inside 4–7 years | Mid-Career |
| A narrow range of 8 or more years, “8+ years”, or “minimum 8 years” | Experienced / Senior |
| No usable text, structured 0–0 without an entry label, a range that crosses bands, a wide open ceiling such as 3–99, or “at least 3 years” | Broad / No Clear Preference |

Structured 0–0 is common in the source even for experienced titles. Those rows stay broad unless the text says entry level.

A range that sits entirely inside one band keeps that band. A range that crosses a band boundary does not get forced into the lower band.

#### Competencies

`config/pcf_competencies.yml`

These labels follow procurement activities described in public material: policy and governance, sourcing and tendering, bid evaluation, contract management, supplier management, category management, operations, and systems. **They are not the unpublished internal Procurement Competency Framework.** Replace the phrase lists with the official names if you have them. One posting can match several labels, so the bars will not sum to the number of postings.

### Internships

Internships and traineeships stay in the data. The dashboard hides them until **More options → Include internships and traineeships** is turned on. The employment types are listed in `config/validation.yml`.

## History

`data/historical/jobs_history.csv` has one row per posting. The key is:

```text
platform|jobId|postingNo
```

Empty parts stay empty. Greenhouse postings have no posting number. Workable uses the account slug as `jobId` and the shortcode as `postingNo`, so both parts are required.

Each run:

- adds a new key, with first-seen and last-seen set to the Singapore run date
- refreshes a key that is still listed, without changing first-seen
- keeps a key that disappeared, sets currently listed to false, and leaves last-seen on the last day it was present
- if that key returns, sets currently listed back to true, moves last-seen forward, keeps first-seen, and increments `relistCount`

Full description text is stored for procurement matches and near-misses. Other rows keep the title, agency, dates, and listing status so the file does not grow with every unrelated description. Text is the latest version seen; an edit made while a posting is open replaces the earlier text, which remains in git history.

`startDate`, `closingDate`, and `postingDate` are plain `YYYY-MM-DD` dates in Singapore time. The source's year-9999 “no closing date” value is stored as blank.

`daysListed` is the observed span from first-seen to last-seen, including any gap while a posting was down. It is not the official advertisement lifetime.

The hiring trend counts a posting in the month or quarter it was **first observed**, and only inside snapshot coverage. In the first covered month, a posting counts only when its posting date is in that same month. Roles that were already open on the first snapshot, with older posting dates, stay in the historical total and stay out of that first bar. The line on the same chart counts postings first seen on or before the last day of each period and still listed that day.

### Replaying older snapshots

`scripts/bootstrap_history.py` is optional and is not called by the weekday workflow. It reclones the upstream repository and rebuilds history from scratch, so running it twice does not double-count relists. Metadata field `historySource` is `upstream-replay` or `current-snapshot`.

Snapshots taken before the `platform` column existed are treated as HRP postings. A file that is empty, unreadable, or below 50 rows is skipped. The replay continues with the next snapshot.

## Updating the taxonomies

Edit the YAML file, keep the indentation, and run the pipeline. Phrase matching is case-insensitive and uses word boundaries. Short tokens such as `RFQ` will not match inside another word.

Example, to treat “head of procurement” in the duties as a match, add that line under `duty_phrases` in `config/procurement_taxonomy.yml`.

## Data limits

- Classification is a heuristic. Review `procurementMatchedTerms` in `data/processed/procurement_jobs.csv`, or the keyword CSVs, before using a cut as a target.
- Keyword counts depend on how agencies word postings. A keyword absent from a posting does not mean the skill is not needed.
- Jobs that opened and closed between snapshots, or before the upstream repository existed, are missing.
- Counting by posting date alone would treat long-lived vacancies as hiring in old months. The trend does not do that.
- Closed vacancy links can return a Careers@Gov “not found” page.
- The source has no ministry column. This dashboard does not infer one.

## Project layout

```text
config/                  classification, keyword, dashboard, and validation rules
scripts/                 download, history, classifiers, keywords, dashboard JSON, bootstrap, rebuild
data/raw/latest.csv      last accepted source file
data/historical/         persistent posting table and source checksum
data/processed/          procurement rows only
docs/                    static site published by GitHub Pages
docs/data/keywords/      one CSV per keyword, plus index.csv
tests/                   parser, history, and validation tests
.github/workflows/       weekday refresh and Pages deploy
```

## Tests

```bash
python -m pytest -q
```

Tests do not download the source file. They cover composite keys, history (including a posting that leaves and returns), plain-date archiving, the balanced procurement rule, the contract-employee exclusion, experience phrases and stated minimums, broad ranges, weak sector scores, keyword matching and keyword files, contract and experience bands, partial quarters and the year-on-year start, empty files, and timestamp parsing.
