#!/bin/sh
# Test du hook pre-push : dépôt Git temporaire avec un remote nu temporaire, lanceur factice (PRE_PUSH_RUNNER).
# Contrôle des noms dans les messages qui partent (fix/sorties-et-masquage, point 3) : liste et extrait des équipes fictifs (noms inventés,
# PMZILLA_LAB_SENSITIVE_NAMES), jamais la vraie liste.
# Lancement à la main : sh tests/hooks/test_pre_push.sh
set -u
unset PMZILLA_SKIP_GREEN_CHECK PRE_PUSH_RUNNER PMZILLA_NOMS
hook="$(cd "$(dirname "$0")/../../tools/hooks" && pwd)/pre-push"
tmp=$(mktemp -d) || exit 1
trap 'rm -rf "$tmp"' EXIT
NOM="Vexillonia"; EQUIPE="Quarkonaute Sud"
mkdir -p "$tmp/listes"
printf '# liste fictive\n%s\n' "$NOM" > "$tmp/listes/noms-sensibles.txt"
printf 'referential_teams:\n- name: %s\n  jira_team_ids: []\ncatalogue_teams: []\n' "$EQUIPE" > "$tmp/listes/equipes-lisibles.yaml"
export PMZILLA_LAB_SENSITIVE_NAMES="$tmp/listes/noms-sensibles.txt"
git init -q --bare "$tmp/distant.git"
git init -q -b main "$tmp/depot" && cd "$tmp/depot" || exit 1
git config user.email t@example.org && git config user.name test
git remote add origin "$tmp/distant.git"
ln -sf "$hook" .git/hooks/pre-push
ok=0; ko=0
verifie() { # description code-attendu ; reste : commande
  desc=$1; attendu=$2; shift 2
  sortie=$("$@" 2>&1); code=$?
  if [ "$code" -eq "$attendu" ]; then echo "ok : $desc"; ok=$((ok+1)); else echo "ECHEC : $desc (code $code, attendu $attendu) $sortie"; ko=$((ko+1)); fi
}
vert() { git rev-parse --git-path pmzilla-run-all-ok; }
cible() { git rev-parse --git-path pmzilla-run-targeted-ok; }
valide() { echo "$1" > f.md; git add f.md; git commit -q --no-verify -m "$1"; }   # le commit sans hook : le test porte sur pre-push
echo "echo ok > $tmp/lance" > "$tmp/vert.sh"
echo "echo rouge; exit 1" > "$tmp/rouge.sh"

valide un
git rev-parse 'HEAD^{tree}' > "$(vert)"
verifie "main : empreinte complète égale à l'arbre poussé, passe sans lancer de test" 0 env PRE_PUSH_RUNNER="sh $tmp/vert.sh" git push -q origin main
verifie "main : aucun lanceur n'a tourné" 1 test -e "$tmp/lance"

valide deux
verifie "main : arbre propre, HEAD poussé, lanceur factice vert : accepté" 0 env PRE_PUSH_RUNNER="sh $tmp/vert.sh" git push -q origin main
verifie "main : le lanceur a bien été lancé par le hook" 0 test -e "$tmp/lance"
rm -f "$tmp/lance"

valide trois
rm -f "$(vert)"
verifie "main : lanceur factice rouge : refusé" 1 env PRE_PUSH_RUNNER="sh $tmp/rouge.sh" git push -q origin main
env PRE_PUSH_RUNNER="sh $tmp/rouge.sh" git push -q origin main 2>&1 | grep -q "pre-push : main exige une exécution complète réussie de l'arbre poussé" && { echo "ok : message du refus"; ok=$((ok+1)); } || { echo "ECHEC : message du refus"; ko=$((ko+1)); }

git rev-parse 'HEAD^{tree}' > "$(cible)"
verifie "main : l'empreinte ciblée seule ne suffit pas (lanceur rouge)" 1 env PRE_PUSH_RUNNER="sh $tmp/rouge.sh" git push -q origin main

echo sale > f.md
verifie "main : arbre sale sans empreinte : refusé sans lancer le lanceur" 1 env PRE_PUSH_RUNNER="sh $tmp/vert.sh" git push -q origin main
verifie "main : le lanceur n'a pas tourné sur un arbre sale" 1 test -e "$tmp/lance"
git checkout -q -- f.md

