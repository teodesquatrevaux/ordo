import html
import json
import time

import pandas as pd
import streamlit as st

from ordo import ar, export
from ordo.config import DEMO, api_key, model, secret
from ordo.ingest import Message, load_any, parse_eml
from ordo.match import load_aliases, save_alias
from ordo.pipeline import catalogue, process
from ordo.ui import CSS

st.set_page_config(page_title="Ordo", layout="wide", initial_sidebar_state="collapsed")
st.markdown(CSS, unsafe_allow_html=True)

FLAG_FR = {
    "ambiguous": "Plusieurs articles possibles",
    "unknown_ref": "Référence inconnue",
    "unknown_ref_designation_used": "Référence inconnue, trouvée par la désignation",
    "typo_suspected": "Faute de frappe probable",
    "match_to_verify": "Correspondance à vérifier",
    "pack_size_to_confirm": "Conditionnement à confirmer",
    "conflict_pdf_vs_email": "L'email et la pièce jointe ne disent pas la même quantité",
    "added_in_email": "Ligne ajoutée dans l'email",
    "ref_prefix_underscore": "Préfixe _ retiré",
    "qty_missing": "Quantité manquante",
    "learned_alias": "Reconnu grâce à une correction précédente",
}
INFO_ONLY = {"ref_prefix_underscore", "learned_alias"}
REF_FLAGS = {"ambiguous", "unknown_ref", "unknown_ref_designation_used", "typo_suspected", "match_to_verify"}
KEEP_AFTER_CHOICE = ("pack_size_to_confirm", "conflict_pdf_vs_email", "added_in_email")
ERP_URL = secret("ERP_DEMO_URL", "https://claude.ai/artifact/4igwQb6qJ14sPawX5shdrM")

cat = catalogue()
REFS = sorted(r["ref"] for r in cat.rows)
ss = st.session_state
ss.setdefault("history", [])
ss.setdefault("ver", 0)


def esc(v):
    return html.escape(str(v if v is not None else ""))


def fmt_qty(q):
    if q in (None, ""):
        return "?"
    q = float(q)
    return f"{q:g}".replace(".", ",")


def status(l):
    if l.get("removed"):
        return "Retirée"
    if not l.get("ref") or not l.get("quantity"):
        return "Bloquant"
    if set(l.get("flags", [])) - INFO_ONLY:
        return "À vérifier"
    return "OK"


def step(n, title, active=True, hint=""):
    st.markdown(f'<div class="o-step{"" if active else " off"}"><b>{n}</b><h3>{esc(title)}</h3></div>'
                + (f'<p class="o-hint">{esc(hint)}</p>' if hint else ""), unsafe_allow_html=True)


def demo_orders():
    out = {}
    for d in sorted(DEMO.iterdir()):
        e = json.loads((d / "expected.json").read_text(encoding="utf-8"))
        out[f"{d.name}, {e['title']}"] = d
    return out


# ---------------- actions on a line (one click each)
def choose(i, ref):
    l = ss.order["lines"][i]
    row = cat.get(ref)
    l["ref"], l["designation"] = row["ref"], row["designation"]
    l["flags"] = [f for f in l["flags"] if f in KEEP_AFTER_CHOICE]
    if row.get("pack_size") and int(float(row["pack_size"])) > 1 and "pack_size_to_confirm" not in l["flags"]:
        l["flags"].append("pack_size_to_confirm")
    l["confidence"], l["edited"] = 1.0, True
    ss.validated = False


def confirm(i):
    l = ss.order["lines"][i]
    q = ss.get(f"q_{ss.ver}_{i}")
    if q:
        l["quantity"] = q
    l["flags"] = [f for f in l["flags"] if f in INFO_ONLY]
    l["edited"] = True
    ss.validated = False


def remove(i):
    ss.order["lines"][i]["removed"] = True
    ss.validated = False


def restore(i):
    ss.order["lines"][i]["removed"] = False


def final_order(order):
    return {**order, "lines": [l for l in order["lines"] if not l.get("removed")]}


