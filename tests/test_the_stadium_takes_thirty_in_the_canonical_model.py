"""Full Metal Lab's -30, pinned on the one copy the plan calls canonical.

FOUND BY `utils/gate_mutation.py`, which is the point of having built it. The
stadium was taught to the damage model this morning after the differential
oracle proved the agent's projection was 30 too generous; the gate then mutated
the lines that fix ADDED and reported three survivors on the canonical copy
alone:

    ptcg/calc/damage.py:261  boolean: And -> Or
    ptcg/calc/damage.py:261  comparison: Eq -> NotEq
    ptcg/calc/damage.py:262  boundary: 30 -> 31

Which is to say: the whole suite stayed green with the stadium applied to every
body regardless of type, with it applied when the stadium is NOT in play, and
with it taking 31 instead of 30. A fix that a night of self-play was needed to
find had nothing watching it the morning it landed.

THE PAIRS. Two axes, two values each, because one example cannot separate them:

    body            lab off    lab on
    Archaludon ex     170        140     Metal, and it resists Grass
    Mega Lopunny ex   200        200     not Metal: the stadium says nothing

The Archaludon column kills the boundary -- 140 and not 141 -- and the two
columns of the Lopunny row kill `and -> or` and `== -> !=` between them, since
either rewrite would take 30 off a body the card does not mention.

THE SECOND 30 IS NOT THE RESISTANCE, and the numbers say so on their own: base
200 lands at 170 with the stadium off, which is the resistance already applied,
and at 140 with it on. That was the hypothesis that cost the most time on the
night this was found, so it is pinned here as arithmetic rather than as prose.

The other four copies of this arithmetic (main.py:5206, 6579, 7412, 7434) are
still unwatched and `ptcg/turn/supporters.py:972-979` and
`ptcg/turn/options/play.py:1556-1562` are not executed by any test at all. That
is the gate's list, not a guess, and it is the next piece of work.
"""

import pytest

from ptcg.calc.damage import _our_effective_damage

ARCHALUDON_EX = 190          # Metal, resists Grass, 300 hp
MEGA_LOPUNNY_EX = 849        # not Metal: the control
HYDRAPPLE_EX = 150           # one of ours, and not the Fezandipiti exception

BASE = 200


class _Body:
    """All `_our_effective_damage` reads of either side is the card id."""

    def __init__(self, card_id):
        self.id = card_id


def _damage(op_id, full_metal_lab):
    return _our_effective_damage(_Body(HYDRAPPLE_EX), _Body(op_id), BASE,
                                 full_metal_lab=full_metal_lab)


@pytest.mark.parametrize("lab,expected", [(False, 170), (True, 140)])
def test_the_stadium_takes_a_second_thirty_off_a_metal_body(lab, expected):
    """170 without it, 140 with it: exactly 30, and only once."""
    assert _damage(ARCHALUDON_EX, lab) == expected


@pytest.mark.parametrize("lab", [False, True])
def test_a_body_that_is_not_metal_is_untouched_either_way(lab):
    """The card names {M} Pokemon. Anything else takes the full hit.

    Both arms matter: with the stadium OFF this is the ordinary board, and with
    it ON it is the pair that refuses `and -> or` and `== -> !=`.
    """
    assert _damage(MEGA_LOPUNNY_EX, lab) == BASE


def test_the_resistance_is_already_in_the_170():
    """The dead hypothesis, kept dead, as arithmetic.

    The gap the oracle measured was 30 and the Grass resistance is also 30,
    which made "the resistance is missing" the obvious and wrong first guess.
    With the stadium off the model already subtracts it.
    """
    assert BASE - _damage(ARCHALUDON_EX, False) == 30, "the resistance"
    assert (_damage(ARCHALUDON_EX, False)
            - _damage(ARCHALUDON_EX, True)) == 30, "the stadium, on top"
