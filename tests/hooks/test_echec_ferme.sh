#!/bin/sh
# Classe D de l'audit #629 (audit-kraken/lots/L1-classes.md, gardes qui échouent ouvertes), constats A-41 (reference-transaction hors session),
# A-42 (pre-merge-commit : erreur de git, verrou périmé sans preuve) et A-43 (pre-commit) : une garde ne rend « permis » que sur une preuve
# positive. Une erreur de git qui ne donne pas le dossier Git commun (sous un verrou vivant ou sans verrou), un dossier commun illisible, un
# verrou périmé dont le processus n'est pas prouvé mort : refus, avec « vérification impossible ».
# Dépôt temporaire, verrou fait à la main, faux `git` placé devant le vrai dans PATH : il échoue sur la seule demande du dossier Git commun.
# Remplace : les « return 0 » et « exit 0 » de ces trois crochets sur une erreur de git (cas D1 à D3 de la classe D). Retrait : permanent (une
# garde qui échoue ouverte est un défaut, R-20261107-26).
# Lancement : sh tests/hooks/test_echec_ferme.sh
set -u
RACINE=$(cd "$(dirname "$0")/../.." && pwd -P)
tmp=$(cd "$(mktemp -d)" && pwd -P) || exit 1
trap 'rm -rf "$tmp"' EXIT
export GIT_CONFIG_GLOBAL="$tmp/gitconfig" GIT_CONFIG_SYSTEM=/dev/null GIT_TERMINAL_PROMPT=0 GIT_CEILING_DIRECTORIES="$tmp"
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE FINISH_LOCK_TOKEN PMZILLA_FINISH_LOCK_MAX_AGE CLAUDECODE
git config --global user.email t@example.org
git config --global user.name test
git config --global init.defaultBranch main
ok=0; ko=0
verifie() { # description condition-vraie (0 = vrai)
  if [ "$2" -eq 0 ]; then echo "ok : $1"; ok=$((ok+1)); else echo "ECHEC : $1 :: $SORTIE"; ko=$((ko+1)); fi
}
contient() { printf '%s' "$SORTIE" | grep -qF -- "$1"; }

nouveau_depot() { # nom : dépôt avec les outils copiés, sans verrou
  d="$tmp/$1"; mkdir -p "$d/tools/hooks"
  cp "$RACINE/tools/finish_lock.py" "$d/tools/"
  ( cd "$d" && git init -q . && echo base > f.txt && git add -A && git commit -q -m base ) || exit 1
}
pose_verrou() { # dépôt pid [âge en secondes]
  mkdir -p "$1/.git/pmzilla-fin-en-cours"
  ( cd "$1/.git/pmzilla-fin-en-cours" && echo "$2" > pid && echo $(( $(date +%s) - ${3:-0} )) > debut && echo feat/autre > branche && echo jeton-du-verrou > jeton )
}

nouveau_depot depot; depot="$tmp/depot"; pose_verrou "$depot" $$
nouveau_depot libre; libre="$tmp/libre"   # sans dossier de verrou
mkdir -p "$tmp/bin"
vrai_git=$(command -v git)
cat > "$tmp/bin/git" <<EOF
#!/bin/sh
case "\$*" in *--git-common-dir*) exit 128 ;; esac
exec "$vrai_git" "\$@"
EOF
chmod +x "$tmp/bin/git"
mkdir -p "$tmp/bin2"
cat > "$tmp/bin2/git" <<EOF
#!/bin/sh
case "\$*" in *--show-toplevel*) exit 128 ;; esac
exec "$vrai_git" "\$@"
EOF
chmod +x "$tmp/bin2/git"
ancien=$(git -C "$depot" rev-parse HEAD)
nouvelle=$(printf '1%.0s' $(seq 1 40))

