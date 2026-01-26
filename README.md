Il progetto prevede la realizzazione di classi per degli studenti, da inserire in un calendario.
Il foglio excel nella directory contiene i dati e i vincoli.

## Cosmic School - Ottimizzatore Calendario Laboratori

Sistema di ottimizzazione per la distribuzione di laboratori scolastici tra classi e formatrici, utilizzando OR-Tools (Google) per risolvere problemi di scheduling con vincoli complessi.

### Setup

Il progetto usa Python 3.12 e `uv` per la gestione delle dipendenze.

```bash
# Il virtualenv e le dipendenze vengono gestite automaticamente
./optimize
```

### Struttura Progetto

```
cosmic-school/
├── criteri.xlsx   # Dati e vincoli (fonte)
├── convert_excel_to_csv.py          # Conversione Excel → CSV
├── create_test_subset.py            # Crea subset per test
├── data/
│   ├── input/                       # File CSV
│   │   ├── scuole.csv
│   │   ├── classi.csv
│   │   ├── formatrici.csv
│   │   ├── laboratori.csv
│   │   ├── fasce_orarie_scuole.csv
│   │   ├── laboratori_classi.csv
│   │   ├── formatrici_classi.csv
│   │   ├── date_escluse_classi.csv
│   │   ├── fasce_orarie_classi.csv
│   │   └── *_test.csv               # Versioni subset per test
│   └── output/                      # Risultati ottimizzazione
│       └── calendario_v3.xlsx
├── src/
│   ├── optimizer_v3.py              # Optimizer principale
│   └── export_formatter.py          # Formattazione output Excel
└── optimize                         # Script CLI (legacy)
```

### Flusso Dati

#### 1. Conversione Excel → CSV
```bash
python convert_excel_to_csv.py
```
- **Input:** `criteri.xlsx`
- **Output:** `data/input/*.csv` (9 file)

#### 2. Creazione subset test (opzionale)
```bash
python create_test_subset.py      # 1 scuola → *_test.csv
python create_test_subset.py 3    # 3 scuole → *_test3.csv
```

#### 3. Esecuzione optimizer
```bash
# Dati completi
python src/optimizer_v3.py

# Subset test (1 scuola)
python src/optimizer_v3.py _test

# Con parametri: suffix, num_workers, timeout
python src/optimizer_v3.py _test 16 180
```

### Formato Dati Input

**scuole.csv**
- `scuola_id`: ID univoco
- `nome`: Nome della scuola
- `citta`: Città

**classi.csv**
- `classe_id`: ID univoco
- `nome`: Nome classe (es: 4A)
- `scuola_id`: ID scuola di appartenenza
- `anno`: Anno scolastico (3, 4 o 5)
- `priorita`: alta/normale (classi quinte = alta)

**formatrici.csv**
- `formatrice_id`: ID univoco
- `nome`: Nome formatrice
- `ore_settimanali_max`: Media ore/settimana
- `lavora_sabato`: si/no
- `giorni_disponibili`: Elenco giorni (es: "lun,mar,mer,gio,ven")
- `preferenza_fasce`: mattina/pomeriggio/misto

**laboratori.csv**
- `laboratorio_id`: ID (4.0, 5.0, 7.0, 8.0, 9.0 per FOP)
- `nome`: Nome laboratorio
- `num_incontri`: Numero incontri richiesti
- `ore_per_incontro`: Durata singolo incontro
- `sequenza`: Ordine di esecuzione

**fasce_orarie_scuole.csv**
- `scuola_id`: ID scuola
- `fascia_id`: ID fascia oraria
- `nome`: Nome fascia (es: "14-16")
- `ora_inizio`: Ora inizio (es: "14:00")
- `ora_fine`: Ora fine (es: "16:00")
- `tipo_giornata`: mattina/pomeriggio

**laboratori_classi.csv**
- `classe_id`, `nome_classe`, `scuola_id`
- `laboratorio_id`: Quali lab fa ogni classe
- `dettagli`: Vincoli specifici (mattina/pomeriggio)
- `date_fissate`: Date già stabilite

**formatrici_classi.csv**
- `formatrice_id`, `nome_formatrice`
- `classe_id`, `nome_classe`
- Assegnazione preferenziale formatrice-classe

**date_escluse_classi.csv**
- `classe_id`, `nome_classe`
- `date_escluse`: Date in cui la classe non è disponibile

### Vincoli Implementati (V3)

**Hard Constraints (devono essere rispettati):**
1. Ogni classe completa tutti i laboratori assegnati
2. Massimo 1 incontro/settimana per classe
3. Lab 8.0 (Presentazione manuali) deve essere sempre l'ultimo
4. Lab 9.0 deve essere prima del Lab 5.0
5. Una formatrice non può essere in due posti contemporaneamente
6. Budget ore totali per formatrice (708 ore totali)
7. Date già fissate rispettate
8. Solo laboratori FOP (4, 5, 7, 8, 9) - GSSI/GST/LNGS ignorati

