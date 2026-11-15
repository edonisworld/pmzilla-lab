#!/bin/sh
# Test du hook pre-push : dépôt Git temporaire avec un remote nu temporaire, lanceur factice (PRE_PUSH_RUNNER).
# Contrôle des noms dans les messages qui partent (fix/sorties-et-masquage, point 3) : liste et extrait des équipes fictifs (noms inventés,
# PMZILLA_LAB_SENSITIVE_NAMES), jamais la vraie liste.
# Lancement à la main : sh tests/hooks/test_pre_push.sh
set -u
unset PMZILLA_SKIP_GREEN_CHECK PRE_PUSH_RUNNER PMZILLA_NOMS
unset CLAUDECODE   # le marqueur de session n'est pas hérité : la suite passe aussi bien dans une session qu'au Terminal ; les cas de session le posent eux-mêmes
hook="$(cd "$(dirname "$0")/../../tools/hooks" && pwd)/pre-push"
tmp=$(mktemp -d) || exit 1
trap 'rm -rf "$tmp"' EXIT
NOM="Vexillonia"; EQUIPE="Quarkonaute Sud"
mkdir -p "$tmp/listes"
printf '# liste fictive\n%s\n' "$NOM" > "$tmp/listes/noms-sensibles.txt"
printf 'referential_teams:\n- name: %s\n  jira_team_ids: []\ncatalogue_teams: []\n' "$EQUIPE" > "$tmp/listes/equipes-lisibles.yaml"
export PMZILLA_LAB_SENSITIVE_NAMES="$tmp/listes/noms-sensibles.txt"
# dossier de données fictif et vide pour TOUS les cas (revue Opus point 10) : le hook lit ci/preuves de PMZILLA_LAB_DATA (preuve du conteneur) ; sans cette
# ligne, les premiers cas liraient le vrai ~/.pmzilla-lab/ci/preuves de l'auteur et un arbre déjà prouvé là fausserait les refus attendus
export PMZILLA_LAB_DATA="$tmp/donnees-fictives"; mkdir -p "$PMZILLA_LAB_DATA/ci"
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

# R-20261102-37 (Q314) : le repli ignore les non suivis sous _bmad-output/, refuse tout le reste
mkdir -p _bmad-output/pmzilla; echo livrable > "_bmad-output/pmzilla/livrable avec espace.md"
verifie "main : un non suivi sous _bmad-output/ n'empêche pas le repli : accepté" 0 env PRE_PUSH_RUNNER="sh $tmp/vert.sh" git push -q origin main
verifie "main : un non suivi sous _bmad-output/ : le lanceur a tourné" 0 test -e "$tmp/lance"
rm -f "$tmp/lance"
rm -rf _bmad-output
valide cinq
mkdir -p _bmad-output/pmzilla; echo livrable > _bmad-output/pmzilla/suivi.md; git add _bmad-output/pmzilla/suivi.md
verifie "main : un fichier indexé sous _bmad-output/ : refusé" 1 env PRE_PUSH_RUNNER="sh $tmp/vert.sh" git push -q origin main
git reset -q; rm -rf _bmad-output
echo autre > hors-bmad.txt
verifie "main : un non suivi hors _bmad-output/ : refusé sans lancer le lanceur" 1 env PRE_PUSH_RUNNER="sh $tmp/vert.sh" git push -q origin main
verifie "main : le lanceur n'a pas tourné (non suivi hors _bmad-output/)" 1 test -e "$tmp/lance"
rm -f hors-bmad.txt

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

