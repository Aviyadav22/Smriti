# Smriti — Indian Legal Domain Reference

> This is the domain knowledge cheat sheet. Every developer building Smriti should understand this document.

---

## 1. Indian Court Hierarchy

### Complete Structure

```
SUPREME COURT OF INDIA (New Delhi)
│   - Final appellate authority for all cases
│   - Decisions binding on ALL courts in India
│   - Original jurisdiction: inter-state disputes, fundamental rights (Art. 32)
│   - 34 judges including Chief Justice of India (CJI)
│
├── 25 HIGH COURTS (State-level appellate courts)
│   │   - Decisions binding on all courts within their territorial jurisdiction
│   │   - Writ jurisdiction under Article 226
│   │   - Appellate + Original jurisdiction
│   │
│   ├── Allahabad High Court         → Uttar Pradesh (bench at Lucknow)
│   ├── Bombay High Court            → Maharashtra, Goa, Dadra & Nagar Haveli, Daman & Diu
│   │                                   (benches at Nagpur, Aurangabad, Goa/Panaji)
│   ├── Calcutta High Court          → West Bengal (circuit bench at Port Blair for A&N Islands)
│   ├── Madras High Court            → Tamil Nadu, Puducherry (bench at Madurai)
│   ├── Delhi High Court             → NCT of Delhi
│   ├── Karnataka High Court         → Karnataka (benches at Dharwad, Kalaburagi)
│   ├── Kerala High Court            → Kerala, Lakshadweep
│   ├── Gujarat High Court           → Gujarat
│   ├── Rajasthan High Court         → Rajasthan (benches at Jaipur, Jodhpur)
│   ├── Patna High Court             → Bihar
│   ├── Punjab & Haryana High Court  → Punjab, Haryana, Chandigarh
│   ├── Andhra Pradesh High Court    → Andhra Pradesh (Amaravati)
│   ├── Telangana High Court         → Telangana (Hyderabad)
│   ├── Orissa High Court            → Odisha
│   ├── Jharkhand High Court         → Jharkhand
│   ├── Chhattisgarh High Court      → Chhattisgarh
│   ├── Uttarakhand High Court       → Uttarakhand
│   ├── Himachal Pradesh High Court  → Himachal Pradesh
│   ├── J&K and Ladakh High Court    → Jammu & Kashmir, Ladakh
│   ├── Gauhati High Court           → Assam, Nagaland, Mizoram, Arunachal Pradesh
│   ├── Tripura High Court           → Tripura
│   ├── Meghalaya High Court         → Meghalaya
│   ├── Manipur High Court           → Manipur
│   └── Sikkim High Court            → Sikkim
│
├── DISTRICT & SESSIONS COURTS
│   │   - One per district (700+ districts in India)
│   │   - District Judge (civil) / Sessions Judge (criminal)
│   │   - First appeal from subordinate courts
│   │
│   └── SUBORDINATE COURTS
│       ├── Civil Judge (Senior/Junior Division)
│       ├── Judicial Magistrate (First/Second Class)
│       ├── Chief Judicial Magistrate
│       ├── Small Causes Courts
│       └── Munsif Courts
│
└── TRIBUNALS & SPECIALIZED BODIES
    ├── NCLT  — National Company Law Tribunal (insolvency, mergers, corporate)
    ├── NCLAT — National Company Law Appellate Tribunal (appeals from NCLT + CCI)
    ├── SAT   — Securities Appellate Tribunal (SEBI appeals)
    ├── CAT   — Central Administrative Tribunal (government service disputes)
    ├── ITAT  — Income Tax Appellate Tribunal
    ├── CESTAT— Customs, Excise & Service Tax Appellate Tribunal
    ├── NGT   — National Green Tribunal (environmental)
    ├── TDSAT — Telecom Disputes Settlement Appellate Tribunal
    ├── AFT   — Armed Forces Tribunal
    ├── NCDRC — National Consumer Disputes Redressal Commission
    ├── SCDRC — State Consumer Disputes Redressal Commission
    └── DFC   — District Consumer Forum
```

### Bench Types (Precedent Weight)

| Bench | Composition | Authority |
|-------|------------|-----------|
| Constitution Bench | 5+ judges | Highest within SC; required for constitutional interpretation |
| Full Bench | 3+ judges (HC) | Highest within that HC |
| Division Bench | 2 judges | Overrides Single Judge |
| Single Judge | 1 judge | Lowest bench authority |

