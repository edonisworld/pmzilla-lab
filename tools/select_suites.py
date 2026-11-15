#!/usr/bin/env python3
"""Sélecteur de suites : lit les chemins de l'index Git et dit quelles suites de tests/ lancer (lancement ciblé, tests/run_all.sh --staged).

    python3 tools/select_suites.py [--root DOSSIER]
    python3 tools/select_suites.py --range <base>...<sommet> [--root DOSSIER]
    python3 tools/select_suites.py --openspec-readers [--root DOSSIER]

Règles (design.md D4 du change workflow-tooling) :
  - un chemin dans le dossier d'une suite (tests/<suite>/) sélectionne cette suite ; un script de test shell listé dans
    tests/suites_shell.txt (une ligne « chemin nom interprète » par suite) sélectionne sa suite shell ;
  - un chemin que le texte d'un fichier de test d'une suite nomme (chemin, ou nom de module pour un .py ou .sh, ou nom de fichier pour
    les autres) sélectionne cette suite ;
  - les suites qui parcourent tous les fichiers suivis (identifiants_personnels, secret_scan) sont toujours sélectionnées ;
  - le manuel généré (change user-manual) : un script .py ou .sh directement sous tools/, une commande de .claude/commands/ ou le
    fichier docs/pmzilla/manuel.md sélectionne en plus la suite « manual ». Ce renfort ne tient pas lieu de suite du chemin : un script
    qu'aucun test ne nomme exige toujours l'exécution complète, et le manuel est le seul fichier de documentation qui sélectionne une suite ;
  - Mothra (mothra-slices, D10, tranche 0) : avec la suite npm déclarée par la ligne SUITES_NPM=(<dossier>:<nom> …) de tests/run_all.sh (entrée mal
    formée : code 2), un fichier .ts ou .tsx sous mothra/ sélectionne cette suite seule ; tout autre chemin sous mothra/ sélectionne cette suite
    et les suites que ses chemins nomment ; mothra/package-lock.json et mothra/.node-version sélectionnent aussi « composants » ;
    contrats/vues.json, contrats/cas-parite.json, contrats/cas-masquage.json et contrats/schemas/ sélectionnent la suite npm et « flow_views ». Un chemin ainsi cartographié
    n'exige jamais l'exécution complète ; mothra/<sous-dossier>/package.json (R-20261101-02) ne cherche que son chemin complet, plus
    « run_all » et « composants » (mothra/package.json et les chemins plus profonds gardent la recherche par nom) ; sans la ligne, un chemin de Mothra l'exige ; un changement du lanceur l'exige aussi ;
  - documentation seule (docs/, openspec/, CHANGELOG.md, README.md, Markdown de _bmad-output/) : rien de plus ;
  - tout autre chemin qu'aucune suite ne nomme, et tout changement de CLAUDE.md, du fichier de réglages, du lanceur et de sa liste de suites
    shell (tests/suites_shell.txt), des hooks, des
    modules qu'importe le hook pre-commit (tools/secret_scan.py, tools/sensitive_names.py) ou du sélecteur, exige l'exécution complète
    (sûr par défaut).

Sortie : une ligne « select_suites : <suite> : <raison> » par suite (code 0), ou « select_suites : exécution complète requise : <chemins> »
(code 3). Code 2 : usage, hors dépôt Git, ou liste des suites shell mal formée (numéro de ligne dans le message). Le sélecteur ne lance aucun test, n'écrit aucun fichier et ne lit que l'index et tests/.
Limites assumées : une suite qui n'exerce un fichier que par une chaîne d'imports est manquée ; un test qui nomme un fichier dans un
commentaire sélectionne sa suite pour rien. Ces manques n'atteignent jamais main (le runner complet du train sur l'arbre intégré et pre-push
exigent un lancement complet vert).

Option --range <base>...<sommet> (change targeted-suites-admission, D3) : mêmes règles, mêmes sorties et mêmes codes, appliquées aux chemins de
« git diff --name-only --no-renames -z <base>...<sommet> » (lu dans le dépôt de --root), et aux tests de --root, sans lire l'index. Plage
absente, mal formée ou illisible : code 2. Remplace : rien. Retrait : tombe avec tests/run_all.sh --branch, son seul appelant avec le train.

Option --openspec-readers (change light-spec-finish, D6) : liste, sans lire l'index, les suites qui lisent le dossier OpenSpec, une ligne
« select_suites : <suite> : <raison> » chacune (code 0 ; 2 usage, hors dépôt, ou liste absente ou mal formée ; jamais 3). Règle (question Q10) :
(a) les gardes toujours sélectionnées (« garde toujours sélectionnée ») ; (b) les suites de la liste déclarée tests/openspec_readers.txt
(« déclarée (tests/openspec_readers.txt) »). Une ligne de la liste est « <suite> » éventuellement suivie de « # pourquoi », ou
« !<suite> : <raison> » pour une suite que le balayage de garde signale sans qu'elle lise openspec/ (jamais lancée). Le sélecteur ne lit que
cette liste ; la garde est tests/select_suites/test_openspec_readers.py, qui échoue quand une suite lit openspec/ sans être déclarée.

Exemple :
    python3 tools/select_suites.py
"""
import re
import subprocess
import sys
from pathlib import Path

