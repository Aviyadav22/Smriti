# Smriti — High-Level Design (HLD)

> Detailed module-level design for India's legal research platform.

---

## Table of Contents

1. [Module Breakdown](#module-breakdown)
2. [Service Boundaries](#service-boundaries)
3. [API Design Philosophy](#api-design-philosophy)
4. [AI Pipeline Detail](#ai-pipeline-detail)
5. [Vector DB Design (Pinecone)](#vector-db-design-pinecone)
6. [Caching Strategy](#caching-strategy)

---

## Module Breakdown

### 1. Search Module (`core/search/`)

**Purpose**: Execute hybrid legal search combining semantic understanding, lexical matching, and structured metadata filtering to return the most relevant Indian legal documents.

**Responsibilities**:
- Parse and understand user queries using LLM
- Execute parallel retrieval across vector, FTS, and metadata channels
- Fuse results using Reciprocal Rank Fusion
- Rerank final candidates for precision
- Enrich results with full case metadata

**Key Classes**:

#### `HybridSearchOrchestrator`
The central coordinator for all search operations.

```python
class HybridSearchOrchestrator:
    """Coordinates vector + FTS + metadata search into a single ranked result set."""

    def __init__(
        self,
        llm: LLMProvider,
        vector_store: VectorStore,
        embedding_provider: EmbeddingProvider,
        reranker: Reranker,
        db: AsyncSession,    # PostgreSQL (FTS + metadata)
    ):
        self.query_understanding = QueryUnderstanding(llm)
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider
        self.reranker = reranker
        self.db = db
        self.rrf_merger = RRFMerger(k=60)

    async def search(self, request: SearchRequest) -> SearchResponse:
        # 1. Understand query
        parsed = await self.query_understanding.parse(request.query)

        # 2. Parallel retrieval
        vector_task = self._vector_search(parsed)
        fts_task = self._fts_search(parsed)
        metadata_task = self._metadata_filter(parsed)
        vector_results, fts_results, metadata_ids = await asyncio.gather(
            vector_task, fts_task, metadata_task
        )

        # 3. Fuse
        merged = self.rrf_merger.merge(
            vector_results, fts_results, metadata_boost_ids=metadata_ids
        )

        # 4. Rerank top 20
        reranked = await self.reranker.rerank(
            query=parsed.reformulated_query,
            documents=[r.text for r in merged[:20]],
            top_n=5,
        )

        # 5. Enrich and return
        return await self._enrich_results(reranked)
```

#### `RRFMerger`
Implements Reciprocal Rank Fusion.

```python
class RRFMerger:
    """
    Reciprocal Rank Fusion implementation.

    Formula: RRF_score(d) = sum(1 / (k + rank_i(d))) for each ranking list i
    Default k=60 per Cormack et al. 2009.
    """

    def __init__(self, k: int = 60, metadata_boost: float = 0.5):
        self.k = k
        self.metadata_boost = metadata_boost

    def merge(
        self,
        vector_results: list[SearchResult],
        fts_results: list[SearchResult],
        metadata_boost_ids: set[str] | None = None,
    ) -> list[SearchResult]:
        scores: dict[str, float] = defaultdict(float)
        result_map: dict[str, SearchResult] = {}

        # Score from vector ranking
        for rank, result in enumerate(vector_results, start=1):
            scores[result.doc_id] += 1.0 / (self.k + rank)
            result_map[result.doc_id] = result

        # Score from FTS ranking
        for rank, result in enumerate(fts_results, start=1):
            scores[result.doc_id] += 1.0 / (self.k + rank)
            if result.doc_id not in result_map:
                result_map[result.doc_id] = result

        # Metadata boost: documents matching structured filters get a flat boost
        if metadata_boost_ids:
            for doc_id in metadata_boost_ids:
                if doc_id in scores:
                    scores[doc_id] += self.metadata_boost

        # Sort by RRF score descending
        ranked_ids = sorted(scores, key=scores.get, reverse=True)
        return [
            result_map[doc_id]._replace(score=scores[doc_id])
            for doc_id in ranked_ids
            if doc_id in result_map
        ]
```

#### `QueryUnderstanding`
LLM-based query parsing.

```python
class QueryUnderstanding:
    """Uses Gemini structured output to parse legal queries into intent + entities + filters."""

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    async def parse(self, raw_query: str) -> ParsedQuery:
        result = await self.llm.generate_structured(
            messages=[
                Message(role="system", content=QUERY_UNDERSTANDING_PROMPT),
                Message(role="user", content=raw_query),
            ],
            schema=ParsedQuery,
            temperature=0.0,
        )
        return result

class ParsedQuery(BaseModel):
    intent: Literal[
        "case_law_search", "statute_lookup", "legal_concept",
        "case_status", "citation_search", "general_question"
    ]
    entities: dict[str, str]        # statute, section, court, judge, party, etc.
    filters: SearchFilters          # structured filters for DB queries
    reformulated_query: str         # clean, expanded query for embedding
    is_follow_up: bool = False      # part of a conversation chain
```

**Dependencies**: `VectorStore`, `EmbeddingProvider`, `LLMProvider`, `Reranker`, PostgreSQL (via SQLAlchemy async session)

---

### 2. Ingestion Module (`core/ingestion/`)

**Purpose**: Transform raw legal PDFs into searchable, indexed, and graph-connected knowledge — the pipeline that populates all three data stores (PostgreSQL, Pinecone, Neo4j).

**Responsibilities**:
- Download and store PDFs in GCS
- Extract text from PDFs (with OCR fallback)
- Parse judgment sections (Facts, Arguments, Ratio Decidendi, Order)
- Extract structured metadata using LLM + regex validation
- Chunk text with section awareness
- Generate embeddings and upsert to Pinecone
- Insert metadata into PostgreSQL with FTS tsvector
- Build citation graph edges in Neo4j

**Key Classes**:

#### `IngestionPipeline`
Orchestrates the full PDF-to-knowledge pipeline.

```python
class IngestionPipeline:
    """
    Full ingestion pipeline: PDF → text → sections → metadata → chunks →
    embeddings → vector store + PostgreSQL + citation graph.
    """

    def __init__(
        self,
        pdf_extractor: PDFExtractor,
        section_detector: SectionDetector,
        metadata_extractor: MetadataExtractor,
        chunker: LegalChunker,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        graph_store: GraphStore,
        file_storage: FileStorage,
        db: AsyncSession,
    ):
        self.pdf_extractor = pdf_extractor
        self.section_detector = section_detector
        self.metadata_extractor = metadata_extractor
        self.chunker = chunker
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.file_storage = file_storage
        self.db = db

    async def ingest(self, source: IngestionSource) -> IngestionResult:
        # 1. Download PDF to GCS
        pdf_bytes = await self._download(source)
        gcs_path = await self.file_storage.upload(
            path=f"pdfs/{shard_key}/{source.doc_id}.pdf",
            data=pdf_bytes,
            content_type="application/pdf",
        )

        # 2. Extract text
        text = await self.pdf_extractor.extract(pdf_bytes)

        # 3. Detect sections
        sections = self.section_detector.detect(text)

        # 4. Extract metadata
        metadata = await self.metadata_extractor.extract(text, sections)

        # 5. Chunk (section-aware)
        chunks = self.chunker.chunk(sections, metadata)

        # 6. Embed
        embeddings = await self.embedding_provider.embed_batch(
            [c.text for c in chunks]
        )

        # 7. Upsert to Pinecone
        vectors = [
            VectorRecord(
                id=f"{source.doc_id}_{c.chunk_index}",
                values=emb,
                metadata={
                    "doc_id": source.doc_id,
                    "case_id": metadata.case_id,
                    "court": metadata.court,
                    "year": metadata.year,
                    "case_type": metadata.case_type,
                    "section_type": c.section_type,
                    "chunk_index": c.chunk_index,
                },
            )
            for c, emb in zip(chunks, embeddings)
        ]
        await self.vector_store.upsert(vectors)

        # 8. Insert into PostgreSQL
        await self._insert_to_db(metadata, chunks, gcs_path)

        # 9. Build citation graph
        await self._build_citations(metadata)

        return IngestionResult(
            doc_id=source.doc_id,
            chunks_created=len(chunks),
            citations_found=len(metadata.cases_cited),
        )
```

#### `PDFExtractor`
Text extraction with quality-aware OCR fallback.

```python
class PDFExtractor:
    """
    Extract text from legal PDFs.

    Strategy:
    1. Try PyMuPDF (fitz) for native text extraction.
    2. If extracted text is too short (< 100 chars per page), assume scanned PDF.
    3. Fall back to Tesseract OCR on rendered page images.
    """

    MIN_CHARS_PER_PAGE = 100

    async def extract(self, pdf_bytes: bytes) -> str:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        text_pages = []

        for page in doc:
            text = page.get_text()
            if len(text.strip()) >= self.MIN_CHARS_PER_PAGE:
                text_pages.append(text)
            else:
                # OCR fallback
                pix = page.get_pixmap(dpi=300)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                ocr_text = pytesseract.image_to_string(img, lang="eng")
                text_pages.append(ocr_text)

        return "\n\n".join(text_pages)
```

#### `LegalChunker`
Section-aware chunking that respects legal document structure.

```python
class LegalChunker:
    """
    Section-aware chunking for Indian legal judgments.

    Each section is chunked independently so that a single chunk never spans
    two sections (e.g., a chunk won't contain both Facts and Ratio Decidendi).

    Parameters:
        chunk_size: 2000 characters (not tokens — char-level is more predictable
                    for mixed English/Hindi legal text)
        overlap: 200 characters (ensures no context loss at boundaries)
    """

    def __init__(self, chunk_size: int = 2000, overlap: int = 200):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(
        self, sections: list[Section], metadata: CaseMetadata
    ) -> list[Chunk]:
        chunks = []
        global_index = 0

        for section in sections:
            text = section.text
            start = 0

            while start < len(text):
                end = start + self.chunk_size
                chunk_text = text[start:end]

                # Try to break at sentence boundary
                if end < len(text):
                    last_period = chunk_text.rfind(". ")
                    if last_period > self.chunk_size * 0.5:
                        chunk_text = chunk_text[: last_period + 1]
                        end = start + last_period + 1

                chunks.append(Chunk(
                    text=chunk_text.strip(),
                    section_type=section.section_type,
                    chunk_index=global_index,
                    doc_id=metadata.doc_id,
                    char_start=start,
                    char_end=end,
                ))
                global_index += 1
                start = end - self.overlap

        return chunks
```

#### `MetadataExtractor`
LLM-powered metadata extraction with regex validation.

```python
class MetadataExtractor:
    """
    Two-pass metadata extraction:
    1. Gemini structured output extracts fields from judgment text.
    2. Regex validation pass catches LLM errors in citations, dates, court names.

    This hybrid approach combines LLM flexibility (understanding varied judgment
    formats) with regex precision (citation format must be exact).
    """

    CITATION_REGEX = re.compile(
        r"\(\d{4}\)\s+\d+\s+SCC\s+\d+|"   # (2024) 5 SCC 123
        r"AIR\s+\d{4}\s+SC\s+\d+|"          # AIR 2024 SC 456
        r"\d{4}\s+SCC\s+OnLine\s+SC\s+\d+"   # 2024 SCC OnLine SC 789
    )

    COURT_NAMES = {
        "Supreme Court of India", "Delhi High Court",
        "Bombay High Court", "Madras High Court",
        # ... all High Courts and tribunals
    }

    async def extract(self, text: str, sections: list[Section]) -> CaseMetadata:
        # Pass 1: LLM extraction
        llm_metadata = await self.llm.generate_structured(
            messages=[
                Message(role="system", content=METADATA_EXTRACTION_PROMPT),
                Message(role="user", content=text[:15000]),  # First 15K chars
            ],
            schema=CaseMetadata,
        )

        # Pass 2: Regex validation
        validated = self._validate(llm_metadata, text)
        return validated

    def _validate(self, metadata: CaseMetadata, text: str) -> CaseMetadata:
        # Validate citation format
        if metadata.citation and not self.CITATION_REGEX.match(metadata.citation):
            # Try to find citation in text via regex
            found = self.CITATION_REGEX.search(text[:2000])
            if found:
                metadata.citation = found.group()

        # Validate court name
        if metadata.court not in self.COURT_NAMES:
            metadata.court = self._fuzzy_match_court(metadata.court)

        # Validate date
        if metadata.date:
            try:
                datetime.strptime(metadata.date, "%Y-%m-%d")
            except ValueError:
                metadata.date = None

        return metadata
```

**Dependencies**: `LLMProvider`, `EmbeddingProvider`, `VectorStore`, `GraphStore`, `FileStorage`, PostgreSQL

---

### 3. Legal Module (`core/legal/`)

**Purpose**: Encode Indian legal domain knowledge — citation formats, court hierarchies, judgment structure, legal terminology. This module has **no external dependencies** (no LLM, no DB) and is pure domain logic.

**Responsibilities**:
- Parse and normalize Indian legal citations
- Map courts to their hierarchy level and jurisdiction
- Detect judgment sections from text patterns
- Provide constants for case types, bench types, legal terms

**Key Classes**:

#### `CitationParser`
Parse and normalize the many formats of Indian legal citations.

```python
class CitationParser:
    """
    Parses Indian legal citations into structured objects.

    Supported formats:
    - SCC: (2024) 5 SCC 123
    - AIR: AIR 2024 SC 456
    - SCC OnLine: 2024 SCC OnLine SC 789
    - SCR: [1950] SCR 88
    - All India Reporter variants
    - High Court citations: 2024 SCC OnLine Del 1234
    """

    PATTERNS = [
        # (year) volume SCC page
        (
            re.compile(r"\((\d{4})\)\s+(\d+)\s+SCC\s+(\d+)"),
            lambda m: Citation(
                reporter="SCC", year=int(m.group(1)),
                volume=int(m.group(2)), page=int(m.group(3)),
                raw=m.group(0),
            ),
        ),
        # AIR year court page
        (
            re.compile(r"AIR\s+(\d{4})\s+(\w+)\s+(\d+)"),
            lambda m: Citation(
                reporter="AIR", year=int(m.group(1)),
                court_code=m.group(2), page=int(m.group(3)),
                raw=m.group(0),
            ),
        ),
        # year SCC OnLine court_code number
        (
            re.compile(r"(\d{4})\s+SCC\s+OnLine\s+(\w+)\s+(\d+)"),
            lambda m: Citation(
                reporter="SCC OnLine", year=int(m.group(1)),
                court_code=m.group(2), page=int(m.group(3)),
                raw=m.group(0),
            ),
        ),
    ]

    @classmethod
    def parse(cls, text: str) -> list[Citation]:
        """Find and parse all citations in the given text."""
        citations = []
        for pattern, builder in cls.PATTERNS:
            for match in pattern.finditer(text):
                citations.append(builder(match))
        return citations

    @classmethod
    def normalize(cls, citation: Citation) -> str:
        """Return a canonical string form for deduplication."""
        if citation.reporter == "SCC":
            return f"({citation.year}) {citation.volume} SCC {citation.page}"
        elif citation.reporter == "AIR":
            return f"AIR {citation.year} {citation.court_code} {citation.page}"
        elif citation.reporter == "SCC OnLine":
            return f"{citation.year} SCC OnLine {citation.court_code} {citation.page}"
        return citation.raw
```

#### `CourtHierarchy`
Court levels and jurisdiction mapping.

```python
class CourtHierarchy:
    """
    Indian court hierarchy for determining precedent weight.

    Level 1: Supreme Court of India (binding on all courts)
    Level 2: High Courts (binding within jurisdiction, persuasive elsewhere)
    Level 3: District Courts, Tribunals, Commissions
    Level 4: Subordinate courts, quasi-judicial bodies
    """

    HIERARCHY: dict[str, int] = {
        "Supreme Court of India": 1,
        "Delhi High Court": 2,
        "Bombay High Court": 2,
        "Madras High Court": 2,
        "Calcutta High Court": 2,
        "Karnataka High Court": 2,
        "Allahabad High Court": 2,
        "Kerala High Court": 2,
        "Punjab and Haryana High Court": 2,
        "Gujarat High Court": 2,
        "Telangana High Court": 2,
        "Rajasthan High Court": 2,
        "Gauhati High Court": 2,
        "Orissa High Court": 2,
        "Jharkhand High Court": 2,
        "Chhattisgarh High Court": 2,
        "Himachal Pradesh High Court": 2,
        "Uttarakhand High Court": 2,
        "Tripura High Court": 2,
        "Meghalaya High Court": 2,
        "Manipur High Court": 2,
        "Sikkim High Court": 2,
        "Jammu and Kashmir High Court": 2,
        "National Company Law Tribunal": 3,
        "National Green Tribunal": 3,
        "NCDRC": 3,
        "ITAT": 3,
        "DRT": 3,
        "CAT": 3,
    }

    JURISDICTION: dict[str, list[str]] = {
        "Delhi High Court": ["Delhi", "NCT Delhi"],
        "Bombay High Court": ["Maharashtra", "Goa", "Dadra and Nagar Haveli", "Daman and Diu"],
        "Madras High Court": ["Tamil Nadu", "Puducherry"],
        "Calcutta High Court": ["West Bengal", "Andaman and Nicobar Islands"],
        # ... all High Court jurisdictions
    }

    @classmethod
    def get_level(cls, court_name: str) -> int:
        return cls.HIERARCHY.get(court_name, 4)

    @classmethod
    def is_binding_on(cls, source_court: str, target_court: str) -> bool:
        """Check if source_court's decisions are binding on target_court."""
        source_level = cls.get_level(source_court)
        target_level = cls.get_level(target_court)

        if source_level < target_level:
            return True  # Higher court is always binding

        if source_level == 2 and target_level >= 3:
            # High Court binding on lower courts within its jurisdiction
            source_jurisdiction = cls.JURISDICTION.get(source_court, [])
            target_jurisdiction = cls.JURISDICTION.get(target_court, [])
            return bool(set(source_jurisdiction) & set(target_jurisdiction))

        return False
```

#### `SectionDetector`
Identify judgment sections from text patterns.

```python
class SectionDetector:
    """
    Detects standard sections in Indian court judgments.

    Indian judgments typically follow this structure:
    1. Header (case name, court, judges, date)
    2. Facts of the Case
    3. Arguments (Petitioner's submissions, Respondent's submissions)
    4. Issues framed
    5. Analysis / Discussion
    6. Ratio Decidendi (the legal principle)
    7. Order / Judgment (the actual decision)
    """

    SECTION_PATTERNS = [
        (SectionType.HEADER, re.compile(
            r"^(IN THE SUPREME COURT|IN THE HIGH COURT|BEFORE|CORAM)",
            re.MULTILINE | re.IGNORECASE
        )),
        (SectionType.FACTS, re.compile(
            r"^(FACTS|BRIEF FACTS|FACTUAL BACKGROUND|THE FACTS)",
            re.MULTILINE | re.IGNORECASE
        )),
        (SectionType.ARGUMENTS, re.compile(
            r"^(ARGUMENTS?|SUBMISSIONS?|CONTENTIONS?|HEARD)",
            re.MULTILINE | re.IGNORECASE
        )),
        (SectionType.ISSUES, re.compile(
            r"^(ISSUES?|POINTS? FOR (DETERMINATION|CONSIDERATION))",
            re.MULTILINE | re.IGNORECASE
        )),
        (SectionType.ANALYSIS, re.compile(
            r"^(ANALYSIS|DISCUSSION|REASONING|CONSIDERATION)",
            re.MULTILINE | re.IGNORECASE
        )),
        (SectionType.RATIO, re.compile(
            r"^(RATIO|RATIO DECIDENDI|THE LAW|LEGAL POSITION)",
            re.MULTILINE | re.IGNORECASE
        )),
        (SectionType.ORDER, re.compile(
            r"^(ORDER|JUDGMENT|RESULT|DISPOSITION|CONCLUSION|OPERATIVE PART)",
            re.MULTILINE | re.IGNORECASE
        )),
    ]

    def detect(self, text: str) -> list[Section]:
        """Split judgment text into labeled sections."""
        # Find all section boundaries
        boundaries: list[tuple[int, SectionType]] = []
        for section_type, pattern in self.SECTION_PATTERNS:
            for match in pattern.finditer(text):
                boundaries.append((match.start(), section_type))

        # Sort by position
        boundaries.sort(key=lambda x: x[0])

        if not boundaries:
            # No sections detected — return entire text as FULL_TEXT
            return [Section(section_type=SectionType.FULL_TEXT, text=text)]

        # Build sections
        sections = []
        for i, (start, section_type) in enumerate(boundaries):
            end = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(text)
            section_text = text[start:end].strip()
            if section_text:
                sections.append(Section(
                    section_type=section_type,
                    text=section_text,
                ))

        return sections
```

#### `Constants`

```python
# core/legal/constants.py

class CaseType(str, Enum):
    CIVIL_APPEAL = "civil_appeal"
    CRIMINAL_APPEAL = "criminal_appeal"
    WRIT_PETITION = "writ_petition"
    SPECIAL_LEAVE_PETITION = "special_leave_petition"
    TRANSFER_PETITION = "transfer_petition"
    REVIEW_PETITION = "review_petition"
    CURATIVE_PETITION = "curative_petition"
    PIL = "public_interest_litigation"
    ORIGINAL_SUIT = "original_suit"
    CONTEMPT_PETITION = "contempt_petition"
    ARBITRATION = "arbitration"
    COMPANY_PETITION = "company_petition"

class BenchType(str, Enum):
    SINGLE_JUDGE = "single_judge"
    DIVISION_BENCH = "division_bench"       # 2 judges
    FULL_BENCH = "full_bench"               # 3 judges
    CONSTITUTION_BENCH = "constitution_bench"  # 5+ judges
    LARGER_BENCH = "larger_bench"            # 7, 9, 11, 13 judges

class SectionType(str, Enum):
    HEADER = "header"
    FACTS = "facts"
    ARGUMENTS = "arguments"
    ISSUES = "issues"
    ANALYSIS = "analysis"
    RATIO = "ratio_decidendi"
    ORDER = "order"
    FULL_TEXT = "full_text"

MAJOR_STATUTES: dict[str, str] = {
    "IPC": "Indian Penal Code, 1860",
    "BNS": "Bharatiya Nyaya Sanhita, 2023",
    "CrPC": "Code of Criminal Procedure, 1973",
    "BNSS": "Bharatiya Nagarik Suraksha Sanhita, 2023",
    "CPC": "Code of Civil Procedure, 1908",
    "IEA": "Indian Evidence Act, 1872",
    "BSA": "Bharatiya Sakshya Adhiniyam, 2023",
    "Constitution": "Constitution of India",
    "IT Act": "Information Technology Act, 2000",
    "Companies Act": "Companies Act, 2013",
    "DPDP Act": "Digital Personal Data Protection Act, 2023",
    "Arbitration Act": "Arbitration and Conciliation Act, 1996",
    "RERA": "Real Estate (Regulation and Development) Act, 2016",
    "IBC": "Insolvency and Bankruptcy Code, 2016",
    "PMLA": "Prevention of Money Laundering Act, 2002",
    "NDPS Act": "Narcotic Drugs and Psychotropic Substances Act, 1985",
}
```

**Dependencies**: None (pure domain logic). This module is imported by Search, Ingestion, and Graph modules.

---

### 4. Graph Module (`core/graph/`)

**Purpose**: Build and query the citation graph in Neo4j to enable citation chain analysis, identify overruled cases, and power visualization features.

**Responsibilities**:
- Extract citations from case metadata and create graph edges
- Resolve cited case names/citations to existing case nodes
- Execute graph traversals (cited-by, cites, chain, overruled)
- Return structured data for frontend visualization

**Key Classes**:

#### `CitationGraphBuilder`
Extracts citations from metadata and creates graph relationships.

```python
class CitationGraphBuilder:
    """
    Builds the citation graph from ingested case metadata.

    Node: Case {id, case_name, citation, court, year, case_type}
    Edge types:
      - CITES: this case cites another case
      - OVERRULES: this case overrules another (detected from text)
      - FOLLOWS: this case follows the reasoning of another
      - DISTINGUISHES: this case distinguishes itself from another
    """

    def __init__(self, graph_store: GraphStore, citation_parser: CitationParser):
        self.graph_store = graph_store
        self.citation_parser = citation_parser

    async def build_for_case(self, metadata: CaseMetadata) -> int:
        """Create case node and all citation edges. Returns edge count."""
        # 1. Create/update the case node
        await self.graph_store.add_case(CaseNode(
            id=metadata.case_id,
            case_name=metadata.case_name,
            citation=metadata.citation,
            court=metadata.court,
            year=metadata.year,
            case_type=metadata.case_type,
        ))

        # 2. Parse cited cases
        edge_count = 0
        for cited_raw in metadata.cases_cited:
            parsed_citations = self.citation_parser.parse(cited_raw)
            for citation in parsed_citations:
                # Resolve to existing case node
                target_id = await self._resolve_citation(citation)
                if target_id:
                    rel_type = self._detect_relationship_type(
                        metadata.full_text, citation
                    )
                    await self.graph_store.add_citation(
                        from_id=metadata.case_id,
                        to_id=target_id,
                        rel_type=rel_type,
                    )
                    edge_count += 1

        return edge_count

    async def _resolve_citation(self, citation: Citation) -> str | None:
        """Try to find existing case node matching this citation."""
        normalized = self.citation_parser.normalize(citation)
        return await self.graph_store.find_case_by_citation(normalized)

    def _detect_relationship_type(self, text: str, citation: Citation) -> str:
        """
        Detect if the case overrules, follows, or distinguishes the cited case.
        Looks at surrounding text within 500 chars of the citation.
        """
        context_window = 500
        cite_str = citation.raw
        idx = text.find(cite_str)
        if idx == -1:
            return "CITES"  # default

        surrounding = text[max(0, idx - context_window): idx + len(cite_str) + context_window].lower()

        if any(word in surrounding for word in ["overrule", "overruled", "no longer good law"]):
            return "OVERRULES"
        elif any(word in surrounding for word in ["distinguished", "distinguishable", "distinguishes"]):
            return "DISTINGUISHES"
        elif any(word in surrounding for word in ["followed", "follows", "following the ratio"]):
            return "FOLLOWS"
        else:
            return "CITES"
```

#### `GraphQuerier`
Execute graph traversals and return structured results.

```python
class GraphQuerier:
    """
    Query the Neo4j citation graph for various traversal patterns.
    """

    def __init__(self, graph_store: GraphStore):
        self.graph_store = graph_store

    async def get_cited_by(self, case_id: str, depth: int = 1) -> list[CaseNode]:
        """Cases that cite this case (incoming CITES edges)."""
        return await self.graph_store.get_cited_by(case_id, depth)

    async def get_cites(self, case_id: str, depth: int = 1) -> list[CaseNode]:
        """Cases cited by this case (outgoing CITES edges)."""
        return await self.graph_store.get_cites(case_id, depth)

    async def get_citation_chain(self, case_id: str, max_depth: int = 3) -> GraphData:
        """
        Full citation chain up to max_depth.
        Returns both nodes and edges for visualization.

        Example Cypher (executed inside GraphStore implementation):
          MATCH path = (c:Case {id: $case_id})-[:CITES*1..3]-(related)
          RETURN path
        """
        return await self.graph_store.get_citation_chain(case_id, max_depth)

    async def is_overruled(self, case_id: str) -> bool:
        """Check if any subsequent case has overruled this one."""
        overruling = await self.graph_store.find_relationship(
            to_id=case_id, rel_type="OVERRULES"
        )
        return len(overruling) > 0

    async def get_related_by_statute(
        self, case_id: str, statute: str
    ) -> list[CaseNode]:
        """
        Find cases that cite the same statute section.

        Cypher:
          MATCH (c1:Case {id: $case_id})-[:CITES_STATUTE]->(s:Statute {name: $statute})
                <-[:CITES_STATUTE]-(c2:Case)
          WHERE c1 <> c2
          RETURN c2
          ORDER BY c2.year DESC
          LIMIT 20
        """
        return await self.graph_store.get_related_by_statute(case_id, statute)

    async def get_visualization_data(self, case_id: str) -> dict:
        """
        Return D3-compatible graph data for frontend visualization.
        """
        chain = await self.get_citation_chain(case_id, max_depth=2)
        is_overruled = await self.is_overruled(case_id)

        return {
            "nodes": [
                {
                    "id": node.id,
                    "label": node.case_name,
                    "court": node.court,
                    "year": node.year,
                    "level": CourtHierarchy.get_level(node.court),
                    "is_overruled": await self.is_overruled(node.id),
                }
                for node in chain.nodes
            ],
            "edges": [
                {
                    "source": edge.from_id,
                    "target": edge.to_id,
                    "type": edge.rel_type,
                }
                for edge in chain.edges
            ],
            "stats": {
                "total_citing": len([e for e in chain.edges if e.to_id == case_id]),
                "total_cited": len([e for e in chain.edges if e.from_id == case_id]),
                "is_overruled": is_overruled,
            },
        }
```

**Dependencies**: `GraphStore` (Neo4j implementation), `CitationParser` (from Legal module)

---

### 5. Security Module (`security/`)

**Purpose**: Handle authentication, authorization, rate limiting, audit logging, and data protection compliance.

**Responsibilities**:
- JWT token issuance, validation, and rotation
- Password hashing with bcrypt
- Role-based access control (RBAC)
- Per-user and per-IP rate limiting
- Comprehensive audit logging
- DPDP Act consent management and data erasure

**Key Classes**:

#### `JWTAuth`

```python
class JWTAuth:
    """JWT authentication with access + refresh token pattern."""

    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm

    def create_access_token(
        self, user_id: str, role: str, expires_delta: timedelta = timedelta(minutes=15)
    ) -> str:
        payload = {
            "sub": user_id,
            "role": role,
            "type": "access",
            "exp": datetime.utcnow() + expires_delta,
            "iat": datetime.utcnow(),
            "jti": str(uuid4()),  # unique token ID for revocation
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def create_refresh_token(
        self, user_id: str, expires_delta: timedelta = timedelta(days=7)
    ) -> str:
        payload = {
            "sub": user_id,
            "type": "refresh",
            "exp": datetime.utcnow() + expires_delta,
            "iat": datetime.utcnow(),
            "jti": str(uuid4()),
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str, expected_type: str = "access") -> TokenPayload:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            if payload.get("type") != expected_type:
                raise InvalidTokenError(f"Expected {expected_type} token")
            return TokenPayload(**payload)
        except jwt.ExpiredSignatureError:
            raise TokenExpiredError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise InvalidTokenError(str(e))
```

#### `PasswordHasher`

```python
class PasswordHasher:
    """bcrypt password hashing with configurable rounds."""

    def __init__(self, rounds: int = 12):
        self.rounds = rounds

    def hash(self, password: str) -> str:
        return bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt(rounds=self.rounds),
        ).decode("utf-8")

    def verify(self, password: str, hashed: str) -> bool:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
```

#### `RBAC`

```python
class RBAC:
    """Role-based access control."""

    PERMISSIONS: dict[str, set[str]] = {
        "free": {
            "search:read",
            "case:read",
            "graph:read",
            "chat:basic",        # limited chat queries per day
        },
        "pro": {
            "search:read",
            "case:read",
            "graph:read",
            "chat:unlimited",
            "document:download",
            "history:read",
        },
        "admin": {
            "search:read",
            "case:read",
            "graph:read",
            "chat:unlimited",
            "document:download",
            "document:upload",
            "ingest:write",
            "user:manage",
            "audit:read",
            "history:read",
        },
    }

    @classmethod
    def has_permission(cls, role: str, permission: str) -> bool:
        role_permissions = cls.PERMISSIONS.get(role, set())
        return permission in role_permissions

    @classmethod
    def require(cls, permission: str):
        """FastAPI dependency that checks permission."""
        async def _check(current_user: User = Depends(get_current_user)):
            if not cls.has_permission(current_user.role, permission):
                raise HTTPException(
                    status_code=403,
                    detail=f"Permission denied: {permission}",
                )
            return current_user
        return _check
```

#### `RateLimiter`

```python
class RateLimiter:
    """
    Sliding window rate limiter backed by Redis.
    Supports per-user and per-IP limits.
    """

    def __init__(self, redis: Redis):
        self.redis = redis

    async def check(
        self, key: str, limit: int, window_seconds: int
    ) -> RateLimitResult:
        now = time.time()
        window_start = now - window_seconds

        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)    # remove expired
        pipe.zadd(key, {str(now): now})                 # add current request
        pipe.zcard(key)                                  # count in window
        pipe.expire(key, window_seconds)                 # TTL cleanup
        _, _, count, _ = await pipe.execute()

        return RateLimitResult(
            allowed=count <= limit,
            remaining=max(0, limit - count),
            reset_at=int(now + window_seconds),
        )
```

#### `AuditLogger`

```python
class AuditLogger:
    """Append-only audit log for all data access events."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        user_id: str | None,
        action: str,
        resource_type: str,
        resource_id: str,
        ip_address: str,
        user_agent: str,
        metadata: dict | None = None,
    ) -> None:
        entry = AuditLogEntry(
            id=str(uuid4()),
            timestamp=datetime.utcnow(),
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata or {},
        )
        self.db.add(entry)
        await self.db.flush()  # Immediate write, no waiting for commit
```

#### `ConsentManager`

```python
class ConsentManager:
    """DPDP Act consent management."""

    async def record_consent(
        self, user_id: str, purpose: str, version: str
    ) -> None:
        """Record user consent for a specific data processing purpose."""
        consent = Consent(
            user_id=user_id,
            purpose=purpose,
            version=version,
            granted_at=datetime.utcnow(),
            is_active=True,
        )
        self.db.add(consent)
        await self.db.commit()

    async def withdraw_consent(self, user_id: str, purpose: str) -> None:
        """Withdraw consent and trigger data handling changes."""
        await self.db.execute(
            update(Consent)
            .where(Consent.user_id == user_id, Consent.purpose == purpose)
            .values(is_active=False, withdrawn_at=datetime.utcnow())
        )
        await self.db.commit()

    async def erase_user_data(self, user_id: str) -> ErasureReport:
        """
        Full data erasure per DPDP Act right to erasure.
        Anonymizes audit logs (keeps event but removes PII).
        Deletes: user record, search history, chat history, preferences.
        """
        report = ErasureReport(user_id=user_id)

        # Anonymize audit logs
        await self.db.execute(
            update(AuditLogEntry)
            .where(AuditLogEntry.user_id == user_id)
            .values(user_id=None, ip_address="[REDACTED]", user_agent="[REDACTED]")
        )
        report.audit_logs_anonymized = True

        # Delete user data
        for model in [SearchHistory, ChatHistory, UserPreference]:
            result = await self.db.execute(
                delete(model).where(model.user_id == user_id)
            )
            report.records_deleted += result.rowcount

        # Delete user record
        await self.db.execute(delete(User).where(User.id == user_id))
        report.user_deleted = True

        await self.db.commit()
        return report
```

**Dependencies**: PostgreSQL, Redis, `python-jose` (JWT), `bcrypt`

---

### 6. API Module (`api/routes/`)

**Purpose**: HTTP interface layer. Thin route handlers that delegate to core service classes.

**Responsibilities**:
- Request validation (Pydantic models)
- Authentication and authorization (via dependencies)
- Route to appropriate service
- Format and return responses
- Handle errors consistently

**Routers**:

#### `SearchRouter` (`api/routes/search.py`)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/api/v1/search` | Hybrid search | Required |
| GET | `/api/v1/search/suggestions` | Autocomplete suggestions | Optional |
| GET | `/api/v1/search/history` | User's search history | Required |

#### `IngestRouter` (`api/routes/ingest.py`)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/api/v1/ingest` | Ingest single document | Admin |
| POST | `/api/v1/ingest/batch` | Batch ingest (up to 50) | Admin |
| GET | `/api/v1/ingest/{job_id}/status` | Check ingestion status | Admin |

#### `ChatRouter` (`api/routes/chat.py`)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/api/v1/chat` | Send message (SSE stream) | Required |
| GET | `/api/v1/chat/sessions` | List chat sessions | Required |
| GET | `/api/v1/chat/sessions/{id}` | Get session messages | Required |
| DELETE | `/api/v1/chat/sessions/{id}` | Delete session | Required |

#### `CaseRouter` (`api/routes/cases.py`)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/v1/cases/{id}` | Get case details | Required |
| GET | `/api/v1/cases/{id}/pdf` | Get signed PDF URL | Pro+ |
| GET | `/api/v1/cases/{id}/sections` | Get parsed sections | Required |
| GET | `/api/v1/cases/{id}/metadata` | Get case metadata | Required |

#### `GraphRouter` (`api/routes/graph.py`)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/v1/graph/{case_id}/cited-by` | Cases citing this case | Required |
| GET | `/api/v1/graph/{case_id}/cites` | Cases cited by this case | Required |
| GET | `/api/v1/graph/{case_id}/chain` | Full citation chain | Required |
| GET | `/api/v1/graph/{case_id}/visualization` | D3-compatible graph data | Required |

#### `AuthRouter` (`api/routes/auth.py`)

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/api/v1/auth/register` | Create account | Public |
| POST | `/api/v1/auth/login` | Login | Public |
| POST | `/api/v1/auth/refresh` | Refresh access token | Public (refresh token) |
| POST | `/api/v1/auth/logout` | Revoke refresh token | Required |
| GET | `/api/v1/auth/me` | Get current user | Required |
| DELETE | `/api/v1/auth/me` | Delete account (DPDP) | Required |

---

## Service Boundaries

### Current Architecture: Monolith for MVP

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI Application                       │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                  API Layer (Routes)                  │    │
│  ├─────────────────────────────────────────────────────┤    │
│  │               Core Service Layer                     │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │    │
│  │  │  Search  │ │ Ingest   │ │  Chat    │ │  Graph │ │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────┘ │    │
│  ├─────────────────────────────────────────────────────┤    │
│  │              Domain Layer (Legal)                    │    │
│  ├─────────────────────────────────────────────────────┤    │
│  │              Provider Layer (Interfaces)             │    │
│  ├─────────────────────────────────────────────────────┤    │
│  │              Security Layer                          │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  Single Cloud Run container                                 │
│  Single process, async I/O (uvicorn)                        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                Next.js 15 Frontend                          │
│  Separate Cloud Run container                               │
│  SSR + client-side hydration                                │
└─────────────────────────────────────────────────────────────┘
```

**Why monolith for MVP?**

1. **Simplicity**: One deployable, one set of logs, one set of health checks.
2. **Latency**: In-process calls between modules (search → legal → graph) have zero network overhead.
3. **Development speed**: No inter-service contracts, no service mesh, no distributed tracing needed yet.
4. **Cost**: Single Cloud Run service scales to zero when idle.

### Future: Async Ingestion Worker

When ingestion volume exceeds what can be handled synchronously (target: >100 documents/day), the ingestion module will be split:

```
┌──────────────────┐         ┌───────────────────────┐
│  FastAPI Backend  │         │  Ingestion Worker      │
│  (Cloud Run)      │         │  (Cloud Run Jobs or    │
│                   │──push──►│   Cloud Tasks)         │
│  POST /ingest     │  queue  │                        │
│  returns job_id   │         │  Pulls from queue      │
│                   │         │  Runs full pipeline     │
│  GET /ingest/     │         │  Updates job status     │
│    {job_id}/      │◄────────│  in PostgreSQL          │
│    status         │  poll   │                        │
└──────────────────┘         └───────────────────────┘
```

**Queue options** (in order of preference):
1. **Google Cloud Tasks** — serverless, auto-retry, dead-letter queue, native Cloud Run integration
2. **Redis queue (rq)** — simple, uses existing Upstash Redis
3. **Celery + Redis** — more features but heavier operational burden

---

## API Design Philosophy

### REST for CRUD Operations

All resource operations follow REST conventions:

```
GET    /api/v1/cases              → list cases (paginated)
GET    /api/v1/cases/{id}         → get single case
POST   /api/v1/ingest             → create (ingest) document
DELETE /api/v1/chat/sessions/{id} → delete chat session
```

### SSE for Chat Streaming

Chat responses use Server-Sent Events (SSE), not WebSockets. SSE is simpler, works through proxies and load balancers, and is sufficient for server-to-client streaming.

```python
@router.post("/chat")
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
):
    async def event_generator():
        async for event in chat_engine.stream(request, current_user):
            match event:
                case TokenEvent(text=text):
                    yield {
                        "event": "token",
                        "data": json.dumps({"text": text}),
                    }
                case CitationEvent(ref=ref, case_id=case_id):
                    yield {
                        "event": "citation",
                        "data": json.dumps({"ref": ref, "case_id": case_id}),
                    }
                case DoneEvent(usage=usage):
                    yield {
                        "event": "done",
                        "data": json.dumps({"usage": usage}),
                    }

    return EventSourceResponse(event_generator())
```

### Consistent Error Format

Every error response follows this structure:

```json
{
  "error": "Human-readable error message",
  "code": "MACHINE_READABLE_ERROR_CODE",
  "details": {
    "field": "query",
    "reason": "Query must be between 1 and 2000 characters"
  }
}
```

Standard error codes:

| HTTP Status | Error Code | Meaning |
|-------------|-----------|---------|
| 400 | `VALIDATION_ERROR` | Request body/params failed validation |
| 401 | `TOKEN_EXPIRED` | Access token has expired |
| 401 | `INVALID_TOKEN` | Token is malformed or signature invalid |
| 403 | `PERMISSION_DENIED` | User lacks required permission |
| 404 | `RESOURCE_NOT_FOUND` | Requested resource does not exist |
| 409 | `ALREADY_EXISTS` | Resource already exists (e.g., duplicate email) |
| 429 | `RATE_LIMITED` | Too many requests |
| 500 | `INTERNAL_ERROR` | Unexpected server error |
| 503 | `SERVICE_UNAVAILABLE` | Downstream service (Pinecone, Gemini) unreachable |

### Versioning

All API routes are prefixed with `/api/v1/`. When breaking changes are needed, a `/api/v2/` prefix will be introduced while keeping v1 operational for a deprecation period.

### Pagination: Cursor-Based

For endpoints returning large result sets (case listings, search history), we use cursor-based pagination:

```json
// Request
GET /api/v1/cases?cursor=eyJpZCI6MTIzfQ&limit=20

// Response
{
  "data": [...],
  "pagination": {
    "next_cursor": "eyJpZCI6MTQzfQ",
    "has_more": true,
    "total_count": 15420
  }
}
```

**Why cursor-based over offset-based?**

1. **Consistent results**: Offset pagination breaks when new documents are ingested between page requests. Cursor pagination always picks up from the exact same point.
2. **Performance**: `OFFSET 10000 LIMIT 20` requires scanning and discarding 10,000 rows. Cursor uses `WHERE id > :cursor LIMIT 20` which is an index seek.
3. **Scalability**: Works identically whether there are 1,000 or 10,000,000 records.

---

## AI Pipeline Detail

### End-to-End Search Pipeline

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            SEARCH PIPELINE                              │
│                                                                         │
│  ┌─────────────┐                                                        │
│  │  Raw Query   │  "SC judgments on 498A misuse after 2020"             │
│  └──────┬──────┘                                                        │
│         │                                                               │
│         ▼                                                               │
│  ┌──────────────────────────────────────────────────────┐               │
│  │  QueryUnderstanding (Gemini 3.1 Pro)                  │               │
│  │                                                        │               │
│  │  Structured output:                                    │               │
│  │  {                                                     │               │
│  │    "intent": "case_law_search",                        │               │
│  │    "entities": {                                       │               │
│  │      "statute": "Section 498A IPC",                    │               │
│  │      "legal_concept": "misuse of anti-dowry law"       │               │
│  │    },                                                  │               │
│  │    "filters": {                                        │               │
│  │      "court": "supreme_court",                         │               │
│  │      "year_from": 2020                                 │               │
│  │    },                                                  │               │
│  │    "reformulated_query": "Supreme Court of India       │               │
│  │      judgments on misuse and abuse of Section 498A      │               │
│  │      Indian Penal Code anti-dowry cruelty provisions    │               │
│  │      after 2020"                                       │               │
│  │  }                                                     │               │
│  └──────────────────────┬───────────────────────────────┘               │
│                         │                                               │
│           ┌─────────────┼─────────────┐                                 │
│           ▼             ▼             ▼                                  │
│  ┌────────────────┐ ┌──────────────┐ ┌──────────────────┐              │
│  │ PINECONE       │ │ POSTGRESQL   │ │ POSTGRESQL       │              │
│  │ Vector Search  │ │ FTS Search   │ │ Metadata Filter  │              │
│  │                │ │              │ │                  │              │
│  │ 1. Embed query │ │ plainto_     │ │ SELECT doc_id    │              │
│  │    via Gemini  │ │ tsquery()    │ │ FROM cases       │              │
│  │    text-embed- │ │              │ │ WHERE court =    │              │
│  │    ding-004    │ │ ts_rank_cd() │ │   'supreme_court'│              │
│  │    (768 dims)  │ │ for cover    │ │ AND year >= 2020 │              │
│  │                │ │ density      │ │                  │              │
│  │ 2. Query with  │ │ ranking      │ │ Returns: set of  │              │
│  │    filters:    │ │              │ │ doc_ids for      │              │
│  │    court=SC    │ │ top_k = 20   │ │ RRF boost        │              │
│  │    year>=2020  │ │              │ │                  │              │
│  │                │ │              │ │                  │              │
│  │ top_k = 20     │ │              │ │                  │              │
│  └───────┬────────┘ └──────┬───────┘ └────────┬─────────┘              │
│          │                 │                  │                         │
│          └─────────────────┼──────────────────┘                         │
│                            ▼                                            │
│  ┌──────────────────────────────────────────────────────┐               │
│  │  RRFMerger (k=60)                                     │               │
│  │                                                        │               │
│  │  For each doc d:                                       │               │
│  │    score = 1/(60 + vector_rank) + 1/(60 + fts_rank)   │               │
│  │    if d in metadata_ids: score += 0.5                  │               │
│  │                                                        │               │
│  │  Sort by score descending → top 20                     │               │
│  └──────────────────────┬───────────────────────────────┘               │
│                         │                                               │
│                         ▼                                               │
│  ┌──────────────────────────────────────────────────────┐               │
│  │  Cohere rerank-v3                                     │               │
│  │                                                        │               │
│  │  Input: query + 20 document texts                      │               │
│  │  Cross-encoder attention: reads query and doc together  │               │
│  │  Output: top 5 with relevance scores                   │               │
│  │                                                        │               │
│  │  Latency budget: ~200-400ms                            │               │
│  └──────────────────────┬───────────────────────────────┘               │
│                         │                                               │
│                         ▼                                               │
│  ┌──────────────────────────────────────────────────────┐               │
│  │  Enrich with Metadata                                 │               │
│  │                                                        │               │
│  │  For each of top 5 results:                            │               │
│  │  - Fetch full case metadata from PostgreSQL            │               │
│  │  - Attach: case_name, citation, court, bench, date,    │               │
│  │    case_type, headnotes, outcome                       │               │
│  │  - Attach: PDF download URL (signed GCS URL)           │               │
│  │  - Attach: relevance score + matched section type      │               │
│  └──────────────────────┬───────────────────────────────┘               │
│                         │                                               │
│                         ▼                                               │
│  ┌──────────────────────────────────────────────────────┐               │
│  │  SearchResponse                                       │               │
│  │  {                                                     │               │
│  │    "results": [                                        │               │
│  │      {                                                 │               │
│  │        "case_name": "Arnesh Kumar v. State of Bihar",  │               │
│  │        "citation": "(2014) 8 SCC 273",                 │               │
│  │        "court": "Supreme Court of India",              │               │
│  │        "score": 0.94,                                  │               │
│  │        "snippet": "...",                               │               │
│  │        "section": "ratio_decidendi",                   │               │
│  │        "metadata": { ... }                             │               │
│  │      },                                                │               │
│  │      ...                                               │               │
│  │    ],                                                  │               │
│  │    "query_understanding": { ... },                     │               │
│  │    "total_candidates": 847,                            │               │
│  │    "latency_ms": 620                                   │               │
│  │  }                                                     │               │
│  └──────────────────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────────────────┘
```

### Latency Budget

| Stage | Target | Notes |
|-------|--------|-------|
| Query Understanding | 200-400ms | Gemini structured output, cached for repeated queries |
| Embedding | 50-100ms | Single vector, Gemini text-embedding-004 |
| Vector Search (Pinecone) | 50-100ms | Serverless, ~20ms p50 |
| FTS Search (PostgreSQL) | 20-50ms | GIN index on tsvector column |
| Metadata Filter (PostgreSQL) | 10-20ms | B-tree indexes on court, year, case_type |
| RRF Merge | <5ms | In-memory sort |
| Cohere Rerank | 200-400ms | Network round-trip + model inference |
| Metadata Enrichment | 20-50ms | Batch PostgreSQL query |
| **Total** | **550-1125ms** | **Target p95 < 1.5s** |

---

## Vector DB Design (Pinecone)

### Index Configuration

| Property | Value | Rationale |
|----------|-------|-----------|
| Index name | `smriti-legal` | Single index for all legal documents |
| Namespace | Not used (single namespace) | Simplicity; filtering via metadata sufficient |
| Dimensions | 768 | Gemini text-embedding-004 output dimensionality |
| Metric | Cosine | Standard for text similarity; normalized embeddings |
| Pod type | Serverless (starter) | Cost-effective for MVP; scales automatically |

### Vector Record Schema

Each vector in Pinecone represents a single chunk of a legal document:

```json
{
  "id": "case_12345_chunk_003",
  "values": [0.0234, -0.0891, ...],   // 768 floats
  "metadata": {
    "doc_id": "case_12345",
    "case_id": "2024-SC-CrlA-1234",
    "court": "supreme_court",
    "year": 2024,
    "case_type": "criminal_appeal",
    "section_type": "ratio_decidendi",
    "chunk_index": 3
  }
}
```

### Metadata Fields for Filtering

| Field | Type | Filterable | Values |
|-------|------|-----------|--------|
| `doc_id` | string | Yes | Unique document identifier |
| `case_id` | string | Yes | Court-assigned case number |
| `court` | string | Yes | `supreme_court`, `delhi_hc`, `bombay_hc`, ... |
| `year` | integer | Yes | 1950-2026 |
| `case_type` | string | Yes | `criminal_appeal`, `writ_petition`, `civil_appeal`, ... |
| `section_type` | string | Yes | `facts`, `ratio_decidendi`, `order`, `arguments`, ... |
| `chunk_index` | integer | No | Sequential index within document |

### Query Patterns

**Basic semantic search with filters:**
```python
results = await pinecone_index.query(
    vector=query_embedding,
    top_k=20,
    filter={
        "court": {"$eq": "supreme_court"},
        "year": {"$gte": 2020},
    },
    include_metadata=True,
)
```

**Section-specific search** (e.g., only search in Ratio Decidendi):
```python
results = await pinecone_index.query(
    vector=query_embedding,
    top_k=20,
    filter={
        "section_type": {"$eq": "ratio_decidendi"},
    },
    include_metadata=True,
)
```

**Multi-filter search:**
```python
results = await pinecone_index.query(
    vector=query_embedding,
    top_k=20,
    filter={
        "$and": [
            {"court": {"$eq": "supreme_court"}},
            {"year": {"$gte": 2015}},
            {"case_type": {"$in": ["criminal_appeal", "special_leave_petition"]}},
        ]
    },
    include_metadata=True,
)
```

### Capacity Planning

| Metric | Estimate (MVP) | Estimate (1 Year) |
|--------|----------------|-------------------|
| Total documents | 10,000 cases | 100,000 cases |
| Avg chunks per document | 15 | 15 |
| Total vectors | 150,000 | 1,500,000 |
| Storage per vector | 768 * 4 bytes = ~3 KB | ~3 KB |
| Total vector storage | ~450 MB | ~4.5 GB |
| Metadata per vector | ~200 bytes | ~200 bytes |
| Total metadata storage | ~30 MB | ~300 MB |

Pinecone serverless (starter tier) supports up to 2 million vectors at no cost, which covers the first year of operation.

---

## Caching Strategy

### Redis Cache Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     Upstash Redis                         │
│                  (Serverless, REST API)                    │
│                                                           │
│  ┌─────────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │  Search Cache    │  │  Session     │  │  Rate Limit │ │
│  │                  │  │  Store       │  │  Counters   │ │
│  │  Key: hash of    │  │              │  │             │ │
│  │  query + filters │  │  Key:        │  │  Key:       │ │
│  │                  │  │  session:    │  │  rl:user:   │ │
│  │  TTL: 1 hour     │  │  {user_id}  │  │  {user_id}  │ │
│  │                  │  │              │  │             │ │
│  │  Value:          │  │  TTL: 24h    │  │  TTL: 60s   │ │
│  │  SearchResponse  │  │              │  │             │ │
│  │  (JSON)          │  │  Value:      │  │  Value:     │ │
│  │                  │  │  user data   │  │  sorted set │ │
│  └─────────────────┘  └──────────────┘  └─────────────┘ │
└──────────────────────────────────────────────────────────┘
```

### Cache Key Generation

```python
import hashlib
import json

def make_cache_key(query: str, filters: dict | None) -> str:
    """
    Deterministic cache key from query + filters.

    Sorted JSON ensures {"court": "SC", "year": 2020}
    and {"year": 2020, "court": "SC"} produce the same key.
    """
    payload = {
        "q": query.strip().lower(),
        "f": filters or {},
    }
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    hash_hex = hashlib.sha256(serialized.encode()).hexdigest()[:16]
    return f"search:{hash_hex}"
```

### Cache Flow

```
             Search Request
                  │
                  ▼
         ┌────────────────┐
         │  Generate       │
         │  cache key      │
         └───────┬────────┘
                 │
                 ▼
         ┌────────────────┐     HIT     ┌──────────────┐
         │  Redis GET      │────────────►│  Return       │
         │  (cache key)    │             │  cached       │
         └───────┬────────┘             │  response     │
                 │ MISS                  └──────────────┘
                 ▼
         ┌────────────────┐
         │  Execute full   │
         │  search pipeline│
         └───────┬────────┘
                 │
          ┌──────┼──────┐
          ▼             ▼
   ┌────────────┐ ┌──────────────┐
   │  Return     │ │  Redis SET   │
   │  response   │ │  (key, resp, │
   │  to client  │ │   TTL=3600)  │
   └────────────┘ └──────────────┘
```

### Cache Invalidation

**On new document ingestion:**

When a new document is ingested, cached search results may become stale. The invalidation strategy is:

```python
async def invalidate_search_cache(metadata: CaseMetadata) -> int:
    """
    Invalidate search cache entries that could be affected by
    the newly ingested document.

    Strategy: Clear all search cache entries.
    This is simple and correct. At MVP scale (< 100 searches/hour cached),
    the cost of re-executing a few searches is negligible compared to
    the complexity of selective invalidation.

    Future optimization: Selective invalidation based on document metadata
    (e.g., only clear caches where court/year filters match the new document).
    """
    pattern = "search:*"
    keys = await redis.keys(pattern)
    if keys:
        deleted = await redis.delete(*keys)
        return deleted
    return 0
```

### What Is NOT Cached

| Resource | Reason |
|----------|--------|
| Chat responses | Every response is contextual and unique |
| Ingestion results | One-time operation, no repeat reads |
| Auth tokens | Stored in client; server validates via signature |
| Graph traversals | Complex, varied queries; cache hit rate too low |
| PDF downloads | Served via signed GCS URLs (GCS handles its own CDN) |

### Cache Metrics

The following metrics are tracked to monitor cache effectiveness:

```python
# Exported as Prometheus metrics (future) or logged
CACHE_HITS = 0
CACHE_MISSES = 0
CACHE_EVICTIONS = 0
CACHE_INVALIDATIONS = 0
AVG_CACHED_RESPONSE_MS = 0    # Target: < 50ms
AVG_UNCACHED_RESPONSE_MS = 0  # Target: < 1500ms
```

---

*This document describes Smriti's high-level design as of March 2026. For system architecture overview, see [ARCHITECTURE.md](./ARCHITECTURE.md).*
