"""PMZilla Lab : noms des réglages de Flux-Lab/flux.yaml (plan de la version anglaise, 7.6).

Les clés de flux.yaml ont un nom anglais. Les anciens noms français sont refusés (arrêt avec un message qui donne le nom
actuel). Les scripts travaillent encore avec les noms français internes : `to_internal` lit les noms anglais et rend les
noms internes, `to_public` fait l'inverse (pour écrire les réglages par défaut), `migrate_text` réécrit un flux.yaml
d'avant le lot 8 dans les nouveaux noms en gardant ses commentaires et sa mise en page (les tables ci-dessous servent à
la migration et au message de refus).

    uv run tools/flux_jira.py config migrate [--dry-run]    réécrit Flux-Lab/flux.yaml (à lancer par l'utilisateur)

Rien dans ce module ne lit Flux-Lab/ de lui-même : il reçoit un dictionnaire ou un texte.
"""
from __future__ import annotations

import datetime
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from yaml_strict import ErreurConfig

# ancien nom (interne, français) -> nouveau nom
TOP = {
    "colonnes": "columns",
    "etats_en_cours": "in_progress_states",
    "etats_a_faire": "todo_states",
    "etats_attente": "waiting_states",
    "motifs_exclus": "excluded_resolutions",
    "types_portefeuille": "portfolio_types",
    "projets_exclus": "excluded_projects",
    "projets_perimetre": "scope_projects",
    "segments": "segments",
    "segments_hors_calcul": "uncounted_segments",
    "point_engagement": "commitment_point",
    "separateur_equipes": "team_separator",
    "seuil_fermetures_groupees": "batch_closure_threshold",
    "motifs_fermetures_groupees": "batch_closure_resolutions",
    "serie_par_defaut": "default_series",
    "noms_projets": "project_names",
    "tableaux": "boards",
    "jira_jeton": "jira_token_type",
    "export_champ_equipe": "export_team_field",
    "export_entete_equipe": "export_team_header",
    "export_champ_verification": "export_verification_field",
    "export_entete_verification": "export_verification_header",
    "export_fuseau": "export_timezone",
    "types_bloquants": "blocking_link_types",
    "types_attente": "waiting_link_types",
}
# réglages supprimés : l'export de l'API a un format de date fixe (history_common.FORMAT_DATE). Les deux noms sont refusés.
REGLAGES_IGNORES = {"format_date", "date_format"}
# noms français de colonnes qui étaient dans les listes par défaut (export manuel de Jira), supprimés avec l'export
# manuel : refusés, comparés sans casse, quand flux.yaml les redonne dans `columns`. Tout autre nom de colonne donné dans
# `columns` est un ajout légitime et reste.
ALIAS_COLONNES_SUPPRIMES = {n.casefold() for n in (
    "Type de ticket", "État", "Etat", "Statut", "Catégorie d'état", "Catégorie de statut", "Clé", "Clé de ticket",
    "Clé du ticket", "Créé", "Création", "Résolu", "Résolution (date)", "Résolution", "Catégorie d'état modifiée",
    "Équipe", "Equipe", "Composants", "Mis à jour", "Mise à jour", "Modifié", "Points d'histoire", "Clé parente")}
# anciens noms d'avant 7.6, refusés (et migrés par `config migrate`) : ils vont vers le même réglage interne
ANCIENS_ALIAS = {"types_exclus": "types_portefeuille"}
# clés qui ne changent pas
INCHANGEES = {"jira_site", "jira_email", "jql_export", "jql_exports", "export_points_field",
              "flow_views_min_cell",
              # R-58 : identifiant cloud, échéance du jeton, étiquettes déclarées, cycles, patches, Discovery Workflow, conservation
              "jira_cloud_id", "jira_token_expires", "jira_token_warning_days", "declared_labels", "cycles", "patches",
              "discovery_workflow", "retention", "epic_types"}
# réglage refusé dans tous les lecteurs (le PO responsable n'est pas stocké, conception D3) : le message porte la phrase clé
# de la conception D19 dans les deux langues (ErreurConfig n'a pas de langue)
REGLAGE_REFUSE = "export_po_field"

COLUMNS = {"type": "type", "etat": "status", "categorie": "category", "cle": "key", "cree": "created",
           "resolu": "resolved", "motif": "resolution", "debut": "category_changed", "equipe": "team",
           "parent": "parent", "modifie": "updated", "story_points": "story_points"}
SEGMENTS = {"definition": "definition", "pret": "ready", "implementation": "implementation",
            "revue_verification": "review_verification", "acceptation": "acceptance"}
UNCOUNTED = {"a_faire": "todo", "termine": "done"}
BOARDS = {"series": "series"}
BOARD = {"nom": "name", "dependances": "dependencies", "dependances_projets": "project_dependencies", "base": "baseline"}
# valeurs renommées : réglage interne -> {ancienne valeur: nouvelle valeur}
VALEURS = {"point_engagement": SEGMENTS, "jira_jeton": {"scopes": "scoped", "classique": "classic"}}

