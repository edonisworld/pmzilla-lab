#!/usr/bin/env python3
"""PMZilla Lab : cherche, en lecture seule, secrets, noms sensibles et identifiants personnels dans une plage de commits, commit par commit. « fichier n°k » est le rang du fichier dans « git diff-tree -c -r --no-renames <sha> » (suppressions comprises) ; « masqué » remplace un nom donné par l'utilisateur qui contient lui-même une trouvaille.

    python3 -I tools/range_scan.py <sommet> [--branch NOM ...] [--repo DOSSIER] [--json]

Plage : toujours origin/main..<sommet>, jamais le main local (une session peut le déplacer) et jamais le seul diff net entre la base et le
sommet : un secret ajouté dans un commit intermédiaire puis retiré plus loin est dans les commits qui partent. Aucune option ne change la
base ; l'outil ne fait jamais de fetch et croit le suivi distant origin/main tel qu'il est (ses appelants font le fetch avant). Les commits
sont lus du plus ancien au plus récent, renommages désactivés. Un commit ordinaire est comparé à son parent (le commit racine, à l'arbre
vide). Un commit de fusion est lu en forme combinée non dense (-c, jamais --cc : un fichier listé sans bloc dense serait lu comme vide) : seules comptent les lignes marquées « + » dans toutes les colonnes, celles qui
n'existent dans aucun parent (contenu injecté ou résolution de conflit) ; les lignes venues d'un côté sont déjà lues dans les commits de ce
côté, ou sont sur origin/main. Seules les lignes ajoutées sont lues : une ligne retirée n'est jamais une trouvaille. Le numéro de ligne est
celui du fichier après le commit.

Ce qui est lu : les lignes ajoutées de chaque commit (secrets, noms et identifiants, quelle que soit la taille du fichier : aucune limite,
comme le crochet pre-commit ; R-20261107-33 point 1), le chemin de chaque fichier que le commit ajoute, copie ou modifie, le message
complet de chaque commit (lu sous le codec déclaré et sous UTF-8, trouvailles réunies) et chaque nom de branche donné (plus le nom du sommet quand
c'est une branche locale, ou la branche courante quand le sommet est HEAD ou @). Un dépôt superficiel (shallow) est refusé (code 3). Les auteurs et les
committers ne sont pas lus. Règles et listes : celles des crochets (tools/secret_scan.py, tools/commit_names_scan.py, tools/sensitive_names.py,
tools/identifiants_personnels.py). La liste des exemples de secrets déclarés est lue dans origin/main seulement (jamais dans le dossier de
travail, l'index ni un commit de la plage) : une branche qui se déclare un exemple ne s'exempte pas ; un exemple déclaré n'est jamais accepté
dans un message, un chemin ou un nom de branche. Un fichier binaire (Git ou octet nul) n'est pas lu : il est compté et listé, jamais passé sous silence. Aucun fichier texte n'est
écarté pour sa taille (le décompte « taille » du rapport reste à 0).

Sortie : chaque ligne commence par « range_scan : ». Jamais un nom, une valeur de secret, un identifiant, un nom de branche, une ligne de
texte ni un message de commit : une trouvaille se dit par sa nature, son fichier, sa ligne, son commit (sha court) et, pour un secret, sa
famille. Un chemin qui contient lui-même une trouvaille est remplacé par son rang dans le commit (« fichier n°<k> »). Avec --json, la sortie
standard est un document de format 1 (base, sommet, trouvailles, exemples acceptés, fichiers non examinés, avertissements, code), où un tel
chemin est une cellule masquée {"masked": true, "reason": "<nature> in path", "index": k}. Le texte et le JSON formatent le même rapport,
calculé par la fonction scan_range. L'outil n'écrit rien : ni référence, ni fichier, ni objet Git.

Codes : 0 rien trouvé ; 1 au moins une trouvaille ; 2 une liste est indisponible (noms sensibles absente ou illisible, exemples déclarés
  d'origin/main mal formée, identifiants illisibles), rien n'est lu ; 3 usage, origin/main introuvable, révision inconnue, Git en échec
  ou erreur inattendue (le type seul est dit, jamais son texte).

Python 3.9 (faux 65 du train automatique du 7 novembre, décision R-20261110-12) : l'outil s'importe sous Python 3.9, le python3 du système que voit le job launchd. Ses annotations
ne sont jamais évaluées à l'import (`from __future__ import annotations`, premier import) et il ne garde aucune forme de 3.10 évaluée à l'exécution (ni `X | Y` hors annotation, ni
`match`) ; les tests de tests/range_scan/ le gardent. Remplace : rien. Retrait : avec la garde de version de tools/finish_train.sh, quand un interpréteur absolu est adopté pour les appels
Python de la fin.

Exemple (avant une fin de branche, depuis l'espace de travail ; l'outil se lance sous python3 -I) :
    python3 tools/range_scan.py feat/ma-branche
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

OUTILS = Path(__file__).resolve().parent
sys.path.insert(0, str(OUTILS))


try:
    import commit_names_scan  # noqa: E402
    import identifiants_personnels  # noqa: E402
    import secret_scan  # noqa: E402
    import sensitive_names  # noqa: E402
    ERREUR_IMPORT = None
except Exception as _erreur:   # noqa: BLE001 : une trace pourrait citer une ligne ; le type seul est dit (code 3)
    ERREUR_IMPORT = _erreur

PREFIXE = "range_scan : "
FORMAT = 1
BASE = "origin/main"
REF_BASE = "refs/remotes/origin/main"
SEPARATEURS = {ord(c): " " for c in "\r\x0b\x0c\x1c\x1d\x1e\x85  "}   # ce que splitlines couperait en plus de \n
ENTETE_BLOC = re.compile(r"^@+ (?:-\d+(?:,\d+)? )+\+(\d+)")
NULS = {"0" * 40, "0" * 64}
USAGE = "python3 -I tools/range_scan.py <sommet> [--branch NOM ...] [--repo DIR] [--json]"
ETIQUETTE_NATURE = {"secret": "secret possible", "name": "nom sensible", "identifier": "identifiant personnel",
                    "encoding": "encodage déclaré incohérent"}
ORDRE_NATURES = ("name", "identifier", "secret")
# Ce que l'environnement hérité ne doit jamais changer : le dépôt lu, son index, ses objets, la lecture des chemins, le remplacement.
VARIABLES_RETIREES = ("GIT_REPLACE_REF_BASE", "GIT_LITERAL_PATHSPECS", "GIT_GLOB_PATHSPECS", "GIT_NOGLOB_PATHSPECS",
                      "GIT_ICASE_PATHSPECS", "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                      "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_SHALLOW_FILE")


class ScanError(Exception):
    """Erreur attendue : code de sortie et clé d'erreur du JSON (jamais de texte venu des données)."""

    def __init__(self, code, cle, tip=None):
        super().__init__(cle)
        self.code, self.cle, self.tip = code, cle, tip


