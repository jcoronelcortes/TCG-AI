"""Boss's Orders: cuanto vale jugarla y a quien gustear.

Extraido VERBATIM de main.py por utils/extraer_definiciones.py
(docs/main-refactor-arquitectura.md). Su pureza esta comprobada por
utils/pureza.py: nada de aqui toca el estado mutable ni las tablas de runtime.
"""

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
]
