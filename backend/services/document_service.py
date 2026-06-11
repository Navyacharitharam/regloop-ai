import pypdf
import csv
import io
from typing import Tuple


async def extract_pdf_text(file_bytes: bytes, filename: str = "") -> str:
    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text:
            pages.append(f"[Page {i+1}]\n{text}")
    return "\n\n".join(pages)


def parse_csv(file_bytes: bytes) -> list:
    text = file_bytes.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    return [row for row in reader]
