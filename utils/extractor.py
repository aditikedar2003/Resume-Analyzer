### FILE: utils/extractor.py
# utils/extractor.py
from io import BytesIO
try:
    import docx  # from python-docx
except Exception:
    docx = None
import PyPDF2

def extract_text_from_txt_bytes(fbytes: bytes):
    try:
        return fbytes.decode("utf-8", errors="ignore")
    except Exception:
        return fbytes.decode("latin-1", errors="ignore")

def extract_text_from_docx_bytes(fbytes: bytes):
    if not docx:
        return extract_text_from_txt_bytes(fbytes)
    bio = BytesIO(fbytes)
    try:
        doc = docx.Document(bio)
        paragraphs = [p.text for p in doc.paragraphs if p.text]
        return "\n".join(paragraphs)
    except Exception:
        return extract_text_from_txt_bytes(fbytes)

def extract_text_from_pdf_bytes(fbytes: bytes):
    bio = BytesIO(fbytes)
    try:
        reader = PyPDF2.PdfReader(bio)
        text_chunks = []
        for page in reader.pages:
            try:
                text_chunks.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n".join(text_chunks)
    except Exception:
        return ""

def extract_file_text(uploaded_file):
    """
    uploaded_file: streamlit uploaded_file object
    returns: text extracted (string)
    """
    if uploaded_file is None:
        return ""
    name = uploaded_file.name.lower()
    raw = uploaded_file.read()
    if name.endswith(".txt"):
        return extract_text_from_txt_bytes(raw)
    if name.endswith(".pdf"):
        return extract_text_from_pdf_bytes(raw)
    if name.endswith(".docx") or name.endswith(".doc"):
        return extract_text_from_docx_bytes(raw)
    # fallback
    return extract_text_from_txt_bytes(raw)
