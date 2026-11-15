"""
PMZilla Lab : règles pures des champs de livraison de Jira (change jira-delivery-fields, design D1, D2, D5, D7, D11, D13).

Module de bibliothèque, sans ligne de commande, sans accès à la base ni au réseau. Il porte :
  - la liste fermée des champs de livraison (D1) et leur réduction à la forme stockée : un sprint en identifiant, état et dates (jamais
    son nom, son but ni son tableau), un champ d'actifs en identifiants d'objet seuls, un champ d'option en identifiant d'option seul
    (R-20261102-51 : jamais le libellé), un engagement en oui/non (R-20261102-50 : présence seulement), la phase de détection d'un défaut en
    code fermé (production, piloting, other) ; aucune valeur ne sort d'ici vers une sortie ;
  - la lecture des colonnes `from` et `to` du changelog (D2) : liste entre crochets `uuid:objectId` des versions visée et livrée et des versions d'épic (R-20261102-61) (aucun repli),
    identifiants de sprint ;
  - la jointure des tickets de version par objet d'actif (D5) ;
  - la règle de glissement (D7) `slips`, le flux d'une épic sur ses propres transitions (D11) `epic_flow_source` et les comptes d'échec de
    changement par version de détection (D13) `change_failure_counts`.
Les lecteurs appellent ces fonctions et ne recomptent jamais dans leur mise en forme.

Table des identifiants (R-20261114-108, même logique que A-92) : le code ne porte AUCUN identifiant réel ; la table vient du bloc `delivery_fields` de
Flux-Lab/flux.yaml (hors Git), posée par `configurer`. Sans table, l'état est neutre : aucun champ n'est demandé, lu ni stocké.

Règle (D1) : le filtre des noms sensibles ne s'applique plus qu'au nom court d'une version, seule valeur de texte encore stockée
(R-20261102-51 : plus aucune valeur d'option n'est stockée). Remplace : son usage sur les valeurs d'option. Retrait : permanent tant que le
nom court est stocké.
"""
from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal, InvalidOperation

import flux_config          # noms des champs : schéma unique DELIVERY_FIELDS_* (R-20261114-108)

# ---------------------------------------------------------------------------------------------------------------------------------
# D1. Liste fermée des champs de livraison
# ---------------------------------------------------------------------------------------------------------------------------------

# Table des champs : NEUTRE par défaut (R-20261114-108, même logique que A-92). Aucun identifiant réel dans le code publié : la table
# vient du bloc `delivery_fields` de Flux-Lab/flux.yaml (hors Git), posée par `configurer` ; les noms des champs viennent du schéma
# unique `flux_config.DELIVERY_FIELDS_*`. Sans table, aucun champ n'est demandé, lu ni stocké (l'export et la collecte le disent).
# Remplace : les identifiants `customfield_…` réels écrits ici. Retrait : permanent (aucune donnée de l'organisation dans l'arbre public).
CHAMP_SPRINT: str | None = None
CHAMPS_ACTIFS: dict[str, str] = {}
CHAMPS_ACTIFS_DEFAUT: dict[str, str] = {}      # défauts seulement (R-20261102-33)
CHAMPS_OPTIONS_MULTIPLES: dict[str, str] = {}
CHAMPS_OPTIONS_UNIQUES: dict[str, str] = {}
CHAMP_RANG: str | None = None
CHAMPS_INDICATEURS: dict[str, str] = {}
CHAMPS_OPTIONS_DEFAUT: dict[str, str] = {}
GENRES_VERSION_EPIC = ("epic_a", "epic_b")

# D2 : champs dont le changelog est collecté. Les deux champs de version des épics y sont, lus comme ceux des stories (même motif, même
# comptage des éléments écartés) : le relevé 1.1 v2 a confirmé leur forme, leur type et leurs comptes (R-20261102-61, qui remplace la
# suspension de R-20261102-55 (2a)) ; les champs des seuls défauts n'y sont jamais (R-20261102-33).
ACTIFS_HISTORISES: dict[str, str] = {}
GENRE_DE_CHAMP: dict[str, str] = {}


def _groupe(table: dict, nom: str) -> dict[str, str]:
    """Les champs déclarés d'un groupe de la table, dans l'ordre du schéma ; un nom hors schéma ou une valeur vide est ignoré."""
    bloc = table.get(nom)
    bloc = bloc if isinstance(bloc, dict) else {}
    return {genre: bloc[genre].strip() for genre in flux_config.DELIVERY_FIELDS_GROUPES[nom]
            if isinstance(bloc.get(genre), str) and bloc[genre].strip()}


