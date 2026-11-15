"""Garde npm (idée 434, change mothra-session-guards) : tools/npm_guard.py refuse, par le code 2 d'un hook PreToolUse, toute commande Bash
qui lancerait npm, npx ou node d'une manière interdite aux sessions, en la résolvant comme npm (alias, abréviations uniques, camelCase,
npm 11), à travers les chemins absolus, les lanceurs (env, sudo, timeout, xargs, find -exec, sh -c, eval, fnm exec, uv run…) et les
commandes composées. Aucune commande n'est exécutée : la suite n'appelle que l'analyse et le script lui-même, qui ne lance rien.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/npm_guard -q -f
"""
import contextlib
import io
import json
import shlex
import subprocess
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
OUTIL = RACINE / "tools" / "npm_guard.py"
sys.path.insert(0, str(RACINE / "tools"))
sys.path.insert(0, str(RACINE / "tests" / "settings_deny"))
import npm_guard  # noqa: E402
import test_settings_deny_npm as regles_deny  # noqa: E402


def refus(commande):
    return npm_guard.refus_de(commande)


def lancer(entree, brut=False):
    texte = entree if brut else json.dumps(entree)
    return subprocess.run([sys.executable, str(OUTIL)], input=texte, capture_output=True, text=True, timeout=30)


def bash(commande):
    return {"tool_name": "Bash", "tool_input": {"command": commande}}


# Copie figée de lib/utils/cmd-list.js de npm 11 (les 72 commandes et les alias), à relire après chaque mise à jour de npm.
COMMANDES_NPM_11 = (
    "access", "adduser", "approve-scripts", "audit", "bugs", "cache", "ci", "completion", "config", "dedupe", "deny-scripts",
    "deprecate", "diff", "dist-tag", "docs", "doctor", "edit", "exec", "explain", "explore", "find-dupes", "fund", "get", "help",
    "help-search", "init", "install", "install-ci-test", "install-scripts", "install-test", "link", "ll", "login", "logout", "ls",
    "org", "outdated", "owner", "pack", "ping", "pkg", "prefix", "profile", "prune", "publish", "query", "rebuild", "repo",
    "restart", "root", "run", "sbom", "search", "set", "shrinkwrap", "stage", "star", "stars", "start", "stop", "team", "test",
    "token", "trust", "undeprecate", "uninstall", "unpublish", "unstar", "update", "version", "view", "whoami",
)
ALIAS_NPM_11 = {
    "author": "owner", "home": "docs", "issues": "bugs", "info": "view", "show": "view", "find": "search", "add": "install",
    "unlink": "uninstall", "remove": "uninstall", "rm": "uninstall", "r": "uninstall", "un": "uninstall", "rb": "rebuild",
    "list": "ls", "ln": "link", "create": "init", "i": "install", "it": "install-test", "cit": "install-ci-test", "u": "update",
    "up": "update", "c": "config", "s": "search", "se": "search", "tst": "test", "t": "test", "ddp": "dedupe", "v": "view",
    "run-script": "run", "clean-install": "ci", "clean-install-test": "install-ci-test", "x": "exec", "why": "explain",
    "la": "ll", "verison": "version", "ic": "ci", "innit": "init", "in": "install", "ins": "install", "inst": "install",
    "insta": "install", "instal": "install", "isnt": "install", "isnta": "install", "isntal": "install", "isntall": "install",
    "install-clean": "ci", "isntall-clean": "ci", "hlep": "help", "dist-tags": "dist-tag", "upgrade": "update",
    "udpate": "update", "rum": "run", "sit": "install-ci-test", "urn": "run", "ogr": "org", "add-user": "adduser",
}


class Cas(unittest.TestCase):
    def refusees(self, commandes):
        for commande in commandes:
            with self.subTest(commande=commande):
                self.assertTrue(refus(commande), f"permise à tort : {commande!r}")

    def permises(self, commandes):
        for commande in commandes:
            with self.subTest(commande=commande):
                self.assertEqual(refus(commande), [], f"refusée à tort : {commande!r}")


class ResolutionDeNpm(unittest.TestCase):
    """La table de npm 11 (lib/utils/cmd-list.js) : nom exact, alias, abréviation unique, camelCase."""

    def test_noms_exacts_et_alias(self):
        attendu = {"install": "install", "i": "install", "add": "install", "isntall": "install", "ic": "ci", "ci": "ci",
                   "clean-install": "ci", "install-clean": "ci", "isntall-clean": "ci", "it": "install-test", "cit": "install-ci-test",
                   "sit": "install-ci-test", "clean-install-test": "install-ci-test", "x": "exec", "up": "update", "u": "update",
                   "upgrade": "update", "udpate": "update", "un": "uninstall", "rm": "uninstall", "r": "uninstall", "t": "test",
                   "tst": "test", "list": "ls", "la": "ll", "run-script": "run", "rum": "run", "urn": "run", "info": "view",
                   "v": "view", "why": "explain", "c": "config", "create": "init", "innit": "init", "ln": "link", "verison": "version",
                   "dist-tags": "dist-tag", "add-user": "adduser", "author": "owner", "home": "docs", "issues": "bugs"}
        for mot, nom in attendu.items():
            with self.subTest(mot=mot):
                self.assertEqual(npm_guard.resoudre_npm(mot), nom)

    def test_abreviations_uniques(self):
        attendu = {"upd": "update", "updat": "update", "upg": "update", "uninst": "uninstall", "unpub": "unpublish", "depre": "deprecate",
                   "exe": "exec", "pru": "prune", "rebu": "rebuild", "tes": "test", "inst": "install", "instal": "install",
                   "uni": "uninstall", "install-t": "install-test", "install-ci": "install-ci-test", "run-scrip": "run", "dedup": "dedupe", "shrink": "shrinkwrap"}
        for mot, nom in attendu.items():
            with self.subTest(mot=mot):
                self.assertEqual(npm_guard.resoudre_npm(mot), nom)

    def test_camelcase(self):
        attendu = {"cleanInstall": "ci", "installTest": "install-test", "installCiTest": "install-ci-test", "cleanInstallTest": "install-ci-test",
                   "helpSearch": "help-search", "findDupes": "find-dupes", "runScript": "run", "installClean": "ci", "distTag": "dist-tag"}
        for mot, nom in attendu.items():
            with self.subTest(mot=mot):
                self.assertEqual(npm_guard.resoudre_npm(mot), nom)

    def test_ambigu_ou_inconnu_ne_resout_rien(self):
        for mot in ("te", "ru", "sta", "de", "p", "zzz", "built", "insx"):
            with self.subTest(mot=mot):
                self.assertIsNone(npm_guard.resoudre_npm(mot))

    def test_toute_commande_de_npm_est_classee(self):
        """Une commande ni permise ni refusée explicitement serait refusée par défaut : la liste des permises reste dans la table."""
        self.assertLessEqual(npm_guard.PERMISES_NPM, set(npm_guard.COMMANDES_NPM))


