"""Vs Crustle/Sylveon: if TODAY we knock out the immune wall, Boss's is NOT played.

Scenario (user, episode 88706549 registro_006 step 47 vs Crustle, LOST):

    US                                    RIVAL
    active  Tapu Bulu    20/140  4e       active  Crustle    170/170  2e
    bench   Meganium    160/160  0e       bench   Dwebble  x3
            Ogerpon ex  210/210  1e               Teal Mask Ogerpon ex 210 1e
            Dipplin      80/80   0e
            Ogerpon ex  210/210  0e
            Meowth ex   170/170  0e
    hand    Boss's Orders, Meowth ex, Ogerpon ex, Applin, Dipplin, 2x Ultra
            Ball, Unfair Stamp
    prizes left: 6 - 6

The agent played **Boss's Orders** to bring up the Teal Mask Ogerpon ex from their bench
and knock it out with Wood Hammer: 2 prizes (`gusteo_2_premios`, 6800) against the 1
prize of the Crustle. Arithmetically it gains a prize; strategically it loses the
game, because the Crustle stays on the table **unharmed**:

- *Mysterious Rock Inn* cancels ALL the damage from our Pokemon ex, and our
  deck is an ex deck (Ogerpon ex, Hydrapple ex, Meowth ex, Fezandipiti ex). Against the
  wall only the NON-ex bodies hit: Tapu Bulu and the Meganium line.
- The window to kill it is exactly the turn in which one of those bodies
  is CHARGED and ACTIVE, and it closes by itself: here Wood Hammer "also does 30
  damage to itself" and the 20 HP Tapu Bulu died in the same blow, whether we gusted
  or not. Changing target did not save the Tapu: it only saved the Crustle.

The user's rule: **vs Crustle or Sylveon, if we can defeat the wall, it is defeated
first; the other Pokemon (and their prizes) come afterwards.** It is implemented in two
pieces:

 1. `_ex_immune_wall_ko_ready` (computed alongside `win_via_boss_gust` /
    `gust_2prize_via_boss`): the rival active is in `EX_IMMUNE_IDS` and our
    active KNOCKS IT OUT this turn. The damage is measured with the central evaluator
    `_our_effective_damage`, which applies the *Sturdy* cap of Crustle 533
    (at full life it survives on 10 HP): there there is NO KO and the rule stays quiet.
 2. The rule `rematar_muro_inmune_antes_de_gustear` of `_REGLAS_BOSS_PLAY`,
    right below the WINNING gust: it vetoes playing Boss's. The flag also switches off
    `gust_2prize_via_boss`/`_deny_evo_via_boss`, which feed the
    Meowth ex -> Last-Ditch -> Boss's engine (digging the card is not worth it either).

Exceptions that still rule: `win_via_boss_gust` and `boss_win_via_bench`
(gusting WINS the game right now).
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

TAPU = m.Tapu_Bulu                 # 920: Wood Hammer 220 (-30 to itself)
OGERPON = m.Teal_Mask_Ogerpon_ex   # 96: a 2-prize ex, 210 HP
MEGANIUM = m.Meganium
MEOWTH = m.Meowth_ex
BOSS = m.Boss_Orders
ULTRA_BALL = m.Ultra_Ball

CRUSTLE = m.Crustle_Grass          # 345: Mysterious Rock Inn (cancels ex)
CRUSTLE_STURDY = m.Crustle_Fighting  # 533: on top of that it survives at full life
DWEBBLE = m.Dwebble_Grass

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "crustle_no_gustear_si_rematamos_el_muro_step47.json")


@pytest.fixture(autouse=True)
def reset_main_state():
    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._cards_prizes_identified = False
    m._cards_last_turn = -1
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
    m._init_cards_tracking()


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
# The real step 47
# ---------------------------------------------------------------------------

def test_paso47_ataca_al_crustle_en_vez_de_gustear():
    obs = _obs_fixture()
    # The fixture must offer BOTH plays for the test to discriminate.
    jugadas = [_jugada(obs, [i]) for i in range(len(obs["select"]["option"]))]
    assert ("PLAY", BOSS) in jugadas, jugadas
    assert ("ATTACK", 1326) in jugadas, jugadas

    assert _jugada(obs, m.agent(obs)) == ("ATTACK", 1326)


def test_paso47_el_muro_es_noqueable_y_la_bandera_lo_ve():
    """The core of the rule: Wood Hammer (220) kills the 170 HP Crustle."""
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
# Synthetic scenarios: the rule and its boundaries
# ---------------------------------------------------------------------------

def _escenario(op_activo=None, mi_activo=None, premios_propios=None,
               mano=(BOSS, ULTRA_BALL)):
    """A charged Tapu Bulu in front of the wall, with a 2-prize rival ex on their
    bench (the gust the agent preferred)."""
    op_activo = op_activo if op_activo is not None else pk(CRUSTLE)
    mi_activo = (mi_activo if mi_activo is not None
                 else pk(TAPU, energias=[G] * 4, fisicas=4))
    return (Escenario(turn=8, paso=47, energia_jugada=True,
                      premios_propios=premios_propios)
            .mi_activo(mi_activo)
            .mi_banca(pk(MEGANIUM), pk(MEOWTH))
            .mi_mano(*mano)
            .op_activo(op_activo)
            .op_banca(pk(OGERPON, energias=[G]), pk(DWEBBLE))
            .op_zonas(mano=6, mazo=30, prizes=6)
            .menu_mano(con_ataque=True)
            .construir())


def test_con_el_muro_noqueable_no_se_juega_boss():
    """The record's case synthetically: 2 prizes on the rival bench do NOT
    justify leaving alive the wall that cancels our whole deck."""
    obs = _escenario()
    accion, _ = _jugada(obs, m.agent(obs))
    assert accion == "ATTACK", _jugada(obs, m.agent(obs))


def test_frontera_activo_ex_el_gusteo_sigue_vivo():
    """With an Ogerpon ex active the wall is UNTOUCHABLE (0 damage): there is no
    window to protect and Boss's is the play again."""
    obs = _escenario(mi_activo=pk(OGERPON, energias=[G] * 6, fisicas=3))
    assert _jugada(obs, m.agent(obs)) == ("PLAY", BOSS)


