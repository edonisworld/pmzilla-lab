"""PMZilla Lab : sous-commande `report` de tools/story_quality.py (change story-quality-audit, design D8, D14, D15, D18).

    uv run tools/story_quality.py report --name <série> [--json] [--language fr|en]

Elle ne lit que les trois vues agrégées (quality_by_team, quality_coverage_by_team, quality_by_product), sous le rôle des vues de qualité,
par le lecteur de tools/flow_views.py : aucune table, aucun texte, aucune clé, aucune personne. La session peut donc la lancer.

Chaque chiffre, cellule masquée, défaut récurrent, masquage secondaire et ordre vient de UNE fonction de service, `report_data` de
tools/story_quality_data.py (D15). Ici on ne fait que la lire et la mettre en forme : aucun calcul de part, de masquage ni d'ordre.

  - sans `--json` : écrit Flux-Lab/rapports/qualite-stories-<série>-AAAA-MM-JJ.md (dossier remplaçable par PMZILLA_LAB_REPORTS pour les
    tests) et écrit la phrase « rapport de qualité des stories écrit » ;
  - avec `--json` : écrit sur la sortie standard le seul document JSON du contrat `story_quality_report` (M2 (a)), aucun fichier ; tout
    autre message va sur la sortie d'erreur.

Garde anti-comparaison : une section ne porte que les chiffres de son équipe ; les équipes sont dans l'ordre des noms ; ni note composite,
ni total par équipe, ni classement, ni ordre par résultat, ni nombre d'équipes.

Parties du Markdown (tâches 3.18 et 3.21, design D8, D18) :
  - `lire_surcouche` lit la surcouche contrôlée par le même lecteur que `grid` (tools/story_quality.py, `read_overlay`), d'où viennent la
    version de surcouche, les libellés des critères ajoutés et les codes désactivés ; jamais une raison, l'identifiant ni le résumé ;
  - `ENTETE_RAPPORT` : la ligne des versions de la grille (ou sa forme sans surcouche), puis les codes désactivés ;
  - `SOUS_SECTIONS_EQUIPE` : « Causes probables dans la chaîne » à la fin de la section de l'équipe, sa notice, puis une ligne par défaut
    récurrent de CETTE équipe (libellé, marque « règle de l'organisation », part non satisfaite et dénominateur, maillon) ;
  - `SECTIONS_FINALES` : « Chaîne du produit » après la dernière équipe, lue de `product_chain` (vue produit) : aucun nom d'équipe, aucune
    part par équipe, aucun nombre d'équipes.
Chaque fonction met en forme une partie du résultat de `report_data` dans l'ordre qu'il donne ; aucune ne calcule, ne trie ni ne masque.

Codes : 0 fait ; 1 vues illisibles (base injoignable, réglages illisibles, seuil de récurrence absent) ; 2 usage (nom de série absent ou
invalide) ; 3 socle absent ou invalide, surcouche invalide ou refusée (comme `grid`), avant toute lecture des vues ; 78 racine de contenu
introuvable (tools/lab_paths.py : PMZILLA_LAB_WORKSPACE sur un dossier absent, ou ni variable ni dépôt Git) quand le dossier des rapports
est cherché, sans --json ni PMZILLA_LAB_REPORTS, après la lecture des vues et avant l'écriture : aucun fichier écrit.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import story_quality_data as data  # noqa: E402
import story_quality_overlay as overlay_module  # noqa: E402

TOOLS = Path(__file__).resolve().parent
REPORTS_VARIABLE = "PMZILLA_LAB_REPORTS"
GRID_VARIABLE = "PMZILLA_LAB_STORY_GRID"            # le même nom que tools/story_quality.py (pas d'import croisé du répartiteur)
CORE_GRID_FILE = TOOLS / "story_quality_grid.json"
VIEWS = ("quality_by_team", "quality_coverage_by_team", "quality_by_product")
SERIES_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")      # un nom de fichier sûr : ni séparateur de chemin, ni espace

def lire_vue(vue: str) -> list[dict]:
    """Lignes d'une des trois vues sous le rôle des vues de qualité (remplacé par les tests). Chaque ligne : colonne -> valeur."""
    import flow_views
    if vue not in VIEWS:
        raise ValueError(vue)
    noms, lignes = flow_views.lire(vue)
    return [dict(zip(noms, ligne)) for ligne in lignes]


