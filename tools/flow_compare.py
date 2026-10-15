# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pyyaml", "psycopg[binary]"]
# ///
"""
PMZilla Lab : comparaison des données Jira lues en base et dans les CSV (lot 6 de la base de données, docs/pmzilla/application.md, 5.3).

    uv run tools/flow_compare.py data <export.csv>... [--history [CACHE]]   les mêmes données, lues par les deux voies
    uv run tools/flow_compare.py reports <rapport-a.md> <rapport-b.md>      deux rapports écrits par les deux voies

Critère de fin du lot 6 : un même export donne des rapports identiques, lu en base ou en CSV.

`data` charge le même export par la voie CSV (celle de flux_jira.py et de dependencies_jira.py) et par la base (flow_store.py), et compare ce que
les deux scripts reçoivent : tickets de flux_jira.py, tickets et liens de dependencies_jira.py, et avec --history les transitions. Comme les
rapports sont des fonctions de ces données, des données identiques donnent des rapports identiques. La base doit d'abord avoir reçu le même export
(`flow_import.py`). Le cache d'historique par défaut est celui de flux_jira.py.

`reports` compare deux rapports déjà écrits (par exemple un `compute` en CSV et un `compute` en base, avec deux valeurs différentes de --name) : le
lignes alignées comme diff, hors le titre, la ligne de fusion des exports et les noms de fichiers de la ligne « Export » ; les
écarts restants sont comptés par numéro de section (0 = avant le premier titre), jamais avec leur contenu.

Ce que l'outil affiche : des COMPTES seulement. Aucune clé de ticket, aucune valeur de champ, aucun nom d'équipe ; les écarts par projet portent la
clé du projet (le préfixe d'une clé), pas celle d'un ticket. Code de sortie 0 si tout est identique, 1 sinon, 2 en cas d'erreur.
À lancer par l'utilisateur seul sur les vraies données (règles deny de .claude/settings.json).

Exemple :
    uv run tools/flow_compare.py data export.csv
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from messages import Messages, add_language_option  # noqa: E402
from flow_compare_messages import CATALOGS  # noqa: E402

CHAMPS_FLUX = ("projet", "categorie", "type", "etat", "cree", "resolu", "resolu_a", "debut", "equipe", "equipes", "motif")
CHAMPS_DEPENDANCES = ("type", "etat", "categorie", "cree", "resolu", "debut", "motif", "equipe", "parent")


class Ecarts:
    """Les écarts d'une comparaison, en comptes."""

    def __init__(self) -> None:
        self.lignes: list[str] = []
        self.total = 0

    def noter(self, texte: str, n: int = 1) -> None:
        self.lignes.append(texte)
        self.total += n


def _projet(cle: str) -> str:
    return cle.rsplit("-", 1)[0].upper() if "-" in cle else "?"


def comparer_dicts(a: dict, b: dict, champs: tuple[str, ...], t: Messages, titre: str, ecarts: Ecarts) -> None:
    """a et b : {clé: {champ: valeur}}. Écrit des comptes : tickets d'un seul côté, champs qui diffèrent, écarts par projet."""
    seulement_a, seulement_b = a.keys() - b.keys(), b.keys() - a.keys()
    communes = a.keys() & b.keys()
    par_champ: Counter = Counter()
    par_projet: Counter = Counter()
    for cle in communes:
        diff = [c for c in champs if a[cle].get(c) != b[cle].get(c)]
        for c in diff:
            par_champ[c] += 1
        if diff:
            par_projet[_projet(cle)] += 1
    for cle in seulement_a | seulement_b:
        par_projet[_projet(cle)] += 1
    ecarts.lignes.append(t("section", title=titre, csv=len(a), db=len(b), common=len(communes)))
    if seulement_a:
        ecarts.noter(t("only_csv", n=len(seulement_a)), len(seulement_a))
    if seulement_b:
        ecarts.noter(t("only_db", n=len(seulement_b)), len(seulement_b))
    for champ in champs:
        if par_champ[champ]:
            ecarts.noter(t("field_differs", field=champ, n=par_champ[champ]), par_champ[champ])
    for projet, n in sorted(par_projet.items()):
        ecarts.lignes.append(t("by_project", project=projet, n=n))