def _scalaire(table: dict, nom: str) -> str | None:
    valeur = table.get(nom)
    return valeur.strip() if isinstance(valeur, str) and valeur.strip() else None


def configurer(table: dict | None) -> bool:
    """Pose la table des champs de livraison lue de `delivery_fields` de flux.yaml (déjà validée par flux_config) ; `None` ou `{}` revient
    à l'état NEUTRE (aucun champ). Rend True si au moins un champ est déclaré. L'export et la collecte l'appellent avec leurs réglages
    avant tout appel à Jira ; les tests l'appellent avec la table factice."""
    global CHAMP_SPRINT, CHAMPS_ACTIFS, CHAMPS_ACTIFS_DEFAUT, CHAMPS_OPTIONS_MULTIPLES, CHAMPS_OPTIONS_UNIQUES, CHAMP_RANG
    global CHAMPS_INDICATEURS, CHAMPS_OPTIONS_DEFAUT, ACTIFS_HISTORISES, GENRE_DE_CHAMP
    global CHAMP_VERSION_ACTIF, CHAMP_VERSION_RELEASED, CHAMP_VERSION_STARTED, CHAMP_VERSION_NOM_COURT
    table = table if isinstance(table, dict) else {}
    CHAMP_SPRINT = _scalaire(table, "sprint")
    CHAMP_RANG = _scalaire(table, "rank")
    CHAMPS_ACTIFS = _groupe(table, "assets")
    CHAMPS_ACTIFS_DEFAUT = _groupe(table, "defect_assets")
    CHAMPS_OPTIONS_MULTIPLES = _groupe(table, "multi_options")
    CHAMPS_OPTIONS_UNIQUES = _groupe(table, "single_options")
    CHAMPS_INDICATEURS = _groupe(table, "flags")
    CHAMPS_OPTIONS_DEFAUT = _groupe(table, "defect_options")
    ACTIFS_HISTORISES = {genre: CHAMPS_ACTIFS[genre] for genre in ("target", "resolution") + GENRES_VERSION_EPIC if genre in CHAMPS_ACTIFS}
    GENRE_DE_CHAMP = {identifiant: genre for genre, identifiant in ACTIFS_HISTORISES.items()}
    version = _groupe(table, "version_tickets")
    CHAMP_VERSION_ACTIF = version.get("asset")
    CHAMP_VERSION_RELEASED = version.get("released")
    CHAMP_VERSION_STARTED = version.get("started")
    CHAMP_VERSION_NOM_COURT = version.get("short_name")
    return table_configuree()


def table_configuree() -> bool:
    """Au moins un champ de livraison est déclaré (champ d'une story, d'un défaut ou d'un ticket de version)."""
    return bool(champs_demandes() or champs_versions_declares())


def versions_configurees() -> bool:
    """L'objet d'actif des tickets de version est déclaré : sans lui, la jointure par objet (D5) n'a pas de clé et la recherche des
    versions n'est pas lancée."""
    return CHAMP_VERSION_ACTIF is not None


def champs_historises() -> list[str]:
    """Identifiants ajoutés à `fieldIds` de la requête groupée du changelog (D2) : sprint, versions visée et livrée, et les versions d'épic
    déclarées historisées. Jamais un champ propre aux défauts. Vide sans table."""
    return ([CHAMP_SPRINT] if CHAMP_SPRINT else []) + list(ACTIFS_HISTORISES.values())


def champs_demandes() -> list[str]:
    """La liste fermée des champs de livraison demandés à Jira dans la recherche des tickets (D1) : aucun champ de personne, de texte libre,
    de temps passé, d'estimation en heures ni de pièce jointe."""
    ids = [i for i in (CHAMP_SPRINT, CHAMP_RANG) if i]
    for groupe in (CHAMPS_ACTIFS, CHAMPS_ACTIFS_DEFAUT, CHAMPS_OPTIONS_MULTIPLES, CHAMPS_OPTIONS_UNIQUES, CHAMPS_INDICATEURS,
                   CHAMPS_OPTIONS_DEFAUT):
        ids += list(groupe.values())
    return ids


# ---------------------------------------------------------------------------------------------------------------------------------
# Filtre des noms sensibles sur le nom court de version (D1)
# ---------------------------------------------------------------------------------------------------------------------------------

MARQUEUR = "[nom sensible]"          # remplace un nom court de version qui tient un nom de la liste


