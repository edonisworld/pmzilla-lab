#!/bin/bash
# Test du module de la garde du matin légère (tools/morning_state.sh, change tooling-morning-guard-light, R-20261102-3 et R-20261102-5,
# design D1 à D5 ; remplace le test de la fenêtre du matin du change morning-guard) : dossier de données, dossier des sauvegardes, journal
# de la copie, fichier d'état de la copie et horloge remplacés par des variables, tous dans un dossier temporaire. Un seul refus : la veille
# (repère « commence » ET verrou tenu par un processus vivant) ou la sauvegarde (repère tenu) tournent ; toute autre défaillance est un
# avertissement avec le code 0, à toute heure. Un cas par raison d'avertissement, par ligne permise, la déclaration de report valable le jour
# même seulement, la preuve par le fichier d'état, l'ordre des avertissements, la lecture du runner (même règle, sans avertissement, sans
# marge), aucune écriture, aucun chemin affiché, les tests statiques (nombre de dumps, verrou et âge de la veille, âge du repère de la
# sauvegarde) et la bibliothèque sourcée.
# Aucun réseau, ni le vrai dossier du labo, ni le vrai dossier de données, ni les vraies sauvegardes.
# Lancement à la main : bash tests/morning_state/test_morning_state.sh
#
# Variables lues par le module (noms fixés par cette suite) : PMZILLA_LAB_WORKSPACE, PMZILLA_LAB_DATA, DB_BACKUP_SAUVEGARDES,
# OFFSITE_COPY_LOG, OFFSITE_DONNEES, PMZILLA_RUN_NOW.
set -u
unset PMZILLA_SKIP_GREEN_CHECK PMZILLA_NO_EVALS PMZILLA_RUN_MORNING_START PMZILLA_WATCH_LOCK_MAX_AGE PMZILLA_RUN_MARKER_MAX_AGE
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
AUTORISE="morning_state : autorisé, ni veille ni sauvegarde en cours"
AUTORISE_EN="morning_state: allowed, neither watch nor backup running"
RUNNER_OK="morning_state : runner complet de session permis, ni veille ni sauvegarde en cours"
RUNNER_OK_EN="morning_state: session full runner allowed, neither watch nor backup running"
AVERT="morning_state : avertissement : "
AVERT_EN="morning_state: warning: "

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
egal() { # description sortie-exacte-attendue (la sortie standard entière)
  if [ "$SORTIE" = "$2" ]; then echo "ok : $1"; ok=$((ok+1)); else echo "ECHEC : $1 :: attendu « $2 » :: obtenu « $SORTIE »"; ko=$((ko+1)); fi
}
seulement_avertissements() { SORTIE=$(printf '%s\n' "$SORTIE" | grep -F "avertissement" ); }   # garde les seules lignes d'avertissement (français)

# instant local de 2026-10-14 « HH:MM » en secondes
instant() { date -j -f "%Y-%m-%d %H:%M" "$JOUR $1" +%s 2>/dev/null || date -d "$JOUR $1" +%s; }

# Remise à zéro d'un cas : tout fait (veille terminée, 4 dumps, copie prouvée), rien ne tourne, horloge à l'heure donnée
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
verrou_veille() { # pid [début en secondes] : le verrou de la veille (dossier veille.verrou du dossier de données)
  mkdir -p "$DONNEES/veille.verrou"; printf '%s' "$1" > "$DONNEES/veille.verrou/pid"
  [ -z "${2:-}" ] || printf '%s' "$2" > "$DONNEES/veille.verrou/debut"
}
repere_sauvegarde() { # pid [début en secondes] : le repère de la sauvegarde (dossier sauvegarde.encours du dossier de données)
  mkdir -p "$DONNEES/sauvegarde.encours"; printf '%s' "$1" > "$DONNEES/sauvegarde.encours/pid"
  [ -z "${2:-}" ] || printf '%s' "$2" > "$DONNEES/sauvegarde.encours/debut"
}
lance() { # arguments de la commande ; sortie dans SORTIE, ERR et CODE
  SORTIE=$(PMZILLA_LAB_WORKSPACE="$ESPACE" PMZILLA_LAB_DATA="$DONNEES" DB_BACKUP_SAUVEGARDES="$SAUV" OFFSITE_COPY_LOG="$JOURNAL" \
    OFFSITE_DONNEES="$OFF" PMZILLA_RUN_NOW="$(instant "$heure")" HOME="$tmp/maison" TMPDIR="$TMPDIR_TEST" bash "$script" "$@" 2>"$tmp/err"); CODE=$?
  ERR=$(cat "$tmp/err")
}
check() { lance check "$@"; }
sh -c 'exit 0' & mort=$!; wait "$mort"   # le pid d'un processus mort

