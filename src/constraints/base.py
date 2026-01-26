"""
Base classes for constraint modeling.

This module defines the foundational classes for expressing and managing
constraints in the Cosmic School scheduling optimizer.
"""

from dataclasses import dataclass, field
from typing import Optional, Any, Dict
from enum import Enum
from abc import ABC, abstractmethod


class ConstraintType(Enum):
    """Type of constraint: hard (must be satisfied) or soft (preference)."""
    HARD = "hard"
    SOFT = "soft"


class ConstraintCategory(Enum):
    """Category of constraint for organization and analysis."""
    TEMPORAL = "temporal"          # Time-related constraints (dates, slots, schedules)
    CAPACITY = "capacity"          # Resource capacity constraints (trainer hours, overlaps)
    SEQUENCING = "sequencing"      # Order and sequence constraints (lab order, prerequisites)
    ASSIGNMENT = "assignment"      # Assignment constraints (class-lab, class-trainer)
    GROUPING = "grouping"          # Grouping constraints (class grouping, max size)


@dataclass
class Constraint(ABC):
    """
    Base class for all constraints.

    Attributes:
        id: Unique identifier for the constraint (e.g., "H01", "S03")
        name: Human-readable name
        type: HARD or SOFT constraint
        category: Category for organization
        description: Detailed description of the constraint
        weight: Weight/penalty for objective function (only for SOFT constraints)
        metadata: Additional metadata for analysis and debugging
    """
    id: str
    name: str
    type: ConstraintType
    category: ConstraintCategory
    description: str
    weight: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate constraint configuration."""
        if self.type == ConstraintType.SOFT and self.weight is None:
            raise ValueError(f"Soft constraint {self.id} must have a weight")
        if self.type == ConstraintType.HARD and self.weight is not None:
            raise ValueError(f"Hard constraint {self.id} should not have a weight")

    def to_dict(self) -> Dict[str, Any]:
        """Convert constraint to dictionary representation."""
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type.value,
            'category': self.category.value,
            'description': self.description,
            'weight': self.weight,
            'metadata': self.metadata,
            'class_name': self.__class__.__name__
        }

    def __repr__(self) -> str:
        """String representation for debugging."""
        weight_str = f", weight={self.weight}" if self.weight else ""
        return f"{self.__class__.__name__}(id='{self.id}', name='{self.name}'{weight_str})"


@dataclass
class HardConstraint(Constraint):
    """
    Hard constraint that must be satisfied.

    Hard constraints are inviolable and must always be satisfied for a
    solution to be considered feasible.
    """
    type: ConstraintType = field(default=ConstraintType.HARD, init=False)

    @abstractmethod
    def validate(self, solution: Any) -> bool:
        """
        Validate if the constraint is satisfied by the solution.

        Args:
            solution: The solution to validate (structure depends on optimizer)

        Returns:
            True if constraint is satisfied, False otherwise
        """
        pass

    @abstractmethod
    def add_to_model(self, model: Any, variables: Any) -> None:
        """
        Add this constraint to the CP-SAT model.

        Args:
            model: OR-Tools CP-SAT model
            variables: Dictionary of decision variables
        """
        pass


@dataclass
class SoftConstraint(Constraint):
    """
    Soft constraint representing a preference.

    Soft constraints are preferences that should be optimized in the
    objective function. Violations contribute to the penalty being minimized.
    """
    type: ConstraintType = field(default=ConstraintType.SOFT, init=False)
    weight: int = 1

    @abstractmethod
    def penalty(self, solution: Any) -> float:
        """
        Calculate penalty for this constraint given a solution.

        Args:
            solution: The solution to evaluate

        Returns:
            Penalty value (0 = fully satisfied, higher = more violated)
        """
        pass

    @abstractmethod
    def add_to_objective(self, model: Any, variables: Any) -> Any:
        """
        Add this constraint's contribution to the objective function.

        Args:
            model: OR-Tools CP-SAT model
            variables: Dictionary of decision variables

        Returns:
            Objective term (expression to be minimized/maximized)
        """
        pass


class ConstraintViolation:
    """
    Represents a constraint violation for reporting and debugging.
    """
    def __init__(self, constraint: Constraint, message: str, severity: str = "error"):
        self.constraint = constraint
        self.message = message
        self.severity = severity  # "error" for hard, "warning" for soft

    def __repr__(self) -> str:
        return f"ConstraintViolation({self.constraint.id}: {self.message})"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'constraint_id': self.constraint.id,
            'constraint_name': self.constraint.name,
            'constraint_type': self.constraint.type.value,
            'message': self.message,
            'severity': self.severity
        }