class UsageInvalide(Exception):
    pass


@dataclass
class ScanReport:
    exit: int = 0
    error: str | None = None
    tip_given: str | None = None   # seulement pour « révision inconnue », jamais dans le JSON
    base_sha: str | None = None
    tip: str | None = None
    commits: int = 0
    findings: list = field(default_factory=list)
    accepted_examples: list = field(default_factory=list)
    n_binary: int = 0
    n_size: int = 0
    not_examined_files: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def not_examined(self) -> dict:
        return {"binary": self.n_binary, "size": self.n_size, "files": self.not_examined_files}

    def to_dict(self) -> dict:
        if self.error is not None:
            return {"format": FORMAT, "exit": self.exit, "error": self.error}
        return {"format": FORMAT, "base": {"ref": BASE, "sha": self.base_sha}, "tip": self.tip, "commits": self.commits,
                "findings": self.findings, "accepted_examples": self.accepted_examples, "not_examined": self.not_examined,
                "warnings": self.warnings, "exit": self.exit}


# --- Git, en lecture seule --------------------------------------------------------------------------------------------------------

def _git(repo, *args, check=True):
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_NO_REPLACE_OBJECTS"] = "1"   # un objet de remplacement (git replace) ne cache jamais un commit de la plage
    for variable in VARIABLES_RETIREES:
        env.pop(variable, None)
    try:
        fait = subprocess.run(["git", "--no-pager", *args], cwd=repo, capture_output=True, env=env, stdin=subprocess.DEVNULL)
    except OSError:
        raise ScanError(3, "git_failure") from None
    if check and fait.returncode != 0:
        raise ScanError(3, "git_failure")
    return fait


