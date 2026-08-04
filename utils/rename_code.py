"""Renames identifiers across the project, and PROVES that nothing else changed.

The translation of comments and docstrings had a gate that made it safe: the AST
had to come out identical. A rename cannot use that gate -- the AST is exactly
what changes -- so it uses the next best thing: the OLD file's AST, with the
same map applied symbolically, must equal the NEW file's AST. That proves two
things at once, and they are the two ways a rename goes wrong:

  * nothing but names changed (no line got lost, no expression got rewritten);
  * every occurrence moved, and only the intended ones (a name left behind or a
    rename that leaked into an unrelated symbol shows up as a mismatch).

What it does NOT prove is that the new name is the right one, or that the map
did not merge two distinct symbols into one. That is what `pytest` and the
golden corpus are for, and why the map is applied in small batches.

The map is a TSV, one rename per line, with an optional third column:

    old_name<TAB>new_name
    old_name<TAB>new_name<TAB>str     # also rewrite exact string literals
    old_name<TAB>new_name<TAB>mod     # also rewrite it inside import paths

`str` is for the handful of names that are also written as strings: the targets
of `monkeypatch.setattr(mod, "name")` and the path constants of the
architecture lint. Nothing else touches strings -- rule labels stay as they are.

`mod` is for renaming a module or package, and it has to be explicit: the parts
of a dotted import path are ordinary NAME tokens, so without this the first
local called `dano` would silently turn `ptcg.calculo.dano` into a module that
does not exist. Names imported FROM a module are identifiers, not path parts,
and are always renamed.

`verify` compares against git HEAD, so each batch has to be COMMITTED before
the next one starts: otherwise the previous batch's renames show up as
"more than names changed" and the proof stops meaning anything.

Usage:
    python utils/rename_code.py report <map.tsv> [path ...]
    python utils/rename_code.py apply  <map.tsv> [path ...]
    python utils/rename_code.py verify <map.tsv> [path ...]   # vs git HEAD

With no paths it walks the project (main.py, ptcg/, utils/, tests/, deck/);
`cg/` is vendored and never touched.
"""

import ast
import io
import subprocess
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ("main.py", "ptcg", "utils", "tests", "deck")
SKIP_PARTS = {"cg", ".venv", ".venv-1", "__pycache__", ".git"}


# --------------------------------------------------------------------------- io
def project_files(paths):
    out = []
    for raw in (paths or TARGETS):
        p = Path(raw)
        if not p.is_absolute():
            p = ROOT / p
        if p.is_file() and p.suffix == ".py":
            out.append(p)
        elif p.is_dir():
            out += [f for f in sorted(p.rglob("*.py"))
                    if not SKIP_PARTS & set(f.relative_to(ROOT).parts)]
    return [f for f in out if not SKIP_PARTS & set(f.relative_to(ROOT).parts)]


def read_map(path):
    renames, in_strings, in_modules = {}, set(), set()
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split("\t")
        old, new = parts[0].strip(), parts[1].strip()
        if old == new:
            continue
        renames[old] = new
        flag = parts[2].strip() if len(parts) > 2 else ""
        if flag == "str":
            in_strings.add(old)
        elif flag == "mod":
            in_modules.add(old)
    return renames, in_strings, in_modules


# ------------------------------------------------------------------ token pass
def rewrite(src, renames, in_strings, in_modules=frozenset()):
    """Rewrites NAME tokens (and declared string literals) from the map.

    `path_state` tracks whether the current NAME is part of a dotted import
    path, where a rename is only allowed for names flagged `mod`.
    """
    out = []
    lines = src.splitlines(keepends=True)
    state = None           # None | "path" (dotted module path) | "names"
    in_all = 0             # bracket depth inside an `__all__ = [...]`
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        text = tok.string
        # `__all__` holds names as STRINGS, and `import *` reads them from
        # there: leaving them behind breaks the star imports at load time.
        if tok.type == tokenize.NAME and text == "__all__":
            in_all = -1                       # armed, waiting for the bracket
        elif in_all == -1 and tok.type == tokenize.OP and text in "([":
            in_all = 1
        elif in_all > 0 and tok.type == tokenize.OP:
            if text in "([":
                in_all += 1
            elif text in ")]":
                in_all -= 1
        elif in_all == -1 and tok.type in (tokenize.NEWLINE, tokenize.NL):
            in_all = 0

        if tok.type == tokenize.NAME and text == "from" and state is None:
            state = "path"
        elif tok.type == tokenize.NAME and text == "import":
            state = "names" if state == "path" else "path"
        elif tok.type == tokenize.NAME and text == "as" and state is not None:
            state = "names"
        elif tok.type in (tokenize.NEWLINE, tokenize.NL):
            state = None

        if tok.type == tokenize.NAME and text in renames \
                and (state != "path" or text in in_modules):
            text = renames[text]
        elif tok.type == tokenize.STRING and (in_strings or in_all > 0):
            body = tok.string
            for quote in ('"""', "'''", '"', "'"):
                if body.startswith(quote) and body.endswith(quote):
                    inner = body[len(quote):-len(quote)]
                    if inner in renames and (in_all > 0 or inner in in_strings):
                        text = quote + renames[inner] + quote
                    break
        out.append((tok.start, tok.end, text, tok.line))
    # rebuild, preserving everything between tokens verbatim
    pieces, pos = [], (1, 0)
    for start, end, text, _ in out:
        pieces.append(_slice(lines, pos, start))
        pieces.append(text)
        pos = end
    pieces.append(_slice(lines, pos, (len(lines) + 1, 0)))
    return "".join(pieces)


