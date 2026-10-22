#!/bin/zsh
# Veille quotidienne de PMZilla Lab (watch) : collecte, pré-tri, liste à lire, puis mise à jour de l'index.
# Lancé chaque matin par launchd (com.pmzilla.watch.plist). Journal : ~/Library/Logs/pmzilla-watch.log
# Code de sortie : 0 si toutes les étapes ont réussi, 1 si l'une a échoué (collecte, pré-tri, liste à lire,
# indexation). Le journal le dit en toute fin et une notification macOS nomme les étapes en échec.
# Le tableau de bord (jamais bloquant) et l'absence d'Ollama (pré-tri et indexation reportés au prochain passage)
# ne comptent pas comme des échecs. Mais si Ollama est absent et que la dernière indexation réussie date de plus de
# PMZILLA_INDEXATION_MAX_JOURS jours (3 par défaut ; à régler dans le .plist, clé EnvironmentVariables), une
# notification macOS le dit, sans changer le code de sortie. La date de la dernière indexation réussie est dans
# $PMZILLA_LAB_DATA/derniere-indexation (par défaut ~/.pmzilla-lab) ; c'est la seule source de cette date.
# L'état de la veille et du pré-tri vit dans la même base : après le contrôle du cache de uv et avant la collecte, l'étape
# « base de données » lance « watch_lab.py check-db --wait N » (N : PMZILLA_WATCH_DB_WAIT secondes, 120 par défaut ; une valeur qui
# n'est pas un entier vaut 120). Si la base ne répond pas (code 4) ou n'a pas les tables (code 5), le jour est sauté : ni collecte,
# ni pré-tri, ni listes à lire, ni indexation (rien n'est écrit ailleurs, aucun fichier de repli) ; le tableau de bord est quand
# même généré, une seule notification nomme l'étape « base de données » et le code de sortie est 1. La veille ne démarre jamais la base.
# L'indexation écrit directement dans la base PostgreSQL ; si la base ne répond pas, l'étape en échec est
# « indexation (base injoignable) ». Après une indexation réussie : sonde de l'index BM25 (jamais un échec).
# Aucun fichier SQLite n'est lu ni écrit.
# Veille des composants (R-41), juste avant le tableau de bord, quoi qu'il soit arrivé à la base et à Ollama :
# « composants.py check --if-due » (une vérification complète par semaine, le jour réglé ou au premier passage suivant). Code 1 :
# une notification (nouveautés à examiner) ; autre code que 0 et 1 : une ligne au journal et une notification. Jamais comptée parmi
# les étapes en échec, jamais de changement du code de sortie. La veille ne nettoie jamais le cache de uv et n'installe rien.
# Tests de mutation du masquage (masking-mutation-tests D7), après la veille des composants : « mutation_masking.py run --due »
# (une exécution par semaine, avec rattrapage). Jamais une étape en échec, jamais de notification, code de sortie inchangé ; un échec
# est nommé dans le journal.
#
# Rattrapage (R-44). Options : « --if-due » (lancement planifié du calendrier, déclencheur « calendrier »), « --catch-up » (lancement
# planifié horaire et au chargement, déclencheur « rattrapage »), aucune (lancement manuel, forcé, déclencheur « manuel »). Autre
# option : code 2, avant tout appel d'outil. Un lancement planifié ne passe qu'entre HEURE_DUE et HEURE_LIMITE (heures murales
# d'Europe/Paris, surcharges PMZILLA_WATCH_DUE_TIME et PMZILLA_WATCH_LATEST_TIME, HH:MM) et seulement si aucun passage du jour n'est
# terminé : sinon il sort avec le code 0 sans rien écrire. Le jour est celui d'Europe/Paris ; l'instant vient de PMZILLA_WATCH_NOW
# (secondes depuis l'époque, entier) quand elle est réglée, de l'horloge sinon. Le repère du jour (veille-du-jour.json dans le dossier
# de données, écriture atomique, droits 600) est la seule source de la décision : le journal n'est jamais lu. Verrou : le dossier
# veille.verrou (mkdir atomique, fichier pid), périmé si son processus est mort ou s'il a plus de PMZILLA_WATCH_LOCK_MAX_AGE secondes
# (21600 par défaut). Passage interrompu : repris une seule fois dans la journée. Jour reporté (base qui ne répond pas, code 4, ou, en
# planifié, réseau absent) : état « reporte », nouvel essai au passage planifié suivant, une seule notification par jour.
# Codes de sortie : 0, 1 (étape en échec, jour reporté compris), 2 (option inconnue), 3 (lancement manuel refusé : un passage est
# en cours), 4 (repère impossible à écrire : aucun passage).
# Résumé du matin (R-50) : en fin de passage planifié terminé ou en échec, après le tableau de bord et l'écriture finale du repère,
# « morning_summary.py --notify --failed-steps <étapes> » (variable PMZILLA_SUMMARY_NOTIFY=1), par le lien du dossier du labo. Il envoie
# l'unique notification du passage, celle d'un échec comprise. S'il rend autre chose que 0 ou ne peut pas être lancé, la notification
# d'échec part comme avant ; un passage réussi reste alors silencieux. Il ne change ni le code de sortie ni la ligne de fin.
#
# Dossiers de code et de contenu (run-worktree D2, D5). Dossier de code : où le lien de ce script se résout (liens suivis) ; les outils
# (dont composants.py et dashboard.py), watch_paths.py, la version de Python épinglée et le script de réveil du contrôle du cache de uv
# y sont lus. Dossier de contenu : PMZILLA_LAB_WORKSPACE (par défaut le dépôt de développement, par Git), exporté aux outils ; la collecte,
# l'indexation et le tableau de bord y travaillent. Un passage qui a lieu écrit les deux dossiers après l'en-tête (et après la ligne de
# rattrapage). Si le dossier de contenu est le dossier d'exécution (PMZILLA_LAB_RUN), le passage s'arrête juste après l'écriture du
# début dans le repère : phrase clé, une notification, repère « echoue » code 1, verrou libéré, sortie 1. Aucun repère propre à ce
# script : le verrou de R-44 est le seul marqueur.
#
# Exemple :
#     zsh tools/watch.sh
set -u
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
PLANIFIE=0
DECLENCHEUR="manuel"
case "${1:-}" in
  "") ;;
  --if-due) PLANIFIE=1; DECLENCHEUR="calendrier" ;;
  --catch-up) PLANIFIE=1; DECLENCHEUR="rattrapage" ;;
  *) echo "Option inconnue : $1 (options admises : --if-due, --catch-up, ou aucune)" >&2; exit 2 ;;
