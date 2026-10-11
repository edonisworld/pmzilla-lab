# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml", "psycopg[binary]"]
# ///
"""
PMZilla Lab : lecture des vues agrégées du schéma flow (lot 6 de la base de données, docs/pmzilla/application.md, 5.3).

    uv run tools/flow_views.py list                       les vues disponibles
    uv run tools/flow_views.py show <vue> [--min-cell N]  le contenu d'une vue

C'est la seule porte de Claude Code vers les données Jira de la base : le script se connecte avec le rôle pmzilla_flow_views, qui n'a
de droit que sur ces quatre vues (aucun sur les tables qui portent les clés de tickets). Une cellule de moins de 5 tickets est déjà
masquée dans la vue même. Ici, le seuil peut être relevé (réglage flow_views_min_cell de Flux-Lab/flux.yaml, ou --min-cell), jamais abaissé
sous 5 : une cellule sous le seuil s'affiche « <N ». Le mot de passe du rôle est dans le Trousseau (service pmzilla-lab-db-pmzilla_flow_views) :
`uv run tools/db.py role-password pmzilla_flow_views` le pose.

Le nom d'une vue est comparé à une liste fermée avant toute requête. Le script n'écrit rien.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db  # noqa: E402
from messages import Messages, add_language_option  # noqa: E402
from flow_views_messages import CATALOGS  # noqa: E402

ROLE = "pmzilla_flow_views"
PLANCHER = 5
VUES = ("v_team_status", "v_team_weekly_resolved", "v_team_open_age", "v_team_dependencies")
COLONNES_COMPTE = ("tickets", "links")        # colonnes de comptage : seules soumises au masquage
WORKSPACE = Path(__file__).resolve().parents[1]
CONFIG_FILE = WORKSPACE / "Flux-Lab" / "flux.yaml"


def seuil_configure(t: Messages, fichier: Path = CONFIG_FILE) -> int:
    """Seuil de flux.yaml (flow_views_min_cell), jamais en dessous de PLANCHER. Fichier absent : PLANCHER."""
    import yaml
    try:
        if not fichier.exists():
            return PLANCHER
        donnees = yaml.safe_load(fichier.read_text(encoding="utf-8")) or {}
        valeur = int(donnees.get("flow_views_min_cell", PLANCHER))
    except (OSError, ValueError, TypeError, yaml.YAMLError, AttributeError):
        print(t("settings_unreadable", floor=PLANCHER), file=sys.stderr)
        return PLANCHER
    return max(PLANCHER, valeur)


def seuil_effectif(configure: int, option: int | None) -> int:
    """Le seuil relevé par l'option l'emporte ; il ne descend jamais sous le réglage ni sous PLANCHER."""
    return max(PLANCHER, configure, option or 0)


def masquer(valeur, seuil: int, t: Messages) -> str:
    if valeur is None or valeur < seuil:
        return t("masked", min_cell=seuil)
    return str(valeur)


def lire(vue: str, role: str = ROLE, **connexion) -> tuple[list[str], list[tuple]]:
    if vue not in VUES:                                        # liste fermée : jamais de nom venu de l'extérieur dans le SQL
        raise ValueError(vue)
    conn = db.connect(role=role, **connexion)
    try:
        curseur = conn.execute(f"SELECT * FROM flow.{vue}")      # noqa: S608  (nom vérifié ci-dessus)
        noms = [c.name for c in curseur.description]
        lignes = curseur.fetchall()
    finally:
        conn.close()
    return noms, lignes


def rendre(noms: list[str], lignes: list[tuple], seuil: int, t: Messages) -> str:
    comptes = {i for i, n in enumerate(noms) if n in COLONNES_COMPTE}
    corps = [[masquer(c, seuil, t) if i in comptes else ("" if c is None else str(c)) for i, c in enumerate(ligne)]
             for ligne in sorted(lignes, key=lambda l: tuple("" if x is None else str(x) for x in l))]
    if not corps:
        return t("no_rows")
    largeurs = [max(len(n), *(len(l[i]) for l in corps)) for i, n in enumerate(noms)]
    sortie = ["  ".join(n.ljust(w) for n, w in zip(noms, largeurs)).rstrip(),
              "  ".join("-" * w for w in largeurs)]
    sortie += ["  ".join(c.ljust(w) for c, w in zip(l, largeurs)).rstrip() for l in corps]
    return "\n".join(sortie)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Vues agrégées du schéma flow (lecture seule).")
    add_language_option(parser)
    sous = parser.add_subparsers(dest="commande", required=True)
    sous.add_parser("list", help="les vues disponibles")
    montrer = sous.add_parser("show", help="le contenu d'une vue")
    montrer.add_argument("vue")
    montrer.add_argument("--min-cell", type=int, help=f"seuil de masquage (relève le réglage, jamais sous {PLANCHER})")
    args = parser.parse_args(argv)
    t = Messages(CATALOGS, args.language)
    configure = seuil_configure(t)
    try:
        if args.commande == "list":
            print(t("views_title", min_cell=configure, masked=t("masked", min_cell=configure)))
            for vue in VUES:
                print(f"  {vue:<28}{t('desc_' + vue)}")
            return 0
        if args.vue not in VUES:
            print(t("unknown_view", name=args.vue, views=", ".join(VUES)), file=sys.stderr)
            return 1
        seuil = seuil_effectif(configure, args.min_cell)
        if args.min_cell is not None and args.min_cell < PLANCHER:
            print(t("min_cell_floor", min_cell=seuil, floor=PLANCHER), file=sys.stderr)
        noms, lignes = lire(args.vue)
        print(rendre(noms, lignes, seuil, t))
        return 0
    except db.ErreurBase as erreur:
        print(t("error", message=erreur), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