# --- aucune fenêtre du matin : à toute heure, sans repère du jour, rien ne tourne : permis avec un avertissement
# (réécrit sous R-20261102-3 et R-20261102-5 : l'ancienne borne 06:45 n'existe plus)
cas 06:44; rm -f "$DONNEES/veille-du-jour.json"; rm -rf "$SAUV/db-$JOUR" "$JOURNAL"; check
code_et "à 06:44, sans repère du jour ni sauvegarde ni copie : permis" 0 "$AUTORISE"
contient "${AVERT}état de la veille illisible"; verifie "à 06:44 : avertissement sur la veille" $?
cas 06:44; check --language en
code_et "à 06:44, tout vérifié, en anglais" 0 "$AUTORISE_EN"
cas 06:45; rm -f "$DONNEES/veille-du-jour.json"; check
code_et "à 06:45 (ancienne borne), sans repère : permis, avertissement" 0 "$AUTORISE"
ne_contient_pas "à 06:45 : aucune phrase de l'ancienne fenêtre" "fenêtre du matin"
cas 04:00; rm -f "$DONNEES/veille-du-jour.json"; check
code_et "à 04:00, sans repère : permis" 0 "$AUTORISE"
ne_contient_pas "à 04:00 : aucune phrase de l'ancienne fenêtre" "fenêtre du matin"
contient "état de la veille illisible"; verifie "à 04:00 : avertissement sur la veille (la veille n'est pas lue qu'après une heure)" $?

# --- tout est vérifié : permis, aucun avertissement
cas 09:00; check
code_et "veille terminée, 4 dumps, copie créée au journal : permis" 0 "$AUTORISE"
ne_contient_pas "tout vérifié : aucun avertissement" "avertissement"
cas 09:00; check --language en
code_et "tout vérifié, en anglais" 0 "$AUTORISE_EN"
ne_contient_pas "tout vérifié, en anglais : aucun avertissement" "warning"
cas 23:59; check
code_et "tard le soir, tout vérifié : permis" 0 "$AUTORISE"
cas 09:00; rm -f "$JOURNAL"; ligne "08:15:02" "déjà présente : db-$JOUR"; check
code_et "ligne « déjà présente » datée du jour : permis, copie prouvée (aucun avertissement)" 0 "$AUTORISE"
ne_contient_pas "ligne « déjà présente » : pas d'avertissement sur la copie" "copie hors du Mac"
cas 09:00; rm -f "$JOURNAL"; ligne "08:15:02" "copie créée : db-$JOUR"; check
code_et "ligne « copie créée » sans détail, fin de ligne : permis, copie prouvée" 0 "$AUTORISE"
ne_contient_pas "ligne « copie créée » sans détail : pas d'avertissement sur la copie" "copie hors du Mac"
cas 09:00; lance --language en check
code_et "l'option de langue est acceptée avant la sous-commande" 0 "$AUTORISE_EN"

# --- la veille : un échec est un avertissement ; seule la veille qui tourne (repère « commence » ET verrou tenu) refuse
for etat in echoue interrompu reporte commence; do
  cas 09:00; repere "$etat"; check
  code_et "veille du jour en état $etat, aucun verrou tenu : permis avec l'avertissement et l'état" 0 "${AVERT}veille du jour pas terminée sans erreur (état : $etat)"
done
cas 09:00; repere echoue; check --language en
code_et "veille en erreur, en anglais : permis avec l'avertissement" 0 "${AVERT_EN}today's watch run not ended without error (state: echoue)"
cas 09:00; repere termine "$HIER"; check
code_et "repère d'hier : permis, avertissement : aucune veille du jour" 0 "${AVERT}veille du jour absente"
cas 09:00; rm -f "$DONNEES/veille-du-jour.json"; check
code_et "aucun fichier de repère : permis, avertissement illisible" 0 "${AVERT}état de la veille illisible"
for heure_illisible in 06:45 09:29 09:31 15:00 22:30 23:50; do
  cas "$heure_illisible"; printf 'pas du json' > "$DONNEES/veille-du-jour.json"; check
  code_et "repère illisible à $heure_illisible : permis, avertissement (plus de refus, plus d'heure de repli)" 0 "${AVERT}état de la veille illisible"
done
cas 09:00; repere echoue "$HIER"; check --language en
code_et "aucune veille du jour, en anglais : permis avec l'avertissement" 0 "${AVERT_EN}no watch run today"
cas 09:00; rm -f "$DONNEES/veille-du-jour.json"; check --language en
code_et "repère absent, en anglais : permis avec l'avertissement" 0 "${AVERT_EN}watch state unreadable"
cas 09:00; repere termine; sed 's/termine/termine /' "$DONNEES/veille-du-jour.json" > "$tmp/x" && mv "$tmp/x" "$DONNEES/veille-du-jour.json"; check
code_et "état mal formé : permis, avertissement illisible" 0 "${AVERT}état de la veille illisible"

