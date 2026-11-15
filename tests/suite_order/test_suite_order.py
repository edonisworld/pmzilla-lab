"""
Tests de tools/suite_order.py (change run-all-faster-and-guarded, design D1, tâche 2.2) : médiane des cinq dernières durées vertes d'un
passage complet, lignes en échec, ciblées ou filtrées ignorées, ligne partielle ou mal formée ignorée, codes 0, 2 et 3, rien d'écrit
(la division par le nombre de morceaux et l'option --chunks sont retirées : B9, finish-single-b7-b9).

    uv run python -m unittest discover -s tests/suite_order -v

Faux fichiers de durées dans un dossier temporaire ; aucune durée n'est comparée à une horloge.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

OUTIL = Path(__file__).resolve().parents[2] / "tools" / "suite_order.py"
sys.path.insert(0, str(OUTIL.parent))
import suite_order  # noqa: E402

ENTETE = "lancement\tidentifiant\tgenre\tposte\tsuite\ttype\tsecondes\tsecondes_unittest\tverdict\traison\n"


def ligne(suite, genre_suite, secondes, verdict="ok", genre="complet"):
    return f"2026-10-29T10:00:00\tid\t{genre}\tespace\t{suite}\t{genre_suite}\t{secondes}\t\t{verdict}\t\n"


class Estimations(unittest.TestCase):
    def test_mediane_des_cinq_dernieres_lignes_vertes(self):
        lignes = [ligne("alpha", "python", s) for s in (900, 1, 2, 3, 4, 100)]   # la première sort des cinq dernières
        self.assertEqual(suite_order.estimations(lignes), {("alpha", "python"): 3.0})   # médiane de 1, 2, 3, 4, 100

    def test_moins_de_cinq_lignes_la_mediane_de_celles_qui_existent(self):
        self.assertEqual(suite_order.estimations([ligne("alpha", "python", 2), ligne("alpha", "python", 6)]), {("alpha", "python"): 4.0})

    def test_les_lignes_en_echec_ciblees_et_filtrees_sont_ignorees(self):
        lignes = [ligne("alpha", "python", 10), ligne("alpha", "python", 500, verdict="échec"), ligne("alpha", "python", 500, verdict="délai"),
                  ligne("alpha", "python", 500, genre="ciblé"), ligne("alpha", "python", 500, genre="filtré")]
        self.assertEqual(suite_order.estimations(lignes), {("alpha", "python"): 10.0})

    def test_une_suite_sans_ligne_utile_n_est_pas_mesuree(self):
        self.assertEqual(suite_order.estimations([ligne("alpha", "python", 5, verdict="échec")]), {})

    def test_la_paire_est_suite_et_type(self):
        lignes = [ligne("offsite_backup", "python", 2), ligne("offsite_backup", "shell", 8)]
        self.assertEqual(suite_order.estimations(lignes), {("offsite_backup", "python"): 2.0, ("offsite_backup", "shell"): 8.0})

    def test_ligne_partielle_ou_mal_formee_ignoree(self):
        lignes = [ENTETE, ligne("alpha", "python", 6), "2026-10-29T10:00:00\tid\tcomplet\tespace\tbeta", "n'importe quoi\n",
                  ligne("gamma", "python", "abc"), ligne("alpha", "python", 8)[:-5]]
        self.assertEqual(suite_order.estimations(lignes), {("alpha", "python"): 6.0})


class Lancement(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.addCleanup(self.dossier.cleanup)
        self.fichier = Path(self.dossier.name) / "durees.tsv"

    def lancer(self, *arguments):
        return subprocess.run([sys.executable, "-I", "-B", str(OUTIL), *arguments], capture_output=True, text=True, timeout=60)

    def test_code_0_une_ligne_par_suite_mesuree(self):
        self.fichier.write_text(ENTETE + ligne("alpha", "python", 5) + ligne("beta", "shell", 12), encoding="utf-8")
        resultat = self.lancer("--durations", str(self.fichier))
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        self.assertEqual(resultat.stdout.splitlines(), ["alpha:python\t5.0", "beta:shell\t12.0"])

    def test_code_2_usage(self):
        self.assertEqual(self.lancer().returncode, 2)
        self.assertEqual(self.lancer("--durations", str(self.fichier), "--chunks", "mauvais").returncode, 2)
        self.assertEqual(self.lancer("--inconnue").returncode, 2)

    def test_code_3_fichier_absent_ou_sans_ligne_utilisable(self):
        self.assertEqual(self.lancer("--durations", str(self.fichier)).returncode, 3)
        self.fichier.write_text(ENTETE + ligne("alpha", "python", 5, verdict="échec"), encoding="utf-8")
        self.assertEqual(self.lancer("--durations", str(self.fichier)).returncode, 3)
        self.fichier.write_text("", encoding="utf-8")
        self.assertEqual(self.lancer("--durations", str(self.fichier)).returncode, 3)

    def test_n_ecrit_rien(self):
        self.fichier.write_text(ENTETE + ligne("alpha", "python", 5), encoding="utf-8")
        avant = (self.fichier.read_bytes(), sorted(p.name for p in Path(self.dossier.name).iterdir()))
        self.lancer("--durations", str(self.fichier))
        self.assertEqual((self.fichier.read_bytes(), sorted(p.name for p in Path(self.dossier.name).iterdir())), avant)


if __name__ == "__main__":
    unittest.main()
