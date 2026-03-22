# Ingestion Pipeline Audit — 10-Agent Consolidated Report

> **10 Opus subagents scrutinized the ingestion pipeline before 35K case ingestion.**
> Date: 2026-03-22 | Scope: Full ingestion pipeline (PDF → PostgreSQL + Pinecone + Neo4j)

---

## Audit Dimensions

| # | Dimension | Focus | Key Findings |
|---|-----------|-------|-------------|
| 1 | Bug Hunter | Code bugs, edge cases, race conditions | 25 bugs found — text hash race, FTS crash safety, None title crash |
| 2 | Scale & Performance | 35K throughput, bottlenecks, resource limits | 4-19 hrs estimate, Neo4j connection bottleneck, contextual embeddings explosion |
| 3 | Data Quality | Metadata accuracy, field validation, LLM extraction | judicial_tone enum mismatch, V2 fields low confidence, 55-field single-pass overload |
| 4 | Resilience & Recovery | Failure modes, retry logic, dedup, idempotency | Pipeline robust (triple-layer dedup), minor GCS fallback path issue |
| 5 | Indian Legal Domain | Legal patterns, citation formats, act coverage | u/s pattern missing, Entry/List patterns, missing reporters/disposals/acts |
| 6 | Chunking & Search Quality | Chunk quality, embedding accuracy, retrieval relevance | 8-12% suboptimal queries, statute boilerplate, 30-40% lack section headers |
| 7 | Storage & Infrastructure | Pinecone/Neo4j/GCS capacity, cost projections | Must upgrade Pinecone (Free→Serverless) and Neo4j (Free→Professional) |
| 8 | Security & Integrity | SQL injection, path traversal, PII, prompt injection | No SQL injection, proper path traversal, LLM prompt injection risk on free-text |
| 9 | E2E Pipeline Trace | Full data flow, handoff points, data loss risks | 14 external API calls/case, 8 handoff points, judge array→string in Neo4j |
| 10 | Test Coverage | Unit/integration test gaps, untested paths | validate_parquet_data untested, pipeline orchestration 50% coverage |

---

## CRITICAL — Must Fix Before 35K Ingestion

### CR1. `judicial_tone` Enum Mismatch
**Agent:** #3 Data Quality
The LLM extraction prompt allows values that don't match the database enum/validation. Cases with unrecognized `judicial_tone` values will fail validation or silently store incorrect data.
**Fix:** Align the prompt's allowed values with the database enum. Add strict validation before insert.

### CR2. FTS Trigger Crash Safety
**Agent:** #1 Bug Hunter
The PostgreSQL full-text search trigger on the `cases` table can crash on edge cases (NULL values, extremely long text). If it crashes during a batch insert, the entire transaction rolls back.
**Fix:** Add COALESCE guards and text length limits in the trigger function. Test with NULL and 1MB+ text inputs.

### CR3. Text Hash Race Condition
**Agent:** #1 Bug Hunter
The dedup check (`text_hash` uniqueness) and the INSERT are not atomic. Under concurrent ingestion, two workers can both pass the dedup check and then both try to INSERT, causing a unique constraint violation that crashes the worker.
**Fix:** Use `INSERT ... ON CONFLICT (text_hash) DO NOTHING` or wrap in a serializable transaction.

### CR4. `u/s` Citation Pattern Missing
**Agent:** #5 Legal Domain
Indian judgments commonly use `u/s` (under section) notation, e.g., "u/s 302 IPC". The regex extractor doesn't recognize this pattern, missing a significant number of statute references.
**Fix:** Add `u/s\s*\d+` pattern to the section extraction regex in `extractor.py`.

### CR5. None Title Crash
**Agent:** #1 Bug Hunter
If the LLM returns `null` for the case title, downstream code that calls `.strip()` or string operations on it crashes with `AttributeError: 'NoneType' object has no attribute 'strip'`.
**Fix:** Add `title = title or "Untitled"` guard before string operations.

### CR6. Pinecone Free Tier Limit
**Agent:** #7 Infrastructure
Pinecone Free tier supports ~100K vectors. At ~30 chunks/case × 35K cases = ~1.05M vectors. **The free tier will be exhausted within ~3,300 cases.**
**Fix:** Upgrade to Pinecone Serverless (Starter) before ingestion. Cost: ~$70/mo for 1M vectors.

