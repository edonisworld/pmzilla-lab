"""PMZilla Lab : sous-commandes `check-teams` et `migrate-teams` de tools/export_jira_api.py (change team-mapping, design D1, D9, D10,
D11, E1 à E4, Q5).

Aucun appel à Jira, aucun appel à l'API Assets. Lancées par l'utilisateur seul, dans le Terminal : elles refusent de démarrer dans une
session Claude Code (variable CLAUDECODE, code 3) avant de lire le moindre fichier, et des règles deny interdisent à la session de les
lancer et de lire leurs fichiers. Les fichiers lus (référentiel, catalogue, ancienne table, liste Assets complète) restent dans le
dossier de flux hors Git. La revue des équipes vues sur les tickets (database-only, D13) ne lit aucun fichier d'export : elle lit la vue
agrégée flow.v_team_tickets_seen de la base, sous le rôle en lecture seule du flux (`lire_equipes_vues`). Aucune sortie n'imprime un libellé, un nom, une clé de ticket ou une valeur de
la liste : des nombres, des identifiants, des chemins de clé avec leur ligne, les noms fixes de colonnes et de types. Seule exception :
la liste des libellés distinctifs que `migrate-teams` propose d'ajouter à la liste des noms sensibles (design D9), imprimée dans le
Terminal de l'auteur et jamais écrite dans un fichier. La règle des mots courants (un libellé dont les mots de plus de trois lettres sont
tous courants n'est pas proposé, et se compte à part) est celle de tools/sensitive_names.py, partagée avec le hook pre-commit.

Change names-and-team-review : `review-teams --add ID [ID ...]` ajoute des identifiants du catalogue, hors référentiel, à la liste de
revue `equipes-revues.yaml` (identifiants seulement, droits 600, hors Git ; tout ou rien : un identifiant inconnu refuse toute la
commande, code 1, rien n'est écrit ; aucune option de marquage global, code 2). `check-teams` la lit (lecture stricte, refus code 1) et
sépare les entrées du catalogue vues sur des tickets en « déjà revues » et « à revoir » (`split_seen_entries`), sans changer son code de
sortie ; `migrate-teams` ne la lit, ne l'écrit et ne la supprime jamais. Une ligne de cellules vides de la liste Assets est refusée.

Ce module reçoit le module export_jira_api (`ex`) : ses messages, son affichage et le dossier de flux de ses tests.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import NamedTuple

import yaml

import flow_organisation as org
import sensitive_names as sn

VARIABLE_CLAUDE_CODE = "CLAUDECODE"
LONGUEUR_MINIMALE = sn.MIN_LENGTH          # design D9 : en dessous, un libellé est en pratique un acronyme ou un mot court
COLONNES = ("id", "type", "libelle", "nom_court", "statut")
STATUTS = ("active", "draft", "inactive", "discarded")
INACTIFS = ("inactive", "discarded")
NOM_LISTE = re.compile(r"equipes-assets-complet-(\d{4}-\d{2}-\d{2})\.csv")

# mots courants et test distinctif : règle partagée du module des noms sensibles (change names-and-team-review, D2)
est_distinctif = sn.is_distinctive


class Objet(NamedTuple):
    ligne: int
    id: str
    type: str
    libelle: str
    statut: str
    nom_court_vide: bool = False       # repli sur le libellé (R-87) : le catalogue n'écrit jamais nom_court


def trier(identifiants) -> list[str]:
    """Identifiants triés par valeur numérique (le texte pour une forme non numérique)."""
    return sorted(identifiants, key=lambda i: (0, int(i), i) if i.isdigit() else (1, 0, i))


def sans_accents(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn").casefold()


# ---------------------------------------------------------------------------
# Sortie et refus
# ---------------------------------------------------------------------------

def dire(ex, cle: str, **valeurs) -> None:
    ex.hj.afficher(ex.t(cle, **valeurs))


def refuser(ex, cle: str, code: int = 1, **valeurs):
    dire(ex, cle, **valeurs)
    sys.exit(code)


def refuser_en_session(ex) -> None:
    """Refus avant toute lecture : ni référentiel, ni catalogue, ni table, ni liste."""
    if VARIABLE_CLAUDE_CODE in os.environ:
        refuser(ex, "session", 3)


def ids_ligne(ex, identifiants) -> str:
    return ex.t("list_separator").join(trier(identifiants))


# ---------------------------------------------------------------------------
# Liste Assets complète : lecture stricte (design D10, complément)
# ---------------------------------------------------------------------------

def date_du_nom(nom: str) -> dt.date | None:
    """Date du nom `equipes-assets-complet-<AAAA-MM-JJ>.csv`, ou None si le nom est autre ou la date impossible."""
    trouve = NOM_LISTE.fullmatch(nom)
    if not trouve:
        return None
    try:
        return dt.date.fromisoformat(trouve.group(1))
    except ValueError:
        return None


def liste_choisie(ex, chemin: str) -> Path:
    """Fichier nommé par l'option : un `equipes-assets-complet-<date>.csv` du dossier de flux, sinon refus (code 1)."""
    candidat = Path(chemin).expanduser()
    if (date_du_nom(candidat.name) is None or candidat.parent.resolve() != ex.hj.FLUX_DIR.resolve()
            or not candidat.is_file()):
        refuser(ex, "assets_absent")
    return candidat