PREFIXE = "select_suites : "
TOUJOURS = {"identifiants_personnels": "toujours sélectionnée : parcourt tous les fichiers suivis",
            "secret_scan": "toujours sélectionnée : parcourt tous les fichiers suivis"}
# tools/secret_scan.py et tools/sensitive_names.py, importés par le crochet pre-commit, comptent comme lui (pre-commit-secret-scan, D7) ;
# tools/commit_names_scan.py, lancé par les crochets commit-msg et pre-push, aussi (fix/sorties-et-masquage).
COMPLETS = {"CLAUDE.md", ".claude/settings.json", ".claude/settings.local.json", "tests/run_all.sh", "tests/suites_shell.txt",
            "tools/select_suites.py",
            "tools/secret_scan.py", "tools/sensitive_names.py", "tools/commit_names_scan.py",
            "tools/preuve_arbre.py"}   # lancé par le crochet pre-push (python3 -I), même précédent que commit_names_scan.py (ci-local-runner, D8)
PREFIXES_COMPLETS = ("tools/hooks/",)
DOCS_PREFIXES = ("docs/", "openspec/")
DOCS_FICHIERS = {"CHANGELOG.md", "README.md"}
SUITE_MANUEL = "manual"
CHEMIN_MANUEL = "docs/pmzilla/manuel.md"
MOT_OPTION = "--openspec-readers"
LISTE_LECTEURS = "tests/openspec_readers.txt"
RAISON_GARDE = "garde toujours sélectionnée"
RAISON_DECLAREE = f"déclarée ({LISTE_LECTEURS})"
LIGNE_LECTEUR = re.compile(r"^(?P<suite>[A-Za-z0-9_.-]+)(?:\s+#.*)?$")
LISTE_SHELL = "tests/suites_shell.txt"
LIGNE_SUITE_SHELL = re.compile(r"^(?P<chemin>tests/[A-Za-z0-9_./-]+\.sh)\s+(?P<nom>[A-Za-z0-9_-]+)\s+(?:sh|bash|zsh)$")
LANCEUR_NPM = "tests/run_all.sh"
LIGNE_SUITES_NPM = re.compile(r"^SUITES_NPM=\((.*)\)[ \t]*$")
ENTREE_SUITE_NPM = re.compile(r"^(?P<dossier>[A-Za-z0-9_-]+):(?P<nom>[A-Za-z0-9_-]+)$")
EXTENSIONS_TYPESCRIPT = (".ts", ".tsx")
DOSSIER_MOTHRA = "mothra"
# Mothra (mothra-slices, D10, tranche 0) : le verrou npm et le fichier de version de Node sélectionnent aussi la suite des composants ; les fichiers
# du contrat commun (vues, cas de parité, schémas générés) sélectionnent la suite npm et celle du lecteur des vues agrégées (flow_views).
CHEMINS_MOTHRA_COMPOSANTS = {"mothra/package-lock.json", "mothra/.node-version"}
CHEMINS_CONTRAT = {"contrats/vues.json", "contrats/cas-parite.json", "contrats/cas-masquage.json"}
PREFIXE_SCHEMAS_CONTRAT = "contrats/schemas/"
# R-20261101-02 (Q137) : le package.json d'un sous-dossier de mothra/ (mothra/<x>/package.json, trois segments) ne passe plus par la recherche par
# nom « package.json » (nommé par une trentaine de suites sans rapport) : recherche du chemin complet seulement, plus ces suites par cartographie
# explicite (run_all lit les workspaces, composants lit les dépendances épinglées). Remplace la recherche par nom pour ces seuls chemins ;
# mothra/package.json et les chemins plus profonds gardent la recherche par nom (décision (ii) du 2026-10-27). Condition de retrait : permanente
# tant que run_all et composants lisent ces package.json. Aucun test ne détecte un nouveau lecteur qui construit le chemin par jointure, ni l'arrêt
# de lecture par run_all ou composants : la source est cette cartographie, revue à chaque branche qui ajoute un lecteur de package.json.
SUITES_PACKAGE_JSON_SOUS_PAQUET = ("run_all", "composants")
LIGNE_EXEMPTION =re.compile(r"^!(?P<suite>[A-Za-z0-9_.-]+)\s*:\s*(?P<raison>\S.*)$")


