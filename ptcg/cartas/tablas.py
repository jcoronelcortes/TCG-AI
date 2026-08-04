"""Card tables derived from the simulator: `card_table` and `attack_table`.

Extracted VERBATIM from main.py in wave 2 of the refactor
(docs/project-history.md).

They are not literal constants (they come from `cg.api`), but they ARE
deterministic and read-only: they are built once at import time and nobody
mutates them -- verified with `utils/pureza.py`. That is exactly the difference
with `ATTACK_ENERGY_REQ`, which looks like a fixed table and is really TURN
state (the Nighttime Mine tax rewrites it on every `agent()` call), which is why
that one stayed in main.py until wave 3.

CAREFUL when moving them: modules that do `from ptcg.cartas.tablas import
card_table` FREEZE the binding at import time. In production it makes no
difference (nobody reassigns them), but a test that patches `main.card_table`
no longer reaches them. That is why their CONSUMERS stayed in main.py until
wave 3, where it was decided who owns the module-level state.
"""

from cg.api import all_card_data, all_attack

all_card = all_card_data()
card_table = {c.cardId: c for c in all_card}
# Table attack-id -> Attack object (name/damage/energies). The `card.attacks`
# entries are IDs (ints), not objects, so _op_best_damage_vs (which does
# getattr(id, 'damage')) always returns 0. This table is what makes it possible
# to RESOLVE the real damage of the opposing active's attack when it is needed
# (see _op_active_attack_damage_to).
attack_table = {a.attackId: a for a in all_attack()}


# Index NAME -> card data: `evolvesFrom` stores the NAME of the pre-evolution,
# so walking a chain upwards means resolving names. It covers ALL the cards in
# the environment (not just the ones in our deck): the lines that have to be
# read here are the OPPONENT's.
_CARD_BY_NAME = {}

# Reverse index NAME -> cards that evolve FROM that name. It complements
# `_CARD_BY_NAME` (which walks up the chain) so the chain can also be walked
# DOWN, to know what an opposing line ends in. It covers ALL the cards in the
# environment.
_EVOLUCIONES_POR_NOMBRE = {}


__all__ = [
    'all_card',
    'card_table',
    'attack_table',
    '_CARD_BY_NAME',
    '_EVOLUCIONES_POR_NOMBRE',
]
