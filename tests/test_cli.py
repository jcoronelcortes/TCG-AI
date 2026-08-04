"""The command line of `utils/`: every script must be launchable and coherent.

This file exists because of a bug it would have caught. A rename moved
`args.aplicar` to `args.apply` across the project -- the same word was a field
of the rules engine -- while the flag stayed `--aplicar`. Three scripts kept
parsing a flag nobody read and reading an attribute nobody set, and they raised
`AttributeError` the moment you passed it. Nothing noticed, because the CLI had
no test at all: the suite exercises the agent, never the tools around it.

Two checks, both static, both cheap:

  1. every `args.X` a script reads is a `dest` some `add_argument` produces;
  2. every option string is spelled the way the rest of the project is.

They are static on purpose. Running the tools would mean playing games, hitting
the network or writing into `records/`; what broke here was the wiring, and the
wiring is visible in the source.
"""

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = sorted(p for p in (ROOT / "utils").glob("*.py"))

# argparse's own, plus what a parser exposes that no `add_argument` declares.
BUILT_IN = {"help", "func", "parse_args", "parse_known_args"}


def _parser_arguments(tree):
    """(dests declared, option strings declared) of every add_argument call."""
    dests, options = set(), set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_argument"):
            continue
        explicit = next((kw.value.value for kw in node.keywords
                         if kw.arg == "dest" and isinstance(kw.value, ast.Constant)), None)
        names = [a.value for a in node.args
                 if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        if explicit:
            dests.add(explicit)
        elif names:
            # argparse takes the first long option, or the positional name
            long = next((n for n in names if n.startswith("--")), None)
            dests.add((long or names[0]).lstrip("-").replace("-", "_"))
        options.update(n for n in names if n.startswith("-"))
    return dests, options


def _attributes_read_from_args(tree):
    """`args.X` / `opts.X`: what the script expects the parser to have set."""
    read = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                and node.value.id in ("args", "opts", "ns"):
            read.add(node.attr)
    return read


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_every_flag_the_script_reads_is_one_it_declares(script):
    tree = ast.parse(script.read_text(encoding="utf-8"))
    dests, _ = _parser_arguments(tree)
    if not dests:
        pytest.skip("no command line")
    missing = _attributes_read_from_args(tree) - dests - BUILT_IN
    assert not missing, (
        f"{script.name} reads {sorted(missing)} but its parser never sets it: "
        "the flag and the attribute drifted apart")


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_the_option_strings_are_english(script):
    """The tools are read by people who do not speak Spanish."""
    _, options = _parser_arguments(ast.parse(script.read_text(encoding="utf-8")))
    spanish = re.compile(
        r"^--(partidas|rival|rivales|pesos|espejo|censo|todos|candidato|solo|"
        r"salida|destino|origen|semilla|titulo|campos|listar|detalle|volcar|"
        r"aplicar|verificar|referencia|hallazgo|indice|autopsia|intervalo|"
        r"progreso|actualizar|desde|hasta|registros|control-carta|sin-criba|"
        r"sin-extra|solo-indice|conservar-replays|max-episodios)$")
    left = sorted(o for o in options if spanish.match(o))
    assert not left, f"{script.name} still offers {left}"
