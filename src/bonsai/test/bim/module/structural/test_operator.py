# This file was generated with the assistance of an AI coding tool.

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


class TestSolvingAtOneItemOnly(NewFile):
    def setup_shared_load(self):
        """Point A has a known force along X and an unknown force up; the unknown's load is also applied at B."""
        ifc = ifcopenshell.file(schema="IFC4")
        tool.Ifc.set(ifc)
        ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcProject")
        case = ifcopenshell.api.structural.add_structural_load_case(ifc, name="Case")
        a, b = (ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcStructuralPointConnection") for _ in range(2))
        loads = {}
        for name, force in (("Known", (10.0, 0.0, 0.0)), ("Shared", (0.0, 0.0, 1.0))):
            load = ifcopenshell.api.structural.add_structural_load(
                ifc, name=name, ifc_class="IfcStructuralLoadSingleForce"
            )
            load.ForceX, load.ForceY, load.ForceZ = force
            loads[name] = load
        add = lambda load, point: ifcopenshell.api.structural.add_structural_activity(
            ifc, applied_load=load, structural_member=point, ifc_class="IfcStructuralPointAction"
        )
        known_at_a, shared_at_a, shared_at_b = add(loads["Known"], a), add(loads["Shared"], a), add(loads["Shared"], b)
        ifcopenshell.api.group.assign_group(ifc, products=[known_at_a, shared_at_a, shared_at_b], group=case)
        tool.Structural.set_locks(shared_at_a, False, True)  # Its magnitude is to be found.
        tool.Structural.set_resultant(a, case, False, True, (1.0, 0.0, 1.0))  # At 45 degrees.
        return loads["Shared"], shared_at_a, shared_at_b

    def test_a_load_shared_with_another_item_is_copied_before_it_changes(self):
        from bonsai.bim.module.structural.operator import get_resolved_forces, write_activity_forces

        shared, shared_at_a, shared_at_b = self.setup_shared_load()
        forces, error = get_resolved_forces(shared_at_a)
        assert not error and forces[shared_at_a] == pytest.approx((0.0, 0.0, 10.0))
        write_activity_forces(forces)
        assert shared_at_a.AppliedLoad != shared
        assert tool.Structural.get_force(shared_at_a.AppliedLoad) == pytest.approx((0.0, 0.0, 10.0))
        # B keeps the load, unchanged.
        assert shared_at_b.AppliedLoad == shared
        assert tool.Structural.get_force(shared) == pytest.approx((0.0, 0.0, 1.0))

    def test_a_load_used_once_is_changed_in_place(self):
        from bonsai.bim.module.structural.operator import get_resolved_forces, write_activity_forces

        shared, shared_at_a, shared_at_b = self.setup_shared_load()
        ifcopenshell.api.root.remove_product(tool.Ifc.get(), product=shared_at_b)
        forces, _ = get_resolved_forces(shared_at_a)
        write_activity_forces(forces)
        assert shared_at_a.AppliedLoad == shared
        assert tool.Structural.get_force(shared) == pytest.approx((0.0, 0.0, 10.0))
