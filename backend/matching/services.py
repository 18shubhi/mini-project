"""Django-to-ML adapter; matching calculations live in the root ml package."""

import sys
from pathlib import Path


ML_ROOT = Path(__file__).resolve().parents[2]
if str(ML_ROOT) not in sys.path:
    sys.path.insert(0, str(ML_ROOT))

from ml.matcher import rank_matches


def item_document(item):
    return {
        "id": item.pk,
        "title": item.title,
        "description": item.description,
        "category": item.category,
        "type": item.type,
        "status": item.status,
        "location": item.location,
        "date": item.date,
    }


__all__ = ["item_document", "rank_matches"]