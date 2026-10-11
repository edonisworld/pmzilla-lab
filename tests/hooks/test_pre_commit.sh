#!/bin/sh
# Test du hook pre-commit : dépôt Git temporaire, liste factice, aucun appel à Claude.
# Lancement à la main : sh tests/hooks/test_pre_commit.sh
set -u
export PMZILLA_SKIP_GREEN_CHECK=1   # ce test vise le garde-fou des noms ; celui du lancement vert a son test (test_pre_commit_green.sh)
hook="$(cd "$(dirname "$0")/../../tools/hooks" && pwd)/pre-commit"
tmp=$(mktemp -d) || exit 1
trap 'rm -rf "$tmp"' EXIT
cd "$tmp" || exit 1
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

# Sans liste, le hook échoue en le disant (R-47) ; liste vide : avertissement seulement
rm Flux-Lab/noms-sensibles.txt
indexe g.md 'texte sans nom'                           ; verifie "sans liste : le commit est refusé, en le disant" 1 "garde-fou des noms impossible : liste absente"; vide
# export puis unset : sous sh (mode POSIX), une affectation devant une fonction persisterait après l'appel
indexe g.md 'texte sans nom'; export PMZILLA_NOMS="$tmp/factice.txt"; verifie "chemin explicite vers une liste absente : refusé aussi" 1 "liste absente"; unset PMZILLA_NOMS; vide
: > Flux-Lab/noms-sensibles.txt; indexe g.md 'EquipeTest'      ; verifie "liste vide : avertissement, sans blocage" 0 "garde-fou des noms inactif : liste vide"
printf '# seulement des commentaires\n\n' > Flux-Lab/noms-sensibles.txt; indexe g.md 'EquipeTest' ; verifie "liste de commentaires seuls : traitée comme vide" 0 "garde-fou des noms inactif : liste vide"

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
