"""Offline extractor (no AI). Deterministic patterns used as a fallback when no API key is set
or the API is unreachable. Deliberately simple: the LLM extractor is the real one."""
import re
from .text import looks_like_ref, parse_qty, parse_price, norm, tokens, NUMWORDS

DATE = r"(\d{1,2}/\d{1,2}(?:/\d{2,4})?)"
UNITS = r"(?:PCE|PCS|PC|U|UN|UNITE|UNITES)"
TABLE_LINE = re.compile(rf"^\s*(\S+)\s+(.+?)\s+(\d+(?:[,.]\d+)?)\s+{UNITS}\b\s*(\d[\d ]*[,.]\d+)?\s*(\d{{1,2}}/\d{{1,2}}/\d{{2,4}})?", re.I)
FORM_LINE = re.compile(r"^\s*(\S+)\s+(.+?)\s+(\d+(?:[,.]\d+)?)\s*$")
BULLET_REF = re.compile(r"^\s*[-*•]?\s*(\d+(?:[,.]\d+)?)\s*[xX×]\s*(\S+)\s*$")
REF_BULLET = re.compile(r"^\s*[-*•]?\s*(\S+)\s*[xX×:]\s*(\d+(?:[,.]\d+)?)\s*$")
FREE = re.compile(r"(?:^|\s|d['’])(\d+|" + "|".join(NUMWORDS) + r")\s+([a-zA-ZÀ-ÿ].+)", re.I)
MODIF = re.compile(r"r[ée]f(?:[ée]rence)?\.?\s*(\S+?)\s+(?:à|a|passe à)\s+(\d+)(?:\s+au lieu de\s+(\d+))?", re.I)
ADD = re.compile(r"ajout\w*\s+(\d+)\s+(?:pi[eè]ces?\s+)?(?:de\s+|d['’])?(?:la\s+)?(?:r[ée]f\.?\s*)?(\S+)", re.I)
POLITE = re.compile(r"s'il vous pla[iî]t|svp|merci.*$", re.I)


def _line(raw, ref, qty, price=None, source="attachment", change="none"):
    return dict(raw_text=raw.strip(), customer_ref=ref, quantity=parse_qty(qty), unit_price=parse_price(price),
                source=source, change=change)


def lines_from_pdf_text(text, dates=None):
    out = []
    for l in text.splitlines():
        m = TABLE_LINE.match(l)
        if m and looks_like_ref(m.group(1)):
            out.append(_line(l, m.group(1), m.group(3), m.group(4)))
            if dates is not None and m.group(5):
                dates.append(m.group(5))
            continue
        m = FORM_LINE.match(l)
        if m and looks_like_ref(m.group(1)) and not re.match(DATE, m.group(1)):
            out.append(_line(l, m.group(1), m.group(3)))
    return out


def lines_from_table(rows):
    hdr_i, cols = None, {}
    for i, r in enumerate(rows):
        low = [norm(c) for c in r]
        if any("qt" in c for c in low) and any("ref" in c for c in low):
            hdr_i = i
            refs = [j for j, c in enumerate(low) if "ref" in c]
            pref = [j for j in refs if any(k in low[j] for k in ("feku", "fournisseur", "fourn"))]
            cols["ref"] = (pref or refs)[-1] if pref else refs[0]
            cols["qty"] = next(j for j, c in enumerate(low) if "qt" in c)
            cols["price"] = next((j for j, c in enumerate(low) if "prix" in c), None)
            cols["des"] = next((j for j, c in enumerate(low) if "design" in c or "libel" in c), None)
            break
    if hdr_i is None:
        return []
    out = []
    for r in rows[hdr_i + 1:]:
        ref = str(r[cols["ref"]]).strip() if cols["ref"] < len(r) else ""
        if not ref:
            continue
        des = str(r[cols["des"]]) if cols["des"] is not None else ""
        price = r[cols["price"]] if cols["price"] is not None else None
        out.append(_line(f"{ref} {des}", ref, r[cols["qty"]], price))
    return out