# sous-clés d'un réglage : (réglage interne, niveau) -> table
SOUS_TABLES = {"colonnes": COLUMNS, "segments": SEGMENTS, "segments_hors_calcul": UNCOUNTED, "tableaux": BOARDS}

# Options renommées communes à plusieurs scripts (plan 7.5) : ancien nom -> nouveau nom
OPTIONS_COMMUNES = {"--nom": "--name", "--perimetre": "--scope", "--semaines": "--weeks", "--historique": "--history",
                    "--aujourdhui": "--today", "--sortie": "--output", "--ouvrir": "--open",
                    "--anonyme": "--anonymous", "--langue": "--language", "--equipe": "--team"}

def refuse_old_options(argv: list[str], table: dict[str, str]) -> list[str]:
    """Refuse les anciens noms d'options (`--cle`, aussi sous la forme `--cle=valeur`) : arrêt avec le code 2 et un message
    qui donne le nom actuel. Les noms actuels passent sans message ; tout ce qui suit `--` est laissé tel quel."""
    for i, argument in enumerate(argv):
        if argument == "--":
            break
        nom = argument.partition("=")[0]
        if nom in table:
            print(f"PMZilla Lab, erreur : l'option « {nom} » n'existe plus ; utiliser « {table[nom]} ».", file=sys.stderr)
            raise SystemExit(2)
    return list(argv)


def _inverse(table: dict[str, str]) -> dict[str, str]:
    return {nouveau: ancien for ancien, nouveau in table.items()}




def _refus(source: str, lignes: dict, cle: str, chemin: str, message: str) -> ErreurConfig:
    """Refus d'un ancien nom : la ligne (quand le fichier vient de `charger`), puis ce qu'il faut écrire. Jamais une valeur."""
    ligne = lignes.get(cle)
    return ErreurConfig(f"{source} : {f'L{ligne} : ' if ligne else ''}{message} "
                        "(`uv run tools/flux_jira.py config migrate` réécrit le fichier).")


def _cle_interne(cle: str, table_publique: dict[str, str], chemin: str, source: str, lignes: dict) -> str:
    """Nom interne (français) d'une clé donnée sous le nom actuel ; l'ancien nom est refusé."""
    inverse = _inverse(table_publique)
    if cle in inverse and inverse[cle] != cle:             # nom actuel
        return inverse[cle]
    if cle in table_publique and table_publique[cle] != cle:   # ancien nom
        raise _refus(source, lignes, cle, chemin,
                     f"« {chemin}{cle} » n'existe plus ; utiliser « {chemin}{table_publique[cle]} »")
    return cle


def _valeur_interne(reglage: str, valeur, source: str, lignes: dict, cle: str):
    table = VALEURS.get(reglage)
    if not table or not isinstance(valeur, str):
        return valeur
    if valeur in _inverse(table) and _inverse(table)[valeur] != valeur:
        return _inverse(table)[valeur]
    if valeur in table and table[valeur] != valeur:
        raise _refus(source, lignes, cle, "", f"valeur « {valeur} » du réglage {TOP.get(reglage, reglage)} n'existe plus ; utiliser « {table[valeur]} »")
    return valeur


def to_internal(raw: dict | None, source: str = "flux.yaml", warn: bool = True) -> dict:
    """Réglages lus dans un fichier, sous les noms actuels, rendus avec les noms internes.

    Un ancien nom (réglage, sous-clé, valeur, colonne française), à n'importe quel niveau, lève `ErreurConfig` avec le nom
    actuel. Si `raw` vient de `yaml_strict.charger`, le message donne le numéro de ligne. `warn` est gardé pour les appelants
    existants et ne sert plus."""
    return _vers_interne(raw, source)


def _vers_interne(raw: dict | None, source: str) -> dict:
    sortie: dict = {}
    lignes = getattr(raw, "lignes", {})
    for cle, valeur in (raw or {}).items():
        if cle == REGLAGE_REFUSE:
            ligne = lignes.get(cle)
            raise ErreurConfig(f"{source} : {f'L{ligne} : ' if ligne else ''}réglage non pris en charge : {REGLAGE_REFUSE} "
                               f"/ setting not supported: {REGLAGE_REFUSE}")
        if cle in REGLAGES_IGNORES:
            raise _refus(source, lignes, cle, "", f"« {cle} » n'existe plus : l'export de l'API a un format de date fixe ; "
                         "supprimer la ligne")
        if cle in ANCIENS_ALIAS:
            raise _refus(source, lignes, cle, "", f"« {cle} » n'existe plus ; utiliser « {TOP[ANCIENS_ALIAS[cle]]} »")
        interne = _cle_interne(cle, TOP, "", source, lignes)
        if interne in SOUS_TABLES and isinstance(valeur, dict):
            table = SOUS_TABLES[interne]
            convertie = {}
            sous_lignes = getattr(valeur, "lignes", {})
            for sous, contenu in valeur.items():
                nom = _cle_interne(sous, table, f"{cle}.", source, sous_lignes)
                if interne == "tableaux" and nom == "series" and isinstance(contenu, list):
                    contenu = [_serie_interne(s, source, f"{cle}.{sous}.") for s in contenu]
                convertie[nom] = contenu
            valeur = _sans_alias_francais(convertie, source, sous_lignes) if interne == "colonnes" else convertie
        else:
            valeur = _valeur_interne(interne, valeur, source, lignes, cle)
        sortie[interne] = valeur
    _valider_nouveaux_blocs(sortie, source, lignes)
    return sortie