# --- la veille qui tourne : « commence » ET un verrou tenu par un processus vivant (Q276)
cas 09:00; repere commence; verrou_veille "$$" "$(instant 09:00)"; check
code_et "« commence » et verrou de la veille tenu par un processus vivant : refusé" 1 "morning_state : refusé, en cours : veille du jour en cours"
cas 09:00; repere commence; verrou_veille "$$" "$(instant 09:00)"; check --language en
code_et "veille qui tourne, en anglais" 1 "morning_state: refused, running: today's watch run in progress"
ne_contient_pas "refus : aucune phrase de l'ancienne fenêtre" "fenêtre du matin"
cas 09:00; repere commence; verrou_veille "$$"; check
code_et "verrou de la veille sans début lisible (date de modification récente) : tenu, refusé" 1 "en cours : veille du jour en cours"
cas 03:00; repere commence; verrou_veille "$$" "$(instant 03:00)"; check
code_et "veille qui tourne à 03:00 : refusé, à toute heure" 1 "en cours : veille du jour en cours"
cas 09:00; repere commence; verrou_veille "$mort" "$(instant 09:00)"; check
code_et "« commence » et verrou d'un processus mort : permis, avertissement avec l'état" 0 "${AVERT}veille du jour pas terminée sans erreur (état : commence)"
cas 09:00; repere commence; verrou_veille "$$" "$(( $(instant 09:00) - 30000 ))"; check
code_et "« commence » et verrou plus vieux que l'âge maximal (21600 s) : permis, avertissement" 0 "${AVERT}veille du jour pas terminée sans erreur (état : commence)"
cas 09:00; repere commence; mkdir -p "$DONNEES/veille.verrou"; check
code_et "« commence » et verrou sans pid : pas tenu, permis" 0 "${AVERT}veille du jour pas terminée sans erreur (état : commence)"
cas 09:00; repere termine; verrou_veille "$$" "$(instant 09:00)"; check
code_et "verrou tenu mais repère « termine » : la veille ne tourne pas, permis" 0 "$AUTORISE"
cas 09:00; repere termine "$HIER"; verrou_veille "$$" "$(instant 09:00)"; check
code_et "verrou tenu mais repère d'hier : le repère seul ne dit pas « commence », permis" 0 "$AUTORISE"

# --- la sauvegarde : un défaut est un avertissement ; seul le repère tenu refuse
cas 09:00; sauvegarde 2; check
code_et "2 dumps sur 4 : permis, avertissement sauvegarde incomplète" 0 "${AVERT}sauvegarde du jour incomplète (2 dump(s) sur 4)"
cas 09:00; sauvegarde 2; check --language en
code_et "2 dumps sur 4, en anglais" 0 "${AVERT_EN}today's backup incomplete (2 of 4 dumps)"
# décision de l'auteur du 2026-10-21 : les trois schémas et le dump partiel de quality (obligatoire depuis le bloc F de R-94)
cas 09:00; rm -rf "$SAUV/db-$JOUR"; mkdir -p "$SAUV/db-$JOUR"
for s in knowledge cases flow quality-sans-texte; do : > "$SAUV/db-$JOUR/$s.dump"; done; check
code_et "4 dumps (trois schémas et le dump partiel de quality) : permis" 0 "$AUTORISE"
ne_contient_pas "4 dumps : aucun avertissement" "avertissement"
cas 09:00; rm -rf "$SAUV/db-$JOUR"; mkdir -p "$SAUV/db-$JOUR"
for s in knowledge cases flow; do : > "$SAUV/db-$JOUR/$s.dump"; done; check
code_et "3 dumps (dump partiel de quality manquant) : permis, avertissement" 0 "${AVERT}sauvegarde du jour incomplète (3 dump(s) sur 4)"
cas 09:00; sauvegarde 5; check
code_et "5 dumps : permis, avertissement : pas le nombre attendu" 0 "${AVERT}sauvegarde du jour incomplète (5 dump(s) sur 4)"
cas 09:00; rm -rf "$SAUV/db-$JOUR"; check
code_et "aucun dossier du jour : permis, avertissement sauvegarde absente" 0 "${AVERT}sauvegarde du jour absente"
cas 09:00; sauvegarde 4 "$HIER"; rm -rf "$SAUV/db-$JOUR"; check
code_et "dossier d'hier seulement : permis, avertissement sauvegarde du jour absente" 0 "${AVERT}sauvegarde du jour absente"
cas 09:00; rm -rf "$SAUV"; check
code_et "dossier des sauvegardes absent : permis, avertissement dossier illisible" 0 "${AVERT}dossier des sauvegardes illisible"
cas 09:00; rm -rf "$SAUV/db-$JOUR"; check --language en
code_et "sauvegarde absente, en anglais" 0 "${AVERT_EN}today's backup missing"
cas 09:00; mkdir -p "$SAUV/db-$JOUR/sous.dump"; rm -f "$SAUV/db-$JOUR/schema4.dump"; check
code_et "un dossier nommé .dump n'est pas un dump (permis, avertissement)" 0 "${AVERT}sauvegarde du jour incomplète (3 dump(s) sur 4)"
cas 09:00; : > "$SAUV/db-$JOUR/notes.txt"; check
code_et "un fichier qui n'est pas un dump n'est pas compté" 0 "$AUTORISE"
ne_contient_pas "un fichier qui n'est pas un dump : aucun avertissement" "avertissement"
cas 09:00; chmod 000 "$SAUV"; check; chmod 755 "$SAUV"
code_et "dossier des sauvegardes inaccessible : permis, avertissement dossier illisible" 0 "${AVERT}dossier des sauvegardes illisible"
cas 09:00; repere_sauvegarde "$$" "$(instant 09:00)"; check
code_et "repère de la sauvegarde tenu par un processus vivant : refusé" 1 "morning_state : refusé, en cours : sauvegarde en cours"
cas 09:00; repere_sauvegarde "$$" "$(instant 09:00)"; check --language en
code_et "sauvegarde qui tourne, en anglais" 1 "morning_state: refused, running: backup in progress"
cas 09:00; repere_sauvegarde "$mort" "$(instant 09:00)"; check
code_et "repère de la sauvegarde d'un processus mort : permis" 0 "$AUTORISE"
cas 09:00; repere_sauvegarde "$$" "$(( $(instant 09:00) - 30000 ))"; check
code_et "repère de la sauvegarde plus vieux que l'âge maximal (21600 s) : permis" 0 "$AUTORISE"
cas 09:00; mkdir -p "$DONNEES/sauvegarde.encours"; check
code_et "repère de la sauvegarde sans pid : pas tenu, permis" 0 "$AUTORISE"

