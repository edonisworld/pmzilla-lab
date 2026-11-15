#!/usr/bin/env python3
"""PMZilla Lab : conditions de `npm ci` pour une session (change npm-ci-session, décisions R-20261030-11 (a), R-20261031-53 et
R-20261031-60). Module importé par tools/npm_guard.py pour une commande réduite à `npm ci` seulement, jamais lancé.

La garde npm refuse `npm ci` à une session. Elle fait une seule exception, décidée ici : `npm ci` sans option, lancé dans le dossier
`mothra` d'un worktree de branche, quand les paquets installés seraient ceux que l'auteur a déjà installés et audités. Deux formes seulement
(design D2) : `npm ci`, le dossier courant du hook étant le dossier `mothra` d'un worktree, et `cd <dossier> && npm ci`, le dossier étant
un seul mot littéral, absolu ou relatif au dossier courant du hook. Aucune option, aucun alias, aucun lanceur, rien avant ni après.

Conditions (R-20261030-11 (a), sans ajout) :
  - le dossier est le dossier `mothra` de la racine d'un worktree lié (jamais l'espace de travail), sous le dossier des worktrees du lab ;
  - aucun verrou de fin de branche dans le dossier Git commun (périmé ou non : dans le doute, refusé) ;
  - `origin/main` lisible, tel que le dépôt l'a reçu au dernier fetch (ce module ne fetch jamais) ;
  - aucune modification non commitée dans le worktree (fichiers non suivis compris, fichiers ignorés exclus) ;
  - chaque `package.json`, `package-lock.json` et `.npmrc` sous `mothra/`, hors des dossiers `node_modules`, a le même contenu sur le disque
    et dans `origin/main` ; un `.npmrc` présent sur le disque et absent de `origin/main` est une différence.

`verifier(dossier, worktrees=None)` rend la liste ordonnée des conditions en échec, des paires (code, chemin relatif ou None) : c'est la
décision ; `message(echecs)` ne fait que l'imprimer (phrases fixes, en français, de la conception D7). `echecs(commande, cwd)` enchaîne la
forme (`forme_admise`, fonction pure sur le lecteur de shell de la garde) puis `verifier`.

Lecture seule : Git avec des arguments fixes (rev-parse, ls-tree, status, cat-file), l'entrée standard fermée, aucune variable GIT_*, le
PATH système et une borne de temps pour l'ensemble de la vérification ; un parcours de mothra/ qui saute node_modules. Ne fetch, ne pull,
n'écrit aucun fichier, ne lance ni npm ni node, n'ouvre aucune connexion, ne lit rien hors du worktree et de son dossier Git commun.
Toute exception ou tout dépassement de temps donne le motif `impossible` (refusé).

Limites énoncées (design D12), hors de la vérification : la configuration npm de l'utilisateur et globale, les variables npm de
l'environnement de la session (la garde refuse déjà une affectation `npm_config_*` dans la commande), la version de Node, un `origin/main` plus
ancien que main local, un CDPATH posé dans le profil de l'utilisateur et absent de l'environnement du hook (le `cd` relatif n'est refusé que si le hook le voit), un filtre clean de Git (lfs…) configuré par l'auteur que `git status` pourrait lancer, ou un `.gitattributes` qui en nomme un (la comparaison tient contre les paquets que l'auteur a commités et audités à ce moment), un fichier modifié entre
le contrôle du hook et le départ de npm dans le même appel, un `npm ci` lancé par un script ou un programme (aucun hook ne le voit).

Ce que cette exception remplace : les deux règles `deny` de `npm ci` nu et de `cd … && npm ci` nu (design D8, retirées par le fichier
d'étape de l'auteur) et les gestes de l'auteur pour `npm ci` sur les worktrees neufs de la session.
Condition de retrait : tombe avec le changement qui donne à un worktree son `node_modules` sans `npm ci` de la session (cache indexé par
l'empreinte du verrou, R-20261030-39 point 2, ou runners isolés, R-20261030-15). Ce changement retire ce module, l'exception de
tools/npm_guard.py et leurs tests, et remet les deux règles de D8, dans la même branche.
"""
import os
import subprocess
import time
import unicodedata
from pathlib import Path