def derniere_liste(ex) -> Path | None:
    """La liste du dossier de flux dont le nom porte la date la plus récente ; la date de modification n'entre jamais en compte."""
    dossier = ex.hj.FLUX_DIR
    if not dossier.is_dir():
        return None
    datees = [(date_du_nom(p.name), p) for p in dossier.iterdir() if p.is_file()]
    datees = [(d, p) for d, p in datees if d is not None]
    return max(datees, key=lambda dp: dp[0])[1] if datees else None


def lire_liste(ex, chemin: Path) -> list[Objet]:
    """Toute la liste est lue et vérifiée avant la moindre écriture. Un refus nomme une colonne fixe, une position ou un numéro de
    ligne, jamais une valeur lue ; une colonne inconnue est refusée avant qu'aucune de ses cellules soit lue."""
    try:
        texte = chemin.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        refuser(ex, "assets_unreadable")
    lecteur = csv.reader(io.StringIO(texte, newline=""))
    entete = [c.strip() for c in next(lecteur, [])]
    for position, colonne in enumerate(entete, 1):
        if colonne not in COLONNES or entete.index(colonne) != position - 1:
            refuser(ex, "assets_unknown_column", position=position)
    for colonne in COLONNES:
        if colonne not in entete:
            refuser(ex, "assets_missing_column", column=colonne)
    indices = {c: entete.index(c) for c in COLONNES}
    objets: list[Objet] = []
    vides: dict[str, list[int]] = {}      # cellules vides refusées, par colonne : comptées, jamais lues
    for ligne_brute in lecteur:
        ligne = lecteur.line_num
        if not any(c.strip() for c in ligne_brute):
            if len(ligne_brute) > 1:        # une ligne de cellules vides (des séparateurs seuls) est refusée ; une ligne sans séparateur est ignorée
                refuser(ex, "assets_empty_line", line=ligne)
            continue
        if len(ligne_brute) > len(entete):
            refuser(ex, "assets_unknown_column", position=len(entete) + 1)
        cellules = {c: (ligne_brute[i].strip() if i < len(ligne_brute) else "") for c, i in indices.items()}
        if not cellules["libelle"] and not cellules["nom_court"]:
            vides.setdefault("libelle_et_nom_court", []).append(ligne)
        for colonne in ("id", "type", "libelle", "statut"):
            if not cellules[colonne] and not (colonne == "libelle" and not cellules["nom_court"]):
                vides.setdefault(colonne, []).append(ligne)
        if any(not cellules[c] for c in ("id", "type", "libelle", "statut")):
            continue
        if not re.fullmatch(r"[0-9]+", cellules["id"]):
            refuser(ex, "assets_bad_id", line=ligne)
        if cellules["type"] not in org.TYPES_EQUIPE:
            refuser(ex, "assets_bad_type", line=ligne)
        statut = cellules["statut"].casefold()
        if statut not in STATUTS:
            refuser(ex, "assets_bad_status", line=ligne)
        objets.append(Objet(ligne, cellules["id"], cellules["type"], cellules["libelle"], statut, not cellules["nom_court"]))
    if vides:
        for colonne, lignes in vides.items():
            dire(ex, "assets_empty_both" if colonne == "libelle_et_nom_court" else "assets_empty_cell",
                 column=colonne, count=len(lignes), line=lignes[0])
        sys.exit(1)
    par_id: dict[str, list[int]] = {}
    for o in objets:
        par_id.setdefault(o.id, []).append(o.ligne)
    for lignes in par_id.values():
        if len(lignes) > 1:
            refuser(ex, "assets_duplicate_id", lines=", ".join(map(str, lignes)))
    par_libelle: dict[str, list[Objet]] = {}
    for o in objets:
        par_libelle.setdefault(o.libelle, []).append(o)
    for groupe in par_libelle.values():
        if len({o.type for o in groupe}) > 1:
            refuser(ex, "assets_label_two_types", lines=", ".join(str(o.ligne) for o in groupe))
    return objets