# --- la copie hors du Mac : ni prouvée ni reportée est un avertissement
cas 23:30; rm -f "$JOURNAL"; check
code_et "tard le soir, copie ni prouvée ni déclarée : permis, avertissement copie" 0 "${AVERT}copie hors du Mac du jour ni prouvée ni reportée"
cas 09:00; rm -f "$JOURNAL"; check --language en
code_et "copie absente, en anglais" 0 "${AVERT_EN}today's off-site copy neither proven nor postponed"
cas 09:00; rm -f "$JOURNAL"; ligne "08:15:30" "copie reportée déclarée : db-$JOUR : disque chez un tiers"; check
code_et "report déclaré aujourd'hui : permis" 0 "$AUTORISE"
ne_contient_pas "report déclaré : pas d'avertissement sur la copie" "copie hors du Mac"
cas 09:00; rm -f "$JOURNAL"; ligne "08:15:30" "copie reportée déclarée : db-$JOUR : disque chez un tiers"; check --language en
code_et "report déclaré, en anglais" 0 "$AUTORISE_EN"
ne_contient_pas "report déclaré, en anglais : pas d'avertissement sur la copie" "off-site copy"
cas 23:00; rm -f "$JOURNAL"; ligne "08:15:30" "copie reportée déclarée : db-$JOUR : disque chez un tiers"; check
code_et "report déclaré, tard le soir : toujours permis" 0 "$AUTORISE"
ne_contient_pas "report déclaré, tard le soir : pas d'avertissement sur la copie" "copie hors du Mac"
cas 09:00; rm -f "$JOURNAL"; ligne "08:15:30" "copie reportée déclarée : db-$HIER : disque chez un tiers" "$HIER"; check
code_et "déclaration d'hier : permis, avertissement copie" 0 "${AVERT}copie hors du Mac du jour ni prouvée ni reportée"
cas 09:00; rm -f "$JOURNAL"; ligne "08:15:30" "copie reportée déclarée : db-$HIER : disque chez un tiers"; check
code_et "ligne d'aujourd'hui qui déclare le report de la sauvegarde d'hier : permis, avertissement copie" 0 "${AVERT}copie hors du Mac du jour ni prouvée ni reportée"
cas 09:00; rm -f "$JOURNAL"; ligne "08:15:30" "disque absent ou verrouillé : copie reportée"; check
code_et "report d'un disque absent, daté du jour : ne compte pas (avertissement copie)" 0 "${AVERT}copie hors du Mac du jour ni prouvée ni reportée"
cas 09:00; rm -f "$JOURNAL"; printf 'copie créée : db-%s (3 fichiers, 12 Ko)\n' "$JOUR" > "$JOURNAL"; check
code_et "ligne sans date (écrite avant le change) : ne compte pas (avertissement copie)" 0 "${AVERT}copie hors du Mac du jour ni prouvée ni reportée"
cas 09:00; rm -f "$JOURNAL"; ligne "07:20:11" "copie créée : db-$HIER (3 fichiers, 12 Ko)"; check
code_et "copie de la sauvegarde d'hier, datée du jour : ne compte pas (avertissement copie)" 0 "${AVERT}copie hors du Mac du jour ni prouvée ni reportée"
cas 09:00; rm -f "$JOURNAL"; ligne "07:20:11" "copie créée : db-$JOUR (3 fichiers, 12 Ko)" "$HIER"; check
code_et "copie de la sauvegarde du jour, ligne datée d'hier : ne compte pas (avertissement copie)" 0 "${AVERT}copie hors du Mac du jour ni prouvée ni reportée"
cas 09:00; rm -f "$JOURNAL"; ligne "07:20:11" "copie créée : db-${JOUR}1 (3 fichiers, 12 Ko)"; check
code_et "un nom de copie qui prolonge la date : ne compte pas (avertissement copie)" 0 "${AVERT}copie hors du Mac du jour ni prouvée ni reportée"
cas 09:00; rm -f "$JOURNAL"; ligne "07:20:11" "copie créée : bmad-memory-$JOUR (3 fichiers, 12 Ko)"; check
code_et "copie du sanctum seule : ne compte pas (avertissement copie)" 0 "${AVERT}copie hors du Mac du jour ni prouvée ni reportée"
cas 09:00; rm -f "$JOURNAL"; printf 'serie-db derniere_copie=db-%s\nserie-sanctum derniere_copie=bmad-memory-%s\n' "$JOUR" "$JOUR" > "$OFF/offsite/statut"; check
code_et "fichier d'état : dernière copie de la base du jour, journal sans ligne : prouvée, permis" 0 "$AUTORISE"
ne_contient_pas "fichier d'état : copie prouvée, pas d'avertissement sur la copie" "copie hors du Mac"
cas 09:00; rm -f "$JOURNAL"; printf 'serie-db derniere_copie=db-%s\n' "$HIER" > "$OFF/offsite/statut"; check
code_et "fichier d'état : dernière copie d'hier : permis, avertissement copie" 0 "${AVERT}copie hors du Mac du jour ni prouvée ni reportée"
cas 09:00; rm -f "$JOURNAL"; printf 'serie-sanctum derniere_copie=db-%s\n' "$JOUR" > "$OFF/offsite/statut"; check
code_et "fichier d'état : une autre série que la base ne prouve rien (avertissement copie)" 0 "${AVERT}copie hors du Mac du jour ni prouvée ni reportée"

