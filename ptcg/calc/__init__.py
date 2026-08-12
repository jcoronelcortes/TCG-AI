"""PURE READINGS of the board. Ask a question, get a number.

Nothing here decides anything: these modules answer the factual questions the
decision layers argue about. They are pure -- everything they need arrives as
an argument, and they write no state -- which is what `utils/purity.py` checks
and rule R2 of the architecture lint enforces.

    card.py         one card: fetch it, what it is worth, what it costs us
    board.py        the board: the active, what can evolve, what can be played
    damage.py       THE DAMAGE MODEL, ours and theirs. The big one.
    energy.py       effective vs physical energy, attach routes, caps
    grass.py        does this board still want energy, and does it want it today
    opponent.py     what their bodies can do; what their hand might hold
    probability.py  the only place the agent reasons about chance

WHY PURITY IS WORTH THE CONSTRAINT: one implementation of each question, used
by everyone. When two rules compute the same fact separately they eventually
disagree, and on this board a disagreement is a lost game rather than a failing
test -- `damage.py` carries the case where exactly that happened.
"""
