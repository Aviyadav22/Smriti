# Smriti — Testing Strategy

---

## 1. Testing Pyramid

```
            ┌─────────┐
            │  Manual  │   5 — Lawyer QA, exploratory testing
            │   QA     │
           ┌┴─────────┴┐
           │   E2E      │  10 — Full user flows (Playwright)
          ┌┴───────────┴┐
          │ Integration  │  30 — API + DB + services together
         ┌┴─────────────┴┐
         │   Unit Tests   │ 100+ — Functions, modules, components
         └────────────────┘
```

**Framework**: pytest (backend), Vitest + React Testing Library (frontend), Playwright (E2E)

---

## 2. Unit Tests

### 2.1 Backend Unit Tests

**Location**: `backend/tests/unit/`
**Runner**: `pytest -v --cov=app`
**Target coverage**: >80% on core modules

#### PDF Extraction (`tests/unit/test_pdf.py`)

```python
# Test cases:
# 1. Extract text from a standard SC judgment PDF
# 2. Handle scanned PDF (triggers OCR fallback)
# 3. Handle empty/corrupt PDF (returns error, not crash)
# 4. Handle password-protected PDF (returns error)
# 5. Extract from multi-page PDF (50+ pages)
# 6. Handle mixed text + image pages

def test_extract_text_standard_pdf():
    """Standard digitally-created PDF should return clean text."""
    text = extract_pdf_text("fixtures/standard_judgment.pdf")
    assert len(text) > 1000
    assert "SUPREME COURT" in text

def test_extract_text_scanned_pdf():
    """Scanned PDF should trigger OCR fallback."""
    text = extract_pdf_text("fixtures/scanned_judgment.pdf")
    assert len(text) > 100  # OCR may not be perfect

def test_extract_text_corrupt_pdf():
    """Corrupt PDF should raise DocumentParseError."""
    with pytest.raises(DocumentParseError):
        extract_pdf_text("fixtures/corrupt.pdf")
```

#### Legal-Aware Chunker (`tests/unit/test_chunker.py`)

```python
# Test cases:
# 1. Detect standard judgment sections (FACTS, ARGUMENTS, RATIO, ORDER)
# 2. Chunk within sections (no cross-section chunks)
# 3. Chunk size ~2000 chars with 200 overlap
# 4. Short judgment (<500 chars) returns single chunk
# 5. Each chunk has correct section_type tag
# 6. Chunk index is sequential within section

def test_section_detection():
    text = load_fixture("judgment_with_sections.txt")
    sections = detect_judgment_sections(text)
    section_types = [s.type for s in sections]
    assert "FACTS" in section_types
    assert "ORDER" in section_types

def test_chunks_respect_sections():
    text = load_fixture("judgment_with_sections.txt")
    chunks = chunk_judgment(text)
    for chunk in chunks:
        assert chunk.section_type in ["HEADER", "FACTS", "ARGUMENTS", "ANALYSIS", "RATIO", "ORDER"]
        assert len(chunk.text) <= 2200  # 2000 + tolerance

def test_chunk_overlap():
    text = "A" * 5000  # Long text
    chunks = chunk_judgment(text)
    for i in range(1, len(chunks)):
        overlap = chunks[i-1].text[-200:]
        assert chunks[i].text.startswith(overlap[:100])  # At least partial overlap
```

#### Metadata Extraction (`tests/unit/test_metadata.py`)

```python
# Test cases:
# 1. Regex: Extract SCC citation from text
# 2. Regex: Extract AIR citation from text
# 3. Regex: Extract INSC citation from text
# 4. Regex: Extract CNR number
# 5. Regex: Parse judge names from header
# 6. Regex: Detect bench type from judge count
# 7. Validate LLM output: reject future dates
# 8. Validate LLM output: reject non-existent courts
# 9. Merge: Parquet metadata wins for title, court, year
# 10. Merge: LLM metadata wins for ratio, acts_cited, keywords

def test_extract_scc_citation():
    assert extract_citation("(2024) 5 SCC 123") == {"reporter": "SCC", "year": 2024, "volume": "5", "page": "123"}

def test_extract_air_citation():
    assert extract_citation("AIR 2024 SC 789") == {"reporter": "AIR", "year": 2024, "court": "SC", "page": "789"}

def test_reject_future_date():
    metadata = {"decision_date": "2030-01-01"}
    validated = validate_with_regex(metadata)
    assert validated["decision_date"] is None  # Rejected

def test_merge_parquet_wins_for_title():
    parquet = {"title": "A v. B"}
    llm = {"title": "A versus B"}
    merged = merge_metadata(parquet, llm)
    assert merged["title"] == "A v. B"  # Parquet wins
```

