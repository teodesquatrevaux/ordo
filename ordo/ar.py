"""Acknowledgement of receipt (AR): PDF + email draft, from a VALIDATED order.
No lead time is invented: the departure date stays 'à confirmer'."""
import io
from datetime import date
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib import colors


def ar_number(order):
    base = (order.get("order_number") or "SANS-NUM").replace(" ", "_")
    return f"AR-{date.today().strftime('%Y%m%d')}-{base}"


def _wrap(c, text, x, y, width_chars):
    words, line, lines = str(text).split(), "", []
    for w in words:
        if len(line) + len(w) + 1 > width_chars:
            lines.append(line)
            line = w
        else:
            line = (line + " " + w).strip()
    lines.append(line)
    for i, l in enumerate(lines[:2]):
        c.drawString(x, y - i * 3.5 * mm, l)
    return min(len(lines), 2)


def pdf(order):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    no = ar_number(order)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(20 * mm, H - 25 * mm, "ACCUSÉ DE RÉCEPTION DE COMMANDE")
    c.setFont("Helvetica", 9)
    info = [f"AR n° {no}    émis le {date.today().strftime('%d/%m/%Y')}",
            f"Client : {order.get('customer') or ''}",
            f"Votre commande n° {order.get('order_number') or '(non communiqué)'} du {order.get('order_date') or 'à confirmer'}",
            f"Livraison souhaitée : {order.get('delivery_date') or 'non précisée'}  (date de départ à confirmer)"]
    for i, t in enumerate(info):
        c.drawString(20 * mm, H - (35 + i * 5) * mm, t)
    y = H - 62 * mm
    xs = [20, 42, 125, 140, 165]
    c.setFont("Helvetica-Bold", 8)
    for x, h in zip(xs, ["Réf.", "Désignation", "Qté", "Prix U. HT", "Total HT"]):
        c.drawString(x * mm, y, h)
    c.line(20 * mm, y - 2 * mm, 190 * mm, y - 2 * mm)
    y -= 7 * mm
    c.setFont("Helvetica", 8)
    total, complete = 0.0, True
    for l in order["lines"]:
        if y < 30 * mm:
            c.showPage(); c.setFont("Helvetica", 8); y = H - 25 * mm
        c.drawString(xs[0] * mm, y, str(l.get("ref") or "?"))
        n = _wrap(c, l.get("designation") or l.get("raw_text", ""), xs[1] * mm, y, 55)
        q = float(l.get("quantity") or 0)
        c.drawRightString(135 * mm, y, f"{q:g}")
        if l.get("unit_price") not in (None, ""):
            p = float(l["unit_price"]); total += p * q
            c.drawRightString(160 * mm, y, f"{p:.2f}"); c.drawRightString(188 * mm, y, f"{p * q:.2f}")
        else:
            complete = False
            c.drawString(xs[3] * mm, y, "selon tarif")
        y -= (4 + 3.5 * n) * mm
    c.line(20 * mm, y, 190 * mm, y)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(20 * mm, y - 6 * mm, f"Total HT : {total:.2f} EUR" + ("" if complete else " (hors lignes au tarif en vigueur)"))
    c.setFont("Helvetica-Oblique", 7); c.setFillColor(colors.red)
    c.drawString(20 * mm, 12 * mm, "Brouillon généré par Ordo (POC) : à relire avant envoi.")
    c.save()
    return buf.getvalue()


def email_text(order):
    lines = "\n".join(f"- {l.get('ref') or '?'} : {(l.get('designation') or '')[:70]} x {float(l.get('quantity') or 0):g}"
                      for l in order["lines"])
    num = order.get("order_number") or "(sans numéro)"
    return f"""Objet : Accusé de réception de votre commande {num}

Bonjour,

Nous avons bien reçu votre commande {num}{' du ' + order['order_date'] if order.get('order_date') else ''} et vous en remercions.

Récapitulatif :
{lines}

Livraison souhaitée : {order.get('delivery_date') or 'non précisée'}. Nous vous confirmons la date de départ dans les meilleurs délais.

Vous trouverez l'accusé de réception en pièce jointe ({ar_number(order)}.pdf).

Cordialement,
Le service commandes
"""