def _sans_alias_francais(colonnes: dict, source: str, lignes: dict) -> dict:
    """Refuse dans `columns` les anciens noms français de colonnes (liste ALIAS_COLONNES_SUPPRIMES). Les autres noms (nom
    de la colonne d'équipe, par exemple) sont gardés."""
    for champ, noms in colonnes.items():
        if isinstance(noms, list):
            for n in noms:
                if isinstance(n, str) and n.strip().casefold() in ALIAS_COLONNES_SUPPRIMES:
                    raise ErreurConfig(f"{source} : « {n.strip()} » n'existe plus dans `columns` : l'export de l'API a des "
                                       "en-têtes fixes en anglais ; `columns` ne sert qu'à ajouter d'autres noms.")
    return colonnes


def _serie_interne(serie, source: str, chemin: str):
    if not isinstance(serie, dict):
        return serie
    lignes = getattr(serie, "lignes", {})
    return {_cle_interne(k, BOARD, chemin, source, lignes): v for k, v in serie.items()}


def to_public(interne: dict) -> dict:
    """Réglages internes -> noms anglais (écriture du fichier de réglages par défaut)."""
    sortie: dict = {}
    for cle, valeur in interne.items():
        nouveau = TOP.get(cle, cle)
        if cle in SOUS_TABLES and isinstance(valeur, dict):
            table = SOUS_TABLES[cle]
            valeur = {table.get(k, k): (([{BOARD.get(a, a): b for a, b in s.items()} if isinstance(s, dict) else s
                                          for s in v] if cle == "tableaux" and isinstance(v, list) else v))
                      for k, v in valeur.items()}
        elif cle in VALEURS and isinstance(valeur, str):
            valeur = VALEURS[cle].get(valeur, valeur)
        sortie[nouveau] = valeur
    return sortie


# ---------------------------------------------------------------------------
# Migration d'un flux.yaml existant (texte, commentaires conservés)
# ---------------------------------------------------------------------------

LIGNE_CLE = re.compile(r"^(?P<indent>\s*)(?P<tiret>- )?(?P<cle>[A-Za-z_][A-Za-z0-9_]*)(?P<reste>\s*:.*)$")


class MigrationConflict(Exception):
    """Deux clés du même bloc donneraient la même clé après migration (ou une clé est écrite deux fois) : rien n'est
    écrit. `conflits` : phrases sans valeurs (numéros de ligne et noms de clés) ; `changements` : ce qui aurait été fait."""

    def __init__(self, conflits: list[str], changements: list[str]):
        super().__init__("; ".join(conflits))
        self.conflits = conflits
        self.changements = changements


