# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
PMZilla Lab : génère le manuel d'utilisation en français, une section par fonctionnalité (change user-manual, R-73).

    uv run tools/manual.py                  imprime le manuel sur la sortie standard, n'écrit rien
    uv run tools/manual.py --write          écrit docs/pmzilla/manuel.md
    uv run tools/manual.py --check          compare le fichier à la sortie, n'écrit rien
    uv run tools/manual.py --root DOSSIER   racine du dépôt (pour les tests ; défaut : le dépôt du script)

Le manuel est construit en LISANT les fichiers : l'arbre syntaxique des scripts Python de tools/, l'en-tête des scripts shell, le
front-matter des commandes de .claude/commands/ et la liste permissions.deny de .claude/settings.json. Aucun script décrit n'est
importé, exécuté ni lancé, aucun processus n'est démarré, aucun réseau ni base ni Trousseau n'est touché. Les modules de
bibliothèque sans point d'entrée, les scripts de hooks et les modèles de tâches planifiées n'ont pas d'entrée.

Chaque commande est rangée dans une zone par la table TABLE de ce fichier ; une commande absente de la table passe dans la
section « Non classées » (le test du dépôt réel échoue alors en la nommant). La sortie est déterministe : mêmes sources, mêmes octets.
Une commande ajoutée ou modifiée régénère le manuel dans le même commit (uv run tools/manual.py --write).

Codes de sortie : 0 imprimé, écrit, ou contrôle réussi ; 1 contrôle : le manuel diffère de la sortie ou est absent ; 2 erreur d'usage,
racine introuvable ou source illisible.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import manual_deny  # noqa: E402
import manual_python  # noqa: E402
import manual_shell  # noqa: E402

PREFIXE = "manual : "
CHEMIN_MANUEL = "docs/pmzilla/manuel.md"
COMMANDE_ECRITURE = "uv run tools/manual.py --write"
VALEUR_CALCULEE = manual_python.VALEUR_CALCULEE
NON_CLASSEES = "Non classées"
MARQUEURS = ("<", ">", "...", "XXX", "chemin/vers")
LANCEURS_EXEMPLE = r"(?:uv run(?: --with \S+)*(?: python3?)?|python3?|bash|zsh)"
NOTE_PLANIFIEE = "lancée aussi par une tâche planifiée"

SECTIONS = [
    "Installation", "Flux et Jira", "Base", "Bibliothèque", "Veille", "Journal et cas", "File de travail GitHub",
    "Branches et worktrees", "Sauvegardes", "Diagnostic (doctor)", "Édition", "Évaluation des postures et tableau de bord",
    "Tests et contrôles",
]

