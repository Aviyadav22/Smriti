# Chapter 2: Teaching Smriti to Read

---

Supreme Court judgments arrive as PDFs. Some are clean, machine-readable text. Some are scanned images from the 1950s. Some are a bizarre mix of both — clean text with a few pages that are just photos of typewritten pages.

Before Smriti could understand anything, she had to learn to *read* these documents. This turned out to be one of the hardest problems in the entire project.

---

## Step 1: Cracking Open the PDF

The first approach was simple: use a PDF library (PyMuPDF) to extract text. For modern PDFs, this works great. Open the file, read each page, get the text. Done.

But Indian court judgments are... special.

**Problem 1: Invisible garbage characters.**
Many PDFs contain zero-width characters — invisible bytes that mess up text processing. You can't see them, but they're there, breaking word boundaries and confusing NLP models.

**Solution:** NFKC normalization + zero-width character removal. Run every character through Unicode normalization, then strip anything invisible.

**Problem 2: Headers and footers everywhere.**
Every page has "SUPREME COURT OF INDIA" at the top and a page number at the bottom. When you extract text, these repeat on every single page, cluttering the output.

**Solution:** Header/footer deduplication. If the same line appears on more than half the pages, it's probably a header or footer — strip it.

**Problem 3: Page breaks split sentences.**
A sentence might start on page 12 and end on page 13. Naive extraction gives you two broken fragments.

**Solution:** Smart page joining. Look at the end of each page — if it ends mid-sentence (no period, no paragraph break), merge it with the next page.

---

## Step 2: When Text Extraction Fails — OCR to the Rescue

Some pages have no extractable text at all. They're scanned images. The PDF library returns empty strings, or worse, garbled nonsense.

This is where OCR (Optical Character Recognition) comes in. OCR looks at the *image* of a page and reads the text from it — like a human would.

**The clever part**: Smriti doesn't OCR everything. That would be slow and expensive. Instead, it checks each page:

1. Try normal text extraction first
2. If a page returns too little text (suspiciously short for a court judgment page), flag it
3. Only OCR the flagged pages (max 20 pages to avoid runaway costs)
4. Merge OCR results back with the normally-extracted text

This **per-page OCR fallback** means Smriti handles mixed PDFs gracefully — pages 1-50 might be clean text, pages 51-53 might be scanned appendices, and that's fine.

---

## Step 3: Quality Scoring

Not all text extraction is equal. A clean modern PDF gives high-quality text. A 1950s scanned judgment gives... okay text at best.

Smriti scores each document's extraction quality:

- **Character count** — How much text did we get?
- **Legal keyword count** — Does the text contain words like "petitioner," "respondent," "held," "Section"? (If not, something went wrong)
- **OCR used** — Was fallback OCR needed? (Lower confidence)
- **Page map** — Which pages were OCR'd vs. normally extracted

This quality score travels with the document forever. Later stages can decide how much to trust the extraction.

```
Quality Tiers:
  HIGH   — Clean extraction, many legal keywords, no OCR needed
  MEDIUM — Some OCR pages, reasonable keyword count
  LOW    — Heavy OCR, few keywords, possible garbled text
```

---

## Step 4: Text Cleaning

Even after extraction and OCR, the text needs cleaning:

1. **Normalize whitespace** — Multiple spaces → single space, weird tabs → spaces
2. **Fix encoding issues** — Sometimes "Section" becomes "Secfion" (OCR mistake with 't')
3. **Remove artifacts** — Page numbers embedded in text, watermarks, scan artifacts
4. **Paragraph detection** — Figure out where paragraphs actually begin and end

The result is clean, readable text that's ready for the next stage — understanding *what* the judgment actually says.

---

## The Journey of a Single Judgment

Let's follow one judgment through the pipeline:

```
1. PDF arrives: "2024_INSC_0142.pdf" (35 pages)

2. Text extraction:
   - Pages 1-32: Clean text ✓
   - Pages 33-35: Scanned appendix → OCR fallback ✓

3. Cleaning:
   - Removed "SUPREME COURT OF INDIA" from 35 pages
   - Removed page numbers
   - NFKC normalized
   - Zero-width chars stripped

4. Quality score:
   - Char count: 52,340
   - Legal keywords: 847
   - OCR pages: 3 of 35
   - Tier: HIGH

5. Output: Clean text ready for metadata extraction
```

This might seem like a lot of work just to read a PDF. But remember — garbage in, garbage out. If the text extraction is bad, everything that follows (metadata, embeddings, search, the research agent) will be bad too.

Getting this right was non-negotiable.

---

## What Changed Over Time

The text extraction module evolved through three major versions:

**V1 (March 4):** Basic PyMuPDF extraction. No OCR. No cleaning. Worked for clean PDFs, failed on anything else.

**V2 (March 20):** Added OCR fallback, header/footer dedup, quality scoring. Handled 90% of documents.

**V3 (March 23):** Per-page OCR (not whole-document), smart page joining, NFKC normalization, zero-width char removal. Handles 99%+ of documents.

Each version was born from real failures — documents that came out garbled, judgments where the "HELD" section was missing because it was on a scanned page, cases where invisible characters made two identical-looking texts compare as different.

---

> **Next: [Chapter 3 — Understanding What She Reads →](./03-understanding-what-she-reads.md)**
>
> *Where AI meets regex, and Smriti learns to extract the who, what, when, and why of every judgment.*

---

### In the Code

| What | Where |
|------|-------|
| PDF extraction & quality scoring | `backend/app/core/ingestion/pdf.py` → `extract_and_score()` |
| Text cleaning & normalization | `backend/app/core/ingestion/pdf.py` |
| OCR fallback logic | `backend/app/core/ingestion/pdf.py` (per-page, max 20 pages) |
| Quality tiers | `backend/app/core/ingestion/pdf.py` → quality object |
| Full ingestion pipeline | [backend/app/core/ingestion/pipeline.py](../../backend/app/core/ingestion/pipeline.py) |
