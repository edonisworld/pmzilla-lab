#!/bin/sh
# Test du hook commit-msg : dépôt temporaire, identifiant fictif dans .pmzilla/identifiants.txt, copie du vrai scanner ;
# noms sensibles fictifs (liste et extrait des équipes inventés, PMZILLA_LAB_SENSITIVE_NAMES), copie de tools/commit_names_scan.py.
# Aucune donnée réelle, aucun appel réseau. Lancement à la main : sh tests/hooks/test_commit_msg.sh
set -u
tools="$(cd "$(dirname "$0")/../../tools" && pwd)"
tmp=$(mktemp -d) || exit 1
tmp=$(cd "$tmp" && pwd -P)
trap 'rm -rf "$tmp"' EXIT
export HOME="$tmp/home"; mkdir -p "$HOME"
ID="zorglub-test"
NOM="Vexillonia"; EQUIPE="Quarkonaute Sud"   # noms inventés : liste des noms sensibles, extrait des équipes
mkdir -p "$tmp/listes"
printf '# liste fictive\n%s\n' "$NOM" > "$tmp/listes/noms-sensibles.txt"
printf 'referential_teams:\n- name: %s\n  jira_team_ids: []\ncatalogue_teams: []\n' "$EQUIPE" > "$tmp/listes/equipes-lisibles.yaml"
unset PMZILLA_NOMS
export PMZILLA_LAB_SENSITIVE_NAMES="$tmp/listes/noms-sensibles.txt"
depot="$tmp/depot"; mkdir -p "$depot/tools/hooks" "$depot/.pmzilla"
cp "$tools/identifiants_personnels.py" "$tools/lab_paths.py" "$depot/tools/"   # le scanner importe le module partagé (R-77)
cp "$tools/commit_names_scan.py" "$tools/sensitive_names.py" "$depot/tools/"   # contrôle des noms (fix/sorties-et-masquage, point 3)
cp "$tools/hooks/commit-msg" "$depot/tools/hooks/" || exit 1
echo "$ID" > "$depot/.pmzilla/identifiants.txt"
cd "$depot" || exit 1
git init -q . && git config user.email t@example.org && git config user.name test
mkdir -p .git/hooks && ln -sf ../../tools/hooks/commit-msg .git/hooks/commit-msg
ok=0; ko=0
verifie() { # description  condition(0=vrai)
  if [ "$2" -eq 0 ]; then echo "ok : $1"; ok=$((ok+1)); else echo "ECHEC : $1"; ko=$((ko+1)); fi
}
echo a > f; git add f

git commit -q -m "ajoute f, chemin /Users/$ID/travail" > "$tmp/sortie" 2>&1; code=$?
verifie "message avec identifiant : commit refusé" "$([ $code -ne 0 ] && echo 0 || echo 1)"
verifie "message avec identifiant : ni l'identifiant ni le texte dans la sortie" "$(grep -qi -e "$ID" -e "ajoute f" "$tmp/sortie" && echo 1 || echo 0)"
verifie "message avec identifiant : le refus est dit" "$(grep -qi 'identifiant' "$tmp/sortie" && echo 0 || echo 1)"
verifie "aucun commit créé" "$(git rev-parse -q --verify HEAD >/dev/null 2>&1 && echo 1 || echo 0)"

git commit -q -m "ajoute f" > "$tmp/sortie" 2>&1; code=$?
verifie "message propre : commit réussi" "$code"

echo b > g; git add g
# revue Opus, points 3 et 4 : une ligne « # » compte (elle peut rester dans le commit : -m "# …", --cleanup=verbatim) ; ce qui suit la
# ligne de ciseaux (diff de git commit -v, jamais commité) ne compte pas
printf 'ok\n\n# commentaire git avec /Users/%s\n' "$ID" > "$tmp/msg"
git commit -q -F "$tmp/msg" --cleanup=verbatim > "$tmp/sortie" 2>&1; code=$?
verifie "identifiant sur une ligne « # » : commit refusé" "$([ $code -ne 0 ] && echo 0 || echo 1)"
printf 'ok\n# ------------------------ >8 ------------------------\n-ancien chemin /Users/%s\n' "$ID" > "$tmp/msg"
git commit -q -F "$tmp/msg" --cleanup=scissors > "$tmp/sortie" 2>&1; code=$?
verifie "identifiant sous la ligne de ciseaux : ne compte pas" "$code"

