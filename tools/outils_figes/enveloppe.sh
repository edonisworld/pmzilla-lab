#!/bin/bash
# PMZilla Lab : fonctions communes des enveloppes figées (niveau 2 du bac à sable, design D4, D5, D12 ; tâches 7.2, 7.3, 7.5 ; R-20261109-09, -12).
#
# Il y a cinq enveloppes : ci_local.sh, gh_issue.sh, flow_views.sh et worktree.sh sont les commandes que le bac à sable de Bash laisse tourner hors de lui
# (`excludedCommands` du fichier géré) ; npm_ci.sh n'est PAS exclue, elle tourne sous le bac à sable (R-20261110-29 Q1). Chacune est copiée
# par l'auteur (fichier d'étape) et par la fin d'un train dans ~/.pmzilla-lab/outils-figes/, un dossier qu'aucune session ne peut écrire, et
# sourcée par ses quatre sœurs depuis CE dossier (jamais depuis le dépôt) : `. "$ICI/enveloppe.sh"`. Rien ici ne s'exécute au chargement
# sauf la remise à zéro du PATH et des variables de l'interpréteur.
#
# Ce que fait chaque enveloppe, dans cet ordre (design D4) :
#   0. la relance (R-20261111-13, -15) : en tête de chaque enveloppe, avant toute commande appelée par son nom, elle se relance par
#      `exec /usr/bin/env -i FIGE_RELANCE=<pid> /bin/bash --noprofile --norc <son chemin> "$@"` : environnement vidé (aucune variable de la session,
#      donc ni BASH_ENV, ni ENV, ni fonction exportée), ni profil ni rc. Le marqueur est le PID de l'enveloppe (exec le conserve). Limite réelle
#      (R-20261111-19 à -22, -23, -38) : les quatre enveloppes exclues du bac à sable s'appellent dans la forme /bin/bash --noprofile --norc -p (l'ancien ordre
#      `/bin/bash -p --noprofile --norc` est refusé par la garde). Sur le /bin/bash 3.2.57 du Mac, -p ferme BASH_ENV, ENV, les fonctions importées et SHELLOPTS (suite
#      forme_p_mac, M1) ; CDPATH y reste suivi (constat M2) : il est tenu par cette relance sous `env -i`, qui n'est précédée d'aucune commande nommée ni d'aucun `cd`
#      (test statique), et par la garde de session, à qui restent aussi PATH, IFS, LANG et LC_*. Le marqueur se forge par un exec qui garde le PID, et une fonction exportée
#      `exec` ou `unset` détourne la relance. Le premier bash a lu BASH_ENV avant la première ligne (sans -p) : cela, aucun script ne peut le défaire, d'où la garde de session
#      (tools/garde_session.py), qui refuse notamment BASH_ENV, ENV, SHELLOPTS, BASHOPTS, PS4, FIGE_RELANCE, BASH_FUNC_… (variable, argument d'env ou nom de
#      commande), `export -f`, `declare -Fx` et `typeset -Fx`, et `set -a` (ou `set -o allexport`, `bash -a`) quand une définition de fonction est dans la commande.
#      Remplace : rien. Retrait de la relance : permanent tant que les enveloppes sont exclues du bac à sable.
#   1. fige_verifier : le relevé `empreintes.sha256` du dossier (une ligne « <sha256> deux espaces <nom relatif> » par fichier figé, la forme de
#      `shasum -a 256`) doit exister, chaque fichier listé doit être égal à son empreinte, et chaque fichier dont l'enveloppe a besoin doit y
#      figurer ; sinon code 97 et la ligne « outil figé : empreinte différente de son relevé, rien n'est lancé : <nom> » ; rien n'est lancé ;
#   2. la sous-commande et les arguments sont contrôlés contre une liste fermée : code 96 (« sous-commande refusée : <nom> », « argument
#      refusé : <option> », « argument refusé : branche », « argument refusé : base ») ; aucune ligne n'imprime la valeur d'un argument ;
#   3. l'outil figé est lancé par `env -i` avec un environnement bâti ici depuis dossiers.conf et une liste fermée ; les variables de la
#      session ne passent jamais ; le code de l'outil est rendu tel quel. Cet environnement pose aussi, par la configuration de git passée en variables
#      (GIT_CONFIG_COUNT et suivantes), les crochets du dépôt (core.hooksPath) et core.fsmonitor=false, et, pour uv, UV_NO_CONFIG, UV_CACHE_DIR et UV_PYTHON.
#
# dossiers.conf (écrit par l'auteur, listé au relevé) : une ligne `clé=valeur` par dossier, chemins absolus, toutes les clés obligatoires :
#   maison, workspace, worktrees, etapes, scratchpad, donnees, noms (la liste des noms sensibles), crochets (le dossier des crochets de git du
#   dépôt), cache_uv (le cache de uv), python (l'interpréteur de uv).
#   scratchpad : le préfixe physique (liens résolus), propre au compte, des dossiers temporaires des sessions : sans « ~ », sans « : », sans « / »
#   final, et jamais `/`, `/tmp`, `/private/tmp` (ni leurs voisins `/var/tmp`, `/private/var/tmp`) ; il doit exister. etapes : sans « : ».
#   Une clé manquante ou une valeur non absolue ou refusée : code 97 sur dossiers.conf (fige_conf_controle, appelée par chaque enveloppe juste après le relevé).
# Les codes 96 et 97 ne heurtent aucun code des outils figés (en-têtes lus : ci_local 0 à 8, 61 ; gh_issue 0 à 8 ; flow_views 0, 1, 2, 78).
# worktree.sh rend en plus le code 3 (liste des noms sensibles absente, rien n'est créé) ; les autres codes de git ou de npm sont rendus tels quels.
#
# Remplace : l'appel direct de ces outils depuis l'espace de travail par la session (lancements qui tournent désormais dans le bac à sable,
# sans réseau ni socket Docker). Retrait : avec le bac à sable (retour arrière final de la décision R-20261107-28).
# Bash 3.2 (celui de macOS) : ni tableau associatif, ni mapfile, ni minuscules par ${x,,}.

PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PATH
unset BASH_ENV ENV CDPATH IFS
LC_ALL=C
export LC_ALL

fige_dire() { printf 'outil figé : %s\n' "$*" >&2; }
fige_refuse() { local code=$1; shift; fige_dire "$*"; exit "$code"; }
fige_97() { fige_refuse 97 "empreinte différente de son relevé, rien n'est lancé : $1"; }
fige_arg_refuse() { fige_refuse 96 "argument refusé : $1"; }

# Le nom d'une sous-commande refusée : imprimé tel quel seulement s'il a la forme d'un mot (lettres, chiffres, tiret, 32 caractères au plus),
# sinon « ? » : aucune ligne ne reprend un texte libre de la session.
fige_nom_sain() {
  case "$1" in
    ""|*[!A-Za-z0-9-]*) printf '?' ;;
    *) if [ "${#1}" -le 32 ]; then printf '%s' "$1"; else printf '?'; fi ;;
  esac
}
fige_sous_refusee() { fige_refuse 96 "sous-commande refusée : $(fige_nom_sain "$1")"; }

# L'empreinte : le programme par son chemin absolu, sous `env -i` (ni PERL5OPT, ni fonction exportée, ni variable de la session ne l'atteignent).
fige_sha() {
  if [ -x /usr/bin/shasum ]; then /usr/bin/env -i /usr/bin/shasum -a 256 -- "$1" | cut -d' ' -f1
  else /usr/bin/env -i /usr/bin/sha256sum -- "$1" | cut -d' ' -f1; fi
}

