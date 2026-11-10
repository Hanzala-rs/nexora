"""Load menu content and bot texts from the database."""
from collections.abc import Iterable, Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.bot.engine import Content, Node
from app.models import MenuNode, MenuTranslation, UiText


def build_content(nodes: Iterable[Mapping], translations: Iterable[Mapping], texts: Iterable[Mapping]) -> Content:
    """Build engine content from row mappings. Inactive nodes are skipped."""
    active = sorted((n for n in nodes if n["is_active"]), key=lambda n: (n["sort_order"], n["id"]))
    by_id = {n["id"]: n for n in active}
    titles: dict[int, dict] = {}
    bodies: dict[int, dict] = {}
    for t in translations:
        titles.setdefault(t["node_id"], {})[t["lang"]] = t["title"]
        bodies.setdefault(t["node_id"], {})[t["lang"]] = t["body"]
    return Content(
        nodes={
            n["action_id"]: Node(
                action_id=n["action_id"],
                parent=by_id[n["parent_id"]]["action_id"] if n["parent_id"] in by_id else None,
                kind=n["kind"],
                title=titles.get(n["id"], {}),
                body=bodies.get(n["id"], {}),
            )
            for n in active
        },
        texts={(t["key"], t["lang"]): t["text"] for t in texts},
    )


def load_content(db: Session) -> Content:
    rows = lambda model: db.execute(select(model.__table__)).mappings().all()  # noqa: E731
    return build_content(rows(MenuNode), rows(MenuTranslation), rows(UiText))
