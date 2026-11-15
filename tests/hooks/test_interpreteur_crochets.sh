#!/bin/sh
# Test des interpréteurs des crochets (R-20261108-07, R-20261108-09, R-20261108-10) : le crochet post-commit ne lit aucun fichier de démarrage de zsh
# (ZDOTDIR), les crochets Python tournent sous /Library/Developer/CommandLineTools/usr/bin/python3 -IS (chemin absolu, sans le relais /usr/bin/python3 :
# ni PATH, ni PYTHONPATH, ni PYTHONPYCACHEPREFIX, ni DEVELOPER_DIR, ni site) et ne lisent ni n'écrivent jamais tools/__pycache__. Chaque cas a son témoin.
# Suite propre au Mac (stat -f BSD, et relais /usr/bin/python3 qui suit DEVELOPER_DIR, propres au Mac ; l'image de la CI locale n'a qu'un lien
# vers son Python, R-20261109-04).
# Aucun appel à Claude, à Ollama ni au réseau. Lancement à la main : sh tests/hooks/test_interpreteur_crochets.sh
set -u
# Première ligne attendue des crochets pre-commit et pre-merge-commit : décision de l'auteur (R-20261108-10).
INTERPRETE="/Library/Developer/CommandLineTools/usr/bin/python3 -IS"
ATTENDU_PRE_COMMIT="#!$INTERPRETE"
unset CLAUDECODE PMZILLA_AFTER_COMMIT PYTHONDONTWRITEBYTECODE PYTHONPATH PYTHONPYCACHEPREFIX ZDOTDIR DEVELOPER_DIR FINISH_LOCK_TOKEN PMZILLA_SKIP_GREEN_CHECK
dossier="$(cd "$(dirname "$0")/../../tools/hooks" && pwd)"
outils="$(dirname "$dossier")"
tmp=$(mktemp -d) || exit 1
trap 'rm -rf "$tmp"' EXIT
# les préfixes et dossiers que les crochets créent eux-mêmes restent dans le dossier du test
export TMPDIR="$tmp"
export HOME="$tmp/home"
mkdir -p "$HOME" "$tmp/zd" "$tmp/pp" "$tmp/travail"
ok=0; ko=0
verifie() { # description code (0 = vrai)
  if [ "$2" -eq 0 ]; then echo "ok : $1"; ok=$((ok+1)); else echo "ECHEC : $1"; ko=$((ko+1)); fi
}

# Première ligne des crochets
[ "$(head -1 "$dossier/pre-commit")" = "$ATTENDU_PRE_COMMIT" ]; verifie "pre-commit : première ligne attendue" $?
[ "$(head -1 "$dossier/pre-merge-commit")" = "$ATTENDU_PRE_COMMIT" ]; verifie "pre-merge-commit : première ligne attendue" $?
[ "$(head -1 "$dossier/post-commit")" = "#!/bin/zsh -f" ]; verifie "post-commit : zsh sans fichier de démarrage (-f)" $?
for h in commit-msg reference-transaction; do
  grep -qF "$INTERPRETE" "$dossier/$h"; verifie "$h : lance $INTERPRETE" $?
  # hors lignes de commentaire, toute ligne qui nomme python3 le nomme par son chemin absolu des CommandLineTools et -IS
  [ -z "$(grep -v '^[[:space:]]*#' "$dossier/$h" | grep 'python3' | grep -vF "$INTERPRETE")" ]; verifie "$h : aucun python3 nu (trouvé par PATH)" $?
  # le relais /usr/bin/python3 (qui suit DEVELOPER_DIR) n'est jamais nommé hors commentaire
  [ -z "$(grep -v '^[[:space:]]*#' "$dossier/$h" | grep -F '/usr/bin/python3' | grep -vF "$INTERPRETE")" ]; verifie "$h : aucun relais /usr/bin/python3" $?
done
for h in pre-commit pre-merge-commit commit-msg reference-transaction post-commit; do
  [ -x "$dossier/$h" ]; verifie "$h : exécutable" $?
done

