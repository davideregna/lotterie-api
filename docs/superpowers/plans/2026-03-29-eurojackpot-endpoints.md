# Eurojackpot Advanced Endpoints Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 5 new endpoints and rewrite 1 existing endpoint for Eurojackpot: statistiche (rewrite), numeri-frequenti, numeri-ritardatari, numeri-spia, previsioni, tabellone.

**Architecture:** All endpoints read from the `eurojackpot` table (estrazioni) and `statistiche` table (pre-computed stats). Euronumeri stats are stored with lotteria key `"eurojackpot_euro"`. Heavy computations (coppie, quaterne, ambi, spia) use in-memory dict caches invalidated when the latest extraction date changes.

**Tech Stack:** Python, FastAPI, SQLite, itertools, collections.Counter

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `giocochiaro/app/stats.py` | Modify (lines 103-104, 125-138) | Add `calcola_eurojackpot_euronumeri()`, update `calcola_tutte()` |
| `giocochiaro/app/api.py` | Modify (lines 885-887) | Rewrite `ej_stats()`, add 5 new endpoint functions + helper caches |

No new files. No DB schema changes (the `statistiche` table already supports arbitrary `lotteria` keys).

---

### Task 1: Add euronumeri stats calculation in `stats.py`

**Files:**
- Modify: `giocochiaro/app/stats.py:103-104` (after `calcola_eurojackpot`)
- Modify: `giocochiaro/app/stats.py:125-138` (inside `calcola_tutte`)

- [ ] **Step 1: Add `calcola_eurojackpot_euronumeri()` function**

Add after line 104 in `stats.py`:

```python
def calcola_eurojackpot_euronumeri():
    calcola_stats("eurojackpot_euro", "eurojackpot", 12, "e1, e2")
```

This reuses the existing `calcola_stats()` generic function. It will store 12 rows in `statistiche` with `lotteria = "eurojackpot_euro"`, one per euronumber (1-12), each with frequenza, ritardo_attuale, ritardo_max, ultima_data.

- [ ] **Step 2: Update `calcola_tutte()` to call it**

In `calcola_tutte()`, add `calcola_eurojackpot_euronumeri()` right after `calcola_eurojackpot()`:

```python
def calcola_tutte():
    print("\n=== CALCOLO STATISTICHE ===\n")
    calcola_millionday()
    calcola_superenalotto()
    calcola_lotto()
    calcola_lotto_ruote()
    calcola_diecelotto()
    calcola_vincicasa()
    calcola_eurojackpot()
    calcola_eurojackpot_euronumeri()  # <-- add this line
    calcola_sivincetutto()
    calcola_winforlife_classico()
    calcola_winforlife_grattacieli()
    calcola_simbolotto()
    print("\n=== FATTO ===")
```

- [ ] **Step 3: Verify stats calculation works**

Run: `cd /root/lotterie-api/giocochiaro && python -c "from app.stats import calcola_eurojackpot_euronumeri; calcola_eurojackpot_euronumeri()"`

Expected: prints `Stats eurojackpot_euro: <N> estrazioni, 12 numeri.`

- [ ] **Step 4: Commit**

```bash
git add giocochiaro/app/stats.py
git commit -m "feat(eurojackpot): add euronumeri stats calculation"
```

---

### Task 2: Rewrite `/api/eurojackpot/statistiche`

**Files:**
- Modify: `giocochiaro/app/api.py:885-887` (replace `ej_stats`)

- [ ] **Step 1: Replace `ej_stats()` function**

Replace lines 885-887:

```python
@app.get("/api/eurojackpot/statistiche")
def ej_stats():
    return get_stats("eurojackpot")
```

With:

