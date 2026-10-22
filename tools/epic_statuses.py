# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml", "psycopg[binary]"]
# ///
"""
PMZilla Lab : relevé des statuts des épics (change jira-gdpr-alignment, tâche 10 ; décisions D6, D16, D18, D19).

    uv run tools/epic_statuses.py [--language fr|en]

À lancer par l'utilisateur seul, dans le Terminal (refusé dans une session Claude Code : règle deny et variable CLAUDECODE).

Lit les tickets et l'historique dans la base (schéma flow, rôle en lecture seule), garde les tickets des types d'épics (réglage
epic_types de flux.yaml, « Epic » par défaut) et écrit Flux-Lab/rapports/statuts-epics-AAAA-MM-JJ.md : par statut, le nombre d'épics
actuellement dedans, le nombre de passages observés dans l'historique et les transitions sortantes les plus fréquentes avec leurs
comptes. Tout compte inférieur à cinq est écrit « masqué » (« masked » en anglais). Ni clé, ni titre, ni équipe, ni personne, ni étiquette dans le rapport ni dans
la console (comptes et phrase clé seulement). Si le bloc discovery_workflow est présent, le rapport dit que la correspondance n'est pas
validée (sans date de validation) et liste les statuts mappés absents des statuts observés (noms seulement). L'outil n'écrit jamais la
correspondance. Un fichier d'export donné est refusé (« les fichiers d'export ne sont plus lus : la base est la seule source », code 2) ;
un chemin donné à --history aussi (« --history ne prend aucun fichier : l'historique est lu dans la base », code 2).

Codes de sortie : 0 rapport écrit ; 1 aucun épic, aucun historique dans la base, base injoignable ou réglage illisible ; 2 usage ou fichier
refusé ; 3 refusé dans une session Claude Code. Le dossier de travail se règle comme les outils voisins (PMZILLA_LAB_WORKSPACE). Aucun
réseau.

Exemple :
    uv run tools/epic_statuses.py
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lab_paths                                            # noqa: E402
import dependencies_jira as dependances                     # noqa: E402
import flux_config as cfg                                   # noqa: E402
import yaml                                                 # noqa: E402
from epic_statuses_messages import CATALOGS                 # noqa: E402
from messages import LANGUAGES, DEFAULT_LANGUAGE, Messages  # noqa: E402
from yaml_strict import ErreurConfig, charger               # noqa: E402

VARIABLE_CLAUDE_CODE = "CLAUDECODE"
SEUIL = 5                  # sous ce seuil, le compte est écrit « masqué » (idée #417 ; l'introduction du rapport donne le seuil)
TRANSITIONS_MAX = 5        # transitions sortantes listées par statut


class Usage(Exception):
    def __init__(self, cle: str):
        super().__init__(cle)
        self.cle = cle


class Analyseur(argparse.ArgumentParser):
    def error(self, message):                    # le message d'argparse peut citer ce que l'utilisateur a tapé
        raise Usage("u_option")


def compte(n: int, t: Messages) -> str:
    return t("cell_masked") if n < SEUIL else str(n)


def reglages(dossier_flux: Path) -> dict:
    """Réglages internes (colonnes par défaut des exports de l'API + flux.yaml s'il existe). Lève ErreurConfig."""
    fichier = dossier_flux / "flux.yaml"
    lu: dict = {}
    if fichier.exists():
        lu = cfg.to_internal(charger(fichier.read_text(encoding="utf-8"), "flux.yaml"), "flux.yaml")
    colonnes = {k: list(v) for k, v in dependances.DEFAULTS["colonnes"].items()}
    for champ, noms in (lu.get("colonnes") or {}).items():
        colonnes[champ] = list(noms) + [n for n in colonnes.get(champ, []) if n not in noms]
    return {**dependances.DEFAULTS, **lu, "colonnes": colonnes}


def releve(epics: dict[str, str], cache: dict[str, dict]) -> dict[str, dict]:
    """Par statut : épics actuellement dedans, passages observés (arrivées), transitions sortantes (Counter)."""
    statuts: dict[str, dict] = {}

    def fiche(nom: str) -> dict:
        return statuts.setdefault(nom, {"actuel": 0, "passages": 0, "sortantes": Counter()})
    for cle, etat in epics.items():
        if etat:
            fiche(etat)["actuel"] += 1
        for transition in (cache.get(cle.upper()) or {}).get("transitions", []):
            if len(transition) < 3:
                continue
            _, depart, arrivee = transition[:3]
            if arrivee:
                fiche(arrivee)["passages"] += 1
            if depart:
                fiche(depart)
                if arrivee:
                    statuts[depart]["sortantes"][arrivee] += 1
    return statuts


def nom_sur(nom: str) -> str:
    return nom.replace("|", "/").replace("\n", " ")


def rapport(t: Messages, jour: dt.date, nb_epics: int, statuts: dict[str, dict], avec_historique: bool,
            discovery: dict | None) -> str:
    lignes = [f"# {t('report_title', date=jour.isoformat())}", "", t("report_intro"), "",
              t("report_epics", n=compte(nb_epics, t)), ""]
    if not avec_historique:
        lignes += [t("history_absent"), ""]
    lignes += [f"| {t('col_status')} | {t('col_current')} | {t('col_passages')} | {t('col_outgoing')} |", "|---|---|---|---|"]
    for nom in sorted(statuts, key=lambda s: (-statuts[s]["actuel"], s)):
        fiche = statuts[nom]
        sortantes = sorted(fiche["sortantes"].items(), key=lambda e: (-e[1], e[0]))[:TRANSITIONS_MAX]
        cellule = "; ".join(f"{nom_sur(vers)} : {compte(n, t)}" for vers, n in sortantes) or t("none_cell")
        lignes.append(f"| {nom_sur(nom)} | {compte(fiche['actuel'], t)} | {compte(fiche['passages'], t)} | {cellule} |")
    if discovery is not None:
        lignes.append("")
        if not discovery["validated"]:
            lignes += [t("mapping_not_validated"), ""]
        absents = sorted({s for statuts_colonne in discovery["columns"].values() for s in statuts_colonne} - set(statuts))
        lignes += [f"## {t('mapped_not_observed')}", ""]
        lignes += [f"- {nom_sur(s)}" for s in absents] or [t("mapped_not_observed_none")]
    return "\n".join(lignes) + "\n"


def main(argv: list[str] | None = None, environ: dict | None = None) -> int:
    environ = os.environ if environ is None else environ
    parseur = Analyseur(prog="epic_statuses.py")        # --help : usage et code 0, sans rien lire
    parseur.add_argument("exports", nargs="*")          # un fichier d'export est refusé (code 2)
    parseur.add_argument("--history", nargs="?", const="", default=None)          # un chemin donné est refusé (code 2)
    parseur.add_argument("--language", default=DEFAULT_LANGUAGE)
    try:
        args = parseur.parse_args(sys.argv[1:] if argv is None else argv)
    except Usage as erreur:
        print(Messages(CATALOGS)(erreur.cle))
        return 2
    if args.language not in LANGUAGES:
        print(Messages(CATALOGS)("u_language"))
        return 2
    t = Messages(CATALOGS, args.language)
    if VARIABLE_CLAUDE_CODE in environ:                          # avant toute lecture de réglage et toute connexion
        print(t("refused_session"))
        return 3
    if args.exports:                                             # design D6 : refusé avant toute connexion, sans nommer le fichier
        print(t("export_files_retired"))
        return 2
    if args.history:                                             # --history reste un drapeau, sans valeur
        print(t("history_path_retired"))
        return 2
    flux = lab_paths.resolve_or_exit(environ)["content_root"] / "Flux-Lab"   # module partagé (R-77)
    try:
        interne = reglages(flux)
    except ErreurConfig as erreur:
        print(erreur.message)
        return 1
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        print(t("export_unreadable"))
        return 1
    types = {x.casefold() for x in cfg.epic_types(interne)}
    try:
        import flow_store                                        # import tardif : psycopg n'est chargé que pour la base
        tickets = flow_store.lire_tickets_flux(interne)[0]
        historique = flow_store.lire_historique(interne)
    except Exception as erreur:
        if type(erreur).__name__ != "ErreurBase":
            raise
        print(str(erreur))                                       # le message de la base ne porte ni mot de passe ni donnée
        return 1
    epics = {x["cle"]: x["etat"] for x in tickets if x["type"].casefold() in types}
    if not epics:
        print(t("no_epic"))
        return 1
    if not historique:
        print(t("no_history_in_db"))
        return 1
    cache = {cle.upper(): {"transitions": transitions} for cle, transitions in historique.items()}
    statuts = releve(epics, cache)
    jour = dt.date.today()
    dossier = flux / "rapports"
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / f"statuts-epics-{jour.isoformat()}.md").write_text(
        rapport(t, jour, len(epics), statuts, True, cfg.discovery_workflow(interne)), encoding="utf-8")
    print(t("epics_line", n=compte(len(epics), t)))
    print(t("statuses_line", n=compte(len(statuts), t)))
    print(t("report_written"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
