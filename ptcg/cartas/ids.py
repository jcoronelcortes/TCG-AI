"""Datos de carta: IDs, grupos y tablas de referencia.

Extraido VERBATIM de main.py en la Ola 1 del refactor
(docs/main-refactor-arquitectura.md). Aqui NO hay logica: solo constantes que
dependen unicamente de literales. Nada de este modulo puede importar estado ni
tocar el simulador -- lo vigila utils/lint_arquitectura.py (R2).

main.py lo reexporta con `from ptcg.cartas.ids import *`, asi que el `__all__`
de abajo tiene que listar TODOS los nombres (incluidos los que empiezan por `_`,
que `import *` omitiria si no).
"""


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
Xerosic_Machinations = 1197

Dawn = 1231
Bug_Catching_Set = 1094
Ultra_Ball = 1121
Night_Stretcher = 1097
Unfair_Stamp = 1080
Poke_Pad = 1152
Forest_of_Vitality = 1261
Neutralization_Zone = 1247
Team_Rockets_Watchtower = 1256
# Festival Grounds (1245): estadio del rival "Festival Lead". Igual que Grand
# Tree es COMPARTIDO -- lo que importa es que este EN MESA, no quien lo bajo--,
# y enciende la habilidad Festival Lead de CUALQUIER Dipplin en juego (el suyo
# y el nuestro). Ver `FESTIVAL_LEAD_IDS` y `_festival_grounds_in_play`.
Festival_Grounds = 1245
# Grand Tree (Stadium ACE SPEC): "Una vez durante el turno de CADA jugador, ese
# jugador puede buscar en su baraja 1 Pokemon de Fase 1 que evolucione de uno de
# sus Pokemon Basicos y ponerlo sobre el para evolucionarlo. Si evoluciono asi,
# puede buscar ademas 1 Pokemon de Fase 2 que evolucione de ese Pokemon."
#
# Es un estadio COMPARTIDO: si lo baja el RIVAL, nosotros tambien podemos usar
# su habilidad en nuestro turno (y buscamos en NUESTRA baraja). Por eso la
# logica de abajo no exige que la carta este en deck.csv: basta con que este en
# juego (`stadium_id == Grand_Tree`).
#
# Restricciones que impone la propia carta (recordatorio de la regla general):
#   * no se puede evolucionar un Basico en NUESTRO PRIMER TURNO, y
#   * no se puede evolucionar un Basico PUESTO EN JUEGO ESTE TURNO
#     (`Pokemon.appearThisTurn`).
# Solo puede haber UN estadio en mesa, asi que Grand Tree y Forest of Vitality
# nunca conviven: Forest NO levanta el veto de "salio este turno" aqui.
Grand_Tree = 1249
# Maximum Belt (Ace Spec): la tool del rival que suma +50 de dano a nuestro
# Pokemon ex activo (antes de debilidad). Modelada en _op_best_damage_vs y
# _op_active_attack_damage_to.
Maximum_Belt = 1158
# Brave Bangle (1175): +30 de dano a nuestro Pokemon ex ACTIVO (antes de
# debilidad) SOLO si el portador NO tiene Rule Box. El Dipplin del mazo Festival
# Lead no lo tiene, asi que su Do the Wave llega con +30 a nuestros ex (log
# 88971843 paso 116: 20x5 banca = 100, +30 Bangle = 130, que remato al Teal Mask
# Ogerpon ex a 70 PV). Sin modelarla, los pivotes defensivos creian que el muro
# ex aguantaba un golpe que en realidad llega potenciado -- mismo agujero que
# tapo Maximum Belt en la auditoria de julio 2026.
Brave_Bangle = 1175
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
# Cornerstone Mask Ogerpon NO-ex (sin habilidad, atacable): no inmuniza,
# pero DELATA el arquetipo Cornerstone (fase 8: autopsia vs el mazo
# cornerstone_cubchoo — con solo el no-ex/Cubchoo a la vista el flag no
# disparaba y la whitelist anti-Cubchoo vetaba a Tapu Bulu 38 veces).
Cornerstone_Mask_Ogerpon = 386
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
# Powerful Hand (unico ataque de Alakazam 743): dano impreso 0 en attack_table
# pero real = 20 x carta en la mano rival. Modelado en
# _op_active_attack_damage_to cuando el llamador pasa op_hand_count.
POWERFUL_HAND_ATTACK_ID = 1072

# --- Dano VARIABLE del rival: la familia de ataques con dano impreso 0 --------
# Do the Wave (115, unico ataque de Dipplin 93): dano impreso 0 en attack_table
# ("20x") pero real = 20 x SU BANCA. Es la MISMA ceguera que Powerful Hand y
# costo la partida del log 88971843 (paso 117): el agente proyectaba 0 contra
# los cuatro candidatos de banca, con lo que TODA la maquinaria de supervivencia
# (`_promo_survives`, la prudencia de `_pb_key`, `_ev_survivor_asis`,
# `_ko_prefer_basic_general`) se apagaba en silencio y la promocion la decidia
# lo unico que quedaba vivo -- "quien puede atacar este turno"--, subiendo un
# Dipplin de 80 PV a comerse 100 con el rival a 1 premio.
#
# A diferencia de Powerful Hand, la escala NO viaja en la firma de
# `_op_active_attack_damage_to` (necesita la banca rival, no la mano), asi que
# se publica en el flag por turno `_op_bench_count`: si dependiera de que cada
# llamador pase un parametro extra volveriamos al mismo 0 silencioso en la
# mayoria de los sitios.
DO_THE_WAVE_ATTACK_ID = 115

