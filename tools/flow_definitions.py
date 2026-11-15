# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml", "psycopg[binary]"]
# ///
"""
PMZilla Lab : chargeur des définitions réelles de flux dans le référentiel du schéma flow (change flow-definitions-loader).

    uv run tools/flow_definitions.py load [--dry-run]

À lancer par l'utilisateur seul, dans le Terminal (refusé dans une session Claude Code : code 3, avant toute lecture ; règle deny en
plus). Il copie dans les trois tables de définitions (statuts de flux avec leurs deux drapeaux, types non planifiés, types de liens
bloquants) ce que les outils de flux lisent déjà, pour que les vues agrégées calculent sur les définitions réelles.

Ce qu'il lit : les réglages de flux, UNE seule fois, par le lecteur strict de tous les outils de flux (yaml_strict, flux_config.to_internal) ;
les lecteurs partagés des outils eux-mêmes (history_common.table_segments et point_engagement, flux_config.defect_types et types_liens) ;
et, en base, au seul moment de l'écriture, les quatre tables du référentiel des cycles (garde ci-dessous). Jamais Jira, jamais un ticket.
Ce qu'il écrit : uniquement par flow_referential.ecrire, sous le rôle d'import, en remplaçant les définitions en entier ; elles sont
datées par l'instant de chargement de la ligne d'état (horloge de la base), sans historique. Aucun nom de statut, de type, de lien
ni de segment, aucune valeur des réglages et aucun mot de passe n'est affiché : la sortie ne compte que des éléments de configuration.

Composition « définitions seules » (conception D4) : tant que le chargeur réel du référentiel des cycles n'existe pas, la partie des
cycles est écrite vide et la sortie le dit (« référentiel des cycles : non chargé, ses tables restent vides »). Garde : dans la
transaction du chargement et avant toute écriture, les quatre tables des cycles doivent être vides ; sinon refus (code 1, rien n'est
écrit) : un référentiel réel des cycles n'est jamais vidé par ce chargeur.

Ce que ce module remplace : rien (nouvelle commande). Conditions de retrait : la composition et sa garde tombent avec le chargeur réel du
référentiel des cycles, dont le change charge les deux parties en un appel de `ecrire` (il réutilise `construire_definitions`) et les
retire dans la même branche (conception D4) ; la commande, son refus de session et sa règle deny tombent avec R-164 (porte unique, D2),
sauf décision écrite dans le change de cette porte (conception D6). Les lecteurs partagés des deux rapports sont permanents tant qu'un
rapport a un défaut de code ; les défauts de statuts quittent history_common avec D106.

Codes de sortie : 0 fait ; 1 refus ou erreur ; 2 usage ; 3 session Claude Code. Messages en français seulement.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flow_referential as fr                               # noqa: E402
import flux_config as cfg                                   # noqa: E402
import history_common as commun                             # noqa: E402
import lab_paths                                            # noqa: E402
from yaml_strict import ErreurConfig, charger               # noqa: E402

ROLE = fr.ROLE_ECRITURE
VARIABLE_CLAUDE_CODE = "CLAUDECODE"
VARIABLE_REGLAGES = "FLOW_DEFINITIONS_SETTINGS"            # emplacement des réglages de flux, pour les tests (comme FLOW_RETENTION_SETTINGS)

MESSAGE_SESSION = "définitions de flux : à lancer par l'utilisateur seul, dans le Terminal"
MESSAGE_REGLAGES_ABSENTS = "définitions de flux : réglages de flux absents"
MESSAGE_REGLAGES_ILLISIBLES = "définitions de flux : réglages de flux illisibles"
MESSAGE_CYCLES_PRESENTS = ("définitions de flux : référentiel des cycles déjà chargé (cycle_referential_present), "
                           "rien n'est écrit")
LIGNE_CYCLES = "référentiel des cycles : non chargé, ses tables restent vides"

# Les quatre tables du référentiel des cycles, seules tables lues par la garde (conception D4).
TABLES_CYCLES = ("ref_cycles", "ref_labels", "ref_dw_columns", "ref_dw_statuses")
REQUETE_VERROU = "LOCK TABLE " + ", ".join(f"flow.{table}" for table in TABLES_CYCLES) + " IN SHARE ROW EXCLUSIVE MODE"
REQUETE_GARDE = "SELECT " + " OR ".join(f"EXISTS (SELECT 1 FROM flow.{table})" for table in TABLES_CYCLES)


class CyclesDejaCharges(Exception):
    """La garde de la conception D4 : une table des cycles contient une ligne ; rien n'est écrit."""