FORMES_NPM_REFUSEES = (
    # la famille install, tous alias, abréviations et écritures
    "npm install", "npm i", "npm in", "npm ins", "npm inst", "npm insta", "npm instal", "npm isnt", "npm isnta", "npm isntal",
    "npm isntall", "npm add", "npm ic", "npm ci", "npm clean-install", "npm cleanInstall", "npm install-clean", "npm isntall-clean",
    "npm installClean", "npm it", "npm install-test", "npm installTest", "npm cit", "npm sit", "npm install-ci-test",
    "npm install-ci", "npm clean-install-test", "npm cleanInstallTest", "npm install-scripts", "npm ci --offline",
    "npm install fastify", "npm i -D typescript",
    # update, uninstall, link
    "npm update", "npm up", "npm u", "npm upgrade", "npm udpate", "npm upd", "npm updat", "npm upg", "npm uninstall fastify", "npm un x",
    "npm unlink", "npm remove x", "npm rm x", "npm r x", "npm uninst x", "npm link", "npm ln", "npm unl",
    # registre, exécution, projet
    "npm publish", "npm pub", "npm unpublish x", "npm unpub x", "npm deprecate x y", "npm depre x y", "npm undeprecate x",
    "npm exec tsc", "npm x tsc", "npm exe tsc", "npm init", "npm create vite", "npm innit", "npm dedupe", "npm dedup", "npm ddp",
    "npm rebuild", "npm rb", "npm rebu", "npm prune", "npm pru", "npm version patch", "npm verison patch", "npm set a b", "npm edit x",
    "npm explore x", "npm shrinkwrap", "npm shrink", "npm pack", "npm cache clean", "npm cach clean",
    # compte, équipe, étiquettes
    "npm adduser", "npm add-user", "npm login", "npm logout", "npm token", "npm owner ls x", "npm author", "npm team", "npm org", "npm ogr",
    "npm access", "npm profile", "npm star x", "npm unstar x", "npm dist-tag ls x", "npm dist-tag rm x y", "npm dist-tags",
    "npm trust", "npm approve-scripts", "npm deny-scripts", "npm stage",
    # sous-formes d'une commande permise
    "npm audit fix", "npm audit fix --force", "npm --json audit fix", "npm audit --json fix", "npm audit --fix",
    "npm config set a b", "npm c set a b", "npm config delete a", "npm config rm a", "npm config edit", "npm config fix",
    "npm pkg set a=b", "npm pkg delete a", "npm pkg fix",
    # options avant la sous-commande
    "npm --prefix mothra install", "npm --prefix=mothra install", "npm -w server ci", "npm --workspace=web update", "npm -ws install",
    "npm --loglevel silent install", "npm --loglevel=silent --prefix mothra i", "npm --json i", "npm --silent install", "npm -s i",
    "npm -dd i", "npm --foo bar install", "npm --foo install", "npm --foo ls install", "npm -- install", "npm --no-audit install",
    "npm --registry https://exemple.invalid install",
)

FORMES_NPM_PERMISES = (
    "npm", "npm test", "npm t", "npm tst", "npm tes", "npm test -- --run", "npm run build", "npm run-script build", "npm rum build",
    "npm urn build", "npm run-scrip build", "npm run lint", "npm run typecheck", "npm run dev", "npm run clean", "npm start",
    "npm ls", "npm ls --all", "npm list", "npm view fastify version", "npm v fastify",
    "npm info fastify", "npm show fastify", "npm outdated", "npm outdated --json", "npm audit", "npm audit --json",
    "npm audit signatures", "npm help", "npm help install", "npm help ci", "npm --version", "npm -v",
    "npm config get registry", "npm c get x", "npm config --location=global get registry",
    "npm --global true test", "npm -g false test", "npm --color always run build", "npm --json true ls", "npm -g false ls",
    "npm --prefix mothra test", "npm --prefix mothra run build", "npm --prefix=mothra run build", "npm -w server run build",
    "npm --workspace=web test", "npm --workspaces test", "npm -ws run build", "npm --silent run build", "npm -s test", "npm --json outdated",
    "npm --loglevel=silent test", "npm --loglevel silent run build", "npm -dd ls", "npm --no-audit test", "npm --if-present run x",
    "npm run install-check", "npm run update-snapshots", "npm run build -- --target x", "npm run i", "npm run ci",
    "npm test install", "npm run x -- install", "npm --user-agent=x test", "npm run x -- --shell",
)

# Hors de la liste de mothra/CLAUDE.md (« Commands a session runs ») : refusées, ainsi que tout mot inconnu ou ambigu.
FORMES_NPM_HORS_LISTE = (
    "npm docs x", "npm home x", "npm bugs x", "npm issues x", "npm repo x", "npm doctor", "npm diff", "npm search x", "npm find x",
    "npm s x", "npm whoami", "npm ping", "npm completion", "npm stop", "npm restart", "npm explain x", "npm why x", "npm ll", "npm la",
    "npm root", "npm prefix", "npm fund", "npm get registry", "npm config list", "npm config ls", "npm config", "npm config get set",
    "npm pkg get name", "npm sbom", "npm query x", "npm stars", "npm find-dupes", "npm help-search x",
    "npm te", "npm ru", "npm sta", "npm zzz", "npm built", "npm --silent zzz", "npm de", "npm p",
)