### CR7. Neo4j AuraDB Free Tier Limit
**Agent:** #7 Infrastructure
Neo4j Free tier has 200K nodes / 400K relationships. At ~35K case nodes + citation edges (~5-10 per case), we need ~35K nodes + ~200K+ relationships. **Cuts it close and may fail mid-ingestion.**
**Fix:** Upgrade to Neo4j Professional. Cost: ~$55/mo.

---

## HIGH — Should Fix Before Ingestion

### H1. Contextual Embeddings Explosion
**Agent:** #2 Scale
Contextual embeddings (Anthropic technique — prepend context to each chunk before embedding) can 3-5x the token count sent to the embedding API. For 35K cases × 30 chunks × 5x overhead = ~5.25M embedding calls.
**Impact:** Dramatically increases Gemini embedding API cost and time.
**Fix:** Evaluate whether contextual prefix is worth the cost at scale, or use a shorter prefix.

### H2. Neo4j Connection Bottleneck
**Agent:** #2 Scale
Neo4j operations use a single connection pool. Under concurrent ingestion with 5+ workers, the connection pool saturates, causing timeouts and retries.
**Fix:** Increase Neo4j pool size or batch Neo4j operations (collect edges, write in bulk).

### H3. 55-Field Single-Pass LLM Extraction Overload
**Agent:** #3 Data Quality
The metadata extraction prompt asks Gemini to extract 55 fields in a single pass. LLM accuracy drops significantly past ~20 fields. V2 fields (case_number, headnotes, outcome_summary, etc.) are especially at risk of low-quality extraction.
**Fix:** Split into 2-3 focused extraction passes (core metadata → citations → V2 enrichment).

### H4. Page Location Anchor Bug
**Agent:** #1 Bug Hunter
The page location tracking (which page a chunk comes from) has an off-by-one error when headers/footers are removed. Chunks may reference the wrong page number.
**Fix:** Recalculate page offsets after header/footer removal.

### H5. OCR Performance at Scale
**Agent:** #1 Bug Hunter
Per-page OCR fallback (when text extraction fails) uses synchronous processing. For scanned PDFs (common in older judgments), OCR can take 30-60 seconds per page. A 100-page scanned judgment blocks a worker for 30+ minutes.
**Fix:** Add OCR timeout per page. Consider parallel OCR pages.

### H6. GCS Fallback Path Issue
**Agent:** #4 Resilience
When GCS upload fails and the circuit breaker opens, there's no fallback to store the PDF locally. The case is marked as failed and the PDF is lost.
**Fix:** Add a local storage fallback when GCS is unavailable. Re-upload on recovery.

### H7. Missing Reporters and Acts
**Agent:** #5 Legal Domain
The citation extractor misses several common reporters: Criminal Appeal Reports (CAR), Income Tax Reports (ITR), Excise & Customs Cases (ECC). Also missing ~20 commonly referenced acts.
**Fix:** Expand the reporter list and act short-name mappings in `extractor.py`.

### H8. Judge Array→String in Neo4j Loses Structure
**Agent:** #9 E2E Trace
Judge names stored as ARRAY in PostgreSQL are converted to a comma-separated string in Neo4j. This loses the ability to query individual judges in the graph.
**Fix:** Store judges as separate nodes in Neo4j with JUDGED_BY relationships.

### H9. Act Name Duplication Between LLM and Regex
**Agent:** #9 E2E Trace
Both the LLM extraction and the regex supplementation extract act names. There's no deduplication — the same act can appear twice with slightly different names (e.g., "IPC" vs "Indian Penal Code").
**Fix:** Normalize act names to canonical forms before merging LLM and regex results.

### H10. validate_parquet_data Untested
**Agent:** #10 Test Coverage
The function that validates Parquet metadata before ingestion has zero test coverage. This is the first quality gate — if it passes garbage, everything downstream is garbage.
**Fix:** Write unit tests covering valid data, missing fields, wrong types, edge cases.

### H11. Pipeline Orchestration 50% Test Coverage
**Agent:** #10 Test Coverage
The main `pipeline.py` orchestrator has ~50% test coverage. Key untested paths: circuit breaker activation, concurrent batch failure, GCS retry exhaustion.
**Fix:** Add integration tests for failure scenarios.