class FiltreOptions:
    """Passe chaque nom court de version par la règle partagée de tools/sensitive_names.py : une valeur qui tient un nom de la liste est remplacée
    par le marqueur du module ; le nombre de remplacements est compté (plus aucune valeur d'option n'est stockée : R-20261102-51). La liste est chargée au premier appel de
    `charger()`, que l'export fait avant le premier appel à Jira, sinon à la première valeur rencontrée. Le paramètre `charger` du
    constructeur rend la liste des noms (lève SensitiveNamesUnavailable si elle manque)."""

    def __init__(self, charger=None):
        self._charger = charger
        self._motifs = None
        self.remplacees = 0

    def charger(self) -> None:
        """Charge la liste des noms (lève SensitiveNamesUnavailable si elle manque). L'export l'appelle AVANT le premier appel à Jira
        (R-20261102-41, Q326). Garde neuve ; remplace : rien ; retrait : permanent tant qu'un nom court de version est stocké."""
        import sensitive_names
        if self._motifs is None:
            noms = self._charger() if self._charger is not None else sensitive_names.load_judged_names()
            self._motifs = sensitive_names.patterns(noms)

    def valeur(self, texte: str) -> str:
        import sensitive_names
        self.charger()
        if sensitive_names.line_matches(self._motifs, texte):
            self.remplacees += 1
            return MARQUEUR
        return texte


# ---------------------------------------------------------------------------------------------------------------------------------
# Réduction des valeurs de champ à leur forme stockée (D1)
# ---------------------------------------------------------------------------------------------------------------------------------

def rempli(valeur) -> bool:
    """Oui/non d'un engagement ou de l'objectif stratégique : présence seulement (R-20261102-50), jamais le contenu ni une valeur d'option :
    toute option vaut oui, le vide vaut non. Un booléen vaut sa valeur ; un nombre est rempli ; un texte, une liste, un objet ou un document
    sans contenu ne l'est pas."""
    if valeur is None:
        return False
    if isinstance(valeur, bool):
        return valeur
    if isinstance(valeur, str):
        return bool(valeur.strip())
    if isinstance(valeur, (list, tuple)):
        return any(rempli(v) for v in valeur)
    if isinstance(valeur, dict):
        if valeur.get("type") == "doc":
            return bool(valeur.get("content"))
        return any(rempli(v) for v in valeur.values())
    return True


def sprints(valeur) -> list[dict]:
    """Sprints d'un ticket : identifiant Jira, état et dates seulement (Q295). Jamais `name`, `goal` ni `boardId`."""
    sortie: list[dict] = []
    vus: set[str] = set()
    for element in valeur if isinstance(valeur, list) else []:
        if not isinstance(element, dict) or isinstance(element.get("id"), bool) or not isinstance(element.get("id"), (int, str)):
            continue
        identifiant = str(element["id"]).strip()
        if not identifiant or identifiant in vus:
            continue
        vus.add(identifiant)
        sortie.append({"id": identifiant, "state": element.get("state") if isinstance(element.get("state"), str) else None,
                       "start": _texte_date(element.get("startDate")), "end": _texte_date(element.get("endDate")),
                       "complete": _texte_date(element.get("completeDate"))})
    return sortie


def _texte_date(valeur) -> str | None:
    return valeur.strip() if isinstance(valeur, str) and valeur.strip() else None


def objets_d_actifs(valeur) -> list[str]:
    """Identifiants d'objet d'un champ d'actifs (`objectId`), dans l'ordre et sans doublon. `id` et `workspaceId` sont écartés, ainsi que
    tout libellé de l'objet."""
    sortie: list[str] = []
    for element in valeur if isinstance(valeur, list) else []:
        identifiant = element.get("objectId") if isinstance(element, dict) else None
        if isinstance(identifiant, (int, str)) and not isinstance(identifiant, bool) and str(identifiant).strip():
            if str(identifiant).strip() not in sortie:
                sortie.append(str(identifiant).strip())
    return sortie


def _identifiant_d_option(element) -> str | None:
    """L'identifiant d'une option Jira (R-20261102-51) : jamais son libellé. Une option sans identifiant n'est pas gardée."""
    identifiant = element.get("id") if isinstance(element, dict) else None
    if isinstance(identifiant, bool) or not isinstance(identifiant, (int, str)) or not str(identifiant).strip():
        return None
    return str(identifiant).strip()


def options(valeur) -> list[str]:
    """Identifiants d'option d'un champ à valeurs multiples, dans l'ordre. Une valeur est un objet d'option ou une liste d'objets."""
    elements = valeur if isinstance(valeur, list) else [valeur]
    return [i for i in (_identifiant_d_option(e) for e in elements) if i is not None]


