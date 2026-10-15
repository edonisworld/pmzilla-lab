"""Le résumé du matin ne montre jamais le secret, ne touche ni gh ni le réseau, et lit ses dossiers par les réglages (design D5, D11, D12, D13).

Les cas du secret passent par la vraie lecture des bilans (module db) avec un faux `security` (PMZILLA_LAB_DB_SECURITY_BIN) et une base
dont le port est fermé : aucune base réelle, aucun Trousseau réel.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide import Labo, JOUR, MOT_DE_PASSE, RACINE, SENTINELLE, ms  # noqa: E402

TITRE_FR = "PMZilla : résumé du matin"


class Secret(Labo):
    def setUp(self):
        super().setUp()
        env = {"PMZILLA_LAB_DB_PORT": "1", "PMZILLA_LAB_DB_SECURITY_BIN": str(self.bin / "security")}
        for cle, valeur in env.items():
            os.environ[cle] = valeur
            self.addCleanup(os.environ.pop, cle, None)
        os.environ.pop("PMZILLA_LAB_DB_URL", None)

    def lancer_reel(self, *argv, **env):
        """Sans la fonction des bilans de remplacement : la vraie lecture (module db), avec le faux `security`."""
        import contextlib, io
        from unittest import mock
        sortie, erreur = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, env), contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
            code = ms.main(list(argv))
        return code, sortie.getvalue(), erreur.getvalue()

    def test_lecture_du_trousseau_en_echec_bilans_indisponibles_et_resume_envoye(self):
        self.stub("security", "#!/bin/sh\nexit 44\n")
        self.tout_connu()
        code, sortie, erreur = self.lancer_reel("--notify", PMZILLA_SUMMARY_NOTIFY="1")
        self.assertEqual(code, 0)
        self.assertIn("Bilans : indisponible", sortie)
        self.assertEqual(len(sortie.splitlines()), 5)
        appels = self.notifications()
        self.assertEqual(len(appels), 1)
        self.assertIn("Bilans : indisponible", appels[0][-1])

    def test_trousseau_qui_plante_meme_issue(self):
        self.stub("security", "#!/bin/sh\necho 'erreur interne' >&2\nkill -9 $$\n")
        code, sortie, _ = self.lancer_reel("--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(sortie)["reviews"]["state"], "unavailable")

    def test_security_introuvable_meme_issue(self):
        os.environ["PMZILLA_LAB_DB_SECURITY_BIN"] = str(self.tmp / "absent")
        self.assertEqual(json.loads(self.lancer_reel("--json")[1])["reviews"]["state"], "unavailable")

    def test_mot_de_passe_sentinelle_et_base_injoignable_jamais_affiche(self):
        self.stub("security", f"#!/bin/sh\nprintf '%s\\n' '{MOT_DE_PASSE}'\n")
        self.tout_connu()
        toute_la_sortie = ""
        for argv in ((), ("--json",), ("--language", "en"), ("--notify",)):
            code, sortie, erreur = self.lancer_reel(*argv, PMZILLA_SUMMARY_NOTIFY="1")
            self.assertEqual(code, 0, argv)
            toute_la_sortie += sortie + erreur
        self.assertIn("Bilans : base injoignable", toute_la_sortie)
        self.assertNotIn(MOT_DE_PASSE, toute_la_sortie)
        journal = self.appels.read_text(encoding="utf-8") if self.appels.exists() else ""
        self.assertNotIn(MOT_DE_PASSE, journal)
        for fichier in self.donnees.rglob("*"):
            if fichier.is_file():
                self.assertNotIn(MOT_DE_PASSE, fichier.read_text(encoding="utf-8"), fichier.name)

    def test_mot_de_passe_sentinelle_dans_la_variable_et_le_journal_de_la_pile(self):
        self.stub("security", "#!/bin/sh\nexit 44\n")
        os.environ["PMZILLA_LAB_DB_PASSWORD_PMZILLA_CASES_RO"] = MOT_DE_PASSE
        self.addCleanup(os.environ.pop, "PMZILLA_LAB_DB_PASSWORD_PMZILLA_CASES_RO", None)
        code, sortie, erreur = self.lancer_reel("--json")
        self.assertEqual(code, 0)
        self.assertNotIn(MOT_DE_PASSE, sortie + erreur)
        self.assertEqual(json.loads(sortie)["reviews"]["state"], "unreachable")


class Source(unittest.TestCase):
    SCRIPT = RACINE / "tools" / "morning_summary.py"

    def test_aucun_gh_psql_docker_security_ni_appel_reseau(self):
        code = self.SCRIPT.read_text(encoding="utf-8").split("# ///\n", 2)[-1]     # sans l'en-tête des dépendances (httpx y est déclaré pour cases_store)
        texte = code + (RACINE / "tools" / "morning_summary_messages.py").read_text(encoding="utf-8")
        for interdit in (r"\bgh\b", r"\bpsql\b", r"\bdocker\b", r"\bsecurity\b", r"\burllib\b", r"\brequests\b", r"\bhttpx\b", r"\bsocket\b",
                         r"https?://", r"\bcurl\b", r"find-generic-password", r"\bpg_dump\b"):
            self.assertIsNone(re.search(interdit, texte), interdit)

    def test_les_seuls_programmes_lances_sont_osascript_et_git_en_lecture(self):
        import ast
        texte = self.SCRIPT.read_text(encoding="utf-8")
        appels = [n for n in ast.walk(ast.parse(texte)) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                  and isinstance(n.func.value, ast.Name) and n.func.value.id == "subprocess" and n.func.attr != "SubprocessError"]
        self.assertEqual(len(appels), 2)     # osascript (notification) et git rev-parse (dossier de contenu, R-43)
        self.assertEqual(re.findall(r"commande = \[(.*?)\]", texte), ['"osascript"'])
        self.assertEqual(re.findall(r'subprocess\.run\(\["git", "-C", str\(code\), "(.*?)"', texte), ["rev-parse"])

    def test_pas_de_shell_et_pas_de_os_system(self):
        texte = self.SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("shell=True", texte)
        self.assertNotIn("os.system", texte)


class AutreArbre(Labo):
    def test_lancement_depuis_une_copie_du_code_hors_de_l_espace_de_travail(self):
        copie = self.tmp / "arbre-d-execution" / "tools"
        shutil.copytree(RACINE / "tools", copie, ignore=shutil.ignore_patterns("__pycache__", "*.lock"))
        self.tout_connu()
        (self.racine / ".pmzilla" / "cases.yaml").write_text("author: auteur-de-test\n", encoding="utf-8")
        os.environ.pop("PMZILLA_LAB_CASES_AUTHOR")
        env = {**os.environ, "PMZILLA_LAB_DB_PORT": "1", "PMZILLA_LAB_DB_SECURITY_BIN": str(self.tmp / "absent")}
        fait = subprocess.run([sys.executable, "-I", str(copie / "morning_summary.py"), "--json"], capture_output=True, text=True, env=env,
                              cwd=self.tmp, timeout=60)
        self.assertEqual(fait.returncode, 0, fait.stderr)
        donnees = json.loads(fait.stdout)
        self.assertEqual(donnees["watch"]["state"], "done")
        self.assertEqual(donnees["watch"]["retained"], 7)
        self.assertEqual(donnees["queue"]["ready"], 4)
        self.assertEqual(donnees["doctor"]["problems"], 2)
        self.assertEqual(donnees["reviews"]["state"], "unavailable")     # l'auteur est lu dans le dossier configuré : la ligne existe
        self.assertNotIn(SENTINELLE, fait.stdout + fait.stderr)


    def test_lancement_manuel_par_le_lien_du_labo_sans_variable_lit_l_auteur_dans_le_dossier_de_contenu(self):
        # R-43 (D2) : le dossier de code est un arbre Git lié au dépôt de développement ; sans PMZILLA_LAB_WORKSPACE, le contenu est ce dépôt.
        home = self.tmp / "home"
        lab = home / "PMZilla-Lab"
        dev = lab / "workspace"
        (dev / ".pmzilla").mkdir(parents=True)
        (dev / ".pmzilla" / "cases.yaml").write_text("author: auteur-de-test\n", encoding="utf-8")
        creer_depot_et_arbre(dev, lab / "run")
        run_tools = lab / "run" / "tools"
        shutil.copytree(RACINE / "tools", run_tools, ignore=shutil.ignore_patterns("__pycache__", "*.lock"))
        (lab / "morning_summary.py").symlink_to(run_tools / "morning_summary.py")
        self.tout_connu()
        env = {k: v for k, v in os.environ.items() if k not in ("PMZILLA_LAB_CASES_AUTHOR", "PMZILLA_LAB_WORKSPACE", "PMZILLA_LAB_RUN")}
        env.update(HOME=str(home), PMZILLA_LAB_DB_PORT="1", PMZILLA_LAB_DB_SECURITY_BIN=str(self.tmp / "absent"))
        fait = subprocess.run([sys.executable, "-I", str(lab / "morning_summary.py"), "--json"], capture_output=True, text=True, env=env,
                              cwd=self.tmp, timeout=60)
        self.assertEqual(fait.returncode, 0, fait.stderr)
        self.assertEqual(json.loads(fait.stdout)["reviews"]["state"], "unavailable")     # l'auteur est trouvé : la ligne existe


GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}


def creer_depot_et_arbre(depot: Path, arbre: Path):
    """Dépôt Git avec un commit, puis un second dossier lié (git worktree)."""
    env = {**os.environ, **GIT_ENV}
    depot.mkdir(parents=True, exist_ok=True)
    for cmd in (["init", "-q"], ["commit", "-q", "--allow-empty", "-m", "x"], ["worktree", "add", "-q", "--detach", str(arbre)]):
        subprocess.run(["git", "-C", str(depot), *cmd], check=True, env=env, capture_output=True, stdin=subprocess.DEVNULL)


class DossierContenu(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        sys.path.insert(0, str(RACINE / "tools"))
        import morning_summary
        self.ms = morning_summary
        self.addCleanup(lambda: sys.path.remove(str(RACINE / "tools")))

    def avec_env(self, **kw):
        from unittest import mock
        env = {k: v for k, v in os.environ.items() if k != "PMZILLA_LAB_WORKSPACE"}
        env.update(kw)
        return mock.patch.dict(os.environ, env, clear=True)

    def test_la_variable_gagne(self):
        with self.avec_env(PMZILLA_LAB_WORKSPACE=str(self.tmp / "voulu")):
            self.assertEqual(self.ms.dossier_contenu(self.tmp), self.tmp / "voulu")

    def test_un_arbre_lie_se_resout_vers_le_depot_principal(self):
        creer_depot_et_arbre(self.tmp / "principal", self.tmp / "lie")
        with self.avec_env():
            self.assertEqual(self.ms.dossier_contenu(self.tmp / "lie").resolve(), (self.tmp / "principal").resolve())
            self.assertEqual(self.ms.dossier_contenu(self.tmp / "principal").resolve(), (self.tmp / "principal").resolve())

    def test_git_en_echec_rend_le_dossier_du_code(self):
        (self.tmp / "vide").mkdir()
        with self.avec_env(GIT_CEILING_DIRECTORIES=str(self.tmp)):
            self.assertEqual(self.ms.dossier_contenu(self.tmp / "vide"), self.tmp / "vide")
        creer_depot_et_arbre(self.tmp / "principal", self.tmp / "lie")
        with self.avec_env(PATH=str(self.tmp / "sans-git")):
            self.assertEqual(self.ms.dossier_contenu(self.tmp / "lie"), self.tmp / "lie")


if __name__ == "__main__":
    unittest.main()
