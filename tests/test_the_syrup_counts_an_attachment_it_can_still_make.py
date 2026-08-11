"""The Night Stretcher route projected a Grass the turn had no attachment left for.

Syrup Storm scales with the Grass on OUR field, and the ATTACK block's estimator
adds the one it is about to attach. It has two routes to that Grass:

    if hand has a Grass and NOT state.energyAttached:   +1 attachment unit
    elif no Grass in hand, a Night Stretcher in hand,
         and a Grass in the discard:                    +1 attachment unit

The first branch asked whether the turn's attachment still existed from the day
it was written. **The second never did.** With the attachment already spent it
still counted a Grass it could not attach, and with Meganium in play
`_grass_attach_unit()` is TWO, so the projection came out 60 damage high.

FOUND BY THE DIFFERENTIAL ORACLE, and only after two artefacts had been taken
out of the way -- the mirror seat and the plan's attacker (`186d155`). What was
left was small, ours and unanimous: 9 PHANTOM_KO in 1200 games against
`crustle_wall_9`, and 9 of 9 had exactly this board --

    no Grass in hand · a Night Stretcher in hand · Grass in the discard
    Meganium in play · state.energyAttached already True

-- and every one of them predicted our Hydrapple ex would knock out their Mega
Kangaskhan ex and left it standing at 30 (or at 10 behind a Hero's Cape). The
engine was right about the Grass count every single time; we were counting an
eleventh unit that could not exist.

THE FROZEN CORPUS SEES NONE OF THIS. `golden_corpus` reports no changes: the
board does not occur in the 50 committed records, which is why the fix ships with
a fixture taken from the oracle's own dump instead. A rule with no corpus
exposure is not a rule with no cost -- it is a rule the corpus cannot arbitrate,
and the instrument that can is the one that found it.

The fixture is the first of the nine, `partida 1134 paso 63`.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "utils"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import selfplay as sp

FIXTURE = (ROOT / "tests" / "fixtures" /
           "crustle_wall_9_the_syrup_counted_an_attachment_already_spent.json")

GRASS, NIGHT_STRETCHER, MEGANIUM = 1, 1097, 710
HYDRAPPLE_EX, MEGA_KANGASKHAN_EX = 150, 756


@pytest.fixture(scope="module")
def tablero():
    if not FIXTURE.is_file():
        pytest.skip("falta el volcado del oraculo")
    return json.loads(FIXTURE.read_text())


@pytest.fixture(scope="module")
def agente():
    return sp.load_agent(ROOT / "main.py", "syrup_attachment")


def _nuestro(obs):
    cur = obs["current"]
    return cur["players"][cur["yourIndex"]]


# ---------------------------------------------------------------------------
# 1. The board: every precondition of the branch, and no attachment left
# ---------------------------------------------------------------------------

def test_el_tablero_es_el_de_la_rama_sin_guarda(tablero):
    obs = tablero["observation"]
    nos = _nuestro(obs)
    mano = [c["id"] for c in (nos.get("hand") or [])]
    descarte = [c["id"] for c in (nos.get("discard") or [])]
    campo = [b["id"] for z in ("active", "bench") for b in (nos.get(z) or [])]

    assert mano.count(GRASS) == 0, "la primera rama no puede ser la que dispara"
    assert mano.count(NIGHT_STRETCHER) >= 1
    assert descarte.count(GRASS) >= 1
    assert MEGANIUM in campo, "sin Meganium el error seria de 30, no de 60"
    assert obs["current"]["energyAttached"] is True, (
        "el adjunte del turno YA esta gastado: esa es la premisa que faltaba")
    assert campo[0] == HYDRAPPLE_EX


def test_el_objetivo_y_su_vida_son_los_del_hallazgo(tablero):
    assert tablero["finding"]["hp_before"] == 300
    assert tablero["finding"]["hp_after"] == 30
    assert tablero["finding"]["predicted_remain_hp"] == -30


# ---------------------------------------------------------------------------
# 2. The rule
# ---------------------------------------------------------------------------

def test_ya_no_proyectamos_un_KO_que_el_motor_no_da(tablero, agente):
    """The whole finding in one assertion: the plan must stop claiming the body
    falls when the engine leaves it at 30."""
    obs = copy.deepcopy(tablero["observation"])
    agente.agent(obs)
    remain = agente.AGENT_STATE.plan.remain_hp
    assert remain is not None and remain > 0, (
        f"el plan sigue prometiendo el KO (remain_hp={remain}); "
        "el motor deja ese cuerpo a 30")


def test_la_prediccion_cuadra_con_las_Grass_QUE_HAY(tablero, agente):
    """Syrup Storm is 30 + 30 x the Grass on our field. With no attachment left
    the estimator may count what is on the board and not one unit more."""
    obs = copy.deepcopy(tablero["observation"])
    nos = _nuestro(obs)
    en_campo = sum(len(b.get("energies") or [])
                   for z in ("active", "bench") for b in (nos.get(z) or []))
    agente.agent(obs)
    hp_antes = tablero["finding"]["hp_before"]
    proyectado = hp_antes - agente.AGENT_STATE.plan.remain_hp
    assert proyectado == 30 + 30 * en_campo, (
        f"proyectamos {proyectado} con {en_campo} Grass en el campo; "
        f"el motor resolvio {hp_antes - tablero['finding']['hp_after']}")


def test_y_es_exactamente_lo_que_el_motor_resolvio(tablero, agente):
    obs = copy.deepcopy(tablero["observation"])
    agente.agent(obs)
    real = tablero["finding"]["hp_before"] - tablero["finding"]["hp_after"]
    proyectado = tablero["finding"]["hp_before"] - agente.AGENT_STATE.plan.remain_hp
    assert proyectado == real, (
        f"proyectado {proyectado} contra {real} resuelto por el motor")


# ---------------------------------------------------------------------------
# 3. The control: with the attachment still available the Grass DOES count
# ---------------------------------------------------------------------------

def test_con_el_adjunte_disponible_la_ruta_del_stretcher_sigue_contando(tablero, agente):
    """The guard must not delete the branch. On the same board with the turn's
    attachment unspent, the Night Stretcher route is a real Grass and the
    projection is allowed to include it -- otherwise the fix would just be the
    branch removed, and this project has paid for that shape before."""
    obs = copy.deepcopy(tablero["observation"])
    obs["current"]["energyAttached"] = False
    agente.agent(obs)
    con_adjunte = agente.AGENT_STATE.plan.remain_hp

    obs2 = copy.deepcopy(tablero["observation"])
    agente.agent(obs2)
    sin_adjunte = agente.AGENT_STATE.plan.remain_hp

    assert con_adjunte < sin_adjunte, (
        "con el adjunte libre la proyeccion tiene que ser MAYOR (menos hp "
        f"restante): {con_adjunte} contra {sin_adjunte}")