```python
@app.get("/api/eurojackpot/statistiche")
def ej_stats():
    with get_db_ctx() as conn:
        totale = conn.execute("SELECT COUNT(*) FROM eurojackpot").fetchone()[0]
        numeri_rows = conn.execute(
            "SELECT * FROM statistiche WHERE lotteria = 'eurojackpot' ORDER BY numero ASC"
        ).fetchall()
        euro_rows = conn.execute(
            "SELECT * FROM statistiche WHERE lotteria = 'eurojackpot_euro' ORDER BY numero ASC"
        ).fetchall()

    if not numeri_rows:
        return {"errore": "Statistiche non calcolate"}

    numeri = rows_to_list(numeri_rows)
    euro = rows_to_list(euro_rows)

    aggiornato_al = numeri[0]["aggiornato_il"].split(" ")[0] if numeri[0].get("aggiornato_il") else None

    top_rit = sorted(numeri, key=lambda x: x["ritardo_attuale"], reverse=True)[:10]
    top_freq = sorted(numeri, key=lambda x: x["frequenza"], reverse=True)[:10]
    top_euro = sorted(euro, key=lambda x: x["frequenza"], reverse=True)[:5]

    # Distribuzione decine
    fasce = [(1, 10), (11, 20), (21, 30), (31, 40), (41, 50)]
    totale_freq = sum(n["frequenza"] for n in numeri)
    distribuzione = []
    for lo, hi in fasce:
        count = sum(n["frequenza"] for n in numeri if lo <= n["numero"] <= hi)
        distribuzione.append({
            "range": f"{lo}-{hi}",
            "count": count,
            "percentuale": round(count / totale_freq * 100, 1) if totale_freq else 0,
        })

    return {
        "lotteria": "eurojackpot",
        "aggiornato_al": aggiornato_al,
        "totale_estrazioni": totale,
        "top_ritardatari": [{"numero": n["numero"], "ritardo": n["ritardo_attuale"]} for n in top_rit],
        "top_frequenti": [{"numero": n["numero"], "frequenza": n["frequenza"]} for n in top_freq],
        "top_euro_frequenti": [{"numero": n["numero"], "frequenza": n["frequenza"]} for n in top_euro],
        "distribuzione_decine": distribuzione,
    }
```

- [ ] **Step 2: Test the endpoint**

Run: `cd /root/lotterie-api/giocochiaro && python -c "
import os; os.environ.setdefault('HMAC_SECRET','test'); os.environ.setdefault('API_KEY','test')
from app.database import get_db_ctx
from app.api import ej_stats
r = ej_stats()
assert 'top_ritardatari' in r and len(r['top_ritardatari']) <= 10
assert 'top_euro_frequenti' in r and len(r['top_euro_frequenti']) <= 5
assert 'distribuzione_decine' in r and len(r['distribuzione_decine']) == 5
assert 'totale_estrazioni' in r
print('OK:', list(r.keys()))
"`

Expected: prints `OK: ['lotteria', 'aggiornato_al', 'totale_estrazioni', 'top_ritardatari', 'top_frequenti', 'top_euro_frequenti', 'distribuzione_decine']`

- [ ] **Step 3: Commit**

```bash
git add giocochiaro/app/api.py
git commit -m "feat(eurojackpot): rewrite /statistiche with decine distribution and euronumeri"
```

---

### Task 3: Add `/api/eurojackpot/tabellone`

**Files:**
- Modify: `giocochiaro/app/api.py` (add after `ej_stats`, before the SiVinceTutto section at line 890)

- [ ] **Step 1: Add endpoint**

Insert after the `ej_stats()` function:

```python
@app.get("/api/eurojackpot/tabellone")
def ej_tabellone():
    with get_db_ctx() as conn:
        totale = conn.execute("SELECT COUNT(*) FROM eurojackpot").fetchone()[0]
        numeri_rows = conn.execute(
            "SELECT * FROM statistiche WHERE lotteria = 'eurojackpot' ORDER BY numero ASC"
        ).fetchall()
        euro_rows = conn.execute(
            "SELECT * FROM statistiche WHERE lotteria = 'eurojackpot_euro' ORDER BY numero ASC"
        ).fetchall()

    if not numeri_rows:
        return {"errore": "Statistiche non calcolate"}

    aggiornato_al = numeri_rows[0]["aggiornato_il"].split(" ")[0] if numeri_rows[0]["aggiornato_il"] else None

    def _tab_row(r):
        return {"numero": r["numero"], "frequenza": r["frequenza"],
                "ritardo": r["ritardo_attuale"], "ritardo_max": r["ritardo_max"]}

    return {
        "lotteria": "eurojackpot",
        "aggiornato_al": aggiornato_al,
        "totale_estrazioni": totale,
        "numeri": [_tab_row(r) for r in numeri_rows],
        "euronumeri": [_tab_row(r) for r in euro_rows],
    }
```

- [ ] **Step 2: Test the endpoint**

