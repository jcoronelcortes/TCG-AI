"""Downloads the 60-card decks of the best competitors on the leaderboard.

Strategy (inherited from the notebook `notebook/ptcg-ai-battle-leaderboard-deck-meta-by-score-band.ipynb`):

    leaderboard -> submission per team -> public episodes ("Game History")
    -> replay JSON -> steps[1][seat]["action"] == the exact 60 cards

The replay does NOT have to be "guessed": step 1 of every game contains the literal
deck of each seat, so the list of 60 IDs is recovered exactly and not
by statistical inference over the cards seen in the log.

Each replay carries TWO decks (both seats). That is why:
  * if the opponent of a game is also in the top-N, their deck is recorded without
    spending a single extra API call;
  * the opponents outside the top-N are kept separately in `adicionales/` because they come
    for free and are just as useful for the simulator.

Output: one CSV per deck with 60 lines (one Card ID per line, no header), which
is exactly the format `deck.csv` and `deck/opponents/*.csv` already consume.

Typical usage:

    python utils/download_competitor_decks.py --top 100

The process is resumable: the decks already recovered are kept in a JSON cache,
so relaunching it only asks the API for what is missing.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable

RAIZ = Path(__file__).resolve().parent.parent

# --- Request policy (the same as the published notebook) -------------------
INTERVALO_PETICION_S = 2.0
TAM_LOTE = 100
ENFRIAMIENTO_LOTE_S = 60.0
MAX_REINTENTOS = 6
MAX_ESPERA_REINTENTO_S = 60.0
RETRYABLE_STATUSES = {408, 425, 500, 502, 503, 504}

COMPETICION = "pokemon-tcg-ai-battle"
TAM_PAGINA_LEADERBOARD = 200

# Basic energies: the only cards with no copy limit.
BASIC_ENERGIES = set(range(1, 9))
MAX_COPIES = 4

# Archetype rules, copied from the published notebook. They are evaluated from top
# to bottom: the specific hybrids go BEFORE the single-card rules.
#   "all" -> every marker card must be present
#   "any" -> one is enough
ARCHETYPES: list[dict[str, Any]] = [
    {"nombre": "Great Tusk / Crustle", "all": ["Great Tusk", "Crustle"]},
    {"nombre": "Marnie Grimmsnarl", "any": ["Marnie's Grimmsnarl ex"]},
    {"nombre": "Cynthia Garchomp", "any": ["Cynthia's Garchomp ex"]},
    {"nombre": "Mega Lucario", "any": ["Mega Lucario ex"]},
    {"nombre": "Archaludon", "any": ["Archaludon ex"]},
    {"nombre": "Crustle Wall", "any": ["Crustle"]},
    {"nombre": "Dragapult", "any": ["Dragapult ex"]},
    {"nombre": "Mega Starmie", "any": ["Mega Starmie ex"]},
    {"nombre": "Starmie", "any": ["Starmie ex", "Starmie"]},
    {"nombre": "Mega Gardevoir", "any": ["Mega Gardevoir ex"]},
    {"nombre": "Alakazam", "any": ["Alakazam ex", "Alakazam"]},
    {"nombre": "Iono Bellibolt", "any": ["Iono's Bellibolt ex"]},
    {"nombre": "Festival Lead", "any": ["Dipplin"]},
    {"nombre": "Hop Trevenant", "any": ["Hop's Trevenant"]},
    {"nombre": "Hop Snorlax", "any": ["Hop's Snorlax"]},
    {"nombre": "Mega Kangaskhan", "any": ["Mega Kangaskhan ex"]},
    {"nombre": "Chandelure", "any": ["Chandelure ex", "Chandelure"]},
    {"nombre": "Mega Greninja", "any": ["Mega Greninja ex"]},
    {"nombre": "Mega Clefable", "any": ["Mega Clefable ex"]},
    {"nombre": "Team Rocket Mewtwo", "any": ["Team Rocket's Mewtwo ex"]},
    # Added after measuring the top-100 of Aug 2026: they were the only decks that
    # fell to the "Otro /" fallback. They go AT THE END on purpose, so they cannot
    # steal a deck from any earlier, already validated rule.
    # The hybrid goes before its two separate pieces: there are lists that play
    # 2 Buneary + 2 Mega Lopunny ex AND 2 Snorunt + 2 Mega Froslass ex in equal
    # parts, and naming them after a single half would be arbitrary.
    {"nombre": "Mega Lopunny / Mega Froslass", "all": ["Mega Lopunny ex", "Mega Froslass ex"]},
    {"nombre": "Ogerpon Verde", "any": ["Teal Mask Ogerpon ex"]},
    {"nombre": "Mega Lopunny", "any": ["Mega Lopunny ex"]},
    {"nombre": "Mega Froslass", "any": ["Mega Froslass ex"]},
]


def card_key(name: Any) -> str:
    """Normalises a card name for comparison (typographic apostrophes, etc.)."""
    import unicodedata

    text = unicodedata.normalize("NFKC", str(name or ""))
    text = text.replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", text.strip()).casefold()


def classify_archetype(
    deck: list[int], names: dict[int, str], pokemon: set[int]
) -> str:
    """Labels the deck by marker cards; if there is no rule, it falls back to the ex Pokemon."""
    if not names:
        return ""
    presentes = {card_key(names.get(cid, "")) for cid in deck}
    for rule in ARCHETYPES:
        exigidas = {card_key(n) for n in rule.get("all", [])}
        alguna = {card_key(n) for n in rule.get("any", [])}
        if (not exigidas or exigidas.issubset(presentes)) and (not alguna or alguna & presentes):
            return rule["nombre"]

    # With no rule: the most repeated ex Pokemon is the most honest label.
    conteo: Counter[str] = Counter()
    for cid, n in Counter(deck).items():
        if cid in pokemon:
            conteo[str(names.get(cid, ""))] += n
    if not conteo:
        return "Desconocido"
    ex = [(n, nom) for nom, n in conteo.items() if card_key(nom).endswith(" ex")]
    candidates = ex or [(n, nom) for nom, n in conteo.items()]
    _, chosen = sorted(candidates, key=lambda t: (-t[0], t[1]))[0]
    return f"Otro / {chosen}"


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------
def load_credentials() -> None:
    """Exposes the Kaggle token in the environment BEFORE importing the SDK."""
    if os.environ.get("KAGGLE_API_TOKEN") or os.environ.get("KAGGLE_KEY"):
        return
    candidates = [
        Path.home() / ".kaggle" / "access_token",
        Path.home() / ".kaggle" / "kaggle_token.txt",
        RAIZ / "kaggle_token.txt",
        Path("kaggle_token.txt"),
    ]
    for path in candidates:
        try:
            if path.is_file():
                token = path.read_text(encoding="utf-8").strip()
                if token:
                    os.environ["KAGGLE_API_TOKEN"] = token
                    print(f"Kaggle token read from {path}")
                    return
        except OSError:
            continue
    print("Warning: no local token found; platform credentials will be used.")


# ---------------------------------------------------------------------------
# Normalising the SDK's objects
# ---------------------------------------------------------------------------
def normalizar(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [normalizar(v) for v in value]
    if isinstance(value, dict):
        return {str(k): normalizar(v) for k, v in value.items()}
    if hasattr(value, "to_dict"):
        return normalizar(value.to_dict())
    if hasattr(value, "name") and hasattr(value, "value"):
        return value.name
    crudo = getattr(value, "__dict__", {})
    return {
        str(k).lstrip("_"): normalizar(v)
        for k, v in crudo.items()
        if not str(k).startswith("__")
    }


def como_dict(obj: Any) -> dict[str, Any]:
    value = normalizar(obj)
    return value if isinstance(value, dict) else {}


def first(mapa: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in mapa and mapa[key] is not None:
            return mapa[key]
    return default


def a_float(value: Any) -> float:
    if value is None:
        return math.nan
    text = str(value).replace(",", "").strip()
    m = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    return float(m.group(0)) if m else math.nan


# ---------------------------------------------------------------------------
# Pacer + retries
# ---------------------------------------------------------------------------
class FalloDePeticion(RuntimeError):
    def __init__(self, etiqueta: str, state: int | None, intentos: int):
        self.state = state
        self.intentos = intentos
        detail = f"HTTP {state}" if state is not None else "error de red"
        super().__init__(f"{etiqueta} fallo tras {intentos} intento(s) ({detail}).")


class Marcapasos:
    """Spaces out ALL the requests and cools down after each batch."""

    def __init__(self, interval: float, tam_lote: int, enfriamiento: float):
        self.interval = float(interval)
        self.tam_lote = int(tam_lote)
        self.enfriamiento = float(enfriamiento)
        self.last_start = 0.0
        self.peticiones = 0

    def esperar(self) -> None:
        if self.peticiones and self.peticiones % self.tam_lote == 0:
            print(f"  [pause] batch of {self.tam_lote} requests: {self.enfriamiento:.0f}s")
            time.sleep(self.enfriamiento)
            self.last_start = time.monotonic()
        resto = self.interval - (time.monotonic() - self.last_start)
        if resto > 0:
            time.sleep(resto)
        self.last_start = time.monotonic()
        self.peticiones += 1


PACER = Marcapasos(INTERVALO_PETICION_S, TAM_LOTE, ENFRIAMIENTO_LOTE_S)
ERRORES: Counter[str] = Counter()


def http_status(exc: Exception) -> int | None:
    resp = getattr(exc, "response", None)
    crudo = getattr(resp, "status_code", None)
    if crudo is None:
        crudo = getattr(exc, "status", None)
    try:
        return int(crudo) if crudo is not None else None
    except (TypeError, ValueError):
        return None


def reintentar_tras(exc: Exception) -> float | None:
    resp = getattr(exc, "response", None)
    cabeceras = getattr(resp, "headers", None) or getattr(exc, "headers", None) or {}
    value = cabeceras.get("Retry-After") or cabeceras.get("retry-after")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        try:
            momento = parsedate_to_datetime(str(value))
            if momento.tzinfo is None:
                momento = momento.replace(tzinfo=timezone.utc)
            return max(0.0, (momento - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


def llamar(etiqueta: str, func: Callable, *args, **kwargs):
    """An API call with pacing, retries and a 429 = do-not-insist policy."""
    last: Exception | None = None
    intentos = 0
    for intento in range(MAX_REINTENTOS):
        intentos = intento + 1
        PACER.esperar()
        try:
            return func(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - the SDK raises heterogeneous types
            last = exc
            state = http_status(exc)
            ERRORES[f"http_{state}" if state is not None else type(exc).__name__] += 1
            # A 429 is skipped immediately: insisting only makes the limit worse.
            if state == 429:
                break
            recuperable = state is None or state in RETRYABLE_STATUSES
            if not recuperable or intento == MAX_REINTENTOS - 1:
                break
            espera = min(
                MAX_ESPERA_REINTENTO_S,
                max(reintentar_tras(exc) or 0.0, 2.0 * (2**intento)) + random.uniform(0.25, 1.25),
            )
            print(f"  [reintento] {etiqueta}: {state or type(exc).__name__}; espero {espera:.1f}s")
            time.sleep(espera)
    raise FalloDePeticion(etiqueta, http_status(last) if last else None, intentos) from last


# ---------------------------------------------------------------------------
# Card data (to validate and summarise)
# ---------------------------------------------------------------------------
def load_cards() -> tuple[dict[int, str], set[int], set[int]]:
    """Returns (name by Card ID, ACE SPEC Card IDs, Pokemon Card IDs)."""
    import csv

    path = None
    for cand in (RAIZ / "dataset" / "EN_Card_Data.csv", RAIZ / "EN_Card_Data.csv"):
        if cand.is_file():
            path = cand
            break
    if path is None:
        print("Warning: EN_Card_Data.csv not found; name validation is skipped.")
        return {}, set(), set()

    names: dict[int, str] = {}
    ace_spec: set[int] = set()
    pokemon: set[int] = set()
    type_column = "Stage (Pokémon)/Type (Energy and Trainer)"
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                cid = int(str(row["Card ID"]).strip())
            except (KeyError, TypeError, ValueError):
                continue
            names.setdefault(cid, str(row.get("Card Name", "")).strip())
            if str(row.get("Rule", "")).strip().upper() == "ACE SPEC":
                ace_spec.add(cid)
            if "pok" in str(row.get(type_column, "")).strip().lower():
                pokemon.add(cid)
    return names, ace_spec, pokemon


def validate_deck(deck: list[int], ace_spec: set[int]) -> list[str]:
    """Checks the construction rules. Returns the list of warnings."""
    avisos: list[str] = []
    if len(deck) != 60:
        avisos.append(f"tiene {len(deck)} cartas y no 60")
    conteo = Counter(deck)
    for cid, n in sorted(conteo.items()):
        if cid in BASIC_ENERGIES:
            continue  # a basic energy: no cap
        if n > MAX_COPIES:
            avisos.append(f"{n} copias del ID {cid} (max {MAX_COPIES})")
    n_ace = sum(n for cid, n in conteo.items() if cid in ace_spec)
    if n_ace > 1:
        avisos.append(f"{n_ace} cartas ACE SPEC (max 1)")
    return avisos


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------
def obtener_leaderboard(api, kaggle_mod, top_n: int) -> list[dict[str, Any]]:
    """Returns the first `top_n` positions (one team each, the highest score)."""
    from kaggle.api.kaggle_api_extended import ApiGetLeaderboardRequest

    rows: list[dict[str, Any]] = []
    token: str | None = None
    vistos: set[str] = set()

    with api.build_kaggle_client() as cliente:
        while True:
            peticion = ApiGetLeaderboardRequest()
            peticion.competition_name = COMPETICION
            peticion.page_size = TAM_PAGINA_LEADERBOARD
            if token:
                peticion.page_token = token
            respuesta = llamar(
                "pagina de leaderboard",
                cliente.competitions.competition_api_client.get_leaderboard,
                peticion,
            )
            rows.extend(como_dict(item) for item in (respuesta.submissions or []))
            next_item = str(respuesta.next_page_token or "")
            # With pages of 200 the first one is enough for a top-100, but paging
            # continues in case the endpoint returns shorter pages.
            if len(rows) >= top_n * 2 or not next_item or next_item in vistos:
                break
            vistos.add(next_item)
            token = next_item

    normalizadas = []
    for row in rows:
        team_id = first(row, "teamId", "team_id")
        score = a_float(first(row, "score", "publicScore", "public_score"))
        if team_id is None or math.isnan(score):
            continue
        normalizadas.append(
            {
                "team_id": int(team_id),
                "puntaje": score,
                "fecha": first(row, "submissionDate", "submission_date"),
            }
        )

    # A team can only occupy one position: we keep their best score.
    best_by_team: dict[int, dict[str, Any]] = {}
    for row in normalizadas:
        actual = best_by_team.get(row["team_id"])
        if actual is None or row["puntaje"] > actual["puntaje"]:
            best_by_team[row["team_id"]] = row

    ordenadas = sorted(
        best_by_team.values(), key=lambda f: (-f["puntaje"], f["team_id"])
    )[:top_n]
    for posicion, row in enumerate(ordenadas, start=1):
        row["posicion"] = posicion
    return ordenadas


def elegir_submission(api, team_id: int, puntaje_lb: float) -> dict[str, Any] | None:
    """The public submission whose score is closest to the leaderboard's."""
    submissions = llamar("submissions del equipo", api.competition_team_submissions, int(team_id)) or []
    candidatas: list[dict[str, Any]] = []
    for item in submissions:
        row = como_dict(item)
        sid = first(row, "id", "ref", "submissionId", "submission_id")
        if sid is None:
            continue
        candidatas.append(
            {
                "submission_id": int(sid),
                "puntaje": a_float(first(row, "publicScore", "public_score", "score")),
            }
        )
    if not candidatas:
        return None

    def order(row: dict[str, Any]):
        p = row["puntaje"]
        distancia = abs(p - puntaje_lb) if not math.isnan(p) else math.inf
        return (distancia, -p if not math.isnan(p) else math.inf, -row["submission_id"])

    return min(candidatas, key=order)


