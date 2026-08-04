"""Flip the Script is not lost by closing the turn with an attack.

Scenario (user, episode 88710037 registro_006 step 78 vs Archaludon ex,
LOST):

    US                                      RIVAL
    active  Teal Mask Ogerpon ex 210 3e     active  Archaludon ex 400 3e
    bench   Bayleef, Meowth ex, 2x Applin,  bench   Duraludon 10, Duraludon 130,
            Fezandipiti ex (played on              Fezandipiti ex
            step 77 with the Ultra Ball)
    hand    Lillie's Determination, Boss's Orders, Bayleef
    prizes left: 6 - 4     (they knocked out our Ogerpon ex the previous turn)

The menu of step 78 offered FOUR plays: play Lillie's, play Boss's, the
**Flip the Script** ability of the just-played Fezandipiti ex (draw 3) and
attacking. The agent ATTACKED, closing the turn and throwing the draw away. The loss
is flat and unrecoverable: the ability is ONCE PER TURN and its activation
condition -- having a Pokemon knocked out on the previous turn -- goes away with the
turn. Playing the Fezandipiti ex with an Ultra Ball (a two-card cost) and not
cashing in its ability leaves the turn in the red.

Cause: a CIRCULAR BLOCK between three rules that are correct on their own.

  * the ability is vetoed by ORDER, "Lillie's Determination first and THEN the
    ability" (`_lillie_blocks_fez_ability`), so that Lillie's does not shuffle
    the 3 drawn cards back;
  * Lillie's vetoes itself by yielding to an executable Boss's
    (`cede_a_boss_ejecutable`, -1);
  * and Boss's is downgraded to 20 by yielding to Lillie's with no bench attacker
    (`sin_atacante_banca_cede_a_lillie`).

None of the three is played, the attack (1100) wins the menu and the ability dies.

Fix (agnostic to the rival deck: it only looks at our hand and the menu). The ORDER
vetoes on abilities are registered as DEFERRABLE in
`_ability_order_veto` and the "REVOKE ORDER VETOES" block lifts them when the
"X first" is not going to happen:

  (a) no blocker is offered and playable (score > 0) in this menu -- with no playable
      X there is no "after X". That is the case of step 78;
  (b) the blocker is alive but LOSES against attacking/passing and no other
      play is left alive -- the turn closes in this very action.

With the blocker playable and more plays alive the veto is kept: the blocker is
played first and, on leaving the hand, the veto switches itself off.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from parcheo import instalar
from state_builder import C, G, Escenario, pk

OGERPON = m.Teal_Mask_Ogerpon_ex    # 96: the active of step 78
FEZ = m.Fezandipiti_ex              # 140: Flip the Script (draw 3)
MEOWTH = m.Meowth_ex
BAYLEEF = m.Bayleef
APPLIN = m.Applin
LILLIE = m.Lillie_Determination     # blocker (Supporter)
STAMP = m.Unfair_Stamp              # blocker (Item)
BOSS = m.Boss_Orders
TAPU = m.Tapu_Bulu

ARCHALUDON = 190                    # the rival active of the record (400 HP)
DURALUDON = 169

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "fez_flip_the_script_antes_de_atacar_step78.json")


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
    """('PLAY'|'ABILITY', card_id) / ('ATTACK', attackId) / ('END', None)."""
    o = obs["select"]["option"][eleccion[0]]
    tipo = o["type"]
    yo = obs["current"]["yourIndex"]
    jugador = obs["current"]["players"][yo]
    if tipo == int(m.OptionType.PLAY):
        return ("PLAY", jugador["hand"][o["index"]]["id"])
    if tipo == int(m.OptionType.ABILITY):
        zona = (jugador["active"] if o["area"] == int(m.AreaType.ACTIVE)
                else jugador["bench"])
        return ("ABILITY", zona[o["index"]]["id"])
    if tipo == int(m.OptionType.ATTACK):
        return ("ATTACK", o.get("attackId"))
    if tipo == int(m.OptionType.RETREAT):
        return ("RETREAT", None)
    if tipo == int(m.OptionType.END):
        return ("END", None)
    return (tipo, None)


def _jugadas(obs):
    return [_jugada(obs, [i])
            for i in range(len(obs["select"]["option"]))]


# ---------------------------------------------------------------------------
# The real step 78
# ---------------------------------------------------------------------------

def test_paso78_usa_flip_the_script_en_vez_de_atacar():
    obs = _obs_fixture()
    # The fixture must offer the THREE plays for the test to discriminate.
    jugadas = _jugadas(obs)
    assert ("ABILITY", FEZ) in jugadas, jugadas
    assert ("ATTACK", 120) in jugadas, jugadas
    assert ("PLAY", LILLIE) in jugadas, jugadas

    assert _jugada(obs, m.agent(obs)) == ("ABILITY", FEZ)


def test_paso78_el_bloqueo_circular_existe_de_verdad():
    """Documents the state that made the mistake inevitable: the ability's
    blocker (Lillie's) is in hand and offered, but is NOT playable."""
    obs = _obs_fixture()
    st = m.to_observation_class(obs).current
    mano = [c.id for c in st.players[0].hand]
    assert mano.count(LILLIE) == 1
    assert mano.count(BOSS) == 1
    assert not st.supporterPlayed          # => _lillie_blocks_fez_ability active
    assert st.players[0].deckCount > 4     # => the deck-out brake does NOT apply

    # Lillie's yields to Boss's and Boss's yields to Lillie's: neither is played.
    eleccion = m.agent(obs)
    assert _jugada(obs, eleccion)[0] != "PLAY"


def test_paso78_la_ventana_exacta_del_bloqueo_circular():
    """Pins the ctx window in which the two rules yield the turn to each other, so
    that a future change in `cede_a_boss_ejecutable` / `_boss_cede_dig` does not
    move it unnoticed: no bench attacker ready, a gustable pre-evo THREAT
    and an active doomed ONLY according to `attack_table`.

    Closing the asymmetry (making `cede_a_boss_ejecutable` also look at
    `active_doomed_real`, as `_boss_cede_dig` does) was MEASURED and came out at -0.39
    points with n=7000 per branch across 4 matchups; see the rule's comment in
    main.py. Here the turn is rescued by the deferrable ORDER veto: with no playable
    blocker, Flip the Script cashes in the draw of 3."""
    obs = _obs_fixture()
    visto = {}
    orig = m._score_boss_orders_play

    def espia(ctx):
        visto["ctx"] = ctx
        return orig(ctx)

    _rest_score_boss_orders_play = instalar("_score_boss_orders_play", espia)
    try:
        m.agent(obs)
    finally:
        _rest_score_boss_orders_play()
    ctx = visto["ctx"]
    assert ctx.has_ready_bench_attacker is False
    assert ctx.boss_ko_threat_preevo is True
    assert ctx.active_ko_likely is False     # the BLIND heuristic
    assert ctx.active_doomed_real is True    # the REAL finisher from attack_table
    # The asymmetry live: Lillie's vetoes itself, Boss's is downgraded to the
    # yielding band. Neither of the two is played.
    assert m._score_lillie_determination_play(ctx) == m.SCORE_VETO
    assert m._score_boss_orders_play(ctx) == m.BOSS_SCORE_EMPTY_GUST


def test_paso78_la_habilidad_se_usa_antes_de_cualquier_cierre_de_turno():
    """The menu trimmed to ability + attack + pass: the turn is never closed
    with Flip the Script available."""
    obs = _obs_fixture()
    opciones = obs["select"]["option"]
    idx = [i for i, o in enumerate(opciones)
           if o["type"] in (int(m.OptionType.ABILITY),
                            int(m.OptionType.ATTACK),
                            int(m.OptionType.END))]
    obs["select"]["option"] = [opciones[i] for i in idx]
    assert _jugada(obs, m.agent(obs)) == ("ABILITY", FEZ)


# ---------------------------------------------------------------------------
# A synthetic generalisation: the requested ORDER is still alive
# ---------------------------------------------------------------------------

def _escenario(mano, con_ataque=True):
    """The board of step 78 rebuilt with the StateBuilder, with a parametric hand.

    The ABILITY option of the benched Fezandipiti ex (slot 4) is added by hand, which
    `menu_mano` does not emit, right before the turn-closing options.
    """
    esc = (Escenario(turno=6, paso=78, tac=7)
           .mi_activo(pk(OGERPON, energias=[G, G, G]))
           .mi_banca(pk(BAYLEEF, pre_evo=[m.Chikorita]), MEOWTH, APPLIN,
                     APPLIN, pk(FEZ, aparecio=True))
           .mi_mano(*mano)
           .mi_descarte(m.Ultra_Ball, m.Ultra_Ball, m.Lanas_Aid,
                        m.Basic_Grass_Energy, m.Basic_Grass_Energy,
                        m.Basic_Grass_Energy, OGERPON)
           .op_activo(pk(ARCHALUDON, hp=400, max_hp=400, energias=[C, C, C],
                         pre_evo=[DURALUDON]))
           .op_banca(pk(DURALUDON, hp=130, max_hp=130, energias=[C, C, C]))
           .op_zonas(mano=9, mazo=23, prizes=4)
           .menu_mano(con_ataque=con_ataque))
    obs = esc.construir()
    opciones = obs["select"]["option"]
    n_play = sum(1 for o in opciones if o["type"] == int(m.OptionType.PLAY))
    opciones.insert(n_play, {"type": int(m.OptionType.ABILITY),
                             "area": int(m.AreaType.BENCH), "index": 4})
    return obs


def _con_ko_previo(obs):
    """Step 78 comes after we were knocked out: it replicates the tracking
    state that leaves `ko_last_turn` switched on."""
    m.ko_last_turn = True
    m._ko_detected_this_turn = True
    m._prev_op_prize = 6
    return obs


def test_sintetico_sin_bloqueador_usa_la_habilidad():
    """Case (a) in its simplest form: with no Lillie's or Stamp in hand the
    ability is cashed in before attacking."""
    obs = _con_ko_previo(_escenario([BOSS]))
    assert ("ABILITY", FEZ) in _jugadas(obs)
    assert _jugada(obs, m.agent(obs)) == ("ABILITY", FEZ)


def test_sintetico_unfair_stamp_jugable_manda_primero():
    """The requested order is NOT broken: with a playable Unfair Stamp and another live play
    (Boss's) the Stamp goes first and the ability waits for the next menu -- if
    not, the Stamp would shuffle the 3 drawn cards back."""
    obs = _con_ko_previo(_escenario([STAMP, BOSS]))
    jugadas = _jugadas(obs)
    assert ("PLAY", STAMP) in jugadas, jugadas
    assert ("ABILITY", FEZ) in jugadas, jugadas
    assert _jugada(obs, m.agent(obs)) == ("PLAY", STAMP)


def test_sintetico_lillie_jugable_manda_primero():
    """The same order with the other blocker: Lillie's Determination before the
    ability when Lillie's IS playable."""
    obs = _con_ko_previo(_escenario([LILLIE]))
    jugadas = _jugadas(obs)
    assert ("PLAY", LILLIE) in jugadas, jugadas
    assert _jugada(obs, m.agent(obs)) == ("PLAY", LILLIE)


def test_sintetico_deck_out_sigue_vetando_la_habilidad():
    """The deck-out brake is a VALUE veto, not an ORDER one: the revocation does not
    lift it even with a hand free of blockers."""
    esc = (Escenario(turno=6, paso=78, tac=7)
           .mi_activo(pk(OGERPON, energias=[G, G, G]))
           .mi_banca(pk(FEZ, aparecio=True))
           .mi_mano(BOSS)
           .mazo(TAPU, MEOWTH, APPLIN)          # deckCount = 3 (<= 4)
           .resto_al_descarte()
           .op_activo(pk(ARCHALUDON, hp=400, max_hp=400, energias=[C, C, C],
                         pre_evo=[DURALUDON]))
           .op_zonas(mano=5, mazo=20, prizes=4)
           .menu_mano(con_ataque=True))
    obs = esc.construir()
    opciones = obs["select"]["option"]
    n_play = sum(1 for o in opciones if o["type"] == int(m.OptionType.PLAY))
    opciones.insert(n_play, {"type": int(m.OptionType.ABILITY),
                             "area": int(m.AreaType.BENCH), "index": 0})
    _con_ko_previo(obs)
    assert obs["current"]["players"][0]["deckCount"] <= 4
    assert ("ABILITY", FEZ) in _jugadas(obs)
    assert _jugada(obs, m.agent(obs)) != ("ABILITY", FEZ)