def lines_from_body(body, has_attachment_lines):
    out, mods = [], []
    clean = []
    for l in body.splitlines():
        if l.strip().startswith(">"):
            break  # quoted previous message
        clean.append(l)
    for l in clean:
        if has_attachment_lines:
            for m in MODIF.finditer(l):
                mods.append(_line(m.group(0), m.group(1), m.group(2), source="email_body", change="modified_by_email"))
            for m in ADD.finditer(l):
                mods.append(_line(m.group(0), m.group(2), m.group(1), source="email_body", change="added_by_email"))
            continue
        m = BULLET_REF.match(l)
        if m and looks_like_ref(m.group(2)):
            out.append(_line(l, m.group(2), m.group(1), source="email_body"))
            continue
        m = REF_BULLET.match(l)
        if m and looks_like_ref(m.group(1)):
            out.append(_line(l, m.group(1), m.group(2), source="email_body"))
            continue
        for chunk in re.split(r",|\bet\b|\baussi\b|\.\s", l, flags=re.I):
            chunk = POLITE.sub("", chunk).strip()
            fm = FREE.search(chunk)
            if fm:
                desc = fm.group(2).strip()
                out.append(_line(f"{fm.group(1)} {desc}", None, fm.group(1), source="email_body"))
    return out, mods


def full_date(d, ref_year):
    if not d:
        return None
    p = d.split("/")
    if len(p) == 2:
        p.append(str(ref_year))
    if len(p[2]) == 2:
        p[2] = "20" + p[2]
    return f"{int(p[0]):02d}/{int(p[1]):02d}/{p[2]}"


def _email_date(msg):
    from email.utils import parsedate_to_datetime
    try:
        return parsedate_to_datetime(msg.date)
    except Exception:
        return None


def header(msg, texts, line_dates=()):
    blob = "\n".join([msg.subject, msg.body] + texts)
    h = dict(customer=None, order_number=None, order_date=None, delivery_date=None, ar_requested="no")
    m = re.search(r"(?:COMMANDE|BC|CF|N[°o])\s*(?:N[°o]\s*)?:?\s*([A-Z]{0,4}-?[0-9][A-Z0-9\-]{3,})", blob, re.I)
    if m:
        h["order_number"] = m.group(1)
    ed = _email_date(msg)
    year = ed.year if ed else 2026
    m = re.search(r"date[^\n\d]{0,20}(\d{1,2}/\d{1,2}/\d{2,4})", "\n".join(texts), re.I)
    h["order_date"] = full_date(m.group(1), year) if m else (ed.strftime("%d/%m/%Y") if ed else None)
    m = re.search(r"livr\w*[^\n\d]{0,40}" + DATE, blob, re.I)
    if m:
        h["delivery_date"] = full_date(m.group(1), year)
    elif line_dates:
        h["delivery_date"] = full_date(sorted(set(line_dates))[0], year)
    if re.search(r"48\s*h", blob, re.I):
        h["ar_requested"] = "yes_48h"
    elif re.search(r"\bAR\b|accus[ée] de r[ée]ception|confirmer la r[ée]ception", blob):
        h["ar_requested"] = "yes"
    first = next((l.strip() for t in texts for l in t.splitlines() if l.strip()), "")
    first = re.split(r"\s*(?:COMMANDE|N°)\b", re.sub(r"(?i)^bon de commande\s*", "", first), flags=re.I)[0].strip(" \t-:")
    h["customer"] = first[:60] if len(first) > 2 else (msg.sender or "").split("@")[-1].strip(">")
    return h


def extract(msg, ocr_fn=None):
    lines, texts, notes, line_dates = [], [], [], []
    for a in msg.attachments:
        if a.kind == "xlsx":
            lines += lines_from_table(a.table)
            texts.append(a.text)
        elif a.is_scan:
            if ocr_fn:
                t = ocr_fn(a.images)
                found = lines_from_pdf_text(t, line_dates)
                if found:
                    texts.append(t)
                lines += found
                notes.append(f"{a.name} : scan lu par OCR local" + (" (fiabilité réduite)." if found else ", texte illisible : utiliser le mode IA (vision)."))
            else:
                notes.append(f"{a.name} : PDF scanné sans texte, nécessite le mode IA (vision).")
        elif a.text:
            texts.append(a.text)
            lines += lines_from_pdf_text(a.text, line_dates)
    body_lines, mods = lines_from_body(msg.body or "", bool(lines))
    lines += body_lines
    h = header(msg, texts, line_dates)
    h["lines"] = lines
    h["modifications"] = mods
    h["notes"] = notes
    return h
