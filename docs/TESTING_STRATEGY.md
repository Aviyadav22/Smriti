# Smriti -- Testing Strategy

**Last updated**: March 12, 2026

---

## 1. Test Summary (Current State)

| Category | Count | Location | Runner |
|----------|------:|----------|--------|
| Backend unit tests | 1,443 | `backend/tests/unit/` | pytest |
| Backend integration tests | 31 | `backend/tests/integration/` | pytest |
| Backend search accuracy | 15 (6 pass, 9 data-dependent) | `backend/tests/quality/` | pytest |
| Frontend tests | 298 | `frontend/src/__tests__/` | vitest + React Testing Library |
| **Total** | **~1,772** | | |

Zero TypeScript errors in frontend build.

---

## 2. Testing Pyramid

```
            +----------+
            |  Manual   |   5 -- Lawyer QA, exploratory testing
            |   QA      |
           +------------+
           |    E2E      |  10 -- Full user flows (Playwright, planned)
          +--------------+
          | Integration  |  31 -- API + DB + services together
         +----------------+
         |   Unit Tests   | 1,443 backend + 298 frontend
         +----------------+
```

**Frameworks**: pytest (backend), Vitest + React Testing Library (frontend), Playwright (E2E, planned)
**Mocking**: unittest.mock + AsyncMock (backend), vi.mock + MSW (frontend)

---

## 3. Backend Unit Tests

**Location**: `backend/tests/unit/`
**Runner**: `pytest -v --cov=app`
**Target coverage**: >80% on core modules

### 3.1 Test File Inventory (90 test files)

#### Ingestion & PDF Processing
| File | Covers |
|------|--------|
| `test_pdf_extraction.py` | Standard PDF text extraction, NFKC normalization, header/footer dedup |
| `test_pdf_ocr_and_password.py` | OCR fallback for scanned PDFs, password-protected PDF handling |
| `test_pdf_quality_scoring.py` | PDF quality score computation |
| `test_chunker.py` | Legal-aware chunking (2000-char, 200-overlap, section boundaries) |
| `test_ingestion_sections.py` | Section detection (FACTS, ARGUMENTS, RATIO, ORDER, DISSENT, CONCURRENCE) |
| `test_ingestion_pipeline.py` | Full pipeline unit tests: PDF to chunks to embeddings |
| `test_concurrent_ingestion.py` | Concurrent ingestion safety |
| `test_ingestion_rate_limiter.py` | Ingestion-level rate limiting |
| `test_circuit_breaker.py` | Circuit breaker (10 failures threshold) |
| `test_graceful_shutdown.py` | Graceful shutdown handling |
| `test_vector_chunk_text.py` | Chunk text stored in vectors |
| `test_pipeline_citation_equivalents.py` | Citation equivalent pipeline integration |
| `test_pipeline_treatment.py` | Treatment classification in pipeline |

#### Metadata & Legal Extraction
| File | Covers |
|------|--------|
| `test_metadata.py` | Regex-based metadata extraction (SCC, AIR, INSC, CNR citations) |
| `test_metadata_llm_retry.py` | LLM metadata extraction with Tenacity retry |
| `test_extractor.py` | Legal entity extraction (neutral citations, reporters, acts, sections) |
| `test_courts.py` | Court name normalization |
| `test_citation_equivalence.py` | Citation equivalence detection |
| `test_citation_equivalent_model.py` | Citation equivalent ORM model |
| `test_devanagari_preservation.py` | Devanagari script preservation in processing |
| `test_statute_expansion.py` | Short act name expansion (42 mappings) |

#### Search
| File | Covers |
|------|--------|
| `test_hybrid_search.py` | Hybrid search pipeline (vector + FTS + rerank) |
| `test_fulltext.py` | Full-text search with tsvector, websearch_to_tsquery |
| `test_rrf.py` | Reciprocal Rank Fusion (k=60) |
| `test_weighted_rrf.py` | Weighted RRF variants |
| `test_query_understanding.py` | Query intent classification, filter extraction from NL |
| `test_search_routes.py` | Search API endpoint tests |
| `test_section_search.py` | Section-scoped search |
| `test_hindi_search.py` | Hindi query handling |
| `test_multi_court_filter.py` | Multi-court filter support |

