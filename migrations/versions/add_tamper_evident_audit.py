"""add tamper-evident audit trail and trace identifiers

Revision ID: tamper_evident_audit
Revises: add_durable_tasks
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "tamper_evident_audit"
down_revision = "add_durable_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.add_column("audit_log", sa.Column("event_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("audit_log", sa.Column("event_category", sa.String(50), nullable=False, server_default="platform"))
    op.add_column("audit_log", sa.Column("actor_type", sa.String(30), nullable=False, server_default="user"))
    op.add_column("audit_log", sa.Column("subject_type", sa.String(50), nullable=True))
    op.add_column("audit_log", sa.Column("subject_id", sa.String(100), nullable=True))
    op.add_column("audit_log", sa.Column("correlation_id", sa.String(64), nullable=True))
    op.add_column("audit_log", sa.Column("trace_id", sa.String(64), nullable=True))
    op.add_column("audit_log", sa.Column("run_id", postgresql.UUID(), nullable=True))
    op.add_column("audit_log", sa.Column("task_id", postgresql.UUID(), nullable=True))
    op.add_column("audit_log", sa.Column("session_id", postgresql.UUID(), nullable=True))
    op.add_column("audit_log", sa.Column("policy_id", sa.String(150), nullable=True))
    op.add_column("audit_log", sa.Column("reason", sa.Text(), nullable=True))
    op.add_column("audit_log", sa.Column("previous_hash", sa.String(64), nullable=True))
    op.add_column("audit_log", sa.Column("event_hash", sa.String(64), nullable=True))
    op.add_column("agent_runs", sa.Column("trace_id", sa.String(64), nullable=True))

    for column in ("event_category", "subject_type", "subject_id", "correlation_id", "trace_id", "run_id", "task_id", "session_id"):
        op.create_index(f"ix_audit_log_{column}", "audit_log", [column])
    op.create_index("ix_agent_runs_trace_id", "agent_runs", ["trace_id"])

    op.execute("""
        DO $$
        DECLARE item audit_log%ROWTYPE; prior text := repeat('0', 64); calculated text;
        BEGIN
          FOR item IN SELECT * FROM audit_log ORDER BY id FOR UPDATE LOOP
            item.previous_hash := prior;
            calculated := encode(digest(prior || '|' ||
              ((to_jsonb(item) - 'previous_hash' - 'event_hash' - 'updated_at')::text), 'sha256'), 'hex');
            UPDATE audit_log SET previous_hash = prior, event_hash = calculated WHERE id = item.id;
            prior := calculated;
          END LOOP;
        END $$;
    """)
    op.alter_column("audit_log", "previous_hash", nullable=False, server_default=sa.text("repeat('0', 64)"))
    op.alter_column("audit_log", "event_hash", nullable=False)
    op.create_unique_constraint("uq_audit_log_event_hash", "audit_log", ["event_hash"])

    op.execute("""
        CREATE FUNCTION set_audit_log_hash() RETURNS trigger AS $$
        DECLARE prior text;
        BEGIN
          PERFORM pg_advisory_xact_lock(hashtext('audit_log_hash_chain'));
          SELECT event_hash INTO prior FROM audit_log ORDER BY id DESC LIMIT 1;
          NEW.previous_hash := coalesce(prior, repeat('0', 64));
          NEW.event_hash := encode(digest(NEW.previous_hash || '|' ||
            ((to_jsonb(NEW) - 'previous_hash' - 'event_hash' - 'updated_at')::text), 'sha256'), 'hex');
          RETURN NEW;
        END; $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER audit_log_hash_before_insert
        BEFORE INSERT ON audit_log FOR EACH ROW EXECUTE FUNCTION set_audit_log_hash()
    """)
    op.execute("""
        CREATE FUNCTION reject_audit_log_mutation() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'audit_log is append-only';
        END; $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER audit_log_append_only
        BEFORE UPDATE OR DELETE ON audit_log FOR EACH ROW EXECUTE FUNCTION reject_audit_log_mutation()
    """)
    op.execute("""
        CREATE FUNCTION verify_audit_log_chain() RETURNS boolean AS $$
        DECLARE item audit_log%ROWTYPE; prior text := repeat('0', 64); calculated text;
        BEGIN
          FOR item IN SELECT * FROM audit_log ORDER BY id LOOP
            IF item.previous_hash <> prior THEN RETURN false; END IF;
            calculated := encode(digest(prior || '|' ||
              ((to_jsonb(item) - 'previous_hash' - 'event_hash' - 'updated_at')::text), 'sha256'), 'hex');
            IF item.event_hash <> calculated THEN RETURN false; END IF;
            prior := item.event_hash;
          END LOOP;
          RETURN true;
        END; $$ LANGUAGE plpgsql STABLE
    """)

    op.create_table(
        "audit_export_checkpoints",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("destination", sa.String(255), nullable=False),
        sa.Column("last_audit_id", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("destination"),
    )


def downgrade() -> None:
    op.drop_table("audit_export_checkpoints")
    op.execute("DROP FUNCTION IF EXISTS verify_audit_log_chain()")
    op.execute("DROP TRIGGER IF EXISTS audit_log_append_only ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS reject_audit_log_mutation()")
    op.execute("DROP TRIGGER IF EXISTS audit_log_hash_before_insert ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS set_audit_log_hash()")
    op.drop_index("ix_agent_runs_trace_id", table_name="agent_runs")
    op.drop_column("agent_runs", "trace_id")
    for column in reversed(("event_category", "subject_type", "subject_id", "correlation_id", "trace_id", "run_id", "task_id", "session_id")):
        op.drop_index(f"ix_audit_log_{column}", table_name="audit_log")
    op.drop_constraint("uq_audit_log_event_hash", "audit_log", type_="unique")
    for column in ("event_hash", "previous_hash", "reason", "policy_id", "session_id", "task_id", "run_id", "trace_id", "correlation_id", "subject_id", "subject_type", "actor_type", "event_category", "event_version"):
        op.drop_column("audit_log", column)