# --- le report ne couvre ni la veille ni la sauvegarde : seule la ligne de la partie en défaut apparaît (réécrit en lignes d'avertissement)
cas 09:00; rm -f "$JOURNAL"; ligne "08:15:30" "copie reportée déclarée : db-$JOUR : disque chez un tiers"; repere reporte; check
code_et "report déclaré mais veille reportée : permis, avertissement sur la veille" 0 "${AVERT}veille du jour pas terminée sans erreur (état : reporte)"
seulement_avertissements
ne_contient_pas "l'avertissement ne nomme que la veille (pas la sauvegarde)" "sauvegarde"
ne_contient_pas "l'avertissement ne nomme que la veille (pas la copie)" "copie"
cas 09:00; rm -f "$JOURNAL"; ligne "08:15:30" "copie reportée déclarée : db-$JOUR : disque chez un tiers"; sauvegarde 2; check
code_et "report déclaré mais sauvegarde incomplète : permis, avertissement sur la sauvegarde" 0 "${AVERT}sauvegarde du jour incomplète (2 dump(s) sur 4)"
seulement_avertissements
ne_contient_pas "l'avertissement ne nomme que la sauvegarde" "veille"

# --- plusieurs avertissements, dans l'ordre veille, sauvegarde, copie (réécrit : l'ancienne ligne de refus devient des lignes d'avertissement)
cas 09:00; rm -f "$JOURNAL" "$DONNEES/veille-du-jour.json"; repere termine "$HIER"; sauvegarde 1; check --language en
egal "trois avertissements, en anglais, dans l'ordre veille, sauvegarde, copie" "$AUTORISE_EN
${AVERT_EN}no watch run today
${AVERT_EN}today's backup incomplete (1 of 4 dumps)
${AVERT_EN}today's off-site copy neither proven nor postponed"
code_et "trois avertissements : le code reste 0" 0
cas 09:00; rm -f "$JOURNAL"; repere echoue; rm -rf "$SAUV/db-$JOUR"; check
egal "trois avertissements, en français, dans l'ordre veille, sauvegarde, copie" "$AUTORISE
${AVERT}veille du jour pas terminée sans erreur (état : echoue)
${AVERT}sauvegarde du jour absente
${AVERT}copie hors du Mac du jour ni prouvée ni reportée"
cas 09:00; rm -f "$JOURNAL"; repere_sauvegarde "$$" "$(instant 09:00)"; check
code_et "avertissement à côté d'un refus : la sauvegarde tourne, la copie manque" 1 "morning_state : refusé, en cours : sauvegarde en cours"
contient "${AVERT}copie hors du Mac du jour ni prouvée ni reportée"; verifie "le refus est suivi de l'avertissement sur la copie" $?
cas 09:00; repere commence; verrou_veille "$$" "$(instant 09:00)"; repere_sauvegarde "$$" "$(instant 09:00)"; check
egal "veille et sauvegarde en cours : les deux raisons, veille d'abord, puis l'avertissement du repère « commence »" "morning_state : refusé, en cours : veille du jour en cours ; sauvegarde en cours
${AVERT}veille du jour pas terminée sans erreur (état : commence)"
code_et "les deux en cours : le code est 1" 1

