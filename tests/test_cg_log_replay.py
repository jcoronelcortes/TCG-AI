import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import utils.log_replay as log_replay


def test_load_log_reads_steps(tmp_path):
    log_path = tmp_path / "game.json"
    log_path.write_text(json.dumps({"steps": [[{"observation": {"select": None}, "action": []}]]}), encoding="utf-8")

    steps = log_replay.load_log(str(log_path))

    assert len(steps) == 1
    assert steps[0][0]["action"] == []


def test_load_log_raises_for_invalid_payload(tmp_path):
    log_path = tmp_path / "bad.json"
    log_path.write_text(json.dumps({"foo": "bar"}), encoding="utf-8")

    with pytest.raises(ValueError):
        log_replay.load_log(str(log_path))


@pytest.mark.parametrize(
    ("action", "select", "expected"),
    [
        ([0], {"option": [{"type": 1}], "minCount": 1, "maxCount": 1}, [0]),
        ([1], {"option": [{"type": 1}], "minCount": 1, "maxCount": 1}, None),
        ([], {"option": [{"type": 1}], "minCount": 1, "maxCount": 1}, [0]),
    ],
)
def test_canonical_action_handles_valid_and_invalid_choices(action, select, expected):
    assert log_replay._canonical_action(action, select) == expected


def test_replay_log_counts_matches_and_ignored_entries(monkeypatch, tmp_path):
    log_path = tmp_path / "game.json"
    log_path.write_text(
        json.dumps(
            {
                "steps": [
                    [{"observation": {"select": {"option": [{"type": 1}, {"type": 2}], "minCount": 1, "maxCount": 1}, "current": {"turn": 1}}, "action": [0]}],
                    [{"observation": {"select": {"option": [{"type": 1}], "minCount": 1, "maxCount": 1}, "current": {"turn": 2}}, "action": "bad"}],
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(log_replay, "agent", lambda obs: [1])

    summary = log_replay.replay_log(str(log_path))

    assert summary["processed"] == 2
    assert summary["compared"] == 1
    assert summary["matched"] == 0
    assert summary["mismatched"] == 1
    assert summary["ignored"] == 1


def test_replay_log_stops_on_interactive_quit(monkeypatch, tmp_path):
    log_path = tmp_path / "game.json"
    log_path.write_text(json.dumps({"steps": [[{"observation": {"select": {"option": [{"type": 1}], "minCount": 1, "maxCount": 1}, "current": {"turn": 1}}, "action": [0]}]]}), encoding="utf-8")

    monkeypatch.setattr(log_replay, "agent", lambda obs: [0])
    monkeypatch.setattr("builtins.input", lambda *args, **kwargs: "q")

    summary = log_replay.replay_log(str(log_path), interactive=True)

    assert summary["processed"] == 1
    assert summary["compared"] == 0
