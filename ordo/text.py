import re
import unicodedata

STOP = {"de", "d", "du", "des", "la", "le", "les", "l", "un", "une", "a", "au", "aux", "et", "pour",
        "avec", "sans", "en", "par", "sur", "mm", "s", "il", "vous", "plait", "svp", "x", "pce", "pcs",
        "piece", "pieces", "type", "capacite", "dimension", "dimensions", "lecture", "longueur"}
NUMWORDS = {"un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7,
            "huit": 8, "neuf": 9, "dix": 10, "douze": 12, "vingt": 20}
REF_RE = re.compile(r"^_?[A-Za-z]{0,3}\d{1,6}(?:/\d+)?[A-Za-z]{0,3}$")


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def norm(s):
    s = strip_accents(str(s)).lower()
    s = re.sub(r"(\d)\s*x\s*(\d)", r"\1 x \2", s)
    s = re.sub(r"(\d)-(\d)", r"\1 \2", s)
    s = re.sub(r"[^a-z0-9/,.]+", " ", s)
    s = re.sub(r"(?<!\d)[,.]|[,.](?!\d)", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def singular(t):
    if t.endswith("aux") and len(t) > 4:
        return t[:-3] + "al"
    if t.endswith(("s", "x")) and len(t) > 3 and not t[-2].isdigit():
        return t[:-1]
    return t


def tokens(s):
    return [singular(t) for t in norm(s).split() if t not in STOP]


def numbers(s):
    return set(re.findall(r"\d+(?:[,.]\d+)?", norm(s)))


def norm_ref(r):
    """Canonical form of a reference as typed by a customer."""
    if r is None:
        return ""
    r = str(r).strip().upper().lstrip("_").strip(".,;:")
    r = re.sub(r"\s+", "", r)
    return r


def looks_like_ref(tok):
    return bool(REF_RE.match(str(tok).strip().strip(".,;:")))


def parse_qty(s):
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).strip().lower()
    if s in NUMWORDS:
        return float(NUMWORDS[s])
    s = s.replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def parse_price(s):
    if s in (None, ""):
        return None
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).replace(" ", "").replace("€", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None