class ListeInvalide(Exception):
    """La liste déclarée des lecteurs d'openspec est absente, illisible ou mal formée."""


def erreur_usage(texte: str) -> int:
    print(f"{PREFIXE}usage : {texte}", file=sys.stderr)
    return 2


def chemins_indexes(racine: Path) -> list[str] | None:
    fait = subprocess.run(["git", "diff", "--cached", "--name-only", "--no-renames", "-z"], cwd=racine, capture_output=True)
    if fait.returncode != 0:
        return None
    return [p for p in fait.stdout.decode("utf-8", errors="replace").split("\0") if p]


def chemins_plage(racine: Path, plage: str) -> list[str] | None:
    """Les chemins que change une plage « <base>...<sommet> » (différence à trois points), lue dans le dépôt de la racine (targeted-suites-admission, D3).
    None quand la plage ou le dépôt ne se lisent pas. Ne lit pas l'index."""
    fait = subprocess.run(["git", "diff", "--name-only", "--no-renames", "-z", plage, "--"], cwd=racine, capture_output=True)
    if fait.returncode != 0:
        return None
    return [p for p in fait.stdout.decode("utf-8", errors="replace").split("\0") if p]


def documentation(chemin: str) -> bool:
    return (chemin in DOCS_FICHIERS or chemin.startswith(DOCS_PREFIXES)
            or (chemin.startswith("_bmad-output/") and chemin.endswith(".md")))


def releve_du_manuel(chemin: str) -> bool:
    """Un script directement sous tools/, une commande slash ou le manuel lui-même : le manuel généré peut changer."""
    morceaux = chemin.split("/")
    return (chemin == CHEMIN_MANUEL
            or (len(morceaux) == 2 and morceaux[0] == "tools" and chemin.endswith((".py", ".sh")))
            or (len(morceaux) == 3 and morceaux[:2] == [".claude", "commands"] and chemin.endswith(".md")))


def suites_python(racine: Path) -> list[str]:
    tests = racine / "tests"
    if not tests.is_dir():
        return []
    return sorted(d.name for d in tests.iterdir() if d.is_dir() and any(d.glob("test_*.py")))


