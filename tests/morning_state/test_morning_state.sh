#!/bin/bash
# Test du module de l'état du matin (tools/morning_state.sh, change morning-guard, idée #366, design D1 à D5 et D12) : dossier de données,
# dossier des sauvegardes, journal de la copie, fichier d'état de la copie et horloge remplacés par des variables, tous dans un dossier
# temporaire. Un cas par raison de refus, par ligne permise, la déclaration de report valable le jour même seulement, la preuve par
# le fichier d'état, un état illisible refusé à toute heure après le début, aucune écriture, aucun chemin affiché, les tests statiques
# (nombre de dumps, début du matin) et la bibliothèque sourcée.
# Aucun réseau, ni le vrai dossier du labo, ni le vrai dossier de données, ni les vraies sauvegardes.
# Lancement à la main : bash tests/morning_state/test_morning_state.sh
#
# Variables lues par le module (noms fixés par cette suite) : PMZILLA_LAB_WORKSPACE, PMZILLA_LAB_DATA, DB_BACKUP_SAUVEGARDES,
# OFFSITE_COPY_LOG, OFFSITE_DONNEES, PMZILLA_RUN_NOW, PMZILLA_RUN_MORNING_START.
set -u
unset PMZILLA_SKIP_GREEN_CHECK PMZILLA_NO_EVALS PMZILLA_RUN_MORNING_START   # le début du matin est posé cas par cas (R-104)
export TZ=Europe/Paris
racine="$(cd "$(dirname "$0")/../.." && pwd)"
script="$racine/tools/morning_state.sh"
tmp=$(mktemp -d) || exit 1
trap 'chmod -R u+w "$tmp" 2>/dev/null; rm -rf "$tmp"' EXIT
ok=0; ko=0
SORTIE=""; ERR=""; CODE=0

JOUR="2026-10-14"
HIER="2026-10-13"
DONNEES="$tmp/donnees"; SAUV="$tmp/sauvegardes"; JOURNAL="$tmp/copie.log"; OFF="$tmp/off"; ESPACE="$tmp/espace"; TMPDIR_TEST="$tmp/tmpdir"

verifie() { # description condition-vraie (0 = vrai)
  if [ "$2" -eq 0 ]; then echo "ok : $1"; ok=$((ok+1)); else echo "ECHEC : $1 :: code $CODE :: $SORTIE :: $ERR"; ko=$((ko+1)); fi
}
contient() { printf '%s' "$SORTIE" | grep -qF -- "$1"; }
code_et() { # description code-attendu [phrase]
  local desc=$1 attendu=$2 phrase=${3:-}
  if [ "$CODE" -eq "$attendu" ] && { [ -z "$phrase" ] || contient "$phrase"; }; then
    echo "ok : $desc"; ok=$((ok+1))
  else
    echo "ECHEC : $desc (code $CODE, attendu $attendu, phrase « $phrase ») :: $SORTIE :: $ERR"; ko=$((ko+1))
  fi
}
ne_contient_pas() { # description phrase
  if contient "$2"; then echo "ECHEC : $1 (contient « $2 ») :: $SORTIE"; ko=$((ko+1)); else echo "ok : $1"; ok=$((ok+1)); fi
}

# instant local de 2026-10-14 « HH:MM » en secondes
instant() { date -j -f "%Y-%m-%d %H:%M" "$JOUR $1" +%s 2>/dev/null || date -d "$JOUR $1" +%s; }