# ---------------------------------------------------------------------------
# migrate-teams
# ---------------------------------------------------------------------------

def cmd_migrate_teams(ex, args) -> None:
    refuser_en_session(ex)
    dossier = ex.hj.FLUX_DIR
    destination = dossier / ex.NOM_CATALOGUE
    if destination.exists():
        refuser(ex, "catalogue_present")
    objets = lire_liste(ex, liste_choisie(ex, args.liste))
    referentiel = org.charger_si_present(dossier / ex.NOM_REFERENTIEL, ex._LANGUE)
    table = ex.charger_table() if (dossier / ex.NOM_TABLE).exists() else None

    # une entrée par libellé, dans l'ordre de la liste ; aucun objet écarté
    entrees: dict[str, dict] = {}
    for o in objets:
        e = entrees.setdefault(o.libelle, {"type": o.type, "ids": [], "statuts": set()})
        e["ids"].append(o.id)
        e["statuts"].add(o.statut)
    nommes_comme = [i for nom, e in entrees.items() if referentiel is not None and nom in referentiel.teams
                    for i in e["ids"] if referentiel.team_for_jira_id(i) is None]
    obsoletes = {nom for nom, e in entrees.items() if e["statuts"] <= set(INACTIFS)}
    meles = {nom for nom, e in entrees.items() if e["statuts"] & set(INACTIFS) and e["statuts"] - set(INACTIFS)}
    ecrits = []
    for nom, e in entrees.items():
        ecrit = {"name": nom, "jira_team_ids": e["ids"], "type": e["type"]}
        if nom in obsoletes:
            ecrit["obsolete"] = True
        ecrits.append(ecrit)
    contenu = yaml.safe_dump({"teams": ecrits}, sort_keys=False, allow_unicode=True, default_flow_style=False)
    temporaire = destination.with_suffix(".tmp")
    descripteur = os.open(temporaire, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descripteur, "w", encoding="utf-8") as f:
            f.write(contenu)
        os.chmod(temporaire, 0o600)
        os.replace(temporaire, destination)
    finally:
        # Échec avant le renommage : le temporaire créé ici ne reste pas (il ferait échouer le lancement suivant, O_EXCL).
        temporaire.unlink(missing_ok=True)

    compte = {s: sum(1 for o in objets if o.statut == s) for s in STATUTS}
    dire(ex, "assets_read", total=len(objets), active=compte["active"], draft=compte["draft"], inactive=compte["inactive"],
         discarded=compte["discarded"])
    replis = [o for o in objets if o.nom_court_vide]
    if replis:
        dire(ex, "short_name_fallback", total=len(replis), **{s: sum(1 for o in replis if o.statut == s) for s in STATUTS})
    if table is not None:
        dans_liste = {o.id: o.libelle for o in objets}
        seulement_table = set(table) - set(dans_liste)
        dire(ex, "table_compared", only_table=len(seulement_table), only_list=len(set(dans_liste) - set(table)),
             different=sum(1 for i in set(table) & set(dans_liste) if table[i].strip() != dans_liste[i]))
        if seulement_table:
            dire(ex, "table_only_ids", ids=ids_ligne(ex, seulement_table))
    dire(ex, "catalogue_written", entries=len(entrees), named=len(nommes_comme))
    if nommes_comme:
        dire(ex, "named_like_ids", ids=ids_ligne(ex, nommes_comme))
    types = [e["type"] for e in entrees.values()]
    dire(ex, "types_written", development=types.count(org.TYPES_EQUIPE[0]), verification=types.count(org.TYPES_EQUIPE[1]),
         product=types.count(org.TYPES_EQUIPE[2]), other=types.count(org.TYPES_EQUIPE[3]))
    dire(ex, "written_obsolete", count=len(obsoletes))
    if obsoletes:
        dire(ex, "written_obsolete_ids", ids=ids_ligne(ex, [i for nom in obsoletes for i in entrees[nom]["ids"]]))
    dire(ex, "mixed_statuses", count=len(meles))
    if meles:
        dire(ex, "mixed_statuses_ids", ids=ids_ligne(ex, [i for nom in meles for i in entrees[nom]["ids"]]))
    propositions = [nom for nom in entrees if est_distinctif(nom)]
    dire(ex, "labels_proposed", count=len(propositions))      # le Terminal de l'auteur seulement ; rien n'est écrit dans un fichier
    for nom in propositions:
        ex.hj.afficher(nom)
    dire(ex, "labels_left_out", count=len(entrees) - len(propositions))
    dire(ex, "labels_left_out_common", count=sum(1 for nom in entrees if sn.is_common_label(nom)))      # jamais un libellé


