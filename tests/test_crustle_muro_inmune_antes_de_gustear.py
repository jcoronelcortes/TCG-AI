"""Vs Crustle/Sylveon: si HOY noqueamos el muro inmune, NO se juega Boss's.

Escenario (user, episodio 88706549 registro_006 paso 47 vs Crustle, PERDIDA):

    NOSOTROS                              RIVAL
    activo  Tapu Bulu    20/140  4e       activo  Crustle    170/170  2e
    banca   Meganium    160/160  0e       banca   Dwebble  x3
            Ogerpon ex  210/210  1e               Teal Mask Ogerpon ex 210 1e
            Dipplin      80/80   0e
            Ogerpon ex  210/210  0e
            Meowth ex   170/170  0e
    mano    Boss's Orders, Meowth ex, Ogerpon ex, Applin, Dipplin, 2x Ultra
            Ball, Unfair Stamp
    premios restantes: 6 - 6

El agente jugo **Boss's Orders** para subir el Teal Mask Ogerpon ex de su banca
y noquearlo con Wood Hammer: 2 premios (`gusteo_2_premios`, 6800) contra el 1
premio del Crustle. Aritmeticamente gana un premio; estrategicamente pierde la
partida, porque el Crustle se queda en mesa **sano**:

- *Mysterious Rock Inn* anula TODO el dano de nuestros Pokemon ex, y nuestro
  mazo es ex (Ogerpon ex, Hydrapple ex, Meowth ex, Fezandipiti ex). Contra el
  muro solo pegan los cuerpos NO-ex: Tapu Bulu y la linea Meganium.
- La ventana para matarlo es exactamente el turno en el que uno de esos cuerpos
  esta CARGADO y de ACTIVO, y se cierra sola: aqui Wood Hammer "also does 30
  damage to itself" y el Tapu Bulu de 20 PV moria en el mismo golpe, gustearas
  o no. Cambiar de objetivo no salvo al Tapu: solo salvo al Crustle.

Regla del user: **vs Crustle o Sylveon, si podemos derrotar al muro, se derrota
primero; los otros Pokemon (y sus premios) van despues.** Se implementa en dos
piezas:

 1. `_ex_immune_wall_ko_ready` (calculado junto a `win_via_boss_gust` /
    `gust_2prize_via_boss`): el activo rival esta en `EX_IMMUNE_IDS` y nuestro
    activo lo NOQUEA este turno. El dano se mide con el evaluador central
    `_our_effective_damage`, que aplica el tope de *Sturdy* del Crustle 533
    (a vida completa sobrevive a 10 PV): ahi NO hay KO y la regla calla.
 2. La regla `rematar_muro_inmune_antes_de_gustear` de `_REGLAS_BOSS_PLAY`,
    justo debajo del gusteo GANADOR: veta jugar Boss's. La bandera apaga
    ademas `gust_2prize_via_boss`/`_deny_evo_via_boss`, que alimentan el motor
    Meowth ex -> Last-Ditch -> Boss's (no vale la pena cavar la carta tampoco).

Excepciones que siguen mandando: `win_via_boss_gust` y `boss_win_via_bench`
(gustear GANA la partida ya mismo).
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import G, Escenario, pk

TAPU = m.Tapu_Bulu                 # 920: Wood Hammer 220 (-30 a si mismo)
OGERPON = m.Teal_Mask_Ogerpon_ex   # 96: ex de 2 premios, 210 PV
MEGANIUM = m.Meganium
MEOWTH = m.Meowth_ex
BOSS = m.Boss_Orders
ULTRA_BALL = m.Ultra_Ball

CRUSTLE = m.Crustle_Grass          # 345: Mysterious Rock Inn (anula ex)
CRUSTLE_STURDY = m.Crustle_Fighting  # 533: ademas sobrevive a vida completa
DWEBBLE = m.Dwebble_Grass

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "crustle_no_gustear_si_rematamos_el_muro_step47.json")


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
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cartas_tracking()


def _obs_fixture():
    with open(_FIXTURE, encoding="utf-8") as f:
        return json.load(f)["observation"]


def _jugada(obs, eleccion):
    """('PLAY', card_id) / ('ATTACK', attackId) / ('RETREAT'|'END', None)."""
    o = obs["select"]["option"][eleccion[0]]
    tipo = o["type"]
    mano = obs["current"]["players"][obs["current"]["yourIndex"]]["hand"]
    if tipo == int(m.OptionType.PLAY):
        return ("PLAY", mano[o["index"]]["id"])
    if tipo == int(m.OptionType.ATTACK):
        return ("ATTACK", o.get("attackId"))
    if tipo == int(m.OptionType.RETREAT):
        return ("RETREAT", None)
    if tipo == int(m.OptionType.END):
        return ("END", None)
    return (tipo, None)


# ---------------------------------------------------------------------------
# El paso 47 real
# ---------------------------------------------------------------------------

def test_paso47_ataca_al_crustle_en_vez_de_gustear():
    obs = _obs_fixture()
    # El fixture debe ofrecer AMBAS jugadas para que el test discrimine.
    jugadas = [_jugada(obs, [i]) for i in range(len(obs["select"]["option"]))]
    assert ("PLAY", BOSS) in jugadas, jugadas
    assert ("ATTACK", 1326) in jugadas, jugadas

    assert _jugada(obs, m.agent(obs)) == ("ATTACK", 1326)


def test_paso47_el_muro_es_noqueable_y_la_bandera_lo_ve():
    """El nucleo de la regla: Wood Hammer (220) mata al Crustle de 170 PV."""
    obs = _obs_fixture()
    st = m.to_observation_class(obs).current
    tapu, crustle = st.players[0].active[0], st.players[1].active[0]
    assert crustle.id in m.EX_IMMUNE_IDS
    eff = len(tapu.energies)
    dmg = m._our_effective_damage(
        tapu, crustle,
        m._attacker_base_damage(tapu.id, crustle, eff, grass_scale=eff,
                                teal_self_energy=eff, bench_count=5))
    assert dmg >= (crustle.hp or 0), f"dano {dmg} vs {crustle.hp} PV"


# ---------------------------------------------------------------------------
# Escenarios sinteticos: la regla y sus fronteras
# ---------------------------------------------------------------------------

def _escenario(op_activo=None, mi_activo=None, premios_propios=None,
               mano=(BOSS, ULTRA_BALL)):
    """Tapu Bulu cargado delante del muro, con un ex rival de 2 premios en su
    banca (el gusteo que el agente prefería)."""
    op_activo = op_activo if op_activo is not None else pk(CRUSTLE)
    mi_activo = (mi_activo if mi_activo is not None
                 else pk(TAPU, energias=[G] * 4, fisicas=4))
    return (Escenario(turno=8, paso=47, energia_jugada=True,
                      premios_propios=premios_propios)
            .mi_activo(mi_activo)
            .mi_banca(pk(MEGANIUM), pk(MEOWTH))
            .mi_mano(*mano)
            .op_activo(op_activo)
            .op_banca(pk(OGERPON, energias=[G]), pk(DWEBBLE))
            .op_zonas(mano=6, mazo=30, premios=6)
            .menu_mano(con_ataque=True)
            .construir())


def test_con_el_muro_noqueable_no_se_juega_boss():
    """El caso del registro en sintetico: 2 premios en la banca rival NO
    justifican dejar vivo al muro que anula todo nuestro mazo."""
    obs = _escenario()
    accion, _ = _jugada(obs, m.agent(obs))
    assert accion == "ATTACK", _jugada(obs, m.agent(obs))


def test_frontera_activo_ex_el_gusteo_sigue_vivo():
    """Con un Ogerpon ex de activo el muro es INTOCABLE (dano 0): no hay
    ventana que proteger y Boss's vuelve a ser la jugada."""
    obs = _escenario(mi_activo=pk(OGERPON, energias=[G] * 6, fisicas=3))
    assert _jugada(obs, m.agent(obs)) == ("PLAY", BOSS)


