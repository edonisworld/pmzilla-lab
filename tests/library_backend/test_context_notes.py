"""
Le serveur et les notes de contexte (organisation-context, design D5 ; tâche 4.2) : tools/knowledge_library.py et le serveur de
tools/pmzilla_lab_library.py. Sans base, sans Ollama, sans paquet `mcp` : une fausse connexion, une recherche SQL simulée, un faux FastMCP.

    bash tests/run_all.sh library_backend

La recherche réelle sur une base jetable (note indexée à côté de la bibliothèque inventée) est dans tests/pmzilla_lab_library/
test_context_notes_base.py (sautée sans base). Les formes figées de la bibliothèque inventée (demo_expected.py) ne changent pas.
"""
import datetime as dt
import sys
import unittest
from pathlib import Path
from unittest import mock

import pg_demo                  # noqa: F401  (ajoute tools/, tests/db et tests/fixtures_library au chemin)
import demo_library as demo     # noqa: E402
import hybrid_search            # noqa: E402
import knowledge_library as kl  # noqa: E402
import pmzilla_lab_library as library  # noqa: E402
import private_collections      # noqa: E402
from aides_serveur import FauxFastMCP, modules_mcp  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "context_lab"))
import identifiants_personnels  # noqa: E402

RACINE = Path(__file__).resolve().parents[2]
CONTEXTE = private_collections.CONTEXT_COLLECTION


class FausseBase:
    def rollback(self):
        pass


def ligne_de_note(review="2026-12-01", position=0):
    return {"id": 7, "position": position, "section": "Périmètre", "text": "Une organisation inventée.", "kind": "text", "ref": {},
            "title": "Organisation de test", "file": "2026-09-01-organisation-de-test.md",
            "meta": {"note_date": "2026-09-01", "nature": "declarative", "source": "entretien avec un rôle", "review_date": review},
            "names": [CONTEXTE]}


def ligne_de_livre():
    return {"id": 1, "position": 0, "section": "S", "text": "Un livre.", "kind": "text", "ref": {}, "title": "Livre", "file": "livre.md",
            "meta": {}, "names": ["flow"]}


class Filtre(unittest.TestCase):
    def setUp(self):
        self.captured = {}

        def fake(conn, spec, **options):
            self.captured = options
            return [(7, 0.5)]
        patch = mock.patch.object(hybrid_search, "hybrid_search", side_effect=fake)
        patch.start()
        self.addCleanup(patch.stop)
        self.lib = kl.PostgresLibrary(connect=FausseBase, embed=demo.fake_embed, today=dt.date(2026, 10, 18))
        self.lib._describe_many = lambda ids: {7: ligne_de_note()}

    def test_une_recherche_sans_collection_exclut_les_privees(self):
        self.lib.search("organisation", None, 8)
        self.assertEqual(self.captured["exclude_collections"], [CONTEXTE])
        self.lib.search("organisation", [], 8)
        self.assertEqual(self.captured["exclude_collections"], [CONTEXTE])

    def test_une_recherche_qui_nomme_la_collection_ne_l_exclut_pas(self):
        self.lib.search("organisation", [CONTEXTE], 8)
        self.assertIsNone(self.captured["exclude_collections"])
        self.assertEqual(self.captured["collections"], [CONTEXTE])

    def test_le_filtre_de_date_est_transmis_et_ne_retire_pas_les_notes(self):
        self.lib.search("organisation", [CONTEXTE], 8, "2027-01-01")
        self.assertEqual(self.captured["since"], "2027-01-01")
        sql, _ = hybrid_search.build_query(hybrid_search.LIBRARY_SPEC, query="x", vector=[0.1], collections=[CONTEXTE], since="2027-01-01")
        self.assertIn("b.published_on IS NULL OR b.published_on >= %(since)s", sql)       # une note n'a pas de date de publication


