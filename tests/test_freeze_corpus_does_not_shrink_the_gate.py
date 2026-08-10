"""Accepting a flip may not cost the gate half its games.

`tests/test_the_frozen_corpus_runs_on_a_clean_checkout.py` fails with "revisa
los flips y luego: python utils/freeze_corpus.py", and until August 2026 that
command did two things instead of one: it rewrote the snapshot, yes, but it
first REBUILT `tests/corpus/frozen_records.json.gz` out of `records/`.

`records/` is transient and git-ignored. A working tree holds whatever games
were last analysed -- measured on this repository: **13** -- while the
committed bundle holds every game somebody ever froze: **50, 3 580 decisions**.
Following the instruction on the failing test would have thrown 37 games of
coverage away, and because the bundle is a gzip, the diff of that commit shows
one unreadable binary blob: nobody reviewing the pull request could see it.

The two halves of the fix, both pinned here:

  * `--snapshot-only` re-plays the bundle THAT IS ALREADY COMMITTED and writes
    only the snapshot. That is the operation "accept the reviewed flips", and
    it is what the failing test now names.
  * the plain form REFUSES to rebuild a bundle smaller than the frozen one
    unless `--force`, and says which of the three things you probably meant.

Neither test touches the real corpus: `build_bundle` and `frozen_records` are
the two seams, and both are patched.

See [[freeze-corpus-reconstruye-el-bundle-desde-records]] and
[[corpus-dorado-resnapshot-silencioso]] (the other way the corpus lies).
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT, ROOT / "utils", ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import freeze_corpus as fc  # noqa: E402


def _bundle(n):
    return {f"registro_{i:03d}.json": {"seat": 0, "steps": []} for i in range(n)}


def test_it_refuses_to_rebuild_a_bundle_smaller_than_the_frozen_one(
        monkeypatch, capsys):
    monkeypatch.setattr(fc, "build_bundle", lambda: _bundle(13))
    monkeypatch.setattr(fc.gc, "frozen_records", lambda: _bundle(50))
    monkeypatch.setattr(fc, "write", lambda bundle: pytest.fail(
        "reescribio el bundle: se acaban de perder 37 registros"))

    assert fc.main([]) == 2
    err = capsys.readouterr().err
    assert "--snapshot-only" in err and "--force" in err


def test_force_is_the_way_to_shrink_it_on_purpose(monkeypatch):
    escrito = []
    monkeypatch.setattr(fc, "build_bundle", lambda: _bundle(13))
    monkeypatch.setattr(fc.gc, "frozen_records", lambda: _bundle(50))
    monkeypatch.setattr(fc, "write", lambda bundle: escrito.append(len(bundle)))

    assert fc.main(["--force"]) == 0
    assert escrito == [13]


def test_a_bundle_that_grows_needs_no_flag(monkeypatch):
    escrito = []
    monkeypatch.setattr(fc, "build_bundle", lambda: _bundle(50))
    monkeypatch.setattr(fc.gc, "frozen_records", lambda: _bundle(13))
    monkeypatch.setattr(fc, "write", lambda bundle: escrito.append(len(bundle)))

    assert fc.main([]) == 0
    assert escrito == [50]


def test_snapshot_only_replays_the_frozen_bundle_and_never_the_local_records(
        monkeypatch):
    replayed = []
    monkeypatch.setattr(fc.gc, "frozen_records", lambda: _bundle(50))
    monkeypatch.setattr(fc, "build_bundle", lambda: pytest.fail(
        "--snapshot-only no puede mirar records/"))
    monkeypatch.setattr(fc, "write_snapshot",
                        lambda bundle: replayed.append(len(bundle)))

    assert fc.main(["--snapshot-only"]) == 0
    assert replayed == [50]
