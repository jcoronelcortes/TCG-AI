"""A KO BETWEEN TURNS does not enable Flip the Script: Fezandipiti ex is not played.

Scenario (user, episode 88914948 registro_008 step 76 vs Marnie/Grimmsnarl,
LOST):

    US (seat 1)                              RIVAL (Marnie/Grimmsnarl)
    active  Meowth ex 110/170                active  Munkidori 90/110 2e
    bench   Meganium 130, Ogerpon ex 150,    bench   Munkidori 90, 2x Froslass,
            Ogerpon ex 150, Tapu Bulu 140            2x Marnie's Impidimp
    hand    Fezandipiti ex, Bayleef,
            Meganium, Unfair Stamp, Tapu Bulu
    prizes 6 - 5   (the rival has just taken one: we lost the Dipplin)

Turn 8, with a free bench slot: the agent played Fezandipiti ex to cash in
Flip the Script's draw of 3. The ability was NOT available -- the turn
closed without using it and the body stayed on the bench as a gift of 2
prizes in the last slot.

THE WINDOW, NOT THE SOURCE OF THE DAMAGE
----------------------------------------
Flip the Script (and the Unfair Stamp, which carries the SAME clause printed on it) requires
one of our Pokemon to have been Knocked Out "during your OPPONENT'S LAST TURN".
The record's logs say where the Dipplin died:

    TURN_END(rival) -> 14 x HP_CHANGE(putDamageCounter, -10) -> Dipplin to the
    discard -> the rival takes a prize -> TURN_START(ours)

It is Freezing Shroud (Froslass: 1 counter on each Pokemon WITH AN ABILITY, and there were
TWO Froslass), an effect that fires BETWEEN TURNS. The KO does not fall inside the rival's
turn: it falls in no-man's-land. The engine confirms it twice in the same
menu: it does not offer the Unfair Stamp we had in hand nor, after playing the body,
the ability.

The cut is NOT "attack vs ability". The same episode refutes that: in step
105 Munkidori MOVED 3 counters with Adrena-Brain and killed our Ogerpon ex
INSIDE the rival's turn -- and the next turn the engine DID offer the Stamp.
An ability that knocks out inside the rival's turn counts; an attack that knocked out
between turns would not. What decides is the WINDOW.

The old detector only looked at the EFFECT of the KO (the rival takes a prize ->
`op_prize` goes down), which does not say WHEN the body died. `_rastrear_ventana_de_ko`
follows the TURN_START / TURN_END of the logs and classifies each KO of ours; the
result can only LOWER `ko_last_turn`, never raise it, so with no
evidence in the logs the behaviour is the same as before.
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m

FEZ = m.Fezandipiti_ex
STAMP = m.Unfair_Stamp

_FIX = ROOT / "tests" / "fixtures"
_FIX_ENTRE_TURNOS = _FIX / "marnie_ko_entre_turnos_no_baja_fez_step76.json"
_FIX_TURNO_RIVAL = _FIX / "marnie_ko_en_turno_rival_habilita_el_sello_step107.json"


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._cards_prizes_identified = False
    m._cards_last_turn = -1
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m.ko_last_turn = False
    m._ko_detected_this_turn = False
    m._prev_op_prize = 6
    yield
    m._init_cards_tracking()


def _cargar(fixture):
    """(previous observation, decision observation) from the record."""
    with open(fixture, encoding="utf-8") as f:
        datos = json.load(f)
    return datos["observacion_previa"], datos["observation"]


def _jugadas(obs):
    """(type, card_id) of each menu option."""
    yo = obs["current"]["yourIndex"]
    mano = obs["current"]["players"][yo]["hand"]
    salida = []
    for o in obs["select"]["option"]:
        if o["type"] == int(m.OptionType.PLAY):
            salida.append(("PLAY", mano[o["index"]]["id"]))
        elif o["type"] == int(m.OptionType.END):
            salida.append(("END", None))
        else:
            salida.append((o["type"], None))
    return salida


def _log(**campos):
    return SimpleNamespace(**campos)


# ---------------------------------------------------------------------------
# 1. The record: a KO between turns -> the body is NOT played
# ---------------------------------------------------------------------------

def test_ko_entre_turnos_no_baja_fezandipiti():
    previa, decision = _cargar(_FIX_ENTRE_TURNOS)

    # The real menu offered playing the Fezandipiti ex.
    jugadas = _jugadas(decision)
    assert ("PLAY", FEZ) in jugadas, jugadas

    # ... and the engine itself said the clause was NOT satisfied: we had the
    # Unfair Stamp in hand and it does not appear as playable.
    yo = decision["current"]["yourIndex"]
    mano = [c["id"] for c in decision["current"]["players"][yo]["hand"]]
    assert STAMP in mano, mano
    assert ("PLAY", STAMP) not in jugadas, jugadas

    m.agent(previa)          # it brings the rival's TURN_END
    eleccion = m.agent(decision)

    assert not m.ko_last_turn, (
        "el KO llego ENTRE TURNOS (Freezing Shroud): Flip the Script no se "
        "puede usar y `ko_last_turn` debe quedar en False")
    assert jugadas[eleccion[0]] != ("PLAY", FEZ), (
        f"con la habilidad muerta, bajar Fezandipiti ex regala 2 premios y el "
        f"ultimo hueco de banca a cambio de nada; jugo {jugadas[eleccion[0]]}")


def test_el_menu_del_motor_manda_sobre_la_inferencia_de_logs():
    """Without the window logs, the Stamp missing from the menu already gives it away.

    It is the backup oracle: `ko_last_turn` arrives True because of the prize the
    rival took, but the Unfair Stamp is in hand and the engine does not
    offer it -- hence the clause is not satisfied and the ability does not exist either.
    """
    _, decision = _cargar(_FIX_ENTRE_TURNOS)
    m.agent(decision)          # WITHOUT the previous observation: we did not see the TURN_END
    assert m._own_ko_outside_op_turn == -99
    assert not m.ko_last_turn


# ---------------------------------------------------------------------------
# 2. The other side: a KO INSIDE the rival's turn -> the clause IS satisfied
# ---------------------------------------------------------------------------

def test_ko_por_habilidad_dentro_del_turno_rival_si_habilita():
    previa, decision = _cargar(_FIX_TURNO_RIVAL)

    # Adrena-Brain (Munkidori) moved 3 counters and killed our Ogerpon ex
    # INSIDE the rival's turn: the engine offers the Stamp the next turn.
    jugadas = _jugadas(decision)
    assert ("PLAY", STAMP) in jugadas, jugadas

    m.agent(previa)
    m.agent(decision)

    assert m.ko_last_turn, (
        "un KO por HABILIDAD dentro del turno del rival cuenta igual que uno "
        "por ataque: la clausula habla de la ventana, no de la fuente del dano")


# ---------------------------------------------------------------------------
# 3. The classifier, dry
# ---------------------------------------------------------------------------

def _ko_propio(serial=1, area=m.AreaType.BENCH):
    return _log(type=m.LogType.MOVE_CARD, playerIndex=1, cardId=FEZ,
                serial=serial, fromArea=area, toArea=m.AreaType.DISCARD)


@pytest.mark.parametrize("logs, dentro, fuera", [
    # A KO inside the rival's turn.
    ([_log(type=m.LogType.TURN_START, playerIndex=0), _ko_propio()], 9, -99),
    # A KO between turns (after the rival's TURN_END).
    ([_log(type=m.LogType.TURN_START, playerIndex=0),
      _log(type=m.LogType.TURN_END, playerIndex=0), _ko_propio()], -99, 9),
    # A self-KO on OUR turn (recoil): it does not enable anything either.
    ([_log(type=m.LogType.TURN_START, playerIndex=1), _ko_propio()], -99, 9),
    # With no turn marker there is no evidence: it is not classified.
    ([_ko_propio()], -99, -99),
])
def test_clasificador_de_ventana(logs, dentro, fuera):
    m._reset_ventana_de_ko()
    m._rastrear_ventana_de_ko(logs, my_index=1, turn=9)
    assert m._own_ko_inside_op_turn == dentro
    assert m._own_ko_outside_op_turn == fuera


def test_el_cuerpo_del_rival_y_las_energias_no_son_kos_nuestros():
    m._reset_ventana_de_ko()
    m._rastrear_ventana_de_ko([
        _log(type=m.LogType.TURN_START, playerIndex=0),
        # A KO of the RIVAL (playerIndex 0)
        _log(type=m.LogType.MOVE_CARD, playerIndex=0, cardId=FEZ, serial=5,
             fromArea=m.AreaType.ACTIVE, toArea=m.AreaType.DISCARD),
        # our attached energy to the discard (it accompanies the KO, it is not the body)
        _log(type=m.LogType.MOVE_CARD, playerIndex=1, cardId=m.Basic_Grass_Energy,
             serial=6, fromArea=m.AreaType.ENERGY, toArea=m.AreaType.DISCARD),
        # our pre-evolution to the discard (the same card we already counted)
        _log(type=m.LogType.MOVE_CARD, playerIndex=1, cardId=m.Applin, serial=7,
             fromArea=m.AreaType.PRE_EVOLUTION, toArea=m.AreaType.DISCARD),
    ], my_index=1, turn=9)
    assert m._own_ko_inside_op_turn == -99
    assert m._own_ko_outside_op_turn == -99


def test_partida_nueva_borra_la_ventana():
    """Self-play chains episodes in the same process."""
    m._rastrear_ventana_de_ko([
        _log(type=m.LogType.TURN_START, playerIndex=0),
        _log(type=m.LogType.TURN_END, playerIndex=0), _ko_propio()],
        my_index=1, turn=9)
    assert m._own_ko_outside_op_turn == 9
    m._init_cards_tracking()
    assert m._own_ko_outside_op_turn == -99
    assert m._log_current_turn == m._TURN_LOG_UNKNOWN