def option_unique(valeur) -> str | None:
    """L'identifiant de la première option d'un champ à valeur unique (ou du premier élément si le champ rend une liste)."""
    trouvees = options(valeur)
    return trouvees[0] if trouvees else None


PHASES_RECONNUES = {"Production": "production", "Piloting": "piloting"}          # liste fermée (D13, R-20261102-35) : libellé reconnu -> code


def phase_de_detection(valeur) -> dict | None:
    """Phase de détection d'un défaut : {"id": identifiant d'option, "code": production | piloting | other}. Le libellé est comparé, sans
    être stocké, aux deux libellés reconnus « Production » et « Piloting » (comparaison exacte, bords retirés) ; tout autre libellé, vide
    compris, donne `other`. Aucune valeur libre n'est gardée (R-20261102-51). Sans option : None."""
    element = valeur[0] if isinstance(valeur, list) and valeur else valeur
    if not isinstance(element, dict):
        return None
    libelle = element.get("value") if isinstance(element.get("value"), str) else element.get("name")
    code = PHASES_RECONNUES.get(libelle.strip()) if isinstance(libelle, str) else None
    identifiant = _identifiant_d_option(element)
    if identifiant is None and not isinstance(libelle, str):
        return None
    return {"id": identifiant, "code": code or "other"}


def rang(valeur) -> str | None:
    """Rang de portefeuille : un nombre, gardé en texte décimal. Toute autre forme : rien."""
    if isinstance(valeur, bool) or valeur is None:
        return None
    try:
        nombre = Decimal(str(valeur).strip())
    except InvalidOperation:
        return None
    return format(nombre.normalize(), "f") if nombre.is_finite() else None


def livraison_de(champs: dict, type_du_ticket: str, types_defauts) -> dict | None:
    """Forme stockée des champs de livraison d'un ticket (D1) : le dictionnaire de la partie `delivery` de l'instantané, sans clé vide, ou None
    quand aucun champ n'est rempli (la clé `delivery` est alors absente et l'empreinte du ticket inchangée). Les champs des défauts ne sont
    gardés que pour un ticket dont le type est parmi `types_defauts` (R-20261102-33, -35) ; ailleurs ils sont écartés."""
    champs = champs or {}
    defaut = type_du_ticket.strip().casefold() in {t.strip().casefold() for t in types_defauts or ()}
    livraison: dict = {}
    liste = sprints(champs.get(CHAMP_SPRINT)) if CHAMP_SPRINT else []
    if liste:
        livraison["sprints"] = liste
    actifs = {genre: objets_d_actifs(champs.get(identifiant)) for genre, identifiant in CHAMPS_ACTIFS.items()}
    if defaut:
        actifs.update({genre: objets_d_actifs(champs.get(identifiant)) for genre, identifiant in CHAMPS_ACTIFS_DEFAUT.items()})
    actifs = {genre: ids for genre, ids in actifs.items() if ids}
    if actifs:
        livraison["assets"] = actifs
    multiples = {genre: options(champs.get(identifiant)) for genre, identifiant in CHAMPS_OPTIONS_MULTIPLES.items()}
    multiples = {genre: liste_ for genre, liste_ in multiples.items() if liste_}
    if multiples:
        livraison["options"] = multiples
    uniques = {genre: option_unique(champs.get(identifiant))
               for genre, identifiant in CHAMPS_OPTIONS_UNIQUES.items()}
    uniques = {genre: valeur for genre, valeur in uniques.items() if valeur}
    if uniques:
        livraison["single"] = uniques
    nombre = rang(champs.get(CHAMP_RANG)) if CHAMP_RANG else None
    if nombre is not None:
        livraison["rank"] = nombre
    indicateurs = {genre: rempli(champs.get(identifiant)) for genre, identifiant in CHAMPS_INDICATEURS.items()}
    if any(indicateurs.values()):
        livraison["flags"] = indicateurs
    if defaut:
        options_defaut = {}
        if "detection_phase" in CHAMPS_OPTIONS_DEFAUT:
            options_defaut["detection_phase"] = phase_de_detection(champs.get(CHAMPS_OPTIONS_DEFAUT["detection_phase"]))
        for genre in ("detected_by", "installed_base"):          # identifiant d'option seulement (R-20261102-51)
            if genre in CHAMPS_OPTIONS_DEFAUT:
                identifiant = option_unique(champs.get(CHAMPS_OPTIONS_DEFAUT[genre]))
                options_defaut[genre] = {"id": identifiant} if identifiant is not None else None
        options_defaut = {genre: o for genre, o in options_defaut.items() if o}
        if options_defaut:
            livraison["defect"] = options_defaut
    return livraison or None