# Les crochets se lancent pour de bon (ni 126, ni 127) dans un dépôt neuf du dossier temporaire
mkdir -p "$tmp/depot" && ( cd "$tmp/depot" && git init -q . ) > /dev/null 2>&1
interprete=$(head -1 "$dossier/pre-commit"); interprete=${interprete#\#!}
# shellcheck disable=SC2086
$interprete -c pass > /dev/null 2>&1; code=$?
[ "$code" -eq 0 ]; verifie "pre-commit : l'interpréteur de sa première ligne démarre (code $code)" $?
# exécution directe : c'est la première ligne qui choisit l'interpréteur
( cd "$tmp/depot" && "$dossier/pre-commit" > /dev/null 2> "$tmp/erreur-pre-commit" < /dev/null ); code=$?
[ "$code" -ne 126 ] && [ "$code" -ne 127 ]; verifie "pre-commit : le crochet se lance (code $code, ni 126 ni 127)" $?
grep -q "pre-commit : lance d'abord bash tests/run_all.sh" "$tmp/erreur-pre-commit"; verifie "pre-commit : sa sortie d'erreur porte sa phrase connue" $?
( cd "$tmp/depot" && "$dossier/post-commit" > /dev/null 2>&1 ); code=$?
[ "$code" -eq 0 ]; verifie "post-commit : le crochet se lance et rend 0 (code $code)" $?

# commit-msg : un message propre passe (0), un message qui porte le nom de la liste (fournie ici, factice) est refusé (1) avec la phrase de l'outil ;
# les deux scanners tournent donc pour de bon
echo "nomtemoinzzq" > "$tmp/noms.txt"
echo "un message sans rien de particulier" > "$tmp/message-propre"
echo "un message qui nomme nomtemoinzzq" > "$tmp/message-nom"
( cd "$tmp/depot" && PMZILLA_NOMS="$tmp/noms.txt" "$dossier/commit-msg" "$tmp/message-propre" > /dev/null 2> "$tmp/erreur-cm-propre" < /dev/null ); code=$?
[ "$code" -eq 0 ]; verifie "commit-msg : un message propre passe (code $code)" $?
( cd "$tmp/depot" && PMZILLA_NOMS="$tmp/noms.txt" "$dossier/commit-msg" "$tmp/message-nom" > /dev/null 2> "$tmp/erreur-cm-nom" < /dev/null ); code=$?
[ "$code" -eq 1 ]; verifie "commit-msg : un message qui porte un nom est refusé (code $code)" $?
grep -q "commit-msg : nom sensible dans le message, ligne 1" "$tmp/erreur-cm-nom"; verifie "commit-msg : sa sortie d'erreur porte la phrase de l'outil des noms" $?

# pre-merge-commit et reference-transaction : sans verrou de fin, 0 ; avec un verrou vivant d'un autre jeton, 1 et la phrase du crochet ; avec le jeton, 0
zero="0000000000000000000000000000000000000000"; un="1111111111111111111111111111111111111111"
( cd "$tmp/depot" && "$dossier/pre-merge-commit" > /dev/null 2> "$tmp/erreur-pmc-libre" < /dev/null ); code=$?
[ "$code" -eq 0 ]; verifie "pre-merge-commit : sans verrou, 0 (code $code)" $?
mkdir "$tmp/depot/.git/pmzilla-fin-en-cours"
echo "$$" > "$tmp/depot/.git/pmzilla-fin-en-cours/pid"
date +%s > "$tmp/depot/.git/pmzilla-fin-en-cours/debut"
echo "branche-temoin" > "$tmp/depot/.git/pmzilla-fin-en-cours/branche"
echo "jeton-temoin" > "$tmp/depot/.git/pmzilla-fin-en-cours/jeton"
( cd "$tmp/depot" && "$dossier/pre-merge-commit" > /dev/null 2> "$tmp/erreur-pmc" < /dev/null ); code=$?
[ "$code" -eq 1 ]; verifie "pre-merge-commit : verrou vivant d'un autre jeton, 1 (code $code)" $?
grep -q "pre-merge-commit : fin de branche en cours (branche-temoin), fusion refusée" "$tmp/erreur-pmc"; verifie "pre-merge-commit : sa phrase connue" $?
( cd "$tmp/depot" && echo "$zero $un refs/heads/main" | "$dossier/reference-transaction" prepared > /dev/null 2> "$tmp/erreur-rt" ); code=$?
[ "$code" -eq 1 ]; verifie "reference-transaction : verrou vivant d'un autre jeton, 1 (code $code)" $?
grep -q "reference-transaction : fin de branche en cours (branche-temoin), mise à jour de main refusée" "$tmp/erreur-rt"; verifie "reference-transaction : sa phrase connue" $?
( cd "$tmp/depot" && echo "$zero $un refs/heads/main" | FINISH_LOCK_TOKEN="jeton-temoin" "$dossier/reference-transaction" prepared > /dev/null 2>&1 ); code=$?
[ "$code" -eq 0 ]; verifie "reference-transaction : le jeton du verrou laisse passer (code $code)" $?
( cd "$tmp/depot" && FINISH_LOCK_TOKEN="jeton-temoin" "$dossier/pre-merge-commit" > /dev/null 2>&1 < /dev/null ); code=$?
[ "$code" -eq 0 ]; verifie "pre-merge-commit : le jeton du verrou laisse passer (code $code)" $?

# post-commit et ZDOTDIR : un .zshenv qui note son passage
echo "echo lu > \"$tmp/marque-zsh\"" > "$tmp/zd/.zshenv"
rm -f "$tmp/marque-zsh"
ZDOTDIR="$tmp/zd" zsh -c true
[ -f "$tmp/marque-zsh" ]; verifie "témoin : zsh sans -f lit le .zshenv de ZDOTDIR" $?
rm -f "$tmp/marque-zsh"
( cd "$tmp/travail" && ZDOTDIR="$tmp/zd" PMZILLA_NO_EVALS=1 "$dossier/post-commit" > /dev/null 2>&1 )
[ ! -f "$tmp/marque-zsh" ]; verifie "post-commit : le .zshenv de ZDOTDIR n'est pas lu" $?

# pre-commit et PYTHONPATH : un sitecustomize qui note son passage
echo "open(\"$tmp/marque-path\", 'w').close()" > "$tmp/pp/sitecustomize.py"
rm -f "$tmp/marque-path"
PYTHONPATH="$tmp/pp" python3 -c pass
[ -f "$tmp/marque-path" ]; verifie "témoin : python3 sans -I charge le sitecustomize de PYTHONPATH" $?
rm -f "$tmp/marque-path"
( cd "$tmp/travail" && PYTHONPATH="$tmp/pp" "$dossier/pre-commit" > /dev/null 2>&1 < /dev/null )
[ ! -f "$tmp/marque-path" ]; verifie "pre-commit : PYTHONPATH est ignoré" $?

# pre-commit et PYTHONPYCACHEPREFIX : aucun code compilé n'est écrit dans le dossier désigné
PYTHONPYCACHEPREFIX="$tmp/cache-temoin" PYTHONPATH="$outils" python3 -c "import lab_paths"
[ -n "$(find "$tmp/cache-temoin" -name '*.pyc' 2>/dev/null)" ]; verifie "témoin : python3 sans -I écrit son code compilé sous PYTHONPYCACHEPREFIX" $?
( cd "$tmp/travail" && PYTHONPYCACHEPREFIX="$tmp/cache" "$dossier/pre-commit" > /dev/null 2>&1 < /dev/null )
[ -z "$(find "$tmp/cache" -name '*.pyc' 2>/dev/null)" ]; verifie "pre-commit : PYTHONPYCACHEPREFIX est ignoré" $?

# R-20261108-10 : DEVELOPER_DIR. /usr/bin/python3 est le relais xcrun des CommandLineTools : il lit DEVELOPER_DIR. Les crochets n'y passent plus. Un faux
# interpréteur à la place où le relais le chercherait (<DEVELOPER_DIR>/usr/bin/python3) note son passage ; aucun crochet ne doit le lancer, chacun doit
# démarrer comme sans la variable, et l'interpréteur lancé (sys.executable) doit être le même avec et sans DEVELOPER_DIR.
mkdir -p "$tmp/dev/usr/bin"
printf '#!/bin/sh\n: > "%s/marque-dev"\nexit 0\n' "$tmp" > "$tmp/dev/usr/bin/python3"
chmod +x "$tmp/dev/usr/bin/python3"
rm -f "$tmp/marque-dev"
"$tmp/dev/usr/bin/python3" -c pass
[ -f "$tmp/marque-dev" ]; verifie "témoin : le faux interpréteur note son passage quand il est appelé directement" $?
rm -f "$tmp/marque-dev"
# témoin du relais : sans la variable, /usr/bin/python3 démarre (0) ; avec DEVELOPER_DIR sur le faux dossier, son comportement change (il lance le faux
# interpréteur, ou il échoue parce que le faux dossier n'a pas la structure qu'attend xcrun) : preuve qu'il suit la variable. Constaté sur ce Mac :
# il n'atteint pas le faux interpréteur (xcrun valide le dossier), le témoin porte donc sur le changement de comportement, pas sur la marque.
/usr/bin/python3 -c pass > /dev/null 2>&1; code=$?
[ "$code" -eq 0 ]; verifie "témoin : le relais /usr/bin/python3 démarre sans DEVELOPER_DIR (code $code)" $?
DEVELOPER_DIR="$tmp/dev" /usr/bin/python3 -c pass > /dev/null 2>&1; code=$?
{ [ -f "$tmp/marque-dev" ] || [ "$code" -ne 0 ]; }; verifie "témoin : le relais /usr/bin/python3 suit DEVELOPER_DIR (faux interpréteur lancé ou échec, code $code)" $?
rm -f "$tmp/marque-dev"
# même cause pour /usr/bin/git, relais xcrun lui aussi : les crochets l'appellent pour lire le dossier Git commun. Avec DEVELOPER_DIR sur le faux dossier
# il échoue, et chaque crochet de verrou dit alors sa phrase d'échec fermé « vérification impossible (dossier Git commun non lu ... » au lieu de la phrase
# du verrou. Le code 1 est le même ; le test établit la cause par la sortie réelle de git, puis attend la phrase d'échec fermé (et non celle du verrou).
( cd "$tmp/depot" && DEVELOPER_DIR="$tmp/dev" git rev-parse --git-common-dir > /dev/null 2> "$tmp/erreur-dev-git" ); code=$?
[ "$code" -ne 0 ]; verifie "témoin : git (relais xcrun) échoue avec DEVELOPER_DIR sur le faux dossier (code $code)" $?
[ -s "$tmp/erreur-dev-git" ]; verifie "témoin : git écrit son erreur de relais xcrun sur la sortie d'erreur" $?
# les crochets de verrou rendent le même code qu'avant
( cd "$tmp/depot" && DEVELOPER_DIR="$tmp/dev" "$dossier/pre-commit" > /dev/null 2> "$tmp/erreur-dev-pc" < /dev/null ); code=$?
[ "$code" -eq 1 ]; verifie "DEVELOPER_DIR : pre-commit démarre et rend son code (verrou vivant : 1, code $code)" $?
grep -q "pre-commit : vérification impossible (dossier Git commun non lu" "$tmp/erreur-dev-pc"; verifie "DEVELOPER_DIR : pre-commit porte sa phrase d'échec fermé (git du relais en échec)" $?
( cd "$tmp/depot" && DEVELOPER_DIR="$tmp/dev" "$dossier/pre-merge-commit" > /dev/null 2> "$tmp/erreur-dev-pmc" < /dev/null ); code=$?
[ "$code" -eq 1 ]; verifie "DEVELOPER_DIR : pre-merge-commit démarre et rend son code (code $code)" $?
grep -q "pre-merge-commit : vérification impossible (dossier Git commun non lu" "$tmp/erreur-dev-pmc"; verifie "DEVELOPER_DIR : pre-merge-commit porte sa phrase d'échec fermé (git du relais en échec)" $?
( cd "$tmp/depot" && echo "$zero $un refs/heads/main" | DEVELOPER_DIR="$tmp/dev" "$dossier/reference-transaction" prepared > /dev/null 2> "$tmp/erreur-dev-rt" ); code=$?
[ "$code" -eq 1 ]; verifie "DEVELOPER_DIR : reference-transaction démarre et rend son code (code $code)" $?
grep -q "reference-transaction : vérification impossible (dossier Git commun non lu" "$tmp/erreur-dev-rt"; verifie "DEVELOPER_DIR : reference-transaction porte sa phrase d'échec fermé (git du relais en échec)" $?
( cd "$tmp/depot" && DEVELOPER_DIR="$tmp/dev" PMZILLA_NOMS="$tmp/noms.txt" "$dossier/commit-msg" "$tmp/message-nom" > /dev/null 2> "$tmp/erreur-dev-cm" < /dev/null ); code=$?
[ "$code" -eq 1 ]; verifie "DEVELOPER_DIR : commit-msg démarre et refuse le message qui porte un nom (code $code)" $?
grep -q "commit-msg : nom sensible dans le message, ligne 1" "$tmp/erreur-dev-cm"; verifie "DEVELOPER_DIR : commit-msg porte la phrase de l'outil des noms" $?
[ ! -f "$tmp/marque-dev" ]; verifie "DEVELOPER_DIR : aucun crochet n'a lancé le faux interpréteur" $?
rm -f "$tmp/marque-dev"
# la première ligne des crochets, lancée avec -c, écrit son sys.executable : sans la variable, puis avec DEVELOPER_DIR posé sur le faux dossier
# shellcheck disable=SC2086
$interprete -c 'import sys; open(sys.argv[1], "w").write(sys.executable)' "$tmp/exe-sans"; code=$?
[ "$code" -eq 0 ] && [ -s "$tmp/exe-sans" ]; verifie "DEVELOPER_DIR : l'interpréteur de la première ligne écrit son sys.executable sans la variable (code $code)" $?
# shellcheck disable=SC2086
DEVELOPER_DIR="$tmp/dev" $interprete -c 'import sys; open(sys.argv[1], "w").write(sys.executable)' "$tmp/exe-avec"; code=$?
[ "$code" -eq 0 ] && [ -s "$tmp/exe-avec" ]; verifie "DEVELOPER_DIR : l'interpréteur de la première ligne écrit son sys.executable avec la variable (code $code)" $?
cmp -s "$tmp/exe-sans" "$tmp/exe-avec"; verifie "DEVELOPER_DIR : l'interpréteur lancé est le même avec et sans la variable" $?
[ ! -f "$tmp/marque-dev" ]; verifie "DEVELOPER_DIR : le faux interpréteur n'a pas été lancé par l'appel de la première ligne" $?

# R-20261108-09 point 3 : aucun code compilé lu ni écrit dans tools/__pycache__.
# (a) écriture : liste, tailles et dates du __pycache__ d'une COPIE PRIVÉE des outils (dossier temporaire du test) avant et après le lancement de chaque
# crochet Python. Le tools/__pycache__ du worktree n'est pas mesuré : pendant un runner complet, d'autres suites y écrivent en parallèle (R-20261113-34).
# Les crochets lisent leurs modules à côté d'eux (c'est ce que prouve la partie (b)) : la copie est donc le dossier que les crochets lancés d'elle lisent.
copie_a="$tmp/copie-a/tools"
mkdir -p "$copie_a/hooks"
for f in finish_lock.py lab_paths.py sensitive_names.py secret_scan.py identifiants_personnels.py commit_names_scan.py; do cp "$outils/$f" "$copie_a/$f"; done
for h in pre-commit pre-merge-commit commit-msg reference-transaction; do cp "$dossier/$h" "$copie_a/hooks/$h"; chmod +x "$copie_a/hooks/$h"; done
etat_cache() { # existence du dossier, puis chaque fichier avec sa taille et sa date de modification
  if [ -d "$copie_a/__pycache__" ]; then echo "present"; find "$copie_a/__pycache__" -type f -exec stat -f '%N %z %m' {} + 2>/dev/null | sort; else echo "absent"; fi
}
avant=$(etat_cache)
( cd "$tmp/depot" && "$copie_a/hooks/pre-commit" > /dev/null 2> "$tmp/erreur-a-pc" < /dev/null ); code=$?
[ "$code" -eq 1 ] && grep -q "pre-commit : fin de branche en cours (branche-temoin), commit refusé" "$tmp/erreur-a-pc"; verifie "copie privée : pre-commit a importé ses modules et rendu son code de verrou (code $code)" $?
( cd "$tmp/depot" && "$copie_a/hooks/pre-merge-commit" > /dev/null 2> "$tmp/erreur-a-pmc" < /dev/null ); code=$?
[ "$code" -eq 1 ] && grep -q "pre-merge-commit : fin de branche en cours (branche-temoin), fusion refusée" "$tmp/erreur-a-pmc"; verifie "copie privée : pre-merge-commit a importé finish_lock (code $code)" $?
( cd "$tmp/depot" && echo "$zero $un refs/heads/main" | "$copie_a/hooks/reference-transaction" prepared > /dev/null 2> "$tmp/erreur-a-rt" ); code=$?
[ "$code" -eq 1 ] && grep -q "reference-transaction : fin de branche en cours (branche-temoin), mise à jour de main refusée" "$tmp/erreur-a-rt"; verifie "copie privée : reference-transaction a importé finish_lock (code $code)" $?
( cd "$tmp/depot" && PMZILLA_NOMS="$tmp/noms.txt" "$copie_a/hooks/commit-msg" "$tmp/message-nom" > /dev/null 2> "$tmp/erreur-a-cm" < /dev/null ); code=$?
[ "$code" -eq 1 ] && grep -q "commit-msg : nom sensible dans le message, ligne 1" "$tmp/erreur-a-cm" && ! grep -q -e "identifiant personnel" -e "n'a pas pu être vérifié" "$tmp/erreur-a-cm"; verifie "copie privée : commit-msg a lancé ses deux scanners jusqu'au bout (code $code)" $?
apres=$(etat_cache)
[ "$avant" = "$apres" ]; verifie "tools/__pycache__ de la copie privée des outils : aucun fichier ajouté ni modifié par les quatre crochets Python" $?
# (b) lecture : une copie des outils porte, dans son __pycache__, un code compilé empoisonné (somme de contrôle non vérifiée) pour finish_lock et
# lab_paths ; il note son passage. Témoin : sous -IS sans réglage du préfixe, l'import le charge. Les crochets ne doivent pas le charger.
copie="$tmp/copie/tools"
mkdir -p "$copie/hooks"
for f in finish_lock.py lab_paths.py sensitive_names.py secret_scan.py identifiants_personnels.py commit_names_scan.py; do cp "$outils/$f" "$copie/$f"; done
for h in pre-commit pre-merge-commit commit-msg reference-transaction; do cp "$dossier/$h" "$copie/hooks/$h"; chmod +x "$copie/hooks/$h"; done
printf 'import os\nopen(os.environ["POISON_MARQUE"], "w").close()\nraise ImportError("poison")\n' > "$tmp/poison.py"
for m in finish_lock lab_paths; do
  $INTERPRETE -c 'import importlib.util, py_compile, sys
cache = importlib.util.cache_from_source(sys.argv[2])
py_compile.compile(sys.argv[1], cfile=cache, doraise=True, invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH)' "$tmp/poison.py" "$copie/$m.py"
done
rm -f "$tmp/marque-poison"
POISON_MARQUE="$tmp/marque-poison" $INTERPRETE -c 'import sys
sys.path.insert(0, sys.argv[1])
import finish_lock' "$copie" > /dev/null 2>&1
[ -f "$tmp/marque-poison" ]; verifie "témoin : $INTERPRETE charge le code compilé de __pycache__ quand rien ne règle le préfixe" $?
rm -f "$tmp/marque-poison"
# empreinte des deux codes compilés empoisonnés avant les crochets, comparée après : aucune réécriture
empreinte_pyc() { cksum "$copie"/__pycache__/finish_lock*.pyc "$copie"/__pycache__/lab_paths*.pyc; }
empreinte_avant=$(empreinte_pyc)
( cd "$tmp/depot" && POISON_MARQUE="$tmp/marque-poison" "$copie/hooks/pre-commit" > /dev/null 2>&1 < /dev/null )
[ ! -f "$tmp/marque-poison" ]; verifie "pre-commit : ne lit pas le code compilé de tools/__pycache__" $?
( cd "$tmp/depot" && POISON_MARQUE="$tmp/marque-poison" "$copie/hooks/pre-merge-commit" > /dev/null 2>&1 < /dev/null )
[ ! -f "$tmp/marque-poison" ]; verifie "pre-merge-commit : ne lit pas le code compilé de tools/__pycache__" $?
( cd "$tmp/depot" && echo "$zero $un refs/heads/main" | POISON_MARQUE="$tmp/marque-poison" "$copie/hooks/reference-transaction" prepared > /dev/null 2>&1 )
[ ! -f "$tmp/marque-poison" ]; verifie "reference-transaction : ne lit pas le code compilé de tools/__pycache__" $?
( cd "$tmp/depot" && POISON_MARQUE="$tmp/marque-poison" PMZILLA_NOMS="$tmp/noms.txt" "$copie/hooks/commit-msg" "$tmp/message-nom" > /dev/null 2>&1 < /dev/null )
[ ! -f "$tmp/marque-poison" ]; verifie "commit-msg : ne lit pas le code compilé de tools/__pycache__ (ses deux scanners)" $?
[ -n "$empreinte_avant" ] && [ "$empreinte_avant" = "$(empreinte_pyc)" ]; verifie "les deux codes compilés empoisonnés ont la même empreinte (cksum) après les crochets : aucune réécriture" $?
[ -z "$(find "$copie/__pycache__" -name '*.pyc' -newer "$tmp/poison.py" ! -name 'finish_lock*' ! -name 'lab_paths*' 2>/dev/null)" ]; verifie "les crochets n'ont écrit aucun code compilé dans la copie des outils" $?

echo "$ok réussis, $ko échec(s)"
[ "$ko" -eq 0 ]
