#!/usr/bin/env bash
#
# The night of 11 August 2026 -- track M (measurement).
#
# See docs/night-plan-2026-08-11.md. This script is HALF the night: the CPU
# half, the one that answers questions already written down. The other half is
# construction, and it happens in the working tree AT THE SAME TIME.
#
# THAT IS WHY THIS SCRIPT RUNS FROM AN EXPORTED TREE. `git archive HEAD` is
# unpacked into log/noche-2026-08-11/tree/ and every block runs from there, so
# editing and committing the working tree all night cannot make a block load a
# half-written file. It is the fix of 6c08b87 (`checkout_tree`) reused: loading
# one file was never the agent.
#
# `records/` is NOT in the export -- one of its sixteen files is tracked,
# because it is transient by design. No block here needs it: they play games or
# replay the frozen corpus, and both of those are tracked.
#
# NOTHING OUTSIDE log/noche-2026-08-11/ IS WRITTEN. No block touches main.py,
# ptcg/ or deck/. While this is alive, no swap-based harness may run --
# utils/mutation_probe.py above all: it IS the tree for the length of a run, and
# this project has lost work to that twice in one night.
#
# NO BLOCK CAN STOP THE NIGHT. A failure leaves its log and the next one starts;
# a run that aborts halfway attributes its own damage to the wrong stage.
#
# Usage:
#   bash utils/noche-2026-08-11.sh
#   JOBS=3 bash utils/noche-2026-08-11.sh              # gentler on the machine
#   SOLO=M1,M2 bash utils/noche-2026-08-11.sh          # relaunch some blocks
#   GATE_GAMES=3000 bash utils/noche-2026-08-11.sh     # half a night

set -u

cd "$(dirname "$0")/.." || exit 1
ROOT="$PWD"
OUT="$ROOT/log/noche-2026-08-11"
TREE="$OUT/tree"
PY="${PY:-$ROOT/.venv/bin/python}"
SOLO="${SOLO:-}"
JOBS="${JOBS:-6}"                 # concurrent blocks; 10 were authorised, 6 leaves headroom

# Sample sizes in one place, so a shorter night is one edit and not a rewrite.
GATE_GAMES="${GATE_GAMES:-15000}"       # M1/M2, per arm
CENSO_GAMES="${CENSO_GAMES:-300}"       # M3, per real list
PROFUNDO_GAMES="${PROFUNDO_GAMES:-1000}" # M4, per deck among the five worst
MONITOR_GAMES="${MONITOR_GAMES:-30000}" # M5
PERM_GAMES="${PERM_GAMES:-4000}"        # M6
EJEMPLOS="${EJEMPLOS:-200000}"          # M7, hypothesis examples
MATRIZ_GAMES="${MATRIZ_GAMES:-400}"     # M8, per matchup

mkdir -p "$OUT"

marca() { printf '%s  %s\n' "$(date '+%H:%M:%S')" "$*"; }

quiere() {   # honours SOLO=M1,M3; with SOLO unset, everything runs
    [ -z "$SOLO" ] && return 0
    case ",$SOLO," in *",$1,"*) return 0;; *) return 1;; esac
}

# One line per finished block, appended by the child itself. Short writes to an
# O_APPEND file do not interleave, so the summary survives the concurrency.
anota() {
    printf '%-5s rc=%-3s %4dm %02ds  %s\n' "$1" "$2" "$(($3/60))" "$(($3%60))" "$4" \
        >> "$OUT/RESUMEN.txt"
}

# The semaphore. Polled rather than `wait -n`, because macOS ships bash 3.2 and
# `wait -n` is 4.3: on this machine the clever version degrades to exactly this
# loop with an error message swallowed, and a night is not the place for a
# construct that only works somewhere else.
espera_hueco() {
    while [ "$(jobs -rp | wc -l)" -ge "$JOBS" ]; do
        sleep 5
    done
}

bloque() {   # bloque <id> <title> -- <command...>
    local id="$1" titulo="$2"; shift 3
    quiere "$id" || { marca "[$id] saltado (SOLO=$SOLO)"; return 0; }
    espera_hueco
    marca "[$id] $titulo — empieza"
    (
        cd "$TREE" || exit 1
        local t0=$SECONDS
        "$@" > "$OUT/${id}.log" 2>&1
        local rc=$? dt=$((SECONDS - t0))
        anota "$id" "$rc" "$dt" "$titulo"
        marca "[$id] termina rc=$rc en $((dt/60))m $((dt%60))s -> ${id}.log"
    ) &
}