# ---------------- sidebar: settings
with st.sidebar:
    st.header("Réglages")
    has_key = bool(api_key())
    mode_label = st.radio("Lecture des commandes", ["IA (OpenRouter)", "Hors-ligne (règles)"],
                          index=0 if has_key else 1, disabled=not has_key,
                          help="Sans clé OPENROUTER_API_KEY, seul le mode hors-ligne est disponible.")
    mode = "llm" if mode_label.startswith("IA") and has_key else "offline"
    model_id = st.text_input("Modèle", model(), disabled=mode != "llm")
    if not has_key:
        st.caption("Aucune clé API : lecture hors-ligne. Ajoute OPENROUTER_API_KEY dans .env ou dans les secrets Streamlit.")
    st.divider()
    st.caption(f"{len(cat.rows)} articles au catalogue de démo, {sum(len(v) for v in load_aliases().values())} correspondances apprises.")
    st.caption("Données de démonstration synthétiques : clients et prix fictifs. Références issues du catalogue d'un distributeur (2026).")

st.markdown(
    '<div class="o-top"><div class="o-mark">Ordo<span></span></div>'
    f'<div class="o-tag">Les commandes reçues par email, prêtes pour l\'ERP'
    f'<span class="o-pill">Lecture : {"IA" if mode == "llm" else "hors-ligne"}</span></div></div>',
    unsafe_allow_html=True)

tab_order, tab_eval, tab_cat = st.tabs(["Traiter une commande", "Évaluation", "Catalogue"])

