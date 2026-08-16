"""Self-play gate for the two switches of "el asiento del frente vs Alakazam",
with its own control.

    THE_PIVOT_NEEDS_A_CORPSE_THEY_CAN_TAKE     el retiro: ¿hay cadaver que cobrar?
    THE_PIVOT_PROMOTES_THE_BODY_IT_PAYS_FOR    el asiento: ¿lo cumple quien se sienta?

LEE PRIMERO EL CENSO -- `utils/census_the_pivot_promotes_the_body_it_pays_for.py`.
La frase entera toca **7 decisiones de 2 416** en 32 partidas contra la línea de
Alakazam (1 de ellas la segunda mitad) y **0 de 3 940** fuera del matchup. A esa
exposición un winrate **no puede resolver nada**: este gate es una COMPROBACIÓN
DE DAÑO, no la evidencia. La evidencia son el censo, los dos corpus (local 0
flips, congelado 1 revisado) y los once tests con sus controles sobre tres
tableros reales.

Lo que este gate puede decir, y es lo único que se le pide: que la regla no
rompa nada. Una fila candidata claramente NEGATIVA y fuera del suelo de ruido es
un hallazgo; una fila dentro del suelo no dice que la regla funcione, dice que
no hace daño.

`--control` es lo que pone ese suelo por escrito: juega las banderas contra SÍ
MISMAS, así que su delta es el ruido a la misma N y cualquier fila candidata más
pequeña que esa fila es ruido
([[el-suelo-de-ruido-del-grupo-de-control-ya-es-cero]]).

EL RIVAL POR DEFECTO ES UNA LISTA DE ALAKAZAM, y no `deck.csv`, porque fuera de
ese matchup las dos banderas están estructuralmente calladas (viven dentro de
`op_is_alakazam_deck`): medir contra otra cosa es gastar mil partidas para leer
un cero que ya sabemos. Contra otra lista se usa para lo contrario -- comprobar
que ese cero es cero de verdad.

`--only` mide UNA de las dos. Son una sola frase pero no un solo mecanismo: la
primera decide si el asiento se vende y la segunda a quién, y un gate que sólo
sabe decir "la frase" no puede decir cuál de las dos mitades movió una fila.

LOS BRAZOS SON EL MISMO ÁRBOL CON LAS BANDERAS REBOTADAS, que es la única forma
de que la regla sea la única diferencia entre ellos: los dos son `main.py` tal
como está, cargado dos veces por `selfplay.load_agent` para que cada uno tenga
su propio paquete `ptcg` (un árbol compartido mide exactamente cero -- ver
`load_agent_from_git`).

NO ESCRIBE EN EL ÁRBOL. Sólo lee `main.py` y rebota atributos sobre los módulos
que carga en memoria, así que puede correr mientras se trabaja en el
repositorio.

Uso:
    python utils/gate_the_front_seat_vs_alakazam.py --games 1000
    python utils/gate_the_front_seat_vs_alakazam.py --games 1000 --control
    python utils/gate_the_front_seat_vs_alakazam.py --games 1000 \
        --only THE_PIVOT_PROMOTES_THE_BODY_IT_PAYS_FOR
    python utils/gate_the_front_seat_vs_alakazam.py --games 1000 \
        --opponent deck/real_opponents/archaludon_1.csv     # la mitad de la fuga
"""

import argparse
import math
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT), str(_ROOT / "utils")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import selfplay as sp  # noqa: E402

FLAGS = (
    "THE_PIVOT_NEEDS_A_CORPSE_THEY_CAN_TAKE",
    "THE_PIVOT_PROMOTES_THE_BODY_IT_PAYS_FOR",
)

# La lista contra la que la frase puede hablar. Cualquiera de las once
# `alakazam_*.csv` sirve; la 1 es la de más peso en el meta cosechado.
DEFAULT_OPPONENT = "deck/real_opponents/alakazam_1.csv"


def arm(name, value, only=None):
    """`main.py` con las banderas bajo medición atadas a `value`.

    `only` estrecha la medición a una sola bandera; la otra se queda como viene
    en el fichero, así que el brazo sigue diferenciándose de su baseline en
    exactamente una frase.
    """
    mod = sp.load_agent(_ROOT / "main.py", name)
    for flag in (FLAGS if only is None else (only,)):
        setattr(mod, flag, value)
    return mod