#### Search (`tests/unit/test_search.py`)

```python
# Test cases:
# 1. RRF: Merge two ranked lists correctly
# 2. RRF: Handle empty list from one source
# 3. RRF: Deduplicate by case_id
# 4. Query understanding: citation lookup intent
# 5. Query understanding: topic search intent
# 6. Query understanding: extract year filter from NL query

def test_rrf_merge():
    vector_results = [("case1", 1), ("case2", 2), ("case3", 3)]
    fts_results = [("case2", 1), ("case1", 2), ("case4", 3)]
    merged = reciprocal_rank_fusion([vector_results, fts_results], k=60)
    # case2 ranked 2+1 should score higher than case1 ranked 1+2 (same) or case3/case4
    assert merged[0].case_id in ["case1", "case2"]

def test_rrf_empty_source():
    vector_results = [("case1", 1)]
    fts_results = []
    merged = reciprocal_rank_fusion([vector_results, fts_results], k=60)
    assert len(merged) == 1
    assert merged[0].case_id == "case1"
```

#### Security (`tests/unit/test_security.py`)

```python
# Test cases:
# 1. JWT: Create token with correct claims
# 2. JWT: Expired token raises error
# 3. JWT: Invalid signature raises error
# 4. JWT: Refresh token rotation (old token invalidated)
# 5. bcrypt: Hash and verify password
# 6. RBAC: Admin can access admin routes
# 7. RBAC: Viewer cannot access admin routes
# 8. Sanitizer: Strip HTML tags
# 9. Sanitizer: Escape SQL injection attempts
# 10. Rate limiter: Block after threshold
# 11. Encryption: Encrypt and decrypt PII field
# 12. Audit: Log entry created for API call

def test_jwt_create_and_verify():
    token = create_access_token(user_id="user1", role="researcher")
    payload = verify_access_token(token)
    assert payload["sub"] == "user1"
    assert payload["role"] == "researcher"

def test_jwt_expired():
    token = create_access_token(user_id="user1", role="researcher", expires_delta=timedelta(seconds=-1))
    with pytest.raises(TokenExpiredError):
        verify_access_token(token)

def test_sanitize_html():
    assert sanitize_input("<script>alert('xss')</script>") == "alert('xss')"

def test_encrypt_decrypt_pii():
    plaintext = "user@example.com"
    encrypted = encrypt_field(plaintext)
    assert encrypted != plaintext
    assert decrypt_field(encrypted) == plaintext
```

### 2.2 Frontend Unit Tests

**Location**: `frontend/__tests__/`
**Runner**: `pnpm test`

```typescript
// Test cases:
// 1. SearchBar: renders, accepts input, calls onSearch
// 2. ResultCard: displays title, citation, court, snippet
// 3. FilterSidebar: renders filters, calls onChange
// 4. CaseViewer: renders metadata, sections tabs
// 5. ChatMessage: renders user vs assistant messages differently
// 6. API client: correctly constructs search request URL

describe("SearchBar", () => {
  it("calls onSearch with query when submitted", () => {
    const onSearch = vi.fn();
    render(<SearchBar onSearch={onSearch} />);
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "right to privacy" } });
    fireEvent.submit(screen.getByRole("form"));
    expect(onSearch).toHaveBeenCalledWith("right to privacy");
  });
});

describe("ResultCard", () => {
  it("displays case title and citation", () => {
    render(<ResultCard case={{ title: "A v. B", citation: "(2024) 5 SCC 123", court: "Supreme Court" }} />);
    expect(screen.getByText("A v. B")).toBeInTheDocument();
    expect(screen.getByText("(2024) 5 SCC 123")).toBeInTheDocument();
  });
});
```

---

## 3. Integration Tests

**Location**: `backend/tests/integration/`
**Requires**: Running PostgreSQL, Redis, Pinecone (test index), Neo4j

### 3.1 Ingestion Pipeline

```python
# Full pipeline: PDF → text → metadata → chunks → embeddings → stores
async def test_full_ingestion_pipeline():
    """Ingest a real SC judgment PDF and verify all stores."""
    case_id = await ingest_judgment("fixtures/real_sc_judgment.pdf", sample_parquet_metadata)

    # Verify PostgreSQL
    case = await get_case(case_id)
    assert case.title is not None
    assert case.court == "Supreme Court of India"
    assert len(case.searchable_text) > 0

    # Verify Pinecone
    results = await vector_store.search(
        query_vector=await embedder.embed_text(case.title),
        top_k=1,
        filters={"case_id": case_id}
    )
    assert len(results) >= 1

    # Verify Neo4j
    node = await graph_store.get_node(case_id)
    assert node is not None
```

