# Formato Output Excel

L'ottimizzatore genera un file Excel con **4 fogli** nel formato richiesto.

## Struttura File

### 1. Foglio "complessivo"
Calendario completo con tutte le informazioni per incontro.

**Colonne (16):**
- `Data`: Data dell'incontro (formato data)
- `Giorno Settimana`: Nome giorno in italiano (lunedì, martedì, ...)
- `Settimana`: Numero settimana ISO
- `Mese`: Numero mese (1-12)
- `Scuola`: Nome completo della scuola
- `Classe`: Nome classe (es: 4A, 5B)
- `Orario inizio`: Ora inizio in formato decimale (es: 9.0 = 09:00)
- `Orario fine`: Ora fine in formato decimale (es: 11.0 = 11:00)
- `Attività (macro)`: Codice attività (A3, A5, A6, A7)
- `Attività (micro)`: Descrizione attività completa
- `Partner`: Partner responsabile (FOP, GSSI-GST-LNGS, ecc.)
- `Nome formatore`: Nome formatrice
- `Durata attivitá`: Durata in ore
- `Modalitá erogazione`: Modalità (default: "formatore online")
- `INCONTRO FATTO`: Campo vuoto per compilazione manuale
- `MODULI POST ATTIVITA`: Campo vuoto per compilazione manuale

**Mappatura Attività:**
- Citizen Science → A3, "citizen science", FOP
- Discriminazioni di genere → A5, "sensibilizzazione discriminazioni di genere", FOP
- Orientamento e competenze → A6, "orientamento e competenze", FOP
- Presentazione manuali → A7, "presentazione manuali", FOP

### 2. Foglio "per_formatore_sett_data"
Vista per formatrice, ordinata per nome e data.

**Colonne (8):**
- `Nome formatore`: Nome formatrice
- `Settimana`: Numero settimana
- `Data`: Data incontro
- `Giorno Settimana`: Nome giorno
- `Scuola`: Nome scuola
- `Classe`: Nome classe
- `Attività (micro)`: Descrizione attività
- `MEDIAN di Orario inizio`: Orario medio di inizio

**Caratteristiche:**
- Include righe "Totale {Formatrice}" con statistiche aggregate
- Ordinato per: Nome formatore → Data

### 3. Foglio "per_scuola_per_Classe"
Vista per scuola e classe.

**Colonne (9):**
- `Scuola`: Nome scuola
- `Classe`: Nome classe
- `Settimana`: Numero settimana
- `Data`: Data incontro
- `Giorno Settimana`: Nome giorno
- `Attività (micro)`: Descrizione attività
- `Partner`: Partner responsabile
- `Nome formatore`: Nome formatrice
- `MEDIAN di Orario inizio`: Orario medio

**Ordinamento:** Scuola → Classe → Data

### 4. Foglio "per_scuola_per_data"
Vista per scuola ordinata per data.

**Colonne (9):**
- `Scuola`: Nome scuola
- `Settimana`: Numero settimana
- `Data`: Data incontro
- `Giorno Settimana`: Nome giorno
- `Classe`: Nome classe
- `Attività (micro)`: Descrizione attività
- `Partner`: Partner responsabile
- `Nome formatore`: Nome formatrice
- `MEDIAN di Orario inizio`: Orario medio

**Ordinamento:** Scuola → Data → Orario inizio

## Esempio Utilizzo

```bash
# Esegui ottimizzazione
./optimize-v2

# L'output sarà in:
data/output/calendario_v2_con_fasce.xlsx

# Apri con LibreOffice o Excel
libreoffice data/output/calendario_v2_con_fasce.xlsx
```

## Note Tecniche

### Calcolo Date
- Le date sono calcolate da: `numero_settimana + nome_giorno`
- Settimana 1 = prima settimana di gennaio 2025
- Usato standard ISO 8601 per numerazione settimane

### Orari
- Format decimale: 9.0 = 09:00, 14.5 = 14:30
- Estratti automaticamente dalle fasce orarie definite per scuola

### Nomi Giorni
- In italiano: lunedì, martedì, mercoledì, giovedì, venerdì, sabato, domenica
- Calcolati automaticamente dalla data

## Personalizzazione

Per modificare le mappature attività, modificare il file:
`src/export_formatter.py`

Linee ~66-73 per "attività macro e micro"
Linee ~94-101 per "attività micro" (solo descrizione)

## Validazione Output

Il formato è conforme all'esempio fornito in:
`calendario_esempio_output.xlsx`

Differenze previste:
- Date diverse (dipendono dall'ottimizzazione)
- Nomi scuole/classi/formatrici (dati di esempio vs reali)
- Numeri settimana (calcolati automaticamente)

Tutte le colonne, ordini e formati corrispondono all'esempio originale.
