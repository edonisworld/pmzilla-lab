"""
Tests des étapes repo, hooks et links du script d'installation (tools/install_lab_repo.py ; design D14 lignes repo, hooks, links, D15).
Écrits avant le code (change install-script).

    python3 -W ignore -m unittest discover -s tests/install_lab -p "test_repo.py" -q -f
"""
import os
import unittest

from aide_install import CasDeBase

QUARANTAINE = 'case "$1" in -c) rm -f "$INSTALL_LAB_ETAT/quarantaine" ;; -l) [ -e "$INSTALL_LAB_ETAT/quarantaine" ] && echo "com.apple.quarantine: 0083;00000000;Safari;" ; exit 0 ;; esac'


class Base(CasDeBase):
    def setUp(self):
        super().setUp()
        tools = self.fx.racine / "tools"
        (tools / "hooks").mkdir(exist_ok=True)
        (tools / "hooks" / "pre-commit").write_text("#!/bin/sh\n", encoding="utf-8")
        (tools / "hooks" / "pre-commit").chmod(0o755)
        for nom in ("watch.sh", "db_backup.sh"):
            (tools / nom).chmod(0o755)
        self.fx.simulacre("xattr", QUARANTAINE)

    def fichiers(self):
        tools = self.fx.racine / "tools"
        return sorted(tools.glob("*.sh")) + sorted((tools / "hooks").glob("*"))

    def lancer(self, etape, *args, **kw):
        return self.fx.lancer("--mode", "fresh", "--step", etape, *args, **kw)


class Repo(Base):
    def test_deja_fait(self):
        p = self.lancer("repo")
        self.assertIn("step repo: already done, skipped", p.lignes())
        self.assertEqual(p.code, 0, p.texte)
        self.assertEqual(self.fx.appels_qui_changent(p.appels), [])

    def test_script_non_executable(self):
        (self.fx.racine / "tools" / "watch.sh").chmod(0o644)
        p = self.lancer("repo", reponses="y\n")
        self.assertEqual(p.code, 0, p.texte)
        self.assertTrue(any(a.startswith("xattr -c") for a in p.appels))
        self.assertTrue(all(os.access(f, os.X_OK) for f in self.fichiers()))

    def test_quarantaine(self):
        self.fx.drapeau("quarantaine")
        p = self.lancer("repo", reponses="y\n")
        self.assertEqual(p.code, 0, p.texte)
        self.assertFalse(self.fx.a_drapeau("quarantaine"))
        second = self.lancer("repo")
        self.assertIn("step repo: already done, skipped", second.lignes())
        self.assertEqual(self.fx.appels_qui_changent(second.appels), [])

    def test_refus_par_defaut(self):
        self.fx.drapeau("quarantaine")
        (self.fx.racine / "tools" / "watch.sh").chmod(0o644)
        avant = self.fx.empreinte()
        p = self.lancer("repo", reponses="\n")
        self.assertEqual(p.code, 4, p.texte)
        self.assertIn("step repo: declined", p.texte)
        self.assertEqual(self.fx.appels_qui_changent(p.appels), [])
        self.assertTrue(self.fx.a_drapeau("quarantaine"))
        self.assertEqual(self.fx.empreinte(), avant)
        self.assertFalse(os.access(self.fx.racine / "tools" / "watch.sh", os.X_OK))

    def test_passage_a_blanc(self):
        self.fx.drapeau("quarantaine")
        (self.fx.racine / "tools" / "watch.sh").chmod(0o644)
        avant = self.fx.empreinte()
        p = self.lancer("repo", "--dry-run")
        self.assertEqual(p.code, 0, p.texte)
        self.assertTrue(any(l.startswith("dry run: would run") for l in p.lignes()))
        self.assertEqual(self.fx.appels_qui_changent(p.appels), [])
        self.assertEqual(self.fx.empreinte(), avant)
        self.assertFalse(os.access(self.fx.racine / "tools" / "watch.sh", os.X_OK))

    def test_echec(self):
        self.fx.drapeau("quarantaine")
        self.fx.simulacre("xattr", 'case "$1" in -c) exit 1 ;; -l) echo "com.apple.quarantine: 0083"; exit 0 ;; esac')
        p = self.lancer("repo", reponses="y\n")
        self.assertEqual(p.code, 1, p.texte)
        self.assertRegex(p.texte, r"step repo: failed: .*xattr")