### 3.2 Search Pipeline

```python
async def test_search_end_to_end():
    """Search for an ingested case by topic and verify results."""
    # Pre-condition: at least 100 cases ingested
    results = await hybrid_search("right to privacy fundamental right Article 21")
    assert len(results) > 0
    # K.S. Puttaswamy should be in top 5 (if ingested)
    titles = [r.title for r in results[:5]]
    # At minimum, results should be relevant to privacy/Article 21
    assert any("privacy" in r.snippet.lower() or "article 21" in r.snippet.lower() for r in results[:5])
```

### 3.3 Auth Flow

```python
async def test_auth_register_login_refresh():
    """Full auth flow: register → login → access protected route → refresh."""
    # Register
    resp = await client.post("/auth/register", json={
        "email": "test@example.com", "password": "SecureP@ss123", "name": "Test User",
        "consent_given": True, "consent_version": "1.0"
    })
    assert resp.status_code == 201

    # Login
    resp = await client.post("/auth/login", json={"email": "test@example.com", "password": "SecureP@ss123"})
    assert resp.status_code == 200
    tokens = resp.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    # Access protected route
    resp = await client.get("/cases/some-id", headers={"Authorization": f"Bearer {access_token}"})
    assert resp.status_code in [200, 404]  # Auth passed

    # Refresh token
    resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    new_tokens = resp.json()
    assert new_tokens["access_token"] != access_token  # New token issued
```

---

## 4. Search Accuracy Evaluation

### 4.1 Test Query Set (30 Queries)

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

### 4.2 Evaluation Script

```python
# scripts/evaluate_search.py
# Runs all 30 queries, scores results, generates report

async def evaluate():
    results = []
    for query in TEST_QUERIES:
        search_results = await hybrid_search(query.text, filters=query.filters)
        score = evaluate_results(search_results, query.expected)
        results.append({"query": query.text, "score": score, "top_5": search_results[:5]})

    # Generate report
    citation_recall = mean([r["score"] for r in results[:10]])
    topic_recall = mean([r["score"] for r in results[10:20]])
    filter_accuracy = mean([r["score"] for r in results[20:25]])
    complex_relevance = mean([r["score"] for r in results[25:30]])

    print(f"Citation Recall@5: {citation_recall:.0%} (target: >90%)")
    print(f"Topic Recall@5: {topic_recall:.0%} (target: >70%)")
    print(f"Filter Accuracy: {filter_accuracy:.0%} (target: 100%)")
    print(f"Complex Relevance@5: {complex_relevance:.0%} (target: >60%)")
```

---

## 5. AI Output Evaluation

### 5.1 Metadata Extraction Accuracy

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

### 5.2 RAG Chat Groundedness

**Method**: For each response, check if every factual claim is supported by retrieved context.

| Metric | Definition | Target |
|--------|-----------|--------|
| Groundedness | % of claims backed by retrieved context | >90% |
| Citation accuracy | % of cited cases that actually exist | 100% |
| Completeness | Does the response address the question? (1-5) | >3.5 avg |
| Hallucination rate | % of responses with fabricated cases/citations | <5% |

### 5.3 Section Detection Accuracy

**Method**: Manually annotate sections in 20 judgments. Compare with detected sections.

| Metric | Target |
|--------|--------|
| Section type accuracy | >85% |
| Boundary accuracy (within 200 chars) | >80% |
| False positive rate (detecting non-existent sections) | <10% |

---

## 6. Performance Tests

### 6.1 API Response Times

| Endpoint | p50 Target | p95 Target | p99 Target |
|----------|-----------|-----------|-----------|
| `GET /health` | <50ms | <100ms | <200ms |
| `GET /search` | <1s | <2s | <3s |
| `GET /cases/{id}` | <200ms | <500ms | <1s |
| `POST /chat/message` (first token) | <2s | <3s | <5s |
| `GET /graph/neighborhood` | <500ms | <1s | <2s |
| `POST /ingest/upload` (async start) | <500ms | <1s | <2s |

### 6.2 Load Testing

```bash
# Using k6 or locust
# Simulate 50 concurrent users for 5 minutes
# Mix: 60% search, 20% case view, 10% chat, 10% other
```

**Targets under 50 concurrent users**:
- Error rate: <1%
- Search p95: <3s
- No OOM crashes
- Database connections stay within pool limits

---

