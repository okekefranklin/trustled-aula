"""Extract text from uploaded PDF/DOCX files for prompt enrichment.

Files are read in memory, validated, and discarded — nothing is stored on disk.
"""
import io
import zipfile

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_EXTRACT_CHARS = 15000
ALLOWED_EXTENSIONS = {".pdf", ".docx"}


def _extension(filename):
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower()


def validate_upload(file_storage):
    """Return an error message if the upload is invalid, else None."""
    if not file_storage or not file_storage.filename:
        return None

    ext = _extension(file_storage.filename)
    if f".{ext}" not in ALLOWED_EXTENSIONS:
        return "Only PDF and DOCX files are accepted."

    data = file_storage.read()
    file_storage.seek(0)
    if not data:
        return "The uploaded file is empty."
    if len(data) > MAX_UPLOAD_BYTES:
        return "File exceeds the 10 MB limit."

    if ext == "pdf" and not data.lstrip().startswith(b"%PDF"):
        return "This file does not appear to be a valid PDF."
    if ext == "docx":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                if "word/document.xml" not in zf.namelist():
                    return "This file does not appear to be a valid DOCX document."
        except zipfile.BadZipFile:
            return "This file does not appear to be a valid DOCX document."

    return None


def _extract_pdf(data):
    import pdfplumber

    parts = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
    return "\n\n".join(parts).strip()


def _extract_docx(data):
    from docx import Document

    doc = Document(io.BytesIO(data))
    parts = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n".join(parts).strip()


def extract_text_from_upload(file_storage):
    """Validate and extract text from an upload.

    Returns ``(text, error)``. On success ``error`` is None; on failure ``text``
    is empty and ``error`` is a user-facing message.
    """
    err = validate_upload(file_storage)
    if err:
        return "", err

    ext = _extension(file_storage.filename)
    data = file_storage.read()

    try:
        if ext == "pdf":
            text = _extract_pdf(data)
        else:
            text = _extract_docx(data)
    except Exception:
        return "", (
            "Aula could not read this file. Please check that it is not corrupted "
            "or password-protected, and try again."
        )

    if not text:
        return "", "No readable text was found in this file."

    if len(text) > MAX_EXTRACT_CHARS:
        text = text[:MAX_EXTRACT_CHARS] + "\n\n[Text truncated for length.]"

    return text, None