# Remise à zéro d'un cas : état du matin entièrement vérifié (veille terminée, 4 dumps, copie prouvée), horloge à l'heure donnée
cas() { # HH:MM
  rm -rf "$DONNEES" "$SAUV" "$JOURNAL" "$OFF" "$ESPACE" "$TMPDIR_TEST"
  mkdir -p "$DONNEES" "$SAUV" "$OFF/offsite" "$ESPACE" "$TMPDIR_TEST"
  heure=$1
  repere termine
  sauvegarde 4
  ligne "07:20:11" "copie créée : db-$JOUR (3 fichiers, 12 Ko)"
}
repere() { # etat [date]
  printf '{"date": "%s", "declencheur": "calendrier", "debut": "07:10", "fin": "07:40", "etat": "%s", "code": 0, "notifie": false, "essais": 0, "reprises": 0}\n' \
    "${2:-$JOUR}" "$1" > "$DONNEES/veille-du-jour.json"
}
sauvegarde() { # nombre de dumps [jour]
  local n=$1 j=${2:-$JOUR} i
  rm -rf "${SAUV:?}/db-$j"; mkdir -p "$SAUV/db-$j"
  for i in $(seq 1 "$n"); do : > "$SAUV/db-$j/schema$i.dump"; done
}
ligne() { # HH:MM:SS message [date] : ligne datée du journal de la copie
  printf '%s %s %s\n' "${3:-$JOUR}" "$1" "$2" >> "$JOURNAL"
}
lance() { # arguments de la commande ; sortie dans SORTIE, ERR et CODE
  SORTIE=$(PMZILLA_LAB_WORKSPACE="$ESPACE" PMZILLA_LAB_DATA="$DONNEES" DB_BACKUP_SAUVEGARDES="$SAUV" OFFSITE_COPY_LOG="$JOURNAL" \
    OFFSITE_DONNEES="$OFF" PMZILLA_RUN_NOW="$(instant "$heure")" HOME="$tmp/maison" TMPDIR="$TMPDIR_TEST" bash "$script" "$@" 2>"$tmp/err"); CODE=$?
  ERR=$(cat "$tmp/err")
}
check() { lance check "$@"; }

# --- avant la fenêtre
cas 06:44; rm -f "$DONNEES/veille-du-jour.json"; rm -rf "$SAUV/db-$JOUR" "$JOURNAL"; check
code_et "avant le début du matin, sans repère du jour : permis" 0 "morning_state : autorisé, avant la fenêtre du matin (début 06:45)"
cas 06:44; check --language en
code_et "avant la fenêtre, en anglais" 0 "morning_state: allowed, before the morning window (start 06:45)"
cas 06:45; rm -f "$DONNEES/veille-du-jour.json"; check
code_et "à 06:45 (borne comprise), sans repère : refusé" 1 "fenêtre du matin depuis 06:45"

# --- tout est vérifié
cas 09:00; check
code_et "veille terminée, 4 dumps, copie créée au journal : permis, copie prouvée" 0 "morning_state : autorisé, état du matin vérifié (veille sans erreur, sauvegarde complète, copie hors du Mac prouvée)"
cas 09:00; check --language en
code_et "état du matin vérifié, en anglais" 0 "morning_state: allowed, morning state verified (watch without error, backup complete, off-site copy proven)"
cas 23:59; check
code_et "tard le soir, tout vérifié : permis" 0 "état du matin vérifié"
cas 09:00; rm -f "$JOURNAL"; ligne "08:15:02" "déjà présente : db-$JOUR"; check
code_et "ligne « déjà présente » datée du jour : copie prouvée" 0 "copie hors du Mac prouvée"
cas 09:00; rm -f "$JOURNAL"; ligne "08:15:02" "copie créée : db-$JOUR"; check
code_et "ligne « copie créée » sans détail, fin de ligne : copie prouvée" 0 "copie hors du Mac prouvée"
cas 09:00; lance --language en check
code_et "l'option de langue est acceptée avant la sous-commande" 0 "morning_state: allowed, morning state verified"

# --- la veille
for etat in echoue interrompu reporte commence; do
  cas 09:00; repere "$etat"; check
  code_et "veille du jour en état $etat : refusée avec l'état" 1 "veille du jour pas terminée sans erreur (état : $etat)"
done
cas 09:00; repere echoue; check --language en
code_et "veille en erreur, en anglais" 1 "today's watch run not ended without error (state: echoue)"
cas 09:00; repere termine "$HIER"; check
code_et "repère d'hier : aucune veille du jour" 1 "veille du jour absente"
cas 09:00; rm -f "$DONNEES/veille-du-jour.json"; check
code_et "aucun fichier de repère : illisible (absent ou illisible)" 1 "état de la veille illisible"
for heure_illisible in 06:45 09:29 09:31 15:00 22:30 23:50; do
  cas "$heure_illisible"; printf 'pas du json' > "$DONNEES/veille-du-jour.json"; check
  code_et "repère illisible à $heure_illisible : refusé, sans heure de repli" 1 "état de la veille illisible"
