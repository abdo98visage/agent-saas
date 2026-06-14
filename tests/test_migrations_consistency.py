from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


ROOT = Path(__file__).resolve().parents[1]


def test_alembic_has_single_head():
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    script = ScriptDirectory.from_config(config)
    assert len(script.get_heads()) == 1


def test_latest_migration_includes_runtime_schema_fields():
    migration_path = ROOT / "migrations" / "versions" / "add_user_activity_last_seen.py"
    content = migration_path.read_text(encoding="utf-8")

    for field_name in ["tokens_used", "total_cost", "models_used", "last_seen_at", "user_activities"]:
        assert field_name in content
