#!/bin/zsh
# Veille quotidienne de PMZilla Lab (watch) : collecte, pré-tri, liste à lire, puis mise à jour de l'index.
# Lancé chaque matin par launchd (com.pmzilla.watch.plist). Journal : ~/Library/Logs/pmzilla-watch.log
# Code de sortie : 0 si toutes les étapes ont réussi, 1 si l'une a échoué (collecte, pré-tri, liste à lire,
# indexation). Le journal le dit en toute fin et une notification macOS nomme les étapes en échec.
# Le tableau de bord (jamais bloquant) et l'absence d'Ollama (pré-tri et indexation reportés au prochain passage)
# ne comptent pas comme des échecs. Mais si Ollama est absent et que la dernière indexation réussie date de plus de
# PMZILLA_INDEXATION_MAX_JOURS jours (3 par défaut ; à régler dans le .plist, clé EnvironmentVariables), une
# notification macOS le dit, sans changer le code de sortie. La date de la dernière indexation réussie est dans
# $PMZILLA_LAB_DATA/derniere-indexation (par défaut ~/.pmzilla-lab).
set -u
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
TOOLS="$HOME/PMZilla-Lab"
WORKSPACE="$TOOLS/workspace"   # Bibliotheque-Lab et Watch-Lab y vivent, contenu exclu de Git
# Dossier de la veille : Watch-Lab, par la même logique que les scripts Python (watch_paths.py) ; sans python3, Watch-Lab.
# Si seul l'ancien dossier (Veille-Lab) existe, watch_paths.py refuse (message sur stderr : nom actuel et
# tools/migrate_watch.py) et la veille s'arrête avec le code 1.
if command -v python3 >/dev/null 2>&1; then
  WATCH_LAB=$(python3 "$WORKSPACE/tools/watch_paths.py" lab "$WORKSPACE") || { echo "=== Veille arrêtée : dossier de la veille à l'ancien nom ==="; exit 1; }
fi
[[ -n "${WATCH_LAB:-}" ]] || WATCH_LAB="$WORKSPACE/Watch-Lab"

DATA="${PMZILLA_LAB_DATA:-$HOME/.pmzilla-lab}"
STAMP="$DATA/derniere-indexation"
MAX_JOURS="${PMZILLA_INDEXATION_MAX_JOURS:-3}"
[[ "$MAX_JOURS" == <-> ]] || MAX_JOURS=3
FAILED=()   # étapes en échec, dans l'ordre

notifier() {   # un échec de notification ne change jamais le code de sortie
  osascript -e "display notification \"$1\" with title \"PMZilla watch\"" || echo "Notification macOS impossible"
}

