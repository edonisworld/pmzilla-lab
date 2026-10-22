# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml", "psycopg[binary]"]
# ///
"""
PMZilla Lab : import des tickets Jira dans le schéma flow de la base, à partir de la couche brute datée (change database-only, D4).

    uv run tools/flow_import.py [--mark-absent] [--max-absent-percent N] [--dry-run] [--language fr|en]

L'import ne lit aucun fichier : il dérive les tables courantes (tickets, équipes par ticket, liens, marques « sorti de l'export ») de
la couche brute que l'export écrit (flow.raw_runs, flow.raw_run_sightings, flow.raw_issue_snapshots), en UNE transaction annulée en cas
d'erreur, sous le rôle d'import pmzilla_flow avec son propre mot de passe (Trousseau pmzilla-lab-db-pmzilla_flow ; à poser avec
`db.py role-password pmzilla_flow`). Il n'y a pas d'état « appliqué » : l'import compare le DERNIER instantané de chaque ticket aux
lignes vivantes et les visites du DERNIER passage d'export aux marques, donc relancé sans nouveau passage il ne change rien et dit
« couche brute : aucun nouveau passage à appliquer » (code 0). Les transitions et les périodes d'étiquettes et de versions ne sont plus
écrites ici : la collecte de l'historique (history_jira.py collect) les écrit.

Ce que l'outil écrit, dans le schéma flow, sous le rôle pmzilla_flow :
  - flow.teams : une équipe par nom d'équipe des instantanés, créée à la volée (aucune n'est supprimée) ;
  - flow.issues : les tickets dont un champ diffère du dernier instantané ; flow.issue_teams et flow.links : la différence seulement
    (un instantané dont les liens ne sont pas suivis ne touche pas les liens du ticket) ;
  - flow.issues.out_of_export_at : un ticket vu par le dernier passage perd sa marque, avec ou sans l'option ; avec --mark-absent, un
    ticket stocké non marqué et absent du dernier passage reçoit l'instant de l'import, sans jamais déplacer une marque existante. Le
    dernier passage doit avoir lu toutes les requêtes nommées des réglages (jeu complet) et au moins un ticket, et la part des tickets à
    marquer ne doit pas dépasser --max-absent-percent (défaut 20) ; sinon code 1, rien n'est écrit.
  - flow.issues.history_not_found et history_gone_at : un ticket marqué disparu par la collecte de l'historique et revu par le dernier
    passage d'export perd cette marque (compteur à 0, instant effacé), avec ou sans l'option ; le compteur d'un ticket non marqué
    disparu n'est pas touché. La phrase « tickets marqués disparus, revus par l'export : N » est écrite à chaque passage, 0 compris.
Les instantanés des tickets résolus depuis plus que la durée de conservation (réglage retention) sont ignorés et comptés.

Ce que l'outil n'affiche jamais : aucune clé de ticket, aucun nom d'équipe, aucune valeur de champ, y compris dans les erreurs. La
sortie ne compte que des effectifs. Une erreur de la base est réduite au nom de son type.

--dry-run calcule les mêmes comptes dans la base et annule la transaction : rien n'est écrit.

Usages refusés (code 2, avant toute connexion) : un fichier d'export (« les fichiers d'export ne sont plus lus : l'import part de la
couche brute ») ; --history (« --history est retirée : la collecte de l'historique écrit les transitions »).

    uv run tools/flow_import.py --rebuild [--apply] [--seed] [--language fr|en]
Reconstruction depuis la couche brute datée (change jira-data-architecture, D5) : reconstruit les lignes de tickets, les équipes par
ticket et les liens depuis le DERNIER instantané de chaque ticket, avec les noms d'équipe stockés (ni référentiel, ni catalogue), et les
compare aux tables vivantes. Sans --apply, c'est un essai à blanc : il affiche le nombre de tickets comparés et de tickets qui
changeraient, un compte par champ différent (jamais une valeur) et « reconstruction à blanc : rien n'est écrit ». Avec --apply, il écrit
les différences en une transaction (équipes manquantes créées, aucune supprimée). Il ne touche ni les instants de sortie de l'export, ni
les transitions, ni l'indicateur d'historique, ni les périodes. Refus (code 1, avant toute écriture) : couche brute vide ; tickets
stockés sans instantané (leur nombre est affiché). --seed écrit d'abord, une fois, un instantané construit depuis la ligne vivante de
chaque ticket stocké qui n'en a aucun (passage de genre seed, noms d'équipe sans identifiant), puis reconstruit. Usages refusés (code 2,
avant toute connexion) : --apply ou --seed sans --rebuild ; --mark-absent ou --dry-run avec --rebuild (sans --apply, c'est déjà un
essai à blanc).

Seul l'utilisateur lance cet outil sur les vraies données : Claude Code ne le lance jamais (règles deny de .claude/settings.json). Les
tests passent par une base jetable et des données inventées.

Exemple :
    uv run tools/flow_import.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db                                               # noqa: E402
import flow_raw                                         # noqa: E402
import flux_config as cfg                               # noqa: E402
import lab_paths                                        # noqa: E402
from flow_import_messages import CATALOGS               # noqa: E402
from messages import Messages, add_language_option      # noqa: E402
from yaml_strict import ErreurConfig, charger           # noqa: E402

ROLE = "pmzilla_flow"
SEUIL_ABSENTS_DEFAUT = 20          # part maximale (en %) de tickets stockés que --mark-absent peut marquer d'un coup
CONFIG_FILE = lab_paths.resolve_or_exit()["content_root"] / "Flux-Lab" / "flux.yaml"


def lire_reglages() -> dict:
    """Réglages de flux.yaml sous les noms internes (les noms anglais seuls sont acceptés : flux_config.py)."""
    brut = (charger(CONFIG_FILE.read_text(encoding="utf-8"), "flux.yaml") or {}) if CONFIG_FILE.exists() else {}
    return cfg.to_internal(brut, "flux.yaml")


def _echec(message: str, code: int = 1) -> int:
    print(message, file=sys.stderr)
    return code


def afficher(r: dict, dry_run: bool, t: Messages) -> None:
    if dry_run:
        print(t("dry_run_notice"))
    if r["rien"]:
        print(t("no_new_run"))
        print(t("gone_sighted", n=r["disparus_revus"]))
        return
    print(t("tickets_summary", read=r["compares"], inserted=r["inseres"], updated=r["modifies"], unchanged=r["inchanges"]))
    print(t("teams_links_summary", teams=r["equipes"], links_added=r["liens_ajoutes"], links_removed=r["liens_retires"]))
    print(t("past_retention", skipped=r["hors_conservation"]))
    print(t("out_of_export", marked=r["marques"], back=r["revenus"]))
    print(t("gone_sighted", n=r["disparus_revus"]))


def noms_de_champ(t: Messages) -> dict[str, str]:
    """Nom neutre de chaque champ compté par la reconstruction (flow_raw.CHAMPS), dans la langue de `t`. Chaque clé du catalogue est
    écrite en littéral : le test des clés employées les voit toutes."""
    return {"ticket": t("rebuild_field_ticket"), "status": t("rebuild_field_status"),
            "status category": t("rebuild_field_status_category"), "type": t("rebuild_field_type"),
            "resolution": t("rebuild_field_resolution"), "dates": t("rebuild_field_dates"),
            "story points": t("rebuild_field_story_points"), "parent": t("rebuild_field_parent"),
            "team": t("rebuild_field_team"), "teams": t("rebuild_field_teams"), "links": t("rebuild_field_links")}


def reconstruire(args: argparse.Namespace, t: Messages) -> int:
    """`--rebuild` : reconstruit tickets, équipes par ticket et liens depuis le dernier instantané de chaque ticket de la couche
    brute et les compare aux tables vivantes (essai à blanc par défaut, `--apply` écrit en une transaction). `--seed` écrit d'abord,
    en une transaction, un instantané d'amorçage pour chaque ticket stocké qui n'en a aucun. Ne lit ni les réglages, ni le référentiel
    d'organisation, ni l'équipe d'un fichier. Rend le code de sortie (0 fait, 1 refus ou erreur). Des effectifs seulement."""
    conn = None
    try:
        conn = db.connect(role=ROLE)
        if args.seed:
            print(t("seed_done", n=flow_raw.amorcer(conn)))
        resultat = flow_raw.reconstruire(conn, appliquer=args.apply)
    except flow_raw.Refus as refus:
        return _echec(t("rebuild_raw_empty") if refus.code == "raw_empty" else t("rebuild_no_snapshot", **refus.valeurs))
    except db.ErreurBase as erreur:
        return _echec(str(erreur))
    except Exception as erreur:       # aucun détail : un message de la base pourrait citer une clé ou une valeur
        return _echec(t("unexpected_error", name=type(erreur).__name__))
    finally:
        if conn is not None:
            conn.close()
    print(t("rebuild_compared", n=resultat["compares"], d=resultat["changeraient"]))
    for champ, k in resultat["champs"].items():
        print(t("rebuild_field", field=noms_de_champ(t)[champ], k=k))
    print(t("rebuild_done", d=resultat["modifies"]) if args.apply else t("rebuild_dry_end"))
    return 0


