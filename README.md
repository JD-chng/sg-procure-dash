# Government procurement hiring dashboard

A one-page dashboard of procurement jobs advertised by Singapore government agencies. It is meant for a department head who wants to see, at a glance, how much procurement hiring is happening across government, who is hiring, and what skills agencies are asking for.

All figures come from public job postings on [Careers@Gov](https://jobs.careers.gov.sg/), using the open dataset that [Open Government Products](https://github.com/opengovsg/careersgovsg-jobs-data) publishes. The dashboard keeps a record of every posting it has seen, so roles stay in the figures after they are taken down from Careers@Gov.

This is an independent project. It is not run or endorsed by Careers@Gov, the Public Service, or Open Government Products. It holds no applicant, résumé, or candidate information.

## Contents

- [What the dashboard shows](#what-the-dashboard-shows)
- [How it works](#how-it-works)
- [Where the data comes from](#where-the-data-comes-from)
- [Publishing it on GitHub Pages](#publishing-it-on-github-pages)
- [Running it on your own computer](#running-it-on-your-own-computer)
- [Downloadable lists](#downloadable-lists)
- [How the numbers are worked out](#how-the-numbers-are-worked-out)
- [Changing the rules](#changing-the-rules)
- [The history file](#the-history-file)
- [Known limits](#known-limits)
- [Project layout and tests](#project-layout-and-tests)
- [Credits and licences](#credits-and-licences)

## What the dashboard shows

- **Headline figures:** how many procurement postings there are, how many are open now, how many close within 7 days, and how many offer no permanent option.
- **What changed:** a few plain sentences comparing the latest complete quarter with the one before. A year-on-year comparison switches on by itself once there is a full year of history (from Q2 2027).
- **Hiring over time:** new postings by quarter or month, and how many were still open at the end of each.
- **Agencies hiring most:** select an agency to filter the whole page to it.
- **What agencies ask for:** how often keywords such as GeBIZ, contract management, data analytics, or sustainability appear in the job text, and whether that share is rising or falling. Hover over or tap a figure to see how it was worked out.
- **Contract type and minimum experience asked.**
- **The postings themselves:** a searchable table. Each row links to Careers@Gov and opens to show the full saved text, with matched keywords highlighted.

One set of filters at the top (open or closed, period, agency, keyword) drives every number, chart, sentence, and the table. **Print summary** prints the headline page on one A4 landscape sheet, with the keyword table on a second sheet.

## How it works

```text
Careers@Gov job postings
  -> Open Government Products dataset (one CSV, refreshed twice each weekday)
  -> GitHub Actions, weekdays at 4:30pm Singapore time
       check the file, update the history, apply the rules in config/
  -> data/historical/jobs_history.csv     every posting ever seen
  -> docs/data/                           the figures, full posting text, and CSV lists
  -> GitHub Pages                         the published dashboard
```

- **No AI at run time.** Deciding which jobs count as procurement, matching keywords, and reading years of experience are all done by fixed rules written in plain text files in `config/`. The same posting always gives the same result. Search on the page is ordinary text matching in the browser. The code was written with the help of an AI coding assistant, but nothing that runs to refresh or display the dashboard calls an AI model.
- **No servers, databases, accounts, or paid services.** The processing is a short Python job that GitHub runs on a schedule. The published site is plain HTML, CSS, and JavaScript. The only outside request is downloading the public dataset.
- **The chart library is stored in this repository.** People opening the page do not load anything from a third-party site.

## Where the data comes from

1. Agencies advertise jobs on [Careers@Gov](https://jobs.careers.gov.sg/).
2. [Open Government Products](https://www.open.gov.sg/) collects those listings into the public repository [opengovsg/careersgovsg-jobs-data](https://github.com/opengovsg/careersgovsg-jobs-data), as `data/job-listings.csv`. It is scheduled for 10:10am and 3:10pm Singapore time on weekdays. In practice GitHub starts it late, and the afternoon file usually lands between about 4:10pm and 4:30pm.
3. This project downloads that file on weekday afternoons, adds it to its own history, and rebuilds the dashboard.

Because the upstream repository keeps every past version of the file in its git history, the dashboard's history was rebuilt from those past versions, starting on **9 February 2026**.

## Publishing it on GitHub Pages

The free GitHub plan publishes Pages only from a **public** repository, so the code, the data, and the CSV lists will all be public. The postings are public already, but check this is acceptable before you publish. Paid plans can publish from a private repository, but the site itself stays public unless your organisation uses GitHub Enterprise.

1. Push this repository to GitHub.
2. In **Settings → Actions → General → Workflow permissions**, choose **Read and write permissions**. Without this the refresh cannot save new data.
3. In **Settings → Pages → Build and deployment**, set **Source** to **GitHub Actions**.
4. Open **Actions → Refresh procurement dashboard → Run workflow** to publish for the first time.
5. The site appears at `https://<github-username>.github.io/<repository-name>/`.

### Refresh schedule

| When (Singapore time) | What happens |
| --- | --- |
| Weekdays, about 10:10am and 3:10pm (often up to an hour later) | Open Government Products updates its dataset |
| Weekdays, 4:30pm | This project processes the latest file and republishes the dashboard if anything changed |
| Any time | **Actions → Refresh procurement dashboard → Run workflow** runs it by hand |

The schedule is `30 8 * * 1-5` in `.github/workflows/update-data.yml` (08:30 UTC, Monday to Friday). GitHub sometimes starts scheduled jobs late or, rarely, skips one. A missed day is picked up on the next run, because postings still listed then are recorded on that day. If the upstream afternoon file lands after 4:30pm, that day's run sees the morning file instead.

Each refresh commits the new data as `github-actions[bot]` and publishes the site in the same job. Changes you push yourself under `docs/` are published by the separate **Deploy GitHub Pages** workflow.

### If a refresh fails

- The run stops before it replaces any saved data, so the last good dashboard stays online. The "Data to" date at the top of the page stops moving, and GitHub emails the repository owner.
- An empty file, a failed download, missing columns, or fewer than 500 rows is treated as an error.
- A drop of more than half the previous row count is also an error. If the upstream file really did shrink, run the workflow by hand and tick **Allow a source row-count drop**.
- GitHub pauses scheduled workflows on a public repository after 60 days with no activity. Normal refreshes keep it active. If it is paused, turn it back on under **Actions**.

## Running it on your own computer

You need Python 3.11 or newer, and git if you want to rebuild the history from scratch.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
```

Fetch the latest file and update everything:

```bash
python -m scripts.run_pipeline
```

After editing anything in `config/`, rebuild every output from the saved history without downloading. First-seen dates, last-seen dates, and listing status are left as recorded.

```bash
python -m scripts.rebuild_outputs
```

To view the site, serve the `docs/` folder. Opening `index.html` straight from disk does not work, because the page loads its data files.

```bash
python -m http.server 41731 --directory docs
```

Then open <http://127.0.0.1:41731/>.

Rebuilding the history from scratch (optional, rarely needed) clones the upstream repository, a few hundred megabytes, and replays every past version of the file. Unreadable or very small old files are skipped. If the clone fails, it starts from the current file instead.

```bash
python -m scripts.bootstrap_history
```

## Downloadable lists

Every refresh writes CSV lists so that any figure on the dashboard can be checked against the postings behind it. They open cleanly in Excel. Each list covers the full history, open and closed, and is not affected by the filters on the page.

| File | What is in it | Linked from |
| --- | --- | --- |
| `docs/data/keywords/<keyword>.csv` | Every procurement posting that mentions the keyword: status, agency, title, contract type, minimum years, dates, the words matched, where they matched, a snippet of the surrounding text, the posting link, and the full text of each part where the keyword appeared | The **CSV** link beside each keyword |
| `docs/data/keywords/index.csv` | Every keyword, the patterns it searches for, where it searches, and its counts | **Keyword list (CSV)** |
| `docs/data/experience/<band>.csv` | Every procurement posting in that experience band: the minimum years counted, `foundIn` (the line of the posting the years were taken from), the agency's own experience field, contract type, dates, the posting link, and the full requirements | The links under **Minimum experience asked** |
| `docs/data/experience/index.csv` | Every band, its range of years, and its counts | **All bands** |

The `population` column marks each posting as `core` (what the dashboard shows by default) or `duties-only` (see [Which jobs count as procurement](#which-jobs-count-as-procurement)). Filter to `core` to match the dashboard's default figures. The lists are saved in git each time, so the repository history shows how each one changed.

## How the numbers are worked out

A short version of these definitions is under **How this is counted** at the bottom of the dashboard.

### Which jobs count as procurement

Rules in `config/procurement_taxonomy.yml`. A posting is included when any of these is true:

- The title contains a strong term: procurement, purchasing, strategic sourcing, or tendering.
- The agency filed the job under the Procurement field or functional area.
- The title contains a phrase such as contract management, supplier management, or supplier contracts. "Sourcing" counts only next to another procurement term.
- The duties contain a strong phrase such as "manage procurement", "procurement of", "tender management", or "strategic sourcing".

A single standard mention of government procurement policy is not enough, and neither are two weak words such as "tender" and "vendor". "Contract employee", "employment contract", "commercialisation", and "commercial affairs" are excluded unless the title or field already marks the job as procurement.

By default the dashboard shows **core** procurement roles: those matched on the title or the field. Roles matched only on their duties are often jobs whose main work is something else, so they are hidden until **More options → Include roles that mention procurement only in the duties** is ticked. Internships and traineeships are hidden until **More options → Include internships and traineeships** is ticked.

### Dates and periods

- **First seen** is the first day the dataset contained the posting. Roles already open on 9 February 2026 count from that day, not from when they were first advertised.
- **New postings** in a month or quarter are those first seen in it. In the very first month, only roles also advertised that month are counted, so the backlog open on day one does not show as a spike.
- **Open at end of period** counts postings first seen by the last day of the period and still listed on that day.
- **Quarters** are calendar quarters. A quarter is compared only when every day of it is inside the history. Q1 2026 (from 9 February) and the current quarter ("to date") are shown but not compared.

### When a change is called an increase or decrease

Both quarters need at least 5 postings, and the gap must be at least 3 postings **and** at least 10%. Otherwise the text says "about the same" or "too few to compare". The thresholds are in `config/dashboard.yml`.

### Keyword shares and the change column

A keyword's share is the percentage of postings whose text mentions it at least once. The change column compares the share of **new** postings mentioning it in the earlier and later of two complete quarters, for example "30% → 38%". It uses shares rather than counts so a busier quarter does not make every keyword look more popular. An arrow appears only when both quarters have at least 10 new postings and the share moves by at least 5 percentage points (`keyword_trend` in `config/dashboard.yml`).

Common terms found in most government postings (audit and compliance, stakeholder management, qualifications) are marked generic. They are searched only in the duties and requirements, so standard agency text in the description is not counted, and they are listed last.

### Minimum experience

The minimum is the highest floor the posting states anywhere. "At least 3 years" in the requirements outranks an agency field of 0–8 years. The description is read only when there are no requirements. Figures above 20 are ignored (for example "over 50 years of service"), and a posting labelled Entry level counts as 0. Many agencies state 0 even for senior roles. The `foundIn` column in the experience lists shows where each figure came from.

### Contract type

Taken from the employment type the agency states, and grouped as set out in `config/dashboard.yml`. Fixed-term and contract roles count as "no permanent option".

## Changing the rules

All rules are plain text (YAML) in `config/`. You do not need to edit Python. After a change, run `python -m scripts.rebuild_outputs` or wait for the next refresh. Both apply the change to the full history. If a file has a mistake, the run stops before it replaces the dashboard.

| File | What it controls |
| --- | --- |
| `config/procurement_taxonomy.yml` | Which jobs count as procurement |
| `config/keywords.yml` | The keywords, their search patterns, and which parts of a posting they search |
| `config/dashboard.yml` | Contract-type groups, experience bands, the closing-soon window, and the thresholds for calling a change |
| `config/experience_rules.yml` | Phrases that signal entry-level roles, and career-level bands |
| `config/validation.yml` | Checks on the downloaded file, and which employment types count as internships |
| `config/sector_taxonomy.yml`, `config/pcf_competencies.yml` | Sector and competency labels, kept in the data files only (see below) |

**Keywords.** Each keyword has an `id`, a `label`, one or more patterns, and the parts of a posting to search: `title`, `responsibilities`, `requirements`, or `description`. Patterns are case-insensitive regular expressions, where `\b` marks a word boundary, so `\brfq\b` matches "RFQ" but not a word containing those letters. A keyword removed from the file has its CSV list deleted on the next run.

**Experience bands.** Each band needs a unique `id`, which becomes its file name (`docs/data/experience/<id>.csv`).

**Example:** to count "head of procurement" in the duties as a procurement role, add that phrase under `duty_phrases` in `config/procurement_taxonomy.yml`.

### Classifiers kept in the data only

Sector, career level, and competency labels are still worked out and saved in `data/processed/procurement_jobs.csv`, but they are not shown on the dashboard. Over 90% of core roles came out as "Other / Unclassified" for sector and "Broad" for career level, so the charts said little. The keyword table and experience bands replace them.

- **Sector** (`config/sector_taxonomy.yml`): ICT, built environment, general goods and services, healthcare, defence and security, professional services, facilities, transport and engineering, or Other / Unclassified. A sector is given only when the title and duties clearly favour it. The agency name is never used.
- **Career level** (`config/experience_rules.yml`): taken from stated years of experience, never from words such as "senior" in the title. Ranges that cross bands, or wide ranges such as 3–99, are left as Broad.
- **Competencies** (`config/pcf_competencies.yml`): procurement activities taken from public material, such as sourcing, contract management, and supplier management. **These are not the official Procurement Competency Framework**, which is not public. Replace the phrase lists with the official names if you have them.

## The history file

`data/historical/jobs_history.csv` has one row per posting, identified by `platform|jobId|postingNo`.

On each run:

- A posting seen for the first time is added, with its first-seen and last-seen dates set to that day.
- A posting still listed has its details refreshed. Its first-seen date does not change.
- A posting that has disappeared is kept, marked as no longer listed, and keeps the last day it was seen.
- A posting that comes back is marked as listed again, keeps its first-seen date, and has its relist count increased.

Full text is saved for procurement postings and near-misses. Other postings keep only the title, agency, dates, and status, so the file does not grow with unrelated text. If an agency edits a posting while it is open, the latest text is kept. Earlier versions remain in git history.

All dates are plain `YYYY-MM-DD` dates in Singapore time. The source's "no closing date" value (the year 9999) is saved as blank. `daysListed` is the span between first and last seen, not the official advertising period.

## Known limits

- **Only Careers@Gov.** Agencies that also hire through their own sites or recruiters will be undercounted. There is no salary information, and no ministry column, and the dashboard does not guess one.
- **Short-lived postings can be missed.** A job that opens and closes between two daily runs never appears.
- **Short history.** It starts on 9 February 2026. Year-on-year comparison becomes possible from Q2 2027.
- **Small numbers.** About 140 new core procurement postings arrive per quarter, so one agency's hiring round can move a figure. Treat small changes as signals, not facts.
- **Rule-based matching.** The rules can miss wording they were not written for, or catch unexpected wording. A keyword absent from a posting does not mean the skill is not needed. Check the CSV lists before quoting a figure as a target.
- **Old links break.** Careers@Gov often removes closed postings, so their links can show "not found". The full text is kept in this project's history and lists.

## Project layout and tests

```text
config/                  rules: procurement, keywords, dashboard, experience, validation
scripts/                 download, history, rules, keyword and experience lists, dashboard data
data/raw/latest.csv      last accepted source file
data/historical/         history of every posting seen, and the source checksum
data/processed/          procurement postings only, with every classifier column
docs/                    the published site
docs/data/keywords/      one CSV per keyword, plus index.csv
docs/data/experience/    one CSV per experience band, plus index.csv
tests/                   automated tests
.github/workflows/       weekday refresh, and Pages publishing
```

Run the tests with `python -m pytest -q`. They do not download anything. They cover posting keys, history (including a posting that leaves and returns), date handling, the procurement rules and their exclusions, experience parsing, keyword matching, the CSV lists, contract and experience bands, partial quarters and the year-on-year start, and empty or broken source files. The refresh runs the tests first and stops if any fail.

## Credits and licences

This project stands on the work of others:

- **[Careers@Gov](https://jobs.careers.gov.sg/)**, the Singapore Government's job portal, and the agencies who write and publish the postings. All job content belongs to them.
- **[Open Government Products](https://www.open.gov.sg/)**, for [careersgovsg-jobs-data](https://github.com/opengovsg/careersgovsg-jobs-data), which collects Careers@Gov listings twice each weekday and keeps every past version. Without it this dashboard and its history would not exist. Their repository is released under the MIT License, Copyright (c) 2026 Open Government Products.
- **[Apache ECharts](https://echarts.apache.org/)** 5.5.1, which draws the charts. It is stored at `docs/assets/vendor/echarts.min.js` under the Apache License 2.0, and its notice is in `docs/assets/vendor/NOTICE.txt`.
- **[pandas](https://pandas.pydata.org/)** (BSD 3-Clause License), for reading and writing the data files.
- **[PyYAML](https://pyyaml.org/)** (MIT License), for reading the rule files.
- **[pytest](https://pytest.org/)** (MIT License), for the automated tests.
- **[GitHub Actions](https://docs.github.com/actions)** and **[GitHub Pages](https://pages.github.com/)**, which run the refresh and host the site at no cost.

This project's own code and documentation are released under the [MIT License](LICENSE). That licence does not cover the bundled ECharts file, which keeps its Apache License 2.0, or the job posting content, which belongs to the agencies that published it.