# --- la lecture du runner complet d'une session (sous-commande runner, session-runner) : même règle que check, sans avertissement,
# sans fenêtre ni marge (réécrit sous R-20261102-3 et R-20261102-5 ; les cas de fenêtre et de marge sont retirés)
runner() { lance runner "$@"; }
cas 09:00; repere termine "$HIER"; rm -rf "$SAUV/db-$JOUR"; runner
code_et "runner : veille et sauvegarde pas faites, rien ne tourne : permis" 0 "$RUNNER_OK"
cas 06:44; repere termine "$HIER"; runner
code_et "runner : à 06:44, plus de fenêtre : permis" 0 "$RUNNER_OK"
cas 09:00; runner
code_et "runner : tout fait : permis" 0 "$RUNNER_OK"
egal "runner : une seule ligne, aucun avertissement" "$RUNNER_OK"
cas 09:00; sauvegarde 2; runner
egal "runner : sauvegarde incomplète (cas en défaut) : une seule ligne, aucun avertissement" "$RUNNER_OK"
for etat in echoue interrompu reporte; do
  cas 09:00; repere "$etat"; runner
  code_et "runner : veille en état $etat (un échec) : permis" 0 "$RUNNER_OK"
done
cas 09:00; repere commence; runner
code_et "runner : repère « commence » sans verrou tenu : permis" 0 "$RUNNER_OK"
cas 09:00; repere commence; verrou_veille "$$" "$(instant 09:00)"; runner
code_et "runner : veille en cours (« commence » et verrou tenu) : refusé" 1 "morning_state : runner complet de session refusé, en cours : veille du jour en cours"
cas 09:00; rm -f "$DONNEES/veille-du-jour.json"; runner
code_et "runner : repère de la veille absent : permis" 0 "$RUNNER_OK"
cas 09:00; sauvegarde 2; runner
code_et "runner : 2 dumps sur 4 (un échec possible) : permis" 0 "$RUNNER_OK"
cas 09:00; rm -rf "$SAUV/db-$JOUR"; runner
code_et "runner : sauvegarde du jour absente : permis" 0 "$RUNNER_OK"
cas 09:00; rm -rf "$SAUV"; runner
code_et "runner : dossier des sauvegardes absent (machine sans base) : permis" 0 "$RUNNER_OK"
cas 09:00; chmod 000 "$SAUV"; runner; chmod 755 "$SAUV"
code_et "runner : dossier des sauvegardes inaccessible : permis (n'est plus un refus)" 0 "$RUNNER_OK"
cas 09:00; repere_sauvegarde "$$" "$(instant 09:00)"; runner
code_et "runner : repère de la sauvegarde tenu par un processus vivant : refusé" 1 "morning_state : runner complet de session refusé, en cours : sauvegarde en cours"
cas 09:00; repere_sauvegarde "$mort" "$(instant 09:00)"; runner
code_et "runner : repère de la sauvegarde d'un processus mort : permis" 0 "$RUNNER_OK"
cas 09:00; mkdir -p "$DONNEES/sauvegarde.encours"; runner
code_et "runner : repère de la sauvegarde sans pid : permis (la sauvegarde ne l'écrit qu'en le créant)" 0 "$RUNNER_OK"
cas 23:30; rm -f "$JOURNAL"; runner
code_et "runner : copie hors du Mac ni prouvée ni reportée : permis" 0 "$RUNNER_OK"
cas 09:00; repere commence; verrou_veille "$$" "$(instant 09:00)"; repere_sauvegarde "$$" "$(instant 09:00)"; runner --language en
code_et "runner : en anglais, deux raisons" 1 "morning_state: session full runner refused, running: today's watch run in progress ; backup in progress"
cas 09:00; lance --language en runner
code_et "runner : options avant la sous-commande" 0 "$RUNNER_OK_EN"
cas 09:00
lance runner --margin 540; code_et "runner : --margin 540 : usage, rien n'est lu" 2 ""
lance runner --margin 3600; code_et "runner : --margin 3600 : usage" 2 ""
lance runner --margin abc; code_et "runner : marge non numérique : usage" 2 ""
lance runner --margin; code_et "runner : marge sans valeur : usage" 2 ""
lance check --margin 540; code_et "check n'accepte pas de marge : usage" 2 ""
lance runner check; code_et "deux sous-commandes : usage" 2 ""
SORTIE=$( . "$script"; export PMZILLA_RUN_NOW="$(instant 09:00)"; MORNING_DATA="$DONNEES"; MORNING_BACKUPS="$SAUV"
  echo "encours=$(morning_backup_running) veille=$(morning_watch_running) occupe=[$(morning_busy)]" ); CODE=$?
code_et "sourcé : morning_backup_running, morning_watch_running et morning_busy" 0 "encours=non veille=non occupe=[]"
cas 09:00; repere commence; verrou_veille "$$" "$(instant 09:00)"; repere_sauvegarde "$$" "$(instant 09:00)"
SORTIE=$( . "$script"; export PMZILLA_RUN_NOW="$(instant 09:00)"; MORNING_DATA="$DONNEES"; MORNING_BACKUPS="$SAUV"
  echo "occupe=[$(morning_busy)]" ); CODE=$?
code_et "sourcé : morning_busy rend « veille sauvegarde » dans cet ordre" 0 "occupe=[veille sauvegarde]"
cas 09:00; repere_sauvegarde "$$" "$(instant 09:00)"
SORTIE=$( . "$script"; export PMZILLA_RUN_NOW="$(instant 09:00)"; MORNING_DATA="$DONNEES"; MORNING_BACKUPS="$SAUV"
  echo "occupe=[$(morning_busy)]" ); CODE=$?