# fige_verifier <nom relatif>... : le relevé est lu et respecté (étape 1), et chaque nom donné doit y figurer.
fige_verifier() {
  local releve="$FIGES/empreintes.sha256" ligne attendu nom vus=" " exige
  [ -f "$releve" ] && [ ! -L "$releve" ] || fige_97 empreintes.sha256
  while IFS= read -r ligne || [ -n "$ligne" ]; do
    [ -n "${ligne//[[:space:]]/}" ] || continue
    attendu=${ligne%%  *}
    nom=${ligne#*  }
    if ! [[ $attendu =~ ^[0-9a-f]{64}$ ]] || [ -z "$nom" ] || [ "$nom" = "$ligne" ]; then fige_97 empreintes.sha256; fi
    case "$nom" in /*|*..*) fige_97 empreintes.sha256 ;; esac
    { [ -f "$FIGES/$nom" ] && [ ! -L "$FIGES/$nom" ]; } || fige_97 "$nom"
    [ "$(fige_sha "$FIGES/$nom")" = "$attendu" ] || fige_97 "$nom"
    vus="$vus$nom "
  done < "$releve"
  for exige in "$@"; do
    case "$vus" in *" $exige "*) ;; *) fige_97 "$exige" ;; esac
  done
}

# fige_conf <clé> : la valeur de dossiers.conf, ou rien. fige_conf_exige <clé> : la valeur, absolue et non vide, sinon code 97 sur dossiers.conf.
fige_conf() {
  local cle=$1 k v
  while IFS== read -r k v || [ -n "$k" ]; do
    if [ "$k" = "$cle" ]; then printf '%s' "$v"; return 0; fi
  done < "$FIGES/dossiers.conf"
  return 0
}
fige_conf_exige() {
  local v
  v=$(fige_conf "$1")
  case "$v" in /*) printf '%s' "$v" ;; *) fige_97 dossiers.conf ;; esac
}

# fige_sous <chemin> <dossier> : 0 quand le fichier (existant ou à créer) est sous le dossier, liens résolus ; chemin absolu seulement, sans
# « . » ni « .. », dernier élément qui n'est pas un lien, dossier parent existant.
fige_sous() {
  local chemin=$1 base=$2 parent nom physique racine
  case "$chemin" in /*) ;; *) return 1 ;; esac
  case "$chemin/" in */../*|*/./*) return 1 ;; esac
  [ ! -L "$chemin" ] || return 1
  parent=$(dirname -- "$chemin")
  nom=$(basename -- "$chemin")
  [ -n "$nom" ] || return 1
  physique=$(cd -P -- "$parent" 2>/dev/null && pwd -P) || return 1
  racine=$(cd -P -- "$base" 2>/dev/null && pwd -P) || return 1
  case "$physique/" in "$racine"/*) return 0 ;; *) return 1 ;; esac
}

# fige_conf_controle : toutes les clés de dossiers.conf sont là, absolues ; le scratchpad est un chemin physique propre au compte (voir l'en-tête) ; sinon 97.
fige_conf_controle() {
  local cle v
  for cle in maison workspace worktrees etapes scratchpad donnees noms crochets cache_uv python; do
    v=$(fige_conf_exige "$cle") || exit 97              # la ligne est déjà écrite par le sous-shell ; le code 97 est rendu ici
    case "$v" in *[[:cntrl:]]*) fige_97 dossiers.conf ;; esac
  done
  v=$(fige_conf_exige scratchpad) || exit 97
  case "$v" in /|/tmp|/private/tmp|/var/tmp|/private/var/tmp|*/|*"~"*|*:*) fige_97 dossiers.conf ;; esac
  [ "$(cd -P -- "$v" 2>/dev/null && pwd -P)" = "$v" ] || fige_97 dossiers.conf
  v=$(fige_conf_exige etapes) || exit 97
  case "$v" in *:*) fige_97 dossiers.conf ;; esac
}

# fige_physique <dossier> : le chemin physique du dossier (liens résolus), ou rien.
fige_physique() { (cd -P -- "$1" 2>/dev/null && pwd -P); }

