# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml", "psycopg[binary]"]
# ///
"""
PMZilla Lab : lecture des vues agrégées du schéma flow (lot 6 de la base de données, docs/pmzilla/application.md, 5.3).

    uv run tools/flow_views.py list                       les vues disponibles
    uv run tools/flow_views.py show <vue> [--min-cell N]  le contenu d'une vue

C'est la seule porte de Claude Code vers les données Jira de la base : le script se connecte avec le rôle pmzilla_flow_views, qui n'a
de droit que sur les quatre vues de flow et les deux vues des noms d'équipe v_teams et v_team_jira_ids (aucun sur les tables qui portent les clés de tickets). Les trois vues de qualité des stories
(quality_by_team, quality_coverage_by_team, quality_by_product, change story-quality-audit) se lisent de la même façon sous leur propre rôle,
pmzilla_quality_views (service Trousseau pmzilla-lab-db-pmzilla_quality_views), qui ne lit aucune table du schéma quality. Une cellule de moins de 5 tickets est déjà
masquée dans la vue même. Ici, le seuil peut être relevé (réglage flow_views_min_cell de Flux-Lab/flux.yaml, ou --min-cell), jamais abaissé
sous 5 : une cellule sous le seuil s'affiche « masqué » (« masked » en anglais, idée #417) ; un seuil relevé au-dessus de 5 est
rappelé sur la sortie d'erreur de show, le titre de list donne le seuil configuré. Le mot de passe du rôle est dans le Trousseau (service pmzilla-lab-db-pmzilla_flow_views) :
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
ROLE_QUALITE = "pmzilla_quality_views"          # change story-quality-audit : les trois vues du schéma quality, sous leur propre rôle
PLANCHER = 5
VUES_FLOW = ("v_team_status", "v_team_weekly_resolved", "v_team_open_age", "v_team_dependencies")
VUES_QUALITE = ("quality_by_team", "quality_coverage_by_team", "quality_by_product")
VUES_EQUIPES = ("v_teams", "v_team_jira_ids")  # change team-names-readable (D2, D3) : noms d'équipe, type et identifiants Jira, migration 0014
VUES = VUES_FLOW + VUES_EQUIPES + VUES_QUALITE  # liste fermée : neuf vues, aucune table
# colonnes de comptage : seules soumises au masquage (le drapeau single_po d'une équipe n'en est pas une)
COLONNES_COMPTE = ("tickets", "links", "collected", "audited", "empty_acceptance_criteria", "met", "not_met", "not_applicable",
                   "undetermined")
# Ordre des lignes des trois vues de qualité (change story-quality-audit, D15, M3 (a)) : équipe, genre d'élément, code du critère ; la vue
# du produit n'a pas d'équipe, la couverture n'a pas de code. Jamais l'ordre d'un compte ; Mothra garde cet ordre.
CLES_DE_TRI_QUALITE = ("team", "item_kind", "criterion_code")


def fichier_config() -> Path:
    """Flux-Lab/flux.yaml de la racine de contenu (tools/lab_paths.py), jamais de la racine du code : depuis un worktree, le Flux-Lab du
    code est absent et le seuil retomberait au plancher. Racine introuvable : message et code 78 du module partagé, jamais un repli."""
    import lab_paths
    return lab_paths.resolve_or_exit()["content_root"] / "Flux-Lab" / "flux.yaml"


def seuil_configure(t: Messages, fichier: Path | None = None) -> int:
    """Seuil de flux.yaml (flow_views_min_cell), jamais en dessous de PLANCHER. Fichier absent : PLANCHER. Sans fichier donné :
    fichier_config()."""
    import yaml
    fichier = fichier_config() if fichier is None else fichier
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


def cellule(colonne: str, valeur, seuil: int) -> dict:
    """Cellule structurée (D7). Colonne de comptage : {"value": n} à partir du seuil, sinon (nul de la vue compris) une cellule masquée
    avec sa raison et son seuil. Toute autre colonne (identifiant Jira, type d'équipe, nom) : {"value": v}, jamais masquée."""
    if colonne in COLONNES_COMPTE and (valeur is None or valeur < seuil):
        return {"value": None, "masked": "under_threshold", "threshold": seuil}
    return {"value": valeur}


def masquer(valeur, seuil: int, t: Messages) -> str:
    cell = cellule("tickets", valeur, seuil)
    if "masked" in cell:
        return t("masked")
    return str(cell["value"])


def lire(vue: str, role: str | None = None, **connexion) -> tuple[list[str], list[tuple]]:
    if vue not in VUES:                                        # liste fermée : jamais de nom venu de l'extérieur dans le SQL
        raise ValueError(vue)
    schema, role_de_la_vue = ("quality", ROLE_QUALITE) if vue in VUES_QUALITE else ("flow", ROLE)
    conn = db.connect(role=role or role_de_la_vue, **connexion)
    try:
        curseur = conn.execute(f"SELECT * FROM {schema}.{vue}")      # noqa: S608  (schéma et nom vérifiés ci-dessus)
        noms = [c.name for c in curseur.description]
        lignes = curseur.fetchall()
    finally:
        conn.close()
    return noms, lignes


def rendre(noms: list[str], lignes: list[tuple], seuil: int, t: Messages) -> str:
    def formater(nom: str, valeur) -> str:
        cell = cellule(nom, valeur, seuil)
        if "masked" in cell:
            return t("masked")
        return "" if cell["value"] is None else str(cell["value"])

    cles = [i for colonne in CLES_DE_TRI_QUALITE for i, nom in enumerate(noms) if nom == colonne] if "item_kind" in noms else []

    def cle_de_tri(ligne):
        texte = tuple("" if x is None else str(x) for x in ligne)
        return tuple(texte[i] for i in cles) + texte           # vues de qualité : équipe, genre, code d'abord, jamais un compte (M3 (a))

    corps = [[formater(noms[i], c) for i, c in enumerate(ligne)] for ligne in sorted(lignes, key=cle_de_tri)]
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
            print(t("views_title", min_cell=configure, masked=t("masked")))
            for vue in VUES:
                print(f"  {vue:<28}{t('desc_' + vue)}")
            return 0
        if args.vue not in VUES:
            print(t("unknown_view", name=args.vue, views=", ".join(VUES)), file=sys.stderr)
            return 1
        seuil = seuil_effectif(configure, args.min_cell)
        if args.min_cell is not None and args.min_cell < PLANCHER:
            print(t("min_cell_floor", min_cell=seuil, floor=PLANCHER), file=sys.stderr)
        if seuil > PLANCHER:                                   # la cellule ne dit plus son seuil (idée #417) : un seuil relevé est rappelé
            print(t("min_cell_raised", min_cell=seuil, masked=t("masked")), file=sys.stderr)
        noms, lignes = lire(args.vue)
        print(rendre(noms, lignes, seuil, t))
        return 0
    except db.ErreurBase as erreur:
        print(t("error", message=erreur), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
