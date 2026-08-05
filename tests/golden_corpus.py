"""Golden corpus: a replay of ALL the records with a snapshot of decisions.

Phase 2 of the strategy improvement architecture. The tests with fixtures
cover the steps that already hurt; the golden corpus covers ALL the decisions
of the current records: every change in main.py produces an explicit diff
of which historical decisions it flips, and any unexpected flip goes to
review BEFORE the merge (the "it came back" class of regression).

The records (`records/*.json`, the output of utils/split_turns.py) are LOCAL
and transient data (git-ignored): they are replaced when new games are
analysed. That is why the snapshot (`records/golden_decisions.json`)
lives alongside them (inheriting the ignore) and keeps an md5 hash per record, to
tell two failures with different messages apart:

  1. "the record changed on disk" -> regenerate the snapshot (new data);
  2. "the decisions changed with the same records" -> YOUR change to
     main.py flipped historical decisions: review each flip (was it intended?).

Usage:
    python tests/golden_corpus.py               # compare (exit 1 if it differs)
    python tests/golden_corpus.py --update  # review the diff and rewrite

The replay resets the agent's global state BEFORE EACH FILE (the same
semantics as the tests with fixtures: each record is a segment replayed
from cold). Only the ACTIVE items with a select are replayed.
"""

import hashlib
import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

RECORDS_PATH = _ROOT / "records"
SNAPSHOT_PATH = RECORDS_PATH / "golden_decisions.json"

# Readable OptionType values (cg/api.py).
_TIPOS = {0: "NUM", 1: "SI", 2: "NO", 3: "CARTA", 4: "TOOL", 5: "ECARD",
          6: "ENERGIA", 7: "PLAY", 8: "ATTACH", 9: "EVOLVE", 10: "ABILITY",
          11: "DISCARD", 12: "RETREAT", 13: "ATTACK", 14: "END", 15: "SKILL",
          16: "COND"}


def _main_mod():
    os.chdir(_ROOT)  # main.py opens deck.csv with a relative path
    import main as m
    return m


def reset_agent(m):
    """A mirror of the autouse fixture `reset_main_state` of tests/test_main.py.

    The state that persists between turns lives in `AGENT_STATE` since wave 3, and its
    `reset()` is the ONLY source of the initial values. It used to be set field
    by field with `m.<field> = ...`, which depended on main.py's compatibility
    bridge -- and that bridge is only installed when main.py is imported as a
    module, not when selfplay loads it with `module_from_spec` without registering it in
    sys.modules. There the assignments went to a dead attribute, the reset did
    not happen and the state leaked from one game to the next.
    """
    state = getattr(m, "AGENT_STATE", None)
    if state is not None:
        # ORDER: first `reset()` -- which leaves ACTIVE_CARDS_IN_DECK empty -- and
        # THEN the scan that fills it from deck.csv. The other way round, the reset
        # erased the tracking that had just been built and the agent started each
        # game believing its deck is empty.
        state.reset()
        m._init_cards_tracking()
        return

    m._init_cards_tracking()
    m._cards_first_scan_done = False
    m._cards_prizes_identified = False
    m._cards_last_turn = -1

    # COMPATIBILITY branch: a main.py older than wave 3, where the state consists of
    # module globals. utils/shadow.py compares the current version against a
    # frozen baseline, so this reset has to serve both.
    m.plan = m.AttackPlan()
    m.pre_turn = 0
    m.meganium_in_play = False
    m.forest_in_play = False
    m.ko_last_turn = False
    m._ko_detected_this_turn = False
    m._prev_op_prize = 6
    m.we_go_first = False
    m.op_is_crustle_deck = False
    m.op_is_cornerstone_deck = False
    m.op_has_mega_kangaskhan = False
    m._field_at_turn_start = {}
    m._poke_pad_target_id = 0
    m._ub_meowth_pending = False
    m._ub_fez_pending = False
    m._ld_supp_comprometido = 0
    m._dodge_immune_serial = None
    m._dodge_immune_turn = -1
    m._op_prize_denial_pecharunt = False
    m._op_prize_denial_gengar = False


def _name(m, cid):
    data = m.card_table.get(cid)
    return f"{data.name}({cid})" if data is not None else str(cid)