esac
(( $# <= 1 )) || { echo "Un seul argument admis (--if-due, --catch-up, ou aucun)" >&2; exit 2; }
# Dossier de code (run-worktree D2, D5) : là où le lien de ce script se résout (liens suivis), son dossier parent de tools/. Les outils,
# les réglages suivis, la version de Python épinglée et le script de réveil y sont lus.
SELF="${${(%):-%x}:A}"
RACINE_CODE="${SELF:h:h}"
# Dossiers du lab par le module partagé tools/lab_paths.sh (R-77) : dossier de contenu (PMZILLA_LAB_WORKSPACE, sinon dépôt Git du code ;
# Bibliotheque-Lab et Watch-Lab y vivent, contenu exclu de Git), dossier du lab (les liens des scripts planifiés, dont watch.sh),
# dossier d'exécution. Un échec s'arrête avant tout pas, code 78.
. "$RACINE_CODE/tools/lab_paths.sh"
lab_paths_init || exit $?
TOOLS="$LAB_FOLDER"
WORKSPACE="$LAB_CONTENT_ROOT"
export PMZILLA_LAB_WORKSPACE="$WORKSPACE"
# Dossier de la veille : Watch-Lab, par la même logique que les scripts Python (watch_paths.py) ; sans python3, Watch-Lab.
# Si seul l'ancien dossier (Veille-Lab) existe, watch_paths.py refuse (message sur stderr : nom actuel et
# tools/migrate_watch.py) et la veille s'arrête avec le code 1.
resoudre_watch_lab() {
  if command -v python3 >/dev/null 2>&1; then
    WATCH_LAB=$(python3 -B "$RACINE_CODE/tools/watch_paths.py" lab "$WORKSPACE") || { echo "=== Veille arrêtée : dossier de la veille à l'ancien nom ==="; exit 1; }
  fi
  [[ -n "${WATCH_LAB:-}" ]] || WATCH_LAB="$WORKSPACE/Watch-Lab"
}

HEURE_DUE="07:10"
HEURE_LIMITE="22:00"
DATA="${PMZILLA_LAB_DATA:-$HOME/.pmzilla-lab}"
STAMP="$DATA/derniere-indexation"
MAX_JOURS="${PMZILLA_INDEXATION_MAX_JOURS:-3}"
[[ "$MAX_JOURS" == <-> ]] || MAX_JOURS=3
ATTENTE_BASE="${PMZILLA_WATCH_DB_WAIT:-120}"
[[ "$ATTENTE_BASE" == <-> ]] || ATTENTE_BASE=120
ATTENTE_RESEAU="${PMZILLA_WATCH_NET_WAIT:-120}"
[[ "$ATTENTE_RESEAU" == <-> ]] || ATTENTE_RESEAU=120
AGE_MAX_VERROU="${PMZILLA_WATCH_LOCK_MAX_AGE:-21600}"
[[ "$AGE_MAX_VERROU" == <-> ]] || AGE_MAX_VERROU=21600
FAILED=()   # étapes en échec, dans l'ordre
ETAPES=""
NOTIF_ECHEC_DIFFEREE=0   # passage planifié en échec : la notification attend le résumé du matin
REPORTE=0

# Heures et jour d'Europe/Paris : le fuseau du système ne décide de rien (l'en-tête du journal garde l'horloge du système)
heure_valide() { [[ "$1" =~ '^([01][0-9]|2[0-3]):[0-5][0-9]$' ]]; }
DUE="$HEURE_DUE"
[[ -n "${PMZILLA_WATCH_DUE_TIME:-}" ]] && heure_valide "$PMZILLA_WATCH_DUE_TIME" && DUE="$PMZILLA_WATCH_DUE_TIME"
LIMITE="$HEURE_LIMITE"
[[ -n "${PMZILLA_WATCH_LATEST_TIME:-}" ]] && heure_valide "$PMZILLA_WATCH_LATEST_TIME" && LIMITE="$PMZILLA_WATCH_LATEST_TIME"
instant() { if [[ "${PMZILLA_WATCH_NOW:-}" == <-> ]]; then print -r -- "$PMZILLA_WATCH_NOW"; else date +%s; fi; }
paris() { TZ=Europe/Paris date -r "$1" "+$2"; }   # paris <instant> <format>
MAINTENANT=$(instant)
JOUR=$(paris "$MAINTENANT" %Y-%m-%d)
HEURE=$(paris "$MAINTENANT" %H:%M)

# Repère du passage du jour (design D2) : champs R_*, lu sans sortie, écrit atomiquement
REPERE="$DATA/veille-du-jour.json"
lire_repere() {
  R_VALIDE=0; R_ILLISIBLE=0
  R_DATE=""; R_DECL=""; R_DEBUT=""; R_FIN=""; R_ETAT=""; R_CODE="null"; R_NOTIFIE="false"; R_ESSAIS=0; R_REPRISES=0
  [[ -e "$REPERE" ]] || return 0
  local t re
  t=$(cat "$REPERE" 2>/dev/null) || { R_ILLISIBLE=1; return 0; }
  re='"date": *"([0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9])"'
  [[ "$t" =~ $re ]] && R_DATE="$match[1]"
  re='"etat": *"(commence|termine|echoue|reporte|interrompu)"'
  [[ "$t" =~ $re ]] && R_ETAT="$match[1]"
  if [[ -z "$R_DATE" || -z "$R_ETAT" ]]; then
    R_DATE=""; R_ETAT=""; R_ILLISIBLE=1; return 0
  fi
  R_VALIDE=1
  re='"declencheur": *"([a-z]*)"';  [[ "$t" =~ $re ]] && R_DECL="$match[1]"
  re='"debut": *"([0-9:]*)"';       [[ "$t" =~ $re ]] && R_DEBUT="$match[1]"
  re='"fin": *"([0-9:]*)"';         [[ "$t" =~ $re ]] && R_FIN="$match[1]"
  re='"code": *([0-9]+)';           [[ "$t" =~ $re ]] && R_CODE="$match[1]"
  re='"notifie": *(true|false)';    [[ "$t" =~ $re ]] && R_NOTIFIE="$match[1]"
  re='"essais": *([0-9]+)';         [[ "$t" =~ $re ]] && R_ESSAIS="$match[1]"
  re='"reprises": *([0-9]+)';       [[ "$t" =~ $re ]] && R_REPRISES="$match[1]"
  return 0
}
repere_du_jour() { (( R_VALIDE )) && [[ "$R_DATE" == "$JOUR" ]]; }
ecrire_repere() {   # fichier temporaire dans le même dossier, puis renommage ; droits 600
  local tmp="$DATA/.veille-du-jour.$$.tmp"
  {
    ( umask 077; print -r -- "{\"date\": \"$R_DATE\", \"declencheur\": \"$R_DECL\", \"debut\": \"$R_DEBUT\", \"fin\": \"$R_FIN\", \"etat\": \"$R_ETAT\", \"code\": $R_CODE, \"notifie\": $R_NOTIFIE, \"essais\": $R_ESSAIS, \"reprises\": $R_REPRISES}" > "$tmp" ) \
      && chmod 600 "$tmp" && mv -f "$tmp" "$REPERE"
  } 2>/dev/null || { rm -f "$tmp" 2>/dev/null; echo "Repère du passage du jour impossible à écrire (le passage continue)"; return 1; }
}
repere_inscriptible() {   # crée puis retire un fichier à côté du repère, comme l'écriture atomique
  mkdir -p "$DATA" 2>/dev/null
  local essai="$DATA/.veille-du-jour.$$.essai"
  { : > "$essai"; } 2>/dev/null || return 1
  rm -f "$essai" 2>/dev/null
  return 0
}
dire_erreur() {   # lancement manuel : sortie d'erreur, et sortie standard quand elle est redirigée (journal, tube)
  print -r -- "$1" >&2
  [[ -t 1 ]] || print -r -- "$1"
}
refuser_repere() {   # D8 : aucun passage, code 4 ; une alerte par jour au plus (marqueur hors du dossier de données)
  local cle="Repère du passage du jour impossible à écrire : veille non lancée"
  if (( ! PLANIFIE )); then
    dire_erreur "$cle"
    dire_erreur "Cause : le dossier de données ($DATA) n'est pas inscriptible."
    exit 4
  fi
  local marqueur="$HOME/Library/Logs/pmzilla-watch-alerte" vu=""
  [[ -f "$marqueur" ]] && vu=$(cat "$marqueur" 2>/dev/null)
  [[ "$vu" == "$JOUR" ]] && exit 4
  echo "=== $(date '+%Y-%m-%d %H:%M') ==="
  echo "$cle"
  notifier "$cle"
  { mkdir -p "$HOME/Library/Logs"; print -r -- "$JOUR" > "$marqueur"; } 2>/dev/null
  exit 4
}

# Verrou (D4) : dossier veille.verrou créé par mkdir, avec pid et debut (instant de création, en secondes)
VERROU="$DATA/veille.verrou"
PROPRIETAIRE=""
VERROU_REPRIS=0
verrou_perime() {   # 0 si le verrou existant est périmé (processus mort ou trop vieux, en secondes écoulées)
  local pid debut age mtime
  pid=$(cat "$VERROU/pid" 2>/dev/null)
  if [[ "$pid" != <-> ]]; then   # création en cours, ou dossier abandonné
    mtime=$(stat -f %m "$VERROU" 2>/dev/null)
    [[ "$mtime" == <-> ]] && (( $(date +%s) - mtime > 10 )) && return 0
    return 1
  fi
  kill -0 "$pid" 2>/dev/null || return 0
  debut=$(cat "$VERROU/debut" 2>/dev/null)
  if [[ "$debut" == <-> ]]; then
    age=$(( MAINTENANT - debut ))
  else
    mtime=$(stat -f %m "$VERROU" 2>/dev/null)
    [[ "$mtime" == <-> ]] || return 1
    age=$(( $(date +%s) - mtime ))
  fi
  (( age > AGE_MAX_VERROU )) && return 0
  return 1
}
prendre_verrou() {
  local essai
  for essai in 1 2; do
    if mkdir "$VERROU" 2>/dev/null; then
      print -r -- "$$" > "$VERROU/pid"
      print -r -- "$MAINTENANT" > "$VERROU/debut"
      PROPRIETAIRE=1
      return 0
    fi
    verrou_perime || return 1
    # renommage atomique : un seul processus reprend le verrou périmé
    mv "$VERROU" "$VERROU.perime.$$" 2>/dev/null && { rm -rf "$VERROU.perime.$$"; VERROU_REPRIS=1; }
  done
  return 1
}
liberer_verrou() {   # seulement le processus qui l'a créé
  [[ -n "$PROPRIETAIRE" && "$(cat "$VERROU/pid" 2>/dev/null)" == "$$" ]] && rm -rf "$VERROU"
  return 0
}
trap liberer_verrou EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP

notifier() {   # un échec de notification ne change jamais le code de sortie
  osascript -e "display notification \"$1\" with title \"PMZilla watch\"" || echo "Notification macOS impossible"
}

# Ollama absent : prévenir seulement si l'index n'est plus à jour depuis trop longtemps
verifier_fraicheur_index() {
  local derniere=""
  [[ -f "$STAMP" ]] && derniere=$(<"$STAMP")   # le repère seul : la date d'un fichier d'index n'est jamais lue
  if [[ "$derniere" != <-> ]]; then
    echo "Aucune indexation réussie connue : index peut-être obsolète"
    notifier "Ollama absent et aucune indexation réussie connue. Lancer Ollama pour mettre la bibliothèque à jour."
    return
  fi
  local age=$(( $(date +%s) - derniere ))
  if (( age > MAX_JOURS * 86400 )); then
    echo "Index obsolète : dernière indexation réussie il y a $(( age / 86400 )) jour(s) (seuil : $MAX_JOURS)"
    notifier "Ollama absent : la bibliothèque n'est plus indexée depuis $(( age / 86400 )) jours. Lancer Ollama."
  fi
}

# Sonde de l'index BM25 de la base, après une indexation réussie (« pmzilla_lab_library.py probe » ; code 3 : index
# illisible, « bitmap intersection stream … claimed twice »). Jamais bloquante ni réparatrice : un échec est journalisé
# et notifié, la veille continue, le code de sortie ne change pas. La reconstruction (REINDEX) se fait en
# superutilisateur, par l'utilisateur seul (installation.md).
sonder_index_bm25() {
  local code=0
  uv run "$RACINE_CODE/tools/pmzilla_lab_library.py" probe || code=$?
  (( code == 0 )) && return 0
  if (( code == 3 )); then
    echo "Index BM25 illisible : la recherche plein texte de la base peut échouer. Procédure : docs/pmzilla/installation.md, « Damaged BM25 index »"
    notifier "Index BM25 de la base illisible. Voir installation.md, « Damaged BM25 index »."
  else
    echo "Sonde de l'index BM25 en échec (code $code) : voir ci-dessus"
    notifier "Sonde de l'index BM25 en échec. Voir le journal de la veille."
  fi
  return 0
}

# Cache de uv (R-13) : une mise à jour de uv ou du Python qu'il choisit vide le cache des dépendances des scripts à
# en-tête (le test hors ligne du réveil des postures échoue alors). Chaque matin, on compare les deux versions à celles
# enregistrées dans $DATA (uv-version, uv-python-version) ; si l'une a changé (ou n'est pas enregistrée), on relance le
# script jetable (en-tête du script de réveil + import yaml) dans un dossier temporaire avec le réseau, puis hors ligne depuis un second dossier. Les
# versions ne sont enregistrées qu'après un succès (un échec se retente le lendemain). Notification en cas d'échec
# seulement. Jamais bloquant : un échec ne change ni les étapes ni le code de sortie de la veille.
verifier_cache_uv() {
  local uv_v py_v
  uv_v=$(uv --version 2>/dev/null) || uv_v=""
  py_v=$(cd "$RACINE_CODE" 2>/dev/null && uv python find --show-version 2>/dev/null) || py_v=""
  if [[ -z "$uv_v" || -z "$py_v" ]]; then
    echo "Contrôle du cache de uv impossible : version de uv ou de Python illisible"
    return 0
  fi
  local f_uv="$DATA/uv-version" f_py="$DATA/uv-python-version"
  if [[ -f "$f_uv" && -f "$f_py" && "$(<"$f_uv")" == "$uv_v" && "$(<"$f_py")" == "$py_v" ]]; then
    return 0
  fi
  echo "uv ou son Python a changé ($uv_v, Python $py_v) : contrôle du cache"
  # Script jetable : seulement l'en-tête « # /// script … # /// » du script de réveil (mêmes dépendances, donc même
  # environnement pour uv), puis « import yaml ». Aucun code de réveil n'est exécuté (il suppose la racine du dépôt) :
  # le code de sortie ne dit que si l'environnement se résout et s'importe. Hors du dépôt, pas de .python-version :
  # --python fixe le Python lu dans le dossier de code.
  local reveil="$RACINE_CODE/.claude/skills/pmzilla-discovery-bmad/scripts/wake.py" reseau verif entete ok=0
  reseau=$(mktemp -d) && verif=$(mktemp -d) || { echo "Contrôle du cache de uv impossible : dossier temporaire"; return 0; }
  entete=$(sed -n '/^# \/\/\/ script$/,/^# \/\/\/$/p' "$reveil" 2>/dev/null)
  if [[ -n "$entete" ]] \
      && print -r -- "$entete"$'\nimport yaml' > "$reseau/controle_cache.py" \
      && cp "$reseau/controle_cache.py" "$verif/" \
      && (cd "$reseau" && uv run --python "$py_v" controle_cache.py >/dev/null) \
      && (cd "$verif" && UV_OFFLINE=1 uv run --python "$py_v" controle_cache.py >/dev/null); then
    ok=1
  fi
  rm -rf "$reseau" "$verif"
  if (( ok )); then
    mkdir -p "$DATA" && print -r -- "$uv_v" > "$f_uv" && print -r -- "$py_v" > "$f_py"
    echo "Cache de uv rempli et vérifié hors ligne"
  else
    echo "Cache de uv : le script jetable échoue (réseau coupé ou cache incomplet) ; procédure manuelle : installation.md, « After an update of uv »"
    notifier "Cache de uv à refaire après la mise à jour de uv ou de Python (voir installation.md, After an update of uv)."
  fi
  return 0
}

# Les étapes du jour : collecte, pré-tri, listes à lire, indexation. Sautées en bloc quand la base ne répond pas.
etapes_du_jour() {
  if ! uv run "$RACINE_CODE/tools/watch_lab.py" collect; then
    echo "Collecte en erreur (voir $WATCH_LAB/_rapport_collecte.txt)"
    FAILED+=("collecte")
  fi

  # Adresse d'Ollama : PMZILLA_LAB_OLLAMA, même variable et même défaut que l'indexeur (tools/pmzilla_lab_library.py, OLLAMA_URL).
  local ollama="${PMZILLA_LAB_OLLAMA:-http://localhost:11434}"
  ollama="${ollama%/}"
  if curl -s --max-time 5 "$ollama/api/tags" >/dev/null; then
    # Pré-tri : notes, filtre (en mode « filtre » seulement), partages Bluesky, puis liste à lire classée.
    # En cas d'échec (pas encore de référence, modèle absent), liste simple.
    if uv run "$RACINE_CODE/tools/watch_triage.py" score && uv run "$RACINE_CODE/tools/watch_triage.py" apply \
        && uv run "$RACINE_CODE/tools/watch_triage.py" shares && uv run "$RACINE_CODE/tools/watch_triage.py" digest; then
      :
    else
      echo "Pré-tri en erreur : liste à lire non triée"
      FAILED+=("pré-tri")
      uv run "$RACINE_CODE/tools/watch_lab.py" digest || { echo "Liste à lire en erreur"; FAILED+=("liste à lire"); }
    fi
    # Toujours les deux dossiers : un fichier absent des deux est retiré de l'index
    # L'indexeur écrit directement dans la base PostgreSQL (code 2 : la base ne répond pas).
    # Notes de contexte (organisation-context, D6) : l'option --context quand le dossier de contexte (module partagé lab_paths.sh) a un
    # sous-dossier de notes ; sinon l'étape tourne sans l'option et le journal le dit. Le script ne nomme que le dossier de contexte lui-même.
    local -a option_contexte=()
    if [[ -d "$LAB_CONTEXT_FOLDER/notes" ]]; then
      option_contexte=(--context "$LAB_CONTEXT_FOLDER")
    else
      echo "dossier de contexte absent : notes de contexte inchangées"
    fi
    code_index=0
    uv run "$RACINE_CODE/tools/pmzilla_lab_library.py" index "$WORKSPACE/Bibliotheque-Lab" "$WATCH_LAB" "${option_contexte[@]}" || code_index=$?
    if (( code_index == 2 )); then
      echo "Indexation en erreur : base PostgreSQL injoignable, la bibliothèque n'est pas à jour (bash tools/db_up.sh)"
      FAILED+=("indexation (base injoignable)")
    elif (( code_index != 0 )); then
      echo "Indexation en erreur : la bibliothèque n'est pas à jour"
      FAILED+=("indexation")
    else
      mkdir -p "$DATA" && date +%s > "$STAMP"
      sonder_index_bm25
    fi
  else
    uv run "$RACINE_CODE/tools/watch_lab.py" digest || { echo "Liste à lire en erreur"; FAILED+=("liste à lire"); }
    echo "Ollama ne répond pas : pré-tri et indexation reportés au prochain passage"
    verifier_fraicheur_index
  fi
}

# Veille hebdomadaire des composants (R-41) : jamais une étape en échec, jamais bloquante
veiller_composants() {
  local code=0
  uv run "$RACINE_CODE/tools/composants.py" check --if-due || code=$?
  if (( code == 1 )); then
    notifier "Composants : nouveautés à examiner. Voir le tableau de bord."
  elif (( code != 0 )); then
    echo "Veille des composants impossible (code $code)"
    notifier "Veille des composants impossible. Voir le journal de la veille."
  fi
  return 0
}

# Tests de mutation du masquage, hebdomadaires avec rattrapage (masking-mutation-tests D7) : jamais une étape en échec,
# jamais de notification, le code de sortie de la veille inchangé ; un échec est nommé dans le journal
tester_mutation() {
  local code=0
  uv run --offline "$RACINE_CODE/tools/mutation_masking.py" run --due || code=$?
  if (( code == 2 )); then
    echo "Tests de mutation en échec : lancement impossible (code 2), voir uv run tools/mutation_masking.py report"
  elif (( code == 3 )); then
    echo "Tests de mutation en échec : score sous le seuil (code 3), voir uv run tools/mutation_masking.py report"
  elif (( code != 0 )); then
    echo "Tests de mutation en échec (code $code)"
  fi
  return 0
}

# Refus (D2) : le dossier de contenu est le dossier d'exécution (PMZILLA_LAB_RUN, par défaut le dossier run du dossier du lab) ou l'un de ses sous-dossiers.
# Un dossier de contenu égal au dossier de code dans le dépôt de développement est accepté.
dossier_de_contenu_est_arbre() {
  local arbre="${LAB_RUN_TREE:A}" contenu="${WORKSPACE:A}"
  [[ "$contenu" == "$arbre" || "$contenu" == "$arbre"/* ]] && return 0
  # Un dossier de contenu strictement dans le dossier de code est dans le dossier d'exécution quand le script est lancé par son lien
  # (le dossier du lab dérivé du contenu ne désigne alors plus le dossier d'exécution).
  [[ "$contenu" == "${RACINE_CODE:A}"/* ]]
}

# --- Décision : le passage a-t-il lieu ? ---
lire_repere
if (( PLANIFIE )); then   # lecture sans sortie ; rien à faire : code 0, rien d'écrit
  [[ "$HEURE" < "$DUE" || "$HEURE" > "$LIMITE" ]] && exit 0
  if repere_du_jour && [[ "$R_ETAT" == (termine|echoue|interrompu) ]]; then exit 0; fi
fi
resoudre_watch_lab
repere_inscriptible || refuser_repere
if ! prendre_verrou; then
  (( PLANIFIE )) && exit 0
  dire_erreur "=== Veille non lancée : un passage est déjà en cours ==="
  exit 3
fi
lire_repere   # relu sous le verrou
NOTE_REPRISE=0
if repere_du_jour; then
  if (( PLANIFIE )); then
    if [[ "$R_ETAT" == (termine|echoue|interrompu) ]]; then exit 0; fi
    if [[ "$R_ETAT" == commence ]]; then   # passage interrompu : personne ne tient le verrou
      if (( R_REPRISES >= 1 )); then
        R_ETAT="interrompu"; R_FIN="$HEURE"
        ecrire_repere >/dev/null
        exit 0
      fi
      R_REPRISES=$(( R_REPRISES + 1 )); NOTE_REPRISE=1
    fi
  fi
else
  R_NOTIFIE="false"; R_ESSAIS=0; R_REPRISES=0
fi
R_DATE="$JOUR"; R_DECL="$DECLENCHEUR"; R_DEBUT="$HEURE"; R_FIN=""; R_ETAT="commence"; R_CODE="null"

echo "=== $(date '+%Y-%m-%d %H:%M') ==="
[[ "$DECLENCHEUR" == rattrapage ]] && echo "Passage de rattrapage : la veille du jour n'avait pas eu lieu"
echo "Dossier de code : $RACINE_CODE"
echo "Dossier de contenu : $WORKSPACE"
(( R_ILLISIBLE )) && echo "Repère du passage du jour illisible : passage considéré comme dû"
(( VERROU_REPRIS )) && echo "Verrou de la veille périmé, repris"
(( NOTE_REPRISE )) && echo "Passage du jour interrompu : nouvel essai, le seul de la journée"
ecrire_repere
if dossier_de_contenu_est_arbre; then   # D2 : après le garde de R-44 et l'écriture du début, avant tout contrôle et toute étape
  echo "=== Veille arrêtée : le dossier de contenu est le dossier d'exécution ==="
  notifier "Veille arrêtée : le dossier de contenu est le dossier d'exécution. Voir installation.md, « Run worktree »."
  R_ETAT="echoue"; R_CODE="1"; R_FIN=$(paris "$(instant)" %H:%M)
  ecrire_repere
  exit 1   # le piège EXIT libère le verrou
fi
verifier_cache_uv || true
if (( PLANIFIE )); then   # réseau : seulement en planifié, avant la base
  code_reseau=0
  uv run "$RACINE_CODE/tools/watch_lab.py" check-network --wait "$ATTENTE_RESEAU" || code_reseau=$?
  if (( code_reseau != 0 )); then
    echo "Réseau absent à $(paris "$(instant)" %H:%M) : collecte, pré-tri, listes à lire et indexation du jour reportés."
    FAILED+=("réseau")
    REPORTE=1
  fi
fi
if (( ! REPORTE )); then
  code_base=0
  uv run "$RACINE_CODE/tools/watch_lab.py" check-db --wait "$ATTENTE_BASE" || code_base=$?
  if (( code_base == 0 )); then
    etapes_du_jour
  else
    if (( code_base == 5 )); then
      echo "Tables de la veille absentes : collecte, pré-tri, listes à lire et indexation du jour sautés."
    else
      echo "Base de données injoignable à $(date '+%H:%M') : collecte, pré-tri, listes à lire et indexation du jour sautés, rien n'est écrit ailleurs."
    fi
    (( code_base == 4 )) && REPORTE=1   # la base ne répond pas : reporté ; tables absentes ou autre code : échec
    FAILED+=("base de données")
  fi
fi
(( REPORTE )) && echo "Veille du jour reportée : nouvel essai au prochain passage planifié"

veiller_composants
tester_mutation

# Tableau de bord (page HTML locale) : son échec ne fait jamais échouer la veille
uv run "$RACINE_CODE/tools/dashboard.py" || echo "Tableau de bord non généré (voir ci-dessus)"

CODE=0
if (( ${#FAILED[@]} > 0 )); then
  CODE=1
  ETAPES="${(j:, :)FAILED}"
  echo "=== Veille terminée avec ${#FAILED[@]} étape(s) en échec : $ETAPES ==="
  if (( REPORTE )); then   # une seule notification de report par jour
    R_ESSAIS=$(( R_ESSAIS + 1 ))
    [[ "$R_NOTIFIE" == true ]] || notifier "Étape(s) en échec : $ETAPES. Voir ~/Library/Logs/pmzilla-watch.log"
    R_NOTIFIE="true"
  elif (( PLANIFIE )); then
    NOTIF_ECHEC_DIFFEREE=1
  else
    notifier "Étape(s) en échec : $ETAPES. Voir ~/Library/Logs/pmzilla-watch.log"
  fi
else
  echo "=== Veille terminée sans erreur ==="
fi
if (( CODE == 0 )); then R_ETAT="termine"; elif (( REPORTE )); then R_ETAT="reporte"; else R_ETAT="echoue"; fi
R_CODE="$CODE"; R_FIN=$(paris "$(instant)" %H:%M)
ecrire_repere
if (( PLANIFIE && ! REPORTE )); then   # résumé du matin (R-50) : passage terminé ou en échec seulement
  code_resume=0
  PMZILLA_SUMMARY_NOTIFY=1 uv run "$TOOLS/morning_summary.py" --notify --failed-steps "$ETAPES" || code_resume=$?
  if (( code_resume != 0 )); then
    echo "Résumé du matin non envoyé (code $code_resume)"
    (( NOTIF_ECHEC_DIFFEREE )) && notifier "Étape(s) en échec : $ETAPES. Voir ~/Library/Logs/pmzilla-watch.log"
  fi
fi
exit $CODE