def _resoudre(repo, revision):
    """Le sha complet d'un commit, ou None."""
    fait = _git(repo, "rev-parse", "--verify", "--quiet", f"{revision}^{{commit}}", check=False)
    sortie = fait.stdout.decode("ascii", errors="replace").strip()
    return sortie if fait.returncode == 0 and sortie else None


# --- Listes -----------------------------------------------------------------------------------------------------------------------

def _listes(repo, racine, base):
    """(motifs des noms, exemples déclarés de la base `base` (sha résolu), identifiants) ; une liste indisponible : ScanError de code 2
    (fermé par défaut). Les modules des listes nomment parfois un fichier illisible : rien de leur sortie d'erreur ne sort d'ici."""
    with contextlib.redirect_stderr(io.StringIO()):
        return _listes_lues(repo, racine, base)


def _listes_lues(repo, racine, base):
    try:
        motifs = commit_names_scan.motifs_des_listes()
    except commit_names_scan.ListeIndisponible as erreur:
        raise ScanError(2, "names_list_" + ("absent" if erreur.motif == "absente" else "unreadable")) from None
    fait = _git(repo, "cat-file", "blob", f"{base}:{secret_scan.LISTE_EXEMPLES}", check=False)
    declares = set()
    if fait.returncode == 0:
        try:
            declares = secret_scan.parse_declared(fait.stdout.decode("utf-8"))
        except (UnicodeDecodeError, secret_scan.ListeInvalide):
            raise ScanError(2, "examples_list_malformed") from None
    try:
        identifiants = identifiants_personnels.identifiants(Path(racine))
    except (SystemExit, OSError, UnicodeDecodeError):
        raise ScanError(2, "identifiers_unreadable") from None
    return motifs, declares, identifiants


class Regles:
    """Les trois familles de recherche, appliquées à un texte d'une ligne ou à un message."""

    def __init__(self, motifs, declares, identifiants):
        self.motifs, self.declares, self.identifiants = motifs, declares, identifiants

    def nom(self, ligne):
        return bool(self.motifs) and sensitive_names.line_matches(self.motifs, ligne)

    def identifiant(self, texte):
        bas = texte.lower()
        return any(c in bas for c in self.identifiants)

    def texte(self, texte):
        """[(nature, famille)] d'un chemin, d'un message ou d'un nom de branche : un exemple déclaré n'est jamais accepté ici."""
        trouvees = [("secret", f.family) for f in secret_scan.findings(texte)]
        if any(self.nom(ligne) for ligne in texte.splitlines()):
            trouvees.append(("name", None))
        if self.identifiant(texte):
            trouvees.append(("identifier", None))
        return trouvees


# --- Lecture des commits ----------------------------------------------------------------------------------------------------------

def _fichiers_du_commit(repo, sha):
    """[(chemin en octets, chemin décodé, mode, blob)] de tous les fichiers du commit, dans l'ordre de Git (le rang commence à 1)."""
    fait = _git(repo, "diff-tree", "--cc", "-r", "--raw", "-z", "--no-renames", "--no-abbrev", "--no-commit-id", "--root", "--no-ext-diff", sha)
    morceaux = fait.stdout.split(b"\0")
    fichiers, i = [], 0
    while i < len(morceaux):
        meta = morceaux[i]
        if not meta.startswith(b":") or i + 1 >= len(morceaux):
            i += 1
            continue
        chemin = morceaux[i + 1]
        i += 2
        entete = meta.lstrip(b":")
        n = len(meta) - len(entete)
        champs = entete.decode("ascii", errors="replace").split(" ")
        mode, blob = champs[n], champs[2 * n + 1]
        fichiers.append((chemin, chemin.decode("utf-8", errors="replace"), mode, blob))
    return fichiers