git checkout -q -b travail
valide quatre
verifie "branche de travail : aucun contrôle" 0 env PRE_PUSH_RUNNER="sh $tmp/rouge.sh" git push -q origin travail
git checkout -q main
verifie "poussée de HEAD (travail) vers main sans être sur le commit : refusé" 1 env PRE_PUSH_RUNNER="sh $tmp/vert.sh" git push -q origin travail:main
verifie "contournement PMZILLA_SKIP_GREEN_CHECK=1 : accepté" 0 env PMZILLA_SKIP_GREEN_CHECK=1 PRE_PUSH_RUNNER="sh $tmp/rouge.sh" git push -q origin travail:main
verifie "suppression d'une branche distante : aucun contrôle" 0 env PRE_PUSH_RUNNER="sh $tmp/rouge.sh" git push -q origin :travail

# Référence poussée dont l'arbre est introuvable : refusée (entrée standard fabriquée, hook lancé directement)
inconnu=1234567890123456789012345678901234567890
sortie=$(printf 'refs/heads/main %s refs/heads/main %s\n' "$inconnu" 0000000000000000000000000000000000000000 | PRE_PUSH_RUNNER="sh $tmp/vert.sh" sh "$hook" origin x 2>&1); code=$?
if [ "$code" -eq 1 ]; then echo "ok : arbre introuvable : refusé"; ok=$((ok+1)); else echo "ECHEC : arbre introuvable : refusé (code $code)"; ko=$((ko+1)); fi
case "$sortie" in *"main exige une exécution complète réussie de l'arbre poussé"*) echo "ok : arbre introuvable : message du refus"; ok=$((ok+1));; *) echo "ECHEC : arbre introuvable : message du refus"; ko=$((ko+1));; esac
verifie "arbre introuvable : le lanceur n'a pas tourné" 1 test -e "$tmp/lance"

# --- light-spec-finish (D5) : l'empreinte allégée pmzilla-light-ok n'est acceptée qu'après revérification : arbre poussé, chemins sous openspec/
# seulement (premier parent), arbre du premier parent validé dans l'enregistrement pmzilla-main-validated (date, signature d'environnement de la question Q9 : tools/finish_env.sh --main-signature).
# Le lanceur factice rouge sert de preuve : un push accepté avec lui n'a lancé aucun test ; un push refusé n'a pas été accepté sur l'empreinte allégée.
rm -f "$(vert)" "$(cible)" "$tmp/lance"
commun=$(git rev-parse --path-format=absolute --git-common-dir)
registre="$commun/pmzilla-main-validated"
leger() { git rev-parse --git-path pmzilla-light-ok; }
distant_main() { git --git-dir="$tmp/distant.git" rev-parse main; }
revient() { git checkout -q -B main "$(distant_main)"; rm -f "$registre" "$(leger)" "$(vert)" "$tmp/lance"; }
compteur=0
signature() { bash "$(dirname "$hook")/../finish_env.sh" --main-signature; }   # signature d'environnement que le hook recalcule
scenario() { # date-de-la-ligne chemin-modifie [signature ; défaut : celle de l'environnement] : premier parent validé à cette date, puis un commit qui change le chemin
  compteur=$((compteur+1))
  printf '%s\tcomplet\t%s\t%s\n' "$(git rev-parse 'HEAD^{tree}')" "$1" "${3:-$(signature)}" > "$registre"
  mkdir -p "$(dirname "$2")"; echo "v$compteur" > "$2"; git add "$2"; git commit -q --no-verify -m "scenario $compteur"
  git rev-parse 'HEAD^{tree}' > "$(leger)"
  avant_registre=$(cat "$registre"); avant_leger=$(cat "$(leger)")
}
inchanges() { [ "$(cat "$registre")" = "$avant_registre" ] && [ "$(cat "$(leger)")" = "$avant_leger" ]; }
pousse() { env LIGHT_FINISH_TODAY=2026-01-15 PRE_PUSH_RUNNER="sh $1" git push -q origin main; }
revient

scenario 2026-01-15 openspec/specs/a/spec.md
verifie "allégé : empreinte égale, openspec/ seulement, premier parent validé : accepté sans lancer de test" 0 pousse "$tmp/rouge.sh"
verifie "allégé : le hook n'a écrit aucun des deux enregistrements" 0 inchanges
revient

