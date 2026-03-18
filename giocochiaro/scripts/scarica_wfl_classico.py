"""
Scarica l'archivio storico di Win for Life Classico da winforlife.it.
Usa Playwright per renderizzare le pagine (JS-rendered).
Scarica giorno per giorno con pagine parallele per velocità.
"""

import asyncio
import os
import re
import sys
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
OUTPUT = os.path.join(DATA_DIR, "winforlife_classico.txt")
BASE_URL = "https://www.winforlife.it/archivio-estrazioni-classico"

MESI = {1:'gennaio',2:'febbraio',3:'marzo',4:'aprile',5:'maggio',6:'giugno',
        7:'luglio',8:'agosto',9:'settembre',10:'ottobre',11:'novembre',12:'dicembre'}

CONCURRENCY = 4  # pagine parallele


async def scrape_day(page, date):
    """Scarica tutte le estrazioni di un giorno. Ritorna lista di tuple."""
    url = f"{BASE_URL}/{date.year}/{MESI[date.month]}/{date.day}"
    results = []
    try:
        resp = await page.goto(url, timeout=15000, wait_until='domcontentloaded')
        if resp.status != 200:
            return results
        await page.wait_for_timeout(1500)

        trs = await page.query_selector_all('table tr')
        for tr in trs:
            text = (await tr.inner_text()).strip()
            match = re.match(
                r'N[ºo°]\s*(\d+)\s+del\s+(\d+\s+\w+\s+\d{4})\s+(\d{2}:\d{2})',
                text
            )
            if match:
                concorso = match.group(1)
                ora = match.group(3)
                # Extract numbers
                nums = re.findall(r'\b(\d{1,2})\b', text)
                # Filter: skip concorso, day, year, hour parts - get the 10 game numbers + numerone
                # The numbers appear after the time. Get all digit sequences
                after_time = text.split(ora, 1)[-1] if ora in text else ""
                game_nums = re.findall(r'\b(\d{1,2})\b', after_time)
                # Filter to valid numbers (1-20)
                valid = [n for n in game_nums if 1 <= int(n) <= 20]
                if len(valid) >= 11:  # 10 numeri + 1 numerone
                    numeri = valid[:10]
                    numerone = valid[10]
                    data_fmt = date.strftime("%d/%m/%Y")
                    results.append((concorso, data_fmt, ora, numeri, numerone))
    except Exception:
        pass
    return results


async def worker(sem, page, date, all_results, progress):
    """Worker con semaforo per limitare concorrenza."""
    async with sem:
        results = await scrape_day(page, date)
        all_results.extend(results)
        progress['done'] += 1
        if progress['done'] % 50 == 0:
            print(f"  Progresso: {progress['done']}/{progress['total']} giorni ({len(all_results)} estrazioni)")


async def main():
    # Determine date range
    # WfL Classico started Sep 2009, but let's check from 2013 (when xamig Grattacieli data starts)
    start_year = int(sys.argv[1]) if len(sys.argv) > 1 else 2013
    start_date = datetime(start_year, 1, 1)
    end_date = datetime.now()

    total_days = (end_date - start_date).days + 1
    print(f"Scaricamento Win for Life Classico")
    print(f"  Periodo: {start_date.strftime('%d/%m/%Y')} -> {end_date.strftime('%d/%m/%Y')}")
    print(f"  Giorni da scaricare: {total_days}")
    print(f"  Concorrenza: {CONCURRENCY} pagine")

    all_results = []
    progress = {'done': 0, 'total': total_days}

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True, channel='chrome',
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )

        pages = []
        for _ in range(CONCURRENCY):
            ctx = await browser.new_context(
                user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
            )
            pg = await ctx.new_page()
            pages.append(pg)

        sem = asyncio.Semaphore(CONCURRENCY)

        # Process in batches
        dates = [start_date + timedelta(days=i) for i in range(total_days)]
        batch_size = CONCURRENCY * 5

        for i in range(0, len(dates), batch_size):
            batch = dates[i:i + batch_size]
            tasks = []
            for j, date in enumerate(batch):
                pg = pages[j % CONCURRENCY]
                tasks.append(worker(sem, pg, date, all_results, progress))
            await asyncio.gather(*tasks)

        await browser.close()

    # Sort by date ASC, then concorso ASC
    all_results.sort(key=lambda x: (
        datetime.strptime(x[1], "%d/%m/%Y"),
        int(x[0])
    ))

    # Write file
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write("Concorso\tData\tOra\tN.1\tN.2\tN.3\tN.4\tN.5\tN.6\tN.7\tN.8\tN.9\tN.10\tNumerone\n")
        current_year = None
        for concorso, data, ora, numeri, numerone in all_results:
            year = int(data.split('/')[2])
            if year != current_year:
                f.write(f"Archivio estrazioni Win for Life Classico anno {year}\n")
                current_year = year
            nums_str = "\t".join(numeri)
            f.write(f"{concorso}\t{data}\t{ora}\t{nums_str}\t{numerone}\n")

    print(f"\nCompletato: {len(all_results)} estrazioni -> {OUTPUT}")
    print(f"File size: {os.path.getsize(OUTPUT):,} bytes")


if __name__ == "__main__":
    asyncio.run(main())
