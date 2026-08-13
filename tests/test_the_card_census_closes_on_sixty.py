"""Both halves of the card census: it must find what is there and only that.

A harness is validated twice or not at all. SENSITIVITY is that a card which
cannot possibly be played is reported with conversion 0; SPECIFICITY is that the
fates of one game sum to sixty, exactly once per copy. A census that fails the
first invents dead cards; one that fails the second prices every card against a
denominator that is wrong, and every table downstream of it is void.

WHAT THESE TESTS PIN, and each line is a defect that was real:

  * **The fates close on sixty.** `resolve_game` recovers the copies it never
    saw by subtracting the seen multiset from `deck.csv`, so the row count is an
    invariant and not a hope. `OTRO` is the resolver's own alarm and must stay
    empty: with it the sum always closes, which turns a resolver bug into a
    labelled residue instead of a silently wrong percentage.

  * **A copy can cycle, and the first version got it wrong.** Drawn, shuffled
    back by a Marnie, drawn again, still in hand at the end: the plan's fate
    order was a first-match-wins list, so it answered `DEVUELTA_AL_MAZO` for a
    card sitting in our hand. Serial 43 of episode 92484395 does this for real.
    The fate is now how the copy LAST left our hand, with the observation as the
    authority on where it ended.

  * **Fodder is a HAND -> DISCARD with no PLAY, and needs no same-step
    correlation.** Measured on a real episode: a played card emits `PLAY` and no
    movement event whatsoever, and all 14 HAND -> DISCARD events belonged to
    copies that were never played. The plan budgeted risk for a correlation rule
    that turns out to be unnecessary.

  * **The opponent's events arrive in our own stream.** Filtering by
    `playerIndex` is what turns the plan's impossible "8 prize events for 6
    prizes" into the true 5. Without it the census silently prices our list using
    the opponent's plays.

  * **The dead-in-hand set IS the final hand.** Run against whatever episode is
    on disk, this compares the fate the stream implies against the zone the
    observation states -- two independent sources for the same fact.
"""

import json
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "utils", ROOT / "tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import card_census as cc  # noqa: E402
from cg.api import AreaType, LogType  # noqa: E402

# A synthetic deck: fifteen cards, four copies each, no engine needed.
DECK = [c for c in range(1, 16) for _ in range(4)]
US, THEM = 0, 1


def ev(kind, serial, card_id, *, seat=US, src=None, dst=None):
    event = {"type": int(kind), "playerIndex": seat, "serial": serial,
             "cardId": card_id}
    if src is not None:
        event["fromArea"] = int(src)
    if dst is not None:
        event["toArea"] = int(dst)
    return event


def draw(turn, serial, card_id, **kw):
    return (turn, ev(LogType.DRAW, serial, card_id, **kw))


def move(turn, serial, card_id, src, dst, **kw):
    return (turn, ev(LogType.MOVE_CARD, serial, card_id, src=src, dst=dst, **kw))


def play(turn, serial, card_id, **kw):
    return (turn, ev(LogType.PLAY, serial, card_id, **kw))


def fate_of(rows, serial):
    return next(r["fate"] for r in rows if r["serial"] == serial)


# ---------------------------------------------------------------------------
# Specificity
# ---------------------------------------------------------------------------

def test_the_fates_close_on_sixty_and_every_copy_has_exactly_one():
    """Sixty rows, one fate each, and the unseen remainder recovered by subtraction."""
    events = [draw(1, 3, 1), play(1, 3, 1), draw(1, 4, 2)]
    rows, diag = cc.resolve_game(events, US, {4: AreaType.HAND}, DECK, last_turn=3)

    assert len(rows) == cc.DECK_SIZE, "a game is sixty copies, always"
    assert diag["filas"] == cc.DECK_SIZE
    assert Counter(r["card_id"] for r in rows) == Counter(DECK), (
        "the census must price the deck it was given, copy for copy")
    assert all(r["fate"] in cc.FATES for r in rows)
    assert diag["otro"] == 0, "OTRO is the resolver's alarm, not a fate"
    assert diag["sobrantes"] == 0