# --- noms sensibles (fix/sorties-et-masquage, point 3) : liste et extrait des équipes, mêmes règles que pre-commit, fermé par défaut
echo n1 > n1; git add n1
printf 'titre neutre\n\ncorps qui cite %s ici\n' "$NOM" > "$tmp/msg"
git commit -q -F "$tmp/msg" > "$tmp/sortie" 2>&1; code=$?
verifie "nom de la liste dans le message : commit refusé" "$([ $code -ne 0 ] && echo 0 || echo 1)"
verifie "nom de la liste : la ligne du message est donnée" "$(grep -q 'ligne 3' "$tmp/sortie" && echo 0 || echo 1)"
verifie "nom de la liste : ni le nom ni le texte dans la sortie" "$(grep -qi -e "$NOM" -e "corps qui cite" "$tmp/sortie" && echo 1 || echo 0)"
verifie "nom de la liste : le refus est dit" "$(grep -q 'nom sensible' "$tmp/sortie" && echo 0 || echo 1)"
git commit -q -m "revue de l'équipe $EQUIPE" > "$tmp/sortie" 2>&1; code=$?
verifie "nom de l'extrait des équipes : commit refusé" "$([ $code -ne 0 ] && echo 0 || echo 1)"
verifie "nom de l'extrait : ni le nom ni le texte dans la sortie" "$(grep -qi -e "Quarkonaute" -e "revue de" "$tmp/sortie" && echo 1 || echo 0)"
git commit -q -m "mot collé ${NOM}x seulement" > "$tmp/sortie" 2>&1; code=$?
verifie "nom collé à une lettre : pas un nom entier, commit réussi" "$code"
echo n2 > n2; git add n2
printf 'ok\n\n# commentaire git avec %s\n' "$NOM" > "$tmp/msg"
git commit -q -F "$tmp/msg" --cleanup=verbatim > "$tmp/sortie" 2>&1; code=$?
verifie "nom sur une ligne « # » : commit refusé" "$([ $code -ne 0 ] && echo 0 || echo 1)"
git commit -q -m "# $NOM" > "$tmp/sortie" 2>&1; code=$?
verifie "git commit -m \"# nom\" : commit refusé" "$([ $code -ne 0 ] && echo 0 || echo 1)"
printf 'retire un nom\n# ------------------------ >8 ------------------------\n-ancienne ligne %s\n' "$NOM" > "$tmp/msg"
git commit -q -F "$tmp/msg" --cleanup=scissors > "$tmp/sortie" 2>&1; code=$?
verifie "nom sous la ligne de ciseaux (diff de git commit -v) : ne compte pas" "$code"
echo n2b > n2b; git add n2b
echo n3 > n3; git add n3
git commit -q -m "ajoute n3, chemin /Users/$ID/x et $NOM" > "$tmp/sortie" 2>&1; code=$?
verifie "identifiant et nom : commit refusé, les deux refus sont dits" "$([ $code -ne 0 ] && grep -q 'identifiant' "$tmp/sortie" && grep -q 'nom sensible' "$tmp/sortie" && echo 0 || echo 1)"
mv "$tmp/listes/noms-sensibles.txt" "$tmp/listes/absente.txt"
git commit -q -m "message neutre" > "$tmp/sortie" 2>&1; code=$?
verifie "liste des noms absente : commit refusé (fermé par défaut)" "$([ $code -ne 0 ] && echo 0 || echo 1)"
verifie "liste des noms absente : le refus le dit" "$(grep -q 'liste des noms sensibles absente' "$tmp/sortie" && echo 0 || echo 1)"
mv "$tmp/listes/absente.txt" "$tmp/listes/noms-sensibles.txt"
git commit -q -m "message neutre" > "$tmp/sortie" 2>&1; code=$?
verifie "liste revenue, message neutre : commit réussi" "$code"
# revue Opus, point 2 : le module des noms en échec (sa trace pourrait citer une ligne) : refus, seule une ligne de l'outil est montrée
echo n4 > n4; git add n4
printf 'raise ValueError("%s")\n' "$NOM" > tools/sensitive_names.py
git commit -q -m "message neutre" > "$tmp/sortie" 2>&1; code=$?
verifie "module des noms en échec : commit refusé" "$([ $code -ne 0 ] && echo 0 || echo 1)"
verifie "module des noms en échec : ni le nom ni une trace dans la sortie" "$(grep -qi -e "$NOM" -e "Traceback" "$tmp/sortie" && echo 1 || echo 0)"
cp "$tools/sensitive_names.py" tools/sensitive_names.py

echo c > h; git add h
printf '%s\n' 'raise SystemExit(2)' > tools/identifiants_personnels.py
git commit -q -m "autre" > "$tmp/sortie" 2>&1; code=$?
verifie "scanner en erreur : commit refusé" "$([ $code -ne 0 ] && echo 0 || echo 1)"
verifie "scanner en erreur : dit que le message n'a pas pu être vérifié" "$(grep -qi 'pas pu être vérifié' "$tmp/sortie" && echo 0 || echo 1)"

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
