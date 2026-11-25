"""Turn an incoming email (.eml) or a loose file into a normalized 'Message' with text parts."""
import email
import io
from email import policy
from dataclasses import dataclass, field


@dataclass
class Attachment:
    name: str
    kind: str            # pdf | xlsx | image | other
    data: bytes
    text: str = ""
    is_scan: bool = False
    images: list = field(default_factory=list)   # PNG bytes, only for scans / images
    table: list = field(default_factory=list)    # rows, only for xlsx


@dataclass
class Message:
    sender: str = ""
    subject: str = ""
    date: str = ""
    body: str = ""
    attachments: list = field(default_factory=list)


def pdf_to_attachment(name, data):
    import pdfplumber
    a = Attachment(name=name, kind="pdf", data=data)
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        a.text = "\n".join((p.extract_text() or "") for p in pdf.pages)
        if len(a.text.strip()) < 20:
            a.is_scan = True
            for p in pdf.pages[:3]:
                buf = io.BytesIO()
                p.to_image(resolution=150).original.save(buf, format="PNG")
                a.images.append(buf.getvalue())
    return a


def xlsx_to_attachment(name, data):
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
    rows = []
    for ws in wb.worksheets:
        for r in ws.iter_rows(values_only=True):
            if any(v not in (None, "") for v in r):
                rows.append(["" if v is None else v for v in r])
    text = "\n".join("\t".join(str(v) for v in r) for r in rows)
    return Attachment(name=name, kind="xlsx", data=data, text=text, table=rows)


def image_to_attachment(name, data):
    return Attachment(name=name, kind="image", data=data, is_scan=True, images=[data])


def file_to_attachment(name, data):
    n = name.lower()
    if n.endswith(".pdf"):
        return pdf_to_attachment(name, data)
    if n.endswith((".xlsx", ".xlsm")):
        return xlsx_to_attachment(name, data)
    if n.endswith((".png", ".jpg", ".jpeg")):
        return image_to_attachment(name, data)
    if n.endswith((".txt", ".csv")):
        return Attachment(name=name, kind="other", data=data, text=data.decode("utf-8", "replace"))
    return Attachment(name=name, kind="other", data=data)


def parse_eml(data):
    m = email.message_from_bytes(data, policy=policy.default)
    msg = Message(sender=str(m.get("From", "")), subject=str(m.get("Subject", "")), date=str(m.get("Date", "")))
    body = m.get_body(preferencelist=("plain", "html"))
    msg.body = body.get_content() if body else ""
    for part in m.iter_attachments():
        name = part.get_filename() or "piece_jointe"
        msg.attachments.append(file_to_attachment(name, part.get_payload(decode=True)))
    return msg


def load_any(name, data):
    if name.lower().endswith(".eml"):
        return parse_eml(data)
    msg = Message(subject=name)
    msg.attachments.append(file_to_attachment(name, data))
    return msg


def ocr_available():
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def ocr(images):
    import pytesseract
    from PIL import Image
    langs = pytesseract.get_languages(config="")
    lang = "fra" if "fra" in langs else "eng"
    return "\n".join(pytesseract.image_to_string(Image.open(io.BytesIO(b)), lang=lang, config="--psm 6") for b in images)