def _instant(valeur):
    try:
        return dt.datetime.fromisoformat(str(valeur)).astimezone(dt.timezone.utc)
    except ValueError:
        return str(valeur)


def _normaliser_historique(transitions: list) -> list:
    return sorted(((_instant(d), a, b) for d, a, b in transitions), key=lambda x: (str(x[0]), str(x[1]), str(x[2])))


def comparer_historiques(csv: dict, base: dict, cles: set[str], t: Messages, ecarts: Ecarts) -> None:
    """Seules les clés présentes dans l'export comptent (la base n'importe pas les transitions d'une clé qu'elle ne connaît pas)."""
    a = {c: _normaliser_historique(csv.get(c, [])) for c in cles}
    b = {c: _normaliser_historique(base.get(c, [])) for c in cles}
    ecarts.lignes.append(t("history_section", csv=sum(len(v) for v in a.values()), db=sum(len(v) for v in b.values())))
    # couverture : un ticket « avec historique » est un ticket qui a une entrée (même sans transition) : flux_jira.py compte la
    # couverture et repère les dormants d'après les entrées, pas d'après les transitions
    entrees_csv, entrees_db = {c for c in cles if c in csv}, {c for c in cles if c in base}
    ecarts.lignes.append(t("history_coverage", csv=len(entrees_csv), db=len(entrees_db), total=len(cles)))
    if entrees_csv - entrees_db:
        ecarts.noter(t("history_entries_only_csv", n=len(entrees_csv - entrees_db)), len(entrees_csv - entrees_db))
    if entrees_db - entrees_csv:
        ecarts.noter(t("history_entries_only_db", n=len(entrees_db - entrees_csv)), len(entrees_db - entrees_csv))
    differentes = [c for c in cles if a[c] != b[c]]
    if differentes:
        ecarts.noter(t("history_differs", n=len(differentes)), len(differentes))
        manquantes = sum(1 for c in differentes if len(a[c]) != len(b[c]))
        if manquantes:
            ecarts.lignes.append(t("history_count_differs", n=manquantes))


def comparer_donnees(paths: list[str], historique: Path | None, t: Messages, settings_flux: dict | None = None,
                     settings_dep: dict | None = None) -> Ecarts:
    """Charge `paths` par les deux voies et compare. Les réglages sont ceux de flux.yaml (injectables pour les tests)."""
    import flux_jira
    import dependencies_jira
    import flow_store
    settings_flux = settings_flux or flux_jira.config()
    settings_dep = settings_dep or dependencies_jira.config()
    ecarts = Ecarts()

    tickets_csv, _, _, _ = flux_jira.read_exports(paths, settings_flux)
    tickets_db, _, _, _ = flow_store.lire_tickets_flux(settings_flux)
    comparer_dicts({x["cle"]: x for x in tickets_csv}, {x["cle"]: x for x in tickets_db}, CHAMPS_FLUX, t, t("title_flux"), ecarts)

    dep_csv = dependencies_jira.read_exports(paths, settings_dep)
    dep_db = flow_store.lire_dependances(settings_dep)
    comparer_dicts(dep_csv["tickets"], dep_db["tickets"], CHAMPS_DEPENDANCES, t, t("title_dependencies"), ecarts)
    liens_csv, liens_db = set(map(tuple, dep_csv["liens"])), set(map(tuple, dep_db["liens"]))
    ecarts.lignes.append(t("links_section", csv=len(liens_csv), db=len(liens_db)))
    if liens_csv - liens_db:
        ecarts.noter(t("links_only_csv", n=len(liens_csv - liens_db)), len(liens_csv - liens_db))
    if liens_db - liens_csv:
        ecarts.noter(t("links_only_db", n=len(liens_db - liens_csv)), len(liens_db - liens_csv))

    if historique is not None:
        cache = flux_jira.charger_historique(historique)
        base = flow_store.lire_historique(settings_flux)
        comparer_historiques(cache, base, {x["cle"].upper() for x in tickets_csv if x["cle"]}, t, ecarts)
    return ecarts