### H12. Missing Entry/List Patterns
**Agent:** #5 Legal Domain
Schedule/Entry and List references (e.g., "Entry 52 List I", "Schedule VII") are not extracted. These are common in constitutional and taxation cases.
**Fix:** Add regex patterns for Entry, List, Schedule references.

---

## MEDIUM — Fix After Initial Ingestion

### Infrastructure & Performance
| ID | Finding | Agent |
|----|---------|-------|
| M1 | No progress reporting for individual PDF extraction | #9 |
| M2 | No ETA calculation during batch ingestion | #2 |
| M3 | Memory usage unbounded for large PDFs (loaded fully into memory) | #2 |
| M4 | No disk space check before starting ingestion | #7 |
| M5 | SQLite tracker is single-threaded bottleneck | #2 |
| M6 | No warm-up/dry-run mode to validate pipeline before full ingestion | #4 |

### Data Quality
| ID | Finding | Agent |
|----|---------|-------|
| M7 | 30-40% of judgments lack section headers → heading detection fails silently | #6 |
| M8 | Statute boilerplate chunks dilute search quality | #6 |
| M9 | No quality score threshold — all chunks stored regardless of quality | #3 |
| M10 | V2 fields (is_reportable, headnotes) have low extraction confidence | #3 |
| M11 | Cross-type proximity dedup may over-aggressively merge distinct paragraphs | #6 |
| M12 | No validation that extracted year matches Parquet metadata year | #3 |

### Security & Integrity
| ID | Finding | Agent |
|----|---------|-------|
| M13 | LLM prompt injection risk on free-text fields (headnotes, outcome_summary) | #8 |
| M14 | PII detection gaps — no check for Aadhaar numbers, phone numbers in text | #8 |
| M15 | No audit trail for who/when triggered ingestion | #8 |

### Citation & Legal
| ID | Finding | Agent |
|----|---------|-------|
| M16 | Missing disposal types (allowed, dismissed with costs, remanded) | #5 |
| M17 | No detection of per incuriam judgments | #5 |
| M18 | Redundant citation extraction — same citation found by both LLM and regex | #9 |

---

## Time & Cost Estimates for 35K Ingestion

### Time
| Scenario | API Keys | Concurrency | Est. Time |
|----------|----------|-------------|-----------|
| Conservative | 1 Gemini key (30 RPM) | 3 workers | ~19 hours |
| Moderate | 3 Gemini keys (90 RPM) | 5 workers | ~8 hours |
| Aggressive | 5 Gemini keys (150 RPM) | 10 workers | ~4 hours |

**Bottlenecks:** Gemini API rate limits (metadata extraction + embeddings), Neo4j writes, PDF download from S3.

### One-Time Ingestion Cost
| Service | Est. Cost |
|---------|-----------|
| Gemini API (metadata + embeddings) | $30-60 |
| S3 data transfer (35K PDFs, ~50GB) | $0 (public bucket) |
| Pinecone writes (1M vectors) | Included in plan |
| Neo4j writes | Included in plan |
| **Total** | **$30-60** |

### Monthly Steady-State Cost
| Service | Free Tier | Required Tier | Monthly Cost |
|---------|-----------|---------------|--------------|
| Pinecone | 100K vectors | Serverless | ~$70/mo |
| Neo4j AuraDB | 200K nodes | Professional | ~$55/mo |
| GCS | 5GB free | Standard | ~$5/mo |
| Redis (Upstash) | 10K cmds/day | Pay-as-you-go | ~$5/mo |
| **Total** | | | **~$135/mo** |

---

## Pre-Ingestion Checklist

### Must Do (Blockers)
- [ ] **CR1**: Fix `judicial_tone` enum mismatch
- [ ] **CR2**: Add FTS trigger safety guards
- [ ] **CR3**: Use `ON CONFLICT` for text hash dedup
- [ ] **CR4**: Add `u/s` citation pattern
- [ ] **CR5**: Guard against None title
- [ ] **CR6**: Upgrade Pinecone to Serverless
- [ ] **CR7**: Upgrade Neo4j to Professional (or verify free tier capacity)
- [ ] Delete old 112 cases from PostgreSQL + Pinecone + Neo4j
- [ ] Write and test reset script

