"""El escalon MAS ALTO de una linea rival, si esta en la BANCA, se GUSTEA.

Escenario (user, `registros/registro_008_pasos_133_hasta_141.json` paso 136,
episodio 89224411, turno 8, vs Marnie's Grimmsnarl ex, **PERDIDA**):

    NOSOTROS (asiento 1, 4 premios)        RIVAL (2 premios)
    activo  Hydrapple ex 300/330, 2e       activo  **Marnie's Impidimp** 70 PV,
    banca   Meganium 2e, Meowth ex,                Basico, **1 energia**
            Fezandipiti ex, Ogerpon ex 4e, banca   Froslass, Froslass,
            Ogerpon ex                             Munkidori 1e,
    mano    Xerosic, **Dawn**, Dipplin,            **Marnie's Morgrem 100 PV,
            Hydrapple ex, **Boss's Orders**,       Fase 1, 2 energias**,
            Bayleef, Poke Pad, Tapu Bulu           Munkidori 1e

Syrup Storm (30 + 30 por cada Planta en TODOS nuestros Pokemon, 8 unidades)
noquea a cualquiera de los dos cuerpos, y los dos rinden **1 premio**. El
agente jugaba **Dawn** y atacaba al Impidimp. Es el error: el Morgrem esta un
escalon MAS ARRIBA de la MISMA linea y solo se alcanza GUSTEANDOLO.

  * matar al Impidimp cobra 1 premio y deja que el **Morgrem** evolucione a
    **Marnie's Grimmsnarl ex** (Fase 2, 320 PV, 2 premios, *Punk Up* busca 5
    energias del mazo al evolucionar) -- que es exactamente lo que paso en el
    registro: el rival promovio el Morgrem y cerro la partida;
  * gustear el Morgrem cobra **el mismo premio** y obliga al rival a rehacer
    los DOS escalones (evolucionar el Impidimp y volver a buscar la Fase 2).

REGLA (simetrica de [[boss-gust-mayor-evolucion-fase2]]): dentro de una linea
Basico -> Fase 1 -> Fase 2 se noquea SIEMPRE la etapa mas alta alcanzable. Si
la que esta mas arriba es la del ACTIVO rival, se ataca y se guarda el Boss's
(test_boss_noquear_la_etapa_mas_alta_de_la_linea); si esta en la BANCA, se
gasta el Boss's en subirla.

Por que no disparaba
--------------------
El bucle deny-evo de la valoracion del Boss's descartaba el Morgrem por
`_bo_active_prize_dominates` (el activo rinde >= premios que la pre-evo: 1 >= 1)
y ninguna de sus tres excepciones cubria este tablero:

  * `_bo_pe_is_ex_line_vs_wall` y `_bo_pe_is_energized_preevo_vs_bare_wall`
    exigen un activo rival con **0 energias**; el Impidimp tenia 1;
  * `_bo_pe_is_energized_preevo_off_line` exige un activo **ajeno** a la linea;
    el Impidimp es la pre-evo de la propia linea.

Las tres miraban la ENERGIA del activo, nunca su ETAPA. El fix
(`_bo_pe_outranks_active`) es el espejo exacto del veto de etapa que ya existia
en el sentido contrario, y es deck-agnostico por partida doble: la etapa sale
del dato de carta (`_supera_en_evolucion`) y el "vale el Boss's" de que la
cadena termine en un ex (`_linea_culmina_en_ex`), no de listas por mazo.

Medicion: 1 solo flip en las 63 decisiones nuestras del episodio 89224411 (el
de este paso). Corpus dorado sin cambios. Self-play vs bot (700 partidas por
rama): Marnie 95.0% vs 93.9%, Cynthia 99.4% vs 98.7%, Dragapult 97.3% = 97.3%.

Unificacion posterior (`_preevo_de_linea_ex`)
---------------------------------------------
El bloque standalone `_deny_evo_via_boss` -- el que alimenta al motor Meowth ex
-> Last-Ditch Catch -> Boss's cuando la carta esta en el MAZO -- clasificaba la
pre-evo con la lista curada `EX_PREEVO_IDS`, que solo crecia *despues* de perder
una partida (la linea Cynthia se anadio asi). Ahora usa el mismo helper de dato
de carta, con la guarda `DUNSPARCE_IDS` (su linea culmina en Dudunsparce ex pero
el gusteo los tiene PROHIBIDOS como objetivo: motivar un gusteo hacia un objetivo
vetado es el fallo del Dwebble del log 86339758). Es superconjunto exacto de la
lista -- lo fija `test_el_helper_es_SUPERCONJUNTO_de_la_lista_curada` -- y anade
tres cartas en todo el meta: Frillish (jellicent_lock, con su Jellicent ex EN SU
MAZO), Applin/Dipplin (festival_lead) y Snorunt (marnie).

Esa segunda parte es NEUTRA en winrate y el gate no la puede medir: con 2500
partidas por rama, jellicent_lock 94.2% vs 94.9%, festival_lead 99.0% = 99.0% y
el GRUPO DE CONTROL -- mega_lucario, donde las dos ramas ejecutan exactamente el
mismo codigo porque ninguna carta de ese mazo cambia de clase -- 92.2% vs 93.2%,
o sea 1.0 punto de ruido puro. Su justificacion no es el marcador sino no volver
a tener que inscribir a mano cada linea rival nueva.
"""