# Zone de chaque commande : chemin de lancement (script) ou /nom (commande slash). Une seule table, jamais lue dans les scripts.
TABLE: dict[str, str] = {
    # Installation
    "tools/install_hooks.sh": "Installation",
    "tools/install_lab.py": "Installation",
    "tools/install_lab.sh": "Installation",
    "tools/install_links.sh": "Installation",
    "tools/bmad_remplacements.py": "Installation",
    "tools/composants.py": "Installation",
    "tools/sanctum_refresh.py": "Installation",
    "tools/migrate_watch.py": "Installation",
    # Flux et Jira
    "tools/dependencies_jira.py": "Flux et Jira",
    "tools/epic_statuses.py": "Flux et Jira",
    "tools/export_jira_api.py": "Flux et Jira",
    "tools/flow_board.py": "Flux et Jira",
    "tools/flow_compare.py": "Flux et Jira",
    "tools/flow_monthly.py": "Flux et Jira",
    "tools/flow_retention.py": "Flux et Jira",
    "tools/flux_jira.py": "Flux et Jira",
    "tools/history_jira.py": "Flux et Jira",
    "tools/segment_sample.py": "Flux et Jira",
    "/dependencies": "Flux et Jira",
    "/monthly-flow": "Flux et Jira",
    # Base
    "tools/db.py": "Base",
    "tools/db_up.sh": "Base",
    "tools/flow_import.py": "Base",
    "tools/flow_views.py": "Base",
    # Bibliothèque
    "tools/convert_books.py": "Bibliothèque",
    "tools/pmzilla_lab_library.py": "Bibliothèque",
    "tools/sort_by_domain.py": "Bibliothèque",
    "tools/sorting_exclusions.py": "Bibliothèque",
    "tools/caption_diagnostic.py": "Bibliothèque",
    "tools/outside_library.py": "Bibliothèque",
    "tools/book_usage.py": "Bibliothèque",
    "tools/library_parity.py": "Bibliothèque",
    "/add-books": "Bibliothèque",
    # Veille
    "tools/watch.sh": "Veille",
    "tools/watch_lab.py": "Veille",
    "tools/watch_paths.py": "Veille",
    "tools/watch_triage.py": "Veille",
    "tools/morning_summary.py": "Veille",
    "/watch-digest": "Veille",
    # Journal et cas
    "tools/journal_lab.py": "Journal et cas",
    "tools/cases_calibration.py": "Journal et cas",
    "tools/critic_mirror.py": "Journal et cas",
    "/journal": "Journal et cas",
    "/critic-mirror": "Journal et cas",
    # File de travail GitHub
    "tools/gh_issue.py": "File de travail GitHub",
    "tools/roadmap.py": "File de travail GitHub",
    "/next": "File de travail GitHub",
    "/start": "File de travail GitHub",
    "/batch": "File de travail GitHub",
    "/close": "File de travail GitHub",
    "/implement": "File de travail GitHub",
    # Branches et worktrees
    "tools/finish_branch.sh": "Branches et worktrees",
    "tools/finish_worktree.sh": "Branches et worktrees",
    "tools/worktree.sh": "Branches et worktrees",
    "tools/run_worktree.sh": "Branches et worktrees",
    # Sauvegardes
    "tools/db_backup.sh": "Sauvegardes",
    "tools/db_restore_test.sh": "Sauvegardes",
    "tools/offsite_backup.sh": "Sauvegardes",
    "tools/sauvegarde_sanctum.sh": "Sauvegardes",
    # Diagnostic (doctor)
    "tools/doctor.py": "Diagnostic (doctor)",
    "tools/doctor.sh": "Diagnostic (doctor)",
    "/doctor": "Diagnostic (doctor)",
    # Édition
    "tools/build_edition.py": "Édition",
    "tools/publish_edition.py": "Édition",
    "/update-readme": "Édition",
    # Évaluation des postures et tableau de bord
    "tools/posture_evals.py": "Évaluation des postures et tableau de bord",
    "tools/evals_auto.sh": "Évaluation des postures et tableau de bord",
    "tools/dashboard.py": "Évaluation des postures et tableau de bord",
    "tools/final_messages_check.py": "Évaluation des postures et tableau de bord",
    "/roundtable": "Évaluation des postures et tableau de bord",
    "/adapt-message": "Évaluation des postures et tableau de bord",
    # Tests et contrôles
    "tests/run_all.sh": "Tests et contrôles",
    "tools/identifiants_personnels.py": "Tests et contrôles",
    "tools/select_suites.py": "Tests et contrôles",
    "tools/manual.py": "Tests et contrôles",
    "tools/dbtest.sh": "Tests et contrôles",
    "/audit": "Tests et contrôles",
}