def suites_shell(racine: Path) -> dict[str, str]:
    """{chemin du script de test shell : nom de la suite}, d'après tests/suites_shell.txt (R-130), dans l'ordre du fichier.
    Fichier absent : {}. Lève ListeInvalide : fichier illisible ou ligne mal formée (numéro de ligne dans le message)."""
    chemin_liste = racine / LISTE_SHELL
    if not chemin_liste.is_file():
        return {}
    try:
        texte = chemin_liste.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        raise ListeInvalide(f"liste des suites shell illisible ({LISTE_SHELL})") from None
    suites: dict[str, str] = {}
    for numero, brute in enumerate(texte.splitlines(), start=1):
        ligne = brute.split("#", 1)[0].strip()
        if not ligne:
            continue
        m = LIGNE_SUITE_SHELL.match(ligne)
        if not m:
            raise ListeInvalide(f"{LISTE_SHELL}, ligne {numero} mal formée : « {brute} »")
        suites[m.group("chemin")] = m.group("nom")
    return suites


def suites_npm(racine: Path) -> dict[str, str]:
    """{dossier : nom de la suite npm}, d'après la ligne « SUITES_NPM=(<dossier>:<nom> …) » de tests/run_all.sh (mothra-slices, D9), dans l'ordre de la
    ligne. Fichier ou ligne absents : {} (aucun chemin de Mothra n'est alors cartographié : exécution complète). Lève ListeInvalide : fichier
    illisible ou entrée mal formée (numéro d'entrée)."""
    chemin_lanceur = racine / LANCEUR_NPM
    if not chemin_lanceur.is_file():
        return {}
    try:
        texte = chemin_lanceur.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        raise ListeInvalide(f"lanceur illisible ({LANCEUR_NPM})") from None
    suites: dict[str, str] = {}
    for brute in texte.splitlines():
        m = LIGNE_SUITES_NPM.match(brute)
        if not m:
            continue
        for numero, entree in enumerate(m.group(1).split(), start=1):
            e = ENTREE_SUITE_NPM.match(entree)
            if not e:
                raise ListeInvalide(f"{LANCEUR_NPM}, SUITES_NPM, entrée {numero} mal formée : « {entree} »")
            suites[e.group("dossier")] = e.group("nom")
        break
    return suites


def suites_cartographiees(chemin: str, py: list[str], npm: dict[str, str]) -> dict[str, str]:
    """Les suites que les règles de Mothra donnent à un chemin (D10, tranche 0) : {} si le chemin n'est pas cartographié ou si la suite npm
    de Mothra n'est pas déclarée. Un chemin cartographié ne passe jamais par la recherche générale ni par l'exécution complète."""
    suite_npm = npm.get(DOSSIER_MOTHRA)
    if suite_npm is None:
        return {}
    trouvees: dict[str, str] = {}
    if chemin.startswith(DOSSIER_MOTHRA + "/"):
        trouvees[suite_npm] = f"chemin sous {DOSSIER_MOTHRA}/"
        if chemin in CHEMINS_MOTHRA_COMPOSANTS and "composants" in py:
            trouvees["composants"] = "verrou npm ou version de Node"
    elif chemin in CHEMINS_CONTRAT or chemin.startswith(PREFIXE_SCHEMAS_CONTRAT):
        trouvees[suite_npm] = "contrat commun de Mothra"
        if "flow_views" in py:
            trouvees["flow_views"] = "contrat commun de Mothra"
    return trouvees


def textes_des_suites(racine: Path, py: list[str], shell: dict[str, str]) -> dict[str, str]:
    """{suite : texte concaténé de ses fichiers de test}."""
    textes: dict[str, list[str]] = {}
    for nom in py:
        for fichier in (racine / "tests" / nom).rglob("*"):
            if fichier.is_file() and fichier.suffix in (".py", ".sh"):
                textes.setdefault(nom, []).append(fichier.read_text(encoding="utf-8", errors="replace"))
    for chemin, nom in shell.items():
        fichier = racine / chemin
        if fichier.is_file():
            textes.setdefault(nom, []).append(fichier.read_text(encoding="utf-8", errors="replace"))
    return {nom: "\n".join(parties) for nom, parties in textes.items()}