# Source du nom du verrou : tools/finish_lock.py (LOCK_NAME). Un test compare les deux ; un écart échoue en nommant les deux valeurs.
NOM_VERROU = "pmzilla-fin-en-cours"
FICHIERS_PAQUET = {"package-lock.json": "verrou", "package.json": "paquet", ".npmrc": "npmrc"}
LECTURES_GIT = ("rev-parse", "ls-tree", "status", "cat-file")
DELAI_TOTAL = 8.0   # secondes pour toute la vérification ; le hook de la garde a une borne de 10 secondes
ENV_GIT = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LC_ALL": "C"}   # le PATH système, aucune variable GIT_*

# Ordre des conditions, celui des phrases de la conception D7.
ORDRE = ("forme", "worktree", "fin", "origine", "non-commite", "verrou", "paquet", "npmrc", "impossible")

PHRASES = {
    "forme": "forme non admise (aucune option, aucun alias, rien avant ni après)",
    "worktree": "pas dans le dossier mothra d'un worktree (espace de travail, dossier d'exécution ou autre dossier)",
    "fin": "fin en cours (verrou de fin présent)",
    "origine": "état Git illisible ou origin/main introuvable",
    "non-commite": "modification non commitée dans le worktree",
    "verrou": "package-lock.json différent de origin/main : <chemin>",
    "paquet": "package.json différent de origin/main : <chemin>",
    "npmrc": ".npmrc absent de origin/main ou différent : <chemin>",
    "impossible": "vérification impossible",
}
PREFIXE = "garde npm : npm ci refusé : "
FIN_DE_MESSAGE = (". Une session lance npm ci seulement sous la forme « npm ci » ou « cd <dossier> && npm ci », dans le dossier mothra "
                  "d'un worktree propre, sans fin en cours, avec les package.json, package-lock.json et .npmrc de mothra/ identiques à "
                  "origin/main. Un verrou modifié, avec son npm install et son audit, reste à l'auteur.")

MARQUEURS_DU_LECTEUR = "\x01\x02\x03\x04\x05\x06\x07"
INTERDITS_DANS_UN_MOT = set(MARQUEURS_DU_LECTEUR) | set("~*?[]{}$`\\!#<>|&;()'\"") | {"\n", "\r", "\t", "\x00"}


def _cle(nom: str) -> str:
    """Nom comparé comme le disque du Mac : normalisation NFC puis casefold (`.NPMRC`, `package.jſon` valent `.npmrc`, `package.json`)."""
    return unicodedata.normalize("NFC", nom).casefold()


class Impossible(Exception):
    """Une lecture qui ne peut pas aboutir (temps écoulé, Git illisible) : la vérification est refusée."""


# --- La forme ---------------------------------------------------------------------------------------------------------------------------

def _mot_litteral(mot: str) -> bool:
    return bool(mot) and not any(c in INTERDITS_DANS_UN_MOT for c in mot)


