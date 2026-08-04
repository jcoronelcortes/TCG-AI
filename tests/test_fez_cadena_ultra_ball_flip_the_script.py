"""The chain Ultra Ball -> Fezandipiti ex -> Flip the Script gets COMPLETED.

Scenario (user, episode 88710543 registro_006 turn 6 vs Mega Lucario,
WON -- but by luck):

    US                                       OPPONENT
    active  Hydrapple ex 330 2e              active  Mega Lucario ex 340 2e
    bench   Meowth ex, Meganium, 2x          bench   2x Riolu, Lucario, Riolu
            Ogerpon ex
    prizes left: 3 - 4          (we were knocked out last turn: Flip the
                                 Script is ALIVE)

Recorded sequence (steps 86-104):

    Poke Pad -> Applin | Ultra Ball (discarding Meganium + Applin) -> **searches for
    Fezandipiti ex** | **Unfair Stamp** (shuffles the hand into the deck: the freshly
    dug Fezandipiti goes with it) | Bug Catching Set | play the Fezandipiti (which
    came back by LUCK among the Stamp's 5 cards) | Teal Dance | Ripening
    Charge | Teal Dance | attack.

Two mistakes, both with the same root: "a free play that dies with the
turn":

1. STEP 91 -- the Unfair Stamp SHUFFLED into the deck the Fezandipiti ex the Ultra
   Ball had just paid for with two cards (Meganium + Applin to the discard). Cause:
   a CIRCULAR BLOCK of three rules that are each correct on their own:
     * playing the Fezandipiti was vetoed by the Req H ORDERING veto
       (`_lucario_riolu_gust`: "vs Mega Lucario with a gustable Riolu, yield the
       play to the Boss's"),
     * the Boss's was vetoed by `cede_a_unfair_stamp` ("the Stamp first, since it
       shuffles the hand"),
     * and the Stamp stayed at 2000 through `mano_con_pokemon_o_evo` ("put the
       Pokemon in hand down first").
   The Stamp won by elimination and took into the deck the Fezandipiti AND the very
   Boss's that Req H was yielding the turn to.
   Fix: (a) the Req H veto EXEMPTS a Fezandipiti ex with its ability alive --
   it is a Pokemon, it does not consume the turn's Supporter, so it does not compete with the
   Boss's; and (b) `_ub_fez_pending`, sibling of `_ub_meowth_pending`: if the Ultra
   Ball CHOSE to search for Fezandipiti ex, the body GOES DOWN even if another veto kills it.

2. STEPS 95-102 -- Flip the Script was offered in FOUR menus and was never used:
   at 30000 it lost against Teal Dance (31300) and Ripening Charge (31100) menu
   after menu, and the turn closed by attacking. The 3-card draw is FREE, it is ONCE
   PER TURN and its condition (being knocked out) dies with the turn, whereas
   an attachment that does not finish can be made afterwards without losing anything. Besides, drawing
   FIRST decides the attachments better (the 3 cards may be Grass).
   Fix: `FEZ_DRAW_ABILITY_SCORE` = 31700 (above the whole family of non-lethal
   charges) + promotion to the ENERGY tier so that no charge overrides it by ORDER.

What does NOT change: the order Unfair Stamp / Lillie's -> the ability (the Stamp
would shuffle the 3 drawn cards away), the deck-out brake, the LETHAL bands of
Teal Dance / Ripening (41000+: the ability that enables TODAY's KO still comes
first) and the WINNING finisher (step 102: if the game closes this turn,
drawing 3 adds nothing).
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from state_builder import C, G, Escenario, pk

FEZ = m.Fezandipiti_ex          # 140: Flip the Script (draw 3)
HYDRA = m.Hydrapple_ex          # 150: Ripening Charge
OGERPON = m.Teal_Mask_Ogerpon_ex  # 96: Teal Dance
MEOWTH = m.Meowth_ex
MEGANIUM = m.Meganium
CHIKORITA = m.Chikorita
BAYLEEF = m.Bayleef
APPLIN = m.Applin
DIPPLIN = m.Dipplin
STAMP = m.Unfair_Stamp
LILLIE = m.Lillie_Determination
BOSS = m.Boss_Orders
DAWN = m.Dawn
GRASS = m.Basic_Grass_Energy

MEGA_LUCARIO = 678              # the opposing active of the record (340 HP)
RIOLU = m.Riolu

_FIX = ROOT / "tests" / "fixtures"
_FIX_STEP91 = _FIX / "fez_ub_baja_el_cuerpo_antes_del_stamp_step91.json"
_FIX_STEP95 = _FIX / "fez_flip_the_script_antes_de_cargar_energia_step95.json"
_FIX_STEP102 = _FIX / "fez_remate_ganador_sobre_flip_the_script_step102.json"
_REGISTRO = ROOT / "registros" / "registro_006_pasos_086_hasta_104.json"


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
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cartas_tracking()


def _obs(fixture):
    with open(fixture, encoding="utf-8") as f:
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
    if tipo == int(m.OptionType.ATTACH):
        return ("ATTACH", jugador["hand"][o["index"]]["id"])
    if tipo == int(m.OptionType.ATTACK):
        return ("ATTACK", o.get("attackId"))
    if tipo == int(m.OptionType.RETREAT):
        return ("RETREAT", None)
    if tipo == int(m.OptionType.END):
        return ("END", None)
    return (tipo, None)


def _jugadas(obs):
    return [_jugada(obs, [i]) for i in range(len(obs["select"]["option"]))]


def _menus_del_registro():
    """The menus of OUR seat (yourIndex 1) from the record, in order."""
    with open(_REGISTRO, encoding="utf-8") as f:
        data = json.load(f)
    return [e["observation"] for paso in data["steps"] for e in paso
            if e["status"] in ("ACTIVE", "DONE")
            and e["observation"]["current"]["yourIndex"] == 1]


# ---------------------------------------------------------------------------
# 1. Step 91: the body that paid for the Ultra Ball goes down BEFORE the Unfair Stamp
# ---------------------------------------------------------------------------

def test_paso91_baja_el_fezandipiti_antes_del_unfair_stamp():
    obs = _obs(_FIX_STEP91)
    jugadas = _jugadas(obs)
    # The real menu offered both plays in competition.
    assert ("PLAY", FEZ) in jugadas, jugadas
    assert ("PLAY", STAMP) in jugadas, jugadas
    assert _jugada(obs, m.agent(obs)) == ("PLAY", FEZ)


def test_paso91_el_bloqueo_circular_existe_de_verdad():
    """It documents the state that made it inevitable: a Boss's in hand unplayed
    (Req H active), a playable Unfair Stamp (we were knocked out) and room on the bench."""
    obs = _obs(_FIX_STEP91)
    st = m.to_observation_class(obs).current
    yo = st.players[st.yourIndex]
    mano = [c.id for c in yo.hand]
    assert mano.count(STAMP) == 1
    assert mano.count(BOSS) == 1
    assert mano.count(FEZ) == 1
    assert not st.supporterPlayed
    assert len(yo.bench) == 4                      # there is room for the Fez
    assert any(bp.id == RIOLU for bp in st.players[1 - st.yourIndex].bench)
    m.agent(obs)
    assert m.ko_last_turn is True                  # Flip the Script ALIVE


@pytest.mark.skipif(
    not _REGISTRO.exists(),
    reason=("necesita la SECUENCIA de menus del registro (episodio 88710543), "
            "que es dato local transitorio: `utils/split_turns.py` lo "
            "reescribe con cada partida nueva. COBERTURA YA RESTITUIDA en "
            "tests/test_fez_pending_sintetico.py, que fabrica la secuencia con "
            "el StateBuilder (y por tanto es inmune a la rotacion). Este test "
            "se conserva por si el episodio vuelve a estar en disco."))
def test_turno_completo_la_ultra_ball_deja_el_fezandipiti_pendiente():
    """End to end over the record: the Ultra Ball chooses Fezandipiti ex, that
    sets `_ub_fez_pending`, and the next menu PLAYS it (before, the
    Stamp was played and the body went back into the deck)."""
    menus = _menus_del_registro()
    elecciones = []
    for obs in menus[:6]:
        elecciones.append((obs["select"]["context"], m.agent(obs)))
    # menu 4 = the Ultra Ball's selection (TO_HAND context): it searches for Fezandipiti.
    ub = menus[4]
    idx = elecciones[4][1][0]
    assert ub["select"]["effect"]["id"] == m.Ultra_Ball
    assert ub["select"]["deck"][ub["select"]["option"][idx]["index"]]["id"] == FEZ
    assert m._ub_fez_pending is True
    # menu 5 = the next main menu: the body goes down.
    assert _jugada(menus[5], elecciones[5][1]) == ("PLAY", FEZ)


# ---------------------------------------------------------------------------
# 2. Steps 95-102: the ability is cashed in before spending the turn's energy
# ---------------------------------------------------------------------------

def test_paso95_flip_the_script_antes_de_teal_dance_y_ripening():
    obs = _obs(_FIX_STEP95)
    jugadas = _jugadas(obs)
    assert ("ABILITY", FEZ) in jugadas, jugadas
    assert ("ABILITY", OGERPON) in jugadas, jugadas     # Teal Dance
    assert ("ABILITY", HYDRA) in jugadas, jugadas       # Ripening Charge
    assert ("ATTACH", GRASS) in jugadas, jugadas
    assert _jugada(obs, m.agent(obs)) == ("ABILITY", FEZ)


def test_paso95_la_banda_esta_por_encima_de_las_cargas_no_letales():
    """The draw goes first by SCORE and by TIER: if it stayed in tier 0
    any promoted Teal Dance / Ripening would override it by ORDER."""
    assert m.FEZ_DRAW_ABILITY_SCORE > m.RIPEN_HEAL_ABILITY_SCORE
    assert m.FEZ_DRAW_ABILITY_SCORE > 31600      # the ceiling of the bench charges
    assert m.FEZ_DRAW_ABILITY_SCORE < 41000      # the LETHAL bands untouched


def test_paso102_el_remate_ganador_sigue_por_encima_del_robo():
    """The ONLY exception: with the game won this turn (3 prizes and the
    Syrup Storm knocks out the Mega Lucario ex) attacking comes first -- drawing 3
    changes nothing."""
    obs = _obs(_FIX_STEP102)
    jugadas = _jugadas(obs)
    assert ("ABILITY", FEZ) in jugadas, jugadas
    assert _jugada(obs, m.agent(obs)) == ("ATTACK", 195)


# ---------------------------------------------------------------------------
# 3. A synthetic generalisation
# ---------------------------------------------------------------------------

def _escenario_lucario(mano, con_ataque=True):
    """The board of step 91 rebuilt with the StateBuilder, with a parametric hand."""
    esc = (Escenario(turno=6, paso=91, tac=6)
           .mi_activo(pk(HYDRA, energias=[G, G], pre_evo=[APPLIN, DIPPLIN]))
           .mi_banca(MEOWTH, pk(MEGANIUM, pre_evo=[CHIKORITA, BAYLEEF]),
                     pk(OGERPON, energias=[G]), OGERPON)
           .mi_mano(*mano)
           .op_activo(pk(MEGA_LUCARIO, hp=340, max_hp=340, energias=[C, C],
                         pre_evo=[RIOLU]))
           .op_banca(RIOLU, RIOLU)
           .op_zonas(mano=6, mazo=23, premios=4)
           .menu_mano(con_ataque=con_ataque))
    obs = esc.construir()
    # Step 91 arrives after we were knocked out: it replicates the tracking.
    m.ko_last_turn = True
    m._ko_detected_this_turn = True
    m._prev_op_prize = 6
    return obs


def test_sintetico_req_h_ya_no_veta_el_fezandipiti_con_la_habilidad_viva():
    """With a Boss's in hand (Req H active) and a Riolu on the opposing bench, playing the
    Fezandipiti ex is NO longer vetoed: it does not consume the Supporter, so the Boss's is
    played afterwards anyway."""
    obs = _escenario_lucario([FEZ, BOSS])
    assert ("PLAY", FEZ) in _jugadas(obs)
    assert _jugada(obs, m.agent(obs)) == ("PLAY", FEZ)


def test_sintetico_req_h_sigue_vetando_el_desarrollo_normal():
    """The Req H veto has not been disabled: a development body (Chikorita)
    still yields the play to the Boss's."""
    obs = _escenario_lucario([CHIKORITA, BOSS])
    jugadas = _jugadas(obs)
    assert ("PLAY", CHIKORITA) in jugadas, jugadas
    assert _jugada(obs, m.agent(obs)) != ("PLAY", CHIKORITA)


