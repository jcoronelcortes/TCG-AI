"""Lana's Aid: no se gasta el Supporter del turno por una carta MUERTA.

Escenario (user, episodio **88904232** paso 140, turno 10, vs Marnie's
Grimmsnarl ex --- partida **GANADA** 1-5 en premios; la fuga no costo el
partido, pero es fuga igual y el self-play la cobra: +2.2 pp en el matchup.
Ojo al citar `registro_NNN`: son datos locales transitorios y el nombre se
recicla; el ancla estable es el `EpisodeId`. Cuando se escribio este test el
paso vivia en `registros/registro_010_pasos_139_hasta_144.json`):

    NOSOTROS (2 premios)                     RIVAL (5 premios)
    activo  Hydrapple ex 240/330  6e         activo  Marnie's Grimmsnarl 100/100
    banca   Meganium     100/160  2e                 (sin energias)
            Meowth ex    140/170  2e
            Ogerpon ex   150/210  6e
            Meowth ex    140/170  0e
            Ogerpon ex   180/210  4e   <- banca LLENA (5/5)
    mano    Ogerpon ex + Dawn + **Lana's Aid**
    descarte  4x Lillie's, 3x Bug Catching Set, 2x Night Stretcher,
              2x Forest of Vitality, 1x Poke Pad y **1 Applin**
              -- NI UNA sola Energia Planta

El agente jugo **Lana's Aid**. El menu de recuperacion tenia UNA sola opcion
(`select.option` con un unico elemento): ese Applin. Y ese Applin es carta
muerta por partida doble --- con la banca LLENA un Basico no entra de ninguna
forma, y la linea ya estaba resuelta con el Hydrapple ex en el activo. Se gasto
el Supporter del turno para mover una carta del descarte a la mano.

Causa: la capa de JUGADA cobraba su base de 300 por `total_recoverable >= 1`,
que solo cuenta cartas del descarte. La capa de SELECCION si sabe leer la mesa
(`_pokemon_injugable`, `_plan_de_planta`; ver
`test_lana_recupera_energia_no_basicos`), pero para entonces la carta ya esta
jugada: el veto tenia que subir un escalon.

Regla del user: **Lana's se juega SOLO si hace falta algo que se pueda poner en
juego ESTE turno** --- Pokemon jugables o Energia adjuntable. Se aplica con la
MISMA lectura de mesa que decide luego que se levanta:

  1. VETO (`lana_val = 0`) si nada de lo recuperable entra en juego hoy: ningun
     Pokemon jugable (`_pokemon_injugable`) y ninguna via de adjunte viva
     (`_plan_de_planta().slots_hoy`) para una Planta del descarte.
  2. TECHO (`LANA_PLAY_SIN_DEMANDA`) si lo jugable no hace FALTA: Energia que
     NADIE pide (todos los atacantes en juego llegan ya a `ATTACK_ENERGY_REQ`,
     o la mano tiene mas Plantas de las que caben hoy), o un Pokemon que cabe
     en la banca pero que ningun bono de necesidad reclama
     (`_lana_val_bonos == LANA_PLAY_BASE_RECUPERABLE`). Techo y no veto: la
     carta sigue siendo jugable, solo cede el turno a otro Supporter con valor
     real.

Y la MISMA puerta en **Dawn** (bloque 4 de este archivo): con Lana's vetada, el
Supporter del turno se iba en el Dawn de la mano, que con la banca llena y las
dos lineas ya evolucionadas tampoco podia traer nada jugable. La regla ya
existia palabra por palabra pero encerrada en `op_is_alakazam_deck`; se
generaliza a todos los matchups y saca los pares pre->evo de `EVO_LINES`.

Corpus dorado: un unico flip --- el paso 140 pasa de jugar Lana's a ATACAR (el
mismo KO que la partida real hizo despues de tirar el Supporter).
"""

import collections
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from cg.api import OptionType

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "marnie_lana_recupera_applin_muerto_step140.json")

APPLIN = m.Applin
HYDRAPPLE = m.Hydrapple_ex


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


