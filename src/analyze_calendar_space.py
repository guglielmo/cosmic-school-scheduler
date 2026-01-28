#!/usr/bin/env python3
"""
Analyze available space in the calendar to determine if rebalancing is feasible.

Measures:
1. Temporal density: How many weeks are occupied vs available per class
2. Trainer capacity headroom: Unused trainer capacity per slot
3. Theoretical maximum splits: How many groups could be split
"""

import csv
from collections import defaultdict


def get_week_from_slot(slot_id):
    """Extract week number from slot_id."""
    return int(slot_id.split('-')[0][1:])


def read_assignments():
    """Read all assignments from calendario_con_formatrici.csv."""
    assignments = []

    with open('data/output/calendario_con_formatrici.csv', 'r') as f:
        reader = csv.DictReader(f)

        for row in reader:
            if row['slot_id'] == 'Totale':
                continue

            for col, val in row.items():
                if col in ['slot_id', 'num_formatrici', 'num_formatrici_disponibili']:
                    continue

                if val and val not in ['X', '-', '']:
                    class_id = int(col.split('-')[0])

                    if ':' not in val:
                        continue

                    parts = val.split(':')
                    if len(parts) != 2:
                        continue

                    lab_part, trainer_part = parts
                    lab_meeting = lab_part.split('/')[0]
                    lab, meeting = lab_meeting.split('-')
                    trainer_id = int(trainer_part.split('-')[0])

                    assignments.append({
                        'slot_id': row['slot_id'],
                        'class_id': class_id,
                        'lab': lab,
                        'meeting': meeting,
                        'trainer_id': trainer_id
                    })

    return assignments


def analyze_temporal_density(assignments):
    """
    Analyze how saturated the calendar is for each class.

    Returns:
        dict: class_id -> {
            'weeks_occupied': int,
            'weeks_available': int,
            'density': float (0-1),
            'labs': list of labs
        }
    """
    # Track weeks occupied per class
    class_weeks = defaultdict(set)
    class_labs = defaultdict(set)

    for assign in assignments:
        week = get_week_from_slot(assign['slot_id'])
        class_weeks[assign['class_id']].add(week)
        class_labs[assign['class_id']].add(assign['lab'])

    # Total weeks: 0-16 = 17 weeks
    total_weeks = 17

    results = {}
    for class_id, weeks in class_weeks.items():
        weeks_occupied = len(weeks)
        weeks_free = total_weeks - weeks_occupied
        density = weeks_occupied / total_weeks

        results[class_id] = {
            'weeks_occupied': weeks_occupied,
            'weeks_free': weeks_free,
            'density': density,
            'labs': sorted(class_labs[class_id])
        }

    return results


def analyze_trainer_capacity():
    """
    Analyze trainer capacity headroom per slot.

    Returns:
        dict: slot_id -> {
            'used': float,
            'available': int,
            'headroom': float,
            'utilization': float
        }
    """
    slot_capacity = {}

    with open('data/output/calendario_con_formatrici.csv', 'r') as f:
        reader = csv.DictReader(f)

        for row in reader:
            if row['slot_id'] == 'Totale':
                continue

            slot_id = row['slot_id']

            try:
                used = float(row.get('num_formatrici', 0))
                available = int(row.get('num_formatrici_disponibili', 0))

                headroom = available - used
                utilization = used / available if available > 0 else 0

                slot_capacity[slot_id] = {
                    'used': used,
                    'available': available,
                    'headroom': headroom,
                    'utilization': utilization
                }
            except (ValueError, TypeError):
                continue

    return slot_capacity


def analyze_groups(assignments):
    """
    Analyze grouped sessions and potential for splitting.

    Returns:
        dict: Statistics about groups
    """
    # Group by (slot, lab, meeting, trainer)
    groups = defaultdict(list)

    for assign in assignments:
        key = (assign['slot_id'], assign['lab'], assign['meeting'], assign['trainer_id'])
        groups[key].append(assign['class_id'])

    # Analyze group sizes
    group_sizes = defaultdict(int)
    for classes in groups.values():
        group_sizes[len(classes)] += 1

    # Calculate theoretical splits
    total_groups = len(groups)
    grouped_sessions = sum(count for size, count in group_sizes.items() if size > 1)
    single_sessions = group_sizes.get(1, 0)

    # If all groups were split to singles: how many formatrici slots needed?
    current_slots = sum(
        (size * 0.5 if size > 1 else 1.0) * count
        for size, count in group_sizes.items()
    )

    if_all_split = sum(size * count for size, count in group_sizes.items())

    additional_slots_needed = if_all_split - current_slots

    return {
        'total_groups': total_groups,
        'grouped_sessions': grouped_sessions,
        'single_sessions': single_sessions,
        'group_sizes': dict(group_sizes),
        'current_formatrici_slots': current_slots,
        'if_all_split': if_all_split,
        'additional_slots_needed': additional_slots_needed
    }


