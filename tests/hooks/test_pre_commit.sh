#!/bin/sh
# Test du hook pre-commit : dépôt Git temporaire, liste factice, aucun appel à Claude.
# Lancement à la main : sh tests/hooks/test_pre_commit.sh
set -u
unset PMZILLA_NOMS PMZILLA_LAB_SENSITIVE_NAMES   # la séance (worktree) peut les porter : le test vise sa liste factice
export PMZILLA_SKIP_GREEN_CHECK=1   # ce test vise le garde-fou des noms ; celui du lancement vert a son test (test_pre_commit_green.sh)
hook="$(cd "$(dirname "$0")/../../tools/hooks" && pwd)/pre-commit"
tmp=$(mktemp -d) || exit 1
trap 'rm -rf "$tmp"' EXIT
# Faux lab : $tmp est le dossier du lab, $repo le dépôt de développement (dossier de contenu, par la variable : jamais le vrai lab) ;
# le dossier d'exécution par défaut du module partagé est donc $tmp/run.
repo="$tmp/workspace"; mkdir -p "$repo"
export PMZILLA_LAB_WORKSPACE="$repo"; unset PMZILLA_LAB_RUN
cd "$repo" || exit 1
git init -q . && git config user.email t@example.org && git config user.name test
mkdir Flux-Lab
printf 'EquipeTest\nA&B\nABC\nZETA\n' > Flux-Lab/noms-sensibles.txt
ok=0; ko=0

verifie() { # description attendu(0=passe,1=bloque) [motif attendu dans la sortie]
  desc=$1; attendu=$2; motif=${3:-}
  sortie=$(python3 "$hook" 2>&1); code=$?
  if [ "$code" -ne "$attendu" ]; then echo "ECHEC : $desc (code $code, attendu $attendu)"; ko=$((ko+1)); return; fi
  if [ -n "$motif" ] && ! printf '%s' "$sortie" | grep -q "$motif"; then
    echo "ECHEC : $desc (sortie sans « $motif »)"; ko=$((ko+1)); return; fi
  if printf '%s' "$sortie" | grep -q -e 'EquipeTest' -e 'A&B' -e 'ABC' -e 'ZETA'; then
    echo "ECHEC : $desc (la sortie contient un nom)"; ko=$((ko+1)); return; fi
  echo "ok : $desc"; ok=$((ok+1))
}
indexe() { printf '%s\n' "$2" > "$1"; git add "$1"; }
vide() { git reset -q; rm -f f.md essai-hook.txt LISEZMOI; }

