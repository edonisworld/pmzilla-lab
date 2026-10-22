#!/usr/bin/env python3
"""PMZilla Lab : cherche, en lecture seule, les noms sensibles dans les messages de commit, sans jamais afficher le nom ni le message.

Origine : fix/sorties-et-masquage, décision de l'auteur du 2026-10-21, point 3 (un nom d'équipe n'entre jamais dans un message de commit,
et une fuite vers GitHub au push est irréversible).

    python3 tools/commit_names_scan.py [--depot DOSSIER] [-- RÉVISION ...]
    python3 tools/commit_names_scan.py --message FICHIER|- [--sans-ciseaux]

Sans révision : les commits locaux non poussés, branches et étiquettes locales (git log --branches --tags --not --remotes ; une étiquette
déjà poussée dont le commit n'est sur aucune branche distante reste comptée). Avec des révisions après « -- » : celles-ci, passées telles
quelles à git log (par exemple « -- origin/main..main » ou « -- <sha> --not --remotes=origin »). Le crochet pre-push s'en sert pour les
commits qui partent ; le crochet commit-msg (option --message) pour le message en cours, et pre-push aussi pour le message d'une étiquette
annotée (« --message - --sans-ciseaux », lu sur l'entrée standard).

En mode --message, toutes les lignes comptent, lignes « # » comprises (elles peuvent rester dans le commit : git commit -m "# …",
--cleanup=verbatim ou whitespace), jusqu'à la ligne de ciseaux de git (« # ------------------------ >8 ------------------------ ») : ce qui
la suit (le diff de git commit -v) n'est jamais commité et n'est pas lu. --sans-ciseaux lit le texte entier.

Listes et règles : celles du crochet pre-commit, par tools/sensitive_names.py. La liste des noms sensibles (PMZILLA_LAB_SENSITIVE_NAMES,
puis PMZILLA_NOMS, sinon Flux-Lab/noms-sensibles.txt du dossier de contenu) et les noms distinctifs de l'extrait des équipes qui la voisine ;
mot entier, casse ignorée sauf pour les noms de 3 caractères ou moins et les sigles en majuscules. Liste absente ou illisible : rien n'est
lu, code 2 (fermé par défaut, comme pre-commit) ; liste vide sans nom dans l'extrait : avertissement « liste vide », code 0.

Sortie : chaque ligne commence par « commit_names_scan : ». Une ligne par commit touché, « nom dans le message du commit <sha court> », puis
le compte « <n> commit(s) lu(s), <m> dont le message contient un nom » ; avec --message, une ligne « nom dans le message, ligne <n> » par
ligne touchée. Jamais le nom trouvé, jamais le texte du message. Une erreur inattendue (module des noms en échec compris) donne le code 3 et
le seul type de l'exception, jamais sa trace. Aucune écriture, ni dans le dépôt ni ailleurs.

Codes : 0 aucun nom ; 1 au moins un ; 2 liste indisponible ; 3 usage, lecture des commits ou du message impossible, erreur inattendue.

Exemple (avant une fin de branche, depuis l'espace de travail) :
    python3 tools/commit_names_scan.py
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import sensitive_names  # noqa: E402
    ERREUR_IMPORT = None
except Exception as _erreur:   # noqa: BLE001 : une trace pourrait citer une ligne ; le type seul est dit (code 3)
    sensitive_names = None
    ERREUR_IMPORT = _erreur

PREFIXE = "commit_names_scan : "
PAR_DEFAUT = ["--branches", "--tags", "--not", "--remotes"]
SEPARATEUR = "\x1f"
CISEAUX = re.compile(r"^\S{0,2} ?-{24} >8 -{24}\s*$")   # ligne de ciseaux de git, caractère de commentaire quelconque


class ListeIndisponible(Exception):
    """La liste des noms sensibles est absente ou illisible ; `motif` vaut « absente » ou « illisible »."""

    def __init__(self, motif):
        self.motif = motif
        super().__init__(motif)


class UsageInvalide(Exception):
    pass


class Analyseur(argparse.ArgumentParser):
    def error(self, message):
        raise UsageInvalide(message)


def motifs_des_listes():
    """Motifs compilés de la liste et de l'extrait voisin, comme le crochet pre-commit ; liste vide (aucun nom nulle part) : []."""
    try:
        chemin = sensitive_names.default_path()
    except SystemExit:   # PMZILLA_LAB_WORKSPACE sur un dossier absent (lab_paths) : la liste n'est pas trouvable
        raise ListeIndisponible("absente") from None
    if not chemin.is_file():
        raise ListeIndisponible("absente")
    try:
        texte = chemin.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        raise ListeIndisponible("illisible") from None
    noms = sensitive_names.parse_names(texte) + sensitive_names.extract_names(chemin.parent / sensitive_names.NOM_EXTRAIT)
    return sensitive_names.patterns(noms)


