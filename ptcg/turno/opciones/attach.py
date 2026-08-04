"""Puntuacion de las opciones `ATTACH`.

Rama `o.type == OptionType.ATTACH` de la cadena de `agent()`, extraida VERBATIM.
Desempaqueta del contexto los 26 campos que lee y devuelve los
2 que reasigna; los demas quedan como estaban, igual que antes.
"""

from cg.api import AreaType
from ptcg.calculo.carta import get_card
from ptcg.calculo.energia import _can_attack_eff, _grass_attach_unit
from ptcg.cartas.ids import Applin, Basic_Grass_Energy, Chikorita, Dipplin, Fezandipiti_ex, Hydrapple_ex, Meowth_ex, Pinsir, RETREAT_COST, SCORE_VETO, Tapu_Bulu, Teal_Mask_Ogerpon_ex
from ptcg.cartas.puntuacion import MAIN_ATTACKERS
from ptcg.estado.agente import ESTADO


def puntuar(tc, o, score):
    """Devuelve el puntaje de `o`. Puede devolver `_SALTAR`."""
    _attach_cede_a_teal_dance = tc._attach_cede_a_teal_dance
    _attach_enable_retreat_attack = tc._attach_enable_retreat_attack
    _attach_enable_retreat_ko = tc._attach_enable_retreat_ko
    _bcs_playable_in_hand = tc._bcs_playable_in_hand
    _carga_activo_habilita_ataque = tc._carga_activo_habilita_ataque
    _carga_activo_remata = tc._carga_activo_remata
    _gust_2prize_via_boss = tc._gust_2prize_via_boss
    _lucario_sac_pivot = tc._lucario_sac_pivot
    _tapu_future_charge = tc._tapu_future_charge
    _tapu_sac_enable_retreat = tc._tapu_sac_enable_retreat
    _teal_dance_ko_pivot = tc._teal_dance_ko_pivot
    _teal_dance_slots = tc._teal_dance_slots
    _win_via_boss_gust = tc._win_via_boss_gust
    card = tc.card
    energy_score = tc.energy_score
    hand_counts = tc.hand_counts
    has_ogerpon = tc.has_ogerpon
    itchy_pollen_active = tc.itchy_pollen_active
    my_index = tc.my_index
    my_state = tc.my_state
    obs = tc.obs
    pokemon = tc.pokemon
    scores = tc.scores
    state = tc.state

    try:
        card = get_card(obs, AreaType.HAND, o.index, my_index)
        pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
        if card is not None and pokemon is not None:
            score = energy_score(pokemon, o.inPlayArea == AreaType.ACTIVE)
            if o.inPlayArea == AreaType.ACTIVE:
        
                # vs Crustle, Tapu Bulu ACTIVO es nuestro atacante PRINCIPAL
                # (no-ex; el unico que daña al muro inmune a ex): tiene SIEMPRE
                # la primera prioridad de carga, desde el primer turno. El veto
                # generico de "no cargar el activo inicial" (Ogerpon/Tapu en
                # nuestro primer turno, pensado para no desperdiciar energia
                # sobrecargando el atacante de arranque) NO debe degradarlo:
                # sin carga, Tapu nunca llega a sus 4 energias para Wood Hammer
                # (user, registro_002 paso 17 vs Crustle, PERDIDA: el agente
                # cargaba un Applin de banca en vez del Tapu Bulu activo). Solo
                # se exime a Tapu Bulu; Ogerpon ex sigue vetado (no daña al muro).
                _ft_veto_ids = ((Teal_Mask_Ogerpon_ex,) if ESTADO.op_is_crustle_deck
                                else (Teal_Mask_Ogerpon_ex, Tapu_Bulu))
                if (((state.turn == 1 and ESTADO.we_go_first) or
                        (state.turn == 2 and not ESTADO.we_go_first))
                        and my_state.active and my_state.active[0] is not None
                        and my_state.active[0].id in _ft_veto_ids
                        # ...salvo que esa carga REMATE hoy (anti-DONK): el
                        # veto de primer turno existe para no desperdiciar
                        # energia, no para renunciar a un KO.
                        and not _carga_activo_remata):
                    if _lucario_sac_pivot:
                        # Cargar el Ogerpon ex activo: al retirarlo despues,
                        # conservara energia en la banca (paga el coste de
                        # retirada y deja un atacante cargado a salvo).
                        score = 8500
                    else:
                        score = SCORE_VETO
                elif _tapu_sac_enable_retreat:
                    # Adjuntar energia al ex activo (2 premios) para alcanzar
                    # su coste de retirada y poder pivotar a un Tapu Bulu ya
                    # cargado que noquea al activo rival (user, log 86029588
                    # turno 16 paso 148, vs Alakazam/Dunsparce). El coste de
                    # retirada de Fezandipiti ex es 1, asi que UNA Planta ya
                    # habilita la retirada este mismo turno -> subir a Tapu y
                    # rematar. Antes se puntuaba 8000, pero un Dipplin de
                    # BANCA a 0 energia puntua 8150 (8000+150) y GANABA el
                    # desempate, desperdiciando la energia en un no-atacante y
                    # rompiendo la linea de KO. Se sube por encima de cualquier
                    # desarrollo de banca (Dipplin/Applin/Tapu no letales) para
                    # que el adjunte al activo gane; sigue por debajo de una
                    # carga LETAL de este turno (41000/42000).
                    score = 24000
                elif _attach_enable_retreat_ko:
                    # Adjunte que habilita retirada + KO de banca (user,
                    # registro_034 paso 141 vs Terrakion): es una linea
                    # LETAL de este turno, asi que puntua en la banda de
                    # las cargas letales (41000): sobre Teal Dance
                    # (31500-31600) y las cargas de banca (~30000), bajo
                    # el remate directo del activo (42000). El resto de la
                    # cadena (RETREAT via plan con can_switch, promocion,
                    # ataque) ya la resuelve la maquinaria existente una
                    # vez la retirada es legal.
                    score = 41000
                elif _attach_enable_retreat_attack:
                    # Misma linea sin KO (user, log 88162794 turnos 11/13 vs
                    # Archaludon ex): el activo no puede atacar ni retirarse y
                    # el atacante de banca solo hace CHIP. La Planta va al
                    # ACTIVO para pagar la retirada: 80-140 de dano valen mas
                    # que cerrar el turno sin atacar. Banda 31200 (la que citan
                    # las ramas de Teal Dance como "el adjunte manual"): por
                    # encima de cualquier carga de banca (<=31150, incluida la
                    # de Ripening al mejor atacante) y por debajo de todo lo
                    # que habilita un KO este turno (31300+, 31500, 41000).
                    score = 31200
                elif (ESTADO.plan.attacker == 0 and ESTADO.plan.energy
                        # La banda de `_carga_activo_habilita_ataque` (31300)
                        # esta calibrada contra el motor UB (31450) y Teal
                        # Dance (31500): el bonus de desempate la cruzaria.
                        and not _carga_activo_habilita_ataque):
                    score += 200
        
                elif (ESTADO.plan.attacker >= 1 and has_ogerpon and score > 31000
                        and not ESTADO.op_is_crustle_deck and not ESTADO.op_is_cornerstone_deck
                        and not (_win_via_boss_gust or _gust_2prize_via_boss)
                        # ...ni cuando esta carga es la que hace atacar al
                        # activo HOY (remate o unico ataque del turno).
                        and not _carga_activo_remata
                        and not _carga_activo_habilita_ataque):
                    # NO degradar el adjunte al activo si hay una jugada
                    # GANADORA / de 2 premios via Boss's que se apoya en cargar
                    # el activo (user, registro_012 paso 227 vs Iono): Myriad
                    # Leaf Shower de Ogerpon cuenta la energia de AMBOS activos,
                    # asi que cargar el activo + gustear un Bellibolt ex
                    # energizado lo noquea (2 premios). El remate ganador
                    # (energy_score=42000) debe prevalecer sobre este downgrade
                    # (pensado para no sobrecargar el activo cuando ataca un
                    # cuerpo de banca), que si no borraria la linea de KO.
        
                    _attach_active_pkmn = my_state.active[0] if my_state.active else None
                    _attach_needs_for_retreat = False
                    if _attach_active_pkmn is not None:
                        _attach_rc = RETREAT_COST.get(_attach_active_pkmn.id, 1)
                        _attach_curr_e = len(_attach_active_pkmn.energies)
                        if _attach_curr_e < _attach_rc:
                            _attach_needs_for_retreat = True
                    if not _attach_needs_for_retreat:
                        score = 7500
            else:
                if ESTADO.plan.attacker == 1 + o.inPlayIndex and ESTADO.plan.energy:
                    score += 200
        
                _our_first_turn_attach = ((state.turn == 1 and ESTADO.we_go_first) or
                                          (state.turn == 2 and not ESTADO.we_go_first))
                _active_blocked_ft = (
                    my_state.active and my_state.active[0] is not None
                    and my_state.active[0].id in (Teal_Mask_Ogerpon_ex, Tapu_Bulu))
                if _our_first_turn_attach and _active_blocked_ft and len(pokemon.energies) < 1:
                    _BENCH_ATTACKER_PRIORITY = {
                        Hydrapple_ex: 900,
                        Dipplin: 850,
                        Teal_Mask_Ogerpon_ex: 800,
                        Tapu_Bulu: 750,
                        Pinsir: 650,
                        # Priorizamos la linea de Hydrapple ex (Applin ->
                        # Dipplin -> Hydrapple ex), que acelera energia y
                        # carga a Tapu Bulu en un turno, por encima de la
                        # linea de Meganium (Chikorita).
                        Applin: 500,
                        Chikorita: 400,
                        Fezandipiti_ex: 200,
                    }
                    _bench_prio = _BENCH_ATTACKER_PRIORITY.get(pokemon.id)
                    if _bench_prio is not None:
                        score = max(score, 8000 + _bench_prio)
        
                # Nunca cargar manualmente energia a un Meowth ex de BANCA: es un
                # no-atacante y la energia se desperdicia. El unico uso valido de
                # Meowth ex para el adjunte manual es en el ACTIVO, para pagar su
                # retirada cuando haga falta (lo gestiona la rama AreaType.ACTIVE
                # via energy_score). Se veta SIEMPRE, sin importar el turno ni si
                # es el unico objetivo de banca disponible.
                if pokemon.id == Meowth_ex:
                    score = SCORE_VETO
        
            if _bcs_playable_in_hand and not itchy_pollen_active and score > 9000 \
                    and not (_tapu_future_charge
                             and o.inPlayArea != AreaType.ACTIVE
                             and pokemon is not None
                             and pokemon.id == Tapu_Bulu) \
                    and not (_carga_activo_remata
                             and o.inPlayArea == AreaType.ACTIVE):
                # Bug Catching Set primero... salvo que la carga al ACTIVO
                # remate este turno: el KO no espera a una busqueda.
                score = 9000
        
            if _teal_dance_ko_pivot and hand_counts.get(Basic_Grass_Energy, 0) <= 1:
                # Pivote Teal Dance (log 85802744 turno 16): con una
                # sola Energia Planta en mano, RESERVARLA para Teal Dance en
                # el activo (adjunta + ROBA y habilita la retirada de coste 1
                # para subir al atacante no-ex que noquea al muro Crustle). Se
                # veta cualquier adjunte manual para que no robe la Planta ni
                # supere a Teal Dance por el tier ENERGY del orden de jugada.
                score = SCORE_VETO
        
            # Teal Dance PRECEDE al adjunte manual (user, registro_004 paso
            # 28, vs Mega Starmie): si vamos a cargar energia MANUALMENTE a
            # un Teal Mask Ogerpon ex que TODAVIA puede usar Teal Dance este
            # turno (su opcion ABILITY sigue disponible en este mismo slot),
            # se veta el adjunte manual. Teal Dance adjunta la Planta Y ROBA
            # una carta, asi que se juega PRIMERO; tras usarla la habilidad
            # desaparece y, si aun se quiere una 2a energia, el adjunte
            # manual se puntua con normalidad en el paso siguiente. Esto
            # corrige el orden impuesto por el tier ENERGY (que hacia ganar
            # al adjunte manual pese a que Teal Dance puntua mas alto).
            if (score > 0
                    and pokemon is not None
                    and pokemon.id == Teal_Mask_Ogerpon_ex
                    and (o.inPlayArea, o.inPlayIndex) in _teal_dance_slots):
                score = SCORE_VETO
        
            # GENERALIZACION de la precedencia anterior (user, registro_002
            # paso 20, vs Marnie): Teal Dance no solo precede al adjunte
            # sobre el PROPIO Ogerpon. Mientras quede una Teal Dance por
            # usar este turno, un adjunte manual que sea mero DESARROLLO
            # (el objetivo NO queda listo para atacar con esa energia) cede
            # ante ella. Teal Dance gasta la misma Planta de la mano, pero
            # ademas ROBA una carta y NO consume el adjunte manual del
            # turno: es estrictamente mejor que gastar el adjunte en un
            # cuerpo que no va a atacar.
            #
            # En el registro, el Ogerpon ex ACTIVO ya habia usado su Teal
            # Dance ese turno, asi que el adjunte al activo quedaba vetado
            # por la regla de primer turno y la Teal Dance del Ogerpon ex de
            # BANCA caia a la banda degradada (7500); el unico objetivo que
            # quedaba, un Chikorita de banca, ganaba con 8400 (base 8000 de
            # energy_score + boost de desarrollo) y desperdiciaba la unica
            # Planta en un cuerpo que con 1 energia no es atacante.
            #
            # Se CAPA (no se veta) por debajo de la banda degradada de Teal
            # Dance (7500) en vez de anular la jugada: si la habilidad
            # estuviera vetada por otra via, el adjunte sigue siendo jugable
            # y no se cuelga el turno. "Listo para atacar" exige ATACANTE
            # REAL (MAIN_ATTACKERS): Chikorita/Applin/Bayleef figuran en
            # ATTACK_ENERGY_REQ por su ataque de chip, pero no son atacantes.
            #
            # No basta con capar el score: el ORDEN DE JUGADA manda por
            # tier y el adjunte manual vive en _TIER_ENERGY, mientras que
            # una Teal Dance degradada (7500) se queda en tier 0 (su
            # promocion exige >= 29000, guard que NO se toca: evita que una
            # Teal Dance degradada aplaste por tier a Ripening Charge). Por
            # eso el indice se marca aqui y mas abajo se deja el adjunte en
            # tier 0, para que dentro del mismo tier decida el score
            # (Teal Dance 7500 > adjunte capado 7000).
            # Solo la BANDA DE DESARROLLO (< 9000: la base 8000 de
            # energy_score y el boost de banca del primer turno, max 8900).
            # Los adjuntes con override estrategico puntuan muy por encima
            # (8500 sacrificio Lucario, 24000 pivote Tapu, 31000+ cargas,
            # 41000 el que habilita retirada hacia un KO de banca) y NO son
            # desarrollo: ceder ahi romperia lineas letales de este turno.
            if (pokemon is not None and _teal_dance_slots
                    and 0 < score < 9000
                    and not (pokemon.id in MAIN_ATTACKERS
                             and _can_attack_eff(
                                 pokemon.id,
                                 len(pokemon.energies)
                                 + _grass_attach_unit()))):
                score = min(score, 7000)
                _attach_cede_a_teal_dance.add(len(scores))
        return score
    finally:
        tc.card = card
        tc.pokemon = pokemon


__all__ = ['puntuar']