indexe f.md 'texte sans nom'                          ; verifie "fichier propre passe" 0; vide
indexe f.md "ligne 1
une EquipeTest ici"                                    ; verifie "nom simple bloque, ligne 2" 1 "f.md, ligne 2"; vide
indexe f.md 'equipetest en minuscules'                 ; verifie "casse ignorée" 1 "f.md, ligne 1"; vide
indexe f.md '(A&B) entre parenthèses'                  ; verifie "A&B entre parenthèses bloque" 1 "ligne 1"; vide
indexe f.md 'A&B'                                      ; verifie "A&B seul bloque" 1; vide
indexe f.md 'XA&B collé à une lettre'                  ; verifie "XA&B ne bloque pas" 0; vide
indexe f.md 'A&B2 collé à un chiffre'                  ; verifie "A&B2 ne bloque pas" 0; vide
indexe f.md 'le sigle ABC ici'                         ; verifie "sigle ABC bloque" 1 "f.md, ligne 1"; vide
indexe f.md 'le sigle abc en minuscules'               ; verifie "abc passe (nom de 3 caractères, casse respectée)" 0; vide
indexe f.md 'le sigle Abc'                             ; verifie "Abc passe" 0; vide
indexe f.md 'ZETA en majuscules'                       ; verifie "sigle ZETA bloque" 1; vide
indexe f.md 'zeta en minuscules'                       ; verifie "zeta passe (nom en majuscules, casse respectée)" 0; vide
indexe essai-hook.txt 'une EquipeTest dans un .txt'    ; verifie "fichier .txt examiné" 1 "essai-hook.txt, ligne 1"; vide
indexe essai-hook.txt 'ce test ne marche pas'          ; verifie ".txt propre passe" 0; vide
indexe essai-hook.txt 'le sigle ABC ici'               ; verifie ".txt : sigle ABC bloque" 1 "essai-hook.txt, ligne 1"; vide
indexe essai-hook.txt 'le sigle abc ici'               ; verifie ".txt : abc passe" 0; vide
indexe LISEZMOI 'le sigle ABC ici'                     ; verifie "sans extension : sigle ABC bloque" 1 "LISEZMOI, ligne 1"; vide
indexe LISEZMOI 'le sigle abc ici'                     ; verifie "sans extension : abc passe" 0; vide
printf 'EquipeTest\0binaire\n' > b.bin; git add b.bin ; verifie "binaire (octet nul) non examiné" 0; git reset -q; rm -f b.bin
python3 -c "open('gros.md','w').write('EquipeTest\n' + 'x' * 1100000)"; git add gros.md
verifie "fichier de plus de 1 Mo signalé sans blocage" 0 "gros.md dépasse 1 Mo"; git reset -q; rm -f gros.md
indexe f.md 'MonEquipeTestBis'                         ; verifie "nom au milieu d'un mot ne bloque pas" 0; vide
printf '# NomEnCommentaire\n   # AutreEnCommentaire\n' >> Flux-Lab/noms-sensibles.txt
indexe f.md '# NomEnCommentaire et    # AutreEnCommentaire'   ; verifie "ligne de la liste commençant par # ignorée (comme sensitive_names.py)" 0; vide
indexe f.md 'une EquipeTest'                           ; verifie "la liste reste active avec des commentaires" 1 "f.md, ligne 1"; vide

# Un commit réel est refusé par le hook installé, sans --no-verify
mkdir -p .git/hooks && ln -sf "$hook" .git/hooks/pre-commit   # lien, comme tools/install_hooks.sh : le hook importe tools/sensitive_names.py à côté de lui
indexe f.md 'une EquipeTest'
if git commit -q -m t >/dev/null 2>&1; then echo "ECHEC : git commit aurait dû être refusé"; ko=$((ko+1)); else echo "ok : git commit refusé par le hook"; ok=$((ok+1)); fi
vide
indexe f.md 'texte sans nom'
if git commit -q -m t >/dev/null 2>&1; then echo "ok : git commit propre accepté"; ok=$((ok+1)); else echo "ECHEC : commit propre refusé"; ko=$((ko+1)); fi

