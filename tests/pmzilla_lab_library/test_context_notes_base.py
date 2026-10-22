"""
La recherche des notes de contexte sur une base jetable (organisation-context, design D4 et D5 ; tâche 4.2). Sautée sans base ; lancée
par l'utilisateur avec bash tools/dbtest.sh. Jamais la vraie base.

Une note inventée est indexée par l'option --context à côté de la bibliothèque inventée de tests/pmzilla_lab_library (les formes figées de
la bibliothèque de démonstration ne changent pas), puis lue par PostgresLibrary : recherche par défaut sans la note, recherche qui nomme la
collection avec la note, champs d'en-tête et marque stale avec une date injectée, filtre de date qui garde les notes, liste des collections.
"""
import contextlib
import datetime as dt
import io
import os
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "context_lab"))
from fixtures_context import IDENTIFIANT, Contexte, note  # noqa: E402
from test_pmzilla_lab_library import LectureEnBase, fake_embed_1024, knowledge_library, library  # noqa: E402
import identifiants_personnels  # noqa: E402
import private_collections  # noqa: E402

CONTEXTE = private_collections.CONTEXT_COLLECTION
NOTE = "2026-09-01-organisation-de-test.md"
CORPS = ("## Périmètre\n\nLa limite de travail en cours et le débit des équipes alignées sur un flux : une organisation inventée, "
         "avec un forum mensuel de décisions et une liste de dépendances entre équipes.\n")
QUESTION = "limite de travail en cours débit équipes flux organisation"


class RechercheDesNotes(LectureEnBase):
    def setUp(self):
        super().setUp()
        self.ctx = Contexte(notes={NOTE: note(body=CORPS, review="2026-12-01")})
        self.addCleanup(self.ctx.close)
        # La fausse liste et de faux identifiants, jamais les vrais (context-index-name-guard, D7).
        for patch in (mock.patch.dict(os.environ, {"PMZILLA_LAB_SENSITIVE_NAMES": str(self.ctx.liste), "PMZILLA_NOMS": str(self.ctx.liste)}),
                      mock.patch.object(identifiants_personnels, "identifiants", return_value=[IDENTIFIANT])):
            patch.start()
            self.addCleanup(patch.stop)
        with contextlib.redirect_stdout(io.StringIO()):
            library.index([self.racine], store=self.store, context=self.ctx.dossier)

    def lire(self, aujourdhui=None):
        return knowledge_library.PostgresLibrary(connect=self.base.connect, embed=fake_embed_1024, today=aujourdhui)

    def fichiers(self, resultats):
        return {r["file"] for r in resultats}

    def test_recherche_par_defaut_sans_la_note(self):
        trouve = self.lire().search(QUESTION, None, 14)
        self.assertTrue(trouve)
        self.assertNotIn(NOTE, self.fichiers(trouve))
        self.assertIn("Flux.md", self.fichiers(trouve))

    def test_recherche_nommee_avec_la_note_ses_champs_et_stale(self):
        trouve = self.lire(dt.date(2027, 1, 5)).search(QUESTION, [CONTEXTE], 8)
        self.assertEqual(self.fichiers(trouve), {NOTE})
        premier = trouve[0]
        self.assertEqual((premier["note_date"], premier["nature"], premier["review_date"]), ("2026-09-01", "declarative", "2026-12-01"))
        self.assertIs(premier["stale"], True)
        self.assertNotIn("author", premier)
        self.assertNotIn("url", premier)
        self.assertEqual(premier["collections"], [CONTEXTE])

    def test_note_a_jour_stale_faux(self):
        trouve = self.lire(dt.date(2026, 10, 18)).search(QUESTION, [CONTEXTE], 8)
        self.assertIs(trouve[0]["stale"], False)

    def test_le_filtre_de_date_garde_les_notes(self):
        trouve = self.lire().search(QUESTION, [CONTEXTE], 8, "2027-01-01")
        self.assertEqual(self.fichiers(trouve), {NOTE})

    def test_les_collections_montrent_celle_du_contexte_avec_son_compte(self):
        self.assertEqual(self.lire().collections()[CONTEXTE], 1)
        livres = self.lire().books(CONTEXTE)
        self.assertEqual([b["file"] for b in livres], [NOTE])

    def test_read_passage_porte_les_champs_de_la_note(self):
        biblio = self.lire(dt.date(2027, 1, 5))
        premier = biblio.search(QUESTION, [CONTEXTE], 8)[0]
        lu = biblio.read(premier["passage_id"], 0, 1)
        self.assertEqual((lu["note_date"], lu["review_date"], lu["stale"]), ("2026-09-01", "2026-12-01", True))
        self.assertNotIn("author", lu)