#### Security & Auth
| File | Covers |
|------|--------|
| `test_auth.py` | JWT create/verify, password hashing (bcrypt), token expiry |
| `test_auth_routes.py` | Register/login/refresh/logout API flows |
| `test_rbac.py` | Role-based access control (user, admin, super_admin) |
| `test_rate_limiter.py` | Rate limiting (Redis-backed + in-memory fallback) |
| `test_sanitizer.py` | Input sanitization, prompt injection detection |
| `test_encryption.py` | AES-256-GCM field-level encryption |
| `test_audit_logging.py` | Audit log creation, IP hashing |
| `test_dpdp_routes.py` | DPDP Act compliance endpoints (data summary, erasure, consent) |
| `test_config_validation.py` | Production config validation (secret lengths, CORS) |

#### Chat & RAG
| File | Covers |
|------|--------|
| `test_chat_routes.py` | Chat session management, message sending |
| `test_rag.py` | RAG pipeline (retrieval + generation) |
| `test_rag_context.py` | Context assembly for RAG |
| `test_checkpointer.py` | LangGraph MemorySaver checkpointing |

#### Agents (LangGraph)
| File | Covers |
|------|--------|
| `test_research_agent.py` | Research agent graph execution |
| `test_research_nodes.py` | Research agent individual nodes |
| `test_case_prep_agent.py` | Case prep agent |
| `test_case_prep_nodes.py` | Case prep agent nodes |
| `test_strategy_graph.py` | Strategy agent graph |
| `test_strategy_nodes.py` | Strategy agent nodes |
| `test_drafting_graph.py` | Drafting agent graph |
| `test_drafting_nodes.py` | Drafting agent nodes |
| `test_drafting_templates.py` | Legal document templates |
| `test_agent_execution_model.py` | Agent execution ORM model |
| `test_agent_graph_execution.py` | Agent graph execution tracking |
| `test_agent_nodes_common.py` | Shared agent node utilities |
| `test_agent_prompts.py` | Agent prompt templates (IRAC enforcement) |
| `test_agent_routes.py` | Agent API routes |
| `test_agent_state.py` | Agent state management |
| `test_common_nodes.py` | Common node implementations |
| `test_routing_utils.py` | Agent routing utilities |
| `test_citation_verifier.py` | Semantic citation verification |
| `test_confidence_scoring.py` | Agent confidence scoring |

#### Graph, Analytics & Providers
| File | Covers |
|------|--------|
| `test_graph_routes.py` | Citation graph API routes |
| `test_graph_traversal.py` | Neo4j graph traversal |
| `test_neo4j_store.py` | Neo4j provider (MERGE-based, idempotent) |
| `test_judge_analytics.py` | Judge analytics computations |
| `test_judge_routes.py` | Judge API routes |
| `test_document_analyzer.py` | Document analysis |
| `test_precedent_mapper.py` | Precedent relationship mapping |
| `test_precedent_strength.py` | Precedent strength classification |
| `test_treatment.py` | Case treatment classification |
| `test_treatment_citation_association.py` | Treatment-citation linking |
| `test_provider_contracts.py` | Protocol contract compliance tests |
| `test_tts_provider.py` | TTS provider (Sarvam AI) |
| `test_gcs_storage.py` | GCS storage provider |