def nom_cherche(chemin: str) -> str:
    p = Path(chemin)
    return p.stem if p.suffix in (".py", ".sh") else p.name


def suites_du_chemin(chemin: str, py: list[str], shell: dict[str, str], textes: dict[str, str]) -> dict[str, str]:
    trouvees: dict[str, str] = {}
    morceaux = chemin.split("/")
    if len(morceaux) > 2 and morceaux[0] == "tests" and morceaux[1] in py:
        trouvees[morceaux[1]] = "chemin dans la suite"
    if chemin in shell:
        trouvees[shell[chemin]] = "script de test shell listé"
    if len(morceaux) == 3 and morceaux[0] == DOSSIER_MOTHRA and morceaux[2] == "package.json":
        for suite, texte in textes.items():
            if suite not in trouvees and chemin in texte:
                trouvees[suite] = "chemin nommé par ses tests"
        for suite in SUITES_PACKAGE_JSON_SOUS_PAQUET:
            if suite in py and suite not in trouvees:
                trouvees[suite] = "package.json d'un sous-paquet de Mothra (cartographie)"
        return trouvees
    nom = nom_cherche(chemin)
    motif = re.compile(r"(?<![\w.-])" + re.escape(nom) + r"(?![\w-])")
    for suite, texte in textes.items():
        if suite in trouvees:
            continue
        if chemin in texte:
            trouvees[suite] = "chemin nommé par ses tests"
        elif motif.search(texte):
            trouvees[suite] = f"« {nom} » nommé par ses tests"
    return trouvees


def selectionner(racine: Path, chemins: list[str]) -> tuple[dict[str, list[str]], list[str]]:
    """(raisons par suite, chemins qui exigent l'exécution complète)."""
    py = suites_python(racine)
    shell = suites_shell(racine)
    npm = suites_npm(racine)
    textes = textes_des_suites(racine, py, shell)
    raisons: dict[str, list[str]] = {nom: [raison] for nom, raison in TOUJOURS.items()}
    complets: list[str] = []
    for chemin in chemins:
        if chemin in COMPLETS or chemin.startswith(PREFIXES_COMPLETS):
            complets.append(chemin)
            continue
        if releve_du_manuel(chemin) and SUITE_MANUEL in py:
            raisons.setdefault(SUITE_MANUEL, []).append(f"{chemin} (peut changer le manuel généré)")
        mappees = suites_cartographiees(chemin, py, npm)
        if mappees:
            for suite, motif in mappees.items():
                raisons.setdefault(suite, []).append(f"{chemin} ({motif})")
            if chemin.startswith(DOSSIER_MOTHRA + "/") and not chemin.endswith(EXTENSIONS_TYPESCRIPT):
                # autre chemin de Mothra : la suite npm, plus les suites que les tests nomment ; jamais l'exécution complète
                for suite, motif in suites_du_chemin(chemin, py, shell, textes).items():
                    raisons.setdefault(suite, []).append(f"{chemin} ({motif})")
            continue
        if documentation(chemin):
            continue
        suites = suites_du_chemin(chemin, py, shell, textes)
        if not suites:
            complets.append(chemin)
            continue
        for suite, motif in suites.items():
            raisons.setdefault(suite, []).append(f"{chemin} ({motif})")
    return raisons, complets


