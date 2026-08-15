"""A veto that defers to a card the turn cannot play defers to nothing.

Scenario (`records/registro_014_pasos_051_hasta_051.json`, step 51, turn 14,
episode 93229766 vs **Budew / Dragapult** -- LOST):

    US (6 prizes)                          RIVAL (6 prizes)
    active  Chikorita 20/70, **0 e**       active  **Budew** 30/30
    bench   Applin 30/40, 0 e              bench   Fezandipiti ex 210
            Applin 40/40, 0 e                      Munkidori 110, Munkidori 110
            Teal Mask Ogerpon ex, **3 {G}**        Dreepy 70
            Teal Mask Ogerpon ex, **1 {G}**
    hand    Poke Pad, Chikorita, Night Stretcher, Xerosic's Machinations,
            Poke Pad, **Bug Catching Set**, **Meowth ex**, Fezandipiti ex

        [0] PLAY Chikorita       (2nd of the line: vetoed by the line cap)
        [1] PLAY Meowth ex
        [2] PLAY Fezandipiti ex
        [3] END                  <-- played

THE TURN IS FROZEN, AND ALL BY ITSELF. Their Budew declared *Itchy Pollen* last
turn, so no Item can be played: the two Poke Pad, the Night Stretcher and the
Bug Catching Set are all dead cards this turn. Their hand is empty, so the
Xerosic has no legal target and the engine does not even offer it. Our own
Chikorita is in front with no energy and a retreat cost of one, so it can
neither attack nor step aside -- and the Ogerpon ex holding **three** Grass,
one attachment short of nothing at all, is stranded on the bench behind it.

WHAT WAS LEFT, AND WHAT VETOED IT. The Meowth ex is the only card in hand that
does anything: *Last-Ditch Catch* searches the deck for a Supporter, the deck
still holds a Lillie's Determination, and at six prizes that Supporter draws
eight cards. The Meowth branch of `ptcg/turn/options/play.py` refused it with

    elif _bcs_playable_in_hand and bench_count >= 1:      # "play the Set first"
        score = SCORE_VETO

The Set could not be played. Four branches further down sits the rule written
for this exact board -- `_active_cant_attack_this_turn`, score 21800 -- and the
ladder never reached it. The turn ended with END, the eighth in a row without
an attack, and the Chikorita died two turns later with the game already gone.

THE READING, and it is one word long: **playable means playable THIS TURN**.
`_bcs_playable_in_hand` asked whether a Set was in hand and whether the deck
still held something for it to find, and never whether an Item could be played
at all. The other two consumers of the pair already asked it by hand
(`attach.py:291`, and `bug_catching_set.py` for `pp_playable_in_hand`), so the
lock now lives in the flag itself and every reader inherits it: the general rule
before its special case. `itchy_pollen_active` already collected all three
sources of the lock -- Budew, Galvantula ex's Fulgurite, and an opposing active
that locks Items -- so the correction is deck-agnostic by construction.

WHAT THIS TEST IS NOT ABOUT. Step 39 of the same game (turn 8) looks identical
and is not: **Team Rocket's Watchtower** was still in play, and it cancels the
abilities of {C} Pokemon, so benching the Meowth ex there would have fetched
nothing. The engine says so directly -- forced through `search_begin`, the menu
after the play is a bare END with no Last-Ditch prompt, while across ~200 Meowth
plays in the logs without that stadium the YES/NO prompt always appears. END was
right on turn 8 and wrong on turn 14, and the difference is the stadium our own
Forest of Vitality replaced on turn 12.
"""

import copy
import json
import sys
from collections import defaultdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import main as m  # noqa: E402
from golden_corpus import reset_agent  # noqa: E402
from recorded_deck import deck_of_record  # noqa: E402

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "locked_item_is_not_the_better_play_turn14.json")

BCS = m.Bug_Catching_Set
BUDEW = m.Budew
CHIKORITA = m.Chikorita
FEZ = m.Fezandipiti_ex
LILLIE = m.Lillie_Determination
MEOWTH = m.Meowth_ex
OGERPON = m.Teal_Mask_Ogerpon_ex
POKE_PAD = m.Poke_Pad
GRASS = m.Basic_Grass_Energy


@pytest.fixture(autouse=True)
def _reset():
    reset_agent(m)
    yield
    reset_agent(m)


def _obs():
    with open(_FIXTURE, encoding="utf-8") as f:
        return copy.deepcopy(json.load(f)["observation"])


def _play_idx(obs, card_id):
    cur = obs["current"]
    mano = cur["players"][cur["yourIndex"]]["hand"]
    for i, o in enumerate(obs["select"]["option"]):
        if o.get("type") == int(m.OptionType.PLAY) and mano[o["index"]]["id"] == card_id:
            return i
    raise AssertionError(f"no hay opcion de jugar {card_id}")


def _end_idx(obs):
    for i, o in enumerate(obs["select"]["option"]):
        if o.get("type") == int(m.OptionType.END):
            return i
    raise AssertionError("no hay opcion de END")


# ---------------------------------------------------------------------------
# 1. The board: the lock, and a turn that cannot attack behind it
# ---------------------------------------------------------------------------

def test_the_item_lock_is_on_and_the_hand_is_mostly_items():
    o = _obs()
    cur = o["current"]
    yo = cur["yourIndex"]
    mio = cur["players"][yo]

    # Their Budew attacked last turn: that log IS the lock, and it is the only
    # evidence of it -- Itchy Pollen leaves nothing on the board to read.
    ataques = [lg for lg in o["logs"]
               if lg.get("type") == int(m.LogType.ATTACK)
               and lg.get("playerIndex") != yo]
    assert [lg["cardId"] for lg in ataques] == [BUDEW]

    # Four of the eight cards in hand are Items, and every one of them is dead.
    mano = [c["id"] for c in mio["hand"]]
    assert mano.count(POKE_PAD) == 2 and BCS in mano
    assert MEOWTH in mano

    # The turn's own slots are untouched: this is not a turn that spent itself.
    assert not cur["supporterPlayed"] and not cur["energyAttached"]