def migrate_analysis(texte: str) -> tuple[str, list[str], list[str]]:
    """Réécrit les clés (et les valeurs de `commitment_point` et `jira_token_type`) en nouveaux noms.

    Rend le texte, les changements (« LN : chemin.de.la.clé -> nouveau », le chemin tel qu'il est écrit dans le
    fichier, sans valeurs) et les conflits (deux clés d'un même bloc qui donnent le même nom, ou une clé en double). Idempotent :
    un fichier déjà migré ne change pas. Les commentaires, l'ordre et la mise en page sont conservés."""
    sortie: list[str] = []
    changements: list[str] = []
    conflits: list[str] = []
    pile: list[tuple[int, str, str, int]] = []        # (colonne de la clé, nom interne, nom écrit, numéro de ligne)
    vus: dict[tuple, dict[str, tuple[int, str]]] = {}   # bloc -> {nom après migration: (ligne, nom écrit)}
    item = 0                                           # ligne du dernier « - » (entrée d'une liste de séries)
    interne_de = {**{v: k for k, v in TOP.items()}, **{k: k for k in TOP}}
    for numero, ligne in enumerate(texte.split("\n"), start=1):
        m = None if ligne.lstrip().startswith("#") else LIGNE_CLE.match(ligne)
        if not m:
            sortie.append(ligne)
            continue
        colonne = len(m["indent"]) + (2 if m["tiret"] else 0)
        while pile and pile[-1][0] >= colonne:
            pile.pop()
        chemin = tuple(nom for _, nom, _, _ in pile)
        ecrit = ".".join(nom for _, _, nom, _ in pile)
        cle = m["cle"]
        if m["tiret"]:
            item = numero
        nouveau, interne, connue = cle, cle, False
        if not chemin:
            interne = ANCIENS_ALIAS.get(interne_de.get(cle, cle), interne_de.get(cle, cle))
            connue = cle in TOP or cle in TOP.values() or cle in ANCIENS_ALIAS or cle in INCHANGEES
            nouveau = TOP.get(interne, cle) if cle in TOP or cle in ANCIENS_ALIAS else cle
        elif len(chemin) == 1 and chemin[0] in SOUS_TABLES:
            table = SOUS_TABLES[chemin[0]]
            interne = {**_inverse(table), **{k: k for k in table}}.get(cle, cle)
            connue = cle in table or cle in table.values()
            nouveau = table.get(interne, cle)
        elif chemin == ("tableaux", "series"):
            interne = {**_inverse(BOARD), **{k: k for k in BOARD}}.get(cle, cle)
            connue = cle in BOARD or cle in BOARD.values()
            nouveau = BOARD.get(interne, cle)
        if connue:
            bloc = (pile[-1][3] if pile else 0, item if chemin == ("tableaux", "series") else 0)
            deja = vus.setdefault(bloc, {}).get(nouveau)
            if deja:
                memes = deja[1] == cle
                conflits.append(f"L{deja[0]} et L{numero} : "
                                + (f"« {(ecrit + '.' if ecrit else '') + cle} » est écrite deux fois" if memes else
                                   f"« {(ecrit + '.' if ecrit else '') + deja[1]} » et « {(ecrit + '.' if ecrit else '') + cle} » "
                                   f"donnent la même clé « {nouveau} »"))
            else:
                vus[bloc][nouveau] = (numero, cle)
        reste = m["reste"]
        if not chemin and interne in VALEURS:
            reste = _migrer_valeur(interne, reste, changements, numero)
        if nouveau != cle:
            changements.append(f"L{numero} : {(ecrit + '.' if ecrit else '') + cle} -> {nouveau}")
        sortie.append(f"{m['indent']}{m['tiret'] or ''}{nouveau}{reste}")
        pile.append((colonne, interne, cle, numero))
    return "\n".join(sortie), changements, conflits


def migrate_text(texte: str) -> tuple[str, list[str]]:
    """`migrate_analysis` sans les conflits : s'il y en a, lève `MigrationConflict` (rien ne doit être écrit)."""
    nouveau, changements, conflits = migrate_analysis(texte)
    if conflits:
        raise MigrationConflict(conflits, changements)
    return nouveau, changements


def _migrer_valeur(interne: str, reste: str, changements: list[str], numero: int) -> str:
    m = re.match(r"^(\s*:\s*)(['\"]?)([A-Za-z_]+)(['\"]?)(\s*(?:#.*)?)$", reste)
    if not m:
        return reste
    ancienne = m[3]
    nouvelle = VALEURS[interne].get(ancienne)
    if nouvelle is None or nouvelle == ancienne:
        return reste
    changements.append(f"L{numero} : valeur de {interne} : {ancienne} -> {nouvelle}")
    return f"{m[1]}{m[2]}{nouvelle}{m[4]}{m[5]}"


def migrate_file(chemin: Path, dry_run: bool = False) -> list[str]:
    """Réécrit un flux.yaml en nouveaux noms ; garde l'ancien à côté (`flux.yaml.avant-migration`). Aucune valeur
    n'est affichée : seulement les noms de clés changés."""
    texte = chemin.read_text(encoding="utf-8")
    nouveau, changements = migrate_text(texte)          # MigrationConflict : rien n'est écrit
    if changements and not dry_run:
        sauvegarde = chemin.with_name(chemin.name + ".avant-migration")
        if not sauvegarde.exists():
            shutil.copy2(chemin, sauvegarde)
        chemin.write_text(nouveau, encoding="utf-8")
    return changements


# ---------------------------------------------------------------------------
# Réglages du change R-58 : validation à la lecture (to_internal) et lecteurs normalisés
# ---------------------------------------------------------------------------

CLE_CYCLE = re.compile(r"^(?P<annee>\d{4})-(?:C(?P<n>[1-6])|(?P<eoy>EOY))$")
CLE_PATCH = re.compile(r"^(?P<annee>\d{4})-Q[1-4]$")
ROLES_ETIQUETTES = ("up_merge", "cycle", "epic_review")
CHAMPS_CYCLE = {"fix_version", "start", "end", "up_merge_provision", "base_version"}
CHAMPS_DISCOVERY = {"columns", "start_column", "review_passed_columns", "validated_on"}
# réglage de conservation -> (défaut, minimum)
CHAMPS_RETENTION = {"period_days": (365, 1), "max_file_age_days": (365, 0), "labelled_backup_days": (30, 1),
                    "offsite_flow_age_days": (35, 1)}
