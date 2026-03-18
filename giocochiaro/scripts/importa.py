import os
import sys

# Aggiungi la root del progetto al path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import get_db_ctx, init_db
from app.config import DATA_DIR

BATCH_SIZE = 1000


def importa_millionday():
    filepath = os.path.join(DATA_DIR, "millionday.txt")
    if not os.path.exists(filepath):
        print("data/millionday.txt non trovato!")
        return

    with get_db_ctx() as conn:
        c = conn.cursor()
        batch = []
        importati = 0
        duplicati = 0

        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or not line[0].isdigit():
                    continue

                try:
                    parts = line.split("\t")
                    data_ora_raw = parts[0].strip()
                    data = data_ora_raw[:10]
                    ora = data_ora_raw.split(" ")[-1].replace(".", ":")

                    numeri = []
                    for p in parts[1:6]:
                        p = p.strip()
                        if p and p.isdigit():
                            numeri.append(int(p))

                    if len(numeri) != 5:
                        continue

                    extra = [0, 0, 0, 0, 0]
                    for p in parts:
                        p = p.strip()
                        if "." in p and len(p.split(".")) == 5:
                            try:
                                vals = [int(x) for x in p.split(".")]
                                if any(v != 0 for v in vals):
                                    extra = vals
                                elif extra == [0, 0, 0, 0, 0]:
                                    extra = vals
                            except ValueError:
                                continue
                            break

                    batch.append((data, ora, *numeri, *extra))

                    if len(batch) >= BATCH_SIZE:
                        c.executemany("""
                            INSERT OR IGNORE INTO millionday
                            (data, ora, n1, n2, n3, n4, n5, e1, e2, e3, e4, e5)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, batch)
                        importati += c.rowcount
                        duplicati += len(batch) - c.rowcount
                        batch.clear()

                except (ValueError, IndexError):
                    continue

        if batch:
            c.executemany("""
                INSERT OR IGNORE INTO millionday
                (data, ora, n1, n2, n3, n4, n5, e1, e2, e3, e4, e5)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, batch)
            importati += c.rowcount
            duplicati += len(batch) - c.rowcount

        conn.commit()
        totale = c.execute("SELECT COUNT(*) FROM millionday").fetchone()[0]

    print(f"MillionDay: {importati} importate, {duplicati} duplicate, {totale} totali nel DB.")


def _parse_se_txt(filepath):
    risultati = []
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if len(line) < 10 or line[4] != "-" or line[7] != "-":
                continue
            try:
                parts = line.split("\t")
                data = parts[0].strip()
                numeri_raw = [p.strip() for p in parts[1:] if p.strip()]
                if len(numeri_raw) < 8:
                    continue
                numeri = [int(numeri_raw[i]) for i in range(6)]
                jolly = int(numeri_raw[6])
                superstar = int(numeri_raw[7])
                risultati.append((0, data, *numeri, jolly, superstar))
            except (ValueError, IndexError):
                continue
    return risultati


def _parse_se_csv(filepath):
    risultati = []
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or not line[0].isdigit():
                continue
            try:
                if ";" in line:
                    parts = line.split(";")
                elif "," in line:
                    parts = line.split(",")
                else:
                    parts = line.split("\t")
                parts = [p.strip() for p in parts if p.strip()]
                if len(parts) >= 8:
                    concorso = int(parts[0]) if len(parts) > 8 else 0
                    data = parts[1] if len(parts) > 8 else parts[0]
                    start = 2 if len(parts) > 8 else 1
                    numeri = [int(parts[start + i]) for i in range(6)]
                    jolly = int(parts[start + 6]) if len(parts) > start + 6 else 0
                    superstar = int(parts[start + 7]) if len(parts) > start + 7 else 0
                    risultati.append((concorso, data, *numeri, jolly, superstar))
            except (ValueError, IndexError):
                continue
    return risultati


