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


def test_the_answer_to_a_menu_is_stored_on_the_next_step(monkeypatch, tmp_path):
    """The alignment itself, which is what the tool got wrong for months.

    The three-option menu of step 0 is answered by the action of step 1 ([2]),
    NOT by the one stored beside it ([0]). An agent that replies [2] agrees with
    the log; reading the action off the same step would score it a mismatch and
    send the reader to the wrong step.
    """
    log_path = tmp_path / "game.json"
    log_path.write_text(
        json.dumps(
            {
                "steps": [
                    [{"observation": {"select": {"option": [{"type": 1}, {"type": 2}, {"type": 3}], "minCount": 1, "maxCount": 1}, "current": {"turn": 1}}, "action": [0]}],
                    [{"observation": {"select": {"option": [{"type": 1}], "minCount": 1, "maxCount": 1}, "current": {"turn": 1}}, "action": [2]}],
                    [{"observation": {"select": None}, "action": []}],
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        log_replay, "agent",
        lambda obs: [2] if len(obs["select"]["option"]) == 3 else [0])

    summary = log_replay.replay_log(str(log_path))

    assert summary["processed"] == 2
    assert summary["compared"] == 2
    assert summary["matched"] == 2
    assert summary["mismatched"] == 0


def test_logged_answer_is_none_when_the_log_does_not_hold_it(tmp_path):
    """The last menu of a file has no answer yet, and a seat can be missing."""
    steps = [
        [{"action": [0]}, {"action": [1]}],
        [{"action": [3]}],
    ]

    assert log_replay._logged_answer(steps, 0, 0) == [3]
    assert log_replay._logged_answer(steps, 0, 1) is None   # seat not on step 1
    assert log_replay._logged_answer(steps, 1, 0) is None   # last step


def test_replay_log_counts_matches_and_ignored_entries(monkeypatch, tmp_path):
    log_path = tmp_path / "game.json"
    log_path.write_text(
        json.dumps(
            {
                "steps": [
                    [{"observation": {"select": {"option": [{"type": 1}, {"type": 2}], "minCount": 1, "maxCount": 1}, "current": {"turn": 1}}, "action": [0]}],
                    [{"observation": {"select": {"option": [{"type": 1}], "minCount": 1, "maxCount": 1}, "current": {"turn": 2}}, "action": "bad"}],
                    [{"observation": {"select": None}, "action": [0]}],
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