scenario 2026-01-15 openspec/specs/b/spec.md
git rev-parse 'HEAD~1^{tree}' > "$(leger)"; avant_leger=$(cat "$(leger)")
verifie "allégé : empreinte d'un autre arbre : refusé (lanceur rouge)" 1 pousse "$tmp/rouge.sh"
verifie "allégé : empreinte d'un autre arbre : les enregistrements sont inchangés" 0 inchanges
verifie "allégé : empreinte d'un autre arbre : le lanceur vert est lancé par le hook puis accepté" 0 pousse "$tmp/vert.sh"
verifie "allégé : empreinte d'un autre arbre : le lanceur a tourné" 0 test -e "$tmp/lance"
revient

scenario 2026-01-15 openspec/specs/c/spec.md
rm -f "$registre"
verifie "allégé : premier parent non validé (aucun enregistrement) : refusé" 1 pousse "$tmp/rouge.sh"
revient
scenario 2026-01-15 openspec/specs/c2/spec.md
printf '%s\tcomplet\t2026-01-15\t%s\n' 1111111111111111111111111111111111111111 "$(signature)" > "$registre"
verifie "allégé : enregistrement sans l'arbre du premier parent : refusé" 1 pousse "$tmp/rouge.sh"
revient

scenario 2026-01-15 tools/hors.sh
verifie "allégé : le commit poussé change aussi un chemin hors de openspec/ : refusé" 1 pousse "$tmp/rouge.sh"
revient
compteur=$((compteur+1)); echo "v$compteur" > racine.txt; git add racine.txt; git commit -q --no-verify -m "racine"   # le premier parent diffère alors par openspec/ et un fichier racine
scenario 2026-01-15 openspec/specs/d/spec.md
verifie "allégé : un fichier racine dans le premier parent n'empêche rien (seul le commit poussé compte)" 0 pousse "$tmp/rouge.sh"
revient
scenario 2026-01-15 openspec/specs/e/spec.md
git rm -q --cached openspec/specs/e/spec.md; ln -sf ../x openspec/specs/e/spec.md; git add openspec/specs/e/spec.md; git commit -q --no-verify --amend -m "lien"
git rev-parse 'HEAD^{tree}' > "$(leger)"; avant_leger=$(cat "$(leger)")
verifie "allégé : lien symbolique sous openspec/ : refusé" 1 pousse "$tmp/rouge.sh"
revient

scenario 2026-01-09 openspec/specs/f/spec.md
verifie "allégé : premier parent validé il y a 6 jours : accepté sans lancer de test" 0 pousse "$tmp/rouge.sh"
revient
scenario 2026-01-08 openspec/specs/g/spec.md
verifie "allégé : premier parent validé il y a 7 jours (limite) : accepté sans lancer de test" 0 pousse "$tmp/rouge.sh"
revient
scenario 2026-01-07 openspec/specs/h/spec.md
verifie "allégé : premier parent validé il y a 8 jours : refusé (expiré)" 1 pousse "$tmp/rouge.sh"
verifie "allégé : premier parent expiré : le lanceur vert est lancé par le hook" 0 pousse "$tmp/vert.sh"
verifie "allégé : premier parent expiré : le lanceur a tourné" 0 test -e "$tmp/lance"
revient
# passage allégé forcé (risque des faux runners) : un premier parent validé par une ligne « allégé-forcé » n'ouvre pas le chemin allégé
scenario 2026-01-15 openspec/specs/i/spec.md
printf '%s\tallégé-forcé\t2026-01-15\t%s\n' "$(git rev-parse 'HEAD~1^{tree}')" "$(signature)" > "$registre"; avant_registre=$(cat "$registre")
verifie "allégé : premier parent validé par un passage forcé : refusé (lanceur rouge)" 1 pousse "$tmp/rouge.sh"
verifie "allégé : premier parent validé par un passage forcé : le lanceur vert est lancé par le hook" 0 pousse "$tmp/vert.sh"
verifie "allégé : premier parent validé par un passage forcé : le lanceur a tourné" 0 test -e "$tmp/lance"
revient
# signature d'environnement (Q9) : la ligne enregistrée avec un faux uv, le hook lancé avec un autre uv ou sans uv dans son PATH
sans_uv="$tmp/sans-uv"   # liens vers chaque exécutable du PATH réel sauf uv
mkdir -p "$sans_uv" "$tmp/uv-a" "$tmp/uv-b"
for d in $(printf '%s' "$PATH" | tr ':' ' '); do
  for f in "$d"/*; do
    b=${f##*/}
    [ "$b" != uv ] && [ -f "$f" ] && [ -x "$f" ] && [ ! -e "$sans_uv/$b" ] && ln -s "$f" "$sans_uv/$b"
  done