# ---------------------------------------------------------------------------------------------------------------------------------
# D2. Événements du changelog, lus dans les colonnes `from` et `to` seulement
# ---------------------------------------------------------------------------------------------------------------------------------

MOTIF_ELEMENT_ACTIF = re.compile(r"^[0-9a-fA-F-]{36}:\d+$", re.ASCII)
MOTIF_SPRINT = re.compile(r"^\d+$", re.ASCII)


def _colonne_vide(texte) -> bool:
    return texte is None or (isinstance(texte, str) and not texte.strip())


def identifiants_d_actifs(texte) -> tuple[set[str], set[str]]:
    """(identifiants d'objet, éléments illisibles) d'une colonne `from` ou `to` d'un champ d'actifs : la liste entre crochets
    `[uuid:objectId, uuid:objectId]` (R-20261102-34, format établi, aucun repli). Sans crochets, virgules ni espaces de bord ; chaque élément
    doit correspondre au motif `^[0-9a-fA-F-]{36}:\\d+$` ; l'identifiant d'objet est la partie après les deux-points. Une colonne vide ou
    absente est l'ensemble vide."""
    if _colonne_vide(texte) or not isinstance(texte, str):
        return set(), set()
    identifiants, illisibles = set(), set()
    corps = texte.strip()
    if corps.startswith("["):          # seuls le « [ » de tête et le « ] » de fin sont retirés ; un crochet intérieur rend l'élément illisible
        corps = corps[1:]
    if corps.endswith("]"):
        corps = corps[:-1]
    for element in corps.split(","):
        element = element.strip()
        if not element:
            continue
        if MOTIF_ELEMENT_ACTIF.fullmatch(element):
            identifiants.add(element.rsplit(":", 1)[1])
        else:
            illisibles.add(element)
    return identifiants, illisibles


def evenements_actifs(avant, apres) -> tuple[set[str], set[str], int]:
    """(ajoutés, retirés, nombre d'éléments illisibles) d'un changement d'un champ d'actifs : différences d'ensembles entre `from` et `to`. Un
    élément hors motif n'est pas gardé ; le reste du changement l'est. Le nombre compte les éléments distincts du changement."""
    a, ill_a = identifiants_d_actifs(avant)
    b, ill_b = identifiants_d_actifs(apres)
    return b - a, a - b, len(ill_a | ill_b)


def identifiants_de_sprints(texte) -> set[str]:
    """Identifiants de sprint d'une colonne `from` ou `to` (nombres séparés par des virgules) ; tout autre élément est écarté."""
    if _colonne_vide(texte) or not isinstance(texte, str):
        return set()
    return {e.strip() for e in texte.split(",") if MOTIF_SPRINT.fullmatch(e.strip())}


def evenements_sprint(avant, apres) -> tuple[set[str], set[str]]:
    """(ajoutés, retirés) d'un changement de sprint, depuis les colonnes d'identifiants seules (jamais `fromString` ni `toString`)."""
    a, b = identifiants_de_sprints(avant), identifiants_de_sprints(apres)
    return b - a, a - b


def courantes_de(champs: dict) -> dict:
    """Valeurs courantes des champs historisés d'un ticket, lues dans la réponse d'une recherche : {"sprints": [identifiants]} et {"actifs":
    {genre: [identifiants d'objet]}}. Une clé absente de la réponse reste absente (valeur inconnue, non un champ vide) : les périodes du
    champ ne sont alors pas reconstruites. Jamais un nom ni un libellé."""
    sortie: dict = {}
    if CHAMP_SPRINT and CHAMP_SPRINT in champs:
        sortie["sprints"] = [s["id"] for s in sprints(champs[CHAMP_SPRINT])]
    actifs = {genre: objets_d_actifs(champs[identifiant]) for genre, identifiant in ACTIFS_HISTORISES.items() if identifiant in champs}
    if actifs:
        sortie["actifs"] = actifs
    return sortie