def _slice(lines, start, end):
    (r1, c1), (r2, c2) = start, end
    if r1 > len(lines):
        return ""
    if r1 == r2:
        return lines[r1 - 1][c1:c2]
    out = [lines[r1 - 1][c1:]]
    out += lines[r1:min(r2 - 1, len(lines))]
    if r2 - 1 < len(lines):
        out.append(lines[r2 - 1][:c2])
    return "".join(out)


# -------------------------------------------------------------- symbolic pass
class _Symbolic(ast.NodeTransformer):
    """Applies the map to an AST, so an old file can be compared to a new one."""

    def __init__(self, renames, in_strings, in_modules=frozenset()):
        self.r, self.s, self.m = renames, in_strings, in_modules

    def _path(self, dotted):
        """A dotted module path: only the parts flagged `mod` move."""
        return ".".join(self.r[p] if p in self.m else p
                        for p in dotted.split("."))

    def _n(self, name):
        return self.r.get(name, name)

    def visit_Name(self, node):
        node.id = self._n(node.id)
        return self.generic_visit(node)

    def visit_Attribute(self, node):
        node.attr = self._n(node.attr)
        return self.generic_visit(node)

    def visit_arg(self, node):
        node.arg = self._n(node.arg)
        return self.generic_visit(node)

    def visit_keyword(self, node):
        if node.arg:
            node.arg = self._n(node.arg)
        return self.generic_visit(node)

    def visit_FunctionDef(self, node):
        node.name = self._n(node.name)
        return self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        node.name = self._n(node.name)
        return self.generic_visit(node)

    def visit_Global(self, node):
        node.names = [self._n(n) for n in node.names]
        return node

    visit_Nonlocal = visit_Global

    def visit_alias(self, node):
        # In `from X import y`, `y` is an identifier; in `import X.Y`, a path.
        node.name = self._n(node.name) if "." not in node.name \
            else self._path(node.name)
        if node.asname:
            node.asname = self._n(node.asname)
        return node

    def visit_ImportFrom(self, node):
        if node.module:
            node.module = self._path(node.module)
        for a in node.names:
            a.name = self._n(a.name)
            if a.asname:
                a.asname = self._n(a.asname)
        return node

    def visit_Import(self, node):
        for a in node.names:
            a.name = self._path(a.name)
            if a.asname:
                a.asname = self._n(a.asname)
        return node

    def visit_ExceptHandler(self, node):
        if node.name:
            node.name = self._n(node.name)
        return self.generic_visit(node)

    def visit_Constant(self, node):
        if isinstance(node.value, str) and node.value in self.s:
            node.value = self.r[node.value]
        return node

    def visit_Assign(self, node):
        # `__all__` is the export list `import *` reads: its strings are names.
        if any(isinstance(t, ast.Name) and t.id == "__all__"
               for t in node.targets) \
                and isinstance(node.value, (ast.List, ast.Tuple)):
            for e in node.value.elts:
                if isinstance(e, ast.Constant) and isinstance(e.value, str):
                    e.value = self._n(e.value)
        return self.generic_visit(node)


def dump(src, renames=None, in_strings=None, in_modules=None):
    tree = ast.parse(src)
    if renames:
        tree = _Symbolic(renames, in_strings or set(),
                         in_modules or set()).visit(tree)
        ast.fix_missing_locations(tree)
    return ast.dump(tree)


# -------------------------------------------------------------------- commands
def scopes(tree):
    """(label, line, names) per scope, with the names of the enclosing ones.

    Two names only clash if they can be seen at the same time, and a nested
    function sees its parent's names -- so the parents' are carried down.
    """
    out = []

    NESTED = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)

    def own_names(node):
        """Names bound or used HERE -- a nested def contributes only its name."""
        found = set()
        for child in ast.iter_child_nodes(node):
            if isinstance(child, NESTED):
                found.add(child.name)
                continue
            if isinstance(child, ast.Name):
                found.add(child.id)
            elif isinstance(child, ast.arg):
                found.add(child.arg)
            found |= own_names(child)
        return found

    def walk(node, label, inherited):
        names = inherited | own_names(node)
        out.append((label, getattr(node, "lineno", 0), names))
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef)):
                walk(child, f"{label}.{child.name}", names)

    walk(tree, "<module>", set())
    return out


