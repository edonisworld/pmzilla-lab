#!/bin/bash
# PMZilla Lab : étapes de la passe de bout en bout de Mothra (change ci-local-runner, design D2 phase 3, tâches 9.1 et 9.2 ; R-20261101-113).
#
# Fichier de fonctions : on le SOURCE, on ne le lance pas ; au chargement il n'écrit rien et ne lance rien. Deux appelants :
#   - tools/dbtest.sh (--e2e), qui source celui de SON arbre, donne une fonction SQL qui passe par le conteneur jetable (exec dans le conteneur, client
#     psql) et garde ses phrases, ses codes (1 et 4) et son empreinte ;
#   - ci/passage.sh (phase e2e), devant lequel tools/ci_local.sh concatène CE fichier, lu dans le dépôt de l'outil et jamais dans l'arbre testé (R-94,
#     R-20261101-113) ; sa fonction SQL passe par psycopg (SQL et secret sur l'entrée standard, mot de passe lu par Python dans l'environnement, jamais
#     développé par le shell), car le conteneur des suites n'a ni socket Docker ni client psql.
# Remplace : le bloc « passe de bout en bout » de tools/dbtest.sh (lignes 309 à 399 avant ce change), déplacé ici sans changer le comportement de
# dbtest. Retrait : permanent, tant que dbtest.sh et la CI lancent la même passe (une seule copie des étapes).
#
# Les fonctions RENDENT un code, jamais exit : l'appelant décide de sa sortie.
#
#     bash tools/e2e_steps.sh    ne fait rien (fichier de fonctions à sourcer) : aucun Docker, aucune base, aucun serveur
#
# Code de sortie : 0, lancé directement comme sourcé.
#
# Paramètres, posés par l'appelant avant e2e_enchainer :
#   E2E_PORT_BASE      port de PostgreSQL de la base jetable          E2E_PORT_SERVEUR   port du serveur Mothra (127.0.0.1)
#   E2E_ATTENTE        secondes d'attente du serveur au plus          E2E_RACINE         racine de l'arbre (listes factices de noms)
#   E2E_VARIABLES_BASE tableau d'affectations NOM=valeur pour les migrations et le chargeur (port, repère, mot de passe si l'appelant le donne)
#   e2e_sql            fonction de l'appelant : exécute en superutilisateur le SQL reçu sur l'entrée standard, rend un code, n'affiche rien
#   E2E_SORTIE_PASSE   (facultatif) fichier où e2e_passe garde aussi la sortie de la passe (ci/passage.sh y lit « N passed », R-20261103-6)
#   e2e_retraits       (ce fichier) pose E2E_RETRAIT, E2E_RETRAIT_BASE et E2E_RETRAIT_SERVEUR d'après l'environnement : les variables
#                      PMZILLA_LAB_DB_* et MOTHRA_* sont retirées de chaque commande (le serveur garde seulement les mots de passe des rôles qu'on lui pose)
# Pour les tests, chacune remplace une étape par un programme unique : E2E_CMD_MIGRER, E2E_CMD_CHARGEUR, E2E_CMD_BUILD, E2E_CMD_SERVEUR (reste au
# premier plan), E2E_CMD_SONDE (reçoit le port du serveur), E2E_CMD_PASSE. Aucune n'est posée dans le conteneur de la CI.
# Sorties : E2E_CAUSE (vide si la passe est verte, sinon migrations, jeu synthétique, rôle des vues, rôle de stockage, construction du bundle,
# serveur ou passe) et E2E_RC (code de la commande en échec).

e2e_sonde_serveur() { # réussit si quelque chose écoute sur le port du serveur (la sonde ne prouve que cela)
  if [ -n "${E2E_CMD_SONDE:-}" ]; then "$E2E_CMD_SONDE" "$E2E_PORT_SERVEUR" >/dev/null 2>&1
  else ( exec 3<>"/dev/tcp/127.0.0.1/$E2E_PORT_SERVEUR" ) 2>/dev/null; fi
}