import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

import main as m
from cg.api import AreaType, OptionType, SelectContext, SelectType

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "marnie_step136_gustear_el_morgrem_no_el_impidimp.json")

IMPIDIMP = m.Marnies_Impidimp
MORGREM = m.Marnies_Morgrem
GRIMMSNARL = m.Grimmsnarl_ex
HYDRAPPLE = m.Hydrapple_ex
BOSS = m.Boss_Orders
DAWN = m.Dawn
FROSLASS = m.Froslass
MUNKIDORI = m.Munkidori


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


def _pkm(card_id, energias=0):
    return SimpleNamespace(id=card_id, energies=[1] * energias, energyCards=[],
                           tools=[])


def _idx(obs, **campos):
    """Indice de la opcion del menu que cumple todos los campos dados."""
    return next(i for i, o in enumerate(obs["select"]["option"])
                if all(o.get(k) == v for k, v in campos.items()))


def _mano_idx(obs, card_id):
    """Posicion de `card_id` en NUESTRA mano (la que usan las opciones type=7)."""
    yo = obs["current"]["yourIndex"]
    return next(i for i, c in enumerate(obs["current"]["players"][yo]["hand"])
                if c["id"] == card_id)


def _menu_de_gusteo(obs):
    """Convierte el menu MAIN en el select de OBJETIVO del Boss's ya jugado."""
    cur = obs["current"]
    yo = cur["yourIndex"]
    mio, riv = cur["players"][yo], cur["players"][1 - yo]
    mio["hand"] = [c for c in mio["hand"] if c["id"] != BOSS]
    mio["handCount"] = len(mio["hand"])
    cur["supporterPlayed"] = True
    obs["select"] = {
        "type": int(SelectType.CARD), "context": int(SelectContext.SWITCH),
        "minCount": 1, "maxCount": 1,
        "remainDamageCounter": 0, "remainEnergyCost": 0,
        "option": [{"type": int(OptionType.CARD), "area": int(AreaType.BENCH),
                    "index": k, "playerIndex": 1 - yo}
                   for k in range(len(riv["bench"]))],
        "deck": None, "contextCard": None,
        "effect": {"id": BOSS, "playerIndex": yo, "serial": 500},
    }
    return obs


# ---------------------------------------------------------------------------
# 1. El escenario: sin el, el test no mide nada
# ---------------------------------------------------------------------------

