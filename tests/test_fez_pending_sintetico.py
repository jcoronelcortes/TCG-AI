"""The handover of `_ub_fez_pending` BETWEEN menus, rebuilt with the StateBuilder.

It covers the only thing that went dormant when the local records rotated: the chain
**Ultra Ball → Fezandipiti ex → playing it**, which by definition needs TWO consecutive
menus and therefore does not fit in a single-observation fixture.

The original test (`test_fez_cadena_ultra_ball_flip_the_script.py`) reproduced that
sequence from `registros/registro_006_pasos_086_hasta_104.json`. The records
are transient local data —`utils/split_turns.py` rewrites them with every
new game— and episode 88710543 is no longer in `registros/` or in
`log/`, so that test ended up in `skipif`. Here the sequence is FABRICATED, which
also makes it immune to the next rotation.

Scenario (the same shape as registro_006 steps 90-91 vs Mega Lucario):

    US                                        OPPONENT
    active  Hydrapple ex, 2 {G}               active  Mega Lucario ex 340/340
    bench   Meowth ex, Meganium,              bench   Riolu
            Teal Mask Ogerpon ex x2
    We were knocked out last turn -> Flip the Script ALIVE.

**Menu A** — the Ultra Ball is played and the fetch chooses **Fezandipiti ex**: that
arms `_ub_fez_pending`, the mark of "this search is ALREADY paid for".

**Menu B** — the next MAIN, with the hand reduced to **Unfair Stamp +
Fezandipiti ex**: the original bug was that the Stamp was played first and shuffled
the freshly dug Fezandipiti back into the deck, with the Ultra Ball already paid for.

**A finding while rebuilding it:** with `_ub_fez_pending` switched off by hand, the Fezandipiti
is played ANYWAY. The chain has TWO independent defences and the first one is enough in
every state that can be built:

  1. `_us_pokemon_jugable`, inside the Stamp's own scorer: with a PLAYABLE Pokémon
     in hand (here the Fez), the Stamp falls to its low band (**2000**)
     instead of the high one (**7500** = "the hand has nothing better to do"), and
     for that reason alone it loses against playing the body.
  2. `_ub_fez_pending` (22000, applied AFTER all the branch's vetoes —
     which are precisely the ones that contradict an already paid-for search):
     the net for when some ORDERING veto knocks the PLAY down.

That is why the control is NOT "without the flag the Stamp wins" (that would be false):
what is pinned is the Stamp's BAND, which is observable and does discriminate —
2000 with the Fez playable, 7500 with the bench full, where the Fez can no longer be played.

A note on state: `ko_last_turn` cannot be injected directly (`agent()` recomputes it
from `_ko_detected_this_turn` and the logs), and it is reset when a turn change is detected.
`pre_turn` is set to the current turn so that reset does not
fire, just as with `_grass_attaches_this_turn` in the Cruel Arrow test.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main as m
from parcheo import instalar
from state_builder import Escenario, pk, G

FEZ = m.Fezandipiti_ex
STAMP = m.Unfair_Stamp
HYDRA = m.Hydrapple_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
MEOWTH = m.Meowth_ex
MEGANIUM = m.Meganium
APPLIN = m.Applin
DIPPLIN = m.Dipplin
CHIKORITA = m.Chikorita
BAYLEEF = m.Bayleef
MEGA_LUCARIO = 678
RIOLU = m.Riolu

TURNO = 6


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
    m._grass_attaches_this_turn = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cartas_tracking()


def _armar_turno():
    """Leaves the turn state as if the opponent had knocked us out: Flip the
    Script alive and without `agent()` resetting the turn at the first menu."""
    m.pre_turn = TURNO
    m._ko_detected_this_turn = True


def _campo(esc, banca_llena=False):
    """The board common to both menus."""
    extra = (m.Tapu_Bulu,) if banca_llena else ()
    return (esc
            .mi_activo(pk(HYDRA, energias=[G, G], fisicas=2,
                          pre_evo=[APPLIN, DIPPLIN]))
            .mi_banca(MEOWTH,
                      pk(MEGANIUM, pre_evo=[CHIKORITA, BAYLEEF]),
                      pk(OGERPON, energias=[G, G, G, G], fisicas=4),
                      OGERPON, *extra)
            .op_activo(pk(MEGA_LUCARIO, hp=340, max_hp=340))
            .op_banca(RIOLU)
            .op_zonas(mano=5, mazo=30, premios=4))


def _menu_fetch():
    """Menu A: the Ultra Ball fetch, with a Fezandipiti ex in the deck."""
    esc = Escenario(turno=TURNO, paso=90, tac=5, premios_propios=3)
    return (_campo(esc)
            .mi_mano(STAMP)
            .mazo(FEZ, CHIKORITA, APPLIN)
            # `fetch_ultra_ball()` consumes an Ultra Ball from the pool (the card "in
            # effect"), so it goes BEFORE `resto_al_descarte()`, which takes
            # everything left over. The other way round, the builder's strict
            # accounting runs out of copies and aborts.
            .fetch_ultra_ball()
            .resto_al_descarte()
            .construir())


def _menu_bajar(banca_llena=False):
    """Menu B: the next MAIN. A THIN hand (Stamp + Fez) so the Stamp
    scores in its high band and the test really discriminates."""
    esc = Escenario(turno=TURNO, paso=91, tac=6, premios_propios=3)
    return (_campo(esc, banca_llena=banca_llena)
            .mi_mano(STAMP, FEZ)
            .mazo(CHIKORITA, APPLIN)      # `resto_al_descarte()` requires it
            .resto_al_descarte()
            .menu_mano()
            .construir())


def _jugada(obs, eleccion):
    o = obs["select"]["option"][eleccion[0]]
    if o["type"] == int(m.OptionType.PLAY):
        yo = obs["current"]["yourIndex"]
        return ("PLAY", obs["current"]["players"][yo]["hand"][o["index"]]["id"])
    if o["type"] == int(m.OptionType.CARD):
        return ("CARTA", obs["select"]["deck"][o["index"]]["id"])
    return (o["type"], None)


# ---------------------------------------------------------------------------
# 1. The scenario: without these conditions the chain does not exist
# ---------------------------------------------------------------------------

def test_el_escenario_tiene_flip_the_script_viva_y_hueco_en_banca():
    _armar_turno()
    obs = _menu_fetch()
    m.agent(obs)
    assert m.ko_last_turn is True                 # Flip the Script's condition
    yo = obs["current"]["yourIndex"]
    mio = obs["current"]["players"][yo]
    assert len([b for b in mio["bench"] if b]) < 5          # the Fez fits
    assert not any(b and b["id"] == FEZ for b in mio["bench"])
    assert any(o["type"] == int(m.OptionType.CARD)
               for o in obs["select"]["option"])


# ---------------------------------------------------------------------------
# 2. The chain, menu by menu
# ---------------------------------------------------------------------------

def test_menuA_la_ultra_ball_busca_el_fezandipiti_y_arma_el_pendiente():
    _armar_turno()
    obs = _menu_fetch()
    assert _jugada(obs, m.agent(obs)) == ("CARTA", FEZ)
    assert m._ub_fez_pending is True


def test_menuB_el_cuerpo_pagado_baja_antes_que_el_sello():
    _armar_turno()
    m.agent(_menu_fetch())                # it arms `_ub_fez_pending`
    obs = _menu_bajar()
    assert _jugada(obs, m.agent(obs)) == ("PLAY", FEZ)


# ---------------------------------------------------------------------------
# 3. The chain's TWO defences
# ---------------------------------------------------------------------------
# While rebuilding the scenario something the record's test could not distinguish
# was verified: with `_ub_fez_pending` switched off by hand, the Fezandipiti is played
# ANYWAY. The chain is protected by two independent mechanisms and the first one is
# enough in the reachable states:
#
#   1) `_us_pokemon_jugable` inside the Stamp's scorer: with a PLAYABLE
#      Pokémon in hand (here the Fez itself), the Stamp falls to its low band
#      (2000) instead of the high one (7500 = "the hand has nothing better to
#      do"). For that reason alone it already loses against playing the body.
#   2) `_ub_fez_pending` (22000, after all the branch's vetoes): the
#      safety net for when some ORDERING veto knocks the PLAY down.
#
# That is why the control canNOT be "without the flag the Stamp wins": it would be false. What
# can be pinned —and what really protects the chain— is the Stamp's
# band, which is observable and does discriminate.

def test_el_sello_cede_al_cuerpo_jugable_y_esa_es_la_primera_defensa():
    """The first line: with the Fez PLAYABLE the Stamp scores in the low band."""
    _armar_turno()
    m._ub_fez_pending = False
    assert _score_del_sello(_menu_bajar()) == 2000


def test_con_la_banca_llena_el_sello_recupera_su_banda_alta():
    """A counterfactual proving the 2000 is caused by the playable body and not
    by something else: with the bench at 5 the Fez can no longer be played, the hand is left
    with nothing to do and the Stamp rises to its default (7500)."""
    _armar_turno()
    m._ub_fez_pending = False
    assert _score_del_sello(_menu_bajar(banca_llena=True)) == 7500


def _score_del_sello(obs):
    visto = {}
    orig = m._score_unfair_stamp_play

    def espia(ctx):
        r = orig(ctx)
        visto.setdefault("s", r)
        return r

    _rest_score_unfair_stamp_play = instalar("_score_unfair_stamp_play", espia)
    try:
        m.agent(obs)
    finally:
        _rest_score_unfair_stamp_play()
    return visto.get("s")