def forme_admise(commande, cwd):
    """Le dossier visé (chemin absolu résolu) quand la commande est exactement `npm ci` ou `cd <dossier> && npm ci`, sinon None.
    Fonction pure sur le lecteur de shell de la garde (decouper, segments) : aucune expression régulière sur le texte de la commande.
    `npm ci` nu demande le dossier courant du hook ; `cd` accepte un mot littéral, absolu ou relatif à ce dossier."""
    import npm_guard
    if not isinstance(commande, str) or "\n" in commande or "#" in commande:
        return None
    sous_commandes = []
    try:
        jetons = npm_guard.decouper(commande, sous_commandes)
    except Exception:   # Syntaxe comprise : illisible, refusé
        return None
    if sous_commandes:
        return None
    cwd_utile = cwd if isinstance(cwd, str) and os.path.isabs(cwd) else None
    if jetons == [("w", "npm"), ("w", "ci")]:
        return os.path.realpath(cwd_utile) if cwd_utile else None
    if (len(jetons) == 5 and jetons[0] == ("w", "cd") and jetons[2] == ("op", "&&")
            and jetons[3:] == [("w", "npm"), ("w", "ci")] and jetons[1][0] == "w"):
        dossier = jetons[1][1]
        if not _mot_litteral(dossier) or dossier.startswith(("-", "+", "=")):
            return None
        if {".", ".."} & set(dossier.split("/")):   # « .. » est physique ici et logique pour le shell (lien symbolique) : refusé
            return None
        if os.path.isabs(dossier):
            return os.path.realpath(dossier)
        if os.environ.get("CDPATH") or not cwd_utile:   # sous bash, CDPATH peut envoyer « cd mothra » ailleurs : cd relatif refusé
            return None
        return os.path.realpath(os.path.join(cwd_utile, dossier))
    return None


# --- Les lectures de Git ------------------------------------------------------------------------------------------------------------------

class _Git:
    def __init__(self, dossier: str, fin: float):
        self.dossier, self.fin = dossier, fin

    def lire(self, sous_commande: str, *arguments: str):
        """(code, sortie, erreur) d'une lecture de Git, la sortie en octets."""
        if sous_commande not in LECTURES_GIT:
            raise Impossible
        reste = self.fin - time.monotonic()
        if reste <= 0:
            raise Impossible
        r = subprocess.run(["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", self.dossier, sous_commande, *arguments],
                           stdin=subprocess.DEVNULL, capture_output=True, timeout=reste, env=ENV_GIT)
        return r.returncode, r.stdout, r.stderr


def _dossier_des_worktrees(commun: str, worktrees):
    """Le dossier des worktrees du lab, résolu par le module des chemins du lab (jamais écrit ici), liens suivis."""
    if worktrees is not None:
        return os.path.realpath(str(worktrees))
    import lab_paths
    contenu = lab_paths.content_root()   # depuis la racine de code de la garde (ou PMZILLA_LAB_WORKSPACE), jamais depuis le dépôt visé
    if os.path.realpath(str(Path(commun).parent)) != os.path.realpath(str(contenu)):
        return None   # un dépôt hors du lab : aucun dossier de worktrees ne lui convient
    return os.path.realpath(str(lab_paths.worktrees_folder(contenu)))


def _sous(dossier: str, parent) -> bool:
    return parent is not None and dossier != parent and os.path.commonpath([dossier, parent]) == parent


def _fichiers_du_disque(top: str, fin: float) -> dict:
    """{chemin relatif à la racine du worktree : contenu} des fichiers de paquet sous mothra/, hors node_modules."""
    trouves = {}
    for racine, dossiers, fichiers in os.walk(os.path.join(top, "mothra")):
        if time.monotonic() > fin:
            raise Impossible
        dossiers[:] = [d for d in dossiers if d != "node_modules"]
        for nom in fichiers:
            if _cle(nom) in FICHIERS_PAQUET:   # le disque du Mac ne distingue pas .NPMRC de .npmrc : npm lit l'un comme l'autre
                chemin = os.path.join(racine, nom)
                with open(chemin, "rb") as f:
                    trouves[os.path.relpath(chemin, top)] = f.read()
    return trouves


def _fichiers_de_origine(git: _Git) -> dict:
    """{chemin : contenu} des mêmes fichiers dans origin/main."""
    code, sortie, _ = git.lire("ls-tree", "-r", "-z", "--full-tree", "refs/remotes/origin/main", "--", "mothra")
    if code != 0:
        raise Impossible
    trouves = {}
    for entree in sortie.split(b"\0"):
        meta, _, chemin = entree.partition(b"\t")
        if not chemin:
            continue
        texte = os.fsdecode(chemin)
        morceaux = texte.split("/")
        if _cle(morceaux[-1]) not in FICHIERS_PAQUET or "node_modules" in morceaux[:-1]:
            continue
        code, contenu, _ = git.lire("cat-file", "blob", meta.split()[2].decode("ascii"))
        if code != 0:
            raise Impossible
        trouves[texte] = contenu
    return trouves


