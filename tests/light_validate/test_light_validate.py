"""tools/light_validate.py : validation OpenSpec du chemin allégé (change light-finish-touched-specs, design D1 à D4).

Dépôts temporaires avec un dossier openspec/ et une fausse commande OpenSpec (LIGHT_VALIDATE_OPENSPEC) qui lit, dans
chaque élément, un fichier findings.txt (une ligne « NIVEAU|message » par avertissement, l'index suit la position).

    python3 -m unittest discover -s tests/light_validate -v
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

OUTIL = Path(__file__).resolve().parents[2] / "tools" / "light_validate.py"

FAUX = r'''
import json, os, sys
args = sys.argv[1:]
with open(os.environ["LIGHT_FAKE_LOG"], "a") as f:
    f.write(os.getcwd() + "\t" + " ".join(args) + "\n")
if os.environ.get("LIGHT_FAKE_MODE") == "garbage":
    print("pas du JSON")
    sys.exit(1)
item = args[1]
genre = args[args.index("--type") + 1]
dossier = os.path.join(os.getcwd(), "openspec", "changes" if genre == "change" else "specs", item)
if not os.path.isdir(dossier):
    sys.stderr.write("introuvable\n")
    sys.exit(1)
issues = []
chemin = os.path.join(dossier, "findings.txt")
if os.path.exists(chemin):
    for i, ligne in enumerate(l.rstrip("\n") for l in open(chemin) if l.strip()):
        niveau, message = ligne.split("|", 1)
        issues.append({"level": niveau, "path": "requirements[%d]" % i, "message": message})
print(json.dumps({"items": [{"id": item, "type": genre, "valid": not issues, "issues": issues}]}))
sys.exit(1 if issues else 0)
'''

LONG = "WARNING|Requirement text is very long"
TBD = "WARNING|Purpose section is too short (provisional TBD)"


class LightValidate(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.base, True)
        self.depot = self.base / "depot"
        self.tmp = self.base / "tmp"
        self.tmp.mkdir()
        self.depot.mkdir()
        self.faux = self.base / "faux_openspec.py"
        self.faux.write_text(FAUX)
        self.journal = self.base / "appels.log"
        self.journal.write_text("")
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.org")
        self.git("config", "user.name", "test")
        self.ecrire("openspec/config.yaml", "schema: x\n")
        self.ecrire("openspec/changes/archive/.gitkeep", "")
        self.ecrire("openspec/specs/alpha/spec.md", "a\n")
        self.ecrire("openspec/specs/beta/spec.md", "b\n")
        self.ecrire("openspec/changes/ch1/proposal.md", "p\n")
        self.valide("base")
        self.git("switch", "-q", "-c", "feat")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.depot), *args], check=True, capture_output=True, text=True).stdout.strip()

    def ecrire(self, chemin, texte):
        p = self.depot / chemin
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(texte)

    def valide(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def lance(self, commande=None, mode=None):
        env = dict(os.environ)
        env["LIGHT_VALIDATE_OPENSPEC"] = commande or "%s %s" % (sys.executable, self.faux)
        env["LIGHT_FAKE_LOG"] = str(self.journal)
        env["TMPDIR"] = str(self.tmp)
        env.pop("LIGHT_FAKE_MODE", None)
        if mode:
            env["LIGHT_FAKE_MODE"] = mode
        r = subprocess.run([sys.executable, "-I", str(OUTIL), "main", "HEAD"], cwd=self.depot, env=env,
                           capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def appels(self):
        return [l.split("\t") for l in self.journal.read_text().splitlines() if l]

    # D1 : éléments touchés
    def test_un_change_touche(self):
        self.ecrire("openspec/changes/ch1/design.md", "d\n")
        self.valide("c")
        code, sortie = self.lance()
        self.assertEqual(code, 0, sortie)
        self.assertIn("validation OpenSpec : 1 élément(s) touché(s), aucun nouvel avertissement strict", sortie)
        appels = self.appels()
        self.assertTrue(all(a[1].split()[1] == "ch1" for a in appels), appels)
        racines = {a[0] for a in appels}
        self.assertEqual(len(racines), 2, appels)   # l'arbre du sommet et l'export de main
        self.assertIn(os.path.realpath(self.depot), {os.path.realpath(r) for r in racines})
        self.assertTrue(all("--type change" in a[1] and "--strict" in a[1] and "--json" in a[1] for a in appels))

    def test_archive_seule(self):
        self.ecrire("openspec/changes/archive/2026-01-01-x/proposal.md", "p\n")
        self.valide("a")
        code, sortie = self.lance()
        self.assertEqual(code, 0, sortie)
        self.assertIn("validation OpenSpec : aucun élément à valider (archives seulement)", sortie)
        self.assertEqual(self.appels(), [])

    def test_element_supprime_ne_donne_rien(self):
        self.git("rm", "-rq", "openspec/changes/ch1")
        self.valide("s")
        code, sortie = self.lance()
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.appels(), [])

    def test_configuration_touchee_valide_tout(self):
        self.ecrire("openspec/config.yaml", "schema: y\n")
        self.valide("c")
        code, sortie = self.lance()
        self.assertEqual(code, 0, sortie)
        self.assertIn("3 élément(s) touché(s)", sortie)
        vus = {(a[1].split()[1]) for a in self.appels()}
        self.assertEqual(vus, {"alpha", "beta", "ch1"})
        self.assertEqual(len(self.appels()), 6)   # deux arbres

    # D2 : aucun nouvel avertissement strict
    def test_avertissement_deja_sur_main(self):
        self.ecrire("openspec/specs/alpha/findings.txt", LONG + "\n")
        self.git("add", "-A"); self.git("commit", "-q", "-m", "w")
        self.git("switch", "-q", "main"); self.git("merge", "-q", "feat"); self.git("switch", "-q", "-c", "feat2")
        self.ecrire("openspec/specs/alpha/spec.md", "a2\n")
        self.valide("t")
        code, sortie = self.lance()
        self.assertEqual(code, 0, sortie)
        self.assertIn("aucun nouvel avertissement strict", sortie)
        self.assertIn("avertissements stricts déjà présents sur main, non bloquants : spec alpha", sortie)

    def test_un_avertissement_de_plus(self):
        self.ecrire("openspec/specs/alpha/findings.txt", LONG + "\n")
        self.git("add", "-A"); self.git("commit", "-q", "-m", "w")
        self.git("switch", "-q", "main"); self.git("merge", "-q", "feat"); self.git("switch", "-q", "-c", "feat2")
        self.ecrire("openspec/specs/alpha/findings.txt", LONG + "\n" + LONG + "\n")
        self.valide("t")
        code, sortie = self.lance()
        self.assertEqual(code, 1, sortie)
        lignes = [l for l in sortie.splitlines() if l.startswith("nouvel avertissement strict")]
        self.assertEqual(lignes, ["nouvel avertissement strict : spec alpha : Requirement text is very long"])

    def test_decalage_d_index(self):
        self.ecrire("openspec/specs/alpha/findings.txt", LONG + "\n")
        self.git("add", "-A"); self.git("commit", "-q", "-m", "w")
        self.git("switch", "-q", "main"); self.git("merge", "-q", "feat"); self.git("switch", "-q", "-c", "feat2")
        self.ecrire("openspec/specs/alpha/findings.txt", "INFO|court\n" + LONG + "\n")   # le même avertissement change d'index
        self.valide("t")
        code, sortie = self.lance()
        self.assertEqual(code, 0, sortie)

    def test_nouveau_change_avec_un_avertissement(self):
        self.ecrire("openspec/changes/neuf/proposal.md", "p\n")
        self.ecrire("openspec/changes/neuf/findings.txt", LONG + "\n")
        self.valide("n")
        code, sortie = self.lance()
        self.assertEqual(code, 1, sortie)
        self.assertIn("nouvel avertissement strict : change neuf : Requirement text is very long", sortie)
        self.assertEqual({a[1].split()[1] for a in self.appels() if "neuf" in a[1]}, {"neuf"})

    def test_objet_absent_de_main_sans_avertissement(self):
        self.ecrire("openspec/changes/neuf/proposal.md", "p\n")
        self.valide("n")
        code, sortie = self.lance()
        self.assertEqual(code, 0, sortie)

    def test_objectif_provisoire_laisse_par_une_archive(self):
        self.git("mv", "openspec/changes/ch1", "openspec/changes/archive/2026-01-01-ch1")
        self.ecrire("openspec/specs/neuve/spec.md", "n\n")
        self.ecrire("openspec/specs/neuve/findings.txt", TBD + "\n")
        self.valide("archive")
        code, sortie = self.lance()
        self.assertEqual(code, 1, sortie)
        lignes = [l for l in sortie.splitlines() if l.startswith("nouvel avertissement strict")]
        self.assertEqual(len(lignes), 1, sortie)
        self.assertIn("spec neuve", lignes[0])

    def test_un_niveau_info_ne_compte_pas(self):
        self.ecrire("openspec/specs/alpha/findings.txt", "INFO|note\n")
        self.valide("i")
        code, sortie = self.lance()
        self.assertEqual(code, 0, sortie)

    # codes d'échec
    def test_commande_absente(self):
        self.ecrire("openspec/specs/alpha/spec.md", "a2\n")
        self.valide("t")
        code, sortie = self.lance(commande=str(self.base / "inexistante"))
        self.assertEqual(code, 127, sortie)

    def test_sortie_illisible(self):
        self.ecrire("openspec/specs/alpha/spec.md", "a2\n")
        self.valide("t")
        code, sortie = self.lance(mode="garbage")
        self.assertEqual(code, 1, sortie)
        self.assertIn("validation OpenSpec illisible pour spec alpha", sortie)

    # D2 : rien d'écrit hors d'un dossier temporaire, qui disparaît
    def test_dossier_temporaire_supprime_et_depot_intact(self):
        self.ecrire("openspec/specs/alpha/spec.md", "a2\n")
        self.valide("t")
        avant = self.git("status", "--porcelain")
        self.lance()
        self.assertEqual(list(self.tmp.iterdir()), [])
        self.assertEqual(self.git("status", "--porcelain"), avant)
        self.assertTrue(any(str(self.tmp) in os.path.realpath(a[0]) or os.path.realpath(str(self.tmp)) in os.path.realpath(a[0])
                            for a in self.appels()))

    def test_dossier_temporaire_supprime_en_cas_d_echec(self):
        self.ecrire("openspec/specs/alpha/spec.md", "a2\n")
        self.valide("t")
        self.lance(mode="garbage")
        self.assertEqual(list(self.tmp.iterdir()), [])

    def test_docstring_et_bibliotheque_standard(self):
        texte = OUTIL.read_text()
        self.assertIn("127", texte.split('"""')[1])
        self.assertNotIn("import yaml", texte)


if __name__ == "__main__":
    unittest.main()
