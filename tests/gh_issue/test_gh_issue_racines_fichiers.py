"""
Tests de tools/gh_issue.py sous l'enveloppe figée du bac à sable (niveau 2, revue de K3 : B4, B5, R4 et point (b) ; R-20261109-09, -12) :
  - les deux racines : RACINE_CODE (réglages, imports) et RACINE (le dépôt sur lequel porte la commande), posée par l'enveloppe ;
  - l'ouverture contrôlée des fichiers (--body-file, --comment-file, --description-file en lecture, --sortie en écriture) quand l'enveloppe a posé les dossiers
    permis : lien symbolique, lien physique, fichier d'un autre propriétaire, hors des dossiers, sans troncature avant le contrôle ; sans les variables,
    le comportement d'avant ;
  - le nom d'un change validé avant de devenir un chemin (R4).
Aucun gh, aucun réseau : les fonctions sont appelées directement, dans des dossiers jetables.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/gh_issue -q -f
"""
import argparse
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import gh_issue as g  # noqa: E402
import roadmap_model as rm  # noqa: E402


class Dossiers(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(os.path.realpath(self.tmp.name))
        self.permis = self.base / "permis"
        self.ailleurs = self.base / "ailleurs"
        self.voisin = self.base / "permis-voisin"          # même début de nom que le dossier permis : un préfixe n'est pas un dossier parent
        for d in (self.permis, self.ailleurs, self.voisin):
            d.mkdir()


class Fichiers(Dossiers):
    def setUp(self):
        super().setUp()
        self.fichier = self.permis / "corps.md"
        self.fichier.write_text("texte\n", encoding="utf-8")
        p = mock.patch.dict(os.environ, {g.ENV_BASES_LECTURE: str(self.permis), g.ENV_BASES_SORTIE: str(self.permis)})
        p.start()
        self.addCleanup(p.stop)

    def lit(self, chemin):
        return g.read_text_file(chemin, "--body-file")

    def refuse_lecture(self, chemin):
        with self.assertRaises(g.Stop) as e:
            self.lit(chemin)
        self.assertEqual(e.exception.code, 2)

    # --- lecture -----------------------------------------------------------------------------------------------------------------------
    def test_un_fichier_ordinaire_sous_la_base_est_lu(self):
        self.assertEqual(self.lit(self.fichier), "texte\n")
        self.assertEqual(self.lit(str(self.fichier)), "texte\n")

    def test_plusieurs_bases_separees_par_deux_points(self):
        with mock.patch.dict(os.environ, {g.ENV_BASES_LECTURE: f"{self.ailleurs}:{self.permis}"}):
            self.assertEqual(self.lit(self.fichier), "texte\n")

    def test_lien_symbolique_refuse_meme_vers_un_fichier_permis(self):
        lien = self.permis / "lien.md"
        lien.symlink_to(self.fichier)
        self.refuse_lecture(lien)
        dehors = self.ailleurs / "secret.md"
        dehors.write_text("secret\n", encoding="utf-8")
        lien2 = self.permis / "lien-dehors.md"
        lien2.symlink_to(dehors)
        self.refuse_lecture(lien2)

    def test_lien_physique_refuse(self):
        dur = self.permis / "dur.md"
        try:
            os.link(self.fichier, dur)
        except OSError:
            self.skipTest("liens physiques impossibles ici")
        self.refuse_lecture(self.fichier)           # deux noms pour le même fichier : refusé sous l'un comme sous l'autre
        self.refuse_lecture(dur)

    def test_fichier_d_un_autre_proprietaire_refuse(self):
        with mock.patch.object(g.os, "getuid", return_value=os.getuid() + 1):
            self.refuse_lecture(self.fichier)

    def test_fichier_hors_de_la_base_refuse(self):
        dehors = self.ailleurs / "corps.md"
        dehors.write_text("texte\n", encoding="utf-8")
        voisin = self.voisin / "corps.md"
        voisin.write_text("texte\n", encoding="utf-8")
        for chemin in (dehors, voisin):
            with self.subTest(chemin=chemin.parent.name):
                self.refuse_lecture(chemin)

    def test_un_dossier_ou_un_fichier_absent_refuse(self):
        self.refuse_lecture(self.permis)
        self.refuse_lecture(self.permis / "absent.md")

    def test_sans_la_variable_le_comportement_d_avant_reste(self):
        lien = self.permis / "lien.md"
        lien.symlink_to(self.fichier)
        dehors = self.ailleurs / "corps.md"
        dehors.write_text("dehors\n", encoding="utf-8")
        with mock.patch.dict(os.environ):
            os.environ.pop(g.ENV_BASES_LECTURE)
            os.environ.pop(g.ENV_BASES_SORTIE)
            self.assertEqual(self.lit(lien), "texte\n")
            self.assertEqual(self.lit(dehors), "dehors\n")
            sortie = self.ailleurs / "sortie.json"
            g.ecrire_texte(sortie, "x\n")
            self.assertEqual(sortie.read_text(encoding="utf-8"), "x\n")

    def test_les_commandes_lisent_par_ce_chemin(self):
        """La lecture d'un --body-file d'idée et celle de cmd_comment passent par le contrôle : un lien refusé donne le code 2."""
        lien = self.permis / "lien.md"
        lien.symlink_to(self.fichier)
        with self.assertRaises(g.Stop) as e:
            g.read_body_file(lien)
        self.assertEqual(e.exception.code, 2)
        with self.assertRaises(OSError):
            g.lire_texte(lien)

    # --- écriture (--sortie) -------------------------------------------------------------------------------------------------------------
    def test_ecriture_dans_la_base_cree_le_fichier_en_0600_et_remplace_le_contenu(self):
        sortie = self.permis / "sortie.json"
        g.ecrire_texte(sortie, "premier contenu assez long\n")
        self.assertEqual(oct(sortie.stat().st_mode & 0o777), oct(0o600))
        g.ecrire_texte(sortie, "court\n")
        self.assertEqual(sortie.read_text(encoding="utf-8"), "court\n")           # tronqué après le contrôle, pas de reste de l'ancien contenu

    def test_ecriture_hors_de_la_base_refusee_sans_toucher_au_fichier(self):
        for dossier in (self.ailleurs, self.voisin):
            with self.subTest(dossier=dossier.name):
                existant = dossier / "sortie.json"
                existant.write_text("a garder\n", encoding="utf-8")
                with self.assertRaises(OSError):
                    g.ecrire_texte(existant, "ecrase\n")
                self.assertEqual(existant.read_text(encoding="utf-8"), "a garder\n")        # sans O_TRUNC : rien n'est tronqué avant le contrôle

    def test_ecriture_par_un_lien_symbolique_refusee(self):
        cible = self.permis / "cible.json"
        cible.write_text("a garder\n", encoding="utf-8")
        lien = self.permis / "lien.json"
        lien.symlink_to(cible)
        with self.assertRaises(OSError):
            g.ecrire_texte(lien, "ecrase\n")
        self.assertEqual(cible.read_text(encoding="utf-8"), "a garder\n")

    def test_ecriture_dans_un_fichier_a_lien_physique_refusee(self):
        cible = self.permis / "cible.json"
        cible.write_text("a garder\n", encoding="utf-8")
        dur = self.ailleurs / "dur.json"
        try:
            os.link(cible, dur)
        except OSError:
            self.skipTest("liens physiques impossibles ici")
        with self.assertRaises(OSError):
            g.ecrire_texte(cible, "ecrase\n")
        self.assertEqual(dur.read_text(encoding="utf-8"), "a garder\n")

    def test_ecriture_dans_un_fichier_d_un_autre_proprietaire_refusee(self):
        cible = self.permis / "cible.json"
        cible.write_text("a garder\n", encoding="utf-8")
        with mock.patch.object(g.os, "getuid", return_value=os.getuid() + 1):
            with self.assertRaises(OSError):
                g.ecrire_texte(cible, "ecrase\n")
        self.assertEqual(cible.read_text(encoding="utf-8"), "a garder\n")

    def test_les_bases_d_ecriture_et_de_lecture_sont_distinctes(self):
        with mock.patch.dict(os.environ, {g.ENV_BASES_LECTURE: f"{self.permis}:{self.ailleurs}", g.ENV_BASES_SORTIE: str(self.permis)}):
            g.ecrire_texte(self.permis / "ok.json", "x\n")
            with self.assertRaises(OSError):
                g.ecrire_texte(self.ailleurs / "pas-ok.json", "x\n")

    def test_emit_read_ecrit_dans_la_base_et_refuse_ailleurs_par_le_code_2(self):
        a = argparse.Namespace(sortie=str(self.permis / "lecture.json"))
        self.assertEqual(g.emit_read(a, [], {}), "wrote 0 issue(s)")
        self.assertTrue((self.permis / "lecture.json").is_file())
        with self.assertRaises(g.Stop) as e:
            g.emit_read(argparse.Namespace(sortie=str(self.ailleurs / "lecture.json")), [], {})
        self.assertEqual(e.exception.code, 2)


class Racines(unittest.TestCase):
    def valeurs(self, variable=None):
        env = {k: v for k, v in os.environ.items() if k != g.ENV_RACINE}
        if variable is not None:
            env[g.ENV_RACINE] = variable
        r = subprocess.run([sys.executable, "-c", "import gh_issue as g; print(g.RACINE); print(g.RACINE_CODE); print(g.racine_reglages())"],
                           cwd=str(RACINE / "tools"), env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return [Path(l) for l in r.stdout.splitlines()]

    def test_sans_la_variable_les_deux_racines_sont_le_dossier_du_code(self):
        racine, code, reglages = self.valeurs()
        self.assertEqual(code, RACINE)
        self.assertEqual((racine, reglages), (RACINE, RACINE))

    def test_avec_la_variable_la_racine_change_pas_le_dossier_du_code_ni_les_reglages(self):
        with tempfile.TemporaryDirectory() as autre:
            racine, code, reglages = self.valeurs(autre)
            self.assertEqual(racine, Path(autre))
            self.assertEqual((code, reglages), (RACINE, RACINE))

    def test_une_variable_non_absolue_est_ignoree(self):
        for valeur in ("relatif/dossier", ""):
            with self.subTest(valeur=valeur):
                racine, code, _ = self.valeurs(valeur)
                self.assertEqual((racine, code), (RACINE, RACINE))

    def test_les_reglages_se_lisent_dans_le_dossier_du_code_quand_l_enveloppe_a_pose_une_racine(self):
        with tempfile.TemporaryDirectory() as t:
            code, depot = Path(t) / "code", Path(t) / "depot"
            for dossier, release in ((code, "Kraken"), (depot, "Hydra")):
                (dossier / "tools").mkdir(parents=True)
                (dossier / rm.SETTINGS_FILE).write_text(f"current_release: {release}\n", encoding="utf-8")
            with mock.patch.object(g, "RACINE_CODE", code), mock.patch.object(g, "RACINE", depot):
                with mock.patch.dict(os.environ, {g.ENV_RACINE: str(depot)}):
                    self.assertEqual(g.current_release(), "Kraken")                      # le dépôt de la session ne change pas la release
                with mock.patch.dict(os.environ):
                    os.environ.pop(g.ENV_RACINE, None)
                    self.assertEqual(g.current_release(), "Hydra")                       # hors enveloppe : comme avant


class NomDeChange(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dossier = Path(os.path.realpath(self.tmp.name))
        self.root = self.dossier / "root"
        (self.root / "openspec" / "changes" / "demo").mkdir(parents=True)
        (self.root / "openspec" / "changes" / "demo" / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
        archive = self.root / "openspec" / "changes" / "archive" / "2026-10-11-old"
        archive.mkdir(parents=True)
        (archive / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
        (self.dossier / "secret").mkdir()
        (self.dossier / "secret" / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
        q = mock.patch.object(g, "RACINE", self.root)
        q.start()
        self.addCleanup(q.stop)

    def test_un_change_ouvert_et_un_chemin_d_archive_sont_resolus(self):
        self.assertEqual(g.tasks_path("demo"), self.root / "openspec" / "changes" / "demo" / "tasks.md")
        self.assertEqual(g.tasks_path("old"), self.root / "openspec" / "changes" / "archive" / "2026-10-11-old" / "tasks.md")
        complet = "openspec/changes/archive/2026-10-11-old"
        self.assertEqual(g.tasks_path(complet), self.root / complet / "tasks.md")
        self.assertIsNone(g.tasks_path("absent"))

    def test_un_nom_invalide_ou_une_remontee_est_refuse_par_le_code_7_sans_reprendre_le_texte(self):
        mauvais = ("../secret", "..", "demo/../../secret", "a/b", "Demo", "demo.x", "demo ", "", "/etc", "openspec/changes/archive/../../../secret",
                   "openspec/changes/archive/x/../../../../secret", "openspec/changes/archive/2026.10", "openspec/changes/demo", "demo\n")
        for nom in mauvais:
            with self.subTest(nom=nom):
                with self.assertRaises(g.Stop) as e:
                    g.tasks_path(nom)
                self.assertEqual(e.exception.code, 7)
                self.assertNotIn("secret", " ".join(e.exception.lines))


if __name__ == "__main__":
    unittest.main()