# ---------------------------------------------------------------------------
# check-teams
# ---------------------------------------------------------------------------

def cmd_check_teams(ex, args) -> None:
    refuser_en_session(ex)
    dossier = ex.hj.FLUX_DIR
    referentiel = org.charger_si_present(dossier / ex.NOM_REFERENTIEL, ex._LANGUE)
    catalogue = org.charger_catalogue_si_present(dossier / ex.NOM_CATALOGUE, ex._LANGUE)
    revue = org.charger_revue_si_present(dossier / ex.NOM_REVUE, ex._LANGUE)        # liste de revue : refusée (code 1) si elle est illisible
    if referentiel is not None:
        org.verifier_sources(referentiel, catalogue, ex._LANGUE)
    equipes = list(referentiel.teams.values()) if referentiel is not None else []
    ids_referentiel = {i for e in equipes for i in e.jira_ids}
    obsoletes = [i for i in catalogue.ids if catalogue.est_obsolete(i)]
    table_presente = (dossier / ex.NOM_TABLE).exists()
    table = ex.charger_table() if table_presente else None

    dire(ex, "teams_consistent", referential=len(ids_referentiel), catalogue=len(catalogue.ids), obsolete=len(obsoletes))
    if table_presente:
        dire(ex, "table_deprecated")
    non_couverts = set(table or {}) - ids_referentiel - catalogue.ids
    if non_couverts:
        dire(ex, "table_not_covered", count=len(non_couverts))
        dire(ex, "table_ids_to_place", ids=ids_ligne(ex, non_couverts))

    sans_identifiant = [e for e in equipes if not e.jira_ids]
    dire(ex, "without_identifier", count=len(sans_identifiant))
    if sans_identifiant:
        dire(ex, "without_identifier_paths", paths=ex.t("list_separator").join(f"{e.chemin} (L{e.ligne})" for e in sans_identifiant))

    liste = derniere_liste(ex)
    if liste is None:
        dire(ex, "assets_none")
    else:
        dire(ex, "assets_used", file=liste.name)
        par_id = {o.id: o for o in lire_liste(ex, liste)}
        absents = ids_referentiel - set(par_id)
        dire(ex, "absent_from_assets", count=len(absents))
        if absents:
            dire(ex, "absent_from_assets_ids", ids=ids_ligne(ex, absents))
        inactives = [(e, [i for i in e.jira_ids if i in par_id and par_id[i].statut in INACTIFS]) for e in equipes]
        inactives = [(e, ids) for e, ids in inactives if ids]
        dire(ex, "inactive_in_assets", count=len(inactives))
        if inactives:
            dire(ex, "inactive_in_assets_ids", ids=ids_ligne(ex, [i for _, ids in inactives for i in ids]))
        changes = [i for entree in catalogue.entrees if entree.type for i in entree.jira_ids
                   if i in par_id and par_id[i].type != entree.type]
        dire(ex, "types_changed", count=len(changes))
        if changes:
            dire(ex, "types_changed_ids", ids=ids_ligne(ex, changes))

    # types lus du catalogue (avec ou sans liste)
    differents = [e for e in equipes if org.types_differents(e, catalogue)]
    dire(ex, "different_types", count=len(differents))
    if differents:
        dire(ex, "different_types_ids", ids=ids_ligne(ex, [i for e in differents for i in e.jira_ids]))
    forces = [e for e in equipes if e.type]
    dire(ex, "forced_listed", count=len(forces))
    for e in forces:
        deduit = org.type_deduit(e, catalogue)
        assets = deduit or ex.t("assets_type_different" if org.types_differents(e, catalogue) else "assets_type_none")
        dire(ex, "forced_line", path=f"{e.chemin_type} (L{e.ligne_type})", forced=e.type, assets=assets)
    divergents = [e for e in forces if org.type_deduit(e, catalogue) and org.type_deduit(e, catalogue) != e.type]
    dire(ex, "forced_differs", count=len(divergents))
    if divergents:
        dire(ex, "forced_differs_ids", ids=ids_ligne(ex, [i for e in divergents for i in e.jira_ids]))
    inutiles = [e for e in forces if org.type_deduit(e, catalogue) == e.type]
    dire(ex, "forced_not_needed", count=len(inutiles))
    if inutiles:
        dire(ex, "forced_not_needed_paths", paths=ex.t("list_separator").join(f"{e.chemin_type} (L{e.ligne_type})" for e in inutiles))

    signaler_entrees_vues(ex, referentiel, catalogue, revue)
    if non_couverts:
        sys.exit(4)


