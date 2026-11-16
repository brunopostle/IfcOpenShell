# This file was generated with the assistance of an AI coding tool.

import bpy
import ifcopenshell
import ifcopenshell.api.root
import ifcopenshell.api.structural

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


class TestNamingTheMomentCentre(NewFile):
    def test_the_centre_is_written_by_its_points_name(self):
        from bonsai.bim.module.structural.report import get_centre_symbols

        ifc = ifcopenshell.file(schema="IFC4")
        tool.Ifc.set(ifc)
        case = ifcopenshell.api.structural.add_structural_load_case(ifc, name="Case")
        assert tool.Structural.get_centre_symbol(case) == "A"  # No centre: the textbook's A.
        point = ifcopenshell.api.root.create_entity(ifc, ifc_class="IfcStructuralPointConnection", name="B")
        tool.Structural.set_moment_centre(case, point)
        assert tool.Structural.get_centre_symbol(case) == "B"
        assert get_centre_symbols(case) == ("B", "B")
        point.Name = "Joint 1"  # Too long for a subscript of letters: set as text.
        assert get_centre_symbols(case) == (r"\text{Joint 1}", "Joint 1")
        point.Name = None  # Unnamed: A, as statics texts write a moment centre.
        assert tool.Structural.get_centre_symbol(case) == "A"
