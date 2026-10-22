#!/usr/bin/env python3
"""Recherche de secrets dans un texte (change pre-commit-secret-scan, design D1, D6, D8) : bibliothèque standard seulement.

Le crochet pre-commit (tools/hooks/pre-commit) l'importe, comme tools/sensitive_names.py. Liste fermée de familles à forte confiance :
clé privée, clé d'accès cloud, jetons GitHub, Anthropic, Atlassian et Slack, adresse avec mot de passe, mot de passe du labo (variable de la
liste fermée affectée d'une valeur littérale). Jamais d'entropie : le dépôt contient des hachages de verrous, des condensats d'images et des
empreintes SHA. Un espace réservé n'est jamais une trouvaille : valeur entre chevrons, d'un seul caractère répété, ou référence de shell ou
de gabarit (`$`, `${…}`, `{{…}}`, `%(…)s`, `{X}` : nom en majuscules entre accolades).

Aucune valeur trouvée n'est renvoyée, stockée ni imprimée : `findings(texte)` ne rend que (ligne, famille). L'empreinte (SHA-256 de la valeur)
ne sert qu'à comparer à la liste des exemples déclarés et n'est jamais imprimée.

Liste des exemples déclarés : tools/secret_scan_exemples.txt, une entrée par ligne « <chemin> <empreinte>  # <raison> » ; lignes vides et
lignes commençant par « # » ignorées ; une ligne mal formée lève ListeInvalide (le crochet refuse alors le commit). Une trouvaille dont le
chemin ET l'empreinte sont dans la liste n'est pas refusée ; la même valeur dans un autre fichier l'est.

    uv run tools/secret_scan.py declare <chemin>:<ligne> --raison <texte> [--racine DOSSIER]
    uv run tools/secret_scan.py declare docs/pmzilla/guide.md:12 --raison "exemple de format de jeton"

« declare » (l'auteur seul, dans le Terminal) ajoute une entrée par trouvaille de la ligne et n'imprime que le chemin, la ligne, la famille et
« exemple déclaré ».

Codes de sortie : 0 entrées écrites ; 1 aucune trouvaille sur cette ligne ; 2 usage, fichier illisible ou liste mal formée ;
  3 refusé dans une session Claude Code (variable CLAUDECODE), avant toute lecture.
"""
import hashlib
import os
import re
import subprocess
import sys
from typing import NamedTuple

LISTE_EXEMPLES = "tools/secret_scan_exemples.txt"
VARIABLE_CLAUDE_CODE = "CLAUDECODE"

CLE_PRIVEE = "cle_privee"
CLE_CLOUD = "cle_cloud"
JETON_GITHUB = "jeton_github"
CLE_ANTHROPIC = "cle_anthropic"
JETON_ATLASSIAN = "jeton_atlassian"
JETON_SLACK = "jeton_slack"
ADRESSE_MOT_DE_PASSE = "adresse_mot_de_passe"
MOT_DE_PASSE_LABO = "mot_de_passe_labo"

ETIQUETTES = {
    CLE_PRIVEE: "clé privée",
    CLE_CLOUD: "clé d'accès cloud",
    JETON_GITHUB: "jeton GitHub",
    CLE_ANTHROPIC: "clé d'API Anthropic",
    JETON_ATLASSIAN: "jeton Atlassian",
    JETON_SLACK: "jeton Slack",
    ADRESSE_MOT_DE_PASSE: "adresse avec mot de passe",
    MOT_DE_PASSE_LABO: "mot de passe du labo",
}

# Familles à préfixe : (famille, motif, groupe du corps du jeton). Le corps d'un seul caractère répété est un espace réservé.
_BORNE = r"(?<![A-Za-z0-9_])"
FAMILLES_A_PREFIXE = (
    (CLE_CLOUD, re.compile(_BORNE + r"(?:AKIA|ASIA|AGPA|AIDA|AROA|ANPA|ANVA|AIPA)([0-9A-Z]{16})(?![A-Za-z0-9])"), 1),
    (JETON_GITHUB, re.compile(_BORNE + r"gh[pousr]_([A-Za-z0-9]{36,255})(?![A-Za-z0-9])"), 1),
    (JETON_GITHUB, re.compile(_BORNE + r"github_pat_([A-Za-z0-9_]{22,255})(?![A-Za-z0-9_])"), 1),
    (CLE_ANTHROPIC, re.compile(_BORNE + r"sk-ant-([A-Za-z0-9_-]{20,})"), 1),
    (JETON_ATLASSIAN, re.compile(_BORNE + r"AT(?:ATT|CTT)([A-Za-z0-9_=-]{20,})"), 1),
    (JETON_SLACK, re.compile(_BORNE + r"xox[abprs]-([A-Za-z0-9-]{10,})"), 1),
    (JETON_SLACK, re.compile(_BORNE + r"xapp-[0-9]-([A-Za-z0-9-]{10,})"), 1),
)
ENTETE_CLE_PRIVEE = re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----")
# Schéma borné et précédé d'un non-caractère de schéma : temps linéaire sur une très longue ligne (D3, fichiers de toute taille).
ADRESSE = re.compile(r"(?<![A-Za-z0-9+.-])[A-Za-z][A-Za-z0-9+.-]{0,31}://[^\s:/@'\"`]+:([^\s@/'\"`]+)@[^\s/'\"`]+")