def _lignes_ajoutees(patch: bytes):
    """([(numéro, texte)] des lignes ajoutées dans toutes les colonnes, binaire signalé par Git) d'un diff sans contexte."""
    ajoutees, binaire, dans_bloc, colonnes, courant = [], False, False, 1, 0
    for ligne in patch.decode("utf-8", errors="replace").split("\n"):
        if ligne.startswith("@@"):
            m = ENTETE_BLOC.match(ligne)
            if m is None:
                dans_bloc = False
                continue
            colonnes, courant, dans_bloc = len(ligne) - len(ligne.lstrip("@")) - 1, int(m.group(1)), True
            continue
        if not dans_bloc:
            if ligne.startswith(("Binary files ", "GIT binary patch")):
                binaire = True
            continue
        if ligne.startswith("diff "):   # jamais une ligne de bloc (elles commencent par une colonne) : fin du fichier
            dans_bloc = False
            continue
        if ligne.startswith("\\") or len(ligne) < colonnes:
            continue
        marques = ligne[:colonnes]
        if "-" in marques:
            continue
        if marques == "+" * colonnes:
            ajoutees.append((courant, ligne[colonnes:]))
        courant += 1
    return ajoutees, binaire


def _paquets(ajoutees):
    """Les lignes ajoutées consécutives, groupées : la famille de la clé privée a besoin de la ligne qui suit l'en-tête."""
    paquets = []
    for numero, texte in ajoutees:
        if paquets and paquets[-1][-1][0] + 1 == numero:
            paquets[-1].append((numero, texte))
        else:
            paquets.append([(numero, texte)])
    return paquets


def _masque(nature, rang):
    return {"masked": True, "reason": f"{nature} in path", "index": rang}


def _decoder_message(entetes: bytes, brut: bytes) -> list:
    """Les lectures du message : UTF-8 tolérant toujours, et le codec de l'en-tête « encoding » quand il y en a un (un en-tête peut mentir sur
    le vrai codage : les deux lectures sont faites, les trouvailles réunies). Codec inconnu ou message indécodable : git_failure."""
    codec = None
    for ligne in entetes.split(b"\n"):
        if ligne.startswith(b"encoding "):
            codec = ligne[len(b"encoding "):].decode("ascii", errors="replace").strip()
            break
    lectures = [brut.decode("utf-8", errors="replace")]
    incoherent = False
    if codec is not None:
        try:
            declaree = brut.decode(codec)
        except LookupError:
            raise ScanError(3, "git_failure") from None   # codec inconnu : fermé
        except (UnicodeDecodeError, ValueError):
            # fermé par défaut mais utile : si la lecture UTF-8 stricte réussit, elle suffit et l'incohérence est signalée
            try:
                brut.decode("utf-8")
            except UnicodeDecodeError:
                raise ScanError(3, "git_failure") from None
            incoherent = True
        else:
            if declaree not in lectures:
                lectures.append(declaree)
    return lectures, incoherent


