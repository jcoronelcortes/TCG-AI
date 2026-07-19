import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cg.game as game
from cg.sim import StartData


@pytest.fixture(autouse=True)
def reset_battle_state():
    game.Battle.battle_ptr = None
    game.Battle.obs = None
    yield
    game.Battle.battle_ptr = None
    game.Battle.obs = None


def test_get_battle_data_decodes_json_and_sets_search_input(monkeypatch):
    class FakeSerialData:
        json = b'{"turn": 1}'
        data = b"abc"
        count = 3
        selectPlayer = 0

    monkeypatch.setattr(game.lib, "GetBattleData", lambda ptr: FakeSerialData())

    data = game._get_battle_data()

    assert data["turn"] == 1
    assert data["search_begin_input"] == "abc"


def test_battle_start_rejects_non_60_card_decks():
    with pytest.raises(ValueError, match="60 cards"):
        game.battle_start([1] * 59, [2] * 60)


def test_battle_start_returns_observation_and_sets_ptr(monkeypatch):
    class FakeSerialData:
        json = b'{"turn": 1}'
        data = b""
        count = 0
        selectPlayer = 0

    monkeypatch.setattr(game.lib, "BattleStart", lambda arg: StartData(battlePtr=99, errorPlayer=0, errorType=0))
    monkeypatch.setattr(game.lib, "GetBattleData", lambda ptr: FakeSerialData())

    obs, start_data = game.battle_start([1] * 60, [2] * 60)

    assert game.Battle.battle_ptr == 99
    assert start_data.battlePtr == 99
    assert obs["turn"] == 1


def test_battle_select_rejects_malformed_input():
    with pytest.raises(ValueError, match="select_list"):
        game.battle_select([1, "bad"])


def test_battle_select_raises_for_engine_errors(monkeypatch):
    game.Battle.battle_ptr = 10
    monkeypatch.setattr(game.lib, "Select", lambda ptr, arg, length: 30)

    with pytest.raises(ValueError, match="battle_ptr broken"):
        game.battle_select([0])


def test_battle_finish_and_visualize_data(monkeypatch):
    called = []

    def fake_finish(ptr):
        called.append(ptr)

    monkeypatch.setattr(game.lib, "BattleFinish", fake_finish)
    monkeypatch.setattr(game.lib, "VisualizeData", lambda ptr: b"visual")

    game.Battle.battle_ptr = 15
    game.battle_finish()
    result = game.visualize_data()

    assert called == [15]
    assert result == "visual"