# ================= order tab
with tab_order:
    step(1, "Recevoir une commande",
         hint="Un email avec un PDF, un fichier Excel, un scan, ou juste du texte. Ordo lit les lignes et les retrouve dans le catalogue.")
    src = st.radio("Source", ["Commande de démo", "Importer un fichier", "Coller un texte"], horizontal=True,
                   label_visibility="collapsed")
    msg = None
    if src == "Commande de démo":
        demos = demo_orders()
        c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
        choice = c1.selectbox("Commande de démo", list(demos))
        if c2.button("Lire la commande", type="primary", width="stretch"):
            msg = parse_eml((demos[choice] / "email.eml").read_bytes())
    elif src == "Importer un fichier":
        f = st.file_uploader("Email (.eml), PDF, Excel ou image", type=["eml", "pdf", "xlsx", "png", "jpg", "jpeg", "txt"])
        if f and st.button("Lire la commande", type="primary"):
            msg = load_any(f.name, f.getvalue())
    else:
        txt = st.text_area("Texte de l'email", height=140, placeholder="Bonjour, merci de nous livrer 4 x 469200 ...")
        if txt and st.button("Lire la commande", type="primary"):
            msg = Message(subject="Texte collé", body=txt)

    if msg is not None:
        with st.spinner("Lecture en cours..."):
            order = process(msg, mode=mode, model_id=model_id)
        for l in order["lines"]:
            l["proposed_ref"] = l["ref"]
            l["auto_ok"] = status(l) == "OK"
        ss.msg, ss.order, ss.t_loaded, ss.validated = msg, order, time.time(), False
        ss.ver += 1

    has_order = "order" in ss
    step(2, "Vérifier", active=has_order,
         hint="" if has_order else "La commande lue apparaîtra ici, avec les seules lignes qui demandent votre avis.")

    if has_order:
        msg, order = ss.msg, ss.order
        meta = order["_meta"]
        lines = order["lines"]
        if meta.get("error"):
            st.warning(f"L'IA n'a pas répondu, lecture hors-ligne utilisée. Détail : {meta['error']}")

        live = [l for l in lines if not l.get("removed")]
        n_ok = sum(status(l) == "OK" for l in live)
        n_blk = sum(status(l) == "Bloquant" for l in live)
        n_chk = len(live) - n_ok - n_blk
        cost = meta.get("cost_usd") or 0
        auto = sum(1 for l in lines if l.get("auto_ok"))

        left, right = st.columns([2, 3], gap="large")
        with left:
            att = "".join(f"<div class='h'>Pièce jointe : {esc(a.name)}{' (scan)' if a.is_scan else ''}</div>" for a in msg.attachments)
            st.markdown(f"<div class='o-mail'><div class='h'>De : {esc(msg.sender or '-')}<br>Objet : {esc(msg.subject or '-')}</div>"
                        f"<pre>{esc(msg.body or '(vide)')}</pre>{att}</div>", unsafe_allow_html=True)
            for a in msg.attachments:
                with st.expander(f"Voir {a.name}", expanded=False):
                    if a.kind == "pdf":
                        if a.images:
                            st.image(a.images[0], width="stretch")
                        else:
                            import io
                            import pdfplumber
                            with pdfplumber.open(io.BytesIO(a.data)) as p:
                                st.image(p.pages[0].to_image(resolution=90).original, width="stretch")
                    elif a.kind == "xlsx":
                        st.dataframe(pd.DataFrame(a.table).astype(str), hide_index=True)
                    elif a.kind == "image":
                        st.image(a.data, width="stretch")
                    else:
                        st.text(a.text[:2000])
        with right:
            st.markdown(
                f"<div class='o-order'><div class='who'>{esc(order.get('customer') or 'Client inconnu')}</div>"
                f"<div class='meta'>Commande {esc(order.get('order_number') or 'sans numéro')}"
                f"{', du ' + esc(order['order_date']) if order.get('order_date') else ''}"
                f"{', livraison souhaitée ' + esc(order['delivery_date']) if order.get('delivery_date') else ''}"
                f"<br>Lecture {esc(meta['mode'])} en {meta.get('seconds_total', 0)} s, coût IA {cost:.4f} $</div>"
                "<div class='o-figs'>"
                f"<div><strong>{len(live)}</strong>lignes</div>"
                f"<div><strong>{auto} sur {len(lines)}</strong>reconnues sans vous</div>"
                f"<div class='{'warn' if n_chk else ''}'><strong>{n_chk}</strong>à vérifier</div>"
                f"<div class='{'bad' if n_blk else ''}'><strong>{n_blk}</strong>bloquantes</div>"
                "</div></div>", unsafe_allow_html=True)
            if order.get("ar_requested", "no") != "no":
                st.markdown(f"<p class='o-note'>Le client demande un accusé de réception"
                            f"{' sous 48 h' if order['ar_requested'] == 'yes_48h' else ''}.</p>", unsafe_allow_html=True)
            for n in order.get("notes", []):
                st.markdown(f"<p class='o-note'>{esc(n)}</p>", unsafe_allow_html=True)
            with st.expander("Corriger le client, le numéro ou les dates"):
                h1, h2 = st.columns(2)
                order["customer"] = h1.text_input("Client", order.get("customer") or "")
                order["order_number"] = h2.text_input("N° commande client", order.get("order_number") or "")
                h3, h4 = st.columns(2)
                order["order_date"] = h3.text_input("Date commande", order.get("order_date") or "")
                order["delivery_date"] = h4.text_input("Livraison souhaitée", order.get("delivery_date") or "")

        # ---- the order sheet
        rows = []
        for k, l in enumerate(lines, 1):
            s = status(l)
            cls = {"À vérifier": "doubt", "Bloquant": "block", "Retirée": "gone"}.get(s, "")
            badge = {"OK": "<span class='st ok'>Reconnu</span>", "À vérifier": "<span class='st doubt'>À vérifier</span>",
                     "Bloquant": "<span class='st block'>Bloquant</span>", "Retirée": "<span class='st'>Retirée</span>"}[s]
            reasons = [FLAG_FR.get(f, f) for f in l["flags"] if s != "OK" or f in INFO_ONLY]
            why = f"<div class='why'>{esc(', '.join(reasons))}</div>" if reasons else ""
            cref = f"<code>{esc(l['customer_ref'])}</code> " if l.get("customer_ref") and l["customer_ref"] not in (l.get("raw_text") or "") else ""
            art = (f"<code>{esc(l['ref'])}</code><div class='des'>{esc(l['designation'])}</div>" if l.get("ref")
                   else "<span class='des'>?</span>")
            price = "" if l.get("unit_price") in (None, "") else f"{float(l['unit_price']):.2f} €".replace(".", ",")
            rows.append(f"<tr class='{cls}'><td class='n'>{k}</td><td class='src'>{cref}{esc(l.get('raw_text'))}</td>"
                        f"<td class='q'>{fmt_qty(l.get('quantity'))}</td><td>{art}</td><td class='p hide-sm'>{price}</td>"
                        f"<td>{badge}{why}</td></tr>")
        st.markdown("<table class='o-sheet'><thead><tr><th></th><th>Écrit par le client</th><th class='q'>Qté</th>"
                    "<th>Article du catalogue</th><th class='p hide-sm'>Prix HT</th><th>Statut</th></tr></thead><tbody>"
                    + "".join(rows) + "</tbody></table>", unsafe_allow_html=True)

        # ---- one card per line that needs a person
        for i, l in enumerate(lines):
            s = status(l)
            if s == "Retirée":
                continue
            if s == "OK":
                continue
            with st.container(key=f"{'fixb' if s == 'Bloquant' else 'fix'}_{ss.ver}_{i}"):
                reasons = [FLAG_FR.get(f, f) for f in l["flags"] if f not in INFO_ONLY]
                st.markdown(f"<div class='o-q'>Ligne {i + 1} : <b>« {esc(l.get('raw_text'))} »</b> "
                            f"<small>(qté {fmt_qty(l.get('quantity'))})</small></div>"
                            f"<div class='o-reasons'>{esc(', '.join(reasons)) or 'Quantité à renseigner'}"
                            f"{' : ' + esc(l['note']) if l.get('note') else ''}"
                            f"{' : ' + esc(l.get('pack_info') or cat.get(l['ref']).get('pack_info')) if 'pack_size_to_confirm' in l['flags'] and l.get('ref') else ''}</div>",
                            unsafe_allow_html=True)
                needs_ref = not l.get("ref") or bool(set(l["flags"]) & REF_FLAGS)
                cands = [c for c in (l.get("candidates") or []) if cat.get(c)][:3]
                if needs_ref and cands:
                    cols = st.columns(max(len(cands), 3))
                    for col, c in zip(cols, cands):
                        row = cat.get(c)
                        col.markdown(f"<div class='o-cand'><span class='o-ref'>{esc(row['ref'])}</span><br>{esc(row['designation'][:90])}</div>",
                                     unsafe_allow_html=True)
                        col.button(f"Choisir {row['ref']}", key=f"c_{ss.ver}_{i}_{c}", on_click=choose, args=(i, row["ref"]),
                                   type="primary" if c == l.get("ref") else "secondary", width="stretch")
                a1, a2, a3, a4 = st.columns([2, 1.2, 1.2, 1.2], vertical_alignment="bottom")
                if needs_ref:
                    other = a1.selectbox("Autre référence du catalogue", REFS, index=None, key=f"o_{ss.ver}_{i}",
                                         placeholder="Chercher une référence", format_func=lambda r: f"{r}, {cat.get(r)['designation'][:50]}")
                    if other:
                        a2.button("Prendre celle-ci", key=f"ob_{ss.ver}_{i}", on_click=choose, args=(i, other), width="stretch")
                else:
                    a1.number_input("Quantité", min_value=0.0, step=1.0, value=float(l.get("quantity") or 0),
                                    key=f"q_{ss.ver}_{i}")
                    a2.button("Confirmer", key=f"ok_{ss.ver}_{i}", on_click=confirm, args=(i,), type="primary", width="stretch")
                a4.button("Retirer la ligne", key=f"rm_{ss.ver}_{i}", on_click=remove, args=(i,), width="stretch")

        gone = [i for i, l in enumerate(lines) if l.get("removed")]
        if gone:
            g1, _ = st.columns([2, 3])
            for i in gone:
                g1.button(f"Remettre la ligne {i + 1}", key=f"rs_{ss.ver}_{i}", on_click=restore, args=(i,))

        # ---------------- 3. validate and send to the ERP
        step(3, "Valider et envoyer vers l'ERP", active=True)
        blocking = [l for l in live if status(l) == "Bloquant"]
        pending = [l for l in live if status(l) == "À vérifier"]
        if blocking:
            st.markdown(f"<p class='o-blocked'>{len(blocking)} ligne(s) bloquante(s) : choisissez une référence et une quantité, ou retirez la ligne.</p>",
                        unsafe_allow_html=True)
        elif pending:
            st.markdown(f"<p class='o-wait'>Encore {len(pending)} ligne(s) à vérifier.</p>", unsafe_allow_html=True)
        c1, c2 = st.columns([1, 2], vertical_alignment="center")
        force = c2.checkbox("Valider quand même les lignes à vérifier", value=False, disabled=not pending or bool(blocking))
        if c1.button("Valider la commande", type="primary", disabled=bool(blocking) or (bool(pending) and not force) or not live):
            learned = 0
            for l in live:
                if l.get("edited") and l["ref"] and l["ref"] != l.get("proposed_ref"):
                    save_alias(order["customer"], l.get("customer_ref") or l["raw_text"], l["ref"])
                    learned += 1
            ss.history.append(dict(
                heure=time.strftime("%H:%M:%S"), client=order["customer"], commande=order["order_number"],
                lignes=len(live), ok_sans_correction=sum(1 for l in live if not l.get("edited") and l["ref"] == l.get("proposed_ref")),
                corrigees=sum(1 for l in live if l.get("edited")), alias_appris=learned, lecture_s=meta.get("seconds_total"),
                temps_total_s=round(time.time() - ss.t_loaded, 1), cout_usd=round(cost, 5), mode=meta["mode"]))
            ss.validated, ss.learned = True, learned

        if ss.get("validated"):
            fo = final_order(order)
            base = (order["order_number"] or "commande").replace("/", "-")
            learned = ss.get("learned", 0)
            st.markdown(f"<div class='o-done'><b>Commande validée.</b> Le fichier d'import est prêt"
                        f"{f', et {learned} correction(s) sont mémorisées pour ce client : sa prochaine commande passera seule' if learned else ''}."
                        "</div>", unsafe_allow_html=True)
            d1, d2, d3 = st.columns(3)
            d1.download_button("Télécharger le fichier d'import (CSV)", export.to_csv(fo), f"{base}_import_erp.csv",
                               "text/csv", type="primary", width="stretch")
            if ERP_URL:
                d2.link_button("Ouvrir l'ERP de démo", ERP_URL, width="stretch")
            d3.download_button("Accusé de réception (PDF)", ar.pdf(fo), f"{ar.ar_number(fo)}.pdf", "application/pdf", width="stretch")
            st.markdown("<p class='o-note'>Dans l'ERP : « Importer des commandes », puis déposez le fichier. L'ERP vérifie chaque ligne, "
                        "crée la commande et garde une trace dans son journal des imports. Format générique : le format d'import réel "
                        "de l'ERP du distributeur reste à confirmer.</p>", unsafe_allow_html=True)
            with st.expander("Brouillon de l'email d'accusé de réception"):
                st.text_area("Email", ar.email_text(fo), height=260, label_visibility="collapsed")

        with st.expander("Modifier dans un tableau (quantités, prix)"):
            df = pd.DataFrame([{"Ligne": k, "Réf.": l["ref"] or "", "Qté": l["quantity"], "Prix U. HT": l["unit_price"]}
                               for k, l in enumerate(lines, 1)])

            def apply_edits():
                ed = ss.get(f"editor_{ss.ver}", {})
                for r, ch in ed.get("edited_rows", {}).items():
                    l = lines[int(r)]
                    if "Qté" in ch:
                        l["quantity"] = ch["Qté"]
                        l["flags"] = [f for f in l["flags"] if f not in ("qty_missing", "conflict_pdf_vs_email")]
                        l["edited"] = True
                    if "Prix U. HT" in ch:
                        l["unit_price"] = ch["Prix U. HT"]
                ss.validated = False
                ss.ver += 1

            st.data_editor(df, key=f"editor_{ss.ver}", on_change=apply_edits, hide_index=True, width="stretch",
                           disabled=["Ligne", "Réf."],
                           column_config={"Qté": st.column_config.NumberColumn(min_value=0, step=1),
                                          "Prix U. HT": st.column_config.NumberColumn(format="%.2f")})