def _lire_commit(repo, sha, regles, rapport):
    brut_commit = _git(repo, "cat-file", "commit", sha).stdout   # jamais « log » : log.showSignature et le format ajoutent du texte
    entetes, _, brut_message = brut_commit.partition(b"\n\n")
    trouvees_message = []
    lectures, incoherent = _decoder_message(entetes, brut_message)
    for lecture in lectures:
        for trouvee in regles.texte(lecture):
            if trouvee not in trouvees_message:
                trouvees_message.append(trouvee)
    if incoherent:
        rapport.findings.append({"kind": "encoding", "where": "message", "commit": sha, "file": None, "line": None, "family": None,
                                 "branch_index": None})
    for nature, famille in trouvees_message:
        rapport.findings.append({"kind": nature, "where": "message", "commit": sha, "file": None, "line": None, "family": famille,
                                 "branch_index": None})
    for rang, (brut, chemin, mode, blob) in enumerate(_fichiers_du_commit(repo, sha), 1):
        if blob in NULS:   # fichier supprimé : rien n'est ajouté
            continue
        natures = [n for n, _ in regles.texte(chemin)]
        masque = next((_masque(n, rang) for n in ORDRE_NATURES if n in natures), None)
        for nature, famille in regles.texte(chemin):
            rapport.findings.append({"kind": nature, "where": "path", "commit": sha, "file": _masque(nature, rang), "line": None,
                                     "family": famille, "branch_index": None})
        if mode == "160000":   # sous-module : son chemin est lu, il n'a pas de contenu
            continue
        affiche = masque if masque is not None else chemin
        contenu = _git(repo, "cat-file", "blob", blob).stdout
        binaire = b"\0" in contenu
        patch = b"" if binaire else _git(repo, "diff-tree", "-c", "-p", "-U0", "--no-renames", "--no-commit-id", "--root", "--no-ext-diff",
                                        "--no-textconv", "--text", sha, "--", b":(top,literal)" + brut).stdout
        if not binaire and not any(l.startswith(b"diff ") for l in patch.split(b"\n")):
            raise ScanError(3, "git_failure")   # fermé par défaut : un fichier que le patch ne montre pas n'est jamais lu comme propre
        ajoutees, binaire_git = ([], True) if binaire else _lignes_ajoutees(patch)
        if binaire or binaire_git:
            rapport.n_binary += 1
            rapport.not_examined_files.append({"commit": sha, "file": affiche, "reason": "binary"})
            continue
        for paquet in _paquets(ajoutees):
            texte = "\n".join(t.translate(SEPARATEURS) for _, t in paquet)
            refusees, acceptees = secret_scan.check(chemin, texte, regles.declares)
            for trouvaille in refusees:
                rapport.findings.append({"kind": "secret", "where": "line", "commit": sha, "file": affiche,
                                         "line": paquet[0][0] + trouvaille.line - 1, "family": trouvaille.family, "branch_index": None})
            for trouvaille in acceptees:
                rapport.accepted_examples.append({"commit": sha, "file": affiche, "line": paquet[0][0] + trouvaille.line - 1,
                                                  "family": trouvaille.family})
        for numero, texte in ajoutees:
            for nature, present in (("name", regles.nom(texte)), ("identifier", regles.identifiant(texte))):
                if present:
                    rapport.findings.append({"kind": nature, "where": "line", "commit": sha, "file": affiche, "line": numero,
                                             "family": None, "branch_index": None})


# --- Fonction de service ----------------------------------------------------------------------------------------------------------

def scan_range(repo, tip, branches) -> ScanReport:
    """Lit origin/main..<tip> commit par commit et rend le rapport ; toute la logique est ici, le texte et le JSON ne font que le formater.
    Erreur attendue (liste indisponible, base absente, révision inconnue, Git en échec) : rapport de code 2 ou 3, sans exception."""
    rapport = ScanReport(tip_given=tip)
    try:
        _scanner(str(repo), tip, list(branches), rapport)
    except ScanError as erreur:
        rapport.exit, rapport.error = erreur.code, erreur.cle
    return rapport