def importa_superenalotto():
    txt_path = os.path.join(DATA_DIR, "superenalotto.txt")
    csv_path = os.path.join(DATA_DIR, "superenalotto.csv")

    tutti = []

    if os.path.exists(txt_path):
        tutti.extend(_parse_se_txt(txt_path))
        print(f"  superenalotto.txt: {len(tutti)} righe lette")

    csv_count_before = len(tutti)
    if os.path.exists(csv_path):
        tutti.extend(_parse_se_csv(csv_path))
        print(f"  superenalotto.csv: {len(tutti) - csv_count_before} righe lette")

    if not tutti:
        print("Nessun file SuperEnalotto trovato, skip.")
        return

    with get_db_ctx() as conn:
        c = conn.cursor()
        importati = 0

        for i in range(0, len(tutti), BATCH_SIZE):
            batch = tutti[i:i + BATCH_SIZE]
            c.executemany("""
                INSERT OR IGNORE INTO superenalotto
                (concorso, data, n1, n2, n3, n4, n5, n6, jolly, superstar)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, batch)
            importati += c.rowcount

        conn.commit()
        totale = c.execute("SELECT COUNT(*) FROM superenalotto").fetchone()[0]

    duplicati = len(tutti) - importati
    print(f"SuperEnalotto: {importati} importate, {duplicati} duplicate, {totale} totali nel DB.")


def importa_lotto():
    """Importa lotto.txt in formato xamig: Concorso\tData\tBari_nums\tCagliari_nums\t..."""
    filepath = os.path.join(DATA_DIR, "lotto.txt")
    if not os.path.exists(filepath):
        print("data/lotto.txt non trovato, skip.")
        return

    from datetime import datetime

    ruote_nomi = ["Bari", "Cagliari", "Firenze", "Genova", "Milano",
                  "Napoli", "Palermo", "Roma", "Torino", "Venezia", "Nazionale"]

    with get_db_ctx() as conn:
        c = conn.cursor()
        batch = []
        importati = 0

        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t")
                if not parts[0].strip().isdigit():
                    continue
                try:
                    data_raw = parts[1].strip()
                    data = datetime.strptime(data_raw, "%d/%m/%Y").strftime("%Y-%m-%d")

                    # Ogni ruota è nella colonna parts[2+i] con numeri separati da spazi
                    for i, ruota in enumerate(ruote_nomi):
                        if 2 + i >= len(parts):
                            break
                        campo = parts[2 + i].strip()
                        if not campo:
                            continue
                        nums = [int(x) for x in campo.split() if x.isdigit()]
                        if len(nums) == 5:
                            batch.append((data, ruota, *nums))

                    if len(batch) >= BATCH_SIZE:
                        c.executemany("""
                            INSERT OR IGNORE INTO lotto
                            (data, ruota, n1, n2, n3, n4, n5)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, batch)
                        importati += c.rowcount
                        batch.clear()
                except (ValueError, IndexError):
                    continue

        if batch:
            c.executemany("""
                INSERT OR IGNORE INTO lotto
                (data, ruota, n1, n2, n3, n4, n5)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, batch)
            importati += c.rowcount

        conn.commit()
        totale = c.execute("SELECT COUNT(*) FROM lotto").fetchone()[0]

    print(f"Lotto: {importati} importate, {totale} totali nel DB.")


def importa_diecelotto():
    """Importa 10elotto.txt in formato xamig: Concorso\tData\tN.1..N.20\tOro\tOro2\tExtra..."""
    filepath = os.path.join(DATA_DIR, "10elotto.txt")
    if not os.path.exists(filepath):
        print("data/10elotto.txt non trovato, skip.")
        return

    from datetime import datetime

    with get_db_ctx() as conn:
        c = conn.cursor()
        batch = []
        importati = 0
        col_numeri = ", ".join([f"n{i}" for i in range(1, 21)])

        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t")
                if not parts[0].strip().isdigit():
                    continue
                try:
                    # parts[0]=concorso, parts[1]=data, parts[2..21]=20 numeri
                    data_raw = parts[1].strip()
                    data = datetime.strptime(data_raw, "%d/%m/%Y").strftime("%Y-%m-%d")

                    numeri = []
                    for i in range(2, min(22, len(parts))):
                        v = parts[i].strip()
                        if v and v != "-" and v.isdigit():
                            numeri.append(int(v))
                    if len(numeri) != 20:
                        continue

                    # Numero Oro (parts[22]) e Doppio Oro (parts[23])
                    numero_oro = 0
                    doppio_oro = 0
                    if len(parts) > 22:
                        v = parts[22].strip()
                        if v and v != "-" and v.isdigit():
                            numero_oro = int(v)
                    if len(parts) > 23:
                        v = parts[23].strip()
                        if v and v != "-" and v.isdigit():
                            doppio_oro = int(v)

                    batch.append((data, *numeri, numero_oro, doppio_oro))
                    if len(batch) >= BATCH_SIZE:
                        c.executemany(f"""
                            INSERT OR IGNORE INTO diecelotto
                            (data, {col_numeri}, numero_oro, doppio_oro)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, batch)
                        importati += c.rowcount
                        batch.clear()
                except (ValueError, IndexError):
                    continue

        if batch:
            c.executemany(f"""
                INSERT OR IGNORE INTO diecelotto
                (data, {col_numeri}, numero_oro, doppio_oro)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, batch)
            importati += c.rowcount

        conn.commit()
        totale = c.execute("SELECT COUNT(*) FROM diecelotto").fetchone()[0]

    print(f"10eLotto: {importati} importate, {totale} totali nel DB.")


def importa_eurojackpot():
    filepath = os.path.join(DATA_DIR, "eurojackpot.txt")
    if not os.path.exists(filepath):
        print("data/eurojackpot.txt non trovato, skip.")
        return

    with get_db_ctx() as conn:
        c = conn.cursor()
        batch = []
        importati = 0

        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t")
                if not parts[0].strip().isdigit():
                    continue
                try:
                    concorso = int(parts[0].strip())
                    data_raw = parts[1].strip()
                    from datetime import datetime
                    data = datetime.strptime(data_raw, "%d/%m/%Y").strftime("%Y-%m-%d")
                    numeri = [int(parts[2 + i].strip()) for i in range(5)]
                    e1 = int(parts[7].strip())
                    e2 = int(parts[8].strip())
                    batch.append((concorso, data, *numeri, e1, e2))
                    if len(batch) >= BATCH_SIZE:
                        c.executemany("""
                            INSERT OR IGNORE INTO eurojackpot
                            (concorso, data, n1, n2, n3, n4, n5, e1, e2)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, batch)
                        importati += c.rowcount
                        batch.clear()
                except (ValueError, IndexError):
                    continue

        if batch:
            c.executemany("""
                INSERT OR IGNORE INTO eurojackpot
                (concorso, data, n1, n2, n3, n4, n5, e1, e2)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, batch)
            importati += c.rowcount

        conn.commit()
        totale = c.execute("SELECT COUNT(*) FROM eurojackpot").fetchone()[0]

    print(f"Eurojackpot: {importati} importate, {totale} totali nel DB.")


def importa_vincicasa():
    filepath = os.path.join(DATA_DIR, "vincicasa.txt")
    if not os.path.exists(filepath):
        print("data/vincicasa.txt non trovato, skip.")
        return

    with get_db_ctx() as conn:
        c = conn.cursor()
        batch = []
        importati = 0

        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t")
                if not parts[0].strip().isdigit():
                    continue
                try:
                    concorso = int(parts[0].strip())
                    data_raw = parts[1].strip()
                    from datetime import datetime
                    data = datetime.strptime(data_raw, "%d/%m/%Y").strftime("%Y-%m-%d")
                    numeri = [int(parts[2 + i].strip()) for i in range(5)]
                    batch.append((concorso, data, *numeri))
                    if len(batch) >= BATCH_SIZE:
                        c.executemany("""
                            INSERT OR IGNORE INTO vincicasa
                            (concorso, data, n1, n2, n3, n4, n5)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, batch)
                        importati += c.rowcount
                        batch.clear()
                except (ValueError, IndexError):
                    continue

        if batch:
            c.executemany("""
                INSERT OR IGNORE INTO vincicasa
                (concorso, data, n1, n2, n3, n4, n5)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, batch)
            importati += c.rowcount

        conn.commit()
        totale = c.execute("SELECT COUNT(*) FROM vincicasa").fetchone()[0]

    print(f"VinciCasa: {importati} importate, {totale} totali nel DB.")


def importa_sivincetutto():
    filepath = os.path.join(DATA_DIR, "sivincetutto.txt")
    if not os.path.exists(filepath):
        print("data/sivincetutto.txt non trovato, skip.")
        return

    with get_db_ctx() as conn:
        c = conn.cursor()
        batch = []
        importati = 0

        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t")
                if not parts[0].strip().isdigit():
                    continue
                try:
                    concorso = int(parts[0].strip())
                    data_raw = parts[1].strip()
                    from datetime import datetime
                    data = datetime.strptime(data_raw, "%d/%m/%Y").strftime("%Y-%m-%d")
                    numeri = [int(parts[2 + i].strip()) for i in range(6)]
                    batch.append((concorso, data, *numeri))
                    if len(batch) >= BATCH_SIZE:
                        c.executemany("""
                            INSERT OR IGNORE INTO sivincetutto
                            (concorso, data, n1, n2, n3, n4, n5, n6)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, batch)
                        importati += c.rowcount
                        batch.clear()
                except (ValueError, IndexError):
                    continue

        if batch:
            c.executemany("""
                INSERT OR IGNORE INTO sivincetutto
                (concorso, data, n1, n2, n3, n4, n5, n6)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, batch)
            importati += c.rowcount

        conn.commit()
        totale = c.execute("SELECT COUNT(*) FROM sivincetutto").fetchone()[0]

    print(f"SiVinceTutto: {importati} importate, {totale} totali nel DB.")


def importa_winforlife():
    filepath = os.path.join(DATA_DIR, "winforlife.txt")
    if not os.path.exists(filepath):
        print("data/winforlife.txt non trovato, skip.")
        return

    with get_db_ctx() as conn:
        c = conn.cursor()
        batch = []
        importati = 0

        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t")
                if not parts[0].strip().isdigit():
                    continue
                try:
                    concorso = int(parts[0].strip())
                    data_raw = parts[1].strip()
                    from datetime import datetime
                    data = datetime.strptime(data_raw, "%d/%m/%Y").strftime("%Y-%m-%d")
                    ora = parts[2].strip() if len(parts) > 2 else ""
                    numeri = [int(parts[3 + i].strip()) for i in range(10)]
                    numerone = int(parts[13].strip()) if len(parts) > 13 else 0
                    # Dati xamig = Grattacieli (17 estrazioni/giorno)
                    batch.append(("grattacieli", concorso, data, ora, *numeri, numerone))
                    if len(batch) >= BATCH_SIZE:
                        c.executemany("""
                            INSERT OR IGNORE INTO winforlife
                            (tipo, concorso, data, ora, n1, n2, n3, n4, n5, n6, n7, n8, n9, n10, numerone)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, batch)
                        importati += c.rowcount
                        batch.clear()
                except (ValueError, IndexError):
                    continue

        if batch:
            c.executemany("""
                INSERT OR IGNORE INTO winforlife
                (tipo, concorso, data, ora, n1, n2, n3, n4, n5, n6, n7, n8, n9, n10, numerone)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, batch)
            importati += c.rowcount

        conn.commit()
        totale = c.execute("SELECT COUNT(*) FROM winforlife").fetchone()[0]

    print(f"WinForLife: {importati} importate, {totale} totali nel DB.")


def importa_winforlife_classico():
    filepath = os.path.join(DATA_DIR, "winforlife_classico.txt")
    if not os.path.exists(filepath):
        print("data/winforlife_classico.txt non trovato, skip.")
        return

    with get_db_ctx() as conn:
        c = conn.cursor()
        batch = []
        importati = 0

        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t")
                if not parts[0].strip().isdigit():
                    continue
                try:
                    concorso = int(parts[0].strip())
                    data_raw = parts[1].strip()
                    from datetime import datetime
                    data = datetime.strptime(data_raw, "%d/%m/%Y").strftime("%Y-%m-%d")
                    ora = parts[2].strip() if len(parts) > 2 else ""
                    numeri = [int(parts[3 + i].strip()) for i in range(10)]
                    numerone = int(parts[13].strip()) if len(parts) > 13 else 0
                    batch.append(("classico", concorso, data, ora, *numeri, numerone))
                    if len(batch) >= BATCH_SIZE:
                        c.executemany("""
                            INSERT OR IGNORE INTO winforlife
                            (tipo, concorso, data, ora, n1, n2, n3, n4, n5, n6, n7, n8, n9, n10, numerone)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, batch)
                        importati += c.rowcount
                        batch.clear()
                except (ValueError, IndexError):
                    continue

        if batch:
            c.executemany("""
                INSERT OR IGNORE INTO winforlife
                (tipo, concorso, data, ora, n1, n2, n3, n4, n5, n6, n7, n8, n9, n10, numerone)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, batch)
            importati += c.rowcount

        conn.commit()
        totale_c = c.execute("SELECT COUNT(*) FROM winforlife WHERE tipo='classico'").fetchone()[0]

    print(f"WinForLife Classico: {importati} importate, {totale_c} totali nel DB.")


def importa_simbolotto():
    filepath = os.path.join(DATA_DIR, "simbolotto.txt")
    if not os.path.exists(filepath):
        print("data/simbolotto.txt non trovato, skip.")
        return

    from datetime import datetime

    with get_db_ctx() as conn:
        c = conn.cursor()
        batch = []
        importati = 0

        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("\t")
                if not parts[0].strip().isdigit():
                    continue
                try:
                    concorso = int(parts[0].strip())
                    data_raw = parts[1].strip()
                    data = datetime.strptime(data_raw, "%d/%m/%Y").strftime("%Y-%m-%d")
                    ruota = parts[2].strip() if len(parts) > 2 else ""
                    numeri = [int(parts[3 + i].strip()) for i in range(5)]
                    batch.append((concorso, data, ruota, *numeri))
                    if len(batch) >= BATCH_SIZE:
                        c.executemany("""
                            INSERT OR IGNORE INTO simbolotto
                            (concorso, data, ruota, n1, n2, n3, n4, n5)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, batch)
                        importati += c.rowcount
                        batch.clear()
                except (ValueError, IndexError):
                    continue

        if batch:
            c.executemany("""
                INSERT OR IGNORE INTO simbolotto
                (concorso, data, ruota, n1, n2, n3, n4, n5)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, batch)
            importati += c.rowcount

        conn.commit()
        totale = c.execute("SELECT COUNT(*) FROM simbolotto").fetchone()[0]

    print(f"Simbolotto: {importati} importate, {totale} totali nel DB.")


def importa_tutto():
    init_db()
    print("\n=== IMPORT ARCHIVI ===\n")
    importa_millionday()
    importa_superenalotto()
    importa_lotto()
    importa_diecelotto()
    importa_eurojackpot()
    importa_vincicasa()
    importa_sivincetutto()
    importa_winforlife()
    importa_winforlife_classico()
    importa_simbolotto()
    print("\n=== COMPLETATO ===")


if __name__ == "__main__":
    importa_tutto()