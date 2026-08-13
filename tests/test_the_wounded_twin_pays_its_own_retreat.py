"""The retreat is paid in CARDS, and the bill was being written in SYMBOLS.

Scenario (`records/registro_008_pasos_105_hasta_110.json`, step 105, turn 8,
LOST vs Team Rocket -- episode 92484395):

    US (4 prizes)                          RIVAL (3 prizes)
    active  Hydrapple ex **150/330**,      active  TR Spidops 130/130, 2 en.
            ONE Grass = 2 effective                (Rocket Rush: 30 x their
            Syrup Storm -> 510, lethal              Team Rocket's in play = 180)
    bench   Hydrapple ex **330/330**, 3 Grass   bench  TR Mewtwo ex 280, TR
            Teal Mask Ogerpon ex 210, 3 Grass         Articuno 120, TR Spidops
            Meowth ex 170, Tapu Bulu 140,             x2, TR Mimikyu 60
            Meganium 160  (Wild Growth: every Grass is worth {G}{G})
    hand    ONE Basic Grass, Boss's Orders, Ultra Ball, Lillie's, Xerosic...

Both Hydrapple ex take the same knockout -- Syrup Storm counts the Grass on the
whole field, not the attacker's -- and one of them is at 150 HP against a reply
that does 180. The line that was on the table: **Ripening Charge puts the Grass
on the ACTIVE**, which heals it 30 (150 -> 180) and takes it from 2 to 4
effective energy, enough to pay a retreat of 3; retreat, promote the healthy
twin, Boss's Orders onto the Mewtwo ex, Syrup Storm. Same prize, and what
stands in the active spot afterwards is 330 HP against 180.

The agent attached the Grass to a benched Tapu Bulu, gusted and attacked from
the wounded body. Rocket Rush knocked it out for two prizes.

WHY NOTHING SAW IT. `_hydra_fragile_pivot` -- the detector of exactly this line
-- matched the board on every clause and then failed its own completability
check: it asked for `RETREAT_COST[id] - physical_energy(...)` = 3 - 1 = **2**
Grass in hand and we had one. That subtraction has no unit: the cost is printed
in SYMBOLS and the payment is made in whole CARDS, and with Meganium's Wild
Growth on the field each Grass pays for two symbols. The retreat needed
`ceil(3/2) - 1` = **ONE**. Without Meganium the two arithmetics agree, which is
why the bug was invisible for as long as it was.

Fix, and it is deck-agnostic: `_retreat_cards_missing` (ptcg/calc/energy.py),
the counting mirror of `_retreat_payable`, is the only thing allowed to answer
"how much Grass does this retreat still need". `_hydra_fragile_pivot` and its
consumer in `ptcg/turn/energy.py` ask it. And the Grass travels by the FREE
route: Ripening Charge scores in the lethal band for this line, so the turn's
manual attachment is not spent on a job an ability was already doing -- and the
30 points it heals on the way are collected.

What does NOT change: the two rules just above it in `ptcg/turn/energy.py`
still count in symbols on purpose (the note there says why), and a healthy
active never steps aside for a twin -- the comparison stays STRICT.

Golden corpus: a single flip, this step's
(ATTACH->Tapu Bulu -> ABILITY Hydrapple ex).
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
from cg.api import SelectType
from ptcg.calc.energy import _retreat_cards_missing, _retreat_payable
from ptcg.state.agent_state import AGENT_STATE

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "team_rocket_the_wounded_twin_pays_its_retreat_step105.json")

HYDRAPPLE = m.Hydrapple_ex
TAPU = m.Tapu_Bulu
MEGANIUM = m.Meganium
GRASS = m.Basic_Grass_Energy
BOSS = m.Boss_Orders
SPIDOPS = 401          # Team Rocket's Spidops: Rocket Rush, 30 x their Rockets
MEWTWO = 431           # Team Rocket's Mewtwo ex: 280 HP, two prizes
SYRUP_STORM = 195


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
    m._poke_pad_target_id = 0
    m._ub_meowth_pending = False
    m._ub_fez_pending = False
    m._ld_supp_comprometido = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cards_tracking()


def _obs():
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])


def _mine(obs):
    return obs["current"]["players"][obs["current"]["yourIndex"]]


def _theirs(obs):
    return obs["current"]["players"][1 - obs["current"]["yourIndex"]]


def _ability_on_the_active(obs):
    """Index of the Ripening Charge of the ACTIVE Hydrapple ex."""
    return next(i for i, o in enumerate(obs["select"]["option"])
                if o.get("type") == int(m.OptionType.ABILITY)
                and o.get("area") == int(m.AreaType.ACTIVE))


def _attach_to_bench(obs, slot):
    return next(i for i, o in enumerate(obs["select"]["option"])
                if o.get("type") == int(m.OptionType.ATTACH)
                and o.get("inPlayArea") == int(m.AreaType.BENCH)
                and o.get("inPlayIndex") == slot)


def _after_the_ripening_charge(obs):
    """The board one legal play later: the Grass has landed on the ACTIVE.

    Ripening Charge attaches a Basic Grass from hand to one of our Pokemon and
    heals 30 from it. That is the whole derivation -- the card leaves the hand,
    the active gains one physical Grass (two effective under Wild Growth) and 30
    HP -- and it is what turns a retreat of 3 symbols from unpayable into
    payable, so the simulator now offers RETREAT. The menu is rebuilt in the
    shape the engine gives on that board: the four cards of the hand it can
    actually play, the retreat, the attack and END.
    """
    obs = copy.deepcopy(obs)
    mine = _mine(obs)
    active = mine["active"][0]
    grass = next(c for c in mine["hand"] if c["id"] == GRASS)
    mine["hand"].remove(grass)
    mine["handCount"] = len(mine["hand"])
    active["energyCards"].append(grass)
    active["energies"] = active["energies"] + [int(m.EnergyType.GRASS)] * 2
    active["hp"] = min(active["maxHp"], active["hp"] + m.RIPENING_HEAL)
    playable = [i for i, c in enumerate(mine["hand"])
                if m.card_table[c["id"]].cardType != int(m.CardType.POKEMON)]
    obs["select"]["option"] = (
        [{"type": int(m.OptionType.PLAY), "index": i} for i in playable]
        + [{"type": int(m.OptionType.RETREAT)},
           {"type": int(m.OptionType.ATTACK), "attackId": SYRUP_STORM},
           {"type": int(m.OptionType.END)}]
    )
    return obs


def _after_the_gust(obs):
    """And one more: Boss's Orders has dragged their Mewtwo ex to the front."""
    obs = copy.deepcopy(obs)
    mine, theirs = _mine(obs), _theirs(obs)
    mewtwo = next(b for b in theirs["bench"] if b and b["id"] == MEWTWO)
    theirs["bench"].remove(mewtwo)
    theirs["bench"].append(theirs["active"][0])
    theirs["active"] = [mewtwo]
    mine["hand"] = [c for c in mine["hand"] if c["id"] != BOSS]
    mine["handCount"] = len(mine["hand"])
    obs["current"]["supporterPlayed"] = True
    obs["select"]["option"] = [
        o for o in obs["select"]["option"]
        if o.get("type") != int(m.OptionType.PLAY)]
    return obs