done
cas 09:00; repere echoue "$HIER"; check --language en
code_et "aucune veille du jour, en anglais" 1 "no watch run today"
cas 09:00; rm -f "$DONNEES/veille-du-jour.json"; check --language en
code_et "repère absent, en anglais" 1 "watch state unreadable"
cas 09:00; repere termine; sed 's/termine/termine /' "$DONNEES/veille-du-jour.json" > "$tmp/x" && mv "$tmp/x" "$DONNEES/veille-du-jour.json"; check
code_et "état mal formé : illisible" 1 "état de la veille illisible"

# --- la sauvegarde
cas 09:00; sauvegarde 2; check
code_et "2 dumps sur 4 : sauvegarde incomplète" 1 "sauvegarde du jour incomplète (2 dump(s) sur 4)"
cas 09:00; sauvegarde 2; check --language en
code_et "2 dumps sur 4, en anglais" 1 "today's backup incomplete (2 of 4 dumps)"
# décision de l'auteur du 2026-10-21 : les trois schémas et le dump partiel de quality (obligatoire depuis le bloc F de R-94)
cas 09:00; rm -rf "$SAUV/db-$JOUR"; mkdir -p "$SAUV/db-$JOUR"
for s in knowledge cases flow quality-sans-texte; do : > "$SAUV/db-$JOUR/$s.dump"; done; check
code_et "4 dumps (trois schémas et le dump partiel de quality) : vérifié" 0 "état du matin vérifié (veille sans erreur, sauvegarde complète"
cas 09:00; rm -rf "$SAUV/db-$JOUR"; mkdir -p "$SAUV/db-$JOUR"
for s in knowledge cases flow; do : > "$SAUV/db-$JOUR/$s.dump"; done; check
code_et "3 dumps (trois schémas, dump partiel de quality manquant) : refusé" 1 "sauvegarde du jour incomplète (3 dump(s) sur 4)"
cas 09:00; sauvegarde 5; check
code_et "5 dumps : pas le nombre attendu" 1 "sauvegarde du jour incomplète (5 dump(s) sur 4)"
cas 09:00; rm -rf "$SAUV/db-$JOUR"; check
code_et "aucun dossier du jour : sauvegarde absente" 1 "sauvegarde du jour absente"
cas 09:00; sauvegarde 4 "$HIER"; rm -rf "$SAUV/db-$JOUR"; check
code_et "dossier d'hier seulement : sauvegarde du jour absente" 1 "sauvegarde du jour absente"
cas 09:00; rm -rf "$SAUV"; check
code_et "dossier des sauvegardes absent : compte comme non complète" 1 "dossier des sauvegardes illisible"
cas 09:00; rm -rf "$SAUV/db-$JOUR"; check --language en
code_et "sauvegarde absente, en anglais" 1 "today's backup missing"
cas 09:00; mkdir -p "$SAUV/db-$JOUR/sous.dump"; rm -f "$SAUV/db-$JOUR/schema4.dump"; check
code_et "un dossier nommé .dump n'est pas un dump" 1 "sauvegarde du jour incomplète (3 dump(s) sur 4)"
cas 09:00; : > "$SAUV/db-$JOUR/notes.txt"; check
code_et "un fichier qui n'est pas un dump n'est pas compté" 0 "état du matin vérifié"
cas 09:00; chmod 000 "$SAUV"; check; chmod 755 "$SAUV"
code_et "dossier des sauvegardes inaccessible : refusé" 1 "dossier des sauvegardes illisible"