Run: `cd /root/lotterie-api/giocochiaro && python -c "
import os; os.environ.setdefault('HMAC_SECRET','test'); os.environ.setdefault('API_KEY','test')
from app.api import ej_tabellone
r = ej_tabellone()
assert len(r['numeri']) == 50, f'Expected 50, got {len(r[\"numeri\"])}'
assert len(r['euronumeri']) == 12, f'Expected 12, got {len(r[\"euronumeri\"])}'
assert r['numeri'][0]['numero'] == 1  # ordered ASC
assert all(k in r['numeri'][0] for k in ('frequenza', 'ritardo', 'ritardo_max'))
print('OK')
"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add giocochiaro/app/api.py
git commit -m "feat(eurojackpot): add /tabellone endpoint"
```

---

### Task 4: Add `/api/eurojackpot/numeri-frequenti`

**Files:**
- Modify: `giocochiaro/app/api.py` (add after `ej_tabellone`, before SiVinceTutto)

This endpoint needs heavy computation for coppie and quaterne, so it uses a cache dict.

- [ ] **Step 1: Add cache and computation function**

Insert after `ej_tabellone()`:

```python
_ej_freq_cache = {"data": None, "result": None}


def _ej_calcola_combinazioni():
    from collections import Counter
    from itertools import combinations

    with get_db_ctx() as conn:
        rows = conn.execute("SELECT n1, n2, n3, n4, n5 FROM eurojackpot").fetchall()

    freq_coppie = Counter()
    freq_quaterne = Counter()

    for r in rows:
        numeri = tuple(sorted([r["n1"], r["n2"], r["n3"], r["n4"], r["n5"]]))
        for coppia in combinations(numeri, 2):
            freq_coppie[coppia] += 1
        for quaterna in combinations(numeri, 4):
            freq_quaterne[quaterna] += 1

    coppie = [{"coppia": list(k), "frequenza": v} for k, v in freq_coppie.most_common(10)]
    quaterne = [{"quaterna": list(k), "frequenza": v} for k, v in freq_quaterne.most_common(5)]

    return {"coppie": coppie, "quaterne": quaterne}
```

- [ ] **Step 2: Add endpoint**

Insert after the computation function:

```python
@app.get("/api/eurojackpot/numeri-frequenti")
def ej_numeri_frequenti():
    with get_db_ctx() as conn:
        totale = conn.execute("SELECT COUNT(*) FROM eurojackpot").fetchone()[0]
        numeri_rows = conn.execute(
            "SELECT * FROM statistiche WHERE lotteria = 'eurojackpot' ORDER BY frequenza DESC"
        ).fetchall()
        euro_rows = conn.execute(
            "SELECT * FROM statistiche WHERE lotteria = 'eurojackpot_euro' ORDER BY frequenza DESC"
        ).fetchall()
        ultima = conn.execute("SELECT data FROM eurojackpot ORDER BY data DESC LIMIT 1").fetchone()

    if not numeri_rows:
        return {"errore": "Statistiche non calcolate"}

    ultima_data = ultima["data"] if ultima else None
    aggiornato_al = numeri_rows[0]["aggiornato_il"].split(" ")[0] if numeri_rows[0]["aggiornato_il"] else None

    if _ej_freq_cache["data"] != ultima_data:
        _ej_freq_cache["result"] = _ej_calcola_combinazioni()
        _ej_freq_cache["data"] = ultima_data

    cached = _ej_freq_cache["result"]

    return {
        "lotteria": "eurojackpot",
        "aggiornato_al": aggiornato_al,
        "totale_estrazioni": totale,
        "numeri": [{"numero": r["numero"], "frequenza": r["frequenza"]} for r in numeri_rows],
        "euronumeri": [{"numero": r["numero"], "frequenza": r["frequenza"]} for r in euro_rows],
        "coppie": cached["coppie"],
        "quaterne": cached["quaterne"],
    }
```

- [ ] **Step 3: Test the endpoint**

Run: `cd /root/lotterie-api/giocochiaro && python -c "
import os; os.environ.setdefault('HMAC_SECRET','test'); os.environ.setdefault('API_KEY','test')
from app.api import ej_numeri_frequenti
r = ej_numeri_frequenti()
assert len(r['numeri']) == 50
assert len(r['euronumeri']) == 12
assert len(r['coppie']) == 10
assert len(r['quaterne']) == 5
assert r['numeri'][0]['frequenza'] >= r['numeri'][-1]['frequenza']  # DESC
print('OK')
"`

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add giocochiaro/app/api.py
git commit -m "feat(eurojackpot): add /numeri-frequenti with coppie and quaterne"
```

---

### Task 5: Add `/api/eurojackpot/numeri-ritardatari`

**Files:**
- Modify: `giocochiaro/app/api.py` (add after `ej_numeri_frequenti`, before SiVinceTutto)

- [ ] **Step 1: Add ambi ritardatari cache and computation**

Insert after `ej_numeri_frequenti()`:

```python
_ej_ambi_cache = {"data": None, "result": None}


