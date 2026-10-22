"""
Le SQL de `analyse` et `coach` (tools/story_quality_audit_store.py) sur la BASE JETABLE (change story-quality-audit, tâche 3.9 ; design D7,
« Data model ») : sauté sans le repère DBTEST_PORT de bash tools/dbtest.sh (même règle que test_magasin_base.py). Vérifie aussi qu'un
coaching et un échantillon ne changent aucun compte des vues de qualité. La vraie base n'est jamais ouverte ; données inventées.

    bash tools/dbtest.sh story_quality
"""
from __future__ import annotations

import contextlib
import datetime as dt
import secrets
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
sys.path.insert(0, str(RACINE / "tests" / "db"))
import db  # noqa: E402
import story_quality_audit_store as audit_store  # noqa: E402
import story_quality_store as store  # noqa: E402
import test_db  # noqa: E402  (la garde des tests avec base : une seule règle)

INSTANT = dt.datetime(2026, 9, 1, 10, 0, tzinfo=dt.timezone.utc)
PAIRE = ("socle-fictif", "3", "", "")
PAIRE_SURCOUCHE = ("socle-fictif", "3", "surcouche-fictive", "2")
VERDICTS = [("story-un", "core", "ticket_template", "met"), ("story-deux", "core", "refinement", "not_met")]
VUES = ("quality_by_team", "quality_coverage_by_team", "quality_by_product")


def element(cle, equipes=("Alpha",)):
    return store.Element(key=cle, kind="story", parent_key=None, status_category="new", created_at=INSTANT, updated_at=INSTANT,
                         resolved_at=None, teams=list(equipes), title="zztitre " + cle, description="d", acceptance_criteria="",
                         content_hash="h-" + cle, replacements=0)


