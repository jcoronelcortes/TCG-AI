"""Tests de la regla "ATACAR CON EL ACTIVO ES LO PRIMERO".

Antes de repartir la energia del turno, el agente debe preguntarse si el ACTIVO
puede llegar a su COSTE DE ATAQUE usando TODAS las vias de carga que le quedan
vivas (adjunte manual + habilidades que puedan apuntarle: Ripening Charge desde
cualquier Hydrapple ex, Teal Dance si el propio activo es el Ogerpon). Si llega
y el ataque hace dano, la energia va al ACTIVO:

  * `_carga_activo_remata` (el ataque NOQUEA)  -> SCORE_CARGA_ACTIVO_REMATE,
    por delante de cargar un atacante de BANCA para promoverlo (41000) y del
    foco de carga de Ogerpon (41700);
  * `_carga_activo_habilita_ataque` (solo chip, pero sin esa carga el turno
    seria ESTERIL) -> SCORE_CARGA_ACTIVO_ATAQUE, sobre Teal Dance (31500) y los
    pivotes de retirada por habilidad (31600).

Caso de origen (user, episodio 88433181, registro_006 paso 67 vs Marnie's
Grimmsnarl, GANADA con error): Hydrapple ex ACTIVO recien evolucionado a 0
energias, TRES Plantas en mano, adjunte manual sin gastar, dos Ripening Charge
vivas y el activo rival (Munkidori) a 10 PV. El agente cargaba al Hydrapple de
BANCA y mandaba las habilidades a un Ogerpon de banca: turno sin atacar con el
KO servido. Ademas el plan de banca era IMPOSIBLE -- promoverlo exigia retirar
al Hydrapple activo (coste 3) con 0 energias encima.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from cg.api import AreaType, OptionType
from state_builder import G, Escenario, pk

APPLIN = m.Applin
DIPPLIN = m.Dipplin
HYDRAPPLE = m.Hydrapple_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
TAPU = m.Tapu_Bulu
MEOWTH = m.Meowth_ex
FEZA = m.Fezandipiti_ex
ENERGIA = m.Basic_Grass_Energy

_FIXTURE = ROOT / "tests" / "fixtures" / "grimmsnarl_step67_carga_activo_para_syrup.json"


@pytest.fixture(autouse=True)
def reset_main_state():
    """Este fichero no tenia reset y funcionaba solo porque ordenaba PRIMERO en
    la suite, heredando los globales limpios del import. Cualquier fichero que
    ordenase antes le dejaba `op_is_crustle_deck` / `meganium_in_play` / ...
    encendidos de la partida anterior y lo tumbaba. Mismo reset que sus
    hermanos: el orden de la suite deja de importar."""
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
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cartas_tracking()


def _obs_step67():
    with open(_FIXTURE, encoding="utf-8") as f:
        return json.load(f)["observation"]


def _opciones_attach(obs):
    """{posicion: 'activo'|'banca-k'} para las opciones ATTACH del menu."""
    destinos = {}
    for i, opt in enumerate(obs["select"]["option"]):
        if opt.get("type") != OptionType.ATTACH:
            continue
        if opt.get("inPlayArea") == AreaType.ACTIVE:
            destinos[i] = "activo"
        else:
            destinos[i] = f"banca-{opt.get('inPlayIndex')}"
    return destinos


def test_step67_carga_el_activo_y_no_el_hydrapple_de_banca():
    """Registro real: la Planta va al Hydrapple ex ACTIVO (Syrup Storm = KO)."""
    obs = _obs_step67()
    cur = obs["current"]
    mio = cur["players"][cur["yourIndex"]]

    # El escenario debe ser el del registro para que el test signifique algo.
    assert mio["active"][0]["id"] == HYDRAPPLE
    assert mio["active"][0]["energies"] == []
    assert cur["energyAttached"] is False
    assert sum(1 for c in mio["hand"] if c["id"] == ENERGIA) >= 2

    destinos = _opciones_attach(obs)
    assert "activo" in destinos.values()
    assert any(d.startswith("banca") for d in destinos.values())

    eleccion = m.agent(obs)

    assert len(eleccion) == 1 and eleccion[0] in destinos, (
        f"esperaba un ATTACH, obtuvo {eleccion} (destinos={destinos})")
    assert destinos[eleccion[0]] == "activo", (
        f"la energia debia ir al ACTIVO, fue a {destinos[eleccion[0]]}")


def test_step67_ripening_charge_apunta_al_activo():
    """Con el adjunte manual ya gastado, Ripening Charge completa el coste."""
    obs = _obs_step67()
    cur = obs["current"]
    mio = cur["players"][cur["yourIndex"]]

    # Simular el paso siguiente: el adjunte manual ya puso 1 Planta en el activo
    # (queda 1 para el coste de Syrup Storm, que la habilidad debe aportar).
    energia = next(c for c in mio["hand"] if c["id"] == ENERGIA)
    mio["hand"] = [c for c in mio["hand"] if c is not energia]
    mio["handCount"] = len(mio["hand"])
    mio["active"][0]["energies"] = [G]
    mio["active"][0]["energyCards"] = [energia]
    cur["energyAttached"] = True
    # Menu con solo las habilidades vivas (Ripening de cada Hydrapple) y END.
    obs["select"]["option"] = [
        {"type": int(OptionType.ABILITY), "area": int(AreaType.ACTIVE), "index": 0},
        {"type": int(OptionType.ABILITY), "area": int(AreaType.BENCH), "index": 0},
        {"type": int(OptionType.ABILITY), "area": int(AreaType.BENCH), "index": 4},
        {"type": int(OptionType.END)},
    ]

    eleccion = m.agent(obs)

    assert eleccion and eleccion[0] in (0, 1), (
        f"esperaba activar Ripening Charge (opt 0/1), obtuvo {eleccion}")


def test_step67_con_el_activo_cargado_ataca():
    """Cierre de la cadena: con las 2 Plantas encima, Syrup Storm se dispara."""
    obs = _obs_step67()
    cur = obs["current"]
    mio = cur["players"][cur["yourIndex"]]

    energias = [c for c in mio["hand"] if c["id"] == ENERGIA][:2]
    mio["hand"] = [c for c in mio["hand"] if c not in energias]
    mio["handCount"] = len(mio["hand"])
    mio["active"][0]["energies"] = [G, G]
    mio["active"][0]["energyCards"] = energias
    cur["energyAttached"] = True
    obs["select"]["option"] = [
        {"type": int(OptionType.ATTACK), "attackId": 195},
        {"type": int(OptionType.END)},
    ]

    assert m.agent(obs) == [0], "con Syrup Storm listo y el rival a 10 PV, ATACA"


# --- Generalizacion deck-agnostica (escenarios sinteticos) -----------------

def test_activo_ogerpon_carga_a_si_mismo_para_rematar():
    """Ogerpon ex ACTIVO a 2 energias: la 3a (Myriad) remata -> va al ACTIVO.

    En banca hay un Hydrapple ex a 0 energias, el objetivo "de desarrollo" que
    antes se llevaba la Planta.
    """
    obs = (Escenario(turno=8, paso=90, tac=2)
           .mi_activo(pk(OGERPON, energias=[G, G]))
           .mi_banca(pk(HYDRAPPLE, pre_evo=[APPLIN, DIPPLIN]), MEOWTH)
           .mi_mano(ENERGIA, ENERGIA)
           .op_activo(pk(m.Munkidori, hp=40))
           .op_banca(pk(m.Froslass, pre_evo=[m.Snorunt]))
           .op_zonas(mano=4, mazo=30, premios=4)
           .menu_attach_energia()
           .construir())

    destinos = _opciones_attach(obs)
    eleccion = m.agent(obs)

    assert destinos[eleccion[0]] == "activo", (
        f"la Planta debia ir al Ogerpon ACTIVO (remata), fue a "
        f"{destinos[eleccion[0]]}")


def test_activo_sin_remate_pero_turno_esteril_tambien_carga_al_activo():
    """Sin KO posible, cargar al activo es la unica forma de atacar hoy."""
    obs = (Escenario(turno=8, paso=90, tac=2)
           .mi_activo(pk(HYDRAPPLE, energias=[G], pre_evo=[APPLIN, DIPPLIN]))
           .mi_banca(pk(APPLIN), MEOWTH)
           .mi_mano(ENERGIA)
           .op_activo(pk(m.Grimmsnarl_ex, hp=320,
                         energias=[G, G, G]))
           .op_zonas(mano=4, mazo=30, premios=5)
           .menu_attach_energia()
           .construir())

    destinos = _opciones_attach(obs)
    eleccion = m.agent(obs)

    assert destinos[eleccion[0]] == "activo", (
        f"sin la carga al activo el turno seria esteril; fue a "
        f"{destinos[eleccion[0]]}")


def test_activo_que_ya_ataca_no_acapara_la_energia():
    """Control negativo: si el activo YA llega a su coste, la regla no dispara.

    El Hydrapple ex activo con 2 energias ya ataca; la Planta debe seguir el
    reparto normal (desarrollo de banca), no quedarse en el activo.
    """
    obs = (Escenario(turno=8, paso=90, tac=2)
           .mi_activo(pk(HYDRAPPLE, energias=[G, G], pre_evo=[APPLIN, DIPPLIN]))
           .mi_banca(pk(OGERPON), MEOWTH)
           .mi_mano(ENERGIA)
           .op_activo(pk(m.Grimmsnarl_ex, hp=320,
                         energias=[G, G, G]))
           .op_zonas(mano=4, mazo=30, premios=5)
           .menu_attach_energia()
           .construir())

    destinos = _opciones_attach(obs)
    eleccion = m.agent(obs)

    assert destinos[eleccion[0]] != "activo", (
        "el activo ya podia atacar: la energia debia ir a la banca")
