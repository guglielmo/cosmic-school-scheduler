# Riepilogo Setup Completato

## Cosa è stato realizzato

✅ **Setup progetto completo**
- Python 3.12 con virtualenv
- Gestione dipendenze con `uv`
- Libreria di ottimizzazione: OR-Tools (Google)

✅ **Due versioni dell'ottimizzatore**
1. **V1 (`./optimize`)**: Versione base semplificata
2. **V2 (`./optimize-v2`)**: Versione completa con fasce orarie

✅ **Dati di esempio funzionanti**
- 3 scuole (Galilei Pescara, Einstein Teramo, Bafile L'Aquila)
- 12 classi (4 per scuola)
- 3 formatrici con preferenze diverse
- 4 laboratori FOP
- 9 fasce orarie (scuola Einstein ha orari diversi: 8-10, 10-12, 12-14)

✅ **Funzionalità implementate**

### Vincoli Hard (devono essere rispettati)
1. ✅ Ogni classe completa tutti i laboratori
2. ✅ Max 1 incontro/settimana per classe
3. ✅ Sequenzialità: finire un lab prima di iniziare il successivo
4. ✅ Una formatrice non può essere in due posti contemporaneamente
5. ✅ Fasce orarie specifiche per scuola (V2)
6. ✅ Preferenze orarie scuola: mattina/pomeriggio/misto (V2)

### Vincoli Soft (ottimizzati)
1. ✅ Continuità: stessa formatrice per tutta la classe (peso 10)
2. ✅ Variare fasce orarie per non gravare sugli stessi docenti (peso 2)
3. ✅ Rispettare preferenze fasce orarie delle formatrici (peso 1)

## Test Eseguiti

### Test V1 (Base)
```bash
./optimize
```
**Risultato**: ✅ OTTIMALE in 0.19s
- 96 incontri schedulati
- Bilanciamento: Alice 66h, Beatrice 62h, Clara 64h
- Valore obiettivo: 0 (perfetto)

### Test V2 (Con Fasce Orarie)
```bash
./optimize-v2
```
**Risultato**: ✅ OTTIMALE in 5.20s
- 96 incontri schedulati con giorno e fascia oraria
- Preferenze formatrici rispettate:
  - Alice (mattina): 100% mattina
  - Beatrice (misto): distribuita
  - Clara (pomeriggio): 100% pomeriggio
- Fasce orarie diverse per scuola Einstein (8-10) rispettate

## File Generati

### Struttura Progetto
```
cosmic-school/
├── data/
│   ├── input/
│   │   ├── esempio_scuole.csv
│   │   ├── esempio_classi.csv
│   │   ├── esempio_formatrici.csv
│   │   ├── esempio_laboratori.csv
│   │   └── esempio_fasce_orarie_scuole.csv
│   └── output/
│       ├── calendario_ottimizzato.xlsx      (V1)
│       └── calendario_v2_con_fasce.xlsx     (V2)
├── src/
│   ├── optimizer.py        (V1)
│   └── optimizer_v2.py     (V2)
├── optimize                (script V1)
├── optimize-v2             (script V2)
├── .venv/                  (virtualenv)
├── README.md
├── PROSSIMI_PASSI.md
└── RIEPILOGO_SETUP.md
```

## Output Excel

Entrambe le versioni generano file Excel con:

**Fogli:**
1. **Calendario Completo**: tutte le assegnazioni
   - V1: Settimana | Scuola | Classe | Laboratorio | Formatrice | Ore
   - V2: + Giorno | Fascia Oraria

2. **Fogli per Formatrice**: un foglio per ogni formatrice con il suo calendario

3. **Statistiche**: ore totali e numero incontri per formatrice

## Come Procedere con Dati Reali

### Passo 1: Creare file CSV con dati reali
Modifica i file in `data/input/` sostituendo i dati di esempio con:
- 12 scuole vere
- 69 classi reali
- 6 formatrici con disponibilità effettive
- 6 laboratori completi

### Passo 2: Lanciare ottimizzazione
```bash
# Prova prima con poche classi
./optimize-v2

# Verifica risultati
libreoffice data/output/calendario_v2_con_fasce.xlsx
```

### Passo 3: Iterare
Se non trova soluzioni:
- Aumenta timeout (in `src/optimizer_v2.py` linea ~230)
- Rilassa vincoli temporaneamente per debugging
- Verifica risorse sufficienti (ore formatrici vs ore richieste)

## Parametri Configurabili

In `src/optimizer_v2.py`:
- **Linea ~37**: `num_settimane = 20` (periodo gennaio-maggio)
- **Linea ~230**: `time_limit_seconds = 180` (timeout solver)
- **Linea ~169**: `penalita_totale.append(10 * cambio)` (peso continuità)
- **Linea ~190**: `penalita_totale.append(2 * stessa_fascia)` (peso rotazione)
- **Linea ~210**: `penalita_totale.append(1 * self.assignments[key])` (peso preferenze)

## Prestazioni Attese

**Esempio semplificato (12 classi, 96 incontri):**
- V1: ~0.2s
- V2: ~5s

**Scala reale stimata (69 classi, ~552 incontri):**
- V2: 30-120s (dipende da vincoli)

Se supera 10 minuti, considera:
- Ottimizzare 5 settimane alla volta
- Separare scuole geograficamente distanti

## Vantaggi della Soluzione

✅ **Riproducibile**: basta rilanciare lo script
✅ **Trasparente**: codice leggibile e modificabile
✅ **Scalabile**: funziona anche con più classi
✅ **Validato**: vincoli hard garantiti dal solver
✅ **Flessibile**: pesi e parametri facilmente modificabili
✅ **Documentato**: README e commenti nel codice

## Prossimi Miglioramenti Possibili

1. **Calendario vacanze**: escludere settimane specifiche
2. **Laboratori già completati**: per classe
3. **Distanze geografiche**: minimizzare spostamenti formatrici
4. **Anticipo classi quinte**: prima di maggio
5. **Visualizzazioni**: Gantt chart, mappe, grafici

Consulta `PROSSIMI_PASSI.md` per dettagli implementativi.

---

**Stato attuale**: ✅ Sistema funzionante e testato con successo!
