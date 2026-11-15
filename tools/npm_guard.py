#!/usr/bin/env python3
"""PMZilla Lab : garde npm (idée 434, change mothra-session-guards, condition de la tranche 0 de Mothra).

Hook Claude Code PreToolUse des appels Bash : refuse toute commande qui lancerait npm, npx ou node d'une manière interdite aux
sessions (mothra/CLAUDE.md, « What a session never does »), en la résolvant comme npm lui-même (table d'alias et abréviations
uniques de npm 11, écritures camelCase) et en suivant les lanceurs (env, sudo, timeout, xargs, find -exec, sh -c, eval, fnm exec,
uv run, su -c, script, tmux, sous-shells, substitutions, listes de commandes). Une session garde npm test, npm run, npm start,
npm ls, view, outdated, audit sans fix, help, config get, --version et node <fichier>. Dans le doute, la commande est refusée :
commande illisible, analyse en échec, sous-commande npm inconnue ou hors de cette liste, nom de commande non résolu.

    python3 tools/npm_guard.py   refusé : message sur la sortie d'erreur, code 2 (Claude Code bloque l'appel)

Une seule exception (change npm-ci-session, R-20261031-53) : `npm ci` sans option, sous la forme « npm ci » ou « cd <dossier> && npm ci », dans
le dossier mothra d'un worktree de branche, quand les conditions de R-20261030-11 (a) tiennent (tools/npm_ci_conditions.py, importé pour
cette commande seule) : package.json, package-lock.json et .npmrc de mothra/ identiques à origin/main, arbre propre, aucune fin en cours.
Elle remplace deux règles deny et les gestes de l'auteur sur les worktrees neufs, et tombe avec le changement qui donne un node_modules à
un worktree sans npm ci de la session (design D11). Refusé avec une ligne propre à `npm ci`, qui nomme les conditions en échec.

Entrée : le JSON du hook sur l'entrée standard (champ cwd compris). Entrée illisible (ou entrée standard non lisible) ou commande Bash sans
chaîne : code 2 (« entrée illisible »). Autre outil que Bash, commande vide : code 0, aucune sortie. Toute exception de l'analyse : code 2. Bibliothèque standard seulement ; ne lit que l'entrée standard, n'écrit aucun fichier,
n'imprime que les formes refusées (jamais la commande entière). Hors le cas de `npm ci`, ne lance aucune commande ; pour `npm ci`, le module
des conditions lance seulement des lectures de Git (aucun fetch, aucune écriture, ni npm ni node). Limites : un programme écrit dans un fichier puis
lancé, un autre langage qui lance npm (osascript, awk, perl, python -c, alias git, make -f -), un alias ou une fonction du shell de
l'auteur ne sont pas examinés ; pour `npm ci`, les limites de D12 (configuration npm de l'utilisateur, Node, origin/main plus ancien que main).
"""
import json
import os
import re
import sys

# Sous `python3 -I` (lancement par chemin absolu, change session-guard-n1, D2), Python n'ajoute pas le dossier du script à sys.path : le dossier de ce
# fichier, liens suivis, passe en tête avant tout import d'un module voisin (npm_ci_conditions). Jamais le dossier courant. Remplace : le lancement par
# la variable du dossier du projet, qui exécutait la copie du worktree. Retrait : permanent.
_DOSSIER = os.path.dirname(os.path.realpath(__file__))
if sys.path[:1] != [_DOSSIER]:
    sys.path.insert(0, _DOSSIER)

VAR_DEB, VAR_FIN, INCONNU, VARQ_DEB = "\x01", "\x02", "\x03", "\x04"   # variable nue, fin, valeur inconnue, variable entre guillemets
BENIGNE_NUE, BENIGNE_QUOTEE = "\x06", "\x07"   # précèdent « /x », valeur d'une variable jugée bénigne (HOME…), nue ou entre guillemets
QUOTE = "\x05"   # suit INCONNU quand l'expansion était entre guillemets (pas de découpage) ; INCONNU seul : expansion nue
PROFONDEUR_MAX = 8
PROFONDEUR_SYNTAXE = 40
LECTURES_MAX = 256

# --- Table de npm 11 (lib/utils/cmd-list.js du npm installé) ---------------------------------------------------------------------------