# --- la copie hors du Mac
cas 23:30; rm -f "$JOURNAL"; check
code_et "tard le soir, copie ni prouvée ni déclarée : refusé" 1 "copie hors du Mac du jour ni prouvée ni reportée"
cas 09:00; rm -f "$JOURNAL"; check --language en
code_et "copie absente, en anglais" 1 "today's off-site copy neither proven nor postponed"
cas 09:00; rm -f "$JOURNAL"; ligne "08:15:30" "copie reportée déclarée : db-$JOUR : disque chez un tiers"; check
code_et "report déclaré aujourd'hui : permis, copie reportée par déclaration" 0 "copie hors du Mac reportée par déclaration)"
cas 09:00; rm -f "$JOURNAL"; ligne "08:15:30" "copie reportée déclarée : db-$JOUR : disque chez un tiers"; check --language en
code_et "report déclaré, en anglais" 0 "off-site copy postponed by declaration)"
cas 23:00; rm -f "$JOURNAL"; ligne "08:15:30" "copie reportée déclarée : db-$JOUR : disque chez un tiers"; check
code_et "report déclaré, tard le soir : toujours permis" 0 "reportée par déclaration"
cas 09:00; rm -f "$JOURNAL"; ligne "08:15:30" "copie reportée déclarée : db-$HIER : disque chez un tiers" "$HIER"; check
code_et "déclaration d'hier : refusée" 1 "copie hors du Mac du jour ni prouvée ni reportée"
cas 09:00; rm -f "$JOURNAL"; ligne "08:15:30" "copie reportée déclarée : db-$HIER : disque chez un tiers"; check
code_et "ligne d'aujourd'hui qui déclare le report de la sauvegarde d'hier : refusée" 1 "copie hors du Mac du jour ni prouvée ni reportée"
cas 09:00; rm -f "$JOURNAL"; ligne "08:15:30" "disque absent ou verrouillé : copie reportée"; check
code_et "report d'un disque absent, daté du jour : ne compte pas" 1 "copie hors du Mac du jour ni prouvée ni reportée"
cas 09:00; rm -f "$JOURNAL"; printf 'copie créée : db-%s (3 fichiers, 12 Ko)\n' "$JOUR" > "$JOURNAL"; check
code_et "ligne sans date (écrite avant le change) : ne compte pas" 1 "copie hors du Mac du jour ni prouvée ni reportée"
cas 09:00; rm -f "$JOURNAL"; ligne "07:20:11" "copie créée : db-$HIER (3 fichiers, 12 Ko)"; check
code_et "copie de la sauvegarde d'hier, datée du jour : ne compte pas" 1 "copie hors du Mac du jour ni prouvée ni reportée"
cas 09:00; rm -f "$JOURNAL"; ligne "07:20:11" "copie créée : db-$JOUR (3 fichiers, 12 Ko)" "$HIER"; check
code_et "copie de la sauvegarde du jour, ligne datée d'hier : ne compte pas" 1 "copie hors du Mac du jour ni prouvée ni reportée"
cas 09:00; rm -f "$JOURNAL"; ligne "07:20:11" "copie créée : db-${JOUR}1 (3 fichiers, 12 Ko)"; check
code_et "un nom de copie qui prolonge la date : ne compte pas" 1 "copie hors du Mac du jour ni prouvée ni reportée"
cas 09:00; rm -f "$JOURNAL"; ligne "07:20:11" "copie créée : bmad-memory-$JOUR (3 fichiers, 12 Ko)"; check
code_et "copie du sanctum seule : ne compte pas" 1 "copie hors du Mac du jour ni prouvée ni reportée"
cas 09:00; rm -f "$JOURNAL"; printf 'serie-db derniere_copie=db-%s\nserie-sanctum derniere_copie=bmad-memory-%s\n' "$JOUR" "$JOUR" > "$OFF/offsite/statut"; check
code_et "fichier d'état : dernière copie de la base du jour, journal sans ligne : prouvée" 0 "copie hors du Mac prouvée"
cas 09:00; rm -f "$JOURNAL"; printf 'serie-db derniere_copie=db-%s\n' "$HIER" > "$OFF/offsite/statut"; check
code_et "fichier d'état : dernière copie d'hier : refusé" 1 "copie hors du Mac du jour ni prouvée ni reportée"
cas 09:00; rm -f "$JOURNAL"; printf 'serie-sanctum derniere_copie=db-%s\n' "$JOUR" > "$OFF/offsite/statut"; check
code_et "fichier d'état : une autre série que la base ne prouve rien" 1 "copie hors du Mac du jour ni prouvée ni reportée"

# --- le report ne couvre ni la veille ni la sauvegarde
cas 09:00; rm -f "$JOURNAL"; ligne "08:15:30" "copie reportée déclarée : db-$JOUR : disque chez un tiers"; repere reporte; check
code_et "report déclaré mais veille reportée : refusé" 1 "veille du jour pas terminée sans erreur (état : reporte)"
ne_contient_pas "le refus ne nomme que la veille (pas la sauvegarde)" "sauvegarde"
ne_contient_pas "le refus ne nomme que la veille (pas la copie)" "copie"
cas 09:00; rm -f "$JOURNAL"; ligne "08:15:30" "copie reportée déclarée : db-$JOUR : disque chez un tiers"; sauvegarde 2; check
code_et "report déclaré mais sauvegarde incomplète : refusé" 1 "sauvegarde du jour incomplète (2 dump(s) sur 4)"
ne_contient_pas "le refus ne nomme que la sauvegarde" "veille"

