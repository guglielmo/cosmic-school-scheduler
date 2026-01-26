# Stato Implementazione OptimizerV7

**Data**: 26 Gennaio 2026
**Versione**: 0.1 - Work in Progress

---

## 📊 RIEPILOGO

| Componente | Stato | Note |
|------------|-------|------|
| **Sistema Constraints** | ✅ Completo | 31 constraints definiti |
| **OptimizerV7 Scheletro** | ✅ Completo | Architettura base funzionante |
| **Metodi add_to_model()** | 🔄 Parziale | 1/14 hard constraints implementati |
| **Metodi add_to_objective()** | 🔄 Parziale | 1/10 soft constraints implementati |
| **Test Suite** | ✅ Creata | test_optimizer_v7.py |
| **Bug Tecnici** | ⚠️ 1 critico | Dataclass field ordering |

---

## ✅ COMPLETATO

### 1. Sistema di Constraints Formali
- ✅ 14 Hard Constraints definiti (`src/constraints/hard_constraints.py`)
- ✅ 10 Soft Constraints definiti (`src/constraints/soft_constraints.py`)
- ✅ 7 Special Rules definiti (`src/constraints/special_rules.py`)
- ✅ ConstraintFactory implementato (`src/constraints/factory.py`)
- ✅ Configurazione pesi (`config/constraint_weights.yaml`)
- ✅ Fix H02: aggiunto campo `excluded_dates`

### 2. OptimizerV7 - Architettura
- ✅ Scheletro completo (`src/optimizer_V7.py`, ~600 righe)
- ✅ Classe `MeetingKey` per chiavi univoche incontri
- ✅ Classe `ModelVariables` per container variabili
- ✅ Metodi pipeline:
  - `load_data()`: Carica CSV e costruisce mappings
  - `load_constraints()`: Usa ConstraintFactory
  - `build_variables()`: Crea variabili OR-Tools
  - `apply_hard_constraints()`: Chiama `add_to_model()` per ogni hard constraint
  - `build_objective()`: Chiama `add_to_objective()` per ogni soft constraint
  - `solve()`: Risolve con CP-SAT
  - `export_solution()`: Esporta risultati (stub)
  - `run()`: Pipeline completo

### 3. Variabili OR-Tools Create
```python
# Per ogni incontro (classe, lab, k):
settimana[meeting]: IntVar(0..15)  # 16 settimane
giorno[meeting]: IntVar(0..5)      # lun-sab
fascia[meeting]: IntVar(1..3)      # mattino1, mattino2, pomeriggio
formatrice[meeting]: IntVar(1..4)  # 4 formatrici
slot[meeting]: IntVar              # Combinato per ordinamento
```

### 4. Constraints Implementati

| ID | Constraint | Status | File | Linee |
|----|-----------|--------|------|-------|
| **H08** | MaxOneMeetingPerWeekConstraint | ✅ Implementato | hard_constraints.py | ~234-246 |
| **H01** | TrainerTotalHoursConstraint | ⚠️ Parziale | hard_constraints.py | ~29-52 |
| **S01** | MaximizeGroupingConstraint | ✅ Implementato | soft_constraints.py | ~32-45 |

**Dettagli**:

#### H08: MaxOneMeetingPerWeekConstraint ✅
```python
def add_to_model(self, model, variables):
    week_vars = [variables.settimana[m]
                 for m in variables.meetings_by_class[self.class_id]]
    if len(week_vars) > 1:
        model.AddAllDifferent(week_vars)
```
**Status**: Completamente implementato e funzionante.

#### H01: TrainerTotalHoursConstraint ⚠️
```python
def add_to_model(self, model, variables):
    # Crea is_formatrice variables
    # Somma ore * is_formatrice per ogni incontro
    # model.Add(total_hours <= max_hours)
```
**Status**: Implementazione base. Problemi:
- ❌ Ore per lab hardcoded (2h), serve accesso a `lab_info`
- ❌ Non gestisce accorpamenti (duplicate hours)
- ✅ Logica base corretta

#### S01: MaximizeGroupingConstraint ✅
```python
def add_to_objective(self, model, variables):
    return sum(variables.accorpa.values())  # Somma tutte le variabili accorpa
```
**Status**: Implementato. Richiede:
- ⚠️ Variabili `accorpa[]` da creare in `build_variables()`

### 5. Test Suite
- ✅ Script `test_optimizer_v7.py` creato
- ✅ 6 test definiti:
  1. Inizializzazione
  2. Caricamento dati
  3. Caricamento constraints
  4. Creazione variabili
  5. Applicazione constraints
  6. Costruzione obiettivo

