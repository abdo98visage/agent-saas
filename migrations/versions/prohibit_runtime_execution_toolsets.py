"""prohibit terminal and code execution runtime toolsets

Revision ID: prohibit_execution_tools
Revises: add_mcp_control_plane
"""

from typing import Sequence, Union

from alembic import op


revision: str = "prohibit_execution_tools"
down_revision: Union[str, None] = "add_mcp_control_plane"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE profiles
        SET runtime_toolsets = COALESCE(
            (
                SELECT jsonb_agg(item)
                FROM jsonb_array_elements(runtime_toolsets) AS item
                WHERE item #>> '{}' NOT IN ('terminal', 'code_execution')
            ),
            '[]'::jsonb
        )
        WHERE runtime_toolsets ?| ARRAY['terminal', 'code_execution']
        """
    )


def downgrade() -> None:
    # Removing a prohibited capability is intentionally not reversible because
    # the previous per-profile choice cannot be reconstructed safely.
    pass