def _scanner(repo, tip, branches, rapport):
    if not tip or tip.startswith("-"):
        raise ScanError(3, "usage")
    racine = _git(repo, "rev-parse", "--show-toplevel").stdout.decode("utf-8", errors="replace").strip()
    if not racine:
        raise ScanError(3, "git_failure")
    repo = racine   # Git part toujours de la racine : --repo peut pointer un sous-dossier
    if _git(repo, "rev-parse", "--is-shallow-repository").stdout.decode("ascii", errors="replace").strip() == "true":
        raise ScanError(3, "git_failure")   # un dépôt superficiel cache des parents : la plage ne serait pas celle des commits qui partent
    base = _resoudre(repo, REF_BASE)
    if base is None:
        raise ScanError(3, "base_missing")
    sommet = _resoudre(repo, tip)
    if sommet is None:
        raise ScanError(3, "unknown_tip", tip)
    noms_de_branche = list(branches)
    complet = _git(repo, "rev-parse", "--symbolic-full-name", tip, check=False).stdout.decode("utf-8", errors="replace").strip()
    # x, heads/x et refs/heads/x se lisent comme la branche x ; x~0 n'est pas une branche ; HEAD et @ se lisent comme la branche courante
    # (au pire une fausse alerte), et rien quand HEAD est détachée
    nom_du_sommet = None
    if tip in ("HEAD", "@"):
        courante = _git(repo, "symbolic-ref", "--quiet", "--short", "HEAD", check=False)
        if courante.returncode == 0:
            nom_du_sommet = courante.stdout.decode("utf-8", errors="replace").strip() or None
    elif complet.startswith("refs/heads/"):
        nom_du_sommet = complet[len("refs/heads/"):]
    if nom_du_sommet is not None and nom_du_sommet not in noms_de_branche:
        noms_de_branche.append(nom_du_sommet)
    motifs, declares, identifiants = _listes(repo, racine, base)
    regles = Regles(motifs, declares, identifiants)
    rapport.base_sha, rapport.tip = base, sommet
    if not motifs:
        rapport.warnings.append("empty_names_list")
    for rang, nom in enumerate(noms_de_branche, 1):
        for nature, famille in regles.texte(nom):
            rapport.findings.append({"kind": nature, "where": "branch", "commit": None, "file": None, "line": None, "family": famille,
                                     "branch_index": rang})
    commits = _git(repo, "rev-list", "--topo-order", "--reverse", f"{base}..{sommet}").stdout.decode("ascii").split()
    rapport.commits = len(commits)
    for sha in commits:
        _lire_commit(repo, sha, regles, rapport)
    rapport.exit = 1 if rapport.findings else 0


# --- Formatage --------------------------------------------------------------------------------------------------------------------

def _fichier(valeur):
    return f"fichier n°{valeur['index']}" if isinstance(valeur, dict) else valeur


def _ligne_de_trouvaille(f):
    nature, court = ETIQUETTE_NATURE[f["kind"]], (f["commit"] or "")[:7]
    famille = f" ({secret_scan.label(f['family'])})" if f["family"] else ""
    if f["where"] == "line":
        return f"{nature} dans {_fichier(f['file'])}, ligne {f['line']}{famille}, commit {court}"
    if f["where"] == "path":
        return f"{nature} dans le chemin du fichier n°{f['file']['index']} du commit {court}"
    if f["kind"] == "encoding":
        return f"message : encodage déclaré incohérent, commit {court}"
    if f["where"] == "message":
        return f"{nature} dans le message du commit {court}{famille}"
    return f"{nature} dans le nom de branche n°{f['branch_index']}"


def _affichable(texte, repo):
    """Un nom donné par l'utilisateur n'est écrit que s'il ne contient rien de sensible ; listes indisponibles : jamais écrit."""
    try:
        racine = _git(repo, "rev-parse", "--show-toplevel").stdout.decode("utf-8", errors="replace").strip()
        base = _resoudre(repo, REF_BASE)
        if base is None:
            return "masqué"
        motifs, declares, identifiants = _listes(repo, racine, base)
        return texte if not Regles(motifs, declares, identifiants).texte(texte) else "masqué"
    except Exception:   # noqa: BLE001
        return "masqué"


def _phrase_d_erreur(rapport, repo):
    cle = rapport.error
    phrases = {
        "names_list_absent": "liste des noms sensibles absente : vérification impossible, refus par défaut",
        "names_list_unreadable": "liste des noms sensibles illisible : vérification impossible, refus par défaut",
        "examples_list_malformed": "liste des exemples déclarés d'origin/main mal formée : vérification impossible",
        "identifiers_unreadable": "identifiants personnels illisibles : vérification impossible",
        "usage": f"usage : {USAGE}",
        "base_missing": "origin/main introuvable",
        "git_failure": "lecture Git impossible (Git en échec)",
    }
    if cle == "unknown_tip":
        return f"révision inconnue : {_affichable(rapport.tip_given or '', repo)}"
    if cle.startswith("unexpected:"):
        return f"erreur inattendue ({cle.split(':', 1)[1]})"
    return phrases[cle]


