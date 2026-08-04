"""Lana's Aid: what is picked up from the discard is decided by THE BOARD, not by the
shape of the evolution lines.

Scenario (user, episode 88776459 registro_018 step 118 vs Crustle, LOST):

    US                                      OPPONENT
    active  Tapu Bulu   140/140  2e         active  Crustle  270/290
    bench   Meganium    160/160  2e         (a bench full of charged bodies)
            Meowth ex    50/170  2e
            Meganium    160/160  0e
            Ogerpon ex   90/210  2e
            Ogerpon ex  210/210  0e   <- bench FULL (5/5)
    hand    Hydrapple ex
    discard   4x Basic Grass, 2x Applin, 1x Dipplin (+ items)
    the turn's energy UNPLAYED

The agent played **Lana's Aid** -- the right card, as the user confirms -- and
picked up **2 Applin + 1 Dipplin**. With the bench FULL a Basic does not fit in
any way, and the Dipplin has no Applin in play to
evolve on top of: three DEAD cards. The turn died without attacking.

What the board was asking for was **energy**:

- with two Meganium in play (*Wild Growth*) ONE physical Grass is worth {G}{G}, so
  `_grass_attach_unit()` = 2;
- the ACTIVE Tapu Bulu has 2 effective and Wood Hammer asks for 4
  (`ATTACK_ENERGY_REQ`): **a single Grass puts it in attack range THIS turn**, and the
  manual attachment was still unspent;
- the other two Grass charge the Meganium for the next turn (the two
  Ogerpon ex in play also leave two *Teal Dance* alive).

Root cause: Lana's Aid had no branch of its own in the `TO_HAND` context and fell to
the generic recovery scorer, which only knows how to read evolution-line SHAPES
("am I missing this link?") and looks at neither the energy nor the bench slot. Its
numbers -- Applin 260 > Dipplin 250 > Grass 240 -- decided the menu.

The fix, in two pieces that share the SAME board reading:

 1. `_plan_de_planta`: it walks the `MAIN_ATTACKERS` in play, measures their deficit
    in Grass CARDS (`ceil((req - effective) / unit)`) and counts the turn's real
    attachment routes (manual + `_grass_ability_slots`: Teal Dance only
    charges its bearer, Ripening Charge anyone). It returns `demanda` and
    `desbloquea_hoy`/`cartas_para_atacar`.
 2. The `Lanas_Aid` branch of the `TO_HAND` context, in three bands
    (`LANA_SEL_PLANTA_DESBLOQUEA` > `LANA_SEL_PLANTA_DEMANDA` > development >
    `LANA_SEL_PLANTA_SOBRANTE`/`LANA_SEL_INJUGABLE`), with the ordinal
    `_lana_orden_planta` so that only the FIRST `demanda` Grass get the
    high band -- otherwise, four tied copies would take all 3 choices
    even if the board could only use one.

Along the way, `_lana_energy_enables_attack` (the PLAY layer, which decides whether Lana's Aid
deserves the 950 points against Lillie's) switches to the same
`_plan_de_planta`: before it only knew how to look at Hydrapple ex and that is why it stayed silent with
a Tapu Bulu one Grass away from firing.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import G, Escenario, pk

GRASS = m.Basic_Grass_Energy
TAPU = m.Tapu_Bulu                 # Wood Hammer: 4 effective energies
MEGANIUM = m.Meganium              # Wild Growth: each physical Grass is worth {G}{G}
OGERPON = m.Teal_Mask_Ogerpon_ex
MEOWTH = m.Meowth_ex
HYDRAPPLE = m.Hydrapple_ex
APPLIN = m.Applin
DIPPLIN = m.Dipplin
CHIKORITA = m.Chikorita
LANA = m.Lanas_Aid
CRUSTLE = m.Crustle_Grass
DWEBBLE = m.Dwebble_Grass

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "crustle_lana_levanta_energia_no_basicos_step118.json")


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
    m._grass_attaches_this_turn = 0
    yield
    m._init_cards_tracking()


def _cartas_elegidas(obs, eleccion):
    """The discard ids the selection returns, in order of preference."""
    descarte = obs["current"]["players"][obs["current"]["yourIndex"]]["discard"]
    return [descarte[obs["select"]["option"][i]["index"]]["id"] for i in eleccion]


# ---------------------------------------------------------------------------
# The real step 118
# ---------------------------------------------------------------------------

def test_paso118_levanta_las_tres_energias():
    with open(_FIXTURE, encoding="utf-8") as f:
        fixture = json.load(f)
    obs = fixture["observation"]

    # The real menu offered 4 Grass, 2 Applin and 1 Dipplin.
    ofrecidas = _cartas_elegidas(obs, range(len(obs["select"]["option"])))
    assert sorted(ofrecidas) == sorted([GRASS] * 4 + [APPLIN] * 2 + [DIPPLIN])
    assert obs["select"]["maxCount"] == 3

    # What was played in the game (and lost the turn).
    assert _cartas_elegidas(obs, fixture["recorded_action"]) == [APPLIN, APPLIN,
                                                                 DIPPLIN]

    assert _cartas_elegidas(obs, m.agent(obs)) == [GRASS, GRASS, GRASS]


def test_paso118_una_planta_pone_a_atacar_al_tapu_bulu():
    """The core of the board reading: with Meganium in play the Tapu Bulu is
    ONE Grass card away from being able to attack, and the turn's attachment is still free."""
    with open(_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    m.agent(obs)  # it sets the turn's globals (meganium_in_play, ...)

    o = m.to_observation_class(obs)
    mi = o.current.players[o.current.yourIndex]
    campo = {}
    for p in mi.active + mi.bench:
        if p is not None:
            campo[p.id] = campo.get(p.id, 0) + 1
    mano = {}
    for c in (mi.hand or []):
        mano[c.id] = mano.get(c.id, 0) + 1

    assert m.meganium_in_play and m._grass_attach_unit() == 2
    tapu = mi.active[0]
    assert tapu.id == TAPU
    assert len(tapu.energies) == 2 and m.ATTACK_ENERGY_REQ[TAPU] == 4

    plan = m._grass_plan(mi, o.current, campo, mano)
    assert plan.unlocks_today
    assert plan.cards_to_attack == 1
    assert plan.demanda == 3          # the Meganium/Ogerpon ask for the rest


def test_paso118_applin_y_dipplin_son_cartas_muertas():
    """Bench 5/5 and no Applin in play: neither does the Basic fit nor does the Stage 1
    evolve anything."""
    with open(_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    o = m.to_observation_class(obs)
    mi = o.current.players[o.current.yourIndex]
    campo = {}
    for p in mi.active + mi.bench:
        if p is not None:
            campo[p.id] = campo.get(p.id, 0) + 1
    banca = len([p for p in mi.bench if p is not None])

    assert banca == mi.benchMax
    assert m._pokemon_injugable(APPLIN, campo, banca, mi.benchMax)
    assert m._pokemon_injugable(DIPPLIN, campo, banca, mi.benchMax)
    assert not m._pokemon_injugable(GRASS, campo, banca, mi.benchMax)


# ---------------------------------------------------------------------------
# `_plan_de_planta`: the board reading, in isolation
# ---------------------------------------------------------------------------

def _plan(active, banca=(), mano=(), energia_jugada=False, cambio=False):
    obs = (Escenario(turn=10, energia_jugada=energia_jugada)
           .mi_activo(active)
           .mi_banca(*banca)
           .mi_mano(*mano)
           .op_activo(pk(CRUSTLE))
           .op_zonas(mano=5, mazo=30, prizes=6)
           .menu_mano()
           .construir())
    o = m.to_observation_class(obs)
    mi = o.current.players[o.current.yourIndex]
    campo = {}
    for p in mi.active + mi.bench:
        if p is not None:
            campo[p.id] = campo.get(p.id, 0) + 1
    m.meganium_in_play = campo.get(MEGANIUM, 0) >= 1
    m._grass_attaches_this_turn = 0
    cuentas = {}
    for c in (mi.hand or []):
        cuentas[c.id] = cuentas.get(c.id, 0) + 1
    return m._grass_plan(mi, o.current, campo, cuentas,
                             can_switch=cambio)


def test_plan_todos_cargados_no_hay_demanda():
    """With no deficit there is no demand: energy stops being worth anything even if
    there are attachments left free."""
    plan = _plan(pk(TAPU, energias=[G] * 4, fisicas=4),
                 banca=[pk(OGERPON, energias=[G] * 3, fisicas=3)])
    assert plan.demanda == 0
    assert not plan.unlocks_today


def test_plan_sin_adjunte_libre_no_desbloquea_pero_sigue_habiendo_demanda():
    """With the manual attachment spent and no charging abilities, the Grass does not reach
    the field TODAY -- but it goes to hand and the attacker goes on asking for it."""
    plan = _plan(pk(TAPU, energias=[G] * 2, fisicas=2), energia_jugada=True)
    assert not plan.unlocks_today
    assert plan.demanda >= 1


def test_plan_la_planta_de_la_mano_ya_desbloquea():
    """With the Grass already in hand, recovering another unlocks nothing: the
    detector cannot charge twice for the same attack."""
    plan = _plan(pk(TAPU, energias=[G] * 2, fisicas=2), mano=[GRASS])
    assert not plan.unlocks_today


def test_plan_atacante_de_banca_solo_desbloquea_si_podemos_cambiar():
    banca = [pk(MEGANIUM, energias=[G] * 2, fisicas=1)]
    active = pk(MEOWTH)               # Meowth ex is not a MAIN_ATTACKER
    assert not _plan(active, banca=banca).unlocks_today
    assert _plan(active, banca=banca, cambio=True).unlocks_today


def test_plan_con_las_habilidades_apagadas_solo_queda_el_adjunte_manual():
    """Under Watchtower / Iron Thorns (`meowth_ability_lock`) there is no Teal Dance
    or Ripening Charge: treating those routes as alive invents unlocks that do not
    exist (measured: -3.9 points of winrate vs the Iron Thorns deck)."""
    active = pk(OGERPON, energias=[G], fisicas=1)      # 1 of 3 effective
    banca = [pk(OGERPON, energias=[G] * 2, fisicas=2)]

    obs = (Escenario(turn=10)
           .mi_activo(active).mi_banca(*banca)
           .op_activo(pk(CRUSTLE)).op_zonas(mano=5, mazo=30, prizes=6)
           .menu_mano().construir())
    o = m.to_observation_class(obs)
    mi = o.current.players[o.current.yourIndex]
    campo = {OGERPON: 2}
    m.meganium_in_play = False
    m._grass_attaches_this_turn = 0

    # With the abilities alive: the manual attachment + 2 Teal Dance -> 3 slots, and the
    # active (1 of 3) reaches 3 with 2 Grass.
    vivas = m._grass_plan(mi, o.current, campo, {})
    assert vivas.slots_today == 3 and vivas.unlocks_today

    # With the lock on, only the manual attachment is left: 1 Grass is not enough.
    apagadas = m._grass_plan(mi, o.current, campo, {},
                                 abilities_off=True)
    assert apagadas.slots_today == 1 and not apagadas.unlocks_today


def test_plan_los_no_atacantes_no_inventan_demanda():
    """Chikorita and Applin have a cost in `ATTACK_ENERGY_REQ` but are not in
    `MAIN_ATTACKERS`: with them on the bench the board asks for no energy."""
    plan = _plan(pk(TAPU, energias=[G] * 4, fisicas=4),
                 banca=[pk(CHIKORITA), pk(APPLIN)])
    assert plan.demanda == 0


# ---------------------------------------------------------------------------
# `_pokemon_injugable`: the dead-card floor
# ---------------------------------------------------------------------------

def test_injugable_con_hueco_en_banca_nada_esta_muerto():
    campo = {MEGANIUM: 1}
    assert not m._pokemon_injugable(APPLIN, campo, 3, 5)
    assert not m._pokemon_injugable(DIPPLIN, campo, 3, 5)


def test_injugable_banca_llena_la_evolucion_vive_si_su_preevo_esta_en_juego():
    """The Dipplin is still playable with a full bench if there is an Applin in
    play: it evolves on top of it, it takes no slot."""
    campo = {APPLIN: 1, MEGANIUM: 4}
    assert not m._pokemon_injugable(DIPPLIN, campo, 5, 5)
    assert m._pokemon_injugable(APPLIN, campo, 5, 5)


def test_injugable_no_aplica_a_lo_que_no_es_pokemon():
    assert not m._pokemon_injugable(GRASS, {}, 5, 5)
    assert not m._pokemon_injugable(LANA, {}, 5, 5)


# ---------------------------------------------------------------------------
# The selection, synthetically
# ---------------------------------------------------------------------------

def _seleccion_lana(active, banca, descarte, mano=(), energia_jugada=False):
    obs = (Escenario(turn=10, partidario_jugado=True,
                     energia_jugada=energia_jugada)
           .mi_activo(active)
           .mi_banca(*banca)
           .mi_mano(*mano)
           .mi_descarte(*descarte)
           .op_activo(pk(CRUSTLE))
           .op_banca(pk(DWEBBLE))
           .op_zonas(mano=5, mazo=30, prizes=6)
           .fetch_descarte(LANA, cuantas=3, solo=(GRASS, APPLIN, DIPPLIN,
                                                  CHIKORITA))
           .construir())
    return obs, _cartas_elegidas(obs, m.agent(obs))


def test_seleccion_banca_llena_la_energia_gana_al_desarrollo():
    """registro_018, synthetically."""
    _, elegidas = _seleccion_lana(
        active=pk(TAPU, energias=[G] * 2, fisicas=1),
        banca=[pk(MEGANIUM, energias=[G] * 2, fisicas=1), pk(MEOWTH),
               pk(MEGANIUM), pk(OGERPON, energias=[G] * 2, fisicas=1),
               pk(OGERPON)],
        descarte=[GRASS, GRASS, GRASS, APPLIN, APPLIN, DIPPLIN])
    assert elegidas == [GRASS, GRASS, GRASS]


def test_seleccion_sin_demanda_de_energia_vuelve_el_desarrollo():
    """Boundary: with the active ALREADY charged and room on the bench, the energy is surplus and
    the recovery goes back to being development (starting the Hydrapple line)."""
    _, elegidas = _seleccion_lana(
        active=pk(TAPU, energias=[G] * 4, fisicas=4),
        banca=[pk(MEOWTH)],
        descarte=[GRASS, GRASS, GRASS, APPLIN, DIPPLIN],
        energia_jugada=True)
    assert APPLIN in elegidas, elegidas


def test_seleccion_solo_la_planta_que_hace_falta_cobra_la_banda_alta():
    """With a demand of ONE Grass and room on the bench, the SECOND choice is already
    development: the ordinal stops four tied copies taking the whole
    menu (the surplus Grass falls to `LANA_SEL_PLANTA_SOBRANTE`, below
    the Applin that starts the Hydrapple line)."""
    obs, elegidas = _seleccion_lana(
        active=pk(TAPU, energias=[G] * 2, fisicas=1),
        banca=[pk(MEGANIUM, energias=[G] * 4, fisicas=2), pk(MEOWTH)],
        descarte=[GRASS, GRASS, GRASS, GRASS, APPLIN, CHIKORITA])
    assert elegidas[:2] == [GRASS, APPLIN], elegidas