# Festival Lead (habilidad de Dipplin 93): con Festival Grounds EN MESA, este
# Pokemon puede usar un ataque suyo DOS veces; si el primero noquea a nuestro
# activo, ataca OTRA VEZ en cuanto elegimos el reemplazo. Es decir: bajo ese
# estadio, el cuerpo que promovemos tras un KO come un golpe entero ANTES de
# que juguemos -- justo la premisa contraria a la que asume la rama de
# promocion ("la promocion ocurre en el turno RIVAL, donde nadie ataca ya").
FESTIVAL_LEAD_IDS = {Dipplin}



ALAKAZAM_LINE_IDS = (Abra, Kadabra, Alakazam_ex)
# Los cuerpos de la linea que de verdad ATACAN. Powerful Hand cuesta UNA sola
# energia, asi que un Alakazam con energia encima (o el Kadabra que evoluciona a
# el ese mismo turno) es una amenaza inmediata; un Abra pelado no lo es.
ALAKAZAM_ATTACKER_IDS = (Kadabra, Alakazam_ex)

# Linea Mega Lopunny ex: Buneary (basico, id 848) -> Mega Lopunny ex (Stage 1,
# id 849, ex de 2 premios). El basico atacante de este mazo es Buneary.
Buneary = 848
Mega_Lopunny_ex = 849
# Linea Cynthia's Garchomp ex: Gible (basico 379) -> Gabite (Stage 1, 380) ->
# Cynthia's Garchomp ex (Stage 2, 381, ex de 2 premios). El mazo acompana con
# muros de 1 premio (Cynthia's Spiritomb 387, Roselia 341).
Cynthias_Gible = 379
Cynthias_Gabite = 380
Cynthias_Garchomp_ex = 381
Gardevoir_ex = 747
Ralts = 745
Kirlia = 746
Raging_Bolt_ex = 63
Lugia_VSTAR = 337
# Linea Mega Abomasnow ex: Snover (basico, id 722) -> Mega Abomasnow ex (Mega
# ex de 3 premios, id 723). Su atacante one-shotea a cualquiera de nuestros ex,
# igual que Raging Bolt/Bellowing Thunder: mismo plan de DESCUADRE DE PREMIOS
# (poner un cuerpo de 1 premio delante cuando no podemos noquear al activo).
Snover = 722
Mega_Abomasnow_ex = 723
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

# Ambas variantes de Crustle comparten la habilidad anti-ex; la Fighting (533)
# activaba `op_is_crustle_deck` pero faltaba aqui, asi que el calculo de dano
# puntual creia que nuestros ex SI la danaban (auditoria julio 2026).
EX_IMMUNE_IDS = {Crustle_Grass, Crustle_Fighting, Sylveon}

# La LINEA Crustle (pre-evo incluida). `op_is_crustle_deck` es el flag de
# "muro inmune a ex" y tambien se enciende con Sylveon/Eevee, que comparten la
# inmunidad pero NO el resto del mazo. Las reglas que dependen de como esta
# CONSTRUIDO el mazo Crustle -- p.ej. que apenas juega estadio, ver
# `t1_segundos_crustle_estadio_antes_de_lillie` -- tienen que mirar esta lista,
# no el flag.
CRUSTLE_LINE_IDS = {Crustle_Grass, Crustle_Fighting,
                    Dwebble_Grass, Dwebble_Fighting}



ABILITY_IMMUNE_IDS = {Cornerstone_Mask_Ogerpon_ex}

OUR_ABILITY_IDS = {Teal_Mask_Ogerpon_ex, Hydrapple_ex, Meganium, Fezandipiti_ex, Meowth_ex, Dipplin}

# Cuerpos que NUNCA compensa subir al activo con Boss's aunque no puedan atacar:
# los MUROS que anulan a nuestros atacantes (Crustle/Sylveon vs ex, Cornerstone
# vs habilidades) y el LOCKER Iron Thorns ex, cuya Initialization apaga Teal
# Dance / Ripening / Last-Ditch / Flip the Script desde el puesto ACTIVO. Los
# cinco tienen ataques de coste 3, asi que pelados pasan por "inofensivos"
# (`_op_cuerpo_inofensivo`) y se llevarian la preferencia del gusteo sin KO.
GUST_TRAMPA_IDS = EX_IMMUNE_IDS | ABILITY_IMMUNE_IDS | {Iron_Thorns_ex}

# --- Supervivencia al KO y nuevas inmunidades (plan jul 2026, P0.1/P1.6) -----
# Cuerpos que SOBREVIVEN un golpe letal estando a vida COMPLETA quedandose a
# 10 PV: Crustle 533 ("Sturdy", ya modelado) y Pikachu ex 210 ("Resolute
# Heart", faltaba). El dano efectivo se capa a hp-10 en _our_effective_damage,
# asi que todo `can_ko` que pase por ahi hereda el cap automaticamente.
Pikachu_ex_Resolute = 210
FULL_HP_SURVIVE_IDS = {Crustle_Fighting, Pikachu_ex_Resolute}

# Mega Hawlucha ex ("Tenacious Body"): ante un golpe letal tira moneda y con
# cara sobrevive a 10 PV -> el KO NUNCA esta garantizado. Survival Brace (tool
# 1155): a vida completa sobrevive al KO a 10 PV. Los evaluadores de REMATE
# (wins_now / SCORE_WIN_GAME / _active_attack_wins_now) consultan
# _ko_no_garantizado para no declarar una victoria que depende de una moneda o
# de una tool; el dano normal NO se altera (atacarlos sigue teniendo valor).
Mega_Hawlucha_ex = 886
Survival_Brace = 1155

