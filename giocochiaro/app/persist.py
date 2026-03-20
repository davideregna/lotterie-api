import json
from datetime import datetime
from app.database import get_db_ctx


def _parse_data(data_raw: str) -> str | None:
    data_raw = data_raw.strip().split(" ")[0]
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(data_raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _parse_ora(data_raw: str) -> str:
    parts = data_raw.strip().split(" ")
    if len(parts) >= 2 and ":" in parts[-1]:
        return parts[-1]
    return "20:30"


def _concorso_int(concorso) -> int:
    if isinstance(concorso, int):
        return concorso
    if isinstance(concorso, str) and concorso.isdigit():
        return int(concorso)
    return 0


# ── Live data (JSON completo) ──────────────────────────────────────

def salva_live(e) -> None:
    """Salva il JSON grezzo nella tabella live_data per gli endpoint /ultima.

    Aggiorna aggiornato_il SOLO se i dati sono effettivamente cambiati.
    """
    if not e.raw_data:
        return
    data = _parse_data(e.data) or ""
    new_json = json.dumps(e.raw_data, ensure_ascii=False)

    with get_db_ctx() as conn:
        row = conn.execute(
            "SELECT raw_json FROM live_data WHERE gioco = ?", (e.gioco,)
        ).fetchone()

        if row and json.loads(row["raw_json"]) == e.raw_data:
            return

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        conn.execute("""
            INSERT OR REPLACE INTO live_data (gioco, data, raw_json, aggiornato_il)
            VALUES (?, ?, ?, ?)
        """, (e.gioco, data, new_json, now))
        conn.commit()


def get_live(gioco: str) -> dict | None:
    """Legge il JSON grezzo dalla tabella live_data."""
    with get_db_ctx() as conn:
        row = conn.execute(
            "SELECT raw_json, data, aggiornato_il FROM live_data WHERE gioco = ?",
            (gioco,)
        ).fetchone()
    if not row:
        return None
    return {
        "raw": json.loads(row["raw_json"]),
        "data": row["data"],
        "aggiornato_il": row["aggiornato_il"],
    }


# ── Salvataggio archivio ──────────────────────────────────────────

def salva_millionday(e) -> bool:
    if len(e.numeri) != 5:
        return False
    data = _parse_data(e.data)
    if not data:
        return False
    ora = _parse_ora(e.data)
    extra = e.extra if len(e.extra) == 5 else [0, 0, 0, 0, 0]

    with get_db_ctx() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT OR IGNORE INTO millionday
            (data, ora, n1, n2, n3, n4, n5, e1, e2, e3, e4, e5)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (data, ora, *e.numeri, *extra))
        conn.commit()
        return c.rowcount > 0


def salva_superenalotto(e) -> bool:
    if len(e.numeri) != 6:
        return False
    data = _parse_data(e.data)
    if not data:
        return False

    with get_db_ctx() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT OR IGNORE INTO superenalotto
            (concorso, data, n1, n2, n3, n4, n5, n6, jolly, superstar)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (_concorso_int(e.concorso), data, *e.numeri, e.jolly or 0, e.superstar or 0))
        conn.commit()
        return c.rowcount > 0


