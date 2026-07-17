# Frontier Signal v1 — Concrete implementation plan

## 1. Product definition

**Name:** Frontier Signal  
**Purpose:** Detect technically credible AI/OR developments before mainstream coverage, while separately measuring real-world impact and Chinese-market momentum.

### Primary outputs

1. **Daily Radar** — maximum 15 evidence-linked items.
2. **Immediate Watch Alerts** — only high-relevance, high-earliness events.
3. **Weekly Trend Memo** — clusters, contradictions, lead/lag, and experiments worth running.
4. **Searchable item store** — source, claims, entities, scores, and user feedback.

### Item labels

- `ACT`
- `RESEARCH_OPPORTUNITY`
- `WATCH_CAREFULLY`
- `CHINA_EARLY_SIGNAL`
- `LIKELY_HYPE`
- `REPACKAGING`
- `ROUTINE`

## 2. V1 architecture

```text
Collectors
  -> normalization
  -> privacy filter
  -> deterministic deduplication
  -> Flash translation/claim extraction
  -> deterministic feature computation
  -> Flash scoring
  -> Pro skeptic pass on selected items
  -> weighted ranking
  -> evidence-linked report
```

### Why this is not an open-ended swarm

Open-ended agent conversations create:
- duplicated reasoning;
- untraceable claims;
- unstable cost;
- fabricated consensus;
- difficult retries.

V1 uses named agents as stateless functions with strict input/output schemas.

## 3. Named agents and model routing

| Agent | Implementation name | Model | Thinking | Trigger |
|---|---|---:|---:|---|
| Language Normalizer | `TranslatorAgent` | V4 Flash | disabled | Non-English item |
| Claim Extractor | `ClaimExtractorAgent` | V4 Flash | disabled | Every unique item |
| Topic/Entity Tagger | Included in extractor | V4 Flash | disabled | Every unique item |
| Impact Analyst | `ImpactAgent` | V4 Flash | disabled | Every unique item |
| Technical Assessor | Included in impact agent | V4 Flash | disabled | Every unique item |
| Skeptic | `SkepticAgent` | V4 Pro | enabled/high | Priority ≥ 68, marketing risk ≥ 65, or contradictory evidence |
| Daily Editor | `DailyEditorAgent` | V4 Pro | enabled/high | Final top items only |
| Weekly Synthesizer | `TrendSynthesizerAgent` | V4 Pro | enabled/max | Weekly clusters |
| Source Curator | deterministic + optional Pro | Pro only on ambiguity | New source/person candidate |
| Privacy Gate | deterministic | none | Every item |

### Expected model split

- Flash: 90–97% of tokens
- Pro: 3–10% of tokens
- Pro must never be used merely to translate or summarize a single clean item.

## 4. DeepSeek request policy

### Flash calls

- `model=deepseek-v4-flash`
- `thinking={"type":"disabled"}`
- `response_format={"type":"json_object"}`
- temperature 0.1
- max output 2,500 tokens

### Pro calls

- `model=deepseek-v4-pro`
- `thinking={"type":"enabled"}`
- `reasoning_effort="high"` or `"max"`
- `response_format={"type":"json_object"}`
- do not set temperature in thinking mode
- max output 5,000 tokens

### Failure policy

1. Retry 429/5xx with exponential backoff.
2. Validate JSON against Pydantic.
3. Retry once with validation errors included.
4. If still invalid, mark `analysis_failed`, preserve raw item, and continue.
5. Never silently fabricate missing source metadata.

## 5. Data model

### Raw item

- source ID
- source type
- canonical source URL
- external platform ID
- original title
- original body
- author/display name
- original language
- publication timestamp
- retrieval timestamp
- region
- public/private visibility
- raw metadata
- content SHA-256

### Analysis

- translated title
- English summary
- atomic claims
- entities
- topics
- evidence links
- technical confidence
- impact velocity
- personal relevance
- earliness
- source diversity
- marketing risk
- skeptic objections
- classification
- priority score
- model and prompt version

## 6. Source rollout

### Enabled in the runnable v1

1. arXiv
2. Optimization Online RSS
3. GitHub
4. Hacker News
5. OpenReview
6. YouTube
7. Generic RSS
8. Manual JSONL intake

### China public-web registry

- 智源社区 / BAAI Hub
- 魔搭社区 / ModelScope
- 启智社区 / OpenI
- 机器之心
- 量子位
- 新智元
- InfoQ 中国 AI
- 36氪 AI
- 雷峰网 AI
- DeepSeek official channels
- 通义千问 / Qwen official channels
- 字节跳动 Seed
- 智谱 AI / Z.ai
- 月之暗面 / Kimi
- MiniMax
- 百川智能
- 阶跃星辰
- 面壁智能 / OpenBMB
- 上海人工智能实验室
- 清华 AIR
- 清华 KEG

### Semi-manual/high-value channels

- WeChat public accounts
- WeChat technical groups
- Jike
- selected Weibo accounts
- selected Zhihu authors/columns

