# Cosmic School - Ottimizzatore Calendario Laboratori

Sistema di ottimizzazione per la distribuzione di laboratori scolastici tra classi e formatrici, utilizzando **Google OR-Tools CP-SAT solver**.

## Overview

Il sistema schedula 87 classi in 13 scuole per 5 laboratori FOP, gestiti da 4 formatrici, attraverso una **pipeline modulare**:
- Ogni laboratorio ha il proprio optimizer
- I calendari vengono unificati
- Le formatrici vengono assegnate proporzionalmente al budget ore
- Massimizzazione accorpamenti (2 classi insieme) per efficienza

**Documentazione vincoli**: Vedi `INTERPRETAZIONE_VINCOLI.md` per specifiche complete.

## Setup

```bash
# Installa dipendenze
pip install -r requirements.txt

# Oppure con uv (raccomandato)
uv pip install -r requirements.txt
```

## Struttura Progetto

```
cosmic-school/
├── src/
│   ├── optimizers/                    # Optimizer per laboratorio
│   │   ├── lab4_citizen_science.py    # Citizen Science (5 incontri)
│   │   ├── lab5_orientamento.py       # Orientamento e competenze (2 incontri)
│   │   ├── lab7_sensibilizzazione.py  # Sensibilizzazione (2 incontri consecutivi)
│   │   ├── lab8_lab9.py               # Presentazione manuali + pt.2
│   │   └── trainer_assignment.py      # Assegnazione formatrici
│   │
│   ├── generators/                    # Generazione calendari e viste
│   │   ├── build_slots_calendar.py    # Crea matrice slot temporali
│   │   ├── build_class_availability.py # Disponibilità classi per slot
│   │   ├── generate_formatrici_availability.py # Disponibilità formatrici
│   │   ├── generate_unified_calendar.py # Unifica calendari lab
│   │   └── generate_views.py          # Genera viste calendario
│   │
│   ├── utils/
│   │   └── date_utils.py              # Utilities per date
│   │
│   └── verify_constraints.py          # Verifica vincoli
│
├── data/
│   ├── input/                         # File CSV di input
│   └── output/                        # Risultati ottimizzazione
│       └── views/                     # Viste calendario
│
├── archive/                           # Codice legacy (V0-V7)
│
├── INTERPRETAZIONE_VINCOLI.md         # Specifica vincoli
├── CLAUDE.md                          # Istruzioni per Claude Code
└── requirements.txt
```

## Quick Start

### Pipeline Veloce (Comandi Sequenziali)

```bash
# Availability (solo prima volta)
python src/generators/build_slots_calendar.py && \
python src/generators/build_class_availability.py && \
python src/generators/generate_formatrici_availability.py

# Lab 4, 5, 7 → Unifica → Lab 9 → Unifica → Lab 8 → Unifica
python src/optimizers/lab4_citizen_science.py && \
python src/optimizers/lab5_orientamento.py && \
python src/optimizers/lab7_sensibilizzazione.py && \
python src/generators/generate_unified_calendar.py && \
python src/optimizers/lab8_lab9.py --lab 9 && \
python src/generators/generate_unified_calendar.py && \
python src/optimizers/lab8_lab9.py --lab 8 && \
python src/generators/generate_unified_calendar.py

# Formatrici, viste, verifica
python src/optimizers/trainer_assignment.py -v && \
python src/generators/generate_views.py && \
python src/verify_constraints.py
```

### Pipeline Completa

```bash
# ============================================================================
# STEP 1: Genera matrici disponibilità (eseguire solo una volta)
# ============================================================================
python src/generators/build_slots_calendar.py
python src/generators/build_class_availability.py
python src/generators/generate_formatrici_availability.py

# ============================================================================
# STEP 2: Esegui optimizer Lab 4, 5, 7 (in ordine di dipendenza)
# ============================================================================
python src/optimizers/lab4_citizen_science.py
python src/optimizers/lab5_orientamento.py
python src/optimizers/lab7_sensibilizzazione.py

# ============================================================================
# STEP 3: Genera calendario unificato (Lab 4+5+7)
# ============================================================================
python src/generators/generate_unified_calendar.py

# ============================================================================
# STEP 4: Esegui optimizer Lab 9 (evita settimane occupate da Lab 4+5+7)
# ============================================================================
python src/optimizers/lab8_lab9.py --lab 9

# ============================================================================
# STEP 5: Rigenera calendario unificato (Lab 4+5+7+9)
# ============================================================================
python src/generators/generate_unified_calendar.py

# ============================================================================
# STEP 6: Esegui optimizer Lab 8 (evita settimane occupate da Lab 4+5+7+9)
# ============================================================================
python src/optimizers/lab8_lab9.py --lab 8

# ============================================================================
# STEP 7: Rigenera calendario unificato finale (tutti i lab: 4+5+7+9+8)
# ============================================================================
python src/generators/generate_unified_calendar.py

# ============================================================================
# STEP 8: Assegna formatrici al calendario completo
# ============================================================================
python src/optimizers/trainer_assignment.py -v

# ============================================================================
# STEP 9: Genera viste calendario (per formatrice, classe, lab, giornaliere)
# ============================================================================
python src/generators/generate_views.py

# ============================================================================
# STEP 10: Verifica vincoli (ore formatrici, completamento classi, integrità)
# ============================================================================
python src/verify_constraints.py
```

### Perché Rigenerare il Calendario Unificato?

Il calendario unificato (`calendario_laboratori.csv`) deve essere rigenerato **tre volte**:

1. **Dopo Lab 4+5+7**: Fornisce a Lab 9 le informazioni sulle formatrici già occupate
2. **Dopo Lab 9**: Fornisce a Lab 8 le informazioni su Lab 4+5+7+9
3. **Dopo Lab 8**: Crea il calendario finale completo per l'assegnazione formatrici

