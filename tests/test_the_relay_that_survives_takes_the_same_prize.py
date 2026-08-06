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

The prize gate (`_reply_closes_the_game`) keeps it a defensive pivot rather than
a preference: a trade we merely dislike is not worth the retreat cost, the game
is.

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


def test_it_does_not_fire_when_their_reply_is_not_the_game():
    """Six prizes on their side: our ex is a trade, not the match. The retreat
    cost is not worth paying for that."""
    chosen = _chosen(_board("retreat", active_energies=3, op_prizes=6))
    assert chosen["type"] == int(m.OptionType.ATTACK), chosen


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


def test_the_prize_gate_reads_the_board_after_our_own_knockout():
    """Their prizes minus what we are about to knock out, against what our
    active hands over."""
    alakazam = _stub(ALAKAZAM, 140)          # a 1-prize Stage 2
    hydra = _stub(HYDRA, 110)                # ours, 2 prizes
    assert m.prize_count_op(alakazam) == 1 and m.prize_count(hydra) == 2
    # Three prizes left: after our knockout they need two, and our ex is two.
    assert m._reply_closes_the_game(hydra, SimpleNamespace(prize=[None] * 3),
                                    alakazam)
    # Four: they still need one more turn after cashing our ex.
    assert not m._reply_closes_the_game(hydra, SimpleNamespace(prize=[None] * 4),
                                        alakazam)
    # And our own knockout already winning is not a reply to survive.
    assert not m._reply_closes_the_game(hydra, SimpleNamespace(prize=[None]),
                                        alakazam)