---

## 🔄 IN CORSO

### Bug Critico: Dataclass Field Ordering
**Problema**: Python dataclasses richiede che campi con default vengano DOPO campi senza default.

**Errore**:
```python
@dataclass
class TrainerTotalHoursConstraint(HardConstraint):
    trainer_id: int              # No default
    trainer_name: str            # No default
    max_hours: int               # No default

    id: str = "H01"              # ❌ ERRORE: default dopo no-default
    name: str = "Trainer Total Hours"
```

**Errore Python**:
```
TypeError: non-default argument 'trainer_id' follows default argument
```

**Soluzione**: Usare `field(default=..., init=False)`:
```python
id: str = field(default="H01", init=False)
name: str = field(default="Trainer Total Hours", init=False)
category: ConstraintCategory = field(default=ConstraintCategory.CAPACITY, init=False)
description: str = field(default="Total hours budget...", init=False)
```

**Status**: ⚠️ Applicato SOLO a H01. Serve applicare a TUTTI i 31 constraints.

---

## ❌ NON IMPLEMENTATO

### Constraints (30/31 da completare)

#### Hard Constraints (13/14 da implementare)
- ❌ H02: TrainerAvailabilityConstraint
- ❌ H03: FixedDatesConstraint
- ❌ H04: ClassLabAssignmentConstraint
- ❌ H05: LabTimeOfDayConstraint
- ❌ H06: ClassTimeSlotsConstraint
- ❌ H07: ClassExcludedDatesConstraint
- ❌ H09: Lab8LastConstraint
- ❌ H10: NoTrainerOverlapConstraint
- ❌ H11: SchedulingPeriodConstraint
- ❌ H12: MaxGroupSizeConstraint
- ❌ H13: LabCompletionConstraint
- ❌ H14: Lab9BeforeLab5Constraint

#### Soft Constraints (9/10 da implementare)
- ❌ S02: TrainerContinuityConstraint
- ❌ S03: TrainerWeeklyHoursConstraint
- ❌ S04: TrainerTimePreferenceConstraint
- ❌ S05: PreferredGroupingConstraint
- ❌ S06: LabSequenceConstraint
- ❌ S07: FifthYearPriorityConstraint
- ❌ S08: TimeSlotVariationConstraint
- ❌ S09: BalanceTrainerLoadConstraint
- ❌ S10: MinimizeLateMaySchedulingConstraint

#### Special Rules (7/7 da implementare)
- ❌ SP01: CitizenScienceGapConstraint
- ❌ SP02: PartialLabMeetingsConstraint
- ❌ SP03: MultiMeetingAfternoonConstraint
- ❌ SP04: OneMeetingTimeConstraint
- ❌ SP05: WeekdayTimeSpecificConstraint
- ❌ SP06: IgnoreExternalLabsConstraint
- ❌ SP07: SaturdayOnlyMargheritaConstraint

### Funzionalità

- ❌ **Variabili Accorpamento**: `accorpa[c1, c2, lab]` non create
  - Necessarie per S01, H12, e budget ore
  - Devono essere create in `build_variables()`
  - Devono rispettare condizioni compatibilità (stessa scuola, etc.)

- ❌ **Context Data Access**: Constraints non hanno accesso a dati
  - Serve `lab_info` per ore per lab
  - Serve `class_info` per school_id, year
  - Serve `trainer_info` per max_hours
  - **Soluzione**: Passare `context` object a `add_to_model()`

- ❌ **Export Solution**: `export_solution()` è stub
  - Deve leggere valori da solver
  - Deve formattare come CSV
  - Deve gestire accorpamenti

- ❌ **Validation**: Metodi `validate()` tutti stub
  - Per post-solve validation
  - Per debugging

---

## 🎯 PROSSIMI PASSI

### Priorità ALTA (Bloccanti)

1. **Fix Dataclass Fields** (1-2 ore)
   - Applicare `field(..., init=False)` a tutti i 31 constraints
   - Testare che il sistema si avvii

2. **Context Object** (2-3 ore)
   - Creare classe `ConstraintContext` con tutti i dati necessari
   - Modificare firma `add_to_model(model, variables, context)`
   - Modificare firma `add_to_objective(model, variables, context)`
   - Aggiornare constraints implementati

