# Inventario Completo Constraints Formali

**Generato**: 26 Gennaio 2026
**Fonte**: `src/constraints/` (sistema formale)
**Scopo**: Documentazione esatta per riscrittura optimizer

---

## 📊 RIEPILOGO

| Tipo | Quantità | File |
|------|----------|------|
| **Hard Constraints** | 14 | `hard_constraints.py` |
| **Soft Constraints** | 10 | `soft_constraints.py` |
| **Special Rules** | 7 | `special_rules.py` |
| **TOTALE** | **31** | |

---

## 🔒 HARD CONSTRAINTS (14)

### H01: TrainerTotalHoursConstraint
```python
@dataclass
class TrainerTotalHoursConstraint(HardConstraint):
    trainer_id: int
    trainer_name: str
    max_hours: int

    id: str = "H01"
    category: ConstraintCategory = CAPACITY
```
**Fonte**: `formatrici.csv` → `ore_generali`
**Vincolo**: Budget ore totali per formatrice

---

### H02: TrainerAvailabilityConstraint
```python
@dataclass
class TrainerAvailabilityConstraint(HardConstraint):
    trainer_id: int
    trainer_name: str
    available_mornings: List[str]      # ["lun", "mar", ...]
    available_afternoons: List[str]    # ["lun", "mer", ...]
    available_dates: Optional[List[str]] = None  # Slot specifici
    works_saturday: bool = False

    id: str = "H02"
    category: ConstraintCategory = TEMPORAL
```
**Fonte**: `formatrici.csv` → `mattine_disponibili`, `pomeriggi_disponibili`, `date_disponibili`, `lavora_sabato`
**Logica**:
- Se `date_disponibili` è set → SOLO quelle date/orari
- Altrimenti → usa `mattine_disponibili` + `pomeriggi_disponibili`
- `works_saturday`: solo Margherita può lavorare sabato

---

### H03: FixedDatesConstraint
```python
@dataclass
class FixedDatesConstraint(HardConstraint):
    class_id: int
    class_name: str
    lab_id: int
    lab_name: str
    fixed_dates: List[str]  # Date parsate

    id: str = "H03"
    category: ConstraintCategory = TEMPORAL
```
**Fonte**: `laboratori_classi.csv` → `date_fissate`
**Vincolo**: Date già fissate sono immutabili (SUPER HARD)
**Impatto**:
- Classe occupata in quella settimana
- Rispetta "max 1 incontro/settimana"
- NO altri incontri in quella settimana

---

### H04: ClassLabAssignmentConstraint
```python
@dataclass
class ClassLabAssignmentConstraint(HardConstraint):
    class_id: int
    class_name: str
    assigned_labs: List[int]  # Lab IDs

    id: str = "H04"
    category: ConstraintCategory = ASSIGNMENT
```
**Fonte**: `laboratori_classi.csv`
**Vincolo**: Ogni classe fa SOLO i lab assegnati (non tutti)

---

### H05: LabTimeOfDayConstraint
```python
@dataclass
class LabTimeOfDayConstraint(HardConstraint):
    class_id: int
    class_name: str
    lab_id: int
    lab_name: str
    time_of_day: Literal["mattina", "pomeriggio"]

    id: str = "H05"
    category: ConstraintCategory = TEMPORAL
```
**Fonte**: `laboratori_classi.csv` → `dettagli`
**Vincolo**: Lab DEVE essere schedulato in mattina o pomeriggio (quando specificato)

---

### H06: ClassTimeSlotsConstraint
```python
@dataclass
class ClassTimeSlotsConstraint(HardConstraint):
    class_id: int
    class_name: str
    available_slots: List[str]  # ["mattino1", "mattino2", ...]
    is_hard: bool               # True se preferenza="disponibile"
    available_weekdays: List[str]  # ["lunedì", "martedì", ...]

    id: str = "H06"
    category: ConstraintCategory = TEMPORAL
```
**Fonte**: `fasce_orarie_classi.csv` → `fasce_disponibili`, `preferenza`, `giorni_settimana`
**Vincolo**: Classe può usare SOLO questi slot/giorni
**Nota**: È HARD solo se `preferenza = "disponibile"`, altrimenti è soft

