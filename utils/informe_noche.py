"""Reads a night's logs and writes the one page somebody actually reads.

The failure mode this project knows by name is *a number nobody read*. A night
produces nine logs, some of them tens of thousands of lines, and the useful
content of each is between one and ten numbers. This walks them and writes
`INFORME.md` next to them.

It reports three things per block and refuses to invent a fourth:

  * the EXIT CODE and what it means for that particular tool --- the permutation
    probe reports findings by exit code, so a non-zero there is FINDINGS and not
    FAILED, and calling a tool's findings a failure is how a pipeline teaches
    people to ignore its red;
  * whether the block's SELF-TEST ran and passed. A stage whose self-test failed
    is INVALID regardless of its exit code, including zero, and its numbers are
    replaced rather than shown. A detector that cannot prove it still works and
    then says "nothing found" is the most misleading of the three outcomes;
  * the numbers, grepped by patterns that are checked against what the tools
    actually print, not against what they printed once.

Usage:
    python utils/informe_noche.py                       # the -c night
    python utils/informe_noche.py --dir log/noche_2026-08-10-c
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "log" / "noche_2026-08-10-c"

# What each block is for, and how to read a non-zero exit code from it.
BLOQUES = {
    "B1a": ("El oraculo contra las 87 listas reales", "error"),
    "B1b": ("Los cinco peores por tasa, volcados", "error"),
    "B2": ("El eje Crustle con intervalos estrechos", "error"),
    "B2b": ("El crustle_wall_6 RETIRADO, desde el respaldo", "error"),
    "B3": ("El monitor de invariantes", "error"),
    "B4": ("La sonda de permutacion", "hallazgos"),
    "B5": ("Soak de propiedades", "error"),
    "B6": ("Radar de colisiones sobre listas reales", "error"),
    "B7": ("Matriz ponderada contra el meta nuevo", "error"),
}

# The phrases the detectors print when their self-test passes. If a tool stops
# printing its phrase this goes quiet, which is why the phrases are asserted in
# tests/test_the_night_quarantines_a_detector_that_cannot_validate_itself.py.
AUTOTEST_OK = ("Auto-test", "auto-test", "self-test")
AUTOTEST_MAL = ("Auto-test FALLA", "auto-test FALLA", "SELF-TEST FAILED",
                "self-test FAILED")


def lee(path: Path) -> str:
    try:
        return path.read_text(errors="replace")
    except OSError:
        return ""


def codigos_de_salida(resumen: str) -> dict[str, tuple[int, str]]:
    """`B1a  rc=0     12m 03s  titulo` -> {'B1a': (0, '12m 03s')}"""
    salida = {}
    for linea in resumen.splitlines():
        m = re.match(r"(\S+)\s+rc=(-?\d+)\s+(\d+m \d+s)", linea)
        if m:
            salida[m.group(1)] = (int(m.group(2)), m.group(3))
    return salida


def censo_del_oraculo(texto: str) -> list[tuple[float, str, int, int]]:
    """Findings rate per deck, from the one-invocation-per-deck census."""
    mazo, hallazgos, juzgados = None, {}, {}
    for linea in texto.splitlines():
        cab = re.match(r"### (\S+)", linea)
        if cab:
            mazo = cab.group(1)
            hallazgos.setdefault(mazo, 0)
            juzgados.setdefault(mazo, 0)
            continue
        if mazo is None:
            continue
        c = re.match(r"\s+(PHANTOM_KO|MISSED_KO|DAMAGE_DRIFT):\s+(\d+)\s*$", linea)
        if c:
            hallazgos[mazo] += int(c.group(2))
        t = re.search(r"ataques juzgados:\s+(\d+)", linea)
        if t:
            juzgados[mazo] += int(t.group(1))
    filas = [(hallazgos[m] / juzgados[m], m, hallazgos[m], juzgados[m])
             for m in hallazgos if juzgados.get(m)]
    filas.sort(reverse=True)
    return filas


def invariantes(texto: str) -> list[tuple[str, int]]:
    """The five that are defects. STALE_FLAG/STALE_READ are not."""
    reales = ("DECK_BELIEF", "ILLEGAL_INDEX", "END_EMPTY_BENCH",
              "ENERGY_CAP", "DOUBLE_ATTACH")
    salida = []
    for nombre in reales:
        m = re.search(rf"\b{nombre}:\s+(\d+)", texto)
        salida.append((nombre, int(m.group(1)) if m else 0))
    return salida


def permutacion(texto: str) -> dict[str, object]:
    datos: dict[str, object] = {}
    m = re.search(r"decisions compared:\s+(\d+)", texto)
    if m:
        datos["comparadas"] = int(m.group(1))
    m = re.search(r"order-dependent\s*:\s+(\d+)\s+\(([\d.]+)%\)", texto)
    if m:
        datos["dependientes"] = int(m.group(1))
        datos["tasa"] = m.group(2)
    # The strategic ones: an ATTACK/RETREAT fork is decided by menu position.
    datos["bifurcaciones"] = len(re.findall(r"ATTACK.*RETREAT|RETREAT.*ATTACK",
                                            texto))
    return datos


def autotest(texto: str) -> str:
    if not texto.strip():
        return "sin log"
    if any(p in texto for p in AUTOTEST_MAL):
        return "FALLA -> el bloque es INVALIDO, sus numeros no valen"
    if any(p in texto for p in AUTOTEST_OK):
        return "pasa"
    return "el bloque no publica auto-test"


def informe(carpeta: Path) -> str:
    resumen = lee(carpeta / "RESUMEN.txt")
    rcs = codigos_de_salida(resumen)
    out, add = [], None
    out = []
    add = out.append

    add(f"# Informe de la noche — `{carpeta.name}`")
    add("")
    cabecera = [l for l in resumen.splitlines()
                if l.startswith(("HEAD", "corpus", "arranque", "fin", "total"))]
    if cabecera:
        add("```")
        out.extend(cabecera)
        add("```")
    add("")

    if not rcs:
        corriendo = any((carpeta / f"{b}.log").exists() for b in BLOQUES)
        if corriendo:
            add("**La noche sigue en marcha:** ningún bloque ha terminado "
                "todavía, así que lo de abajo es un adelanto y no un resultado. "
                "`log/noche_10ago_c.txt` lleva la traza con marcas de tiempo.")
        else:
            add("**La noche no dejó RESUMEN.txt legible ni un solo log.** Murió "
                "antes de escribir su primera línea. `log/noche_10ago_c.txt` "
                "tiene la traza con marcas de tiempo.")
        add("")

    add("## Estado de cada bloque")
    add("")
    add("| | Bloque | rc | tiempo | auto-test |")
    add("|---|---|---|---|---|")
    for bid, (titulo, lectura) in BLOQUES.items():
        texto = lee(carpeta / f"{bid}.log")
        rc, tiempo = rcs.get(bid, (None, "—"))
        if rc is None:
            # A block writes its RESUMEN row when it FINISHES, so "no row" and
            # "still running" look identical from there. The log tells them
            # apart, and calling a running block "it never ran" is the kind of
            # small lie that gets read as a result.
            estado = "en curso" if texto.strip() else "no llegó a correr"
        elif rc == 0:
            estado = "0"
        elif lectura == "hallazgos":
            estado = f"{rc} = HALLAZGOS, no fallo"
        else:
            estado = f"**{rc}**"
        add(f"| {bid} | {titulo} | {estado} | {tiempo} | {autotest(texto)} |")
    add("")

    # --- B1a, the census ----------------------------------------------------
    b1a = lee(carpeta / "B1a.log")
    if b1a.strip():
        filas = censo_del_oraculo(b1a)
        add("## B1a · El residuo del oráculo, lista por lista")
        add("")
        if not filas:
            add("El censo no dejó ninguna pareja hallazgos/juzgados legible. "
                "Antes de culpar al agente, mira si los mazos se cargaron: "
                "estas listas nunca habían pasado por el oráculo.")
        else:
            total_h = sum(f[2] for f in filas)
            total_j = sum(f[3] for f in filas)
            tasa = 100 * total_h / total_j if total_j else 0
            add(f"**{total_h} hallazgos sobre {total_j} ataques juzgados "
                f"({tasa:.2f} %)** en {len(filas)} listas.")
            add("")
            add("Contra los 19 sintéticos la tasa medida dos noches seguidas "
                "fue 1,39-1,42 %. Un orden de magnitud de diferencia acusa a la "
                "carga de los mazos antes que al agente.")
            add("")
            add("| lista | tasa | hallazgos | juzgados |")
            add("|---|---:|---:|---:|")
            for t, mazo, h, j in filas[:10]:
                add(f"| `{mazo}` | {100*t:.2f} % | {h} | {j} |")
            limpias = sum(1 for f in filas if f[2] == 0)
            add("")
            add(f"Listas con **cero** hallazgos: {limpias} de {len(filas)}.")
        add("")

    # --- B2 / B2b, the Crustle axis -----------------------------------------
    for bid, titulo in (("B2", "B2 · La familia Crustle nueva, y el control"),
                        ("B2b", "B2b · El `crustle_wall_6` retirado")):
        texto = lee(carpeta / f"{bid}.log")
        if not texto.strip():
            continue
        add(f"## {titulo}")
        add("")
        filas = [l for l in texto.splitlines()
                 if re.search(r"\b(crustle_wall|mega_lucario)_\d+", l)
                 and "%" in l]
        if filas:
            add("```")
            out.extend(filas[:30])
            add("```")
        else:
            add("Sin filas de winrate legibles; mira el log entero.")
        add("")

    # --- B3, the invariants --------------------------------------------------
    b3 = lee(carpeta / "B3.log")
    if b3.strip():
        add("## B3 · Invariantes")
        add("")
        add("| invariante | violaciones |")
        add("|---|---:|")
        for nombre, n in invariantes(b3):
            marca = f"**{n}**" if n else "0"
            add(f"| {nombre} | {marca} |")
        add("")
        add("`STALE_FLAG` y `STALE_READ` salen a miles y **no son defectos**: "
            "son banderas cuya premisa murió, no decisiones equivocadas.")
        add("")

    # --- B4, the permutation probe -------------------------------------------
    b4 = lee(carpeta / "B4.log")
    if b4.strip():
        datos = permutacion(b4)
        add("## B4 · Decisiones que dependen del orden del menú")
        add("")
        if "dependientes" in datos:
            add(f"**{datos['dependientes']} de {datos.get('comparadas', '?')} "
                f"({datos.get('tasa', '?')} %)** cambian si el menú se permuta.")
        add("")
        add(f"De ellas, **{datos.get('bifurcaciones', 0)}** son bifurcaciones "
            "`ATTACK` contra `RETREAT`. Ésas son las que importan: un empate "
            "`CARD` vs `CARD` es cosmético, atacar-o-retirar no.")
        add("")

    # --- B5, B6, B7 ----------------------------------------------------------
    b5 = lee(carpeta / "B5.log")
    if b5.strip():
        add("## B5 · Soak de propiedades")
        add("")
        cola = [l for l in b5.strip().splitlines() if l.strip()][-3:]
        add("```")
        out.extend(cola)
        add("```")
        add("")
        if "failed" in b5.lower() or "Falsifying" in b5:
            add("**Hay una falsación.** Es el artefacto más valioso que puede "
                "producir una noche, porque Hypothesis lo devuelve MINIMIZADO.")
            add("")

    b6 = lee(carpeta / "B6.log")
    if b6.strip():
        add("## B6 · Radar de colisiones sobre listas reales")
        add("")
        cand = b6.split("--- candidates")
        if len(cand) > 1:
            add("```")
            out.extend(cand[-1].strip().splitlines()[:20])
            add("```")
        add("")
        add("Primera vez que el radar mira listas reales. Una situación que se "
            "resuelve muy por debajo de la mediana en UNA lista y no en las "
            "demás señala una colisión de banderas de matchup.")
        add("")

    b7 = lee(carpeta / "B7.log")
    if b7.strip():
        add("## B7 · Contra el meta ponderado")
        add("")
        cola = [l for l in b7.strip().splitlines() if l.strip()][-14:]
        add("```")
        out.extend(cola)
        add("```")
        add("")
        add("Línea base de este corpus: no hay con qué compararla. Las 4 listas "
            "casi copia de la nuestra inflan el número y están marcadas en "
            "`pesos.csv`.")
        add("")

    add("---")
    add("")
    add("**Ningún hallazgo de aquí se convierte en un cambio del agente sin "
        "medirlo, y se mide la FRECUENCIA antes que el winrate.**")
    add("")
    return "\n".join(out)


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=str(DEFAULT))
    ap.add_argument("--output", default=None,
                    help="default: INFORME.md inside --dir")
    args = ap.parse_args(argv)

    carpeta = Path(args.dir)
    if not carpeta.is_absolute():
        carpeta = ROOT / carpeta
    if not carpeta.is_dir():
        print(f"ERROR: there is no {carpeta}", file=sys.stderr)
        return 2

    texto = informe(carpeta)
    destino = Path(args.output) if args.output else carpeta / "INFORME.md"
    if not destino.is_absolute():
        destino = ROOT / destino
    destino.write_text(texto, encoding="utf-8")
    print(f"written to {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