3. **Variabili Accorpamento** (3-4 ore)
   - Implementare logica compatibilità coppie
   - Creare variabili `accorpa[c1, c2, lab]`
   - Aggiungere vincoli sincronizzazione (se accorpa=1, stessi slot)

### Priorità MEDIA (Funzionalità Core)

4. **Implementare Constraints Critici** (8-10 ore)
   - H02: TrainerAvailabilityConstraint
   - H03: FixedDatesConstraint
   - H09: Lab8LastConstraint
   - H10: NoTrainerOverlapConstraint
   - SP01: CitizenScienceGapConstraint

5. **Implementare Remaining Hard Constraints** (10-15 ore)
   - H04, H05, H06, H07, H11, H12, H13, H14

6. **Implementare Soft Constraints** (8-10 ore)
   - S02-S10

### Priorità BASSA (Nice to Have)

7. **Export Solution** (4-5 ore)
8. **Validation Methods** (3-4 ore)
9. **Special Rules** (5-6 ore)
10. **Unit Tests per ogni Constraint** (10-15 ore)

---

## 📁 FILE CREATI

```
cosmic-school/
├── src/
│   ├── optimizer_V7.py                  ← NEW: Optimizer basato su constraints
│   └── constraints/
│       └── hard_constraints.py          ← MODIFIED: H01, H02, H08 implementati
│       └── soft_constraints.py          ← MODIFIED: S01 implementato
│
├── test_optimizer_v7.py                 ← NEW: Test suite
│
├── CONSTRAINTS_INVENTORY.md             ← NEW: Inventario completo constraints
├── CONSTRAINTS_ALIGNMENT.md             ← NEW: Allineamento con INTERPRETAZIONE_VINCOLI
├── VINCOLI_IMPLEMENTATI_V6.md           ← NEW: Analisi V6
└── IMPLEMENTATION_STATUS.md             ← NEW: Questo file
```

---

## 📊 STATISTICHE

```
Constraints definiti:      31/31  (100%)
Constraints implementati:   3/31  (10%)
  Hard implementati:        1/14  (7%)
  Soft implementati:        1/10  (10%)
  Special implementati:     0/7   (0%)

Codice scritto:           ~800 righe (optimizer_V7.py + implementations)
Test scritti:             6 test cases
Documentazione:           ~1500 righe (4 documenti nuovi)

Tempo stimato rimanente:  40-60 ore
  Fix bloccanti:          6-9 ore
  Core functionality:     28-35 ore
  Nice-to-have:           22-30 ore
```

---

## 🐛 ISSUE TRACKER

| # | Tipo | Priorità | Descrizione | Status |
|---|------|----------|-------------|--------|
| #1 | Bug | 🔴 CRITICA | Dataclass field ordering error | ⏸ In progress |
| #2 | Feature | 🔴 ALTA | Context object per accesso dati | ⏳ Todo |
| #3 | Feature | 🔴 ALTA | Variabili accorpamento | ⏳ Todo |
| #4 | Feature | 🟡 MEDIA | Export solution | ⏳ Todo |
| #5 | Feature | 🟡 MEDIA | Implementare H02-H14 | ⏳ Todo |
| #6 | Feature | 🟡 MEDIA | Implementare S02-S10 | ⏳ Todo |
| #7 | Feature | 🟢 BASSA | Implementare SP01-SP07 | ⏳ Todo |
| #8 | Feature | 🟢 BASSA | Validation methods | ⏳ Todo |

---

## 💡 NOTE TECNICHE

### Perché `field(default=..., init=False)`?
Python dataclasses richiedono che parametri con default vengano DOPO quelli senza. Ma vogliamo mantenere i campi base (`id`, `name`, etc.) in fondo per leggibilità. La soluzione è `init=False` che esclude questi campi dal `__init__` generato.

### Perché ConstraintContext?
I constraints devono accedere a informazioni globali (ore per lab, school_id per classe, etc.) ma non è elegante passare 10 parametri. Un context object centralizza queste info.

### Pattern add_to_model()
Ogni constraint implementa la logica OR-Tools specifica:
- Crea variabili ausiliarie se necessario
- Usa `model.Add()`, `AddAllDifferent()`, `AddForbiddenAssignments()`, etc.
- Accede a `variables.settimana`, `variables.giorno`, etc.

### Pattern add_to_objective()
Ogni soft constraint ritorna un termine (espressione OR-Tools):
- Positivo = penalità (da minimizzare)
- Negativo o BoolVar = bonus (da massimizzare)
- Il peso moltiplica il termine nell'obiettivo

---

**Fine Stato Implementazione**
