# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
PMZilla Lab : seul chemin d'écriture vers GitHub pour la file de travail (change github-roadmap, design D7 à D9).

    uv run tools/gh_issue.py new-feature --title T --theme X --milestone M [--blocked-by R-a,R-b] [--set key=value]... [--product mothra]
    uv run tools/gh_issue.py edit R-<n> [--title T] [--milestone M] [--set key=value]... [--product mothra|none]   (--product : pose le label product:<valeur> (liste fermée, aujourd'hui mothra) ou, avec none, le retire ; l'absence de label vaut PMZilla ; sync-tasks recopie le label de la feature sur ses tâches ;--title : texte sans clé, la commande ajoute « R-<n> · » ; non vide, refusé s'il commence déjà par une clé)
    uv run tools/gh_issue.py status R-<n> <Todo|Ready|"In progress"|Done>
    uv run tools/gh_issue.py block R-<n> --by R-<m>      /      unblock R-<n> --by R-<m>
    uv run tools/gh_issue.py comment R-<n> --body-file F
    uv run tools/gh_issue.py sync-tasks R-<n>
    uv run tools/gh_issue.py new-task R-<n> --title T --body-file F [--milestone M]   (tâche utilisateur autonome, sans tasks.md : issue type:task + owner:user (+ product: de la feature) de clé R-<n>/u<k>, k = prochain numéro libre, sous-issue de la feature, dans son jalon sauf --milestone (existant) ; --title : texte sans clé, la commande ajoute « R-<n> · » ; relance avec le même titre : rien de recréé ; garde-fou sur titre et corps)
    uv run tools/gh_issue.py close-step <clé> [--reason R]   (R-<n>/g<groupe>, R-<n>/t<tâche> ou R-<n>/u<k> ; --reason obligatoire hors étape utilisateur)
    uv run tools/gh_issue.py close-feature R-<n> [--edition-public]   (--edition-public : ajoute l'étiquette edition:public avant la fermeture, ou seule sur une feature déjà fermée ; edition-publish-tooling, D19)
    uv run tools/gh_issue.py new-idea --title T (--body B | --body-file F) [--milestone M] [--value 1|2|3] [--product mothra]   (idée : étiquette type:idea, marqueur roadmap-idea, jamais de Project ; --body et --body-file s'excluent, l'un des deux est obligatoire, le texte du fichier passe par le même garde-fou ; fichier absent, vide ou non ordinaire : code 2, rien d'envoyé ; jalon existant et étiquette value:N facultatifs ; change single-tracking-github, D7 ; #184)
    uv run tools/gh_issue.py edit-idea <n|#n> [--title T] [--milestone M] [--value 1|2|3] [--product mothra|none] [--body-file F]   (change le titre (non vide, marqueur conservé), le jalon, remplace l'étiquette value:N ou remplace le corps d'une idée par le texte de F, marqueur conservé, mêmes contrôles que new-idea ; refuse une issue sans type:idea ; #184)
    uv run tools/gh_issue.py comment-idea <n|#n> --body-file F   (commente une idée ; `comment` reste réservé aux R-<n> ; refuse une issue sans type:idea ; #244, point F)
    uv run tools/gh_issue.py close-idea <n|#n> [--comment-file F]   (ferme une idée, avec un commentaire facultatif posté avant ; refuse une issue sans type:idea ; #244, point F)
    uv run tools/gh_issue.py ensure-labels
    uv run tools/gh_issue.py ensure-milestone M [--closed]

Le dépôt est celui du remote `origin` (lu par `git remote get-url origin` dans la racine) et figure dans chaque chemin de
requête ; `--repo` ne sert qu'à le confirmer (un autre dépôt : code 2). `gh` tourne dans la racine du dépôt.
Garde-fou avant toute requête (D8) : noms sensibles du hook pre-commit (module partagé, liste locale), identifiants
personnels (scanner), motif de clé de ticket (deux majuscules au moins, un tiret, des chiffres ; les `R-<n>` passent).
Une trouvaille refuse la commande entière, rien n'est envoyé ; la sortie nomme le champ et la ligne, jamais la valeur.

Codes (D9) : 0 fait ou rien à faire ; 1 GitHub a refusé ; 2 usage ; 3 trouvaille du garde-fou ; 4 garde-fou impossible ;
5 GitHub injoignable ou non authentifié ; 6 scope `project` ou Project manquant ; 7 règle de la file ; 8 état inconnu
(une écriture sans réponse, ou GitHub perdu après des écritures confirmées). Sortie en anglais,
chaque ligne préfixée `gh_issue: `. Rien n'est mis en file pour plus tard. Jamais de suppression d'issue, d'étiquette ou de
jalon, jamais de transfert, de release ni de tag.

`gh` est remplaçable par la variable d'environnement PMZILLA_GH (chemin d'un exécutable), pour les tests. Chaque appel a
l'entrée standard fermée (sauf s'il envoie un corps), les invites désactivées (GH_PROMPT_DISABLED), une limite de temps
(PMZILLA_GH_TIMEOUT, 60 s) et une attente totale bornée sur les limites de débit (PMZILLA_GH_MAX_WAIT, 120 s).
Les fonctions de ce module sont la couche d'écriture de l'import initial, retiré depuis. Tests : tests/gh_issue.
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import roadmap_model as rm  # noqa: E402
import sensitive_names  # noqa: E402
import identifiants_personnels  # noqa: E402

RACINE = Path(__file__).resolve().parents[1]
PREFIX = "gh_issue: "
ENV_GH = "PMZILLA_GH"
PROJECT_TITLE = "PMZilla Lab roadmap"
TICKET_KEY = re.compile(r"(?<![A-Za-z0-9_])[A-Z]{2,}-\d+")
FENCE = re.compile(r"^```roadmap[ \t]*\n.*?^```[ \t]*$", re.S | re.M)
LABEL_COLORS = {"value": "bfd4f2", "type": "1f6feb", "theme": "0e8a16", "model": "5319e7", "parallel": "fbca04", "owner": "d93f0b", "edition": "c5def5",
                "product": "b60205"}
LABEL_DESCRIPTIONS = {"product:mothra": "Feature, task or idea of the Mothra product (no product: label means PMZilla)"}
PRODUCT_NONE = "none"        # --product none : retire le label product: (edit, edit-idea)
sleep = time.sleep           # remplaçable par les tests
now = time.time              # idem (limite de débit : X-Ratelimit-Reset)
SECONDARY_WAIT = 60          # attente minimale sur une limite secondaire
PAUSE = 1.0                  # secondes entre deux créations (PMZILLA_GH_PAUSE)
TIMEOUT = 60.0               # secondes par appel gh (PMZILLA_GH_TIMEOUT)
MAX_WAIT = 120.0             # secondes d'attente cumulées sur les limites de débit, par commande (PMZILLA_GH_MAX_WAIT)
VISIBILITY_DELAYS = (1, 2, 4, 8)   # écarts entre les 5 lectures qui attendent qu'une feature soit listée
CLOSE_MARKER = "<!-- roadmap-close -->"
REASON_MARKER = "<!-- roadmap-closed-with-reason -->"
SHOW_CMD = "uv run --with pyyaml python tools/roadmap.py show"


def env_float(name, default):
    try:
        v = float(os.environ.get(name, default))
    except ValueError:
        return default
    return v if v > 0 else default


class Stop(Exception):
    """Arrêt de la commande : code de sortie et lignes de message (sans préfixe)."""

    node_missing = False   # « Could not resolve to a node » : l'objet qu'on vient de créer n'est pas encore visible

    def __init__(self, code, *lines):
        super().__init__(" / ".join(lines))
        self.code = code
        self.lines = list(lines)


# --- Dépôt d'origine ----------------------------------------------------------------------------------------------

def git_origin_url():
    """URL de `origin` (lecture seule, dans la racine du dépôt) ; chaîne vide si elle manque."""
    try:
        p = subprocess.run(["git", "-C", str(RACINE), "remote", "get-url", "origin"], capture_output=True, text=True,
                           timeout=30, cwd=RACINE)
    except (OSError, subprocess.SubprocessError):
        return ""
    return p.stdout.strip() if p.returncode == 0 else ""


def git_head():
    """(branche courante ou None en tête détachée, commit court ou chaîne vide) ; lecture seule, dans la racine."""
    def run(*args):
        try:
            p = subprocess.run(["git", "-C", str(RACINE), *args], capture_output=True, text=True, timeout=30, cwd=RACINE,
                               stdin=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError):
            return ""
        return p.stdout.strip() if p.returncode == 0 else ""
    branch = run("rev-parse", "--abbrev-ref", "HEAD")
    return (None if branch in ("", "HEAD") else branch), run("rev-parse", "--short", "HEAD")


def current_release():
    """Release en cours d'après tools/roadmap_settings.yaml (D12) ; chaîne vide si le fichier manque ou si rien n'est réglé.
    Stop(7) si le fichier est invalide (rien n'a été envoyé)."""
    try:
        text = (RACINE / rm.SETTINGS_FILE).read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    except (OSError, UnicodeDecodeError):
        raise Stop(7, f"{rm.SETTINGS_FILE} is unreadable; nothing was sent") from None
    try:
        return rm.parse_settings(text)["current_release"]
    except ValueError:
        raise Stop(7, f"{rm.SETTINGS_FILE} is invalid; nothing was sent") from None


def strip_headers(out):
    """Retire les en-têtes HTTP que `gh api --include` place avant le corps."""
    if out.startswith("HTTP/"):
        mo = re.search(r"\r?\n\r?\n", out)
        return out[mo.end():] if mo else ""
    return out


# --- Garde-fou (D8) -----------------------------------------------------------------------------------------------

class Guard:
    def __init__(self, names, identifiers):
        self.motifs = sensitive_names.patterns(names)
        self.identifiers = [i.lower() for i in identifiers if i]

    @classmethod
    def load(cls, root=None):
        """Charge la liste et les identifiants ; échoue fermé (code 4)."""
        try:
            names = sensitive_names.load_names()
        except sensitive_names.SensitiveNamesUnavailable as e:
            cause = {"missing": "absent", "empty": "empty", "unreadable": "unreadable"}[e.reason]
            raise Stop(4, f"guard could not run: sensitive-names list {cause}") from None
        names = names + sensitive_names.extract_names()      # team-names-readable, D8 : jamais d'erreur, liste vide sans extrait
        try:
            ids = identifiants_personnels.identifiants(Path(root) if root else RACINE)
        except BaseException as e:   # SystemExit(2) du scanner compris
            if isinstance(e, KeyboardInterrupt):
                raise
            raise Stop(4, "guard could not run: identifier scanner failed") from None
        return cls(names, ids)

    def scan(self, fields):
        """fields : champ -> texte. Lève Stop(3) à la première trouvaille ; ne cite jamais la valeur ni la ligne."""
        for champ, texte in fields.items():
            for n, ligne in enumerate(str(texte).split("\n"), 1):
                if sensitive_names.line_matches(self.motifs, ligne):
                    kind = "sensitive name"
                elif any(i in ligne.lower() for i in self.identifiers):
                    kind = "personal identifier"
                elif TICKET_KEY.search(ligne):
                    kind = "ticket key"
                else:
                    continue
                raise Stop(3, f"refused: {kind} in {champ}, line {n}; nothing was sent")


# --- Client gh ----------------------------------------------------------------------------------------------------

class Client:
    def __init__(self, guard):
        self.guard = guard
        self._repo = None
        self.writes = 0          # écritures confirmées par GitHub
        self.writing = False     # une écriture est partie et n'a pas encore de réponse
        self.waited = 0          # secondes d'attente cumulées sur les limites de débit
        self.target = None       # feature sur laquelle porte la commande (pour la commande de vérification)
        self._labels = None
        self._milestones = None

    # exécution
    def wait_seconds(self, low, tentative):
        """Attente avant de rejouer après une limite de débit (Retry-After, X-Ratelimit-Reset ; 60 s au moins si secondaire)."""
        m = re.search(r"retry-after:\s*(\d+)", low)
        r = re.search(r"x-ratelimit-reset:\s*(\d+)", low)
        if m:
            wait = int(m.group(1))
        elif r:
            wait = max(0, int(r.group(1)) - int(now())) + 1
        else:
            wait = min(60, 2 ** tentative)
        if "secondary rate limit" in low:
            wait = max(SECONDARY_WAIT, wait)
        return min(wait, 3600)

    def refusal(self, p):
        """Ligne de refus de GitHub : le message passe par le garde ; une trouvaille ou l'absence de garde le retient."""
        brut = (p.stderr or "") + "\n" + strip_headers(p.stdout or "")
        mo = re.search(r"HTTP (\d{3})", brut)
        withheld = f"GitHub refused: HTTP {mo.group(1) if mo else '?'} (message withheld)"
        premiere = next((l.strip() for l in (p.stderr or "").splitlines() if l.strip()), "")
        if not premiere:
            try:
                d = json.loads(strip_headers(p.stdout or ""))
                premiere = str(((d.get("errors") or [{}])[0] or {}).get("message") or d.get("message") or "")
            except (ValueError, AttributeError, IndexError, TypeError):
                premiere = ""
        if self.guard is None:
            return withheld
        try:
            self.guard.scan({"GitHub message": brut})
        except Stop:
            return withheld
        return f"GitHub refused: {(premiere or 'no message')[:200]}"

    def check(self, retry):
        """Fin de message : comment vérifier ce que la commande a fait. `retry` : phrase de rejeu pour une feature."""
        if self.target:
            return f"check with {SHOW_CMD} {self.target}" + retry
        return "run the same command again, it is idempotent"

    def lost(self, note=""):
        """Arrêt quand GitHub ne répond plus : 5 avant toute écriture, 8 dès qu'une écriture est partie (D5)."""
        if self.writing:
            return Stop(8, f"state unknown: {self.writes} write(s) confirmed, the last write got no answer; "
                           + self.check(" before running the command again"))
        if self.writes:
            return Stop(8, f"state unknown: GitHub unreachable after {self.writes} confirmed write(s); "
                           + self.check(", then run the same command again"))
        return Stop(5, f"GitHub unreachable{note}; nothing was sent")

    def confirmed_line(self):
        """Deuxième ligne d'un refus (1) ou d'une erreur de scope (6) venus après des écritures confirmées."""
        return (f"{self.writes} write(s) were confirmed before this failure; "
                + self.check(""))

    def run(self, args, stdin=None):
        exe = os.environ.get(ENV_GH) or "gh"
        if args[:1] == ["api"]:
            args = ["api", "--include", *args[1:]]
        timeout = env_float("PMZILLA_GH_TIMEOUT", TIMEOUT)
        max_wait = env_float("PMZILLA_GH_MAX_WAIT", MAX_WAIT)
        opts = {"input": stdin} if stdin is not None else {"stdin": subprocess.DEVNULL}
        env = {**os.environ, "GH_PROMPT_DISABLED": "1"}
        for tentative in range(5):
            try:
                p = subprocess.run([exe, *args], capture_output=True, text=True, timeout=timeout, cwd=RACINE, env=env,
                                   **opts)
            except FileNotFoundError:
                raise Stop(5, "gh not found; install the GitHub CLI") from None
            except subprocess.TimeoutExpired:
                raise self.lost(f" (no answer within {timeout:g} s)") from None
            if p.returncode == 0:
                return strip_headers(p.stdout) if args[:1] == ["api"] else p.stdout
            stderr = (p.stderr or "").lower()
            raw = stderr + "\n" + (p.stdout or "").lower()                      # les en-têtes ne servent qu'à l'attente
            low = stderr + "\n" + strip_headers(p.stdout or "").lower()         # classement : erreur standard et corps (D4)
            if "gh auth login" in low or "not logged in" in low or "http 401" in low or "bad credentials" in low:
                raise Stop(5, "not authenticated; run gh auth login in the Terminal")
            if "required scopes" in low or "insufficient_scopes" in low:
                raise Stop(6, "missing token scope project; run gh auth refresh -s project in the Terminal")
            if "could not resolve to a node" in low:
                err = Stop(1, self.refusal(p))
                err.node_missing = True
                raise err
            if any(m in stderr for m in ("could not resolve host", "no such host", "dial tcp", "timed out", "timeout",
                                         "connection refused", "network is unreachable", "error connecting")):
                raise self.lost()
            if "rate limit" in low or "http 429" in low:
                wait = self.wait_seconds(raw, tentative)
                if self.waited + wait > max_wait:
                    if self.writes:
                        raise Stop(8, f"state unknown: GitHub unreachable after {self.writes} confirmed write(s); "
                                      + self.check(", then run the same command again"))
                    raise Stop(5, f"GitHub rate limit: {wait} s to wait is over the allowed wait; nothing was sent")
                self.waited += wait
                sleep(wait)
                continue
            raise Stop(1, self.refusal(p))
        raise Stop(1, "GitHub refused: rate limit still active after retries")

    def repo(self):
        if self._repo is None:
            self._repo = rm.repo_from_url(git_origin_url())
            if self._repo is None:
                raise Stop(2, "usage: the origin remote is missing or is not a GitHub repository")
        return self._repo

    def owner(self):
        return self.repo().split("/")[0]

    # lectures (aucun texte envoyé)
    def get(self, path):
        out = self.run(["api", f"repos/{self.repo()}/{path}"])
        return json.loads(out) if out.strip() else None

    def get_all(self, path):
        sep = "&" if "?" in path else "?"
        resultat, page = [], 1
        while True:
            lot = self.get(f"{path}{sep}per_page=100&page={page}") or []
            resultat.extend(lot)
            if len(lot) < 100:
                return resultat
            page += 1

    def graphql_read(self, query, variables):
        out = self.run(["api", "graphql", "--input", "-"], json.dumps({"query": query, "variables": variables}))
        return json.loads(out)

    # écritures : toujours après le garde-fou
    def send(self, method, path, payload, texts):
        if self.guard is None:
            raise Stop(4, "guard could not run: no guard loaded")
        self.guard.scan(texts)
        self.writing = True
        try:
            out = self.run(["api", "-X", method, f"repos/{self.repo()}/{path}", "--input", "-"], json.dumps(payload))
        finally:
            self.writing = False
        self.writes += 1
        self.pace()
        return json.loads(out) if out.strip() else None

    def graphql_write(self, query, variables, texts):
        if self.guard is None:
            raise Stop(4, "guard could not run: no guard loaded")
        self.guard.scan(texts)
        self.writing = True
        try:
            out = self.run(["api", "graphql", "--input", "-"], json.dumps({"query": query, "variables": variables}))
        finally:
            self.writing = False
        self.writes += 1
        self.pace()
        return json.loads(out)

    def pace(self):
        pause = float(os.environ.get("PMZILLA_GH_PAUSE", PAUSE))
        if pause > 0:
            sleep(pause)

    # étiquettes et jalons
    def labels(self):
        if self._labels is None:
            self._labels = {l["name"] for l in self.get_all("labels")}
        return self._labels

    def milestones(self):
        if self._milestones is None:
            self._milestones = {m["title"]: m for m in self.get_all("milestones?state=all")}
        return self._milestones


# --- Instantané des issues ----------------------------------------------------------------------------------------

class Snapshot:
    def __init__(self, issues):
        self.issues = [i for i in issues if "pull_request" not in i]
        self.by_key = {}
        for i in self.issues:
            k = rm.parse_marker(i.get("body") or "")
            if k:
                self.by_key.setdefault(k, []).append(i)
        self.by_number = {i["number"]: i for i in self.issues}

    def get(self, key):
        lst = self.by_key.get(key)
        return lst[0] if lst else None

    def max_id(self):
        best = 0
        for i in self.issues:
            p = rm.parse_title(i.get("title") or "")
            if p:
                best = max(best, p[0])
            k = rm.parse_marker(i.get("body") or "")
            if k:
                best = max(best, rm.parse_key(k)[1])
        return best

    def features(self):
        return [(k, v[0]) for k, v in self.by_key.items() if rm.parse_key(k)[0] == "feature"]

    def add(self, issue):
        self.issues.append(issue)
        self.by_number[issue["number"]] = issue
        k = rm.parse_marker(issue.get("body") or "")
        if k:
            self.by_key.setdefault(k, []).append(issue)


def load_snapshot(client):
    return Snapshot(client.get_all("issues?state=all"))


def label_names(issue):
    return [l["name"] if isinstance(l, dict) else l for l in issue.get("labels", [])]


# --- Opérations d'écriture ----------------------------------------------------------------------------------------

def ensure_label(client, name):
    if name in client.labels():
        return False
    color = LABEL_COLORS.get(name.split(":")[0], "ededed")
    payload = {"name": name, "color": color}
    if name in LABEL_DESCRIPTIONS:
        payload["description"] = LABEL_DESCRIPTIONS[name]
    client.send("POST", "labels", payload, {"label": name, **({"description": payload["description"]} if "description" in payload else {})})
    client.labels().add(name)
    return True


def ensure_milestone(client, title, closed=False):
    """Crée le jalon s'il manque (fermé d'emblée si `closed`) ; ne change jamais un jalon existant."""
    if title in client.milestones():
        return False
    m = client.send("POST", "milestones", {"title": title, "state": "closed" if closed else "open"}, {"milestone": title})
    client.milestones()[title] = m
    return True


def milestone_number(client, title):
    m = client.milestones().get(title)
    if m is None:
        raise Stop(7, "unknown milestone")
    return m["number"]


def create_issue(client, snap, key, title, body, labels, milestone=None):
    """(issue, créée). Une issue dont le marqueur existe n'est pas recréée."""
    existing = snap.get(key)
    if existing:
        return existing, False
    for l in labels:
        ensure_label(client, l)
    payload = {"title": title, "body": body, "labels": list(labels)}
    if milestone:
        payload["milestone"] = milestone_number(client, milestone)
    texts = {"title": title, "body": body, "labels": "\n".join(labels)}
    if milestone:
        texts["milestone"] = milestone
    issue = client.send("POST", "issues", payload, texts)
    snap.add(issue)
    return issue, True


def patch_issue(client, number, payload, texts):
    return client.send("PATCH", f"issues/{number}", payload, texts)


def close_issue(client, issue, reason="completed"):
    if issue.get("state") == "closed":
        return False
    patch_issue(client, issue["number"], {"state": "closed", "state_reason": reason}, {})
    issue["state"] = "closed"
    return True


def reopen_issue(client, issue):
    if issue.get("state") != "closed":
        return False
    patch_issue(client, issue["number"], {"state": "open"}, {})
    issue["state"] = "open"
    return True


def issue_comments(client, number):
    return [c.get("body") or "" for c in client.get_all(f"issues/{number}/comments")]


def has_comment(client, number, marker):
    return any(b.lstrip().startswith(marker) for b in issue_comments(client, number))


def issue_milestone(issue):
    return (issue.get("milestone") or {}).get("title")


def set_milestone(client, issue, title):
    """Fixe le jalon de l'issue s'il diffère ; True si une requête est partie. Le texte du jalon passe par le garde."""
    if issue_milestone(issue) == title:
        return False
    number = milestone_number(client, title)
    patch_issue(client, issue["number"], {"milestone": number}, {"milestone": title})
    issue["milestone"] = {"title": title, "number": number}
    return True


def sub_issues(client, parent_number):
    return client.get_all(f"issues/{parent_number}/sub_issues")


def sub_issue_numbers(client, parent_number):
    return {i["number"] for i in client.get_all(f"issues/{parent_number}/sub_issues")}


def add_sub_issue(client, parent, child):
    client.send("POST", f"issues/{parent['number']}/sub_issues", {"sub_issue_id": child["id"]}, {})


def blocker_numbers(client, number):
    return {i["number"] for i in client.get_all(f"issues/{number}/dependencies/blocked_by")}


def add_blocked_by(client, issue, blocker):
    client.send("POST", f"issues/{issue['number']}/dependencies/blocked_by", {"issue_id": blocker["id"]}, {})


def remove_blocked_by(client, issue, blocker):
    client.send("DELETE", f"issues/{issue['number']}/dependencies/blocked_by/{blocker['id']}", {}, {})


# --- Project (GraphQL) --------------------------------------------------------------------------------------------

Q_PROJECTS = """query($login: String!) { repositoryOwner(login: $login) { ... on ProjectV2Owner { projectsV2(first: 50) {
 nodes { id title fields(first: 30) { nodes { ... on ProjectV2SingleSelectField { id name options { id name } } } } } } } } }"""
Q_ITEMS = """query($project: ID!, $after: String) { node(id: $project) { ... on ProjectV2 { items(first: 100, after: $after) {
 pageInfo { hasNextPage endCursor } nodes { id content { ... on Issue { number } }
 fieldValueByName(name: "Status") { ... on ProjectV2ItemFieldSingleSelectValue { name } } } } } } }"""
M_ADD = "mutation($project: ID!, $content: ID!) { addProjectV2ItemById(input: {projectId: $project, contentId: $content}) { item { id } } }"
M_SET = """mutation($project: ID!, $item: ID!, $field: ID!, $option: String!) { updateProjectV2ItemFieldValue(input:
 {projectId: $project, itemId: $item, fieldId: $field, value: {singleSelectOptionId: $option}}) { projectV2Item { id } } }"""


class Project:
    def __init__(self, client, title=PROJECT_TITLE):
        self.client, self.title = client, title
        data = client.graphql_read(Q_PROJECTS, {"login": client.owner()})
        nodes = (((data.get("data") or {}).get("repositoryOwner") or {}).get("projectsV2") or {}).get("nodes") or []
        found = [n for n in nodes if n and n.get("title") == title]
        status = None
        if found:
            status = next((f for f in found[0]["fields"]["nodes"] if f and f.get("name") == "Status"), None)
        if not found or status is None or not set(rm.STATUSES) <= {o["name"] for o in status["options"]}:
            raise Stop(6, "Project not found or Status options incomplete")
        self.id, self.field_id = found[0]["id"], status["id"]
        self.options = {o["name"]: o["id"] for o in status["options"]}
        self._items = None

    def items(self):
        """numéro d'issue -> (identifiant d'item, Status ou None)."""
        if self._items is None:
            self._items, after = {}, None
            while True:
                d = self.client.graphql_read(Q_ITEMS, {"project": self.id, "after": after})
                page = d["data"]["node"]["items"]
                for n in page["nodes"]:
                    c = n.get("content") or {}
                    if "number" in c:
                        v = n.get("fieldValueByName") or {}
                        self._items[c["number"]] = (n["id"], v.get("name"))
                if not page["pageInfo"]["hasNextPage"]:
                    break
                after = page["pageInfo"]["endCursor"]
        return self._items

    def add_item(self, issue):
        """Ajoute l'issue au Project ; rejoue (écarts de VISIBILITY_DELAYS) tant que GitHub ne la résout pas encore."""
        for delay in (*VISIBILITY_DELAYS, None):
            try:
                return self.client.graphql_write(M_ADD, {"project": self.id, "content": issue["node_id"]}, {})
            except Stop as s:
                if not s.node_missing or delay is None:
                    raise
            sleep(delay)

    def ensure_status(self, issue, status):
        """Ajoute l'issue au Project si besoin et fixe le Status ; True si une requête est partie."""
        it = self.items().get(issue["number"])
        sent = False
        if it is None:
            d = self.add_item(issue)
            it = (d["data"]["addProjectV2ItemById"]["item"]["id"], None)
            sent = True
        if it[1] != status:
            self.client.graphql_write(M_SET, {"project": self.id, "item": it[0], "field": self.field_id,
                                              "option": self.options[status]}, {})
            sent = True
        self.items()[issue["number"]] = (it[0], status)
        return sent


# --- Bodies et plans ----------------------------------------------------------------------------------------------

def today():
    brut = os.environ.get("ROADMAP_TODAY")
    return brut if brut else datetime.date.today().isoformat()


def feature_body(key, block, text=None):
    corps = f"{rm.marker(key)}\n\n{rm.render_block(block)}"
    return corps + (f"\n\n{text}" if text else "")


def replace_block(body, block):
    return FENCE.sub(lambda _: rm.render_block(block), body, count=1)


def subissue_plan(n, change, groups):
    """Sous-issues d'après les groupes taggés (D3) : clé, titre, étiquettes, corps, complet, genre."""
    plan = []
    for g in groups:
        key = rm.group_key(n, g.number)
        body = f"{rm.marker(key)}\n\nChange: {change}\nGroup: {g.number}"
        if g.kind == "agent":
            labels = [rm.LABEL_TASK, rm.label_model(g.model)] + ([rm.LABEL_PARALLEL] if g.parallel else [])
            plan.append({"key": key, "title": rm.group_title(n, g.number, g.title), "labels": labels, "body": body,
                         "complete": rm.group_complete(g), "kind": "agent"})
            for t in rm.user_tasks(g):
                tk = rm.task_key(n, t.id)
                plan.append({"key": tk, "title": rm.user_task_title(n, t.id), "labels": [rm.LABEL_TASK, rm.LABEL_USER],
                             "body": f"{rm.marker(tk)}\n\nChange: {change}\nTask: {t.id}", "complete": rm.task_complete(t),
                             "kind": "user-task"})
        else:
            plan.append({"key": key, "title": rm.group_title(n, g.number, g.title), "labels": [rm.LABEL_TASK, rm.LABEL_USER],
                         "body": body, "complete": rm.group_complete(g), "kind": "user-group"})
    return plan


def tasks_path(change):
    """tasks.md d'un change ouvert, ou archivé (chemin d'archive complet ou nom seul) ; None s'il est introuvable."""
    base = RACINE / "openspec" / "changes"
    for c in (base / change / "tasks.md", RACINE / change / "tasks.md"):
        if c.is_file():
            return c
    trouves = sorted((base / "archive").glob(f"*-{change}/tasks.md"))
    return trouves[-1] if trouves else None


# --- Contexte de commande -----------------------------------------------------------------------------------------

class Ctx:
    def __init__(self, client):
        self.client = client
        self.out = []
        self._snap = None
        self._project = None

    def say(self, line):
        self.out.append(line)

    @property
    def snap(self):
        if self._snap is None:
            self._snap = load_snapshot(self.client)
        return self._snap

    @property
    def project(self):
        if self._project is None:
            self._project = Project(self.client)
        return self._project

    def feature(self, key):
        parse = _parse_feature_key(key)
        issue = self.snap.get(parse)
        if issue is None and rm.parse_key(parse)[1] > self.snap.max_id():
            for delay in VISIBILITY_DELAYS:      # peut-être créée à l'instant : la liste de GitHub a du retard
                sleep(delay)
                self._snap = load_snapshot(self.client)
                issue = self._snap.get(parse)
                if issue is not None:
                    break
        if issue is None or rm.parse_key(parse)[0] != "feature":
            raise Stop(7, f"unknown identifier {key}")
        return issue

    def block_of(self, issue):
        try:
            return rm.parse_block(issue.get("body") or "")
        except rm.BlockError:
            raise Stop(7, f"invalid block: {rm.parse_marker(issue.get('body') or '')}") from None


def _parse_feature_key(key):
    if not re.fullmatch(r"R-\d+", key or ""):
        raise Stop(2, "usage: expected an identifier like R-12")
    return key


# --- Sous-commandes -----------------------------------------------------------------------------------------------

def parse_sets(sets):
    out = {}
    for s in sets or []:
        k, sep, v = s.partition("=")
        if not sep or k not in rm.KEYS:
            raise Stop(2, "usage: --set expects key=value with a known block key")
        out[k] = int(v) if k == "rank" and v.isdigit() else v
    return out


def invalid_block(block, is_open, key=None):
    pb = rm.validate_block(block, is_open=is_open, marker_key=key)
    if pb:
        raise Stop(7, "invalid block: " + ", ".join(sorted({p.split(" :")[0] for p in pb})))


def open_ranks(snap, ignore=None):
    ranks = {}
    for k, i in snap.features():
        if i.get("state") != "open" or k == ignore:
            continue
        try:
            r = rm.parse_block(i.get("body") or "").get("rank")
        except rm.BlockError:
            continue
        if isinstance(r, int):
            ranks[r] = k
    return ranks


def await_listed(client, key, issue):
    """Relit la liste jusqu'à ce que la feature créée y figure (5 lectures espacées) ; sinon code 8 (D6)."""
    for delay in (*VISIBILITY_DELAYS, None):
        issues = client.get_all("issues?state=all")
        if any(rm.parse_marker(i.get("body") or "") == key for i in issues if "pull_request" not in i):
            return
        if delay is not None:
            sleep(delay)
    raise Stop(8, f"state unknown: created {key} (#{issue['number']}) but GitHub does not list it yet; "
                  f"wait before the next new-feature, then check with {SHOW_CMD} {key}")


def with_product(labels, product):
    """Étiquettes avec le label `product:` demandé : `none` le retire, une valeur le pose à la place de tout autre label `product:`."""
    rest = [l for l in labels if not l.startswith(rm.LABEL_PRODUCT_PREFIX)]
    return rest if product == PRODUCT_NONE else rest + [rm.label_product(product)]


def cmd_new_feature(ctx, a):
    snap, client = ctx.snap, ctx.client
    if a.theme not in rm.THEMES:
        raise Stop(2, "usage: --theme must be one of " + ", ".join(rm.THEMES))
    n = snap.max_id() + 1
    key = rm.feature_key(n)
    client.target = key
    block = {"id": key, "theme": a.theme, "estimate": "tbd", "method": "direct-prompt", "model": "tbd", "conditions": ""}
    block.update(parse_sets(a.set))
    block["id"] = key
    block["theme"] = a.theme
    ranks = open_ranks(snap)
    if "rank" not in block:
        block["rank"] = (max(ranks) if ranks else 0) + 10
    elif block["rank"] in ranks:
        raise Stop(7, f"rank already used by {ranks[block['rank']]}")
    invalid_block(block, True, key)
    blockers = [b for b in (a.blocked_by or "").split(",") if b]
    blocker_issues = [ctx.feature(b) for b in blockers]
    title = rm.feature_title(n, a.title)
    body = feature_body(key, block)
    labels = [rm.LABEL_FEATURE, rm.label_theme(a.theme)]
    if a.product:
        labels.append(rm.label_product(a.product))
    client.guard.scan({"title": title, "body": body, "labels": "\n".join(labels), "milestone": a.milestone})
    project = ctx.project
    milestone_number(client, a.milestone)
    issue, _ = create_issue(client, snap, key, title, body, labels, a.milestone)
    await_listed(client, key, issue)
    for b in blocker_issues:
        add_blocked_by(client, issue, b)
    project.ensure_status(issue, "Todo")
    ctx.say(f"created {key} (#{issue['number']})")


def cmd_edit(ctx, a):
    issue = ctx.feature(a.key)
    key, client = a.key, ctx.client
    n = rm.parse_key(key)[1]
    block = ctx.block_of(issue)
    sets = parse_sets(a.set)
    sets.pop("id", None)
    block.update(sets)
    invalid_block(block, issue.get("state") == "open", key)
    if "rank" in sets and sets["rank"] in open_ranks(ctx.snap, ignore=key):
        raise Stop(7, f"rank already used by {open_ranks(ctx.snap, ignore=key)[sets['rank']]}")
    payload, texts = {}, {}
    if a.title is not None:
        # --title prend le texte sans clé ; la commande ajoute « R-n · » (comme new-feature) ; un titre déjà préfixé est refusé
        if not a.title.strip():
            raise Stop(2, "usage: --title must not be empty")
        if re.match(rf"\s*R-\d+\s*{rm.SEP}", a.title):
            raise Stop(2, f"usage: --title takes the text without the R-<n> {rm.SEP} prefix, the command adds it")
        new_title = rm.feature_title(n, a.title.strip())
        if new_title != issue.get("title"):
            payload["title"] = texts["title"] = new_title
    body = replace_block(issue.get("body") or "", block)
    if body != issue.get("body"):
        payload["body"] = body
        texts["body"] = body
    labels = label_names(issue)
    relabel = False
    if "theme" in sets:
        labels = [l for l in labels if not l.startswith("theme:")] + [rm.label_theme(block["theme"])]
        relabel = True
    if a.product is not None:
        labels = with_product(labels, a.product)
        relabel = relabel or sorted(labels) != sorted(label_names(issue))
    if relabel:
        payload["labels"] = labels
        texts["labels"] = "\n".join(labels)
    if a.milestone is not None:
        texts["milestone"] = a.milestone
    client.guard.scan(texts)
    if a.milestone is not None:
        if issue.get("state") == "open" and client.milestones().get(a.milestone, {}).get("state") == "closed":
            raise Stop(7, "closed milestone: an open feature cannot move to it")
        payload["milestone"] = milestone_number(client, a.milestone)
    if not payload:
        ctx.say("nothing to do")
        return
    if "labels" in payload:
        for l in payload["labels"]:
            ensure_label(client, l)
    patch_issue(client, issue["number"], payload, texts)
    ctx.say(f"edited {key} (#{issue['number']})")
    if a.milestone is not None:
        moved = sum(set_milestone(client, sub, a.milestone) for sub in sub_issues(client, issue["number"]))
        if moved:
            ctx.say(f"moved {moved} sub-issue(s) to {a.milestone}")


def move_to_release(ctx, issue, key):
    """D12 : la feature et ses sous-issues (ouvertes ou fermées) passent dans la release en cours, avant le Status.
    Refus (7) avant toute écriture si la release n'est pas un jalon ouvert."""
    client = ctx.client
    release = current_release()
    if not release:
        ctx.say("no current release; milestone unchanged")
        return
    if client.milestones().get(release, {}).get("state") != "open":
        raise Stop(7, f"current release {release} is not an open milestone; nothing was sent")
    client.guard.scan({"milestone": release})
    subs = sub_issues(client, issue["number"])
    late = [s for s in subs if issue_milestone(s) != release]
    feature_moved = issue_milestone(issue) != release
    if not feature_moved and not late:
        return
    if feature_moved:
        set_milestone(client, issue, release)
    for sub in late:
        set_milestone(client, sub, release)
    if feature_moved:
        ctx.say(f"moved {key} and {len(late)} sub-issue(s) to {release}")
    else:
        ctx.say(f"moved {len(late)} sub-issue(s) of {key} to {release}")


def cmd_status(ctx, a):
    issue = ctx.feature(a.key)
    if a.status not in rm.STATUSES:
        raise Stop(2, "usage: status must be one of " + ", ".join(rm.STATUSES))
    project = ctx.project
    sent = False
    if a.status == "In progress":
        move_to_release(ctx, issue, a.key)
        block = ctx.block_of(issue)
        if "started_on" not in block:
            block["started_on"] = today()
            body = replace_block(issue.get("body") or "", block)
            ctx.client.guard.scan({"body": body})
            patch_issue(ctx.client, issue["number"], {"body": body}, {"body": body})
            issue["body"] = body
            sent = True
    sent = project.ensure_status(issue, a.status) or sent
    ctx.say(f"status {a.key} {a.status}" if sent else "nothing to do")


def reaches(client, snap, start, target, path=None, seen=None):
    """Chemin de `start` à `target` en suivant les relations « blocked by », ou None."""
    path, seen = (path or [start]), (seen if seen is not None else set())
    if start == target:
        return path
    seen.add(start)
    issue = snap.get(start)
    if issue is None:
        return None
    for num in sorted(blocker_numbers(client, issue["number"])):
        nxt = snap.by_number.get(num)
        k = rm.parse_marker((nxt or {}).get("body") or "") if nxt else None
        if k and k not in seen:
            r = reaches(client, snap, k, target, path + [k], seen)
            if r:
                return r
    return None


def cmd_block(ctx, a, remove=False):
    issue, blocker = ctx.feature(a.key), ctx.feature(a.by)
    client = ctx.client
    if a.key == a.by:
        raise Stop(7, f"dependency cycle: {a.key} -> {a.key}")
    have = blocker_numbers(client, issue["number"])
    if remove:
        if blocker["number"] not in have:
            ctx.say("nothing to do")
            return
        remove_blocked_by(client, issue, blocker)
        ctx.say(f"unblocked {a.key} from {a.by}")
        return
    if blocker["number"] in have:
        ctx.say("nothing to do")
        return
    cycle = reaches(client, ctx.snap, a.by, a.key)
    if cycle:
        raise Stop(7, "dependency cycle: " + " -> ".join([a.key] + cycle))
    add_blocked_by(client, issue, blocker)
    ctx.say(f"blocked {a.key} by {a.by}")


def cmd_comment(ctx, a):
    issue = ctx.feature(a.key)
    try:
        texte = Path(a.body_file).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        raise Stop(2, "usage: --body-file must name a readable text file") from None
    ctx.client.send("POST", f"issues/{issue['number']}/comments", {"body": texte}, {"comment": texte})
    ctx.say(f"commented {a.key}")


def sync_plan(ctx, feature_issue, key, required=True):
    block = ctx.block_of(feature_issue)
    change = block.get("change")
    if not change:
        if required:
            raise Stop(7, f"no change for {key}")
        return None
    path = tasks_path(change)
    if path is None:
        if required:
            raise Stop(7, f"tasks.md not found for change of {key}")
        return None
    if "archive" in path.parts:
        if required:
            raise Stop(7, f"change archived for {key}; its sub-issues were synchronised before the archiving")
        return None   # change archivé : ses sous-issues ont été synchronisées avant l'archivage (tasks.md sans tags possibles)
    try:
        groups = rm.parse_tasks(path.read_text(encoding="utf-8"), change)
    except rm.PlanError as e:
        raise Stop(7, f"tasks.md groups untagged: {', '.join(str(x) for x in e.untagged)} (change {e.change})") from None
    return subissue_plan(rm.parse_key(key)[1], change, groups)


def do_sync(ctx, key, issue, required=True):
    plan = sync_plan(ctx, issue, key, required)
    if plan is None:
        return 0
    client, snap = ctx.client, ctx.snap
    product = [l for l in label_names(issue) if l in {rm.label_product(x) for x in rm.PRODUCTS}]   # la feature donne son produit à ses tâches
    for p in plan:
        p["labels"] = p["labels"] + product
    fields = {}
    for p in plan:
        fields[f"{p['key']} title"] = p["title"]
        fields[f"{p['key']} body"] = p["body"]
        fields[f"{p['key']} labels"] = "\n".join(p["labels"])
    client.guard.scan(fields)
    linked = sub_issue_numbers(client, issue["number"])
    milestone = issue_milestone(issue)
    changed = 0
    for p in plan:
        sub, created = create_issue(client, snap, p["key"], p["title"], p["body"], p["labels"], milestone)
        if created:
            changed += 1
            ctx.say(f"created {p['key']} (#{sub['number']})")
        if sub["number"] not in linked:
            add_sub_issue(client, issue, sub)
            linked.add(sub["number"])
            changed += 0 if created else 1
        if milestone and set_milestone(client, sub, milestone):
            changed += 1
            ctx.say(f"set milestone {milestone} on {p['key']}")
        if p["kind"] == "user-group":
            if p["complete"] and sub.get("state") == "open":
                ctx.say(f"ready to close after your confirmation: {p['key']}")
            continue
        if p["complete"] and close_issue(client, sub):
            changed += 1
            ctx.say(f"closed {p['key']}")
        elif (not p["complete"] and sub.get("state") == "closed" and not has_comment(client, sub["number"], REASON_MARKER)
              and reopen_issue(client, sub)):
            changed += 1
            ctx.say(f"reopened {p['key']}")
    return changed


def cmd_sync_tasks(ctx, a):
    issue = ctx.feature(a.key)
    if do_sync(ctx, a.key, issue) == 0:
        ctx.say("nothing to do")


def cmd_close_step(ctx, a):
    try:
        kind = rm.parse_key(a.key)[0]
    except ValueError:
        raise Stop(2, "usage: close-step expects R-<n>/g<group>, R-<n>/t<task> or R-<n>/u<k>") from None
    if kind == "feature":
        raise Stop(2, "usage: close-step expects R-<n>/g<group>, R-<n>/t<task> or R-<n>/u<k>")
    issue = ctx.snap.get(a.key)
    if issue is None:
        raise Stop(7, f"unknown identifier {a.key}")
    reason = (a.reason or "").strip()
    is_user = rm.LABEL_USER in label_names(issue)
    if not is_user and not reason:
        raise Stop(7, f"{a.key} is an agent sub-issue; close it with --reason after the user's confirmation")
    client = ctx.client
    posted = False
    if reason:
        text = f"{REASON_MARKER}\nClosed with a reason: {reason}"
        client.guard.scan({"comment": text})
        if not has_comment(client, issue["number"], REASON_MARKER):
            client.send("POST", f"issues/{issue['number']}/comments", {"body": text}, {"comment": text})
            posted = True
    closed = close_issue(client, issue)
    ctx.say(f"closed {a.key}" if closed else ("nothing to do" if not posted else f"reason recorded on {a.key}"))


def cmd_new_task(ctx, a):
    """Tâche utilisateur autonome R-<n>/u<k> (sans tasks.md) : type:task + owner:user (+ produit de la feature), sous-issue de la
    feature, dans son jalon sauf --milestone ; idempotente sur le titre."""
    feature = ctx.feature(a.key)
    n = rm.parse_key(a.key)[1]
    if not a.title.strip():
        raise Stop(2, "usage: --title must not be empty")
    if re.match(rf"\s*R-\d+\s*{rm.SEP}", a.title):
        raise Stop(2, f"usage: --title takes the text without the R-<n> {rm.SEP} prefix, the command adds it")
    texte = read_body_file(a.body_file)
    title = rm.feature_title(n, a.title.strip())
    key = None
    taken = 0
    for k, issues in ctx.snap.by_key.items():
        kind, kn, k_id = rm.parse_key(k)
        if kind == "user-task" and kn == n:
            taken = max(taken, int(k_id))
            if issues[0].get("title") == title and key is None:
                key = k
    new_key = rm.user_task_key(n, taken + 1)
    body = f"{rm.marker(new_key)}\n\n{texte.strip()}"
    labels = [rm.LABEL_TASK, rm.LABEL_USER] + [l for l in label_names(feature) if l in {rm.label_product(x) for x in rm.PRODUCTS}]
    milestone = a.milestone or issue_milestone(feature)
    texts = {"title": title, "body": body, "labels": "\n".join(labels)}
    if milestone:
        texts["milestone"] = milestone
    ctx.client.guard.scan(texts)
    if milestone:
        milestone_number(ctx.client, milestone)
    if key is not None:
        issue = ctx.snap.get(key)
        if issue["number"] not in sub_issue_numbers(ctx.client, feature["number"]):
            add_sub_issue(ctx.client, feature, issue)
            ctx.say(f"linked {key} (#{issue['number']}) to {a.key}")
        else:
            ctx.say(f"already exists: {key} (#{issue['number']})")
        return
    issue, _ = create_issue(ctx.client, ctx.snap, new_key, title, body, labels, milestone)
    add_sub_issue(ctx.client, feature, issue)
    ctx.say(f"created {new_key} (#{issue['number']})")


def cmd_close_feature(ctx, a):
    issue = ctx.feature(a.key)
    client = ctx.client
    block = ctx.block_of(issue)
    project = ctx.project
    had_done = bool(block.get("done_on"))
    new_body = None
    branch, short = git_head()
    if branch:
        comment = f"{CLOSE_MARKER}\nClosed on branch {branch}, before the merge; the user merges with bash tools/finish_branch.sh."
    else:
        comment = f"{CLOSE_MARKER}\nClosed outside a branch (detached HEAD at {short or 'unknown'}), before the merge."
    fields = {"comment": comment}
    labels_now = label_names(issue)
    new_labels = None
    if getattr(a, "edition_public", False) and rm.LABEL_EDITION_PUBLIC not in labels_now:
        new_labels = labels_now + [rm.LABEL_EDITION_PUBLIC]
        fields["labels"] = "\n".join(new_labels)
    if "done_on" not in block:
        block["done_on"] = today()
        new_body = replace_block(issue.get("body") or "", block)
        fields["body"] = new_body
    client.guard.scan(fields)      # le refus du garde précède toute écriture, synchronisation comprise
    do_sync(ctx, a.key, issue, required=False)
    subs = client.get_all(f"issues/{issue['number']}/sub_issues")
    open_subs = [rm.parse_marker(s.get("body") or "") or f"#{s['number']}" for s in subs if s.get("state") == "open"]
    if open_subs:
        raise Stop(7, "open sub-issues remain: " + ", ".join(sorted(open_subs)))
    if new_labels is not None:      # l'étiquette précède l'état, le commentaire et le statut (D19)
        patch_issue(client, issue["number"], {"labels": new_labels}, {"labels": "\n".join(new_labels)})
        issue["labels"] = [{"name": n} for n in new_labels]
        ctx.say(f"label {rm.LABEL_EDITION_PUBLIC} added to {a.key}")
    if issue.get("state") == "closed" and had_done and project.items().get(issue["number"], (0, None))[1] == "Done":
        if has_comment(client, issue["number"], CLOSE_MARKER):
            if new_labels is None:
                ctx.say("nothing to do")
        else:      # rejeu d'une fermeture interrompue avant le commentaire : il est posté une fois, jamais en double
            client.send("POST", f"issues/{issue['number']}/comments", {"body": comment}, {"comment": comment})
            ctx.say(f"closing comment recorded on {a.key}")
        return
    if new_body is not None:
        client.send("PATCH", f"issues/{issue['number']}", {"body": new_body}, {"body": new_body})
        issue["body"] = new_body
    project.ensure_status(issue, "Done")
    if not has_comment(client, issue["number"], CLOSE_MARKER):
        client.send("POST", f"issues/{issue['number']}/comments", {"body": comment}, {"comment": comment})
    close_issue(client, issue)
    ctx.say(f"closed {a.key}")
    unblocked = []
    for dep in client.get_all(f"issues/{issue['number']}/dependencies/blocking"):
        full = ctx.snap.by_number.get(dep["number"], dep)
        k = rm.parse_marker(full.get("body") or "")
        if full.get("state") != "open" or not k:
            continue
        if all((ctx.snap.by_number.get(b) or {}).get("state") == "closed" or b == issue["number"]
               for b in blocker_numbers(client, full["number"])):
            unblocked.append(k)
    ctx.say("unblocked: " + (", ".join(sorted(unblocked, key=lambda x: rm.parse_key(x)[1])) if unblocked else "none"))


def cmd_new_idea(ctx, a):
    """Enregistre une idée (D7) : une issue étiquetée type:idea, sans jalon, Project, statut ni bloc ; idempotente sur le slug."""
    slug = rm.idea_slug(a.title)
    texte = read_body_file(a.body_file) if a.body_file is not None else (a.body or "")
    if not a.title.strip() or not texte.strip() or not slug:
        raise Stop(2, "usage: new-idea needs a non-empty --title with letters or digits, and a non-empty --body or --body-file")
    body = f"{rm.idea_marker(slug)}\n\n{texte.strip()}"
    labels = [rm.LABEL_IDEA] + ([idea_value_label(a.value)] if a.value else []) + ([rm.label_product(a.product)] if a.product else [])
    texts = {"title": a.title, "body": body, "labels": "\n".join(labels)}
    if a.milestone:
        texts["milestone"] = a.milestone
    ctx.client.guard.scan(texts)
    for i in ctx.snap.issues:     # ouverte ou fermée : le slug reste pris
        if rm.parse_idea_marker(i.get("body") or "") == slug:
            ctx.say(f"already exists: idea {slug} (#{i['number']})")
            return
    payload = {"title": a.title, "body": body, "labels": labels}
    if a.milestone:
        payload["milestone"] = milestone_number(ctx.client, a.milestone)
    for l in labels:
        ensure_label(ctx.client, l)
    issue = ctx.client.send("POST", "issues", payload, texts)
    ctx.say(f"created idea {slug} (#{issue['number']})")


def read_body_file(path):
    """Texte d'un --body-file d'idée : un fichier ordinaire, lisible et non vide ; sinon Stop(2) (rien n'est envoyé)."""
    p = Path(path)
    if not p.is_file():
        raise Stop(2, "usage: --body-file must name an existing regular file")
    texte = read_text_file(p, "--body-file")
    if not texte.strip():
        raise Stop(2, "usage: --body-file names an empty file")
    return texte


IDEA_VALUES = ("1", "2", "3")


def idea_value_label(value):
    return f"value:{value}"


def idea_of(ctx, ref):
    """L'issue de l'idée désignée par `<n>` ou `#<n>` ; Stop(2) si ce n'est pas un numéro, Stop(7) si l'issue manque ou n'a pas l'étiquette type:idea."""
    m = re.fullmatch(r"#?(\d+)", ref or "")
    if not m:
        raise Stop(2, "usage: expected an issue number like 244 or #244")
    issue = ctx.snap.by_number.get(int(m.group(1)))
    if issue is None or rm.LABEL_IDEA not in label_names(issue):
        raise Stop(7, f"#{m.group(1)} is not an idea (no {rm.LABEL_IDEA} label)")
    return issue


def cmd_edit_idea(ctx, a):
    """Change la valeur (étiquette value:N), le jalon ou le corps (--body-file) d'une idée existante (#184)."""
    if a.value is None and a.milestone is None and a.body_file is None and a.title is None and a.product is None:
        raise Stop(2, "usage: edit-idea needs --title, --value, --milestone, --product or --body-file")
    if a.title is not None and not a.title.strip():
        raise Stop(2, "usage: --title must not be empty")
    issue = idea_of(ctx, a.number)
    client = ctx.client
    payload, texts = {}, {}
    if a.title is not None and a.title.strip() != issue.get("title"):
        payload["title"] = texts["title"] = a.title.strip()      # le marqueur (slug) ne change pas
    if a.body_file is not None:
        texte = read_body_file(a.body_file).strip()
        slug = rm.parse_idea_marker(issue.get("body") or "")      # le marqueur de l'idée reste en tête du corps
        body = f"{rm.idea_marker(slug)}\n\n{texte}" if slug else texte
        if body != (issue.get("body") or ""):
            payload["body"], texts["body"] = body, body
    if a.value is not None:
        wanted = idea_value_label(a.value)
        labels = [l for l in label_names(issue) if not re.fullmatch(r"value:\d+", l)] + [wanted]
        if sorted(labels) != sorted(label_names(issue)):
            payload["labels"], texts["labels"] = labels, "\n".join(labels)
    if a.product is not None:
        labels = with_product(payload.get("labels", label_names(issue)), a.product)
        if sorted(labels) != sorted(label_names(issue)):
            payload["labels"], texts["labels"] = labels, "\n".join(labels)
    if a.milestone is not None and issue_milestone(issue) != a.milestone:
        texts["milestone"] = a.milestone
    if not texts:
        ctx.say("nothing to do")
        return
    client.guard.scan(texts)
    if "milestone" in texts:
        payload["milestone"] = milestone_number(client, a.milestone)
    for l in payload.get("labels", []):
        ensure_label(client, l)
    patch_issue(client, issue["number"], payload, texts)
    ctx.say(f"edited idea #{issue['number']}")


def read_text_file(path, option):
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        raise Stop(2, f"usage: {option} must name a readable text file") from None


def cmd_comment_idea(ctx, a):
    """Commente une idée (issue type:idea) ; le texte passe par le garde avant toute requête (#244, point F)."""
    issue = idea_of(ctx, a.number)
    texte = read_text_file(a.body_file, "--body-file")
    ctx.client.send("POST", f"issues/{issue['number']}/comments", {"body": texte}, {"comment": texte})
    ctx.say(f"commented idea #{issue['number']}")


def cmd_close_idea(ctx, a):
    """Ferme une idée (issue type:idea), avec un commentaire facultatif posté avant la fermeture ; rien à faire si elle est fermée (#244, point F)."""
    issue = idea_of(ctx, a.number)
    texte = read_text_file(a.comment_file, "--comment-file") if a.comment_file else None
    if texte is not None:
        ctx.client.guard.scan({"comment": texte})      # le refus du garde précède toute écriture
    if issue.get("state") == "closed":
        ctx.say("nothing to do")
        return
    if texte is not None and texte.strip():
        ctx.client.send("POST", f"issues/{issue['number']}/comments", {"body": texte}, {"comment": texte})
    close_issue(ctx.client, issue)
    ctx.say(f"closed idea #{issue['number']}")


def cmd_ensure_labels(ctx, a):
    made = [l for l in [*rm.all_labels(), rm.LABEL_IDEA] if ensure_label(ctx.client, l)]
    ctx.say(f"created {len(made)} label(s)" if made else "nothing to do")


def cmd_ensure_milestone(ctx, a):
    ctx.say(f"created milestone {a.name}" if ensure_milestone(ctx.client, a.name, a.closed) else "nothing to do")


# --- Ligne de commande --------------------------------------------------------------------------------------------

class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Stop(2, "usage: " + message.splitlines()[0])


def build_parser():
    p = Parser(prog="gh_issue.py", description="Seul chemin d'écriture vers GitHub pour la file de travail")
    common = Parser(add_help=False)
    common.add_argument("--repo", help="confirme le dépôt de origin (un autre dépôt est refusé)")
    sub = p.add_subparsers(dest="cmd", required=True, parser_class=Parser)

    s = sub.add_parser("new-feature", parents=[common])
    s.add_argument("--title", required=True)
    s.add_argument("--theme", required=True)
    s.add_argument("--milestone", required=True)
    s.add_argument("--blocked-by")
    s.add_argument("--set", action="append")
    s.add_argument("--product", choices=rm.PRODUCTS, help="adds the label product:<value> (no label means PMZilla)")
    s.set_defaults(fn=cmd_new_feature)

    s = sub.add_parser("edit", parents=[common])
    s.add_argument("key")
    s.add_argument("--title")
    s.add_argument("--milestone")
    s.add_argument("--set", action="append")
    s.add_argument("--product", choices=(*rm.PRODUCTS, PRODUCT_NONE), help="sets the label product:<value>; none removes it")
    s.set_defaults(fn=cmd_edit)

    s = sub.add_parser("status", parents=[common])
    s.add_argument("key")
    s.add_argument("status")
    s.set_defaults(fn=cmd_status)

    for name, remove in (("block", False), ("unblock", True)):
        s = sub.add_parser(name, parents=[common])
        s.add_argument("key")
        s.add_argument("--by", required=True)
        s.set_defaults(fn=lambda ctx, a, r=remove: cmd_block(ctx, a, r))

    s = sub.add_parser("comment", parents=[common])
    s.add_argument("key")
    s.add_argument("--body-file", required=True)
    s.set_defaults(fn=cmd_comment)

    s = sub.add_parser("new-task", parents=[common])
    s.add_argument("key", help="the feature, R-<n>")
    s.add_argument("--title", required=True, help="text without key; the command adds the prefix R-<n> ·")
    s.add_argument("--body-file", required=True, help="file holding the text of the task")
    s.add_argument("--milestone", help="an existing milestone (default: the milestone of the feature)")
    s.set_defaults(fn=cmd_new_task)

    for name, fn in (("sync-tasks", cmd_sync_tasks), ("close-feature", cmd_close_feature), ("close-step", cmd_close_step)):
        s = sub.add_parser(name, parents=[common])
        s.add_argument("key")
        if name == "close-step":
            s.add_argument("--reason", help="mandatory for an agent sub-issue, optional for a user step")
        if name == "close-feature":
            s.add_argument("--edition-public", action="store_true", help="add the edition:public label (also on a closed feature)")
        s.set_defaults(fn=fn)

    s = sub.add_parser("new-idea", parents=[common])
    s.add_argument("--title", required=True)
    grp = s.add_mutually_exclusive_group(required=True)
    grp.add_argument("--body", help="text of the idea")
    grp.add_argument("--body-file", help="file holding the text of the idea (exclusive with --body)")
    s.add_argument("--milestone", help="an existing milestone")
    s.add_argument("--value", choices=IDEA_VALUES, help="adds the label value:N")
    s.add_argument("--product", choices=rm.PRODUCTS, help="adds the label product:<value> (no label means PMZilla)")
    s.set_defaults(fn=cmd_new_idea)

    s = sub.add_parser("edit-idea", parents=[common])
    s.add_argument("number", help="issue number of the idea, 244 or #244")
    s.add_argument("--title", help="new title of the idea (not empty)")
    s.add_argument("--value", choices=IDEA_VALUES, help="replaces the value:N label")
    s.add_argument("--product", choices=(*rm.PRODUCTS, PRODUCT_NONE), help="sets the label product:<value>; none removes it")
    s.add_argument("--milestone", help="an existing milestone")
    s.add_argument("--body-file", help="file whose text replaces the body of the idea (its marker is kept)")
    s.set_defaults(fn=cmd_edit_idea)

    s = sub.add_parser("comment-idea", parents=[common])
    s.add_argument("number", help="issue number of the idea, 244 or #244")
    s.add_argument("--body-file", required=True)
    s.set_defaults(fn=cmd_comment_idea)

    s = sub.add_parser("close-idea", parents=[common])
    s.add_argument("number", help="issue number of the idea, 244 or #244")
    s.add_argument("--comment-file", help="text posted as a comment before the closing")
    s.set_defaults(fn=cmd_close_idea)

    s = sub.add_parser("ensure-labels", parents=[common])
    s.set_defaults(fn=cmd_ensure_labels)
    s = sub.add_parser("ensure-milestone", parents=[common])
    s.add_argument("name")
    s.add_argument("--closed", action="store_true")
    s.set_defaults(fn=cmd_ensure_milestone)
    return p


def emit(code, lines):
    stream = sys.stdout if code == 0 else sys.stderr
    for l in lines:
        print(PREFIX + l, file=stream)


def main(argv=None):
    client = None
    try:
        args = build_parser().parse_args(argv)
        guard = Guard.load()
        client = Client(guard)
        if getattr(args, "key", None):
            client.target = args.key.split("/")[0]
        if args.repo and args.repo != client.repo():
            raise Stop(2, "usage: the repository is the one of origin; another repository is refused")
        ctx = Ctx(client)
        args.fn(ctx, args)
        emit(0, ctx.out)
        return 0
    except Stop as s:
        lines = list(s.lines)
        if s.code in (1, 6) and client is not None and client.writes:
            lines.append(client.confirmed_line())
        emit(s.code, lines)
        return s.code


if __name__ == "__main__":
    sys.exit(main())
