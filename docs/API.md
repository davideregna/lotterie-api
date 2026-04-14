# GiocoChiaro API - Documentazione

> API REST per estrazioni, archivi e statistiche di **Lotto**, **10eLotto**, **SuperEnalotto** e **SiVinceTutto**.

**Base URL:** `http://localhost:8000`

---

## Lotto

Il Lotto italiano ha **11 ruote**: Bari, Cagliari, Firenze, Genova, Milano, Napoli, Palermo, Roma, Torino, Venezia, Nazionale. Ogni ruota estrae 5 numeri (da 1 a 90). Estrazioni: martedi, giovedi e sabato.

---

### `GET /api/lotto/ultima`

Ultima estrazione con tutte le ruote.

**Risposta:**

```json
{
  "lotteria": "lotto",
  "data": "2026-03-21",
  "ruote": [
    {
      "ruota": "BA",
      "nome": "Bari",
      "numeri": [12, 34, 56, 78, 90],
      "numero_oro": 12
    },
    {
      "ruota": "CA",
      "nome": "Cagliari",
      "numeri": [3, 19, 44, 67, 81],
      "numero_oro": 3
    },
    ...
    {
      "ruota": "RN",
      "nome": "Nazionale",
      "numeri": [7, 25, 38, 52, 88],
      "numero_oro": 7
    }
  ],
  "simbolotti": {
    "ruota": "Firenze",
    "numeri": [2, 18, 27, 35, 41]
  },
  "aggiornato_il": "2026-03-21 20:15"
}
```

| Campo | Tipo | Descrizione |
|-------|------|-------------|
| `ruote` | array | 11 oggetti, uno per ogni ruota |
| `ruote[].ruota` | string | Codice ruota (BA, CA, FI, GE, MI, NA, PA, RM, TO, VE, RN) |
| `ruote[].nome` | string | Nome esteso della ruota |
| `ruote[].numeri` | array[int] | 5 numeri estratti (1-90) |
| `ruote[].numero_oro` | int | Numero Oro della ruota |
| `simbolotti` | object | Simbolotto associato (opzionale) |
| `aggiornato_il` | string | Timestamp ultimo aggiornamento effettivo |

---

### `GET /api/lotto/ultime`

Ultime N estrazioni, raggruppate per data, con tutte le ruote.

**Parametri query:**

| Parametro | Tipo | Default | Max | Descrizione |
|-----------|------|---------|-----|-------------|
| `n` | int | 10 | 100 | Numero di estrazioni |

**Esempio:** `GET /api/lotto/ultime?n=5`

**Risposta:**

```json
{
  "lotteria": "lotto",
  "estrazioni": [
    {
      "data": "2026-03-21",
      "ruote": [
        {"ruota": "BA", "numeri": [12, 34, 56, 78, 90]},
        {"ruota": "CA", "numeri": [3, 19, 44, 67, 81]},
        ...
      ]
    },
    {
      "data": "2026-03-19",
      "ruote": [...]
    }
  ]
}
```

---

### `GET /api/lotto/archivio`

Archivio storico delle estrazioni. Supporta filtro per singola ruota.

**Parametri query:**

| Parametro | Tipo | Default | Max | Descrizione |
|-----------|------|---------|-----|-------------|
| `ruota` | string | - | - | Filtra per ruota (es. `bari`, `milano`, `nazionale`) |
| `limit` | int | 100 | 10000 | Numero massimo di risultati |
| `offset` | int | 0 | - | Offset per paginazione |

**Esempi:**

```
GET /api/lotto/archivio                          # tutte le ruote, ultime 100
GET /api/lotto/archivio?ruota=bari&limit=50      # solo Bari, ultime 50
GET /api/lotto/archivio?limit=200&offset=100     # paginazione
```

**Risposta:**

```json
{
  "lotteria": "lotto",
  "totale": 15234,
  "limit": 100,
  "offset": 0,
  "estrazioni": [
    {
      "id": 1,
      "data": "2026-03-21",
      "ruota": "Bari",
      "n1": 12, "n2": 34, "n3": 56, "n4": 78, "n5": 90
    },
    ...
  ]
}
```

---

### `GET /api/lotto/statistiche`