def _escenario_teal_lillie(mano):
    """A board with ONE single Ogerpon ex in play: with Lillie's + Ogerpon ex +
    Grass in hand, `_fez_prefer_teal_lillie` switches on, which vetoes playing the
    Fezandipiti in order to prefer Teal + Teal Dance + Lillie's."""
    esc = (Escenario(turno=6, paso=91, tac=6)
           .mi_activo(pk(HYDRA, energias=[G, G], pre_evo=[APPLIN, DIPPLIN]))
           .mi_banca(MEOWTH, pk(MEGANIUM, pre_evo=[CHIKORITA, BAYLEEF]),
                     pk(OGERPON, energias=[G]))
           .mi_mano(*mano)
           .op_activo(pk(MEGA_LUCARIO, hp=340, max_hp=340, energias=[C, C],
                         pre_evo=[RIOLU]))
           .op_banca(RIOLU, RIOLU)
           .op_zonas(mano=6, mazo=23, premios=4)
           .menu_mano(con_ataque=True))
    obs = esc.construir()
    m.ko_last_turn = True
    m._ko_detected_this_turn = True
    m._prev_op_prize = 6
    return obs


def test_sintetico_ub_fez_pending_completa_la_busqueda_pagada():
    """`_fez_prefer_teal_lillie` (Lillie's + Ogerpon ex + Grass in hand) vetoes
    playing the Fezandipiti... unless the Ultra Ball has just paid for it."""
    obs = _escenario_teal_lillie([FEZ, LILLIE, OGERPON, GRASS])
    assert ("PLAY", FEZ) in _jugadas(obs)
    assert _jugada(obs, m.agent(obs)) != ("PLAY", FEZ)

    obs = _escenario_teal_lillie([FEZ, LILLIE, OGERPON, GRASS])
    m._ub_fez_pending = True
    assert _jugada(obs, m.agent(obs)) == ("PLAY", FEZ)


def test_sintetico_pending_no_rompe_los_limites_fisicos():
    """The override does not fill an already complete bench (a PHYSICAL limit)."""
    esc = (Escenario(turno=6, paso=91, tac=6)
           .mi_activo(pk(HYDRA, energias=[G, G], pre_evo=[APPLIN, DIPPLIN]))
           .mi_banca(MEOWTH, pk(MEGANIUM, pre_evo=[CHIKORITA, BAYLEEF]),
                     pk(OGERPON, energias=[G]), OGERPON, APPLIN)
           .mi_mano(FEZ, DAWN)
           .op_activo(pk(MEGA_LUCARIO, hp=340, max_hp=340, energias=[C, C],
                         pre_evo=[RIOLU]))
           .op_banca(RIOLU)
           .op_zonas(mano=6, mazo=23, premios=4)
           .menu_mano(con_ataque=True))
    obs = esc.construir()
    m.ko_last_turn = True
    m._ko_detected_this_turn = True
    m._prev_op_prize = 6
    m._ub_fez_pending = True
    assert len(obs["current"]["players"][0]["bench"]) == 5
    assert _jugada(obs, m.agent(obs)) != ("PLAY", FEZ)
