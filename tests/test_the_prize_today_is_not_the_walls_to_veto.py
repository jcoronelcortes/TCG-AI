"""The wall was on their BENCH, and the archetype vetoed the prize anyway.

Scenario (`records/registro_017_pasos_123_hasta_125.json`, steps 123 and 125,
turn 17, episode 93232495 vs Crustle / Mega Kangaskhan ex -- LOST):

    US (4 prizes)                          OPPONENT (3 prizes)
    active  Tapu Bulu 30/140, **2 units**  active  **Mega Kangaskhan ex 80/300**
    bench   Meganium 4, Ogerpon ex 4,              **no energy: it cannot attack**
            Fezandipiti ex 0, Ogerpon ex 4,
            Meowth ex 0                    bench   Crustle 150
    hand    Poke Pad, **Night Stretcher**, Ogerpon ex, Xerosic's Machinations
    discard **six Basic Grass Energy**     turn's attachment: **UNSPENT**

Wood Hammer costs four units and does 220 flat. Meganium's Wild Growth is in
play, so ONE basic Grass card is worth two: the Tapu Bulu sits at 2 of 4, and a
single Grass out of that discard both pays for the attack and knocks out a Mega
ex at 80 HP -- **three prizes**, taking us from four to one, off an opponent
whose only other body is a Crustle.

The agent played Xerosic's Machinations and then ENDED THE TURN with the Night
Stretcher still in hand. `utils/turn_explorer.py` rediscovers the line on that
board unaided: `NS->PLANTA -> ATTACH->Tapu Bulu -> ... -> ATTACK`, worth
`(0 wins, 3 prizes, 80 damage)` against the agent's zero.

THE CAUSE. `_score_night_stretcher_play` REPLACES its scenario list against a
wall archetype:

    if ctx.op_is_crustle_deck or ctx.op_is_cornerstone_deck:
        best, _ = _resolve_max(_ESC_NS_CRUSTLE, w)     # the whole ballot
    else:
        best, _ = _resolve_max(_ESC_NS_RECUPERACION, w)

Every scenario that prices a recovered energy by *does it take a prize today*
lives in the list that gets replaced -- and on top of that, the three lethal
ones each carried `not op_is_crustle_deck and not op_is_cornerstone_deck` of
their own. So against a Crustle list the card could not be played for a lethal
energy at all. Not rarely: never, and regardless of who was actually standing
in the active spot. Here the Crustle was on their BENCH.

THE ASYMMETRY IS THE PROOF. The FETCH half of this same card already scores
that Grass at 1400, its top band -- `_RULES_NS_GRASS.grass_makes_the_active_ko`,
written for `registro_008` step 85 against this very same Mega Kangaskhan ex,
and written with **no archetype guard**, because
`tests/test_night_stretcher_takes_the_energy_that_kos.py` argues at length that
none is needed. The two halves of Night Stretcher were reading one board and
disagreeing about it, and the half that said no is the half that runs first.

THE FIX, and why it is deck-agnostic. A wall is a BODY in the active spot, not
a deck list, and the damage model already answers that exact question for the
body actually standing there: `_our_effective_damage` applies the
Crustle/Cornerstone immunity, Neutralization Zone, weakness and resistance, so
`_grass_on_active_enables_ko` comes back False on its own when the target is out
of reach. The four scenarios whose predicate ends in that proof are collected
into `_ESC_NS_REMATE_HOY` and resolved ALONGSIDE whichever list the archetype
picks. The whitelist keeps its veto over which BODY comes back -- that judgement
is untouched; what it no longer does is swallow the prize on the table.

The controls below are what separate the two claims. With the wall itself in
front (our ex against a Crustle active) the recovery goes back to being vetoed,
and with the target 30 HP out of reach it does too -- on the same board, through
the same code path.
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
from tests.state_builder import Scenario, pk

_FIXTURES = ROOT / "tests" / "fixtures"
_STEP123 = _FIXTURES / "crustle_kangaskhan_the_prize_the_wall_does_not_own_step123.json"
_STEP125 = _FIXTURES / "crustle_kangaskhan_the_prize_the_wall_does_not_own_step125.json"

SEAT = 0                       # our seat in the record

GRASS = m.Basic_Grass_Energy
TAPU = m.Tapu_Bulu
OGERPON = m.Teal_Mask_Ogerpon_ex
MEOWTH = m.Meowth_ex
MEGANIUM = m.Meganium
NIGHT_STRETCHER = m.Night_Stretcher
POKE_PAD = m.Poke_Pad
XEROSIC = m.Xerosic_Machinations

MEGA_KANGASKHAN = 756          # 300 HP, 3 prizes
CRUSTLE = m.Crustle_Grass      # 150 HP, the wall
WOOD_HAMMER = 1326             # 220 flat, and 30 to itself


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _obs(path):
    with open(path, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _hand_play(obs, card_id):
    """The menu index that PLAYS `card_id` from hand, or None."""
    hand = obs["current"]["players"][SEAT]["hand"]
    for i, opt in enumerate(obs["select"]["option"]):
        if opt.get("type") == int(m.OptionType.PLAY) and hand[opt["index"]]["id"] == card_id:
            return i
    return None


def _end(obs):
    for i, opt in enumerate(obs["select"]["option"]):
        if opt.get("type") == int(m.OptionType.END):
            return i
    return None


# ----------------------------------------------------------------------
# 1. The board is the one the record lost on
# ----------------------------------------------------------------------

def test_the_fixture_is_a_mega_ex_at_eighty_with_the_wall_on_the_bench():
    obs = _obs(_STEP123)
    cur = obs["current"]
    mine, op = cur["players"][SEAT], cur["players"][1 - SEAT]

    assert mine["active"][0]["id"] == TAPU
    assert len(mine["active"][0]["energies"]) == 2, "two of Wood Hammer's four"
    assert cur["energyAttached"] is False, "the turn's attachment is unspent"
    assert not any(c["id"] == GRASS for c in mine["hand"]), (
        "no Grass in hand: the discard is the only source")
    assert sum(1 for c in mine["discard"] if c["id"] == GRASS) == 6

    assert op["active"][0]["id"] == MEGA_KANGASKHAN
    assert op["active"][0]["hp"] == 80
    assert op["active"][0]["energies"] == [], "it cannot even answer"
    assert [b["id"] for b in op["bench"]] == [CRUSTLE], (
        "the wall is on their BENCH, not in the way")

    assert _hand_play(obs, NIGHT_STRETCHER) is not None, (
        "the card IS on the menu; the point is that it was never played")


def test_the_matchup_flag_that_used_to_veto_it_is_really_on():
    """Without this the test below measures a board, not the guard."""
    m.agent(_obs(_STEP123))
    assert m.AGENT_STATE.op_is_crustle_deck is True
    assert m.AGENT_STATE.meganium_in_play is True, "Wild Growth doubles the Grass"


# ----------------------------------------------------------------------
# 2. The arithmetic: one card in the discard is three prizes
# ----------------------------------------------------------------------

def test_one_grass_pays_wood_hammer_and_wood_hammer_kills_it():
    from ptcg.calc.energy import _grass_attach_unit
    from ptcg.cards.tables import attack_table

    m.agent(_obs(_STEP123))                      # so Wild Growth is read off the board
    assert _grass_attach_unit() == 2, "one Grass card = two units under Meganium"
    assert m.AGENT_STATE.ATTACK_ENERGY_REQ[TAPU] == 4
    assert 2 + 2 >= 4, "two on the Tapu plus the recovered one pays the cost"
    assert attack_table[WOOD_HAMMER].damage == 220 >= 80


def test_the_knockout_is_worth_three_prizes_of_the_four_we_had_left():
    from ptcg.calc.card import prize_count_op

    obs = _obs(_STEP123)
    cur = obs["current"]

    class _Body:
        def __init__(self, raw):
            self.__dict__.update(raw)
    assert prize_count_op(_Body(cur["players"][1 - SEAT]["active"][0])) == 3
    assert len(cur["players"][SEAT]["prize"]) == 4, "4 -> 1 in one attack"


# ----------------------------------------------------------------------
# 3. The decision, on both menus of that turn
# ----------------------------------------------------------------------

def test_step123_plays_the_night_stretcher():
    obs = _obs(_STEP123)
    assert m.agent(obs) == [_hand_play(obs, NIGHT_STRETCHER)], (
        "the recorded game played Xerosic's Machinations here")


def test_step125_does_not_end_the_turn_with_the_prize_in_hand():
    """The second menu of the same turn, after the Supporter was spent: the
    Night Stretcher and the Poke Pad are all that is left, and the agent ENDED.
    """
    obs = _obs(_STEP125)
    stretcher, end = _hand_play(obs, NIGHT_STRETCHER), _end(obs)
    assert stretcher is not None and end is not None
    assert m.agent(obs) != [end], "this is the END that lost the game"
    assert m.agent(_obs(_STEP125)) == [stretcher]


# ----------------------------------------------------------------------
# 4. The controls: it is the KNOCKOUT that moves it, not the matchup
# ----------------------------------------------------------------------

def _wall_deck_board(active, op_active, discard=(GRASS, GRASS)):
    """A Crustle list (the wall on their bench) with a Night Stretcher in hand,
    no Grass in hand and the turn's attachment unspent.

    The bench is Meowth ex and Fezandipiti ex on purpose: neither is in
    `_ns_e_charge_bench_crustle`'s list, so the only Crustle-whitelist scenario
    that could keep the card alive stays quiet and what is measured is the
    lethal one. The discard holds Grass and nothing else, so
    `basico_whitelist` has nothing to offer either. And the hand holds the
    Night Stretcher ALONE, so the menu is the card against END and no ordering
    question can stand in for the veto.
    """
    return (Scenario(turn=17, step=123, tac=1, first_player=0, own_prizes=4)
            .my_active(active)
            .my_bench(pk(MEOWTH), pk(m.Fezandipiti_ex))
            .my_hand(NIGHT_STRETCHER)
            .my_discard(*discard)
            .op_active(op_active)
            .op_bench(pk(CRUSTLE, hp=150, max_hp=150))
            .op_zones(hand=4, deck=25, prizes=3)
            .menu_hand()
            .build())


def _plays_the_stretcher(obs):
    return m.agent(obs) == [_hand_play(obs, NIGHT_STRETCHER)]


def test_against_a_crustle_list_the_lethal_energy_is_recovered():
    """The finding, rebuilt from scratch: a wall deck, the wall on the bench,
    and a reachable Mega ex in front. No Meganium here -- one Grass is one
    unit -- so the line does not lean on the doubler either."""
    req = m.AGENT_STATE.ATTACK_ENERGY_REQ[TAPU]
    obs = _wall_deck_board(
        active=pk(TAPU, energies=req - 1),
        op_active=pk(MEGA_KANGASKHAN, hp=200, max_hp=300))
    assert _plays_the_stretcher(obs)


def test_but_not_when_the_target_is_out_of_reach():
    """The same board with 250 HP in front: 220 does not knock out, the energy
    stops being a prize today and the Crustle whitelist's veto stands."""
    req = m.AGENT_STATE.ATTACK_ENERGY_REQ[TAPU]
    obs = _wall_deck_board(
        active=pk(TAPU, energies=req - 1),
        op_active=pk(MEGA_KANGASKHAN, hp=250, max_hp=300))
    assert not _plays_the_stretcher(obs)