def evenements_de_livraison(historiques: list[dict]) -> tuple[list[list], list[list], int]:
    """(événements de sprint, événements d'actifs, éléments illisibles) d'un historique. Un événement de sprint : [date, "add"|"remove",
    identifiant] ; un événement d'actifs : [date, "add"|"remove", "genre:identifiant d'objet"] (même forme à trois éléments que les
    événements de version, pour construire les périodes de la même façon). Seuls les champs historisés (D2) sont lus, par leur
    identifiant de champ ; les colonnes `fromString` et `toString` ne sont jamais lues. Les listes ne sont pas triées ici."""
    sprints_, actifs, illisibles = [], [], 0
    for historique in historiques or []:
        date = historique.get("created")
        for element in historique.get("items") or []:
            champ = element.get("fieldId")
            if CHAMP_SPRINT and champ == CHAMP_SPRINT:
                ajoutes, retires = evenements_sprint(element.get("from"), element.get("to"))
                sprints_ += [[date, "remove", i] for i in sorted(retires)] + [[date, "add", i] for i in sorted(ajoutes)]
            elif champ in GENRE_DE_CHAMP:
                genre = GENRE_DE_CHAMP[champ]
                ajoutes, retires, ill = evenements_actifs(element.get("from"), element.get("to"))
                illisibles += ill
                actifs += [[date, "remove", f"{genre}:{i}"] for i in sorted(retires)] + [[date, "add", f"{genre}:{i}"] for i in sorted(ajoutes)]
    return sprints_, actifs, illisibles


# ---------------------------------------------------------------------------------------------------------------------------------
# D5. Jointure des tickets de version par objet d'actif
# ---------------------------------------------------------------------------------------------------------------------------------

# Champs des tickets de version : neutres par défaut, posés par `configurer` (groupe `version_tickets` de la table).
CHAMP_VERSION_ACTIF: str | None = None          # l'objet d'actif d'un ticket de version : égal à l'objet de la version visée ou livrée d'une story
CHAMP_VERSION_RELEASED: str | None = None
CHAMP_VERSION_STARTED: str | None = None
CHAMP_VERSION_NOM_COURT: str | None = None


def champs_versions_declares() -> list[str]:
    """Les identifiants déclarés des champs de ticket de version (l'actif, Released, Started, le nom court), dans cet ordre."""
    return [i for i in (CHAMP_VERSION_ACTIF, CHAMP_VERSION_RELEASED, CHAMP_VERSION_STARTED, CHAMP_VERSION_NOM_COURT) if i]


def champs_versions() -> list[str]:
    """Les seuls champs demandés par la recherche des tickets de version (D4) : type, état, l'actif, Released, Started et le nom court
    (ceux que la table déclare). Ni résumé, ni personne, ni champ de texte."""
    return ["issuetype", "status"] + champs_versions_declares()


def version_de_ticket(champs: dict, filtre: "FiltreOptions | None" = None) -> dict:
    """Un ticket de version réduit à ce que la jointure lit : les objets d'actif, le nom court, l'état et sa catégorie, Started, Released.
    La clé et le résumé du ticket ne passent jamais ici. Le nom court passe par le filtre des noms sensibles ; les options ne sont plus stockées que par identifiant."""
    statut = champs.get("status") if isinstance(champs.get("status"), dict) else {}
    court = champs.get(CHAMP_VERSION_NOM_COURT)
    if isinstance(court, dict):
        court = court.get("value")
    if filtre is not None and isinstance(court, str) and court.strip():
        court = filtre.valeur(court.strip())
    categorie = statut.get("statusCategory") if isinstance(statut.get("statusCategory"), dict) else {}
    return {"objets": objets_d_actifs(champs.get(CHAMP_VERSION_ACTIF)), "short_name": court,
            "status": statut.get("name"), "status_category": categorie.get("name"),
            "started": champs.get(CHAMP_VERSION_STARTED), "released": champs.get(CHAMP_VERSION_RELEASED)}


CONTENU_VIDE = {"short_name": None, "status": None, "status_category": None, "started": None, "released": None}


def _date_iso(valeur) -> str | None:
    if not isinstance(valeur, str):
        return None
    try:
        return dt.date.fromisoformat(valeur.strip()[:10]).isoformat()
    except ValueError:
        return None


def contenu_de_version(ticket: dict) -> dict:
    """Contenu d'une version (nom court, état, catégorie d'état, Started, Released en AAAA-MM-JJ) depuis un ticket de version réduit."""
    court = ticket.get("short_name")
    return {"short_name": court.strip() if isinstance(court, str) and court.strip() else None,
            "status": ticket.get("status") if isinstance(ticket.get("status"), str) else None,
            "status_category": ticket.get("status_category") if isinstance(ticket.get("status_category"), str) else None,
            "started": _date_iso(ticket.get("started")), "released": _date_iso(ticket.get("released"))}


