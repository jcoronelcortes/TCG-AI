#!/usr/bin/env bash
#
# The night of 10 August 2026, after the meta moved.
#
# `docs/night-plan-2026-08-10-b.md` asked six questions and answered one of
# them, at 5 games instead of 2 000. Its five unanswered blocks are still the
# right questions -- but they were written against a corpus that no longer
# exists. The leaderboard was re-harvested on the 9th: 267 of the 300 lists
# changed content, Mega Lopunny / Mega Froslass went from 9 decks to 24, and
# `deck/real_opponents/` -- numbered BY META WEIGHT -- was rebuilt from scratch.
#
# So this run is not "relaunch the b night". It is the same six questions asked
# of the corpus that now exists, plus the one measurement the rebuild makes
# newly cheap and newly necessary:
#
#   B1a  the differential oracle over EVERY real list (it has only ever seen
#        the 19 synthetic ones, and now not even the real ones it saw are these)
#   B1b  the five worst by RATE, dumped as fixtures
#   B2   the Crustle axis with tight intervals, and a control family
#   B3   the invariant monitor at ten times the sample, every violation dumped
#   B4   the order-dependent decisions, dumped so they can be triaged
#   B5   the property soak at ten times the budget
#   B6   the collision radar -- now able to look at the REAL lists, which is
#        the question it was built for and could not be pointed at until today
#   B7   the weighted matchup matrix over the new corpus: the only number that
#        says "how we do against the meta that exists", and it does not exist
#        for these lists
#
# Everything it writes lives under log/noche_2026-08-10-c/. Nothing outside it
# is touched: no block writes to main.py, ptcg/ or deck/.
#
# No block can stop the night. A block that fails leaves its log and the next
# one starts, because a run that aborts halfway attributes its own damage to
# the wrong stage.
#
# Usage:
#   bash utils/noche_2026-08-10-c.sh
#   PY=.venv/bin/python bash utils/noche_2026-08-10-c.sh   # another interpreter
#   SOLO=B2,B6 bash utils/noche_2026-08-10-c.sh            # relaunch some blocks
#   CENSO_GAMES=150 bash utils/noche_2026-08-10-c.sh       # half a night

set -u

cd "$(dirname "$0")/.." || exit 1
ROOT="$PWD"
OUT="$ROOT/log/noche_2026-08-10-c"
PY="${PY:-.venv/bin/python}"
SOLO="${SOLO:-}"
CORPUS="${CORPUS:-$ROOT/deck/real_opponents}"

mkdir -p "$OUT"

# Sample sizes in one place, so a shorter night is one edit and not a rewrite.
CENSO_GAMES="${CENSO_GAMES:-300}"         # B1a, per real list
PROFUNDO_GAMES="${PROFUNDO_GAMES:-1000}"  # B1b, per deck among the five worst
MATRIZ_GAMES="${MATRIZ_GAMES:-1000}"      # B2, per matchup
MONITOR_GAMES="${MONITOR_GAMES:-20000}"   # B3
PERM_GAMES="${PERM_GAMES:-2000}"          # B4
EJEMPLOS="${EJEMPLOS:-200000}"            # B5, hypothesis examples
RADAR_GAMES="${RADAR_GAMES:-400}"         # B6, per real list
MATRIZ_META_GAMES="${MATRIZ_META_GAMES:-300}"   # B7, per matchup

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
    marca "[$id] termina rc=$rc en $((dt/60))m $((dt%60))s -> log/noche_2026-08-10-c/${id}.log"
    printf '%-5s rc=%-3s %4dm %02ds  %s\n' "$id" "$rc" "$((dt/60))" "$((dt%60))" "$titulo" \
        >> "$OUT/RESUMEN.txt"
}