### Should Do (Quality)
- [ ] **H1**: Evaluate contextual embedding cost vs benefit
- [ ] **H3**: Split LLM extraction into 2-3 passes
- [ ] **H4**: Fix page location anchor off-by-one
- [ ] **H7**: Expand reporter and act lists
- [ ] **H8**: Store judges as Neo4j nodes (not string)
- [ ] **H9**: Normalize act names before merge
- [ ] **H10**: Write validate_parquet_data tests

### Nice to Have
- [ ] **M6**: Add dry-run mode (ingest 10 cases, validate output)
- [ ] **M2**: Add ETA logging during batch ingestion
- [ ] **M9**: Add quality score threshold for chunks

---

## Agent-Specific Summaries

### Agent 1: Bug Hunter
Found 25 bugs total. Top 5:
1. Text hash race condition under concurrent ingestion (CR3)
2. FTS trigger crash on NULL/oversized text (CR2)
3. Page location anchor off-by-one after header removal (H4)
4. OCR performance cliff on scanned PDFs (H5)
5. None title crash on `.strip()` call (CR5)

### Agent 2: Scale & Performance
35K ingestion takes 4-19 hours depending on API key count. Key bottlenecks:
- Gemini rate limits (30 RPM/key) — primary bottleneck
- Neo4j connection pool saturation at 5+ workers
- Contextual embeddings 3-5x token overhead
- SQLite tracker is single-threaded

### Agent 3: Data Quality
LLM extraction quality concerns:
- `judicial_tone` enum mismatch between prompt and DB (CR1)
- 55-field single-pass overload → low accuracy on V2 fields (H3)
- No cross-validation between LLM-extracted year and Parquet year
- `is_reportable` and `headnotes` fields have <60% extraction confidence

### Agent 4: Resilience & Recovery
Pipeline is robust overall:
- Triple-layer dedup (SQLite tracker + text hash + citation conflict) works well
- Circuit breaker (10 failures → OPEN, 60s cooldown) is properly implemented
- Graceful shutdown with SIGINT/SIGTERM handling works
- **Gap:** No GCS fallback when upload fails (H6)

### Agent 5: Indian Legal Domain
Missing legal patterns:
- `u/s` (under section) notation not recognized (CR4)
- Entry/List/Schedule references not extracted (H12)
- Missing ~20 commonly referenced acts
- Missing reporters: CAR, ITR, ECC, and others (H7)
- Missing disposal types: allowed, dismissed with costs, remanded

### Agent 6: Chunking & Search Quality
Chunk quality issues:
- 30-40% of judgments lack section headers → heading detection fails
- Statute boilerplate chunks dilute search results
- 8-12% of generated queries are suboptimal due to chunk boundaries
- Cross-type proximity dedup may be over-aggressive

### Agent 7: Storage & Infrastructure
Infrastructure capacity analysis:
- **Pinecone**: Free tier exhausted at ~3,300 cases. Must upgrade. ($70/mo)
- **Neo4j**: Free tier at limit. Should upgrade. ($55/mo)
- **GCS**: Adequate for 35K PDFs (~50GB). ($5/mo)
- **PostgreSQL**: No issues at 35K scale
- **Total monthly**: ~$135/mo

### Agent 8: Security & Integrity
Security posture:
- No SQL injection vulnerabilities (parameterized queries throughout)
- Path traversal protection in LocalStorage (`_safe_path`)
- LLM prompt injection risk on free-text fields (headnotes, outcome_summary)
- PII gaps: no Aadhaar/phone number detection
- No audit trail for ingestion triggers

### Agent 9: E2E Pipeline Trace
Per-case pipeline flow:
- 14 external API calls per case (S3 + Gemini × 2 + Pinecone + Neo4j + ...)
- 8 critical handoff points where data loss can occur
- Judge array→string conversion in Neo4j loses structure (H8)
- Act name duplication between LLM and regex extraction (H9)
- Redundant citation extraction (same citation found twice)

### Agent 10: Test Coverage
Coverage gaps:
- `validate_parquet_data` — zero tests (H10)
- Pipeline orchestrator — ~50% coverage (H11)
- Integration tests use mocks (don't test real service interactions)
- No test for circuit breaker activation path
- No test for concurrent batch failure handling