# Farigiraf ex ("Armor Tail"): inmune al dano de ataques de BASICOS ex. De
# nuestro mazo anula a Ogerpon ex / Meowth ex / Fezandipiti ex; Hydrapple ex es
# Etapa 2 y SI lo dana, igual que los no-ex (Tapu Bulu, Meganium, Bayleef...).
Farigiraf_ex = 83
OUR_BASIC_EX_IDS = {Teal_Mask_Ogerpon_ex, Meowth_ex, Fezandipiti_ex}

# --- Planes de matchup: QUE Pokemon permite bajar cada uno -------------------
# Dos matchups restringen la banca a una lista cerrada (el resto de nuestros
# Pokemon se veta en la rama PLAY): vs Cubchoo la lista de abajo, vs Comfey
# SOLO Teal Mask Ogerpon ex (maximo 2). Viven como constante -- y no como una
# tupla local de la rama PLAY -- porque las REDES DE RESCATE del bloque de
# finalizacion tienen que consultar el mismo plan: cavar con Ultra Ball un
# cuerpo que el propio plan vetara al bajarlo no salva un turno muerto, solo
# quema dos cartas de la mano (ver `_matchup_permite_bajar`).
CUBCHOO_ALLOWED_PLAY_IDS = (Applin, Dipplin, Hydrapple_ex,
                            Chikorita, Bayleef, Meganium,
                            Teal_Mask_Ogerpon_ex, Meowth_ex)

# --- Bloqueo de items del rival (plan jul 2026, P1.5) ------------------------
# Ademas del Itchy Pollen de Budew (ya modelado por log de ataque), bloquean
# nuestros items: Jellicent ex 598 ("Oceanic Curse") y Tyranitar 290 ("Daunting
# Gaze") MIENTRAS esten en el activo rival, y Galvantula ex 161 con Fulgurite
# (attackId 210) durante nuestro turno siguiente. Con 10+ items en el mazo
# (UBx4/BCSx4/NSx2/Stamp/PokePad) el motor entero depende de detectarlos.
Jellicent_ex = 598
Tyranitar_Daunting = 290
Galvantula_ex = 161
FULGURITE_ATTACK_ID = 210
OP_ITEM_LOCK_ACTIVE_IDS = {Jellicent_ex, Tyranitar_Daunting}

# --- Bloqueo de habilidades por Iron Thorns ex (plan jul 2026, P1.4) ---------
# Iron Thorns ex 37 ("Initialization") en el ACTIVO rival: los Pokemon con Rule
# Box de AMBOS lados pierden sus habilidades -> se apagan Teal Dance, Ripening
# Charge, Last-Ditch Catch y Flip the Script a la vez (nuestro motor entero).
# NO afecta a los sin Rule Box (Meganium Wild Growth y Dipplin siguen vivos:
# Dipplin no tiene Rule Box; Festival Lead requiere estadio que no jugamos).
OUR_RULEBOX_ABILITY_IDS = {Teal_Mask_Ogerpon_ex, Hydrapple_ex, Fezandipiti_ex,
                           Meowth_ex}

# --- Denegacion de premios del rival (plan jul 2026, P0.2) -------------------
# Munkidori ex 139 ("Oh No You Don't"): si el rival tiene Pecharunt ex 141 en
# juego, su KO rinde 1 premio MENOS. Mega Gengar ex 772 ("Shadowy
# Concealment"): mientras este en juego, el KO de un Pokemon {D} rival por un
# ex NUESTRO rinde 1 premio menos. Sin esto, `wins_now`/SCORE_WIN_GAME pueden
# declarar una victoria a la que le falta 1 premio. Se consultan via
# `prize_count_op` (solo para Pokemon DEL RIVAL: nuestro Fezandipiti ex
# tambien es {D} y NO debe verse afectado).
Munkidori_ex = 139
Pecharunt_ex = 141
Mega_Gengar_ex = 772

# --- Burst de banca rival (plan jul 2026, P0.3) ------------------------------
# Dusknoir 133 ("Cursed Blast": 13 contadores = 130) y Dusclops 132 (5 = 50)
# aportan dano EXTRA desde la banca ADEMAS del ataque del activo rival (la
# habilidad se usa y LUEGO atacan). `active_ko_likely` debe sumarlo o los
# pivotes defensivos creen que el muro sobrevive un golpe que en realidad
# llega con +130.
OP_BENCH_BURST = {Dusknoir: 130, Dusclops: 50}

# Dano AUTOMATICO que el ataque del rival reparte a UN Pokemon de NUESTRA banca
# (user, registro_006/008 vs Marnie's Grimmsnarl ex, PERDIDA). Shadow Bullet
# hace 180 al activo Y 30 a un banquillo CADA turno, asi que nuestros cuerpos de
# poca vida (Dipplin 80, Applin 40, Chikorita 70) mueren solos y regalan premios
# sin que el rival gaste nada. El agente era ciego a ese goteo: `op_bench_snipe_
# threat` era un booleano que solo se leia en el setup. Aqui se cuantifica para
# poder proyectar QUE cuerpo muere el proximo turno y decidir si conviene curarlo
# (Ripening Charge cura 30) o evolucionarlo (la evolucion resetea la vida).
# Valores del texto de cada ataque; el default 30 es el caso conservador.
OP_BENCH_SNIPE_DAMAGE = {
    Grimmsnarl_ex: 30,       # Shadow Bullet: 180 + 30 a 1 banquillo
    Dragapult_ex: 60,        # Phantom Dive: 6 contadores repartibles (60 a uno)
    Mega_Starmie_ex: 50,     # Jetting Blow: 120 + 50 a 1 banquillo
    Mega_Greninja_ex: 120,   # Mirage Barrage: 120 a 2 Pokemon
}
OP_BENCH_SNIPE_DEFAULT = 30

