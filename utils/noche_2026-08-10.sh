#!/usr/bin/env bash
#
# The second run of the night of 9-10 August 2026.
#
# The first `nightly.py --full` finished at 15:52 with every gate green and
# three open questions it could not answer with the sample it had. This script
# is those three questions and nothing else. It is NOT "the same, but bigger":
# every block asks something the full run raised and left open.
#
#   B1  the residue against the 98 REAL decks (it has only ever been measured
#       against the 19 synthetic ones), then a deep dump of the five worst
#   B2  the Crustle axis with tight intervals, and a control family
#   B3  the monitor at ten times the sample, with every violation dumped
#   B4  the 1 698 order-dependent decisions, dumped so they can be triaged
#   B5  the property soak at ten times the budget
#   B6  the collision radar, the tool built for exactly the question B2 asks
#
# Everything it writes lives under log/noche_2026-08-10/ and nothing outside it
# is touched: the working tree is as clean at the end as at the start.
#
# No block can stop the night. A block that fails leaves its log and the next
# one starts, because a run that aborts halfway attributes its own damage to
# the wrong stage.
#
# Usage:
#   bash utils/noche_2026-08-10.sh
#   PY=.venv/bin/python bash utils/noche_2026-08-10.sh    # another interpreter
#   SOLO=B2,B3 bash utils/noche_2026-08-10.sh             # relaunch some blocks

set -u

cd "$(dirname "$0")/.." || exit 1
ROOT="$PWD"
OUT="$ROOT/log/noche_2026-08-10"
PY="${PY:-python}"
SOLO="${SOLO:-}"

mkdir -p "$OUT"

# Sample sizes, in one place so a shorter night is one edit and not a rewrite.
CENSO_GAMES="${CENSO_GAMES:-300}"     # B1a, per real deck
PROFUNDO_GAMES="${PROFUNDO_GAMES:-1000}"  # B1b, per deck among the five worst
MATRIZ_GAMES="${MATRIZ_GAMES:-1000}"  # B2, per matchup
MONITOR_GAMES="${MONITOR_GAMES:-20000}"
PERM_GAMES="${PERM_GAMES:-2000}"
EJEMPLOS="${EJEMPLOS:-200000}"        # B5, hypothesis examples
RADAR_GAMES="${RADAR_GAMES:-400}"     # B6, per synthetic deck

marca() { printf '%s  %s\n' "$(date '+%H:%M:%S')" "$*"; }

quiere() {   # honours SOLO=B2,B3; with SOLO unset, everything runs
    [ -z "$SOLO" ] && return 0
    case ",$SOLO," in *",$1,"*) return 0;; *) return 1;; esac
}

bloque() {   # bloque <id> <title> -- <command...>
    local id="$1" titulo="$2"; shift 3
    quiere "$id" || { marca "[$id] saltado (SOLO=$SOLO)"; return 0; }
    local fichero="$OUT/${id}.log"
    marca "[$id] $titulo — empieza"
    local t0=$SECONDS
    "$@" > "$fichero" 2>&1
    local rc=$? dt=$((SECONDS - t0))
    marca "[$id] termina rc=$rc en $((dt/60))m $((dt%60))s -> log/noche_2026-08-10/${id}.log"
    printf '%-4s rc=%-3s %4dm %02ds  %s\n' "$id" "$rc" "$((dt/60))" "$((dt%60))" "$titulo" \
        >> "$OUT/RESUMEN.txt"
}