def describir_opcion(m, obs, idx):
    """A readable label for option `idx` of the select of `obs`."""
    sel = obs["select"]
    if idx >= len(sel["option"]):
        return f"?idx{idx}"
    o = sel["option"][idx]
    t = o.get("type")
    etiqueta = _TIPOS.get(t, f"t{t}")
    me = obs["current"]["players"][obs["current"]["yourIndex"]]
    try:
        if t == 7:  # PLAY: an index over the hand
            return f"PLAY {_name(m, me['hand'][o['index']]['id'])}"
        if t == 3:  # CARD: an index over the area (visible deck, hand, field...)
            area = o.get("area")
            if area == 1 and sel.get("deck"):
                return f"CARTA {_name(m, sel['deck'][o['index']]['id'])}"
            if area == 2 and me.get("hand"):
                return f"CARTA {_name(m, me['hand'][o['index']]['id'])}"
            jugador = obs["current"]["players"][o.get("playerIndex", 0)]
            if area == 4 and jugador["active"]:
                return f"CARTA {_name(m, jugador['active'][0]['id'])}"
            if area == 5:
                return f"CARTA {_name(m, jugador['bench'][o['index']]['id'])}"
            return f"CARTA a{area} i{o.get('index')}"
        if t == 8:  # ATTACH: a target in play
            if o.get("inPlayArea") == 4:
                return f"ATTACH->{_name(m, me['active'][0]['id'])}"
            return f"ATTACH->{_name(m, me['bench'][o['inPlayIndex']]['id'])}"
        if t == 10:  # ABILITY
            if o.get("area") == 4:
                return f"ABILITY {_name(m, me['active'][0]['id'])}"
            return f"ABILITY {_name(m, me['bench'][o['index']]['id'])}"
        if t == 13:
            return f"ATTACK id{o.get('attackId')}"
    except (IndexError, KeyError, TypeError):
        return f"{etiqueta} (irresoluble)"
    return etiqueta


def _our_deck_ids():
    csv = (_ROOT / "deck.csv").read_text().split("\n")
    return {int(csv[i]) for i in range(60)}


def our_index(data):
    """The seat (0 or 1) in which WE play in this episode.

    It is not always 0: depending on the pairing we can be player 1
    (e.g. episode 87709673). It is decided by a vote: the seat whose
    VISIBLE cards match deck.csv the most. Without this, the replay
    fed the agent with the OPPONENT's observations (their `yourIndex`)
    and also skipped all our decisions.
    """
    deck = _our_deck_ids()
    votos = [0, 0]
    decide = [0, 0]
    for step in data.get("steps", []):
        for item in step:
            obs = item.get("observation") or {}
            cur = obs.get("current")
            if not cur:
                continue
            if item.get("status") == "ACTIVE" and obs.get("select"):
                asiento = cur.get("yourIndex")
                if asiento in (0, 1):
                    decide[asiento] += 1
            for idx, jugador in enumerate(cur.get("players", [])):
                vistas = []
                for pk in (jugador.get("active") or []) + (
                        jugador.get("bench") or []):
                    if pk:
                        vistas.append(pk.get("id"))
                for card in (jugador.get("discard") or []):
                    vistas.append(card.get("id"))
                for card in (jugador.get("hand") or []):
                    vistas.append(card.get("id"))
                votos[idx] += sum(1 for cid in vistas if cid in deck)
    elegido = 0 if votos[0] >= votos[1] else 1
    # A MIRROR match makes the vote meaningless: both seats play deck.csv, so it
    # is decided by how much of each side happens to be visible. In
    # registro_013 (episode 89616806, our agent against itself) it picked the seat
    # that does not act in that segment and the record contributed ZERO decisions
    # -- a record inside the corpus that gated nothing, and silently, because an
    # empty list compares equal to an empty list forever.
    # When the chosen seat takes no decision and the other one does, the other one
    # is our seat: no record in the corpus may be a no-op.
    if decide[elegido] == 0 and decide[1 - elegido] > 0:
        return 1 - elegido
    return elegido