---

### H07: ClassExcludedDatesConstraint
```python
@dataclass
class ClassExcludedDatesConstraint(HardConstraint):
    class_id: int
    class_name: str
    excluded_dates: List[str]  # Date parsate

    id: str = "H07"
    category: ConstraintCategory = TEMPORAL
```
**Fonte**: `date_escluse_classi.csv` → `date_escluse`
**Vincolo**: Classe NON può avere incontri in queste date

---

### H08: MaxOneMeetingPerWeekConstraint
```python
@dataclass
class MaxOneMeetingPerWeekConstraint(HardConstraint):
    class_id: int
    class_name: str

    id: str = "H08"
    category: ConstraintCategory = TEMPORAL
```
**Fonte**: Implicito (regola generale)
**Vincolo**: Max 1 incontro/settimana per classe (include date fissate)

---

### H09: Lab8LastConstraint
```python
@dataclass
class Lab8LastConstraint(HardConstraint):
    class_id: int
    class_name: str

    id: str = "H09"
    category: ConstraintCategory = SEQUENCING
```
**Fonte**: `INTERPRETAZIONE_VINCOLI.md`
**Vincolo**: Lab 8.0 (Presentazione Manuali) DEVE essere sempre l'ultimo

---

### H10: NoTrainerOverlapConstraint
```python
@dataclass
class NoTrainerOverlapConstraint(HardConstraint):
    trainer_id: int
    trainer_name: str

    id: str = "H10"
    category: ConstraintCategory = CAPACITY
```
**Fonte**: Implicito (regola fisica)
**Vincolo**: Formatrice non può essere in due posti contemporaneamente

---

### H11: SchedulingPeriodConstraint
```python
@dataclass
class SchedulingPeriodConstraint(HardConstraint):
    window1_start: str = "2026-01-28"
    window1_end: str = "2026-04-01"
    window2_start: str = "2026-04-13"
    window2_end: str = "2026-05-16"

    id: str = "H11"
    category: ConstraintCategory = TEMPORAL
```
**Fonte**: `INTERPRETAZIONE_VINCOLI.md`
**Vincolo**: Tutti gli incontri nelle finestre valide (escl. Pasqua)

---

### H12: MaxGroupSizeConstraint
```python
@dataclass
class MaxGroupSizeConstraint(HardConstraint):
    max_group_size: int = 2

    id: str = "H12"
    category: ConstraintCategory = GROUPING
```
**Fonte**: `INTERPRETAZIONE_VINCOLI.md`
**Vincolo**: Max 2 classi per meeting
**Condizioni accorpamento**:
- Stessa scuola
- Stesso lab
- Stessa formatrice (se pre-assegnata)
- Stesso slot (settimana + giorno + fascia)
- Fasce compatibili per entrambe
- Date compatibili per entrambe

---

### H13: LabCompletionConstraint
```python
@dataclass
class LabCompletionConstraint(HardConstraint):
    class_id: int
    class_name: str
    lab_id: int
    lab_name: str
    num_meetings_required: int

    id: str = "H13"
    category: ConstraintCategory = ASSIGNMENT
```
**Fonte**: `laboratori.csv` → `num_incontri` (+ override in `laboratori_classi.csv`)
**Vincolo**: Classe deve completare tutti gli incontri richiesti per ogni lab

---

### H14: Lab9BeforeLab5Constraint
```python
@dataclass
class Lab9BeforeLab5Constraint(HardConstraint):
    class_id: int
    class_name: str

    id: str = "H14"
    category: ConstraintCategory = SEQUENCING
```
**Fonte**: `INTERPRETAZIONE_VINCOLI.md`
**Vincolo**: Lab 9.0 DEVE essere schedulato prima di Lab 5.0

---

## 🎯 SOFT CONSTRAINTS (10)