class Scripts(Base):
    def cas(self, etape, script, drapeau, interpreteur):
        return etape, script, drapeau, interpreteur

    def chacun(self):
        return (("hooks", "install_hooks.sh", "hooks-ok", "sh"), ("links", "install_links.sh", "links-ok", "zsh"))

    def test_deja_en_place(self):
        for etape, script, drapeau, interp in self.chacun():
            with self.subTest(etape):
                self.fx.drapeau(drapeau)
                p = self.lancer(etape)
                self.assertEqual(p.code, 0, p.texte)
                self.assertIn(f"step {etape}: already done, skipped", p.lignes())
                self.assertEqual(p.appels_de(script), [f"{script} --verify"])

    def test_installation_puis_verification(self):
        for etape, script, drapeau, interp in self.chacun():
            with self.subTest(etape):
                p = self.lancer(etape, reponses="y\n")
                self.assertEqual(p.code, 0, p.texte)
                self.assertEqual([a.strip() for a in p.appels_de(script)], [f"{script} --verify", script, f"{script} --verify"])
                self.assertTrue(self.fx.a_drapeau(drapeau))
                second = self.lancer(etape)
                self.assertIn(f"step {etape}: already done, skipped", second.lignes())
                self.assertEqual(self.fx.appels_qui_changent(second.appels), [])

    def test_refus_par_defaut(self):
        for etape, script, drapeau, interp in self.chacun():
            with self.subTest(etape):
                avant = self.fx.empreinte()
                p = self.lancer(etape, reponses="\n")
                self.assertEqual(p.code, 4, p.texte)
                self.assertIn(f"step {etape}: declined", p.texte)
                self.assertEqual(self.fx.appels_qui_changent(p.appels), [])
                self.assertFalse(self.fx.a_drapeau(drapeau))
                self.assertEqual(self.fx.empreinte(), avant)

    def test_passage_a_blanc(self):
        for etape, script, drapeau, interp in self.chacun():
            with self.subTest(etape):
                avant = self.fx.empreinte()
                p = self.lancer(etape, "--dry-run")
                self.assertEqual(p.code, 0, p.texte)
                self.assertTrue(any(l.startswith("dry run: would run") and f"{interp} " in l and script in l for l in p.lignes()), p.texte)
                self.assertEqual(self.fx.appels_qui_changent(p.appels), [])
                self.assertEqual(self.fx.empreinte(), avant)

    def test_echec_de_l_installation(self):
        for etape, script, drapeau, interp in self.chacun():
            with self.subTest(etape):
                self.fx.drapeau(f"{script}-echec")
                p = self.lancer(etape, reponses="y\n")
                self.assertEqual(p.code, 1, p.texte)
                self.assertRegex(p.texte, rf"step {etape}: failed: .*{script}")

    def test_verification_qui_echoue_apres_installation(self):
        # l'installateur rend 0 mais ne pose pas l'état : la vérification échoue
        (self.fx.racine / "tools" / "install_hooks.sh").write_text(
            '#!/bin/sh\necho "install_hooks.sh $*" >> "$INSTALL_LAB_APPELS"\n[ "$1" = "--verify" ] && exit 1\nexit 0\n', encoding="utf-8")
        p = self.lancer("hooks", reponses="y\n")
        self.assertEqual(p.code, 1, p.texte)
        self.assertRegex(p.texte, r"step hooks: failed: .*--verify")

    def test_dependance_repo_et_drapeau_liens(self):
        # sans --step : hooks et links passent après repo ; liens_ok posé (observable : links déjà fait)
        self.fx.drapeau("hooks-ok")
        self.fx.drapeau("links-ok")
        p = self.fx.lancer("--mode", "fresh", "--start-at", "repo")
        self.assertIn("step links: already done, skipped", p.lignes())
        self.assertEqual(self.fx.appels_qui_changent(p.appels), [])
        self.assertEqual(p.appels_de("install_links.sh"), ["install_links.sh --verify"])


if __name__ == "__main__":
    unittest.main()
