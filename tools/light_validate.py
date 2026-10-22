#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""Validation OpenSpec du chemin allégé : seulement les éléments que la branche touche, seulement les nouveaux avertissements stricts
(change light-finish-touched-specs, design D1 à D3). Bibliothèque standard seulement.

    python3 -I tools/light_validate.py <main> <sommet>
    python3 tools/light_validate.py main HEAD

À lancer à la racine de l'arbre à valider (le worktree, ou l'espace de travail sur la branche). <main> est la référence de main à jour,
<sommet> le sommet de la branche. Variable pour les tests : LIGHT_VALIDATE_OPENSPEC, la commande OpenSpec (défaut : openspec).

Éléments touchés (D1), d'après « git diff --name-only --no-renames <main> <sommet> -- openspec/ » :
  - openspec/changes/<nom>/… (hors archive) : le change <nom>, s'il existe encore au sommet ;
  - openspec/specs/<capacité>/… : la spécification <capacité>, si elle existe encore au sommet ;
  - openspec/changes/archive/… : aucun élément ;
  - tout autre chemin sous openspec/ : tous les changes et toutes les spécifications du sommet.

Chaque élément est validé en mode strict (« openspec validate <élément> --type <change|spec> --strict --json --no-interactive ») dans l'arbre
courant et dans l'arbre de main, exporté par « git archive » dans un dossier temporaire supprimé à la sortie (D2). Un avertissement est le
couple (niveau, message), le chemin n'est pas comparé ; seuls les niveaux ERROR et WARNING comptent. Il est nouveau quand son nombre au sommet
dépasse celui de main ; un élément absent de main a tous ses avertissements nouveaux.

Sorties (rien d'autre n'est écrit) :
  0  « validation OpenSpec : <n> élément(s) touché(s), aucun nouvel avertissement strict », plus, s'il y en a,
     « avertissements stricts déjà présents sur main, non bloquants : <éléments> » ;
     ou « validation OpenSpec : aucun élément à valider (archives seulement) »
  1  une ligne « nouvel avertissement strict : <élément> : <message> » par avertissement nouveau ;
     ou « validation OpenSpec illisible pour <élément> » (sortie de la commande qui n'est pas le JSON attendu)
  127 la commande OpenSpec est absente ou non exécutable (les appelants prennent alors le runner complet)
"""
import collections
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile

NIVEAUX = ("ERROR", "WARNING")


class CommandeAbsente(Exception):
    pass


class Illisible(Exception):
    pass


def git(*args):
    return subprocess.run(["git", *args], capture_output=True)


def chemins_changes(principal, sommet):
    r = git("diff", "--name-only", "--no-renames", "-z", principal, sommet, "--", "openspec/")
    if r.returncode != 0:
        raise SystemExit("light_validate : git diff impossible : %s" % r.stderr.decode(errors="replace").strip())
    return [c for c in r.stdout.decode().split("\0") if c]


def existe_au_sommet(sommet, chemin):
    return git("cat-file", "-e", "%s:%s" % (sommet, chemin)).returncode == 0


def tous_les_elements(sommet):
    elements = []
    for genre, dossier in (("change", "openspec/changes"), ("spec", "openspec/specs")):
        r = git("ls-tree", "-d", "--name-only", sommet, dossier + "/")
        for ligne in r.stdout.decode().splitlines():
            nom = ligne.rsplit("/", 1)[-1]
            if genre == "change" and nom == "archive":
                continue
            elements.append((genre, nom))
    return sorted(elements)


def elements_touches(principal, sommet):
    tous = False
    elements = set()
    for chemin in chemins_changes(principal, sommet):
        parties = chemin.split("/")
        if len(parties) >= 4 and parties[1] == "changes" and parties[2] == "archive":
            continue
        if len(parties) >= 4 and parties[1] in ("changes", "specs"):
            genre = "change" if parties[1] == "changes" else "spec"
            if existe_au_sommet(sommet, "/".join(parties[:3])):
                elements.add((genre, parties[2]))
            continue
        tous = True
    return tous_les_elements(sommet) if tous else sorted(elements)


def exporter_main(principal, destination):
    r = git("archive", principal, "openspec")
    if r.returncode != 0:
        return   # main sans dossier openspec/ : chaque élément est nouveau
    with tarfile.open(fileobj=io.BytesIO(r.stdout)) as archive:
        if hasattr(tarfile, "data_filter"):
            archive.extractall(destination, filter="data")
        else:
            archive.extractall(destination)


def avertissements(commande, racine, genre, nom):
    try:
        r = subprocess.run(commande + ["validate", nom, "--type", genre, "--strict", "--json", "--no-interactive"],
                           cwd=racine, stdin=subprocess.DEVNULL, capture_output=True, text=True)
    except (FileNotFoundError, PermissionError):
        raise CommandeAbsente()
    if r.returncode in (126, 127):
        raise CommandeAbsente()
    try:
        donnees = json.loads(r.stdout)
        trouvailles = collections.Counter()
        for element in donnees["items"]:
            for probleme in element.get("issues", []):
                if probleme.get("level") in NIVEAUX:
                    trouvailles[(probleme["level"], probleme["message"])] += 1
    except (ValueError, KeyError, TypeError, AttributeError):
        raise Illisible()
    return trouvailles


def main(argv):
    if len(argv) != 3:
        print("usage : light_validate.py <main> <sommet>", file=sys.stderr)
        return 2
    principal, sommet = argv[1], argv[2]
    commande = shlex.split(os.environ.get("LIGHT_VALIDATE_OPENSPEC") or "openspec")
    elements = elements_touches(principal, sommet)
    if not elements:
        print("validation OpenSpec : aucun élément à valider (archives seulement)")
        return 0
    temporaire = tempfile.mkdtemp(prefix="light-validate-")
    try:
        exporter_main(principal, temporaire)
        nouvelles, anciennes = [], []
        for genre, nom in elements:
            etiquette = "%s %s" % (genre, nom)
            try:
                au_sommet = avertissements(commande, os.getcwd(), genre, nom)
                if os.path.isdir(os.path.join(temporaire, "openspec", "changes" if genre == "change" else "specs", nom)):
                    sur_main = avertissements(commande, temporaire, genre, nom)
                else:
                    sur_main = collections.Counter()
            except CommandeAbsente:
                return 127
            except Illisible:
                print("validation OpenSpec illisible pour %s" % etiquette)
                return 1
            if sur_main:
                anciennes.append(etiquette)
            for (niveau, message), nombre in sorted(au_sommet.items()):
                for _ in range(nombre - sur_main.get((niveau, message), 0)):
                    nouvelles.append("nouvel avertissement strict : %s : %s" % (etiquette, message))
        if nouvelles:
            print("\n".join(nouvelles))
            return 1
        print("validation OpenSpec : %d élément(s) touché(s), aucun nouvel avertissement strict" % len(elements))
        if anciennes:
            print("avertissements stricts déjà présents sur main, non bloquants : %s" % ", ".join(anciennes))
        return 0
    finally:
        shutil.rmtree(temporaire, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