#### Models, Routes & Infrastructure
| File | Covers |
|------|--------|
| `test_case_routes.py` | Case detail API (UUID validation) |
| `test_case_section_model.py` | Case section ORM model |
| `test_phase5_models.py` | Phase 5 data models |
| `test_phase5_prompts.py` | Phase 5 LLM prompts |
| `test_document_routes.py` | Document upload/management routes |
| `test_document_tasks.py` | Celery document processing tasks |
| `test_audio_routes.py` | Audio digest API routes |
| `test_audio_tasks.py` | Audio generation Celery tasks |
| `test_admin_routes.py` | Admin dashboard routes |
| `test_health_extended.py` | Extended health check endpoint |
| `test_logging_config.py` | Structured JSON logging, PII redaction |
| `test_celery_config.py` | Celery worker configuration |
| `test_translation.py` | Hindi translation support |
| `test_migration_011.py` | Database migration correctness |

### 3.2 Example Test Patterns

```python
# Chunking: section boundaries, overlap, size limits
def test_chunks_respect_sections():
    text = load_fixture("judgment_with_sections.txt")
    chunks = chunk_judgment(text)
    for chunk in chunks:
        assert chunk.section_type in ["HEADER", "FACTS", "ARGUMENTS", "ANALYSIS", "RATIO", "ORDER"]
        assert len(chunk.text) <= 2200  # 2000 + tolerance

# Security: JWT create and verify round-trip
def test_jwt_create_and_verify():
    token = create_access_token(user_id="user1", role="researcher")
    payload = verify_access_token(token)
    assert payload["sub"] == "user1"
    assert payload["role"] == "researcher"

# Search: RRF merge correctness
def test_rrf_merge():
    vector_results = [("case1", 1), ("case2", 2)]
    fts_results = [("case2", 1), ("case3", 2)]
    merged = reciprocal_rank_fusion([vector_results, fts_results], k=60)
    assert merged[0].case_id == "case2"  # Best combined rank
```

---

## 4. Frontend Tests

**Location**: `frontend/src/__tests__/`
**Runner**: `npx vitest` (or `npm test`)
**Count**: 298 tests across 30 test files

### 4.1 Test File Inventory

| File | Covers |
|------|--------|
| `home-page.test.tsx` | Landing page rendering |
| `search-page.test.tsx` | Search UI, query submission, results display |
| `search-integration.test.tsx` | Search + API client integration |
| `case-detail-page.test.tsx` | Case detail view with metadata |
| `chat-page.test.tsx` | Chat interface, message rendering (react-markdown) |
| `graph-page.test.tsx` | Citation graph visualization |
| `upload-page.test.tsx` | Document upload flow |
| `login-page.test.tsx` | Login form, validation |
| `register-page.test.tsx` | Registration form, consent checkbox |
| `agents-hub.test.tsx` | Agents hub page |
| `research-workspace.test.tsx` | Research agent workspace |
| `case-prep-workspace.test.tsx` | Case prep agent workspace |
| `strategy-agent-workspace.test.tsx` | Strategy agent workspace |
| `drafting-agent-workspace.test.tsx` | Drafting agent workspace |
| `agent-components.test.tsx` | Shared agent UI components |
| `agent-history-page.test.tsx` | Agent execution history |
| `document-detail-page.test.tsx` | Document detail view |
| `judges-page.test.tsx` | Judge listing page |
| `judge-profile-page.test.tsx` | Individual judge profile |
| `judge-compare-page.test.tsx` | Judge comparison view |
| `courts-page.test.tsx` | Courts listing page |
| `header.test.tsx` | Header navigation component |
| `footer.test.tsx` | Footer component |
| `audio-player.test.tsx` | Audio player component |
| `error-boundary.test.tsx` | Error boundary component |
| `api-client.test.ts` | API client (fetch wrapper, error handling) |
| `legal-components.test.tsx` | Legal disclaimer, citation display |
| `precedent-badge.test.tsx` | Precedent strength badge |
| `quality-components.test.tsx` | Quality indicator components |
| `i18n-integration.test.tsx` | Hindi internationalization |

### 4.2 Testing Approach

- **Server Components**: Tested via async rendering with React Testing Library
- **Client Components**: Standard RTL with `render()` + user event simulation
- **API Mocking**: `vi.mock` for the API client module, MSW for HTTP-level mocking
- **Routing**: Next.js App Router mocked via `next/navigation` stubs

