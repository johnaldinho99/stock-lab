from __future__ import annotations

from . import classic, magic, ml
from .base import Strategy

STRATEGIES: dict[str, Strategy] = {s.id: s for s in [*classic.build(), *magic.build(), *ml.build()]}
FAMILY_ORDER = ["Klassiska", "Magic Formula", "Maskininlärning", "Referens"]