def _ej_calcola_ambi_ritardatari():
    from itertools import combinations

    with get_db_ctx() as conn:
        rows = conn.execute(
            "SELECT data, n1, n2, n3, n4, n5 FROM eurojackpot ORDER BY data ASC"
        ).fetchall()

    # Track last extraction index where each pair appeared
    ultima_coppia = {}

    for idx, r in enumerate(rows):
        numeri = tuple(sorted([r["n1"], r["n2"], r["n3"], r["n4"], r["n5"]]))
        for coppia in combinations(numeri, 2):
            ultima_coppia[coppia] = (idx, r["data"])

    totale = len(rows)
    ambi = []
    for coppia, (last_idx, last_data) in ultima_coppia.items():
        ritardo = totale - 1 - last_idx
        if ritardo > 0:
            ambi.append({
                "coppia": list(coppia),
                "ritardo": ritardo,
                "ultima_estrazione": last_data,
            })

    ambi.sort(key=lambda x: x["ritardo"], reverse=True)
    return ambi[:10]
```

- [ ] **Step 2: Add endpoint**

Insert after the computation function:

```python
@app.get("/api/eurojackpot/numeri-ritardatari")
def ej_numeri_ritardatari():
    with get_db_ctx() as conn:
        totale = conn.execute("SELECT COUNT(*) FROM eurojackpot").fetchone()[0]
        numeri_rows = conn.execute(
            "SELECT * FROM statistiche WHERE lotteria = 'eurojackpot' ORDER BY ritardo_attuale DESC"
        ).fetchall()
        euro_rows = conn.execute(
            "SELECT * FROM statistiche WHERE lotteria = 'eurojackpot_euro' ORDER BY ritardo_attuale DESC"
        ).fetchall()
        ultima = conn.execute("SELECT data FROM eurojackpot ORDER BY data DESC LIMIT 1").fetchone()

    if not numeri_rows:
        return {"errore": "Statistiche non calcolate"}

    ultima_data = ultima["data"] if ultima else None
    aggiornato_al = numeri_rows[0]["aggiornato_il"].split(" ")[0] if numeri_rows[0]["aggiornato_il"] else None

    if _ej_ambi_cache["data"] != ultima_data:
        _ej_ambi_cache["result"] = _ej_calcola_ambi_ritardatari()
        _ej_ambi_cache["data"] = ultima_data

    def _rit_row(r):
        return {
            "numero": r["numero"],
            "ritardo": r["ritardo_attuale"],
            "ritardo_max": r["ritardo_max"],
            "ultima_estrazione": r["ultima_data"],
        }

    return {
        "lotteria": "eurojackpot",
        "aggiornato_al": aggiornato_al,
        "totale_estrazioni": totale,
        "numeri": [_rit_row(r) for r in numeri_rows[:20]],
        "euronumeri": [_rit_row(r) for r in euro_rows],
        "ambi": _ej_ambi_cache["result"],
    }
```

- [ ] **Step 3: Test the endpoint**

Run: `cd /root/lotterie-api/giocochiaro && python -c "
import os; os.environ.setdefault('HMAC_SECRET','test'); os.environ.setdefault('API_KEY','test')
from app.api import ej_numeri_ritardatari
r = ej_numeri_ritardatari()
assert len(r['numeri']) == 20
assert len(r['euronumeri']) == 12
assert len(r['ambi']) <= 10
assert r['numeri'][0]['ritardo'] >= r['numeri'][-1]['ritardo']  # DESC
print('OK')
"`

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add giocochiaro/app/api.py
git commit -m "feat(eurojackpot): add /numeri-ritardatari with ambi"
```

---

### Task 6: Add `/api/eurojackpot/numeri-spia`

**Files:**
- Modify: `giocochiaro/app/api.py` (add after `ej_numeri_ritardatari`, before SiVinceTutto)

- [ ] **Step 1: Add spia cache and computation**

Insert after `ej_numeri_ritardatari()`:

```python
_ej_spia_cache = {"data": None, "result": None}


