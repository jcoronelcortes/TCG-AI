"""Unfair Stamp: it is only played if it DISRUPTS or if the REFRESH comes cheap.

Scenario (`records/registro_006_pasos_085_hasta_108.json`, episode 89215128,
step 99, turn 6 vs Marnie's Grimmsnarl, WON):

    US                                        RIVAL
    active  Hydrapple ex 260/330              active  Marnie's Morgrem
    bench   Ogerpon ex, Meowth ex,            hand    **1 card**
            Dipplin, Fezandipiti ex,
            Ogerpon ex
    hand    **Unfair Stamp**, Meganium,
            Bayleef, Ultra Ball, Grass        (5 cards counting the Stamp)

The Stamp is an ACE SPEC (Item) with a symmetric and expensive text:

    "Each player shuffles their hand into their deck. Then, you draw 5 cards
     and your opponent draws 2 cards."

Hence it has only TWO ways of paying off, and the rule (user, August 2026) requires
at least one of them to hold:

  (1) **DISRUPTION** -- it exists only if it TAKES cards away from the rival. Since it
      leaves them at exactly 2, with a rival hand <= 2 it takes nothing away; in this
      step the rival had **1** card and the Stamp GAVE them one.
  (2) **REFRESH** -- we draw 5, but first we shuffle our WHOLE hand. It is
      worth it as long as what is sacrificed (the hand WITHOUT the Stamp itself) is
      <= 4 cards. In step 99 four were sacrificed -> the Stamp **is** played,
      and in fact the record plays it there (and wins the game).

The rule belongs to the CARD, not to the matchup: the Stamp behaves the same against
any deck, so it carries no whitelist. In the record itself you can see
the pattern that is now written down: with the hand at 10, 9, 8, 7 and 6 cards the Stamp
should NOT be played (a rival with 1 card and too much of our own hand to burn); as
soon as the hand drops to 5 by playing items, clause (2) holds and it is played.

A side effect that had to be closed: half a dozen ORDER vetoes yield
the turn to the Stamp (Boss's, Lillie's, Lana's, Dawn, Xerosic, the
Meowth ex -> Last-Ditch Catch chain and Fezandipiti's ability). If the Stamp is
vetoed and those vetoes go on looking only at "we were knocked out + it is still in hand", the turn
is PARALYSED: the way is yielded to a card that is no longer going to be played. That is why they all
now share the same predicate, `_stamp_pendiente`.
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

import main as m
from patching import instalar

_FIXTURE = (ROOT / "tests" / "fixtures"
            / "marnie_step99_sello_solo_si_disrumpe_o_refresca.json")

STAMP = m.Unfair_Stamp
GRASS = m.Basic_Grass_Energy


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
    m._ub_fez_pending = False
    m._ld_supp_comprometido = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    yield
    m._init_cards_tracking()


def _load():
    with open(_FIXTURE, encoding="utf-8") as f:
        data = json.load(f)
    return (copy.deepcopy(data["observacion_previa"]),
            copy.deepcopy(data["observation"]))


def _decision(extra_hand=0, op_hand=None):
    """Runs the real decision of step 99 and returns (choice, the Stamp's score).

    `extra_hand` fattens OUR hand with dead Grass Energies (the turn's energy
    is already attached): they are exactly the cards the Stamp would shuffle
    into the deck. They are added at the END so as not to shift the `index` of the
    menu's PLAY options.
    """
    previa, dec = _load()
    yo = dec["current"]["yourIndex"]
    mio = dec["current"]["players"][yo]
    for k in range(extra_hand):
        mio["hand"].append({"id": GRASS, "playerIndex": yo, "serial": 900 + k})
    mio["handCount"] = len(mio["hand"])
    if op_hand is not None:
        dec["current"]["players"][1 - yo]["handCount"] = op_hand

    visto = {}
    original = m._score_unfair_stamp_play

    def spy(ctx):
        r = original(ctx)
        visto["stamp"] = r
        return r

    _rest_score_unfair_stamp_play = instalar("_score_unfair_stamp_play", spy)
    try:
        m.agent(previa)                     # it brings the rival KO window
        choice = m.agent(dec)
    finally:
        _rest_score_unfair_stamp_play()
    return choice, visto.get("stamp")


def _plays_the_stamp(obs_choice):
    """Option 0 of the step 99 menu is PLAY of the Unfair Stamp."""
    return obs_choice == [0]


def _ctx(op_hand, hand, stamp=1, ko=True):
    return SimpleNamespace(ko_last_turn=ko,
                           hand_counts={STAMP: stamp},
                           op_hand_count=op_hand,
                           my_hand_len=hand)


# ---------------------------------------------------------------------------
# 1. The record: a hand of 5 (4 are sacrificed) -> the Stamp IS PLAYED
# ---------------------------------------------------------------------------

def test_the_menu_offered_the_stamp_and_the_opponent_had_one_card():
    _, dec = _load()
    yo = dec["current"]["yourIndex"]
    hand = [c["id"] for c in dec["current"]["players"][yo]["hand"]]
    assert hand[0] == STAMP and len(hand) == 5, hand
    assert dec["current"]["players"][1 - yo]["handCount"] == 1
    assert dec["select"]["option"][0]["type"] == int(m.OptionType.PLAY)


def test_a_cheap_refresh_the_stamp_is_played_as_in_the_record():
    choice, score = _decision()
    assert score > 0, score
    assert _plays_the_stamp(choice), (
        "sacrificando solo 4 cartas el refresco (robar 5) paga por si solo, "
        f"aunque el rival no pierda nada; jugo {choice}")


# ---------------------------------------------------------------------------
# 2. The new behaviour: with no disruption and a big hand, the Stamp WAITS
# ---------------------------------------------------------------------------

def test_with_no_disruption_and_a_big_hand_the_stamp_is_vetoed():
    choice, score = _decision(extra_hand=1)      # 5 would be sacrificed
    assert score <= 0, score
    assert not _plays_the_stamp(choice), (
        "con el rival a 1 carta el Sello no disrumpe, y barajar 5 cartas "
        f"propias por 5 nuevas quema recursos ya jugables; jugo {choice}")


def test_with_a_long_opponent_hand_the_stamp_returns_even_if_we_sacrifice_a_lot():
    """Clause (1) is independent: if it DISRUPTS, our own hand does not matter."""
    choice, score = _decision(extra_hand=4, op_hand=m.STAMP_MIN_OP_HAND)
    assert score > 0, score
    assert _plays_the_stamp(choice), choice


# ---------------------------------------------------------------------------
# 3. The two exact edges
# ---------------------------------------------------------------------------

def test_the_edge_of_our_own_hand():
    """Sacrificing 4 passes; sacrificing 5 no longer does (hand = sacrifice + the Stamp)."""
    assert m._stamp_worth_playing(1, m.STAMP_MAX_HAND_SACRIFICED + 1)
    assert not m._stamp_worth_playing(1, m.STAMP_MAX_HAND_SACRIFICED + 2)


def test_the_edge_of_the_opponent_hand():
    """The Stamp leaves the rival at 2, so the disruption is `op_hand - 2`. The
    floor is TWO cards denied: one card is the rounding error of any draw engine
    (registro_006 step 88, `test_the_stamp_does_not_bury_the_last_xerosic`)."""
    big_hand = m.STAMP_MAX_HAND_SACRIFICED + 5
    assert not m._stamp_worth_playing(m.STAMP_MIN_OP_HAND - 1, big_hand)
    assert m._stamp_worth_playing(m.STAMP_MIN_OP_HAND, big_hand)


def test_with_no_data_it_invents_no_plays():
    """The rule only SUBTRACTS: without `op_hand_count` at hand it behaves as before."""
    assert m._stamp_worth_playing(None, 99)
    assert m._stamp_worth_playing(99, None)


# ---------------------------------------------------------------------------
# 4. It is a CARD rule: the same veto against any deck
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("matchup", ["op_is_alakazam_deck",
                                     "op_is_control_deck",
                                     "op_is_gardevoir_deck",
                                     "op_is_zoroark_deck",
                                     "op_is_aggro_deck"])
def test_el_veto_no_lo_resucita_ningun_bonus_de_matchup(matchup):
    """`_AJUSTES_STAMP_PLAY` bonuses plays that are going to be made (+250..+400 by
    matchup); none of them must pull the veto (-1) up to positive numbers."""
    ctx = _ctx(op_hand=1, hand=m.STAMP_MAX_HAND_SACRIFICED + 2)
    for field in ("op_is_alakazam_deck", "op_is_control_deck",
                  "op_is_slowking_deck", "op_is_gardevoir_deck",
                  "op_is_zoroark_deck", "op_is_aggro_deck",
                  "op_is_beedrill_deck"):
        setattr(ctx, field, field == matchup)
    ctx.state = SimpleNamespace(turn=3, supporterPlayed=False,
                                energyAttached=False)
    ctx.my_prize, ctx.op_prize = 4, 2
    ctx.hand_counts = {STAMP: 1, GRASS: 0}
    ctx.forest_in_play = False
    assert m._score_unfair_stamp_play(ctx) <= 0


# ---------------------------------------------------------------------------
# 5. A vetoed Stamp does NOT paralyse the turn
# ---------------------------------------------------------------------------

def test_a_vetoed_stamp_stops_blocking_the_supporters():
    """`_stamp_pendiente` is the single source of the order vetoes (Boss's,
    Lillie's, Lana's, Dawn, Xerosic, the Meowth chain and Flip the Script)."""
    wait = _ctx(op_hand=1, hand=m.STAMP_MAX_HAND_SACRIFICED + 2)
    assert not m._stamp_pendiente(wait)

    juega = _ctx(op_hand=1, hand=m.STAMP_MAX_HAND_SACRIFICED + 1)
    assert m._stamp_pendiente(juega)


def test_with_no_ko_the_stamp_is_never_pending():
    assert not m._stamp_pendiente(_ctx(op_hand=8, hand=3, ko=False))
    assert not m._stamp_pendiente(_ctx(op_hand=8, hand=3, stamp=0))
