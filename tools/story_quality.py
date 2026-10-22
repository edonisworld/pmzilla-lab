# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml", "jsonschema", "requests", "psycopg[binary]"]
# ///
"""
PMZilla Lab : qualité des stories et des epics (change story-quality-audit). Répartiteur des sous-commandes (design D14) ; un module par
sous-commande, chargé seulement quand elle est lancée :

    uv run tools/story_quality.py collect [--query <nom>] [--language fr|en]                   tools/story_quality_collect.py
    uv run tools/story_quality.py review --team <équipe> --sample <n> [--language fr|en]       tools/story_quality_review.py
    uv run tools/story_quality.py analyse [--sample <n> [--team <équipe>]] [--dry-run] [--language fr|en]
    uv run tools/story_quality.py coach (--team <équipe> | --keys <clé>...) [--show | --dry-run] [--language fr|en]
                                                                                               tools/story_quality_engine.py
    uv run tools/story_quality.py report --name <série> [--json] [--language fr|en]           tools/story_quality_report.py
    uv run tools/story_quality.py grid [--show [--json]] [--language fr|en]                    (ici)

Tant que le module d'une sous-commande n'est pas écrit, elle répond « pas encore disponible » avec le code 2. `collect`, `review`,
`analyse` et `coach`, essai compris, sont réservées à l'utilisateur, dans le Terminal : dans une session Claude Code (variable CLAUDECODE),
elles s'arrêtent avec le code 3 avant de lire le moindre réglage (design D5, garde-fou 4). `report` et `grid` ne lisent que les vues ou la
grille : la session peut les lancer.

`grid` valide le socle de la grille et la surcouche de l'organisation (design D17) et n'écrit que des versions et des effectifs ; elle ne
lit ni base, ni Jira, ni clé, et la session peut la lancer. Avec `--show`, elle écrit aussi les critères effectifs (code, libellés,
définition, question au moteur, condition « sans objet », lien, ligne de source ou marque « règle de l'organisation ») et la structure
attendue par genre ; jamais une raison de désactivation, l'identifiant de la surcouche ni le résumé de contexte du produit.
`grid --show` et `grid --show --json` mettent en forme le résultat d'une seule fonction de service, `effective_grid` de
tools/story_quality_data.py (design D15) ; avec `--json`, la sortie standard ne porte que le document du contrat `story_quality_grid`,
et la phrase « pas de surcouche » va sur la sortie d'erreur.

La surcouche est lue dans le sous-dossier `regles/` du dossier de contexte (variable PMZILLA_LAB_CONTEXT) ; sans fichier, le socle seul
s'applique. Le socle est lu dans tools/story_quality_grid.json (variable PMZILLA_LAB_STORY_GRID pour un autre chemin, utilisée par les tests).

Codes : 0 fait ; 1 erreur (Jira, base, moteur injoignable, réglages illisibles) ; 2 usage ; 3 prérequis refusé (session Claude Code,
champ de personne configuré, socle absent ou invalide, surcouche invalide ou portant un nom sensible ou un identifiant personnel, liste des
noms sensibles indisponible, bloc de réglages absent, plafond absent ou invalide ; pour `analyse` et `coach` aussi : clé d'analyse
absente, contenu de la surcouche changé sans nouvelle version, pas de terminal pour la confirmation, tous les éléments du lot bloqués
faute de relecture d'équipe).
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import identifiants_personnels  # noqa: E402
import sensitive_names  # noqa: E402
import story_quality_data as data  # noqa: E402
import story_quality_overlay as overlay_module  # noqa: E402
from messages import LANGUAGES, Messages  # noqa: E402
from story_quality_messages import CATALOGS  # noqa: E402

CORE_GRID_FILE = TOOLS / "story_quality_grid.json"
GRID_VARIABLE = "PMZILLA_LAB_STORY_GRID"
NAMES_VARIABLE = "PMZILLA_LAB_SENSITIVE_NAMES"
SESSION_VARIABLE = "CLAUDECODE"                 # posée par Claude Code dans ses terminaux

SOUS_COMMANDES = ("collect", "review", "analyse", "coach", "report", "grid")
RESERVEES_A_L_UTILISATEUR = ("collect", "review", "analyse", "coach")
# un module par sous-commande (grid reste ici). Un module écrit est importé par son nom dans `charger_module` (import statique, vu par
# le contrôle des dépendances de tests/script_dependencies) ; un module pas encore écrit passe par importlib et rend « pas encore
# disponible ». Quand un bloc écrit le sien, il remplace sa ligne d'importlib par un import statique.
MODULES = {"collect": "story_quality_collect", "review": "story_quality_review", "analyse": "story_quality_engine",
           "coach": "story_quality_engine", "report": "story_quality_report"}


class _Parser(argparse.ArgumentParser):
    def error(self, message):                                   # jamais d'écho de l'argument fautif
        raise ValueError("arguments")


def read_arguments(argv):
    parser = _Parser(prog="story_quality.py")
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)
    collect = sub.add_parser("collect", help="lit les stories et les epics dans Jira, nettoie leurs textes et les écrit dans la base "
                                             "(utilisateur seul)")
    collect.add_argument("--query", help="une seule requête nommée du bloc story_quality (aucune marque de sortie de collecte)")
    review = sub.add_parser("review", help="relecture d'un échantillon nettoyé d'une équipe, sans clés (utilisateur seul)")
    review.add_argument("--team", required=True)
    review.add_argument("--sample", required=True, help="taille de l'échantillon, entier positif")
    analyse = sub.add_parser("analyse", help="audit par le moteur d'analyse (utilisateur seul)")
    analyse.add_argument("--sample")
    analyse.add_argument("--team")
    analyse.add_argument("--dry-run", action="store_true")
    coach = sub.add_parser("coach", help="coaching par le moteur d'analyse (utilisateur seul)")
    choix = coach.add_mutually_exclusive_group(required=True)
    choix.add_argument("--team")
    choix.add_argument("--keys", nargs="+")
    mode = coach.add_mutually_exclusive_group()
    mode.add_argument("--show", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    report = sub.add_parser("report", help="rapport agrégé par équipe, lu dans les vues")
    report.add_argument("--name", required=True)
    report.add_argument("--json", action="store_true")
    grid = sub.add_parser("grid", help="valide le socle et la surcouche ; --show écrit les critères effectifs")
    grid.add_argument("--show", action="store_true")
    grid.add_argument("--json", action="store_true", help="avec --show : le contrat de la grille effective en JSON sur la sortie standard")
    for sous in (collect, review, analyse, coach, report, grid):
        sous.add_argument("--language", choices=LANGUAGES, default="fr")
    args = parser.parse_args(argv)
    if args.command == "grid" and args.json and not args.show:
        raise ValueError("arguments")
    return args


def charger_module(commande: str):
    """Module de la sous-commande, ou None tant qu'il n'est pas écrit."""
    if commande == "collect":
        import story_quality_collect
        return story_quality_collect
    if commande == "report":
        import story_quality_report
        return story_quality_report
    if commande == "review":
        import story_quality_review
        return story_quality_review
    if commande in ("analyse", "coach"):
        import story_quality_engine
        return story_quality_engine
    nom = MODULES[commande]
    try:
        return importlib.import_module(nom)
    except ModuleNotFoundError as erreur:
        if erreur.name == nom:
            return None
        raise


def read_overlay(core: dict, environ, identifiers):
    """Surcouche contrôlée, ou None sans fichier. Lève OverlayError."""
    path = overlay_module.overlay_path(environ)
    if path is None or not path.is_file():
        return None
    text = overlay_module.read_overlay_file(path)
    try:
        names = sensitive_names.load_names(environ.get(NAMES_VARIABLE) or None)
    except sensitive_names.SensitiveNamesUnavailable:
        raise overlay_module.OverlayError("names_unavailable") from None
    if identifiers is None:
        identifiers = identifiants_personnels.identifiants(TOOLS.parent)
    return overlay_module.check_overlay(text, data.core_codes(core), names, identifiers)


def show_text(grid: dict, language: str, t: Messages) -> list[str]:
    """Lignes de `grid --show` : la mise en forme du résultat de data.effective_grid, sans rien construire."""
    lines = []
    for kind in data.KINDS:
        lines.append(f"[{t('kind_' + kind)}]")
        for c in grid["kinds"][kind]["criteria"]:
            lines.append(t("criterion_line", code=c["code"], label=c["labels"][language], link=c["link"], source=c["source"]))
            lines.append(t("definition", text=c["definition"]))
            lines.append(t("question", text=c["engine_question"]))
            if c["not_applicable_condition"]:
                lines.append(t("not_applicable", text=c["not_applicable_condition"]))
        for key, message in (("sections", "structure_sections"), ("definition_of_ready", "structure_dor"),
                             ("vocabulary", "structure_vocabulary")):
            items = grid["kinds"][kind]["structure"][key]
            if items:
                lines.append(t(message, items="; ".join(items)))
    return lines


def main(argv=None, environ=None, identifiers=None) -> int:
    """Rend le code de sortie. `environ` et `identifiers` sont remplaçables pour les tests."""
    environ = os.environ if environ is None else environ
    t = Messages(CATALOGS, "fr")
    try:
        args = read_arguments(sys.argv[1:] if argv is None else argv)
    except ValueError:
        print(t("usage", what="arguments"), file=sys.stderr)
        return 2
    except SystemExit as stop:
        return stop.code or 0
    t = Messages(CATALOGS, args.language)
    if args.command in RESERVEES_A_L_UTILISATEUR and SESSION_VARIABLE in environ:
        print(t("session_refused"), file=sys.stderr)          # avant toute lecture : ni réglage, ni base, ni Jira
        return 3
    if args.command != "grid":
        module = charger_module(args.command)
        if module is None:
            print(t("not_available", command=args.command), file=sys.stderr)
            return 2
        return module.lancer(args, environ, t)
    try:
        core = data.load_core_grid(Path(environ.get(GRID_VARIABLE) or CORE_GRID_FILE))
    except data.GridError as erreur:
        print(t(erreur.args[0]), file=sys.stderr)
        return 3
    try:
        overlay = read_overlay(core, environ, identifiers)
    except overlay_module.OverlayError as erreur:
        print(t(erreur.key, **erreur.values), file=sys.stderr)
        return 3
    if args.show:
        grid = data.effective_grid(core, overlay, args.language)
        if args.json:
            if overlay is None:
                print(t("no_overlay"), file=sys.stderr)         # la sortie standard ne porte que le document JSON
            print(json.dumps(grid, ensure_ascii=False, indent=2))
            return 0
        versions = {"cv": grid["core_version"], "ov": grid["overlay_version"] if grid["overlay_version"] is not None else t("version_none")}
        print(t("show_header", **versions))
        if overlay is None:
            print(t("no_overlay"))
        for line in show_text(grid, args.language, t):
            print(line)
    elif overlay is None:
        print(t("no_overlay"))
    print(t("grid_valid", cv=core["version"], ov=overlay["version"] if overlay else t("version_none"),
            a=sum(len(v) for v in (overlay or {}).get("criteria", {}).values()), d=len(data.disabled_codes(overlay))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
