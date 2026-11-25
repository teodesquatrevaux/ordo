"""LLM extractor through OpenRouter (OpenAI-compatible API). The model only READS the order:
it copies references as written and never maps them to the catalogue (matching is deterministic)."""
import base64
import json
import time
from .config import api_key, model, PRICE_IN, PRICE_OUT

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["customer", "order_number", "order_date", "delivery_date", "ar_requested", "lines", "notes"],
    "properties": {
        "customer": {"type": ["string", "null"]},
        "order_number": {"type": ["string", "null"]},
        "order_date": {"type": ["string", "null"], "description": "JJ/MM/AAAA"},
        "delivery_date": {"type": ["string", "null"], "description": "JJ/MM/AAAA"},
        "ar_requested": {"type": "string", "enum": ["no", "yes", "yes_48h"]},
        "notes": {"type": "array", "items": {"type": "string"}},
        "lines": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["raw_text", "customer_ref", "quantity", "unit_price", "source", "change"],
            "properties": {
                "raw_text": {"type": "string"},
                "customer_ref": {"type": ["string", "null"]},
                "quantity": {"type": ["number", "null"]},
                "unit_price": {"type": ["number", "null"]},
                "source": {"type": "string", "enum": ["attachment", "email_body"]},
                "change": {"type": "string", "enum": ["none", "modified_by_email", "added_by_email"]},
            }}},
    },
}

SYSTEM = """Tu lis des commandes B2B reçues par un distributeur d'instruments de mesure.
Règles :
- Recopie chaque référence EXACTEMENT comme écrite par le client (garde les préfixes, suffixes, fautes). Ne corrige rien, ne devine aucune référence absente : customer_ref = null si le client n'en donne pas.
- raw_text = la ligne telle qu'écrite (désignation comprise), sans la quantité si possible.
- quantity = quantité commandée telle qu'écrite (ne convertis pas en lots ou en boîtes).
- Si le corps de l'email modifie la pièce jointe (quantité changée, ligne ajoutée), produis la ligne FINALE avec change = modified_by_email ou added_by_email, et mets l'ancienne valeur dans notes.
- ar_requested : yes_48h si un accusé de réception est demandé sous 48 h, yes si un AR ou une confirmation est demandé, sinon no.
- Ignore signatures, mentions légales, conditions générales, totaux.
- Dates au format JJ/MM/AAAA. N'invente aucune donnée absente : null."""


def _content(msg):
    parts = [f"Expéditeur : {msg.sender}\nObjet : {msg.subject}\nDate : {msg.date}\n\n--- CORPS DE L'EMAIL ---\n{msg.body}"]
    images = []
    for a in msg.attachments:
        if a.is_scan:
            parts.append(f"\n--- PIÈCE JOINTE {a.name} (image, voir ci-dessous) ---")
            images += a.images
        elif a.text:
            parts.append(f"\n--- PIÈCE JOINTE {a.name} ---\n{a.text}")
    content = [{"type": "text", "text": "\n".join(parts)}]
    for b in images:
        content.append({"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(b).decode()}})
    return content


def extract(msg, model_id=None):
    from openai import OpenAI
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key(), timeout=90)
    t0 = time.time()
    r = client.chat.completions.create(
        model=model_id or model(),
        messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": _content(msg)}],
        response_format={"type": "json_schema", "json_schema": {"name": "order", "strict": True, "schema": SCHEMA}},
        temperature=0,
        extra_body={"usage": {"include": True}},
    )
    out = json.loads(r.choices[0].message.content)
    u = r.usage
    cost = getattr(u, "cost", None)
    if cost is None and u is not None:
        cost = u.prompt_tokens * PRICE_IN + u.completion_tokens * PRICE_OUT
    out["_meta"] = dict(seconds=round(time.time() - t0, 2), cost_usd=cost,
                        tokens_in=getattr(u, "prompt_tokens", None), tokens_out=getattr(u, "completion_tokens", None))
    out["modifications"] = []
    return out