# Dossier d'exécution (change run-worktree, D6) : refus avant tout autre garde-fou, contournement du propriétaire compris ; aucun refus
# dans le dépôt principal ni dans un worktree de branche de travail. Le dossier d'exécution est PMZILLA_LAB_RUN, sinon le dossier run du dossier du lab (module partagé).
CLE="pre-commit : commit refusé dans le dossier d'exécution"
git branch -q -f base HEAD
git worktree add -q --detach "$tmp/run" HEAD
git worktree add -q -b travail-test "$tmp/wt" HEAD
verifie_dans() { # description attendu dossier motif [absent] : lance le hook dans le dossier donné, comme le fait git commit
  desc=$1; attendu=$2; dossier=$3; motif=$4; absent=${5:-}
  sortie=$(cd "$dossier" && python3 "$hook" 2>&1); code=$?
  if [ "$code" -ne "$attendu" ]; then echo "ECHEC : $desc (code $code, attendu $attendu) $sortie"; ko=$((ko+1)); return; fi
  if [ -n "$motif" ] && ! printf '%s' "$sortie" | grep -q -- "$motif"; then echo "ECHEC : $desc (sortie sans « $motif »)"; ko=$((ko+1)); return; fi
  if [ -n "$absent" ] && printf '%s' "$sortie" | grep -q -- "$absent"; then echo "ECHEC : $desc (sortie avec « $absent »)"; ko=$((ko+1)); return; fi
  echo "ok : $desc"; ok=$((ok+1))
}
empreinte() { (cd "$1" && git write-tree > "$(git rev-parse --git-path pmzilla-run-all-ok)"); }   # ce que fait run_all.sh
echo propre > "$tmp/run/r.md"; git -C "$tmp/run" add r.md
empreinte "$tmp/run"
export PMZILLA_LAB_RUN="$tmp/run"
export PMZILLA_NOMS="$repo/Flux-Lab/noms-sensibles.txt"   # les worktrees n'ont pas Flux-Lab/ (hors Git) : la liste du dépôt principal
unset PMZILLA_SKIP_GREEN_CHECK
verifie_dans "dossier d'exécution, empreinte complète valide : refusé" 1 "$tmp/run" "$CLE"
export PMZILLA_SKIP_GREEN_CHECK=1
verifie_dans "dossier d'exécution, contournement du propriétaire : refusé aussi" 1 "$tmp/run" "$CLE"
echo "une EquipeTest ici" > "$tmp/run/r.md"; git -C "$tmp/run" add r.md
verifie_dans "dossier d'exécution : refus avant le garde-fou des noms" 1 "$tmp/run" "$CLE" "nom sensible"
git -C "$tmp/run" reset -q; rm -f "$tmp/run/r.md"
echo propre > "$tmp/wt/w.md"; git -C "$tmp/wt" add w.md
verifie_dans "worktree de branche de travail : pas de refus du dossier d'exécution" 0 "$tmp/wt" "" "dossier d'exécution"
echo propre > "$repo/run-voisin.md"
verifie_dans "dépôt principal : pas de refus du dossier d'exécution" 0 "$repo" "" "dossier d'exécution"
# Sans PMZILLA_LAB_RUN : le dossier par défaut est le dossier run du dossier du lab (module partagé), ici $tmp/run
unset PMZILLA_LAB_RUN
verifie_dans "dossier par défaut (run du dossier du lab) refusé" 1 "$tmp/run" "$CLE"
# Un commit réel, hook installé : refusé dans le dossier d'exécution (sans --no-verify), accepté dans le worktree de travail
export PMZILLA_LAB_RUN="$tmp/run"
echo reel > "$tmp/run/c.md"; git -C "$tmp/run" add c.md
if git -C "$tmp/run" commit -q -m t >/dev/null 2>&1; then echo "ECHEC : git commit dans le dossier d'exécution aurait dû être refusé"; ko=$((ko+1)); else echo "ok : git commit refusé dans le dossier d'exécution"; ok=$((ok+1)); fi
if git -C "$tmp/wt" commit -q -m t >/dev/null 2>&1; then echo "ok : git commit accepté dans le worktree de travail"; ok=$((ok+1)); else echo "ECHEC : commit refusé dans le worktree de travail"; ko=$((ko+1)); fi
unset PMZILLA_LAB_RUN PMZILLA_NOMS
git -C "$tmp/run" reset -q; rm -f "$tmp/run/c.md" "$repo/run-voisin.md"

