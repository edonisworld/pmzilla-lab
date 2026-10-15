"""
Jeu d'essai des postures (tools/posture_evals.py) contre une vraie base jetable (R-37, design.md D11) : prérequis lus dans la
bibliothèque de démonstration, bibliothèque jetable d'un cas indexée dans la base jetable après vidage.

    bash tools/dbtest.sh posture_evals          (par l'utilisateur seul ; sautés sans base)

Aucun appel à Claude ni à Ollama (vecteurs inventés de demo_library), aucune lecture de la vraie bibliothèque ni de la vraie base :
la base pmzilla_test_<hex> est créée, chargée de la bibliothèque inventée, puis supprimée. Les articles indexés sont ceux, inventés,
de tests/postures/fixtures/watch-digest/collections.
"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tests" / "library_backend"))
import pg_demo                  # noqa: E402  (ajoute tools/, tests/db et tests/fixtures_library au chemin)
import demo_library as demo     # noqa: E402
import pmzilla_lab_library as library  # noqa: E402

import posture_evals as essai   # noqa: E402

BIBLIOTHEQUE_DU_CAS = "tests/postures/fixtures/watch-digest/collections"


class AvecDossierDeDonnees(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        patch = mock.patch.dict(os.environ, {"PMZILLA_LAB_DATA": str(self.tmp / "donnees")})
        patch.start()
        self.addCleanup(patch.stop)


class PrerequisSurLaBaseDeDemonstration(AvecDossierDeDonnees):
    """Les trois règles, lues sous le rôle de lecture seule dans la bibliothèque inventée."""

    def setUp(self):
        super().setUp()
        self.pg = pg_demo.ThrowawayDatabase(self)        # saute le test sans base
        self.lecteur = essai.LibraryReader(self.pg.connect())

    def manque(self, regles):
        return essai.unmet_prerequisites(regles, reader=self.lecteur)

    def test_livre_par_titre_sans_casse(self):
        self.assertEqual(self.manque([{"book": "ATELIER DES FLUX"}]), [])
        self.assertIn("Inconnu", self.manque([{"book": "Inconnu"}])[0])

    def test_collection_par_nom_exact(self):
        self.assertEqual(self.manque([{"collection": "watch", "minimum": 3}]), [])
        self.assertIn("3 livre(s) pour 4", self.manque([{"collection": "watch", "minimum": 4}])[0])
        self.assertIn("0 livre(s)", self.manque([{"collection": "wat"}])[0])

    def test_sujet_absent_tous_les_mots_sans_casse_ni_accents(self):
        self.assertIn("présent", self.manque([{"absent_topic": "EQUIPE accents"}])[0])
        self.assertIn("présent", self.manque([{"absent_topic": "delai file"}])[0])         # « délai », « file » : un passage
        self.assertIn("présent", self.manque([{"absent_topic": "chapitre little"}])[0])    # la section compte dans le plein texte
        self.assertEqual(self.manque([{"absent_topic": "délai prototypage"}]), [])        # un mot absent : sujet absent
        self.assertEqual(self.manque([{"absent_topic": "prototypage génératif"}]), [])

    def test_sujet_absent_en_alternatives_or(self):
        self.assertIn("(1 passages)", self.manque([{"absent_topic": '"prototypage génératif" OR "ACCENTS ne comptent"'}])[0])
        self.assertIn("présent", self.manque([{"absent_topic": 'prototypage OR "allonge le delai"'}])[0])
        self.assertEqual(self.manque([{"absent_topic": '"prototypage génératif" OR "generative prototyping"'}]), [])

    def test_expression_entre_guillemets_mots_voisins_dans_l_ordre(self):
        # « Une file d'attente qui grandit allonge le délai » : « file » et « délai » y sont, mais pas voisins
        self.assertEqual(self.manque([{"absent_topic": '"file délai"'}]), [])               # non voisins : ne compte pas
        self.assertEqual(self.manque([{"absent_topic": '"délai allonge"'}]), [])            # voisins mais à l'envers
        self.assertIn("(1 passages)", self.manque([{"absent_topic": '"allonge le DÉLAI"'}])[0])   # voisins, ordre, sans casse
        self.assertIn("présent", self.manque([{"absent_topic": '"délai de bout"'}])[0])
        self.assertIn("présent", self.manque([{"absent_topic": "file délai"}])[0])          # sans guillemets : tous les mots
        self.assertEqual(self.manque([{"absent_topic": '"file délai" OR "délai file"'}]), [])
        self.assertIn("(1 passages)", self.manque([{"absent_topic": '"file délai" OR "allonge le délai"'}])[0])

    def test_aucune_ecriture_et_chaque_lecture_termine_sa_transaction(self):
        self.manque([{"book": "flux"}, {"collection": "flow"}, {"absent_topic": "flux"}])
        self.assertEqual(self.lecteur.conn.info.transaction_status.name, "IDLE")     # rien n'est resté ouvert


class BibliothequeJetableIndexee(AvecDossierDeDonnees):
    """Un cas `library:` : les tables de la bibliothèque de la base jetable sont vidées, puis le dossier du cas y est indexé par la
    ligne de commande de l'indexeur (jouée ici dans le processus, vecteurs inventés), la base étant désignée par la variable."""

    def setUp(self):
        super().setUp()
        self.pg = pg_demo.ThrowawayDatabase(self)        # chargée de la bibliothèque de démonstration : ce qui doit disparaître
        self.indexations = []
        for patch in (mock.patch.object(essai, "WORKSPACE", RACINE),
                      mock.patch.object(essai, "connect_cases_database", lambda nom: self.pg._raw()),
                      mock.patch.object(essai.subprocess, "run", self.indexeur),
                      mock.patch.object(library, "embed", demo.fake_embed),
                      # L'indexeur se connecte par db.connect sans mot de passe : Trousseau d'abord, puis la variable. Sur le Mac de
                      # l'utilisateur, le Trousseau donne le mot de passe de la vraie instance, refusé par l'instance jetable de
                      # dbtest.sh : le Trousseau est écarté ici, la variable (celle de l'instance jetable) est lue.
                      mock.patch.object(pg_demo.db, "mot_de_passe_trousseau", lambda *a, **k: None)):
            patch.start()
            self.addCleanup(patch.stop)

    def indexeur(self, commande, env=None, **options):
        """`uv run …/pmzilla_lab_library.py index <dossier>` joué par main() de l'indexeur, avec l'environnement transmis."""
        self.assertEqual(commande[-2], "index")
        self.indexations.append(env[essai.KNOWLEDGE_DBNAME_VARIABLE])
        sortie = io.StringIO()
        with mock.patch.dict(os.environ, {essai.KNOWLEDGE_DBNAME_VARIABLE: env[essai.KNOWLEDGE_DBNAME_VARIABLE]}), \
                mock.patch.object(sys, "argv", ["pmzilla_lab_library.py", "index", commande[-1]]), \
                contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(sortie):
            try:
                library.main()
                code = 0
            except SystemExit as fin:
                code = fin.code if isinstance(fin.code, int) else (0 if fin.code is None else 1)
        return subprocess.CompletedProcess(commande, code, sortie.getvalue(), "")

    def livres(self) -> set[str]:
        conn = self.pg._raw()
        try:
            return {nom for (nom,) in conn.execute("SELECT file_name FROM knowledge.books").fetchall()}
        finally:
            conn.rollback()

    def test_vidage_puis_indexation_du_dossier_du_cas_dans_la_base_jetable(self):
        self.assertTrue(self.livres() & set(demo.BOOKS))
        config = essai.case_library({"id": "c", "library": BIBLIOTHEQUE_DU_CAS}, self.tmp, dbname=self.pg.name)
        self.assertEqual(self.indexations, [self.pg.name])
        attendus = {chemin.name for chemin in (RACINE / BIBLIOTHEQUE_DU_CAS).glob("*/*.md")}
        self.assertEqual(self.livres(), attendus)                           # rien de la bibliothèque d'avant
        serveur = json.loads(config.read_text(encoding="utf-8"))["mcpServers"]["pmzilla-library"]
        self.assertEqual(serveur["env"], {essai.KNOWLEDGE_DBNAME_VARIABLE: self.pg.name})
        self.assertNotIn("--backend", serveur["args"])
        lecteur = essai.LibraryReader(self.pg.connect())
        self.assertEqual(essai.unmet_prerequisites([{"collection": "watch", "minimum": len(attendus)}], reader=lecteur), [])
        self.assertFalse(list((self.tmp / "donnees").glob("*.sqlite")))     # aucun index fichier


if __name__ == "__main__":
    unittest.main()
