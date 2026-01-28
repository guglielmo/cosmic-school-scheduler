# Report Analisi Vincoli - Calendario Cosmic School V2

**Data**: 22 Gennaio 2026
**Analisi**: Dati da "criteri per calendario_v2.xlsx"

---

## 📊 RIEPILOGO DATI

### Dimensioni Problema
- **87 classi** da 13 scuole diverse
- **10 laboratori totali**:
  - 5 gestiti da **formatrici interne** (citizen science, orientamento, discriminazioni genere, presentazione manuali, discriminazioni pt.2)
  - 5 gestiti da **enti esterni** GSSI/GST/LNGS (introduzione fisica, costruzione rivelatori, formazione rilevazioni, orientamento STEM esperti)
- **4 formatrici** disponibili
- **Periodo**: Gennaio-Maggio (20 settimane)

### Ore Richieste vs Disponibili

| Formatrice | Ore/settimana | Ore totali (20 sett) |
|------------|---------------|----------------------|
| Anita      | 18.0          | 360                  |
| Andreea    | 8.0           | 160                  |
| Ida        | 10.0          | 200                  |
| Margherita | 8.0           | 160                  |
| **TOTALE** | **44.0**      | **880**              |

**Ore richieste calcolate**: 962 ore (solo per laboratori formatrici)

---

## 🚨 PROBLEMI CRITICI

### 1. DEFICIT DI ORE - PRIORITÀ MASSIMA ⚠️

```
Ore disponibili formatrici:  880 ore
Ore richieste (stimate):     962 ore
DEFICIT:                     -82 ore (9.3% in più del disponibile)
```

**Implicazione**: Il problema potrebbe **non avere soluzione** con i dati attuali.

**Cause possibili**:
- Alcune classi fanno più laboratori di altre (2-7 laboratori per classe)
- Il foglio `laboratori_classi` contiene 347 righe (non tutte le classi fanno tutti i laboratori)
- Media laboratori per classe: 4.0

**Verifica necessaria**:
- [ ] Controllare se il calcolo tiene conto che non tutte le classi fanno tutti i laboratori
- [ ] Verificare se alcune formatrici possono aumentare le ore settimanali
- [ ] Valutare se alcuni laboratori possono essere ridotti (es. da 5 a 4 incontri)

---

### 2. CLASSI SENZA FORMATRICE ASSEGNATA

**20 classi su 87** (23%) non hanno una formatrice pre-assegnata nel foglio `formatrici_classi`:

| Classe ID | Nome Classe |
|-----------|-------------|
| 9         | 3BLSA       |
| 12        | 3IA         |
| 17        | 4InA        |
| 18        | 5AtIA       |
| 43        | 3AS         |
| 44        | 3ESA        |
| 48        | 4AS-SAA     |
| 49        | 4CS         |
| 51        | 4ESA        |
| 55        | 3A-SAA      |
| ... e altre 10 classi |

**Domanda**: Queste classi devono:
- A) Essere assegnate manualmente da Elena (aggiornare il file Excel)?
- B) Essere assegnate automaticamente dall'optimizer?

---

### 3. DISTRIBUZIONE CARICO FORMATRICI - SBILANCIATA

| Formatrice | Classi Assegnate | % del Totale | Ore Disponibili |
|------------|------------------|--------------|-----------------|
| Anita      | 40               | 60%          | 360             |
| Margherita | 17               | 25%          | 160             |
| Ida        | 15               | 22%          | 200             |
| Andreea    | 14               | 21%          | 160             |

**Note**:
- Anita ha 40 classi ma anche il doppio delle ore disponibili (18h/sett)
- Le percentuali si sovrappongono perché alcune classi potrebbero non essere nel foglio

**Domanda**: Questa distribuzione è intenzionale o va ribilanciata?

---

### 4. DATE GIÀ FISSATE - 96 VINCOLI HARD

**96 incontri** hanno già una data fissata (colonna "date giá fissate" in `laboratori_classi`).

**Esempi**:

| Classe | Laboratorio | Data Fissata |
|--------|-------------|--------------|
| 3A     | 1.0 (Introduzione fisica) | 26 febbraio 9-13 |
| 3C     | 1.0 (Introduzione fisica) | 26 febbraio 9-13 |
| 4B     | 2.0 (Costruzione) | 9 marzo 9-13, 10 marzo 9-13 |
| 4B     | 3.0 (Formazione) | 20 marzo mattina |
| 5D     | 8.0 (Presentazione manuali) | 28 febbraio 10-12 |

**Problemi da verificare**:
- [ ] Alcune date sono **prima del 19 gennaio** (inizio schedulazione)
- [ ] Formato date misto: "26 febbraio 9-13" vs "2025-01-15 00:00:00"
- [ ] Date multiple per stesso incontro (es. "9 marzo 9-13, 10 marzo 9-13")
- [ ] Questi incontri devono essere **esclusi dalla schedulazione** automatica o vanno comunque inclusi nel calendario finale?

