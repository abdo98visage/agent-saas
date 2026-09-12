"""serialize concurrent audit inserts without forking the hash chain

Revision ID: repair_audit_chain_order
Revises: knowledge_connectors
"""
from alembic import op


revision = "repair_audit_chain_order"
down_revision = "knowledge_connectors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("LOCK TABLE audit_log IN ACCESS EXCLUSIVE MODE")
    op.execute("DROP TRIGGER audit_log_append_only ON audit_log")
    op.execute("""
        DO $$
        DECLARE item audit_log%ROWTYPE; prior text := repeat('0', 64); calculated text;
        BEGIN
          FOR item IN SELECT * FROM audit_log ORDER BY id FOR UPDATE LOOP
            calculated := encode(digest(prior || '|' ||
              ((to_jsonb(item) - 'previous_hash' - 'event_hash' - 'updated_at')::text), 'sha256'), 'hex');
            UPDATE audit_log SET previous_hash = prior, event_hash = calculated WHERE id = item.id;
            prior := calculated;
          END LOOP;
        END $$
    """)
    op.execute("""
        CREATE TRIGGER audit_log_append_only
        BEFORE UPDATE OR DELETE ON audit_log FOR EACH ROW EXECUTE FUNCTION reject_audit_log_mutation()
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION set_audit_log_hash() RETURNS trigger AS $$
        DECLARE prior text;
        BEGIN
          PERFORM pg_advisory_xact_lock(hashtext('audit_log_hash_chain'));
          SELECT candidate.event_hash INTO prior
          FROM audit_log candidate
          WHERE NOT EXISTS (
            SELECT 1 FROM audit_log child WHERE child.previous_hash = candidate.event_hash
          )
          ORDER BY candidate.id DESC LIMIT 1;
          NEW.previous_hash := coalesce(prior, repeat('0', 64));
          NEW.event_hash := encode(digest(NEW.previous_hash || '|' ||
            ((to_jsonb(NEW) - 'previous_hash' - 'event_hash' - 'updated_at')::text), 'sha256'), 'hex');
          RETURN NEW;
        END; $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION verify_audit_log_chain() RETURNS boolean AS $$
        DECLARE total_rows bigint; walked_rows bigint; invalid_hashes bigint; genesis_rows bigint; forks bigint;
        BEGIN
          SELECT count(*), count(*) FILTER (WHERE previous_hash = repeat('0', 64))
          INTO total_rows, genesis_rows FROM audit_log;
          IF total_rows = 0 THEN RETURN true; END IF;

          SELECT count(*) INTO invalid_hashes
          FROM audit_log item
          WHERE item.event_hash <> encode(digest(item.previous_hash || '|' ||
            ((to_jsonb(item) - 'previous_hash' - 'event_hash' - 'updated_at')::text), 'sha256'), 'hex');

          SELECT count(*) INTO forks FROM (
            SELECT previous_hash FROM audit_log
            WHERE previous_hash <> repeat('0', 64)
            GROUP BY previous_hash HAVING count(*) > 1
          ) duplicate_children;

          WITH RECURSIVE chain(event_hash, path) AS (
            SELECT event_hash, ARRAY[event_hash]::text[] FROM audit_log
            WHERE previous_hash = repeat('0', 64)
            UNION ALL
            SELECT item.event_hash, chain.path || item.event_hash
            FROM audit_log item JOIN chain ON item.previous_hash = chain.event_hash
            WHERE NOT item.event_hash = ANY(chain.path)
          )
          SELECT count(*) INTO walked_rows FROM chain;

          RETURN invalid_hashes = 0 AND genesis_rows = 1 AND forks = 0 AND walked_rows = total_rows;
        END; $$ LANGUAGE plpgsql STABLE
    """)
    op.execute("""
        INSERT INTO audit_log (user_id, action, details, event_category, actor_type)
        VALUES (NULL, 'audit_chain_repaired', '{"reason":"concurrent_insert_order"}'::jsonb, 'platform', 'system')
    """)


def downgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION set_audit_log_hash() RETURNS trigger AS $$
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
        CREATE OR REPLACE FUNCTION verify_audit_log_chain() RETURNS boolean AS $$
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