---

## 5. Integration Tests

**Location**: `backend/tests/integration/`
**Count**: 31 tests across 3 files
**Requires**: Running PostgreSQL, Redis, Pinecone (test index), Neo4j

| File | Tests | Covers |
|------|------:|--------|
| `test_search.py` | ~12 | Search pipeline end-to-end, faceted search |
| `test_search_accuracy.py` | ~12 | Search result relevance, filter correctness |
| `test_ingestion.py` | ~7 | Full ingestion pipeline: PDF to all stores |

### 5.1 Key Integration Scenarios

- **Ingestion pipeline**: PDF upload to text extraction to metadata to chunks to embeddings to Pinecone + PostgreSQL + Neo4j
- **Search pipeline**: Query to query understanding to vector search + FTS to RRF merge to reranking to response
- **Faceted search**: Verify filter accuracy (court, year, case_type, judge, act)
- **Case detail**: Retrieve full case with metadata, sections, and citation graph
- **Auth flow**: Register to login to access protected route to refresh token to logout

---

## 6. Search Accuracy Evaluation

**Location**: `backend/tests/quality/`
**Status**: 15 tests total -- 6 pass with current data, 9 are data-dependent (need 50K+ ingested cases)

### 6.1 Test Query Set (30 Queries)

**Category 1: Citation Lookup (10 queries)**
| # | Query | Expected Top Result | Metric |
|---|-------|--------------------:|--------|
| 1 | "Kesavananda Bharati v State of Kerala" | Kesavananda Bharati v. State of Kerala (1973) | Exact match in top 1 |
| 2 | "Maneka Gandhi passport case" | Maneka Gandhi v. Union of India (1978) | Exact match in top 1 |
| 3 | "2017 10 SCC 1" | K.S. Puttaswamy v. Union of India (2017) | Exact match in top 1 |
| 4 | "Vishaka guidelines case" | Vishaka v. State of Rajasthan (1997) | Exact match in top 1 |
| 5 | "Navtej Johar section 377" | Navtej Singh Johar v. Union of India (2018) | Exact match in top 1 |
| 6 | "ADM Jabalpur habeas corpus" | ADM Jabalpur v. Shivkant Shukla (1976) | Exact match in top 3 |
| 7 | "Shreya Singhal section 66A" | Shreya Singhal v. Union of India (2015) | Exact match in top 1 |
| 8 | "MC Mehta Taj Mahal pollution" | M.C. Mehta v. Union of India | Exact match in top 3 |
| 9 | "Shah Bano maintenance case" | Mohd. Ahmed Khan v. Shah Bano Begum (1985) | Exact match in top 3 |
| 10 | "AIR 1973 SC 1461" | Kesavananda Bharati | Exact match in top 1 |

**Target**: >90% recall@5 (9/10 found in top 5)

**Category 2: Topic Search (10 queries)**
| # | Query | Expected Results Should Contain | Metric |
|---|-------|--------------------------------:|--------|
| 11 | "right to privacy as fundamental right" | Puttaswamy (2017), Gobind v. State of M.P. | Relevant cases in top 5 |
| 12 | "dowry death section 304B" | Cases discussing Section 304B IPC | Relevant in top 5 |
| 13 | "environmental protection public interest" | MC Mehta cases, Vellore Citizens | Relevant in top 5 |
| 14 | "bail conditions anticipatory" | Sushila Aggarwal (2020), Gurbaksh Singh | Relevant in top 5 |
| 15 | "land acquisition compensation" | Cases on Right to Fair Compensation Act | Relevant in top 5 |
| 16 | "freedom of speech reasonable restrictions" | Shreya Singhal, S. Rangarajan | Relevant in top 5 |
| 17 | "arbitration clause validity" | Cases on Arbitration Act, Section 7/11 | Relevant in top 5 |
| 18 | "specific performance contract" | Cases on Specific Relief Act | Relevant in top 5 |
| 19 | "death penalty rarest of rare" | Bachan Singh v. State of Punjab (1980), Machhi Singh | Relevant in top 5 |
| 20 | "divorce cruelty mental harassment" | Cases on Section 13 Hindu Marriage Act | Relevant in top 5 |