Statistiche complete: ritardatari, frequenti e dati per ogni numero (1-90).

**Parametri query:**

| Parametro | Tipo | Default | Descrizione |
|-----------|------|---------|-------------|
| `ruota` | string | - | Statistiche per singola ruota (es. `bari`, `roma`) |

Ruote valide: `bari`, `cagliari`, `firenze`, `genova`, `milano`, `napoli`, `palermo`, `roma`, `torino`, `venezia`, `nazionale`.

**Esempi:**

```
GET /api/lotto/statistiche               # statistiche globali (tutte le ruote)
GET /api/lotto/statistiche?ruota=roma     # solo ruota Roma
GET /api/lotto/statistiche?ruota=nazionale
```

**Risposta:**

```json
{
  "lotteria": "lotto",
  "aggiornato_il": "2026-03-21 20:15",
  "top_ritardatari": [
    {
      "lotteria": "lotto",
      "numero": 42,
      "frequenza": 1203,
      "ritardo_attuale": 87,
      "ritardo_max": 142,
      "ultima_data": "2025-12-20",
      "aggiornato_il": "2026-03-21 20:15"
    },
    ...
  ],
  "top_frequenti": [
    {
      "lotteria": "lotto",
      "numero": 77,
      "frequenza": 1589,
      "ritardo_attuale": 3,
      "ritardo_max": 98,
      "ultima_data": "2026-03-19",
      "aggiornato_il": "2026-03-21 20:15"
    },
    ...
  ],
  "tutti": [
    { "numero": 1, "frequenza": 1456, "ritardo_attuale": 12, "ritardo_max": 105, "ultima_data": "2026-03-10" },
    { "numero": 2, "frequenza": 1423, "ritardo_attuale": 5, "ritardo_max": 112, "ultima_data": "2026-03-19" },
    ...
    { "numero": 90, "frequenza": 1401, "ritardo_attuale": 8, "ritardo_max": 99, "ultima_data": "2026-03-15" }
  ]
}
```

| Campo | Descrizione |
|-------|-------------|
| `top_ritardatari` | Top 10 numeri con il ritardo attuale piu alto |
| `top_frequenti` | Top 10 numeri piu frequenti nell'archivio |
| `tutti` | Array completo dei 90 numeri con tutte le statistiche |
| `frequenza` | Quante volte il numero e stato estratto in totale |
| `ritardo_attuale` | Da quante estrazioni il numero non esce |
| `ritardo_max` | Il ritardo storico piu lungo mai registrato |
| `ultima_data` | Data dell'ultima estrazione in cui e uscito |

---

## 10eLotto

Il 10eLotto estrae **20 numeri** (da 1 a 90) derivati dalle ruote del Lotto, piu Numero Oro, Doppio Oro e 15 numeri Extra. Estrazioni: insieme al Lotto (mar, gio, sab).

---

### `GET /api/10elotto/ultima`

Ultima estrazione del 10eLotto.

**Risposta:**

```json
{
  "lotteria": "10elotto",
  "data": "2026-03-21",
  "numeri": [3, 7, 12, 15, 19, 22, 25, 34, 38, 41, 44, 52, 56, 60, 67, 72, 78, 81, 88, 90],
  "numero_oro": 12,
  "doppio_oro": 34,
  "extra": [1, 5, 9, 14, 18, 27, 30, 35, 47, 53, 63, 69, 74, 82, 86],
  "aggiornato_il": "2026-03-21 20:15"
}
```

| Campo | Tipo | Descrizione |
|-------|------|-------------|
| `numeri` | array[int] | 20 numeri vincenti (1-90) |
| `numero_oro` | int | Numero Oro |
| `doppio_oro` | int | Doppio Oro |
| `extra` | array[int] | 15 numeri Extra |

---

### `GET /api/10elotto/archivio`

Archivio storico del 10eLotto.

**Parametri query:**

| Parametro | Tipo | Default | Max | Descrizione |
|-----------|------|---------|-----|-------------|
| `limit` | int | 100 | 10000 | Numero massimo di risultati |
| `offset` | int | 0 | - | Offset per paginazione |

**Esempio:** `GET /api/10elotto/archivio?limit=50&offset=200`

