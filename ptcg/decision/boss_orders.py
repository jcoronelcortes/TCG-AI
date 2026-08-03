"""Boss's Orders: cuanto vale jugarla y a quien gustear.

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/main-refactor-arquitectura.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

from ptcg.calculo.rival import _alakazam_relevo_de_atacante, _op_activo_inofensivo, _op_cuerpo_inofensivo
from ptcg.calculo.energia import _can_attack_eff, _grass_attach_unit, _retreat_grass_units
from ptcg.calculo.dano import _attacker_base_damage, _bench_attacker_best_damage, _bench_attacker_can_ko, _our_effective_damage
from ptcg.calculo.carta import prize_count_op
from ptcg.estado.agente import ESTADO
from ptcg.cartas.ids import Basic_Grass_Energy, Bayleef, DUNSPARCE_IDS, Dipplin, EX_PREEVO_IDS, Fezandipiti_ex, Hydrapple_ex, Meganium, OUR_EX_IDS, RETREAT_COST, THREAT_PREEVO_IDS, Tapu_Bulu, Teal_Mask_Ogerpon_ex
from ptcg.calculo.tablero import _active_of
from ptcg.calculo.energia import _grass_mult
from ptcg.calculo.dano import _ko_no_garantizado
from dataclasses import dataclass
from ptcg.cartas.ids import ALAKAZAM_ATTACKER_IDS, ALAKAZAM_LINE_IDS, Abra, Alakazam_ex, Boss_Orders, Budew, Cyndaquil, Dragapult_ex, Drakloak, Dreepy, Dwebble_Fighting, Dwebble_Grass, EX_PREEVO_IDS, Froslass, GUST_TRAMPA_IDS, Hydrapple_ex, Iron_Thorns_ex, Kadabra, Latias_ex, Lillie_Determination, Meowth_ex, Munkidori, Quilava, SCORE_FORBID, Snorunt, THREAT_PREEVO_IDS, Teal_Mask_Ogerpon_ex, Typhlosion
from ptcg.cartas.tablas import card_table
from ptcg.motor.reglas import _Ajuste, _ReglaFija


def _boss_val_de(ctx):
    return ctx.supp_values.get(Boss_Orders, 0)


def _boss_empty_gust(ctx):
    """Activo que NO puede atacar este turno (log 85799299 paso 50): el gusteo
    no es ejecutable como remate; con Lillie's en mano refrescar rinde mas.
    Se exceptuan los casos valiosos."""
    return (ctx.active_cant_attack
            and not ctx.boss_win_via_bench
            and not ctx.boss_dodge_redirect
            and not ctx.boss_defensive_gust
            and not ctx.op_has_ability_immune_active
            and not ctx.op_has_ex_immune_active
            and ctx.hand_counts.get(Lillie_Determination, 0) >= 1)


def _boss_first_turn_cede(ctx):
    """En NUESTRO primer turno (log 86025936 paso 11) con Lillie's en mano
    SIEMPRE se juega Lillie's; Boss's cede (un gusteo no cobra premio el
    primer turno)."""
    return (ctx.our_first_turn
            and ctx.hand_counts.get(Lillie_Determination, 0) >= 1
            and not ctx.state.supporterPlayed
            and not ctx.boss_win_via_bench)


def _boss_cede_dig(ctx):
    """Cede a Lillie's cuando NO tenemos un atacante REAL de banca (user,
    registro_005 vs Dragapult): un gusteo de DESARROLLO (cortar la linea
    rival noqueando un basico/pre-evo de 1 premio) no tiene prioridad si
    ademas del activo solo tenemos BASICOS y ningun atacante de banca
    listo: sin segundo atacante el gusteo no encadena y conviene CAVAR.
    `has_ready_bench_attacker` solo cuenta atacantes reales listos, nunca
    un Applin. Se exceptuan TODOS los gusteos valiosos."""
    # ACTIVO CONDENADO SIN RELEVO (user, registro_004 t4 vs Team Rocket,
    # PERDIDA; deck-agnostico): con el activo a punto de morir
    # (active_ko_likely) y NINGUN atacante de banca listo, un gusteo de
    # premios que NO gana la partida (boss_ko_threat_preevo: +1 premio del
    # Spidops debil) deja el tablero sin plan -- el rival noquea, promovemos
    # un cuerpo sin energia y la mano muerta no rehace nada. Ahi el KO cede
    # a Lillie's (cavar atacantes futuros); el gusteo GANADOR
    # (boss_win_via_bench / win_via_boss_gust) sigue dominando.
    # `active_doomed_real` (user, registro_004 t4 vs Mega Lucario, PERDIDA):
    # el heuristico `active_ko_likely` daba False con nuestro Ogerpon ex a
    # 210/210 PV porque `_op_best_damage_vs` no resuelve el dano del ataque
    # rival (siempre 0); el Mega Lucario ex de enfrente ya tenia las 2
    # energias de Mega Brave (270) y lo noqueaba seguro. Se consulta tambien
    # el remate REAL leido de attack_table para que la cesion dispare.
    _condenado_sin_relevo = ((ctx.active_ko_likely or ctx.active_doomed_real)
                             and not ctx.has_ready_bench_attacker)
    return (ctx.hand_counts.get(Lillie_Determination, 0) >= 1
            and not ctx.has_ready_bench_attacker
            and not ctx.boss_win_via_bench
            and not ctx.boss_dodge_redirect
            and not ctx.boss_defensive_gust
            and not (ctx.boss_ko_threat_preevo
                     and not _condenado_sin_relevo)
            and not ctx.boss_deny_alakazam_line
            and not ctx.op_has_ability_immune_active
            and not ctx.op_has_ex_immune_active)


def _boss_unlock_gust(ctx):
    """Gustear para DES-LOCKEAR habilidades (autopsia iron_thorns p018 t10,
    paso 3 plan jul 2026): con Iron Thorns ex de ACTIVO rival, Initialization
    anula Teal Dance / Ripening / Last-Ditch / Flip the Script -- todo nuestro
    motor. El lock es POSICIONAL: subir con Boss's cualquier cuerpo NO-locker
    de su banca lo apaga en el acto (a diferencia de Watchtower, que es
    estadio y el gusteo no lo toca). En 6 turnos muertos de la autopsia el
    agente tenia Boss's en mano, banca rival con no-lockers... y END
    (`sin_valor`). Encadena ademas con Meowth ex EN MANO: Boss's primero
    (des-lockea), Meowth despues -> Last-Ditch ya funciona.
    Guards: Iron Thorns ex en el ACTIVO rival, un no-locker en su banca que
    subir, y que el des-lockeo nos sirva HOY (Ogerpon ex / Hydrapple ex en
    juego, o Meowth ex en mano)."""
    act = ctx.op_state.active[0] if ctx.op_state.active else None
    if act is None or act.id != Iron_Thorns_ex:
        return False
    if not any(b is not None and b.id != Iron_Thorns_ex
               for b in (ctx.op_state.bench or [])):
        return False
    return (ctx.field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1
            or ctx.field_counts.get(Hydrapple_ex, 0) >= 1
            or ctx.hand_counts.get(Meowth_ex, 0) >= 1)


def _boss_motivo_con_premio(ctx):
    """¿El gusteo tiene un motivo REAL por delante? Denominador comun de los
    dos vetos de abajo: si algo de esto esta vivo, el Boss's se juega y ellos
    deciden el objetivo. Cubre los remates (ganar la partida, 2 premios, KO por
    `boss_prize_rank`), los cortes de linea con KO (`deny_evo`,
    `deny_alakazam_line`, `gust_key_bench`, `ko_threat_preevo`), la esquiva
    (`dodge_redirect`), el gusteo DEFENSIVO (evitar el remate rival) y los
    muros que anulan a nuestro atacante de frente."""
    v = ctx.supp_values
    return (ctx.win_via_boss_gust or ctx.gust_2prize_via_boss
            or ctx.boss_win_via_bench or ctx.boss_deny_alakazam_line
            or ctx.boss_prize_rank >= 1 or ctx.boss_ko_threat_preevo
            or ctx.boss_dodge_redirect or ctx.boss_defensive_gust
            or ctx.op_has_ability_immune_active or ctx.op_has_ex_immune_active
            or bool(v.get('_boss_deny_evo'))
            or bool(v.get('_boss_gust_key_bench')))


def _gust_es_basico(card_id):
    data = card_table.get(card_id)
    return (data is not None
            and not getattr(data, 'stage1', False)
            and not getattr(data, 'stage2', False))


def _v_gust_traba_neta(c):
    v = 500 + c.stall_diff * 100
    # Desempate (usuario): entre objetivos que traban IGUAL, evitar subir la
    # PRE-EVOLUCION del atacante principal rival (podria evolucionar y atacar
    # desde el activo). Penalizacion pequena que solo rompe empates.
    if c.card_id in THREAT_PREEVO_IDS or c.card_id in EX_PREEVO_IDS:
        v -= 50
    return v


_REGLAS_GUST_ESTORBO = [
    # Coste de retirada GRATIS: el rival lo devuelve al banco sin pagar
    # nada; no estorba en absoluto (p.ej. Budew). Descartado.
    _ReglaFija("retirada_gratis",
               lambda c: c.rc0 <= 0,
               lambda c: SCORE_FORBID),
    # Latias ex (Skyliner) deja retirar GRATIS a cualquier Basico: gustear
    # un Basico no lo traba, y gustear a la propia Latias es inutil (user,
    # registro 010 paso 76 vs Dragapult). El objetivo correcto es un
    # NO-basico (p.ej. Drakloak).
    _ReglaFija("latias_libera_basicos",
               lambda c: (c.op_latias
                          and (c.card_id == Latias_ex
                               or _gust_es_basico(c.card_id))),
               lambda c: SCORE_FORBID),
    # Subir un Iron Thorns ex como ESTORBO es un tiro en el pie: su
    # Initialization en el activo LOCKEA nuestras habilidades (Teal Dance /
    # Ripening / Last-Ditch) -- si ya habia uno delante, el gusteo que debia
    # des-lockear (gusteo_deslockea_habilidades) lo mantiene; si no lo
    # habia, lo crea. En modo OFENSIVO no aplica: gustearlo para NOQUEARLO
    # cobra 2 premios y se lo lleva del tablero.
    _ReglaFija("estorbo_crea_lock_iron_thorns",
               lambda c: c.card_id == Iron_Thorns_ex,
               lambda c: SCORE_FORBID),
    # Estorbo proporcional al coste de retirada NETO (el que el rival no
    # puede pagar con su energia): a mayor coste sin energia, mas se traba.
    _ReglaFija("traba_neta",
               lambda c: c.stall_diff >= 1,
               _v_gust_traba_neta),
    # Ya puede pagar su propia retirada: mal objetivo (defecto -200).
]


_AJUSTES_GUST_ESTORBO = [
    # Generalizacion Alakazam (user, registro_004 paso 51 vs Garchomp,
    # PERDIDA): privilegiar SIEMPRE la MAYOR evolucion de la linea rival
    # que un atacante de banca pueda NOQUEAR tras retirar. Sin esto, el
    # modo estorbo prefiere el basico y deja crecer la linea rival.
    _Ajuste("linea_rival_mayor_evolucion",
            # c.rc0 > 0: en el original este override vive DENTRO del else
            # de retirada-gratis; no debe rescatar un FORBID por rc0<=0.
            lambda c, s: (c.rc0 > 0 and not c.op_alakazam
                          and c.linea_rank >= 1 and c.linea_can_ko),
            lambda c, s: max(s, 6000 + c.linea_rank * 3000
                             + c.energia * 50
                             + (300 if c.tiene_tool else 0))),
    # Regla (user, registro 014 paso 146 vs Alakazam): en modo estorbo,
    # PRIORIZAR la linea Alakazam sobre otros basicos de soporte; atrapar
    # su pre-evo corta el desarrollo. Kadabra > Abra > Alakazam.
    _Ajuste("linea_alakazam_estorbo",
            lambda c, s: (c.op_alakazam
                          and c.card_id in ALAKAZAM_LINE_IDS),
            lambda c, s: s + {Kadabra: 350, Abra: 300,
                              Alakazam_ex: 250}[c.card_id]),
    # ...pero SIN KO ese orden esta invertido: subir un Kadabra/Alakazam es
    # cambiarle un atacante por otro (Powerful Hand cuesta 1 energia y el
    # Kadabra evoluciona el mismo turno). El relevo solo funciona con un Abra
    # pelado o con un cuerpo fuera de la linea (user, registro_002 paso 20).
    # Va DESPUES del ajuste de arriba para pisar su bonificacion.
    _Ajuste("linea_alakazam_no_promover_atacante",
            lambda c, s: (c.op_alakazam and not c.can_ko
                          and c.card_id in ALAKAZAM_ATTACKER_IDS),
            lambda c, s: SCORE_FORBID),
    # Mismo criterio que en modo OFENSIVO (ver alli), y aqui pesa mas: en modo
    # estorbo nuestro activo NO puede atacar, asi que el cuerpo que subamos nos
    # golpea sin respuesta. `traba_neta` solo mira quien no puede pagar su
    # RETIRADA; esto mira quien no puede pagar su ATAQUE. `s > 0` para no
    # rescatar un SCORE_FORBID de las reglas de arriba.
    _Ajuste("sin_ko_prefiere_cuerpo_muerto",
            lambda c, s: (s > 0 and not c.can_ko and c.cuerpo_inofensivo
                          and c.card_id not in GUST_TRAMPA_IDS),
            lambda c, s: s + 1500),
]


def _gust_linea_evolutiva(c, id_final, id_medio, id_basico):
    """Contribucion para mazos de linea evolutiva conocida (Dragapult,
    Ethan's Typhlosion, Alakazam): clavar/derribar la pieza mas avanzada.
    La fase 1 SIN energia queda CLAVADA (no paga retirada ni ataca) y
    RETRASA la evolucion: mejor objetivo de disrupcion; el basico sin
    energia tambien queda clavado (estorbo fuerte)."""
    if c.card_id == id_final:
        return 1200 if c.can_ko else 800
    if c.card_id == id_medio:
        if c.can_ko:
            return 1000
        return 700 if c.energia < c.rc1 else 300
    if c.card_id == id_basico:
        if c.can_ko:
            return 400
        return 500 if c.energia < c.rc1 else 200
    if c.can_ko:
        if c.is_ex:
            return 900 + c.energia * 50
        if c.is_stage1:
            return 350 + c.energia * 50
        return 250 + c.energia * 50
    return 150


def _gust_tiers_genericos(c):
    """Mazo sin linea conocida: tiers por etapa/energia (KO / no-KO)."""
    if c.can_ko:
        if c.is_ex and c.energia >= 1:
            return 1100
        if c.is_ex:
            return 1000
        if c.is_stage2 and c.energia >= 1:
            return 900
        if c.is_stage2:
            return 850
        if c.is_stage1 and c.energia >= 1:
            return 700
        if c.is_stage1:
            return 600
        if c.card_id in THREAT_PREEVO_IDS:
            return 550
        if c.card_id == Budew:
            return 500
        if c.card_id == Munkidori:
            return 450
        if c.card_id == Snorunt:
            return 400
        if c.card_id in (Dwebble_Grass, Dwebble_Fighting):
            return 380
        if c.card_id in (Dreepy,):
            return 350
        if c.energia >= 1:
            return 300
        return 200
    if c.is_ex and c.energia >= 1:
        return 250
    if c.is_ex:
        return 200
    if c.is_stage2 and c.energia >= 1:
        return 180
    if c.is_stage2:
        return 160
    if c.is_stage1 and c.energia >= 1:
        return 150
    if c.is_stage1:
        return 130
    if c.card_id == Froslass:
        return 220
    if c.card_id == Budew:
        return 200
    if c.card_id == Munkidori:
        return 190
    if c.card_id == Snorunt:
        return 185
    if c.card_id in (Dreepy, Drakloak):
        return 180
    if c.card_id in (Dwebble_Grass, Dwebble_Fighting):
        return 178
    return 100


def _gust_linea_rival(c):
    if c.op_linea_dragapult:
        return _gust_linea_evolutiva(c, Dragapult_ex, Drakloak, Dreepy)
    if c.op_linea_typhlosion:
        return _gust_linea_evolutiva(c, Typhlosion, Quilava, Cyndaquil)
    if c.op_alakazam:
        return _gust_linea_evolutiva(c, Alakazam_ex, Kadabra, Abra)
    return _gust_tiers_genericos(c)


def _gust_releva_al_atacante(op_state):
    """Deck-agnostico: ¿el gusteo cambia un ATACANTE por un cuerpo muerto?

    Es la generalizacion de `_alakazam_relevo_de_atacante` al resto de mazos de
    linea evolutiva. Un gusteo SIN KO solo le cuesta un turno al rival cuando su
    ACTIVO puede atacar (o podra con un adjunte) y el cuerpo que sube NO: ahi la
    energia invertida se queda parada en la banca y para volver hay que pagar
    retirada. Si su activo ya no ataca, no hay nada que relevar -- y ademas
    Boss's le regala la retirada gratis (`_boss_gusteo_sin_proposito`).

    Se descartan como relevo:
      * Dunsparce: objetivo PROHIBIDO de gusteo (regla del user);
      * las PRE-EVOLUCIONES de amenaza conocidas (THREAT_PREEVO_IDS /
        EX_PREEVO_IDS): evolucionan EN EL ACTIVO y atacan con el cuerpo NUEVO,
        asi que su coste de ataque de hoy no dice nada. Es justo lo que paso en
        registro_002 paso 20 con el Abra -> Kadabra.

    NOTA: vs Alakazam sigue mandando `_alakazam_relevo_de_atacante`, que SI
    admite un Abra pelado como relevo (regla explicita del user). Aqui el Abra
    quedaria descartado por ser pre-evo de amenaza -- y ademas su ataque cuesta
    1, asi que tampoco es "inofensivo" por coste.
    """
    if _op_activo_inofensivo(op_state):
        return False
    for _b in (op_state.bench or []):
        if _b is None or _b.id in DUNSPARCE_IDS:
            continue
        if _b.id in THREAT_PREEVO_IDS or _b.id in EX_PREEVO_IDS:
            continue
        if _op_cuerpo_inofensivo(_b):
            return True
    return False


def _grass_unlocks_active_retreat(my_state, op_state, meganium_active,
                                  total_grass, bench_count, neutral_zone,
                                  active_can_attack, budget=1):
    """(ko, chip): ¿las Plantas que AUN pueden aterrizar sobre el ACTIVO pagan su
    coste de retirada y habilitan atacar con un atacante de banca?

    Nucleo comun de la linea "Planta al activo -> RETIRAR -> atacar con el de
    banca". Lo consumen dos rutas distintas:
      * el adjunte MANUAL (`_attach_enable_retreat_ko` /
        `_attach_enable_retreat_attack`, que ademas exigen que el adjunte del
        turno siga libre), y
      * las HABILIDADES de carga (Ripening Charge adjunta a CUALQUIERA de
        nuestros Pokemon, Teal Dance al suyo): esas NO gastan el adjunte manual,
        asi que la linea sigue viva con `state.energyAttached` ya puesto
        (user, registro_014 pasos 137/141 vs Alakazam).

    Devuelve (False, False) si no hay nada que desbloquear: el activo ya paga su
    retirada, una Planta no le alcanza, o con esa Planta el PROPIO activo ataca
    igual o mejor que el cuerpo de banca (entonces no se retira). `chip` solo se
    evalua si el activo NO puede atacar este turno.

    La comparacion con el ataque del activo es por DANO, no por "puede atacar"
    (user, registro_006 paso 101 vs Alakazam, PERDIDA): el activo era un Applin
    (coste de ataque 1, coste de retirada 1) con un Teal Mask Ogerpon ex de banca
    a 6 energias efectivas que NOQUEABA al Alakazam. Como una Planta dejaba al
    Applin "en su coste de ataque", el guardia antiguo apagaba la linea entera --
    y eso que `_attacker_base_damage` no le da NI UN PUNTO de dano al Applin. La
    Planta se fue a un Ogerpon de banca y el turno acabo sin atacar. Un cuerpo de
    relleno que llega a su coste de ataque no puede vetar el KO servido de un
    atacante real; el empate si se resuelve a favor del activo (atacar con el
    activo es lo primero, y ademas no gasta la retirada).

    `budget` es el PRESUPUESTO de carga: cuantas Plantas pueden todavia aterrizar
    sobre el ACTIVO en este turno (adjunte manual sin gastar + habilidades de
    carga que le apunten, acotado por las Plantas disponibles). Espeja el
    presupuesto de `_carga_activo_remata`, que ya calculaba asi el coste de
    ATAQUE del activo -- aqui faltaba y la linea se limitaba a UNA Planta (user,
    episodio 88631738 paso 77): con un coste de retirada de 2 o 3 simbolos y dos
    vias de carga vivas, la retirada era pagable y el detector no la veia, asi
    que el turno se cerraba sin atacar. `budget=1` (defecto) reproduce el
    comportamiento anterior, que es lo correcto para los consumidores con una
    sola Planta a mano (p. ej. la que recupera una Night Stretcher del descarte).
    """
    act = _active_of(my_state)
    opa = _active_of(op_state)
    if act is None or opa is None:
        return False, False
    rc = RETREAT_COST.get(act.id, 1)
    e = len(act.energies)
    unit = _grass_attach_unit()
    if e >= rc:
        return False, False
    # Plantas necesarias para llegar al coste (redondeo hacia arriba), y las que
    # el presupuesto permite. La cadena se ejecuta paso a paso: el desempate
    # greedy vuelve a evaluar tras cada carga, con `need` ya decrementado.
    need = -(-(rc - e) // unit) if unit > 0 else 0
    if not 1 <= need <= max(1, int(budget or 1)):
        return False, False
    gained = need * unit
    # Dano EFECTIVO que haria el propio activo con esas mismas Plantas (0 si no
    # llega a su coste de ataque o si su ataque no puntua en el modelo).
    act_dmg = 0
    if _can_attack_eff(act.id, e + gained):
        _act_base = _attacker_base_damage(
            act.id, opa, e + gained, grass_scale=total_grass + gained,
            teal_self_energy=e + gained, bench_count=bench_count)
        act_dmg = _our_effective_damage(act, opa, _act_base, meganium_active,
                                        neutral_zone)
        if act_dmg > 0 and act_dmg >= (opa.hp or 0):
            # El activo REMATA con esa Planta: atacar con el es lo primero.
            return False, False
    # La energia adjuntada se descarta al pagar la retirada: el Grass del campo
    # tras retirar se aproxima con el actual (neto ~0).
    grass_after = max(0, total_grass - _retreat_grass_units(rc))
    if _bench_attacker_can_ko(my_state, opa, meganium_active, total_grass,
                              bench_count, grass_after, neutral_zone):
        return True, False
    if active_can_attack:
        return False, False
    # Guarda "no cambiar un ex por un cuerpo peor" (espejo del scorer de
    # retirada): el cuerpo que sube debe aguantar al menos lo que le queda al ex.
    min_hp = (act.hp or 0) if act.id in OUR_EX_IDS else 0
    chip = _bench_attacker_best_damage(
        my_state, opa, meganium_active, bench_count, grass_after,
        neutral_zone, min_body_hp=min_hp)
    return False, chip > act_dmg


def _boss_regala_linea_alakazam(ctx):
    """VETO vs Alakazam (user, registro_002 paso 20, PERDIDA -- ep. 88906640).

    Turno 2: nuestro Ogerpon ex a 1/3 energias (sin ataque), su activo un
    Fezandipiti ex a 0 energias (Cruel Arrow cuesta 3: NO puede atacar en su
    turno) y su banca con cuatro Abra + un Dunsparce. El agente jugo Boss's
    Orders y subio un Abra; el rival tenia el Kadabra EN LA MANO, evoluciono y
    empezo a atacar con el cuerpo que le habiamos puesto delante.

    Dos errores en la misma jugada: (1) el gusteo no cobraba nada -- el activo
    rival no era una amenaza que hubiera que quitar de enmedio; (2) en ESTE
    matchup Abra/Kadabra/Alakazam son la unica linea atacante, asi que subir
    uno es hacerles el trabajo. La valoracion venia de la rama
    `elif op_is_alakazam_deck` de `evaluate_supporters`, que puntuaba 700 el
    gusteo de "la mayor evolucion de la linea que haya en banca" sin exigir KO.

    El unico gusteo sin KO que se permite es el RELEVO de su atacante
    (`_alakazam_relevo_de_atacante`). Todo motivo con premio por delante
    (`_boss_motivo_con_premio`) manda sobre este veto."""
    if not ctx.op_is_alakazam_deck or _boss_motivo_con_premio(ctx):
        return False
    return not _alakazam_relevo_de_atacante(ctx.op_state)


def _boss_gusteo_sin_proposito(ctx):
    """VETO deck-agnostico: gusteo sin KO contra un activo rival INOFENSIVO.

    Boss's Orders es, para el rival, una RETIRADA GRATIS. Solo compensa
    regalarsela por una de dos razones: cobrar un premio que de frente no
    cobramos, o quitar de enmedio al cuerpo que nos va a golpear. Si su ACTIVO
    no puede atacar ni en su proximo turno (`_op_activo_inofensivo`: todos sus
    ataques cuestan mas de energias+1) la segunda razon no existe, y
    `_boss_motivo_con_premio` ya descarta la primera: el gusteo solo mueve
    cuerpos, gasta el Supporter del turno y deja al rival mejor colocado.

    Generaliza el fallo de `registro_002 paso 20` a cualquier mazo: las ramas
    de `evaluate_supporters` que puntuan "subir la mayor evolucion de su linea"
    (Dragapult, Ethan's Typhlosion, Gardevoir, Zoroark, Slowking, Alakazam) y
    la rama de TRABA (`stall_val`) no exigen KO, y todas desembocan en la regla
    de reserva `valor_del_supporter`.

    EXCEPCION: si su activo es una pre-evolucion de amenaza conocida
    (THREAT_PREEVO_IDS / EX_PREEVO_IDS) no se lee su ataque actual -- evoluciona
    y ataca con el cuerpo nuevo -- asi que no se veta."""
    if _boss_motivo_con_premio(ctx):
        return False
    act = ctx.op_state.active[0] if ctx.op_state.active else None
    if act is not None and (act.id in THREAT_PREEVO_IDS
                            or act.id in EX_PREEVO_IDS):
        return False
    return _op_activo_inofensivo(ctx.op_state)


@dataclass
class _CtxGustObjetivo:
    card_id: int
    energia: int
    rc0: int                 # RETREAT_COST.get(id, 0) (trabas)
    rc1: int                 # RETREAT_COST.get(id, 1) (lineas evolutivas)
    stall_diff: int          # rc0 - energia
    is_ex: bool              # flag ex (sin mega)
    is_exmega: bool          # ex o megaEx (tiers de KO)
    is_megaex: bool          # megaEx (3 premios): tier propio por encima de ex
    prizes: int              # prize_count(objetivo): premios que cobramos al noquearlo
    wins_now: bool           # el KO de este objetivo GANA la partida (prizes >= my_prize)
    is_stage1: bool
    is_stage2: bool
    tiene_tool: bool
    can_ko: bool             # el activo (o banca tras retirar) lo noquea
    tier_ko: int             # 1..8 si can_ko, 0 si no
    plan_target_match: bool  # o.index == plan.target - 1
    regust_energized: bool   # copia energizada del activo rival sin energia
    linea_rank: int          # 0 basico / 1 stage1 / 2 stage2
    linea_can_ko: bool       # estorbo: atacante de banca la noquea tras retirar
    op_alakazam: bool
    op_latias: bool
    op_linea_dragapult: bool
    op_linea_typhlosion: bool
    # El ACTIVO rival anula nuestro dano (muro): atacar de frente da 0 premios.
    muro_bloquea_activo: bool = False
    # El objetivo NO podria atacar desde el activo en el proximo turno rival ni
    # adjuntandole una energia (`_op_cuerpo_inofensivo`, medido por COSTE). Es
    # el dato que decide el objetivo cuando NO hay KO: subir un cuerpo muerto
    # les cuesta el turno; subir uno que ataca les hace el trabajo.
    cuerpo_inofensivo: bool = False


def _ctx_gust_objetivo(card, o, my_state, op_state, state, hand_counts,
                       total_grass, bench_count, neutralization_zone_active,
                       op_is_alakazam, op_latias, op_linea_dragapult,
                       op_linea_typhlosion, my_prize=6):
    tgt_data = card_table.get(card.id)
    energia = len(card.energies) if hasattr(card, 'energies') else 0
    hp = card.hp if hasattr(card, 'hp') else 999
    is_ex = bool(tgt_data and getattr(tgt_data, 'ex', False))
    is_megaex = bool(tgt_data and getattr(tgt_data, 'megaEx', False))
    is_exmega = bool(tgt_data is not None and
                     (getattr(tgt_data, 'ex', False) or
                      getattr(tgt_data, 'megaEx', False)))
    prizes = prize_count_op(card)
    is_stage1 = bool(tgt_data and getattr(tgt_data, 'stage1', False))
    is_stage2 = bool(tgt_data and getattr(tgt_data, 'stage2', False))

    # KO por el ACTIVO: tabla de dano por atacante + debilidad/resistencia
    # (salvo Fezandipiti, dano fijo) + inmunidades ex/habilidad.
    can_ko = False
    atk = my_state.active[0] if my_state.active else None
    if atk is not None:
        eff_e = len(atk.energies) * _grass_mult()
        can_attach = (hand_counts.get(Basic_Grass_Energy, 0) >= 1
                      and not state.energyAttached)
        eff_after = eff_e + (_grass_attach_unit() if can_attach else 0)
        dmg = 0
        if atk.id == Hydrapple_ex and eff_after >= 2:
            dmg = 30 + 30 * total_grass
        elif atk.id == Dipplin and eff_after >= 1:
            dmg = 20 * bench_count
        elif atk.id == Teal_Mask_Ogerpon_ex and eff_after >= 3:
            o_e = energia
            m_e = len(atk.energies) + (1 if can_attach else 0)
            dmg = 30 + 30 * (o_e + m_e)
        elif atk.id == Tapu_Bulu and eff_after >= 4:
            dmg = 220
        elif atk.id == Fezandipiti_ex and eff_after >= 3:
            dmg = 100
        elif atk.id == Meganium and eff_after >= 4:
            dmg = 140
        elif atk.id == Bayleef and eff_after >= 2:
            dmg = 60

        # Evaluador CENTRAL de dano (P0.1): la copia inline aplicaba debilidad
        # e inmunidades ex/habilidad pero ignoraba Drednaw (anula >=200),
        # Sturdy/Resolute Heart (cap a hp-10), Armor Tail de Farigiraf y la
        # Neutralization Zone -> `can_ko`/`wins_now` podian declarar KOs falsos.
        eff_dmg = _our_effective_damage(atk, card, dmg, ESTADO.meganium_in_play,
                                        neutralization_zone_active)
        if eff_dmg >= hp:
            can_ko = True

    # KO alternativo: retirar el activo y noquear con un atacante de banca.
    if not can_ko and atk is not None:
        switch_hand = hand_counts.get(1123, 0) >= 1
        ret_cost = RETREAT_COST.get(atk.id, 1)
        if switch_hand or len(atk.energies) >= ret_cost:
            grass_after = max(0, total_grass
                              - (0 if switch_hand else ret_cost))
            if _bench_attacker_can_ko(
                    my_state, card, ESTADO.meganium_in_play, total_grass,
                    bench_count, grass_after, neutralization_zone_active):
                can_ko = True

    # Tiers de KO PRIZE-AWARE (user, registro_011 vs Mega Heracross ex): un
    # megaEx rinde 3 PREMIOS, un ex 2. Antes ambos caian en `is_exmega` (tier
    # 8/7) y el +1 por "energizado" (con_e) hacia que un ex de 2 premios
    # ENERGIZADO (tier 8) le ganara a un megaEx de 3 premios SIN energia (tier
    # 7): el juego gusteaba el Ogerpon ex (2) en vez del Mega (3) que ganaba la
    # partida. Ahora el megaEx tiene su propio tier POR ENCIMA del ex (10/9 vs
    # 8/7), de modo que un Mega sin energia (9 -> 27000) supera a un ex
    # energizado (8 -> 24000). Deck-agnostico.
    tier = 0
    if can_ko:
        con_e = energia >= 1
        if is_megaex:
            tier = 10 if con_e else 9
        elif is_ex:
            tier = 8 if con_e else 7
        elif is_stage2:
            tier = 6 if con_e else 5
        elif is_stage1:
            tier = 4 if con_e else 3
        else:
            tier = 2 if con_e else 1

    # Estorbo: la MAYOR evolucion de la linea rival que un atacante de banca
    # pueda noquear tras retirar el activo (registro_004 paso 51 vs Garchomp).
    linea_rank = 2 if is_stage2 else (1 if is_stage1 else 0)
    linea_can_ko = False
    if linea_rank >= 1 and atk is not None:
        switch_hand = hand_counts.get(1123, 0) >= 1
        ret_cost = RETREAT_COST.get(atk.id, 1)
        if switch_hand or len(atk.energies) >= ret_cost:
            grass_after = max(0, total_grass
                              - (0 if switch_hand else ret_cost))
            if _bench_attacker_can_ko(
                    my_state, card, ESTADO.meganium_in_play, total_grass,
                    bench_count, grass_after, neutralization_zone_active):
                linea_can_ko = True

    op_act = op_state.active[0] if op_state.active else None
    regust = (can_ko and op_act is not None and op_act.id == card.id
              and len(op_act.energies) == 0 and energia >= 1)

    # MURO EN EL PUESTO ACTIVO (deck-agnostico): si nuestro ACTIVO no le hace NI
    # UN punto de dano al activo rival, atacar de frente no cobra premios y el
    # unico premio del turno esta en la BANCA rival. Cubre cualquier anulacion
    # que ya modele `_our_effective_damage` (Mysterious Rock Inn de Crustle,
    # Cornerstone Stance, Sylveon...), no una lista de ids. Lo consume la
    # exencion del veto anti-Dwebble en `_AJUSTES_GUST_ESTORBO`.
    muro_bloquea_activo = False
    if atk is not None and op_act is not None:
        _mb_raw = len(atk.energies) + (
            1 if (hand_counts.get(Basic_Grass_Energy, 0) >= 1
                  and not state.energyAttached) else 0)
        _mb_base = _attacker_base_damage(
            atk.id, op_act, _mb_raw * _grass_mult(), grass_scale=total_grass,
            teal_self_energy=_mb_raw, bench_count=bench_count)
        muro_bloquea_activo = _our_effective_damage(
            atk, op_act, _mb_base, ESTADO.meganium_in_play,
            neutralization_zone_active) <= 0

    return _CtxGustObjetivo(
        card_id=card.id, energia=energia,
        rc0=RETREAT_COST.get(card.id, 0), rc1=RETREAT_COST.get(card.id, 1),
        stall_diff=RETREAT_COST.get(card.id, 0) - energia,
        is_ex=is_ex, is_exmega=is_exmega, is_megaex=is_megaex,
        # `wins_now` exige ademas KO GARANTIZADO (P0.1): contra Tenacious Body
        # (moneda) o Survival Brace el remate puede fallar y regalar el turno.
        prizes=prizes, wins_now=(can_ko and prizes >= my_prize
                                 and not _ko_no_garantizado(card)),
        is_stage1=is_stage1, is_stage2=is_stage2,
        tiene_tool=bool(getattr(card, 'tools', None)),
        can_ko=can_ko, tier_ko=tier,
        plan_target_match=(o.index == ESTADO.plan.target - 1),
        regust_energized=regust,
        linea_rank=linea_rank, linea_can_ko=linea_can_ko,
        op_alakazam=op_is_alakazam, op_latias=op_latias,
        op_linea_dragapult=op_linea_dragapult,
        op_linea_typhlosion=op_linea_typhlosion,
        muro_bloquea_activo=muro_bloquea_activo,
        cuerpo_inofensivo=_op_cuerpo_inofensivo(card))

__all__ = [
    '_boss_val_de',
    '_boss_empty_gust',
    '_boss_first_turn_cede',
    '_boss_cede_dig',
    '_boss_unlock_gust',
    '_boss_motivo_con_premio',
    '_gust_es_basico',
    '_v_gust_traba_neta',
    '_gust_linea_evolutiva',
    '_gust_tiers_genericos',
    '_gust_linea_rival',
    '_REGLAS_GUST_ESTORBO',
    '_AJUSTES_GUST_ESTORBO',
    '_gust_releva_al_atacante',
    '_boss_regala_linea_alakazam',
    '_boss_gusteo_sin_proposito',
    '_CtxGustObjetivo',
    '_ctx_gust_objetivo',
    '_grass_unlocks_active_retreat',
]
