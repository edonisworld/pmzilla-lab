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
