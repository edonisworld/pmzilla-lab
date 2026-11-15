"""tools/version_photo.py contre une vraie base jetable (change version-quality-photo, tâches 1.3, 3.1 à 3.4 ; spec jira-flow-version-photo).

    bash tools/dbtest.sh db

Ce que la fausse connexion et le magasin en mémoire de tests/version_photo ne prouvent pas : les requêtes de MagasinBase sur le vrai schéma, la règle
d'unicité d'une semaine, la suppression en cascade d'un passage remplacé, le registre de N en ajout seulement, le numéro de version opaque.
SAUTÉS sans base jetable. Données inventées ; le fichier de réglages est un fichier temporaire, jamais Flux-Lab/.
"""
import contextlib
import datetime as dt
import io
import tempfile
import unittest
from pathlib import Path

import test_db as base          # noqa: E402,F401
from test_db import db          # noqa: E402
import test_flow_schema as fs   # noqa: E402
import version_photo as vp      # noqa: E402

MAINTENANT = dt.datetime(2026, 10, 23, 14, 0, tzinfo=dt.timezone.utc)          # un vendredi
REGLAGES = "defect_types: [Bug]\nportfolio_types: [Epic]\n"
MARQUE = "zzversion"


class AvecBase(unittest.TestCase):
    setUp_base = fs.SchemaFlow.setUp
    _supprimer = fs.SchemaFlow._supprimer
    conn = fs.SchemaFlow.conn
    essaie = fs.SchemaFlow.essaie

    def setUp(self):
        self.setUp_base()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.reglages = Path(self.temp.name) / "flux.yaml"
        self.reglages.write_text(REGLAGES, encoding="utf-8")
        self.environ = {"VERSION_PHOTO_SETTINGS": str(self.reglages), "VERSION_PHOTO_NOW": MAINTENANT.isoformat()}
        self.donnees = self.conn()

    def ouvrir(self):
        c = self.conn()
        c.execute("SET ROLE pmzilla_flow")
        return vp.MagasinBase(c)

    def lancer(self, *argv, maintenant=None):
        env = dict(self.environ)
        if maintenant:
            env["VERSION_PHOTO_NOW"] = maintenant.isoformat()
        sortie, erreur = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
            code = vp.main(list(argv), env, ouvrir_magasin=self.ouvrir)
        return code, sortie.getvalue(), erreur.getvalue()

    def ticket(self, cle, type_="Bug", equipe=1, cree="2026-01-05", resolu=None, sorti=False, fix=(), affects=(), periodes=()):
        c = self.donnees
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.issues (key, project, type, status, status_category, created_at, resolved_at, updated_at, team_id, out_of_export_at) "
                  "VALUES (%s, 'PROJ', %s, 'Closed', 'Done', %s, %s, now(), %s, CASE WHEN %s THEN now() END)",
                  (cle, type_, f"{cree}T12:00:00+00", f"{resolu}T12:00:00+00" if resolu else None, equipe, sorti))
        for nom in fix:
            c.execute("INSERT INTO flow.issue_current_versions (issue_key, kind, name) VALUES (%s, 'fix', %s)", (cle, nom))
        for nom in affects:
            c.execute("INSERT INTO flow.issue_current_versions (issue_key, kind, name) VALUES (%s, 'affects', %s)", (cle, nom))
        for nom, pose in periodes:
            c.execute("INSERT INTO flow.issue_version_periods (issue_key, version, added_at) VALUES (%s, %s, %s)", (cle, nom, f"{pose}T12:00:00+00"))
        c.execute("RESET ROLE")
        c.commit()

    def equipes(self):
        self.donnees.execute("SET ROLE pmzilla_flow")
        self.donnees.execute("INSERT INTO flow.teams (name) VALUES ('Alpha')")
        self.donnees.execute("RESET ROLE")
        self.donnees.commit()

    def requete(self, sql, params=()):
        c = self.conn()
        c.execute("SET ROLE pmzilla_flow")
        return c.execute(sql, params).fetchall()

    def jeu(self):
        self.equipes()
        v = f"{MARQUE}-a"
        self.ticket("PROJ-1", resolu="2026-08-12", fix=[v], affects=[v], periodes=[(v, "2026-08-12")])
        self.ticket("PROJ-2", type_="Story", resolu="2026-08-13")
        self.ticket("PROJ-3", type_="Epic", resolu="2026-08-13")
        self.ticket("PROJ-4", resolu="2026-08-12", sorti=True, affects=[v])
        self.ticket("PROJ-5", equipe=None, affects=[v])