**Soft Constraints (da implementare):**
1. Accorpamenti: max 2 classi insieme (risparmio ore)
2. Continuità formatrice per classe
3. Priorità classi quinte (finire prima di maggio)

### Output

L'ottimizzatore genera un file Excel con **4 fogli** nel formato richiesto:

1. **complessivo**: Calendario completo con Data | Giorno | Settimana | Scuola | Classe | Orari | Attività | Formatrice | ecc.
2. **per_formatore_sett_data**: Vista per formatrice ordinata per data
3. **per_scuola_per_Classe**: Vista per scuola e classe
4. **per_scuola_per_data**: Vista per scuola ordinata per data

Vedere `FORMATO_OUTPUT.md` per dettagli completi sul formato.

### Esempio Uso

```bash
# 1. Converti Excel in CSV (dopo modifiche al foglio Excel)
python convert_excel_to_csv.py

# 2. Crea subset per test veloce
python create_test_subset.py

# 3. Esegui optimizer su subset
python src/optimizer_v3.py _test 16 180
# Output: data/output/calendario_v3_test.xlsx

# 4. Esegui optimizer su dati completi
python src/optimizer_v3.py "" 16 300
# Output: data/output/calendario_v3.xlsx
```

### Versioni Optimizer

**V1/V2 (legacy):** `./optimize`, `./optimize-v2`
- Versioni precedenti, più semplici

**V3 (attuale):** `python src/optimizer_v3.py`
- Vincoli completi da Excel
- Multi-core (16 worker)
- Date fissate, sequenzialità lab, budget ore

### Note

- Questo è un **esempio semplificato** (3 scuole, 12 classi, 3 formatrici, 4 laboratori)
- Per dati reali: modificare i CSV in `data/input/`
- Il solver ha un timeout di 120 secondi (configurabile in `optimizer.py`)
- Se non trova soluzioni, probabilmente i vincoli sono troppo stringenti o le risorse insufficienti

---

## STATO ATTUALE E PROSSIMI PASSI

### Situazione al 4 dicembre 2024

L'optimizer attuale è un **prototipo demo**. I requisiti reali (da `criteri per calendario.xlsx`) sono molto più complessi:

| Parametro | Demo attuale | Requisiti reali |
|-----------|--------------|-----------------|
| Gruppi classe | 12 | 69 |
| Scuole | 3 | 12 |
| Formatrici FOP | 3 | 6 |
| Partner | solo FOP | FOP + GSSI-GST-LNGS |

### Vincoli reali da implementare

1. **Laboratori FOP:**
   - Citizen Science: 5 incontri x 2h (3° incontro autonomo in 5 scuole specifiche)
   - Discriminazioni di genere: 2 incontri x 2h
   - Orientamento e competenze: 2 incontri x 2h
   - Presentazione manuali: 1 incontro x 2h (**deve essere l'ultimo**)

2. **Laboratori GSSI-GST-LNGS:**
   - Orientamento: 3 incontri x 2h (1 per classe)
   - Costruzione rivelatore: 2 mezze giornate **consecutive** x 4h + 1 online x 2h settimana dopo

3. **Fasce orarie:** 9-10, 11-13, 15-17 (una scuola ha 8-10, 10-12, 12-14)

4. **Giorni:** lun-ven (una scuola anche sabato, una sola formatrice disponibile sabato)

5. **Preferenze scuole:** alcune solo mattina, altre solo pomeriggio, altre misto

6. **Priorità quinte:** devono finire prima di maggio

7. **Vacanze scolastiche:** da escludere nel periodo gennaio-maggio

8. **Laboratori già fatti:** alcuni lab fatti ottobre-dicembre (info da integrare)

9. **Continuità formatrice:** idealmente stessa formatrice per tutta la classe, almeno per ciclo di laboratorio

### Piano di sviluppo

#### Fase 1: Adattamento optimizer (DA FARE)
- [ ] Sessione di brainstorming per definire struttura dati e vincoli
- [ ] Implementare lettura dati da Google Sheet pubblico
- [ ] Adattare vincoli ai requisiti reali
- [ ] Testare con dati reali

#### Fase 2: Distribuzione (DOPO)
- [ ] Impacchettare come `.exe` per Windows
- [ ] L'utente finale (senza competenze tecniche) potrà:
  1. Aggiornare i dati nel Google Sheet
  2. Doppio click su `optimize.exe`
  3. Ottenere `calendario_ottimizzato.xlsx`

### Decisioni prese

- **Input dati:** Google Sheet pubblico (condiviso con "chiunque abbia il link")
- **Output:** File Excel locale
- **Target:** utente Windows senza competenze tecniche

### Per riprendere il lavoro

1. Lanciare sessione di brainstorming per definire:
   - Struttura esatta del Google Sheet (quali fogli, quali colonne)
   - Come gestire i vincoli complessi (costruzione rivelatore, lab autonomi, ecc.)
   - Come rappresentare i laboratori già fatti
2. Poi procedere con l'implementazione

