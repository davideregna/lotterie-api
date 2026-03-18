"""
Scraper per le ultime estrazioni di:
- SuperEnalotto, VinciCasa, Eurojackpot, SiVinceTutto (API gntn-pgd.it)
- Win for Life Classico, Win for Life Grattacieli (API gntn-pgd.it)
- Lotto, 10eLotto (API lotto-italia.it via cloudscraper)
- MillionDAY + MillionDAY Extra (API lotto-italia.it via cloudscraper)
"""

import asyncio
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from playwright.async_api import async_playwright, Page
import cloudscraper


@dataclass
class Estrazione:
    gioco: str
    concorso: str = ""
    data: str = ""
    numeri: list[int] = field(default_factory=list)
    jolly: int | None = None
    superstar: int | None = None
    euronumeri: list[int] = field(default_factory=list)
    numerone: int | None = None
    numero_oro: int | None = None
    extra: list[int] = field(default_factory=list)
    ruote: dict = field(default_factory=dict)
    raw_data: dict = field(default_factory=dict)  # JSON grezzo completo


# ── Configurazione giochi gntn ─────────────────────────────────────

GIOCHI_GNTN = [
    {
        "nome": "SuperEnalotto",
        "api_id": "superenalotto",
        "url": "https://www.superenalotto.it/ultima-estrazione",
        "has_jolly": True,
        "has_superstar": True,
    },
    {
        "nome": "VinciCasa",
        "api_id": "vincicasa",
        "url": "https://www.vincicasa.it/ultima-estrazione",
    },
    {
        "nome": "Eurojackpot",
        "api_id": "eurojackpot",
        "url": "https://www.eurojackpot.it/ultima-estrazione",
        "has_euronumeri": True,
    },
    {
        "nome": "SiVinceTutto",
        "api_id": "sivincetutto",
        "url": "https://www.sivincetutto.it/ultima-estrazione",
    },
    {
        "nome": "Win for Life Classico",
        "api_id": "winforlifeclassico",
        "has_numerone": True,
    },
    {
        "nome": "Win for Life Grattacieli",
        "api_id": "winforlifegrattacieli",
        "has_numerone": True,
    },
]

API_GNTN = "https://www.gntn-pgd.it/gntn-info-web/rest/gioco/{}/estrazioni/ultimoconcorso?idPartner=GIOCHINUMERICI_INFO"

API_LOTTO = "https://www.lotto-italia.it/gdl/estrazioni-e-vincite/estrazioni-del-lotto.json"
API_MILLIONDAY = "https://www.lotto-italia.it/md/estrazioni-e-vincite/ultime-estrazioni-millionDay.json"


# ── Helpers ────────────────────────────────────────────────────────

