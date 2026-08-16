"""The opponent posterior: hosting is binary, zero is exact, the prior is meta.

Phase S1 (docs/plan-la-busqueda-en-juego-2026-08-15.md §4). These tests build
the prior from INJECTED lists -- `deck/real_opponents_500/` is gitignored, and
a test that needs it would go green-by-skip on a clean checkout, which is the
"a control that does not run the measurement is not a control" defect. The
integration path over the real lists is exercised by
`utils/opponent_prior_census.py`, which is a tool, not a test.
"""

import random
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ptcg.opponent.prior import OpponentPrior, ids_seen  # noqa: E402

# Three tiny "lists" (the module never checks they are sixty distinct cards,
# only multiset membership; sixty entries keep the arithmetic honest).
LIST_A = [101] * 20 + [102] * 20 + [103] * 20            # archetype "alpha"
LIST_B = [101] * 20 + [102] * 20 + [104] * 20            # archetype "beta"
LIST_C = [201] * 30 + [202] * 30                          # archetype "gamma"


def make_prior(wa=0.6, wb=0.3, wc=0.1):
    return OpponentPrior([
        ("alpha_1", "Alpha", wa, LIST_A),
        ("beta_1", "Beta", wb, LIST_B),
        ("gamma_1", "Gamma", wc, LIST_C),
    ])


def obs_with_opponent_board(card_ids, your_index=0):
    """We are seat `your_index`; the opponent's bench shows `card_ids`."""
    them = [{"id": cid, "energyCards": [], "tools": [], "preEvolution": []}
            for cid in card_ids]
    players = [None, None]
    players[your_index] = {"hand": [], "discard": [], "prize": [],
                           "active": [], "bench": []}
    players[1 - your_index] = {"hand": [], "discard": [], "prize": [],
                               "active": [], "bench": them}
    return {"current": {"yourIndex": your_index, "players": players},
            "select": {}}


def test_the_posterior_is_normalised_and_sorted():
    posterior = make_prior().posterior(obs_with_opponent_board([101]))
    assert abs(sum(p for _n, p in posterior) - 1.0) < 1e-9
    probs = [p for _n, p in posterior]
    assert probs == sorted(probs, reverse=True)


def test_a_list_that_cannot_host_the_board_gets_exact_zero():
    # 104 belongs to B only: A and C cannot host, and zero means ABSENT.
    posterior = make_prior().posterior(obs_with_opponent_board([104]))
    names = [n for n, _p in posterior]
    assert names == ["beta_1"]
    assert posterior[0][1] == 1.0


def test_among_hosts_the_meta_prior_decides():
    # 101 is shared by A and B: both host, so the split is the meta prior.
    posterior = dict(make_prior(wa=0.6, wb=0.3, wc=0.1)
                     .posterior(obs_with_opponent_board([101])))
    assert "gamma_1" not in posterior
    assert abs(posterior["alpha_1"] - 2 / 3) < 1e-9
    assert abs(posterior["beta_1"] - 1 / 3) < 1e-9


def test_more_board_evicts_the_wrong_host():
    prior = make_prior()
    early = dict(prior.posterior(obs_with_opponent_board([101])))
    late = dict(prior.posterior(obs_with_opponent_board([101, 103])))
    assert "beta_1" in early
    assert list(late) == ["alpha_1"]


def test_a_count_above_the_lists_copies_is_foreign():
    # LIST_A carries twenty 103s; twenty-one visible copies cannot be hosted.
    board = [103] * 21
    posterior, hosted = make_prior().evaluate(obs_with_opponent_board(board))
    assert not hosted


def test_the_fallback_is_flagged_and_still_normalised():
    posterior, hosted = make_prior().evaluate(obs_with_opponent_board([999]))
    assert hosted is False
    assert abs(sum(p for _n, p in posterior) - 1.0) < 1e-9


def test_the_archetype_posterior_sums_lists_of_one_archetype():
    prior = OpponentPrior([
        ("alpha_1", "Alpha", 0.4, LIST_A),
        ("alpha_2", "Alpha", 0.2, LIST_A),
        ("beta_1", "Beta", 0.4, LIST_B),
    ])
    arch = dict(prior.archetype_posterior(obs_with_opponent_board([101])))
    assert abs(arch["Alpha"] - 0.6) < 1e-9
    assert abs(arch["Beta"] - 0.4) < 1e-9


def test_sample_deck_is_deterministic_under_a_seeded_rng():
    prior = make_prior()
    obs = obs_with_opponent_board([101])
    a = [prior.sample_deck(obs, random.Random(7))[0] for _ in range(10)]
    b = [prior.sample_deck(obs, random.Random(7))[0] for _ in range(10)]
    assert a == b


def test_sample_deck_never_returns_a_zero_mass_list():
    prior = make_prior()
    obs = obs_with_opponent_board([104])  # only beta_1 hosts
    for seed in range(50):
        name, deck = prior.sample_deck(obs, random.Random(seed))
        assert name == "beta_1"
        assert len(deck) == 60


def test_ids_seen_counts_attachments_stadium_and_cards_in_flight():
    obs = {
        "current": {
            "yourIndex": 0,
            "players": [
                {"hand": [], "discard": [], "prize": [], "active": [],
                 "bench": []},
                {"hand": [{"id": 1}],
                 "discard": [{"id": 2}],
                 "prize": [None, {"id": 3}],
                 "active": [{"id": 4,
                             "energyCards": [{"id": 5}],
                             "tools": [{"id": 6}],
                             "preEvolution": [{"id": 7}]}],
                 "bench": [None]},
            ],
            "stadium": [{"id": 8, "playerIndex": 1}],
            "looking": [{"id": 9, "playerIndex": 1},
                        {"id": 10, "playerIndex": 0}],
        },
        "select": {"effect": [{"id": 11, "playerIndex": 1}]},
    }
    seen = ids_seen(obs, 1)
    assert dict(seen) == {1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1, 7: 1, 8: 1,
                          9: 1, 11: 1}


def test_the_flat_variant_ignores_the_meta_weight():
    flat = OpponentPrior([
        ("alpha_1", "Alpha", 1.0, LIST_A),
        ("beta_1", "Beta", 1.0, LIST_B),
    ])
    posterior = dict(flat.posterior(obs_with_opponent_board([101])))
    assert abs(posterior["alpha_1"] - 0.5) < 1e-9
