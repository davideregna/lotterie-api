#!/usr/bin/env python3
"""
Scrape le vincite di tutte le estrazioni VinciCasa da estrazionedellotto.it
e arricchisce vincicasa.txt con le colonne: V5, Q5, V4, Q4, V3, Q3, V2, Q2

Uso:
    python scrape_vincicasa_vincite.py            # scrape tutte
    python scrape_vincicasa_vincite.py --test 5   # solo le prime 5 (test)
"""

import os
import re
import sys
import time
import argparse
import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "data")
VINCICASA_TXT = os.path.join(DATA_DIR, "vincicasa.txt")
VINCICASA_OUT = os.path.join(DATA_DIR, "vincicasa_new.txt")

BASE_URL = "https://www.estrazionedellotto.it/vinci-casa/risultati/vinci-casa-estrazione-del-{}"
DELAY = 0.3

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; lotterie-api/1.0)",
    "Accept-Language": "it-IT,it;q=0.9",
})


def parse_euro_to_centesimi(s):
    """'500.000,00 €' → 50000000 centesimi"""
    s = re.sub(r'[€&euro;\s;]', '', s)
    s = s.replace('.', '').replace(',', '')
    try:
        return int(s)
    except ValueError:
        return 0


def parse_italian_int(s):
    """'1.790' → 1790"""
    return int(s.replace('.', '').strip())


def scrape_vincite(data_ddmmyyyy):
    """
    Scrape le vincite per una data. Ritorna (v5,q5,v4,q4,v3,q3,v2,q2) o None.
    V = numero vincite, Q = quota in centesimi.
    """
    day, month, year = data_ddmmyyyy.split('/')
    url = BASE_URL.format(f"{day}-{month}-{year}")

    try:
        resp = session.get(url, timeout=15)
        if resp.status_code != 200:
            return None

        html = resp.text
        result = {}

        for cat in [5, 4, 3, 2]:
            pattern = (
                rf'Punti\s+{cat}</span></td>\s*'
                r'<td>([\d.,]+)\s*(?:&euro;|€)</td>\s*'
                r'<td>([\d.]+)</td>'
            )
            m = re.search(pattern, html, re.DOTALL)
            if m:
                quota = parse_euro_to_centesimi(m.group(1))
                num_vincite = parse_italian_int(m.group(2))
                result[cat] = (num_vincite, quota)
            else:
                result[cat] = (0, 0)

        return (
            result[5][0], result[5][1],
            result[4][0], result[4][1],
            result[3][0], result[3][1],
            result[2][0], result[2][1],
        )
    except Exception as e:
        print(f"  Errore {data_ddmmyyyy}: {e}")
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", type=int, default=0, help="Scrape solo le prime N righe (test)")
    args = parser.parse_args()

    if not os.path.exists(VINCICASA_TXT):
        print(f"File non trovato: {VINCICASA_TXT}")
        sys.exit(1)

    with open(VINCICASA_TXT, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    header_lines = []
    draw_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped or not stripped[0].isdigit():
            header_lines.append(stripped)
        else:
            draw_lines.append(stripped)

    totale = len(draw_lines)
    if args.test:
        draw_lines = draw_lines[:args.test]

    print(f"Estrazioni nel file: {totale}")
    print(f"Da scrappare: {len(draw_lines)}")
    print()

    with open(VINCICASA_OUT, 'w', encoding='utf-8') as out:
        out.write("Archivio estrazioni VinciCasa\n")
        out.write("Concorso\tData\tN.1\tN.2\tN.3\tN.4\tN.5\tV5\tQ5\tV4\tQ4\tV3\tQ3\tV2\tQ2\n")

        scraped = 0
        errori = 0
        vuote = "\t\t\t\t\t\t\t\t"

        for i, line in enumerate(draw_lines):
            parts = line.split('\t')
            if len(parts) < 7:
                out.write(line + vuote + "\n")
                errori += 1
                continue

            data = parts[1].strip()
            vincite = scrape_vincite(data)

            if vincite:
                cols = "\t".join(str(v) for v in vincite)
                out.write(f"{line}\t{cols}\n")
                scraped += 1
            else:
                out.write(line + vuote + "\n")
                errori += 1

            if (i + 1) % 50 == 0 or (i + 1) == len(draw_lines):
                elapsed = (i + 1) * DELAY
                remaining = (len(draw_lines) - i - 1) * DELAY
                print(f"  [{i+1}/{len(draw_lines)}] {scraped} ok, {errori} errori "
                      f"(~{remaining/60:.0f} min rimanenti)")

            time.sleep(DELAY)

        # Se era un test, appendi le righe restanti non processate
        if args.test and args.test < totale:
            remaining_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped and stripped[0].isdigit():
                    remaining_lines.append(stripped)
            for line in remaining_lines[args.test:]:
                out.write(line + vuote + "\n")

    print(f"\nCompletato: {scraped} scrappate, {errori} errori su {len(draw_lines)}")
    print(f"Output scritto in: {VINCICASA_OUT}")
    print(f"Verifica il file e poi: mv vincicasa_new.txt vincicasa.txt")


if __name__ == '__main__':
    main()
