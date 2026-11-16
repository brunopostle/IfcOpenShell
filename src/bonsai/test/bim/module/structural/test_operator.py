# This file was generated with the assistance of an AI coding tool.

import math
from types import SimpleNamespace
from unittest import mock

import bpy
import ifcopenshell
import ifcopenshell.api.group
import ifcopenshell.api.root
import ifcopenshell.api.structural
import ifcopenshell.api.unit
import ifcopenshell.guid
import pytest
from mathutils import Vector

import bonsai.tool as tool
from bonsai.bim.module.structural.data import LoadGroupDecorationData
from bonsai.bim.module.structural.decorator import LoadsDecorator
from bonsai.bim.module.structural.operator import PickStructuralLoads, get_load_unit_symbol
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


class TestLoadStructuralLoads(NewFile):
    def test_unused_only(self):
        ifc = ifcopenshell.file(schema="IFC4")
        tool.Ifc.set(ifc)
        point = ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcStructuralPointConnection")
        used = ifcopenshell.api.structural.add_structural_load(
            ifc, name="Used", ifc_class="IfcStructuralLoadSingleForce"
        )
        ifcopenshell.api.structural.add_structural_load(ifc, name="Unused", ifc_class="IfcStructuralLoadSingleForce")
        activity = ifcopenshell.api.structural.add_structural_activity(
            ifc, applied_load=used, structural_member=point, ifc_class="IfcStructuralPointAction"
        )
        case = ifcopenshell.api.structural.add_structural_load_case(ifc, name="Case")
        ifcopenshell.api.group.assign_group(ifc, products=[activity], group=case)
        props = tool.Structural.get_structural_props()
        props.show_unused_loads_only = True  # Which lists the loads again.
        assert [load.name for load in props.structural_loads] == ["Unused"]
        props.show_unused_loads_only = False
        assert sorted(load.name for load in props.structural_loads) == ["Unused", "Used"]


class TestShowStructuralLoadCase(NewFile):
    def test_showing_and_hiding_a_load_case(self):
        ifc = ifcopenshell.file(schema="IFC4")
        tool.Ifc.set(ifc)
        model = ifcopenshell.api.structural.add_structural_analysis_model(ifc)
        case = ifcopenshell.api.structural.add_structural_load_case(ifc, name="Case")
        model.LoadedBy = [case]
        LoadGroupDecorationData.is_loaded = False
        props = tool.Structural.get_structural_props()
        props.activity_type = "Action"
        bpy.ops.bim.show_structural_load_case(load_case=case.id())
        assert props.show_loads and props.load_group_to_show == str(case.id())
        # Clicking the open eye of the case shown hides the loads.
        bpy.ops.bim.show_structural_load_case(load_case=case.id())
        assert not props.show_loads


def region(type, x, y, width, height, data=None):
    return SimpleNamespace(type=type, x=x, y=y, width=width, height=height, data=data)


class TestGetViewUnderMouse:
    def get(self, regions, x, y):
        area = SimpleNamespace(type="VIEW_3D", regions=regions)
        context = SimpleNamespace(window=SimpleNamespace(screen=SimpleNamespace(areas=[area])))
        return PickStructuralLoads.get_view_under_mouse(None, context, SimpleNamespace(mouse_x=x, mouse_y=y))

    def test_the_view_of_the_quarter_of_a_quad_view_under_the_mouse(self):
        left, right = region("WINDOW", 0, 0, 100, 100, "left"), region("WINDOW", 100, 0, 100, 100, "right")
        assert self.get([left, right], 150, 50)[1:] == (right, "right")

    def test_not_under_a_sidebar_lying_over_the_view(self):
        view = region("WINDOW", 0, 0, 200, 100, "view")
        sidebar = region("UI", 150, 0, 50, 100)
        assert self.get([view, sidebar], 175, 50) is None
        assert self.get([view, sidebar], 75, 50)[1] is view

    def test_a_hidden_sidebar_takes_nothing(self):
        view = region("WINDOW", 0, 0, 200, 100, "view")
        assert self.get([view, region("UI", 199, 0, 1, 100)], 199, 50)[1] is view


