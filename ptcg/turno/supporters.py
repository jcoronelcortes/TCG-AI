"""`evaluate_supporters`, extraida VERBATIM de `agent()` (Ola 5).

Capturaba 41 variables del turno; ahora llegan en un contexto que se
desempaqueta al entrar, con los MISMOS nombres, de modo que el cuerpo es
exactamente el que estaba en main.py.
"""

from cg.api import EnergyType
from ptcg.calculo.carta import prize_count_op
from ptcg.calculo.dano import _attacker_base_damage, _bench_attacker_can_ko, _our_effective_damage
from ptcg.calculo.energia import _grass_attach_unit, _grass_mult, _retreat_grass_units
from ptcg.cartas.grupos import EVO_LINES
from ptcg.cartas.ids import ABILITY_IMMUNE_IDS, Abra, Alakazam_ex, Applin, BOSS_PRIORITY_CRUSTLE_GUST, Basic_Grass_Energy, Bayleef, Boss_Orders, Chikorita, Crustle_Fighting, Crustle_Grass, Dawn, Dipplin, Drednaw, Dusclops, Duskull, Dwebble_Fighting, Dwebble_Grass, EX_IMMUNE_IDS, EX_PREEVO_IDS, Fezandipiti_ex, Froslass, HIGH_PRIORITY_BENCH_TARGETS, Hydrapple_ex, KEY_BENCH_ATTACKER_IDS, Kadabra, Kirlia, LANA_PLAY_BASE_RECUPERABLE, LANA_PLAY_SIN_DEMANDA, Lanas_Aid, Lillie_Determination, Meganium, Meowth_ex, Munkidori, NONEX_FINAL_PREEVO_IDS, OUR_ABILITY_IDS, OUR_EX_IDS, Pinsir, RETREAT_COST, Ralts, Slowpoke, THREAT_PREEVO_IDS, Tapu_Bulu, Teal_Mask_Ogerpon_ex, Ultra_Ball, Zorua_N
from ptcg.cartas.lineas import _pokemon_injugable, _preevo_de_linea_ex, _supera_en_evolucion
from ptcg.cartas.tablas import card_table
from ptcg.decision.boss_orders import _gust_releva_al_atacante
from ptcg.estado.agente import ESTADO
from ptcg.estado.claves import ESTADO_MAZO
from ptcg.turno.supporters_ctx import CtxEvaluateSupporters  # noqa: F401