# Revue de sécurité (R-133) : ce que la première version laissait passer.
OPTIONS_BOOLEENNES_REFUSEES = (   # a : nopt donne true, false ou always à l'option booléenne, jamais la sous-commande
    "npm --global true install", "npm -g false i x", "npm --color always install", "npm --json true install", "npm --no-color true ci",
    "npm --silent false update", "npm -s true i", "npm --global true --json false install", "npm -g true -s false exec x",
)
OPTIONS_QUI_LANCENT_REFUSEES = (   # b : options qui font lancer un programme, entières ou abrégées, et affectations de configuration
    "npm --browser x test", "npm --browser=firefox ls", "npm --viewer x help", "npm --editor vim test", "npm --script-shell /bin/sh test",
    "npm --script-shell=sh run x", "npm --shell sh test", "npm --node-options=--x test", "npm --userconfig f test", "npm --globalconfig f ls",
    "npm --script-s=x test", "npm --node-o x test", "npm --brow x ls", "npm --user x test", "npm --glob x ls", "npm --ed x test",
    "npm_config_script_shell=x npm test", "NPM_CONFIG_NODE_OPTIONS=x npm test", "NODE_OPTIONS=--require=x npm test",
    "env npm_config_x=1 npm test", "export NODE_OPTIONS=x; npm test", "env -S 'NODE_OPTIONS=x npm test'", "NODE_OPTIONS=x node server.js",
    "env NODE_OPTIONS=x node server.js", "export npm_config_userconfig=x", "NPM_CONFIG_PREFIX=x ls",
)
NODE_OPTIONS_INCONNUES = (   # c : une option inconnue qui prend une valeur ne cache pas un -e, -p, --eval ou --print qui suit
    "node --env-file-if-exists .env -e 1", "node --env-file-if-exists=.env -e 1", "node --foo bar --eval 1", "node --foo bar -p 1",
    "node --foo -pe 1", "node --trace-event-categories v8 -e 1", "node --foo bar --print=1", "node --foo bar --eval=1",
    "node --import=DATA:text/javascript,x", "node --import DATA:x", "node --require Data:x", "node -r DATA:x", "node -rdata:x",
    "node --loader Data:x a.js", "node --experimental-loader DATA:x a.js", "node --foo x --interactive", "node --foo x -i",
)
DOCUMENTS_ICI_ET_ARITHMETIQUE_REFUSES = (   # d : << dans une arithmétique n'ouvre pas de document ici ; un vrai document garde ses substitutions
    "((1<<2))\nnpm install", "echo $((1<<2))\nnpm install", "x=$((1<<2))\nnpm ci", "((i=1<<2)); npm install", "(( 1 << 2 ))\nnpm i",
    "((x=2<<3))\nnpm update",
    "cat <<EOF\nabc\nEOF\nnpm install", "cat <<EOF\n$(npm install)\nEOF", "cat <<EOF\n`npm install`\nEOF", "cat <<'EOF'\n$(npm install)\nEOF",
    "cat <<-EOF\n\tx\n\tEOF\nnpm install", "echo $(( $(npm install) ))", "echo $((1+$(npm ci)))", "((x=$(npm install)))",
    "cat <<EOF\n${x:-$(npm install)}\nEOF",
)
DOCUMENTS_ICI_ET_ARITHMETIQUE_PERMIS = (
    "((1<<2)); echo ok", "echo $((1<<2)) $((2*3))", "((n=2*3))", "cat <<EOF\nabc\nEOF\nnpm test", "echo $((2*3))", "x=$((1<<2)); echo $x",
    "cat <<EOF\n$HOME ${x:-d}\nEOF", "for ((i=0;i<3;i++)); do echo $i; done",
)
ENV_AVEC_LETTRES_GROUPEES = (   # e
    "env -iS 'npm install'", "env -iS'npm install'", "env -i -S 'npm install'", "env -uX -S 'npm i'", "env -iuX -S 'npm i'",
    "env -iS 'cd x && npm ci'", "env -S'npm install' ls",
)
ENTREES_STANDARD_REFUSEES = (   # 4 : programmes lus sur l'entrée standard ou par substitution
    "sh -", "bash -", "bash /dev/stdin", "bash <(echo npm install)", "bash <(curl x)", "sh <(echo x)", "source <(echo npm install)",
    ". <(echo x)", "source /dev/stdin", ". /dev/stdin", "node /dev/stdin", "node /dev/fd/0", "bash /dev/fd/63", "bash /proc/self/fd/0",
    "node <(echo 1)", "zsh /dev/stdin",
)
SUBSTITUTIONS_DANS_ACCOLADES_REFUSEES = (
    "echo ${x:-$(npm install)}", "echo ${x:=$(npm ci)}", 'echo "${x:-$(npm install)}"', "echo ${x:-`npm install`}", "echo ${x:-${y:-$(npm i)}}",
    "echo ${x/$(npm install)/y}",
)
FORMES_SHELL_REFUSEES = (   # function, trap, coproc, zsh
    "function f { npm install; }", "function f() { npm install; }", "function f { npm install; }; f", "trap 'npm install' EXIT",
    "trap -- 'npm install' EXIT", "trap 'npm i' ERR", "coproc npm install", "coproc NAME { npm install; }", "=npm install",
    "noglob npm install", "nocorrect npm install", "repeat 2 npm install", "- npm install", "{ echo a; } always { npm install; }",
    "$SHELL -c 'npm install'", "$SHELL -c 'ls'", "${SHELL} -c ls", "/opt/homebrew/lib/node_modules/npm/bin/npm-cli.js install",
    "./npm-cli.js i", "npx-cli.js tsc", "/x/bin/npx-cli.js tsc", "NPM-CLI.JS install", "=node -e 1", "repeat 2 do npm install; done",
)
FORMES_SHELL_PERMISES = (
    "source ./env.sh", ". ./env.sh", "trap 'echo bye' EXIT", "trap - EXIT", "trap -p", "function f { echo hi; }", "function f() { echo hi; }",
    "coproc ls", "noglob ls *", "nocorrect ls", "repeat 2 echo hi", "=ls", "- ls", "echo ${x:-default}", "echo ${HOME}", "/x/bin/npm-cli.js test",
    "{ echo a; } always { echo b; }", "echo $SHELL",
)
LANCEURS_SUPPLEMENTAIRES_REFUSES = (   # script, su -c, gtimeout, sandbox-exec, tmux, screen
    "script -q /dev/null npm install", "script -c 'npm install' /dev/null", "script npm install", "su -c 'npm install'",
    "su root -c 'npm install'", "su -lc 'npm i' root", "su --command='npm install' root", "su --command 'npm ci'", "gtimeout 5 npm install",
    "gtimeout -s KILL 5 npm i", "sandbox-exec -p x npm install", "sandbox-exec -f prof.sb npm i", "tmux new-session -d 'npm install'",
    "tmux new -d npm install", "tmux send-keys 'npm install' Enter", "tmux run-shell 'npm i'", "tmux new-session -d -s x 'cd y && npm ci'",
    "screen -dmS x npm install", "screen -X stuff 'npm install'", "screen -dm bash -c 'npm i'", "tmux new-session -d 'node -e 1'",
)
LANCEURS_SUPPLEMENTAIRES_PERMIS = (
    "gtimeout 5 npm test", "su -c 'ls' root", "script -q /dev/null ls", "script -c 'ls' /dev/null", "tmux ls", "tmux new -s dev",
    "tmux send-keys 'ls' Enter", "screen -ls", "sandbox-exec -p x ls", "tmux new-session -d 'npm test'", "screen -dmS x npm test",
)
COMMANDES_ILLISIBLES = ("echo 'abc", 'echo "abc | tail', "echo $(abc", "echo `abc", "echo ${abc", "echo $((1+2)", "echo \"$(\"",
                        "echo 'npm install", 'npm install "', "npm install $(", "npm install `", "npx 'x", "echo $(npm install")



class FormesNpm(Cas):
    def test_formes_refusees(self):
        self.refusees(FORMES_NPM_REFUSEES)

    def test_formes_permises(self):
        self.permises(FORMES_NPM_PERMISES)

    def test_hors_de_la_liste_de_mothra_refuse(self):
        self.refusees(FORMES_NPM_HORS_LISTE)

    def test_le_motif_nomme_la_commande_resolue_et_l_ecriture(self):
        self.assertEqual(refus("npm isntall x"), ["npm install (écrit « isntall »)"])
        self.assertEqual(refus("npm install x"), ["npm install"])
        self.assertEqual(refus("npm cleanInstall"), ["npm ci (écrit « cleanInstall »)"])
        self.assertEqual(refus("npm audit fix"), ["npm audit fix"])
        self.assertEqual(refus("npm config set a b"), ["npm config set"])

    def test_chemins_et_lanceurs_nus(self):
        for prefixe in ("", "cd mothra && ", "cd mothra; ", "env ", "env NODE_ENV=test ", "env -u NPM_TOKEN ", "env -i ", "NODE_ENV=test ",
                        "FOO=1 BAR=2 ", "/opt/homebrew/bin/", "/usr/local/bin/", "~/.local/share/fnm/aliases/default/bin/",
                        "$HOME/.local/share/fnm/aliases/default/bin/", "${HOME}/.local/share/fnm/aliases/default/bin/",
                        "/Users/quelquun/.local/share/fnm/aliases/default/bin/", "~/.local/state/fnm_multishells/123_456/bin/",
                        "/Users/quelquun/.local/state/fnm_multishells/9_9/bin/", "./node_modules/.bin/", "../mothra/bin/"):
            with self.subTest(prefixe=prefixe):
                if prefixe.endswith("/"):
                    self.assertTrue(refus(f"{prefixe}npm install"))
                    self.assertTrue(refus(f"{prefixe}npx tsc"))
                    self.assertTrue(refus(f"{prefixe}node -e 1"))
                    self.assertEqual(refus(f"{prefixe}npm test"), [])
                    self.assertEqual(refus(f"{prefixe}node --version"), [])
                else:
                    self.assertTrue(refus(f"{prefixe}npm install"))
                    self.assertTrue(refus(f"{prefixe}npm isntall"))
                    self.assertTrue(refus(f"{prefixe}npx tsc"))
                    self.assertEqual(refus(f"{prefixe}npm test"), [])

    def test_casse_du_disque_du_mac(self):
        self.refusees(("NPM install", "Npm i", "NPX tsc", "/opt/homebrew/bin/NPM install", "NODE -e 1", "Node -p 1", "YARN add x"))
        self.permises(("NPM test", "Node --version"))


