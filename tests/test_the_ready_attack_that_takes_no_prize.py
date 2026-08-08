"""A ready attack that takes no prize is not what the turn is for.

Scenario (`records/registro_008_pasos_057_hasta_057.json` step 57, turn 8,
episode 90874130 vs Mega Lucario ex, LOST):

    US (6 prizes)                        RIVAL (5 prizes)
    active  Teal Mask Ogerpon ex         active  Mega Lucario ex 340/340
            210/210, 3 Grass             bench   Mega Lucario ex 340/340
    bench   Chikorita 70, Applin 40              Solrock, Solrock, Lunatone,
            Teal Mask Ogerpon ex x2              Riolu
            (1 Grass each)
    hand    Meowth ex, Hydrapple ex, Meganium, Teal Mask Ogerpon ex,
            Xerosic's Machinations, Unfair Stamp, Forest of Vitality x2
            -- and NOT ONE Basic Grass

Myriad Leaf Shower is 30 + 30 for each Energy on BOTH Active Pokemon: three on
us, one on them, 150 against a 340 HP Mega Lucario ex at full health. No
knockout, no prize -- and the body that throws it is dead to Mega Brave (270)
on the reply. The agent attacked as its FIRST and ONLY action and closed the
turn with eight cards in hand, the Supporter slot unspent and a Meowth ex whose
Last-Ditch Catch was free. In the record the chip left the Lucario at 190, they
attacked with that same 190 body, and the game was lost.

The veto that produced it reads `_active_ready_attacker`: "our active can
attack, so we do not spend a 2-prize body on searching for a Supporter". It
measures whether the attack is LEGAL, not whether it is worth anything. The
turn plan had already said it was not -- `prizes_today=0`, `op_prizes_next=2`,
mode DEVELOP -- which is exactly what `_ready_attack_is_inert` now asks.

And it was never a choice between the two. A Pokemon PLAY lives in
`_TIER_DEVELOP` (40) and the attack in tier 0, so the body goes down,
Last-Ditch Catch fetches the Supporter, the Supporter is played and the attack
STILL closes the turn ([[el-hueco-de-supporter-muere-con-el-ataque-que-cierra-
el-turno]]).

Deck-agnostic in both directions: the flag names no card and no archetype, it
reads the prize arithmetic of the plan. It is the general case of a carve-out
`_active_ready_attacker` already had -- an attacker that does ZERO to an immune
wall is not a ready attacker. Zero damage is the degenerate end of "takes no
prize".

What the turn becomes, rolled forward with the real simulator from this exact
board (`cg.api.search_begin/search_step`): Meowth ex -> Last-Ditch Catch ->
Dawn -> the Applin line -> two evolutions -> retreat, and the turn ends with a
Hydrapple ex 330/330 in front. Mega Brave does 270 to it: they take ZERO prizes
on the reply instead of the two the chip conceded.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import G, Scenario, pk

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "lucario_inert_myriad_benches_the_meowth_step57.json")

OGERPON = m.Teal_Mask_Ogerpon_ex
MEOWTH = m.Meowth_ex
MEGA_LUCARIO = 678
RIOLU = 677
SOLROCK = 676


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._cards_prizes_identified = False
    m._cards_last_turn = -1
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m.meganium_in_play = False
    m.forest_in_play = False
    m.ko_last_turn = False
    m._ko_detected_this_turn = False
    m._prev_op_prize = 6
    m.we_go_first = False
    m.op_is_crustle_deck = False
    m.op_is_cornerstone_deck = False
    m.op_has_mega_kangaskhan = False
    m.op_is_starmie_deck = False
    m._field_at_turn_start = {}
    yield
    m._init_cards_tracking()


def _obs():
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])


def _option(obs, **match):
    for i, o in enumerate(obs["select"]["option"]):
        if all(o.get(k) == v for k, v in match.items()):
            return i
    raise AssertionError(f"no option matches {match}")


def _meowth_option(obs):
    mine = obs["current"]["players"][obs["current"]["yourIndex"]]
    for i, o in enumerate(obs["select"]["option"]):
        if (o.get("type") == int(m.OptionType.PLAY)
                and mine["hand"][o["index"]]["id"] == MEOWTH):
            return i
    raise AssertionError("the Meowth ex is not on the menu")


# ---------------------------------------------------------------------------
# 1. The board: without this, the test measures nothing
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_inert_myriad_in_front_of_the_lucario():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mine, opponent = o["current"]["players"][yo], o["current"]["players"][1 - yo]

    active = mine["active"][0]
    assert active["id"] == OGERPON and active["hp"] == active["maxHp"] == 210

    # READY: Myriad Leaf Shower costs three and there are three Grass on it. This
    # is the whole point -- the attack is legal, and it is still worth nothing.
    assert m.ATTACK_ENERGY_REQ_BASE[OGERPON] == 3
    assert len(active["energies"]) == 3
    assert any(x.get("type") == int(m.OptionType.ATTACK)
               for x in o["select"]["option"])

    # INERT: 30 + 30 x (3 ours + 1 theirs) = 150 against 340 at full health.
    wall = opponent["active"][0]
    assert wall["id"] == MEGA_LUCARIO and wall["hp"] == wall["maxHp"] == 340
    assert len(wall["energies"]) == 1

    # ...and the body that throws it does not live to throw a second one:
    # Mega Brave is 270 against 210.
    assert m._op_active_attack_damage_to(
        m.to_observation_class(o).current.players[1 - yo].active[0],
        m.to_observation_class(o).current.players[yo].active[0],
        opponent["handCount"]) >= active["hp"]

    # The hand engine is intact and free: a Meowth ex in hand, none in play, one
    # bench slot left, the Supporter slot unspent -- and no Lillie's in hand.
    assert sum(1 for c in mine["hand"] if c["id"] == MEOWTH) == 1
    assert all(b["id"] != MEOWTH for b in mine["bench"])
    assert len(mine["bench"]) == 4 and mine["benchMax"] == 5
    assert not o["current"]["supporterPlayed"]
    assert all(c["id"] != m.Lillie_Determination for c in mine["hand"])

    # Neither of the two narrower arms of the ladder can see this board: the
    # hand is EIGHT cards (the 21500 arm caps at 4) and the bench holds four
    # bodies (the 21400 arm caps at 1).
    assert mine["handCount"] == 8


def test_the_plan_reads_the_turn_as_sterile():
    """The flag is the plan's arithmetic, not a new reading of the board."""
    o = _obs()
    m.agent(o)
    plan = m.AGENT_STATE.turn_plan
    assert plan.prizes_today == 0, "the turn takes no prize"
    assert plan.op_prizes_next >= 1, "and the body in front dies on the reply"
    assert not plan.wins_this_turn


