# Data Analysis — Brigade Road (ST1008 / STORE_BLR_002), 10 Apr 2026

Real POS export: **24 invoices, 21 unique customers, 101 line items**,
trading 12:15–21:40 IST. **₹34,332 net** (₹44,920 gross GMV), avg basket
**₹1,430**, median ₹856, ~4.9 items/basket (inflated by GWP/free items),
range ₹149–₹8,243.

**Department mix (line items):** makeup 54 · skin 27 · bath-body 9 · hair 6 ·
personal-care 4 · fragrance 1. **Top brands:** Faces Canada 32 · Good Vibes 14 ·
Purplle 10 · NY Bae 10 · DermDoc 6. **Orders by hour peak at 19:00 (5 orders)**;
a clear evening crush that the queue-spike anomaly is tuned for.

**Offer dependence:** "Buy 2 Get 1 Faces & NY Bae" drives 35 line items and
"Buy 2 Get 2 Sheet Mask" 13 — promotions cluster on the **south makeup wall**.

**Layout correlation (the differentiating insight).** The floor plan puts
skincare on the **north wall** (EB Korean, Good Vibes, DermDoc, Minimalist,
Aqualogica, Lakme Skin) and makeup on the **south wall** (Maybelline, Faces
Canada, Lakme, Colorbar+Sugar, Swiss Beauty, Renee/NY Bae, Streax), with central
makeup tester units and the cash counter on the right. POS revenue is dominated
by **makeup** (Faces Canada alone = 32 line items), i.e. the south wall + central
testers are the revenue engine, while north-wall skincare is browse-heavy.

This is exactly what the API surfaces: **/heatmap** (dwell/attention) vs the
**/funnel** purchase stage reveals *attention-without-sales* zones — the
"which zones get looked at but don't convert" business question. Pairing the two
endpoints lets a store manager move a promoter or reposition a planogram with
evidence, not intuition. Salesperson skew is also stark (Zufishan Khazra =
₹16,583 across 7 invoices vs the next at ₹6,542), suggesting staffing/coaching
leverage that the staff-aware event stream can later quantify.
