"""merge alert and skill migration heads

Revision ID: merge_alert_and_skill_heads
Revises: add_alert_events, add_skill_definitions_table
Create Date: 2026-06-23 12:15:00.000000
"""


revision = "merge_alert_and_skill_heads"
down_revision = ("add_alert_events", "add_skill_definitions_table")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
