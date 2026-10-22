"""
Tests de tools/commit_names_scan.py (fix/sorties-et-masquage, décision de l'auteur du 2026-10-21, point 3) : passage unique, en lecture seule,
sur les messages des commits non poussés, et contrôle d'un message de commit (crochet commit-msg).

    uv run python -W ignore -m unittest discover -s tests/sensitive_names -q

Dépôt Git et dépôt distant nu créés par le test dans un dossier temporaire ; listes fictives (noms inventés) passées par
PMZILLA_LAB_SENSITIVE_NAMES, l'extrait des équipes voisin de la liste. La vraie liste et le vrai extrait ne sont jamais lus.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

OUTIL = Path(__file__).resolve().parents[2] / "tools" / "commit_names_scan.py"
NOM = "Zorglubia"            # nom fictif de la liste
COURT = "QXZ"                # nom fictif de trois caractères : casse respectée
EQUIPE = "Quarkonaute Nord"  # nom fictif de l'extrait des équipes
EXTRAIT = f"""extracted_on: '2026-10-19'
referential_teams:
- name: {EQUIPE}
  jira_team_ids: []
catalogue_teams: []
"""


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.liste = self.tmp / "listes" / "noms-sensibles.txt"
        self.liste.parent.mkdir()
        self.liste.write_text(f"# commentaire\n{NOM}\n{COURT}\n", encoding="utf-8")
        (self.liste.parent / "equipes-lisibles.yaml").write_text(EXTRAIT, encoding="utf-8")
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("PMZILLA_", "GIT_"))}
        self.env.update(PMZILLA_LAB_SENSITIVE_NAMES=str(self.liste), GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
                        GIT_TERMINAL_PROMPT="0")
        self.distant = self.tmp / "distant.git"
        self.depot = self.tmp / "depot"
        self.git_brut("init", "-q", "--bare", str(self.distant), cwd=self.tmp)
        self.git_brut("init", "-q", "-b", "main", str(self.depot), cwd=self.tmp)
        self.git("remote", "add", "origin", str(self.distant))
        self.compteur = 0

    def tearDown(self):
        self._tmp.cleanup()

    def git_brut(self, *args, cwd):
        return subprocess.run(["git", "-c", "user.name=test", "-c", "user.email=t@example.org", *args], cwd=cwd, env=self.env,
                              capture_output=True, text=True, check=True).stdout.strip()

    def git(self, *args):
        return self.git_brut(*args, cwd=self.depot)

    def commit(self, message):
        self.compteur += 1
        (self.depot / "f.txt").write_text(str(self.compteur), encoding="utf-8")
        self.git("add", "f.txt")
        self.git("commit", "-q", "--no-verify", "-m", message)
        return self.git("rev-parse", "--short", "HEAD")

    def lance(self, *args):
        fait = subprocess.run([sys.executable, str(OUTIL), *args], cwd=self.depot, env=self.env, capture_output=True, text=True)
        return fait.returncode, fait.stdout + fait.stderr


class PassageSurLesCommitsNonPousses(Base):
    def test_aucun_commit_non_pousse_code_0(self):
        self.commit(f"pousse avec {NOM}")
        self.git("push", "-q", "origin", "main")
        code, sortie = self.lance()
        self.assertEqual(code, 0, sortie)
        self.assertIn("0 commit(s) lu(s), 0 dont le message contient un nom", sortie)

    def test_commit_touche_sha_court_seulement_jamais_le_nom_ni_le_message(self):
        self.commit("base poussée")
        self.git("push", "-q", "origin", "main")
        propre = self.commit("message propre")
        touche = self.commit(f"ajoute la vue de {NOM} et autre chose")
        code, sortie = self.lance()
        self.assertEqual(code, 1, sortie)
        self.assertIn("2 commit(s) lu(s), 1 dont le message contient un nom", sortie)
        self.assertIn(touche, sortie)
        self.assertNotIn(propre, sortie)
        self.assertNotIn(NOM, sortie)
        self.assertNotIn(NOM.lower(), sortie.lower())
        self.assertNotIn("ajoute la vue", sortie)
        self.assertNotIn("message propre", sortie)

    def test_nom_dans_le_corps_du_message_et_casse_ignoree(self):
        self.commit(f"titre neutre\n\ncorps qui cite {NOM.upper()}")
        code, sortie = self.lance()
        self.assertEqual(code, 1, sortie)

    def test_nom_de_l_extrait_des_equipes(self):
        touche = self.commit(f"revue de l'équipe {EQUIPE}")
        code, sortie = self.lance()
        self.assertEqual(code, 1, sortie)
        self.assertIn(touche, sortie)
        self.assertNotIn("Quarkonaute", sortie)

    def test_memes_regles_de_correspondance_que_pre_commit(self):
        self.commit(f"mot collé {NOM}x et sigle {COURT.lower()} en minuscules")
        code, sortie = self.lance()
        self.assertEqual(code, 0, sortie)
        self.commit(f"sigle {COURT} en capitales")
        code, sortie = self.lance()
        self.assertEqual(code, 1, sortie)
        self.assertIn("2 commit(s) lu(s), 1 dont le message contient un nom", sortie)

    def test_branche_jamais_poussee_comptee(self):
        self.commit("base")
        self.git("push", "-q", "origin", "main")
        self.git("checkout", "-q", "-b", "travail")
        touche = self.commit(f"travail sur {NOM}")
        self.git("checkout", "-q", "main")
        code, sortie = self.lance()
        self.assertEqual(code, 1, sortie)
        self.assertIn(touche, sortie)

    def test_plage_donnee_en_argument(self):
        premier = self.commit(f"ancien {NOM}")
        self.commit("récent propre")
        code, sortie = self.lance("--", f"{premier}..HEAD")
        self.assertEqual(code, 0, sortie)
        self.assertIn("1 commit(s) lu(s), 0 dont le message contient un nom", sortie)
        code, sortie = self.lance("--", "HEAD", "--not", "--remotes=origin")
        self.assertEqual(code, 1, sortie)
        self.assertIn("2 commit(s) lu(s), 1 dont le message contient un nom", sortie)

    def test_liste_absente_code_2_ferme_par_defaut(self):
        self.commit(f"ajoute {NOM}")
        self.liste.unlink()
        code, sortie = self.lance()
        self.assertEqual(code, 2, sortie)
        self.assertIn("liste des noms sensibles absente", sortie)
        self.assertNotIn("commit(s) lu(s)", sortie)

    def test_liste_vide_avertit_sans_bloquer(self):
        self.commit("ajoute f")
        self.liste.write_text("# rien\n", encoding="utf-8")
        (self.liste.parent / "equipes-lisibles.yaml").unlink()
        code, sortie = self.lance()
        self.assertEqual(code, 0, sortie)
        self.assertIn("liste vide", sortie)

    def test_liste_vide_avec_un_extrait_garde_les_noms_de_l_extrait(self):
        self.commit(f"revue {EQUIPE}")
        self.liste.write_text("", encoding="utf-8")
        code, sortie = self.lance()
        self.assertEqual(code, 1, sortie)

    def test_revision_inconnue_code_3(self):
        self.commit("ajoute f")
        code, sortie = self.lance("--", "inexistante..HEAD")
        self.assertEqual(code, 3, sortie)
        self.assertIn("lecture des commits impossible", sortie)

    def test_etiquette_locale_non_poussee_comptee(self):
        # revue Opus, point 6 : le passage par défaut inclut les étiquettes locales (--tags), pas seulement les branches
        self.commit("base")
        self.git("push", "-q", "origin", "main")
        self.git("checkout", "-q", "--detach")
        touche = self.commit(f"hors branche {NOM}")
        self.git("tag", "t-local")
        self.git("checkout", "-q", "main")
        code, sortie = self.lance()
        self.assertEqual(code, 1, sortie)
        self.assertIn(touche, sortie)

    def test_lecture_seule(self):
        self.commit(f"ajoute {NOM}")
        avant = (self.git("rev-parse", "HEAD"), self.git("status", "--porcelain"), self.git("for-each-ref"))
        self.lance()
        self.assertEqual(avant, (self.git("rev-parse", "HEAD"), self.git("status", "--porcelain"), self.git("for-each-ref")))


class ControleDUnMessage(Base):
    def message(self, texte):
        chemin = self.tmp / "COMMIT_EDITMSG"
        chemin.write_text(texte, encoding="utf-8")
        return self.lance("--message", str(chemin))

    def test_message_propre_code_0(self):
        code, sortie = self.message("ajoute f\n\ncorps neutre\n")
        self.assertEqual(code, 0, sortie)

    def test_message_touche_numero_de_ligne_jamais_le_nom(self):
        code, sortie = self.message(f"titre\n\ncorps avec {NOM}\n")
        self.assertEqual(code, 1, sortie)
        self.assertIn("ligne 3", sortie)
        self.assertNotIn(NOM, sortie)
        self.assertNotIn("corps avec", sortie)

    def test_les_lignes_de_commentaire_comptent(self):
        # revue Opus, point 3 : une ligne « # » peut rester dans le commit (git commit -m "# …", --cleanup=verbatim ou whitespace)
        code, sortie = self.message(f"titre\n# commentaire avec {NOM}\n")
        self.assertEqual(code, 1, sortie)
        self.assertIn("ligne 2", sortie)

    def test_texte_coupe_a_la_ligne_de_ciseaux(self):
        # revue Opus, point 4 : git commit -v met le diff sous la ligne de ciseaux ; un commit qui retire un nom n'est pas refusé
        code, sortie = self.message(f"retire un nom\n# ------------------------ >8 ------------------------\n-ancienne ligne {NOM}\n")
        self.assertEqual(code, 0, sortie)
        code, sortie = self.message(f"titre {NOM}\n# ------------------------ >8 ------------------------\n")
        self.assertEqual(code, 1, sortie)

    def test_entree_standard_sans_ciseaux(self):
        # message d'une étiquette annotée (crochet pre-push) : lu sur l'entrée standard, entier, sans coupe aux ciseaux
        texte = f"version\n# ------------------------ >8 ------------------------\nnote {NOM}\n"
        fait = subprocess.run([sys.executable, str(OUTIL), "--message", "-", "--sans-ciseaux"], cwd=self.depot, env=self.env,
                              input=texte, capture_output=True, text=True)
        self.assertEqual(fait.returncode, 1, fait.stdout + fait.stderr)
        self.assertNotIn(NOM, fait.stdout + fait.stderr)

    def test_liste_absente_code_2(self):
        self.liste.unlink()
        code, sortie = self.message("titre\n")
        self.assertEqual(code, 2, sortie)


class ErreurInattendue(Base):
    """Revue Opus, point 2 : une exception ne sort jamais en code 1 (nom trouvé) et sa trace, qui pourrait citer une ligne d'une liste,
    n'est jamais imprimée : code 3 et le seul type de l'exception."""

    def test_exception_pendant_la_lecture_des_listes(self):
        import contextlib
        import io
        from unittest import mock
        sys.path.insert(0, str(OUTIL.parent))
        try:
            import commit_names_scan as outil
            sortie = io.StringIO()
            with mock.patch.dict(os.environ, self.env, clear=True), \
                    mock.patch.object(outil.sensitive_names, "extract_names", side_effect=ValueError(f"ligne {NOM}")), \
                    contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(sortie):
                code = outil.main(["--depot", str(self.depot)])
        finally:
            sys.path.remove(str(OUTIL.parent))
        self.assertEqual(code, 3, sortie.getvalue())
        self.assertIn("ValueError", sortie.getvalue())
        self.assertNotIn(NOM, sortie.getvalue())

    def test_module_des_noms_en_echec_a_l_import(self):
        copie = self.tmp / "outils"
        copie.mkdir()
        (copie / "commit_names_scan.py").write_text(OUTIL.read_text(encoding="utf-8"), encoding="utf-8")
        (copie / "sensitive_names.py").write_text(f'raise ValueError("{NOM}")\n', encoding="utf-8")
        fait = subprocess.run([sys.executable, str(copie / "commit_names_scan.py")], cwd=self.depot, env=self.env,
                              capture_output=True, text=True)
        self.assertEqual(fait.returncode, 3, fait.stdout + fait.stderr)
        self.assertNotIn(NOM, fait.stdout + fait.stderr)
        self.assertIn("ValueError", fait.stdout + fait.stderr)


if __name__ == "__main__":
    unittest.main()