done
printf '#!/bin/sh\necho "uv 1.2.3"\n' > "$tmp/uv-a/uv"; printf '#!/bin/sh\necho "uv 1.2.4"\n' > "$tmp/uv-b/uv"; chmod +x "$tmp/uv-a/uv" "$tmp/uv-b/uv"
pousse_path() { env PATH="$1" LIGHT_FINISH_TODAY=2026-01-15 PRE_PUSH_RUNNER="sh $2" git push -q origin main; }
signature_uv() { PATH="$tmp/uv-a:$sans_uv" signature; }
scenario 2026-01-15 openspec/specs/i/spec.md "$(signature_uv)"
verifie "allégé : même signature (faux uv identique) : accepté sans lancer de test" 0 pousse_path "$tmp/uv-a:$sans_uv" "$tmp/rouge.sh"
revient
scenario 2026-01-15 openspec/specs/i2/spec.md "$(signature_uv)"
verifie "allégé : premier parent enregistré avec une autre signature : refusé" 1 pousse_path "$tmp/uv-b:$sans_uv" "$tmp/rouge.sh"
verifie "allégé : autre signature : le lanceur vert est lancé par le hook" 0 pousse_path "$tmp/uv-b:$sans_uv" "$tmp/vert.sh"
verifie "allégé : autre signature : le lanceur a tourné" 0 test -e "$tmp/lance"
revient
scenario 2026-01-15 openspec/specs/i3/spec.md "$(signature_uv)"
verifie "allégé : uv absent du PATH du hook : refusé" 1 pousse_path "$sans_uv" "$tmp/rouge.sh"
verifie "allégé : uv absent du PATH du hook : le lanceur vert est lancé par le hook" 0 pousse_path "$sans_uv" "$tmp/vert.sh"
verifie "allégé : uv absent du PATH du hook : le lanceur a tourné" 0 test -e "$tmp/lance"
revient
scenario 2026-01-15 openspec/specs/i4/spec.md inconnue
verifie "allégé : signature enregistrée « inconnue » : refusé" 1 pousse "$tmp/rouge.sh"
revient
scenario 2026-01-09 openspec/specs/i5/spec.md "$(signature_uv)"
verifie "allégé : même signature à 6 jours : accepté sans lancer de test" 0 pousse_path "$tmp/uv-a:$sans_uv" "$tmp/rouge.sh"
revient

# l'empreinte complète garde son sens, l'empreinte ciblée ne suffit toujours pas
scenario 2026-01-15 openspec/specs/j/spec.md
rm -f "$(leger)"; git rev-parse 'HEAD^{tree}' > "$(cible)"
verifie "sans empreinte allégée : l'empreinte ciblée ne suffit pas : refusé" 1 pousse "$tmp/rouge.sh"
rm -f "$(cible)"
revient

