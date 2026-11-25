import time
from .ingest import ocr_available, ocr
from .match import Catalogue, match_line, load_aliases
from . import extract_rules, extract_llm
from .config import api_key
from .text import norm_ref

_CAT = None


def catalogue():
    global _CAT
    if _CAT is None:
        _CAT = Catalogue()
    return _CAT


def _apply_modifications(lines, mods):
    """Offline mode only: apply 'qty changed' / 'line added' instructions found in the email body."""
    for m in mods:
        target = next((l for l in lines if norm_ref(l["customer_ref"]) == norm_ref(m["customer_ref"])), None)
        if m["change"] == "modified_by_email" and target:
            target["note"] = f"PJ : {target['quantity']:g}, email : {m['quantity']:g}"
            target["quantity"] = m["quantity"]
            target["change"] = "modified_by_email"
        elif target is None:
            m["change"] = "added_by_email"
            lines.append(m)
    return lines


def process(msg, mode="auto", model_id=None, aliases=None):
    t0 = time.time()
    use_llm = mode == "llm" or (mode == "auto" and api_key())
    meta = dict(mode="ia" if use_llm else "hors-ligne", cost_usd=0.0, error=None)
    if use_llm:
        try:
            order = extract_llm.extract(msg, model_id)
            meta.update(order.pop("_meta"))
        except Exception as e:  # fall back so the demo never dies
            meta.update(mode="hors-ligne (IA indisponible)", error=f"{type(e).__name__}: {e}"[:300])
            use_llm = False
    if not use_llm:
        order = extract_rules.extract(msg, ocr if ocr_available() else None)
    lines = _apply_modifications(order.get("lines", []), order.pop("modifications", []))
    cat = catalogue()
    aliases = load_aliases() if aliases is None else aliases
    out = []
    for i, l in enumerate(lines, 1):
        m = match_line(cat, l, order.get("customer"), aliases)
        flags = list(m["flags"])
        if l.get("change") == "modified_by_email":
            flags.append("conflict_pdf_vs_email")
        if l.get("change") == "added_by_email":
            flags.append("added_in_email")
        out.append(dict(n=i, raw_text=l.get("raw_text", ""), customer_ref=l.get("customer_ref"),
                        ref=m["ref"], designation=m["designation"], quantity=l.get("quantity"),
                        unit_price=l.get("unit_price"), confidence=m["confidence"], method=m["method"],
                        flags=sorted(set(flags)), candidates=m["candidates"], note=l.get("note", "")))
    if not out:
        order.setdefault("notes", []).append("Aucune ligne de commande détectée.")
    order["lines"] = out
    meta["seconds_total"] = round(time.time() - t0, 2)
    order["_meta"] = meta
    return order