### S01: MaximizeGroupingConstraint ⚠️ CRITICO
```python
@dataclass
class MaximizeGroupingConstraint(SoftConstraint):
    weight: int = 20

    id: str = "S01"
    category: ConstraintCategory = GROUPING
```
**Fonte**: `INTERPRETAZIONE_VINCOLI.md` → Budget Ore
**Preferenza**: MASSIMIZZARE accorpamenti (ESSENZIALE per budget!)
**Peso**: 20 (ALTO - bonus per ogni accorpamento)
**Contesto**:
- Con accorpamenti: 664h necessarie
- Senza: 926h necessarie
- Budget: 708h → Accorpamenti ESSENZIALI

---

### S02: TrainerContinuityConstraint
```python
@dataclass
class TrainerContinuityConstraint(SoftConstraint):
    class_id: int
    class_name: str
    preferred_trainer_id: int
    preferred_trainer_name: str
    weight: int = 10

    id: str = "S02"
    category: ConstraintCategory = ASSIGNMENT
```
**Fonte**: `formatrici_classi.csv`
**Preferenza**: Stessa formatrice per tutti i lab di una classe
**Peso**: 10 (ALTO - penalità per cambio formatrice)

---

### S03: TrainerWeeklyHoursConstraint
```python
@dataclass
class TrainerWeeklyHoursConstraint(SoftConstraint):
    trainer_id: int
    trainer_name: str
    target_weekly_hours: float
    weight: int = 3

    id: str = "S03"
    category: ConstraintCategory = CAPACITY
```
**Fonte**: `formatrici.csv` → `ore_settimanali (media)`
**Preferenza**: Rispettare media ore/settimana (non vincolante)
**Peso**: 3 (MEDIO)

---

### S04: TrainerTimePreferenceConstraint
```python
@dataclass
class TrainerTimePreferenceConstraint(SoftConstraint):
    trainer_id: int
    trainer_name: str
    preferred_time: Literal["mattina", "pomeriggio", "misto"]
    weight: int = 1

    id: str = "S04"
    category: ConstraintCategory = TEMPORAL
```
**Fonte**: `formatrici.csv` → `preferenza_fasce`
**Preferenza**: Rispettare preferenza oraria formatrice
**Peso**: 1 (BASSO)

---

### S05: PreferredGroupingConstraint
```python
@dataclass
class PreferredGroupingConstraint(SoftConstraint):
    class_id: int
    class_name: str
    preferred_partner_id: int
    preferred_partner_name: str
    weight: int = 5

    id: str = "S05"
    category: ConstraintCategory = GROUPING
```
**Fonte**: `classi.csv` → `accorpamento_preferenziale`
**Preferenza**: Accorpare classi con partner preferiti
**Peso**: 5 (MEDIO - bonus quando accorpate)

---

### S06: LabSequenceConstraint
```python
@dataclass
class LabSequenceConstraint(SoftConstraint):
    ideal_sequence: List[int] = field(default_factory=lambda: [7, 4, 5])
    weight: int = 2

    id: str = "S06"
    category: ConstraintCategory = SEQUENCING
```
**Fonte**: `INTERPRETAZIONE_VINCOLI.md`
**Preferenza**: Ordine ideale 7 (Sensibilizzazione) → 4 (Citizen Science) → 5 (Orientamento)
**Peso**: 2 (BASSO - bonus per rispetto sequenza)

---

### S07: FifthYearPriorityConstraint
```python
@dataclass
class FifthYearPriorityConstraint(SoftConstraint):
    class_id: int
    class_name: str
    class_year: int
    weight: int = 3

    id: str = "S07"
    category: ConstraintCategory = TEMPORAL
```
**Fonte**: `INTERPRETAZIONE_VINCOLI.md`
**Preferenza**: Classi quinte finiscono prima (evitare Maggio)
**Peso**: 3 (MEDIO - penalità per settimane tardive)

---

### S08: TimeSlotVariationConstraint
```python
@dataclass
class TimeSlotVariationConstraint(SoftConstraint):
    class_id: int
    class_name: str
    weight: int = 2

    id: str = "S08"
    category: ConstraintCategory = TEMPORAL
```
**Fonte**: `INTERPRETAZIONE_VINCOLI.md`
**Preferenza**: Evitare stessa fascia in settimane consecutive
**Peso**: 2 (BASSO - penalità per ripetizione)