# Dérogations : « Qui lance » vient d'abord des règles deny, mais CLAUDE.md et les règles de session interdisent aussi à Claude Code des
# lancements que ces règles n'attrapent pas (lecture de Flux-Lab/exports/, base de données, vraies sources Jira, contenu des livres,
# disque externe). Clé : (nom du script, sous-commande) ; la sous-commande None vaut pour le script et toutes ses sous-commandes.
# Valeur : la raison. Le libellé est toujours « Terminal seulement ». Un test du dépôt réel échoue si l'un de ces scripts sort autrement.
DEROGATIONS: dict[tuple[str, str | None], str] = {
    ("dependencies_jira.py", None): "le CSV lit Flux-Lab/exports/ (lecture interdite à la session) et --source db est réservé à l'utilisateur",
    ("flux_jira.py", None): "--source db est réservé à l'utilisateur, le CSV lit Flux-Lab/exports/",
    ("export_jira_api.py", None): "vraie API Jira, lancée par l'utilisateur seul",
    ("history_jira.py", None): "vraie API Jira et historique des statuts, lancés par l'utilisateur seul",
    ("db.py", None): "scripts de base de données, réservés à l'utilisateur",
    ("pmzilla_lab_library.py", None): "l'indexeur écrit dans la base et lit les livres ; réservé à l'utilisateur",
    ("offsite_backup.sh", None): "disque externe chiffré des sauvegardes, réservé à l'utilisateur",
    ("convert_books.py", None): "conversion des livres, réservée à l'utilisateur",
    ("sort_by_domain.py", None): "tri des livres par domaine, réservé à l'utilisateur",
    ("caption_diagnostic.py", None): "lit le texte Markdown d'un livre (dossier de contenu)",
    ("migrate_watch.py", None): "déplace et parcourt le dossier de contenu de la veille",
    ("watch_lab.py", None): "lit et écrit Watch-Lab, appelle le réseau",
    ("watch_triage.py", None): "lit les articles de Watch-Lab/watch/ et écrit dans Watch-Lab",
    ("watch.sh", None): "enchaîne la collecte, le pré-tri et l'indexation sur Watch-Lab, sous launchd",
    ("composants.py", "check"): "interroge le réseau (sources des versions) ; lancé par la veille ou par l'utilisateur (fiche C18 de R-41)",
    ("segment_sample.py", None): "lit les exports CSV et le cache d'historique de Flux-Lab (lecture interdite à la session)",
}


class SourceIllisible(Exception):
    def __init__(self, chemin: str, type_erreur: str):
        super().__init__(f"{chemin} ({type_erreur})")
        self.chemin = chemin
        self.type_erreur = type_erreur


def relatif(racine: Path, chemin: Path) -> str:
    return chemin.relative_to(racine).as_posix()


def scripts_python(racine: Path) -> list[Path]:
    return sorted(p for p in (racine / "tools").glob("*.py") if p.is_file())


def lire(racine: Path, chemin: Path, lecteur):
    try:
        return lecteur(chemin)
    except (SyntaxError, UnicodeDecodeError, ValueError) as erreur:
        raise SourceIllisible(relatif(racine, chemin), type(erreur).__name__) from erreur


def commandes_trouvees(racine: Path) -> set[str]:
    """Identifiants des commandes décrites : scripts Python avec point d'entrée, scripts shell, run_all.sh, commandes slash."""
    trouvees = set()
    for chemin in scripts_python(racine):
        if lire(racine, chemin, manual_python.lire_script) is not None:
            trouvees.add(relatif(racine, chemin))
    trouvees.update(relatif(racine, c) for c in manual_shell.scripts_shell(racine))
    if (racine / "tests" / "run_all.sh").is_file():
        trouvees.add("tests/run_all.sh")
    trouvees.update(f"/{c.stem}" for c in manual_shell.commandes_slash(racine))
    return trouvees


def exemple_valide(ligne: str, nom_script: str) -> bool:
    """Une ligne d'usage devient l'exemple : elle lance le script lui-même, sans crochet ni marqueur (design D3)."""
    if any(m in ligne for m in MARQUEURS) or any(c in ligne for c in "[]|"):
        return False
    return re.match(rf"{LANCEURS_EXEMPLE} (?:\./)?(?:tools|tests)/{re.escape(nom_script)}(?:\s|$)", ligne) is not None


METAVAR_CHOIX = re.compile(r"^\{([^{}]+)\}$")


def choix_de(argument: dict):
    """Les choix littéraux d'un argument ; à défaut, ceux que son metavar écrit en `{a,b}` (cas de --source {csv,db})."""
    if argument["choix"]:
        return argument["choix"]
    correspondance = METAVAR_CHOIX.match(argument.get("metavar") or "")
    return [c.strip() for c in correspondance.group(1).split(",")] if correspondance else argument["choix"]


def options_de(arguments: list[dict]) -> list[str]:
    """Options littérales à essayer contre les règles deny : chaque nom, avec chacun de ses choix littéraux."""
    options = []
    for argument in arguments:
        if argument["positionnel"]:
            continue
        for nom in argument["noms"]:
            choix = choix_de(argument)
            if isinstance(choix, list) and choix:
                options.extend(f"{nom} {c}" for c in choix)
            else:
                options.append(nom)
    return options