**Risposta:**

```json
{
  "lotteria": "10elotto",
  "totale": 5230,
  "limit": 100,
  "offset": 0,
  "estrazioni": [
    {
      "id": 1,
      "data": "2026-03-21",
      "n1": 3, "n2": 7, "n3": 12, "n4": 15, "n5": 19,
      "n6": 22, "n7": 25, "n8": 34, "n9": 38, "n10": 41,
      "n11": 44, "n12": 52, "n13": 56, "n14": 60, "n15": 67,
      "n16": 72, "n17": 78, "n18": 81, "n19": 88, "n20": 90,
      "numero_oro": 12,
      "doppio_oro": 34
    },
    ...
  ]
}
```

---

### `GET /api/10elotto/statistiche`

Statistiche: ritardatari, frequenti e dati completi per ogni numero (1-90).

**Risposta:** stessa struttura delle statistiche Lotto (vedi sopra).

```json
{
  "lotteria": "10elotto",
  "aggiornato_il": "2026-03-21 20:15",
  "top_ritardatari": [...],
  "top_frequenti": [...],
  "tutti": [
    { "numero": 1, "frequenza": 1205, "ritardo_attuale": 4, "ritardo_max": 32, "ultima_data": "..." },
    ...
  ]
}
```

---

### `GET /api/10elotto5min/ultime`

**10eLotto ogni 5 minuti** - estrazioni live (non collegate al Lotto classico).

> Questo endpoint scrapa in tempo reale da 10elotto5.it. Ha un **cache di 60 secondi**.

**Risposta:**

```json
{
  "lotteria": "10elotto5min",
  "estrazioni": [
    {
      "concorso": 12345,
      "data": "2026-03-24",
      "ora": "14:35",
      "numeri": [2, 5, 11, 18, 22, 27, 33, 39, 41, 48, 52, 55, 61, 67, 71, 74, 79, 83, 86, 90],
      "numero_oro": 18,
      "doppio_oro": 41,
      "extra": [1, 7, 14, 20, 25, 30, 36, 44, 50, 57, 63, 68, 73, 80, 88]
    },
    ...
  ],
  "totale": 288,
  "aggiornato_il": "2026-03-24 14:35"
}
```

| Campo | Tipo | Descrizione |
|-------|------|-------------|
| `estrazioni` | array | Estrazioni della giornata (fino a 288 al giorno) |
| `estrazioni[].concorso` | int | Numero progressivo del concorso |
| `estrazioni[].ora` | string | Orario dell'estrazione (HH:MM) |
| `estrazioni[].numeri` | array[int] | 20 numeri estratti |
| `estrazioni[].numero_oro` | int | Numero Oro |
| `estrazioni[].doppio_oro` | int | Doppio Oro |
| `estrazioni[].extra` | array[int] | 15 numeri Extra |
| `aggiornato_il` | string | Si aggiorna solo quando i dati cambiano |

---

## SuperEnalotto

Il SuperEnalotto estrae **6 numeri** (da 1 a 90), piu **Jolly** e **SuperStar**. Estrazioni: martedi, giovedi e sabato.

---

### `GET /api/superenalotto/ultima`

Ultima estrazione con jackpot, montepremi e vincite.

**Risposta:**

```json
{
  "lotteria": "superenalotto",
  "concorso": "45",
  "anno": "2026",
  "data": "2026-03-21",
  "numeri": [5, 18, 27, 42, 63, 81],
  "jolly": 34,
  "superstar": 72,
  "jackpot_centesimi": 5432100000,
  "jackpot_euro": "54321000.00",
  "montepremi": {
    "totale_centesimi": 9876500000,
    "totale_euro": "98765000.00",
    "concorso_centesimi": 3210000000,
    "concorso_euro": "32100000.00"
  },
  "vincite": [
    {
      "categoria": "6",
      "tipo": "SEI",
      "importo_centesimi": 0,
      "importo_euro": "0.00",
      "numero_vincite": 0
    },
    {
      "categoria": "5+1",
      "tipo": "CINQUE_JOLLY",
      "importo_centesimi": 123456789,
      "importo_euro": "1234567.89",
      "numero_vincite": 1,
      "numero_vincite_italia": 1
    },
    {
      "categoria": "5",
      "tipo": "CINQUE",
      "importo_centesimi": 5000000,
      "importo_euro": "50000.00",
      "numero_vincite": 3
    },
    ...
  ],
  "totale_vincite": 245678,
  "importo_totale_vincite_centesimi": 987654321,
  "importo_totale_vincite_euro": "9876543.21",
  "aggiornato_il": "2026-03-21 20:30"
}
```