# fige_inscrit <chemin physique> : 0 quand le dossier est inscrit comme worktree du workspace, c'est-à-dire quand un fichier gitdir de
# <workspace>/.git/worktrees/*/ contient « <chemin>/.git ». Lecture seule, aucun git lancé, rien de ce que la session écrit dans son worktree n'est cru.
fige_inscrit() {
  local phys=$1 workspace f l
  workspace=$(fige_conf_exige workspace) || exit 97
  for f in "$workspace"/.git/worktrees/*/gitdir; do
    { [ -f "$f" ] && [ ! -L "$f" ]; } || continue
    l=""
    IFS= read -r l < "$f" || true
    [ "$l" = "$phys/.git" ] && return 0
  done
  return 1
}

# fige_worktree_valide <dossier> : un worktree existant, EXACTEMENT un niveau sous le dossier des worktrees (liens résolus), qui porte un fichier .git
# et qui est inscrit par le workspace (fige_inscrit).
fige_worktree_valide() {
  local dir=$1 base physique racine rel
  case "$dir" in /*) ;; *) return 1 ;; esac
  case "$dir/" in */../*|*/./*) return 1 ;; esac
  [ -d "$dir" ] && [ -f "$dir/.git" ] || return 1
  base=$(fige_conf_exige worktrees) || exit 97       # (idem : le sous-shell a écrit la ligne)
  physique=$(fige_physique "$dir") || return 1
  racine=$(fige_physique "$base") || return 1
  rel=${physique#"$racine"/}
  { [ "$rel" != "$physique" ] && [ -n "$rel" ]; } || return 1
  case "$rel" in */*) return 1 ;; esac
  fige_inscrit "$physique"
}

# fige_git_cfg <dossier des crochets> : écrit GIT_CFG, la configuration de git passée par l'environnement à toute commande lancée ici : les crochets du dépôt
# (que la session ne peut pas écrire) et pas de moniteur de système de fichiers. Elle l'emporte sur la configuration du dépôt, que la session peut écrire.
fige_git_cfg() {
  GIT_CFG=("GIT_CONFIG_COUNT=2" "GIT_CONFIG_KEY_0=core.hooksPath" "GIT_CONFIG_VALUE_0=$1" "GIT_CONFIG_KEY_1=core.fsmonitor" "GIT_CONFIG_VALUE_1=false")
}

# fige_env : bâtit ENV_FIGE, l'environnement de l'outil figé, depuis une liste fermée et dossiers.conf (jamais depuis la session).
fige_env() {
  local maison workspace donnees noms crochets cache python
  maison=$(fige_conf_exige maison) || exit 97         # (idem : le sous-shell a écrit la ligne)
  workspace=$(fige_conf_exige workspace) || exit 97
  donnees=$(fige_conf_exige donnees) || exit 97
  noms=$(fige_conf_exige noms) || exit 97
  crochets=$(fige_conf_exige crochets) || exit 97
  cache=$(fige_conf_exige cache_uv) || exit 97
  python=$(fige_conf_exige python) || exit 97
  fige_git_cfg "$crochets"
  ENV_FIGE=("PATH=$maison/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" "HOME=$maison" "LANG=en_US.UTF-8"
            "UV_OFFLINE=1" "UV_NO_CONFIG=1" "UV_CACHE_DIR=$cache" "UV_PYTHON=$python" "GH_PROMPT_DISABLED=1" "GIT_TERMINAL_PROMPT=0"
            "PMZILLA_LAB_WORKSPACE=$workspace" "PMZILLA_LAB_DATA=$donnees" "PMZILLA_LAB_SENSITIVE_NAMES=$noms" "${GIT_CFG[@]}")
}

# fige_dans_liste <mot> <mot>... : 0 quand le premier mot figure parmi les suivants.
fige_dans_liste() {
  local mot=$1 x
  shift
  for x in "$@"; do [ "$x" = "$mot" ] && return 0; done
  return 1
}