# Gel pendant une fin de branche (change multi-session-piloting, D7, tâche 5.4) : le verrou est un dossier du dossier Git commun, fait ici à la main.
# Refus avant tous les autres contrôles, contournement du propriétaire compris ; jeton égal ou verrou périmé : les autres contrôles tournent.
GEL="$repo/.git/pmzilla-fin-en-cours"
CLE_GEL="pre-commit : fin de branche en cours (feat/autre), commit refusé"
pose_verrou() { # pid jeton : verrou factice
  rm -rf "$GEL"; mkdir -p "$GEL"; printf '%s\n' "$1" > "$GEL/pid"; date +%s > "$GEL/debut"; printf 'feat/autre\n' > "$GEL/branche"; printf '%s\n' "$2" > "$GEL/jeton"
}
etat_verrou() { (cd "$GEL" && cat pid debut branche jeton 2>/dev/null); }
mort=$(sh -c 'echo $$')   # numéro d'un processus qui n'existe plus
unset FINISH_LOCK_TOKEN
export PMZILLA_SKIP_GREEN_CHECK=1
indexe f.md 'texte du gel un'
pose_verrou $$ jeton-de-test; avant=$(etat_verrou)
verifie_dans "gel : verrou vivant, aucun jeton, contournement du propriétaire posé : refusé" 1 "$repo" "$CLE_GEL"
unset PMZILLA_SKIP_GREEN_CHECK
verifie_dans "gel : verrou vivant, aucun jeton : refusé" 1 "$repo" "$CLE_GEL"
export FINISH_LOCK_TOKEN=un-autre-jeton PMZILLA_SKIP_GREEN_CHECK=1
verifie_dans "gel : verrou vivant, jeton différent : refusé" 1 "$repo" "$CLE_GEL"
export FINISH_LOCK_TOKEN=jeton-de-test
verifie_dans "gel : jeton égal à celui du verrou : les autres contrôles tournent" 0 "$repo" "" "fin de branche en cours"
indexe f.md 'une EquipeTest ici'
verifie_dans "gel : jeton égal, le garde-fou des noms s'applique toujours" 1 "$repo" "nom sensible dans f.md"
vide; indexe f.md 'texte du gel deux'
[ "$(etat_verrou)" = "$avant" ]; if [ $? -eq 0 ]; then echo "ok : gel : le hook n'a ni créé ni retiré ni changé le verrou"; ok=$((ok+1)); else echo "ECHEC : gel : le verrou a changé"; ko=$((ko+1)); fi
unset FINISH_LOCK_TOKEN
pose_verrou "$mort" jeton-de-test; avant=$(etat_verrou)
verifie_dans "gel : verrou périmé (processus mort) : les autres contrôles tournent" 0 "$repo" "verrou de fin périmé, ignoré" "commit refusé"
[ "$(etat_verrou)" = "$avant" ]; if [ $? -eq 0 ]; then echo "ok : gel : le verrou périmé est laissé en place"; ok=$((ok+1)); else echo "ECHEC : gel : verrou périmé modifié"; ko=$((ko+1)); fi
# Un commit réel, hook installé : refusé sous un verrou vivant (le sommet de la branche ne bouge pas), accepté avec le jeton
pose_verrou $$ jeton-de-test
tete=$(git -C "$repo" rev-parse HEAD)
if git commit -q -m t >/dev/null 2>&1; then echo "ECHEC : git commit aurait dû être refusé pendant une fin de branche"; ko=$((ko+1)); else echo "ok : gel : git commit refusé pendant une fin de branche"; ok=$((ok+1)); fi
[ "$(git -C "$repo" rev-parse HEAD)" = "$tete" ]; if [ $? -eq 0 ]; then echo "ok : gel : le sommet de la branche n'a pas bougé"; ok=$((ok+1)); else echo "ECHEC : gel : le sommet a bougé"; ko=$((ko+1)); fi
if FINISH_LOCK_TOKEN=jeton-de-test git commit -q -m t >/dev/null 2>&1; then echo "ok : gel : git commit accepté avec le jeton de la fin"; ok=$((ok+1)); else echo "ECHEC : gel : commit refusé malgré le jeton"; ko=$((ko+1)); fi
rm -rf "$GEL"; vide

