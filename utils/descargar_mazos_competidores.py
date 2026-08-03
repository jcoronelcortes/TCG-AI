"""Descarga los mazos de 60 cartas de los mejores competidores del leaderboard.

Estrategia (heredada del notebook `notebook/ptcg-ai-battle-leaderboard-deck-meta-by-score-band.ipynb`):

    leaderboard -> submission por equipo -> episodios publicos ("Game History")
    -> replay JSON -> steps[1][asiento]["action"] == las 60 cartas exactas

El replay NO hay que "adivinarlo": el paso 1 de cada partida contiene el mazo
literal de cada asiento, de modo que la lista de 60 IDs se recupera exacta y no
por inferencia estadistica sobre las cartas vistas en el log.

Cada replay trae DOS mazos (los dos asientos). Por eso:
  * si el rival de una partida tambien esta en el top-N, su mazo se registra sin
    gastar una sola llamada extra a la API;
  * los rivales fuera del top-N se guardan aparte en `adicionales/` porque salen
    gratis y sirven igual para el simulador.

Salida: un CSV por mazo con 60 lineas (un Card ID por linea, sin cabecera), que
es exactamente el formato que ya consumen `deck.csv` y `deck/rivales/*.csv`.

Uso tipico:

    python utils/descargar_mazos_competidores.py --top 100

El proceso es reanudable: los mazos ya recuperados se guardan en un cache JSON,
de modo que volver a lanzarlo solo pide a la API lo que falta.
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

# --- Politica de peticiones (misma que el notebook publicado) ---------------
INTERVALO_PETICION_S = 2.0
TAM_LOTE = 100
ENFRIAMIENTO_LOTE_S = 60.0
MAX_REINTENTOS = 6
MAX_ESPERA_REINTENTO_S = 60.0
ESTADOS_REINTENTABLES = {408, 425, 500, 502, 503, 504}

COMPETICION = "pokemon-tcg-ai-battle"
TAM_PAGINA_LEADERBOARD = 200

# Energias basicas: unicas cartas sin tope de copias.
ENERGIAS_BASICAS = set(range(1, 9))
MAX_COPIAS = 4


# ---------------------------------------------------------------------------
# Credenciales
# ---------------------------------------------------------------------------
def cargar_credenciales() -> None:
    """Expone el token de Kaggle en el entorno ANTES de importar el SDK."""
    if os.environ.get("KAGGLE_API_TOKEN") or os.environ.get("KAGGLE_KEY"):
        return
    candidatos = [
        Path.home() / ".kaggle" / "access_token",
        Path.home() / ".kaggle" / "kaggle_token.txt",
        RAIZ / "kaggle_token.txt",
        Path("kaggle_token.txt"),
    ]
    for ruta in candidatos:
        try:
            if ruta.is_file():
                token = ruta.read_text(encoding="utf-8").strip()
                if token:
                    os.environ["KAGGLE_API_TOKEN"] = token
                    print(f"Token de Kaggle leido de {ruta}")
                    return
        except OSError:
            continue
    print("Aviso: no se encontro token local; se usaran credenciales de plataforma.")


# ---------------------------------------------------------------------------
# Normalizacion de objetos del SDK
# ---------------------------------------------------------------------------
def normalizar(valor: Any) -> Any:
    if valor is None or isinstance(valor, (str, int, float, bool)):
        return valor
    if isinstance(valor, datetime):
        return valor.isoformat()
    if isinstance(valor, (list, tuple)):
        return [normalizar(v) for v in valor]
    if isinstance(valor, dict):
        return {str(k): normalizar(v) for k, v in valor.items()}
    if hasattr(valor, "to_dict"):
        return normalizar(valor.to_dict())
    if hasattr(valor, "name") and hasattr(valor, "value"):
        return valor.name
    crudo = getattr(valor, "__dict__", {})
    return {
        str(k).lstrip("_"): normalizar(v)
        for k, v in crudo.items()
        if not str(k).startswith("__")
    }


def como_dict(obj: Any) -> dict[str, Any]:
    valor = normalizar(obj)
    return valor if isinstance(valor, dict) else {}


def primero(mapa: dict[str, Any], *claves: str, defecto: Any = None) -> Any:
    for clave in claves:
        if clave in mapa and mapa[clave] is not None:
            return mapa[clave]
    return defecto


def a_float(valor: Any) -> float:
    if valor is None:
        return math.nan
    texto = str(valor).replace(",", "").strip()
    m = re.search(r"[-+]?\d+(?:\.\d+)?", texto)
    return float(m.group(0)) if m else math.nan


# ---------------------------------------------------------------------------
# Pacer + reintentos
# ---------------------------------------------------------------------------
class FalloDePeticion(RuntimeError):
    def __init__(self, etiqueta: str, estado: int | None, intentos: int):
        self.estado = estado
        self.intentos = intentos
        detalle = f"HTTP {estado}" if estado is not None else "error de red"
        super().__init__(f"{etiqueta} fallo tras {intentos} intento(s) ({detalle}).")


class Marcapasos:
    """Espacia TODAS las peticiones y enfria tras cada lote."""

    def __init__(self, intervalo: float, tam_lote: int, enfriamiento: float):
        self.intervalo = float(intervalo)
        self.tam_lote = int(tam_lote)
        self.enfriamiento = float(enfriamiento)
        self.ultimo_inicio = 0.0
        self.peticiones = 0

    def esperar(self) -> None:
        if self.peticiones and self.peticiones % self.tam_lote == 0:
            print(f"  [pausa] lote de {self.tam_lote} peticiones: {self.enfriamiento:.0f}s")
            time.sleep(self.enfriamiento)
            self.ultimo_inicio = time.monotonic()
        resto = self.intervalo - (time.monotonic() - self.ultimo_inicio)
        if resto > 0:
            time.sleep(resto)
        self.ultimo_inicio = time.monotonic()
        self.peticiones += 1


PACER = Marcapasos(INTERVALO_PETICION_S, TAM_LOTE, ENFRIAMIENTO_LOTE_S)
ERRORES: Counter[str] = Counter()


def estado_http(exc: Exception) -> int | None:
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
    valor = cabeceras.get("Retry-After") or cabeceras.get("retry-after")
    if valor is None:
        return None
    try:
        return max(0.0, float(valor))
    except (TypeError, ValueError):
        try:
            momento = parsedate_to_datetime(str(valor))
            if momento.tzinfo is None:
                momento = momento.replace(tzinfo=timezone.utc)
            return max(0.0, (momento - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


def llamar(etiqueta: str, func: Callable, *args, **kwargs):
    """Llamada a la API con marcapasos, reintentos y politica 429 = no insistir."""
    ultimo: Exception | None = None
    intentos = 0
    for intento in range(MAX_REINTENTOS):
        intentos = intento + 1
        PACER.esperar()
        try:
            return func(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - el SDK lanza tipos heterogeneos
            ultimo = exc
            estado = estado_http(exc)
            ERRORES[f"http_{estado}" if estado is not None else type(exc).__name__] += 1
            # Un 429 se salta de inmediato: insistir solo empeora el limite.
            if estado == 429:
                break
            recuperable = estado is None or estado in ESTADOS_REINTENTABLES
            if not recuperable or intento == MAX_REINTENTOS - 1:
                break
            espera = min(
                MAX_ESPERA_REINTENTO_S,
                max(reintentar_tras(exc) or 0.0, 2.0 * (2**intento)) + random.uniform(0.25, 1.25),
            )
            print(f"  [reintento] {etiqueta}: {estado or type(exc).__name__}; espero {espera:.1f}s")
            time.sleep(espera)
    raise FalloDePeticion(etiqueta, estado_http(ultimo) if ultimo else None, intentos) from ultimo


# ---------------------------------------------------------------------------
# Datos de cartas (para validar y resumir)
# ---------------------------------------------------------------------------
def cargar_cartas() -> tuple[dict[int, str], set[int], set[int]]:
    """Devuelve (nombre por Card ID, Card IDs ACE SPEC, Card IDs de Pokemon)."""
    import csv

    ruta = None
    for cand in (RAIZ / "dataset" / "EN_Card_Data.csv", RAIZ / "EN_Card_Data.csv"):
        if cand.is_file():
            ruta = cand
            break
    if ruta is None:
        print("Aviso: EN_Card_Data.csv no encontrado; se omite la validacion por nombre.")
        return {}, set(), set()

    nombres: dict[int, str] = {}
    ace_spec: set[int] = set()
    pokemon: set[int] = set()
    columna_tipo = "Stage (Pokémon)/Type (Energy and Trainer)"
    with ruta.open(encoding="utf-8-sig", newline="") as fh:
        for fila in csv.DictReader(fh):
            try:
                cid = int(str(fila["Card ID"]).strip())
            except (KeyError, TypeError, ValueError):
                continue
            nombres.setdefault(cid, str(fila.get("Card Name", "")).strip())
            if str(fila.get("Rule", "")).strip().upper() == "ACE SPEC":
                ace_spec.add(cid)
            if "pok" in str(fila.get(columna_tipo, "")).strip().lower():
                pokemon.add(cid)
    return nombres, ace_spec, pokemon


def validar_mazo(mazo: list[int], ace_spec: set[int]) -> list[str]:
    """Comprueba las reglas de construccion. Devuelve la lista de avisos."""
    avisos: list[str] = []
    if len(mazo) != 60:
        avisos.append(f"tiene {len(mazo)} cartas y no 60")
    conteo = Counter(mazo)
    for cid, n in sorted(conteo.items()):
        if cid in ENERGIAS_BASICAS:
            continue  # energia basica: sin tope
        if n > MAX_COPIAS:
            avisos.append(f"{n} copias del ID {cid} (max {MAX_COPIAS})")
    n_ace = sum(n for cid, n in conteo.items() if cid in ace_spec)
    if n_ace > 1:
        avisos.append(f"{n_ace} cartas ACE SPEC (max 1)")
    return avisos


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------
def obtener_leaderboard(api, kaggle_mod, top_n: int) -> list[dict[str, Any]]:
    """Devuelve las `top_n` primeras posiciones (equipo unico, mayor puntaje)."""
    from kaggle.api.kaggle_api_extended import ApiGetLeaderboardRequest

    filas: list[dict[str, Any]] = []
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
            filas.extend(como_dict(item) for item in (respuesta.submissions or []))
            siguiente = str(respuesta.next_page_token or "")
            # Con paginas de 200 basta la primera para un top-100, pero se sigue
            # paginando por si el endpoint devuelve paginas mas cortas.
            if len(filas) >= top_n * 2 or not siguiente or siguiente in vistos:
                break
            vistos.add(siguiente)
            token = siguiente

    normalizadas = []
    for fila in filas:
        team_id = primero(fila, "teamId", "team_id")
        puntaje = a_float(primero(fila, "score", "publicScore", "public_score"))
        if team_id is None or math.isnan(puntaje):
            continue
        normalizadas.append(
            {
                "team_id": int(team_id),
                "puntaje": puntaje,
                "fecha": primero(fila, "submissionDate", "submission_date"),
            }
        )

    # Un equipo solo puede ocupar una posicion: nos quedamos con su mejor puntaje.
    mejor_por_equipo: dict[int, dict[str, Any]] = {}
    for fila in normalizadas:
        actual = mejor_por_equipo.get(fila["team_id"])
        if actual is None or fila["puntaje"] > actual["puntaje"]:
            mejor_por_equipo[fila["team_id"]] = fila

    ordenadas = sorted(
        mejor_por_equipo.values(), key=lambda f: (-f["puntaje"], f["team_id"])
    )[:top_n]
    for posicion, fila in enumerate(ordenadas, start=1):
        fila["posicion"] = posicion
    return ordenadas


def elegir_submission(api, team_id: int, puntaje_lb: float) -> dict[str, Any] | None:
    """La submission publica cuyo puntaje mas se acerca al del leaderboard."""
    submissions = llamar("submissions del equipo", api.competition_team_submissions, int(team_id)) or []
    candidatas: list[dict[str, Any]] = []
    for item in submissions:
        fila = como_dict(item)
        sid = primero(fila, "id", "ref", "submissionId", "submission_id")
        if sid is None:
            continue
        candidatas.append(
            {
                "submission_id": int(sid),
                "puntaje": a_float(primero(fila, "publicScore", "public_score", "score")),
            }
        )
    if not candidatas:
        return None

    def orden(fila: dict[str, Any]):
        p = fila["puntaje"]
        distancia = abs(p - puntaje_lb) if not math.isnan(p) else math.inf
        return (distancia, -p if not math.isnan(p) else math.inf, -fila["submission_id"])

    return min(candidatas, key=orden)


# ---------------------------------------------------------------------------
# Episodios ("Game History") y replays
# ---------------------------------------------------------------------------
def listar_episodios(api, submission_id: int) -> list[dict[str, Any]]:
    """Episodios publicos completados de una submission, del mas reciente atras."""
    episodios = llamar("episodios de la submission", api.competition_list_episodes, int(submission_id)) or []
    salida: list[dict[str, Any]] = []
    for item in episodios:
        fila = como_dict(item)
        eid = primero(fila, "id", "episodeId", "episode_id")
        if eid is None:
            continue
        tipo = str(primero(fila, "type", defecto="PUBLIC"))
        estado = str(primero(fila, "state", defecto="COMPLETED"))
        if "PUBLIC" not in tipo.upper():
            continue
        if not re.search(r"COMPLETE", estado, flags=re.IGNORECASE):
            continue
        fila["id"] = int(eid)
        salida.append(fila)
    return sorted(salida, key=lambda f: int(f["id"]), reverse=True)


def descargar_replay(api, episode_id: int, dir_cache: Path) -> dict[str, Any]:
    """Descarga (o reutiliza) el replay JSON de un episodio."""
    from kaggle.api.kaggle_api_extended import ApiGetEpisodeReplayRequest

    destino = dir_cache / f"episode-{episode_id}-replay.json"
    if destino.exists() and destino.stat().st_size > 1000:
        try:
            return json.loads(destino.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            destino.unlink(missing_ok=True)

    def una_vez() -> bytes:
        peticion = ApiGetEpisodeReplayRequest()
        peticion.episode_id = int(episode_id)
        with api.build_kaggle_client() as cliente:
            respuesta = cliente.competitions.competition_api_client.get_episode_replay(peticion)
            respuesta.raise_for_status()
            return respuesta.content

    contenido = llamar("replay del episodio", una_vez)
    destino.write_bytes(contenido)
    return json.loads(contenido)


def extraer_mazos(replay: dict[str, Any]) -> dict[int, list[int]]:
    """Mazos de 60 cartas por asiento. `steps[1][asiento]["action"]` es el mazo."""
    pasos = replay.get("steps") or []
    mazos: dict[int, list[int]] = {}

    if len(pasos) > 1 and isinstance(pasos[1], list):
        for asiento, entrada in enumerate(pasos[1]):
            try:
                accion = entrada.get("action", [])
            except AttributeError:
                continue
            if isinstance(accion, list) and len(accion) == 60 and all(isinstance(x, int) for x in accion):
                mazos[asiento] = [int(x) for x in accion]
    if mazos:
        return mazos

    # Compatibilidad con replays antiguos que exponen los mazos en `visualize`.
    try:
        visualize = pasos[0][0].get("visualize", [])
        crudos = visualize[0].get("action", []) if visualize else []
        if isinstance(crudos, list) and len(crudos) == 2:
            for asiento, mazo in enumerate(crudos):
                if isinstance(mazo, list) and len(mazo) == 60:
                    mazos[asiento] = [int(x) for x in mazo]
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        pass
    return mazos


# ---------------------------------------------------------------------------
# Recoleccion
# ---------------------------------------------------------------------------
class Recolector:
    """Acumula mazos por submission, incluidos los rivales que salen gratis."""

    def __init__(self, objetivos: dict[int, int], recoger_extra: bool):
        # objetivos: submission_id -> posicion en el leaderboard
        self.objetivos = objetivos
        self.recoger_extra = recoger_extra
        self.mazos: dict[int, dict[str, Any]] = {}   # submission_id -> {mazo, posicion}
        self.extra: dict[int, list[int]] = {}        # submission_id -> mazo (fuera del top)
        self.episodios_usados: set[int] = set()

    def registrar(self, episodio: dict[str, Any], replay: dict[str, Any]) -> None:
        mazos = extraer_mazos(replay)
        if not mazos:
            return
        agentes = primero(episodio, "agents", defecto=[]) or []
        por_asiento: dict[int, dict[str, Any]] = {}
        for orden, agente in enumerate(agentes):
            fila = como_dict(agente)
            idx = primero(fila, "index", defecto=orden)
            try:
                por_asiento[int(idx)] = fila
            except (TypeError, ValueError):
                por_asiento[orden] = fila

        for asiento, mazo in mazos.items():
            agente = por_asiento.get(asiento, {})
            sid = primero(agente, "submissionId", "submission_id")
            if sid is None:
                continue
            sid = int(sid)
            if sid in self.objetivos:
                if sid not in self.mazos:
                    self.mazos[sid] = {"mazo": mazo, "posicion": self.objetivos[sid]}
            elif self.recoger_extra and sid not in self.extra:
                self.extra[sid] = mazo

    def completo(self, submission_id: int) -> bool:
        return submission_id in self.mazos


def cargar_cache(ruta: Path) -> dict[str, Any]:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        return datos if isinstance(datos, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def guardar_cache(ruta: Path, datos: dict[str, Any]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(".tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(ruta)


# ---------------------------------------------------------------------------
# Escritura de resultados
# ---------------------------------------------------------------------------
def escribir_mazos(
    recolector: Recolector,
    filas_lb: list[dict[str, Any]],
    dir_salida: Path,
    nombres: dict[int, str],
    ace_spec: set[int],
    pokemon: set[int],
) -> tuple[int, int]:
    """Escribe mazo_XXX.csv en orden de posicion y devuelve (principales, extra)."""
    import csv

    dir_salida.mkdir(parents=True, exist_ok=True)
    for viejo in dir_salida.glob("mazo_*.csv"):
        viejo.unlink()

    puntaje_por_posicion = {f["posicion"]: f["puntaje"] for f in filas_lb}
    recuperados = sorted(recolector.mazos.values(), key=lambda d: d["posicion"])

    indice: list[dict[str, Any]] = []
    for numero, dato in enumerate(recuperados, start=1):
        mazo = dato["mazo"]
        nombre = f"mazo_{numero:03d}.csv"
        # Formato del proyecto: un Card ID por linea, sin cabecera.
        (dir_salida / nombre).write_text(
            "\n".join(str(cid) for cid in mazo) + "\n", encoding="utf-8"
        )
        avisos = validar_mazo(mazo, ace_spec)
        conteo = Counter(mazo)
        principal = ""
        if nombres:
            # Pokemon mas repetido: etiqueta util para ojear el arquetipo de un
            # vistazo. Si el mazo no trae Pokemon reconocibles, cae a cualquier
            # carta que no sea energia basica.
            candidatas = [(n, cid) for cid, n in conteo.items() if cid in pokemon]
            if not candidatas:
                candidatas = [(n, cid) for cid, n in conteo.items() if cid not in ENERGIAS_BASICAS]
            if candidatas:
                _, cid = max(candidatas, key=lambda t: (t[0], -t[1]))
                principal = nombres.get(cid, "")
        indice.append(
            {
                "archivo": nombre,
                "posicion_leaderboard": dato["posicion"],
                "puntaje": puntaje_por_posicion.get(dato["posicion"], ""),
                "cartas": len(mazo),
                "ids_distintos": len(conteo),
                "energias_basicas": sum(n for cid, n in conteo.items() if cid in ENERGIAS_BASICAS),
                "ace_spec": sum(n for cid, n in conteo.items() if cid in ace_spec),
                "carta_mas_repetida": principal,
                "avisos": "; ".join(avisos),
            }
        )

    with (dir_salida / "indice.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        escritor = csv.DictWriter(fh, fieldnames=list(indice[0].keys()) if indice else ["archivo"])
        escritor.writeheader()
        escritor.writerows(indice)

    n_extra = 0
    if recolector.extra:
        dir_extra = dir_salida / "adicionales"
        dir_extra.mkdir(parents=True, exist_ok=True)
        for viejo in dir_extra.glob("extra_*.csv"):
            viejo.unlink()
        for numero, sid in enumerate(sorted(recolector.extra), start=1):
            mazo = recolector.extra[sid]
            (dir_extra / f"extra_{numero:03d}.csv").write_text(
                "\n".join(str(cid) for cid in mazo) + "\n", encoding="utf-8"
            )
            n_extra += 1

    return len(recuperados), n_extra


# ---------------------------------------------------------------------------
# Principal
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--top", type=int, default=100, help="posiciones del leaderboard a analizar (por defecto 100)")
    parser.add_argument("--salida", default=str(RAIZ / "decks_competidores"), help="carpeta de salida")
    parser.add_argument("--max-episodios", type=int, default=3, help="replays a probar por competidor antes de rendirse")
    parser.add_argument("--intervalo", type=float, default=INTERVALO_PETICION_S, help="segundos entre peticiones a la API")
    parser.add_argument("--sin-extra", action="store_true", help="no guardar los mazos rivales fuera del top-N")
    parser.add_argument("--conservar-replays", action="store_true", help="no borrar los replays descargados (~4 MB cada uno)")
    args = parser.parse_args(argv)

    PACER.intervalo = float(args.intervalo)

    cargar_credenciales()
    try:
        import kaggle
    except ImportError:
        print("ERROR: falta el SDK de Kaggle. Instala con: pip install 'kaggle==2.2.3'", file=sys.stderr)
        return 1

    api = kaggle.api
    if not hasattr(api, "competition_team_submissions"):
        print("ERROR: el SDK instalado no expone las submissions de simulacion; usa kaggle>=2.2.3", file=sys.stderr)
        return 1

    dir_salida = Path(args.salida)
    dir_salida.mkdir(parents=True, exist_ok=True)
    dir_cache = dir_salida / ".cache_replays"
    dir_cache.mkdir(parents=True, exist_ok=True)
    ruta_cache = dir_salida / ".mazos_cache.json"

    nombres, ace_spec, pokemon = cargar_cartas()
    print(f"Cartas conocidas: {len(nombres)} | ACE SPEC: {len(ace_spec)} | Pokemon: {len(pokemon)}")

    print(f"\n== 1/3 Leaderboard: primeras {args.top} posiciones ==")
    filas_lb = obtener_leaderboard(api, kaggle, args.top)
    if not filas_lb:
        print("ERROR: el leaderboard no devolvio filas.", file=sys.stderr)
        return 1
    print(f"Equipos: {len(filas_lb)} | puntaje {filas_lb[0]['puntaje']:.1f} .. {filas_lb[-1]['puntaje']:.1f}")

    cache = cargar_cache(ruta_cache)
    submissions_cache: dict[str, Any] = cache.get("submissions", {})
    mazos_cache: dict[str, Any] = cache.get("mazos", {})
    extra_cache: dict[str, Any] = cache.get("extra", {})

    print(f"\n== 2/3 Submission activa por equipo ==")
    objetivos: dict[int, int] = {}   # submission_id -> posicion
    sin_submission = 0
    for fila in filas_lb:
        team_id = fila["team_id"]
        clave = f"{team_id}:{fila['puntaje']:.4f}"
        elegida = submissions_cache.get(clave)
        if elegida is None:
            try:
                elegida = elegir_submission(api, team_id, fila["puntaje"])
            except FalloDePeticion as exc:
                print(f"  pos {fila['posicion']:>3}: sin submission ({exc})")
                sin_submission += 1
                continue
            submissions_cache[clave] = elegida or {}
            guardar_cache(ruta_cache, {"submissions": submissions_cache, "mazos": mazos_cache, "extra": extra_cache})
        if not elegida or elegida.get("submission_id") is None:
            sin_submission += 1
            continue
        sid = int(elegida["submission_id"])
        fila["submission_id"] = sid
        objetivos.setdefault(sid, fila["posicion"])
    print(f"Submissions localizadas: {len(objetivos)} | sin submission publica: {sin_submission}")

    recolector = Recolector(objetivos, recoger_extra=not args.sin_extra)
    # Reanudacion: recupera lo ya descargado en ejecuciones previas.
    for sid_txt, mazo in mazos_cache.items():
        sid = int(sid_txt)
        if sid in objetivos and isinstance(mazo, list) and len(mazo) == 60:
            recolector.mazos[sid] = {"mazo": [int(c) for c in mazo], "posicion": objetivos[sid]}
    if recolector.recoger_extra:
        for sid_txt, mazo in extra_cache.items():
            if isinstance(mazo, list) and len(mazo) == 60 and int(sid_txt) not in objetivos:
                recolector.extra[int(sid_txt)] = [int(c) for c in mazo]
    if recolector.mazos:
        print(f"Reanudado desde cache: {len(recolector.mazos)} mazos ya recuperados")

    print(f"\n== 3/3 Game History -> replay -> 60 cartas ==")
    pendientes = [f for f in filas_lb if f.get("submission_id")]
    fallos: Counter[str] = Counter()

    for n, fila in enumerate(pendientes, start=1):
        sid = int(fila["submission_id"])
        posicion = fila["posicion"]
        if recolector.completo(sid):
            continue  # ya lo dio el replay de otro competidor: cero llamadas

        try:
            episodios = listar_episodios(api, sid)
        except FalloDePeticion as exc:
            print(f"  pos {posicion:>3}: sin historial ({exc})")
            fallos["episodios"] += 1
            continue
        if not episodios:
            print(f"  pos {posicion:>3}: sin episodios publicos completados")
            fallos["sin_episodios"] += 1
            continue

        for episodio in episodios[: args.max_episodios]:
            eid = int(episodio["id"])
            try:
                replay = descargar_replay(api, eid, dir_cache)
            except FalloDePeticion as exc:
                fallos["replay"] += 1
                if exc.estado == 429:
                    print(f"  pos {posicion:>3}: HTTP 429, se salta")
                    break
                continue
            except (json.JSONDecodeError, OSError):
                fallos["replay_ilegible"] += 1
                continue
            recolector.registrar(episodio, replay)
            recolector.episodios_usados.add(eid)
            if not args.conservar_replays:
                (dir_cache / f"episode-{eid}-replay.json").unlink(missing_ok=True)
            if recolector.completo(sid):
                break

        if recolector.completo(sid):
            print(f"  pos {posicion:>3}: mazo recuperado  ({len(recolector.mazos)} en total, {n}/{len(pendientes)})")
        else:
            print(f"  pos {posicion:>3}: NO recuperado")
            fallos["sin_mazo"] += 1

        # Persistir tras cada competidor: una interrupcion no pierde trabajo.
        mazos_cache = {str(s): d["mazo"] for s, d in recolector.mazos.items()}
        extra_cache = {str(s): m for s, m in recolector.extra.items()}
        guardar_cache(ruta_cache, {"submissions": submissions_cache, "mazos": mazos_cache, "extra": extra_cache})

    print(f"\n== Escritura ==")
    n_principal, n_extra = escribir_mazos(recolector, filas_lb, dir_salida, nombres, ace_spec, pokemon)
    if not args.conservar_replays:
        for sobrante in dir_cache.glob("*.json"):
            sobrante.unlink(missing_ok=True)

    con_avisos = sum(1 for d in recolector.mazos.values() if validar_mazo(d["mazo"], ace_spec))
    print(f"Mazos del top-{args.top}: {n_principal}/{len(filas_lb)}  ->  {dir_salida}/mazo_XXX.csv")
    if n_extra:
        print(f"Mazos rivales extra (gratis, fuera del top): {n_extra}  ->  {dir_salida}/adicionales/")
    print(f"Replays descargados: {len(recolector.episodios_usados)} | peticiones a la API: {PACER.peticiones}")
    print(f"Mazos con avisos de construccion: {con_avisos}")
    if fallos:
        print("Fallos:", dict(fallos))
    if ERRORES:
        print("Errores de API:", dict(ERRORES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