---

### S09: BalanceTrainerLoadConstraint
```python
@dataclass
class BalanceTrainerLoadConstraint(SoftConstraint):
    trainer_id: int
    trainer_name: str
    weight: int = 2

    id: str = "S09"
    category: ConstraintCategory = CAPACITY
```
**Fonte**: Implicito (best practice)
**Preferenza**: Bilanciare carico formatrice tra settimane
**Peso**: 2 (BASSO - penalità per varianza alta)

---

### S10: MinimizeLateMaySchedulingConstraint
```python
@dataclass
class MinimizeLateMaySchedulingConstraint(SoftConstraint):
    weight: int = 1

    id: str = "S10"
    category: ConstraintCategory = TEMPORAL
```
**Fonte**: Implicito (preferenza generale)
**Preferenza**: Preferire scheduling anticipato (evitare fine Maggio)
**Peso**: 1 (MOLTO BASSO)

---

## 🔧 SPECIAL RULES (7)

### SP01: CitizenScienceGapConstraint ⚠️ IMPORTANTE
```python
@dataclass
class CitizenScienceGapConstraint(HardConstraint):
    class_id: int
    class_name: str
    school_id: int
    school_name: str
    applies: bool = False  # True per scuole specifiche

    APPLICABLE_SCHOOLS: List[str] = [
        "Potenza", "Vasto", "Bafile", "Lanciano", "Peano Rosa"
    ]

    id: str = "SP01"
    category: ConstraintCategory = SEQUENCING
```
**Fonte**: `INTERPRETAZIONE_VINCOLI.md`
**Vincolo**: Lab 4.0 (Citizen Science) ha 5 incontri ma il 3° è autonomo
**Implementazione**:
- Schedulare solo incontri 1, 2, 4, 5 (4 con formatrice)
- Lasciare 1 settimana vuota tra incontro 2 e 4
- Quella settimana = incontro autonomo (no formatrice)
**Vincolo**: `week[meeting4] >= week[meeting2] + 2`

---

### SP02: PartialLabMeetingsConstraint
```python
@dataclass
class PartialLabMeetingsConstraint(HardConstraint):
    class_id: int
    class_name: str
    lab_id: int
    lab_name: str
    standard_meetings: int  # Da laboratori.csv
    actual_meetings: int    # Ridotto per questa classe

    id: str = "SP02"
    category: ConstraintCategory = ASSIGNMENT
```
**Fonte**: `laboratori_classi.csv` → `dettagli` (es. "solo 1 incontro")
**Vincolo**: Classe fa meno incontri del numero standard per questo lab

---

### SP03: MultiMeetingAfternoonConstraint
```python
@dataclass
class MultiMeetingAfternoonConstraint(HardConstraint):
    class_id: int
    class_name: str
    lab_id: int
    lab_name: str
    num_afternoon_required: int
    avoid_consecutive: bool = True

    id: str = "SP03"
    category: ConstraintCategory = TEMPORAL
```
**Fonte**: `laboratori_classi.csv` → `dettagli`
**Esempio**: "2 incontri devono essere di pomeriggio ma non in settimane consecutive"
**Vincoli**:
1. N incontri DEVONO essere pomeriggio
2. Quelli pomeriggio NON consecutivi

---

### SP04: OneMeetingTimeConstraint
```python
@dataclass
class OneMeetingTimeConstraint(HardConstraint):
    class_id: int
    class_name: str
    lab_id: int
    lab_name: str
    time_of_day: str  # "mattina" o "pomeriggio"
    min_meetings_required: int = 1

    id: str = "SP04"
    category: ConstraintCategory = TEMPORAL
```
**Fonte**: `laboratori_classi.csv` → `dettagli`
**Esempio**: "un incontro deve essere di pomeriggio"
**Vincolo**: Almeno 1 incontro in fascia specificata

---

