"""Three rules the linter did not have, one per bug that shipped on 10 August.

None of the three showed up as a red test, which is the entry criterion for a
rule in `lint_architecture.py`:

  R6  a test that READS a `records/` file must carry a skip guard. `records/` is
      transient local data and gets re-harvested; a census that pinned
      `registro_006_pasos_054_hasta_056.json` went red when a harvest took that
      board away, with nothing about the rule having changed (32a5537).
  R7  a gate that loads two arms must define AND call `provenance()`. Before
      6c08b87 both arms shared every module under `ptcg/`, so a change to any
      rule measured exactly zero -- and in this project a neutral result orders
      a revert. R7 found a live one the night it was written:
      `utils/gate_promoted_relay.py` had no such check.
  R8  inside the DISCARD block, the turn-scoped flags may only be read to build
      the horizon. On a discard FORCED by the opponent those flags describe what
      THEY spent, and since Xerosic's Machinations is itself a Supporter,
      `supporterPlayed` is True on every forced discard it can produce --
      `_protect_last_supporter` was unreachable code, not a misfiring rule
      (93a27eb).

EACH RULE IS TESTED IN BOTH DIRECTIONS, which is this project's standing rule
for anything that reports: it must flag a planted offender AND stay quiet on the
tree as it stands. A linter rule that only ever passes is indistinguishable from
one that is switched off -- and R6's first draft, which passed a green tree, was
flagging the assertion message "--snapshot-only no puede mirar records/": a
sentence about the directory, not a read of it.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "utils"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import lint_architecture as lint


def _escribir(tmp_path, nombre, fuente):
    destino = tmp_path / nombre
    destino.write_text(fuente, encoding="utf-8")
    return destino


# --------------------------------------------------------------------------
# R6


def test_r6_acusa_al_test_que_lee_un_registro_sin_guarda(tmp_path):
    archivo = _escribir(tmp_path, "test_falso.py", '''
"""Docstring citing registro_006_pasos_054_hasta_056.json as provenance."""
from pathlib import Path

def test_algo():
    datos = Path("records/registro_006_pasos_054_hasta_056.json").read_text()
    assert datos
''')
    fallos = lint.rule_6_records_are_transient([archivo])
    assert len(fallos) == 1, fallos
    assert fallos[0][0] == "R6"


def test_r6_calla_si_el_test_lleva_su_guarda(tmp_path):
    archivo = _escribir(tmp_path, "test_falso.py", '''
from pathlib import Path
import pytest

def test_algo():
    ruta = Path("records/registro_006_pasos_054_hasta_056.json")
    if not ruta.is_file():
        pytest.skip("records/ is transient local data")
    assert ruta.read_text()
''')
    assert lint.rule_6_records_are_transient([archivo]) == []


def test_r6_no_confunde_la_prosa_con_una_lectura(tmp_path):
    # The false positive the first draft produced: citing a record in a
    # docstring is how a finding carries its provenance, and an assertion
    # message that merely names the directory is a sentence, not a dependency.
    archivo = _escribir(tmp_path, "test_falso.py", '''
"""Written off registro_004_pasos_021_hasta_026.json step 26."""

def test_algo():
    assert 1 == 1, "--snapshot-only no puede mirar records/"
    assert True, "el registro_005 paso 64 quedo supersedido"
''')
    assert lint.rule_6_records_are_transient([archivo]) == []


def test_r6_esta_limpia_en_el_arbol():
    assert lint.rule_6_records_are_transient() == []


# --------------------------------------------------------------------------
# R7


_GATE_CON_PROCEDENCIA = '''
import selfplay as sp

def provenance(candidate, base):
    if candidate.score_option is base.score_option:
        raise SystemExit("los dos brazos son el MISMO agente")

def main():
    candidate = sp.load_agent("main.py", "arm_with")
    base = sp.load_agent("main.py", "arm_without")
    provenance(candidate, base)
'''


def test_r7_acusa_al_gate_de_dos_brazos_sin_procedencia(tmp_path):
    archivo = _escribir(tmp_path, "gate_falso.py", '''
import selfplay as sp

def main():
    candidate = sp.load_agent("main.py", "arm_with")
    base = sp.load_agent("main.py", "arm_without")
    return candidate, base
''')
    fallos = lint.rule_7_gates_check_provenance([archivo])
    assert len(fallos) == 1, fallos
    assert fallos[0][0] == "R7"
    assert "provenance" in fallos[0][3]


def test_r7_acusa_al_que_la_define_y_no_la_llama(tmp_path):
    # The failure that reads as compliance: the function is there, in the diff,
    # in the review -- and nothing invokes it.
    archivo = _escribir(tmp_path, "gate_falso.py",
                        _GATE_CON_PROCEDENCIA.replace("    provenance(candidate, base)\n", ""))
    fallos = lint.rule_7_gates_check_provenance([archivo])
    assert len(fallos) == 1 and "no la llama" in fallos[0][3], fallos


def test_r7_calla_con_el_gate_completo(tmp_path):
    archivo = _escribir(tmp_path, "gate_falso.py", _GATE_CON_PROCEDENCIA)
    assert lint.rule_7_gates_check_provenance([archivo]) == []


def test_r7_no_pide_procedencia_a_un_gate_de_un_solo_brazo(tmp_path):
    # `gate_coverage.py` and `gate_mutation.py` load no agent at all: they are
    # not two-arm gates and the rule must not invent work for them.
    archivo = _escribir(tmp_path, "gate_falso.py", '''
import selfplay as sp

def main():
    return sp.load_agent("main.py", "solo")
''')
    assert lint.rule_7_gates_check_provenance([archivo]) == []


def test_r7_esta_limpia_en_el_arbol():
    # It was NOT clean when it was written: gate_promoted_relay.py loaded two
    # arms, patched two seams by two different routes and never asked whether
    # either patch had landed. That is what this rule is for.
    assert lint.rule_7_gates_check_provenance() == []


# --------------------------------------------------------------------------
# R8


def test_r8_acusa_la_bandera_cruda_en_el_bloque_discard(tmp_path):
    archivo = _escribir(tmp_path, "card_falso.py", '''
def score_option(state, context, select):
    if context == SelectContext.PLAY:
        pass
    elif context == SelectContext.DISCARD:
        _forced_discard = select.effect is not None
        _supporter_spent = state.supporterPlayed and not _forced_discard
        _energy_spent = state.energyAttached and not _forced_discard
        if not state.supporterPlayed:
            score = 5
    return score
''')
    fallos = lint.rule_8_discard_reads_its_horizon(archivo)
    assert len(fallos) == 1, fallos
    assert fallos[0][0] == "R8" and "supporterPlayed" in fallos[0][3]


def test_r8_permite_las_dos_lineas_que_construyen_el_horizonte(tmp_path):
    archivo = _escribir(tmp_path, "card_falso.py", '''
def score_option(state, context, select):
    if context == SelectContext.DISCARD:
        _forced_discard = select.effect is not None
        _supporter_spent = state.supporterPlayed and not _forced_discard
        _energy_spent = state.energyAttached and not _forced_discard
        if not _supporter_spent:
            score = 5
    return score
''')
    assert lint.rule_8_discard_reads_its_horizon(archivo) == []


def test_r8_no_mira_fuera_del_bloque_discard(tmp_path):
    # Outside a forced discard the flags are OURS and reading them raw is
    # correct. A rule that forbade them everywhere would be asking the code to
    # lie about the turn it is on.
    archivo = _escribir(tmp_path, "card_falso.py", '''
def score_option(state, context, select):
    if context == SelectContext.PLAY:
        if not state.supporterPlayed and not state.energyAttached:
            score = 5
    return score
''')
    assert lint.rule_8_discard_reads_its_horizon(archivo) == []


def test_r8_esta_limpia_en_card_py():
    assert lint.rule_8_discard_reads_its_horizon() == []
