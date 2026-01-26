"""
Basic tests for constraint system.

Run with: pytest tests/test_constraints.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import pytest
from constraints import (
    ConstraintFactory,
    ConstraintType,
    ConstraintCategory,
    HardConstraint,
    SoftConstraint,
    TrainerTotalHoursConstraint,
    MaximizeGroupingConstraint,
)


class TestConstraintBase:
    """Test base constraint classes."""

    def test_hard_constraint_creation(self):
        """Test creating a hard constraint."""
        constraint = TrainerTotalHoursConstraint(
            trainer_id=1,
            trainer_name="Test Trainer",
            max_hours=100
        )

        assert constraint.id == "H01"
        assert constraint.type == ConstraintType.HARD
        assert constraint.category == ConstraintCategory.CAPACITY
        assert constraint.weight is None
        assert constraint.max_hours == 100

    def test_soft_constraint_creation(self):
        """Test creating a soft constraint."""
        constraint = MaximizeGroupingConstraint(weight=20)

        assert constraint.id == "S01"
        assert constraint.type == ConstraintType.SOFT
        assert constraint.category == ConstraintCategory.GROUPING
        assert constraint.weight == 20

    def test_hard_constraint_cannot_have_weight(self):
        """Test that hard constraints reject weight parameter."""
        with pytest.raises(ValueError):
            # Try to create hard constraint with weight via dict
            from dataclasses import replace
            base = TrainerTotalHoursConstraint(
                trainer_id=1,
                trainer_name="Test",
                max_hours=100
            )
            # Manually set weight (should fail in __post_init__)
            base.weight = 10
            base.__post_init__()

    def test_soft_constraint_requires_weight(self):
        """Test that soft constraints require weight."""
        # MaximizeGroupingConstraint has default weight, so we test via base class
        from constraints.base import SoftConstraint, ConstraintCategory
        from dataclasses import dataclass

        with pytest.raises(ValueError):
            @dataclass
            class TestSoftConstraint(SoftConstraint):
                id: str = "TEST"
                name: str = "Test"
                category: ConstraintCategory = ConstraintCategory.TEMPORAL
                description: str = "Test"
                weight: int = None  # Will trigger error

                def penalty(self, solution):
                    return 0

                def add_to_objective(self, model, variables):
                    return None

            TestSoftConstraint()


class TestConstraintFactory:
    """Test constraint factory."""

    @pytest.fixture
    def factory(self):
        """Create factory instance."""
        return ConstraintFactory(
            data_dir="data/input",
            config_path="config/constraint_weights.yaml"
        )

    def test_factory_initialization(self, factory):
        """Test factory initializes correctly."""
        assert factory.data_dir.name == "input"
        assert isinstance(factory.config, dict)

    def test_load_csv_data(self, factory):
        """Test loading CSV data."""
        factory.load_all_csv_data()

        # Check expected CSV files are loaded
        assert 'formatrici' in factory.csv_data
        assert 'classi' in factory.csv_data
        assert 'laboratori' in factory.csv_data

        # Check formatrici data
        formatrici = factory.csv_data['formatrici']
        assert len(formatrici) > 0
        assert 'formatrice_id' in formatrici[0]
        assert 'nome' in formatrici[0]
        assert 'ore_generali' in formatrici[0]

    def test_build_constraints(self, factory):
        """Test building constraints from CSV."""
        constraints = factory.build_all_constraints()

        assert len(constraints) > 0

        # Check we have both hard and soft constraints
        hard = [c for c in constraints if c.type == ConstraintType.HARD]
        soft = [c for c in constraints if c.type == ConstraintType.SOFT]

        assert len(hard) > 0
        assert len(soft) > 0

    def test_constraint_summary(self, factory):
        """Test generating constraint summary."""
        constraints = factory.build_all_constraints()
        summary = factory.get_constraint_summary(constraints)

        assert 'total' in summary
        assert 'by_type' in summary
        assert 'by_category' in summary
        assert summary['total'] == len(constraints)

    def test_parse_weekday_list(self, factory):
        """Test parsing weekday lists."""
        result = factory._parse_weekday_list("lun,mar,mer")
        assert result == ["lun", "mar", "mer"]

        result = factory._parse_weekday_list("")
        assert result == []

    def test_parse_dettagli(self, factory):
        """Test parsing dettagli field."""
        # Test simple time of day
        result = factory._parse_dettagli("mattina")
        assert result['time_of_day'] == 'mattina'

        # Test partial meetings
        result = factory._parse_dettagli("solo 2 incontri")
        assert result['partial_meetings'] == 2

        # Test afternoon requirement
        result = factory._parse_dettagli("un incontro deve essere di pomeriggio")
        assert result['one_afternoon'] is True

        # Test complex case
        result = factory._parse_dettagli("2 incontri devono essere di pomeriggio ma non in settimane consecutive")
        assert result['afternoon_count'] == 2

    def test_export_constraints_json(self, factory, tmp_path):
        """Test exporting constraints to JSON."""
        constraints = factory.build_all_constraints()

        output_file = tmp_path / "test_constraints.json"
        factory.export_constraints_to_json(constraints, str(output_file))

        assert output_file.exists()

        # Check JSON is valid
        import json
        with open(output_file, 'r') as f:
            data = json.load(f)

        assert isinstance(data, list)
        assert len(data) == len(constraints)
        assert 'id' in data[0]
        assert 'name' in data[0]
        assert 'type' in data[0]


class TestConstraintIntegration:
    """Integration tests for constraint system."""

    def test_all_trainers_have_constraints(self):
        """Test that all trainers from CSV have constraints."""
        factory = ConstraintFactory()
        constraints = factory.build_all_constraints()

        # Get trainer IDs from constraints
        trainer_hours = [c for c in constraints if isinstance(c, TrainerTotalHoursConstraint)]
        trainer_ids = {c.trainer_id for c in trainer_hours}

        # Should have 4 trainers
        assert len(trainer_ids) == 4

    def test_constraint_ids_unique(self):
        """Test that constraint class IDs are unique."""
        factory = ConstraintFactory()
        constraints = factory.build_all_constraints()

        # Get all unique constraint class IDs (not instance IDs)
        class_ids = {c.__class__.__name__: c.id for c in constraints}

        # Each class should have a unique ID
        seen_ids = set()
        for class_name, constraint_id in class_ids.items():
            assert constraint_id not in seen_ids, f"Duplicate ID {constraint_id} for {class_name}"
            seen_ids.add(constraint_id)

    def test_all_categories_present(self):
        """Test that constraints cover all categories."""
        factory = ConstraintFactory()
        constraints = factory.build_all_constraints()

        categories = {c.category for c in constraints}

        # Should have constraints in most categories
        # (not necessarily all, but at least these critical ones)
        assert ConstraintCategory.TEMPORAL in categories
        assert ConstraintCategory.CAPACITY in categories
        assert ConstraintCategory.GROUPING in categories


def test_constraint_to_dict():
    """Test constraint serialization to dict."""
    constraint = TrainerTotalHoursConstraint(
        trainer_id=1,
        trainer_name="Test",
        max_hours=100
    )

    data = constraint.to_dict()

    assert data['id'] == "H01"
    assert data['name'] == "Trainer Total Hours"
    assert data['type'] == 'hard'
    assert data['category'] == 'capacity'
    assert data['class_name'] == 'TrainerTotalHoursConstraint'


def test_constraint_repr():
    """Test constraint string representation."""
    constraint = TrainerTotalHoursConstraint(
        trainer_id=1,
        trainer_name="Test",
        max_hours=100
    )

    repr_str = repr(constraint)
    assert "TrainerTotalHoursConstraint" in repr_str
    assert "H01" in repr_str
    assert "Trainer Total Hours" in repr_str


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