COMPOSEES_REFUSEES = (
    "cd mothra; npm install", "ls && npm i", "false || npm ci", "ls | npm install", "ls & npm install", "npm test && npm install",
    "npm test; npm up", "(npm install)", "{ npm install; }", "{ npm install ; }", "echo a; (cd x && npm up)", "(cd x; (npm ci))",
    "echo $(npm install)", "echo `npm install`", 'echo "$(npm install)"', 'echo "a `npm ci` b"', "echo <(npm install)", "! npm install",
    "if true; then npm install; fi", "if npm install; then echo ok; fi", "while false; do npm ci; done", "for d in a b; do npm i; done",
    "until npm install; do sleep 1; done", "case x in x) npm install ;; esac", "f() { npm install; }; f",
    "npm test\nnpm install", "npm test \\\n && npm i", "npm install # un commentaire", "npm install 2>&1", "npm install > sortie.txt",
    "npm install &> sortie.txt", "npm test 2>/dev/null; npm i", "echo x > a.txt && npm install", "FOO=1 npm install", "NPM_CONFIG_X=1 npm ci",
    "echo $(echo $(npm install))", 'echo "$(echo "$(npm install)")"', "echo $((1+2)) && npm i", "[ -f package.json ] && npm install",
    "[[ -d mothra ]] && npm ci",
)
COMPOSEES_PERMISES = (
    "cd mothra && npm test", "cd mothra; npm start", "(cd mothra && npm test)", "{ npm test; }", "if npm test; then echo ok; fi",
    "for s in a b; do npm run $s; done", "echo $(npm ls)", "echo `npm outdated`", "npm test 2>&1", "npm test > sortie.txt",
    "npm test &> sortie.txt", "npm run build 2>/dev/null || true", "[ -f package.json ] && npm test", "[[ -d mothra ]] && npm test",
    "npm test && npm run build && npm start", "npm ls | wc -l", "npm view fastify --json | python3 -c 'import sys'",
    "echo 'a; npm install'", 'echo "npm install"', "printf '%s' \"npm ci\"", "echo npm install", "git commit -m 'npm install'",
    'git commit -m "feat: npx, npm ci et node -e"', 'grep -rn "npm install" docs/', 'grep -n "npm ci --offline" tools/worktree.sh',
    "git grep npx", 'git grep -n "npm exec"', 'rg "pnpm install" docs', "cat <<EOF\nnpm install\nEOF", "echo a#npm install",
    "ls | sort", "X=1; echo $X", "", "   ", "# npm install", "ls # npm install", "echo 'npm install' > notes.txt",
)


class CommandesComposees(Cas):
    def test_formes_refusees(self):
        self.refusees(COMPOSEES_REFUSEES)

    def test_formes_permises(self):
        self.permises(COMPOSEES_PERMISES)


LANCEURS_REFUSES = (
    # préfixes qui lancent la commande suivante
    "command npm install", "command -p npm install", "builtin command npm install", "exec npm install", "time npm install",
    "time -p npm install", "nohup npm install", "nohup npm install &", "nice npm install", "nice -n 5 npm install", "nice -10 npm install",
    "sudo npm install", "sudo -u x npm install", "sudo -E npm i", "doas npm install", "timeout 60 npm install",
    "timeout -s KILL 60 npm install", "timeout --signal=KILL 60 npm i", "caffeinate npm install", "caffeinate -i npm install",
    "stdbuf -o0 npm install", "setsid npm install", "arch -arm64 npm install", "env -S 'npm install'", "env -S'npm install'",
    "env --split-string='npm install'", "env -- npm install", "env FOO=1 npm install",
    # xargs et find
    "xargs npm install", "xargs -n1 npm install", "xargs -n 1 npm install", "xargs -I{} npm install {}", "echo install | xargs npm",
    "echo i | xargs -I{} npm {}", "echo x | xargs -n1 npm", "echo x | xargs sh -c 'npm install'", "echo x | xargs npx", "echo -e | xargs node",
    "find . -exec npm install \\;", "find . -name package.json -execdir npm ci \\;", "find . -exec npm {} \\;", "find . -ok npm i {} +",
    # interpréteurs et eval
    "sh -c 'npm install'", 'sh -c "npm install"', "bash -c 'npm ci'", "bash -lc 'npm ci'", "zsh -c 'npm i'", "dash -c 'npm i'",
    "bash -c 'cd x && npm install'", "bash -c \"bash -c 'npm install'\"", "sh -c 'echo $(npm install)'", "bash -ec 'npm i'",
    "bash -o pipefail -c 'npm i'", "eval 'npm install'", "eval npm install", 'eval "npm" install', "eval 'ls; npm i'", "watch npm install",
    "watch -n 5 npm install", "echo 'npm install' | sh", "echo 'npm install' | bash", "bash <<< 'npm install'",
    "bash <<EOF\nnpm install\nEOF", "sh", "bash", "zsh -s", "cat x | sh -s",
    # gestionnaires de versions et d'exécution
    "fnm exec npm install", "fnm exec --using=22 npm install", "fnm exec --using 22 -- npm install", "volta run npm install",
    "volta run --node 22 npm install", "mise exec node@22 -- npm install", "mise x -- npm i", "asdf exec npm install",
    "nvm exec 22 npm install", "nvm run 22 -e 1", "direnv exec . npm install", "uv run npm install", "uv run --with x npm install",
    "uvx npm install", "poetry run npm install", "pipenv run npm install",
)
LANCEURS_PERMIS = (
    "command -v npm", "command -v node", "command -pv npm", "which npm", "type npm", "time npm test", "nohup npm start", "nice -n 5 npm test",
    "sudo -u x ls", "timeout 60 npm test", "timeout -s KILL 60 npm test", "caffeinate -i npm test", "env -S 'npm test'",
    "env -- npm test", "env", "env FOO=1", "xargs ls", "echo x | xargs echo", "echo x | xargs -n1 npm test", "find . -name '*.py'",
    "find . -name '*.py' -exec grep -l foo {} \\;", "find . -type f -exec ls {} +", "bash -c 'ls -la'", 'sh -c "echo hi"',
    "bash tools/worktree.sh feat/mothra-slice-0", "bash tools/worktree.sh feat/x --yes", "zsh tools/worktree.sh feat/x",
    "bash tests/run_all.sh npm_guard", "bash tests/run_all.sh mothra", "bash --version", "sh -n script.sh", "eval 'ls -la'",
    "watch ls", "fnm exec node --version", "fnm exec -- npm test", "fnm list", "fnm current", "fnm use 22", "volta run npm test",
    "mise exec node@22 -- npm test", "asdf exec npm test", "nvm use 22", "nvm exec 22 npm test", "nvm run 22 server.js", "direnv exec . npm test",
    "uv run tools/pilot.py freeze --check", "uv run --with numpy --with 'psycopg[binary]' python -W ignore -m unittest discover -s tests/x -q -f",
    "uvx ruff check", "uv sync", "poetry run pytest", "exec ls", "builtin cd x", "sudo ls", "nohup ls &",
)


class Lanceurs(Cas):
    def test_formes_refusees(self):
        self.refusees(LANCEURS_REFUSES)

    def test_formes_permises(self):
        self.permises(LANCEURS_PERMIS)

    def test_imbrication_trop_profonde_refusee(self):
        script = "npm install"
        for _ in range(10):
            script = "sh -c " + shlex.quote(script)
        self.assertTrue(refus(script))
        self.assertIn("commande trop imbriquée", refus(script))