def test_nothing_of_ours_can_attack_and_the_charged_body_cannot_come_up():
    o = _obs()
    cur = o["current"]
    yo = cur["yourIndex"]
    mio = cur["players"][yo]

    # The energy IS on the table -- three Grass on one Ogerpon ex -- and it is
    # unreachable: the Chikorita in front has nothing to pay its retreat with.
    assert mio["active"][0]["id"] == CHIKORITA
    assert not mio["active"][0]["energies"]
    assert m.RETREAT_COST.get(CHIKORITA, 1) >= 1
    cargados = sorted(len(p["energies"]) for p in mio["bench"] if p and p["energies"])
    assert cargados == [1, 3]
    assert not any(c["id"] == GRASS for c in mio["hand"])

    cls = m.to_observation_class(o).current
    manos = defaultdict(int)
    for c in mio["hand"]:
        manos[c["id"]] += 1
    campo = defaultdict(int)
    for p in (mio["active"] + mio["bench"]):
        if p:
            campo[p["id"]] += 1
    assert not m._a_body_can_attack_this_turn(cls.players[yo], cls, manos, campo)


# ---------------------------------------------------------------------------
# 2. The reading: the flag, and the decision it was holding down
# ---------------------------------------------------------------------------

def test_the_flag_does_not_call_a_locked_item_playable():
    """The predicate itself, not only the choice it produces."""
    caja = {}

    # `_bcs_playable_in_hand` is a local of `agent()`, so it is read where it is
    # consumed: the play ladder. Watching the CONTEXT that ladder is handed is
    # the closest the flag can be observed to the rule that uses it.
    # The dispatch table binds the scorers by VALUE at import
    # ([[from-import-liga-una-copia-no-una-vista]]), so the spy goes in the
    # table and not on the module the function was defined in.
    import ptcg.turn.scoring as scoring_mod
    from cg.api import OptionType

    orig_play = scoring_mod._TABLE[OptionType.PLAY]

    def spy(tc, o, score):
        caja.setdefault("bcs", tc._bcs_playable_in_hand)
        caja.setdefault("lock", tc.itchy_pollen_active)
        return orig_play(tc, o, score)

    scoring_mod._TABLE[OptionType.PLAY] = spy
    try:
        with deck_of_record():
            m.agent(_obs())
    finally:
        scoring_mod._TABLE[OptionType.PLAY] = orig_play

    assert caja.get("lock") is True, "el candado de objetos no se leyo en este tablero"
    assert caja.get("bcs") is False, (
        "el Bug Catching Set sigue contando como jugable con los objetos "
        "bloqueados: el veto del Meowth ex cede la ranura a una carta que el "
        "motor no aceptaria")


def test_the_only_playable_card_goes_down_instead_of_ending_the_turn():
    o = _obs()
    with deck_of_record():
        elegido = m.agent(o)
    assert elegido == [_play_idx(o, MEOWTH)], (
        "con los objetos bloqueados, la mano muerta y ningun cuerpo capaz de "
        "atacar, el Meowth ex es la unica carta que hace algo: su Last-Ditch "
        "Catch busca el Supporter que abre el turno siguiente")
    assert elegido != [_end_idx(o)]


def test_without_the_reading_the_recorded_end_comes_back():
    """The arm the measurements compare against: the flag off, the game's move."""
    o = _obs()
    original = m.AN_ITEM_UNDER_A_LOCK_IS_NOT_A_PLAYABLE_CARD
    m.AN_ITEM_UNDER_A_LOCK_IS_NOT_A_PLAYABLE_CARD = False
    try:
        with deck_of_record():
            assert m.agent(o) == [_end_idx(o)], (
                "sin la lectura el agente deberia reproducir el END de la "
                "partida; si ya no lo hace, este test mide otra cosa")
    finally:
        m.AN_ITEM_UNDER_A_LOCK_IS_NOT_A_PLAYABLE_CARD = original


# ---------------------------------------------------------------------------
# 3. The border: the same board one stadium earlier is NOT this rule
# ---------------------------------------------------------------------------

def test_the_lock_reading_does_not_touch_the_watchtower_turn():
    """Turn 8 of the same game: the Watchtower muted the Meowth, END was right.

    The two boards differ in one card, and a correction that could not tell them
    apart would be putting a 2-prize body down for an ability that does not fire.
    """
    ruta = ROOT / "records" / "registro_008_pasos_039_hasta_039.json"
    if not ruta.exists():                     # `records/` is local and transient
        pytest.skip("registro_008 no esta en records/ (datos locales)")
    with open(ruta, encoding="utf-8") as f:
        datos = json.load(f)
    obs = None
    for paso in datos["steps"]:
        for item in paso:
            ob = item["observation"]
            cur = ob.get("current") or {}
            if (cur.get("yourIndex") == 1 and ob.get("select")
                    and item["status"] == "ACTIVE"):
                obs = ob
                break
        if obs:
            break
    assert obs is not None
    assert obs["current"]["stadium"][0]["id"] == m.Team_Rockets_Watchtower
    with deck_of_record():
        assert m.agent(copy.deepcopy(obs)) == [_end_idx(obs)], (
            "con el Team Rocket's Watchtower en juego el Last-Ditch Catch no "
            "existe: bajar el Meowth ex solo regala un cuerpo de dos premios")
