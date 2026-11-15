"""
MagasinBase de tools/version_photo.py avec une FAUSSE connexion (change version-quality-photo, tâche 1.3) : les requêtes émises, leur ordre, leurs
paramètres et la transaction, sans PostgreSQL. Les effets sur une vraie base sont dans tests/db/test_flow_version_photo_outil.py (sauté sans base).
"""
import datetime as dt
import re
import unittest

from aide_version_photo import Espace, jour, vp
from version_photo_messages import CATALOGS
from messages import check_catalogs


class FauxCurseur:
    def __init__(self, lignes):
        self.lignes = list(lignes)

    def __iter__(self):
        return iter(self.lignes)

    def fetchone(self):
        return self.lignes[0] if self.lignes else None


class FausseConnexion:
    """Rend, pour chaque requête, les lignes enregistrées sous le début de son texte ; journalise tout."""

    def __init__(self, reponses=None):
        self.reponses = reponses or {}
        self.appels: list[tuple[str, tuple]] = []
        self.commits = self.rollbacks = 0
        self.fermee = False
        self.compteur = 100

    def execute(self, sql, params=()):
        self.appels.append((sql, params))
        if sql.startswith("INSERT INTO flow.version_photo_runs"):
            return FauxCurseur([(7,)])
        if sql.startswith("INSERT INTO flow.version_photo_versions"):
            self.compteur += 1
            return FauxCurseur([(self.compteur,)])
        for debut, lignes in self.reponses.items():
            if sql.startswith(debut):
                return FauxCurseur(lignes)
        return FauxCurseur([])

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.fermee = True

    def sql(self, debut):
        return [a for a in self.appels if a[0].startswith(debut)]


class LectureDesTickets(unittest.TestCase):
    def test_les_tickets_et_leurs_versions_periodes_et_transitions(self):
        pose = jour("2026-03-04")
        conn = FausseConnexion({
            "SELECT i.key": [("PROJ-1", "Bug", "Alpha", jour("2026-01-05"), jour("2026-03-03"), False),
                             ("PROJ-2", "Story", "(sans équipe)", jour("2026-01-06"), None, True)],
            "SELECT v.issue_key": [("PROJ-1", "fix", "V"), ("PROJ-1", "affects", "W"), ("PROJ-1", "affects", "X")],
            "SELECT p.issue_key": [("PROJ-1", "V", pose, None)],
            "SELECT x.issue_key": [("PROJ-1", jour("2026-03-05"), "Closed", "Open")],
        })
        tickets = vp.MagasinBase(conn).lire_tickets(frozenset({"bug", "defect"}))
        self.assertEqual(len(tickets), 2)
        un, deux = tickets
        self.assertEqual((un.type, un.equipe, un.hors_export, un.fix, un.affects), ("Bug", "Alpha", False, frozenset({"V"}), frozenset({"W", "X"})))
        self.assertEqual(un.periodes, (("V", pose, None),))
        self.assertEqual(un.transitions, ((jour("2026-03-05"), "Closed", "Open"),))
        self.assertEqual((deux.equipe, deux.hors_export, deux.fix, deux.periodes), ("(sans équipe)", True, frozenset(), ()))

    def test_les_requetes_de_versions_et_periodes_ne_lisent_que_les_defauts(self):
        conn = FausseConnexion()
        vp.MagasinBase(conn).lire_tickets(frozenset({"zzdefaut", "bug"}))
        for debut in ("SELECT v.issue_key", "SELECT p.issue_key"):
            (sql, params), = conn.sql(debut)
            self.assertIn("lower(btrim(i.type)) = ANY(%(types)s)", sql)
            self.assertEqual(params, {"types": ["bug", "zzdefaut"]})

    def test_les_transitions_de_tous_les_types_sont_lues(self):
        """Décision 3 du 2026-10-23 : une seule définition des fermetures, pour les défauts et pour le débit de tous les items."""
        pose = jour("2026-03-04")
        conn = FausseConnexion({
            "SELECT i.key": [("PROJ-1", "Bug", "Alpha", jour("2026-01-05"), None, False),
                             ("PROJ-2", "Story", "Alpha", jour("2026-01-06"), jour("2026-03-04"), False)],
            "SELECT x.issue_key": [("PROJ-2", pose, "Open", "Closed")],
        })
        self.assertNotIn("type", vp.SQL_TRANSITIONS)
        tickets = vp.MagasinBase(conn).lire_tickets(frozenset({"bug"}))
        (sql, params), = conn.sql("SELECT x.issue_key")
        self.assertNotIn("ANY(", sql)
        self.assertEqual(params, ())
        self.assertEqual(tickets[1].transitions, ((pose, "Open", "Closed"),))                          # un item qui n'est pas un défaut

    def test_premiere_equipe_ou_sans_equipe_dans_la_requete(self):
        self.assertIn("LEFT JOIN flow.teams t ON t.id = i.team_id", vp.SQL_TICKETS)
        self.assertIn("coalesce(t.name, '(sans équipe)')", vp.SQL_TICKETS)
        self.assertIn("i.out_of_export_at IS NOT NULL", vp.SQL_TICKETS)

    def test_aucune_colonne_de_titre_ni_de_personne_lue(self):
        for nom, texte in vars(vp).items():
            if nom.startswith("SQL_") and isinstance(texte, str):
                self.assertNotRegex(texte, r"(?i)\b(summary|title|description|assignee|reporter|creator|author|label)\b", nom)


