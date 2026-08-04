"""vs Dragapult: the Ultra Ball is spent TODAY because TOMORROW there will be no Items.

Scenario (`registros/registro_002_pasos_012_hasta_017.json`, step 17, turn 2
going second, LOST vs Dragapult -- episode 89079426):

    US (6 prizes)                              OPPONENT (6 prizes)
    active  Chikorita 70, 1 {G}                active  **Budew 30**
    bench   Fezandipiti ex 210, **0 {G}**      bench   Dreepy, Dreepy,
    hand    Grass x3, Boss's x2,                       Munkidori 1 {G}
            **Ultra Ball**, Meganium, Forest
    (Lillie's Determination ALREADY played this turn)

The agent **attacked with the Chikorita** and closed the turn with the Ultra Ball in
hand. That was the last turn it could be played: the Budew's *Itchy Pollen*
-- a ZERO-energy attack -- blocks Items during our next turn, and
against Dragapult the Budew does not leave the field. The only card capable of remaking
the game stayed there as decoration.

And the board did not allow waiting: the Fezandipiti ex needs 3 energies (one per
turn) and the Meganium in hand had no Bayleef underneath -> **tomorrow it does not attack
either** (`_sin_atacante_para_manana`).

Rule (user): against Dragapult (or with any Budew on the opposing field), with no
hand that starts the attack, the Ultra Ball is played to dig out **Meowth ex**. It
is not put down today -- the Supporter slot is already spent, so its *Last-Ditch Catch*
would produce nothing and the body would only GIVE AWAY two prizes on the opponent's turn --:
it goes down TOMORROW, when its ability brings a **Lillie's Determination**. Neither
Pokémon nor abilities nor Supporters are blocked by *Itchy Pollen*; Items are.

Cause: `_eval_ub_best_target` returned 0 and the Ultra Ball fell to `SCORE_CANCEL`
(-100), below the Chikorita's attack (1000). The two branches that could dig
out the Meowth ex require `not supporterPlayed` -- "the Ultra Ball is only played for
a Pokémon we are going to PLAY this turn", `_ub_cavar_meowth_se_juega` --, and
the sterile-turn rescue net, which DOES know about the Item block, does not switch on
because the turn was not sterile: there was a real attack.

Fix: `_ub_meowth_para_manana`, the only branch that buys for the next
turn, because it is the only one in which keeping the Ultra Ball amounts to throwing it away.
Its two new pieces are shared with whoever already decided the same thing:

  * `_bloqueo_de_items_inminente` -- a Budew on the opposing field or a Dragapult deck; the
    same predicate the sterile-turn net used inline;
  * `_sin_atacante_para_manana` -- one turn further than `_sin_ataque_hoy`:
    it counts next turn's attachment and the evolutions the hand completes.

The fetch has its own half (`bloqueo_de_items_manana` in `_REGLAS_UB_MEOWTH`,
above `last_ditch_no_produce`): without it the already paid-for search would have
brought back anything else.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import Escenario, pk, G

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "dragapult_ub_meowth_para_manana_step17.json")

CHIKORITA = m.Chikorita
BAYLEEF = m.Bayleef
MEGANIUM = m.Meganium
APPLIN = m.Applin
DIPPLIN = m.Dipplin
OGERPON = m.Teal_Mask_Ogerpon_ex
FEZ = m.Fezandipiti_ex
MEOWTH = m.Meowth_ex
LILLIE = m.Lillie_Determination
BOSS = m.Boss_Orders
ULTRA_BALL = m.Ultra_Ball
FOREST = m.Forest_of_Vitality
GRASS = m.Basic_Grass_Energy
BUDEW = m.Budew
DREEPY = m.Dreepy
MUNKIDORI = m.Munkidori

TURNO = 2


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cartas_tracking()
    m._cartas_first_scan_done = False
    m._cartas_prizes_identified = False
    m._cartas_last_turn = -1
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
    m._grass_attaches_this_turn = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cartas_tracking()


def _jugada(obs, eleccion):
    o = obs["select"]["option"][eleccion[0]]
    if o["type"] == int(m.OptionType.PLAY):
        yo = obs["current"]["yourIndex"]
        return ("PLAY", obs["current"]["players"][yo]["hand"][o["index"]]["id"])
    if o["type"] == int(m.OptionType.CARD):
        return ("CARTA", obs["select"]["deck"][o["index"]]["id"])
    return (int(o["type"]), None)


# ---------------------------------------------------------------------------
# 1. The real step of the record
# ---------------------------------------------------------------------------

def test_paso17_juega_la_ultra_ball_en_vez_de_atacar_con_el_chikorita():
    with open(_FIXTURE, encoding="utf-8") as f:
        obs = json.load(f)["observation"]
    assert _jugada(obs, m.agent(obs)) == ("PLAY", ULTRA_BALL), (
        "con Budew en el activo rival la Ultra Ball CADUCA este turno y el "
        "tablero no ataca mañana: se cava el Meowth ex antes de atacar")


# ---------------------------------------------------------------------------
# 2. The synthetic scenario: the three menus of the chain
# ---------------------------------------------------------------------------
# The record cuts off at step 17 (the agent attacked), so the fetch and the
# next turn are FABRICATED with StateBuilder on the same board.

def _campo(esc, fez_energias=0, mano_extra=()):
    return (esc
            .mi_activo(pk(CHIKORITA, energias=[G], fisicas=1))
            .mi_banca(pk(FEZ, energias=[G] * fez_energias,
                         fisicas=fez_energias))
            .op_activo(pk(BUDEW))
            .op_banca(DREEPY, DREEPY, pk(MUNKIDORI, energias=[G], fisicas=0))
            .op_zonas(mano=5, mazo=43, prizes=6))


# NOTE: `menu_mano()` emits a PLAY option for EACH card in hand, without the
# simulator's legality filter. That is why the record's Meganium (Stage 2
# with no Bayleef underneath: the real game NEVER offers it) is left out of the hands
# of the synthetic MAIN menus -- otherwise the agent "plays" it and the scenario
# measures something else. In the fetch menu it can be there: the hand is not offered there.
def _menu_main(fez_energias=0, mano=(GRASS, GRASS, GRASS, BOSS, BOSS,
                                     ULTRA_BALL, FOREST),
               op_generico=False, partidario_jugado=True):
    """Menu A: the MAIN of step 17 (the turn's energy already attached)."""
    esc = Escenario(turno=TURNO, paso=17, tac=6, primer_jugador=1,
                    energia_jugada=True,
                    partidario_jugado=partidario_jugado)
    esc = _campo(esc, fez_energias=fez_energias)
    if op_generico:
        # CONTROL: the same board with no piece threatening to block
        # Items (neither Budew nor a Dreepy line) -> the Ultra Ball is kept.
        esc.op_activo(pk(MUNKIDORI))
        esc.op_banca(pk(MUNKIDORI), pk(MUNKIDORI))
    return (esc
            .mi_mano(*mano)
            .mazo(MEOWTH, LILLIE, BAYLEEF, OGERPON, APPLIN)
            .resto_al_descarte()
            .menu_mano(con_ataque=True)
            .construir())


def _menu_fetch():
    """Menu B: the fetch of the Ultra Ball just played."""
    esc = Escenario(turno=TURNO, paso=18, tac=7, primer_jugador=1,
                    energia_jugada=True, partidario_jugado=True)
    return (_campo(esc)
            .mi_mano(GRASS, BOSS, BOSS, MEGANIUM, FOREST)
            .mazo(MEOWTH, LILLIE, BAYLEEF, OGERPON, APPLIN)
            .fetch_ultra_ball()
            .resto_al_descarte()
            .construir())


def _menu_manana():
    """Menu C: OUR next turn, already under the Itchy Pollen. Items
    cannot be played (that is why there is none in hand) but the
    Meowth ex can: its Last-Ditch Catch brings the Lillie's."""
    obs = (Escenario(turno=TURNO + 2, paso=30, tac=1, primer_jugador=1)
           .mi_activo(pk(CHIKORITA, energias=[G], fisicas=1))
           .mi_banca(pk(FEZ))
           .op_activo(pk(BUDEW))
           .op_banca(DREEPY, DREEPY, pk(MUNKIDORI, energias=[G], fisicas=0))
           .op_zonas(mano=5, mazo=40, prizes=6)
           .mi_mano(MEOWTH, GRASS, GRASS)
           .mazo(LILLIE, BAYLEEF, OGERPON, APPLIN)
           .resto_al_descarte()
           .menu_mano(con_ataque=True)
           .construir())
    # The Itchy Pollen of the opponent's turn: `itchy_pollen_active` is derived from the
    # ATTACK logs (see the "Opposing ITEM block" section of `agent()`).
    obs["logs"] = [{"type": int(m.LogType.ATTACK), "cardId": BUDEW,
                    "playerIndex": 1, "serial": 88}]
    return obs


def test_menuA_la_ultra_ball_gana_al_ataque_del_chikorita():
    obs = _menu_main()
    assert _jugada(obs, m.agent(obs)) == ("PLAY", ULTRA_BALL)


def test_menuB_el_fetch_de_la_busqueda_pagada_trae_el_meowth_ex():
    obs = _menu_fetch()
    assert _jugada(obs, m.agent(obs)) == ("CARTA", MEOWTH), (
        "la Ultra Ball se pagó EXACTAMENTE por este cuerpo; sin la regla "
        "`bloqueo_de_items_manana` el veto `last_ditch_no_produce` la "
        "desviaba a otra carta")


def test_menuC_manana_el_meowth_ex_se_baja_bajo_el_bloqueo_de_objetos():
    obs = _menu_manana()
    assert _jugada(obs, m.agent(obs)) == ("PLAY", MEOWTH), (
        "bajo el Itchy Pollen los Pokémon y las habilidades SIGUEN jugándose: "
        "el Meowth ex cavado ayer baja y su Last-Ditch trae la Lillie's")


# ---------------------------------------------------------------------------
# 3. Controls: the rule does not fire without its three premises
# ---------------------------------------------------------------------------

def test_control_sin_amenaza_de_bloqueo_la_ultra_ball_se_guarda():
    obs = _menu_main(op_generico=True)
    assert _jugada(obs, m.agent(obs)) != ("PLAY", ULTRA_BALL), (
        "sin Budew ni línea Dreepy enfrente la Ultra Ball NO caduca: sigue "
        "valiendo la regla general de no cavar lo que no se juega hoy")


def test_control_con_atacante_a_una_energia_la_ultra_ball_se_guarda():
    # Fezandipiti ex at 2 energies: next turn's attachment puts it in
    # attack range (Cruel Arrow, 3) -> `_sin_atacante_para_manana` is False.
    obs = _menu_main(fez_energias=2)
    assert _jugada(obs, m.agent(obs)) != ("PLAY", ULTRA_BALL)


def test_control_con_lillie_en_mano_no_hay_nada_que_cavar():
    obs = _menu_main(mano=(GRASS, GRASS, BOSS, LILLIE, ULTRA_BALL, FOREST),
                     partidario_jugado=False)
    assert _jugada(obs, m.agent(obs)) != ("PLAY", ULTRA_BALL), (
        "el Meowth ex vale por la Lillie's que busca; con la Lillie's ya en "
        "la mano el rodeo no compra nada")


# ---------------------------------------------------------------------------
# 4. The new predicates, separately
# ---------------------------------------------------------------------------

def test_bloqueo_de_items_inminente_cubre_budew_y_la_linea_dragapult():
    assert m._bloqueo_de_items_inminente(True, False, False) is True   # Budew
    assert m._bloqueo_de_items_inminente(False, True, False) is True   # Dragapult ex
    assert m._bloqueo_de_items_inminente(False, False, True) is True   # Dreepy
    assert m._bloqueo_de_items_inminente(False, False, False) is False


def test_sin_atacante_para_manana_no_cuenta_al_chikorita_ni_a_los_basicos():
    from types import SimpleNamespace as NS
    _pk = lambda cid, e=0: NS(id=cid, energies=[G] * e)
    tablero = NS(active=[_pk(CHIKORITA, 1)], bench=[_pk(FEZ, 0)])

    # The Chikorita attacks, but it is not a MAIN_ATTACKER; the Fezandipiti ex is at 3
    # energies and only ONE is attached per turn. A Tapu Bulu in hand (4
    # energies) is not "starting to attack tomorrow" either.
    assert m._sin_atacante_para_manana(tablero, {m.Tapu_Bulu: 1}, {}) is True

    # With the Fezandipiti at 2, tomorrow's attachment puts it in attack range.
    cargado = NS(active=[_pk(CHIKORITA, 1)], bench=[_pk(FEZ, 2)])
    assert m._sin_atacante_para_manana(cargado, {}, {}) is False

    # An evolution from hand on top of its pre-evo on the table also counts: it inherits
    # the body's energy and attacks.
    assert m._sin_atacante_para_manana(
        tablero, {MEGANIUM: 1}, {BAYLEEF: 1}) is False
