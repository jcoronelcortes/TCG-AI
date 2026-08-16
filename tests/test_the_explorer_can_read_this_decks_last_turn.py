"""El explorador de turno no sabia leer el turno final de ESTE mazo.

`utils/turn_explorer.py` es la herramienta que responde "existia una linea
mejor?", y sobre el ultimo turno del episodio 93579160 vs Alakazam (PERDIDA)
respondia que no. La respuesta era de la HERRAMIENTA, no del tablero: le faltaban
las dos piezas de las que vive este mazo.

1. WILD GROWTH EN LA CARGA SIMULADA. La observacion lista energia EFECTIVA -- un
   cuerpo con un Grass fisico bajo un Meganium muestra DOS entradas en
   `energies` (`ptcg/calc/energy.py`, idea 1) -- pero `_attach` añadia UNA sola
   entrada por carta. Toda linea proyectada quedaba corta en un simbolo por
   carga, y justo en los tableros donde el duplicador ES el plan: un Meganium a
   2/4 seguia leyendose a 3/4 despues de adjuntar y su ataque no aparecia nunca.

2. LANA'S AID. La unica recuperacion modelada era Night Stretcher. En ese tablero
   el descarte tenia DIEZ Grass, la mano NINGUNO, y la unica ruta a la carga que
   falta era la Lana's Aid: el modelo no la conocia, asi que decia "no hay linea"
   de un turno que el propio agente si juega. Es un Supporter, o sea que comparte
   ranura con el Boss's Orders y ahora eso se ramifica.

Los dos son bugs de la herramienta, y los dos se demuestran sobre el mismo
tablero: desde el asiento del Meganium el turno GANA (Lana's Aid -> adjuntar ->
Solar Beam 140 sobre un Alakazam de 140, el ultimo premio) y desde el asiento que
el episodio eligio -- un Fezandipiti ex sin energias -- no gana nada.

DE DONDE SALE EL TABLERO, y por que no de `records/`. La primera version de este
fichero leia `records/registro_014_pasos_175_hasta_178.json` y `records/` es data
LOCAL Y TRANSITORIA (git-ignored): se regenero a mitad de la sesion que escribio
esto y el test paso de medir a saltarse en silencio, que es la peor de las dos
cosas que puede hacer. El turno 14 se DERIVA aqui del fixture ya congelado de la
promocion (`_turn14`), con la unica transformacion que hace el motor entre los
dos menus: el cuerpo elegido pasa al puesto activo, el turno avanza y sus
banderas se reinician. La derivacion reproduce el tablero grabado carta por carta
-- diez Grass en el descarte, ninguno en la mano -- y ya no depende de nada que
se pueda borrar.

Ver `tests/test_the_seat_that_closes_the_game_is_not_a_tie_break.py` para la
regla de promocion que decide en cual de los dos asientos empieza este turno.
"""

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "utils", ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import main as m
import turn_explorer as te

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "alakazam_our_match_point_the_seat_that_closes_the_game_step174.json")

GRASS = 1
# La carta que robamos al empezar ese turno, tal como la grabo la partida. No
# toca la linea -- es el eslabon medio de la propia linea Meganium -- pero
# sacarla del tablero seria inventarse una mano mas pequeña que la real.
DRAW_OF_THE_TURN = m.Bayleef


def _turn14(promoted_id):
    """El turno 14 que sigue a promover `promoted_id`, desde el fixture.

    La transformacion es la del motor entre los dos menus y nada mas: el cuerpo
    elegido toma el puesto activo, robamos la carta del turno y las banderas del
    turno (Supporter, adjunte, retirada, estadio) vuelven a cero.
    """
    obs = copy.deepcopy(json.loads(_FIXTURE.read_text(encoding="utf-8"))["observation"])
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    k = next(i for i, b in enumerate(mine["bench"])
             if b and b["id"] == promoted_id)
    mine["active"] = [mine["bench"][k]]
    mine["bench"] = [b for i, b in enumerate(mine["bench"]) if i != k]
    mine["hand"] = list(mine["hand"]) + [{"id": DRAW_OF_THE_TURN,
                                          "playerIndex": cur["yourIndex"],
                                          "serial": 69}]
    mine["handCount"] = len(mine["hand"])
    mine["deckCount"] = max(0, mine["deckCount"] - 1)
    cur["turn"] += 1
    cur["turnActionCount"] = 1
    for flag in ("supporterPlayed", "energyAttached", "retreated",
                 "stadiumPlayed"):
        cur[flag] = False
    return obs