**Target**: >70% recall@5 (7/10 have relevant results in top 5)

**Category 3: Filtered Search (5 queries)**
| # | Query | Filters | Expected |
|---|-------|---------|----------|
| 21 | "criminal appeal" | court=SC, year=2023 | Only 2023 SC criminal appeals |
| 22 | "writ petition Article 32" | case_type=Writ Petition | Only writ petitions |
| 23 | "Justice Chandrachud" | judge=D.Y. Chandrachud | Only cases by this judge |
| 24 | "tax evasion penalty" | year_from=2020, year_to=2024 | Only 2020-2024 cases |
| 25 | "constitutional bench" | bench_type=constitutional | Only 5+ judge benches |

**Target**: 100% filter accuracy (all results match filters)

**Category 4: Complex/Natural Language (5 queries)**
| # | Query | Expected Behavior |
|---|-------|-------------------|
| 26 | "can a wife claim maintenance after divorce under Muslim law?" | Shah Bano, Danial Latifi cases |
| 27 | "what is the law on sedition in India after 2022?" | S.G. Vombatkere v. Union of India, cases on Section 124A |
| 28 | "recent Supreme Court judgments on transgender rights" | NALSA v. Union of India, recent cases |
| 29 | "difference between murder and culpable homicide" | Cases distinguishing Sections 299/300 IPC |
| 30 | "is euthanasia legal in India?" | Common Cause v. Union of India (2018) |

**Target**: >60% have meaningfully relevant results in top 5

---

## 7. AI Output Evaluation

### 7.1 Metadata Extraction Accuracy

**Method**: Manually label metadata for 50 judgments. Compare LLM extraction against labels.

| Field | Metric | Target |
|-------|--------|--------|
| title | Exact match | >95% |
| citation | Exact match (normalized) | >90% |
| court | Exact match | >98% |
| year | Exact match | >99% |
| decision_date | Exact match | >95% |
| judge | Set overlap (F1) | >90% |
| case_type | Exact match | >85% |
| bench_type | Exact match | >90% |
| acts_cited | Set overlap (F1) | >80% |
| cases_cited | Set overlap (F1) | >75% |
| ratio_decidendi | Human rating (1-5) | >3.5 avg |
| keywords | Set overlap (F1) | >70% |
| case_number | Exact match | >90% |
| is_reportable | Exact match | >95% |
| headnotes | Human rating (1-5) | >3.5 avg |
| outcome_summary | Human rating (1-5) | >3.5 avg |

### 7.2 RAG Chat Groundedness

**Method**: For each response, check if every factual claim is supported by retrieved context.

| Metric | Definition | Target |
|--------|-----------|--------|
| Groundedness | % of claims backed by retrieved context | >90% |
| Citation accuracy | % of cited cases that actually exist | 100% |
| Completeness | Does the response address the question? (1-5) | >3.5 avg |
| Hallucination rate | % of responses with fabricated cases/citations | <5% |

### 7.3 Section Detection Accuracy

**Method**: Manually annotate sections in 20 judgments. Compare with detected sections.

| Metric | Target |
|--------|--------|
| Section type accuracy | >85% |
| Boundary accuracy (within 200 chars) | >80% |
| False positive rate (detecting non-existent sections) | <10% |

---

## 8. Performance Tests

### 8.1 API Response Times

| Endpoint | p50 Target | p95 Target | p99 Target |
|----------|-----------|-----------|-----------|
| `GET /health` | <50ms | <100ms | <200ms |
| `GET /search` | <1s | <2s | <3s |
| `GET /cases/{id}` | <200ms | <500ms | <1s |
| `POST /chat/message` (first token) | <2s | <3s | <5s |
| `GET /graph/neighborhood` | <500ms | <1s | <2s |
| `POST /ingest/upload` (async start) | <500ms | <1s | <2s |
| `GET /agents/*/execute` (SSE first event) | <2s | <3s | <5s |

