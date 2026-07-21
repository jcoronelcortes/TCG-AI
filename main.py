

import os
import sys
from collections import defaultdict
from dataclasses import dataclass
from typing import NamedTuple

from cg.api import AreaType, CardType, EnergyType, Observation, SelectContext, OptionType, Card, Pokemon, SpecialConditionType, LogType, all_card_data, to_observation_class

# =============================================================================
# CONVENCIONES DEL AGENTE (leer antes de tocar puntuaciones o energia)
# -----------------------------------------------------------------------------
# ENERGIA:
#   * `len(pokemon.energies)` YA es la energia EFECTIVA. La observacion aplica
#     Wild Growth de Meganium duplicando cada energia basica de Planta FISICA,
#     asi que NUNCA hay que volver a multiplicar por 2. Por eso `_grass_mult()`
#     devuelve 1. Comparar `len(energies)` directamente con ATTACK_ENERGY_REQ.
#   * `_grass_attach_unit()` = energia EFECTIVA que aporta adjuntar UNA Planta
#     basica: 2 si Meganium esta en juego, 1 si no.
#   * Las energias del RIVAL en nuestra observacion NO estan dobladas.
#
# PUNTUACION:
#   * `agent(obs)` puntua cada opcion; se juega la de mayor valor.
#   * Requisitos de energia para atacar: ATTACK_ENERGY_REQ (fuente unica).
#   * Dano base de nuestros atacantes: _attacker_base_damage(...) (fuente unica).
#     Debilidad/resistencia/inmunidad se aplican aparte en _our_effective_damage.
#
# TIPOS DE OPCION (OptionType, valores numericos en el log):
#   7 = PLAY (jugar carta de la mano)   13 = ATTACK
#   12 = PASS                           14 = END TURN        3 = seleccion objetivo
# =============================================================================


file_path = "deck.csv"
if not os.path.exists(file_path):
    file_path = "/kaggle_simulations/agent/" + file_path
with open(file_path, "r") as file:
    csv = file.read().split("\n")
my_deck = []
for i in range(60):
    my_deck.append(int(csv[i]))

all_card = all_card_data()
card_table = {c.cardId: c for c in all_card}

RETREAT_COST = {
    21:1, 22:3, 23:4, 24:2, 25:2, 26:1, 27:1, 28:1, 29:1, 30:3,
    31:1, 32:1, 33:1, 34:1, 35:1, 36:1, 37:4, 38:1, 39:1, 40:1,
    41:3, 42:1, 43:1, 44:3, 46:2, 47:1, 48:2, 49:3, 50:1, 51:2,
    52:1, 53:2, 54:3, 55:3, 56:1, 57:1, 58:3, 59:1, 60:1, 61:2,
    62:2, 63:3, 64:1, 66:3, 67:2, 68:1, 69:1, 70:2, 71:1, 72:2,
    73:1, 74:1, 75:1, 76:2, 77:2, 78:2, 79:2, 80:2, 81:1, 82:2,
    83:2, 84:2, 85:1, 86:2, 87:2, 88:1, 89:1, 90:2, 91:4, 92:1,
    93:2, 94:1, 95:1, 96:1, 97:1, 98:2, 99:1, 100:1, 101:1, 102:1,
    103:1, 104:1, 105:1, 106:1, 107:2, 108:1, 109:1, 110:2, 111:3, 112:1,
    113:2, 114:2, 115:3, 116:2, 117:1, 118:4, 119:1, 120:1, 121:1, 122:1,
    123:1, 124:2, 125:4, 126:1, 127:1, 128:1, 129:2, 130:1, 131:1, 132:2,
    133:3, 134:1, 135:4, 136:1, 137:1, 138:3, 139:1, 140:1, 141:1, 142:1,
    143:1, 144:2, 145:1, 146:2, 147:3, 148:1, 149:1, 150:3, 151:1, 152:1,
    154:2, 155:3, 156:3, 157:2, 158:3, 159:2, 160:1, 161:1, 162:2, 163:3,
    164:1, 165:2, 166:3, 167:3, 168:1, 169:2, 170:2, 171:3, 172:1, 173:1,
    174:1, 175:2, 176:2, 177:1, 178:1, 179:3, 180:1, 181:1, 182:2, 184:2,
    185:1, 186:2, 187:1, 188:1, 189:1, 190:2, 191:2, 192:2, 193:3, 194:1,
    195:2, 196:3, 197:1, 198:2, 199:1, 200:3, 201:3, 202:1, 203:3, 204:2,
    205:2, 206:1, 207:2, 208:2, 209:1, 210:1, 211:1, 212:1, 213:1, 214:1,
    215:1, 216:1, 217:1, 218:2, 219:2, 220:1, 221:1, 222:1, 223:4, 224:2,
    225:3, 226:2, 227:1, 228:2, 229:3, 230:1, 231:1, 232:4, 233:2, 234:2,
    236:2, 237:1, 238:1, 239:2, 240:1, 241:2, 242:1, 243:1, 245:1, 246:1,
    247:1, 248:2, 249:1, 250:2, 251:4, 252:1, 253:3, 254:1, 255:2, 256:2,
    257:2, 258:3, 259:3, 260:1, 261:1, 262:2, 263:3, 264:4, 265:1, 267:1,
    268:2, 269:2, 270:1, 271:1, 272:1, 273:1, 274:1, 275:2, 276:3, 277:1,
    280:1, 281:2, 282:3, 283:4, 284:1, 285:1, 286:1, 287:2, 288:2, 289:3,
    290:3, 291:1, 292:1, 293:2, 294:1, 295:3, 296:3, 297:1, 298:2, 299:2,
    300:2, 301:2, 302:2, 303:2, 304:4, 305:1, 306:3, 307:1, 308:1, 309:1,
    310:2, 311:1, 312:2, 313:1, 314:1, 315:2, 316:2, 317:1, 318:2, 319:1,
    320:2, 321:1, 322:2, 323:1, 324:1, 325:2, 326:2, 327:2, 328:1, 330:1,
    331:1, 332:3, 333:1, 335:1, 336:2, 337:2, 338:2, 339:1, 340:1, 341:1,
    342:1, 343:1, 344:2, 345:3, 346:1, 347:3, 348:3, 349:1, 350:1, 351:1,
    352:1, 353:1, 354:2, 355:2, 356:3, 357:2, 358:1, 359:1, 360:1, 361:1,
    362:1, 363:4, 364:1, 365:1, 366:2, 367:1, 368:1, 369:4, 370:1, 371:2,
    372:4, 374:1, 375:1, 376:1, 377:1, 378:1, 379:1, 380:1, 382:3, 383:3,
    384:1, 385:2, 386:1, 387:1, 388:2, 389:3, 390:2, 391:1, 392:2, 393:2,
    394:1, 395:2, 396:1, 397:1, 398:1, 399:1, 400:1, 401:2, 402:1, 403:1,
    404:2, 405:2, 406:3, 407:2, 408:1, 409:2, 410:1, 411:2, 412:2, 413:2,
    414:1, 415:2, 416:1, 417:1, 418:3, 419:4, 420:2, 421:1, 422:1, 423:3,
    424:4, 425:1, 426:1, 427:2, 428:2, 429:2, 430:2, 431:3, 432:2, 435:2,
    436:2, 437:1, 438:2, 439:2, 440:1, 441:2, 442:3, 443:3, 444:3, 445:1,
    446:1, 447:3, 448:1, 449:2, 450:1, 451:2, 452:3, 453:1, 454:2, 455:3,
    456:1, 457:1, 458:1, 459:3, 460:4, 461:1, 462:2, 463:1, 464:1, 465:2,
    466:1, 467:2, 468:1, 469:1, 470:1, 471:2, 472:2, 473:1, 474:1, 475:1,
    476:1, 478:1, 479:1, 480:1, 481:2, 482:1, 483:1, 484:1, 485:1, 486:1,
    487:1, 488:1, 489:2, 490:1, 491:2, 492:2, 493:1, 494:1, 495:2, 496:1,
    497:1, 498:1, 499:1, 500:1, 501:2, 502:3, 503:3, 504:3, 505:1, 506:2,
    507:3, 508:1, 509:2, 512:2, 513:3, 514:1, 515:2, 516:1, 517:2, 518:1,
    519:1, 520:1, 521:1, 522:1, 523:3, 524:4, 525:1, 526:1, 527:3, 528:2,
    529:3, 530:3, 531:2, 532:2, 533:3, 534:2, 535:3, 536:3, 537:3, 538:2,
    539:2, 540:3, 541:1, 542:1, 543:3, 544:1, 545:2, 546:2, 547:2, 548:2,
    549:2, 550:3, 551:1, 554:1, 555:1, 556:1, 557:1, 558:2, 559:1, 560:1,
    562:1, 563:2, 564:3, 565:1, 566:1, 567:1, 568:3, 569:4, 570:1, 571:1,
    572:2, 573:2, 574:1, 575:1, 576:2, 577:1, 578:1, 579:1, 580:1, 581:2,
    582:2, 583:2, 584:1, 585:1, 586:1, 587:1, 588:2, 589:1, 590:1, 591:1,
    592:2, 593:2, 594:1, 595:1, 596:2, 597:3, 598:3, 599:2, 600:3, 601:3,
    602:1, 603:1, 604:1, 605:1, 606:1, 607:3, 608:1, 609:1, 610:1, 611:2,
    612:2, 613:3, 614:1, 615:1, 616:2, 617:3, 618:3, 619:2, 620:3, 621:1,
    622:2, 623:3, 624:1, 625:2, 626:1, 627:1, 628:1, 629:1, 630:3, 631:2,
    632:1, 633:1, 634:1, 635:1, 636:2, 637:2, 638:1, 639:1, 640:2, 641:3,
    642:1, 643:1, 644:1, 645:2, 646:1, 647:1, 648:2, 650:2, 651:3, 652:4,
    653:1, 654:2, 655:1, 656:1, 657:2, 658:2, 659:1, 660:1, 661:2, 662:4,
    663:2, 664:1, 665:1, 667:2, 668:2, 669:1, 670:1, 671:4, 673:2, 674:3,
    675:1, 676:1, 677:2, 678:2, 679:1, 680:1, 681:1, 682:2, 683:2, 684:3,
    685:4, 686:3, 687:2, 688:1, 690:1, 691:1, 692:1, 693:1, 694:4, 695:2,
    696:2, 697:1, 698:2, 699:2, 700:2, 701:1, 702:1, 703:2, 704:1, 705:1,
    706:2, 707:4, 708:1, 709:2, 710:2, 711:1, 712:1, 714:2, 715:2, 716:2,
    717:2, 718:3, 719:1, 720:1, 721:3, 722:3, 723:4, 724:2, 725:2, 726:1,
    727:1, 728:1, 729:1, 730:2, 731:1, 732:1, 733:2, 734:3, 735:1, 736:1,
    738:1, 739:1, 740:1, 741:1, 742:1, 743:1, 744:1, 745:1, 746:1, 747:2,
    749:1, 750:2, 751:1, 752:3, 753:3, 754:1, 755:1, 756:3, 757:1, 758:1,
    759:1, 760:2, 761:3, 762:1, 763:2, 764:1, 765:1, 766:1, 767:1, 768:1,
    769:1, 770:1, 771:1, 772:2, 773:1, 774:1, 775:1, 776:1, 777:2, 778:1,
    779:1, 780:2, 781:2, 782:1, 783:1, 784:2, 785:2, 786:1, 787:1, 788:2,
    789:2, 790:2, 791:1, 792:2, 793:3, 794:2, 795:1, 796:2, 797:2, 798:2,
    799:2, 800:2, 801:3, 802:4, 803:2, 804:1, 805:2, 806:1, 807:1, 808:1,
    809:1, 810:1, 811:1, 812:1, 813:1, 814:1, 815:1, 816:2, 817:1, 818:2,
    819:2, 820:1, 821:1, 822:1, 823:1, 824:1, 825:1, 826:1, 827:1, 829:1,
    830:2, 831:2, 832:3, 833:1, 834:2, 835:2, 836:2, 837:3, 838:1, 839:2,
    840:2, 841:1, 842:2, 843:1, 844:1, 845:1, 846:1, 847:1, 848:1, 849:1,
    850:1, 851:3, 852:1, 853:3, 854:1, 855:3, 856:3, 857:3, 858:1, 859:1,
    860:1, 861:1, 862:1, 863:1, 864:2, 865:1, 866:2, 867:2, 868:2, 869:2,
    870:1, 871:1, 872:1, 873:1, 874:3, 875:1, 876:1, 877:1, 878:2, 879:2,
    880:1, 881:1, 882:1, 883:1, 884:1, 885:2, 886:1, 887:3, 888:3, 889:4,
    890:3, 891:1, 892:1, 893:2, 894:2, 895:2, 896:2, 897:3, 898:1, 899:1,
    900:1, 901:3, 902:2, 903:2, 904:2, 905:1, 906:2, 907:1, 909:1, 910:1,
    911:2, 912:1, 913:2, 914:3, 915:2, 916:1, 917:1, 918:2, 919:2, 920:3,
    921:3, 922:1, 923:1, 924:1, 925:1, 926:1, 927:1, 928:1, 929:2, 930:2,
    931:3, 932:4, 933:2, 934:2, 935:2, 936:3, 937:1, 938:2, 939:3, 940:2,
    941:2, 942:3, 943:3, 944:3, 945:1, 946:1, 947:1, 948:1, 949:1, 950:1,
    951:1, 952:1, 953:2, 954:1, 955:1, 956:1, 957:1, 958:2, 959:1, 960:1,
    961:1, 962:2, 963:1, 964:1, 965:1, 966:2, 967:2, 968:2, 969:1, 970:1,
    971:3, 972:1, 973:3, 974:1, 975:2, 976:1, 977:3, 978:1, 979:2, 980:3,
    981:3, 982:3, 983:1, 984:1, 985:2, 986:3, 987:1, 988:3, 989:1, 990:1,
    991:4, 992:2, 993:4, 994:2, 995:2, 997:3, 998:2, 999:2, 1000:1, 1001:1,
    1002:1, 1003:1, 1004:1, 1005:1, 1006:1, 1007:1, 1008:1, 1009:2, 1010:2, 1011:1,
    1012:1, 1014:1, 1015:1, 1016:2, 1017:1, 1018:3, 1019:1, 1020:2, 1021:2, 1022:2,
    1023:1, 1024:1, 1025:1, 1026:1, 1027:2, 1028:2, 1029:2, 1030:1, 1031:2, 1032:3,
    1033:3, 1034:3, 1035:1, 1036:1, 1038:1, 1039:1, 1040:1, 1041:2, 1042:1, 1043:1,
    1044:1, 1045:1, 1046:3, 1047:3, 1048:4, 1049:4, 1050:1, 1051:2, 1052:2, 1053:3,
    1054:3, 1056:2, 1057:1, 1058:1, 1059:1, 1060:2, 1061:3, 1062:1, 1063:1, 1065:2,
    1066:2, 1067:3, 1068:1, 1069:1, 1070:1, 1071:1, 1072:4, 1073:1, 1074:4, 1075:1,
    1076:1,
}

Teal_Mask_Ogerpon_ex = 96
Chikorita = 917
Bayleef = 709
Meganium = 710
Applin = 92
Dipplin = 93
Hydrapple_ex = 150
Meowth_ex = 1071
Fezandipiti_ex = 140
Tapu_Bulu = 920

Pinsir = 25

Lillie_Determination = 1227
Boss_Orders = 1182
Lanas_Aid = 1184

Dawn = 1231
Bug_Catching_Set = 1094
Ultra_Ball = 1121
Night_Stretcher = 1097
Unfair_Stamp = 1080
Poke_Pad = 1152
Forest_of_Vitality = 1261
Neutralization_Zone = 1247
Team_Rockets_Watchtower = 1256
Basic_Grass_Energy = 1

Budew = 235

Crustle_Grass = 345
Dwebble_Grass = 344
Crustle_Fighting = 533
Dwebble_Fighting = 532
Sylveon = 330

# Mazo de mill/control Comfey (user): Comfey (unico atacante, "Flower Shower" nos
# hace robar 3 -> nos deckea), Bramblin (no ataca) evoluciona a Brambleghast que
# CONFUNDE nuestro activo con "Prison Panic". Detectado por cualquiera de los 3.
Comfey = 164
Bramblin = 817
Brambleghast = 818

Munkidori = 112
Froslass = 104
Snorunt = 103
Dragapult_ex = 121
Dreepy = 119
Drakloak = 120
Iron_Thorns_ex = 37
Charizard_ex = 790
Grimmsnarl_ex = 648
Marnies_Impidimp = 646
Marnies_Morgrem = 647
Latias_ex = 184
Cornerstone_Mask_Ogerpon_ex = 117
Mega_Kangaskhan_ex = 756

Hops_Phantump = 878
Hops_Trevenant = 879
Splashing_Dodge_Atk = 1266
COIN_FLIP_LOG_TYPE = 22

Mega_Greninja_ex = 40
Mega_Starmie_ex = 1031
Slowking = 163
Slowpoke = 162

Beedrill = -991
Weedle = -992
Kakuna = -993
Zoroark_N = 293
Zorua_N = 292
Alakazam_ex = 743
Abra = 741
Kadabra = 742
# Linea Mega Lopunny ex: Buneary (basico, id 848) -> Mega Lopunny ex (Stage 1,
# id 849, ex de 2 premios). El basico atacante de este mazo es Buneary.
Buneary = 848
Mega_Lopunny_ex = 849
Gardevoir_ex = 747
Ralts = 745
Kirlia = 746
Raging_Bolt_ex = 63
Lugia_VSTAR = 337
Dusknoir = 133
Duskull = 131
Dusclops = 132
Typhlosion = 354
Cyndaquil = 352
Quilava = 353
Drednaw = 158
Chewtle = 157
Cubchoo = 506
Beartic = 507
Eevee_TWM = 43
Eevee_SFA = 145
Eevee_PRE_ex = 249
Eevee_SSP = 317
EEVEE_IDS = {43, 145, 249, 317}

OUR_EX_IDS = {Teal_Mask_Ogerpon_ex, Hydrapple_ex, Meowth_ex, Fezandipiti_ex}

# Cartas de tipo Item ("artefactos") de nuestro mazo. Se usa para posponer la
# bajada de Tapu Bulu hasta haber jugado los items que valga la pena.
DECK_ITEM_IDS = frozenset({Bug_Catching_Set, Ultra_Ball, Night_Stretcher,
                           Poke_Pad, Unfair_Stamp})

EX_IMMUNE_IDS = {Crustle_Grass, Sylveon}

ABILITY_IMMUNE_IDS = {Cornerstone_Mask_Ogerpon_ex}

OUR_ABILITY_IDS = {Teal_Mask_Ogerpon_ex, Hydrapple_ex, Meganium, Fezandipiti_ex, Meowth_ex, Dipplin}

NON_ATTACKER_ENERGY_WASTE_IDS = {Meowth_ex, Fezandipiti_ex}

HIGH_PRIORITY_BENCH_TARGETS = {Budew, Munkidori, Froslass, Snorunt, Dreepy, Drakloak, Dwebble_Grass, Dwebble_Fighting}

META_BENCH_TARGETS = {Slowpoke, Slowking, Weedle, Kakuna, Beedrill, Zorua_N, Zoroark_N,
                      Abra, Kadabra, Alakazam_ex, Ralts, Kirlia, Gardevoir_ex,
                      Duskull, Dusclops, Dusknoir, Cyndaquil, Quilava, Typhlosion,
                      Chewtle, Drednaw, Sylveon, 43, 145, 249, 317}

FIRE_POKEMON_IDS = {Charizard_ex, Typhlosion, Cyndaquil, Quilava}

WATER_SNIPE_IDS = {Mega_Greninja_ex, 47}

PSYCHIC_CONTROL_IDS = {Slowking, Alakazam_ex, Gardevoir_ex}

Riolu = 677
Mega_Lucario_ex = 678
Duraludon = 169

THREAT_PREEVO_IDS = {Riolu, Duraludon, Hops_Phantump, Dwebble_Grass, Dwebble_Fighting,
                     Buneary}

# Dunsparce (id 65 = TEF, id 305 = JTG): NUNCA gustear con Boss's Orders (user
# req). Son muros que se retiran/reposicionan con facilidad; subirlos al activo
# rival con Boss's Orders no aporta ventaja.
DUNSPARCE_IDS = {65, 305}

# Pokemon clave de cada mazo que conviene noquear con Boss's Orders desde la
# banca AUNQUE nuestro activo pueda noquear al activo rival, cuando ese activo
# rival NO es un Pokemon clave (p.ej. un muro sin energia). Ej.: en el mazo Hop
# el atacante clave es Hop's Trevenant; su linea (Trevenant/Phantump) debe
# cazarse en banca. La prioridad entre objetivos (con/sin energia, evolucion vs
# pre-evo) la resuelve _boss_tier en la seleccion del objetivo (TO_ACTIVE):
# Trevenant con energia > Trevenant sin energia > Phantump con energia >
# Phantump sin energia.
KEY_BENCH_ATTACKER_IDS = {Hops_Trevenant, Hops_Phantump}

EX_PREEVO_IDS = {
    Dreepy, Drakloak,
    Riolu,
    Duraludon,
    Zorua_N,
    Abra, Kadabra,
    Ralts, Kirlia,
    Marnies_Impidimp, Marnies_Morgrem,
    Buneary,  # -> Mega Lopunny ex (id 849, ex de 2 premios)
}

# Pre-evoluciones de EX_PREEVO_IDS cuya forma FINAL es NON-ex (1 premio) en
# este entorno, NO un ex de 2 premios. Abra -> Kadabra -> Alakazam (id 743) es
# la unica: la constante `Alakazam_ex = 743` es un nombre enganoso; el dato de
# la carta marca ex=False (1 premio). La logica de "negar una linea EX" (que
# justifica gustear una pre-evo con Boss's para impedir un ATACANTE DE 2
# PREMIOS) NO debe aplicar a esta linea: gustear+noquear la pre-evo rinde 1
# premio, lo mismo que noquear al muro activo, asi que es un gusteo inutil.
NONEX_FINAL_PREEVO_IDS = {Abra, Kadabra}

_ID_NAME_EXPECTATIONS = {
    Teal_Mask_Ogerpon_ex: "Ogerpon", Chikorita: "Chikorita", Bayleef: "Bayleef",
    Meganium: "Meganium", Applin: "Applin", Dipplin: "Dipplin",
    Hydrapple_ex: "Hydrapple", Meowth_ex: "Meowth", Fezandipiti_ex: "Fezandipiti",
    Tapu_Bulu: "Tapu",
    Budew: "Budew", Crustle_Grass: "Crustle", Dwebble_Grass: "Dwebble",
    Crustle_Fighting: "Crustle", Dwebble_Fighting: "Dwebble", Sylveon: "Sylveon",
    Munkidori: "Munkidori", Froslass: "Froslass", Snorunt: "Snorunt",
    Dragapult_ex: "Dragapult", Dreepy: "Dreepy", Drakloak: "Drakloak",
    Iron_Thorns_ex: "Iron Thorns", Grimmsnarl_ex: "Grimmsnarl", Latias_ex: "Latias",
    Marnies_Impidimp: "Impidimp", Marnies_Morgrem: "Morgrem",
    Cornerstone_Mask_Ogerpon_ex: "Ogerpon", Slowking: "Slowking", Slowpoke: "Slowpoke",
    Zoroark_N: "Zoroark", Zorua_N: "Zorua", Kadabra: "Kadabra",
    Gardevoir_ex: "Gardevoir", Ralts: "Ralts", Kirlia: "Kirlia",
    Raging_Bolt_ex: "Raging Bolt", Dusknoir: "Dusknoir", Duskull: "Duskull",
    Dusclops: "Dusclops", Typhlosion: "Typhlosion", Cyndaquil: "Cyndaquil",
    Quilava: "Quilava", Drednaw: "Drednaw", Chewtle: "Chewtle",
}

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

try:
    _ID_AUDIT_MISMATCHES = _validate_id_constants()
except Exception:
    _ID_AUDIT_MISMATCHES = []

SCORE_WIN_GAME = 50000

SCORE_LOOKAHEAD_EX_TRADE = 250
SCORE_LOOKAHEAD_KO_TRADE = 120
SCORE_LOOKAHEAD_SAFE = 60
SCORE_LOOKAHEAD_PROMOTE_KO = 120
SCORE_LOOKAHEAD_PROMOTE_SAFE = 40

SCORE_BELIEF_DIG_ENERGY = 250

# Prioridad de Boss's Orders cuando, frente a Crustle, nuestro activo ex esta
# bloqueado pero hay un objetivo en la banca rival al que si podemos pegar y que
# podemos noquear o dejar sin poder retirarse. Debe superar a los cebos de robo
# (Lillie's ~650) y al resto del ladder de Boss's.
BOSS_PRIORITY_CRUSTLE_GUST = 990

# Puntaje al que se rebaja Tapu Bulu cuando aun quedan items ("artefactos") en la
# mano: queda por debajo de la banda de items utiles (~9800+, o 9000 cuando un
# item se autolimita) y por encima de items que NO valen la pena (puntaje bajo).
# Asi los items utiles se juegan primero y, cuando ya no quede ninguno util,
# Tapu Bulu vuelve a ganar y se baja. Aplica SOLO a Tapu Bulu.
TAPU_WAIT_FOR_ITEMS_SCORE = 8900

# --- Ladder de puntuacion de Boss's Orders (rama PLAY, ~L9250) ---
# Orden de prioridad de mayor a menor cuando decidimos jugar Boss's Orders. Los
# nombres documentan que remate representa cada rama; a todos (salvo el gusteo
# "vacio") se les suma `supporter_boost`. Lillie's base = 5000, asi que las
# ramas >5000 ganan a refrescar con Lillie's y las <5000 le ceden la prioridad.
BOSS_SCORE_WIN_NOW = 20000           # gusteo que GANA la partida con el activo: prioridad maxima
BOSS_SCORE_WIN_VIA_BENCH = 5600      # gustada letal a un objetivo de banca
BOSS_SCORE_WALL_GUST = 5500          # rival con muro inmune (ex/habilidad) al activo
BOSS_SCORE_DODGE_REDIRECT = 5500     # redireccion por esquiva (dodge)
BOSS_SCORE_PRIZE_RANK_BASE = 5200    # gusteo que habilita KO (afinado por prize_rank)
BOSS_SCORE_LOW_VALUE_GUST = 1500     # gusteo de bajo valor
BOSS_SCORE_DEFENSIVE_GUST = 1500     # gusteo defensivo (vs Crustle)
BOSS_SCORE_EMPTY_GUST = 20           # gusteo NO ejecutable: ceder a Lillie's

class AttackPlan:
    attacker = -1
    target = -1
    attack_index = -1
    remain_hp = -1
    energy = False

plan = AttackPlan()
pre_turn = 0
meganium_in_play = False


def _grass_mult():
    # La observacion del juego YA aplica Wild Growth de Meganium: cada energia
    # basica de Planta FISICA aparece DUPLICADA en la lista `energies`, por lo
    # que len(energies) ES la energia EFECTIVA. Por eso este multiplicador es 1
    # (se conserva como funcion para que los sitios `crudo * _grass_mult()`
    # heredados sigan devolviendo la energia efectiva sin reescribirlos).
    return 1


def _grass_attach_unit():
    # Energia EFECTIVA que aporta UNA energia basica de Planta recien adjuntada
    # (desde la mano o recuperada). Con Wild Growth de Meganium en juego una
    # Planta fisica provee {G}{G} = 2 efectivas; sin Meganium, 1.
    return 2 if meganium_in_play else 1


def _active_of(state):
    # Pokemon activo de `state`, o None si no hay activo. Centraliza el patron
    # repetido `state.active[0] if state.active and state.active[0] is not None
    # else None`.
    if state is None:
        return None
    _act = getattr(state, "active", None)
    return _act[0] if _act and _act[0] is not None else None


def _physical_energy(effective_len):
    # Convierte energia EFECTIVA (len(energies), ya doblada por Wild Growth de
    # NUESTRO Meganium) a cartas de energia FISICAS. Con Meganium cada Planta
    # fisica cuenta como 2 efectivas, asi que fisica = efectiva // 2; sin
    # Meganium, efectiva == fisica.
    return effective_len // 2 if meganium_in_play else effective_len


def _retreat_cards(retreat_cost):
    # Numero de cartas de energia FISICAS necesarias para pagar `retreat_cost`
    # (expresado en unidades EFECTIVAS). Con Meganium cada Planta paga por dos
    # (division con techo). 0 si el coste es <= 0.
    if retreat_cost <= 0:
        return 0
    return -(-retreat_cost // _grass_attach_unit())


# Requisitos de energia EFECTIVA para atacar, por carta (fuente unica de verdad).
# len(energies) YA es energia efectiva (la observacion duplica la Planta por
# Wild Growth), asi que se compara directamente contra estos valores.
ATTACK_ENERGY_REQ = {
    Hydrapple_ex: 2, Dipplin: 1, Teal_Mask_Ogerpon_ex: 3,
    Tapu_Bulu: 4, Fezandipiti_ex: 3, Meganium: 4, Pinsir: 2,
    Bayleef: 2, Applin: 1, Chikorita: 1,
}

# Atacantes principales evaluados en los bloques de listo-para-atacar.
MAIN_ATTACKERS = (
    Hydrapple_ex, Dipplin, Teal_Mask_Ogerpon_ex,
    Tapu_Bulu, Fezandipiti_ex, Meganium, Pinsir,
)


def _can_attack_eff(card_id, raw_energy):
    # True si la carta puede atacar. raw_energy = len(energies) YA es la energia
    # efectiva (la observacion aplica Wild Growth), asi que se compara directo.
    _req = ATTACK_ENERGY_REQ.get(card_id)
    return _req is not None and raw_energy >= _req


forest_in_play = False
ko_last_turn = False
_ko_detected_this_turn = False
_prev_op_prize = 6
we_go_first = False
op_is_crustle_deck = False
op_is_cornerstone_deck = False
op_has_mega_kangaskhan = False
_field_at_turn_start = {}
_poke_pad_target_id = 0
_ub_meowth_pending = False

_dodge_immune_serial = None
_dodge_immune_turn = -1

ESTADO_MAZO = "MAZO"
ESTADO_BANCA = "BANCA"
ESTADO_MANO = "MANO"
ESTADO_PREMIO = "PREMIO"
ESTADO_DESCARTE = "DESCARTE"

CARTAS_ACTIVAS_EN_MAZO = {}
_cartas_first_scan_done = False
_cartas_prizes_identified = False
_cartas_last_turn = -1

def _init_cartas_tracking():
    global CARTAS_ACTIVAS_EN_MAZO, _cartas_first_scan_done, _cartas_prizes_identified
    CARTAS_ACTIVAS_EN_MAZO = {}
    _cartas_first_scan_done = False
    _cartas_prizes_identified = False
    for card_id in my_deck:
        if card_id not in CARTAS_ACTIVAS_EN_MAZO:
            CARTAS_ACTIVAS_EN_MAZO[card_id] = {
                ESTADO_MAZO: 0,
                ESTADO_BANCA: 0,
                ESTADO_MANO: 0,
                ESTADO_PREMIO: 0,
                ESTADO_DESCARTE: 0,
            }
        CARTAS_ACTIVAS_EN_MAZO[card_id][ESTADO_MAZO] += 1

_init_cartas_tracking()

def _move_card_state(card_id, from_state, to_state):
    if card_id in CARTAS_ACTIVAS_EN_MAZO:
        if CARTAS_ACTIVAS_EN_MAZO[card_id][from_state] > 0:
            CARTAS_ACTIVAS_EN_MAZO[card_id][from_state] -= 1
            CARTAS_ACTIVAS_EN_MAZO[card_id][to_state] += 1
            return True
    return False

def _belief_deck_and_prizes():
    deck = 0
    prize = 0
    for counts in CARTAS_ACTIVAS_EN_MAZO.values():
        deck += counts.get(ESTADO_MAZO, 0)
        prize += counts.get(ESTADO_PREMIO, 0)
    return deck, prize

def _prob_draw_any(target_ids, draws=1):
    if draws <= 0:
        return 0.0
    if isinstance(target_ids, int):
        target_ids = (target_ids,)
    target_set = set(target_ids)
    deck = 0
    hits = 0
    for cid, counts in CARTAS_ACTIVAS_EN_MAZO.items():
        n = counts.get(ESTADO_MAZO, 0)
        deck += n
        if cid in target_set:
            hits += n
    if deck <= 0 or hits <= 0:
        return 0.0
    draws = min(draws, deck)
    miss = deck - hits
    p_none = 1.0
    for i in range(draws):
        denom = deck - i
        if denom <= 0:
            break
        p_none *= max(0, (miss - i)) / denom
    return 1.0 - p_none

def _prob_card_accessible(card_id):
    counts = CARTAS_ACTIVAS_EN_MAZO.get(card_id)
    if not counts:
        return 0.0
    in_deck = counts.get(ESTADO_MAZO, 0)
    in_prize = counts.get(ESTADO_PREMIO, 0)
    copies = in_deck + in_prize
    if copies <= 0:
        return 0.0
    deck, prize = _belief_deck_and_prizes()
    total_hidden = deck + prize
    if total_hidden <= 0:
        return 1.0 if in_deck > 0 else 0.0
    if prize <= 0:
        return 1.0
    p_all_prized = 1.0
    for i in range(copies):
        denom = total_hidden - i
        if denom <= 0:
            p_all_prized = 0.0
            break
        p_all_prized *= max(0, (prize - i)) / denom
    return 1.0 - p_all_prized

def _our_effective_damage(my_pokemon, op_pokemon, base_damage,
                          meganium_active=False, neutralization_zone=False):
    if op_pokemon is None or base_damage is None:
        return 0
    data = card_table.get(op_pokemon.id)
    if data is None:
        return max(0, base_damage)
    my_is_ex = my_pokemon.id in OUR_EX_IDS
    my_has_ability = my_pokemon.id in OUR_ABILITY_IDS
    is_fez = (my_pokemon.id == Fezandipiti_ex)
    damage = base_damage

    if op_pokemon.id in EX_IMMUNE_IDS and my_is_ex:
        return 0

    _op_has_rule_box = bool(getattr(data, 'ex', False) or getattr(data, 'megaEx', False))
    if neutralization_zone and my_is_ex and not _op_has_rule_box:
        return 0

    if op_pokemon.id in ABILITY_IMMUNE_IDS and my_has_ability:
        return 0

    if not is_fez:
        if data.weakness == EnergyType.GRASS:
            damage *= 2
        elif data.resistance == EnergyType.GRASS:
            damage -= 30

    if op_pokemon.id == Drednaw and damage >= 200:
        return 0

    if (op_pokemon.id == Crustle_Fighting and
            op_pokemon.hp == op_pokemon.maxHp and damage >= op_pokemon.hp):
        damage = op_pokemon.hp - 10

    return max(0, int(damage))

def _attacker_base_damage(attacker_id, target, effective_energy,
                          grass_scale, teal_self_energy, bench_count):
    """Dano base de un atacante propio contra `target`, ANTES de aplicar
    debilidad/resistencia/inmunidad (de eso se encarga _our_effective_damage).

    - effective_energy: energia EFECTIVA disponible para atacar (len(energies)
      ya es efectiva; incluir aqui la energia a adjuntar si corresponde).
    - grass_scale: nº de energias Grass para escalar el ataque de Hydrapple.
    - teal_self_energy: energia propia para escalar el ataque de Teal Mask
      (internamente se le suma la energia del objetivo).
    - bench_count: nº de Pokemon en nuestra banca (escala el ataque de Dipplin).

    Devuelve 0 si el atacante no llega a su requisito de energia
    (ATTACK_ENERGY_REQ, fuente unica de verdad).
    """
    req = ATTACK_ENERGY_REQ
    if attacker_id == Hydrapple_ex and effective_energy >= req[Hydrapple_ex]:
        return 30 + 30 * grass_scale
    if attacker_id == Teal_Mask_Ogerpon_ex and effective_energy >= req[Teal_Mask_Ogerpon_ex]:
        # Ivy Bludgeon: 30 + 30 por cada Energia Planta adjunta A ESTE Pokemon
        # (user, registro_012 paso 93). NO cuenta la energia del objetivo: antes
        # se sumaba `len(target.energies)`, lo que SOBREESTIMABA el dano (p.ej. un
        # Ogerpon ex de 4 energias contra Duraludon daba 180 en vez de 150, y con
        # la resistencia -30 a Planta el juego creia que noqueaba (150) cuando en
        # realidad hace 120 y NO noquea). `teal_self_energy` ya es la energia
        # EFECTIVA propia (Wild Growth de Meganium la duplica).
        return 30 + 30 * teal_self_energy
    if attacker_id == Tapu_Bulu and effective_energy >= req[Tapu_Bulu]:
        return 220
    if attacker_id == Fezandipiti_ex and effective_energy >= req[Fezandipiti_ex]:
        return 100
    if attacker_id == Meganium and effective_energy >= req[Meganium]:
        return 140
    if attacker_id == Dipplin and effective_energy >= req[Dipplin]:
        return 20 * bench_count
    if attacker_id == Pinsir and effective_energy >= req[Pinsir]:
        return 100
    return 0

def _bench_attacker_can_ko(my_state, target, meganium_active, total_grass_field,
                           bench_count, retreat_grass_after, neutral_zone):
    if target is None:
        return False
    _thp = target.hp or 0
    if _thp <= 0:
        return False
    for bp in (my_state.bench or []):
        if bp is None:
            continue
        e = len(bp.energies)
        eff = e * _grass_mult()
        base = _attacker_base_damage(bp.id, target, eff,
                                     grass_scale=retreat_grass_after,
                                     teal_self_energy=e, bench_count=bench_count)
        if base <= 0:
            continue
        if _our_effective_damage(bp, target, base, meganium_active, neutral_zone) >= _thp:
            return True
    return False

def _op_hand_size(op_state):
    try:
        return len(op_state.hand) if op_state.hand else 0
    except (AttributeError, TypeError):
        return 0

def _op_disruption_belief(op_state, op_supporter_played):
    h = _op_hand_size(op_state)
    if h <= 0:
        return 0.05

    p_one = 2.0 / 40.0
    p_none = (1.0 - p_one) ** h
    p = 1.0 - p_none
    return max(0.05, min(0.85, p))

import os as _os_dbg
DEBUG_DECISIONS = _os_dbg.environ.get("PTCG_DEBUG", "") not in ("", "0", "false", "False")

def _debug_log_decision(context, select, scores, obs, my_index, top_n=3):
    if not DEBUG_DECISIONS:
        return
    try:
        import sys as _sys
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        print(f"[DBG] ctx={getattr(context, 'name', context)} "
              f"opciones={len(scores)}", file=_sys.stderr)
        for _r, _i in enumerate(ranked[:top_n]):
            _label = ""
            try:
                _opt = select.option[_i]
                _card = get_card(obs, _opt.area, _opt.index, my_index)
                if _card is not None:
                    _cd = card_table.get(_card.id)
                    _label = getattr(_cd, 'name', None) or f"id={_card.id}"
                else:
                    _label = f"area={getattr(_opt, 'area', '?')}"
            except Exception:
                _label = "?"
            print(f"[DBG]   #{_r+1} idx={_i} score={scores[_i]} {_label}",
                  file=_sys.stderr)
    except Exception:
        pass

def _first_turn_scan(my_state):
    global _cartas_first_scan_done
    if _cartas_first_scan_done:
        return

    if my_state.hand:
        for card in my_state.hand:
            _move_card_state(card.id, ESTADO_MAZO, ESTADO_MANO)

    for pokemon in my_state.active + my_state.bench:
        if pokemon is None:
            continue
        _move_card_state(pokemon.id, ESTADO_MAZO, ESTADO_BANCA)
        for pre in pokemon.preEvolution:
            _move_card_state(pre.id, ESTADO_MAZO, ESTADO_BANCA)
        for ec in pokemon.energyCards:
            _move_card_state(ec.id, ESTADO_MAZO, ESTADO_BANCA)
        for tc in pokemon.tools:
            _move_card_state(tc.id, ESTADO_MAZO, ESTADO_BANCA)

    for card in my_state.discard:
        _move_card_state(card.id, ESTADO_MAZO, ESTADO_DESCARTE)
    _cartas_first_scan_done = True

def _area_to_estado(area):
    if area == AreaType.DECK:
        return ESTADO_MAZO
    elif area == AreaType.HAND:
        return ESTADO_MANO
    elif area in (AreaType.ACTIVE, AreaType.BENCH):
        return ESTADO_BANCA
    elif area == AreaType.DISCARD:
        return ESTADO_DESCARTE
    elif area == AreaType.PRIZE:
        return ESTADO_PREMIO
    return None

def _process_logs(obs, my_index):
    for log in obs.logs:
        if not hasattr(log, 'type'):
            continue

        if log.type == LogType.DRAW and hasattr(log, 'playerIndex') and log.playerIndex == my_index:
            _move_card_state(log.cardId, ESTADO_MAZO, ESTADO_MANO)

        elif log.type == LogType.MOVE_CARD and hasattr(log, 'playerIndex') and log.playerIndex == my_index:
            if hasattr(log, 'fromArea') and hasattr(log, 'toArea') and hasattr(log, 'cardId'):
                from_estado = _area_to_estado(log.fromArea)
                to_estado = _area_to_estado(log.toArea)
                if from_estado and to_estado and from_estado != to_estado:
                    _move_card_state(log.cardId, from_estado, to_estado)

def _identify_prizes(obs, my_state=None):
    # Se recalcula en CADA revelacion COMPLETA del mazo. La vista del mazo
    # durante una busqueda (Ultra Ball, Poke Pad, etc.) muestra en select.deck
    # TODAS las cartas del mazo, por lo que es la verdad de referencia de lo que
    # hay en MAZO ahora mismo. Cualquier copia propia que no este en el mazo (ni
    # en mano/juego/descarte) esta en los premios. Al no usar un cerrojo de una
    # sola vez, el conocimiento de premios se corrige solo y se mantiene al dia.
    if obs.select is None or obs.select.deck is None:
        return
    if obs.select.effect is None:
        return
    # Ultra Ball SIEMPRE revela el mazo entero -> reconciliar directo.
    # Para otros efectos (Poke Pad, etc.) solo reconciliar si es una revelacion
    # del mazo COMPLETO: hay efectos que muestran solo una parte ("mira las 7 de
    # arriba", p.ej. Bug Catching Set) y en esos casos len(select.deck) < deckCount;
    # reconciliar con una vista parcial marcaria como PREMIADAS cartas que si estan
    # en el mazo. Por eso exigimos len(select.deck) == deckCount.
    if obs.select.effect.id != Ultra_Ball:
        deck_count = getattr(my_state, 'deckCount', None) if my_state is not None else None
        if deck_count is None or len(obs.select.deck) != deck_count:
            return

    deck_counts = defaultdict(int)
    for card in obs.select.deck:
        deck_counts[card.id] += 1

    for cid, entry in CARTAS_ACTIVAS_EN_MAZO.items():
        total_copies = sum(entry.values())
        in_deck = deck_counts.get(cid, 0)
        hidden = total_copies - entry[ESTADO_MANO] - entry[ESTADO_BANCA] - entry[ESTADO_DESCARTE]
        if hidden < 0:
            hidden = 0
        entry[ESTADO_MAZO] = in_deck
        premio = hidden - in_deck
        entry[ESTADO_PREMIO] = premio if premio > 0 else 0

def _sync_from_state(my_state):

    actual = defaultdict(lambda: {ESTADO_MANO: 0, ESTADO_BANCA: 0, ESTADO_DESCARTE: 0})
    if my_state.hand:
        for card in my_state.hand:
            actual[card.id][ESTADO_MANO] += 1
    for pokemon in my_state.active + my_state.bench:
        if pokemon is None:
            continue
        actual[pokemon.id][ESTADO_BANCA] += 1
        for pre in pokemon.preEvolution:
            actual[pre.id][ESTADO_BANCA] += 1
        for ec in pokemon.energyCards:
            actual[ec.id][ESTADO_BANCA] += 1
        for tc in pokemon.tools:
            actual[tc.id][ESTADO_BANCA] += 1
    for card in my_state.discard:
        actual[card.id][ESTADO_DESCARTE] += 1

    for cid in CARTAS_ACTIVAS_EN_MAZO:
        entry = CARTAS_ACTIVAS_EN_MAZO[cid]
        real_mano = actual[cid][ESTADO_MANO]
        real_banca = actual[cid][ESTADO_BANCA]
        real_descarte = actual[cid][ESTADO_DESCARTE]

        total_copies = sum(entry.values())

        entry[ESTADO_MANO] = real_mano
        entry[ESTADO_BANCA] = real_banca
        entry[ESTADO_DESCARTE] = real_descarte

        remaining = total_copies - real_mano - real_banca - real_descarte
        if remaining < 0:
            remaining = 0

        known_premio = min(entry[ESTADO_PREMIO], remaining)
        entry[ESTADO_PREMIO] = known_premio
        entry[ESTADO_MAZO] = remaining - known_premio

def _update_cartas_tracking(obs, my_index, my_state):
    global _cartas_first_scan_done, _cartas_last_turn

    if obs.current.turn == 1 and _cartas_last_turn > 1:
        _init_cartas_tracking()
        global op_is_crustle_deck, op_is_cornerstone_deck, op_has_mega_kangaskhan
        op_is_crustle_deck = False
        op_is_cornerstone_deck = False
        op_has_mega_kangaskhan = False
    _cartas_last_turn = obs.current.turn

    if not _cartas_first_scan_done and obs.current is not None:

        _first_turn_scan(my_state)
    else:

        _process_logs(obs, my_index)

        _sync_from_state(my_state)

    _identify_prizes(obs, my_state)

def get_card(obs: Observation, area: AreaType, index: int, player_index: int) -> Pokemon | Card | None:
    ps = obs.current.players[player_index]
    try:
        match area:
            case AreaType.DECK:
                return obs.select.deck[index]
            case AreaType.HAND:
                return ps.hand[index]
            case AreaType.DISCARD:
                return ps.discard[index]
            case AreaType.ACTIVE:
                return ps.active[index]
            case AreaType.BENCH:
                return ps.bench[index]
            case AreaType.PRIZE:
                return ps.prize[index]
            case AreaType.STADIUM:
                return obs.current.stadium[index]
            case AreaType.LOOKING:
                return obs.current.looking[index]
            case _:
                return None
    except (IndexError, AttributeError, TypeError):
        return None

def prize_count(pokemon: Pokemon) -> int:
    data = card_table[pokemon.id]
    count = 3 if data.megaEx else 2 if data.ex else 1
    for card in pokemon.energyCards:
        if card.id == 12:
            count -= 1
    for card in pokemon.tools:
        if card.id == 1172 and "Lillie" in data.name:
            count -= 1
    return max(0, count)

def count_total_grass_energy(my_state) -> int:
    total = 0
    for pokemon in my_state.active + my_state.bench:
        if pokemon is None:
            continue
        for e in pokemon.energies:
            if e == EnergyType.GRASS:
                total += 1
    return total

def calc_syrup_storm_damage(my_state, has_meganium: bool) -> int:
    total_grass = count_total_grass_energy(my_state)
    if has_meganium:

        pass
    return 30 + 30 * total_grass

def pokemon_score(pokemon: Pokemon) -> int:
    data = card_table[pokemon.id]
    score = prize_count(pokemon) * 1000
    score += len(pokemon.energies) * 150
    score += len(pokemon.tools) * 100
    if data.stage2:
        score += 250
    elif data.stage1:
        score += 130

    pid = pokemon.id

    if pid == 144 or pid == 322 or pid == 323 or pid == 337:
        score -= 200
    if pid == 112 and len(pokemon.energies) >= 1:
        score += 300

    if pid == Meganium:
        score += 350
    elif pid == Gardevoir_ex:
        score += 400
    elif pid == Typhlosion:
        score += 350
    elif pid == Slowking:
        score += 400
    elif pid == Dusknoir:
        score += 350
    elif pid == Alakazam_ex:
        score += 300
    score += pokemon.hp
    return score

def _count_hand_play_options(hand_counts, field_counts, bench_count, energy_attached):
    play_options = 0

    if hand_counts.get(Meganium, 0) >= 1 and field_counts.get(Bayleef, 0) >= 1:
        play_options += 2
    if hand_counts.get(Bayleef, 0) >= 1 and field_counts.get(Chikorita, 0) >= 1:
        play_options += 2
    if hand_counts.get(Hydrapple_ex, 0) >= 1 and field_counts.get(Dipplin, 0) >= 1:
        play_options += 2
    if hand_counts.get(Dipplin, 0) >= 1 and field_counts.get(Applin, 0) >= 1:
        play_options += 2

    supporters_in_hand = (hand_counts.get(Lillie_Determination, 0) + hand_counts.get(Boss_Orders, 0) +
                         hand_counts.get(Dawn, 0) +
                         hand_counts.get(Lanas_Aid, 0))
    play_options += supporters_in_hand

    if hand_counts.get(Basic_Grass_Energy, 0) >= 1 and not energy_attached:
        play_options += 1

    if bench_count < 5:
        for bcid in (Chikorita, Applin, Teal_Mask_Ogerpon_ex):
            if hand_counts.get(bcid, 0) >= 1:
                play_options += 1
    return play_options, supporters_in_hand

def _eval_ub_best_target(field_counts, hand_counts, meganium_in_play, has_hydrapple,
                         forest_in_play, op_has_ex_immune_active, op_has_ex_immune_bench,
                         op_prize, bench_count, state, ko_last_turn,
                         _best_supp_in_mazo_val, supporters_in_hand, hand_is_weak,
                         has_energy_for_teal, _we_go_first=False,
                         _best_supp_in_hand_val=0,
                         op_is_crustle_deck=False, op_is_cornerstone_deck=False,
                         op_active_is_budew=False, watchtower_in_play=False):
    ub_best_target = 0

    _bench_full = (bench_count >= 5)

    _hand_total = sum(hand_counts.values())

    if state.turn == 2 and not _we_go_first:

        if (not state.supporterPlayed and
                hand_counts.get(Lillie_Determination, 0) == 0 and
                field_counts.get(Meowth_ex, 0) < 2 and
                bench_count < 5 and
                not watchtower_in_play and
                CARTAS_ACTIVAS_EN_MAZO.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) > 0):
            _lillie_in_mazo = CARTAS_ACTIVAS_EN_MAZO.get(Lillie_Determination, {}).get(ESTADO_MAZO, 0)
            if _lillie_in_mazo > 0:
                ub_best_target = max(ub_best_target, 1100)
            elif any(CARTAS_ACTIVAS_EN_MAZO.get(sid, {}).get(ESTADO_MAZO, 0) > 0
                     for sid in (Dawn, Lanas_Aid)):
                ub_best_target = max(ub_best_target, 950)

        if bench_count == 0:
            _has_basic_in_hand_t1s = any(hand_counts.get(pid, 0) >= 1
                                         for pid in (Chikorita, Applin, Teal_Mask_Ogerpon_ex,
                                                     Tapu_Bulu, Meowth_ex, Fezandipiti_ex,
                                                     Pinsir))
            _active_is_weak_basic = any(field_counts.get(pid, 0) >= 1
                                        for pid in (Applin, Chikorita))
            if not _has_basic_in_hand_t1s and _active_is_weak_basic:
                if CARTAS_ACTIVAS_EN_MAZO.get(Teal_Mask_Ogerpon_ex, {}).get(ESTADO_MAZO, 0) > 0:
                    ub_best_target = max(ub_best_target, 1050)

        return ub_best_target

    if state.turn == 1 and _we_go_first:
        # Regla vs Budew activo: si el rival abre con Budew en el ACTIVO, su
        # ataque Itchy Pollen nos bloqueara los Items durante NUESTRO proximo
        # turno. Por eso, si no tenemos Lillie's en mano pero si una Ultra Ball,
        # debemos usarla AHORA para buscar Meowth ex, jugarlo y que su habilidad
        # nos traiga una Lillie's (supporter, jugable aun bajo el bloqueo de
        # items) para el siguiente turno. Prioridad maxima e independiente del
        # desarrollo del banco.
        if (op_active_is_budew and
                hand_counts.get(Lillie_Determination, 0) == 0 and
                hand_counts.get(Meowth_ex, 0) == 0 and
                field_counts.get(Meowth_ex, 0) == 0 and
                bench_count < 5 and
                not state.supporterPlayed and
                not watchtower_in_play and
                CARTAS_ACTIVAS_EN_MAZO.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) > 0 and
                CARTAS_ACTIVAS_EN_MAZO.get(Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0):
            return 1100

        _has_basic_in_hand = any(hand_counts.get(pid, 0) >= 1
                                 for pid in (Chikorita, Applin, Teal_Mask_Ogerpon_ex,
                                             Tapu_Bulu, Fezandipiti_ex, Pinsir))
        if bench_count >= 1 or _has_basic_in_hand:
            return 0

        _best_t1_val = 0

        if (field_counts.get(Teal_Mask_Ogerpon_ex, 0) == 0 and
                CARTAS_ACTIVAS_EN_MAZO.get(Teal_Mask_Ogerpon_ex, {}).get(ESTADO_MAZO, 0) > 0):
            _val = 950
            if hand_counts.get(Basic_Grass_Energy, 0) >= 1:
                _val = 1000
            _best_t1_val = max(_best_t1_val, _val)

        if (field_counts.get(Chikorita, 0) == 0 and
                CARTAS_ACTIVAS_EN_MAZO.get(Chikorita, {}).get(ESTADO_MAZO, 0) > 0):
            _val = 850
            if field_counts.get(Applin, 0) >= 1 or field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1:
                _val = 900
            if hand_counts.get(Bayleef, 0) >= 1:
                _val += 50
            _best_t1_val = max(_best_t1_val, _val)

        if (field_counts.get(Applin, 0) == 0 and
                CARTAS_ACTIVAS_EN_MAZO.get(Applin, {}).get(ESTADO_MAZO, 0) > 0):
            _val = 800
            if field_counts.get(Chikorita, 0) >= 1 or field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1:
                _val = 850
            if hand_counts.get(Dipplin, 0) >= 1:
                _val += 50
            _best_t1_val = max(_best_t1_val, _val)

        ub_best_target = max(ub_best_target, _best_t1_val)
        return ub_best_target

    _stamp_blocks_supp_chain = (ko_last_turn and hand_counts.get(Unfair_Stamp, 0) >= 1)

    _supp_in_hand_is_inferior = False
    if supporters_in_hand >= 1 and _best_supp_in_mazo_val >= 600:

        if _best_supp_in_mazo_val > _best_supp_in_hand_val + 100:
            _supp_in_hand_is_inferior = True

    meowth_viable = (
        not _stamp_blocks_supp_chain and
        not (state.turn <= 1 and _we_go_first) and
        not state.supporterPlayed and
        not watchtower_in_play and
        (supporters_in_hand == 0 or _supp_in_hand_is_inferior) and
        field_counts.get(Meowth_ex, 0) == 0 and
        bench_count < 5 and
        CARTAS_ACTIVAS_EN_MAZO.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) > 0 and
        _best_supp_in_mazo_val > 200
    )

    if not meowth_viable and op_is_crustle_deck:
        _boss_in_mazo = CARTAS_ACTIVAS_EN_MAZO.get(Boss_Orders, {}).get(ESTADO_MAZO, 0) > 0
        _boss_val_ub = _best_supp_in_mazo_val
        if (_boss_in_mazo and _boss_val_ub >= 900 and
                not state.supporterPlayed and
                not watchtower_in_play and
                field_counts.get(Meowth_ex, 0) == 0 and
                bench_count < 5 and
                hand_counts.get(Boss_Orders, 0) == 0 and
                CARTAS_ACTIVAS_EN_MAZO.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) > 0):
            meowth_viable = True
    if meowth_viable:
        meowth_val = _best_supp_in_mazo_val
        if state.turn <= 2:
            meowth_val += 200
        elif hand_is_weak:
            meowth_val += 100
        ub_best_target = max(ub_best_target, meowth_val)

    if has_energy_for_teal and field_counts.get(Teal_Mask_Ogerpon_ex, 0) < 2 and bench_count < 5:
        if CARTAS_ACTIVAS_EN_MAZO.get(Teal_Mask_Ogerpon_ex, {}).get(ESTADO_MAZO, 0) > 0:
            val = 650
            if field_counts.get(Teal_Mask_Ogerpon_ex, 0) == 0:
                val = 750
            if hand_counts.get(Basic_Grass_Energy, 0) >= 2:
                val += 100
            ub_best_target = max(ub_best_target, val)

    if (has_energy_for_teal and
            field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 2 and
            bench_count < 5 and
            field_counts.get(Hydrapple_ex, 0) >= 1):
        if CARTAS_ACTIVAS_EN_MAZO.get(Teal_Mask_Ogerpon_ex, {}).get(ESTADO_MAZO, 0) > 0:

            _td_dmg_bonus = 60 if meganium_in_play else 30
            val = 500 + _td_dmg_bonus * 2

            if hand_counts.get(Basic_Grass_Energy, 0) >= 2:
                val += 150

            if field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 2:
                val += 50
            ub_best_target = max(ub_best_target, val)

    _evolvable = _field_at_turn_start if (not forest_in_play and _field_at_turn_start) else field_counts

    if not meganium_in_play:
        if _evolvable.get(Bayleef, 0) >= 1:
            if CARTAS_ACTIVAS_EN_MAZO.get(Meganium, {}).get(ESTADO_MAZO, 0) > 0:
                ub_best_target = max(ub_best_target, 1000)
        elif _evolvable.get(Chikorita, 0) >= 1 and field_counts.get(Bayleef, 0) >= 1:

            if CARTAS_ACTIVAS_EN_MAZO.get(Meganium, {}).get(ESTADO_MAZO, 0) > 0:
                if forest_in_play:

                    ub_best_target = max(ub_best_target, 1000)
                else:
                    # Bayleef recien evolucionado ESTE turno (habia Chikorita al
                    # inicio del turno) y SIN Forest: no se podra evolucionar a
                    # Meganium hasta el PROXIMO turno. Buscar Meganium ahora es solo
                    # preparacion, no aporta este turno, asi que se rebaja la
                    # prioridad para no gastar Ultra Ball + 2 descartes en una pieza
                    # inusable si hay mejores objetivos o pocos descartes seguros
                    # (con >=2 descartes seguros y sin mejor objetivo aun se busca).
                    ub_best_target = max(ub_best_target, 280)
        elif _evolvable.get(Chikorita, 0) >= 1:

            if (CARTAS_ACTIVAS_EN_MAZO.get(Bayleef, {}).get(ESTADO_MAZO, 0) > 0
                    and hand_counts.get(Bayleef, 0) == 0):
                # Solo vale buscar Bayleef si NO tenemos ya uno en la mano:
                # con una Chikorita en juego, un unico Bayleef basta para
                # evolucionarla. Si ya lo tenemos, la Ultra Ball no aporta nada
                # para esta linea (y gastaria 2 cartas de descarte por un duplicado).
                ub_best_target = max(ub_best_target, 850)

            elif (CARTAS_ACTIVAS_EN_MAZO.get(Meganium, {}).get(ESTADO_MAZO, 0) > 0 and
                  (forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1) and
                  hand_counts.get(Bayleef, 0) >= 1):
                _prot = 1
                if not forest_in_play:
                    _prot += 1
                if _hand_total - 1 - _prot >= 2:
                    ub_best_target = max(ub_best_target, 900)

        elif not _bench_full and field_counts.get(Chikorita, 0) + field_counts.get(Bayleef, 0) == 0:
            if CARTAS_ACTIVAS_EN_MAZO.get(Chikorita, {}).get(ESTADO_MAZO, 0) > 0:
                _has_mega_evo_in_mazo = (CARTAS_ACTIVAS_EN_MAZO.get(Bayleef, {}).get(ESTADO_MAZO, 0) > 0 or
                                         CARTAS_ACTIVAS_EN_MAZO.get(Meganium, {}).get(ESTADO_MAZO, 0) > 0)
                _has_mega_evo_in_hand = (hand_counts.get(Bayleef, 0) >= 1 or hand_counts.get(Meganium, 0) >= 1)
                _forest_available = (forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1)

                _can_chain_mega = False
                if _forest_available and hand_counts.get(Bayleef, 0) >= 1:
                    _prot = 1
                    if not forest_in_play:
                        _prot += 1
                    if _hand_total - 1 - _prot >= 2:
                        _can_chain_mega = True
                        ub_best_target = max(ub_best_target, 700)
                if not _can_chain_mega:
                    if _has_mega_evo_in_mazo or _has_mega_evo_in_hand:
                        ub_best_target = max(ub_best_target, 500)
                    else:
                        ub_best_target = max(ub_best_target, 200)

    if not has_hydrapple:
        if _evolvable.get(Dipplin, 0) >= 1:
            if CARTAS_ACTIVAS_EN_MAZO.get(Hydrapple_ex, {}).get(ESTADO_MAZO, 0) > 0:
                ub_best_target = max(ub_best_target, 950)
        elif _evolvable.get(Applin, 0) >= 1 and field_counts.get(Dipplin, 0) >= 1:

            if CARTAS_ACTIVAS_EN_MAZO.get(Hydrapple_ex, {}).get(ESTADO_MAZO, 0) > 0:
                if forest_in_play:
                    ub_best_target = max(ub_best_target, 950)
                else:
                    # Dipplin recien evolucionado ESTE turno (habia Applin al inicio
                    # del turno) y SIN Forest: no se podra evolucionar a Hydrapple ex
                    # hasta el PROXIMO turno. Buscar Hydrapple ahora es solo
                    # preparacion; se rebaja la prioridad para no gastar Ultra Ball +
                    # 2 descartes en una pieza inusable si hay mejores objetivos o
                    # pocos descartes seguros (con >=2 descartes seguros y sin mejor
                    # objetivo aun se busca).
                    ub_best_target = max(ub_best_target, 280)
        elif _evolvable.get(Applin, 0) >= 1:

            if (CARTAS_ACTIVAS_EN_MAZO.get(Dipplin, {}).get(ESTADO_MAZO, 0) > 0
                    and hand_counts.get(Dipplin, 0) == 0):
                # Mismo criterio que Bayleef: no buscar Dipplin si ya hay uno en
                # la mano (un Dipplin basta para evolucionar la unica Applin).
                ub_best_target = max(ub_best_target, 800)

            elif (CARTAS_ACTIVAS_EN_MAZO.get(Hydrapple_ex, {}).get(ESTADO_MAZO, 0) > 0 and
                  (forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1) and
                  hand_counts.get(Dipplin, 0) >= 1):
                _prot = 1
                if not forest_in_play:
                    _prot += 1
                if _hand_total - 1 - _prot >= 2:
                    ub_best_target = max(ub_best_target, 850)
        elif not _bench_full and field_counts.get(Applin, 0) + field_counts.get(Dipplin, 0) == 0:
            if CARTAS_ACTIVAS_EN_MAZO.get(Applin, {}).get(ESTADO_MAZO, 0) > 0:
                _has_hydra_evo_in_mazo = (CARTAS_ACTIVAS_EN_MAZO.get(Dipplin, {}).get(ESTADO_MAZO, 0) > 0 or
                                           CARTAS_ACTIVAS_EN_MAZO.get(Hydrapple_ex, {}).get(ESTADO_MAZO, 0) > 0)
                _has_hydra_evo_in_hand = (hand_counts.get(Dipplin, 0) >= 1 or hand_counts.get(Hydrapple_ex, 0) >= 1)
                _forest_available = (forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1)

                _can_chain_hydra = False
                if _forest_available and hand_counts.get(Dipplin, 0) >= 1:
                    _prot = 1
                    if not forest_in_play:
                        _prot += 1
                    if hand_counts.get(Hydrapple_ex, 0) >= 1:
                        _prot += 1
                    if _hand_total - 1 - _prot >= 2:
                        _can_chain_hydra = True
                        if hand_counts.get(Hydrapple_ex, 0) >= 1:

                            ub_best_target = max(ub_best_target, 950)
                        else:

                            ub_best_target = max(ub_best_target, 600)
                if not _can_chain_hydra:
                    if _has_hydra_evo_in_mazo or _has_hydra_evo_in_hand:
                        ub_best_target = max(ub_best_target, 450)
                    else:
                        ub_best_target = max(ub_best_target, 180)

    if not _bench_full and not has_energy_for_teal and field_counts.get(Teal_Mask_Ogerpon_ex, 0) < 2:
        if CARTAS_ACTIVAS_EN_MAZO.get(Teal_Mask_Ogerpon_ex, {}).get(ESTADO_MAZO, 0) > 0:
            if field_counts.get(Teal_Mask_Ogerpon_ex, 0) == 0 and bench_count <= 2:
                ub_best_target = max(ub_best_target, 350)

    if not _bench_full and field_counts.get(Tapu_Bulu, 0) == 0:
        if CARTAS_ACTIVAS_EN_MAZO.get(Tapu_Bulu, {}).get(ESTADO_MAZO, 0) > 0:
            if meganium_in_play and (op_has_ex_immune_active or op_has_ex_immune_bench):
                val = 750
                if has_hydrapple:
                    val = 850
                ub_best_target = max(ub_best_target, val)

    if not _bench_full and field_counts.get(Pinsir, 0) == 0:
        if CARTAS_ACTIVAS_EN_MAZO.get(Pinsir, {}).get(ESTADO_MAZO, 0) > 0:
            if op_is_crustle_deck or op_is_cornerstone_deck:
                val = 900
                if meganium_in_play:
                    val = 950
                ub_best_target = max(ub_best_target, val)

    if (not _bench_full and not _stamp_blocks_supp_chain and
            not hand_is_weak and not state.supporterPlayed and
            field_counts.get(Meowth_ex, 0) == 0 and supporters_in_hand == 0 and
            _best_supp_in_mazo_val >= 500):
        if CARTAS_ACTIVAS_EN_MAZO.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) > 0:
            if state.turn <= 4:
                ub_best_target = max(ub_best_target, min(_best_supp_in_mazo_val, 500))

    if not _bench_full and field_counts.get(Fezandipiti_ex, 0) == 0:
        if CARTAS_ACTIVAS_EN_MAZO.get(Fezandipiti_ex, {}).get(ESTADO_MAZO, 0) > 0:
            if ko_last_turn:
                ub_best_target = max(ub_best_target, 1050)

    return ub_best_target


# =============================================================================
# DecisionContext + scorers extraidos (refactor Prioridad 1)
# -----------------------------------------------------------------------------
# `agent()` es una unica funcion de ~11.800 lineas cuyo bucle de scoring mezcla
# decenas de reglas en un if/elif gigante. Para reducir ese monolito se estan
# extrayendo las ramas de puntuacion a funciones PURAS `_score_*(ctx)` que leen
# un `DecisionContext` construido una sola vez por decision. Cada extraccion es
# un refactor de comportamiento IDENTICO, verificado por la suite de tests.
#
# Estado del refactor: PoC con la rama de Boss's Orders (`_score_boss_orders_play`).
# Al extraer mas ramas se agregan aqui los campos que necesiten; el objetivo es
# que `agent()` acabe orquestando (construye ctx -> mapea opcion a su scorer ->
# argmax) en vez de contener toda la logica inline.
@dataclass
class DecisionContext:
    """Entradas invariantes de una decision (se construye antes del bucle de
    scoring). Los scorers `_score_*` la tratan como SOLO LECTURA."""
    # Objetos de estado compartidos
    state: object
    my_state: object
    op_state: object
    hand_counts: dict
    field_counts: dict
    supp_values: dict
    cartas_en_mazo: dict
    field_at_turn_start: dict
    # Recuento de tablero / premios
    bench_count: int
    my_hand_len: int
    my_prize: int
    op_prize: int
    op_hand_count: int
    meganium_in_play: bool
    forest_in_play: bool
    itchy_pollen_active: bool
    has_hydrapple: bool
    watchtower_in_play: bool
    neutralization_zone_active: bool
    mega_line_active: bool
    active_needs_energy: bool
    evolve_possible_in_play: bool
    energy_starved_low_draw: bool
    pp_playable_in_hand: bool
    can_attack: bool
    best_supp_in_hand_val: int
    best_supp_in_mazo_val: int
    # Flags de matchup / muros del rival
    op_is_alakazam_deck: bool
    op_is_hop_deck: bool
    op_is_comfey_deck: bool
    op_active_is_dunsparce: bool
    op_has_ability_immune_active: bool
    op_has_ex_immune_active: bool
    op_has_ex_immune_bench: bool
    op_is_control_deck: bool
    op_is_slowking_deck: bool
    op_is_gardevoir_deck: bool
    op_is_zoroark_deck: bool
    op_is_aggro_deck: bool
    op_is_beedrill_deck: bool
    op_is_crustle_deck: bool
    op_is_cornerstone_deck: bool
    op_is_fire_deck: bool
    op_is_mirror: bool
    op_kang_ko_target: bool
    stadium_id: int
    # Flags de turno
    ko_last_turn: bool
    our_first_turn: bool
    active_cant_attack: bool
    bdg_retreat_ko: bool
    supporter_boost: int
    we_go_first: bool
    budew_op_index: int
    budew_on_op_field: bool
    lucario_sac_pivot: bool
    win_via_boss_gust: bool
    gust_2prize_via_boss: bool
    # Flags de Boss's Orders (calculados en evaluate_supporters / mas arriba)
    boss_win_via_bench: bool
    boss_dodge_redirect: bool
    boss_defensive_gust: bool
    boss_deny_alakazam_line: bool
    boss_low_value_gust: bool
    boss_prize_rank: int


def _score_boss_orders_play(ctx: DecisionContext) -> int:
    """Puntua la jugada de Boss's Orders (id 1182). Extraido verbatim de la rama
    `elif card.id == Boss_Orders` del bucle de scoring de agent()."""
    state = ctx.state
    hand_counts = ctx.hand_counts
    if state.supporterPlayed:
        return -1
    if ctx.ko_last_turn and hand_counts.get(Unfair_Stamp, 0) >= 1:
        return -1
    if (ctx.op_is_alakazam_deck and ctx.op_active_is_dunsparce
            and ctx.active_cant_attack):
        # Regla (user): vs mazo Alakazam, con un Dunsparce en el activo rival y
        # nuestro activo SIN poder atacar este turno, NO jugar Boss's Orders:
        # gustear un atacante Psiquico a la banca solo despejaria el muro y les
        # daria via libre para pegar; conviene mantener trabado a Dunsparce.
        return -1

    # Gusteo GANADOR: nuestro ACTIVO noquea a un ex/objetivo de la banca rival y
    # con ello GANA la partida (toma los premios que faltan). Es la mejor jugada
    # posible del turno y debe superar CUALQUIER retirada/pivote defensivo (que
    # puntuan ~6500-6600). Antes, este gusteo ganador se puntuaba como
    # win_via_bench (5600) y perdia contra el pivote de retirada de Hydrapple ex,
    # por lo que el agente RETIRABA en vez de rematar. (user, registro 019 paso
    # 190 vs Dragapult, GANADA: preferir Boss's -> gustear un ex y noquear con el
    # activo, de preferencia Dragapult ex si lo puede derrotar.)
    if ctx.win_via_boss_gust:
        return BOSS_SCORE_WIN_NOW + ctx.supporter_boost

    _boss_val = ctx.supp_values.get(Boss_Orders, 0)
    supporter_boost = ctx.supporter_boost
    # Si nuestro activo NO puede atacar este turno (log 85799299 paso 50) el
    # gusteo NO es ejecutable como remate; con Lillie's en mano refrescar rinde
    # mas, asi que cedemos la prioridad. Se exceptuan los casos valiosos.
    _boss_empty_gust = (
        ctx.active_cant_attack
        and not ctx.boss_win_via_bench
        and not ctx.boss_dodge_redirect
        and not ctx.boss_defensive_gust
        and not ctx.op_has_ability_immune_active
        and not ctx.op_has_ex_immune_active
        and hand_counts.get(Lillie_Determination, 0) >= 1)
    # En NUESTRO primer turno (log 86025936 paso 11) con Lillie's en mano SIEMPRE
    # se juega Lillie's; Boss's cede (un gusteo no cobra premio el primer turno).
    _boss_first_turn_cede = (
        ctx.our_first_turn
        and hand_counts.get(Lillie_Determination, 0) >= 1
        and not state.supporterPlayed
        and not ctx.boss_win_via_bench)
    if _boss_first_turn_cede:
        return BOSS_SCORE_EMPTY_GUST
    if _boss_empty_gust:
        return BOSS_SCORE_EMPTY_GUST
    if (ctx.op_has_ability_immune_active or ctx.op_has_ex_immune_active) and _boss_val >= 900:
        return BOSS_SCORE_WALL_GUST + supporter_boost
    if ctx.boss_dodge_redirect:
        return BOSS_SCORE_DODGE_REDIRECT + supporter_boost
    if ctx.boss_win_via_bench:
        return BOSS_SCORE_WIN_VIA_BENCH + supporter_boost
    if ctx.boss_deny_alakazam_line:
        # Cortar la linea Alakazam: gustear+noquear su pre-evo de banca cuando el
        # activo rival esta fuera de la linea (muro). Registro 010, paso 64.
        return BOSS_SCORE_PRIZE_RANK_BASE + supporter_boost
    if ctx.boss_low_value_gust:
        return BOSS_SCORE_LOW_VALUE_GUST + supporter_boost
    if ctx.boss_prize_rank >= 1:
        return BOSS_SCORE_PRIZE_RANK_BASE + (8 - ctx.boss_prize_rank) * 20 + supporter_boost
    if ctx.boss_defensive_gust:
        return BOSS_SCORE_DEFENSIVE_GUST + supporter_boost
    if _boss_val <= 0:
        return -1
    return 2400 + int(_boss_val * 1.4) + supporter_boost


def _score_unfair_stamp_play(ctx: DecisionContext) -> int:
    """Puntua la jugada de Unfair Stamp (refresco de mano). Extraido verbatim de
    la rama `elif card.id == Unfair_Stamp`. El valor sube cuanto MENOS uso
    alternativo tenga la mano este turno (Pokemon/evo < item < energia < nada)."""
    state = ctx.state
    hand_counts = ctx.hand_counts
    field_counts = ctx.field_counts

    # Regla (user): si tenemos Lillie's Determination en la mano y el rival tiene
    # 3 o menos cartas en la mano, NO jugar Unfair Stamp; se cede la prioridad a
    # Lillie's Determination. Con la mano rival ya tan corta la disrupcion de
    # Unfair Stamp aporta poco, y refrescar NUESTRA mano con Lillie's (robar 6/8)
    # rinde mas. Unfair Stamp baraja la mano (incluida la Lillie's), asi que son
    # jugadas mutuamente excluyentes; se prefiere Lillie's. Solo aplica con el
    # Supporter del turno aun sin jugar (para que Lillie's sea jugable).
    if (hand_counts.get(Lillie_Determination, 0) >= 1
            and ctx.op_hand_count <= 3
            and not state.supporterPlayed):
        return -1

    _us_has_playable_pokemon = False
    if ctx.bench_count < 5:
        if (hand_counts.get(Chikorita, 0) >= 1 and
                field_counts.get(Chikorita, 0) + field_counts.get(Bayleef, 0) + field_counts.get(Meganium, 0) == 0):
            _us_has_playable_pokemon = True
        if (hand_counts.get(Applin, 0) >= 1 and
                field_counts.get(Applin, 0) + field_counts.get(Dipplin, 0) == 0):
            _us_has_playable_pokemon = True
        if (hand_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1 and
                field_counts.get(Teal_Mask_Ogerpon_ex, 0) < 2):
            _us_has_playable_pokemon = True
        if hand_counts.get(Tapu_Bulu, 0) >= 1 and field_counts.get(Tapu_Bulu, 0) == 0:
            _us_has_playable_pokemon = True
        if (hand_counts.get(Meowth_ex, 0) >= 1 and field_counts.get(Meowth_ex, 0) == 0
                and not ctx.ko_last_turn):
            _us_has_playable_pokemon = True
        if hand_counts.get(Fezandipiti_ex, 0) >= 1 and field_counts.get(Fezandipiti_ex, 0) == 0:
            _us_has_playable_pokemon = True

    _us_has_playable_evo = False
    if hand_counts.get(Meganium, 0) >= 1 and field_counts.get(Bayleef, 0) >= 1 and not ctx.meganium_in_play:
        _us_has_playable_evo = True
    if hand_counts.get(Bayleef, 0) >= 1 and field_counts.get(Chikorita, 0) >= 1:
        _us_has_playable_evo = True
    if hand_counts.get(Hydrapple_ex, 0) >= 1 and field_counts.get(Dipplin, 0) >= 1:
        _us_has_playable_evo = True
    if hand_counts.get(Dipplin, 0) >= 1 and field_counts.get(Applin, 0) >= 1:
        _us_has_playable_evo = True

    _us_has_playable_item = False
    if not ctx.itchy_pollen_active:
        if hand_counts.get(Bug_Catching_Set, 0) >= 1:
            _us_has_playable_item = True
        if hand_counts.get(Ultra_Ball, 0) >= 1 and ctx.my_hand_len >= 3:
            _us_has_playable_item = True
        if hand_counts.get(Night_Stretcher, 0) >= 1:
            _us_has_playable_item = True
        if hand_counts.get(Poke_Pad, 0) >= 1:
            _us_has_playable_item = True

    _us_has_energy_play = (hand_counts[Basic_Grass_Energy] >= 1 and not state.energyAttached)
    _us_has_stadium_play = (hand_counts.get(Forest_of_Vitality, 0) >= 1 and not ctx.forest_in_play)

    if _us_has_playable_pokemon or _us_has_playable_evo:
        us_score = 2000
    elif _us_has_playable_item:
        us_score = 2500
    elif _us_has_energy_play or _us_has_stadium_play:
        us_score = 3000
    else:
        us_score = 7500

    if state.turn <= 4:
        us_score += 300
    if ctx.my_prize > ctx.op_prize + 1:
        us_score += 200
    if ctx.op_is_alakazam_deck:
        us_score += 400
    elif ctx.op_is_control_deck or ctx.op_is_slowking_deck:
        us_score += 350
    elif ctx.op_is_gardevoir_deck:
        us_score += 300
    elif ctx.op_is_zoroark_deck:
        us_score += 250
    if (ctx.op_is_aggro_deck or ctx.op_is_beedrill_deck) and ctx.my_prize > ctx.op_prize:
        us_score += 350
    return us_score


def _score_poke_pad_play(ctx: DecisionContext) -> int:
    """Puntua la jugada de Poke Pad (busca un Pokemon SIN Rule Box del mazo).
    Extraido verbatim de la rama `elif card.id == Poke_Pad`. Prioriza habilitar
    una evolucion ESTE turno; si no, asegurar basicos; con banca llena y sin nada
    que evolucionar, guarda el recurso."""
    state = ctx.state
    hand_counts = ctx.hand_counts
    field_counts = ctx.field_counts
    bench_count = ctx.bench_count
    forest_in_play = ctx.forest_in_play
    meganium_in_play = ctx.meganium_in_play
    cartas = ctx.cartas_en_mazo

    pp_score = 9800

    NON_RULEBOX_IDS = (Chikorita, Bayleef, Meganium, Applin, Dipplin, Tapu_Bulu)
    searchable = {}
    for cid in NON_RULEBOX_IDS:
        if cid in cartas and cartas[cid][ESTADO_MAZO] > 0:
            searchable[cid] = cartas[cid][ESTADO_MAZO]

    # Rival abre con Budew en el ACTIVO y vamos SEGUNDOS: su Itchy Pollen bloquea
    # objetos en NUESTRO proximo turno, asi que este primer turno es el UNICO para
    # usar objetos. En ese caso jugamos TODAS las Poke Pad ahora.
    _pp_budew_dump = (ctx.budew_op_index == 0
                      and state.turn == 2 and not ctx.we_go_first)

    if not searchable:
        pp_score = -1

    elif ((state.turn == 1 and ctx.we_go_first) or (state.turn == 2 and not ctx.we_go_first)):
        _pp_have_applin_t1 = (field_counts.get(Applin, 0) >= 1
                              or hand_counts.get(Applin, 0) >= 1)
        _pp_have_chik_t1 = (field_counts.get(Chikorita, 0) >= 1
                            or hand_counts.get(Chikorita, 0) >= 1)
        if (not _pp_have_applin_t1 and Applin in searchable
                and bench_count < 5):
            pp_score = 12800
        elif (not _pp_have_chik_t1 and Chikorita in searchable
                and bench_count < 5):
            pp_score = 12600
        elif _pp_budew_dump:
            pp_score = 12400
        else:
            pp_score = -1

    else:
        _pp_evolvable = ctx.field_at_turn_start if (not forest_in_play and ctx.field_at_turn_start) else field_counts
        _pp_can_evolve_this_turn = False
        _pp_evo_value = 0

        if (Meganium in searchable and not meganium_in_play and
                hand_counts.get(Meganium, 0) == 0):
            if _pp_evolvable.get(Bayleef, 0) >= 1:
                _pp_can_evolve_this_turn = True
                _pp_evo_value = max(_pp_evo_value, 1200)
            elif forest_in_play and _pp_evolvable.get(Chikorita, 0) >= 1 and hand_counts.get(Bayleef, 0) >= 1:
                _pp_can_evolve_this_turn = True
                _pp_evo_value = max(_pp_evo_value, 1100)

        if (Bayleef in searchable and not meganium_in_play and
                hand_counts.get(Bayleef, 0) == 0):
            if _pp_evolvable.get(Chikorita, 0) >= 1:
                _pp_can_evolve_this_turn = True
                _pp_evo_value = max(_pp_evo_value, 1000)
                if forest_in_play and hand_counts.get(Meganium, 0) >= 1:
                    _pp_evo_value = max(_pp_evo_value, 1150)

        if (Dipplin in searchable and
                hand_counts.get(Dipplin, 0) == 0):
            if _pp_evolvable.get(Applin, 0) >= 1:
                _pp_can_evolve_this_turn = True
                _pp_evo_value = max(_pp_evo_value, 950)
                if forest_in_play and hand_counts.get(Hydrapple_ex, 0) >= 1:
                    _pp_evo_value = max(_pp_evo_value, 1100)

        if _pp_can_evolve_this_turn:
            if _pp_evo_value >= 1100:
                pp_score = 23000
            elif _pp_evo_value >= 900:
                pp_score = 22000
            else:
                pp_score = 20000
        else:
            _pp_chik_line_on_bench = (
                field_counts.get(Chikorita, 0) + field_counts.get(Bayleef, 0) + field_counts.get(Meganium, 0)) >= 1
            _pp_chik_in_hand = hand_counts.get(Chikorita, 0) >= 1

            if (Chikorita in searchable and not meganium_in_play and
                    not _pp_chik_line_on_bench and not _pp_chik_in_hand and
                    bench_count < 5):
                pp_score = 12800
            elif Applin in searchable and bench_count < 5:
                pp_score = 12600
            else:
                pp_score = -1

    if (ctx.lucario_sac_pivot and Tapu_Bulu in searchable
            and field_counts.get(Tapu_Bulu, 0) == 0
            and hand_counts.get(Tapu_Bulu, 0) == 0
            and bench_count < 5):
        # Buscar Tapu Bulu para usarlo como sacrificio de 1 premio.
        pp_score = 13000

    # Corte de banca llena (variante estricta): Poke Pad solo busca Pokemon SIN
    # Rule Box, asi que EXCLUYE la linea Dipplin->Hydrapple ex. Con banca llena y
    # sin pre-evo que evolucionar CON UNA BUSQUEDA, se guarda el recurso.
    _pp_evolve_needs_search = (
        (field_counts.get(Chikorita, 0) >= 1 and
         hand_counts.get(Bayleef, 0) == 0 and
         cartas.get(Bayleef, {}).get(ESTADO_MAZO, 0) > 0) or
        (field_counts.get(Bayleef, 0) >= 1 and
         hand_counts.get(Meganium, 0) == 0 and
         cartas.get(Meganium, {}).get(ESTADO_MAZO, 0) > 0) or
        (field_counts.get(Applin, 0) >= 1 and
         hand_counts.get(Dipplin, 0) == 0 and
         cartas.get(Dipplin, {}).get(ESTADO_MAZO, 0) > 0))

    if (bench_count >= 5 and not _pp_evolve_needs_search
            and pp_score > 0 and not _pp_budew_dump):
        pp_score = -1

    return pp_score


def _score_night_stretcher_play(ctx: DecisionContext) -> int:
    """Puntua la jugada de Night Stretcher (recupera un Pokemon o Energia basica
    del descarte). Extraido verbatim de la rama `elif card.id == Night_Stretcher`:
    acumula `best_recovery_value` sobre ~40 escenarios de recuperacion y lo mapea
    a tiers de `ns_score`."""
    # Rebind de campos del contexto para conservar el cuerpo original intacto.
    state = ctx.state
    my_state = ctx.my_state
    op_state = ctx.op_state
    hand_counts = ctx.hand_counts
    field_counts = ctx.field_counts
    bench_count = ctx.bench_count
    forest_in_play = ctx.forest_in_play
    meganium_in_play = ctx.meganium_in_play
    has_hydrapple = ctx.has_hydrapple
    _field_at_turn_start = ctx.field_at_turn_start
    CARTAS_ACTIVAS_EN_MAZO = ctx.cartas_en_mazo
    op_is_crustle_deck = ctx.op_is_crustle_deck
    op_is_cornerstone_deck = ctx.op_is_cornerstone_deck
    ko_last_turn = ctx.ko_last_turn
    watchtower_in_play = ctx.watchtower_in_play
    _best_supp_in_hand_val = ctx.best_supp_in_hand_val
    _best_supp_in_mazo_val = ctx.best_supp_in_mazo_val
    neutralization_zone_active = ctx.neutralization_zone_active
    _active_needs_energy = ctx.active_needs_energy
    _mega_line_active = ctx.mega_line_active
    op_kang_ko_target = ctx.op_kang_ko_target
    _evolve_possible_in_play = ctx.evolve_possible_in_play

    ns_score = -1

    discard_basics = []
    discard_evos = []
    discard_energy = 0
    for c in my_state.discard:
        if c.id == Basic_Grass_Energy:
            discard_energy += 1
        elif c.id in (Chikorita, Applin, Teal_Mask_Ogerpon_ex,
                      Tapu_Bulu, Meowth_ex, Fezandipiti_ex, Pinsir):
            if c.id not in discard_basics:
                discard_basics.append(c.id)
        elif c.id in (Bayleef, Meganium, Dipplin, Hydrapple_ex):
            if c.id not in discard_evos:
                discard_evos.append(c.id)

    best_recovery_value = 0

    if (Applin in discard_basics and
            hand_counts.get(Dipplin, 0) >= 1 and
            hand_counts.get(Hydrapple_ex, 0) >= 1 and
            forest_in_play and bench_count < 5):
        best_recovery_value = max(best_recovery_value, 980)

    if (Dipplin in discard_evos and
            hand_counts.get(Applin, 0) >= 1 and
            hand_counts.get(Hydrapple_ex, 0) >= 1 and
            forest_in_play and bench_count < 5):
        best_recovery_value = max(best_recovery_value, 970)

    if (Applin in discard_basics and
            hand_counts.get(Dipplin, 0) >= 1 and
            forest_in_play and bench_count < 5):
        best_recovery_value = max(best_recovery_value, 900)

    if (Dipplin in discard_evos and
            hand_counts.get(Applin, 0) >= 1 and
            forest_in_play and bench_count < 5):
        best_recovery_value = max(best_recovery_value, 880)

    if (Hydrapple_ex in discard_evos and
            field_counts.get(Applin, 0) >= 1 and
            hand_counts.get(Dipplin, 0) >= 1 and
            forest_in_play):
        best_recovery_value = max(best_recovery_value, 960)

    _ns_evolvable = _field_at_turn_start if (not forest_in_play and _field_at_turn_start) else field_counts
    if (Hydrapple_ex in discard_evos and
            _ns_evolvable.get(Dipplin, 0) >= 1):
        best_recovery_value = max(best_recovery_value, 950)

    if (Chikorita in discard_basics and not meganium_in_play and
            hand_counts.get(Bayleef, 0) >= 1 and
            hand_counts.get(Meganium, 0) >= 1 and
            forest_in_play and bench_count < 5):
        best_recovery_value = max(best_recovery_value, 990)

    if (Bayleef in discard_evos and not meganium_in_play and
            hand_counts.get(Chikorita, 0) >= 1 and
            hand_counts.get(Meganium, 0) >= 1 and
            forest_in_play and bench_count < 5):
        best_recovery_value = max(best_recovery_value, 985)

    if (Chikorita in discard_basics and not meganium_in_play and
            hand_counts.get(Bayleef, 0) >= 1 and
            forest_in_play and bench_count < 5):
        best_recovery_value = max(best_recovery_value, 920)

    if (Bayleef in discard_evos and not meganium_in_play and
            hand_counts.get(Chikorita, 0) >= 1 and
            forest_in_play and bench_count < 5):
        best_recovery_value = max(best_recovery_value, 910)

    if (Meganium in discard_evos and not meganium_in_play and
            field_counts.get(Chikorita, 0) >= 1 and
            hand_counts.get(Bayleef, 0) >= 1 and
            forest_in_play):
        best_recovery_value = max(best_recovery_value, 975)

    if (Meganium in discard_evos and not meganium_in_play and
            _ns_evolvable.get(Bayleef, 0) >= 1):
        best_recovery_value = max(best_recovery_value, 970)

    if (Applin in discard_basics and
            not has_hydrapple and
            field_counts.get(Applin, 0) + field_counts.get(Dipplin, 0) == 0 and
            bench_count < 5):
        best_recovery_value = max(best_recovery_value, 700)

    if (Chikorita in discard_basics and
            not meganium_in_play and
            field_counts.get(Chikorita, 0) + field_counts.get(Bayleef, 0) + field_counts.get(Meganium, 0) == 0 and
            bench_count < 5):
        best_recovery_value = max(best_recovery_value, 750)

    _ns_evolvable_play = _field_at_turn_start if (not forest_in_play and _field_at_turn_start) else field_counts
    if (Dipplin in discard_evos and
            not has_hydrapple and
            hand_counts.get(Dipplin, 0) == 0 and
            _ns_evolvable_play.get(Applin, 0) >= 1):
        if forest_in_play:
            best_recovery_value = max(best_recovery_value, 880)
        else:
            best_recovery_value = max(best_recovery_value, 750)

    if (Bayleef in discard_evos and
            not meganium_in_play and
            hand_counts.get(Bayleef, 0) == 0 and
            _ns_evolvable_play.get(Chikorita, 0) >= 1):
        if forest_in_play:
            best_recovery_value = max(best_recovery_value, 900)
        else:
            best_recovery_value = max(best_recovery_value, 780)

    if (Meganium in discard_evos and
            not meganium_in_play and
            hand_counts.get(Meganium, 0) == 0 and
            _ns_evolvable_play.get(Bayleef, 0) >= 1):
        if forest_in_play:
            best_recovery_value = max(best_recovery_value, 970)
        else:
            best_recovery_value = max(best_recovery_value, 900)

    if (Hydrapple_ex in discard_evos and
            not has_hydrapple and
            hand_counts.get(Hydrapple_ex, 0) == 0 and
            _ns_evolvable_play.get(Dipplin, 0) >= 1):
        if forest_in_play:
            best_recovery_value = max(best_recovery_value, 960)
        else:
            best_recovery_value = max(best_recovery_value, 950)

    if forest_in_play and bench_count < 5:

        if (Applin in discard_basics and
                field_counts.get(Applin, 0) + field_counts.get(Dipplin, 0) + field_counts.get(Hydrapple_ex, 0) == 0 and
                not has_hydrapple and
                (hand_counts.get(Dipplin, 0) >= 1 or
                 CARTAS_ACTIVAS_EN_MAZO.get(Dipplin, {}).get(ESTADO_MAZO, 0) > 0)):
            best_recovery_value = max(best_recovery_value, 870)

        if (Chikorita in discard_basics and
                field_counts.get(Chikorita, 0) + field_counts.get(Bayleef, 0) + field_counts.get(Meganium, 0) == 0 and
                not meganium_in_play and
                (hand_counts.get(Bayleef, 0) >= 1 or
                 CARTAS_ACTIVAS_EN_MAZO.get(Bayleef, {}).get(ESTADO_MAZO, 0) > 0)):
            best_recovery_value = max(best_recovery_value, 890)

    if (Tapu_Bulu in discard_basics and
            field_counts.get(Tapu_Bulu, 0) == 0 and
            op_is_crustle_deck and bench_count < 5):
        best_recovery_value = max(best_recovery_value, 850)

    if (Fezandipiti_ex in discard_basics and
            field_counts.get(Fezandipiti_ex, 0) == 0 and
            ko_last_turn and bench_count < 5):
        best_recovery_value = max(best_recovery_value, 840)

    if (Teal_Mask_Ogerpon_ex in discard_basics and
            hand_counts.get(Basic_Grass_Energy, 0) >= 1 and
            bench_count <= 3):
        best_recovery_value = max(best_recovery_value, 820)

    # Recuperar Meowth ex del descarte para activar el motor de refresco (Meowth
    # ex -> Last-Ditch Catch -> Lillie's). Registro 006, paso 51 vs Alakazam.
    if (Meowth_ex in discard_basics and
            not watchtower_in_play and
            field_counts.get(Meowth_ex, 0) == 0 and
            bench_count < 5 and
            not state.supporterPlayed and
            _best_supp_in_hand_val < 500 and
            _best_supp_in_mazo_val >= 400):
        best_recovery_value = max(best_recovery_value, 830)

    if discard_energy >= 1 and not state.energyAttached:
        _active_pokemon_ns = my_state.active[0] if my_state.active else None
        if _active_pokemon_ns is not None and hand_counts[Basic_Grass_Energy] == 0:
            _act_e = len(_active_pokemon_ns.energies)
            _act_eff = _act_e * _grass_mult()
            _needs_for_attack = False
            _at_max = False
            if _active_pokemon_ns.id == Hydrapple_ex:
                _needs_for_attack = (_act_eff < 2)
                _at_max = (_act_e >= 2)
            elif _active_pokemon_ns.id == Dipplin:
                _needs_for_attack = (_act_e < 1)
                _at_max = (_act_e >= 1)
            elif _active_pokemon_ns.id == Teal_Mask_Ogerpon_ex:
                _needs_for_attack = (_act_eff < 3)
                _at_max = (_act_e >= 3)
            elif _active_pokemon_ns.id == Tapu_Bulu:
                _needs_for_attack = (_act_eff < 4)
                _at_max = (_act_e >= 4)
            elif _active_pokemon_ns.id == Pinsir:
                _needs_for_attack = (_act_eff < 2)
                _at_max = (_act_e >= 2)
            elif _active_pokemon_ns.id in (Chikorita, Bayleef, Meganium):
                _rc = RETREAT_COST.get(_active_pokemon_ns.id, 1)
                _needs_for_attack = (_act_e < _rc)
                _at_max = (_act_e >= _rc)

            if _needs_for_attack and not _at_max:
                best_recovery_value = max(best_recovery_value, 860)

    if discard_energy >= 1 and hand_counts[Basic_Grass_Energy] == 0:
        _act_ns_rc = my_state.active[0] if my_state.active else None
        if (_act_ns_rc is not None and _act_ns_rc.id == Hydrapple_ex
                and len(_act_ns_rc.energies) * _grass_mult() < 2):
            # Hydrapple ex activo que aun no ataca y sin Planta en mano: recuperar
            # una energia del descarte para cargarlo con Ripening Charge.
            best_recovery_value = max(best_recovery_value, 860)

    if (discard_energy >= 1 and hand_counts[Basic_Grass_Energy] == 0 and
            not op_is_crustle_deck and not op_is_cornerstone_deck):
        _act_ns_leth = my_state.active[0] if my_state.active else None
        _opp_ns_leth = op_state.active[0] if (op_state.active and op_state.active[0] is not None) else None
        if (_act_ns_leth is not None and _act_ns_leth.id == Hydrapple_ex and
                _opp_ns_leth is not None):
            _mult_leth = _grass_mult()
            _hyd_eff_leth = len(_act_ns_leth.energies) * _mult_leth
            if _hyd_eff_leth >= 2:
                _syrup_now = calc_syrup_storm_damage(my_state, meganium_in_play)
                _syrup_after = _syrup_now + 30 * _grass_attach_unit()
                _now_eff = _our_effective_damage(
                    _act_ns_leth, _opp_ns_leth, _syrup_now,
                    meganium_in_play, neutralization_zone_active)
                _after_eff = _our_effective_damage(
                    _act_ns_leth, _opp_ns_leth, _syrup_after,
                    meganium_in_play, neutralization_zone_active)
                _opp_hp_leth = _opp_ns_leth.hp or 0
                if _now_eff < _opp_hp_leth <= _after_eff and _after_eff > 0:
                    best_recovery_value = max(best_recovery_value, 950)

    if (discard_energy >= 1 and
            hand_counts[Basic_Grass_Energy] == 0 and
            field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1):

        _ogerpon_can_teal = False
        for _bp in my_state.bench:
            if (_bp is not None and _bp.id == Teal_Mask_Ogerpon_ex
                    and len(_bp.energies) < 3):
                _ogerpon_can_teal = True
                break
        if not _ogerpon_can_teal and my_state.active:
            _act_og = my_state.active[0]
            if (_act_og is not None and _act_og.id == Teal_Mask_Ogerpon_ex
                    and len(_act_og.energies) < 3):
                _ogerpon_can_teal = True

        if _ogerpon_can_teal:
            best_recovery_value = max(best_recovery_value, 800)
        elif not state.energyAttached:
            if _active_needs_energy:
                best_recovery_value = max(best_recovery_value, 860)

    if (_mega_line_active and discard_energy >= 1 and
            hand_counts[Basic_Grass_Energy] == 0 and not state.energyAttached):
        best_recovery_value = max(best_recovery_value, 950)

    if op_is_crustle_deck or op_is_cornerstone_deck:
        if op_is_cornerstone_deck and not op_is_crustle_deck:
            _cc_recover_basics = (Tapu_Bulu, Pinsir)
            _cc_recover_evos = ()
        else:
            _cc_recover_basics = (Tapu_Bulu, Pinsir, Applin, Chikorita)
            _cc_recover_evos = (Dipplin, Bayleef, Meganium)
        _cc_recover_value = 0

        for _cc_b in _cc_recover_basics:
            if _cc_b in discard_basics and bench_count < 5:
                _cc_recover_value = max(_cc_recover_value, 900)

        if (Dipplin in _cc_recover_evos and Dipplin in discard_evos and
                not has_hydrapple and
                (field_counts.get(Applin, 0) >= 1 or
                 hand_counts.get(Applin, 0) >= 1)):
            _cc_recover_value = max(_cc_recover_value, 880)
        if (Bayleef in _cc_recover_evos and Bayleef in discard_evos and
                not meganium_in_play and
                (field_counts.get(Chikorita, 0) >= 1 or
                 hand_counts.get(Chikorita, 0) >= 1)):
            _cc_recover_value = max(_cc_recover_value, 880)
        if (Meganium in _cc_recover_evos and Meganium in discard_evos and
                not meganium_in_play and
                (field_counts.get(Bayleef, 0) >= 1 or
                 hand_counts.get(Bayleef, 0) >= 1)):
            _cc_recover_value = max(_cc_recover_value, 900)

        if (discard_energy >= 1 and
                hand_counts.get(Basic_Grass_Energy, 0) == 0 and
                not state.energyAttached and
                my_state.active and my_state.active[0] is not None and
                my_state.active[0].id == Dipplin and
                len(my_state.active[0].energies) == 0):
            _cc_recover_value = max(_cc_recover_value, 900)

        if (op_kang_ko_target and
                Hydrapple_ex in discard_evos and
                not has_hydrapple and
                (field_counts.get(Dipplin, 0) >= 1 or
                 hand_counts.get(Dipplin, 0) >= 1)):
            _cc_recover_value = max(_cc_recover_value, 960)

        best_recovery_value = _cc_recover_value

    # Matchup de desgaste (Crustle / Cornerstone): recuperar Energia Planta para
    # empezar a CARGAR un atacante de banca antes de refrescar con Lillie's.
    if ((op_is_crustle_deck or op_is_cornerstone_deck) and
            discard_energy >= 1 and
            hand_counts.get(Basic_Grass_Energy, 0) == 0 and
            not state.energyAttached):
        for _ns_bp in (my_state.bench or []):
            if _ns_bp is None:
                continue
            if _ns_bp.id not in (Tapu_Bulu, Teal_Mask_Ogerpon_ex,
                                 Hydrapple_ex, Meganium):
                continue
            _ns_bp_req = ATTACK_ENERGY_REQ.get(_ns_bp.id)
            if _ns_bp_req is None:
                continue
            if len(_ns_bp.energies) * _grass_mult() < _ns_bp_req:
                best_recovery_value = max(best_recovery_value, 850)
                break

    if best_recovery_value >= 900:
        ns_score = 11800
    elif best_recovery_value >= 800:
        ns_score = 11000
    elif best_recovery_value >= 700:
        ns_score = 10400
    elif best_recovery_value > 0:
        ns_score = 9800

    # Corte de banca llena (igual que Ultra Ball / Poke Pad), con excepciones:
    # energia basica util o una pre-evo en juego cuya siguiente etapa este en el
    # descarte (se recupera y evoluciona).
    _ns_energy_useful = (
        discard_energy >= 1 and
        hand_counts.get(Basic_Grass_Energy, 0) == 0 and
        not state.energyAttached)
    if (discard_energy >= 1 and
            hand_counts.get(Basic_Grass_Energy, 0) == 0 and
            my_state.active and my_state.active[0] is not None and
            my_state.active[0].id == Hydrapple_ex and
            len(my_state.active[0].energies) * _grass_mult() < 2):
        _ns_energy_useful = True
    _ns_something_to_evolve = _evolve_possible_in_play or (
        (field_counts.get(Chikorita, 0) >= 1 and Bayleef in discard_evos) or
        (field_counts.get(Bayleef, 0) >= 1 and Meganium in discard_evos) or
        (field_counts.get(Applin, 0) >= 1 and Dipplin in discard_evos) or
        (field_counts.get(Dipplin, 0) >= 1 and Hydrapple_ex in discard_evos))
    if (bench_count >= 5 and not _ns_something_to_evolve
            and not _ns_energy_useful and ns_score > 0):
        ns_score = -1

    if (op_kang_ko_target and
            Hydrapple_ex in discard_evos and
            not has_hydrapple and
            (field_counts.get(Dipplin, 0) >= 1 or
             hand_counts.get(Dipplin, 0) >= 1)):
        ns_score = 34000

    return ns_score


def _score_forest_of_vitality_play(ctx: DecisionContext) -> int:
    """Puntua la jugada de Forest of Vitality (estadio que permite evolucionar el
    mismo turno). Extraido verbatim de la rama `if card.id == Forest_of_Vitality`
    (se elimino un print de depuracion residual que no afectaba al score)."""
    state = ctx.state
    hand_counts = ctx.hand_counts
    field_counts = ctx.field_counts
    meganium_in_play = ctx.meganium_in_play
    has_hydrapple = ctx.has_hydrapple
    stadium_id = ctx.stadium_id
    we_go_first = ctx.we_go_first

    _our_first_turn_first = we_go_first and state.turn == 1
    _our_first_turn_second = (not we_go_first) and state.turn == 2
    if _our_first_turn_first:
        return -1
    if _our_first_turn_second and stadium_id == 0:
        return -1
    if _our_first_turn_second and stadium_id != 0 and stadium_id != Forest_of_Vitality:
        return 15000
    if stadium_id == Forest_of_Vitality:
        return -1

    if ctx.neutralization_zone_active:
        score = 28000
        if (field_counts.get(Chikorita, 0) >= 1 or
                field_counts.get(Applin, 0) >= 1 or
                field_counts.get(Dipplin, 0) >= 1):
            score = 29000
        return score

    _evo_chain = False

    # Meganium buscable en el mazo con un buscador en mano (Poke Pad / Ultra Ball):
    # jugar Forest habilita evolucionar ESTE turno un Bayleef hasta Meganium.
    _meg_fetchable_fv = (
        ctx.cartas_en_mazo.get(Meganium, {}).get(ESTADO_MAZO, 0) > 0 and
        (hand_counts.get(Poke_Pad, 0) >= 1 or
         hand_counts.get(Ultra_Ball, 0) >= 1))

    if field_counts.get(Chikorita, 0) >= 1 and not meganium_in_play:
        if hand_counts.get(Bayleef, 0) >= 1 or hand_counts.get(Meganium, 0) >= 1:
            _evo_chain = True
    if field_counts.get(Bayleef, 0) >= 1 and not meganium_in_play:
        if hand_counts.get(Meganium, 0) >= 1 or _meg_fetchable_fv:
            _evo_chain = True
    if field_counts.get(Applin, 0) >= 1:
        if hand_counts.get(Dipplin, 0) >= 1 or hand_counts.get(Hydrapple_ex, 0) >= 1:
            _evo_chain = True
    if field_counts.get(Dipplin, 0) >= 1 and not has_hydrapple:
        if hand_counts.get(Hydrapple_ex, 0) >= 1:
            _evo_chain = True

    if (hand_counts.get(Chikorita, 0) >= 1 and
            field_counts[Chikorita] + field_counts[Bayleef] + field_counts[Meganium] == 0 and
            hand_counts.get(Bayleef, 0) >= 1):
        _evo_chain = True
    if (hand_counts.get(Applin, 0) >= 1 and
            field_counts[Applin] + field_counts[Dipplin] == 0 and
            hand_counts.get(Dipplin, 0) >= 1):
        _evo_chain = True

    if _evo_chain:
        score = 21900
        if stadium_id != 0:
            score = 22000
        if ctx.op_is_fire_deck or ctx.op_is_aggro_deck or ctx.op_is_beedrill_deck:
            score += 200
    elif stadium_id != 0:
        score = 15000
    elif state.turn <= 4:
        score = 14000
        if ctx.op_is_fire_deck or ctx.op_is_aggro_deck or ctx.op_is_mirror:
            score = 15000
    else:
        score = 8000
    return score


def _score_bug_catching_set_play(ctx: DecisionContext) -> int:
    """Puntua la jugada de Bug Catching Set (mira 7 cartas del mazo y coge una
    Planta/Energia). Extraido verbatim de la rama `elif card.id == Bug_Catching_Set`:
    estima la probabilidad de encontrar algo util y el valor de las piezas de
    evolucion disponibles."""
    state = ctx.state
    hand_counts = ctx.hand_counts
    field_counts = ctx.field_counts
    meganium_in_play = ctx.meganium_in_play
    has_hydrapple = ctx.has_hydrapple
    CARTAS_ACTIVAS_EN_MAZO = ctx.cartas_en_mazo

    bcs_score = 10500

    ogerpon_on_bench = field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1
    has_energy_for_teal = hand_counts[Basic_Grass_Energy] >= 1

    if ogerpon_on_bench and has_energy_for_teal:
        bcs_score -= 100

    grass_pokemon_in_mazo = 0
    energy_in_mazo = 0
    high_value_in_mazo = 0

    for cid, states in CARTAS_ACTIVAS_EN_MAZO.items():
        if states[ESTADO_MAZO] <= 0:
            continue
        copies_in_mazo = states[ESTADO_MAZO]
        cdata = card_table.get(cid)
        if cid == Basic_Grass_Energy:
            energy_in_mazo += copies_in_mazo
        elif cdata and cdata.cardType == CardType.POKEMON:

            if cdata.energyType == EnergyType.GRASS:
                grass_pokemon_in_mazo += copies_in_mazo

                if cid == Meganium and not meganium_in_play and (field_counts.get(Bayleef, 0) >= 1 or field_counts.get(Chikorita, 0) >= 1):
                    high_value_in_mazo += copies_in_mazo
                elif cid == Hydrapple_ex and not has_hydrapple and (field_counts.get(Dipplin, 0) >= 1 or field_counts.get(Applin, 0) >= 1):
                    high_value_in_mazo += copies_in_mazo
                elif cid == Bayleef and not meganium_in_play and field_counts.get(Chikorita, 0) >= 1:
                    high_value_in_mazo += copies_in_mazo
                elif cid == Dipplin and not has_hydrapple and field_counts.get(Applin, 0) >= 1:
                    high_value_in_mazo += copies_in_mazo
                elif cid == Chikorita and not meganium_in_play and field_counts.get(Chikorita, 0) + field_counts.get(Bayleef, 0) + field_counts.get(Meganium, 0) == 0:
                    high_value_in_mazo += copies_in_mazo
                elif cid == Applin and not has_hydrapple and field_counts.get(Applin, 0) + field_counts.get(Dipplin, 0) + field_counts.get(Hydrapple_ex, 0) == 0:
                    high_value_in_mazo += copies_in_mazo
                elif cid == Teal_Mask_Ogerpon_ex and field_counts.get(Teal_Mask_Ogerpon_ex, 0) < 2:
                    high_value_in_mazo += copies_in_mazo

    total_eligible_in_mazo = grass_pokemon_in_mazo + energy_in_mazo
    total_mazo = sum(v[ESTADO_MAZO] for v in CARTAS_ACTIVAS_EN_MAZO.values())

    if total_eligible_in_mazo == 0:
        bcs_score = -1
    else:

        if total_mazo <= 7:
            p_find = 1.0 if total_eligible_in_mazo > 0 else 0.0
        else:
            p_miss_all = 1.0
            remaining = total_mazo
            eligible_remaining = total_eligible_in_mazo
            for _ in range(min(7, total_mazo)):
                if remaining <= 0:
                    break
                p_miss_all *= (remaining - eligible_remaining) / remaining
                remaining -= 1
            p_find = 1.0 - p_miss_all

        if p_find >= 0.9:
            bcs_score += 800
        elif p_find >= 0.7:
            bcs_score += 500
        elif p_find >= 0.5:
            bcs_score += 200
        else:
            bcs_score -= 300

        if high_value_in_mazo >= 3:
            bcs_score += 600
        elif high_value_in_mazo >= 2:
            bcs_score += 400
        elif high_value_in_mazo >= 1:
            bcs_score += 200

        if not meganium_in_play and not has_hydrapple:
            bcs_score += 300
        elif not meganium_in_play or not has_hydrapple:
            bcs_score += 150

        if hand_counts[Basic_Grass_Energy] == 0 and not state.energyAttached:
            bcs_score += 200

            if ctx.energy_starved_low_draw and energy_in_mazo > 0:
                bcs_score += SCORE_BELIEF_DIG_ENERGY

    score = bcs_score

    if ctx.pp_playable_in_hand and not ctx.itchy_pollen_active and score > 9000:
        score = 9000
    return score


class _UBFlags(NamedTuple):
    survival_mode: bool
    first_action_turn: bool
    hand_size: int
    evolve_needs_search: bool
    evolve_now_search: bool
    developed_attacker_board: bool


def _ub_derive_flags(ctx) -> _UBFlags:
    """Fase A de _score_ultra_ball_play: flags derivados del contexto (modo
    supervivencia, primer turno, busquedas de evolucion, tablero desarrollado,
    tamano de mano). Cuerpo verbatim (Paso 2 del plan)."""
    state = ctx.state
    my_state = ctx.my_state
    hand_counts = ctx.hand_counts
    field_counts = ctx.field_counts
    bench_count = ctx.bench_count
    we_go_first = ctx.we_go_first
    forest_in_play = ctx.forest_in_play
    can_attack = ctx.can_attack
    _field_at_turn_start = ctx.field_at_turn_start
    CARTAS_ACTIVAS_EN_MAZO = ctx.cartas_en_mazo
    op_is_crustle_deck = ctx.op_is_crustle_deck
    op_has_ex_immune_active = ctx.op_has_ex_immune_active
    op_has_ex_immune_bench = ctx.op_has_ex_immune_bench

    _ub_survival_mode = False
    _our_first_action_turn = (
        (state.turn == 1 and we_go_first) or
        (state.turn == 2 and not we_go_first))
    if bench_count == 0 and _our_first_action_turn:
        _ub_survival_mode = True

    elif bench_count == 0 and state.turn >= 2:
        _ub_survival_mode = True

    # Variante ESTRICTA de _evolve_possible_in_play SOLO para el
    # corte de banca llena de Ultra Ball: la excepcion de "hay algo
    # que evolucionar" unicamente cuenta cuando la pieza de
    # evolucion FALTA en la mano y esta en el MAZO (hace falta
    # buscarla con Ultra Ball). Si la evolucion YA esta en la mano,
    # la linea se evoluciona sin Ultra Ball, asi que buscar con ella
    # solo traeria una carta inutil/redundante (banca llena) y hasta
    # podria descartar la propia evolucion como coste.
    # NOTA (user, log 86028607 paso 47, vs Crustle): la busqueda de
    # Hydrapple ex (evolucion del Dipplin) NO cuenta si el rival es
    # inmune a ex (Crustle): la rama TO_HAND rebaja ese objetivo a
    # 40 (carta muerta), asi que la Ultra Ball nunca lo traeria; sin
    # esta excepcion la busqueda "fantasma" de Hydrapple ex saltaba
    # el corte de banca llena y jugaba una Ultra Ball inutil.
    _ub_op_ex_immune = (op_is_crustle_deck or
                        op_has_ex_immune_active or
                        op_has_ex_immune_bench)
    _ub_evolve_needs_search = (
        (field_counts.get(Chikorita, 0) >= 1 and
         hand_counts.get(Bayleef, 0) == 0 and
         CARTAS_ACTIVAS_EN_MAZO.get(Bayleef, {}).get(ESTADO_MAZO, 0) > 0) or
        (field_counts.get(Bayleef, 0) >= 1 and
         hand_counts.get(Meganium, 0) == 0 and
         CARTAS_ACTIVAS_EN_MAZO.get(Meganium, {}).get(ESTADO_MAZO, 0) > 0) or
        (field_counts.get(Applin, 0) >= 1 and
         hand_counts.get(Dipplin, 0) == 0 and
         CARTAS_ACTIVAS_EN_MAZO.get(Dipplin, {}).get(ESTADO_MAZO, 0) > 0) or
        (field_counts.get(Dipplin, 0) >= 1 and
         hand_counts.get(Hydrapple_ex, 0) == 0 and
         CARTAS_ACTIVAS_EN_MAZO.get(Hydrapple_ex, {}).get(ESTADO_MAZO, 0) > 0 and
         not _ub_op_ex_immune))

    # Variante de _ub_evolve_needs_search que ademas exige poder
    # COMPLETAR la evolucion ESTE turno: la pre-evolucion debe
    # poder evolucionar ya (hay Forest of Vitality en juego o la
    # pre-evo estaba en juego al inicio del turno, no salio este
    # turno). Si es asi, buscar con Ultra Ball desarrolla la linea
    # de evolucion AHORA, asi que NO se debe posponer frente a
    # Lillie's Determination (se evoluciona primero y Lillie's se
    # juega despues, sin barajar las piezas ya en mesa).
    _ub_evolve_now_search = (
        (field_counts.get(Chikorita, 0) >= 1 and
         hand_counts.get(Bayleef, 0) == 0 and
         CARTAS_ACTIVAS_EN_MAZO.get(Bayleef, {}).get(ESTADO_MAZO, 0) > 0 and
         (forest_in_play or _field_at_turn_start.get(Chikorita, 0) >= 1)) or
        (field_counts.get(Bayleef, 0) >= 1 and
         hand_counts.get(Meganium, 0) == 0 and
         CARTAS_ACTIVAS_EN_MAZO.get(Meganium, {}).get(ESTADO_MAZO, 0) > 0 and
         (forest_in_play or _field_at_turn_start.get(Bayleef, 0) >= 1)) or
        (field_counts.get(Applin, 0) >= 1 and
         hand_counts.get(Dipplin, 0) == 0 and
         CARTAS_ACTIVAS_EN_MAZO.get(Dipplin, {}).get(ESTADO_MAZO, 0) > 0 and
         (forest_in_play or _field_at_turn_start.get(Applin, 0) >= 1)) or
        (field_counts.get(Dipplin, 0) >= 1 and
         hand_counts.get(Hydrapple_ex, 0) == 0 and
         CARTAS_ACTIVAS_EN_MAZO.get(Hydrapple_ex, {}).get(ESTADO_MAZO, 0) > 0 and
         (forest_in_play or _field_at_turn_start.get(Dipplin, 0) >= 1) and
         not _ub_op_ex_immune))

    # Regla (user, log 86028035 paso 53): si YA tenemos un
    # atacante LISTO en el activo (existe opcion de ATACAR este
    # turno) y la banca ya tiene >=2 Pokemon energizados
    # (atacantes potenciales), la Ultra Ball NO debe jugarse para
    # DESARROLLAR mas atacantes de bajo valor descartando energia
    # / Lillie's Determination utiles: conviene atacar y conservar
    # los recursos. Solo se veta el desarrollo redundante; los
    # objetivos de alto valor (>=800: cadena Meowth->Lillie, piezas
    # de evolucion) y las busquedas que habilitan una evolucion
    # pendiente siguen permitidos.
    _ub_bench_energized = sum(
        1 for _ubp in (my_state.bench or [])
        if _ubp is not None and len(_ubp.energies) >= 1)
    _ub_developed_attacker_board = (
        can_attack and _ub_bench_energized >= 2)

    hand_size = len(my_state.hand) if my_state.hand else 0

    return _UBFlags(
        survival_mode=_ub_survival_mode,
        first_action_turn=_our_first_action_turn,
        hand_size=hand_size,
        evolve_needs_search=_ub_evolve_needs_search,
        evolve_now_search=_ub_evolve_now_search,
        developed_attacker_board=_ub_developed_attacker_board)


def _ub_terminal_overrides(ctx, ub_score, _ub_survival_mode, hand_size, _our_first_action_turn):
    """Fase E de _score_ultra_ball_play: overrides terminales sobre `ub_score`
    ya calculado (rescate supervivencia, Bug Set, gate primer turno, salvaguarda
    banca llena, deferral linea Alakazam). SIEMPRE se aplica; hila y devuelve
    ub_score. Cuerpo verbatim (Paso 2 del plan)."""
    hand_counts = ctx.hand_counts
    state = ctx.state
    bench_count = ctx.bench_count
    field_counts = ctx.field_counts
    itchy_pollen_active = ctx.itchy_pollen_active
    we_go_first = ctx.we_go_first
    watchtower_in_play = ctx.watchtower_in_play
    budew_on_op_field = ctx.budew_on_op_field
    budew_op_index = ctx.budew_op_index
    CARTAS_ACTIVAS_EN_MAZO = ctx.cartas_en_mazo
    _evolve_possible_in_play = ctx.evolve_possible_in_play
    _boss_deny_alakazam_line = ctx.boss_deny_alakazam_line

    _ub_lillie_in_hand_playable = (
        hand_counts.get(Lillie_Determination, 0) >= 1 and
        not state.supporterPlayed)
    # El rescate de supervivencia solo tiene sentido con HUECO en banca: busca
    # un Basico para bajarlo y desarrollar/defender. Con la banca LLENA
    # (bench_count >= 5) no se puede banquear nada, asi que buscar un Basico solo
    # lo llevaria muerto a la mano (pagando 2 descartes). Sin este `bench_count
    # < 5`, el rescate resucitaba la Ultra Ball (a 25000) pese al corte de banca
    # llena, jugando una Ultra Ball inutil (user, registro 006 paso 72 vs Hops,
    # PERDIDA: banca llena, buscaba un Applin que no podia jugar).
    if (_ub_survival_mode and ub_score <= 0 and hand_size >= 3 and
            bench_count < 5 and
            not _ub_lillie_in_hand_playable):

        _ub_has_playable_basic_in_hand = False
        if bench_count < 5:
            for _surv_hand_id in (Chikorita, Applin, Teal_Mask_Ogerpon_ex,
                                  Tapu_Bulu, Meowth_ex, Fezandipiti_ex, Pinsir):
                if hand_counts.get(_surv_hand_id, 0) >= 1:
                    _ub_has_playable_basic_in_hand = True
                    break
        if not _ub_has_playable_basic_in_hand:

            _ub_has_basic_in_mazo = False
            for _surv_id in (Chikorita, Applin, Teal_Mask_Ogerpon_ex,
                             Tapu_Bulu, Meowth_ex, Fezandipiti_ex, Pinsir):
                if CARTAS_ACTIVAS_EN_MAZO.get(_surv_id, {}).get(ESTADO_MAZO, 0) > 0:
                    _ub_has_basic_in_mazo = True
                    break
            if _ub_has_basic_in_mazo:
                ub_score = 25000

    if (hand_counts.get(Bug_Catching_Set, 0) >= 1 and
            not itchy_pollen_active and
            ub_score > 0 and ub_score < 25000):
        ub_score -= 1500

    _ub_first_turn_allowed = True
    if _our_first_action_turn:
        _ub_ft_case1 = (bench_count == 0)
        _ub_ft_case2 = (
            (not we_go_first) and
            not watchtower_in_play and
            hand_counts.get(Meowth_ex, 0) == 0 and
            hand_counts.get(Lillie_Determination, 0) == 0 and
            not state.supporterPlayed and
            field_counts.get(Meowth_ex, 0) < 2 and
            bench_count < 5 and
            CARTAS_ACTIVAS_EN_MAZO.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) > 0 and
            CARTAS_ACTIVAS_EN_MAZO.get(Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0)
        _ub_ft_case3 = (
            (not we_go_first) and
            not watchtower_in_play and
            budew_on_op_field and budew_op_index == 0)
        _ub_first_turn_allowed = (
            _ub_ft_case1 or _ub_ft_case2 or _ub_ft_case3)
    if not _ub_first_turn_allowed:
        ub_score = -1

    # SALVAGUARDA FINAL de banca llena (user, log 86210257
    # paso 86, GANADA vs Mega Starmie). Control EXTRA que tiene
    # la ULTIMA palabra sobre cualquier ruta anterior que
    # hubiera dejado ub_score > 0: con la banca LLENA
    # (bench_count >= 5) y SIN ninguna evolucion que completar
    # en juego (`_evolve_possible_in_play` = no hay una
    # pre-evolucion en mesa cuya siguiente etapa este en mano o
    # en el mazo), Ultra Ball no puede banquear nada nuevo y
    # solo malgasta su coste (descartar 2 cartas utiles, p.ej.
    # un Hydrapple ex + Forest of Vitality) para traer una
    # carta MUERTA a la mano (un Chikorita que no cabe en
    # banca). Duplica el corte de L9029/L9220 pero como override
    # terminal, para que ninguna rama intermedia pueda
    # reactivarla. UNICA excepcion: modo supervivencia (banca
    # vacia), donde bench_count>=5 ya es False de por si.
    if (bench_count >= 5
            and not _evolve_possible_in_play
            and not _ub_survival_mode):
        # -100 (por debajo del piso de veto -1) para que, si el resto de
        # jugadas del turno tambien estan vetadas (ataque/retirada = -1), el
        # argmax prefiera ATACAR/PASAR antes que malgastar esta Ultra Ball
        # inutil por defecto (indice 0). (user, registro 006 paso 72 vs Hops.)
        ub_score = -100

    # Secuencia (user, registro 010, paso 64 vs Alakazam): si esta
    # activo el corte de la linea Alakazam (`_boss_deny_alakazam_line`)
    # y todavia tenemos el Boss's Orders en la mano sin jugar,
    # POSPONER la Ultra Ball: jugarla ahora descartaria el propio
    # Boss's como coste (a menudo es el unico fodder). Se rebaja por
    # debajo del Boss's (BOSS_SCORE_PRIZE_RANK_BASE) para que el
    # gusteo se ejecute primero; una vez jugado el Boss's, esta
    # guarda deja de aplicar y la Ultra Ball recupera su score.
    if (_boss_deny_alakazam_line and ub_score > 2000
            and hand_counts.get(Boss_Orders, 0) >= 1
            and not state.supporterPlayed):
        ub_score = 2000

    return ub_score


def _ub_cancel_stamp(ctx) -> bool:
    """Fase C de Ultra Ball: veto por coste (stamp). ¿Jugar UB descartaria
    una carta valiosa como su coste de 2? Predicado puro; conteo verbatim."""
    hand_counts = ctx.hand_counts
    field_counts = ctx.field_counts
    bench_count = ctx.bench_count
    state = ctx.state
    ko_last_turn = ctx.ko_last_turn
    op_is_crustle_deck = ctx.op_is_crustle_deck
    op_has_ex_immune_active = ctx.op_has_ex_immune_active
    op_has_ex_immune_bench = ctx.op_has_ex_immune_bench
    has_hydrapple = ctx.has_hydrapple
    forest_in_play = ctx.forest_in_play
    meganium_in_play = ctx.meganium_in_play
    CARTAS_ACTIVAS_EN_MAZO = ctx.cartas_en_mazo

    _ub_cancel_for_stamp = False
    if hand_counts.get(Unfair_Stamp, 0) >= 1:

        # Las COPIAS SOBRANTES de Ultra Ball (todas menos la
        # que se juega) SI son fodder valido para pagar el
        # coste sin tocar Unfair Stamp. Antes se excluian TODAS
        # las Ultra Ball del conteo, asi que con mano {Unfair
        # Stamp, Ultra Ball, Ultra Ball, Lana's Aid} solo veia
        # 1 descartable (Lana's) y cancelaba la Ultra Ball,
        # terminando el turno sin buscar (user, log 86403004
        # paso 17, PERDIDA vs Iono): la 2a Ultra Ball + Lana's
        # Aid pagan el coste, protegen el Stamp y buscan Meowth
        # ex -> Lillie's.
        _ub_discardable_without_stamp = max(
            0, hand_counts.get(Ultra_Ball, 0) - 1)
        for _ub_sid, _ub_scnt in hand_counts.items():
            if _ub_sid in (Ultra_Ball, Unfair_Stamp):
                continue
            _ub_discardable_without_stamp += _ub_scnt
        if _ub_discardable_without_stamp < 2:

            _ub_cancel_for_stamp = True

    return _ub_cancel_for_stamp


def _ub_cancel_fez(ctx) -> bool:
    """Fase C de Ultra Ball: veto por coste (fez). ¿Jugar UB descartaria
    una carta valiosa como su coste de 2? Predicado puro; conteo verbatim."""
    hand_counts = ctx.hand_counts
    field_counts = ctx.field_counts
    bench_count = ctx.bench_count
    state = ctx.state
    ko_last_turn = ctx.ko_last_turn
    op_is_crustle_deck = ctx.op_is_crustle_deck
    op_has_ex_immune_active = ctx.op_has_ex_immune_active
    op_has_ex_immune_bench = ctx.op_has_ex_immune_bench
    has_hydrapple = ctx.has_hydrapple
    forest_in_play = ctx.forest_in_play
    meganium_in_play = ctx.meganium_in_play
    CARTAS_ACTIVAS_EN_MAZO = ctx.cartas_en_mazo

    _ub_cancel_for_fez = False
    if (ko_last_turn and
            hand_counts.get(Fezandipiti_ex, 0) >= 1 and
            field_counts.get(Fezandipiti_ex, 0) == 0 and
            bench_count < 5):

        _ub_discardable_without_fez = 0
        for _ub_fid, _ub_fcnt in hand_counts.items():
            if _ub_fid in (Ultra_Ball, Fezandipiti_ex, Unfair_Stamp):
                continue
            _ub_discardable_without_fez += _ub_fcnt
        if _ub_discardable_without_fez < 2:

            _ub_cancel_for_fez = True

    return _ub_cancel_for_fez


def _ub_cancel_lillie(ctx) -> bool:
    """Fase C de Ultra Ball: veto por coste (lillie). ¿Jugar UB descartaria
    una carta valiosa como su coste de 2? Predicado puro; conteo verbatim."""
    hand_counts = ctx.hand_counts
    field_counts = ctx.field_counts
    bench_count = ctx.bench_count
    state = ctx.state
    ko_last_turn = ctx.ko_last_turn
    op_is_crustle_deck = ctx.op_is_crustle_deck
    op_has_ex_immune_active = ctx.op_has_ex_immune_active
    op_has_ex_immune_bench = ctx.op_has_ex_immune_bench
    has_hydrapple = ctx.has_hydrapple
    forest_in_play = ctx.forest_in_play
    meganium_in_play = ctx.meganium_in_play
    CARTAS_ACTIVAS_EN_MAZO = ctx.cartas_en_mazo

    # CANCELAR Ultra Ball si su coste sacrificaria un
    # Lillie's Determination sin haber jugado partidario
    # (user, log 86210811 paso 36/37, GANADA). Escenario:
    # mano pequena {Unfair Stamp, Fezandipiti ex, Ultra
    # Ball, Lillie's}, supporterPlayed=False. El coste de
    # Ultra Ball (descartar 2) protege Unfair Stamp
    # (-10000) y termina descartando Fezandipiti +
    # Lillie's, tirando el partidario a la basura. Lillie's
    # (baraja la mano y roba 6/8) es una jugada MUCHO mejor
    # y debe tener prioridad. Contamos las cartas realmente
    # descartables SIN tocar Lillie's; excluimos tambien
    # Unfair Stamp porque nunca se descarta (score -10000),
    # asi que no puede pagar el coste. Si quedan <2, para
    # pagar Ultra Ball habria que descartar el Lillie's ->
    # se cancela y el partidario gana la decision.
    # AJUSTE (user, log 86401283 paso 32, GANADA vs Alakazam):
    # el conteo INGENUO (toda carta != UB/Lillie's/Unfair
    # Stamp) sobrecontaba fodder. Con mano {UB, Hydrapple ex,
    # Lillie's, Grass} y un Applin en banca, Hydrapple ex es
    # OBJETIVO de evolucion: el scorer de DISCARD lo protege
    # (score 3, POR DEBAJO del Lillie's protegido ~5), asi que
    # NUNCA se descarta y en su lugar cae Lillie's. El conteo
    # ingenuo veia 2 "descartables" (Hydrapple + Grass) y NO
    # cancelaba, tirando el partidario. Ahora solo se cuenta
    # como fodder lo que el scorer de DISCARD SI soltaria antes
    # que Lillie's: se EXCLUYEN las piezas de evolucion / Fez
    # en estado PROTEGIDO (mismos criterios de score bajo del
    # bloque SelectContext.DISCARD).
    _ub_cancel_for_lillie = False
    if (not state.supporterPlayed and
            hand_counts.get(Lillie_Determination, 0) >= 1):

        _ub_discardable_without_lillie = 0
        for _ub_llid, _ub_llcnt in hand_counts.items():
            if _ub_llid in (Ultra_Ball, Lillie_Determination, Unfair_Stamp):
                continue
            _ub_ll_fodder = True
            if _ub_llid == Hydrapple_ex:
                if (op_is_crustle_deck or op_has_ex_immune_active or
                        op_has_ex_immune_bench):
                    _ub_ll_fodder = True
                elif has_hydrapple:
                    _ub_ll_fodder = True
                elif (field_counts.get(Dipplin, 0) >= 1 or
                      field_counts.get(Applin, 0) >= 1):
                    _ub_ll_fodder = False
                elif (hand_counts.get(Dipplin, 0) >= 1 and
                      (forest_in_play or
                       hand_counts.get(Forest_of_Vitality, 0) >= 1) and
                      CARTAS_ACTIVAS_EN_MAZO.get(Applin, {}).get(ESTADO_MAZO, 0) > 0):
                    _ub_ll_fodder = False
            elif _ub_llid == Dipplin:
                if (has_hydrapple and
                        not (op_has_ex_immune_active or op_has_ex_immune_bench)):
                    _ub_ll_fodder = True
                elif field_counts.get(Applin, 0) >= 1:
                    _ub_ll_fodder = False
                elif (hand_counts.get(Hydrapple_ex, 0) >= 1 and
                      (forest_in_play or
                       hand_counts.get(Forest_of_Vitality, 0) >= 1) and
                      CARTAS_ACTIVAS_EN_MAZO.get(Applin, {}).get(ESTADO_MAZO, 0) > 0):
                    _ub_ll_fodder = False
            elif _ub_llid == Meganium:
                _ub_ll_fodder = not (field_counts.get(Bayleef, 0) >= 1)
            elif _ub_llid == Bayleef:
                _ub_ll_fodder = not (field_counts.get(Chikorita, 0) >= 1)
            elif _ub_llid == Fezandipiti_ex:
                if (ko_last_turn and
                        field_counts.get(Fezandipiti_ex, 0) == 0 and
                        bench_count < 5):
                    _ub_ll_fodder = False
            elif _ub_llid == Meowth_ex:
                # Meowth ex esta PROTEGIDO por el scorer de
                # DISCARD (score 2) salvo que: ya tengamos uno
                # en juego (score 82) o la banca este llena Y ya
                # se jugo el supporter del turno (score 65). Solo
                # en esos dos casos es fodder real; en cualquier
                # otro el scorer lo CONSERVA y suelta Lillie's en
                # su lugar (user, log 86412738 paso 115, GANADA
                # vs Hops: mano {UB, Lana's Aid, Lillie's, Meowth
                # ex} con banca llena y supporter sin jugar ->
                # descartaba Lana's + Lillie's y guardaba un
                # Meowth ex ni siquiera jugable).
                if field_counts.get(Meowth_ex, 0) >= 1:
                    _ub_ll_fodder = True
                elif bench_count >= 5 and state.supporterPlayed:
                    _ub_ll_fodder = True
                else:
                    _ub_ll_fodder = False
            if _ub_ll_fodder:
                _ub_discardable_without_lillie += _ub_llcnt
        if _ub_discardable_without_lillie < 2:

            _ub_cancel_for_lillie = True

    return _ub_cancel_for_lillie


def _ub_cancel_meowth(ctx) -> bool:
    """Fase C de Ultra Ball: veto por coste (meowth). ¿Jugar UB descartaria
    una carta valiosa como su coste de 2? Predicado puro; conteo verbatim."""
    hand_counts = ctx.hand_counts
    field_counts = ctx.field_counts
    bench_count = ctx.bench_count
    state = ctx.state
    ko_last_turn = ctx.ko_last_turn
    op_is_crustle_deck = ctx.op_is_crustle_deck
    op_has_ex_immune_active = ctx.op_has_ex_immune_active
    op_has_ex_immune_bench = ctx.op_has_ex_immune_bench
    has_hydrapple = ctx.has_hydrapple
    forest_in_play = ctx.forest_in_play
    meganium_in_play = ctx.meganium_in_play
    CARTAS_ACTIVAS_EN_MAZO = ctx.cartas_en_mazo

    _ub_cancel_for_meowth = False
    if (hand_counts.get(Meowth_ex, 0) >= 1 and
          field_counts.get(Meowth_ex, 0) == 0 and
          bench_count < 5 and
          not state.supporterPlayed and
          CARTAS_ACTIVAS_EN_MAZO.get(Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0):

        _ub_safe_without_meowth = 0
        for _ub_cid, _ub_cnt in hand_counts.items():
            if _ub_cid in (Ultra_Ball, Meowth_ex):
                continue
            for _ in range(_ub_cnt):
                if _ub_cid == Basic_Grass_Energy:
                    _ub_safe_without_meowth += 1
                elif _ub_cid == Tapu_Bulu:
                    if field_counts.get(Tapu_Bulu, 0) >= 1:
                        _ub_safe_without_meowth += 1
                    elif not (op_has_ex_immune_active or op_has_ex_immune_bench):
                        _ub_safe_without_meowth += 1
                elif _ub_cid == Pinsir:
                    if field_counts.get(Pinsir, 0) >= 1:
                        _ub_safe_without_meowth += 1
                    elif not (op_has_ex_immune_active or op_has_ex_immune_bench):
                        _ub_safe_without_meowth += 1
                elif _ub_cid == Forest_of_Vitality and (forest_in_play or _ub_cnt > 1):
                    _ub_safe_without_meowth += 1
                elif _ub_cid == Fezandipiti_ex and (field_counts.get(Fezandipiti_ex, 0) >= 1 or not ko_last_turn):
                    _ub_safe_without_meowth += 1
                elif _ub_cid == Chikorita and (field_counts.get(Chikorita, 0) + field_counts.get(Bayleef, 0) + field_counts.get(Meganium, 0) >= 1):
                    _ub_safe_without_meowth += 1
                elif _ub_cid == Applin and (field_counts.get(Applin, 0) + field_counts.get(Dipplin, 0) + field_counts.get(Hydrapple_ex, 0) >= 1):
                    _ub_safe_without_meowth += 1
                elif _ub_cid == Meganium and meganium_in_play:
                    _ub_safe_without_meowth += 1
                elif _ub_cid == Bayleef and meganium_in_play:
                    _ub_safe_without_meowth += 1
                elif _ub_cid == Lanas_Aid and _ub_cnt > 1:
                    _ub_safe_without_meowth += 1
                elif _ub_cid == Night_Stretcher and _ub_cnt > 1:
                    _ub_safe_without_meowth += 1
                elif _ub_cid == Bug_Catching_Set and _ub_cnt > 1:
                    _ub_safe_without_meowth += 1

        if _ub_safe_without_meowth < 2:
            _ub_cancel_for_meowth = True

    return _ub_cancel_for_meowth


def _ub_target_score(ctx, _ubf) -> int:
    """Fase D de Ultra Ball (ruta NO cancelada): valora el mejor objetivo de
    busqueda y mapea a tiers de ub_score, con penalizaciones por descartes y
    posible deferral del Supporter. Cuerpo verbatim (Paso 2 del plan)."""
    state = ctx.state
    my_state = ctx.my_state
    hand_counts = ctx.hand_counts
    field_counts = ctx.field_counts
    bench_count = ctx.bench_count
    my_prize = ctx.my_prize
    op_prize = ctx.op_prize
    we_go_first = ctx.we_go_first
    forest_in_play = ctx.forest_in_play
    meganium_in_play = ctx.meganium_in_play
    has_hydrapple = ctx.has_hydrapple
    ko_last_turn = ctx.ko_last_turn
    watchtower_in_play = ctx.watchtower_in_play
    itchy_pollen_active = ctx.itchy_pollen_active
    can_attack = ctx.can_attack
    _field_at_turn_start = ctx.field_at_turn_start
    CARTAS_ACTIVAS_EN_MAZO = ctx.cartas_en_mazo
    op_is_crustle_deck = ctx.op_is_crustle_deck
    op_is_cornerstone_deck = ctx.op_is_cornerstone_deck
    op_has_ex_immune_active = ctx.op_has_ex_immune_active
    op_has_ex_immune_bench = ctx.op_has_ex_immune_bench
    budew_on_op_field = ctx.budew_on_op_field
    budew_op_index = ctx.budew_op_index
    _mega_line_active = ctx.mega_line_active
    _evolve_possible_in_play = ctx.evolve_possible_in_play
    _best_supp_in_hand_val = ctx.best_supp_in_hand_val
    _best_supp_in_mazo_val = ctx.best_supp_in_mazo_val
    _win_via_boss_gust = ctx.win_via_boss_gust
    _gust_2prize_via_boss = ctx.gust_2prize_via_boss
    _boss_deny_alakazam_line = ctx.boss_deny_alakazam_line
    _ub_evolve_needs_search = _ubf.evolve_needs_search
    _ub_evolve_now_search = _ubf.evolve_now_search
    _ub_developed_attacker_board = _ubf.developed_attacker_board
    hand_size = _ubf.hand_size
    ub_score = 10000

    _ub_hand_play_options, _ub_supporters_in_hand = _count_hand_play_options(
        hand_counts, field_counts, bench_count, state.energyAttached)
    _ub_hand_is_weak = (_ub_hand_play_options <= 1 and hand_size <= 4)
    _ub_has_energy_for_teal = hand_counts.get(Basic_Grass_Energy, 0) >= 1

    ub_best_target = _eval_ub_best_target(
        field_counts, hand_counts, meganium_in_play, has_hydrapple,
        forest_in_play, op_has_ex_immune_active, op_has_ex_immune_bench,
        op_prize, bench_count, state, ko_last_turn,
        _best_supp_in_mazo_val, _ub_supporters_in_hand, _ub_hand_is_weak,
        _ub_has_energy_for_teal, we_go_first,
        _best_supp_in_hand_val,
        op_is_crustle_deck, op_is_cornerstone_deck,
        budew_on_op_field and budew_op_index == 0,
        watchtower_in_play)

    if (not (ko_last_turn and hand_counts.get(Unfair_Stamp, 0) >= 1) and
            hand_counts.get(Meowth_ex, 0) == 0 and
            hand_counts.get(Lillie_Determination, 0) == 0 and
            not state.supporterPlayed and
            field_counts.get(Meowth_ex, 0) < 2 and
            bench_count < 5 and
            CARTAS_ACTIVAS_EN_MAZO.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) > 0 and
            CARTAS_ACTIVAS_EN_MAZO.get(Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0):

        if _ub_hand_is_weak or _mega_line_active:
            ub_best_target = max(ub_best_target, 950)
        elif _best_supp_in_mazo_val >= 600:
            ub_best_target = max(ub_best_target, 850)

    if ub_best_target == 0:
        ub_score = -1
    else:

        _ub_ns_in_hand = (hand_counts.get(Night_Stretcher, 0) >= 1)

        _ub_meowth_chain = (
            ub_best_target >= 850 and
            not state.supporterPlayed and
            CARTAS_ACTIVAS_EN_MAZO.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) > 0 and
            CARTAS_ACTIVAS_EN_MAZO.get(Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0)
        safe_discards = 0
        for cid, cnt in hand_counts.items():
            if cid == Ultra_Ball:
                continue
            for _ in range(cnt):

                if cid == Basic_Grass_Energy:
                    safe_discards += 1

                elif cid in (Chikorita, Applin, Tapu_Bulu):
                    if field_counts.get(cid, 0) >= 1:
                        safe_discards += 1
                    elif CARTAS_ACTIVAS_EN_MAZO.get(cid, {}).get(ESTADO_MAZO, 0) >= 1:
                        safe_discards += 1
                    elif _ub_ns_in_hand:
                        safe_discards += 1

                elif cid == Forest_of_Vitality and (forest_in_play or cnt > 1):
                    safe_discards += 1
                elif cid == Meganium and meganium_in_play:
                    safe_discards += 1
                elif cid == Bayleef and meganium_in_play:
                    safe_discards += 1
                elif cid == Hydrapple_ex and has_hydrapple and cnt > 1:
                    safe_discards += 1
                elif cid == Meowth_ex and field_counts.get(Meowth_ex, 0) >= 1:
                    safe_discards += 1
                elif cid == Fezandipiti_ex and (field_counts.get(Fezandipiti_ex, 0) >= 1 or not ko_last_turn):
                    safe_discards += 1
                elif cid == Night_Stretcher and cnt > 1:
                    safe_discards += 1
                elif cid == Lanas_Aid and cnt > 1:
                    safe_discards += 1
                elif cid == Lillie_Determination and cnt > 1:
                    safe_discards += 1

                elif cid == Lanas_Aid and cnt == 1 and _ub_meowth_chain:
                    safe_discards += 1

                elif cid == Dipplin:
                    if cnt > 1:
                        safe_discards += 1
                    elif field_counts.get(Applin, 0) == 0:
                        safe_discards += 1

        if (_ub_developed_attacker_board and
                ub_best_target < 800 and
                not _ub_evolve_needs_search):
            # Board ya desarrollado con atacante listo:
            # no gastar Ultra Ball + descartes en un
            # objetivo de desarrollo de bajo valor.
            ub_score = -1
        elif ub_best_target < 300 and safe_discards < 2:
            ub_score = -1
        elif ub_best_target < 250:
            ub_score = -1
        elif bench_count >= 5 and not _evolve_possible_in_play:
            # Banca LLENA + NINGUN Pokemon en juego que
            # evolucionar: la Ultra Ball solo llevaria la
            # carta a la MANO (no se puede banquear nada)
            # y no habilita ninguna evolucion, asi que no
            # aporta nada este turno. Se cancela para
            # GUARDAR el recurso para cuando derriben un
            # Pokemon (banca con hueco) o haya algo que
            # evolucionar.
            ub_score = -1
        else:

            if ub_best_target >= 900:
                ub_score = 12500
            elif ub_best_target >= 700:
                ub_score = 12000
            elif ub_best_target >= 500:
                ub_score = 11200
            elif ub_best_target >= 300:
                ub_score = 10500
            else:
                ub_score = 10000

            if safe_discards < 2:
                ub_score -= 600
            elif safe_discards < 3:
                ub_score -= 250

            if _ub_hand_is_weak and ub_best_target >= 650:
                ub_score += 500

            if hand_counts.get(Lillie_Determination, 0) >= 1 and not state.supporterPlayed:
                _ub_enables_evo = (ub_best_target >= 800)
                # Con exactamente 6 premios restantes
                # Lillie's Determination roba 8 cartas:
                # ese refuerzo masivo tiene prioridad,
                # asi que se pospone Ultra Ball aunque
                # habilite una evolucion, para jugar
                # primero Lillie's.
                # EXCEPCION: si la Ultra Ball habilita una
                # evolucion que se puede COMPLETAR este
                # turno (`_ub_evolve_now_search`: pre-evo en
                # mesa evolucionable ya por Forest o por
                # estar desde el inicio del turno, y la
                # pieza en el mazo), NO se degrada: primero
                # se desarrolla la linea de evolucion y
                # Lillie's se juega despues, para no barajar
                # al mazo unas Ultra Ball que este turno
                # habilitaban evoluciones.
                _lillie_draws_8 = (my_prize == 6)
                if ((hand_size < 4 or not _ub_enables_evo
                        or _lillie_draws_8)
                        and not _ub_evolve_now_search):
                    ub_score = 4500

            # No quemar Lillie's Determination como coste
            # de Ultra Ball cuando eso nos dejaria sin mano.
            # Si al pagar el coste (descartar 2 cartas) no
            # quedan al menos 2 cartas distintas de la
            # Lillie's, jugar Ultra Ball obliga a descartar
            # la Lillie's y nos quedamos practicamente sin
            # mano. En ese caso se cancela, salvo que la
            # busqueda sirva para cerrar la partida (tomar
            # los premios que faltan, es decir muy pocos
            # premios restantes).
            if hand_counts.get(Lillie_Determination, 0) >= 1:
                _ub_non_lillie_discardable = 0
                for _ub_lid, _ub_lcnt in hand_counts.items():
                    if _ub_lid in (Ultra_Ball, Lillie_Determination):
                        continue
                    _ub_non_lillie_discardable += _ub_lcnt
                _ub_lillie_forced_discard = (
                    _ub_non_lillie_discardable < 2)
                _ub_winning_search = (
                    my_prize <= 2 or
                    _win_via_boss_gust or
                    _gust_2prize_via_boss)
                if (_ub_lillie_forced_discard
                        and not _ub_winning_search):
                    ub_score = -1

    return ub_score


def _ub_score_before_overrides(ctx, _ubf) -> int:
    """Fases B+C+D de _score_ultra_ball_play: cortes duros tempranos, vetos por
    coste de descarte y valoracion de objetivo. Devuelve ub_score ANTES de los
    overrides terminales (Fase E). Cuerpo verbatim (Paso 2 del plan)."""
    state = ctx.state
    my_state = ctx.my_state
    hand_counts = ctx.hand_counts
    field_counts = ctx.field_counts
    bench_count = ctx.bench_count
    my_prize = ctx.my_prize
    op_prize = ctx.op_prize
    we_go_first = ctx.we_go_first
    forest_in_play = ctx.forest_in_play
    meganium_in_play = ctx.meganium_in_play
    has_hydrapple = ctx.has_hydrapple
    ko_last_turn = ctx.ko_last_turn
    watchtower_in_play = ctx.watchtower_in_play
    itchy_pollen_active = ctx.itchy_pollen_active
    can_attack = ctx.can_attack
    _field_at_turn_start = ctx.field_at_turn_start
    CARTAS_ACTIVAS_EN_MAZO = ctx.cartas_en_mazo
    op_is_crustle_deck = ctx.op_is_crustle_deck
    op_is_cornerstone_deck = ctx.op_is_cornerstone_deck
    op_has_ex_immune_active = ctx.op_has_ex_immune_active
    op_has_ex_immune_bench = ctx.op_has_ex_immune_bench
    budew_on_op_field = ctx.budew_on_op_field
    budew_op_index = ctx.budew_op_index
    _mega_line_active = ctx.mega_line_active
    _evolve_possible_in_play = ctx.evolve_possible_in_play
    _best_supp_in_hand_val = ctx.best_supp_in_hand_val
    _best_supp_in_mazo_val = ctx.best_supp_in_mazo_val
    _win_via_boss_gust = ctx.win_via_boss_gust
    _gust_2prize_via_boss = ctx.gust_2prize_via_boss
    _boss_deny_alakazam_line = ctx.boss_deny_alakazam_line
    _ub_evolve_needs_search = _ubf.evolve_needs_search
    _ub_evolve_now_search = _ubf.evolve_now_search
    _ub_developed_attacker_board = _ubf.developed_attacker_board
    hand_size = _ubf.hand_size
    ub_score = 10000

    if hand_size < 3:
        ub_score = -1
    elif bench_count >= 5 and not _ub_evolve_needs_search:
        # SALVAGUARDA temprana (corte duro): con la banca LLENA
        # y NINGUN Pokemon en juego que se pueda evolucionar CON UNA
        # BUSQUEDA (la pieza de evolucion falta en mano y esta en el
        # mazo), la Ultra Ball no puede banquear nada nuevo y solo
        # llevaria una carta REDUNDANTE a la mano (p.ej. un 2o
        # Meganium cuando ya hay uno en juego), pagando ademas el
        # coste de descartar 2 cartas utiles. Tampoco cuenta si la
        # evolucion YA esta en la mano (esa linea evoluciona sin
        # Ultra Ball). No aporta NADA este turno, asi que se cancela
        # SIEMPRE para guardar el recurso hasta que derriben un
        # Pokemon (hueco en banca) o haya una evolucion que buscar.
        # Independiente de como quede ub_best_target.
        # Se usa un valor CLARAMENTE por debajo del piso de veto (-1) para que,
        # en un turno donde el resto de jugadas tambien esten vetadas (ataque /
        # retirada = -1 y END muy negativo), el argmax NO caiga por defecto en
        # jugar esta Ultra Ball inutil (indice 0). Asi se prefiere atacar / pasar
        # antes que malgastar la Ultra Ball + 2 descartes (user, registro 006
        # paso 72 vs Hops, PERDIDA: banca llena, buscaba un Hydrapple ex que no
        # quedaba en el mazo).
        ub_score = -100
    else:

        _ub_cancel_for_stamp = _ub_cancel_stamp(ctx)
        _ub_cancel_for_fez = _ub_cancel_fez(ctx)
        _ub_cancel_for_lillie = _ub_cancel_lillie(ctx)
        _ub_cancel_for_meowth = _ub_cancel_meowth(ctx)
        if (_ub_cancel_for_stamp or _ub_cancel_for_fez
                or _ub_cancel_for_lillie or _ub_cancel_for_meowth):
            ub_score = -1

        if not _ub_cancel_for_meowth and not _ub_cancel_for_stamp and not _ub_cancel_for_fez and not _ub_cancel_for_lillie:
            ub_score = _ub_target_score(ctx, _ubf)
    return ub_score


def _score_ultra_ball_play(ctx) -> int:
    """Puntua la jugada de Ultra Ball. Orquestador (Paso 2 del plan): compone las
    3 fases ya aisladas. Fase A `_ub_derive_flags` (contexto derivado) -> Fases
    B+C+D `_ub_score_before_overrides` (cortes duros, vetos por coste, valoracion
    de objetivo) -> Fase E `_ub_terminal_overrides` (overrides terminales, SIEMPRE
    al final). Ver docs/main-refactor-ultra-ball-plan.md."""
    # Estrategia vs Comfey (user, registro_005): la Ultra Ball SOLO sirve para
    # buscar Teal Mask Ogerpon ex, y el maximo es 2 en juego. Si ya tenemos 2, la
    # Ultra Ball es inutil -> CANCELAR (por debajo del piso de veto -1 para que el
    # agente ATAQUE/PASE en vez de malgastar la carta y sus 2 descartes).
    if (ctx.op_is_comfey_deck
            and ctx.field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 2):
        return -100
    _ubf = _ub_derive_flags(ctx)
    ub_score = _ub_score_before_overrides(ctx, _ubf)
    ub_score = _ub_terminal_overrides(
        ctx, ub_score, _ubf.survival_mode, _ubf.hand_size, _ubf.first_action_turn)
    return ub_score


def _score_lillie_determination_play(ctx: DecisionContext) -> int:
    """Puntua la jugada de Lillie's Determination (baraja la mano y roba 6/8).
    Extraida verbatim de la rama `elif card.id == Lillie_Determination`. Cuida no
    barajar piezas de evolucion pendientes y cede/gana prioridad frente a Boss's
    segun el estado. Cuerpo verbatim (refactor Prioridad 1)."""
    score = 0
    state = ctx.state
    my_state = ctx.my_state
    hand_counts = ctx.hand_counts
    field_counts = ctx.field_counts
    bench_count = ctx.bench_count
    meganium_in_play = ctx.meganium_in_play
    has_hydrapple = ctx.has_hydrapple
    forest_in_play = ctx.forest_in_play
    ko_last_turn = ctx.ko_last_turn
    can_attack = ctx.can_attack
    supporter_boost = ctx.supporter_boost
    _field_at_turn_start = ctx.field_at_turn_start
    op_is_alakazam_deck = ctx.op_is_alakazam_deck
    _our_first_turn = ctx.our_first_turn
    _active_cant_attack_this_turn = ctx.active_cant_attack
    _bdg_retreat_ko = ctx.bdg_retreat_ko
    _boss_win_via_bench = ctx.boss_win_via_bench
    _boss_dodge_redirect = ctx.boss_dodge_redirect
    _boss_low_value_gust = ctx.boss_low_value_gust
    _boss_prize_rank = ctx.boss_prize_rank

    _ready_ex_attackers = 0
    _lillie_my_pkmn = (
        [my_state.active[0]] if (my_state.active and my_state.active[0] is not None) else [])
    _lillie_my_pkmn += [bp for bp in my_state.bench if bp is not None]
    for _exp in _lillie_my_pkmn:
        _exp_eff = len(_exp.energies) * _grass_mult()
        if _exp.id == Hydrapple_ex and _exp_eff >= 2:
            _ready_ex_attackers += 1
        elif _exp.id == Teal_Mask_Ogerpon_ex and _exp_eff >= 3:
            _ready_ex_attackers += 1
        elif _exp.id == Fezandipiti_ex and _exp_eff >= 3:
            _ready_ex_attackers += 1

    # Piezas de evolucion en mano cuya pre-evolucion YA esta en
    # juego (activo o banca): si barajamos la mano con Lillie's
    # Determination las devolveriamos al mazo y perderiamos la
    # linea de evolucion. Detectamos esa situacion para NO jugar
    # Lillie's hasta completar las evoluciones disponibles.
    _lillie_pending_evo = False
    if not meganium_in_play:
        if (hand_counts.get(Bayleef, 0) >= 1 and
                field_counts.get(Chikorita, 0) >= 1):
            _lillie_pending_evo = True
        if (hand_counts.get(Meganium, 0) >= 1 and
                field_counts.get(Bayleef, 0) >= 1):
            _lillie_pending_evo = True
        if (forest_in_play and
                hand_counts.get(Meganium, 0) >= 1 and
                field_counts.get(Chikorita, 0) >= 1 and
                hand_counts.get(Bayleef, 0) >= 1):
            _lillie_pending_evo = True
    if not has_hydrapple:
        if (hand_counts.get(Dipplin, 0) >= 1 and
                field_counts.get(Applin, 0) >= 1):
            _lillie_pending_evo = True
        if (hand_counts.get(Hydrapple_ex, 0) >= 1 and
                field_counts.get(Dipplin, 0) >= 1):
            _lillie_pending_evo = True
        if (forest_in_play and
                hand_counts.get(Hydrapple_ex, 0) >= 1 and
                field_counts.get(Applin, 0) >= 1 and
                hand_counts.get(Dipplin, 0) >= 1):
            _lillie_pending_evo = True

    # Podemos EVOLUCIONAR realmente una de esas lineas ESTE
    # turno? Solo cuenta si la pre-evolucion esta AHORA en juego
    # (field_counts) y ademas puede evolucionar ya: o estaba en
    # juego al inicio del turno (_field_at_turn_start, no salio
    # este turno) o hay Forest of Vitality (permite evolucionar el
    # mismo turno). Evita el falso positivo de contar como
    # evolucionable un Pokemon que YA evoluciono este turno.
    _lillie_evolve_now = False
    if not meganium_in_play:
        if (hand_counts.get(Bayleef, 0) >= 1 and
                field_counts.get(Chikorita, 0) >= 1 and
                (forest_in_play or
                 _field_at_turn_start.get(Chikorita, 0) >= 1)):
            _lillie_evolve_now = True
        if (hand_counts.get(Meganium, 0) >= 1 and
                field_counts.get(Bayleef, 0) >= 1 and
                (forest_in_play or
                 _field_at_turn_start.get(Bayleef, 0) >= 1)):
            _lillie_evolve_now = True
    if not has_hydrapple:
        if (hand_counts.get(Dipplin, 0) >= 1 and
                field_counts.get(Applin, 0) >= 1 and
                (forest_in_play or
                 _field_at_turn_start.get(Applin, 0) >= 1)):
            _lillie_evolve_now = True
        if (hand_counts.get(Hydrapple_ex, 0) >= 1 and
                field_counts.get(Dipplin, 0) >= 1 and
                (forest_in_play or
                 _field_at_turn_start.get(Dipplin, 0) >= 1)):
            _lillie_evolve_now = True

    # Hydrapple ex CARGADO en el activo (>=2 de Planta efectiva,
    # listo para Syrup Storm): jugar Lillie's Determination tiene
    # prioridad sobre Boss's Orders. Barajar la mano y robar 6-8
    # busca mas Pokemon y energia para potenciar Syrup Storm (que
    # escala con la energia Planta en juego); Hydrapple conserva su
    # energia (Lillie's solo baraja la MANO) y ataca igual despues.
    _hydra_active_charged = (
        my_state.active and my_state.active[0] is not None
        and my_state.active[0].id == Hydrapple_ex
        and len(my_state.active[0].energies) * _grass_mult() >= 2)

    # Regla (user, registro 008 paso 84 vs Hops): Boss's Orders es una carta CLAVE
    # vs Hops (permite gustear y noquear a un Hops Phantump / Trevenant que saque
    # CARA y noquee a nuestro activo). Lillie's Determination baraja TODA la mano
    # al mazo (incluido el Boss's), asi que vs Hops, con Boss's en mano, solo se
    # juega Lillie's si el ACTIVO es el UNICO atacante disponible (necesitamos
    # cavar por mas recursos). Con >= 2 atacantes LISTOS (activo + banca) NO se
    # juega Lillie's: se guarda el Boss's en la mano para la respuesta. Si no hay
    # Boss's en mano, Lillie's se puede jugar con normalidad.
    _hop_keep_boss = False
    if (ctx.op_is_hop_deck
            and hand_counts.get(Boss_Orders, 0) >= 1
            and not _boss_win_via_bench):
        _lillie_ready_attackers = 0
        for _lra in _lillie_my_pkmn:
            _lra_req = ATTACK_ENERGY_REQ.get(_lra.id)
            if _lra_req is None:
                continue
            if len(_lra.energies) * _grass_mult() >= _lra_req:
                _lillie_ready_attackers += 1
        if _lillie_ready_attackers >= 2:
            _hop_keep_boss = True

    # Estrategia vs Comfey (user, registro_005): Lillie's Determination SOLO se
    # juega si tenemos 10 o MAS cartas en la mano. Baraja la mano al mazo, lo que
    # nos DEVUELVE cartas al deck (evita deckearnos por Flower Shower y esquiva el
    # descarte de Xerosic's Machinations). Con menos de 10 cartas NO se juega. Con
    # >=10 se deja pasar al scoring normal (positivo).
    if ctx.op_is_comfey_deck and len(my_state.hand or []) < 10:
        score = -1
    elif _hop_keep_boss:
        score = -1
    elif (not ctx.op_is_comfey_deck
            and state.turn <= 2 and len(my_state.hand or []) >= 10
            and not _our_first_turn):

        score = -1
    elif state.supporterPlayed:
        score = -1
    elif (ko_last_turn and hand_counts.get(Unfair_Stamp, 0) >= 1
            and ctx.op_hand_count > 3):

        # EXCEPCION (user): con Unfair Stamp en mano normalmente se prefiere jugar
        # el Stamp (draw 5 + disrupcion) sobre Lillie's; PERO si el rival tiene 3 o
        # menos cartas en la mano la disrupcion aporta poco y se prefiere Lillie's,
        # asi que este veto solo aplica con la mano rival > 3.
        score = -1
    elif (op_is_alakazam_deck and
            hand_counts.get(Unfair_Stamp, 0) >= 1 and
            _ready_ex_attackers >= 2 and
            ctx.op_hand_count > 3):

        score = -1
    elif _our_first_turn:
        # Regla (user, log 86025936 paso 11): en NUESTRO primer
        # turno SIEMPRE se juega Lillie's Determination si esta en
        # la mano, por encima de Boss's Orders. Se ignora el veto
        # de mano >= 10 y el veto por prioridad de Boss's. La capa
        # de orden de jugada mantiene Lillie's (tier 0, score 5000)
        # DESPUES de los desarrollos/items de mayor score, asi que
        # se baraja la mano al final del turno.
        score = 5000
    elif (_hydra_active_charged and not _lillie_pending_evo
            and not _boss_win_via_bench
            and not (_boss_dodge_redirect
                     and hand_counts.get(Boss_Orders, 0) >= 1)):
        # Prioridad Lillie's > Boss's con Hydrapple ex cargado en
        # el activo. Puntua por ENCIMA del maximo de Boss's que no
        # gana la partida (~5600); se exceptua `_boss_win_via_bench`
        # (gustada letal a la banca) para no perder un remate.
        # EXCEPCION (user, log 86343257 paso 99, PERDIDA vs Hop):
        # si el activo rival es INMUNE por esquiva (Splashing Dodge
        # con cara -> `_boss_dodge_redirect`) NO se puede atacar al
        # activo este turno, asi que potenciar Syrup Storm con
        # Lillie's es inutil; se cede la prioridad a Boss's Orders
        # (5500) para gustear y noquear un objetivo de banca.
        score = 5800 + supporter_boost
    elif (not _boss_low_value_gust and
            hand_counts.get(Boss_Orders, 0) >= 1 and
            ((_boss_prize_rank >= 1 and not _active_cant_attack_this_turn)
             or _boss_win_via_bench or _boss_dodge_redirect)):

        # No vetar Lillie's cuando el gusteo por `_boss_prize_rank`
        # NO es ejecutable este turno (activo no puede atacar y sin
        # atacante de banca listo). Los remates ejecutables
        # (win_via_bench / dodge) si siguen vetando Lillie's.
        score = -1
    elif (hand_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1 and
            hand_counts.get(Basic_Grass_Energy, 0) >= 1 and
            bench_count < 5):

        score = 4500
    elif (_lillie_pending_evo and state.turn > 2
            and len(my_state.hand or []) > 4
            and (_lillie_evolve_now
                 or not (can_attack or _bdg_retreat_ko))):
        # Tenemos en mano la evolucion (Bayleef/Meganium/Dipplin/
        # Hydrapple ex) de un Pokemon que ya esta en juego. Primero
        # se completan esas evoluciones (que puntuan ~31000-35000)
        # y se juegan los items; Lillie's Determination se pospone
        # para cuando no quede nada mas que evolucionar. Si la
        # pre-evolucion esta en el activo y todavia no se puede
        # evolucionar este turno (se difiere hasta banquearla), se
        # conserva igualmente para NO descartar las piezas al
        # barajar la mano. Corrige el caso en que se jugaba Lillie's
        # con Bayleef+Meganium en mano y se perdia la linea.
        # EXCEPCION 1: con 4 o menos cartas en mano en total, el
        # valor de robar (Lillie's roba 6-8) supera el de conservar
        # la linea, asi que NO se veta y se juega Lillie's.
        # EXCEPCION 2: si NO podemos evolucionar la linea ESTE turno
        # (`_lillie_evolve_now` False, p.ej. Bayleef recien
        # evolucionado sin Forest) Y vamos a ATACAR este turno, NO
        # se veta: atacar dejaria la Lillie's varada en la mano;
        # mejor jugarla ahora (robar 6-8) antes del ataque. "Atacar
        # este turno" incluye tanto el activo actual (`can_attack`)
        # como noquear al activo rival RETIRANDO y promoviendo un
        # atacante de banca listo (`_bdg_retreat_ko`). Solo se
        # conserva la linea si de verdad podemos evolucionarla ya
        # (evolucionar primero) o si NO vamos a cerrar el turno
        # atacando (se guarda para el proximo turno).
        # (user, log 86345042 paso 44, vs Mega Lucario, GANADA):
        # con Hydrapple ex en mano + Dipplin en banca y un atacante
        # de banca que ya noquea al Riolu activo (retirar+promover),
        # el juego jugaba Boss's Orders en un gusteo sin premio en
        # vez de refrescar; ahora `_bdg_retreat_ko` desbloquea
        # Lillie's para buscar mas recursos (p.ej. el Estadio) antes
        # de atacar.
        # EXCEPCION 3 (user, registro 003 paso 36 vs Archaludon ex,
        # GANADA): si NO podemos evolucionar la linea ESTE turno
        # (`_lillie_evolve_now` False) hemos entrado a esta rama por
        # el disyuntor `not (can_attack or _bdg_retreat_ko)`, es
        # decir, el turno seria MUERTO (no evolucionamos, no
        # atacamos, no retiramos-para-noquear). En ese caso conservar
        # unas piezas que igualmente no bajaremos hoy es peor que
        # refrescar: Lillie's roba 6 (u 8 con 6 premios) y abre nuevas
        # opciones de energia/atacante. Solo se mantiene el veto
        # (conservar la linea) cuando SI podemos evolucionar ya
        # (`_lillie_evolve_now`): ahi se evoluciona primero y se
        # difiere Lillie's para no barajar las piezas restantes.
        if not _lillie_evolve_now:
            score = 5000
        else:
            score = -1
    elif len(my_state.hand or []) <= 6:

        score = 5000
    else:
        score = 5000

        _has_pending_evolutions = False

        if (hand_counts.get(Bayleef, 0) >= 1 and
                field_counts.get(Chikorita, 0) >= 1 and
                not meganium_in_play):
            _has_pending_evolutions = True

        if (hand_counts.get(Meganium, 0) >= 1 and
                field_counts.get(Bayleef, 0) >= 1 and
                not meganium_in_play):
            _has_pending_evolutions = True

        if (hand_counts.get(Dipplin, 0) >= 1 and
                field_counts.get(Applin, 0) >= 1 and
                not has_hydrapple):
            _has_pending_evolutions = True

        if (hand_counts.get(Hydrapple_ex, 0) >= 1 and
                field_counts.get(Dipplin, 0) >= 1 and
                not has_hydrapple):
            _has_pending_evolutions = True

        if (hand_counts.get(Meganium, 0) >= 1 and
                field_counts.get(Chikorita, 0) >= 1 and
                forest_in_play and not meganium_in_play and
                hand_counts.get(Bayleef, 0) >= 1):
            _has_pending_evolutions = True

        if (hand_counts.get(Hydrapple_ex, 0) >= 1 and
                field_counts.get(Applin, 0) >= 1 and
                forest_in_play and not has_hydrapple and
                hand_counts.get(Dipplin, 0) >= 1):
            _has_pending_evolutions = True

        if _has_pending_evolutions:

            _evolvable_now = _field_at_turn_start if (not forest_in_play and _field_at_turn_start) else field_counts
            _can_evolve_now = False

            if (hand_counts.get(Bayleef, 0) >= 1 and
                    _evolvable_now.get(Chikorita, 0) >= 1 and
                    not meganium_in_play):
                _can_evolve_now = True
            if (hand_counts.get(Meganium, 0) >= 1 and
                    _evolvable_now.get(Bayleef, 0) >= 1 and
                    not meganium_in_play):
                _can_evolve_now = True
            if (hand_counts.get(Dipplin, 0) >= 1 and
                    _evolvable_now.get(Applin, 0) >= 1 and
                    not has_hydrapple):
                _can_evolve_now = True
            if (hand_counts.get(Hydrapple_ex, 0) >= 1 and
                    _evolvable_now.get(Dipplin, 0) >= 1 and
                    not has_hydrapple):
                _can_evolve_now = True
            if forest_in_play:
                if (hand_counts.get(Meganium, 0) >= 1 and
                        field_counts.get(Chikorita, 0) >= 1 and
                        not meganium_in_play and
                        hand_counts.get(Bayleef, 0) >= 1):
                    _can_evolve_now = True
                if (hand_counts.get(Hydrapple_ex, 0) >= 1 and
                        field_counts.get(Applin, 0) >= 1 and
                        not has_hydrapple and
                        hand_counts.get(Dipplin, 0) >= 1):
                    _can_evolve_now = True

            if _can_evolve_now:

                pass
            elif state.turn <= 2:

                pass
            elif (hand_counts.get(Lanas_Aid, 0) >= 1 and
                    not state.supporterPlayed):

                pass
            elif len(my_state.hand or []) >= 7:

                pass
            else:

                score = -1

    return score


def _score_lanas_aid_play(ctx: DecisionContext, score: int) -> int:
    """Puntua la jugada de Lana's Aid (recupera Pokemon no-ex + Energia del
    descarte a la mano). Extraida verbatim; recibe el score entrante (10000) y lo
    ajusta. Cede prioridad a Lillie's si no habilita ataque. Refactor Prioridad 1."""
    state = ctx.state
    my_state = ctx.my_state
    hand_counts = ctx.hand_counts
    ko_last_turn = ctx.ko_last_turn
    supporter_boost = ctx.supporter_boost
    _mega_line_active = ctx.mega_line_active
    _active_cant_attack_this_turn = ctx.active_cant_attack
    _supp_values = ctx.supp_values

    if state.supporterPlayed:
        score = -1
    elif ctx.op_is_comfey_deck and sum(
            1 for c in (my_state.discard or [])
            if getattr(c, 'id', None) == Basic_Grass_Energy) < 2:
        # Estrategia vs Comfey (user, registro_005): Lana's Aid SOLO se juega para
        # RECUPERAR ENERGIAS, y solo si recupera al menos DOS (>=2 Energias Planta
        # en el descarte). Nuestros unicos Pokemon vs Comfey son Ogerpon ex (Rule
        # Box: Lana's no los recupera), asi que su valor aqui es exclusivamente la
        # energia. Con menos de 2 energias recuperables NO se juega.
        score = -1
    elif ko_last_turn and hand_counts.get(Unfair_Stamp, 0) >= 1:
        score = -1
    else:
        _lana_val = _supp_values.get(Lanas_Aid, 0)
        if _lana_val <= 0:
            score = -1
        else:
            score = 2400 + int(_lana_val * 1.4) + supporter_boost

        if (_mega_line_active and score < 4500 and
                not state.supporterPlayed and
                hand_counts.get(Basic_Grass_Energy, 0) == 0 and
                not state.energyAttached):

            _lana_has_energy_discard = any(
                c.id == Basic_Grass_Energy for c in my_state.discard)
            if _lana_has_energy_discard:
                score = max(score, 4500)

        # Regla (user, log 86509038 paso 62, vs Mega Lucario,
        # PERDIDA): si NO tenemos un Pokemon que pueda atacar este
        # turno (`_active_cant_attack_this_turn`), la UNICA razon
        # para priorizar Lana's Aid sobre Lillie's Determination es
        # recuperar basicos + energia que HABILITEN un ataque
        # (`_lana_enables_attack`). En caso contrario Lillie's tiene
        # prioridad: refrescar la mano (robar 6-8) rinde mas que
        # recuperar piezas que no permiten atacar ya (en el log se
        # recupero Tapu Bulu sin energia para cargarlo y se perdio la
        # jugada de Lillie's). Se cede la prioridad bajando Lana's por
        # debajo del score base de Lillie's (5000), pero se conserva
        # jugable (2000) por si Lillie's estuviera vetada por otra via
        # (asi Lana's sigue siendo el mejor supporter disponible).
        if (score > 0
                and _active_cant_attack_this_turn
                and hand_counts.get(Lillie_Determination, 0) >= 1
                and not state.supporterPlayed
                and not _supp_values.get('_lana_enables_attack')):
            score = min(score, 2000)

    return score


def agent(obs_dict: dict) -> list[int]:
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        return my_deck

    state = obs.current
    select = obs.select
    context = select.context
    my_index = state.yourIndex
    my_state = state.players[my_index]
    op_state = state.players[1 - my_index]
    my_prize = len(my_state.prize)
    op_prize = len(op_state.prize)

    _update_cartas_tracking(obs, my_index, my_state)

    global plan
    global pre_turn
    global meganium_in_play
    global forest_in_play
    global ko_last_turn
    global _ko_detected_this_turn
    global _prev_op_prize
    global we_go_first
    global op_is_crustle_deck
    global op_is_cornerstone_deck
    global op_has_mega_kangaskhan
    global _field_at_turn_start
    global _poke_pad_target_id
    global _ub_meowth_pending
    global _dodge_immune_serial
    global _dodge_immune_turn

    if state.firstPlayer >= 0:
        we_go_first = (state.firstPlayer == state.yourIndex)

    if pre_turn != state.turn:
        pre_turn = state.turn
        plan = AttackPlan()

        _field_at_turn_start = None

        _ko_detected_this_turn = False

        _poke_pad_target_id = 0

        _ub_meowth_pending = False

    field_counts = defaultdict(int)
    hand_counts = defaultdict(int)
    discard_counts = defaultdict(int)

    meganium_in_play = False
    forest_in_play = False
    has_ogerpon = False
    has_hydrapple = False
    bench_count = 0

    for card in my_state.active + my_state.bench:
        if card is None:
            continue
        field_counts[card.id] += 1
        if card.id == Meganium:
            meganium_in_play = True
        if card.id == Hydrapple_ex:
            has_hydrapple = True
        if card.id == Teal_Mask_Ogerpon_ex:
            has_ogerpon = True

    for pokemon in my_state.bench:
        if pokemon is not None:
            bench_count += 1

    if _field_at_turn_start is None:
        _field_at_turn_start = dict(field_counts)

    if _poke_pad_target_id > 0 and field_counts.get(_poke_pad_target_id, 0) > 0:
        _poke_pad_target_id = 0

    for card in my_state.hand:
        hand_counts[card.id] += 1

    for card in my_state.discard:
        discard_counts[card.id] += 1

    # Con la banca LLENA, un recurso de busqueda (Ultra Ball / Poke Pad) solo
    # aporta valor si permite EVOLUCIONAR un Pokemon ya en juego (no se puede
    # banquear nada nuevo). "Hay algo que evolucionar" = tenemos en juego una
    # pre-evolucion cuya siguiente etapa esta disponible (en mano o en el mazo).
    _evolve_possible_in_play = (
        (field_counts.get(Chikorita, 0) >= 1 and
         (hand_counts.get(Bayleef, 0) >= 1 or
          CARTAS_ACTIVAS_EN_MAZO.get(Bayleef, {}).get(ESTADO_MAZO, 0) > 0)) or
        (field_counts.get(Bayleef, 0) >= 1 and
         (hand_counts.get(Meganium, 0) >= 1 or
          CARTAS_ACTIVAS_EN_MAZO.get(Meganium, {}).get(ESTADO_MAZO, 0) > 0)) or
        (field_counts.get(Applin, 0) >= 1 and
         (hand_counts.get(Dipplin, 0) >= 1 or
          CARTAS_ACTIVAS_EN_MAZO.get(Dipplin, {}).get(ESTADO_MAZO, 0) > 0)) or
        (field_counts.get(Dipplin, 0) >= 1 and
         (hand_counts.get(Hydrapple_ex, 0) >= 1 or
          CARTAS_ACTIVAS_EN_MAZO.get(Hydrapple_ex, {}).get(ESTADO_MAZO, 0) > 0))
    )

    stadium_id = 0
    for card in state.stadium:
        stadium_id = card.id

    if stadium_id == Forest_of_Vitality:
        forest_in_play = True

    neutralization_zone_active = (stadium_id == Neutralization_Zone)

    # Team Rocket's Watchtower: los Pokemon {C} en juego (ambos jugadores) NO
    # tienen Habilidades. Meowth ex es {C}, asi que su Last-Ditch Catch (buscar
    # Supporter al banquearlo) queda ANULADA mientras este estadio siga en
    # juego. No conviene bajar Meowth ex ni buscarlo con Ultra Ball hasta poder
    # reemplazar el estadio (p.ej. con Forest of Vitality).
    watchtower_in_play = (stadium_id == Team_Rockets_Watchtower)

    is_poisoned = my_state.poisoned
    is_burned = my_state.burned
    is_asleep = my_state.asleep
    is_paralyzed = my_state.paralyzed
    is_confused = my_state.confused
    has_condition = is_poisoned or is_burned or is_asleep or is_paralyzed or is_confused

    condition_blocks_action = is_paralyzed or is_asleep

    condition_risky_attack = is_confused

    condition_passive_damage = is_poisoned or is_burned

    condition_urgency = 0
    if is_paralyzed:
        condition_urgency += 5000
    if is_asleep:
        condition_urgency += 3000
    if is_confused:
        condition_urgency += 2000
    if is_poisoned:
        condition_urgency += 1500
    if is_burned:
        condition_urgency += 1200

    ko_last_turn = _ko_detected_this_turn

    if not ko_last_turn:

        for log in obs.logs:
            if hasattr(log, 'type'):
                if (log.type == LogType.MOVE_CARD and hasattr(log, 'playerIndex') and
                        log.playerIndex != my_index and hasattr(log, 'fromArea') and
                        log.fromArea == AreaType.PRIZE):
                    ko_last_turn = True
                    break

    if not ko_last_turn:

        if op_prize < _prev_op_prize:
            ko_last_turn = True

    if not ko_last_turn:

        if context == SelectContext.TO_ACTIVE and not state.retreated:
            ko_last_turn = True

    if ko_last_turn:
        _ko_detected_this_turn = True

    # Bloqueo de la cadena Unfair Stamp -> habilidad de Fezandipiti (Flip the
    # Script): mientras tengamos Unfair Stamp jugable este turno (nos noquearon
    # el turno anterior y sigue en la mano) primero se juega el Stamp y DESPUES
    # la habilidad. Se define aqui (ambito de agent) porque el bloque de la
    # habilidad de Fezandipiti la consulta en cualquier contexto.
    _stamp_blocks_supp_chain = (ko_last_turn and hand_counts.get(Unfair_Stamp, 0) >= 1)

    # Orden Lillie's Determination -> Flip the Script (peticion usuario): si
    # tenemos Lillie's Determination en la mano y aun no hemos jugado Supporter
    # este turno, primero se juega Lillie's Determination y DESPUES la habilidad
    # de Fezandipiti. Lillie's Determination es Supporter: al jugarse sale de la
    # mano y este flag pasa a False, re-habilitando la habilidad (30000).
    _lillie_blocks_fez_ability = (hand_counts.get(Lillie_Determination, 0) >= 1
                                  and not state.supporterPlayed)

    if context == SelectContext.MAIN:
        _prev_op_prize = op_prize

    def _op_best_damage_vs(my_pokemon, assume_attach=True):
        if my_pokemon is None:
            return 0
        _opa = _active_of(op_state)
        if _opa is None:
            return 0
        _opd = card_table.get(_opa.id)
        if not _opd or not getattr(_opd, 'attacks', None):
            return 0
        _avail = len(_opa.energies) + (1 if assume_attach else 0)
        _best = 0
        for _atk in _opd.attacks:
            _dmg = getattr(_atk, 'damage', None)
            if _dmg is None:
                continue
            _cost = getattr(_atk, 'cost', None)
            _need = 0
            if _cost is not None:
                try:
                    _need = len(_cost)
                except TypeError:
                    try:
                        _need = int(_cost)
                    except (TypeError, ValueError):
                        _need = 0
            if _need <= _avail:
                _best = max(_best, _dmg)
        _myd = card_table.get(my_pokemon.id)
        if (_myd and _opd and getattr(_myd, 'weakness', None) is not None and
                _myd.weakness == getattr(_opd, 'energyType', None)):
            _best *= 2
        return _best

    def _op_counter_threat_vs(my_pokemon):
        # Ataques que colocan CONTADORES de dano segun el tamano de mano rival
        # (p.ej. Alakazam - Powerful Hand: 20 por carta en su mano). Estos
        # ataques tienen 'damage' = None (n/a), asi que _op_best_damage_vs los
        # ignora y el agente queda ciego a la amenaza. Aqui los estimamos para
        # que el lookahead penalice subir a un Pokemon fragil que moriria.
        if my_pokemon is None:
            return 0
        _opa = _active_of(op_state)
        if _opa is None:
            return 0
        if _opa.id == Alakazam_ex:
            _h = _op_hand_size(op_state)
            if _h <= 0:
                _h = 4  # mano rival oculta: estimacion conservadora
            return 20 * _h
        return 0

    active_ko_likely = False
    active_hp_ratio = 1.0
    estimated_op_damage = 0
    _teal_wall_pivot = False

    _mega_line_active = False
    if my_state.active and my_state.active[0] is not None:
        my_active = my_state.active[0]
        active_hp_ratio = my_active.hp / max(1, my_active.maxHp)
        if my_active.id in (Chikorita, Bayleef, Meganium):
            _mega_line_active = True

        op_active = _active_of(op_state)
        if op_active is not None:
            op_data = card_table.get(op_active.id)
            op_energy = len(op_active.energies)

            estimated_op_damage = _op_best_damage_vs(my_active)

            if estimated_op_damage >= my_active.hp:
                active_ko_likely = True
            elif my_active.hp <= 60 and op_energy >= 2:
                active_ko_likely = True
            elif active_hp_ratio <= 0.3 and op_energy >= 1:
                active_ko_likely = True

            # Pivote defensivo con Teal Dance (user): si el activo es un Teal
            # Mask Ogerpon ex CONDENADO que NO podra atacar este turno (necesita
            # 3 de energia) y en la banca hay un Hydrapple ex a vida completa
            # (muro de 330), la linea correcta es usar Teal Dance en el activo
            # (adjunta Grass + ROBA 1) para tambien habilitar su retirada (coste
            # 1) y luego RETIRAR para subir al cuerpo mas fuerte (Hydrapple ex),
            # aunque aun no pueda atacar: no se regala el activo por nada.
            if (active_ko_likely
                    and my_active.id == Teal_Mask_Ogerpon_ex
                    and (len(my_active.energies) + _grass_attach_unit()) < 3
                    and hand_counts.get(Basic_Grass_Energy, 0) >= 1):
                for _twp_bp in (my_state.bench or []):
                    if (_twp_bp is not None and _twp_bp.id == Hydrapple_ex
                            and _twp_bp.hp >= (_twp_bp.maxHp or 0)):
                        _teal_wall_pivot = True
                        break

    itchy_pollen_active = False
    for log in obs.logs:
        if hasattr(log, 'type') and log.type == LogType.ATTACK:
            if log.cardId == Budew and log.playerIndex != my_index:
                itchy_pollen_active = True

    op_active_dodge_immune = False
    _dodge_pending_serial = None
    for log in obs.logs:
        _lt = getattr(log, 'type', None)
        if _lt == LogType.ATTACK:
            if (getattr(log, 'cardId', None) == Hops_Phantump
                    and getattr(log, 'attackId', None) == Splashing_Dodge_Atk
                    and getattr(log, 'playerIndex', None) != my_index):
                _dodge_pending_serial = getattr(log, 'serial', None)
        elif _lt == COIN_FLIP_LOG_TYPE:

            if (_dodge_pending_serial is not None
                    and getattr(log, 'playerIndex', None) != my_index):
                if getattr(log, 'head', False):

                    if (op_state.active and op_state.active[0] is not None
                            and getattr(op_state.active[0], 'serial', None)
                            == _dodge_pending_serial):
                        op_active_dodge_immune = True

                        _dodge_immune_serial = _dodge_pending_serial
                        _dodge_immune_turn = state.turn
                _dodge_pending_serial = None

    if (not op_active_dodge_immune
            and _dodge_immune_serial is not None
            and _dodge_immune_turn == state.turn
            and op_state.active and op_state.active[0] is not None
            and getattr(op_state.active[0], 'serial', None) == _dodge_immune_serial):
        op_active_dodge_immune = True

    budew_on_op_field = False
    budew_op_index = -1
    if op_state.active and op_state.active[0] is not None and op_state.active[0].id == Budew:
        budew_on_op_field = True
        budew_op_index = 0
    else:
        for idx, pokemon in enumerate(op_state.bench):
            if pokemon is not None and pokemon.id == Budew:
                budew_on_op_field = True
                budew_op_index = idx + 1
                break

    op_has_ex_immune_active = False
    op_has_ex_immune_bench = False
    op_has_ability_immune_active = False
    op_has_sturdy_crustle = False
    op_has_dwebble_bench = False
    op_has_crustle_bench = False

    op_has_froslass = False
    op_has_snorunt_bench = False
    op_has_munkidori = False
    op_has_dragapult = False
    op_has_dreepy_line = False
    op_has_typhlosion = False
    op_has_ethan_preevo = False
    op_is_fire_deck = False
    op_is_mirror = False
    op_bench_snipe_threat = False
    op_has_latias_ex = False

    op_is_greninja_deck = False
    op_is_slowking_deck = False
    op_is_beedrill_deck = False
    op_is_drednaw_deck = False
    op_is_sylveon_deck = False
    op_has_eevee_bench = False
    op_has_non_immune_eevee_ex = False
    op_is_dragapult_dusknoir = False
    op_is_alakazam_deck = False
    op_is_gardevoir_deck = False
    op_is_zoroark_deck = False
    op_is_aggro_deck = False
    op_is_control_deck = False
    op_has_mega_starmie_active = False
    op_is_lucario_deck = False
    op_is_cubchoo_deck = False
    op_is_hop_deck = False
    op_is_comfey_deck = False
    op_active_is_dunsparce = False
    if op_state.active and op_state.active[0] is not None:
        op_active_id = op_state.active[0].id
        if op_active_id in EX_IMMUNE_IDS:
            op_has_ex_immune_active = True
        if op_active_id in ABILITY_IMMUNE_IDS:
            op_has_ability_immune_active = True
        if op_active_id == Cornerstone_Mask_Ogerpon_ex:
            op_is_cornerstone_deck = True
        if op_active_id == Crustle_Fighting:
            op_has_sturdy_crustle = True
        if op_active_id in (Crustle_Grass, Crustle_Fighting, Dwebble_Grass, Dwebble_Fighting):
            op_is_crustle_deck = True
        if op_active_id == Mega_Kangaskhan_ex:
            op_has_mega_kangaskhan = True
        if op_active_id == Froslass:
            op_has_froslass = True
        if op_active_id == Munkidori:
            op_has_munkidori = True
        if op_active_id == Dragapult_ex:
            op_has_dragapult = True
            op_bench_snipe_threat = True
        if op_active_id == Typhlosion:
            op_has_typhlosion = True
        if op_active_id in (Cyndaquil, Quilava):
            op_has_ethan_preevo = True
        if op_active_id == Grimmsnarl_ex:
            op_bench_snipe_threat = True
        if op_active_id == Mega_Starmie_ex and len(op_state.active[0].energies) >= 1:

            op_has_mega_starmie_active = True
            op_bench_snipe_threat = True
        if op_active_id == Latias_ex:
            op_has_latias_ex = True
        if op_active_id in (Riolu, Mega_Lucario_ex):
            op_is_lucario_deck = True
        if op_active_id in (Cubchoo, Beartic):
            op_is_cubchoo_deck = True
        if op_active_id in (Hops_Phantump, Hops_Trevenant):
            op_is_hop_deck = True
        if op_active_id in (Comfey, Bramblin, Brambleghast):
            op_is_comfey_deck = True
        if op_active_id in DUNSPARCE_IDS:
            op_active_is_dunsparce = True

        op_active_data = card_table.get(op_active_id)
        if op_active_data and op_active_data.energyType == EnergyType.FIRE:
            op_is_fire_deck = True

        if op_active_id in (Teal_Mask_Ogerpon_ex, Hydrapple_ex, Dipplin, Applin, Meganium, Bayleef, Chikorita):
            op_is_mirror = True

        if op_active_id == Mega_Greninja_ex:
            op_is_greninja_deck = True
            op_bench_snipe_threat = True
        if op_active_id in (Slowpoke, Slowking):
            op_is_slowking_deck = True
            op_is_control_deck = True
        if op_active_id in (Weedle, Kakuna, Beedrill):
            op_is_beedrill_deck = True
            op_is_aggro_deck = True
        if op_active_id in (Chewtle, Drednaw):
            op_is_drednaw_deck = True
        if op_active_id == Sylveon or op_active_id in EEVEE_IDS:
            op_is_sylveon_deck = True
            op_is_crustle_deck = True
        if op_active_id == Eevee_PRE_ex:
            op_has_non_immune_eevee_ex = True
        if op_active_id in (Abra, Kadabra, Alakazam_ex):
            op_is_alakazam_deck = True
        if op_active_id in (Ralts, Kirlia, Gardevoir_ex):
            op_is_gardevoir_deck = True
        if op_active_id in (Zorua_N, Zoroark_N):
            op_is_zoroark_deck = True
        if op_active_id in (Raging_Bolt_ex, Lugia_VSTAR):
            op_is_aggro_deck = True
    for idx, pokemon in enumerate(op_state.bench):
        if pokemon is not None:
            if pokemon.id in EX_IMMUNE_IDS:
                op_has_ex_immune_bench = True
            if pokemon.id == Cornerstone_Mask_Ogerpon_ex:
                op_is_cornerstone_deck = True
            if pokemon.id == Crustle_Fighting:
                op_has_sturdy_crustle = True
            if pokemon.id in (Dwebble_Grass, Dwebble_Fighting):
                op_has_dwebble_bench = True
                op_is_crustle_deck = True
            if pokemon.id in (Crustle_Grass, Crustle_Fighting):
                op_is_crustle_deck = True
                op_has_crustle_bench = True
            if pokemon.id == Mega_Kangaskhan_ex:
                op_has_mega_kangaskhan = True
            if pokemon.id in (Comfey, Bramblin, Brambleghast):
                op_is_comfey_deck = True
            if pokemon.id == Froslass:
                op_has_froslass = True
            if pokemon.id == Snorunt:
                op_has_snorunt_bench = True
            if pokemon.id == Munkidori:
                op_has_munkidori = True
            if pokemon.id == Dragapult_ex:
                op_has_dragapult = True
                op_bench_snipe_threat = True
            if pokemon.id == Typhlosion:
                op_has_typhlosion = True
            if pokemon.id in (Cyndaquil, Quilava):
                op_has_ethan_preevo = True
            if pokemon.id == Grimmsnarl_ex:
                op_bench_snipe_threat = True
            if pokemon.id in (Dreepy, Drakloak):
                op_has_dreepy_line = True
            if pokemon.id == Latias_ex:
                op_has_latias_ex = True
            if pokemon.id in (Riolu, Mega_Lucario_ex):
                op_is_lucario_deck = True
            if pokemon.id in (Cubchoo, Beartic):
                op_is_cubchoo_deck = True
            if pokemon.id in (Hops_Phantump, Hops_Trevenant):
                op_is_hop_deck = True

            bench_data = card_table.get(pokemon.id)
            if bench_data and bench_data.energyType == EnergyType.FIRE:
                op_is_fire_deck = True

            if pokemon.id in (Teal_Mask_Ogerpon_ex, Hydrapple_ex, Dipplin, Applin, Meganium, Bayleef, Chikorita):
                op_is_mirror = True

            if pokemon.id in (Mega_Greninja_ex,):
                op_is_greninja_deck = True
                op_bench_snipe_threat = True
            if pokemon.id in (Slowpoke, Slowking):
                op_is_slowking_deck = True
                op_is_control_deck = True
            if pokemon.id in (Weedle, Kakuna, Beedrill):
                op_is_beedrill_deck = True
                op_is_aggro_deck = True
            if pokemon.id in (Chewtle, Drednaw):
                op_is_drednaw_deck = True
            if pokemon.id == Sylveon or pokemon.id in EEVEE_IDS:
                op_is_sylveon_deck = True
                op_is_crustle_deck = True
                if pokemon.id in EEVEE_IDS:
                    op_has_eevee_bench = True
                if pokemon.id == Eevee_PRE_ex:
                    op_has_non_immune_eevee_ex = True
            if pokemon.id in (Duskull, Dusclops, Dusknoir):
                op_is_dragapult_dusknoir = op_has_dragapult or op_has_dreepy_line
            if pokemon.id in (Abra, Kadabra, Alakazam_ex):
                op_is_alakazam_deck = True
            if pokemon.id in (Ralts, Kirlia, Gardevoir_ex):
                op_is_gardevoir_deck = True
            if pokemon.id in (Zorua_N, Zoroark_N):
                op_is_zoroark_deck = True
            if pokemon.id in (Raging_Bolt_ex, Lugia_VSTAR):
                op_is_aggro_deck = True

    # Eevee ex (id 249) NO es el muro Sylveon: es un ex atacable. Si el rival
    # sigue la linea Eevee ex y no hay ningun muro inmune real (Sylveon) en
    # juego, revocamos la estrategia anti-muro y volvemos a la estrategia ex:
    # atacamos ese ex con nuestros ex y evolucionamos Dipplin -> Hydrapple ex.
    if op_has_non_immune_eevee_ex and not (op_has_ex_immune_active or op_has_ex_immune_bench):
        op_is_crustle_deck = False
        op_is_sylveon_deck = False

    total_grass = count_total_grass_energy(my_state)

    # Pivote-muro a Hydrapple ex SIN KO (user, log 85856881 paso 127, vs Mega
    # Lucario ex, partida GANADA). A diferencia de `_teal_wall_pivot` (activo que
    # NO puede atacar), aqui el Teal Mask Ogerpon ex activo SI puede atacar, pero
    # su Myriad Leaf Shower NO noquea al rival y el Mega Lucario ex lo remata el
    # proximo turno (Mega Brave, 270 > 210 HP). Si en la banca hay un Hydrapple
    # ex a vida completa (muro de 330 HP) que SOBREVIVE al mejor golpe rival y
    # puede atacar (>=2 efectivas), la linea correcta es RETIRAR el Ogerpon
    # fragil y subir al muro: resiste el golpe y sigue presionando (Syrup Storm
    # 330), en vez de atacar con el Ogerpon que moriria regalando 2 premios. El
    # unico modo de retirarse en este motor es elegir PASS en el menu principal
    # (expone el prompt de retirada, ctx=30); por eso mas abajo apuntamos el plan
    # al Hydrapple de banca para SUPRIMIR la opcion de atacar con el Ogerpon.
    # Acotado a Mega Lucario (remate rival fijo y alto).
    _hydra_wall_pivot = False
    _hwp_active = my_state.active[0] if my_state.active else None
    _hwp_op_active = _active_of(op_state)
    if (op_is_lucario_deck and active_ko_likely
            and _hwp_active is not None
            and _hwp_active.id == Teal_Mask_Ogerpon_ex
            and len(_hwp_active.energies) >= 3
            and _hwp_op_active is not None):
        _hwp_op_hp = _hwp_op_active.hp or 0
        _hwp_oger_dmg = 30 + 30 * (
            len(_hwp_active.energies) + len(_hwp_op_active.energies))
        _hwp_oger_ko = (_hwp_op_hp > 0 and _hwp_oger_dmg >= _hwp_op_hp)
        _hwp_ret_phys = _physical_energy(len(_hwp_active.energies))
        _hwp_ret_cost = RETREAT_COST.get(_hwp_active.id, 1)
        if not _hwp_oger_ko and _hwp_ret_phys >= _hwp_ret_cost:
            for _hwp_bp in (my_state.bench or []):
                if (_hwp_bp is not None and _hwp_bp.id == Hydrapple_ex
                        and _hwp_bp.hp >= (_hwp_bp.maxHp or 0)
                        and len(_hwp_bp.energies) * _grass_mult() >= 2
                        and (_hwp_bp.hp or 0) > _op_best_damage_vs(_hwp_bp)):
                    _hydra_wall_pivot = True
                    break

    # Muro Feza -> Hydrapple ex vs Mega Lucario (user, log 86342087 paso 130,
    # PERDIMOS): si el ACTIVO es un Fezandipiti ex DEBIL a Lucha que sera
    # NOQUEADO por Mega Lucario ex el proximo turno (Mega Brave 270 x2 = 540,
    # 2 premios) y en la banca hay un Hydrapple ex sano (muro 330 que SOBREVIVE
    # el golpe rival, debilidad {R} no {F}), la linea correcta NO es cargar y
    # atacar con el Feza condenado (muere regalando 2 premios) sino cargar al
    # Hydrapple (ver energy_score), RETIRAR al Feza (coste 1) y promover el muro
    # para atacar. `_feza_lucario_wall` habilita esa carga; aqui, una vez el
    # Hydrapple ya esta listo (>=2 efectivas), activamos el pivote-muro para
    # suprimir el ataque del Feza y exponer la retirada (mismo mecanismo que el
    # pivote de Ogerpon de arriba). El Feza debe poder retirarse ya (energia
    # fisica >= coste de retirada 1).
    _feza_lucario_wall = False
    if (op_is_lucario_deck and active_ko_likely
            and _hwp_active is not None
            and _hwp_active.id == Fezandipiti_ex
            and _hwp_op_active is not None):
        _flw_ret_phys = _physical_energy(len(_hwp_active.energies))
        _flw_ret_cost = RETREAT_COST.get(_hwp_active.id, 1)
        if _flw_ret_phys >= _flw_ret_cost:
            for _flw_bp in (my_state.bench or []):
                if (_flw_bp is not None and _flw_bp.id == Hydrapple_ex
                        and _flw_bp.hp >= (_flw_bp.maxHp or 0)
                        and (_flw_bp.hp or 0) > _op_best_damage_vs(_flw_bp)):
                    _feza_lucario_wall = True
                    if len(_flw_bp.energies) * _grass_mult() >= 2:
                        # Hydrapple ya cargado: activar el pivote-muro para
                        # retirar el Feza y promover el muro (reusa el bloque de
                        # reasignacion de plan.attacker de mas abajo).
                        _hydra_wall_pivot = True

    # Pivote Hydrapple ex FRAGIL: retirar el activo con poca vida y promover al
    # sano (user, log 86027506 paso 81, vs Abomasnow, GANADA). Si el ACTIVO es un
    # Hydrapple ex con poca vida (en riesgo de KO) y en la BANCA hay OTRO
    # Hydrapple ex a (casi) plena vida, que SOBREVIVE al mejor golpe rival y esta
    # listo para un Syrup Storm LETAL, la linea correcta es RETIRAR el fragil para
    # protegerlo (si se queda activo lo noquean el proximo turno = 2 premios) y
    # SUBIR al sano a rematar (mismo KO, pero desde el cuerpo sano). El motor solo
    # ofrece retirada si el activo tiene energia FISICA >= su coste de retirada
    # (3 para Hydrapple ex); por eso hay que ROUTEAR la energia de este turno
    # (adjunte manual + Ripening Charge) al ACTIVO fragil hasta alcanzar ese coste
    # en vez de dejarla en el Hydrapple de banca (que ya esta cargado). Este flag
    # habilita esa carga en `energy_score`; el retiro+promocion posterior lo cubre
    # `_hydra_lethal_promote` (retiro con score 9000) una vez que can_switch pasa
    # a True.
    _hydra_fragile_pivot = False
    _hfp_active = my_state.active[0] if my_state.active else None
    _hfp_opa = _active_of(op_state)
    if (_hfp_active is not None and _hfp_active.id == Hydrapple_ex
            and _hfp_opa is not None and (_hfp_opa.hp or 0) > 0
            and (active_ko_likely
                 or (_hfp_active.hp or 0) <= (_hfp_active.maxHp or 1) * 0.5)):
        _hfp_rc = RETREAT_COST.get(Hydrapple_ex, 3)
        _hfp_phys = _physical_energy(len(_hfp_active.energies))
        if _hfp_phys < _hfp_rc:
            for _hfp_bp in (my_state.bench or []):
                if (_hfp_bp is not None and _hfp_bp.id == Hydrapple_ex
                        and (_hfp_bp.hp or 0) > (_hfp_active.hp or 0)
                        and (_hfp_bp.hp or 0) > _op_best_damage_vs(_hfp_bp)
                        and len(_hfp_bp.energies) * _grass_mult() >= 2):
                    _hfp_bdmg = _our_effective_damage(
                        _hfp_bp, _hfp_opa, 30 + 30 * total_grass,
                        meganium_in_play, neutralization_zone_active)
                    if _hfp_bdmg > 0 and _hfp_bdmg >= (_hfp_opa.hp or 0):
                        _hydra_fragile_pivot = True
                        break

    _conf_active = my_state.active[0] if my_state.active else None
    _conf_ex_immune_match = (op_is_crustle_deck or op_is_cornerstone_deck or
                             op_has_ex_immune_active or op_has_ex_immune_bench)

    def _conf_can_attack_pkmn(_p):
        if _p is None:
            return False
        _e = len(_p.energies)
        _eff = _e * _grass_mult()
        if _p.id == Hydrapple_ex:
            return _eff >= 2
        if _p.id == Dipplin:
            return _e >= 1
        if _p.id == Teal_Mask_Ogerpon_ex:
            return _eff >= 3
        if _p.id == Tapu_Bulu:
            return _eff >= 4
        if _p.id == Pinsir:
            return _eff >= 2
        if _p.id == Fezandipiti_ex:
            return _eff >= 3
        return False

    def _conf_is_matchup_attacker(_pid):
        if _conf_ex_immune_match:
            return _pid in (Tapu_Bulu, Dipplin, Pinsir)
        return _pid in (Hydrapple_ex, Dipplin, Teal_Mask_Ogerpon_ex,
                        Tapu_Bulu, Pinsir, Fezandipiti_ex)

    _conf_bench_attacker_ready = any(
        bp is not None and _conf_is_matchup_attacker(bp.id) and _conf_can_attack_pkmn(bp)
        for bp in (my_state.bench or []))
    _conf_bench_attacker_body = any(
        bp is not None and _conf_is_matchup_attacker(bp.id)
        for bp in (my_state.bench or []))
    _conf_active_can_retreat = False
    if is_confused and _conf_active is not None:
        # Wild Growth de Meganium duplica cada energia basica de Planta, asi que
        # la energia efectiva puede cubrir el coste de retirada con menos cartas
        # (p.ej. Meganium con 1 energia = {G}{G} -> paga su retirada de 2).
        _conf_ret_eff = len(_conf_active.energies) * _grass_mult()
        _conf_active_can_retreat = (
            _conf_ret_eff >= RETREAT_COST.get(_conf_active.id, 1))
    _conf_active_can_attack = bool(is_confused and _conf_can_attack_pkmn(_conf_active))
    _conf_should_retreat = bool(
        is_confused and _conf_active_can_retreat and _conf_bench_attacker_ready)
    _conf_should_attack = bool(
        is_confused and not _conf_bench_attacker_ready and _conf_active_can_attack)

    can_attack = False
    _active_cant_attack_this_turn = False
    _hydra_pivot_active = False
    _tapu_sac_pivot = False
    _tapu_sac_enable_retreat = False
    _prize_denial_pivot = False

    _bo_active_attack_sufficient = False

    can_switch = False
    can_op_switch = False
    has_switch_card = False
    if context == SelectContext.MAIN:
        can_switch = False
        can_op_switch = False
        for o in select.option:
            if o.type == OptionType.PLAY:
                card = get_card(obs, AreaType.HAND, o.index, my_index)
                if card is not None:
                    if card.id == Boss_Orders:
                        can_op_switch = True
            elif o.type == OptionType.RETREAT:
                can_switch = True
            elif o.type == OptionType.ATTACK:
                can_attack = True

        has_switch_card = False
        for o in select.option:
            if o.type == OptionType.PLAY:
                card = get_card(obs, AreaType.HAND, o.index, my_index)
                if card is not None and card.id == 1123:
                    can_switch = True
                    has_switch_card = True

        my_cards = [my_state.active[0]] if my_state.active else []
        for pokemon in my_state.bench:
            if pokemon is not None:
                my_cards.append(pokemon)
        op_cards = [op_state.active[0]] if op_state.active else []
        for pokemon in op_state.bench:
            if pokemon is not None:
                op_cards.append(pokemon)

        if state.turn >= 2 and len(my_cards) > 0 and len(op_cards) > 0:
            best_score = -1
            for i, my_pokemon in enumerate(my_cards):
                if my_pokemon is None:
                    continue
                if i != 0 and not can_switch:
                    break

                attack_options = []
                if my_pokemon.id == Hydrapple_ex:

                    _syrup_grass = total_grass
                    if hand_counts.get(Basic_Grass_Energy, 0) >= 1 and not state.energyAttached:
                        _syrup_grass += _grass_attach_unit()
                    syrup_dmg = 30 + 30 * _syrup_grass
                    attack_options.append((2, syrup_dmg, 0, True))
                elif my_pokemon.id == Dipplin:

                    wave_dmg = 20 * bench_count
                    attack_options.append((1, wave_dmg, 0, False))
                elif my_pokemon.id == Teal_Mask_Ogerpon_ex:

                    if len(op_cards) > 0:
                        op_active_energy = len(op_cards[0].energies) if op_cards[0] is not None else 0
                        my_energy = len(my_pokemon.energies)
                        leaf_dmg = 30 + 30 * my_energy
                        attack_options.append((3, leaf_dmg, 0, False))
                elif my_pokemon.id == Tapu_Bulu:

                    attack_options.append((4, 220, 0, False))
                elif my_pokemon.id == Meganium:

                    attack_options.append((4, 140, 0, False))
                elif my_pokemon.id == Fezandipiti_ex:

                    attack_options.append((3, 100, 0, True))
                elif my_pokemon.id == Pinsir:

                    attack_options.append((2, 100, 1, False))

                for energy_req, base_damage, attack_idx, colorless_ok in attack_options:
                    base_score = 0

                    energy_count = len(my_pokemon.energies)
                    more_energy = False
                    _ns_energy_recovery = False

                    effective_energy = energy_count * _grass_mult()

                    if effective_energy < energy_req:
                        if hand_counts[Basic_Grass_Energy] >= 1 and not state.energyAttached:
                            effective_energy += _grass_attach_unit()
                            if effective_energy < energy_req:
                                continue
                            else:
                                more_energy = True

                        elif (i != 0 and
                              hand_counts.get(Night_Stretcher, 0) >= 1 and
                              discard_counts.get(Basic_Grass_Energy, 0) >= 1 and
                              not state.energyAttached):
                            _ns_eff = _grass_attach_unit()
                            if effective_energy + _ns_eff >= energy_req:
                                more_energy = True
                                _ns_energy_recovery = True
                            else:
                                continue
                        else:
                            continue

                    my_is_ex = my_pokemon.id in OUR_EX_IDS

                    _op_active_is_drednaw = (op_state.active and op_state.active[0] is not None
                                             and op_state.active[0].id == Drednaw)
                    if my_pokemon.id == Hydrapple_ex:
                        base_score += 200
                        if op_has_ability_immune_active:
                            base_score -= 2000

                        if _op_active_is_drednaw:
                            _syrup_dmg_est = 30 + 30 * total_grass
                            if _syrup_dmg_est >= 200:
                                base_score -= 3000

                        elif op_is_fire_deck:
                            base_score += 150
                        elif op_is_aggro_deck:
                            base_score += 100
                    elif my_pokemon.id == Dipplin:
                        base_score += 50

                        if op_has_ex_immune_active:
                            base_score += 1200
                        if op_has_ability_immune_active:
                            base_score += 1500

                        if _op_active_is_drednaw:
                            base_score += 2500
                    elif my_pokemon.id == Tapu_Bulu:
                        if op_has_ex_immune_active:
                            base_score += 2200

                            if (op_state.active and op_state.active[0] is not None
                                    and op_state.active[0].id == Sylveon):
                                base_score += 800
                        elif op_has_ability_immune_active:
                            base_score += 2500
                        elif _op_active_is_drednaw:
                            base_score -= 3000
                        elif op_is_fire_deck:
                            base_score += 800

                        elif op_is_control_deck or op_is_slowking_deck:
                            base_score += 500
                        else:
                            base_score += 100
                    elif my_pokemon.id == Pinsir:
                        base_score += 50

                        if op_has_ex_immune_active:
                            base_score += 1300
                        if op_has_ability_immune_active:
                            base_score += 1600

                        if _op_active_is_drednaw:
                            base_score += 2300
                    elif my_pokemon.id == Meganium:
                        if op_has_ex_immune_active:
                            base_score += 1500

                            if (op_state.active and op_state.active[0] is not None
                                    and op_state.active[0].id == Sylveon):
                                base_score += 2000
                        if op_has_ability_immune_active:
                            base_score -= 2000

                        if _op_active_is_drednaw:
                            base_score += 3500
                    elif my_pokemon.id == Teal_Mask_Ogerpon_ex:
                        base_score -= 100
                        if op_has_ability_immune_active:
                            base_score -= 2000
                    elif my_pokemon.id == Fezandipiti_ex:

                        if op_has_ex_immune_active:
                            base_score -= 2000
                        if op_has_ability_immune_active:
                            base_score -= 2000

                    if neutralization_zone_active:
                        if my_is_ex:
                            base_score -= 3000
                        else:

                            base_score += 2000

                    for j, op_pokemon in enumerate(op_cards):
                        if op_pokemon is None:
                            continue

                        if j != 0 and not can_op_switch and my_pokemon.id != Fezandipiti_ex:
                            break

                        damage = base_damage
                        data = card_table[op_pokemon.id]

                        if op_pokemon.id in EX_IMMUNE_IDS and my_is_ex:
                            damage = 0

                        _op_has_rule_box = (data.ex or data.megaEx)
                        if (neutralization_zone_active and my_is_ex and
                                not _op_has_rule_box and damage > 0):
                            damage = 0

                        my_has_ability = (my_pokemon.id in OUR_ABILITY_IDS)
                        if op_pokemon.id in ABILITY_IMMUNE_IDS and my_has_ability:
                            damage = 0

                        _drednaw_shell_active = (op_pokemon.id == Drednaw and damage > 0)

                        if damage > 0 and my_pokemon.id != Fezandipiti_ex:
                            if data.weakness == EnergyType.GRASS:
                                damage *= 2
                            elif data.resistance == EnergyType.GRASS:
                                damage -= 30

                        if _drednaw_shell_active and damage >= 200:
                            damage = 0

                        effective_ko_hp = op_pokemon.hp
                        if op_pokemon.id == Crustle_Fighting and op_pokemon.hp == op_pokemon.maxHp:

                            if damage >= op_pokemon.hp:
                                damage = op_pokemon.hp - 10
                                effective_ko_hp = op_pokemon.hp + 1

                        prize = 0
                        score = pokemon_score(op_pokemon)
                        if damage <= 0 and op_pokemon.id in EX_IMMUNE_IDS:
                            score = -5000
                        elif damage <= 0 and op_pokemon.id in ABILITY_IMMUNE_IDS:
                            score = -5000
                        elif damage <= 0 and _drednaw_shell_active:
                            score = -5000
                        elif damage <= 0 and neutralization_zone_active and my_is_ex:
                            score = -5000
                        elif op_pokemon.hp <= damage:
                            prize = prize_count(op_pokemon)
                        else:
                            score *= damage / max(1, op_pokemon.hp)
                        score += base_score

                        if op_pokemon.id == Budew:
                            if op_pokemon.hp <= damage:
                                score += 8000
                            else:
                                score += 3000

                        elif op_pokemon.id == Froslass:
                            if op_pokemon.hp <= damage:
                                score += 9000
                            else:
                                score += 4000

                        elif op_pokemon.id == Munkidori:
                            if op_pokemon.hp <= damage:
                                score += 7500
                            else:
                                score += 2500

                        elif op_pokemon.id == Snorunt:
                            if op_pokemon.hp <= damage:
                                score += 7000
                            else:
                                score += 2500

                        elif op_pokemon.id in (Dreepy, Drakloak):
                            if op_pokemon.hp <= damage:
                                # vs la linea Dragapult, cortar un Drakloak
                                # (Stage-1 energizado a un paso de Dragapult ex,
                                # atacante de 2 premios que hace spread) con el
                                # snipe libre de Cruel Arrow (Fezandipiti ex, 100
                                # fijo) es MAS valioso que noquear a Budew (soporte
                                # de 30hp). Sin este boost el KO de Budew (8000 +
                                # 3500 basico + 300 activo = 11800) supera al de
                                # Drakloak (6500 + 3000 Stage-1 = 9500) y el juego
                                # dispara a Budew. Elevamos Drakloak por encima de
                                # Budew SOLO en el matchup Dragapult. Cruel Arrow
                                # nunca noquea al propio Dragapult ex (320hp), asi
                                # que no interfiere con KOs de mayor premio.
                                if op_pokemon.id == Drakloak and op_has_dreepy_line:
                                    score += 9800
                                else:
                                    score += 6500
                            else:
                                score += 2000

                        elif op_pokemon.id in (Dwebble_Grass, Dwebble_Fighting):
                            if op_pokemon.hp <= damage:
                                score += 6000
                            else:
                                score += 2000

                        elif op_pokemon.id in EX_IMMUNE_IDS and not my_is_ex and damage > 0:
                            if op_pokemon.hp <= damage:
                                score += 7000
                            else:
                                score += 4000

                        elif op_pokemon.id == Crustle_Fighting and op_pokemon.hp < op_pokemon.maxHp:
                            if op_pokemon.hp <= damage:
                                score += 5000

                        elif op_pokemon.id in (Ralts, Kirlia):
                            if op_pokemon.hp <= damage:
                                score += 6000
                            else:
                                score += 1500
                        elif op_pokemon.id == Gardevoir_ex:
                            if op_pokemon.hp <= damage:
                                score += 7500
                            else:
                                score += 3000

                        elif op_pokemon.id in (Abra, Kadabra):
                            if op_pokemon.hp <= damage:
                                score += 5500
                            else:
                                score += 1500
                        elif op_pokemon.id == Alakazam_ex:
                            if op_pokemon.hp <= damage:
                                score += 7000
                            else:
                                score += 2500

                        elif op_pokemon.id == Slowking:
                            if op_pokemon.hp <= damage:
                                score += 7500
                            else:
                                score += 3000
                        elif op_pokemon.id == Slowpoke:
                            if op_pokemon.hp <= damage:
                                score += 5500
                            else:
                                score += 1500

                        elif op_pokemon.id in (Duskull, Dusclops):
                            if op_pokemon.hp <= damage:
                                score += 5500
                            else:
                                score += 1500
                        elif op_pokemon.id == Dusknoir:
                            if op_pokemon.hp <= damage:
                                score += 7000
                            else:
                                score += 2500

                        elif op_pokemon.id == Zoroark_N:
                            if op_pokemon.hp <= damage:
                                score += 6500
                            else:
                                score += 2000
                        elif op_pokemon.id == Zorua_N:
                            if op_pokemon.hp <= damage:
                                score += 5000
                            else:
                                score += 1200

                        elif op_pokemon.id == Typhlosion:
                            if op_pokemon.hp <= damage:
                                score += 6500
                            else:
                                score += 2000
                        elif op_pokemon.id in (Cyndaquil, Quilava):
                            if op_pokemon.hp <= damage:
                                score += 5000
                            else:
                                score += 1200

                        elif op_pokemon.id == Chewtle:
                            if op_pokemon.hp <= damage:
                                score += 7000
                            else:
                                score += 2500

                        elif op_pokemon.id == Drednaw and damage > 0:
                            if op_pokemon.hp <= damage:
                                score += 8000
                            else:
                                score += 3000

                        elif op_pokemon.id in EEVEE_IDS:
                            if op_pokemon.hp <= damage:
                                score += 7500
                            else:
                                score += 2500

                        elif op_pokemon.id == Sylveon and damage > 0:
                            if op_pokemon.hp <= damage:
                                score += 9000
                            else:
                                score += 4000

                        if my_pokemon.id == Fezandipiti_ex and damage > 0:
                            _op_data = card_table.get(op_pokemon.id)
                            _is_stage2 = (_op_data and getattr(_op_data, 'stage2', False))
                            _is_stage1 = (_op_data and getattr(_op_data, 'stage1', False))
                            _is_ex = (_op_data and getattr(_op_data, 'ex', False))
                            if op_pokemon.hp <= damage:

                                if _is_stage2:
                                    score += 5000
                                elif _is_ex:
                                    score += 4500
                                elif not _is_stage1:
                                    score += 3500
                                else:
                                    score += 3000
                            else:

                                if j == 0:
                                    score += 500

                        if my_prize <= prize:
                            score = 50000
                        elif prize > 0:

                            remaining_after_ko = op_prize - prize
                            if remaining_after_ko == 1:

                                score += 4000

                        if i == 0:
                            score += 220
                        if j == 0:
                            score += 300
                        score += effective_energy

                        _la_return = _op_best_damage_vs(my_pokemon)
                        if _la_return > 0:
                            if _la_return >= my_pokemon.hp:
                                if my_pokemon.id in OUR_EX_IDS:

                                    _la_disrupt = _op_disruption_belief(op_state, False)
                                    score -= int(SCORE_LOOKAHEAD_EX_TRADE * (0.6 + 0.4 * _la_disrupt))
                                else:
                                    score -= SCORE_LOOKAHEAD_KO_TRADE
                            elif _la_return <= my_pokemon.hp * 0.4:
                                score += SCORE_LOOKAHEAD_SAFE

                        if best_score < score:
                            best_score = score
                            plan.attacker = i
                            plan.target = j
                            plan.attack_index = attack_idx
                            plan.remain_hp = op_pokemon.hp - damage
                            plan.energy = more_energy

            _op_act_main = op_state.active[0] if op_state.active else None
            _ret_active = my_cards[0] if my_cards else None
            if (_op_act_main is not None and can_switch and _ret_active is not None
                    and _ret_active.id != Hydrapple_ex):

                _hydra_mc_idx = -1
                _hydra_mc_pk = None

                _hydra_charge_idx = -1
                _hydra_charge_pk = None
                _grass_in_hand_promo = hand_counts.get(Basic_Grass_Energy, 0) >= 1
                # Desempate por VIDA (user, log 86212499 paso 151, vs Alakazam,
                # GANADA): con dos o mas Hydrapple ex de banca IGUALES aptos para
                # promover y atacar (p.ej. uno a 70 hp y otro a 330 hp), promover
                # SIEMPRE al de MAS vida. Antes el bucle recorria la banca en
                # orden y tomaba el PRIMER Hydrapple apto (`break` / primer
                # candidato de carga), es decir el de menor indice de banca (el
                # de 70 hp), que es fragil y muere facil. Ahora se recorre toda
                # la banca y, a igualdad de aptitud (listo >= 2 efectivas, o
                # cargable a >= 2), se elige el de mayor hp. Se mantiene la
                # prioridad: un Hydrapple YA cargado (`_hydra_mc_idx`) prevalece
                # sobre uno que necesita carga (`_hydra_charge_idx`).
                for _mc_i, _mc_pk in enumerate(my_cards):
                    if _mc_i == 0 or _mc_pk is None:
                        continue
                    if _mc_pk.id == Hydrapple_ex:
                        _mc_eff = len(_mc_pk.energies) * _grass_mult()
                        if _mc_eff >= 2:
                            if (_hydra_mc_idx < 0
                                    or (_mc_pk.hp or 0) > (_hydra_mc_pk.hp or 0)):
                                _hydra_mc_idx = _mc_i
                                _hydra_mc_pk = _mc_pk
                        elif (_grass_in_hand_promo and
                                len(_mc_pk.energies) + _grass_attach_unit() >= 2):
                            if (_hydra_charge_idx < 0
                                    or (_mc_pk.hp or 0) > (_hydra_charge_pk.hp or 0)):
                                _hydra_charge_idx = _mc_i
                                _hydra_charge_pk = _mc_pk

                _hydra_promo_needs_charge = False
                if _hydra_mc_idx < 0 and _hydra_charge_idx >= 1:

                    _ret_req_now = None
                    if _ret_active.id == Hydrapple_ex:
                        _ret_req_now = 2
                    elif _ret_active.id == Dipplin:
                        _ret_req_now = 1
                    elif _ret_active.id == Teal_Mask_Ogerpon_ex:
                        _ret_req_now = 3
                    elif _ret_active.id == Tapu_Bulu:
                        _ret_req_now = 4
                    elif _ret_active.id == Pinsir:
                        _ret_req_now = 2
                    elif _ret_active.id == Fezandipiti_ex:
                        _ret_req_now = 3
                    elif _ret_active.id == Meganium:
                        _ret_req_now = 4
                    _ret_eff_now = len(_ret_active.energies) * _grass_mult()
                    _ret_act_ready_now = (_ret_req_now is not None and _ret_eff_now >= _ret_req_now)

                    if _ret_req_now is None or _ret_act_ready_now:
                        _hydra_mc_idx = _hydra_charge_idx
                        _hydra_mc_pk = _hydra_charge_pk
                        _hydra_promo_needs_charge = True
                if _hydra_mc_idx >= 1:
                    _op_main_hp = _op_act_main.hp or 0

                    _ret_cost = RETREAT_COST.get(_ret_active.id, 1)
                    if has_switch_card:
                        _ret_cost = 0
                    # Wild Growth: cada Planta paga por dos, se descartan menos
                    # CARTAS de Planta para cubrir la retirada.
                    _ret_cards = _retreat_cards(_ret_cost)
                    _hydra_grass_after = max(0, total_grass - _ret_cards)
                    if _hydra_promo_needs_charge:
                        _hydra_grass_after += 1
                    _hydra_base = 30 + 30 * _hydra_grass_after
                    _hydra_ko_dmg = _our_effective_damage(
                        _hydra_mc_pk, _op_act_main, _hydra_base,
                        meganium_in_play, neutralization_zone_active)
                    _hydra_can_ko = (_hydra_ko_dmg > 0 and _hydra_ko_dmg >= _op_main_hp)

                    _act_can_ko = False
                    _act_prof = None
                    if _ret_active.id == Dipplin:
                        _act_prof = (1, 20 * bench_count)
                    elif _ret_active.id == Teal_Mask_Ogerpon_ex:
                        _oae = len(_op_act_main.energies)
                        _act_prof = (3, 30 + 30 * (len(_ret_active.energies) + _oae))
                    elif _ret_active.id == Tapu_Bulu:
                        _act_prof = (4, 220)
                    elif _ret_active.id == Meganium:
                        _act_prof = (4, 140)
                    elif _ret_active.id == Pinsir:
                        _act_prof = (2, 100)
                    elif _ret_active.id == Fezandipiti_ex:
                        _act_prof = (3, 100)
                    if _act_prof is not None:
                        _act_req, _act_base = _act_prof
                        _act_eff = len(_ret_active.energies) * _grass_mult()
                        if (_act_eff < _act_req and hand_counts.get(Basic_Grass_Energy, 0) >= 1
                                and not state.energyAttached):
                            _act_eff += _grass_attach_unit()
                        if _act_eff >= _act_req:
                            _act_dmg = _our_effective_damage(
                                _ret_active, _op_act_main, _act_base,
                                meganium_in_play, neutralization_zone_active)
                            _act_can_ko = (_act_dmg > 0 and _act_dmg >= _op_main_hp)

                    _promote_hydra = _hydra_can_ko or (not _act_can_ko)

                    if _hydra_ko_dmg <= 0:
                        _promote_hydra = False
                    # Regla (user, registro 010 paso 82 vs Alakazam): un Tapu Bulu
                    # CARGADO en el activo que puede NOQUEAR al activo rival ataca
                    # el mismo; no cede el ataque al pivote de Hydrapple ex. Tapu
                    # Bulu es no-ex (1 premio si lo noquean), asi que rematar con el
                    # es mejor que exponer/gastar la Hydrapple ex (2 premios).
                    if _ret_active.id == Tapu_Bulu and _act_can_ko:
                        _promote_hydra = False
                    if _promote_hydra and plan.attacker != _hydra_mc_idx:
                        plan.attacker = _hydra_mc_idx
                        plan.target = 0
                        plan.attack_index = 0
                        plan.remain_hp = _op_main_hp - _hydra_ko_dmg
                        plan.energy = False

            if (plan.attacker >= 1
                    and _op_act_main is not None
                    and _ret_active is not None
                    and _ret_active.id in OUR_EX_IDS
                    and _op_act_main.id not in EX_IMMUNE_IDS):
                _rule_act_immune = False
                if _op_act_main.id in ABILITY_IMMUNE_IDS and _ret_active.id in OUR_ABILITY_IDS:
                    _rule_act_immune = True
                if neutralization_zone_active and _ret_active.id in OUR_EX_IDS:
                    _op_act_data_rule = card_table.get(_op_act_main.id)
                    if not (_op_act_data_rule and (_op_act_data_rule.ex or _op_act_data_rule.megaEx)):
                        _rule_act_immune = True
                if not _rule_act_immune:
                    _rule_act_prof = None
                    if _ret_active.id == Teal_Mask_Ogerpon_ex:
                        _oae_r = len(_op_act_main.energies)
                        _rule_act_prof = (3, 30 + 30 * (len(_ret_active.energies) + _oae_r))
                    elif _ret_active.id == Hydrapple_ex:
                        _rule_act_prof = (2, 30 + 30 * total_grass)
                    elif _ret_active.id == Fezandipiti_ex:
                        _rule_act_prof = (3, 100)
                    if _rule_act_prof is not None:
                        _rule_req, _rule_base = _rule_act_prof
                        _rule_eff = len(_ret_active.energies) * _grass_mult()
                        _rule_needs_attach = False
                        if (_rule_eff < _rule_req
                                and hand_counts.get(Basic_Grass_Energy, 0) >= 1
                                and not state.energyAttached):
                            _rule_eff += _grass_attach_unit()
                            _rule_needs_attach = True
                        if _rule_eff >= _rule_req:
                            _rule_act_dmg = _our_effective_damage(
                                _ret_active, _op_act_main, _rule_base,
                                meganium_in_play, neutralization_zone_active)
                            _rule_bench_kos = (plan.target == 0
                                               and plan.remain_hp is not None
                                               and plan.remain_hp <= 0)
                            if _rule_act_dmg > 0 and not _rule_bench_kos:
                                plan.attacker = 0
                                plan.target = 0
                                plan.attack_index = 0
                                plan.remain_hp = (_op_act_main.hp or 0) - _rule_act_dmg
                                plan.energy = _rule_needs_attach

            # --- Pivote defensivo a Hydrapple ex ---
            # Si nuestro activo es fragil (poca vida / probable KO el proximo
            # turno) y en la banca hay un Hydrapple ex a vida completa con
            # energia propia suficiente (Wild Growth de Meganium cuenta) para
            # noquear al activo rival, conviene RETIRAR al activo fragil y subir
            # a Hydrapple ex: su altisima vida es muy dificil de noquear,
            # mantiene la presion y no regala premios. El activo fragil se
            # resguarda en la banca; el KO se entrega igual pero con un cuerpo
            # mucho mas resistente al frente. Meganium es clave: duplica la
            # energia de Planta, asi que Hydrapple puede atacar con menos cartas.
            # Regla (user, registro 010 paso 82 vs Alakazam): un Tapu Bulu CARGADO
            # en el activo que puede NOQUEAR al activo rival NUNCA se retira; debe
            # atacar. Al ser no-ex, si lo noquean solo entrega 1 premio, asi que
            # rematar con el es mejor que gastar el pivote a Hydrapple ex (2
            # premios). Vetamos el pivote defensivo a Hydrapple cuando el activo es
            # un Tapu Bulu con KO disponible (aunque sea "fragil"): no dispararlo
            # evita ademas que `plan.attacker` apunte a Hydrapple y suprima el ataque.
            _tapu_active_ko_here = False
            if (_ret_active is not None and _ret_active.id == Tapu_Bulu
                    and _op_act_main is not None
                    and len(_ret_active.energies) * _grass_mult() >= 4):
                _tapu_dmg_here = _our_effective_damage(
                    _ret_active, _op_act_main, 220, meganium_in_play,
                    neutralization_zone_active)
                _tapu_active_ko_here = (_tapu_dmg_here > 0
                                        and _tapu_dmg_here >= (_op_act_main.hp or 0))

            if (can_switch and _op_act_main is not None and _ret_active is not None
                    and _ret_active.id != Hydrapple_ex
                    and not _tapu_active_ko_here
                    and (active_ko_likely or active_hp_ratio <= 0.6)):
                _piv_op_hp = _op_act_main.hp or 0
                for _piv_i, _piv_pk in enumerate(my_cards):
                    if _piv_i == 0 or _piv_pk is None or _piv_pk.id != Hydrapple_ex:
                        continue
                    # Solo si Hydrapple ex esta a vida completa (muy dificil de
                    # noquear); si ya esta danado no aporta la ventaja de muro.
                    if _piv_pk.hp < (_piv_pk.maxHp or 0):
                        continue
                    # Necesita energia PROPIA para atacar tras subir (Wild Growth
                    # incluido): el umbral efectivo de Hydrapple ex es 2.
                    if len(_piv_pk.energies) * _grass_mult() < 2:
                        continue
                    _piv_dmg = _our_effective_damage(
                        _piv_pk, _op_act_main, 30 + 30 * total_grass,
                        meganium_in_play, neutralization_zone_active)
                    if _piv_dmg > 0 and _piv_dmg >= _piv_op_hp:
                        plan.attacker = _piv_i
                        plan.target = 0
                        plan.attack_index = 0
                        plan.remain_hp = _piv_op_hp - _piv_dmg
                        plan.energy = False
                        _hydra_pivot_active = True
                        break

            # --- Pivote-muro a Hydrapple ex SIN KO (user, log 85856881 p.127) ---
            # Si `_hydra_wall_pivot` (Ogerpon activo condenado que SI puede atacar
            # pero NO noquea, y muro Hydrapple ex a vida completa en banca que
            # sobrevive), apuntamos el plan al Hydrapple de banca para que la
            # opcion de ATACAR con el Ogerpon fragil quede SUPRIMIDA (plan.attacker
            # >= 1 con retirada disponible -> ver bloque ATTACK), de modo que el
            # agente elija PASS, el motor exponga la retirada (ctx=30) y se suba al
            # muro. No exige `can_switch` (en ctx=0 no hay opcion RETREAT; la
            # retirada solo se expone tras PASS). Solo si aun no hay un plan de
            # pivote con KO fijado.
            if (_hydra_wall_pivot and not _hydra_pivot_active
                    and plan.attacker == 0 and _op_act_main is not None):
                for _hwpp_i, _hwpp_pk in enumerate(my_cards):
                    if (_hwpp_i >= 1 and _hwpp_pk is not None
                            and _hwpp_pk.id == Hydrapple_ex
                            and _hwpp_pk.hp >= (_hwpp_pk.maxHp or 0)
                            and len(_hwpp_pk.energies) * _grass_mult() >= 2):
                        _hwpp_dmg = _our_effective_damage(
                            _hwpp_pk, _op_act_main, 30 + 30 * total_grass,
                            meganium_in_play, neutralization_zone_active)
                        plan.attacker = _hwpp_i
                        plan.target = 0
                        plan.attack_index = 0
                        plan.remain_hp = (_op_act_main.hp or 0) - _hwpp_dmg
                        plan.energy = False
                        break

            # --- Sacrificio de premios: pivote a Tapu Bulu de banca (user) ---
            # Si nuestro activo es un ex (2 premios) en riesgo de ser noqueado el
            # proximo turno y en la banca hay un Tapu Bulu (no-ex, 1 premio) LISTO
            # para atacar que puede noquear al activo rival, conviene RETIRAR al ex
            # y subir a Tapu Bulu para atacar: tomamos el KO igual, pero exponemos
            # al frente solo un cuerpo de 1 premio. Si el rival lo noquea entregamos
            # 1 premio en vez de 2. No aplica si ya pivotamos a un Hydrapple ex de
            # banca (muro a vida completa, mejor cuerpo).
            #
            # Ademas del caso DEFENSIVO (activo en riesgo), permitimos el pivote
            # PROACTIVO (user): con Meganium en juego y un Tapu Bulu de banca ya
            # LISTO (>=4 efectivas) que noquea al activo rival, subir a Tapu Bulu
            # (1 premio) para atacar y NO exponer el ex activo (2 premios), aunque
            # el ex este sano. No aplica en matchups con muros/inmunidades ni con
            # Zona de Neutralizacion.
            _tapu_proactive_lead = (
                meganium_in_play
                and not (op_is_crustle_deck or op_is_cornerstone_deck
                         or op_is_sylveon_deck)
                and not neutralization_zone_active)
            if (not _hydra_pivot_active
                    and _op_act_main is not None and _ret_active is not None
                    and _ret_active.id in OUR_EX_IDS
                    and (active_ko_likely or active_hp_ratio <= 0.5
                         or _tapu_proactive_lead)
                    and my_prize > prize_count(_op_act_main)):
                _tsac_op_hp = _op_act_main.hp or 0
                _tsac_bench_kos = False
                for _tsac_i, _tsac_pk in enumerate(my_cards):
                    if _tsac_i == 0 or _tsac_pk is None or _tsac_pk.id != Tapu_Bulu:
                        continue
                    # Tapu Bulu debe estar LISTO (>=4 de Planta efectiva).
                    if len(_tsac_pk.energies) * _grass_mult() < 4:
                        continue
                    _tsac_dmg = _our_effective_damage(
                        _tsac_pk, _op_act_main, 220,
                        meganium_in_play, neutralization_zone_active)
                    if _tsac_dmg > 0 and _tsac_dmg >= _tsac_op_hp:
                        _tsac_bench_kos = True
                        if can_switch:
                            plan.attacker = _tsac_i
                            plan.target = 0
                            plan.attack_index = 0
                            plan.remain_hp = _tsac_op_hp - _tsac_dmg
                            plan.energy = False
                            _tapu_sac_pivot = True
                        break
                # Si Tapu ya puede rematar desde banca pero NO podemos retirar aun
                # al ex (le falta energia para el coste de retirada) y basta UNA
                # energia mas para habilitarla y tenemos aun el enganche manual de
                # este turno, conviene atacar esa energia al ex activo para poder
                # retirarlo y subir a Tapu. Solo aplica con Tapu YA cargado, de modo
                # que jamas le quitamos energia a Tapu.
                if (_tsac_bench_kos and not can_switch and not state.energyAttached
                        and hand_counts.get(Basic_Grass_Energy, 0) >= 1):
                    _tsac_rc = RETREAT_COST.get(_ret_active.id, 1)
                    _tsac_cur_e = len(_ret_active.energies)
                    if _tsac_cur_e < _tsac_rc and _tsac_cur_e + 1 >= _tsac_rc:
                        _tapu_sac_enable_retreat = True

            # --- Negacion de premios: pivote defensivo a un cuerpo de 1 premio ---
            # Analisis ANTES de atacar (user, log 86211357 paso 128, PERDIDA vs
            # Mega Starmie). Si nuestro activo es un ex (2 premios) que sera
            # NOQUEADO el proximo turno y con ese KO el rival ALCANZA los premios
            # que le faltan para GANAR (prize_count(activo) >= op_prize, con
            # op_prize >= 2), NO conviene atacar con el activo condenado. En su
            # lugar lo retiramos y subimos a un Pokemon de banca de MENOS premios
            # (no-ex = 1 premio) que pueda atacar; asi, aunque lo noqueen, el
            # rival NO completa los premios para ganar ese turno. Preferimos el
            # cuerpo que ademas SOBREVIVA al ataque rival (soporta); si ninguno
            # sobrevive, el de MAS dano. A diferencia de `_tapu_sac_pivot`, este
            # NO exige que el cuerpo noquee al rival: es puramente defensivo
            # (ganar tiempo negando el premio letal). EXCEPCION: si el propio
            # activo puede rematar y GANAR ya este turno, no se retira (se ataca).
            if (not _prize_denial_pivot
                    and not _hydra_pivot_active and not _tapu_sac_pivot
                    and can_switch
                    and _op_act_main is not None and _ret_active is not None
                    and _ret_active.id in OUR_EX_IDS
                    and active_ko_likely
                    and op_prize >= 2
                    and prize_count(_ret_active) >= op_prize):

                # Si el propio activo puede tomar un KO que nos hace GANAR ya,
                # atacamos (no retiramos).
                _pdp_active_wins_now = False
                if my_prize <= prize_count(_op_act_main):
                    _pdp_ae = len(_ret_active.energies)
                    _pdp_aeff = _pdp_ae * _grass_mult()
                    _pdp_abase = 0
                    if _ret_active.id == Hydrapple_ex and _pdp_aeff >= 2:
                        _pdp_abase = 30 + 30 * total_grass
                    elif _ret_active.id == Teal_Mask_Ogerpon_ex and _pdp_aeff >= 3:
                        _pdp_abase = 30 + 30 * _pdp_ae
                    elif _ret_active.id == Fezandipiti_ex and _pdp_aeff >= 3:
                        _pdp_abase = 100
                    if _pdp_abase > 0:
                        _pdp_adm = _our_effective_damage(
                            _ret_active, _op_act_main, _pdp_abase,
                            meganium_in_play, neutralization_zone_active)
                        if _pdp_adm > 0 and _pdp_adm >= (_op_act_main.hp or 0):
                            _pdp_active_wins_now = True

                if not _pdp_active_wins_now:
                    _pdp_best_i = -1
                    _pdp_best_key = None
                    for _pdp_i, _pdp_pk in enumerate(my_cards):
                        if _pdp_i == 0 or _pdp_pk is None:
                            continue
                        # Solo cuerpos que entreguen MENOS premios de los que el
                        # rival necesita para ganar (no-ex): asi el KO no cierra.
                        if prize_count(_pdp_pk) >= op_prize:
                            continue
                        _pdp_req = ATTACK_ENERGY_REQ.get(_pdp_pk.id)
                        if _pdp_req is None:
                            continue
                        _pdp_e = len(_pdp_pk.energies)
                        _pdp_eff = _pdp_e * _grass_mult()
                        _pdp_can_attach = (
                            hand_counts.get(Basic_Grass_Energy, 0) >= 1
                            and not state.energyAttached)
                        _pdp_eff_after = _pdp_eff + (
                            _grass_attach_unit() if _pdp_can_attach else 0)
                        if _pdp_eff_after < _pdp_req:
                            continue  # no puede atacar este turno
                        # Dano estimado del cuerpo contra el activo rival.
                        _pdp_base = 0
                        if _pdp_pk.id == Tapu_Bulu:
                            _pdp_base = 220
                        elif _pdp_pk.id == Meganium:
                            _pdp_base = 140
                        elif _pdp_pk.id == Pinsir:
                            _pdp_base = 100
                        elif _pdp_pk.id == Dipplin:
                            _pdp_base = 20 * max(0, bench_count - 1)
                        _pdp_dmg = _our_effective_damage(
                            _pdp_pk, _op_act_main, _pdp_base,
                            meganium_in_play, neutralization_zone_active
                        ) if _pdp_base > 0 else 0
                        # Preferencia: (sobrevive el ataque rival, dano, vida).
                        _pdp_hp = _pdp_pk.hp or 0
                        _pdp_survives = 1 if (_pdp_hp > _op_best_damage_vs(_pdp_pk)) else 0
                        _pdp_key = (_pdp_survives, _pdp_dmg, _pdp_hp)
                        if _pdp_best_key is None or _pdp_key > _pdp_best_key:
                            _pdp_best_key = _pdp_key
                            _pdp_best_i = _pdp_i
                    if _pdp_best_i >= 1:
                        plan.attacker = _pdp_best_i
                        plan.target = 0
                        plan.attack_index = 0
                        plan.remain_hp = (_op_act_main.hp or 1)
                        plan.energy = False
                        _prize_denial_pivot = True

        _act_stall = my_state.active[0] if my_state.active else None
        if _act_stall is not None:
            # Fuente unica de valores: ATTACK_ENERGY_REQ (solo atacantes
            # principales, mismo conjunto de claves que antes).
            _ATK_REQS_STALL = {k: ATTACK_ENERGY_REQ[k] for k in MAIN_ATTACKERS}
            _stall_req = _ATK_REQS_STALL.get(_act_stall.id, 999)
            _stall_eff = len(_act_stall.energies) * _grass_mult()
            _stall_can_attach = (hand_counts.get(Basic_Grass_Energy, 0) >= 1
                                 and not state.energyAttached)
            _stall_after = _stall_eff + (
                _grass_attach_unit() if _stall_can_attach else 0)

            if _stall_after < _stall_req:

                _nrg_deck = CARTAS_ACTIVAS_EN_MAZO.get(
                    Basic_Grass_Energy, {}).get(ESTADO_MAZO, 0)
                _deck_total = max(1, sum(
                    v.get(ESTADO_MAZO, 0) for v in CARTAS_ACTIVAS_EN_MAZO.values()))

                _td_stall = sum(
                    1 for p in (list(my_state.active or []) + list(my_state.bench))
                    if p is not None and p.id == Teal_Mask_Ogerpon_ex
                    and len(p.energies) >= 1)

                if _td_stall <= 0 or _nrg_deck <= 0:
                    _active_cant_attack_this_turn = True
                else:

                    _p_no = 1.0
                    for _ in range(min(_td_stall, 4)):
                        _p_no *= max(0, _deck_total - _nrg_deck) / _deck_total
                    _active_cant_attack_this_turn = (_p_no > 0.5)

            if _active_cant_attack_this_turn and can_switch:
                for _bp_s in my_state.bench:
                    if (_bp_s is not None and _bp_s.id in _ATK_REQS_STALL
                            and _bp_s.id != Meowth_ex):
                        _bp_eff_s = len(_bp_s.energies) * _grass_mult()
                        if _bp_eff_s >= _ATK_REQS_STALL[_bp_s.id]:
                            _active_cant_attack_this_turn = False
                            break

    def evaluate_supporters() -> dict:
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
        _tapu_can_attack = (field_counts.get(Tapu_Bulu, 0) >= 1 and meganium_in_play and
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
        if (op_is_crustle_deck and op_has_ex_immune_active
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
                                               meganium_in_play,
                                               neutralization_zone_active)
                if damage <= 0:
                    continue  # objetivo inmune / no atacable
                can_ko_target = damage >= (gust_target.hp or 0)
                target_cannot_retreat = (
                    len(gust_target.energies) < RETREAT_COST.get(gust_target.id, 1))
                if can_ko_target or target_cannot_retreat:
                    crustle_gust_worth_it = True
                    break

        if crustle_gust_worth_it:
            values[Boss_Orders] = BOSS_PRIORITY_CRUSTLE_GUST
        elif _fez_active_can_attack:

            values[Boss_Orders] = 0
        elif (op_is_crustle_deck and _tapu_can_attack and not _op_active_is_crustle and
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
        elif budew_on_op_field and budew_op_index >= 1:
            values[Boss_Orders] = 800
        elif op_has_snorunt_bench:
            values[Boss_Orders] = 780
        elif op_has_munkidori and not (op_state.active and op_state.active[0] and op_state.active[0].id == Munkidori):
            values[Boss_Orders] = 750
        elif op_has_dwebble_bench:
            values[Boss_Orders] = 740
        elif op_has_eevee_bench:
            values[Boss_Orders] = 750
        elif op_has_dreepy_line:

            _DRAGAPULT_STAGE = {Dreepy: 1, Drakloak: 2}
            _op_act_dp = op_state.active[0] if op_state.active else None
            _dp_act_stage = (_DRAGAPULT_STAGE.get(_op_act_dp.id, 0)
                             if _op_act_dp is not None else 0)
            _dp_best_bench_stage = 0
            for _dp_bp in op_state.bench:
                if _dp_bp is not None and _dp_bp.id in (Dreepy, Drakloak):
                    _dp_best_bench_stage = max(
                        _dp_best_bench_stage, _DRAGAPULT_STAGE[_dp_bp.id])
            if _dp_best_bench_stage > _dp_act_stage:
                values[Boss_Orders] = 700
            else:
                values[Boss_Orders] = 0

        elif op_has_typhlosion or op_has_ethan_preevo:

            _ETHAN_STAGE = {Cyndaquil: 1, Quilava: 2, Typhlosion: 3}
            _op_act_et = op_state.active[0] if op_state.active else None
            _et_act_stage = (_ETHAN_STAGE.get(_op_act_et.id, 0)
                             if _op_act_et is not None else 0)
            _et_best_bench_stage = 0
            for _et_bp in op_state.bench:
                if _et_bp is not None and _et_bp.id in _ETHAN_STAGE:
                    _et_best_bench_stage = max(
                        _et_best_bench_stage, _ETHAN_STAGE[_et_bp.id])
            if _et_best_bench_stage > _et_act_stage:
                values[Boss_Orders] = 700
            else:
                values[Boss_Orders] = 0

        elif op_is_gardevoir_deck and any(
            p is not None and p.id in (Ralts, Kirlia) for p in op_state.bench):
            values[Boss_Orders] = 730
        elif op_is_alakazam_deck:

            _ALAKAZAM_STAGE = {Abra: 1, Kadabra: 2, Alakazam_ex: 3}
            _op_act_az = op_state.active[0] if op_state.active else None
            _az_act_stage = (_ALAKAZAM_STAGE.get(_op_act_az.id, 0)
                             if _op_act_az is not None else 0)
            _az_best_bench_stage = 0
            for _az_bp in op_state.bench:
                if _az_bp is not None and _az_bp.id in _ALAKAZAM_STAGE:
                    _az_best_bench_stage = max(
                        _az_best_bench_stage, _ALAKAZAM_STAGE[_az_bp.id])
            if _az_best_bench_stage > _az_act_stage:
                values[Boss_Orders] = 700
            else:
                values[Boss_Orders] = 0

        elif op_is_slowking_deck and any(
            p is not None and p.id == Slowpoke for p in op_state.bench):
            values[Boss_Orders] = 710
        elif op_is_dragapult_dusknoir and any(
            p is not None and p.id in (Duskull, Dusclops) for p in op_state.bench):
            values[Boss_Orders] = 700
        elif op_is_zoroark_deck and any(
            p is not None and p.id == Zorua_N for p in op_state.bench):
            values[Boss_Orders] = 690
        elif plan.target >= 1:
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

                if _tgt.id in EX_IMMUNE_IDS and _bo_atk.id in OUR_EX_IDS:
                    return 0
                if _tgt.id in ABILITY_IMMUNE_IDS and _bo_atk.id in OUR_ABILITY_IDS:
                    return 0

                _td = card_table.get(_tgt.id)
                if _bo_atk.id != Fezandipiti_ex and _td:
                    if _td.weakness == EnergyType.GRASS:
                        _d *= 2
                    elif _td.resistance == EnergyType.GRASS:
                        _d -= 30

                if _tgt.id == Drednaw and _d >= 200:
                    return 0
                return _d

            _bo_op_active = op_state.active[0]

            _bo_active_dmg = 0 if op_active_dodge_immune else _boss_dmg_to(_bo_op_active)
            _bo_can_ko_active = (_bo_active_dmg >= (_bo_op_active.hp or 0) and _bo_active_dmg > 0)
            _bo_active_prize = prize_count(_bo_op_active) if _bo_can_ko_active else 0

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
                if op_is_crustle_deck and _bo_bp.id in (Dwebble_Grass, Dwebble_Fighting):
                    continue
                _bo_bp_dmg = _boss_dmg_to(_bo_bp)
                if _bo_bp_dmg > _bo_best_bench_dmg:
                    _bo_best_bench_dmg = _bo_bp_dmg
                if _bo_bp_dmg >= (_bo_bp.hp or 0) and _bo_bp_dmg > 0:
                    _bo_bp_prize = prize_count(_bo_bp)
                    if _bo_bp_prize > _bo_best_bench_prize:
                        _bo_best_bench_prize = _bo_bp_prize

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
                                          and my_prize <= prize_count(_bo_op_active)))
            if _bo_win_via_bench:
                values[Boss_Orders] = max(values.get(Boss_Orders, 0), 990)

                values['_boss_win_via_bench'] = True

            _bo_deny_evo_target = False
            _bo_ko_active_wins = (_bo_can_ko_active
                                  and my_prize <= prize_count(_bo_op_active))

            _bo_cur_act = my_state.active[0] if my_state.active else None
            _bo_de_switch = hand_counts.get(1123, 0) >= 1
            _bo_de_can_retreat = False
            _bo_de_grass_after = total_grass
            if _bo_cur_act is not None:
                _bo_de_rc = RETREAT_COST.get(_bo_cur_act.id, 1)
                if _bo_de_switch or len(_bo_cur_act.energies) >= _bo_de_rc:
                    _bo_de_can_retreat = True
                    _bo_de_grass_after = max(
                        0, total_grass - (0 if _bo_de_switch else _bo_de_rc))
            if not _bo_win_via_bench and not _bo_ko_active_wins:
                for _bo_pe in op_state.bench:
                    if _bo_pe is None:
                        continue
                    # log 86339758 paso 98: Dwebble esta vetado como objetivo de
                    # gusteo en mazo Crustle, no puede motivar negar la linea.
                    if op_is_crustle_deck and _bo_pe.id in (Dwebble_Grass, Dwebble_Fighting):
                        continue

                    _bo_pe_is_threat = _bo_pe.id in THREAT_PREEVO_IDS
                    _bo_pe_is_ex_preevo_energized = (
                        _bo_pe.id in EX_PREEVO_IDS
                        and _bo_pe.id not in NONEX_FINAL_PREEVO_IDS
                        and len(_bo_pe.energies) >= 1
                        and _bo_can_ko_active
                        and prize_count(_bo_op_active) == prize_count(_bo_pe))
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
                        and prize_count(_bo_op_active) <= 1
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
                    if not (_bo_pe_is_threat or _bo_pe_is_ex_preevo_energized
                            or _bo_pe_is_ex_line_vs_wall):
                        continue
                    _bo_pe_dmg = _boss_dmg_to(_bo_pe)
                    _bo_pe_ko = (_bo_pe_dmg >= (_bo_pe.hp or 0) and _bo_pe_dmg > 0)

                    if not _bo_pe_ko and _bo_de_can_retreat:
                        _bo_pe_ko = _bench_attacker_can_ko(
                            my_state, _bo_pe, meganium_in_play, total_grass,
                            bench_count, _bo_de_grass_after,
                            neutralization_zone_active)
                    if _bo_pe_ko:
                        if (_bo_can_ko_active
                                and prize_count(_bo_op_active) >= prize_count(_bo_pe)
                                and not _bo_pe_is_ex_line_vs_wall
                                and not _bo_pe_is_energized_preevo_vs_bare_wall):
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
                            my_state, _bo_al, meganium_in_play, total_grass,
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
            # Boss's Orders mas abajo. El objetivo concreto lo elige _boss_tier.
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
                            my_state, _bo_kp, meganium_in_play, total_grass,
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

            if _bo_best_bench_prize > _bo_active_prize and _bo_best_bench_prize > 0:

                _bo_active_prize_val = prize_count(_bo_op_active)
                _bo_trade_down = (not _bo_can_ko_active and _bo_active_dmg > 0
                                  and _bo_active_prize_val > _bo_best_bench_prize)
                if not _bo_trade_down:
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
                _bo_active_prize_now = prize_count(_bo_op_active)
                if my_prize <= _bo_active_prize_now:
                    values[Boss_Orders] = 0
                elif (_bo_active_prize_now >= _bo_best_bench_prize
                        and len(_bo_op_active.energies) > 0):
                    values[Boss_Orders] = 0
                elif (_bo_op_active.id == Crustle_Grass
                        and _bo_best_bench_prize <= _bo_active_prize_now
                        and len(_bo_op_active.energies) > 0):

                    values[Boss_Orders] = 0

            if (_bo_active_dmg > 0 and not _bo_win_via_bench and not _bo_deny_evo_target
                    and not _bo_dipplin_combo and not _bo_gust_key_bench
                    and not _bo_defensive_gust and not _bo_deny_alakazam_line):
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
            if (op_is_crustle_deck and not crustle_gust_worth_it
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

        if op_has_ability_immune_active and plan.target >= 1:

            _attacker_ready = (plan.attacker >= 0 and not plan.energy)
            _attacker_ready_with_attach = (plan.attacker >= 0 and plan.energy and
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

        if not meganium_in_play and not has_hydrapple:
            values[Dawn] = 900
        elif not meganium_in_play:
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
                not (meganium_in_play and has_hydrapple)):
            if forest_in_play:

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
            lana_val = 300
            if bench_count <= 1:
                lana_val += 400
            elif bench_count <= 2:
                lana_val += 200
            if Chikorita in discard_basic_pokemon and not meganium_in_play:
                if field_counts[Chikorita] + field_counts[Bayleef] + field_counts[Meganium] == 0:
                    lana_val += 350
            if Applin in discard_basic_pokemon and not has_hydrapple:
                if field_counts[Applin] + field_counts[Dipplin] + field_counts[Hydrapple_ex] == 0:
                    lana_val += 300
            if forest_in_play and any(pid in discard_basic_pokemon for pid in (Chikorita, Applin)):
                lana_val += 200
            if total_recoverable >= 3:
                lana_val += 150

            if op_is_crustle_deck:
                _tapu_in_play_lana = field_counts.get(Tapu_Bulu, 0) >= 1
                if Tapu_Bulu in discard_basic_pokemon and not _tapu_in_play_lana:
                    lana_val += 350
                if (Applin in discard_basic_pokemon and
                        field_counts.get(Applin, 0) + field_counts.get(Dipplin, 0) == 0):
                    lana_val += 200

        _lana_energy_enables_attack = False
        if (discard_basic_energy >= 1
                and hand_counts.get(Basic_Grass_Energy, 0) == 0
                and my_state.active and my_state.active[0] is not None):
            _la_active = my_state.active[0]
            _la_mult = _grass_mult()
            _la_cur_eff = len(_la_active.energies) * _la_mult
            if _la_active.id == Hydrapple_ex:

                _la_slots = (0 if state.energyAttached else 1) + 1
                _la_slots = min(_la_slots, discard_basic_energy)
                _la_eff_after = len(_la_active.energies) + _la_slots * _grass_attach_unit()
                if _la_cur_eff < 2 and _la_eff_after >= 2:
                    _lana_energy_enables_attack = True
            elif can_switch or has_switch_card:

                _la_bench_hydra = None
                for _bp in my_state.bench:
                    if _bp is not None and _bp.id == Hydrapple_ex:
                        if (_la_bench_hydra is None or
                                len(_bp.energies) > len(_la_bench_hydra.energies)):
                            _la_bench_hydra = _bp
                if _la_bench_hydra is not None:
                    _la_bh_slots = (0 if state.energyAttached else 1) + 1
                    _la_bh_slots = min(_la_bh_slots, discard_basic_energy)
                    _la_bh_cur_eff = len(_la_bench_hydra.energies) * _la_mult
                    _la_bh_eff_after = len(_la_bench_hydra.energies) + _la_bh_slots * _grass_attach_unit()
                    if _la_bh_cur_eff < 2 and _la_bh_eff_after >= 2:
                        _lana_energy_enables_attack = True
        if _lana_energy_enables_attack:

            lana_val = max(lana_val, 950)

        values[Lanas_Aid] = lana_val
        # Se expone para la capa de scoring PLAY: distingue el caso en que Lana's
        # recupera energia que HABILITA un ataque (unica razon para priorizarla
        # sobre Lillie's cuando no tenemos atacante) del resto.
        values['_lana_enables_attack'] = _lana_energy_enables_attack

        if state.turn == 2 and not we_go_first:
            values[Lillie_Determination] = 1000
            for _sid in (Boss_Orders, Dawn, Lanas_Aid):
                if _sid in values:
                    values[_sid] = min(values[_sid], 200)

        if state.turn <= 2 and hand_size >= 10:
            values[Lillie_Determination] = -1

        if (ko_last_turn and
                hand_counts.get(Dawn, 0) >= 1 and
                hand_counts.get(Lillie_Determination, 0) == 0 and
                hand_counts.get(Meowth_ex, 0) == 0 and
                hand_counts.get(Ultra_Ball, 0) == 0 and
                field_counts.get(Fezandipiti_ex, 0) == 0 and
                CARTAS_ACTIVAS_EN_MAZO.get(Fezandipiti_ex, {}).get(ESTADO_MAZO, 0) > 0 and
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

        if op_is_crustle_deck and values.get(Boss_Orders, 0) > 0:
            _cru_act = op_state.active[0] if op_state.active else None
            _cru_act_ok = (_cru_act is not None and
                           _cru_act.id in (Dwebble_Grass, Crustle_Grass,
                                           Dwebble_Fighting, Crustle_Fighting))
            _cru_has_nondwebble_bench = any(
                bp is not None and bp.id not in (Dwebble_Grass, Dwebble_Fighting)
                for bp in op_state.bench)
            if not _cru_act_ok or not _cru_has_nondwebble_bench:
                values[Boss_Orders] = 0

        # Regla (user, vs Alakazam): con la BANCA LLENA (bench_count >= 5) solo
        # jugamos Dawn si REALMENTE nos falta una evolucion (Fase 1 / Fase 2)
        # para un Pokemon que YA tenemos en juego (banca o activo) y que
        # podriamos evolucionar. Dawn busca hasta 3 Pokemon del mazo a la mano
        # (adelgaza el mazo); con banca llena no podemos bajar basicos nuevos,
        # asi que si NO necesitamos ninguna evolucion, jugar Dawn solo roba /
        # vacia el mazo de mas y arriesga PERDER por deckout (no quedan cartas
        # que robar). En ese caso NO se juega (valor 0). Solo se considera
        # "necesaria" una evolucion si tenemos la pre-evolucion en juego, NO
        # tenemos su evolucion en la mano y esa evolucion sigue disponible en el
        # mazo (Dawn puede traerla).
        if op_is_alakazam_deck and bench_count >= 5:
            _ALK_DAWN_EVO = {
                Chikorita: Bayleef,
                Bayleef: Meganium,
                Applin: Dipplin,
                Dipplin: Hydrapple_ex,
            }
            _alk_dawn_need_evo = False
            for _alk_lo, _alk_hi in _ALK_DAWN_EVO.items():
                if (field_counts.get(_alk_lo, 0) >= 1
                        and hand_counts.get(_alk_hi, 0) < 1
                        and CARTAS_ACTIVAS_EN_MAZO.get(_alk_hi, {}).get(ESTADO_MAZO, 0) > 0):
                    _alk_dawn_need_evo = True
                    break
            if not _alk_dawn_need_evo:
                values[Dawn] = 0

        return values

    _supp_values = evaluate_supporters()

    _best_supp_in_hand_val = 0
    _best_supp_in_hand_id = None
    for sid in (Boss_Orders, Dawn, Lillie_Determination, Lanas_Aid):
        if hand_counts.get(sid, 0) >= 1 and _supp_values.get(sid, 0) > _best_supp_in_hand_val:
            _best_supp_in_hand_val = _supp_values[sid]
            _best_supp_in_hand_id = sid

    _boss_prize_rank = 0
    if (context == SelectContext.MAIN
            and hand_counts.get(Boss_Orders, 0) >= 1
            and op_state.active and op_state.active[0] is not None):
        _bpr_active = my_state.active[0] if my_state.active else None
        _bpr_attach = (hand_counts.get(Basic_Grass_Energy, 0) >= 1
                       and not state.energyAttached)

        _bpr_ret_cost = 0 if has_switch_card else (
            RETREAT_COST.get(_bpr_active.id, 1) if _bpr_active is not None else 1)
        # Wild Growth: cada Planta paga por dos, menos cartas descartadas al retirar.
        _bpr_ret_cards = _retreat_cards(_bpr_ret_cost)
        _bpr_grass_after = max(0, total_grass - _bpr_ret_cards)

        def _bpr_active_can_ko(_tgt):
            if _bpr_active is None or _tgt is None:
                return False
            e = len(_bpr_active.energies)
            eff = e * _grass_mult()
            eff_a = eff + (_grass_attach_unit() if _bpr_attach else 0)
            e_a = e + (1 if _bpr_attach else 0)
            base = _attacker_base_damage(_bpr_active.id, _tgt, eff_a,
                                         grass_scale=total_grass,
                                         teal_self_energy=e_a, bench_count=bench_count)
            if base <= 0:
                return False
            _d = _our_effective_damage(_bpr_active, _tgt, base,
                                       meganium_in_play, neutralization_zone_active)
            return _d >= (_tgt.hp or 0) and _d > 0

        for _bpr_tgt in (op_state.bench or []):
            if _bpr_tgt is None:
                continue
            _bpr_td = card_table.get(_bpr_tgt.id)
            if _bpr_td is None:
                continue
            # log 86339758 paso 98: Dwebble esta vetado como objetivo de gusteo
            # en mazo Crustle; no debe contar en el ranking de premios de Boss's.
            if op_is_crustle_deck and _bpr_tgt.id in (Dwebble_Grass, Dwebble_Fighting):
                continue

            if getattr(_bpr_td, 'megaEx', False):
                _bpr_base = 1
            elif getattr(_bpr_td, 'ex', False):
                _bpr_base = 3
            elif getattr(_bpr_td, 'stage2', False):
                _bpr_base = 5
            elif getattr(_bpr_td, 'stage1', False):
                _bpr_base = 7
            elif _bpr_tgt.id in THREAT_PREEVO_IDS:

                _bpr_base = 7
            else:
                continue

            _bpr_ko = _bpr_active_can_ko(_bpr_tgt)
            if not _bpr_ko and can_switch:
                _bpr_ko = _bench_attacker_can_ko(
                    my_state, _bpr_tgt, meganium_in_play, total_grass,
                    bench_count, _bpr_grass_after, neutralization_zone_active)
            if not _bpr_ko:
                continue
            _bpr_rank = _bpr_base + (0 if len(_bpr_tgt.energies) >= 1 else 1)
            if _boss_prize_rank == 0 or _bpr_rank < _boss_prize_rank:
                _boss_prize_rank = _bpr_rank

    if _bo_active_attack_sufficient or _supp_values.get('_active_attack_sufficient'):
        _boss_prize_rank = 0

    # =================================================================
    # Req H (log 86023830, paso 69): vs mazo Mega Lucario, si el rival
    # tiene un Riolu (pre-evolucion de su atacante principal Mega Lucario
    # ex) en la banca que podemos gustear y noquear, y ya tenemos banca
    # propia establecida (>=2 Pokemon, suficientes atacantes cargados), la
    # prioridad NO es refrescar la mano ni desarrollar (Meowth ex,
    # Chikorita, Tapu...), sino jugar Boss's Orders sobre el Riolu para
    # cortar la linea del atacante principal. `_boss_deny_evo` ya confirma
    # que hay una pre-evolucion ex gusteable y noqueable en la banca rival
    # (muro inofensivo en el activo); el objetivo concreto lo elige
    # _boss_tier, que prefiere el Riolu por THREAT_PREEVO_IDS. Este flag
    # VETA los desarrollos (tier DEVELOP) mas abajo para que Boss's
    # (supporter, tier 0) sea la jugada elegida por encima de Meowth ex.
    # =================================================================
    _lucario_riolu_gust = (
        op_is_lucario_deck
        and not state.supporterPlayed
        and hand_counts.get(Boss_Orders, 0) >= 1
        and bench_count >= 2
        and bool(_supp_values.get('_boss_deny_evo'))
        and any(bp is not None and bp.id == Riolu
                for bp in (op_state.bench or [])))

    _boss_win_via_bench = bool(_supp_values.get('_boss_win_via_bench'))

    _boss_dodge_redirect = bool(_supp_values.get('_boss_dodge_redirect'))

    _boss_deny_alakazam_line = bool(_supp_values.get('_boss_deny_alakazam_line'))

    _best_supp_in_mazo_val = 0
    _best_supp_in_mazo_id = None
    for sid in (Boss_Orders, Dawn, Lillie_Determination, Lanas_Aid):
        if CARTAS_ACTIVAS_EN_MAZO.get(sid, {}).get(ESTADO_MAZO, 0) > 0:
            val = _supp_values.get(sid, 0)
            if val > _best_supp_in_mazo_val:
                _best_supp_in_mazo_val = val
                _best_supp_in_mazo_id = sid

    _gust_2prize_via_boss = False
    _win_via_boss_gust = False
    if (not state.supporterPlayed
            and my_state.active and my_state.active[0] is not None
            and op_state.active and op_state.active[0] is not None
            and op_state.bench
            and (hand_counts.get(Boss_Orders, 0) >= 1
                 or CARTAS_ACTIVAS_EN_MAZO.get(Boss_Orders, {}).get(ESTADO_MAZO, 0) > 0)):
        _mbw_atk = my_state.active[0]
        _mbw_attach = (hand_counts.get(Basic_Grass_Energy, 0) >= 1
                       and not state.energyAttached)

        def _mbw_dmg_to(_tgt):
            if _mbw_atk is None or _tgt is None:
                return 0
            _eff = len(_mbw_atk.energies) * _grass_mult()
            _eff_after = _eff + (_grass_attach_unit() if _mbw_attach else 0)
            _atk_e = len(_mbw_atk.energies) + (1 if _mbw_attach else 0)
            # Dano base via la tabla unica _attacker_base_damage (misma formula
            # y umbrales que antes; el remate debilidad/resistencia/inmunidad
            # queda inline debajo para conservar el comportamiento exacto de
            # este sitio, que NO aplica zona de neutralizacion ni el tope de
            # Crustle a plena vida).
            _d = _attacker_base_damage(_mbw_atk.id, _tgt, _eff_after,
                                       grass_scale=total_grass,
                                       teal_self_energy=_atk_e,
                                       bench_count=bench_count)
            if _d <= 0:
                return 0
            if _tgt.id in EX_IMMUNE_IDS and _mbw_atk.id in OUR_EX_IDS:
                return 0
            if _tgt.id in ABILITY_IMMUNE_IDS and _mbw_atk.id in OUR_ABILITY_IDS:
                return 0
            _td = card_table.get(_tgt.id)
            if _mbw_atk.id != Fezandipiti_ex and _td:
                if _td.weakness == EnergyType.GRASS:
                    _d *= 2
                elif _td.resistance == EnergyType.GRASS:
                    _d -= 30
            if _tgt.id == Drednaw and _d >= 200:
                return 0
            return _d

        _mbw_act = op_state.active[0]
        _mbw_act_dmg = _mbw_dmg_to(_mbw_act)
        _mbw_act_ko = (_mbw_act_dmg >= (_mbw_act.hp or 0) and _mbw_act_dmg > 0)
        _mbw_act_wins = _mbw_act_ko and my_prize <= prize_count(_mbw_act)

        if not _mbw_act_wins:
            for _mbw_bp in op_state.bench:
                if _mbw_bp is None:
                    continue
                # log 86339758 paso 98: Dwebble vetado como gusteo en mazo Crustle.
                if op_is_crustle_deck and _mbw_bp.id in (Dwebble_Grass, Dwebble_Fighting):
                    continue
                _mbw_bp_dmg = _mbw_dmg_to(_mbw_bp)
                if (_mbw_bp_dmg >= (_mbw_bp.hp or 0) and _mbw_bp_dmg > 0
                        and my_prize <= prize_count(_mbw_bp)):
                    _win_via_boss_gust = True
                    break

            _mbw_act_prize = prize_count(_mbw_act) if _mbw_act_ko else 0
            _mbw_best_bench_prize = 0
            for _mbw_bp2 in op_state.bench:
                if _mbw_bp2 is None:
                    continue
                # log 86339758 paso 98: Dwebble vetado como gusteo en mazo Crustle.
                if op_is_crustle_deck and _mbw_bp2.id in (Dwebble_Grass, Dwebble_Fighting):
                    continue
                _mbw_bp2_dmg = _mbw_dmg_to(_mbw_bp2)
                if _mbw_bp2_dmg >= (_mbw_bp2.hp or 0) and _mbw_bp2_dmg > 0:
                    _mbw_bp2_pr = prize_count(_mbw_bp2)
                    if _mbw_bp2_pr > _mbw_best_bench_prize:
                        _mbw_best_bench_prize = _mbw_bp2_pr
            _mbw_trade_down = (not _mbw_act_ko and _mbw_act_dmg > 0
                               and prize_count(_mbw_act) > _mbw_best_bench_prize)
            if (_mbw_best_bench_prize >= 2
                    and _mbw_best_bench_prize > _mbw_act_prize
                    and not _mbw_trade_down):
                _gust_2prize_via_boss = True

    # No malgastar Boss's Orders en un gusteo defensivo si YA podemos noquear al
    # activo rival este mismo turno retirando a un atacante listo de la banca
    # (p. ej. subir a Tapu Bulu). can_attack solo mira el activo actual, no la
    # opcion de retirada, por eso hay que comprobarlo aparte.
    _bdg_retreat_ko = False
    if (can_switch and op_state.active and op_state.active[0] is not None
            and my_state.active and my_state.active[0] is not None):
        _bdg_cur_active = my_state.active[0]
        _bdg_ret_cost = (0 if has_switch_card
                         else RETREAT_COST.get(_bdg_cur_active.id, 1))
        _bdg_ret_cards = _retreat_cards(_bdg_ret_cost)
        _bdg_grass_after = max(0, total_grass - _bdg_ret_cards)
        _bdg_retreat_ko = _bench_attacker_can_ko(
            my_state, op_state.active[0], meganium_in_play, total_grass,
            bench_count, _bdg_grass_after, neutralization_zone_active)

    # Regla (user, log 85804848 paso 49, vs Alakazam, PERDIMOS): si un atacante
    # de banca YA puede noquear al activo rival este turno (retirar+promover,
    # `_bdg_retreat_ko`), Boss's Orders es redundante como remate: no hace falta
    # gustear a la banca para cobrar premio, basta con noquear al activo. En ese
    # caso, si tenemos Lillie's Determination en la mano, refrescar con Lillie's
    # rinde mas que gastar el supporter en un gusteo innecesario, asi que anulamos
    # `_boss_prize_rank` para ceder la prioridad a Lillie's. Se respetan los
    # gusteos realmente ejecutables/valiosos (letal a banca, 2 premios) que se
    # puntuan por sus propias ramas antes que `_boss_prize_rank`.
    if (_bdg_retreat_ko
            and hand_counts.get(Lillie_Determination, 0) >= 1
            and not _win_via_boss_gust
            and not _gust_2prize_via_boss):
        _boss_prize_rank = 0

    _boss_defensive_gust = False
    if (op_is_crustle_deck and not state.supporterPlayed and not can_attack
            and not _bdg_retreat_ko
            and not _conf_should_retreat
            and not _win_via_boss_gust and not _gust_2prize_via_boss
            and hand_counts.get(Boss_Orders, 0) >= 1
            and op_state.active and op_state.active[0] is not None
            and len(op_state.active[0].energies) >= 1
            and op_state.bench):
        _bdg_op_act_rc = RETREAT_COST.get(op_state.active[0].id, 0)
        _bdg_threshold = 1 if _bdg_op_act_rc == 0 else 2
        for _bdg_bp in op_state.bench:
            if _bdg_bp is None:
                continue
            _bdg_rc = RETREAT_COST.get(_bdg_bp.id, 0)
            _bdg_e = len(_bdg_bp.energies)
            if (_bdg_rc - _bdg_e) >= _bdg_threshold:
                _boss_defensive_gust = True
                break

    _meowth_devel_lillie = False
    if (not state.supporterPlayed
            and (hand_counts.get(Meowth_ex, 0) >= 1
                 or field_counts.get(Meowth_ex, 0) >= 1)
            and (CARTAS_ACTIVAS_EN_MAZO.get(Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0
                 or hand_counts.get(Lillie_Determination, 0) >= 1)):
        _mdl_in_play = 0
        for _mdl_p in (list(my_state.active or []) + list(my_state.bench or [])):
            if _mdl_p is not None and _mdl_p.id != Meowth_ex:
                _mdl_in_play += 1
        _mdl_hand_size = len(my_state.hand) if my_state.hand else 0
        _mdl_max_in_play = 4 if _mdl_hand_size <= 2 else 3
        if _mdl_in_play <= _mdl_max_in_play:
            _meowth_devel_lillie = True

    # ¿Nuestro ACTIVO ya es un atacante LISTO para atacar este turno? (activo en
    # MAIN_ATTACKERS con energia efectiva suficiente y podemos atacar). Se usa
    # para no malgastar jugadas en cuerpos de utilidad (p.ej. Meowth ex, que solo
    # busca un Supporter) cuando ya tenemos con que atacar.
    _active_ready_attacker = False
    _ara_act = my_state.active[0] if my_state.active else None
    if (can_attack and _ara_act is not None and _ara_act.id in MAIN_ATTACKERS
            and _can_attack_eff(_ara_act.id, len(_ara_act.energies))):
        _active_ready_attacker = True

    # Numero de atacantes LISTOS (activo + banca) con energia suficiente para
    # atacar ya. Sirve para decidir si merece la pena refrescar la mano (bajar
    # Meowth ex -> Lillie's) o si ya tenemos atacantes de sobra.
    _ready_attacker_count = 0
    for _rac_p in (list(my_state.active or []) + list(my_state.bench or [])):
        if (_rac_p is not None and _rac_p.id in MAIN_ATTACKERS
                and _can_attack_eff(_rac_p.id, len(_rac_p.energies))):
            _ready_attacker_count += 1

    _ctm_dipplin_low = False
    _ctm_tapu_high = False
    _ctm_tapu_ready = False
    if op_is_crustle_deck:
        _ctm_op_act = op_state.active[0] if op_state.active else None
        _ctm_active_is_crustle = (_ctm_op_act is not None and
                                  _ctm_op_act.id in (Crustle_Grass, Crustle_Fighting))
        _ctm_all_in_play = (field_counts.get(Dipplin, 0) >= 1
                            and field_counts.get(Tapu_Bulu, 0) >= 1
                            and field_counts.get(Meganium, 0) >= 1)
        if _ctm_active_is_crustle and _ctm_all_in_play:
            # Tapu Bulu es nuestro mejor atacante vs Crustle (no-ex, 220). Si esta
            # cargado (activo O banca), priorizarlo SIEMPRE: no retirar un Tapu
            # activo ya listo, y si esta en banca hacer el maximo esfuerzo por
            # subirlo a atacar. Solo se pica con Dipplin cuando Tapu NO esta listo.
            for _ctm_tp in (([my_state.active[0]] if my_state.active else [])
                            + list(my_state.bench or [])):
                if (_ctm_tp is not None and _ctm_tp.id == Tapu_Bulu
                        and _can_attack_eff(Tapu_Bulu, len(_ctm_tp.energies))):
                    _ctm_tapu_ready = True
                    break
            if _ctm_tapu_ready:
                _ctm_tapu_high = True
            elif len(_ctm_op_act.energies) <= 2:
                _ctm_dipplin_low = True
            else:
                _ctm_tapu_high = True

    _ctm_chikorita_bench = False
    _ctm_applin_bench = False
    if op_is_crustle_deck:
        _ctm_chikorita_bench = any(
            bp is not None and bp.id in (Chikorita, Bayleef, Meganium)
            for bp in (my_state.bench or []))
        _ctm_applin_bench = any(
            bp is not None and bp.id in (Applin, Dipplin, Hydrapple_ex)
            for bp in (my_state.bench or []))

    _ctm_charge_active_dipplin = False
    if op_is_crustle_deck and not _ctm_tapu_ready:
        _ctm_cad_op_act = op_state.active[0] if op_state.active else None
        _ctm_cad_act_crustle = (_ctm_cad_op_act is not None and
                                _ctm_cad_op_act.id in (Crustle_Grass, Crustle_Fighting))
        _ctm_cad_dipplin_active = (my_state.active and my_state.active[0] is not None
                                   and my_state.active[0].id == Dipplin)
        if _ctm_cad_dipplin_active:
            if _ctm_cad_act_crustle:
                if len(_ctm_cad_op_act.energies) <= 2:
                    _ctm_charge_active_dipplin = True
            else:
                _ctm_charge_active_dipplin = True

    if context == SelectContext.MAIN and _ctm_dipplin_low:
        _my_cards_ctm = ([my_state.active[0]] if my_state.active else [])
        for _bp_ctm in my_state.bench:
            if _bp_ctm is not None:
                _my_cards_ctm.append(_bp_ctm)
        _dip_idx_ctm = -1
        for _idx_ctm, _mc_ctm in enumerate(_my_cards_ctm):
            if _mc_ctm is not None and _mc_ctm.id == Dipplin:
                if _dip_idx_ctm < 0:
                    _dip_idx_ctm = _idx_ctm
                if len(_mc_ctm.energies) >= 1:
                    _dip_idx_ctm = _idx_ctm
                    break
        if _dip_idx_ctm >= 0:
            plan.attacker = _dip_idx_ctm
            plan.target = 0
            plan.attack_index = 0
            plan.energy = (len(_my_cards_ctm[_dip_idx_ctm].energies) < 1)
            if op_state.active and op_state.active[0] is not None:
                plan.remain_hp = (op_state.active[0].hp or 0)

    if context == SelectContext.MAIN and _ctm_tapu_ready:
        _my_cards_tpr = ([my_state.active[0]] if my_state.active else [])
        for _bp_tpr in my_state.bench:
            if _bp_tpr is not None:
                _my_cards_tpr.append(_bp_tpr)
        _tapu_idx_tpr = -1
        for _idx_tpr, _mc_tpr in enumerate(_my_cards_tpr):
            if (_mc_tpr is not None and _mc_tpr.id == Tapu_Bulu
                    and _can_attack_eff(Tapu_Bulu, len(_mc_tpr.energies))):
                _tapu_idx_tpr = _idx_tpr
                break
        if _tapu_idx_tpr >= 0:
            # Tapu Bulu ya cargado: si es el activo (idx 0) se ataca sin retirar;
            # si esta en banca, forzar la promocion retirando el activo.
            plan.attacker = _tapu_idx_tpr
            plan.target = 0
            plan.attack_index = 0
            plan.energy = False
            if op_state.active and op_state.active[0] is not None:
                plan.remain_hp = (op_state.active[0].hp or 0)

    _active_pokemon = my_state.active[0] if my_state.active else None
    _active_needs_energy = False
    if _active_pokemon is not None and not state.energyAttached:
        _act_energy = len(_active_pokemon.energies)
        _act_effective = _act_energy * _grass_mult()
        if _active_pokemon.id == Hydrapple_ex:
            _active_needs_energy = (_act_effective < 2)
        elif _active_pokemon.id == Dipplin:
            _active_needs_energy = (_act_energy < 1)
        elif _active_pokemon.id == Teal_Mask_Ogerpon_ex:
            _active_needs_energy = (_act_effective < 3)
        elif _active_pokemon.id == Tapu_Bulu:

            _active_needs_energy = (_act_effective < 4)
        elif _active_pokemon.id == Pinsir:

            _active_needs_energy = (_act_effective < 2)
        elif _active_pokemon.id == Meowth_ex:

            _active_needs_energy = (_act_energy == 0)
        elif _active_pokemon.id == Fezandipiti_ex:

            _fez_eff_after_att = _act_energy + _grass_attach_unit()
            if _act_effective >= 3:
                _active_needs_energy = False
            elif _fez_eff_after_att >= 3:
                _active_needs_energy = True
            else:

                _active_needs_energy = (_act_energy == 0)
        elif _active_pokemon.id in (Chikorita, Bayleef, Meganium):

            _retreat_needed = RETREAT_COST.get(_active_pokemon.id, 1)
            # Con Wild Growth cada energia basica de Planta vale por dos para
            # pagar la retirada, por lo que basta la energia efectiva (p.ej.
            # Meganium con 1 energia ya puede retirarse: 1*2 >= 2).
            _active_needs_energy = (_act_effective < _retreat_needed)

    _energy_in_hand = hand_counts.get(Basic_Grass_Energy, 0)
    _enough_for_both = (_energy_in_hand >= 2)

    _active_hydra_ready = (
        _active_pokemon is not None
        and _active_pokemon.id == Hydrapple_ex
        and len(_active_pokemon.energies) * _grass_mult() >= 2
    )

    _active_hydra_capped = (
        _active_pokemon is not None
        and _active_pokemon.id == Hydrapple_ex
        and len(_active_pokemon.energies) >= 2
    )

    _bench_has_chargeable = any(bp is not None for bp in (my_state.bench or []))

    _reserve_hydra_active_charge = False
    if (_active_pokemon is not None and _active_pokemon.id == Hydrapple_ex
            and _energy_in_hand == 1 and not op_has_ex_immune_active):
        _rhac_mult = _grass_mult()
        _rhac_cur = len(_active_pokemon.energies) * _rhac_mult
        _rhac_after = len(_active_pokemon.energies) + _grass_attach_unit()
        if _rhac_cur < 2 and _rhac_after >= 2:
            _reserve_hydra_active_charge = True

    _prob_energy_draw_soon = _prob_draw_any(Basic_Grass_Energy, draws=2)
    _energy_starved_low_draw = (
        _active_needs_energy and _energy_in_hand == 0 and
        not state.energyAttached and _prob_energy_draw_soon < 0.5
    )

    _hydrapple_bench_needs_energy = False
    if hand_counts.get(Basic_Grass_Energy, 0) >= 1:
        for _bp in (my_state.bench or []):
            if _bp is not None and _bp.id == Hydrapple_ex:
                _hydra_bench_e = len(_bp.energies)
                _hydra_bench_eff = _hydra_bench_e * _grass_mult()
                if _hydra_bench_eff < 2:
                    _hydrapple_bench_needs_energy = True
                    break

    _energy_demands_before_teal = 0
    if _active_needs_energy:
        _energy_demands_before_teal += 1
    if _hydrapple_bench_needs_energy:
        _energy_demands_before_teal += 1
    _enough_after_priorities = (_energy_in_hand > _energy_demands_before_teal)

    _reserve_energy_for_hydra_evolve = False
    if (_active_pokemon is not None and _active_pokemon.id == Dipplin
            and _energy_in_hand == 1 and not op_has_ex_immune_active):
        _hydra_reachable_this_turn = (
            hand_counts.get(Hydrapple_ex, 0) >= 1
            or hand_counts.get(Ultra_Ball, 0) >= 1)
        if _hydra_reachable_this_turn:
            if len(_active_pokemon.energies) + _grass_attach_unit() >= 2:
                _reserve_energy_for_hydra_evolve = True

    _bcs_playable_in_hand = False
    if hand_counts.get(Bug_Catching_Set, 0) >= 1:
        for _bcs_cid, _bcs_states in CARTAS_ACTIVAS_EN_MAZO.items():
            if _bcs_states[ESTADO_MAZO] <= 0:
                continue
            if _bcs_cid == Basic_Grass_Energy:
                _bcs_playable_in_hand = True
                break
            _bcs_cdata = card_table.get(_bcs_cid)
            if (_bcs_cdata is not None and _bcs_cdata.cardType == CardType.POKEMON
                    and _bcs_cdata.energyType == EnergyType.GRASS):
                _bcs_playable_in_hand = True
                break

    _pp_playable_in_hand = False
    if hand_counts.get(Poke_Pad, 0) >= 1:
        for _pp_cid in (Chikorita, Bayleef, Meganium, Applin, Dipplin, Tapu_Bulu):
            _pp_states = CARTAS_ACTIVAS_EN_MAZO.get(_pp_cid)
            if _pp_states is not None and _pp_states[ESTADO_MAZO] > 0:
                _pp_playable_in_hand = True
                break

    # --- Regla (user): Meowth ex + Lillie's Determination en NUESTRO primer turno ---
    # En nuestro primer turno NO se debe jugar Meowth ex primero: se despliega el
    # resto de la mano (Pokemon basicos y artefactos) y se juega Lillie's
    # Determination al FINAL. Motivo: Lillie's baraja toda la mano en el mazo, asi
    # que cualquier Supporter que Meowth ex buscara terminaria barajado (fetch
    # desperdiciado) y Meowth ex quedaria de mas en la banca como Pokemon de 2
    # premios. EXCEPCION: al finalizar el turno, si en juego solo queda el Pokemon
    # activo (banca vacia) y Meowth ex es la UNICA carta de la mano, entonces si se
    # baja Meowth ex para buscar Lillie's Determination y jugarla el siguiente turno.
    _our_first_turn = ((state.turn == 1 and we_go_first)
                       or (state.turn == 2 and not we_go_first))
    _lillie_available = (
        hand_counts.get(Lillie_Determination, 0) >= 1
        or CARTAS_ACTIVAS_EN_MAZO.get(
            Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0)
    _meowth_hand_only_card = (
        hand_counts.get(Meowth_ex, 0) >= 1
        and (len(my_state.hand) if my_state.hand else 0) == 1)
    _meowth_lone_fetch = (
        _our_first_turn
        and bench_count == 0
        and field_counts.get(Meowth_ex, 0) == 0
        and _meowth_hand_only_card
        and CARTAS_ACTIVAS_EN_MAZO.get(
            Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0)

    _bench_attacker_ready = False
    for _bp in (my_state.bench or []):
        if _bp is None:
            continue
        _bp_e = len(_bp.energies)
        _bp_eff = _bp_e * _grass_mult()
        if _bp.id == Hydrapple_ex and _bp_eff >= 2:
            _bench_attacker_ready = True
            break
        if _bp.id == Teal_Mask_Ogerpon_ex and _bp_eff >= 3:
            _bench_attacker_ready = True
            break
        if _bp.id == Dipplin and _bp_e >= 1:
            _bench_attacker_ready = True
            break
        if _bp.id == Tapu_Bulu and _bp_eff >= 4:
            _bench_attacker_ready = True
            break
        if _bp.id == Pinsir and _bp_eff >= 2:
            _bench_attacker_ready = True
            break
        if _bp.id == Meganium and _bp_eff >= 4:
            _bench_attacker_ready = True
            break

    _bench_attacker_needs_energy = False
    for _bp in (my_state.bench or []):
        if _bp is None:
            continue
        _bp_e = len(_bp.energies)
        _bp_eff = _bp_e * _grass_mult()
        if _bp.id == Hydrapple_ex and _bp_eff < 2:
            _bench_attacker_needs_energy = True
            break
        if _bp.id == Teal_Mask_Ogerpon_ex and _bp_eff < 3:
            _bench_attacker_needs_energy = True
            break
        if _bp.id == Dipplin and _bp_e < 1:
            _bench_attacker_needs_energy = True
            break
        if _bp.id == Tapu_Bulu and _bp_eff < 4:
            _bench_attacker_needs_energy = True
            break

    _op_active_hp = 0
    _op_active_weakness_grass = False
    _op_active_resistance_grass = False
    if op_state.active and op_state.active[0] is not None:
        _op_active_hp = op_state.active[0].hp
        _op_data = card_table.get(op_state.active[0].id)
        if _op_data and _op_data.weakness == EnergyType.GRASS:
            _op_active_weakness_grass = True
        # Resistencia a Grass (p.ej. Archaludon ex): el motor resta 30 de dano
        # (ver _our_effective_damage). Debe restarse aqui para no sobreestimar
        # el Syrup Storm y creer que ya hacemos KO cuando faltan 30.
        if _op_data and _op_data.resistance == EnergyType.GRASS:
            _op_active_resistance_grass = True

    _active_hydra_cannot_ko = False
    if _active_hydra_capped and _op_active_hp > 0:
        _syrup_dmg_now = 30 + 30 * total_grass
        if _op_active_weakness_grass:
            _syrup_dmg_now *= 2
        elif _op_active_resistance_grass:
            _syrup_dmg_now = max(0, _syrup_dmg_now - 30)
        _active_hydra_cannot_ko = (_syrup_dmg_now < _op_active_hp)

    def _extra_energy_enables_ko(pokemon_id: int, current_energy: int) -> bool:
        if _op_active_hp <= 0:
            return False
        _mult = _grass_attach_unit()

        if pokemon_id == Hydrapple_ex:

            _dmg_now = 30 + 30 * total_grass
            _dmg_extra = 30 + 30 * (total_grass + _mult)
            if _op_active_weakness_grass:
                _dmg_now *= 2
                _dmg_extra *= 2
            elif _op_active_resistance_grass:
                _dmg_now = max(0, _dmg_now - 30)
                _dmg_extra = max(0, _dmg_extra - 30)
            return _dmg_now < _op_active_hp <= _dmg_extra

        if pokemon_id == Teal_Mask_Ogerpon_ex:
            _op_e = 0
            if op_state.active and op_state.active[0] is not None:
                _op_e = len(op_state.active[0].energies)
            _my_eff = current_energy
            _dmg_now = 30 + 30 * (_my_eff + _op_e)
            _dmg_extra = 30 + 30 * (_my_eff + _mult + _op_e)
            if _op_active_weakness_grass:
                _dmg_now *= 2
                _dmg_extra *= 2
            elif _op_active_resistance_grass:
                _dmg_now = max(0, _dmg_now - 30)
                _dmg_extra = max(0, _dmg_extra - 30)
            return _dmg_now < _op_active_hp <= _dmg_extra

        return False

    _active_already_kos = False
    if _active_pokemon is not None and _op_active_hp > 0:

        _ak_eff = len(_active_pokemon.energies)
        _ak_dmg = 0
        _ak_is_grass = True
        if _active_pokemon.id == Teal_Mask_Ogerpon_ex and _ak_eff >= 3:
            _ak_op_e = (len(op_state.active[0].energies)
                        if (op_state.active and op_state.active[0] is not None) else 0)
            _ak_dmg = 30 + 30 * _ak_eff
        elif _active_pokemon.id == Hydrapple_ex and _ak_eff >= 2:
            _ak_dmg = 30 + 30 * total_grass
        elif _active_pokemon.id == Tapu_Bulu and _ak_eff >= 4:
            _ak_dmg = 220
        elif _active_pokemon.id == Meganium and _ak_eff >= 4:
            _ak_dmg = 140
        elif _active_pokemon.id == Fezandipiti_ex and _ak_eff >= 3:
            # Cruel Arrow: 100 de dano FIJO (tipo Oscuridad, no Planta) a
            # cualquier Pokemon. Cuenta como KO del activo rival para habilitar
            # la carga del atacante futuro (Tapu Bulu). No aplica la debilidad /
            # resistencia a Planta porque no es dano de Planta.
            _ak_dmg = 100
            _ak_is_grass = False
        if _ak_dmg > 0 and _ak_is_grass and _op_active_weakness_grass:
            _ak_dmg *= 2
        elif _ak_dmg > 0 and _ak_is_grass and _op_active_resistance_grass:
            _ak_dmg = max(0, _ak_dmg - 30)
        _active_already_kos = (_ak_dmg >= _op_active_hp)

    # KO LETAL de Ogerpon por DOBLE carga en un turno (user, log 85803267 turno
    # 4): Myriad Leaf Shower ({G}{G}{G}) hace 30 + 30 por cada energia en AMBOS
    # activos. Si el activo es Teal Mask Ogerpon ex y este turno podemos sumarle
    # DOS energias (adjunte MANUAL + Teal Dance, que adjunta 1 Planta y ademas
    # roba), puede alcanzar las 3 energias necesarias y un dano LETAL (x2 si el
    # rival es debil a Planta, p.ej. Marnie's Grimmsnarl ex 320 HP -> con 3
    # energias y 2 del rival: (30+30*5)*2 = 360 >= 320). El scorer codicioso solo
    # mira +1 energia por opcion, asi que ni `_active_already_kos` ni
    # `_extra_energy_enables_ko` (que solo cuentan +1) detectan este letal de +2;
    # esta bandera evita que se penalice/despriorice cargar el ACTIVO.
    _ogerpon_td_manual_lethal = False
    if (_active_pokemon is not None
            and _active_pokemon.id == Teal_Mask_Ogerpon_ex
            and not state.energyAttached
            and _op_active_hp > 0
            and not _active_already_kos
            and hand_counts.get(Basic_Grass_Energy, 0) >= 2):
        _td_avail_lethal = any(
            o.type == OptionType.ABILITY and o.area == AreaType.ACTIVE
            for o in select.option)
        if _td_avail_lethal:
            _otml_unit = _grass_attach_unit()
            _otml_op_e = (len(op_state.active[0].energies)
                          if (op_state.active and op_state.active[0] is not None)
                          else 0)
            _otml_e_after = len(_active_pokemon.energies) + 2 * _otml_unit
            _otml_dmg = 30 + 30 * _otml_e_after
            if _op_active_weakness_grass:
                _otml_dmg *= 2
            elif _op_active_resistance_grass:
                _otml_dmg = max(0, _otml_dmg - 30)
            if _otml_e_after >= 3 and _otml_dmg >= _op_active_hp:
                _ogerpon_td_manual_lethal = True

    op_active_is_kangaskhan = bool(
        op_state.active and op_state.active[0] is not None
        and op_state.active[0].id == Mega_Kangaskhan_ex)

    op_kang_ko_target = False
    if op_active_is_kangaskhan and _op_active_hp > 0:
        _mult_kk = _grass_attach_unit()

        _kk_grass_max = total_grass
        if not state.energyAttached and hand_counts.get(Basic_Grass_Energy, 0) >= 1:
            _kk_grass_max += _mult_kk
        _syrup_max_kk = 30 + 30 * _kk_grass_max

        _hydra_in_play = field_counts.get(Hydrapple_ex, 0) >= 1
        _dipplin_evolvable = (field_counts.get(Dipplin, 0) >= 1
                              or hand_counts.get(Dipplin, 0) >= 1)
        _hydra_reachable = (
            hand_counts.get(Hydrapple_ex, 0) >= 1
            or (hand_counts.get(Night_Stretcher, 0) >= 1
                and discard_counts.get(Hydrapple_ex, 0) >= 1))

        _hydra_line_available = (
            _hydra_in_play
            or (_dipplin_evolvable and _hydra_reachable))

        if _hydra_line_available and _syrup_max_kk >= _op_active_hp:
            op_kang_ko_target = True

    # NUEVA REGLA (preparar atacante futuro): si Meganium y Tapu Bulu estan en
    # juego y el activo YA asegura el KO al activo rival, cargamos energia en
    # Tapu Bulu (banca) para dejarlo listo como atacante del proximo turno. Con
    # Meganium cada energia basica cuenta como {G}{G}, asi que 2 energias
    # fisicas = 4 efectivas = Tapu Bulu listo para atacar (220). Ademas de la
    # adjuncion manual, aprovechamos la habilidad Ripening Charge de Hydrapple
    # ex (que adjunta a CUALQUIER Pokemon) para poner la 2a energia. Solo aplica
    # fuera de los matchups especiales, que ya tienen su propia logica.
    _tapu_bench_future = None
    for _bp_tf in (my_state.bench or []):
        if _bp_tf is not None and _bp_tf.id == Tapu_Bulu:
            _tapu_bench_future = _bp_tf
            break
    _tapu_future_charge = (
        meganium_in_play
        and _active_already_kos
        and _tapu_bench_future is not None
        and len(_tapu_bench_future.energies) * _grass_mult() < 4
        and not op_is_crustle_deck
        and not op_is_cornerstone_deck
        and not neutralization_zone_active)

    # NUEVA REGLA (ex atascado vs muro inmune): cuando nuestro ACTIVO es un ex
    # que el activo rival BLOQUEA (Crustle inmuniza a nuestros ex; Cornerstone
    # a nuestros Pokemon con habilidad) no hace dano, asi que conviene retirarlo
    # y promover un atacante que SI golpee al muro (el que pega mas fuerte se
    # elige al promover via `_best_promote_card`). Para poder retirar, primero
    # hay que cargar el ex hasta su coste de retirada. `_ex_stuck_promo_ready` =
    # nuestro activo esta bloqueado por el muro Y hay en banca un atacante NO
    # bloqueado y LISTO para golpear al muro este turno.
    _op_wall_active = None
    if op_has_ex_immune_active or op_has_ability_immune_active:
        _op_wall_active = _active_of(op_state)

    def _dmg_vs_wall(_p):
        # Dano efectivo de _p contra el activo rival inmune; 0 si esta bloqueado
        # por la inmunidad o si no puede atacar este turno.
        if _p is None or _op_wall_active is None:
            return 0
        if op_has_ex_immune_active and _p.id in OUR_EX_IDS:
            return 0
        if op_has_ability_immune_active and _p.id in OUR_ABILITY_IDS:
            return 0
        _e = len(_p.energies)
        _eff = _e * _grass_mult()
        # Dano base crudo (sin debilidad/resistencia: es el golpe directo contra
        # el muro) via la tabla unica _attacker_base_damage.
        return _attacker_base_damage(_p.id, _op_wall_active, _eff,
                                     grass_scale=total_grass,
                                     teal_self_energy=_e,
                                     bench_count=bench_count)

    _my_active_pk = (my_state.active[0]
                     if (my_state.active and my_state.active[0] is not None)
                     else None)
    _active_blocked_by_wall = (
        _op_wall_active is not None and _my_active_pk is not None
        and ((op_has_ex_immune_active and _my_active_pk.id in OUR_EX_IDS)
             or (op_has_ability_immune_active and _my_active_pk.id in OUR_ABILITY_IDS)))
    _wall_bench_attacker_ready = any(
        _dmg_vs_wall(_bp) > 0 for _bp in (my_state.bench or []))

    # Regla (user, log 86174943 turno 22, vs Crustle, PERDIDA): si nuestro
    # activo es un Teal Mask Ogerpon ex LISTO para atacar (>=3 efectivas) y este
    # turno podemos jugar Boss's Orders para SUBIR un Mega Kangaskhan ex de la
    # banca rival, NO retiramos a Ogerpon para promover a Dipplin. El Kangaskhan
    # NO es la linea inmune (Crustle), asi que Ogerpon SI lo puede atacar y es su
    # MEJOR atacante; Dipplin se RESERVA para romper el muro Crustle (nuestros ex
    # le hacen 0). Antes, `_ex_stuck_promo_ready` veia el activo Ogerpon bloqueado
    # por el muro Crustle + Dipplin listo en banca y lo retiraba (6000), aunque el
    # plan real del turno era Boss's sobre el Kangaskhan y atacarlo con Ogerpon.
    _keep_ogerpon_for_kang = False
    if (op_is_crustle_deck
            and _my_active_pk is not None
            and _my_active_pk.id == Teal_Mask_Ogerpon_ex
            and len(_my_active_pk.energies) * _grass_mult() >= 3
            and hand_counts.get(Boss_Orders, 0) >= 1
            and not state.supporterPlayed):
        for _kbp in (op_state.bench or []):
            if _kbp is not None and _kbp.id == Mega_Kangaskhan_ex:
                _keep_ogerpon_for_kang = True
                break

    _ex_stuck_promo_ready = (_active_blocked_by_wall and _wall_bench_attacker_ready
                             and not _keep_ogerpon_for_kang)

    # Regla (user, log 86406907 paso 87, GANADA vs Crustle): si nuestro ACTIVO
    # es un atacante NO-ex que SI golpea al muro inmune-a-ex (el activo rival ES
    # el Crustle/Sylveon, op_has_ex_immune_active True) y puede atacar este
    # turno, NUNCA se retira: DEBE atacar. Retirarlo promoveria un Pokemon ex de
    # banca que hace 0 dano al muro (nuestros ex no le pegan). La UNICA razon
    # para retirar vs Crustle es que el activo rival NO sea el muro (p.ej. un
    # Mega Kangaskhan ex), caso en que op_has_ex_immune_active es False y este
    # flag no aplica. `_dmg_vs_wall` ya devuelve 0 para nuestros ex bloqueados y
    # >0 solo para un atacante no-ex con energia suficiente contra ese muro.
    _nonex_active_hits_wall = (
        can_attack
        and op_has_ex_immune_active
        and _my_active_pk is not None
        and _my_active_pk.id not in OUR_EX_IDS
        and _dmg_vs_wall(_my_active_pk) > 0)

    # Pivote Teal Dance -> retirar -> promover atacante letal (user, log
    # 85802744 turno 16): si el activo es un Teal Mask Ogerpon ex BLOQUEADO por
    # el muro rival (Crustle/Sylveon inmuniza a nuestros ex) que AUN no puede
    # retirarse (energia efectiva < coste de retirada) pero hay un atacante
    # no-ex LISTO en banca que SI golpea al muro, y tenemos una Energia Planta
    # basica en mano, la linea correcta es usar TEAL DANCE en el activo (adjunta
    # la Planta al propio activo + ROBA 1 carta) para habilitar su retirada, y
    # NO malgastar la Planta cargando desarrolladores de banca (p.ej. Dipplin).
    # Tras Teal Dance el activo tendra energia para retirarse el proximo paso y
    # subir al atacante que noquea al muro. `_grass_attach_unit()` = energia
    # EFECTIVA que aporta 1 Planta (2 con Meganium en juego, 1 sin).
    _teal_dance_ko_pivot = False
    if (_ex_stuck_promo_ready
            and _my_active_pk is not None
            and _my_active_pk.id == Teal_Mask_Ogerpon_ex
            and hand_counts.get(Basic_Grass_Energy, 0) >= 1):
        _tdkp_rc = RETREAT_COST.get(Teal_Mask_Ogerpon_ex, 1)
        _tdkp_eff_now = len(_my_active_pk.energies) * _grass_mult()
        _tdkp_eff_after = _tdkp_eff_now + _grass_attach_unit()
        if _tdkp_eff_now < _tdkp_rc and _tdkp_eff_after >= _tdkp_rc:
            _teal_dance_ko_pivot = True

    # Pivote Ripening Charge -> retirar -> promover atacante letal (user, log
    # 86028607 turno 22, GANADA): analogo a _teal_dance_ko_pivot pero con el
    # ACTIVO = Hydrapple ex BLOQUEADO por el muro rival (Crustle inmuniza a
    # nuestros ex, Hydrapple ex hace 0). Hydrapple ex no puede atacar pero tiene
    # la habilidad Ripening Charge: se usa para adjuntar una Planta AL PROPIO
    # Hydrapple activo y alcanzar su coste de retirada (EFECTIVO), retirarlo y
    # subir a un atacante no-ex LISTO en banca (Tapu Bulu, 220) que noquea al
    # muro. La retirada se mide en energia EFECTIVA (Wild Growth de Meganium
    # duplica cada Planta fisica), por eso 1 Planta (=2 ef con Meganium) basta
    # para pasar de 2 a 4 ef >= coste 3. Requiere _ex_stuck_promo_ready (activo
    # bloqueado + atacante de banca ya LISTO); por eso solo se activa DESPUES de
    # cargar a Tapu con el adjunte manual (que lo deja listo este mismo turno),
    # momento en que el desempate greedy re-evalua y esta bandera pasa a True.
    _ripen_retreat_ko_pivot = False
    if (_ex_stuck_promo_ready
            and _my_active_pk is not None
            and _my_active_pk.id == Hydrapple_ex
            and hand_counts.get(Basic_Grass_Energy, 0) >= 1):
        _rrkp_rc = RETREAT_COST.get(Hydrapple_ex, 3)
        _rrkp_eff_now = len(_my_active_pk.energies) * _grass_mult()
        _rrkp_eff_after = _rrkp_eff_now + _grass_attach_unit()
        if _rrkp_eff_now < _rrkp_rc and _rrkp_eff_after >= _rrkp_rc:
            _ripen_retreat_ko_pivot = True

    # Pivote Ripening Charge -> cargar Tapu de banca a LETAL -> retirar Hydrapple
    # -> promover Tapu -> noquear al muro (user, log 86182112 paso 82, GANADA vs
    # Crustle). Variante de _ripen_retreat_ko_pivot para cuando el activo
    # Hydrapple ex bloqueado por el muro Crustle YA puede retirarse (energia
    # efectiva >= coste de retirada) pero el Tapu Bulu de banca AUN no esta listo
    # (necesita una 2a Planta para llegar a 4 efectivas = Wood Hammer 220). Sin
    # esta bandera, Teal Dance (Ogerpon, cap Crustle) y Ripening Charge quedaban
    # AMBOS en -1 y el desempate greedy elegia Teal Dance, sobrecargando a
    # Ogerpon (fisicas > cap) y dejando a Tapu en 2 efectivas, sin poder rematar
    # al muro. Ripening Charge (adjunta una Planta a CUALQUIER Pokemon) debe GANAR
    # para poner la 2a Planta en Tapu; el objetivo Tapu se fija en energy_score
    # (ATTACH_FROM, +20000 porque _tapu_eff_ct < 4). Solo se activa DESPUES del
    # adjunte manual que deja a Tapu en 2 efectivas (el greedy re-evalua paso a
    # paso). _grass_attach_unit() = energia EFECTIVA de 1 Planta (2 con Meganium).
    _ripen_bench_tapu_ko_pivot = False
    if (op_is_crustle_deck
            and _active_blocked_by_wall
            and _my_active_pk is not None
            and _my_active_pk.id == Hydrapple_ex
            and hand_counts.get(Basic_Grass_Energy, 0) >= 1):
        _rbtk_rc = RETREAT_COST.get(Hydrapple_ex, 3)
        _rbtk_act_eff = len(_my_active_pk.energies) * _grass_mult()
        if _rbtk_act_eff >= _rbtk_rc:
            _rbtk_unit = _grass_attach_unit()
            _rbtk_req = ATTACK_ENERGY_REQ.get(Tapu_Bulu, 4)
            for _rbtk_bp in (my_state.bench or []):
                if _rbtk_bp is None or _rbtk_bp.id != Tapu_Bulu:
                    continue
                _rbtk_eff_now = len(_rbtk_bp.energies) * _grass_mult()
                _rbtk_eff_after = _rbtk_eff_now + _rbtk_unit
                if _rbtk_eff_now >= _rbtk_req or _rbtk_eff_after < _rbtk_req:
                    continue
                _rbtk_base = _attacker_base_damage(
                    Tapu_Bulu, _op_wall_active, _rbtk_eff_after,
                    grass_scale=total_grass, teal_self_energy=0,
                    bench_count=bench_count)
                if _our_effective_damage(
                        _rbtk_bp, _op_wall_active, _rbtk_base,
                        meganium_in_play) >= (_op_wall_active.hp or 0):
                    _ripen_bench_tapu_ko_pivot = True
                    break

    def energy_score(pokemon: Pokemon, active: bool) -> float:
        energy_count = len(pokemon.energies)
        # Desempate por VIDA (user, log 86212499 paso 151, vs Alakazam, GANADA):
        # cuando hay dos o mas Pokemon IGUALES como objetivo de carga de energia
        # (p.ej. dos Hydrapple ex en banca, uno a 70 hp y otro a 330 hp), SIEMPRE
        # cargar al de MAS vida. Antes ambos caian en la misma rama y obtenian el
        # mismo puntaje entero, asi que el empate lo rompia el orden de opcion
        # (indice de banca menor -> el de 70 hp). Se suma una fraccion DIMINUTA de
        # la vida (< 1 punto: hp/100000, maximo 0.0033) que SOLO altera empates
        # exactos y nunca cruza los umbrales enteros de las demas ramas, de modo
        # que a igualdad de puntaje gana el de mas vida. Cubre el adjunte MANUAL
        # (OptionType.ATTACH) y el objetivo de Ripening Charge
        # (SelectContext.ATTACH_FROM), ya que ambos puntuan via energy_score.
        score = 8000 + (getattr(pokemon, 'hp', 0) or 0) / 100000.0

        # Regla (user, log 86028607 paso 21, vs Crustle, GANAMOS): un Chikorita
        # puede tener como MAXIMO 1 energia. NUNCA adjuntar una 2a energia a un
        # Chikorita (su unico ataque usa 1 energia; el excedente se desperdicia
        # y conviene reservar la energia para atacantes reales o retiradas).
        # Aplica al activo y a la banca, y a cualquier via de adjunte (manual o
        # Ripening Charge). len(energies) es EFECTIVA (Wild Growth de Meganium
        # DUPLICA cada Planta), asi que se convierte a cartas FISICAS.
        if pokemon.id == Chikorita and _physical_energy(energy_count) >= 1:
            return -1

        # Regla (user, log 86607718 turno 2, vs Crustle, PERDIMOS): si empezamos
        # el turno con un Chikorita en el ACTIVO y NINGUN Chikorita en la banca,
        # la prioridad vs Crustle es RETIRARLO (para evolucionarlo a Meganium en
        # la banca y subir un cuerpo util; Chikorita activo es un lastre de 1
        # premio que no ataca al muro). Para poder retirar (coste 1) hace falta
        # cargarle 1 Planta, asi que el adjunte de energia va al Chikorita ACTIVO
        # (0 fisicas) POR ENCIMA de cargar atacantes de banca (p.ej. Tapu Bulu),
        # siempre que exista un cuerpo en banca al que promover tras el retiro.
        # Solo la 1a energia: la regla de "Chikorita max 1" de arriba sigue
        # vigente. Va DESPUES del remate ganador (42000) para no bloquear un KO.
        if (op_is_crustle_deck and active and pokemon.id == Chikorita
                and _physical_energy(energy_count) == 0
                and field_counts.get(Chikorita, 0) <= 1
                and bench_count >= 1
                and not state.energyAttached):
            return 41500

        # Regla (user, log 85855786 paso 141, vs Alakazam, GANAMOS): si este
        # turno existe una jugada GANADORA / de 2 premios via Boss's Orders
        # (gustear al banco rival un objetivo que noqueamos para cobrar los
        # premios que faltan) y ese KO letal se apoya en tener la energia en el
        # ACTIVO (que es el atacante), la carga DEBE ir al ACTIVO. Ganar la
        # partida AHORA es la maxima prioridad y prevalece sobre cargar a Tapu
        # Bulu como atacante FUTURO (`_tapu_future_charge`, 40000), que solo
        # sirve el proximo turno y es irrelevante si ya cerramos la partida.
        if active and (_win_via_boss_gust or _gust_2prize_via_boss):
            return 42000

        # Regla (user, log 86342087 paso 130, vs Mega Lucario, PERDIMOS): si el
        # activo es un Fezandipiti ex DEBIL a Lucha que sera NOQUEADO por Mega
        # Lucario ex el proximo turno (Mega Brave 270 x2 = 540, 2 premios) y en
        # la banca hay un Hydrapple ex sano (muro 330 que SOBREVIVE el golpe
        # rival), la energia de este turno NO debe ir al Feza condenado (que solo
        # atacaria una vez antes de morir regalando 2 premios) sino al Hydrapple:
        # asi lo dejamos listo (>=2 efectivas) para, tras RETIRAR al Feza (coste
        # 1) y promoverlo, atacar con Syrup Storm. Se veta el adjunte al activo
        # y se prioriza cargar el Hydrapple de banca hasta habilitar su ataque.
        # Va DESPUES del remate ganador (42000) para no bloquear un KO letal.
        if _feza_lucario_wall:
            if active:
                return -1
            if (pokemon.id == Hydrapple_ex
                    and len(pokemon.energies) * _grass_mult() < 2):
                return 41000

        # Regla (user): un Tapu Bulu en juego puede tener como MAXIMO 4 energias
        # FISICAS si NO hay Meganium en juego, o 2 si SI hay Meganium. Con
        # Meganium (Wild Growth) cada Planta fisica cuenta DOBLE, asi que 2
        # fisicas = 4 efectivas = suficiente para Wood Hammer (coste 4); sin
        # Meganium hacen falta 4 fisicas. No adjuntar mas: el excedente se
        # desperdicia y conviene reservar la energia. len(energies) es EFECTIVA
        # => se convierte a cartas FISICAS con _physical_energy. Aplica al
        # adjunte manual (OptionType.ATTACH) y al objetivo de Ripening Charge
        # (SelectContext.ATTACH_FROM), activo o banca. Va DESPUES del return de
        # la jugada ganadora (42000) para no bloquear un remate letal.
        if pokemon.id == Tapu_Bulu:
            _tapu_max_phys = 2 if meganium_in_play else 4
            if _physical_energy(energy_count) >= _tapu_max_phys:
                return -1

        # Regla (user, vs Crustle, log 86583376 paso 84): un Teal Mask Ogerpon
        # ex no puede tener mas de DOS energias FISICAS cargadas (por adjunte
        # manual o Ripening Charge). Contra el muro Crustle (que inmuniza a
        # nuestros ex) Ogerpon no puede atacar al muro, asi que RESERVAMOS
        # energia y no lo sobrecargamos. En BANCA el tope es DURO (max 2
        # fisicas). UNICA excepcion para una 3a energia: cuando Ogerpon esta en
        # el ACTIVO y esa energia HABILITA el KO del activo rival
        # (_extra_energy_enables_ko) -- el activo rival no siempre es el muro
        # inmune; puede ser un no-ex al que Ogerpon SI daña. Se conserva ademas
        # el bypass op_kang_ko_target (KO de Mega Kangaskhan ex con Hydrapple
        # ex, donde la energia extra en el tablero sube el dano de Syrup Storm).
        # len(energies) es EFECTIVA (Wild Growth de Meganium duplica cada
        # Planta) => se convierte a cartas FISICAS con _physical_energy.
        if (op_is_crustle_deck and pokemon.id == Teal_Mask_Ogerpon_ex
                and not op_kang_ko_target):
            _crus_phys = _physical_energy(energy_count)
            if not active:
                if _crus_phys >= 2:
                    return -1
            else:
                if _crus_phys >= 3:
                    return -1
                if (_crus_phys >= 2
                        and not _extra_energy_enables_ko(
                            Teal_Mask_Ogerpon_ex, energy_count)):
                    return -1

        # Regla (user, vs Alakazam y vs Hop's): topes de energia para Teal Mask
        # Ogerpon ex (adjunte MANUAL o Ripening Charge). Base FISICA = 4 sin
        # Meganium en juego / 2 con Meganium (Wild Growth duplica cada Planta,
        # asi que 2 fisicas = 4 efectivas = listo para Myriad Leaf Shower coste
        # 3). En BANCA el tope es DURO: no sobrecargamos, reservamos energia. En
        # el ACTIVO se permite UNA energia FISICA extra (la 5a sin Meganium / la
        # 3a con Meganium) SOLO si esa energia es la que HABILITA el KO al activo
        # rival (_extra_energy_enables_ko: el dano actual no noquea pero con +1
        # si). Una linea GANADORA via Boss's ya devolvio 42000 arriba, asi que
        # este tope no bloquea remates letales. len(energies) es EFECTIVA => se
        # convierte a cartas FISICAS con _physical_energy.
        if (op_is_alakazam_deck or op_is_hop_deck) and pokemon.id == Teal_Mask_Ogerpon_ex:
            _alk_base_phys = 2 if meganium_in_play else 4
            _alk_phys = _physical_energy(energy_count)
            if not active:
                if _alk_phys >= _alk_base_phys:
                    return -1
            else:
                if _alk_phys >= _alk_base_phys + 1:
                    return -1
                if (_alk_phys >= _alk_base_phys
                        and not _extra_energy_enables_ko(
                            Teal_Mask_Ogerpon_ex, energy_count)):
                    return -1

        # Matchup Cubchoo (user): topes de energia FISICA por Pokemon. Cubchoo
        # bloquea nuestro ataque el proximo turno, asi que no sobrecargamos y
        # RESERVAMOS energias en la MANO para pagar retiradas. IMPORTANTE: la
        # observacion DUPLICA cada Planta fisica cuando Meganium esta en juego
        # (Wild Growth), asi que len(energies) es EFECTIVA; la convertimos a
        # cartas FISICAS (_cub_phys) para aplicar los topes que el usuario
        # definio en cartas. Aplica al adjunte manual (OptionType.ATTACH) y al
        # objetivo de Ripening Charge (SelectContext.ATTACH_FROM).
        if op_is_cubchoo_deck:
            _cub_phys = _physical_energy(energy_count)
            if pokemon.id == Teal_Mask_Ogerpon_ex and _cub_phys >= (2 if meganium_in_play else 4):
                return -1
            if pokemon.id == Applin and _cub_phys >= 1:
                return -1
            if pokemon.id == Dipplin and _cub_phys >= (1 if meganium_in_play else 2):
                return -1
            if pokemon.id == Hydrapple_ex and _cub_phys >= (2 if meganium_in_play else 3):
                return -1
            # Linea de Meganium (Chikorita/Bayleef/Meganium): tope de 3 energias
            # FISICAS en toda la linea (regla del usuario, cambio 4).
            if pokemon.id in (Chikorita, Bayleef, Meganium) and _cub_phys >= 3:
                return -1

        # Estado de retirada del ACTIVO propio: para promover un Hydrapple ex
        # LETAL de BANCA hay que RETIRAR el activo, lo que exige energia FISICA
        # en el activo >= su coste de retirada. len(energies) es EFECTIVA (Wild
        # Growth de Meganium DUPLICA cada Planta), pero la retirada se paga con
        # cartas FISICAS, asi que fisica = efectiva // 2 cuando Meganium esta en
        # juego. Si el activo AUN NO puede retirarse, la carga debe ir al ACTIVO
        # para empezar a pagar la retirada, no al Hydrapple de banca (que no
        # ataca desde el banco).
        _hls_my_act = (my_state.active[0]
                       if (my_state.active and my_state.active[0] is not None)
                       else None)
        _hls_act_phys = 0
        _hls_act_rc = 1
        if _hls_my_act is not None:
            _hls_act_eff = len(_hls_my_act.energies)
            _hls_act_phys = _physical_energy(_hls_act_eff)
            _hls_act_rc = RETREAT_COST.get(_hls_my_act.id, 1)
        _hls_act_retreatable = (_hls_my_act is None
                                or (_hls_my_act.id == Hydrapple_ex
                                    and not _hydra_fragile_pivot)
                                or _hls_act_phys >= _hls_act_rc)

        # Regla (user): si cargar a un Hydrapple ex de BANCA lo deja listo
        # (>=2 efectivas) para un Syrup Storm LETAL sobre el activo rival,
        # priorizar esa carga (Ripening Charge o adjunte manual) por encima de
        # cualquier otra, para poder promoverlo (retirando el activo) y rematar.
        # Va DESPUES del tope Cubchoo (que reserva energia) y ANTES de la carga
        # de Tapu Bulu, porque ganar la partida es la maxima prioridad. SOLO si
        # el activo YA puede retirarse este turno (si no, la carga letal debe ir
        # al ACTIVO, ver bloque siguiente): cargar un Hydrapple de banca que no
        # se puede promover no sirve (no ataca desde el banco).
        if (not active and pokemon.id == Hydrapple_ex
                and _hls_act_retreatable
                and op_state.active and op_state.active[0] is not None):
            _hls_eff_after = energy_count * _grass_mult() + _grass_attach_unit()
            if _hls_eff_after >= 2:
                _hls_opa = op_state.active[0]
                _hls_opa_hp = _hls_opa.hp or 0
                # total_grass es EFECTIVO; adjuntar 1 Grass suma _grass_attach_unit().
                _hls_dmg = _our_effective_damage(
                    pokemon, _hls_opa,
                    30 + 30 * (total_grass + _grass_attach_unit()),
                    meganium_in_play, neutralization_zone_active)
                if _hls_dmg > 0 and _hls_opa_hp > 0 and _hls_dmg >= _hls_opa_hp:
                    return 41000

        # Regla (user): si el Hydrapple ex LETAL esta en BANCA pero el activo
        # propio AUN NO puede retirarse (energia fisica < coste de retirada), la
        # carga debe ir al ACTIVO para empezar a pagar la retirada y asi habilitar
        # el retiro -> promocion del Hydrapple -> Syrup Storm letal. Solo si la
        # retirada es COMPLETABLE este turno: hacen falta (coste - fisica actual)
        # Plantas y disponemos de al menos esa cantidad en mano y de suficientes
        # adjuntes (1 manual + una Ripening Charge por cada Hydrapple de banca).
        if (active and _hls_my_act is not None
                and not _hls_act_retreatable
                and _hls_my_act.id != Hydrapple_ex
                and op_state.active and op_state.active[0] is not None):
            _hls_bench_hydra = [
                _bp for _bp in (my_state.bench or [])
                if _bp is not None and _bp.id == Hydrapple_ex
                and len(_bp.energies) >= 2]
            _hls_promote_lethal = False
            if _hls_bench_hydra:
                _hls_opa2 = op_state.active[0]
                _hls_opa2_hp = _hls_opa2.hp or 0
                for _bp in _hls_bench_hydra:
                    _hls_bdmg = _our_effective_damage(
                        _bp, _hls_opa2, 30 + 30 * total_grass,
                        meganium_in_play, neutralization_zone_active)
                    if _hls_bdmg > 0 and _hls_opa2_hp > 0 and _hls_bdmg >= _hls_opa2_hp:
                        _hls_promote_lethal = True
                        break
            if _hls_promote_lethal:
                _hls_need = _hls_act_rc - _hls_act_phys
                _hls_grass_hand = sum(
                    1 for _c in (my_state.hand or [])
                    if _c.id == Basic_Grass_Energy)
                _hls_max_attach = 1 + len(_hls_bench_hydra)
                if (_hls_need >= 1 and _hls_grass_hand >= _hls_need
                        and _hls_max_attach >= _hls_need):
                    return 41000

        # Regla (user, log 86027506 paso 81, vs Abomasnow, GANADA): si el ACTIVO
        # es un Hydrapple ex FRAGIL y en la banca hay un Hydrapple ex sano y letal
        # (`_hydra_fragile_pivot`), la energia de este turno debe ir al ACTIVO
        # fragil para alcanzar su coste de retirada (3 fisicas) y poder RETIRARLO
        # (protegerlo) -> promover al sano -> Syrup Storm letal. Cubre el adjunte
        # MANUAL (OptionType.ATTACH) y el objetivo de Ripening Charge
        # (SelectContext.ATTACH_FROM). Solo si la retirada es COMPLETABLE este
        # turno: bastan las Plantas de la mano y los adjuntes disponibles (1
        # manual + una Ripening Charge por cada Hydrapple de banca).
        if (active and _hydra_fragile_pivot
                and _hls_my_act is not None
                and _hls_my_act.id == Hydrapple_ex
                and _hls_act_phys < _hls_act_rc):
            _hfp_need = _hls_act_rc - _hls_act_phys
            _hfp_grass_hand = sum(
                1 for _c in (my_state.hand or [])
                if _c.id == Basic_Grass_Energy)
            _hfp_bench_hydra_ct = sum(
                1 for _bp in (my_state.bench or [])
                if _bp is not None and _bp.id == Hydrapple_ex)
            _hfp_max_attach = (0 if state.energyAttached else 1) + _hfp_bench_hydra_ct
            if (_hfp_need >= 1 and _hfp_grass_hand >= _hfp_need
                    and _hfp_max_attach >= _hfp_need):
                return 41000

        # Pivote Ripening -> retirar -> promover Tapu letal vs muro inmune (user,
        # log 86028607 turno 22): si _ripen_retreat_ko_pivot esta activo (activo
        # = Hydrapple ex bloqueado por Crustle con un Tapu de banca YA LISTO que
        # noquea al muro), la Planta de Ripening Charge debe ir al PROPIO
        # Hydrapple ACTIVO para alcanzar su coste de retirada (efectivo) y poder
        # retirarlo -> subir a Tapu -> Wood Hammer letal. Cubre el objetivo de
        # Ripening Charge (SelectContext.ATTACH_FROM); el adjunte manual ya se
        # gasto en cargar a Tapu (por eso el pivote solo existe tras esa carga).
        if _ripen_retreat_ko_pivot and active and pokemon.id == Hydrapple_ex:
            return 41000

        # Regla (user, log 85857426 paso 37, vs Mega Lucario, PERDIMOS): NO
        # malgastar el adjunte manual en un Tapu Bulu ACTIVO condenado. Si el
        # activo es un Tapu Bulu que, tras adjuntar 1 Planta, SIGUE sin poder
        # atacar (Wood Hammer necesita 4 efectivas) y SIGUE sin poder retirarse
        # (energia FISICA < coste de retirada 3) — la energia no le sirve este
        # turno y sera noqueado el proximo — y ademas en la banca hay un Teal
        # Mask Ogerpon ex sin cargar (energia < 3) al que Teal Dance puede
        # adjuntar Grass + ROBAR, vetar el adjunte manual (-1). Asi el orden de
        # jugada (ATTACH es tier ENERGY=1, Teal Dance ABILITY es tier 0) ya no
        # antepone la carga desperdiciada y se usa Teal Dance: no se pierde la
        # energia y se roba una carta. Acotado a Mega Lucario (remate rival
        # fijo y alto). Cubre el adjunte MANUAL (OptionType.ATTACH) y el objetivo
        # de Ripening Charge (SelectContext.ATTACH_FROM).
        if (active and pokemon.id == Tapu_Bulu and op_is_lucario_deck
                and hand_counts.get(Basic_Grass_Energy, 0) >= 1):
            _twt_eff_after = energy_count + _grass_attach_unit()
            _twt_phys_after = _physical_energy(energy_count) + 1
            _twt_rc = RETREAT_COST.get(Tapu_Bulu, 3)
            if _twt_eff_after < 4 and _twt_phys_after < _twt_rc:
                for _twt_bp in (my_state.bench or []):
                    if (_twt_bp is not None
                            and _twt_bp.id == Teal_Mask_Ogerpon_ex
                            and len(_twt_bp.energies) < 3):
                        return -1

        # Prioridad maxima: cargar Tapu Bulu de banca como atacante futuro
        # cuando el activo ya asegura el KO y Meganium esta en juego. Reusada
        # tanto por la adjuncion manual (OptionType.ATTACH) como por el objetivo
        # de Ripening Charge (SelectContext.ATTACH_FROM).
        if (_tapu_future_charge and not active and pokemon.id == Tapu_Bulu
                and len(pokemon.energies) * _grass_mult() < 4):
            return 40000

        if (op_is_crustle_deck or op_is_cornerstone_deck) and \
                pokemon.id == Meganium and energy_count >= 4:
            return -1

        if is_confused and _conf_active is not None:
            if (not active and _conf_is_matchup_attacker(pokemon.id)
                    and not _conf_can_attack_pkmn(pokemon)):
                return 40000
            if active and _conf_bench_attacker_ready and not _conf_active_can_retreat:
                _ret_eff_es = energy_count * _grass_mult()
                if _ret_eff_es < RETREAT_COST.get(pokemon.id, 1):
                    return 35000
            if (active and not _conf_bench_attacker_body
                    and _conf_is_matchup_attacker(pokemon.id)
                    and not _conf_active_can_attack):
                return 33000

        if op_is_cornerstone_deck and not op_is_crustle_deck:

            if pokemon.id == Tapu_Bulu:

                if energy_count < 4:
                    score += 22000
                    if active:
                        score += 100
                else:
                    score -= 50
            elif pokemon.id == Pinsir:

                if energy_count < 2:
                    score += 23000
                    if active:
                        score += 100
                else:
                    score -= 50
            elif pokemon.id == Teal_Mask_Ogerpon_ex:

                if active and energy_count == 0:
                    _tapu_ready_cs = any(
                        bp is not None and bp.id == Tapu_Bulu and len(bp.energies) >= 4
                        for bp in (my_state.bench or []))
                    if _tapu_ready_cs:
                        score += 10
                        score += 40
                    else:
                        score -= 500
                else:
                    score -= 500
            else:

                if active and energy_count == 0:
                    _tapu_ready_cs2 = any(
                        bp is not None and bp.id == Tapu_Bulu and len(bp.energies) >= 4
                        for bp in (my_state.bench or []))
                    if _tapu_ready_cs2:
                        score += 10
                        score += 30
                    else:
                        score -= 300
                else:
                    score -= 300
            return score

        if op_is_crustle_deck:

            # Energia EXCEDENTE: si el Tapu Bulu ACTIVO ya esta cargado (>=4
            # efectivas) puede atacar sin mas, asi que la adjuncion manual de
            # este turno no debe desperdiciarse sobrecargandolo. Se redirige por
            # orden de prioridad: (1) otro Tapu Bulu de banca que aun no llega a
            # 4 efectivas, (2) Dipplin sin energia, (3) Meganium sin sus 4
            # efectivas. Si ninguno la necesita, se GUARDA la energia (score
            # negativo -> el agente no la juega).
            _ctm_act_te = my_state.active[0] if my_state.active else None
            _ctm_active_tapu_full = (
                _ctm_act_te is not None
                and _ctm_act_te.id == Tapu_Bulu
                and len(_ctm_act_te.energies) * _grass_mult() >= 4)
            if _ctm_active_tapu_full:
                if (pokemon.id == Tapu_Bulu and not active
                        and energy_count * _grass_mult() < 4):
                    return 40000
                if pokemon.id == Dipplin and energy_count < 1:
                    return 39000
                if pokemon.id == Meganium and energy_count * _grass_mult() < 4:
                    return 38000
                return -1

            if pokemon.id == Tapu_Bulu:

                # Regla (user, log 85802744 paso 55): si Meganium AUN no esta en
                # juego pero se puede evolucionar ESTE turno (Bayleef en juego +
                # Meganium en mano), Wild Growth doblara las energias fisicas
                # ACTUALES de Tapu Bulu. Si con ese doblado Tapu ya alcanza sus 4
                # efectivas (>= 2 energias fisicas ahora), NO malgastar el adjunte
                # manual sobrecargandolo: se reserva la energia y se evoluciona
                # Meganium, que deja a Tapu listo para atacar sin gastarla. El
                # scorer es codicioso (no simula "evolucionar primero"), por eso
                # aqui, con Meganium fuera de juego, veia a Tapu con solo sus
                # fisicas (< 4) y le daba prioridad de carga.
                _meg_evolvable_now_tapu = (
                    not active
                    and not meganium_in_play
                    and field_counts.get(Bayleef, 0) >= 1
                    and hand_counts.get(Meganium, 0) >= 1)
                if _meg_evolvable_now_tapu and energy_count * 2 >= 4:
                    return -1

                # len(energies) YA es la energia EFECTIVA (la observacion duplica
                # la Planta por Wild Growth): Wood Hammer necesita 4 efectivas.
                # No sobrecargar mas alla de eso.
                _tapu_eff_ct = energy_count * _grass_mult()
                if _tapu_eff_ct < 4:
                    score += 20000
                    if _ctm_tapu_high:

                        score += 5000
                    if _ctm_chikorita_bench:

                        score += 11000
                    if active:
                        score += 100
                else:
                    score -= 50
            elif pokemon.id == Teal_Mask_Ogerpon_ex:

                if active and energy_count == 0:

                    _tapu_bench_og = any(
                        bp is not None and bp.id in (Tapu_Bulu, Dipplin, Meganium) and
                        len(bp.energies) >= (1 if bp.id == Dipplin else 4)
                        for bp in (my_state.bench or []))
                    if _tapu_bench_og:
                        score += 10
                        score += 40
                    else:
                        score -= 500
                else:
                    score -= 500
            elif pokemon.id == Applin:

                if energy_count < 1:
                    score += 22000
                    if _ctm_applin_bench and not _ctm_chikorita_bench:

                        score += 6500
                    if active:
                        score += 100
                else:
                    score -= 40
            elif pokemon.id == Dipplin:

                if _ctm_charge_active_dipplin and active and energy_count < 1:

                    score = 50000
                elif _ctm_tapu_high:

                    score = -1
                elif energy_count < 1:
                    score += 23000
                    if active:
                        score += 100
                else:
                    score = -1
            elif pokemon.id == Pinsir:

                if energy_count < 2:
                    score += 21000
                    if active:
                        score += 100
                else:
                    score -= 50
            elif pokemon.id == Meganium:

                # Meganium es el duplicador clave contra Crustle; no debe quedarse
                # de muro en el activo. Si esta activo y aun no puede retirarse
                # (0 energias) y hay un atacante no-ex de banca ya cargado para
                # promover, priorizamos cargarle 1 energia: con Wild Growth
                # 1 energia basica = {G}{G}, suficiente para pagar su retirada de 2
                # y sacarlo a la banca el proximo turno.
                _meg_promo_ready = any(
                    bp is not None and (
                        (bp.id == Tapu_Bulu and
                         len(bp.energies) * _grass_mult() >= 4) or
                        (bp.id == Dipplin and len(bp.energies) >= 1) or
                        (bp.id == Pinsir and
                         len(bp.energies) * _grass_mult() >= 2))
                    for bp in (my_state.bench or []))

                _tapu_in_play_meg = field_counts.get(Tapu_Bulu, 0) >= 1
                _dipplin_in_play_meg = any(
                    bp is not None and bp.id == Dipplin
                    for bp in (list(my_state.active or []) + list(my_state.bench)))

                # len(energies) YA es la energia EFECTIVA (Wild Growth ya aplicado
                # en la observacion): Solar Beam necesita 4.
                _meg_eff = energy_count * _grass_mult()
                if active and energy_count == 0 and _meg_promo_ready:
                    score += 24000
                    score += 100
                elif not _tapu_in_play_meg and not _dipplin_in_play_meg and _meg_eff < 4:
                    score += 19000
                    if active:
                        score += 100
                elif _meg_eff < 4:
                    score -= 50
                else:
                    score -= 80
            else:

                if (active and pokemon.id in OUR_EX_IDS
                        and _ex_stuck_promo_ready
                        and energy_count * _grass_mult()
                            < RETREAT_COST.get(pokemon.id, 1)):
                    # Nuestro ex activo no puede danar al Crustle (inmune) y hay
                    # un atacante no-ex LISTO en banca: cargamos el ex hasta su
                    # coste de retirada para poder retirarlo el proximo paso y
                    # promover al atacante que SI golpea al Crustle.
                    score += 24000
                    score += 100
                elif active:
                    score += 10

                    _tapu_on_bench = field_counts.get(Tapu_Bulu, 0) >= 1
                    if _tapu_on_bench and energy_count == 0:
                        score += 50
                    else:
                        score -= 300
                else:
                    score -= 300
            return score

        if neutralization_zone_active:
            if pokemon.id == Tapu_Bulu:
                effective_energy = energy_count * _grass_mult()
                if active:
                    score += 10
                    if effective_energy < 4:
                        score += 23200
                    else:
                        score -= 50
                else:
                    if effective_energy < 4:
                        score += 600
                    else:
                        score -= 80
                return score
            elif pokemon.id == Dipplin:
                if active:
                    score += 10
                    if energy_count < 1:
                        score += 23200
                    else:
                        score -= 30
                else:
                    if energy_count < 1:
                        score += 400
                    else:
                        score -= 50
                return score
            elif pokemon.id == Pinsir:

                effective_energy = energy_count * _grass_mult()
                if active:
                    score += 10
                    if effective_energy < 2:
                        score += 23000
                    else:
                        score -= 40
                else:
                    if effective_energy < 2:
                        score += 380
                    else:
                        score -= 60
                return score
            elif pokemon.id == Meganium:

                effective_energy = energy_count * _grass_mult()
                if active:
                    score += 10
                    if effective_energy < 4:
                        score += 15000
                    else:
                        score -= 100
                else:
                    if effective_energy < 4:
                        score += 300
                    else:
                        score -= 100
                return score
            elif pokemon.id == Teal_Mask_Ogerpon_ex:

                if energy_count >= 2:
                    score -= 500
                elif active:
                    score += 10
                    score += 100
                else:
                    score += 200
                return score
            elif pokemon.id in OUR_EX_IDS:

                _op_act_nz_e = op_state.active[0] if op_state.active else None
                _op_nz_e_rb = False
                if _op_act_nz_e is not None:
                    _op_nz_e_data = card_table[_op_act_nz_e.id]
                    _op_nz_e_rb = (_op_nz_e_data.ex or _op_nz_e_data.megaEx)
                if _op_nz_e_rb:
                    pass
                elif active:
                    score += 10
                    score -= 200
                    return score
                else:
                    score -= 300
                    return score

        if (meganium_in_play and _active_pokemon is not None
                and _active_pokemon.id == Hydrapple_ex
                and len(_active_pokemon.energies) >= 1
                and _bench_has_chargeable
                and not op_is_crustle_deck and not op_is_cornerstone_deck
                and not neutralization_zone_active):

            if active:
                return -1
            _raw_mb = len(pokemon.energies)
            if pokemon.id == Hydrapple_ex:
                return 20000 if _raw_mb < 1 else -1
            if pokemon.id == Teal_Mask_Ogerpon_ex:

                return 19000 if _raw_mb < 2 else 5000
            if pokemon.id == Dipplin:
                return 18000 if _raw_mb < 1 else -1
            if pokemon.id == Meganium:
                return 17000 if _raw_mb < 2 else -1
            if pokemon.id == Tapu_Bulu:
                return 16000 if _raw_mb < 2 else -1
            return -1

        if (_active_hydra_capped and _bench_has_chargeable
                and not op_is_crustle_deck and not op_is_cornerstone_deck
                and not neutralization_zone_active):
            if active:
                return -1
            _eff_bench_sc = energy_count * _grass_mult()
            if pokemon.id == Teal_Mask_Ogerpon_ex:

                if energy_count < 3:
                    return 20000 - energy_count * 100
                return -1
            if pokemon.id == Meganium:
                return 18000 if energy_count < 2 else -1
            if pokemon.id == Hydrapple_ex:
                return 16000 if _eff_bench_sc < 2 else -1
            if pokemon.id == Dipplin:
                return 14000 if energy_count < 1 else -1
            if pokemon.id == Applin:
                return 12000 if energy_count < 2 else -1
            if pokemon.id == Tapu_Bulu:
                _tapu_cap_sc = 4
                return 10000 if _eff_bench_sc < _tapu_cap_sc else -1

            return 8000 if energy_count < 1 else -1

        if _active_already_kos and not active and energy_count == 0 \
                and not op_is_crustle_deck and not op_is_cornerstone_deck \
                and not neutralization_zone_active:
            if pokemon.id in NON_ATTACKER_ENERGY_WASTE_IDS:
                return -1
            return {
                Hydrapple_ex: 30000,
                Teal_Mask_Ogerpon_ex: 29000,
                Dipplin: 28000,
                Meganium: 27000,
                Tapu_Bulu: 26000,
            }.get(pokemon.id, 25000)

        _bench_hydra_pre_target = any(
            bp is not None and bp.id in (Dipplin, Applin) and len(bp.energies) < 1
            for bp in (my_state.bench or []))
        if (not op_is_crustle_deck and not op_is_cornerstone_deck
                and not neutralization_zone_active
                and not _active_needs_energy
                and _active_pokemon is not None
                and _active_pokemon.id != Hydrapple_ex
                and _bench_hydra_pre_target):
            if active:
                return -1
            if pokemon.id == Dipplin and energy_count < 1:
                return 24000
            if pokemon.id == Applin and energy_count < 1:
                return 23500

        if active:
            score += 10

            if active_ko_likely:
                _after_energy = energy_count + _grass_attach_unit()
                _after_energy_raw = energy_count + 1

                _can_attack_after = False
                if pokemon.id == Hydrapple_ex:
                    _can_attack_after = (_after_energy >= 2)
                elif pokemon.id == Dipplin:
                    _can_attack_after = (_after_energy_raw >= 1)
                elif pokemon.id == Teal_Mask_Ogerpon_ex:
                    _can_attack_after = (_after_energy >= 3 or _ogerpon_td_manual_lethal)
                elif pokemon.id == Tapu_Bulu:
                    _can_attack_after = (_after_energy >= 4)
                elif pokemon.id == Fezandipiti_ex:
                    _can_attack_after = (_after_energy >= 3)

                _retreat_cost_pkmn = RETREAT_COST.get(pokemon.id, 1)
                # Energia efectiva tras adjuntar (Wild Growth duplica Planta):
                # 1 energia en Meganium ya paga su retirada de 2.
                _can_retreat_after = (_after_energy >= _retreat_cost_pkmn)

                _has_bench_atk_retreat = False
                for _bp in (my_state.bench or []):
                    if _bp is not None and _bp.id in (Hydrapple_ex, Dipplin, Teal_Mask_Ogerpon_ex, Tapu_Bulu, Fezandipiti_ex):
                        _has_bench_atk_retreat = True
                        break

                if not _can_attack_after and (not _can_retreat_after or not _has_bench_atk_retreat):
                    return score - 100

            effective_energy = energy_count * _grass_mult()

            if pokemon.id == Hydrapple_ex:
                energy_threshold = 2
                if effective_energy < energy_threshold:
                    score += 23200
                    if op_is_fire_deck:
                        score += 500
                    if op_is_aggro_deck or op_is_beedrill_deck:
                        score += 300
                elif energy_count < 2:

                    score += 23200
                elif _extra_energy_enables_ko(Hydrapple_ex, energy_count):

                    score += 15000
                elif _bench_attacker_ready and not _active_already_kos:

                    score += 23200
                else:
                    score -= 100
            elif pokemon.id == Dipplin:
                if energy_count < 1:
                    score += 23200
                    if op_has_ex_immune_active:
                        score += 500
                else:
                    score -= 30
            elif pokemon.id == Teal_Mask_Ogerpon_ex:
                if effective_energy < 3:
                    score += 23200
                elif energy_count < 3:

                    score += 23200
                elif _extra_energy_enables_ko(Teal_Mask_Ogerpon_ex, energy_count):

                    score += 15000
                elif (_bench_attacker_ready and not _bench_attacker_needs_energy
                        and not _active_already_kos):

                    score += 23200
                else:

                    score -= 100
            elif pokemon.id == Tapu_Bulu:

                if energy_count < 4:
                    if meganium_in_play:
                        score += 23200
                        if op_has_ex_immune_active:
                            score += 500
                    else:
                        score += 15000
                else:
                    score -= 80
            elif pokemon.id == Meganium:

                _sylveon_active = (op_state.active and op_state.active[0] is not None
                                   and op_state.active[0].id == Sylveon)
                if op_is_drednaw_deck or _sylveon_active:

                    _meg_eff = energy_count * _grass_mult()
                    if _meg_eff < 4:
                        score += 23200
                    else:
                        score -= 100
                elif energy_count < 2:
                    score += 23200
                else:
                    score -= 500
            elif pokemon.id in (Chikorita, Bayleef):

                _retreat_cost = RETREAT_COST.get(pokemon.id, 1)
                # Wild Growth duplica la energia basica de Planta para la retirada.
                _cb_ret_eff = energy_count * _grass_mult()
                if _cb_ret_eff < _retreat_cost:
                    score += 23200
                else:
                    score -= 500
            elif pokemon.id == Meowth_ex:

                # Meowth ex ACTIVO: solo lo cargamos cuando la retirada es NECESARIA,
                # es decir cuando hay un atacante real en banca al que promover. Si
                # no hay a quien pasar, cargarlo no aporta y se demota.
                if energy_count == 0:
                    _has_bench_attacker = False
                    for _bp in my_state.bench:
                        if _bp is not None and _bp.id in (Hydrapple_ex, Dipplin, Teal_Mask_Ogerpon_ex, Tapu_Bulu, Fezandipiti_ex):
                            _has_bench_attacker = True
                            break
                    if _has_bench_attacker:
                        score += 23200
                    else:
                        score -= 500
                else:
                    score -= 500
            elif pokemon.id == Fezandipiti_ex:

                _fez_eff = energy_count * _grass_mult()
                _fez_eff_after = energy_count + _grass_attach_unit()
                if _fez_eff >= 3:

                    score -= 100
                elif _fez_eff_after >= 3:

                    score += 23200
                elif energy_count == 0:

                    _has_bench_attacker = False
                    for _bp in my_state.bench:
                        if _bp is not None and _bp.id in (Hydrapple_ex, Dipplin, Teal_Mask_Ogerpon_ex, Tapu_Bulu):
                            _has_bench_attacker = True
                            break
                    if _has_bench_attacker:
                        score += 23200
                    else:
                        score += 5000
                else:

                    score -= 200
            elif pokemon.id == Pinsir:

                if effective_energy < 2:
                    score += 23200
                    if op_has_ex_immune_active:
                        score += 500
                else:
                    score -= 60

        else:

            if pokemon.id == Teal_Mask_Ogerpon_ex:
                if energy_count < 2:
                    score += 400
                elif energy_count < 3:
                    score += 250
                elif _extra_energy_enables_ko(Teal_Mask_Ogerpon_ex, energy_count):
                    score += 150
                else:
                    score -= 100
            elif pokemon.id == Tapu_Bulu:

                if not meganium_in_play:
                    score -= 100
                elif op_has_ex_immune_active or op_has_ex_immune_bench:
                    if energy_count < 2:
                        score += 350
                    else:
                        score -= 80
                elif energy_count < 2:
                    score += 100
                else:
                    score -= 80
            elif pokemon.id == Hydrapple_ex:

                effective_energy = energy_count * _grass_mult()
                if effective_energy < 2:

                    score += 23100
                    if op_is_fire_deck:
                        score += 100
                    if op_is_aggro_deck or op_is_beedrill_deck:
                        score += 80
                elif energy_count < 2:
                    score += 150
                    if op_is_fire_deck:
                        score += 100
                elif _extra_energy_enables_ko(Hydrapple_ex, energy_count):
                    score += 100
                else:
                    score -= 100
            elif pokemon.id == Dipplin:
                if energy_count < 1:
                    score += 150
                    if op_has_ex_immune_active:
                        score += 80

                    if op_is_drednaw_deck:
                        score += 200

                    elif op_is_sylveon_deck:
                        score += 150
                else:
                    score -= 30
            elif pokemon.id == Applin:

                if energy_count == 0:
                    score += 40
                elif energy_count == 1:
                    _applin_full_evolve_now = (hand_counts.get(Dipplin, 0) >= 1 and
                                               hand_counts.get(Hydrapple_ex, 0) >= 1)
                    if _applin_full_evolve_now and not meganium_in_play:
                        score += 50
                    else:
                        score -= 300
                else:
                    score -= 400
            elif pokemon.id == Meganium:

                _sylveon_threat = (op_is_sylveon_deck and op_has_ex_immune_active and
                                   op_state.active and op_state.active[0] is not None and
                                   op_state.active[0].id == Sylveon)
                if op_is_drednaw_deck or _sylveon_threat:
                    _meg_eff_bench = energy_count * _grass_mult()
                    if _meg_eff_bench < 4:
                        score += 500
                    else:
                        score -= 50
                elif energy_count >= 2:
                    score -= 100
                elif (has_hydrapple and _active_pokemon is not None and
                      _active_pokemon.id == Hydrapple_ex and energy_count < 1):
                    score += 60
                else:
                    score -= 50
            elif pokemon.id == Meowth_ex:
                score -= 100
                if op_has_froslass:
                    score -= 50
            elif pokemon.id == Fezandipiti_ex:

                _fez_energy_req = 3
                _is_fez_attacker = (plan.attacker >= 1 and
                    my_state.bench[plan.attacker - 1] is not None and
                    my_state.bench[plan.attacker - 1].id == Fezandipiti_ex)
                if _is_fez_attacker and energy_count < _fez_energy_req:
                    score += 300
                elif energy_count < _fez_energy_req and not any(
                    p is not None and p.id in (Hydrapple_ex, Teal_Mask_Ogerpon_ex, Tapu_Bulu, Dipplin)
                    for p in my_state.bench + list(my_state.active or [])):

                    score += 200
                else:
                    score -= 100
                if op_has_froslass:
                    score -= 50
            elif pokemon.id == Pinsir:

                _pinsir_eff_bench = energy_count * _grass_mult()
                if op_has_ex_immune_active or op_has_ex_immune_bench:
                    if _pinsir_eff_bench < 2:
                        score += 350
                    else:
                        score -= 60
                elif _pinsir_eff_bench < 2:
                    score += 80
                else:
                    score -= 60
        return score

    _sel_active_cant_attack = False
    _sel_active_pkmn = my_state.active[0] if my_state.active else None
    if _sel_active_pkmn is not None:
        # Fuente unica de requisitos: ATTACK_ENERGY_REQ.
        _sel_req = ATTACK_ENERGY_REQ.get(_sel_active_pkmn.id)
        if _sel_req is not None:
            _sel_mult = _grass_mult()
            _sel_eff_now = len(_sel_active_pkmn.energies) * _sel_mult
            _sel_can_now = (_sel_eff_now >= _sel_req)
            _sel_can_attach = False
            if (not _sel_can_now and not state.energyAttached
                    and hand_counts.get(Basic_Grass_Energy, 0) >= 1):
                _sel_eff_after = len(_sel_active_pkmn.energies) + _grass_attach_unit()
                _sel_can_attach = (_sel_eff_after >= _sel_req)
            _sel_active_cant_attack = not (_sel_can_now or _sel_can_attach)
        elif _sel_active_pkmn.id == Meowth_ex:
            _sel_active_cant_attack = True

    _sel_ctx_card = getattr(select, 'contextCard', None)
    _meowth_skip_fetch = (
        context == SelectContext.ACTIVATE
        and _sel_ctx_card is not None and _sel_ctx_card.id == Meowth_ex
        and _meowth_devel_lillie
        and hand_counts.get(Lillie_Determination, 0) >= 1
        and not _win_via_boss_gust and not _gust_2prize_via_boss
    )

    # Cuando vamos por detras en premios y el unico gusteo de Boss's Orders es
    # un objetivo de bajo valor (basico/pre-evo de 1 premio, rank alto) que no
    # gana la partida ni toma 2 premios, es mejor desarrollar con Lillie's que
    # quemar el Boss's Orders por un premio menor.
    _boss_low_value_gust = (
        _boss_prize_rank >= 7
        and not _win_via_boss_gust
        and not _gust_2prize_via_boss
        and not _boss_win_via_bench
        and not _boss_dodge_redirect
        and my_prize > op_prize
        and hand_counts.get(Lillie_Determination, 0) >= 1
    )

    # --- Regla anti-2-premios vs Mega Lucario (Riolu activo rival) ---
    # Si en nuestro primer turno (yendo segundos) el rival tiene un Riolu activo
    # con energia, el proximo turno evolucionara a Mega Lucario ex y noqueara a
    # nuestro Ogerpon ex (2 premios). Para evitarlo, retiramos el Ogerpon ex y
    # promovemos un basico de 1 premio como sacrificio (prioridad Tapu Bulu >
    # Applin > Chikorita), entregando solo 1 premio de un Pokemon que no se
    # necesita.
    _lucario_sac_context = (
        state.turn == 2 and not we_go_first
        and op_state.active and op_state.active[0] is not None
        and op_state.active[0].id == Riolu
        and len(op_state.active[0].energies) >= 1
        and field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1
    )
    _lucario_sac_pivot = (
        _lucario_sac_context
        and my_state.active and my_state.active[0] is not None
        and my_state.active[0].id == Teal_Mask_Ogerpon_ex
    )
    _lucario_sac_available = (
        field_counts.get(Tapu_Bulu, 0) >= 1
        or field_counts.get(Applin, 0) >= 1
        or field_counts.get(Chikorita, 0) >= 1
        or (hand_counts.get(Tapu_Bulu, 0) >= 1 and bench_count < 5)
    )
    # Dentro del escenario anti-Lucario, Tapu Bulu SOLO es el sacrificio/objetivo
    # prioritario cuando de verdad aporta:
    #   * rival con proteccion a ex (Crustle / Cornerstone Ogerpon / Sylveon),
    #     donde nuestros ex hacen 0 dano, o
    #   * motor Hydrapple ex cargado + Meganium en juego, que permite bajar Tapu
    #     Bulu y cargarlo al instante (con Meganium 2 energias cuentan como 4 y
    #     puede atacar de inmediato).
    # En caso contrario preferimos gastar Applin > Chikorita y conservar Tapu Bulu.
    _lucario_hydra_engine = False
    if meganium_in_play and has_hydrapple:
        for _lhp in (my_state.active + my_state.bench):
            if (_lhp is not None and _lhp.id == Hydrapple_ex
                    and len(_lhp.energies) * _grass_mult() >= 2):
                _lucario_hydra_engine = True
                break
    _tapu_sac_priority = _lucario_sac_pivot and (
        op_is_crustle_deck or op_is_cornerstone_deck or op_is_sylveon_deck
        or op_has_ex_immune_active or op_has_ex_immune_bench
        or op_has_ability_immune_active or _lucario_hydra_engine)
    _lucario_other_sac_available = (
        field_counts.get(Applin, 0) >= 1 or field_counts.get(Chikorita, 0) >= 1
        or hand_counts.get(Applin, 0) >= 1 or hand_counts.get(Chikorita, 0) >= 1)

    # Al valorar descartes, conservar siempre al menos una Lillie's: la primera
    # copia evaluada recibe puntaje protector y solo las copias sobrantes son
    # libremente descartables.
    _lillie_protected_once = False

    # ------------------------------------------------------------------
    # Promocion tras KO: elegir SIEMPRE el mejor atacante de banca segun el
    # Pokemon ACTIVO rival (no segun que cartas tenga en el mazo). Para cada
    # candidato que pueda atacar este turno se estima su dano EFECTIVO contra
    # el activo rival, respetando:
    #   * Inmunidad a ex del activo (Crustle / Sylveon): nuestros ex hacen 0.
    #   * Inmunidad de habilidad del activo (Cornerstone Ogerpon ex): nuestros
    #     atacantes que dependen de habilidad hacen 0.
    #   * Debilidad del activo rival a nuestro tipo (x2).
    # El que mas dano hace se marca para promoverlo de forma decisiva:
    #   - Activo normal / Mega (p.ej. Mega Kangaskhan ex): sube el que pega mas
    #     fuerte (con banca cargada suele ser Hydrapple ex).
    #   - Crustle activo: descarta nuestros ex y sube el mejor no-ex.
    #   - Cornerstone activo: sube un atacante que no dependa de habilidad.
    _best_promote_card = None
    _forced_ko_promote = (
        (context == SelectContext.SWITCH or context == SelectContext.TO_ACTIVE)
        and not (my_state.active and my_state.active[0] is not None)
        and not _lucario_sac_context)
    if _forced_ko_promote:
        _op_prom_active = (op_state.active[0]
                           if op_state.active and op_state.active[0] is not None
                           else None)
        _op_prom_data = (card_table.get(_op_prom_active.id)
                         if _op_prom_active is not None else None)
        _op_prom_weak = getattr(_op_prom_data, 'weakness', None) if _op_prom_data else None
        _op_prom_en = len(_op_prom_active.energies) if _op_prom_active is not None else 0
        _op_prom_remain = (getattr(_op_prom_active, 'hp', 0)
                           if _op_prom_active is not None else 0)
        _prom_bench_after = max(0, bench_count - 1)
        _prom_can_attach = (
            hand_counts.get(Basic_Grass_Energy, 0) >= 1
            or (hand_counts.get(Night_Stretcher, 0) >= 1
                and discard_counts.get(Basic_Grass_Energy, 0) >= 1))
        _best_promote_dmg = -1
        _best_promote_key = None
        for _pb in my_state.bench:
            if _pb is None or not isinstance(_pb, Pokemon):
                continue
            _pb_req = ATTACK_ENERGY_REQ.get(_pb.id)
            if _pb_req is None:
                continue
            _pb_en_eff = len(_pb.energies)
            if _pb_en_eff < _pb_req and _prom_can_attach:
                _pb_en_eff += _grass_attach_unit()
            if _pb_en_eff < _pb_req:
                continue  # no puede atacar este turno
            if _pb.id == Hydrapple_ex:
                _pb_dmg = 30 + 30 * total_grass
            elif _pb.id == Teal_Mask_Ogerpon_ex:
                _pb_dmg = 30 + 30 * len(_pb.energies)
            elif _pb.id == Dipplin:
                _pb_dmg = 20 * _prom_bench_after
            elif _pb.id == Tapu_Bulu:
                _pb_dmg = 220
            elif _pb.id == Meganium:
                _pb_dmg = 140
            elif _pb.id == Fezandipiti_ex:
                _pb_dmg = 100
            else:
                _pb_dmg = 10
            # Inmunidad a ex del activo rival (Crustle / Sylveon): ex -> 0.
            if op_has_ex_immune_active and _pb.id in OUR_EX_IDS:
                _pb_dmg = 0
            # Inmunidad de habilidad del activo rival (Cornerstone): los
            # atacantes que dependen de habilidad quedan bloqueados -> 0.
            if op_has_ability_immune_active and _pb.id in OUR_ABILITY_IDS:
                _pb_dmg = 0
            # Debilidad del activo rival a nuestro tipo -> x2.
            _pb_data = card_table.get(_pb.id)
            if (_pb_data is not None and _op_prom_weak is not None
                    and getattr(_pb_data, 'energyType', None) == _op_prom_weak):
                _pb_dmg *= 2
            if _pb_dmg <= 0:
                continue  # inmune / sin ataque util: no puede derrotar al rival
            # Regla: subir SIEMPRE el de MAS VIDA que pueda derrotar al rival.
            # Prioridad lexicografica: (puede noquear, vida restante, dano).
            _pb_can_ko = 1 if (_op_prom_remain > 0 and _pb_dmg >= _op_prom_remain) else 0
            _pb_hp = getattr(_pb, 'hp', 0) or 0
            _pb_key = (_pb_can_ko, _pb_hp, _pb_dmg)
            if _best_promote_key is None or _pb_key > _best_promote_key:
                _best_promote_key = _pb_key
                _best_promote_dmg = _pb_dmg
                _best_promote_card = _pb
        if _best_promote_card is None or _best_promote_dmg <= 0:
            _best_promote_card = None

        # Regla (user, registro 007 paso 90 vs Alakazam, GANADA): al promover tras
        # un KO, si en la banca hay un Tapu Bulu que puede ATACAR este turno (>=4
        # energia efectiva, o le falta y la tenemos en mano / recuperable con Night
        # Stretcher) y con su ataque de 220 NOQUEA al activo rival, subirlo SIEMPRE
        # -aunque un ex de banca (Ogerpon/Hydrapple ex) tenga mas vida o pegue algo
        # mas fuerte-. Tapu Bulu es no-ex (solo 1 premio si lo noquean) y remata
        # igual que un ex de 2 premios: exponer el cuerpo barato es lo correcto.
        # Complementa [[tapu-bulu-activo-que-noquea-ataca-no-retira]] (que decide no
        # retirar un Tapu Bulu que noquea); esta decide a QUIEN promover.
        if _op_prom_remain > 0:
            _tapu_prom = None
            for _tb in my_state.bench:
                if _tb is None or not isinstance(_tb, Pokemon) or _tb.id != Tapu_Bulu:
                    continue
                _tb_req = ATTACK_ENERGY_REQ.get(Tapu_Bulu, 4)
                _tb_eff = len(_tb.energies)
                if _tb_eff < _tb_req and _prom_can_attach:
                    _tb_eff += _grass_attach_unit()
                if _tb_eff < _tb_req:
                    continue
                _tb_dmg = 220
                _tb_data = card_table.get(Tapu_Bulu)
                if (_tb_data is not None and _op_prom_weak is not None
                        and getattr(_tb_data, 'energyType', None) == _op_prom_weak):
                    _tb_dmg *= 2
                if _tb_dmg >= _op_prom_remain:
                    _tapu_prom = _tb
                    break
            if _tapu_prom is not None:
                _best_promote_card = _tapu_prom

        # Regla (user, registro_010 paso 127, vs Alakazam, PERDIDA): al PROMOVER
        # (retiro voluntario o KO) contra un mazo de Alakazam, preferir SIEMPRE un
        # cuerpo de UN premio (Meganium o Tapu Bulu) que NOQUEE al activo rival
        # sobre un ex de 2 premios, aunque el ex tenga MAS vida. Extiende la regla
        # universal de Tapu Bulu (arriba) para incluir a Meganium en este matchup:
        # si nos noquean el atacante solo cedemos 1 premio en vez de 2. Entre
        # varios candidatos de 1 premio se sube el de MAS vida.
        if op_is_alakazam_deck and _op_prom_remain > 0:
            _ak_1prize_prom = None
            _ak_1prize_hp = -1
            for _mb in my_state.bench:
                if _mb is None or not isinstance(_mb, Pokemon):
                    continue
                if _mb.id not in (Meganium, Tapu_Bulu):
                    continue
                _mb_req = ATTACK_ENERGY_REQ.get(_mb.id)
                if _mb_req is None:
                    continue
                _mb_eff = len(_mb.energies)
                if _mb_eff < _mb_req and _prom_can_attach:
                    _mb_eff += _grass_attach_unit()
                if _mb_eff < _mb_req:
                    continue
                _mb_dmg = 220 if _mb.id == Tapu_Bulu else 140
                _mb_data = card_table.get(_mb.id)
                if (_mb_data is not None and _op_prom_weak is not None
                        and getattr(_mb_data, 'energyType', None) == _op_prom_weak):
                    _mb_dmg *= 2
                if _mb_dmg < _op_prom_remain:
                    continue
                _mb_hp = getattr(_mb, 'hp', 0) or 0
                if _mb_hp > _ak_1prize_hp:
                    _ak_1prize_hp = _mb_hp
                    _ak_1prize_prom = _mb
            if _ak_1prize_prom is not None:
                _best_promote_card = _ak_1prize_prom

    # Regla (user) vs Mega Lucario: cuando el rival nos NOQUEA un Pokemon y en
    # la banca NO hay NINGUN atacante capaz de atacar este turno
    # (`_best_promote_card is None`), preferimos SIEMPRE promover primero un
    # Pokemon BASICO (Applin es la prioridad entre los basicos), o Dipplin si no
    # tenemos ningun basico. Asi entregamos un cuerpo barato (1 premio) en vez de
    # un ex (2 premios) que igual no puede contraatacar. Si no hay basico ni
    # Dipplin en la banca, se conserva la logica actual de promocion.
    _lucario_ko_prefer_basic = (
        _forced_ko_promote
        and op_is_lucario_deck
        and _best_promote_card is None)
    # ------------------------------------------------------------------

    # Regla (user, log 86345562 p55): al PROMOVER (retiro o KO) cuando NINGUN
    # cuerpo de la banca puede atacar este turno y tenemos Lillie's Determination
    # en mano para refrescar la mano, preferimos subir un BASICO de 1 premio
    # (Applin es la prioridad) en vez de un ex de 2 premios (Meowth ex / Ogerpon
    # ex). Asi entregamos solo 1 premio como muro mientras rehacemos la mano con
    # Lillie's y conservamos los ex -y su energia ya cargada- a salvo en la banca
    # para atacar mas tarde. Solo aplica si el activo rival NO es inmune a ex ni
    # a habilidad (esos matchups ya suben un ex-muro con su propia logica).
    _ref_grass_attachable = (
        hand_counts.get(Basic_Grass_Energy, 0) >= 1
        or (hand_counts.get(Night_Stretcher, 0) >= 1
            and discard_counts.get(Basic_Grass_Energy, 0) >= 1))
    _ref_forced_promote = not (my_state.active and my_state.active[0] is not None)
    _ref_can_attach = _ref_grass_attachable and (
        not state.energyAttached or _ref_forced_promote)
    _refresh_no_attacker = True
    for _rbp in my_state.bench:
        if _rbp is None or not isinstance(_rbp, Pokemon):
            continue
        if _rbp.id not in MAIN_ATTACKERS:
            continue
        _rbp_e = len(_rbp.energies)
        if _can_attack_eff(_rbp.id, _rbp_e) or (
                _ref_can_attach
                and _can_attack_eff(_rbp.id, _rbp_e + _grass_attach_unit())):
            _refresh_no_attacker = False
            break
    _refresh_promote_prefer_basic = (
        (context == SelectContext.SWITCH or context == SelectContext.TO_ACTIVE)
        and not _lucario_sac_context
        and not _lucario_ko_prefer_basic
        and hand_counts.get(Lillie_Determination, 0) >= 1
        and not op_has_ex_immune_active
        and not op_has_ability_immune_active
        and _refresh_no_attacker)
    # ------------------------------------------------------------------

    # --- Matchup Crustle + Mega Kangaskhan ex: reparto de atacantes (user) ---
    # Contra este mazo hay que atacar al Mega Kangaskhan ex (u otro objetivo NO
    # inmune a ex) con NUESTRO ex, y RESERVAR los no-ex -sobre todo Tapu Bulu,
    # que noquea a Crustle de un solo ataque- para cuando Crustle este activo.
    # Si el activo rival es Crustle (inmune a ex) se sube un no-ex; si no hay
    # ningun ex nuestro capaz de atacar, se usa un basico igualmente.
    _cm_matchup = op_is_crustle_deck and op_has_mega_kangaskhan
    _cm_have_ex_attacker = False
    _cm_vs_ex_target = (_cm_matchup and not op_has_ex_immune_active
                        and op_state.active and op_state.active[0] is not None)
    if _cm_vs_ex_target:
        for _cmp in my_state.bench:
            if _cmp is None or not isinstance(_cmp, Pokemon):
                continue
            if _cmp.id in (Teal_Mask_Ogerpon_ex, Hydrapple_ex):
                _cm_req = ATTACK_ENERGY_REQ.get(_cmp.id)
                if _cm_req is None:
                    continue
                _cm_e = len(_cmp.energies)
                if (_cm_e < _cm_req and not state.energyAttached
                        and hand_counts.get(Basic_Grass_Energy, 0) >= 1):
                    _cm_e += _grass_attach_unit()
                if _cm_e >= _cm_req:
                    _cm_have_ex_attacker = True
                    break
    # Solo repartimos (reservar Tapu Bulu / priorizar ex) cuando el activo rival
    # NO es inmune a ex y tenemos un ex capaz de atacarlo este turno.
    _cm_use_ex = _cm_vs_ex_target and _cm_have_ex_attacker

    # Contexto de decision (refactor Prioridad 1): entradas invariantes que
    # consumen los scorers extraidos `_score_*`. Se construye una sola vez.
    ctx = DecisionContext(
        state=state,
        my_state=my_state,
        op_state=op_state,
        hand_counts=hand_counts,
        field_counts=field_counts,
        supp_values=_supp_values,
        cartas_en_mazo=CARTAS_ACTIVAS_EN_MAZO,
        field_at_turn_start=_field_at_turn_start,
        bench_count=bench_count,
        my_hand_len=len(my_state.hand or []),
        my_prize=my_prize,
        op_prize=op_prize,
        op_hand_count=getattr(op_state, 'handCount', 0),
        meganium_in_play=meganium_in_play,
        forest_in_play=forest_in_play,
        itchy_pollen_active=itchy_pollen_active,
        has_hydrapple=has_hydrapple,
        watchtower_in_play=watchtower_in_play,
        neutralization_zone_active=neutralization_zone_active,
        mega_line_active=_mega_line_active,
        active_needs_energy=_active_needs_energy,
        evolve_possible_in_play=_evolve_possible_in_play,
        energy_starved_low_draw=_energy_starved_low_draw,
        pp_playable_in_hand=_pp_playable_in_hand,
        can_attack=can_attack,
        best_supp_in_hand_val=_best_supp_in_hand_val,
        best_supp_in_mazo_val=_best_supp_in_mazo_val,
        op_is_alakazam_deck=op_is_alakazam_deck,
        op_is_hop_deck=op_is_hop_deck,
        op_is_comfey_deck=op_is_comfey_deck,
        op_active_is_dunsparce=op_active_is_dunsparce,
        op_has_ability_immune_active=op_has_ability_immune_active,
        op_has_ex_immune_active=op_has_ex_immune_active,
        op_has_ex_immune_bench=op_has_ex_immune_bench,
        op_is_control_deck=op_is_control_deck,
        op_is_slowking_deck=op_is_slowking_deck,
        op_is_gardevoir_deck=op_is_gardevoir_deck,
        op_is_zoroark_deck=op_is_zoroark_deck,
        op_is_aggro_deck=op_is_aggro_deck,
        op_is_beedrill_deck=op_is_beedrill_deck,
        op_is_crustle_deck=op_is_crustle_deck,
        op_is_cornerstone_deck=op_is_cornerstone_deck,
        op_is_fire_deck=op_is_fire_deck,
        op_is_mirror=op_is_mirror,
        op_kang_ko_target=op_kang_ko_target,
        stadium_id=stadium_id,
        ko_last_turn=ko_last_turn,
        our_first_turn=_our_first_turn,
        active_cant_attack=_active_cant_attack_this_turn,
        bdg_retreat_ko=_bdg_retreat_ko,
        supporter_boost=(500 if itchy_pollen_active else 0),
        we_go_first=we_go_first,
        budew_op_index=budew_op_index,
        budew_on_op_field=budew_on_op_field,
        lucario_sac_pivot=_lucario_sac_pivot,
        win_via_boss_gust=_win_via_boss_gust,
        gust_2prize_via_boss=_gust_2prize_via_boss,
        boss_win_via_bench=_boss_win_via_bench,
        boss_dodge_redirect=_boss_dodge_redirect,
        boss_defensive_gust=_boss_defensive_gust,
        boss_deny_alakazam_line=_boss_deny_alakazam_line,
        boss_low_value_gust=_boss_low_value_gust,
        boss_prize_rank=_boss_prize_rank,
    )

    # Teal Dance PRECEDE al adjunte manual (user, registro_004 paso 28, vs
    # Mega Starmie): si un Teal Mask Ogerpon ex TODAVIA tiene su habilidad Teal
    # Dance disponible este turno (aparece una opcion ABILITY para ese mismo
    # Ogerpon), no se debe cargar energia MANUALMENTE sobre el. Teal Dance
    # adjunta una Planta Y ademas ROBA una carta, asi que tiene prioridad: el
    # adjunte manual se pospone hasta que la habilidad se haya usado. Aqui
    # recopilamos las posiciones (area, index) de los Ogerpon que aun pueden
    # usar Teal Dance para vetar en la rama ATTACH el adjunte manual a ese slot.
    _teal_dance_slots = set()
    if context == SelectContext.MAIN:
        for _tds_o in select.option:
            if _tds_o.type == OptionType.ABILITY:
                _tds_card = get_card(obs, _tds_o.area, _tds_o.index, my_index)
                if _tds_card is not None and _tds_card.id == Teal_Mask_Ogerpon_ex:
                    _teal_dance_slots.add((_tds_o.area, _tds_o.index))

    # Pivote vs Alakazam (user, registro_010 paso 127, PERDIDA): contra un mazo de
    # Alakazam preferimos atacar con cuerpos de UN premio (Meganium, Tapu Bulu) en
    # vez de con un ex (2 premios). Si el ACTIVO es un ex NUESTRO que va a atacar,
    # pero hay en banca un atacante NO-ex de 1 premio (Meganium/Tapu Bulu) LISTO
    # que NOQUEA al activo rival, y el ex activo puede pagar su coste de retirada,
    # RETIRAMOS el ex y promovemos al cuerpo de 1 premio para atacar: si luego nos
    # lo noquean cedemos 1 premio en vez de 2. NO aplica si atacar con el ex GANA
    # la partida (entonces se ataca y punto). La promocion posterior elige el
    # cuerpo de 1 premio via `_best_promote_card` (rama vs Alakazam de arriba).
    _alakazam_pivot_1prize = False
    if (context == SelectContext.MAIN and op_is_alakazam_deck
            and can_attack and my_state.active and my_state.active[0] is not None):
        _akp_act = my_state.active[0]
        _akp_op = op_state.active[0] if op_state.active else None
        if (_akp_act.id in OUR_EX_IDS and _akp_op is not None
                and not op_has_ex_immune_active):
            _akp_op_hp = _akp_op.hp or 0
            _akp_rc = RETREAT_COST.get(_akp_act.id, 1)
            _akp_can_retreat = len(_akp_act.energies) >= _akp_rc
            _akp_bench_ko_1prize = False
            for _akp_bp in (my_state.bench or []):
                if _akp_bp is None or _akp_bp.id not in (Meganium, Tapu_Bulu):
                    continue
                _akp_be = len(_akp_bp.energies)
                if not _can_attack_eff(_akp_bp.id, _akp_be):
                    continue
                _akp_base = _attacker_base_damage(
                    _akp_bp.id, _akp_op, _akp_be * _grass_mult(),
                    grass_scale=0, teal_self_energy=_akp_be, bench_count=bench_count)
                if _akp_base <= 0:
                    continue
                if _our_effective_damage(_akp_bp, _akp_op, _akp_base,
                                         meganium_in_play,
                                         neutralization_zone_active) >= _akp_op_hp:
                    _akp_bench_ko_1prize = True
                    break
            _akp_prizes_from_ko = prize_count(_akp_op)
            _akp_my_left = len([p for p in (my_state.prize or []) if p is None])
            _akp_win_now = _akp_my_left <= _akp_prizes_from_ko
            if _akp_can_retreat and _akp_bench_ko_1prize and not _akp_win_now:
                _alakazam_pivot_1prize = True

    scores = []
    for o in select.option:
        score = 0

        if o.type == OptionType.NUMBER:
            score = o.number

        elif o.type == OptionType.YES:
            score = 1
            if context == SelectContext.ACTIVATE:

                score = 10
                if _meowth_skip_fetch:
                    score = -1
            elif context == SelectContext.IS_FIRST:

                score = -1
                we_go_first = True
            elif context == SelectContext.COIN_HEAD:

                score = 2

        elif o.type == OptionType.NO:
            if context == SelectContext.IS_FIRST:
                score = 2
                we_go_first = False
            elif context == SelectContext.ACTIVATE and _meowth_skip_fetch:
                score = 10

        elif o.type == OptionType.CARD:
            card = get_card(obs, o.area, o.index, o.playerIndex)
            if card is not None:
                energy_count = 0
                if isinstance(card, Pokemon):
                    energy_count = len(card.energies)

                if context == SelectContext.SWITCH or context == SelectContext.TO_ACTIVE:
                    if o.playerIndex == my_index and _lucario_sac_context:
                        # Promover un sacrificio de 1 premio en vez del Ogerpon ex,
                        # para entregar solo 1 premio a Mega Lucario (no 2). Por
                        # defecto conservamos Tapu Bulu y sacrificamos antes
                        # Applin > Chikorita; solo cuando Tapu Bulu es realmente
                        # prioritario (rival con proteccion a ex o motor Hydrapple
                        # ex + Meganium) se sacrifica Tapu Bulu primero.
                        if _tapu_sac_priority:
                            if card.id == Tapu_Bulu:
                                score = 6000
                            elif card.id == Applin:
                                score = 5500
                            elif card.id == Chikorita:
                                score = 5000
                            else:
                                score = 100
                        else:
                            if card.id == Applin:
                                score = 6000
                            elif card.id == Chikorita:
                                score = 5500
                            elif card.id == Tapu_Bulu:
                                score = 200
                            else:
                                score = 100
                    elif o.playerIndex == my_index:

                        # Listo-para-atacar via energia efectiva (fuente unica:
                        # ATTACK_ENERGY_REQ). Ahora incluye Pinsir (antes omitido).
                        _can_attack_now = (
                            card.id in MAIN_ATTACKERS
                            and _can_attack_eff(card.id, energy_count))

                        _ns_grass_recover_switch = (
                            hand_counts.get(Night_Stretcher, 0) >= 1 and
                            discard_counts.get(Basic_Grass_Energy, 0) >= 1)
                        _grass_attachable_switch = (
                            hand_counts.get(Basic_Grass_Energy, 0) >= 1 or
                            _ns_grass_recover_switch)
                        _forced_promote_switch = not my_state.active
                        _can_attack_with_attach = _can_attack_now
                        if (not _can_attack_now and _grass_attachable_switch
                                and (not state.energyAttached or _forced_promote_switch)):
                            _pkmn_eff_plus1 = energy_count + _grass_attach_unit()
                            if card.id == Hydrapple_ex:
                                _can_attack_with_attach = (_pkmn_eff_plus1 >= 2)
                            elif card.id == Dipplin:
                                _can_attack_with_attach = True
                            elif card.id == Teal_Mask_Ogerpon_ex:
                                _can_attack_with_attach = (_pkmn_eff_plus1 >= 3)
                            elif card.id == Tapu_Bulu:
                                _can_attack_with_attach = (_pkmn_eff_plus1 >= 4)
                            elif card.id == Fezandipiti_ex:
                                _can_attack_with_attach = (_pkmn_eff_plus1 >= 3)
                            elif card.id == Meganium:
                                _can_attack_with_attach = (_pkmn_eff_plus1 >= 4)

                        if _can_attack_now:
                            score = 500
                        elif _can_attack_with_attach:
                            score = 350
                        else:
                            score = 100

                        if card.hp is not None:
                            score += card.hp // 10

                        score += energy_count

                        # Negacion de premios al promover (user): si al rival le
                        # faltan <=2 premios para ganar, preferir DECISIVAMENTE
                        # subir un cuerpo de 1 premio que YA pueda atacar antes que
                        # un ex (2 premios), para que un KO rival no cierre la
                        # partida. Solo BONIFICA a los no-ex atacantes (nunca
                        # penaliza al ex): si el unico cuerpo capaz de atacar es un
                        # ex, se sigue promoviendo con normalidad.
                        if (op_prize <= 2 and _can_attack_now
                                and prize_count(card) <= 1):
                            score += 3000

                        # Al retirar un activo CONFUNDIDO, priorizar subir a un
                        # atacante del matchup que YA pueda atacar (p.ej. Dipplin
                        # vs Crustle) por encima de un muro que no ataca este
                        # turno (p.ej. un ex al que Crustle es inmune). Evita
                        # subir al Pokemon equivocado tras curar la confusion.
                        if (is_confused and _can_attack_now
                                and _conf_is_matchup_attacker(card.id)):
                            score += 2000

                        if not _can_attack_now and not _can_attack_with_attach:
                            if card.hp is not None:

                                score += card.hp // 5

                                if estimated_op_damage > 0 and card.hp > estimated_op_damage:
                                    score += 80
                                elif estimated_op_damage > 0 and card.hp <= estimated_op_damage:
                                    score -= 20

                        if _teal_wall_pivot and card.id == Hydrapple_ex:
                            # Pivote defensivo con Teal Dance: subir al cuerpo mas
                            # fuerte (Hydrapple ex, muro de 330) aunque no pueda
                            # atacar aun. Bono decisivo para elegirlo al promover.
                            score += 4000

                        if card.id == Hydrapple_ex:
                            score += 60
                            if _can_attack_now:

                                _syrup_dmg = 30 + 30 * total_grass
                                score += min(_syrup_dmg // 10, 30)
                            elif _can_attack_with_attach:

                                score += 250
                            if _cm_use_ex and (_can_attack_now or _can_attack_with_attach):
                                # Matchup Crustle + Mega Kangaskhan ex: subir
                                # NUESTRO ex para atacar al Mega y conservar los
                                # no-ex para Crustle.
                                score += 500
                        elif card.id == Tapu_Bulu:
                            if _can_attack_now:
                                score += 50
                            if _cm_use_ex:
                                # Reservar Tapu Bulu para Crustle (lo noquea de un
                                # golpe): NO subirlo contra el Mega Kangaskhan ex,
                                # que atacamos con nuestros ex.
                                score -= 500
                            elif op_has_ex_immune_active or op_is_crustle_deck:
                                score += 80
                            if op_is_cornerstone_deck:

                                score += 120
                        elif card.id == Teal_Mask_Ogerpon_ex:
                            score += 30
                            if _cm_use_ex and (_can_attack_now or _can_attack_with_attach):
                                # Subir NUESTRO ex para atacar al Mega Kangaskhan
                                # ex y conservar los no-ex (Tapu Bulu) para Crustle.
                                score += 500
                        elif card.id == Dipplin:
                            score += 15
                            if op_has_ex_immune_active:
                                score += 40

                            if (op_is_crustle_deck and state.retreated and
                                    energy_count == 0 and
                                    hand_counts.get(Night_Stretcher, 0) >= 1 and
                                    hand_counts.get(Basic_Grass_Energy, 0) == 0 and
                                    discard_counts.get(Basic_Grass_Energy, 0) >= 1):
                                score += 5000
                        elif card.id == Meganium:
                            if (op_has_ex_immune_active or op_is_crustle_deck) and _can_attack_now:

                                score += 120
                            else:
                                score -= 80
                        elif card.id == Meowth_ex:
                            score -= 100
                        elif card.id == Fezandipiti_ex:
                            score -= 100
                        elif card.id == Chikorita:
                            score -= 60
                        elif card.id == Bayleef:
                            score -= 50
                        elif card.id == Applin:
                            score -= 70

                        # Regla (user, log 86607718 turno 2, vs Crustle): al
                        # PROMOVER (p.ej. tras retirar un Chikorita activo) cuando
                        # NINGUN cuerpo puede atacar al muro este turno, subir un EX
                        # tanque como muro desechable -- primer candidato Teal Mask
                        # Ogerpon ex (210 HP) -- y RESERVAR a Tapu Bulu en la banca
                        # (nuestro atacante clave que noquea a Crustle) para cargarlo
                        # a salvo. Solo cuando NADIE ataca: si Tapu ya puede atacar,
                        # su +80 vs Crustle sigue mandando. No aplica al reparto
                        # Crustle + Mega Kangaskhan ex (_cm_use_ex).
                        if (op_is_crustle_deck and not _cm_use_ex
                                and not _can_attack_now
                                and not _can_attack_with_attach):
                            if card.id == Teal_Mask_Ogerpon_ex:
                                score += 300
                            elif card.id == Tapu_Bulu:
                                score -= 300

                        _op_act_wsel = op_state.active[0] if op_state.active else None
                        if _op_act_wsel is not None and isinstance(card, Pokemon):
                            _op_act_wsel_data = card_table.get(_op_act_wsel.id)
                            _card_wsel_data = card_table.get(card.id)
                            if (_card_wsel_data is not None and getattr(_card_wsel_data, 'weakness', None) is not None and
                                    _op_act_wsel_data is not None and
                                    getattr(_op_act_wsel_data, 'energyType', None) == _card_wsel_data.weakness):
                                score -= 250

                            _op_dmg_vs_card = max(_op_best_damage_vs(card),
                                                  _op_counter_threat_vs(card))
                            if _op_dmg_vs_card > 0:
                                if _op_dmg_vs_card >= card.hp:
                                    score -= SCORE_LOOKAHEAD_PROMOTE_KO
                                elif _op_dmg_vs_card <= card.hp * 0.4:
                                    score += SCORE_LOOKAHEAD_PROMOTE_SAFE

                        _forest_available = (forest_in_play or
                                             hand_counts.get(Forest_of_Vitality, 0) >= 1)

                        if card.id == Applin and _forest_available:

                            _has_dipplin_hand = (hand_counts.get(Dipplin, 0) >= 1)
                            _has_hydrapple_hand = (hand_counts.get(Hydrapple_ex, 0) >= 1)
                            _has_energy_hand = (hand_counts.get(Basic_Grass_Energy, 0) >= 1 and
                                                not state.energyAttached)
                            if _has_dipplin_hand and _has_hydrapple_hand:

                                _evo_bonus = 600
                                if _has_energy_hand:
                                    _evo_bonus += 150

                                _bench_grass_energy = 0
                                for _bp in my_state.bench:
                                    if _bp is not None and _bp.id != card.id:
                                        _bench_grass_energy += len(_bp.energies)
                                if _bench_grass_energy >= 1:
                                    _evo_bonus += 100

                                _mega_evolvable = (meganium_in_play or
                                    (hand_counts.get(Meganium, 0) >= 1 and
                                     (field_counts.get(Bayleef, 0) >= 1 or
                                      (field_counts.get(Chikorita, 0) >= 1 and
                                       hand_counts.get(Bayleef, 0) >= 1 and _forest_available))))
                                if _mega_evolvable:
                                    _evo_bonus += 100
                                score += _evo_bonus
                            elif _has_dipplin_hand:

                                _evo_bonus = 300
                                if _has_energy_hand:
                                    _evo_bonus += 100
                                if op_has_ex_immune_active:
                                    _evo_bonus += 150
                                score += _evo_bonus

                        elif card.id == Chikorita and _forest_available:

                            _has_bayleef_hand = (hand_counts.get(Bayleef, 0) >= 1)
                            _has_meganium_hand = (hand_counts.get(Meganium, 0) >= 1)
                            if _has_bayleef_hand and _has_meganium_hand and not meganium_in_play:

                                pass
                            elif _has_bayleef_hand and not meganium_in_play:

                                pass

                        elif card.id == Dipplin and not has_hydrapple:

                            if hand_counts.get(Hydrapple_ex, 0) >= 1 and _forest_available:
                                _evo_bonus = 500
                                _has_energy_hand = (hand_counts.get(Basic_Grass_Energy, 0) >= 1 and
                                                    not state.energyAttached)
                                if _has_energy_hand:
                                    _evo_bonus += 150
                                _bench_grass_energy = 0
                                for _bp in my_state.bench:
                                    if _bp is not None and _bp.id != card.id:
                                        _bench_grass_energy += len(_bp.energies)
                                if _bench_grass_energy >= 1:
                                    _evo_bonus += 100
                                score += _evo_bonus
                            elif hand_counts.get(Hydrapple_ex, 0) >= 1:

                                pass

                        elif card.id == Bayleef and not meganium_in_play:

                            if hand_counts.get(Meganium, 0) >= 1 and _forest_available:

                                _has_bench_attacker = any(
                                    bp is not None and bp.id in (Hydrapple_ex, Dipplin,
                                        Teal_Mask_Ogerpon_ex, Tapu_Bulu)
                                    for bp in my_state.bench)
                                if _has_bench_attacker:

                                    pass

                        if card.id in (Chikorita, Bayleef, Meganium):
                            _meg_designated_attacker = False
                            if (card.id == Meganium and len(card.energies) >= 4 and
                                    (op_is_crustle_deck or op_is_cornerstone_deck)):
                                _meg_other_atk_p = any(
                                    bp is not None and (
                                        (bp.id == Dipplin and len(bp.energies) >= 1) or
                                        (bp.id == Tapu_Bulu and len(bp.energies) >= 4) or
                                        (bp.id == Pinsir and len(bp.energies) >= 2))
                                    for bp in my_state.bench)
                                if not _meg_other_atk_p:
                                    _meg_designated_attacker = True
                            # vs Alakazam (user, registro_010 paso 127): un
                            # Meganium (1 premio) LISTO para atacar es un atacante
                            # DESIGNADO -- lo preferimos como activo antes que un ex
                            # de 2 premios, aunque haya otros atacantes de banca. Sin
                            # esto el veto de "Meganium activo" (-10000) impedia
                            # promoverlo tras retirar el ex (_alakazam_pivot_1prize).
                            elif (card.id == Meganium and op_is_alakazam_deck
                                    and _can_attack_now):
                                _meg_designated_attacker = True
                            if _meg_designated_attacker:
                                score += 400
                            elif bench_count > 1:
                                score = -10000

                        if op_has_ex_immune_active and card.id not in OUR_EX_IDS:
                            score += 150
                        elif op_has_ex_immune_active and card.id in OUR_EX_IDS:
                            score -= 80

                        if op_has_ability_immune_active and card.id not in OUR_ABILITY_IDS:
                            score += 180
                        elif op_has_ability_immune_active and card.id in OUR_ABILITY_IDS:
                            score -= 100

                        if op_is_fire_deck and card.id == Hydrapple_ex and _can_attack_now:
                            score += 40

                        if op_is_control_deck and card.id == Tapu_Bulu and _can_attack_now:
                            score += 50

                        _op_is_drednaw_active = (op_state.active and op_state.active[0] is not None
                                                 and op_state.active[0].id == Drednaw)
                        if _op_is_drednaw_active:
                            if card.id == Meganium and _can_attack_now:
                                score += 250
                            elif card.id == Meganium and _can_attack_with_attach:
                                score += 200
                            elif card.id == Dipplin and _can_attack_now:
                                score += 180
                            elif card.id == Dipplin and _can_attack_with_attach:
                                score += 150
                            elif card.id == Hydrapple_ex:
                                score -= 150
                            elif card.id == Tapu_Bulu:
                                score -= 150

                        _op_is_sylveon_active = (op_state.active and op_state.active[0] is not None
                                                 and op_state.active[0].id == Sylveon)
                        if _op_is_sylveon_active:
                            if card.id == Tapu_Bulu and _can_attack_now:
                                score += 280
                            elif card.id == Meganium and _can_attack_now:
                                score += 260
                            elif card.id == Tapu_Bulu and _can_attack_with_attach:
                                score += 220
                            elif card.id == Meganium and _can_attack_with_attach:
                                score += 200
                            elif card.id == Dipplin and _can_attack_now:
                                score += 180
                            elif card.id == Dipplin and _can_attack_with_attach:
                                score += 150
                            elif card.id in OUR_EX_IDS:
                                score -= 200

                        if neutralization_zone_active:

                            _op_act_nz = op_state.active[0] if op_state.active else None
                            _op_act_nz_rb = False
                            if _op_act_nz is not None:
                                _op_act_nz_data = card_table[_op_act_nz.id]
                                _op_act_nz_rb = (_op_act_nz_data.ex or _op_act_nz_data.megaEx)
                            if not _op_act_nz_rb:

                                if card.id == Tapu_Bulu and _can_attack_now:
                                    score += 250
                                elif card.id == Meganium and _can_attack_now:
                                    score += 220
                                elif card.id == Tapu_Bulu and _can_attack_with_attach:
                                    score += 200
                                elif card.id == Meganium and _can_attack_with_attach:
                                    score += 180
                                elif card.id == Dipplin and _can_attack_now:
                                    score += 160
                                elif card.id == Dipplin and _can_attack_with_attach:
                                    score += 140
                                elif card.id in OUR_EX_IDS:
                                    score -= 200

                        if o.index == plan.attacker - 1:
                            score += 120

                        if card.id == Dipplin and hand_counts.get(Hydrapple_ex, 0) >= 1:
                            score += 80
                        elif card.id == Bayleef and hand_counts.get(Meganium, 0) >= 1:
                            score -= 30
                        elif card.id == Applin and hand_counts.get(Dipplin, 0) >= 1:
                            if forest_in_play and hand_counts.get(Hydrapple_ex, 0) >= 1:
                                score += 60
                            else:
                                score += 20
                        elif card.id == Chikorita and hand_counts.get(Bayleef, 0) >= 1:
                            if forest_in_play and hand_counts.get(Meganium, 0) >= 1:
                                score -= 30
                            else:
                                score += 5

                        if has_condition:
                            score += 50

                        # --- Promocion vs activo INMUNE a ex (Crustle) -------
                        # Solo cuando el Pokemon inmune esta ACTIVO (no basta
                        # con que este en banca): Crustle activo anula el dano de
                        # NUESTROS ex, por lo que un ex no ataca pero sirve de
                        # MURO. Regla: subir un atacante no-ex que SI dane a
                        # Crustle si puede atacar; si ninguno puede, subir un ex
                        # como muro (con energia primero; si ninguno tiene
                        # energia, primero Teal Mask Ogerpon ex).
                        if op_has_ex_immune_active:
                            _crus_is_our_ex = card.id in OUR_EX_IDS
                            _crus_nonex_attacker = (_can_attack_now
                                                    and not _crus_is_our_ex)
                            if _crus_nonex_attacker:
                                # Atacante no-ex que SI dana a Crustle: prioridad maxima.
                                score += 6000
                            elif _crus_is_our_ex:
                                # Muro ex: con energia primero; si no, Teal Mask primero.
                                if energy_count >= 1:
                                    score += 3000 + energy_count * 10
                                elif card.id == Teal_Mask_Ogerpon_ex:
                                    score += 2500
                                else:
                                    score += 2000

                        # Bono decisivo al mejor atacante contra el ACTIVO rival
                        # (calculado antes del bucle segun dano efectivo). Vale
                        # para cualquier activo: Mega/normal -> el que pega mas
                        # fuerte (Hydrapple ex); Crustle/Cornerstone -> el mejor
                        # no-ex / no-habilidad.
                        if _best_promote_card is not None and card is _best_promote_card:
                            score += 4000

                        # Regla (user) vs Mega Lucario sin atacante en banca:
                        # promover primero un BASICO (Applin prioritario) o, si no
                        # hay basico, Dipplin. El resto de cuerpos (ex, Fases 1/2
                        # que no sean Dipplin) conservan su score actual, asi que
                        # si no hay basico ni Dipplin sigue la logica normal.
                        if _lucario_ko_prefer_basic:
                            _luc_prom_data = card_table.get(card.id)
                            _luc_is_basic = (
                                _luc_prom_data is not None
                                and not getattr(_luc_prom_data, 'stage1', False)
                                and not getattr(_luc_prom_data, 'stage2', False))
                            if card.id == Applin:
                                score = 9000
                            elif _luc_is_basic:
                                score = 8500
                            elif card.id == Dipplin:
                                score = 8000

                        # Regla (user, log 86345562 p55): preferir subir un
                        # BASICO de 1 premio (Applin) en vez de un ex de 2 premios
                        # cuando ningun cuerpo puede atacar y tenemos Lillie's para
                        # refrescar. Conserva los ex -y su energia- a salvo en la
                        # banca. No hay basico -> sigue la promocion normal (ex).
                        if _refresh_promote_prefer_basic:
                            _ref_pb_data = card_table.get(card.id)
                            _ref_is_basic = (
                                _ref_pb_data is not None
                                and not getattr(_ref_pb_data, 'stage1', False)
                                and not getattr(_ref_pb_data, 'stage2', False))
                            if card.id not in OUR_EX_IDS and _ref_is_basic:
                                if card.id == Applin:
                                    score = 6000
                                else:
                                    score = 5500
                    else:

                        if card.id in DUNSPARCE_IDS:
                            # Excepcion (usuario): NUNCA gustear con Boss's Orders a
                            # un Dunsparce (ids 65 y 305). Descartado por completo
                            # como objetivo, en modo estorbo y en modo ofensivo.
                            score = -100000
                        elif _active_cant_attack_this_turn or _sel_active_cant_attack:
                            _rc_target = RETREAT_COST.get(card.id, 0)
                            _target_energy_cnt = len(card.energies) if hasattr(card, 'energies') else 0

                            if _rc_target <= 0:
                                # Coste de retirada GRATIS: el rival lo devuelve al
                                # banco sin pagar nada, no estorba en absoluto.
                                # NUNCA gustear un Pokemon de retirada gratis
                                # (p.ej. Budew). Descartado por completo.
                                score = -100000
                            else:
                                _stall_diff = _rc_target - _target_energy_cnt

                                # Latias ex (habilidad Skyliner) deja retirar GRATIS a
                                # CUALQUIER Basico (incluida ella misma). Con Latias ex
                                # en juego, gustear un Basico NO lo traba (se retira
                                # gratis el proximo turno) y gustear a la propia Latias
                                # ex es inutil. Regla (user, registro 010 paso 76 vs
                                # Dragapult): NUNCA gustear Latias ex ni un Basico si
                                # hay una Latias ex en juego; el objetivo correcto es un
                                # NO-basico (p.ej. Drakloak). Descartado por completo.
                                _lat_forbid = False
                                if op_has_latias_ex:
                                    _tgt_data = card_table.get(card.id)
                                    _lat_tgt_is_basic = (
                                        _tgt_data is not None
                                        and not getattr(_tgt_data, 'stage1', False)
                                        and not getattr(_tgt_data, 'stage2', False))
                                    if card.id == Latias_ex or _lat_tgt_is_basic:
                                        _lat_forbid = True

                                if _lat_forbid:
                                    score = -100000
                                elif _stall_diff >= 1:
                                    # Estorbo proporcional al coste de retirada NETO
                                    # (coste que el rival NO puede pagar con su
                                    # energia): a mayor coste sin energia, mas se
                                    # traba. Prioriza el objetivo con mayor coste de
                                    # retirada sin energias.
                                    score += 500 + _stall_diff * 100
                                    # DESEMPATE (usuario): entre objetivos que traban
                                    # IGUAL (mismo coste de retirada neto), evitar
                                    # subir la PRE-EVOLUCION del atacante principal
                                    # del rival (p.ej. Riolu -> Mega Lucario ex):
                                    # dejarla de activo le permite evolucionarla y
                                    # atacar desde el puesto activo. Penalizacion
                                    # pequena (<100) que SOLO rompe empates y NO
                                    # invierte la prioridad de trabar mas.
                                    if (card.id in THREAT_PREEVO_IDS
                                            or card.id in EX_PREEVO_IDS):
                                        score -= 50
                                else:
                                    # Ya puede pagar su propia retirada: mal objetivo.
                                    score -= 200

                                # Generalizacion de la regla Alakazam (user,
                                # registro_004 paso 51, vs Cynthia's Garchomp,
                                # PERDIDA): al gustear, privilegiar SIEMPRE la
                                # MAYOR evolucion de la linea rival (stage2 >
                                # stage1) siempre que nuestro atacante -el activo
                                # no puede atacar aqui, pero un atacante de BANCA al
                                # que podamos subir tras RETIRAR- pueda NOQUEARLA.
                                # Aplica a mazos de Fase 2 (Cynthia's Garchomp,
                                # Dragapult, Marnie); Alakazam conserva su regla
                                # propia (abajo). Entre iguales se prefiere el mas
                                # invertido (energia + herramienta). Sin esto, el
                                # modo estorbo prefiere el basico (mas dificil de
                                # retirar) y deja crecer la linea evolutiva rival.
                                if (not op_is_alakazam_deck
                                        and card.id not in DUNSPARCE_IDS):
                                    _line_data = card_table.get(card.id)
                                    _line_rank = (
                                        2 if getattr(_line_data, 'stage2', False)
                                        else (1 if getattr(_line_data, 'stage1', False)
                                              else 0))
                                    if _line_rank >= 1:
                                        _line_act = my_state.active[0] if my_state.active else None
                                        _line_can_ko = False
                                        if _line_act is not None:
                                            _line_switch = hand_counts.get(1123, 0) >= 1
                                            _line_rc = RETREAT_COST.get(_line_act.id, 1)
                                            if (_line_switch
                                                    or len(_line_act.energies) >= _line_rc):
                                                _line_grass_after = max(
                                                    0, total_grass
                                                    - (0 if _line_switch else _line_rc))
                                                if _bench_attacker_can_ko(
                                                        my_state, card, meganium_in_play,
                                                        total_grass, bench_count,
                                                        _line_grass_after,
                                                        neutralization_zone_active):
                                                    _line_can_ko = True
                                        if _line_can_ko:
                                            _line_tool = bool(getattr(card, 'tools', None))
                                            score = max(
                                                score,
                                                6000 + _line_rank * 3000
                                                + _target_energy_cnt * 50
                                                + (300 if _line_tool else 0))

                            # Regla (user, registro 014 paso 146 vs Alakazam): al
                            # gustear como ESTORBO (nuestro activo no puede atacar),
                            # PRIORIZAR la linea Alakazam (Abra/Kadabra/Alakazam) por
                            # encima de otros basicos de soporte (p.ej. Shaymin).
                            # Atrapar su pre-evo en el activo corta el desarrollo del
                            # atacante Psiquico y obliga al rival a gastar recursos en
                            # retirarla. Contrarresta el -50 de EX_PREEVO y desempata
                            # la linea Kadabra > Abra > Alakazam.
                            if op_is_alakazam_deck and card.id in (Abra, Kadabra, Alakazam_ex):
                                score += {Kadabra: 350, Abra: 300, Alakazam_ex: 250}[card.id]
                        else:

                            # plan.target (a que rival atacariamos) solo es
                            # relevante cuando NO estamos en modo estorbo; dentro
                            # del estorbo generaba desempates arbitrarios entre
                            # basicos equivalentes.
                            if o.index == plan.target - 1:
                                score += 100

                            _boss_tgt_data = card_table.get(card.id)
                            _boss_tgt_is_ex = (_boss_tgt_data and getattr(_boss_tgt_data, 'ex', False))
                            _boss_tgt_is_stage2 = (_boss_tgt_data and getattr(_boss_tgt_data, 'stage2', False))
                            _boss_tgt_is_stage1 = (_boss_tgt_data and getattr(_boss_tgt_data, 'stage1', False))
                            _boss_tgt_energy = len(card.energies) if hasattr(card, 'energies') else 0
                            _boss_tgt_hp = card.hp if hasattr(card, 'hp') else 999

                            _boss_can_ko = False
                            _boss_our_dmg = 0
                            _boss_atk = my_state.active[0] if my_state.active else None
                            if _boss_atk is not None:
                                _boss_atk_eff_e = len(_boss_atk.energies) * _grass_mult()
                                _boss_can_attach_e = (hand_counts.get(Basic_Grass_Energy, 0) >= 1
                                                     and not state.energyAttached)
                                _boss_atk_after = _boss_atk_eff_e + (_grass_attach_unit() if _boss_can_attach_e else 0)

                                if _boss_atk.id == Hydrapple_ex and _boss_atk_after >= 2:
                                    _boss_our_dmg = 30 + 30 * total_grass
                                elif _boss_atk.id == Dipplin and _boss_atk_after >= 1:
                                    _boss_our_dmg = 20 * bench_count
                                elif _boss_atk.id == Teal_Mask_Ogerpon_ex and _boss_atk_after >= 3:
                                    _o_e = len(card.energies) if hasattr(card, 'energies') else 0
                                    _m_e = len(_boss_atk.energies) + (1 if _boss_can_attach_e else 0)
                                    _boss_our_dmg = 30 + 30 * (_o_e + _m_e)
                                elif _boss_atk.id == Tapu_Bulu and _boss_atk_after >= 4:
                                    _boss_our_dmg = 220
                                elif _boss_atk.id == Fezandipiti_ex and _boss_atk_after >= 3:
                                    _boss_our_dmg = 100
                                elif _boss_atk.id == Meganium and _boss_atk_after >= 4:
                                    _boss_our_dmg = 140
                                elif _boss_atk.id == Bayleef and _boss_atk_after >= 2:
                                    _boss_our_dmg = 60

                                _boss_eff_dmg = _boss_our_dmg
                                if _boss_atk.id != Fezandipiti_ex and _boss_tgt_data:
                                    if getattr(_boss_tgt_data, 'weakness', None) == EnergyType.GRASS:
                                        _boss_eff_dmg *= 2
                                    elif getattr(_boss_tgt_data, 'resistance', None) == EnergyType.GRASS:
                                        _boss_eff_dmg -= 30

                                _boss_atk_is_ex = (_boss_atk.id in OUR_EX_IDS)
                                if card.id in EX_IMMUNE_IDS and _boss_atk_is_ex:
                                    _boss_eff_dmg = 0

                                if card.id in ABILITY_IMMUNE_IDS and _boss_atk.id in OUR_ABILITY_IDS:
                                    _boss_eff_dmg = 0

                                if _boss_eff_dmg >= _boss_tgt_hp:
                                    _boss_can_ko = True

                            if not _boss_can_ko and _boss_atk is not None:
                                _bo_switch_hand = hand_counts.get(1123, 0) >= 1
                                _bo_ret_cost = RETREAT_COST.get(_boss_atk.id, 1)
                                _bo_can_retreat = (_bo_switch_hand
                                                   or len(_boss_atk.energies) >= _bo_ret_cost)
                                if _bo_can_retreat:
                                    _bo_grass_after = max(
                                        0, total_grass - (0 if _bo_switch_hand else _bo_ret_cost))
                                    if _bench_attacker_can_ko(
                                            my_state, card, meganium_in_play, total_grass,
                                            bench_count, _bo_grass_after,
                                            neutralization_zone_active):
                                        _boss_can_ko = True

                            _boss_tier = 0
                            if _boss_can_ko:
                                _bt_has_e = _boss_tgt_energy >= 1
                                _bt_is_exmega = (_boss_tgt_data is not None and
                                                 (getattr(_boss_tgt_data, 'ex', False) or
                                                  getattr(_boss_tgt_data, 'megaEx', False)))
                                if _bt_is_exmega:
                                    _boss_tier = 8 if _bt_has_e else 7
                                elif _boss_tgt_is_stage2:
                                    _boss_tier = 6 if _bt_has_e else 5
                                elif _boss_tgt_is_stage1:
                                    _boss_tier = 4 if _bt_has_e else 3
                                else:
                                    _boss_tier = 2 if _bt_has_e else 1
                                score += _boss_tier * 3000

                                # PRIORIDAD (user, log 86504664 paso 94, PERDIDA
                                # vs Archaludon ex): al poder NOQUEAR, una pre-evo
                                # ENERGIZADA de una linea ex (EX_PREEVO_IDS, p.ej.
                                # Duraludon -> Archaludon ex) es objetivo PRIORITARIO:
                                # noquearla borra un futuro atacante ex de 2 premios.
                                # Por defecto un basico pre-evo cae en tier 2 (6000) y
                                # perdia contra cualquier stage2 NO-ex (tier 6=18000,
                                # p.ej. Cinderace). Le damos un tier efectivo 6.5
                                # (19500): por encima de cualquier objetivo no-ex,
                                # por debajo de un ex real en juego (tier 7-8).
                                if (_bt_has_e and not _bt_is_exmega
                                        and card.id in EX_PREEVO_IDS):
                                    score += max(
                                        0, 19500 - _boss_tier * 3000)

                            # Sin posibilidad de KO: gusteamos como ESTORBO (nuestro
                            # activo puede atacar pero no noquea a NINGUN objetivo).
                            # En ese caso preferir el basico mas dificil de retirar,
                            # es decir el de MAYOR (coste de retirada - energias
                            # cargadas): a mayor coste NETO que el rival no puede
                            # pagar, mas lo trabamos (regla del usuario). Empata con
                            # el desempate del modo estorbo ofensivo/defensivo.
                            if not _boss_can_ko:
                                _bo_stall_diff = (RETREAT_COST.get(card.id, 0)
                                                  - _boss_tgt_energy)
                                if _bo_stall_diff >= 1:
                                    score += _bo_stall_diff * 100
                                    # Desempate entre objetivos que traban IGUAL:
                                    # evitar dejar de activo la PRE-EVOLUCION del
                                    # atacante principal del rival (p.ej. Riolu ->
                                    # Mega Lucario ex), que podria evolucionar y
                                    # atacar desde el puesto activo.
                                    if (card.id in THREAT_PREEVO_IDS
                                            or card.id in EX_PREEVO_IDS):
                                        score -= 50

                            _bo_sel_op_active = op_state.active[0] if op_state.active else None
                            if (_boss_can_ko and _bo_sel_op_active is not None
                                    and _bo_sel_op_active.id == card.id
                                    and len(_bo_sel_op_active.energies) == 0
                                    and _boss_tgt_energy >= 1):
                                score += 200

                            if op_has_dragapult or op_has_dreepy_line:
                                if card.id == Dragapult_ex:
                                    if _boss_can_ko:
                                        score += 1200
                                    else:
                                        score += 800
                                elif card.id == Drakloak:
                                    if _boss_can_ko:
                                        score += 1000
                                    elif _boss_tgt_energy < RETREAT_COST.get(card.id, 1):
                                        # Sin posibilidad de KO: subir al activo el
                                        # Drakloak SIN energia RETRASA el ataque de
                                        # Dragapult y ademas queda CLAVADO (no puede
                                        # pagar su retirada ni atacar). Es el mejor
                                        # objetivo de disrupcion.
                                        score += 700
                                    else:
                                        # Drakloak CON energia: puede pagar su
                                        # retirada y reposicionarse gratis, e incluso
                                        # evolucionar a Dragapult ex ya con energia.
                                        # Estorbo debil: peor que cualquier objetivo
                                        # que quede CLAVADO sin energia.
                                        score += 300
                                elif card.id == Dreepy:
                                    if _boss_can_ko:
                                        score += 400
                                    elif _boss_tgt_energy < RETREAT_COST.get(card.id, 1):
                                        # Dreepy SIN energia para pagar su retirada:
                                        # queda CLAVADO en el activo (no puede atacar
                                        # ni retirarse). Estorbo fuerte, por encima de
                                        # un Drakloak CON energia que se reposiciona
                                        # gratis.
                                        score += 500
                                    else:
                                        # Dreepy que si puede pagar su retirada:
                                        # se reposiciona, estorba poco.
                                        score += 200
                                elif _boss_can_ko:

                                    if _boss_tgt_is_ex:
                                        score += 900 + (_boss_tgt_energy * 50)
                                    elif _boss_tgt_is_stage1:
                                        score += 350 + (_boss_tgt_energy * 50)
                                    else:
                                        score += 250 + (_boss_tgt_energy * 50)
                                else:
                                    score += 150
                            elif op_has_typhlosion or op_has_ethan_preevo:
                                # Mazo Ethan's Typhlosion (linea 352/353/354).
                                # Misma logica que Dragapult: Typhlosion es el
                                # atacante final (fase 2), Quilava la fase 1 clave
                                # (su habilidad busca cartas de Ethan) y Cyndaquil el
                                # basico. Priorizamos clavar/derribar la pieza mas
                                # avanzada de su linea evolutiva.
                                if card.id == Typhlosion:
                                    if _boss_can_ko:
                                        score += 1200
                                    else:
                                        score += 800
                                elif card.id == Quilava:
                                    if _boss_can_ko:
                                        score += 1000
                                    elif _boss_tgt_energy < RETREAT_COST.get(card.id, 1):
                                        # Quilava SIN energia: queda CLAVADO en el
                                        # activo (no puede pagar retirada ni atacar) y
                                        # RETRASA la evolucion a Typhlosion. Mejor
                                        # objetivo de disrupcion de la linea.
                                        score += 700
                                    else:
                                        # Quilava CON energia: puede retirarse gratis
                                        # y reposicionarse (incluso evolucionar ya con
                                        # energia). Estorbo debil.
                                        score += 300
                                elif card.id == Cyndaquil:
                                    if _boss_can_ko:
                                        score += 400
                                    elif _boss_tgt_energy < RETREAT_COST.get(card.id, 1):
                                        # Cyndaquil SIN energia para pagar retirada:
                                        # queda CLAVADO en el activo. Estorbo fuerte,
                                        # por encima de un Quilava CON energia que se
                                        # reposiciona gratis.
                                        score += 500
                                    else:
                                        # Cyndaquil que si puede pagar su retirada:
                                        # se reposiciona, estorba poco.
                                        score += 200
                                elif _boss_can_ko:

                                    if _boss_tgt_is_ex:
                                        score += 900 + (_boss_tgt_energy * 50)
                                    elif _boss_tgt_is_stage1:
                                        score += 350 + (_boss_tgt_energy * 50)
                                    else:
                                        score += 250 + (_boss_tgt_energy * 50)
                                else:
                                    score += 150
                            elif op_is_alakazam_deck:
                                # Mazo Alakazam ex (linea 741/742/743). Misma
                                # logica que Dragapult/Ethan: Alakazam ex es el
                                # atacante final (fase 2 ex), Kadabra la fase 1
                                # (su habilidad Psychic Draw roba 2) y Abra el
                                # basico. Priorizamos clavar/derribar la pieza
                                # mas avanzada de su linea evolutiva.
                                if card.id == Alakazam_ex:
                                    if _boss_can_ko:
                                        score += 1200
                                    else:
                                        score += 800
                                elif card.id == Kadabra:
                                    if _boss_can_ko:
                                        score += 1000
                                    elif _boss_tgt_energy < RETREAT_COST.get(card.id, 1):
                                        # Kadabra SIN energia: queda CLAVADO en el
                                        # activo (no puede pagar retirada ni
                                        # atacar) y RETRASA la evolucion a Alakazam
                                        # ex. Mejor objetivo de disrupcion.
                                        score += 700
                                    else:
                                        # Kadabra CON energia: puede retirarse
                                        # gratis y reposicionarse (incluso
                                        # evolucionar ya con energia). Estorbo debil.
                                        score += 300
                                elif card.id == Abra:
                                    if _boss_can_ko:
                                        score += 400
                                    elif _boss_tgt_energy < RETREAT_COST.get(card.id, 1):
                                        # Abra SIN energia para pagar retirada:
                                        # queda CLAVADO en el activo. Estorbo
                                        # fuerte, por encima de un Kadabra CON
                                        # energia que se reposiciona gratis.
                                        score += 500
                                    else:
                                        # Abra que si puede pagar su retirada: se
                                        # reposiciona, estorba poco.
                                        score += 200
                                elif _boss_can_ko:

                                    if _boss_tgt_is_ex:
                                        score += 900 + (_boss_tgt_energy * 50)
                                    elif _boss_tgt_is_stage1:
                                        score += 350 + (_boss_tgt_energy * 50)
                                    else:
                                        score += 250 + (_boss_tgt_energy * 50)
                                else:
                                    score += 150
                            else:

                                if _boss_can_ko:

                                    if _boss_tgt_is_ex and _boss_tgt_energy >= 1:
                                        score += 1100
                                    elif _boss_tgt_is_ex:
                                        score += 1000
                                    elif _boss_tgt_is_stage2 and _boss_tgt_energy >= 1:
                                        score += 900
                                    elif _boss_tgt_is_stage2:
                                        score += 850
                                    elif _boss_tgt_is_stage1 and _boss_tgt_energy >= 1:
                                        score += 700
                                    elif _boss_tgt_is_stage1:
                                        score += 600
                                    else:

                                        if card.id in THREAT_PREEVO_IDS:
                                            score += 550
                                        elif card.id == Budew:
                                            score += 500
                                        elif card.id == Munkidori:
                                            score += 450
                                        elif card.id == Snorunt:
                                            score += 400
                                        elif card.id in (Dwebble_Grass, Dwebble_Fighting):
                                            score += 380
                                        elif card.id in (Dreepy,):
                                            score += 350
                                        elif _boss_tgt_energy >= 1:
                                            score += 300
                                        else:
                                            score += 200
                                else:

                                    if _boss_tgt_is_ex and _boss_tgt_energy >= 1:
                                        score += 250
                                    elif _boss_tgt_is_ex:
                                        score += 200
                                    elif _boss_tgt_is_stage2 and _boss_tgt_energy >= 1:
                                        score += 180
                                    elif _boss_tgt_is_stage2:
                                        score += 160
                                    elif _boss_tgt_is_stage1 and _boss_tgt_energy >= 1:
                                        score += 150
                                    elif _boss_tgt_is_stage1:
                                        score += 130
                                    elif card.id == Froslass:
                                        score += 220
                                    elif card.id == Budew:
                                        score += 200
                                    elif card.id == Munkidori:
                                        score += 190
                                    elif card.id == Snorunt:
                                        score += 185
                                    elif card.id in (Dreepy, Drakloak):
                                        score += 180
                                    elif card.id in (Dwebble_Grass, Dwebble_Fighting):
                                        score += 178
                                    else:
                                        score += 100

                            if op_is_crustle_deck and card.id in (Dwebble_Grass, Dwebble_Fighting):
                                score = -100000

                            # Regla general: un Pokemon con coste de retirada GRATIS
                            # nunca es buen objetivo de Boss's Orders si NO lo vamos a
                            # noquear este turno (el rival lo devuelve al banco sin
                            # coste). Solo se permite gustearlo cuando es un KO real
                            # (prize), donde la retirada es irrelevante.
                            if RETREAT_COST.get(card.id, 0) <= 0 and not _boss_can_ko:
                                score = -100000

                elif context == SelectContext.SETUP_ACTIVE_POKEMON:

                    if card.id == Teal_Mask_Ogerpon_ex:
                        score = 100
                    elif card.id in (Chikorita, Applin) and hand_counts.get(card.id, 0) >= 2:

                        score = 7
                    elif card.id == Applin:
                        score = 5
                    elif card.id == Chikorita:
                        score = 3
                    elif card.id == Meowth_ex:
                        score = 0
                    else:
                        score = 1

                elif context == SelectContext.SETUP_BENCH_POKEMON:

                    if card.id == Chikorita:
                        score = 8

                        if op_is_fire_deck or op_is_aggro_deck:
                            score = 10
                    elif card.id == Applin:
                        score = 7

                        if op_bench_snipe_threat:
                            score = 4
                        elif op_is_fire_deck or op_is_aggro_deck:
                            score = 8
                    elif card.id == Teal_Mask_Ogerpon_ex:
                        score = 6

                        if op_is_fire_deck:
                            score = 7
                    elif card.id == Meowth_ex:

                        score = -1
                    elif card.id == Fezandipiti_ex:
                        # Al comienzo de la partida (setup) NO bajamos Fezandipiti
                        # ex a la banca salvo que sea el UNICO Pokemon de la mano
                        # (obligados a poner un basico). Fezandipiti ex es debil a
                        # Lucha ({F}) y vale 2 premios, y su habilidad Flip the
                        # Script solo sirve tras ser noqueado; bajarlo de salida
                        # regala un KO de 2 premios facil (critico vs Mega Lucario,
                        # que NO es detectable aun en el setup: el rival no ha
                        # revelado su activo). Si hay otro Pokemon en la mano, lo
                        # conservamos (se puede bajar mas tarde cuando convenga).
                        _setup_hand_poke = 0
                        for _shp in (my_state.hand or []):
                            _shp_data = card_table.get(_shp.id)
                            if _shp_data is not None and _shp_data.cardType == CardType.POKEMON:
                                _setup_hand_poke += 1
                        if _setup_hand_poke <= 1:
                            score = 2
                            if op_has_froslass:
                                score = 0
                            if op_bench_snipe_threat:
                                score = 1
                        else:
                            score = -1
                    elif card.id == Tapu_Bulu:

                        if meganium_in_play and (op_has_ex_immune_active or op_has_ex_immune_bench):
                            score = 3
                        elif op_is_crustle_deck:
                            score = 3
                        else:
                            score = -1
                    elif card.id == Pinsir:

                        if op_is_crustle_deck or op_is_sylveon_deck or op_is_cornerstone_deck:
                            score = 3
                        elif op_has_ex_immune_active or op_has_ex_immune_bench:
                            score = 2
                        else:
                            score = -1

                elif context == SelectContext.TO_HAND:
                    score = 200 - hand_counts[card.id] * 100

                    is_bcs_selection = (select.effect is not None and select.effect.id == Bug_Catching_Set)

                    if is_bcs_selection:

                        score = 100

                        if card.id == Chikorita:
                            if not meganium_in_play and field_counts.get(Chikorita, 0) + field_counts.get(Bayleef, 0) + field_counts.get(Meganium, 0) == 0:
                                score = 800
                                if forest_in_play and (hand_counts[Bayleef] >= 1 or hand_counts[Meganium] >= 1):
                                    score = 950
                            elif not meganium_in_play and field_counts.get(Chikorita, 0) + field_counts.get(Bayleef, 0) >= 1:
                                score = 50
                            else:
                                score = 50

                        elif card.id == Bayleef:
                            if not meganium_in_play and field_counts.get(Chikorita, 0) >= 1:
                                score = 850
                                if forest_in_play and hand_counts[Meganium] >= 1:
                                    score = 950
                            elif not meganium_in_play and hand_counts[Chikorita] >= 1:
                                score = 700
                            elif not meganium_in_play:
                                score = 400
                            else:
                                score = 30

                        elif card.id == Meganium:
                            if not meganium_in_play and (field_counts.get(Bayleef, 0) >= 1):
                                score = 1000
                            elif not meganium_in_play and field_counts.get(Chikorita, 0) >= 1 and forest_in_play:
                                score = 900
                            elif not meganium_in_play:
                                score = 500
                            else:
                                score = 20

                        elif card.id == Applin:
                            if not has_hydrapple and field_counts.get(Applin, 0) + field_counts.get(Dipplin, 0) + field_counts.get(Hydrapple_ex, 0) == 0:
                                score = 700
                                if forest_in_play and (hand_counts[Dipplin] >= 1 or hand_counts[Hydrapple_ex] >= 1):
                                    score = 850
                            elif not has_hydrapple:
                                score = 200
                            else:
                                score = 40

                        elif card.id == Dipplin:
                            if not has_hydrapple and field_counts.get(Applin, 0) >= 1:
                                score = 800
                                if forest_in_play and hand_counts[Hydrapple_ex] >= 1:
                                    score = 900
                            elif not has_hydrapple and hand_counts[Applin] >= 1:
                                score = 650
                            elif op_has_ex_immune_active or op_has_ex_immune_bench:
                                score = 600
                            elif not has_hydrapple:
                                score = 350
                            else:
                                score = 30

                        elif card.id == Hydrapple_ex:
                            if not has_hydrapple and (field_counts.get(Dipplin, 0) >= 1):
                                score = 950
                            elif not has_hydrapple and field_counts.get(Applin, 0) >= 1 and forest_in_play:
                                score = 850
                            elif not has_hydrapple:
                                score = 400
                            else:
                                score = 25

                        elif card.id == Teal_Mask_Ogerpon_ex:
                            if field_counts.get(Teal_Mask_Ogerpon_ex, 0) < 2:
                                score = 600
                                if bench_count <= 2:
                                    score += 100
                            elif (bench_count < 5 and
                                  hand_counts.get(Basic_Grass_Energy, 0) >= 1 and
                                  field_counts.get(Hydrapple_ex, 0) >= 1):

                                score = 550
                            else:
                                score = 20

                        elif card.id == Tapu_Bulu:
                            if field_counts.get(Tapu_Bulu, 0) == 0:

                                if meganium_in_play and (op_has_ex_immune_active or op_has_ex_immune_bench):
                                    score = 600
                                    if has_hydrapple:
                                        score = 700
                                else:
                                    score = 50
                            else:
                                score = 20

                        elif card.id == Pinsir:

                            if field_counts.get(Pinsir, 0) == 0 and (
                                    op_is_crustle_deck or op_is_cornerstone_deck):
                                score = 750
                            else:
                                score = 20

                        elif card.id == Meowth_ex:

                            if (not watchtower_in_play and
                                    field_counts.get(Meowth_ex, 0) == 0 and not state.supporterPlayed and
                                    _best_supp_in_hand_val < 500 and _best_supp_in_mazo_val >= 400):

                                score = min(500, _best_supp_in_mazo_val - 100)
                            else:
                                score = 15

                        elif card.id == Fezandipiti_ex:
                            if op_is_lucario_deck:
                                if (field_counts.get(Fezandipiti_ex, 0) == 0 and
                                        (ko_last_turn or bench_count == 0)):
                                    score = 650
                                else:
                                    score = -1
                            elif field_counts.get(Fezandipiti_ex, 0) == 0 and ko_last_turn:
                                score = 650
                            else:
                                score = 10

                        elif card.id == Basic_Grass_Energy:
                            score = 350

                            if hand_counts[Basic_Grass_Energy] == 0:
                                score = 550
                                if not state.energyAttached:
                                    score = 650
                            elif has_hydrapple:
                                score = 400

                            if hand_counts[Basic_Grass_Energy] >= 3:
                                score = 150

                        if card.id in CARTAS_ACTIVAS_EN_MAZO:
                            prized_copies = CARTAS_ACTIVAS_EN_MAZO[card.id][ESTADO_PREMIO]
                            total_copies = sum(CARTAS_ACTIVAS_EN_MAZO[card.id].values())
                            if prized_copies > 0 and total_copies - prized_copies <= 1:
                                score += 100

                    elif select.effect is not None and select.effect.id == Poke_Pad:

                        score = 10

                        _our_first_turn_pp = ((state.turn == 1 and we_go_first) or
                                              (state.turn == 2 and not we_go_first))
                        if _our_first_turn_pp:
                            _pp_have_applin_sel = (field_counts.get(Applin, 0) >= 1
                                                   or hand_counts.get(Applin, 0) >= 1)
                            _pp_have_chik_sel = (field_counts.get(Chikorita, 0) >= 1
                                                 or hand_counts.get(Chikorita, 0) >= 1)
                            if card.id == Applin and not _pp_have_applin_sel:
                                score = 2000
                            elif card.id == Chikorita and not _pp_have_chik_sel:
                                score = 1900
                            else:
                                score = 10
                        else:

                            # Poke Pad busca un Pokemon NO Rule-Box (basico o
                            # evolucion) hacia la MANO. La regla correcta es mirar el
                            # tablero ACTUAL y traer la SIGUIENTE evolucion de un
                            # Pokemon que YA esta en banca, aunque no se pueda jugar
                            # este mismo turno: sirve para el PROXIMO turno. Por eso NO
                            # usamos la foto de inicio de turno (_field_at_turn_start):
                            # esa foto ignora un Bayleef recien evolucionado y nos haria
                            # buscar un 2o Bayleef redundante en vez del Meganium que SI
                            # completa la linea (Chikorita->Bayleef->Meganium). Con el
                            # tablero actual, un Bayleef en banca -> buscar Meganium.
                            _pp_sel_evolvable = field_counts
                            _pp_sel_has_evo = False

                            if (not meganium_in_play and hand_counts.get(Meganium, 0) == 0):
                                if _pp_sel_evolvable.get(Bayleef, 0) >= 1:
                                    _pp_sel_has_evo = True
                                elif (forest_in_play and _pp_sel_evolvable.get(Chikorita, 0) >= 1 and
                                      hand_counts.get(Bayleef, 0) >= 1):
                                    _pp_sel_has_evo = True

                            if (not meganium_in_play and hand_counts.get(Bayleef, 0) == 0 and
                                    _pp_sel_evolvable.get(Chikorita, 0) >= 1):
                                _pp_sel_has_evo = True

                            if (hand_counts.get(Dipplin, 0) == 0 and
                                    _pp_sel_evolvable.get(Applin, 0) >= 1):
                                _pp_sel_has_evo = True

                            if _pp_sel_has_evo:

                                if card.id == Meganium:
                                    if not meganium_in_play and hand_counts.get(Meganium, 0) == 0:
                                        if _pp_sel_evolvable.get(Bayleef, 0) >= 1:
                                            score = 1000
                                        elif (forest_in_play and _pp_sel_evolvable.get(Chikorita, 0) >= 1 and
                                              hand_counts.get(Bayleef, 0) >= 1):
                                            score = 900
                                    else:
                                        score = 10
                                elif card.id == Bayleef:
                                    if (not meganium_in_play and hand_counts.get(Bayleef, 0) == 0 and
                                            _pp_sel_evolvable.get(Chikorita, 0) >= 1):
                                        score = 850
                                        if forest_in_play and hand_counts.get(Meganium, 0) >= 1:
                                            score = 950
                                    else:
                                        score = 10
                                elif card.id == Dipplin:
                                    if (hand_counts.get(Dipplin, 0) == 0 and
                                            _pp_sel_evolvable.get(Applin, 0) >= 1):
                                        score = 800
                                        if forest_in_play and hand_counts.get(Hydrapple_ex, 0) >= 1:
                                            score = 920
                                    else:
                                        score = 10
                                else:

                                    score = 10
                            else:

                                _pp_have_chik = (field_counts.get(Chikorita, 0) >= 1 or
                                                 hand_counts.get(Chikorita, 0) >= 1)
                                _pp_have_bay = (field_counts.get(Bayleef, 0) >= 1 or
                                                hand_counts.get(Bayleef, 0) >= 1)
                                _pp_have_applin = (field_counts.get(Applin, 0) >= 1 or
                                                   hand_counts.get(Applin, 0) >= 1)
                                _pp_have_dipplin = (field_counts.get(Dipplin, 0) >= 1 or
                                                    hand_counts.get(Dipplin, 0) >= 1)
                                if card.id == Bayleef:
                                    if (not meganium_in_play and _pp_have_chik and
                                            not _pp_have_bay):
                                        score = 850
                                    else:
                                        score = 10
                                elif card.id == Dipplin:
                                    if _pp_have_applin and not _pp_have_dipplin:
                                        score = 800
                                    else:
                                        score = 10
                                elif card.id == Meganium:

                                    if (not meganium_in_play and
                                            hand_counts.get(Meganium, 0) == 0 and
                                            _pp_have_bay):
                                        score = 700
                                    else:
                                        score = 10
                                elif card.id == Chikorita:
                                    _pp_chik_line_sel = (
                                        field_counts.get(Chikorita, 0) + field_counts.get(Bayleef, 0) + field_counts.get(Meganium, 0)) >= 1
                                    _pp_chik_hand_sel = hand_counts.get(Chikorita, 0) >= 1
                                    if (not meganium_in_play and not _pp_chik_line_sel and
                                            not _pp_chik_hand_sel and bench_count < 5):
                                        score = 800
                                    else:
                                        score = 10
                                elif card.id == Applin:
                                    if bench_count < 5:
                                        score = 650
                                    else:
                                        score = 10
                                else:
                                    score = 10

                    elif select.effect is not None and select.effect.id == Night_Stretcher:

                        score = 50

                        if card.id == Basic_Grass_Energy:
                            score = 300

                            _act_og_sel = my_state.active[0] if my_state.active else None
                            # Ogerpon ACTIVO que aun no puede atacar (<3 efectivas)
                            # pero que con UNA Planta via Teal Dance llegaria a >=3:
                            # recuperar la Planta es prioritario. Teal Dance es una
                            # HABILIDAD independiente del adjunte manual, por eso ya
                            # NO se exige _active_needs_energy (que se apaga con
                            # state.energyAttached); en su lugar se exige que la
                            # Planta habilite realmente el ataque (len+unidad >= 3).
                            # Cubre el pivote retirar->promover Ogerpon->Night
                            # Stretcher->Teal Dance->atacar (user, log 86583929
                            # turno 4 vs Alakazam). len(energies) es EFECTIVA (Wild
                            # Growth de Meganium duplica cada Planta).
                            _act_og_can_teal_attack = (
                                _act_og_sel is not None and
                                _act_og_sel.id == Teal_Mask_Ogerpon_ex and
                                len(_act_og_sel.energies) < 3 and
                                len(_act_og_sel.energies) + _grass_attach_unit() >= 3 and
                                hand_counts[Basic_Grass_Energy] == 0)
                            # Hydrapple ex activo que aun no puede atacar (efectiva < 2)
                            # y sin Planta en mano: recuperar una ENERGIA para cargarlo
                            # con Ripening Charge (habilidad, independiente del adjunte
                            # manual, por eso no exige not state.energyAttached).
                            _act_hyd_ripen = (
                                _act_og_sel is not None and
                                _act_og_sel.id == Hydrapple_ex and
                                len(_act_og_sel.energies) * _grass_mult() < 2 and
                                hand_counts[Basic_Grass_Energy] == 0)

                            # Matchup Crustle/Cornerstone: recuperar la Energia Planta
                            # para CARGAR un atacante de banca (Tapu Bulu y cia.) cuando
                            # aun podemos adjuntarla este turno. Asegura que la energia
                            # sea el objetivo preferido de Night Stretcher.
                            _ns_bench_charge_sel = False
                            if ((op_is_crustle_deck or op_is_cornerstone_deck) and
                                    hand_counts[Basic_Grass_Energy] == 0 and
                                    not state.energyAttached):
                                for _nsc_bp in (my_state.bench or []):
                                    if _nsc_bp is None:
                                        continue
                                    if _nsc_bp.id not in (Tapu_Bulu, Teal_Mask_Ogerpon_ex,
                                                          Hydrapple_ex, Meganium):
                                        continue
                                    _nsc_req = ATTACK_ENERGY_REQ.get(_nsc_bp.id)
                                    if _nsc_req is None:
                                        continue
                                    if len(_nsc_bp.energies) * _grass_mult() < _nsc_req:
                                        _ns_bench_charge_sel = True
                                        break

                            if _act_hyd_ripen:
                                # Hydrapple ex ACTIVO que aun no puede atacar: recuperar
                                # energia para cargarlo con Ripening Charge GANA sobre
                                # cualquier otro objetivo de recuperacion (Pokemon
                                # incluidos). Solo cuando Hydrapple ex es el activo; si
                                # no lo es, este caso no aplica y la logica sigue igual.
                                score = 1300
                            elif _ns_bench_charge_sel:
                                # Cargar un atacante de banca vs Crustle: la Energia
                                # Planta es el mejor objetivo de recuperacion.
                                score = 950
                            elif _active_needs_energy and hand_counts[Basic_Grass_Energy] == 0 and not state.energyAttached:
                                score = 900
                            elif _act_og_can_teal_attack:
                                score = 900
                            elif hand_counts[Basic_Grass_Energy] == 0:
                                score = 600
                                if not state.energyAttached:
                                    score = 700
                                ogerpon_bench = field_counts.get(Teal_Mask_Ogerpon_ex, 0)
                                if ogerpon_bench >= 1 and hand_counts[Basic_Grass_Energy] == 0:
                                    score = 750
                            elif has_hydrapple and total_grass < 4:
                                score = 450
                            elif hand_counts[Basic_Grass_Energy] >= 3:
                                score = 100

                        elif card.id == Fezandipiti_ex:

                            if field_counts.get(Fezandipiti_ex, 0) == 0 and ko_last_turn and bench_count < 5:
                                score = 850
                            elif op_is_lucario_deck:
                                if field_counts.get(Fezandipiti_ex, 0) == 0 and bench_count == 0:
                                    score = 200
                                else:
                                    score = -1
                            elif field_counts.get(Fezandipiti_ex, 0) == 0:
                                score = 200
                            else:
                                score = 10

                        elif card.id == Chikorita:
                            if not meganium_in_play:
                                chikorita_line = field_counts.get(Chikorita, 0) + field_counts.get(Bayleef, 0) + field_counts.get(Meganium, 0)
                                if chikorita_line == 0:
                                    score = 800
                                    if forest_in_play and (hand_counts.get(Bayleef, 0) >= 1 or hand_counts.get(Meganium, 0) >= 1):
                                        score = 950
                                    elif hand_counts.get(Bayleef, 0) >= 1:
                                        score = 900

                                    if CARTAS_ACTIVAS_EN_MAZO.get(Chikorita, {}).get(ESTADO_MAZO, 0) == 0:
                                        score += 100
                                    elif CARTAS_ACTIVAS_EN_MAZO.get(Chikorita, {}).get(ESTADO_MAZO, 0) > 0:
                                        score -= 100
                                else:
                                    score = 40
                            else:
                                score = 40

                        elif card.id == Applin:
                            if not has_hydrapple:
                                hydra_line = field_counts.get(Applin, 0) + field_counts.get(Dipplin, 0) + field_counts.get(Hydrapple_ex, 0)
                                if hydra_line == 0:
                                    score = 700
                                    if forest_in_play and (hand_counts.get(Dipplin, 0) >= 1 or hand_counts.get(Hydrapple_ex, 0) >= 1):
                                        score = 870
                                    elif hand_counts.get(Dipplin, 0) >= 1:
                                        score = 800

                                    if CARTAS_ACTIVAS_EN_MAZO.get(Applin, {}).get(ESTADO_MAZO, 0) == 0:
                                        score += 100
                                    elif CARTAS_ACTIVAS_EN_MAZO.get(Applin, {}).get(ESTADO_MAZO, 0) > 0:
                                        score -= 100
                                elif bench_count <= 1:
                                    score = 350
                                else:
                                    score = 80
                            else:
                                score = 35

                        elif card.id == Teal_Mask_Ogerpon_ex:
                            if field_counts.get(Teal_Mask_Ogerpon_ex, 0) < 2:
                                score = 550
                                if field_counts.get(Teal_Mask_Ogerpon_ex, 0) == 0:
                                    score = 700
                                if bench_count <= 1:
                                    score += 100

                                if CARTAS_ACTIVAS_EN_MAZO.get(Teal_Mask_Ogerpon_ex, {}).get(ESTADO_MAZO, 0) == 0:
                                    score += 100
                            elif (bench_count < 5 and
                                  hand_counts.get(Basic_Grass_Energy, 0) >= 1 and
                                  field_counts.get(Hydrapple_ex, 0) >= 1):

                                score = 500
                            else:
                                score = 20

                        elif card.id == Tapu_Bulu:
                            if field_counts.get(Tapu_Bulu, 0) == 0:
                                if meganium_in_play and (op_has_ex_immune_active or op_has_ex_immune_bench):
                                    score = 700
                                    if has_hydrapple:
                                        score = 800
                                elif op_has_ex_immune_active or op_has_ex_immune_bench:
                                    score = 350
                                else:
                                    score = 50
                            else:
                                score = 15

                        elif card.id == Pinsir:

                            if field_counts.get(Pinsir, 0) == 0 and (
                                    op_is_crustle_deck or op_is_cornerstone_deck):
                                score = 850
                            else:
                                score = 15

                        elif card.id == Meowth_ex:

                            if state.turn == 1 and we_go_first:
                                score = 10
                            elif (not watchtower_in_play and
                                    field_counts.get(Meowth_ex, 0) == 0 and
                                    bench_count < 5 and
                                    not state.supporterPlayed and
                                    _best_supp_in_hand_val < 500 and _best_supp_in_mazo_val >= 400):
                                score = min(700, _best_supp_in_mazo_val)

                                if CARTAS_ACTIVAS_EN_MAZO.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) == 0:
                                    score += 100
                            else:
                                score = 15

                        elif card.id == Hydrapple_ex:

                            _ns_sel_evolvable = _field_at_turn_start if (not forest_in_play and _field_at_turn_start) else field_counts
                            if _ns_sel_evolvable.get(Dipplin, 0) >= 1 and not has_hydrapple:
                                score = 980

                            elif (field_counts.get(Applin, 0) >= 1 and
                                    hand_counts.get(Dipplin, 0) >= 1 and
                                    forest_in_play and not has_hydrapple):
                                score = 960
                            else:
                                score = 30

                        elif card.id == Meganium:

                            _ns_sel_evolvable = _field_at_turn_start if (not forest_in_play and _field_at_turn_start) else field_counts
                            if _ns_sel_evolvable.get(Bayleef, 0) >= 1 and not meganium_in_play:
                                score = 990

                            elif (field_counts.get(Chikorita, 0) >= 1 and
                                    hand_counts.get(Bayleef, 0) >= 1 and
                                    forest_in_play and not meganium_in_play):
                                score = 975
                            else:
                                score = 30

                        elif card.id == Dipplin:

                            if (hand_counts.get(Applin, 0) >= 1 and
                                    hand_counts.get(Hydrapple_ex, 0) >= 1 and
                                    forest_in_play and bench_count < 5):
                                score = 970

                            elif (hand_counts.get(Applin, 0) >= 1 and
                                    forest_in_play and bench_count < 5):
                                score = 880

                            elif ((_field_at_turn_start if (not forest_in_play and _field_at_turn_start) else field_counts).get(Applin, 0) >= 1) and not has_hydrapple:
                                score = 850
                            else:
                                score = 30

                        elif card.id == Bayleef:

                            if (hand_counts.get(Chikorita, 0) >= 1 and
                                    hand_counts.get(Meganium, 0) >= 1 and
                                    forest_in_play and bench_count < 5 and
                                    not meganium_in_play):
                                score = 985

                            elif (hand_counts.get(Chikorita, 0) >= 1 and
                                    forest_in_play and bench_count < 5 and
                                    not meganium_in_play):
                                score = 910

                            elif ((_field_at_turn_start if (not forest_in_play and _field_at_turn_start) else field_counts).get(Chikorita, 0) >= 1) and not meganium_in_play:
                                score = 870
                            else:
                                score = 30

                        if card.id in CARTAS_ACTIVAS_EN_MAZO and card.id != Basic_Grass_Energy:
                            entry = CARTAS_ACTIVAS_EN_MAZO[card.id]
                            if entry[ESTADO_MAZO] == 0 and entry[ESTADO_PREMIO] >= 1:
                                score += 200
                            elif entry[ESTADO_MAZO] == 0 and entry[ESTADO_PREMIO] == 0:
                                score += 150

                        if op_is_crustle_deck or op_is_cornerstone_deck:
                            if op_is_cornerstone_deck and not op_is_crustle_deck:
                                _cc_sel_valid = (Tapu_Bulu, Pinsir)
                            else:
                                _cc_sel_valid = (Tapu_Bulu, Pinsir, Applin, Chikorita,
                                                 Dipplin, Bayleef, Meganium)
                            if card.id not in _cc_sel_valid:
                                score = -1

                    elif select.effect is not None and select.effect.id == Ultra_Ball:

                        score = 100

                        hand_play_options, supporters_in_hand = _count_hand_play_options(
                            hand_counts, field_counts, bench_count, state.energyAttached)
                        hand_is_weak = (hand_play_options <= 1 and len(my_state.hand) <= 4)
                        has_energy_for_teal = hand_counts.get(Basic_Grass_Energy, 0) >= 1

                        _ub_evolvable = _field_at_turn_start if (not forest_in_play and _field_at_turn_start) else field_counts

                        _t1_going_second_meowth = (
                            state.turn == 2 and not we_go_first and
                            not state.supporterPlayed and
                            hand_counts.get(Lillie_Determination, 0) == 0 and
                            field_counts.get(Meowth_ex, 0) < 2 and
                            bench_count < 5 and
                            CARTAS_ACTIVAS_EN_MAZO.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) > 0 and
                            CARTAS_ACTIVAS_EN_MAZO.get(Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0)

                        _t1_going_second_need_ogerpon = (
                            state.turn == 2 and not we_go_first and
                            bench_count == 0 and
                            any(field_counts.get(pid, 0) >= 1 for pid in (Applin, Chikorita)) and
                            not any(hand_counts.get(pid, 0) >= 1
                                    for pid in (Chikorita, Applin, Teal_Mask_Ogerpon_ex,
                                                Tapu_Bulu, Meowth_ex, Fezandipiti_ex, Pinsir)))

                        _t1_going_first_need_basic = (
                            state.turn == 1 and we_go_first and
                            bench_count == 0 and
                            not any(hand_counts.get(pid, 0) >= 1
                                    for pid in (Chikorita, Applin, Teal_Mask_Ogerpon_ex,
                                                Tapu_Bulu, Fezandipiti_ex, Pinsir)))

                        # Regla (user, log 85850698 paso 5, GANADO vs Lucario):
                        # cuando solo tenemos UN Pokemon en juego (banca vacia) y
                        # NINGUN Pokemon jugable en la mano, la busqueda de Ultra
                        # Ball debe traer SIEMPRE Meowth ex (Basico que ademas, al
                        # bajarlo, busca un Supporter = Lillie's Determination para
                        # refrescar la mano el proximo turno) en vez de Ogerpon ex.
                        # EXCEPCION: si YA tenemos una Lillie's Determination en la
                        # mano, no hace falta el fetch de Meowth ex -> se prefiere
                        # Ogerpon ex (atacante). Requiere Meowth ex y Lillie's en el
                        # mazo, sin Watchtower (que anula su habilidad) y < 2 Meowth
                        # ex ya en juego.
                        _ub_only_active_in_play = (bench_count == 0)
                        _ub_no_playable_basic_hand = not any(
                            hand_counts.get(pid, 0) >= 1
                            for pid in (Chikorita, Applin, Teal_Mask_Ogerpon_ex,
                                        Tapu_Bulu, Fezandipiti_ex, Pinsir, Meowth_ex))
                        _ub_prefer_meowth_develop = (
                            _ub_only_active_in_play
                            and _ub_no_playable_basic_hand
                            and hand_counts.get(Lillie_Determination, 0) == 0
                            and not watchtower_in_play
                            and field_counts.get(Meowth_ex, 0) < 2
                            and bench_count < 5
                            and CARTAS_ACTIVAS_EN_MAZO.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) > 0
                            and CARTAS_ACTIVAS_EN_MAZO.get(Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0)

                        # -----------------------------------------------------
                        # Prioridad Dipplin vs Meowth ex en la busqueda (user):
                        # Solo se PRIVILEGIA buscar Dipplin en 3 casos:
                        #  1) Ya se jugo una Lillie's Determination antes (esta en
                        #     el descarte).
                        #  2) Rival anti-ex (Crustle / Sylveon / Cornerstone ex) y
                        #     podemos ATACAR este turno con Dipplin (el Applin a
                        #     evolucionar ya tiene energia para el ataque de 1).
                        #  3) Tenemos estadio (Forest) + Hydrapple ex en mano y
                        #     podemos evolucionar a Hydrapple ex y ADEMAS atacar
                        #     (Syrup Storm requiere 2 de energia efectiva).
                        # Si no se cumple ninguno, Meowth ex tiene prioridad para
                        # refrescar la mano, SIN importar lo que haya en la mano.
                        # -----------------------------------------------------
                        # Fix (user, log 86585073 turno 4, vs Marnie, GANADA): que
                        # ya se haya jugado una Lillie's Determination NO basta para
                        # privilegiar a Dipplin/Hydrapple sobre Meowth ex en la
                        # busqueda si AUN quedan Lillie's en el MAZO. Meowth ex (al
                        # bajarlo, su habilidad Last-Ditch Catch busca un Supporter)
                        # sigue siendo la mejor busqueda para refrescar la mano cuando
                        # la linea Hydrapple no aporta ataque (Hydrapple ex es un ex
                        # de 2 premios que aqui no puede atacar). Solo se privilegia a
                        # Dipplin por "Lillie ya jugada" cuando el motor de Lillie's
                        # esta AGOTADO (ninguna copia queda en el mazo); si aun hay
                        # copias, Meowth ex conserva prioridad (_lillie_in_mazo, abajo).
                        _dp_lillie_played = (
                            discard_counts.get(Lillie_Determination, 0) >= 1
                            and CARTAS_ACTIVAS_EN_MAZO.get(
                                Lillie_Determination, {}).get(ESTADO_MAZO, 0) == 0)

                        _dp_applin_energy = 0
                        for _dp_bp in (my_state.bench or []):
                            if _dp_bp is not None and _dp_bp.id == Applin:
                                _dp_applin_energy = max(_dp_applin_energy,
                                                        len(_dp_bp.energies))

                        _dp_anti_ex = (
                            (op_is_crustle_deck or op_is_sylveon_deck or
                             op_is_cornerstone_deck)
                            and _dp_applin_energy >= ATTACK_ENERGY_REQ.get(Dipplin, 1))

                        _dp_can_grass_now = (not state.energyAttached and
                                             hand_counts.get(Basic_Grass_Energy, 0) >= 1)
                        _dp_hydra_req = ATTACK_ENERGY_REQ.get(Hydrapple_ex, 2)
                        _dp_hydra_line = (
                            forest_in_play and
                            hand_counts.get(Hydrapple_ex, 0) >= 1 and
                            _dp_applin_energy >= 1 and
                            (_dp_applin_energy >= _dp_hydra_req or
                             (_dp_can_grass_now and
                              _dp_applin_energy + _grass_attach_unit() >= _dp_hydra_req)))

                        _dipplin_priority = (_dp_lillie_played or _dp_anti_ex or
                                             _dp_hydra_line)

                        # Hydrapple ex traido para evolucionar un Dipplin YA en juego
                        # este turno (rama de score 980), pero que quedaria MUERTO: sin
                        # energia suficiente para Syrup Storm (2 efectiva). Buscar un
                        # Hydrapple ex que no ataca solo tiene sentido si NO hay una
                        # jugada mejor. Cuando el motor de refresco Meowth ex ->
                        # Last-Ditch Catch -> Lillie's Determination esta disponible,
                        # traer Meowth ex (rehace la mano y abre opciones de energia /
                        # atacante) supera a un Hydrapple ex inerte que ademas una
                        # Lillie's posterior podria barajar de vuelta al mazo
                        # (registro 004, paso ~62 vs Iono, PERDIDA). Solo aplica si
                        # Hydrapple ex NO puede atacar este turno.
                        _ub_hydra_evolvable_now = (
                            not has_hydrapple and _ub_evolvable.get(Dipplin, 0) >= 1)
                        _ub_hydra_can_attack_now = False
                        if _ub_hydra_evolvable_now:
                            _ub_best_dip_e = -1
                            for _hp in (([my_state.active[0]] if my_state.active else [])
                                        + list(my_state.bench or [])):
                                if _hp is not None and _hp.id == Dipplin:
                                    if len(_hp.energies) > _ub_best_dip_e:
                                        _ub_best_dip_e = len(_hp.energies)
                            if _ub_best_dip_e >= 0:
                                _ub_hdip_can_attach = (
                                    not state.energyAttached
                                    and hand_counts.get(Basic_Grass_Energy, 0) >= 1)
                                _ub_hdip_after = _ub_best_dip_e + (
                                    _grass_attach_unit() if _ub_hdip_can_attach else 0)
                                if _ub_hdip_after >= ATTACK_ENERGY_REQ.get(Hydrapple_ex, 2):
                                    _ub_hydra_can_attack_now = True
                        _ub_hydra_dead_prefer_meowth = (
                            _ub_hydra_evolvable_now
                            and not _ub_hydra_can_attack_now
                            and not watchtower_in_play
                            and field_counts.get(Meowth_ex, 0) < 2
                            and bench_count < 5
                            and not state.supporterPlayed
                            and hand_counts.get(Lillie_Determination, 0) == 0
                            and CARTAS_ACTIVAS_EN_MAZO.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) > 0
                            and CARTAS_ACTIVAS_EN_MAZO.get(Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0)

                        # Analogo a _ub_hydra_dead_prefer_meowth, pero para la linea
                        # Meganium (Chikorita->Bayleef->Meganium). Un Meganium traido
                        # con Ultra Ball es INUTIL este turno si no hay un Bayleef en
                        # juego que evolucionar (ni Forest+Bayleef en mano para
                        # encadenar): con solo la linea baja en juego (p.ej. Chikorita)
                        # el Meganium es mera preparacion (score 200) y no aporta ataque.
                        # Si ademas NO tenemos un atacante LISTO, preferimos traer
                        # Meowth ex para bajarlo, que su Last-Ditch Catch busque una
                        # Lillie's y refrescar la mano/opciones. Cubre incluso el caso
                        # de un 2o Meowth ex con uno ya en banca (el activo Chikorita
                        # solo hace chip, no es atacante real). (user, registro 004
                        # paso 35 vs Mega Lucario, GANADA)
                        _ub_mega_evolvable_now = (
                            not meganium_in_play and _ub_evolvable.get(Bayleef, 0) >= 1)
                        _ub_mega_chain_now = (
                            not meganium_in_play
                            and _ub_evolvable.get(Chikorita, 0) >= 1
                            and (forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1)
                            and hand_counts.get(Bayleef, 0) >= 1)
                        _ub_mega_dead_prefer_meowth = (
                            not meganium_in_play
                            and not _ub_mega_evolvable_now
                            and not _ub_mega_chain_now
                            and not _active_ready_attacker
                            and not watchtower_in_play
                            and field_counts.get(Meowth_ex, 0) < 2
                            and bench_count < 5
                            and not state.supporterPlayed
                            and hand_counts.get(Lillie_Determination, 0) == 0
                            and CARTAS_ACTIVAS_EN_MAZO.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) > 0
                            and CARTAS_ACTIVAS_EN_MAZO.get(Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0)

                        # Regla (user, registro_004 paso 29, vs Mega Starmie):
                        # generaliza _ub_mega_dead_prefer_meowth. Aunque una
                        # evolucion SEA jugable este turno (p.ej. hay un Bayleef
                        # en juego para subir Meganium), si NO tenemos NINGUN
                        # atacante USABLE este turno la Ultra Ball debe traer
                        # Meowth ex (bajarlo -> Last-Ditch Catch busca Lillie's ->
                        # refrescar la mano y abrir opciones) en vez de una
                        # evolucion que no aportara ataque ahora. Un atacante es
                        # "usable" si: (a) el ACTIVO puede atacar ya, o (b) hay un
                        # atacante LISTO en banca Y el activo puede pagar su coste
                        # de retirada para SUBIRLO al activo. En este registro el
                        # activo (Tapu Bulu, 0 energia, coste 3) no puede
                        # retirarse, asi que el Ogerpon ex cargado de banca esta
                        # atascado -> no hay atacante usable.
                        _uba_act = my_state.active[0] if my_state.active else None
                        _ub_active_can_retreat = (
                            _uba_act is not None
                            and len(_uba_act.energies) >= RETREAT_COST.get(_uba_act.id, 1))
                        _ub_bench_ready_attacker = any(
                            _bp is not None and _bp.id in MAIN_ATTACKERS
                            and _can_attack_eff(_bp.id, len(_bp.energies))
                            for _bp in (my_state.bench or []))
                        _ub_usable_attacker = (
                            _active_ready_attacker
                            or (_ub_active_can_retreat and _ub_bench_ready_attacker))
                        _ub_no_attacker_prefer_meowth = (
                            not _ub_usable_attacker
                            and not watchtower_in_play
                            and field_counts.get(Meowth_ex, 0) < 2
                            and bench_count < 5
                            and not state.supporterPlayed
                            and hand_counts.get(Lillie_Determination, 0) == 0
                            and CARTAS_ACTIVAS_EN_MAZO.get(Meowth_ex, {}).get(ESTADO_MAZO, 0) > 0
                            and CARTAS_ACTIVAS_EN_MAZO.get(Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0)

                        if card.id == Meowth_ex:
                            _lillie_in_mazo = CARTAS_ACTIVAS_EN_MAZO.get(
                                Lillie_Determination, {}).get(ESTADO_MAZO, 0)
                            _any_supp_in_mazo = any(
                                CARTAS_ACTIVAS_EN_MAZO.get(sid, {}).get(ESTADO_MAZO, 0) > 0
                                for sid in (Lillie_Determination, Boss_Orders, Dawn, Lanas_Aid))
                            if watchtower_in_play:
                                # Team Rocket's Watchtower anula la habilidad de
                                # Meowth ex (Pokemon incoloro): no buscarlo con UB.
                                score = 10
                            elif (hand_counts.get(Lillie_Determination, 0) >= 1
                                    and not (op_is_crustle_deck
                                             and hand_counts.get(Boss_Orders, 0) == 0
                                             and CARTAS_ACTIVAS_EN_MAZO.get(
                                                 Boss_Orders, {}).get(ESTADO_MAZO, 0) > 0
                                             and _supp_values.get(Boss_Orders, 0) >= 900)):
                                # Regla (user, log 86339167 paso 23, PERDIDA vs Mega
                                # Starmie): si YA tenemos una Lillie's Determination
                                # en la MANO, no buscar Meowth ex con Ultra Ball. El
                                # unico proposito de traer Meowth ex es que su
                                # habilidad busque un Supporter (Lillie's) para
                                # refrescar la mano; con Lillie's ya en mano es
                                # redundante y desperdicia la Ultra Ball (y su coste
                                # de descarte). Mejor buscar una evolucion util
                                # (p.ej. Bayleef para evolucionar a Chikorita) y
                                # luego jugar la Lillie's. EXCEPCION: vs Crustle,
                                # donde Meowth ex sirve para traer Boss's Orders
                                # (gust), no para refrescar la mano.
                                score = 10
                            elif _ub_prefer_meowth_develop:
                                # Unico Pokemon en juego + sin Basico jugable en
                                # mano + sin Lillie's en mano: traer Meowth ex para
                                # bajarlo, buscar Lillie's y refrescar la mano.
                                score = 1250
                            elif _ub_hydra_dead_prefer_meowth:
                                # La unica evolucion "grande" disponible (Hydrapple ex
                                # sobre un Dipplin en juego) quedaria muerta este turno.
                                # Preferir traer Meowth ex para refrescar la mano con
                                # Lillie's y abrir opciones de juego/ataque.
                                score = 1000
                            elif _ub_mega_dead_prefer_meowth:
                                # La linea Meganium no aporta este turno (no hay Bayleef
                                # en juego que evolucionar) y no tenemos atacante listo:
                                # traer Meowth ex para refrescar con Lillie's en vez de
                                # un Meganium inutil de preparacion.
                                score = 1000
                            elif _ub_no_attacker_prefer_meowth:
                                # No hay atacante USABLE este turno (ni activo que
                                # ataque, ni atacante de banca que podamos subir
                                # porque el activo no puede retirarse). Traer Meowth
                                # ex (refresco Lillie's) supera a evolucionar una
                                # linea que no dara ataque ahora. Score > 1000 para
                                # ganar a un Meganium/evolucion jugable (que puntua
                                # hasta 1000 cuando su pre-evolucion esta en juego).
                                score = 1250
                            elif _t1_going_second_meowth:
                                score = 1200
                            elif state.turn == 1 and we_go_first:
                                score = 10
                            elif field_counts.get(Meowth_ex, 0) >= 2:
                                score = 10
                            elif (field_counts.get(Meowth_ex, 0) >= 1
                                    and not _active_cant_attack_this_turn):
                                score = 10
                            elif bench_count >= 5:
                                score = 10
                            elif _dipplin_priority:
                                # Se cumple una de las 3 condiciones que privilegian
                                # a Dipplin: Meowth ex cede la busqueda (baja) para
                                # que gane Dipplin.
                                score = 10
                            elif _mega_line_active and _lillie_in_mazo > 0:
                                score = 1150
                            elif op_is_dragapult_dusknoir and _lillie_in_mazo > 0:
                                score = 985
                            elif (op_is_crustle_deck and hand_counts.get(Boss_Orders, 0) == 0 and
                                    CARTAS_ACTIVAS_EN_MAZO.get(Boss_Orders, {}).get(ESTADO_MAZO, 0) > 0 and
                                    _supp_values.get(Boss_Orders, 0) >= 900):
                                score = 1100
                            elif _lillie_in_mazo > 0:
                                # No hay condicion que privilegie a Dipplin: Meowth
                                # ex tiene PRIORIDAD para refrescar la mano (buscar
                                # Lillie's), sin importar lo que haya en la mano.
                                score = 1000
                            elif _any_supp_in_mazo:
                                # Otro supporter en el mazo: refrescar igualmente.
                                score = 850
                            else:
                                score = 10

                        elif card.id == Teal_Mask_Ogerpon_ex:

                            if _ub_prefer_meowth_develop:
                                # Cede la busqueda a Meowth ex (refresco de mano):
                                # solo se traeria Ogerpon ex aqui si YA tuvieramos
                                # Lillie's en la mano (entonces _ub_prefer_meowth_
                                # develop es False y se usan las ramas de abajo).
                                score = 200
                            elif _t1_going_second_need_ogerpon:
                                score = 1050

                            elif _t1_going_first_need_basic:
                                _val = 950
                                if hand_counts.get(Basic_Grass_Energy, 0) >= 1:
                                    _val = 1000
                                if field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1:
                                    _val = 200
                                score = _val
                            elif field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 2:
                                if has_energy_for_teal and bench_count < 5:
                                    score = 350
                                else:
                                    score = 15
                            elif has_energy_for_teal and bench_count < 5:

                                score = 700
                                if field_counts.get(Teal_Mask_Ogerpon_ex, 0) == 0:
                                    score = 800
                                if hand_counts.get(Basic_Grass_Energy, 0) >= 2:
                                    score += 100
                            elif field_counts.get(Teal_Mask_Ogerpon_ex, 0) == 0 and bench_count <= 2:

                                score = 300
                            else:

                                score = 100

                        elif state.turn == 2 and not we_go_first:
                            score = 10

                        elif card.id == Meganium:
                            if not meganium_in_play:
                                if _ub_evolvable.get(Bayleef, 0) >= 1:
                                    score = 1000
                                elif (_ub_evolvable.get(Chikorita, 0) >= 1 and
                                      (forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1) and
                                      hand_counts.get(Bayleef, 0) >= 1):
                                    score = 950
                                elif _ub_evolvable.get(Chikorita, 0) >= 1:

                                    score = 200
                                elif field_counts.get(Chikorita, 0) >= 1:

                                    score = 150
                                else:
                                    score = 100
                            else:
                                score = 25

                        elif card.id == Hydrapple_ex:
                            if not has_hydrapple:
                                # Si el activo es un Dipplin que puede evolucionar
                                # a Hydrapple ex y atacar este turno (Syrup Storm
                                # requiere 2 de energia efectiva), priorizamos traer
                                # Hydrapple ex por encima del refill de Fezandipiti
                                # (1050): evolucionar y atacar vale mas que robar.
                                _ub_active_pk = my_state.active[0] if my_state.active else None
                                _ub_dipplin_evo_atk = False
                                if (_ub_active_pk is not None
                                        and _ub_active_pk.id == Dipplin
                                        and _ub_evolvable.get(Dipplin, 0) >= 1):
                                    _ub_dip_e_now = len(_ub_active_pk.energies)
                                    _ub_dip_can_attach = (
                                        not state.energyAttached
                                        and hand_counts.get(Basic_Grass_Energy, 0) >= 1)
                                    _ub_dip_e_after = _ub_dip_e_now + _grass_attach_unit()
                                    _ub_req = ATTACK_ENERGY_REQ.get(Hydrapple_ex, 2)
                                    if (_ub_dip_e_now >= _ub_req
                                            or (_ub_dip_can_attach
                                                and _ub_dip_e_after >= _ub_req)):
                                        _ub_dipplin_evo_atk = True
                                if _ub_dipplin_evo_atk:
                                    score = 1200
                                elif _ub_evolvable.get(Dipplin, 0) >= 1:
                                    score = 980
                                elif (_ub_evolvable.get(Applin, 0) >= 1 and
                                      (forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1) and
                                      hand_counts.get(Dipplin, 0) >= 1):
                                    score = 900
                                elif _ub_evolvable.get(Applin, 0) >= 1:

                                    score = 180
                                elif field_counts.get(Applin, 0) >= 1:

                                    score = 130
                                else:
                                    score = 100

                                # Preparar Hydrapple ex para el PROXIMO turno aunque
                                # NO se pueda evolucionar este mismo turno (p.ej. Dipplin
                                # acaba de evolucionar de Applin y no hay Forest en juego,
                                # por lo que la foto de inicio de turno aun ve Applin y las
                                # ramas anteriores solo dan 180). Con Dipplin ya en juego,
                                # Hydrapple ex esta a UNA sola evolucion; conviene traerlo
                                # a la mano si:
                                #   (A) Dipplin es el UNICO Pokemon de planta en juego, o
                                #   (B) la Ultra Ball desarrollaria la linea Meganium pero
                                #       NO podemos evolucionar a Meganium este mismo turno
                                #       (Dipplin->Hydrapple ex esta mas cerca que
                                #       Chikorita->Bayleef->Meganium).
                                if field_counts.get(Dipplin, 0) >= 1 and score < 860:
                                    _uh_grass_ids = (
                                        Applin, Dipplin, Hydrapple_ex, Chikorita,
                                        Bayleef, Meganium, Teal_Mask_Ogerpon_ex,
                                        Tapu_Bulu, Pinsir)
                                    _uh_grass_in_play = sum(
                                        field_counts.get(pid, 0) for pid in _uh_grass_ids)
                                    _uh_dipplin_only_grass = (
                                        _uh_grass_in_play == field_counts.get(Dipplin, 0))

                                    _uh_can_evo_meganium_now = (
                                        not meganium_in_play and (
                                            _ub_evolvable.get(Bayleef, 0) >= 1
                                            or (_ub_evolvable.get(Chikorita, 0) >= 1
                                                and (forest_in_play
                                                     or hand_counts.get(Forest_of_Vitality, 0) >= 1)
                                                and hand_counts.get(Bayleef, 0) >= 1)))
                                    _uh_meganium_line_dev = (
                                        not meganium_in_play and (
                                            hand_counts.get(Bayleef, 0) >= 1
                                            or hand_counts.get(Meganium, 0) >= 1
                                            or CARTAS_ACTIVAS_EN_MAZO.get(
                                                Bayleef, {}).get(ESTADO_MAZO, 0) > 0
                                            or CARTAS_ACTIVAS_EN_MAZO.get(
                                                Meganium, {}).get(ESTADO_MAZO, 0) > 0))

                                    # No prepar Hydrapple ex "para el proximo turno"
                                    # si la linea Meganium SI se puede ADELANTAR este
                                    # mismo turno buscando Bayleef: hay una Chikorita
                                    # evolucionable ya (estaba al inicio del turno),
                                    # sin Bayleef en mano y con Bayleef en el mazo.
                                    # En ese caso conviene buscar Bayleef (usable YA)
                                    # y no un Hydrapple ex que este turno queda muerto
                                    # (p.ej. el Dipplin acaba de evolucionar y no puede
                                    # evolucionar otra vez), y que ademas podria acabar
                                    # barajado por una Lillie's Determination posterior.
                                    _uh_bayleef_search_now = (
                                        not meganium_in_play
                                        and _ub_evolvable.get(Chikorita, 0) >= 1
                                        and hand_counts.get(Bayleef, 0) == 0
                                        and CARTAS_ACTIVAS_EN_MAZO.get(
                                            Bayleef, {}).get(ESTADO_MAZO, 0) > 0)

                                    if (_uh_dipplin_only_grass
                                            or (_uh_meganium_line_dev
                                                and not _uh_can_evo_meganium_now
                                                and not _uh_bayleef_search_now)):
                                        score = 860

                                # Contra mazos con INMUNIDAD A EX (p.ej. Crustle),
                                # Hydrapple ex es un atacante ex que NO puede hacer
                                # dano a esos Pokemon: es una carta muerta. Degradar
                                # su prioridad de busqueda para que la linea Meganium
                                # (no-ex, que SI puede atacar a Crustle y ademas
                                # duplica el dano de planta) o los atacantes no-ex
                                # (Tapu Bulu, Pinsir) tengan preferencia como objetivo
                                # de la Ultra Ball. Coherente con la logica de descarte,
                                # que ya trata a Hydrapple ex como basura vs Crustle.
                                if (op_is_crustle_deck
                                        or op_has_ex_immune_active
                                        or op_has_ex_immune_bench):
                                    score = min(score, 40)

                                # Hydrapple ex quedaria muerto este turno (no ataca) y
                                # el motor de refresco Meowth ex -> Lillie's esta
                                # disponible: cede la busqueda a Meowth ex, que rehace
                                # la mano. Se degrada por debajo de Meowth ex (1000).
                                if _ub_hydra_dead_prefer_meowth:
                                    score = min(score, 150)
                            else:
                                score = 20

                        elif card.id == Bayleef:
                            if meganium_in_play:
                                score = 20
                            elif field_counts.get(Bayleef, 0) >= 1:

                                score = 20
                            elif hand_counts.get(Bayleef, 0) >= 1:
                                # Ya tenemos un Bayleef EN LA MANO: buscar otro es
                                # redundante (un solo Bayleef basta para evolucionar
                                # a la unica Chikorita). No malgastar la Ultra Ball
                                # ni su coste de descarte en un duplicado.
                                score = 20
                            elif _ub_evolvable.get(Chikorita, 0) >= 1:
                                score = 850
                                if hand_counts.get(Meganium, 0) >= 1 and forest_in_play:
                                    score = 950
                            elif field_counts.get(Chikorita, 0) >= 1:

                                score = 200
                            else:

                                score = 150

                        elif card.id == Dipplin:
                            if has_hydrapple:
                                score = 20
                            elif field_counts.get(Dipplin, 0) >= 1:

                                score = 20
                            elif hand_counts.get(Dipplin, 0) >= 1:
                                # Mismo criterio que Bayleef: ya hay un Dipplin en la
                                # mano, buscar otro con Ultra Ball es redundante.
                                score = 20
                            elif _ub_evolvable.get(Applin, 0) >= 1:
                                if _dipplin_priority:
                                    score = 800
                                    if hand_counts.get(Hydrapple_ex, 0) >= 1 and forest_in_play:
                                        score = 920
                                else:
                                    # Sin ninguna de las 3 condiciones que privilegian
                                    # a Dipplin, Meowth ex refresca mejor: Dipplin baja
                                    # para no robarle la busqueda.
                                    score = 150
                            elif field_counts.get(Applin, 0) >= 1:

                                score = 200
                            elif op_has_ex_immune_active or op_has_ex_immune_bench:
                                if _ub_evolvable.get(Applin, 0) >= 1:
                                    score = 600
                                else:
                                    score = 150
                            else:

                                score = 150

                        elif card.id == Chikorita:

                            if _t1_going_first_need_basic:
                                _val = 850
                                if field_counts.get(Applin, 0) >= 1 or field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1:
                                    _val = 900
                                elif field_counts.get(Chikorita, 0) >= 1:
                                    _val = 200
                                if hand_counts.get(Bayleef, 0) >= 1:
                                    _val += 50
                                score = _val
                            elif not meganium_in_play:
                                meganium_line = field_counts.get(Chikorita, 0) + field_counts.get(Bayleef, 0) + field_counts.get(Meganium, 0)
                                if meganium_line == 0:

                                    _bayleef_in_mazo = CARTAS_ACTIVAS_EN_MAZO.get(Bayleef, {}).get(ESTADO_MAZO, 0) > 0
                                    _meganium_in_mazo = CARTAS_ACTIVAS_EN_MAZO.get(Meganium, {}).get(ESTADO_MAZO, 0) > 0
                                    _has_bayleef_hand = hand_counts.get(Bayleef, 0) >= 1
                                    _forest_available = (forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1)

                                    if _forest_available and _has_bayleef_hand:
                                        score = 880
                                    elif _bayleef_in_mazo or _meganium_in_mazo or _has_bayleef_hand:
                                        score = 700
                                    else:

                                        score = 200
                                else:
                                    score = 150
                            else:
                                score = 30

                        elif card.id == Applin:

                            if _t1_going_first_need_basic:
                                _val = 800
                                if field_counts.get(Chikorita, 0) >= 1 or field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1:
                                    _val = 850
                                elif field_counts.get(Applin, 0) >= 1:
                                    _val = 180
                                if hand_counts.get(Dipplin, 0) >= 1:
                                    _val += 50
                                score = _val
                            elif not has_hydrapple:
                                hydra_line = field_counts.get(Applin, 0) + field_counts.get(Dipplin, 0) + field_counts.get(Hydrapple_ex, 0)
                                if hydra_line == 0:

                                    _dipplin_in_mazo = CARTAS_ACTIVAS_EN_MAZO.get(Dipplin, {}).get(ESTADO_MAZO, 0) > 0
                                    _hydrapple_in_mazo = CARTAS_ACTIVAS_EN_MAZO.get(Hydrapple_ex, {}).get(ESTADO_MAZO, 0) > 0
                                    _has_dipplin_hand = hand_counts.get(Dipplin, 0) >= 1
                                    _forest_available = (forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1)

                                    if _forest_available and _has_dipplin_hand:
                                        if hand_counts.get(Hydrapple_ex, 0) >= 1:

                                            score = 980
                                        else:

                                            score = 800
                                    elif _dipplin_in_mazo or _hydrapple_in_mazo or _has_dipplin_hand:
                                        score = 650
                                    else:

                                        score = 180
                                else:
                                    score = 120
                            else:
                                score = 25

                        elif card.id == Tapu_Bulu:
                            if field_counts.get(Tapu_Bulu, 0) == 0:

                                if meganium_in_play and (op_has_ex_immune_active or op_has_ex_immune_bench):
                                    score = 750
                                    if has_hydrapple:
                                        score = 850
                                else:
                                    score = 50
                            else:
                                score = 15

                        elif card.id == Pinsir:

                            if field_counts.get(Pinsir, 0) == 0 and (
                                    op_is_crustle_deck or op_is_cornerstone_deck):
                                score = 900
                            else:
                                score = 15

                        elif card.id == Fezandipiti_ex:
                            if (field_counts.get(Fezandipiti_ex, 0) == 0 and ko_last_turn and
                                    bench_count < 5):

                                score = 1050
                            else:
                                score = 10

                        if card.id in CARTAS_ACTIVAS_EN_MAZO:
                            entry = CARTAS_ACTIVAS_EN_MAZO[card.id]
                            prized = entry[ESTADO_PREMIO]
                            total_copies = sum(entry.values())
                            accessible = total_copies - prized

                            if prized > 0 and accessible <= 1:
                                score += 150

                            if hand_counts.get(card.id, 0) >= 1:
                                score -= 150

                    elif select.effect is not None and select.effect.id == Meowth_ex:

                        score = 50

                        _has_strong_attacker_sel = (
                            field_counts.get(Hydrapple_ex, 0) >= 1 or
                            field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1)
                        _hand_size_sel = len(my_state.hand) if my_state.hand else 0

                        _supp_ids = (Boss_Orders, Dawn, Lillie_Determination, Lanas_Aid)
                        if card.id in _supp_ids:
                            _sv = _supp_values.get(card.id, 0)

                            _no_energy_in_hand = (hand_counts.get(Basic_Grass_Energy, 0) == 0)

                            if (_win_via_boss_gust or _gust_2prize_via_boss) and card.id == Boss_Orders:
                                score = 1300
                            elif _meowth_devel_lillie and card.id == Lillie_Determination:

                                score = 1250
                            elif _hand_size_sel <= 2:

                                if card.id == Lillie_Determination:
                                    score = 1200
                                else:
                                    score = min(_sv, 100)
                            elif ((_active_cant_attack_this_turn or _sel_active_cant_attack)
                                    and _no_energy_in_hand):

                                if card.id == Lillie_Determination:
                                    score = 1200
                                else:
                                    score = min(_sv, 150)
                            elif ((_active_cant_attack_this_turn or _sel_active_cant_attack) and
                                    hand_counts.get(Lillie_Determination, 0) == 0):

                                if card.id == Lillie_Determination:
                                    score = 1200
                                else:
                                    score = min(_sv, 150)
                            elif not _has_strong_attacker_sel and _hand_size_sel <= 5:

                                if card.id == Lillie_Determination:
                                    score = 1000
                                else:
                                    score = min(_sv, 200)
                            elif not _has_strong_attacker_sel:

                                if card.id == Lillie_Determination:
                                    score = 800
                                else:
                                    score = min(_sv, 400)
                            else:

                                score = _sv

                                if card.id == Boss_Orders and op_is_crustle_deck:
                                    score += 100

                    elif select.effect is not None and select.effect.id == Dawn:

                        score = 50
                        _forest_avail = forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1

                        if card.id == Meganium:
                            if meganium_in_play:
                                score = 10
                            elif field_counts.get(Bayleef, 0) >= 1:

                                score = 1000
                            elif field_counts.get(Chikorita, 0) >= 1 and _forest_avail:

                                if hand_counts.get(Bayleef, 0) >= 1:
                                    score = 980
                                else:
                                    score = 950
                            elif hand_counts.get(Chikorita, 0) >= 1 and _forest_avail:

                                if hand_counts.get(Bayleef, 0) >= 1:
                                    score = 960
                                else:
                                    score = 920
                            else:
                                score = 200

                        elif card.id == Bayleef:
                            if meganium_in_play:
                                score = 10
                            elif field_counts.get(Chikorita, 0) >= 1:

                                score = 900
                                if _forest_avail and (hand_counts.get(Meganium, 0) >= 1 or
                                        CARTAS_ACTIVAS_EN_MAZO.get(Meganium, {}).get(ESTADO_MAZO, 0) > 0):
                                    score = 970
                            elif hand_counts.get(Chikorita, 0) >= 1 and _forest_avail:

                                score = 880
                            elif bench_count < 5 and hand_counts.get(Chikorita, 0) >= 1:

                                score = 500
                            else:
                                score = 150

                        elif card.id == Chikorita:
                            if meganium_in_play:
                                score = 10
                            elif field_counts.get(Chikorita, 0) + field_counts.get(Bayleef, 0) + field_counts.get(Meganium, 0) >= 1:
                                score = 50
                            elif bench_count >= 5:
                                score = 30
                            elif _forest_avail and hand_counts.get(Bayleef, 0) >= 1:

                                score = 850
                            elif _forest_avail:

                                score = 800
                            elif hand_counts.get(Bayleef, 0) >= 1:

                                score = 700
                            else:

                                score = 500

                        elif card.id == Hydrapple_ex:
                            if has_hydrapple:
                                score = 10
                            elif field_counts.get(Dipplin, 0) >= 1:

                                score = 980
                            elif field_counts.get(Applin, 0) >= 1 and _forest_avail:

                                if hand_counts.get(Dipplin, 0) >= 1:
                                    score = 960
                                else:
                                    score = 930
                            elif hand_counts.get(Applin, 0) >= 1 and _forest_avail:

                                if hand_counts.get(Dipplin, 0) >= 1:
                                    score = 940
                                else:
                                    score = 900
                            else:
                                score = 180

                        elif card.id == Dipplin:
                            if has_hydrapple and field_counts.get(Dipplin, 0) >= 1:
                                score = 10
                            elif field_counts.get(Applin, 0) >= 1:

                                score = 880
                                if _forest_avail and (hand_counts.get(Hydrapple_ex, 0) >= 1 or
                                        CARTAS_ACTIVAS_EN_MAZO.get(Hydrapple_ex, {}).get(ESTADO_MAZO, 0) > 0):
                                    score = 950
                            elif hand_counts.get(Applin, 0) >= 1 and _forest_avail:
                                score = 860
                            elif bench_count < 5 and hand_counts.get(Applin, 0) >= 1:
                                score = 480
                            else:
                                score = 130

                        elif card.id == Applin:
                            if has_hydrapple and field_counts.get(Applin, 0) + field_counts.get(Dipplin, 0) >= 1:
                                score = 10
                            elif field_counts.get(Applin, 0) + field_counts.get(Dipplin, 0) + field_counts.get(Hydrapple_ex, 0) >= 2:
                                score = 30
                            elif bench_count >= 5:
                                score = 30
                            elif _forest_avail and hand_counts.get(Dipplin, 0) >= 1:
                                score = 830
                            elif _forest_avail:
                                score = 780
                            elif hand_counts.get(Dipplin, 0) >= 1:
                                score = 680
                            else:
                                score = 480

                        elif card.id == Teal_Mask_Ogerpon_ex:
                            if field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 2:
                                score = 10
                            elif bench_count >= 5:
                                score = 30
                            else:
                                score = 400
                                if field_counts.get(Teal_Mask_Ogerpon_ex, 0) == 0:
                                    score = 500

                        elif card.id == Tapu_Bulu:
                            if field_counts.get(Tapu_Bulu, 0) >= 1:
                                score = 10
                            elif op_is_crustle_deck or op_has_ex_immune_active or op_has_ex_immune_bench:
                                score = 600
                                if meganium_in_play:
                                    score = 700
                            else:
                                score = 100

                        elif card.id == Fezandipiti_ex:
                            if field_counts.get(Fezandipiti_ex, 0) >= 1:
                                score = 10
                            elif ko_last_turn:
                                score = 500
                            else:
                                score = 80

                        elif card.id == Meowth_ex:
                            if field_counts.get(Meowth_ex, 0) >= 1:
                                score = 10
                            elif not watchtower_in_play and not state.supporterPlayed and bench_count < 5:
                                score = 300
                            else:
                                score = 50

                        elif card.id == Basic_Grass_Energy:
                            if not state.energyAttached and hand_counts[Basic_Grass_Energy] == 0:
                                score = 400
                            elif hand_counts[Basic_Grass_Energy] == 0:
                                score = 250
                            else:
                                score = 80

                        elif card.id == Forest_of_Vitality:
                            if not forest_in_play and not _forest_avail:
                                score = 600
                            else:
                                score = 10

                        else:

                            score = 50 - hand_counts.get(card.id, 0) * 30

                    else:

                        if card.id == Chikorita:
                            if field_counts[Chikorita] + field_counts[Bayleef] + field_counts[Meganium] >= 1:
                                score -= 150
                            else:
                                score += 80
                        elif card.id == Bayleef:
                            if field_counts[Chikorita] >= 1 or field_counts[Bayleef] >= 1:
                                score += 60
                            else:
                                score -= 50
                        elif card.id == Meganium:
                            if (field_counts[Bayleef] >= 1 or field_counts[Chikorita] >= 1) and not meganium_in_play:
                                score += 100
                            elif meganium_in_play:
                                score -= 200
                            else:
                                score -= 50
                        elif card.id == Applin:
                            if field_counts[Applin] + field_counts[Dipplin] + field_counts[Hydrapple_ex] >= 2:
                                score -= 100
                            else:
                                score += 60
                        elif card.id == Dipplin:
                            if field_counts[Applin] >= 1:
                                score += 70
                            else:
                                score -= 30

                            if op_has_ex_immune_active or op_has_ex_immune_bench:
                                score += 80
                        elif card.id == Hydrapple_ex:
                            if field_counts[Dipplin] >= 1 or field_counts[Applin] >= 1:
                                score += 90
                            elif has_hydrapple:
                                score -= 150
                            else:
                                score -= 30
                        elif card.id == Teal_Mask_Ogerpon_ex:
                            if field_counts[card.id] < 2:
                                score += 50
                            else:
                                score -= 100
                        elif card.id == Meowth_ex:
                            if field_counts[card.id] >= 1:
                                score -= 150
                            else:
                                score += 20
                        elif card.id == Fezandipiti_ex:
                            if field_counts[card.id] >= 1:
                                score -= 200
                            else:
                                score += 15
                        elif card.id == Forest_of_Vitality:
                            if not forest_in_play:
                                score += 70
                            else:
                                score -= 100
                        elif card.id == Basic_Grass_Energy:
                            if not state.energyAttached:
                                score += 40
                            else:
                                score -= 5
                        elif card.id == Tapu_Bulu:
                            if field_counts[card.id] >= 1:
                                score -= 100
                            elif meganium_in_play and (op_has_ex_immune_active or op_has_ex_immune_bench):
                                score += 60
                            else:
                                score -= 10

                    # Matchup vs Cubchoo: Lana's Aid y Night Stretcher SOLO
                    # recuperan Energias Basicas del descarte, nunca Pokemon.
                    # El ataque de Cubchoo deja a nuestro activo sin poder
                    # atacar el proximo turno, asi que aprovechamos el turno
                    # para recargar energia y no gastamos estas cartas en
                    # recuperar Pokemon.
                    if (op_is_cubchoo_deck and select.effect is not None and
                            select.effect.id in (Night_Stretcher, Lanas_Aid)):
                        if card.id == Basic_Grass_Energy:
                            score = max(score, 900)
                        else:
                            score = -1

                elif context == SelectContext.DISCARD:

                    score = 50

                    _has_recovery = (hand_counts.get(Night_Stretcher, 0) >= 1 or
                                    hand_counts.get(Lanas_Aid, 0) >= 1 or
                                    CARTAS_ACTIVAS_EN_MAZO.get(Night_Stretcher, {}).get(ESTADO_MAZO, 0) > 0 or
                                    CARTAS_ACTIVAS_EN_MAZO.get(Lanas_Aid, {}).get(ESTADO_MAZO, 0) > 0)

                    _ns_in_hand = (hand_counts.get(Night_Stretcher, 0) >= 1)

                    _total_supps_in_hand = (hand_counts.get(Lillie_Determination, 0) +
                                           hand_counts.get(Boss_Orders, 0) +
                                           hand_counts.get(Dawn, 0) +
                                           hand_counts.get(Lanas_Aid, 0))
                    _protect_last_supporter = (not state.supporterPlayed and _total_supps_in_hand <= 1)

                    _refresh_supps_in_hand = (hand_counts.get(Lillie_Determination, 0) +
                                              hand_counts.get(Dawn, 0))
                    _protect_refresh_supporter = (not state.supporterPlayed and
                                                  _refresh_supps_in_hand <= 1)

                    _ogerpon_on_field = (field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1)
                    _ogerpon_playable = (hand_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1 and bench_count < 5)
                    _teal_dance_possible = ((_ogerpon_on_field or _ogerpon_playable) and
                                            hand_counts[Basic_Grass_Energy] >= 1)

                    _has_teal_dance_target = (bench_count >= 1 or
                                             hand_counts.get(Applin, 0) >= 1 or
                                             hand_counts.get(Chikorita, 0) >= 1 or
                                             hand_counts.get(Tapu_Bulu, 0) >= 1 or
                                             _ogerpon_playable)
                    _teal_dance_possible = _teal_dance_possible and _has_teal_dance_target

                    if card.id == Basic_Grass_Energy:
                        energy_in_hand = hand_counts[Basic_Grass_Energy]

                        if _teal_dance_possible:

                            if energy_in_hand >= 4:
                                score = 85
                            elif energy_in_hand >= 3:
                                score = 75
                            elif energy_in_hand == 2:

                                score = 18
                            else:

                                score = 2
                        else:

                            if energy_in_hand >= 4:
                                score = 92
                            elif energy_in_hand >= 3:
                                score = 85
                            elif energy_in_hand >= 2:
                                score = 70
                            else:
                                score = 35
                                if state.energyAttached:
                                    score = 65

                        if _has_recovery:
                            score += 5

                        if _ns_in_hand:
                            score += 5

                        energy_in_mazo = CARTAS_ACTIVAS_EN_MAZO.get(Basic_Grass_Energy, {}).get(ESTADO_MAZO, 0)
                        if energy_in_mazo >= 5:
                            score += 5

                    elif card.id == Forest_of_Vitality:
                        if forest_in_play:
                            score = 95
                        elif hand_counts[Forest_of_Vitality] > 1:
                            score = 88
                        elif meganium_in_play and has_hydrapple:
                            score = 70
                        elif CARTAS_ACTIVAS_EN_MAZO.get(Forest_of_Vitality, {}).get(ESTADO_MAZO, 0) >= 2:
                            score = 55
                        else:
                            score = 15

                    elif card.id == Meganium:
                        if meganium_in_play:
                            score = 95
                        elif field_counts.get(Bayleef, 0) >= 1:
                            # Solo es "casi intocable" cuando la linea esta lista de
                            # verdad: con un Bayleef en juego Meganium esta a una sola
                            # evolucion. Tener solo Chikorita NO cuenta (faltan dos
                            # evoluciones), asi que en ese caso cae a las ramas de
                            # abajo y queda mas descartable que un supporter sin jugar.
                            score = 3
                        elif CARTAS_ACTIVAS_EN_MAZO.get(Meganium, {}).get(ESTADO_MAZO, 0) >= 1:
                            score = 40
                        else:
                            score = 20

                    elif card.id == Bayleef:
                        if meganium_in_play:
                            score = 88
                        elif field_counts.get(Chikorita, 0) >= 1:
                            score = 3
                        elif hand_counts.get(Bayleef, 0) > 1:
                            score = 75
                        elif CARTAS_ACTIVAS_EN_MAZO.get(Bayleef, {}).get(ESTADO_MAZO, 0) >= 1:
                            score = 50
                        else:
                            score = 25

                    elif card.id == Chikorita:
                        if meganium_in_play:
                            score = 85
                        elif field_counts.get(Chikorita, 0) + field_counts.get(Bayleef, 0) >= 1:
                            score = 75
                        elif hand_counts.get(Chikorita, 0) > 1:
                            score = 72
                        elif _ns_in_hand:
                            score = 62
                        elif _has_recovery:
                            score = 55
                        else:
                            score = 18

                    elif card.id == Applin:
                        if has_hydrapple:
                            score = 83
                        elif field_counts.get(Applin, 0) + field_counts.get(Dipplin, 0) >= 1:
                            score = 72
                        elif hand_counts.get(Applin, 0) > 1:
                            score = 70
                        elif _ns_in_hand:
                            score = 60
                        elif _has_recovery:
                            score = 52
                        else:
                            score = 18

                    elif card.id == Tapu_Bulu:
                        if field_counts.get(Tapu_Bulu, 0) >= 1:
                            score = 95
                        elif meganium_in_play and (op_has_ex_immune_active or op_has_ex_immune_bench):
                            score = 5
                        elif op_has_ex_immune_active or op_has_ex_immune_bench:
                            score = 20
                        else:
                            score = 90

                    elif card.id == Pinsir:

                        if field_counts.get(Pinsir, 0) >= 1:
                            score = 95
                        elif op_has_ex_immune_active or op_has_ex_immune_bench:
                            score = 15
                        else:
                            score = 90

                    elif card.id == Hydrapple_ex:
                        if op_is_crustle_deck or op_has_ex_immune_active or op_has_ex_immune_bench:

                            score = 96
                        elif has_hydrapple and hand_counts.get(Hydrapple_ex, 0) > 1:
                            score = 55
                        elif has_hydrapple:
                            score = 30
                        elif field_counts.get(Dipplin, 0) >= 1 or field_counts.get(Applin, 0) >= 1:
                            score = 3
                        elif (hand_counts.get(Dipplin, 0) >= 1 and
                              (forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1) and
                              CARTAS_ACTIVAS_EN_MAZO.get(Applin, {}).get(ESTADO_MAZO, 0) > 0):
                            score = 3
                        else:
                            score = 12

                    elif card.id == Teal_Mask_Ogerpon_ex:
                        if field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 2:
                            score = 65
                        elif field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1:
                            score = 25
                        else:
                            score = 8

                    elif card.id == Dipplin:
                        if has_hydrapple and not (op_has_ex_immune_active or op_has_ex_immune_bench):
                            score = 55
                        elif field_counts.get(Applin, 0) >= 1:
                            score = 5
                        elif (hand_counts.get(Hydrapple_ex, 0) >= 1 and
                              (forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1) and
                              CARTAS_ACTIVAS_EN_MAZO.get(Applin, {}).get(ESTADO_MAZO, 0) > 0):
                            score = 3
                        elif op_has_ex_immune_active or op_has_ex_immune_bench:
                            score = 8
                        else:
                            score = 18

                    elif card.id == Meowth_ex:
                        if field_counts.get(Meowth_ex, 0) >= 1:
                            score = 82
                        elif bench_count >= 5 and state.supporterPlayed:

                            score = 65
                        else:

                            score = 2

                    elif card.id == Fezandipiti_ex:
                        if field_counts.get(Fezandipiti_ex, 0) >= 1:
                            score = 82
                        elif ko_last_turn and bench_count < 5:

                            score = -10000
                        else:

                            score = 38

                    elif card.id == Boss_Orders:
                        if (op_is_crustle_deck or op_has_dwebble_bench) and hand_counts.get(Boss_Orders, 0) <= 1:

                            score = 2
                        elif hand_counts.get(Boss_Orders, 0) > 1:
                            score = 85
                        elif _protect_last_supporter:
                            score = 12
                        elif budew_on_op_field or op_has_dwebble_bench:
                            score = 10
                        elif op_prize <= 3:
                            score = 20
                        elif state.turn <= 5 and hand_counts.get(Dawn, 0) >= 1:

                            score = 30
                        else:
                            # Copia unica de Boss's Orders: aunque ya hayamos jugado
                            # el supporter del turno, conserva valor a futuro (gust al
                            # banco para rematar/desviar), asi que NO es descarte libre.
                            # Se protege, pero MENOS que Lillie's: si hay que soltar un
                            # supporter para pagar un coste, cae Boss's antes que Lillie's.
                            score = 22

                    elif card.id == Lillie_Determination:
                        if _lillie_protected_once:
                            # Copia sobrante (ya conservamos una): descartable.
                            score = 72
                        else:
                            _lillie_protected_once = True
                            if _protect_last_supporter:

                                score = 5
                            elif _protect_refresh_supporter:

                                score = 2
                            elif state.turn <= 5 and not state.supporterPlayed:

                                score = 8
                            elif hand_counts.get(Lillie_Determination, 0) > 1:
                                # Hay duplicados y ya jugamos supporter: conservamos
                                # una copia (puntaje bajo) y las demas seran las
                                # descartables via la rama de arriba.
                                score = 20
                            elif len(my_state.hand) >= 6:
                                # Copia unica: aun con el supporter ya jugado, Lillie's
                                # conserva valor a futuro (robo/mano nueva). Se protege
                                # POR DEBAJO de Boss's (Lillie tiene prioridad de
                                # conservacion), de modo que Boss's cae primero.
                                score = 16
                            else:
                                score = 14

                    elif card.id == Dawn:
                        if meganium_in_play and has_hydrapple:
                            score = 75
                        elif _protect_last_supporter:
                            score = 12
                        elif _protect_refresh_supporter:
                            score = 3
                        elif state.turn <= 5 and (hand_counts.get(Lillie_Determination, 0) >= 1 or
                                                  hand_counts.get(Boss_Orders, 0) >= 1):

                            score = 55
                        elif not meganium_in_play or not has_hydrapple:
                            score = 15
                        else:
                            score = 50

                    elif card.id == Lanas_Aid:

                        if hand_counts.get(Lanas_Aid, 0) > 1:
                            score = 80
                        elif _protect_last_supporter:
                            score = 12
                        elif len(my_state.discard) <= 2:
                            score = 75
                        else:
                            score = 35

                    elif card.id == Night_Stretcher:
                        # Night Stretcher solo recupera un Pokemon o una Energia
                        # BASICA del descarte. Regla (user): NO jugarlo si el UNICO
                        # objetivo recuperable es Energia basica que NO podemos usar
                        # este turno (ya adjuntamos energia: state.energyAttached).
                        # Recuperar una energia muerta malgasta la carta sin aportar
                        # nada. Si hay un Pokemon recuperable, o aun podemos adjuntar
                        # la energia (energyAttached False), el veto NO aplica.
                        _ns_disc_poke = any(
                            (card_table.get(_dc.id) is not None
                             and card_table[_dc.id].cardType == CardType.POKEMON)
                            for _dc in my_state.discard)
                        _ns_disc_basic_energy = any(
                            _dc.id == Basic_Grass_Energy
                            for _dc in my_state.discard)
                        _ns_only_dead_energy = (
                            not _ns_disc_poke
                            and _ns_disc_basic_energy
                            and state.energyAttached)
                        if _ns_only_dead_energy:
                            score = -1
                        elif hand_counts.get(Night_Stretcher, 0) > 1:
                            score = 78
                        elif len(my_state.discard) <= 1:
                            score = 70
                        else:
                            score = 30

                    elif card.id == Bug_Catching_Set:
                        if hand_counts.get(Bug_Catching_Set, 0) > 1:
                            score = 76
                        elif itchy_pollen_active:
                            score = 85
                        else:
                            score = 45

                    elif card.id == Ultra_Ball:

                        if hand_counts.get(Ultra_Ball, 0) > 1:
                            score = 95
                        else:
                            score = 38

                    elif card.id == Poke_Pad:
                        if itchy_pollen_active:
                            score = 85
                        else:
                            score = 55

                    elif card.id == Unfair_Stamp:

                        score = -10000

                    # Estrategia vs Comfey (user, registro_005): descarte por
                    # Xerosic's Machinations (nos deja SOLO 3 cartas en la mano). La
                    # prioridad de MANTENER es: Energias > Night Stretcher > Lana's
                    # Aid > Unfair Stamp > resto de entrenadores. El score aqui es de
                    # DESCARTE (mayor = se descarta antes), asi que las cartas a
                    # MANTENER llevan score BAJO. Un Ogerpon ex EXTRA (ya hay 2 en
                    # juego) es inutil -> se descarta; si aun caben (<2), se conserva
                    # por encima de los entrenadores porque es el plan del matchup.
                    if op_is_comfey_deck:
                        if card.id == Basic_Grass_Energy:
                            score = 80
                        elif card.id == Teal_Mask_Ogerpon_ex:
                            score = (850 if field_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 2
                                     else 120)
                        elif card.id == Night_Stretcher:
                            score = 300
                        elif card.id == Lanas_Aid:
                            score = 400
                        elif card.id == Unfair_Stamp:
                            score = 500
                        else:
                            score = 850

                elif context == SelectContext.RECOVER_SPECIAL_CONDITION:

                    if hasattr(card, 'id'):
                        score = 50
                elif context == SelectContext.AFFECT_SPECIAL_CONDITION:

                    score = 50
                elif context == SelectContext.ATTACH_FROM:
                    score = energy_score(card, o.area == AreaType.ACTIVE)

        elif o.type == OptionType.PLAY:
            card = get_card(obs, AreaType.HAND, o.index, my_index)
            if card is None:
                score = -1
            else:
                data = card_table[card.id]
                if data.cardType == CardType.POKEMON:
                    score = 20000

                    _block_4th_ex = False
                    if ((op_is_crustle_deck or op_is_cornerstone_deck)
                            and card.id in OUR_EX_IDS):
                        _ex_in_play = sum(field_counts.get(_ex_id, 0)
                                          for _ex_id in OUR_EX_IDS)
                        if _ex_in_play >= 3:
                            _block_4th_ex = True

                    if _block_4th_ex:
                        score = -1
                    elif card.id == Chikorita:

                        _meg_line_count = field_counts[Chikorita] + field_counts[Bayleef] + field_counts[Meganium]
                        _max_meg_line = 2 if (op_is_crustle_deck or op_is_cornerstone_deck) else 1
                        if _meg_line_count >= _max_meg_line:
                            score = -1
                        else:
                            _forest_avail = forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1

                            if (op_has_mega_starmie_active and
                                    not (_forest_avail and hand_counts.get(Bayleef, 0) >= 1)):
                                score = -1
                            else:
                                score = 21500
                                if op_is_mirror or op_is_fire_deck or op_is_crustle_deck:
                                    score = 21700
                                elif op_is_aggro_deck or op_is_beedrill_deck:
                                    score = 21700
                                elif op_is_greninja_deck or op_is_dragapult_dusknoir:
                                    score = 21600

                                if _forest_avail and hand_counts.get(Bayleef, 0) >= 1:
                                    score += 200
                    elif card.id == Applin:

                        _drag_snipe_charged = False
                        for _dp in (([op_state.active[0]]
                                     if (op_state.active and op_state.active[0] is not None)
                                     else [])
                                    + [b for b in op_state.bench if b is not None]):
                            if _dp.id == Dragapult_ex:
                                if (EnergyType.FIRE in _dp.energies and
                                        EnergyType.PSYCHIC in _dp.energies):
                                    _drag_snipe_charged = True
                                    break
                        _op_active_free_retreat = bool(
                            op_state.active and op_state.active[0] is not None and
                            (op_state.active[0].id == Budew or
                             RETREAT_COST.get(op_state.active[0].id, 1) == 0))
                        _dragapult_snipe_setup = _drag_snipe_charged and _op_active_free_retreat
                        _applin_evolvable_now = (
                            forest_in_play and hand_counts.get(Dipplin, 0) >= 1)

                        if bench_count >= 5:
                            score = -1
                        elif _dragapult_snipe_setup and not _applin_evolvable_now:
                            score = -1
                        elif (op_is_cubchoo_deck and
                                field_counts.get(Applin, 0) + field_counts.get(Dipplin, 0)
                                + field_counts.get(Hydrapple_ex, 0) >= 1):
                            # Matchup Cubchoo (user): solo UNA linea
                            # Applin->Dipplin->Hydrapple ex en juego a la vez. Si ya
                            # hay un miembro de la linea en mesa, no bajar otro Applin.
                            score = -1
                        else:
                            _forest_avail = forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1

                            if (op_has_mega_starmie_active and
                                    not (_forest_avail and hand_counts.get(Dipplin, 0) >= 1)):
                                score = -1
                            else:
                                score = 21200

                                if field_counts[Applin] >= 1:
                                    score = 20800

                                if _forest_avail and hand_counts.get(Dipplin, 0) >= 1:
                                    score += 200

                                if (op_is_fire_deck or op_is_aggro_deck) and not has_hydrapple:
                                    score += 300

                                if op_bench_snipe_threat and not _forest_avail:
                                    if field_counts[Applin] + field_counts[Dipplin] + field_counts[Hydrapple_ex] >= 1:
                                        score = 18000

                                    elif hand_counts.get(Dipplin, 0) == 0:
                                        score -= 500
                    elif card.id == Teal_Mask_Ogerpon_ex:
                        _meg_line_present = (
                            meganium_in_play or
                            field_counts.get(Bayleef, 0) >= 1 or
                            field_counts.get(Chikorita, 0) >= 1)
                        if (op_is_crustle_deck or op_is_cornerstone_deck) and \
                                not op_has_mega_kangaskhan and \
                                field_counts[card.id] >= 2:

                            score = -1
                        elif bench_count >= 5:
                            score = -1
                        elif field_counts[card.id] >= 2:

                            if hand_counts.get(Basic_Grass_Energy, 0) >= 1:
                                score = 20500
                            elif op_has_mega_kangaskhan and _meg_line_present:

                                score = 20500
                            else:
                                score = -1
                        else:
                            score = 21000
                    elif card.id == Meowth_ex:

                        if watchtower_in_play:
                            # Team Rocket's Watchtower anula la habilidad de
                            # Meowth ex (Pokemon incoloro): no bajarlo a la banca.
                            score = -1
                        elif ((_win_via_boss_gust or _gust_2prize_via_boss)
                                and hand_counts.get(Boss_Orders, 0) == 0
                                and CARTAS_ACTIVAS_EN_MAZO.get(Boss_Orders, {}).get(ESTADO_MAZO, 0) > 0
                                and field_counts[card.id] == 0
                                and bench_count < 5):

                            score = 22500
                        elif (_active_ready_attacker
                                and field_counts[card.id] == 0
                                and bench_count < 5
                                and not state.supporterPlayed
                                and hand_counts.get(Lillie_Determination, 0) == 0
                                and CARTAS_ACTIVAS_EN_MAZO.get(
                                    Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0
                                and (len(my_state.hand) if my_state.hand else 0) <= 4
                                and _ready_attacker_count <= 2
                                and not (plan.attacker == 0
                                         and plan.remain_hp is not None
                                         and plan.remain_hp <= 0)
                                and not watchtower_in_play
                                and (not op_has_froslass
                                     or _ready_attacker_count <= 1)):
                            # Regla (user, logs 86592502 turno 9 vs Archaludon ex,
                            # 86593647 turno 4 vs Mega Starmie ex y 86699707 paso 51
                            # vs Marnie's Grimmsnarl ex, todas PERDIDAS):
                            # EXCEPCION al veto de abajo. Aunque el activo YA pueda
                            # atacar, si la MANO es DEBIL (<=4 cartas) y aun queda una
                            # Lillie's Determination en el MAZO, bajar Meowth ex para
                            # que su habilidad Last-Ditch Catch traiga Lillie's y
                            # jugarla (baraja la mano y roba 6) da MUCHAS mas opciones
                            # de juego y ataque que jugar un cuerpo REDUNDANTE (2o
                            # Teal Mask Ogerpon ex, 21000) o lanzar un ataque DEBIL no
                            # letal (Dipplin ~1100) vs un muro de 330 HP. Se exige que
                            # haya un atacante listo pero POCOS (<=2: si ya hay muchos
                            # listos no hace falta refrescar), que el ataque del activo
                            # NO sea letal (si noquea, se ataca y se cobra el premio),
                            # que no se haya jugado Supporter y que no este anulada su
                            # habilidad (Watchtower siempre veta). Froslass tambien
                            # veta EXCEPTO cuando nuestro UNICO atacante listo es el
                            # propio activo (_ready_attacker_count <= 1) y su ataque
                            # NO es letal: ahi no hay presion real (un chip vs el muro)
                            # y cavar por Lillie's vale mas que el riesgo de banquear
                            # Meowth ex ante Froslass (caso 86699707: activo Dipplin
                            # chip vs Grimmsnarl ex 320 HP). Supera al cuerpo
                            # redundante (21500 > 21000) para que Meowth ex gane.
                            score = 21500
                        elif (_active_ready_attacker
                                and field_counts[card.id] == 0):
                            # Regla (user, log 86511741 paso 57, vs Mega Abomasnow
                            # ex, PERDIDA): si nuestro ACTIVO ya es un atacante
                            # LISTO para atacar este turno, NO bajamos Meowth ex
                            # solo para buscar un Supporter. Es un cuerpo de 2
                            # premios y no necesitamos partidario: preferimos
                            # desarrollar con Ultra Ball/Dawn (p.ej. buscar Teal
                            # Mask Ogerpon ex y acelerar energia con Teal Dance) o
                            # atacar directamente. La gustada LETAL con Boss's ya se
                            # resolvio en la rama anterior (_win_via_boss_gust).
                            score = -1
                        elif (hand_counts.get(Lillie_Determination, 0) >= 1
                                and field_counts[card.id] == 0):
                            # Regla (user): si YA tenemos Lillie's Determination EN
                            # LA MANO, NO se juega Meowth ex en NINGUN turno; se
                            # despliega el resto y se juega Lillie's. Bajar Meowth ex
                            # solo malgastaria un cuerpo de 2 premios y su busqueda
                            # de Supporter, porque Lillie's baraja TODA la mano en el
                            # mazo -> la carta buscada se perderia. La gustada LETAL
                            # con Boss's se maneja antes (rama _win_via_boss_gust).
                            # Si Lillie's NO esta en la mano pero SI en el mazo, este
                            # veto NO aplica: se deja pasar a `_meowth_devel_lillie`
                            # para bajar Meowth ex, BUSCAR Lillie's y jugarla.
                            score = -1
                        elif (_bcs_playable_in_hand
                                and hand_counts.get(Lillie_Determination, 0) >= 1
                                and field_counts[card.id] == 0
                                and not (_win_via_boss_gust or _gust_2prize_via_boss)):

                            score = -1
                        elif (_meowth_devel_lillie
                                and hand_counts.get(Meowth_ex, 0) >= 1
                                and hand_counts.get(Lillie_Determination, 0) == 0
                                and CARTAS_ACTIVAS_EN_MAZO.get(Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0
                                and field_counts[card.id] == 0
                                and bench_count < 5):

                            score = 21800
                        elif _bcs_playable_in_hand and bench_count >= 1:

                            score = -1
                        elif (field_counts[card.id] == 1
                                and bench_count < 5
                                and _active_cant_attack_this_turn
                                and not state.supporterPlayed
                                and hand_counts.get(Lillie_Determination, 0) == 0
                                and CARTAS_ACTIVAS_EN_MAZO.get(
                                    Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0
                                and not op_has_froslass
                                and not (state.turn == 1 and we_go_first)):

                            score = 21700
                        elif field_counts[card.id] >= 1:
                            score = -1
                        elif bench_count >= 5:
                            score = -1
                        elif (hand_counts.get(Unfair_Stamp, 0) >= 1 and ko_last_turn):

                            score = -1
                        elif state.turn == 1 and we_go_first:

                            _other_basics_in_hand = any(
                                hand_counts.get(pid, 0) >= 1
                                for pid in (Chikorita, Applin, Teal_Mask_Ogerpon_ex,
                                            Tapu_Bulu, Fezandipiti_ex, Pinsir))
                            if bench_count == 0 and not _other_basics_in_hand:
                                score = 19000
                            else:
                                score = -1
                        elif state.turn == 2 and not we_go_first:

                            if (not state.supporterPlayed and
                                    _best_supp_in_hand_val < 500 and
                                    _best_supp_in_mazo_id == Lillie_Determination and
                                    _best_supp_in_mazo_val >= 650):
                                score = 20500
                            else:
                                score = -1
                        elif state.supporterPlayed:
                            score = -1
                        elif op_has_froslass:
                            # Normalmente NO se banca Meowth ex (2 premios) contra
                            # Froslass (pinga la banca). EXCEPCION (user, registro_008
                            # paso 84, vs Marnie/Froslass, PERDIDA): en un TURNO
                            # MUERTO -- el activo no puede ATACAR ni RETIRARSE (0
                            # energia < coste de retirada), no hay atacante de banca
                            # que subir y no hay cartas en mano para habilitar un
                            # ataque -- con hueco en banca y el motor de refresco en
                            # el MAZO (Meowth ex -> Last-Ditch Catch busca Lana's Aid
                            # o Lillie's Determination), bajar Meowth ex es la UNICA
                            # jugada util: recuperar 3 energias del descarte (Lana's
                            # Aid) o refrescar la mano (Lillie's) abre opciones de
                            # ataque los proximos turnos. La eleccion Lana's/Lillie's
                            # la resuelve la busqueda del Supporter.
                            _mw_act_reloc = my_state.active[0] if my_state.active else None
                            _mw_can_retreat = (
                                _mw_act_reloc is not None
                                and len(_mw_act_reloc.energies)
                                >= RETREAT_COST.get(_mw_act_reloc.id, 1))
                            _mw_engine_in_mazo = (
                                CARTAS_ACTIVAS_EN_MAZO.get(
                                    Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0
                                or CARTAS_ACTIVAS_EN_MAZO.get(
                                    Lanas_Aid, {}).get(ESTADO_MAZO, 0) > 0)
                            if (_active_cant_attack_this_turn
                                    and not _mw_can_retreat
                                    and field_counts[card.id] == 0
                                    and bench_count < 5
                                    and not state.supporterPlayed
                                    and hand_counts.get(Lillie_Determination, 0) == 0
                                    and _mw_engine_in_mazo):
                                score = 21600
                            else:
                                score = -1
                        elif (_active_cant_attack_this_turn and
                              not state.supporterPlayed and
                              hand_counts.get(Lillie_Determination, 0) == 0 and
                              CARTAS_ACTIVAS_EN_MAZO.get(Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0):

                            score = 21800
                        elif (bench_count >= 1 and
                              hand_counts.get(Lillie_Determination, 0) >= 1 and
                              hand_counts.get(Ultra_Ball, 0) >= 1 and
                              not (op_is_crustle_deck or op_is_drednaw_deck or op_is_sylveon_deck) and
                              not (_best_supp_in_mazo_id == Boss_Orders and _best_supp_in_mazo_val >= 650)):

                            score = -1
                        elif _best_supp_in_hand_val >= 500:

                            _boss_in_mazo = CARTAS_ACTIVAS_EN_MAZO.get(Boss_Orders, {}).get(ESTADO_MAZO, 0) > 0
                            _boss_val = _supp_values.get(Boss_Orders, 0)
                            if op_is_crustle_deck and _boss_in_mazo and _boss_val >= 900 and hand_counts.get(Boss_Orders, 0) == 0:
                                score = 21500
                            elif (op_is_drednaw_deck and _boss_in_mazo and _boss_val >= 650
                                  and hand_counts.get(Boss_Orders, 0) == 0):

                                score = 21500
                            elif (op_is_sylveon_deck and _boss_in_mazo and _boss_val >= 650
                                  and hand_counts.get(Boss_Orders, 0) == 0):

                                score = 21500
                            else:
                                score = -1
                        else:

                            _meowth_score = -1
                            _target_id = _best_supp_in_mazo_id
                            _target_val = _best_supp_in_mazo_val

                            if _target_id == Boss_Orders and _target_val >= 650:

                                _meowth_score = 21000
                            elif _target_id == Lillie_Determination and _target_val >= 650:

                                _ATK_REQS_MEOWTH = {
                                    Hydrapple_ex: 2, Dipplin: 1, Teal_Mask_Ogerpon_ex: 3,
                                    Tapu_Bulu: 4, Meganium: 4, Fezandipiti_ex: 3,
                                    Pinsir: 2,
                                }
                                _ready_attackers = 0

                                _m_act = my_state.active[0] if my_state.active else None
                                if _m_act is not None and _m_act.id in _ATK_REQS_MEOWTH:
                                    _m_eff = len(_m_act.energies) * _grass_mult()
                                    if _m_eff >= _ATK_REQS_MEOWTH[_m_act.id]:
                                        _ready_attackers += 1

                                for _m_bp in my_state.bench:
                                    if _m_bp is not None and _m_bp.id in _ATK_REQS_MEOWTH:
                                        _m_bp_eff = len(_m_bp.energies) * _grass_mult()
                                        if _m_bp_eff >= _ATK_REQS_MEOWTH[_m_bp.id]:
                                            _ready_attackers += 1

                                _m_hand_size = len(my_state.hand) if my_state.hand else 0
                                if _ready_attackers <= 2 and _m_hand_size < 4:
                                    _meowth_score = 20500

                            elif _target_id == Dawn and _target_val >= 700:

                                _forest_avail = forest_in_play or hand_counts.get(Forest_of_Vitality, 0) >= 1
                                if _forest_avail:
                                    _meowth_score = 20500
                            elif _target_id == Lanas_Aid and _target_val >= 600:

                                _meowth_score = 20000

                            score = _meowth_score
                    elif card.id == Fezandipiti_ex:

                        # Con Lillie's Determination + Teal Mask Ogerpon ex +
                        # energia de Planta en la mano, la jugada correcta es bajar
                        # Teal (futuro atacante), usar Teal Dance y despues jugar
                        # Lillie's Determination para refrescar la mano. La habilidad
                        # de Fezandipiti (Flip the Script) solo roba hasta 3 cartas,
                        # asi que con la mano cargada no aporta y gastaria el turno /
                        # la banca en un no-atacante. Dejamos que Teal (21000) gane.
                        _fez_prefer_teal_lillie = (
                            hand_counts.get(Lillie_Determination, 0) >= 1
                            and not state.supporterPlayed
                            and hand_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1
                            and field_counts[Teal_Mask_Ogerpon_ex] < 2
                            and hand_counts.get(Basic_Grass_Energy, 0) >= 1
                            and bench_count < 5)

                        if _fez_prefer_teal_lillie:

                            score = -1
                        elif field_counts[card.id] >= 1:
                            score = -1
                        elif bench_count >= 5:
                            score = -1
                        elif (op_is_lucario_deck or op_is_crustle_deck
                              or op_is_cornerstone_deck or op_is_sylveon_deck):
                            # Contra Mega Lucario (Lucha), Crustle, Cornerstone
                            # Ogerpon y Sylveon: Fezandipiti ex vale 2 premios y su
                            # habilidad Flip the Script solo sirve tras ser noqueado.
                            # NO lo bajamos por desarrollo al comienzo de la partida.
                            # Si la habilidad esta viva (ko_last_turn) se conserva la
                            # ruta normal. Si no, esperamos al final del turno y solo
                            # lo bajamos como ULTIMO recurso cuando la banca esta
                            # VACIA: sin banca, un KO a nuestro activo el proximo
                            # turno = derrota. Con score bajo (500) cualquier
                            # desarrollo real (basico ~20000) se juega antes; Fez solo
                            # cae si no queda otra forma de tener un cuerpo en juego.
                            if ko_last_turn:
                                score = 22000
                                if len(my_state.hand) <= 3:
                                    score = 22500
                            elif bench_count == 0:
                                score = 500
                            else:
                                score = -1
                        elif state.turn == 1:

                            if bench_count == 1:
                                score = 15000
                            else:
                                score = -1
                        else:
                            fez_score = -1

                            if ko_last_turn:
                                fez_score = 22000

                                if len(my_state.hand) <= 3:
                                    fez_score = 22500

                            if not ko_last_turn and bench_count <= 2:
                                _all_bench_basics = True
                                for _bp_fez in my_state.bench:
                                    if _bp_fez is not None:
                                        _bp_fez_data = card_table.get(_bp_fez.id)
                                        if _bp_fez_data and (getattr(_bp_fez_data, 'stage1', False) or
                                                             getattr(_bp_fez_data, 'stage2', False)):
                                            _all_bench_basics = False
                                            break
                                # Contra Mega Lucario (tipo Lucha) NO bajamos
                                # Fezandipiti ex solo por "desarrollo": es debil a
                                # Lucha ({F}) y vale 2 premios, y su habilidad Flip
                                # the Script esta muerta si no nos noquearon el
                                # turno anterior. Bajarlo asi solo regala un KO de
                                # 2 premios facil. Con la habilidad viva
                                # (ko_last_turn) se conserva la ruta de 22000.
                                if _all_bench_basics and not op_is_lucario_deck:
                                    fez_score = max(fez_score, 15000)

                            score = fez_score
                    elif card.id == Tapu_Bulu:

                        _tapu_first_turn = (state.turn <= 2)
                        _tapu_in_play_count = (
                            (1 if (my_state.active and my_state.active[0] is not None) else 0)
                            + bench_count)

                        _op_is_crustle_like = (
                            op_is_crustle_deck or op_has_ability_immune_active or
                            op_is_cornerstone_deck or op_is_sylveon_deck or
                            op_has_ex_immune_active or op_has_ex_immune_bench)

                        if field_counts[card.id] >= 1:
                            score = -1
                        elif (_tapu_in_play_count >= 4 and not _op_is_crustle_like and
                              meganium_in_play and not _tapu_first_turn):

                            score = 16000
                        elif _tapu_in_play_count > 2 and not op_is_crustle_deck:

                            score = -1
                        elif op_is_crustle_deck:

                            score = 22000
                            if meganium_in_play:
                                score = 22500
                        elif op_has_ability_immune_active or op_is_cornerstone_deck:

                            score = 22500
                        elif op_is_sylveon_deck:

                            score = 22000
                        elif op_has_ex_immune_active or op_has_ex_immune_bench:

                            score = 21000
                            if has_hydrapple:
                                score = 22000
                        elif (_lucario_sac_pivot and bench_count < 5
                                and (_tapu_sac_priority
                                     or not _lucario_other_sac_available)):

                            # Bajar Tapu Bulu vs Mega Lucario solo cuando es el
                            # sacrificio prioritario (rival con proteccion a ex o
                            # motor Hydrapple ex + Meganium) o cuando no hay otro
                            # basico de 1 premio (Applin / Chikorita) disponible.
                            # Si hay alternativa desechable, conservamos Tapu Bulu.
                            score = 21500
                        elif _tapu_first_turn:

                            score = -1
                        elif not meganium_in_play:

                            score = -1
                        else:

                            score = 16000

                        # Tapu Bulu solo se baja despues de jugar todos los items
                        # ("artefactos") que el juego considere jugar. Si aun queda
                        # algun item en la mano, rebajamos la prioridad de Tapu Bulu
                        # por debajo de la banda de items utiles: los items que valen
                        # la pena (puntaje mas alto) se juegan primero y, cuando solo
                        # queden items sin valor (puntaje bajo), Tapu Bulu vuelve a
                        # ganar y se baja. Aplica SOLO a Tapu Bulu.
                        _tapu_items_pending = any(
                            hand_counts.get(_it_id, 0) >= 1 for _it_id in DECK_ITEM_IDS)
                        if _tapu_items_pending and score > TAPU_WAIT_FOR_ITEMS_SCORE:
                            score = TAPU_WAIT_FOR_ITEMS_SCORE
                    elif card.id == Pinsir:

                        score = -1

                    if (_poke_pad_target_id > 0 and card.id == _poke_pad_target_id and
                            bench_count < 5):
                        if score <= 0:
                            score = 21000

                    if (_ub_meowth_pending and card.id == Meowth_ex and
                            field_counts[Meowth_ex] == 0 and bench_count < 5
                            and not _active_ready_attacker):
                        # `_ub_meowth_pending` (una Ultra Ball previa trajo Meowth ex)
                        # fuerza bajarlo para encadenar Last-Ditch Catch -> Lillie's y
                        # REFRESCAR la mano. Pero Meowth ex solo se justifica cuando NO
                        # tenemos con que atacar: si el ACTIVO ya es un atacante listo,
                        # bajar un cuerpo de 2 premios para buscar un Supporter (a menudo
                        # ni jugable: Supporter ya jugado este turno) es redundante y no
                        # aporta ataque. En ese caso NO se anula el veto de arriba (rama
                        # `_active_ready_attacker` -> -1) y se ataca (registro 006,
                        # paso 57 vs Alakazam, GANADA pero jugada innecesaria). La
                        # excepcion legitima (mano debil + Lillie's en mazo + activo
                        # listo) ya la puntua la rama ~8875 con 21500 (score > 0), asi
                        # que esta guarda no la afecta.
                        if score <= 0:
                            score = 21000

                    # Matchup Cubchoo (user, cambio 5): la banca SOLO puede tener,
                    # vs este mazo, la linea de Hydrapple ex (Applin/Dipplin/
                    # Hydrapple ex, una), la linea de Meganium (Chikorita/Bayleef/
                    # Meganium, una), hasta DOS Teal Mask Ogerpon ex y UN Meowth ex
                    # (solo cuando haga falta para BUSCAR una Lillie's Determination
                    # del mazo). El resto de Pokemon (Tapu Bulu, Fezandipiti ex,
                    # Pinsir...) NO se juega. Se aplica tras las excepciones de
                    # poke_pad/ub_meowth y ANTES del fallback de banca vacia (mas
                    # abajo), que sigue garantizando que nunca nos quedemos sin
                    # Pokemon en juego (jugada legal forzada).
                    if op_is_cubchoo_deck:
                        _CUB_ALLOWED_PLAY = (
                            Applin, Dipplin, Hydrapple_ex,
                            Chikorita, Bayleef, Meganium,
                            Teal_Mask_Ogerpon_ex, Meowth_ex)
                        if card.id not in _CUB_ALLOWED_PLAY:
                            score = -1
                        elif (card.id == Teal_Mask_Ogerpon_ex
                                and field_counts[card.id] >= 2):
                            # No mas de dos Teal Mask Ogerpon ex en juego.
                            score = -1
                        elif card.id == Meowth_ex:
                            # Un solo Meowth ex y solo si hay una Lillie's
                            # Determination que buscar en el mazo (no ya en mano).
                            _cub_meowth_ok = (
                                field_counts[Meowth_ex] == 0
                                and hand_counts.get(Lillie_Determination, 0) == 0
                                and CARTAS_ACTIVAS_EN_MAZO.get(
                                    Lillie_Determination, {}).get(ESTADO_MAZO, 0) > 0)
                            if not _cub_meowth_ok:
                                score = -1

                    # Req H: vs Mega Lucario con un Riolu gusteable+noqueable en
                    # la banca rival y banca propia establecida, NO desarrollar
                    # ni refrescar la mano: cedemos la jugada a Boss's Orders
                    # (gustear + noquear al Riolu para cortar su linea). Vetamos
                    # el desarrollo de CUALQUIER Pokemon (tier DEVELOP) para que
                    # Boss's (supporter, tier 0) sea la jugada elegida. El flag
                    # exige bench_count>=2, asi que el rescate anti-softlock de
                    # mas abajo (banca vacia) nunca entra en conflicto.
                    if _lucario_riolu_gust:
                        score = -1

                    # Rescate anti-softlock: con la banca vacia, subir un basico
                    # que quedo en <=0 para poder desplegarlo (jugada legal).
                    # EXCEPCION: en nuestro primer turno, con una Lillie's
                    # Determination jugable en mano, NO forzamos a Meowth ex a la
                    # banca (respetamos el veto: se despliega el resto y se juega
                    # Lillie's; si tras jugar Lillie's sigue sin haber banca,
                    # supporterPlayed pasa a True y este rescate se rehabilita para
                    # bajar Meowth ex como ultimo recurso). Esto aplica AUNQUE ya
                    # tengamos un Meowth ex en juego (p.ej. como activo): bajar un
                    # SEGUNDO Meowth ex es aun mas inutil (su busqueda de Supporter
                    # se baraja con Lillie's y expone otro cuerpo de 2 premios).
                    _meowth_first_turn_hold = (
                        card.id == Meowth_ex
                        and _our_first_turn
                        and hand_counts.get(Lillie_Determination, 0) >= 1
                        and not state.supporterPlayed)
                    if (bench_count == 0 and score <= 0
                            and not _meowth_first_turn_hold and
                            not (getattr(data, 'stage1', False) or
                                 getattr(data, 'stage2', False))):
                        if card.id in OUR_EX_IDS:
                            score = 80
                        else:
                            score = 150

                    _dip_act = my_state.active[0] if my_state.active else None
                    if (_dip_act is not None and _dip_act.id == Dipplin
                            and bench_count < 5
                            and card.id not in OUR_EX_IDS
                            and not (getattr(data, 'stage1', False) or
                                     getattr(data, 'stage2', False))
                            and op_state.active and op_state.active[0] is not None):
                        _dip_can_attack = (
                            len(_dip_act.energies) >= 1
                            or (hand_counts.get(Basic_Grass_Energy, 0) >= 1
                                and not state.energyAttached))
                        if _dip_can_attack:
                            _dip_op_act = op_state.active[0]
                            _dip_op_hp = _dip_op_act.hp or 0
                            _dwave_now = 20 * bench_count
                            _dwave_boost = 20 * (bench_count + 1)
                            _dip_td = card_table.get(_dip_op_act.id)
                            if _dip_td is not None:
                                if _dip_td.weakness == EnergyType.GRASS:
                                    _dwave_now *= 2
                                    _dwave_boost *= 2
                                elif _dip_td.resistance == EnergyType.GRASS:
                                    _dwave_now -= 30
                                    _dwave_boost -= 30
                            _dip_ko_now = (_dwave_now >= _dip_op_hp and _dwave_now > 0)
                            _dip_ko_boost = (_dwave_boost >= _dip_op_hp and _dwave_boost > 0)
                            if _dip_ko_boost and not _dip_ko_now:

                                score = max(score, 21900)

                    if card.id == Meowth_ex:
                        _meowth_played_this_turn = (
                            field_counts[Meowth_ex] >
                            _field_at_turn_start.get(Meowth_ex, 0)
                            if _field_at_turn_start is not None else False)
                        if watchtower_in_play:
                            # Team Rocket's Watchtower anula la habilidad de los
                            # Pokemon {C}: bajar Meowth ex ahora NO activaria
                            # Last-Ditch Catch (no busca Supporter). No lo jugamos
                            # hasta reemplazar el estadio (p.ej. con Forest).
                            score = -1
                        elif _meowth_played_this_turn:
                            score = -1
                        elif field_counts[Meowth_ex] >= 2:
                            score = -1
                        elif field_counts[Meowth_ex] >= 1 and score <= 0:
                            score = -1

                    # Estrategia vs Comfey (user, registro_005): SOLO bajar Teal
                    # Mask Ogerpon ex, MAXIMO 2 en juego, y nada mas. Es el mejor
                    # atacante del matchup (facil de cargar y de retirar cuando lo
                    # confunde Brambleghast). EXCEPCION de ARRANQUE: si no tenemos
                    # ningun Ogerpon ex en juego NI en la mano y aun no hay ningun
                    # cuerpo en juego (banca+activo vacios), bajamos un starter con
                    # prioridad Applin > Chikorita > cualquiera para poder partir.
                    if op_is_comfey_deck:
                        _cf_og_field = field_counts.get(Teal_Mask_Ogerpon_ex, 0)
                        _cf_og_hand = hand_counts.get(Teal_Mask_Ogerpon_ex, 0)
                        if card.id == Teal_Mask_Ogerpon_ex:
                            score = 22000 if _cf_og_field < 2 else -1
                        else:
                            _cf_has_body = (
                                bench_count >= 1
                                or (my_state.active and my_state.active[0] is not None))
                            _cf_need_starter = (
                                _cf_og_field == 0 and _cf_og_hand == 0
                                and not _cf_has_body)
                            if _cf_need_starter:
                                if card.id == Applin:
                                    score = 21000
                                elif card.id == Chikorita:
                                    score = 20500
                                else:
                                    score = 20000
                            else:
                                score = -1

                else:
                    score = 10000

                    supporter_boost = 500 if itchy_pollen_active else 0
                    if card.id == Forest_of_Vitality:
                        # Refactor Prioridad 1: rama extraida a `_score_forest_of_vitality_play`.
                        score = _score_forest_of_vitality_play(ctx)
                    elif card.id == Bug_Catching_Set:
                        # Refactor Prioridad 1: rama extraida a `_score_bug_catching_set_play`.
                        score = _score_bug_catching_set_play(ctx)
                    elif card.id == Ultra_Ball:
                        # Refactor Prioridad 1 (Paso 1): rama extraida a `_score_ultra_ball_play`.
                        score = _score_ultra_ball_play(ctx)
                    elif card.id == Night_Stretcher:
                        # Refactor Prioridad 1: rama extraida a `_score_night_stretcher_play`.
                        score = _score_night_stretcher_play(ctx)
                    elif card.id == Poke_Pad:
                        # Refactor Prioridad 1: rama extraida a `_score_poke_pad_play`.
                        score = _score_poke_pad_play(ctx)
                    elif card.id == Unfair_Stamp:
                        # Refactor Prioridad 1: rama extraida a `_score_unfair_stamp_play`.
                        score = _score_unfair_stamp_play(ctx)
                    elif card.id == Boss_Orders:
                        # Refactor Prioridad 1: rama extraida a `_score_boss_orders_play`.
                        score = _score_boss_orders_play(ctx)
                    elif card.id == Lillie_Determination:
                        # Refactor Prioridad 1: rama extraida a `_score_lillie_determination_play`.
                        score = _score_lillie_determination_play(ctx)
                    elif card.id == Dawn:
                        if state.supporterPlayed:
                            score = -1
                        elif ko_last_turn and hand_counts.get(Unfair_Stamp, 0) >= 1:
                            score = -1
                        else:
                            _dawn_val = _supp_values.get(Dawn, 0)
                            if _dawn_val <= 0:
                                score = -1
                            else:
                                score = 2400 + int(_dawn_val * 1.4) + supporter_boost
                    elif card.id == Lanas_Aid:
                        # Refactor Prioridad 1: rama extraida a `_score_lanas_aid_play`.
                        score = _score_lanas_aid_play(ctx, score)

                    # Estrategia vs Comfey (user, registro_005): las UNICAS cartas de
                    # ENTRENADOR que se juegan son Lillie's Determination, Lana's Aid
                    # y Boss's Orders (supporters), mas Ultra Ball y Night Stretcher
                    # (items del plan, Regla 5). El resto -Dawn, Unfair Stamp, otros
                    # items y estadios- NO se juegan: se descartan/ignoran (-1). Las
                    # reglas propias de Lillie's (mano>=10) y Lana's (>=2 energias) ya
                    # se aplicaron arriba; aqui solo se veta lo que NO esta en la lista.
                    if (op_is_comfey_deck and score > 0
                            and card.id not in (
                                Lillie_Determination, Lanas_Aid, Boss_Orders,
                                Ultra_Ball, Night_Stretcher)):
                        score = -1
        elif o.type == OptionType.ATTACH:
            card = get_card(obs, AreaType.HAND, o.index, my_index)
            pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
            if card is not None and pokemon is not None:
                score = energy_score(pokemon, o.inPlayArea == AreaType.ACTIVE)
                if o.inPlayArea == AreaType.ACTIVE:

                    if (((state.turn == 1 and we_go_first) or
                            (state.turn == 2 and not we_go_first))
                            and my_state.active and my_state.active[0] is not None
                            and my_state.active[0].id in (Teal_Mask_Ogerpon_ex, Tapu_Bulu)):
                        if _lucario_sac_pivot:
                            # Cargar el Ogerpon ex activo: al retirarlo despues,
                            # conservara energia en la banca (paga el coste de
                            # retirada y deja un atacante cargado a salvo).
                            score = 8500
                        else:
                            score = -1
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
                    elif plan.attacker == 0 and plan.energy:
                        score += 200

                    elif (plan.attacker >= 1 and has_ogerpon and score > 31000
                            and not op_is_crustle_deck and not op_is_cornerstone_deck):

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
                    if plan.attacker == 1 + o.inPlayIndex and plan.energy:
                        score += 200

                    _our_first_turn_attach = ((state.turn == 1 and we_go_first) or
                                              (state.turn == 2 and not we_go_first))
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
                        score = -1

                if _bcs_playable_in_hand and not itchy_pollen_active and score > 9000 \
                        and not (_tapu_future_charge
                                 and o.inPlayArea != AreaType.ACTIVE
                                 and pokemon is not None
                                 and pokemon.id == Tapu_Bulu):
                    score = 9000

                if _teal_dance_ko_pivot and hand_counts.get(Basic_Grass_Energy, 0) <= 1:
                    # Pivote Teal Dance (log 85802744 turno 16): con una
                    # sola Energia Planta en mano, RESERVARLA para Teal Dance en
                    # el activo (adjunta + ROBA y habilita la retirada de coste 1
                    # para subir al atacante no-ex que noquea al muro Crustle). Se
                    # veta cualquier adjunte manual para que no robe la Planta ni
                    # supere a Teal Dance por el tier ENERGY del orden de jugada.
                    score = -1

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
                    score = -1

        elif o.type == OptionType.EVOLVE:
            pokemon = get_card(obs, o.inPlayArea, o.inPlayIndex, my_index)
            card = get_card(obs, AreaType.HAND, o.index, my_index)
            if card is not None and pokemon is not None:
                _is_active = (o.inPlayArea == AreaType.ACTIVE)
                _pkmn_energy = len(pokemon.energies)
                _has_energy_in_hand = (hand_counts.get(Basic_Grass_Energy, 0) >= 1 and not state.energyAttached)

                score = 9000 + _pkmn_energy

                if card.id == Meganium:
                    score = 35000
                    if op_is_fire_deck or op_is_mirror or op_is_crustle_deck:
                        score = 35500

                    if pokemon.id == Chikorita:
                        score += 500

                elif card.id == Hydrapple_ex:
                    score = 33000

                    if op_is_crustle_deck and op_kang_ko_target:

                        score = 34500
                    elif op_is_crustle_deck and op_active_is_kangaskhan:

                        score = 33000
                    elif op_is_crustle_deck:
                        score = -1
                    elif op_is_fire_deck:
                        score = 33500

                    elif op_is_drednaw_deck:
                        _other_dipplin_count = field_counts.get(Dipplin, 0)
                        _has_hydrapple_already = field_counts.get(Hydrapple_ex, 0) >= 1
                        if _has_hydrapple_already:

                            score = 22000
                        elif _other_dipplin_count >= 2:

                            score = 32500
                        elif _other_dipplin_count >= 1 and not _is_active:

                            score = 32000
                        else:

                            score = 22000

                    elif op_is_sylveon_deck and op_has_ex_immune_active:
                        _other_dipplin_count = field_counts.get(Dipplin, 0)
                        _has_hydrapple_already = field_counts.get(Hydrapple_ex, 0) >= 1

                        _tapu_ready_sv = any(
                            bp is not None and bp.id == Tapu_Bulu and
                            len(bp.energies) * _grass_mult() >= 4
                            for bp in list(my_state.active or []) + list(my_state.bench))
                        if _tapu_ready_sv:
                            score = 32500
                        elif _has_hydrapple_already:
                            score = 22000
                        elif _other_dipplin_count >= 2:
                            score = 32500
                        elif _other_dipplin_count >= 1 and not _is_active:
                            score = 32000
                        else:
                            score = 22000

                    if pokemon.id == Applin and not op_is_crustle_deck:
                        score += 500

                    # ── Regla: no malgastar un KO letal de Dipplin ──────────
                    # Si el activo es un Dipplin al que, cargandole 1 energia
                    # Grass este turno, "Do the Wave" (20 x banca) noquearia al
                    # Pokemon activo rival, PERO al evolucionar a Hydrapple ex NO
                    # podriamos noquear este turno (Syrup Storm exige 2 energias),
                    # NO evolucionamos: conservamos el Dipplin para atacar y
                    # llevarnos el KO. Reglas del usuario:
                    #   (1) Dipplin noquea y Hydrapple no -> NO evolucionar.
                    #   (2) Dipplin no noquea -> evolucionar con normalidad.
                    #   (3) sin energia disponible -> evolucionar (protege Dipplin).
                    if _is_active and pokemon.id == Dipplin:
                        _dip_can_attack_now = (_pkmn_energy >= 1 or _has_energy_in_hand)
                        if _dip_can_attack_now:
                            _op_act_evo = (op_state.active[0]
                                           if op_state.active and op_state.active[0] is not None
                                           else None)
                            if _op_act_evo is not None and (_op_act_evo.hp or 0) > 0:
                                _dip_dmg = _our_effective_damage(
                                    pokemon, _op_act_evo, 20 * bench_count,
                                    meganium_in_play, neutralization_zone_active)
                                _dip_kos = (_dip_dmg > 0 and _dip_dmg >= (_op_act_evo.hp or 0))
                                # Energia efectiva de Hydrapple ex tras evolucionar
                                # (hereda la energia del Dipplin + posible adjunto).
                                _hydra_eff = _pkmn_energy * _grass_mult()
                                if _has_energy_in_hand:
                                    _hydra_eff += _grass_attach_unit()
                                _hydra_kos = False
                                if _hydra_eff >= ATTACK_ENERGY_REQ[Hydrapple_ex]:
                                    _hydra_grass = total_grass + (1 if _has_energy_in_hand else 0)
                                    _hydra_dmg = _our_effective_damage(
                                        pokemon, _op_act_evo, 30 + 30 * _hydra_grass,
                                        meganium_in_play, neutralization_zone_active)
                                    _hydra_kos = (_hydra_dmg > 0 and _hydra_dmg >= (_op_act_evo.hp or 0))
                                if _dip_kos and not _hydra_kos:
                                    score = -1

                elif card.id == Bayleef:

                    if _is_active:
                        if has_condition and condition_blocks_action:

                            score = 34000 + condition_urgency
                        elif not can_switch:

                            score = 31300
                        else:
                            # Activo evolucionable (p.ej. Chikorita) que SI puede
                            # cambiar de activo. Por defecto NO se evoluciona en el
                            # activo (dejaria un Bayleef fragil arriba). Dos
                            # escenarios ajustan este veto:
                            _evo_active_rc = RETREAT_COST.get(pokemon.id, 1)
                            _evo_active_eff = _pkmn_energy * _grass_mult()
                            _evo_can_attach_now = (
                                hand_counts.get(Basic_Grass_Energy, 0) >= 1 and
                                not state.energyAttached)
                            _evo_eff_after_attach = _evo_active_eff + (
                                _grass_attach_unit() if _evo_can_attach_now else 0)
                            if _evo_active_eff >= _evo_active_rc:
                                # Escenario 1: ya tiene energia cargada para pagar
                                # la retirada -> conviene RETIRARLO primero y
                                # evolucionarlo ya en la banca. Se mantiene el veto;
                                # la logica de retiro sube un atacante de banca y el
                                # Chikorita evoluciona despues desde la banca.
                                score = -1
                            elif (hand_counts.get(Lillie_Determination, 0) >= 1
                                    and not state.supporterPlayed):
                                # Escenario 2: no puede pagar la retirada con su
                                # energia actual, pero tenemos Lillie's Determination
                                # en mano y podremos cargar energia despues de
                                # jugarla -> evolucionamos el activo a Bayleef ahora.
                                score = 31300
                            elif _evo_eff_after_attach >= _evo_active_rc:
                                # Escenario 1 (variante): se le puede cargar energia
                                # este turno para pagar la retirada -> retirar primero
                                # y evolucionar en banca. Se mantiene el veto.
                                score = -1
                            else:
                                score = -1
                    else:
                        score = 32000
                        if op_is_fire_deck or op_is_mirror or op_is_crustle_deck:
                            score = 32500
                        if op_is_cubchoo_deck:
                            # Cambio 4 (user): la linea de Meganium es la PRIORIDAD
                            # principal de evolucion vs Cubchoo, por delante de la
                            # linea de Hydrapple ex (Dipplin->Hydrapple = 33000).
                            # Meganium final ya vale 35000 (> este 34000).
                            score = 34000

                elif card.id == Dipplin:

                    if _pkmn_energy >= 1 or _has_energy_in_hand:
                        score = 31500
                        if op_has_ex_immune_active or op_has_ex_immune_bench:
                            if not has_hydrapple:
                                score = 32000

                        if op_is_drednaw_deck:
                            score = 33000

                        elif op_is_sylveon_deck:
                            score = 32500
                    else:

                        score = 25000
                        if op_is_drednaw_deck:
                            score = 31000
                        elif op_is_sylveon_deck:
                            score = 30500

                if _is_active and active_ko_likely and score > 0 and card.id != Meganium:
                    _evo_effective_energy = _pkmn_energy * _grass_mult()
                    if _has_energy_in_hand:
                        _evo_effective_energy += _grass_attach_unit()
                    _evo_can_attack = False
                    if card.id == Hydrapple_ex:
                        _evo_can_attack = (_evo_effective_energy >= 2)
                    elif card.id == Dipplin:
                        _evo_can_attack = (_pkmn_energy >= 1 or _has_energy_in_hand)
                    elif card.id == Bayleef:
                        _evo_can_attack = False

                    if not _evo_can_attack and not (has_condition and _is_active):
                        score = 8000

                    elif _evo_can_attack and card.id != Hydrapple_ex:

                        _evo_data = card_table.get(card.id)
                        _evo_max_hp = _evo_data.hp if (_evo_data and hasattr(_evo_data, 'hp')) else 0

                        _current_damage = pokemon.maxHp - pokemon.hp if hasattr(pokemon, 'maxHp') else 0
                        _evo_hp_after = _evo_max_hp - max(0, _current_damage)

                        _evo_op_damage = estimated_op_damage
                        if _evo_data:
                            _op_act = _active_of(op_state)
                            if _op_act is not None:
                                _op_act_data = card_table.get(_op_act.id)
                                if (_op_act_data and hasattr(_evo_data, 'weakness') and
                                        hasattr(_op_act_data, 'energyType') and
                                        _evo_data.weakness == _op_act_data.energyType):

                                    _base_op_dmg = 0
                                    if _op_act_data.attacks:
                                        for _atk in _op_act_data.attacks:
                                            if hasattr(_atk, 'damage') and _atk.damage is not None:
                                                _base_op_dmg = max(_base_op_dmg, _atk.damage)
                                    _evo_op_damage = _base_op_dmg * 2
                                elif (hasattr(_evo_data, 'weakness') and
                                      hasattr(_op_act_data, 'energyType') and
                                      _evo_data.weakness != _op_act_data.energyType):

                                    _base_op_dmg = 0
                                    if _op_act_data.attacks:
                                        for _atk in _op_act_data.attacks:
                                            if hasattr(_atk, 'damage') and _atk.damage is not None:
                                                _base_op_dmg = max(_base_op_dmg, _atk.damage)
                                    _evo_op_damage = _base_op_dmg

                        _evo_survives = (_evo_hp_after > _evo_op_damage)

                        if not _evo_survives:

                            _bench_has_same_preevo = False
                            for _bp in my_state.bench:
                                if _bp is not None and _bp.id == pokemon.id:
                                    _bench_has_same_preevo = True
                                    break

                            if _bench_has_same_preevo and not (has_condition and _is_active):

                                score = 8000

                if has_condition and _is_active and score > 0:
                    score += condition_urgency

        elif o.type == OptionType.ABILITY:
            card = get_card(obs, o.area, o.index, my_index)
            if card is not None:
                if card.id == Teal_Mask_Ogerpon_ex:

                    _ogerpon_energy = len(card.energies) if isinstance(card, Pokemon) else 0

                    _crustle_atk_needs_grass = False
                    if op_is_crustle_deck and hand_counts.get(Basic_Grass_Energy, 0) == 1:
                        for _cng in (list(my_state.active or []) + list(my_state.bench or [])):
                            if _cng is None:
                                continue
                            _cng_e = len(_cng.energies)
                            if ((_cng.id == Tapu_Bulu and _cng_e < 4) or
                                    (_cng.id == Dipplin and _cng_e < 1) or
                                    (_cng.id == Pinsir and _cng_e < 2)):
                                _crustle_atk_needs_grass = True
                                break

                    _td_ko_on_active = False
                    if (o.area == AreaType.ACTIVE
                            and op_state.active and op_state.active[0] is not None
                            and not op_has_ex_immune_active
                            and hand_counts.get(Basic_Grass_Energy, 0) >= 1):
                        _td_op_act = op_state.active[0]
                        _td_op_hp = _td_op_act.hp or 0
                        _td_eff_now = _ogerpon_energy
                        _td_eff_after = _ogerpon_energy + _grass_attach_unit()
                        # Ivy Bludgeon = 30 + 30 por Energia Planta PROPIA (no del
                        # objetivo). Se pasa por _our_effective_damage para aplicar
                        # debilidad Y RESISTENCIA correctamente (user, registro_012
                        # paso 93: Duraludon resiste -30 a Planta, asi que Teal
                        # Dance habilita el KO al pasar de 4 a >=5 energias
                        # efectivas). `card` es el propio Teal Mask Ogerpon ex.
                        _td_base_now = 30 + 30 * _td_eff_now if _td_eff_now >= 3 else 0
                        _td_base_after = 30 + 30 * _td_eff_after if _td_eff_after >= 3 else 0
                        _td_dmg_now = _our_effective_damage(
                            card, _td_op_act, _td_base_now,
                            meganium_in_play, neutralization_zone_active)
                        _td_dmg_after = _our_effective_damage(
                            card, _td_op_act, _td_base_after,
                            meganium_in_play, neutralization_zone_active)
                        _td_ko_now = (_td_dmg_now > 0 and _td_dmg_now >= _td_op_hp)
                        _td_ko_after = (_td_dmg_after > 0 and _td_dmg_after >= _td_op_hp)
                        _td_ko_on_active = (_td_ko_after and not _td_ko_now)
                    if hand_counts[Basic_Grass_Energy] < 1:
                        score = -1
                    elif _td_ko_on_active:

                        score = 31500
                    elif (op_is_cubchoo_deck and
                            _physical_energy(_ogerpon_energy)
                            >= (2 if meganium_in_play else 4)):
                        # Matchup Cubchoo (user): no sobrecargar al Ogerpon con
                        # Teal Dance mas alla del tope FISICO (2 con Meganium / 4
                        # sin). len(energies) viene DUPLICADO por Wild Growth con
                        # Meganium, por eso convertimos a cartas fisicas antes de
                        # comparar. No se necesita mas energia para atacar.
                        # Excepcion: si habilita un KO (arriba, _td_ko_on_active).
                        score = -1
                    elif (op_is_alakazam_deck
                            and _physical_energy(_ogerpon_energy)
                            >= (2 if meganium_in_play else 4)):
                        # Regla (user, vs Alakazam): tope de energia para Teal
                        # Mask Ogerpon ex via Teal Dance. Base FISICA = 4 sin
                        # Meganium / 2 con Meganium (Wild Growth duplica cada
                        # Planta). En BANCA es DURO; en el ACTIVO la 5a/3a energia
                        # solo se permite si HABILITA el KO, caso ya resuelto
                        # arriba por _td_ko_on_active (31500). Fuera de esa
                        # excepcion no sobrecargamos: reservamos energia.
                        # len(energies) es EFECTIVA => se pasa a cartas fisicas.
                        score = -1
                    elif _teal_wall_pivot and o.area == AreaType.ACTIVE:
                        # Activo condenado (Teal Mask Ogerpon ex) que no puede
                        # atacar + Hydrapple ex (muro) en banca: usar Teal Dance
                        # en el ACTIVO (adjunta Grass + ROBA 1) para habilitar su
                        # retirada (coste 1) y luego subir al cuerpo mas fuerte.
                        # Debe GANAR al adjunte manual (~31200) para aprovechar el
                        # robo y no malgastar la energia del turno.
                        score = 31600
                    elif _teal_dance_ko_pivot and o.area == AreaType.ACTIVE:
                        # Pivote Teal Dance -> retirar -> promover atacante letal
                        # (user, log 85802744 turno 16): activo Teal Mask Ogerpon
                        # ex bloqueado por el muro Crustle que aun no puede
                        # retirarse, con un atacante no-ex LISTO en banca (Tapu
                        # Bulu, 220 de dano) que noquea al muro. Teal Dance en el
                        # activo adjunta la Planta (+ROBA) y habilita la retirada
                        # de coste 1 para subir a Tapu y noquear el proximo paso.
                        # Debe GANAR al adjunte manual a Dipplin (~31000).
                        score = 31600
                    elif (op_is_crustle_deck and not op_kang_ko_target
                            and _physical_energy(_ogerpon_energy) >= 2):
                        # Regla (user, vs Crustle, log 86583376 paso 84): un Teal
                        # Mask Ogerpon ex no puede tener mas de DOS energias
                        # FISICAS cargadas via Teal Dance. Contra el muro Crustle
                        # (que inmuniza a nuestros ex) Ogerpon no ataca al muro,
                        # asi que reservamos energia y no lo sobrecargamos. La
                        # UNICA excepcion (Ogerpon ACTIVO cuya 3a energia habilita
                        # el KO del activo rival) ya se resolvio arriba con
                        # _td_ko_on_active (31500). Se conserva ademas el bypass
                        # op_kang_ko_target (KO de Mega Kangaskhan ex con Hydrapple
                        # ex, donde la energia extra sube el dano de Syrup Storm).
                        # len(energies) es EFECTIVA (Wild Growth duplica) => se
                        # pasa a cartas fisicas con _physical_energy.
                        score = -1
                    elif _crustle_atk_needs_grass:

                        score = 7500
                    elif _reserve_energy_for_hydra_evolve and o.area != AreaType.ACTIVE:

                        score = 7500
                    elif _ogerpon_energy >= 3:

                        if _extra_energy_enables_ko(Teal_Mask_Ogerpon_ex, _ogerpon_energy):
                            score = 29000
                        elif _active_already_kos and o.area != AreaType.ACTIVE:

                            score = 31050
                        elif (o.area == AreaType.ACTIVE and _bench_attacker_ready
                                and not _active_already_kos):

                            score = 31050
                        else:
                            score = -1
                    elif _active_hydra_ready:

                        score = 31300
                    elif (_active_needs_energy and not _enough_for_both and plan.attacker < 1
                            and not (
                                ((state.turn == 1 and we_go_first) or
                                 (state.turn == 2 and not we_go_first))
                                and o.area == AreaType.ACTIVE
                                and card.id in (Teal_Mask_Ogerpon_ex, Tapu_Bulu))):

                        score = 7500
                    elif _reserve_hydra_active_charge and o.area != AreaType.ACTIVE:

                        score = 7500
                    elif _hydrapple_bench_needs_energy and not _enough_after_priorities:

                        score = 7500
                    elif (o.area != AreaType.ACTIVE and
                            ((not _active_needs_energy) or _enough_for_both)):

                        score = 31500
                    else:

                        score = 31000
                elif card.id == Hydrapple_ex:

                    _hydra_energy = len(card.energies) if isinstance(card, Pokemon) else 0
                    # Guard (user, log 85848966 paso 76, GANADO vs Crustle): NO
                    # activar Ripening Charge si la Grass extra no tiene destino
                    # util. Ripening Charge (una vez activada) OBLIGA a adjuntar
                    # a algun Pokemon; si el activo es un Tapu Bulu YA cargado
                    # (>=4 efectivas) y en banca no hay ningun atacante que
                    # necesite energia (Tapu<4ef, Dipplin sin energia o
                    # Meganium<4ef), energy_score (ATTACH_FROM) devuelve -1 para
                    # TODAS las opciones -> el desempate elige la 1a (el ACTIVO)
                    # y se sobrecarga al Tapu ya listo, malgastando una carta de
                    # Grass de la mano (que con Meganium sirve para retiradas /
                    # el proximo turno). Espeja el override de energy_score
                    # (~L4326). Como Hydrapple ex es ex y NO daña a Crustle, no
                    # se pierde ningun Syrup Storm letal al no activarla.
                    _ripen_wasted_vs_crustle = False
                    if op_is_crustle_deck:
                        _rip_act = my_state.active[0] if my_state.active else None
                        _rip_active_tapu_full = (
                            _rip_act is not None and _rip_act.id == Tapu_Bulu
                            and len(_rip_act.energies) * _grass_mult() >= 4)
                        if _rip_active_tapu_full:
                            _rip_bench_needs = any(
                                _bp is not None and (
                                    (_bp.id == Tapu_Bulu and len(_bp.energies) * _grass_mult() < 4)
                                    or (_bp.id == Dipplin and len(_bp.energies) < 1)
                                    or (_bp.id == Meganium and len(_bp.energies) * _grass_mult() < 4))
                                for _bp in (my_state.bench or []))
                            _ripen_wasted_vs_crustle = not _rip_bench_needs
                    if hand_counts[Basic_Grass_Energy] < 1:
                        score = -1
                    elif _ripen_retreat_ko_pivot and o.area == AreaType.ACTIVE:
                        # Pivote Ripening -> retirar -> promover Tapu letal vs
                        # Crustle (user, log 86028607 turno 22): activo Hydrapple
                        # ex bloqueado por el muro con un Tapu de banca YA LISTO
                        # (220 de dano) que noquea a Crustle. Activar Ripening
                        # Charge para adjuntar una Planta al PROPIO Hydrapple y
                        # alcanzar su coste de retirada (efectivo), habilitando
                        # retirarlo y subir a Tapu para rematar. Debe GANAR a
                        # Teal Dance / adjuntes normales; el objetivo (activo
                        # Hydrapple) se fija en energy_score (ATTACH_FROM).
                        score = 31600
                    elif _ripen_bench_tapu_ko_pivot and o.area == AreaType.ACTIVE:
                        # Pivote Ripening -> cargar Tapu de banca a letal ->
                        # retirar Hydrapple -> promover Tapu -> noquear al muro
                        # (user, log 86182112 paso 82): activo Hydrapple ex
                        # bloqueado por el muro Crustle y YA retirable, con un
                        # Tapu de banca en 2 efectivas que con 1 Planta mas llega
                        # a 4 (Wood Hammer 220, letal). Activar Ripening Charge
                        # para adjuntar la 2a Planta a Tapu (objetivo fijado en
                        # energy_score / ATTACH_FROM, +20000) en vez de malgastar
                        # el adjunte en Teal Dance sobre Ogerpon. Ver
                        # _ripen_bench_tapu_ko_pivot (~L4395).
                        score = 31600
                    elif _ripen_wasted_vs_crustle:
                        score = -1
                    elif _hydra_energy >= 2:
                        if _extra_energy_enables_ko(Hydrapple_ex, _hydra_energy):
                            score = 29000
                        elif (o.area == AreaType.ACTIVE and _active_hydra_cannot_ko
                                and _bench_has_chargeable):

                            score = 30000
                        elif _tapu_future_charge:
                            # El activo ya asegura el KO: usamos Ripening Charge
                            # (adjunta a cualquier Pokemon) para poner una 2a
                            # energia en Tapu Bulu de banca y dejarlo listo
                            # (2 fisicas = 4 efectivas con Meganium). El objetivo
                            # Tapu Bulu se elige en energy_score (ATTACH_FROM).
                            score = 30000
                        else:
                            score = -1
                    elif _active_needs_energy and not _enough_for_both and o.area != AreaType.ACTIVE:

                        score = 7500
                    else:

                        _hydra_eff = _hydra_energy * _grass_mult()
                        if _hydra_eff < 2:

                            if _hydra_energy == 0 and o.area != AreaType.ACTIVE:
                                score = 31150
                            else:
                                score = 31100
                        else:

                            score = 30500
                elif card.id == Fezandipiti_ex:
                    # Orden correcto Unfair Stamp -> Flip the Script: mientras
                    # tengamos Unfair Stamp jugable este turno (nos noquearon el
                    # turno anterior y sigue en la mano) primero se juega Unfair
                    # Stamp y DESPUES la habilidad de Fezandipiti. Asi el Stamp
                    # no baraja de vuelta las 3 cartas que roba la habilidad;
                    # quedan 5 (Stamp) + 3 (habilidad) = 8 cartas. Unfair Stamp
                    # es Item: al jugarse sale de la mano y _stamp_blocks_supp_chain
                    # pasa a False, re-habilitando la habilidad (30000).
                    # Ademas, si tenemos Lillie's Determination en la mano (y aun
                    # no jugamos Supporter), la jugamos ANTES que la habilidad.
                    if _stamp_blocks_supp_chain or _lillie_blocks_fez_ability:
                        score = -1
                    else:
                        score = 30000
                elif card.id == Meowth_ex:

                    score = 30000
                elif card.id == 1267:
                    score = 1
                else:
                    score = 29000

        elif o.type == OptionType.RETREAT:

            _active_reloc = my_state.active[0] if my_state.active else None

            # Regla (user, log 86510119 paso 26, vs Dragapult, PERDIDA): si al
            # retirar el activo la promocion volveria a subir un Pokemon de la
            # MISMA especie que el que estamos retirando, la retirada no cambia
            # nada y solo malgasta la energia del coste de retirada. Se cancela
            # (score = -1) para dejar al Pokemon en el activo. Dos casos:
            #   (a) todos los candidatos de banca son la misma especie que el
            #       activo (el unico candidato es el mismo Pokemon), o
            #   (b) la promocion prefiere subir un BASICO de 1 premio (tenemos
            #       Lillie's Determination y NINGUN atacante de banca listo para
            #       atacar este turno, rival no inmune a ex/habilidad) y ese
            #       basico volveria a ser la especie del activo (p.ej. Applin
            #       activo con otro Applin en banca): subir Applin por Applin no
            #       aporta nada.
            _same_species_retreat = False
            if _active_reloc is not None:
                _ss_bench = [bp for bp in (my_state.bench or [])
                             if bp is not None and isinstance(bp, Pokemon)]
                if _ss_bench:
                    # (a) Caso literal: no hay ningun candidato de otra especie.
                    _ss_only_same = all(bp.id == _active_reloc.id
                                        for bp in _ss_bench)

                    # (b) Caso "preferir basico": reproducimos la condicion de la
                    # promocion (`_refresh_promote_prefer_basic`).
                    _ss_grass_attach = (
                        hand_counts.get(Basic_Grass_Energy, 0) >= 1
                        and not state.energyAttached)
                    _ss_bench_atk_ready = False
                    for bp in _ss_bench:
                        if bp.id not in MAIN_ATTACKERS:
                            continue
                        _ss_e = len(bp.energies)
                        if _can_attack_eff(bp.id, _ss_e) or (
                                _ss_grass_attach
                                and _can_attack_eff(
                                    bp.id, _ss_e + _grass_attach_unit())):
                            _ss_bench_atk_ready = True
                            break
                    _ss_prefer_basic = (
                        hand_counts.get(Lillie_Determination, 0) >= 1
                        and not op_has_ex_immune_active
                        and not op_has_ability_immune_active
                        and not _ss_bench_atk_ready)
                    _ss_act_data = card_table.get(_active_reloc.id)
                    _ss_act_is_basic = (
                        _ss_act_data is not None
                        and not getattr(_ss_act_data, 'stage1', False)
                        and not getattr(_ss_act_data, 'stage2', False))
                    # Basicos no-ex candidatos de banca (los que la promocion
                    # preferiria como muro de 1 premio).
                    _ss_bench_basics = []
                    for bp in _ss_bench:
                        _bp_d = card_table.get(bp.id)
                        if (_bp_d is not None
                                and not getattr(_bp_d, 'stage1', False)
                                and not getattr(_bp_d, 'stage2', False)
                                and bp.id not in OUR_EX_IDS):
                            _ss_bench_basics.append(bp.id)
                    # El basico promovido es de la especie del activo si: el
                    # activo es Applin (basico de maxima prioridad) y hay otro
                    # Applin en banca, o todos los basicos candidatos son de la
                    # especie del activo (suba el que suba, misma especie).
                    _ss_same_basic = False
                    if _ss_bench_basics:
                        if _active_reloc.id == Applin:
                            _ss_same_basic = (Applin in _ss_bench_basics)
                        else:
                            _ss_same_basic = (
                                Applin not in _ss_bench_basics
                                and all(_b == _active_reloc.id
                                        for _b in _ss_bench_basics))
                    _ss_prefer_same = (
                        _ss_prefer_basic and _ss_act_is_basic
                        and _active_reloc.id not in OUR_EX_IDS
                        and _ss_same_basic)

                    _same_species_retreat = _ss_only_same or _ss_prefer_same

            # Regla: Meganium activo + Hydrapple ex en banca + rival SIN
            # proteccion-ex (no Crustle/Sylveon/inmunes a ex) => retirar Meganium
            # para promover a Hydrapple ex (atacante/motor clave). Meganium sigue
            # en banca, asi que Wild Growth se mantiene. NO aplica vs muros
            # inmunes a ex, donde Hydrapple ex (ex) no podria golpear.
            _meg_retreat_for_hydra = False
            if (_active_reloc is not None and _active_reloc.id == Meganium
                    and can_switch
                    and not (op_is_crustle_deck or op_has_ex_immune_active
                             or op_has_ex_immune_bench or op_is_sylveon_deck)):
                for _mrh_bp in (my_state.bench or []):
                    if _mrh_bp is not None and _mrh_bp.id == Hydrapple_ex:
                        _meg_retreat_for_hydra = True
                        break

            _grd_prefer_attack = False
            if (_active_reloc is not None and can_switch
                    and not (op_is_crustle_deck or op_is_cornerstone_deck)):
                _grd_opa = (op_state.active[0]
                            if (op_state.active and op_state.active[0] is not None)
                            else None)
                _grd_opa_hp = (_grd_opa.hp or 0) if _grd_opa is not None else 0
                _grd_opa_e = len(_grd_opa.energies) if _grd_opa is not None else 0

                def _grd_damage(_p):
                    _e = len(_p.energies)
                    _eff = _e * _grass_mult()
                    if _p.id == Hydrapple_ex and _eff >= 2:
                        return 30 + 30 * total_grass
                    if _p.id == Teal_Mask_Ogerpon_ex and _eff >= 3:
                        return 30 + 30 * (_e + _grd_opa_e)
                    if _p.id == Dipplin and _e >= 1:
                        return 100
                    if _p.id == Tapu_Bulu and _eff >= 4:
                        return 220
                    if _p.id == Fezandipiti_ex and _eff >= 3:
                        return 100
                    if _p.id == Pinsir and _eff >= 2:
                        return 100
                    if _p.id == Meganium and _eff >= 4:
                        return 140
                    return 0

                _grd_active_can_attack = _grd_damage(_active_reloc) > 0
                _grd_any_ko = False
                for _grd_p in ([_active_reloc] + list(my_state.bench)):
                    if _grd_p is None:
                        continue
                    _grd_d = _grd_damage(_grd_p)
                    if _grd_d > 0 and _grd_opa_hp > 0 and _grd_d >= _grd_opa_hp:
                        _grd_any_ko = True
                        break
                if _grd_active_can_attack and not _grd_any_ko:
                    _grd_prefer_attack = True

            _active_can_ko_now = False
            if (can_attack and _active_reloc is not None
                    and op_state.active and op_state.active[0] is not None):
                _acn_op = op_state.active[0]
                _acn_e = len(_active_reloc.energies)
                _acn_eff = _acn_e * _grass_mult()
                _acn_base = 0
                if _active_reloc.id == Dipplin and _acn_e >= 1:
                    _acn_base = 20 * bench_count
                elif _active_reloc.id == Hydrapple_ex and _acn_eff >= 2:
                    _acn_base = 30 + 30 * total_grass
                elif _active_reloc.id == Teal_Mask_Ogerpon_ex and _acn_eff >= 3:
                    _acn_base = 30 + 30 * _acn_e
                elif _active_reloc.id == Tapu_Bulu and _acn_eff >= 4:
                    _acn_base = 220
                elif _active_reloc.id == Fezandipiti_ex and _acn_eff >= 3:
                    _acn_base = 100
                elif _active_reloc.id == Meganium and _acn_eff >= 4:
                    _acn_base = 140
                elif _active_reloc.id == Pinsir and _acn_eff >= 2:
                    _acn_base = 100
                if _acn_base > 0:
                    _acn_dmg = _our_effective_damage(
                        _active_reloc, _acn_op, _acn_base,
                        meganium_in_play, neutralization_zone_active)
                    if _acn_dmg > 0 and _acn_dmg >= (_acn_op.hp or 0):
                        _active_can_ko_now = True

            # Proteger a Hydrapple ex: si nuestro Hydrapple ex activo va a ser
            # noqueado el proximo turno y no puede tomar un KO este turno, es
            # mejor retirarlo y promover un atacante de banca no-ex (p.ej.
            # Dipplin) que si pueda atacar. Hydrapple ex es clave para acelerar
            # energia y cargar a Tapu Bulu en un solo turno, asi que evitamos
            # entregarlo (2 premios) por nada.
            _hydra_ex_protect_retreat = False
            if (_active_reloc is not None and _active_reloc.id == Hydrapple_ex
                    and can_switch and active_ko_likely
                    and not _active_can_ko_now):
                for _hpr_bp in my_state.bench:
                    if _hpr_bp is None:
                        continue
                    _hpr_e = len(_hpr_bp.energies)
                    _hpr_eff = _hpr_e * _grass_mult()
                    if _hpr_bp.id == Dipplin and _hpr_e >= 1:
                        _hydra_ex_protect_retreat = True
                        break
                    elif _hpr_bp.id == Tapu_Bulu and _hpr_eff >= 4:
                        _hydra_ex_protect_retreat = True
                        break
                    elif _hpr_bp.id == Meganium and _hpr_eff >= 4:
                        _hydra_ex_protect_retreat = True
                        break
                    elif _hpr_bp.id == Pinsir and _hpr_eff >= 2:
                        _hydra_ex_protect_retreat = True
                        break

            # Regla (user): si un Hydrapple ex de BANCA (ya con >=2 efectivas)
            # puede subir al activo y rematar con un Syrup Storm LETAL sobre el
            # activo rival, retirar el activo actual para promoverlo y ganar la
            # partida. Solo cuando se puede cambiar (can_switch). La promocion
            # posterior elige a ese Hydrapple ex via `_best_promote_card`.
            # IMPORTANTE (user, log 86338560 paso 114, GANADA vs Mega Lucario):
            # NO retirar el activo si el PROPIO activo YA puede rematar este turno
            # (`_active_can_ko_now`). En ese caso subir a otro Hydrapple ex de
            # banca (mismo tipo, con MENOS energia) solo pagaria el coste de
            # retirada y reduciria el ataque sin ganar nada: el activo debe atacar.
            # EXCEPCION (user, log 86412738 paso 145 vs Hops; GENERALIZADA en log
            # 86505760 paso 55, GANADA vs Alakazam): aunque el activo YA pueda
            # noquear, si es un ex FRAGIL (2 premios, distinto de Hydrapple y con
            # menos HP que el muro 330) y un Hydrapple ex de BANCA TAMBIEN puede
            # rematar (Syrup Storm letal), SIEMPRE se prefiere retirar y atacar con
            # el Hydrapple ex: mismo KO pero deja el muro de 330 HP como activo en
            # vez de exponer el ex fragil (Hydrapple aguanta ataques mayores que
            # Ogerpon en turnos futuros). Regla del user: siempre que un Hydrapple
            # ex de banca pueda derrotar al rival, es nuestro atacante prioritario.
            # UNICA excepcion: no pivotar si atacar con el activo YA gana la partida
            # este turno (my_prize <= premios del activo rival): ahi no hay turno
            # futuro que proteger, se ataca directo. El pivote NO aplica cuando el
            # activo es NO-ex (retirarlo para exponer un ex de 2 premios seria peor)
            # ni cuando el activo ya es el propio Hydrapple ex.
            _active_ex_fragile_pivot = (
                _active_reloc is not None
                and _active_can_ko_now
                and _active_reloc.id in OUR_EX_IDS
                and _active_reloc.id != Hydrapple_ex
                and (_active_reloc.maxHp or 0) < 330
                and op_state.active and op_state.active[0] is not None
                and not (my_prize <= prize_count(op_state.active[0])))
            _hydra_lethal_promote = False
            if (_active_reloc is not None and can_switch
                    and (not _active_can_ko_now or _active_ex_fragile_pivot)
                    and op_state.active and op_state.active[0] is not None):
                _hlp_opa = op_state.active[0]
                _hlp_opa_hp = _hlp_opa.hp or 0
                for _hlp_bp in (my_state.bench or []):
                    if _hlp_bp is None or _hlp_bp.id != Hydrapple_ex:
                        continue
                    if len(_hlp_bp.energies) * _grass_mult() < 2:
                        continue  # no puede pagar Syrup Storm
                    _hlp_dmg = _our_effective_damage(
                        _hlp_bp, _hlp_opa, 30 + 30 * total_grass,
                        meganium_in_play, neutralization_zone_active)
                    if _hlp_dmg > 0 and _hlp_opa_hp > 0 and _hlp_dmg >= _hlp_opa_hp:
                        _hydra_lethal_promote = True
                        break

            # Regla (user, log 86583929 turno 4, vs Alakazam, PERDIDA): pivote de
            # KO con Teal Mask Ogerpon ex. Si el activo esta ESTANCADO (no puede
            # noquear este turno, p.ej. un Fezandipiti ex sin las 3 energias de su
            # ataque) y en la banca hay un Teal Mask Ogerpon ex que, al PROMOVERLO
            # y usar Teal Dance, alcanza >=3 energias EFECTIVAS y su Myriad Leaf
            # Shower NOQUEA al activo rival, retirar el activo para subir al Ogerpon
            # y rematar. La Planta que necesita Teal Dance se obtiene de la mano o,
            # con Night Stretcher, recuperando una Planta del descarte -- incluida
            # la que el propio coste de retirada acaba de descartar del activo. El
            # scorer greedy evaluaba a los Ogerpon de banca a su energia ACTUAL
            # (via _grd_damage/_bench_attacker_can_ko, que exigen >=3 efectivas) y
            # nunca modelaba la rampa de Teal Dance tras promover, por eso no "veia"
            # esta linea. Solo si el rival NO inmuniza a nuestros ex (Ogerpon no
            # daña a Crustle/Sylveon). len(energies) es EFECTIVA (Wild Growth de
            # Meganium duplica cada Planta): sin Meganium un Ogerpon a 1 Planta
            # llega a 2 tras Teal Dance (<3) y el detector no dispara.
            _ogerpon_lethal_promote = False
            if (_active_reloc is not None and can_switch
                    and not _active_can_ko_now
                    and _active_reloc.id != Teal_Mask_Ogerpon_ex
                    and not op_has_ex_immune_active
                    and op_state.active and op_state.active[0] is not None):
                _olp_opa = op_state.active[0]
                _olp_opa_hp = _olp_opa.hp or 0
                _olp_op_e = len(_olp_opa.energies)
                # Planta disponible para Teal Dance: en mano, o recuperable con
                # Night Stretcher desde el descarte (o desde la energia que la
                # retirada acaba de descartar del activo, que en nuestro mazo es
                # Planta).
                _olp_grass_ok = (
                    hand_counts.get(Basic_Grass_Energy, 0) >= 1
                    or (hand_counts.get(Night_Stretcher, 0) >= 1
                        and (discard_counts.get(Basic_Grass_Energy, 0) >= 1
                             or _physical_energy(len(_active_reloc.energies)) >= 1)))
                if _olp_grass_ok:
                    for _olp_bp in (my_state.bench or []):
                        if _olp_bp is None or _olp_bp.id != Teal_Mask_Ogerpon_ex:
                            continue
                        _olp_eff_after = len(_olp_bp.energies) + _grass_attach_unit()
                        if _olp_eff_after < 3:
                            continue
                        _olp_dmg = _our_effective_damage(
                            _olp_bp, _olp_opa,
                            30 + 30 * (_olp_eff_after + _olp_op_e),
                            meganium_in_play, neutralization_zone_active)
                        if _olp_dmg > 0 and _olp_opa_hp > 0 and _olp_dmg >= _olp_opa_hp:
                            _ogerpon_lethal_promote = True
                            break

            # Regla (user): un Tapu Bulu CARGADO en el activo que puede noquear
            # al Pokemon activo rival NO debe retirarse; debe atacar. Al no ser
            # ex, si lo noquean solo entrega 1 premio, asi que conviene rematar
            # con el en lugar de gastar el pivote a Hydrapple ex (que si es
            # noqueado entrega 2 premios). Por eso vetamos el retiro/promocion.
            # EXCEPCION: en matchups ex-inmunes (Crustle / Cornerstone /
            # Sylveon), si el activo rival NO pertenece a la linea ex-inmune
            # (no requiere a Tapu para ser danado) y hay un Pokemon de banca que
            # lo puede rematar, SI retiramos a Tapu Bulu para reservarlo como
            # atacante clave contra los muros con proteccion ex. Si el activo
            # rival ES de la linea ex-inmune, Tapu Bulu ataca (es quien puede
            # con esos muros).
            if (_active_reloc is not None and _active_reloc.id == Tapu_Bulu
                    and _active_can_ko_now):
                _tapu_ex_immune_match = (op_is_crustle_deck
                                         or op_is_cornerstone_deck
                                         or op_is_sylveon_deck)
                _tapu_opa_id = (op_state.active[0].id
                                if op_state.active
                                and op_state.active[0] is not None else None)
                _tapu_opa_is_immune_line = (
                    _tapu_opa_id in {
                        Crustle_Grass, Crustle_Fighting, Dwebble_Grass,
                        Dwebble_Fighting, Sylveon,
                        Cornerstone_Mask_Ogerpon_ex}
                    or _tapu_opa_id in EEVEE_IDS)
                _tapu_reserve = (_tapu_ex_immune_match
                                 and not _tapu_opa_is_immune_line
                                 and not op_has_ex_immune_active)
                if not _tapu_reserve:
                    # Tapu Bulu debe atacar: no lo retiramos para promover.
                    _hydra_lethal_promote = False

            _op_active_is_cubchoo = bool(
                op_state.active and op_state.active[0] is not None
                and op_state.active[0].id == Cubchoo)
            _cub_bench_attacker_ready = any(
                _bp_cub is not None and _conf_can_attack_pkmn(_bp_cub)
                for _bp_cub in (my_state.bench or []))

            if _hydra_lethal_promote:
                # Retirar el activo para promover al Hydrapple ex de banca cuyo
                # Syrup Storm es LETAL y rematar. Maxima prioridad de retiro.
                score = 9000
            elif _ogerpon_lethal_promote:
                # Retirar el activo estancado para promover un Teal Mask Ogerpon
                # ex de banca y rematar con Myriad Leaf Shower tras Teal Dance
                # (user, log 86583929 turno 4 vs Alakazam). Prioridad de retiro
                # equiparada a la del pivote de Hydrapple: cobrar el premio AHORA.
                # Las acciones posteriores (Night Stretcher para recuperar la
                # Planta, Teal Dance sobre el nuevo activo y el ataque) ya las
                # habilitan sus scorers (_td_ko_on_active da 31500 al Teal Dance
                # que habilita el KO, y el scorer de ATTACK remata si es letal).
                score = 8900
            elif (_op_active_is_cubchoo and can_switch
                    and not _cub_bench_attacker_ready):
                # Matchup vs Cubchoo: su ataque deja a nuestro activo sin poder
                # atacar el proximo turno. Retirar ahora para subir a un Pokemon
                # de banca que TAMPOCO puede atacar (sin energia suficiente) solo
                # lo expone al mismo ataque y desperdicia el pivote. Mientras no
                # haya un atacante LISTO en banca, NO se retira: se mantiene el
                # activo (Cubchoo pega poco) y se aprovecha el turno para cargar
                # energia hasta dejar listo a un atacante de banca. Cuando ese
                # atacante este cargado, _cub_bench_attacker_ready sera True y se
                # permitira el retiro para subirlo y atacar en nuestro turno.
                score = -1
            elif (_lucario_sac_pivot and _lucario_sac_available
                    and bench_count >= 1 and can_switch):
                # Retirar el Ogerpon ex para no entregar 2 premios al Mega Lucario;
                # despues promoveremos un sacrificio de 1 premio.
                score = 8000
            elif _conf_should_retreat:
                score = 4000 + condition_urgency
            elif _hydra_ex_protect_retreat:

                score = 6000
            elif _ex_stuck_promo_ready and can_switch:
                # Nuestro activo es un ex bloqueado por un muro inmune (Crustle /
                # Sylveon) y hay un atacante no-ex LISTO en banca: retirar para
                # promover al que SI golpea al muro (el mas fuerte se elige en
                # `_best_promote_card`). Evita malgastar el turno atacando por 0.
                score = 6000
            elif _hydra_pivot_active:
                # Pivote defensivo: retirar al activo fragil y subir a Hydrapple
                # ex (vida completa) que tambien noquea. Prioridad alta para que
                # gane sobre atacar con el activo fragil (que moriria el proximo
                # turno). El plan ya apunta a Hydrapple, por lo que la opcion de
                # ATACAR con el activo queda suprimida (plan.attacker >= 1).
                score = 6500
            elif _teal_wall_pivot and can_switch:
                # Activo Teal Mask Ogerpon ex condenado que NO puede atacar: ya
                # se uso Teal Dance (adjunto 1 Grass -> paga la retirada de 1).
                # Retirar y subir al cuerpo mas fuerte de banca (Hydrapple ex,
                # 330 HP) aunque aun no pueda atacar: no regalar el activo por
                # nada y poner un muro. La promocion elige el de mas vida.
                score = 6450
            elif _hydra_wall_pivot:
                # Activo Teal Mask Ogerpon ex condenado que SI puede atacar pero
                # NO noquea (muro Hydrapple ex sano en banca). Retirar y subir al
                # muro (330 HP) que sobrevive al remate rival y sigue atacando
                # (Syrup Storm 330), en vez de atacar con el Ogerpon fragil que
                # moriria regalando 2 premios. El plan apunta a Hydrapple, asi que
                # ATACAR con el activo queda suprimido (plan.attacker >= 1).
                score = 6450
            elif _tapu_sac_pivot:
                # Sacrificio de premios (user): nuestro activo es un ex de 2
                # premios en riesgo y un Tapu Bulu de banca (1 premio) listo puede
                # noquear al activo rival. Retirar el ex y subir a Tapu Bulu para
                # atacar: mismo KO, pero si nos noquean entregamos 1 premio en vez
                # de 2. Prioridad alta: gana incluso cuando el activo tambien puede
                # noquear ahora (_active_can_ko_now). El plan apunta a Tapu, asi que
                # la opcion de ATACAR con el activo queda suprimida (plan.attacker>=1).
                score = 6600
            elif _prize_denial_pivot:
                # Negacion de premios (user): retirar el ex activo CONDENADO (2
                # premios) que si atacamos igual moriria el proximo turno dando al
                # rival los premios para GANAR, y subir un cuerpo de 1 premio que
                # ataca. Asi el KO rival del proximo turno NO cierra la partida. El
                # plan apunta a ese cuerpo (plan.attacker>=1), por lo que ATACAR con
                # el activo condenado queda suprimido.
                score = 6550
            elif _meg_retreat_for_hydra and not _active_can_ko_now:
                # Meganium activo: subir a Hydrapple ex de banca (rival sin
                # proteccion-ex). Prioridad alta para que gane sobre atacar con
                # Meganium o mantenerlo. Excepcion: si Meganium noquea AHORA
                # (_active_can_ko_now) se queda para tomar el premio.
                score = 6400
            elif _nonex_active_hits_wall:
                # user, log 86406907 paso 87, GANADA vs Crustle: nuestro activo
                # es un atacante NO-ex (p.ej. Meganium) que SI golpea al muro
                # inmune-a-ex (Crustle activo). NUNCA se retira: retirarlo solo
                # promoveria un ex de banca que hace 0 al muro. Debe ATACAR.
                score = -1
            elif _grd_prefer_attack:

                score = -1
            elif _active_can_ko_now:

                score = -1
            elif plan.attacker >= 1:

                _retreat_active = my_state.active[0] if my_state.active else None
                _retreat_active_can_attack = False
                if _retreat_active is not None:
                    _ra_eff = len(_retreat_active.energies) * _grass_mult()
                    _ra_can_attach = (hand_counts.get(Basic_Grass_Energy, 0) >= 1 and
                                      not state.energyAttached)
                    _ra_eff_after = _ra_eff + (_grass_attach_unit() if _ra_can_attach else 0)
                    if _retreat_active.id == Hydrapple_ex:
                        _retreat_active_can_attack = (_ra_eff_after >= 2)
                    elif _retreat_active.id == Dipplin:
                        _retreat_active_can_attack = (len(_retreat_active.energies) >= 1 or _ra_can_attach)
                    elif _retreat_active.id == Teal_Mask_Ogerpon_ex:
                        _retreat_active_can_attack = (_ra_eff_after >= 3)
                    elif _retreat_active.id == Tapu_Bulu:
                        _retreat_active_can_attack = (_ra_eff_after >= 4)
                    elif _retreat_active.id == Pinsir:
                        _retreat_active_can_attack = (_ra_eff_after >= 2)
                    elif _retreat_active.id == Fezandipiti_ex:
                        _retreat_active_can_attack = (_ra_eff_after >= 3)

                if not _retreat_active_can_attack:

                    score = 3500
                else:

                    score = 2500
            elif my_state.active and my_state.active[0] is not None:
                active = my_state.active[0]
                active_energy = len(active.energies)

                _our_first_turn = (state.turn == 1 and we_go_first) or (state.turn == 2 and not we_go_first)

                NON_ATTACKERS = (Meganium, Meowth_ex, Chikorita, Bayleef, Applin)

                # Meganium incluido: puede atacar (req 4 efectivo) y debe contar
                # como atacante disponible en banca. Fuente unica: MAIN_ATTACKERS.
                STRATEGIC_ATTACKERS = MAIN_ATTACKERS

                _bench_ready_for_retreat = False
                for bp in my_state.bench:
                    if bp is None:
                        continue
                    _brr_e = len(bp.energies)
                    _brr_eff = _brr_e * _grass_mult()
                    if bp.id == Hydrapple_ex and _brr_eff >= 2:
                        _bench_ready_for_retreat = True
                        break
                    elif bp.id == Dipplin and _brr_e >= 1:
                        _bench_ready_for_retreat = True
                        break
                    elif bp.id == Teal_Mask_Ogerpon_ex and _brr_eff >= 3:
                        _bench_ready_for_retreat = True
                        break
                    elif bp.id == Tapu_Bulu and _brr_eff >= 4:
                        _bench_ready_for_retreat = True
                        break
                    elif bp.id == Fezandipiti_ex and _brr_eff >= 3:
                        _bench_ready_for_retreat = True
                        break
                    elif bp.id == Meganium and _brr_eff >= 4:
                        _bench_ready_for_retreat = True
                        break

                _BASIC_OR_STAGE1_NONEX = (
                    Applin, Dipplin, Chikorita, Bayleef, Tapu_Bulu, Pinsir)
                _fase58_promo_ready = any(
                    bp is not None and bp.id in _BASIC_OR_STAGE1_NONEX
                    for bp in my_state.bench)

                _meg_only_attacker_retreat = False
                if ((op_is_crustle_deck or op_is_cornerstone_deck) and
                        can_switch and active.id != Meganium):

                    _opa_km = (op_state.active[0]
                               if (op_state.active and op_state.active[0] is not None)
                               else None)
                    _opa_km_hp = (_opa_km.hp or 0) if _opa_km is not None else 0

                    def _meg_blk_ko(_p):
                        # ¿este atacante no-ex noquea al activo rival (Crustle) este turno?
                        # len(energies) YA es la energia EFECTIVA (Wild Growth ya
                        # aplicado en la observacion) -> Solar Beam (140) con 4.
                        if _p is None or _opa_km is None or _opa_km_hp <= 0:
                            return False
                        _e = len(_p.energies)
                        _eff = _e * _grass_mult()
                        _base = 0
                        if _p.id == Dipplin and _e >= 1:
                            _base = 20 * bench_count
                        elif _p.id == Tapu_Bulu and _eff >= 4:
                            _base = 220
                        elif _p.id == Pinsir and _eff >= 2:
                            _base = 100
                        elif _p.id == Meganium and _eff >= 4:
                            _base = 140
                        if _base <= 0:
                            return False
                        return _our_effective_damage(
                            _p, _opa_km, _base, meganium_in_play,
                            neutralization_zone_active) >= _opa_km_hp

                    _other_atk_ready_meg = any(
                        _mp_meg is not None and _mp_meg.id != Meganium and
                        _meg_blk_ko(_mp_meg)
                        for _mp_meg in ([active] + list(my_state.bench)))

                    _meganium_bench_ready_meg = any(
                        bp is not None and bp.id == Meganium and _meg_blk_ko(bp)
                        for bp in my_state.bench)

                    _act_ko_rival_meg = False
                    if (can_attack and op_state.active and
                            op_state.active[0] is not None):
                        _opa_meg = op_state.active[0]
                        _opa_meg_e = len(_opa_meg.energies)
                        _act_base_meg = 0
                        if active.id == Teal_Mask_Ogerpon_ex:
                            _act_base_meg = 30 + 30 * (len(active.energies) + _opa_meg_e)
                        elif active.id == Hydrapple_ex:
                            _act_base_meg = 30 + 30 * total_grass
                        if _act_base_meg > 0:
                            _act_dmg_meg = _our_effective_damage(
                                active, _opa_meg, _act_base_meg,
                                meganium_in_play, neutralization_zone_active)
                            if _act_dmg_meg >= (_opa_meg.hp or 0) and _act_dmg_meg > 0:
                                _act_ko_rival_meg = True
                    if (not _other_atk_ready_meg and _meganium_bench_ready_meg and
                            not _act_ko_rival_meg):
                        _meg_only_attacker_retreat = True

                if _meg_only_attacker_retreat:

                    score = 3500

                elif ((op_is_crustle_deck or op_is_cornerstone_deck) and
                      active.id == Teal_Mask_Ogerpon_ex):
                    if not can_switch:
                        score = -1
                    else:

                        _tmo_ko_rival = False
                        _opa_tmo = (op_state.active[0]
                                    if (op_state.active and op_state.active[0] is not None)
                                    else None)
                        if can_attack and _opa_tmo is not None:
                            _opa_tmo_e = len(_opa_tmo.energies)
                            _tmo_base = 30 + 30 * (len(active.energies) + _opa_tmo_e)
                            _tmo_dmg = _our_effective_damage(
                                active, _opa_tmo, _tmo_base,
                                meganium_in_play, neutralization_zone_active)
                            if _tmo_dmg >= (_opa_tmo.hp or 0) and _tmo_dmg > 0:
                                _tmo_ko_rival = True
                        if _tmo_ko_rival:
                            score = -1
                        else:

                            _tmo_attacker_ready = False
                            for bp in my_state.bench:
                                if bp is None:
                                    continue
                                _bp_e = len(bp.energies)
                                _bp_eff = _bp_e * _grass_mult()
                                if bp.id == Pinsir and _bp_eff >= 2:
                                    _tmo_attacker_ready = True
                                    break
                                elif bp.id == Tapu_Bulu and _bp_eff >= 4:
                                    _tmo_attacker_ready = True
                                    break
                                elif (op_is_crustle_deck and
                                      bp.id == Dipplin and _bp_e >= 1):
                                    _tmo_attacker_ready = True
                                    break
                                elif (op_is_crustle_deck and
                                      bp.id == Meganium and _bp_eff >= 4):
                                    _tmo_attacker_ready = True
                                    break
                                elif (not op_has_ex_immune_active and
                                      bp.id == Hydrapple_ex and _bp_eff >= 2):
                                    _tmo_attacker_ready = True
                                    break
                                elif (not op_has_ex_immune_active and
                                      bp.id == Teal_Mask_Ogerpon_ex and _bp_eff >= 3):
                                    _tmo_attacker_ready = True
                                    break
                            if _tmo_attacker_ready:
                                score = 3400
                            else:
                                score = -1
                elif (not can_attack) and can_switch and _bench_ready_for_retreat:

                    score = 3200

                elif (op_is_cornerstone_deck and can_switch and
                      active.id in OUR_ABILITY_IDS and
                      op_state.active and op_state.active[0] is not None and
                      op_state.active[0].id == Cornerstone_Mask_Ogerpon_ex):
                    _cs_tapu_ready = any(
                        bp is not None and bp.id == Tapu_Bulu and
                        len(bp.energies) >= 4
                        for bp in my_state.bench)
                    if _cs_tapu_ready:
                        score = 3400
                    else:
                        score = -1

                elif (op_is_crustle_deck and can_switch and
                      active.id in OUR_EX_IDS):

                    _cr_op_act = op_state.active[0] if op_state.active else None
                    _cr_ex_can_ko = False
                    if can_attack and _cr_op_act is not None:
                        _cr_op_e = len(_cr_op_act.energies)
                        _cr_base = 0
                        if active.id == Teal_Mask_Ogerpon_ex:
                            _cr_base = 30 + 30 * (len(active.energies) + _cr_op_e)
                        elif active.id == Hydrapple_ex:
                            _cr_base = 30 + 30 * total_grass
                        if _cr_base > 0:
                            _cr_dmg = _our_effective_damage(
                                active, _cr_op_act, _cr_base,
                                meganium_in_play, neutralization_zone_active)
                            if _cr_dmg >= (_cr_op_act.hp or 0) and _cr_dmg > 0:
                                _cr_ex_can_ko = True
                    if _cr_ex_can_ko:
                        score = -1
                    else:
                        _crustle_bench_atk = False
                        for bp in my_state.bench:
                            if bp is None:
                                continue
                            _ce_eff = len(bp.energies) * _grass_mult()
                            if ((bp.id == Tapu_Bulu and _ce_eff >= 4) or
                                    (bp.id == Dipplin and len(bp.energies) >= 1) or
                                    (bp.id == Meganium and _ce_eff >= 4)):
                                _crustle_bench_atk = True
                                break
                        if _crustle_bench_atk:
                            score = 3400
                        else:
                            score = -1

                elif (active.id in OUR_EX_IDS and (not can_attack) and can_switch
                      and estimated_op_damage >= (active.hp or 0)
                      and _fase58_promo_ready):
                    score = 3300

                elif active.id == Fezandipiti_ex and plan.attacker == 0:
                    score = -1

                elif (active.id == Fezandipiti_ex and
                      state.turn == 2 and not we_go_first):
                    score = -1

                elif active.id in NON_ATTACKERS:

                    _has_bench_attacker = False
                    for bp in my_state.bench:
                        if bp is not None and bp.id in STRATEGIC_ATTACKERS:
                            _has_bench_attacker = True
                            break

                    _bench_has_only_non_attackers = True
                    for bp in my_state.bench:
                        if bp is not None and bp.id in STRATEGIC_ATTACKERS:
                            _bench_has_only_non_attackers = False
                            break

                    _HAND_PLAYABLE_ATTACKERS = (Tapu_Bulu, Teal_Mask_Ogerpon_ex)
                    _has_attacker_in_hand = False
                    if bench_count < 5:
                        for _hpa_id in _HAND_PLAYABLE_ATTACKERS:
                            if (hand_counts.get(_hpa_id, 0) >= 1 and
                                    field_counts.get(_hpa_id, 0) == 0):
                                _has_attacker_in_hand = True
                                break

                        if (not _has_attacker_in_hand and
                                hand_counts.get(Fezandipiti_ex, 0) >= 1 and
                                field_counts.get(Fezandipiti_ex, 0) == 0 and
                                state.turn > 1):
                            _has_attacker_in_hand = True

                    # ¿Hay en la banca un atacante REALMENTE listo para atacar
                    # este turno? No basta con que exista un atacante por
                    # identidad (p.ej. un Teal ex): debe tener la energia
                    # efectiva suficiente (Wild Growth incluido), o poder
                    # completarla adjuntando UNA energia de Planta este turno.
                    # Sin esta comprobacion se retiraba el activo para subir a
                    # un atacante SIN cargar, que tampoco podia atacar,
                    # desperdiciando el turno y el coste de retirada.
                    _grass_attach_this_turn = (
                        hand_counts.get(Basic_Grass_Energy, 0) >= 1
                        and not state.energyAttached)
                    _bench_attacker_ready = False
                    for bp in my_state.bench:
                        if bp is None or bp.id not in STRATEGIC_ATTACKERS:
                            continue
                        _bar_req = ATTACK_ENERGY_REQ.get(bp.id)
                        if _bar_req is None:
                            continue
                        _bar_eff = len(bp.energies) * _grass_mult()
                        if _bar_eff >= _bar_req:
                            _bench_attacker_ready = True
                            break
                        if (_grass_attach_this_turn
                                and _bar_eff + _grass_attach_unit() >= _bar_req):
                            _bench_attacker_ready = True
                            break

                    # Pivote de rescate: si el activo es una pre-evolucion FRAGIL
                    # (Chikorita/Bayleef) CONDENADA este turno (probable KO) y en la
                    # banca hay un cuerpo que SOBREVIVE al mejor golpe rival, conviene
                    # RETIRAR aunque el atacante de banca no pueda atacar todavia:
                    # resguardamos la pre-evolucion (se evoluciona luego en banca),
                    # subimos un muro que aguanta y refrescamos la mano (Lillie's se
                    # habilita tras evolucionar). Mantener el cuerpo de poca vida al
                    # frente solo lo entrega gratis y frena la linea de evolucion.
                    _fragile_doomed_pivot = False
                    if (can_switch and active.id in (Chikorita, Bayleef)
                            and (active_ko_likely
                                 or estimated_op_damage >= (active.hp or 0))):
                        for _fdp_bp in my_state.bench:
                            if _fdp_bp is None:
                                continue
                            if (_fdp_bp.hp or 0) > _op_best_damage_vs(_fdp_bp):
                                _fragile_doomed_pivot = True
                                break

                    if active.id in (Chikorita, Bayleef, Meganium):

                        # Regla (user, log 86607718 turno 2, vs Crustle, PERDIMOS):
                        # vs Crustle, si el ACTIVO es un Chikorita y NO hay ningun
                        # Chikorita en la banca, la prioridad es RETIRARLO (para
                        # evolucionarlo a Meganium en banca y subir un cuerpo util),
                        # AUNQUE en la banca no haya todavia un atacante LISTO (el
                        # veto de "atacante de banca sin energia" de abajo lo
                        # bloqueaba). Chikorita activo es un lastre que no daña al
                        # muro. Requiere poder retirar (can_switch: ya cargamos 1
                        # Planta al Chikorita, ver energy_score) y tener un cuerpo en
                        # banca al que promover. La promocion prefiere un atacante y,
                        # si no hay, un ex (Ogerpon ex primero, ver _best_promote).
                        if (op_is_crustle_deck and active.id == Chikorita
                                and field_counts.get(Chikorita, 0) <= 1
                                and bench_count >= 1):
                            score = 6500
                        elif _has_bench_attacker and _bench_attacker_ready:
                            score = 6000
                        elif _fragile_doomed_pivot:
                            # Activo fragil condenado: retirar para subir un cuerpo
                            # que sobrevive y resguardar la pre-evolucion, aunque el
                            # atacante de banca no pueda atacar aun. Gana sobre atacar
                            # con un cuerpo que morira el proximo turno.
                            score = 5800
                        elif _has_bench_attacker and not _bench_attacker_ready:
                            # Hay un atacante en banca pero SIN energia para
                            # atacar este turno: retirar ahora solo subiria un
                            # cuerpo que tampoco ataca. Mejor mantener el activo
                            # y seguir cargando al atacante de la banca.
                            score = -1
                        elif _bench_has_only_non_attackers and _has_attacker_in_hand:

                            score = -1
                        else:
                            score = 5500
                    elif active.id == Meowth_ex:

                        _ATK_REQS_RETREAT = {
                            Hydrapple_ex: 2, Dipplin: 1, Teal_Mask_Ogerpon_ex: 3,
                            Tapu_Bulu: 4, Fezandipiti_ex: 3,
                        }
                        _has_ready_bench_for_meowth = False
                        for bp in my_state.bench:
                            if bp is None or bp.id not in _ATK_REQS_RETREAT:
                                continue
                            _bp_eff_m = len(bp.energies) * _grass_mult()
                            if _bp_eff_m >= _ATK_REQS_RETREAT[bp.id]:
                                _has_ready_bench_for_meowth = True
                                break

                        _meowth_data_r = card_table.get(Meowth_ex)
                        _op_act_r = op_state.active[0] if op_state.active else None
                        _op_act_data_r = card_table.get(_op_act_r.id) if _op_act_r is not None else None
                        _meowth_weak_to_op = (
                            _meowth_data_r is not None and getattr(_meowth_data_r, 'weakness', None) is not None and
                            _op_act_data_r is not None and
                            getattr(_op_act_data_r, 'energyType', None) == _meowth_data_r.weakness)
                        _safe_chargeable_body = False
                        if _meowth_weak_to_op:
                            for bp in my_state.bench:
                                if bp is None:
                                    continue
                                _bp_data_r = card_table.get(bp.id)
                                _bp_weak_r = (
                                    _bp_data_r is not None and getattr(_bp_data_r, 'weakness', None) is not None and
                                    _op_act_data_r is not None and
                                    getattr(_op_act_data_r, 'energyType', None) == _bp_data_r.weakness)
                                if _bp_weak_r:
                                    continue
                                _bp_e_r = len(bp.energies)
                                _bp_eff_r = _bp_e_r * _grass_mult()

                                if bp.id == Teal_Mask_Ogerpon_ex and _bp_eff_r >= 2:
                                    _safe_chargeable_body = True
                                    break
                                elif bp.id == Hydrapple_ex and _bp_eff_r >= 2:
                                    _safe_chargeable_body = True
                                    break
                                elif bp.id == Dipplin and _bp_e_r >= 1:
                                    _safe_chargeable_body = True
                                    break
                                elif bp.id == Tapu_Bulu and _bp_eff_r >= 4:
                                    _safe_chargeable_body = True
                                    break
                                elif bp.id == Meganium and _bp_eff_r >= 4:
                                    _safe_chargeable_body = True
                                    break

                        if _meowth_weak_to_op and _safe_chargeable_body:
                            score = 6000
                        elif _has_ready_bench_for_meowth:
                            score = 5000
                        else:
                            score = -1
                    elif _has_bench_attacker:
                        score = 3000
                    elif _bench_has_only_non_attackers and _has_attacker_in_hand:

                        score = -1
                    else:
                        score = 2500

                elif active.id in STRATEGIC_ATTACKERS:

                    # Listo-para-atacar via energia efectiva (fuente unica:
                    # ATTACK_ENERGY_REQ). El branch ya garantiza pertenencia a
                    # STRATEGIC_ATTACKERS (= MAIN_ATTACKERS).
                    _active_can_attack = _can_attack_eff(active.id, active_energy)

                    if not _active_can_attack:

                        _has_ready_bench = False
                        for bp in my_state.bench:
                            if bp is None:
                                continue
                            # Cuenta cualquier atacante principal listo en banca
                            # (incluye Meganium, antes omitido).
                            if (bp.id in MAIN_ATTACKERS
                                    and _can_attack_eff(bp.id, len(bp.energies))):
                                _has_ready_bench = True
                                break

                        if _has_ready_bench:
                            score = 2500
                        else:
                            score = -1

                    elif (can_switch
                          and estimated_op_damage > 0
                          and estimated_op_damage >= (active.hp or 0)
                          and not (plan.remain_hp is not None
                                   and plan.remain_hp <= 0)):
                        # RETIRO DEFENSIVO: nuestro atacante activo PUEDE atacar
                        # pero sera noqueado el proximo turno (dano estimado del
                        # rival >= sus HP) y atacar con el no noquea al activo
                        # rival. Si en la banca hay un atacante MAS resistente
                        # que sobrevive al ataque rival y puede atacar tras subir,
                        # retirarse a el evita la derrota (muro que ademas
                        # presiona). Sin esto el codigo asume "si puedo atacar,
                        # ataco" y deja morir al activo condenado.
                        _def_retreat_target = False
                        for bp in my_state.bench:
                            if bp is None or bp.id not in MAIN_ATTACKERS:
                                continue
                            if (bp.hp or 0) <= _op_best_damage_vs(bp):
                                continue  # tambien seria noqueado el proximo turno
                            if _can_attack_eff(bp.id, len(bp.energies)):
                                _def_retreat_target = True
                                break
                        if _def_retreat_target:
                            score = 5600
                        else:
                            score = -1

                    elif (active.id in (Hydrapple_ex, Tapu_Bulu) and
                          op_state.active and op_state.active[0] is not None and
                          op_state.active[0].id == Drednaw):
                        _has_shell_bypass_bench = False
                        for bp in my_state.bench:
                            if bp is None:
                                continue
                            _bp_energy = len(bp.energies)
                            _bp_effective = _bp_energy * _grass_mult()
                            if bp.id == Meganium and _bp_effective >= 4:
                                _has_shell_bypass_bench = True
                                break
                            elif bp.id == Dipplin and _bp_energy >= 1:
                                _has_shell_bypass_bench = True
                                break
                        if _has_shell_bypass_bench:
                            score = 5500
                        else:
                            score = -1

                    elif (active.id in OUR_EX_IDS and
                          op_state.active and op_state.active[0] is not None and
                          op_state.active[0].id == Sylveon):
                        _has_nonex_bench = False
                        for bp in my_state.bench:
                            if bp is None:
                                continue
                            _bp_energy = len(bp.energies)
                            _bp_effective = _bp_energy * _grass_mult()
                            if bp.id == Tapu_Bulu and _bp_effective >= 4:
                                _has_nonex_bench = True
                                break
                            elif bp.id == Meganium and _bp_effective >= 4:
                                _has_nonex_bench = True
                                break
                            elif bp.id == Dipplin and _bp_energy >= 1:
                                _has_nonex_bench = True
                                break
                        if _has_nonex_bench:
                            score = 5500
                        else:
                            score = -1

                    elif (neutralization_zone_active and active.id in OUR_EX_IDS):
                        _has_nz_bypass_bench = False
                        for bp in my_state.bench:
                            if bp is None:
                                continue
                            _bp_energy = len(bp.energies)
                            _bp_effective = _bp_energy * _grass_mult()
                            if bp.id == Tapu_Bulu and _bp_effective >= 4:
                                _has_nz_bypass_bench = True
                                break
                            elif bp.id == Meganium and _bp_effective >= 4:
                                _has_nz_bypass_bench = True
                                break
                            elif bp.id == Dipplin and _bp_energy >= 1:
                                _has_nz_bypass_bench = True
                                break
                            elif bp.id == Pinsir and _bp_effective >= 2:
                                _has_nz_bypass_bench = True
                                break

                        _op_act = op_state.active[0] if op_state.active else None
                        _op_act_has_rb = False
                        if _op_act is not None:
                            _op_act_data = card_table[_op_act.id]
                            _op_act_has_rb = (_op_act_data.ex or _op_act_data.megaEx)
                        if _has_nz_bypass_bench and not _op_act_has_rb:
                            score = 5000
                        else:
                            score = -1
                    else:
                        score = -1
                else:
                    score = -1
            else:
                score = -1

            # Cancelar la retirada si solo reubicaria al mismo Pokemon (misma
            # especie) al activo: es inutil y malgasta la energia del coste de
            # retirada (user, log 86510119 paso 26). Ver `_same_species_retreat`.
            # EXCEPCION (user, registro_005 vs Comfey): si el activo esta CONFUNDIDO
            # (Brambleghast), retirarlo para promover un cuerpo de la MISMA especie
            # SI aporta: el nuevo activo NO esta confundido y puede atacar sin la
            # moneda. Con dos Teal Mask Ogerpon ex (el plan del matchup) este es el
            # caso normal, asi que no se veta la retirada de escape de confusion.
            if _same_species_retreat and score > 0 and not _conf_should_retreat:
                score = -1

            # Pivote vs Alakazam (user, registro_010 paso 127): retirar el ex
            # activo para promover un cuerpo de 1 premio (Meganium/Tapu Bulu) que
            # NOQUEA al activo rival (ver `_alakazam_pivot_1prize`). Debe SUPERAR
            # al ataque del ex de 2 premios (score ~1100) para que el motor retire
            # en vez de atacar con el ex; sigue por debajo del umbral de
            # "Supporter antes de retirar" (2000) para respetar ese orden.
            if _alakazam_pivot_1prize:
                score = max(score, 6000)

            # Regla (user, registro 004 paso 53 vs Archaludon ex, GANADA):
            # SIEMPRE jugar el Supporter (Dawn / Lillie's / Lana's Aid) ANTES de
            # retirar. Retirar primero desaprovecha lo que el Supporter aporta al
            # resto del turno (p.ej. Dawn busca la linea Applin -> Dipplin ->
            # Hydrapple ex que se evoluciona con Forest ESTE mismo turno, y solo
            # despues conviene retirar el Fezandipiti ex y promover al Hydrapple
            # ex). El retiro NO lo bloquea jugar el Supporter (sigue disponible
            # despues), asi que se POSPONE: se rebaja su score por debajo de la
            # jugada del Supporter (>=2400) para que el motor elija primero el
            # Supporter y re-evalue el retiro en la siguiente decision.
            if (score > 2000 and not state.supporterPlayed):
                _rt_supp_first = any(
                    hand_counts.get(_sid, 0) >= 1 and _supp_values.get(_sid, 0) > 0
                    for _sid in (Dawn, Lillie_Determination, Lanas_Aid))
                if _rt_supp_first:
                    score = 2000

        elif o.type == OptionType.ATTACK:
            score = 1000
            if plan.attack_index >= 0:

                score += 100

            if condition_risky_attack:
                if _conf_should_attack:
                    score += 300
                elif plan.remain_hp is not None and plan.remain_hp <= 0:
                    score += 50
                else:
                    score -= 500

            _active_is_hydrapple = (my_state.active and my_state.active[0] is not None and
                                    my_state.active[0].id == Hydrapple_ex)
            if _active_is_hydrapple and not itchy_pollen_active:
                _atk_is_ko = (plan.remain_hp is not None and plan.remain_hp <= 0)
                if not _atk_is_ko:

                    _can_add_energy = False

                    if (hand_counts.get(Basic_Grass_Energy, 0) >= 1 and
                            not state.energyAttached):
                        _can_add_energy = True

                    _ogerpon_count = field_counts.get(Teal_Mask_Ogerpon_ex, 0)
                    _energy_in_hand = hand_counts.get(Basic_Grass_Energy, 0)
                    if _ogerpon_count >= 1 and _energy_in_hand >= 1:
                        _can_add_energy = True

                    if (hand_counts.get(Teal_Mask_Ogerpon_ex, 0) >= 1 and
                            bench_count < 5 and _energy_in_hand >= 1):
                        _can_add_energy = True

                    if (hand_counts.get(Ultra_Ball, 0) >= 1 and
                            bench_count < 5 and _energy_in_hand >= 1 and
                            CARTAS_ACTIVAS_EN_MAZO.get(Teal_Mask_Ogerpon_ex, {}).get(ESTADO_MAZO, 0) > 0):
                        _hand_size_atk = len(my_state.hand) if my_state.hand else 0
                        if _hand_size_atk >= 3:
                            _can_add_energy = True

                    if _can_add_energy:

                        score = -1

            if plan.attacker >= 1 and score > 0 and not _nonex_active_hits_wall:
                _plan_atk_is_winning = False
                if plan.remain_hp is not None and plan.remain_hp <= 0:
                    _op_act_plan = op_state.active[0] if op_state.active else None
                    if _op_act_plan is not None and my_prize <= prize_count(_op_act_plan):
                        _plan_atk_is_winning = True
                if not _plan_atk_is_winning:

                    _plan_active = my_state.active[0] if my_state.active else None
                    _plan_can_retreat = False
                    if _plan_active is not None:
                        _plan_rc = RETREAT_COST.get(_plan_active.id, 1)
                        _plan_active_energy = len(_plan_active.energies)
                        if _plan_active_energy >= _plan_rc:
                            _plan_can_retreat = True
                    if _plan_can_retreat:
                        score = -1

            if (bench_count == 0 and hand_counts.get(Ultra_Ball, 0) >= 1):
                _atk_hand_size = len(my_state.hand) if my_state.hand else 0
                if _atk_hand_size >= 3 and not itchy_pollen_active:

                    _atk_has_basic_in_hand = any(
                        hand_counts.get(pid, 0) >= 1
                        for pid in (Chikorita, Applin, Teal_Mask_Ogerpon_ex,
                                    Tapu_Bulu, Meowth_ex, Fezandipiti_ex, Pinsir))
                    if not _atk_has_basic_in_hand:

                        _atk_has_basic_mazo = False
                        for _atk_bid in (Chikorita, Applin, Teal_Mask_Ogerpon_ex,
                                         Tapu_Bulu, Meowth_ex, Fezandipiti_ex, Pinsir):
                            if CARTAS_ACTIVAS_EN_MAZO.get(_atk_bid, {}).get(ESTADO_MAZO, 0) > 0:
                                _atk_has_basic_mazo = True
                                break
                        if _atk_has_basic_mazo:

                            _atk_is_winning = False
                            if plan.remain_hp is not None and plan.remain_hp <= 0:
                                _op_act_atk = op_state.active[0] if op_state.active else None
                                if _op_act_atk is not None and op_prize <= prize_count(_op_act_atk):
                                    _atk_is_winning = True
                            if not _atk_is_winning:
                                score = -1

            if (state.turn == 2 and not we_go_first
                    and hand_counts.get(Lillie_Determination, 0) >= 1):
                _lillie_playable_now = any(
                    _lo.type == OptionType.PLAY
                    and get_card(obs, AreaType.HAND, _lo.index, my_index) is not None
                    and get_card(obs, AreaType.HAND, _lo.index, my_index).id
                    == Lillie_Determination
                    for _lo in select.option)
                if _lillie_playable_now:
                    score = -1

            _atk_active = my_state.active[0] if my_state.active else None
            if (_atk_active is not None and _atk_active.id == Meowth_ex
                    and bench_count == 0):
                # El ataque de Meowth ex (Tuck Tail) devuelve a Meowth ex y todas
                # sus cartas a la mano. Si Meowth ex es el UNICO Pokemon en juego
                # (banca vacia), atacar nos dejaria sin Pokemon en juego =>
                # perdemos la partida. Solo puede atacar si hay al menos un
                # Pokemon en banca al que retroceder.
                score = -1

            if op_active_dodge_immune:
                score = -1

        elif o.type == OptionType.END:

            if can_attack:
                _end_attack_is_risky = (
                    condition_risky_attack and
                    not (plan.remain_hp is not None and plan.remain_hp <= 0))
                if _conf_should_attack or not _end_attack_is_risky:
                    score = -10000

        elif o.type == OptionType.SPECIAL_CONDITION:

            if context == SelectContext.RECOVER_SPECIAL_CONDITION:

                if o.specialConditionType is not None:
                    if o.specialConditionType == SpecialConditionType.PARALYZE:
                        score = 500
                    elif o.specialConditionType == SpecialConditionType.SLEEP:
                        score = 400
                    elif o.specialConditionType == SpecialConditionType.CONFUSE:
                        score = 300
                    elif o.specialConditionType == SpecialConditionType.POISON:
                        score = 200
                    elif o.specialConditionType == SpecialConditionType.BURN:
                        score = 150
            elif context == SelectContext.AFFECT_SPECIAL_CONDITION:

                if o.specialConditionType is not None:
                    if o.specialConditionType == SpecialConditionType.PARALYZE:
                        score = 500
                    elif o.specialConditionType == SpecialConditionType.SLEEP:
                        score = 400
                    elif o.specialConditionType == SpecialConditionType.CONFUSE:
                        score = 350
                    elif o.specialConditionType == SpecialConditionType.POISON:
                        score = 200
                    elif o.specialConditionType == SpecialConditionType.BURN:
                        score = 150

        scores.append(score)

    if select.effect is not None and select.effect.id == Poke_Pad and context == SelectContext.TO_HAND:
        _best_pp_score = -1
        _best_pp_id = 0
        for _pp_idx, _pp_opt in enumerate(select.option):
            if _pp_idx < len(scores) and scores[_pp_idx] > _best_pp_score:
                _pp_card = get_card(obs, _pp_opt.area, _pp_opt.index, my_index)
                if _pp_card is not None:
                    _best_pp_score = scores[_pp_idx]
                    _best_pp_id = _pp_card.id
        if _best_pp_id > 0 and _best_pp_score > 10:

            _pp_data = card_table.get(_best_pp_id)
            _pp_is_basic = not (_pp_data is not None and
                                (getattr(_pp_data, 'stage1', False) or
                                 getattr(_pp_data, 'stage2', False)))
            if _pp_is_basic:
                _poke_pad_target_id = _best_pp_id

    if (_lucario_sac_pivot and select.effect is not None
            and select.effect.id == Poke_Pad and context == SelectContext.TO_HAND):
        # Tapu Bulu SOLO se fuerza como objetivo de Poke Pad cuando de verdad
        # aporta:
        #   * el rival juega un mazo con proteccion a ex (Crustle / Cornerstone
        #     Ogerpon / Sylveon), donde nuestros ex hacen 0 dano, o
        #   * ya tenemos Hydrapple ex cargado + Meganium en juego, que permite
        #     bajar Tapu Bulu y cargarlo al instante (con Meganium 2 energias
        #     cuentan como 4, asi que puede atacar de inmediato).
        # En cualquier otro caso (p.ej. este mismo escenario anti-Lucario) la
        # prioridad la decide el scoring normal: Applin > Chikorita >
        # evoluciones de Pokemon en juego que no tengamos en mano, y Tapu Bulu
        # queda como ultima opcion. Ademas no se trae un Tapu Bulu redundante
        # si ya tenemos uno en mano o en juego.
        _tapu_already = (hand_counts.get(Tapu_Bulu, 0) >= 1 or
                         field_counts.get(Tapu_Bulu, 0) >= 1)
        if (not _tapu_already) and _tapu_sac_priority:
            for _pp_sac_idx, _pp_sac_opt in enumerate(select.option):
                _pp_sac_card = get_card(obs, _pp_sac_opt.area, _pp_sac_opt.index, my_index)
                if _pp_sac_card is not None and _pp_sac_card.id == Tapu_Bulu:
                    if _pp_sac_idx < len(scores):
                        scores[_pp_sac_idx] = 99999
                    _poke_pad_target_id = Tapu_Bulu
                    break

    if select.effect is not None and select.effect.id == Ultra_Ball and context == SelectContext.TO_HAND:
        _best_ub_score = -1
        _best_ub_id = 0
        for _ub_idx, _ub_opt in enumerate(select.option):
            if _ub_idx < len(scores) and scores[_ub_idx] > _best_ub_score:
                _ub_card = get_card(obs, _ub_opt.area, _ub_opt.index, my_index)
                if _ub_card is not None:
                    _best_ub_score = scores[_ub_idx]
                    _best_ub_id = _ub_card.id
        if _best_ub_id == Meowth_ex and _best_ub_score > 10:
            _ub_meowth_pending = True

    _vetoed_stadium_idxs = set()
    _our_first_turn_guard = ((we_go_first and state.turn == 1) or
                             (not we_go_first and state.turn == 2))
    _replace_opp_stadium_ok = (
        (not we_go_first) and state.turn == 2 and
        stadium_id != 0 and stadium_id != Forest_of_Vitality)
    if _our_first_turn_guard and not _replace_opp_stadium_ok and select.option:
        for _gi, _go in enumerate(select.option):
            if _gi >= len(scores):
                continue
            if _go.type == OptionType.PLAY:
                _gcard = get_card(obs, AreaType.HAND, _go.index, my_index)
                if _gcard is not None:
                    _gdata = card_table.get(_gcard.id)
                    if _gdata is not None and _gdata.cardType == CardType.STADIUM:
                        scores[_gi] = -99999
                        _vetoed_stadium_idxs.add(_gi)

    # =================================================================
    # ORDEN DE JUGADA (contexto MAIN): imponer la secuencia solicitada
    #   1) estadio  2) basicos + evoluciones  3) Poke Pad
    #   4) Bug Catching Set  5) cargar energia
    # El estadio solo aparece jugable a partir del turno 3 (en el turno 1/2
    # queda vetado mas arriba), asi que su tier solo actua "despues del
    # segundo turno". La energia que habilita un KO/ataque letal ESTE turno
    # conserva prioridad maxima (excepcion). Solo se reordenan estas 5
    # categorias entre si mediante una clave (tier, score): los tiers altos
    # se juegan primero y, dentro del mismo tier, decide el score original.
    # El resto de opciones (Ultra Ball, supporters, ataque, etc.) mantiene su
    # tier 0 y su puntaje. Solo se promueve una opcion jugable (score > 0),
    # de modo que los vetos (-1) se siguen respetando.
    # =================================================================
    _play_order_tier = [0] * len(scores)
    if context == SelectContext.MAIN:
        _TIER_KO_ENERGY = 6
        _TIER_STADIUM = 5
        _TIER_DEVELOP = 4
        _TIER_POKE_PAD = 3
        _TIER_BUG_SET = 2
        _TIER_ENERGY = 1
        for _po_i, _po_o in enumerate(select.option):
            if _po_i >= len(scores) or scores[_po_i] <= 0:
                continue
            if _po_o.type == OptionType.EVOLVE:
                _play_order_tier[_po_i] = _TIER_DEVELOP
            elif _po_o.type == OptionType.ATTACH:
                _po_is_ko_energy = (
                    getattr(plan, 'energy', False)
                    and plan.remain_hp is not None
                    and plan.remain_hp <= 0
                    and plan.attacker >= 0
                    and ((_po_o.inPlayArea == AreaType.ACTIVE
                          and plan.attacker == 0)
                         or (_po_o.inPlayArea != AreaType.ACTIVE
                             and plan.attacker == 1 + _po_o.inPlayIndex)))
                # Fix (user, log 86506312 paso 97, vs Alakazam): NO tratar la
                # carga al ACTIVO como "energia de KO" (tier 6) cuando
                # `_tapu_future_charge` esta activo. Ese flag ya garantiza que el
                # activo (Hydrapple ex) NOQUEA con su energia ACTUAL y que hay
                # Meganium en juego (cada Planta cuenta doble), asi que la energia
                # extra en el activo es INNECESARIA. Sin esta exclusion, el tier
                # KO_ENERGY del activo aplastaba (6 > 1) la carga de Tapu Bulu de
                # banca (`_tapu_future_charge`, score 40000, tier ENERGY),
                # desperdiciando la energia en un atacante ya listo en vez de
                # preparar al atacante FUTURO. Al bajar el activo a tier ENERGY,
                # la carga de Tapu (40000) gana el desempate dentro del mismo tier.
                if (_tapu_future_charge
                        and _po_o.inPlayArea == AreaType.ACTIVE):
                    _po_is_ko_energy = False
                _play_order_tier[_po_i] = (
                    _TIER_KO_ENERGY if _po_is_ko_energy else _TIER_ENERGY)
            elif _po_o.type == OptionType.PLAY:
                _po_card = get_card(obs, AreaType.HAND, _po_o.index, my_index)
                if _po_card is not None:
                    _po_data = card_table.get(_po_card.id)
                    if _po_card.id == Poke_Pad:
                        _play_order_tier[_po_i] = _TIER_POKE_PAD
                    elif _po_card.id == Bug_Catching_Set:
                        _play_order_tier[_po_i] = _TIER_BUG_SET
                    elif _po_data is not None and _po_data.cardType == CardType.STADIUM:
                        _play_order_tier[_po_i] = _TIER_STADIUM
                    elif _po_data is not None and _po_data.cardType == CardType.POKEMON:
                        _play_order_tier[_po_i] = _TIER_DEVELOP
            elif _po_o.type == OptionType.ABILITY:
                # Teal Dance PRECEDE al adjunte manual (user, registro_004 paso
                # 28, vs Mega Starmie): la habilidad Teal Dance de Teal Mask
                # Ogerpon ex adjunta 1 Planta Y ROBA una carta, asi que debe
                # jugarse ANTES que cualquier adjunte manual de energia. Sin
                # esto, la habilidad quedaba en tier 0 (por debajo del tier
                # ENERGY=1 de los adjuntes) y el orden de jugada anteponia una
                # carga manual pese a que Teal Dance puntua mucho mas alto,
                # desperdiciando el robo. Al ponerla en tier ENERGY, dentro del
                # mismo tier decide el score (Teal Dance ~31500 gana). Las
                # cargas de KO letal de ESTE turno siguen en tier KO_ENERGY=6.
                _po_ab_card = get_card(obs, _po_o.area, _po_o.index, my_index)
                if (_po_ab_card is not None
                        and _po_ab_card.id == Teal_Mask_Ogerpon_ex):
                    _play_order_tier[_po_i] = _TIER_ENERGY

    desc_indices = [i for i, _ in sorted(
        enumerate(scores),
        key=lambda x: (_play_order_tier[x[0]], x[1]),
        reverse=True)]

    _debug_log_decision(context, select, scores, obs, my_index)

    if context == SelectContext.SETUP_BENCH_POKEMON:
        wanted = [i for i in desc_indices if scores[i] >= 0]

        if len(wanted) < select.minCount:
            wanted = desc_indices[:select.minCount]
        return wanted[:select.maxCount]

    if _vetoed_stadium_idxs:
        desc_indices = [i for i in desc_indices if i not in _vetoed_stadium_idxs]

    return desc_indices[:select.maxCount]
