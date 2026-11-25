# System Architecture & Engineering Deep Dive

## 0. Architecture Diagrams

### A. End-to-End System & UI Architecture

```mermaid
flowchart LR
    subgraph CLIENT["Browser — 3-Column UI (backend/static/index.html)"]
        direction TB
        C1["Col 1 (3/12): Notice Input<br/>File Upload · WhatsApp Text · Status Banner"]
        C2["Col 2 (5/12): Intelligence & Proof<br/>Eligibility Badge · EN/HI/MR Cards · Clauses C1..Cn"]
        C3["Col 3 (4/12): Grounded Chat<br/>Multilingual Q&A · Click-to-Highlight C#"]
        LS[("localStorage<br/>StudentProfile & Theme")]
    end

    subgraph API["FastAPI Backend (backend/app/main.py)"]
        direction TB
        P["POST /api/notices/analyze<br/>parser.py -> extractor.py"]
        EL["POST /api/notices/eligibility<br/>eligibility.py (0 AI Tokens)"]
        TR["POST /api/notices/translate<br/>translator.py + Hash Cache"]
        CH["POST /api/notices/chat<br/>chat.py (Scoped to C1..Cn)"]
    end

    subgraph ROUTER["Unified LLM Router (llm_client.py)"]
        direction TB
        GEM["Gemini 5-Model Chain<br/>3.5-flash-lite -> 4-hydrogen -> 3.8-flash<br/>-> 3.6-flash -> 3.1-flash-lite"]
        GRQ["Groq 2-Model Chain<br/>openai/gpt-oss-120b -> openai/gpt-oss-20b"]
    end

    C1 -->|"multipart/form-data"| P
    LS -.->|"Profile JSON"| EL
    C2 -->|"canonical + profile"| EL
    C2 -->|"canonical + lang"| TR
    C3 -->|"clauses + question + lang"| CH

    P -->|"prefer=gemini"| GEM
    TR -->|"Cache Miss · prefer=gemini"| GEM
    CH -->|"prefer=groq"| GRQ

    GEM -.->|"Failover on 503/429/404"| GRQ
    GRQ -.->|"Failover on Error"| GEM

    P -->|"clauses + canonical"| C2
    EL -->|"Eligible / Not Eligible + Warnings"| C2
    TR -->|"Localized View + cached flag"| C2
    CH -->|"answer + max 3 verified C# tags"| C3
```

### B. Multi-Provider Failover & Caching Sequence

```mermaid
sequenceDiagram
    actor Student
    participant UI as Web UI (index.html)
    participant API as FastAPI Backend
    participant Cache as SHA-256 Translation Cache
    participant Router as llm_client.py
    participant Gemini as Gemini (5 Models)
    participant Groq as Groq (2 Models)

    Student->>UI: Upload Notice (PDF / Image / DOCX / Text)
    UI->>API: POST /api/notices/analyze
    API->>API: Stage 1: Parse into [C1..Cn] (0 tokens)
    API->>Router: Stage 2: Extract CanonicalNotice (prefer="gemini")
    Router->>Gemini: Try Gemini chain (3.5-flash-lite ... 3.1-flash-lite)
    alt Gemini succeeds
        Gemini-->>Router: Validated JSON
    else Gemini 503 / 429 overload
        Router->>Groq: Automatic failover (gpt-oss-120b -> gpt-oss-20b)
        Groq-->>Router: Validated JSON
    end
    Router-->>API: CanonicalNotice
    API->>API: Deterministic _validate_citations() guardrail
    API-->>UI: { clauses, canonical }

    UI->>API: POST /api/notices/eligibility (0 tokens)
    API-->>UI: { status, passed_checks, failed_reasons, edge_warnings }

    Student->>UI: Click Hindi / Marathi toggle
    UI->>API: POST /api/notices/translate
    API->>Cache: Lookup SHA-256(canonical + lang)
    alt Cache Hit
        Cache-->>API: Localized JSON (0 tokens, <5 ms)
    else Cache Miss
        API->>Router: Translate compact JSON (prefer="gemini")
        Router-->>API: Localized JSON (preserving [C#] tags)
        API->>Cache: Store translation
    end
    API-->>UI: Localized View

    Student->>UI: Ask follow-up question in EN / HI / MR
    UI->>API: POST /api/notices/chat
    API->>Router: Grounded Q&A on [C1..Cn] (prefer="groq")
    Router->>Groq: Fast LPU inference (fallback -> Gemini)
    Groq-->>Router: { answer, citations, found_in_notice }
    API->>API: Strip invalid tags & cap at 3 citations
    API-->>UI: Grounded Reply + Clickable [C#] Chips
```