COMMANDES_NPM = (
    "access", "adduser", "approve-scripts", "audit", "bugs", "cache", "ci", "completion", "config", "dedupe", "deny-scripts",
    "deprecate", "diff", "dist-tag", "docs", "doctor", "edit", "exec", "explain", "explore", "find-dupes", "fund", "get", "help",
    "help-search", "init", "install", "install-ci-test", "install-scripts", "install-test", "link", "ll", "login", "logout", "ls",
    "org", "outdated", "owner", "pack", "ping", "pkg", "prefix", "profile", "prune", "publish", "query", "rebuild", "repo",
    "restart", "root", "run", "sbom", "search", "set", "shrinkwrap", "stage", "star", "stars", "start", "stop", "team", "test",
    "token", "trust", "undeprecate", "uninstall", "unpublish", "unstar", "update", "version", "view", "whoami",
)
ALIAS_NPM = {
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
MOTS_NPM = set(COMMANDES_NPM) | set(ALIAS_NPM)

# Commandes npm qu'une session lance (mothra/CLAUDE.md, « Commands a session runs ») : toute autre commande, inconnue ou ambiguë
# comprise, est refusée.
PERMISES_NPM = {"run", "test", "start", "ls", "view", "outdated", "audit", "help", "config"}
MOTS_CONFIG_REFUSES = {"set", "delete", "rm", "edit", "fix", "list", "ls"}

OPTIONS_NPM_AVEC_VALEUR = {
    "prefix", "workspace", "loglevel", "registry", "cache", "tag", "otp", "omit", "include", "scope",
    "location", "before", "depth", "tmp", "cafile", "ca", "cert", "key", "proxy", "https-proxy", "noproxy",
    "local-address", "user-agent", "fetch-retries", "fetch-retry-factor", "fetch-retry-mintimeout", "fetch-retry-maxtimeout",
    "fetch-timeout", "maxsockets", "access", "audit-level", "auth-type", "call", "package", "lockfile-version", "logs-dir",
    "logs-max", "npm-version", "save-prefix", "searchlimit", "searchopts", "searchexclude", "searchstaleness",
    "tag-version-prefix", "install-strategy", "min-release-age", "format", "cidr", "umask",
    "message", "init-author-name", "init-author-email", "init-author-url", "init-license", "init-module", "init-version", "diff",
    "diff-unified", "diff-src-prefix", "diff-dst-prefix", "allow-git", "replace-registry-host", "pack-destination",
}
# Options qui font lancer un programme par npm : refusées, noms entiers ou abrégés (nopt accepte les préfixes uniques).
OPTIONS_NPM_QUI_LANCENT = ("browser", "viewer", "editor", "script-shell", "shell", "node-options", "userconfig", "globalconfig")
OPTIONS_NPM_BOOLEENNES = {
    "json", "long", "parseable", "global", "dry-run", "offline", "silent", "all", "workspaces", "include-workspace-root",
    "if-present", "production", "ignore-scripts", "audit", "fund", "progress", "color", "force", "yes", "quiet", "verbose", "help",
    "version", "save", "save-dev", "save-optional", "save-exact", "save-peer", "save-bundle", "legacy-peer-deps",
    "strict-peer-deps", "package-lock", "package-lock-only", "prefer-offline", "prefer-online", "global-style",
    "foreground-scripts", "unicode", "update-notifier", "dd", "ddd", "timing", "engine-strict", "no-audit", "no-fund",
}
VALEURS_BOOLEENNES = ("true", "false", "always")   # nopt : une option booléenne ou mixte (color) les prend pour valeur
COURTES_NPM_BOOLEENNES = set("gDSEOBqsdvlpyfhnaLUV?")
COURTES_NPM_AVEC_VALEUR = set("wcm")

GESTIONNAIRES = {"pnpm", "pnpx", "pnx", "pn", "yarn", "yarnpkg", "bun", "bunx", "corepack"}
INTERPRETES = {"sh", "bash", "zsh", "dash", "ksh", "ash"}
SHELLS_REFUSES = {"fish", "csh", "tcsh"}   # non analysés (aucune session ne les utilise) : refusés entièrement
FICHIERS_NPM = {"npm", "npx", "npm-cli.js", "npx-cli.js", "npm-cli", "npx-cli"}
MOTS_RESERVES = {"if", "then", "else", "elif", "fi", "do", "done", "while", "until", "!", "{", "}", "esac", "in", "always"}
SANS_COMMANDE = {"for", "select", "case"}
LANCEURS_SIMPLES = {   # lanceur : options qui prennent une valeur séparée
    "time": set(), "nohup": set(), "exec": {"-a"}, "setsid": set(), "unbuffer": set(), "nice": {"-n"}, "ionice": {"-c", "-n"},
    "sudo": {"-u", "-g", "-h", "-p", "-C", "-D", "-r", "-t", "-T", "-U", "-R"}, "doas": {"-u", "-C"}, "caffeinate": {"-t", "-w"},
    "stdbuf": {"-i", "-o", "-e"}, "arch": {"-arch"}, "chronic": set(), "noglob": set(), "nocorrect": set(),
}
OPTIONS_NODE_AVEC_VALEUR = {
    "conditions", "env-file", "title", "test-name-pattern", "test-reporter", "test-reporter-destination", "inspect-port",
    "disable-warning", "watch-path", "input-type", "stack-trace-limit", "redirect-warnings", "diagnostic-dir", "report-dir",
    "openssl-config", "icu-data-dir", "run", "trace-event-categories", "trace-event-file-pattern", "experimental-sea-config",
}
OPTIONS_NODE_SANS_VALEUR = {
    "inspect", "inspect-brk", "inspect-wait", "test", "watch", "watch-preserve-output", "check", "version", "help",
    "abort-on-uncaught-exception", "harmony", "deprecation", "warnings", "frozen-intrinsics", "jitless", "zero-fill-buffers",
    "verify-base-objects", "force-context-aware", "insecure-http-parser", "openssl-legacy-provider", "napi-modules", "prof",
    "prof-process", "use-strict", "build-snapshot", "v8-options", "completion-bash", "enable-source-maps", "trace-warnings",
    "trace-deprecation", "trace-uncaught", "trace-sigint", "trace-sync-io", "trace-exit", "trace-tls", "trace-env",
    "trace-require-module", "pending-deprecation", "throw-deprecation", "expose-gc", "preserve-symlinks",
}
PREFIXES_NODE_SANS_VALEUR = ("no-", "experimental-")
OPTIONS_NODE_SANS_SCRIPT = {"version", "help", "check", "test", "run", "v8-options", "completion-bash", "build-snapshot"}
ENTREES_STANDARD = ("/dev/", "/proc/")   # un programme lu sur /dev/stdin, /dev/fd/N, /proc/self/fd/N
BENIGNES = {"HOME", "PWD", "OLDPWD", "TMPDIR", "CLAUDE_PROJECT_DIR", "USER", "PATH", "TMP", "TEMP"}

AFFECTATION = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\+?=")
NOM_VARIABLE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
OPERATEURS_DOUBLES = {"&&", "||", "|&", ";;", ";&", ">>", ">&", "<&", "&>", "<<", "<>", ">|"}
MOTS_SUSPECTS = re.compile(r"(?<![A-Za-z0-9_-])(npm|npx|node|nodejs|pnpm|pnpx|pnx|yarn|yarnpkg|bun|bunx|corepack)(?![A-Za-z0-9_-])", re.I)
ILLISIBLE = "commande illisible (guillemet, parenthèse ou accolade non fermé, ou imbrication excessive)"


_RAPPEL = None   # rappel de la garde de session (voir `lancer`) ; None : comportement d'origine


def _poser_rappel(rappel):
    global _RAPPEL
    _RAPPEL = rappel


def avec_rappel(commande: str, rappel) -> list:
    """Analyse `commande` comme `refus_de`, en passant chaque commande simple, affectation et liste de jetons au rappel (garde de session,
    change session-guard-n1, D1). Rend les motifs de refus de la lecture npm ; une analyse en échec y laisse ses motifs
    (« commande illisible… », « commande trop imbriquée », « analyse impossible »). Remplace : rien. Retrait : permanent."""
    refus = []
    _poser_rappel(rappel)
    try:
        analyser_script(commande, {}, 0, refus)
    except Exception:   # RecursionError comprise : dans le doute, analyse en échec
        refus.append("analyse impossible")
    finally:
        _poser_rappel(None)
    return refus


class Syntaxe(Exception):
    """Commande que le shell lui-même refuserait, ou imbriquée au-delà de la borne : refusée dans le doute."""


# --- Lecture du shell -------------------------------------------------------------------------------------------------------------------

def _fin_backtick(t: str, i: int) -> int:
    while i < len(t):
        if t[i] == "\\":
            i += 2
        elif t[i] == "`":
            return i
        else:
            i += 1
    raise Syntaxe


def _passer_guillemets(t: str, i: int, prof: int) -> int:
    """Index qui suit le guillemet fermant ; i est l'index qui suit le guillemet ouvrant."""
    n = len(t)
    while i < n and t[i] != '"':
        c = t[i]
        if c == "\\":
            i += 2
        elif c == "$" and t[i + 1:i + 2] == "(":
            i = _fin_substitution(t, i + 2, prof + 1) + 1
        elif c == "$" and t[i + 1:i + 2] == "{":
            i = _fin_accolade(t, i + 2, prof + 1) + 1
        elif c == "`":
            i = _fin_backtick(t, i + 1) + 1
        else:
            i += 1
    if i >= n:
        raise Syntaxe
    return i + 1


def _fin_substitution(t: str, i: int, prof: int = 0) -> int:
    """Index de la parenthèse qui ferme une substitution ouverte juste avant l'index i."""
    if prof > PROFONDEUR_SYNTAXE:
        raise Syntaxe
    ouvertes, n = 1, len(t)
    while i < n:
        c = t[i]
        if c == "\\":
            i += 2
            continue
        if c == "'":
            j = t.find("'", i + 1)
            if j < 0:
                raise Syntaxe
            i = j + 1
            continue
        if c == '"':
            i = _passer_guillemets(t, i + 1, prof)
            continue
        if c == "`":
            i = _fin_backtick(t, i + 1) + 1
            continue
        if c == "(":
            ouvertes += 1
        elif c == ")":
            ouvertes -= 1
            if ouvertes == 0:
                return i
        i += 1
    raise Syntaxe


def _fin_accolade(t: str, i: int, prof: int = 0) -> int:
    """Index de l'accolade qui ferme ${ ouvert juste avant l'index i."""
    if prof > PROFONDEUR_SYNTAXE:
        raise Syntaxe
    n = len(t)
    while i < n:
        c = t[i]
        if c == "\\":
            i += 2
        elif c == "'":
            j = t.find("'", i + 1)
            if j < 0:
                raise Syntaxe
            i = j + 1
        elif c == '"':
            i = _passer_guillemets(t, i + 1, prof)
        elif c == "$" and t[i + 1:i + 2] == "(":
            i = _fin_substitution(t, i + 2, prof + 1) + 1
        elif c == "$" and t[i + 1:i + 2] == "{":
            i = _fin_accolade(t, i + 2, prof + 1) + 1
        elif c == "`":
            i = _fin_backtick(t, i + 1) + 1
        elif c == "}":
            return i
        else:
            i += 1
    raise Syntaxe


def _substitutions_du_texte(t: str, subs: list, prof: int = 0):
    """Ajoute à subs les substitutions $( ), `…` et celles des ${…} d'un texte qui ne se découpe pas en mots (corps de here-document,
    contenu d'une expression arithmétique ou d'un ${…})."""
    if prof > PROFONDEUR_SYNTAXE:
        raise Syntaxe
    i, n = 0, len(t)
    while i < n:
        c = t[i]
        if c == "\\":
            i += 2
        elif c == "$" and t[i + 1:i + 2] == "(":
            j = _fin_substitution(t, i + 2, prof + 1)
            subs.append(t[i + 2:j])
            i = j + 1
        elif c == "$" and t[i + 1:i + 2] == "{":
            j = _fin_accolade(t, i + 2, prof + 1)
            _substitutions_du_texte(t[i + 2:j], subs, prof + 1)
            i = j + 1
        elif c == "`":
            j = _fin_backtick(t, i + 1)
            subs.append(t[i + 1:j].replace("\\`", "`"))
            i = j + 1
        else:
            i += 1


def _arithmetique(contenu: str, subs: list):
    """Expression arithmétique : seules ses substitutions s'exécutent ; un nom de lanceur dedans fait analyser le tout."""
    _substitutions_du_texte(contenu, subs)
    if MOTS_SUSPECTS.search(contenu):
        subs.append(contenu)


def _ansi(t: str, i: int, mot: list) -> int:
    """$'...' : décode les échappements courants ; i est l'index qui suit l'apostrophe ouvrante."""
    n = len(t)
    while i < n and t[i] != "'":
        if t[i] == "\\" and i + 1 < n:
            suivant = t[i + 1]
            if suivant == "x" and re.match(r"[0-9a-fA-F]{1,2}", t[i + 2:i + 4]):
                chiffres = re.match(r"[0-9a-fA-F]{1,2}", t[i + 2:i + 4]).group()
                mot.append(chr(int(chiffres, 16)))
                i += 2 + len(chiffres)
            elif suivant in "01234567":
                chiffres = re.match(r"[0-7]{1,3}", t[i + 1:i + 4]).group()
                mot.append(chr(int(chiffres, 8)))
                i += 1 + len(chiffres)
            elif suivant == "u" and re.match(r"[0-9a-fA-F]{1,4}", t[i + 2:i + 6]):
                chiffres = re.match(r"[0-9a-fA-F]{1,4}", t[i + 2:i + 6]).group()
                mot.append(chr(int(chiffres, 16)))
                i += 2 + len(chiffres)
            else:
                mot.append({"n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b", "e": "\x1b"}.get(suivant, suivant))
                i += 2
        else:
            mot.append(t[i])
            i += 1
    if i >= n:
        raise Syntaxe
    return i + 1


def _guillemets(t: str, i: int, mot: list, subs: list) -> int:
    """Texte entre guillemets doubles ; i est l'index qui suit le guillemet ouvrant."""
    n = len(t)
    while i < n:
        c = t[i]
        if c == '"':
            return i + 1
        if c == "\\" and i + 1 < n:
            suivant = t[i + 1]
            if suivant == "\n":
                i += 2
            elif suivant in '$`"\\':
                mot.append(suivant)
                i += 2
            else:
                mot.append("\\")
                i += 1
        elif c == "$":
            i = _dollar(t, i, mot, subs, True)
        elif c == "`":
            j = _fin_backtick(t, i + 1)
            subs.append(t[i + 1:j].replace("\\`", "`"))
            mot.append(INCONNU + QUOTE)
            i = j + 1
        else:
            mot.append(c)
            i += 1
    raise Syntaxe


def _dollar(t: str, i: int, mot: list, subs: list, entre_guillemets: bool) -> int:
    n = len(t)
    suivant = t[i + 1] if i + 1 < n else ""
    inconnu = INCONNU + QUOTE if entre_guillemets else INCONNU
    if suivant == "(":
        j = _fin_substitution(t, i + 2)
        if t[i + 2:i + 3] == "(":   # $(( … )) : expression arithmétique
            _arithmetique(t[i + 2:j], subs)
        else:
            subs.append(t[i + 2:j])
        mot.append(inconnu)
        return j + 1
    if suivant == "{":
        j = _fin_accolade(t, i + 2)
        nom = t[i + 2:j]
        _substitutions_du_texte(nom, subs)
        debut = VARQ_DEB if entre_guillemets else VAR_DEB
        if NOM_VARIABLE.fullmatch(nom):
            mot.append(f"{debut}{nom}{VAR_FIN}")
        else:   # ${IFS:=…} affecte IFS : le nom reste dans le mot pour que analyser_segment le voie
            mot.append(inconnu + ("IFS" if "IFS" in nom else ""))
        return j + 1
    if suivant == "'" and not entre_guillemets:
        return _ansi(t, i + 2, mot)
    if suivant == '"' and not entre_guillemets:
        return _guillemets(t, i + 2, mot, subs)
    m = NOM_VARIABLE.match(t, i + 1)
    if m:
        mot.append(f"{VARQ_DEB if entre_guillemets else VAR_DEB}{m.group()}{VAR_FIN}")
        return m.end()
    if suivant and suivant in "=~^+":   # zsh : $=X, $~X, $^X, $+X (découpage, globbing, tableau, test) : expansion inconnue
        m = NOM_VARIABLE.match(t, i + 2)
        if m:
            mot.append(inconnu)
            return m.end()
    if suivant and (suivant.isdigit() or suivant in "@*#?$!-"):
        mot.append(inconnu)
        return i + 2
    mot.append("$")
    return i + 1


def _sauter_documents_ici(t: str, i: int, attendus: list, subs: list) -> int:
    """Saute les corps des here-documents en attente ; leurs substitutions $( ) et `…` s'exécutent : elles vont dans subs."""
    n = len(t)
    for delimiteur, tabulations in attendus:
        corps = []
        while i < n:
            j = t.find("\n", i)
            ligne = t[i:j] if j >= 0 else t[i:]
            i = j + 1 if j >= 0 else n
            if (ligne.lstrip("\t") if tabulations else ligne) == delimiteur:
                break
            corps.append(ligne)
        _substitutions_du_texte("\n".join(corps), subs)
    return i


def decouper(t: str, subs: list) -> list:
    """Jetons (genre, texte) : « w » un mot (variables en marqueurs), « op » un séparateur, « redir » une redirection.
    Le texte des substitutions ($( ), `…`, <( )) est ajouté à subs, à analyser à part."""
    jetons, mot, i, n = [], None, 0, len(t)
    attendus, attend_delimiteur = [], None

    def clore():
        nonlocal mot, attend_delimiteur
        if mot is not None:
            texte = "".join(mot)
            jetons.append(("w", texte))
            if attend_delimiteur is not None:
                attendus.append((re.sub(f"[{VAR_DEB}{VAR_FIN}{INCONNU}{VARQ_DEB}{QUOTE}]", "", texte), attend_delimiteur))
                attend_delimiteur = None
            mot = None

    while i < n:
        c = t[i]
        if c in " \t\r":
            clore()
            i += 1
        elif c == "\n":
            clore()
            jetons.append(("op", ";"))
            i += 1
            if attendus:
                i = _sauter_documents_ici(t, i, attendus, subs)
                attendus = []
        elif c == "#" and mot is None:
            j = t.find("\n", i)
            i = n if j < 0 else j
        elif c == "\\":
            if i + 1 < n and t[i + 1] == "\n":
                i += 2
            else:
                mot = [] if mot is None else mot
                if i + 1 < n:
                    mot.append(t[i + 1])
                i += 2
        elif c == "'":
            j = t.find("'", i + 1)
            if j < 0:
                raise Syntaxe
            mot = [] if mot is None else mot
            mot.append(t[i + 1:j])
            i = j + 1
        elif c == '"':
            mot = [] if mot is None else mot
            i = _guillemets(t, i + 1, mot, subs)
        elif c == "$":
            mot = [] if mot is None else mot
            i = _dollar(t, i, mot, subs, False)
        elif c == "`":
            j = _fin_backtick(t, i + 1)
            subs.append(t[i + 1:j].replace("\\`", "`"))
            mot = [] if mot is None else mot
            mot.append(INCONNU)
            i = j + 1
        elif c in "<>" and t[i + 1:i + 2] == "(":
            j = _fin_substitution(t, i + 2)
            subs.append(t[i + 2:j])
            mot = [] if mot is None else mot
            mot.append(INCONNU)
            i = j + 1
        elif c == "(" and t[i + 1:i + 2] == "(" and mot is None:   # ((expression)) : commande arithmétique, pas un here-document
            j = _fin_substitution(t, i + 1)
            _arithmetique(t[i + 1:j], subs)
            jetons.append(("op", ";"))
            i = j + 1
        elif c in ";&|<>()":
            if t[i:i + 3] == "<<<":
                operateur = "<<<"
            elif t[i:i + 3] == "<<-":
                operateur = "<<-"
            elif t[i:i + 2] in OPERATEURS_DOUBLES:
                operateur = t[i:i + 2]
            else:
                operateur = c
            redirection = operateur[0] in "<>" or operateur == "&>"
            if redirection and mot is not None and "".join(mot).isdigit():
                mot = None   # le numéro de descripteur qui précède (2>&1)
            else:
                clore()
            jetons.append(("redir" if redirection else "op", operateur))
            if operateur in ("<<", "<<-"):
                attend_delimiteur = operateur == "<<-"
            i += len(operateur)
        else:
            mot = [] if mot is None else mot
            mot.append(c)
            i += 1
    clore()
    return jetons


def segments(jetons: list) -> list:
    """Listes de mots, une par commande simple (séparateurs, parenthèses et redirections retirés)."""
    sortie, courant, saute = [], [], False
    for genre, valeur in jetons:
        if genre == "redir":
            saute = True
        elif genre == "op":
            saute = False
            if courant:
                sortie.append(courant)
                courant = []
        elif saute:
            saute = False
        else:
            courant.append(valeur)
    if courant:
        sortie.append(courant)
    return sortie


def developper(mot: str, env: dict) -> str:
    def valeur(m):
        nom = m.group(2)
        nue = m.group(1) == VAR_DEB
        if nom in env:
            return env[nom].replace(QUOTE, "") if nue else env[nom]   # la valeur d'une expansion nue ne garde pas l'état « guillemets »
        # Sous un rappel (garde de session), seules les variables que le rappel déclare connues (`variables_connues`, HOME pour la garde) gardent la
        # valeur lisible ; PWD, OLDPWD, CLAUDE_PROJECT_DIR… valent une expansion inconnue (revue Opus, constat 5). Sans rappel, ou avec un rappel qui
        # ne déclare rien : BENIGNES, comme avant. Remplace : rien. Retrait : permanent.
        connues = getattr(_RAPPEL, "variables_connues", BENIGNES) if _RAPPEL is not None else BENIGNES
        if nom in BENIGNES and nom in connues:
            return (BENIGNE_NUE if nue else BENIGNE_QUOTEE) + "/x"   # lisible comme « /x », sauf pour l'argument de fichier d'un shell
        return INCONNU if nue else INCONNU + QUOTE
    return re.sub(f"([{VAR_DEB}{VARQ_DEB}])([^{VAR_FIN}]*){VAR_FIN}", valeur, mot)


def developper_mots(mots: list, env: dict) -> list:
    """Mots développés ; une variable nue dont la valeur contient des blancs est coupée en plusieurs mots (découpage du shell). Dès
    que IFS a été affecté, le découpage est inconnu : un mot qui contient une expansion nue devient une valeur inconnue."""
    sortie = []
    for mot in mots:
        texte = developper(mot, env)
        if VAR_DEB in mot and "IFS" in env:
            sortie.append(INCONNU)
        elif VAR_DEB in mot and re.search(r"\s", texte):
            sortie.extend(texte.split())
        else:
            sortie.append(texte)
    return sortie


def noter(env: dict, nom: str, valeur: str, refus: list):
    """Enregistre une affectation ; celles qui font lancer un programme par npm ou node sont refusées."""
    nom = nom.rstrip("+")
    if _RAPPEL is not None:
        _RAPPEL.affectation(nom, valeur)
    if nom.lower().startswith("npm_config_") or nom.upper() == "NODE_OPTIONS":
        refus.append(f"affectation {nom} (configure npm ou node)")
    env[nom] = valeur


# --- Résolution comme npm ---------------------------------------------------------------------------------------------------------------

def _prefixes_uniques() -> dict:
    compte, premier = {}, {}
    for mot in MOTS_NPM:
        for k in range(1, len(mot) + 1):
            compte[mot[:k]] = compte.get(mot[:k], 0) + 1
            premier[mot[:k]] = mot
    return {p: premier[p] for p, c in compte.items() if c == 1}


ABREVIATIONS = _prefixes_uniques()
OPTIONS_NPM_CONNUES = OPTIONS_NPM_AVEC_VALEUR | OPTIONS_NPM_BOOLEENNES


def resoudre_npm(mot: str):
    """La commande npm que désigne ce mot (deref de npm : camelCase, nom exact, alias, abréviation unique), ou None."""
    if re.search("[A-Z]", mot):
        mot = re.sub("([A-Z])", lambda m: "-" + m.group(1).lower(), mot)
    if mot in COMMANDES_NPM:
        return mot
    if mot in ALIAS_NPM:
        return ALIAS_NPM[mot]
    a = ABREVIATIONS.get(mot)
    while a in ALIAS_NPM:
        a = ALIAS_NPM[a]
    return a


def lectures_npm(args: list) -> list:
    """Lectures possibles des arguments de npm : liste de (mot de commande ou None, mots suivants, lecture sûre). Une option inconnue
    donne deux lectures (elle prend la valeur suivante, ou non), comme nopt ; la lecture qui lui fait prendre une valeur n'est pas
    sûre : un mot inconnu y est ignoré, seule une vraie commande y compte. Une option booléenne prend true, false ou always."""
    resultats = []

    def avancer(i: int, sure: bool, profondeur: int):
        if profondeur > PROFONDEUR_SYNTAXE or len(resultats) > LECTURES_MAX:
            raise Syntaxe
        while i < len(args):
            a = args[i]
            if a == "--":
                resultats.append((args[i + 1], args[i + 2:], sure) if i + 1 < len(args) else (None, [], sure))
                return
            if a.startswith("--"):
                nom, egal, _ = a[2:].partition("=")
                if egal:
                    i += 1
                elif nom in OPTIONS_NPM_AVEC_VALEUR:
                    i += 2
                elif nom in OPTIONS_NPM_BOOLEENNES or nom.startswith("no-"):
                    i += 1
                    if args[i:i + 1] and args[i] in VALEURS_BOOLEENNES:
                        i += 1
                else:
                    avancer(i + 2, False, profondeur + 1)
                    i += 1
                continue
            if a.startswith("-") and len(a) > 1 and a[1] != INCONNU:
                amas, consomme, inconnu = a[1:], False, False
                for k, lettre in enumerate(amas):
                    if lettre in COURTES_NPM_AVEC_VALEUR:
                        consomme = k == len(amas) - 1
                        break
                    if lettre not in COURTES_NPM_BOOLEENNES:
                        inconnu = True
                if consomme:
                    i += 2
                    continue
                if inconnu:
                    avancer(i + 2, False, profondeur + 1)
                i += 1
                if not inconnu and args[i:i + 1] and args[i] in VALEURS_BOOLEENNES:
                    i += 1
                continue
            resultats.append((a, args[i + 1:], sure))
            return
        resultats.append((None, [], sure))

    avancer(0, True, 0)
    return resultats


def options_qui_lancent(args: list) -> list:
    """Options de npm qui lui font lancer un programme (--editor, --script-shell…), écrites en entier ou abrégées."""
    trouvees = []
    for a in args:
        if a == "--":
            break
        if a.startswith("--") and len(a) > 2:
            nom = a[2:].partition("=")[0]
            if not nom or nom in OPTIONS_NPM_CONNUES:
                continue
            if nom in OPTIONS_NPM_QUI_LANCENT or any(d.startswith(nom) for d in OPTIONS_NPM_QUI_LANCENT):
                trouvees.append(f"npm --{nom[:30]} (option qui lance un programme)")
    return trouvees


def verdict_npm(nom: str, reste: list):
    """Motif de refus d'une commande npm résolue, ou None."""
    if nom not in PERMISES_NPM:
        return f"npm {nom}"
    if nom == "audit" and any(m in ("fix", "--fix") for m in reste):
        return "npm audit fix"
    if nom == "config":
        positionnels = [m for m in reste if not m.startswith("-")]
        if not positionnels or positionnels[0] != "get" or MOTS_CONFIG_REFUSES & set(positionnels):
            return "npm config " + (positionnels[0] if positionnels else "(sans get)")
    return None


def analyser_npm(args: list, incertain: bool, refus: list):
    refus.extend(options_qui_lancent(args))
    try:
        lectures = lectures_npm(args)
    except Syntaxe:
        refus.append("npm : arguments trop ambigus")
        return
    for mot, reste, sure in lectures:
        if mot is None:
            if incertain:
                refus.append("npm sans sous-commande (arguments reçus par l'entrée standard)")
            continue
        nom = None if INCONNU in mot else resoudre_npm(mot)
        if nom is None:
            if sure or incertain:
                refus.append("npm : sous-commande inconnue, ambiguë ou non résolue")
            continue
        motif = verdict_npm(nom, reste)
        if motif:
            refus.append(motif + (f" (écrit « {mot[:30]} »)" if mot != nom else ""))


# --- node ---------------------------------------------------------------------------------------------------------------------------------

def lectures_node(args: list) -> list:
    """Lectures possibles des arguments de node : liste de (refus ou None, fichier ou None, mots suivants, sans_script). Une option
    inconnue donne deux lectures (elle prend la valeur suivante, ou non) pour qu'aucun -e, -p ou --eval ne reste caché derrière."""
    sorties = []

    def avancer(i: int, sans_script: bool, profondeur: int):
        if profondeur > PROFONDEUR_SYNTAXE or len(sorties) > LECTURES_MAX:
            raise Syntaxe
        while i < len(args):
            a = args[i]
            if a == "--":
                sorties.append((None, args[i + 1] if i + 1 < len(args) else None, args[i + 2:], sans_script))
                return
            if a == "-":
                sorties.append(("node - (programme sur l'entrée standard)", None, [], True))
                return
            if a.startswith("--"):
                nom, egal, valeur = a[2:].partition("=")
                nom = nom.replace("_", "-")
                if nom in ("eval", "print", "interactive"):
                    sorties.append((f"node --{nom}", None, [], True))
                    return
                if nom in OPTIONS_NODE_SANS_SCRIPT:
                    sans_script = True
                if nom in ("import", "require", "loader", "experimental-loader"):
                    if not egal:
                        valeur = args[i + 1] if i + 1 < len(args) else ""
                        i += 1
                    if valeur.lower().startswith("data:"):
                        sorties.append((f"node --{nom} data: (programme dans l'option)", None, [], True))
                        return
                    i += 1
                elif egal or nom in OPTIONS_NODE_SANS_VALEUR or nom.startswith(PREFIXES_NODE_SANS_VALEUR):
                    i += 1
                elif nom in OPTIONS_NODE_AVEC_VALEUR:
                    i += 2
                else:
                    avancer(i + 2, sans_script, profondeur + 1)
                    i += 1
                continue
            if a.startswith("-") and len(a) > 1:
                amas = a[1:]
                if amas[0] in "rC":
                    valeur = amas[1:] or (args[i + 1] if i + 1 < len(args) else "")
                    if valeur.lower().startswith("data:"):
                        sorties.append(("node -r data: (programme dans l'option)", None, [], True))
                        return
                    i += 1 if len(amas) > 1 else 2
                    continue
                if re.search("[epi]", amas):
                    sorties.append(("node -e, -p ou -i (évaluation ou interpréteur)", None, [], True))
                    return
                if amas in ("v", "h", "c"):
                    sans_script = True
                i += 1
                continue
            sorties.append((None, a, args[i + 1:], sans_script))
            return
        sorties.append((None, None, [], sans_script))

    avancer(0, False, 0)
    return sorties


def analyser_node(args: list, env: dict, profondeur: int, refus: list, incertain: bool):
    try:
        lectures = lectures_node(args)
    except Syntaxe:
        refus.append("node : arguments trop ambigus")
        return
    motifs = [m for m, _, _, _ in lectures if m]
    if motifs:
        refus.extend(motifs)
        return
    if all(f is None and not s for _, f, _, s in lectures):
        refus.append("node sans fichier (entrée standard ou interpréteur)")
        return
    for _, fichier, reste, _ in lectures:
        if fichier is None:
            continue
        base = fichier.rsplit("/", 1)[-1]
        if INCONNU in base:
            refus.append("node : fichier non résolu (substitution ou variable)")
        elif fichier.startswith(ENTREES_STANDARD):
            refus.append("node : programme lu sur l'entrée standard (/dev/stdin)")
        elif base.lower() in FICHIERS_NPM:
            if base.lower().startswith("npx"):
                refus.append("npx (par node)")
            else:
                analyser_npm(reste, incertain, refus)


# --- Lanceurs ---------------------------------------------------------------------------------------------------------------------------

def sauter_options(args: list, avec_valeur=frozenset()) -> list:
    while args and args[0].startswith("-") and args[0] != "-":
        if args[0] == "--":
            return args[1:]
        args = args[2:] if args[0] in avec_valeur else args[1:]
    return args


def analyser_script(texte: str, env: dict, profondeur: int, refus: list, incertain: bool = False):
    if profondeur > PROFONDEUR_MAX:
        refus.append("commande trop imbriquée")
        return
    subs = []
    try:
        jetons = decouper(texte, subs)
    except Syntaxe:
        refus.append(ILLISIBLE)
        return
    if _RAPPEL is not None:
        _RAPPEL.jetons(jetons)
    for sous in subs:
        analyser_script(sous, env, profondeur + 1, refus, incertain)
    for mots in segments(jetons):
        analyser_segment(mots, env, profondeur, refus, incertain)


def analyser_segment(mots: list, env: dict, profondeur: int, refus: list, incertain: bool):
    if "IFS" not in env and any("IFS" in re.sub(f"[{VAR_DEB}{VAR_FIN}{INCONNU}{VARQ_DEB}{QUOTE}]", "", m) for m in mots):
        env["IFS"] = ""   # IFS affecté (for, read, printf -v, ${IFS:=…}…) ou nommé : le découpage des mots est inconnu
    while mots and AFFECTATION.match(mots[0]):
        nom, _, valeur = mots[0].partition("=")
        noter(env, nom, developper(valeur, env), refus)
        mots = mots[1:]
    while mots and mots[0] in MOTS_RESERVES:
        mots = mots[1:]
    if mots and mots[0] == "function":   # function f { corps ; } : le corps commence après l'accolade
        mots = mots[2:]
        while mots and mots[0] in MOTS_RESERVES:
            mots = mots[1:]
    if not mots or mots[0] in SANS_COMMANDE:
        if mots and _RAPPEL is not None and mots[0] in ("for", "select"):   # `for NOM in …` pose NOM : le rappel le voit (revue Opus, constat 9)
            _RAPPEL.incertain = incertain
            _RAPPEL.commande(mots, env)
        return
    if mots[0] in ("export", "declare", "local", "readonly", "typeset"):
        if _RAPPEL is not None:   # `export NOM` sans « = » : le rappel voit la commande avant ses affectations (revue Opus, constat 9)
            _RAPPEL.incertain = incertain
            _RAPPEL.commande([m for m in developper_mots(mots, env) if m == mots[0] or not AFFECTATION.match(m)], env)   # les « NOM=valeur » vont par noter
        for mot in mots[1:]:
            if AFFECTATION.match(mot):
                nom, _, valeur = mot.partition("=")
                noter(env, nom, developper(valeur, env), refus)
        return
    lancer(developper_mots(mots, env), env, profondeur, refus, incertain)


def _entree_standard(mot: str) -> bool:
    return mot == "-" or mot.startswith(ENTREES_STANDARD) or INCONNU in mot.rsplit("/", 1)[-1]


JOKERS = re.compile(r"[*?\[{]")
EXPANSIONS_EN_TETE = re.compile(f"(?:{INCONNU}{QUOTE}?)+")


def _chemin_normalise(mot: str) -> str:
    """Chemin absolu sans « // », « . » ni « .. » (sans accès au disque)."""
    parties = []
    for composant in mot.split("/"):
        if composant == "..":
            if parties:
                parties.pop()
        elif composant not in ("", "."):
            parties.append(composant)
    return "/" + "/".join(parties)


def _entree_du_shell(mot: str) -> bool:
    """Argument de fichier d'un shell qui peut valoir l'entrée standard (R-138, règle stricte). Les marqueurs INCONNU sont les
    expansions non résolues : nues (INCONNU seul, le découpage peut les couper n'importe où) ou entre guillemets (INCONNU + QUOTE).
    Refusés : « - », /dev/ et /proc/ (chemin normalisé compris), les jokers, toute expansion nue, un mot qui commence par une
    expansion sans qu'un « / » la suive, un composant « .. », un dernier composant qui contient une expansion ou peut valoir
    stdin, 0, - ou un nombre. "$D/x.sh" passe ; $1-x.sh, ./"$1" et "$D"/stdin sont refusés."""
    # une variable jugée bénigne (HOME, TMPDIR…) peut avoir été réaffectée : ici elle vaut une expansion inconnue, guillemets gardés
    mot = mot.replace(BENIGNE_NUE + "/x", INCONNU).replace(BENIGNE_QUOTEE + "/x", INCONNU + QUOTE)
    if mot == "-" or mot.startswith(ENTREES_STANDARD) or JOKERS.search(mot):
        return True
    if not re.search(INCONNU, mot):
        dernier = mot.rsplit("/", 1)[-1]
        if dernier in ("stdin", "0", "-") or dernier.isdigit():   # chemin relatif vers /dev/stdin, /dev/fd/0 (cd /dev && bash fd/0)
            return True
        return mot.startswith("/") and _chemin_normalise(mot).startswith(ENTREES_STANDARD)
    if re.search(f"{INCONNU}(?!{QUOTE})", mot):
        return True   # expansion nue
    tete = EXPANSIONS_EN_TETE.match(mot)
    if tete and not mot[tete.end():].startswith("/"):
        return True
    composants = mot.split("/")
    if any(re.sub(f"{INCONNU}{QUOTE}", "", c) == ".." for c in composants):
        return True
    dernier = composants[-1]
    return INCONNU in dernier or dernier in ("stdin", "0", "-") or dernier.isdigit()


def lancer(mots: list, env: dict, profondeur: int, refus: list, incertain: bool, rappel=None):
    """Analyse une commande simple. `rappel` (change session-guard-n1, D1) : objet facultatif qui reçoit chaque commande simple vue par
    l'analyseur, lanceurs et chaînes `-c` compris (rappel.commande(mots, env)), chaque affectation (rappel.affectation(nom, valeur)) et les
    jetons de chaque texte découpé (rappel.jetons(jetons)). Sans rappel, le comportement est exactement celui d'avant. Les appels récursifs
    passent par le rappel du module que pose `avec_rappel`."""
    if rappel is not None:
        rappel_actif = _RAPPEL
        _poser_rappel(rappel)
        try:
            return lancer(mots, env, profondeur, refus, incertain)
        finally:
            _poser_rappel(rappel_actif)
    while mots and AFFECTATION.match(mots[0]):
        nom, _, valeur = mots[0].partition("=")
        noter(env, nom, valeur, refus)
        mots = mots[1:]
    if not mots:
        return
    if profondeur > PROFONDEUR_MAX:
        refus.append("commande trop imbriquée")
        return
    if _RAPPEL is not None:
        _RAPPEL.incertain = incertain   # vrai sous xargs et find -exec : arguments ajoutés à l'exécution (revue Opus, constat 1)
        _RAPPEL.commande(mots, env)
    texte, args = mots[0], mots[1:]
    if texte == "-":   # zsh : précommande « - » (lancement comme shell de connexion)
        lancer(args, env, profondeur + 1, refus, incertain)
        return
    if texte.startswith("=") and len(texte) > 1:   # zsh : =npm est le chemin de npm
        texte = texte[1:]
    base = texte.rsplit("/", 1)[-1]
    nom = base.lower()   # le disque du Mac ne distingue pas NPM de npm
    if INCONNU in base or (nom not in ("[", "[[") and re.search(r"[*?\[{]", base)):
        refus.append(f"nom de commande non résolu « {texte[:40].replace(INCONNU, '?').replace(QUOTE, '')} » (substitution, variable ou joker)")
        return
    if nom in ("npm", "npm-cli.js", "npm-cli"):
        analyser_npm(args, incertain, refus)
    elif nom in ("npx", "npx-cli.js", "npx-cli"):
        refus.append("npx")
    elif nom in ("node", "nodejs"):
        analyser_node(args, env, profondeur, refus, incertain)
    elif nom in GESTIONNAIRES:
        refus.append(nom)
    elif nom in SHELLS_REFUSES:
        refus.append(f"{nom} (shell non analysé)")
    elif nom in INTERPRETES:
        analyser_interprete(args, env, profondeur, refus, incertain)
    elif nom in ("source", "."):
        if args and _entree_standard(args[0]):
            refus.append("source d'un programme lu sur l'entrée standard ou par substitution")
    elif nom == "eval":
        analyser_script(" ".join(args), env, profondeur + 1, refus, incertain)
    elif nom == "trap":
        reste = sauter_options(args)
        if reste:
            analyser_script(reste[0], env, profondeur + 1, refus, incertain)
    elif nom == "repeat":
        reste = args[1:]
        lancer(reste[1:] if reste[:1] == ["do"] else reste, env, profondeur + 1, refus, incertain)
    elif nom == "coproc":
        lancer(args, env, profondeur + 1, refus, incertain)
        if args[1:2] in (["{"], ["("]):
            lancer(args[2:], env, profondeur + 1, refus, incertain)
    elif nom == "env":
        lancer_env(args, env, profondeur, refus, incertain)
    elif nom == "command" or nom == "builtin":
        reste = args
        while reste and reste[0].startswith("-"):
            if re.search("[vV]", reste[0]):
                return   # command -v : cherche le programme, ne le lance pas
            reste = reste[1:]
        lancer(reste, env, profondeur + 1, refus, incertain)
    elif nom in ("timeout", "gtimeout"):
        reste = sauter_options(args, {"-s", "-k", "--signal", "--kill-after"})
        lancer(reste[1:], env, profondeur + 1, refus, incertain)
    elif nom == "xargs":
        reste = sauter_options(args, {"-I", "-n", "-L", "-P", "-s", "-d", "-E", "-a", "-J", "-R", "-S", "-l"})
        lancer(reste, env, profondeur + 1, refus, True)
    elif nom == "find":
        lancer_find(args, env, profondeur, refus, incertain)
    elif nom == "watch":
        reste = sauter_options(args, {"-n", "--interval"})
        analyser_script(" ".join(reste), env, profondeur + 1, refus, incertain)
    elif nom == "su":
        for k, a in enumerate(args):
            if a.startswith("--command=") or a == "--command" or (a.startswith("-") and not a.startswith("--") and "c" in a[1:]):
                chaine = a.partition("=")[2] if a.startswith("--command=") else (args[k + 1] if k + 1 < len(args) else "")
                analyser_script(chaine, env, profondeur + 1, refus, incertain)
    elif nom == "script":   # macOS : script [-q] fichier commande… ; Linux : script -c "commande" fichier
        if "-c" in args and args.index("-c") + 1 < len(args):
            analyser_script(args[args.index("-c") + 1], env, profondeur + 1, refus, incertain)
        reste = sauter_options(args, {"-t", "-c"})
        lancer(reste[1:], env, profondeur + 1, refus, incertain)
        lancer(reste, env, profondeur + 1, refus, incertain)
    elif nom == "sandbox-exec":
        lancer(sauter_options(args, {"-p", "-f", "-n", "-D"}), env, profondeur + 1, refus, incertain)
    elif nom in ("tmux", "screen"):   # la commande est un argument (ou la suite des arguments) lancé par un shell
        for k, a in enumerate(args):
            if not a.startswith("-"):
                analyser_script(a, env, profondeur + 1, refus, incertain)
            lancer(args[k:], env, profondeur + 1, refus, incertain)
    elif nom in LANCEURS_SIMPLES:
        lancer(sauter_options(args, LANCEURS_SIMPLES[nom]), env, profondeur + 1, refus, incertain)
    elif nom == "fnm" and args[:1] == ["exec"]:
        avec_valeur = {"--using", "--version-file-strategy", "--log-level", "--fnm-dir", "--arch", "--node-dist-mirror",
                       "--resolve-engines"}
        lancer(sauter_options(args[1:], avec_valeur), env, profondeur + 1, refus, incertain)
    elif nom == "volta" and args[:1] == ["run"]:
        avec_valeur = {"--node", "--npm", "--yarn", "--pnpm", "--bundled-npm", "--env"}
        lancer(sauter_options(args[1:], avec_valeur), env, profondeur + 1, refus, incertain)
    elif nom == "mise" and args[:1] in (["exec"], ["x"]):
        reste = args[1:]
        if "--" in reste:
            reste = reste[reste.index("--") + 1:]
        else:
            reste = [m for m in sauter_options(reste) if "@" not in m]
        lancer(reste, env, profondeur + 1, refus, incertain)
    elif nom == "asdf" and args[:1] == ["exec"]:
        lancer(args[1:], env, profondeur + 1, refus, incertain)
    elif nom == "direnv" and args[:1] == ["exec"]:
        lancer(args[2:], env, profondeur + 1, refus, incertain)
    elif nom == "nvm" and args[:1] in (["exec"], ["run"]):
        reste = sauter_options(args[1:])[1:]   # la version
        if args[0] == "run":
            analyser_node(reste, env, profondeur, refus, incertain)
        else:
            lancer(reste, env, profondeur + 1, refus, incertain)
    elif nom in ("uv", "uvx"):
        reste = args
        if nom == "uv":
            if args[:1] != ["run"]:
                return
            reste = args[1:]
        avec_valeur = {"--with", "--with-editable", "--with-requirements", "-p", "--python", "--project", "--directory",
                       "--env-file", "--extra", "--group", "--package", "--no-group", "--only-group", "--index",
                       "--default-index", "--index-url", "--extra-index-url", "--find-links", "--from", "-w"}
        lancer(sauter_options(reste, avec_valeur), env, profondeur + 1, refus, incertain)
    elif nom in ("poetry", "pipenv", "pdm", "rye") and args[:1] == ["run"]:
        lancer(args[1:], env, profondeur + 1, refus, incertain)


def lancer_env(args: list, env: dict, profondeur: int, refus: list, incertain: bool):
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--":
            i += 1
            break
        if a.startswith("--split-string"):
            if a == "--split-string":
                chaine, suite = (args[i + 1] if i + 1 < len(args) else ""), args[i + 2:]
            else:
                chaine, suite = a.partition("=")[2], args[i + 1:]
            analyser_script(chaine + " " + " ".join(suite), env, profondeur + 1, refus, incertain)
            return
        if a.startswith("--"):
            i += 2 if a in ("--unset", "--chdir", "--argv0") else 1
        elif a.startswith("-") and a != "-":
            amas = a[1:]
            place = next((k for k, lettre in enumerate(amas) if lettre in "uCPSa"), None)
            if place is None:
                i += 1
                continue
            attache = amas[place + 1:]
            if amas[place] == "S":   # -S peut suivre d'autres lettres : -iS 'npm install'
                chaine = attache or (args[i + 1] if i + 1 < len(args) else "")
                suite = args[i + 1:] if attache else args[i + 2:]
                analyser_script(chaine + " " + " ".join(suite), env, profondeur + 1, refus, incertain)
                return
            i += 1 if attache else 2
        elif AFFECTATION.match(a):
            nom, _, valeur = a.partition("=")
            noter(env, nom, valeur, refus)
            i += 1
        else:
            break
    lancer(args[i:], env, profondeur + 1, refus, incertain)


def lancer_find(args: list, env: dict, profondeur: int, refus: list, incertain: bool):
    i = 0
    while i < len(args):
        if args[i] in ("-exec", "-execdir", "-ok", "-okdir"):
            j = i + 1
            while j < len(args) and args[j] not in (";", "+"):
                j += 1
            lancer(args[i + 1:j], env, profondeur + 1, refus, True)
            i = j
        i += 1


LONGUES_SHELL_SANS_VALEUR = {
    "--norc", "--noprofile", "--posix", "--login", "--noediting", "--restricted", "--verbose", "--debugger", "--dump-strings",
    "--dump-po-strings", "--pretty-print", "--rpm-requires", "--protected",
}
LONGUES_SHELL_AVEC_VALEUR = {"--rcfile", "--init-file", "--emulate"}


MOTIF_SHELL_NON_RESOLUE = "shell : option non résolue (variable ou substitution)"
MOTIF_SHELL_LONGUE_INCONNUE = "shell : option longue inconnue (peut prendre une valeur)"


def lire_options_shell(args: list):
    """R-20261111-23. Lecture pure des options d'un shell (même parcours qu'avant pour analyser_interprete, dont elle est maintenant la source unique ;
    garde_session.regle_allexport l'appelle aussi). Rend (options, i, c_option, stdin, motif) : `options` la liste de (signe, lettre, valeur), la valeur
    n'étant renseignée que pour o et O (l'argument suivant, ou None s'il manque) ; `i` l'indice du premier argument qui n'est pas une option ; `c_option`
    et `stdin` si -c ou -s (ou `-`) ont été lus ; `motif` le refus quand la lecture s'arrête sur une option non résolue ou une longue inconnue, sinon None.
    Remplace : la boucle écrite à la main dans analyser_interprete. Retrait : permanent."""
    options, i, c_option, stdin = [], 0, False, False
    while i < len(args):
        a = args[i]
        if a == "--":
            i += 1
            break
        if a[:1] in "-+" and len(a) > 1 and INCONNU in a:
            return options, i, c_option, stdin, MOTIF_SHELL_NON_RESOLUE
        if a.startswith("--"):
            nom = a.partition("=")[0]
            if nom in LONGUES_SHELL_AVEC_VALEUR:
                i += 1 if "=" in a else 2
            elif nom in LONGUES_SHELL_SANS_VALEUR:
                i += 1
            else:
                return options, i, c_option, stdin, MOTIF_SHELL_LONGUE_INCONNUE
            continue
        if a == "-":
            stdin = True
            i += 1
            break
        if a[:1] in "-+" and len(a) > 1:
            consomme = 0
            for lettre in a[1:]:
                valeur = None
                if lettre in "oO":
                    valeur = args[i + 1 + consomme] if i + 1 + consomme < len(args) else None
                    consomme += 1   # -o et -O prennent l'argument suivant, chacun le sien, dans l'ordre
                elif a[0] == "-" and lettre == "c":
                    c_option = True
                elif a[0] == "-" and lettre == "s":
                    stdin = True
                options.append((a[0], lettre, valeur))
            i += 1 + consomme
            continue
        break
    return options, i, c_option, stdin, None


def analyser_interprete(args: list, env: dict, profondeur: int, refus: list, incertain: bool):
    if args[:1] and args[0] in ("--version", "--help"):   # seulement en premier : après la chaîne de -c, le shell l'a déjà lancée
        return
    _options, i, c_option, stdin, motif = lire_options_shell(args)
    if motif:
        refus.append(motif)
        return
    if c_option:   # la chaîne de commandes est le premier argument qui n'est pas une option
        if i < len(args):
            analyser_script(args[i], env, profondeur + 1, refus, incertain)
    elif i >= len(args) or stdin or _entree_du_shell(args[i]):
        refus.append("shell qui lit ses commandes sur l'entrée standard ou par substitution")


# --- Hook ---------------------------------------------------------------------------------------------------------------------------------

def refus_de(commande: str) -> list:
    """Formes refusées de la commande, dans l'ordre, sans doublon ; [] si la commande est permise. Une analyse en échec refuse."""
    refus = []
    try:
        analyser_script(commande, {}, 0, refus)
    except Exception:   # RecursionError comprise : dans le doute, refusé
        refus.append("analyse impossible")
    vus = []
    for motif in refus:
        if motif not in vus:
            vus.append(motif)
    return vus


MESSAGE = ("garde npm : refusé : {formes}. Une session ne lance ni installation, ni mise à jour, ni retrait, ni liaison, ni "
           "publication de paquet, ni npx, npm exec ou node en évaluation (mothra/CLAUDE.md, « What a session never does »). Permis : "
           "npm test, npm run <script>, npm start, npm ls, view, outdated, audit sans fix, help, config get, npm --version, "
           "node --version et node <fichier>.")


class _EntreeIllisible(Exception):
    """L'entrée du hook n'est pas un JSON lisible, ou une commande Bash n'a pas de chaîne de commande."""


def _lire_commande(texte: str):
    """La commande Bash (chaîne, éventuellement vide), ou None pour un autre outil. Lève _EntreeIllisible quand l'entrée n'est pas un JSON
    d'objet avec un nom d'outil, ou quand l'outil Bash n'a pas de chaîne `command`. Échec fermé (A-45 de #629, R-20261107-30 point 7).
    Remplace : le passage (code 0) d'une entrée illisible ou d'une commande Bash sans chaîne. Retrait : permanent."""
    try:
        donnees = json.loads(texte)
    except ValueError:
        raise _EntreeIllisible from None
    if not isinstance(donnees, dict) or not isinstance(donnees.get("tool_name"), str):
        raise _EntreeIllisible
    if donnees["tool_name"] != "Bash":
        return None
    entree = donnees.get("tool_input")
    commande = entree.get("command") if isinstance(entree, dict) else None
    if not isinstance(commande, str):
        raise _EntreeIllisible
    return commande


def _cwd_du_hook(entree: str):
    """Le dossier courant du hook (champ `cwd` du JSON), ou None."""
    try:
        cwd = json.loads(entree).get("cwd")
    except (ValueError, AttributeError):
        return None
    return cwd if isinstance(cwd, str) else None


# Repli quand le module des conditions lui-même est inutilisable : la phrase de fin de D7 y est recopiée ; un test la compare à celle du module.
MESSAGE_NPM_CI_ILLISIBLE = ("garde npm : npm ci refusé : vérification impossible. Une session lance npm ci seulement sous la forme « npm ci » ou "
                            "« cd <dossier> && npm ci », dans le dossier mothra d'un worktree propre, sans fin en cours, avec les package.json, "
                            "package-lock.json et .npmrc de mothra/ identiques à origin/main. Un verrou modifié, avec son npm install et son "
                            "audit, reste à l'auteur.")


def _npm_ci(commande: str, entree: str, worktrees) -> int:
    """Exception de R-20261031-53 à la règle « une session ne lance pas npm ci » : `npm ci` seul, dans le dossier mothra d'un worktree de
    branche, sous les conditions de R-20261030-11 (a) que lit tools/npm_ci_conditions.py (importé ici seulement). Remplace les deux règles
    deny de `npm ci` nu et de `cd … && npm ci` nu et les gestes de l'auteur sur les worktrees neufs ; tombe avec le changement qui donne
    à un worktree son node_modules sans npm ci de la session (design D11 de npm-ci-session) : ce changement retire cette fonction, le
    module et leurs tests. Toute exception : refusé avec « vérification impossible »."""
    try:
        import npm_ci_conditions
        echecs = npm_ci_conditions.echecs(commande, _cwd_du_hook(entree), worktrees)
        if not echecs:
            return 0
        texte = npm_ci_conditions.message(echecs)
    except Exception:
        texte = MESSAGE_NPM_CI_ILLISIBLE
    print(texte, file=sys.stderr)
    return 2


def main(argv: list, entree: str, worktrees=None) -> int:
    try:
        commande = _lire_commande(entree)
        if not commande:
            return 0
        formes = refus_de(commande)
    except _EntreeIllisible:
        formes = ["entrée illisible"]
    except Exception:   # toute exception, RecursionError et MemoryError comprises : dans le doute, refusé
        formes = ["analyse impossible"]
    if not formes:
        return 0
    if len(formes) == 1 and formes[0].startswith("npm ci"):   # `npm ci` écrit ci ou par un alias de npm : l'exception de _npm_ci
        return _npm_ci(commande, entree, worktrees)
    print(MESSAGE.format(formes="; ".join(formes)), file=sys.stderr)
    return 2


if __name__ == "__main__":
    # Remplace : la trace Python sur une entrée standard non lisible. Retrait : permanent
    try:
        _entree = sys.stdin.read()
    except Exception:   # entrée standard fermée ou non décodable : refus (2) au lieu d'une trace
        print(MESSAGE.format(formes="entrée illisible"), file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1:], _entree))
