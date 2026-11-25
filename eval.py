"""Scores the pipeline against the 10 synthetic orders (demo/*/expected.json).
Usage: python eval.py [offline|llm]"""
import json
import sys
from pathlib import Path
from ordo.ingest import parse_eml
from ordo.pipeline import process

KEY_FLAGS = {"ambiguous", "unknown_ref", "pack_size_to_confirm", "conflict_pdf_vs_email", "added_in_email", "typo_suspected"}


def score(exp, got):
    res = dict(lines_expected=len(exp["lines"]), lines_found=len(got["lines"]), ref_ok=0, ref_total=0,
               qty_ok=0, flag_hits=0, flag_total=0, safe_refusals=0, refusal_total=0, wrong_auto=0)
    pool = list(got["lines"])
    for e in exp["lines"]:
        # pair expected line with the found line that has the same raw ref/text, else same position
        g = next((x for x in pool if (x.get("customer_ref") or "").strip(" .").upper().lstrip("_") == str(e["raw"]).upper().lstrip("_")), None)
        if g is None:
            g = next((x for x in pool if e["raw"][:12].lower() in (x.get("raw_text") or "").lower()), None)
        if g is None and pool:
            g = pool[0]
        if g is None:
            res["ref_total"] += e["expected_ref"] is not None
            res["refusal_total"] += e["expected_ref"] is None
            res["flag_total"] += len(set(e["flags"]) & KEY_FLAGS)
            continue
        pool.remove(g)
        if g.get("quantity") is not None and float(g["quantity"]) == float(e["qty"]):
            res["qty_ok"] += 1
        if e["expected_ref"] is None:
            res["refusal_total"] += 1
            if g["ref"] is None:
                res["safe_refusals"] += 1
            elif not g["flags"]:
                res["wrong_auto"] += 1
        else:
            res["ref_total"] += 1
            if g["ref"] == e["expected_ref"]:
                res["ref_ok"] += 1
            elif not g["flags"]:
                res["wrong_auto"] += 1
        for f in set(e["flags"]) & KEY_FLAGS:
            res["flag_total"] += 1
            res["flag_hits"] += f in g["flags"]
    return res


def main(mode="offline"):
    tot, rows = {}, []
    for d in sorted(Path("demo").iterdir()):
        exp = json.loads((d / "expected.json").read_text(encoding="utf-8"))
        got = process(parse_eml((d / "email.eml").read_bytes()), mode=mode, aliases={})  # no learned aliases: reproducible
        r = score(exp, got)
        r["id"], r["seconds"], r["cost_usd"] = d.name, got["_meta"].get("seconds_total"), got["_meta"].get("cost_usd") or 0
        rows.append(r)
        for k, v in r.items():
            if isinstance(v, (int, float)) and k != "id":
                tot[k] = tot.get(k, 0) + v
    return rows, tot


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "offline"
    rows, t = main(mode)
    for r in rows:
        print(f"{r['id']}  lignes {r['lines_found']}/{r['lines_expected']}  réf {r['ref_ok']}/{r['ref_total']}  qté {r['qty_ok']}/{r['lines_expected']}"
              f"  alertes {r['flag_hits']}/{r['flag_total']}  refus sûrs {r['safe_refusals']}/{r['refusal_total']}  erreurs silencieuses {r['wrong_auto']}  {r['seconds']}s")
    print(f"\nTOTAL réf {t['ref_ok']}/{t['ref_total']}  qté {t['qty_ok']}/{t['lines_expected']}  alertes {t['flag_hits']}/{t['flag_total']}"
          f"  refus sûrs {t['safe_refusals']}/{t['refusal_total']}  erreurs silencieuses {t['wrong_auto']}  coût {t['cost_usd']:.4f} USD")