def _ej_calcola_numeri_spia():
    from collections import Counter

    with get_db_ctx() as conn:
        rows = conn.execute(
            "SELECT n1, n2, n3, n4, n5 FROM eurojackpot ORDER BY data ASC"
        ).fetchall()

    totale = len(rows)
    # For each number that appeared in extraction i,
    # count which numbers appear in extraction i+1
    spia_counts = {}   # spia_num -> Counter of followed-by numbers
    spia_totals = {}   # spia_num -> how many times it appeared (excluding last extraction)

    for i in range(totale - 1):
        numeri_corrente = set([rows[i]["n1"], rows[i]["n2"], rows[i]["n3"], rows[i]["n4"], rows[i]["n5"]])
        numeri_successivo = set([rows[i+1]["n1"], rows[i+1]["n2"], rows[i+1]["n3"], rows[i+1]["n4"], rows[i+1]["n5"]])

        for n in numeri_corrente:
            if n not in spia_counts:
                spia_counts[n] = Counter()
                spia_totals[n] = 0
            spia_totals[n] += 1
            for s in numeri_successivo:
                if s != n:
                    spia_counts[n][s] += 1

    # Build result: for each spia, top 5 spiati + affidabilita
    risultati = []
    for numero, counter in spia_counts.items():
        top5 = counter.most_common(5)
        if not top5:
            continue
        spiati = [s for s, _ in top5]
        # Affidabilita: % of times at least 1 of top5 appeared in the next extraction
        hit = 0
        idx = 0
        for i in range(totale - 1):
            numeri_corrente = set([rows[i]["n1"], rows[i]["n2"], rows[i]["n3"], rows[i]["n4"], rows[i]["n5"]])
            if numero not in numeri_corrente:
                continue
            numeri_successivo = set([rows[i+1]["n1"], rows[i+1]["n2"], rows[i+1]["n3"], rows[i+1]["n4"], rows[i+1]["n5"]])
            if numeri_successivo & set(spiati):
                hit += 1
            idx += 1
        affidabilita = round(hit / idx * 100) if idx > 0 else 0
        risultati.append({
            "numero": numero,
            "spiati": spiati,
            "affidabilita": affidabilita,
        })

    risultati.sort(key=lambda x: x["affidabilita"], reverse=True)
    return {"totale_estrazioni": totale, "spia": risultati[:20]}
```

- [ ] **Step 2: Add endpoint**

Insert after the computation function:

```python
@app.get("/api/eurojackpot/numeri-spia")
def ej_numeri_spia():
    with get_db_ctx() as conn:
        ultima = conn.execute("SELECT data FROM eurojackpot ORDER BY data DESC LIMIT 1").fetchone()
    ultima_data = ultima["data"] if ultima else None

    if _ej_spia_cache["data"] != ultima_data:
        _ej_spia_cache["result"] = _ej_calcola_numeri_spia()
        _ej_spia_cache["data"] = ultima_data

    cached = _ej_spia_cache["result"]
    return {
        "lotteria": "eurojackpot",
        "aggiornato_al": ultima_data,
        "totale_estrazioni": cached["totale_estrazioni"],
        "spia": cached["spia"],
    }