# ---------------------------------------------------------------------------
# 2. The decision
# ---------------------------------------------------------------------------

def test_the_inert_attack_does_not_veto_the_hand_engine():
    o = _obs()
    chosen = m.agent(o)
    assert chosen == [_meowth_option(o)], (
        f"el Myriad de 150 contra un muro de 340 a vida llena no toma premio y "
        f"el cuerpo que lo lanza muere en la replica: el turno vale lo que la "
        f"mano construya. Bajar el Meowth ex (opt {_meowth_option(o)}) para "
        f"encadenar Last-Ditch Catch -> Supporter, no atacar "
        f"(opt {_option(o, type=int(m.OptionType.ATTACK))}); obtuvo {chosen}")


def test_the_play_defers_the_attack_it_does_not_replace_it():
    """The whole argument is one of SEQUENCE. The body has to win as a PLAY --
    by ORDER tier, above the attack -- and the attack has to still be on the
    menu, to be thrown at the end of the same turn."""
    o = _obs()
    chosen = m.agent(o)
    opt = o["select"]["option"][chosen[0]]
    assert opt.get("type") == int(m.OptionType.PLAY)
    assert any(x.get("type") == int(m.OptionType.ATTACK)
               for x in o["select"]["option"])


# ---------------------------------------------------------------------------
# 3. Deck-agnostic, and one control per guard
# ---------------------------------------------------------------------------
#
# The synthetic boards below carry NO Mega Lucario: the rule is read off the
# prize arithmetic, so any body that walls the attack and one-shots the
# attacker produces it. Every control was checked against the PREVIOUS version
# of the tree -- on the first board it answers ATTACK and on each control it
# already answers what is asserted here -- so the controls really do isolate
# this rule ([[corpus-dorado-registros-que-no-vigilaban-nada]]).

WALL = dict(hp=340, max_hp=340, energies=[G])