ETIQUETTE_SAUVEGARDE = re.compile(r"[a-z0-9]+")
DUREE_CYCLE_JOURS = 53        # huit semaines, du lundi au vendredi
PERIODE_MAX_JOURS = 365


def _ligne(bloc, cle) -> str:
    """« L12 : » quand le dictionnaire vient de `charger` et connaît la ligne de la clé, sinon rien."""
    numero = getattr(bloc, "lignes", {}).get(cle)
    return f"L{numero} : " if numero else ""


def _refus_reglage(source: str, bloc, cle, chemin: str, message: str) -> ErreurConfig:
    """Refus d'un réglage : ligne de la clé, chemin de la clé, ce qui ne va pas. Jamais la valeur."""
    return ErreurConfig(f"{source} : {_ligne(bloc, cle)}« {chemin} » {message}")


def _date(valeur) -> datetime.date | None:
    """Date AAAA-MM-JJ lue par YAML (date) ou écrite en chaîne ISO ; None sinon."""
    if isinstance(valeur, datetime.datetime):
        return None
    if isinstance(valeur, datetime.date):
        return valeur
    if isinstance(valeur, str):
        try:
            return datetime.date.fromisoformat(valeur.strip())
        except ValueError:
            return None
    return None


def _entier(valeur, minimum: int) -> bool:
    return isinstance(valeur, int) and not isinstance(valeur, bool) and valeur >= minimum


def _valider_nouveaux_blocs(interne: dict, source: str, lignes: dict) -> None:
    """Valide les réglages R-58 présents (rien n'est lu pour un bloc absent) ; lève `ErreurConfig` (chemin et ligne)."""
    if "jira_cloud_id" in interne and not (isinstance(interne["jira_cloud_id"], str) and interne["jira_cloud_id"].strip()):
        raise _refus_reglage(source, interne_lignes(lignes), "jira_cloud_id", "jira_cloud_id", "doit être une chaîne non vide")
    if "jira_token_expires" in interne and _date(interne["jira_token_expires"]) is None:
        raise _refus_reglage(source, interne_lignes(lignes), "jira_token_expires", "jira_token_expires",
                             "doit être une date AAAA-MM-JJ")
    if "jira_token_warning_days" in interne and not _entier(interne["jira_token_warning_days"], 1):
        raise _refus_reglage(source, interne_lignes(lignes), "jira_token_warning_days", "jira_token_warning_days",
                             "doit être un entier supérieur à zéro")
    if "declared_labels" in interne:
        _valider_etiquettes(interne["declared_labels"], source, lignes)
    if "cycles" in interne:
        _valider_cycles(interne["cycles"], source, lignes)
    if "patches" in interne:
        _valider_patches(interne["patches"], interne.get("cycles"), source, lignes)
    if "discovery_workflow" in interne:
        _valider_discovery(interne["discovery_workflow"], source, lignes)
    if "retention" in interne:
        _valider_retention(interne["retention"], source, lignes)
    if "epic_types" in interne:
        valeur = interne["epic_types"]
        if not (isinstance(valeur, list) and valeur and all(isinstance(t, str) and t.strip() for t in valeur)):
            raise _refus_reglage(source, interne_lignes(lignes), "epic_types", "epic_types",
                                 "doit être une liste non vide de types de tickets (chaînes)")


def interne_lignes(lignes: dict):
    """Petit adaptateur : `_refus_reglage` lit l'attribut `lignes` d'un dictionnaire ; ici on a déjà ce dictionnaire."""
    class _L:
        pass
    objet = _L()
    objet.lignes = lignes
    return objet


def _bloc_dict(valeur, source: str, parent_lignes: dict, cle: str, chemin: str):
    if not isinstance(valeur, dict):
        raise _refus_reglage(source, interne_lignes(parent_lignes), cle, chemin, "doit être un bloc de réglages")
    return valeur


