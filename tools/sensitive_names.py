#!/usr/bin/env python3
"""Garde des noms sensibles du module des cas (design.md 3.5).

Fonctions pures, mêmes règles de correspondance que le hook pre-commit : mot entier (un nom collé à une lettre, un
chiffre ou un tiret bas ne correspond pas ; un nom qui commence ou finit par un symbole correspond), casse ignorée sauf
pour les noms de 3 caractères ou moins et les sigles entièrement en majuscules, comparés en respectant la casse.

`load_names` lit un nom par ligne (lignes vides et lignes commençant par « # » ignorées). Fichier absent, illisible, ou
sans aucun nom : `SensitiveNamesUnavailable`, avec `reason` valant `missing`, `unreadable` ou `empty` ; jamais une liste
vide. Le message nomme le chemin, jamais le contenu. Chemin : `Flux-Lab/noms-sensibles.txt` sous l'espace de travail,
remplaçable par PMZILLA_LAB_SENSITIVE_NAMES. `find_field` renvoie le nom du champ concerné, jamais le nom trouvé.

Règle des mots courants (change names-and-team-review), partagée par `migrate-teams` et le hook pre-commit : `is_common_word`,
`is_distinctive` (libellé à proposer pour la liste), `is_common_label` et `common_word_lines` (numéros de ligne des entrées de la liste
dont les mots de plus de trois lettres sont tous courants, jamais les entrées). Liste fermée dans le code, aucun dictionnaire embarqué.

Noms génériques (change extract-name-exclusions) : `extract_names` écarte les noms de l'extrait que la liste `noms-generiques.txt`, voisine de
l'extrait et hors Git, reprend (égalité sans casse du nom entier). La liste des noms sensibles n'est jamais filtrée.
"""
import os
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lab_paths  # noqa: E402

MOT = "A-Za-z0-9_"
RACINE = Path(__file__).resolve().parents[1]


class SensitiveNamesUnavailable(Exception):
    def __init__(self, reason, path):
        self.reason = reason
        self.path = Path(path)
        detail = {"missing": "liste absente", "unreadable": "liste illisible", "empty": "liste sans aucun nom"}[reason]
        super().__init__(f"{detail} : {self.path}")


def default_path() -> Path:
    """Le chemin de la liste, par le registre des fichiers locaux de tools/lab_paths.py : PMZILLA_LAB_SENSITIVE_NAMES, puis PMZILLA_NOMS,
    sinon sa place dans le dossier de contenu (le dépôt principal depuis un worktree). Sans dépôt Git, un chemin inexistant : liste absente."""
    chemin = lab_paths.local_file_for("sensitive_names", RACINE)
    return chemin if chemin is not None else Path("<dossier de contenu introuvable>") / "noms-sensibles.txt"


def parse_names(texte: str) -> list:
    """Un nom par ligne ; lignes vides et lignes commençant par « # » ignorées. Seule lecture de la liste, partagée avec le hook pre-commit."""
    return [l.strip() for l in texte.lstrip("\ufeff").splitlines() if l.strip() and not l.strip().startswith("#")]


def load_names(path=None) -> list:
    chemin = Path(path) if path is not None else default_path()
    if not chemin.exists():
        raise SensitiveNamesUnavailable("missing", chemin)
    try:
        texte = chemin.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        raise SensitiveNamesUnavailable("unreadable", chemin) from None
    noms = parse_names(texte)
    if not noms:
        raise SensitiveNamesUnavailable("empty", chemin)
    return noms


NOM_EXTRAIT = "equipes-lisibles.yaml"
SECTIONS_EXTRAIT = ("referential_teams", "catalogue_teams")
NOM_GENERIQUES = "noms-generiques.txt"


def extract_path() -> Path:
    """L'extrait des noms d'équipes (change team-names-readable) voisine la liste : même dossier, sans lire la liste."""
    return default_path().parent / NOM_EXTRAIT


def _noms_de_l_extrait_sans_yaml(texte: str) -> list:
    """Lecteur de repli, sans dépendance (le hook tourne sous python3 nu) : les lignes `name:` des deux sections, valeur nue ou entre guillemets."""
    noms, section = [], None
    for ligne in texte.splitlines():
        if ligne and not ligne[0].isspace() and not ligne.startswith("-"):
            section = ligne.split(":", 1)[0].strip()
            continue
        m = re.match(r"^\s*(?:-\s+)?name:\s*(.*?)\s*$", ligne)
        if m and section in SECTIONS_EXTRAIT:
            valeur = m.group(1)
            if len(valeur) >= 2 and valeur[0] == valeur[-1] == "'":
                valeur = valeur[1:-1].replace("''", "'")
            elif len(valeur) >= 2 and valeur[0] == valeur[-1] == '"':
                valeur = valeur[1:-1].replace('\\"', '"')
            noms.append(valeur)
    return noms


def _noms_de_l_extrait(texte: str) -> list:
    """Toujours le lecteur sans dépendance : ce module reste en bibliothèque standard (exempté dans tests/script_dependencies), et le
    hook (python3 nu) comme gh_issue.py lisent ainsi l'extrait de la même façon, avec ou sans yaml installé."""
    return _noms_de_l_extrait_sans_yaml(texte)


def extract_names(path=None) -> list:
    """Noms distinctifs (`is_distinctive`) des équipes de l'extrait Flux-Lab/equipes-lisibles.yaml (`referential_teams` et `catalogue_teams`),
    sans doublon, moins les noms de la liste des noms génériques voisine (`generic_names`). Extrait absent, illisible ou invalide : liste
    vide, jamais d'erreur. N'ouvre jamais la liste des noms sensibles, qui n'est jamais filtrée."""
    chemin = Path(path) if path is not None else extract_path()
    try:
        texte = chemin.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError, ValueError):
        return []
    exclus = generic_names(chemin.parent)
    vus = []
    for nom in _noms_de_l_extrait(texte):
        nom = nom.strip()
        if nom not in vus and is_distinctive(nom) and nom.casefold() not in exclus:
            vus.append(nom)
    return vus


