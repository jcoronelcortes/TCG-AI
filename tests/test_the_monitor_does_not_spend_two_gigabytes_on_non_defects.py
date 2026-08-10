"""`--dump` wrote 196 575 files and 2.1 GB to record nothing.

The night of 9-10 August ran the invariant monitor over 20 000 games. The five
invariants that are defects came back at ZERO --- the result you want --- and
the dump directory came back at **2.1 GB across 196 575 JSON files**, every one
of them a `STALE_FLAG` or a `STALE_READ`.

Neither is a defect, and the monitor's own docstring is the authority on that:
a flag standing on a dead premise "harms nothing if nobody looks at it", and
the first version of the file reported 440 stale episodes that were not bugs.
They come out in the tens of thousands on any real run.

A dump that costs two gigabytes to record nothing is not a dump. It is a way of
burying the one observation that matters on the night it finally lands, under
two hundred thousand that do not.

So `--dump` now writes only the kinds that ARE defects, and says out loud how
many it left out --- because a silent cap reads as "that is all there was" when
it means "that is all that was written". These tests pin both halves.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "utils") not in sys.path:
    sys.path.insert(0, str(ROOT / "utils"))

from invariant_monitor import DEFECT_KINDS, dump


def finding(kind, n):
    return {"kind": kind, "game": n, "step": n, "detail": f"{kind} {n}",
            "observation": {"current": {"turn": n}}}


@pytest.fixture
def hallazgos():
    return ([finding("STALE_FLAG", i) for i in range(20)]
            + [finding("STALE_READ", i) for i in range(15)]
            + [finding("DECK_BELIEF", 1), finding("ILLEGAL_INDEX", 2)])


def test_the_noise_is_not_written(tmp_path, hallazgos):
    escritos = dump(hallazgos, tmp_path)
    assert len(escritos) == 2, "vuelve a volcar los 35 no-defectos"
    nombres = sorted(Path(p).name for p in escritos)
    assert nombres[0].startswith("deck_belief")
    assert nombres[1].startswith("illegal_index")


def test_the_real_defects_are_still_written(tmp_path, hallazgos):
    """Sensitivity: the filter must not swallow the finding it exists to expose."""
    escritos = dump(hallazgos, tmp_path)
    assert len(list(tmp_path.glob("*.json"))) == len(escritos) == 2


def test_asking_for_everything_still_gets_everything(tmp_path, hallazgos):
    """`kinds=None` is the escape hatch behind `--dump-kinds all`."""
    escritos = dump(hallazgos, tmp_path, None)
    assert len(escritos) == len(hallazgos) == 37


def test_stale_flag_and_stale_read_are_the_two_left_out(tmp_path):
    """Pinned by name, so adding a kind to the monitor is a deliberate choice.

    A new kind is NOT dumped until somebody puts it in DEFECT_KINDS, which is
    the safe default: the failure mode this guards is a dump nobody reads, not
    a finding nobody records.
    """
    assert "STALE_FLAG" not in DEFECT_KINDS
    assert "STALE_READ" not in DEFECT_KINDS
    for kind in ("DECK_BELIEF", "ILLEGAL_INDEX", "END_EMPTY_BENCH",
                 "ENERGY_CAP", "DOUBLE_ATTACH", "AGENT_RAISED"):
        assert kind in DEFECT_KINDS, f"{kind} dejaria de volcarse"


def test_the_observation_travels_with_the_violation(tmp_path):
    """The whole point of a dump is that the board comes with it."""
    import json
    escritos = dump([finding("DECK_BELIEF", 7)], tmp_path)
    guardado = json.loads(Path(escritos[0]).read_text())
    assert guardado["observation"]["current"]["turn"] == 7
    assert guardado["violation"]["kind"] == "DECK_BELIEF"