def deriver(args: argparse.Namespace, t: Messages) -> int:
    """Import normal : dérive les tables courantes de la couche brute (design D4), en une transaction ; `--dry-run` annule."""
    try:
        retention = cfg.retention_days(lire_reglages())
    except ErreurConfig as erreur:       # le message nomme le réglage, jamais sa valeur
        return _echec(str(erreur))
    conn = None
    try:
        conn = db.connect(role=ROLE)
        resultat = flow_raw.deriver(conn, appliquer=not args.dry_run, marquer_absents=args.mark_absent,
                                    seuil_pourcent=args.max_absent_percent, retention_jours=retention)
    except flow_raw.RefusDerivation as refus:      # refus avant toute écriture
        if refus.suite:
            print(t(refus.code), file=sys.stderr)
            return _echec(t(refus.suite))
        return _echec(t(refus.code, percent=f"{args.max_absent_percent:g}"))
    except db.ErreurBase as erreur:
        return _echec(str(erreur))
    except Exception as erreur:       # aucun détail : un message de la base pourrait citer une clé ou une valeur
        return _echec(t("unexpected_error", name=type(erreur).__name__))
    finally:
        if conn is not None:
            conn.close()
    afficher(resultat, args.dry_run, t)
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Import des tickets Jira dans le schéma flow de la base, depuis la couche brute")
    parser.add_argument("export", nargs="*", help=argparse.SUPPRESS)          # un fichier d'export est refusé (code 2)
    parser.add_argument("--rebuild", action="store_true",
                        help="reconstruit tickets, équipes par ticket et liens depuis la couche brute (essai à blanc par défaut)")
    parser.add_argument("--apply", action="store_true", help="avec --rebuild : écrit la reconstruction (une transaction)")
    parser.add_argument("--seed", action="store_true",
                        help="avec --rebuild : écrit d'abord un instantané d'amorçage pour chaque ticket stocké qui n'en a aucun")
    parser.add_argument("--history", nargs="?", const="", default=None, help=argparse.SUPPRESS)       # retirée : refusée (code 2)
    parser.add_argument("--mark-absent", action="store_true",
                        help="marque « sorti de l'export » les tickets stockés absents du dernier passage d'export ; exige que ce "
                             "passage ait lu toutes les requêtes nommées de flux.yaml")
    parser.add_argument("--max-absent-percent", type=float, default=SEUIL_ABSENTS_DEFAUT, metavar="N",
                        help=f"avec --mark-absent : refuse l'import si plus de N %% des tickets stockés seraient marqués "
                             f"(défaut {SEUIL_ABSENTS_DEFAUT}) ; refuse aussi un dernier passage sans aucun ticket")
    parser.add_argument("--dry-run", action="store_true", help="calcule les comptes dans la base, annule, n'écrit rien")
    add_language_option(parser)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if not 0 <= args.max_absent_percent <= 100:
        parser.error("--max-absent-percent doit être compris entre 0 et 100")
    t = Messages(CATALOGS, args.language)
    # usages refusés avant toute lecture, écriture ou connexion (code 2)
    if args.export:
        sys.exit(_echec(t("export_files_retired"), 2))
    if args.history is not None:
        sys.exit(_echec(t("history_retired"), 2))
    if (args.apply or args.seed) and not args.rebuild:
        sys.exit(_echec(t("usage_flags_need_rebuild"), 2))
    if args.rebuild and (args.mark_absent or args.dry_run):          # sans --apply, --rebuild est déjà un essai à blanc
        sys.exit(_echec(t("usage_rebuild_options"), 2))
    sys.exit(reconstruire(args, t) if args.rebuild else deriver(args, t))


if __name__ == "__main__":
    main()