def test_a_copy_seen_twice_is_not_counted_twice():
    """Two events for one serial are one copy, not two: the census is per COPY."""
    events = [draw(1, 3, 1), move(2, 3, 1, AreaType.HAND, AreaType.DECK),
              draw(3, 3, 1), play(3, 3, 1)]
    rows, diag = cc.resolve_game(events, US, {}, DECK, last_turn=4)
    assert len(rows) == cc.DECK_SIZE
    assert sum(1 for r in rows if r["serial"] == 3) == 1
    assert diag["sobrantes"] == 0


# ---------------------------------------------------------------------------
# Sensitivity
# ---------------------------------------------------------------------------

def test_a_card_that_is_never_played_converts_at_zero():
    """The planted dead card. Drawn every game, played never: conversion 0."""
    # Card 7 is drawn and sits in hand; card 1 is drawn and played.
    events = [draw(1, 3, 1), play(1, 3, 1), draw(1, 20, 7)]
    rows, _ = cc.resolve_game(events, US, {20: AreaType.HAND}, DECK, last_turn=5)
    per_card, games = cc.aggregate([{"rows": rows, "won": True, "diag": {}}])

    assert games == 1
    assert per_card[7]["conversion"] == 0.0, (
        "a card drawn and never played must be reported dead, not merely quiet")
    assert per_card[7]["tasa_muerte"] > 0.0
    assert per_card[1]["conversion"] == 1.0, "and the played one must not be"


def test_a_card_never_seen_is_not_reported_as_dead_in_hand():
    """`NO_VISTA` is 'deck or unrevealed prize'; it is not a dead card."""
    rows, diag = cc.resolve_game([], US, {}, DECK, last_turn=1, prizes_hidden=6)
    per_card, _ = cc.aggregate([{"rows": rows, "won": False, "diag": diag}])
    assert per_card[1]["tasa_no_vista"] == 1.0
    assert per_card[1]["tasa_muerte"] == 0.0, (
        "a card still in the deck was never wasted in hand")
    assert diag["premios_ocultos"] == 6, "the honest denominator travels with the rows"


# ---------------------------------------------------------------------------
# The rules the engine's own events settle
# ---------------------------------------------------------------------------

def test_a_played_card_needs_no_movement_event():
    """A PLAY with no MOVE_CARD at all is still JUGADA.

    Measured: 22 PLAY events on a real episode, none of them paired with a
    movement for the same serial. A resolver that waited for HAND -> DISCARD to
    confirm a play would report every Supporter we cast as never played.
    """
    rows, _ = cc.resolve_game([draw(1, 3, 1), play(2, 3, 1)], US, {}, DECK,
                              last_turn=4)
    assert fate_of(rows, 3) == cc.JUGADA


def test_fodder_is_a_hand_to_discard_with_no_play():
    """The Ultra Ball case: the cost is fodder, the Ultra Ball itself is played."""
    events = [draw(1, 3, 1), draw(1, 4, 2), draw(1, 5, 3),
              play(2, 3, 1),                                     # the Ultra Ball
              move(2, 4, 2, AreaType.HAND, AreaType.DISCARD),    # its two costs
              move(2, 5, 3, AreaType.HAND, AreaType.DISCARD)]
    rows, diag = cc.resolve_game(events, US, {}, DECK, last_turn=4)
    assert fate_of(rows, 3) == cc.JUGADA
    assert fate_of(rows, 4) == cc.FORRAJE
    assert fate_of(rows, 5) == cc.FORRAJE
    assert diag["otro"] == 0


def test_the_copy_that_comes_back_is_dead_in_hand_not_shuffled_back():
    """The cycling regression: drawn, Marnie'd away, drawn again, still in hand.

    The plan's first-match-wins fate order answered DEVUELTA_AL_MAZO here.
    """
    events = [draw(1, 3, 1),
              move(2, 3, 1, AreaType.HAND, AreaType.DECK),
              draw(3, 3, 1)]
    rows, _ = cc.resolve_game(events, US, {3: AreaType.HAND}, DECK, last_turn=6)
    assert fate_of(rows, 3) == cc.MUERTA_EN_MANO

    # And with no return, the same stream really is a card shuffled back.
    rows, _ = cc.resolve_game(events[:2], US, {}, DECK, last_turn=6)
    assert fate_of(rows, 3) == cc.DEVUELTA_AL_MAZO


