"""vs Dragapult: Tapu Bulu NO se baja con el tablero ya desarrollado.

Escenario (`registros/registro_003_pasos_018_hasta_056.json`, paso 43, turno 3,
PERDIDA vs Dragapult -- episodio 88912610):

    NOSOTROS                                   RIVAL (Dragapult)
    activo  Meganium 160, 2 energías           activo  Dreepy 70 (+ herramienta)
    banca   Dipplin 80                         banca   Dreepy, Dreepy
            Teal Mask Ogerpon ex x3 (2 en. c/u)
    mano    Ultra Ball, Chikorita, Dawn,
            Planta x3, **Tapu Bulu**

Con **cinco Pokémon ya en juego** el agente bajaba Tapu Bulu y dejaba la banca
LLENA. Dos pasos antes el Bug Catching Set ya lo había elegido a él (sobre
Bayleef) para traerlo a la mano, así que el error venía en pareja: buscar la
carta y jugarla.

Por qué está mal en ESTE matchup. Tapu Bulu es el atacante **manual** del mazo:
su papel es pegar cuando el rival apaga nuestras habilidades (Iron Thorns,
Cornerstone) o inmuniza a nuestros ex (Crustle, Sylveon). Dragapult no hace ni
lo uno ni lo otro -- Teal Mask Ogerpon ex e Hydrapple ex atacan con normalidad
--, así que ahí es un cuerpo de relleno sin energía. Y cada cuerpo extra le PAGA
al rival:

  * *Phantom Dive* reparte 6 contadores por la banca (`op_bench_snipe_threat` ya
    se enciende en este matchup); con la banca llena el reparto siempre
    encuentra dónde doler;
  * es un premio más que regalar, y ocupa el hueco que necesitan las líneas que
    sí atacan (Applin/Dipplin/Hydrapple ex y Chikorita/Bayleef/Meganium).

Regla (user): **vs Dragapult, Tapu Bulu solo se baja con <=2 Pokémon en juego**
-- ahí manda la supervivencia, porque un KO nos dejaría sin banca
([[nunca-terminar-turno-banca-vacia]]).

Causa: la rama PLAY de Tapu Bulu decidía por tablero, no por matchup. La
condición que disparó aquí (`_tapu_in_play_count >= 4 and meganium_in_play and
not _op_is_crustle_like`) puntúa 16000 precisamente cuando hay MUCHOS cuerpos en
juego -- justo lo contrario de lo que pide este matchup. Y estaba ANTES en la
cadena que el veto genérico por aglomeración (`_tapu_in_play_count > 2`).

Arreglo: `_dragapult_no_tapu`, calculado una sola vez y aplicado en los cuatro
sitios que deciden lo mismo, para que buscar y bajar no puedan contradecirse
([[state-builder-escenarios-sinteticos]] documenta el mismo patrón en
`_matchup_permite_bajar`):

  * la rama PLAY (primera de la cadena),
  * los fetch de Bug Catching Set / Night Stretcher / Dawn,
  * `_matchup_permite_bajar`, que usa la red de rescate del turno estéril.

El veto **cede ante el muro** (`_op_is_crustle_like`): si además hay en mesa algo
que anula habilidades o inmuniza a nuestros ex, Tapu Bulu vuelve a ser el único
atacante y manda la colisión de matchups
([[colision-cubchoo-muro-inmune-pivote]]).

Corpus dorado: exactamente dos flips, los dos de este turno -- el fetch del Bug
Catching Set (Tapu Bulu -> Bayleef) y este paso (bajar Tapu Bulu -> Ultra Ball,
que es la que trajo el Hydrapple ex).
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
            / "dragapult_no_bajar_tapu_bulu_step43.json")
_REGISTRO = (ROOT / "registros"
             / "registro_003_pasos_018_hasta_056.json")

TAPU = m.Tapu_Bulu
DREEPY = m.Dreepy
MEGANIUM = m.Meganium
OGERPON = m.Teal_Mask_Ogerpon_ex


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
    m._ld_supp_comprometido = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cartas_tracking()


def _obs():
    return copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])


def _idx_tapu(obs):
    """Índice de la opción 'PLAY Tapu Bulu' del menú principal."""
    mano = obs["current"]["players"][obs["current"]["yourIndex"]]["hand"]
    for i, o in enumerate(obs["select"]["option"]):
        if o.get("type") == int(m.OptionType.PLAY) and mano[o["index"]]["id"] == TAPU:
            return i
    raise AssertionError("el fixture no ofrece bajar Tapu Bulu")


# ---------------------------------------------------------------------------
# 1. El escenario: sin él, el test no mide nada
# ---------------------------------------------------------------------------

def test_el_fixture_es_la_banca_llena_vs_dragapult():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    riv = o["current"]["players"][1 - yo]

    # Cinco Pokémon en juego: activo Meganium + cuatro en banca.
    banca = [b for b in mio["bench"] if b]
    assert mio["active"][0]["id"] == MEGANIUM
    assert len(banca) == 4
    assert sum(1 for b in banca if b["id"] == OGERPON) == 3
    assert 1 + len(banca) > 2, "con <=2 cuerpos la regla NO aplica"

    # Tapu Bulu está en la mano y el menú ofrece bajarlo.
    assert any(c["id"] == TAPU for c in mio["hand"])
    assert _idx_tapu(o) == 2

    # El rival es Dragapult (línea Dreepy) y NO es un mazo de muro: no anula
    # habilidades ni inmuniza a nuestros ex, así que Tapu Bulu no hace falta.
    assert riv["active"][0]["id"] == DREEPY
    assert any(b and b["id"] == DREEPY for b in riv["bench"])

    # Y el registro confirma que ahí se bajó (la jugada que este test veta).
    fx = json.load(open(_FIXTURE, encoding="utf-8"))
    assert fx["accion_registrada"] == [2]


def test_no_se_baja_tapu_bulu():
    o = _obs()
    m.meganium_in_play = True
    assert m.agent(o) != [_idx_tapu(o)], (
        "vs Dragapult, con 5 Pokémon ya en juego, Tapu Bulu no aporta ataque "
        "y sólo suma un cuerpo al reparto de Phantom Dive")


# ---------------------------------------------------------------------------
# 2. El replay fiel: el mismo turno reproducido desde frío
# ---------------------------------------------------------------------------

def _replay_hasta(paso_final):
    """Reproduce el registro desde su primer paso y devuelve las decisiones."""
    datos = json.load(open(_REGISTRO, encoding="utf-8"))
    pasos = datos["source_step_numbers"]
    decisiones = {}
    for i, par in enumerate(datos["steps"]):
        if pasos[i] > paso_final:
            break
        for item in par:
            obs = item.get("observation") or {}
            if (item.get("status") != "ACTIVE" or not obs.get("select")
                    or obs["current"].get("yourIndex") != 1):
                continue
            decisiones[pasos[i]] = (copy.deepcopy(obs), m.agent(copy.deepcopy(obs)))
    return decisiones


@pytest.mark.skipif(
    not _REGISTRO.exists(),
    reason="registro local rotado (registros/ es transitorio)")
def test_replay_fiel_ni_lo_busca_ni_lo_baja():
    dec = _replay_hasta(43)

    # Paso 42: el Bug Catching Set mira 7 cartas y elige 2. Tapu Bulu ya no
    # es una de ellas (antes salía Planta + Tapu Bulu).
    obs42, eleccion42 = dec[42]
    vistas = obs42["select"]["deck"] or obs42["current"]["looking"]
    elegidas = [vistas[obs42["select"]["option"][i]["index"]]["id"]
                for i in eleccion42]
    assert TAPU in [c["id"] for c in vistas], "el BCS SÍ veía a Tapu Bulu"
    assert TAPU not in elegidas, (
        "no se busca lo que después no se va a poder bajar")

    # Paso 43: y el turno sigue por la Ultra Ball (la que trajo Hydrapple ex).
    obs43, eleccion43 = dec[43]
    assert eleccion43 != [_idx_tapu(obs43)]


# ---------------------------------------------------------------------------
# 3. Los límites de la regla
# ---------------------------------------------------------------------------

def test_con_dos_cuerpos_en_juego_si_se_baja():
    """<=2 Pokémon en juego: manda la supervivencia, no el reparto de daño."""
    o = _obs()
    mio = o["current"]["players"][o["current"]["yourIndex"]]
    mio["bench"] = mio["bench"][:1]          # activo + 1 = 2 en juego
    m.meganium_in_play = True
    assert m.agent(o) == [_idx_tapu(o)]


def _sin_items_en_mano(obs):
    """Quita la Ultra Ball y rehace el menú.

    Tapu Bulu tiene un tope propio y anterior a todo esto
    (`TAPU_WAIT_FOR_ITEMS_SCORE`: no se baja mientras queden items por jugar,
    [[bug-catching-set-antes-de-bajar-pokemon]]). Para medir el veto de
    matchup hay que sacar ese tope de en medio.
    """
    yo = obs["current"]["yourIndex"]
    mio = obs["current"]["players"][yo]
    mio["hand"] = [c for c in mio["hand"] if c["id"] != m.Ultra_Ball]
    mio["handCount"] = len(mio["hand"])
    jugables = {m.Tapu_Bulu, m.Chikorita}
    obs["select"]["option"] = (
        [{"index": i, "type": int(m.OptionType.PLAY)}
         for i, c in enumerate(mio["hand"]) if c["id"] in jugables]
        + [{"type": int(m.OptionType.RETREAT)}, {"type": int(m.OptionType.END)}])


def test_el_veto_cede_ante_un_muro_inmune():
    """Colisión de matchups: con un Cornerstone en mesa Tapu vuelve a ser EL
    atacante (nuestros ex con habilidad hacen 0), y el veto se levanta."""
    o = _obs()
    yo = o["current"]["yourIndex"]
    riv = o["current"]["players"][1 - yo]
    riv["active"][0]["id"] = m.Cornerstone_Mask_Ogerpon_ex
    riv["active"][0]["hp"] = riv["active"][0]["maxHp"] = 220
    _sin_items_en_mano(o)
    m.meganium_in_play = True
    assert m.agent(o) == [_idx_tapu(o)]


def test_con_el_muro_fuera_el_veto_vuelve():
    """Control del test anterior: mismo tablero SIN el muro -> sigue vetado."""
    o = _obs()
    _sin_items_en_mano(o)
    m.meganium_in_play = True
    assert m.agent(o) != [_idx_tapu(o)]


def test_el_veto_no_toca_otros_matchups():
    """Sin Dragapult enfrente, el mismo tablero sigue bajando a Tapu Bulu."""
    o = _obs()
    yo = o["current"]["yourIndex"]
    riv = o["current"]["players"][1 - yo]
    for pk in riv["active"] + [b for b in riv["bench"] if b]:
        pk["id"] = m.Chikorita                 # un básico cualquiera, no-Dragapult
        pk["hp"] = pk["maxHp"] = 70
    m.meganium_in_play = True
    assert m.agent(o) == [_idx_tapu(o)]


# ---------------------------------------------------------------------------
# 4. El predicado compartido: buscar y bajar no pueden contradecirse
# ---------------------------------------------------------------------------

def test_matchup_permite_bajar_veta_tapu_vs_dragapult():
    campo = {}
    assert m._matchup_permite_bajar(TAPU, campo, False, False,
                                    dragapult_no_tapu=True) is False
    # Sin el veto (<=2 cuerpos, u otro rival) sigue permitido...
    assert m._matchup_permite_bajar(TAPU, campo, False, False) is True
    # ...y sólo afecta a Tapu Bulu.
    assert m._matchup_permite_bajar(OGERPON, campo, False, False,
                                    dragapult_no_tapu=True) is True
