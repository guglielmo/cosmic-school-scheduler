# Vincoli Implementati in Optimizer V6

Analisi dei vincoli effettivamente implementati nel branch `claude/optimize-lab-scheduling-pzTYb` (ora in `main`).

**Data analisi**: 26 Gennaio 2026
**File analizzato**: `src/optimizer_V6.py` + `src/domain_preprocessor.py`

---

## 📊 Riepilogo Quantitativo

| Categoria | Implementati | Nel Sistema Strutturato | Gap |
|-----------|--------------|-------------------------|-----|
| **Hard Constraints** | 16 | 14 | +2 implementati, alcuni parziali |
| **Soft Constraints** | 4 | 10 | -6 non implementati |
| **Special Rules** | 3 | 7 | -4 non implementati |
| **TOTALE** | **23** | **31** | **-8 vincoli mancanti** |

---

## ✅ VINCOLI HARD IMPLEMENTATI (16)

### Completamente Implementati

| ID | Nome | Dove | Note |
|----|------|------|------|
| **H01** | Trainer Total Hours | `optimizer_V6.py:621-646` | Budget ore formatrici con accorpamenti |
| **H02** | Max One Meeting/Week | `optimizer_V6.py:369-379` | `AddAllDifferent` su settimane |
| **H03** | Lab 8 Must Be Last | `optimizer_V6.py:411-424` | Presentazione Manuali ultimo |
| **H04** | Lab Sequencing | `optimizer_V6.py:393-409` | Sequenzialità laboratori (OR logic) |
| **H07** | Class Excluded Dates | `domain_preprocessor.py:93-100` | Gestito nel preprocessor |
| **H08** | Scheduling Period | `domain_preprocessor.py:259-273` | Settimane 0-15 con vincoli speciali |
| **H09** | No Trainer Overlap | `optimizer_V6.py:747-816` | Iterativo con risoluzione conflitti |
| **H10** | Max Group Size | `optimizer_V6.py:323-328` | Max 1 accorpamento per classe-lab |
| **H11** | Lab Completion | Implicito | Ogni incontro schedulato |
| **H13** | Fixed Dates | `optimizer_V6.py:503-527` | Date fissate GSSI/esterni |
| **H14** | Trainer Availability | `optimizer_V6.py:529-619` | Disponibilità formatrice (giorni + slot specifici) |

### Vincoli Speciali Calendario

| Vincolo | Dove | Descrizione |
|---------|------|-------------|
| **Vincolo Inizio** | `optimizer_V6.py:331-337` | Settimana 0 solo da giovedì |
| **Vincolo Pasqua** | `optimizer_V6.py:348-355` | Settimana 9 solo fino a mercoledì |
| **Vincolo Fine** | `optimizer_V6.py:339-346` | Settimana 15 solo fino a giovedì |
| **Vincolo Sabato** | `optimizer_V6.py:357-367` | Solo formatrice 4 (Margherita) |
| **GSSI Weeks** | `optimizer_V6.py:488-501` | Esclude settimane lab esterni |

### Vincoli Ordinamento

| Vincolo | Dove | Descrizione |
|---------|------|-------------|
| **Ordinamento Incontri** | `optimizer_V6.py:381-391` | Incontri stesso lab in ordine |

---

## ❌ VINCOLI HARD NON/PARZIALMENTE IMPLEMENTATI

| ID | Nome | Status | Note |
|----|------|--------|------|
| **H05** | Lab Time of Day | ❌ NON implementato | dettagli="mattina"/"pomeriggio" ignorato |
| **H06** | Class Time Slots | ⚠️ PARZIALE | Gestito nel preprocessor ma non "hard" se preferenza≠"disponibile" |
| **H12** | Lab 9 Before Lab 5 | ❌ NON implementato | Sequenza 9→5 non forzata |

---

## ✅ VINCOLI SOFT IMPLEMENTATI (4)

| ID | Nome | Dove | Peso | Note |
|----|------|------|------|------|
| **S01** | Maximize Grouping | ❌ NON in obiettivo | N/A | Solo variabili, no incentivo |
| **S02** | Trainer Continuity | `optimizer_V6.py:653-676` | 100 | Continuità formatrice per classe |
| **S03** | Preferred Grouping | `optimizer_V6.py:678-686` | 50 | Accorpamenti preferenziali |
| **S04** | Fifth Year Priority | `optimizer_V6.py:688-701` | 10 | Classi quinte prima (inverted week) |
| **S05** | Lab Sequence | `optimizer_V6.py:703-725` | 20 | Ordine ideale: 7→9→4→5 |

**Nota critica**: **S01 (Maximize Grouping)** non è nell'obiettivo! Le variabili `accorpa` esistono ma non sono incentivate, quindi il solver non ha motivo di massimizzare gli accorpamenti.

---

## ❌ VINCOLI SOFT NON IMPLEMENTATI (6)