def test_the_last_way_it_left_wins_over_the_first():
    """Drawn, fodder, recovered by a Night Stretcher, then played."""
    events = [draw(1, 3, 1),
              move(1, 3, 1, AreaType.HAND, AreaType.DISCARD),
              move(4, 3, 1, AreaType.DISCARD, AreaType.HAND),
              play(4, 3, 1)]
    rows, _ = cc.resolve_game(events, US, {}, DECK, last_turn=6)
    assert fate_of(rows, 3) == cc.JUGADA
    row = next(r for r in rows if r["serial"] == 3)
    assert row["veces_recuperada"] == 1, "and the history the fate cannot carry is kept"


def test_the_starting_basic_is_put_into_play_not_played():
    """Setup placement is MOVE_CARD(HAND -> ACTIVE); the engine emits no PLAY."""
    events = [draw(0, 3, 1), move(0, 3, 1, AreaType.HAND, AreaType.ACTIVE)]
    rows, _ = cc.resolve_game(events, US, {3: AreaType.ACTIVE}, DECK, last_turn=4)
    assert fate_of(rows, 3) == cc.PUESTA_EN_JUEGO
    per_card, _ = cc.aggregate([{"rows": rows, "won": True, "diag": {}}])
    assert per_card[1]["conversion"] > 0, "it did its job, so it converted"


def test_the_hand_a_mill_empties_is_not_called_fodder():
    """The Comfey case, and the reason the `OTRO` alarm exists.

    The opponent rifling our hand emits a FACE-DOWN `HAND -> LOOKING` with no
    cardId, so the only visible half of the copy's departure is
    `LOOKING -> DISCARD`. Before this fate existed the copy fell through every
    rule into `OTRO`: 19 of 36 games against Comfey mill produced one.

    It must not be FORRAJE. Fodder is a cost we chose to pay, and a card the
    opponent took from us says nothing about whether it earns its slot.
    """
    events = [draw(1, 3, 1),
              (5, {"type": int(LogType.MOVE_CARD_REVERSE), "playerIndex": US,
                   "fromArea": int(AreaType.HAND), "toArea": int(AreaType.LOOKING)}),
              move(5, 3, 1, AreaType.LOOKING, AreaType.DISCARD)]
    rows, diag = cc.resolve_game(events, US, {}, DECK, last_turn=8)
    assert fate_of(rows, 3) == cc.DESCARTADA_EN_REVELADO
    assert fate_of(rows, 3) != cc.FORRAJE
    assert diag["otro"] == 0, "the alarm must stay silent once the fate is named"
    assert diag["mano_revelada"] == 1, (
        "and the blindness is reported by transition, not lumped into one total")
    assert diag["reparto_premios"] == 0


def test_a_card_put_into_play_from_the_deck_still_counts_as_played():
    """Entering play is read by destination: some cards never pass through hand."""
    events = [move(2, 3, 1, AreaType.DECK, AreaType.BENCH)]
    rows, diag = cc.resolve_game(events, US, {3: AreaType.BENCH}, DECK, last_turn=5)
    assert fate_of(rows, 3) == cc.PUESTA_EN_JUEGO
    assert diag["otro"] == 0


def test_a_promotion_does_not_relabel_an_attacker_as_freshly_placed():
    """BENCH -> ACTIVE starts IN play, so it is not a card entering play.

    Reading entry by destination alone would overwrite JUGADA with
    PUESTA_EN_JUEGO for every Pokemon we ever promote, because the last departure
    wins and the promotion comes last.
    """
    events = [draw(1, 3, 1), play(1, 3, 1),
              move(6, 3, 1, AreaType.BENCH, AreaType.ACTIVE)]
    rows, _ = cc.resolve_game(events, US, {3: AreaType.ACTIVE}, DECK, last_turn=9)
    assert fate_of(rows, 3) == cc.JUGADA


