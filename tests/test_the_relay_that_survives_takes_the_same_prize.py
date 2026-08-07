"""The knockout is available either way: take it with the body that survives.

User, registro_012 step 120 vs Alakazam, LOST (episode 90099795). Turn 12, four
prizes to three. Our active was a Hydrapple ex at 110 of its 330 HP with two
energies, and its Syrup Storm finished their Alakazam from the front. So the
agent spent the turn on Teal Dance and attacked. Their reply -- Powerful Hand,
twenty per card in a hand of six -- knocked that 110 HP body out, took the two
prizes it hands over, and closed the game.

One energy short of its retreat cost sat the answer: a benched Teal Mask Ogerpon
ex with three energies whose Myriad Leaf Shower finished the same Alakazam, from
210 HP, out of reach of that same reply. Charge the active, retreat, promote,
attack. Same prize this turn, and the body left in front lives to take the next
one.

TWO GUARDS FAILED, AND BOTH ARE FIXED HERE.

`_grass_unlocks_active_retreat` -- the detector of the whole "Grass to the
active, retreat, attack with the benched one" line -- gives up the moment the
active can finish from the front. `_active_can_ko_now` vetoes the retreat itself
for the same reason. Both are right while the active can afford to stand there,
and neither asks whether it can.

WHY IT IS SCOPED TO THE REPLY ONLY THE HAND REVEALS. Powerful Hand places
counters, so the attack table prints damage 0 and every defensive rule in the
agent reads their Alakazam as harmless. That is the seam. Where the opposing
attack is readable the ordinary way, the pivots built and measured against those
boards already decide -- and they decide differently: the Marnie records spend
that same Grass healing a doomed Dipplin instead. `_hand_revealed_lethal_reply`
draws the line by reading the attack twice, once the way everyone else reads it
and once counting their hand, and only speaks when the second is lethal and the
first is not.

The prize gate (`_reply_reaches_match_point`) keeps THIS pivot a defensive one
rather than a preference: a trade we merely dislike is not worth the retreat
cost, the game is. It is also what still scopes the expensive half of the line,
the Grass spent on the active to unlock the retreat.

THAT GATE WAS READING THE WRONG PILE (fixed Aug 2026). It used to subtract
`prize_count_op(their active)` from their prizes before comparing, as if the
knockout we are about to take came out of THEIR pile. It comes out of ours
(record 90350002: finishing their Alakazam moved OUR prizes from 4 to 3 and left
theirs at 1; `utils/selfplay.py` says the same thing where it counts prizes
taken). The subtraction made a pile of three read like a pile of one and -- the
part that cost something -- made their MATCH POINT read as zero, so the gate
failed its own `>= 1` guard and went quiet on the one board where losing the
active loses the game.

Sweeping their pile from one to six over this same board, exactly ONE decision
changes: at a pile of one the Grass now goes to the active instead of the bench.
Two upwards is untouched, which is also why 900 self-play games against the
Alakazam bot showed ZERO divergence between the old formula and the new one --
the gate is only reachable behind Powerful Hand, and we win that matchup often
enough that they rarely reach one prize while still threatening.

Later note (registro_008 step 126): the RETREAT itself is no longer only this
pivot's business. `_front_spot_upgrade` reads the same shape -- two of our
bodies take the same knockout, their reply removes one of them -- without the
prize gate, and takes the boards this one leaves alone. See
`test_the_front_spot_goes_to_the_body_that_pays_less.py`.

Golden corpus: 3 flips, all of them in this same losing turn, all of them Teal
Dance -> charge the active for the retreat.
"""

import copy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import Scenario, pk, G