def evaluate_supporters(tc):
    # Desempaquetado de las capturas.
    _active_cant_attack_this_turn = tc._active_cant_attack_this_turn
    _plan_de_planta = tc._plan_de_planta
    bench_count = tc.bench_count
    bench_max = tc.bench_max
    budew_on_op_field = tc.budew_on_op_field
    budew_op_index = tc.budew_op_index
    can_switch = tc.can_switch
    estimated_op_damage = tc.estimated_op_damage
    field_counts = tc.field_counts
    hand_counts = tc.hand_counts
    has_hydrapple = tc.has_hydrapple
    has_switch_card = tc.has_switch_card
    meowth_ability_lock = tc.meowth_ability_lock
    my_prize = tc.my_prize
    my_state = tc.my_state
    neutralization_zone_active = tc.neutralization_zone_active
    op_active_dodge_immune = tc.op_active_dodge_immune
    op_has_ability_immune_active = tc.op_has_ability_immune_active
    op_has_crustle_bench = tc.op_has_crustle_bench
    op_has_dreepy_line = tc.op_has_dreepy_line
    op_has_dwebble_bench = tc.op_has_dwebble_bench
    op_has_eevee_bench = tc.op_has_eevee_bench
    op_has_ethan_preevo = tc.op_has_ethan_preevo
    op_has_ex_immune_active = tc.op_has_ex_immune_active
    op_has_ex_immune_bench = tc.op_has_ex_immune_bench
    op_has_froslass = tc.op_has_froslass
    op_has_latias_ex = tc.op_has_latias_ex
    op_has_munkidori = tc.op_has_munkidori
    op_has_snorunt_bench = tc.op_has_snorunt_bench
    op_has_typhlosion = tc.op_has_typhlosion
    op_is_alakazam_deck = tc.op_is_alakazam_deck
    op_is_dragapult_dusknoir = tc.op_is_dragapult_dusknoir
    op_is_drednaw_deck = tc.op_is_drednaw_deck
    op_is_gardevoir_deck = tc.op_is_gardevoir_deck
    op_is_slowking_deck = tc.op_is_slowking_deck
    op_is_sylveon_deck = tc.op_is_sylveon_deck
    op_is_zoroark_deck = tc.op_is_zoroark_deck
    op_prize = tc.op_prize
    op_state = tc.op_state
    state = tc.state
    total_grass = tc.total_grass

    values = {}

    _fez_active_can_attack = False
    if (my_state.active and my_state.active[0] and
            my_state.active[0].id == Fezandipiti_ex):
        _fez_eff_e = len(my_state.active[0].energies) * _grass_mult()
        _fez_can_attach = (hand_counts.get(Basic_Grass_Energy, 0) >= 1
                           and not state.energyAttached)
        _fez_eff_after = _fez_eff_e + (_grass_attach_unit() if _fez_can_attach else 0)
        if _fez_eff_after >= 3:
            _fez_active_can_attack = True

    _op_active_is_crustle = (op_state.active and op_state.active[0] and
                             op_state.active[0].id in (Crustle_Grass, Crustle_Fighting))
    _tapu_can_attack = (field_counts.get(Tapu_Bulu, 0) >= 1 and ESTADO.meganium_in_play and
                        any(bp is not None and bp.id == Tapu_Bulu and len(bp.energies) >= 2
                            for bp in (my_state.bench + my_state.active)))

    # --- Boss's Orders vs Crustle: nuestro activo ex esta bloqueado por la
    # inmunidad de Crustle (le hacemos 0 dano). Buscamos en la banca rival un
    # objetivo al que SI podamos pegar (_our_effective_damage > 0). Boss's tiene
    # prioridad si a ese objetivo lo podemos noquear O no puede retirarse
    # (energia adjunta < su coste de retirada, es decir a lo sumo n-1). La unica
    # razon para NO subir Boss's es que no podamos noquearlo y ademas tenga la
    # energia suficiente para retirarse. Los objetivos inmunes (p.ej. otro
    # Crustle) devuelven 0 dano y quedan descartados automaticamente.
    crustle_gust_worth_it = False
    if (ESTADO.op_is_crustle_deck and op_has_ex_immune_active
            and my_state.active and my_state.active[0] is not None
            and my_state.active[0].id in OUR_EX_IDS):
        our_attacker = my_state.active[0]
        can_attach_grass = (hand_counts.get(Basic_Grass_Energy, 0) >= 1
                            and not state.energyAttached)
        raw_energy = len(our_attacker.energies)
        effective_energy = raw_energy * _grass_mult()
        effective_energy_after_attach = effective_energy + (
            _grass_attach_unit() if can_attach_grass else 0)
        raw_energy_after_attach = raw_energy + (1 if can_attach_grass else 0)
        for gust_target in (op_state.bench or []):
            if gust_target is None:
                continue
            base_damage = _attacker_base_damage(
                our_attacker.id, gust_target, effective_energy_after_attach,
                grass_scale=total_grass,
                teal_self_energy=raw_energy_after_attach,
                bench_count=bench_count)
            if base_damage <= 0:
                continue
            damage = _our_effective_damage(our_attacker, gust_target, base_damage,
                                           ESTADO.meganium_in_play,
                                           neutralization_zone_active)
            if damage <= 0:
                continue  # objetivo inmune / no atacable
            can_ko_target = damage >= (gust_target.hp or 0)
            target_cannot_retreat = (
                len(gust_target.energies) < RETREAT_COST.get(gust_target.id, 1))
            if can_ko_target or target_cannot_retreat:
                crustle_gust_worth_it = True
                break

        # NOTA (ciclo jul 2026, MEDIDO Y REVERTIDO): se intento extender
        # este detector con el KO ALTERNATIVO tras retirar (autopsia
        # v2.1 crustle p049 t10: Fez ex trabado delante, Dipplin de
        # banca noquea al Dwebble gusteado 80>=70; `worth_it` quedaba
        # False y Lillie's 4500 se quemaba el Supporter con el premio
        # servido), junto con el modo POR CANDIDATO en la seleccion de
        # objetivo (un can_ko evalua en ofensivo aunque el activo este
        # trabado). La linea puntual es real (fixture del paso 72), pero
        # el agregado midio NEGATIVO consistente en TRES tiradas
        # independientes vs crustle (-1.5 y -2.1 con n=1000, -1.0 con
        # n=2000; ~-1.4 agregado con n=4000/rama). Hipotesis del coste:
        # el premio del Dwebble QUEMA uno de los 2 Boss's que el endgame
        # necesita (win_via_boss_gust) y expone al cuerpo promovido al
        # contragolpe. Si se reintenta: exigir que el promovido
        # SOBREVIVA el remate rival proyectado o que el premio cierre la
        # partida, y medir contra este mismo registro.

    # Gusteo APAGAFUEGOS: el objetivo no vale por sus premios sino por la
    # MAQUINA que apaga (Froslass 850, Munkidori 750). Se anota aqui la
    # carta y se revoca mas abajo si no la podemos noquear ESTE turno --
    # `_boss_dmg_to` aun no existe en este punto del bloque.
    _bo_apagafuegos = None

    if crustle_gust_worth_it:
        values[Boss_Orders] = BOSS_PRIORITY_CRUSTLE_GUST
    elif _fez_active_can_attack:

        values[Boss_Orders] = 0
    elif (ESTADO.op_is_crustle_deck and _tapu_can_attack and not _op_active_is_crustle and
            op_has_crustle_bench):
        values[Boss_Orders] = 950

    elif (op_is_drednaw_deck and op_state.active and op_state.active[0] is not None
          and op_state.active[0].id == Drednaw):

        _has_shell_bypass_attacker = False
        _meganium_can_attack = False
        _dipplin_can_attack = False
        for _bp_dr in list(my_state.active or []) + list(my_state.bench):
            if _bp_dr is None:
                continue
            _bp_dr_eff = len(_bp_dr.energies) * _grass_mult()
            if _bp_dr.id == Meganium and _bp_dr_eff >= 4:
                _has_shell_bypass_attacker = True
                _meganium_can_attack = True
            elif _bp_dr.id == Dipplin and len(_bp_dr.energies) >= 1:
                _has_shell_bypass_attacker = True
                _dipplin_can_attack = True

        _drednaw_bench_targets = False
        for _op_bp_dr in op_state.bench:
            if _op_bp_dr is not None and _op_bp_dr.id != Drednaw:
                _drednaw_bench_targets = True
                break
        if not _has_shell_bypass_attacker and _drednaw_bench_targets:

            values[Boss_Orders] = 980
        elif _has_shell_bypass_attacker and _drednaw_bench_targets:

            if _meganium_can_attack:
                values[Boss_Orders] = 500
            else:

                values[Boss_Orders] = 850

    elif op_is_sylveon_deck and op_has_eevee_bench:

        values[Boss_Orders] = 850
    elif (op_is_sylveon_deck and op_has_ex_immune_bench and
          not op_has_ex_immune_active):

        _has_nonex_attacker_sylveon = False
        for _bp_sv in list(my_state.active or []) + list(my_state.bench):
            if _bp_sv is None:
                continue
            _bp_sv_eff = len(_bp_sv.energies) * _grass_mult()
            if _bp_sv.id == Tapu_Bulu and _bp_sv_eff >= 4:
                _has_nonex_attacker_sylveon = True
                break
            elif _bp_sv.id == Meganium and _bp_sv_eff >= 4:
                _has_nonex_attacker_sylveon = True
                break
            elif _bp_sv.id == Dipplin and len(_bp_sv.energies) >= 1:
                _has_nonex_attacker_sylveon = True
                break
            elif _bp_sv.id == Pinsir and _bp_sv_eff >= 2:
                _has_nonex_attacker_sylveon = True
                break
        if _has_nonex_attacker_sylveon:
            values[Boss_Orders] = 900
    elif op_has_froslass and not (op_state.active and op_state.active[0] and op_state.active[0].id == Froslass):
        values[Boss_Orders] = 850
        _bo_apagafuegos = Froslass
    elif budew_on_op_field and budew_op_index >= 1:
        values[Boss_Orders] = 800
    elif op_has_snorunt_bench:
        values[Boss_Orders] = 780
    elif op_has_munkidori and not (op_state.active and op_state.active[0] and op_state.active[0].id == Munkidori):
        values[Boss_Orders] = 750
        _bo_apagafuegos = Munkidori
    elif op_has_dwebble_bench:
        values[Boss_Orders] = 740
    elif op_has_eevee_bench:
        values[Boss_Orders] = 750
    # --- Mazos de LINEA EVOLUTIVA: el gusteo sin KO exige RELEVO ---------
    # Las seis ramas de abajo compartian el mismo defecto que la de Alakazam
    # (registro_002 paso 20): pagaban 690-730 por el mero hecho de que
    # hubiera una pieza de su linea en la banca. Dragapult y Ethan's ademas
    # exigian `bench_stage > active_stage`, es decir preferian subir la pieza
    # MAS evolucionada -- justo la que el rival quiere delante para
    # evolucionarla y atacar. Gardevoir/Slowking/Dusknoir/Zoroark ni siquiera
    # comparaban: bastaba con ver la pre-evolucion en su banca.
    #
    # Ninguna exigia KO. Ahora todas pasan por `_gust_releva_al_atacante`:
    # sin KO, un gusteo solo le cuesta un turno al rival si cambia un cuerpo
    # que ATACA por uno que no puede. Los gusteos que SI cobran se puntuan
    # aparte y con el KO ya comprobado: `_bo_deny_evo_target` (965),
    # `_bo_gust_key_bench` (975), `_boss_ko_ex_value` (985) y
    # `_boss_prize_rank`. El valor por mazo se conserva para no mover el
    # orden relativo entre matchups cuando el relevo SI existe.
    elif op_has_dreepy_line:
        values[Boss_Orders] = 700 if _gust_releva_al_atacante(op_state) else 0
    elif op_has_typhlosion or op_has_ethan_preevo:
        values[Boss_Orders] = 700 if _gust_releva_al_atacante(op_state) else 0
    elif op_is_gardevoir_deck and any(
        p is not None and p.id in (Ralts, Kirlia) for p in op_state.bench):
        values[Boss_Orders] = 730 if _gust_releva_al_atacante(op_state) else 0
    elif op_is_alakazam_deck:
        # vs Alakazam esta rama NO inventa valor para el gusteo.
        #
        # Antes puntuaba 700 "subir la mayor evolucion de la linea que haya
        # en banca" (`_az_best_bench_stage > _az_act_stage`), sin exigir KO.
        # Con su Fezandipiti ex pelado de activo y cuatro Abra en banca eso
        # valia 700 y le REGALABA la pre-evolucion de su UNICA linea
        # atacante -- ademas de una retirada gratis para el muro (user,
        # registro_002 paso 20, PERDIDA): el rival tenia el Kadabra en la
        # mano, evoluciono el Abra que le subimos y ataco con el.
        #
        # El unico gusteo sin KO que rinde en este matchup es el RELEVO de
        # su atacante (`_alakazam_relevo_de_atacante`), pero eso LEVANTA EL
        # VETO (`_boss_regala_linea_alakazam`), no compra prioridad: el
        # motor Night Stretcher -> Meowth ex -> Lillie's compite por el
        # MISMO Supporter del turno (la Last-Ditch busca uno para jugarlo)
        # y ese motor esta medido (registro_006 paso 51). Los gusteos que si
        # cobran se puntuan aparte y con KO exigido: `_bo_deny_alakazam_line`
        # (965), `_boss_ko_ex_value` (985) y `_boss_prize_rank`.
        values[Boss_Orders] = 0

    elif op_is_slowking_deck and any(
        p is not None and p.id == Slowpoke for p in op_state.bench):
        values[Boss_Orders] = 710 if _gust_releva_al_atacante(op_state) else 0
    elif op_is_dragapult_dusknoir and any(
        p is not None and p.id in (Duskull, Dusclops) for p in op_state.bench):
        values[Boss_Orders] = 700 if _gust_releva_al_atacante(op_state) else 0
    elif op_is_zoroark_deck and any(
        p is not None and p.id == Zorua_N for p in op_state.bench):
        values[Boss_Orders] = 690 if _gust_releva_al_atacante(op_state) else 0
    elif ESTADO.plan.target >= 1:
        values[Boss_Orders] = 650
    elif op_prize <= 2:
        values[Boss_Orders] = 500
    else:
        values[Boss_Orders] = 0

    _bo_active_attack_sufficient = False
    if (hand_counts.get(Boss_Orders, 0) >= 1 and not _fez_active_can_attack
            and op_state.active and op_state.active[0] is not None):
        _bo_atk = my_state.active[0] if my_state.active else None
        _bo_attach = (hand_counts.get(Basic_Grass_Energy, 0) >= 1
                      and not state.energyAttached)

        def _boss_dmg_to(_tgt, _wave_bench_override=None):
            if _bo_atk is None or _tgt is None:
                return 0
            _eff = len(_bo_atk.energies) * _grass_mult()
            _eff_after = _eff + (_grass_attach_unit() if _bo_attach else 0)
            _atk_e = len(_bo_atk.energies) + (1 if _bo_attach else 0)
            _d = 0
            if _bo_atk.id == Hydrapple_ex and _eff_after >= 2:
                _d = 30 + 30 * total_grass
            elif _bo_atk.id == Teal_Mask_Ogerpon_ex and _eff_after >= 3:
                _d = 30 + 30 * _atk_e
            elif _bo_atk.id == Tapu_Bulu and _eff_after >= 4:
                _d = 220
            elif _bo_atk.id == Fezandipiti_ex and _eff_after >= 3:
                _d = 100
            elif _bo_atk.id == Meganium and _eff_after >= 4:
                _d = 140
            elif _bo_atk.id == Dipplin and _eff_after >= 1:
                _wave_bench = (bench_count if _wave_bench_override is None
                               else _wave_bench_override)
                _d = 20 * _wave_bench
            elif _bo_atk.id == Pinsir and _eff_after >= 2:
                _d = 100
            if _d <= 0:
                return 0

            # Evaluador CENTRAL de dano (paso 9 plan jul 2026, auditoria
            # de call sites): la copia inline aplicaba inmunidades ex/
            # habilidad, Neutralization Zone, debilidad/resistencia (salvo
            # Fezandipiti, dano fijo) y Drednaw, pero ignoraba Sturdy/
            # Resolute Heart (FULL_HP_SURVIVE_IDS: a vida completa el dano
            # se capa a hp-10) y el Armor Tail de Farigiraf ex (inmune a
            # Basicos ex) -> `_bo_can_ko_active`/los KOs de banca del
            # gusteo podian declarar un remate FALSO sobre esos cuerpos y
            # quemar el Boss's en una "victoria" que no ocurria. La misma
            # migracion que fca07a1 hizo en ~30 sitios (P0.1).
            return _our_effective_damage(
                _bo_atk, _tgt, _d, ESTADO.meganium_in_play,
                neutralization_zone_active)

        _bo_op_active = op_state.active[0]

        _bo_active_dmg = 0 if op_active_dodge_immune else _boss_dmg_to(_bo_op_active)
        _bo_can_ko_active = (_bo_active_dmg >= (_bo_op_active.hp or 0) and _bo_active_dmg > 0)
        _bo_active_prize = prize_count_op(_bo_op_active) if _bo_can_ko_active else 0

        _bo_best_bench_prize = 0
        _bo_best_bench_dmg = 0
        for _bo_bp in op_state.bench:
            if _bo_bp is None:
                continue
            # log 86339758 paso 98: en mazo Crustle NO gusteamos Dwebble
            # (el manejador de seleccion lo veta con score=-100000), asi que
            # tampoco debe MOTIVAR jugar Boss's Orders. Sin esto el juego
            # jugaba Boss's persiguiendo un KO a Dwebble que nunca gustea, y
            # en la seleccion terminaba subiendo al activo un Pokemon MENOS
            # trabado (Mega Kangaskhan ex con energias) en vez de dejar de
            # activo al mas trabado (coste de retirada NETO mayor) y atacable.
            if ESTADO.op_is_crustle_deck and _bo_bp.id in (Dwebble_Grass, Dwebble_Fighting):
                continue
            _bo_bp_dmg = _boss_dmg_to(_bo_bp)
            if _bo_bp_dmg > _bo_best_bench_dmg:
                _bo_best_bench_dmg = _bo_bp_dmg
            if _bo_bp_dmg >= (_bo_bp.hp or 0) and _bo_bp_dmg > 0:
                _bo_bp_prize = prize_count_op(_bo_bp)
                if _bo_bp_prize > _bo_best_bench_prize:
                    _bo_best_bench_prize = _bo_bp_prize

        # --- El gusteo APAGAFUEGOS exige KO ESTE TURNO -----------------
        # (user, registros/marnie partida 1, turnos 4 y 6, PERDIDA.) Las
        # ramas de Froslass (850) y Munkidori (750) pagaban por el mero
        # hecho de que la pieza estuviera en su banca, sin mirar si la
        # podiamos matar. Con Tapu Bulu activo a 0-1 energias gusteamos el
        # Froslass DOS VECES y pasamos el turno sin atacar: quemamos el
        # Supporter del turno, le regalamos al rival una retirada gratis y
        # el Froslass siguio repartiendo 20 por ronda a cada cuerpo nuestro
        # con habilidad. Sin KO, ese gusteo es peor que no jugar nada.
        #
        # Es la misma puerta que `_gust_releva_al_atacante` impone a los
        # mazos de linea evolutiva, pero aqui el criterio es mas duro (KO,
        # no relevo): el valor de estas piezas esta en APAGARLAS, y una
        # Froslass viva en el puesto activo hace exactamente el mismo dano
        # que en la banca. Se revoca ANTES de las subidas por remate
        # (`_bo_win_via_bench` y companeras), que siguen pudiendo levantar
        # el Boss's por sus propios motivos.
        if _bo_apagafuegos is not None:
            _bo_apaga_ko = False
            for _bo_ap in (op_state.bench or []):
                if _bo_ap is None or _bo_ap.id != _bo_apagafuegos:
                    continue
                _bo_ap_dmg = _boss_dmg_to(_bo_ap)
                if _bo_ap_dmg > 0 and _bo_ap_dmg >= (_bo_ap.hp or 0):
                    _bo_apaga_ko = True
                    break
            if not _bo_apaga_ko:
                values[Boss_Orders] = 0

        _bo_dipplin_combo = False
        _OUR_BASICS_COMBO = (Chikorita, Applin, Teal_Mask_Ogerpon_ex,
                             Tapu_Bulu, Meowth_ex, Fezandipiti_ex, Pinsir)
        if (_bo_atk is not None and _bo_atk.id == Dipplin
                and (len(_bo_atk.energies) + (1 if _bo_attach else 0)) >= 1
                and bench_count < 5
                and any(hand_counts.get(_b, 0) >= 1 for _b in _OUR_BASICS_COMBO)):
            _combo_bench = bench_count + 1
            for _bo_cp in op_state.bench:
                if _bo_cp is None:
                    continue
                if (_bo_cp.id not in HIGH_PRIORITY_BENCH_TARGETS
                        and _bo_cp.id not in THREAT_PREEVO_IDS):
                    continue
                _cp_hp = _bo_cp.hp or 0
                _cur_dmg = _boss_dmg_to(_bo_cp)
                _boost_dmg = _boss_dmg_to(_bo_cp, _combo_bench)
                _cur_ko = (_cur_dmg >= _cp_hp and _cur_dmg > 0)
                _boost_ko = (_boost_dmg >= _cp_hp and _boost_dmg > 0)
                if _boost_ko and not _cur_ko:
                    _bo_dipplin_combo = True
                    break
        if _bo_dipplin_combo:
            values[Boss_Orders] = max(values.get(Boss_Orders, 0), 960)
            values['_boss_dipplin_combo'] = True

        _bo_win_via_bench = (_bo_best_bench_prize > 0
                             and _bo_best_bench_prize >= my_prize
                             and not (_bo_can_ko_active
                                      and my_prize <= prize_count_op(_bo_op_active)))
        if _bo_win_via_bench:
            values[Boss_Orders] = max(values.get(Boss_Orders, 0), 990)

            values['_boss_win_via_bench'] = True

        # Win via RETIRAR+PROMOVER (user, registro_012 p241 vs Iono, GANADA):
        # el activo actual NO noquea al objetivo de banca, pero un atacante de
        # BANCA (Hydrapple ex: Syrup Storm escala con el Grass TOTAL del campo,
        # no con su energia propia) SI lo noquea tras RETIRAR el activo, y ese
        # KO nos da los premios para GANAR. La deteccion anterior solo miraba
        # el ataque del activo ACTUAL; por eso el juego no "veia" el remate y
        # jugaba Lana's Aid en vez de Boss's Orders.
        if (not _bo_win_via_bench and my_prize >= 1):
            _bo_wr_active = my_state.active[0] if my_state.active else None
            _bo_wr_switch = hand_counts.get(1123, 0) >= 1
            _bo_wr_cost = 0 if _bo_wr_switch else (
                RETREAT_COST.get(_bo_wr_active.id, 1)
                if _bo_wr_active is not None else 1)
            if (_bo_wr_active is not None
                    and (_bo_wr_switch
                         or len(_bo_wr_active.energies) >= _bo_wr_cost)):
                _bo_wr_grass_after = max(
                    0, total_grass - _retreat_grass_units(_bo_wr_cost))
                for _bo_wr_tgt in op_state.bench:
                    if _bo_wr_tgt is None:
                        continue
                    if (ESTADO.op_is_crustle_deck
                            and _bo_wr_tgt.id in (Dwebble_Grass, Dwebble_Fighting)):
                        continue
                    if prize_count_op(_bo_wr_tgt) < my_prize:
                        continue
                    if _bench_attacker_can_ko(
                            my_state, _bo_wr_tgt, ESTADO.meganium_in_play, total_grass,
                            bench_count, _bo_wr_grass_after,
                            neutralization_zone_active):
                        _bo_win_via_bench = True
                        values[Boss_Orders] = max(values.get(Boss_Orders, 0), 990)
                        values['_boss_win_via_bench'] = True
                        break

        _bo_deny_evo_target = False
        _bo_ko_active_wins = (_bo_can_ko_active
                              and my_prize <= prize_count_op(_bo_op_active))

        _bo_cur_act = my_state.active[0] if my_state.active else None
        _bo_de_switch = hand_counts.get(1123, 0) >= 1
        _bo_de_can_retreat = False
        _bo_de_grass_after = total_grass
        if _bo_cur_act is not None:
            _bo_de_rc = RETREAT_COST.get(_bo_cur_act.id, 1)
            if _bo_de_switch or len(_bo_cur_act.energies) >= _bo_de_rc:
                _bo_de_can_retreat = True
                _bo_de_grass_after = max(
                    0, total_grass - (0 if _bo_de_switch
                                      else _retreat_grass_units(_bo_de_rc)))
        if not _bo_win_via_bench and not _bo_ko_active_wins:
            for _bo_pe in op_state.bench:
                if _bo_pe is None:
                    continue
                # log 86339758 paso 98: Dwebble esta vetado como objetivo de
                # gusteo en mazo Crustle, no puede motivar negar la linea.
                if ESTADO.op_is_crustle_deck and _bo_pe.id in (Dwebble_Grass, Dwebble_Fighting):
                    continue

                _bo_pe_is_threat = _bo_pe.id in THREAT_PREEVO_IDS
                _bo_pe_is_ex_preevo_energized = (
                    _bo_pe.id in EX_PREEVO_IDS
                    and _bo_pe.id not in NONEX_FINAL_PREEVO_IDS
                    and len(_bo_pe.energies) >= 1
                    and _bo_can_ko_active
                    and prize_count_op(_bo_op_active) == prize_count_op(_bo_pe))
                # Negar una linea EX desde la banca AUNQUE la pre-evolucion NO
                # tenga energia: cuando el activo rival es un muro inofensivo
                # sin energia (noquearlo no corta ninguna amenaza) y en la
                # banca hay una pre-evolucion de una linea ex (p.ej. Abra ->
                # Alakazam ex, Ralts -> Gardevoir ex) que podemos noquear,
                # conviene gustearla con Boss's para impedir que evolucione a
                # un atacante de 2 premios, aunque el premio inmediato sea el
                # mismo que noquear al muro.
                _bo_pe_is_ex_line_vs_wall = (
                    _bo_pe.id in EX_PREEVO_IDS
                    and _bo_pe.id not in NONEX_FINAL_PREEVO_IDS
                    and _bo_can_ko_active
                    and len(_bo_op_active.energies) == 0
                    and prize_count_op(_bo_op_active) <= 1
                    and _bo_op_active.id not in EX_PREEVO_IDS
                    and _bo_op_active.id not in THREAT_PREEVO_IDS
                    and _bo_op_active.id not in KEY_BENCH_ATTACKER_IDS)
                # Negar una linea EX cuando el activo rival es OTRA pre-evolucion
                # de la MISMA cadena pero un muro DESNUDO (0 energia) y en la
                # banca hay una pre-evolucion ex ENERGIZADA (mas cerca de su
                # atacante). `_bo_pe_is_ex_line_vs_wall` no cubre este caso porque
                # exige que el activo NO este en EX_PREEVO_IDS, pero en la linea
                # Marnie (Impidimp -> Morgrem -> Grimmsnarl ex) tanto Impidimp
                # como Morgrem estan en EX_PREEVO_IDS. Noquear al Impidimp
                # desnudo del activo (reemplazable, 1 premio) rinde lo mismo que
                # gustear+noquear al Morgrem energizado (1 premio) PERO deja que
                # Morgrem evolucione a Grimmsnarl ex; gustear el Morgrem corta la
                # linea del atacante principal (user, log 86402439 paso 100).
                _bo_pe_is_energized_preevo_vs_bare_wall = (
                    _bo_pe_is_ex_preevo_energized
                    and len(_bo_op_active.energies) == 0)
                # Negar una linea EX cuando el activo rival esta FUERA de esa
                # linea (noquearlo no la toca), aunque TENGA energia. Generaliza
                # `_bo_pe_is_energized_preevo_vs_bare_wall` (que exige activo con
                # 0 energia): con premios IGUALES, gustear+noquear la pre-evo ex
                # energizada de banca (Morgrem -> Grimmsnarl ex) corta al atacante
                # principal, mientras que noquear un activo AJENO a la linea
                # (Munkidori, un soporte de 1 premio) rinde el mismo premio pero
                # deja viva la evolucion. El activo debe ser un objetivo AJENO:
                # ni pre-evo ex, ni pre-evo amenaza, ni atacante clave de banca
                # (si el activo YA fuese de esa clase, noquearlo ya aportaria, y
                # la comparacion de premios de abajo decide). La igualdad de
                # premios ya viene garantizada por `_bo_pe_is_ex_preevo_energized`
                # (prize_count activo == prize_count pre-evo). (user, registro_004
                # paso 47 vs Marnie: activo Munkidori 1e + Morgrem energizado en
                # banca; el juego jugaba Dawn/estadio en vez de Boss's al Morgrem.)
                _bo_pe_is_energized_preevo_off_line = (
                    _bo_pe_is_ex_preevo_energized
                    and _bo_op_active.id not in EX_PREEVO_IDS
                    and _bo_op_active.id not in THREAT_PREEVO_IDS
                    and _bo_op_active.id not in KEY_BENCH_ATTACKER_IDS)
                # ESCALON DE BANCA (user, registro_008 paso 136 vs Marnie's
                # Grimmsnarl ex, PERDIDA): simetrico exacto del VETO DE ETAPA
                # de mas abajo. Dentro de una linea Basico -> Fase 1 -> Fase 2
                # se noquea SIEMPRE la etapa MAS ALTA alcanzable; cuando la
                # que esta mas arriba es la de BANCA, esa etapa solo se
                # alcanza GUSTEANDOLA. Activo Marnie's Impidimp (Basico) y
                # Morgrem (Fase 1, 2 energias) en banca: los dos rinden 1
                # premio y el Hydrapple ex noquea a cualquiera, pero noquear
                # al Impidimp deja que el Morgrem evolucione a Marnie's
                # Grimmsnarl ex (Fase 2, 320 PV, 2 premios, Punk Up busca 5
                # energias); gustear el Morgrem obliga al rival a rehacer los
                # DOS escalones. Las tres excepciones de arriba no cubrian
                # este tablero: `vs_bare_wall` exige activo con 0 energia (el
                # Impidimp tenia 1) y `off_line` exige un activo AJENO a la
                # linea (el Impidimp es su propia pre-evo).
                # Deck-agnostico por partida doble: la ETAPA sale del dato de
                # carta (`_supera_en_evolucion`) y el "vale el Boss's" sale de
                # que la cadena termine en un ex (`_preevo_de_linea_ex`), no
                # de listas por mazo. La igualdad de premios se exige aqui
                # explicitamente porque este predicado no pasa por
                # `_bo_pe_is_ex_preevo_energized` (la energia de la pre-evo es
                # irrelevante cuando lo que corta la linea es la ETAPA).
                _bo_pe_outranks_active = (
                    _bo_can_ko_active
                    and _supera_en_evolucion(_bo_pe, _bo_op_active)
                    and prize_count_op(_bo_op_active) == prize_count_op(_bo_pe)
                    and _preevo_de_linea_ex(_bo_pe.id))
                if not (_bo_pe_is_threat or _bo_pe_is_ex_preevo_energized
                        or _bo_pe_is_ex_line_vs_wall
                        or _bo_pe_outranks_active):
                    continue
                _bo_pe_dmg = _boss_dmg_to(_bo_pe)
                _bo_pe_ko = (_bo_pe_dmg >= (_bo_pe.hp or 0) and _bo_pe_dmg > 0)

                if not _bo_pe_ko and _bo_de_can_retreat:
                    _bo_pe_ko = _bench_attacker_can_ko(
                        my_state, _bo_pe, ESTADO.meganium_in_play, total_grass,
                        bench_count, _bo_de_grass_after,
                        neutralization_zone_active)
                if _bo_pe_ko:
                    # Con una PRE-EVO AMENAZA (Duraludon->Archaludon ex) que
                    # podemos noquear, solo se prefiere noquear el activo si
                    # este rinde ESTRICTAMENTE mas premios; con premios IGUALES
                    # gustear la pre-evo es mejor (mismo premio y REMUEVE al
                    # atacante del mazo). Para los demas objetivos se mantiene
                    # el criterio >= (user, registro_007 p78 vs Archaludon:
                    # Cinderace no-ex activo = 1 premio, igual que Duraludon;
                    # el juego noqueaba al Cinderace en vez de gustear Duraludon).
                    # EXCEPCION (user, registro_006 paso 75 vs Archaludon): si
                    # el ACTIVO rival es TAMBIEN una pre-evo AMENAZA (Duraludon)
                    # que podemos noquear e igual o MAS desarrollada (>= energia)
                    # que la pre-evo de banca, NOQUEAR el activo ya remueve una
                    # amenaza de la MISMA clase por el MISMO premio, y ademas es
                    # el cuerpo mas peligroso (mas energia + herramientas como
                    # Hero's Cape). Gustear una copia de banca mas debil malgasta
                    # el Boss's y deja viva la Duraludon grande: preferimos
                    # atacar el activo (dominates=True aunque los premios sean
                    # iguales).
                    _bo_active_is_threat_ko = (
                        _bo_op_active.id in THREAT_PREEVO_IDS
                        and len(_bo_op_active.energies) >= len(_bo_pe.energies))
                    _bo_active_prize_dominates = (
                        (prize_count_op(_bo_op_active) > prize_count_op(_bo_pe)
                         or _bo_active_is_threat_ko)
                        if _bo_pe_is_threat
                        else prize_count_op(_bo_op_active) >= prize_count_op(_bo_pe))
                    # VETO DE ETAPA (user, registro_008 paso 93 vs Cynthia's
                    # Garchomp ex, GANADA con error): el ACTIVO rival es un
                    # eslabon MAS EVOLUCIONADO de la MISMA linea que la
                    # pre-evo de banca (activo Cynthia's Gabite Fase 1
                    # DESNUDO, banca Cynthia's Gible Basico con 1 energia).
                    # Noquear el Gabite cobra el mismo premio y corta la
                    # linea UN ESCALON MAS ARRIBA -- ademas es GRATIS, no
                    # gasta el Boss's ni el Supporter del turno. Este veto
                    # pisa a las tres excepciones: aqui disparaba
                    # `_energized_preevo_vs_bare_wall` (pensada para el caso
                    # INVERSO de la linea Marnie: activo Impidimp BASICO
                    # desnudo, banca Morgrem FASE 1 energizada), que solo
                    # miraba la energia del activo y no su ETAPA.
                    _bo_active_outranks_pe = (
                        _supera_en_evolucion(_bo_op_active, _bo_pe)
                        and prize_count_op(_bo_op_active) >= prize_count_op(_bo_pe))
                    if (_bo_can_ko_active
                            and (_bo_active_outranks_pe
                                 or (_bo_active_prize_dominates
                                     and not _bo_pe_is_ex_line_vs_wall
                                     and not _bo_pe_is_energized_preevo_vs_bare_wall
                                     and not _bo_pe_is_energized_preevo_off_line
                                     and not _bo_pe_outranks_active))):
                        continue
                    _bo_deny_evo_target = True
                    break
        if _bo_deny_evo_target:
            values[Boss_Orders] = max(values.get(Boss_Orders, 0), 965)
            values['_boss_deny_evo'] = True

        # --- Cortar la linea Alakazam gusteando su pre-evo de banca -------
        # Regla (user, registro 010, paso 64 vs Alakazam, GANADA): cuando el
        # activo rival NO pertenece a la linea Alakazam (Abra 741 -> Kadabra
        # 742 -> Alakazam 743) -- p.ej. un Dunsparce que hace de muro -- y en
        # la BANCA hay una pre-evolucion de esa linea que nuestro activo puede
        # noquear, la prioridad es GUSTEARLA con Boss's Orders y noquearla para
        # cortar el desarrollo del atacante Psiquico. Atacar al muro del activo
        # no toca la linea; gustear+noquear la pre-evo rinde el mismo premio
        # PERO frena a Alakazam. Prioridad de objetivo Kadabra > Abra > Alakazam
        # (la elige el manejador de seleccion, ~L2300).
        # NOTA: esto NO contradice [[boss-no-gustear-preevo-linea-no-ex]]: alli
        # el activo rival ERA de la linea Alakazam (atacarlo ya la golpea), asi
        # que gustear una copia de banca es inutil. Aqui el activo esta FUERA de
        # la linea, por eso la condicion exige `_bo_op_active.id not in` la
        # cadena. Como Abra/Kadabra son NONEX_FINAL_PREEVO (Alakazam es 1 premio)
        # el deny-evo generico los ignora; esta regla los cubre solo en el caso
        # "activo fuera de linea".
        _bo_deny_alakazam_line = False
        if (op_is_alakazam_deck
                and _bo_op_active.id not in (Abra, Kadabra, Alakazam_ex)):
            for _bo_al in op_state.bench:
                if _bo_al is None or _bo_al.id not in (Abra, Kadabra, Alakazam_ex):
                    continue
                _bo_al_dmg = _boss_dmg_to(_bo_al)
                _bo_al_ko = (_bo_al_dmg >= (_bo_al.hp or 0) and _bo_al_dmg > 0)
                if not _bo_al_ko and _bo_de_can_retreat:
                    _bo_al_ko = _bench_attacker_can_ko(
                        my_state, _bo_al, ESTADO.meganium_in_play, total_grass,
                        bench_count, _bo_de_grass_after,
                        neutralization_zone_active)
                if _bo_al_ko:
                    _bo_deny_alakazam_line = True
                    break
        if _bo_deny_alakazam_line:
            values[Boss_Orders] = max(values.get(Boss_Orders, 0), 965)
            values['_boss_deny_alakazam_line'] = True

        # --- Cazar al Pokemon clave del mazo en banca ---------------------
        # Si el activo rival NO es un Pokemon clave (p.ej. Hop's Snorlax sin
        # energia) pero en la banca hay un atacante clave del mazo (Hop's
        # Trevenant / Phantump) que podemos noquear con nuestro activo, la
        # jugada correcta es gustear ese atacante en vez de conformarnos con
        # noquear al activo inofensivo (mismo valor de premios). Marcamos la
        # bandera para NO dejar que la regla "atacar es suficiente" anule el
        # Boss's Orders mas abajo. El objetivo concreto lo eligen los ajustes de _AJUSTES_GUST_OFENSIVO.
        _bo_gust_key_bench = False
        if (_bo_op_active.id not in KEY_BENCH_ATTACKER_IDS
                and not _bo_win_via_bench and not _bo_deny_evo_target
                and not _bo_ko_active_wins):
            for _bo_kp in op_state.bench:
                if _bo_kp is None or _bo_kp.id not in KEY_BENCH_ATTACKER_IDS:
                    continue
                _bo_kp_dmg = _boss_dmg_to(_bo_kp)
                _bo_kp_ko = (_bo_kp_dmg >= (_bo_kp.hp or 0) and _bo_kp_dmg > 0)
                if not _bo_kp_ko and _bo_de_can_retreat:
                    _bo_kp_ko = _bench_attacker_can_ko(
                        my_state, _bo_kp, ESTADO.meganium_in_play, total_grass,
                        bench_count, _bo_de_grass_after,
                        neutralization_zone_active)
                if _bo_kp_ko:
                    _bo_gust_key_bench = True
                    break
        if _bo_gust_key_bench:
            values[Boss_Orders] = max(values.get(Boss_Orders, 0), 975)
            values['_boss_gust_key_bench'] = True

        if op_active_dodge_immune and not _bo_win_via_bench:
            if _bo_best_bench_prize > 0:
                values[Boss_Orders] = max(values.get(Boss_Orders, 0), 985)
                values['_boss_dodge_redirect'] = True
            elif _bo_best_bench_dmg > 0:
                values[Boss_Orders] = max(values.get(Boss_Orders, 0), 970)
                values['_boss_dodge_redirect'] = True

        _bo_bench_prize_beats_active = False
        if _bo_best_bench_prize > _bo_active_prize and _bo_best_bench_prize > 0:

            _bo_active_prize_val = prize_count_op(_bo_op_active)
            _bo_trade_down = (not _bo_can_ko_active and _bo_active_dmg > 0
                              and _bo_active_prize_val > _bo_best_bench_prize)
            if not _bo_trade_down:
                _bo_bench_prize_beats_active = True
                _bo_prize_diff = _bo_best_bench_prize - _bo_active_prize
                values[Boss_Orders] = max(values.get(Boss_Orders, 0),
                                          960 + 10 * _bo_prize_diff)

        if _bo_can_ko_active and len(_bo_op_active.energies) == 0:
            for _bo_bp in op_state.bench:
                if (_bo_bp is not None and _bo_bp.id == _bo_op_active.id
                        and len(_bo_bp.energies) >= 1):
                    _bo_mirror_dmg = _boss_dmg_to(_bo_bp)
                    if _bo_mirror_dmg >= (_bo_bp.hp or 0) and _bo_mirror_dmg > 0:
                        values[Boss_Orders] = max(values.get(Boss_Orders, 0), 955)
                        break

        # --- Boss's Orders DEFENSIVO (evitar el KO letal) ----------------
        # Si nuestro activo va a ser noqueado el proximo turno (dano
        # estimado del rival >= nuestros HP) y NO podemos noquear al activo
        # rival ni ganar por banca, la jugada correcta puede ser gustear un
        # Pokemon inofensivo de la banca rival: uno que NO pueda atacar el
        # proximo turno (ni con una energia extra) y que NO pueda retirarse
        # (energia < coste de retirada), de modo que el rival pierda su
        # ataque letal. Todo el resto del scoring de Boss's es ofensivo, asi
        # que sin esto la regla "atacar es suficiente" (mas abajo) lo anula
        # y se pierde la partida.
        # REGLA (usuario): si nuestro ACTIVO es un Basico o una Fase 1
        # (p.ej. Applin, Dipplin, Bayleef) que sera derrotado el proximo
        # turno, jugar Boss's Orders SOLO si podemos subir un Pokemon de la
        # banca rival que NO pueda derrotar a nuestro activo. La eleccion
        # concreta del objetivo la hace el manejador de seleccion (reglas
        # actuales de Boss's Orders).
        _bo_defensive_gust = False
        _bo_active_basic_or_s1 = (
            _bo_atk is not None
            and len(getattr(_bo_atk, 'preEvolution', []) or []) <= 1)
        _bo_my_active_data = card_table.get(_bo_atk.id) if _bo_atk is not None else None
        _bo_my_active_weak = getattr(_bo_my_active_data, 'weakness', None) if _bo_my_active_data else None
        if (_bo_atk is not None and _bo_active_basic_or_s1
                and estimated_op_damage > 0
                and estimated_op_damage >= (_bo_atk.hp or 0)
                and not _bo_can_ko_active and not _bo_win_via_bench
                and not _bo_deny_evo_target and not _bo_gust_key_bench
                and not _bo_dipplin_combo):
            for _bo_dg in op_state.bench:
                if _bo_dg is None:
                    continue
                _bo_dg_e = len(_bo_dg.energies)
                _bo_dg_rc = RETREAT_COST.get(_bo_dg.id, 1)
                if _bo_dg_e >= _bo_dg_rc:
                    continue  # podria retirarse y volver a poner al atacante letal
                _bo_dg_d = card_table.get(_bo_dg.id)
                # dano MAXIMO que este Pokemon de banca le haria a NUESTRO
                # activo el proximo turno (asumiendo que le adjuntan 1 energia).
                _bo_dg_dmg_vs_us = 0
                if _bo_dg_d and getattr(_bo_dg_d, 'attacks', None):
                    _bo_dg_avail = _bo_dg_e + 1
                    for _bo_dg_atk in _bo_dg_d.attacks:
                        _bo_dg_dmg = getattr(_bo_dg_atk, 'damage', None)
                        if _bo_dg_dmg is None or _bo_dg_dmg <= 0:
                            continue
                        _bo_dg_cost = getattr(_bo_dg_atk, 'cost', None)
                        _bo_dg_need = 0
                        if _bo_dg_cost is not None:
                            try:
                                _bo_dg_need = len(_bo_dg_cost)
                            except TypeError:
                                try:
                                    _bo_dg_need = int(_bo_dg_cost)
                                except (TypeError, ValueError):
                                    _bo_dg_need = 0
                        if _bo_dg_need <= _bo_dg_avail:
                            _bo_dg_dmg_vs_us = max(_bo_dg_dmg_vs_us, _bo_dg_dmg)
                # aplicar debilidad de NUESTRO activo al tipo del Pokemon de banca
                if (_bo_my_active_weak is not None and _bo_dg_d is not None
                        and _bo_dg_dmg_vs_us > 0
                        and _bo_my_active_weak == getattr(_bo_dg_d, 'energyType', None)):
                    _bo_dg_dmg_vs_us *= 2
                # objetivo VALIDO = este Pokemon NO puede derrotar a nuestro activo
                if _bo_dg_dmg_vs_us < (_bo_atk.hp or 0):
                    _bo_defensive_gust = True
                    break
        if _bo_defensive_gust:
            values[Boss_Orders] = max(values.get(Boss_Orders, 0), 940)
            values['_boss_defensive_gust'] = True

        if (_bo_can_ko_active and not _bo_win_via_bench and not _bo_deny_evo_target
                and not _bo_dipplin_combo and not _bo_gust_key_bench
                and not _bo_deny_alakazam_line):
            _bo_active_prize_now = prize_count_op(_bo_op_active)
            if my_prize <= _bo_active_prize_now:
                values[Boss_Orders] = 0
            elif (_bo_active_prize_now >= _bo_best_bench_prize
                    and len(_bo_op_active.energies) > 0):
                values[Boss_Orders] = 0
            elif (_bo_op_active.id == Crustle_Grass
                    and _bo_best_bench_prize <= _bo_active_prize_now
                    and len(_bo_op_active.energies) > 0):

                values[Boss_Orders] = 0

        # "ATACAR AL ACTIVO ES SUFICIENTE" -- pero un CHIP no es un premio
        # (user, registro_020 paso 122 vs Crustle, PERDIDA). Alli el activo
        # rival era un Crustle de 150 y Meganium le hacia 140: el remanente
        # (10) caia bajo el umbral de 100 y esta regla anulaba el Boss's...
        # que valia 970 porque en la BANCA habia otro Crustle a **30 PV** con
        # dos energias, un premio servido para el mismo Solar Beam. El chip
        # no cobra nada y el rival simplemente rota el cuerpo herido a la
        # banca (es lo que hizo). Por eso la regla cede -- como ya cedia ante
        # deny_evo / key_bench / defensivo -- cuando el gusteo cobra un premio
        # que el ataque al activo NO cobra (`_bo_bench_prize_beats_active`,
        # exactamente el mismo predicado que le puso el 960+ arriba).
        if (_bo_active_dmg > 0 and not _bo_win_via_bench and not _bo_deny_evo_target
                and not _bo_dipplin_combo and not _bo_gust_key_bench
                and not _bo_defensive_gust and not _bo_deny_alakazam_line
                and not _bo_bench_prize_beats_active):
            _bo_active_remaining = (_bo_op_active.hp or 0) - _bo_active_dmg
            if _bo_can_ko_active or _bo_active_remaining <= 100:
                values[Boss_Orders] = 0
                _bo_active_attack_sufficient = True

                values['_active_attack_sufficient'] = True

    if _active_cant_attack_this_turn and hand_counts.get(Boss_Orders, 0) >= 1:

        _boss_ko_ex_value = 0
        _boss_ko_energy_value = 0

        _our_attackers_info = []
        for _idx_ba, _our_p in enumerate(list(my_state.active or []) + list(my_state.bench)):
            if _our_p is None:
                continue

            if _idx_ba != 0 and not can_switch:
                continue
            _our_dmg = 0
            _our_eff_e = len(_our_p.energies) * _grass_mult()

            _can_attach_ba = (hand_counts.get(Basic_Grass_Energy, 0) >= 1
                              and not state.energyAttached)
            _our_eff_after = _our_eff_e + (_grass_attach_unit() if _can_attach_ba else 0)

            if _our_p.id == Hydrapple_ex and _our_eff_after >= 2:
                _our_dmg = 30 + 30 * total_grass
            elif _our_p.id == Dipplin and _our_eff_after >= 1:
                _our_dmg = 20 * bench_count
            elif _our_p.id == Teal_Mask_Ogerpon_ex and _our_eff_after >= 3:
                _our_dmg = 30 + 30 * (len(_our_p.energies) + (1 if _can_attach_ba else 0))
            elif _our_p.id == Tapu_Bulu and _our_eff_after >= 4:
                _our_dmg = 220
            elif _our_p.id == Fezandipiti_ex and _our_eff_after >= 3:
                _our_dmg = 100
            elif _our_p.id == Meganium and _our_eff_after >= 4:
                _our_dmg = 140
            elif _our_p.id == Pinsir and _our_eff_after >= 2:
                _our_dmg = 100
            elif _our_p.id == Bayleef and _our_eff_after >= 2:
                _our_dmg = 60
            elif _our_p.id == Chikorita and _our_eff_after >= 1:
                _our_dmg = 30

            if _our_dmg > 0:
                _our_attackers_info.append((_our_p, _our_dmg))

        for _op_bp in op_state.bench:
            if _op_bp is None:
                continue
            _op_data_b = card_table.get(_op_bp.id)
            _is_ex_target = (_op_data_b and getattr(_op_data_b, 'ex', False))
            _is_stage2_target = (_op_data_b and getattr(_op_data_b, 'stage2', False))
            _op_bench_energy = len(_op_bp.energies)

            for _atk_p, _atk_dmg in _our_attackers_info:
                _eff_dmg = _atk_dmg

                if _atk_p.id != Fezandipiti_ex and _op_data_b:
                    if _op_data_b.weakness == EnergyType.GRASS:
                        _eff_dmg *= 2
                    elif _op_data_b.resistance == EnergyType.GRASS:
                        _eff_dmg -= 30

                _atk_is_ex = (_atk_p.id in OUR_EX_IDS)
                if _op_bp.id in EX_IMMUNE_IDS and _atk_is_ex:
                    _eff_dmg = 0

                if _op_bp.id in ABILITY_IMMUNE_IDS and _atk_p.id in OUR_ABILITY_IDS:
                    _eff_dmg = 0

                if _op_bp.id == Drednaw and _eff_dmg >= 200:
                    _eff_dmg = 0

                if _eff_dmg >= _op_bp.hp:

                    if _is_ex_target or _is_stage2_target:
                        _boss_ko_ex_value = max(_boss_ko_ex_value, 985)
                    elif _op_bench_energy >= 1:
                        _boss_ko_energy_value = max(_boss_ko_energy_value, 970)

        if _boss_ko_ex_value > 0:
            values[Boss_Orders] = max(values.get(Boss_Orders, 0), _boss_ko_ex_value)
        elif _boss_ko_energy_value > 0:
            values[Boss_Orders] = max(values.get(Boss_Orders, 0), _boss_ko_energy_value)
        else:

            _op_active_pkmn = op_state.active[0] if op_state.active else None
            _op_active_stuck = False
            if _op_active_pkmn is not None:
                _op_active_rc = RETREAT_COST.get(_op_active_pkmn.id, 0)
                _op_active_energy_cnt = len(_op_active_pkmn.energies)
                _op_active_diff = _op_active_rc - _op_active_energy_cnt
                if _op_active_diff >= 2:
                    _op_active_stuck = True

            if _op_active_stuck:

                if values.get(Boss_Orders, 0) <= 0:
                    values[Boss_Orders] = 0
            else:

                _stall_threshold = 1 if _op_active_rc == 0 else 2
                _best_stall_diff = 0
                _has_stall_target = False
                for _bps in op_state.bench:
                    if _bps is not None:
                        _rc = RETREAT_COST.get(_bps.id, 0)
                        _bps_energy = len(_bps.energies)
                        _diff = _rc - _bps_energy
                        if _diff >= _stall_threshold:

                            if op_has_latias_ex:
                                _cd = card_table.get(_bps.id)
                                if (_cd and not getattr(_cd, 'stage1', False)
                                        and not getattr(_cd, 'stage2', False)):
                                    continue
                            if _diff > _best_stall_diff:
                                _best_stall_diff = _diff
                                _has_stall_target = True

                if _has_stall_target:

                    if _best_stall_diff >= 2:
                        stall_val = 975
                    else:
                        stall_val = 900
                    values[Boss_Orders] = max(values.get(Boss_Orders, 0), stall_val)
                elif values.get(Boss_Orders, 0) <= 0:
                    values[Boss_Orders] = 0

        # REGLA (usuario, log 86507974 paso 141): SOLO vs mazo Crustle. Si
        # nuestro activo NO puede atacar este turno, jugar Boss's Orders por
        # motivo defensivo unicamente cuando el ACTIVO rival sea una amenaza
        # inminente: puede atacarnos el proximo turno o solo le falta 1
        # energia para hacerlo (energia_actual + 1 >= coste minimo de su
        # ataque con dano). Si necesita 2 o mas energias (p.ej. Mega
        # Kangaskhan ex con 1 energia y ataque de coste 3) no hay ataque que
        # neutralizar, asi que no gastamos el supporter. No aplica si ya hay
        # una razon ofensiva real (KO a un objetivo de banca) ni en el
        # gusteo por inmunidad de Crustle.
        if (ESTADO.op_is_crustle_deck and not crustle_gust_worth_it
                and _boss_ko_ex_value <= 0 and _boss_ko_energy_value <= 0):
            _boc_active = op_state.active[0] if op_state.active else None
            _boc_imminent = False
            if _boc_active is not None:
                _boc_energy = len(_boc_active.energies)
                _boc_min_cost = None
                _boc_data = card_table.get(_boc_active.id)
                if _boc_data and getattr(_boc_data, 'attacks', None):
                    for _boc_atk in _boc_data.attacks:
                        _boc_dmg = getattr(_boc_atk, 'damage', None)
                        if _boc_dmg is None or _boc_dmg <= 0:
                            continue
                        _boc_cost = getattr(_boc_atk, 'cost', None)
                        _boc_need = 0
                        if _boc_cost is not None:
                            try:
                                _boc_need = len(_boc_cost)
                            except TypeError:
                                try:
                                    _boc_need = int(_boc_cost)
                                except (TypeError, ValueError):
                                    _boc_need = 0
                        if _boc_min_cost is None or _boc_need < _boc_min_cost:
                            _boc_min_cost = _boc_need
                if (_boc_min_cost is not None
                        and _boc_energy + 1 >= _boc_min_cost):
                    _boc_imminent = True
            if not _boc_imminent:
                values[Boss_Orders] = 0

    if op_has_ability_immune_active and ESTADO.plan.target >= 1:

        _attacker_ready = (ESTADO.plan.attacker >= 0 and not ESTADO.plan.energy)
        _attacker_ready_with_attach = (ESTADO.plan.attacker >= 0 and ESTADO.plan.energy and
                                       hand_counts.get(Basic_Grass_Energy, 0) >= 1 and
                                       not state.energyAttached)
        if _attacker_ready or _attacker_ready_with_attach:
            values[Boss_Orders] = max(values.get(Boss_Orders, 0), 980)
    elif op_has_ability_immune_active and len(op_state.bench) >= 1:

        _has_non_ability_attacker_ready = False
        _ATK_REQS_BOSS = {
            Tapu_Bulu: 4, Dipplin: 1, Bayleef: 2, Chikorita: 1, Applin: 1,
            Pinsir: 2,
        }
        for _bp in (list(my_state.active or []) + list(my_state.bench)):
            if _bp is not None and _bp.id not in OUR_ABILITY_IDS:
                _req = _ATK_REQS_BOSS.get(_bp.id, 999)
                _eff = len(_bp.energies) * _grass_mult()

                if _eff >= _req:
                    _has_non_ability_attacker_ready = True
                    break
                elif (hand_counts.get(Basic_Grass_Energy, 0) >= 1 and
                      not state.energyAttached):
                    _eff_after = _eff + _grass_attach_unit()
                    if _eff_after >= _req:
                        _has_non_ability_attacker_ready = True
                        break
        if _has_non_ability_attacker_ready:
            values[Boss_Orders] = max(values.get(Boss_Orders, 0), 960)

    if not ESTADO.meganium_in_play and not has_hydrapple:
        values[Dawn] = 900
    elif not ESTADO.meganium_in_play:
        values[Dawn] = 800
    elif not has_hydrapple:
        values[Dawn] = 700
    else:
        values[Dawn] = 200

    hand_size = len(my_state.hand) if my_state.hand else 0

    _remaining_plays = 0
    if hand_counts.get(Basic_Grass_Energy, 0) >= 1 and not state.energyAttached:
        _remaining_plays += 1
    if bench_count < 5:
        for _pid in (Chikorita, Applin, Teal_Mask_Ogerpon_ex):
            if hand_counts.get(_pid, 0) >= 1:
                _remaining_plays += 1
    if hand_counts.get(Meganium, 0) >= 1 and field_counts.get(Bayleef, 0) >= 1:
        _remaining_plays += 1
    if hand_counts.get(Bayleef, 0) >= 1 and field_counts.get(Chikorita, 0) >= 1:
        _remaining_plays += 1
    if hand_counts.get(Hydrapple_ex, 0) >= 1 and field_counts.get(Dipplin, 0) >= 1:
        _remaining_plays += 1
    if hand_counts.get(Dipplin, 0) >= 1 and field_counts.get(Applin, 0) >= 1:
        _remaining_plays += 1

    if my_prize == 6:
        values[Lillie_Determination] = 750
        if hand_size <= 3:
            values[Lillie_Determination] = 800
    elif hand_size <= 2:
        values[Lillie_Determination] = 800
    elif hand_size <= 3:
        values[Lillie_Determination] = 700
    elif _remaining_plays <= 1:
        values[Lillie_Determination] = 650
    elif hand_size <= 5:
        values[Lillie_Determination] = 550
    else:
        values[Lillie_Determination] = 400

    if op_is_alakazam_deck and hand_size >= 4:
        values[Lillie_Determination] = min(values[Lillie_Determination], 450)

        if _remaining_plays >= 2:
            values[Lillie_Determination] = min(values[Lillie_Determination], 300)

    if (hand_counts.get(Dawn, 0) >= 1 and
            hand_counts.get(Lillie_Determination, 0) >= 1 and
            not (ESTADO.meganium_in_play and has_hydrapple)):
        if ESTADO.forest_in_play:

            values[Dawn] = max(values.get(Dawn, 0),
                               values.get(Lillie_Determination, 0) + 50)
        else:

            values[Lillie_Determination] = max(values.get(Lillie_Determination, 0),
                                               values.get(Dawn, 0) + 50)

    lana_val = 0
    discard_basic_pokemon = []
    discard_basic_energy = 0
    for c in my_state.discard:
        if c.id == Basic_Grass_Energy:
            discard_basic_energy += 1
        # Lana's Aid solo recupera Pokemon SIN Regla (Rule Box). Los Pokemon ex
        # (Teal Mask Ogerpon ex, Meowth ex, Fezandipiti ex) TIENEN Regla y NO
        # son recuperables por Lana's Aid, asi que no deben contar como objetivo
        # ni inflar su valor. Contarlos hacia que Lana's Aid se valorara alto
        # (p.ej. 700 por un Meowth ex en el descarte) y ese valor fantasma
        # bloqueaba la linea Night Stretcher -> Meowth ex -> Lillie's al elevar
        # `_best_supp_in_hand_val` (registro 006, paso 51 vs Alakazam).
        elif c.id in (Chikorita, Applin, Tapu_Bulu, Pinsir):
            discard_basic_pokemon.append(c.id)

    total_recoverable = len(discard_basic_pokemon) + discard_basic_energy
    if total_recoverable >= 1:
        lana_val = LANA_PLAY_BASE_RECUPERABLE
        if bench_count <= 1:
            lana_val += 400
        elif bench_count <= 2:
            lana_val += 200
        if Chikorita in discard_basic_pokemon and not ESTADO.meganium_in_play:
            if field_counts[Chikorita] + field_counts[Bayleef] + field_counts[Meganium] == 0:
                lana_val += 350
        if Applin in discard_basic_pokemon and not has_hydrapple:
            if field_counts[Applin] + field_counts[Dipplin] + field_counts[Hydrapple_ex] == 0:
                lana_val += 300
        if ESTADO.forest_in_play and any(pid in discard_basic_pokemon for pid in (Chikorita, Applin)):
            lana_val += 200
        if total_recoverable >= 3:
            lana_val += 150

        if ESTADO.op_is_crustle_deck:
            _tapu_in_play_lana = field_counts.get(Tapu_Bulu, 0) >= 1
            if Tapu_Bulu in discard_basic_pokemon and not _tapu_in_play_lana:
                lana_val += 350
            if (Applin in discard_basic_pokemon and
                    field_counts.get(Applin, 0) + field_counts.get(Dipplin, 0) == 0):
                lana_val += 200

    # Valor SOLO de los bonos de necesidad (banca corta, linea caida,
    # Forest, >=3 recuperables, matchup): se congela ANTES del suelo de 950
    # por energia, que es una razon distinta. `> LANA_PLAY_BASE_RECUPERABLE`
    # es "algun bono se cobro", es decir, la mesa PIDE lo que hay ahi
    # abajo -- y no solo "hay una carta recuperable".
    _lana_val_bonos = lana_val

    # ¿La ENERGIA del descarte habilita un ataque? Antes esto solo sabia
    # mirar a Hydrapple ex (activo, o de banca con un cambio disponible), y
    # por eso callaba con un Tapu Bulu activo a una Planta de disparar Wood
    # Hammer (registro_018 paso 118 vs Crustle, PERDIDA). Ahora lo resuelve
    # `_plan_de_planta`, que recorre TODOS los `MAIN_ATTACKERS` en juego con
    # `ATTACK_ENERGY_REQ` y cuenta las vias de adjunte reales (manual, Teal
    # Dance, Ripening Charge). Es la MISMA lectura que decide luego que se
    # levanta del descarte, asi que jugar la carta y usarla no pueden
    # discrepar.
    _lana_plan_play = _plan_de_planta(
        my_state, state, field_counts, hand_counts,
        puede_cambiar=(can_switch or has_switch_card),
        habilidades_apagadas=meowth_ability_lock)
    _lana_energy_enables_attack = (
        discard_basic_energy >= 1
        and _lana_plan_play.desbloquea_hoy
        and _lana_plan_play.cartas_para_atacar <= discard_basic_energy)
    if _lana_energy_enables_attack:

        lana_val = max(lana_val, 950)

    # LO QUE SE LEVANTA TIENE QUE PODER JUGARSE (user, episodio 88904232
    # paso 140 vs Marnie, GANADA -- la fuga no costo la partida, pero es
    # fuga igual). Mesa: Hydrapple ex activo, banca LLENA (5/5),
    # descarte SIN Plantas y con un unico Applin. Lana's Aid solo podia
    # levantar ese Applin -- un Basico que con la banca llena no entra de
    # ninguna forma, y de una linea que ya estaba evolucionada en el activo.
    # El agente gasto el Supporter del turno para meter en la mano una carta
    # MUERTA. La causa: el bloque de arriba cobra su base de 300 por
    # "total_recoverable >= 1", que solo cuenta cartas del descarte y no
    # mira ni el hueco de banca ni las vias de adjunte.
    #
    # La regla del user: Lana's se juega SOLO si de verdad hace falta algo
    # que se pueda poner en juego ESTE turno -- Pokemon jugables o Energia
    # adjuntable. Se aplica en dos escalones, con la MISMA lectura de mesa
    # que decide luego que se levanta (`_pokemon_injugable` / `_plan_de_planta`):
    #
    #   1. VETO si nada de lo recuperable puede entrar en juego hoy: ningun
    #      Pokemon jugable (`_pokemon_injugable`: banca llena mata a un
    #      Basico, y una evolucion solo vive si su pre-evolucion esta EN
    #      JUEGO) y ninguna via de adjunte viva para una Planta.
    #   2. TECHO si lo jugable no hace FALTA: Energia que NADIE pide (todos
    #      los atacantes en juego ya llegan a `ATTACK_ENERGY_REQ`, o la mano
    #      ya tiene mas Plantas de las que caben hoy), o un Pokemon que cabe
    #      en la banca pero que ningun bono de necesidad reclama (la linea
    #      ya esta en juego, la banca no esta corta...). Es techo y no veto
    #      porque la carta sigue siendo jugable: solo cede el turno a
    #      cualquier otro Supporter util.
    _lana_pk_jugable = any(
        not _pokemon_injugable(_pid, field_counts, bench_count,
                               bench_max)
        for _pid in discard_basic_pokemon)
    _lana_pk_necesario = (_lana_pk_jugable
                          and _lana_val_bonos > LANA_PLAY_BASE_RECUPERABLE)
    _lana_energia_jugable = (discard_basic_energy >= 1
                             and _lana_plan_play.slots_hoy >= 1)
    _lana_energia_util = (_lana_energia_jugable
                          and _lana_plan_play.nuevas_utiles_hoy >= 1
                          and _lana_plan_play.demanda >= 1)
    if not (_lana_pk_jugable or _lana_energia_jugable):
        lana_val = 0
    elif not (_lana_pk_necesario or _lana_energia_util
              or _lana_energy_enables_attack):
        lana_val = min(lana_val, LANA_PLAY_SIN_DEMANDA)

    values[Lanas_Aid] = lana_val
    # Se expone para la capa de scoring PLAY: distingue el caso en que Lana's
    # recupera energia que HABILITA un ataque (unica razon para priorizarla
    # sobre Lillie's cuando no tenemos atacante) del resto.
    values['_lana_enables_attack'] = _lana_energy_enables_attack

    if state.turn == 2 and not ESTADO.we_go_first:
        values[Lillie_Determination] = 1000
        for _sid in (Boss_Orders, Dawn, Lanas_Aid):
            if _sid in values:
                values[_sid] = min(values[_sid], 200)

    if state.turn <= 2 and hand_size >= 10:
        values[Lillie_Determination] = -1

    if (ESTADO.ko_last_turn and
            hand_counts.get(Dawn, 0) >= 1 and
            hand_counts.get(Lillie_Determination, 0) == 0 and
            hand_counts.get(Meowth_ex, 0) == 0 and
            hand_counts.get(Ultra_Ball, 0) == 0 and
            field_counts.get(Fezandipiti_ex, 0) == 0 and
            ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(Fezandipiti_ex, {}).get(ESTADO_MAZO, 0) > 0 and
            bench_count < 5):
        values[Dawn] = 1100

        for _sid in (Boss_Orders, Lanas_Aid):
            if _sid in values:
                values[_sid] = min(values[_sid], 200)

    if values.get(Boss_Orders, 0) > 0 and op_state.active and op_state.active[0] is not None:
        _bo_active_pkmn = op_state.active[0]
        _bo_has_distinct_target = False
        for _bo_bench_pkmn in op_state.bench:
            if _bo_bench_pkmn is None:
                continue
            if (_bo_bench_pkmn.id != _bo_active_pkmn.id or
                    len(_bo_bench_pkmn.energies) != len(_bo_active_pkmn.energies)):
                _bo_has_distinct_target = True
                break
        if not _bo_has_distinct_target:
            values[Boss_Orders] = 0

    # Reserva del Supporter vs Crustle: sin un objetivo relevante en la banca
    # rival, Boss's no se quema. `crustle_gust_worth_it` es justamente la
    # comprobacion de que SI lo hay (nuestro ex esta bloqueado por el muro y
    # en la banca hay un cuerpo al que danamos y noqueamos o trabamos), asi
    # que no puede pisarla: con la banca rival llena de Dwebble este corte
    # anulaba el gusteo de 990 recien calculado y el turno moria sin premios
    # (user, episodio 88620891 paso 78 vs Crustle, PERDIDA).
    if (ESTADO.op_is_crustle_deck and values.get(Boss_Orders, 0) > 0
            and not crustle_gust_worth_it):
        _cru_act = op_state.active[0] if op_state.active else None
        _cru_act_ok = (_cru_act is not None and
                       _cru_act.id in (Dwebble_Grass, Crustle_Grass,
                                       Dwebble_Fighting, Crustle_Fighting))
        _cru_has_nondwebble_bench = any(
            bp is not None and bp.id not in (Dwebble_Grass, Dwebble_Fighting)
            for bp in op_state.bench)
        if not _cru_act_ok or not _cru_has_nondwebble_bench:
            values[Boss_Orders] = 0

    # Regla (user, vs Alakazam): con la BANCA LLENA solo jugamos Dawn si
    # REALMENTE nos falta una evolucion (Fase 1 / Fase 2) para un Pokemon
    # que YA tenemos en juego (banca o activo) y que podriamos evolucionar.
    # Dawn busca hasta 3 Pokemon del mazo a la mano (adelgaza el mazo); con
    # banca llena no podemos bajar basicos nuevos, asi que si NO
    # necesitamos ninguna evolucion, jugar Dawn solo roba / vacia el mazo de
    # mas y arriesga PERDER por deckout (no quedan cartas que robar). En ese
    # caso NO se juega (valor 0). Solo se considera "necesaria" una
    # evolucion si tenemos la pre-evolucion en juego, NO tenemos su
    # evolucion en la mano y esa evolucion sigue disponible en el mazo (Dawn
    # puede traerla).
    #
    # GENERALIZADA A TODOS LOS MATCHUPS (user, episodio 88904232 paso 140
    # vs Marnie): es la MISMA puerta de utilidad que la de Lana's Aid
    # de mas arriba -- lo que el Supporter trae a la mano tiene que poder
    # ponerse en juego --, y no tenia nada de especifico de Alakazam. En ese
    # paso, con Lana's ya vetada, el Supporter del turno se iba en un Dawn
    # que con la banca 5/5 y las dos lineas ya evolucionadas (Meganium +
    # Hydrapple ex en juego) solo podia traer cartas inertes. Los pares
    # pre->evo salen ahora de `EVO_LINES` en vez de una tabla fija.
    if bench_count >= bench_max:
        _dawn_need_evo = False
        for _dw_linea in EVO_LINES:
            for _dw_pre, _dw_evo in zip(_dw_linea, _dw_linea[1:]):
                if (field_counts.get(_dw_pre, 0) >= 1
                        and hand_counts.get(_dw_evo, 0) < 1
                        and ESTADO.CARTAS_ACTIVAS_EN_MAZO.get(
                            _dw_evo, {}).get(ESTADO_MAZO, 0) > 0):
                    _dawn_need_evo = True
                    break
            if _dawn_need_evo:
                break
        if not _dawn_need_evo:
            values[Dawn] = 0

    return values


__all__ = ['evaluate_supporters']
