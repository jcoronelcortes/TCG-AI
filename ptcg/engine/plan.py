"""AttackPlan: the attack the turn has decided to make, once, for everyone.

The board is scanned for the best attack ONCE per turn; every later phase reads
the answer from here instead of recomputing it. That single-writer shape is the
point: a dozen scorers ask "is our attack a knockout?" and they all have to get
the same answer, or the turn contradicts itself -- the retreat scorer declining
to retreat for an attack the finalizer then decides not to make.

It lives on `AGENT_STATE.plan` and is REPLACED WHOLE at the start of each turn
(a fresh `AttackPlan()`), which is what stops last turn's knockout from being
believed this turn. Consumers are spread across `ptcg/turn/`: the attack scorer
ranks the menu with it, the retreat and play scorers ask whether the turn ends
in a knockout before spending resources, and `finalize` reads it when it picks
the action to actually submit.

READING IT SAFELY: `remain_hp <= 0` is the "this attack knocks out" test, and
every consumer guards it with `is not None` first. The fields carry -1 while no
attack has been found, so a bare `<= 0` on a fresh plan would report a knockout
that does not exist.

Extracted VERBATIM from main.py by utils/extract_definitions.py
(docs/project-history.md). Its purity is verified by
utils/purity.py: nothing here touches mutable state or the runtime tables.
"""

class AttackPlan:
    """The chosen attack, as five numbers. -1 means "nothing chosen yet"."""

    attacker = -1      # index of OUR attacking body; 0 is the active
    target = -1        # index of THEIR body being hit; 0 is their active
    attack_index = -1  # which of the attacker's attacks (its slot on the card)
    remain_hp = -1     # target HP left AFTER the hit: <= 0 means a knockout
    energy = False     # True if the plan only works once we attach this turn

__all__ = [
    'AttackPlan',
]