# --- finish-single-b7-b9 (B9, D8, D10 ; décision de l'auteur R-20261105-32 Q1) : la voie allégée est retirée du hook. L'empreinte allégée pmzilla-light-ok n'est plus
# lue : chaque scénario de l'ancienne acceptation (arbre, openspec/ seulement, premier parent validé dans pmzilla-main-validated avec la signature d'environnement
# de tools/finish_env.sh --main-signature, date, signature) est RÉÉCRIT pour affirmer le refus avec la phrase existante, aucun n'est supprimé. Le lanceur factice
# rouge sert de preuve : le hook retombe sur son propre lancement complet, qui échoue ; le lanceur vert est lancé par le hook puis accepté (voie du lancement
# complet du hook, inchangée). Remplace : les tests d'acceptation de l'empreinte allégée ; retrait : permanent.
rm -f "$(vert)" "$(cible)" "$tmp/lance"
commun=$(git rev-parse --path-format=absolute --git-common-dir)
registre="$commun/pmzilla-main-validated"
leger() { git rev-parse --git-path pmzilla-light-ok; }
distant_main() { git --git-dir="$tmp/distant.git" rev-parse main; }
revient() { git checkout -q -B main "$(distant_main)"; rm -f "$registre" "$(leger)" "$(vert)" "$(cible)" "$tmp/lance"; }
compteur=0
signature() { bash "$(dirname "$hook")/../finish_env.sh" --main-signature; }   # signature d'environnement que l'ancien hook recalculait
scenario() { # date-de-la-ligne chemin-modifie [signature ; défaut : celle de l'environnement] : premier parent validé à cette date, puis un commit qui change le chemin
  compteur=$((compteur+1))
  printf '%s\tcomplet\t%s\t%s\n' "$(git rev-parse 'HEAD^{tree}')" "$1" "${3:-$(signature)}" > "$registre"
  mkdir -p "$(dirname "$2")"; echo "v$compteur" > "$2"; git add "$2"; git commit -q --no-verify -m "scenario $compteur"
  git rev-parse 'HEAD^{tree}' > "$(leger)"
  avant_registre=$(cat "$registre"); avant_leger=$(cat "$(leger)")
}
inchanges() { [ "$(cat "$registre")" = "$avant_registre" ] && [ "$(cat "$(leger)")" = "$avant_leger" ]; }
pousse() { env LIGHT_FINISH_TODAY=2026-01-15 PRE_PUSH_RUNNER="sh $1" git push -q origin main; }
phrase_refus() { sortie_p=$(pousse "$1" 2>&1); case "$sortie_p" in *"pre-push : main exige une exécution complète réussie de l'arbre poussé"*) return 0;; *) return 1;; esac; }
refuse_avec_phrase() { # description : refus (lanceur rouge) et phrase existante du refus
  verifie "$1 : refusé (lanceur rouge)" 1 pousse "$tmp/rouge.sh"
  verifie "$1 : la phrase existante du refus" 0 phrase_refus "$tmp/rouge.sh"
}
revient

scenario 2026-01-15 openspec/specs/a/spec.md
refuse_avec_phrase "allégé : empreinte égale, openspec/ seulement, premier parent validé (acceptée avant B9)"
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
refuse_avec_phrase "allégé : premier parent non validé (aucun enregistrement)"
revient
scenario 2026-01-15 openspec/specs/c2/spec.md
printf '%s\tcomplet\t2026-01-15\t%s\n' 1111111111111111111111111111111111111111 "$(signature)" > "$registre"
refuse_avec_phrase "allégé : enregistrement sans l'arbre du premier parent"
revient

scenario 2026-01-15 tools/hors.sh
refuse_avec_phrase "allégé : le commit poussé change aussi un chemin hors de openspec/"
revient
compteur=$((compteur+1)); echo "v$compteur" > racine.txt; git add racine.txt; git commit -q --no-verify -m "racine"   # le premier parent diffère alors par openspec/ et un fichier racine
scenario 2026-01-15 openspec/specs/d/spec.md
refuse_avec_phrase "allégé : un fichier racine dans le premier parent (acceptée avant B9, seul le commit poussé comptait)"
revient
scenario 2026-01-15 openspec/specs/e/spec.md
git rm -q --cached openspec/specs/e/spec.md; ln -sf ../x openspec/specs/e/spec.md; git add openspec/specs/e/spec.md; git commit -q --no-verify --amend -m "lien"
git rev-parse 'HEAD^{tree}' > "$(leger)"; avant_leger=$(cat "$(leger)")
refuse_avec_phrase "allégé : lien symbolique sous openspec/"
revient

scenario 2026-01-09 openspec/specs/f/spec.md
refuse_avec_phrase "allégé : premier parent validé il y a 6 jours (acceptée avant B9)"
revient
scenario 2026-01-08 openspec/specs/g/spec.md
refuse_avec_phrase "allégé : premier parent validé il y a 7 jours, limite (acceptée avant B9)"
revient
scenario 2026-01-07 openspec/specs/h/spec.md
refuse_avec_phrase "allégé : premier parent validé il y a 8 jours (expiré)"
verifie "allégé : premier parent expiré : le lanceur vert est lancé par le hook" 0 pousse "$tmp/vert.sh"
verifie "allégé : premier parent expiré : le lanceur a tourné" 0 test -e "$tmp/lance"
revient
# passage allégé forcé (risque des faux runners) : une ligne « allégé-forcé » n'ouvrait pas le chemin allégé ; il n'existe plus
scenario 2026-01-15 openspec/specs/i/spec.md
printf '%s\tallégé-forcé\t2026-01-15\t%s\n' "$(git rev-parse 'HEAD~1^{tree}')" "$(signature)" > "$registre"; avant_registre=$(cat "$registre")
refuse_avec_phrase "allégé : premier parent validé par un passage forcé"
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
phrase_refus_path() { sortie_p=$(pousse_path "$1" "$2" 2>&1); case "$sortie_p" in *"pre-push : main exige une exécution complète réussie de l'arbre poussé"*) return 0;; *) return 1;; esac; }
signature_uv() { PATH="$tmp/uv-a:$sans_uv" signature; }
scenario 2026-01-15 openspec/specs/i/spec.md "$(signature_uv)"
verifie "allégé : même signature (faux uv identique) : refusé (acceptée avant B9)" 1 pousse_path "$tmp/uv-a:$sans_uv" "$tmp/rouge.sh"
verifie "allégé : même signature (faux uv identique) : la phrase existante du refus" 0 phrase_refus_path "$tmp/uv-a:$sans_uv" "$tmp/rouge.sh"
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
refuse_avec_phrase "allégé : signature enregistrée « inconnue »"
revient
scenario 2026-01-09 openspec/specs/i5/spec.md "$(signature_uv)"
verifie "allégé : même signature à 6 jours : refusé (acceptée avant B9)" 1 pousse_path "$tmp/uv-a:$sans_uv" "$tmp/rouge.sh"
verifie "allégé : même signature à 6 jours : la phrase existante du refus" 0 phrase_refus_path "$tmp/uv-a:$sans_uv" "$tmp/rouge.sh"
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

