"""Fail when the Alembic revision graph has missing parents or multiple heads."""
import ast
from pathlib import Path


def _assignment(tree: ast.Module, name: str):
    for node in tree.body:
        target = None
        value = None
        if isinstance(node, ast.Assign):
            target = next((item for item in node.targets if isinstance(item, ast.Name) and item.id == name), None)
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            target = node.target
            value = node.value
        if target is not None and value is not None:
            return ast.literal_eval(value)
    return None


def main() -> None:
    revisions: dict[str, str] = {}
    parents: set[str] = set()
    versions_dir = Path(__file__).resolve().parents[1] / "migrations" / "versions"
    for path in versions_dir.glob("*.py"):
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        revision = _assignment(tree, "revision")
        down_revision = _assignment(tree, "down_revision")
        if not revision:
            raise SystemExit(f"{path.name}: missing revision")
        if revision in revisions:
            raise SystemExit(f"duplicate revision {revision}: {revisions[revision]} and {path.name}")
        revisions[revision] = path.name
        if isinstance(down_revision, str):
            parents.add(down_revision)
        elif isinstance(down_revision, (tuple, list)):
            parents.update(down_revision)

    missing = sorted(parents - revisions.keys())
    heads = sorted(set(revisions) - parents)
    if missing:
        raise SystemExit(f"missing parent revisions: {', '.join(missing)}")
    if len(heads) != 1:
        raise SystemExit(f"expected one Alembic head, found {len(heads)}: {', '.join(heads)}")
    print(f"alembic_head={heads[0]}")


if __name__ == "__main__":
    main()