e2e_retraits() { # E2E_RETRAIT (build, passe), E2E_RETRAIT_BASE (migrations, chargeur : le mot de passe du superutilisateur n'est pas retiré, l'appelant le pose
                 # ou l'environnement le porte déjà), E2E_RETRAIT_SERVEUR (comme E2E_RETRAIT, sauf les deux mots de passe de rôle, que le serveur reçoit)
  local variable
  E2E_RETRAIT=(-u PMZILLA_NO_EVALS -u DBTEST_PORT)
  E2E_RETRAIT_BASE=(-u PMZILLA_NO_EVALS -u DBTEST_PORT)
  E2E_RETRAIT_SERVEUR=(-u PMZILLA_NO_EVALS -u DBTEST_PORT)
  while IFS= read -r variable; do
    [ -n "$variable" ] || continue
    E2E_RETRAIT+=(-u "$variable")
    [ "$variable" = "PMZILLA_LAB_DB_PASSWORD" ] || E2E_RETRAIT_BASE+=(-u "$variable")
    [ "$variable" = "PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA_VIEWS" ] || [ "$variable" = "PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA" ] || E2E_RETRAIT_SERVEUR+=(-u "$variable")
  done < <(compgen -e PMZILLA_LAB_DB_)
  while IFS= read -r variable; do
    [ -n "$variable" ] || continue
    E2E_RETRAIT+=(-u "$variable"); E2E_RETRAIT_BASE+=(-u "$variable"); E2E_RETRAIT_SERVEUR+=(-u "$variable")
  done < <(compgen -e MOTHRA_)
}

e2e_secrets() { # mots de passe aléatoires des deux rôles : posés dans la base par e2e_sql, passés au serveur par préfixe d'affectation, jamais affichés
  E2E_SECRET_VUES="$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')"
  E2E_SECRET_STOCKAGE="$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')"
}

e2e_migrer() {
  if [ -n "${E2E_CMD_MIGRER:-}" ]; then env "${E2E_RETRAIT_BASE[@]}" "${E2E_VARIABLES_BASE[@]}" "$E2E_CMD_MIGRER"
  else env "${E2E_RETRAIT_BASE[@]}" "${E2E_VARIABLES_BASE[@]}" uv run tools/db.py migrate; fi
}

e2e_charger() {
  if [ -n "${E2E_CMD_CHARGEUR:-}" ]; then env "${E2E_RETRAIT_BASE[@]}" "${E2E_VARIABLES_BASE[@]}" "$E2E_CMD_CHARGEUR"
  else env "${E2E_RETRAIT_BASE[@]}" "${E2E_VARIABLES_BASE[@]}" uv run --with "psycopg[binary]" python tests/mothra_donnees/jeu_synthetique.py; fi
}

# Les mots de passe des rôles passent par l'entrée standard de e2e_sql (jamais par un argument).
e2e_poser_role_des_vues() {
  [ -n "$E2E_SECRET_VUES" ] || return 1
  e2e_sql <<< "ALTER ROLE pmzilla_mothra_views LOGIN PASSWORD '$E2E_SECRET_VUES';"
}

e2e_poser_role_de_stockage() {
  [ -n "$E2E_SECRET_STOCKAGE" ] || return 1
  # R-20261101-129 (Q270). Même appel SQL que le mot de passe du rôle, pour garder le nombre et l'ordre des appels de e2e_sql (une cause d'échec
  # de plus ne vaut pas un appel de plus) : une ligne datée de l'historique des seuils pour les deux seuils d'échantillon, posée SOUS le rôle de
  # stockage (SET ROLE : INSERT seulement, comme le serveur le fait pour l'Agile Lead), pour que le tableau « lead time » du tableau de bord ait
  # ses seuils (mothra/server/src/fiches/tableau.ts lit ces deux codes). Date 2026-10-27, auteur author-1. Médiane : 5, le plancher de masquage
  # (invariant 2), parce que le jeu synthétique de l'e2e (tests/mothra_donnees/jeu_synthetique.py) n'a que 5, 5, 9 et 5 tickets livrés par équipe :
  # au-dessus de 5, aucune cellule de la colonne médiane ne montre de valeur (R-20261102-5, Q281 (a) ; remplace la valeur 10 de Q270 pour la
  # médiane, dans l'e2e seulement ; retrait : permanent tant que ce jeu est celui de l'e2e). P85 : 20, celle des tests du serveur
  # (mothra/server/test/tableau-reduit.test.ts ligne 51 ; mothra/server/test/db/fiches-calcul.test.ts, SEUILS), qui laisse visible l'état
  # « échantillon insuffisant ». Table : mothra.threshold_history (db/migrations/0024_mothra_schema.sql). Remplace : rien. Retrait : permanent
  # tant que le serveur lit ses seuils dans cet historique.
  # Uniquement dans la base jetable de l'appelant (e2e_sql vise son port) ; rien ne s'écrit sur une vraie base.
  e2e_sql <<< "ALTER ROLE pmzilla_mothra LOGIN PASSWORD '$E2E_SECRET_STOCKAGE'; SET ROLE pmzilla_mothra; INSERT INTO mothra.threshold_history (threshold_code, value, set_on, set_by) VALUES ('sample_median_min_items', 5, DATE '2026-10-27', 'author-1'), ('sample_p85_min_items', 20, DATE '2026-10-27', 'author-1'); RESET ROLE;"
}

