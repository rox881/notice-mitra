
# Problem Statement & Solution Design

## 1. The Real Campus Problem (AI-04)

Official college circulars—covering exam forms, scholarship schemes, fee deadlines, ATKT rules, and placement drives—are routinely distributed as multi-page scanned PDFs, notice-board photos, Word drafts, or chaotic WhatsApp forwards. Students face four compounding bottlenecks:

1. **Dense Bureaucratic Language:** Critical dates, fees, and eligibility exceptions are buried inside formal English prose.
2. **Language Barrier:** First-generation learners and regional-medium students struggle with administrative English, while literal word-for-word translation distorts academic terms (e.g., *CGPA*, *ATKT*, *MahaDBT*, *Tehsildar Income Certificate*).
3. **Eligibility Traps ("Is this even for me?"):** A student may spend hours collecting documents only to miss a single buried condition (e.g., *"minimum 7.5 CGPA"*, *"zero active backlogs"*, or *"not valid for hostelites"*).
4. **Trust & Hallucination Risk:** Copying a notice into a generic chatbot carries no verifiable proof—if an AI hallucinates a deadline or fee amount, the student pays the penalty.

---

## 2. Why a Generic ChatGPT / Google Translate Wrapper Fails

| Failure Mode of Naive Wrappers                     | How NoticeMitra Solves It                                                                              |
| :------------------------------------------------- | :----------------------------------------------------------------------------------------------------- |
| Assumes clean copy-pasted text                     | Ingests digital PDFs, scanned images (OCR), `.docx` files, and raw WhatsApp text                     |
| Produces unverified summaries                      | Indexes every line/paragraph into `[C1..Cn]` and validates every `[C#]` citation deterministically |
| LLMs miscalculate numeric rules (CGPA, income)     | Pure Python rule engine evaluates hard numeric criteria with 0 AI tokens                               |
| Translates all 3 languages upfront (3x token burn) | Stores a compact **Canonical English Core** once and lazy-loads/caches Hindi & Marathi on demand |
| Guesses answers when info is missing               | Chat is locked strictly to `[C1..Cn]` and explicitly refuses if a detail is absent                   |

---

## 3. The 3-Pillar Solution

### Pillar 1: Truth & Click-to-Cite Grounding (Digital Trust)

Before any LLM touches a notice, deterministic code assigns every meaningful block a unique clause ID (`C1`, `C2`, ..., `Cn`). During extraction and Q&A, the model must attach exact source clause IDs. A deterministic Pydantic guardrail strips any hallucinated or non-existent clause code before the response reaches the UI. Clicking any compact `[C#]` chip scrolls to and highlights the original clause.

### Pillar 2: Hybrid Deterministic Eligibility Checking

Standard eligibility parameters—`target_branches`, `target_years`, `target_categories`, `min_cgpa`, `max_income`, and `max_backlogs`—are evaluated in pure Python (`eligibility.py`) against the student's locally saved profile (`localStorage`). Context-specific exceptions that cannot be reduced to fixed numbers (e.g., *"Not applicable to students already availing MahaDBT"*) are extracted into `edge_conditions[]` with their `[C#]` citation and surfaced as amber warning cards.

### Pillar 3: Canonical Core + On-Demand Regional Intelligence

* **Upload Once:** AI extracts a compact (~350-token) Canonical English JSON removing letterhead fluff and noise.
* **Translate Lazily:** Switching to **हिंदी (Hindi)** or **मराठी (Marathi)** translates only that compact JSON—preserving dates, fees, and `[C#]` tags—and caches the result by content hash so repeat views cost **0 tokens**.
* **Grounded Multilingual Q&A:** Students ask follow-up questions in English, Hindi, or Marathi and receive concise answers grounded exclusively in `[C1..Cn]` with up to 3 direct citations.
