#!/usr/bin/env python3
"""
Cosmic School Optimizer - Basato su Sistema di Constraints Formali

Questo optimizer usa il sistema di constraints formali definito in src/constraints/
per garantire coerenza, tracciabilità e manutenibilità.

Architettura:
1. ConstraintFactory carica tutti i constraints dai CSV
2. Variabili OR-Tools create per ogni (classe, lab, incontro)
3. Ogni HardConstraint.add_to_model() aggiunge vincoli al modello
4. Ogni SoftConstraint.add_to_objective() contribuisce alla funzione obiettivo
5. Solver CP-SAT risolve il problema

Variabili di decisione per ogni incontro (classe, lab, k):
- settimana[c,l,k]: IntVar(0..15)  # 16 settimane
- giorno[c,l,k]: IntVar(0..5)      # lun-sab
- fascia[c,l,k]: IntVar(1..3)      # mattino1, mattino2, pomeriggio
- formatrice[c,l,k]: IntVar(1..4)  # 4 formatrici

Per accorpamenti:
- accorpa[c1,c2,lab]: BoolVar       # True se c1 e c2 fanno lab insieme
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple, Set, Any
from dataclasses import dataclass
from collections import defaultdict

import pandas as pd
from ortools.sat.python import cp_model

# Add src to path se necessario
sys.path.insert(0, str(Path(__file__).parent))

from constraints import (
    ConstraintFactory,
    ConstraintType,
    HardConstraint,
    SoftConstraint,
    MeetingKey,
)
from date_utils import DateMapper


class ModelVariables:
    """Container per tutte le variabili del modello"""

    def __init__(self):
        # Variabili principali per ogni incontro
        self.settimana: Dict[MeetingKey, cp_model.IntVar] = {}
        self.giorno: Dict[MeetingKey, cp_model.IntVar] = {}
        self.fascia: Dict[MeetingKey, cp_model.IntVar] = {}
        self.formatrice: Dict[MeetingKey, cp_model.IntVar] = {}

        # Variabili helper
        self.slot: Dict[MeetingKey, cp_model.IntVar] = {}  # Slot combinato per ordinamento

        # Variabili accorpamento
        self.accorpa: Dict[Tuple[int, int, int], cp_model.BoolVar] = {}  # (c1, c2, lab)

        # Variabili ausiliarie per vincoli soft
        self.is_formatrice: Dict[Tuple[int, MeetingKey], cp_model.BoolVar] = {}  # (f_id, meeting)

        # Mappings per lookup veloce
        self.meetings: List[MeetingKey] = []  # Tutti gli incontri
        self.meetings_by_class: Dict[int, List[MeetingKey]] = defaultdict(list)
        self.meetings_by_trainer: Dict[int, List[MeetingKey]] = defaultdict(list)


@dataclass
class ConstraintContext:
    """
    Context object che fornisce ai constraints l'accesso ai dati globali.

    Passato a add_to_model() e add_to_objective() per evitare
    di passare 10+ parametri separati.
    """
    # Info sui laboratori
    lab_info: Dict[int, Dict]  # lab_id -> {name, num_meetings, hours_per_meeting}

    # Info sulle classi
    class_info: Dict[int, Dict]  # class_id -> {name, school_id, year, priority}

    # Info sulle formatrici
    trainer_info: Dict[int, Dict]  # trainer_id -> {name, max_hours}

    # Info sulle scuole
    school_info: Dict[int, Dict]  # school_id -> {name, city}

    # Lab assignments
    labs_per_class: Dict[int, List[int]]  # class_id -> [lab_ids]

    # Dataframes originali (per accesso a colonne complesse)
    data: Dict[str, pd.DataFrame]

    # Costanti temporali
    num_settimane: int = 16
    num_giorni: int = 6
    num_fasce: int = 3
    num_formatrici: int = 4


class Optimizer:
    """
    Optimizer basato su constraints formali.

    Flow:
    1. __init__: Carica dati e constraints
    2. build_variables(): Crea variabili OR-Tools
    3. apply_hard_constraints(): Applica tutti i hard constraints
    4. build_objective(): Costruisce funzione obiettivo dai soft constraints
    5. solve(): Risolve con CP-SAT
    6. export_solution(): Esporta risultati
    """

    # Costanti
    NUM_SETTIMANE = 16
    NUM_GIORNI = 6  # 0-5 (lun-sab)
    NUM_FASCE = 3   # 1-3 (mattino1, mattino2, pomeriggio)
    NUM_FORMATRICI = 4  # 1-4

    def __init__(self, input_dir: str = "data/input",
                 config_path: str = "src/constraints/config/constraint_weights.yaml",
                 verbose: bool = False):
        """
        Inizializza optimizer con sistema di constraints formali.

        Args:
            input_dir: Directory con CSV di input
            config_path: Path al file di configurazione pesi
            verbose: Se True, stampa log dettagliati
        """
        self.input_dir = Path(input_dir)
        self.verbose = verbose

        # OR-Tools
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        self.variables = ModelVariables()

        # Sistema di constraints
        self.factory = ConstraintFactory(
            data_dir=str(self.input_dir),
            config_path=config_path
        )
        self.constraints = []
        self.hard_constraints: List[HardConstraint] = []
        self.soft_constraints: List[SoftConstraint] = []

        # Dati caricati
        self.data = {}

        # Mappings costruiti dai CSV
        self.class_info: Dict[int, Dict] = {}  # class_id -> {name, school_id, year, ...}
        self.lab_info: Dict[int, Dict] = {}    # lab_id -> {name, num_meetings, hours, ...}
        self.trainer_info: Dict[int, Dict] = {} # trainer_id -> {name, max_hours, ...}
        self.school_info: Dict[int, Dict] = {}  # school_id -> {name, city, ...}

        # Strutture costruite
        self.labs_per_class: Dict[int, List[int]] = defaultdict(list)
        self.num_meetings_per_lab: Dict[int, int] = {}

        # Context per constraints (creato dopo load_data)
        self.context: ConstraintContext = None

        self._log("=" * 80)
        self._log("  COSMIC SCHOOL OPTIMIZER - Constraint-Based Scheduler")
        self._log("=" * 80)

    def _log(self, message: str):
        """Log condizionale"""
        if self.verbose:
            print(message)

    def load_data(self):
        """Carica tutti i dati CSV"""
        self._log("\n1. Caricamento dati...")

        # Carica CSV
        csv_files = [
            'scuole', 'classi', 'laboratori', 'laboratori_classi',
            'formatrici', 'formatrici_classi',
            'fasce_orarie_scuole', 'fasce_orarie_classi',
            'date_escluse_classi'
        ]

        for csv_name in csv_files:
            csv_path = self.input_dir / f"{csv_name}.csv"
            if csv_path.exists():
                self.data[csv_name] = pd.read_csv(csv_path)
                self._log(f"  ✓ {csv_name}.csv: {len(self.data[csv_name])} righe")
            else:
                self._log(f"  ⚠ {csv_name}.csv: NON TROVATO")
                self.data[csv_name] = pd.DataFrame()

        # Costruisci mappings
        self._build_mappings()

        # Crea context per constraints
        self.context = ConstraintContext(
            lab_info=self.lab_info,
            class_info=self.class_info,
            trainer_info=self.trainer_info,
            school_info=self.school_info,
            labs_per_class=self.labs_per_class,
            data=self.data,
            num_settimane=self.NUM_SETTIMANE,
            num_giorni=self.NUM_GIORNI,
            num_fasce=self.NUM_FASCE,
            num_formatrici=self.NUM_FORMATRICI
        )

        self._log(f"\n  Riepilogo:")
        self._log(f"    {len(self.class_info)} classi")
        self._log(f"    {len(self.lab_info)} laboratori FOP")
        self._log(f"    {len(self.trainer_info)} formatrici")
        self._log(f"    {len(self.school_info)} scuole")

    def _build_mappings(self):
        """Costruisce strutture dati dai CSV"""
        # Classes
        for _, row in self.data['classi'].iterrows():
            class_id = int(row['classe_id'])
            self.class_info[class_id] = {
                'name': row['nome'],
                'school_id': int(row['scuola_id']),
                'year': int(row['anno']),
                'priority': row.get('priorita', 'normale')
            }

        # Labs
        for _, row in self.data['laboratori'].iterrows():
            lab_id = int(row['laboratorio_id'])
            self.lab_info[lab_id] = {
                'name': row['nome'],
                'num_meetings': int(row['num_incontri']),
                'hours_per_meeting': int(row['ore_per_incontro'])
            }
            self.num_meetings_per_lab[lab_id] = int(row['num_incontri'])

        # Trainers
        for _, row in self.data['formatrici'].iterrows():
            trainer_id = int(row['formatrice_id'])
            self.trainer_info[trainer_id] = {
                'name': row['nome'],
                'max_hours': int(row['ore_generali'])
            }

        # Schools
        for _, row in self.data['scuole'].iterrows():
            school_id = int(row['scuola_id'])
            self.school_info[school_id] = {
                'name': row['nome'],
                'city': row['citta']
            }

        # Lab assignments per class
        lab_ids_validi = set(self.lab_info.keys())
        for _, row in self.data['laboratori_classi'].iterrows():
            lab_id = int(row['laboratorio_id'])
            if lab_id in lab_ids_validi:  # Solo lab FOP
                class_id = int(row['classe_id'])
                self.labs_per_class[class_id].append(lab_id)

    def load_constraints(self):
        """Carica constraints dal factory"""
        self._log("\n2. Caricamento constraints...")

        # Usa factory per costruire tutti i constraints
        self.constraints = self.factory.build_all_constraints()

        # Separa hard e soft
        self.hard_constraints = [c for c in self.constraints if c.type == ConstraintType.HARD]
        self.soft_constraints = [c for c in self.constraints if c.type == ConstraintType.SOFT]

        self._log(f"  ✓ {len(self.hard_constraints)} Hard Constraints")
        self._log(f"  ✓ {len(self.soft_constraints)} Soft Constraints")

        # Mostra sommario per categoria
        from collections import Counter
        categories = Counter(c.category.value for c in self.constraints)
        self._log(f"\n  Per categoria:")
        for cat, count in categories.most_common():
            self._log(f"    {cat:12s}: {count:3d}")

    def build_variables(self):
        """Crea tutte le variabili OR-Tools"""
        self._log("\n3. Creazione variabili...")

        num_vars = 0

        # Per ogni classe e i suoi lab
        for class_id, labs in self.labs_per_class.items():
            for lab_id in labs:
                num_meetings = self.num_meetings_per_lab.get(lab_id, 1)

                for k in range(num_meetings):
                    key = MeetingKey(class_id, lab_id, k)
                    self.variables.meetings.append(key)
                    self.variables.meetings_by_class[class_id].append(key)

                    # Variabili temporali
                    self.variables.settimana[key] = self.model.NewIntVar(
                        0, self.NUM_SETTIMANE - 1,
                        f"w_{class_id}_{lab_id}_{k}"
                    )

                    self.variables.giorno[key] = self.model.NewIntVar(
                        0, self.NUM_GIORNI - 1,
                        f"d_{class_id}_{lab_id}_{k}"
                    )

                    self.variables.fascia[key] = self.model.NewIntVar(
                        1, self.NUM_FASCE,
                        f"f_{class_id}_{lab_id}_{k}"
                    )

                    # Variabile formatrice
                    self.variables.formatrice[key] = self.model.NewIntVar(
                        1, self.NUM_FORMATRICI,
                        f"t_{class_id}_{lab_id}_{k}"
                    )

                    # Variabile slot (per ordinamento)
                    self.variables.slot[key] = self.model.NewIntVar(
                        0, self.NUM_SETTIMANE * 60 + self.NUM_GIORNI * 12 + 12,
                        f"s_{class_id}_{lab_id}_{k}"
                    )
                    self.model.Add(
                        self.variables.slot[key] ==
                        self.variables.settimana[key] * 60 +
                        self.variables.giorno[key] * 12 +
                        self.variables.fascia[key]
                    )

                    num_vars += 5  # 5 variabili per incontro

        # Crea variabili accorpamento per coppie compatibili
        self._log(f"\n  Creazione variabili accorpamento...")
        num_accorpa = 0

        # Trova coppie compatibili
        compatible_pairs = []
        classes = list(self.class_info.keys())

        for i, c1 in enumerate(classes):
            for c2 in classes[i+1:]:  # c1 < c2 per evitare duplicati
                # Verifica compatibilità: stessa scuola
                if self.class_info[c1]['school_id'] == self.class_info[c2]['school_id']:
                    # Trova lab comuni
                    labs_c1 = set(self.labs_per_class[c1])
                    labs_c2 = set(self.labs_per_class[c2])
                    common_labs = labs_c1 & labs_c2

                    for lab in common_labs:
                        compatible_pairs.append((c1, c2, lab))

        # Crea variabili accorpa e vincoli di sincronizzazione
        for c1, c2, lab in compatible_pairs:
            # Crea variabile BoolVar per questa coppia/lab
            accorpa_var = self.model.NewBoolVar(f"acc_{c1}_{c2}_{lab}")
            self.variables.accorpa[(c1, c2, lab)] = accorpa_var
            num_accorpa += 1

            # Vincoli di sincronizzazione: se accorpa=1, devono avere stesso slot
            # Per ogni coppia di incontri (k-esimo incontro di c1 e c2 per questo lab)
            num_meetings = self.num_meetings_per_lab.get(lab, 1)

            for k in range(num_meetings):
                key_c1 = MeetingKey(c1, lab, k)
                key_c2 = MeetingKey(c2, lab, k)

                # Se entrambi gli incontri esistono
                if key_c1 in self.variables.settimana and key_c2 in self.variables.settimana:
                    # Se accorpa=1, allora slot e formatrice devono essere uguali
                    # OTTIMIZZAZIONE: usa variabile slot invece di 3 constraints separati
                    # slot = settimana * 60 + giorno * 12 + fascia (già calcolato)
                    self.model.Add(
                        self.variables.slot[key_c1] == self.variables.slot[key_c2]
                    ).OnlyEnforceIf(accorpa_var)

                    # Anche la formatrice deve essere la stessa
                    self.model.Add(
                        self.variables.formatrice[key_c1] == self.variables.formatrice[key_c2]
                    ).OnlyEnforceIf(accorpa_var)

        self._log(f"  ✓ {num_accorpa} variabili accorpamento create")
        self._log(f"  ✓ {len(self.variables.meetings)} incontri")
        self._log(f"  ✓ {num_vars + num_accorpa} variabili totali")

        # TODO: Variabili accorpamento (da implementare)
        self._log(f"  ⏸ Variabili accorpamento: da implementare")

    def apply_hard_constraints(self):
        """Applica tutti i hard constraints al modello"""
        self._log("\n4. Applicazione Hard Constraints...")

        for constraint in self.hard_constraints:
            constraint_name = constraint.__class__.__name__
            self._log(f"  [{constraint.id}] {constraint_name}...")

            try:
                # Chiama add_to_model() del constraint
                constraint.add_to_model(self.model, self.variables, self.context)
                self._log(f"    ✓ Applicato")
            except NotImplementedError:
                self._log(f"    ⏸ Non ancora implementato")
            except Exception as e:
                self._log(f"    ✗ Errore: {e}")

    def build_objective(self):
        """Costruisce funzione obiettivo dai soft constraints"""
        self._log("\n5. Costruzione Obiettivo...")

        objective_terms = []

        for constraint in self.soft_constraints:
            constraint_name = constraint.__class__.__name__
            weight = constraint.weight
            self._log(f"  [{constraint.id}] {constraint_name} (peso={weight})...")

            try:
                # Chiama add_to_objective() del constraint
                term = constraint.add_to_objective(self.model, self.variables, self.context)
                if term is not None:
                    objective_terms.append(weight * term)
                    self._log(f"    ✓ Aggiunto (peso={weight})")
            except NotImplementedError:
                self._log(f"    ⏸ Non ancora implementato")
            except Exception as e:
                self._log(f"    ✗ Errore: {e}")

        if objective_terms:
            self.model.Maximize(sum(objective_terms))
            self._log(f"\n  ✓ Obiettivo: massimizza {len(objective_terms)} termini")
        else:
            self._log(f"\n  ⚠ Nessun termine obiettivo (solo feasibility)")

    def solve(self, time_limit_seconds: int = 300):
        """
        Risolve il modello con CP-SAT.

        Args:
            time_limit_seconds: Timeout in secondi

        Returns:
            Status del solver (OPTIMAL, FEASIBLE, o None se nessuna soluzione)
        """
        self._log("\n6. Solving...")
        self._log(f"  Timeout: {time_limit_seconds}s")

        self.solver.parameters.max_time_in_seconds = time_limit_seconds
        self.solver.parameters.log_search_progress = self.verbose
        self.solver.parameters.num_search_workers = 12

        status = self.solver.Solve(self.model)

        status_name = self.solver.StatusName(status)
        wall_time = self.solver.WallTime()

        self._log(f"\n  Status: {status_name}")
        self._log(f"  Tempo: {wall_time:.2f}s")

        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            if hasattr(self.solver, 'ObjectiveValue'):
                obj_value = self.solver.ObjectiveValue()
                self._log(f"  Obiettivo: {obj_value}")
            return status
        else:
            self._log(f"  ✗ Nessuna soluzione trovata")
            return None

    def export_solution(self, output_path: str):
        """
        Esporta la soluzione trovata in formato CSV.

        Args:
            output_path: Path del file CSV di output

        Output columns:
            - classe_id, classe_nome, scuola_nome
            - laboratorio_id, laboratorio_nome
            - incontro_num (1-based)
            - formatrice_id, formatrice_nome
            - settimana, giorno, fascia, slot
            - data, orario (human-readable)
            - accorpata_con (se accorpata)
        """
        self._log(f"\n7. Esportazione soluzione...")

        if not hasattr(self, 'solver') or self.solver is None:
            self._log(f"  ✗ Errore: solver non disponibile")
            return

        # Crea date mapper
        date_mapper = DateMapper()

        # Mappa nomi giorni e fasce
        day_names = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato"]
        fascia_names = {1: "Mattino1", 2: "Mattino2", 3: "Pomeriggio"}

        # Raccogli risultati
        results = []

        for meeting in self.variables.meetings:
            # Leggi valori soluzione
            week = self.solver.Value(self.variables.settimana[meeting])
            day = self.solver.Value(self.variables.giorno[meeting])
            fascia = self.solver.Value(self.variables.fascia[meeting])
            trainer_id = self.solver.Value(self.variables.formatrice[meeting])
            slot = self.solver.Value(self.variables.slot[meeting])

            # Ottieni info da context
            class_info = self.context.class_info[meeting.class_id]
            lab_info = self.context.lab_info[meeting.lab_id]
            trainer_info = self.context.trainer_info[trainer_id]
            school_info = self.context.school_info[class_info['school_id']]

            # Formatta data e orario
            datetime_str = date_mapper.format_datetime(week, day, fascia)

            # Verifica se accorpata
            accorpata_con = []
            for (c1, c2, lab), var in self.variables.accorpa.items():
                if self.solver.Value(var) == 1:
                    # Questa coppia è accorpata
                    if meeting.class_id == c1 and meeting.lab_id == lab:
                        accorpata_con.append(c2)
                    elif meeting.class_id == c2 and meeting.lab_id == lab:
                        accorpata_con.append(c1)

            accorpata_str = ", ".join([self.context.class_info[cid]['name'] for cid in accorpata_con]) if accorpata_con else ""

            # Aggiungi record
            results.append({
                'classe_id': meeting.class_id,
                'classe_nome': class_info['name'],
                'scuola_nome': school_info['name'],
                'laboratorio_id': meeting.lab_id,
                'laboratorio_nome': lab_info['name'],
                'incontro_num': meeting.meeting_index + 1,  # 1-based
                'formatrice_id': trainer_id,
                'formatrice_nome': trainer_info['name'],
                'settimana': week,
                'giorno_num': day,
                'giorno_nome': day_names[day],
                'fascia_num': fascia,
                'fascia_nome': fascia_names[fascia],
                'slot': slot,
                'data_ora': datetime_str,
                'accorpata_con': accorpata_str
            })

        # Converti in DataFrame e ordina
        df = pd.DataFrame(results)
        df = df.sort_values(['settimana', 'giorno_num', 'fascia_num', 'classe_id', 'laboratorio_id', 'incontro_num'])

        # Salva CSV
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)

        self._log(f"  ✓ Esportati {len(df)} incontri")
        self._log(f"  ✓ Output: {output_path}")

        # Statistiche accorpamenti
        num_accorpamenti = sum(
            1 for var in self.variables.accorpa.values()
            if self.solver.Value(var) == 1
        )
        if num_accorpamenti > 0:
            self._log(f"  ✓ Accorpamenti: {num_accorpamenti}")

    def run(self, output_path: str = "data/output/calendario.csv",
            time_limit: int = 300):
        """
        Esegue l'intero pipeline di ottimizzazione.

        Args:
            output_path: Path del file di output
            time_limit: Timeout in secondi per il solver

        Returns:
            True se soluzione trovata, False altrimenti
        """
        try:
            self.load_data()
            self.load_constraints()
            self.build_variables()
            self.apply_hard_constraints()
            self.build_objective()

            status = self.solve(time_limit_seconds=time_limit)

            if status:
                self.export_solution(output_path)
                self._log("\n✅ Ottimizzazione completata con successo!")
                return True
            else:
                self._log("\n❌ Nessuna soluzione trovata")
                return False

        except Exception as e:
            self._log(f"\n❌ Errore: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """Entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Cosmic School Optimizer - Constraint-based scheduler'
    )
    parser.add_argument(
        '--input', '-i',
        default='data/input',
        help='Directory con CSV di input'
    )
    parser.add_argument(
        '--output', '-o',
        default='data/output/calendario.csv',
        help='File CSV di output'
    )
    parser.add_argument(
        '--config', '-c',
        default='src/constraints/config/constraint_weights.yaml',
        help='File configurazione pesi'
    )
    parser.add_argument(
        '--timeout', '-t',
        type=int,
        default=300,
        help='Timeout solver in secondi'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Log dettagliati'
    )

    args = parser.parse_args()

    # Crea e esegui optimizer
    optimizer = Optimizer(
        input_dir=args.input,
        config_path=args.config,
        verbose=args.verbose
    )

    success = optimizer.run(
        output_path=args.output,
        time_limit=args.timeout
    )

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
