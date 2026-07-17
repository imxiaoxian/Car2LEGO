"""car_specs knowledge base table

Revision ID: 002
Revises: 001
Create Date: 2026-07-11 20:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('car_specs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('make', sa.String(length=100), nullable=False),
        sa.Column('model', sa.String(length=200), nullable=False),
        sa.Column('year', sa.SmallInteger(), nullable=False),
        sa.Column('body_style', sa.String(length=50), nullable=True),
        sa.Column('length_mm', sa.SmallInteger(), nullable=True),
        sa.Column('width_mm', sa.SmallInteger(), nullable=True),
        sa.Column('height_mm', sa.SmallInteger(), nullable=True),
        sa.Column('wheelbase_mm', sa.SmallInteger(), nullable=True),
        sa.Column('engine_type', sa.String(length=200), nullable=True),
        sa.Column('drive_type', sa.String(length=20), nullable=True),
        sa.Column('horsepower', sa.SmallInteger(), nullable=True),
        sa.Column('top_speed_kmh', sa.SmallInteger(), nullable=True),
        sa.Column('distinctive_features', sa.JSON(), nullable=True),
        sa.Column('colors_available', sa.JSON(), nullable=True),
        sa.Column('body_proportions', sa.Text(), nullable=True),
        sa.Column('source', sa.String(length=200), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('make', 'model', 'year')
    )
    op.create_index(op.f('ix_car_specs_make'), 'car_specs', ['make'], unique=False)
    op.create_index(op.f('ix_car_specs_model'), 'car_specs', ['model'], unique=False)
    op.create_index(op.f('ix_car_specs_year'), 'car_specs', ['year'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_car_specs_year'), table_name='car_specs')
    op.drop_index(op.f('ix_car_specs_model'), table_name='car_specs')
    op.drop_index(op.f('ix_car_specs_make'), table_name='car_specs')
    op.drop_table('car_specs')
