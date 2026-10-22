"""
Garde des chemins en dur (R-77, design D3, D4) : aucun fichier de code exécutable suivi de tools/ (scripts, hooks Git, modèles de
planification) ne porte un chemin littéral vers le dossier du lab ou vers un dossier personnel. Hors du champ : la documentation
(fichiers .md, .txt, .rst, même sous tools/), CLAUDE.md, le README et le guide d'installation, qui peuvent nommer ces chemins.

    bash tests/run_all.sh lab_paths

Motif : `PMZilla-Lab` suivi de `/`, `"` ou `'` (la casse compte : le dossier de données `.pmzilla-lab` n'en fait pas partie), ou `/Users/`.
Un échec donne le chemin et le numéro de ligne, jamais le texte de la ligne. La garde n'a aucune exception, commentaires compris (D4) :
la liste transitoire de la migration est vidée et retirée (tâche 9.2).
"""
import re
import subprocess
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
OUTILS = RACINE / "tools"
MOTIF = re.compile(r"PMZilla-Lab[/\"']|/Users/")

DOCUMENTATION = (".md", ".txt", ".rst")   # hors du champ de la garde


def fichiers_suivis() -> list:
    """Les fichiers de code suivis par Git sous tools/ (documentation exclue) ; sans dépôt (arbre de l'édition), tous ceux du dossier."""
    r = subprocess.run(["git", "-C", str(RACINE), "ls-files", "-z", "--", "tools"], capture_output=True, text=True)
    if r.returncode == 0 and r.stdout:
        noms = [p for p in r.stdout.split("\0") if p]
    else:
        noms = [str(p.relative_to(RACINE)) for p in OUTILS.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    return sorted(n for n in noms if not n.endswith(DOCUMENTATION))


def lignes_en_defaut(chemin: str) -> list:
    """Numéros des lignes d'un fichier texte qui portent un littéral ; un fichier binaire n'en porte aucune."""
    try:
        texte = (RACINE / chemin).read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    return [n for n, ligne in enumerate(texte.splitlines(), 1) if MOTIF.search(ligne)]


class TestGardeDesChemins(unittest.TestCase):
    def test_la_documentation_est_hors_du_champ(self):
        self.assertFalse(any(n.endswith(DOCUMENTATION) for n in fichiers_suivis()))
        self.assertIn("tools/com.pmzilla.watch.plist", fichiers_suivis())     # les modèles de planification sont dans le champ
        self.assertIn("tools/hooks/pre-commit", fichiers_suivis())            # les hooks Git aussi

    def test_aucun_litteral(self):
        trouves = []
        for chemin in fichiers_suivis():
            trouves += [f"{chemin}:{n}" for n in lignes_en_defaut(chemin)]
        self.assertEqual(trouves, [], "chemin littéral vers le dossier du lab ou un dossier personnel (chemin:ligne)")

    def test_les_modules_partages_n_ont_aucun_litteral(self):
        for nom in ("tools/lab_paths.py", "tools/lab_paths.sh"):
            self.assertEqual(lignes_en_defaut(nom), [], nom)

    def test_le_motif_attrape_les_formes_connues_et_pas_le_dossier_de_donnees(self):
        for texte in ('x = "~/PMZilla-Lab/workspace"', 'maison / "PMZilla-Lab" / "run"', "'PMZilla-Lab'", "/Users/quelquun/x"):
            self.assertTrue(MOTIF.search(texte), texte)
        for texte in ("~/.pmzilla-lab", "PMZilla Lab", "le dépôt pmzilla-lab/", "PMZilla-Labo"):
            self.assertFalse(MOTIF.search(texte), texte)


if __name__ == "__main__":
    unittest.main()
