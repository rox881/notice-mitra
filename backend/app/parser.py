import io
import fitz  # PyMuPDF
from docx import Document
from rapidocr_onnxruntime import RapidOCR

# Initialize OCR engine once at module load (fast reuse across uploads)
ocr_engine = RapidOCR()


def _clean_text(text: str) -> str:
    return " ".join(text.split()).strip()


def parse_document(file_bytes: bytes, filename: str) -> dict:
    """
    Extracts indexed clauses [C1, C2, ...] with page numbers and bounding boxes
    from digital PDFs, scanned PDFs, images (PNG/JPG), or Word docs (.docx).
    """
    ext = filename.lower().split(".")[-1]
    clauses = []
    clause_idx = 1

    if ext == "pdf":
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page_num, page in enumerate(doc, start=1):
            page_rect = page.rect
            blocks = page.get_text("blocks")
            text_blocks = [b for b in blocks if b[6] == 0 and len(_clean_text(b[4])) > 8]

            if text_blocks:
                for b in text_blocks:
                    cleaned = _clean_text(b[4])
                    clauses.append({
                        "clause_code": f"C{clause_idx}",
                        "raw_text": cleaned,
                        "page_num": page_num,
                        "bbox": {
                            "x": round(b[0] / page_rect.width, 4),
                            "y": round(b[1] / page_rect.height, 4),
                            "w": round((b[2] - b[0]) / page_rect.width, 4),
                            "h": round((b[3] - b[1]) / page_rect.height, 4),
                        },
                    })
                    clause_idx += 1
            else:
                pix = page.get_pixmap(dpi=200)
                img_bytes = pix.tobytes("png")
                ocr_clauses, clause_idx = _run_ocr_on_image(
                    img_bytes, page_num, pix.width, pix.height, clause_idx
                )
                clauses.extend(ocr_clauses)

    elif ext == "docx":
        doc = Document(io.BytesIO(file_bytes))
        # Extract paragraphs
        for para in doc.paragraphs:
            cleaned = _clean_text(para.text)
            if len(cleaned) > 8:
                clauses.append({
                    "clause_code": f"C{clause_idx}",
                    "raw_text": cleaned,
                    "page_num": 1,
                    "bbox": None,  # Word docs don't have fixed visual coordinates
                })
                clause_idx += 1
        # Extract table rows (critical for fee/date tables)
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(_clean_text(cell.text) for cell in row.cells if _clean_text(cell.text))
                if len(row_text) > 8:
                    clauses.append({
                        "clause_code": f"C{clause_idx}",
                        "raw_text": row_text,
                        "page_num": 1,
                        "bbox": None,
                    })
                    clause_idx += 1

    else:
        # Image upload path (PNG, JPG, JPEG)
        img_doc = fitz.open(stream=file_bytes, filetype=ext)
        pix = img_doc[0].get_pixmap()
        ocr_clauses, clause_idx = _run_ocr_on_image(
            file_bytes, 1, pix.width, pix.height, clause_idx
        )
        clauses.extend(ocr_clauses)

    return {
        "filename": filename,
        "total_clauses": len(clauses),
        "clauses": clauses,
    }


def _run_ocr_on_image(
    img_bytes: bytes, page_num: int, width: int, height: int, start_idx: int
) -> tuple[list[dict], int]:
    result, _ = ocr_engine(img_bytes)
    clauses = []
    idx = start_idx
    if not result:
        return clauses, idx

    for item in result:
        box, raw_text, conf = item
        cleaned = _clean_text(raw_text)
        if len(cleaned) <= 4 or float(conf) < 0.5:
            continue

        xs = [pt[0] for pt in box]
        ys = [pt[1] for pt in box]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)

        clauses.append({
            "clause_code": f"C{idx}",
            "raw_text": cleaned,
            "page_num": page_num,
            "bbox": {
                "x": round(x0 / width, 4),
                "y": round(y0 / height, 4),
                "w": round((x1 - x0) / width, 4),
                "h": round((y1 - y0) / height, 4),
            },
        })
        idx += 1

    return clauses, idx


def parse_raw_text(raw_text: str, title: str = "Pasted Notice") -> dict:
    """
    Splits pasted WhatsApp/plain text into indexed clauses [C1, C2, ...]
    by line breaks or bullet points.
    """
    clauses = []
    clause_idx = 1

    for line in raw_text.splitlines():
        cleaned = _clean_text(line)
        if len(cleaned) > 8:
            clauses.append({
                "clause_code": f"C{clause_idx}",
                "raw_text": cleaned,
                "page_num": 1,
                "bbox": None,
            })
            clause_idx += 1

    return {
        "filename": title,
        "total_clauses": len(clauses),
        "clauses": clauses,
    }