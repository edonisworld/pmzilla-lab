# Évolution du flux : serie-x, du 2026-09-04 au 2026-10-04

Compare les rapports du 2026-09-04 et du 2026-10-04 (30 jours d'écart), calculés en local à partir de deux exports Jira. Agrégats seulement : aucun ticket n'est cité ni suivi.

## Ce qui a bougé

- Débit en hausse : 4.2 éléments par semaine sur les 4 semaine(s) nouvelle(s), contre 2.0 sur les 4 semaines d'avant (+112%).
- Loi de Little : un élément resterait en cours environ 157 jours, contre 207 (-24%).
- Plus d'éléments en cours depuis plus de 90 jours : 26 → 27.
- Plus d'éléments en cours plus âgés que le lead time P85 : 21 → 27.
- File « Backlog » : plus d'éléments à faire depuis plus de 90 jours, 4 → 7.
- (sans équipe) : clôtures groupées sur les 8 dernières semaines (62% des éléments terminés sur 2 semaines).
- Equipe B : débit en hausse, 0.2 → 1.0 par semaine (+300%).
- Equipe B : clôtures groupées sur les 8 dernières semaines (80% des éléments terminés sur 2 semaines).
- Equipe C : débit en hausse, 0.2 → 1.8 par semaine (+600%).

Seuils : débit ±25% (±30% par équipe), lead time P85 ±20%, WIP et loi de Little ±20%, toute hausse du vieillissement (au moins 3 éléments de plus de 90 jours en plus pour une équipe) ; clôtures groupées quand 2 semaines portent au moins 60% des éléments terminés des 8 dernières semaines. Chaque signal est une question à poser aux équipes, pas une conclusion.

## Débit

- Semaines nouvelles (4) : 4.2 par semaine, contre 2.0 sur les 4 dernières semaines du rapport précédent.
- Moyenne sur toute la fenêtre : 1.7 → 2.2 (+32%) ; semaines à zéro : 3 → 2.
- Série du nouveau rapport, de la plus ancienne à la plus récente : 1, 2, 0, 3, 1, 1, 0, 2, 2, 2, 4, 1, 2, 6, 2, 2, 1, 1, 2, 2, 1, 3, 3, 5, 1, 8.

## Lead time (de la création à la résolution)

| Périmètre | P50 | P85 |
|---|---|---|
| Tous types | 49 j → 45 j (-8%) | 98 j → 98 j (+0%) |
| Bug | 52 j → 52 j (-1%) | 105 j → 105 j (-0%) |
| Story | 34 j → 42 j (+23%) | 91 j → 98 j (+8%) |
| Task | 64 j → 50 j (-22%) | 101 j → 98 j (-3%) |

## Travail en cours

- En cours : 50 → 50 (+0%) ; à faire : 33 → 33 (+0%).
- Loi de Little : 207 j → 157 j (-24%).

| État | Avant | Après |
|---|---|---|
| In Review | 23 | 23 |
| Testing | 14 | 14 |
| In Progress | 13 | 13 |

## Vieillissement des éléments en cours

| En cours depuis plus de | Avant | Après |
|---|---|---|
| 30 jours | 33 | 41 |
| 90 jours | 26 | 27 |
| 180 jours | 6 | 10 |
| 365 jours | 0 | 0 |
| 730 jours | 0 | 0 |
| plus que le lead time P85 | 21 | 27 |

## Files avant engagement

| État à faire | Éléments | Âge P50 depuis la création | Plus de 90 j |
|---|---|---|---|
| Open | 15 → 15 (+0%) | 106 j → 136 j (+28%) | 9 → 11 |
| Backlog | 12 → 12 (+0%) | 86 j → 116 j (+35%) | 4 → 7 |
| To Do | 6 → 6 (+0%) | 145 j → 175 j (+21%) | 5 → 5 |

## Par équipe

| Équipe | Débit récent / sem. | Lead time P85 | WIP | WIP > 90 j | Clôtures sur 2 semaines |
|---|---|---|---|---|---|
| (sans équipe) | 1.0 → 1.0 (+0%) | 99 j → 100 j (+1%) | 11 → 11 (+0%) | 3 → 3 | 38% → 62% (groupées) |
| Equipe A | 0.5 → 0.5 (+0%) | 93 j → 98 j (+5%) | 13 → 13 (+0%) | 9 → 9 | n/d → n/d |
| Equipe B | 0.2 → 1.0 (+300%) | 100 j → 96 j (-3%) | 13 → 13 (+0%) | 7 → 7 | n/d → 80% (groupées) |
| Equipe C | 0.2 → 1.8 (+600%) | 35 j → 92 j (+163%) | 13 → 13 (+0%) | 7 → 8 | n/d → 50% |

« Clôtures sur 2 semaines » : part des éléments terminés sur les 8 dernières semaines de chaque rapport qui tombent sur ses 2 meilleures semaines (n/d sous 5 éléments terminés).

## Prévisions

- Terminer 50 éléments, 85 % de chances : 34 sem. → 27 sem. (-21%).

## Limites

- Les deux fenêtres se chevauchent : sur les semaines communes, c'est la même donnée. Seules les semaines nouvelles disent ce qui a changé dans le débit.
- Les comptes sont nets : un élément sorti du WIP et un autre entré s'annulent. Le script ne garde aucun identifiant de ticket, il ne peut donc pas dire quels éléments ont franchi un seuil.
- Par équipe, les séries sont courtes : un écart d'une ou deux unités suffit à franchir un seuil.
