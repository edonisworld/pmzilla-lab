"""
Revue Opus du commit f8cb0ee4 (audit #629, groupe O4) : l'indexeur n'écrit jamais, dans sa sortie, le nom de fichier d'une note de contexte
que la garde des noms refuse, qu'elle soit refusée pour son nom, pour son corps ou pour son en-tête. Faux magasin, fausse liste de noms.

    bash tests/run_all.sh pmzilla_lab_library
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "context_lab"))
from unittest import mock  # noqa: E402
from fixtures_context import note  # noqa: E402
from test_context_notes import CORPS, AvecContexte  # noqa: E402
from test_pmzilla_lab_library import library  # noqa: E402

DEUX_MOTS = "Zorb Quillan"
FICHIER = "2026-09-05-zorb-quillan.md"
MARQUEUR = "(file name hidden)"


class NomDeFichierMasque(AvecContexte):
    def setUp(self):
        super().setUp()
        self.ctx.liste.write_text(f"{DEUX_MOTS}\n", encoding="utf-8")

    def assertNomAbsent(self, sortie, erreur):
        for texte in (sortie, erreur):
            self.assertNotIn("zorb", texte.lower())
            self.assertNotIn("quillan", texte.lower())

    def test_nom_refuse_pour_lui_meme_n_est_pas_ecrit(self):
        self.ctx.ecrire(FICHIER, note(title="Organisation neutre", date="2026-09-05", body=CORPS))
        code, sortie, erreur = self.lancer()
        self.assertEqual(code, 1)
        self.assertIn(f"not indexed: {MARQUEUR}: sensitive name in file name", erreur)
        self.assertNomAbsent(sortie, erreur)
        self.assertNotIn(FICHIER, self.store.books)

    def test_nom_refuse_et_en_tete_invalide_n_est_pas_ecrit(self):
        self.ctx.ecrire(FICHIER, note(title="Sans revue", date="2026-09-05", sans=("review",), body=CORPS))
        code, sortie, erreur = self.lancer()
        self.assertEqual(code, 1)
        self.assertIn(f"not indexed: {MARQUEUR}: header field missing: review", erreur)
        self.assertNomAbsent(sortie, erreur)

    def test_nom_refuse_et_corps_sensible_n_est_pas_ecrit(self):
        self.ctx.ecrire(FICHIER, note(title="Autre titre", date="2026-09-05", body=f"le rôle voit {DEUX_MOTS}\n"))
        code, sortie, erreur = self.lancer()
        self.assertEqual(code, 1)
        self.assertIn(f"not indexed: {MARQUEUR}: sensitive name in line", erreur)
        self.assertNomAbsent(sortie, erreur)

    def test_un_nom_sain_refuse_pour_son_en_tete_reste_nomme(self):
        self.ctx.ecrire("2026-09-02-sans-revue.md", note(title="Sans revue", sans=("review",), body=CORPS))
        code, sortie, erreur = self.lancer()
        self.assertEqual(code, 1)
        self.assertIn("not indexed: 2026-09-02-sans-revue.md: header field missing: review", erreur)


class LigneRemovedMasquee(AvecContexte):
    """Lot 5, question 2c (option a) : la ligne `removed:` n'écrit pas le nom d'une note que la garde refuse ; un nom admis y reste."""

    def test_nom_refuse_apres_coup_la_note_retiree_est_masquee(self):
        self.ctx.ecrire(FICHIER, note(title="Organisation neutre", date="2026-09-05", body=CORPS))
        code, _, erreur = self.lancer()
        self.assertEqual(code, 0, erreur)
        self.assertIn(FICHIER, self.store.books)
        self.ctx.liste.write_text(f"{DEUX_MOTS}\n", encoding="utf-8")
        code, sortie, erreur = self.lancer()
        self.assertEqual(code, 1)
        self.assertNotIn(FICHIER, self.store.books)
        self.assertIn(f"removed: {MARQUEUR}", sortie)
        for texte in (sortie, erreur):
            self.assertNotIn("zorb", texte.lower())
            self.assertNotIn("quillan", texte.lower())

    def test_nom_admis_retire_pour_son_corps_reste_nomme(self):
        nom = "2026-09-05-note-saine.md"
        self.ctx.ecrire(nom, note(title="Note saine", date="2026-09-05", body="rien de sensible\n"))
        self.lancer()
        self.assertIn(nom, self.store.books)
        self.ctx.ecrire(nom, note(title="Note saine", date="2026-09-05", body="le rôle voit Plombuxor\n"))
        self.ctx.liste.write_text("Plombuxor\n", encoding="utf-8")
        code, sortie, erreur = self.lancer()
        self.assertEqual(code, 1)
        self.assertIn(f"removed: {nom}", sortie)
        self.assertNotIn(MARQUEUR, sortie)
        self.assertNotIn("Plombuxor", sortie + erreur)


class ListeIndisponibleNomsMasques(AvecContexte):
    """R-20261108-03, question 3 (a) : liste des noms absente ou vide, l'indexeur n'écrit aucun nom de note privée, y compris sur la ligne
    `removed:` ; le nom d'un livre reste affiché."""
    NEUTRE = "2026-09-05-organisation-neutre.md"

    def indexe_puis_rend_la_liste_indisponible(self, vide):
        self.ctx.ecrire(self.NEUTRE, note(title="Organisation neutre", date="2026-09-05", body=CORPS))
        code, sortie, erreur = self.lancer()
        self.assertEqual(code, 0, erreur)
        self.assertIn(self.NEUTRE, self.store.books)
        self.assertIn("Flux inventé", sortie)        # le livre de la fixture garde son titre affiché
        if vide:
            self.ctx.liste.write_text("# rien\n", encoding="utf-8")
        else:
            self.liste(self.ctx.tmp / "absente.txt")

    def verifie(self, vide):
        self.indexe_puis_rend_la_liste_indisponible(vide)
        code, sortie, erreur = self.lancer()
        self.assertEqual(code, 1)
        self.assertNotIn(self.NEUTRE, sortie + erreur)
        self.assertIn(self.NEUTRE, self.store.books)        # une liste indisponible n'empêche pas d'indexer : rien n'est retiré
        # Chemin de retrait atteint malgré la liste indisponible (liste perdue entre le balayage et le retrait) : le nom est masqué.
        with mock.patch.object(library, "scan_context", return_value=({}, [], set(), False)):
            code, sortie, erreur = self.lancer()
        self.assertEqual(code, 0, erreur)
        self.assertIn(f"removed: {MARQUEUR}", sortie)
        self.assertNotIn(self.NEUTRE, sortie + erreur)

    def test_liste_absente(self):
        self.verifie(False)

    def test_liste_vide(self):
        self.verifie(True)


if __name__ == "__main__":
    unittest.main()