e2e_construire() { # bundle construit depuis l'arbre, sous le même environnement nettoyé que le serveur
  if [ -n "${E2E_CMD_BUILD:-}" ]; then env "${E2E_RETRAIT[@]}" "$E2E_CMD_BUILD"; else ( cd mothra && env "${E2E_RETRAIT[@]}" npm run build ); fi
}

e2e_demarrer_serveur() { # E2E_SERVEUR_PID ; le serveur ne lit que le port, le jeu, la base, les deux listes de noms factices de mothra/server/test/listes/
  # (noms inventés, jamais les vraies listes) et les mots de passe des rôles des vues et de stockage, posés par préfixe d'affectation devant exec
  # (jamais en argument de env, donc absents de la liste des processus). Limite : le mot de passe du superutilisateur passe en argument de env aux
  # seules commandes des migrations et du chargeur quand l'appelant le donne dans E2E_VARIABLES_BASE.
  # Sa sortie d'erreur passe sur la sortie standard (2>&1), pour que son refus de démarrage apparaisse dans le rapport du conteneur (seul le stdout
  # passe par tee dans la CI locale). Remplace : rien. Retrait : permanent.
  if [ -n "${E2E_CMD_SERVEUR:-}" ]; then
    ( PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA_VIEWS="$E2E_SECRET_VUES" PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA="$E2E_SECRET_STOCKAGE" \
        exec env "${E2E_RETRAIT_SERVEUR[@]}" DBTEST_PORT="$E2E_PORT_BASE" MOTHRA_PORT="$E2E_PORT_SERVEUR" \
        MOTHRA_DATASET=synthetic MOTHRA_DB_NAME=pmzilla \
        MOTHRA_SENSITIVE_NAMES_FILE="$E2E_RACINE/mothra/server/test/listes/noms-sensibles.txt" \
        MOTHRA_TEAM_NAMES_FILE="$E2E_RACINE/mothra/server/test/listes/equipes-lisibles.yaml" "$E2E_CMD_SERVEUR" 2>&1 ) &
  else
    ( cd mothra/server && PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA_VIEWS="$E2E_SECRET_VUES" PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA="$E2E_SECRET_STOCKAGE" \
        exec env "${E2E_RETRAIT_SERVEUR[@]}" DBTEST_PORT="$E2E_PORT_BASE" \
        MOTHRA_PORT="$E2E_PORT_SERVEUR" MOTHRA_DATASET=synthetic MOTHRA_DB_NAME=pmzilla \
        MOTHRA_SENSITIVE_NAMES_FILE="$E2E_RACINE/mothra/server/test/listes/noms-sensibles.txt" \
        MOTHRA_TEAM_NAMES_FILE="$E2E_RACINE/mothra/server/test/listes/equipes-lisibles.yaml" node src/main.ts 2>&1 ) &
  fi
  E2E_SERVEUR_PID=$!
}

e2e_attendre_serveur() { # 0 : NOTRE serveur écoute ; 1 : il n'écoute pas, ou il s'est arrêté alors que le port répond (phrases dites ici)
  local ecoute=0 i=0
  while [ "$i" -lt "$E2E_ATTENTE" ]; do
    if e2e_sonde_serveur; then ecoute=1; break; fi
    kill -0 "$E2E_SERVEUR_PID" 2>/dev/null || break
    i=$((i + 1)); sleep 1
  done
  if [ "$ecoute" -ne 1 ]; then echo "Le serveur Mothra n'écoute pas (arrêté ou trop lent) ; voir sa sortie ci-dessus"; return 1; fi
  # La sonde a répondu : encore faut-il que ce soit NOTRE serveur (le port a été vérifié libre avant, mais le serveur a pu sortir aussitôt).
  if ! kill -0 "$E2E_SERVEUR_PID" 2>/dev/null; then
    echo "Le serveur Mothra s'est arrêté alors que le port répond : la sonde ne prouve rien, passe en échec, aucune preuve"; return 1
  fi
  return 0
}