def avant_les_ciseaux(texte):
    """Les lignes du texte jusqu'à la ligne de ciseaux de git, exclue (tout le texte sans elle)."""
    lignes = texte.splitlines()
    for n, ligne in enumerate(lignes):
        if CISEAUX.match(ligne):
            return lignes[:n]
    return lignes


def lignes_touchees(motifs, lignes):
    """Numéros (à partir de 1) des lignes qui contiennent un nom."""
    return [n for n, ligne in enumerate(lignes, 1) if sensitive_names.line_matches(motifs, ligne)]


def messages(depot, revisions):
    """(sha court, message) de chaque commit des révisions ; None si git log échoue (révision inconnue, hors dépôt)."""
    fait = subprocess.run(["git", "log", "-z", f"--format=%h{SEPARATEUR}%B", *revisions, "--"], cwd=depot, capture_output=True,
                          stdin=subprocess.DEVNULL)
    if fait.returncode != 0:
        return None
    sortie = fait.stdout.decode("utf-8", errors="replace")
    return [tuple(bloc.split(SEPARATEUR, 1)) for bloc in sortie.split("\0") if SEPARATEUR in bloc]


def dire(texte, erreur=False):
    print(f"{PREFIXE}{texte}", file=sys.stderr if erreur else sys.stdout)


def executer(argv):
    revisions = []
    if "--" in argv:
        coupe = argv.index("--")
        argv, revisions = argv[:coupe], argv[coupe + 1:]
    parser = Analyseur(description="Cherche les noms sensibles dans les messages de commit (lecture seule)")
    parser.add_argument("--depot", default=".", help="dépôt Git à lire (défaut : le dossier courant)")
    parser.add_argument("--message", help="contrôle ce fichier de message (« - » : l'entrée standard) au lieu des commits")
    parser.add_argument("--sans-ciseaux", action="store_true", help="avec --message : lit le texte entier, sans coupe à la ligne de ciseaux")
    args = parser.parse_args(argv)
    if args.message and revisions:
        raise UsageInvalide("--message ne se combine pas avec des révisions")
    if args.sans_ciseaux and not args.message:
        raise UsageInvalide("--sans-ciseaux va avec --message")
    try:
        motifs = motifs_des_listes()
    except ListeIndisponible as erreur:
        dire(f"liste des noms sensibles {erreur.motif} : vérification impossible, refus par défaut "
             "(indique la liste avec PMZILLA_LAB_SENSITIVE_NAMES=<chemin>)", erreur=True)
        return 2
    if not motifs:
        dire("garde-fou des noms inactif : liste vide", erreur=True)

    if args.message:
        try:
            if args.message == "-":
                texte = sys.stdin.buffer.read().decode("utf-8", errors="replace")
            else:
                texte = Path(args.message).read_text(encoding="utf-8", errors="replace")
        except OSError as erreur:
            dire(f"lecture du message impossible ({type(erreur).__name__})", erreur=True)
            return 3
        lignes = texte.splitlines() if args.sans_ciseaux else avant_les_ciseaux(texte)
        touchees = lignes_touchees(motifs, lignes) if motifs else []
        for numero in touchees:
            dire(f"nom dans le message, ligne {numero}")
        return 1 if touchees else 0

    lus = messages(args.depot, revisions or PAR_DEFAUT)
    if lus is None:
        dire("lecture des commits impossible (git log en échec : révision inconnue ou hors dépôt)", erreur=True)
        return 3
    touches = [sha for sha, texte in lus if motifs and lignes_touchees(motifs, texte.splitlines())]
    for sha in touches:
        dire(f"nom dans le message du commit {sha}")
    dire(f"{len(lus)} commit(s) lu(s), {len(touches)} dont le message contient un nom")
    return 1 if touches else 0


def main(argv=None):
    """Toute erreur inattendue sort en code 3 avec le seul type de l'exception : jamais en code 1 (nom trouvé), jamais une trace."""
    if ERREUR_IMPORT is not None:
        dire(f"erreur inattendue ({type(ERREUR_IMPORT).__name__}) : vérification impossible", erreur=True)
        return 3
    try:
        return executer(sys.argv[1:] if argv is None else argv)
    except UsageInvalide as erreur:
        dire(f"usage : {erreur}", erreur=True)
        return 3
    except Exception as erreur:   # noqa: BLE001
        dire(f"erreur inattendue ({type(erreur).__name__}) : vérification impossible", erreur=True)
        return 3


if __name__ == "__main__":
    sys.exit(main())