def construire_definitions(interne: dict) -> tuple[tuple[fr.StatutFlux, ...], tuple[fr.TypeNonPlanifie, ...],
                                                   tuple[fr.TypeLienBloquant, ...]]:
    """Les trois blocs de définitions, depuis les réglages déjà rendus par `flux_config.to_internal` (conception D1 et D2). Pure : aucun
    fichier, aucune connexion. Les drapeaux viennent de `definir_statut`, jamais d'un calcul ici ; un segment que les tables de noms ne
    connaissent pas est passé tel quel et refusé par `definir_statut` (flow_status_segment)."""
    noms = {**cfg.SEGMENTS, **cfg.UNCOUNTED}
    segment_de, calcules = commun.table_segments(interne)
    engagement_interne = commun.point_engagement(interne)
    engagement = noms.get(engagement_interne, engagement_interne)
    statuts = tuple(fr.definir_statut(statut, noms.get(segment, segment), engagement) for statut, segment in segment_de.items())
    if engagement_interne not in calcules:                      # comme le rapport de flux : le point d'engagement est un segment calculé
        raise fr.ReferentielInvalide(fr.MESSAGE_INVALIDE + "commitment_flag")
    non_planifies = tuple(fr.TypeNonPlanifie(nom, "defect") for nom in cfg.defect_types(interne))
    bloquants, attente = cfg.types_liens(interne)
    liens = (tuple(fr.TypeLienBloquant(nom, "blocks") for nom in bloquants)
             + tuple(fr.TypeLienBloquant(nom, "waits_for") for nom in attente))
    return statuts, non_planifies, liens


def referentiel_des_definitions(interne: dict) -> fr.Referentiel:
    """Référentiel dont la partie des cycles est vide (conception D4) et dont les définitions sont celles de `construire_definitions`."""
    statuts, non_planifies, liens = construire_definitions(interne)
    return fr.Referentiel(cycles=(), etiquettes=(), colonnes=(), statuts=(), valide_le=None, statuts_flux=statuts,
                          types_non_planifies=non_planifies, types_liens_bloquants=liens)


def verifier(referentiel: fr.Referentiel) -> None:
    """Lève ReferentielInvalide (codes seulement) si le référentiel est refusé ; aucune étiquette n'est déclarée."""
    constats = fr.valider(referentiel, ())
    if constats:
        raise fr.ReferentielInvalide(fr.MESSAGE_INVALIDE + ", ".join(constats))


def comptes(referentiel: fr.Referentiel) -> tuple[int, int, int]:
    return len(referentiel.statuts_flux), len(referentiel.types_non_planifies), len(referentiel.types_liens_bloquants)


def charger_definitions(connexion, interne: dict) -> tuple[int, int, int]:
    """Écrit les définitions par `flow_referential.ecrire`, sur la connexion de l'appelant, en une seule transaction (conception D1, D4).
    Dans cette transaction et avant toute écriture, vérifie que les quatre tables des cycles sont vides, sinon lève CyclesDejaCharges. Ne
    lit aucune autre table que ces quatre (et le rôle, que lit `ecrire`) ; ouvre aucune connexion. Rend les trois comptes."""
    referentiel = referentiel_des_definitions(interne)
    verifier(referentiel)                                       # refus avant la moindre instruction
    with connexion.transaction():
        connexion.execute(REQUETE_VERROU)                       # un chargeur des cycles concurrent attend la fin de celui-ci
        if connexion.execute(REQUETE_GARDE).fetchone()[0]:
            raise CyclesDejaCharges(MESSAGE_CYCLES_PRESENTS)    # la sortie annule la transaction : rien n'est écrit
        fr.ecrire(connexion, referentiel, ())
    return comptes(referentiel)