def format_text(rapport, repo="."):
    """(lignes de la sortie standard, lignes de la sortie d'erreur), sans rien décider : tout vient du rapport."""
    if rapport.error is not None:
        return [], [PREFIXE + _phrase_d_erreur(rapport, repo)]
    sortie = [PREFIXE + _ligne_de_trouvaille(f) for f in rapport.findings]
    for a in rapport.accepted_examples:
        sortie.append(f"{PREFIXE}exemple déclaré accepté : {_fichier(a['file'])}, ligne {a['line']} ({secret_scan.label(a['family'])}), "
                      f"commit {a['commit'][:7]}")
    for n in rapport.not_examined_files:
        sortie.append(f"{PREFIXE}non examiné (binaire) : {_fichier(n['file'])}, commit {n['commit'][:7]}")
    compte = {k: sum(1 for f in rapport.findings if f["kind"] == k) for k in ETIQUETTE_NATURE}
    sortie.append(f"{PREFIXE}{rapport.commits} commit(s) lu(s) de {BASE} {rapport.base_sha[:7]} à {rapport.tip[:7]} : "
                  f"{compte['secret']} secret(s), {compte['name']} nom(s), {compte['identifier']} identifiant(s), "
                  f"{rapport.n_binary + rapport.n_size} fichier(s) non examiné(s) (binaire : {rapport.n_binary}, taille : {rapport.n_size})")
    erreur = [PREFIXE + "garde-fou des noms inactif : liste vide" for w in rapport.warnings if w == "empty_names_list"]
    return sortie, erreur


# --- Ligne de commande ------------------------------------------------------------------------------------------------------------

class Analyseur(argparse.ArgumentParser):
    def error(self, message):
        raise UsageInvalide(message)


def _analyser(argv):
    parser = Analyseur(prog="range_scan.py", description="Cherche secrets, noms sensibles et identifiants personnels dans origin/main..<sommet> "
                                                         "(lecture seule)")
    parser.add_argument("tip", metavar="sommet", help="révision qui désigne un commit : fin de la plage origin/main..<sommet>")
    parser.add_argument("--branch", action="append", default=[], help="nom de branche à lire aussi (répétable)")
    parser.add_argument("--repo", default=".", help="dépôt Git à lire (défaut : le dossier courant)")
    parser.add_argument("--json", action="store_true", help="document JSON de format 1 sur la sortie standard")
    return parser.parse_args(argv)


def main(argv=None):
    """Toute erreur inattendue sort en code 3 avec le seul type de l'exception : jamais en code 1, jamais une trace."""
    argv = list(sys.argv[1:] if argv is None else argv)
    en_json = "--json" in argv
    repo = "."
    if ERREUR_IMPORT is not None:
        rapport = ScanReport(exit=3, error=f"unexpected:{type(ERREUR_IMPORT).__name__}")
    else:
        try:
            args = _analyser(argv)
            repo = args.repo
            rapport = scan_range(args.repo, args.tip, args.branch)
        except UsageInvalide:
            rapport = ScanReport(exit=3, error="usage")
        except Exception as erreur:   # noqa: BLE001
            rapport = ScanReport(exit=3, error=f"unexpected:{type(erreur).__name__}")
    if en_json:
        print(json.dumps(rapport.to_dict(), ensure_ascii=False))
        return rapport.exit
    try:
        sortie, erreur = format_text(rapport, repo)
    except Exception as exception:   # noqa: BLE001
        sortie, erreur, rapport.exit = [], [f"{PREFIXE}erreur inattendue ({type(exception).__name__})"], 3
    for ligne in sortie:
        print(ligne)
    for ligne in erreur:
        print(ligne, file=sys.stderr)
    return rapport.exit


if __name__ == "__main__":
    sys.exit(main())
