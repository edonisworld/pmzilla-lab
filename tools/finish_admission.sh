# PMZilla Lab : règle d'admission d'un worktree, source unique pour le train (les fins unitaires qui la partageaient sont retirées par B9)
# (change finish-single-b3-b6, B4, design D8 et D12). Source unique de la règle des fichiers ignorés qui seraient perdus, de la propreté d'un
# worktree et de la lecture de la trace de revue, pour tools/finish_train.sh (train ;
# admission et nouvelle vérification avant le retrait d'un worktree).
# Module SOURCÉ (bash du système, 3.2 sur Mac ; ni mapfile ni construction récente) ; il ne contient aucun exit, n'imprime rien, ne change ni les
# options du shell appelant ni son dossier courant, et n'écrit aucun fichier. Chaque appelant garde ses phrases, ses codes et sa présentation.
#
#     . "$(dirname "$0")/finish_admission.sh"
#     fa_ignored "$worktree"                  pose FA_IGN_COUNT (nombre de fichiers ignorés qui seraient perdus) et FA_IGN_DIRS (dossiers de premier niveau,
#                                             un par ligne, dans l'ordre où Git les liste ; « (racine) » pour un fichier à la racine) ; jamais un nom de fichier
#     fa_clean "$worktree"                    rend 0 quand « git status --porcelain » est vide, 1 sinon (aussi quand Git échoue : fail-closed)
#     fa_review_done "$branche" "$sommet"     rend 0 quand la liste des branches prêtes tient une ligne de cette branche, à ce sommet exact (40 hexadécimaux),
#                                             avec la revue « faite » ; 1 dans tous les autres cas (fail-closed)
#
# Lancé seul, il ne fait rien (il ne définit que des fonctions) :
#
#     bash tools/finish_admission.sh
#
# fa_ignored : lit « git ls-files -z --others --ignored --exclude-standard » (chemins en -z : noms non ASCII, guillemets, barres inverses ou retours à la
# ligne non cités). Exceptés (ils ne comptent pas) : le réglage local de .claude/ (settings.local.json), les caches Python (__pycache__, *.pyc), les
# .DS_Store, le contenu d'un composant node_modules situé sous mothra/ qui est un vrai dossier du worktree (jamais un lien symbolique, qui reste compté) ET
# que Git ignore lui-même (un dossier suivi ne l'est pas), et le contenu de mothra/front/dist/, même règle (R-148 u16 et u18).
# fa_review_done : la liste est celle de la décision R-20261028-61 (tools/train_ready.py, fichier hors Git de la session), lue par le lecteur de R-166
# (train_ready.read_list), jamais par un second fichier ; un fichier absent ou illisible, une ligne absente, un autre sommet ou une revue « non requise »
# donnent « pas de revue ». Ce module n'écrit jamais cette liste.
#
# Codes de sortie du script : sans objet (module sourcé).

FA_IGN_COUNT=0
FA_IGN_DIRS=""
FA_NM_EXEMPTE=""   # dernier node_modules reconnu exempté : ses milliers de fichiers ne refont ni le test de dossier ni le test d'ignorance
FA_NM_REFUSE=""    # dernier node_modules refusé : ses fichiers ne refont pas non plus les tests
FA_DIST_EXEMPTE=""
FA_ROOT=""
FA_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

fa_sous_node_modules_mothra() { # chemin relatif : vrai si sous mothra/, dans un composant node_modules qui est un vrai dossier ignoré du worktree FA_ROOT
  local reste base comp
  case "$1" in mothra/*) ;; *) return 1 ;; esac
  case "$1" in "$FA_NM_EXEMPTE"/*) [ -n "$FA_NM_EXEMPTE" ] && return 0 ;; esac
  case "$1" in "$FA_NM_REFUSE"/*) [ -n "$FA_NM_REFUSE" ] && return 1 ;; esac
  base="mothra"; reste="${1#mothra/}"
  while :; do
    case "$reste" in */*) ;; *) return 1 ;; esac
    comp="${reste%%/*}"; reste="${reste#*/}"; base="$base/$comp"
    if [ "$comp" = node_modules ]; then
      if [ -d "$FA_ROOT/$base" ] && [ ! -L "$FA_ROOT/$base" ] && git -C "$FA_ROOT" check-ignore -q "$base/" 2>/dev/null; then FA_NM_EXEMPTE="$base"; return 0; fi
      FA_NM_REFUSE="$base"; return 1
    fi
  done
}

fa_sous_dist_mothra() { # chemin relatif : vrai si sous mothra/front/dist/, qui est un vrai dossier ignoré du worktree FA_ROOT (même règle que node_modules)
  case "$1" in mothra/front/dist/*) ;; *) return 1 ;; esac
  case "$FA_DIST_EXEMPTE" in 1) return 0 ;; 0) return 1 ;; esac
  if [ -d "$FA_ROOT/mothra/front/dist" ] && [ ! -L "$FA_ROOT/mothra/front/dist" ] && git -C "$FA_ROOT" check-ignore -q "mothra/front/dist/" 2>/dev/null; then FA_DIST_EXEMPTE=1; return 0; fi
  FA_DIST_EXEMPTE=0; return 1
}

fa_ignored() { # worktree : pose FA_IGN_COUNT et FA_IGN_DIRS
  local f premier
  FA_IGN_COUNT=0; FA_IGN_DIRS=""; FA_NM_EXEMPTE=""; FA_NM_REFUSE=""; FA_DIST_EXEMPTE=""; FA_ROOT=$1
  while IFS= read -r -d '' f; do
    [ -n "$f" ] || continue
    case "$f" in .claude/settings.local.json|__pycache__/*|*/__pycache__/*|*.pyc|.DS_Store|*/.DS_Store) continue ;; esac
    fa_sous_node_modules_mothra "$f" && continue
    fa_sous_dist_mothra "$f" && continue
    FA_IGN_COUNT=$((FA_IGN_COUNT + 1))
    case "$f" in */*) premier=${f%%/*} ;; *) premier="(racine)" ;; esac
    case "
$FA_IGN_DIRS
" in *"
$premier
"*) ;; *) FA_IGN_DIRS="$FA_IGN_DIRS${FA_IGN_DIRS:+
}$premier" ;; esac
  done < <(git -C "$1" ls-files -z --others --ignored --exclude-standard 2>/dev/null)
  return 0
}

fa_clean() { # worktree : 0 quand rien n'est modifié, indexé ou non suivi (hors fichiers ignorés) ; 1 sinon, dont un échec de Git
  local s
  s=$(git -C "$1" status --porcelain 2>/dev/null) || return 1
  [ -z "$s" ]
}

fa_review_done() { # branche sommet : 0 quand la revue est enregistrée pour cette branche à ce sommet exact
  local reponse
  [ -f "$FA_DIR/train_ready.py" ] || return 1
  reponse=$(python3 -I -c '
import sys
sys.path.insert(0, sys.argv[1])
import train_ready
branche, sommet = sys.argv[2], sys.argv[3]
for e in train_ready.read_list():
    if e["branche"] == branche and e["sommet"] == sommet and e["revue"] == "faite":
        print("oui")
        break
' "$FA_DIR" "$1" "$2" 2>/dev/null </dev/null) || return 1
  [ "$reponse" = oui ]
}