# --- LA VENTANA DE REGALO (user, registros/marnie partidas 1-3, PERDIDAS) ----
# Las tres derrotas fueron por UN premio y el rival cobro 7 de 18 premios SIN
# ATACAR. El snipe de OP_BENCH_SNIPE_DAMAGE (30) es solo un tercio de la
# amenaza: faltaban las dos fuentes que matan cuerpos sin gastar ataque.
#
# 1) Freezing Shroud (Froslass): 1 contador a CADA Pokemon con habilidad de
#    AMBOS lados en cada Chequeo Pokemon. Hay DOS chequeos por ronda (fin de
#    nuestro turno y fin del suyo), asi que cada Froslass reparte 20 por ronda
#    a cada uno de nuestros cuerpos de OUR_ABILITY_IDS. Con dos Froslass, 40.
# 2) Adrena-Brain (Munkidori): mueve hasta 3 contadores desde UNO de SUS
#    Pokemon a CUALQUIERA de los nuestros -- activo o banca, una vez por turno
#    por Munkidori con energia Oscura. Es dano DIRIGIBLE: si curamos al cuerpo
#    A el rival apunta al B.
#
# Ojo con dos lecturas que rompen la intuicion:
#   - El Tera de Teal Mask Ogerpon ex en banca previene dano DE ATAQUES: corta
#     el snipe de 30 pero NO los contadores de Froslass ni los que mueve
#     Munkidori (verificado: en la partida 2 el Ogerpon de banca murio con 60
#     contadores movidos por dos Munkidori).
#   - La municion de Munkidori se AUTO-RENUEVA: su propio Froslass carga 10 por
#     chequeo sobre cada Munkidori y sobre el Grimmsnarl ex (todos tienen
#     habilidad), asi que los contadores que hay hoy en su mesa no son el techo.
FREEZING_SHROUD_COUNTER = 10   # dano por contador de Freezing Shroud
CHECKUPS_PER_ROUND = 2         # chequeos Pokemon entre dos turnos nuestros
ADRENA_BRAIN_MOVE = 30         # contadores que mueve UN Munkidori energizado

# Curacion de Ripening Charge (Hydrapple ex) al Pokemon que recibe la Planta.
RIPENING_HEAL = 30
# Score del OBJETIVO de Ripening Charge cuando la habilidad se usa para curar.
RIPEN_HEAL_TARGET_SCORE = 39500
# Score de la HABILIDAD Ripening Charge jugada por su curacion: sobre la Teal
# Dance de desarrollo (31050) y bajo la que habilita un KO (31500) o los pivotes
# de retirada (31600). >= 29000 para que suba al tier ENERGY y compita alli.
RIPEN_HEAL_ABILITY_SCORE = 31250
# Misma habilidad cuando el cuerpo que sale de la ventana es un ex (DOS premios)
# -- p.ej. el Teal Mask Ogerpon ex activo a 20 PV de la partida 3, que murio a
# 30 contadores movidos. Ahi la curacion gana a Teal Dance (31500): un robo de
# una carta no vale dos premios. Sigue por debajo de las bandas letales (41000+)
# y de los pivotes de retirada (31600).
RIPEN_HEAL_EX_ABILITY_SCORE = 31550

# Techo de la carga sobre un cuerpo CONDENADO (Fase C del plan de Marnie): el
# rival puede cobrarlo antes de nuestro proximo turno y no ataca hoy, asi que la
# Planta se va al descarte con el. Es un TECHO, no un veto: queda por debajo de
# toda la banda de desarrollo (~8000) y por encima del ultimo recurso de
# Applin/Dipplin con Hydrapple en juego (10), que es energia que de verdad no
# rinde nada. Si no queda nada mejor, la energia sigue cayendo aqui.
SCORE_CARGA_CONDENADA = 20
# Piso de la banda LETAL de `energy_score`: de 41000 para arriba la energia
# cobra o niega un premio HOY (remates, pivotes de retirada, gusteo ganador) y
# ninguna consideracion de desarrollo la toca. Documentado ya en los comentarios
# de RIPEN_HEAL_* y de la familia `_carga_activo_*`; aqui se le pone nombre para
# que el techo de la Fase C sepa donde parar.
SCORE_CARGA_LETAL_FLOOR = 41000

# Score de FLIP THE SCRIPT (Fezandipiti ex: robar 3 tras un KO nuestro). Va por
# ENCIMA de toda la familia de habilidades de CARGA no letales -- Teal Dance
# (29000-31500) y Ripening Charge (30500-31600) -- porque es GRATIS, es UNA VEZ
# POR TURNO y su condicion muere con el turno, mientras que un adjunte que no
# remata se puede hacer despues sin perder nada. Ademas robar PRIMERO decide
# mejor los adjuntes: las 3 cartas nuevas pueden ser Plantas. Por debajo de las
# bandas LETALES (41000+) y del remate ganador. >= 29000 para subir al tier
# ENERGY (si se quedara en tier 0, cualquier carga lo pisaria por ORDEN).
FEZ_DRAW_ABILITY_SCORE = 31700