def test_frontera_sturdy_sin_KO_el_gusteo_sigue_vivo():
    """Crustle 533 a vida COMPLETA sobrevive a 10 PV (*Sturdy*): Wood Hammer no
    lo noquea, asi que no hay muro que rematar y el gusteo de 2 premios manda.
    Es la razon por la que la bandera se mide con `_our_effective_damage`."""
    obs = _escenario(op_activo=pk(CRUSTLE_STURDY))
    assert _jugada(obs, m.agent(obs)) == ("PLAY", BOSS)


def test_frontera_gusteo_ganador_manda_sobre_el_muro():
    """A 2 premios, gustear el ex de banca GANA la partida en el acto: el
    remate (`win_via_boss_gust`) sigue por encima del muro."""
    obs = _escenario(premios_propios=2)
    assert _jugada(obs, m.agent(obs)) == ("PLAY", BOSS)


# ---------------------------------------------------------------------------
# El scorer puro
# ---------------------------------------------------------------------------

def test_scorer_veta_boss_con_muro_noqueable():
    from test_main import _make_boss_ctx  # helper compartido del scorer

    veto = m._score_boss_orders_play(
        _make_boss_ctx(op_is_crustle_deck=True, op_has_ex_immune_active=True,
                       gust_2prize_via_boss=True,
                       ex_immune_wall_ko_ready=True))
    assert veto == m.SCORE_VETO

    # Sin la bandera, el mismo contexto juega el gusteo de 2 premios.
    sin_muro = m._score_boss_orders_play(
        _make_boss_ctx(op_is_crustle_deck=True, op_has_ex_immune_active=True,
                       gust_2prize_via_boss=True))
    assert sin_muro == m.BOSS_SCORE_GUST_2PRIZE

    # Y el remate ganador no cede al muro.
    gana = m._score_boss_orders_play(
        _make_boss_ctx(op_is_crustle_deck=True, op_has_ex_immune_active=True,
                       win_via_boss_gust=True, ex_immune_wall_ko_ready=True))
    assert gana == m.BOSS_SCORE_WIN_NOW