# ---------------------------------------------------------------------------
# extract-teams (change team-names-readable, design D4, D10)
# ---------------------------------------------------------------------------

NOM_EXTRAIT = "equipes-lisibles.yaml"


class ExtraitNoms(NamedTuple):
    """Ce que l'extrait contient, et rien d'autre : jamais d'effectif, de site, de département, de Mission Team ni de commentaire."""
    referential_teams: list[dict]
    catalogue_teams: list[dict]
    extracted_on: dt.date


def extrait_des_noms(referentiel, catalogue, date: dt.date | None = None) -> ExtraitNoms:
    """Choisit les champs au niveau de l'équipe (décision a) dans le référentiel et le catalogue déjà lus par les lecteurs stricts ;
    `referentiel` vaut None quand le fichier est absent. Les listes sont vides pour une source absente."""
    equipes = list(referentiel.teams.values()) if referentiel is not None else []
    cat = catalogue if catalogue is not None else org.Catalogue()
    du_referentiel = [{"name": e.nom, "jira_team_ids": list(e.jira_ids), "without_identifier": not e.jira_ids,
                       "type": org.type_effectif(e, cat)} for e in equipes]
    du_catalogue = [{"name": c.nom, "jira_team_ids": list(c.jira_ids), "type": c.type, "obsolete": c.obsolete,
                     "outside_referential": referentiel is None or not any(referentiel.team_for_jira_id(i) for i in c.jira_ids)}
                    for c in cat.entrees]
    return ExtraitNoms(du_referentiel, du_catalogue, date or dt.date.today())


