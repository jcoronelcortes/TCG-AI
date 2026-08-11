"""The whole night, as a script somebody else can run.

T4.1 of docs/testing-plan-2026-08.md. The pipeline already existed -- the runs
of 6-7 and 8-9 August are it -- but it existed as a sequence of commands in
somebody's terminal, which means the night could only be repeated by the person
who ran it. A night nobody else can relaunch is not infrastructure.

WHAT IT RUNS, in the order the dependencies want:

    suite -> lint -> corpus -> coverage -> mutation
          -> differential oracle -> invariant monitor
          -> permutation -> hypothesis soak -> matchup matrix

The gates come first because everything after them is only worth reading on a
green tree, and a night built on a red baseline attributes its own damage to the
wrong stage.

THE RULE THIS SCRIPT EXISTS TO ENFORCE, and it is the lesson of the two days
that produced it. Four detectors in this repository have reported their own bugs
as defects of the agent: the differential oracle over three rounds, the
invariant monitor twice in one morning, and the mutation gate twice more for two
unrelated causes. In every case the numbers looked like findings.

So a detector here does not get to report a number until it has proved, in the
same run, that it can both catch a planted defect and stay quiet without one.
When a self-test fails the stage is marked INVALID and its output is quarantined
in the report rather than summarised: an unvalidated number is not a smaller
finding, it is not a finding at all.

PROFILES, because "the night" is not one length:

    --quick    a few minutes. Everything runs, nothing runs long. For "is the
               pipeline itself still working".
    (default)  ~1 hour. The detectors get enough games to mean something.
    --full     hours. The soak, plus the matchup matrix, which is the only
               stage that answers "does it win more".

Nothing here writes to `main.py` or `ptcg/` -- except the mutation stage, which
rewrites the file it is mutating for the length of one test run and restores it
through `mutation_probe._protect` (atexit plus SIGINT/SIGTERM). That is why it
is the one stage that must not run while anything else is reading the tree.

Usage:
    python utils/nightly.py --quick
    python utils/nightly.py --since HEAD~5
    python utils/nightly.py --full --since origin/main
"""

import argparse
import datetime
import os
import re
import subprocess
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

PROFILES = {
    # games for the oracle / monitor / permutation, hypothesis examples,
    # games per opponent for the matrix (None = do not run the matrix)
    "quick": dict(games=40, examples=100, matrix=None, decks=2, coverage=False),
    "normal": dict(games=400, examples=2000, matrix=None, decks=6, coverage=True),
    "full": dict(games=2000, examples=20000, matrix=200, decks=19, coverage=True),
}

OK, FAILED, INVALID, SKIPPED = "OK", "FALLO", "INVALIDO", "SALTADO"
FINDINGS = "HALLAZGOS"


class Stage:
    """One step, its log, and how to read a single line out of it."""

    def __init__(self, key, title, argv, summarise, env=None, optional=False,
                 findings_exit=False):
        # `findings_exit`: a non-zero exit from this tool means IT FOUND
        # SOMETHING, not that it broke. The permutation probe and the mutation
        # gate both report that way, and calling their findings a failure is how
        # a pipeline teaches people to ignore its red.
        self.findings_exit = findings_exit
        self.key = key
        self.title = title
        self.argv = argv
        self.summarise = summarise
        self.env = env or {}
        self.optional = optional
        self.status = SKIPPED
        self.summary = ""
        self.seconds = 0.0
        self.log = None


def _tail(text, lines=25):
    return "\n".join(text.strip().splitlines()[-lines:])


def _grep(pattern, text, default="(sin resumen)"):
    found = [ln.strip() for ln in text.splitlines() if re.search(pattern, ln)]
    return found[-1] if found else default


def _oracle_summary(out):
    """Games judged and how many findings, which is the pair worth one line."""
    judged = _grep(r"ataques juzgados", out, "")
    kinds = [ln.strip() for ln in out.splitlines()
             if re.match(r"\s+(PHANTOM_KO|MISSED_KO|DAMAGE_DRIFT):", ln)]
    if not kinds:
        return f"{judged} | sin hallazgos"
    return f"{judged} | " + ", ".join(kinds)


def _counts_summary(out):
    """Every `NAME: n` count the tool printed, or the explicit nothing."""
    counts = [ln.strip() for ln in out.splitlines()
              if re.match(r"\s+[A-Z_]{4,}: \d+", ln)]
    if counts:
        return ", ".join(counts)
    return _grep(r"NINGUNA|ninguna|0 |sin ", out)


SELF_TEST_FAILED_SUMMARY = "el auto-test del detector fallo: sus numeros no valen"

# What a detector prints when it refuses to run. Both of this project's
# validated detectors abort with one of these before producing any number.
SELF_TEST_FAILURES = ("AUTO-TEST FALLIDO", "AUTO-TEST IMPOSIBLE")