**Rule**: A larger bench's decision can only be overruled by an equal or larger bench. A Division Bench cannot overrule a Constitution Bench.

---

## 2. Citation Formats

### Format Catalog

| Format | Pattern | Example | Regex |
|--------|---------|---------|-------|
| **SCC** | (Year) Volume SCC Page | (2017) 10 SCC 1 | `\(\d{4}\)\s+\d+\s+SCC\s+\d+` |
| **SCC (Online)** | Year SCC OnLine SC Number | 2023 SCC OnLine SC 1500 | `\d{4}\s+SCC\s+OnLine\s+\w+\s+\d+` |
| **AIR** | AIR Year Court Page | AIR 2023 SC 100 | `AIR\s+\d{4}\s+\w+\s+\d+` |
| **INSC** (neutral) | Year INSC Number | 2023 INSC 1 | `\d{4}\s+INSC\s+\d+` |
| **SCR** | [Year] Volume SCR Page | [2023] 5 SCR 120 | `\[\d{4}\]\s+\d+\s+SCR\s+\d+` |
| **CrLJ** | Year CrLJ Page | 2023 CrLJ 4500 | `\d{4}\s+Cr\.?L\.?J\.?\s+\d+` |
| **Scale** | (Year) Volume SCALE Page | (2023) 2 SCALE 100 | `\(\d{4}\)\s+\d+\s+SCALE\s+\d+` |
| **BomLR** | Year BomLR Page | 2023 BomLR 200 | `\d{4}\s+Bom\.?L\.?R\.?\s+\d+` |
| **CalWN** | Year CalWN Page | 2023 CalWN 50 | `\d{4}\s+Cal\.?W\.?N\.?\s+\d+` |
| **MLJ** | (Year) Volume MLJ Page | (2023) 2 MLJ 100 | `\(\d{4}\)\s+\d+\s+MLJ\s+\d+` |
| **DLT** | Year DLT Page | 2023 DLT 300 | `\d{4}\s+DLT\s+\d+` |

### AIR Court Codes

| Code | Court |
|------|-------|
| SC | Supreme Court |
| All | Allahabad HC |
| Bom | Bombay HC |
| Cal | Calcutta HC |
| Del | Delhi HC |
| Mad | Madras HC |
| Kar | Karnataka HC |
| Ker | Kerala HC |
| Guj | Gujarat HC |
| Raj | Rajasthan HC |
| Pat | Patna HC |
| P&H | Punjab & Haryana HC |
| AP | Andhra Pradesh HC |
| Ori | Orissa HC |

### Normalization Rules

1. Always store the INSC neutral citation as canonical when available
2. One case can have multiple citations (SCC + AIR + INSC) — store all, index all
3. Normalize year format: always 4 digits
4. Store court name in full canonical form ("Supreme Court of India", not "SC")
5. When parsing, try all patterns in sequence — first match wins

---

## 3. Key Bare Acts & Statutory Framework

### New Criminal Laws (Effective July 1, 2024)

| Old Law | New Law | Key Changes |
|---------|---------|-------------|
| Indian Penal Code (IPC), 1860 | **Bharatiya Nyaya Sanhita (BNS)**, 2023 | 358 sections (was 511). New: organized crime (S.111), terrorism (S.113), mob lynching (S.103(2)) |
| Criminal Procedure Code (CrPC), 1973 | **Bharatiya Nagarik Suraksha Sanhita (BNSS)**, 2023 | 531 sections (was 484). Mandatory: Zero FIR, forensics for 7yr+ offenses, judgment within 45 days, charges within 60 days |
| Indian Evidence Act, 1872 | **Bharatiya Sakshya Adhiniyam (BSA)**, 2023 | 170 sections (was 167). Electronic evidence updated, mandatory video recording of search/seizure |

**Critical for search**: Old judgments cite IPC sections. System must map old → new:
- IPC Section 302 (murder) → BNS Section 103
- IPC Section 304 (culpable homicide) → BNS Section 105
- IPC Section 376 (rape) → BNS Section 63
- IPC Section 420 (cheating) → BNS Section 318
- IPC Section 498A (cruelty) → BNS Section 85

### Constitution of India

