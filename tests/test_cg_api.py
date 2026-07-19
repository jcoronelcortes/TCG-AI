import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cg.api as api


def test_to_observation_class_converts_nested_payload():
    payload = {
        "select": {
            "type": api.SelectType.MAIN,
            "context": api.SelectContext.MAIN,
            "minCount": 1,
            "maxCount": 1,
            "remainDamageCounter": 0,
            "remainEnergyCost": 0,
            "option": [{"type": api.OptionType.PLAY, "index": 0}],
            "deck": None,
            "contextCard": None,
            "effect": None,
        },
        "logs": [],
        "current": {
            "turn": 2,
            "turnActionCount": 1,
            "yourIndex": 0,
            "firstPlayer": 0,
            "supporterPlayed": False,
            "stadiumPlayed": False,
            "energyAttached": False,
            "retreated": False,
            "result": -1,
            "stadium": [],
            "looking": [],
            "players": [
                {
                    "active": [None],
                    "bench": [],
                    "benchMax": 5,
                    "deckCount": 59,
                    "discard": [],
                    "prize": [],
                    "handCount": 1,
                    "hand": [{"id": 1, "serial": 10, "playerIndex": 0}],
                    "poisoned": False,
                    "burned": False,
                    "asleep": False,
                    "paralyzed": False,
                    "confused": False,
                },
                {
                    "active": [None],
                    "bench": [],
                    "benchMax": 5,
                    "deckCount": 59,
                    "discard": [],
                    "prize": [],
                    "handCount": 0,
                    "hand": None,
                    "poisoned": False,
                    "burned": False,
                    "asleep": False,
                    "paralyzed": False,
                    "confused": False,
                },
            ],
        },
    }

    obs = api.to_observation_class(payload)

    assert isinstance(obs, api.Observation)
    assert obs.current.turn == 2
    assert isinstance(obs.current.players[0], api.PlayerState)
    assert obs.select.context == api.SelectContext.MAIN
    assert obs.select.option[0].type == api.OptionType.PLAY


def test_all_card_data_and_all_attack_return_dataclasses(monkeypatch):
    monkeypatch.setattr(
        api.lib,
        "AllCard",
        lambda: json.dumps([
            {
                "cardId": 1,
                "name": "Pikachu",
                "cardType": api.CardType.POKEMON,
                "retreatCost": 1,
                "hp": 100,
                "weakness": None,
                "resistance": None,
                "energyType": api.EnergyType.LIGHTNING,
                "basic": True,
                "stage1": False,
                "stage2": False,
                "ex": False,
                "megaEx": False,
                "tera": False,
                "aceSpec": False,
                "evolvesFrom": None,
                "skills": [],
                "attacks": [],
            }
        ]).encode("utf-8"),
    )
    monkeypatch.setattr(
        api.lib,
        "AllAttack",
        lambda: json.dumps([
            {
                "attackId": 1,
                "name": "Tackle",
                "text": "Deal damage",
                "damage": 20,
                "energies": [api.EnergyType.COLORLESS],
            }
        ]).encode("utf-8"),
    )

    cards = api.all_card_data()
    attacks = api.all_attack()

    assert cards[0].name == "Pikachu"
    assert attacks[0].damage == 20


def test_search_begin_validates_inputs_and_calls_library(monkeypatch):
    captured = {}

    def fake_search_begin(agent_ptr, sbi_bytes, length, your_deck, your_prize, opp_deck, opp_prize, opp_hand, opp_active, manual_coin):
        captured["args"] = (agent_ptr, sbi_bytes, length, your_deck, your_prize, opp_deck, opp_prize, opp_hand, opp_active, manual_coin)
        return json.dumps({"state": {"observation": {"select": None, "logs": [], "current": None}, "searchId": 42}, "error": 0}).encode("utf-8")

    monkeypatch.setattr(api.lib, "AgentStart", lambda: 77)
    monkeypatch.setattr(api.lib, "SearchBegin", fake_search_begin)

    obs = SimpleNamespace(
        search_begin_input="abc",
        current=SimpleNamespace(
            yourIndex=0,
            players=[
                SimpleNamespace(deckCount=1, prize=[object()], active=[None]),
                SimpleNamespace(deckCount=1, prize=[], active=[None], handCount=0),
            ],
        ),
        select=SimpleNamespace(deck=None),
    )

    state = api.search_begin(obs, [1], [2], [3], [], [], [9])

    assert state.searchId == 42
    assert captured["args"][1] == b"abc"
    assert captured["args"][2] == 3


def test_search_begin_raises_for_invalid_lengths():
    obs = SimpleNamespace(
        search_begin_input="abc",
        current=SimpleNamespace(
            yourIndex=0,
            players=[
                SimpleNamespace(deckCount=2, prize=[object()], active=[None]),
                SimpleNamespace(deckCount=1, prize=[], active=[None], handCount=0),
            ],
        ),
        select=SimpleNamespace(deck=None),
    )

    with pytest.raises(ValueError):
        api.search_begin(obs, [1], [2], [3], [], [], [])


def test_search_step_maps_error_codes(monkeypatch):
    def fake_search_step(agent_ptr, search_id, selection, count):
        return json.dumps({"state": None, "error": 4}).encode("utf-8")

    monkeypatch.setattr(api.lib, "SearchStep", fake_search_step)

    with pytest.raises(ValueError, match="Must be"):
        api.search_step(1, [0])


def test_search_end_and_release_delegate_to_library(monkeypatch):
    called = []

    def fake_search_end(agent_ptr):
        called.append(("end", agent_ptr))

    def fake_search_release(agent_ptr, search_id):
        called.append(("release", agent_ptr, search_id))

    monkeypatch.setattr(api.lib, "SearchEnd", fake_search_end)
    monkeypatch.setattr(api.lib, "SearchRelease", fake_search_release)
    monkeypatch.setattr(api.lib, "AgentStart", lambda: 5)

    api.search_end()
    api.search_release(7)

    assert called[0][0] == "end"
    assert called[1][2] == 7
