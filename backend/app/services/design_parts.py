"""Persist generated parts with catalog references and repeatable task results."""

import uuid

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.design import DesignPart
from app.models.part import Part
from app.services.lego_parts_knowledge import CAR_PARTS_CATALOG


async def replace_design_parts(db: AsyncSession, design_id: uuid.UUID, parts_data: list[dict]) -> None:
    catalog = {p.part_num: p for p in CAR_PARTS_CATALOG}
    entries = {}
    for part in parts_data:
        number = part["part_num"]
        info = catalog.get(number)
        entries[number] = {"part_num": number, "name": info.name if info else number,
                           "ldraw_name": number if number.endswith(".dat") else f"{number}.dat"}
    if entries:
        dialect = db.get_bind().dialect.name
        insert = sqlite_insert if dialect == "sqlite" else postgres_insert
        await db.execute(insert(Part).values(list(entries.values())).on_conflict_do_nothing(index_elements=["part_num"]))
    await db.execute(delete(DesignPart).where(DesignPart.design_id == design_id))
    db.add_all([DesignPart(
        design_id=design_id, part_num=p["part_num"], ldraw_color_id=p["ldraw_color_id"],
        quantity=p["quantity"], bricklink_id=p.get("bricklink_id"),
    ) for p in parts_data])
    await db.flush()
