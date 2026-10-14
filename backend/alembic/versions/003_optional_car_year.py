"""Allow vehicle identity without a requested model year."""

from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("cars") as batch:
        batch.alter_column("year", existing_type=sa.SmallInteger(), nullable=True)
    op.create_index("uq_cars_without_year", "cars",
                    [sa.text("lower(make)"), sa.text("lower(model)")], unique=True,
                    sqlite_where=sa.text("year IS NULL"), postgresql_where=sa.text("year IS NULL"))


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM cars WHERE year IS NULL")).scalar():
        raise ValueError("Assign real model years before downgrading; unknown years cannot be invented")
    op.drop_index("uq_cars_without_year", table_name="cars")
    with op.batch_alter_table("cars") as batch:
        batch.alter_column("year", existing_type=sa.SmallInteger(), nullable=False)