# --- plusieurs raisons, dans l'ordre veille, sauvegarde, copie
cas 09:00; rm -f "$JOURNAL" "$DONNEES/veille-du-jour.json"; repere termine "$HIER"; sauvegarde 1; check --language en
code_et "plusieurs raisons, en anglais" 1 "morning_state: refused, morning window since 06:45: no watch run today ; today's backup incomplete (1 of 4 dumps) ; today's off-site copy neither proven nor postponed"
cas 09:00; rm -f "$JOURNAL"; repere echoue; rm -rf "$SAUV/db-$JOUR"; check
code_et "plusieurs raisons, en français" 1 "morning_state : refusé, fenêtre du matin depuis 06:45 : veille du jour pas terminée sans erreur (état : echoue) ; sauvegarde du jour absente ; copie hors du Mac du jour ni prouvée ni reportée"

# --- le début du matin
cas 07:59; rm -f "$JOURNAL" "$DONNEES/veille-du-jour.json"
SORTIE=$(PMZILLA_RUN_MORNING_START=08:00 PMZILLA_LAB_WORKSPACE="$ESPACE" PMZILLA_LAB_DATA="$DONNEES" DB_BACKUP_SAUVEGARDES="$SAUV" OFFSITE_COPY_LOG="$JOURNAL" \
  OFFSITE_DONNEES="$OFF" PMZILLA_RUN_NOW="$(instant 07:59)" HOME="$tmp/maison" bash "$script" check 2>&1); CODE=$?
code_et "début du matin réglé à 08:00 : permis à 07:59" 0 "(début 08:00)"
SORTIE=$(PMZILLA_RUN_MORNING_START=pas-une-heure PMZILLA_LAB_WORKSPACE="$ESPACE" PMZILLA_LAB_DATA="$DONNEES" DB_BACKUP_SAUVEGARDES="$SAUV" OFFSITE_COPY_LOG="$JOURNAL" \
  OFFSITE_DONNEES="$OFF" PMZILLA_RUN_NOW="$(instant 06:50)" HOME="$tmp/maison" bash "$script" check 2>&1); CODE=$?
code_et "début du matin invalide : retour au défaut 06:45" 1 "fenêtre du matin depuis 06:45"

# --- usage
cas 09:00
lance; code_et "sans sous-commande : usage" 2 ""
[ -z "$SORTIE" ] && contains_err=0 || contains_err=1; verifie "l'usage ne s'écrit pas sur la sortie standard" "$contains_err"
printf '%s' "$ERR" | grep -qF "morning_state : usage : check [--language fr|en]"; verifie "l'usage est dit en français" $?
lance --help; code_et "option inconnue : usage" 2 ""
lance check --nimporte; code_et "option inconnue après check : usage" 2 ""
lance check --language de; code_et "langue inconnue : usage" 2 ""
lance check --language; code_et "option de langue sans valeur : usage" 2 ""
lance check check; code_et "deux fois la sous-commande : usage" 2 ""
lance --language en; code_et "langue sans sous-commande : usage" 2 ""
printf '%s' "$ERR" | grep -qF "morning_state: usage: check [--language fr|en]"; verifie "l'usage est dit en anglais avec --language en" $?
SORTIE=$(PMZILLA_LAB_WORKSPACE="$tmp/absent" bash "$script" 2>/dev/null); CODE=$?
code_et "usage avant toute lecture : le module des dossiers n'est pas appelé" 2 ""

# --- échec de la résolution des dossiers
SORTIE=$(PMZILLA_LAB_WORKSPACE="$tmp/absent" PMZILLA_RUN_NOW="$(instant 09:00)" bash "$script" check 2>"$tmp/err"); CODE=$?; ERR=$(cat "$tmp/err")
code_et "dossier de contenu absent : code 78 du module partagé" 78 ""
printf '%s' "$ERR" | grep -qF "chemins du lab"; verifie "le message du module partagé est conservé" $?