# The names of the real lists, read from the corpus rather than hardcoded: the
# whole point of tonight is that these names moved.
#
# A plain glob and not `find | xargs basename`. This project lives under
# "VS Proyectos/TCG AI", xargs splits its input on whitespace, and the dry run
# of this script duly reported 261 lists instead of 87 and spent seven minutes
# censusing decks called `VS` and `TCG`. It failed with exit code 0 and a full
# log, which is the shape of failure this repository keeps naming: a number
# that looks like a measurement.
listas() {
    local f nombre
    for f in "$CORPUS"/*.csv; do
        [ -e "$f" ] || continue
        nombre="$(basename "$f" .csv)"
        [ "$nombre" = "pesos" ] && continue
        printf '%s\n' "$nombre"
    done
}

# --- B1a: the oracle over every real list -----------------------------------
# One invocation per deck so each one runs its own SELF-TEST. A census whose
# detector cannot prove it still works is the result that misleads worst: it
# says "nothing found" and it means "nothing looked".
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
for tasa, mazo in sorted(tasas, reverse=True)[:5]:
    if tasa > 0:
        print(mazo)
PY
}

profundo_oraculo() {
    local nombre
    if [ ! -s "$OUT/B1a.log" ]; then
        echo "sin censo (B1a) del que sacar los peores: nada que profundizar"
        return 0
    fi
    local hubo=0
    peores_del_censo | while read -r nombre; do
        [ -z "$nombre" ] && continue
        hubo=1
        echo "### $nombre  ($PROFUNDO_GAMES partidas, con volcado)"
        "$PY" utils/differential_oracle.py \
            --games "$PROFUNDO_GAMES" \
            --opponent "$CORPUS/$nombre.csv" \
            --dump "$OUT/violaciones_oraculo/$nombre" 2>&1
        echo
    done
    [ "$hubo" = 0 ] && echo "(el censo no dejo ningun mazo con tasa > 0)"
    return 0
}

# --- B2: the Crustle axis, and a control family -----------------------------
# The families are read from the corpus, not written down: after the rebuild
# `crustle_wall_6` is a rank and not a deck, and the number of lists per family
# has moved with the meta.
eje_crustle() {
    local lista
    lista="$(listas | grep -E '^(crustle_wall|mega_lucario)_[0-9]+$' | paste -sd, -)"
    if [ -z "$lista" ]; then
        echo "no hay listas crustle_wall ni mega_lucario en $CORPUS"
        return 1
    fi
    echo "corpus: $CORPUS"
    echo "decks: $lista"
    echo
    "$PY" utils/matchup_matrix.py --games "$MATRIZ_GAMES" \
        --opponents "$CORPUS" --only "$lista"
}

# --- B2b: the dead deck, measured once before it stops mattering ------------
# The corpus bridge says the old `crustle_wall_6` -- the 54.5 %, eighteen points
# below its own family -- is GONE from the top 300: the nearest list in the new
# corpus is 32 cards away, and the NAME has landed on a deck nobody has ever
# measured. The list itself still exists, in the 7 August backup, and this is
# the last night it is worth a game: at n=1 000 it separates "the finding was
# the +/-7 of 200 games" from "we really do lose to that shell". One of those
# answers transfers to the six new crustle_wall lists and the other does not.
eje_crustle_muerto() {
    local viejo="$ROOT/deck/real_opponents_2026-08-07"
    if [ ! -f "$viejo/crustle_wall_6.csv" ]; then
        echo "no hay respaldo del corpus viejo en $viejo: nada que cerrar"
        return 0
    fi
    echo "corpus RETIRADO: $viejo"
    echo "el mazo que produjo el 54,5% y ya no esta en el meta"
    echo
    "$PY" utils/matchup_matrix.py --games "$MATRIZ_GAMES" \
        --opponents "$viejo" --only crustle_wall_6,crustle_wall_1,crustle_wall_2
}

# --- B7: how we do against the meta that actually exists --------------------
weighted_matrix() {
    "$PY" utils/matchup_matrix.py --games "$MATRIZ_META_GAMES" \
        --opponents "$CORPUS" --weights
}

# ----------------------------------------------------------------------------

: > "$OUT/RESUMEN.txt"
marca "arranca la noche, salida en log/noche_2026-08-10-c/"
marca "HEAD $(git rev-parse --short HEAD), arbol $(git status --porcelain | wc -l | tr -d ' ') ficheros sucios"
marca "corpus $CORPUS ($(listas | wc -l | tr -d ' ') listas reales)"
{
    echo "HEAD $(git rev-parse --short HEAD)"
    echo "corpus $CORPUS  ($(listas | wc -l | tr -d ' ') listas)"
    echo "arranque $(date '+%Y-%m-%d %H:%M:%S')"
    echo
} >> "$OUT/RESUMEN.txt"
INICIO=$SECONDS

bloque B1a "El oraculo contra TODAS las listas reales nuevas" -- censo_oraculo
bloque B1b "Los cinco peores del censo, con volcado" -- profundo_oraculo
bloque B2  "El eje Crustle con intervalos estrechos + control" -- eje_crustle
bloque B2b "El crustle_wall_6 RETIRADO, medido a n=$MATRIZ_GAMES" -- eje_crustle_muerto
bloque B3 "El monitor a $MONITOR_GAMES partidas, con volcado" -- \
    "$PY" utils/invariant_monitor.py --games "$MONITOR_GAMES" \
        --dump "$OUT/violaciones_monitor" --progress 2000
bloque B4  "La sonda de permutacion a $PERM_GAMES, volcada para triaje" -- \
    "$PY" utils/permutation_probe.py --games "$PERM_GAMES" \
        --dump "$OUT/permutacion"
bloque B5  "Soak de propiedades a $EJEMPLOS ejemplos" -- \
    env PTCG_HYPOTHESIS_EXAMPLES="$EJEMPLOS" "$PY" -m pytest -q \
        tests/test_invariants.py tests/test_properties_of_any_legal_board.py
bloque B6  "Radar de colisiones sobre las listas REALES" -- \
    "$PY" utils/collision_radar.py --games "$RADAR_GAMES" --opponents "$CORPUS"
bloque B7  "Matriz ponderada contra el meta nuevo" -- weighted_matrix

TOTAL=$((SECONDS - INICIO))
marca "noche terminada en $((TOTAL/3600))h $(((TOTAL%3600)/60))m"
{
    echo
    echo "total $((TOTAL/3600))h $(((TOTAL%3600)/60))m"
    echo "fin $(date '+%Y-%m-%d %H:%M:%S')"
    echo "arbol al terminar: $(git status --porcelain | wc -l | tr -d ' ') ficheros sucios"
    echo
    echo "rc != 0 NO es un fallo en B4 (la sonda informa por codigo de salida)."
} >> "$OUT/RESUMEN.txt"

cat "$OUT/RESUMEN.txt"
