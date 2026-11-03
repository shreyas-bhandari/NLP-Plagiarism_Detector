import os
import re


def extract_pdf_text(path):
    import PyPDF2
    parts = []
    with open(path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or '')
            except Exception:
                parts.append('')
    return '\n'.join(parts)


def extract_docx_text(path):
    import docx
    document = docx.Document(path)
    return '\n'.join(p.text for p in document.paragraphs)


def extract_text(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == '.pdf':
        return extract_pdf_text(path)
    if ext in ('.docx', '.doc'):
        return extract_docx_text(path)
    if ext == '.txt':
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    raise ValueError(f'Unsupported file type: {ext}')


def clean_text(text):
    text = (text or '').replace('\x00', '')
    text = re.sub(r'[ \t\r\f\v]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()