def _obs(**mut):
    o = copy.deepcopy(json.load(open(_FIXTURE, encoding="utf-8"))["observation"])
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    if mut.get("hueco_en_banca"):
        # Huecos de banca: resucitan al Applin (se puede bajar HOY) y, a
        # partir de 3, dejan la banca CORTA (<=2), que es un bono de necesidad.
        mio["bench"] = mio["bench"][:-mut["hueco_en_banca"]]
    if mut.get("evo_pendiente"):
        # Un Applin en banca: su Fase 1 (Dipplin) sigue en el mazo, asi que hay
        # una evolucion REAL que Dawn puede traer aunque la banca este llena.
        mio["bench"][-1] = {"appearThisTurn": False, "energies": [],
                            "energyCards": [], "hp": 70, "id": m.Applin,
                            "maxHp": 70, "playerIndex": yo,
                            "preEvolution": [], "serial": 980, "tools": []}
    if mut.get("planta_en_descarte"):
        # Energia recuperable + adjunte del turno sin gastar: hay algo que
        # SI se puede poner en juego hoy.
        for k in range(mut["planta_en_descarte"]):
            mio["discard"].append({"id": m.Basic_Grass_Energy,
                                   "playerIndex": yo, "serial": 950 + k})
    if mut.get("planta_en_mano"):
        # La mano ya tiene mas Plantas de las que caben este turno: recuperar
        # otra no pone NADA en el campo hoy. (Se anaden al final: ninguna
        # opcion del menu apunta a esos indices.)
        for k in range(mut["planta_en_mano"]):
            mio["hand"].append({"id": m.Basic_Grass_Energy,
                                "playerIndex": yo, "serial": 970 + k})
        mio["handCount"] = len(mio["hand"])
    if mut.get("tapu_sin_energia"):
        # Un Tapu Bulu de banca a 0/4 crea DEMANDA real de Planta.
        mio["bench"][-1] = {"appearThisTurn": False, "energies": [],
                            "energyCards": [], "hp": 140, "id": m.Tapu_Bulu,
                            "maxHp": 140, "playerIndex": yo,
                            "preEvolution": [], "serial": 960, "tools": []}
    return o


def _opcion_de_mano(obs, card_id):
    """Indice de la opcion que juega `card_id` desde la mano."""
    yo = obs["current"]["yourIndex"]
    mano = obs["current"]["players"][yo]["hand"]
    for i, o in enumerate(obs["select"]["option"]):
        if (o.get("type") == int(OptionType.PLAY)
                and mano[o["index"]]["id"] == card_id):
            return i
    return None


def _valor_lana(obs):
    """`values[Lanas_Aid]`: el valor de mesa que decide la capa de JUGADA."""
    capturado = {}
    orig = m._score_lanas_aid_play

    def espia(ctx, score):
        capturado.setdefault("v", ctx.supp_values.get(m.Lanas_Aid))
        return orig(ctx, score)

    m._score_lanas_aid_play = espia
    try:
        m.agent(obs)
    finally:
        m._score_lanas_aid_play = orig
    assert "v" in capturado, "el scorer de Lana's Aid no llego a evaluarse"
    return capturado["v"]


# ---------------------------------------------------------------------------
# 1. El escenario: sin el, el test no mide nada
# ---------------------------------------------------------------------------

def test_el_fixture_es_la_recuperacion_muerta():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]

    assert not o["current"]["supporterPlayed"]        # el Supporter esta vivo
    assert len(mio["bench"]) == mio["benchMax"] == 5  # banca LLENA
    assert mio["active"][0]["id"] == HYDRAPPLE        # la linea ya resuelta

    # Todo lo que Lana's Aid puede levantar: UN Applin y ninguna Planta.
    recuperable = [c["id"] for c in mio["discard"]
                   if c["id"] in (m.Chikorita, m.Applin, m.Tapu_Bulu, m.Pinsir)
                   or c["id"] == m.Basic_Grass_Energy]
    assert recuperable == [APPLIN]

    # Y ese Applin es carta muerta: Basico con la banca llena.
    campo = collections.Counter([c["id"] for c in mio["bench"]] +
                                [mio["active"][0]["id"]])
    assert m._pokemon_injugable(APPLIN, campo, len(mio["bench"]),
                                mio["benchMax"])

    assert _opcion_de_mano(o, m.Lanas_Aid) is not None


# ---------------------------------------------------------------------------
# 2. La decision
# ---------------------------------------------------------------------------

def test_no_juega_lana_para_recuperar_una_carta_muerta():
    obs = _obs()
    lana = _opcion_de_mano(obs, m.Lanas_Aid)
    assert m.agent(obs) != [lana], (
        "con la banca llena y solo un Applin recuperable, Lana's Aid no mete "
        "nada en juego: gastar el Supporter del turno en ella es tirarlo")


def test_el_valor_de_jugada_queda_vetado():
    assert _valor_lana(_obs()) == 0


def test_el_turno_se_va_en_atacar_y_el_supporter_se_conserva():
    """El desenlace completo: ni Lana's ni Dawn (que con la banca llena y las
    dos lineas ya evolucionadas tampoco trae nada jugable). El turno se gasta
    en el KO --- que en la partida real tambien se hizo, DESPUES de tirar el
    Supporter."""
    obs = _obs()
    ataque = next(i for i, o in enumerate(obs["select"]["option"])
                  if o.get("type") == int(OptionType.ATTACK))
    assert m.agent(obs) == [ataque]


# ---------------------------------------------------------------------------
# 3. Los limites: cuando SI hace falta algo que poner en juego, Lana's vuelve
# ---------------------------------------------------------------------------