# --- rien n'est écrit, aucun chemin n'est affiché
cas 09:00; rm -f "$JOURNAL"; ligne "08:15:30" "copie reportée déclarée : db-$JOUR : cause"; : > "$OFF/offsite/statut"
instantane() { ( cd "$tmp" && find donnees sauvegardes copie.log off espace tmpdir maison -print 2>/dev/null | LC_ALL=C sort | while IFS= read -r f; do
    printf '%s %s %s\n' "$f" "$(stat -f '%m %z' "$f" 2>/dev/null || stat -c '%Y %s' "$f")" "$(cksum < "$f" 2>/dev/null)"; done ) ; }
avant=$(instantane)
check; sortie1="$SORTIE $ERR"; check --language en; sortie2="$SORTIE $ERR"
lance check; sortie3="$SORTIE $ERR"
apres=$(instantane)
[ "$avant" = "$apres" ]; verifie "les dossiers de données, des sauvegardes, le journal, l'état et le dossier temporaire sont inchangés" $?
[ -z "$(ls -A "$TMPDIR_TEST")" ]; verifie "le dossier temporaire reste vide" $?
SORTIE="$sortie1 $sortie2 $sortie3"
{ ! contient "$tmp" && ! contient "/Users" && ! contient "$HOME"; }; verifie "aucune sortie ne contient de chemin" $?
cas 09:00; rm -f "$JOURNAL"; check
SORTIE="$SORTIE $ERR"
{ ! contient "$tmp" && ! contient "/Users" && ! contient "sauvegardes" && ! contient ".dump"; }; verifie "un refus ne contient ni chemin ni nom de fichier" $?

# --- la bibliothèque sourcée
cas 09:00
SORTIE=$( set -u; . "$script"
  export PMZILLA_RUN_NOW="$(instant 09:00)" OFFSITE_COPY_LOG="$JOURNAL" OFFSITE_DONNEES="$OFF"
  MORNING_DATA="$DONNEES"; MORNING_BACKUPS="$SAUV"
  echo "veille=$(morning_watch_state) sauvegarde=$(morning_backup_state) dumps=$(morning_backup_dumps) copie=$(morning_copy_state) decision=$(morning_decision)"
  echo "encore là" ); CODE=$?
code_et "sourcé : cinq fonctions, une valeur chacune, l'appelant n'est pas quitté" 0 "veille=fini sauvegarde=fini dumps=4 copie=prouvee decision=verifie"
contient "encore là"; verifie "sourcer le module ne sort pas du shell de l'appelant" $?
SORTIE=$( . "$script"; echo "$-"; pwd ); options_apres=$SORTIE
SORTIE=$( echo "$-"; pwd ); options_avant=$SORTIE
[ "$options_apres" = "$options_avant" ]; verifie "sourcer le module ne change ni les options du shell ni le dossier courant" $?
SORTIE=$( . "$script"; export PMZILLA_RUN_NOW="$(instant 05:00)"; MORNING_DATA=""; MORNING_BACKUPS=""
  echo "veille=$(morning_watch_state) sauvegarde=$(morning_backup_state) decision=$(morning_decision)" ); CODE=$?
code_et "sourcé, dossiers non posés : illisible, et avant la fenêtre la décision est « avant »" 0 "veille=illisible sauvegarde=illisible decision=avant"
SORTIE=$( . "$script"; export PMZILLA_RUN_NOW="$(instant 09:00)"; MORNING_DATA="$DONNEES"; MORNING_BACKUPS="$tmp/absent"
  echo "sauvegarde=$(morning_backup_state) dumps=$(morning_backup_dumps)" ); CODE=$?
code_et "sourcé, dossier des sauvegardes absent : « ignore » et 0 dump" 0 "sauvegarde=ignore dumps=0"
cas 09:00; repere echoue
SORTIE=$( . "$script"; export PMZILLA_RUN_NOW="$(instant 09:00)"; MORNING_DATA="$DONNEES"; echo "veille=$(morning_watch_state)" ); CODE=$?
code_et "sourcé, veille en erreur : l'état est rendu tel quel (« echoue »)" 0 "veille=echoue"
repere reporte
SORTIE=$( . "$script"; export PMZILLA_RUN_NOW="$(instant 09:00)"; MORNING_DATA="$DONNEES"; echo "veille=$(morning_watch_state)" ); CODE=$?
code_et "sourcé, veille reportée" 0 "veille=reporte"
repere commence "$HIER"
SORTIE=$( . "$script"; export PMZILLA_RUN_NOW="$(instant 09:00)"; MORNING_DATA="$DONNEES"; echo "veille=$(morning_watch_state)" ); CODE=$?
code_et "sourcé, repère d'un autre jour" 0 "veille=autrejour"