def chemin_reglages(environ) -> Path:
    if environ.get(VARIABLE_REGLAGES):
        return Path(environ[VARIABLE_REGLAGES]).expanduser()
    return lab_paths.resolve_or_exit(environ)["content_root"] / "Flux-Lab" / "flux.yaml"


def lire_reglages(chemin: Path) -> dict:
    """Une seule lecture stricte des réglages de flux, sous les noms internes ; n'en crée jamais le fichier."""
    return cfg.to_internal(charger(chemin.read_text(encoding="utf-8"), "flux.yaml") or {}, "flux.yaml")


def ouvrir_base_import():
    import db
    return db.connect(role=ROLE)


def _echec(message: str, code: int = 1) -> int:
    print(message, file=sys.stderr)
    return code


def lire_arguments(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chargeur des définitions réelles de flux dans le référentiel du schéma flow")
    sous = parser.add_subparsers(dest="commande", required=True)
    charge = sous.add_parser("load", help="charge les définitions de flux (statuts, types non planifiés, types de liens bloquants)")
    charge.add_argument("--dry-run", action="store_true", help="construit et valide, n'ouvre aucune connexion, n'écrit rien")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, environ=None, ouvrir_base=None) -> int:
    """Rend le code de sortie. `environ` et `ouvrir_base` sont remplaçables pour les tests."""
    environ = os.environ if environ is None else environ
    ouvrir_base = ouvrir_base or ouvrir_base_import
    if VARIABLE_CLAUDE_CODE in environ:                         # avant toute lecture : ni réglage, ni dossier, ni base
        return _echec(MESSAGE_SESSION, 3)
    try:
        args = lire_arguments(sys.argv[1:] if argv is None else argv)
    except SystemExit as sortie:                                # usage : l'analyseur a déjà écrit son message
        return int(sortie.code or 0)
    chemin = chemin_reglages(environ)
    if not chemin.exists():
        return _echec(MESSAGE_REGLAGES_ABSENTS)
    try:
        interne = lire_reglages(chemin)
        referentiel = referentiel_des_definitions(interne)
        verifier(referentiel)
    except ErreurConfig as erreur:                              # le message nomme des clés et des lignes, jamais une valeur
        return _echec(str(erreur))
    except (OSError, UnicodeError):                             # aucun détail : ni chemin réel ni message du système
        return _echec(MESSAGE_REGLAGES_ILLISIBLES)
    except fr.ReferentielInvalide as refus:
        return _echec(str(refus))
    n_statuts, n_types, n_liens = comptes(referentiel)
    if args.dry_run:
        print(f"définitions de flux, essai à blanc : {n_statuts} statuts, {n_types} types non planifiés, "
              f"{n_liens} types de liens bloquants ; rien n'est écrit")
        return 0
    conn = None
    try:
        conn = ouvrir_base()
    except Exception as erreur:                                 # aucun détail : seul le nom du type (jamais le mot de passe)
        return _echec(f"définitions de flux : base injoignable ({type(erreur).__name__})")
    try:
        charger_definitions(conn, interne)
        conn.commit()
    except CyclesDejaCharges as refus:
        return _echec(str(refus))
    except fr.ReferentielInvalide as refus:
        return _echec(str(refus))
    except Exception as erreur:                                 # aucun détail : un message de la base pourrait citer une valeur
        return _echec(f"définitions de flux : erreur inattendue ({type(erreur).__name__}), rien n'est écrit")
    finally:
        if conn is not None:
            conn.close()
    print(f"définitions de flux chargées : {n_statuts} statuts, {n_types} types non planifiés, {n_liens} types de liens bloquants")
    print(LIGNE_CYCLES)
    return 0


if __name__ == "__main__":
    sys.exit(main())
