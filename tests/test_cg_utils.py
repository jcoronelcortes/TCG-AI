import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cg.utils import json_to_dataclass, to_dataclass


@dataclass
class Child:
    name: str
    value: int


@dataclass
class Parent:
    title: str
    child: Child
    children: list[Child]


def test_to_dataclass_converts_nested_structure():
    payload = {
        "title": "root",
        "child": {"name": "leaf", "value": 1},
        "children": [{"name": "first", "value": 2}, {"name": "second", "value": 3}],
    }

    result = to_dataclass(payload, Parent)

    assert isinstance(result, Parent)
    assert result.title == "root"
    assert result.child.name == "leaf"
    assert result.children[1].value == 3


def test_to_dataclass_returns_none_for_none_input():
    assert to_dataclass(None, Parent) is None


def test_json_to_dataclass_parses_bytes_payload():
    payload = json.dumps({
        "title": "json-root",
        "child": {"name": "json-child", "value": 7},
        "children": [],
    }).encode("utf-8")

    result = json_to_dataclass(payload, Parent)

    assert isinstance(result, Parent)
    assert result.child.value == 7
    assert result.children == []