# ---------------------------------------------------------------------------
# 0. El tablero: sin esto los tests de abajo no miden nada
# ---------------------------------------------------------------------------

def test_the_board_is_the_one_the_record_left_us():
    obs = _turn14(m.Meganium)
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    theirs = cur["players"][1 - cur["yourIndex"]]

    # Meganium delante, a UNA carga de Solar Beam (2 de 4 efectivas).
    assert mine["active"][0]["id"] == m.Meganium
    assert len(mine["active"][0]["energies"]) == 2
    assert m.ATTACK_ENERGY_REQ[m.Meganium] == 4

    # Sin Grass en mano: la unica ruta es la Lana's Aid sobre el descarte.
    assert all(c["id"] != m.Basic_Grass_Energy for c in mine["hand"])
    assert any(c["id"] == m.Lanas_Aid for c in mine["hand"])
    assert sum(1 for c in mine["discard"]
               if c["id"] == m.Basic_Grass_Energy) == 10

    # Su Alakazam entero, y un premio en cada monton.
    assert theirs["active"][0]["hp"] == 140
    assert len(mine["prize"]) == 1


# ---------------------------------------------------------------------------
# 1. Wild Growth: una carta de Grass son DOS simbolos con el duplicador en mesa
# ---------------------------------------------------------------------------

def test_the_simulated_attachment_is_worth_what_wild_growth_makes_it_worth():
    obs = _turn14(m.Meganium)
    body = {"id": m.Dipplin, "energies": [], "energyCards": []}
    te._attach(body, {"id": GRASS, "playerIndex": 1, "serial": 999}, obs)
    assert len(body["energies"]) == 2, "Wild Growth no se aplico"
    assert len(body["energyCards"]) == 1, "se inventaron cartas, no simbolos"


def test_without_the_doubler_in_play_it_is_worth_one():
    """El control: sin Meganium en mesa la carga vale uno, como antes."""
    obs = _turn14(m.Fezandipiti_ex)
    cur = obs["current"]
    mine = cur["players"][cur["yourIndex"]]
    mine["bench"] = [b for b in mine["bench"] if b and b["id"] != m.Meganium]
    assert not any(p["id"] == m.Meganium for p in te._pokes(te._yo(obs)))
    body = {"id": m.Dipplin, "energies": [], "energyCards": []}
    te._attach(body, {"id": GRASS, "playerIndex": 1, "serial": 999}, obs)
    assert len(body["energies"]) == 1


# ---------------------------------------------------------------------------
# 2. Lana's Aid: la unica ruta a la carga que falta en ese tablero
# ---------------------------------------------------------------------------

def test_lanas_aid_is_a_legal_action_and_costs_the_supporter_slot():
    obs = _turn14(m.Meganium)

    acciones = dict(te.acciones_legales(obs))
    etiqueta = next(k for k in acciones if k.startswith("LANA->"))
    assert etiqueta == "LANA->3 PLANTA"
    # Y con la mano sin Grass, la Lana's Aid es lo unico que abre el adjunte.
    assert not any(k.startswith("ATTACH->") for k in acciones)

    despues = acciones[etiqueta](obs)
    y2 = te._yo(despues)
    assert sum(1 for c in y2["hand"] if c["id"] == m.Basic_Grass_Energy) == 3
    assert despues["current"]["supporterPlayed"] is True
    # Y con la ranura gastada, el Boss's Orders de la mano ya no es jugable.
    assert not any(k.startswith("BOSS->")
                   for k, _ in te.acciones_legales(despues))


# ---------------------------------------------------------------------------
# 3. Las dos piezas juntas: el turno que gana, y solo desde un asiento
# ---------------------------------------------------------------------------

def test_from_the_meganium_seat_the_turn_wins_the_game():
    gana, linea, _ = te.explore(_turn14(m.Meganium), respetar_menu=False)
    assert gana[0] == 1, (gana, linea)      # gana
    assert gana[1] == 1, (gana, linea)      # el ultimo premio
    assert linea == ["LANA->3 PLANTA", "ATTACH->Meganium", "ATTACK"], linea


def test_from_the_seat_the_episode_chose_there_is_no_winning_line():
    """El control del anterior: el mismo turno, el mismo modelo, otro asiento."""
    gana, linea, _ = te.explore(_turn14(m.Fezandipiti_ex), respetar_menu=False)
    assert gana[0] == 0, (gana, linea)
    assert gana[1] == 0, (gana, linea)