def classify(output, code, findings_exit):
    """(status, quarantine) for one finished stage.

    The order matters and it is the whole point of this script. A stage whose
    SELF-TEST failed is INVALID no matter what its exit code was -- including
    zero, because a detector that cannot validate itself and then reports
    "nothing found" is the most misleading result of the three. Its summary is
    replaced rather than shown: an unvalidated number is not a smaller finding,
    it is not a finding.

    Below that, a non-zero exit means FINDINGS for the tools that report by
    exit code (the permutation probe, the mutation gate, the corpus) and FAILED
    for everything else.
    """
    if any(mark in output for mark in SELF_TEST_FAILURES):
        return INVALID, True
    if code == 0:
        return OK, False
    return (FINDINGS if findings_exit else FAILED), False


def run(stage, outdir, index):
    stage.log = outdir / f"{index:02d}_{stage.key}.log"
    env = {**os.environ, **stage.env}
    started = time.time()
    print(f"[{index:02d}] {stage.title} ...", flush=True)
    try:
        result = subprocess.run(stage.argv, cwd=_ROOT, env=env,
                                capture_output=True, text=True)
        output = (result.stdout or "") + (result.stderr or "")
        code = result.returncode
    except OSError as exc:
        output, code = f"no se pudo lanzar: {exc!r}", 127
    stage.seconds = time.time() - started
    stage.log.write_text(output, encoding="utf-8")

    stage.status, quarantined = classify(output, code, stage.findings_exit)
    stage.summary = (SELF_TEST_FAILED_SUMMARY if quarantined
                     else stage.summarise(output))
    print(f"     {stage.status}  {stage.seconds:.0f}s  {stage.summary}", flush=True)
    return stage


def build_stages(profile, since, decks):
    p = PROFILES[profile]
    py = sys.executable
    stages = [
        Stage("suite", "La suite", [py, "-m", "pytest", "-q"],
              lambda out: _grep(r"passed|failed|error", out)),
        Stage("lint", "Lint de arquitectura", [py, "utils/lint_architecture.py"],
              lambda out: _grep(r"violation|no violations", out)),
        Stage("corpus", "Corpus dorado local", [py, "tests/golden_corpus.py"],
              lambda out: _grep(r"[Cc]orpus", out), findings_exit=True),
    ]

    if p["coverage"]:
        stages.append(Stage(
            "coverage", "Cobertura contra los suelos",
            [py, "-c",
             "import subprocess,sys;"
             "subprocess.run([sys.executable,'-m','pytest','-q','--cov=main',"
             "'--cov=ptcg','--cov-report=json:coverage.json'],check=False);"
             "sys.exit(subprocess.run([sys.executable,'utils/gate_coverage.py',"
             "'--check','coverage.json']).returncode)"],
            lambda out: _grep(r"modulos|SUELO", out)))

    stages.append(Stage(
        "mutation", "Gate de mutacion sobre las lineas nuevas",
        [py, "utils/gate_mutation.py", "--changed", since],
        lambda out: _grep(r"SUPERVIVIENTES|El gate pasa|Ningun fichero", out),
        findings_exit=True))

    for deck in decks:
        name = Path(deck).stem
        stages.append(Stage(
            f"oracle_{name}", f"Oraculo diferencial vs {name}",
            [py, "utils/differential_oracle.py", "--games", str(p["games"]),
             "--opponent", deck],
            _oracle_summary))

    stages += [
        Stage("monitor", "Monitor de invariantes",
              [py, "utils/invariant_monitor.py", "--games", str(p["games"])],
              _counts_summary),
        Stage("permutation", "Sonda de permutacion del menu",
              [py, "utils/permutation_probe.py", "--games", str(p["games"])],
              lambda out: " | ".join(
                  ln.strip() for ln in out.splitlines()
                  if re.match(r"(decisions compared|order-dependent)", ln)
              ) or _grep(r"decision", out),
              findings_exit=True),
        Stage("hypothesis", f"Soak de propiedades ({p['examples']} ejemplos)",
              [py, "-m", "pytest", "-q", "tests/test_invariants.py",
               "tests/test_properties_of_any_legal_board.py"],
              lambda out: _grep(r"passed|failed", out),
              env={"PTCG_HYPOTHESIS_EXAMPLES": str(p["examples"])}),
        # THE THREE INSTRUMENTS OF 11 AUGUST, in the pipeline rather than in
        # somebody's terminal -- which is this file's whole reason for existing.
        # All three read the frozen corpus and none of them writes to the tree.
        Stage("rules", "Censo de reglas: las que nunca disparan",
              [py, "utils/rule_census.py", "--corpus", "--games", str(p["games"])],
              lambda out: " | ".join(
                  ln.strip() for ln in out.splitlines()
                  if re.match(r"(CENSO DE REGLAS|NUNCA EVALUADA|EVALUADA, NUNCA)", ln)
              ) or _grep(r"regla", out)),
        Stage("duplicates", "Auditoria de doble copia en el descarte",
              [py, "utils/duplicate_protection_audit.py"],
              lambda out: _grep(r"pares con score IDENTICO|ninguna carta", out)),
        Stage("fuel", "El coste que paga con el combustible que compra",
              [py, "utils/fodder_ladder_audit.py"],
              lambda out: _grep(r"inversiones|ninguna:", out)),
    ]

    if p["matrix"]:
        stages.append(Stage(
            "matrix", "Matriz de matchups",
            [py, "utils/matchup_matrix.py", "--games", str(p["matrix"])],
            lambda out: _grep(r"winrate|ponderad", out), optional=True))
    return stages