### SP05: WeekdayTimeSpecificConstraint
```python
@dataclass
class WeekdayTimeSpecificConstraint(HardConstraint):
    class_id: int
    class_name: str
    weekday_constraints: dict  # {"mercoledì": "pomeriggio", ...}

    id: str = "SP05"
    category: ConstraintCategory = TEMPORAL
```
**Fonte**: `fasce_orarie_classi.csv` → `giorni_settimana`
**Esempio**: "mercoledì pomeriggio, giovedì pomeriggio"
**Vincolo**: Giorni specifici disponibili solo in certe fasce

---

### SP06: IgnoreExternalLabsConstraint
```python
@dataclass
class IgnoreExternalLabsConstraint(HardConstraint):
    fop_labs: List[int] = [4, 5, 7, 8, 9]
    external_labs: List[int] = [1, 2, 3, 6, 11]

    id: str = "SP06"
    category: ConstraintCategory = ASSIGNMENT
```
**Fonte**: `INTERPRETAZIONE_VINCOLI.md`
**Vincolo**: Schedulare SOLO lab FOP (4,5,7,8,9), ignorare esterni (1,2,3,6,11)
**Nota**: Più filtro preprocessing che vincolo runtime

---

### SP07: SaturdayOnlyMargheritaConstraint
```python
@dataclass
class SaturdayOnlyMargheritaConstraint(HardConstraint):
    trainer_id: int = 4
    trainer_name: str = "Margherita"

    id: str = "SP07"
    category: ConstraintCategory = TEMPORAL
```
**Fonte**: `formatrici.csv` → `lavora_sabato`
**Vincolo**: SOLO Margherita può lavorare il sabato
**Nota**: Coperto da H02 (TrainerAvailabilityConstraint)

---

## 🔍 NOTE IMPORTANTI

### 1. Metodi Non Implementati
Tutti i constraints hanno metodi **stub**:
```python
def validate(self, solution: Any) -> bool:
    pass  # ← Non implementato

def add_to_model(self, model: Any, variables: Any) -> None:
    pass  # ← Non implementato

def penalty(self, solution: Any) -> float:  # Solo soft
    pass  # ← Non implementato

def add_to_objective(self, model: Any, variables: Any) -> Any:  # Solo soft
    pass  # ← Non implementato
```

**Implicazione**: Questi metodi devono essere implementati per ogni constraint nel nuovo optimizer!

### 2. Campi Opzionali
Alcuni campi hanno valori di default o sono opzionali:
- `available_dates` in H02 (None se non specificato)
- `is_hard` in H06 (dipende da `preferenza`)
- `applies` in SP01 (solo per scuole specifiche)
- `avoid_consecutive` in SP03 (default True)

### 3. Configurazione Pesi
I pesi soft sono configurabili in `config/constraint_weights.yaml`:
```yaml
objective_function:
  maximize_grouping: 20
  trainer_continuity: 10
  # ...
```

### 4. Factory Pattern
`ConstraintFactory` in `factory.py` costruisce automaticamente i constraints dai CSV:
```python
factory = ConstraintFactory()
constraints = factory.build_all_constraints()
```

---

## ✅ COMPLETEZZA vs INTERPRETAZIONE_VINCOLI.md

### Allineamento
✅ Tutti i vincoli di INTERPRETAZIONE_VINCOLI.md sono presenti
✅ ID e nomi corrispondono
✅ Sorgenti CSV corrette
✅ Logica descritta accuratamente

### Differenze Minori
1. **Ordine ID**: Sistema formale usa H01-H14, S01-S10, SP01-SP07
2. **Granularità**: Alcuni vincoli sono più dettagliati (es. H06 con `is_hard`)
3. **Special Rules**: Separate in file dedicato per chiarezza

---

## 🎯 PROSSIMI PASSI PER RISCRITTURA

1. **Implementare metodi `add_to_model()`** per ogni Hard Constraint
2. **Implementare metodi `add_to_objective()`** per ogni Soft Constraint
3. **Creare OptimizerV7** che usa `ConstraintFactory`
4. **Testare con subset di dati**
5. **Validare output vs V6**

---

**Fine Inventario**