def reglages_rapport(t) -> tuple:
    """(seuil de récurrence ou None, seuil de masquage effectif). Remplacé par les tests. Lève yaml_strict.ErreurConfig."""
    import flux_config
    import flow_views
    import history_jira
    from flow_views_messages import CATALOGS as CATALOGUES_VUES
    from messages import Messages
    bloc = flux_config.story_quality(history_jira.reglages())
    configure = flow_views.seuil_configure(Messages(CATALOGUES_VUES, t.language))
    return (bloc or {}).get("recurrence_threshold"), flow_views.seuil_effectif(configure, None)


def identifiants():
    """Identifiants personnels à refuser dans la surcouche (None : les vrais, lus par le répartiteur ; remplacé par les tests)."""
    return None


def lire_surcouche(core: dict, environ):
    """Surcouche contrôlée, ou None sans fichier : le lecteur de `grid` (même contrôle, même refus). Lève OverlayError."""
    import story_quality                         # import tardif : le répartiteur importe ce module
    return story_quality.read_overlay(core, environ, identifiants())


def aujourdhui() -> dt.date:
    return dt.date.today()


def dossier_rapports(environ) -> Path:
    """PMZILLA_LAB_REPORTS, sinon Flux-Lab/rapports de la racine de contenu (tools/lab_paths.py), jamais de la racine du code."""
    if environ.get(REPORTS_VARIABLE):
        return Path(environ[REPORTS_VARIABLE])
    import lab_paths
    return lab_paths.resolve_or_exit(environ)["content_root"] / "Flux-Lab" / "rapports"


# --- mise en forme (aucun calcul : tout vient de report_data) --------------------------------------------------------------------------

def texte_cellule(cellule: dict, t) -> str:
    if cellule["state"] == "masked":                 # idée #417 : « masqué » / « masked » ; le seuil est donné une fois, dans la légende
        return t("cell_masked")
    return str(cellule["value"])


def texte_part(part: dict, t) -> str:
    if part["state"] == "masked":
        return t("cell_masked")
    return f"{part['numerator']['value']}/{part['denominator']['value']}"


def libelle(critere: dict, t) -> str:
    """Libellé d'un critère ou d'une ligne de cause, avec la marque « règle de l'organisation » pour un critère de la surcouche (D17)."""
    if critere["origin"] == data.OVERLAY_ORIGIN:
        return f"{critere['label']} ({t('organisation_rule')})"
    return critere["label"]


def texte_maillon(lien: str, t) -> str:
    return t("link_" + lien) if lien in data.LINKS else lien


def ligne_cause(ligne: dict, t) -> str:
    return t("cause_line", code=ligne["code"], label=libelle(ligne, t), text=texte_part(ligne["share_not_met"], t),
             link=texte_maillon(ligne["link"], t))


def lignes_causes(titre: str, bloc: dict, t) -> list[str]:
    """Titre, notice, puis les lignes dans l'ordre du service, ou la phrase « aucun défaut récurrent »."""
    lignes = [titre, "", bloc["notice"]["text"], ""]
    if not bloc["lines"]:
        return lignes + [t("no_recurrent_defect"), ""]
    return lignes + [ligne_cause(ligne, t) for ligne in bloc["lines"]] + [""]


def lignes_grille(resultat: dict, t) -> list[str]:
    """Ligne des versions de la grille (D8, D14), puis les codes désactivés par la surcouche ; jamais une raison ni un identifiant."""
    grille = resultat["grid"]
    if grille["overlay_version"] is None:
        lignes = [t("grid_line_no_overlay", cv=grille["core_version"]), ""]
    else:
        lignes = [t("grid_line", cv=grille["core_version"], ov=grille["overlay_version"]), ""]
    if grille["disabled_codes"]:
        lignes += [t("disabled_criteria", codes=", ".join(grille["disabled_codes"])), ""]
    return lignes


def sous_section_causes(equipe: dict, resultat: dict, t) -> list[str]:
    """Causes probables de CETTE équipe seulement (D18) : aucune autre équipe, aucun nombre d'équipes."""
    return lignes_causes(f"### {t('probable_causes_heading')}", equipe["probable_causes"], t)


def section_chaine_produit(resultat: dict, t) -> list[str]:
    """Chaîne du produit (D18, O8) : lue du seul `product_chain` (vue produit), sans nom ni part d'équipe."""
    return lignes_causes(f"## {t('product_chain_heading')}", resultat["product_chain"], t)


