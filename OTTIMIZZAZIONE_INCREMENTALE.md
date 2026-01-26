# Piano: Ottimizzatore Incrementale da Zero

## 1. Analisi File CSV

### Entita (Master Data)

| File | Records | Chiave Primaria | Descrizione |
|------|---------|-----------------|-------------|
| `scuole.csv` | 13 | scuola_id | Scuole con preferenze orario e disponibilita sabato |
| `classi.csv` | 87 | classe_id | Classi con anno e priorita, FK: scuola_id |
| `formatrici.csv` | 4 | formatrice_id | Formatrici con ore max settimanali, giorni disponibili, preferenze fasce |
| `laboratori.csv` | 6 | laboratorio_id | Laboratori FOP con num_incontri, ore_per_incontro, sequenza |
| `fasce_orarie_scuole.csv` | 39 | (scuola_id, fascia_id) | 3 fasce mattutine per scuola (mapping per output finale) |

### Relazioni (Vincoli)

| File | Records | Chiavi | Descrizione |
|------|---------|--------|-------------|
| `laboratori_classi.csv` | 349 | (classe_id, laboratorio_id) | Quali lab deve fare ogni classe + date_fissate + dettagli |
| `formatrici_classi.csv` | 88 | (formatrice_id, classe_id) | Quale formatrice segue quale classe |
| `fasce_orarie_classi.csv` | 87 | classe_id | Quali fasce sono disponibili per ogni classe |
| `date_escluse_classi.csv` | 22 | classe_id | Date in cui una classe non e disponibile |

### Schema ER Semplificato

```
scuole (1) ──── (M) classi ──── (M) laboratori_classi ──── (1) laboratori
   │                 │
   │                 ├──── (1) formatrici_classi ──── (1) formatrici
   │                 │
   │                 ├──── (1) fasce_orarie_classi
   │                 │
   │                 └──── (1) date_escluse_classi
   │
   └──── (M) fasce_orarie_scuole
```

---

## 2. Vincoli con Fonti

### Fonte: `criteri.xlsx` foglio "criteri generali"

#### Periodo Calendario (righe 33-34)
- **Blocco 1**: 28/1/2026 - 1/4/2026 (9 settimane)
- **GAP Pasqua**: 2/4 - 12/4/2026 (no attivita)
- **Blocco 2**: 13/4/2026 - 16/5/2026 (5 settimane)
- **Totale**: ~14 settimane effettive

#### Vincoli Hard (obbligatori)

| ID | Vincolo | Fonte | Dettaglio |
|----|---------|-------|-----------|
| H1 | Ogni classe completa tutti i suoi laboratori | `laboratori_classi.csv` | sum(incontri) == num_incontri per ogni (classe, lab) |
| H1b | Accorpamenti: max 2 classi per incontro | criteri riga 25 | Classi della stessa scuola possono fare lab insieme |
| H2 | Max 1 incontro/settimana per classe | criteri riga 25 | "ogni classe puo avere massimo un incontro a settimana" |
| H3 | Presentazione manuali ULTIMO | criteri righe 15, 17 | "questo deve essere l'ultimo laboratorio che fa ogni classe" |
| H4 | Sequenzialita lab | criteri riga 26 | "prima di iniziare un nuovo laboratorio e necessario aver concluso quello precedente" |
| H5 | Giorni lavoro: lun-ven | criteri riga 23 | "da lunedi a venerdi" |
| H6 | Sabato: solo 2 scuole | criteri riga 23 | "tranne due scuole che possono lavorare anche il sabato" |
| H7 | Sabato: solo 1 formatrice | criteri riga 23 | "solo una formatrice puo lavorare il sabato" |
| H8 | Citizen Science 3° incontro autonomo | criteri riga 14 | Solo in: Potenza, Vasto, Bafile, Lanciano, Peano Rosa |
| H9 | No sovrapposizioni formatrice | implicito | Una formatrice non puo essere in 2 posti contemporaneamente |
| H10 | Fasce generiche globali | implicito | 3 fasce generiche: mattino1, mattino2, pomeriggio |
| H11 | Fasce disponibili per classe | `fasce_orarie_classi.csv` | Ogni classe specifica quali fasce puo usare (subset di {mattino1, mattino2, pomeriggio}) |

**NOTA:** Il vincolo "formatrice max 1 citta per giorno" NON e necessario perche i corsi sono **totalmente online**.
| H12 | Date escluse per classe | `date_escluse_classi.csv` | Alcune classi non disponibili in certe date |
| H13 | Date fissate | `laboratori_classi.csv` colonna date_fissate | Alcuni incontri gia schedulati |
| H14 | Disponibilita giorni formatrice | `formatrici.csv` colonna giorni_disponibili | Ogni formatrice lavora solo certi giorni |
| H15 | Budget ore formatrice (upper bound) | `formatrici.csv` colonna ore_generali | Ogni formatrice non puo superare le ore stanziate: ore_usate ≤ ore_max |