def ts_to_date(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%d/%m/%Y")


def ultima_data_lotto() -> str:
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    giorni_estrazione = [1, 3, 4, 5]
    for i in range(7):
        d = now - timedelta(days=i)
        if d.weekday() in giorni_estrazione:
            return d.strftime("%Y%m%d")
    return now.strftime("%Y%m%d")


def oggi() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


# ── Parser gntn ────────────────────────────────────────────────────

def parse_gntn_response(data: dict, gioco: dict) -> Estrazione:
    estrazione = Estrazione(gioco=gioco["nome"])
    estrazione.raw_data = data  # salva tutto il JSON grezzo

    concorso_info = data.get("concorso") or {}
    if isinstance(concorso_info, dict):
        estrazione.concorso = concorso_info.get("numero", "")
    if not estrazione.concorso:
        dc = data.get("dettaglioConcorso") or {}
        concorso_info = dc.get("concorso") or {}
        estrazione.concorso = concorso_info.get("numero", "")

    ts = data.get("dataEstrazione")
    if not ts:
        dc = data.get("dettaglioConcorso") or {}
        ts = dc.get("dataEstrazione")
    if ts:
        estrazione.data = ts_to_date(ts)

    comb = data.get("combinazioneVincente")
    if not comb:
        dc = data.get("dettaglioConcorso") or {}
        comb = dc.get("combinazioneVincente") or {}

    estrazione.numeri = [int(n) for n in (comb.get("estratti") or [])]

    if gioco.get("has_jolly"):
        j = comb.get("numeroJolly")
        if j:
            estrazione.jolly = int(j)
    if gioco.get("has_superstar"):
        s = comb.get("superstar")
        if s:
            estrazione.superstar = int(s)
    if gioco.get("has_euronumeri"):
        estrazione.euronumeri = [int(n) for n in (comb.get("euronumeri") or [])]
    if gioco.get("has_numerone"):
        n = comb.get("numerone")
        if n:
            estrazione.numerone = int(n)

    return estrazione


# ── Fetch gntn (via Playwright) ────────────────────────────────────

async def fetch_gntn(page: Page, gioco: dict, max_retries: int = 3) -> Estrazione | None:
    url = API_GNTN.format(gioco["api_id"])
    for attempt in range(max_retries):
        try:
            resp = await page.goto(url, timeout=10000)
            if resp.status != 200:
                return None
            text = await page.inner_text("body")
            data = json.loads(text)
            comb = data.get("combinazioneVincente") or (data.get("dettaglioConcorso") or {}).get("combinazioneVincente")
            if data.get("stato") == 2 or not (comb and comb.get("estratti")):
                if attempt < max_retries - 1:
                    print(f"  Dati non disponibili, riprovo tra 3s...")
                    await asyncio.sleep(3)
                    continue
                return None
            return parse_gntn_response(data, gioco)
        except Exception:
            return None
    return None


async def fetch_gntn_fallback(page: Page, gioco: dict) -> Estrazione | None:
    if "url" not in gioco:
        return None
    try:
        await page.goto(gioco["url"], wait_until="domcontentloaded", timeout=15000)
        await page.locator(
            "div.combination-container.combinations-JS .combination"
        ).first.wait_for(timeout=15000)

        estrazione = Estrazione(gioco=gioco["nome"])
        info = page.locator("div.competition-info-JS")
        if await info.count() > 0:
            p_tag = info.locator("p").first
            if await p_tag.count() > 0:
                estrazione.data = (await p_tag.inner_text()).strip()
            conc = await info.get_attribute("data-conc-number")
            if conc:
                estrazione.concorso = conc
            else:
                import re
                match = re.search(r"Nº(\d+)", estrazione.data)
                if match:
                    estrazione.concorso = match.group(1)

        balls = page.locator("div.combination-container.combinations-JS .combination")
        for i in range(await balls.count()):
            ball = balls.nth(i)
            text = (await ball.inner_text()).strip()
            if not text.isdigit():
                continue
            numero = int(text)
            classes = await ball.get_attribute("class") or ""
            if gioco.get("has_jolly") and "combination-jolly" in classes:
                estrazione.jolly = numero
            elif gioco.get("has_superstar") and "combination-superstar" in classes:
                estrazione.superstar = numero
            elif gioco.get("has_euronumeri") and "combination-euronumeri" in classes:
                estrazione.euronumeri.append(numero)
            else:
                estrazione.numeri.append(numero)
        return estrazione
    except Exception:
        return None


async def scarica_gntn(page: Page, gioco: dict) -> Estrazione | None:
    nome = gioco["nome"]
    print(f"Scarico {nome}...")
    estrazione = await fetch_gntn(page, gioco)
    if estrazione and estrazione.numeri:
        print(f"  OK (API) - {len(estrazione.numeri)} numeri trovati")
        return estrazione
    estrazione = await fetch_gntn_fallback(page, gioco)
    if estrazione and estrazione.numeri:
        print(f"  OK (scraping) - {len(estrazione.numeri)} numeri trovati")
        return estrazione
    print(f"  ERRORE: nessun dato trovato per {nome}", file=sys.stderr)
    return None


# ── Fetch lotto-italia.it (via cloudscraper) ───────────────────────

def fetch_lotto(scraper: cloudscraper.CloudScraper) -> list[Estrazione]:
    risultati = []
    data_str = ultima_data_lotto()
    print("Scarico Lotto + 10eLotto...")

    try:
        r = scraper.post(API_LOTTO, json={"data": data_str}, timeout=15)
        if r.status_code != 200:
            print(f"  ERRORE Lotto: HTTP {r.status_code}", file=sys.stderr)
            return risultati
        data = r.json()
        if data.get("esito") != "OK":
            print(f"  ERRORE Lotto: {data.get('messaggio')}", file=sys.stderr)
            return risultati
    except Exception as e:
        print(f"  ERRORE Lotto: {e}", file=sys.stderr)
        return risultati

    ts = data.get("data")
    data_fmt = ts_to_date(ts) if ts else ""

    # ── Lotto
    lotto = Estrazione(gioco="Lotto", data=data_fmt)
    lotto.raw_data = data  # JSON grezzo completo
    estrazioni_ruote = data.get("estrazione") or []
    for ruota in estrazioni_ruote:
        nome_ruota = ruota.get("ruotaExtended", ruota.get("ruota", ""))
        numeri_ruota = ruota.get("numeri", [])
        lotto.ruote[nome_ruota] = numeri_ruota
    for ruota in estrazioni_ruote:
        if ruota.get("ruota") == "RN":
            lotto.numeri = ruota.get("numeri", [])
    if not lotto.numeri and estrazioni_ruote:
        lotto.numeri = estrazioni_ruote[0].get("numeri", [])
    print(f"  OK Lotto - {len(estrazioni_ruote)} ruote")
    risultati.append(lotto)

    # ── Simbolotto
    simbolotti = data.get("simbolotti")
    if simbolotti:
        simb_numeri = simbolotti.get("simbolotti", [])
        if simb_numeri:
            simb = Estrazione(gioco="Simbolotto", data=data_fmt)
            simb.raw_data = simbolotti
            simb.numeri = [int(n) for n in simb_numeri]
            simb.ruote = {"ruota": simbolotti.get("ruota", "")}
            print(f"  OK Simbolotto - {len(simb.numeri)} numeri (ruota {simbolotti.get('ruota', '?')})")
            risultati.append(simb)

    # ── 10eLotto
    numeri_vincenti = data.get("numeriVincenti")
    if numeri_vincenti:
        diecelotto = Estrazione(gioco="10eLotto", data=data_fmt)
        diecelotto.raw_data = data  # stessa risposta, contiene anche 10eLotto
        diecelotto.numeri = numeri_vincenti
        ns = data.get("numeroSpeciale")
        if ns:
            diecelotto.numero_oro = ns
        extra_nums = data.get("numeriEstrattiOvertime")
        if extra_nums:
            diecelotto.extra = extra_nums
        print(f"  OK 10eLotto - {len(numeri_vincenti)} numeri + {len(extra_nums or [])} extra")
        risultati.append(diecelotto)

    return risultati


def fetch_millionday(scraper: cloudscraper.CloudScraper) -> list[Estrazione]:
    risultati = []
    print("Scarico MillionDAY...")

    try:
        r = scraper.post(
            API_MILLIONDAY,
            json={"data": oggi(), "numeroEstrazioni": "1"},
            timeout=15,
        )
        if r.status_code != 200:
            from datetime import timedelta
            ieri = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y%m%d")
            r = scraper.post(
                API_MILLIONDAY,
                json={"data": ieri, "numeroEstrazioni": "1"},
                timeout=15,
            )
        if r.status_code != 200:
            print(f"  ERRORE: HTTP {r.status_code}", file=sys.stderr)
            return risultati
        draws = r.json()
    except Exception as e:
        print(f"  ERRORE: {e}", file=sys.stderr)
        return risultati

    if not draws:
        print("  Nessuna estrazione trovata", file=sys.stderr)
        return risultati

    draw = draws[0]
    ts = draw.get("data")
    data_fmt = ts_to_date(ts) if ts else ""
    orario = draw.get("orarioEstrazione", "")

    md = Estrazione(gioco="MillionDAY", data=f"{data_fmt} {orario}".strip())
    md.raw_data = draw  # JSON grezzo del singolo draw
    md.numeri = [int(n) for n in (draw.get("numeriEstratti") or [])]
    md.extra = [int(n) for n in (draw.get("numeriEstrattiOvertime") or [])]

    print(f"  OK - {len(md.numeri)} numeri + {len(md.extra)} extra")
    risultati.append(md)

    return risultati


# ── Stampa ─────────────────────────────────────────────────────────

def stampa_risultati(estrazioni: list[Estrazione]):
    separatore = "=" * 50
    for e in estrazioni:
        print(f"\n{separatore}")
        print(f"  {e.gioco}")
        print(f"{separatore}")
        if e.concorso:
            print(f"  Concorso: {e.concorso}")
        if e.data:
            print(f"  Data: {e.data}")
        if e.ruote:
            for ruota, numeri in e.ruote.items():
                print(f"  {ruota}: {', '.join(str(n) for n in numeri)}")
        else:
            print(f"  Numeri: {', '.join(str(n) for n in e.numeri)}")
        if e.jolly is not None:
            print(f"  Jolly: {e.jolly}")
        if e.superstar is not None:
            print(f"  SuperStar: {e.superstar}")
        if e.euronumeri:
            print(f"  Euronumeri: {', '.join(str(n) for n in e.euronumeri)}")
        if e.numerone is not None:
            print(f"  Numerone: {e.numerone}")
        if e.numero_oro is not None:
            print(f"  Numero Oro: {e.numero_oro}")
        if e.extra:
            print(f"  Extra: {', '.join(str(n) for n in e.extra)}")
    print(f"\n{separatore}\n")


# ── Main ───────────────────────────────────────────────────────────

async def main():
    print("Avvio scraping estrazioni...\n")

    scraper = cloudscraper.create_scraper()

    try:
        loop = asyncio.get_event_loop()
        lotto_task = loop.run_in_executor(None, fetch_lotto, scraper)
        md_task = loop.run_in_executor(None, fetch_millionday, scraper)

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                channel="chrome",
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
            )

            pages = [await context.new_page() for _ in GIOCHI_GNTN]
            gntn_results = await asyncio.gather(
                *(scarica_gntn(page, gioco) for page, gioco in zip(pages, GIOCHI_GNTN))
            )
            await browser.close()

        lotto_results = await lotto_task
        md_results = await md_task
    finally:
        scraper.close()

    estrazioni = [r for r in gntn_results if r is not None]
    estrazioni.extend(lotto_results)
    estrazioni.extend(md_results)

    if estrazioni:
        stampa_risultati(estrazioni)

    return estrazioni


if __name__ == "__main__":
    asyncio.run(main())