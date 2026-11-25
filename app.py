import json
import time
from pathlib import Path

import pandas as pd
import streamlit as st

from ordo import ar, export
from ordo.config import DEMO, api_key, model
from ordo.ingest import Message, load_any, parse_eml
from ordo.match import load_aliases, save_alias
from ordo.pipeline import catalogue, process

st.set_page_config(page_title="Ordo, commandes vers ERP", page_icon="📥", layout="wide")

FLAG_FR = {
    "ambiguous": "Plusieurs articles possibles",
    "unknown_ref": "Référence inconnue",
    "unknown_ref_designation_used": "Réf. inconnue, trouvée par la désignation",
    "typo_suspected": "Faute de frappe probable",
    "match_to_verify": "Correspondance à vérifier",
    "pack_size_to_confirm": "Conditionnement à confirmer",
    "conflict_pdf_vs_email": "Email et PDF en désaccord",
    "added_in_email": "Ligne ajoutée dans l'email",
    "ref_prefix_underscore": "Préfixe _ retiré",
    "qty_missing": "Quantité manquante",
    "learned_alias": "Choix appris d'une correction précédente",
}
INFO_ONLY = {"ref_prefix_underscore", "learned_alias"}
cat = catalogue()
REFS = sorted(r["ref"] for r in cat.rows)

ss = st.session_state
ss.setdefault("history", [])
ss.setdefault("ver", 0)


def status(l):
    if not l.get("ref") or not l.get("quantity"):
        return "Bloquant"
    if set(l.get("flags", [])) - INFO_ONLY:
        return "À vérifier"
    return "OK"


def demo_orders():
    out = {}
    for d in sorted(DEMO.iterdir()):
        e = json.loads((d / "expected.json").read_text(encoding="utf-8"))
        out[f"{d.name} · {e['title']}"] = d
    return out


# ---------------- sidebar
with st.sidebar:
    st.title("Ordo")
    st.caption("Commandes reçues par email → commandes prêtes pour l'ERP")
    has_key = bool(api_key())
    mode_label = st.radio("Lecture des commandes", ["IA (OpenRouter)", "Hors-ligne (règles)"],
                          index=0 if has_key else 1, disabled=not has_key,
                          help="Sans clé OPENROUTER_API_KEY, seul le mode hors-ligne est disponible.")
    mode = "llm" if mode_label.startswith("IA") and has_key else "offline"
    model_id = st.text_input("Modèle", model(), disabled=mode != "llm")
    if not has_key:
        st.info("Aucune clé API trouvée : mode hors-ligne. Ajoute OPENROUTER_API_KEY dans .env ou dans les secrets Streamlit.")
    st.divider()
    st.metric("Articles au catalogue de démo", len(cat.rows))
    st.metric("Alias appris", sum(len(v) for v in load_aliases().values()))
    st.caption("Données de démonstration synthétiques (clients et prix fictifs). Références issues du catalogue FEKU 2026.")

tab_order, tab_eval, tab_cat = st.tabs(["Traiter une commande", "Évaluation et métriques", "Catalogue"])

