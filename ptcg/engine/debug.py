"""Decision dump for debugging (PTCG_DEBUG).

Extracted VERBATIM from main.py by utils/extract_definitions.py
(docs/project-history.md). Its purity is verified by
utils/purity.py: nothing here touches mutable state or the runtime tables.
"""

import os as _os_dbg
from ptcg.calc.card import get_card
from ptcg.cards.tables import card_table


DEBUG_DECISIONS = _os_dbg.environ.get("PTCG_DEBUG", "") not in ("", "0", "false", "False")


def _debug_log_decision(context, select, scores, obs, my_index, top_n=3):
    if not DEBUG_DECISIONS:
        return
    try:
        import sys as _sys
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        print(f"[DBG] ctx={getattr(context, 'name', context)} "
              f"opciones={len(scores)}", file=_sys.stderr)
        for _r, _i in enumerate(ranked[:top_n]):
            _label = ""
            try:
                _opt = select.option[_i]
                _card = get_card(obs, _opt.area, _opt.index, my_index)
                if _card is not None:
                    _cd = card_table.get(_card.id)
                    _label = getattr(_cd, 'name', None) or f"id={_card.id}"
                else:
                    _label = f"area={getattr(_opt, 'area', '?')}"
            except Exception:
                _label = "?"
            print(f"[DBG]   #{_r+1} idx={_i} score={scores[_i]} {_label}",
                  file=_sys.stderr)
    except Exception:
        pass

__all__ = [
    'DEBUG_DECISIONS',
    '_debug_log_decision',
]