# --- ATACAR CON EL ACTIVO ES LO PRIMERO -------------------------------------
# Bandas de la familia `_carga_activo_*` (ver los flags homonimos en agent()):
# cargar al ACTIVO hasta su COSTE DE ATAQUE usando TODAS las vias de carga que
# quedan vivas este turno (adjunte manual + habilidades de carga).
#
# `_carga_activo_remata` (el ataque resultante NOQUEA al activo rival): 41900.
# Por encima de TODAS las cargas letales "indirectas" -- promover un atacante
# de banca (41000), el foco de carga de un Ogerpon (41700) -- porque atacar con
# el ACTIVO no paga coste de retirada ni depende de que la retirada sea legal.
# Por debajo del remate GANADOR via Boss's (42000) y del atacante de 1 premio
# vs Alakazam (43000), que resuelven la partida / el intercambio de premios.
SCORE_CARGA_ACTIVO_REMATE = 41900
# `_carga_activo_habilita_ataque` (el ataque no remata pero hace CHIP y sin esa
# carga el turno seria ESTERIL): 31300. Su valor NO esta en ganar pulsos, sino
# en SALTARSE las ramas de energy_score que degradaban la carga al activo (el
# `score - 100` de `active_ko_likely`, el veto de `_active_hydra_capped`, los
# topes por matchup, el downgrade a 7500...). Por eso se queda en una banda
# deliberadamente MODESTA: sobre el adjunte de desarrollo al activo (~31210) y
# sobre `_attach_enable_retreat_attack` (31200), pero BAJO el motor
# UB->Meowth->Lillie's (31450) y Teal Dance (31500) -- con un turno sin remate
# a la vista, refrescar la mano o robar sigue mandando sobre un chip. Sin KO no
# hay prisa: el adjunte del turno sigue vivo despues de esas jugadas.
SCORE_CARGA_ACTIVO_ATAQUE = 31300

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
# Linea Rocket's Mewtwo (limitless /decks/337, analizado julio 2026): el motor
# de dano barato del mazo es Team Rocket's Tarountula (400, 50 HP) -> Team
# Rocket's Spidops (401, Stage 1, linea 4-4); Team Rocket's Mewtwo ex (431,
# 280 HP, Erasure Ball 160) es el finisher de 2 premios (cubierto por el
# gusteo generico de 2 premios). Cortar los Tarountula con Boss's frena su
# tempo igual que Riolu/Duraludon.
Rockets_Tarountula = 400
Rockets_Spidops = 401
Rockets_Mewtwo_ex = 431

THREAT_PREEVO_IDS = {Riolu, Duraludon, Hops_Phantump, Dwebble_Grass, Dwebble_Fighting,
                     Buneary, Rockets_Tarountula}

# Dunsparce (id 65 = TEF, id 305 = JTG): NUNCA gustear con Boss's Orders (user
# req). Son muros que se retiran/reposicionan con facilidad; subirlos al activo
# rival con Boss's Orders no aporta ventaja.
DUNSPARCE_IDS = {65, 305}

# Pokemon clave de cada mazo que conviene noquear con Boss's Orders desde la
# banca AUNQUE nuestro activo pueda noquear al activo rival, cuando ese activo
# rival NO es un Pokemon clave (p.ej. un muro sin energia). Ej.: en el mazo Hop
# el atacante clave es Hop's Trevenant; su linea (Trevenant/Phantump) debe
# cazarse en banca. La prioridad entre objetivos (con/sin energia, evolucion vs
# pre-evo) la resuelve el ajuste tier_ko (_AJUSTES_GUST_OFENSIVO) al elegir objetivo:
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
    # Linea Cynthia's Garchomp ex (user, registro_006 paso 82 vs Garchomp,
    # GANADA con error): la linea NO estaba en este set, asi que el deny-evo
    # de Boss's (`_bo_pe_is_ex_preevo_energized` / `_bo_pe_is_ex_line_vs_wall`)
    # jamas disparaba: con Tapu Bulu listo, Boss's en mano y un Gabite
    # ENERGIZADO en la banca rival, el agente noqueaba al muro Spiritomb en
    # vez de gustear+noquear el Gabite (pre-evo del atacante ex de 2 premios).
    # Privilegiar SIEMPRE cortar la linea evolutiva de Cynthia's Garchomp ex.
    Cynthias_Gible, Cynthias_Gabite,
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
    Raging_Bolt_ex: "Raging Bolt", Snover: "Snover",
    Mega_Abomasnow_ex: "Abomasnow", Dusknoir: "Dusknoir", Duskull: "Duskull",
    Dusclops: "Dusclops", Typhlosion: "Typhlosion", Cyndaquil: "Cyndaquil",
    Quilava: "Quilava", Drednaw: "Drednaw", Chewtle: "Chewtle",
}


SCORE_WIN_GAME = 50000

# Anclas BASE de la rama PLAY: puntaje de partida antes de ajustes por matchup /
# situacion. El resto de scores de desarrollo se leen como "base +/- matiz".
SCORE_DEVELOP_BASE = 20000   # base: bajar un Pokemon a la banca
SCORE_ITEM_BASE = 10000      # base: jugar una carta que NO es Pokemon (item/supporter)
# Base del valor generico de un Supporter (Boss's/Lana's/Dawn): score = BASE +
# int(valor * 1.4) + supporter_boost. Usada por los 3 scorers de Supporter.
SCORE_SUPPORTER_VALUE_BASE = 2400

