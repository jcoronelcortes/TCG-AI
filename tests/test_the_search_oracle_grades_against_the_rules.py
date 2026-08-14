"""The search oracle: it must add up to sixty, and it must know what it cannot see.

The rollout half needs the local engine and is exercised by
`python utils/search_oracle.py --self-test` (2.8 s, both halves). What is pinned
HERE is the part that can be wrong silently and would poison every number
downstream: **the determinization**.

The defect this file exists for is real and was made while writing the module.
`search_begin` validates only `len(...) < count` — too FEW cards is an error and
too MANY is accepted without a word. A first determinizer counted hand, bench,
active and discard, forgot that an attached energy, a tool and a pre-evolution
are cards too, and handed the opponent **46 cards for a deck of 40**. The engine
took it and the rollout played a game with six cards that deck did not have.
Nothing would have complained; the grade would simply have been wrong.
"""

import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "utils"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import search_oracle as so  # noqa: E402


def _board(hand_us, deck_count_us, prize_us, seen_us,
           hand_them, deck_count_them, prize_them, seen_them):
    """A minimal observation: only the fields the determinizer reads."""
    def card(cid):
        return {"id": cid, "serial": None}

    def player(hand, deck_count, prize, active, bench):
        return {"hand": [card(c) for c in hand],
                "deckCount": deck_count,
                "prize": [None] * prize,
                "handCount": len(hand),
                "discard": [],
                "active": active,
                "bench": bench}

    return {"current": {
        "yourIndex": 0,
        "stadium": [],
        "players": [player([], deck_count_us, prize_us, seen_us, []),
                    player(hand_them, deck_count_them, prize_them, seen_them, [])],
    }}


def _body(cid, energies=(), tools=(), pre=()):
    return {"id": cid, "serial": None,
            "energyCards": [{"id": e} for e in energies],
            "tools": [{"id": t} for t in tools],
            "preEvolution": [{"id": p} for p in pre]}


DECK_A = [1] * 30 + [2] * 30
DECK_B = [3] * 30 + [4] * 30


def test_the_determinization_closes_on_sixty_per_seat():
    """The invariant: seen + hand + prize + deck is sixty, on both sides."""
    obs = _board(hand_us=[], deck_count_us=53, prize_us=6, seen_us=[_body(1)],
                 hand_them=[3, 3], deck_count_them=51, prize_them=6,
                 seen_them=[_body(4)])
    det = so.determinize(obs, obs, DECK_A, DECK_B)
    assert len(det["your_deck"]) == 53
    assert len(det["your_prize"]) == 6
    assert len(det["opponent_deck"]) == 51
    assert len(det["opponent_prize"]) == 6
    assert det["opponent_hand"] == [3, 3]


def test_an_attached_energy_is_a_card_and_is_counted():
    """The defect that motivated the file.

    The active carries four energies and a tool. Count only the body and five
    cards go missing from the seen multiset, which means five extra cards in the
    deck we hand the engine — and the engine does not object.
    """
    active = [_body(1, energies=(2, 2, 2, 2), tools=(2,))]
    obs = _board(hand_us=[], deck_count_us=48, prize_us=6, seen_us=active,
                 hand_them=[], deck_count_them=54, prize_them=6, seen_them=[])
    det = so.determinize(obs, obs, DECK_A, DECK_B)
    assert len(det["your_deck"]) == 48, "the five cards in play are not in the deck"
    total = Counter(det["your_deck"]) + Counter(det["your_prize"]) + Counter(
        {1: 1, 2: 5})
    assert sum(total.values()) == 60


def test_a_pre_evolution_under_a_body_is_counted_too():
    obs = _board(hand_us=[], deck_count_us=51, prize_us=6,
                 seen_us=[_body(1, pre=(2, 2))],
                 hand_them=[], deck_count_them=54, prize_them=6, seen_them=[])
    det = so.determinize(obs, obs, DECK_A, DECK_B)
    assert len(det["your_deck"]) == 51


def test_a_determinization_that_does_not_add_up_raises():
    """Sixty is the contract, and breaking it must be loud.

    Here the board claims a 60-card deck while three cards are already visible,
    which cannot be true. The engine would accept the surplus; we do not.
    """
    obs = _board(hand_us=[], deck_count_us=60, prize_us=6,
                 seen_us=[_body(1), _body(1), _body(1)],
                 hand_them=[], deck_count_them=54, prize_them=6, seen_them=[])
    with pytest.raises(so.DeterminizationError):
        so.determinize(obs, obs, DECK_A, DECK_B)


def test_the_same_seed_gives_the_same_determinization():
    """The half of specificity our seed actually controls.

    The engine's own shuffles are NOT seeded — measured, and it is why the
    module is an estimator with a noise floor rather than a replay. What must
    hold is that the part we sample is reproducible.
    """
    obs = _board(hand_us=[], deck_count_us=53, prize_us=6, seen_us=[_body(1)],
                 hand_them=[3], deck_count_them=52, prize_them=6,
                 seen_them=[_body(4)])
    import random

    a = so.determinize(obs, obs, DECK_A, DECK_B, rng=random.Random(7))
    b = so.determinize(obs, obs, DECK_A, DECK_B, rng=random.Random(7))
    for key in ("your_deck", "your_prize", "opponent_deck", "opponent_prize"):
        assert a[key] == b[key]


def test_the_oracle_says_out_loud_that_it_cannot_be_a_policy():
    """It reads the opponent's hand. A grader that quietly became a policy would
    be cheating, so the module must say so in its first paragraph."""
    head = so.__doc__[:600].upper()
    assert "NEVER BE A PLAY-TIME POLICY" in head, (
        "the warning has to be at the TOP, where somebody opening the file "
        "reads it before deciding what to do with the module")