def generic_names(dossier) -> frozenset:
    """Noms de la liste `noms-generiques.txt` du dossier donné (change extract-name-exclusions, D1 et D3), repliés en minuscules
    (`casefold`) : un nom par ligne, espaces de bord, lignes vides et lignes commençant par « # » ignorés, marque d'ordre des octets
    acceptée. Liste absente ou illisible : ensemble vide, jamais d'erreur, jamais de message."""
    try:
        texte = (Path(dossier) / NOM_GENERIQUES).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError, ValueError):
        return frozenset()
    return frozenset(n.casefold() for n in parse_names(texte))


def _sensible_a_la_casse(nom):
    return len(nom) <= 3 or (nom == nom.upper() and nom != nom.lower())


def _compiler(noms, drapeaux):
    if not noms:
        return None
    motifs = sorted(noms, key=len, reverse=True)
    return re.compile(rf"(?<![{MOT}])(?:" + "|".join(re.escape(n) for n in motifs) + rf")(?![{MOT}])", drapeaux)


def _motifs(names):
    noms = {n.strip() for n in names if n and n.strip()}
    exacts = {n for n in noms if _sensible_a_la_casse(n)}
    return [m for m in (_compiler(exacts, 0), _compiler(noms - exacts, re.IGNORECASE)) if m]


def patterns(names) -> list:
    """Motifs compilés d'une liste de noms (seule compilation, partagée avec le hook pre-commit)."""
    return _motifs(names)


def line_matches(motifs, ligne: str) -> bool:
    return any(m.search(ligne) for m in motifs)


# ---------------------------------------------------------------------------
# Mots courants (change names-and-team-review, D2 et D3)
# ---------------------------------------------------------------------------

MIN_LENGTH = 6          # en dessous, un libellé est en pratique un acronyme ou un mot court

# Liste fermée de mots courants, anglais et français, du vocabulaire de fonction, de domaine, d'équipe et de la vie de travail :
# jamais un nom. Aucun dictionnaire embarqué, aucun nom d'organisation, de produit, d'équipe ou de domaine.
COMMON_WORDS = frozenset("""
team teams equipe equipes squad squads platform platforms plateforme plateformes support service services product products produit
produits data donnees core domain domains domaine domaines backend frontend front back quality qualite delivery livraison
integration integrations infrastructure security securite operations operation ops development developpement verification
validation management gestion other autre autres group groups groupe groupes project projects projet projets business mobile
cloud release releases test tests testing design research architecture program programme tooling outils outil devops engineering
ingenierie solutions solution systems systemes system experience client clients customer customers pilotage transverse commun
communs common shared partage tech technique technical application applications applicatif logiciel software hardware reseau
network analytics analyse analyses reporting discovery strategy strategie growth marketing sales finance legal compliance
conformite payment payments paiement paiements billing facturation portal portail gateway workflow workflows pipeline pipelines
monitoring supervision observability reliability fiabilite performance enablement capability capabilities foundation
foundations enterprise global regional central digital innovation success onboarding search recherche catalog catalogue
content contenu media identity identite access acces account accounts compte comptes maintenance exploitation operationnel
conception formation accompagnement soutien parcours flux stream streams enabling complicated subsystem sous-systeme
process processus programs office train planning roadmap backlog sprint agile scrum kanban
""".split())


def _plain(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn").casefold()


def is_common_word(word: str) -> bool:
    """Le mot est dans la liste fermée des mots courants (casse et accents ignorés)."""
    return _plain(word.strip()) in COMMON_WORDS


def _long_words(label: str) -> list:
    return [m for m in re.split(r"[\s\-_]+", label.strip()) if len(m) > 3]


def _only_common_words(label: str) -> bool:
    """Au moins un mot de plus de trois lettres, et tous ceux-là sont des mots courants."""
    mots = _long_words(label)
    return bool(mots) and all(is_common_word(m) for m in mots)


def is_distinctive(label: str) -> bool:
    """Libellé à proposer pour la liste des noms sensibles : au moins MIN_LENGTH caractères (sans les espaces de bord) et au moins un
    mot de plus de trois lettres qui n'est pas un mot courant."""
    label = label.strip()
    return len(label) >= MIN_LENGTH and any(not is_common_word(m) for m in _long_words(label))


def is_common_label(label: str) -> bool:
    """Libellé assez long dont les mots de plus de trois lettres sont tous courants (écarté par le filtre comme mot courant)."""
    return len(label.strip()) >= MIN_LENGTH and _only_common_words(label)


def common_word_lines(text: str) -> list:
    """Numéros de ligne physiques (à partir de 1) des entrées de la liste dont les mots de plus de trois lettres sont tous courants.
    Jamais l'entrée ; une entrée de trois caractères ou moins n'est jamais signalée."""
    lignes = text.lstrip("﻿").splitlines()
    return [n for n, l in enumerate(lignes, 1) if l.strip() and not l.strip().startswith("#") and _only_common_words(l)]


def find_field(fields: dict, names):
    """Nom du premier champ dont la valeur contient un nom listé, sinon None. Ne renvoie jamais le nom trouvé."""
    motifs = _motifs(names)
    for champ, valeur in fields.items():
        if line_matches(motifs, str(valeur)):
            return champ
    return None