def main():
    print("=" * 80)
    print("CALENDAR SPACE ANALYSIS")
    print("=" * 80)

    # Read data
    print("\nLoading calendar...")
    assignments = read_assignments()
    print(f"  {len(assignments)} total assignments")

    # 1. Temporal density
    print("\n" + "=" * 80)
    print("1. TEMPORAL DENSITY (Weeks occupied per class)")
    print("=" * 80)

    density_data = analyze_temporal_density(assignments)

    # Summary statistics
    densities = [d['density'] for d in density_data.values()]
    avg_density = sum(densities) / len(densities)

    print(f"\nAverage temporal density: {avg_density:.1%}")
    print(f"Classes: {len(density_data)}")

    # Distribution
    density_bins = {
        '< 40%': sum(1 for d in densities if d < 0.4),
        '40-60%': sum(1 for d in densities if 0.4 <= d < 0.6),
        '60-80%': sum(1 for d in densities if 0.6 <= d < 0.8),
        '80-100%': sum(1 for d in densities if d >= 0.8)
    }

    print("\nDensity distribution:")
    for bin_name, count in density_bins.items():
        pct = count / len(densities) * 100
        print(f"  {bin_name:12}: {count:3d} classes ({pct:5.1f}%)")

    # Most saturated classes
    print("\nMost saturated classes (top 10):")
    sorted_classes = sorted(density_data.items(),
                           key=lambda x: x[1]['density'],
                           reverse=True)

    for class_id, data in sorted_classes[:10]:
        print(f"  Class {class_id:2d}: {data['weeks_occupied']:2d}/17 weeks " +
              f"({data['density']:.1%}), {len(data['labs'])} labs")

    # 2. Trainer capacity
    print("\n" + "=" * 80)
    print("2. TRAINER CAPACITY HEADROOM")
    print("=" * 80)

    capacity_data = analyze_trainer_capacity()

    # Summary
    total_headroom = sum(c['headroom'] for c in capacity_data.values())
    avg_utilization = sum(c['utilization'] for c in capacity_data.values()) / len(capacity_data)

    print(f"\nTotal trainer capacity headroom: {total_headroom:.1f} formatrici-slots")
    print(f"Average slot utilization: {avg_utilization:.1%}")

    # Distribution
    util_bins = {
        '0-25%': sum(1 for c in capacity_data.values() if c['utilization'] < 0.25),
        '25-50%': sum(1 for c in capacity_data.values() if 0.25 <= c['utilization'] < 0.5),
        '50-75%': sum(1 for c in capacity_data.values() if 0.5 <= c['utilization'] < 0.75),
        '75-100%': sum(1 for c in capacity_data.values() if c['utilization'] >= 0.75)
    }

    print("\nSlot utilization distribution:")
    for bin_name, count in util_bins.items():
        pct = count / len(capacity_data) * 100
        print(f"  {bin_name:12}: {count:3d} slots ({pct:5.1f}%)")

    # Most saturated slots
    print("\nMost saturated slots (top 10):")
    sorted_slots = sorted(capacity_data.items(),
                         key=lambda x: x[1]['utilization'],
                         reverse=True)

    for slot_id, data in sorted_slots[:10]:
        print(f"  {slot_id}: {data['used']:.1f}/{data['available']} " +
              f"({data['utilization']:.1%}), headroom: {data['headroom']:.1f}")

    # 3. Groups analysis
    print("\n" + "=" * 80)
    print("3. GROUPING ANALYSIS")
    print("=" * 80)

    groups_data = analyze_groups(assignments)

    print(f"\nTotal meeting groups: {groups_data['total_groups']}")
    print(f"  Grouped sessions (2+ classes): {groups_data['grouped_sessions']}")
    print(f"  Single sessions: {groups_data['single_sessions']}")

    print("\nGroup size distribution:")
    for size in sorted(groups_data['group_sizes'].keys()):
        count = groups_data['group_sizes'][size]
        print(f"  Size {size}: {count:3d} groups")

    print(f"\nCurrent formatrici slots used: {groups_data['current_formatrici_slots']:.1f}")
    print(f"If all groups split to singles: {groups_data['if_all_split']:.1f}")
    print(f"Additional slots needed: {groups_data['additional_slots_needed']:.1f}")

    # 4. Feasibility assessment
    print("\n" + "=" * 80)
    print("4. REBALANCING FEASIBILITY ASSESSMENT")
    print("=" * 80)

    additional_needed = groups_data['additional_slots_needed']

    print(f"\nTo split all groups into singles:")
    print(f"  Additional formatrici slots needed: {additional_needed:.1f}")
    print(f"  Total trainer capacity headroom: {total_headroom:.1f}")
    print(f"  Theoretical surplus/deficit: {total_headroom - additional_needed:.1f}")

    if total_headroom >= additional_needed:
        print("\n✓ Theoretically, there IS enough trainer capacity headroom")
        print("  However, practical constraints may prevent full redistribution:")
    else:
        print("\n✗ NOT enough trainer capacity headroom even theoretically")
        print("  Cannot split all groups - trainer availability is the bottleneck")

    print("\nPractical constraints that limit rebalancing:")
    print("  1. Weekly constraint: Classes can only have 1 meeting/week")
    print(f"     Average {avg_density:.1%} of weeks already occupied")
    print("  2. Lab consistency: Moving 1 meeting requires moving all meetings")
    print("     for that lab (e.g., L4 has 5 consecutive meetings)")
    print("  3. Temporal saturation: High-density classes have few free weeks")
    print(f"     {density_bins['80-100%']} classes at 80-100% density")

    print("\n" + "=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)

    if total_headroom < additional_needed:
        print("\n❌ Post-scheduling rebalancing is NOT feasible")
        print("   Insufficient trainer capacity headroom")
    elif avg_density > 0.7:
        print("\n⚠️  Post-scheduling rebalancing is SEVERELY LIMITED")
        print("   High temporal density leaves little room for redistribution")
    else:
        print("\n⚠️  Post-scheduling rebalancing is THEORETICALLY POSSIBLE")
        print("   but PRACTICALLY COMPLEX due to lab consistency requirements")

    print("\nAlternative approach:")
    print("  - Integrate trainer balancing into INITIAL optimizers")
    print("  - Add soft constraint to maximize num_formatrici (reduce grouping)")
    print("  - Balance between minimizing total slots and balancing trainer hours")
    print("  - This is harder but respects lab consistency from the start")

    print("\n" + "=" * 80)


if __name__ == '__main__':
    main()