# --- ci-local-runner (D8, Q217) : la preuve du conteneur. ci/preuves (dossier de données fictif, PMZILLA_LAB_DATA) avec les trois phases ET une ligne de
# l'arbre dans pmzilla-run-mac-ok du dossier Git commun : accepté sans lancer de test. `ciblee` jamais ; deux phases ou pas de ligne Mac : refusé ;
# fichier illisible (appel sans preuve) : refusé. Le lanceur factice rouge prouve qu'un push accepté n'a rien lancé. Jamais le vrai dossier de données.
verifie "conteneur : le hook testé a tools/preuve_arbre.py à côté de lui (sinon la voie du conteneur ne peut pas réussir)" 0 test -f "$(dirname "$hook")/../preuve_arbre.py"
donnees="$tmp/donnees"; mkdir -p "$donnees/ci"
mac_ok="$commun/pmzilla-run-mac-ok"
revient
valide conteneur
arbre_c=$(git rev-parse 'HEAD^{tree}')
# lanceur rouge de ce bloc qui laisse un témoin quand il tourne : l'assertion finale « n'a pas tourné » porte alors (le rouge.sh commun n'écrit rien)
echo "echo lance > $tmp/lance-c; echo rouge; exit 1" > "$tmp/rouge-c.sh"
pousse_c() { env PMZILLA_LAB_DATA="$donnees" PRE_PUSH_RUNNER="sh $tmp/rouge-c.sh" git push -q origin main; }
rm -f "$donnees/ci/preuves" "$mac_ok"
printf '%s\tcle\tportable,base,e2e\n' "$arbre_c" > "$donnees/ci/preuves"
verifie "conteneur : ci/preuves sans ligne Mac : refusé" 1 pousse_c
printf '%s\n' "$arbre_c" > "$mac_ok"
printf '%s\tcle\tportable,base\n' "$arbre_c" > "$donnees/ci/preuves"
verifie "conteneur : deux phases sur trois : refusé" 1 pousse_c
printf '%s\tcle\tportable,base,e2e\n' "$(git rev-parse 'HEAD~1^{tree}')" > "$donnees/ci/preuves"
verifie "conteneur : ligne d'un autre arbre : refusé" 1 pousse_c
printf '%s\tcle\tportable,base,e2e\n' "$arbre_c" > "$donnees/ci/preuves"; : > "$mac_ok"
verifie "conteneur : fichier Mac sans l'arbre : refusé" 1 pousse_c
printf '%s\n' "$arbre_c" > "$mac_ok"; rm -f "$donnees/ci/preuves"
fichier_branche=$(git rev-parse --git-path pmzilla-run-branch-ok)
printf '%s\talpha\n' "$arbre_c" > "$fichier_branche"
verifie "conteneur : l'empreinte de branche (ciblee) seule ne passe jamais : refusé" 1 pousse_c
rm -f "$fichier_branche"
printf '%s\tcle\tportable,base,e2e\n' "$arbre_c" > "$donnees/ci/preuves"
if [ "$(id -u)" -eq 0 ]; then   # en root, chmod 000 n'empêche pas la lecture : le cas ne prouverait rien (revue Opus point 10)
  echo "saute : conteneur : ci/preuves illisible (appel sans preuve) : refusé (le test tourne en root, chmod 000 est sans effet)"
else
  chmod 000 "$donnees/ci/preuves"
  verifie "conteneur : ci/preuves illisible (appel sans preuve) : refusé" 1 pousse_c
  chmod 600 "$donnees/ci/preuves"
fi
rm -f "$tmp/lance-c"   # les refus précédents ont fait tourner le lanceur rouge (repli du hook) : le témoin est remis à zéro avant le cas accepté
verifie "conteneur : trois phases et ligne Mac : accepté sans lancer de test" 0 pousse_c
verifie "conteneur : le lanceur n'a pas tourné" 1 test -e "$tmp/lance-c"
rm -f "$mac_ok"

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