def cmd_extract_teams(ex, args) -> None:
    """Écrit Flux-Lab/equipes-lisibles.yaml (atomique, droits 600). Refus en session avant toute lecture ; un refus d'un lecteur
    strict ou aucune source : code 1 et rien n'est écrit. La console ne montre que des nombres."""
    refuser_en_session(ex)
    dossier = ex.hj.FLUX_DIR
    chemin_ref, chemin_cat = dossier / ex.NOM_REFERENTIEL, dossier / ex.NOM_CATALOGUE
    if not chemin_ref.is_file() and not chemin_cat.is_file():
        refuser(ex, "extract_no_source")
    referentiel = org.charger_si_present(chemin_ref, ex._LANGUE)
    catalogue = org.charger_catalogue_si_present(chemin_cat, ex._LANGUE)
    if referentiel is not None:
        org.verifier_sources(referentiel, catalogue, ex._LANGUE)
    extrait = extrait_des_noms(referentiel, catalogue)
    contenu = yaml.safe_dump({"extracted_on": extrait.extracted_on.isoformat(), "referential_teams": extrait.referential_teams,
                              "catalogue_teams": extrait.catalogue_teams}, sort_keys=False, allow_unicode=True,
                             default_flow_style=False)
    destination = dossier / NOM_EXTRAIT
    temporaire = destination.with_name(destination.name + ".tmp")
    try:
        descripteur = os.open(temporaire, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descripteur, "w", encoding="utf-8") as f:
            f.write(contenu)
        os.chmod(temporaire, 0o600)
        os.replace(temporaire, destination)
    except OSError as erreur:
        refuser(ex, "extract_not_written", error=type(erreur).__name__)          # le nom du type, jamais le message
    finally:
        temporaire.unlink(missing_ok=True)
    dire(ex, "extract_written", referential=len(extrait.referential_teams),
         without=sum(1 for e in extrait.referential_teams if e["without_identifier"]), catalogue=len(extrait.catalogue_teams))


class EquipesVuesInjoignables(Exception):
    """La base, son mot de passe ou le rôle en lecture seule sont inutilisables : la revue du catalogue est sautée. Aucun détail."""


# La seule lecture de la revue du catalogue (database-only, D13) : la vue agrégée par équipe, lisible par le rôle en lecture seule du
# flux et par lui seul. Aucune table des tickets ni des équipes par ticket, aucune table brute ; aucun masquage (la sortie de check-teams
# ne montre à l'auteur que des décomptes et des identifiants d'équipe).
REQUETE_EQUIPES_VUES = "SELECT team_name, tickets FROM flow.v_team_tickets_seen"


def lire_equipes_vues(ouvrir=None) -> dict[str, int]:
    """Nombre de tickets stockés, sans instant de sortie de l'export, par nom d'équipe (la vue flow.v_team_tickets_seen), sous le rôle
    en lecture seule, connecté comme les lecteurs des rapports (flow_store.ouvrir). Ne lit aucun fichier et n'écrit rien. Lève
    EquipesVuesInjoignables si la base ne répond pas, sans détail. `ouvrir` : fabrique de connexion, pour les tests."""
    try:
        if ouvrir is None:
            import flow_store
            ouvrir = flow_store.ouvrir
        connexion = ouvrir()
    except Exception:
        raise EquipesVuesInjoignables() from None
    try:
        return {nom: int(n) for nom, n in connexion.execute(REQUETE_EQUIPES_VUES).fetchall()}
    except Exception:
        raise EquipesVuesInjoignables() from None
    finally:
        connexion.close()


def entrees_candidates(referentiel, catalogue) -> dict[str, list[str]]:
    """Entrées non obsolètes du catalogue qui portent au moins un identifiant hors référentiel : libellé -> ces identifiants."""
    candidates = {}
    for entree in catalogue.entrees:
        hors = [i for i in entree.jira_ids if referentiel is None or referentiel.team_for_jira_id(i) is None]
        if hors and not entree.obsolete:
            candidates[entree.nom] = hors
    return candidates


def revue_des_entrees_vues(vues: dict[str, int], candidates: dict[str, list[str]], review_list) -> tuple[list, dict, int]:
    """Calcul de la revue, sans mise en forme (design D13) : (entrées déjà revues, entrées nouvelles -> leurs identifiants à revoir,
    nombre de tickets des entrées nouvelles). Une entrée est vue quand son libellé est le nom d'une équipe de la vue ; le nombre est la
    somme des décomptes de la vue des entrées nouvelles (un ticket qui porte deux entrées à revoir compte deux fois : décision de l'auteur du
    2026-10-18, la phrase dit « tickets comptés par entrée »). Un décompte inférieur à 5 est utilisé tel quel : la vue n'est pas masquée."""
    vus = {nom: ids for nom, ids in candidates.items() if nom in vues}
    revues, nouvelles = split_seen_entries(vus, review_list)
    return revues, nouvelles, sum(vues[nom] for nom in nouvelles)