class RegistreDesSorties(AvecBase):
    """Change version-release-date, tâche 3.3 : le registre est rempli depuis les versions courantes stockées, et la vue lit la semaine retenue."""

    def sortie(self, nom, date_sortie, drapeau, cle=None):
        c = self.donnees
        c.execute("SET ROLE pmzilla_flow")
        c.execute("UPDATE flow.issue_current_versions SET release_date = %s, released = %s WHERE name = %s AND (%s::text IS NULL OR issue_key = %s)",
                  (date_sortie, drapeau, nom, cle, cle))
        c.execute("RESET ROLE")
        c.commit()

    def adopter_n(self, semaines=6):
        c = self.donnees                                                              # version attendue du marqueur simulée (R-20261104-45 (1) : 3)
        c.execute(f"CREATE OR REPLACE FUNCTION flow.masking_version() RETURNS integer LANGUAGE sql IMMUTABLE AS $$ SELECT {int(vp.VERSION_MASQUAGE_ATTENDUE)} $$")
        c.commit()
        self.assertEqual(self.lancer("adopt-n", "--weeks", str(semaines), "--adopted-on", "2026-10-23")[0], 0)          # le marqueur de la migration 0022 est en place

    def lignes_de_la_vue(self, filtre):
        c = self.conn()
        c.execute("SET ROLE pmzilla_flow_views")
        return c.execute("SELECT week_start, release_date, released FROM flow.v_version_quality_photo WHERE " + filtre).fetchall()

    def test_take_remplit_le_registre_depuis_les_lignes_stockees(self):
        self.equipes()
        v = f"{MARQUE}-a"
        self.ticket("PROJ-1", resolu="2026-10-20", fix=[v], affects=[v])
        self.sortie(v, dt.date(2029, 7, 14), True)
        code, sortie, erreur = self.lancer("take", "--language", "en")
        self.assertEqual(code, 0, erreur)
        self.assertEqual(self.requete("SELECT release_date, released FROM flow.version_photo_versions"), [(dt.date(2029, 7, 14), True)])
        self.assertIn("versions without release date: 0", sortie)
        self.assertIn("versions with conflicting release attributes: 0", sortie)
        for valeur in (MARQUE, "2029", "True"):
            self.assertNotIn(valeur, sortie + erreur)

    def test_une_version_sans_date_reste_nulle_et_une_divergence_donne_null(self):
        self.equipes()
        v, w = f"{MARQUE}-a", f"{MARQUE}-b"
        self.ticket("PROJ-1", resolu="2026-10-20", fix=[v, w], affects=[v])
        self.ticket("PROJ-2", resolu="2026-10-20", fix=[v])
        self.sortie(v, dt.date(2029, 7, 14), True, cle="PROJ-1")
        self.sortie(v, dt.date(2029, 8, 1), True, cle="PROJ-2")                # même nom, deux dates : divergent
        code, sortie, erreur = self.lancer("take", "--language", "en")
        self.assertEqual(code, 0, erreur)
        self.assertEqual(self.requete(f"SELECT name = '{v}', release_date, released FROM flow.version_photo_versions ORDER BY name"),
                         [(True, None, True), (False, None, None)])
        self.assertIn("versions without release date: 2", sortie)
        self.assertIn("versions with conflicting release attributes: 1", sortie)

    def test_une_version_purgee_garde_ses_dernieres_valeurs(self):
        self.equipes()
        v = f"{MARQUE}-a"
        self.ticket("PROJ-1", resolu="2026-10-20", fix=[v], affects=[v])
        self.sortie(v, dt.date(2029, 7, 14), False)
        self.lancer("take", maintenant=dt.datetime(2026, 10, 23, 14, tzinfo=dt.timezone.utc))
        c = self.donnees
        c.execute("SET ROLE pmzilla_flow")
        c.execute("DELETE FROM flow.issues WHERE key = 'PROJ-1'")                # purge : la cascade retire la ligne de version courante
        c.execute("RESET ROLE")
        c.commit()
        code, _, erreur = self.lancer("take", maintenant=dt.datetime(2026, 10, 30, 14, tzinfo=dt.timezone.utc))
        self.assertEqual(code, 0, erreur)
        self.assertEqual(self.requete("SELECT release_date, released FROM flow.version_photo_versions"), [(dt.date(2029, 7, 14), False)])

    def test_version_reportee_un_ancien_ticket_hors_export_ne_compte_plus(self):
        """Décision du 2026-10-23 : le ticket sorti de l'export garde l'ancienne date, ceux de l'export portent la nouvelle : pas de conflit."""
        self.equipes()
        v = f"{MARQUE}-a"
        self.ticket("PROJ-1", resolu="2026-10-20", sorti=True, fix=[v])
        self.ticket("PROJ-2", resolu="2026-10-20", fix=[v])
        self.ticket("PROJ-3", resolu="2026-10-20", affects=[v])
        self.sortie(v, dt.date(2029, 7, 14), False, cle="PROJ-1")
        self.sortie(v, dt.date(2029, 8, 1), True, cle="PROJ-2")
        self.sortie(v, dt.date(2029, 8, 1), True, cle="PROJ-3")
        code, sortie, erreur = self.lancer("take", "--language", "en")
        self.assertEqual(code, 0, erreur)
        self.assertEqual(self.requete("SELECT release_date, released FROM flow.version_photo_versions"), [(dt.date(2029, 8, 1), True)])
        self.assertIn("versions with conflicting release attributes: 0", sortie)

    def test_version_dont_tous_les_tickets_ont_quitte_l_export_garde_la_derniere_date(self):
        self.equipes()
        v = f"{MARQUE}-a"
        self.ticket("PROJ-1", resolu="2026-10-20", fix=[v])
        self.sortie(v, dt.date(2029, 7, 14), True)
        self.assertEqual(self.lancer("take", maintenant=dt.datetime(2026, 10, 23, 14, tzinfo=dt.timezone.utc))[0], 0)
        c = self.donnees
        c.execute("SET ROLE pmzilla_flow")
        c.execute("UPDATE flow.issues SET out_of_export_at = now() WHERE key = 'PROJ-1'")
        c.execute("RESET ROLE")
        c.commit()
        self.sortie(v, dt.date(2030, 1, 1), False)                              # une valeur différente, portée seulement par un ticket sorti
        code, sortie, erreur = self.lancer("take", "--language", "en", maintenant=dt.datetime(2026, 10, 30, 14, tzinfo=dt.timezone.utc))
        self.assertEqual(code, 0, erreur)
        self.assertEqual(self.requete("SELECT release_date, released FROM flow.version_photo_versions"), [(dt.date(2029, 7, 14), True)])
        self.assertIn("versions without release date: 0", sortie)

    def test_deux_take_sans_nouvelle_version_ne_sautent_aucun_numero(self):
        self.equipes()
        v, w = f"{MARQUE}-a", f"{MARQUE}-b"
        self.ticket("PROJ-1", resolu="2026-10-20", fix=[v])
        self.sortie(v, dt.date(2029, 7, 14), True)
        self.assertEqual(self.lancer("take", maintenant=dt.datetime(2026, 10, 23, 14, tzinfo=dt.timezone.utc))[0], 0)
        self.assertEqual(self.lancer("take", maintenant=dt.datetime(2026, 10, 30, 14, tzinfo=dt.timezone.utc))[0], 0)
        self.ticket("PROJ-2", resolu="2026-10-20", fix=[w])
        self.sortie(w, dt.date(2029, 8, 1), False)
        self.assertEqual(self.lancer("take", maintenant=dt.datetime(2026, 11, 6, 14, tzinfo=dt.timezone.utc))[0], 0)
        numeros = [n for n, in self.requete("SELECT version_no FROM flow.version_photo_versions ORDER BY version_no")]
        self.assertEqual(len(numeros), 2)
        self.assertEqual(numeros[1] - numeros[0], 1)                            # aucun numéro consommé par les mises à jour

    def test_un_run_refuse_n_ecrit_rien_dans_le_registre(self):
        self.equipes()
        v = f"{MARQUE}-a"
        self.ticket("PROJ-1", resolu="2026-10-20", fix=[v], affects=[v])
        self.sortie(v, dt.date(2029, 7, 14), True)
        self.lancer("take")
        self.sortie(v, dt.date(2029, 8, 1), False)
        self.assertEqual(self.lancer("take")[0], 3)                              # seconde photo de la semaine : refusée
        self.assertEqual(self.requete("SELECT release_date, released FROM flow.version_photo_versions"), [(dt.date(2029, 7, 14), True)])

    def test_la_vue_rend_la_semaine_retenue_d_une_version_datee_et_la_couverture_seule_sans_date(self):
        self.equipes()
        v, w = f"{MARQUE}-a", f"{MARQUE}-b"
        self.ticket("PROJ-1", resolu="2026-10-20", fix=[v], affects=[v])
        self.ticket("PROJ-2", resolu="2026-10-20", fix=[w], affects=[w])
        self.sortie(v, dt.date(2026, 11, 30), False)                              # le lundi 2026-11-30 moins 6 semaines : la semaine du 2026-10-19
        self.assertEqual(self.lancer("take")[0], 0)
        self.assertEqual(self.lignes_de_la_vue("version_no IS NOT NULL"), [])      # avant N : aucune ligne de version, même datée
        self.adopter_n(6)
        retenues = self.lignes_de_la_vue("version_no IS NOT NULL")
        self.assertTrue(retenues)
        self.assertEqual({ligne for ligne in retenues}, {(dt.date(2026, 10, 19), dt.date(2026, 11, 30), False)})
        no_w = self.requete(f"SELECT version_no FROM flow.version_photo_versions WHERE name = '{w}'")[0][0]
        c = self.conn()
        c.execute("SET ROLE pmzilla_flow_views")
        self.assertEqual(c.execute("SELECT count(*) FROM flow.v_version_quality_photo WHERE version_no = %s", (no_w,)).fetchone()[0], 0)
        self.assertGreater(c.execute("SELECT count(*) FROM flow.v_version_quality_photo WHERE version_no IS NULL AND team IS NULL").fetchone()[0], 0)