# --- the export ------------------------------------------------------------
preparar_arbol() {
    rm -rf "$TREE"
    mkdir -p "$TREE"
    git -C "$ROOT" archive --format=tar HEAD | tar -x -C "$TREE" || return 1
    # The frozen corpus and the real lists must have made it across, or several
    # blocks would run and report nothing rather than fail.
    [ -f "$TREE/tests/corpus/frozen_decisions.json" ] || { echo "sin corpus congelado"; return 1; }
    [ -d "$TREE/deck/real_opponents" ] || { echo "sin corpus de rivales"; return 1; }
    [ -f "$TREE/deck.csv" ] || echo "AVISO: no hay deck.csv en la raiz exportada"
    return 0
}

CORPUS="$TREE/deck/real_opponents"

# The names of the real lists, read from the corpus rather than hardcoded: a
# rank is not a deck, and these names move with every harvest.
#
# A plain glob and not `find | xargs basename`: this project lives under
# "VS Proyectos/TCG AI", xargs splits on whitespace, and a previous night duly
# censused decks called `VS` and `TCG` -- exit code 0, full log, nonsense.
listas() {
    local f nombre
    for f in "$CORPUS"/*.csv; do
        [ -e "$f" ] || continue
        nombre="$(basename "$f" .csv)"
        [ "$nombre" = "pesos" ] && continue
        printf '%s\n' "$nombre"
    done
}

# --- M0: the exposure of every gate this project has built ------------------
# Frequency before winrate, made routine. A census is the CEILING of any effect
# a rule can have; four of them together is the table nobody has ever printed.
censo_de_censos() {
    local g nombre
    for g in "$TREE"/utils/gate_*.py; do
        [ -e "$g" ] || continue
        nombre="$(basename "$g")"
        grep -q -- "--census" "$g" || { echo "### $nombre  (sin --census, saltado)"; echo; continue; }
        echo "### $nombre"
        "$PY" "$g" --census 2>&1
        echo
    done
}

# --- M1/M2: the pending falsification --------------------------------------
# The criterion is written in docs/night-plan-2026-08-11.md §3, BEFORE the
# number exists. --control is not optional: both arms neutralised at the same n
# is that run's noise floor, measured instead of assumed.

# --- M3: the oracle over every real list -----------------------------------
# One invocation per deck so each runs its own SELF-TEST. A census whose
# detector cannot prove it still works is the result that misleads worst.
#
# This is the first WIDE run since the target fix of 51dc87d: 89.2 % of the
# oracle's previous findings were scored against the wrong body, so every
# residue figure on record is inflated.
censo_oraculo() {
    local nombre
    listas | while read -r nombre; do
        [ -z "$nombre" ] && continue
        echo "### $nombre"
        "$PY" utils/differential_oracle.py --games "$CENSO_GAMES" \
            --opponent "$CORPUS/$nombre.csv" 2>&1
        echo
    done
}

# --- M4: the five worst of M3, by RATE, dumped ------------------------------
# By rate and not by count: a deck that judges twice as many attacks reports
# twice as many findings at the same defect level. Runs in the same slot as M3
# because it reads M3's log.
peores_del_censo() {
    "$PY" - "$OUT/M3.log" <<'PY'
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
for tasa, mazo in sorted(tasas, reverse=True)[:5]:
    if tasa > 0:
        print(mazo)
PY
}

oraculo_censo_y_profundo() {
    censo_oraculo > "$OUT/M3.log" 2>&1
    echo "=== M4: los cinco peores por TASA, con volcado ==="
    if [ ! -s "$OUT/M3.log" ]; then
        echo "sin censo del que sacar los peores"
        return 0
    fi
    local nombre encontrados=0
    while read -r nombre; do
        [ -z "$nombre" ] && continue
        encontrados=$((encontrados + 1))
        echo "### $nombre  ($PROFUNDO_GAMES partidas, con volcado)"
        "$PY" utils/differential_oracle.py \
            --games "$PROFUNDO_GAMES" \
            --opponent "$CORPUS/$nombre.csv" \
            --dump "$OUT/violaciones_oraculo/$nombre" 2>&1
        echo
    done < <(peores_del_censo)
    [ "$encontrados" = 0 ] && echo "(el censo no dejo ningun mazo con tasa > 0)"
    return 0
}

# --- M8: how we do against the meta that actually exists --------------------
matriz_ponderada() {
    "$PY" utils/matchup_matrix.py --games "$MATRIZ_GAMES" \
        --opponents "$CORPUS" --weights
}

# ----------------------------------------------------------------------------

: > "$OUT/RESUMEN.txt"
marca "arranca la noche (carril M), salida en log/noche-2026-08-11/"
marca "exportando el arbol de HEAD a $TREE"
if ! preparar_arbol; then
    marca "EL EXPORT FALLO: sin arbol congelado no se mide nada. Abortando."
    exit 1
fi

SUCIOS="$(git -C "$ROOT" status --porcelain | wc -l | tr -d ' ')"
marca "HEAD $(git -C "$ROOT" rev-parse --short HEAD), arbol de trabajo $SUCIOS ficheros sucios"
marca "corpus $CORPUS ($(listas | wc -l | tr -d ' ') listas reales), JOBS=$JOBS"
{
    echo "HEAD      $(git -C "$ROOT" rev-parse --short HEAD)"
    echo "arbol     exportado en $TREE (el de trabajo sigue vivo y editable)"
    echo "corpus    $CORPUS  ($(listas | wc -l | tr -d ' ') listas)"
    echo "arranque  $(date '+%Y-%m-%d %H:%M:%S')   JOBS=$JOBS"
    echo
} >> "$OUT/RESUMEN.txt"
INICIO=$SECONDS

bloque M0 "El censo de TODOS los gates: exposicion antes que winrate" -- censo_de_censos
bloque M1 "Falsacion coste/busqueda, n=$GATE_GAMES" -- \
    "$PY" utils/gate_the_search_buys.py --games "$GATE_GAMES" --progress 1000
bloque M2 "El suelo de ruido de esa misma corrida (--control), n=$GATE_GAMES" -- \
    "$PY" utils/gate_the_search_buys.py --games "$GATE_GAMES" --progress 1000 --control
bloque M34 "El oraculo (arreglado) contra las $(listas | wc -l | tr -d ' ') listas reales, + los cinco peores" -- \
    oraculo_censo_y_profundo
# `--dump-kinds all` and not the default: the first run of this block asked for a
# dump, counted 294 012 findings and wrote ZERO observations, because the default
# kind list does not include the two that actually fired (STALE_FLAG and
# STALE_READ). The monitor said so in its own output -- which is the behaviour
# this repository asks of a detector -- and the script is what should have
# listened. A dump nobody can open is a finding nobody can act on.
bloque M5 "El monitor de invariantes a $MONITOR_GAMES partidas, con volcado" -- \
    "$PY" utils/invariant_monitor.py --games "$MONITOR_GAMES" \
        --dump "$OUT/violaciones_monitor" --dump-kinds all --progress 2000
bloque M6 "La sonda de permutacion a $PERM_GAMES, volcada para triaje" -- \
    "$PY" utils/permutation_probe.py --games "$PERM_GAMES" --dump "$OUT/permutacion"
bloque M7 "Soak de propiedades a $EJEMPLOS ejemplos" -- \
    env PTCG_HYPOTHESIS_EXAMPLES="$EJEMPLOS" "$PY" -m pytest -q \
        tests/test_invariants.py tests/test_properties_of_any_legal_board.py
bloque M8 "Matriz ponderada contra el meta que existe" -- matriz_ponderada

marca "todos los bloques lanzados; esperando a que terminen"
wait

TOTAL=$((SECONDS - INICIO))
marca "carril M terminado en $((TOTAL/3600))h $(((TOTAL%3600)/60))m"
{
    echo
    echo "total $((TOTAL/3600))h $(((TOTAL%3600)/60))m"
    echo "fin   $(date '+%Y-%m-%d %H:%M:%S')"
    echo
    echo "rc != 0 NO es un fallo en M6 (la sonda informa por codigo de salida)."
    echo "M1/M2 se leen JUNTOS: un delta que no supera el suelo del control no es un delta."
} >> "$OUT/RESUMEN.txt"

cat "$OUT/RESUMEN.txt"