### 8.2 Load Testing

```bash
# Using locust (backend/tests/load/locustfile.py)
# Simulate 50 concurrent users for 5 minutes
# Mix: 60% search, 20% case view, 10% chat, 10% other
```

**Targets under 50 concurrent users**:
- Error rate: <1%
- Search p95: <3s
- No OOM crashes
- Database connections stay within pool limits

---

## 9. Security Tests

See `SECURITY_AUDIT.md` for the full OWASP Top 10 audit with implementation references.

### 9.1 Unit-Tested Security Controls

| Control | Test File | Key Assertions |
|---------|-----------|----------------|
| JWT auth | `test_auth.py` | Token create/verify, expiry, invalid signature, revocation |
| Password hashing | `test_auth.py` | bcrypt hash/verify round-trip |
| RBAC | `test_rbac.py` | Role enforcement (user, admin, super_admin), privilege escalation blocked |
| Rate limiting | `test_rate_limiter.py` | Redis-backed + in-memory fallback, 429 after threshold |
| Input sanitization | `test_sanitizer.py` | HTML stripping, null byte removal, prompt injection detection |
| AES-256-GCM encryption | `test_encryption.py` | Encrypt/decrypt round-trip, tamper detection |
| Audit logging | `test_audit_logging.py` | Log creation, IP hashing with SHA-256 |
| DPDP compliance | `test_dpdp_routes.py` | Data summary, erasure, consent withdrawal |
| Config validation | `test_config_validation.py` | Secret length enforcement, CORS wildcard rejection |

---

## 10. Test Fixtures

### Required Test Data

```
backend/tests/fixtures/
|-- pdfs/
|   |-- standard_judgment.pdf          # Digitally-created SC judgment
|   |-- scanned_judgment.pdf           # Scanned/OCR judgment
|   |-- long_judgment.pdf              # 100+ page judgment
|   |-- short_order.pdf                # 1-2 page order
|   +-- corrupt.pdf                    # Invalid PDF file
|-- texts/
|   |-- judgment_with_sections.txt     # Full judgment with clear sections
|   |-- judgment_no_sections.txt       # Unstructured judgment
|   +-- judgment_multiple_citations.txt # Many case citations
|-- metadata/
|   |-- sample_parquet_row.json        # One row from Parquet metadata
|   +-- sample_llm_output.json        # Expected LLM extraction output
+-- search/
    |-- test_queries.json              # 30 evaluation queries with expected results
    +-- sample_vectors.json            # Pre-computed embeddings for test
```

---

## 11. CI/CD Pipeline (Planned)

```yaml
# .github/workflows/test.yml
steps:
  - Backend lint: ruff check + ruff format --check
  - Backend unit tests: pytest tests/unit/ -v --cov=app
  - Frontend lint: eslint + tsc --noEmit
  - Frontend tests: npm test
  - Security scan: pip-audit + npm audit
  # Integration tests run manually or on merge to main
  # Search accuracy tests require live services + 50K+ cases
```

---

## 12. Test Execution Commands

```bash
# All backend tests
cd backend && pytest -v

# Unit tests only
cd backend && pytest tests/unit/ -v

# Integration tests (requires running services)
cd backend && pytest tests/integration/ -v

# Search accuracy benchmarks (requires live services + data)
cd backend && pytest tests/quality/ -v

# With coverage report
cd backend && pytest --cov=app --cov-report=html

# Frontend tests
cd frontend && npm test

# Frontend tests with coverage
cd frontend && npm test -- --coverage

# E2E tests (requires running backend + frontend, planned)
cd frontend && npm run test:e2e

# Load tests
cd backend && locust -f tests/load/locustfile.py
```
