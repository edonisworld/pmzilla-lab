# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
PMZilla Lab : modèle partagé de la file de travail sur GitHub (change github-roadmap, design D1, D2, D3, D5).

Module de fonctions pures, sans réseau ni gh, importé par l'outil d'écriture, l'import et le lecteur :

- marqueurs d'identité et clés (`<!-- roadmap-id: R-<n> -->`, `R-<n>/g<groupe>`, `R-<n>/t<tâche>`) ;
- motif des titres (`R-<n> · <titre>`) et noms des labels ;
- bloc `roadmap` du corps d'une feature : lecture, écriture, validation ;
- table état -> (ouverture, Status) ;
- parseur des groupes de `tasks.md` avec leurs tags et la règle de complétude ; un groupe sans tag valide est une erreur de plan ;
- dépôt d'origine d'après l'URL d'un remote GitHub (change workflow-tooling-fixes, D7) ;
- réglages de la file (`tools/roadmap_settings.yaml`, D12) : analyse du texte, sans lire le fichier.

Usage : `import roadmap_model` après avoir ajouté `tools/` au chemin. Tests : tests/roadmap_model.
"""
import datetime
import re
import unicodedata
from dataclasses import dataclass, field

import yaml

THEMES = ("fiabilite", "veille", "bibliotheque", "base", "cas", "postures", "edition", "outillage")
MODELS = ("opus", "sonnet", "haiku")
METHODS = ("openspec", "direct-prompt")
STATES = ("ready", "in-progress", "blocked", "done")
STATUSES = ("Todo", "Ready", "In progress", "Done")

LABEL_FEATURE = "type:feature"
LABEL_TASK = "type:task"
LABEL_PARALLEL = "parallel"
LABEL_USER = "owner:user"
LABEL_EDITION_PUBLIC = "edition:public"     # édition publique (edition-publish-tooling, D19) : posée à la fermeture, jamais retirée
LABEL_IDEA = "type:idea"     # hors de all_labels() : une idée n'est pas un élément de la file
PRODUCTS = ("mothra",)       # produits étiquetés (liste fermée) ; l'absence de label `product:` vaut PMZilla, on ne réétiquette pas l'existant
LABEL_PRODUCT_PREFIX = "product:"

SEP = "·"

# --- Dépôt d'origine (D7) -----------------------------------------------------------------------------------------

_REMOTE = re.compile(r"github\.com[:/]([^/\s:]+)/([^/\s]+?)(?:\.git)?/?$")


def repo_from_url(url):
    """propriétaire/dépôt d'après l'URL d'un remote GitHub, ou None."""
    mo = _REMOTE.search((url or "").strip())
    return f"{mo.group(1)}/{mo.group(2)}" if mo else None


# --- Réglages de la file (D12) ------------------------------------------------------------------------------------

SETTINGS_FILE = "tools/roadmap_settings.yaml"
SETTINGS_KEYS = ("current_release",)


def parse_settings(text):
    """Réglages d'après le texte du fichier : {"current_release": nom de jalon ou ""}. Texte vide ou valeur vide : "".
    ValueError si le texte n'est pas un dictionnaire, a une clé inconnue ou une valeur qui n'est pas un nom de jalon."""
    try:
        data = yaml.safe_load(text or "")
    except yaml.YAMLError:
        raise ValueError("réglages illisibles (YAML invalide)") from None
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError("réglages : un dictionnaire est attendu")
    inconnues = sorted(str(k) for k in data if k not in SETTINGS_KEYS)
    if inconnues:
        raise ValueError(f"réglages : clé inconnue {', '.join(inconnues)}")
    valeur = data.get("current_release")
    if valeur is None:
        valeur = ""
    if not isinstance(valeur, str) or valeur != valeur.strip() or "\n" in valeur:
        raise ValueError("current_release : un nom de jalon ou rien est attendu")
    return {"current_release": valeur}

# --- Marqueurs et clés (D1) ---------------------------------------------------------------------------------------

_KEY = re.compile(r"^R-(\d+)(?:/(?:g(\d+)|t(\d+\.\d+)|u(\d+)))?$")
_MARKER = re.compile(r"\A<!-- roadmap-id: (\S+) -->")
_IDEA_MARKER = re.compile(r"\A<!-- roadmap-idea: ([a-z0-9-]+) -->")


