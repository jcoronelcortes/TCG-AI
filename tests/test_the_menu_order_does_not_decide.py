"""Shuffling the menu must not change what gets played.

THE PROPERTY, and why it is worth a file. The observation hands the agent a list
of legal options and it answers with indexes into that list. Every rule in this
project is a score attached to an option, so permuting the list may move the
index and must not move the PLAY. That is a metamorphic property -- it needs no
expected answer -- which is what makes it usable on boards nobody has looked at.

WHAT IT CATCHES that nothing else does: a rule that reaches for `option[0]`, a
tie broken by position instead of by the board, a scan that stops at the first
option of a kind instead of the best one. None of those raises, none of them
turns a test red, and each of them hands part of the decision to whatever order
the simulator happened to emit.

WHAT THE PROBE FOUND OVER REAL GAMES. `utils/permutation_probe.py` runs the same
comparison over played games, where the boards are far richer than anything a
builder produces. Over 18,174 decisions in 150 mirror games, **101 (0.56%) are
decided by the order of the menu**, and the interesting part is which kinds tie:

    context TO_HAND   which card the search brings back        34
    context MAIN      an ability against the manual attachment 23
    context MAIN      one ability against another               16
    context DISCARD   which card is discarded                   12
    context MAIN      attacking against retreating               4
    context MAIN      attacking against benching a body          3
    ... plus five singletons

Two thirds of those are choices between cards where the rules genuinely have
nothing to say yet. The last dozen are not: attacking or retreating is not a tie,
it is a rule that was never written, and it is being settled by the engine's
emission order. That list is a work item, not an assertion, and it is written up
in the night's report rather than frozen here.

WHAT IS ASSERTED HERE: the synthetic boards, where the answer is deterministic
and the suite can own it. 288 grid boards times three permutations, plus a
twelve-option board with a full hand swept over five values of their energy and
six of their prize pile, eight permutations each. All of them invariant today --
so this file is a ratchet: a rule that starts reading positions instead of the
board turns it red.

HOW SENSITIVE IT ACTUALLY IS, measured rather than claimed. A positional bias was
injected into the final ordering (`finalizar`, a bonus for whatever sits at index
0) and grown until this file noticed:

    +500     4 passed      -- invisible
    +5000    1 failed      -- caught
    reversing the tie-break itself     4 passed  -- invisible

The last line is the honest limit and the reason `utils/permutation_probe.py`
exists: the synthetic boards carry no TIES, so a change to how ties break cannot
show up here at all. The score bands of this agent are thousands apart, so what
this file guards is a positional bias big enough to jump a band. The tie
population lives on played boards and is measured there.
"""

import copy
import itertools
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests"), str(ROOT / "utils")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main as m  # noqa: E402
import test_grid_attack_or_retreat as grid  # noqa: E402
from golden_corpus import reset_agent  # noqa: E402
from permutation_probe import meaning  # noqa: E402
from state_builder import G, Scenario, pk  # noqa: E402

OGERPON = m.Teal_Mask_Ogerpon_ex
HYDRA = m.Hydrapple_ex
APPLIN = m.Applin
TAPU = m.Tapu_Bulu
MEOWTH = m.Meowth_ex
DIPPLIN = m.Dipplin
DUNSPARCE = 144


def _play(obs):
    """What the agent chose, as plays rather than as indexes."""
    choice = m.agent(obs)
    return sorted(meaning(m, obs, i) for i in choice)


def _shuffled(obs, rng):
    options = obs["select"]["option"]
    order = list(range(len(options)))
    rng.shuffle(order)
    twin = copy.deepcopy(obs)
    twin["select"]["option"] = [options[i] for i in order]
    return twin


def _invariant(factory, cells, permutations, seed):
    """Every cell decided the same way under every permutation of its menu."""
    rng = random.Random(seed)
    broken = []
    for cell in cells:
        reset_agent(m)
        obs = factory(**cell)
        expected = _play(obs)
        for _ in range(permutations):
            twin = _shuffled(obs, rng)
            reset_agent(m)
            if _play(twin) != expected:
                broken.append((cell, expected, _play(twin)))
                break
    return broken


def _cells(axes):
    names = list(axes)
    return [dict(zip(names, values))
            for values in itertools.product(*(axes[n] for n in names))]


def test_the_grid_decides_the_same_under_any_menu_order():
    """The 288 boards of the attack-or-retreat sweep, three permutations each."""
    broken = _invariant(grid.build, _cells(grid.AXES), permutations=3, seed=11)
    assert not broken, f"la posicion en el menu decidio: {broken[:3]}"


def _rich(their_energy, op_prizes):
    """A twelve-option board: a full hand, two chargeable bodies, an attack, a
    retreat and the turn's attachment all live at once.

    A menu with three options can hardly express a positional bug. This is the
    widest board the builder can make while staying legal, which is where a tie
    has room to appear.
    """
    return (Scenario(turn=9, step=55, own_prizes=4)
            .my_active(pk(OGERPON, energies=[G, G], fisicas=2))
            .my_bench(pk(HYDRA, energies=[G], fisicas=1, pre_evo=[APPLIN]),
                      pk(TAPU, energies=[G], fisicas=1), pk(APPLIN))
            .op_active(pk(OGERPON, energies=[G] * their_energy,
                          fisicas=their_energy))
            .op_bench(pk(TAPU), pk(DUNSPARCE))
            .op_zones(hand=5, deck=28, prizes=op_prizes)
            .my_hand(m.Basic_Grass_Energy, m.Basic_Grass_Energy, m.Ultra_Ball,
                     m.Lillie_Determination, m.Night_Stretcher, DIPPLIN)
            .deck(m.Basic_Grass_Energy, m.Basic_Grass_Energy, MEOWTH)
            .rest_to_discard()
            .menu_hand(with_retreat=True, with_attack=True,
                       with_attachment=True)
            .build())


def test_a_wide_menu_decides_the_same_under_any_order():
    broken = _invariant(
        _rich,
        _cells({"their_energy": [1, 2, 3, 4, 5],
                "op_prizes": [6, 5, 4, 3, 2, 1]}),
        permutations=8, seed=5)
    assert not broken, f"la posicion en el menu decidio: {broken[:3]}"


def test_the_wide_board_really_is_wide():
    """A guard on the guard: if the builder ever stops emitting the whole menu,
    the test above would pass by measuring nothing."""
    assert len(_rich(3, 4)["select"]["option"]) >= 10


def test_the_meaning_of_an_option_survives_the_permutation():
    """The comparison itself has to be index-free, or the test would report a
    divergence every single time. Same option, two positions, one meaning."""
    obs = _rich(3, 4)
    options = obs["select"]["option"]
    twin = copy.deepcopy(obs)
    twin["select"]["option"] = list(reversed(options))
    last = len(options) - 1
    assert meaning(m, obs, 0) == meaning(m, twin, last)