# --- tests statiques : les constantes du module et leurs sources
valeur() { sed -n "s/^$1=\"\{0,1\}\([^\"]*\)\"\{0,1\}\$/\1/p" "$script" | head -1; }
attendu_dumps=$(valeur MORNING_EXPECTED_DUMPS)
# ce que db_backup.sh écrit réellement : un dump par schéma de SCHEMAS (fichier="$CIBLE/$schema.dump" dans la boucle), plus chaque dump
# écrit sous un nom fixe (fichier="$CIBLE/<nom>.dump", aujourd'hui le dump partiel de quality)
schemas=$(sed -n 's/^SCHEMAS="\${DB_BACKUP_SCHEMAS:-\(.*\)}"$/\1/p' "$racine/tools/db_backup.sh" | head -1)
n_schemas=$(printf '%s\n' $schemas | grep -c .)
boucle=$(grep -c -F 'fichier="$CIBLE/$schema.dump"' "$racine/tools/db_backup.sh")
fixes=$(grep -E '^[[:space:]]*fichier="\$CIBLE/[A-Za-z0-9_-]+\.dump"' "$racine/tools/db_backup.sh" | sort -u | grep -c .)
n_ecrits=$((n_schemas + fixes))
SORTIE="attendu=$attendu_dumps, écrits par db_backup.sh=$n_ecrits ($n_schemas schémas : $schemas ; $fixes dump(s) à nom fixe)"
[ -n "$schemas" ] && [ "$boucle" -eq 1 ] && [ "$fixes" -ge 1 ] && [ "$attendu_dumps" = "$n_ecrits" ]
verifie "statique : MORNING_EXPECTED_DUMPS égale le nombre de dumps qu'écrit tools/db_backup.sh, dump partiel de quality compris" $?
plist="$racine/tools/com.pmzilla.watch.plist"
heure_plist=$(sed -n '/<key>Hour<\/key>/{n;s/.*<integer>\([0-9]*\)<\/integer>.*/\1/p;}' "$plist" | head -1)
minute_plist=$(sed -n '/<key>Minute<\/key>/{n;s/.*<integer>\([0-9]*\)<\/integer>.*/\1/p;}' "$plist" | head -1)
avance=$(valeur MORNING_LEAD_MINUTES); debut_defaut=$(valeur MORNING_DEFAULT_START)
total=$(( 10#$heure_plist * 60 + 10#$minute_plist - avance ))
calcule=$(printf '%02d:%02d' $((total / 60)) $((total % 60)))
SORTIE="début par défaut=$debut_defaut, modèle de la veille $heure_plist:$minute_plist moins $avance min = $calcule"
[ -n "$heure_plist" ] && [ -n "$minute_plist" ] && [ "$debut_defaut" = "$calcule" ]; verifie "statique : le début du matin par défaut égale l'heure du modèle de la veille moins l'avance" $?
defaut_run=$(sed -n 's/.*PMZILLA_RUN_MORNING_START:-}" "\([0-9:]*\)".*/\1/p' "$racine/tools/run_worktree.sh" | head -1)
SORTIE="run_worktree.sh=$defaut_run, module=$debut_defaut"
[ "$defaut_run" = "$debut_defaut" ]; verifie "statique : le début du matin par défaut égale celui de tools/run_worktree.sh" $?
# aucune lecture de l'ancien journal de la veille, aucun fichier du modèle installé
SORTIE="pmzilla-watch.log ou LaunchAgents dans le module"
! grep -q -E "pmzilla-watch\.log|LaunchAgents|plutil" "$script"; verifie "statique : le module ne lit ni le journal de la veille ni le fichier installé du planificateur" $?
! grep -n -E '(^|[^[:alnum:]_])(rm|mkdir|touch|mv|cp|tee|mktemp|ln|chmod)[[:space:]]|>>|[^2&0-9 ]>[^&]' "$script" | grep -v '^[0-9]*:[[:space:]]*#' | grep -v '2>' | grep -v '>&2' | grep -q .; verifie "statique : le module ne contient aucune commande d'écriture" $?

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