code_et "sourcé : morning_busy rend « sauvegarde » seule" 0 "occupe=[sauvegarde]"
cas 09:00; repere commence; verrou_veille "$$" "$(instant 09:00)"
SORTIE=$( . "$script"; export PMZILLA_RUN_NOW="$(instant 09:00)"; MORNING_DATA="$DONNEES"; MORNING_BACKUPS="$SAUV"
  echo "occupe=[$(morning_busy)]" ); CODE=$?
code_et "sourcé : morning_busy rend « veille » seule" 0 "occupe=[veille]"

# --- usage
cas 09:00
lance; code_et "sans sous-commande : usage" 2 ""
[ -z "$SORTIE" ] && contains_err=0 || contains_err=1; verifie "l'usage ne s'écrit pas sur la sortie standard" "$contains_err"
printf '%s' "$ERR" | grep -qF "morning_state : usage : check [--language fr|en]"; verifie "l'usage est dit en français" $?
printf '%s' "$ERR" | grep -qF -- "--margin"; [ $? -ne 0 ]; verifie "l'usage ne cite plus l'option --margin" $?
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

# --- rien n'est écrit, aucun chemin n'est affiché (verrou et repère tenus compris : ils ne sont ni créés, ni retirés, ni renouvelés)
cas 09:00; rm -f "$JOURNAL"; ligne "08:15:30" "copie reportée déclarée : db-$JOUR : cause"; : > "$OFF/offsite/statut"
repere commence; verrou_veille "$$" "$(instant 09:00)"; repere_sauvegarde "$$" "$(instant 09:00)"
instantane() { ( cd "$tmp" && find donnees sauvegardes copie.log off espace tmpdir maison -print 2>/dev/null | LC_ALL=C sort | while IFS= read -r f; do
    printf '%s %s %s\n' "$f" "$(stat -f '%m %z' "$f" 2>/dev/null || stat -c '%Y %s' "$f")" "$(cksum < "$f" 2>/dev/null)"; done ) ; }
avant=$(instantane)
check; sortie1="$SORTIE $ERR"; check --language en; sortie2="$SORTIE $ERR"
lance check; sortie3="$SORTIE $ERR"; runner; sortie4="$SORTIE $ERR"
apres=$(instantane)
[ "$avant" = "$apres" ]; verifie "les dossiers de données (verrou et repère tenus compris), des sauvegardes, le journal, l'état et le dossier temporaire sont inchangés" $?
[ -z "$(ls -A "$TMPDIR_TEST")" ]; verifie "le dossier temporaire reste vide" $?
SORTIE="$sortie1 $sortie2 $sortie3 $sortie4"
{ ! contient "$tmp" && ! contient "/Users" && ! contient "$HOME"; }; verifie "aucune sortie ne contient de chemin" $?
cas 09:00; rm -f "$JOURNAL"; check
SORTIE="$SORTIE $ERR"
{ ! contient "$tmp" && ! contient "/Users" && ! contient "sauvegardes" && ! contient ".dump"; }; verifie "un avertissement ne contient ni chemin ni nom de fichier" $?
cas 09:00; repere_sauvegarde "$$" "$(instant 09:00)"; check
SORTIE="$SORTIE $ERR"
{ ! contient "$tmp" && ! contient "/Users" && ! contient "sauvegardes" && ! contient ".dump" && ! contient "veille.verrou" && ! contient "sauvegarde.encours"; }; verifie "un refus ne contient ni chemin ni nom de verrou, de repère ou de fichier" $?

# --- la bibliothèque sourcée
cas 09:00
SORTIE=$( set -u; . "$script"
  export PMZILLA_RUN_NOW="$(instant 09:00)" OFFSITE_COPY_LOG="$JOURNAL" OFFSITE_DONNEES="$OFF"
  MORNING_DATA="$DONNEES"; MORNING_BACKUPS="$SAUV"
  echo "veille=$(morning_watch_state) sauvegarde=$(morning_backup_state) dumps=$(morning_backup_dumps) copie=$(morning_copy_state) occupe=[$(morning_busy)] avertissements=[$(morning_warnings fr)]"
  echo "encore là" ); CODE=$?
code_et "sourcé : les fonctions, une valeur chacune, l'appelant n'est pas quitté (réécrit : plus de décision verifie, mais occupé vide et aucun avertissement)" 0 "veille=fini sauvegarde=fini dumps=4 copie=prouvee occupe=[] avertissements=[]"
contient "encore là"; verifie "sourcer le module ne sort pas du shell de l'appelant" $?
SORTIE=$( . "$script"; echo "$-"; pwd ); options_apres=$SORTIE
SORTIE=$( echo "$-"; pwd ); options_avant=$SORTIE
[ "$options_apres" = "$options_avant" ]; verifie "sourcer le module ne change ni les options du shell ni le dossier courant" $?
SORTIE=$( . "$script"; export PMZILLA_RUN_NOW="$(instant 05:00)"; MORNING_DATA=""; MORNING_BACKUPS=""
  echo "veille=$(morning_watch_state) sauvegarde=$(morning_backup_state) occupe=[$(morning_busy)]" ); CODE=$?