class Reconstruction(AvecBase):
    def test_reconstruction_sur_le_vrai_schema(self):
        self.jeu()
        code, sortie, erreur = self.lancer("reconstruct", "--language", "en")
        self.assertEqual(code, 0, erreur)
        self.assertIn("reconstruction: 10 weeks, 1 versions, 0 partial weeks", sortie)
        self.assertNotIn(MARQUE, sortie + erreur)
        self.assertEqual(self.requete("SELECT source, count(*) FROM flow.version_photo_runs GROUP BY source"), [("reconstructed", 1)])
        self.assertEqual(self.requete("SELECT count(*), min(week_start), max(week_start) FROM flow.version_photo_weeks"),
                         [(10, dt.date(2026, 8, 10), dt.date(2026, 10, 12))])
        premiere = self.requete("SELECT team, found, found_open, corrected_at_week, corrected_now, reopened FROM flow.version_photo_rows "
                                "WHERE week_start = '2026-08-10' AND version_no IS NOT NULL")
        self.assertEqual(sorted(premiere), [("(sans équipe)", 1, 1, 0, 0, 0), ("Alpha", 1, 0, 1, 1, 0)])       # PROJ-4 sorti de l'export : écarté
        libre = self.requete("SELECT team, defects_created, defects_without_affects, resolved_week, resolved_week_defects FROM flow.version_photo_rows "
                             "WHERE week_start = '2026-08-10' AND version_no IS NULL")
        self.assertEqual(sorted(libre), [("(sans équipe)", 1, 0, 0, 0), ("Alpha", 1, 0, 2, 1)])               # la Story compte, l'Epic non
        self.assertEqual(self.requete("SELECT release_date, released FROM flow.version_photo_versions"), [(None, None)])

    def test_seconde_reconstruction_refusee_replace_accepte(self):
        self.jeu()
        self.lancer("reconstruct")
        avant = self.requete("SELECT count(*) FROM flow.version_photo_rows")
        code, sortie, _ = self.lancer("reconstruct", "--language", "en")
        self.assertEqual(code, 3)
        self.assertIn("reconstruction already done: use --replace", sortie)
        self.assertEqual(self.requete("SELECT count(*) FROM flow.version_photo_rows"), avant)
        code, sortie, _ = self.lancer("reconstruct", "--replace", "--language", "en")
        self.assertEqual(code, 0)
        self.assertTrue(sortie.startswith("warning: a reconstruction run again is more partial"))
        self.assertEqual(self.requete("SELECT count(*) FROM flow.version_photo_rows"), avant)
        self.assertEqual(self.requete("SELECT count(*) FROM flow.version_photo_runs"), [(1,)])           # l'ancien passage est parti en cascade

    def test_replace_garde_les_semaines_que_la_purge_a_rendues_non_recalculables(self):
        self.jeu()
        self.ticket("PROJ-6", resolu="2026-09-02")                                                  # la semaine du 2026-08-31
        self.lancer("reconstruct")
        anciennes = self.requete("SELECT week_start, team, found, defects_created FROM flow.version_photo_rows "
                                 "WHERE week_start < '2026-08-31' ORDER BY week_start, team, version_no")
        self.assertTrue(anciennes)
        c = self.donnees
        c.execute("SET ROLE pmzilla_flow")
        c.execute("DELETE FROM flow.issues WHERE key IN ('PROJ-1', 'PROJ-2', 'PROJ-3', 'PROJ-4')")      # purge simulée des plus anciens tickets résolus
        c.execute("RESET ROLE")
        c.commit()
        code, sortie, erreur = self.lancer("reconstruct", "--replace", "--language", "en")
        self.assertEqual(code, 0, erreur)
        self.assertIn("warning: 3 older reconstructed weeks kept as they are, no longer recomputable", sortie)
        self.assertEqual(self.requete("SELECT week_start, team, found, defects_created FROM flow.version_photo_rows "
                                      "WHERE week_start < '2026-08-31' ORDER BY week_start, team, version_no"), anciennes)
        # décision 2 du 2026-10-23 : le recalcul est un nouveau passage, l'ancien garde ses trois semaines non recalculables
        self.assertEqual(self.requete("SELECT count(*) FROM flow.version_photo_runs WHERE source = 'reconstructed'"), [(2,)])
        self.assertEqual(self.requete("SELECT count(*) FROM flow.version_photo_weeks"), [(10,)])
        self.assertEqual(sorted(n for _, n in self.requete("SELECT run_id, count(*) FROM flow.version_photo_weeks GROUP BY run_id")), [3, 7])

    def test_replace_garde_les_photos_vivantes(self):
        self.jeu()
        self.lancer("reconstruct")
        self.lancer("take", maintenant=dt.datetime(2026, 10, 23, 14, tzinfo=dt.timezone.utc))
        self.lancer("take", maintenant=dt.datetime(2026, 10, 30, 14, tzinfo=dt.timezone.utc))
        vivantes = self.requete("SELECT w.week_start, count(r.*) FROM flow.version_photo_weeks w JOIN flow.version_photo_runs p ON p.id = w.run_id "
                                "LEFT JOIN flow.version_photo_rows r ON r.week_start = w.week_start WHERE p.source = 'live' "
                                "GROUP BY w.week_start ORDER BY w.week_start")
        self.assertEqual(len(vivantes), 2)
        code, _, erreur = self.lancer("reconstruct", "--replace", maintenant=dt.datetime(2026, 11, 6, 14, tzinfo=dt.timezone.utc))
        self.assertEqual(code, 0, erreur)
        apres = self.requete("SELECT w.week_start, count(r.*) FROM flow.version_photo_weeks w JOIN flow.version_photo_runs p ON p.id = w.run_id "
                             "LEFT JOIN flow.version_photo_rows r ON r.week_start = w.week_start WHERE p.source = 'live' "
                             "GROUP BY w.week_start ORDER BY w.week_start")
        self.assertEqual(apres, vivantes)

    def test_types_de_defaut_non_regles_rien_n_est_ecrit(self):
        self.jeu()
        self.reglages.write_text("jira_site: x\n", encoding="utf-8")
        code, sortie, _ = self.lancer("reconstruct", "--language", "en")
        self.assertEqual(code, 3)
        self.assertIn("defect types not set", sortie)
        self.assertEqual(self.requete("SELECT count(*) FROM flow.version_photo_runs"), [(0,)])


