"""Lineas evolutivas: etapa, raiz, cadenas del mazo y eslabones que faltan.

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/main-refactor-arquitectura.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

from cg.api import CardType
from collections import defaultdict
from ptcg.cartas.grupos import EVO_LINES
from ptcg.cartas.ids import DUNSPARCE_IDS, _ID_NAME_EXPECTATIONS
from ptcg.cartas.tablas import _CARD_BY_NAME, _EVOLUCIONES_POR_NOMBRE, card_table


def _validate_id_constants():
    mismatches = []
    for _cid, _expected in _ID_NAME_EXPECTATIONS.items():
        if _cid < 0:
            continue
        _cd = card_table.get(_cid)
        _name = getattr(_cd, 'name', None) if _cd is not None else None
        if _name is None or _expected.lower() not in _name.lower():
            mismatches.append((_cid, _expected, _name))
    if mismatches:
        import sys as _sys
        for _cid, _expected, _name in mismatches:
            print(f"[WARN][ID-AUDIT] id={_cid} esperaba '{_expected}' "
                  f"pero card_table dice '{_name}'", file=_sys.stderr)
    return mismatches


def _etapa_evolutiva(card_id):
    """Etapa de `card_id`: 0 Basico, 1 Fase 1, 2 Fase 2. None si no es Pokemon.

    Sale del dato de carta (`basic`/`stage1`/`stage2`), no de `EVO_LINES`, que
    describe unicamente NUESTRO mazo.
    """
    data = card_table.get(card_id)
    if data is None or data.cardType != CardType.POKEMON:
        return None
    if getattr(data, 'stage2', False):
        return 2
    if getattr(data, 'stage1', False):
        return 1
    return 0 if getattr(data, 'basic', False) else None


def _raiz_de_linea(card_id):
    """Nombre del BASICO de la cadena evolutiva de `card_id` (None si se ignora).

    Sube por `evolvesFrom` hasta que no haya pre-evolucion. Si un eslabon
    intermedio no esta en `card_table` se devuelve el ultimo nombre conocido:
    basta para comparar dos cartas de la MISMA cadena.
    """
    data = card_table.get(card_id)
    if data is None or data.cardType != CardType.POKEMON:
        return None
    nombre = data.name or None
    vistos = set()
    while data is not None and getattr(data, 'evolvesFrom', None):
        pre = data.evolvesFrom
        if pre in vistos:                # cadena corrupta: corta el bucle
            break
        vistos.add(pre)
        nombre = pre
        data = _CARD_BY_NAME.get(pre)
    return nombre


def _misma_linea_evolutiva(a_id, b_id):
    """True si los dos ids son eslabones de la MISMA cadena Basico->F1->F2."""
    if a_id == b_id:
        return True
    raiz = _raiz_de_linea(a_id)
    return raiz is not None and raiz == _raiz_de_linea(b_id)


def _supera_en_evolucion(pkmn, otro):
    """True si `pkmn` es un eslabon MAS EVOLUCIONADO de la MISMA linea que `otro`.

    Regla del user (registro_008 paso 93 vs Cynthia's Garchomp ex, GANADA con
    error): dentro de una linea Basico -> Fase 1 -> Fase 2, noquear SIEMPRE la
    etapa MAS ALTA que se pueda. Cobra el mismo premio pero destruye mas
    desarrollo: el rival necesita rehacer los dos escalones antes de volver a
    tener su Fase 2 atacante. Ver [[boss-gust-mayor-evolucion-fase2]].
    """
    if pkmn is None or otro is None:
        return False
    e_pkmn = _etapa_evolutiva(getattr(pkmn, 'id', 0))
    e_otro = _etapa_evolutiva(getattr(otro, 'id', 0))
    if e_pkmn is None or e_otro is None or e_pkmn <= e_otro:
        return False
    return _misma_linea_evolutiva(getattr(pkmn, 'id', 0), getattr(otro, 'id', 0))


def _linea_culmina_en_ex(card_id):
    """True si por ENCIMA de `card_id` su cadena llega a un Pokemon ex/megaEx.

    Deck-agnostico: baja por `evolvesFrom` (nombres, no ids) desde la carta, asi
    que vale para CUALQUIER linea Basico -> Fase 1 -> Fase 2 del entorno sin
    inscribirla a mano en `EX_PREEVO_IDS`. Es el criterio que justifica gastar
    un Boss's en cortar la linea: la etapa final rinde 2+ premios y es el
    atacante real del mazo rival.

    Deja fuera sola la linea Abra -> Kadabra -> Alakazam (su forma final vale 1
    premio en este entorno), que es justo lo que pide
    [[boss-no-gustear-preevo-linea-no-ex]].
    """
    data = card_table.get(card_id)
    if data is None or data.cardType != CardType.POKEMON:
        return False
    pendientes = [data.name or ""]
    vistos = set()
    while pendientes:
        nombre = pendientes.pop()
        if not nombre or nombre in vistos:
            continue
        vistos.add(nombre)
        for evo in _EVOLUCIONES_POR_NOMBRE.get(nombre, ()):
            if getattr(evo, 'ex', False) or getattr(evo, 'megaEx', False):
                return True
            pendientes.append(evo.name or "")
    return False


def _preevo_de_linea_ex(card_id):
    """¿`card_id` es un eslabon que vale GUSTEAR para cortar una linea ex?

    Sustituye a la lista curada `EX_PREEVO_IDS` (menos `NONEX_FINAL_PREEVO_IDS`)
    alli donde el criterio es "la linea acaba en un atacante de 2 premios": lo
    deriva del dato de carta, asi que cubre lineas que nadie inscribio a mano
    (p.ej. Frillish -> Jellicent ex).

    Guarda `DUNSPARCE_IDS`: su linea culmina en Dudunsparce ex, pero el
    manejador de seleccion los veta SIEMPRE como objetivo de gusteo. Un motivo
    que apunta a un objetivo prohibido hace jugar (o buscar) el Boss's para
    acabar subiendo otra cosa -- es el mismo fallo que el Dwebble del log
    86339758.
    """
    if card_id in DUNSPARCE_IDS:
        return False
    return _linea_culmina_en_ex(card_id)


def _construir_cadenas_de_mazo(deck_ids):
    """Deriva del mazo las cadenas evolutivas completas.

    Devuelve `(evo_por_nombre, cadenas)`:
      evo_por_nombre: nombre de la pre-evolucion -> tupla de ids DEL MAZO que
                      evolucionan de ella.
      cadenas:        tupla de `(basico_id, fase1_id, fase2_id_o_0)`. Una misma
                      pre-evolucion puede tener varias evoluciones (copias de
                      distinta expansion), asi que se emite una cadena por
                      combinacion; el consumidor elige.

    Grand Tree busca en NUESTRA baraja, de ahi que solo se consideren ids
    presentes en `deck_ids`.
    """
    ids = set(deck_ids)
    por_nombre = defaultdict(set)
    for cid in ids:
        data = card_table.get(cid)
        if data is None or data.cardType != CardType.POKEMON:
            continue
        pre = getattr(data, 'evolvesFrom', None)
        if pre:
            por_nombre[pre].add(cid)
    evo_por_nombre = {nombre: tuple(sorted(v)) for nombre, v in por_nombre.items()}

    cadenas = []
    for cid in sorted(ids):
        data = card_table.get(cid)
        if data is None or data.cardType != CardType.POKEMON or not data.basic:
            continue
        for s1 in evo_por_nombre.get(data.name, ()):
            s1_data = card_table.get(s1)
            if s1_data is None:
                continue
            s2s = evo_por_nombre.get(s1_data.name, ())
            if s2s:
                for s2 in s2s:
                    cadenas.append((cid, s1, s2))
            else:
                cadenas.append((cid, s1, 0))
    return evo_por_nombre, tuple(cadenas)


def _evo_link_state(hand_counts, field_counts):
    """Clasifica cada EVOLUCION de nuestras lineas para el fetch de la Ultra
    Ball. Devuelve `(necesarios, huerfanos)`:

      huerfano  = su PRE-EVOLUCION no esta ni en juego ni en la mano: traerla es
                  una carta MUERTA, no se puede jugar (user, registro_006 paso
                  79 vs Marnie, PERDIDA: con un Applin en banca y NINGUN Dipplin
                  en juego ni en mano, la Ultra Ball buscaba Hydrapple ex -- que
                  no puede evolucionar nada -- en vez del Dipplin que faltaba).
      necesario = eslabon INTERMEDIO que falta (su pre-evolucion esta en juego,
                  no lo tenemos en mano ni en juego) Y que ademas DESBLOQUEA la
                  etapa 2, que ahora mismo es huerfana. Es "la siguiente
                  evolucion que se necesita en la banca".

    La etapa 2 nunca entra en `necesarios`: cuando ES el eslabon que falta ya la
    puntuan sus propias ramas (Hydrapple ex 980 / Meganium 1000), que ademas
    aplican los clamps de matchup (ex muerto vs Crustle, cesion al motor de
    refresco de Meowth ex). Subirla aqui pisaria esos clamps.

    Se mira el campo ACTUAL (no la foto de inicio de turno): tener el eslabon en
    la mano ya es progreso aunque la evolucion no pueda completarse este turno.
    """
    necesarios, huerfanos = set(), set()
    for linea in EVO_LINES:
        linea_completa = field_counts.get(linea[-1], 0) >= 1
        faltan = []
        for pre, evo in zip(linea, linea[1:]):
            if (field_counts.get(pre, 0) == 0
                    and hand_counts.get(pre, 0) == 0):
                huerfanos.add(evo)
            elif (not linea_completa
                    and field_counts.get(pre, 0) >= 1
                    and field_counts.get(evo, 0) == 0
                    and hand_counts.get(evo, 0) == 0):
                faltan.append(evo)
        # Solo el eslabon intermedio cuya etapa 2 quedo huerfana.
        for evo in faltan:
            if evo != linea[-1] and linea[-1] in huerfanos:
                necesarios.add(evo)
    return necesarios, huerfanos


def _pokemon_injugable(card_id, field_counts, bench_count, bench_max):
    """True si traer `card_id` a la mano trae una carta MUERTA: un Pokemon que
    no se puede poner en juego ni hoy ni el turno siguiente.

    Todo se reduce al hueco de BANCA. Con `bench_count < bench_max` nada esta
    muerto: cabe cualquier Basico, y una evolucion huerfana puede completarse
    banqueando su pre-evolucion (la propia recuperacion trae hasta 3 cartas).
    Con la banca LLENA:
      * un BASICO no entra de ninguna forma -> muerto;
      * una EVOLUCION solo vive si su pre-evolucion esta EN JUEGO (evoluciona
        sobre ella sin ocupar banca). Tenerla en la MANO no basta: bajarla
        exigiria el hueco que no hay.

    Deck-agnostico: las etapas salen de `EVO_LINES` y el tipo, de `card_table`.
    No es un veto -- quien lo use debe dejar la opcion elegible como ULTIMO
    recurso, porque las recuperaciones tienen `minCount >= 1` y a veces todo el
    descarte es carta muerta.
    """
    datos = card_table.get(card_id)
    if datos is None or datos.cardType != CardType.POKEMON:
        return False
    if bench_count < bench_max:
        return False
    for linea in EVO_LINES:
        for pre, evo in zip(linea, linea[1:]):
            if evo == card_id:
                return field_counts.get(pre, 0) == 0
    return True                          # Basico con la banca llena


def _validate_id_constants():
    mismatches = []
    for _cid, _expected in _ID_NAME_EXPECTATIONS.items():
        if _cid < 0:
            continue
        _cd = card_table.get(_cid)
        _name = getattr(_cd, 'name', None) if _cd is not None else None
        if _name is None or _expected.lower() not in _name.lower():
            mismatches.append((_cid, _expected, _name))
    if mismatches:
        import sys as _sys
        for _cid, _expected, _name in mismatches:
            print(f"[WARN][ID-AUDIT] id={_cid} esperaba '{_expected}' "
                  f"pero card_table dice '{_name}'", file=_sys.stderr)
    return mismatches


def _etapa_evolutiva(card_id):
    """Etapa de `card_id`: 0 Basico, 1 Fase 1, 2 Fase 2. None si no es Pokemon.

    Sale del dato de carta (`basic`/`stage1`/`stage2`), no de `EVO_LINES`, que
    describe unicamente NUESTRO mazo.
    """
    data = card_table.get(card_id)
    if data is None or data.cardType != CardType.POKEMON:
        return None
    if getattr(data, 'stage2', False):
        return 2
    if getattr(data, 'stage1', False):
        return 1
    return 0 if getattr(data, 'basic', False) else None


def _raiz_de_linea(card_id):
    """Nombre del BASICO de la cadena evolutiva de `card_id` (None si se ignora).

    Sube por `evolvesFrom` hasta que no haya pre-evolucion. Si un eslabon
    intermedio no esta en `card_table` se devuelve el ultimo nombre conocido:
    basta para comparar dos cartas de la MISMA cadena.
    """
    data = card_table.get(card_id)
    if data is None or data.cardType != CardType.POKEMON:
        return None
    nombre = data.name or None
    vistos = set()
    while data is not None and getattr(data, 'evolvesFrom', None):
        pre = data.evolvesFrom
        if pre in vistos:                # cadena corrupta: corta el bucle
            break
        vistos.add(pre)
        nombre = pre
        data = _CARD_BY_NAME.get(pre)
    return nombre


def _misma_linea_evolutiva(a_id, b_id):
    """True si los dos ids son eslabones de la MISMA cadena Basico->F1->F2."""
    if a_id == b_id:
        return True
    raiz = _raiz_de_linea(a_id)
    return raiz is not None and raiz == _raiz_de_linea(b_id)


def _supera_en_evolucion(pkmn, otro):
    """True si `pkmn` es un eslabon MAS EVOLUCIONADO de la MISMA linea que `otro`.

    Regla del user (registro_008 paso 93 vs Cynthia's Garchomp ex, GANADA con
    error): dentro de una linea Basico -> Fase 1 -> Fase 2, noquear SIEMPRE la
    etapa MAS ALTA que se pueda. Cobra el mismo premio pero destruye mas
    desarrollo: el rival necesita rehacer los dos escalones antes de volver a
    tener su Fase 2 atacante. Ver [[boss-gust-mayor-evolucion-fase2]].
    """
    if pkmn is None or otro is None:
        return False
    e_pkmn = _etapa_evolutiva(getattr(pkmn, 'id', 0))
    e_otro = _etapa_evolutiva(getattr(otro, 'id', 0))
    if e_pkmn is None or e_otro is None or e_pkmn <= e_otro:
        return False
    return _misma_linea_evolutiva(getattr(pkmn, 'id', 0), getattr(otro, 'id', 0))


def _linea_culmina_en_ex(card_id):
    """True si por ENCIMA de `card_id` su cadena llega a un Pokemon ex/megaEx.

    Deck-agnostico: baja por `evolvesFrom` (nombres, no ids) desde la carta, asi
    que vale para CUALQUIER linea Basico -> Fase 1 -> Fase 2 del entorno sin
    inscribirla a mano en `EX_PREEVO_IDS`. Es el criterio que justifica gastar
    un Boss's en cortar la linea: la etapa final rinde 2+ premios y es el
    atacante real del mazo rival.

    Deja fuera sola la linea Abra -> Kadabra -> Alakazam (su forma final vale 1
    premio en este entorno), que es justo lo que pide
    [[boss-no-gustear-preevo-linea-no-ex]].
    """
    data = card_table.get(card_id)
    if data is None or data.cardType != CardType.POKEMON:
        return False
    pendientes = [data.name or ""]
    vistos = set()
    while pendientes:
        nombre = pendientes.pop()
        if not nombre or nombre in vistos:
            continue
        vistos.add(nombre)
        for evo in _EVOLUCIONES_POR_NOMBRE.get(nombre, ()):
            if getattr(evo, 'ex', False) or getattr(evo, 'megaEx', False):
                return True
            pendientes.append(evo.name or "")
    return False


def _preevo_de_linea_ex(card_id):
    """¿`card_id` es un eslabon que vale GUSTEAR para cortar una linea ex?

    Sustituye a la lista curada `EX_PREEVO_IDS` (menos `NONEX_FINAL_PREEVO_IDS`)
    alli donde el criterio es "la linea acaba en un atacante de 2 premios": lo
    deriva del dato de carta, asi que cubre lineas que nadie inscribio a mano
    (p.ej. Frillish -> Jellicent ex).

    Guarda `DUNSPARCE_IDS`: su linea culmina en Dudunsparce ex, pero el
    manejador de seleccion los veta SIEMPRE como objetivo de gusteo. Un motivo
    que apunta a un objetivo prohibido hace jugar (o buscar) el Boss's para
    acabar subiendo otra cosa -- es el mismo fallo que el Dwebble del log
    86339758.
    """
    if card_id in DUNSPARCE_IDS:
        return False
    return _linea_culmina_en_ex(card_id)


def _construir_cadenas_de_mazo(deck_ids):
    """Deriva del mazo las cadenas evolutivas completas.

    Devuelve `(evo_por_nombre, cadenas)`:
      evo_por_nombre: nombre de la pre-evolucion -> tupla de ids DEL MAZO que
                      evolucionan de ella.
      cadenas:        tupla de `(basico_id, fase1_id, fase2_id_o_0)`. Una misma
                      pre-evolucion puede tener varias evoluciones (copias de
                      distinta expansion), asi que se emite una cadena por
                      combinacion; el consumidor elige.

    Grand Tree busca en NUESTRA baraja, de ahi que solo se consideren ids
    presentes en `deck_ids`.
    """
    ids = set(deck_ids)
    por_nombre = defaultdict(set)
    for cid in ids:
        data = card_table.get(cid)
        if data is None or data.cardType != CardType.POKEMON:
            continue
        pre = getattr(data, 'evolvesFrom', None)
        if pre:
            por_nombre[pre].add(cid)
    evo_por_nombre = {nombre: tuple(sorted(v)) for nombre, v in por_nombre.items()}

    cadenas = []
    for cid in sorted(ids):
        data = card_table.get(cid)
        if data is None or data.cardType != CardType.POKEMON or not data.basic:
            continue
        for s1 in evo_por_nombre.get(data.name, ()):
            s1_data = card_table.get(s1)
            if s1_data is None:
                continue
            s2s = evo_por_nombre.get(s1_data.name, ())
            if s2s:
                for s2 in s2s:
                    cadenas.append((cid, s1, s2))
            else:
                cadenas.append((cid, s1, 0))
    return evo_por_nombre, tuple(cadenas)


def _evo_link_state(hand_counts, field_counts):
    """Clasifica cada EVOLUCION de nuestras lineas para el fetch de la Ultra
    Ball. Devuelve `(necesarios, huerfanos)`:

      huerfano  = su PRE-EVOLUCION no esta ni en juego ni en la mano: traerla es
                  una carta MUERTA, no se puede jugar (user, registro_006 paso
                  79 vs Marnie, PERDIDA: con un Applin en banca y NINGUN Dipplin
                  en juego ni en mano, la Ultra Ball buscaba Hydrapple ex -- que
                  no puede evolucionar nada -- en vez del Dipplin que faltaba).
      necesario = eslabon INTERMEDIO que falta (su pre-evolucion esta en juego,
                  no lo tenemos en mano ni en juego) Y que ademas DESBLOQUEA la
                  etapa 2, que ahora mismo es huerfana. Es "la siguiente
                  evolucion que se necesita en la banca".

    La etapa 2 nunca entra en `necesarios`: cuando ES el eslabon que falta ya la
    puntuan sus propias ramas (Hydrapple ex 980 / Meganium 1000), que ademas
    aplican los clamps de matchup (ex muerto vs Crustle, cesion al motor de
    refresco de Meowth ex). Subirla aqui pisaria esos clamps.

    Se mira el campo ACTUAL (no la foto de inicio de turno): tener el eslabon en
    la mano ya es progreso aunque la evolucion no pueda completarse este turno.
    """
    necesarios, huerfanos = set(), set()
    for linea in EVO_LINES:
        linea_completa = field_counts.get(linea[-1], 0) >= 1
        faltan = []
        for pre, evo in zip(linea, linea[1:]):
            if (field_counts.get(pre, 0) == 0
                    and hand_counts.get(pre, 0) == 0):
                huerfanos.add(evo)
            elif (not linea_completa
                    and field_counts.get(pre, 0) >= 1
                    and field_counts.get(evo, 0) == 0
                    and hand_counts.get(evo, 0) == 0):
                faltan.append(evo)
        # Solo el eslabon intermedio cuya etapa 2 quedo huerfana.
        for evo in faltan:
            if evo != linea[-1] and linea[-1] in huerfanos:
                necesarios.add(evo)
    return necesarios, huerfanos


def _pokemon_injugable(card_id, field_counts, bench_count, bench_max):
    """True si traer `card_id` a la mano trae una carta MUERTA: un Pokemon que
    no se puede poner en juego ni hoy ni el turno siguiente.

    Todo se reduce al hueco de BANCA. Con `bench_count < bench_max` nada esta
    muerto: cabe cualquier Basico, y una evolucion huerfana puede completarse
    banqueando su pre-evolucion (la propia recuperacion trae hasta 3 cartas).
    Con la banca LLENA:
      * un BASICO no entra de ninguna forma -> muerto;
      * una EVOLUCION solo vive si su pre-evolucion esta EN JUEGO (evoluciona
        sobre ella sin ocupar banca). Tenerla en la MANO no basta: bajarla
        exigiria el hueco que no hay.

    Deck-agnostico: las etapas salen de `EVO_LINES` y el tipo, de `card_table`.
    No es un veto -- quien lo use debe dejar la opcion elegible como ULTIMO
    recurso, porque las recuperaciones tienen `minCount >= 1` y a veces todo el
    descarte es carta muerta.
    """
    datos = card_table.get(card_id)
    if datos is None or datos.cardType != CardType.POKEMON:
        return False
    if bench_count < bench_max:
        return False
    for linea in EVO_LINES:
        for pre, evo in zip(linea, linea[1:]):
            if evo == card_id:
                return field_counts.get(pre, 0) == 0
    return True                          # Basico con la banca llena

__all__ = [
    '_etapa_evolutiva',
    '_raiz_de_linea',
    '_misma_linea_evolutiva',
    '_supera_en_evolucion',
    '_linea_culmina_en_ex',
    '_preevo_de_linea_ex',
    '_construir_cadenas_de_mazo',
    '_evo_link_state',
    '_pokemon_injugable',
    '_validate_id_constants',
    '_etapa_evolutiva',
    '_raiz_de_linea',
    '_misma_linea_evolutiva',
    '_supera_en_evolucion',
    '_linea_culmina_en_ex',
    '_preevo_de_linea_ex',
    '_construir_cadenas_de_mazo',
    '_evo_link_state',
    '_pokemon_injugable',
    '_validate_id_constants',
]
