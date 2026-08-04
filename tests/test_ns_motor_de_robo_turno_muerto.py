"""On a DEAD turn, the recovery brings the DRAW engine, not development.

Scenario (user, episode 88704504, registro_008 steps 66-67, turn 8 vs
Alakazam, LOST):

    US                                          RIVAL
    active  Teal Mask Ogerpon ex 210/210 0 {G}  active  Alakazam 140/140 1 {G}
    bench   Dipplin 80  0 {G}                   bench   Fezandipiti ex 210,
            Bayleef 110 0 {G}                           Alakazam 140, Kadabra 80
    hand    Night Stretcher            <- ONE card
    discard  Meowth ex (just knocked out), Meganium, 3 basic Grass...

The Night Stretcher was played and the **Meganium** was recovered. None of that could be
played: the Bayleef was at 0 energies, so the Meganium attacked neither that
turn nor the next, and the turn ended with **0 cards in hand** and without any
body able to attack. The rival knocked out the active on their turn.

The card to recover was the **Meowth ex** they had just knocked out:
playing it fires Last-Ditch Catch -> it searches the deck for a Supporter
(Lillie's Determination) -> it is played -> the whole hand is remade. A dead turn
in attack terms is not fixed with development; it is fixed with cards.

Why it failed: the `ns->meganium` table gave 990 (`bayleef_evolucionable`, which
only looks at whether there is an unevolved Bayleef in play) and `ns->meowth`'s
gave 800 at most (`fetch_supporter_del_mazo`, capped at `min(700, the value of the best
Supporter in the deck)`). Development ALWAYS won.

Fix (deck-agnostic): `_sin_ataque_hoy` measures with `ATTACK_ENERGY_REQ` whether
some body gets to attack today -- the active as it stands, a bench attacker
the active can bring up by paying its retreat, or either of the two with ONE
energy more if a charging route is still open. If nobody gets there and the hand runs dry
(<= 2 cards), the rule `motor_de_robo_turno_muerto` puts Meowth ex at 1250
and Fezandipiti ex at 1200, above all the development (990 + 200 from the
last-copy bonus = 1190) and below the energy that produces an attack
TODAY (1300/1400), which never coexists with a dead turn.

The order between the two engines: first Meowth ex (it remakes the WHOLE hand via
Lillie's), then Fezandipiti ex, and the latter ONLY if one of our Pokemon was knocked out
on the previous turn -- with no KO there is no Flip the Script and a 2-prize
body is a gift.
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

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "alakazam_ns_motor_de_robo_turno_muerto_step67.json")

MEOWTH = m.Meowth_ex
MEGANIUM = m.Meganium
NIGHT_STRETCHER = m.Night_Stretcher


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
    m._field_at_turn_start = {}
    m._poke_pad_target_id = 0
    m._ub_meowth_pending = False
    m._ub_fez_pending = False
    m._ub_engine_pivot_turn = False
    m._ld_supp_comprometido = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cards_tracking()


def _observaciones():
    with open(_FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observaciones"])


def _carta_del_descarte(obs, eleccion):
    """Returns the id of the DISCARD card the agent picks."""
    o = obs["select"]["option"][eleccion[0]]
    assert o["type"] == int(m.OptionType.CARD), o
    yo = obs["current"]["yourIndex"]
    return obs["current"]["players"][yo]["discard"][o["index"]]["id"]


def _reproducir(obs_list):
    """Replays the turn IN ORDER; returns the choice of the last menu."""
    eleccion = None
    for o in obs_list:
        eleccion = m.agent(o)
    return eleccion


# ---------------------------------------------------------------------------
# 1. The real turn
# ---------------------------------------------------------------------------

def test_paso67_la_night_stretcher_recupera_el_meowth_no_el_meganium():
    obs_list = _observaciones()
    eleccion = _reproducir(obs_list)
    assert _carta_del_descarte(obs_list[-1], eleccion) == MEOWTH


def test_el_menu_ofrecia_de_verdad_las_dos_cartas():
    """Without Meowth ex AND Meganium in the discard the test discriminates nothing."""
    obs = _observaciones()[-1]
    yo = obs["current"]["yourIndex"]
    descarte = obs["current"]["players"][yo]["discard"]
    ofrecidas = {descarte[o["index"]]["id"]
                 for o in obs["select"]["option"]
                 if o["type"] == int(m.OptionType.CARD)}
    assert MEOWTH in ofrecidas, ofrecidas
    assert MEGANIUM in ofrecidas, ofrecidas


def test_el_paso66_si_juega_la_night_stretcher():
    """The chain starts by playing the card: if step 66 ended the turn,
    step 67 would never exist."""
    obs = _observaciones()[0]
    o = obs["select"]["option"][m.agent(obs)[0]]
    assert o["type"] == int(m.OptionType.PLAY), o
    yo = obs["current"]["yourIndex"]
    assert obs["current"]["players"][yo]["hand"][o["index"]]["id"] == NIGHT_STRETCHER


# ---------------------------------------------------------------------------
# 2. The dead-turn detector, in isolation
# ---------------------------------------------------------------------------

def test_el_turno_esta_muerto_en_ataque():
    """Ogerpon ex asks for 3 effective energy and has 0; Teal Dance only puts 1.
    Dipplin (1) and Bayleef (2) are at 0 and the active does not pay its retreat."""
    obs_list = _observaciones()
    m.agent(obs_list[0])                      # it warms up the turn state
    obs = m.to_observation_class(obs_list[-1])
    yo = obs.current.yourIndex
    my_state = obs.current.players[yo]
    field = {}
    for p in list(my_state.active or []) + list(my_state.bench or []):
        if p is not None:
            field[p.id] = field.get(p.id, 0) + 1
    assert m._sin_ataque_hoy(my_state, obs.current, field) is True


def test_una_energia_en_el_bayleef_resucita_el_turno():
    """The detector is not "there is no attacker": it is "nobody gets there TODAY". With the
    Bayleef at 1 effective energy, ONE more Grass puts it at 2 = its cost, so
    the turn is NO longer dead (even if it still cannot be brought up)."""
    obs_list = _observaciones()
    m.agent(obs_list[0])
    obs = m.to_observation_class(obs_list[-1])
    yo = obs.current.yourIndex
    my_state = obs.current.players[yo]
    field = {}
    for p in list(my_state.active or []) + list(my_state.bench or []):
        if p is not None:
            field[p.id] = field.get(p.id, 0) + 1
    # The active pays its retreat (so it can BRING UP the bench one) and the Bayleef
    # is left one energy away from attacking.
    activo = my_state.active[0]
    activo.energies = [5] * m.RETREAT_COST.get(activo.id, 1)
    for b in my_state.bench:
        if b is not None and b.id == m.Bayleef:
            b.energies = [5]
    assert m._sin_ataque_hoy(my_state, obs.current, field) is False


# ---------------------------------------------------------------------------
# 3. What is NOT broken
# ---------------------------------------------------------------------------

def test_con_lillie_ya_en_la_mano_el_motor_no_dispara():
    """Meowth ex is worth the Supporter it searches for. If the Supporter is ALREADY in
    hand there is nothing to search for and the recovery goes back to development."""
    obs_list = _observaciones()
    m.agent(obs_list[0])
    fetch = obs_list[-1]
    yo = fetch["current"]["yourIndex"]
    fetch["current"]["players"][yo]["hand"] = [
        {"id": m.Lillie_Determination, "playerIndex": yo, "serial": 25}]
    fetch["current"]["players"][yo]["handCount"] = 1
    assert _carta_del_descarte(fetch, m.agent(fetch)) == MEGANIUM


def test_con_el_supporter_del_turno_ya_jugado_el_motor_no_dispara():
    """With no Supporter slot, the Last-Ditch brings an unplayable card: the
    engine produces nothing and development recovers the priority."""
    obs_list = _observaciones()
    m.agent(obs_list[0])
    fetch = obs_list[-1]
    fetch["current"]["supporterPlayed"] = True
    assert _carta_del_descarte(fetch, m.agent(fetch)) == MEGANIUM


def test_con_la_banca_llena_el_motor_no_dispara():
    """The recovered Meowth ex has to be PLAYABLE this turn."""
    obs_list = _observaciones()
    m.agent(obs_list[0])
    fetch = obs_list[-1]
    yo = fetch["current"]["yourIndex"]
    banca = fetch["current"]["players"][yo]["bench"]
    relleno = copy.deepcopy(banca[0])
    while len(banca) < 5:
        banca.append(copy.deepcopy(relleno))
    assert _carta_del_descarte(fetch, m.agent(fetch)) == MEGANIUM
