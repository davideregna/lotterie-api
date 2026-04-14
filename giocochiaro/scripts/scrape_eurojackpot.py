#!/usr/bin/env python3
"""
Scraper per arricchire l'archivio EuroJackpot con dati sui premi/vincite.
Fonte: estrazionedellotto.it

Fasi:
  1) Raccoglie tutti gli URL estrazioni dalle pagine archivio annuali
  2) Per ogni URL, estrae numeri + tabella premi
  3) Genera il file eurojackpot.txt arricchito

Salva il progresso in un JSON per poter riprendere in caso di interruzione.
"""

import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.estrazionedellotto.it"
ARCHIVE_TPL = BASE_URL + "/eurojackpot/risultati/archivio-euro-jackpot-{year}"

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PROGRESS_FILE = DATA_DIR / "eurojackpot_scrape_progress.json"
OUTPUT_FILE = DATA_DIR / "eurojackpot.txt"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# Le 12 categorie premio nell'ordine standard del sito
PRIZE_CATEGORIES = [
    "5+2", "5+1", "5+0", "4+2", "4+1", "4+0",
    "3+2", "2+2", "3+1", "3+0", "1+2", "2+1",
]

# Mappa testo sito → codice categoria
PRIZE_MAP = {
    "5 Numeri e 2 Euronumeri": "5+2",
    "5 Numeri e 1 Euronumero": "5+1",
    "5 Numeri": "5+0",
    "4 Numeri e 2 Euronumeri": "4+2",
    "4 Numeri e 1 Euronumero": "4+1",
    "4 Numeri": "4+0",
    "3 Numeri e 2 Euronumeri": "3+2",
    "2 Numeri e 2 Euronumeri": "2+2",
    "3 Numeri e 1 Euronumero": "3+1",
    "3 Numeri": "3+0",
    "1 Numero e 2 Euronumeri": "1+2",
    "2 Numeri e 1 Euronumero": "2+1",
}

MESI_IT = {
    "gennaio": "01", "febbraio": "02", "marzo": "03", "aprile": "04",
    "maggio": "05", "giugno": "06", "luglio": "07", "agosto": "08",
    "settembre": "09", "ottobre": "10", "novembre": "11", "dicembre": "12",
}


# ── Utilità ───────────────────────────────────────────────────

def fetch(url: str, retries: int = 3, backoff: float = 2.0) -> str | None:
    for attempt in range(retries):
        try:
            r = SESSION.get(url, timeout=20)
            r.raise_for_status()
            return r.text
        except Exception as e:
            if attempt < retries - 1:
                wait = backoff * (attempt + 1)
                print(f"    retry {attempt+1} tra {wait}s – {e}")
                time.sleep(wait)
            else:
                print(f"    ERRORE DEFINITIVO: {url} – {e}")
                return None


def parse_euro_amount(text: str) -> float:
    """'10.132.504,60 €' → 10132504.60"""
    cleaned = text.replace("€", "").replace("\xa0", "").strip()
    cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def parse_int_it(text: str) -> int:
    """'1.234' → 1234"""
    cleaned = text.replace(".", "").replace(",", "").strip()
    try:
        return int(cleaned)
    except ValueError:
        return 0


def date_sort_key(data_str: str) -> str:
    """'28/12/2020' → '2020-12-28'"""
    parts = data_str.split("/")
    if len(parts) == 3:
        return f"{parts[2]}-{parts[1]}-{parts[0]}"
    return data_str


# ── Fase 1: Raccolta URL ─────────────────────────────────────

def get_extraction_urls(year: int) -> list[str]:
    """Estrae tutti gli URL di estrazioni singole dalla pagina archivio annuale."""
    url = ARCHIVE_TPL.format(year=year)
    html = fetch(url)
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    urls = []
    pattern = re.compile(r"/eurojackpot/risultati/euro-jackpot-estrazione-del-\d{2}-\d{2}-\d{4}")

    for a in soup.find_all("a", href=pattern):
        href = a["href"]
        if not href.startswith("http"):
            href = BASE_URL + href
        urls.append(href)

    # Deduplica preservando ordine
    seen = set()
    unique = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            unique.append(u)
    return unique


# ── Fase 2: Parsing estrazione singola ────────────────────────