# --- noms sensibles dans les messages des commits qui partent (fix/sorties-et-masquage, point 3) : toute référence poussée, plage
# distant..local (ou tous les commits absents du distant pour une nouvelle référence) ; refus avec le compte et les SHA courts, jamais le nom ;
# fermé par défaut sans liste ; PMZILLA_SKIP_GREEN_CHECK ne lève pas ce refus.
contient() { case "$1" in *"$2"*) return 0;; *) return 1;; esac; }
git checkout -q -B noms "$(distant_main)"
valide "propre avant"
echo n > n.md; git add n.md; git commit -q --no-verify -m "ajoute la vue de $NOM"
touche=$(git rev-parse --short HEAD)
verifie "noms : branche de travail, nom dans un message qui part : refusé" 1 git push -q origin noms
refus=$(git push -q origin noms 2>&1)   # pas « sortie » : verifie() l'écrase
contient "$refus" "$touche"; verifie "noms : le SHA court du commit touché est donné" 0 test $? -eq 0
contient "$refus" "2 commit(s) lu(s), 1 dont le message contient un nom"; verifie "noms : le compte est donné" 0 test $? -eq 0
contient "$refus" "pre-push : push refusé"; verifie "noms : le refus est dit" 0 test $? -eq 0
contient "$refus" "$NOM"; verifie "noms : le nom n'est jamais imprimé" 1 test $? -eq 0
contient "$refus" "ajoute la vue"; verifie "noms : le message n'est jamais imprimé" 1 test $? -eq 0
verifie "noms : PMZILLA_SKIP_GREEN_CHECK=1 ne lève pas le refus des noms" 1 env PMZILLA_SKIP_GREEN_CHECK=1 git push -q origin noms
git tag t-noms
verifie "noms : étiquette sur un commit touché absent du distant : refusée" 1 git push -q origin refs/tags/t-noms
git tag -d t-noms >/dev/null
git push -q --no-verify origin noms   # le commit touché arrive sur le distant sans crochet : il n'est plus « qui part »
valide "suite propre"
verifie "noms : commit touché déjà sur le distant, pas recompté : accepté" 0 git push -q origin noms
git checkout -q -b noms2
verifie "noms : nouvelle branche sans commit absent du distant : acceptée" 0 git push -q origin noms2
echo e > e.md; git add e.md; git commit -q --no-verify -m "revue de l'équipe $EQUIPE"
verifie "noms : nom de l'extrait des équipes dans un message qui part : refusé" 1 git push -q origin noms2
refus=$(git push -q origin noms2 2>&1)
contient "$refus" "$touche"; verifie "noms : le commit déjà sur le distant n'est pas recompté" 1 test $? -eq 0
contient "$refus" "1 commit(s) lu(s), 1 dont"; verifie "noms : seul le commit qui part est lu" 0 test $? -eq 0
contient "$refus" "Quarkonaute"; verifie "noms : le nom de l'extrait n'est jamais imprimé" 1 test $? -eq 0
git reset -q --hard HEAD~1
git checkout -q -b noms3
echo m > m.md; git add m.md; git commit -q --no-verify -m "mot collé ${NOM}x seulement"
verifie "noms : nom collé à une lettre, pas un nom entier : nouvelle branche acceptée" 0 git push -q origin noms3
mv "$tmp/listes/noms-sensibles.txt" "$tmp/listes/absente.txt"
valide "neutre sans liste"
verifie "noms : liste absente : refusé (fermé par défaut)" 1 git push -q origin noms3
refus=$(git push -q origin noms3 2>&1)
contient "$refus" "liste des noms sensibles absente"; verifie "noms : liste absente : le refus le dit" 0 test $? -eq 0
verifie "noms : suppression d'une branche distante, rien ne part : aucun contrôle" 0 git push -q origin :noms2
mv "$tmp/listes/absente.txt" "$tmp/listes/noms-sensibles.txt"
verifie "noms : liste revenue : accepté" 0 git push -q origin noms3
# revue Opus, point 1 : le message d'une étiquette annotée part aussi (git log pèle jusqu'au commit, qui est propre)
git tag -a t-annotee -m "version de $NOM"
verifie "noms : étiquette annotée dont le message porte un nom : refusée" 1 git push -q origin refs/tags/t-annotee
refus=$(git push -q origin refs/tags/t-annotee 2>&1)
contient "$refus" "étiquette annotée"; verifie "noms : étiquette annotée : le refus le dit" 0 test $? -eq 0
contient "$refus" "$NOM"; verifie "noms : étiquette annotée : le nom n'est jamais imprimé" 1 test $? -eq 0
git tag -d t-annotee >/dev/null
git tag -a t-propre -m "version propre"
verifie "noms : étiquette annotée propre : acceptée" 0 git push -q origin refs/tags/t-propre
# revue Opus, point 5 : distant donné par adresse (aucune référence de suivi) : le sommet distant connu est exclu, et le hook le dit
valide "par adresse"
refus=$(git push -q "$tmp/distant.git" noms3 2>&1); code_adresse=$?
verifie "noms : distant par adresse, branche existante : seule la plage distant..local est lue, accepté" 0 test "$code_adresse" -eq 0
contient "$refus" "distant donné par adresse"; verifie "noms : distant par adresse : le hook le dit" 0 test $? -eq 0
git checkout -q -b noms4
valide "nouvelle par adresse"
verifie "noms : distant par adresse, nouvelle branche : tout l'historique est relu, l'ancien commit touché refuse" 1 git push -q "$tmp/distant.git" noms4
# revue Opus, point 7 : plusieurs références dans un seul push, l'entrée du crochet n'est pas avalée par l'outil (la seconde est contrôlée)
git checkout -q -b noms5 noms3
echo p > p.md; git add p.md; git commit -q --no-verify -m "propre cinq"
git checkout -q -b noms6
echo q > q.md; git add q.md; git commit -q --no-verify -m "six cite $NOM"
verifie "noms : deux références poussées ensemble, la seconde touchée : refusé" 1 git push -q origin noms5 noms6
git checkout -q main

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
