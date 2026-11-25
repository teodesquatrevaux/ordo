# Ordo – Business Brief

18 November 2026

Ordo turns B2B orders received by email into orders ready to import into the ERP, so nobody has to retype them. We start with small distributors, and our first real customer is FEKU-France.

## The problem

At FEKU-France, every order arrives by email, as a PDF or in the email text, and someone types it into the ERP (Simax) by hand. Each customer writes orders differently, with their own references. FEKU's catalogue has 204 pages and many near-identical items, so one wrong line means a wrong delivery.

- About 5 minutes to type one order; at 120 orders a day, that is about 10 hours of typing (Kolonell agency blog, an illustrative scenario, not a study).
- 2% to 5% of orders typed by hand contain an error (Zoey, cited by Workd).
- FEKU's real volumes are still to collect.

## Target market

We target small B2B distributors in France that receive orders by email and have no EDI. Large tools already serve mid-market and enterprise companies.

| Level | How we count | Per year |
| --- | --- | --- |
| Total market | 17,684 wholesalers (not micro) × €3,000 | ~€53M |
| Serviceable market | 16,562 SMEs × 57% × €3,000 | ~€28M |
| Year-3 target | 1% of serviceable, about 94 customers | ~€0.28M |

Sources: INSEE 2023, French wholesale excluding motor vehicles. 57% is the share of “interindustrial” firms in the branch (Akto), an approximation. €3,000 a year assumes a price of €250 a month, not yet tested.

## Product choices and proof

Ordo is built to never put a wrong line into the ERP without a warning.

| Choice | Why |
| --- | --- |
| The AI only reads the order; fixed rules match it to the catalogue | The AI cannot invent a product reference |
| Doubtful lines are flagged; a person fixes them in one click | A check costs less than a wrong delivery |
| Each fix is saved for that customer | Their next order goes through alone, with no model training |
| Output is an import file for the ERP, plus a draft reply to the customer | No IT integration project to get started |

The working prototype (AI mode) scored 100% on 10 test orders: 33/33 correct references, 37/37 correct quantities, 16/16 expected warnings raised and 0 silent errors. These are synthetic orders we wrote ourselves, with a 49-item demo catalogue. The next proof is 20 to 30 real FEKU orders.

## Competition

The market has players, but they mostly sell to bigger companies. Our gap to test is small distributors, a self-serve start and memory per customer.

| Group | Players | Note |
| --- | --- | --- |
| Enterprise tools | Esker, Conexiom, Comena, Proton.ai | Conexiom says it is “built for mid-market and enterprise” (Capterra) |
| French players | Order1, Lisy.co, Deestree | Order1 targets SMEs and mid-caps, with no public price (Appvizer) |
| Today’s habits | Manual typing, EDI, customer portals | EDI and portals ask the customer to change how they order |

## Launch plan

We launch with one pilot customer, FEKU, then use its results to reach similar distributors.

1. Now: test Ordo on 20 to 30 real, anonymised FEKU orders.
2. 25 November: live link, FEKU uses Ordo on its own orders.
3. November to December: about 10 interviews with technical distributors, to test a price of €200 to €400 a month.
4. 18 December: final pitch with real results and FEKU’s feedback.
5. Then: FEKU as a reference to sign the next distributors.

## Blockers and how you can help

What blocks us most is data from FEKU and proof that people will pay.

- We do not know Simax’s import format yet.
- We have no real FEKU orders yet (they contain prices and customer names, so they must be anonymised first).
- FEKU’s packaging rule is unclear.
- We have no pricing data.

How mentors can help: introductions to distributors who receive orders by email, feedback on our price and target, and advice on getting data from a small client.