def signaler_entrees_vues(ex, referentiel, catalogue, revue=()) -> None:
    """Revue (design D1, D13) : entrées non obsolètes du catalogue qui portent un identifiant hors référentiel et dont le libellé est le
    nom d'une équipe vue sur des tickets stockés (la vue agrégée de la base), séparées en déjà revues et nouvelles par la liste de revue
    (names-and-team-review, D5). Aucun fichier d'export n'est lu ; le code de sortie n'est jamais changé."""
    try:
        vues = lire_equipes_vues()
    except EquipesVuesInjoignables:
        dire(ex, "review_unreachable")
        return
    if not vues:
        dire(ex, "review_no_ticket")
        return
    candidates = entrees_candidates(referentiel, catalogue)
    revues, nouvelles, tickets = revue_des_entrees_vues(vues, candidates, revue)
    if revues or nouvelles:
        dire(ex, "review_seen", entries=len(nouvelles), tickets=tickets)
        dire(ex, "review_reviewed", entries=len(revues))
        if nouvelles:
            dire(ex, "review_ids", ids=ids_ligne(ex, [i for ids in nouvelles.values() for i in ids]))


def split_seen_entries(seen: dict, review_list) -> tuple[list, dict]:
    """Sépare les entrées vues (entrée -> ses identifiants hors référentiel) selon la liste de revue (design D5) : (entrées déjà revues,
    entrées nouvelles -> leurs seuls identifiants absents de la liste). Une entrée est déjà revue quand tous ses identifiants y sont."""
    revus = set(review_list)
    deja, nouvelles = [], {}
    for nom, ids in seen.items():
        manquants = [i for i in ids if i not in revus]
        if manquants:
            nouvelles[nom] = manquants
        else:
            deja.append(nom)
    return deja, nouvelles


# ---------------------------------------------------------------------------
# review-teams (change names-and-team-review, design D6)
# ---------------------------------------------------------------------------

def cmd_review_teams(ex, args) -> None:
    """Ajoute des identifiants du catalogue, hors référentiel, à la liste de revue. Tout ou rien : un seul identifiant refusé et rien
    n'est écrit. Jamais un libellé dans la sortie."""
    refuser_en_session(ex)
    dossier = ex.hj.FLUX_DIR
    referentiel = org.charger_si_present(dossier / ex.NOM_REFERENTIEL, ex._LANGUE)
    catalogue = org.charger_catalogue_si_present(dossier / ex.NOM_CATALOGUE, ex._LANGUE)
    destination = dossier / ex.NOM_REVUE
    existants = org.charger_revue_si_present(destination, ex._LANGUE)
    demandes = list(dict.fromkeys(args.ajouter))
    exterieurs = {i for i in catalogue.ids if referentiel is None or referentiel.team_for_jira_id(i) is None}
    inconnus = [i for i in demandes if i not in exterieurs]
    if inconnus:
        refuser(ex, "review_unknown", ids=ids_ligne(ex, inconnus))
    ajoutes = [i for i in demandes if i not in existants]
    if ajoutes:
        contenu = yaml.safe_dump({"reviewed_ids": trier(set(existants) | set(ajoutes))}, sort_keys=False, default_flow_style=False)
        temporaire = destination.with_name(destination.name + ".tmp")
        descripteur = os.open(temporaire, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(descripteur, "w", encoding="utf-8") as f:
                f.write(contenu)
            os.chmod(temporaire, 0o600)
            os.replace(temporaire, destination)
        finally:
            temporaire.unlink(missing_ok=True)
    dire(ex, "review_added", count=len(ajoutes))
    if len(demandes) > len(ajoutes):
        dire(ex, "review_already", count=len(demandes) - len(ajoutes))