# A hand of FIVE, deliberately: the arm this file pins is the only one in the
# ladder with nothing to say about hand size, and a shorter hand would hand the
# decision to the 21500 "weak hand" arm instead (<= 4 cards) and measure that.
# The cards are the record's own leftovers, minus two of them: the Forest of
# Vitality (in the record it was already IN PLAY; in hand its own 21900 would
# decide the turn and this file would be measuring the stadium) and the Unfair
# Stamp (on a hand this short its refresh becomes the play, and a Stamp
# shuffles away the very Supporter the fetch is for). An Applin takes their
# place: a plain development body at 21200, which is also the control that this
# arm outranks ordinary development and is not merely riding on it.
_FULL_HAND = (m.Hydrapple_ex, m.Meganium, m.Xerosic_Machinations, m.Applin)


def _sterile_turn(active, bench, op_active, op_prizes=5, my_prizes=6):
    """Our turn with the hand engine available and the attack on the menu."""
    esc = (Scenario(turn=8, step=57, tac=1, first_player=1, own_prizes=my_prizes)
           .my_active(active)
           .my_bench(*bench)
           .my_hand(MEOWTH, *_FULL_HAND)
           .op_active(op_active)
           .op_bench(pk(RIOLU, hp=80, max_hp=80))
           .op_zones(hand=3, deck=23, prizes=op_prizes))
    esc.deck(*sorted(esc._pool.elements())[:34]).rest_to_discard()
    return esc.menu_hand(with_retreat=True, with_attack=True).build()


def _benches_the_meowth(obs):
    return m.agent(obs) == [_meowth_option(obs)]


def _lucario_free_wall():
    """A 340 HP body with one energy that one-shots a 210 HP ex: the shape,
    not the card. Mega Lucario ex is the one this deck meets, and using it
    keeps the projection honest -- what is NOT used is any Lucario branch."""
    return pk(MEGA_LUCARIO, pre_evo=[RIOLU], **WALL)


def test_the_ready_attack_that_takes_no_prize_benches_the_body():
    obs = _sterile_turn(pk(OGERPON, energies=[G, G, G], fisicas=3),
                        [pk(OGERPON, energies=[G], fisicas=1),
                         pk(m.Chikorita, hp=70, max_hp=70)],
                        _lucario_free_wall())
    assert _benches_the_meowth(obs)


def test_an_attack_that_takes_a_prize_keeps_the_veto():
    """Guard `prizes_today`. The same charged Ogerpon, and in front of it a
    body Myriad DOES knock out. The attack is the turn: nothing is dug for."""
    obs = _sterile_turn(pk(OGERPON, energies=[G, G, G], fisicas=3),
                        [pk(OGERPON, energies=[G], fisicas=1),
                         pk(m.Chikorita, hp=70, max_hp=70)],
                        pk(SOLROCK, hp=110, max_hp=110, energies=[G]))
    assert not _benches_the_meowth(obs)


def test_an_attacker_that_survives_the_reply_keeps_the_veto():
    """Guard `op_prizes_next`. A body that lives to attack again turns today's
    150 into an instalment, not a waste: the chip is a plan, and a plan is not
    a sterile turn."""
    obs = _sterile_turn(pk(m.Hydrapple_ex, hp=330, max_hp=330,
                           energies=[G, G, G], fisicas=3),
                        [pk(OGERPON, energies=[G], fisicas=1),
                         pk(m.Chikorita, hp=70, max_hp=70)],
                        _lucario_free_wall())
    assert not _benches_the_meowth(obs)


def test_charged_relief_on_the_bench_keeps_the_veto():
    """Guard `_ready_attacker_count <= 1`. With a second charged body waiting
    there IS an answer when the active falls, so the turn throws nothing away
    and the 2-prize body is not worth exposing."""
    obs = _sterile_turn(pk(OGERPON, energies=[G, G, G], fisicas=3),
                        [pk(OGERPON, energies=[G, G, G], fisicas=3),
                         pk(m.Chikorita, hp=70, max_hp=70)],
                        _lucario_free_wall())
    assert not _benches_the_meowth(obs)


def test_at_their_match_point_keeps_the_veto():
    """Guard `op_prize > 2`. Plain arithmetic: at their match point the
    2-prize body we bench IS the game, and no Supporter buys that back
    ([[promocion-match-point-y-desempate-supervivientes]])."""
    obs = _sterile_turn(pk(OGERPON, energies=[G, G, G], fisicas=3),
                        [pk(OGERPON, energies=[G], fisicas=1),
                         pk(m.Chikorita, hp=70, max_hp=70)],
                        _lucario_free_wall(), op_prizes=2)
    assert not _benches_the_meowth(obs)