class Ecriture(unittest.TestCase):
    def lignes(self, version, equipe="Alpha"):
        return {"team": equipe, "version": version, "found": 1, "found_open": 0, "corrected_at_week": 0, "corrected_now": 0, "reopened": 0,
                "defects_created": None, "defects_without_affects": None, "resolved_week": None, "resolved_week_defects": None}

    def libre(self, equipe="Alpha"):
        return {"team": equipe, "version": None, "found": None, "found_open": None, "corrected_at_week": None, "corrected_now": None,
                "reopened": None, "defects_created": 3, "defects_without_affects": 1, "resolved_week": 5, "resolved_week_defects": 2}

    def test_passage_semaines_lignes_dans_l_ordre(self):
        conn = FausseConnexion()
        magasin = vp.MagasinBase(conn)
        instant = jour("2026-10-23", 14)
        total = magasin.ecrire_passage("reconstructed", instant, [
            (dt.date(2026, 10, 5), "partial", [self.lignes("zzversion-a"), self.libre()]),
            (dt.date(2026, 10, 12), "complete", [self.lignes("zzversion-a"), self.lignes("zzversion-b")])])
        self.assertEqual(total, 4)
        self.assertTrue(conn.appels[0][0].startswith("INSERT INTO flow.version_photo_runs"))            # toujours un nouveau passage, rien d'abord
        (sql, params), = conn.sql("INSERT INTO flow.version_photo_runs")
        self.assertEqual(params, (instant, "reconstructed"))
        semaines = conn.sql("INSERT INTO flow.version_photo_weeks")
        self.assertEqual([p for _, p in semaines], [(dt.date(2026, 10, 5), 7, "partial"), (dt.date(2026, 10, 12), 7, "complete")])
        self.assertEqual(len(conn.sql("INSERT INTO flow.version_photo_rows")), 4)

    def test_une_version_est_enregistree_une_fois_avec_un_numero_stable(self):
        conn = FausseConnexion()
        vp.MagasinBase(conn).ecrire_passage("reconstructed", jour("2026-10-23"), [
            (dt.date(2026, 10, 5), "complete", [self.lignes("zzversion-a")]), (dt.date(2026, 10, 12), "complete", [self.lignes("zzversion-a")])])
        self.assertEqual(len(conn.sql("INSERT INTO flow.version_photo_versions")), 1)
        lignes = [p for _, p in conn.sql("INSERT INTO flow.version_photo_rows")]
        self.assertEqual({p[2] for p in lignes}, {101})

    def test_une_version_deja_connue_garde_son_numero(self):
        conn = FausseConnexion({"SELECT version_no": [(42,)]})
        vp.MagasinBase(conn).ecrire_passage("live", jour("2026-10-23"), [(dt.date(2026, 10, 19), "complete", [self.lignes("zzversion-a")])])
        self.assertEqual(conn.sql("INSERT INTO flow.version_photo_versions"), [])
        self.assertEqual([p[2] for _, p in conn.sql("INSERT INTO flow.version_photo_rows")], [42])

    def test_ligne_libre_sans_numero_de_version(self):
        conn = FausseConnexion()
        vp.MagasinBase(conn).ecrire_passage("live", jour("2026-10-23"), [(dt.date(2026, 10, 19), "complete", [self.libre()])])
        (sql, params), = conn.sql("INSERT INTO flow.version_photo_rows")
        self.assertEqual(params, (dt.date(2026, 10, 19), "Alpha", None, None, None, None, None, None, 3, 1, 5, 2))
        self.assertEqual(conn.sql("INSERT INTO flow.version_photo_versions"), [])

    def test_aucun_nom_de_version_ni_cle_dans_les_lignes_ecrites_hors_registre(self):
        conn = FausseConnexion()
        vp.MagasinBase(conn).ecrire_passage("live", jour("2026-10-23"), [(dt.date(2026, 10, 19), "complete", [self.lignes("zzversion-a")])])
        for sql, params in conn.appels:
            if sql.startswith("INSERT INTO flow.version_photo_versions"):
                continue
            if sql.startswith("SELECT version_no"):
                continue
            self.assertNotIn("zzversion-a", repr(params), sql)

    def test_suppressions_ciblees(self):
        conn = FausseConnexion()
        magasin = vp.MagasinBase(conn)
        lundis = [dt.date(2026, 8, 31), dt.date(2026, 9, 7)]
        magasin.supprimer_semaines_reconstruites(lundis)
        magasin.supprimer_photo_vivante(dt.date(2026, 10, 19))
        (sql1, params1), (sql2, params2), (sql3, params3) = conn.appels
        self.assertTrue(sql1.startswith("DELETE FROM flow.version_photo_weeks"))
        self.assertIn("source = 'reconstructed'", sql1)                     # jamais une semaine vivante
        self.assertEqual(params1, (lundis,))
        self.assertTrue(sql2.startswith("DELETE FROM flow.version_photo_runs"))
        self.assertIn("source = 'reconstructed'", sql2)
        self.assertIn("NOT EXISTS", sql2)                                   # un passage sans semaine est retiré, jamais un passage qui en garde
        self.assertEqual(params2, ())
        self.assertIn("source = 'live'", sql3)
        self.assertEqual(params3, (dt.date(2026, 10, 19),))

    def test_un_passage_reconstruit_n_est_jamais_reutilise_ni_mis_a_jour(self):
        """Décision 2 du 2026-10-23 : l'index partiel est retiré, chaque relance de --replace écrit un nouveau passage ; l'ancien garde son instant."""
        conn = FausseConnexion({"SELECT id FROM flow.version_photo_runs WHERE source = 'reconstructed'": [(9,)]})
        instant = jour("2026-11-06", 14)
        vp.MagasinBase(conn).ecrire_passage("reconstructed", instant, [(dt.date(2026, 8, 31), "complete", [self.libre()])])
        (sql, params), = conn.sql("INSERT INTO flow.version_photo_runs")
        self.assertEqual(params, (instant, "reconstructed"))
        self.assertEqual(conn.sql("UPDATE flow.version_photo_runs"), [])
        self.assertEqual([p[1] for _, p in conn.sql("INSERT INTO flow.version_photo_weeks")], [7])
        self.assertFalse(hasattr(vp, "SQL_MAJ_PASSAGE"))
        self.assertFalse(hasattr(vp, "SQL_PASSAGE_RECONSTRUIT"))

    def test_toute_ecriture_vise_les_tables_de_photo(self):
        for nom, texte in vars(vp).items():
            if nom.startswith("SQL_") and isinstance(texte, str) and re.match(r"(?i)\s*(INSERT|DELETE|UPDATE)", texte):
                self.assertRegex(texte, r"flow\.version_photo_\w+", nom)
                self.assertNotRegex(texte, r"flow\.(issues|teams|transitions|issue_\w+|links|raw_\w+)\b", nom)

    def test_transaction_valider_puis_fermer(self):
        conn = FausseConnexion()
        magasin = vp.MagasinBase(conn)
        magasin.valider()
        magasin.fermer()
        self.assertEqual((conn.commits, conn.rollbacks, conn.fermee), (1, 1, True))

    def test_adoption(self):
        conn = FausseConnexion({"SELECT count(*) FROM flow.version_photo_n": [(2,)]})
        magasin = vp.MagasinBase(conn)
        self.assertEqual(magasin.nombre_adoptions(), 2)
        magasin.ajouter_adoption(8, dt.date(2026, 12, 1), "r")
        (sql, params), = conn.sql("INSERT INTO flow.version_photo_n")
        self.assertEqual(params, (8, dt.date(2026, 12, 1), "r"))


    def test_garde_du_masquage_lit_le_marqueur_et_jamais_les_noms_de_migration(self):
        for version in (0, 1, 2):
            conn = FausseConnexion({"SELECT flow.masking_version()": [(version,)]})
            self.assertEqual(vp.MagasinBase(conn).version_masquage(), version)
            (sql, params), = conn.appels
            self.assertEqual((sql, params), (vp.SQL_VERSION_MASQUAGE, ()))
            self.assertEqual(conn.sql("INSERT"), [])
        self.assertNotIn("schema_migrations", vp.SQL_VERSION_MASQUAGE)

    def test_fonction_absente_vaut_marqueur_absent_sans_code_1_et_sans_ecriture(self):
        """D9 : l'erreur de fonction indéfinie est lue comme un refus, jamais comme une erreur de base ; une migration dont le nom contient
        `masquage_somme` ne suffit pas, le nom n'est plus lu."""
        from psycopg import errors

        class ConnexionSansMarqueur(FausseConnexion):
            def execute(self, sql, params=()):
                if sql.startswith("SELECT flow.masking_version()"):
                    self.appels.append((sql, params))
                    raise errors.UndefinedFunction("function flow.masking_version() does not exist")
                return super().execute(sql, params)

        conn = ConnexionSansMarqueur({"SELECT EXISTS (SELECT 1 FROM public.schema_migrations": [(True,)]})
        magasin = vp.MagasinBase(conn)
        self.assertIsNone(magasin.version_masquage())
        self.assertEqual(conn.rollbacks, 1)                                     # la transaction avortée est annulée
        self.assertTrue(all("schema_migrations" not in sql for sql, _ in conn.appels))
        espace = Espace()
        espace.setUp()
        self.addCleanup(espace.temp.cleanup)
        code, sortie, _, _, _ = espace.lancer("adopt-n", "--weeks", "6", "--adopted-on", "2026-11-20", "--language", "en", magasin=magasin)
        self.assertEqual((code, sortie.strip()), (3, CATALOGS["en"]["crossing_masking_missing"]))
        self.assertEqual(conn.sql("INSERT"), [])
        self.assertEqual(conn.commits, 0)