## 7. Security Tests

### 7.1 OWASP Top 10 Checklist

| # | Risk | Test | Status |
|---|------|------|--------|
| A01 | Broken Access Control | Verify RBAC on all endpoints, test privilege escalation | Pending |
| A02 | Cryptographic Failures | Verify TLS, JWT signing, password hashing, PII encryption | Pending |
| A03 | Injection | Test SQL injection on search params, XSS on user inputs | Pending |
| A04 | Insecure Design | Review auth flow, consent flow, data isolation | Pending |
| A05 | Security Misconfiguration | Check CORS, CSP headers, debug mode off in prod | Pending |
| A06 | Vulnerable Components | Run `pip audit`, `pnpm audit` | Pending |
| A07 | Auth Failures | Test brute force protection, token expiry, session management | Pending |
| A08 | Data Integrity Failures | Verify signed JWTs, input validation on all endpoints | Pending |
| A09 | Logging Failures | Verify audit log captures all access, PII redacted | Pending |
| A10 | SSRF | Verify no user-controllable URLs fetched server-side | Pending |

### 7.2 Specific Security Tests

```python
# tests/security/

def test_sql_injection_search():
    """Search param should not allow SQL injection."""
    resp = client.get("/search?q='; DROP TABLE cases; --")
    assert resp.status_code == 200  # Query treated as text, no crash

def test_xss_in_chat():
    """Chat input with script tags should be sanitized."""
    resp = client.post("/chat/session1/message", json={"content": "<script>alert('xss')</script>"})
    assert "<script>" not in resp.json()["response"]

def test_rate_limiting():
    """Exceed rate limit and verify 429 response."""
    for _ in range(101):
        resp = client.get("/search?q=test")
    assert resp.status_code == 429

def test_jwt_tampering():
    """Modified JWT should be rejected."""
    token = create_access_token(user_id="user1")
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
    resp = client.get("/cases/1", headers={"Authorization": f"Bearer {tampered}"})
    assert resp.status_code == 401

def test_user_data_isolation():
    """User A cannot access User B's chat history."""
    # Login as user A, create chat
    # Login as user B, try to access user A's chat
    resp = client.get(f"/chat/{user_a_session}/history", headers=user_b_headers)
    assert resp.status_code == 403
```

---

## 8. Test Fixtures

### Required Test Data

```
backend/tests/fixtures/
├── pdfs/
│   ├── standard_judgment.pdf          # Digitally-created SC judgment
│   ├── scanned_judgment.pdf           # Scanned/OCR judgment
│   ├── long_judgment.pdf              # 100+ page judgment
│   ├── short_order.pdf                # 1-2 page order
│   └── corrupt.pdf                    # Invalid PDF file
├── texts/
│   ├── judgment_with_sections.txt     # Full judgment with clear sections
│   ├── judgment_no_sections.txt       # Unstructured judgment
│   └── judgment_multiple_citations.txt # Many case citations
├── metadata/
│   ├── sample_parquet_row.json        # One row from Parquet metadata
│   └── sample_llm_output.json        # Expected LLM extraction output
└── search/
    ├── test_queries.json              # 30 evaluation queries with expected results
    └── sample_vectors.json            # Pre-computed embeddings for test
```

### How to Create Fixtures

1. Download 5 real SC judgment PDFs from S3 (2023-2024, varied types)
2. Manually extract and verify metadata for each
3. Manually annotate sections for 3 of them
4. Store as fixtures (committed to repo, ~5MB total)

---

## 9. CI/CD Pipeline (Future)

```yaml
# .github/workflows/test.yml (when CI is set up)
# Runs on every PR

steps:
  - Backend lint: ruff check + mypy
  - Backend unit tests: pytest tests/unit/
  - Frontend lint: eslint + tsc --noEmit
  - Frontend tests: pnpm test
  - Security scan: pip audit + pnpm audit
  # Integration tests run manually or on merge to main
```

---

## 10. Test Execution Commands

```bash
# All backend tests
cd backend && pytest -v

# Unit tests only
cd backend && pytest tests/unit/ -v

# Integration tests (requires running services)
cd backend && pytest tests/integration/ -v

# With coverage report
cd backend && pytest --cov=app --cov-report=html

# Security tests
cd backend && pytest tests/security/ -v

# Search accuracy evaluation
cd backend && python scripts/evaluate_search.py

# Frontend tests
cd frontend && pnpm test

# Frontend tests with coverage
cd frontend && pnpm test -- --coverage

# E2E tests (requires running backend + frontend)
cd frontend && pnpm test:e2e
```