def exemple_genere(nom_script: str, parseur: dict | None) -> str | None:
    """Exemple construit depuis le parseur seulement quand chaque argument obligatoire a un choix ou un défaut littéral."""
    if parseur is None:
        return None
    morceaux = [f"uv run tools/{nom_script}"]
    sous = [s for s in parseur["sous_commandes"] if s["nom"] != VALEUR_CALCULEE]
    arguments = parseur["arguments"]
    if parseur.get("sous_commandes_requises") and sous:
        morceaux.append(sous[0]["nom"])
        arguments = arguments + sous[0]["arguments"]
    elif parseur.get("sous_commandes_requises"):
        return None
    for argument in arguments:
        if argument["exclusif"] is not None:
            continue
        if not argument["requis"]:
            continue
        if isinstance(argument["choix"], list) and argument["choix"]:
            valeur = argument["choix"][0]
        elif argument["defaut"] not in (None, VALEUR_CALCULEE):
            valeur = argument["defaut"]
        elif argument["action"] in ("store_true", "store_false") and not argument["positionnel"]:
            valeur = None
        else:
            return None
        if argument["positionnel"]:
            morceaux.append(valeur)
        else:
            morceaux.append(argument["noms"][0] if valeur is None else f"{argument['noms'][0]} {valeur}")
    exemple = " ".join(morceaux)
    return exemple if exemple_valide(exemple, nom_script) else None


def premier_exemple(usages: list[str], nom_script: str) -> str | None:
    return next((u for u in usages if exemple_valide(u, nom_script)), None)


def ligne_aide(texte: str | None) -> str:
    if not texte:
        return "-"
    return " ".join(texte.split()).replace("|", "\\|")


def tableau_parametres(arguments: list[dict]) -> list[str]:
    lignes = ["| Paramètre | Valeurs | Défaut | Obligatoire | Aide |", "|---|---|---|---|---|"]
    for a in arguments:
        if a["action"] in ("store_true", "store_false"):
            valeurs = "drapeau"
        elif choix_de(a) == VALEUR_CALCULEE:
            valeurs = VALEUR_CALCULEE
        elif choix_de(a):
            valeurs = ", ".join(choix_de(a))
        else:
            valeurs = "-"
        noms = ", ".join(f"`{n}`" for n in (a["noms"][:1] if a["positionnel"] else a["noms"]))
        defaut = ligne_aide(a["defaut"]) if a["defaut"] is not None else "-"
        lignes.append(f"| {noms} | {valeurs} | {defaut} | {'oui' if a['requis'] else 'non'} | {ligne_aide(a['aide'])} |")
    for numero in sorted({a["exclusif"] for a in arguments if a["exclusif"] is not None}):
        membres = ", ".join(f"`{a['noms'][0]}`" for a in arguments if a["exclusif"] == numero)
        lignes += ["", f"un seul parmi : {membres}"]
    return lignes


def bloc_parametres(parseur: dict) -> list[str]:
    sortie = ["**Paramètres**", ""]
    if parseur["arguments"]:
        sortie += tableau_parametres(parseur["arguments"])
    else:
        sortie.append("aucun paramètre")
    if parseur.get("fonction_partagee"):
        sortie += ["", f"options ajoutées par une fonction partagée : {VALEUR_CALCULEE}"]
    return sortie


def bloc_codes(codes: list[str] | None) -> list[str]:
    if not codes:
        return ["**Codes de sortie** : codes de sortie non documentés"]
    return ["**Codes de sortie**", ""] + [f"- {c}" for c in codes]


def bloc_exemple(exemple: str | None, langage: str = "bash") -> list[str]:
    if not exemple:
        return ["**Exemple** : aucun exemple"]
    return ["**Exemple**", "", f"```{langage}", exemple, "```"]


def bloc_usages(usages: list[dict]) -> list[str]:
    sortie = ["**Usage**", ""]
    for u in usages:
        sortie.append(f"- `{u['commande']}`" + (f" : {u['explication']}" if u["explication"] else ""))
    return sortie


def libelle_de(regles, derogations, nom, langage, sous_commande=None, options=()):
    """Libellé « Qui lance » : la dérogation du script (ou de la sous-commande) d'abord, sinon les règles deny."""
    if (nom, None) in derogations or (nom, sous_commande) in derogations:
        return manual_deny.TERMINAL_SEUL
    return manual_deny.classer(regles, nom, langage, sous_commande, options)