class EnTeteEtMarque(unittest.TestCase):
    def bibliotheque(self, aujourdhui):
        lib = kl.PostgresLibrary(connect=FausseBase, embed=demo.fake_embed, today=aujourdhui)
        self.addCleanup(mock.patch.stopall)
        patch = mock.patch.object(hybrid_search, "hybrid_search", return_value=[(7, 0.5)])
        patch.start()
        self.addCleanup(patch.stop)
        lib._describe_many = lambda ids: {7: ligne_de_note(), 1: ligne_de_livre()}
        return lib

    def test_une_note_a_revoir_porte_ses_champs_et_stale_vrai_sans_auteur_ni_url(self):
        [trouve] = self.bibliotheque(dt.date(2026, 12, 2)).search("organisation", [CONTEXTE], 8)
        self.assertEqual((trouve["note_date"], trouve["nature"], trouve["source"], trouve["review_date"]),
                         ("2026-09-01", "declarative", "entretien avec un rôle", "2026-12-01"))
        self.assertIs(trouve["stale"], True)
        self.assertNotIn("author", trouve)
        self.assertNotIn("url", trouve)

    def test_une_note_a_jour_porte_stale_faux(self):
        [trouve] = self.bibliotheque(dt.date(2026, 12, 1)).search("organisation", [CONTEXTE], 8)
        self.assertIs(trouve["stale"], False)         # la revue du jour même n'est pas encore passée

    def test_la_date_du_jour_est_celle_de_paris_quand_rien_n_est_injecte(self):
        lib = kl.PostgresLibrary(connect=FausseBase, embed=demo.fake_embed)
        self.assertEqual(lib._paris_today(), dt.datetime.now(__import__("zoneinfo").ZoneInfo("Europe/Paris")).date())

    def test_une_date_de_revue_illisible_est_marquee_stale(self):
        marque = kl.PostgresLibrary(connect=FausseBase, embed=demo.fake_embed, today=dt.date(2026, 1, 1))._mark_stale(
            {"review_date": "pas-une-date"})
        self.assertIs(marque["stale"], True)

    def test_un_livre_ne_recoit_aucun_champ_de_note(self):
        lib = kl.PostgresLibrary(connect=FausseBase, embed=demo.fake_embed, today=dt.date(2026, 12, 2))
        décrit = lib._mark_stale(kl.PostgresLibrary._shape(ligne_de_livre(), score=0.1))
        for champ in kl.CONTEXT_FIELDS:
            self.assertNotIn(champ, décrit)

    def test_read_passage_porte_les_champs_en_tete_et_par_passage(self):
        lib = kl.PostgresLibrary(connect=FausseBase, embed=demo.fake_embed, today=dt.date(2026, 12, 2))
        reponses = iter([[(5, 0)], [(7,), (8,)]])
        lib._query = lambda sql, params=(): next(reponses)
        lib._describe_many = lambda ids: {7: ligne_de_note(position=0), 8: {**ligne_de_note(position=1), "id": 8}}
        lu = lib.read(7, 0, 1)
        for champ in ("note_date", "nature", "source", "review_date", "stale"):
            self.assertIn(champ, lu)
            self.assertTrue(all(champ in p for p in lu["passages"]), champ)
        self.assertIs(lu["stale"], True)
        for interdit in ("author", "url", "published"):
            self.assertNotIn(interdit, lu)
            self.assertFalse(any(interdit in p for p in lu["passages"]))

    def test_read_passage_d_un_livre_garde_sa_forme(self):
        lib = kl.PostgresLibrary(connect=FausseBase, embed=demo.fake_embed, today=dt.date(2026, 12, 2))
        reponses = iter([[(5, 0)], [(1,)]])
        lib._query = lambda sql, params=(): next(reponses)
        lib._describe_many = lambda ids: {1: ligne_de_livre()}
        lu = lib.read(1, 0, 0)
        self.assertEqual(sorted(lu), ["book", "file", "passages"])
        self.assertEqual(sorted(lu["passages"][0]), ["kind", "passage_id", "position", "section", "text"])


class Description(unittest.TestCase):
    def description(self):
        with mock.patch.dict(sys.modules, modules_mcp()), mock.patch.object(library, "open_library", return_value=object()):
            library.serve()
        return FauxFastMCP.instance.tools["search_library"].__doc__

    def test_la_description_nomme_la_collection_par_la_constante_et_dit_qu_elle_se_cherche_nommee(self):
        texte = self.description()
        self.assertIn(f'The collection "{CONTEXTE}" holds the user\'s organisation context notes', texte)
        self.assertIn("searched only when named", texte)
        for champ in ("date", "nature", "source", "review date", "stale mark"):
            self.assertIn(champ, texte)

    def test_la_description_garde_son_texte_d_avant(self):
        texte = self.description()
        self.assertIn('"own-articles"', texte)
        self.assertIn("Search the user's digital library", texte)

    def test_la_description_ne_porte_aucun_identifiant_personnel(self):
        texte = self.description().lower()
        for identifiant in identifiants_personnels.identifiants(RACINE):
            self.assertNotIn(identifiant, texte)

    def test_la_source_utilise_la_constante(self):
        source = (RACINE / "tools" / "pmzilla_lab_library.py").read_text(encoding="utf-8")
        self.assertIn("CONTEXT_DESCRIPTION", source)
        self.assertIn("{CONTEXT_COLLECTION}", source)


if __name__ == "__main__":
    unittest.main()
