"""ERP-ready export. The real Simax import format is NOT known yet: this is a generic
semicolon CSV (opens in French Excel) to be mapped once FEKU shares a Simax import sample."""
import csv
import io

COLUMNS = ["numero_commande_client", "client", "date_commande", "date_livraison", "ligne",
           "reference", "designation", "quantite", "prix_unitaire_ht"]


def to_csv(order):
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(COLUMNS)
    for i, l in enumerate(order["lines"], 1):
        price = "" if l.get("unit_price") in (None, "") else f"{float(l['unit_price']):.4f}".replace(".", ",")
        qty = "" if l.get("quantity") in (None, "") else f"{float(l['quantity']):g}".replace(".", ",")
        w.writerow([order.get("order_number") or "", order.get("customer") or "", order.get("order_date") or "",
                    order.get("delivery_date") or "", i, l.get("ref") or "", l.get("designation") or "", qty, price])
    return buf.getvalue().encode("utf-8-sig")