#### Vincoli Soft (obiettivo da minimizzare/massimizzare)

| ID | Vincolo | Fonte | Dettaglio |
|----|---------|-------|-----------|
| S1 | Continuita formatrice | criteri riga 18 | "idealmente ogni formatrice dovrebbe seguire una stessa classe per tutti i laboratori" |
| S1b | Accorpamenti preferenziali | `classi.csv` colonna accorpamento_preferenziale | Se possibile, accorpare con la classe indicata |
| S2 | Classi quinte prioritarie | criteri riga 28 | "le classi quinte devono finire le attivita il prima possibile" |
| S3 | Ordine ideale lab | criteri riga 26 | "idealmente: sensibilizzazione - citizen science - orientamento" |
| S4 | Disponibilita formatrici per fascia | `formatrici.csv` mattine_disponibili, pomeriggi_disponibili | Giorni disponibili per mattina (mattino1/2) e pomeriggio |
| S5 | Preferenze orario scuole | `scuole.csv` colonna preferenza_orario | mattina/pomeriggio/misto (tutte "misto") |
| S6 | Massimizzare utilizzo ore formatrici | `formatrici.csv` colonna ore_generali | Le formatrici vengono pagate per le ore stanziate, quindi idealmente vanno usate tutte |

**NOTA IMPORTANTE - Semplificazione Fasce Orarie:**
Le fasce orarie sono state semplificate a **3 fasce generiche globali**:
- **mattino1**: prima fascia mattutina (es: 8-10)
- **mattino2**: seconda fascia mattutina (es: 9-11 o 10-12)
- **pomeriggio**: fascia pomeridiana (es: 14-16)

Le fasce specifiche in `fasce_orarie_scuole.csv` (8-10, 9-11, 10-12) servono solo per il **mapping in fase di output** quando si produce il calendario finale. Durante l'ottimizzazione si usano solo le 3 fasce generiche.

**Vantaggi della semplificazione:**
- Riduzione ~75% delle variabili booleane (da ~12+ fasce a 3)
- Vincoli H9, H10, H11 molto più semplici
- Solver più veloce e scalabile
- Gestione preferenze formatrici e classi più chiara

---

## 3. Piano Implementativo

### `src/optimizer_V0.py` - Minimo Assoluto
**Variabili:**
```python
assignment[classe_id, lab_id, settimana] = BoolVar
```

**Vincoli implementati:**
- H1: Ogni classe completa ogni lab (sum == num_incontri)
- H2: Max 1 incontro/settimana per classe
- Periodo: 14 settimane (con gap Pasqua)

**Semplificazioni:**
- Ignora formatrici (assegnate dopo)
- Ignora fasce orarie (solo settimane)
- Ignora giorni specifici

**Output:** Per ogni classe, lista di (lab, settimana)

---

### `src/optimizer_V1.py` - Aggiunge Formatrici + Accorpamenti
**Variabili:**
```python
solo[classe_id, lab_id, formatrice_id, settimana] = BoolVar      # classe fa lab da sola
insieme[c1, c2, lab_id, formatrice_id, settimana] = BoolVar      # 2 classi insieme (c1 < c2)
```

**Vincoli implementati:**
- H1: Ogni classe completa ogni lab (solo + insieme)
- H1b: Accorpamenti tra classi della stessa scuola (max 2)
- H2: Max 1 incontro/settimana per classe
- H15: Budget ore formatrice (upper bound): ore_usate ≤ ore_max
  - Gli incontri 'insieme' contano 1x, non 2x (riducono ore necessarie)

**Note:**
- `classi.csv` colonna `accorpamento_preferenziale`: preferenze (soft, per V5)
- Qualsiasi coppia di classi della stessa scuola puo essere accorpata
- Gli accorpamenti riducono le ore totali necessarie

---

### `src/optimizer_V2.py` - Aggiunge Fasce Orarie e Giorni
**Variabili:**
```python
solo[classe, lab, formatrice, settimana, giorno, fascia] = BoolVar
insieme[c1, c2, lab, formatrice, settimana, giorno, fascia] = BoolVar
# dove fascia in {mattino1, mattino2, pomeriggio}  <- SOLO 3 VALORI!
```

**Vincoli aggiuntivi:**
- H5: Giorni lavoro lun-ven
- H6: Sabato solo 2 scuole
- H7: Sabato solo 1 formatrice
- H9: No sovrapposizioni formatrice (stesso giorno+fascia) - molto più semplice con 3 fasce
- H10: Fasce generiche globali (sempre soddisfatto)
- H11: Fasce disponibili per classe (verificare fascia in fasce_disponibili[classe])