OBFUSQUEES_REFUSEES = (
    "'npm' install", '"npm" install', "n'p'm install", 'n"p"m install', "\\npm install", "n\\pm install", "$'npm' install",
    "$'\\x6e\\x70\\x6d' install", "$'\\156\\160\\155' install", "N=npm; $N install", "N=npm; ${N} install", 'N=npm; "$N" install',
    "export N=npm; $N install", "declare N=npm; $N install", "N='npm install'; $N", "A='--prefix x install'; npm $A", "S=install; npm $S",
    "N=npm; M=install; $N $M", "$(which npm) install", "`which npm` install",
    "$(command -v npm) i", "$NPM install", "${NPM} install", "n* install", "/opt/homebrew/bin/np? install", "/opt/homebrew/bin/n{p,}m install",
    "/opt/homebrew/bin/np[m] install", "npm $(echo install)", 'npm "$SUB"', "npm $SUB", "npm `echo i`", "npm ${SUB:-install}",
    "sh -c \"npm $SUB\"", 'bash -c "npm $@"', "echo x | xargs bash -c 'npm \"$@\"' _",
)
OBFUSQUEES_PERMISES = (
    "$HOME/.local/bin/ruff check", "$CLAUDE_PROJECT_DIR/tools/pilot.py", "$(git rev-parse --show-toplevel)/tools/pilot.py",
    '"$(git rev-parse --show-toplevel)"/tools/pilot.py', "~/bin/outil", "N=ls; $N", "N=npm; echo $N install", "echo $NPM install",
    "[ -f x ]", "[[ -f x ]]", "N=test; npm $N", "npm test $ARGS",
)


class Obfuscations(Cas):
    def test_formes_refusees(self):
        self.refusees(OBFUSQUEES_REFUSEES)

    def test_formes_permises(self):
        self.permises(OBFUSQUEES_PERMISES)

    def test_commande_illisible_est_refusee_avec_ou_sans_lanceur(self):
        self.refusees(COMMANDES_ILLISIBLES)
        self.assertEqual(refus("echo 'abc"), [npm_guard.ILLISIBLE])


NPX = ("npx", "npx tsc", "npx --yes create-vite x", "npx -p typescript tsc", "cd mothra && npx tsc", "env npx tsc", "/opt/homebrew/bin/npx tsc",
       "echo a | npx tsc", "NPX tsc", "~/.local/state/fnm_multishells/1_2/bin/npx tsc")
GESTIONNAIRES = ("pnpm install", "pnpm add fastify", "pnpx tsc", "pnx tsc", "pn", "pn install", "yarn", "yarn add fastify", "yarnpkg install",
                 "bun", "bun install", "bunx tsc", "corepack enable", "corepack prepare pnpm@latest", "/opt/homebrew/bin/yarn add x",
                 "sudo yarn", "env CI=1 pnpm i", "time bun i", "sh -c 'yarn'", "echo x | xargs yarn", "cd mothra && pnpm install")


class NpxEtGestionnaires(Cas):
    def test_npx_refuse_sous_toutes_ses_formes(self):
        self.refusees(NPX)

    def test_autres_gestionnaires_refuses(self):
        self.refusees(GESTIONNAIRES)

    def test_motif_nomme(self):
        self.assertEqual(refus("npx tsc"), ["npx"])
        self.assertEqual(refus("cd x && yarn add y"), ["yarn"])
        self.assertEqual(refus("npm install; pnpm i"), ["npm install", "pnpm"])

    def test_noms_voisins_non_refuses(self):
        self.permises(("npmrc-check", "echo npx", "ls npx", "git log -- npx", "cat package.json", "nodemon x", "ls yarn"))


NODE_REFUSEES = (
    "node", "node -i", "node --interactive", "node < script.js", "echo 1 | node", "node -", "node - < script.js", "node -e 1", "node -e \"require('pg')\"",
    "node --eval 1", "node --eval=1", "node -p 1", "node --print 1", "node --print=1", "node -pe 1", "node -ep 1", "node -pi", "node --no-warnings -e 1",
    "node --trace-warnings --stack-size=900 -p process.version", "node --input-type=module -e 'import(\"pg\")'", "node --input-type=module --eval x",
    "node --import=data:text/javascript,x", "node --import data:text/javascript,x", "node --require data:x", "node --loader data:x app.js",
    "node --no-warnings", "node --input-type=module", "xargs node", "env node", "env NODE_ENV=test node -e 1", "cd mothra && node -e 1",
    "NODE_OPTIONS=--x node -e 1", "/opt/homebrew/bin/node -e 1", "~/.local/state/fnm_multishells/1_2/bin/node -e 1",
    "$HOME/.local/share/fnm/aliases/default/bin/node -p 1", "nodejs -e 1", "cat a.js | node", "node --eval_",
    # node qui lance npm
    "node /opt/homebrew/bin/npm install", "node /x/lib/node_modules/npm/bin/npm-cli.js install", "node npm-cli.js i", "node -r x /y/npm-cli.js ci",
    "node ~/.local/share/fnm/aliases/default/lib/node_modules/npm/bin/npx-cli.js tsc", "node $(which npm) install", "node $F", "node `which npx` tsc",
    "node /opt/homebrew/bin/npm isntall", "node --no-warnings /opt/homebrew/bin/npm exec tsc",
)
NODE_PERMISES = (
    "node --version", "node -v", "node --help", "node -h", "node -c app.js", "node --check app.js", "node server.js", "node ./dist/server.js",
    "node --test", "node --test tests/", "node --run build", "node --env-file=.env server.js", "node --env-file .env server.js",
    "node --inspect server.js", "node --experimental-strip-types src/index.ts", "node --no-warnings --trace-warnings server.js",
    "node -r ts-node/register server.js", "node -rts-node/register server.js", "node --require=./x.js server.js", "node --require ./x.js server.js",
    "node --import ./hook.mjs app.js", "node --import=./hook.mjs app.js", "node --loader ts-node/esm app.js", "node --conditions=dev app.js",
    "node -C dev app.js", "node app.js -p 3000", "node app.js -e foo", "node app.js --eval x", "node app.js -", "node app.js -i", "node ./scripts/x.js -pe 1",
    "node -- app.js", "cd mothra && node dist/server.js", "env NODE_ENV=test node server.js", "node --max-old-space-size=4096 server.js",
    "node --stack-size=900 server.js", "node /opt/homebrew/lib/node_modules/x/bin/x.js", "node npm-lint.js", "node tools/npmx.js install",
    "node ~/.local/share/fnm/aliases/default/lib/node_modules/npm/bin/npm-cli.js test", "node /x/npm-cli.js --version", "node /opt/homebrew/bin/npm test",
    "node /opt/homebrew/bin/npm run build", "nodemon server.js", "echo node -e 1", 'grep -n "node -e" CLAUDE.md',
)


class FormesNode(Cas):
    def test_formes_refusees(self):
        self.refusees(NODE_REFUSEES)

    def test_formes_permises(self):
        self.permises(NODE_PERMISES)

    def test_motifs_nommes(self):
        self.assertEqual(refus("node -e 1"), ["node -e, -p ou -i (évaluation ou interpréteur)"])
        self.assertEqual(refus("node"), ["node sans fichier (entrée standard ou interpréteur)"])
        self.assertEqual(refus("node /x/npm-cli.js install"), ["npm install"])
        self.assertEqual(refus("node /x/npx-cli.js tsc"), ["npx (par node)"])