# ================= eval tab
with tab_eval:
    st.subheader("Commandes traitées pendant cette séance")
    if ss.history:
        h = pd.DataFrame(ss.history)
        st.markdown(
            "<div class='o-order'><div class='o-figs' style='margin-top:0;padding-top:0;border-top:0'>"
            f"<div><strong>{len(h)}</strong>commandes validées</div>"
            f"<div><strong>{h.ok_sans_correction.sum() / max(h.lignes.sum(), 1):.0%}</strong>lignes sans correction</div>"
            f"<div><strong>{h.temps_total_s.mean():.0f} s</strong>par commande, vérification comprise</div>"
            f"<div><strong>{h.cout_usd.mean():.4f} $</strong>coût IA moyen</div></div></div>", unsafe_allow_html=True)
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
        st.markdown(
            "<div class='o-order'><div class='o-figs' style='margin-top:0;padding-top:0;border-top:0'>"
            f"<div><strong>{t['ref_ok']} sur {t['ref_total']}</strong>bonnes références</div>"
            f"<div><strong>{t['qty_ok']} sur {t['lines_expected']}</strong>bonnes quantités</div>"
            f"<div><strong>{t['flag_hits']} sur {t['flag_total']}</strong>lignes à doute signalées</div>"
            f"<div class='{'bad' if t['wrong_auto'] else ''}'><strong>{t['wrong_auto']}</strong>erreurs silencieuses</div>"
            "</div></div>", unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(rows)[list(cols)].rename(columns=cols), hide_index=True, width="stretch")

with tab_cat:
    st.caption("Le catalogue de démo dans lequel Ordo cherche les articles. En production : l'export articles de l'ERP du distributeur.")
    st.dataframe(pd.DataFrame(cat.rows)[["ref", "designation", "family", "page", "pack_info", "verification"]],
                 hide_index=True, width="stretch")
