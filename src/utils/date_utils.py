"""
Date utility functions for Cosmic School Optimizer.

Handles conversion between calendar dates and (week, day, slot) tuples.
"""

from datetime import datetime, timedelta
from typing import Tuple, Optional, List
import re


class DateMapper:
    """
    Maps calendar dates to scheduling variables (week, day, slot).

    School year runs from late January to mid-May with Easter break.

    Windows:
    - Window 1: 29/01/2026 - 01/04/2026 (weeks 0-9)
    - Easter break: 02/04/2026 - 12/04/2026
    - Window 2: 13/04/2026 - 30/05/2026 (weeks 10-16)
    """

    # Inizio anno scolastico
    YEAR_START = datetime(2026, 1, 29)  # Giovedì 29 gennaio 2026

    # Finestre temporali
    WINDOW1_START = datetime(2026, 1, 29)  # Giovedì 29 gennaio 2026
    WINDOW1_END = datetime(2026, 4, 1)

    EASTER_START = datetime(2026, 4, 2)
    EASTER_END = datetime(2026, 4, 12)

    WINDOW2_START = datetime(2026, 4, 13)
    WINDOW2_END = datetime(2026, 5, 30)  # Esteso a W16 (settimana 25-30 maggio)

    # Mappings
    WEEKDAY_TO_NUM = {
        "lunedì": 0, "lun": 0,
        "martedì": 1, "mar": 1,
        "mercoledì": 2, "mer": 2,
        "giovedì": 3, "gio": 3,
        "venerdì": 4, "ven": 4,
        "sabato": 5, "sab": 5
    }

    SLOT_TO_NUM = {
        "mattino1": 1, "mattina1": 1, "09:00-11:00": 1,
        "mattino2": 2, "mattina2": 2, "11:00-13:00": 2,
        "pomeriggio": 3, "14:00-16:00": 3, "14:00-18:00": 3
    }

    def __init__(self):
        """Initialize date mapper with week boundaries."""
        self.week_starts = self._compute_week_starts()

    def _compute_week_starts(self) -> List[datetime]:
        """
        Compute start date of each week (always Monday).

        Returns:
            List of 17 datetime objects (start of each week = Monday)
        """
        weeks = []

        # Find the Monday of the week containing WINDOW1_START
        # 28/01/2026 is Wednesday (weekday=2), so Monday is 2 days before
        first_monday = self.WINDOW1_START - timedelta(days=self.WINDOW1_START.weekday())

        # Window 1: weeks 0-9 (10 settimane da lunedì)
        current = first_monday
        for i in range(10):
            weeks.append(current)
            current += timedelta(weeks=1)

        # Window 2: weeks 10-16 (7 settimane, dopo Pasqua)
        # Find Monday of week containing WINDOW2_START
        window2_monday = self.WINDOW2_START - timedelta(days=self.WINDOW2_START.weekday())
        current = window2_monday
        for i in range(7):
            weeks.append(current)
            current += timedelta(weeks=1)

        return weeks

    def date_to_week_day(self, date: datetime) -> Tuple[int, int]:
        """
        Convert date to (week_num, day_num).

        Args:
            date: datetime object

        Returns:
            (week_num, day_num) where:
                week_num: 0-16 (settimana dell'anno scolastico)
                day_num: 0-5 (0=lun, 5=sab)
        """
        # Check if in valid windows
        if not (self.WINDOW1_START <= date <= self.WINDOW1_END or
                self.WINDOW2_START <= date <= self.WINDOW2_END):
            raise ValueError(f"Date {date} is outside valid scheduling windows")

        # Trova la settimana
        for week_num, week_start in enumerate(self.week_starts):
            week_end = week_start + timedelta(days=6)
            if week_start <= date <= week_end:
                # Giorno della settimana (0=lun, 6=dom)
                day_num = date.weekday()
                if day_num == 6:  # domenica non permessa
                    raise ValueError(f"Date {date} is Sunday (not allowed)")
                return week_num, day_num

        raise ValueError(f"Date {date} not found in any week")

    def parse_date_string(self, date_str: str) -> Optional[datetime]:
        """
        Parse various date string formats.

        Formats supported:
        - "2026-02-26"
        - "26/02/2026"
        - "26-02-2026"

        Args:
            date_str: String representing a date

        Returns:
            datetime object or None if parsing fails
        """
        # Remove extra whitespace
        date_str = date_str.strip()

        # Try different formats
        formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%d.%m.%Y"
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        return None

    def parse_datetime_range(self, datetime_str: str) -> Optional[Tuple[datetime, int]]:
        """
        Parse date-time range string to extract date and time slot.

        Formats:
        - "2026-02-26 09:00-13:00" -> (date, slot)
        - "26/02/2026 mattina" -> (date, slot)

        Args:
            datetime_str: String with date and time info

        Returns:
            (datetime, slot_num) or None
        """
        # Try to extract date and time parts
        match = re.match(r'(\d{4}-\d{2}-\d{2}|\d{2}[/-]\d{2}[/-]\d{4})\s+(.+)', datetime_str)

        if not match:
            return None

        date_part = match.group(1)
        time_part = match.group(2).strip().lower()

        # Parse date
        date = self.parse_date_string(date_part)
        if not date:
            return None

        # Parse time slot
        slot = None

        # Check for time range (e.g., "09:00-13:00")
        if '-' in time_part and ':' in time_part:
            start_time = time_part.split('-')[0].strip()
            if start_time.startswith('09'):
                slot = 1  # mattino1
            elif start_time.startswith('11'):
                slot = 2  # mattino2
            elif start_time.startswith('14'):
                slot = 3  # pomeriggio

        # Check for named slots
        if slot is None:
            for slot_name, slot_num in self.SLOT_TO_NUM.items():
                if slot_name in time_part:
                    slot = slot_num
                    break

        if slot:
            return date, slot

        return None

    def week_day_to_date(self, week: int, day: int) -> datetime:
        """
        Convert (week, day) back to date.

        Args:
            week: Week number (0-16)
            day: Day number (0-5)

        Returns:
            datetime object
        """
        if not 0 <= week <= 16:
            raise ValueError(f"Week {week} out of range (0-16)")
        if not 0 <= day <= 5:
            raise ValueError(f"Day {day} out of range (0-5)")

        week_start = self.week_starts[week]
        return week_start + timedelta(days=day)

    def slot_to_time_str(self, slot: int) -> str:
        """Convert slot number to time string."""
        slot_times = {
            1: "09:00-11:00",
            2: "11:00-13:00",
            3: "14:00-16:00"
        }
        return slot_times.get(slot, "unknown")

    def format_datetime(self, week: int, day: int, slot: int) -> str:
        """
        Format (week, day, slot) as human-readable date-time.

        Returns:
            String like "26/02/2026 09:00-11:00"
        """
        date = self.week_day_to_date(week, day)
        time_str = self.slot_to_time_str(slot)
        return f"{date.strftime('%d/%m/%Y')} {time_str}"
