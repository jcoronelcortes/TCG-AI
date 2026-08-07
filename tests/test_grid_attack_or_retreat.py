"""The attack-or-retreat decision, swept over the whole board instead of one cell.

Every rule in the retreat menu was measured on the single board that produced
it. Three of them landed in the same week (the retreat that chooses who pays the
prize, the bench that does not shrink on a swap, the prize gate that was reading
the wrong pile) and none of the three was ever measured with the other two
switched on. This file sweeps 288 boards through `tests/decision_grid.py` and
asserts the three properties a per-board test cannot see.

WHAT IS ASSERTED, and why each one is worth a suite second:

  1. NOTHING BREAKS. 288 synthetic boards, every one legal, and the agent
     returns a valid option on all of them. An exception in a real game is a
     forfeit, and the boards here are the awkward corners -- an Applin in front
     with a charged Tapu behind it, an ex at 60 HP with nothing to promote.

  2. THE DECISION STAYS DECIDED. Along an axis ordered from calm to desperate --
     their prize pile shrinking, their attacker growing -- a defensive decision
     may switch ON once and must never switch back off. A rule that retreats at
     four prizes, attacks at three and retreats at two is not a strategy, it is
     two rules interfering, and that is precisely what one board cannot show.

  3. THE KNOCKOUT IS WHAT MOVES IT. The one boundary the sweep does find sits on
     their energy count, and it is the KO line, not a defensive one: with two
     energies on their Ogerpon our Myriad reads 180 against 210 HP and we look
     for another line; with three it reads 240 and the front body swings. That
     is "attacking with the active comes first" (strategy §2), and pinning it
     here means a future rule that quietly outbids the attack shows up as a
     changed boundary rather than as a lost matchup three weeks later.

WHAT IS DELIBERATELY *NOT* ASSERTED: that the decision ignores their prize pile.
It does -- all six values decide alike in every one of the 288 cells -- and that
is the measured policy of this deck (the prize-denial pivot was built, measured
and reverted twice; see `TurnPlan.denial_saves_the_game`), not a property to
freeze. What the sweep DID expose is narrower and lives elsewhere: when our own
attack knocks their active out, the turn plan stops projecting a reply at all --
and a knockout forces a promotion from a bench that is fully visible.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main as m  # noqa: E402
from decision_grid import boundaries, monotone_along, sweep  # noqa: E402
from state_builder import G, Scenario, pk  # noqa: E402

OGERPON = m.Teal_Mask_Ogerpon_ex
TAPU = m.Tapu_Bulu
CHIKORITA = m.Chikorita
APPLIN = m.Applin

ACTIVES = {
    "ex_healthy": lambda: pk(OGERPON, energies=[G, G, G], fisicas=3),
    "ex_wounded": lambda: pk(OGERPON, hp=60, energies=[G, G, G], fisicas=3),
    "applin": lambda: pk(APPLIN, energies=[G], fisicas=1),
}
RELAYS = {
    "tapu_charged": lambda: [pk(TAPU, energies=[G, G, G, G], fisicas=4)],
    "tapu_bare": lambda: [pk(TAPU)],
    "chikorita": lambda: [pk(CHIKORITA)],
    "ogerpon_2nd": lambda: [pk(OGERPON, energies=[G, G, G], fisicas=3)],
}

AXES = {
    # ordered from calm to desperate: their pile shrinking is more urgent
    "op_prizes": [6, 5, 4, 3, 2, 1],
    # ... and so is their attacker growing (Myriad counts both actives)
    "their_energy": [2, 3, 4, 5],
    "our_active": list(ACTIVES),
    "relay": list(RELAYS),
}


def build(op_prizes, their_energy, our_active, relay):
    """The same board everywhere; only the four axes move.

    The hand is EMPTY on purpose: with a Grass in it the attachment outscores
    everything and all 288 cells decide alike, which measures the attachment
    rule and not this one.
    """
    return (Scenario(turn=10, step=61, own_prizes=4)
            .my_active(ACTIVES[our_active]())
            .my_bench(*RELAYS[relay]())
            .op_active(pk(OGERPON, energies=[G] * their_energy,
                          fisicas=their_energy))
            .op_zones(hand=5, deck=28, prizes=op_prizes)
            .deck(m.Basic_Grass_Energy, m.Basic_Grass_Energy)
            .rest_to_discard()
            .menu_hand(with_retreat=True, with_attack=True)
            .build())


@pytest.fixture(scope="module")
def rows():
    return sweep(build, AXES)


def test_every_cell_of_the_grid_is_decided(rows):
    """288 legal boards, 288 valid answers. An exception here is a forfeit."""
    broken = [r for r in rows if r["error"]]
    assert not broken, f"celdas rotas: {broken[:3]}"
    assert len(rows) == 6 * 4 * 3 * 4
    for row in rows:
        assert row["choice"] and len(row["choice"]) == 1, row


def test_the_defensive_decision_does_not_come_back(rows):
    """Monotone along both danger axes: retreat may switch on once, never twice.

    Validated by mutation while it was written -- forcing the retreat on at a
    single interior value of `their_energy` makes it report the violation with
    the whole sequence, which is what the message has to show to be useful."""
    for axis, reverse in (("op_prizes", True), ("their_energy", False)):
        violations = monotone_along(
            rows, axis, lambda r: r["label"] == "RETREAT",
            AXES[axis], reverse=reverse)
        assert not violations, (
            f"la decision defensiva vuelve sobre {axis}: {violations[:2]}")


def test_the_only_boundary_is_the_knockout(rows):
    """Their energy is the axis that moves the decision, and it moves it once.

    Two energies: Myriad reads 30+30*(3+2) = 180 against 210 HP, no knockout.
    Three: 240, and the body in front swings. Every boundary the sweep finds on
    this axis sits on that step, and it points from RETREAT to ATTACK -- never
    the other way, which would be the agent declining a knockout it has."""
    on_energy = [b for b in boundaries(rows, AXES) if b["axis"] == "their_energy"]
    assert on_energy, "el barrido dejo de encontrar la linea del KO"
    for b in on_energy:
        assert (b["from"], b["to"]) == (2, 3), b
        assert b["decision"] == "RETREAT -> ATTACK", b


def test_the_body_that_cannot_attack_never_stands_and_fights(rows):
    """An Applin in front with one energy has no attack worth the turn; whatever
    the rest of the board says, the answer is never to swing with it."""
    for row in rows:
        if row["our_active"] == "applin":
            assert row["label"] != "ATTACK", row


# ---------------------------------------------------------------------------
# The sweeper itself: a property checker that cannot fail proves nothing
# ---------------------------------------------------------------------------

def _table(pairs):
    return [{"danger": d, "other": "x", "choice": (0,), "error": None,
             "label": lab} for d, lab in pairs]


def test_monotone_along_reports_a_decision_that_comes_back():
    """ON, OFF, ON along the danger axis is the shape being watched for."""
    rows = _table([(1, "ATTACK"), (2, "RETREAT"), (3, "ATTACK"), (4, "RETREAT")])
    violations = monotone_along(
        rows, "danger", lambda r: r["label"] == "RETREAT", [1, 2, 3, 4])
    assert len(violations) == 1
    assert violations[0]["sequence"] == [(1, False), (2, True), (3, False),
                                         (4, True)]


def test_monotone_along_accepts_a_decision_that_switches_once():
    rows = _table([(1, "ATTACK"), (2, "ATTACK"), (3, "RETREAT"), (4, "RETREAT")])
    assert monotone_along(rows, "danger",
                          lambda r: r["label"] == "RETREAT", [1, 2, 3, 4]) == []