Lab 9 e Lab 8 usano il calendario unificato per:
- Conoscere quante formatrici sono già occupate in ogni slot
- Evitare settimane già occupate da altri lab (vincolo "1 incontro/settimana")

**Nota**: Lab 9 e Lab 8 devono essere eseguiti separatamente (`--lab 9` poi `--lab 8`) perché hanno requisiti e dipendenze diverse.

## Architettura Pipeline

### 1. Optimizer per Laboratorio

Ogni lab ha vincoli specifici:

| Lab | Nome | Incontri | Vincoli Speciali |
|-----|------|----------|------------------|
| 4 | Citizen Science | 5 | Gap tra incontro 2 e 4 |
| 5 | Orientamento | 2 | Dopo Lab 4 |
| 7 | Sensibilizzazione | 2 | Settimane consecutive, dopo Lab 4+5 |
| 9 | Sensibilizzazione pt.2 | 1 | Evita Lab 4+5+7 |
| 8 | Presentazione manuali | 1 | Evita Lab 4+5+7+9, ultimo lab |

### 2. Accorpamenti

Classi della stessa scuola possono fare lo stesso incontro insieme:
- Risparmio ore formatrice (1 invece di 2)
- Essenziale per rispettare il budget

### 3. Assegnazione Formatrici

- Distribuzione proporzionale al budget ore
- Rispetto disponibilità (giorni, fasce orarie)
- Massimizzazione preferenze formatrice-classe

## Dati Input

File CSV in `data/input/`:

| File | Descrizione |
|------|-------------|
| `scuole.csv` | 13 scuole |
| `classi.csv` | 87 classi (anno, accorpamenti preferenziali) |
| `formatrici.csv` | 4 formatrici (budget ore, disponibilità) |
| `laboratori.csv` | 5 laboratori FOP |
| `laboratori_classi.csv` | Assegnazioni + note "solo X incontri" |
| `fasce_orarie_classi.csv` | Vincoli fasce orarie |
| `date_escluse_classi.csv` | Date non disponibili |
| `formatrici_classi.csv` | Preferenze formatrice-classe |

### Note Speciali

Nel file `laboratori_classi.csv`, la colonna `dettagli` può contenere:
- `"solo 1 incontro"` - classe fa 1 incontro invece del default
- `"solo 2 incontri"` - classe fa 2 incontri invece del default

## Output

### File Generati

- `data/output/calendario_lab4_ortools.csv` - Calendario Lab 4
- `data/output/calendario_lab5_ortools.csv` - Calendario Lab 5
- `data/output/calendario_lab7_ortools.csv` - Calendario Lab 7
- `data/output/calendario_lab9_ortools.csv` - Calendario Lab 9
- `data/output/calendario_lab8_ortools.csv` - Calendario Lab 8
- `data/output/calendario_laboratori.csv` - Calendario unificato (tutti i lab)
- `data/output/calendario_con_formatrici.csv` - Con assegnazione formatrici

### Viste

In `data/output/views/`:
- `calendario_giornaliero.csv` - Vista giornaliera
- `formatrici/` - Un file per formatrice
- `classi/` - Un file per classe
- `laboratori/` - Un file per laboratorio

## Verifica Vincoli

```bash
python src/verify_constraints.py
```

Verifica:
1. **Ore formatrici**: assegnate vs budget
2. **Completamento classi**: tutti i lab richiesti assegnati
3. **Integrità lab**: numero corretto di incontri

## Budget Context

**Perché gli accorpamenti sono critici?**

- Budget totale: **708 ore** (somma 4 formatrici)
- Con max accorpamenti: ~500 ore necessarie ✅
- Senza accorpamenti: ~900 ore necessarie ❌

## Troubleshooting

### Optimizer INFEASIBLE

**Possibili cause**:
1. Overbooking slot (troppi lab nello stesso momento)
2. Disponibilità formatrici insufficiente (vincolo H7 troppo restrittivo)
3. Vincoli di consecutività non soddisfacibili
4. Calendario non rigenerato dopo lab precedenti

**Soluzioni**:
```bash
# 1. Verifica stato attuale
python src/verify_constraints.py

# 2. Controlla overbooking nel calendario unificato
python src/generators/generate_unified_calendar.py

# 3. Assicurati di rigenerare il calendario unificato dopo ogni lab
# Lab 8/9 richiedono il calendario unificato aggiornato!
```

**Nota**: Lab 8 e Lab 9 hanno un vincolo rilassato sulle formatrici (buffer +1) per trovare soluzioni fattibili.

### Classi Incomplete (verify_constraints.py)

**Problema**: `verify_constraints.py` mostra "presentazione manuali: 0/1 meetings" per molte classi.

**Causa**: Calendario unificato non rigenerato dopo Lab 8/9.

**Soluzione**:
```bash
# Rigenera calendario unificato
python src/generators/generate_unified_calendar.py

# Verifica che Lab 8/9 siano inclusi
grep -c "L8-\|L9-" data/output/calendario_laboratori.csv
# Deve mostrare un numero > 0

# Poi rigenera viste e verifica
python src/generators/generate_views.py
python src/verify_constraints.py
```

### Note "solo X incontri"

Verifica che le note "solo X incontri" in `laboratori_classi.csv` siano corrette.

## Versioni Archiviate

Le versioni precedenti (V0-V7) e il sistema di constraints formali sono in `archive/` per riferimento storico.

## Riferimenti

- **INTERPRETAZIONE_VINCOLI.md** - Specifica completa vincoli
- **CLAUDE.md** - Istruzioni per Claude Code
