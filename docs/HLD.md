# Smriti — High-Level Design (HLD)

> Detailed module-level design for India's legal research platform.

---

## Table of Contents

1. [Module Breakdown](#module-breakdown)
   - [Search Module](#1-search-module-coresearch)
   - [Ingestion Module](#2-ingestion-module-coreingestion)
   - [Legal Module](#3-legal-module-corelegal)
   - [Graph Module](#4-graph-module-coregraph)
   - [Security Module](#5-security-module-security)
   - [Agent Module](#6-agent-module-coreagents)
   - [Drafting Module](#7-drafting-module-coredrafting)
   - [Document Analysis Pipeline](#8-document-analysis-pipeline-tasksdocument_taskspy-apiroutesdocumentspy)
   - [Audio Digest Pipeline](#9-audio-digest-pipeline-apiroutesaudiopy-tasksaudio_taskspy)
   - [DPDP Compliance Module](#10-dpdp-compliance-module-apiroutesdpdppy)
   - [Admin Module](#11-admin-module-apiroutesadmin_correctionspy-admin_reviewpy-data_qualitypy)
   - [Scripts](#12-scripts-scripts)
   - [API Module (Complete Route Inventory)](#13-api-module-apiroutes)
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
    1. Try pdfplumber for native text extraction.
    2. If extracted text is too short (< 100 chars per page), assume scanned PDF.
    3. Fall back to Tesseract OCR on rendered page images.
    """

    MIN_CHARS_PER_PAGE = 100

    async def extract(self, pdf_bytes: bytes) -> str:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            text_pages = []

            for page in pdf.pages:
                text = page.extract_text() or ""
                if len(text.strip()) >= self.MIN_CHARS_PER_PAGE:
                    text_pages.append(text)
                else:
                    # OCR fallback
                    img = page.to_image(resolution=300).original
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

**Purpose**: Handle authentication, authorization, rate limiting, field-level encryption, audit logging, input sanitization, and DPDP Act compliance.

**Responsibilities**:
- JWT token issuance, validation, revocation, and rotation (access + refresh tokens)
- Password hashing with bcrypt (configurable cost factor)
- Role-based access control (RBAC) via FastAPI dependencies
- Per-endpoint sliding-window rate limiting (Redis-backed with in-memory fallback)
- AES-256-GCM field-level encryption for PII
- Comprehensive audit logging with IP hashing for DPDP compliance
- Input sanitization and LLM prompt injection detection
- DPDP Act consent management (inline in auth flow)

**Submodules**:

#### `auth.py` — JWT Authentication

Implements the access + refresh token pattern using PyJWT with HS256 signing. Tokens include `sub` (user_id), `role`, `type`, `jti` (unique token ID), `iss` ("smriti"), and `aud` ("smriti-api") claims. Access tokens default to `settings.jwt_access_token_expire_minutes`; refresh tokens default to `settings.jwt_refresh_token_expire_days`.

Token revocation is Redis-backed: revoked JTIs are stored with auto-expiry matching the token's remaining lifetime. Revocation checks are **fail-closed** — if Redis is unreachable, the token is treated as revoked.

```python
@dataclass(frozen=True, slots=True)
class TokenPayload:
    """Decoded JWT token payload."""
    sub: str   # user_id
    role: str
    exp: datetime
    iat: datetime
    jti: str   # unique token ID for revocation

# Key functions:
create_access_token(user_id, role, expires_delta?) -> str
create_refresh_token(user_id, expires_delta?) -> str
verify_access_token(token) -> TokenPayload
verify_refresh_token(token) -> TokenPayload
revoke_token(jti, exp_timestamp?) -> None
is_token_revoked(jti) -> bool
hash_password(password) -> str       # bcrypt with configurable cost factor
verify_password(plain, hashed) -> bool
```

#### `rbac.py` — Role-Based Access Control

Provides FastAPI dependency functions that extract the current user from the Bearer token and enforce role-based authorization.

```python
# Extract authenticated user (required)
get_current_user(token) -> TokenPayload

# Extract authenticated user (optional — returns None if no token)
get_current_user_optional(token?) -> TokenPayload | None

# Factory: create a dependency that requires specific role(s)
require_role(*roles) -> Callable
# Usage: Depends(require_role("admin"))
# Usage: Depends(require_role("admin", "editor"))
```

#### `rate_limiter.py` — Sliding Window Rate Limiting

Redis-backed sliding window rate limiter using sorted sets. Each request's timestamp is added to a per-key sorted set; expired entries are pruned on every check. Keys follow the pattern `rate:{client_ip}:{endpoint}`.

Features:
- Human-readable limit strings: `"100/minute"`, `"5/hour"`, `"1000/day"`
- In-memory fallback when Redis is unavailable (thread-safe, auto-clears at 10K buckets)
- Per-endpoint configurable via `rate_limit_dependency("60/minute")` FastAPI dependency

```python
# FastAPI dependency factory
rate_limit_dependency(limit: str) -> Callable
# Usage: @router.get("/search", dependencies=[Depends(rate_limit_dependency("30/minute"))])
```

#### `encryption.py` — AES-256-GCM Field-Level Encryption

Symmetric encryption for sensitive database fields (PII, API keys) using the `cryptography` library's AESGCM implementation. The encryption key is configured via `settings.encryption_key` (64-char hex string or base64-encoded 32-byte key).

Output format: base64-encoded concatenation of `nonce (12 bytes) + ciphertext + tag (16 bytes)`.

```python
encrypt_field(plaintext: str) -> str       # Encrypt a field value
decrypt_field(ciphertext: str) -> str      # Decrypt a field value
safe_decrypt(value: str) -> str            # Decrypt if encrypted, return as-is if plaintext
                                           # (migration safety for pre-existing plaintext)
```

#### `audit.py` — Audit Logging

Records security-sensitive user actions to the `audit_logs` PostgreSQL table. IP addresses are **hashed** (SHA-256, truncated to 16 hex chars, salted with encryption_key) before storage — raw IP addresses are never persisted, ensuring DPDP compliance.

```python
async def create_audit_log(
    db, action, user_id, resource_type, resource_id,
    ip_address?, user_agent?, metadata?
) -> None
# Actions: "login", "search", "document.view", "document.delete",
#          "admin.delete_user", "metadata.correction", etc.
```

#### `sanitizer.py` — Input Sanitization and Prompt Injection Detection

Provides three tiers of input cleaning:

1. **`sanitize_input(text)`** — Strips HTML tags, null bytes, and control characters while preserving normal whitespace.
2. **`sanitize_search_query(query)`** — All of the above plus removes known LLM prompt injection markers (25+ patterns including `"ignore previous instructions"`, `"jailbreak"`, `"DAN mode"`, ChatML tokens like `<|im_start|>`) and role-switching patterns.
3. **`detect_prompt_injection(text)`** — Boolean detection of injection attempts via marker matching, role-switching patterns, and excessive special character ratio (>15% threshold).

#### `consent.py` — Consent Management

Consent recording is handled inline during user registration in `auth.py`. The `consents` table tracks consent type, version, grant timestamp, and revocation timestamp. Consent status is queried and managed via the DPDP API endpoints.

**Dependencies**: PostgreSQL, Redis (Upstash), PyJWT, bcrypt, `cryptography` (AESGCM)

---

### 6. Agent Module (`core/agents/`)

**Purpose**: Execute multi-step legal research workflows using LangGraph StateGraph, with human-in-the-loop checkpoints and real-time SSE streaming.

**Responsibilities**:
- Orchestrate complex legal tasks as directed node graphs
- Pause execution at checkpoints for human review/approval
- Stream real-time progress updates via SSE
- Track execution history in PostgreSQL
- Retry external provider calls with Tenacity

**Agent Types**:

| Agent | Description | Node Graph |
|-------|------------|------------|
| `research` | Precedent research | query_expand -> search_precedents -> analyze_results -> (checkpoint) -> synthesize |
| `case_prep` | Issue analysis + deep search | extract_issues -> score_issues -> (checkpoint) -> deep_search per issue -> compile |
| `strategy` | Legal strategy + risk analysis | analyze_position -> identify_risks -> (checkpoint) -> develop_arguments -> verify_citations |
| `drafting` | Document generation + citation verification | select_template -> generate_draft -> (checkpoint) -> verify_citations -> finalize |

**Key Structure**:

```
core/agents/
├── graphs/              # LangGraph StateGraph definitions per agent type
├── nodes/               # Pure async node functions (partial state dicts)
│   └── research_nodes.py
└── ...
```

#### Agent Graph Construction

Each agent is built as a LangGraph `StateGraph`. Nodes are pure async functions that receive the current state and return a partial state dict, which is merged into the graph state. Dependencies (LLM, search, graph store) are captured via closures at graph construction time.

```python
# Simplified agent graph construction
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

def build_research_graph(llm, search, graph_store):
    graph = StateGraph(ResearchState)

    async def query_expand(state: ResearchState) -> dict:
        expanded = await llm.expand_query(state["query"])
        return {"expanded_queries": expanded}

    async def search_precedents(state: ResearchState) -> dict:
        results = await search.hybrid_search(state["expanded_queries"])
        return {"search_results": results}

    async def analyze_results(state: ResearchState) -> dict:
        analysis = await llm.analyze(state["search_results"])
        return {"analysis": analysis, "__interrupt__": True}  # checkpoint

    async def synthesize(state: ResearchState) -> dict:
        memo = await llm.synthesize(state["analysis"], state["human_feedback"])
        return {"memo": memo}

    graph.add_node("query_expand", query_expand)
    graph.add_node("search_precedents", search_precedents)
    graph.add_node("analyze_results", analyze_results)
    graph.add_node("synthesize", synthesize)

    graph.set_entry_point("query_expand")
    graph.add_edge("query_expand", "search_precedents")
    graph.add_edge("search_precedents", "analyze_results")
    graph.add_edge("analyze_results", "synthesize")
    graph.add_edge("synthesize", END)

    return graph.compile(checkpointer=MemorySaver())
```

#### SSE Event Types

Agent execution streams events using the same `data: JSON\n\n` format as chat:

| Event Type | Purpose |
|-----------|---------|
| `status` | Execution state change (e.g., "Expanding queries...") |
| `progress` | Intermediate results or progress percentage |
| `checkpoint` | Human-in-the-loop prompt requiring user input |
| `memo` | Final or partial output document |
| `done` | Execution complete with summary |
| `error` | Error with details |

#### Execution Tracking

Agent executions are persisted to the `agent_executions` PostgreSQL table for history, auditing, and resume capability. Each execution records the agent type, input parameters, output, status, and timing.

**Dependencies**: LangGraph, Gemini 2.5 Pro (LLM), HybridSearchOrchestrator, GraphStore (Neo4j), PostgreSQL (execution tracking), Tenacity (retry)

---

### 7. Drafting Module (`core/drafting/`)

**Purpose**: Generate structured Indian legal documents from LLM-drafted content, with export to DOCX and PDF formats with proper legal formatting.

**Responsibilities**:
- Define structured templates for common Indian legal document types
- Export LLM-generated content to DOCX (python-docx) and PDF (ReportLab)
- Apply Indian legal formatting conventions (Times New Roman, 1-inch margins, numbered paragraphs, centered court headers)

**Submodules**:

#### `templates.py` — Legal Document Templates

Defines 7 immutable `DocumentTemplate` dataclasses, each specifying the document type, ordered section structure, required user-provided fields, statutory basis, court header template, and prompt key.

| Template | Display Name | Statutory Basis | Required Fields |
|----------|-------------|-----------------|-----------------|
| `bail_application` | Bail Application (S.439 CrPC) | Section 439, CrPC 1973 | accused_name, fir_number, police_station, offences_charged |
| `writ_petition_226` | Writ Petition (Art.226) | Article 226, Constitution | petitioner_details, respondent_details, fundamental_right_violated |
| `writ_petition_32` | Writ Petition (Art.32) | Article 32, Constitution | petitioner_details, respondent_details, fundamental_right_violated |
| `written_statement` | Written Statement (Order VIII CPC) | Order VIII, CPC 1908 | suit_number, plaintiff_claims |
| `legal_notice` | Legal Notice | Various | sender_name, sender_address, recipient_name, recipient_address |
| `appeal` | Appeal (Civil/Criminal) | Various | impugned_order_details, lower_court_name |
| `interim_application` | Interim Application | Various | main_case_number, relief_sought |

#### `export.py` — DOCX and PDF Export

Two async export functions that transform LLM-generated markdown/text content into properly formatted legal documents:

- **`export_to_docx(content, template, title?)`** — Produces DOCX with python-docx: Times New Roman 12pt body / 14pt headings / 16pt title, 1-inch margins, centered title, auto-numbered paragraphs under each heading, document metadata (author: "Smriti AI").
- **`export_to_pdf(content, template, title?)`** — Produces PDF with ReportLab: A4 page size, Times-Roman/Times-Bold fonts, same formatting conventions, XML-safe text escaping.

Both functions parse the content into `(heading, body_lines)` pairs using heading detection (markdown `#` headers and ALL-CAPS lines).

**Dependencies**: python-docx, ReportLab, DocumentTemplate definitions

---

### 8. Document Analysis Pipeline (`tasks/document_tasks.py`, `api/routes/documents.py`)

**Purpose**: Accept user-uploaded legal PDFs and run a multi-step async analysis pipeline via Celery, producing issue extraction, precedent mapping, counter-arguments, and a research memo.

**Responsibilities**:
- Upload and store PDF documents (50MB limit, magic byte validation, filename sanitization)
- Execute 7-step async analysis pipeline via Celery worker
- Chunk, embed, and index uploaded documents for search visibility
- Serve analysis results and research memos

**Analysis Pipeline Steps**:

```
Step 1: Extract text      — PDFParser (pdfplumber + OCR fallback)
Step 2: Identify issues    — DocumentAnalyzerService (Gemini LLM)
Step 3: Find precedents    — PrecedentMapperService (embed + vector search + rerank)
Step 4: Counter-arguments  — DocumentAnalyzerService (Gemini LLM)
Step 5: Research memo      — DocumentAnalyzerService (synthesize all findings)
Step 6: Index for search   — chunk_judgment() + GeminiEmbedder + Pinecone upsert
Step 7: Store results      — INSERT into document_analyses table
```

Status tracking: each step updates the document's `status` and `processing_step` fields in real-time (`extracting` -> `analyzing` -> `searching` -> `generating` -> `indexing` -> `completed` or `failed`).

The Celery task (`analyze_document`) has `max_retries=2` with 60-second retry delay for transient errors (ConnectionError, TimeoutError, OSError).

**API Endpoints** (prefix: `/api/v1/documents`):

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/upload` | Upload PDF for analysis (rate: 10/min) | Required |
| GET | `` | List user's documents (paginated) | Required |
| GET | `/{document_id}` | Document details + analysis results | Required |
| DELETE | `/{document_id}` | Delete document and analysis (audit logged) | Required |
| GET | `/{document_id}/memo` | Get research memo | Required |

**Dependencies**: Celery + Redis broker, PDFParser, DocumentAnalyzerService, PrecedentMapperService, GeminiLLM, GeminiEmbedder, PineconeStore, CohereReranker, GCS/local storage

---

### 9. Audio Digest Pipeline (`api/routes/audio.py`, `tasks/audio_tasks.py`)

**Purpose**: Generate spoken-word audio digests of case summaries using text-to-speech, supporting English and Hindi via Sarvam AI with MockTTS fallback for development.

**Responsibilities**:
- Queue async audio generation via Celery
- Generate case summary text and convert to speech
- Store and stream audio files (MP3) via storage provider
- Track generation status per case per language

**API Endpoints** (prefix: `/api/v1/cases`):

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/{case_id}/audio/generate` | Queue audio digest generation (en/hi) | Required |
| GET | `/{case_id}/audio/status` | Check availability (available/generating) | Public |
| GET | `/{case_id}/audio` | Stream MP3 audio file (rate: 10/min) | Public |

The generate endpoint is idempotent: if an audio digest already exists for the requested case+language, it returns `"already_exists"` without re-generating. If generation is in progress, it returns `"generating"`.

Audio files are stored via the storage provider (GCS in production, local filesystem in dev) and streamed to clients as chunked `audio/mpeg` responses.

**Dependencies**: Sarvam AI TTS (production) / MockTTS (dev), Celery + Redis broker, GCS/local storage, PostgreSQL (audio_digests table)

---

### 10. DPDP Compliance Module (`api/routes/dpdp.py`)

**Purpose**: Implement data subject rights under the Digital Personal Data Protection Act, 2023 (India's DPDP Act), providing endpoints for data inventory, erasure, and consent management.

**API Endpoints** (prefix: `/api/v1/dpdp`):

| Method | Path | Description | Auth | Rate Limit |
|--------|------|-------------|------|------------|
| GET | `/data-summary` | User's data inventory across all tables (DPDP Section 11) | Required | 20/min |
| POST | `/erasure` | Right to erasure — atomic deletion of all personal data (DPDP Section 12) | Required | 5/hour |
| POST | `/consent-withdraw` | Withdraw data processing consent (DPDP Section 6) | Required | 10/hour |
| GET | `/consent-status` | Current consent status (type, version, grant/revoke dates) | Required | — |

**Erasure Flow**: All deletions are performed within a single nested transaction for atomicity:
1. Delete agent executions
2. Delete chat messages and sessions
3. Delete documents (CASCADE handles document_analyses)
4. Delete consents
5. Log erasure to `dpdp_audit_log` (retained for compliance)
6. Deactivate user account (`is_active = false`)

**Dependencies**: PostgreSQL (6 tables queried: chat_sessions, chat_messages, documents, agent_executions, audit_logs, consents)

---

### 11. Admin Module (`api/routes/admin_corrections.py`, `admin_review.py`, `data_quality.py`)

**Purpose**: Provide admin-only tools for metadata corrections, editorial review of ingested cases, and data quality monitoring.

**All endpoints require `admin` role** (enforced via `require_role("admin")` dependency).

#### Admin Corrections (`/api/v1/admin/corrections`)

Allows administrators to fix metadata errors on individual cases while maintaining a full audit trail of what changed, who changed it, and why.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/{case_id}/correct` | Correct a single metadata field with audit trail |
| GET | `/{case_id}/history` | Get correction history from audit logs |

Correctable fields: 25 scalar fields (title, citation, court, year, decision_date, case_type, jurisdiction, bench_type, petitioner, respondent, author_judge, disposal_nature, ratio_decidendi, case_number, headnotes, outcome_summary, coram_size, lower_court, lower_court_case_number, appeal_from, opinion_type, split_ratio, petitioner_type, respondent_type, is_pil) plus 7 array fields (judge, acts_cited, cases_cited, keywords, dissenting_judges, concurring_judges, companion_cases).

Each correction: records old value, new value, reason, and corrected_by in `audit_logs`; updates `metadata_provenance` to mark the field as `"admin_corrected"`.

#### Admin Review Queue (`/api/v1/admin/review`)

HITL review queue for cases flagged during ingestion (low confidence, missing critical fields, or explicit `needs_review`/`failed` status).

| Method | Path | Description |
|--------|------|-------------|
| GET | `` | List cases needing review (filterable, sortable, paginated) |
| GET | `/{case_id}` | Full case detail with provenance for review |
| POST | `/{case_id}/approve` | Mark case as reviewed (sets `ingestion_status='complete'`) |
| POST | `/{case_id}/reject` | Reject case for re-ingestion (sets `ingestion_status='rejected'`) |

#### Data Quality Dashboard (`/api/v1/admin/data-quality`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `` | Comprehensive data quality metrics |

Returns: total case count, ingestion status breakdown, per-field population rates (25 scalar + 7 array fields), average non-null metadata fields per case, and citation resolution statistics.

**Dependencies**: PostgreSQL, audit_logs table, require_role("admin")

---

### 12. Scripts (`scripts/`)

**Purpose**: Standalone CLI scripts for data ingestion, graph population, verification, and benchmarking. Designed for both manual execution and automated scheduling (cron, Cloud Scheduler).

#### `ingest_s3.py` — S3 Bulk Ingestion

Downloads Indian Supreme Court judgments from the AWS Open Data bucket (`s3://indian-supreme-court-judgments/`) and runs the full ingestion pipeline for each judgment.

- **Queue-based workers**: Parallel processing with configurable worker count
- **Circuit breaker**: Halts after 10 consecutive failures to prevent cascading errors
- **Graceful shutdown**: Handles SIGINT/SIGTERM for clean worker termination
- **SQLite tracking**: Local `data/ingest_tracker.db` tracks processed files for resume capability
- **Retry**: Tenacity exponential backoff (2-60s, 5 attempts) on downloads and API calls
- **Multi-key support**: Rotates across multiple Gemini API keys (`GEMINI_API_KEYS` env var) for throughput
- **ETA logging**: Estimates remaining time based on processing rate

```bash
python scripts/ingest_s3.py --year 2024              # Single year
python scripts/ingest_s3.py --year-from 2020 --year-to 2024  # Year range
python scripts/ingest_s3.py --resume                  # Resume from last checkpoint
python scripts/ingest_s3.py --year 2024 --limit 100   # Limit count
```

#### `populate_neo4j.py` — Citation Graph Population

Reads all cases from PostgreSQL and builds the full Neo4j citation graph:
- **Case nodes**: id, title, citation, court, year, case_type, bench_type, etc.
- **CITES edges**: Between cases based on `cases_cited` arrays
- **Act nodes + INTERPRETS edges**: From `acts_cited` arrays
- **Judge nodes + DECIDED_BY/AUTHORED_BY edges**: From judge and author_judge fields

```bash
python scripts/populate_neo4j.py               # Full run
python scripts/populate_neo4j.py --batch 500   # Custom batch size
python scripts/populate_neo4j.py --dry-run     # Preview without writing
python scripts/populate_neo4j.py --stats       # Show current Neo4j stats
```

#### `daily_ingest.py` — Scheduled Daily Ingestion

Wrapper for cron/Cloud Scheduler that runs incremental ingestion for the current year, then populates Neo4j. Designed for `cron` or Cloud Run Jobs.

```bash
python scripts/daily_ingest.py                # Current year, resume mode
python scripts/daily_ingest.py --year 2024    # Specific year
python scripts/daily_ingest.py --full         # All years (initial load)
```

#### `verify_ingestion.py` — Post-Ingestion Verification

Cross-store consistency checker that samples cases from PostgreSQL and verifies their presence in Pinecone (vector store) and Neo4j (graph). Reports mismatches, missing vectors, graph gaps, and FTS index issues.

```bash
python scripts/verify_ingestion.py             # Default 100 sample
python scripts/verify_ingestion.py --sample 50 # Custom sample size
```

#### `benchmark_extraction.py` — Metadata Extraction Benchmarking

Evaluates the metadata extraction pipeline against a gold-standard dataset of manually verified cases. Computes per-field precision and recall for 18 scalar fields and 4 list fields.

```bash
python scripts/benchmark_extraction.py --gold-dir data/gold_standard/
python scripts/benchmark_extraction.py --gold-dir data/gold_standard/ --fields title,citation,year
```

**Dependencies**: PostgreSQL, Pinecone, Neo4j, Gemini API, PyArrow (Parquet), Tenacity, asyncpg

---

### 13. API Module (`api/routes/`)

**Purpose**: HTTP interface layer. 15 route modules exposing 61+ endpoints. Thin route handlers that delegate to core service classes.

**Responsibilities**:
- Request validation (Pydantic models)
- Authentication and authorization (via dependencies)
- Rate limiting (per-endpoint configurable)
- Route to appropriate service
- Format and return responses
- Handle errors consistently

**Complete Route Inventory (15 files)**:

#### 1. `AuthRouter` (`api/routes/auth.py`) — Prefix: `/api/v1/auth`

| Method | Path | Description | Auth | Rate Limit |
|--------|------|-------------|------|------------|
| POST | `/register` | Create account (DPDP consent required) | Public | 5/min |
| POST | `/login` | Login, return access + refresh tokens | Public | 5/min |
| POST | `/refresh` | Refresh access token | Public (refresh token) | 10/min |
| POST | `/logout` | Revoke tokens | Required | 20/min |
| DELETE | `/me` | Delete account (DPDP right to erasure) | Required | — |

Password validation enforces: 8+ chars, uppercase, lowercase, digit. Registration requires explicit `consent_given=true` for DPDP compliance.

#### 2. `SearchRouter` (`api/routes/search.py`) — Prefix: `/api/v1/search`

| Method | Path | Description | Auth | Rate Limit |
|--------|------|-------------|------|------------|
| GET | `` | Hybrid search (vector + FTS + RRF + rerank) | Optional | 30/min |
| GET | `/suggest` | Autocomplete suggestions | Optional | 60/min |
| GET | `/facets` | Available filter facets | Optional | 30/min |

Search supports 9 filter parameters: `court`, `year_from`, `year_to`, `case_type`, `bench_type`, `judge`, `act`, `section`, and `language` (en/hi). Prompt injection detection is applied before query processing. Results are cached in Redis (1-hour TTL).

#### 3. `CaseRouter` (`api/routes/cases.py`) — Prefix: `/api/v1/cases`

| Method | Path | Description | Auth | Rate Limit |
|--------|------|-------------|------|------------|
| GET | `/{case_id}` | Full case metadata and text | Public | 60/min |
| GET | `/{case_id}/summary` | AI-generated case summary | Required | 30/min |
| GET | `/{case_id}/pdf` | Serve PDF document | Public | 30/min |
| GET | `/{case_id}/citations` | Cases cited by this case | Public | 60/min |
| GET | `/{case_id}/cited-by` | Cases citing this case | Public | 60/min |
| GET | `/{case_id}/similar` | Semantically similar cases | Optional | 20/min |

#### 4. `ChatRouter` (`api/routes/chat.py`) — Prefix: `/api/v1/chat`

| Method | Path | Description | Auth | Rate Limit |
|--------|------|-------------|------|------------|
| POST | `` | New chat session + first message (SSE stream) | Required | 20/min |
| POST | `/{session_id}/message` | Continue chat session (SSE stream) | Required | 20/min |
| GET | `/sessions` | List user's chat sessions | Required | — |
| GET | `/{session_id}/history` | Get session message history | Required | — |
| DELETE | `/{session_id}` | Delete chat session | Required | — |

Chat messages are encrypted at rest (AES-256-GCM). Prompt injection detection is applied before RAG processing.

#### 5. `AgentRouter` (`api/routes/agents.py`) — Prefix: `/api/v1/agents`

| Method | Path | Description | Auth | Rate Limit |
|--------|------|-------------|------|------------|
| POST | `/{agent_type}/run` | Start agent execution (SSE stream) | Required | 10/min |
| GET | `/executions` | List past agent executions | Required | — |
| GET | `/executions/{execution_id}` | Get execution details | Required | — |
| POST | `/executions/{execution_id}/resume` | Resume from HITL checkpoint | Required | 10/min |
| DELETE | `/executions/{execution_id}` | Cancel execution (sets status to cancelled) | Required | — |
| GET | `/drafting/templates` | List available document templates | Required | — |
| POST | `/drafting/export/{execution_id}` | Export draft to DOCX/PDF | Required | 20/min |

Agent types: `research`, `case_prep`, `strategy`, `drafting`. Active checkpointers are stored in a TTLCache (1-hour TTL, max 1024 entries) to prevent memory leaks from abandoned SSE connections.

#### 6. `GraphRouter` (`api/routes/graph.py`) — Prefix: `/api/v1/graph`

| Method | Path | Description | Auth | Rate Limit |
|--------|------|-------------|------|------------|
| GET | `/{case_id}/neighborhood` | Citation network (depth 1-3) | Optional | 30/min |
| GET | `/{case_id}/chain` | Forward citation chain (depth 1-5) | Optional | 30/min |
| GET | `/{case_id}/authorities` | Top authorities citing this case | Optional | 30/min |
| GET | `/stats` | Graph-wide statistics | Optional | 30/min |

#### 7. `DocumentRouter` (`api/routes/documents.py`) — Prefix: `/api/v1/documents`

| Method | Path | Description | Auth | Rate Limit |
|--------|------|-------------|------|------------|
| POST | `/upload` | Upload PDF for analysis | Required | 10/min |
| GET | `` | List user's documents (paginated) | Required | — |
| GET | `/{document_id}` | Document details + analysis | Required | — |
| DELETE | `/{document_id}` | Delete document (audit logged) | Required | — |
| GET | `/{document_id}/memo` | Get research memo | Required | — |

#### 8. `AudioRouter` (`api/routes/audio.py`) — Prefix: `/api/v1/cases`

| Method | Path | Description | Auth | Rate Limit |
|--------|------|-------------|------|------------|
| POST | `/{case_id}/audio/generate` | Queue audio digest (en/hi) | Required | — |
| GET | `/{case_id}/audio/status` | Check audio availability | Public | — |
| GET | `/{case_id}/audio` | Stream MP3 audio file | Public | 10/min |

#### 9. `IngestRouter` (`api/routes/ingest.py`) — Prefix: `/api/v1/ingest`

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| POST | `/upload` | Upload single PDF for ingestion | Admin |
| GET | `/status/{document_id}` | Check ingestion status | Admin |
| GET | `/dashboard/completeness` | Ingestion completeness dashboard | Admin |
| GET | `/review-queue` | List cases needing review | Admin |
| PATCH | `/cases/{case_id}/metadata` | Update case metadata | Admin |
| POST | `/cases/{case_id}/approve` | Approve case for publication | Admin |
| POST | `/cases/{case_id}/retry` | Retry failed ingestion | Admin |

#### 10. `JudgesRouter` (`api/routes/judges.py`) — Prefix: `/api/v1`

| Method | Path | Description | Auth | Rate Limit |
|--------|------|-------------|------|------------|
| GET | `/judges` | List judges with case counts | Public | 30/min |
| GET | `/judges/compare` | Compare judges side-by-side | Public | 30/min |
| GET | `/judges/{judge_name}` | Judge profile and analytics | Public | 30/min |
| GET | `/judges/{judge_name}/cases` | Cases by judge (paginated) | Public | 30/min |
| GET | `/courts/{court_name}/stats` | Court-level statistics | Public | 30/min |

Results are cached in Redis (1-hour TTL).

#### 11. `DPDPRouter` (`api/routes/dpdp.py`) — Prefix: `/api/v1/dpdp`

See [DPDP Compliance Module](#10-dpdp-compliance-module-apiroutesdpdppy) above.

#### 12. `HealthRouter` (`api/routes/health.py`) — No prefix

| Method | Path | Description | Auth | Rate Limit |
|--------|------|-------------|------|------------|
| GET | `/health` | Dependency health checks | Optional | 60/min |

Checks PostgreSQL, Redis, Pinecone, Neo4j, and Gemini in parallel (5-second per-check timeout). Returns minimal `{"status": "healthy"}` for unauthenticated callers; full dependency details for authenticated users. Returns 503 when critical dependencies (PostgreSQL) are down. Overall status: `healthy` (all up), `degraded` (non-critical down), `unhealthy` (critical down).

#### 13. `DataQualityRouter` (`api/routes/data_quality.py`) — Prefix: `/api/v1/admin/data-quality`

See [Admin Module](#11-admin-module-apiroutesadmin_correctionspy-admin_reviewpy-data_qualitypy) above.

#### 14. `AdminCorrectionsRouter` (`api/routes/admin_corrections.py`) — Prefix: `/api/v1/admin/corrections`

See [Admin Module](#11-admin-module-apiroutesadmin_correctionspy-admin_reviewpy-data_qualitypy) above.

#### 15. `AdminReviewRouter` (`api/routes/admin_review.py`) — Prefix: `/api/v1/admin/review`

See [Admin Module](#11-admin-module-apiroutesadmin_correctionspy-admin_reviewpy-data_qualitypy) above.

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
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ ┌────────┐ │ │
│  │  │  Search  │ │ Ingest   │ │  Chat    │ │  Graph │ │ Agents │ │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────┘ └────────┘ │ │
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

### SSE for Chat and Agent Streaming

Chat responses and agent executions use Server-Sent Events (SSE), not WebSockets. SSE is simpler, works through proxies and load balancers, and is sufficient for server-to-client streaming. Chat SSE includes citation verification events that confirm referenced cases exist and are accurately cited. Agent SSE uses the same `data: JSON\n\n` format with event types: `status`, `progress`, `checkpoint` (HITL), `memo`, `done`, and `error`.

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
│  │  QueryUnderstanding (Gemini 2.5 Pro)                  │               │
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
│  │    gemini-     │ │              │ │ WHERE court =    │              │
│  │    embedding   │ │ ts_rank_cd() │ │   'supreme_court'│              │
│  │    (1536 dims) │ │ for cover    │ │ AND year >= 2020 │              │
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
│  │  Cohere rerank-v4.0-pro                                     │               │
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
| Embedding | 50-100ms | Single vector, Gemini gemini-embedding-001 |
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
| Dimensions | 1536 | Gemini gemini-embedding-001 output dimensionality |
| Metric | Cosine | Standard for text similarity; normalized embeddings |
| Pod type | Serverless (starter) | Cost-effective for MVP; scales automatically |

### Vector Record Schema

Each vector in Pinecone represents a single chunk of a legal document:

```json
{
  "id": "case_12345_chunk_003",
  "values": [0.0234, -0.0891, ...],   // 1536 floats
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
| Storage per vector | 1536 * 4 bytes = ~6 KB | ~6 KB |
| Total vector storage | ~900 MB | ~9 GB |
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