# Extrait des noms d'équipes (change team-names-readable, D8, tâche 5.1) : les noms distinctifs de Flux-Lab/equipes-lisibles.yaml
# s'ajoutent à la liste ; le fichier et la ligne sont dits, jamais le nom ; un nom de mots courants n'est pas gardé ; sans extrait, rien ne change.
verifie_extrait() { # description attendu motif : la sortie ne contient jamais un nom de l'extrait
  desc=$1; attendu=$2; motif=${3:-}
  sortie=$(python3 "$hook" 2>&1); code=$?
  if [ "$code" -ne "$attendu" ]; then echo "ECHEC : $desc (code $code, attendu $attendu)"; ko=$((ko+1)); return; fi
  if [ -n "$motif" ] && ! printf '%s' "$sortie" | grep -q -- "$motif"; then echo "ECHEC : $desc (sortie sans « $motif »)"; ko=$((ko+1)); return; fi
  if printf '%s' "$sortie" | grep -q -i -e 'Quarkonaute' -e 'Platform Team'; then echo "ECHEC : $desc (la sortie contient un nom de l'extrait)"; ko=$((ko+1)); return; fi
  echo "ok : $desc"; ok=$((ok+1))
}
printf 'EquipeTest\n' > Flux-Lab/noms-sensibles.txt
printf 'extracted_on: %s\nreferential_teams:\n- name: Quarkonaute\n  jira_team_ids: []\n  without_identifier: true\n  type: null\ncatalogue_teams:\n- name: Platform Team\n  jira_team_ids: []\n  type: null\n  obsolete: false\n  outside_referential: true\n' "'2026-10-19'" > Flux-Lab/equipes-lisibles.yaml
indexe f.md "ligne 1
une Quarkonaute ici"                                   ; verifie_extrait "extrait : un nom distinctif de l'extrait bloque, fichier et ligne sans le nom" 1 "f.md, ligne 2"; vide
indexe f.md 'quarkonaute en minuscules'                ; verifie_extrait "extrait : casse ignorée" 1 "f.md, ligne 1"; vide
indexe f.md 'une Platform Team ici'                    ; verifie_extrait "extrait : un nom de mots courants ne bloque pas" 0; vide
indexe f.md 'MonQuarkonauteBis'                        ; verifie_extrait "extrait : nom au milieu d'un mot ne bloque pas" 0; vide
indexe f.md 'une EquipeTest ici'                       ; verifie_extrait "extrait : la liste garde ses noms" 1 "f.md, ligne 1"; vide
printf 'cette ligne: [pas du yaml\n' > Flux-Lab/equipes-lisibles.yaml
indexe f.md 'une Quarkonaute ici'                      ; verifie_extrait "extrait illisible : comportement inchangé (la liste seule)" 0; vide
rm -f Flux-Lab/equipes-lisibles.yaml
indexe f.md 'une Quarkonaute ici'                      ; verifie_extrait "sans extrait : comportement inchangé" 0; vide

# Sans liste, le hook échoue en le disant (R-47) ; liste vide : avertissement seulement
rm Flux-Lab/noms-sensibles.txt
indexe g.md 'texte sans nom'                           ; verifie "sans liste : le commit est refusé, en le disant" 1 "garde-fou des noms impossible : liste absente"; vide
# export puis unset : sous sh (mode POSIX), une affectation devant une fonction persisterait après l'appel
indexe g.md 'texte sans nom'; export PMZILLA_NOMS="$tmp/factice.txt"; verifie "chemin explicite vers une liste absente : refusé aussi" 1 "liste absente"; unset PMZILLA_NOMS; vide
: > Flux-Lab/noms-sensibles.txt; indexe g.md 'EquipeTest'      ; verifie "liste vide : avertissement, sans blocage" 0 "garde-fou des noms inactif : liste vide"
printf '# seulement des commentaires\n\n' > Flux-Lab/noms-sensibles.txt; indexe g.md 'EquipeTest' ; verifie "liste de commentaires seuls : traitée comme vide" 0 "garde-fou des noms inactif : liste vide"

# Réserve D8 : liste vide mais extrait non vide : les noms de l'extrait restent gardés (fichier et ligne, jamais le nom) ; sans extrait : inchangé
printf 'extracted_on: %s\nreferential_teams:\n- name: Quarkonaute\n  jira_team_ids: []\n  without_identifier: true\n  type: null\ncatalogue_teams: []\n' "'2026-10-19'" > Flux-Lab/equipes-lisibles.yaml
: > Flux-Lab/noms-sensibles.txt
indexe g.md "ligne 1
une Quarkonaute ici"           ; verifie_extrait "liste vide + extrait : le nom de l'extrait bloque, fichier et ligne sans le nom" 1 "g.md, ligne 2"; vide
indexe g.md 'texte sans nom'    ; verifie_extrait "liste vide + extrait : commit propre accepté" 0; vide
rm -f Flux-Lab/equipes-lisibles.yaml
indexe g.md 'une Quarkonaute ici' ; verifie_extrait "liste vide + sans extrait : inchangé, avertissement et passage" 0 "garde-fou des noms inactif : liste vide"; vide