| Campo | Tipo | Descrizione |
|-------|------|-------------|
| `numeri` | array[int] | 6 numeri estratti (1-90) |
| `jolly` | int | Numero Jolly |
| `superstar` | int | Numero SuperStar |
| `jackpot_centesimi` | int | Jackpot in centesimi |
| `jackpot_euro` | string | Jackpot formattato in euro |
| `montepremi` | object | Montepremi totale e del concorso |
| `vincite` | array | Dettaglio vincite per categoria |
| `vincite[].numero_vincite` | int | Quante vincite per questa categoria |
| `vincite[].numero_vincite_italia` | int | Vincite in Italia (se disponibile) |

**Categorie vincite disponibili:**

| Categoria | Tipo | Descrizione |
|-----------|------|-------------|
| Punti 6 | 14 | Sei numeri |
| Punti 5+1 | 13 | Cinque + Jolly |
| Punti 5 | 12 | Cinque numeri |
| Punti 4 | 11 | Quattro numeri |
| Punti 3 | 10 | Tre numeri |
| Punti 2 | 9 | Due numeri |
| 5 Stella | 25 | Cinque + SuperStar |
| 4 Stella | 24 | Quattro + SuperStar |
| 3 Stella | 23 | Tre + SuperStar |
| 2 Stella | 22 | Due + SuperStar |
| 1 Stella | 21 | Uno + SuperStar |
| 0 Stella | 20 | Zero + SuperStar |

---

### `GET /api/superenalotto/ultime`

Ultime N estrazioni con jackpot, montepremi e vincite (se disponibili).

**Parametri query:**

| Parametro | Tipo | Default | Max | Descrizione |
|-----------|------|---------|-----|-------------|
| `n` | int | 10 | 100 | Numero di estrazioni |

**Esempio:** `GET /api/superenalotto/ultime?n=20`

**Risposta:**

```json
{
  "lotteria": "superenalotto",
  "estrazioni": [
    {
      "concorso": 45,
      "data": "2026-03-21",
      "numeri": [5, 18, 27, 42, 63, 81],
      "jolly": 34,
      "superstar": 72,
      "jackpot_centesimi": 5432100000,
      "jackpot_euro": "54321000.00",
      "montepremi": { ... },
      "vincite": [ ... ],
      "totale_vincite": 245678,
      "importo_totale_vincite_centesimi": 987654321,
      "importo_totale_vincite_euro": "9876543.21"
    },
    ...
  ]
}
```

> **Nota:** i campi `jackpot_centesimi`, `montepremi`, `vincite` sono presenti solo per le estrazioni salvate dopo l'aggiornamento del 25/03/2026. Le estrazioni storiche precedenti restituiscono solo concorso, data, numeri, jolly e superstar.

---

### `GET /api/superenalotto/archivio`

Archivio storico. Supporta filtro per anno.

**Parametri query:**

| Parametro | Tipo | Default | Max | Descrizione |
|-----------|------|---------|-----|-------------|
| `anno` | int | - | - | Filtra per anno (es. `2025`, `2026`) |
| `limit` | int | 100 | 10000 | Numero massimo di risultati |
| `offset` | int | 0 | - | Offset per paginazione |

**Esempi:**

```
GET /api/superenalotto/archivio                    # ultime 100 estrazioni
GET /api/superenalotto/archivio?anno=2025          # solo anno 2025
GET /api/superenalotto/archivio?limit=500&offset=0 # prime 500
```

**Risposta:**

Stessa struttura di `/ultime` ma con paginazione. Ogni estrazione include jackpot/montepremi/vincite se disponibili.

