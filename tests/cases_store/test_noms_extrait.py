"""
R-20261112-24 (A-75 de l'audit #629) : la couche d'accès des cas refuse un brouillon qui cite un nom de la liste ou de l'extrait des
équipes, sans jamais afficher ni écrire ce nom. Liste et extrait FACTICES (variable de test PMZILLA_LAB_SENSITIVE_NAMES, extrait voisin
de la liste) ; sans base (le refus a lieu avant toute connexion). Noms et textes inventés.

Remplace : rien. Retrait : permanent (propriété de confidentialité des messages de refus).
"""
import contextlib
import datetime as dt
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import cases_store as cs        # noqa: E402
import sensitive_names as sn    # noqa: E402

TODAY = dt.date(2027, 3, 1)
NOM_EXTRAIT = "Quillonbrook"    # seulement dans l'extrait
NOM_LISTE = "Zorglub"           # dans la liste
EXTRAIT = f"referential_teams:\n  - name: {NOM_EXTRAIT}\ncatalogue_teams:\n  - name: Marmotte Atelier\n"
BROUILLON = {"problem": "Les parties prenantes ne viennent plus aux revues", "context": {"team_type": "type A", "team_size": 7},
             "tested": "Une revue construite autour de deux décisions", "expected_signal": "Les parties prenantes reviennent",
             "success_criterion": "Quatre revues de suite avec trois parties prenantes"}


class RefusSansLeNom(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dossier = Path(temp.name)
        (self.dossier / "noms.txt").write_text(f"{NOM_LISTE}\n", encoding="utf-8")
        (self.dossier / sn.NOM_EXTRAIT).write_text(EXTRAIT, encoding="utf-8")
        patch = mock.patch.dict("os.environ", {"PMZILLA_LAB_SENSITIVE_NAMES": str(self.dossier / "noms.txt")})
        patch.start()
        self.addCleanup(patch.stop)

    def refus(self, appel):
        sortie, erreur = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur), self.assertRaises(cs.CasesError) as e:
            appel()
        return e.exception, sortie.getvalue() + erreur.getvalue()

    def verifier(self, nom, erreur, capture):
        self.assertEqual(erreur.code, "sensitive_name")                       # (a) refus
        for texte in (str(erreur), repr(erreur), repr(erreur.args), str(erreur.field), capture):
            self.assertNotIn(nom.lower(), texte.lower())                       # (b) jamais le nom
        for fichier in (p for p in self.dossier.rglob("*") if p.is_file() and p.name not in ("noms.txt", sn.NOM_EXTRAIT)):
            self.assertNotIn(nom.lower(), fichier.read_text(encoding="utf-8").lower())

    def test_start_refuse_un_nom_de_la_liste_ou_de_l_extrait_sans_le_nommer(self):
        for nom in (NOM_EXTRAIT, NOM_LISTE):
            with self.subTest(nom=nom):
                brouillon = {**BROUILLON, "problem": f"Le client {nom} bloque", "hypotheses": ["rien"]}
                erreur, capture = self.refus(lambda: cs.start_experiment(None, None, brouillon, "agile-lead-test", TODAY))
                self.assertEqual(erreur.field, "problem")
                self.verifier(nom, erreur, capture)

    def test_note_et_close_refusent_un_nom_de_l_extrait_sans_le_nommer(self):
        erreur, capture = self.refus(lambda: cs.validate_note_draft({"note": f"vu chez {NOM_EXTRAIT.upper()}"}, TODAY, cs._names(None)))
        self.verifier(NOM_EXTRAIT, erreur, capture)
        erreur, capture = self.refus(lambda: cs.validate_close_draft(
            {"outcome": "dropped", "drop_reason": f"équipe {NOM_EXTRAIT} réorganisée"}, TODAY, cs._names(None)))
        self.verifier(NOM_EXTRAIT, erreur, capture)


if __name__ == "__main__":
    unittest.main()
