"""Matching cascade: exact ref -> customer alias -> fuzzy ref (typos) -> designation search.
Never picks silently when candidates are too close: returns flag 'ambiguous' with candidates."""
import csv
import re
import json
from rapidfuzz import fuzz
from .config import CATALOGUE_CSV, ALIASES_JSON
from .text import norm_ref, norm, tokens, numbers, singular

LEAD_QTY = re.compile(r"^\s*(?:[-*\u2022]\s*)?(?:d['\u2019])?(\d+(?:[,.]\d+)?|un|une|deux|trois|quatre|cinq|six|dix|douze)\s*(?:x\s+)?", re.I)
AMBIG_GAP = 6  # score points between best and second candidate below which we refuse to choose


class Catalogue:
    def __init__(self, path=CATALOGUE_CSV):
        with open(path, encoding="utf-8") as f:
            self.rows = list(csv.DictReader(f))
        self.by_ref = {norm_ref(r["ref"]): r for r in self.rows}
        for r in self.rows:
            r["_tokens"] = tokens(r["designation"])
            r["_head"] = r["_tokens"][0] if r["_tokens"] else ""
            r["_nums"] = numbers(r["designation"])
            r["_norm"] = " ".join(r["_tokens"])
        self.heads = {r["_head"] for r in self.rows}

    def get(self, ref):
        return self.by_ref.get(norm_ref(ref))


def load_aliases():
    try:
        return json.loads(ALIASES_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {}


def alias_key(text):
    return norm(LEAD_QTY.sub("", text or "", count=1))


def save_alias(customer, raw, ref):
    a = load_aliases()
    a.setdefault(customer or "*", {})[alias_key(raw)] = ref
    ALIASES_JSON.write_text(json.dumps(a, ensure_ascii=False, indent=2), encoding="utf-8")


def _typo_variants(r):
    """Common OCR / typing confusions: letter O for zero, doubled last letter."""
    out = {r.replace("O", "0"), r.replace("I", "1").replace("L", "1")}
    if len(r) > 3 and r[-1] == r[-2] and r[-1].isalpha():
        out.add(r[:-1])
    out.discard(r)
    return out


def match_ref(cat, raw_ref):
    r = norm_ref(raw_ref)
    if not r:
        return None
    if r in cat.by_ref:
        flags = ["ref_prefix_underscore"] if str(raw_ref).strip().startswith("_") else []
        return dict(ref=cat.by_ref[r]["ref"], confidence=1.0, method="exact", flags=flags, candidates=[])
    for v in _typo_variants(r):
        if v in cat.by_ref:
            return dict(ref=cat.by_ref[v]["ref"], confidence=0.75, method="typo",
                        flags=["typo_suspected", "match_to_verify"], candidates=[cat.by_ref[v]["ref"]])
    scored = sorted(((fuzz.ratio(r, k), k) for k in cat.by_ref), reverse=True)[:3]
    best = scored[0]
    if best[0] >= 90 and (len(scored) < 2 or best[0] - scored[1][0] >= 5):
        return dict(ref=cat.by_ref[best[1]]["ref"], confidence=0.7, method="fuzzy_ref",
                    flags=["typo_suspected", "match_to_verify"], candidates=[cat.by_ref[k]["ref"] for _, k in scored])
    return dict(ref=None, confidence=0.0, method="none", flags=["unknown_ref"],
                candidates=[cat.by_ref[k]["ref"] for s, k in scored if s >= 70])


def match_designation(cat, text):
    text = LEAD_QTY.sub("", text or "", count=1)
    toks = tokens(text)
    if not toks:
        return dict(ref=None, confidence=0.0, method="none", flags=["unknown_ref"], candidates=[])
    q = " ".join(toks)
    qnums = numbers(text)
    head = next((t for t in toks if t in cat.heads), None)
    pool = [r for r in cat.rows if r["_head"] == head] if head else cat.rows
    scored = []
    for r in pool:
        s = fuzz.token_set_ratio(q, r["_norm"])
        s += 8 * len(qnums & r["_nums"]) - 6 * len(qnums - r["_nums"])
        scored.append((s, r["ref"]))
    scored.sort(reverse=True)
    if not scored:
        return dict(ref=None, confidence=0.0, method="none", flags=["unknown_ref"], candidates=[])
    best = scored[0]
    close = [ref for s, ref in scored if best[0] - s < AMBIG_GAP]
    if len(close) > 1:
        return dict(ref=None, confidence=0.4, method="designation", flags=["ambiguous"], candidates=close[:5])
    conf = max(0.0, min(0.9, best[0] / 120))
    if conf < 0.6:
        close = [ref for s, ref in scored if best[0] - s < 15]
        if len(close) > 1:
            return dict(ref=None, confidence=round(conf, 2), method="designation", flags=["ambiguous"], candidates=close[:5])
    flags = [] if conf >= 0.85 else ["match_to_verify"]
    return dict(ref=best[1], confidence=round(conf, 2), method="designation", flags=flags,
                candidates=[ref for _, ref in scored[:3]])


def match_line(cat, line, customer=None, aliases=None):
    """line: dict with raw_text, customer_ref (may be None), quantity."""
    aliases = aliases if aliases is not None else load_aliases()
    raw = line.get("customer_ref") or ""
    text = line.get("raw_text") or raw
    for key in (alias_key(raw), alias_key(text)):
        for scope in (customer or "*", "*"):
            ref = aliases.get(scope, {}).get(key)
            if key and ref and cat.get(ref):
                res = dict(ref=cat.get(ref)["ref"], confidence=0.95, method="alias", flags=["learned_alias"], candidates=[])
                return _post(cat, res, line)
    res = None
    if raw:
        res = match_ref(cat, raw)
        has_words = any(t.isalpha() and len(t) > 2 for t in norm(text).split() if norm_ref(t) != norm_ref(raw))
        if res["ref"] is None and has_words:
            alt = match_designation(cat, text)
            if alt["ref"] or alt["flags"] == ["ambiguous"]:
                alt["flags"] = sorted(set(alt["flags"] + ["unknown_ref_designation_used"]))
                res = alt
    else:
        res = match_designation(cat, text)
    return _post(cat, res, line)


def _post(cat, res, line):
    row = cat.get(res["ref"]) if res["ref"] else None
    res["designation"] = row["designation"] if row else ""
    if row and row.get("pack_size") and int(float(row["pack_size"] or 0)) > 1:
        res["flags"] = sorted(set(res["flags"] + ["pack_size_to_confirm"]))
        res["pack_info"] = row["pack_info"]
    if line.get("quantity") in (None, 0):
        res["flags"] = sorted(set(res["flags"] + ["qty_missing"]))
    return res