def qui_lance(libelle: str, planifie: bool) -> str:
    return f"**Qui lance** : {libelle}" + (f" ({NOTE_PLANIFIEE})" if planifie else "")


def entree_python(racine: Path, chemin: Path, regles: list[str], planifies: set[str], derogations: dict) -> list[str]:
    donnees = lire(racine, chemin, manual_python.lire_script)
    nom, parseur = chemin.name, donnees["parseur"]
    identifiant = relatif(racine, chemin)
    role = donnees["role"] or (parseur and parseur["description"]) or "rôle non documenté"
    options = options_de(parseur["arguments"]) if parseur else []
    libelle = libelle_de(regles, derogations, nom, "python", None, options)
    lignes = [f"### {identifiant}", "", f"**Rôle** : {role}", "", qui_lance(libelle, identifiant in planifies), ""]
    if parseur is None:
        usages = [{"commande": u, "explication": None} for u in donnees["usages"]]
        if usages:
            lignes += bloc_usages(usages) + [""]
        lignes += ["paramètres : voir l'usage", ""]
    else:
        sous = parseur["sous_commandes"]
        if sous:
            lignes += ["**Sous-commandes**", ""]
            for s in sous:
                if s["nom"] == VALEUR_CALCULEE:
                    continue
                lignes += [f"#### {s['nom']}", "", ligne_aide(s["aide"]) if s["aide"] else "-", ""]
                sous_libelle = libelle_de(regles, derogations, nom, "python", s["nom"], options_de(s["arguments"]))
                if sous_libelle != libelle:
                    lignes += [f"**Qui lance** : {sous_libelle}", ""]
                if s["sous_commandes"]:
                    lignes += ["sous-commandes imbriquées : " + ", ".join(s["sous_commandes"]), ""]
                if s["arguments"] or s.get("fonction_partagee"):
                    lignes += bloc_parametres(s) + [""]
            if any(s["nom"] == VALEUR_CALCULEE for s in sous):
                lignes += [f"sous-commandes ajoutées par une boucle : {VALEUR_CALCULEE}", ""]
        if parseur["arguments"] or parseur.get("fonction_partagee") or not sous:
            lignes += bloc_parametres(parseur) + [""]
    exemple = premier_exemple(donnees["usages"], nom) or exemple_genere(nom, parseur)
    lignes += bloc_codes(donnees["codes"]) + [""] + bloc_exemple(exemple)
    return lignes


def entree_shell(racine: Path, chemin: Path, regles: list[str], planifies: set[str], derogations: dict) -> list[str]:
    donnees = lire(racine, chemin, manual_shell.lire_shell)
    identifiant = relatif(racine, chemin)
    libelle = libelle_de(regles, derogations, chemin.name, "shell")
    lignes = [f"### {identifiant}", "", f"**Rôle** : {donnees['role'] or 'rôle non documenté'}", "",
              qui_lance(libelle, identifiant in planifies), ""]
    if donnees["usages"]:
        lignes += bloc_usages(donnees["usages"]) + [""]
    lignes += bloc_codes(donnees["codes"]) + [""]
    exemple = premier_exemple([u["commande"] for u in donnees["usages"]], chemin.name)
    return lignes + bloc_exemple(exemple)


def entree_slash(racine: Path, chemin: Path) -> list[str]:
    donnees = lire(racine, chemin, manual_shell.lire_commande)
    return [f"### /{chemin.stem}", "", f"**Rôle** : {donnees['description'] or 'rôle non documenté'}", "",
            "**Qui lance** : Claude Code seulement", "", f"**Argument** : {donnees['indice_argument'] or '-'}", "",
            f"**Modèle** : {donnees['modele'] or '-'}", ""] + bloc_exemple(
                manual_shell.exemple_commande(chemin.stem, donnees["indice_argument"]), "text")


def clef_de_tri(identifiant: str) -> tuple[int, str]:
    return (1 if identifiant.startswith("/") else 0, identifiant)