# --- Pisos de puntuacion (score floors) ---
# Escala de valores negativos CON NOMBRE (robustez): dejan explicito el orden de
# "no jugar" y evitan que una jugada real quede por debajo de un piso por error.
# Migracion incremental de numeros magicos -> constantes; los valores son EXACTOS
# a los que ya se usaban (renombrado puro, sin cambio de comportamiento).
SCORE_VETO = -1          # jugada vetada / inutil (piso general, el mas comun)
SCORE_CANCEL = -100      # cancelar por debajo del piso de veto (p.ej. Ultra Ball
                         # inutil) para que el desempate por indice no la elija
SCORE_USELESS_ATTACK = -5000  # atacar por 0 dano (rival inmune: ex/habilidad/muro)
SCORE_NEVER = -10000     # nunca (p.ej. no descartar Unfair Stamp; END no letal)
SCORE_FORBID = -100000   # prohibido absoluto (Dunsparce, retirada gratis)

SCORE_LOOKAHEAD_EX_TRADE = 250
SCORE_LOOKAHEAD_KO_TRADE = 120
SCORE_LOOKAHEAD_SAFE = 60
SCORE_LOOKAHEAD_PROMOTE_KO = 120
SCORE_LOOKAHEAD_PROMOTE_SAFE = 40

SCORE_BELIEF_DIG_ENERGY = 250

# --- Escala de la RECUPERACION de Lana's Aid (contexto TO_HAND) --------------
# Lana's levanta hasta 3 cartas del descarte entre Pokemon SIN Regla y Energias
# Basicas. La eleccion la manda la lectura de mesa de `_plan_de_planta`: primero
# la Planta que pone a atacar HOY, luego las que un cuerpo en juego sigue
# pidiendo, y solo despues el desarrollo (que puntua el scorer generico, en la
# banda ~150-280). Ver `_pokemon_injugable` para el piso de carta muerta.
LANA_SEL_PLANTA_DESBLOQUEA = 1400  # la Planta que habilita un ataque este turno
LANA_SEL_PLANTA_DEMANDA = 900      # Planta que un atacante en juego aun pide
LANA_SEL_PLANTA_SOBRANTE = 120     # mas Plantas de las que la mesa sabe usar
LANA_SEL_INJUGABLE = 5             # no se puede poner en juego: ultimo recurso

# Valor BASE de la capa PLAY por tener algo recuperable en el descarte, antes de
# los bonos de necesidad (banca corta, linea caida, Forest, >=3 recuperables,
# matchup). Que `lana_val` se quede EXACTAMENTE en esta base significa "hay una
# carta ahi abajo, pero la mesa no la pide".
LANA_PLAY_BASE_RECUPERABLE = 300

# Techo del VALOR de jugar Lana's Aid (capa PLAY) cuando lo que se puede poner
# en juego hoy no hace falta: Energia que nadie pide (todos los atacantes en
# juego llegan ya a `ATTACK_ENERGY_REQ`, o la mano tiene mas Plantas de las que
# caben este turno) o un Pokemon que cabe en la banca pero que ningun bono
# reclama. Con `SCORE_SUPPORTER_VALUE_BASE` = 2400 y el factor 1.4, deja la
# jugada en ~2540: sigue siendo jugable, pero cede el Supporter del turno a
# cualquier otro con valor real (Dawn generico ~2680, Lillie's 5000).
LANA_PLAY_SIN_DEMANDA = 100

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
BOSS_SCORE_GUST_2PRIZE = 6800        # gustear+noquear un ex de banca por 2 premios (mas que el KO del activo de 1); supera retiradas/pivotes (~6600)
BOSS_SCORE_WIN_VIA_BENCH = 5600      # gustada letal a un objetivo de banca
BOSS_SCORE_WALL_GUST = 5500          # rival con muro inmune (ex/habilidad) al activo
BOSS_SCORE_DODGE_REDIRECT = 5500     # redireccion por esquiva (dodge)
BOSS_SCORE_PRIZE_RANK_BASE = 5200    # gusteo que habilita KO (afinado por prize_rank)
BOSS_SCORE_LOW_VALUE_GUST = 1500     # gusteo de bajo valor
BOSS_SCORE_DEFENSIVE_GUST = 1500     # gusteo defensivo (vs Crustle)
BOSS_SCORE_UNLOCK_GUST = 2600        # gustear para DES-LOCKEAR habilidades (Iron Thorns ex activo)
BOSS_SCORE_EMPTY_GUST = 20           # gusteo NO ejecutable: ceder a Lillie's
XEROSIC_SCORE_ALAKAZAM = 5900        # Xerosic vs Alakazam: capar Powerful Hand (20 x mano rival). Sobre Lillie's hydra-cargado (5800); bajo GUST_2PRIZE (6800) y pivotes defensivos (~6600). Cede a boss_win_via_bench via guard propio
XEROSIC_SCORE_GENERIC = 3380         # Xerosic generico con mano rival muy grande (>=7): valor de disrupcion, bajo Lillie's tipico (~3450)
XEROSIC_SCORE_LAST_RESORT = 20       # sin efecto util claro: solo si ningun otro supporter puntua
XEROSIC_SCORE_SOBRE_BOSS = 7000      # vs Alakazam con Boss's en mano: capar la mano supera a CUALQUIER gusteo que no GANE la partida (sobre GUST_2PRIZE 6800); el gusteo ganador (WIN_NOW 20000) sigue por encima
# --- PESCA DE REMATE (ver `_pesca_de_remate`) --------------------------------
# Lillie's Determination cuando el turno NO tiene ataque posible y el robo puede
# traer la energia que desbloquea un KO. Se coloca por encima de todo el ladder
# de Boss's que no GANA la partida ni cobra 2 premios YA (GUST_2PRIZE 6800) y
# por encima del Lillie's hydra-cargado (5800): un KO probable de 2 premios vale
# mas que cualquier gusteo de desarrollo, y ademas gustear DEGRADA el objetivo
# (Myriad Leaf Shower escala con la energia del activo rival).
LILLIE_SCORE_PESCA_REMATE = 5900
# Probabilidad minima para que la pesca ANULE los vetos de orden de Lillie's
# (Ultra Ball que completa linea, cesion a un gusteo ejecutable...). El caso que
# la motiva sale a 0.63 (2 Plantas de 10 vivas robando 8 de 42). Por debajo de
# este umbral el refresco sigue jugandose por su valor normal, sin privilegios.
PESCA_PROB_MIN = 0.35
# Premios minimos del KO pescado: la pesca solo pisa los vetos si lo que
# desbloquea COBRA premio (un chip probable no paga barajar la mano).
PESCA_PREMIOS_MIN = 1