def _valider_etiquettes(bloc, source: str, lignes: dict) -> None:
    """declared_labels : rôle -> {prefix, labels}. up_merge : exactement deux étiquettes (la première est le légal, la
    seconde le hotfix). Chaque étiquette commence par le préfixe de son rôle ; aucune n'est déclarée deux fois."""
    bloc = _bloc_dict(bloc, source, lignes, "declared_labels", "declared_labels")
    deja: dict[str, str] = {}
    for role, contenu in bloc.items():
        chemin = f"declared_labels.{role}"
        if role not in ROLES_ETIQUETTES:
            raise _refus_reglage(source, bloc, role, chemin, "n'est pas un rôle connu (up_merge, cycle, epic_review)")
        contenu = _bloc_dict(contenu, source, bloc.lignes if hasattr(bloc, "lignes") else {}, role, chemin)
        for sous in contenu:
            if sous not in ("prefix", "labels"):
                raise _refus_reglage(source, contenu, sous, f"{chemin}.{sous}", "n'existe pas (clés : prefix, labels)")
        prefixe, etiquettes = contenu.get("prefix"), contenu.get("labels")
        if not (isinstance(prefixe, str) and prefixe):
            raise _refus_reglage(source, bloc, role, f"{chemin}.prefix", "doit être une chaîne non vide")
        if not (isinstance(etiquettes, list) and etiquettes and all(isinstance(e, str) and e for e in etiquettes)):
            raise _refus_reglage(source, contenu, "labels", f"{chemin}.labels", "doit être une liste d'étiquettes (chaînes)")
        if role == "up_merge" and len(etiquettes) != 2:
            raise _refus_reglage(source, contenu, "labels", f"{chemin}.labels",
                                 "doit déclarer exactement deux étiquettes (le légal puis le hotfix)")
        for e in etiquettes:
            if not e.startswith(prefixe):
                raise _refus_reglage(source, contenu, "labels", f"{chemin}.labels",
                                     f"contient une étiquette qui ne commence pas par le préfixe du rôle")
            if e in deja:
                raise _refus_reglage(source, contenu, "labels", f"{chemin}.labels",
                                     f"déclare une étiquette déjà déclarée ({deja[e]})")
            deja[e] = f"{chemin}.labels"


def _valider_cycles(bloc, source: str, lignes: dict) -> None:
    """cycles : clé AAAA-Cn / AAAA-EOY -> {fix_version, start, end, up_merge_provision?, base_version?}."""
    bloc = _bloc_dict(bloc, source, lignes, "cycles", "cycles")
    vues_versions: dict[str, str] = {}
    base_par_annee: dict[str, str] = {}
    par_annee: dict[str, list] = {}
    for cle, c in bloc.items():
        m = CLE_CYCLE.match(str(cle))
        chemin = f"cycles.{cle}"
        if not m:       # la clé peut être un numéro de version : elle n'est pas répétée
            raise _refus_reglage(source, bloc, cle, "cycles", "contient une clé qui n'a pas la forme AAAA-Cn (n de 1 à 6) "
                                 "ou AAAA-EOY")
        c = _bloc_dict(c, source, bloc.lignes if hasattr(bloc, "lignes") else {}, cle, chemin)
        for sous in c:
            if sous not in CHAMPS_CYCLE:
                raise _refus_reglage(source, c, sous, f"{chemin}.{sous}", f"n'existe pas (clés : {', '.join(sorted(CHAMPS_CYCLE))})")
        version = c.get("fix_version")
        if not (isinstance(version, str) and version.strip()):
            raise _refus_reglage(source, bloc, cle, f"{chemin}.fix_version", "doit être une chaîne non vide")
        if version in vues_versions:
            raise _refus_reglage(source, bloc, cle, chemin,
                                 f"a la même version corrigée que « cycles.{vues_versions[version]} » (une version, une clé)")
        vues_versions[version] = cle
        debut, fin = _date(c.get("start")), _date(c.get("end"))
        if debut is None:
            raise _refus_reglage(source, bloc, cle, f"{chemin}.start", "doit être une date AAAA-MM-JJ")
        if fin is None:
            raise _refus_reglage(source, bloc, cle, f"{chemin}.end", "doit être une date AAAA-MM-JJ")
        if debut.weekday() != 0:
            raise _refus_reglage(source, bloc, cle, f"{chemin}.start", "doit être un lundi")
        if fin.weekday() != 4:
            raise _refus_reglage(source, bloc, cle, f"{chemin}.end", "doit être un vendredi")
        if fin <= debut:
            raise _refus_reglage(source, bloc, cle, chemin, "finit avant de commencer")
        if "up_merge_provision" in c:
            p = c["up_merge_provision"]
            if isinstance(p, bool) or not isinstance(p, (int, float)) or not 0 <= p <= 1:
                raise _refus_reglage(source, bloc, cle, f"{chemin}.up_merge_provision",
                                     "doit être un nombre entre 0 et 1")
        if "base_version" in c:
            if not isinstance(c["base_version"], bool):
                raise _refus_reglage(source, bloc, cle, f"{chemin}.base_version", "doit valoir true ou false")
            if c["base_version"]:
                if m["eoy"]:
                    raise _refus_reglage(source, bloc, cle, f"{chemin}.base_version",
                                         "n'est permis que sur un cycle AAAA-Cn")
                if m["annee"] in base_par_annee:
                    autre = base_par_annee[m["annee"]]
                    raise _refus_reglage(source, bloc, cle, f"{chemin}.base_version",
                                         f"est déjà posé sur « cycles.{autre} » ({_ligne(bloc, autre).strip(' :')}) "
                                         "(une version de base par année)")
                base_par_annee[m["annee"]] = cle
        if not m["eoy"]:
            par_annee.setdefault(m["annee"], []).append((debut, fin, cle))
            if (fin - debut).days != DUREE_CYCLE_JOURS:
                print(f"PMZilla Lab, avertissement : {source} : le cycle {cle} ne dure pas huit semaines.", file=sys.stderr)
    # cycles consécutifs, dans une même année seulement (la version de fin d'année est hors de la chaîne)
    for cycles_annee in par_annee.values():
        cycles_annee.sort()
        for (_, fin_prec, _), (debut, _, cle) in zip(cycles_annee, cycles_annee[1:]):
            if debut != fin_prec + datetime.timedelta(days=3):
                raise _refus_reglage(source, bloc, cle, f"cycles.{cle}.start",
                                     "ne commence pas le lundi qui suit la fin du cycle précédent")


