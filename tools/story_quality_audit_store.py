"""PMZilla Lab : lectures et écritures de `analyse` et `coach` dans le schéma `quality` (change story-quality-audit, design D5, D7, D17 et
« Data model »). Même connexion et même rôle que tools/story_quality_store.py (`SET ROLE pmzilla_quality`) ; seuls les outils lancés par
l'utilisateur dans le Terminal l'ouvrent. Aucun texte n'est écrit ailleurs que dans la base.

    magasin = ouvrir()
    magasin.elements()                        # éléments encore dans la collecte : clé, genre, mise à jour, empreinte, équipes (sans texte)
    magasin.textes(["CLE-1"])                 # {clé: (titre, description, critères, empreinte)} : pour le seul lot envoyé
    magasin.derniers_audits(paire)            # {clé: empreinte du texte du dernier audit à la paire (None avant la migration 0015)}
    magasin.equipes_relues()                  # équipes qui ont une relecture enregistrée
    magasin.enregistrer_audit(cle, paire, verdicts, echantillon, empreinte)
    magasin.enregistrer_coaching(cle, paire, lignes)
    magasin.lire_coaching(cles)
    magasin.empreinte_surcouche(id, version) / magasin.enregistrer_empreinte(id, version, empreinte) -> empreinte enregistrée

`paire` : (identifiant du socle, version du socle, identifiant de la surcouche, version de la surcouche), les deux derniers vides sans
surcouche. Une lecture se termine toujours par une annulation (rien à valider) ; une écriture est une transaction.

Fraîcheur (D7) : un verdict d'audit garde l'empreinte du texte réellement envoyé, lue AVEC ce texte (`textes`), jamais avec la liste des
éléments ; un élément est à auditer quand l'empreinte de son texte actuel diffère de celle de son dernier verdict d'audit à la paire.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import story_quality_store as store  # noqa: E402

SQL_ELEMENTS = ("SELECT i.key, i.kind, i.updated_at, c.content_hash FROM quality.items i JOIN quality.contents c ON c.item_key = i.key "
                "WHERE i.out_of_collection_at IS NULL ORDER BY i.key")
SQL_EQUIPES = "SELECT item_key, team FROM quality.item_teams ORDER BY item_key, position"
SQL_TEXTES = ("SELECT item_key, title, description, acceptance_criteria, content_hash FROM quality.contents "
              "WHERE item_key = ANY(%s)")
SQL_AUDITS = ("SELECT DISTINCT ON (item_key) item_key, content_hash FROM quality.assessments WHERE NOT sample AND core_grid_id = %s "
              "AND core_grid_version = %s AND overlay_id = %s AND overlay_version = %s ORDER BY item_key, analysed_at DESC, id DESC")
SQL_RELUES = "SELECT DISTINCT team FROM quality.team_reviews"
SQL_EFFACER_AUDIT = ("DELETE FROM quality.assessments WHERE item_key = %s AND NOT sample AND core_grid_id = %s "
                     "AND core_grid_version = %s AND overlay_id = %s AND overlay_version = %s")
SQL_EFFACER_ECHANTILLON = "DELETE FROM quality.assessments WHERE item_key = %s AND sample"
SQL_VERDICT = ("INSERT INTO quality.assessments (item_key, core_grid_id, core_grid_version, overlay_id, overlay_version, "
               "criterion_code, origin, link, verdict, sample, content_hash) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")
SQL_EFFACER_COACHING = "DELETE FROM quality.coaching_feedback WHERE item_key = %s"
SQL_COACHING = ("INSERT INTO quality.coaching_feedback (item_key, core_grid_id, core_grid_version, overlay_id, overlay_version, "
                "criterion_code, verdict, feedback) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)")
SQL_LIRE_COACHING = ("SELECT item_key, criterion_code, verdict, feedback FROM quality.coaching_feedback "
                     "WHERE item_key = ANY(%s) ORDER BY item_key, id")
SQL_EMPREINTE = "SELECT content_hash FROM quality.overlay_versions WHERE overlay_id = %s AND version = %s"
SQL_ENREGISTRER_EMPREINTE = ("INSERT INTO quality.overlay_versions (overlay_id, version, content_hash) VALUES (%s, %s, %s) "
                             "ON CONFLICT (overlay_id, version) DO NOTHING")


class MagasinAnalyse(store.MagasinQualite):
    def _lire(self, sql, params=()):
        try:
            cur = self.conn.cursor()
            cur.execute(sql, params)
            return cur.fetchall()
        finally:
            self.conn.rollback()             # lecture seule : rien à valider, même sur une erreur

    def elements(self) -> list[dict]:
        """Éléments encore dans la collecte, par clé : {key, kind, updated_at, content_hash, teams}. Aucun texte."""
        elements = self._lire(SQL_ELEMENTS)
        equipes: dict[str, list[str]] = {}
        for cle, equipe in self._lire(SQL_EQUIPES):
            equipes.setdefault(cle, []).append(equipe)
        return [{"key": k, "kind": genre, "updated_at": maj, "content_hash": empreinte, "teams": equipes.get(k, [])}
                for k, genre, maj, empreinte in elements]

    def textes(self, cles) -> dict[str, tuple[str, str, str, str]]:
        """{clé: (titre, description, critères, empreinte)} : l'empreinte est celle du texte lu ici, celui qui part au moteur."""
        return {k: (t or "", d or "", c or "", h or "") for k, t, d, c, h in self._lire(SQL_TEXTES, (list(cles),))}

    def derniers_audits(self, paire) -> dict:
        """{clé: empreinte du texte de son dernier verdict d'audit à la paire} ; None pour un verdict antérieur à la colonne."""
        return {k: empreinte for k, empreinte in self._lire(SQL_AUDITS, tuple(paire))}

    def equipes_relues(self) -> set[str]:
        return {ligne[0] for ligne in self._lire(SQL_RELUES)}

    def enregistrer_audit(self, cle, paire, verdicts, echantillon: bool, empreinte: str | None = None) -> None:
        """Remplace, en une transaction, les verdicts de l'élément : ceux de la même paire pour un audit, tous les verdicts d'échantillon
        pour un échantillon (jamais un verdict d'audit). `verdicts` : [(code, origine, lien, verdict)] ; `empreinte` : celle du texte
        envoyé."""
        def travail(cur):
            if echantillon:
                cur.execute(SQL_EFFACER_ECHANTILLON, (cle,))
            else:
                cur.execute(SQL_EFFACER_AUDIT, (cle, *paire))
            for code, origine, lien, verdict in verdicts:
                cur.execute(SQL_VERDICT, (cle, *paire, code, origine, lien, verdict, bool(echantillon), empreinte or None))
        self._transaction(travail)

    def enregistrer_coaching(self, cle, paire, lignes) -> None:
        """Remplace le retour de coaching de l'élément. `lignes` : [(code, verdict, retour)]."""
        def travail(cur):
            cur.execute(SQL_EFFACER_COACHING, (cle,))
            for code, verdict, retour in lignes:
                cur.execute(SQL_COACHING, (cle, *paire, code, verdict, retour))
        self._transaction(travail)

    def lire_coaching(self, cles) -> dict[str, list[tuple[str, str, str]]]:
        sortie: dict[str, list[tuple[str, str, str]]] = {}
        for cle, code, verdict, retour in self._lire(SQL_LIRE_COACHING, (list(cles),)):
            sortie.setdefault(cle, []).append((code, verdict, retour))
        return sortie

    def empreinte_surcouche(self, identifiant: str, version: str) -> str | None:
        lignes = self._lire(SQL_EMPREINTE, (identifiant, version))
        return lignes[0][0] if lignes else None

    def enregistrer_empreinte(self, identifiant: str, version: str, empreinte: str) -> str | None:
        """Pose l'empreinte si la version n'en a pas, puis rend celle qui est enregistrée (relue dans la même transaction) : l'appelant
        la compare à la sienne, ce qui couvre un autre lancement qui aurait posé une autre empreinte entre-temps."""
        def travail(cur):
            cur.execute(SQL_ENREGISTRER_EMPREINTE, (identifiant, version, empreinte))
            cur.execute(SQL_EMPREINTE, (identifiant, version))
            ligne = cur.fetchone()
            return ligne[0] if ligne else None
        return self._transaction(travail)


def ouvrir() -> MagasinAnalyse:
    """Même ouverture que story_quality_store.ouvrir (ErreurMagasin sans détail), avec les lectures et écritures de l'analyse."""
    return MagasinAnalyse(store.ouvrir().conn)