# Avertissement sur une entrée qui est un mot courant (change names-and-team-review, D3) : jamais bloquant, jamais l'entrée imprimée
avertit() { # description attendu(0/1) lignes-attendues(séparées par des espaces, vide = aucune) interdit
  desc=$1; attendu=$2; lignes=$3; interdit=$4
  sortie=$(python3 "$hook" 2>&1); code=$?
  if [ "$code" -ne "$attendu" ]; then echo "ECHEC : $desc (code $code, attendu $attendu)"; ko=$((ko+1)); return; fi
  produites=$(printf '%s\n' "$sortie" | sed -n 's/^pre-commit : la ligne \([0-9]*\) de la liste des noms sensibles est un mot courant : la retirer ou la rendre plus distinctive$/\1/p' | tr '\n' ' ' | sed 's/ $//')
  if [ "$produites" != "$lignes" ]; then echo "ECHEC : $desc (lignes « $produites », attendues « $lignes »)"; ko=$((ko+1)); return; fi
  if printf '%s' "$sortie" | grep -q -e "$interdit" -e 'Platform' -e 'Delivery' -e 'Quality'; then
    echo "ECHEC : $desc (la sortie contient une entrée)"; ko=$((ko+1)); return; fi
  echo "ok : $desc"; ok=$((ok+1))
}
printf 'EquipeTest\n# commentaire\nPlatform\nZETA\nDelivery Quality\nabc\n' > Flux-Lab/noms-sensibles.txt
indexe g.md 'texte sans nom'      ; avertit "mots courants de la liste : une alerte par ligne, commit propre accepté" 0 "3 5" EquipeTest; vide
indexe g.md 'une EquipeTest ici'  ; avertit "mots courants de la liste : un commit refusé le reste" 1 "3 5" EquipeTest; vide
printf 'EquipeTest\nZETA\nabc\n' > Flux-Lab/noms-sensibles.txt
indexe g.md 'texte sans nom'      ; avertit "liste sans mot courant : aucune alerte" 0 "" EquipeTest; vide

# Garde-fou des secrets (change pre-commit-secret-scan, D2 à D9) : les valeurs sont fabriquées à l'exécution (aucune dans ce fichier) ;
# la sortie ne contient jamais la valeur ni son empreinte. Le contournement du propriétaire est posé : il ne lève pas ce refus.
unset CLAUDECODE
export PMZILLA_SKIP_GREEN_CHECK=1
corps="aB3dE5gH7jK9mN2pQ4rS6tU8vW1xY0zCAbCd"
jeton="gh""p_$corps"
empreinte=$(python3 -c 'import hashlib, sys; print(hashlib.sha256(sys.argv[1].encode()).hexdigest())' "$jeton")
FERMETURE="Commit refusé : retire ce secret du fichier (et révoque-le s'il est réel) ; aucune valeur n'est affichée."
verifie_secret() { # description attendu [motif] [autre motif] [hook] : motifs littéraux ; jamais la valeur ni l'empreinte dans la sortie
  desc=$1; attendu=$2; motif=${3:-}; autre=${4:-}; crochet=${5:-$hook}
  sortie=$(python3 "$crochet" 2>&1); code=$?
  if [ "$code" -ne "$attendu" ]; then echo "ECHEC : $desc (code $code, attendu $attendu)"; ko=$((ko+1)); return; fi
  if [ -n "$motif" ] && ! printf '%s' "$sortie" | grep -qF -- "$motif"; then echo "ECHEC : $desc (sortie sans « $motif »)"; ko=$((ko+1)); return; fi
  if [ -n "$autre" ] && ! printf '%s' "$sortie" | grep -qF -- "$autre"; then echo "ECHEC : $desc (sortie sans « $autre »)"; ko=$((ko+1)); return; fi
  if printf '%s' "$sortie" | grep -qF -e "$corps" -e "$empreinte"; then echo "ECHEC : $desc (la sortie contient la valeur ou son empreinte)"; ko=$((ko+1)); return; fi
  echo "ok : $desc"; ok=$((ok+1))
}
secret4() { printf 'ligne 1\nligne 2\nligne 3\njeton : %s\n' "$jeton" > "$1"; git add "$1"; }
vide_secrets() { git reset -q; rm -f f.md g.md gros.md b.bin; }
printf 'EquipeTest\n' > Flux-Lab/noms-sensibles.txt