def _valider_patches(bloc, cycles_bloc, source: str, lignes: dict) -> None:
    """patches : clé AAAA-Qn -> liste de versions de correctif ; une version n'est que dans une clé, et pas dans `cycles`."""
    bloc = _bloc_dict(bloc, source, lignes, "patches", "patches")
    versions_cycles = {c.get("fix_version"): k for k, c in cycles_bloc.items() if isinstance(c, dict)} \
        if isinstance(cycles_bloc, dict) else {}
    vues: dict[str, str] = {}
    for cle, versions in bloc.items():
        if not CLE_PATCH.match(str(cle)):
            raise _refus_reglage(source, bloc, cle, "patches", "contient une clé qui n'a pas la forme AAAA-Qn (n de 1 à 4)")
        chemin = f"patches.{cle}"
        if not (isinstance(versions, list) and all(isinstance(v, str) and v for v in versions)):
            raise _refus_reglage(source, bloc, cle, chemin, "doit être une liste de versions (chaînes)")
        for v in versions:
            if v in vues:
                raise _refus_reglage(source, bloc, cle, chemin,
                                     f"a une version déjà donnée à « patches.{vues[v]} » (une version, une clé)")
            if v in versions_cycles:
                raise _refus_reglage(source, bloc, cle, chemin,
                                     f"a une version déjà donnée à « cycles.{versions_cycles[v]} » (une version, une clé)")
            vues[v] = cle


def _valider_discovery(bloc, source: str, lignes: dict) -> None:
    """discovery_workflow : colonnes (nom -> statuts), colonne de départ, colonnes « revue passée », date de validation.
    `start_column` et `review_passed_columns` sont facultatifs ici (rien n'est calculé sans date de validation)."""
    bloc = _bloc_dict(bloc, source, lignes, "discovery_workflow", "discovery_workflow")
    for sous in bloc:
        if sous not in CHAMPS_DISCOVERY:
            raise _refus_reglage(source, bloc, sous, f"discovery_workflow.{sous}",
                                 f"n'existe pas (clés : {', '.join(sorted(CHAMPS_DISCOVERY))})")
    colonnes = bloc.get("columns")
    if not isinstance(colonnes, dict) or not colonnes:
        raise _refus_reglage(source, interne_lignes(lignes), "discovery_workflow", "discovery_workflow.columns",
                             "doit être un bloc : nom de colonne -> liste de statuts")
    statut_vers_colonne: dict[str, str] = {}
    for nom, statuts in colonnes.items():
        if not (isinstance(statuts, list) and all(isinstance(s, str) and s for s in statuts)):
            raise _refus_reglage(source, colonnes, nom, f"discovery_workflow.columns.{nom}",
                                 "doit être une liste de statuts (chaînes)")
        for s in statuts:
            if s in statut_vers_colonne:
                raise _refus_reglage(source, bloc, "columns", "discovery_workflow.columns",
                                     f"mappe un statut à deux colonnes (« {statut_vers_colonne[s]} » et « {nom} »)")
            statut_vers_colonne[s] = nom
    depart = bloc.get("start_column")
    if depart is not None and depart not in colonnes:
        raise _refus_reglage(source, bloc, "start_column", "discovery_workflow.start_column",
                             "n'est pas une colonne déclarée dans columns")
    passees = bloc.get("review_passed_columns", [])
    if not isinstance(passees, list) or not all(isinstance(p, str) for p in passees):
        raise _refus_reglage(source, bloc, "review_passed_columns", "discovery_workflow.review_passed_columns",
                             "doit être une liste de colonnes")
    if any(p not in colonnes for p in passees):
        raise _refus_reglage(source, bloc, "review_passed_columns", "discovery_workflow.review_passed_columns",
                             "contient une colonne qui n'est pas déclarée dans columns")
    if "validated_on" in bloc and _date(bloc["validated_on"]) is None:
        raise _refus_reglage(source, bloc, "validated_on", "discovery_workflow.validated_on", "doit être une date AAAA-MM-JJ")