# ---------------- order tab
with tab_order:
    src = st.radio("Source", ["Commande de démo", "Importer un fichier", "Coller un texte"], horizontal=True)
    msg = None
    if src == "Commande de démo":
        demos = demo_orders()
        choice = st.selectbox("Commande", list(demos))
        if st.button("Lire la commande", type="primary"):
            msg = parse_eml((demos[choice] / "email.eml").read_bytes())
    elif src == "Importer un fichier":
        f = st.file_uploader("Email (.eml), PDF, Excel ou image", type=["eml", "pdf", "xlsx", "png", "jpg", "jpeg", "txt"])
        if f and st.button("Lire la commande", type="primary"):
            msg = load_any(f.name, f.getvalue())
    else:
        txt = st.text_area("Texte de l'email", height=160, placeholder="Bonjour, merci de nous livrer 4 x 469200 ...")
        if txt and st.button("Lire la commande", type="primary"):
            msg = Message(subject="Texte collé", body=txt)

    if msg is not None:
        with st.spinner("Lecture en cours..."):
            order = process(msg, mode=mode, model_id=model_id)
        for l in order["lines"]:
            l["proposed_ref"] = l["ref"]
        ss.msg, ss.order, ss.t_loaded, ss.validated = msg, order, time.time(), False
        ss.ver += 1

    if "order" in ss:
        msg, order = ss.msg, ss.order
        meta = order["_meta"]
        if meta.get("error"):
            st.warning(f"L'IA n'a pas répondu, lecture hors-ligne utilisée. Détail : {meta['error']}")
        left, right = st.columns([2, 3], gap="large")

        with left:
            st.subheader("Email reçu")
            st.caption(f"De : {msg.sender or '-'}  ·  Objet : {msg.subject or '-'}")
            st.text_area("Corps", msg.body or "(vide)", height=180, disabled=True, label_visibility="collapsed")
            for a in msg.attachments:
                with st.expander(f"Pièce jointe : {a.name}" + (" (scan)" if a.is_scan else ""), expanded=False):
                    if a.kind == "pdf":
                        if a.images:
                            st.image(a.images[0], width="stretch")
                        else:
                            import io, pdfplumber
                            with pdfplumber.open(io.BytesIO(a.data)) as p:
                                st.image(p.pages[0].to_image(resolution=90).original, width="stretch")
                    elif a.kind == "xlsx":
                        st.dataframe(pd.DataFrame(a.table).astype(str), hide_index=True)
                    elif a.kind == "image":
                        st.image(a.data, width="stretch")
                    else:
                        st.text(a.text[:2000])

        with right:
            st.subheader("Commande extraite")
            h1, h2, h3, h4 = st.columns(4)
            order["customer"] = h1.text_input("Client", order.get("customer") or "")
            order["order_number"] = h2.text_input("N° commande client", order.get("order_number") or "")
            order["order_date"] = h3.text_input("Date commande", order.get("order_date") or "")
            order["delivery_date"] = h4.text_input("Livraison souhaitée", order.get("delivery_date") or "")
            if order.get("ar_requested", "no") != "no":
                st.info("Le client demande un accusé de réception" + (" sous 48 h." if order["ar_requested"] == "yes_48h" else "."))
            for n in order.get("notes", []):
                st.caption("ℹ️ " + n)

            lines = order["lines"]
            n_ok = sum(status(l) == "OK" for l in lines)
            n_blk = sum(status(l) == "Bloquant" for l in lines)
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Lignes", len(lines))
            m2.metric("OK auto", n_ok)
            m3.metric("À vérifier", len(lines) - n_ok - n_blk)
            m4.metric("Bloquantes", n_blk)
            cost = meta.get("cost_usd") or 0
            m5.metric("Lecture", f"{meta.get('seconds_total', 0)} s")
            st.caption(f"Mode : {meta['mode']}  ·  coût IA : {cost:.4f} $" + (f"  ·  {meta.get('tokens_in')} tokens en entrée" if meta.get("tokens_in") else ""))

        st.markdown("#### Lignes de commande")
        df = pd.DataFrame([{
            "Statut": status(l),
            "Réf. FEKU": l["ref"] or "",
            "Qté": l["quantity"],
            "Alertes": " · ".join(FLAG_FR.get(f, f) for f in l["flags"]) + (f" ({l['note']})" if l.get("note") else ""),
            "Suggestions": ", ".join(l["candidates"][:5]) if not l["ref"] or l["flags"] else "",
            "Texte client": l["raw_text"],
            "Désignation": l["designation"],
            "Prix U. HT": l["unit_price"],
            "Confiance": float(l["confidence"]),
        } for l in lines])

        def apply_edits():
            ed = ss.get(f"editor_{ss.ver}", {})
            for i, ch in ed.get("edited_rows", {}).items():
                l = lines[int(i)]
                if "Réf. FEKU" in ch:
                    l["ref"] = ch["Réf. FEKU"] or None
                    row = cat.get(l["ref"]) if l["ref"] else None
                    l["designation"] = row["designation"] if row else ""
                    l["flags"] = [f for f in l["flags"] if f in ("pack_size_to_confirm", "conflict_pdf_vs_email", "added_in_email")] if l["ref"] else ["unknown_ref"]
                    if row and row.get("pack_size") and int(float(row["pack_size"])) > 1 and "pack_size_to_confirm" not in l["flags"]:
                        l["flags"].append("pack_size_to_confirm")
                    l["confidence"] = 1.0 if l["ref"] else 0.0
                    l["edited"] = True
                if "Qté" in ch:
                    l["quantity"] = ch["Qté"]
                    l["flags"] = [f for f in l["flags"] if f not in ("qty_missing", "conflict_pdf_vs_email")]
                if "Prix U. HT" in ch:
                    l["unit_price"] = ch["Prix U. HT"]
                if ch.get("Statut") == "OK":
                    l["flags"] = [f for f in l["flags"] if f in INFO_ONLY]
                    l["edited"] = True
            ss.ver += 1

        st.data_editor(
            df, key=f"editor_{ss.ver}", on_change=apply_edits, hide_index=True, width="stretch",
            column_config={
                "Statut": st.column_config.SelectboxColumn(options=["OK", "À vérifier", "Bloquant"], width="small",
                                                           help="Passe une ligne à OK une fois vérifiée."),
                "Réf. FEKU": st.column_config.SelectboxColumn(options=[""] + REFS, width="small"),
                "Texte client": st.column_config.TextColumn(disabled=True, width="medium"),
                "Désignation": st.column_config.TextColumn(disabled=True, width="medium"),
                "Qté": st.column_config.NumberColumn(min_value=0, step=1, width="small"),
                "Prix U. HT": st.column_config.NumberColumn(format="%.2f", width="small"),
                "Confiance": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.2f", width="small"),
                "Alertes": st.column_config.TextColumn(disabled=True, width="medium"),
                "Suggestions": st.column_config.TextColumn(disabled=True, width="small", help="Articles candidats du catalogue"),
            })
        st.caption("Choisis la bonne référence dans la colonne Réf. FEKU, ou passe le statut à OK après vérification.")

        blocking = [l for l in lines if status(l) == "Bloquant"]
        pending = [l for l in lines if status(l) == "À vérifier"]
        c1, c2 = st.columns([1, 2])
        force = c2.checkbox("Valider malgré les lignes à vérifier", value=False, disabled=not pending or bool(blocking))
        if c1.button("Valider la commande", type="primary", disabled=bool(blocking) or (bool(pending) and not force)):
            learned = 0
            for l in lines:
                if l.get("edited") and l["ref"] and l["ref"] != l.get("proposed_ref"):
                    save_alias(order["customer"], l.get("customer_ref") or l["raw_text"], l["ref"])
                    learned += 1
            corrected = sum(1 for l in lines if l.get("edited"))
            ss.history.append(dict(
                heure=time.strftime("%H:%M:%S"), client=order["customer"], commande=order["order_number"],
                lignes=len(lines), ok_sans_correction=sum(1 for l in lines if not l.get("edited") and l["ref"] == l.get("proposed_ref")),
                corrigees=corrected, alias_appris=learned, lecture_s=meta.get("seconds_total"),
                temps_total_s=round(time.time() - ss.t_loaded, 1), cout_usd=round(cost, 5), mode=meta["mode"]))
            ss.validated = True
            if learned:
                st.toast(f"{learned} correction(s) mémorisée(s) pour ce client")
        if blocking:
            st.error(f"{len(blocking)} ligne(s) bloquante(s) : choisis une référence et une quantité.")

        if ss.get("validated"):
            st.success("Commande validée. Fichiers prêts.")
            base = (order["order_number"] or "commande").replace("/", "-")
            d1, d2 = st.columns(2)
            d1.download_button("Export ERP (.csv)", export.to_csv(order), f"{base}_import_erp.csv", "text/csv",
                               help="Format générique : le format d'import Simax reste à confirmer.")
            d2.download_button("Accusé de réception (.pdf)", ar.pdf(order), f"{ar.ar_number(order)}.pdf", "application/pdf")
            st.text_area("Email d'accusé de réception (brouillon)", ar.email_text(order), height=260)

