"""Downloads every public replay of a single leaderboard player.

Where `download_competitor_decks.py` sweeps the top-N to harvest 60-card decks,
this tool goes the other way: it takes ONE player and saves the full log of every
game they have played, so their games can be read turn by turn.

    leaderboard (search by team name) -> every submission of that team
    -> public episodes ("Game History") of each submission -> replay JSON

The two submissions of a team are NOT the same agent: each one plays its own
episodes, so both are swept and the episodes deduplicated by id (an episode can
appear twice if a team ends up playing against itself).

Output, under `<out-dir>/<player>/`:
  * `episode-<id>-replay.json`  the raw replay, exactly as the API returns it
  * `index.csv`                 one row per game: date, seat, opponent, result

The process is resumable: a replay already on disk is not asked for again.

Typical usage:

    python utils/download_player_games.py --player ANDPAD
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "utils"))

from download_competitor_decks import (  # noqa: E402
    COMPETITION,
    LEADERBOARD_PAGE_SIZE,
    ERRORES,
    RequestFailure,
    a_float,
    como_dict,
    download_replay,
    first,
    listar_episodios,
    llamar,
    load_credentials,
)


def buscar_equipo(api, patron: str) -> list[dict[str, Any]]:
    """Every leaderboard team whose name contains `patron` (case-insensitive)."""
    from kaggle.api.kaggle_api_extended import ApiGetLeaderboardRequest

    aguja = patron.strip().casefold()
    encontrados: dict[int, dict[str, Any]] = {}
    token: str | None = None
    vistos: set[str] = set()

    with api.build_kaggle_client() as cliente:
        while True:
            request = ApiGetLeaderboardRequest()
            request.competition_name = COMPETITION
            request.page_size = LEADERBOARD_PAGE_SIZE
            if token:
                request.page_token = token
            respuesta = llamar(
                "pagina de leaderboard",
                cliente.competitions.competition_api_client.get_leaderboard,
                request,
            )
            for item in respuesta.submissions or []:
                row = como_dict(item)
                nombre = str(first(row, "teamName", "team_name", default=""))
                team_id = first(row, "teamId", "team_id")
                if team_id is None or aguja not in nombre.casefold():
                    continue
                puntaje = a_float(first(row, "score", "publicScore", "public_score"))
                actual = encontrados.get(int(team_id))
                # A team can appear on several rows: we keep their best score.
                if actual is None or (not math.isnan(puntaje) and puntaje > actual["puntaje"]):
                    encontrados[int(team_id)] = {
                        "team_id": int(team_id),
                        "team_name": nombre,
                        "puntaje": puntaje,
                        "fecha": first(row, "submissionDate", "submission_date"),
                    }
            siguiente = str(respuesta.next_page_token or "")
            if not siguiente or siguiente in vistos:
                break
            vistos.add(siguiente)
            token = siguiente

    return sorted(encontrados.values(), key=lambda f: -f["puntaje"])


def listar_submissions(api, team_id: int) -> list[dict[str, Any]]:
    """Every submission of the team, best score first."""
    crudas = llamar("submissions del equipo", api.competition_team_submissions, int(team_id)) or []
    salida: list[dict[str, Any]] = []
    for item in crudas:
        row = como_dict(item)
        sid = first(row, "id", "ref", "submissionId", "submission_id")
        if sid is None:
            continue
        salida.append(
            {
                "submission_id": int(sid),
                "puntaje": a_float(first(row, "publicScore", "public_score", "score")),
            }
        )
    return sorted(salida, key=lambda f: (-(f["puntaje"] if not math.isnan(f["puntaje"]) else -math.inf)))


def fila_indice(episodio: dict[str, Any], team_id: int) -> dict[str, Any]:
    """Reads the episode's metadata from OUR seat's point of view."""
    agentes = episodio.get("agents") or []
    nuestro: dict[str, Any] = {}
    rival: dict[str, Any] = {}
    for posicion, crudo in enumerate(agentes):
        agente = como_dict(crudo)
        # `index` is absent on seat 0: its position in the list is the seat.
        agente["_asiento"] = int(first(agente, "index", default=posicion) or 0)
        if int(first(agente, "teamId", "team_id", default=-1) or -1) == team_id and not nuestro:
            nuestro = agente
        else:
            rival = agente

    premio = first(nuestro, "reward")
    if premio is None:
        resultado = ""
    elif a_float(premio) > 0:
        resultado = "victoria"
    elif a_float(premio) < 0:
        resultado = "derrota"
    else:
        resultado = "empate"

    return {
        "episode_id": episodio["id"],
        "fecha": first(episodio, "endTime", "createTime", default=""),
        "submission_id": first(nuestro, "submissionId", "submission_id", default=""),
        "asiento": nuestro.get("_asiento", ""),
        "resultado": resultado,
        "rival": first(rival, "teamName", "team_name", default=""),
        "rival_team_id": first(rival, "teamId", "team_id", default=""),
        "rival_submission_id": first(rival, "submissionId", "submission_id", default=""),
    }


CAMPOS_INDICE = [
    "episode_id",
    "fecha",
    "submission_id",
    "asiento",
    "resultado",
    "rival",
    "rival_team_id",
    "rival_submission_id",
]


def escribir_indice(destino: Path, filas: list[dict[str, Any]]) -> None:
    with (destino / "index.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CAMPOS_INDICE)
        writer.writeheader()
        for fila in sorted(filas, key=lambda f: str(f["fecha"]), reverse=True):
            writer.writerow(fila)


def nombre_carpeta(texto: str) -> str:
    """A folder name that survives any filesystem."""
    limpio = re.sub(r"[^\w.\- ]+", "_", texto, flags=re.UNICODE).strip(" .")
    return re.sub(r"\s+", " ", limpio) or "jugador"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--player", required=True, help="Part of the team name, as on the leaderboard.")
    parser.add_argument("--out-dir", default=str(RAIZ), help="Where the player's folder is created.")
    parser.add_argument("--folder", default=None, help="Folder name (default: the --player value).")
    parser.add_argument(
        "--submission-id",
        type=int,
        default=None,
        help="Sweep ONLY this submission instead of every submission of the team.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Cap on replays to download (0 = no cap).")
    parser.add_argument("--dry-run", action="store_true", help="List the episodes without downloading them.")
    args = parser.parse_args(argv)

    load_credentials()
    try:
        import kaggle
    except ImportError:
        print("ERROR: falta el SDK de Kaggle. Instalalo con: pip install 'kaggle==2.2.3'", file=sys.stderr)
        return 2

    api = kaggle.api
    if not hasattr(api, "competition_team_submissions"):
        print("ERROR: el SDK instalado no expone submissions de simulacion; usa kaggle>=2.2.3", file=sys.stderr)
        return 2

    equipos = buscar_equipo(api, args.player)
    if not equipos:
        print(f"No hay ningun equipo cuyo nombre contenga '{args.player}'.", file=sys.stderr)
        return 1
    if len(equipos) > 1:
        print(f"Aviso: '{args.player}' coincide con {len(equipos)} equipos; me quedo con el de mas puntaje:")
        for eq in equipos:
            print(f"  - {eq['team_name']} (team {eq['team_id']}, {eq['puntaje']:.1f})")
    equipo = equipos[0]
    print(f"Jugador: {equipo['team_name']} (team {equipo['team_id']}, puntaje {equipo['puntaje']:.1f})")

    submissions = listar_submissions(api, equipo["team_id"])
    if args.submission_id is not None:
        submissions = [s for s in submissions if s["submission_id"] == args.submission_id] or [
            {"submission_id": args.submission_id, "puntaje": math.nan}
        ]
    if not submissions:
        print("El equipo no tiene submissions visibles.", file=sys.stderr)
        return 1
    print(f"Submissions: {', '.join(str(s['submission_id']) for s in submissions)}")

    # An episode can belong to two submissions of the same team (mirror match):
    # deduplicating by id keeps one file per game, not one per seat.
    episodios: dict[int, dict[str, Any]] = {}
    for sub in submissions:
        try:
            lista = listar_episodios(api, sub["submission_id"])
        except RequestFailure as exc:
            print(f"  submission {sub['submission_id']}: {exc}", file=sys.stderr)
            continue
        nuevos = [ep for ep in lista if int(ep["id"]) not in episodios]
        for ep in lista:
            episodios.setdefault(int(ep["id"]), ep)
        print(f"  submission {sub['submission_id']}: {len(lista)} episodios ({len(nuevos)} nuevos)")

    orden = sorted(episodios.values(), key=lambda e: int(e["id"]), reverse=True)
    if args.limit > 0:
        orden = orden[: args.limit]
    print(f"Total de partidas a guardar: {len(orden)}")

    destino = Path(args.out_dir) / nombre_carpeta(args.folder or args.player)
    filas = [fila_indice(ep, equipo["team_id"]) for ep in orden]

    if args.dry_run:
        for fila in filas[:10]:
            print(f"  {fila['episode_id']}  {fila['fecha']}  {fila['resultado']:8}  vs {fila['rival']}")
        if len(filas) > 10:
            print(f"  ... y {len(filas) - 10} mas")
        return 0

    destino.mkdir(parents=True, exist_ok=True)
    guardados = 0
    fallos = 0
    for numero, episodio in enumerate(orden, start=1):
        eid = int(episodio["id"])
        ruta = destino / f"episode-{eid}-replay.json"
        ya_estaba = ruta.exists() and ruta.stat().st_size > 1000
        try:
            download_replay(api, eid, destino)
        except (RequestFailure, json.JSONDecodeError, OSError) as exc:
            fallos += 1
            print(f"  [{numero}/{len(orden)}] episodio {eid}: FALLO ({exc})", file=sys.stderr)
            continue
        guardados += 1
        marca = "cache" if ya_estaba else "bajado"
        print(f"  [{numero}/{len(orden)}] episodio {eid}: {marca} ({ruta.stat().st_size // 1024} KiB)")

    # The index only covers the replays that really are on disk.
    presentes = {int(m.group(1)) for p in destino.glob("episode-*-replay.json") if (m := re.search(r"episode-(\d+)-", p.name))}
    escribir_indice(destino, [f for f in filas if int(f["episode_id"]) in presentes])

    print(f"\nGuardadas {guardados} partidas en {destino}" + (f" ({fallos} fallos)" if fallos else ""))
    if ERRORES:
        print("Errores de red por tipo:", dict(ERRORES))
    return 0 if fallos == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