```

- [ ] **Step 3: Test the endpoint**

Run: `cd /root/lotterie-api/giocochiaro && python -c "
import os; os.environ.setdefault('HMAC_SECRET','test'); os.environ.setdefault('API_KEY','test')
from app.api import ej_numeri_spia
r = ej_numeri_spia()
assert len(r['spia']) == 20
assert len(r['spia'][0]['spiati']) == 5
assert r['spia'][0]['affidabilita'] >= r['spia'][-1]['affidabilita']  # DESC
print('OK')
"`

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add giocochiaro/app/api.py
git commit -m "feat(eurojackpot): add /numeri-spia endpoint"
```

---

### Task 7: Add `/api/eurojackpot/previsioni`

**Files:**
- Modify: `giocochiaro/app/api.py` (add after `ej_numeri_spia`, before SiVinceTutto)

- [ ] **Step 1: Add endpoint**

Insert after `ej_numeri_spia()`:

```python
@app.get("/api/eurojackpot/previsioni")
def ej_previsioni():
    from datetime import date, timedelta

    with get_db_ctx() as conn:
        numeri_rows = conn.execute(
            "SELECT * FROM statistiche WHERE lotteria = 'eurojackpot' ORDER BY numero ASC"
        ).fetchall()
        euro_rows = conn.execute(
            "SELECT * FROM statistiche WHERE lotteria = 'eurojackpot_euro' ORDER BY numero ASC"
        ).fetchall()

    if not numeri_rows:
        return {"errore": "Statistiche non calcolate"}

    aggiornato_al = numeri_rows[0]["aggiornato_il"].split(" ")[0] if numeri_rows[0]["aggiornato_il"] else None

    def _con_indice(r):
        rm = r["ritardo_max"]
        indice = round(r["ritardo_attuale"] / rm * 100) if rm > 0 else 0
        return {
            "numero": r["numero"],
            "frequenza": r["frequenza"],
            "ritardo": r["ritardo_attuale"],
            "ritardo_max": rm,
            "indice": indice,
        }

    analisi_numeri = sorted([_con_indice(r) for r in numeri_rows], key=lambda x: x["indice"], reverse=True)
    analisi_euro = sorted([_con_indice(r) for r in euro_rows], key=lambda x: x["indice"], reverse=True)

    # Prossima estrazione: prossimo martedi (1) o venerdi (4)
    oggi = date.today()
    prossima = None
    for delta in range(1, 8):
        giorno = oggi + timedelta(days=delta)
        if giorno.weekday() in (1, 4):  # martedi=1, venerdi=4
            prossima = giorno.isoformat()
            break

    return {
        "lotteria": "eurojackpot",
        "aggiornato_al": aggiornato_al,
        "prossima_estrazione": prossima,
        "consigliati": {
            "numeri": [n["numero"] for n in analisi_numeri[:5]],
            "euronumeri": [n["numero"] for n in analisi_euro[:2]],
        },
        "analisi_numeri": analisi_numeri[:10],
        "analisi_euronumeri": analisi_euro[:5],
    }
```

- [ ] **Step 2: Test the endpoint**

Run: `cd /root/lotterie-api/giocochiaro && python -c "
import os; os.environ.setdefault('HMAC_SECRET','test'); os.environ.setdefault('API_KEY','test')
from app.api import ej_previsioni
r = ej_previsioni()
assert len(r['consigliati']['numeri']) == 5
assert len(r['consigliati']['euronumeri']) == 2
assert len(r['analisi_numeri']) == 10
assert len(r['analisi_euronumeri']) == 5
assert r['prossima_estrazione'] is not None
print('OK')
"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add giocochiaro/app/api.py
git commit -m "feat(eurojackpot): add /previsioni endpoint"
```

---

### Task 8: Final verification — all 6 endpoints

- [ ] **Step 1: Run all endpoints together**

Run: `cd /root/lotterie-api/giocochiaro && python -c "
import os; os.environ.setdefault('HMAC_SECRET','test'); os.environ.setdefault('API_KEY','test')
from app.api import ej_stats, ej_tabellone, ej_numeri_frequenti, ej_numeri_ritardatari, ej_numeri_spia, ej_previsioni

for name, fn in [('statistiche', ej_stats), ('tabellone', ej_tabellone), ('numeri-frequenti', ej_numeri_frequenti), ('numeri-ritardatari', ej_numeri_ritardatari), ('numeri-spia', ej_numeri_spia), ('previsioni', ej_previsioni)]:
    r = fn()
    assert 'errore' not in r, f'{name}: {r}'
    print(f'{name}: OK ({list(r.keys())})')
print('ALL OK')
"`

Expected: all 6 endpoints print OK.

- [ ] **Step 2: Start the server and test via HTTP**

Run: `cd /root/lotterie-api/giocochiaro && timeout 5 python -c "
import os; os.environ.setdefault('HMAC_SECRET','test'); os.environ.setdefault('API_KEY','test')
import uvicorn
uvicorn.run('app.api:app', host='127.0.0.1', port=9999)
" &`

Then test each endpoint:

```bash
for ep in statistiche tabellone numeri-frequenti numeri-ritardatari numeri-spia previsioni; do
    curl -s http://127.0.0.1:9999/api/eurojackpot/$ep | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'$ep: OK' if 'errore' not in d else f'$ep: FAIL {d}')"
done
```

- [ ] **Step 3: Commit all remaining changes**

```bash
git add giocochiaro/app/api.py giocochiaro/app/stats.py
git commit -m "feat(eurojackpot): complete all 6 advanced endpoints"
```