---

### 5. DATE ESCLUSE PER CLASSE - 23 CLASSI

**23 classi** hanno date in cui NON possono fare incontri.

**Esempi formati trovati**:

| Classe | Date Escluse | Formato |
|--------|--------------|---------|
| 4B     | dal 2 al 6 marzo | Range testuale |
| 5B     | 2025-01-15 00:00:00 | Timestamp Excel |
| 5DNO   | 5 febbraio pomeriggio<br>11 febbraio pomeriggio<br>17 febbraio mattina e pomeriggio | Liste multiple con fasce |

**Problema**: Formati **non standardizzati** - serve parsing complesso o correzione dati.

**Domanda**: Si può standardizzare il formato in Excel? Es: "2026-03-02 a 2026-03-06" oppure "2026-02-05 pomeriggio"

---

### 6. FASCE ORARIE LIMITATE - 21 CLASSI CRITICHE

**21 classi** hanno solo **2-3 fasce orarie** disponibili (contro una media di 5.2).

**Esempi più restrittivi**:

| Classe | Scuola | Fasce Disponibili | N. Fasce |
|--------|--------|-------------------|----------|
| 4BNO   | Bafile L'Aquila | 6, 7 | 2 |
| 5DNO   | Bafile L'Aquila | 6, 7 | 2 |
| 3AS    | D'Aosta L'Aquila | 5, 7, 10 | 3 |
| 3ESA   | D'Aosta L'Aquila | 5, 7, 10 | 3 |

**Implicazione**:
- Con solo 2-3 fasce, è **molto difficile** evitare sovrapposizioni formatrici
- Se la formatrice è impegnata in quelle fasce, la classe rimane bloccata

**Domanda**: È possibile per queste scuole ampliare le fasce disponibili?

---

## 📋 VINCOLI COMPLESSI DA IMPLEMENTARE

### Già Implementati nell'Optimizer V2:
- ✅ Ogni classe completa i suoi laboratori
- ✅ Max 1 incontro/settimana per classe
- ✅ No sovrapposizioni formatrici nello stesso slot temporale
- ✅ Sequenzialità laboratori (es. lab N+1 dopo lab N)
- ✅ Fasce orarie per scuola
- ✅ Preferenze orarie formatrici (soft)

### Da Implementare (Nuovi Vincoli V2):
- ❌ **Assegnamento formatrice-classe**: 67 classi hanno formatrice pre-assegnata
- ❌ **Laboratori specifici per classe**: non tutte fanno tutti i lab (347 combinazioni)
- ❌ **Date già fissate**: 96 incontri con data/ora predefinita
- ❌ **Date escluse per classe**: 23 classi con date blackout
- ❌ **Fasce orarie specifiche per classe**: override rispetto alle fasce della scuola
- ❌ **Gestione laboratori esterni GSSI/GST/LNGS**: vincoli diversi (consecutività, ecc.)

---

## ⚙️ VINCOLI SPECIALI LABORATORI ESTERNI

I laboratori gestiti da **GSSI/GST/LNGS** hanno regole diverse:

### Laboratorio 2.0 - Costruzione Rivelatori
**Vincolo**: Richiede **2 giorni consecutivi**
- Esempio: "9 marzo 9-13, 10 marzo 9-13"
- In alcune scuole: mattina + pomeriggio stesso giorno
- In altre: due mattine consecutive

### Laboratorio 3.0 - Formazione e Rilevazioni
**Vincolo**: Deve essere **settimana consecutiva** rispetto al lab 2.0

### Laboratorio 4.0 - Citizen Science (5 incontri)
**Nota**: Il terzo incontro è **autonomo** (classe lavora da sola con docente interno)
- Serve indicare settimana libera per lavoro autonomo
- O schedulare solo 4 incontri con formatrice?

**Domanda**: Come gestire questi laboratori?
- A) Schedularli manualmente prima dell'optimizer?
- B) Implementare vincoli speciali nell'optimizer?
- C) Schedularli separatamente dopo i laboratori formatrici?

---

## 🔍 ANOMALIE DATI DA VERIFICARE

### 1. Fasce Orarie con Timestamp
Nel foglio `fasce_orarie`, alcune fasce hanno timestamp invece di orari:

| Fascia ID | Nome | Dovrebbe essere |
|-----------|------|-----------------|
| 1 | 2025-10-08 00:00:00 | 8-10 o 9-11? |
| 2 | 2025-11-09 00:00:00 | 9-11 o 11-13? |
| 3 | 2025-12-10 00:00:00 | 10-12? |

**Azione richiesta**: Correggere con orari reali (es. "9-11", "14-16")