class PhotoVivante(AvecBase):
    def test_photo_puis_seconde_refusee_puis_replace(self):
        self.jeu()
        code, sortie, erreur = self.lancer("take", "--language", "en")
        self.assertEqual(code, 0, erreur)
        self.assertIn("photo taken: week of 2026-10-19", sortie)
        self.assertEqual(self.requete("SELECT p.source, w.coverage FROM flow.version_photo_weeks w JOIN flow.version_photo_runs p ON p.id = w.run_id"),
                         [("live", "complete")])
        lignes = self.requete("SELECT count(*) FROM flow.version_photo_rows")
        code, sortie, _ = self.lancer("take", "--language", "en")
        self.assertEqual(code, 3)
        self.assertIn("photo already taken for this week: use --replace", sortie)
        self.assertEqual(self.requete("SELECT count(*) FROM flow.version_photo_rows"), lignes)
        self.assertEqual(self.lancer("take", "--replace")[0], 0)
        self.assertEqual(self.requete("SELECT count(*) FROM flow.version_photo_runs"), [(1,)])
        self.assertEqual(self.requete("SELECT count(*) FROM flow.version_photo_rows"), lignes)

    def test_photo_vivante_deux_comptes_egaux(self):
        v = f"{MARQUE}-a"
        self.equipes()
        self.ticket("PROJ-1", resolu="2026-10-20", fix=[v], affects=[v])               # aucune période : historique jamais collecté
        code, sortie, _ = self.lancer("take", "--language", "en")
        self.assertEqual(code, 0)
        self.assertIn("defects without fix version history: 1", sortie)
        self.assertEqual(self.requete("SELECT corrected_at_week, corrected_now FROM flow.version_photo_rows WHERE version_no IS NOT NULL"), [(1, 1)])


