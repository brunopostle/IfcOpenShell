# This file was generated with the assistance of an AI coding tool.

import math

import bpy
import ifcopenshell
import ifcopenshell.api.group
import ifcopenshell.api.root
import ifcopenshell.api.structural
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


class TestKeepingTheDirectionOfAForceOfNone(NewFile):
    def setup_point(self):
        ifc = ifcopenshell.file(schema="IFC4")
        tool.Ifc.set(ifc)
        ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcProject")
        case = ifcopenshell.api.structural.add_structural_load_case(ifc, name="Case")
        point = ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcStructuralPointConnection")
        return ifc, case, point

    def add_force(self, ifc, case, point, name, force):
        load = ifcopenshell.api.structural.add_structural_load(ifc, name=name, ifc_class="IfcStructuralLoadSingleForce")
        load.ForceX, load.ForceY, load.ForceZ = force
        activity = ifcopenshell.api.structural.add_structural_activity(
            ifc, applied_load=load, structural_member=point, ifc_class="IfcStructuralPointAction"
        )
        ifcopenshell.api.group.assign_group(ifc, products=[activity], group=case)
        return load, activity

    def test_naming_a_force_of_none_in_the_direction_it_had(self):
        from bonsai.bim.module.structural.operator import get_named_force_direction, write_forces

        ifc, case, point = self.setup_point()
        c, s = math.cos(math.radians(30)), math.sin(math.radians(30))
        load, _ = self.add_force(ifc, case, point, "10 N at 30 deg Q8", (10 * c, 0.0, -10 * s))
        write_forces({load: (1e-15, 0.0, 0.0)})  # Found to be none, as a solve finds it, give or take rounding.
        assert load.Name == "0 N at 30 deg Q8"
        assert tool.Structural.get_force(load) == (0.0, 0.0, 0.0)
        assert get_named_force_direction(load) == pytest.approx((c, 0.0, -s))

    def test_solving_a_force_of_none_along_its_named_direction(self):
        from bonsai.bim.module.structural.operator import get_resolved_forces

        ifc, case, point = self.setup_point()
        _, along_x = self.add_force(ifc, case, point, "X 1 N", (1.0, 0.0, 0.0))
        _, none = self.add_force(ifc, case, point, "0 N at 30 deg Q8", (0.0, 0.0, 0.0))
        for activity in (along_x, none):
            tool.Structural.set_locks(activity, False, True)  # Both magnitudes to be found.
        tool.Structural.set_resultant(point, case, True, True, (20.0, 0.0, -5.0))
        forces, error = get_resolved_forces(none)
        assert not error
        # Down 5 at 30 deg below +X is 10 along that line: 8.66 along X, the other force the rest of 20.
        # By load here; by applied load once solving at one item only is in.
        assert forces.get(none, forces.get(none.AppliedLoad)) == pytest.approx(
            (10 * math.cos(math.radians(30)), 0.0, -5.0)
        )
