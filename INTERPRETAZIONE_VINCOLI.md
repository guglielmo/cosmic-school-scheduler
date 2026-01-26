# Interpretazione Corretta dei Vincoli - Calendario Cosmic School V2

**Aggiornato**: 22 Gennaio 2026
**Basato su**: "criteri per calendario_v2.xlsx" + chiarimenti utente

---

## 🏫 ENTITÀ BASE

### 1. Scuole (13 totali)
- Città
- Alcune possono lavorare il sabato (2 scuole)
- Preferenze mattina/pomeriggio/misto definite per classe, non per scuola

### 2. Classi (87 totali)
- Appartenenza a scuola
- Anno (3/4/5) → **Classi quinte hanno priorità alta**: finire prima possibile, non a maggio (SOFT)
- **Accorpamenti preferenziali** (colonna in Excel): SOFT preference per classi che facciano incontri insieme contemporaneamente
  - Es: classe 5B con 5C → preferire che facciano stesso lab nello stesso momento

### 3. Formatrici (4 totali)
Vincoli:

#### HARD Constraints
- **`ore_generali`**: Totale ore nel periodo (es: Anita = 292 ore) - DEVE essere rispettato
- **`mattine_disponibili`**: Giorni in cui può lavorare la mattina (es: "lun,mar,mer,gio,ven")
- **`pomeriggi_disponibili`**: Giorni in cui può lavorare il pomeriggio
- **`date_escluse_formatrici`**: Se presente → tutte le date OK TRANNE quelle elencate
- **`date_disponibili`**: Se presente → SOLO quelle date/orari sono OK (nient'altro)
  - Se entrambi vuoti → tutte le date disponibili
- **`lavora_sabato`**: Solo Margherita può lavorare il sabato

#### SOFT Constraints
- **`ore_settimanali (media)`**: Media ore/settimana (es: 18h) - cercare di rispettarla ma non vincolante
- **`preferenza_fasce`**: Preferenza mattina/pomeriggio/misto - rispettare quando possibile

### 4. Laboratori
**IMPORTANTE**: Considerare SOLO i 5 laboratori gestiti da **formatrici FOP**:
- 4.0 - Citizen Science (5 incontri da 2h)
- 5.0 - Orientamento e competenze (2 incontri da 2h)
- 7.0 - Sensibilizzazione discriminazioni di genere (2 incontri da 2h)
- 8.0 - Presentazione manuali (1 incontro da 2h)
- 9.0 - Sensibilizzazione discriminazioni di genere pt.2 (1 incontro da 2h)

**IGNORARE** laboratori GSSI/GST/LNGS (1.0, 1.1, 2.0, 3.0, 6.0) - gestiti da partner esterni

### 5. Fasce Orarie (12 totali)
Orari disponibili (es: 9-11, 14-16, 14.30-16.30, ecc.)

---

## 🔒 VINCOLI

### 🎯 VINCOLO CRITICO: Budget Ore

**Budget totale**: 708 ore (somma ore_generali delle 4 formatrici)

| Formatrice | Ore Totali |
|------------|-----------|
| Anita      | 292       |
| Andreea    | 128       |
| Ida        | 160       |
| Margherita | 128       |
| **TOTALE** | **708**   |

**Con accorpamenti max 2 classi**: 664 ore richieste → **+44 ore di margine** ✅

---

### HARD Constraints (devono essere rispettati sempre)

#### 1. Ore Totali Formatrici
- Ogni formatrice ha un totale ore (`ore_generali`) che DEVE essere rispettato
- La media settimanale è indicativa

#### 2. Disponibilità Temporale Formatrici
- `mattine_disponibili` e `pomeriggi_disponibili`: vincoli sui giorni
- `date_escluse_formatrici` o `date_disponibili`: vincoli sulle date specifiche
  - **Logica alternativa**:
    - Se `date_escluse` → tutte OK tranne quelle
    - Se `date_disponibili` → solo quelle OK
    - Se entrambi vuoti → tutte OK

#### 3. Date Già Fissate (SUPER HARD)
- Colonna `date giá fissate` in `laboratori_classi`
- Esempi: "26 febbraio 9-13", "9 marzo 9-13, 10 marzo 9-13"
- Sono date **già stabilite definitivamente**
- **L'optimizer deve**:
  - Considerarle come occupazione della classe in quella settimana
  - Rispettare vincolo "max 1 incontro/settimana" anche per date fissate
  - NON schedulare altri incontri per quella classe in quella settimana

#### 4. Laboratori Specifici per Classe
- Foglio `laboratori_classi` definisce quali lab fa ogni classe
- Una classe fa SOLO i laboratori elencati (non tutti i 5)
- Es: Classe 3A fa solo lab 1.0, 4.0, 5.0, 8.0

#### 5. Dettagli Laboratorio (mattina/pomeriggio)
- Colonna `dettagli_laboraotorio` in `laboratori_classi`
- Se specificato "mattina" o "pomeriggio" → HARD constraint su fascia oraria

#### 6. Fasce Orarie per Classe
- Foglio `fasce_orarie_classi`: definisce fasce disponibili per ogni classe
- **Campo `preferenza`**: se = "disponibile" → HARD constraint (solo quelle fasce)
- **Campo `giorni settimana`**: HARD constraint su disponibilità giorni (es: "da lun a giov")
- Esempio: Classe 4BNO può lavorare SOLO fasce 6,7 e SOLO da lunedì a giovedì

#### 7. Date Escluse per Classe
- Foglio `date_escluse_classi`
- Date in cui classe NON può avere incontri
- Formati misti da parsare: "dal 2 al 6 marzo", "2025-01-15 00:00:00", "5 febbraio pomeriggio"

#### 8. Max 1 Incontro/Settimana per Classe
- Ogni classe può avere massimo 1 incontro a settimana
- Vale anche considerando le date già fissate

#### 9. Laboratorio 8.0 (Presentazione Manuali)
- DEVE essere sempre l'ultimo laboratorio per ogni classe

#### 10. No Sovrapposizioni Formatrici
- Una formatrice non può essere in due posti contemporaneamente

#### 11. Periodo Schedulazione
- **Finestra 1**: 28/1/2026 a 1/4/2026
- **Finestra 2**: 13/4/2026 a 16/5/2026
- (Vacanze pasquali in mezzo)

#### 12. Accorpamenti Classi
**Vincolo generale**: Massimo **2 classi** possono essere accorpate per lo stesso incontro

**Vincolo speciale "insieme"** (NON applicabile ai lab formatrici):
- Solo Lab 1.0 e 1.1 (gestiti da GSSI/GST/LNGS - IGNORATI)
- Tutte le classi della scuola devono fare il lab contemporaneamente

**Per laboratori formatrici (4, 5, 7, 8, 9)**: max 2 classi insieme

**Condizioni accorpamento**:
- Stessa scuola
- Stesso laboratorio
- Stessa formatrice (se pre-assegnata)
- Stesso slot temporale (settimana + giorno + fascia)
- Fasce orarie compatibili per entrambe le classi
- Date disponibili compatibili per entrambe

---

### SOFT Constraints (preferenze da ottimizzare)

#### 1. Massimizzare Accorpamenti
- **PRIORITÀ ALTISSIMA**: gli accorpamenti sono essenziali per budget
- Preferire 2 classi insieme quando possibile (risparmia ore)
- **Peso**: MOLTO ALTO (es: bonus 20 per accorpamento)
- Con accorpamenti ottimali: 664 ore vs 926 ore singole

#### 2. Formatrice per Classe (da `formatrici_classi`)
- **NON è HARD**: è una preferenza
- "Idealmente ogni formatrice dovrebbe seguire una stessa classe per tutti i laboratori"
- Se non possibile, almeno per ogni "ciclo di laboratorio"
- **Peso**: ALTO (es: penalità 10 se cambia formatrice)

#### 3. Media Ore Settimanali Formatrici
- Cercare di stare vicini a `ore_settimanali (media)` ma non vincolante
- L'importante è rispettare `ore_generali` totali
- **Peso**: MEDIO

#### 4. Preferenza Fasce Formatrici
- Campo `preferenza_fasce` (mattina/pomeriggio/misto)
- Rispettare quando possibile ma non bloccante
- **Peso**: BASSO (es: penalità 1)

#### 5. Accorpamenti Preferenziali Classi
- Colonna `accorpamenti preferenziali (solo con classi della stessa scuola)` in `classi`
- Es: 5B indica "5C" → preferire che 5B e 5C facciano stesso lab insieme
- **Peso**: MEDIO (es: bonus 5 se accorpate)

#### 6. Sequenza Ideale Laboratori FOP
- Ordine preferito: Sensibilizzazione (7.0) → Citizen Science (4.0) → Orientamento (5.0)
- Lab 8.0 sempre ultimo (HARD)
- Lab 9.0 deve essere prima del lab 5.0
- **Peso**: BASSO

#### 7. Priorità Classi Quinte
- Finire attività il prima possibile
- Evitare maggio se possibile
- **Peso**: MEDIO (es: penalità crescente per settimane tardive)

#### 8. Variazione Fasce Orarie
- Evitare che classe faccia sempre stessa fascia ogni settimana
- **Peso**: BASSO (es: penalità 2 se stessa fascia in settimane consecutive)

---

## 🔧 VINCOLI SPECIALI

### Citizen Science (Lab 4.0) - 5 Incontri
**Scuole interessate**: Potenza, Vasto, Bafile, Lanciano, Peano Rosa

- Il lab ha 5 incontri ma il **3° è autonomo** (fatto dalla classe con proprio docente)
- **L'optimizer deve**:
  - Schedulare solo incontri 1, 2, 4, 5 (4 incontri con formatrice)
  - Lasciare **1 settimana vuota** tra incontro 2 e incontro 4
  - Quella settimana = incontro autonomo (non coinvolge formatrice)

**Implementazione**:
- Trattare Citizen Science come 4 incontri + 1 gap obbligatorio
- Vincolo: `settimana_incontro4 >= settimana_incontro2 + 2`

---

## 📊 CALCOLO ORE

### Ore Richieste (stimate)
```
Somma per ogni riga di laboratori_classi:
  ore = laboratorio.num_incontri × laboratorio.ore_per_incontro

Speciale per Citizen Science:
  - Se scuola in [Potenza, Vasto, Bafile, Lanciano, Peano Rosa]
  - Contare 4 incontri invece di 5 (il 3° è autonomo)
```

### Ore Disponibili
```
Somma per ogni formatrice:
  ore_totali = formatrice.ore_generali (NON ore_settimanali × 20)
```

---

## 🎯 FUNZIONE OBIETTIVO

```
Minimizza:
  - 20 × (accorpamenti realizzati)              # MASSIMIZZA accorpamenti!
  + 10 × (cambi formatrice per classe)
  + 5  × (mancati accorpamenti preferenziali)
  + 3  × (settimane tardive per classi quinte)
  + 2  × (stessa fascia in settimane consecutive)
  + 1  × (mismatch preferenza_fasce formatrice)
  - 2  × (rispetto sequenza ideale laboratori)
```

**Nota**: Il segno negativo per accorpamenti significa che MASSIMIZZIAMO (riduciamo la penalità quando accorpiamo)

---

## ✅ VERIFICHE COMPLETATE

1. **Budget ore**: 708 ore disponibili
2. **Ore richieste con accorpamenti max 2**: 664 ore → **+44 ore margine** ✅
3. **Accorpamenti necessari**: 129 gruppi da 2 + 46 singole
4. **Laboratori "insieme"**: Solo lab 1.0 e 1.1 (GSSI/GST/LNGS - ignorati)

## ❓ DOMANDE RIMANENTI

1. **Sabbato**: Quali sono le 2 scuole che possono lavorare il sabato?
   - Manca info esplicita nel foglio `scuole`
   - Solo Margherita può lavorare il sabato

2. **Formati date**: Possibile standardizzare in Excel per facilitare parsing?
   - `date_escluse_classi`: formati misti ("dal 2 al 6 marzo", "2025-01-15", "5 febbraio pomeriggio")
   - `date giá fissate`: formati misti ("26 febbraio 9-13", "9 marzo 9-13, 10 marzo 9-13")

---

**Fine Interpretazione**