def test_con_hueco_en_banca_el_applin_es_jugable_pero_no_necesario():
    # El hueco lo hace jugable, pero la linea Applin->Hydrapple ya esta en el
    # activo y la banca no esta corta: ningun bono lo reclama -> techo.
    v = _valor_lana(_obs(hueco_en_banca=1))
    assert 0 < v <= m.LANA_PLAY_SIN_DEMANDA, (
        "un Basico que cabe pero que nadie pide no vale el Supporter del "
        f"turno; obtuvo {v}")


def test_con_la_banca_corta_el_cuerpo_del_descarte_si_hace_falta():
    # Con la banca a 2 cuerpos, recuperar un Basico si es necesidad real
    # (bono de banca corta): Lana's recupera todo su valor.
    v = _valor_lana(_obs(hueco_en_banca=3))
    assert v > m.LANA_PLAY_SIN_DEMANDA, (
        "con la banca corta el Applin del descarte es un cuerpo que hace "
        f"falta; obtuvo {v}")


def test_con_planta_en_el_descarte_y_demanda_real_lana_vale():
    # Tapu Bulu a 0/4 en banca + Plantas en el descarte + adjunte sin gastar:
    # hay energia que se puede jugar HOY y alguien que la pide.
    v = _valor_lana(_obs(planta_en_descarte=3, tapu_sin_energia=True))
    assert v > m.LANA_PLAY_SIN_DEMANDA, (
        "con demanda real de energia Lana's no debe quedarse en el techo de "
        f"'nadie la pide'; obtuvo {v}")


def test_planta_jugable_pero_que_no_llega_al_campo_hoy_cede_el_turno():
    # Mismas Plantas en el descarte, pero la MANO ya tiene mas de las que caben
    # este turno: lo recuperado no pone nada en el campo hoy. La carta sigue
    # siendo jugable (techo, no veto), solo cede el Supporter del turno.
    v = _valor_lana(_obs(planta_en_descarte=3, planta_en_mano=6))
    assert 0 < v <= m.LANA_PLAY_SIN_DEMANDA, (
        "energia recuperable que no llega al campo hoy: jugable, pero por "
        f"debajo del resto de Supporters; obtuvo {v}")


# ---------------------------------------------------------------------------
# 4. La MISMA puerta en Dawn: el Supporter no se salva cambiando de carta
# ---------------------------------------------------------------------------
#
# Con Lana's vetada, el Supporter del turno se iba en el Dawn de la mano: con
# la banca 5/5 y las dos lineas ya evolucionadas (Meganium + Hydrapple ex en
# juego), los hasta 3 Pokemon que busca del mazo son igual de inertes --- y
# ademas adelgazan el mazo, que es como se pierde por deckout. La regla ya
# existia palabra por palabra, pero encerrada en `op_is_alakazam_deck`; no
# tenia nada de especifico de ese matchup, asi que ahora corre siempre y saca
# los pares pre->evo de `EVO_LINES`.

def _valor_dawn(obs):
    """`values[Dawn]`, capturado en el scorer de Dawn."""
    capturado = {}
    orig = m._score_dawn_play

    def espia(ctx):
        capturado.setdefault("v", ctx.supp_values.get(m.Dawn))
        return orig(ctx)

    m._score_dawn_play = espia
    try:
        m.agent(obs)
    finally:
        m._score_dawn_play = orig
    assert "v" in capturado, "el scorer de Dawn no llego a evaluarse"
    return capturado["v"]


def test_el_fixture_tiene_las_dos_lineas_ya_evolucionadas():
    o = _obs()
    yo = o["current"]["yourIndex"]
    mio = o["current"]["players"][yo]
    campo = [c["id"] for c in mio["bench"]] + [mio["active"][0]["id"]]
    assert m.Meganium in campo and m.Hydrapple_ex in campo
    # Ningun cuerpo en juego admite evolucion: no hay nada que Dawn pueda traer
    # y poner encima.
    for linea in m.EVO_LINES:
        for pre, evo in zip(linea, linea[1:]):
            assert pre not in campo, (pre, evo)
    assert _opcion_de_mano(o, m.Dawn) is not None


def test_no_juega_dawn_con_la_banca_llena_y_nada_que_evolucionar():
    assert _valor_dawn(_obs()) == 0


def test_con_una_evolucion_pendiente_dawn_vuelve_a_valer():
    # Un Applin en banca: Dawn puede traer el Dipplin del mazo y evolucionarlo
    # sin ocupar banca.
    assert _valor_dawn(_obs(evo_pendiente=True)) > 0


def test_con_hueco_en_banca_dawn_conserva_su_valor():
    # La puerta solo muerde con la banca LLENA: con hueco, cualquier Basico que
    # traiga Dawn se puede bajar.
    assert _valor_dawn(_obs(hueco_en_banca=1)) > 0