# Liste fermée des noms de variables du labo (mots de passe de la base, jeton Jira, clé d'analyse), suffixe de rôle compris.
NOMS_LABO = r"(?:PMZILLA_LAB_DB_PASSWORD(?:_[A-Z0-9_]+)?|PMZILLA_JIRA_TOKEN|PMZILLA_STORY_ANALYSIS_KEY)"
AFFECTATION_LABO = re.compile(
    _BORNE + NOMS_LABO + r"""(?![A-Za-z0-9_])["']?\]?\s*(?:=|:(?![-=?+]))[ \t]*(?:"([^"]*)"|'([^']*)'|([^\s"'#;&|,)\]}]+))""")   # valeur nue : s'arrête à la virgule et aux fermantes d'un dict ou d'un appel
CONSTANTE = re.compile(r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+")   # valeur nue en MAJUSCULES_ET_SOULIGNÉS : nom de constante, pas un littéral
CARACTERES_REFERENCE = ("(", "[", "$", "<", "{", "`", "%")
REFERENCE_ACCOLADES = re.compile(r"\{[A-Z][A-Z0-9_]*\}")

TAILLE_EMPREINTE = 64
LIGNE_ENTREE = re.compile(r"^(?P<chemin>\S+) (?P<empreinte>[0-9a-f]{64})(?:\s+#.*)?$")


class ListeInvalide(Exception):
    """La liste des exemples déclarés est illisible ou une de ses lignes est mal formée (le crochet refuse alors le commit)."""


class Finding(NamedTuple):
    line: int
    family: str


class _Hit(NamedTuple):
    line: int
    family: str
    value: str


def label(family: str) -> str:
    return ETIQUETTES[family]


def fingerprint(value: str) -> str:
    """SHA-256 de la valeur : sert à comparer à la liste, jamais imprimé."""
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def is_placeholder(value: str) -> bool:
    """Espace réservé : vide, entre chevrons, d'un seul caractère répété, référence de shell ou de gabarit."""
    if not value:
        return True
    if len(set(value)) == 1:
        return True
    if value.startswith(("$", "{{", "%(")) or "${" in value:
        return True
    if REFERENCE_ACCOLADES.fullmatch(value):   # {X} : nom en majuscules entre accolades (gabarit de la documentation)
        return True
    return value.startswith("<") and value.endswith(">")


def _valeur_litterale(valeur: str) -> bool:
    return not is_placeholder(valeur) and not valeur.startswith(CARACTERES_REFERENCE)


def _scan(text: str) -> list:
    lignes = text.splitlines()
    trouvees = []
    for numero, ligne in enumerate(lignes, 1):
        suivante = lignes[numero] if numero < len(lignes) else ""
        for entete in ENTETE_CLE_PRIVEE.finditer(ligne):
            trouvees.append(_Hit(numero, CLE_PRIVEE, ligne[entete.start():] + "\n" + suivante))
        for famille, motif, groupe in FAMILLES_A_PREFIXE:
            for m in motif.finditer(ligne):
                if not is_placeholder(m.group(groupe)):
                    trouvees.append(_Hit(numero, famille, m.group(0)))
        for m in ADRESSE.finditer(ligne):
            if not is_placeholder(m.group(1)):
                trouvees.append(_Hit(numero, ADRESSE_MOT_DE_PASSE, m.group(0)))
        for m in AFFECTATION_LABO.finditer(ligne):
            valeur = next((g for g in m.groups() if g is not None), "")
            nue = m.group(3) is not None and m.group(1) is None and m.group(2) is None
            if _valeur_litterale(valeur) and not (nue and CONSTANTE.fullmatch(valeur)):
                trouvees.append(_Hit(numero, MOT_DE_PASSE_LABO, valeur))
    return trouvees


def findings(text: str) -> list:
    """Les trouvailles du texte, (ligne, famille), sans jamais la valeur, dans l'ordre des lignes."""
    return [Finding(h.line, h.family) for h in _scan(text)]


def parse_declared(text: str) -> set:
    """{(chemin, empreinte)} de la liste des exemples déclarés ; lève ListeInvalide à la première ligne mal formée (jamais son texte)."""
    entrees = set()
    for numero, brute in enumerate(text.splitlines(), 1):
        ligne = brute.strip()
        if not ligne or ligne.startswith("#"):
            continue
        m = LIGNE_ENTREE.match(ligne)
        if not m:
            raise ListeInvalide(f"ligne {numero} mal formée")
        entrees.add((m.group("chemin"), m.group("empreinte")))
    return entrees


def load_declared(chemin: str) -> set:
    """La liste lue sur disque ; fichier absent : ensemble vide ; illisible ou mal formée : ListeInvalide."""
    try:
        with open(chemin, encoding="utf-8") as f:
            texte = f.read()
    except FileNotFoundError:
        return set()
    except (OSError, UnicodeDecodeError):
        raise ListeInvalide("liste illisible") from None
    return parse_declared(texte)


def check(chemin: str, text: str, declared: set) -> tuple:
    """(refusées, acceptées) : les trouvailles du fichier `chemin`, séparées selon qu'une entrée (chemin, empreinte) les déclare."""
    refusees, acceptees = [], []
    for hit in _scan(text):
        cible = acceptees if (chemin, fingerprint(hit.value)) in declared else refusees
        cible.append(Finding(hit.line, hit.family))
    return refusees, acceptees


# --- commande declare -------------------------------------------------------------------------------------------------------------

def _racine_git() -> str:
    try:
        fait = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, check=True)
        return fait.stdout.decode().strip() or os.getcwd()
    except (OSError, subprocess.CalledProcessError):
        return os.getcwd()