code_et "sourcé, dossiers non posés : illisible, et rien ne tourne (réécrit : plus de décision « avant »)" 0 "veille=illisible sauvegarde=illisible occupe=[]"
SORTIE=$( . "$script"; export PMZILLA_RUN_NOW="$(instant 09:00)"; MORNING_DATA="$DONNEES"; MORNING_BACKUPS="$tmp/absent"
  echo "sauvegarde=$(morning_backup_state) dumps=$(morning_backup_dumps)" ); CODE=$?
code_et "sourcé, dossier des sauvegardes absent : « ignore » et 0 dump" 0 "sauvegarde=ignore dumps=0"
SORTIE=$( . "$script"; export PMZILLA_RUN_NOW="$(instant 09:00)"; MORNING_DATA="$DONNEES"; MORNING_BACKUPS="$tmp/absent"; OFFSITE_COPY_LOG="$JOURNAL"; OFFSITE_DONNEES="$OFF"
  morning_warnings fr ); CODE=$?
egal "sourcé, dossier des sauvegardes absent : l'avertissement de la sauvegarde est « dossier des sauvegardes illisible »" "dossier des sauvegardes illisible"
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
SORTIE="repère de db_backup.sh : $(grep -c '^poser_repere sauvegarde\.encours$' "$racine/tools/db_backup.sh")"
[ "$(grep -c '^poser_repere sauvegarde\.encours$' "$racine/tools/db_backup.sh")" = "1" ] && grep -q 'MORNING_DATA/sauvegarde\.encours' "$script"
verifie "statique : le repère lu par la garde est celui que pose tools/db_backup.sh (sauvegarde.encours)" $?
# jumeau (design D2) : le nom du verrou de la veille et son âge maximal, source tools/watch.sh ; un écart fait échouer la suite et nomme la constante
nom_watch=$(sed -n 's/^VERROU="\$DATA\/\(.*\)"$/\1/p' "$racine/tools/watch.sh" | head -1)
nom_module=$(valeur MORNING_WATCH_LOCK)
SORTIE="MORNING_WATCH_LOCK=$nom_module, tools/watch.sh=$nom_watch"
[ -n "$nom_watch" ] && [ "$nom_module" = "$nom_watch" ]; verifie "statique : MORNING_WATCH_LOCK égale le nom du verrou de tools/watch.sh" $?
age_watch=$(sed -n 's/^AGE_MAX_VERROU="\${PMZILLA_WATCH_LOCK_MAX_AGE:-\([0-9]*\)}"$/\1/p' "$racine/tools/watch.sh" | head -1)
age_module=$(valeur MORNING_WATCH_LOCK_MAX_AGE)
SORTIE="MORNING_WATCH_LOCK_MAX_AGE=$age_module, tools/watch.sh=$age_watch"
[ -n "$age_watch" ] && [ "$age_module" = "$age_watch" ]; verifie "statique : MORNING_WATCH_LOCK_MAX_AGE égale l'âge maximal du verrou de tools/watch.sh" $?
age_repere=$(sed -n 's/^AGE_MAX_REPERE="\${PMZILLA_RUN_MARKER_MAX_AGE:-\([0-9]*\)}"$/\1/p' "$racine/tools/db_backup.sh" | head -1)
age_marqueur=$(valeur MORNING_MARKER_MAX_AGE)
SORTIE="MORNING_MARKER_MAX_AGE=$age_marqueur, tools/db_backup.sh=$age_repere"
[ -n "$age_repere" ] && [ "$age_marqueur" = "$age_repere" ]; verifie "statique : MORNING_MARKER_MAX_AGE égale l'âge maximal du repère de tools/db_backup.sh" $?
# plus de fenêtre : ni constante de début, ni option de marge, ni lecture de l'ancienne variable dans le module
SORTIE="MORNING_DEFAULT_START, MORNING_LEAD_MINUTES, PMZILLA_RUN_MORNING_START ou --margin dans le module"
! grep -v '^[[:space:]]*#' "$script" | grep -q -E 'MORNING_DEFAULT_START|MORNING_LEAD_MINUTES|PMZILLA_RUN_MORNING_START|--margin|MS_START|MS_WINDOW'; verifie "statique : le module ne contient plus ni fenêtre, ni marge, ni heure de début du matin (code, hors commentaires)" $?
# aucune lecture de l'ancien journal de la veille, aucun fichier du modèle installé
SORTIE="pmzilla-watch.log ou LaunchAgents dans le module"
! grep -q -E "pmzilla-watch\.log|LaunchAgents|plutil" "$script"; verifie "statique : le module ne lit ni le journal de la veille ni le fichier installé du planificateur" $?
! grep -n -E '(^|[^[:alnum:]_])(rm|mkdir|touch|mv|cp|tee|mktemp|ln|chmod)[[:space:]]|>>|[^2&0-9 ]>[^&]' "$script" | grep -v '^[0-9]*:[[:space:]]*#' | grep -v '2>' | grep -v '>&2' | grep -q .; verifie "statique : le module ne contient aucune commande d'écriture" $?

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