# ---------------- eval tab
with tab_eval:
    st.subheader("Historique de la session")
    if ss.history:
        h = pd.DataFrame(ss.history)
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Commandes validées", len(h))
        k2.metric("Lignes sans correction", f"{h.ok_sans_correction.sum() / max(h.lignes.sum(), 1):.0%}")
        k3.metric("Temps moyen par commande", f"{h.temps_total_s.mean():.0f} s")
        k4.metric("Coût IA moyen", f"{h.cout_usd.mean():.4f} $")
        st.dataframe(h, hide_index=True, width="stretch")
    else:
        st.caption("Aucune commande validée pour l'instant.")

    st.subheader("Banc d'essai sur les 10 commandes de démo")
    st.caption("Compare la sortie à la vérité attendue (expected.json). Le mode hors-ligne a été écrit en regardant ces 10 cas : "
               "son score n'est pas une preuve. Le score qui compte est celui du mode IA, puis sur de vraies commandes.")
    if st.button(f"Lancer l'évaluation ({'IA' if mode == 'llm' else 'hors-ligne'})"):
        import eval as ev
        with st.spinner("Évaluation..."):
            rows, t = ev.main(mode)
        cols = {"id": "Cas", "lines_found": "Lignes trouvées", "lines_expected": "Lignes attendues", "ref_ok": "Réf. justes",
                "ref_total": "Réf. attendues", "qty_ok": "Qté justes", "flag_hits": "Alertes levées", "flag_total": "Alertes attendues",
                "safe_refusals": "Refus prudents", "refusal_total": "Cas ambigus", "wrong_auto": "Erreurs silencieuses",
                "seconds": "Secondes", "cost_usd": "Coût $"}
        st.dataframe(pd.DataFrame(rows)[list(cols)].rename(columns=cols), hide_index=True, width="stretch")
        a, b, c, d = st.columns(4)
        a.metric("Bonnes références", f"{t['ref_ok']}/{t['ref_total']}")
        b.metric("Bonnes quantités", f"{t['qty_ok']}/{t['lines_expected']}")
        c.metric("Alertes attendues levées", f"{t['flag_hits']}/{t['flag_total']}")
        d.metric("Erreurs silencieuses", t["wrong_auto"], help="Mauvaise référence proposée SANS alerte : le pire cas.")

with tab_cat:
    st.dataframe(pd.DataFrame(cat.rows)[["ref", "designation", "family", "page", "pack_info", "verification"]],
                 hide_index=True, width="stretch")
