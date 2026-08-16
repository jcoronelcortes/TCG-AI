"""A wall that falls to the same hit is not a wall, it is a dearer corpse.

Scenario (`records/registro_011_pasos_112_hasta_127.json`, step 119, turn 11,
LOST vs Alakazam -- episode 93430769):

    US (4 prizes)                          THEM (2 prizes)
    active  Meganium **160/160**,          active  Alakazam **140/140**
            4 effective energies                   (Powerful Hand: 20 x hand,
            -> Solar Beam **140**                    19 cards in hand)
    bench   Teal Mask Ogerpon ex (4 en.)   bench   Fezandipiti ex, Kadabra x2
            Meowth ex x2, Bayleef
            **Hydrapple ex 330/330**, 2 en.

Solar Beam does 140 into a body with exactly 140 HP: the prize was already
ours, this turn, for free, taken by a body that hands over ONE prize when it
falls. The agent **retreated** it instead -- burning both Grass cards off the
Meganium to pay the cost -- and the promotion that followed put up a **Bayleef**
with no energy.

WHY. `_hydra_pivot_active` (main.py), the defensive pivot to Hydrapple ex. It
fires on two conditions: the active is doomed (`active_ko_likely` -- their
Powerful Hand with 19 cards in hand) and the benched Hydrapple ex knocks the
opposing active out from where it stands (30 + 30 x 8 Grass after the retreat =
270 >= 140). It then points `plan.attacker` at the bench, which SUPPRESSES the
attack of the active: at step 119 the attack scored **-1** against the retreat's
**6500**.

Its whole justification is the wall -- "its very high HP is very hard to knock
out" -- and it never asked whether the wall stands. That same Powerful Hand
projects 20 x (19 + 2) = **420** against 330 HP, so the trade was: give up a free
knockout, discard two Grass, and swap a one-prize corpse for a two-prize one.
The promotion chain read the projection correctly and picked the cheapest body
to lose, which is how a Bayleef ended up in front.

THE GUARD ALREADY EXISTED, twenty lines above, on the OTHER promotion of the
same Hydrapple ex (`_promote_hydra`, learned from `registro_011` step 138 vs
Dragapult, also lost): "the pivot is only allowed if it SURVIVES the projected
hit or if its own KO already wins the game". The twin never got it. That is the
whole fix, switch `THE_PIVOT_WALL_MUST_SURVIVE_THE_REPLY` (`ptcg/cards/ids.py`).

WHAT DOES NOT CHANGE, and both controls below pin it: with a reply the Hydrapple
ex survives, the pivot still fires -- that is the board it was written for -- and
so does the escape hatch, when the knockout it delivers ends the game and there
is no reply left to survive.

Golden corpus: a single flip, this step's (RETREAT -> ATTACK). Frozen corpus
(50 records, 3 580 decisions): zero.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

import main as m  # noqa: E402
import golden_corpus as gc  # noqa: E402
from state_builder import Scenario, pk, G  # noqa: E402

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "alakazam_no_retirar_el_meganium_que_ya_noquea_step119.json")

MEGANIUM = m.Meganium
HYDRAPPLE = m.Hydrapple_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
BAYLEEF = m.Bayleef
MEOWTH = m.Meowth_ex
ALAKAZAM = m.Alakazam_ex          # THEIR body: read only through its damage
KADABRA = m.Kadabra
SOLAR_BEAM = 1028


@pytest.fixture(autouse=True)
def reset_main_state():
    m.AGENT_STATE.reset()
    m._init_cards_tracking()
    yield
    m.AGENT_STATE.reset()
    m._init_cards_tracking()


def _obs():
    gc.reset_agent(m)
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])


def _index_of(obs, **campos):
    return next(i for i, o in enumerate(obs["select"]["option"])
                if all(o.get(k) == v for k, v in campos.items()))


def _pivot_fired(obs):
    """Did `_hydra_pivot_active` come up on this board?

    Read off the local as `agent()` returns, not re-derived here: the flag is
    what the retreat ladder branches on, and restating its conditions in the
    test would only pin the copy.
    """
    visto = {}

    def tracer(frame, event, arg):
        if event == "return" and frame.f_code.co_name == "agent":
            visto["pivot"] = frame.f_locals.get("_hydra_pivot_active")
            visto["ko_now"] = frame.f_locals.get("_plan_act_kos_now")
        return tracer

    _previous_tracer = sys.gettrace()
    sys.settrace(tracer)
    try:
        visto["choice"] = m.agent(obs)
    finally:
        sys.settrace(_previous_tracer)
    return visto


# ---------------------------------------------------------------------------
# 1. The recorded board: without this arithmetic the test measures nothing
# ---------------------------------------------------------------------------

def test_the_fixture_is_a_free_knockout_traded_for_a_dearer_corpse():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    riv = o["current"]["players"][1 - yo]

    active = mio["active"][0]
    hydra = next(b for b in mio["bench"] if b and b["id"] == HYDRAPPLE)

    # OURS: a Meganium at full HP with the four effective energies Solar Beam
    # costs, and a Hydrapple ex at full HP behind it.
    assert active["id"] == MEGANIUM and active["hp"] == active["maxHp"] == 160
    assert len(active["energies"]) == 4
    assert hydra["hp"] == hydra["maxHp"] == 330

    # THEIRS: an Alakazam of exactly the damage Solar Beam prints.
    assert riv["active"][0]["id"] == ALAKAZAM and riv["active"][0]["hp"] == 140
    assert m.attack_table[SOLAR_BEAM].damage == 140

    # THE PRIZES: the body that already takes it hands over ONE, the "wall"
    # that would replace it hands over TWO.
    cur = m.to_observation_class(o).current
    assert m.prize_count(cur.players[yo].active[0]) == 1
    assert m.prize_count(
        next(b for b in cur.players[yo].bench if b and b.id == HYDRAPPLE)) == 2

    # AND THE WALL DOES NOT STAND: Powerful Hand projects 20 x (hand + 2).
    assert riv["handCount"] == 19
    reply = m._op_active_attack_damage_to(
        cur.players[1 - yo].active[0],
        next(b for b in cur.players[yo].bench if b and b.id == HYDRAPPLE),
        riv["handCount"])
    assert reply >= 330, f"la respuesta proyectada era {reply}, no tumba el muro"


def test_the_meganium_that_already_knocks_out_attacks(monkeypatch):
    """The regression itself: the recorded retreat becomes the attack."""
    monkeypatch.setattr(m, "THE_PIVOT_WALL_MUST_SURVIVE_THE_REPLY", True)
    o = _obs()
    atacar = _index_of(o, attackId=SOLAR_BEAM)
    visto = _pivot_fired(o)
    assert visto["ko_now"] is True, "el activo ya noqueaba: el tablero cambio"
    assert visto["pivot"] is False, (
        "el pivote defensivo sigue apuntando a un Hydrapple ex que su Powerful "
        "Hand tumba igual")
    assert visto["choice"] == [atacar], (
        f"con el KO gratis delante, el turno es atacar; eligio {visto['choice']}")


def test_with_the_switch_off_the_recorded_retreat_comes_back(monkeypatch):
    """The control that proves WHICH change moved the board."""
    monkeypatch.setattr(m, "THE_PIVOT_WALL_MUST_SURVIVE_THE_REPLY", False)
    o = _obs()
    retirar = _index_of(o, type=int(m.OptionType.RETREAT))
    visto = _pivot_fired(o)
    assert visto["pivot"] is True
    assert visto["choice"] == [retirar], (
        f"con el interruptor abajo debe volver la retirada grabada; eligio "
        f"{visto['choice']}")


# ---------------------------------------------------------------------------
# 2. The two controls: the pivot the guard must NOT take away
# ---------------------------------------------------------------------------

def _board(op_hand, own_prizes=4, active_energies=4):
    """The same shape as the record, with their hand size as the dial.

    Powerful Hand is 20 x (hand + 2), so the hand count alone decides whether
    the Hydrapple ex we promote is a wall or a corpse -- and nothing else about
    the board moves with it.
    """
    gc.reset_agent(m)
    return (Scenario(turn=11, step=119, tac=8, own_prizes=own_prizes)
            .my_active(pk(MEGANIUM, energies=[G] * active_energies,
                          fisicas=active_energies // 2,
                          pre_evo=[m.Chikorita, BAYLEEF]))
            .my_bench(pk(OGERPON, energies=[G] * 4, fisicas=2),
                      pk(HYDRAPPLE, energies=[G] * 2, fisicas=1),
                      pk(BAYLEEF, pre_evo=[m.Chikorita]),
                      pk(MEOWTH))
            .my_hand(m.Basic_Grass_Energy, m.Ultra_Ball)
            .op_active(pk(ALAKAZAM, energies=5, fisicas=1,
                          pre_evo=[m.Abra, KADABRA]))
            .op_bench(pk(KADABRA, pre_evo=[m.Abra]))
            .op_zones(hand=op_hand, deck=9, prizes=2)
            .deck(m.Basic_Grass_Energy, m.Night_Stretcher, m.Lillie_Determination)
            .rest_to_discard()
            .menu_hand(with_retreat=True, with_attack=True)
            .build())


def test_the_pivot_still_fires_when_the_wall_actually_stands():
    """THE BOARD THE RULE WAS WRITTEN FOR, and the guard leaves it alone.

    Fourteen cards in their hand: 20 x (14 + 2) = 320, which kills a 160 HP
    Meganium and does NOT kill a 330 HP Hydrapple ex. The active is still
    doomed, the benched Hydrapple still knocks out, and the wall is a wall.
    """
    obs = _board(op_hand=14)
    cur = m.to_observation_class(obs).current
    yo = cur.yourIndex
    hydra = next(b for b in cur.players[yo].bench if b and b.id == HYDRAPPLE)
    reply = m._op_active_attack_damage_to(
        cur.players[1 - yo].active[0], hydra, 14)
    assert reply < 330 <= reply + 100, (
        f"el control no esta en el filo que dice: respuesta {reply}")

    assert _pivot_fired(obs)["pivot"] is True, (
        "con un muro que aguanta, el pivote defensivo sigue siendo la jugada")


def test_the_pivot_still_fires_when_its_knockout_ends_the_game():
    """THE ESCAPE HATCH, the same one `_promote_hydra` already carried.

    One prize left and their active worth exactly that: the knockout the
    promoted Hydrapple ex delivers wins outright, so there is no reply left for
    it to survive. Their hand is the record's, so the wall falls -- and the
    pivot fires anyway. The active cannot pay Solar Beam here (two effective
    energies of the four it costs), which is what leaves the bench as the only
    route to that prize.
    """
    obs = _board(op_hand=19, own_prizes=1, active_energies=2)
    assert _pivot_fired(obs)["pivot"] is True, (
        "el KO del Hydrapple gana la partida: no hay respuesta que sobrevivir")