class MagasinAnalyseSurBaseJetable(unittest.TestCase):
    def setUp(self):
        if not test_db.BASE_DISPONIBLE:
            self.skipTest(test_db.MESSAGE_SAUT)
        self.nom_base = "pmzilla_test_" + secrets.token_hex(6)
        self.admin = db.connect(test_db.URL_BASE, password=test_db.MOT_DE_PASSE, autocommit=True)
        self.addCleanup(self._supprimer)
        self.admin.execute(f'CREATE DATABASE "{self.nom_base}"')
        url = test_db.url_vers(self.nom_base)
        migration = db.connect(url, password=test_db.MOT_DE_PASSE)
        db.migrer(migration, db.lister_migrations(db.DOSSIER_MIGRATIONS))
        migration.commit()
        migration.close()
        self.conn = db.connect(url, password=test_db.MOT_DE_PASSE)
        self.conn.execute(f"SET ROLE {store.ROLE}")
        self.conn.commit()
        self.verif = db.connect(url, password=test_db.MOT_DE_PASSE, autocommit=True)
        self.magasin = audit_store.MagasinAnalyse(self.conn)
        self.magasin.enregistrer_collecte([element(f"PROJ-{i}") for i in range(1, 7)] + [element("PROJ-9", ("Alpha", "Beta"))], {},
                                          complet=True)

    def _supprimer(self):
        for nom in ("conn", "verif"):
            with contextlib.suppress(Exception):
                getattr(self, nom).close()
        with contextlib.suppress(Exception):
            self.admin.execute(f'DROP DATABASE IF EXISTS "{self.nom_base}" WITH (FORCE)')
        self.admin.close()

    def lignes(self, sql, params=()):
        return self.verif.execute(sql, params).fetchall()

    def vues(self):
        return {v: sorted(map(repr, self.lignes(f"SELECT * FROM quality.{v}"))) for v in VUES}

    def test_elements_textes_et_relectures(self):
        elements = self.magasin.elements()
        self.assertEqual([e["key"] for e in elements], [f"PROJ-{i}" for i in range(1, 7)] + ["PROJ-9"])
        self.assertEqual(elements[-1]["teams"], ["Alpha", "Beta"])
        self.assertEqual(elements[0]["updated_at"], INSTANT)
        self.assertEqual(elements[0]["content_hash"], "h-PROJ-1")
        self.assertEqual(self.magasin.textes(["PROJ-1", "PROJ-404"]), {"PROJ-1": ("zztitre PROJ-1", "d", "", "h-PROJ-1")})
        self.assertEqual(self.magasin.equipes_relues(), set())
        self.magasin.enregistrer_relecture("Alpha", 3)
        self.assertEqual(self.magasin.equipes_relues(), {"Alpha"})

    def test_audit_remplace_a_la_meme_paire_et_garde_les_autres(self):
        self.magasin.enregistrer_audit("PROJ-1", PAIRE, VERDICTS, False)
        self.magasin.enregistrer_audit("PROJ-1", PAIRE, VERDICTS[:1], False)
        self.magasin.enregistrer_audit("PROJ-1", PAIRE_SURCOUCHE, VERDICTS, False)
        self.assertEqual(self.lignes("SELECT count(*) FROM quality.assessments WHERE overlay_id = ''")[0][0], 1)
        self.assertEqual(self.lignes("SELECT count(*) FROM quality.assessments WHERE overlay_id <> ''")[0][0], 2)
        self.assertEqual(self.magasin.derniers_audits(PAIRE), {"PROJ-1": None})       # sans empreinte : à réauditer
        self.assertEqual(self.magasin.derniers_audits(("socle-fictif", "4", "", "")), {})

    def test_l_empreinte_stockee_est_celle_du_texte_envoye(self):
        texte = self.magasin.textes(["PROJ-1"])["PROJ-1"]
        self.magasin.enregistrer_collecte([element("PROJ-1")], {}, complet=False)     # recollecte pendant l'envoi : même texte
        self.magasin.enregistrer_audit("PROJ-1", PAIRE, VERDICTS, False, texte[3])
        self.assertEqual({r[0] for r in self.lignes("SELECT content_hash FROM quality.assessments WHERE item_key = 'PROJ-1'")},
                         {"h-PROJ-1"})
        self.assertEqual(self.magasin.derniers_audits(PAIRE), {"PROJ-1": "h-PROJ-1"})
        nouveau = element("PROJ-1")
        nouveau.content_hash = "h-nouveau"
        self.magasin.enregistrer_collecte([nouveau], {}, complet=False)
        self.assertEqual(next(e for e in self.magasin.elements() if e["key"] == "PROJ-1")["content_hash"], "h-nouveau")
        self.assertEqual(self.magasin.derniers_audits(PAIRE), {"PROJ-1": "h-PROJ-1"})     # l'audit garde l'empreinte envoyée

    def test_dernier_audit_le_plus_recent_seulement(self):
        self.magasin.enregistrer_audit("PROJ-2", PAIRE, VERDICTS[:1], False, "h-a")
        self.verif.execute("UPDATE quality.assessments SET analysed_at = analysed_at - interval '1 day' WHERE item_key = 'PROJ-2'")
        self.magasin.enregistrer_audit("PROJ-2", PAIRE_SURCOUCHE, VERDICTS[:1], False, "h-b")
        self.assertEqual(self.magasin.derniers_audits(PAIRE), {"PROJ-2": "h-a"})          # par paire
        self.assertEqual(self.magasin.derniers_audits(PAIRE_SURCOUCHE), {"PROJ-2": "h-b"})

    def test_migration_0015_colonne_sans_texte(self):
        colonnes = self.lignes("SELECT data_type, is_nullable FROM information_schema.columns "
                               "WHERE table_schema = 'quality' AND table_name = 'assessments' AND column_name = 'content_hash'")
        self.assertEqual(colonnes, [("text", "YES")])

    def test_echantillon_ne_touche_jamais_un_audit_et_ne_compte_dans_aucune_vue(self):
        for i in range(1, 7):
            self.magasin.enregistrer_audit(f"PROJ-{i}", PAIRE, VERDICTS, False)
        avant = self.vues()
        self.magasin.enregistrer_audit("PROJ-1", PAIRE, [(c, o, l, "undetermined") for c, o, l, _ in VERDICTS], True)
        self.magasin.enregistrer_audit("PROJ-1", PAIRE, [(c, o, l, "not_met") for c, o, l, _ in VERDICTS], True)
        self.assertEqual(self.lignes("SELECT count(*) FROM quality.assessments WHERE sample")[0][0], 2)
        self.assertEqual(self.lignes("SELECT count(*) FROM quality.assessments WHERE NOT sample AND item_key = 'PROJ-1'")[0][0], 2)
        self.assertEqual(self.vues(), avant)
        self.assertEqual(set(self.magasin.derniers_audits(PAIRE)), {f"PROJ-{i}" for i in range(1, 7)})

    def test_un_coaching_ne_change_aucun_compte_des_vues(self):
        for i in range(1, 7):
            self.magasin.enregistrer_audit(f"PROJ-{i}", PAIRE, VERDICTS, False)
        avant = self.vues()
        for i in range(1, 7):
            self.magasin.enregistrer_coaching(f"PROJ-{i}", PAIRE, [("story-un", "not_met", "zzretour"), ("story-deux", "met", "")])
        self.magasin.enregistrer_coaching("PROJ-1", PAIRE, [("story-un", "met", "nouveau")])
        self.assertEqual(self.vues(), avant)
        self.assertEqual(self.magasin.lire_coaching(["PROJ-1", "PROJ-2", "PROJ-404"]),
                         {"PROJ-1": [("story-un", "met", "nouveau")],
                          "PROJ-2": [("story-un", "not_met", "zzretour"), ("story-deux", "met", "")]})

    def test_empreinte_de_surcouche_posee_une_fois(self):
        self.assertIsNone(self.magasin.empreinte_surcouche("surcouche-fictive", "2"))
        self.assertEqual(self.magasin.enregistrer_empreinte("surcouche-fictive", "2", "e1"), "e1")
        self.assertEqual(self.magasin.enregistrer_empreinte("surcouche-fictive", "2", "e2"), "e1")    # l'appelant voit l'autre
        self.assertEqual(self.magasin.empreinte_surcouche("surcouche-fictive", "2"), "e1")

    def test_verdict_hors_liste_annule_toute_l_ecriture(self):
        self.magasin.enregistrer_audit("PROJ-1", PAIRE, VERDICTS, False)
        with self.assertRaises(db.psycopg.Error):
            self.magasin.enregistrer_audit("PROJ-1", PAIRE, [VERDICTS[0], ("story-deux", "core", "refinement", "peut-etre")], False)
        self.assertEqual(self.lignes("SELECT count(*) FROM quality.assessments WHERE item_key = 'PROJ-1'")[0][0], 2)


if __name__ == "__main__":
    unittest.main()
