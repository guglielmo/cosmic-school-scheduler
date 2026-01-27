#!/usr/bin/env python3
"""
Build complete calendar of available time slots.

Generates all available slots from January 29 to end of May,
following the project's scheduling windows and constraints.

Output format: sWW-mm-dd-wd-slot (e.g., "s01-02-02-lun-M1")
"""

from datetime import datetime, timedelta
import csv
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from date_utils import DateMapper


# Weekday names in Italian (abbreviated)
WEEKDAY_NAMES = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]

# Slot names
SLOT_NAMES = {
    1: "M1",  # mattina1 09:00-11:00
    2: "M2",  # mattina2 11:00-13:00
    3: "P"    # pomeriggio 14:00-16:00
}


def generate_all_slots():
    """
    Generate all available time slots.

    Returns:
        List of dicts with slot information:
        - slot_id: formatted as "mm-dd-wd-slot" (e.g., "02-02-lun-M1")
        - date: datetime object
        - week_num: week number (0-15)
        - day_num: day number (0-5, Mon-Sat)
        - weekday: weekday name (lun, mar, ...)
        - slot_num: slot number (1-3)
        - slot_name: slot name (M1, M2, P)
        - time_range: time range (e.g., "09:00-11:00")
    """
    mapper = DateMapper()
    slots = []

    # Iterate over all 16 weeks
    for week in range(16):
        # Iterate over all days (0=Mon, 5=Sat)
        for day in range(6):  # Mon-Sat only (no Sunday)
            # Get the actual date
            date = mapper.week_day_to_date(week, day)

            # Check if date is within valid windows
            in_window1 = mapper.WINDOW1_START <= date <= mapper.WINDOW1_END
            in_window2 = mapper.WINDOW2_START <= date <= mapper.WINDOW2_END

            if not (in_window1 or in_window2):
                continue  # Skip dates in Easter break

            # Determine number of slots for this day
            # Saturday: only 2 slots (M1, M2)
            # Mon-Fri: 3 slots (M1, M2, P)
            num_slots = 2 if day == 5 else 3

            # Generate slots for this day
            for slot in range(1, num_slots + 1):
                weekday = WEEKDAY_NAMES[day]
                slot_name = SLOT_NAMES[slot]
                time_range = mapper.slot_to_time_str(slot)

                # Format: sWW-mm-dd-wd-slot
                slot_id = f"s{week:02d}-{date.month:02d}-{date.day:02d}-{weekday}-{slot_name}"

                slots.append({
                    "slot_id": slot_id,
                    "date": date.strftime("%Y-%m-%d"),
                    "date_formatted": date.strftime("%d/%m/%Y"),
                    "week_num": week,
                    "day_num": day,
                    "weekday": weekday,
                    "slot_num": slot,
                    "slot_name": slot_name,
                    "time_range": time_range,
                    "full_datetime": f"{date.strftime('%d/%m/%Y')} {time_range}"
                })

    return slots


def save_slots_to_csv(slots, output_path):
    """Save slots to CSV file."""
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            "slot_id",
            "date",
            "date_formatted",
            "week_num",
            "day_num",
            "weekday",
            "slot_num",
            "slot_name",
            "time_range",
            "full_datetime"
        ])
        writer.writeheader()
        writer.writerows(slots)


def print_summary(slots):
    """Print summary statistics."""
    print(f"\n📅 Total slots generated: {len(slots)}")

    # Count by week
    weeks = {}
    for slot in slots:
        w = slot["week_num"]
        weeks[w] = weeks.get(w, 0) + 1

    print(f"\n📊 Slots per week:")
    for w in sorted(weeks.keys()):
        print(f"   Week {w:2d}: {weeks[w]:3d} slots")

    # Count by slot type
    slot_types = {}
    for slot in slots:
        st = slot["slot_name"]
        slot_types[st] = slot_types.get(st, 0) + 1

    print(f"\n🕐 Slots by type:")
    for st in ["M1", "M2", "P"]:
        count = slot_types.get(st, 0)
        print(f"   {st}: {count:3d} slots")

    # Date range
    first = slots[0]["date_formatted"]
    last = slots[-1]["date_formatted"]
    print(f"\n📆 Date range: {first} - {last}")

    # Example slots
    print(f"\n📝 Example slots:")
    for i in [0, 1, 2, len(slots)//2, -3, -2, -1]:
        s = slots[i]
        print(f"   {s['slot_id']:20s} → {s['full_datetime']}")


def main():
    """Main entry point."""
    print("🚀 Building slots calendar...")
    print("=" * 60)

    # Generate slots
    slots = generate_all_slots()

    # Print summary
    print_summary(slots)

    # Save to CSV
    output_dir = Path(__file__).parent.parent / "data" / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "slots_calendar.csv"

    save_slots_to_csv(slots, output_path)
    print(f"\n✅ Saved to: {output_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