def test_and_not_when_the_wall_itself_is_the_body_in_front():
    """The case the removed guard was standing in for, done properly: our ex
    against an ACTIVE Crustle. `_our_effective_damage` returns 0 through the
    immunity, so the recovery is vetoed by the damage model rather than by the
    deck list -- which is the whole point of the change."""
    req = m.AGENT_STATE.ATTACK_ENERGY_REQ[OGERPON]
    obs = _wall_deck_board(
        active=pk(OGERPON, energies=req - 1),
        op_active=pk(CRUSTLE, hp=60, max_hp=150))
    assert not _plays_the_stretcher(obs)


# ----------------------------------------------------------------------
# 5. The rest of the chain: the recovered Grass is not left dead in hand
# ----------------------------------------------------------------------

def _board_after_the_recovery(active_energy, hand, menu):
    """The board of step 123 with the Grass already recovered: Tapu Bulu in
    front of the 80 HP Mega Kangaskhan ex, Meganium on the bench doubling."""
    esc = (Scenario(turn=17, step=124, tac=2, first_player=0, own_prizes=4)
           .my_active(pk(TAPU, energies=active_energy, fisicas=active_energy // 2))
           .my_bench(pk(MEGANIUM, energies=4, fisicas=2), pk(MEOWTH))
           .my_hand(*hand)
           .my_discard(GRASS, GRASS, GRASS)
           .op_active(pk(MEGA_KANGASKHAN, hp=80, max_hp=300))
           .op_bench(pk(CRUSTLE, hp=150, max_hp=150))
           .op_zones(hand=4, deck=25, prizes=3))
    return menu(esc).build()


def test_the_recovered_grass_goes_onto_the_attacker():
    obs = _board_after_the_recovery(active_energy=2, hand=(GRASS,),
                                    menu=lambda e: e.menu_hand(with_attachment=True))
    opt = obs["select"]["option"][m.agent(obs)[0]]
    assert opt.get("type") == int(m.OptionType.ATTACH), f"expected an attach, got {opt}"
    assert opt.get("inPlayArea") == int(m.AreaType.ACTIVE), (
        f"the Grass went to the bench with the knockout in front: {opt}")


def test_and_once_it_is_paid_for_the_turn_ends_attacking():
    obs = _board_after_the_recovery(active_energy=4, hand=(),
                                    menu=lambda e: e.menu_hand(with_attack=True,
                                                               with_retreat=True))
    opt = obs["select"]["option"][m.agent(obs)[0]]
    assert opt.get("type") == int(m.OptionType.ATTACK), (
        f"with the finisher paid for it chose {opt}")
    assert opt.get("attackId") == WOOD_HAMMER
