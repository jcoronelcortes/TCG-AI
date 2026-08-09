"""Structurally broken boards: does not raise, answers something legal.

T2.4 of docs/testing-plan-2026-08.md. The only failure mode that costs the whole
game regardless of how well the agent plays is an EXCEPTION inside the
container: the match is forfeited on the spot, and no amount of correct strategy
before it matters. The agent also runs against decks it has never seen, on
boards no fixture in this repository contains.

So this asserts the weakest possible property, on purpose: not "it plays well",
not even "it plays sensibly", only *it comes back with an index that exists*.
That is the whole point -- a property this weak needs nobody to know the right
play, which is what lets it be checked on boards nobody designed.

THE MUTATIONS are structural rather than random: the shapes a real opponent's
deck or a rules interaction can actually produce, and which no fixture here
happens to have.

  * every zone emptied in turn -- bench, hand, discard, prizes;
  * the stadium removed from under a board that had one;
  * a card id that is in no table at all (an opposing card we do not model);
  * `minCount` 0, the select that may legally be answered with nothing;
  * the opponent's bench emptied, which is the board a knockout produces.

MEASURED, and the number is the finding: 12 real boards x 8 mutations = 96
observations, ZERO exceptions and ZERO illegal answers. A test whose result is
"nothing happened" earns its place here because the thing it watches for is
catastrophic and silent until it is not -- and because the next unmodelled card
that walks into a zone this suite has never emptied will hit it first.
"""

import copy
import glob
import json
from pathlib import Path

import pytest

import main as m
from golden_corpus import reset_agent

ROOT = Path(__file__).resolve().parents[1]

# Bounded on purpose: this file runs on every push, and the marginal board buys
# less than the second it costs. The boards are taken in name order so the set
# is the same on every machine.
BOARDS = 12

UNKNOWN_CARD_ID = 999999


def _my(o):
    return o["current"]["players"][o["current"]["yourIndex"]]


def _theirs(o):
    return o["current"]["players"][1 - o["current"]["yourIndex"]]


def _load_boards():
    out = []
    for name in sorted(glob.glob(str(ROOT / "tests" / "fixtures" / "*.json"))):
        try:
            data = json.loads(Path(name).read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        obs = data.get("observation") if isinstance(data, dict) else None
        if obs is None and isinstance(data, dict) and "select" in data:
            obs = data
        if not isinstance(obs, dict):
            continue
        select = obs.get("select") or {}
        if not select.get("option"):
            continue
        out.append((Path(name).name, obs))
        if len(out) >= BOARDS:
            break
    return out


_BOARDS = _load_boards()

MUTATIONS = {
    "no stadium": lambda o: o["current"].update(stadium=[]),
    "empty bench": lambda o: _my(o).update(bench=[]),
    "empty hand": lambda o: _my(o).update(hand=[]),
    "empty discard": lambda o: _my(o).update(discard=[]),
    "no prizes left": lambda o: _my(o).update(prize=[]),
    "a card in no table": lambda o: _my(o)["hand"].append(
        {"id": UNKNOWN_CARD_ID, "serial": 123456,
         "playerIndex": o["current"]["yourIndex"]}),
    "minCount 0": lambda o: o["select"].update(minCount=0),
    "their bench swept": lambda o: _theirs(o).update(bench=[]),
}


def _is_legal(choice, options):
    return (isinstance(choice, list)
            and all(isinstance(i, int) and 0 <= i < len(options)
                    for i in choice))


def test_there_are_boards_to_fuzz():
    """Guard the harness: an empty corpus would make every test below vacuous."""
    assert len(_BOARDS) == BOARDS


def test_the_legality_check_can_fail():
    """The other half. A checker that accepts anything proves nothing."""
    assert _is_legal([0], [{"type": 14}])
    assert not _is_legal([1], [{"type": 14}]), "an index past the end"
    assert not _is_legal([-1], [{"type": 14}]), "a negative index"
    assert not _is_legal(None, [{"type": 14}]), "no answer at all"


@pytest.mark.parametrize("mutation", sorted(MUTATIONS))
def test_a_structurally_broken_board_still_gets_a_legal_answer(mutation):
    apply_mutation = MUTATIONS[mutation]
    for name, board in _BOARDS:
        o = copy.deepcopy(board)
        try:
            apply_mutation(o)
        except (KeyError, IndexError, TypeError):
            continue          # the board has no such zone: nothing to break
        reset_agent(m)
        try:
            choice = m.agent(o)
        except Exception as exc:            # noqa: BLE001 -- that IS the test
            pytest.fail(f"{name} con '{mutation}': el agente lanzo "
                        f"{exc!r} -- en el contenedor eso es la partida")
        assert _is_legal(choice, o["select"]["option"]), (
            f"{name} con '{mutation}': indice ilegal {choice!r} sobre "
            f"{len(o['select']['option'])} opciones")