| ID | Nome | Descrizione |
|----|------|-------------|
| **S06** | Trainer Weekly Hours | Rispettare media settimanale |
| **S07** | Trainer Time Preference | Preferenza mattina/pomeriggio formatrice |
| **S08** | Time Slot Variation | Ruotare fasce orarie consecutive |
| **S09** | Balance Trainer Load | Distribuire carico tra settimane |
| **S10** | Minimize Late May | Preferire scheduling anticipato |

---

## 🔧 REGOLE SPECIALI

### Implementate (3)

| ID | Nome | Dove | Note |
|----|------|------|------|
| **SP06** | Ignore External Labs | `optimizer_V6.py:149-153` | Filtra lab GSSI (1,2,3,6,11) |
| **SP07** | Saturday Only Margherita | `optimizer_V6.py:357-367` | Vincolo H7 implementato |
| **GSSI Blocking** | `optimizer_V6.py:156-170` | Settimane occupate da lab esterni |

### NON Implementate (4)

| ID | Nome | Descrizione |
|----|------|-------------|
| **SP01** | Citizen Science Gap | Settimana vuota tra incontro 2 e 4 (autonomo) |
| **SP02** | Partial Lab Meetings | "solo 1 incontro", "solo 2 incontri" |
| **SP03** | Multi-Afternoon Non-Consecutive | N incontri pomeriggio non consecutivi |
| **SP04** | One Meeting Time | Almeno 1 incontro in fascia specifica |

---

## 🔍 ANALISI DETTAGLIATA

### 1. Vincoli nel Preprocessor (`domain_preprocessor.py`)

Il preprocessor riduce i domini **prima** di creare le variabili:

```python
Vincoli gestiti nel preprocessing:
- H06: Fasce orarie disponibili per classe  (linea 186-299)
- H07: Date escluse per classe              (linea 93-100)
- H08: Finestra scheduling (28/1 - 16/5)    (linea 259-273)
- GSSI: Settimane occupate                  (linea 99-100)
```

**Limitazione**: I vincoli nel preprocessor sono "soft" perché:
- Se `preferenza ≠ "disponibile"` in `fasce_orarie_classi.csv`, le fasce sono preferenze, non vincoli
- Il solver può comunque assegnare slot fuori dal dominio ridotto (se necessario)

### 2. Accorpamenti - Problema Critico ⚠️

```python
# PROBLEMA: Accorpamenti non massimizzati!
# Le variabili esistono:
self.accorpa[(c1, c2, lab_id)] = self.model.NewBoolVar(...)

# Ma NON sono nell'obiettivo:
objective_terms = [
    # S1: Continuità formatrice
    # S1b: Accorpamenti preferenziali
    # S2: Quinte prima
    # S3: Ordine ideale
]
# ❌ MANCA: incentivo a massimizzare accorpa[(c1,c2,lab)]
```

**Conseguenza**: Il solver crea accorpamenti **solo se forced da altri vincoli**, non per ottimizzare il budget ore!

### 3. Ordinamento Laboratori

```python
# Ordine HARD (H4): Tutti i lab devono essere sequenziali
# Ordine SOFT (S3): Preferenza per sequenza 7→9→4→5
ORDINE_IDEALE_LAB = {7: 1, 9: 2, 4: 3, 5: 4}
```

**Gap**: Lab 9 prima di Lab 5 **dovrebbe essere HARD** (secondo INTERPRETAZIONE_VINCOLI.md), ma è solo SOFT in S3.

### 4. Vincoli Formatrice

```python
# H14 implementato in due modalità:

# Modalità 1: date_disponibili specificate
if slot_specifici is not None:
    # WHITELIST: SOLO questi slot
    self.model.AddForbiddenAssignments(...)  # Vieta tutti gli altri

# Modalità 2: mattine/pomeriggi disponibili
else:
    # BLACKLIST: Vieta combinazioni non disponibili
    self.model.AddForbiddenAssignments(...)
```

**Implementazione corretta** secondo INTERPRETAZIONE_VINCOLI.md.

### 5. Budget Ore

```python
# Budget corretto con accorpamenti:
ore_effettive = sum(contributi) - sum(duplicati)

# contributi: ore * is_formatrice per ogni incontro
# duplicati: ore * accorpa * is_formatrice per incontri secondi
```

**Implementazione corretta**: Gli incontri accorpati contano una sola volta per la formatrice.

---

## 📈 CONFRONTO CON SISTEMA STRUTTURATO

### Mappatura ID