HYDRA, APPLIN, DIPPLIN = m.Hydrapple_ex, m.Applin, m.Dipplin
OGERPON, CHIKORITA, BAYLEEF = m.Teal_Mask_Ogerpon_ex, m.Chikorita, m.Bayleef
ALAKAZAM, ABRA, KADABRA = m.Alakazam_ex, m.Abra, m.Kadabra
DUNSPARCE = 305
HANDHELD_FAN = 1161      # the tool their Alakazam carried; it adds no damage
GRASS = m.Basic_Grass_Energy


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _board(menu, active_energies=2, op_hand=6, op_prizes=3, relay_energies=3):
    """The board of step 120, with the four knobs the guards need.

    `menu` walks the line: "attach" is the turn as the record found it,
    "retreat" is the same board one energy later, "promote" is the switch
    prompt, "attack" is the promoted body's turn to swing.
    """
    sc = (Scenario(turn=12, step=120, tac=13, own_prizes=4,
                   energy_played=(menu != "attach"), supporter_played=True,
                   stadium_played=True)
          .my_active(pk(HYDRA, hp=110, energies=[G] * active_energies,
                        fisicas=active_energies, pre_evo=[APPLIN, DIPPLIN]))
          .my_bench(pk(BAYLEEF, pre_evo=[CHIKORITA]),
                    pk(OGERPON, energies=[G] * relay_energies,
                       fisicas=relay_energies),
                    pk(OGERPON, energies=[G, G], fisicas=2),
                    pk(OGERPON, energies=[G], fisicas=1))
          .op_active(pk(ALAKAZAM, hp=140, max_hp=140, energies=[G],
                        pre_evo=[ABRA], tools=[HANDHELD_FAN]))
          .op_bench(pk(KADABRA, hp=80, max_hp=80, energies=[G], pre_evo=[ABRA]),
                    pk(ALAKAZAM, hp=140, max_hp=140, energies=[G],
                       pre_evo=[ABRA], tools=[HANDHELD_FAN]),
                    pk(KADABRA, hp=80, max_hp=80, pre_evo=[ABRA]),
                    pk(DUNSPARCE, hp=70, max_hp=70))
          .op_zones(hand=op_hand, deck=13, prizes=op_prizes))
    if menu == "attach":
        sc = sc.my_hand(GRASS).deck().rest_to_discard().menu_hand(
            with_attachment=True, with_attack=True)
    elif menu == "retreat":
        sc = sc.my_hand().deck().rest_to_discard().menu_hand(
            with_retreat=True, with_attack=True)
    else:
        sc = sc.my_hand().deck().rest_to_discard().promote_after_retreat()
    return sc.build()


def _chosen(obs):
    return obs["select"]["option"][m.agent(copy.deepcopy(obs))[0]]


def _stub(card_id, hp, tools=(), energies=0):
    return SimpleNamespace(id=card_id, hp=hp, maxHp=hp, tools=list(tools),
                           energies=[1] * energies, energyCards=[])


# ---------------------------------------------------------------------------
# 1. The board really is the one from the record
# ---------------------------------------------------------------------------

def test_both_bodies_finish_and_only_one_of_them_survives():
    obs = m.to_observation_class(copy.deepcopy(_board("attach")))
    cur = obs.current
    mine = cur.players[cur.yourIndex]
    theirs = cur.players[1 - cur.yourIndex]
    active, op_active = mine.active[0], theirs.active[0]
    relay = mine.bench[1]
    grass = sum(len(p.energies) for p in [active] + [b for b in mine.bench if b])

    # Their Alakazam prints damage 0: read the ordinary way it is harmless, and
    # counting their hand it kills our 110 HP active.
    assert m._op_active_attack_damage_to(op_active, active) == 0
    reply = m._op_active_attack_damage_to(op_active, active,
                                          op_hand_count=theirs.handCount)
    assert reply >= (active.hp or 0)

    # And it does NOT reach the relay, which finishes the same Alakazam.
    assert reply < (relay.hp or 0)
    after = max(0, grass - m._retreat_grass_units(m.RETREAT_COST[HYDRA]))
    assert m._bench_finisher_that_survives(
        mine, op_active, False, 4, after, False, reply, m.prize_count(active))


# ---------------------------------------------------------------------------
# 2. The line, step by step
# ---------------------------------------------------------------------------

def test_the_grass_pays_the_retreat_instead_of_feeding_teal_dance():
    chosen = _chosen(_board("attach"))
    assert chosen["type"] == int(m.OptionType.ATTACH), chosen
    assert chosen["inPlayArea"] == int(m.AreaType.ACTIVE), (
        "the Grass belongs on the active: it is one energy short of the retreat "
        "cost that unlocks the relay")


def test_the_active_retreats_even_though_it_finishes_from_the_front():
    chosen = _chosen(_board("retreat", active_energies=3))
    assert chosen["type"] == int(m.OptionType.RETREAT), chosen


def test_the_relay_that_comes_up_is_the_charged_ogerpon():
    obs = _board("promote", active_energies=3)
    mine = obs["current"]["players"][obs["current"]["yourIndex"]]
    relay = next(i for i, b in enumerate(mine["bench"])
                 if b["id"] == OGERPON and len(b["energies"]) == 3)
    assert m.agent(copy.deepcopy(obs)) == [relay]