ENTETE_RAPPORT: list = [lignes_grille]                  # fonctions (résultat, t) -> lignes, sous la légende (tâche 3.18)
SOUS_SECTIONS_EQUIPE: list = [sous_section_causes]      # fonctions (équipe, résultat, t) -> lignes, fin de la section d'une équipe (3.18)
SECTIONS_FINALES: list = [section_chaine_produit]       # fonctions (résultat, t) -> lignes, après la dernière section d'équipe (3.21)


def lignes_equipe(equipe: dict, resultat: dict, t) -> list[str]:
    lignes = [f"## {equipe['team']}", ""]
    if equipe["single_po"]:
        lignes += [equipe["single_po_notice"], ""]
    for genre in data.KINDS:
        couverture = equipe["coverage"].get(genre)
        criteres = equipe["criteria"][genre]
        if couverture is None and not criteres:
            continue
        lignes += [f"### {t('kind_' + genre)}", ""]
        if couverture is not None:
            lignes.append(t("report_coverage", c=texte_cellule(couverture["collected"], t), a=texte_cellule(couverture["audited"], t),
                            x=texte_cellule(couverture["empty_acceptance_criteria"], t)))
        for critere in criteres:
            lignes.append(t("report_criterion", code=critere["code"], label=libelle(critere, t), text=texte_part(critere["share_met"], t)))
        lignes.append("")
    for fonction in SOUS_SECTIONS_EQUIPE:
        lignes += fonction(equipe, resultat, t)
    return lignes


def markdown(resultat: dict, nom: str, t, min_cell: int = data.MASK_FLOOR) -> str:
    """`min_cell` : seuil de masquage effectif, écrit dans la légende (une cellule masquée ne le porte plus, idée #417)."""
    lignes = [f"# {t('report_title', label=nom)}", "", resultat["notice"]["text"], "", t("report_legend", n=min_cell), ""]
    for fonction in ENTETE_RAPPORT:
        lignes += fonction(resultat, t)
    if not resultat["teams"]:
        lignes += [t("report_no_results"), ""]
    for equipe in resultat["teams"]:
        lignes += lignes_equipe(equipe, resultat, t)
    for fonction in SECTIONS_FINALES:
        lignes += fonction(resultat, t)
    while lignes and lignes[-1] == "":
        lignes.pop()
    return "\n".join(lignes) + "\n"


def lancer(args, environ, t) -> int:
    nom = str(args.name or "")
    if not SERIES_NAME.fullmatch(nom):
        print(t("usage", what="--name"), file=sys.stderr)
        return 2
    import yaml_strict
    try:
        recurrence, min_cell = reglages_rapport(t)
    except yaml_strict.ErreurConfig as erreur:
        print(t("settings_unreadable", detail=str(erreur)), file=sys.stderr)
        return 1
    if recurrence is None:             # pas de défaut (D16, D18) : le seuil est un réglage de l'utilisateur ; refus avant toute lecture
        print(t("settings_unreadable", detail="story_quality.recurrence_threshold"), file=sys.stderr)
        return 1
    try:
        core = data.load_core_grid(Path(environ.get(GRID_VARIABLE) or CORE_GRID_FILE))
    except data.GridError as erreur:
        print(t(erreur.args[0]), file=sys.stderr)
        return 3
    try:
        surcouche = lire_surcouche(core, environ)
    except overlay_module.OverlayError as erreur:          # comme `grid` : avant toute lecture des vues, aucun fichier
        print(t(erreur.key, **erreur.values), file=sys.stderr)
        return 3
    try:
        lignes = {vue: lire_vue(vue) for vue in VIEWS}
    except Exception as erreur:
        if type(erreur).__name__ == "ErreurBase":
            print(t("db_unreachable"), file=sys.stderr)
        else:
            print(t("db_error", kind=type(erreur).__name__), file=sys.stderr)
        return 1
    if surcouche is None:                                  # D17 : la phrase est toujours imprimée ; avec --json, sur la sortie d'erreur
        print(t("no_overlay"), file=sys.stderr if args.json else sys.stdout)
    resultat = data.report_data(lignes["quality_by_team"], lignes["quality_coverage_by_team"], lignes["quality_by_product"],
                                data.effective_grid(core, surcouche, args.language), threshold=recurrence,
                                disabled=data.disabled_codes(surcouche), min_cell=min_cell, language=args.language)
    if args.json:
        print(json.dumps(resultat, ensure_ascii=False, indent=2))
        return 0
    dossier = dossier_rapports(environ)
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / f"qualite-stories-{nom}-{aujourdhui().isoformat()}.md").write_text(markdown(resultat, nom, t, min_cell), encoding="utf-8")
    print(t("report_written"))
    return 0
