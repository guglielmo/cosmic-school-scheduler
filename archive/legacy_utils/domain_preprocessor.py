#!/usr/bin/env python3
"""
Domain Preprocessor - Riduzione domini per ottimizzazione CP-SAT

Questo modulo pre-calcola i domini validi per ogni classe PRIMA di creare
le variabili nel modello, riducendo drasticamente lo spazio di ricerca.

Vincoli considerati nel preprocessing:
- H03: Date fissate (occupano settimane specifiche)
- H06: Fasce orarie disponibili per classe
- H07: Date escluse per classe
- H11: Finestra di scheduling (28/1 - 16/5, escl. Pasqua)
- GSSI: Settimane occupate da laboratori GSSI

Output:
- Domini ridotti per ogni (classe, lab, incontro)
- Coppie compatibili per accorpamento (intersezione domini non vuota)
- Statistiche di riduzione
"""

import pandas as pd
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Set, Dict, List, Tuple, Optional
from datetime import date, timedelta
from pathlib import Path

from date_parser import DateParser


@dataclass
class SlotDomain:
    """Dominio di uno slot: combinazione (settimana, giorno, fascia)"""
    weeks: Set[int] = field(default_factory=set)
    days_per_week: Dict[int, Set[int]] = field(default_factory=dict)  # week -> set(giorni)
    slots_per_day: Dict[Tuple[int, int], Set[int]] = field(default_factory=dict)  # (week, day) -> set(fasce)

    def get_valid_slots(self) -> Set[Tuple[int, int, int]]:
        """Ritorna set di tuple (settimana, giorno, fascia) valide"""
        valid = set()
        for week in self.weeks:
            days = self.days_per_week.get(week, set())
            for day in days:
                fasce = self.slots_per_day.get((week, day), set())
                for fascia in fasce:
                    valid.add((week, day, fascia))
        return valid

    def count_slots(self) -> int:
        """Conta il numero totale di slot validi"""
        return len(self.get_valid_slots())

    def intersect(self, other: 'SlotDomain') -> 'SlotDomain':
        """Intersezione di due domini"""
        result = SlotDomain()
        result.weeks = self.weeks & other.weeks

        for week in result.weeks:
            days_self = self.days_per_week.get(week, set())
            days_other = other.days_per_week.get(week, set())
            common_days = days_self & days_other
            if common_days:
                result.days_per_week[week] = common_days

                for day in common_days:
                    slots_self = self.slots_per_day.get((week, day), set())
                    slots_other = other.slots_per_day.get((week, day), set())
                    common_slots = slots_self & slots_other
                    if common_slots:
                        result.slots_per_day[(week, day)] = common_slots

        # Rimuovi settimane senza giorni validi
        result.weeks = {w for w in result.weeks if w in result.days_per_week}

        return result

    def is_empty(self) -> bool:
        """Verifica se il dominio è vuoto"""
        return len(self.weeks) == 0 or self.count_slots() == 0


@dataclass
class ClassDomain:
    """Dominio complessivo di una classe"""
    class_id: int
    class_name: str
    school_id: int
    year: int

    # Dominio base (da H06, H11)
    base_domain: SlotDomain = field(default_factory=SlotDomain)

    # Date escluse (H07)
    excluded_slots: Set[Tuple[int, int, Optional[Set[int]]]] = field(default_factory=set)

    # Settimane fissate per lab (H03) - settimane già occupate
    fixed_weeks: Set[int] = field(default_factory=set)

    # Settimane GSSI (occupate da lab esterni)
    gssi_weeks: Set[int] = field(default_factory=set)

    # Dominio effettivo (dopo tutte le riduzioni)
    effective_domain: SlotDomain = field(default_factory=SlotDomain)

    # Statistiche
    original_slot_count: int = 0
    reduced_slot_count: int = 0


@dataclass
class GroupingPair:
    """Coppia di classi compatibili per accorpamento"""
    class1_id: int
    class2_id: int
    lab_id: int
    common_domain: SlotDomain
    compatibility_score: float = 0.0  # Percentuale slot in comune