def _switch_menu(obs):
    """The promotion the retreat opens."""
    obs = copy.deepcopy(obs)
    obs["select"] = {
        "type": int(SelectType.CARD), "context": int(m.SelectContext.SWITCH),
        "minCount": 1, "maxCount": 1, "remainDamageCounter": 0,
        "remainEnergyCost": 0, "deck": None, "contextCard": None, "effect": None,
        "option": [{"type": int(m.OptionType.CARD), "area": int(m.AreaType.BENCH),
                    "index": k, "playerIndex": obs["current"]["yourIndex"]}
                   for k in range(len(_mine(obs)["bench"]))],
    }
    return obs


# ---------------------------------------------------------------------------
# 1. The scenario: without it, the test measures nothing
# ---------------------------------------------------------------------------

def test_the_fixture_is_the_wounded_twin_in_front():
    o = _obs()
    mine, theirs = _mine(o), _theirs(o)
    active = mine["active"][0]
    twin = next(b for b in mine["bench"] if b and b["id"] == HYDRAPPLE)

    # The same card twice: the one in front is spent, the one behind is not.
    assert active["id"] == twin["id"] == HYDRAPPLE
    assert active["maxHp"] == twin["maxHp"] == 330
    assert active["hp"] == 150 and twin["hp"] == 330

    # Wild Growth is on the field, which is what makes the arithmetic matter:
    # ONE physical Grass on the active reads as TWO effective.
    assert any(b and b["id"] == MEGANIUM for b in mine["bench"])
    assert len(active["energyCards"]) == 1 and len(active["energies"]) == 2

    # The retreat is 3 symbols and is NOT on the menu yet.
    assert m.RETREAT_COST[HYDRAPPLE] == 3
    assert all(op.get("type") != int(m.OptionType.RETREAT)
               for op in o["select"]["option"])

    # Exactly ONE Grass in hand -- the whole point of the bill being right.
    assert sum(1 for c in mine["hand"] if c["id"] == GRASS) == 1

    # Their Spidops answers for 180: more than the 150 the active has left,
    # less than the 330 the twin has.
    assert theirs["active"][0]["id"] == SPIDOPS
    rockets = 1 + sum(1 for b in theirs["bench"] if b)
    assert 30 * rockets == 180 > active["hp"]
    assert 30 * rockets < twin["hp"]


