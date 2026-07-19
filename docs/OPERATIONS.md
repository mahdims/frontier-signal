# Operations

## GitHub Actions daily email

The `Daily Frontier Signal radar` workflow runs the complete pipeline every day at
04:30 in the `America/Vancouver` timezone. This corresponds to 11:30 UTC during PDT
and 12:30 UTC during PST, keeping the start at least 90 minutes beyond DeepSeek's
06:00–10:00 UTC peak-pricing window. GitHub handles daylight-saving changes.
It can also be started manually with **Actions → Daily Frontier Signal radar → Run workflow**.

Add these repository secrets under **Settings → Secrets and variables → Actions**:

- `DEEPSEEK_API_KEY`: API key used for analysis and synthesis.
- `GMAIL_USERNAME`: Gmail address used to send the report.
- `GMAIL_APP_PASSWORD`: Google App Password for that Gmail account, not its normal password.
- `YOUTUBE_API_KEY`: optional; only needed if the YouTube collector is enabled.
- `X_BEARER_TOKEN`: optional; required before enabling the X collector. X API usage may
  incur separate pay-per-use charges.

Add this repository variable under **Settings → Secrets and variables → Actions → Variables**:

- `REPORT_EMAIL_TO`: destination Gmail address (it may be the same address).

The workflow uses the built-in `GITHUB_TOKEN` for GitHub collection. It restores the
SQLite database from the previous run so already-seen items are not analyzed and emailed
again, uploads each full Markdown report as a 30-day workflow artifact, and sends a compact
title/label/summary digest with the full Markdown report attached. The uploaded artifact
also contains the SQLite database, so collected items, analyses, and LLM usage records can
be recovered independently of the workflow cache.

If email delivery fails after a successful run, manually run the workflow with
`delivery_only` enabled. It restores the cached database, regenerates and sends the report,
and does not collect sources or call DeepSeek.

## Delivery ledger and duplicate prevention

Each generated report and its included analysis IDs are stored in the SQLite database.
Normal daily reports select only analyses that have never appeared in an earlier report.
If SMTP delivery fails, the report remains pending and `delivery_only` resends the exact
stored content rather than generating or analyzing anything again. After successful email
delivery, the workflow marks the report delivered and saves a second database checkpoint.

Manual workflow runs expose an `include_reported` option for intentionally building a
report that may repeat previously reported items. Leave it disabled for routine delivery.
The CLI equivalent is `frontier-signal report --include-reported`.

Before analysis, each daily run removes only unanalysed backlog that is older than seven
days, belongs to a disabled/removed source, or is a GitHub issue from a release-only feed.
Previously paid analyses and stored reports are retained. Report selection also rejects
items older than seven days, limits GitHub to three entries, limits each source to one
entry, and reserves available space for Chinese media, academic papers, and social signals.
These defaults can be adjusted with the `REPORT_*` and `MAX_ITEM_AGE_DAYS` environment
settings. Run `frontier-signal prune-backlog --days 7` to apply the same safe cleanup
locally.

Scheduled workflows only run from the repository's default branch, so merge the workflow
there after testing it with a manual run.

## Recommended launchd schedule on macOS

Create a shell script that activates the virtual environment and runs:

```bash
frontier-signal run-daily
```

Schedule collection more frequently only after the first week. Running every source every five minutes is wasteful and will trigger rate limits.

## Suggested cadence

- GitHub/Hacker News: every 30–60 minutes
- arXiv/OpenReview/YouTube: every 2–4 hours
- Daily report: 07:30 America/Vancouver
- Weekly report: Friday 16:00 America/Vancouver

## Failure handling

Collectors are isolated. One failed source must not abort a run. Failures are printed in the collection result. Add persistent source-run logging before production deployment.

## Calibration protocol

For the first 100 top-ranked items, record one verdict:

- useful;
- hype;
- known;
- wrong topic;
- good but late.

After 100 labels, adjust topic weights and the Pro threshold. Do not train a personalized ranker before collecting enough feedback.
