# Rename maps

The project was written in Spanish and translated to English in place: first
the documentation, then every comment and docstring, then the identifiers, the
file and folder names, the command line, and finally the rule labels.

These 40 files are what drove that, and they are kept for one reason: they are
the only record of **what became what**. A note, a commit message or a
screenshot written before the rename quotes the old spelling, and this is where
you look it up.

## What a map looks like

One rename per line, tab separated, with an optional flag:

```
old_name	new_name
old_name	new_name	str    # the matching string literals move too
old_name	new_name	mod    # it is a module, so import paths move too
old_name	new_name	code   # identifier only: the literals are something
                               # else, and each one was checked
```

The comment at the top of each map says what the batch covers and, where a
name needed a flag, why. Those explanations are the useful part: they are the
record of which literals were data and which were code.

## The interesting ones

| Map | What it holds |
|---|---|
| `11-estado.tsv` | `ESTADO` -> `AGENT_STATE` and the belief zones |
| `09-motor-reglas.tsv` | the rules engine: `_ReglaFija` -> `_FixedRule` |
| `18-ptcg-modules.tsv` | the package layout: `cartas` -> `cards`, `turno` -> `turn` |
| `23-cli-dests.tsv` | the argparse flags and the attributes they set |
| `25-rule-labels.tsv` | the 260 rule labels, the last thing to move |

## Replaying one

The tool that applied them still lives in `utils/rename_code.py` and still
reads this format:

```bash
python utils/rename_code.py report docs/history/rename-maps/25-rule-labels.tsv
```

`report` is the interesting command even today: it refuses a rename when the
new name would collide inside a scope, when a parameter is passed by keyword
somewhere else, when a class field is read from another file, or when the name
also exists as a string literal. Every one of those guards is there because a
batch broke something first.
