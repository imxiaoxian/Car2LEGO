"""BrickLink Wanted List XML and CSV export generation."""

from app.models.design import Design, DesignPart


class ExportService:
    """Generates export files: BrickLink XML, CSV, and LDraw formats."""

    @staticmethod
    def generate_bricklink_xml(design: Design, parts: list[DesignPart]) -> str:
        """Generate BrickLink Wanted List XML from design parts.

        This XML can be uploaded to BrickLink.com to create a wanted list
        for one-click brick purchasing.
        """
        lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<INVENTORY>"]
        for p in parts:
            item_id = p.bricklink_id or p.part_num
            color_id = p.bricklink_color_id or p.ldraw_color_id
            lines.append("  <ITEM>")
            lines.append("    <ITEMTYPE>P</ITEMTYPE>")
            lines.append(f"    <ITEMID>{item_id}</ITEMID>")
            if color_id:
                lines.append(f"    <COLOR>{color_id}</COLOR>")
            lines.append(f"    <MINQTY>{p.quantity}</MINQTY>")
            lines.append("    <REMARKS>Car2LEGO design part</REMARKS>")
            lines.append("  </ITEM>")
        lines.append("</INVENTORY>")
        return "\n".join(lines)

    @staticmethod
    def generate_csv(design: Design, parts: list[DesignPart]) -> str:
        """Generate CSV parts list for spreadsheet import."""
        header = "part_num,bricklink_id,color_id,quantity"
        rows = [header]
        for p in parts:
            rows.append(
                f"{p.part_num},{p.bricklink_id or ''},"
                f"{p.ldraw_color_id},{p.quantity}"
            )
        return "\n".join(rows)

    @staticmethod
    def generate_ldr_content(design: Design) -> str:
        """Generate minimal LDraw file header for a design.

        For Level 1 matches using official sets, this references the set's
        existing LDraw model. For AI-generated designs, a full LDraw file
        is generated during the Celery task.
        """
        lines = [
            "0 Car2LEGO Design",
            f"0 Name: {design.id}",
            "0 Author: Car2LEGO",
            "0 !LICENSE Redistributable under CC BY 4.0",
            "",
        ]
        return "\n".join(lines)
