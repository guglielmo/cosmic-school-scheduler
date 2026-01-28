# Prossimi Passi per Dati Reali

Questo documento spiega come adattare l'ottimizzatore ai dati reali del progetto (69 classi, 12 scuole, 6 formatrici).

## 1. Preparare i Dati Reali

Devi creare 4 file CSV in `data/input/` con i dati veri:

### scuole.csv
```csv
scuola_id,nome,citta,preferenza_orario,sabato_disponibile
1,I.I.S. E. Mattei (ITI+IPS),Vasto,mattina,no
2,I.I.S. Lic. Scientifico e Artistico Bafile,L'Aquila,misto,no
...
```

**Campi:**
- `preferenza_orario`: mattina / pomeriggio / misto
- `sabato_disponibile`: si / no

### classi.csv
```csv
classe_id,nome,scuola_id,anno,priorita,laboratori_completati
1,4A,1,4,normale,"[]"
2,5B,1,5,alta,"[1,2]"
...
```

**Campi:**
- `anno`: 3, 4 o 5
- `priorita`: alta (per classi quinte) / normale
- `laboratori_completati`: lista ID laboratori già fatti (es: `[1,2]` o `[]`)

### formatrici.csv
```csv
formatrice_id,nome,ore_settimanali_max,lavora_sabato,giorni_disponibili
1,Formatrice A,20,no,"lun,mar,mer,gio,ven"
2,Formatrice B,20,si,"lun,mar,mer,gio,ven,sab"
...
```

### laboratori.csv
```csv
laboratorio_id,nome,num_incontri,ore_per_incontro,sequenza
1,Citizen Science,5,2,1
2,Discriminazioni di genere,2,2,2
3,Orientamento e competenze,2,2,3
4,Presentazione manuali,1,2,4
```

**Note:**
- `sequenza`: ordine di esecuzione (il lab 4 deve essere ultimo)
- Per Citizen Science: 5 incontri ma il 3° è autonomo (va indicato come settimana libera)

## 2. Vincoli Aggiuntivi da Implementare

Nel file `src/optimizer.py` dovrai aggiungere:

### Vincoli Hard
1. **Laboratori già completati**: se una classe ha `laboratori_completati = [1,2]`, non schedulare lab 1 e 2
2. **Periodo**: gennaio-maggio = settimane 1-20 circa (già implementato, ma serve calendario vacanze)
3. **Fasce orarie variabili**: ogni settimana fascia diversa per non gravare sugli stessi prof
4. **Preferenze orarie scuole**: rispettare `preferenza_orario` del CSV

### Vincoli Soft (da ottimizzare)
1. **Anticipo classi quinte**: preferire le prime settimane (prima di maggio)
2. **Minimizzare spostamenti geografici**: aggiungere matrice distanze tra scuole
3. **Stessa formatrice per classe**: già implementato ✓
4. **Bilanciamento ore**: già implementato parzialmente

## 3. Modifiche al Codice

### a) Lettura laboratori già completati
In `src/optimizer.py`, nella funzione `build_model()`, aggiungi:

```python
# Dopo il caricamento dati
import ast
for _, classe in self.classi.iterrows():
    labs_completati = ast.literal_eval(classe['laboratori_completati'])
    for lab_id in labs_completati:
        # Non creare variabili per questi laboratori
        pass
```

### b) Aggiungere calendario con vacanze
Crea `data/input/calendario.csv`:
```csv
settimana,data_inizio,data_fine,disponibile
1,2025-01-13,2025-01-17,si
2,2025-01-20,2025-01-24,si
...
10,2025-03-17,2025-03-21,no  # vacanze pasquali
...
```

### c) Matrice distanze geografiche
Per minimizzare spostamenti, aggiungi:
```python
# Penalità per distanza
distanze = {
    (1, 2): 50,  # Vasto - L'Aquila = 50km
    (1, 3): 80,  # Vasto - Teramo = 80km
    ...
}

# Nella funzione obiettivo
for formatrice in formatrici:
    for sett in settimane:
        # Se formatrice lavora in scuola A e B nella stessa settimana, penalizza
        pass
```

## 4. Parametri da Tuning

Nel codice attuale, questi parametri sono hardcoded ma potrebbero aver bisogno di aggiustamenti:

```python
num_settimane = 20              # Linea 37: gennaio-maggio
max_incontri_formatrice = 2     # Linea 132: max incontri/settimana
peso_continuita = 10            # Linea 179: peso cambio formatrice
timeout_solver = 120            # Linea 278: timeout in secondi
```

Con 69 classi e 6 laboratori, potrebbero servire:
- `timeout_solver = 600` (10 minuti)
- Più worker per parallelizzazione (già gestito da OR-Tools)

## 5. Testing Incrementale

**Strategia consigliata:**

1. **Fase 1**: Testa con 1 scuola (6-8 classi)
2. **Fase 2**: Testa con 3 scuole (~20 classi)
3. **Fase 3**: Dati completi (69 classi)

Per ogni fase:
```bash
# Modifica i CSV in data/input/
./optimize

# Verifica risultati in data/output/calendario_ottimizzato.xlsx
```

## 6. Debugging

Se il solver non trova soluzioni:

### Controlla vincoli impossibili
```python
# Calcola ore richieste totali
tot_ore = 69 classi × (5+2+2+1) incontri × 2 ore = 1380 ore

# Ore disponibili formatrici
tot_disponibili = 6 formatrici × 20 ore/sett × 20 sett = 2400 ore
# OK! Risorse sufficienti
```

### Rilassa vincoli temporaneamente
Per debugging, commenta temporaneamente:
- Vincolo sequenzialità (linea 81-138)
- Vincolo 1 incontro/settimana (linea 67-79)

E verifica se trova soluzioni.

## 7. Visualizzazioni Aggiuntive

Una volta funzionante, potresti aggiungere:

```bash
# Installa librerie visualizzazione
uv pip install matplotlib plotly openpyxl

# Aggiungi in src/visualizer.py
- Gantt chart per formatrice
- Mappa geografica spostamenti
- Grafico bilanciamento ore
```

## 8. Ottimizzazioni Performance

Se il solver è troppo lento (>10 minuti):

1. **Riduci orizzonte temporale**: invece di 20 settimane, ottimizza 5 settimane alla volta
2. **Decomposizione per scuola**: ottimizza scuole lontane separatamente
3. **Usa euristica iniziale**: fornisci una soluzione manuale come punto di partenza

## Contatti

Per domande o problemi:
- Documentazione OR-Tools: https://developers.google.com/optimization
- Issue tracker: github.com/google/or-tools

---

**Prossimo passo immediato**: Crea i 4 CSV con i dati reali e rilancia `./optimize`
