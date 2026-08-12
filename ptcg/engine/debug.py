"""Decision dump for debugging (PTCG_DEBUG).

Prints the top-scoring options of a menu, by CARD NAME, so a surprising choice
can be read back without a debugger. Off unless `PTCG_DEBUG` is set to
something other than empty/`0`/`false`; the flag is read ONCE at import, so
setting it mid-process does nothing.

Two properties matter more than what it prints. It goes to STDERR, so it cannot
corrupt the stdout channel the competition harness reads; and every line of it
is wrapped in a bare `except`, so a malformed option or a card missing from the
table degrades the label to `?` instead of crashing a live game. A debugging
aid that can lose a match is worse than no debugging aid.

For the heavier questions -- which RULE decided, and how a whole game replays
-- this is the wrong tool: see `tests/rule_trace.py` and `utils/log_replay.py`.

Extracted VERBATIM from main.py by utils/extract_definitions.py
(docs/project-history.md). Its purity is verified by
utils/purity.py: nothing here touches mutable state or the runtime tables.
"""

import os as _os_dbg
from ptcg.calc.card import get_card
from ptcg.cards.tables import card_table


DEBUG_DECISIONS = _os_dbg.environ.get("PTCG_DEBUG", "") not in ("", "0", "false", "False")


def _debug_log_decision(context, select, scores, obs, my_index, top_n=3):
    """Print the `top_n` best-scoring options of this menu, named, to stderr.

    `scores` is parallel to `select.option`, so the ranking is over indices and
    each one is labelled by looking its card up in the table. A no-op when
    `PTCG_DEBUG` is unset, and silent on any failure -- see the module note.
    """
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