- **470 Articles** across 25 Parts + 12 Schedules
- **Key articles for legal research**:
  - Art. 14: Right to equality
  - Art. 19: Freedom of speech, assembly, movement, profession
  - Art. 21: Right to life and personal liberty (most litigated)
  - Art. 32: Right to Constitutional remedies (SC writs)
  - Art. 226: High Court writ jurisdiction
  - Art. 136: Special Leave Petition (SLP) to Supreme Court
  - Art. 141: Law declared by SC binding on all courts
  - Art. 142: Supreme Court's plenary powers
  - Art. 368: Amendment of Constitution
  - Art. 370: Special status of J&K (abrogated 2019)

### Other Key Statutes

| Statute | Sections | Domain |
|---------|----------|--------|
| Code of Civil Procedure (CPC), 1908 | 158 + 51 Orders | Civil litigation procedure |
| Companies Act, 2013 | 470 sections, 29 chapters | Corporate law, NCLT jurisdiction |
| Arbitration & Conciliation Act, 1996 | 86 sections | Dispute resolution |
| Information Technology Act, 2000 | 94 sections | Cyber law, electronic commerce |
| Consumer Protection Act, 2019 | 107 sections | Consumer rights, e-commerce |
| SEBI Act, 1992 | 35 sections | Securities regulation |
| Insolvency & Bankruptcy Code, 2016 | 255 sections | Corporate insolvency |
| Right to Information Act, 2005 | 31 sections | Government transparency |
| Prevention of Corruption Act, 1988 | 31 sections | Public servant corruption |
| NDPS Act, 1985 | 83 sections | Narcotics and drugs |
| PMLA, 2002 | 75 sections | Money laundering |

---

## 4. How Indian Lawyers Actually Research

### Daily Workflow

```
1. RECEIVE BRIEF from client or senior
   → Identify legal issues (what law applies? what facts matter?)

2. SEARCH FOR PRECEDENTS
   → Open IndianKanoon / SCC Online / Manupatra
   → Search by: section number, keywords, case name
   → Problem: keyword search misses semantically similar cases
   → Scroll through 50+ results hoping to find the right one

3. READ JUDGMENTS (The Bottleneck)
   → Open 5-10 potentially relevant PDFs
   → Read 20-200 pages EACH looking for ratio decidendi
   → No way to jump to the relevant section
   → Takes 2-4 hours for a single research task

4. ANALYZE & MAP
   → Check if found cases are still good law (not overruled?)
   → Manual citation checking — open each cited case
   → Map facts of precedent to client's facts
   → No tool helps with this comparison

5. DRAFT ARGUMENTS
   → Write legal arguments citing found precedents
   → Format citations correctly
   → Cross-reference with bare acts
```

### What Smriti Fixes

| Step | Current Pain | Smriti Solution |
|------|-------------|-----------------|
| Search | Keyword-only, misses semantic matches | Hybrid search (semantic + BM25 + metadata) |
| Read | 200 pages per judgment | Parsed sections, ratio highlighted |
| Analyze | Manual citation checking | Citation graph, "still good law?" indicator |
| Compare | No tool for fact comparison | RAG chat: "Compare this case to [my facts]" |
| Draft | Manual citation formatting | Correct citations auto-linked |

---

## 5. Indian Legal Terminology Glossary

### Court Parties & Roles

| Term | Definition | Context |
|------|-----------|---------|
| **Petitioner** | Party who files a petition (writ, SLP, etc.) | Writ jurisdiction |
| **Respondent** | Party opposing the petition | Writ jurisdiction |
| **Plaintiff** | Party who files a civil suit | Civil original jurisdiction |
| **Defendant** | Party against whom suit is filed | Civil original jurisdiction |
| **Appellant** | Party appealing a lower court decision | Appellate jurisdiction |
| **Complainant** | Person who lodges FIR/complaint | Criminal matters |
| **Accused** | Person charged with a crime | Criminal matters |
| **Amicus Curiae** | "Friend of the Court" — expert appointed to assist | Complex cases, PILs |
| **Intervenor** | Third party permitted to join proceedings | When their interests affected |

### Legal Professionals

| Term | Definition |
|------|-----------|
| **Advocate** | Enrolled with Bar Council, authorized to appear in court. Requires LLB + AIBE + enrollment |
| **Senior Advocate** | Designated by SC/HC for exceptional ability. Wears a different gown. Cannot appear without instructing advocate. |
| **Advocate on Record (AoR)** | Only advocates who can file cases in Supreme Court. Requires separate exam. |
| **Vakalatnama** | Written authority from client authorizing advocate to appear on their behalf |
| **Public Prosecutor** | Government-appointed advocate for criminal prosecution |
| **Amicus Curiae** | Court-appointed expert advocate to assist in complex matters |