class TestPickLoads:
    def pick(self, x, y):
        LoadsDecorator.shader_info = [{}]
        LoadsDecorator.pickables = [{"tail": (0.0, 0.0, 0.0), "tip": (100.0, 0.0, 0.0), "activity": 7, "info": 0}]
        # Viewed from the front, as if X and Z were the region's x and y.
        project = lambda region, rv3d, point: Vector((point.x, point.z))
        with mock.patch("bonsai.bim.module.structural.decorator.location_3d_to_region_2d", project):
            try:
                # A region with no labels drawn in it, so that only arrows are picked.
                return LoadsDecorator.pick(mock.Mock(as_pointer=lambda: 0), None, x, y)
            finally:
                LoadsDecorator.pickables, LoadsDecorator.shader_info = [], []

    def test_an_arrow_within_a_few_pixels(self):
        assert self.pick(60, 5)["activity"] == 7
        assert self.pick(60, 15) is None

    def test_not_at_its_tail_where_its_point_is_selected(self):
        assert self.pick(5, 0) is None


class TestLoadCaseSelfWeight(NewFile):
    def test_edit_and_clear_self_weight(self):
        ifc = ifcopenshell.file(schema="IFC4")
        tool.Ifc.set(ifc)
        load_case = ifc.createIfcStructuralLoadCase(
            GlobalId=ifcopenshell.guid.new(),
            Name="Dead Load",
            PredefinedType="LOAD_CASE",
            ActionType="PERMANENT_G",
            ActionSource="DEAD_LOAD_G",
        )
        props = tool.Structural.get_structural_props()

        bpy.ops.bim.enable_editing_structural_load_case(load_case=load_case.id())
        assert props.load_case_has_self_weight is False
        assert tuple(props.load_case_self_weight) == (0.0, 0.0, -1.0)

        props.load_case_has_self_weight = True
        props.load_case_self_weight = (0.5, 0.0, -1.0)
        bpy.ops.bim.edit_structural_load_case()
        assert list(load_case.SelfWeightCoefficients) == [0.5, 0.0, -1.0]

        bpy.ops.bim.enable_editing_structural_load_case(load_case=load_case.id())
        assert props.load_case_has_self_weight is True
        assert tuple(props.load_case_self_weight) == (0.5, 0.0, -1.0)

        props.load_case_has_self_weight = False
        bpy.ops.bim.edit_structural_load_case()
        assert load_case.SelfWeightCoefficients is None


class TestGetLoadUnitSymbol(NewFile):
    def make_file(self) -> ifcopenshell.file:
        ifc = ifcopenshell.file(schema="IFC4")
        tool.Ifc.set(ifc)
        ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcProject")
        ifcopenshell.api.unit.assign_unit(ifc)  # millimetres
        return ifc

    def test_composing_force_over_length_when_no_load_units_are_declared(self):
        self.make_file()
        assert get_load_unit_symbol("IfcStructuralPointConnection") == "N"
        assert get_load_unit_symbol("IfcStructuralCurveMember") == "N/mm"
        assert get_load_unit_symbol("IfcStructuralSurfaceMember") == "N/mm2"

    def test_using_the_declared_load_units(self):
        ifc = self.make_file()
        bpy.context.scene.unit_settings.system = "METRIC"
        ifcopenshell.api.unit.assign_unit(ifc, units=tool.Unit.add_structural_units())
        assert get_load_unit_symbol("IfcStructuralPointConnection") == "kN"
        assert get_load_unit_symbol("IfcStructuralCurveMember") == "kN/m"
        assert get_load_unit_symbol("IfcStructuralSurfaceMember") == "kN/m2"


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