def salva_lotto(e) -> bool:
    if not e.ruote:
        return False
    data = _parse_data(e.data)
    if not data:
        return False

    inseriti = 0
    with get_db_ctx() as conn:
        c = conn.cursor()
        for ruota, numeri in e.ruote.items():
            if len(numeri) != 5:
                continue
            c.execute("""
                INSERT OR IGNORE INTO lotto (data, ruota, n1, n2, n3, n4, n5)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (data, ruota, *numeri))
            inseriti += c.rowcount
        conn.commit()
    return inseriti > 0


def salva_diecelotto(e) -> bool:
    if len(e.numeri) != 20:
        return False
    data = _parse_data(e.data)
    if not data:
        return False

    col_numeri = ", ".join([f"n{i}" for i in range(1, 21)])
    placeholders = ", ".join(["?"] * 23)

    with get_db_ctx() as conn:
        c = conn.cursor()
        c.execute(f"""
            INSERT OR IGNORE INTO diecelotto (data, {col_numeri}, numero_oro, doppio_oro)
            VALUES ({placeholders})
        """, (data, *e.numeri, e.numero_oro or 0, 0))
        conn.commit()
        return c.rowcount > 0


def salva_vincicasa(e) -> bool:
    if len(e.numeri) != 5:
        return False
    data = _parse_data(e.data)
    if not data:
        return False

    with get_db_ctx() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT OR IGNORE INTO vincicasa (concorso, data, n1, n2, n3, n4, n5)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (_concorso_int(e.concorso), data, *e.numeri))
        conn.commit()
        return c.rowcount > 0


def salva_eurojackpot(e) -> bool:
    if len(e.numeri) != 5 or len(e.euronumeri) != 2:
        return False
    data = _parse_data(e.data)
    if not data:
        return False

    with get_db_ctx() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT OR IGNORE INTO eurojackpot (concorso, data, n1, n2, n3, n4, n5, e1, e2)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (_concorso_int(e.concorso), data, *e.numeri, *e.euronumeri))
        conn.commit()
        return c.rowcount > 0


def salva_sivincetutto(e) -> bool:
    if len(e.numeri) != 6:
        return False
    data = _parse_data(e.data)
    if not data:
        return False

    with get_db_ctx() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT OR IGNORE INTO sivincetutto (concorso, data, n1, n2, n3, n4, n5, n6)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (_concorso_int(e.concorso), data, *e.numeri))
        conn.commit()
        return c.rowcount > 0


def salva_winforlife(e) -> bool:
    if len(e.numeri) != 10:
        return False
    data = _parse_data(e.data)
    if not data:
        return False

    if "Classico" in e.gioco:
        tipo = "classico"
    elif "Grattacieli" in e.gioco:
        tipo = "grattacieli"
    else:
        return False

    ora = _parse_ora(e.data) if " " in e.data.strip() else ""

    with get_db_ctx() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT OR IGNORE INTO winforlife
            (tipo, concorso, data, ora, n1, n2, n3, n4, n5, n6, n7, n8, n9, n10, numerone)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (tipo, _concorso_int(e.concorso), data, ora, *e.numeri, e.numerone or 0))
        conn.commit()
        return c.rowcount > 0


def salva_simbolotto(e) -> bool:
    if len(e.numeri) != 5:
        return False
    data = _parse_data(e.data)
    if not data:
        return False

    ruota = ""
    if hasattr(e, "ruote") and isinstance(e.ruote, dict):
        ruota = e.ruote.get("ruota", "")
    elif hasattr(e, "raw_data") and isinstance(e.raw_data, dict):
        ruota = e.raw_data.get("ruota", "")

    with get_db_ctx() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT OR IGNORE INTO simbolotto (concorso, data, ruota, n1, n2, n3, n4, n5)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (_concorso_int(e.concorso), data, ruota, *e.numeri))
        conn.commit()
        return c.rowcount > 0


SALVA_MAP = {
    "MillionDAY": salva_millionday,
    "SuperEnalotto": salva_superenalotto,
    "Lotto": salva_lotto,
    "10eLotto": salva_diecelotto,
    "VinciCasa": salva_vincicasa,
    "Eurojackpot": salva_eurojackpot,
    "SiVinceTutto": salva_sivincetutto,
    "Win for Life Classico": salva_winforlife,
    "Win for Life Grattacieli": salva_winforlife,
    "Simbolotto": salva_simbolotto,
}


def salva_estrazione(e) -> bool:
    """Salva nell'archivio DB + aggiorna i dati live + appende al file .txt."""
    # Salva sempre il JSON live
    salva_live(e)

    # Salva nell'archivio DB
    fn = SALVA_MAP.get(e.gioco)
    if fn:
        try:
            nuova = fn(e)
            # Se è una nuova estrazione, appende anche al file .txt
            if nuova:
                from app.txt_append import append_estrazione
                append_estrazione(e)
            return nuova
        except Exception as ex:
            print(f"  ERRORE salvataggio {e.gioco}: {ex}")
            return False
    return False