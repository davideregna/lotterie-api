from datetime import datetime
from app.database import get_db_ctx
from app.config import TABELLE_VALIDE


def calcola_stats(lotteria, tabella, max_numero, colonne_numeri, where=""):
    if tabella not in TABELLE_VALIDE:
        raise ValueError(f"Tabella non valida: {tabella}")

    with get_db_ctx() as conn:
        c = conn.cursor()

        if lotteria == "millionday":
            order = "ORDER BY data ASC, ora ASC"
        elif tabella == "winforlife":
            order = "ORDER BY data ASC, ora ASC"
        else:
            order = "ORDER BY data ASC"

        sql = f"SELECT data, {colonne_numeri} FROM {tabella} {where} {order}"
        c.execute(sql)
        rows = c.fetchall()

        if not rows:
            print(f"Nessuna estrazione {lotteria}.")
            return

        totale = len(rows)

        frequenze = [0] * (max_numero + 1)
        ultima_uscita = [-1] * (max_numero + 1)
        ritardo_max = [0] * (max_numero + 1)

        for idx, row in enumerate(rows):
            numeri_estratti = set(row[1:])
            for n in range(1, max_numero + 1):
                if n in numeri_estratti:
                    ritardo = idx if ultima_uscita[n] == -1 else idx - ultima_uscita[n]
                    if ritardo > ritardo_max[n]:
                        ritardo_max[n] = ritardo
                    frequenze[n] += 1
                    ultima_uscita[n] = idx

        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        c.execute("DELETE FROM statistiche WHERE lotteria = ?", (lotteria,))

        batch = []
        for n in range(1, max_numero + 1):
            ritardo_attuale = totale if ultima_uscita[n] == -1 else (totale - 1) - ultima_uscita[n]
            if ritardo_attuale > ritardo_max[n]:
                ritardo_max[n] = ritardo_attuale

            ud = rows[ultima_uscita[n]][0] if ultima_uscita[n] != -1 else ""
            batch.append((lotteria, n, frequenze[n], ritardo_attuale, ritardo_max[n], ud, now))

        c.executemany("""
            INSERT INTO statistiche
            (lotteria, numero, frequenza, ritardo_attuale, ritardo_max, ultima_data, aggiornato_il)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, batch)

        conn.commit()

    print(f"Stats {lotteria}: {totale} estrazioni, {max_numero} numeri.")


def calcola_millionday():
    calcola_stats("millionday", "millionday", 55, "n1, n2, n3, n4, n5")


def calcola_superenalotto():
    calcola_stats("superenalotto", "superenalotto", 90, "n1, n2, n3, n4, n5, n6")


RUOTE_LOTTO = [
    "Bari", "Cagliari", "Firenze", "Genova", "Milano",
    "Napoli", "Palermo", "Roma", "Torino", "Venezia", "Nazionale",
]


def calcola_lotto():
    calcola_stats("lotto", "lotto", 90, "n1, n2, n3, n4, n5")


def calcola_lotto_ruote():
    for ruota in RUOTE_LOTTO:
        calcola_stats(
            f"lotto_{ruota.lower()}", "lotto", 90,
            "n1, n2, n3, n4, n5", f"WHERE ruota = '{ruota}'"
        )


def calcola_diecelotto():
    col = ", ".join([f"n{i}" for i in range(1, 21)])
    calcola_stats("10elotto", "diecelotto", 90, col)


def calcola_vincicasa():
    calcola_stats("vincicasa", "vincicasa", 40, "n1, n2, n3, n4, n5")


def calcola_eurojackpot():
    calcola_stats("eurojackpot", "eurojackpot", 50, "n1, n2, n3, n4, n5")


def calcola_sivincetutto():
    calcola_stats("sivincetutto", "sivincetutto", 90, "n1, n2, n3, n4, n5, n6")


def calcola_winforlife_classico():
    col = ", ".join([f"n{i}" for i in range(1, 11)])
    calcola_stats("winforlife_classico", "winforlife", 20, col, "WHERE tipo = 'classico'")


def calcola_winforlife_grattacieli():
    col = ", ".join([f"n{i}" for i in range(1, 11)])
    calcola_stats("winforlife_grattacieli", "winforlife", 20, col, "WHERE tipo = 'grattacieli'")


def calcola_simbolotto():
    calcola_stats("simbolotto", "simbolotto", 45, "n1, n2, n3, n4, n5")


def calcola_tutte():
    print("\n=== CALCOLO STATISTICHE ===\n")
    calcola_millionday()
    calcola_superenalotto()
    calcola_lotto()
    calcola_lotto_ruote()
    calcola_diecelotto()
    calcola_vincicasa()
    calcola_eurojackpot()
    calcola_sivincetutto()
    calcola_winforlife_classico()
    calcola_winforlife_grattacieli()
    calcola_simbolotto()
    print("\n=== FATTO ===")


if __name__ == "__main__":
    calcola_tutte()