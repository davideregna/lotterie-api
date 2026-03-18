"""
Appende le nuove estrazioni ai file .txt di archivio.
Chiamato da persist.salva_estrazione() ogni volta che una nuova estrazione viene salvata nel DB.
"""

import os
from datetime import datetime
from app.config import DATA_DIR


def _data_ddmmyyyy(data_raw: str) -> str:
    """Converte qualsiasi formato data in DD/MM/YYYY."""
    data_raw = data_raw.strip().split(" ")[0]
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(data_raw, fmt).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return ""


def _data_iso(data_raw: str) -> str:
    """Converte qualsiasi formato data in YYYY-MM-DD."""
    data_raw = data_raw.strip().split(" ")[0]
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(data_raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


def _append_line(filename: str, line: str):
    filepath = os.path.join(DATA_DIR, filename)
    if not os.path.exists(filepath):
        return
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def append_superenalotto(e):
    if len(e.numeri) != 6:
        return
    data = _data_iso(e.data)
    if not data:
        return
    jolly = str(e.jolly or 0).zfill(2)
    superstar = str(e.superstar or 0).zfill(2)
    nums = "\t".join(str(n).zfill(2) for n in e.numeri)
    _append_line("superenalotto.txt", f"{data}\t{nums}\t\t{jolly}\t{superstar}")


def append_millionday(e):
    if len(e.numeri) != 5:
        return
    data = _data_iso(e.data)
    if not data:
        return
    parts = e.data.strip().split(" ")
    ora = parts[-1].replace(":", ".") if len(parts) >= 2 and ":" in parts[-1] else "20.30"
    draw_num = "02" if ora >= "18" else "01"
    extra = e.extra if len(e.extra) == 5 else [0, 0, 0, 0, 0]
    nums = "\t".join(str(n).zfill(2) for n in e.numeri)
    extra_str = ".".join(str(n).zfill(2) for n in extra)
    _append_line("millionday.txt", f"{data}/{draw_num} {ora}\t{nums}\t\t{extra_str}")


def append_lotto(e):
    if not e.ruote:
        return
    data = _data_ddmmyyyy(e.data)
    if not data:
        return
    concorso = e.concorso or "0"
    ruote_nomi = ["Bari", "Cagliari", "Firenze", "Genova", "Milano",
                  "Napoli", "Palermo", "Roma", "Torino", "Venezia", "Nazionale"]
    ruote_str = []
    for nome in ruote_nomi:
        numeri = e.ruote.get(nome, [])
        if len(numeri) == 5:
            ruote_str.append(" ".join(str(n) for n in numeri) + " ")
        else:
            ruote_str.append("     ")
    _append_line("lotto.txt", f"{concorso}\t{data}\t" + "\t".join(ruote_str))


def append_diecelotto(e):
    if len(e.numeri) != 20:
        return
    data = _data_ddmmyyyy(e.data)
    if not data:
        return
    concorso = e.concorso or "0"
    nums = "\t".join(str(n) for n in e.numeri)
    oro = str(e.numero_oro or 0)
    oro2 = "-"
    extra_parts = [str(x) for x in (e.extra or [])]
    if not extra_parts:
        extra_parts = ["-"] * 15
    extras = "\t".join(extra_parts)
    _append_line("10elotto.txt", f"{concorso}\t{data}\t{nums}\t{oro}\t{oro2}\t{extras}")


def append_eurojackpot(e):
    if len(e.numeri) != 5 or len(e.euronumeri) != 2:
        return
    data = _data_ddmmyyyy(e.data)
    if not data:
        return
    concorso = e.concorso or "0"
    nums = "\t".join(str(n) for n in e.numeri)
    euros = "\t".join(str(n) for n in e.euronumeri)
    _append_line("eurojackpot.txt", f"{concorso}\t{data}\t{nums}\t{euros}")


def append_vincicasa(e):
    if len(e.numeri) != 5:
        return
    data = _data_ddmmyyyy(e.data)
    if not data:
        return
    concorso = e.concorso or "0"
    nums = "\t".join(str(n) for n in e.numeri)
    _append_line("vincicasa.txt", f"{concorso}\t{data}\t{nums}")


def append_sivincetutto(e):
    if len(e.numeri) != 6:
        return
    data = _data_ddmmyyyy(e.data)
    if not data:
        return
    concorso = e.concorso or "0"
    nums = "\t".join(str(n) for n in e.numeri)
    _append_line("sivincetutto.txt", f"{concorso}\t{data}\t{nums}")


def append_winforlife(e):
    if len(e.numeri) != 10:
        return
    data = _data_ddmmyyyy(e.data)
    if not data:
        return
    concorso = e.concorso or "0"
    ora = ""
    parts = e.data.strip().split(" ")
    if len(parts) >= 2:
        ora = parts[-1]
    nums = "\t".join(str(n) for n in e.numeri)
    numerone = str(e.numerone or 0)
    _append_line("winforlife.txt", f"{concorso}\t{data}\t{ora}\t{nums}\t{numerone}")


def append_simbolotto(e):
    if len(e.numeri) != 5:
        return
    data = _data_ddmmyyyy(e.data)
    if not data:
        return
    concorso = e.concorso or "0"
    ruota = ""
    if hasattr(e, "ruote") and isinstance(e.ruote, dict):
        ruota = e.ruote.get("ruota", "")
    elif hasattr(e, "raw_data") and isinstance(e.raw_data, dict):
        ruota = e.raw_data.get("ruota", "")
    nums = "\t".join(str(n) for n in e.numeri)
    _append_line("simbolotto.txt", f"{concorso}\t{data}\t{ruota}\t{nums}")


APPEND_MAP = {
    "MillionDAY": append_millionday,
    "SuperEnalotto": append_superenalotto,
    "Lotto": append_lotto,
    "10eLotto": append_diecelotto,
    "VinciCasa": append_vincicasa,
    "Eurojackpot": append_eurojackpot,
    "SiVinceTutto": append_sivincetutto,
    "Win for Life Classico": append_winforlife,
    "Win for Life Grattacieli": append_winforlife,
    "Simbolotto": append_simbolotto,
}


def append_estrazione(e):
    """Appende un'estrazione al file .txt corrispondente."""
    fn = APPEND_MAP.get(e.gioco)
    if fn:
        try:
            fn(e)
        except Exception as ex:
            print(f"  WARN: append txt {e.gioco}: {ex}")
