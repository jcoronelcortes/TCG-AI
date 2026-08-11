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

A CORRECTION, because the first version of this docstring said the opposite.
The gate that produced these three also reported twelve more survivors across
`main.py` and both wave-2 copies, and every one of them was an artifact: its
line-to-test map was truncated (see `utils/gate_mutation.py`) and the mutation
probe was reusing stale bytecode between same-size mutants. Re-run after both
were fixed, the whole Full Metal Lab fix comes back with ZERO survivors except
one equivalent mutant. The four other copies of the arithmetic ARE watched.

The equivalent one, kept here because knowing it is dead saves the next reader
the same search: `meganium_active=False -> True` on the signature survives
because `meganium_active` is never read inside this function -- zero uses in the
body, while its two neighbours have one each. It is a parameter the ~70 call
sites still pass and nothing consumes.
"""

import pytest

from ptcg.calc.damage import _our_effective_damage
from ptcg.state.agent_state import AGENT_STATE


@pytest.fixture(autouse=True)
def _no_stadium_unless_the_test_says_so():
    """The flag is global and now load-bearing: every test here starts from an
    empty field and leaves it empty."""
    AGENT_STATE.full_metal_lab_in_play = False
    yield
    AGENT_STATE.full_metal_lab_in_play = False

ARCHALUDON_EX = 190          # Metal, resists Grass, 300 hp
MEGA_LOPUNNY_EX = 849        # not Metal: the control
DURALUDON = 169             # Metal and resists Grass, but NOT an ex
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


def test_the_default_asks_the_board_instead_of_answering_no():
    """The DEFAULT of the keyword, which is a different claim from its False arm.

    IT USED TO BE `False`, and the docstring here defended it: the keyword
    existed so that "the ~70 call sites which know nothing about the stadium did
    not have to change at once". None of them ever did -- zero of 69 passed it --
    so the canonical model knew the card and was never asked about it, and every
    finisher went on over-reading by 30 into their Metal. That cost episode
    91627381 (see `test_the_stadium_is_the_finisher_it_was_hiding`).

    So the default is now `None` = ASK THE BOARD, i.e. read
    `AGENT_STATE.full_metal_lab_in_play`, which `agent()` writes from the
    stadium on every observation. True/False still force the answer, for these
    tests and for any caller projecting a board where the stadium is about to
    change.

    Both arms, because the read is what the fix is: the stadium off is the 170
    the old default gave for the wrong reason, and the stadium on is the 140 no
    call site could reach.
    """
    AGENT_STATE.full_metal_lab_in_play = False
    assert _our_effective_damage(_Body(HYDRAPPLE_EX), _Body(ARCHALUDON_EX),
                                 BASE) == 170, "no stadium in play"
    AGENT_STATE.full_metal_lab_in_play = True
    assert _our_effective_damage(_Body(HYDRAPPLE_EX), _Body(ARCHALUDON_EX),
                                 BASE) == 140, "and the board is what says so"


def test_an_explicit_keyword_still_overrides_the_board():
    """The projector's escape hatch: what the damage would be under ANOTHER
    stadium. With Full Metal Lab really on the field, `full_metal_lab=False`
    answers the question "and if we replaced it?" -- which is the very play the
    record's board needed."""
    AGENT_STATE.full_metal_lab_in_play = True
    assert _damage(ARCHALUDON_EX, False) == 170
    AGENT_STATE.full_metal_lab_in_play = False
    assert _damage(ARCHALUDON_EX, True) == 140


def test_the_other_two_switches_are_off_by_default_as_well():
    """The whole keyword row, not just the stadium.

    `_our_effective_damage` takes three optional switches and each is a rule
    that turns damage OFF: with `neutralization_zone` our ex do nothing to a
    body without a rule box, and the stadium takes its 30. The other two still
    default to False -- only the stadium graduated to reading the board -- and
    those defaults stay load-bearing for the ~70 call sites that name none of
    them.

    Duraludon is the body that separates them: Metal, resists Grass, and NOT an
    ex, so Neutralization Zone would take our Hydrapple ex to zero if it were on.
    """
    AGENT_STATE.full_metal_lab_in_play = False
    assert _our_effective_damage(_Body(HYDRAPPLE_EX), _Body(DURALUDON),
                                 BASE) == 170, "neutralization zone off"
    assert _our_effective_damage(_Body(HYDRAPPLE_EX), _Body(DURALUDON), BASE,
                                 neutralization_zone=True) == 0, (
        "and the arm that proves the assertion above is not vacuous")


def test_the_resistance_is_already_in_the_170():
    """The dead hypothesis, kept dead, as arithmetic.

    The gap the oracle measured was 30 and the Grass resistance is also 30,
    which made "the resistance is missing" the obvious and wrong first guess.
    With the stadium off the model already subtracts it.
    """
    assert BASE - _damage(ARCHALUDON_EX, False) == 30, "the resistance"
    assert (_damage(ARCHALUDON_EX, False)
            - _damage(ARCHALUDON_EX, True)) == 30, "the stadium, on top"
