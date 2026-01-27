#!/usr/bin/env python3
"""
Example script demonstrating constraint system usage.

This script shows how to:
1. Load constraints from CSV data
2. Inspect constraint properties
3. Generate summary reports
4. Export constraints for documentation
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from constraints import ConstraintFactory, ConstraintType, ConstraintCategory


def main():
    print("=" * 80)
    print("Cosmic School Constraint System - Example")
    print("=" * 80)
    print()

    # Initialize factory
    print("Initializing constraint factory...")
    factory = ConstraintFactory(
        data_dir="data/input",
        config_path="config/constraint_weights.yaml"
    )

    # Load all CSV data
    print("Loading CSV data...")
    factory.load_all_csv_data()
    print(f"  Loaded {len(factory.csv_data)} CSV files")
    print()

    # Build all constraints
    print("Building constraints from CSV data...")
    constraints = factory.build_all_constraints()
    print(f"  Created {len(constraints)} constraints")
    print()

    # Generate summary
    print("=" * 80)
    print("CONSTRAINT SUMMARY")
    print("=" * 80)
    summary = factory.get_constraint_summary(constraints)

    print(f"\nTotal constraints: {summary['total']}")
    print(f"\nBy type:")
    for ctype, count in summary['by_type'].items():
        print(f"  {ctype:10s}: {count:3d}")

    print(f"\nBy category:")
    for category, count in summary['by_category'].items():
        print(f"  {category:12s}: {count:3d}")

    print(f"\nBy constraint class (top 10):")
    for class_name, count in summary['by_class'].most_common(10):
        print(f"  {class_name:45s}: {count:3d}")

    # Show examples of each constraint type
    print()
    print("=" * 80)
    print("EXAMPLE CONSTRAINTS")
    print("=" * 80)

    print("\nHARD CONSTRAINTS (examples):")
    hard_constraints = [c for c in constraints if c.type == ConstraintType.HARD]
    for constraint in hard_constraints[:5]:
        print(f"  [{constraint.id}] {constraint.name}")
        print(f"      Category: {constraint.category.value}")
        print(f"      {constraint.description}")
        print()

    print("\nSOFT CONSTRAINTS (examples):")
    soft_constraints = [c for c in constraints if c.type == ConstraintType.SOFT]
    for constraint in soft_constraints[:5]:
        print(f"  [{constraint.id}] {constraint.name} (weight: {constraint.weight})")
        print(f"      Category: {constraint.category.value}")
        print(f"      {constraint.description}")
        print()

    # Group by category
    print()
    print("=" * 80)
    print("CONSTRAINTS BY CATEGORY")
    print("=" * 80)

    for category in ConstraintCategory:
        cat_constraints = [c for c in constraints if c.category == category]
        if cat_constraints:
            print(f"\n{category.value.upper()} ({len(cat_constraints)} constraints):")
            for c in cat_constraints[:3]:  # Show first 3
                print(f"  - [{c.id}] {c.name} ({c.type.value})")
            if len(cat_constraints) > 3:
                print(f"  ... and {len(cat_constraints) - 3} more")

    # Analyze specific constraint types
    print()
    print("=" * 80)
    print("SPECIFIC ANALYSES")
    print("=" * 80)

    # Trainer constraints
    from constraints import TrainerTotalHoursConstraint
    trainer_hours = [c for c in constraints if isinstance(c, TrainerTotalHoursConstraint)]
    print(f"\nTrainer hour budgets:")
    total_hours = 0
    for c in trainer_hours:
        print(f"  {c.trainer_name:12s}: {c.max_hours:3d} hours")
        total_hours += c.max_hours
    print(f"  {'TOTAL':12s}: {total_hours:3d} hours")

    # Fixed dates
    from constraints import FixedDatesConstraint
    fixed_dates = [c for c in constraints if isinstance(c, FixedDatesConstraint)]
    print(f"\nClasses with fixed dates: {len(fixed_dates)}")
    for c in fixed_dates[:5]:
        print(f"  {c.class_name} - Lab {c.lab_id}: {len(c.fixed_dates)} fixed date(s)")

    # Fifth year priority
    from constraints import FifthYearPriorityConstraint
    fifth_years = [c for c in constraints if isinstance(c, FifthYearPriorityConstraint)]
    print(f"\nFifth-year classes with priority: {len(fifth_years)}")

    # Preferred groupings
    from constraints import PreferredGroupingConstraint
    preferred_groups = [c for c in constraints if isinstance(c, PreferredGroupingConstraint)]
    print(f"\nPreferred class groupings: {len(preferred_groups)}")
    for c in preferred_groups[:5]:
        print(f"  {c.class_name} <-> {c.preferred_partner_name}")

    # Export to JSON
    print()
    print("=" * 80)
    print("EXPORT")
    print("=" * 80)

    output_path = "data/output/constraints_export.json"
    print(f"\nExporting constraints to: {output_path}")
    factory.export_constraints_to_json(constraints, output_path)
    print("Export complete!")

    # Configuration summary
    print()
    print("=" * 80)
    print("CONFIGURATION")
    print("=" * 80)

    if factory.config:
        print("\nObjective function weights:")
        for key, value in factory.config.get('objective_function', {}).items():
            print(f"  {key:30s}: {value:3d}")

        print("\nSpecial rules:")
        for key, value in factory.config.get('special_rules', {}).items():
            if isinstance(value, dict):
                print(f"  {key}:")
                for k, v in value.items():
                    print(f"    {k}: {v}")
            else:
                print(f"  {key}: {value}")

    print()
    print("=" * 80)
    print("Example completed successfully!")
    print("=" * 80)


if __name__ == '__main__':
    main()
