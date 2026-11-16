# This file was generated with the assistance of an AI coding tool.

import bpy
import ifcopenshell
import ifcopenshell.api.group
import ifcopenshell.api.root
import ifcopenshell.api.structural
import ifcopenshell.guid
import pytest

import bonsai.tool as tool
from test.bim.bootstrap import NewFile


class TestLoadBoundaryConditions(NewFile):
    def test_filtering_duplicate_names(self):
        ifc = ifcopenshell.file(schema="IFC4")
        tool.Ifc.set(ifc)
        ifc.createIfcBoundaryNodeCondition(Name="Fixed")
        ifc.createIfcBoundaryNodeCondition(Name="Fixed")
        ifc.createIfcBoundaryNodeCondition(Name="Pinned")
        props = tool.Structural.get_structural_props()
        props.filtered_boundary_conditions = True
        bpy.ops.bim.load_boundary_conditions()
        assert sorted(c.name for c in props.boundary_conditions) == ["Pinned"]


class TestSolveFactoredResultant(NewFile):
    def setup_case(self):
        """A load case with a Coefficient of 1.5. One force is in it directly; the other through a load group
        assigned to it by a factor of 2, so it is drawn at 1.5 x 2 = 3 times its value."""
        ifc = ifcopenshell.file(schema="IFC4")
        tool.Ifc.set(ifc)
        point = ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcStructuralPointConnection")
        case = ifcopenshell.api.structural.add_structural_load_case(ifc, name="Case")
        case.Coefficient = 1.5
        group = ifcopenshell.api.structural.add_structural_load_group(ifc, name="Group")
        ifcopenshell.api.group.assign_group(ifc, products=[group], group=case)
        activities = []
        for name, force in (("Known", (10.0, 0.0, 0.0)), ("Unknown", (0.0, 0.0, 1.0))):
            load = ifcopenshell.api.structural.add_structural_load(
                ifc, name=name, ifc_class="IfcStructuralLoadSingleForce"
            )
            load.ForceX, load.ForceY, load.ForceZ = force
            activities.append(
                ifcopenshell.api.structural.add_structural_activity(
                    ifc, applied_load=load, structural_member=point, ifc_class="IfcStructuralPointAction"
                )
            )
        ifcopenshell.api.group.assign_group(ifc, products=[activities[0]], group=case)
        ifc.createIfcRelAssignsToGroupByFactor(
            ifcopenshell.guid.new(), RelatedObjects=[activities[1]], RelatingGroup=group, Factor=2.0
        )
        return case, activities

    def test_factor_of_each_activity_in_its_load_case(self):
        case, (known, unknown) = self.setup_case()
        assert tool.Structural.get_activity_factor(known, case) == pytest.approx(1.5)
        assert tool.Structural.get_activity_factor(unknown, case) == pytest.approx(3.0)

    def test_solving_in_the_forces_drawn(self):
        from bonsai.bim.module.structural.operator import solve_factored

        case, activities = self.setup_case()
        # Drawn, the known force is 15 along X; for a resultant at 45 deg the unknown must be drawn 15 along Z,
        # which is 5 of its own value, times 3.
        solved, resultant, error = solve_factored(
            activities,
            [(10.0, 0.0, 0.0), (0.0, 0.0, 1.0)],
            [(True, True), (False, True)],
            (1.0, 0.0, 1.0),
            (False, True),
        )
        assert not error
        assert solved[0] == pytest.approx((10.0, 0.0, 0.0))
        assert solved[1] == pytest.approx((0.0, 0.0, 5.0))
        assert resultant == pytest.approx((15.0, 0.0, 15.0))

    def test_refusing_an_unknown_with_a_factor_of_zero(self):
        from bonsai.bim.module.structural.operator import solve_factored

        case, activities = self.setup_case()
        case.Coefficient = 0.0
        _, _, error = solve_factored(
            activities,
            [(10.0, 0.0, 0.0), (0.0, 0.0, 1.0)],
            [(True, True), (False, True)],
            (1.0, 0.0, 1.0),
            (False, True),
        )
        assert "factor of 0" in error