def parse_extraction(url: str) -> dict | None:
    """Scarica e parsa una pagina estrazione singola."""
    html = fetch(url)
    if not html:
        return None

    soup = BeautifulSoup(html, "lxml")
    result = {}

    # ── Data da URL ──
    m = re.search(r"estrazione-del-(\d{2})-(\d{2})-(\d{4})", url)
    if m:
        day, month, year = m.groups()
        result["data"] = f"{day}/{month}/{year}"
    else:
        return None

    # ── Concorso ──
    text = soup.get_text(" ", strip=True)
    concorso = 0
    for pat in [
        r"La\s+(\d+)\s*[°ªa]\s*estrazione",      # "La 52 a estrazione"
        r"Estrazione\s+n\.?\s*(\d+)",              # "Estrazione n. 52"
        r"estrazione\s+numero\s*(\d+)",            # "estrazione numero 52"
    ]:
        m = re.search(pat, text, re.I)
        if m:
            concorso = int(m.group(1))
            break
    result["concorso"] = concorso

    # ── Numeri estratti ──
    numeri, euronumeri = _extract_numbers(soup)
    if not numeri or len(numeri) < 5:
        print(f"    WARN: numeri non trovati per {url}")
        return None
    result["numeri"] = numeri[:5]
    result["euronumeri"] = euronumeri[:2] if len(euronumeri) >= 2 else [0, 0]

    # ── Tabella premi ──
    result["vincite"] = _extract_prizes(soup)

    return result


def _extract_numbers(soup: BeautifulSoup) -> tuple[list[int], list[int]]:
    """Estrae i 5 numeri e i 2 euronumeri dalla pagina."""
    numeri = []
    euronumeri = []

    # Strategia 1: BallsAscending div
    balls_div = soup.find(id="BallsAscending")
    if balls_div:
        balls = balls_div.find_all(class_=re.compile(r"ball"))
        if len(balls) >= 7:
            nums = [int(b.get_text(strip=True)) for b in balls if b.get_text(strip=True).isdigit()]
            if len(nums) >= 7:
                return nums[:5], nums[5:7]

    # Strategia 2: cercare .ball ovunque nella pagina
    all_balls = soup.find_all(class_=re.compile(r"ball"))
    if len(all_balls) >= 7:
        nums = []
        for b in all_balls:
            t = b.get_text(strip=True)
            if t.isdigit():
                nums.append(int(t))
            if len(nums) >= 7:
                break
        if len(nums) >= 7:
            return nums[:5], nums[5:7]

    # Strategia 3: cercare nella lista puntata (come nella pagina archivio)
    for ul in soup.find_all("ul"):
        items = ul.find_all("li")
        if len(items) >= 7:
            nums = []
            for li in items:
                t = li.get_text(strip=True)
                if t.isdigit():
                    nums.append(int(t))
            if len(nums) >= 7:
                return nums[:5], nums[5:7]

    # Strategia 4: regex nel testo
    text = soup.get_text()
    m = re.search(r"(?:Numeri\s+vincenti|Numeri\s+estratti)[:\s]*(\d+)\s*[,\-\s]+(\d+)\s*[,\-\s]+(\d+)\s*[,\-\s]+(\d+)\s*[,\-\s]+(\d+)", text, re.I)
    if m:
        numeri = [int(m.group(i)) for i in range(1, 6)]
    m2 = re.search(r"(?:Euro\s*numer[io]|Stelle)[:\s]*(\d+)\s*[,\-\s]+(\d+)", text, re.I)
    if m2:
        euronumeri = [int(m2.group(1)), int(m2.group(2))]

    return numeri, euronumeri


def _extract_prizes(soup: BeautifulSoup) -> dict:
    """Estrae la tabella premi dalla pagina."""
    prizes = {}

    # Cerca la tabella basicTable
    table = soup.find("table", class_="basicTable")
    if not table:
        # Fallback: qualsiasi tabella con "Premio" nell'header
        for t in soup.find_all("table"):
            if t.find(string=re.compile(r"Premio", re.I)):
                table = t
                break
    if not table:
        return prizes

    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 4:
            continue

        premio_text = cells[0].get_text(strip=True)
        cat = PRIZE_MAP.get(premio_text)
        if not cat:
            continue

        quota = parse_euro_amount(cells[1].get_text(strip=True))
        vi = parse_int_it(cells[2].get_text(strip=True))
        vt = parse_int_it(cells[3].get_text(strip=True))

        prizes[cat] = {"quota": quota, "vi": vi, "vt": vt}

    return prizes


# ── Fase 3: Generazione file .txt ─────────────────────────────

