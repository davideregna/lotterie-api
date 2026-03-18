"""
Scarica gli archivi storici completi da xamig.com per tutti i giochi.
Salva i file .txt nella cartella data/.

Giochi scaricati:
- Lotto (dal 1874)
- 10eLotto (dal 2009)
- Eurojackpot (dal 2012)
- VinciCasa (dal 2014)
- SiVinceTutto (dal 2011)
- Win for Life (dal 2013)
"""

import os
import sys
import time
import cloudscraper

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

GIOCHI = {
    "lotto": {
        "url": "https://www.xamig.com/lotto/download-archivio.php",
        "primo_anno": 1874,
        "file": "lotto.txt",
    },
    "10elotto": {
        "url": "https://www.xamig.com/10elotto/download-archivio.php",
        "primo_anno": 2009,
        "file": "10elotto.txt",
    },
    "eurojackpot": {
        "url": "https://www.xamig.com/eurojackpot/download-archivio.php",
        "primo_anno": 2012,
        "file": "eurojackpot.txt",
    },
    "vincicasa": {
        "url": "https://www.xamig.com/vincicasa/download-archivio.php",
        "primo_anno": 2014,
        "file": "vincicasa.txt",
    },
    "sivincetutto": {
        "url": "https://www.xamig.com/sivincetutto/download-archivio.php",
        "primo_anno": 2011,
        "file": "sivincetutto.txt",
    },
    "winforlife": {
        "url": "https://www.xamig.com/win-for-life/download-archivio.php",
        "primo_anno": 2013,
        "file": "winforlife.txt",
    },
}

ANNO_CORRENTE = 2026


def scarica_gioco(scraper, nome, config):
    url = config["url"]
    primo = config["primo_anno"]
    filepath = os.path.join(DATA_DIR, config["file"])

    print(f"\n{'='*50}")
    print(f"  {nome.upper()}")
    print(f"{'='*50}")

    header_salvato = False
    righe_totali = 0

    with open(filepath, "w", encoding="utf-8") as out:
        for anno in range(primo, ANNO_CORRENTE + 1):
            try:
                r = scraper.post(
                    url,
                    data={"anno": str(anno), "format": "txt", "Esporta": "Esporta"},
                    timeout=20,
                )
                if r.status_code != 200:
                    print(f"  {anno}: HTTP {r.status_code}, skip")
                    continue

                lines = r.text.split("\n")
                data_lines = []

                for line in lines:
                    stripped = line.strip()
                    if not stripped:
                        continue

                    # Prima riga = nome gioco, seconda = info archivio, terza = header colonne
                    if stripped.startswith("Archivio estrazioni"):
                        # Header anno - scriviamo come separatore
                        out.write(f"{stripped}\n")
                        continue
                    elif stripped.startswith("Concorso\t"):
                        # Header colonne - salva solo la prima volta
                        if not header_salvato:
                            out.write(f"{stripped}\n")
                            header_salvato = True
                        continue
                    elif stripped == nome.capitalize() or stripped in (
                        "Lotto", "10eLotto", "EuroJackpot", "VinciCasa",
                        "SiVinceTutto SuperEnalotto", "Win for Life",
                    ):
                        continue
                    elif stripped.startswith("./"):
                        # Errore/file non trovato
                        continue

                    # Riga dati
                    # Verifica che inizi con un numero (concorso)
                    first_field = stripped.split("\t")[0].strip()
                    if first_field.isdigit():
                        data_lines.append(stripped)

                for dl in data_lines:
                    out.write(f"{dl}\n")

                righe_totali += len(data_lines)
                if data_lines:
                    print(f"  {anno}: {len(data_lines)} estrazioni")
                else:
                    print(f"  {anno}: nessun dato")

            except Exception as e:
                print(f"  {anno}: ERRORE - {e}")

            # Rate limiting gentile
            time.sleep(0.3)

    print(f"  TOTALE: {righe_totali} estrazioni -> {filepath}")
    return righe_totali


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    scraper = cloudscraper.create_scraper()

    # Se specificato un gioco come argomento, scarica solo quello
    filtro = sys.argv[1] if len(sys.argv) > 1 else None

    print("Scaricamento archivi storici da xamig.com")
    print(f"Directory output: {DATA_DIR}")

    totale_globale = 0
    try:
        for nome, config in GIOCHI.items():
            if filtro and filtro != nome:
                continue
            tot = scarica_gioco(scraper, nome, config)
            totale_globale += tot
    finally:
        scraper.close()

    print(f"\n{'='*50}")
    print(f"  COMPLETATO: {totale_globale} estrazioni totali scaricate")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
