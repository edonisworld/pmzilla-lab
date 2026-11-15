"""PMZilla Lab : magasin du schéma `quality` de la base (change story-quality-audit, design D3, D9 et « Data model »).

Seuls les outils lancés par l'utilisateur dans le Terminal l'ouvrent (`collect`, `review`, puis `analyse` et `coach`) : la session ne lit
jamais les tables de `quality`. Connexion de l'exécuteur, puis `SET ROLE pmzilla_quality` (rôle de lecture-écriture du schéma, sans mot
de passe propre), comme l'outil de rétention. Aucun texte n'est écrit dans un fichier, un cache ou un journal : la base est la seule
destination. Une erreur annule la transaction et remonte telle quelle ; l'appelant n'en affiche que le type.

    magasin = ouvrir()                       # ErreurMagasin si la base ne répond pas (message sans détail)
    marques, revenus = magasin.enregistrer_collecte(elements, attributs, complet=True)
    textes = magasin.echantillon("équipe", 5, random.Random())
    magasin.enregistrer_relecture("équipe", len(textes))
    magasin.fermer()

Les tests passent par une fausse connexion (protocole `execute`, `fetchall`, `rowcount`, `commit`, `rollback`) ou par la base jetable.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROLE = "pmzilla_quality"


class ErreurMagasin(Exception):
    """La base ne répond pas, ou le mot de passe manque : le message ne porte aucun détail de la base."""


@dataclass
class Element:
    """Un élément collecté, déjà nettoyé : jamais un champ de personne. Les instants sont des datetime avec fuseau."""
    key: str
    kind: str                         # "story" ou "epic"
    parent_key: str | None
    status_category: str | None
    created_at: object
    updated_at: object
    resolved_at: object | None
    teams: list[str] = field(default_factory=list)
    title: str = ""
    description: str = ""
    acceptance_criteria: str = ""
    content_hash: str = ""
    replacements: int = 0


SQL_ELEMENT = (
    "INSERT INTO quality.items (key, kind, parent_key, status_category, created_at, updated_at, resolved_at, text_collected_at, "
    "out_of_collection_at) VALUES (%s, %s, %s, %s, %s, %s, %s, now(), NULL) "
    "ON CONFLICT (key) DO UPDATE SET kind = EXCLUDED.kind, parent_key = EXCLUDED.parent_key, "
    "status_category = EXCLUDED.status_category, created_at = EXCLUDED.created_at, updated_at = EXCLUDED.updated_at, "
    "resolved_at = EXCLUDED.resolved_at, text_collected_at = now(), out_of_collection_at = NULL")
SQL_EQUIPES_EFFACER = "DELETE FROM quality.item_teams WHERE item_key = %s"
SQL_EQUIPE = "INSERT INTO quality.item_teams (item_key, team, position) VALUES (%s, %s, %s)"
SQL_CONTENU = (
    "INSERT INTO quality.contents (item_key, title, description, acceptance_criteria, content_hash, replacements) "
    "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (item_key) DO UPDATE SET title = EXCLUDED.title, "
    "description = EXCLUDED.description, acceptance_criteria = EXCLUDED.acceptance_criteria, "
    "content_hash = EXCLUDED.content_hash, replacements = EXCLUDED.replacements")
SQL_ATTRIBUTS = ("INSERT INTO quality.team_attributes (team, single_po) VALUES (%s, %s) "
                 "ON CONFLICT (team) DO UPDATE SET single_po = EXCLUDED.single_po")
SQL_REVENUS = "SELECT count(*) FROM quality.items WHERE out_of_collection_at IS NOT NULL AND key = ANY(%s)"
SQL_MARQUER = ("UPDATE quality.items SET out_of_collection_at = now() "
               "WHERE out_of_collection_at IS NULL AND NOT (key = ANY(%s))")
SQL_CLES_EQUIPE = ("SELECT i.key FROM quality.items i JOIN quality.item_teams t ON t.item_key = i.key "
                   "WHERE t.team = %s AND i.out_of_collection_at IS NULL ORDER BY i.key")
SQL_TEXTES = "SELECT item_key, title, description, acceptance_criteria FROM quality.contents WHERE item_key = ANY(%s)"
SQL_RELECTURE = "INSERT INTO quality.team_reviews (team, sample_size) VALUES (%s, %s)"
# change patient-data-detection (design D6) : textes nettoyés de TOUS les éléments stockés (sortis de la collecte compris), sans clé ;
# passages du détecteur et levées de la suspension (aucun compte, aucun texte, aucune clé)
SQL_TEXTES_DETECTION = ("SELECT i.kind, c.title, c.description, c.acceptance_criteria FROM quality.items i "
                        "JOIN quality.contents c ON c.item_key = i.key")
SQL_DETECTION = ("INSERT INTO quality.patient_scan_runs (detector_version, id_markers_fingerprint, items_read, found) "
                 "VALUES (%s, %s, %s::jsonb, %s::jsonb) RETURNING run_at")
SQL_DERNIERE_DETECTION = ("SELECT id, run_at, detector_version, id_markers_fingerprint, items_read, found FROM quality.patient_scan_runs "
                          "ORDER BY run_at DESC, id DESC LIMIT 1")
SQL_LEVEE = ("INSERT INTO quality.patient_scan_lifts (detector_version, id_markers_fingerprint, run_id, accepted_categories) "
             "VALUES (%s, %s, %s, %s)")
SQL_DERNIERE_LEVEE = ("SELECT id, lifted_at, detector_version, id_markers_fingerprint, run_id, accepted_categories "
                      "FROM quality.patient_scan_lifts ORDER BY lifted_at DESC, id DESC LIMIT 1")
SQL_TROUVES_APRES = "SELECT found FROM quality.patient_scan_runs WHERE run_at > %s"


def _json(valeur):
    """Un jsonb rendu par le pilote est déjà un dictionnaire ; une chaîne (fausse connexion, ancien pilote) est décodée."""
    return json.loads(valeur) if isinstance(valeur, str) else dict(valeur)


class MagasinQualite:
    """Écritures et lectures de `quality` sur une connexion déjà placée sous le rôle de lecture-écriture du schéma."""

    def __init__(self, conn):
        self.conn = conn

    def _transaction(self, travail):
        try:
            resultat = travail(self.conn.cursor())
            self.conn.commit()
            return resultat
        except BaseException:
            self.conn.rollback()
            raise

    def enregistrer_collecte(self, elements: list[Element], attributs: dict[str, bool], complet: bool,
                             vus: list[str] | None = None) -> tuple[int, int]:
        """Écrit en UNE transaction les éléments, leurs équipes, leurs textes nettoyés et les attributs d'équipe. Une nouvelle collecte
        remplace le texte d'un élément et remet son instant de collecte à maintenant, sans garder d'ancienne version. Sur un passage
        complet (`complet`), marque sortis de la collecte les éléments stockés qui ne sont pas dans `vus` (toutes les clés de story ou
        d'epic rendues par les requêtes ; par défaut celles des éléments écrits). Rend (marqués, revenus) : revenus = éléments
        écrits qui portaient la marque."""
        cles = [e.key for e in elements]
        vus = cles if vus is None else list(vus)

        def travail(cur):
            cur.execute(SQL_REVENUS, (cles,))
            revenus = int(cur.fetchone()[0])
            for e in elements:
                cur.execute(SQL_ELEMENT, (e.key, e.kind, e.parent_key, e.status_category, e.created_at, e.updated_at, e.resolved_at))
                cur.execute(SQL_EQUIPES_EFFACER, (e.key,))
                for position, equipe in enumerate(dict.fromkeys(e.teams), start=1):
                    cur.execute(SQL_EQUIPE, (e.key, equipe, position))
                cur.execute(SQL_CONTENU, (e.key, e.title, e.description, e.acceptance_criteria, e.content_hash, e.replacements))
            for equipe, drapeau in sorted(attributs.items()):
                cur.execute(SQL_ATTRIBUTS, (equipe, bool(drapeau)))
            marques = 0
            if complet:
                cur.execute(SQL_MARQUER, (vus,))
                marques = max(int(cur.rowcount or 0), 0)
            return marques, revenus
        return self._transaction(travail)

    def echantillon(self, equipe: str, taille: int, alea) -> list[tuple[str, str, str]]:
        """Tirage au hasard (`alea` : random.Random) d'au plus `taille` éléments de l'équipe encore dans la collecte ; rend leurs
        textes nettoyés (titre, description, critères d'acceptation), SANS les clés, dans l'ordre du tirage. Liste vide : aucun
        élément collecté pour cette équipe."""
        cur = self.conn.cursor()
        cur.execute(SQL_CLES_EQUIPE, (equipe,))
        cles = [r[0] for r in cur.fetchall()]
        if not cles:
            self.conn.rollback()
            return []
        tirees = alea.sample(cles, min(taille, len(cles)))
        cur.execute(SQL_TEXTES, (tirees,))
        textes = {r[0]: (r[1] or "", r[2] or "", r[3] or "") for r in cur.fetchall()}
        self.conn.rollback()                 # lecture seule : rien à valider
        return [textes[c] for c in tirees if c in textes]

    def enregistrer_relecture(self, equipe: str, taille: int) -> None:
        """Enregistre la relecture d'un échantillon de l'équipe (équipe, instant, taille) : ni texte, ni clé, ni personne."""
        self._transaction(lambda cur: cur.execute(SQL_RELECTURE, (equipe, taille)))

    def textes_pour_detection(self) -> list[tuple[str, str, str, str]]:
        """(genre, titre, description, critères) des textes nettoyés de TOUS les éléments stockés, sortis de la collecte compris, SANS les
        clés, dans un ordre quelconque. Lecture seule (change patient-data-detection)."""
        try:
            cur = self.conn.cursor()
            cur.execute(SQL_TEXTES_DETECTION)
            return [(r[0], r[1] or "", r[2] or "", r[3] or "") for r in cur.fetchall()]
        finally:
            self.conn.rollback()

    def enregistrer_detection(self, version: int, empreinte: str | None, lus: dict[str, int], trouves: dict[str, bool]):
        """Enregistre un passage du détecteur : version, empreinte de la liste facultative (None : absente), éléments lus par genre, un
        drapeau trouvé par catégorie. Ni compte par catégorie, ni texte, ni clé, ni équipe. Rend l'instant enregistré."""
        def travail(cur):
            cur.execute(SQL_DETECTION, (version, empreinte, json.dumps(lus, sort_keys=True), json.dumps(trouves, sort_keys=True)))
            ligne = cur.fetchone()
            return ligne[0] if ligne else None
        return self._transaction(travail)

    def derniere_detection(self) -> dict | None:
        """Dernier passage : {id, run_at, detector_version, labels_fingerprint, items_read, found}, ou None."""
        try:
            cur = self.conn.cursor()
            cur.execute(SQL_DERNIERE_DETECTION)
            ligne = cur.fetchone()
        finally:
            self.conn.rollback()
        if not ligne:
            return None
        return {"id": ligne[0], "run_at": ligne[1], "detector_version": ligne[2], "labels_fingerprint": ligne[3],
                "items_read": _json(ligne[4]), "found": _json(ligne[5])}

    def enregistrer_levee(self, version: int, empreinte: str | None, run_id, acceptees: list[str]) -> None:
        """Enregistre la levée de la suspension : version du détecteur, empreinte de la liste, passage sur lequel elle s'appuie, catégories
        acceptées."""
        self._transaction(lambda cur: cur.execute(SQL_LEVEE, (version, empreinte, run_id, sorted(set(acceptees)))))

    def derniere_levee(self) -> dict | None:
        """Dernière levée : {id, lifted_at, detector_version, labels_fingerprint, run_id, accepted, found_after}, ou None. `found_after` :
        les catégories trouvées par les passages enregistrés APRÈS la levée."""
        try:
            cur = self.conn.cursor()
            cur.execute(SQL_DERNIERE_LEVEE)
            ligne = cur.fetchone()
            if not ligne:
                return None
            cur.execute(SQL_TROUVES_APRES, (ligne[1],))
            apres = {code for (trouves,) in cur.fetchall() for code, drapeau in _json(trouves).items() if drapeau}
        finally:
            self.conn.rollback()
        return {"id": ligne[0], "lifted_at": ligne[1], "detector_version": ligne[2], "labels_fingerprint": ligne[3],
                "run_id": ligne[4], "accepted": sorted(ligne[5] or []), "found_after": sorted(apres)}

    def fermer(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass


def ouvrir() -> MagasinQualite:
    """Connexion de l'exécuteur (mot de passe du Trousseau ou de la variable), puis SET ROLE pmzilla_quality. ErreurMagasin sans détail
    si la base ne répond pas. psycopg n'est chargé qu'ici (import tardif de db)."""
    import db
    import psycopg.sql
    try:
        conn = db.connect()
        conn.cursor().execute(psycopg.sql.SQL("SET ROLE {}").format(psycopg.sql.Identifier(ROLE)))
        conn.commit()                        # le rôle tient pour la session : une annulation plus tard ne le retire pas
    except Exception:                        # ErreurBase ou erreur du pilote : jamais de détail de la base dans le message
        raise ErreurMagasin() from None
    return MagasinQualite(conn)