### Criminal Procedure Terms

| Term | Definition |
|------|-----------|
| **FIR** (First Information Report) | Written police document when a cognizable offense is reported. Under BNSS: Zero FIR can be filed at any police station. |
| **Chargesheet** | Formal document filed by police after investigation concluding there's sufficient evidence to prosecute |
| **Cognizable offense** | Police can arrest without warrant and investigate without magistrate's order |
| **Non-cognizable offense** | Police need magistrate's order to investigate |
| **Bailable offense** | Accused has right to bail as a matter of right |
| **Non-bailable offense** | Bail at court's discretion |
| **Anticipatory bail** | Bail granted before arrest (Section 482 BNSS) |
| **Regular bail** | Bail granted after arrest |
| **Interim bail** | Temporary bail pending hearing |
| **Judicial custody** | Accused held in jail (not police station) |
| **Police custody** | Accused held at police station for interrogation (max 15 days under BNSS) |
| **Remand** | Court order sending accused to custody |

### Court Orders & Proceedings

| Term | Definition |
|------|-----------|
| **Stay order** | Temporary halt of proceedings or enforcement |
| **Injunction** | Court order prohibiting a party from specific action |
| **Ex-parte** | Proceeding conducted with only one party present |
| **In-camera** | Proceedings held in private (not open court) |
| **Adjournment** | Postponement of hearing to a later date |
| **Decree** | Formal expression of court's adjudication in a suit |
| **Order** | Formal expression that doesn't amount to a decree |
| **Judgment** | Statement of grounds for a decree or order |

### Five Constitutional Writs

| Writ | Meaning | Use |
|------|---------|-----|
| **Habeas Corpus** | "Produce the body" | Challenge unlawful detention |
| **Mandamus** | "We command" | Compel government official to perform duty |
| **Certiorari** | "To be certified" | Quash order of lower court/tribunal |
| **Prohibition** | "To forbid" | Prevent lower court from exceeding jurisdiction |
| **Quo Warranto** | "By what authority" | Challenge person's right to hold public office |

### Legal Doctrines & Principles

| Term | Definition |
|------|-----------|
| **Ratio decidendi** | The legal principle that forms the basis of the decision. Binding precedent. |
| **Obiter dicta** | Judge's remarks that are not essential to the decision. Persuasive, not binding. |
| **Stare decisis** | "Stand by decided matters" — principle of following precedent |
| **Per incuriam** | "Through lack of care" — decision made without considering relevant law. Can be disregarded. |
| **Sub judice** | "Under judgment" — matter currently before a court |
| **Res judicata** | "Matter already judged" — cannot relitigate same issue |
| **Locus standi** | Legal standing to bring a case |
| **Ultra vires** | "Beyond powers" — action exceeding legal authority |
| **Inter alia** | "Among other things" |
| **Prima facie** | "At first sight" — based on first impression |

---

## 6. Regional Court Quirks

### Bench Locations

Several High Courts have multiple benches across their state:

| High Court | Principal Seat | Circuit/Regular Benches |
|------------|---------------|------------------------|
| Allahabad | Allahabad | Lucknow |
| Bombay | Mumbai | Nagpur, Aurangabad, Goa (Panaji) |
| Calcutta | Kolkata | Port Blair (Andaman & Nicobar) |
| Madras | Chennai | Madurai |
| Gauhati | Guwahati | Kohima (Nagaland), Aizawl (Mizoram), Itanagar (Arunachal) |
| Karnataka | Bengaluru | Dharwad, Kalaburagi |
| Rajasthan | Jodhpur | Jaipur |
| Patna | Patna | — |

### Language of Proceedings

- **Supreme Court**: English only (Article 348)
- **High Courts**: English by default. Hindi authorized in: Rajasthan, MP, UP, Bihar
- **District Courts**: Language varies by state (Hindi, regional languages common)
- **Judgments**: Increasingly being translated into 17 regional languages (42,000+ SC translations)

### Filing Conventions

- **Supreme Court**: Only AoR (Advocate on Record) can file. Digital filing via e-filing portal.
- **High Courts**: Any enrolled advocate can file. Mix of physical and digital filing.
- **District Courts**: Physical filing predominant. eCourts digitization in progress.
- **Tribunals**: Own filing procedures. NCLT uses own e-filing system.
