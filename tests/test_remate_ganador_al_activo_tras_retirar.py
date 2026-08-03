"""MATCH POINT contra el ACTIVO rival: el rematador esta en la BANCA.

Escenario (user, episodio 89104831, registro_010 paso 144 vs Marnie's
Grimmsnarl ex, PERDIDA):

    NOSOTROS (asiento 1)                    RIVAL (Marnie's Grimmsnarl)
    activo  Fezandipiti ex 20/210 (2 ef.)   activo  Marnie's Grimmsnarl ex
    banca   Meowth ex 130, Meowth ex 160,           310/320, 3 energias {D}
            Teal Mask Ogerpon ex 200 (4e),  banca   2x Munkidori 100,
            Meganium 150, Ogerpon ex 200            Froslass 90, Impidimp 70
    mano    Xerosic, Chikorita, Dipplin,
            Hydrapple ex, Meganium, Boss's
    premios 2 - 1   (a nosotros nos faltan DOS)

El menu ofrecia exactamente cuatro cosas: Xerosic, Boss's Orders, RETIRAR y
END. Habia mate en el tablero:

    RETIRAR Fezandipiti (coste 1, y lleva energia) -> promover el Teal Mask
    Ogerpon ex de 4 energias -> Myriad Leaf Shower.

Myriad Leaf Shower hace 30 + 30 por cada Energia unida a AMBOS activos
(ver [[ogerpon-myriad-cuenta-ambos-activos]]): 30 + 30 x (4 nuestras + 3 del
Grimmsnarl) = 240, y el Grimmsnarl ex tiene DEBILIDAD Planta -> 240 x 2 =
**480 >= 310**. Es un Pokemon ex: **2 premios**, justo los 2 que faltaban.
Partida ganada en el sitio.

El agente jugo Boss's Orders, gusteo una Froslass (1 premio), la noqueo y
cerro el turno a 1 premio. El rival remato en el suyo.

EL BUG: EL ACTIVO RIVAL ERA INVISIBLE
-------------------------------------
Todas las lecturas de "¿puedo noquear al ACTIVO rival?" se hacian con el
Pokemon que esta HOY en el activo -- `_boss_dmg_to` -> `_bo_can_ko_active`,
y `_bpr_active_can_ko` dentro de `_boss_prize_rank`. Con el Fezandipiti
atascado (2 efectivas, su ataque pide 3) eso da 0 dano, luego
`_bo_active_prize = 0`: el Grimmsnarl ex de 2 premios contaba como CERO
premios y cualquier cuerpo de banca de 1 premio le ganaba. Boss's puntuaba
5200 (`gusteo_por_prize_rank`) contra los 3500 de la retirada.

La asimetria es el fallo, no el numero: para los objetivos de BANCA ese mismo
bloque SI mira a traves de la retirada (`_bench_attacker_can_ko`, tanto en
`_boss_prize_rank` como en `_bo_win_via_bench`); para el ACTIVO, nunca.

EL ARREGLO: `_win_ko_active_via_promote`
----------------------------------------
Cierra la simetria en el unico caso que no admite discusion -- cuando ese KO
GANA la partida (`prize_count_op(activo rival) >= my_prize`), la retirada es
pagable y el rematador esta en la BANCA (si el activo ACTUAL ya noquea, la
via es atacar, no retirar). Ganar es VETO, mismo criterio que
PROMO_MATCH_POINT_VETO: el Boss's se veta, `_boss_prize_rank` se anula y la
retirada sube a 9600 con `_TIER_WIN_ATTACK` para que ninguna carga de energia
la adelante por ORDEN.
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

BOSS = m.Boss_Orders
OGERPON = m.Teal_Mask_Ogerpon_ex
GRIMMSNARL = 648
FROSLASS = 104

_FIX = (ROOT / "tests" / "fixtures"
        / "marnie_remate_ganador_al_activo_tras_retirar_step144.json")


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cartas_tracking()
    m._cartas_first_scan_done = False
    m._cartas_prizes_identified = False
    m._cartas_last_turn = -1
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m.ko_last_turn = False
    m._ko_detected_this_turn = False
    m._prev_op_prize = 6
    # Globals de matchup/mesa: sin resetearlos, el orden de la suite decide que
    # Supporter gana entre los NO vetados y la frontera se vuelve fragil.
    m.meganium_in_play = False
    m.forest_in_play = False
    m.we_go_first = False
    m.op_is_crustle_deck = False
    m.op_is_cornerstone_deck = False
    m.op_has_mega_kangaskhan = False
    yield
    m._init_cartas_tracking()


def _fixture():
    with open(_FIX, encoding="utf-8") as f:
        return json.load(f)


def _tipos(obs):
    return [o["type"] for o in obs["select"]["option"]]


def _idx_de_tipo(obs, tipo):
    return _tipos(obs).index(int(tipo))


def _idx_play_boss(obs):
    yo = obs["current"]["yourIndex"]
    mano = obs["current"]["players"][yo]["hand"]
    for i, o in enumerate(obs["select"]["option"]):
        if o["type"] == int(m.OptionType.PLAY) and mano[o["index"]]["id"] == BOSS:
            return i
    return -1


# ---------------------------------------------------------------------------
# El tablero: que el mate existia de verdad, medido con los evaluadores del motor
# ---------------------------------------------------------------------------

def test_el_mate_existia_ogerpon_de_banca_noquea_al_grimmsnarl():
    obs = m.to_observation_class(_fixture()["observation"])
    st = obs.current
    yo, rival = st.players[1], st.players[0]

    assert len(yo.prize) == 2, "nos faltaban DOS premios"
    opa = rival.active[0]
    assert opa.id == GRIMMSNARL and opa.hp == 310
    assert m.prize_count_op(opa) == 2, "el Grimmsnarl ex vale 2 premios"

    # La retirada era pagable: coste 1 y el Fezandipiti llevaba energia.
    act = yo.active[0]
    assert len(act.energies) >= m.RETREAT_COST.get(act.id, 1)

    m.meganium_in_play = any(p is not None and p.id == m.Meganium
                             for p in (yo.active + yo.bench))
    total_grass = sum(len(p.energies) for p in (yo.active + yo.bench)
                      if p is not None)

    ogerpon = next(p for p in yo.bench
                   if p is not None and p.id == OGERPON and len(p.energies) == 4)
    base = m._attacker_base_damage(ogerpon.id, opa, len(ogerpon.energies),
                                   grass_scale=total_grass,
                                   teal_self_energy=len(ogerpon.energies),
                                   bench_count=len(yo.bench))
    # 30 + 30 x (4 nuestras + 3 suyas) = 240 ... y x2 por debilidad Planta.
    assert base == 240, base
    efectivo = m._our_effective_damage(ogerpon, opa, base, m.meganium_in_play)
    assert efectivo == 480, efectivo
    assert efectivo >= opa.hp, "el KO al activo rival GANA la partida"

    # Ninguna gustada de la banca rival cobra los 2 premios que faltan.
    assert all(m.prize_count_op(b) == 1
               for b in rival.bench if b is not None)


# ---------------------------------------------------------------------------
# La decision: RETIRAR, no Boss's Orders
# ---------------------------------------------------------------------------

def test_retira_en_vez_de_gustear():
    fx = _fixture()
    previa, decision = fx["observacion_previa"], fx["observation"]

    # El menu real ofrecia las dos: jugar el Boss's y RETIRAR.
    i_boss = _idx_play_boss(decision)
    i_retreat = _idx_de_tipo(decision, m.OptionType.RETREAT)
    assert i_boss >= 0 and i_retreat >= 0, _tipos(decision)

    m.agent(previa)
    eleccion = m.agent(decision)

    assert eleccion == [i_retreat], (
        f"esperaba RETIRAR (idx {i_retreat}), eligio {eleccion}")
    assert eleccion != [i_boss], "el Boss's tira el turno ganador"


def test_la_linea_completa_cierra_la_partida():
    """Tras retirar: promover el Ogerpon cargado y atacar al Grimmsnarl."""
    fx = _fixture()

    promo = fx["contrafactual_promocion"]
    eleccion = m.agent(promo)
    banca = promo["current"]["players"][1]["bench"]
    subido = banca[promo["select"]["option"][eleccion[0]]["index"]]
    assert subido["id"] == OGERPON and len(subido["energies"]) == 4, subido

    ataque = fx["contrafactual_ataque"]
    assert ataque["current"]["players"][0]["active"][0]["id"] == GRIMMSNARL
    eleccion = m.agent(ataque)
    opcion = ataque["select"]["option"][eleccion[0]]
    assert opcion["type"] == int(m.OptionType.ATTACK), opcion


# ---------------------------------------------------------------------------
# La FRONTERA: la regla solo manda cuando el KO GANA la partida
# ---------------------------------------------------------------------------

def test_la_regla_no_depende_del_atacante_concreto():
    """El mismo tablero con un Tapu Bulu cargado (no-ex, otro ataque) en vez del
    Ogerpon: Wood Hammer 220 x2 por debilidad = 440 >= 310. Sigue siendo mate,
    asi que sigue mandando la retirada. La bandera se apoya en
    `_bench_attacker_can_ko`, que es generica."""
    fx = _fixture()
    decision = copy.deepcopy(fx["observation"])
    for p in decision["current"]["players"][1]["bench"]:
        if p["id"] == OGERPON and len(p["energies"]) == 4:
            p["id"] = m.Tapu_Bulu
            p["hp"] = p["maxHp"] = 140
            break
    else:
        pytest.fail("no se encontro el Ogerpon cargado en la banca")

    m.agent(fx["observacion_previa"])
    eleccion = m.agent(decision)
    assert eleccion == [_idx_de_tipo(decision, m.OptionType.RETREAT)], eleccion


def test_sin_rematador_en_banca_no_dispara():
    """FRONTERA: si ningun cuerpo de banca noquea al activo rival, retirar no
    cierra nada y el Boss's vuelve a ser la jugada."""
    fx = _fixture()
    decision = copy.deepcopy(fx["observation"])
    for p in decision["current"]["players"][1]["bench"]:
        if p["id"] == OGERPON and len(p["energies"]) == 4:
            p["energies"] = [1]
            p["energyCards"] = p["energyCards"][:1]
            break

    m.agent(fx["observacion_previa"])
    eleccion = m.agent(decision)
    # El contrato de la regla es "cerrar la partida retirando". Sin rematador no
    # cierra nada, asi que no debe secuestrar el turno; cual de los Supporters
    # NO vetados gana despues lo deciden otros scorers.
    assert eleccion != [_idx_de_tipo(decision, m.OptionType.RETREAT)], eleccion


def test_sin_match_point_el_gusteo_sigue_vivo():
    """Con TRES premios pendientes, el KO al activo (2 premios) ya no cierra la
    partida: el veto no dispara y Boss's Orders vuelve a ser jugable."""
    fx = _fixture()
    decision = copy.deepcopy(fx["observation"])
    decision["current"]["players"][1]["prize"] = [None, None, None]

    m.agent(fx["observacion_previa"])
    eleccion = m.agent(decision)

    assert eleccion != [_idx_de_tipo(decision, m.OptionType.RETREAT)], (
        f"sin match point la retirada no debe mandar, eligio {eleccion}")
    assert eleccion == [_idx_play_boss(decision)], (
        f"sin match point el gusteo debe seguir disponible, eligio {eleccion}")
