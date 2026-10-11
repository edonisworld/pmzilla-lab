$ add
Session recorded: J-20261001-1 · rétro · équipe Alpha
  follow-up J-20261001-1.s1: Reformuler les trois actions avec un critère de fin (Scrum Master, due 2026-10-05)
  follow-up J-20261001-1.s2: Partager le résultat à la direction produit (Product Owner, due 2026-10-20)
  experiment J-20261001-1.x: review on 2026-10-04

$ add
Session recorded: J-20260920-1 · coaching · rôle Product Owner
  follow-up J-20260920-1.s1: Clarifier le critère d'acceptation (Product Owner, due 2026-10-30)

$ add
[exit] Entry refused, nothing was written: Field "constat" is missing or empty.

$ add
[exit] Entry refused, nothing was written: Unknown fields: personne.

$ add
[exit] Entry refused, nothing was written: type: "soirée" is unknown (accepted values: atelier, rétro, coaching, CoP, formation, diagnostic, autre).

$ add
[exit] Entry refused, nothing was written: posture: "magie" is unknown (accepted values: discovery, delivery, scaling, facilitation, aucune).

$ add
[exit] Entry refused, nothing was written: date: 2026-12-01 is in the future; the journal records past sessions.

$ add
[exit] Entry refused, nothing was written: date: expected a date in YYYY-MM-DD format, got "hier".

$ add
[exit] Entry refused, nothing was written: "tente" is longer than 600 characters: summarize it in a few lines.

$ add
[exit] Entry refused, nothing was written: The entry must be a YAML dictionary (see FORMAT in the help).

$ add
[exit] Entry refused, nothing was written: suites[1].echeance: expected a date in YYYY-MM-DD format, got "None".

$ add
[exit] Entry refused, nothing was written: suites[1]: expected quoi, pour, echeance.

$ add
[exit] Entry refused, nothing was written: experience: expected hypothese, signal, bilan_le.

$ add
[exit] Entry refused, nothing was written: Field "pour" is missing or empty.

$ add
[exit] File not found: <tmp>/absent.yaml

$ follow-ups
Follow-ups (open) as of 2026-10-06:
  OVERDUE J-20261001-1.s1 · due 2026-10-05 · Scrum Master · Reformuler les trois actions avec un critère de fin  (session of 2026-10-01, rétro, équipe Alpha)
  J-20261001-1.s2 · due 2026-10-20 · Product Owner · Partager le résultat à la direction produit  (session of 2026-10-01, rétro, équipe Alpha)
  J-20260920-1.s1 · due 2026-10-30 · Product Owner · Clarifier le critère d'acceptation  (session of 2026-09-20, coaching, rôle Product Owner)

Experiments due for review:
  J-20261001-1.x · review planned on 2026-10-04 · équipe Alpha
    hypothesis: Un critère de fin par action augmente la part d'actions terminées.
    expected signal: Au moins deux actions sur trois terminées à la rétro suivante.

$ follow-ups --scope PRODUCT owner
Follow-ups · PRODUCT owner (open) as of 2026-10-06:
  J-20260920-1.s1 · due 2026-10-30 · Product Owner · Clarifier le critère d'acceptation  (session of 2026-09-20, coaching, rôle Product Owner)

$ follow-ups --scope inconnu
Follow-ups · inconnu (open) as of 2026-10-06:
  none

$ follow-ups
Follow-ups (open) as of 2026-10-03:
  J-20261001-1.s1 · due 2026-10-05 · Scrum Master · Reformuler les trois actions avec un critère de fin  (session of 2026-10-01, rétro, équipe Alpha)
  J-20261001-1.s2 · due 2026-10-20 · Product Owner · Partager le résultat à la direction produit  (session of 2026-10-01, rétro, équipe Alpha)
  J-20260920-1.s1 · due 2026-10-30 · Product Owner · Clarifier le critère d'acceptation  (session of 2026-09-20, coaching, rôle Product Owner)

$ update J-20261001-1.s1 faite --note Fait sur place.
Follow-up J-20261001-1.s1: done.

$ update J-20261001-1.s2 abandonnee
Follow-up J-20261001-1.s2: abandoned.

$ update J-20261001-1.x conclue
[exit] --note is required to conclude an experiment: what happened?

$ update J-20261001-1.x faite
[exit] An experiment is concluded: use status "conclue", with the result in --note.

$ update J-20261001-1.s1 conclue
[exit] Status of a follow-up (values as written in the journal): ouverte, faite, abandonnee.

$ update J-1.s9 faite
[exit] Unknown identifier: J-1.s9 (see the command follow-ups --all).

$ update J-20261001-1.x conclue --note Hypothèse confirmée.
Experiment J-20261001-1.x concluded.

$ follow-ups --all
Follow-ups (all) as of 2026-10-06:
  J-20260920-1.s1 · due 2026-10-30 · Product Owner · Clarifier le critère d'acceptation  (session of 2026-09-20, coaching, rôle Product Owner)
  J-20261001-1.s1 [done] · due 2026-10-05 · Scrum Master · Reformuler les trois actions avec un critère de fin  (session of 2026-10-01, rétro, équipe Alpha)
  J-20261001-1.s2 [abandoned] · due 2026-10-20 · Product Owner · Partager le résultat à la direction produit  (session of 2026-10-01, rétro, équipe Alpha)

$ review --since 2026-09-01
# Journal from 2026-09-01 to 2026-10-06: 2 session(s)

Follow-ups: 3 promised · 1 done · 1 abandoned · 1 open, of which 0 overdue.
Experiments: 1 · 1 concluded.

## J-20261001-1 · 2026-10-01 · rétro · équipe Alpha · facilitation
- Tried: Rétrospective en format 4L avec un vote à points.
- Finding: Plus de participation, mais les actions restent vagues.
- Follow-up [done] Reformuler les trois actions avec un critère de fin · Scrum Master · 2026-10-05 (Fait sur place.)
- Follow-up [abandoned] Partager le résultat à la direction produit · Product Owner · 2026-10-20
- Experiment [concluded] Un critère de fin par action augmente la part d'actions terminées. · signal: Au moins deux actions sur trois terminées à la rétro suivante. · result: Hypothèse confirmée.

## J-20260920-1 · 2026-09-20 · coaching · rôle Product Owner · aucune
- Tried: Échange.
- Finding: Clair.
- Follow-up [open] Clarifier le critère d'acceptation · Product Owner · 2026-10-30


$ review --since 2026-09-01 --scope product owner
# Journal from 2026-09-01 to 2026-10-06 · product owner: 1 session(s)

Follow-ups: 1 promised · 0 done · 0 abandoned · 1 open, of which 0 overdue.
Experiments: 0 · 0 concluded.

## J-20260920-1 · 2026-09-20 · coaching · rôle Product Owner · aucune
- Tried: Échange.
- Finding: Clair.
- Follow-up [open] Clarifier le critère d'acceptation · Product Owner · 2026-10-30