### 2. Preferenze Fasce Formatrici
Formatrice **Ida** ha preferenza_fasce = `1.2` (dovrebbe essere "mattina", "pomeriggio", o "misto")

**Azione richiesta**: Verificare e correggere

### 3. Colonna Unnamed in Scuole
Il foglio `scuole` ha colonna "Unnamed: 3" con valori "ok" / "no" / NaN

**Domanda**: Cosa significa? Conferma/validazione?

---

## 🎯 DOMANDE PER ELENA

### Priorità Alta

1. **Come risolviamo il deficit di 82 ore?**
   - [ ] Alcune formatrici possono aumentare ore settimanali?
   - [ ] Alcuni laboratori possono essere ridotti (es. Citizen Science da 5 a 4 incontri)?
   - [ ] Possiamo estendere il periodo oltre 20 settimane?
   - [ ] Alcune classi possono fare >1 incontro/settimana?

2. **Le 20 classi senza formatrice assegnata: come procedere?**
   - [ ] Assegnarle manualmente (aggiornare Excel)
   - [ ] Lasciar decidere all'optimizer

3. **Date già fissate: vanno incluse nel calendario finale o sono già fuori?**
   - Se vanno incluse: come integrarle con ottimizzazione?
   - Se sono fuori: vanno comunque rispettate come vincoli di disponibilità?

### Priorità Media

4. **Laboratori GSSI/GST/LNGS: come gestirli?**
   - [ ] Schedularli prima dell'optimizer (manualmente)?
   - [ ] Integrarli nell'optimizer con vincoli speciali?
   - [ ] Schedularli dopo (separatamente)?

5. **Citizen Science (lab 4.0) - 3° incontro autonomo:**
   - [ ] Schedulare solo 4 incontri con formatrice?
   - [ ] Schedulare 5 incontri marcando il 3° come "autonomo"?

6. **Date escluse: possiamo standardizzare il formato?**
   - Proposta: "YYYY-MM-DD" per date singole, "YYYY-MM-DD a YYYY-MM-DD" per range
   - Specificare "mattina"/"pomeriggio" se necessario

### Priorità Bassa

7. **Correggere fasce orarie 1, 2, 3 con timestamp**
8. **Preferenza_fasce formatrice Ida: correggere "1.2"**
9. **Colonna "Unnamed: 3" nel foglio scuole: cosa significa?**

---

## 📈 PROSSIMI PASSI CONSIGLIATI

### Scenario A - Dati Corretti Prima
1. Elena corregge dati critici in Excel (ore, date, formati)
2. Ri-conversione CSV
3. Implementazione vincoli aggiuntivi in optimizer
4. Test con subset ridotto
5. Esecuzione completa

**Tempo stimato**: 2-3 giorni

### Scenario B - Test Parziale Subito
1. Implementare vincoli base con dati attuali
2. Test su subset ridotto (1 scuola) per validare approccio
3. Identificare problemi pratici
4. Correzione dati basata su risultati test
5. Implementazione completa

**Tempo stimato**: 3-4 giorni (più iterazioni)

---

## 💾 FILE GENERATI

Tutti i dati sono stati convertiti in CSV in `data/input/`:

**File Base:**
- `scuole.csv` (13 scuole)
- `classi.csv` (87 classi)
- `formatrici.csv` (4 formatrici)
- `laboratori.csv` (5 laboratori formatrici, esclusi GSSI/GST/LNGS)
- `fasce_orarie_scuole.csv` (156 righe: 13 scuole × 12 fasce)

**File Vincoli:**
- `date_escluse_classi.csv` (23 classi)
- `fasce_orarie_classi.csv` (87 classi)
- `formatrici_classi.csv` (86 assegnamenti)
- `laboratori_classi.csv` (347 combinazioni classe-laboratorio)

**Script Utili:**
- `convert_excel_to_csv.py` - Conversione Excel → CSV
- `analizza_vincoli.py` - Analisi vincoli e statistiche
- `create_test_subset.py` - Crea subset ridotti per testing

---

## 🔧 STATO OPTIMIZER

**Optimizer V2 Ottimizzato** (16 core):
- ✅ Funzionante su subset ridotto (1 scuola, 6 classi)
- ✅ Parallelizzazione attiva (16 core)
- ✅ Pre-calcolo indici per performance
- ⏱️ Tempo: ~2-3 minuti per subset 1 scuola
- ❌ Non ancora testato su dataset completo (87 classi)

**Vincoli Implementati**: Base (completamento, max 1/sett, sovrapposizioni, sequenzialità)
**Vincoli Mancanti**: Assegnamenti, date fissate, date escluse, fasce specifiche per classe

---

## 📞 CONTATTI

Per domande su questo report o l'analisi tecnica:
- Documentazione OR-Tools: https://developers.google.com/optimization
- Repository progetto: [percorso repo se disponibile]

---

**Fine Report**
