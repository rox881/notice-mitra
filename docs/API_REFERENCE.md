
# API Reference

Base URL (local): `http://127.0.0.1:8000`
Interactive Swagger UI: `http://127.0.0.1:8000/docs`

---

## Endpoint Summary

| Method   | Endpoint                     | Stage       | Description                                                        |
| :------- | :--------------------------- | :---------- | :----------------------------------------------------------------- |
| `GET`  | `/`                        | UI          | Serves the 3-column NoticeMitra web application                    |
| `GET`  | `/health`                  | System      | Health check returning service status                              |
| `POST` | `/api/notices/parse`       | Stage 1     | Parses uploaded file or raw text into indexed clauses `[C1..Cn]` |
| `POST` | `/api/notices/analyze`     | Stages 1–2 | Runs parsing + canonical extraction + citation verification        |
| `POST` | `/api/notices/eligibility` | Stage 3A    | Deterministic Python eligibility check against a student profile   |
| `POST` | `/api/notices/translate`   | Stage 3B    | Returns English canonical view or cached Hindi/Marathi translation |
| `POST` | `/api/notices/chat`        | Stage 4     | Grounded multilingual Q&A locked strictly to `[C1..Cn]`          |

---

## Endpoint Details

### 1. `POST /api/notices/analyze`

Accepts `multipart/form-data` with either `file` (`.pdf`, `.png`, `.jpg`, `.jpeg`, `.docx`) or `raw_text` (string).

**Response (`200 OK`):**

```json
{
  "filename": "scholarship_notice.pdf",
  "total_clauses": 7,
  "clauses": [
    { "clause_code": "C1", "raw_text": "OFFICE OF THE PRINCIPAL...", "page_num": 1, "bbox": null }
  ],
  "canonical": {
    "title": "Merit-cum-Means Tuition Fee Waiver Scheme",
    "category": "Scholarship",
    "urgency": "High",
    "summary_bullets": [
      { "text": "Open for SE and TE students of CS, IT, and AIML.", "citation": "C3" }
    ],
    "deadlines": [
      { "event": "Submit physical form at Admin Window 3", "date": "30th November 2026", "citation": "C7" }
    ],
    "required_documents": [
      { "text": "Tehsildar Income Certificate", "citation": "C6" }
    ],
    "hard_rules": {
      "target_branches": ["CS", "IT", "AIML"],
      "target_years": ["SE", "TE"],
      "target_categories": [],
      "min_cgpa": 7.5,
      "max_income": 600000,
      "max_backlogs": 0,
      "citation": "C4"
    },
    "edge_conditions": [
      { "text": "Hostel residents or MahaDBT recipients are not eligible.", "citation": "C5" }
    ]
  }
}
```

---

### 2. `POST /api/notices/eligibility`

**Request (`application/json`):**

```json
{
  "canonical": { "...": "canonical object from /analyze" },
  "profile": {
    "branch": "CS",
    "year": "TE",
    "category": "OPEN",
    "cgpa": 8.0,
    "family_income": 450000,
    "active_backlogs": 0
  }
}
```

**Response (`200 OK`):**

```json
{
  "status": "Eligible",
  "passed_checks": ["Branch CS matches", "Year TE matches", "CGPA 8.0 >= 7.5", "Income within limit", "Backlogs 0 <= 0"],
  "failed_reasons": [],
  "edge_warnings": [
    { "text": "Hostel residents or MahaDBT recipients are not eligible.", "citation": "C5" }
  ],
  "citation": "C4"
}
```

---

### 3. `POST /api/notices/translate`

**Request (`application/json`):**

```json
{
  "canonical": { "...": "canonical object from /analyze" },
  "lang": "mr"
}
```

*Supported values for `lang`: `"en"`, `"hi"`, `"mr"`. Returns localized fields with `"cached": true/false`.*

---

### 4. `POST /api/notices/chat`

**Request (`application/json`):**

```json
{
  "clauses": [
    { "clause_code": "C4", "raw_text": "Minimum 7.5 CGPA and zero active backlogs.", "page_num": 1, "bbox": null }
  ],
  "question": "Can I apply if I have 1 active backlog?",
  "lang": "hi",
  "profile": {
    "branch": "CS",
    "year": "TE",
    "category": "OPEN",
    "cgpa": 8.0,
    "family_income": 450000,
    "active_backlogs": 1
  }
}
```

**Response (`200 OK`):**

```json
{
  "answer": "नहीं, इस योजना के लिए शून्य (0) एक्टिव बैकलॉग होना आवश्यक है।",
  "citations": ["C4"],
  "found_in_notice": true
}
```

---

## Error Codes

| Code    | Cause                                                                               |
| :------ | :---------------------------------------------------------------------------------- |
| `400` | Unsupported file extension, empty upload, or missing both `file` and `raw_text` |
| `422` | Validation error (missing required JSON fields) or zero readable clauses extracted  |
| `500` | Upstream AI provider failure after exhausting all 7 Gemini + Groq fallback models   |