Use forwarding, exports, public URLs, or a browser “save to intake” action. Do not build account-evasion or private-group scraping.

## 7. Initial research ontology

### Weight 1.00

- agent evaluation
- lifelong agents
- self-evolving agents
- test-time scaling
- agent memory
- multi-agent systems
- vision-language embeddings
- multimodal retrieval
- spatial reasoning
- neural combinatorial optimization
- LLMs for optimization modeling
- vehicle routing
- metaheuristics
- learned search
- solver infrastructure

### Weight 0.75

- inference systems
- multimodal foundation models
- synthetic data
- evaluation methodology
- AI systems
- world models
- model compression
- long-context systems
- reinforcement learning

### Weight 0.25

- generic chatbot products
- prompt lists
- wrappers without technical novelty
- funding without technical consequence
- leaderboard claims without code

## 8. Ranking formula

```text
priority =
  0.32 * personal_relevance
+ 0.18 * earliness
+ 0.17 * technical_confidence
+ 0.13 * impact_velocity
+ 0.10 * source_diversity
+ 0.10 * source_historical_precision
- 0.10 * marketing_risk
- duplication_penalty
```

All inputs are normalized to `[0,100]`.

### Hard rules

- No public source link: cannot enter Daily Radar.
- Private content: cannot be quoted in shareable reports.
- Single company announcement with no independent evidence: technical confidence capped at 65.
- No code for a code-release claim: confidence capped at 55.
- Engagement alone cannot raise technical confidence.
- A senior title affects impact/proximity, not truth.
- Independent reproduction may raise technical confidence by up to 20.
- Multiple outlets copying one press release count as one source family.

## 9. Seven-day implementation schedule

### Day 1 — environment and storage

- Create `.env`.
- Start SQLite or PostgreSQL.
- Run `frontier-signal init-db`.
- Insert source registry.
- Validate DeepSeek model access with a JSON-output smoke test.

**Exit criterion:** one test item can be saved and analyzed.

### Day 2 — deterministic collectors

- Enable arXiv queries.
- Add GitHub token.
- Enable GitHub release/issue watchers.
- Enable Hacker News.
- Confirm Optimization Online feed.

**Exit criterion:** at least 50 raw items collected with no LLM calls.

### Day 3 — bilingual analysis

- Run translation and extraction on 20 English and 20 Mandarin items.
- Inspect claim atomicity.
- Tighten topic aliases and organization aliases.

**Exit criterion:** ≥90% valid JSON; original Chinese retained.

### Day 4 — scoring and skeptic

- Inspect score distributions.
- Correct score inflation.
- Run Pro skeptic only above threshold.

**Exit criterion:** Pro calls below 10% of items.

### Day 5 — report and privacy

- Generate daily report.
- Verify every item has source links.
- Test one private WeChat item and ensure it is excluded.

**Exit criterion:** shareable report contains no private text.

### Day 6 — China intake

- Create browser/manual workflow for public WeChat articles and Jike/Weibo URLs.
- Add five official organization accounts.
- Add ten Mandarin keywords and aliases.

**Exit criterion:** at least ten Chinese items analyzed end-to-end.

### Day 7 — calibration

- Mark 50 items as useful/hype/known.
- Adjust topic weights.
- Adjust Pro trigger and report length.
- Freeze prompt versions as `v1.0`.

**Exit criterion:** at least 60% of top-10 items are judged useful.

## 10. Production cadence

### Every 30 minutes

- GitHub watched repositories
- Hacker News
- manual intake directory
- public organization feeds

### Every 2 hours

- arXiv
- OpenReview
- YouTube
- public Chinese pages through permitted monitors

### Every day at 07:30 Vancouver time

- analyze backlog
- run skeptic selection
- generate Daily Radar

### Every Friday at 16:00 Vancouver time

- generate Weekly Trend Memo
- identify source/person additions
- calculate China-versus-West first-seen lead/lag

## 11. Cost controls

Default budget variables:

```env
MAX_DAILY_LLM_COST_USD=3.00
MAX_PRO_CALLS_PER_DAY=25
MAX_ITEMS_ANALYZED_PER_RUN=150
PRO_PRIORITY_THRESHOLD=68
```

The pipeline stops new LLM calls when the daily budget is reached but continues deterministic collection.

## 12. First dashboard

Do not build a polished frontend first. Use generated Markdown and the database.

After two weeks of data, build a small Streamlit or FastAPI/React interface with:

- score sliders;
- source/region/language filters;
- claim and entity search;
- China-first filter;
- contradiction filter;
- feedback buttons;
- original/translated text toggle;
- direct source links.

Building the frontend before scoring calibration is wasted work.

## 13. V1.1 backlog

- pgvector embeddings and cross-language cluster deduplication
- source-family graph
- person historical-precision scoring
- GitHub velocity time series
- citation graph enrichment
- Slack/Telegram delivery
- browser extension for one-click intake
- OCR for screenshot-only sources
- weekly change-point detection
- external fact-check query tools