FUSION = re.compile(r"^(Fusion de \d+ exports|Merge of \d+ exports)\b")      # n'existe que du côté CSV avec plusieurs fichiers
NOM_EXPORT = re.compile(r"^(Export ?: ).*? · ")                              # le nom du fichier (CSV) ou « base »


def normaliser_rapport(texte: str) -> list[str]:
    """Lignes d'un rapport sans ce qui dépend de la source : le titre (première ligne : il porte le nom), la ligne de fusion
    des exports, les noms de fichiers de la ligne « Export » ; les suites de lignes vides sont réduites à une."""
    lignes: list[str] = []
    for ligne in texte.splitlines()[1:]:
        if FUSION.match(ligne):
            continue
        ligne = NOM_EXPORT.sub(r"\1· ", ligne, count=1)
        if not ligne.strip() and (not lignes or not lignes[-1].strip()):
            continue
        lignes.append(ligne)
    while lignes and not lignes[-1].strip():
        lignes.pop()
    return lignes


def comparer_rapports(a: Path, b: Path, t: Messages) -> Ecarts:
    """Aligne les lignes comme diff (une ligne en plus ou en moins ne décale pas les suivantes) ; les écarts restants sont
    comptés par numéro de section (0 = avant le premier titre « # »), jamais avec leur contenu."""
    ecarts = Ecarts()
    lignes_a = normaliser_rapport(a.read_text(encoding="utf-8"))
    lignes_b = normaliser_rapport(b.read_text(encoding="utf-8"))
    ecarts.lignes.append(t("reports_section", a=len(lignes_a), b=len(lignes_b)))
    par_section: Counter = Counter()
    for etiquette, i1, i2, j1, j2 in difflib.SequenceMatcher(None, lignes_a, lignes_b, autojunk=False).get_opcodes():
        if etiquette != "equal":
            section = sum(1 for ligne in lignes_a[:i1] if ligne.startswith("#"))
            par_section[section] += max(i2 - i1, j2 - j1)
    for section in sorted(par_section):
        ecarts.noter(t("reports_section_differs", section=section, n=par_section[section]), par_section[section])
    return ecarts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare les données Jira lues en base et dans les CSV (comptes seulement).")
    add_language_option(parser)
    sous = parser.add_subparsers(dest="commande", required=True)
    d = sous.add_parser("data", help="les mêmes données lues par les deux voies")
    d.add_argument("export", nargs="+", help="un ou plusieurs exports CSV déjà importés en base")
    d.add_argument("--history", nargs="?", const="", default=None, metavar="CACHE",
                   help="compare aussi les transitions (cache de history_jira.py ; défaut : celui de flux_jira.py)")
    r = sous.add_parser("reports", help="deux rapports écrits par les deux voies")
    r.add_argument("rapport_a")
    r.add_argument("rapport_b")
    args = parser.parse_args(argv)
    t = Messages(CATALOGS, args.language)
    try:
        if args.commande == "reports":
            ecarts = comparer_rapports(Path(args.rapport_a).expanduser(), Path(args.rapport_b).expanduser(), t)
        else:
            historique = None
            if args.history is not None:
                import flux_jira
                historique = Path(args.history).expanduser() if args.history else flux_jira.HISTORIQUE_DEFAUT
            ecarts = comparer_donnees(args.export, historique, t)
    except SystemExit:
        raise
    except FileNotFoundError:
        print(t("error", message=t("file_missing")), file=sys.stderr)
        return 2
    except Exception as erreur:          # le message d'une exception peut citer une clé ou une valeur : seul le type est affiché
        print(t("error", message=type(erreur).__name__), file=sys.stderr)
        try:
            import db
            if isinstance(erreur, db.ErreurBase):
                print(t("error", message=str(erreur)), file=sys.stderr)
        except ImportError:
            pass
        return 2
    print("\n".join(ecarts.lignes))
    print(t("identical") if ecarts.total == 0 else t("differences", n=ecarts.total))
    return 0 if ecarts.total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
