"""El explorador de turno no sabia leer el turno final de ESTE mazo.

`utils/turn_explorer.py` es la herramienta que responde "¿existia una linea
mejor?", y sobre el ultimo turno de `registro_013`/`registro_014` (episodio
93579160 vs Alakazam, PERDIDA) respondia que no. La respuesta era de la
herramienta, no del tablero: le faltaban las dos piezas de las que vive este
mazo.

1. WILD GROWTH EN LA CARGA SIMULADA. La observacion lista energia EFECTIVA -- un
   cuerpo con un Grass fisico bajo un Meganium muestra DOS entradas en
   `energies` (`ptcg/calc/energy.py`, idea 1) -- pero `_attach` añadia UNA sola
   entrada por carta. Toda linea proyectada quedaba corta en un simbolo por
   carga, y justo en los tableros donde el duplicador ES el plan: un Meganium a
   2/4 seguia leyendose a 3/4 despues de adjuntar y su ataque no aparecia nunca.

2. LANA'S AID. La unica recuperacion modelada era Night Stretcher. En el tablero
   del registro el descarte tenia DIEZ Grass, la mano NINGUNO, y la unica ruta a
   la carga que falta era la Lana's Aid: el modelo no la conocia, asi que decia
   "no hay linea" de un turno que el propio agente si juega. Es un Supporter, o
   sea que comparte ranura con el Boss's Orders y ahora eso se ramifica.

Los dos son bugs de la HERRAMIENTA, y los dos se demuestran sobre el mismo
tablero real: desde el asiento del Meganium el turno GANA (Lana's Aid -> adjuntar
-> Solar Beam 140 sobre un Alakazam de 140, el ultimo premio) y desde el asiento
que el episodio eligio -- un Fezandipiti ex sin energias -- no gana nada.

Ver `tests/test_the_seat_that_closes_the_game_is_not_a_tie_break.py` para la
regla de promocion que decide en cual de los dos asientos empieza ese turno.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "utils", ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import main as m
import turn_explorer as te

_RECORD = ROOT / "records" / "registro_014_pasos_175_hasta_178.json"

GRASS = 1


def _turn14():
    """El primer menu MAIN del turno 14, tal como lo grabo la partida."""
    data = json.loads(_RECORD.read_text(encoding="utf-8"))
    return copy.deepcopy(data["steps"][0][1]["observation"])


def _with_meganium_in_front(obs):
    """El mismo turno con el asiento que da la promocion arreglada."""
    out = copy.deepcopy(obs)
    mine = out["current"]["players"][out["current"]["yourIndex"]]
    k = next(i for i, b in enumerate(mine["bench"])
             if b and b["id"] == m.Meganium)
    mine["active"], mine["bench"][k] = [mine["bench"][k]], mine["active"][0]
    # Flip the Script era del Fezandipiti ex: con el Meganium delante el motor
    # no ofreceria esa opcion.
    out["select"]["option"] = [o for o in out["select"]["option"]
                               if o.get("type") != 10]
    return out


pytestmark = pytest.mark.skipif(
    not _RECORD.exists(),
    reason="records/ es data local y transitoria (git-ignored)")


# ---------------------------------------------------------------------------
# 1. Wild Growth: una carta de Grass son DOS simbolos con el duplicador en mesa
# ---------------------------------------------------------------------------

def test_the_simulated_attachment_is_worth_what_wild_growth_makes_it_worth():
    obs = _with_meganium_in_front(_turn14())
    body = {"id": m.Dipplin, "energies": [], "energyCards": []}
    te._attach(body, {"id": GRASS, "playerIndex": 1, "serial": 999}, obs)
    assert len(body["energies"]) == 2, "Wild Growth no se aplico"
    assert len(body["energyCards"]) == 1, "se inventaron cartas, no simbolos"


def test_without_the_doubler_in_play_it_is_worth_one():
    """El control: sin Meganium en mesa la carga vale uno, como antes."""
    obs = _with_meganium_in_front(_turn14())
    mine = obs["current"]["players"][obs["current"]["yourIndex"]]
    mine["active"] = [{"id": m.Dipplin, "hp": 80, "maxHp": 80,
                       "energies": [], "energyCards": [], "serial": 900,
                       "preEvolution": [], "tools": []}]
    mine["bench"] = [b for b in mine["bench"] if b and b["id"] != m.Meganium]
    body = {"id": m.Dipplin, "energies": [], "energyCards": []}
    te._attach(body, {"id": GRASS, "playerIndex": 1, "serial": 999}, obs)
    assert len(body["energies"]) == 1


# ---------------------------------------------------------------------------
# 2. Lana's Aid: la unica ruta a la carga que falta en ese tablero
# ---------------------------------------------------------------------------

def test_lanas_aid_is_a_legal_action_and_costs_the_supporter_slot():
    obs = _with_meganium_in_front(_turn14())
    mine = obs["current"]["players"][obs["current"]["yourIndex"]]
    assert any(c["id"] == m.Lanas_Aid for c in mine["hand"])
    assert all(c["id"] != m.Basic_Grass_Energy for c in mine["hand"])
    assert sum(1 for c in mine["discard"] if c["id"] == m.Basic_Grass_Energy) >= 3

    acciones = dict(te.acciones_legales(obs))
    etiqueta = next(k for k in acciones if k.startswith("LANA->"))
    assert etiqueta == "LANA->3 PLANTA"

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
    gana, linea, _ = te.explore(_with_meganium_in_front(_turn14()),
                                respetar_menu=False)
    assert gana[0] == 1, (gana, linea)      # gana
    assert gana[1] == 1, (gana, linea)      # el ultimo premio
    assert linea == ["LANA->3 PLANTA", "ATTACH->Meganium", "ATTACK"], linea


def test_from_the_seat_the_episode_chose_there_is_no_winning_line():
    """El control del anterior: el mismo turno, el mismo modelo, otro asiento."""
    gana, linea, _ = te.explore(_turn14(), respetar_menu=False)
    assert gana[0] == 0, (gana, linea)