COMMANDE_MK_R_138 = r'''cd ~/PMZilla-Lab/workspace && uv run tools/pilot.py freeze --check || exit 0; cd ~/PMZilla-Lab/etapes
mk() { sed -e "s/NOM-fin-de-branche/$1-fin-de-branche/g" -e "s|wt-chore-current-release-kraken\"|$2\"|" -e "s|BRANCHE=\"chore/current-release-kraken\"|BRANCHE=\"$3\"|" -e "s/mktemp -t fin-current-release/mktemp -t fin-$1/" -e "4,6c\\
# $1-fin-de-branche.sh v1, générée le 2026-10-23 ($4 ; reprise de modele-fin-de-branche.sh ; aucun fichier évalué touché : aucun jeu d essai)." modele-fin-de-branche.sh > $1-fin-de-branche.sh; echo "== $1"; ETAPE_A_BLANC=1 /bin/bash $1-fin-de-branche.sh 2>&1 | grep -E "REFUS|code 14|conflit|main avant|essai|code [0-9]"; }
mk r135 wt-fix-dbtest-sous-charge fix/dbtest-sous-charge "R-135, Kraken : test_dbtest.sh isolé du dépôt réel, code de sortie juste"
mk r136 wt-feat-tracabilite-specs feat/tracabilite-specs "R-136, Kraken : lignes Source des specs contrôlées par tests/spec_sources"
cd ~/PMZilla-Lab/workspace'''


class ArgumentDeShellMelantVariableEtTexte(Cas):
    """R-138, règle stricte : l'argument de fichier d'un shell ne contient aucune expansion nue (le découpage peut la couper n'importe
    où), ne commence pas par une expansion sauf suivie de « / », et son dernier composant ne peut valoir stdin, 0, - ni un nombre."""

    def test_entree_standard_refusee(self):
        self.refusees(("bash -", "bash /dev/stdin", "bash <(echo x)", "bash", "bash $1", 'bash "${X}"', "bash $X$Y", "/bin/bash $1",
                       "sh $X", "bash /dev/$X", "bash $X/stdin", 'bash "$A"/dev/stdin', "bash $(echo x)", "zsh $1 $2", 'bash "$@"'))

    def test_expansion_nue_refusee(self):
        self.refusees(("bash $X", "bash $1-x.sh", "bash $1.sh", "bash $D/x.sh", "bash ${=1}-x.sh", "sh ./$1", "bash ./x$1.sh",
                       "bash $1-fin-de-branche.sh", "/bin/bash $1-fin-de-branche.sh", "bash -c 'bash $1-x.sh' _ x", "bash ${=1}"))

    def test_mot_qui_commence_par_une_expansion_refuse(self):
        self.refusees(("bash \"$1\"c 'npm install'", "bash $1s", "bash -- \"$1\"c 'npm install'", 'bash "$A"-', 'bash "$1"s',
                       "bash -$X 'npm install'", "bash \"$1\"", 'bash "$D"x.sh'))

    def test_option_de_shell_non_resolue_avec_c_refusee(self):
        """R-20261111-23 retouche 4 : la forme exacte qu'une garde de session ne juge pas (`-a` caché) est refusée par la garde npm."""
        self.refusees(("bash -$(printf a) -c 'f(){ :; }; ls'",))

    def test_dernier_composant_qui_peut_valoir_stdin_refuse(self):
        self.refusees(('bash ./"$1"', 'bash "$D"/stdin', 'bash "$D"/0', 'bash "$D"/-', 'bash "$D"/63', 'bash "$D/../x.sh"',
                       'bash "$D"/"$E"', 'bash /de"$V"/stdin'))

    def test_fichier_accepte(self):
        self.permises(('bash "$D/x.sh"', '/bin/bash "$D/x.sh"', 'bash "$D/sous/x.sh" a b', "bash x.sh", "bash ./x.sh", "bash ../x.sh",
                       "bash -x x.sh", "bash -c 'echo hi'", "bash --norc x.sh", "bash -xo posix x.sh", "bash -xo posix -c 'echo hi'",
                       "bash -c -x 'echo hi'", "bash -- x.sh", "zsh --emulate sh -c 'echo hi'", "bash /tmp/x/../y.sh"))

    def test_npm_reste_refuse_a_cote(self):
        self.refusees(("bash x.sh; npm install", 'bash "$D/x.sh"; npx tsc'))

    def test_commande_de_la_session_rejouee_a_l_identique_refusee(self):
        # R-138 : la commande de la session lance /bin/bash $1-fin-de-branche.sh, une variable NUE suivie de texte ; le découpage du
        # shell peut la couper n'importe où ($1 = « -c » donnerait un -c-fin-de-branche.sh) : refusée, par choix de l'auteur.
        self.assertEqual(refus(COMMANDE_MK_R_138), ["shell qui lit ses commandes sur l'entrée standard ou par substitution"])


class ContournementsDesShells(Cas):
    """Cinq contournements préexistants d'analyser_interprete (revue de sécurité du 2026-10-23)."""

    def test_groupes_d_options_courtes_avec_o_ou_majuscule(self):
        self.refusees(("bash -xo posix -c 'npm install'", "bash -xO extglob -s", "bash -ox posix -c 'npm install'",
                       "bash -oo a b -c 'npm install'", "bash +o posix -c 'npm install'", "zsh -xo shwordsplit -c 'npm install'"))

    def test_c_suivi_d_une_autre_option(self):
        self.refusees(("bash -c -x 'npm install'", "bash -c -e -x 'npm install'", "bash -ec -x 'npm install'", "sh -c -- 'npm install'"))

    def test_options_longues_avec_valeur(self):
        self.refusees(("zsh --emulate sh -c 'npm install'", "bash --rcfile x.sh -c 'npm install'", "bash --init-file x -c 'npm i'",
                       "bash --option-inconnue x.sh"))

    def test_chemins_non_normalises_ou_a_joker_vers_stdin(self):
        self.refusees(("bash //dev/stdin", "bash /./dev/stdin", "bash /tmp/../dev/stdin", "bash /de[v]/stdin", "bash /dev/./stdin",
                       "bash /proc/../dev/stdin", "bash *.sh", "bash x[1].sh", "bash x?.sh", "bash /de{v,x}/stdin", 'bash "$D"/s*', "bash ///dev/fd/0"))

    def test_ifs_modifie(self):
        self.refusees(("IFS=:; A='-c:npm install;'; bash $A-x.sh", "IFS=:; A=x.sh; bash $A", "IFS=: bash $A", "export IFS=:; bash $A",
                       "IFS=:; A='-c:npm install;'; $A"))

    def test_sans_ifs_une_valeur_connue_se_lit_comme_le_shell(self):
        self.refusees(("A='-c'; bash $A 'npm install'",))
        self.permises(("A=x.sh; bash $A", "A='-x x.sh'; bash $A"))