# Ollama absent : prévenir seulement si l'index n'est plus à jour depuis trop longtemps
verifier_fraicheur_index() {
  local derniere=""
  if [[ -f "$STAMP" ]]; then derniere=$(<"$STAMP")
  elif [[ -f "$DATA/library.sqlite" ]]; then derniere=$(stat -f %m "$DATA/library.sqlite")   # avant le premier repère
  fi
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

# Copie PostgreSQL de la bibliothèque (lot 4) : après une indexation réussie, si l'utilisateur l'a activée (fichier
# $DATA/knowledge-sync, créé après le premier import réussi). Jamais bloquante : un échec est journalisé et notifié,
# il ne compte pas parmi les étapes en échec de la veille et ne change pas le code de sortie.
synchroniser_postgres() {
  [[ -f "$DATA/knowledge-sync" ]] || return 0
  if ! uv run "$WORKSPACE/tools/knowledge_import.py" import; then
    echo "Synchronisation PostgreSQL en erreur : la copie de la bibliothèque n'est pas à jour (base arrêtée ? bash tools/db_up.sh)"
    notifier "Base PostgreSQL injoignable ou synchronisation en erreur : la copie de la bibliothèque n'est pas à jour."
  else
    controler_copie_postgres
  fi
}

# Contrôle quotidien de la copie, après un import réussi : « knowledge_import.py verify » compare les deux côtés et sonde l'index BM25 (code 3 :
# index illisible, « bitmap intersection stream … claimed twice »). Jamais bloquant ni réparateur : un échec est journalisé et notifié, la veille
# continue, le code de sortie ne change pas. La reconstruction (REINDEX) se fait en superutilisateur, par l'utilisateur seul (installation.md).
controler_copie_postgres() {
  local code=0
  uv run "$WORKSPACE/tools/knowledge_import.py" verify || code=$?
  (( code == 0 )) && return 0
  if (( code == 3 )); then
    echo "Index BM25 illisible : la recherche plein texte de la base peut échouer. Procédure : docs/pmzilla/installation.md, « Damaged BM25 index »"
    notifier "Index BM25 de la base illisible. Voir installation.md, « Damaged BM25 index »."
  else
    echo "Vérification de la copie PostgreSQL en échec (code $code) : voir ci-dessus ; docs/pmzilla/installation.md, section 14.3"
    notifier "Vérification de la copie PostgreSQL en échec. Voir le journal et installation.md, section 14.3."
  fi
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
  py_v=$(cd "$WORKSPACE" 2>/dev/null && uv python find --show-version 2>/dev/null) || py_v=""
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
  # --python fixe le Python lu dans le workspace.
  local reveil="$WORKSPACE/.claude/skills/pmzilla-discovery-bmad/scripts/wake.py" reseau verif entete ok=0
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

echo "=== $(date '+%Y-%m-%d %H:%M') ==="
verifier_cache_uv || true
if ! uv run "$TOOLS/watch_lab.py" collect; then
  echo "Collecte en erreur (voir $WATCH_LAB/_rapport_collecte.txt)"
  FAILED+=("collecte")
fi

if curl -s --max-time 5 http://localhost:11434/api/tags >/dev/null; then
  # Pré-tri : notes, filtre (en mode « filtre » seulement), partages Bluesky, puis liste à lire classée.
  # En cas d'échec (pas encore de référence, modèle absent), liste simple.
  if uv run "$TOOLS/watch_triage.py" score && uv run "$TOOLS/watch_triage.py" apply \
      && uv run "$TOOLS/watch_triage.py" shares && uv run "$TOOLS/watch_triage.py" digest; then
    :
  else
    echo "Pré-tri en erreur : liste à lire non triée"
    FAILED+=("pré-tri")
    uv run "$TOOLS/watch_lab.py" digest || { echo "Liste à lire en erreur"; FAILED+=("liste à lire"); }
  fi
  # Toujours les deux dossiers : un fichier absent des deux est retiré de l'index
  if ! uv run "$TOOLS/pmzilla_lab_library.py" index "$WORKSPACE/Bibliotheque-Lab" "$WATCH_LAB"; then
    echo "Indexation en erreur : la bibliothèque n'est pas à jour"
    FAILED+=("indexation")
  else
    mkdir -p "$DATA" && date +%s > "$STAMP"
    synchroniser_postgres
  fi
else
  uv run "$TOOLS/watch_lab.py" digest || { echo "Liste à lire en erreur"; FAILED+=("liste à lire"); }
  echo "Ollama ne répond pas : pré-tri et indexation reportés au prochain passage"
  verifier_fraicheur_index
fi

# Tableau de bord (page HTML locale) : son échec ne fait jamais échouer la veille
uv run "$WORKSPACE/tools/dashboard.py" || echo "Tableau de bord non généré (voir ci-dessus)"

if (( ${#FAILED[@]} > 0 )); then
  ETAPES="${(j:, :)FAILED}"
  echo "=== Veille terminée avec ${#FAILED[@]} étape(s) en échec : $ETAPES ==="
  notifier "Étape(s) en échec : $ETAPES. Voir ~/Library/Logs/pmzilla-watch.log"
  exit 1
fi
echo "=== Veille terminée sans erreur ==="