def _verifier(dossier, worktrees):
    fin = time.monotonic() + DELAI_TOTAL
    cible = os.path.realpath(str(dossier))
    if not os.path.isdir(cible):
        return [("worktree", None)]
    git = _Git(cible, fin)
    code, sortie, erreur = git.lire("rev-parse", "--path-format=absolute", "--show-toplevel", "--git-dir", "--git-common-dir")
    if code != 0:
        return [("worktree", None)] if b"not a git repository" in erreur else [("origine", None)]
    lignes = sortie.decode("utf-8", "surrogateescape").split("\n")
    if len(lignes) < 3 or not all(lignes[:3]):
        return [("origine", None)]
    top, gitdir, commun = (os.path.realpath(ligne) for ligne in lignes[:3])
    if cible != os.path.join(top, "mothra") or gitdir == commun or not _sous(top, _dossier_des_worktrees(commun, worktrees)):
        return [("worktree", None)]
    echecs = []
    if os.path.lexists(os.path.join(commun, NOM_VERROU)):
        echecs.append(("fin", None))
    code, _, _ = git.lire("rev-parse", "--verify", "--quiet", "refs/remotes/origin/main^{commit}")
    origine_lisible = code == 0
    if not origine_lisible:
        echecs.append(("origine", None))
    code, sortie, _ = git.lire("status", "--porcelain=v1", "--untracked-files=normal")
    if code != 0:
        if origine_lisible:
            echecs.append(("origine", None))
    elif sortie.strip():
        echecs.append(("non-commite", None))
    if origine_lisible:
        sur_disque, dans_origine = _fichiers_du_disque(top, fin), _fichiers_de_origine(git)
        for chemin in sorted(set(sur_disque) | set(dans_origine)):
            if sur_disque.get(chemin) != dans_origine.get(chemin):
                echecs.append((FICHIERS_PAQUET[_cle(chemin.rsplit("/", 1)[-1])], chemin))
    return sorted(echecs, key=lambda e: ORDRE.index(e[0]))   # le tri est stable : les chemins gardent leur ordre alphabétique


def verifier(dossier, worktrees=None) -> list:
    """Les conditions en échec, dans l'ordre de la conception D7, sous forme de paires (code, chemin relatif ou None) ; [] si `npm ci`
    est admis dans ce dossier. `worktrees` remplace le dossier des worktrees du lab (tests). Toute exception : `impossible`."""
    try:
        return _verifier(dossier, worktrees)
    except Exception:   # Impossible, TimeoutExpired, OSError, MemoryError : dans le doute, refusé
        return [("impossible", None)]


def echecs(commande, cwd, worktrees=None) -> list:
    """La décision pour une commande réduite à `npm ci` : la forme d'abord (elle arrête seule), puis les conditions du dossier."""
    try:
        cible = forme_admise(commande, cwd)
        if cible is None:
            return [("forme", None)]
        return verifier(cible, worktrees)
    except Exception:
        return [("impossible", None)]


# --- Le message ---------------------------------------------------------------------------------------------------------------------------

def _propre(chemin) -> str:
    return "".join(c if c.isprintable() else "?" for c in str(chemin))


def phrase(code: str, chemin=None) -> str:
    return PHRASES[code].replace("<chemin>", _propre(chemin) if chemin else "")


def message(liste) -> str:
    """La ligne unique d'un `npm ci` refusé : le préfixe, les phrases des conditions en échec jointes par « ; », la phrase de fin.
    Elle n'imprime ni la commande, ni le chemin absolu du worktree, ni le contenu d'un fichier."""
    return PREFIXE + "; ".join(phrase(code, chemin) for code, chemin in liste) + FIN_DE_MESSAGE