# ---------------------------------------------------------------------------
# Episodes ("Game History") and replays
# ---------------------------------------------------------------------------
def listar_episodios(api, submission_id: int) -> list[dict[str, Any]]:
    """Completed public episodes of a submission, from the most recent backwards."""
    episodios = llamar("episodios de la submission", api.competition_list_episodes, int(submission_id)) or []
    output: list[dict[str, Any]] = []
    for item in episodios:
        row = como_dict(item)
        eid = first(row, "id", "episodeId", "episode_id")
        if eid is None:
            continue
        tipo = str(first(row, "type", default="PUBLIC"))
        state = str(first(row, "state", default="COMPLETED"))
        if "PUBLIC" not in tipo.upper():
            continue
        if not re.search(r"COMPLETE", state, flags=re.IGNORECASE):
            continue
        row["id"] = int(eid)
        output.append(row)
    return sorted(output, key=lambda f: int(f["id"]), reverse=True)


def download_replay(api, episode_id: int, cache_dir: Path) -> dict[str, Any]:
    """Downloads (or reuses) an episode's replay JSON."""
    from kaggle.api.kaggle_api_extended import ApiGetEpisodeReplayRequest

    target_path = cache_dir / f"episode-{episode_id}-replay.json"
    if target_path.exists() and target_path.stat().st_size > 1000:
        try:
            return json.loads(target_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            target_path.unlink(missing_ok=True)

    def once() -> bytes:
        peticion = ApiGetEpisodeReplayRequest()
        peticion.episode_id = int(episode_id)
        with api.build_kaggle_client() as cliente:
            respuesta = cliente.competitions.competition_api_client.get_episode_replay(peticion)
            respuesta.raise_for_status()
            return respuesta.content

    contenido = llamar("replay del episodio", once)
    target_path.write_bytes(contenido)
    return json.loads(contenido)


def extract_decks(replay: dict[str, Any]) -> dict[int, list[int]]:
    """60-card decks per seat. `steps[1][seat]["action"]` is the deck."""
    steps = replay.get("steps") or []
    decks: dict[int, list[int]] = {}

    if len(steps) > 1 and isinstance(steps[1], list):
        for asiento, entry in enumerate(steps[1]):
            try:
                accion = entry.get("action", [])
            except AttributeError:
                continue
            if isinstance(accion, list) and len(accion) == 60 and all(isinstance(x, int) for x in accion):
                decks[asiento] = [int(x) for x in accion]
    if decks:
        return decks

    # Compatibility with old replays that expose the decks in `visualize`.
    try:
        visualize = steps[0][0].get("visualize", [])
        crudos = visualize[0].get("action", []) if visualize else []
        if isinstance(crudos, list) and len(crudos) == 2:
            for asiento, deck in enumerate(crudos):
                if isinstance(deck, list) and len(deck) == 60:
                    decks[asiento] = [int(x) for x in deck]
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        pass
    return decks


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------
class Recolector:
    """Accumulates decks per submission, including the opponents that come for free."""

    def __init__(self, objetivos: dict[int, int], recoger_extra: bool):
        # targets: submission_id -> position on the leaderboard
        self.objetivos = objetivos
        self.recoger_extra = recoger_extra
        self.decks: dict[int, dict[str, Any]] = {}   # submission_id -> {deck, position}
        self.extra: dict[int, list[int]] = {}        # submission_id -> deck (outside the top)
        self.episodios_usados: set[int] = set()

    def registrar(self, episodio: dict[str, Any], replay: dict[str, Any]) -> None:
        decks = extract_decks(replay)
        if not decks:
            return
        agentes = first(episodio, "agents", default=[]) or []
        by_seat: dict[int, dict[str, Any]] = {}
        for order, agent_state in enumerate(agentes):
            row = como_dict(agent_state)
            idx = first(row, "index", default=order)
            try:
                by_seat[int(idx)] = row
            except (TypeError, ValueError):
                by_seat[order] = row

        for asiento, deck in decks.items():
            agent_state = by_seat.get(asiento, {})
            sid = first(agent_state, "submissionId", "submission_id")
            if sid is None:
                continue
            sid = int(sid)
            if sid in self.objetivos:
                if sid not in self.decks:
                    self.decks[sid] = {"mazo": deck, "posicion": self.objetivos[sid]}
            elif self.recoger_extra and sid not in self.extra:
                self.extra[sid] = deck

    def completo(self, submission_id: int) -> bool:
        return submission_id in self.decks


def load_cache(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_cache(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)


# ---------------------------------------------------------------------------
# Writing the results
# ---------------------------------------------------------------------------
def index_row(
    file_path: str,
    deck: list[int],
    posicion: Any,
    score: Any,
    names: dict[int, str],
    ace_spec: set[int],
    pokemon: set[int],
) -> dict[str, Any]:
    """Builds a deck's index row (a single definition of the columns)."""
    conteo = Counter(deck)
    principal = ""
    if names:
        # The most repeated Pokemon. CAREFUL: it is not the archetype -- it is usually a
        # support piece at 4 copies. The `arquetipo` column is the one that classifies.
        candidatas = [(n, cid) for cid, n in conteo.items() if cid in pokemon]
        if not candidatas:
            candidatas = [(n, cid) for cid, n in conteo.items() if cid not in BASIC_ENERGIES]
        if candidatas:
            _, cid = max(candidatas, key=lambda t: (t[0], -t[1]))
            principal = names.get(cid, "")
    return {
        "archivo": file_path,
        "posicion_leaderboard": posicion,
        "puntaje": score,
        "arquetipo": classify_archetype(deck, names, pokemon),
        "cartas": len(deck),
        "ids_distintos": len(conteo),
        "energias_basicas": sum(n for cid, n in conteo.items() if cid in BASIC_ENERGIES),
        "ace_spec": sum(n for cid, n in conteo.items() if cid in ace_spec),
        "pokemon_mas_repetido": principal,
        "avisos": "; ".join(validate_deck(deck, ace_spec)),
    }


def write_index(out_dir: Path, rows: list[dict[str, Any]]) -> None:
    import csv

    columnas = list(rows[0].keys()) if rows else ["archivo"]
    with (out_dir / "indice.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        escritor = csv.DictWriter(fh, fieldnames=columnas)
        escritor.writeheader()
        escritor.writerows(rows)


def regenerar_indice(
    out_dir: Path, names: dict[int, str], ace_spec: set[int], pokemon: set[int]
) -> int:
    """Rebuilds indice.csv by reading the decks already saved, WITHOUT touching the API.

    The leaderboard moves by the hour, so downloading again would change
    the top-N and renumber decks that have already been published. This mode only recomputes the
    columns derived from the deck and keeps the position/score of the previous index.
    """
    import csv

    previo: dict[str, dict[str, str]] = {}
    previous_path = out_dir / "indice.csv"
    if previous_path.is_file():
        with previous_path.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                previo[row.get("archivo", "")] = row

    rows: list[dict[str, Any]] = []
    for path in sorted(out_dir.glob("mazo_*.csv")):
        deck = [int(x) for x in path.read_text(encoding="utf-8").split() if x.strip()]
        previous = previo.get(path.name, {})
        rows.append(
            index_row(
                path.name,
                deck,
                previous.get("posicion_leaderboard", ""),
                previous.get("puntaje", ""),
                names,
                ace_spec,
                pokemon,
            )
        )
    write_index(out_dir, rows)
    return len(rows)


def write_decks(
    recolector: Recolector,
    leaderboard_rows: list[dict[str, Any]],
    out_dir: Path,
    names: dict[int, str],
    ace_spec: set[int],
    pokemon: set[int],
) -> tuple[int, int]:
    """Writes mazo_XXX.csv in position order and returns (main, extra)."""
    import csv

    out_dir.mkdir(parents=True, exist_ok=True)
    for viejo in out_dir.glob("mazo_*.csv"):
        viejo.unlink()

    score_by_position = {f["posicion"]: f["puntaje"] for f in leaderboard_rows}
    recuperados = sorted(recolector.decks.values(), key=lambda d: d["posicion"])

    index: list[dict[str, Any]] = []
    for numero, datum in enumerate(recuperados, start=1):
        deck = datum["mazo"]
        name = f"mazo_{numero:03d}.csv"
        # The project's format: one Card ID per line, no header.
        (out_dir / name).write_text(
            "\n".join(str(cid) for cid in deck) + "\n", encoding="utf-8"
        )
        index.append(
            index_row(
                name,
                deck,
                datum["posicion"],
                score_by_position.get(datum["posicion"], ""),
                names,
                ace_spec,
                pokemon,
            )
        )

    write_index(out_dir, index)

    n_extra = 0
    if recolector.extra:
        dir_extra = out_dir / "adicionales"
        dir_extra.mkdir(parents=True, exist_ok=True)
        for viejo in dir_extra.glob("extra_*.csv"):
            viejo.unlink()
        for numero, sid in enumerate(sorted(recolector.extra), start=1):
            deck = recolector.extra[sid]
            (dir_extra / f"extra_{numero:03d}.csv").write_text(
                "\n".join(str(cid) for cid in deck) + "\n", encoding="utf-8"
            )
            n_extra += 1

    return len(recuperados), n_extra


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--top", type=int, default=100, help="leaderboard positions to analyse (default 100)")
    parser.add_argument("--output", default=str(RAIZ / "competitor_decks"), help="output folder")
    parser.add_argument("--max-episodes", type=int, default=3, help="replays to try per competitor before giving up")
    parser.add_argument("--interval", type=float, default=INTERVALO_PETICION_S, help="seconds between API requests")
    parser.add_argument("--no-extra", action="store_true", help="do not save opponent decks outside the top N")
    parser.add_argument(
        "--index-only",
        action="store_true",
        help="rebuild indice.csv from the decks already saved, without calling the API "
        "(so a reshuffled leaderboard does not renumber the saved decks)",
    )
    parser.add_argument("--keep-replays", action="store_true", help="keep the downloaded replays (~4 MB each)")
    args = parser.parse_args(argv)

    PACER.interval = float(args.interval)

    # This mode needs no credentials or SDK: it only reads what is already on disk.
    if args.index_only:
        names, ace_spec, pokemon = load_cards()
        out_dir = Path(args.output)
        if not out_dir.is_dir():
            print(f"ERROR: there is no folder {out_dir}", file=sys.stderr)
            return 1
        n = regenerar_indice(out_dir, names, ace_spec, pokemon)
        print(f"indice.csv rebuilt with {n} decks (no API calls)")
        return 0

    load_credentials()
    try:
        import kaggle
    except ImportError:
        print("ERROR: the Kaggle SDK is missing. Install it with: pip install 'kaggle==2.2.3'", file=sys.stderr)
        return 1

    api = kaggle.api
    if not hasattr(api, "competition_team_submissions"):
        print("ERROR: the installed SDK does not expose simulation submissions; use kaggle>=2.2.3", file=sys.stderr)
        return 1

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = out_dir / ".cache_replays"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = out_dir / ".decks_cache.json"

    names, ace_spec, pokemon = load_cards()
    print(f"Known cards: {len(names)} | ACE SPEC: {len(ace_spec)} | Pokemon: {len(pokemon)}")

    print(f"\n== 1/3 Leaderboard: primeras {args.top} posiciones ==")
    leaderboard_rows = obtener_leaderboard(api, kaggle, args.top)
    if not leaderboard_rows:
        print("ERROR: the leaderboard returned no rows.", file=sys.stderr)
        return 1
    print(f"Equipos: {len(leaderboard_rows)} | puntaje {leaderboard_rows[0]['puntaje']:.1f} .. {leaderboard_rows[-1]['puntaje']:.1f}")

    cache = load_cache(cache_path)
    submissions_cache: dict[str, Any] = cache.get("submissions", {})
    decks_cache: dict[str, Any] = cache.get("mazos", {})
    extra_cache: dict[str, Any] = cache.get("extra", {})

    print(f"\n== 2/3 Active submission per team ==")
    objetivos: dict[int, int] = {}   # submission_id -> position
    without_submission = 0
    for row in leaderboard_rows:
        team_id = row["team_id"]
        key = f"{team_id}:{row['puntaje']:.4f}"
        elegida = submissions_cache.get(key)
        if elegida is None:
            try:
                elegida = elegir_submission(api, team_id, row["puntaje"])
            except FalloDePeticion as exc:
                print(f"  pos {row['posicion']:>3}: no submission ({exc})")
                without_submission += 1
                continue
            submissions_cache[key] = elegida or {}
            save_cache(cache_path, {"submissions": submissions_cache, "mazos": decks_cache, "extra": extra_cache})
        if not elegida or elegida.get("submission_id") is None:
            without_submission += 1
            continue
        sid = int(elegida["submission_id"])
        row["submission_id"] = sid
        objetivos.setdefault(sid, row["posicion"])
    print(f"Submissions localizadas: {len(objetivos)} | with no public submission: {without_submission}")

    recolector = Recolector(objetivos, recoger_extra=not args.no_extra)
    # Resumption: it recovers what was already downloaded in previous runs.
    for sid_txt, deck in decks_cache.items():
        sid = int(sid_txt)
        if sid in objetivos and isinstance(deck, list) and len(deck) == 60:
            recolector.decks[sid] = {"mazo": [int(c) for c in deck], "posicion": objetivos[sid]}
    if recolector.recoger_extra:
        for sid_txt, deck in extra_cache.items():
            if isinstance(deck, list) and len(deck) == 60 and int(sid_txt) not in objetivos:
                recolector.extra[int(sid_txt)] = [int(c) for c in deck]
    if recolector.decks:
        print(f"Reanudado desde cache: {len(recolector.decks)} decks already recovered")

    print(f"\n== 3/3 Game History -> replay -> 60 cards ==")
    pendientes = [f for f in leaderboard_rows if f.get("submission_id")]
    failures: Counter[str] = Counter()

    for n, row in enumerate(pendientes, start=1):
        sid = int(row["submission_id"])
        posicion = row["posicion"]
        if recolector.completo(sid):
            continue  # another competitor's replay already gave it: zero calls

        try:
            episodios = listar_episodios(api, sid)
        except FalloDePeticion as exc:
            print(f"  pos {posicion:>3}: no history ({exc})")
            failures["episodios"] += 1
            continue
        if not episodios:
            print(f"  pos {posicion:>3}: no completed public episodes")
            failures["sin_episodios"] += 1
            continue

        for episodio in episodios[: args.max_episodes]:
            eid = int(episodio["id"])
            try:
                replay = download_replay(api, eid, cache_dir)
            except FalloDePeticion as exc:
                failures["replay"] += 1
                if exc.state == 429:
                    print(f"  pos {posicion:>3}: HTTP 429, skipped")
                    break
                continue
            except (json.JSONDecodeError, OSError):
                failures["replay_ilegible"] += 1
                continue
            recolector.registrar(episodio, replay)
            recolector.episodios_usados.add(eid)
            if not args.keep_replays:
                (cache_dir / f"episode-{eid}-replay.json").unlink(missing_ok=True)
            if recolector.completo(sid):
                break

        if recolector.completo(sid):
            print(f"  pos {posicion:>3}: deck recovered  ({len(recolector.decks)} en total, {n}/{len(pendientes)})")
        else:
            print(f"  pos {posicion:>3}: NOT recovered")
            failures["sin_mazo"] += 1

        # Persist after each competitor: an interruption does not lose work.
        decks_cache = {str(s): d["mazo"] for s, d in recolector.decks.items()}
        extra_cache = {str(s): m for s, m in recolector.extra.items()}
        save_cache(cache_path, {"submissions": submissions_cache, "mazos": decks_cache, "extra": extra_cache})

    print(f"\n== Escritura ==")
    n_principal, n_extra = write_decks(recolector, leaderboard_rows, out_dir, names, ace_spec, pokemon)
    if not args.keep_replays:
        for sobrante in cache_dir.glob("*.json"):
            sobrante.unlink(missing_ok=True)

    with_warnings = sum(1 for d in recolector.decks.values() if validate_deck(d["mazo"], ace_spec))
    print(f"Decks in the top {args.top}: {n_principal}/{len(leaderboard_rows)}  ->  {out_dir}/mazo_XXX.csv")
    if n_extra:
        print(f"Extra opponent decks (free, outside the top): {n_extra}  ->  {out_dir}/adicionales/")
    print(f"Replays descargados: {len(recolector.episodios_usados)} | API requests: {PACER.peticiones}")
    print(f"Decks with build warnings: {with_warnings}")
    if failures:
        print("Fallos:", dict(failures))
    if ERRORES:
        print("API errors:", dict(ERRORES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