def replay_record(m, path):
    """Replays a record from cold and returns OUR decisions."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    yo = our_index(data)
    reset_agent(m)
    decisiones = []
    for step in data.get("steps", []):
        for item in step:
            obs = item.get("observation") or {}
            cur = obs.get("current") or {}
            if (item.get("status") != "ACTIVE" or not obs.get("select")
                    or cur.get("yourIndex") != yo):
                continue
            choice = m.agent(obs)
            decisiones.append({
                # Our ACTIVE observations do not carry a "step" (only the
                # INACTIVE ones of the other seat do): the decision is identified
                # by turn/action, which is stable.
                "paso": obs.get("step"),
                "turno": (obs.get("current") or {}).get("turn"),
                "accion": (obs.get("current") or {}).get("turnActionCount"),
                "contexto": obs["select"].get("context"),
                "eleccion": list(choice),
                "detalle": [describir_opcion(m, obs, i) for i in choice],
            })
    return decisiones


def _md5(path):
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


def record_files():
    return sorted(p for p in RECORDS_PATH.glob("registro_*.json"))


def build_corpus():
    m = _main_mod()
    corpus = {}
    for path in record_files():
        corpus[path.name] = {
            "md5": _md5(path),
            "decisiones": replay_record(m, path),
        }
    return corpus


def load_snapshot():
    if not SNAPSHOT_PATH.exists():
        return None
    with open(SNAPSHOT_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_snapshot(corpus):
    with open(SNAPSHOT_PATH, "w", encoding="utf-8") as f:
        json.dump(corpus, f, ensure_ascii=False, indent=1, sort_keys=True)


def comparar(dorado, actual):
    """Returns (changed_records, missing, new, flips).

    flips: a list of dicts with file/step/golden/current, ONLY from files
    whose md5 matches (the same data, different decisions => a code change).
    """
    cambiados, flips = [], []
    faltantes = sorted(set(dorado) - set(actual))
    nuevos = sorted(set(actual) - set(dorado))
    for name in sorted(set(dorado) & set(actual)):
        oro, today = dorado[name], actual[name]
        if oro["md5"] != today["md5"]:
            cambiados.append(name)
            continue
        # A DIFFERENT NUMBER OF DECISIONS ON THE SAME DATA is a flip too, and the
        # `zip` below hides it: it stops at the shorter list, so a record that
        # went from 0 decisions to 19 (which is what happened to registro_013 when
        # the seat of a mirror match was resolved) compared as "no changes". The
        # count is the first thing that has to match.
        if len(oro["decisiones"]) != len(today["decisiones"]):
            flips.append({
                "archivo": name,
                "paso": "recuento",
                "dorado": f"{len(oro['decisiones'])} decisiones",
                "actual": f"{len(today['decisiones'])} decisiones",
            })
        for d_oro, d_today in zip(oro["decisiones"], today["decisiones"]):
            if d_oro["eleccion"] != d_today["eleccion"]:
                _id = (f"paso {d_oro['paso']}" if d_oro.get("paso") is not None
                       else f"turno {d_oro.get('turno')} accion {d_oro.get('accion')}")
                flips.append({
                    "archivo": name,
                    "paso": _id,
                    "dorado": f"{d_oro['eleccion']} {d_oro['detalle']}",
                    "actual": f"{d_today['eleccion']} {d_today['detalle']}",
                })
    return cambiados, faltantes, nuevos, flips


def formatear_flips(flips):
    lines = []
    for f in flips:
        lines.append(f"  {f['archivo']} {f['paso']}:")
        lines.append(f"    dorado: {f['dorado']}")
        lines.append(f"    actual: {f['actual']}")
    return "\n".join(lines)


def main(argv):
    update = "--update" in argv
    actual = build_corpus()
    dorado = load_snapshot()

    if dorado is None:
        save_snapshot(actual)
        n = sum(len(v["decisiones"]) for v in actual.values())
        print(f"Snapshot inicial creado: {SNAPSHOT_PATH.name} "
              f"({len(actual)} registros, {n} decisiones)")
        return 0

    cambiados, faltantes, nuevos, flips = comparar(dorado, actual)

    if cambiados or faltantes or nuevos:
        print("Records changed on disk (new data, not a flip):")
        for n in cambiados:
            print(f"  ~ {n}")
        for n in faltantes:
            print(f"  - {n} (no longer there)")
        for n in nuevos:
            print(f"  + {n} (nuevo)")
    if flips:
        print("DECISIONS FLIPPED with the same records "
              "(a code change):")
        print(formatear_flips(flips))
    if not (cambiados or faltantes or nuevos or flips):
        print("Golden corpus: no changes.")
        return 0

    if update:
        save_snapshot(actual)
        print(f"\nSnapshot actualizado: {SNAPSHOT_PATH}")
        return 0
    print("\n(use --update to accept these changes)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