class DomainPreprocessor:
    """Preprocessor per riduzione domini"""

    NUM_SETTIMANE = 16
    NUM_GIORNI = 6  # 0-5 (lun-sab)
    FASCE_GENERICHE = {1, 2, 3}  # mattino1, mattino2, pomeriggio
    SCUOLE_SABATO = {10, 13}  # Scuole che lavorano sabato

    # Settimane speciali
    SETTIMANA_INIZIO = 0  # Solo gio-sab (giorni 3-5)
    SETTIMANA_PASQUA = 9  # Solo lun-mer (giorni 0-2)
    SETTIMANA_FINE = 15   # Solo lun-gio (giorni 0-3)

    def __init__(self, input_dir: str = "data/input"):
        self.input_dir = Path(input_dir)
        self.class_domains: Dict[int, ClassDomain] = {}
        self.grouping_pairs: List[GroupingPair] = []

        # Dati caricati
        self.scuole = None
        self.classi = None
        self.laboratori = None
        self.laboratori_classi = None
        self.fasce_orarie_classi = None
        self.date_escluse_classi = None

        # Mappings
        self.labs_per_classe: Dict[int, List[int]] = defaultdict(list)
        self.scuola_per_classe: Dict[int, int] = {}
        self.anno_per_classe: Dict[int, int] = {}
        self.num_incontri_lab: Dict[int, int] = {}

    def load_data(self):
        """Carica tutti i dati CSV"""
        print("Caricamento dati...")

        self.scuole = pd.read_csv(self.input_dir / "scuole.csv")
        self.classi = pd.read_csv(self.input_dir / "classi.csv")
        self.laboratori = pd.read_csv(self.input_dir / "laboratori.csv")
        self.laboratori_classi = pd.read_csv(self.input_dir / "laboratori_classi.csv")
        self.fasce_orarie_classi = pd.read_csv(self.input_dir / "fasce_orarie_classi.csv")
        self.date_escluse_classi = pd.read_csv(self.input_dir / "date_escluse_classi.csv")

        # Carica anche fasce_orarie_scuole per DateParser
        fasce_orarie_scuole = pd.read_csv(self.input_dir / "fasce_orarie_scuole.csv")
        DateParser.load_fasce_info(fasce_orarie_scuole)

        # Costruisci mappings
        lab_ids_validi = set(self.laboratori['laboratorio_id'].values)

        for _, row in self.laboratori_classi.iterrows():
            if row['laboratorio_id'] in lab_ids_validi:
                self.labs_per_classe[row['classe_id']].append(row['laboratorio_id'])

        for _, row in self.classi.iterrows():
            self.scuola_per_classe[row['classe_id']] = row['scuola_id']
            self.anno_per_classe[row['classe_id']] = int(row['anno'])

        for _, lab in self.laboratori.iterrows():
            self.num_incontri_lab[lab['laboratorio_id']] = int(lab['num_incontri'])

        print(f"  {len(self.classi)} classi, {len(self.laboratori)} laboratori")
        print(f"  {len(self.labs_per_classe)} classi con lab FOP")

        return self

    def _build_base_domain(self, class_id: int) -> SlotDomain:
        """Costruisce il dominio base per una classe (H06, H11)"""
        domain = SlotDomain()

        scuola_id = self.scuola_per_classe.get(class_id)
        can_saturday = scuola_id in self.SCUOLE_SABATO

        # H06: Fasce disponibili per classe
        fasce_row = self.fasce_orarie_classi[
            self.fasce_orarie_classi['classe_id'] == class_id
        ]

        if len(fasce_row) > 0:
            fasce_str = fasce_row.iloc[0].get('fasce_disponibili', '')
            giorni_str = fasce_row.iloc[0].get('giorni_settimana', '')
            preferenza = fasce_row.iloc[0].get('preferenza', '')
        else:
            fasce_str = ''
            giorni_str = ''
            preferenza = ''

        # Parse fasce disponibili
        available_fasce = set()
        if pd.isna(fasce_str) or fasce_str == '':
            available_fasce = self.FASCE_GENERICHE.copy()
        else:
            fasce_map = {'mattino1': 1, 'mattino2': 2, 'pomeriggio': 3}
            for part in str(fasce_str).lower().split(','):
                part = part.strip()
                if part in fasce_map:
                    available_fasce.add(fasce_map[part])
            if not available_fasce:
                available_fasce = self.FASCE_GENERICHE.copy()

        # Parse giorni disponibili (con vincoli per fascia)
        # Format: "lunedì, martedì, mercoledì pomeriggio, giovedì pomeriggio, venerdì"
        available_days = set(range(5))  # Default: lun-ven
        if can_saturday:
            available_days.add(5)

        day_slot_constraints = {}  # giorno -> set(fasce permesse)

        if not pd.isna(giorni_str) and giorni_str != '':
            giorni_map = {
                'lunedi': 0, 'lunedì': 0,
                'martedi': 1, 'martedì': 1,
                'mercoledi': 2, 'mercoledì': 2,
                'giovedi': 3, 'giovedì': 3,
                'venerdi': 4, 'venerdì': 4,
                'sabato': 5
            }

            available_days = set()
            for part in str(giorni_str).lower().split(','):
                part = part.strip()

                # Check for time constraint (e.g., "mercoledì pomeriggio")
                has_mattina = 'mattina' in part
                has_pomeriggio = 'pomeriggio' in part

                # Extract day name
                for day_name, day_num in giorni_map.items():
                    if day_name in part:
                        if day_num == 5 and not can_saturday:
                            continue
                        available_days.add(day_num)

                        if has_mattina and not has_pomeriggio:
                            day_slot_constraints[day_num] = {1, 2}  # Solo mattina
                        elif has_pomeriggio and not has_mattina:
                            day_slot_constraints[day_num] = {3}  # Solo pomeriggio
                        break

        # H11: Finestra scheduling (applicata implicitamente)
        # Settimane 0-15, con vincoli speciali
        for week in range(self.NUM_SETTIMANE):
            valid_days_for_week = available_days.copy()

            # Vincoli calendario speciali
            if week == self.SETTIMANA_INIZIO:
                # Solo gio-sab
                valid_days_for_week = valid_days_for_week & {3, 4, 5}
            elif week == self.SETTIMANA_PASQUA:
                # Solo lun-mer
                valid_days_for_week = valid_days_for_week & {0, 1, 2}
            elif week == self.SETTIMANA_FINE:
                # Solo lun-gio
                valid_days_for_week = valid_days_for_week & {0, 1, 2, 3}

            if not valid_days_for_week:
                continue

            domain.weeks.add(week)
            domain.days_per_week[week] = valid_days_for_week

            for day in valid_days_for_week:
                # Fasce disponibili per questo giorno
                day_fasce = available_fasce.copy()

                # Applica vincoli giorno-specifici
                if day in day_slot_constraints:
                    day_fasce = day_fasce & day_slot_constraints[day]

                if day_fasce:
                    domain.slots_per_day[(week, day)] = day_fasce

            # Rimuovi giorni senza fasce
            domain.days_per_week[week] = {
                d for d in domain.days_per_week[week]
                if (week, d) in domain.slots_per_day
            }

        # Rimuovi settimane senza giorni
        domain.weeks = {w for w in domain.weeks if domain.days_per_week.get(w)}

        return domain

    def _apply_excluded_dates(self, domain: SlotDomain, class_id: int) -> SlotDomain:
        """Applica H07: Date escluse"""
        excluded_row = self.date_escluse_classi[
            self.date_escluse_classi['classe_id'] == class_id
        ]

        if len(excluded_row) == 0:
            return domain

        date_escluse_str = excluded_row.iloc[0]['date_escluse']
        if pd.isna(date_escluse_str):
            return domain

        parsed = DateParser.parse_date_escluse(date_escluse_str)

        for sett, giorno, fasce_escluse in parsed:
            if sett is None or sett not in domain.weeks:
                continue

            if giorno not in domain.days_per_week.get(sett, set()):
                continue

            key = (sett, giorno)
            if key not in domain.slots_per_day:
                continue

            if fasce_escluse is None:
                # Escludi tutto il giorno
                domain.slots_per_day.pop(key, None)
                if sett in domain.days_per_week:
                    domain.days_per_week[sett].discard(giorno)
            else:
                # Escludi solo alcune fasce
                domain.slots_per_day[key] = domain.slots_per_day[key] - fasce_escluse
                if not domain.slots_per_day[key]:
                    domain.slots_per_day.pop(key, None)
                    if sett in domain.days_per_week:
                        domain.days_per_week[sett].discard(giorno)

        # Pulisci settimane vuote
        domain.weeks = {w for w in domain.weeks if domain.days_per_week.get(w)}

        return domain

    def _get_fixed_weeks(self, class_id: int) -> Set[int]:
        """Ottiene settimane con date fissate (H03)"""
        fixed_weeks = set()

        rows = self.laboratori_classi[self.laboratori_classi['classe_id'] == class_id]

        for _, row in rows.iterrows():
            date_fissate = row.get('date_fissate')
            if pd.isna(date_fissate) or date_fissate == '':
                continue

            parsed = DateParser.parse_date_fissate(date_fissate)
            for sett, giorno, fasce in parsed:
                if sett is not None:
                    fixed_weeks.add(sett)

        return fixed_weeks

    def _get_gssi_weeks(self, class_id: int) -> Set[int]:
        """Ottiene settimane occupate da lab GSSI"""
        gssi_weeks = set()
        lab_ids_validi = set(self.laboratori['laboratorio_id'].values)

        rows = self.laboratori_classi[self.laboratori_classi['classe_id'] == class_id]

        for _, row in rows.iterrows():
            lab_id = row['laboratorio_id']
            if lab_id in lab_ids_validi:
                continue  # Lab FOP, non GSSI

            date_fissate = row.get('date_fissate')
            if pd.isna(date_fissate) or date_fissate == '':
                continue

            parsed = DateParser.parse_date_fissate(date_fissate)
            for sett, giorno, fasce in parsed:
                if sett is not None:
                    gssi_weeks.add(sett)

        return gssi_weeks

    def compute_class_domains(self):
        """Calcola i domini per tutte le classi"""
        print("\nCalcolo domini classi...")

        total_original = 0
        total_reduced = 0

        for _, row in self.classi.iterrows():
            class_id = row['classe_id']

            if class_id not in self.labs_per_classe:
                continue

            # Crea dominio classe
            cd = ClassDomain(
                class_id=class_id,
                class_name=row['nome'],
                school_id=row['scuola_id'],
                year=int(row['anno'])
            )

            # 1. Dominio base (H06, H11)
            cd.base_domain = self._build_base_domain(class_id)
            cd.original_slot_count = cd.base_domain.count_slots()

            # 2. Copia per modifiche
            cd.effective_domain = SlotDomain(
                weeks=cd.base_domain.weeks.copy(),
                days_per_week={k: v.copy() for k, v in cd.base_domain.days_per_week.items()},
                slots_per_day={k: v.copy() for k, v in cd.base_domain.slots_per_day.items()}
            )

            # 3. Applica date escluse (H07)
            cd.effective_domain = self._apply_excluded_dates(cd.effective_domain, class_id)

            # 4. Ottieni settimane fissate e GSSI
            cd.fixed_weeks = self._get_fixed_weeks(class_id)
            cd.gssi_weeks = self._get_gssi_weeks(class_id)

            # 5. Rimuovi settimane GSSI dal dominio (per lab FOP)
            for week in cd.gssi_weeks:
                if week in cd.effective_domain.weeks:
                    cd.effective_domain.weeks.discard(week)
                    cd.effective_domain.days_per_week.pop(week, None)
                    # Rimuovi anche gli slots
                    to_remove = [k for k in cd.effective_domain.slots_per_day if k[0] == week]
                    for k in to_remove:
                        cd.effective_domain.slots_per_day.pop(k, None)

            cd.reduced_slot_count = cd.effective_domain.count_slots()

            self.class_domains[class_id] = cd

            total_original += cd.original_slot_count
            total_reduced += cd.reduced_slot_count

        reduction_pct = 100 * (1 - total_reduced / total_original) if total_original > 0 else 0
        print(f"  Slot totali: {total_original} -> {total_reduced} ({reduction_pct:.1f}% riduzione)")

        return self

    def compute_grouping_pairs(self):
        """Pre-calcola coppie compatibili per accorpamento"""
        print("\nCalcolo coppie accorpamento...")

        # Raggruppa classi per scuola
        classi_per_scuola = defaultdict(list)
        for class_id, cd in self.class_domains.items():
            classi_per_scuola[cd.school_id].append(class_id)

        lab_ids_validi = set(self.laboratori['laboratorio_id'].values)
        total_pairs = 0
        compatible_pairs = 0

        for scuola_id, classi_scuola in classi_per_scuola.items():
            for i, c1 in enumerate(classi_scuola):
                for c2 in classi_scuola[i+1:]:
                    # Trova lab in comune
                    labs_c1 = set(self.labs_per_classe[c1])
                    labs_c2 = set(self.labs_per_classe[c2])
                    labs_comuni = labs_c1 & labs_c2 & lab_ids_validi

                    if not labs_comuni:
                        continue

                    # Calcola intersezione domini
                    dom1 = self.class_domains[c1].effective_domain
                    dom2 = self.class_domains[c2].effective_domain
                    intersection = dom1.intersect(dom2)

                    for lab_id in labs_comuni:
                        total_pairs += 1

                        if intersection.is_empty():
                            continue

                        # Calcola score di compatibilità
                        slots1 = dom1.count_slots()
                        slots2 = dom2.count_slots()
                        common_slots = intersection.count_slots()

                        if slots1 > 0 and slots2 > 0:
                            score = common_slots / min(slots1, slots2)
                        else:
                            score = 0

                        pair = GroupingPair(
                            class1_id=c1,
                            class2_id=c2,
                            lab_id=lab_id,
                            common_domain=intersection,
                            compatibility_score=score
                        )
                        self.grouping_pairs.append(pair)
                        compatible_pairs += 1

        pct_compatible = 100 * compatible_pairs / total_pairs if total_pairs > 0 else 0
        print(f"  Coppie totali: {total_pairs}, compatibili: {compatible_pairs} ({pct_compatible:.1f}%)")

        return self

    def get_domain_for_meeting(self, class_id: int, lab_id: int, meeting_k: int) -> SlotDomain:
        """Ottiene il dominio specifico per un incontro, considerando date fissate"""
        if class_id not in self.class_domains:
            return SlotDomain()

        cd = self.class_domains[class_id]
        base = cd.effective_domain

        # Verifica se questo incontro ha una data fissata
        rows = self.laboratori_classi[
            (self.laboratori_classi['classe_id'] == class_id) &
            (self.laboratori_classi['laboratorio_id'] == lab_id)
        ]

        if len(rows) == 0:
            return base

        date_fissate = rows.iloc[0].get('date_fissate')
        if pd.isna(date_fissate) or date_fissate == '':
            return base

        parsed = DateParser.parse_date_fissate(date_fissate)

        if meeting_k < len(parsed):
            sett, giorno, fasce_valide = parsed[meeting_k]
            if sett is not None:
                # Dominio ristretto a questa data specifica
                fixed_domain = SlotDomain()
                fixed_domain.weeks = {sett}
                fixed_domain.days_per_week[sett] = {giorno}

                if fasce_valide:
                    fixed_domain.slots_per_day[(sett, giorno)] = fasce_valide
                else:
                    # Usa fasce dal dominio base se non specificate
                    base_fasce = base.slots_per_day.get((sett, giorno), self.FASCE_GENERICHE)
                    fixed_domain.slots_per_day[(sett, giorno)] = base_fasce

                return fixed_domain

        return base

    def get_available_weeks(self, class_id: int) -> Set[int]:
        """Ritorna settimane disponibili per una classe (escl. fissate e GSSI)"""
        if class_id not in self.class_domains:
            return set()

        cd = self.class_domains[class_id]
        available = cd.effective_domain.weeks.copy()

        # Non escludere le settimane fissate dal dominio generale
        # perché potrebbero servire per altri lab

        return available

    def get_compatible_pairs_for_lab(self, lab_id: int) -> List[Tuple[int, int, float]]:
        """Ritorna coppie compatibili per un lab specifico: [(c1, c2, score), ...]"""
        return [
            (p.class1_id, p.class2_id, p.compatibility_score)
            for p in self.grouping_pairs
            if p.lab_id == lab_id
        ]

    def print_statistics(self):
        """Stampa statistiche dettagliate"""
        print("\n" + "=" * 60)
        print("STATISTICHE PRE-PROCESSING")
        print("=" * 60)

        # Per anno
        by_year = defaultdict(list)
        for cd in self.class_domains.values():
            by_year[cd.year].append(cd)

        print("\nDomini per anno:")
        for year in sorted(by_year.keys()):
            classes = by_year[year]
            avg_original = sum(c.original_slot_count for c in classes) / len(classes)
            avg_reduced = sum(c.reduced_slot_count for c in classes) / len(classes)
            reduction = 100 * (1 - avg_reduced / avg_original) if avg_original > 0 else 0
            print(f"  Anno {year}: {len(classes)} classi, media slot {avg_original:.0f} -> {avg_reduced:.0f} ({reduction:.1f}% rid.)")

        # Classi con domini molto ristretti
        print("\nClassi con domini ristretti (<50 slot):")
        restricted = [(cd.class_name, cd.reduced_slot_count)
                     for cd in self.class_domains.values()
                     if cd.reduced_slot_count < 50]
        restricted.sort(key=lambda x: x[1])
        for name, count in restricted[:10]:
            print(f"  {name}: {count} slot")

        # Accorpamenti
        print(f"\nCoppie accorpamento compatibili: {len(self.grouping_pairs)}")

        high_compat = [p for p in self.grouping_pairs if p.compatibility_score > 0.7]
        print(f"  Alta compatibilità (>70%): {len(high_compat)}")

        low_compat = [p for p in self.grouping_pairs if p.compatibility_score < 0.3]
        print(f"  Bassa compatibilità (<30%): {len(low_compat)}")

        # Settimane GSSI
        classes_with_gssi = [cd for cd in self.class_domains.values() if cd.gssi_weeks]
        total_gssi_weeks = sum(len(cd.gssi_weeks) for cd in classes_with_gssi)
        print(f"\nClassi con lab GSSI: {len(classes_with_gssi)}")
        print(f"  Totale settimane GSSI bloccate: {total_gssi_weeks}")

        print("=" * 60)

    def export_domains_summary(self, output_path: str = "data/output/domains_summary.csv"):
        """Esporta riassunto domini in CSV"""
        rows = []
        for cd in self.class_domains.values():
            rows.append({
                'classe_id': cd.class_id,
                'nome': cd.class_name,
                'scuola_id': cd.school_id,
                'anno': cd.year,
                'slot_originali': cd.original_slot_count,
                'slot_ridotti': cd.reduced_slot_count,
                'riduzione_pct': 100 * (1 - cd.reduced_slot_count / cd.original_slot_count) if cd.original_slot_count > 0 else 0,
                'settimane_disponibili': len(cd.effective_domain.weeks),
                'settimane_fissate': len(cd.fixed_weeks),
                'settimane_gssi': len(cd.gssi_weeks)
            })

        df = pd.DataFrame(rows)
        df = df.sort_values(['anno', 'scuola_id', 'nome'])
        df.to_csv(output_path, index=False)
        print(f"\nEsportato: {output_path}")

        return df


def main():
    """Esegue preprocessing e mostra statistiche"""
    preprocessor = DomainPreprocessor()
    preprocessor.load_data()
    preprocessor.compute_class_domains()
    preprocessor.compute_grouping_pairs()
    preprocessor.print_statistics()
    preprocessor.export_domains_summary()


if __name__ == "__main__":
    main()