# --- B1a: the oracle over every real deck -----------------------------------
# One invocation per deck so each one runs its own self-test: a census whose
# detector cannot prove it still works is the one result worth nothing.
censo_oraculo() {
    local f nombre
    for f in "$ROOT"/deck/real_opponents/*.csv; do
        nombre="$(basename "$f" .csv)"
        [ "$nombre" = "pesos" ] && continue
        echo "### $nombre"
        "$PY" utils/differential_oracle.py --games "$CENSO_GAMES" --opponent "$f" 2>&1
        echo
    done
}

# --- B1b: the five worst by RATE, dumped as fixtures ------------------------
# By rate and not by absolute count: a deck that judges twice as many attacks
# reports twice as many findings at the same defect level.
peores_del_censo() {
    "$PY" - "$OUT/B1a.log" <<'PY'
import re, sys, pathlib
texto = pathlib.Path(sys.argv[1]).read_text(errors="replace")
mazo, hallazgos, juzgados = None, {}, {}
for linea in texto.splitlines():
    encabezado = re.match(r"### (\S+)", linea)
    if encabezado:
        mazo = encabezado.group(1)
        hallazgos.setdefault(mazo, 0)
        juzgados.setdefault(mazo, 0)
        continue
    if mazo is None:
        continue
    conteo = re.match(r"\s+(PHANTOM_KO|MISSED_KO|DAMAGE_DRIFT):\s+(\d+)\s*$", linea)
    if conteo:
        hallazgos[mazo] += int(conteo.group(2))
    total = re.search(r"ataques juzgados:\s+(\d+)", linea)
    if total:
        juzgados[mazo] += int(total.group(1))
tasas = [(hallazgos[m] / juzgados[m], m) for m in hallazgos if juzgados.get(m)]
for _, mazo in sorted(tasas, reverse=True)[:5]:
    print(mazo)
PY
}

profundo_oraculo() {
    local nombre
    if [ ! -s "$OUT/B1a.log" ]; then
        echo "sin censo (B1a) del que sacar los peores: nada que profundizar"
        return 0
    fi
    peores_del_censo | while read -r nombre; do
        [ -z "$nombre" ] && continue
        echo "### $nombre  ($PROFUNDO_GAMES partidas, con volcado)"
        "$PY" utils/differential_oracle.py \
            --games "$PROFUNDO_GAMES" \
            --opponent "$ROOT/deck/real_opponents/${nombre}.csv" \
            --dump "$OUT/violaciones_oraculo/$nombre" 2>&1
        echo
    done
}

# --- B2: the Crustle axis, and a control family -----------------------------
# mega_lucario is the next worst family (87.0 % against crustle_wall's 76.6 %):
# without it, a tighter Crustle number cannot be told from a tighter everything.
eje_crustle() {
    local lista
    lista="$(ls "$ROOT"/deck/real_opponents/crustle_wall_*.csv \
                 "$ROOT"/deck/real_opponents/mega_lucario_*.csv 2>/dev/null \
             | xargs -n1 basename | sed 's/\.csv$//' | paste -sd, -)"
    echo "decks: $lista"
    "$PY" utils/matchup_matrix.py --games "$MATRIZ_GAMES" --only "$lista"
}

# ----------------------------------------------------------------------------

: > "$OUT/RESUMEN.txt"
marca "arranca la noche, salida en log/noche_2026-08-10/"
marca "HEAD $(git rev-parse --short HEAD), arbol $(git status --porcelain | wc -l | tr -d ' ') ficheros sucios"
INICIO=$SECONDS

bloque B1a "El oraculo contra los 98 mazos REALES" -- censo_oraculo
bloque B1b "Los cinco peores del censo, con volcado" -- profundo_oraculo
bloque B2  "El eje Crustle con intervalos estrechos" -- eje_crustle
bloque B3  "El monitor a $MONITOR_GAMES partidas, con volcado" -- \
    "$PY" utils/invariant_monitor.py --games "$MONITOR_GAMES" \
        --dump "$OUT/violaciones_monitor" --progress 2000
bloque B4  "La sonda de permutacion, volcada para triaje" -- \
    "$PY" utils/permutation_probe.py --games "$PERM_GAMES" \
        --dump "$OUT/permutacion"
bloque B5  "Soak de propiedades a $EJEMPLOS ejemplos" -- \
    env PTCG_HYPOTHESIS_EXAMPLES="$EJEMPLOS" "$PY" -m pytest -q \
        tests/test_invariants.py tests/test_properties_of_any_legal_board.py
bloque B6  "Radar de colisiones sobre los 19 sinteticos" -- \
    "$PY" utils/collision_radar.py --games "$RADAR_GAMES"

TOTAL=$((SECONDS - INICIO))
marca "noche terminada en $((TOTAL/3600))h $(((TOTAL%3600)/60))m"
{
    echo
    echo "total $((TOTAL/3600))h $(((TOTAL%3600)/60))m"
    echo "arbol al terminar: $(git status --porcelain | wc -l | tr -d ' ') ficheros sucios"
    echo
    echo "rc != 0 NO es un fallo en B4 (la sonda informa por codigo de salida)."
} >> "$OUT/RESUMEN.txt"

cat "$OUT/RESUMEN.txt"
