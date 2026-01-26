# Cosmic School - Ottimizzatore Calendario Laboratori

Sistema di ottimizzazione per la distribuzione di laboratori scolastici tra classi e formatrici, utilizzando **Google OR-Tools CP-SAT solver** con un **sistema formale di constraints**.

## Overview

L'optimizer schedula 87 classi in 13 scuole per 5 laboratori FOP, gestiti da 4 formatrici, rispettando:
- **14 Hard Constraints** (vincoli obbligatori)
- **10 Soft Constraints** (preferenze ottimizzate)
- Budget di 708 ore totali
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
├── requirements.txt              # Dipendenze unificate
├── INTERPRETAZIONE_VINCOLI.md    # Specifica vincoli (riferimento)
├── CLAUDE.md                     # Istruzioni per Claude Code
│
├── data/
│   ├── input/                    # File CSV di input
│   │   ├── scuole.csv
│   │   ├── classi.csv
│   │   ├── formatrici.csv
│   │   ├── laboratori.csv
│   │   ├── laboratori_classi.csv
│   │   ├── formatrici_classi.csv
│   │   ├── fasce_orarie_classi.csv
│   │   └── date_escluse_classi.csv
│   └── output/                   # Risultati ottimizzazione
│       └── calendario.csv
│
├── src/
│   ├── optimizer.py              # Optimizer principale
│   ├── constraints/              # Sistema formale constraints
│   │   ├── base.py              # Classi base
│   │   ├── hard_constraints.py  # 14 hard constraints
│   │   ├── soft_constraints.py  # 10 soft constraints
│   │   ├── special_rules.py     # Regole speciali
│   │   ├── factory.py           # Factory per caricamento
│   │   ├── README.md            # Documentazione constraints
│   │   ├── config/              # Configurazione
│   │   │   └── constraint_weights.yaml  # Pesi soft constraints
│   │   └── examples/            # Esempi di utilizzo
│   │       └── constraint_example.py
│   ├── date_utils.py            # Utilities date/orari
│   └── export_formatter.py      # Formattazione Excel output
│
├── scripts/
│   ├── test_optimizer_pipeline.py  # Test pipeline completo
│   └── test_subset.py              # Test su subset ridotto
│
└── archive/                     # Codice legacy e doc obsoleti
    ├── optimizers/              # V0-V6 (versioni precedenti)
    ├── docs/                    # Documentazione obsoleta
    └── legacy_utils/            # Utilities non più usati
```

## Quick Start

### Run Optimizer

```bash
# Dati completi (default timeout: 300s)
python src/optimizer.py --verbose

# Con timeout personalizzato
python src/optimizer.py --verbose --timeout 600

# Output personalizzato
python src/optimizer.py --output data/output/my_calendar.csv
```

### Test

```bash
# Test pipeline completo (smoke test)
python scripts/test_optimizer_pipeline.py

# Test su subset ridotto (2 scuole)
python scripts/test_subset.py

# Analizza sistema constraints
./analyze-constraints
```

## Architettura

### Sistema di Constraints Formali

L'optimizer usa un sistema strutturato di constraints definiti in `src/constraints/`:

```python
from constraints import ConstraintFactory

# Carica tutti i constraints dai CSV
factory = ConstraintFactory(data_dir="data/input")
constraints = factory.build_all_constraints()

