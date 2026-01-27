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

### Pipeline Completa

```bash
# 1. Genera matrici disponibilità (solo prima volta)
python src/generators/build_slots_calendar.py
python src/generators/build_class_availability.py
python src/generators/generate_formatrici_availability.py

# 2. Esegui optimizer lab (in ordine)
python src/optimizers/lab4_citizen_science.py
python src/optimizers/lab5_orientamento.py
python src/optimizers/lab7_sensibilizzazione.py
python src/optimizers/lab8_lab9.py

# 3. Genera calendario unificato
python src/generators/generate_unified_calendar.py

# 4. Assegna formatrici
python src/optimizers/trainer_assignment.py -v

# 5. Genera viste
python src/generators/generate_views.py

# 6. Verifica vincoli
python src/verify_constraints.py
```

## Architettura Pipeline

### 1. Optimizer per Laboratorio

Ogni lab ha vincoli specifici:

| Lab | Nome | Incontri | Vincoli Speciali |
|-----|------|----------|------------------|
| 4 | Citizen Science | 5 | Gap tra incontro 2 e 4 |
| 5 | Orientamento | 2 | Dopo Lab 4 |
| 7 | Sensibilizzazione | 2 | Settimane consecutive, dopo Lab 4+5 |
| 8 | Presentazione manuali | 1 | Deve essere l'ultimo |
| 9 | Sensibilizzazione pt.2 | 1 | Prima di Lab 5 |

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
- `data/output/calendario_lab8_lab9_ortools.csv` - Calendario Lab 8/9
- `data/output/calendario_laboratori.csv` - Calendario unificato
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
2. Disponibilità formatrici insufficiente
3. Vincoli di consecutività non soddisfacibili

**Debug**:
```bash
# Verifica stato attuale
python src/verify_constraints.py

# Controlla overbooking nel calendario unificato
python src/generators/generate_unified_calendar.py
```

### Classi Incomplete

Verifica che le note "solo X incontri" in `laboratori_classi.csv` siano corrette.

## Versioni Archiviate

Le versioni precedenti (V0-V7) e il sistema di constraints formali sono in `archive/` per riferimento storico.

## Riferimenti

- **INTERPRETAZIONE_VINCOLI.md** - Specifica completa vincoli
- **CLAUDE.md** - Istruzioni per Claude Code