def build_txt(extractions: list[dict]) -> str:
    """Costruisce il contenuto del file .txt arricchito."""
    # Ordina per data
    extractions.sort(key=lambda e: date_sort_key(e["data"]))

    # Raggruppa per anno
    years: dict[str, list[dict]] = {}
    for e in extractions:
        year = e["data"].split("/")[2]
        years.setdefault(year, []).append(e)

    # Header colonne premi
    prize_cols = []
    for cat in PRIZE_CATEGORIES:
        prize_cols.extend([f"Q{cat}", f"VI{cat}", f"VT{cat}"])

    header = "\t".join([
        "Concorso", "Data", "N.1", "N.2", "N.3", "N.4", "N.5", "EN.1", "EN.2"
    ] + prize_cols)

    lines = []
    for year in sorted(years.keys()):
        year_data = years[year]
        # Ordine decrescente per data (più recente prima)
        year_data.sort(key=lambda e: date_sort_key(e["data"]), reverse=True)

        last_date = year_data[0]["data"]
        lines.append(f"Archivio estrazioni EuroJackpot anno {year} aggiornato al {last_date}")
        lines.append(header)

        for e in year_data:
            nums = "\t".join(str(n) for n in e["numeri"])
            euros = "\t".join(str(n) for n in e["euronumeri"])

            prize_vals = []
            vincite = e.get("vincite", {})
            for cat in PRIZE_CATEGORIES:
                if cat in vincite:
                    v = vincite[cat]
                    prize_vals.append(f"{v['quota']:.2f}")
                    prize_vals.append(str(v["vi"]))
                    prize_vals.append(str(v["vt"]))
                else:
                    prize_vals.extend(["-", "-", "-"])

            line = "\t".join([
                str(e["concorso"]), e["data"], nums, euros
            ] + prize_vals)
            lines.append(line)

    return "\n".join(lines) + "\n"


# ── Progresso ─────────────────────────────────────────────────

def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"urls": [], "completed": {}, "failed": []}


def save_progress(prog: dict):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(prog, f, ensure_ascii=False)


# ── Main ──────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  SCRAPER EUROJACKPOT – estrazionedellotto.it")
    print("=" * 60)

    prog = load_progress()

    # ── Fase 1 ──
    if not prog["urls"]:
        print("\n📋 Fase 1: Raccolta URL da archivi annuali...")
        all_urls = []
        for year in range(2012, 2027):
            print(f"  {year}...", end=" ", flush=True)
            urls = get_extraction_urls(year)
            print(f"{len(urls)} estrazioni")
            all_urls.extend(urls)
            time.sleep(0.5)

        prog["urls"] = all_urls
        save_progress(prog)
        print(f"\n  Totale URL: {len(all_urls)}")
    else:
        print(f"\n📋 Fase 1: {len(prog['urls'])} URL già raccolti")

    # ── Fase 2 ──
    completed = prog.get("completed", {})
    failed = prog.get("failed", [])
    total = len(prog["urls"])
    remaining = [u for u in prog["urls"] if u not in completed and u not in failed]

    print(f"\n🔍 Fase 2: Scraping ({len(completed)} ok / {len(failed)} fail / {total} totali)")
    print(f"   Rimaste: {len(remaining)}")

    for i, url in enumerate(remaining):
        slug = url.split("/")[-1]
        idx = len(completed) + len(failed) + 1
        print(f"  [{idx}/{total}] {slug}...", end=" ", flush=True)

        data = parse_extraction(url)
        if data and data.get("numeri"):
            completed[url] = data
            n_prizes = len(data.get("vincite", {}))
            print(f"OK ({data['data']}, {n_prizes} premi)")
        else:
            failed.append(url)
            print("FAIL")

        # Salva ogni 20 estrazioni
        if (i + 1) % 20 == 0:
            prog["completed"] = completed
            prog["failed"] = failed
            save_progress(prog)

        time.sleep(0.35)

    prog["completed"] = completed
    prog["failed"] = failed
    save_progress(prog)

    print(f"\n  Completate: {len(completed)}")
    if failed:
        print(f"  Fallite: {len(failed)}")
        for f_url in failed[:10]:
            print(f"    - {f_url.split('/')[-1]}")

    # ── Fase 3 ──
    print(f"\n📝 Fase 3: Generazione {OUTPUT_FILE.name}...")
    extractions = list(completed.values())
    txt = build_txt(extractions)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(txt)

    n_lines = len(txt.splitlines())
    print(f"\n✅ Fatto! {len(extractions)} estrazioni → {n_lines} righe")
    print(f"   File: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
