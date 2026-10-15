"""
Tests de tools/identifiants_personnels.py : la condition de publication « aucun identifiant personnel ».

    uv run python -m unittest discover -s tests/identifiants_personnels -v

Faux dépôt Git dans un dossier temporaire avec un identifiant fictif (dans `.pmzilla/identifiants.txt`) ; le vrai dépôt
n'est pas lu.
"""
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import identifiants_personnels as ip  # noqa: E402

ID = "zorglub-test"


class Recherche(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.racine = Path(self.temp.name).resolve()
        subprocess.run(["git", "init", "-q"], cwd=self.racine, check=True)
        (self.racine / ".pmzilla").mkdir()
        (self.racine / ".pmzilla" / "identifiants.txt").write_text(ID + "\n", encoding="utf-8")
        self.ecrire("propre.md", "rien à signaler\n")
        self.ecrire("nom.md", f"ligne 1\nmon dossier est /Users/{ID}/travail\n")
        self.ecrire("casse.md", f"{ID.upper()} en majuscules\n")
        self.ecrire("docs/pmzilla/version-anglaise.md", f"{ID}\n")
        self.ecrire("docs/pmzilla/bibliotheque-lacunes.md", f"{ID}\n")
        self.ecrire("_bmad-output/pmzilla/table-ronde/2026-01-01-sujet.md", f"{ID}\n")
        self.ecrire("_bmad-output/pmzilla/autre.md", f"{ID}\n")
        self.ecrire("non-suivi.md", f"{ID}\n", suivre=False)
        (self.racine / "image.png").write_bytes(b"\x89PNG" + ID.encode())
        subprocess.run(["git", "add", "image.png"], cwd=self.racine, check=True)

    def tearDown(self):
        self.temp.cleanup()

    def ecrire(self, nom, texte, suivre=True):
        chemin = self.racine / nom
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(texte, encoding="utf-8")
        if suivre:
            subprocess.run(["git", "add", nom], cwd=self.racine, check=True)

    def test_trouve_l_identifiant_et_le_chemin_personnel(self):
        trouves = ip.chercher(self.racine, ip.EXCLUS_PAR_DEFAUT)
        self.assertEqual(trouves["nom.md"], [2])
        self.assertEqual(trouves["casse.md"], [1])        # la casse est ignorée
        self.assertNotIn("propre.md", trouves)

    def test_ignore_les_fichiers_hors_edition_non_suivis_et_binaires(self):
        trouves = ip.chercher(self.racine, ip.EXCLUS_PAR_DEFAUT)
        for nom in ("docs/pmzilla/version-anglaise.md",
                    "docs/pmzilla/bibliotheque-lacunes.md", "non-suivi.md", "image.png"):
            self.assertNotIn(nom, trouves)

    def test_le_dossier_des_tables_rondes_est_exclu_mais_pas_le_reste_de_bmad_output(self):
        trouves = ip.chercher(self.racine, ip.EXCLUS_PAR_DEFAUT)
        self.assertNotIn("_bmad-output/pmzilla/table-ronde/2026-01-01-sujet.md", trouves)
        self.assertIn("_bmad-output/pmzilla/autre.md", trouves)

    def test_le_plan_est_exclu_par_defaut_mais_pas_les_autres_docs(self):
        self.assertIn("docs/pmzilla/version-anglaise.md", ip.EXCLUS_PAR_DEFAUT)
        self.ecrire("docs/pmzilla/installation.md", f"{ID}\n")
        self.assertIn("docs/pmzilla/installation.md", ip.chercher(self.racine, ip.EXCLUS_PAR_DEFAUT))

    def test_le_chemin_de_la_racine_est_un_identifiant(self):
        self.ecrire("chemin.md", f"cd {self.racine}/tools\n")
        self.assertIn("chemin.md", ip.chercher(self.racine, ip.EXCLUS_PAR_DEFAUT))

    def test_sortie_sans_identifiant_ni_texte_de_ligne(self):
        sortie = io.StringIO()
        with mock.patch.object(sys, "argv", ["x", "--racine", str(self.racine), "--lignes"]), contextlib.redirect_stdout(sortie):
            code = ip.main()
        texte = sortie.getvalue()
        self.assertEqual(code, 1)
        self.assertIn("nom.md : 1 (lignes 2)", texte)
        self.assertNotIn(ID, texte.lower())
        self.assertNotIn("travail", texte)
        self.assertIn("Total : 3 ligne(s) dans 3 fichier(s)", texte)

    def test_code_zero_sans_occurrence(self):
        for nom in ("nom.md", "casse.md", "_bmad-output/pmzilla/autre.md"):
            subprocess.run(["git", "rm", "-q", "-f", nom], cwd=self.racine, check=True)
        sortie = io.StringIO()
        with mock.patch.object(sys, "argv", ["x", "--racine", str(self.racine)]), contextlib.redirect_stdout(sortie):
            self.assertEqual(ip.main(), 0)
        self.assertIn("Total : 0 ligne(s) dans 0 fichier(s)", sortie.getvalue())

    def test_exclusion_supplementaire(self):
        trouves = ip.chercher(self.racine, ip.EXCLUS_PAR_DEFAUT + ("nom.md",))
        self.assertNotIn("nom.md", trouves)

    def test_identifiants_viennent_du_compte_et_du_fichier_local(self):
        trouves = ip.identifiants(self.racine)
        self.assertIn(ID, trouves)
        self.assertIn(ip.getpass.getuser().lower(), trouves)


class AuteurDesCas(unittest.TestCase):
    """L'identifiant d'auteur du module des cas, lu dans .pmzilla/cases.yaml (design.md 3.8), jamais dans l'environnement."""

    AUTEUR = "auteur-invente-test"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.racine = Path(self.temp.name).resolve()
        subprocess.run(["git", "init", "-q"], cwd=self.racine, check=True)
        (self.racine / ".pmzilla").mkdir()
        (self.racine / ".pmzilla" / "identifiants.txt").write_text(ID + "\n", encoding="utf-8")
        self.addCleanup(self.temp.cleanup)

    def cases(self, contenu: bytes | str):
        donnees = contenu if isinstance(contenu, bytes) else contenu.encode("utf-8")
        (self.racine / ".pmzilla" / "cases.yaml").write_bytes(donnees)

    def ecrire(self, nom, texte, suivre=True):
        chemin = self.racine / nom
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(texte, encoding="utf-8")
        if suivre:
            subprocess.run(["git", "add", nom], cwd=self.racine, check=True)

    def test_l_auteur_est_cherche_dans_les_fichiers_suivis(self):
        self.cases(f"author: {self.AUTEUR}\n")
        self.ecrire("propre.md", "rien\n")
        self.ecrire("cite.md", f"ligne 1\nvu par {self.AUTEUR.upper()} lundi\n")
        self.assertIn(self.AUTEUR, ip.identifiants(self.racine))
        self.assertEqual(ip.chercher(self.racine, ip.EXCLUS_PAR_DEFAUT), {"cite.md": [2]})

    def test_main_avec_lignes_n_imprime_ni_l_identifiant_ni_le_texte(self):
        self.cases(f"author: {self.AUTEUR}\n")
        self.ecrire("cite.md", f"ligne 1\nvu par {self.AUTEUR.upper()} lundi\n")
        sortie = io.StringIO()
        with mock.patch.object(sys, "argv", ["x", "--racine", str(self.racine), "--lignes"]), contextlib.redirect_stdout(sortie):
            code = ip.main()
        texte = sortie.getvalue()
        self.assertEqual(code, 1)
        self.assertIn("cite.md : 1 (lignes 2)", texte)
        self.assertNotIn(self.AUTEUR, texte.lower())
        self.assertNotIn("lundi", texte)

    def test_formes_de_la_valeur(self):
        for ligne in ("author: x-test", 'author: "x-test"', "author: 'x-test'", "author:   x-test   # commentaire",
                      "author:\tx-test\t#\tcommentaire"):
            with self.subTest(ligne=ligne):
                self.cases(f"autre: y\n{ligne}\n")
                self.assertEqual(ip.identifiant_auteur(self.racine), "x-test")

    def test_cle_indentee_ou_autre_cle_donne_none(self):
        for contenu in ("  author: x-test\n", "autre: x-test\n"):
            with self.subTest(contenu=contenu):
                self.cases(contenu)
                self.assertIsNone(ip.identifiant_auteur(self.racine))

    def test_auteur_absent_ou_vide_ne_change_rien(self):
        sans = ip.identifiants(self.racine)
        self.ecrire("propre.md", "rien\n")
        self.assertIsNone(ip.identifiant_auteur(self.racine))     # pas de cases.yaml
        for contenu in ("author:\n", 'author: ""\n', "author:   # commentaire\n"):
            with self.subTest(contenu=contenu):
                self.cases(contenu)
                self.assertIsNone(ip.identifiant_auteur(self.racine))
                sortie, erreur = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
                    self.assertEqual(ip.identifiants(self.racine), sans)
                self.assertEqual((sortie.getvalue(), erreur.getvalue()), ("", ""))
                with mock.patch.object(sys, "argv", ["x", "--racine", str(self.racine)]), contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(ip.main(), 0)

    def test_la_variable_d_environnement_n_est_pas_lue(self):
        with mock.patch.dict(os.environ, {"PMZILLA_LAB_CASES_AUTHOR": "agile-lead-test"}):
            self.assertNotIn("agile-lead-test", ip.identifiants(self.racine))

    def test_fichier_illisible_code_2_sans_contenu(self):
        self.cases(f"author: {self.AUTEUR}\n".encode("utf-8") + b"\xff")
        r = subprocess.run([sys.executable, str(Path(ip.__file__)), "--racine", str(self.racine)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("cases.yaml", r.stderr)
        self.assertNotIn(self.AUTEUR, (r.stdout + r.stderr).lower())

    def test_option_fichier_gagne_l_identifiant(self):
        self.cases(f"author: {self.AUTEUR}\n")
        message = self.racine / "msg.txt"
        message.write_text(f"titre\n\npar {self.AUTEUR}\n", encoding="utf-8")
        r = subprocess.run([sys.executable, str(Path(ip.__file__)), "--racine", str(self.racine), "--fichier", str(message)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("msg.txt : 1", r.stdout)
        self.assertNotIn(self.AUTEUR, (r.stdout + r.stderr).lower())


class Sanctums(unittest.TestCase):
    """Les sanctums générés depuis les modèles sont cherchés comme des fichiers suivis (lot 6, plan 6.1)."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.racine = Path(self.temp.name).resolve()
        (self.racine / ".pmzilla").mkdir()
        (self.racine / ".pmzilla" / "identifiants.txt").write_text(ID + "\n", encoding="utf-8")
        self.skill = self.racine / ".claude" / "skills" / "pmzilla-delivery-bmad"
        (self.skill / "scripts").mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def faux_init(self, contenu: str):
        (self.skill / "scripts" / "init-sanctum.py").write_text(
            "import sys\nfrom pathlib import Path\n"
            "d = Path(sys.argv[1]) / '_bmad' / 'memory' / 'x'\nd.mkdir(parents=True)\n"
            f"(d / 'CREED.md').write_text({contenu!r}, encoding='utf-8')\n", encoding="utf-8")

    def test_un_modele_qui_ecrit_un_chemin_personnel_dans_le_sanctum_est_repere(self):
        self.faux_init(f"ligne 1\nsanctum : /Users/{ID}/PMZilla-Lab/workspace\n")
        trouves = ip.chercher_dans_les_sanctums(self.racine)
        self.assertEqual(trouves, {"sanctum:delivery/_bmad/memory/x/CREED.md": [2]})

    def test_un_sanctum_propre_ne_donne_rien(self):
        self.faux_init("rien à signaler\n")
        self.assertEqual(ip.chercher_dans_les_sanctums(self.racine), {})

    def test_skill_sans_script_ignore_et_script_en_echec_arrete_tout(self):
        self.assertEqual(ip.chercher_dans_les_sanctums(self.racine), {})
        (self.skill / "scripts" / "init-sanctum.py").write_text("raise SystemExit(3)\n", encoding="utf-8")
        with self.assertRaises(SystemExit):
            ip.chercher_dans_les_sanctums(self.racine)

    def test_les_vrais_skills_ne_laissent_aucun_identifiant_dans_un_sanctum_genere(self):
        racine_reelle = Path(__file__).resolve().parents[2]
        self.assertEqual(ip.chercher_dans_les_sanctums(racine_reelle, cherches=["/users/", "/home/", str(racine_reelle).lower()]), {})


class FichierDonne(unittest.TestCase):
    """Option --fichier : un fichier texte donné (message de commit), suivi ou non, mêmes règles de sortie."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.racine = Path(self.temp.name).resolve()
        subprocess.run(["git", "init", "-q"], cwd=self.racine, check=True)
        (self.racine / ".pmzilla").mkdir()
        (self.racine / ".pmzilla" / "identifiants.txt").write_text(ID + "\n", encoding="utf-8")
        self.addCleanup(self.temp.cleanup)

    def lancer(self, nom, texte=None, *options):
        chemin = self.racine / nom
        if texte is not None:
            chemin.write_text(texte, encoding="utf-8")
        argv = [sys.executable, str(Path(ip.__file__)), "--racine", str(self.racine), "--fichier", str(chemin), *options]
        return subprocess.run(argv, capture_output=True, text=True)

    def test_identifiant_dans_le_fichier_non_suivi(self):
        r = self.lancer("msg.txt", f"titre\n\nvu dans /Users/{ID.upper()}/x\n", "--lignes")
        self.assertEqual(r.returncode, 1)
        self.assertIn("msg.txt : 1 (lignes 3)", r.stdout)
        self.assertNotIn(ID, (r.stdout + r.stderr).lower())
        self.assertNotIn("vu dans", r.stdout + r.stderr)

    def test_fichier_propre(self):
        r = self.lancer("msg.txt", "rien a signaler\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_fichier_absent_code_d_erreur_et_chemin_nomme(self):
        r = self.lancer("absent.txt")
        self.assertEqual(r.returncode, 2)
        self.assertIn("absent.txt", r.stdout + r.stderr)

    def test_les_fichiers_suivis_ne_sont_pas_cherches_avec_fichier(self):
        (self.racine / "suivi.md").write_text(ID + "\n", encoding="utf-8")
        subprocess.run(["git", "add", "suivi.md"], cwd=self.racine, check=True)
        r = self.lancer("msg.txt", "propre\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class Arbre(unittest.TestCase):
    """Mode arbre (--arbre) : un dossier généré, sans Git, avec les identifiants de la racine privée."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name).resolve()
        self.racine = base / "privee"
        self.arbre = base / "arbre"
        (self.racine / ".pmzilla").mkdir(parents=True)
        (self.racine / ".pmzilla" / "identifiants.txt").write_text(ID + "\n", encoding="utf-8")
        self.arbre.mkdir()

    def ecrire(self, nom, texte):
        chemin = self.arbre / nom
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(texte, encoding="utf-8")

    def lancer(self, *options, arbre=None):
        argv = [sys.executable, str(Path(ip.__file__)), "--racine", str(self.racine),
                "--arbre", str(arbre if arbre is not None else self.arbre), *options]
        return subprocess.run(argv, capture_output=True, text=True)

    def test_identifiant_dans_un_arbre_sans_git(self):
        self.ecrire("docs/a.md", f"un\ndeux /Users/{ID.upper()}/x\n")
        self.ecrire("propre.md", "rien\n")
        r = self.lancer("--lignes")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("docs/a.md : 1 (lignes 2)", r.stdout)
        self.assertIn("Total : 1 ligne(s) dans 1 fichier(s)", r.stdout)
        self.assertNotIn(ID, (r.stdout + r.stderr).lower())
        self.assertNotIn("deux", r.stdout + r.stderr)

    def test_fonction_importable_chemins_relatifs(self):
        self.ecrire("a/b/c.md", f"{ID}\n")
        self.assertEqual(ip.chercher_arbre(self.arbre, self.racine), {"a/b/c.md": [1]})

    def test_aucune_exclusion_par_defaut(self):
        for nom in ip.EXCLUS_PAR_DEFAUT:
            self.ecrire(nom if not nom.endswith("/") else nom + "x.md", f"{ID}\n")
        trouves = ip.chercher_arbre(self.arbre, self.racine)
        self.assertEqual(len(trouves), len(ip.EXCLUS_PAR_DEFAUT))
        self.assertIn("docs/pmzilla/bibliotheque-lacunes.md", trouves)

    def test_exclusion_supplementaire_refusee_code_2(self):
        self.ecrire("a.md", f"{ID}\n")
        r = self.lancer("--exclure", "a.md")
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("a.md :", r.stdout)
        self.assertNotIn("Total", r.stdout)

    def test_dossier_inexistant_code_2(self):
        r = self.lancer(arbre=self.arbre / "absent")
        self.assertEqual(r.returncode, 2)
        self.assertIn("absent", r.stdout + r.stderr)

    def test_ne_lit_ni_les_identifiants_ni_la_config_des_cas_de_l_arbre(self):
        self.ecrire(".pmzilla/identifiants.txt", "autre-secret-xyz\n")
        self.ecrire(".pmzilla/cases.yaml", "author: auteur-des-cas-xyz\n")
        self.ecrire("a.md", "autre-secret-xyz et auteur-des-cas-xyz\n")
        self.assertEqual(ip.chercher_arbre(self.arbre, self.racine), {})

    def test_auteur_des_cas_de_la_racine_est_cherche(self):
        (self.racine / ".pmzilla" / "cases.yaml").write_text("author: auteur-prive-xyz\n", encoding="utf-8")
        self.ecrire("a.md", "vu : AUTEUR-PRIVE-XYZ\n")
        self.assertEqual(ip.chercher_arbre(self.arbre, self.racine), {"a.md": [1]})

    def test_chemin_de_la_racine_et_binaire_ignore(self):
        self.ecrire("a.md", f"cd {self.racine}/x\n")
        (self.arbre / "b.bin").write_bytes(b"\xff\xfe" + ID.encode())
        self.assertEqual(ip.chercher_arbre(self.arbre, self.racine), {"a.md": [1]})

    def test_sanctums_du_skill_de_l_arbre(self):
        skill = self.arbre / ".claude" / "skills" / "pmzilla-delivery-bmad"
        (skill / "scripts").mkdir(parents=True)
        (skill / "scripts" / "init-sanctum.py").write_text(
            "import sys\nfrom pathlib import Path\n"
            "d = Path(sys.argv[1]) / '_bmad' / 'x'\nd.mkdir(parents=True)\n"
            f"(d / 'CREED.md').write_text('a\\nchemin /Users/' + {ID[:4]!r} + {ID[4:]!r} + '/w\\n', encoding='utf-8')\n", encoding="utf-8")
        trouves = ip.chercher_arbre(self.arbre, self.racine)
        self.assertEqual(trouves, {"sanctum:delivery/_bmad/x/CREED.md": [2]})
        r = self.lancer()
        self.assertEqual(r.returncode, 1)
        self.assertIn("sanctum:delivery/_bmad/x/CREED.md : 1", r.stdout)

    def test_arbre_propre_code_zero(self):
        self.ecrire("a.md", "rien\n")
        r = self.lancer()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Total : 0 ligne(s) dans 0 fichier(s)", r.stdout)


class ConfigurationBmad(unittest.TestCase):
    """Le nom d'utilisateur BMAD suivi par Git est le nom générique ; le fichier personnel reste hors Git."""

    RACINE = Path(__file__).resolve().parents[2]

    def test_user_name_generique_dans_les_trois_yaml(self):
        for module in ("core", "bmm", "bmb"):
            lignes = (self.RACINE / "_bmad" / module / "config.yaml").read_text(encoding="utf-8").splitlines()
            self.assertIn("user_name: BMad", lignes, f"_bmad/{module}/config.yaml")

    def test_config_user_toml_non_suivi(self):
        r = subprocess.run(["git", "ls-files", "_bmad/config.user.toml"], cwd=self.RACINE, capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), "")

    def test_gitignore_exclut_les_fichiers_personnels_bmad(self):
        lignes = (self.RACINE / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("/_bmad/config.user.toml", lignes)
        self.assertIn("/_bmad/custom/*.user.toml", lignes)


class DepotReel(unittest.TestCase):
    """Garde du dépôt réel : aucun identifiant personnel dans un fichier suivi.

    Rien n'est toléré : toute occurrence d'un identifiant dans un fichier suivi fait échouer le test, hors des exclusions par
    défaut du scanner (historique et plans). Le réglage `bluesky` vit dans watch/tri.local.yaml, non suivi. Le test passe sur
    une machine où les identifiants n'apparaissent nulle part (autre compte, clone neuf).
    """
    RACINE = Path(__file__).resolve().parents[2]
    TOLERES_LOT_8 = ()

    def test_aucun_identifiant_personnel_dans_les_fichiers_suivis(self):
        trouves = ip.chercher(self.RACINE, ip.EXCLUS_PAR_DEFAUT + self.TOLERES_LOT_8)
        detail = "; ".join(f"{nom} : lignes {', '.join(map(str, lignes))}" for nom, lignes in sorted(trouves.items()))
        self.assertFalse(trouves, f"Identifiants personnels dans des fichiers suivis : {detail}")


if __name__ == "__main__":
    unittest.main()