def joindre_versions(tickets: list[dict]) -> tuple[dict[str, dict], dict]:
    """Jointure des tickets de version par objet d'actif (D5). Chaque ticket : {"objets": [identifiants], "short_name", "status",
    "status_category", "started", "released"}. Rend ({objet: contenu}, comptes). Un ticket sans objet ou avec plusieurs est compté
    (`sans_actif`), non gardé ; un objet porté par deux tickets garde un contenu nul et est compté une fois (`conflits`). Aucune clé de ticket
    n'entre ni ne sort."""
    par_objet: dict[str, list[dict]] = {}
    sans_actif = plusieurs_actifs = 0
    for ticket in tickets:
        objets = list(dict.fromkeys(ticket.get("objets") or []))
        if len(objets) != 1:
            if objets:
                plusieurs_actifs += 1          # ligne dédiée (R-20261102-41, Q327)
            else:
                sans_actif += 1
            continue
        par_objet.setdefault(objets[0], []).append(ticket)
    contenus: dict[str, dict] = {}
    conflits = 0
    for objet, porteurs in par_objet.items():
        if len(porteurs) > 1:
            conflits += 1
            contenus[objet] = dict(CONTENU_VIDE)
        else:
            contenus[objet] = contenu_de_version(porteurs[0])
    return contenus, {"lus": len(tickets), "sans_actif": sans_actif, "plusieurs_actifs": plusieurs_actifs, "conflits": conflits}


# ---------------------------------------------------------------------------------------------------------------------------------
# D7. Glissement
# ---------------------------------------------------------------------------------------------------------------------------------

def slips(valeurs) -> tuple[int, list]:
    """Glissements d'un champ de sprint ou de version (D7). La valeur du champ à un instant est l'ensemble de ses identifiants ; on garde la suite
    ordonnée des valeurs non vides ; un glissement est un pas vers une valeur qui tient un identifiant absent de la valeur non vide
    précédente. Le premier remplissage n'est jamais un glissement, un vidage non plus ; V1, puis vide, puis V2 fait un glissement. Chaque
    élément de `valeurs` est un ensemble (liste, ensemble) d'identifiants, ou une paire (instant, ensemble) ; rend (nombre, instants des
    glissements : None pour un élément sans instant). Remplace : la partie « a changé » de l'inventaire des champs. Retrait : permanent."""
    precedente: set | None = None
    instants: list = []
    for element in valeurs:
        if isinstance(element, tuple) and len(element) == 2 and isinstance(element[1], (set, frozenset, list)):
            instant, ensemble = element[0], set(element[1])
        else:
            instant, ensemble = None, set(element)
        if not ensemble:
            continue
        if precedente is not None and ensemble - precedente:
            instants.append(instant)
        precedente = ensemble
    return len(instants), instants


# ---------------------------------------------------------------------------------------------------------------------------------
# D11. Flux d'une épic
# ---------------------------------------------------------------------------------------------------------------------------------

def epic_flow_source(epic: dict) -> list:
    """Transitions sur lesquelles se mesure le flux d'une épic (D11) : les siennes, jamais seulement celles de ses stories. `epic` : {"transitions":
    [...], "stories": [...]} ; les transitions des stories ne sont jamais lues. Remplace : rien. Retrait : permanent."""
    return list((epic or {}).get("transitions") or [])


# ---------------------------------------------------------------------------------------------------------------------------------
# D13. Comptes d'échec de changement par version de détection
# ---------------------------------------------------------------------------------------------------------------------------------

PRODUCTION, PILOTING = "Production", "Piloting"