def lire_liste_lecteurs(racine: Path) -> tuple[dict[str, str], dict[str, str]]:
    """({suite : pourquoi} des lecteurs déclarés, {suite : raison} des exemptions) de tests/openspec_readers.txt (light-spec-finish, D6).
    Lignes vides et lignes commençant par « # » ignorées. Lève ListeInvalide : fichier absent ou illisible, ligne mal formée, suite en double."""
    chemin = racine / LISTE_LECTEURS
    try:
        texte = chemin.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        raise ListeInvalide(f"liste des suites qui lisent openspec/ introuvable ou illisible ({LISTE_LECTEURS})") from None
    lecteurs: dict[str, str] = {}
    exemptees: dict[str, str] = {}
    for numero, brute in enumerate(texte.splitlines(), start=1):
        ligne = brute.strip()
        if not ligne or ligne.startswith("#"):
            continue
        exemption = LIGNE_EXEMPTION.match(ligne)
        lecteur = None if exemption else LIGNE_LECTEUR.match(ligne)
        if not exemption and not lecteur:
            raise ListeInvalide(f"{LISTE_LECTEURS}, ligne {numero} mal formée : « {ligne} »")
        suite = (exemption or lecteur).group("suite")
        if suite in lecteurs or suite in exemptees:
            raise ListeInvalide(f"{LISTE_LECTEURS}, ligne {numero} : la suite « {suite} » est présente deux fois")
        if exemption:
            exemptees[suite] = exemption.group("raison").strip()
        else:
            lecteurs[suite] = ligne
    return lecteurs, exemptees


def lecteurs_openspec(racine: Path) -> dict[str, str]:
    """{suite : raison} des suites que le chemin allégé lance (light-spec-finish, D6, question Q10) : (a) les gardes toujours sélectionnées ;
    (b) les suites de la liste déclarée tests/openspec_readers.txt (les exemptions n'en font pas partie). Lève ListeInvalide."""
    lecteurs, _ = lire_liste_lecteurs(racine)
    trouvees: dict[str, str] = {nom: RAISON_GARDE for nom in TOUJOURS}
    for suite in lecteurs:
        trouvees.setdefault(suite, RAISON_DECLAREE)
    return trouvees


def main(argv: list[str]) -> int:
    racine = Path.cwd()
    arguments = list(argv)
    if arguments in (["-h"], ["--help"]):
        print(__doc__)
        return 0
    lecteurs = MOT_OPTION in arguments
    if lecteurs:
        arguments.remove(MOT_OPTION)
    plage = None
    while arguments:
        if arguments[0] == "--root":
            if len(arguments) < 2:
                return erreur_usage("--root demande un dossier")
            racine = Path(arguments[1])
            arguments = arguments[2:]
        elif arguments[0] == "--range" and plage is None:
            if len(arguments) < 2 or "..." not in arguments[1] or arguments[1].startswith("-"):
                return erreur_usage("--range demande une plage <base>...<sommet>")
            plage = arguments[1]
            arguments = arguments[2:]
        else:
            return erreur_usage("python3 tools/select_suites.py [--root DOSSIER] [--range BASE...SOMMET]")
    if lecteurs and plage is not None:
        return erreur_usage("--range ne se combine pas avec --openspec-readers")
    if lecteurs:
        sonde = subprocess.run(["git", "rev-parse", "--git-dir"], cwd=racine, capture_output=True) if racine.is_dir() else None
        if sonde is None or sonde.returncode != 0:
            print(f"{PREFIXE}pas un dépôt Git : {racine}", file=sys.stderr)
            return 2
        try:
            trouvees = lecteurs_openspec(racine)
        except ListeInvalide as erreur:
            print(f"{PREFIXE}{erreur}", file=sys.stderr)
            return 2
        for suite, raison in sorted(trouvees.items()):
            print(f"{PREFIXE}{suite} : {raison}")
        return 0
    chemins = chemins_indexes(racine) if plage is None else chemins_plage(racine, plage)
    if chemins is None:
        print(f"{PREFIXE}pas un dépôt Git : {racine}" if plage is None else f"{PREFIXE}plage illisible : {plage}", file=sys.stderr)
        return 2
    try:
        raisons, complets = selectionner(racine, chemins)
    except ListeInvalide as erreur:
        print(f"{PREFIXE}{erreur}", file=sys.stderr)
        return 2
    if complets:
        print(f"{PREFIXE}exécution complète requise : {', '.join(complets)}")
        return 3
    for suite in sorted(raisons):
        print(f"{PREFIXE}{suite} : {' ; '.join(raisons[suite][:3])}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