def test_the_promoted_relay_attacks_and_finishes():
    """The board after the retreat: the Ogerpon ex is in front with its three
    energies and the Hydrapple is on the bench, its own discarded paying the
    cost."""
    obs = (Scenario(turn=12, step=122, tac=16, own_prizes=4, energy_played=True,
                    supporter_played=True, stadium_played=True, retirado=True)
           .my_active(pk(OGERPON, energies=[G, G, G], fisicas=3))
           .my_bench(pk(HYDRA, hp=110, pre_evo=[APPLIN, DIPPLIN]),
                     pk(BAYLEEF, pre_evo=[CHIKORITA]),
                     pk(OGERPON, energies=[G, G], fisicas=2),
                     pk(OGERPON, energies=[G], fisicas=1))
           .op_active(pk(ALAKAZAM, hp=140, max_hp=140, energies=[G],
                         pre_evo=[ABRA], tools=[HANDHELD_FAN]))
           .op_bench(pk(KADABRA, hp=80, max_hp=80, energies=[G], pre_evo=[ABRA]),
                     pk(ALAKAZAM, hp=140, max_hp=140, energies=[G], pre_evo=[ABRA]),
                     pk(DUNSPARCE, hp=70, max_hp=70))
           .op_zones(hand=6, deck=13, prizes=3)
           .my_hand().deck().rest_to_discard().menu_hand(with_attack=True)
           .build())
    chosen = _chosen(obs)
    assert chosen["type"] == int(m.OptionType.ATTACK), chosen


# ---------------------------------------------------------------------------
# 3. The guards
# ---------------------------------------------------------------------------

def test_a_relay_that_dies_to_the_same_reply_buys_nothing():
    """Nine cards in their hand puts Powerful Hand over the 210 HP of the relay
    too. With nothing left standing either way, the active takes the prize from
    the front."""
    chosen = _chosen(_board("retreat", active_energies=3, op_hand=9))
    assert chosen["type"] == int(m.OptionType.ATTACK), chosen


def test_when_their_reply_is_only_a_trade_the_wider_rule_takes_the_board():
    """Six prizes on their side: our ex is a trade, not the match, and THIS
    pivot stays silent -- `_reply_reaches_match_point` is what scopes it, and it is
    what the Grass-to-the-active half is still spent on.

    The retreat happens anyway, and by a different name. `_front_spot_upgrade`
    (registro_008 step 126) reads the same board without the prize gate: two
    bodies take the same knockout, their reply removes one of them and not the
    other, so the one left standing is the one that outlasts it. The boundary
    moved on purpose; what this test pins is that it moved to the OTHER rule and
    that this one did not grow the gate it was measured without."""
    obs = _board("retreat", active_energies=3, op_prizes=6)
    cur = m.to_observation_class(copy.deepcopy(obs)).current
    mine = cur.players[cur.yourIndex]
    theirs = cur.players[1 - cur.yourIndex]
    assert m._reply_reaches_match_point(mine.active[0], theirs,
                                    theirs.active[0]) is False
    assert _chosen(obs)["type"] == int(m.OptionType.RETREAT)


def test_the_seam_is_the_reply_only_their_hand_reveals():
    """The predicate that scopes the whole rule. An attack the table already
    reads as lethal is somebody else's business: the pivots measured against
    those boards keep deciding them."""
    alakazam = _stub(ALAKAZAM, 140, energies=1)
    ours = _stub(HYDRA, 110)
    # Powerful Hand: invisible without the hand, lethal with it.
    assert m._op_active_attack_damage_to(alakazam, ours) == 0
    assert m._hand_revealed_lethal_reply(alakazam, ours, 6) > 0
    # A hand too small to matter reveals nothing either.
    assert m._hand_revealed_lethal_reply(alakazam, ours, 0) == 0
    # And a body it cannot reach at all.
    assert m._hand_revealed_lethal_reply(alakazam, _stub(OGERPON, 210), 6) == 0


def test_at_their_match_point_the_grass_finally_pays_the_retreat():
    """The board the old gate could never see, and the only one that moved.

    With one prize left on their side, ANY knockout wins it for them -- so the
    doomed body in front is the game, which is the exact shape this pivot exists
    for. The old gate subtracted our own winnings from their pile first, so at a
    pile of one it came out at zero, failed its own `>= 1` guard and went quiet
    precisely there. The Grass went to the bench and the 110 HP active stayed in
    front of a reply that finishes it.

    Sweeping their pile from one to six, this is the ONLY value whose decision
    changes: everything from two upwards already agreed.
    """
    chosen = _chosen(_board("attach", op_prizes=1))
    assert chosen["type"] == int(m.OptionType.ATTACH)
    assert chosen["inPlayArea"] == int(m.AreaType.ACTIVE), (
        "at their match point the Grass belongs on the active: it pays the "
        "retreat that puts a body they cannot finish in front"
    )