class ContournementsDeLaRevueR138(Cas):
    """R-138, suite de la revue de sécurité : un test par contournement, écrit avant la correction."""

    def test_point1_help_ou_version_apres_la_chaine_de_c(self):
        self.refusees(("bash -c 'npm install' --help", "bash -c 'npm install' --version", "sh -c 'npm install' x --help"))
        self.permises(("bash --version", "bash --help", "zsh --version"))

    def test_point2_formes_zsh_dollar_egal_tilde_accent_plus(self):
        self.refusees(("N=npm; $=N install", "bash $=X-x.sh", "N=npm; $~N install", "N=npm; $^N install", "N=npm; $+N install",
                       "bash $~X-x.sh", "bash $^X-x.sh", "bash $+X-x.sh"))

    def test_point3_chemin_litteral_vers_stdin(self):
        self.refusees(("echo 'npm install' | bash ../../../../../../../../dev/stdin", "cd / && bash dev/stdin", "cd /dev && bash fd/0",
                       "bash 0", "bash fd/63", "bash ../../dev/stdin"))
        self.permises(("bash ../x.sh", "bash tools/x.sh", "bash x/y.sh"))

    def test_point4_ifs_affecte_autrement_que_par_ifs_egal(self):
        self.refusees(("bash -c 'for IFS in x; do A=\"-cxnpm install;\"; bash $A-y.sh; done'",
                       "for IFS in :; do A='-c:npm install;'; bash $A-y.sh; done",
                       "read IFS <<< ':'; A='-c:npm install;'; bash $A-y.sh",
                       "printf -v IFS ':'; A='-c:npm install;'; bash $A-y.sh",
                       "A=x; echo ${IFS:=:}; bash $A-y.sh", "A=x; echo ${IFS::=:}; bash $A-y.sh",
                       "read 'IFS'; A=x.sh; bash $A", 'printf -v "IFS" :; A=x.sh; bash $A'))

    def test_point5_variable_benigne_reaffectee_dans_l_argument_du_shell(self):
        self.refusees(("for TMPDIR in /dev/stdin; do echo 'npm install' | bash \"$TMPDIR\"; done", 'bash "$HOME"', "bash $HOME/x.sh",
                       'bash "$TMPDIR"', "bash $PWD", 'bash "$PWD"/stdin', "TMPDIR=/dev/stdin; echo 'npm install' | bash \"$TMPDIR\"",
                       "for HOME in /dev/stdin; do bash \"$HOME\"; done"))
        self.permises(('bash "$HOME/x.sh"', 'bash "$TMPDIR/x.sh"', '"$CLAUDE_PROJECT_DIR/tools/x.sh"',
                       'bash "$CLAUDE_PROJECT_DIR/tools/x.sh"'))

    def test_point7_fish_csh_tcsh_refuses(self):
        self.refusees(("fish -C 'npm install' x.fish", "fish x.fish", "csh x.csh", "tcsh -c 'npm install'", "/opt/homebrew/bin/fish x.fish",
                       "env fish x.fish", "fish --version"))

    def test_faux_positifs_toujours_acceptes(self):
        self.permises(("bash tools/x.sh", "bash tests/run_all.sh --staged", "/bin/bash ~/PMZilla-Lab/scripts/fin-de-branche.sh",
                       "zsh ~/PMZilla-Lab/watch.sh", "bash -o pipefail -c 'echo ok'", "bash --noprofile --norc -c 'echo ok'",
                       '"$CLAUDE_PROJECT_DIR/tools/x.sh"', "bash ../x.sh", 'bash "$HOME/x.sh"'))


class MatriceDeLaSuiteSettingsDeny(unittest.TestCase):
    """La matrice de tests/settings_deny/test_settings_deny_npm.py : tout ce que les règles deny refusent, le crochet le refuse ;
    tout ce que les règles laissent permis (PERMISES) reste permis ; les limites déclarées (LIMITES) sont toutes refusées."""

    def test_chaque_forme_refusee_par_les_regles_l_est_par_le_crochet(self):
        non_refusees = [c for c in regles_deny.refusees() if not refus(c)]
        self.assertEqual(non_refusees[:10], [], f"{len(non_refusees)} commande(s) permise(s) à tort")

    def test_les_commandes_permises_aujourd_hui_le_restent(self):
        """Sauf npm explain et npm why : hors de la liste de mothra/CLAUDE.md, le crochet les refuse (les règles deny, elles, les laissent)."""
        hors_liste = {"npm explain fastify", "npm why fastify"}
        refusees = [c for c in regles_deny.PERMISES if refus(c) and c not in hors_liste]
        self.assertEqual(refusees, [])
        self.assertEqual([c for c in sorted(hors_liste) if not refus(c)], [])

    def test_les_limites_declarees_sont_couvertes(self):
        permises = [c for c in regles_deny.LIMITES if not refus(c)]
        self.assertEqual(permises, [], "limites déclarées que le crochet laisse passer")

    def test_la_matrice_est_assez_large(self):
        self.assertGreater(len(list(regles_deny.refusees())), 800)


class RevueDeSecurite(Cas):
    """Points de la revue de sécurité de R-133 : refuser dans le doute, et ce que la première version laissait passer."""

    def test_1_commande_illisible_refusee_meme_sans_lanceur(self):
        self.refusees(COMMANDES_ILLISIBLES)

    def test_1_mille_niveaux_apres_une_ligne_refusee(self):
        for imbrication in ("$(", '"$(', "${", "(", "`", "$((", '"${'):
            with self.subTest(imbrication=imbrication):
                self.assertTrue(refus("n''pm install\n" + imbrication * 1000))
                if imbrication != "`":   # mille barres obliques inverses en nombre pair se ferment deux à deux
                    self.assertTrue(refus("echo ok\n" + imbrication * 1000))
        fermees = "echo " + "$(" * 1000 + "x" + ")" * 1000
        self.assertTrue(refus(fermees))
        self.assertTrue(refus("echo " + '"$(' * 1000 + "x" + ')"' * 1000))
        self.assertTrue(refus("echo " + "${a:-" * 1000 + "x" + "}" * 1000))

    def test_1_bornes_sur_les_options_et_les_parentheses(self):
        self.assertTrue(refus("npm " + "--foo " * 1000 + "install"))
        self.assertTrue(refus("npm " + "--foo bar " * 1000 + "ls"))
        self.assertTrue(refus("node " + "--foo " * 1000 + "-e 1"))
        self.assertTrue(refus("(" * 5000 + "npm install" + ")" * 5000))
        self.assertTrue(refus("echo " + "(" * 5000))
        self.assertTrue(refus("npm " + "-g " * 3000 + "install"))

    def test_1_analyse_en_echec_refuse(self):
        original = npm_guard.analyser_script
        try:
            npm_guard.analyser_script = lambda *a, **k: 1 / 0
            self.assertEqual(refus("ls"), ["analyse impossible"])
        finally:
            npm_guard.analyser_script = original

    def test_2a_option_booleenne_suivie_de_true_false_always(self):
        self.refusees(OPTIONS_BOOLEENNES_REFUSEES)
        self.assertEqual(refus("npm --global true install"), ["npm install"])

    def test_2b_options_qui_lancent_un_programme_et_configuration_par_variable(self):
        self.refusees(OPTIONS_QUI_LANCENT_REFUSEES)
        self.permises(("npm --global test", "npm --global true ls", "npm --loglevel silent test", "npm --silent test", "npm --user-agent=x test", "npm run x -- --shell",
                       "npm run x -- --editor", "NODE_ENV=test npm test", "npm_lifecycle=1 ls"))

    def test_2c_option_node_inconnue_ne_cache_pas_une_evaluation(self):
        self.refusees(NODE_OPTIONS_INCONNUES)
        self.permises(("node --inspect server.js", "node --trace-warnings server.js", "node --no-warnings server.js",
                       "node --experimental-strip-types x.ts", "node --env-file .env server.js", "node --foo server.js",
                       "node --foo bar.js"))

    def test_2d_arithmetique_et_documents_ici(self):
        self.refusees(DOCUMENTS_ICI_ET_ARITHMETIQUE_REFUSES)
        self.permises(DOCUMENTS_ICI_ET_ARITHMETIQUE_PERMIS)

    def test_2e_env_lettres_groupees(self):
        self.refusees(ENV_AVEC_LETTRES_GROUPEES)
        self.permises(("env -iS 'npm test'", "env -i ls", "env -iu X ls"))

    def test_3_liste_de_mothra_seulement(self):
        self.refusees(FORMES_NPM_HORS_LISTE)
        self.permises(("npm test", "npm run build", "npm start", "npm ls", "npm view x", "npm outdated", "npm audit", "npm help",
                       "npm config get x", "npm --version"))

    def test_3_les_lectures_non_sures_n_ajoutent_pas_de_faux_refus(self):
        """Une option inconnue donne deux lectures ; celle qui lui fait prendre une valeur ne refuse qu'une vraie commande hors liste."""
        self.permises(("npm --foo run build", "npm --foo test", "npm --foo=1 test", "npm -x run build"))
        self.refusees(("npm --foo bar", "npm --foo ls install", "npm --foo x install", "npm -x install"))

    def test_4_entrees_standard_et_substitutions(self):
        self.refusees(ENTREES_STANDARD_REFUSEES)
        self.permises(("bash script.sh", "bash ./tools/x.sh a b", "sh -n x.sh", "node ./dev.js", "source ./x.sh", "bash --version"))

    def test_4_substitutions_dans_les_accolades(self):
        self.refusees(SUBSTITUTIONS_DANS_ACCOLADES_REFUSEES)

    def test_4_function_trap_coproc_zsh(self):
        self.refusees(FORMES_SHELL_REFUSEES)
        self.permises(FORMES_SHELL_PERMISES)

    def test_4_script_su_gtimeout_sandbox_tmux_screen(self):
        self.refusees(LANCEURS_SUPPLEMENTAIRES_REFUSES)
        self.permises(LANCEURS_SUPPLEMENTAIRES_PERMIS)

    def test_4_shell_n_est_plus_benin(self):
        self.assertTrue(refus("$SHELL -c 'npm install'"))
        self.assertTrue(refus("${SHELL} -c 'ls'"))
        self.assertEqual(refus("echo $SHELL"), [])