def _valider_retention(bloc, source: str, lignes: dict) -> None:
    """retention : durées en jours et étiquette de sauvegarde. La durée de conservation > 365 n'est refusée qu'à l'usage
    (`retention_days`) ; l'âge maximal des fichiers ne dépasse jamais la durée de conservation."""
    bloc = _bloc_dict(bloc, source, lignes, "retention", "retention")
    for sous, valeur in bloc.items():
        chemin = f"retention.{sous}"
        if sous == "backup_label":
            if not (isinstance(valeur, str) and ETIQUETTE_SAUVEGARDE.fullmatch(valeur)):
                raise _refus_reglage(source, bloc, sous, chemin, "doit être fait de lettres minuscules et de chiffres")
        elif sous in CHAMPS_RETENTION:
            if not _entier(valeur, CHAMPS_RETENTION[sous][1]):
                raise _refus_reglage(source, bloc, sous, chemin, f"doit être un entier d'au moins {CHAMPS_RETENTION[sous][1]}")
        else:
            raise _refus_reglage(source, bloc, sous, chemin, "n'existe pas")
    # seul un âge maximal écrit est comparé : sans lui, l'âge par défaut est ramené à la durée de conservation (`retention`)
    if "max_file_age_days" in bloc and bloc["max_file_age_days"] > bloc.get("period_days", CHAMPS_RETENTION["period_days"][0]):
        raise _refus_reglage(source, bloc, "max_file_age_days", "retention.max_file_age_days",
                             "dépasse la durée de conservation (period_days)")


# --- lecteurs normalisés : reçoivent le dictionnaire rendu par to_internal (déjà validé) ---

@dataclass(frozen=True)
class Cycle:
    """Un cycle des réglages : clé neutre, version corrigée, bornes (lundi, vendredi), part de montée de version
    prévue (None si absente) et drapeau « version de base »."""
    key: str
    fix_version: str
    start: datetime.date
    end: datetime.date
    provision: float | None
    base_version: bool


def cloud_id(interne: dict) -> str | None:
    """Identifiant cloud de `jira_cloud_id` (None si absent). La forme sûre est vérifiée par l'outil Jira."""
    return interne.get("jira_cloud_id")


def token_expiry(interne: dict) -> tuple[datetime.date | None, int]:
    """(date d'échéance du jeton ou None, nombre de jours d'avertissement, 30 par défaut)."""
    return _date(interne.get("jira_token_expires")), interne.get("jira_token_warning_days", 30)


def declared_labels(interne: dict) -> dict | None:
    """Étiquettes déclarées : rôle -> {prefix, labels} ; None sans bloc. Pour up_merge, la première étiquette est le légal
    et la seconde le hotfix."""
    bloc = interne.get("declared_labels")
    if bloc is None:
        return None
    return {role: {"prefix": c["prefix"], "labels": list(c["labels"])} for role, c in bloc.items()}


def cycles(interne: dict) -> list[Cycle]:
    """Cycles triés par date de début (liste vide sans bloc)."""
    return sorted((Cycle(cle, c["fix_version"], _date(c["start"]), _date(c["end"]), c.get("up_merge_provision"),
                         bool(c.get("base_version", False))) for cle, c in (interne.get("cycles") or {}).items()),
                  key=lambda x: (x.start, x.key))


def patches(interne: dict) -> dict[str, list[str]]:
    """Versions de correctif par clé trimestrielle AAAA-Qn (dictionnaire vide sans bloc)."""
    return {cle: list(v) for cle, v in (interne.get("patches") or {}).items()}


def discovery_workflow(interne: dict) -> dict | None:
    """Correspondance statuts -> colonnes du Discovery Workflow, ou None sans bloc. `validated` est faux sans date de
    validation : rien ne doit alors être calculé sur la correspondance."""
    bloc = interne.get("discovery_workflow")
    if bloc is None:
        return None
    validee = _date(bloc.get("validated_on"))
    return {"columns": {n: list(s) for n, s in bloc["columns"].items()}, "start_column": bloc.get("start_column"),
            "review_passed_columns": list(bloc.get("review_passed_columns", [])), "validated_on": validee,
            "validated": validee is not None}


def epic_types(interne: dict) -> list[str]:
    """Types de tickets « épic » (outil des statuts d'épics) ; ["Epic"] sans réglage."""
    return [t.strip() for t in interne.get("epic_types", ["Epic"])]


def retention(interne: dict) -> dict:
    """Réglages de conservation complets, défauts appliqués."""
    bloc = interne.get("retention") or {}
    sortie = {cle: bloc.get(cle, defaut) for cle, (defaut, _) in CHAMPS_RETENTION.items()}
    sortie["backup_label"] = bloc.get("backup_label", "rgpd")
    if "max_file_age_days" not in bloc:
        sortie["max_file_age_days"] = min(sortie["max_file_age_days"], sortie["period_days"])
    return sortie


def retention_days(interne: dict) -> int:
    """Durée de conservation en jours. Lève `ErreurConfig` (sans la valeur) au-delà d'un an : à appeler avant toute
    lecture par l'export, la collecte et l'import."""
    jours = retention(interne)["period_days"]
    if jours > PERIODE_MAX_JOURS:
        raise ErreurConfig("flux.yaml : « retention.period_days » dépasse un an : réduire la durée de conservation.")
    return jours