def test_the_boards_above_match_point_did_not_move():
    """Two prizes and up keep the decision they were measured with."""
    assert _chosen(_board("attach", op_prizes=2))["inPlayArea"] == int(m.AreaType.ACTIVE)
    assert _chosen(_board("attach", op_prizes=3))["inPlayArea"] == int(m.AreaType.ACTIVE)
    for op_prizes in (4, 5, 6):
        assert _chosen(_board("attach", op_prizes=op_prizes))["inPlayArea"] == int(
            m.AreaType.BENCH), op_prizes


def test_the_prize_gate_reads_only_their_pile():
    """What our active hands over, against THEIR remaining prizes.

    The gate used to subtract `prize_count_op(their active)` from their pile
    first, as if the knockout we are about to take came out of it. It does not:
    prizes are cashed from the pile of the player cashing them, so our winnings
    leave OUR pile (verified on record 90350002). Mixing the two sides made a
    pile of three read like a pile of one, and made their match point -- the
    board where this pivot matters most -- read as nothing at all.
    """
    alakazam = _stub(ALAKAZAM, 140)          # a 1-prize Stage 2
    hydra = _stub(HYDRA, 110)                # ours, 2 prizes
    assert m.prize_count_op(alakazam) == 1 and m.prize_count(hydra) == 2

    def gate(their_prizes):
        return m._reply_reaches_match_point(
            hydra, SimpleNamespace(prize=[None] * their_prizes), alakazam)

    # Three: their reply cashes our two and leaves them on one. Match point.
    assert gate(3)
    # Four: it leaves them on two, needing a further turn after that. A trade.
    assert not gate(4)
    assert not gate(6)
    # One or two: their reply wins outright. This is where the old subtraction
    # went quiet, and it is the board the pivot exists for.
    assert gate(1)
    assert gate(2)


def test_the_gate_does_not_read_the_body_we_are_knocking_out():
    """Their active's own prize value must not move the answer.

    It is the whole of the bug in one assertion: swap the body we are about to
    finish for one worth twice as many prizes and nothing about THEIR pile has
    changed, so the gate cannot change either.
    """
    hydra = _stub(HYDRA, 110)
    one_prize = _stub(ALAKAZAM, 140)
    two_prize = _stub(OGERPON, 210)                  # an ex: 2 prizes
    assert m.prize_count_op(one_prize) == 1 and m.prize_count_op(two_prize) == 2

    for their_prizes in (1, 2, 3, 4, 6):
        pile = SimpleNamespace(prize=[None] * their_prizes)
        assert (m._reply_reaches_match_point(hydra, pile, one_prize)
                is m._reply_reaches_match_point(hydra, pile, two_prize))


def test_a_cheaper_body_in_front_needs_them_closer_to_the_win():
    """The gate is about what WE hand over, so a one-prize body raises the bar."""
    hydra = _stub(HYDRA, 110)                        # ours, 2 prizes
    dipplin = _stub(DIPPLIN, 80)                     # ours, 1 prize
    alakazam = _stub(ALAKAZAM, 140)
    assert m.prize_count(hydra) == 2 and m.prize_count(dipplin) == 1

    def gate(body, their_prizes):
        return m._reply_reaches_match_point(
            body, SimpleNamespace(prize=[None] * their_prizes), alakazam)

    # Our two-prize ex reaches match point from three; the one-prize body only
    # does it from two, because it buys them half as much.
    assert gate(hydra, 3) and not gate(hydra, 4)
    assert gate(dipplin, 2) and not gate(dipplin, 3)


def test_a_reply_that_does_exactly_the_remaining_hp_is_lethal():
    """The boundary, found by `utils/mutation_probe.py` and not by a lost game.

    `_hand_revealed_lethal_reply` ends on `seen if seen >= hp else 0`. Rewriting
    that `>=` as `>` -- the reply that lands EXACTLY on the last hit point stops
    counting as lethal -- survived the entire suite: 1498 tests, all green, on an
    agent that would walk into every exactly-lethal blow in the game.

    Powerful Hand does 20 x (hand + 2), so a hand of 6 reads 160. A body with
    exactly 160 left dies to it, and one with 170 does not. The prize gate above
    only ever fires behind this predicate, which makes this the outer boundary of
    the whole pivot.
    """
    alakazam = _stub(ALAKAZAM, 140, energies=1)
    assert m._hand_revealed_lethal_reply(alakazam, _stub(HYDRA, 160), 6) == 160
    assert m._hand_revealed_lethal_reply(alakazam, _stub(HYDRA, 170), 6) == 0
