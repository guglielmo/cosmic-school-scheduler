"""
Constraint modeling system for Cosmic School scheduling optimizer.

This package provides a structured way to express and manage constraints
based on CSV data and INTERPRETAZIONE_VINCOLI.md specifications.
"""

from .base import (
    Constraint,
    HardConstraint,
    SoftConstraint,
    ConstraintType,
    ConstraintCategory,
    ConstraintViolation,
    MeetingKey,
)

from .hard_constraints import (
    TrainerTotalHoursConstraint,
    TrainerAvailabilityConstraint,
    FixedDatesConstraint,
    ClassLabAssignmentConstraint,
    LabTimeOfDayConstraint,
    ClassTimeSlotsConstraint,
    ClassExcludedDatesConstraint,
    MaxOneMeetingPerWeekConstraint,
    Lab8LastConstraint,
    NoTrainerOverlapConstraint,
    SchedulingPeriodConstraint,
    MaxGroupSizeConstraint,
    LabCompletionConstraint,
    Lab9BeforeLab5Constraint,
)

from .soft_constraints import (
    MaximizeGroupingConstraint,
    TrainerContinuityConstraint,
    TrainerWeeklyHoursConstraint,
    TrainerTimePreferenceConstraint,
    PreferredGroupingConstraint,
    LabSequenceConstraint,
    FifthYearPriorityConstraint,
    TimeSlotVariationConstraint,
    BalanceTrainerLoadConstraint,
    MinimizeLateMaySchedulingConstraint,
)

from .special_rules import (
    CitizenScienceGapConstraint,
    PartialLabMeetingsConstraint,
    MultiMeetingAfternoonConstraint,
    OneMeetingTimeConstraint,
    WeekdayTimeSpecificConstraint,
    IgnoreExternalLabsConstraint,
    SaturdayOnlyMargheritaConstraint,
)

from .factory import ConstraintFactory

__all__ = [
    # Base classes
    'Constraint',
    'HardConstraint',
    'SoftConstraint',
    'ConstraintType',
    'ConstraintCategory',
    'ConstraintViolation',
    'MeetingKey',
    # Factory
    'ConstraintFactory',
    # Hard constraints
    'TrainerTotalHoursConstraint',
    'TrainerAvailabilityConstraint',
    'FixedDatesConstraint',
    'ClassLabAssignmentConstraint',
    'LabTimeOfDayConstraint',
    'ClassTimeSlotsConstraint',
    'ClassExcludedDatesConstraint',
    'MaxOneMeetingPerWeekConstraint',
    'Lab8LastConstraint',
    'NoTrainerOverlapConstraint',
    'SchedulingPeriodConstraint',
    'MaxGroupSizeConstraint',
    'LabCompletionConstraint',
    'Lab9BeforeLab5Constraint',
    # Soft constraints
    'MaximizeGroupingConstraint',
    'TrainerContinuityConstraint',
    'TrainerWeeklyHoursConstraint',
    'TrainerTimePreferenceConstraint',
    'PreferredGroupingConstraint',
    'LabSequenceConstraint',
    'FifthYearPriorityConstraint',
    'TimeSlotVariationConstraint',
    'BalanceTrainerLoadConstraint',
    'MinimizeLateMaySchedulingConstraint',
    # Special rules
    'CitizenScienceGapConstraint',
    'PartialLabMeetingsConstraint',
    'MultiMeetingAfternoonConstraint',
    'OneMeetingTimeConstraint',
    'WeekdayTimeSpecificConstraint',
    'IgnoreExternalLabsConstraint',
    'SaturdayOnlyMargheritaConstraint',
]

__version__ = '1.0.0'