**Note:**
- La riduzione da ~12+ fasce a 3 fasce riduce drasticamente lo spazio di ricerca
- Le preferenze formatrici si verificano controllando:
  - Se fascia = mattino1 o mattino2: giorno in mattine_disponibili[formatrice]
  - Se fascia = pomeriggio: giorno in pomeriggi_disponibili[formatrice]

---

### `src/optimizer_V3.py` - Aggiunge Date
**Vincoli aggiuntivi:**
- H12: Date escluse per classe
- H13: Date fissate (pre-scheduled)

---

### `src/optimizer_V4.py` - Aggiunge Sequenzialita
**Vincoli aggiuntivi:**
- H3: Presentazione manuali sempre ultimo
- H4: Sequenzialita laboratori (concludere prima di iniziare nuovo)
- H8: Citizen Science 3° incontro autonomo (gap settimana)

---

### `src/optimizer_V5.py` - Aggiunge Ottimizzazione
**Vincoli soft (obiettivo):**
- S1: Minimizza cambi formatrice per classe
- S2: Classi quinte finiscono prima
- S3: Ordine ideale lab (sensibilizzazione → citizen → orientamento)
- S4: Rispetta preferenze orario formatrici
- S5: Rispetta preferenze orario scuole
- S6: Massimizza utilizzo ore formatrici (usare più ore possibili del budget)

---

### `src/optimizer_V6.py` - Versione Finale Completa
Integrazione di tutti i vincoli + raffinamenti finali + test completi

---

## 4. Verifica

Per ogni fase:
1. Eseguire optimizer con dati completi
2. Verificare che trovi soluzione
3. Validare output: controllare che vincoli siano rispettati
4. Se fallisce, analizzare conflitti e rilassare vincoli

---

## 5. Note Implementative

### Mapping Fasce Generiche -> Fasce Specifiche (Output)

Durante l'ottimizzazione usiamo solo 3 fasce generiche: {mattino1, mattino2, pomeriggio}.
In fase di output finale, mappiamo queste fasce alle fasce specifiche:

```python
# Mapping per output:
mattino1 -> prima fascia mattutina della scuola da fasce_orarie_scuole.csv (es: fascia_id=1, 8-10)
mattino2 -> seconda fascia mattutina della scuola da fasce_orarie_scuole.csv (es: fascia_id=2, 9-11)
pomeriggio -> FISSO: 14:00-16:00 per tutte le scuole
```

**Nota**: La fascia pomeridiana è unica e fissa (14-16). Gli orari esatti verranno modificati manualmente dopo l'export se necessario.

### Mapping Settimane -> Date Reali
```
Settimana 1:  28/1 - 1/2/2026
Settimana 2:  2/2 - 8/2/2026
...
Settimana 9:  23/3 - 29/3/2026
Settimana 10: 30/3 - 1/4/2026
--- GAP PASQUA: 2/4 - 12/4/2026 ---
Settimana 11: 13/4 - 19/4/2026
...
Settimana 14: 4/5 - 10/5/2026
Settimana 15: 11/5 - 16/5/2026
```

### Scuole con Sabato Disponibile
Da verificare in scuole.csv quali hanno `sabato_disponibile = si`

### Formatrice che Lavora Sabato
Da verificare in formatrici.csv quale ha `lavora_sabato = si`

### Budget Ore Formatrici (Vincoli H15 + S6)
Valori da criteri.xlsx (ore_generali, NON ore_settimanali_max × settimane):
- Anita: 292 ore
- Andreea: 128 ore
- Ida: 160 ore
- Margherita: 128 ore
- **Totale budget: 708 ore**

**Vincolo H15 (hard):** Ogni formatrice non può superare le ore stanziate: `ore_usate ≤ ore_max`

**Vincolo S6 (soft, per V5):** Massimizzare utilizzo ore formatrici.
- Le formatrici vengono pagate per le ore stanziate, quindi idealmente vanno usate tutte
- Implementazione: aggiungere termine nella funzione obiettivo che penalizza ore non usate

Ore necessarie senza accorpamenti: ~962 ore (INFEASIBLE)
Con accorpamenti: ore ridotte perche incontri 'insieme' contano 1x

### Accorpamenti
- **Hard constraint**: max 2 classi per incontro, solo stessa scuola
- **Soft constraint**: preferenze in `classi.csv` colonna `accorpamento_preferenziale`
- Coppie preferenziali: 13 (26 classi su 87)
- Coppie possibili (stessa scuola): ~200+