XEROSIC_STAMP_ORDEN_MIN_OP_HAND = 10  # mano rival minima para que Xerosic se juegue ANTES del Unfair Stamp: el Sello los deja en 2 igual, asi que lo unico que gana el orden son las `op_hand - 3` cartas que Xerosic manda al descarte PARA SIEMPRE; solo vale el hueco de Supporter cuando eso supera una mano entera (>=7 cartas)

# --- Unfair Stamp: cuando el Sello MERECE jugarse (user, agosto 2026) --------
# El Sello es un ACE SPEC (Item) que baraja LAS DOS manos al mazo y reparte 5
# cartas a nosotros y 2 al rival. Solo tiene dos formas de pagar, y la regla
# exige que se cumpla AL MENOS UNA (es regla de CARTA, no de matchup: vale
# contra cualquier mazo):
#
#   (1) DISRUPCION -- solo existe si al rival le QUITA cartas. Como lo deja
#       exactamente en 2, con la mano rival <= 2 no le quita nada; con 1 carta
#       hasta le REGALA una (registro_006 paso 99 vs Marnie: rival con 1 carta,
#       el Sello lo dejo en 2).
#   (2) REFRESCO -- robamos 5, pero antes barajamos TODA nuestra mano al mazo.
#       Sale a cuenta mientras lo que se sacrifica (la mano SIN el propio Sello)
#       sea <= 4 cartas; por encima de eso el Sello quema mas recursos jugables
#       de los que devuelve.
STAMP_MIN_OP_HAND = 3          # mano rival minima para que el Sello DISRUMPA (lo deja en 2)
STAMP_MAX_HAND_SACRIFICADA = 4  # cartas propias (mano sin el Sello) que se pueden barajar