def cmd_report(renames, in_strings, in_modules, files):
    hits, collisions = {}, {}
    for f in files:
        src = f.read_text(encoding="utf-8")
        names = {t.string for t in tokenize.generate_tokens(
            io.StringIO(src).readline) if t.type == tokenize.NAME}
        for old in renames:
            if old in names:
                hits.setdefault(old, []).append(f.relative_to(ROOT))
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for label, line, seen in scopes(tree):
            for old, new in renames.items():
                if old in seen and new in seen:
                    collisions.setdefault(f"{old} -> {new}", []).append(
                        f"{f.relative_to(ROOT)}:{line} {label}")
    # A parameter is API as soon as somebody calls it by keyword. Renaming it
    # in the file that DEFINES it, while a caller elsewhere still writes
    # `old_name=...`, is a TypeError at runtime that no AST proof can see.
    outside = {}
    scope = set(files)
    params = set()
    for f in files:
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                a = node.args
                params.update(x.arg for x in a.args + a.kwonlyargs + a.posonlyargs)
    # The same trap with a different shape: a class field (a dataclass
    # attribute, a `__slots__` entry, a `self.x`) read from another file. The
    # AST proof cannot see it either -- the reader still says `.old_name`.
    fields = set()
    for f in files:
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for stmt in node.body:
                    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                        fields.add(stmt.target.id)
                    elif isinstance(stmt, ast.Assign):
                        for t in stmt.targets:
                            if isinstance(t, ast.Name):
                                fields.add(t.id)
                            if isinstance(t, ast.Name) and t.id == "__slots__":
                                pass
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                    and node.value.id == "self":
                fields.add(node.attr)
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "__slots__" \
                            and isinstance(node.value, (ast.Tuple, ast.List)):
                        fields.update(e.value for e in node.value.elts
                                      if isinstance(e, ast.Constant)
                                      and isinstance(e.value, str))

    params &= set(renames)
    fields &= set(renames)
    for f in project_files(None):
        if f in scope or not (params or fields):
            continue
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg in params:
                outside.setdefault(node.arg, set()).add(f.relative_to(ROOT))
            elif isinstance(node, ast.Attribute) and node.attr in fields:
                outside.setdefault(node.attr, set()).add(f.relative_to(ROOT))

    # A name written as a STRING: `monkeypatch.setattr(m, "NAME")`, a patch
    # helper, an `__all__` entry in a file this batch does not touch. Renaming
    # the code and leaving the string behind fails only at runtime.
    as_string = {}
    for f in project_files(None):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and node.value in renames and node.value not in in_strings:
                as_string.setdefault(node.value, set()).add(f.relative_to(ROOT))

    missing = [o for o in renames if o not in hits]
    print(f"map: {len(renames)} renames   files scanned: {len(files)}")
    print(f"names found: {len(hits)}   never found: {len(missing)}")
    for name, where in sorted(outside.items()):
        print(f"  KEYWORD ARG  {name}= is passed from {len(where)} file(s) "
              f"outside this batch: {', '.join(str(w) for w in sorted(where)[:3])}")
    for old in missing:
        print(f"  NOT FOUND  {old}")
    for name, where in sorted(as_string.items()):
        seen = ", ".join(str(w) for w in sorted(where)[:3])
        print(f"  NAME AS STRING  {name} appears as a literal in "
              f"{len(where)} file(s): {seen} -- add the `str` flag")
    for pair, where in sorted(collisions.items()):
        print(f"  CLASH  {pair} share a scope in {len(where)} place(s): "
              f"{'; '.join(where[:3])}")
    return 1 if (missing or collisions or outside or as_string) else 0


def cmd_apply(renames, in_strings, in_modules, files):
    touched = 0
    for f in files:
        src = f.read_text(encoding="utf-8")
        new = rewrite(src, renames, in_strings, in_modules)
        if new != src:
            ast.parse(new)  # never leave a file that does not parse
            f.write_text(new, encoding="utf-8")
            touched += 1
    print(f"applied: {touched} file(s) rewritten")
    return 0


def cmd_verify(renames, in_strings, in_modules, files):
    bad = []
    for f in files:
        rel = str(f.relative_to(ROOT))
        old = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=ROOT,
                             capture_output=True, text=True)
        if old.returncode:
            continue  # new file, nothing to compare against
        try:
            if dump(old.stdout, renames, in_strings, in_modules) != dump(
                    f.read_text(encoding="utf-8")):
                bad.append(rel)
        except SyntaxError as e:
            bad.append(f"{rel} (syntax: {e})")
    if bad:
        print("VERIFY FAILED -- more than names changed in:")
        for b in bad:
            print("  ", b)
        return 1
    print(f"verify OK: {len(files)} file(s), only the mapped names changed")
    return 0


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    cmd, map_path, paths = sys.argv[1], sys.argv[2], sys.argv[3:]
    renames, in_strings, in_modules = read_map(map_path)
    files = project_files(paths)
    return {"report": cmd_report, "apply": cmd_apply,
            "verify": cmd_verify}[cmd](renames, in_strings, in_modules, files)


if __name__ == "__main__":
    sys.exit(main())