def write_report(stages, outdir, profile, head, started):
    lines = [f"# Corrida nocturna — {started:%Y-%m-%d %H:%M}", "",
             f"Perfil `{profile}`, HEAD `{head}`.", "",
             "| Etapa | Estado | Tiempo | Resumen |", "|---|---|---:|---|"]
    for stage in stages:
        # The summaries come from tool output and several of them carry a `|`,
        # which silently splits a markdown row into extra columns.
        cell = re.sub(r"\s+", " ", stage.summary).replace("|", "/")
        lines.append(f"| {stage.title} | **{stage.status}** | "
                     f"{stage.seconds:.0f}s | {cell} |")

    invalid = [s for s in stages if s.status == INVALID]
    failed = [s for s in stages if s.status == FAILED]
    found = [s for s in stages if s.status == FINDINGS]

    lines += ["", "## Lectura", ""]
    if invalid:
        lines.append("**No creas los numeros de estas etapas.** Su auto-test "
                     "fallo, que es distinto de encontrar un defecto:")
        for stage in invalid:
            lines.append(f"- `{stage.key}` — ver `{stage.log.name}`")
        lines.append("")
    if failed:
        lines.append("Etapas en rojo:")
        for stage in failed:
            lines.append(f"- `{stage.key}` — {stage.summary} "
                         f"(`{stage.log.name}`)")
        lines.append("")
    if found:
        lines.append("Etapas que ENCONTRARON algo (salida distinta de cero "
                     "porque ese es su informe, no porque esten rotas):")
        for stage in found:
            lines.append(f"- `{stage.key}` — {stage.summary} "
                         f"(`{stage.log.name}`)")
        lines.append("")
    if not invalid and not failed:
        lines.append("Todas las etapas verdes y todos los detectores "
                     "validados. Un hallazgo de esta corrida se puede leer "
                     "como un hallazgo.")
        lines.append("")

    lines += ["## Colas de cada log", ""]
    for stage in stages:
        if stage.log and stage.log.exists():
            lines += [f"### {stage.title} (`{stage.log.name}`)", "", "```",
                      _tail(stage.log.read_text(encoding="utf-8")), "```", ""]

    report = outdir / "REPORT.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    return report


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--quick", action="store_true", help="minutos")
    parser.add_argument("--full", action="store_true", help="horas, con matriz")
    parser.add_argument("--since", default="HEAD~1",
                        help="ref de git para el gate de mutacion")
    parser.add_argument("--opponents", default=str(_ROOT / "deck" / "opponents"))
    args = parser.parse_args(argv)

    profile = "quick" if args.quick else "full" if args.full else "normal"
    decks = sorted(Path(args.opponents).glob("*.csv"))[:PROFILES[profile]["decks"]]
    if not decks:
        print(f"no hay mazos en {args.opponents}", file=sys.stderr)
        return 2

    started = datetime.datetime.now()
    outdir = _ROOT / "log" / f"nightly_{started:%Y-%m-%d_%H%M}"
    outdir.mkdir(parents=True, exist_ok=True)
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=_ROOT,
                          capture_output=True, text=True).stdout.strip()
    print(f"Perfil {profile}, HEAD {head}, salida en {outdir}\n")

    stages = build_stages(profile, args.since, [str(d) for d in decks])
    for index, stage in enumerate(stages):
        run(stage, outdir, index)
        # THE BASELINE HAS TO BE GREEN. Everything downstream measures the tree,
        # and a red tree makes every number after it unattributable.
        if stage.key in ("suite", "lint") and stage.status != OK:
            print(f"\nLa etapa `{stage.key}` esta en rojo: la noche para aqui. "
                  f"Una corrida sobre un arbol roto atribuye su propio dano a "
                  f"la etapa equivocada.", file=sys.stderr)
            break

    report = write_report(stages, outdir, profile, head, started)
    print(f"\nInforme: {report}")
    # FINDINGS is not a failure: the exit code says whether the PIPELINE is
    # sound, not whether it found anything. A night that finds something and
    # returns 1 for it trains people to ignore the 1.
    bad = [s for s in stages if s.status in (FAILED, INVALID) and not s.optional]
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