def _arguments_declare(argv):
    """(chemin, ligne, raison, racine) ou None si l'usage est faux."""
    if not argv or ":" not in argv[0]:
        return None
    cible, reste = argv[0], list(argv[1:])
    chemin, _, numero = cible.rpartition(":")
    raison, racine = None, None
    while reste:
        option = reste.pop(0)
        if option == "--raison" and reste:
            raison = reste.pop(0)
        elif option == "--racine" and reste:
            racine = reste.pop(0)
        else:
            return None
    if not chemin or not numero.isdigit() or int(numero) < 1 or not raison or not raison.strip():
        return None
    return chemin, int(numero), " ".join(raison.split()), racine


def declare(argv) -> int:
    if os.environ.get(VARIABLE_CLAUDE_CODE):
        print("secret_scan : declare est refusé dans une session Claude Code ; lance-le toi-même dans le Terminal.", file=sys.stderr)
        return 3
    arguments = _arguments_declare(argv)
    if arguments is None:
        print("usage : secret_scan.py declare <chemin>:<ligne> --raison <texte> [--racine DOSSIER]", file=sys.stderr)
        return 2
    cible, numero, raison, racine = arguments
    racine = os.path.realpath(racine or _racine_git())
    absolu = cible if os.path.isabs(cible) else os.path.join(racine, cible)
    relatif = os.path.relpath(os.path.realpath(absolu), racine).replace(os.sep, "/")
    if relatif.startswith("..") or any(c.isspace() for c in relatif):
        print("secret_scan : chemin hors du dépôt ou contenant un espace, impossible à déclarer", file=sys.stderr)
        return 2
    try:
        with open(absolu, encoding="utf-8") as f:
            texte = f.read()
    except (OSError, UnicodeDecodeError):
        print(f"secret_scan : fichier illisible : {relatif}", file=sys.stderr)
        return 2
    liste = os.path.join(racine, LISTE_EXEMPLES)
    try:
        existantes = load_declared(liste)
    except ListeInvalide as erreur:
        print(f"secret_scan : liste des exemples déclarés invalide ({erreur}), rien n'est écrit", file=sys.stderr)
        return 2
    trouvees = [h for h in _scan(texte) if h.line == numero]
    if not trouvees:
        print(f"secret_scan : aucune trouvaille à la ligne {numero} de {relatif}", file=sys.stderr)
        return 1
    if any(h.value in raison for h in trouvees):
        print("secret_scan : la raison contient une valeur trouvée ; reformule-la sans la citer", file=sys.stderr)
        return 2
    nouvelles = []
    for hit in trouvees:
        empreinte = fingerprint(hit.value)
        if (relatif, empreinte) not in existantes:
            existantes.add((relatif, empreinte))
            nouvelles.append(f"{relatif} {empreinte}  # {raison}\n")
    if nouvelles:
        os.makedirs(os.path.dirname(liste), exist_ok=True)
        debut = ""
        if os.path.isfile(liste) and os.path.getsize(liste):
            with open(liste, "rb") as f:
                f.seek(-1, os.SEEK_END)
                debut = "" if f.read(1) == b"\n" else "\n"
        with open(liste, "a", encoding="utf-8") as f:
            f.write(debut + "".join(nouvelles))
    for hit in trouvees:
        print(f"{relatif}, ligne {numero} ({label(hit.family)}) : exemple déclaré")
    return 0


def main(argv) -> int:
    if argv and argv[0] == "declare":
        return declare(argv[1:])
    print(__doc__)
    return 0 if argv in ([], ["-h"], ["--help"]) else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