# ---------------------------------------------------------------------------
# 2. The arithmetic: cards against cards
# ---------------------------------------------------------------------------

def test_the_retreat_bill_is_counted_in_cards():
    o = _obs()
    m.agent(o)                     # one pass reads Meganium onto the board
    assert AGENT_STATE.meganium_in_play

    active = m.to_observation_class(_obs()).current.players[0].active[0]
    assert not _retreat_payable(active)
    # Two effective of the three symbols: ONE more Grass card covers the rest,
    # because Wild Growth makes it worth two. Counting in symbols asked for two.
    assert _retreat_cards_missing(active) == 1
    assert m.RETREAT_COST[HYDRAPPLE] - m._physical_energy(
        len(active.energies)) == 2


def test_a_body_that_can_already_pay_owes_nothing():
    o = _obs()
    m.agent(o)
    twin = next(b for b in m.to_observation_class(_obs()).current.players[0].bench
                if b is not None and b.id == HYDRAPPLE)
    assert _retreat_payable(twin) and _retreat_cards_missing(twin) == 0


# ---------------------------------------------------------------------------
# 3. The decision: the Grass goes to the wounded active, by the free route
# ---------------------------------------------------------------------------

def test_the_grass_goes_to_the_active_by_the_ripening_charge():
    o = _obs()
    assert m.agent(o) == [_ability_on_the_active(o)], (
        "el Hydrapple ex herido esta a UNA Grass de poder retirarse; la carga "
        "va a el, y por la ruta GRATIS: Ripening Charge ademas le cura 30")


def test_it_does_not_go_to_a_benched_tapu_bulu():
    """The move that was actually played, and the two prizes it cost."""
    o = _obs()
    tapu_slot = next(k for k, b in enumerate(_mine(o)["bench"])
                     if b and b["id"] == TAPU)
    assert m.agent(o) != [_attach_to_bench(o, tapu_slot)]


# ---------------------------------------------------------------------------
# 4. The rest of the line, one legal play at a time
# ---------------------------------------------------------------------------

def test_the_charge_makes_the_retreat_payable():
    after = _after_the_ripening_charge(_obs())
    active = _mine(after)["active"][0]
    assert len(active["energyCards"]) == 2 and len(active["energies"]) == 4
    assert active["hp"] == 180
    assert _retreat_payable(
        m.to_observation_class(after).current.players[0].active[0])


def test_with_their_mewtwo_in_front_the_wounded_body_steps_aside():
    after = _after_the_gust(_after_the_ripening_charge(_obs()))
    retreat = next(i for i, o in enumerate(after["select"]["option"])
                   if o.get("type") == int(m.OptionType.RETREAT))
    assert m.agent(after) == [retreat], (
        "los dos Hydrapple ex se llevan el mismo KO; el que se queda delante "
        "debe ser el de 330, no el de 180")


def test_the_promotion_brings_up_the_healthy_twin():
    after = _switch_menu(_after_the_gust(_after_the_ripening_charge(_obs())))
    bench = _mine(after)["bench"]
    healthy = next(k for k, b in enumerate(bench)
                   if b and b["id"] == HYDRAPPLE and b["hp"] == 330)
    assert m.agent(after) == [healthy]


# ---------------------------------------------------------------------------
# 5. The discriminator: it is the WOUND that moves the body, not the card
# ---------------------------------------------------------------------------

def test_a_healthy_active_keeps_the_front_and_the_grass():
    """Heal the active to full and the whole line switches off.

    Same cards, same hand, same opponent: what makes the pivot fire is the 180
    points of damage on the body in front, so with them gone the Grass has no
    business paying a retreat nobody needs.
    """
    o = _obs()
    _mine(o)["active"][0]["hp"] = 330
    assert m.agent(o) != [_ability_on_the_active(o)]


def test_a_bench_twin_that_is_no_healthier_does_not_call_the_pivot():
    """STRICT improvement: at equal life the swap only pays the retreat."""
    o = _obs()
    twin = next(b for b in _mine(o)["bench"] if b and b["id"] == HYDRAPPLE)
    twin["hp"] = _mine(o)["active"][0]["hp"]
    assert m.agent(o) != [_ability_on_the_active(o)]