def provenance(candidate, base, control, only=None):
    """Se niega a medir dos brazos que en secreto son el mismo agente.

    El modo de fallo que esto existe para impedir es el que ya costó una noche
    entera: dos brazos que comparten árbol, o una bandera que el fichero trae en
    False y nadie encendió, dan un delta de cero que se lee como "la regla es
    neutra" cuando lo que pasa es que no se midió nada.
    """
    flags = FLAGS if only is None else (only,)
    if candidate is base:
        raise SystemExit("los dos brazos son el MISMO agente: la medida seria cero")
    for flag in flags:
        if getattr(base, flag):
            raise SystemExit(
                f"el brazo baseline NO esta neutralizado en {flag}: nada que medir")
        if bool(getattr(candidate, flag)) is bool(control):
            raise SystemExit(
                f"el brazo candidato no esta como dice estar en {flag} "
                f"(control={bool(control)}, lectura={getattr(candidate, flag)})")
    print(f"procedencia OK (candidato "
          f"{'NEUTRALIZADO: control' if control else 'con la lectura'}, "
          f"baseline sin ella; flags={', '.join(flags)})\n", flush=True)


def wilson_delta(w1, n1, w2, n2):
    """Test z de dos proporciones. ASUME Bernoulli independientes, que el bot no
    honra -- la p que imprime se lee como una cota optimista."""
    if not n1 or not n2:
        return 0.0, 0.0, 1.0
    p1, p2 = w1 / n1, w2 / n2
    p = (w1 + w2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2)) or 1e-9
    z = (p1 - p2) / se
    return p1 - p2, z, 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--games", type=int, default=1000)
    ap.add_argument("--progress", type=int, default=500)
    ap.add_argument("--opponent", default=DEFAULT_OPPONENT,
                    help=f"lista rival (por defecto {DEFAULT_OPPONENT}; "
                         f"'deck.csv' para el espejo)")
    ap.add_argument("--only", choices=FLAGS, default=None,
                    help="medir UNA de las dos en vez de la frase")
    ap.add_argument("--control", action="store_true",
                    help="brazo candidato NEUTRALIZADO: mide el suelo de ruido")
    args = ap.parse_args(argv)

    # LOS TRES BRAZOS SE CARGAN ANTES DE JUGAR NADA, y no uno de ellos a mitad
    # de la corrida. `main.py` se lee del DISCO: si alguien lo edita mientras el
    # gate corre -- otra sesión de trabajo, un editor guardando -- un brazo
    # cargado tarde es OTRO agente que el que ya se midió, y la fila sale de
    # comparar dos árboles distintos sin que nada lo diga. La ventana no
    # desaparece (sigue existiendo entre estas tres líneas) pero pasa de durar
    # toda la medición a durar lo que tardan tres imports.
    candidate = arm("arm_candidate", not args.control, args.only)
    base = arm("arm_base", False, args.only)
    baseline = arm("arm_control", False, args.only)
    provenance(candidate, base, args.control, args.only)

    # EL ASIENTO DE ENFRENTE ES EL MISMO AGENTE CON LA OTRA LISTA, y los dos
    # brazos juegan LAS MISMAS SEMILLAS. Emparejados así el motor reparte las
    # mismas partidas a los dos, la fila de control sale exactamente en cero y
    # cualquier fila candidata que no lo sea es la regla y nada más.
    their = (None if args.opponent in (None, "deck.csv")
             else sp.read_deck(_ROOT / args.opponent))
    seeds = list(range(1, args.games + 1))
    n = args.games

    def run(mod, label):
        stats = sp.torneo(mod, base, n, progress=args.progress or None,
                          deck_base=their, seeds=seeds)
        wins = stats["candidate"]
        print(f"  {label:10s} {wins:5d}/{n} = {100 * wins / n:6.2f}%", flush=True)
        return wins

    with_rule = run(candidate, "candidato")
    without = run(baseline, "baseline")
    delta, z, p = wilson_delta(with_rule, n, without, n)
    print(f"\n{'CONTROL' if args.control else 'CANDIDATO'} "
          f"({args.only or 'las dos'}, {args.opponent or 'deck.csv'}, n={n}): "
          f"delta {100 * delta:+.2f} pp   z {z:+.2f}   p {p:.3f}")
    print("Recuerda la exposicion: 7 decisiones de 2 416. Una fila dentro del "
          "suelo de --control dice 'no hace daño', no 'funciona'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