class AdoptionDeN(AvecBase):
    """La base jetable porte toutes les migrations, donc le marqueur flow.masking_version() de la migration 0022 (change masking-sums, D9) ;
    les cas sans marqueur ou à version différente le retirent ou le remplacent sous le propriétaire, dans une base propre à chaque test."""

    def retirer_le_marqueur(self):
        self.donnees.execute("DROP FUNCTION flow.masking_version()")
        self.donnees.commit()

    def poser_le_marqueur(self, version):
        self.donnees.execute(f"CREATE OR REPLACE FUNCTION flow.masking_version() RETURNS integer LANGUAGE sql IMMUTABLE AS $$ SELECT {int(version)} $$")
        self.donnees.commit()

    def adopter(self):
        return self.lancer("adopt-n", "--weeks", "6", "--adopted-on", "2026-11-20", "--language", "en")

    def test_le_marqueur_de_la_migration_est_deux_et_l_outil_attend_trois(self):
        """R-20261104-45 (1) : la migration 0035 (D15) pose la version 2, adopt-n attend la version 3 dès le groupe 6 ; la 3 viendra des groupes 7 et 8."""
        self.assertEqual(self.requete("SELECT flow.masking_version()"), [(2,)])
        self.assertEqual(vp.VERSION_MASQUAGE_ATTENDUE, 3)

    def test_garde_refus_sans_marqueur_et_rien_n_est_ecrit(self):
        """D9 : fonction absente (erreur de fonction indéfinie lue comme un refus), refus 3 et rien d'écrit, même avec une migration dont le nom contient
        `masquage_somme` dans public.schema_migrations."""
        self.retirer_le_marqueur()
        code, sortie, erreur = self.adopter()
        self.assertEqual((code, erreur), (3, ""))
        self.assertEqual(sortie.strip(), vp.CATALOGS["en"]["crossing_masking_missing"])
        self.assertEqual(self.requete("SELECT count(*) FROM flow.version_photo_n"), [(0,)])

    def test_garde_refus_quand_le_marqueur_est_inferieur_et_rien_n_est_ecrit(self):
        self.poser_le_marqueur(vp.VERSION_MASQUAGE_ATTENDUE - 1)
        code, sortie, _ = self.adopter()
        self.assertEqual((code, sortie.strip()), (3, vp.CATALOGS["en"]["crossing_masking_version"].format(
            installed=vp.VERSION_MASQUAGE_ATTENDUE - 1, expected=vp.VERSION_MASQUAGE_ATTENDUE)))
        self.assertEqual(self.requete("SELECT count(*) FROM flow.version_photo_n"), [(0,)])

    def test_garde_refus_avec_le_marqueur_de_la_migration_0035_sans_rien_poser(self):
        """R-20261104-45 (1) : la base jetable porte la version 2 de la migration 0035 : adopt-n refuse tant que les groupes 7 et 8 n'ont pas posé la 3."""
        code, sortie, _ = self.adopter()
        self.assertEqual((code, sortie.strip()), (3, vp.CATALOGS["en"]["crossing_masking_version"].format(installed=2, expected=3)))
        self.assertEqual(self.requete("SELECT count(*) FROM flow.version_photo_n"), [(0,)])

    def test_garde_acceptation_avec_le_marqueur_attendu(self):
        self.poser_le_marqueur(vp.VERSION_MASQUAGE_ATTENDUE)                           # version 3 simulée (celle que poseront les groupes 7 et 8)
        code, sortie, _ = self.adopter()
        self.assertEqual((code, sortie.strip()), (0, "N adopted: 6 weeks, on 2026-11-20"))

    def test_garde_acceptation_avec_un_marqueur_superieur(self):
        self.poser_le_marqueur(vp.VERSION_MASQUAGE_ATTENDUE + 1)
        code, sortie, _ = self.adopter()
        self.assertEqual((code, sortie.strip()), (0, "N adopted: 6 weeks, on 2026-11-20"))
        self.assertEqual(self.requete("SELECT count(*) FROM flow.version_photo_n"), [(1,)])

    def test_registre_en_ajout_seulement_et_derniere_adoption_effective(self):
        self.poser_le_marqueur(vp.VERSION_MASQUAGE_ATTENDUE)                           # version 3 simulée : l'adoption est acceptée
        self.assertEqual(self.lancer("adopt-n", "--weeks", "6", "--adopted-on", "2026-11-20", "--language", "en")[1].strip(), "N adopted: 6 weeks, on 2026-11-20")
        code, sortie, _ = self.lancer("adopt-n", "--weeks", "8", "--adopted-on", "2026-12-01", "--language", "en")
        self.assertEqual(code, 3)
        self.assertEqual(sortie.strip(), "N already adopted: give --reason")
        self.assertEqual(self.requete("SELECT count(*) FROM flow.version_photo_n"), [(1,)])
        code, sortie, _ = self.lancer("adopt-n", "--weeks", "8", "--adopted-on", "2026-12-01", "--reason", "zzraison", "--language", "en")
        self.assertEqual(code, 0)
        self.assertNotIn("zzraison", sortie)
        self.assertEqual(self.requete("SELECT weeks, adopted_on, reason FROM flow.version_photo_n ORDER BY id"),
                         [(6, dt.date(2026, 11, 20), None), (8, dt.date(2026, 12, 1), "zzraison")])


class ErreurDeBase(AvecBase):
    def test_erreur_nom_du_type_seul(self):
        def ouvrir():
            raise db.psycopg.errors.OperationalError("zzversion secret")
        sortie, erreur = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
            code = vp.main(["take", "--language", "en"], self.environ, ouvrir_magasin=ouvrir)
        self.assertEqual(code, 1)
        self.assertEqual(erreur.getvalue().strip(), "Error: OperationalError")


if __name__ == "__main__":
    unittest.main()