def feature_key(n):
    return f"R-{int(n)}"


def group_key(n, group):
    return f"R-{int(n)}/g{int(group)}"


def task_key(n, task_id):
    return f"R-{int(n)}/t{task_id}"


def user_task_key(n, k):
    """Tâche utilisateur autonome (gh_issue new-task), sans tasks.md : R-<n>/u<k>, jamais confondue avec g<N> ni t<N.M>."""
    return f"R-{int(n)}/u{int(k)}"


def parse_key(key):
    """('feature'|'group'|'task'|'user-task', n, None|groupe|id de tâche|numéro). ValueError si la clé est mal formée."""
    mo = _KEY.match(key or "")
    if not mo:
        raise ValueError(f"clé d'identité mal formée : {key!r}")
    n = int(mo.group(1))
    if mo.group(2) is not None:
        return ("group", n, mo.group(2))
    if mo.group(3) is not None:
        return ("task", n, mo.group(3))
    if mo.group(4) is not None:
        return ("user-task", n, mo.group(4))
    return ("feature", n, None)


def marker(key):
    parse_key(key)
    return f"<!-- roadmap-id: {key} -->"


def idea_slug(title):
    """Slug d'une idée (D7) : titre en minuscules, sans accents, chaque suite de non-alphanumériques devient un tiret, tirets rognés."""
    plain = unicodedata.normalize("NFKD", title or "").encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-")


def idea_marker(slug):
    return f"<!-- roadmap-idea: {slug} -->"


def parse_idea_marker(body):
    """Slug du marqueur d'idée placé au tout début du corps, ou None (ce n'est pas un marqueur `roadmap-id`)."""
    mo = _IDEA_MARKER.match(body or "")
    return mo.group(1) if mo else None


def parse_marker(body):
    """Clé du marqueur placé au tout début du corps, ou None."""
    mo = _MARKER.match(body or "")
    if not mo:
        return None
    try:
        parse_key(mo.group(1))
    except ValueError:
        return None
    return mo.group(1)


# --- Titres et labels (D1) ----------------------------------------------------------------------------------------

_TITLE = re.compile(rf"^R-(\d+) {SEP} (.+)$")


def feature_title(n, title):
    return f"R-{int(n)} {SEP} {title}"


def group_title(n, group, title):
    return f"R-{int(n)} {SEP} {int(group)}. {title}"


def user_task_title(n, task_id):
    return f"R-{int(n)} {SEP} {task_id} (user step)"


def parse_title(title):
    """(n, reste du titre) ou None si le titre ne suit pas le motif `R-<n> · <texte>`."""
    mo = _TITLE.match(title or "")
    return (int(mo.group(1)), mo.group(2)) if mo else None


def label_theme(theme):
    if theme not in THEMES:
        raise ValueError(f"thème inconnu : {theme!r}")
    return f"theme:{theme}"


def label_model(model):
    if model not in MODELS:
        raise ValueError(f"modèle inconnu : {model!r}")
    return f"model:{model}"


def label_product(product):
    if product not in PRODUCTS:
        raise ValueError(f"produit inconnu : {product!r}")
    return f"{LABEL_PRODUCT_PREFIX}{product}"


def product_labels(labels):
    """Les labels `product:` d'une liste de noms de labels (connus ou non), dans l'ordre."""
    return [l for l in labels if l.startswith(LABEL_PRODUCT_PREFIX)]


def all_labels():
    return ([LABEL_FEATURE, LABEL_TASK] + [label_theme(t) for t in THEMES] + [label_model(x) for x in MODELS]
            + [LABEL_PARALLEL, LABEL_USER, LABEL_EDITION_PUBLIC] + [label_product(p) for p in PRODUCTS])


# --- Bloc roadmap (D5) --------------------------------------------------------------------------------------------

class BlockError(ValueError):
    pass