## 1. System vs. AI Responsibility Split

NoticeMitra strictly separates **deterministic system code** (facts, coordinates, math, validation, caching) from **generative AI** (semantic extraction, natural regional phrasing, grounded reasoning):

| Stage                                          | System (Deterministic Code)                                                                                    | AI (LLM)                                                                                    | Key Benefit                                          |
| :--------------------------------------------- | :------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------ | :--------------------------------------------------- |
| **1. Ingestion (`parser.py`)**         | PyMuPDF (digital PDF), RapidOCR ONNX (images/scans), `python-docx` (Word), raw text splitter → `[C1..Cn]` | None                                                                                        | 0 AI tokens; zero hallucination on raw numbers/dates |
| **2. Extraction (`extractor.py`)**     | Pydantic `CanonicalNotice` schema + `_validate_citations()` guardrail                                      | **AI Call #1 (Once):** Extracts summary, deadlines, docs, hard rules, edge conditions | Compact source of truth; fake `[C#]` tags blocked  |
| **3A. Eligibility (`eligibility.py`)** | Pure Python comparison against `StudentProfile`                                                              | None                                                                                        | Instant (<5 ms), 0 tokens, 100% accurate math        |
| **3B. Localization (`translator.py`)** | SHA-256 content-hash cache lookup                                                                              | **AI Call #2 (Cache miss only):** Natural EN → HI / MR JSON translation              | ~70% token reduction; 0 tokens on repeat views       |
| **4. Follow-Up Chat (`chat.py`)**      | Clause scoping (`[C1..Cn]`) + citation cap (max 3 verified tags)                                             | **AI Call #3:** Strict grounded Q&A in EN / HI / MR                                   | Refuses out-of-notice queries; fast LPU inference    |

---

## 2. Multi-Provider LLM Failover Router (`llm_client.py`)

Relying on a single hosted model exposes live applications to transient `503 UNAVAILABLE` congestion spikes and `429` rate limits. NoticeMitra centralizes all model calls inside `backend/app/llm_client.py` with **7 models across 2 providers**:

* **Gemini Chain (5 Models):** `gemini-3.5-flash-lite` → `gemini-4-hydrogen` → `gemini-3.8-flash` → `gemini-3.6-flash` → `gemini-3.1-flash-lite`
* **Groq Chain (2 Models):** `openai/gpt-oss-120b` → `openai/gpt-oss-20b`

### Task-Aware Routing Strategy

* **`prefer="gemini"` (`extractor.py`, `translator.py`):** Leverages Gemini's native Pydantic `response_schema` and strong Devanagari fluency for Hindi/Marathi; automatically fails over to Groq JSON mode if all Gemini models are congested.
* **`prefer="groq"` (`chat.py`):** Leverages Groq's low-latency inference for responsive student Q&A; automatically falls back to Gemini if Groq is unavailable.

---

## 3. Data Flow & Guardrails

1. **Citation Guardrail:** Both `extractor.py` and `chat.py` build a `valid_codes = {c["clause_code"] for c in clauses}` set from Stage 1 output. Any AI-returned citation not present in `valid_codes` is dropped before returning JSON to the client.
2. **Strict Refusal Contract (`ChatReply`):** Every chat response returns `{ answer, citations, found_in_notice }`. When `found_in_notice` is `false`, the UI displays an explicit warning indicator (`Not explicitly found in notice`) rather than presenting an assumption as fact.
3. **Zero-Auth Profile Portability:** Student profiles (`branch`, `year`, `category`, `cgpa`, `family_income`, `active_backlogs`) are stored in browser `localStorage` and sent on demand to `/api/notices/eligibility`, allowing instant persona switching during demos without login friction.

---

## 4. Frontend Architecture (`backend/static/index.html`)

Served directly by FastAPI at `GET /` (zero separate build pipeline, zero CORS issues):

* **3-Column Desktop Workspace (`3 : 5 : 4` ratio):**
  * **Left Column (3 cols — Sticky):** File upload (`.pdf`, `.png`, `.jpg`, `.jpeg`, `.docx`), WhatsApp text input, sample circular loader, and live 3-step progress/error status banner.
  * **Center Column (5 cols):** Personalized Eligibility Banner, conditional edge-rule warnings, localized Summary / Deadlines / Required Documents cards, and scrollable Indexed Source Clauses (`[C1..Cn]`) viewer.
  * **Right Column (4 cols — Sticky):** Full-height Grounded Multilingual Follow-Up Chat with compact clickable `[C#]` proof chips.
* **Theme & Localization:** Persistent Light/Dark theme toggle (`localStorage`) and 1-click `English | हिंदी | मराठी` switcher.
