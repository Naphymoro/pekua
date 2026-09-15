"""Durable orchestration tables."""

from alembic import op

from pekua.orchestration.models import OrchestrationBase

revision = "0002_orchestration"
down_revision = "0001_persistence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    OrchestrationBase.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    OrchestrationBase.metadata.drop_all(bind=op.get_bind())