```json
{
  "lotteria": "superenalotto",
  "totale": 4166,
  "limit": 100,
  "offset": 0,
  "estrazioni": [
    {
      "concorso": 45,
      "data": "2026-03-21",
      "numeri": [5, 18, 27, 42, 63, 81],
      "jolly": 34,
      "superstar": 72,
      "jackpot_centesimi": 5432100000,
      "jackpot_euro": "54321000.00",
      "montepremi": { ... },
      "vincite": [ ... ]
    },
    ...
  ]
}
```

---

### `GET /api/superenalotto/statistiche`

Statistiche: ritardatari, frequenti e dati completi per ogni numero (1-90).

**Risposta:**

```json
{
  "lotteria": "superenalotto",
  "aggiornato_il": "2026-03-21 20:30",
  "top_ritardatari": [
    {
      "numero": 42,
      "frequenza": 987,
      "ritardo_attuale": 65,
      "ritardo_max": 120,
      "ultima_data": "2025-12-13"
    },
    ...
  ],
  "top_frequenti": [
    {
      "numero": 77,
      "frequenza": 1102,
      "ritardo_attuale": 2,
      "ritardo_max": 88,
      "ultima_data": "2026-03-19"
    },
    ...
  ],
  "tutti": [
    { "numero": 1, "frequenza": 1005, "ritardo_attuale": 10, "ritardo_max": 95, "ultima_data": "..." },
    ...
    { "numero": 90, "frequenza": 998, "ritardo_attuale": 7, "ritardo_max": 102, "ultima_data": "..." }
  ]
}
```

---

## SiVinceTutto

Il SiVinceTutto estrae **6 numeri** (da 1 a 90). Il montepremi viene distribuito interamente ad ogni concorso. Estrazione: mercoledi.

---

### `GET /api/sivincetutto/ultima`

Ultima estrazione con montepremi e vincite.

**Risposta:**

```json
{
  "lotteria": "sivincetutto",
  "concorso": "12",
  "anno": "2026",
  "data": "2026-03-19",
  "numeri": [8, 23, 35, 49, 67, 82],
  "montepremi_centesimi": 456789000,
  "montepremi_euro": "4567890.00",
  "vincite": [
    {
      "categoria": "6",
      "tipo": "SEI",
      "importo_centesimi": 0,
      "importo_euro": "0.00",
      "numero_vincite": 0
    },
    {
      "categoria": "5",
      "tipo": "CINQUE",
      "importo_centesimi": 234500,
      "importo_euro": "2345.00",
      "numero_vincite": 5
    },
    {
      "categoria": "4",
      "tipo": "QUATTRO",
      "importo_centesimi": 8900,
      "importo_euro": "89.00",
      "numero_vincite": 142
    },
    {
      "categoria": "3",
      "tipo": "TRE",
      "importo_centesimi": 1200,
      "importo_euro": "12.00",
      "numero_vincite": 2890
    },
    {
      "categoria": "2",
      "tipo": "DUE",
      "importo_centesimi": 300,
      "importo_euro": "3.00",
      "numero_vincite": 18500
    }
  ],
  "totale_vincite": 21537,
  "aggiornato_il": "2026-03-19 20:30"
}
```

| Campo | Tipo | Descrizione |
|-------|------|-------------|
| `numeri` | array[int] | 6 numeri estratti (1-90) |
| `concorso` | string | Numero del concorso |
| `anno` | string | Anno del concorso |
| `montepremi_centesimi` | int | Montepremi totale in centesimi |
| `montepremi_euro` | string | Montepremi formattato in euro |
| `vincite` | array | Dettaglio vincite per categoria (6, 5, 4, 3, 2) |
| `vincite[].categoria` | string | Descrizione categoria |
| `vincite[].tipo` | string | Codice tipo (SEI, CINQUE, QUATTRO, TRE, DUE) |
| `vincite[].importo_centesimi` | int | Importo della singola vincita in centesimi |
| `vincite[].importo_euro` | string | Importo formattato in euro |
| `vincite[].numero_vincite` | int | Quante vincite per questa categoria |
| `totale_vincite` | int | Numero totale di vincite nel concorso |

---

### `GET /api/sivincetutto/ultime`

Ultime N estrazioni.

**Parametri query:**