def test_el_fixture_es_el_paso_136_con_la_fase_1_en_la_banca():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    riv = o["current"]["players"][1 - yo]

    assert o["current"]["turn"] == 8 and not o["current"]["supporterPlayed"]

    # Nosotros: Hydrapple ex de activo y el menu ofreciendo Dawn, Boss's y atacar.
    assert mio["active"][0]["id"] == HYDRAPPLE
    assert {BOSS, DAWN} <= {c["id"] for c in mio["hand"]}
    assert _idx(o, type=7, index=_mano_idx(o, BOSS)) >= 0
    assert _idx(o, type=7, index=_mano_idx(o, DAWN)) >= 0
    assert _idx(o, type=13) >= 0

    # El rival: Impidimp (Basico) de activo CON energia -- por eso no bastaba
    # con las excepciones de "muro desnudo" -- y el Morgrem (Fase 1) energizado
    # en la banca. Los dos cuerpos rinden 1 premio.
    assert riv["active"][0]["id"] == IMPIDIMP
    assert len(riv["active"][0]["energies"]) == 1
    banca = [b["id"] for b in riv["bench"]]
    assert banca == [FROSLASS, FROSLASS, MUNKIDORI, MORGREM, MUNKIDORI]
    assert len(riv["bench"][3]["energies"]) == 2
    assert m.prize_count_op(_pkm(IMPIDIMP)) == m.prize_count_op(_pkm(MORGREM)) == 1

    # ...y la linea acaba en un ex de 2 premios: por eso cortarla vale el Boss's.
    assert m.prize_count_op(_pkm(GRIMMSNARL)) == 2


def test_el_hydrapple_noquea_a_los_dos_cuerpos():
    """La regla solo tiene sentido si los dos KOs son REALES: si el Morgrem no
    muriera, gustearlo seria regalarle una retirada gratis al rival."""
    o = _obs()
    riv = o["current"]["players"][1 - o["current"]["yourIndex"]]
    assert riv["active"][0]["hp"] == 70 and riv["bench"][3]["hp"] == 100
    # Syrup Storm: 30 + 30 por cada Planta en TODOS nuestros Pokemon.
    mio = o["current"]["players"][o["current"]["yourIndex"]]
    plantas = len(mio["active"][0]["energies"]) + sum(
        len(b["energies"]) for b in mio["bench"])
    assert 30 + 30 * plantas >= 100


# ---------------------------------------------------------------------------
# 2. La decision y el objetivo
# ---------------------------------------------------------------------------

def test_se_juega_el_boss_no_el_dawn():
    o = _obs()
    assert m.agent(o) == [_idx(o, type=7, index=_mano_idx(o, BOSS))], (
        "con la Fase 1 de la linea en la BANCA y noqueable, se juega Boss's: "
        "mismo premio que atacar al Basico de enfrente, pero corta la linea un "
        "escalon mas arriba y retrasa dos turnos a Marnie's Grimmsnarl ex")


def test_el_objetivo_del_gusteo_es_el_morgrem():
    o = _menu_de_gusteo(_obs())
    riv = o["current"]["players"][1 - o["current"]["yourIndex"]]
    elegido = m.agent(o)
    assert riv["bench"][elegido[0]]["id"] == MORGREM, (
        "el gusteo va a la Fase 1 energizada, no a las Froslass ni a los "
        "Munkidori de soporte")


def test_con_la_fase_1_ya_de_activo_no_se_gasta_el_boss():
    """Control (el veto de etapa, en el mismo tablero): si el escalon alto YA
    esta de activo, atacarlo es gratis y el Boss's se guarda."""
    o = _obs()
    riv = o["current"]["players"][1 - o["current"]["yourIndex"]]
    activo, banca = riv["active"][0], riv["bench"][3]
    activo["id"], banca["id"] = MORGREM, IMPIDIMP
    activo["hp"] = activo["maxHp"] = 100
    banca["hp"] = banca["maxHp"] = 70
    activo["preEvolution"] = [{"id": IMPIDIMP, "playerIndex": 0, "serial": 900}]
    banca["preEvolution"] = []

    assert m.agent(o) == [_idx(o, type=13)], (
        "con la Fase 1 delante se ATACA: mismo premio, corta la linea igual de "
        "arriba y no gasta el Boss's ni el Supporter del turno")


def test_la_regla_no_es_de_la_linea_marnie(monkeypatch):
    """Deck-agnostico: el mismo tablero con la linea Dreepy -> Drakloak ->
    Dragapult ex se resuelve igual, sin tocar ninguna lista por mazo."""
    o = _obs()
    riv = o["current"]["players"][1 - o["current"]["yourIndex"]]
    activo, banca = riv["active"][0], riv["bench"][3]
    activo["id"], banca["id"] = m.Dreepy, m.Drakloak
    activo["hp"] = activo["maxHp"] = 60
    banca["hp"] = banca["maxHp"] = 90
    activo["preEvolution"] = []
    banca["preEvolution"] = [{"id": m.Dreepy, "playerIndex": 0, "serial": 900}]

    assert m.agent(o) == [_idx(o, type=7, index=_mano_idx(o, BOSS))]


