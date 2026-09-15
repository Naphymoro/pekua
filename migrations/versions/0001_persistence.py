"""Tenant-aware documents and append-only evidence ledger."""

from alembic import op

from pekua.storage.models import Base

revision = "0001_persistence"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    op.execute("""
      CREATE OR REPLACE FUNCTION reject_evidence_mutation() RETURNS trigger AS $$
      BEGIN
        RAISE EXCEPTION 'evidence_events is append-only';
      END;
      $$ LANGUAGE plpgsql
    """)
    op.execute("""
      CREATE TRIGGER evidence_events_no_update_delete
      BEFORE UPDATE OR DELETE ON evidence_events
      FOR EACH ROW EXECUTE FUNCTION reject_evidence_mutation()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS evidence_events_no_update_delete ON evidence_events")
    op.execute("DROP FUNCTION IF EXISTS reject_evidence_mutation")
    Base.metadata.drop_all(bind=op.get_bind())