| Parametro | Tipo | Default | Max | Descrizione |
|-----------|------|---------|-----|-------------|
| `n` | int | 10 | 100 | Numero di estrazioni |

**Esempio:** `GET /api/sivincetutto/ultime?n=20`

**Risposta:**

```json
{
  "lotteria": "sivincetutto",
  "estrazioni": [
    {
      "concorso": "12",
      "data": "2026-03-19",
      "numeri": [8, 23, 35, 49, 67, 82]
    },
    {
      "concorso": "11",
      "data": "2026-03-12",
      "numeri": [4, 17, 28, 55, 71, 89]
    },
    ...
  ]
}
```

---

### `GET /api/sivincetutto/archivio`

Archivio storico. Supporta filtro per anno.

**Parametri query:**

| Parametro | Tipo | Default | Max | Descrizione |
|-----------|------|---------|-----|-------------|
| `anno` | int | - | - | Filtra per anno (es. `2025`, `2026`) |
| `limit` | int | 100 | 10000 | Numero massimo di risultati |
| `offset` | int | 0 | - | Offset per paginazione |

**Esempi:**

```
GET /api/sivincetutto/archivio                    # ultime 100 estrazioni
GET /api/sivincetutto/archivio?anno=2025          # solo anno 2025
GET /api/sivincetutto/archivio?limit=200&offset=0 # prime 200
```

**Risposta:**

```json
{
  "lotteria": "sivincetutto",
  "totale": 520,
  "limit": 100,
  "offset": 0,
  "estrazioni": [
    {
      "id": 1,
      "concorso": "12",
      "data": "2026-03-19",
      "n1": 8, "n2": 23, "n3": 35, "n4": 49, "n5": 67, "n6": 82
    },
    ...
  ]
}
```

---

### `GET /api/sivincetutto/statistiche`

Statistiche: ritardatari, frequenti e dati completi per ogni numero (1-90).

**Risposta:**

```json
{
  "lotteria": "sivincetutto",
  "aggiornato_il": "2026-03-19 20:30",
  "top_ritardatari": [
    {
      "numero": 15,
      "frequenza": 54,
      "ritardo_attuale": 38,
      "ritardo_max": 45,
      "ultima_data": "2025-07-02"
    },
    ...
  ],
  "top_frequenti": [
    {
      "numero": 82,
      "frequenza": 78,
      "ritardo_attuale": 0,
      "ritardo_max": 30,
      "ultima_data": "2026-03-19"
    },
    ...
  ],
  "tutti": [
    { "numero": 1, "frequenza": 62, "ritardo_attuale": 5, "ritardo_max": 40, "ultima_data": "..." },
    ...
    { "numero": 90, "frequenza": 59, "ritardo_attuale": 11, "ritardo_max": 42, "ultima_data": "..." }
  ]
}
```

---

## Endpoint globali

### `GET /api/tutte/ultime`

Ultima estrazione di **tutti** i giochi in un'unica chiamata.

**Risposta:**

```json
{
  "lotto": { ... },
  "diecelotto": { ... },
  "superenalotto": { ... },
  "sivincetutto": { ... },
  "millionday": { ... },
  "vincicasa": { ... },
  "eurojackpot": { ... },
  "winforlife_classico": { ... },
  "winforlife_grattacieli": { ... },
  "simbolotto": { ... }
}
```

---

### `GET /api/tutte/statistiche`

Statistiche (ritardatari e frequenti) di tutti i giochi.

**Parametri query:**

| Parametro | Tipo | Default | Max | Descrizione |
|-----------|------|---------|-----|-------------|
| `limit` | int | 10 | 90 | Quanti numeri restituire nelle top list |
| `gioco` | string | - | - | Filtra per singolo gioco |

**Esempi:**

```
GET /api/tutte/statistiche                      # tutti i giochi, top 10
GET /api/tutte/statistiche?limit=20             # top 20 per gioco
GET /api/tutte/statistiche?gioco=superenalotto  # solo SuperEnalotto
GET /api/tutte/statistiche?gioco=sivincetutto   # solo SiVinceTutto
```

**Risposta:**