def test_looked_at_and_declined_is_its_own_fate():
    """DECK -> LOOKING -> DECK: we searched straight past it."""
    events = [move(3, 9, 4, AreaType.DECK, AreaType.LOOKING),
              move(3, 9, 4, AreaType.LOOKING, AreaType.DECK)]
    rows, _ = cc.resolve_game(events, US, {}, DECK, last_turn=5)
    assert fate_of(rows, 9) == cc.MIRADA_Y_RECHAZADA
    row = next(r for r in rows if r["serial"] == 9)
    assert row["veces_rechazada"] == 1
    assert row["robada"] == 0, "looking at a card is not drawing it"


def test_the_opponents_events_do_not_enter_our_census():
    """Both seats' events arrive in our stream; only ours may be priced.

    This is the cause of the plan's impossible arithmetic -- eight PRIZE -> HAND
    events in a game that awards six prizes -- and it is the difference between
    censusing our list and censusing the table.
    """
    events = [draw(1, 3, 1), play(1, 3, 1),
              draw(1, 99, 12, seat=THEM), play(1, 99, 12, seat=THEM),
              move(1, 98, 13, AreaType.PRIZE, AreaType.HAND, seat=THEM)]
    rows, diag = cc.resolve_game(events, US, {}, DECK, last_turn=3)
    assert len(rows) == cc.DECK_SIZE
    assert all(r["serial"] != 99 for r in rows), "their copies are not ours"
    assert diag["sobrantes"] == 0


# ---------------------------------------------------------------------------
# Against a real game, if one is on disk
# ---------------------------------------------------------------------------

def _an_episode():
    """Any recorded episode. `log_analisys/` is swapped by the nightly tools, so
    the file is found by shape and never by name."""
    for path in sorted((ROOT / "log_analisys").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and data.get("steps"):
            return path, data
    return None, None


def test_the_dead_in_hand_set_is_exactly_the_final_hand():
    """Two independent sources for one fact, on a real game.

    The fate comes from the event stream; the hand comes from the observation.
    They have to agree card for card, and if they ever stop agreeing the fate
    order has drifted from what the engine does.
    """
    path, data = _an_episode()
    if path is None:
        pytest.skip("no recorded episode on disk")
    deck = cc.read_deck()
    census = cc.census_of_episode(path, deck)
    rows, diag = census["rows"], census["diag"]

    assert diag["filas"] == cc.DECK_SIZE, f"{path.name}: the fates must close on sixty"
    assert diag["otro"] == 0, f"{path.name}: the resolver's alarm went off"
    assert diag["sobrantes"] == 0, f"{path.name}: more copies seen than the deck holds"

    seat = census["seat"]
    _handed, last = cc.observations_of_episode(data, seat)
    in_hand = {c["serial"] for c in (last["current"]["players"][seat].get("hand") or [])}
    dead = {r["serial"] for r in rows if r["fate"] == cc.MUERTA_EN_MANO}
    assert dead == in_hand, (
        f"{path.name}: the stream says {sorted(dead)} died in hand, the board "
        f"says {sorted(in_hand)}")


def test_every_face_down_event_is_one_of_the_two_we_can_name():
    """§6.2's blindness, accounted for instead of assumed.

    `MOVE_CARD_REVERSE` carries no cardId, so face-down movement is
    unattributable and the census can only be honest about it by naming it. Two
    transitions account for all of it: the six DECK -> PRIZE of the deal, and
    HAND -> LOOKING when the opponent rifles our hand. A third kind appearing is
    a new blind spot, and the census must say so rather than absorb it into a
    total that looks tidy.
    """
    path, _data = _an_episode()
    if path is None:
        pytest.skip("no recorded episode on disk")
    diag = cc.census_of_episode(path, cc.read_deck())["diag"]
    unexplained = diag["cara_abajo"] - diag["reparto_premios"] - diag["mano_revelada"]
    assert unexplained == 0, (
        f"{path.name}: {unexplained} face-down events that are neither the prize "
        "deal nor the opponent reading our hand -- the census is blinder than it "
        "reports")
    assert diag["reparto_premios"] <= cc.PRIZES, (
        f"{path.name}: more prizes dealt face-down than a game awards")