secret4 f.md; verifie_secret "secrets : jeton indexé refusé (fichier, ligne 4, famille), contournement du propriétaire posé" 1 "pre-commit : secret possible dans f.md, ligne 4 (jeton GitHub)" "$FERMETURE"; vide_secrets
printf 'PMZILLA_LAB_DB''_PASSWORD=%s\n' "Zx9Qw2Er7" > f.md; git add f.md
verifie_secret "secrets : mot de passe du labo affecté d'un littéral refusé" 1 "pre-commit : secret possible dans f.md, ligne 1 (mot de passe du labo)"; vide_secrets
printf '%s\n' 'postgresql://role:${PGPASSWORD}@localhost/base' 'PMZILLA_LAB_DB''_PASSWORD="$MDP"' > f.md; git add f.md
verifie_secret "secrets : adresse et variable à espace réservé acceptées" 0; vide_secrets
indexe f.md 'texte propre'; verifie_secret "secrets : fichier propre accepté" 0; vide_secrets
python3 -c "import sys; open('gros.md','w').write('x' * 1100000 + '\n' + sys.argv[1] + '\n')" "$jeton"; git add gros.md
verifie_secret "secrets : fichier de plus de 1 Mo cherché quand même, l'avis des noms reste" 1 "pre-commit : secret possible dans gros.md, ligne 2 (jeton GitHub)" "gros.md dépasse 1 Mo, non examiné"; vide_secrets
printf '%s\0binaire\n' "$jeton" > b.bin; git add b.bin; verifie_secret "secrets : binaire (octet nul) ignoré" 0; vide_secrets
# un fichier renommé (git mv) qui reçoit un secret ou un nom est examiné (relecture 4.1 du 2026-10-20 : le filtre ACM laissait passer le R)
for i in 1 2 3 4 5 6 7 8 9 10; do echo "ligne de texte ordinaire $i"; done > r.md; git add r.md; git commit -q -m "fichier à renommer"
git mv r.md r2.md; echo "jeton : $jeton" >> r2.md; git add r2.md
verifie_secret "secrets : fichier renommé avec un secret ajouté : refusé" 1 "pre-commit : secret possible dans r2.md, ligne 11 (jeton GitHub)"; git reset -q --hard
git mv r.md r3.md; echo "une EquipeTest ici" >> r3.md; git add r3.md
verifie_secret "noms : fichier renommé avec un nom ajouté : refusé" 1 "nom sensible dans r3.md, ligne 11"; git reset -q --hard
: > Flux-Lab/noms-sensibles.txt
secret4 g.md; verifie_secret "secrets : liste des noms vide : avertissement et secret refusé quand même" 1 "garde-fou des noms inactif : liste vide" "pre-commit : secret possible dans g.md, ligne 4 (jeton GitHub)"; vide_secrets
rm -f Flux-Lab/noms-sensibles.txt
secret4 g.md; verifie_secret "secrets : liste des noms absente : les deux refus sont dits" 1 "pre-commit : secret possible dans g.md, ligne 4 (jeton GitHub)" "garde-fou des noms impossible : liste absente"
ordre=$(python3 "$hook" 2>&1 | grep -n -e "secret possible" -e "liste absente" | cut -d: -f1 | tr '\n' ' ')
case "$ordre" in "1 "*) echo "ok : secrets : les secrets sont dits avant la liste absente"; ok=$((ok+1)) ;; *) echo "ECHEC : secrets : ordre des refus ($ordre)"; ko=$((ko+1)) ;; esac
vide_secrets
printf 'EquipeTest\n' > Flux-Lab/noms-sensibles.txt
printf 'une EquipeTest ici\njeton : %s\n' "$jeton" > f.md; git add f.md
verifie_secret "secrets : un secret et un nom dans le même fichier : les deux refus" 1 "pre-commit : secret possible dans f.md, ligne 2 (jeton GitHub)" "nom sensible dans f.md, ligne 1"; vide_secrets