```json
{
  "lotto": {
    "lotteria": "lotto",
    "aggiornato_il": "...",
    "top_ritardatari": [...],
    "top_frequenti": [...]
  },
  "10elotto": { ... },
  "superenalotto": { ... },
  "sivincetutto": { ... },
  ...
}
```

> **Nota:** a differenza dell'endpoint per singolo gioco, qui non viene restituito l'array `tutti` con i 90 numeri, ma solo le top list.

---

### `GET /api/stato`

Stato del database con conteggio estrazioni per gioco.

**Risposta:**

```json
{
  "stato": "ok",
  "estrazioni": {
    "millionday": 2450,
    "superenalotto": 8420,
    "lotto": 15234,
    "diecelotto": 5230,
    "sivincetutto": 520,
    "vincicasa": 3100,
    "eurojackpot": 890,
    "winforlife": 4200,
    "simbolotto": 1800
  }
}
```

---

### `GET /api/ricalcola`

Ricalcola tutte le statistiche. **Solo da localhost.**

**Risposta:** `{"stato": "ok", "messaggio": "Statistiche ricalcolate"}`

---

## Glossario statistiche

| Termine | Significato |
|---------|-------------|
| **Frequenza** | Numero totale di volte in cui un numero e stato estratto nell'archivio |
| **Ritardo attuale** | Numero di estrazioni consecutive in cui il numero non e uscito (dal piu recente) |
| **Ritardo massimo** | Il ritardo storico piu lungo mai registrato per quel numero |
| **Top ritardatari** | I 10 numeri con il ritardo attuale piu elevato |
| **Top frequenti** | I 10 numeri estratti piu volte in assoluto |
| **Ultima data** | Data dell'ultima estrazione in cui il numero e apparso |

---

## Aggiornamento dati

I dati vengono aggiornati automaticamente da un **background scheduler** ogni **5 minuti**:

1. Lo scraper raccoglie le estrazioni da fonti ufficiali
2. I nuovi dati vengono salvati nel database e nei file archivio
3. Le statistiche (ritardatari, frequenti) vengono ricalcolate

Il campo `aggiornato_il` in ogni risposta indica l'ultimo aggiornamento **effettivo** dei dati (non l'ora della richiesta).

---

## Riepilogo endpoint

| Gioco | Endpoint | Descrizione |
|-------|----------|-------------|
| **Lotto** | `GET /api/lotto/ultima` | Ultima estrazione (tutte le ruote) |
| | `GET /api/lotto/ultime?n=10` | Ultime N estrazioni |
| | `GET /api/lotto/archivio?ruota=bari` | Archivio (filtro ruota opzionale) |
| | `GET /api/lotto/statistiche?ruota=roma` | Ritardatari e frequenti (filtro ruota opzionale) |
| **10eLotto** | `GET /api/10elotto/ultima` | Ultima estrazione (20 numeri + oro + extra) |
| | `GET /api/10elotto/archivio` | Archivio storico |
| | `GET /api/10elotto/statistiche` | Ritardatari e frequenti |
| **10eLotto 5min** | `GET /api/10elotto5min/ultime` | Estrazioni live ogni 5 minuti |
| **SuperEnalotto** | `GET /api/superenalotto/ultima` | Ultima estrazione (jackpot, vincite) |
| | `GET /api/superenalotto/ultime?n=10` | Ultime N estrazioni |
| | `GET /api/superenalotto/archivio?anno=2025` | Archivio (filtro anno opzionale) |
| | `GET /api/superenalotto/statistiche` | Ritardatari e frequenti |
| **SiVinceTutto** | `GET /api/sivincetutto/ultima` | Ultima estrazione (montepremi, vincite) |
| | `GET /api/sivincetutto/ultime?n=10` | Ultime N estrazioni |
| | `GET /api/sivincetutto/archivio?anno=2025` | Archivio (filtro anno opzionale) |
| | `GET /api/sivincetutto/statistiche` | Ritardatari e frequenti |
| **Globali** | `GET /api/tutte/ultime` | Tutte le ultime estrazioni |
| | `GET /api/tutte/statistiche?limit=20` | Tutte le statistiche |
| | `GET /api/stato` | Stato database |
| | `GET /api/ricalcola` | Ricalcola statistiche (solo localhost) |