# D1 : reference-transaction, hors session, état prepared, une ligne qui vise main
for cas in "sous un verrou vivant:$depot" "sans verrou:$libre"; do
  etiquette=${cas%%:*}; d=${cas#*:}
  SORTIE=$(cd "$d" && printf '%s %s refs/heads/main\n' "$ancien" "$nouvelle" | PATH="$tmp/bin:$PATH" sh "$RACINE/tools/hooks/reference-transaction" prepared 2>&1); CODE=$?
  [ "$CODE" -ne 0 ] && contient "vérification impossible"; verifie "D1 : reference-transaction refuse quand git échoue ($etiquette)" $?
done

# D2 : pre-merge-commit
for cas in "sous un verrou vivant:$depot" "sans verrou:$libre"; do
  etiquette=${cas%%:*}; d=${cas#*:}
  SORTIE=$(cd "$d" && PATH="$tmp/bin:$PATH" python3 "$RACINE/tools/hooks/pre-merge-commit" 2>&1); CODE=$?
  [ "$CODE" -ne 0 ] && contient "vérification impossible"; verifie "D2 : pre-merge-commit refuse quand git échoue ($etiquette)" $?
done

# D3 : pre-commit (le contournement du lancement vert ne change rien au gel)
for cas in "sous un verrou vivant:$depot" "sans verrou:$libre"; do
  etiquette=${cas%%:*}; d=${cas#*:}
  SORTIE=$(cd "$d" && PMZILLA_SKIP_GREEN_CHECK=1 PMZILLA_LAB_WORKSPACE="$d" PATH="$tmp/bin:$PATH" python3 "$RACINE/tools/hooks/pre-commit" 2>&1); CODE=$?
  [ "$CODE" -ne 0 ] && contient "vérification impossible"; verifie "D3 : pre-commit refuse quand git échoue ($etiquette)" $?
done

# Git absent du PATH (l'outil manque) : refus aussi, pour pre-merge-commit et pre-commit (python3 est lancé par chemin absolu)
py=$(command -v python3)
SORTIE=$(cd "$depot" && PATH="$tmp/vide" "$py" "$RACINE/tools/hooks/pre-merge-commit" 2>&1); CODE=$?
[ "$CODE" -ne 0 ] && contient "vérification impossible"; verifie "D2 : pre-merge-commit refuse quand git est absent" $?
SORTIE=$(cd "$depot" && PMZILLA_SKIP_GREEN_CHECK=1 PMZILLA_LAB_WORKSPACE="$depot" PATH="$tmp/vide" "$py" "$RACINE/tools/hooks/pre-commit" 2>&1); CODE=$?
[ "$CODE" -ne 0 ] && contient "vérification impossible"; verifie "D3 : pre-commit refuse quand git est absent" $?

# A-43 : le dossier commun est lu mais pas le sommet du dépôt (rev-parse --show-toplevel échoue), sans verrou : refus, le contrôle n'est pas sauté
SORTIE=$(cd "$libre" && PMZILLA_SKIP_GREEN_CHECK=1 PMZILLA_LAB_WORKSPACE="$libre" PATH="$tmp/bin2:$PATH" python3 "$RACINE/tools/hooks/pre-commit" 2>&1); CODE=$?
[ "$CODE" -ne 0 ] && contient "vérification impossible"; verifie "D3 : pre-commit refuse quand le sommet du dépôt n'est pas lu (sans verrou)" $?

# A-42 : verrou périmé. Processus mort = preuve positive que la fin a disparu : la fusion passe (déjà couvert par test_lock_hooks.sh).
# Processus vivant mais verrou plus vieux que le maximum : aucune preuve, refus.
# Les deux cas ci-dessous (reference-transaction et pre-merge-commit sur un verrou vieux dont le processus vit) recoupent test_lock_hooks.sh,
# lignes 101 à 104 (update-ref de main refusé, « vérification impossible »). Source : test_lock_hooks.sh. Écart : les deux assertions portent sur
# le même refus ; si le comportement change d'un côté seulement, une seule des deux suites (echec-ferme, lock-hooks) devient rouge, et c'est
# l'écart. Remplace : rien (recoupement voulu : ce fichier garde les cas de la classe D). Retrait : permanent.
nouveau_depot vieux; vieux="$tmp/vieux"; pose_verrou "$vieux" $$ 120
SORTIE=$(cd "$vieux" && PMZILLA_FINISH_LOCK_MAX_AGE=60 python3 "$RACINE/tools/hooks/pre-merge-commit" 2>&1); CODE=$?
[ "$CODE" -ne 0 ] && contient "vérification impossible"; verifie "A-42 : pre-merge-commit refuse un verrou périmé par l'âge dont le processus vit" $?
SORTIE=$(cd "$vieux" && printf '%s %s refs/heads/main\n' "$ancien" "$nouvelle" | PMZILLA_FINISH_LOCK_MAX_AGE=60 sh "$RACINE/tools/hooks/reference-transaction" prepared 2>&1); CODE=$?
[ "$CODE" -ne 0 ] && contient "vérification impossible"; verifie "A-42 : reference-transaction refuse un verrou périmé par l'âge dont le processus vit" $?
COMMANDE_DEBLOCAGE="python3 tools/finish_lock.py debloquer"
contient "$COMMANDE_DEBLOCAGE"; verifie "A-42 : le message de refus de reference-transaction contient la commande de déblocage" $?
SORTIE=$(cd "$vieux" && PMZILLA_FINISH_LOCK_MAX_AGE=60 python3 "$RACINE/tools/hooks/pre-merge-commit" 2>&1); CODE=$?
contient "$COMMANDE_DEBLOCAGE"; verifie "A-42 : le message de refus de pre-merge-commit contient la commande de déblocage" $?
# la fin elle-même (jeton égal) passe, même si son verrou a dépassé l'âge
SORTIE=$(cd "$vieux" && FINISH_LOCK_TOKEN=jeton-du-verrou PMZILLA_FINISH_LOCK_MAX_AGE=60 python3 "$RACINE/tools/hooks/pre-merge-commit" 2>&1); CODE=$?
[ "$CODE" -eq 0 ]; verifie "A-42 : pre-merge-commit laisse passer la fin elle-même (jeton égal) sur un verrou vieux" $?

# La commande de déblocage elle-même (réservée à l'auteur) : retire un verrou périmé, jamais un verrou tenu, refusée en session
nouveau_depot debloc; debloc="$tmp/debloc"
pose_verrou "$debloc" $$ 120
# la durée du verrou est celle par défaut (21600 s) : une variable d'âge maximum ne rend pas un verrou tenu périmé (non posée ici)
SORTIE=$(cd "$debloc" && python3 tools/finish_lock.py debloquer 2>&1); CODE=$?
[ "$CODE" -eq 1 ] && [ -d "$debloc/.git/pmzilla-fin-en-cours" ]; verifie "déblocage : un verrou tenu (processus vivant, dans l'âge) n'est pas retiré (code 1)" $?
SORTIE=$(cd "$debloc" && PMZILLA_FINISH_LOCK_MAX_AGE=60 python3 tools/finish_lock.py debloquer 2>&1); CODE=$?
[ "$CODE" -eq 1 ] && [ -d "$debloc/.git/pmzilla-fin-en-cours" ]; verifie "déblocage : la variable d'âge maximum n'est pas lue (verrou de 120 s, code 1)" $?
SORTIE=$(cd "$debloc" && CLAUDECODE=1 python3 tools/finish_lock.py debloquer 2>&1); CODE=$?
[ "$CODE" -eq 6 ] && [ -d "$debloc/.git/pmzilla-fin-en-cours" ]; verifie "déblocage : refusé en session, rien retiré (code 6)" $?
SORTIE=$(cd "$debloc" && CLAUDECODE= python3 tools/finish_lock.py debloquer 2>&1); CODE=$?
[ "$CODE" -eq 6 ] && [ -d "$debloc/.git/pmzilla-fin-en-cours" ]; verifie "déblocage : marqueur de session posé mais vide, refusé aussi (code 6)" $?
pose_verrou "$debloc" $$ 30000
SORTIE=$(cd "$debloc" && python3 tools/finish_lock.py debloquer 2>&1); CODE=$?
[ "$CODE" -eq 0 ] && [ ! -e "$debloc/.git/pmzilla-fin-en-cours" ]; verifie "déblocage : un verrou périmé par l'âge (30000 s, durée par défaut) est retiré (code 0)" $?
contient "processus $$ encore vivant"; verifie "déblocage : un verrou périmé par l'âge dont le processus vit le dit avant le retrait" $?
SORTIE=$(cd "$debloc" && python3 tools/finish_lock.py debloquer 2>&1); CODE=$?
[ "$CODE" -eq 0 ] && contient "aucun verrou"; verifie "déblocage : sans verrou, rien à faire (code 0)" $?
mort=$(sh -c 'echo $$')
nouveau_depot debloc2; debloc2="$tmp/debloc2"; pose_verrou "$debloc2" "$mort"
SORTIE=$(cd "$debloc2" && python3 tools/finish_lock.py debloquer 2>&1); CODE=$?
[ "$CODE" -eq 0 ] && [ ! -e "$debloc2/.git/pmzilla-fin-en-cours" ]; verifie "déblocage : un verrou dont le processus est mort est retiré (code 0)" $?
! contient "encore vivant"; verifie "déblocage : un processus mort n'affiche pas la ligne « encore vivant »" $?

# Pid illisible (A-42, revue de la branche) : message et décision du déblocage (la course du renommage est prouvée dans la suite pilot). Remplace : rien (cas neuf).
# Retrait : permanent. Dossier vieux (touch -t) : retiré ; dossier frais : non retiré, avec un message qui dit le pid illisible.
nouveau_depot debloc3; debloc3="$tmp/debloc3"
pose_verrou "$debloc3" "pas-un-pid"
SORTIE=$(cd "$debloc3" && python3 tools/finish_lock.py debloquer 2>&1); CODE=$?
[ "$CODE" -eq 1 ] && [ -d "$debloc3/.git/pmzilla-fin-en-cours" ] && contient "pid illisible"; verifie "déblocage : pid illisible et dossier frais, non retiré, le message dit le pid illisible (code 1)" $?
! contient "processus vivant"; verifie "déblocage : pid illisible, le message ne parle pas de processus vivant" $?
touch -t 202001010000 "$debloc3/.git/pmzilla-fin-en-cours"
SORTIE=$(cd "$debloc3" && python3 tools/finish_lock.py debloquer 2>&1); CODE=$?
[ "$CODE" -eq 0 ] && [ ! -e "$debloc3/.git/pmzilla-fin-en-cours" ]; verifie "déblocage : pid illisible et dossier vieux, retiré (code 0)" $?

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