def change_failure_counts(defects: list[dict], totaux: dict | None = None) -> dict:
    """Comptes par version de détection (D13, R-20261102-35, -36). Chaque défaut : {"phase": code de la phase de détection, "versions":
    [identifiants d'objet de la version de détection], "id" (facultatif)}. Production : phase égale à `production` ; Piloting : égale à
    `piloting` ; toute autre valeur (le libellé brut « Production » compris), vide comprise, est comptée dans `other_phase` et n'entre dans aucun compte de version. Par version :
    `production` et `piloting`, deux comptes séparés que rien n'additionne. Un défaut sans version de détection est compté dans
    `unattached_production` ou `unattached_piloting`, jamais rattaché ni écarté. Un défaut qui nomme plusieurs versions compte une fois dans
    chacune ; un total sur plusieurs versions compte les défauts DISTINCTS une fois : `total` (toutes les versions) et, pour chaque entrée de
    `totaux` (étiquette -> ensemble de versions, une année par exemple), `totals[étiquette]`. Les champs des versions touchées, de la base
    installée et de « détecté par » ne sont jamais lus. Remplace : la définition de la tuile du taux d'échec (« versions suivies d'un
    correctif »), devenue le taux de reprise (R-20261102-10). Retrait : permanent tant qu'une tuile la lit."""
    par_version: dict[str, dict[str, int]] = {}
    sans_version = {PRODUCTION: 0, PILOTING: 0}
    autre = 0
    distincts: dict[str, dict[str, set]] = {PRODUCTION: {}, PILOTING: {}}       # phase -> {défaut: versions nommées}
    for i, defaut in enumerate(defects):
        phase = {"production": PRODUCTION, "piloting": PILOTING}.get(defaut.get("phase"))          # code de phase seulement (R-20261105-36)
        if phase is None:
            autre += 1
            continue
        versions = list(dict.fromkeys(defaut.get("versions") or []))
        if not versions:
            sans_version[phase] += 1
            continue
        for version in versions:
            compte = par_version.setdefault(version, {"production": 0, "piloting": 0})
            compte["production" if phase == PRODUCTION else "piloting"] += 1
        cle = defaut.get("id")
        distincts[phase][("index", i) if cle is None else ("id", cle)] = set(versions)          # clé None : l'index, jamais une collision entre défauts

    def total_sur(ensemble) -> dict[str, int]:
        return {"production": sum(1 for v in distincts[PRODUCTION].values() if ensemble is None or v & set(ensemble)),
                "piloting": sum(1 for v in distincts[PILOTING].values() if ensemble is None or v & set(ensemble))}

    return {"versions": par_version, "unattached_production": sans_version[PRODUCTION],
            "unattached_piloting": sans_version[PILOTING], "other_phase": autre, "total": total_sur(None),
            "totals": {nom: total_sur(ensemble) for nom, ensemble in (totaux or {}).items()}}


def canonique(livraison: dict) -> dict:
    """Forme canonique de la partie `delivery`, pour l'empreinte de l'instantané : sprints triés par identifiant, objets d'actifs triés, de sorte
    qu'un simple changement d'ordre dans la réponse de Jira ne crée pas d'instantané."""
    sortie = dict(livraison)
    if "sprints" in sortie:
        sortie["sprints"] = sorted(sortie["sprints"], key=lambda s: s["id"])
    if "assets" in sortie:
        sortie["assets"] = {genre: sorted(ids) for genre, ids in sortie["assets"].items()}
    return sortie


# ---------------------------------------------------------------------------------------------------------------------------------
# Lignes des tables courantes dérivées d'une partie `delivery` (import, D3)
# ---------------------------------------------------------------------------------------------------------------------------------

def _instant(texte):
    if not isinstance(texte, str):
        return None
    try:
        moment = dt.datetime.fromisoformat(texte.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=dt.timezone.utc)


def lignes_de(cle: str, livraison: dict | None) -> dict[str, set]:
    """Lignes voulues des tables courantes pour un ticket, depuis la partie `delivery` de son dernier instantané. Clés : `fields`,
    `sprints` (ticket, sprint, état, début, fin, terminé : la ligne de flow.sprints jointe à celle du ticket), `assets`, `options`, `defect`.
    Ensembles de tuples, pour une comparaison exacte avec les lignes vivantes."""
    livraison = livraison or {}
    unique = livraison.get("single") or {}
    drapeaux = livraison.get("flags") or {}
    rang_ = livraison.get("rank")
    champs = set()
    if unique or rang_ is not None or any(drapeaux.values()):
        champs.add((cle, unique.get("release_target"), unique.get("verification_required"), unique.get("product_safety"),
                    unique.get("isp"), unique.get("code_review_status"), None if rang_ is None else Decimal(rang_),
                    bool(drapeaux.get("customer_commitment")), bool(drapeaux.get("source_commitment")),
                    bool(drapeaux.get("strategic_objective"))))
    liste = livraison.get("sprints") or []
    defaut = livraison.get("defect") or {}
    ligne_defaut = set()
    if defaut:
        ligne_defaut.add((cle, (defaut.get("detection_phase") or {}).get("id"), (defaut.get("detection_phase") or {}).get("code"),
                          (defaut.get("detected_by") or {}).get("id"), (defaut.get("installed_base") or {}).get("id")))
    options_ = set()
    for genre, elements in (livraison.get("options") or {}).items():
        for position, identifiant in enumerate(elements, 1):
            options_.add((cle, genre, position, identifiant))
    return {"fields": champs,
            "sprints": {(cle, s["id"], s.get("state"), _instant(s.get("start")), _instant(s.get("end")), _instant(s.get("complete")))
                        for s in liste},
            "assets": {(cle, genre, objet) for genre, objets in (livraison.get("assets") or {}).items() for objet in objets},
            "options": options_, "defect": ligne_defaut}
