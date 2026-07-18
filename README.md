# Frontier Signal v1

A provenance-first AI/OR technical-intelligence pipeline.

The system collects academic, code, industry, social, event, and Chinese-language signals; preserves the original source links; extracts atomic claims; separates technical confidence from impact; ranks items against a personal research ontology; and produces an evidence-linked daily radar.

## Design constraints

1. **Collectors are deterministic.** LLMs do not browse autonomously.
2. **Every claim retains source provenance.**
3. **Impact is not truth.** Technical confidence and impact velocity are separate scores.
4. **China is a first-class region.** Original Mandarin is retained alongside English translation.
5. **Closed/private platforms are not scraped.** WeChat groups, Jike, and restricted Weibo content enter through manual forwarding, public URLs, exports, or compliant monitoring tools.
6. **Most tokens use DeepSeek V4 Flash.** V4 Pro is reserved for contradiction analysis, skepticism, and final synthesis.
7. **The first version is intentionally not a fully autonomous “agent swarm.”** Agents are typed processing stages with JSON contracts.

## Current DeepSeek configuration

- Base URL: `https://api.deepseek.com`
- Fast model: `deepseek-v4-flash`
- Deliberative model: `deepseek-v4-pro`
- Both support JSON output and tool calls.
- This repository does not use the deprecated aliases `deepseek-chat` or `deepseek-reasoner`.

Official documentation:
- https://api-docs.deepseek.com/quick_start/pricing/
- https://api-docs.deepseek.com/api/create-chat-completion/
- https://api-docs.deepseek.com/guides/thinking_mode/

## What works in v1

- arXiv collection through the Atom API
- Generic RSS/Atom feeds
- GitHub releases and issues
- Hacker News new/best stories
- Bluesky public technical-post search
- X seven-day recent search when an `X_BEARER_TOKEN` is configured
- OpenReview API v2 venue ingestion
- YouTube search API
- Manual JSONL intake for WeChat/Jike/Weibo/Zhihu/private groups
- Automated QbitAI Chinese-language RSS intake
- A 50-outlet China-focused media registry with 22 live-tested automated RSS/public-web sources
- Per-source AI keyword filters and small collection caps to control noise and LLM cost
- URL and fuzzy-title deduplication
- Mandarin/English normalization
- Claim extraction
- Topic/entity extraction
- Impact and technical scoring
- DeepSeek Pro skeptic pass for selected items
- Markdown daily report with direct links
- SQLite by default; PostgreSQL-ready SQLAlchemy models
- Daily cost guard and usage log
- Database-backed report delivery ledger that prevents repeat items and preserves failed email deliveries

## Quick start

```bash
cd frontier-signal-v1
cp .env.example .env
# Add DEEPSEEK_API_KEY and optionally GITHUB_TOKEN / YOUTUBE_API_KEY.

python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

frontier-signal init-db
frontier-signal collect
frontier-signal analyze --limit 100
frontier-signal report --hours 30
```

One-command daily run:

```bash
frontier-signal run-daily
```

The report is written to:

```text
outputs/daily/YYYY-MM-DD.md
```

## Docker database

SQLite is sufficient for the first run. To use PostgreSQL:

```bash
docker compose up -d postgres
```

Then set:

```env
DATABASE_URL=postgresql+psycopg://frontier:frontier@localhost:5432/frontier_signal
```

## Manual Chinese/social intake

Create a JSONL file:

```json
{"source_id":"wechat_qwen","url":"https://mp.weixin.qq.com/...","title":"原始标题","content":"原文或摘要","author_name":"通义千问","language":"zh","published_at":"2026-07-16T08:30:00+08:00"}
```

Then run:

```bash
frontier-signal ingest-manual data/manual/china-intake.jsonl
frontier-signal analyze --limit 100
frontier-signal report
```

For a screenshot-only private-group item, do not invent a public URL. Use a local evidence identifier and mark it private:

```json
{"source_id":"wechat_private","url":"private://wechat/2026-07-16/001","title":"群聊截图","content":"Manually transcribed text","language":"zh","metadata":{"visibility":"private","redistribution_allowed":false}}
```

Private content is excluded from externally shareable reports by default.

## CLI

```text
frontier-signal init-db
frontier-signal collect [--source SOURCE_ID]
frontier-signal ingest-manual PATH
frontier-signal analyze [--limit N]
frontier-signal report [--hours N]
frontier-signal run-daily
frontier-signal sources
```

## V1 acceptance criteria

A v1 run is acceptable when:

- at least five source types ingest successfully;
- all displayed items contain a resolvable source URL;
- duplicate rate after normalization is below 10%;
- every ranked item exposes all six component scores;
- Chinese items retain original text and translated text;
- Pro is used for less than 10% of analyzed items;
- daily report contains at most 15 items;
- no private-source text is exposed in shareable output;
- a failed collector does not stop other collectors.

## Known limitations

- No vector database in v1. Deduplication uses canonical URLs, hashes, and title similarity.
- Social-platform API access varies by account and region.
- Jike and WeChat do not have a stable general-purpose public collection API for this use case.
- Trend time-series are basic until enough history accumulates.
- Person roles are stored as time-sensitive claims and must be reverified; they are not hard-coded as permanent facts.
- OpenReview venue identifiers can differ. Update `config/sources.yaml` when a venue changes.
