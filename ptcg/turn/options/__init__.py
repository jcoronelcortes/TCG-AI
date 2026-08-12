"""ONE MODULE PER MENU BRANCH: the scoring of each `OptionType`.

The engine tags every option in a menu with a type, and `ptcg/turn/scoring.py`
dispatches on it. What used to be a 6,628-line if/elif chain is one file per
branch:

    card.py     "pick a card" -- promotion, setup, recovery, discard. The
                largest, because a dozen unrelated decisions share this type;
                read `select.context` first.
    play.py     playing a card out of hand: benching, Items, Supporters
    retreat.py  swapping the body in front: the relay, the pivot, the fee
    ability.py  the free plays -- Teal Dance, Ripening Charge, Grand Tree
    attach.py   where this turn's one energy goes
    evolve.py   which body gets the stage
    attack.py   whether to attack at all; attacking ends the turn
    minor.py    NUMBER, YES, NO, END, SPECIAL_CONDITION -- too small to split

THE CONTRACT every branch follows. It receives the shared `ScoringCtx`,
UNPACKS only the fields it reads, and RETURNS only the ones it reassigns --
equivalent to the single write-back of the original loop, since a field a
branch does not touch keeps its value. A branch that has already appended its
own score returns the `_SALTAR` sentinel instead, which is what used to be a
`continue`.

Higher score = better; negative = veto. But the score is only half the answer:
`ptcg/turn/finalize.py` sorts options into TIERS first and the score decides
only inside the winning tier. A branch that returns the right number in the
wrong tier still loses -- that failure mode is the subject of most of the long
comments in `finalize.py`.
"""