class CrochetPreToolUse(unittest.TestCase):
    """Le script comme Claude Code le lance : le JSON du hook sur l'entrée standard, code 2 et message sur la sortie d'erreur pour un refus."""

    def test_refus_code_2_message_sur_stderr(self):
        r = lancer(bash("npm isntall fastify"))
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")
        self.assertIn("garde npm : refusé : npm install (écrit « isntall »)", r.stderr)
        self.assertIn("Permis : npm test", r.stderr)

    def test_permis_code_0_aucune_sortie(self):
        for commande in ("npm test", "cd mothra && npm run build", "node server.js", "ls | grep x", "git status"):
            with self.subTest(commande=commande):
                r = lancer(bash(commande))
                self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))

    def test_le_message_ne_reprend_pas_la_commande(self):
        r = lancer(bash("npm install SECRET_ARG_12345 --token=SECRET_TOKEN_67890"))
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("SECRET", r.stderr)

    def test_plusieurs_formes_dans_le_message(self):
        r = lancer(bash("npm install && npx tsc && node -e 1"))
        self.assertEqual(r.returncode, 2)
        for forme in ("npm install", "npx", "node -e, -p ou -i"):
            self.assertIn(forme, r.stderr)

    def test_autre_outil_que_bash(self):
        for entree in ({"tool_name": "Read", "tool_input": {"file_path": "npm install"}},
                       {"tool_name": "Edit", "tool_input": {"command": "npm install"}}):
            self.assertEqual(lancer(entree).returncode, 0)

    def test_entrees_illisibles_ou_incompletes(self):
        # R-20261107-30 point 7 (échec fermé) : une entrée illisible ou une commande Bash sans chaîne est refusée (2) ; un autre outil et une
        # commande vide restent à 0.
        for brut in ("", "pas du json", "[]", "{}", '{"tool_name": "Bash"}', '{"tool_name": "Bash", "tool_input": 3}',
                     '{"tool_name": "Bash", "tool_input": {"command": 3}}'):
            with self.subTest(brut=brut, attendu="refus"):
                r = lancer(brut, brut=True)
                self.assertEqual((r.returncode, r.stdout), (2, ""))
                self.assertIn("entrée illisible", r.stderr)
        for brut in ('{"tool_name": "Bash", "tool_input": {"command": ""}}', '{"tool_name": "Read", "tool_input": 3}'):
            with self.subTest(brut=brut, attendu="passe"):
                r = lancer(brut, brut=True)
                self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))

    def test_entree_standard_non_decodable_refuse_sans_trace(self):
        r = subprocess.run([sys.executable, str(OUTIL)], input=b"\xff\xfe\x80", capture_output=True, timeout=30)
        self.assertEqual(r.returncode, 2)
        self.assertNotIn(b"Traceback", r.stderr)

    def test_commande_sur_plusieurs_lignes(self):
        self.assertEqual(lancer(bash("echo début\nnpm ci\necho fin")).returncode, 2)

    def test_main_en_processus(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(npm_guard.main([], json.dumps(bash("npm update"))), 2)
        self.assertEqual(npm_guard.main([], json.dumps(bash("npm ls"))), 0)

    def test_toute_exception_de_l_analyse_refuse(self):
        original = npm_guard.refus_de
        try:
            for erreur in (ZeroDivisionError, RecursionError, MemoryError, KeyError):
                def en_echec(commande, erreur=erreur):
                    raise erreur()
                npm_guard.refus_de = en_echec
                for commande in ("ls", "npm install", "echo bonjour"):
                    with self.subTest(erreur=erreur.__name__, commande=commande):
                        sortie = io.StringIO()
                        with contextlib.redirect_stderr(sortie):
                            self.assertEqual(npm_guard.main([], json.dumps(bash(commande))), 2)
                        self.assertIn("analyse impossible", sortie.getvalue())
        finally:
            npm_guard.refus_de = original

    def test_json_trop_profond_refuse(self):
        profond = "[" * 100000 + "]" * 100000
        r = lancer(profond, brut=True)
        self.assertIn(r.returncode, (0, 2))
        self.assertNotIn("Traceback", r.stderr)
        r = lancer('{"tool_name": "Bash", "tool_input": {"command": "ls"}, "x": ' + profond + "}", brut=True)
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("Traceback", r.stderr)

    def test_commande_illisible_code_2(self):
        for commande in ("echo 'abc", 'echo "abc', "echo $(abc"):
            with self.subTest(commande=commande):
                r = lancer(bash(commande))
                self.assertEqual(r.returncode, 2)
                self.assertIn("commande illisible", r.stderr)


class Sobriete(unittest.TestCase):
    """Le script ne lance rien, n'écrit rien et n'importe que la bibliothèque standard."""

    def test_source(self):
        source = OUTIL.read_text(encoding="utf-8")
        for interdit in ("subprocess", "os.system", "os.popen", " open(", "write_text", "import socket", "urllib", "import requests",
                         "import yaml"):
            self.assertNotIn(interdit, source, interdit)
        self.assertTrue(source.startswith("#!/usr/bin/env python3\n"))

    def test_table_de_npm_figee(self):
        """La table de l'outil est comparée à la copie figée de ce fichier (les 72 commandes et les alias de npm 11, lib/utils/cmd-list.js) :
        la suite ne lit pas le npm installé ; changer la table de l'outil sans relire cmd-list.js et sans mettre cette copie à jour échoue."""
        self.assertEqual(npm_guard.COMMANDES_NPM, COMMANDES_NPM_11)
        self.assertEqual(npm_guard.ALIAS_NPM, ALIAS_NPM_11)
        self.assertEqual(len(COMMANDES_NPM_11), 72)
        self.assertEqual(list(COMMANDES_NPM_11), sorted(COMMANDES_NPM_11))
        for cible in ALIAS_NPM_11.values():
            self.assertIn(cible, COMMANDES_NPM_11)

    def test_liste_des_commandes_permises_figee(self):
        self.assertEqual(npm_guard.PERMISES_NPM, {"run", "test", "start", "ls", "view", "outdated", "audit", "help", "config"})


if __name__ == "__main__":
    unittest.main()