__all__ = [
    'RETREAT_COST',
    'Teal_Mask_Ogerpon_ex',
    'Chikorita',
    'Bayleef',
    'Meganium',
    'Applin',
    'Dipplin',
    'Hydrapple_ex',
    'Meowth_ex',
    'Fezandipiti_ex',
    'Tapu_Bulu',
    'Pinsir',
    'Lillie_Determination',
    'Boss_Orders',
    'Lanas_Aid',
    'Xerosic_Machinations',
    'Dawn',
    'Bug_Catching_Set',
    'Ultra_Ball',
    'Night_Stretcher',
    'Unfair_Stamp',
    'Poke_Pad',
    'Forest_of_Vitality',
    'Neutralization_Zone',
    'Team_Rockets_Watchtower',
    'Festival_Grounds',
    'Grand_Tree',
    'Maximum_Belt',
    'Brave_Bangle',
    'Basic_Grass_Energy',
    'Budew',
    'Crustle_Grass',
    'Dwebble_Grass',
    'Crustle_Fighting',
    'Dwebble_Fighting',
    'Sylveon',
    'Comfey',
    'Bramblin',
    'Brambleghast',
    'Munkidori',
    'Froslass',
    'Snorunt',
    'Dragapult_ex',
    'Dreepy',
    'Drakloak',
    'Iron_Thorns_ex',
    'Charizard_ex',
    'Grimmsnarl_ex',
    'Marnies_Impidimp',
    'Marnies_Morgrem',
    'Latias_ex',
    'Cornerstone_Mask_Ogerpon_ex',
    'Cornerstone_Mask_Ogerpon',
    'Mega_Kangaskhan_ex',
    'Hops_Phantump',
    'Hops_Trevenant',
    'Splashing_Dodge_Atk',
    'COIN_FLIP_LOG_TYPE',
    'Mega_Greninja_ex',
    'Mega_Starmie_ex',
    'Slowking',
    'Slowpoke',
    'Beedrill',
    'Weedle',
    'Kakuna',
    'Zoroark_N',
    'Zorua_N',
    'Alakazam_ex',
    'Abra',
    'Kadabra',
    'POWERFUL_HAND_ATTACK_ID',
    'DO_THE_WAVE_ATTACK_ID',
    'FESTIVAL_LEAD_IDS',
    'ALAKAZAM_LINE_IDS',
    'ALAKAZAM_ATTACKER_IDS',
    'Buneary',
    'Mega_Lopunny_ex',
    'Cynthias_Gible',
    'Cynthias_Gabite',
    'Cynthias_Garchomp_ex',
    'Gardevoir_ex',
    'Ralts',
    'Kirlia',
    'Raging_Bolt_ex',
    'Lugia_VSTAR',
    'Snover',
    'Mega_Abomasnow_ex',
    'Dusknoir',
    'Duskull',
    'Dusclops',
    'Typhlosion',
    'Cyndaquil',
    'Quilava',
    'Drednaw',
    'Chewtle',
    'Cubchoo',
    'Beartic',
    'Eevee_TWM',
    'Eevee_SFA',
    'Eevee_PRE_ex',
    'Eevee_SSP',
    'EEVEE_IDS',
    'OUR_EX_IDS',
    'DECK_ITEM_IDS',
    'EX_IMMUNE_IDS',
    'CRUSTLE_LINE_IDS',
    'ABILITY_IMMUNE_IDS',
    'OUR_ABILITY_IDS',
    'GUST_TRAMPA_IDS',
    'Pikachu_ex_Resolute',
    'FULL_HP_SURVIVE_IDS',
    'Mega_Hawlucha_ex',
    'Survival_Brace',
    'Farigiraf_ex',
    'OUR_BASIC_EX_IDS',
    'CUBCHOO_ALLOWED_PLAY_IDS',
    'Jellicent_ex',
    'Tyranitar_Daunting',
    'Galvantula_ex',
    'FULGURITE_ATTACK_ID',
    'OP_ITEM_LOCK_ACTIVE_IDS',
    'OUR_RULEBOX_ABILITY_IDS',
    'Munkidori_ex',
    'Pecharunt_ex',
    'Mega_Gengar_ex',
    'OP_BENCH_BURST',
    'OP_BENCH_SNIPE_DAMAGE',
    'OP_BENCH_SNIPE_DEFAULT',
    'FREEZING_SHROUD_COUNTER',
    'CHECKUPS_PER_ROUND',
    'ADRENA_BRAIN_MOVE',
    'RIPENING_HEAL',
    'RIPEN_HEAL_TARGET_SCORE',
    'RIPEN_HEAL_ABILITY_SCORE',
    'RIPEN_HEAL_EX_ABILITY_SCORE',
    'SCORE_CARGA_CONDENADA',
    'SCORE_CARGA_LETAL_FLOOR',
    'FEZ_DRAW_ABILITY_SCORE',
    'SCORE_CARGA_ACTIVO_REMATE',
    'SCORE_CARGA_ACTIVO_ATAQUE',
    'NON_ATTACKER_ENERGY_WASTE_IDS',
    'HIGH_PRIORITY_BENCH_TARGETS',
    'META_BENCH_TARGETS',
    'FIRE_POKEMON_IDS',
    'WATER_SNIPE_IDS',
    'PSYCHIC_CONTROL_IDS',
    'Riolu',
    'Mega_Lucario_ex',
    'Duraludon',
    'Rockets_Tarountula',
    'Rockets_Spidops',
    'Rockets_Mewtwo_ex',
    'THREAT_PREEVO_IDS',
    'DUNSPARCE_IDS',
    'KEY_BENCH_ATTACKER_IDS',
    'EX_PREEVO_IDS',
    'NONEX_FINAL_PREEVO_IDS',
    '_ID_NAME_EXPECTATIONS',
    'SCORE_WIN_GAME',
    'SCORE_DEVELOP_BASE',
    'SCORE_ITEM_BASE',
    'SCORE_SUPPORTER_VALUE_BASE',
    'SCORE_VETO',
    'SCORE_CANCEL',
    'SCORE_USELESS_ATTACK',
    'SCORE_NEVER',
    'SCORE_FORBID',
    'SCORE_LOOKAHEAD_EX_TRADE',
    'SCORE_LOOKAHEAD_KO_TRADE',
    'SCORE_LOOKAHEAD_SAFE',
    'SCORE_LOOKAHEAD_PROMOTE_KO',
    'SCORE_LOOKAHEAD_PROMOTE_SAFE',
    'SCORE_BELIEF_DIG_ENERGY',
    'LANA_SEL_PLANTA_DESBLOQUEA',
    'LANA_SEL_PLANTA_DEMANDA',
    'LANA_SEL_PLANTA_SOBRANTE',
    'LANA_SEL_INJUGABLE',
    'LANA_PLAY_BASE_RECUPERABLE',
    'LANA_PLAY_SIN_DEMANDA',
    'BOSS_PRIORITY_CRUSTLE_GUST',
    'TAPU_WAIT_FOR_ITEMS_SCORE',
    'BOSS_SCORE_WIN_NOW',
    'BOSS_SCORE_GUST_2PRIZE',
    'BOSS_SCORE_WIN_VIA_BENCH',
    'BOSS_SCORE_WALL_GUST',
    'BOSS_SCORE_DODGE_REDIRECT',
    'BOSS_SCORE_PRIZE_RANK_BASE',
    'BOSS_SCORE_LOW_VALUE_GUST',
    'BOSS_SCORE_DEFENSIVE_GUST',
    'BOSS_SCORE_UNLOCK_GUST',
    'BOSS_SCORE_EMPTY_GUST',
    'XEROSIC_SCORE_ALAKAZAM',
    'XEROSIC_SCORE_GENERIC',
    'XEROSIC_SCORE_LAST_RESORT',
    'XEROSIC_SCORE_SOBRE_BOSS',
    'LILLIE_SCORE_PESCA_REMATE',
    'PESCA_PROB_MIN',
    'PESCA_PREMIOS_MIN',
    'XEROSIC_STAMP_ORDEN_MIN_OP_HAND',
    'STAMP_MIN_OP_HAND',
    'STAMP_MAX_HAND_SACRIFICADA',
]