def entrees(racine: Path, derogations: dict) -> dict[str, list[str]]:
    """{identifiant : lignes de l'entrée} pour toutes les commandes décrites."""
    regles = manual_deny.lire_regles(racine / ".claude" / "settings.json")
    planifies = manual_shell.scripts_planifies(racine / "tools")
    resultat = {}
    for chemin in scripts_python(racine):
        if lire(racine, chemin, manual_python.lire_script) is not None:
            resultat[relatif(racine, chemin)] = entree_python(racine, chemin, regles, planifies, derogations)
    for chemin in manual_shell.scripts_shell(racine):
        resultat[relatif(racine, chemin)] = entree_shell(racine, chemin, regles, planifies, derogations)
    run_all = racine / "tests" / "run_all.sh"
    if run_all.is_file():
        resultat["tests/run_all.sh"] = entree_shell(racine, run_all, regles, planifies, derogations)
    for chemin in manual_shell.commandes_slash(racine):
        resultat[f"/{chemin.stem}"] = entree_slash(racine, chemin)
    return resultat


def construire(racine: Path, table: dict[str, str] | None = None, derogations: dict | None = None) -> str:
    """Le texte du manuel pour le dépôt `racine` ; `table` et `derogations` remplacent les tables du fichier (tests)."""
    racine = Path(racine)
    table = TABLE if table is None else table
    toutes = entrees(racine, DEROGATIONS if derogations is None else derogations)
    lignes = ["# Manuel d'utilisation de PMZilla Lab", "",
              "Généré par uv run tools/manual.py : ne pas modifier à la main.", ""]
    for zone in SECTIONS + [NON_CLASSEES]:
        ids = sorted((i for i in toutes if (table.get(i) if zone != NON_CLASSEES else None) == zone
                      or (zone == NON_CLASSEES and table.get(i) not in SECTIONS)), key=clef_de_tri)
        if not ids:
            continue
        lignes += [f"## {zone}", ""]
        for identifiant in ids:
            lignes += toutes[identifiant] + [""]
    lignes += ["## Hors du manuel", "",
               f"Ne sont pas décrits ici : les scripts de hooks Git du dossier `{manual_shell.DOSSIER_HOOKS}` et les modèles de "
               f"tâches planifiées `{manual_shell.MODELE_PLANIFIE}` (launchd).", ""]
    return "\n".join(l.rstrip() for l in lignes).rstrip("\n") + "\n"


def nombre_de_commandes(racine: Path) -> int:
    return len(commandes_trouvees(racine))


def main(argv: list[str]) -> int:
    analyseur = argparse.ArgumentParser(prog="manual.py", description="Génère le manuel d'utilisation en français.")
    mode = analyseur.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help=f"écrit {CHEMIN_MANUEL}")
    mode.add_argument("--check", action="store_true", help="compare le fichier à la sortie, n'écrit rien")
    analyseur.add_argument("--root", metavar="DOSSIER", default=str(Path(__file__).resolve().parents[1]),
                           help="racine du dépôt (pour les tests)")
    try:
        options = analyseur.parse_args(argv)
    except SystemExit as sortie:
        return 2 if sortie.code not in (0, None) else 0
    racine = Path(options.root)
    if not racine.is_dir():
        print(f"{PREFIXE}racine introuvable : {racine}", file=sys.stderr)
        return 2
    try:
        texte = construire(racine)
        total = nombre_de_commandes(racine)
    except SourceIllisible as erreur:
        print(f"{PREFIXE}source illisible : {erreur.chemin} ({erreur.type_erreur})", file=sys.stderr)
        return 2
    fichier = racine / CHEMIN_MANUEL
    if options.write:
        fichier.parent.mkdir(parents=True, exist_ok=True)
        fichier.write_text(texte, encoding="utf-8")
        print(f"{PREFIXE}{CHEMIN_MANUEL} écrit ({total} commandes)")
    elif options.check:
        if not fichier.is_file():
            print(f"{PREFIXE}le manuel est absent : {CHEMIN_MANUEL} ; régénérer avec : {COMMANDE_ECRITURE}", file=sys.stderr)
            return 1
        if fichier.read_text(encoding="utf-8") != texte:
            print(f"{PREFIXE}le manuel n'est pas à jour : {CHEMIN_MANUEL} ; régénérer avec : {COMMANDE_ECRITURE}", file=sys.stderr)
            return 1
        print(f"{PREFIXE}le manuel est à jour")
    else:
        sys.stdout.write(texte)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
