"""Which of this project's named rules never fire -- and which are never even asked.

THE BUG THIS EXISTS FOR. `_protect_last_supporter` was gated on `not
state.supporterPlayed`, and Xerosic's Machinations IS a Supporter, so on every
forced discard that card can produce the flag was already True. The rule was not
misfiring: it was UNREACHABLE, and it had been unreachable since it was written.
Reviving it (93a27eb) immediately exposed two further defects that had been
hiding behind it. Nothing in the repository could have pointed at it, and yet
every ingredient was already here: each rule carries a NAME, and every chain
resolves through one choke point in `ptcg/engine/rules.py`. Nobody counted.

WHAT IT COUNTS, per rule, over a workload:

    chain_seen  the rule's chain was resolved (its list was walked)
    evaluated   its `when` was actually called
    fired       its `when` returned True
    decided     it is the one that set the score (chains break at the first
                rule that fires; in ARGMAX chains it means it won the max)

and four bands fall out of those, from most to least suspicious:

    CHAIN NEVER RESOLVED     the whole scorer never ran on this workload
    NEVER EVALUATED          something above it always decides first -- dead by
                             ORDERING
    EVALUATED, NEVER FIRED   its condition never held on a real board -- dead by
                             CONDITION. This is the `_protect_last_supporter`
                             band, and the expensive one
    FIRED, NEVER DECIDED     it fires and is always outranked. Not dead, but not
                             load-bearing either

Adjustments get a fifth: FIRED, NEVER CHANGED THE SCORE -- an adjustment that
always applies and always returns what it was given is a rule nobody applies.

THIS IS A WORKLIST, NOT A VERDICT, and the report says so out loud. A rule with
no fires may simply be RARE: several here are written for one board seen once,
and the honest reading of a zero is "no board in this workload reached it",
which is a statement about the workload as much as about the rule. That is why
every band is printed with the traffic of its chain next to it: a rule that never
fires in a chain resolved 40 000 times is a very different object from one whose
chain ran twice.

HOW IT INSTRUMENTS. Nothing in the tree is modified -- not one line of `ptcg/`,
and no monkeypatch of the engine's semantics. The rule OBJECTS themselves are
found by walking the loaded agent's modules, and their `when`/`value` callables
are wrapped in place. The engine then runs exactly the code it always runs. Only
`_resolve_rules` and `_resolve_max` are rebound, and only to note which lists get
walked -- they still delegate to the originals.

REBINDING IS DONE BY IDENTITY ACROSS EVERY MODULE, never by name in one place:
`from ... import` binds a COPY, so a module that imported `_resolve_max` holds
its own reference and patching `ptcg.engine.rules` alone would miss it. That is
the same trap `gate_the_search_buys.py` documents from the other side.

THE SELF-TEST IS NOT OPTIONAL, and it runs before the real pass (`--self-test`
to run only it). A detector that cannot prove it still works produces the result
that misleads worst: "nothing found" reads exactly like "nothing looked". Both
halves are checked -- a planted dead rule must be reported, and the rules that
demonstrably decided in that same pass must not be.

Usage:
    python utils/rule_census.py --self-test
    python utils/rule_census.py --corpus
    python utils/rule_census.py --corpus --games 200
    python utils/rule_census.py --corpus --games 200 --dump log/censo_reglas.json
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from types import FunctionType, ModuleType

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "utils", _ROOT / "tests"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import selfplay as sp  # noqa: E402

# The decks the workload plays against when none is named. Deliberately a spread
# rather than the hard matchup: a census that only ever sees walls reports every
# rule written for anything else as dead.
DEFAULT_DECKS = (
    "deck/opponents/crustle_kangaskhan.csv",
    "deck/opponents/alakazam.csv",
    "deck/opponents/dragapult.csv",
    "deck/opponents/cynthia_garchomp.csv",
    "deck/opponents/archaludon.csv",
    "deck/opponents/marnie_grimmsnarl.csv",
)

_MAX_WINNER = re.compile(r"^max:(?P<winner>.+?)=")


class Contadores:
    """One per rule object. `cambio` only means anything for adjustments."""

    __slots__ = ("cadena", "evaluada", "disparada", "decidio", "gano", "cambio", "modo")

    def __init__(self):
        self.cadena = 0
        self.evaluada = 0
        self.disparada = 0
        self.decidio = 0     # `value` was called. In a CHAIN that means it set
        self.gano = 0        # the score; in ARGMAX it only means it fired, and
        self.cambio = 0      # `gano` is the one that means it won
        self.modo = "cadena"     # or "max", set when a _resolve_max walks it

    def reset(self):
        self.cadena = self.evaluada = self.disparada = 0
        self.decidio = self.gano = self.cambio = 0

    def mando(self):
        """Did this rule actually decide anything? The answer depends on the mode,
        and conflating the two is what the self-test caught the first time it ran:
        in ARGMAX every rule that fires calls `value`, so `decidio` there is not
        a decision, it is participation."""
        return self.gano if self.modo == "max" else self.decidio

    def as_dict(self):
        return {"cadena": self.cadena, "evaluada": self.evaluada,
                "disparada": self.disparada, "decidio": self.decidio,
                "gano": self.gano, "cambio": self.cambio, "modo": self.modo}


class Registro:
    """Every named rule the agent holds, and where it lives."""

    def __init__(self):
        self.donde = {}        # id(rule) -> (module, varname, index, rule.name, kind)
        self.contadores = {}   # id(rule) -> Contadores
        self.objetos = {}      # id(rule) -> the rule itself (keeps it alive)
        self.desconocidas = 0  # rules walked at runtime that no module names

    def anota(self, rule, modulo, var, indice, kind):
        clave = id(rule)
        if clave in self.donde:
            return False
        self.donde[clave] = (modulo, var, indice, rule.name, kind)
        self.contadores[clave] = Contadores()
        self.objetos[clave] = rule
        return True

    def contador(self, rule):
        return self.contadores.get(id(rule))

    def reset(self):
        for c in self.contadores.values():
            c.reset()
        self.desconocidas = 0

    def etiqueta(self, clave):
        modulo, var, indice, nombre, _ = self.donde[clave]
        corto = modulo.split(".")[-1]
        return f"{corto}.{var}[{indice}] {nombre}"


def espacios_del_agente(agente):
    """Every module namespace reachable from the loaded agent, as (name, dict).

    `sp.load_agent` gives each arm its OWN `ptcg` tree and then restores
    `sys.modules`, so these modules are NOT reachable by name -- only through
    the objects the agent holds.

    AND THEY ARE NOT REACHABLE AS MODULES EITHER. main.py imports with
    `from ptcg... import <name>`, which binds functions, never the module: a
    walk that only followed module objects found precisely nothing, which is how
    the first version of this file reported "no ptcg.engine.rules". So the walk
    follows FUNCTIONS as well, through `__globals__` -- a function's globals IS
    the namespace of the module that defines it. That is the same door
    `gate_the_search_buys.py` uses (`agent.score_option.__globals__['card']`),
    opened generally.

    R4 of the architecture linter (no lazy imports of our own package) is what
    makes the walk complete: everything we own is bound at import time.
    """
    def nuestro(nombre):
        return nombre.split(".")[0] in ("ptcg", "cg")

    # The seed is taken on trust and labelled `main`: `sp.load_agent` names the
    # module after the ARM ("censo", "arm_with"), so a filter that asked for
    # "main" rejected the very namespace it was handed and the walk returned
    # empty.
    vistos, orden, pendientes = set(), [], []
    semilla = vars(agente)
    vistos.add(id(semilla))
    orden.append(("main", semilla))
    pendientes.append(semilla)
    primera = True
    while pendientes:
        esp = pendientes.pop()
        nombre = str(esp.get("__name__", "?"))
        if not primera:
            if id(esp) in vistos:
                continue
            vistos.add(id(esp))
            if not nuestro(nombre):
                continue
            orden.append((nombre, esp))
        primera = False
        for valor in list(esp.values()):
            siguiente = None
            if isinstance(valor, ModuleType):
                siguiente = vars(valor)
            elif isinstance(valor, FunctionType):
                siguiente = valor.__globals__
            if siguiente is not None and id(siguiente) not in vistos:
                pendientes.append(siguiente)
    return orden


def espacio(agente, nombre):
    for nom, esp in espacios_del_agente(agente):
        if nom == nombre:
            return esp
    return None


def construir_registro(agente):
    """Finds the rule objects by their module-level names.

    A rule bound to no name -- built inside a function on every call -- cannot be
    found this way. That is not silent: `desconocidas` counts the ones the
    engine walks at runtime and the registry never saw, and the report prints it.
    """
    registro = Registro()
    reglas_ns = espacio(agente, "ptcg.engine.rules")
    if reglas_ns is None:
        raise SystemExit("no se encontro ptcg.engine.rules en el agente cargado")
    FixedRule, Adjustment = reglas_ns["_FixedRule"], reglas_ns["_Adjustment"]

    def clase_de(objeto):
        if isinstance(objeto, FixedRule):
            return "regla"
        if isinstance(objeto, Adjustment):
            return "ajuste"
        return None

    # `main` is walked LAST. It re-exports most of these lists by name, so
    # scanning it first attributed all 392 rules to "main" and lost the module
    # that actually defines them -- which is half of what makes a dead rule
    # findable.
    espacios = sorted(espacios_del_agente(agente), key=lambda par: par[0] == "main")
    for nombre_mod, esp in espacios:
        for var, valor in sorted(esp.items(), key=lambda kv: kv[0]):
            kind = clase_de(valor)
            if kind:
                registro.anota(valor, nombre_mod, var, 0, kind)
                continue
            if isinstance(valor, (list, tuple)):
                for i, elemento in enumerate(valor):
                    kind = clase_de(elemento)
                    if kind:
                        registro.anota(elemento, nombre_mod, var, i, kind)
    return registro, reglas_ns


def instrumentar(agente, registro, reglas_ns):
    """Wraps the rule objects and the two resolvers. Returns an undo callable."""
    deshacer = []

    def envolver_regla(rule, contador):
        cuando, valor = rule.when, rule.value

        def when(ctx, _c=contador, _f=cuando):
            _c.evaluada += 1
            resultado = _f(ctx)
            if resultado:
                _c.disparada += 1
            return resultado

        def value(ctx, _c=contador, _f=valor):
            _c.decidio += 1
            return _f(ctx)

        rule.when, rule.value = when, value
        deshacer.append(lambda r=rule, w=cuando, v=valor: setattr_pair(r, w, v))

    def envolver_ajuste(adj, contador):
        cuando, aplicar = adj.when, adj.apply

        def when(ctx, score, _c=contador, _f=cuando):
            _c.evaluada += 1
            resultado = _f(ctx, score)
            if resultado:
                _c.disparada += 1
            return resultado

        def apply(ctx, score, _c=contador, _f=aplicar):
            _c.decidio += 1
            nuevo = _f(ctx, score)
            if nuevo != score:
                _c.cambio += 1
            return nuevo

        adj.when, adj.apply = when, apply
        deshacer.append(lambda a=adj, w=cuando, p=aplicar: setattr_apply(a, w, p))

    def setattr_pair(rule, w, v):
        rule.when, rule.value = w, v

    def setattr_apply(adj, w, p):
        adj.when, adj.apply = w, p

    for clave, rule in registro.objetos.items():
        contador = registro.contadores[clave]
        if registro.donde[clave][4] == "ajuste":
            envolver_ajuste(rule, contador)
        else:
            envolver_regla(rule, contador)

    # The two resolvers, rebound only to note which lists get walked. They
    # delegate: the engine's semantics are untouched.
    orig_rules = reglas_ns["_resolve_rules"]
    orig_max = reglas_ns["_resolve_max"]

    def marcar(secuencia, modo):
        for elemento in secuencia:
            contador = registro.contador(elemento)
            if contador is None:
                registro.desconocidas += 1
                continue
            contador.cadena += 1
            contador.modo = modo

    def resolve_rules(rules, adjustments, ctx, default):
        marcar(rules, "cadena")
        marcar(adjustments, "cadena")
        return orig_rules(rules, adjustments, ctx, default)

    def resolve_max(scenarios, ctx):
        marcar(scenarios, "max")
        mejor, traza = orig_max(scenarios, ctx)
        # In ARGMAX mode `value` is called by every rule that fires, so the
        # `decidio` counter above would read "fired". The winner is the one the
        # engine names in its own trace; re-deriving it here beats
        # reimplementing the resolution.
        encontrado = _MAX_WINNER.match(traza or "")
        if encontrado:
            ganador = encontrado.group("winner")
            for elemento in scenarios:
                if elemento.name == ganador:
                    contador = registro.contador(elemento)
                    if contador is not None:
                        contador.gano += 1
                    break
        return mejor, traza

    # BY IDENTITY, ACROSS EVERY MODULE. `from ... import` binds a copy, so the
    # name in `ptcg.engine.rules` is not the one most callers hold.
    reemplazos = {id(orig_rules): resolve_rules, id(orig_max): resolve_max}
    for _, esp in espacios_del_agente(agente):
        for var, valor in list(esp.items()):
            nuevo = reemplazos.get(id(valor))
            if nuevo is not None:
                esp[var] = nuevo
                deshacer.append(lambda n=esp, v=var, o=valor: n.__setitem__(v, o))

    def restaurar():
        for accion in reversed(deshacer):
            accion()

    return restaurar


# --------------------------------------------------------------------------
# workloads


def pasada_corpus(agente):
    import golden_corpus as gc

    records = gc.frozen_records()
    if not records:
        raise SystemExit("no hay corpus congelado en tests/corpus/")
    decisiones = 0
    for _, data in sorted(records.items()):
        decisiones += len(gc.replay_data(agente, data))
    return f"corpus congelado: {decisiones} decisiones en {len(records)} registros"


def pasada_partidas(agente, partidas, mazos):
    from opponent_bot import OpponentBot

    jugadas = 0
    for rel in mazos:
        ruta = _ROOT / rel
        if not ruta.exists():
            continue
        stats = sp.torneo(agente, OpponentBot(), partidas, deck_base=sp.read_deck(ruta))
        jugadas += stats["candidate"] + stats["base"]
    return f"self-play: {jugadas} partidas contra {len(mazos)} mazos"


# --------------------------------------------------------------------------
# the report


def bandas(registro):
    """Sorts every rule into exactly one band. Order is most to least suspicious."""
    salida = defaultdict(list)
    for clave, contador in registro.contadores.items():
        _, _, _, _, kind = registro.donde[clave]
        if contador.cadena == 0:
            banda = "CADENA NUNCA RESUELTA"
        elif contador.evaluada == 0:
            banda = "NUNCA EVALUADA"
        elif contador.disparada == 0:
            banda = "EVALUADA, NUNCA DISPARA"
        elif kind == "ajuste" and contador.cambio == 0:
            banda = "DISPARA, NUNCA CAMBIA EL SCORE"
        elif kind != "ajuste" and contador.modo == "max" and contador.gano == 0:
            banda = "DISPARA, NUNCA GANA"
        elif kind != "ajuste" and contador.modo == "cadena" and contador.decidio == 0:
            banda = "DISPARA, NUNCA DECIDE"
        else:
            continue                      # alive: it decided something
        salida[banda].append(clave)
    return salida


ORDEN_BANDAS = ("CADENA NUNCA RESUELTA", "NUNCA EVALUADA", "EVALUADA, NUNCA DISPARA",
                "DISPARA, NUNCA DECIDE", "DISPARA, NUNCA GANA",
                "DISPARA, NUNCA CAMBIA EL SCORE")


def informe(registro, cargas):
    total = len(registro.contadores)
    vivas = total - sum(len(v) for v in bandas(registro).values())
    print(f"\nCENSO DE REGLAS -- {total} reglas con nombre, {vivas} decidieron algo")
    for carga in cargas:
        print(f"  carga: {carga}")
    if registro.desconocidas:
        print(f"  AVISO: {registro.desconocidas} reglas recorridas que ningun modulo "
              f"nombra (construidas dentro de una funcion): el censo NO las ve")

    # A rule whose `when` runs more often than its chain is walked is being asked
    # somewhere the engine is not resolving -- called by hand from a helper. It
    # is not a defect by itself, but it is a rule with two callers, and this
    # project has already paid for one of those (93a27eb: one discard menu, two
    # horizons).
    sueltas = [(c.evaluada - c.cadena, k) for k, c in registro.contadores.items()
               if c.evaluada > c.cadena]
    if sueltas:
        sueltas.sort(reverse=True)
        print(f"  DOS LLAMANTES: {len(sueltas)} reglas evaluadas mas veces de las que "
              f"su cadena se resolvio (alguien las pregunta a mano):")
        for extra, clave in sueltas[:5]:
            print(f"      +{extra:<6} {registro.etiqueta(clave)}")

    por_banda = bandas(registro)
    for banda in ORDEN_BANDAS:
        claves = por_banda.get(banda) or []
        if not claves:
            continue
        # Ranked by the traffic of the chain they sit in: a rule that never
        # fires in a chain resolved 40 000 times is a very different object from
        # one whose chain ran twice.
        claves.sort(key=lambda k: -registro.contadores[k].cadena)
        print(f"\n{banda}  ({len(claves)})")
        for clave in claves:
            c = registro.contadores[clave]
            print(f"  {registro.etiqueta(clave):<64} cadena={c.cadena:<8} "
                  f"eval={c.evaluada:<8} dispara={c.disparada}")

    print("\nESTO ES UNA LISTA DE TRABAJO, NO UN VEREDICTO. Una regla sin disparos "
          "puede ser simplemente RARA -- varias estan escritas para un tablero visto "
          "una vez -- y un cero dice tanto de la carga como de la regla. Lo que hay "
          "que mirar primero es una regla muerta en una cadena de mucho trafico.")


# --------------------------------------------------------------------------
# the self-test: both halves, before any number is believed


def auto_test(agente, registro, mazos, partidas=6):
    """Plants dead rules and requires them reported; requires live ones not to be.

    The planted rules go into the BUSIEST chain, which is only known after a
    warm-up. `__canario_nunca_dispara__` is safe to leave in front of a live
    chain -- its condition is False, so the engine's behaviour is identical --
    while `__canario_inalcanzable__` needs a blocker above it and DOES change
    what that chain returns. That is why the whole self-test runs as its own
    pass whose counters are then thrown away.
    """
    print("AUTO-TEST (las dos mitades) ...", flush=True)
    registro.reset()
    pasada_partidas(agente, 2, mazos[:1])

    candidatas = [(c.cadena, k) for k, c in registro.contadores.items()
                  if registro.donde[k][4] == "regla" and c.cadena]
    if not candidatas:
        raise SystemExit("AUTO-TEST INVALIDO: ninguna cadena se resolvio en el calentamiento")
    _, clave = max(candidatas)
    modulo, var, _, _, _ = registro.donde[clave]
    esp = espacio(agente, modulo) or {}
    anfitriona = esp.get(var)
    if not isinstance(anfitriona, list):
        raise SystemExit(f"AUTO-TEST INVALIDO: {modulo}.{var} no es una lista mutable; "
                         "no se puede plantar el canario sin tocar el arbol")

    FixedRule = espacio(agente, "ptcg.engine.rules")["_FixedRule"]

    muerto = FixedRule("__canario_nunca_dispara__", lambda c: False, lambda c: 0)
    bloqueo = FixedRule("__canario_bloqueo__", lambda c: True, lambda c: 0)
    tapado = FixedRule("__canario_inalcanzable__", lambda c: True, lambda c: 0)
    for canario in (muerto, bloqueo, tapado):
        registro.anota(canario, modulo, var, -1, "regla")

    original = list(anfitriona)
    restaurar = instrumentar_solo(registro, (muerto, bloqueo, tapado))
    anfitriona[:] = [muerto, bloqueo, tapado] + original
    registro.reset()
    try:
        pasada_partidas(agente, partidas, mazos[:1])
    finally:
        anfitriona[:] = original
        restaurar()

    por_banda = bandas(registro)
    en_banda = {registro.donde[k][3]: banda
                for banda, claves in por_banda.items() for k in claves}
    fallos = []

    # Half one -- SENSITIVITY: both planted corpses must be named, in the right
    # band. A detector that misses a rule it was handed misses the real ones.
    if en_banda.get("__canario_nunca_dispara__") != "EVALUADA, NUNCA DISPARA":
        fallos.append("el canario que nunca dispara no se reporto en su banda "
                      f"(salio como {en_banda.get('__canario_nunca_dispara__')!r})")
    if en_banda.get("__canario_inalcanzable__") != "NUNCA EVALUADA":
        fallos.append("el canario inalcanzable no se reporto en su banda "
                      f"(salio como {en_banda.get('__canario_inalcanzable__')!r})")

    # Half two -- SPECIFICITY: the blocker decided every single resolution of
    # that chain, so if it appears in any band the bands are noise.
    if "__canario_bloqueo__" in en_banda:
        fallos.append("el canario VIVO (decidio en cada resolucion) fue reportado "
                      f"como muerto en {en_banda['__canario_bloqueo__']!r}")
    # `mando()` and not `decidio`: the first run of this self-test failed here,
    # and it was right to. `_ESC_NS_RECUPERACION.energia_teal_dance` sits in an
    # ARGMAX chain where every rule that fires calls `value`, so `decidio` read
    # as "decided" for a rule that competes and always loses -- a rule the bands
    # correctly called dead.
    decidieron = [k for k, c in registro.contadores.items()
                  if c.mando() and registro.donde[k][4] == "regla"]
    delatadas = [registro.etiqueta(k) for k in decidieron
                 if any(k in claves for claves in por_banda.values())]
    if delatadas:
        fallos.append(f"{len(delatadas)} reglas que DECIDIERON salieron en una banda "
                      f"de muertas: {delatadas[:3]}")

    for clave in [k for k, v in registro.donde.items() if v[2] == -1]:
        registro.donde.pop(clave, None)
        registro.contadores.pop(clave, None)
        registro.objetos.pop(clave, None)
    registro.reset()

    if fallos:
        for f in fallos:
            print(f"  AUTO-TEST FALLA: {f}")
        return False
    print("  AUTO-TEST OK: reporta las plantadas y calla con las vivas\n", flush=True)
    return True


def instrumentar_solo(registro, reglas):
    """Wraps a handful of rules added after the main instrumentation pass."""
    deshacer = []
    for rule in reglas:
        contador = registro.contador(rule)
        cuando, valor = rule.when, rule.value

        def when(ctx, _c=contador, _f=cuando):
            _c.evaluada += 1
            resultado = _f(ctx)
            if resultado:
                _c.disparada += 1
            return resultado

        def value(ctx, _c=contador, _f=valor):
            _c.decidio += 1
            return _f(ctx)

        rule.when, rule.value = when, value
        deshacer.append(lambda r=rule, w=cuando, v=valor: (setattr(r, "when", w),
                                                           setattr(r, "value", v)))

    def restaurar():
        for accion in deshacer:
            accion()

    return restaurar


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", action="store_true",
                    help="replay the frozen corpus (deterministic, 3 580 decisions)")
    ap.add_argument("--games", type=int, default=0,
                    help="self-play games per opponent deck")
    ap.add_argument("--opponent", default=None,
                    help="csv of an opponent deck; repeatable via commas")
    ap.add_argument("--dump", default=None, help="write the raw counters as json")
    ap.add_argument("--self-test", action="store_true",
                    help="run only the two halves and report whether they hold")
    ap.add_argument("--no-self-test", action="store_true",
                    help="skip the self-test (the numbers are then unvalidated)")
    args = ap.parse_args(argv)

    mazos = (args.opponent.split(",") if args.opponent else list(DEFAULT_DECKS))
    agente = sp.load_agent(_ROOT / "main.py", "censo")
    registro, reglas_ns = construir_registro(agente)
    print(f"registro: {len(registro.contadores)} reglas con nombre en "
          f"{len({v[0] for v in registro.donde.values()})} modulos", flush=True)
    restaurar = instrumentar(agente, registro, reglas_ns)

    try:
        valido = True
        if not args.no_self_test:
            valido = auto_test(agente, registro, mazos)
            if args.self_test:
                return 0 if valido else 1
        if not valido:
            print("\nAUTO-TEST FALLIDO: el censo queda INVALIDO y no se imprime. "
                  "Un numero de un detector que no puede probar que funciona no es "
                  "un hallazgo mas pequeno, es ninguno.")
            return 1

        cargas = []
        if args.corpus:
            cargas.append(pasada_corpus(agente))
        if args.games:
            cargas.append(pasada_partidas(agente, args.games, mazos))
        if not cargas:
            raise SystemExit("nada que medir: usa --corpus y/o --games N")

        informe(registro, cargas)
        if args.dump:
            destino = Path(args.dump)
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(json.dumps(
                {registro.etiqueta(k): c.as_dict()
                 for k, c in registro.contadores.items()}, indent=2))
            print(f"\ncontadores crudos -> {destino}")
    finally:
        restaurar()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