def test_frontera_sturdy_sin_KO_el_gusteo_sigue_vivo():
    """Crustle 533 at FULL life survives on 10 HP (*Sturdy*): Wood Hammer does not
    knock it out, so there is no wall to finish and the 2-prize gust rules.
    That is why the flag is measured with `_our_effective_damage`."""
    obs = _escenario(op_activo=pk(CRUSTLE_STURDY))
    assert _jugada(obs, m.agent(obs)) == ("PLAY", BOSS)


def test_frontera_gusteo_ganador_manda_sobre_el_muro():
    """At 2 prizes, gusting the bench ex WINS the game on the spot: the
    finisher (`win_via_boss_gust`) still comes above the wall."""
    obs = _escenario(premios_propios=2)
    assert _jugada(obs, m.agent(obs)) == ("PLAY", BOSS)


# ---------------------------------------------------------------------------
# The pure scorer
# ---------------------------------------------------------------------------

def test_scorer_veta_boss_con_muro_noqueable():
    from test_main import _make_boss_ctx  # a shared helper of the scorer

    veto = m._score_boss_orders_play(
        _make_boss_ctx(op_is_crustle_deck=True, op_has_ex_immune_active=True,
                       gust_2prize_via_boss=True,
                       ex_immune_wall_ko_ready=True))
    assert veto == m.SCORE_VETO

    # Without the flag, the same context plays the 2-prize gust.
    sin_muro = m._score_boss_orders_play(
        _make_boss_ctx(op_is_crustle_deck=True, op_has_ex_immune_active=True,
                       gust_2prize_via_boss=True))
    assert sin_muro == m.BOSS_SCORE_GUST_2PRIZE

    # And the winning finisher does not yield to the wall.
    gana = m._score_boss_orders_play(
        _make_boss_ctx(op_is_crustle_deck=True, op_has_ex_immune_active=True,
                       win_via_boss_gust=True, ex_immune_wall_ko_ready=True))
    assert gana == m.BOSS_SCORE_WIN_NOW