# Exemples déclarés (D6) : la liste est lue dans l'index ; chemin et empreinte acceptés, la même valeur ailleurs refusée
mkdir -p tools
printf '# exemples déclarés\nf.md %s  # exemple de format\n' "$empreinte" > tools/secret_scan_exemples.txt; git add tools/secret_scan_exemples.txt
secret4 f.md; verifie_secret "exemple déclaré : accepté, fichier et ligne dits" 0 "pre-commit : exemple déclaré accepté : f.md, ligne 4 (jeton GitHub)"
git reset -q f.md; rm -f f.md
secret4 g.md; verifie_secret "exemple déclaré : la même valeur dans un autre fichier refusée" 1 "pre-commit : secret possible dans g.md, ligne 4 (jeton GitHub)"
git reset -q g.md; rm -f g.md
export CLAUDECODE=1
indexe f.md 'texte propre'; verifie_secret "liste des exemples indexée depuis une session : refusée" 1 "pre-commit : liste des exemples déclarés modifiée depuis une session ; commit refusé"
unset CLAUDECODE
verifie_secret "liste des exemples indexée hors session : acceptée" 0
if git commit -q -m liste >/dev/null 2>&1; then echo "ok : liste des exemples commitée hors session"; ok=$((ok+1)); else echo "ECHEC : commit de la liste refusé hors session"; ko=$((ko+1)); fi
export CLAUDECODE=1
secret4 f.md; verifie_secret "exemple déclaré : accepté en session quand la liste n'est pas modifiée" 0 "exemple déclaré accepté : f.md, ligne 4"
unset CLAUDECODE
git reset -q f.md; rm -f f.md
printf 'ligne mal formée\n' > tools/secret_scan_exemples.txt; git add tools/secret_scan_exemples.txt
indexe f.md 'texte propre'; verifie_secret "liste des exemples mal formée : refus, le garde-fou échoue fermé" 1 "pre-commit : recherche de secrets impossible (ListeInvalide), commit refusé"
printf '# exemples déclarés\nf.md %s  # exemple de format\n' "$empreinte" > tools/secret_scan_exemples.txt; git add tools/secret_scan_exemples.txt; vide_secrets

# Module des secrets absent ou en échec (D5) : copie du hook et de ses modules dans un dossier du test ; refus, contournement posé
copie="$tmp/copie/tools"; mkdir -p "$copie/hooks"
outils="$(dirname "$(dirname "$hook")")"
cp "$hook" "$copie/hooks/pre-commit"; cp "$outils/finish_lock.py" "$outils/lab_paths.py" "$outils/sensitive_names.py" "$copie/"
indexe f.md 'texte propre'
verifie_secret "module des secrets absent : commit refusé" 1 "pre-commit : recherche de secrets impossible (ModuleNotFoundError), commit refusé" "" "$copie/hooks/pre-commit"
printf 'raise RuntimeError("module cassé")\n' > "$copie/secret_scan.py"
verifie_secret "module des secrets qui échoue à l'import : commit refusé, le texte de l'erreur jamais dit" 1 "recherche de secrets impossible (RuntimeError)" "" "$copie/hooks/pre-commit"
printf 'LISTE_EXEMPLES = "tools/secret_scan_exemples.txt"\nVARIABLE_CLAUDE_CODE = "CLAUDECODE"\nclass ListeInvalide(Exception):\n    pass\ndef parse_declared(texte):\n    return set()\ndef check(chemin, texte, declares):\n    raise ValueError("echec")\n' > "$copie/secret_scan.py"
indexe h.md 'texte propre et nouveau'   # un fichier indexé : la recherche est appelée
verifie_secret "module des secrets qui échoue pendant la recherche : commit refusé" 1 "recherche de secrets impossible (ValueError)" "" "$copie/hooks/pre-commit"
git reset -q; rm -f h.md; vide_secrets
# Un commit réel, hook installé : refusé pour un secret, sans --no-verify (g.md : la liste commitée ne déclare que f.md)
secret4 g.md
if git commit -q -m t >/dev/null 2>&1; then echo "ECHEC : git commit d'un secret aurait dû être refusé"; ko=$((ko+1)); else echo "ok : git commit d'un secret refusé par le hook"; ok=$((ok+1)); fi
vide_secrets

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
