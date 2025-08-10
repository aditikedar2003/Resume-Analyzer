from io import BytesIO
import PyPDF2
import docx


def extract_text_from_txt(fbytes: bytes):
    try:
        return fbytes.decode('utf-8', errors='ignore')
    except Exception:
        return fbytes.decode('latin-1', errors='ignore')


def extract_text_from_docx(fbytes: bytes):
    bio = BytesIO(fbytes)
    doc = docx.Document(bio)
    paragraphs = [p.text for p in doc.paragraphs if p.text]
    return "\n".join(paragraphs)


def extract_text_from_pdf(fbytes: bytes):
    bio = BytesIO(fbytes)
    try:
        reader = PyPDF2.PdfReader(bio)
        text_chunks = []
        for page in reader.pages:
            text_chunks.append(page.extract_text() or "")
        return "\n".join(text_chunks)
    except Exception:
        return ""


def extract_file_text(uploaded_file):
    if uploaded_file is None:
        return ""
    name = uploaded_file.name.lower()
    raw = uploaded_file.read()
    if name.endswith('.txt'):
        return extract_text_from_txt(raw)
    if name.endswith('.pdf'):
        return extract_text_from_pdf(raw)
    if name.endswith('.docx') or name.endswith('.doc'):
        try:
            return extract_text_from_docx(raw)
        except Exception:
            return extract_text_from_txt(raw)
    return extract_text_from_txt(raw)
