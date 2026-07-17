# Operations

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
