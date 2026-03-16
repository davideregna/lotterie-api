import asyncio
import time
from datetime import datetime
from app.persist import salva_estrazione
from app.stats import calcola_tutte
from app.database import init_db

INTERVALLO = 300  # 5 minuti


async def aggiorna():
    from scraper.scraper import main as scrape_all

    ora = datetime.now().strftime("%H:%M:%S")
    print(f"\n[{ora}] === AGGIORNAMENTO ===")

    try:
        estrazioni = await scrape_all()
    except Exception as ex:
        print(f"  ERRORE scraping: {ex}")
        return

    nuove = 0
    for e in estrazioni:
        if salva_estrazione(e):
            print(f"    NUOVA: {e.gioco} {e.data}")
            nuove += 1

    if nuove > 0:
        print(f"  {nuove} estrazioni nuove salvate. Ricalcolo stats...")
        calcola_tutte()
    else:
        print(f"  Nessuna novità ({len(estrazioni)} estrazioni controllate).")


async def start_background():
    """Task asincrono per FastAPI."""
    print(f"=== SCHEDULER ATTIVO — ogni {INTERVALLO // 60} min ===\n")
    while True:
        await aggiorna()
        await asyncio.sleep(INTERVALLO)


if __name__ == "__main__":
    init_db()
    print(f"=== SCHEDULER ATTIVO — ogni {INTERVALLO // 60} min ===\n")
    while True:
        asyncio.run(aggiorna())
        time.sleep(INTERVALLO)