_FENCE = re.compile(r"^```roadmap[ \t]*\n(.*?)^```[ \t]*$", re.S | re.M)
_ESTIMATE = re.compile(r"^(?:tbd|\d+min|\d+h(?:\d{1,2})?)$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ID = re.compile(r"^R-\d+$")
REQUIRED = ("id", "theme", "estimate", "method", "model", "conditions")
DATES = ("not_before", "due", "started_on", "done_on")
KEYS = REQUIRED + ("rank", "change") + DATES
_ORDER = ("id", "theme", "estimate", "method", "model", "rank", "conditions", "change") + DATES


def parse_block(body):
    """Le bloc `roadmap` du corps, en dict (dates en chaînes ISO). BlockError s'il manque, est double ou n'est pas un dict."""
    found = _FENCE.findall(body or "")
    if not found:
        raise BlockError("bloc roadmap absent")
    if len(found) > 1:
        raise BlockError("plusieurs blocs roadmap")
    try:
        data = yaml.safe_load(found[0])
    except yaml.YAMLError as e:
        raise BlockError(f"bloc roadmap illisible : {e}") from None
    if not isinstance(data, dict):
        raise BlockError("le bloc roadmap n'est pas un dictionnaire de clés")
    return {k: (v.isoformat() if isinstance(v, (datetime.date, datetime.datetime)) else v) for k, v in data.items()}


def render_block(block):
    """Le bloc clôturé, clés dans l'ordre du design, une par ligne. Les chaînes sont écrites entre guillemets si besoin."""
    lignes = ["```roadmap"]
    keys = [k for k in _ORDER if k in block] + [k for k in block if k not in _ORDER]
    for k in keys:
        v = block[k]
        if isinstance(v, str):
            if v == "" or v == "tbd" or v == "unknown" or _DATE.match(v):
                texte = '""' if v == "" else v
            else:
                texte = yaml.safe_dump(v, default_flow_style=True, allow_unicode=True, width=10**6).splitlines()[0]
            lignes.append(f"{k}: {texte}")
        else:
            lignes.append(f"{k}: {v}")
    lignes.append("```")
    return "\n".join(lignes)


def _valid_date(v):
    if not isinstance(v, str) or not _DATE.match(v):
        return False
    try:
        datetime.date.fromisoformat(v)
    except ValueError:
        return False
    return True


def _estimate_minutes(e):
    """Minutes d'une estimation valide (None pour tbd)."""
    mo = re.match(r"^(\d+)min$", e)
    if mo:
        return int(mo.group(1))
    mo = re.match(r"^(\d+)h(\d{1,2})?$", e)
    return int(mo.group(1)) * 60 + int(mo.group(2) or 0) if mo else None


def validate_block(block, *, is_open=True, marker_key=None, theme_label=None):
    """Liste des problèmes (vide si valide). marker_key et theme_label : valeurs du marqueur et du label à égaler."""
    pb = []
    for k in REQUIRED:
        if k not in block:
            pb.append(f"{k} : clé requise absente")
    if is_open and "rank" not in block:
        pb.append("rank : requis sur une feature ouverte")
    for k in block:
        if k not in KEYS:
            pb.append(f"{k} : clé inconnue")
    v = block.get("id")
    if "id" in block and (not isinstance(v, str) or not _ID.match(v)):
        pb.append(f"id : attendu R-<n>, reçu {v!r}")
    if "theme" in block and block["theme"] not in THEMES:
        pb.append(f"theme : valeur hors de {', '.join(THEMES)}")
    if "method" in block and block["method"] not in METHODS:
        pb.append(f"method : valeur hors de {', '.join(METHODS)}")
    if "model" in block and block["model"] not in MODELS + ("tbd",):
        pb.append(f"model : valeur hors de {', '.join(MODELS)}, tbd")
    if "estimate" in block and not (isinstance(block["estimate"], str) and _ESTIMATE.match(block["estimate"])):
        pb.append(f"estimate : forme attendue 45min, 2h, 1h30 ou tbd, reçu {block['estimate']!r}")
    elif "estimate" in block and _estimate_minutes(block["estimate"]) == 0:
        pb.append("estimate : durée nulle refusée (0min, 0h)")
    if "rank" in block:
        r = block["rank"]
        if isinstance(r, bool) or not isinstance(r, int) or r < 1:
            pb.append(f"rank : entier positif attendu, reçu {r!r}")
    if "conditions" in block and not isinstance(block["conditions"], str):
        pb.append("conditions : texte attendu")
    if "change" in block and not (isinstance(block["change"], str) and block["change"].strip()):
        pb.append("change : texte non vide attendu")
    for k in DATES:
        if k in block and not (_valid_date(block[k]) or (k == "done_on" and block[k] == "unknown")):
            pb.append(f"{k} : date AAAA-MM-JJ attendue" + (" (ou unknown)" if k == "done_on" else ""))
    if marker_key is not None and block.get("id") != marker_key:
        pb.append(f"id : {block.get('id')!r} différent du marqueur {marker_key!r}")
    if theme_label is not None and block.get("theme") != theme_label:
        pb.append(f"theme : {block.get('theme')!r} différent du label {theme_label!r}")
    return pb


# --- Groupes de tasks.md (D3) -------------------------------------------------------------------------------------

class PlanError(ValueError):
    def __init__(self, change, untagged):
        self.change = change
        self.untagged = list(untagged)
        super().__init__(f"{change} : tasks.md groups untagged: {', '.join(str(n) for n in self.untagged)}")


@dataclass
class Task:
    id: str
    text: str
    done: bool
    user: bool


@dataclass
class Group:
    number: int
    title: str
    kind: str                      # 'agent' | 'user'
    model: str | None
    parallel: bool
    tasks: list = field(default_factory=list)


_HEAD = re.compile(r"^## (\d+)\. (.*?)\s*$")
_TAIL_TAGS = re.compile(r"((?:\s*\[[^\[\]]+\])+)\s*$")
_ONE_TAG = re.compile(r"\[([^\[\]]+)\]")
_TASK = re.compile(r"^\s*- \[([ xX])\] (\d+\.\d+)\s+(.*)$")


def _tags(title):
    """(titre sans tags, liste des tags) pour les tags en fin de titre."""
    mo = _TAIL_TAGS.search(title)
    if not mo:
        return title, []
    return title[:mo.start()].rstrip(), [t.strip() for t in _ONE_TAG.findall(mo.group(1))]


def _kind(tags):
    """(kind, model, parallel) ou None si les tags ne forment pas un groupe valide."""
    models = [t for t in tags if t.startswith("model:")]
    users = [t for t in tags if t == "user"]
    par = [t for t in tags if t == "parallel"]
    if len(models) + len(users) + len(par) != len(tags) or len(par) > 1:
        return None
    if len(models) == 1 and not users:
        mod = models[0].split(":", 1)[1].strip()
        return ("agent", mod, bool(par)) if mod in MODELS else None
    if len(users) == 1 and not models:
        return ("user", None, bool(par))
    return None


def parse_tasks(text, change):
    """Les groupes numérotés de `tasks.md`. PlanError (change, numéros) si un groupe n'a pas de tag valide."""
    groups, untagged, cur, in_code = [], [], None, False
    for ligne in text.splitlines():
        if ligne.lstrip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if ligne.startswith("#"):
            mo = _HEAD.match(ligne)
            if mo:
                num, (titre, tags) = int(mo.group(1)), _tags(mo.group(2))
                k = _kind(tags)
                if k is None:
                    untagged.append(num)
                    cur = None
                else:
                    cur = Group(num, titre, k[0], k[1], k[2])
                    groups.append(cur)
            elif ligne.startswith("# ") or ligne.startswith("## ") or ligne in ("#", "##"):
                cur = None             # seuls les titres de niveau 1 et 2 ferment le groupe courant
            continue
        t = _TASK.match(ligne)
        if t and cur is not None:
            corps = t.group(3)
            user = corps.startswith("[user]")
            cur.tasks.append(Task(t.group(2), corps, t.group(1) in "xX", user))
    if untagged:
        raise PlanError(change, untagged)
    return groups


def user_tasks(group):
    """Tâches `[user]` d'un groupe agent (une sous-issue owner:user chacune)."""
    return [t for t in group.tasks if t.user] if group.kind == "agent" else []


def task_complete(task):
    return task.done


def group_complete(group):
    """Complet quand chaque ligne de tâche est cochée ; un groupe sans tâche n'est pas complet."""
    return bool(group.tasks) and all(t.done for t in group.tasks)
