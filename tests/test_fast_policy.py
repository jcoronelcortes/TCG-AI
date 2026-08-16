"""fast_policy: legal, deterministic under a seeded rng, and stateless.

Phase S2 §5.2. The "strictly better than random on the sensitivity board"
requirement needs the LOCAL engine and a gitignored opponent list, so that
half lives in `utils/shadow_arbiter.py --selftest` (a tool, measured the
night of 16 August); what a clean checkout can assert is here.
"""

import random
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import ptcg.search.fast_policy as fp  # noqa: E402
from ptcg.search.fast_policy import fast_policy  # noqa: E402


def menu(options, min_count=1, max_count=1):
    return {"select": {"option": options, "minCount": min_count,
                       "maxCount": max_count},
            "current": {"yourIndex": 0}}


def test_an_attack_is_taken_over_everything_else():
    obs = menu([{"type": 14}, {"type": 7}, {"type": 13}, {"type": 12}])
    for seed in range(20):
        assert fast_policy(obs, random.Random(seed)) == [2]


def test_end_and_retreat_only_when_nothing_else_remains():
    obs = menu([{"type": 14}, {"type": 7}, {"type": 10}])
    for seed in range(20):
        assert fast_policy(obs, random.Random(seed))[0] in (1, 2)
    only_out = menu([{"type": 14}, {"type": 12}])
    picks = {fast_policy(only_out, random.Random(s))[0] for s in range(20)}
    assert picks <= {0, 1}


def test_a_multi_pick_menu_honours_the_bounds():
    obs = menu([{"type": 3}] * 6, min_count=2, max_count=4)
    for seed in range(30):
        choice = fast_policy(obs, random.Random(seed))
        assert 2 <= len(choice) <= 4
        assert len(set(choice)) == len(choice)
        assert all(0 <= i < 6 for i in choice)


def test_the_same_seed_gives_the_same_choice():
    obs = menu([{"type": 7}, {"type": 3}, {"type": 10}, {"type": 14}])
    a = [fast_policy(obs, random.Random(9)) for _ in range(5)]
    b = [fast_policy(obs, random.Random(9)) for _ in range(5)]
    assert a == b


def test_an_empty_menu_returns_none():
    assert fast_policy(menu([]), random.Random(1)) is None


def test_the_module_keeps_no_mutable_state():
    mutable = (list, dict, set, bytearray)
    offenders = [name for name, value in vars(fp).items()
                 if not name.startswith("__")
                 and isinstance(value, mutable)]
    assert offenders == []


def test_as_agent_closes_over_its_own_rng():
    obs = menu([{"type": 7}, {"type": 3}])
    a = fp.as_agent(random.Random(4))
    b = fp.as_agent(random.Random(4))
    assert [a(obs) for _ in range(5)] == [b(obs) for _ in range(5)]


def test_the_mixed_agent_plays_our_seat_and_refuses_theirs():
    ours = menu([{"type": 13}, {"type": 14}])
    ours["current"]["yourIndex"] = 0
    theirs = menu([{"type": 13}, {"type": 14}])
    theirs["current"]["yourIndex"] = 1
    agent = fp.as_mixed_agent(0, random.Random(2))
    assert agent(ours) == [0]
    try:
        agent(theirs)
        raised = False
    except LookupError:
        raised = True
    assert raised  # search_oracle._choose turns this into a random legal pick
