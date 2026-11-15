"""
R-20261112-24 (A-75 de l'audit #629) : le journal refuse un périmètre ou un brouillon qui cite un nom de la liste ou de l'extrait des
équipes, sans jamais afficher ni écrire ce nom. Liste et extrait FACTICES (variable de test PMZILLA_LAB_SENSITIVE_NAMES, extrait voisin
de la liste) ; noms et textes inventés.

Remplace : rien. Retrait : permanent (propriété de confidentialité des messages de refus).
"""
import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from test_journal_lab import ENTREE, Base  # noqa: E402
import journal_lab as journal              # noqa: E402
import sensitive_names                     # noqa: E402

NOM_EXTRAIT = "Quillonbrook"      # seulement dans l'extrait
NOM_LISTE = "Zorglub"             # dans la liste (voir Base)
EXTRAIT = f"referential_teams:\n  - name: {NOM_EXTRAIT}\ncatalogue_teams:\n  - name: Marmotte Atelier\n"
BROUILLON_EXPERIENCE = """\
problem: Les revues de sprint sont peu suivies
context:
  team_type: type A
  team_size: 7
  phase: croissance
tested: Une revue construite autour de deux décisions
expected_signal: Les parties prenantes reviennent
success_criterion: Quatre revues de suite avec trois parties prenantes
posture: delivery
"""


class RefusSansLeNom(Base):
    def setUp(self):
        super().setUp()
        (self.noms.parent / sensitive_names.NOM_EXTRAIT).write_text(EXTRAIT, encoding="utf-8")

    def cli_capture(self, *arguments):
        """(code de sortie, stdout, stderr) ; le code est le texte de SystemExit pour `add`, l'entier pour `experiment`."""
        sortie, erreur = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", ["journal_lab.py", "--today", "2026-10-06", *arguments]), \
                contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
            with self.assertRaises(SystemExit) as arret:
                journal.main()
        return arret.exception.code, sortie.getvalue(), erreur.getvalue()

    def ecrits_par_l_outil(self):
        """Fichiers du dossier temporaire hors ceux que le test a écrits lui-même."""
        a_moi = {self.noms, self.noms.parent / sensitive_names.NOM_EXTRAIT}
        return [p for p in self.tmp.rglob("*") if p.is_file() and p not in a_moi]

    def verifier_sans_le_nom(self, nom, *morceaux):
        for morceau in morceaux:
            self.assertNotIn(nom.lower(), str(morceau).lower())
        for fichier in self.ecrits_par_l_outil():
            if fichier.name in ("entree.yaml", "brouillon.yaml"):   # le fichier du test, que l'outil ne réécrit pas
                continue
            self.assertNotIn(nom.lower(), fichier.read_text(encoding="utf-8").lower(), fichier.name)

    def test_add_refuse_un_perimetre_qui_cite_un_nom_et_ne_l_affiche_pas(self):
        for nom in (NOM_EXTRAIT, NOM_LISTE):
            with self.subTest(nom=nom):
                texte = ENTREE.replace("équipe Alpha", f"équipe {nom}")
                chemin = self.fichier(texte)
                code, sortie, erreur = self.cli_capture("add", str(chemin))
                self.assertIn("perimetre", str(code))                  # le champ est nommé
                self.assertFalse(journal.JOURNAL_FILE.exists())        # (a) refus : rien n'est écrit
                self.assertTrue(chemin.exists())
                self.verifier_sans_le_nom(nom, code, sortie, erreur)   # (b) jamais le nom

    def test_add_refuse_un_nom_en_minuscules_dans_un_autre_champ_sans_l_afficher(self):
        texte = ENTREE.replace("Plus de participation", f"Plus de participation chez {NOM_EXTRAIT.lower()}")
        code, sortie, erreur = self.cli_capture("add", str(self.fichier(texte)))
        self.assertIn("constat", str(code))
        self.assertFalse(journal.JOURNAL_FILE.exists())
        self.verifier_sans_le_nom(NOM_EXTRAIT, code, sortie, erreur)

    def test_experiment_start_refuse_un_nom_et_ne_l_affiche_pas(self):
        for nom in (NOM_EXTRAIT, NOM_LISTE):
            with self.subTest(nom=nom):
                chemin = self.fichier(BROUILLON_EXPERIENCE.replace("Les revues", f"Chez {nom}, les revues"), "brouillon.yaml")
                with mock.patch.dict("os.environ", {"PMZILLA_LAB_CASES_AUTHOR": "agile-lead-test"}):
                    code, sortie, erreur = self.cli_capture("experiment", "start", str(chemin))
                self.assertEqual(code, 1)                              # (a) refus
                self.assertIn("problem", erreur)                       # le champ est nommé
                self.verifier_sans_le_nom(nom, code, sortie, erreur)   # (b) jamais le nom


if __name__ == "__main__":
    unittest.main()