class Catalogues(unittest.TestCase):
    def test_le_refus_du_masquage_nomme_la_raison_dans_les_deux_langues(self):
        fr, en = CATALOGS["fr"]["crossing_masking_missing"], CATALOGS["en"]["crossing_masking_missing"]
        self.assertIn("R-144", fr)
        self.assertIn("R-144", en)
        self.assertIn("croisements", fr)
        self.assertIn("crossings", en)

    def test_le_refus_de_version_nomme_installee_attendue_et_la_raison_dans_les_deux_langues(self):
        """Décision du 2026-10-28 : version installée, version attendue, raison « propagation des bornes D15 non installée »."""
        fr, en = CATALOGS["fr"]["crossing_masking_version"], CATALOGS["en"]["crossing_masking_version"]
        self.assertEqual(fr.format(installed=1, expected=2),
                         "adoption de N refusée : version installée 1, version attendue 2, raison : propagation des bornes D15 non installée")
        self.assertEqual(en.format(installed=1, expected=2),
                         "N adoption refused: installed version 1, expected version 2, reason: D15 bounds propagation not installed")

    def test_les_deux_langues_ont_les_memes_cles_et_champs(self):
        self.assertEqual(check_catalogs(CATALOGS), [])

    def test_phrases_cles_de_d14(self):
        fr, en = CATALOGS["fr"], CATALOGS["en"]
        self.assertEqual(en["reconstruct_done"].format(weeks=10, versions=3, partial=2), "reconstruction: 10 weeks, 3 versions, 2 partial weeks")
        self.assertEqual(fr["reconstruct_done"].format(weeks=10, versions=3, partial=2), "reconstruction : 10 semaines, 3 versions, 2 semaines partielles")
        self.assertEqual(en["reconstruct_kept"].format(n=3), "warning: 3 older reconstructed weeks kept as they are, no longer recomputable")
        self.assertEqual(fr["reconstruct_kept"].format(n=3),
                         "avertissement : 3 semaines reconstruites plus anciennes gardées telles quelles, plus recalculables")
        self.assertEqual(en["photo_taken"].format(date="2026-10-19", rows=4), "photo taken: week of 2026-10-19, 4 rows")
        self.assertEqual(fr["photo_taken"].format(date="2026-10-19", rows=4), "photo prise : semaine du 2026-10-19, 4 lignes")
        self.assertEqual(en["n_adopted"].format(n=6, date="2026-11-20"), "N adopted: 6 weeks, on 2026-11-20")
        self.assertEqual(fr["n_adopted"].format(n=6, date="2026-11-20"), "N adopté : 6 semaines, le 2026-11-20")
        self.assertEqual(en["defect_types_missing"], "defect types not set")
        self.assertEqual(fr["defect_types_missing"], "types de défaut non réglés")


if __name__ == "__main__":
    unittest.main()
