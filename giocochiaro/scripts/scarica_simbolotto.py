"""
Scarica l'archivio storico completo del Simbolotto da estrazionisimbolotto.it.
Salva il file simbolotto.txt nella cartella data/.

Il Simbolotto è attivo dal 18 luglio 2019.
"""

import os
import sys
import time
import cloudscraper
from bs4 import BeautifulSoup

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
FILEPATH = os.path.join(DATA_DIR, "simbolotto.txt")

URL = "https://www.estrazionisimbolotto.it/simbolotto/archivio/statistiche-simbolotto-{anno}.htm"
PRIMO_ANNO = 2019
ANNO_CORRENTE = 2026


def scarica():
    scraper = cloudscraper.create_scraper()
    righe_totali = 0

    print(f"Scaricamento archivio Simbolotto ({PRIMO_ANNO}-{ANNO_CORRENTE})")
    print(f"Fonte: estrazionisimbolotto.it")
    print(f"Output: {FILEPATH}")

    with open(FILEPATH, "w", encoding="utf-8") as out:
        out.write("Concorso\tData\tRuota\tN1\tN2\tN3\tN4\tN5\n")

        # Ordine cronologico: dal primo anno all'ultimo
        tutti = []

        for anno in range(PRIMO_ANNO, ANNO_CORRENTE + 1):
            url = URL.format(anno=anno)
            try:
                r = scraper.get(url, timeout=15)
                if r.status_code != 200:
                    print(f"  {anno}: HTTP {r.status_code}, skip")
                    continue

                soup = BeautifulSoup(r.text, "html.parser")
                table = soup.find("table")
                if not table:
                    print(f"  {anno}: nessuna tabella trovata, skip")
                    continue

                rows = table.find_all("tr")[1:]  # skip header

                anno_righe = []
                for row in rows:
                    cells = [c.get_text(strip=True) for c in row.find_all("td")]
                    if len(cells) < 8:
                        continue

                    # cells: data, concorso, ruota, pari, dispari, n1, n2, n3, n4, n5
                    data_raw = cells[0]  # DD.MM.YY
                    concorso = cells[1]
                    ruota = cells[2]
                    numeri = cells[5:10]

                    # Converti data DD.MM.YY -> DD/MM/YYYY (usa anno dal loop, il sito ha typo)
                    parts = data_raw.split(".")
                    if len(parts) == 3:
                        data_fmt = f"{parts[0]}/{parts[1]}/{anno}"
                    else:
                        data_fmt = data_raw

                    anno_righe.append((concorso, data_fmt, ruota, *numeri))

                # Le righe sono in ordine decrescente (più recente prima), invertiamo
                anno_righe.reverse()
                tutti.extend(anno_righe)

                print(f"  {anno}: {len(anno_righe)} estrazioni")

            except Exception as e:
                print(f"  {anno}: ERRORE - {e}")

            time.sleep(0.3)

        # Scrivi tutte le righe in ordine cronologico
        for riga in tutti:
            out.write("\t".join(riga) + "\n")
            righe_totali += 1

    scraper.close()

    print(f"\n{'='*50}")
    print(f"  COMPLETATO: {righe_totali} estrazioni -> {FILEPATH}")
    print(f"{'='*50}")


if __name__ == "__main__":
    scarica()