# Filtra per tipo
hard = [c for c in constraints if c.type == ConstraintType.HARD]
soft = [c for c in constraints if c.type == ConstraintType.SOFT]
```

**Vedi `src/constraints/README.md`** per documentazione completa del sistema.

### Variabili di Decisione

Per ogni incontro `(classe, lab, k)`:
- `settimana[c,l,k]`: IntVar(0..15) - Settimana (16 totali)
- `giorno[c,l,k]`: IntVar(0..5) - Giorno (lun-sab)
- `fascia[c,l,k]`: IntVar(1..3) - Fascia oraria (mattino1, mattino2, pomeriggio)
- `formatrice[c,l,k]`: IntVar(1..4) - ID formatrice
- `accorpa[c1,c2,lab]`: BoolVar - True se classi accorpate

### Constraints Implementati

**Hard Constraints (14)** - devono essere soddisfatti:
- H01: Budget ore formatrici (708h totali)
- H02: Disponibilità temporale formatrici
- H03: Date già fissate (pre-schedulati)
- H04: Laboratori specifici per classe
- H05: Dettagli laboratorio (mattina/pomeriggio)
- H06: Fasce orarie per classe
- H07: Date escluse per classe
- H08: Max 1 incontro/settimana per classe
- H09: Lab 8.0 deve essere ultimo
- H10: No sovrapposizioni formatrici
- H11: Periodo scheduling (16 settimane, 2 finestre)
- H12: Max 2 classi accorpate
- H13: Completamento laboratori
- H14: Lab 9.0 prima di Lab 5.0

**Soft Constraints (10)** - ottimizzati nell'obiettivo:
- S01: **Massimizza accorpamenti (peso 20)** ⭐ CRITICO
- S02: Continuità formatrice per classe
- S03: Media ore settimanali formatrici
- S04: Preferenze fasce formatrici
- S05: Accorpamenti preferenziali classi
- S06: Sequenza ideale laboratori
- S07: Priorità classi quinte (finire prima)
- S08: Variazione fasce orarie
- S09: Bilanciamento carico formatrici
- S10: Minimizza scheduling tardo (maggio)

**Regole Speciali**:
- Citizen Science (Lab 4.0): gap 1 settimana tra incontro 2 e 4 (incontro 3 autonomo)
- Incontri parziali: alcune classi fanno solo 1-2 incontri invece del totale
- Vincoli pomeriggio: varie combinazioni (tutti, almeno 1, 2 non consecutivi)

### Dati Input

File CSV in `data/input/`:

| File | Descrizione |
|------|-------------|
| `scuole.csv` | 13 scuole |
| `classi.csv` | 87 classi (anno, priorità, accorpamenti preferenziali) |
| `formatrici.csv` | 4 formatrici (budget ore, disponibilità, preferenze) |
| `laboratori.csv` | 5 laboratori FOP (num incontri, ore, sequenza) |
| `laboratori_classi.csv` | Assegnazione lab a classi + date fissate |
| `formatrici_classi.csv` | Preferenze formatrice-classe (soft) |
| `fasce_orarie_classi.csv` | Vincoli fasce orarie per classe |
| `date_escluse_classi.csv` | Date non disponibili per classe |

### Output

File CSV: `data/output/calendario.csv` (default)

**Colonne**:
- `classe_id`, `classe_nome`, `scuola_nome`
- `laboratorio_id`, `laboratorio_nome`
- `incontro_num` (1-based)
- `formatrice_id`, `formatrice_nome`
- `settimana`, `giorno_num`, `giorno_nome`
- `fascia_num`, `fascia_nome`
- `slot` (ordinamento)
- `data_ora` (formato leggibile)
- `accorpata_con` (se accorpata con altre classi)

**Statistiche**:
- Numero incontri schedulati
- Numero accorpamenti realizzati
- Distribuzione ore per formatrice

## Configurazione

### Pesi Soft Constraints

Modifica `src/constraints/config/constraint_weights.yaml`:

```yaml
objective_function:
  maximize_grouping: 20        # Accorpamenti (CRITICO!)
  trainer_continuity: 10       # Continuità formatrice
  fifth_year_priority: 3       # Priorità quinte
  # ... altri pesi
```

### Solver Parameters

In `src/optimizer.py`:
- `NUM_SETTIMANE = 16` - Orizzonte scheduling
- `NUM_GIORNI = 6` - Lun-Sab
- `NUM_FASCE = 3` - Mattino1, Mattino2, Pomeriggio
- `timeout = 300s` - Default (configurabile via CLI)
- `num_workers = 12` - Parallelizzazione CP-SAT

## Budget Context

**Perché S01 (massimizzare accorpamenti) ha peso 20?**

- Budget totale: **708 ore** (somma 4 formatrici)
- Con max accorpamenti: **664 ore** → +44h margine ✅
- Senza accorpamenti: **926 ore** → eccede budget ❌

**Gli accorpamenti sono essenziali per la fattibilità del problema.**

## Troubleshooting

### Nessuna soluzione trovata

**Possibili cause**:
1. **Vincoli troppo stringenti**: Rilassa alcuni hard constraints o verifica date escluse
2. **Budget insufficiente**: Verifica che accorpamenti siano possibili
3. **Timeout troppo breve**: Aumenta `--timeout 600`
4. **Conflitti date fissate**: Controlla `laboratori_classi.csv`

**Debug**:
```bash
# Analizza constraints e compatibilità
./analyze-constraints

# Test su subset ridotto
python scripts/test_subset.py

# Verbose output
python src/optimizer.py --verbose --timeout 600
```

### Performance lente

- Aumenta `num_search_workers` in `optimizer.py`
- Riduci `NUM_SETTIMANE` se possibile
- Usa subset per test rapidi


## Sviluppo

### Aggiungere Nuovi Constraints

1. **Definisci il constraint** in `src/constraints/hard_constraints.py` o `soft_constraints.py`:

```python
@dataclass(kw_only=True)
class MyNewConstraint(HardConstraint):
    """Descrizione del vincolo."""
    param1: int
    param2: str

    id: str = "H15"
    name: str = "My New Constraint"
    category: ConstraintCategory = ConstraintCategory.TEMPORAL

    def add_to_model(self, model, variables, context):
        # Implementa vincolo OR-Tools
        # model.Add(...)
        pass
```

2. **Aggiungi al factory** in `src/constraints/factory.py` per caricamento automatico dai CSV

3. **Configura peso** in `src/constraints/config/constraint_weights.yaml` (se soft)

4. **Documenta** in `INTERPRETAZIONE_VINCOLI.md`

### Testing

```bash
# Test constraints singoli
python tests/test_constraints.py

# Test pipeline completo
python scripts/test_optimizer_pipeline.py

# Test su dati reali subset
python scripts/test_subset.py
```

### Versioni Archiviate

Le versioni precedenti (V0-V6) sono in `archive/optimizers/` per riferimento storico.

## Riferimenti

- **INTERPRETAZIONE_VINCOLI.md** - Specifica completa vincoli
- **src/constraints/README.md** - Documentazione sistema constraints
- **CLAUDE.md** - Istruzioni per Claude Code
- **src/constraints/config/constraint_weights.yaml** - Configurazione pesi

## License

Progetto Cosmic School - Sistema di scheduling laboratori scolastici.