# ---------------------------------------------------------------------------
# 3. `_linea_culmina_en_ex`, en aislamiento (deck-agnostico)
# ---------------------------------------------------------------------------

def test_la_linea_ex_se_deriva_del_dato_de_carta():
    # Lineas que SI terminan en un atacante de 2 premios: cortarlas vale el Boss's.
    for cid in (IMPIDIMP, MORGREM, m.Cynthias_Gible, m.Cynthias_Gabite,
                m.Dreepy, m.Drakloak, m.Ralts, m.Kirlia, m.Duraludon,
                m.Riolu, m.Buneary, m.Applin, m.Dipplin):
        assert m._linea_culmina_en_ex(cid), cid


def test_la_linea_alakazam_queda_fuera():
    """Abra -> Kadabra -> Alakazam acaba en un cuerpo de 1 premio: gustear su
    pre-evo rinde lo mismo que atacar de frente. Es [[boss-no-gustear-preevo-
    linea-no-ex]], y aqui sale gratis del dato de carta."""
    assert not m._linea_culmina_en_ex(m.Abra)
    assert not m._linea_culmina_en_ex(m.Kadabra)
    assert not m._linea_culmina_en_ex(m.Dwebble_Grass)
    assert not m._linea_culmina_en_ex(m.Hops_Phantump)


def test_el_helper_es_SUPERCONJUNTO_de_la_lista_curada():
    """`_preevo_de_linea_ex` sustituye a `EX_PREEVO_IDS` en el bloque standalone
    `_deny_evo_via_boss` (Boss's buscado desde el MAZO con Meowth ex ->
    Last-Ditch). La sustitucion solo es valida si NO pierde ninguna linea que
    alguien inscribio a mano tras perder una partida."""
    perdidas = [cid for cid in (m.EX_PREEVO_IDS - m.NONEX_FINAL_PREEVO_IDS)
                if not m._preevo_de_linea_ex(cid)]
    assert perdidas == [], [m.card_table[c].name for c in perdidas]


def test_el_helper_cubre_lineas_que_la_lista_curada_no_tenia():
    """Frillish -> Jellicent ex esta en `deck/rivales/jellicent_lock.csv` y NO
    estaba en `EX_PREEVO_IDS`: la lista curada solo crecia despues de perder."""
    FRILLISH = 597
    assert m.card_table[FRILLISH].name == "Frillish"
    assert FRILLISH not in m.EX_PREEVO_IDS
    assert m._preevo_de_linea_ex(FRILLISH)


def test_dunsparce_no_motiva_un_gusteo_que_tiene_prohibido():
    """Dunsparce -> Dudunsparce ex culmina en ex, pero el manejador de seleccion
    veta SIEMPRE a Dunsparce como objetivo. Un motivo que apunta a un objetivo
    prohibido gasta (o busca) el Boss's para acabar subiendo otra cosa: es el
    fallo del Dwebble del log 86339758."""
    for cid in m.DUNSPARCE_IDS:
        assert m._linea_culmina_en_ex(cid), "la linea SI acaba en ex..."
        assert not m._preevo_de_linea_ex(cid), "...pero no debe motivar el gusteo"


def test_la_cima_de_una_linea_no_culmina_en_nada():
    # Una Fase 2 (o un Basico sin evolucion) no tiene ya nada por encima.
    assert not m._linea_culmina_en_ex(GRIMMSNARL)
    assert not m._linea_culmina_en_ex(HYDRAPPLE)
    assert not m._linea_culmina_en_ex(m.Teal_Mask_Ogerpon_ex)
    # Lo que no es Pokemon (o no existe) no tiene linea.
    assert not m._linea_culmina_en_ex(BOSS)
    assert not m._linea_culmina_en_ex(-12345)