e2e_passe() { # tests/run_e2e.sh de l'arbre, sans variable PMZILLA_LAB_DB_* (run_e2e refuse un DBTEST_PORT égal au port de la vraie base)
  # E2E_SORTIE_PASSE (R-20261103-6, Q1) : quand l'appelant la pose (ci/passage.sh), la sortie de la passe est aussi gardée dans ce fichier, pour que la
  # phase e2e lise « N passed » de Playwright ; le code rendu reste celui de la passe. Sans elle (dbtest), rien ne change. Remplace : rien.
  # Retrait : permanent, tant que la phase e2e de ci/passage.sh compte les tests lancés.
  if [ -n "${E2E_SORTIE_PASSE:-}" ]; then
    env "${E2E_RETRAIT[@]}" DBTEST_PORT="$E2E_PORT_BASE" MOTHRA_E2E_URL="http://127.0.0.1:$E2E_PORT_SERVEUR" bash "${E2E_CMD_PASSE:-tests/run_e2e.sh}" 2>&1 | tee "$E2E_SORTIE_PASSE"
    return "${PIPESTATUS[0]}"
  fi
  env "${E2E_RETRAIT[@]}" DBTEST_PORT="$E2E_PORT_BASE" MOTHRA_E2E_URL="http://127.0.0.1:$E2E_PORT_SERVEUR" bash "${E2E_CMD_PASSE:-tests/run_e2e.sh}"
}

e2e_arreter_serveur() { # idempotent : appelée à la fin de la chaîne et, par dbtest, au nettoyage (Ctrl+C compris)
  if [ -n "${E2E_SERVEUR_PID:-}" ]; then
    kill "$E2E_SERVEUR_PID" 2>/dev/null
    wait "$E2E_SERVEUR_PID" 2>/dev/null
    E2E_SERVEUR_PID=""
  fi
}

e2e_clore() { e2e_arreter_serveur; E2E_SECRET_VUES=""; E2E_SECRET_STOCKAGE=""; }

e2e_etape() { # <nom> <commande...> : l'en-tête, puis la commande ; en échec, E2E_CAUSE (le nom), E2E_RC, et 1
  local nom=$1 rc
  shift
  echo; echo "=== $nom ==="
  "$@"; rc=$?
  if [ "$rc" -ne 0 ]; then E2E_CAUSE=$nom; E2E_RC=$rc; return 1; fi
  return 0
}

e2e_enchainer() { # la chaîne complète, dans l'ordre : migrations, jeu synthétique, rôles, bundle, serveur, passe ; 0 si tout est vert
  local rc vert=0
  set +x   # aucune trace des secrets, même si l'appelant a activé xtrace
  E2E_CAUSE=""; E2E_RC=0; E2E_SERVEUR_PID=""
  e2e_secrets
  e2e_etape "migrations" e2e_migrer || { e2e_clore; return 1; }
  e2e_etape "jeu synthétique" e2e_charger || { e2e_clore; return 1; }
  e2e_etape "rôle des vues" e2e_poser_role_des_vues || { e2e_clore; return 1; }
  e2e_etape "rôle de stockage" e2e_poser_role_de_stockage || { e2e_clore; return 1; }
  echo; echo "=== construction du bundle ==="
  e2e_construire; rc=$?
  if [ "$rc" -ne 0 ]; then E2E_CAUSE="construction du bundle"; E2E_RC=$rc; e2e_clore; return 1; fi
  echo; echo "=== serveur Mothra ==="
  e2e_demarrer_serveur
  if ! e2e_attendre_serveur; then E2E_CAUSE="serveur"; E2E_RC=1; e2e_clore; return 1; fi
  echo; echo "=== passe de bout en bout ==="
  e2e_passe; rc=$?
  if [ "$rc" -eq 0 ]; then vert=1; fi
  # Le serveur doit avoir tenu pendant toute la passe : sinon une passe verte ne prouve rien.
  if [ "$vert" -eq 1 ] && ! kill -0 "$E2E_SERVEUR_PID" 2>/dev/null; then
    echo "Le serveur Mothra s'est arrêté pendant la passe : passe en échec, aucune preuve"; vert=0; rc=1
  fi
  e2e_clore
  if [ "$vert" -ne 1 ]; then E2E_CAUSE="passe"; E2E_RC=$rc; return 1; fi
  return 0
}
