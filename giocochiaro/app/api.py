from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional
from app.database import get_db_ctx, init_db
from app.config import TABELLE_VALIDE
from app.persist import get_live, salva_estrazione
import json as _json
import hmac
import hashlib
import time
import os


HMAC_SECRET = os.getenv("HMAC_SECRET", "")
if not HMAC_SECRET:
    raise RuntimeError("Variabile d'ambiente HMAC_SECRET non configurata!")
HMAC_MAX_AGE = 30  # secondi di validità


async def scrape_iniziale():
    """Scrapa se live_data è vuoto o vecchio."""
    oggi = datetime.now().strftime("%Y-%m-%d")

    with get_db_ctx() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM live_data WHERE data = ?", (oggi,)
        ).fetchone()
        aggiornati_oggi = row[0] if row else 0

    if aggiornati_oggi >= 3:
        print("Live data già aggiornati, skip scrape iniziale.")
        return

    print("Live data assenti o vecchi, scrape iniziale...")
    try:
        from scraper.scraper import main as scrape_all
        from app.stats import calcola_tutte

        estrazioni = await scrape_all()
        nuove = 0
        for e in estrazioni:
            if salva_estrazione(e):
                nuove += 1

        if nuove > 0:
            calcola_tutte()
            print(f"Scrape iniziale completato: {nuove} nuove estrazioni.")
        else:
            print("Scrape iniziale completato: nessuna estrazione nuova (dati live aggiornati).")
    except Exception as ex:
        print(f"ERRORE scrape iniziale: {ex}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    import asyncio
    from app.scheduler import start_background

    await scrape_iniziale()

    task = asyncio.create_task(start_background())
    yield
    task.cancel()


app = FastAPI(title="GiocoChiaro API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.middleware("http")
async def check_hmac_auth(request: Request, call_next):
    client = request.client.host
    if client in ("127.0.0.1", "::1"):
        return await call_next(request)

    if request.url.path.startswith("/api/"):
        signature = request.headers.get("X-Signature")
        timestamp = request.headers.get("X-Timestamp")

        if not signature or not timestamp:
            return JSONResponse(
                status_code=403,
                content={"errore": "Accesso non autorizzato"}
            )

        # Controlla che il timestamp non sia troppo vecchio
        try:
            req_time = int(timestamp)
        except ValueError:
            return JSONResponse(
                status_code=403,
                content={"errore": "Timestamp non valido"}
            )

        now = int(time.time())
        if abs(now - req_time) > HMAC_MAX_AGE:
            return JSONResponse(
                status_code=403,
                content={"errore": "Richiesta scaduta"}
            )

        # Ricalcola la firma e confronta
        expected = hmac.new(
            HMAC_SECRET.encode(),
            timestamp.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected):
            return JSONResponse(
                status_code=403,
                content={"errore": "Firma non valida"}
            )

    return await call_next(request)


def rows_to_list(rows):
    return [dict(r) for r in rows]


def get_stats(lotteria):
    with get_db_ctx() as conn:
        rows = conn.execute(
            "SELECT * FROM statistiche WHERE lotteria = ? ORDER BY numero ASC",
            (lotteria,)
        ).fetchall()

    if not rows:
        return {"errore": "Statistiche non calcolate"}

    dati = rows_to_list(rows)
    return {
        "lotteria": lotteria,
        "aggiornato_il": dati[0]["aggiornato_il"],
        "top_ritardatari": sorted(dati, key=lambda x: x["ritardo_attuale"], reverse=True)[:10],
        "top_frequenti": sorted(dati, key=lambda x: x["frequenza"], reverse=True)[:10],
        "tutti": dati,
    }


def _fmt_importo(centesimi: int) -> str:
    return f"{centesimi / 100:.2f}"


def _parse_vincite_gntn(raw_vincite: list) -> list:
    vincite = []
    for v in raw_vincite:
        quota = v.get("quota", {})
        cat = quota.get("categoriaVincita", {})
        desc = cat.get("descrizione", "")
        tipo = cat.get("tipo", cat.get("tipoCodiceCategoriaVincita", ""))
        importo = quota.get("importo", 0)
        numero = int(v.get("numero", 0))
        numero_italia = v.get("numeroItalia")

        entry = {
            "categoria": desc,
            "tipo": tipo,
            "importo_centesimi": importo,
            "importo_euro": _fmt_importo(importo),
            "numero_vincite": numero,
        }
        if numero_italia is not None:
            entry["numero_vincite_italia"] = int(numero_italia)
        vincite.append(entry)
    return vincite


# ── MillionDay ──────────────────────────────────────────────

@app.get("/api/millionday/ultima")
def md_ultima():
    live = get_live("MillionDAY")
    if live:
        raw = live["raw"]
        return {
            "lotteria": "millionday",
            "data": live["data"],
            "ora": raw.get("orarioEstrazione", ""),
            "numeri": [int(n) for n in (raw.get("numeriEstratti") or [])],
            "extra": [int(n) for n in (raw.get("numeriEstrattiOvertime") or [])],
            "numero_milionari": raw.get("numeroMilionari", 0),
            "progressivo": raw.get("progressivo"),
            "aggiornato_il": live["aggiornato_il"],
        }

    with get_db_ctx() as conn:
        row = conn.execute("SELECT * FROM millionday ORDER BY data DESC, ora DESC LIMIT 1").fetchone()
    if not row:
        return {"errore": "Nessuna estrazione"}
    return {
        "lotteria": "millionday",
        "data": row["data"], "ora": row["ora"],
        "numeri": [row["n1"], row["n2"], row["n3"], row["n4"], row["n5"]],
        "extra": [row["e1"], row["e2"], row["e3"], row["e4"], row["e5"]],
    }


@app.get("/api/millionday/archivio")
def md_archivio(anno: Optional[int] = None, limit: int = Query(100, le=10000), offset: int = 0):
    with get_db_ctx() as conn:
        if anno:
            rows = conn.execute(
                "SELECT * FROM millionday WHERE data LIKE ? ORDER BY data DESC, ora DESC LIMIT ? OFFSET ?",
                (f"{anno}-%", limit, offset)
            ).fetchall()
            totale = conn.execute(
                "SELECT COUNT(*) FROM millionday WHERE data LIKE ?", (f"{anno}-%",)
            ).fetchone()[0]
        else:
            rows = conn.execute(
                "SELECT * FROM millionday ORDER BY data DESC, ora DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
            totale = conn.execute("SELECT COUNT(*) FROM millionday").fetchone()[0]
    return {"lotteria": "millionday", "totale": totale, "limit": limit, "offset": offset, "estrazioni": rows_to_list(rows)}


@app.get("/api/millionday/ultime")
def md_ultime(n: int = Query(10, le=100)):
    with get_db_ctx() as conn:
        rows = conn.execute("SELECT * FROM millionday ORDER BY data DESC, ora DESC LIMIT ?", (n,)).fetchall()
    return {
        "lotteria": "millionday",
        "estrazioni": [{
            "data": r["data"], "ora": r["ora"],
            "numeri": [r["n1"], r["n2"], r["n3"], r["n4"], r["n5"]],
            "extra": [r["e1"], r["e2"], r["e3"], r["e4"], r["e5"]],
        } for r in rows]
    }


@app.get("/api/millionday/statistiche")
def md_stats():
    return get_stats("millionday")


# ── SuperEnalotto ───────────────────────────────────────────


def _se_row_to_dict(r) -> dict:
    """Converte una riga DB superenalotto in dict con jackpot/vincite se presenti."""
    d = {
        "concorso": r["concorso"], "data": r["data"],
        "numeri": [r["n1"], r["n2"], r["n3"], r["n4"], r["n5"], r["n6"]],
        "jolly": r["jolly"], "superstar": r["superstar"],
    }
    jackpot = r["jackpot"] if r["jackpot"] else 0
    if jackpot:
        d["jackpot_centesimi"] = jackpot
        d["jackpot_euro"] = _fmt_importo(jackpot)
    montepremi_raw = r["montepremi_json"]
    if montepremi_raw:
        mp = _json.loads(montepremi_raw)
        d["montepremi"] = {
            "totale_centesimi": mp.get("montepremiTotale", 0),
            "totale_euro": _fmt_importo(mp.get("montepremiTotale", 0)),
            "concorso_centesimi": mp.get("montepremiConcorso", 0),
            "concorso_euro": _fmt_importo(mp.get("montepremiConcorso", 0)),
        }
    vincite_raw = r["vincite_json"]
    if vincite_raw:
        det = _json.loads(vincite_raw)
        d["vincite"] = _parse_vincite_gntn(det.get("vincite", []))
        d["totale_vincite"] = int(det.get("numeroTotaleVincite", 0))
        d["importo_totale_vincite_centesimi"] = det.get("importoTotaleVincite", 0)
        d["importo_totale_vincite_euro"] = _fmt_importo(det.get("importoTotaleVincite", 0))
    return d


@app.get("/api/superenalotto/ultima")
def se_ultima():
    live = get_live("SuperEnalotto")
    if live:
        raw = live["raw"]
        comb = raw.get("combinazioneVincente") or {}
        concorso = raw.get("concorso") or {}
        montepremi = raw.get("montepremi") or {}
        det_vincite = raw.get("dettaglioVincite") or {}

        return {
            "lotteria": "superenalotto",
            "concorso": concorso.get("numero", ""),
            "anno": concorso.get("anno", ""),
            "data": live["data"],
            "numeri": [int(n) for n in (comb.get("estratti") or [])],
            "jolly": int(comb["numeroJolly"]) if comb.get("numeroJolly") else None,
            "superstar": int(comb["superstar"]) if comb.get("superstar") else None,
            "jackpot_centesimi": raw.get("jackpot", 0),
            "jackpot_euro": _fmt_importo(raw.get("jackpot", 0)),
            "montepremi": {
                "totale_centesimi": montepremi.get("montepremiTotale", 0),
                "totale_euro": _fmt_importo(montepremi.get("montepremiTotale", 0)),
                "concorso_centesimi": montepremi.get("montepremiConcorso", 0),
                "concorso_euro": _fmt_importo(montepremi.get("montepremiConcorso", 0)),
            },
            "vincite": _parse_vincite_gntn(det_vincite.get("vincite", [])),
            "totale_vincite": int(det_vincite.get("numeroTotaleVincite", 0)),
            "importo_totale_vincite_centesimi": det_vincite.get("importoTotaleVincite", 0),
            "importo_totale_vincite_euro": _fmt_importo(det_vincite.get("importoTotaleVincite", 0)),
            "aggiornato_il": live["aggiornato_il"],
        }

    with get_db_ctx() as conn:
        row = conn.execute("SELECT * FROM superenalotto ORDER BY data DESC LIMIT 1").fetchone()
    if not row:
        return {"errore": "Nessuna estrazione"}
    return _se_row_to_dict(row)


@app.get("/api/superenalotto/archivio")
def se_archivio(anno: Optional[int] = None, limit: int = Query(100, le=10000), offset: int = 0):
    with get_db_ctx() as conn:
        if anno:
            rows = conn.execute(
                "SELECT * FROM superenalotto WHERE data LIKE ? ORDER BY data DESC LIMIT ? OFFSET ?",
                (f"{anno}-%", limit, offset)
            ).fetchall()
            totale = conn.execute(
                "SELECT COUNT(*) FROM superenalotto WHERE data LIKE ?", (f"{anno}-%",)
            ).fetchone()[0]
        else:
            rows = conn.execute(
                "SELECT * FROM superenalotto ORDER BY data DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
            totale = conn.execute("SELECT COUNT(*) FROM superenalotto").fetchone()[0]
    return {"lotteria": "superenalotto", "totale": totale, "limit": limit, "offset": offset,
            "estrazioni": [_se_row_to_dict(r) for r in rows]}


@app.get("/api/superenalotto/ultime")
def se_ultime(n: int = Query(10, le=100)):
    with get_db_ctx() as conn:
        rows = conn.execute("SELECT * FROM superenalotto ORDER BY data DESC LIMIT ?", (n,)).fetchall()
    return {
        "lotteria": "superenalotto",
        "estrazioni": [_se_row_to_dict(r) for r in rows]
    }


@app.get("/api/superenalotto/statistiche")
def se_stats():
    return get_stats("superenalotto")


# ── Lotto ───────────────────────────────────────────────────

@app.get("/api/lotto/ultima")
def lo_ultima():
    live = get_live("Lotto")
    if live:
        raw = live["raw"]
        estrazioni = raw.get("estrazione") or []
        simbolotti = raw.get("simbolotti")

        ruote = []
        for r in estrazioni:
            ruote.append({
                "ruota": r.get("ruota", ""),
                "nome": r.get("ruotaExtended", ""),
                "numeri": r.get("numeri", []),
                "numero_oro": r.get("numeroOro"),
            })

        risposta = {
            "lotteria": "lotto",
            "data": live["data"],
            "ruote": ruote,
            "aggiornato_il": live["aggiornato_il"],
        }
        if simbolotti:
            risposta["simbolotti"] = {
                "ruota": simbolotti.get("ruota", ""),
                "numeri": simbolotti.get("simbolotti", []),
            }
        return risposta

    with get_db_ctx() as conn:
        ultima_data = conn.execute("SELECT data FROM lotto ORDER BY data DESC LIMIT 1").fetchone()
        if not ultima_data:
            return {"errore": "Nessuna estrazione"}
        rows = conn.execute("SELECT * FROM lotto WHERE data = ? ORDER BY ruota", (ultima_data["data"],)).fetchall()
    return {
        "lotteria": "lotto",
        "data": ultima_data["data"],
        "ruote": [{"ruota": r["ruota"], "numeri": [r["n1"], r["n2"], r["n3"], r["n4"], r["n5"]]} for r in rows],
    }


@app.get("/api/lotto/archivio")
def lo_archivio(ruota: Optional[str] = None, limit: int = Query(100, le=10000), offset: int = 0):
    with get_db_ctx() as conn:
        if ruota:
            rows = conn.execute(
                "SELECT * FROM lotto WHERE LOWER(ruota) = LOWER(?) ORDER BY data DESC LIMIT ? OFFSET ?",
                (ruota, limit, offset)
            ).fetchall()
            totale = conn.execute(
                "SELECT COUNT(*) FROM lotto WHERE LOWER(ruota) = LOWER(?)", (ruota,)
            ).fetchone()[0]
        else:
            rows = conn.execute(
                "SELECT * FROM lotto ORDER BY data DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
            totale = conn.execute("SELECT COUNT(*) FROM lotto").fetchone()[0]
    return {"lotteria": "lotto", "totale": totale, "limit": limit, "offset": offset, "estrazioni": rows_to_list(rows)}


@app.get("/api/lotto/ultime")
def lo_ultime(n: int = Query(10, le=100)):
    with get_db_ctx() as conn:
        date = conn.execute("SELECT DISTINCT data FROM lotto ORDER BY data DESC LIMIT ?", (n,)).fetchall()
        risultati = []
        for d in date:
            rows = conn.execute("SELECT * FROM lotto WHERE data = ? ORDER BY ruota", (d["data"],)).fetchall()
            risultati.append({
                "data": d["data"],
                "ruote": [{"ruota": r["ruota"], "numeri": [r["n1"], r["n2"], r["n3"], r["n4"], r["n5"]]} for r in rows],
            })
    return {"lotteria": "lotto", "estrazioni": risultati}


@app.get("/api/lotto/statistiche")
def lo_stats(ruota: Optional[str] = None):
    if ruota:
        ruota_lower = ruota.lower()
        ruote_valide = [
            "bari", "cagliari", "firenze", "genova", "milano",
            "napoli", "palermo", "roma", "torino", "venezia", "nazionale",
        ]
        if ruota_lower not in ruote_valide:
            return {"errore": f"Ruota non valida. Valide: {', '.join(ruote_valide)}"}
        return get_stats(f"lotto_{ruota_lower}")
    return get_stats("lotto")


# ── 10eLotto ────────────────────────────────────────────────

@app.get("/api/10elotto/ultima")
def dl_ultima():
    live = get_live("10eLotto")
    if live:
        raw = live["raw"]
        return {
            "lotteria": "10elotto",
            "data": live["data"],
            "numeri": raw.get("numeriVincenti", []),
            "numero_oro": raw.get("numeroSpeciale"),
            "doppio_oro": raw.get("doppioNumeroSpeciale"),
            "extra": raw.get("numeriEstrattiOvertime", []),
            "aggiornato_il": live["aggiornato_il"],
        }

    with get_db_ctx() as conn:
        row = conn.execute("SELECT * FROM diecelotto ORDER BY data DESC LIMIT 1").fetchone()
    if not row:
        return {"errore": "Nessuna estrazione"}
    return {
        "lotteria": "10elotto", "data": row["data"],
        "numeri": [row[f"n{i}"] for i in range(1, 21)],
        "numero_oro": row["numero_oro"], "doppio_oro": row["doppio_oro"],
    }


@app.get("/api/10elotto/archivio")
def dl_archivio(limit: int = Query(100, le=10000), offset: int = 0):
    with get_db_ctx() as conn:
        rows = conn.execute("SELECT * FROM diecelotto ORDER BY data DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
        totale = conn.execute("SELECT COUNT(*) FROM diecelotto").fetchone()[0]
    return {"lotteria": "10elotto", "totale": totale, "limit": limit, "offset": offset, "estrazioni": rows_to_list(rows)}


@app.get("/api/10elotto/statistiche")
def dl_stats():
    return get_stats("10elotto")


def _vc_row_to_dict(r) -> dict:
    d = {
        "concorso": r["concorso"], "data": r["data"],
        "numeri": [r["n1"], r["n2"], r["n3"], r["n4"], r["n5"]],
    }
    montepremi_raw = r["montepremi_json"]
    if montepremi_raw:
        mp = _json.loads(montepremi_raw)
        d["montepremi_centesimi"] = mp.get("montepremiTotale", 0)
        d["montepremi_euro"] = _fmt_importo(mp.get("montepremiTotale", 0))
    vincite_raw = r["vincite_json"]
    if vincite_raw:
        det = _json.loads(vincite_raw)
        d["vincite"] = _parse_vincite_gntn(det.get("vincite", []))
        d["totale_vincite"] = int(det.get("numeroTotaleVincite", 0))
    return d


# ── VinciCasa ───────────────────────────────────────────────

@app.get("/api/vincicasa/ultima")
def vc_ultima():
    live = get_live("VinciCasa")
    if live:
        raw = live["raw"]
        dc = raw.get("dettaglioConcorso") or raw
        concorso = dc.get("concorso") or raw.get("concorso") or {}
        comb = dc.get("combinazioneVincente") or {}
        montepremi = dc.get("montepremi") or {}
        det_vincite = dc.get("dettaglioVincite") or {}

        return {
            "lotteria": "vincicasa",
            "concorso": concorso.get("numero", ""),
            "anno": concorso.get("anno", ""),
            "data": live["data"],
            "numeri": [int(n) for n in (comb.get("estratti") or [])],
            "montepremi_centesimi": montepremi.get("montepremiTotale", 0),
            "montepremi_euro": _fmt_importo(montepremi.get("montepremiTotale", 0)),
            "vincite": _parse_vincite_gntn(det_vincite.get("vincite", [])),
            "totale_vincite": int(det_vincite.get("numeroTotaleVincite", 0)),
            "aggiornato_il": live["aggiornato_il"],
        }

    with get_db_ctx() as conn:
        row = conn.execute("SELECT * FROM vincicasa ORDER BY data DESC LIMIT 1").fetchone()
    if not row:
        return {"errore": "Nessuna estrazione"}
    return {"lotteria": "vincicasa", **_vc_row_to_dict(row)}


@app.get("/api/vincicasa/archivio")
def vc_archivio(anno: Optional[int] = None, limit: int = Query(100, le=10000), offset: int = 0):
    with get_db_ctx() as conn:
        if anno:
            rows = conn.execute(
                "SELECT * FROM vincicasa WHERE data LIKE ? ORDER BY data DESC LIMIT ? OFFSET ?",
                (f"{anno}-%", limit, offset)
            ).fetchall()
            totale = conn.execute("SELECT COUNT(*) FROM vincicasa WHERE data LIKE ?", (f"{anno}-%",)).fetchone()[0]
        else:
            rows = conn.execute("SELECT * FROM vincicasa ORDER BY data DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
            totale = conn.execute("SELECT COUNT(*) FROM vincicasa").fetchone()[0]
    return {"lotteria": "vincicasa", "totale": totale, "limit": limit, "offset": offset, "estrazioni": [_vc_row_to_dict(r) for r in rows]}


@app.get("/api/vincicasa/ultime")
def vc_ultime(n: int = Query(10, le=100)):
    with get_db_ctx() as conn:
        rows = conn.execute("SELECT * FROM vincicasa ORDER BY data DESC LIMIT ?", (n,)).fetchall()
    return {
        "lotteria": "vincicasa",
        "estrazioni": [_vc_row_to_dict(r) for r in rows]
    }


@app.get("/api/vincicasa/statistiche")
def vc_stats():
    base = get_stats("vincicasa")

    with get_db_ctx() as conn:
        rows = conn.execute(
            "SELECT concorso, data, n1, n2, n3, n4, n5, vincite_json FROM vincicasa WHERE vincite_json IS NOT NULL"
        ).fetchall()

    tipo_map = {"14": "5", "13": "4", "12": "3", "11": "2"}
    stats = {c: {"totale_vincite": 0, "totale_importo": 0, "con_vincita": 0,
                  "quota_min": None, "quota_max": 0} for c in ["5", "4", "3", "2"]}
    case_vinte = []

    for r in rows:
        det = _json.loads(r["vincite_json"])
        for v in det.get("vincite", []):
            quota = v.get("quota", {})
            cat = tipo_map.get(quota.get("categoriaVincita", {}).get("tipo", ""))
            if not cat:
                continue
            num = int(v.get("numero", 0))
            importo = quota.get("importo", 0)
            s = stats[cat]
            s["totale_vincite"] += num
            s["totale_importo"] += num * importo
            if num > 0:
                s["con_vincita"] += 1
                if s["quota_min"] is None or importo < s["quota_min"]:
                    s["quota_min"] = importo
                if importo > s["quota_max"]:
                    s["quota_max"] = importo
                if cat == "5":
                    case_vinte.append({
                        "concorso": r["concorso"], "data": r["data"],
                        "numeri": [r["n1"], r["n2"], r["n3"], r["n4"], r["n5"]],
                        "vincitori": num,
                        "importo_euro": _fmt_importo(importo),
                    })

    tot = len(rows)
    categorie = {}
    for cat in ["5", "4", "3", "2"]:
        s = stats[cat]
        categorie[f"punti_{cat}"] = {
            "totale_vincite": s["totale_vincite"],
            "totale_distribuito_euro": _fmt_importo(s["totale_importo"]),
            "estrazioni_con_vincita": s["con_vincita"],
            "percentuale": round(s["con_vincita"] / tot * 100, 1) if tot else 0,
            "quota_media_euro": _fmt_importo(round(s["totale_importo"] / s["totale_vincite"])) if s["totale_vincite"] else "0.00",
            "quota_min_euro": _fmt_importo(s["quota_min"] or 0),
            "quota_max_euro": _fmt_importo(s["quota_max"]),
        }

    base["statistiche_premi"] = categorie
    base["case_vinte"] = {
        "totale": sum(c["vincitori"] for c in case_vinte),
        "estrazioni": sorted(case_vinte, key=lambda x: x["data"], reverse=True),
    }
    return base


_vc_spia_cache = {"data": None, "result": None}


def _vc_calcola_numeri_spia():
    from collections import Counter
    from itertools import combinations

    with get_db_ctx() as conn:
        rows = conn.execute("SELECT n1, n2, n3, n4, n5 FROM vincicasa").fetchall()

    freq_singolo = Counter()
    freq_coppia = Counter()

    for r in rows:
        numeri = sorted([r["n1"], r["n2"], r["n3"], r["n4"], r["n5"]])
        for n in numeri:
            freq_singolo[n] += 1
        for coppia in combinations(numeri, 2):
            freq_coppia[coppia] += 1

    # Salva tutte le coppie ordinate (il top lo applica l'endpoint)
    tutte = []
    for (a, b), freq in freq_coppia.most_common():
        tutte.append({
            "numero_spia": a,
            "numero_associato": b,
            "frequenza_associazione": freq,
            "percentuale": round(freq / freq_singolo[a] * 100, 1),
        })

    return {"totale_estrazioni": len(rows), "coppie": tutte}


@app.get("/api/vincicasa/numeri-spia")
def vc_numeri_spia(top: int = Query(20, le=100)):
    with get_db_ctx() as conn:
        ultima = conn.execute("SELECT data FROM vincicasa ORDER BY data DESC LIMIT 1").fetchone()
    ultima_data = ultima["data"] if ultima else None

    if _vc_spia_cache["data"] != ultima_data:
        _vc_spia_cache["result"] = _vc_calcola_numeri_spia()
        _vc_spia_cache["data"] = ultima_data

    cached = _vc_spia_cache["result"]
    return {
        "lotteria": "vincicasa",
        "aggiornato_il": ultima_data,
        "totale_estrazioni": cached["totale_estrazioni"],
        "coppie": cached["coppie"][:top],
    }


_vc_combi_cache = {"data": None, "result": None}


def _vc_calcola_combinazioni():
    from collections import Counter
    from itertools import combinations

    with get_db_ctx() as conn:
        rows = conn.execute("SELECT n1, n2, n3, n4, n5 FROM vincicasa").fetchall()

    freq_coppie = Counter()
    freq_terni = Counter()

    for r in rows:
        numeri = sorted([r["n1"], r["n2"], r["n3"], r["n4"], r["n5"]])
        for coppia in combinations(numeri, 2):
            freq_coppie[coppia] += 1
        for terno in combinations(numeri, 3):
            freq_terni[terno] += 1

    coppie = [{"numeri": list(k), "frequenza": v} for k, v in freq_coppie.most_common(15)]
    terni = [{"numeri": list(k), "frequenza": v} for k, v in freq_terni.most_common(10)]

    return {"estrazioni_analizzate": len(rows), "coppie": coppie, "terni": terni}


@app.get("/api/vincicasa/combinazioni")
def vc_combinazioni():
    with get_db_ctx() as conn:
        ultima = conn.execute("SELECT data FROM vincicasa ORDER BY data DESC LIMIT 1").fetchone()
    ultima_data = ultima["data"] if ultima else None

    if _vc_combi_cache["data"] != ultima_data:
        _vc_combi_cache["result"] = _vc_calcola_combinazioni()
        _vc_combi_cache["data"] = ultima_data

    cached = _vc_combi_cache["result"]
    return {
        "coppie": cached["coppie"],
        "terni": cached["terni"],
        "estrazioni_analizzate": cached["estrazioni_analizzate"],
        "aggiornato_il": ultima_data,
    }


# ── Eurojackpot ─────────────────────────────────────────────


def _ej_row_to_dict(r) -> dict:
    """Converte una riga DB eurojackpot in dict, con vincite se presenti."""
    d = {
        "concorso": r["concorso"], "data": r["data"],
        "numeri": [r["n1"], r["n2"], r["n3"], r["n4"], r["n5"]],
        "euronumeri": [r["e1"], r["e2"]],
    }
    vincite_raw = r["vincite_json"]
    if vincite_raw:
        det = _json.loads(vincite_raw)
        d["vincite"] = _parse_vincite_gntn(det.get("vincite", []))
        d["totale_vincite"] = int(det.get("numeroTotaleVincite", 0))
    return d


@app.get("/api/eurojackpot/ultima")
def ej_ultima():
    live = get_live("Eurojackpot")
    if live:
        raw = live["raw"]
        comb = raw.get("combinazioneVincente") or {}
        concorso = raw.get("concorso") or {}
        det_vincite = raw.get("dettaglioVincite") or {}

        return {
            "lotteria": "eurojackpot",
            "concorso": concorso.get("numero", ""),
            "anno": concorso.get("anno", ""),
            "data": live["data"],
            "numeri": [int(n) for n in (comb.get("estratti") or [])],
            "euronumeri": [int(n) for n in (comb.get("euronumeri") or [])],
            "jackpot_centesimi": raw.get("jackpot", 0),
            "jackpot_euro": _fmt_importo(raw.get("jackpot", 0)),
            "montepremi_centesimi": raw.get("montepremi", 0),
            "montepremi_euro": _fmt_importo(raw.get("montepremi", 0)),
            "vincite": _parse_vincite_gntn(det_vincite.get("vincite", [])),
            "totale_vincite": int(det_vincite.get("numeroTotaleVincite", 0)),
            "aggiornato_il": live["aggiornato_il"],
        }

    with get_db_ctx() as conn:
        row = conn.execute("SELECT * FROM eurojackpot ORDER BY data DESC LIMIT 1").fetchone()
    if not row:
        return {"errore": "Nessuna estrazione"}
    return {"lotteria": "eurojackpot", **_ej_row_to_dict(row)}


_ej_paese_cache: dict = {"payload": None, "ts": 0.0}
_EJ_PAESE_TTL = 300  # 5 minuti


@app.get("/api/eurojackpot/vincite-per-paese")
def ej_vincite_per_paese():
    import time
    import requests as _req

    now = time.time()
    if _ej_paese_cache["payload"] and now - _ej_paese_cache["ts"] < _EJ_PAESE_TTL:
        return _ej_paese_cache["payload"]

    url = (
        "https://www.eurojackpot.com/wlinfo/WL_InfoService"
        "?client=jsn&gruppe=ZahlenUndQuoten&ewGewsum=ja&spielart=EJ&lang=en"
    )
    try:
        resp = _req.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        raw = resp.json()
    except Exception as ex:
        return {"errore": f"Impossibile recuperare i dati: {ex}"}

    head = raw.get("head", {})
    ziehungen_numeri = raw.get("zahlen", {}).get("hauptlotterie", {}).get("ziehungen", [])

    numeri, euronumeri = [], []
    for z in ziehungen_numeri:
        bezeichnung = z.get("bezeichnung", "")
        if "50" in bezeichnung:
            numeri = [int(n) for n in z.get("zahlenSortiert", [])]
        elif "12" in bezeichnung:
            euronumeri = [int(n) for n in z.get("zahlenSortiert", [])]

    klassen_raw = (
        raw.get("auswertung", {})
           .get("quoten", {})
           .get("hauptlotterie", {})
           .get("ziehungen", [{}])[0]
           .get("gewinnklassen", [])
    )

    vincite = []
    for k in klassen_raw:
        aufteilung = k.get("aufteilung")
        entry = {
            "klasse": k["klasse"],
            "descrizione": k["beschreibung"],
            "abbreviazione": k["kurzbeschreibung"],
            "totale_vincitori": k["anzahl"],
            "vincita_euro": k["quote"],
        }
        if k.get("jackpot"):
            entry["jackpot_euro"] = k["jackpot"]
        if aufteilung is not None:
            entry["per_paese"] = [
                {
                    "paese": a["land"],
                    "alpha3": a["landAlpha3"],
                    "provincia": a.get("provinz"),
                    "provincia_iso": a.get("provinzIsoCode"),
                    "vincitori": a["anzahl"],
                }
                for a in aufteilung
            ]
        vincite.append(entry)

    payload = {
        "lotteria": "eurojackpot",
        "data": head.get("datum"),
        "numeri": numeri,
        "euronumeri": euronumeri,
        "vincite": vincite,
        "aggiornato_il": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "fonte": "eurojackpot.com",
    }

    _ej_paese_cache["payload"] = payload
    _ej_paese_cache["ts"] = now
    return payload


@app.get("/api/eurojackpot/archivio")
def ej_archivio(anno: Optional[int] = None, limit: int = Query(100, le=10000), offset: int = 0):
    with get_db_ctx() as conn:
        if anno:
            rows = conn.execute(
                "SELECT * FROM eurojackpot WHERE data LIKE ? ORDER BY data DESC LIMIT ? OFFSET ?",
                (f"{anno}-%", limit, offset)
            ).fetchall()
            totale = conn.execute("SELECT COUNT(*) FROM eurojackpot WHERE data LIKE ?", (f"{anno}-%",)).fetchone()[0]
        else:
            rows = conn.execute("SELECT * FROM eurojackpot ORDER BY data DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
            totale = conn.execute("SELECT COUNT(*) FROM eurojackpot").fetchone()[0]
    return {"lotteria": "eurojackpot", "totale": totale, "limit": limit, "offset": offset,
            "estrazioni": [_ej_row_to_dict(r) for r in rows]}


@app.get("/api/eurojackpot/ultime")
def ej_ultime(n: int = Query(10, le=100)):
    with get_db_ctx() as conn:
        rows = conn.execute("SELECT * FROM eurojackpot ORDER BY data DESC LIMIT ?", (n,)).fetchall()
    return {
        "lotteria": "eurojackpot",
        "estrazioni": [_ej_row_to_dict(r) for r in rows]
    }


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


_ej_ambi_cache = {"data": None, "result": None}


def _ej_calcola_ambi_ritardatari():
    from itertools import combinations

    with get_db_ctx() as conn:
        rows = conn.execute(
            "SELECT data, n1, n2, n3, n4, n5 FROM eurojackpot ORDER BY data ASC"
        ).fetchall()

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


_ej_spia_cache = {"data": None, "result": None}


def _ej_calcola_numeri_spia():
    from collections import Counter

    with get_db_ctx() as conn:
        rows = conn.execute(
            "SELECT n1, n2, n3, n4, n5 FROM eurojackpot ORDER BY data ASC"
        ).fetchall()

    totale = len(rows)
    spia_counts = {}

    for i in range(totale - 1):
        numeri_corrente = set([rows[i]["n1"], rows[i]["n2"], rows[i]["n3"], rows[i]["n4"], rows[i]["n5"]])
        numeri_successivo = set([rows[i+1]["n1"], rows[i+1]["n2"], rows[i+1]["n3"], rows[i+1]["n4"], rows[i+1]["n5"]])

        for n in numeri_corrente:
            if n not in spia_counts:
                spia_counts[n] = Counter()
            for s in numeri_successivo:
                if s != n:
                    spia_counts[n][s] += 1

    risultati = []
    for numero, counter in spia_counts.items():
        top5 = counter.most_common(5)
        if not top5:
            continue
        spiati = [s for s, _ in top5]
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

    oggi = date.today()
    prossima = None
    for delta in range(1, 8):
        giorno = oggi + timedelta(days=delta)
        if giorno.weekday() in (1, 4):
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


# ── SiVinceTutto ────────────────────────────────────────────

@app.get("/api/sivincetutto/ultima")
def svt_ultima():
    live = get_live("SiVinceTutto")
    if live:
        raw = live["raw"]
        comb = raw.get("combinazioneVincente") or {}
        concorso = raw.get("concorso") or {}
        montepremi = raw.get("montepremi") or {}
        det_vincite = raw.get("dettaglioVincite") or {}

        return {
            "lotteria": "sivincetutto",
            "concorso": concorso.get("numero", ""),
            "anno": concorso.get("anno", ""),
            "data": live["data"],
            "numeri": [int(n) for n in (comb.get("estratti") or [])],
            "montepremi_centesimi": montepremi.get("montepremiTotale", 0),
            "montepremi_euro": _fmt_importo(montepremi.get("montepremiTotale", 0)),
            "vincite": _parse_vincite_gntn(det_vincite.get("vincite", [])),
            "totale_vincite": int(det_vincite.get("numeroTotaleVincite", 0)),
            "aggiornato_il": live["aggiornato_il"],
        }

    with get_db_ctx() as conn:
        row = conn.execute("SELECT * FROM sivincetutto ORDER BY data DESC LIMIT 1").fetchone()
    if not row:
        return {"errore": "Nessuna estrazione"}
    return {
        "lotteria": "sivincetutto",
        "concorso": row["concorso"], "data": row["data"],
        "numeri": [row["n1"], row["n2"], row["n3"], row["n4"], row["n5"], row["n6"]],
    }


@app.get("/api/sivincetutto/archivio")
def svt_archivio(anno: Optional[int] = None, limit: int = Query(100, le=10000), offset: int = 0):
    with get_db_ctx() as conn:
        if anno:
            rows = conn.execute(
                "SELECT * FROM sivincetutto WHERE data LIKE ? ORDER BY data DESC LIMIT ? OFFSET ?",
                (f"{anno}-%", limit, offset)
            ).fetchall()
            totale = conn.execute("SELECT COUNT(*) FROM sivincetutto WHERE data LIKE ?", (f"{anno}-%",)).fetchone()[0]
        else:
            rows = conn.execute("SELECT * FROM sivincetutto ORDER BY data DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
            totale = conn.execute("SELECT COUNT(*) FROM sivincetutto").fetchone()[0]
    return {"lotteria": "sivincetutto", "totale": totale, "limit": limit, "offset": offset, "estrazioni": rows_to_list(rows)}


@app.get("/api/sivincetutto/ultime")
def svt_ultime(n: int = Query(10, le=100)):
    with get_db_ctx() as conn:
        rows = conn.execute("SELECT * FROM sivincetutto ORDER BY data DESC LIMIT ?", (n,)).fetchall()
    return {
        "lotteria": "sivincetutto",
        "estrazioni": [{
            "concorso": r["concorso"], "data": r["data"],
            "numeri": [r["n1"], r["n2"], r["n3"], r["n4"], r["n5"], r["n6"]],
        } for r in rows]
    }


@app.get("/api/sivincetutto/statistiche")
def svt_stats():
    return get_stats("sivincetutto")


# ── Win for Life ────────────────────────────────────────────

@app.get("/api/winforlife/{tipo}/ultima")
def wfl_ultima(tipo: str):
    if tipo not in ("classico", "grattacieli"):
        return {"errore": "Tipo non valido (classico/grattacieli)"}

    gioco_map = {"classico": "Win for Life Classico", "grattacieli": "Win for Life Grattacieli"}
    live = get_live(gioco_map[tipo])
    if live:
        raw = live["raw"]
        comb = raw.get("combinazioneVincente") or {}
        concorso = raw.get("concorso") or {}
        det_vincite = raw.get("dettaglioVincite") or {}

        return {
            "lotteria": f"winforlife_{tipo}",
            "concorso": concorso.get("numero", ""),
            "anno": concorso.get("anno", ""),
            "data": live["data"],
            "numeri": [int(n) for n in (comb.get("estratti") or [])],
            "numerone": int(comb["numerone"]) if comb.get("numerone") else None,
            "montepremi_centesimi": raw.get("montepremi", 0),
            "montepremi_euro": _fmt_importo(raw.get("montepremi", 0)),
            "vincite": _parse_vincite_gntn(det_vincite.get("vincite", [])),
            "totale_vincite": int(det_vincite.get("numeroTotaleVincite", 0)),
            "aggiornato_il": live["aggiornato_il"],
        }

    with get_db_ctx() as conn:
        row = conn.execute("SELECT * FROM winforlife WHERE tipo = ? ORDER BY data DESC, ora DESC LIMIT 1", (tipo,)).fetchone()
    if not row:
        return {"errore": "Nessuna estrazione"}
    return {
        "lotteria": f"winforlife_{tipo}",
        "concorso": row["concorso"], "data": row["data"], "ora": row["ora"],
        "numeri": [row[f"n{i}"] for i in range(1, 11)],
        "numerone": row["numerone"],
    }


@app.get("/api/winforlife/{tipo}/archivio")
def wfl_archivio(tipo: str, limit: int = Query(100, le=10000), offset: int = 0):
    if tipo not in ("classico", "grattacieli"):
        return {"errore": "Tipo non valido (classico/grattacieli)"}
    with get_db_ctx() as conn:
        rows = conn.execute(
            "SELECT * FROM winforlife WHERE tipo = ? ORDER BY data DESC, ora DESC LIMIT ? OFFSET ?",
            (tipo, limit, offset)
        ).fetchall()
        totale = conn.execute("SELECT COUNT(*) FROM winforlife WHERE tipo = ?", (tipo,)).fetchone()[0]
    return {"lotteria": f"winforlife_{tipo}", "totale": totale, "limit": limit, "offset": offset, "estrazioni": rows_to_list(rows)}


@app.get("/api/winforlife/{tipo}/ultime")
def wfl_ultime(tipo: str, n: int = Query(10, le=100)):
    if tipo not in ("classico", "grattacieli"):
        return {"errore": "Tipo non valido (classico/grattacieli)"}
    with get_db_ctx() as conn:
        rows = conn.execute("SELECT * FROM winforlife WHERE tipo = ? ORDER BY data DESC, ora DESC LIMIT ?", (tipo, n)).fetchall()
    return {
        "lotteria": f"winforlife_{tipo}",
        "estrazioni": [{
            "concorso": r["concorso"], "data": r["data"], "ora": r["ora"],
            "numeri": [r[f"n{i}"] for i in range(1, 11)],
            "numerone": r["numerone"],
        } for r in rows]
    }


# ── Simbolotto ──────────────────────────────────────────────

@app.get("/api/simbolotto/ultima")
def simb_ultima():
    live = get_live("Simbolotto")
    if live:
        raw = live["raw"]
        return {
            "lotteria": "simbolotto",
            "data": live["data"],
            "ruota": raw.get("ruota", ""),
            "numeri": [int(n) for n in (raw.get("simbolotti") or [])],
            "aggiornato_il": live["aggiornato_il"],
        }

    with get_db_ctx() as conn:
        row = conn.execute("SELECT * FROM simbolotto ORDER BY data DESC LIMIT 1").fetchone()
    if not row:
        return {"errore": "Nessuna estrazione"}
    return {
        "lotteria": "simbolotto",
        "data": row["data"], "ruota": row["ruota"],
        "numeri": [row["n1"], row["n2"], row["n3"], row["n4"], row["n5"]],
    }


@app.get("/api/simbolotto/archivio")
def simb_archivio(anno: Optional[int] = None, limit: int = Query(100, le=10000), offset: int = 0):
    with get_db_ctx() as conn:
        if anno:
            rows = conn.execute(
                "SELECT * FROM simbolotto WHERE data LIKE ? ORDER BY data DESC LIMIT ? OFFSET ?",
                (f"{anno}-%", limit, offset)
            ).fetchall()
            totale = conn.execute("SELECT COUNT(*) FROM simbolotto WHERE data LIKE ?", (f"{anno}-%",)).fetchone()[0]
        else:
            rows = conn.execute("SELECT * FROM simbolotto ORDER BY data DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
            totale = conn.execute("SELECT COUNT(*) FROM simbolotto").fetchone()[0]
    return {"lotteria": "simbolotto", "totale": totale, "limit": limit, "offset": offset, "estrazioni": rows_to_list(rows)}


@app.get("/api/simbolotto/ultime")
def simb_ultime(n: int = Query(10, le=100)):
    with get_db_ctx() as conn:
        rows = conn.execute("SELECT * FROM simbolotto ORDER BY data DESC LIMIT ?", (n,)).fetchall()
    return {
        "lotteria": "simbolotto",
        "estrazioni": [{
            "concorso": r["concorso"], "data": r["data"], "ruota": r["ruota"],
            "numeri": [r["n1"], r["n2"], r["n3"], r["n4"], r["n5"]],
        } for r in rows]
    }


@app.get("/api/simbolotto/statistiche")
def simb_stats():
    return get_stats("simbolotto")


# ── 10eLotto ogni 5 minuti (live) ──────────────────────────

_10E5_URL = "https://www.10elotto5.it/wp-content/themes/twentysixteen-child/10elotto5/estrazioni10elotto5.php"
_10e5_cache = {"data": None, "ts": 0, "estrazioni_prec": None, "aggiornato_il": None}

@app.get("/api/10elotto5min/ultime")
def dl5_ultime():
    """Ultime estrazioni 10eLotto ogni 5 minuti (live da 10elotto5.it)."""
    import cloudscraper

    # Cache 60 secondi per non bombardare la fonte
    now = time.time()
    if _10e5_cache["data"] and now - _10e5_cache["ts"] < 60:
        return _10e5_cache["data"]

    try:
        scraper = cloudscraper.create_scraper()
        r = scraper.get(_10E5_URL, timeout=10)
        scraper.close()
        if r.status_code != 200:
            return {"errore": "Fonte non disponibile"}

        raw = r.json()
        estrazioni = []
        for e in raw.get("estrazioni", []):
            estrazioni.append({
                "concorso": int(e.get("nestr", 0)),
                "data": e.get("data", ""),
                "ora": e.get("ora", "")[:5],
                "numeri": [int(e.get(f"c{i}", 0)) for i in range(1, 21)],
                "numero_oro": int(e.get("Oro", 0)),
                "doppio_oro": int(e.get("dOro", 0)),
                "extra": [int(e.get(f"e{i}", 0)) for i in range(1, 16)],
            })

        # Aggiorna aggiornato_il solo se i dati sono effettivamente cambiati
        if estrazioni != _10e5_cache["estrazioni_prec"]:
            _10e5_cache["aggiornato_il"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            _10e5_cache["estrazioni_prec"] = estrazioni

        risposta = {
            "lotteria": "10elotto5min",
            "estrazioni": estrazioni,
            "totale": len(estrazioni),
            "aggiornato_il": _10e5_cache["aggiornato_il"],
        }
        _10e5_cache["data"] = risposta
        _10e5_cache["ts"] = now
        return risposta

    except Exception as ex:
        return {"errore": f"Errore recupero dati: {ex}"}


# ── Globali ─────────────────────────────────────────────────

@app.get("/api/tutte/ultime")
def tutte_ultime():
    return {
        "millionday": md_ultima(),
        "superenalotto": se_ultima(),
        "lotto": lo_ultima(),
        "diecelotto": dl_ultima(),
        "vincicasa": vc_ultima(),
        "eurojackpot": ej_ultima(),
        "sivincetutto": svt_ultima(),
        "winforlife_classico": wfl_ultima("classico"),
        "winforlife_grattacieli": wfl_ultima("grattacieli"),
        "simbolotto": simb_ultima(),
    }


@app.get("/api/tutte/statistiche")
def tutte_stats(limit: int = Query(10, ge=1, le=90), gioco: str = Query(None)):
    with get_db_ctx() as conn:
        if gioco:
            rows = conn.execute(
                "SELECT * FROM statistiche WHERE lotteria = ? ORDER BY numero ASC",
                (gioco,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM statistiche ORDER BY lotteria ASC, numero ASC"
            ).fetchall()

    if not rows:
        return {"errore": "Statistiche non calcolate"}

    per_gioco = {}
    for r in rows:
        d = dict(r)
        lot = d["lotteria"]
        if lot not in per_gioco:
            per_gioco[lot] = {"aggiornato_il": d["aggiornato_il"], "numeri": []}
        per_gioco[lot]["numeri"].append(d)

    risultato = {}
    for lot, info in per_gioco.items():
        numeri = info["numeri"]
        risultato[lot] = {
            "lotteria": lot,
            "aggiornato_il": info["aggiornato_il"],
            "top_ritardatari": sorted(numeri, key=lambda x: x["ritardo_attuale"], reverse=True)[:limit],
            "top_frequenti": sorted(numeri, key=lambda x: x["frequenza"], reverse=True)[:limit],
        }

    return risultato


@app.get("/api/ricalcola")
def ricalcola(request: Request):
    client = request.client.host
    if client not in ("127.0.0.1", "::1"):
        return JSONResponse(status_code=403, content={"errore": "Solo localhost"})
    from app.stats import calcola_tutte
    calcola_tutte()
    return {"stato": "ok", "messaggio": "Statistiche ricalcolate"}


@app.get("/api/stato")
def stato():
    with get_db_ctx() as conn:
        r = {}
        for t in TABELLE_VALIDE:
            r[t] = conn.execute("SELECT COUNT(*) FROM " + t).fetchone()[0]
    return {"stato": "ok", "estrazioni": r}