| Sistema Strutturato | Optimizer V6 | Status |
|---------------------|--------------|--------|
| H01 | Budget ore formatrici | ✅ Implementato |
| H02 | H2: Max 1/settimana | ✅ Implementato |
| H03 | H13: Date fissate | ✅ Implementato |
| H04 | H4: Sequenzialità | ✅ Implementato |
| H05 | - | ❌ NON implementato |
| H06 | Preprocessor | ⚠️ Parziale |
| H07 | H12: Date escluse | ✅ Nel preprocessor |
| H08 | H2 | ✅ Implementato |
| H09 | H3: Lab 8 ultimo | ✅ Implementato |
| H10 | H9: No overlap | ✅ Iterativo |
| H11 | H11: Periodo scheduling | ✅ Preprocessor |
| H12 | H1b: Max group size | ✅ Implementato |
| H13 | Implicito | ✅ Implementato |
| H14 | - | ❌ NON implementato |
| S01 | - | ❌ NON nell'obiettivo! |
| S02 | S1: Continuità | ✅ Implementato |
| S03 | - | ❌ NON implementato |
| S04 | - | ❌ NON implementato |
| S05 | S1b: Acc. pref. | ✅ Implementato |
| S06 | S3: Ordine ideale | ✅ Implementato |
| S07 | S2: Quinte prima | ✅ Implementato |
| S08 | - | ❌ NON implementato |
| S09 | - | ❌ NON implementato |
| S10 | - | ❌ NON implementato |

---

## 🎯 VINCOLI CRITICI MANCANTI

### 1. **S01: Maximize Grouping** ⚠️ CRITICO

```python
# DA AGGIUNGERE all'obiettivo:
for (c1, c2, lab_id), acc_var in self.accorpa.items():
    objective_terms.append(PESO_ACCORPAMENTO * acc_var)  # es. peso 1000
```

**Impatto**: Senza questo, il budget ore potrebbe essere superato!

### 2. **SP01: Citizen Science Gap** ⚠️ IMPORTANTE

```python
# DA AGGIUNGERE per lab 4 in scuole specifiche:
if lab_id == 4 and school_name in CITIZEN_SCIENCE_SCHOOLS:
    # Gap di 1 settimana tra incontro 2 e 4
    self.model.Add(
        self.settimana[(classe_id, 4, 3)] >=
        self.settimana[(classe_id, 4, 1)] + 2
    )
```

### 3. **H05: Lab Time of Day** ⚠️ IMPORTANTE

```python
# DA AGGIUNGERE per dettagli specifici:
if dettagli == "mattina":
    self.model.Add(self.fascia[key] <= 2)  # Solo fascia 1 o 2
elif dettagli == "pomeriggio":
    self.model.Add(self.fascia[key] == 3)  # Solo fascia 3
```

### 4. **SP02-SP04: Dettagli Laboratorio**

Parsing del campo `dettagli` in `laboratori_classi.csv` per:
- "solo N incontri"
- "N incontri pomeriggio non consecutivi"
- "un incontro pomeriggio"

---

## 💡 RACCOMANDAZIONI

### Priorità Alta (MUST HAVE)

1. ✅ **Aggiungere S01 (Maximize Grouping) all'obiettivo**
   - Peso molto alto (es. 1000) per incentivare accorpamenti
   - Critico per rispettare budget ore

2. ✅ **Implementare SP01 (Citizen Science Gap)**
   - Richiesto da scuole specifiche
   - Settimana autonoma tra incontro 2 e 4

3. ✅ **Implementare H05 (Lab Time of Day)**
   - Parsing campo `dettagli` in `laboratori_classi.csv`
   - Vincolo HARD su fascia mattina/pomeriggio

### Priorità Media (SHOULD HAVE)

4. ✅ **Implementare SP02 (Partial Lab Meetings)**
   - "solo 1 incontro", "solo 2 incontri"

5. ✅ **Rendere H12 HARD** (Lab 9 prima di Lab 5)
   - Attualmente è soft in S3

6. ✅ **Implementare SP03-SP04** (Requisiti pomeriggio)
   - Parsing dettagli complessi

### Priorità Bassa (NICE TO HAVE)

7. Implementare vincoli soft mancanti (S06-S10)
8. Aggiungere metriche di qualità soluzione
9. Export vincoli violati nel report

---

## 📊 STATISTICHE IMPLEMENTAZIONE

```
Vincoli implementati:     23 / 31  (74%)
Vincoli HARD:             16 / 14  (114% - alcuni extra)
Vincoli SOFT:              4 / 10  (40%)
Vincoli SPECIAL:           3 / 7   (43%)

Critici mancanti:          3 (S01, SP01, H05)
Importanti mancanti:       3 (SP02-SP04)
Nice-to-have mancanti:     6 (S06-S10, H12 upgrade)
```

---

## 🔗 Riferimenti

- **Implementazione**: `src/optimizer_V6.py`
- **Preprocessing**: `src/domain_preprocessor.py`
- **Specifica completa**: `INTERPRETAZIONE_VINCOLI.md`
- **Sistema strutturato**: `src/constraints/`

---

**Conclusione**: L'optimizer V6 implementa la maggior parte dei vincoli HARD fondamentali, ma manca di alcuni vincoli CRITICI (soprattutto S01 per gli accorpamenti) e di parsing completo dei dettagli laboratori. È necessario aggiungere almeno i vincoli di priorità ALTA prima di considerare il sistema completo.
