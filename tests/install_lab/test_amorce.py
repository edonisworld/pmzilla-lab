"""Tests de l'amorce zsh (change install-script, design D1, D2, D16, D17 ; spec « Bootstrap before the Python launcher exists »).
L'amorce réelle est lancée avec zsh contre le décor factice ; jamais pour de vrai."""
from __future__ import annotations

import os
import shutil
import subprocess
import unittest
from pathlib import Path

from aide_install import AMORCE, CasDeBase

DEPOT = "https://example.invalid/lab.git"


class CasAmorce(CasDeBase):
    def setUp(self):
        super().setUp()
        fx = self.fx
        fx.simulacre("brew")
        fx.simulacre("uv")
        # PATH minimal : simulacres + zsh seul (pas de /usr/bin, qui servirait un vrai git)
        self.outils = fx.tmp / "outils"
        self.outils.mkdir()
        for outil in ("zsh", "chmod"):     # chmod : pour les simulacres qui en créent d'autres
            (self.outils / outil).symlink_to(shutil.which(outil))
        self.env = {"PATH": f"{fx.simulacres}:{self.outils}", "INSTALL_LAB_BREW_PREFIX": str(fx.tmp / "sans-brew")}
        self.copie = fx.copier_amorce()

    def lancer(self, *args, reponses="", depuis=None, env=None):
        e = dict(self.env)
        e.update(env or {})
        return self.fx.lancer_amorce(*args, reponses=reponses, env=e, depuis=depuis or self.copie)

    def hors_clone(self):
        """Copie de l'amorce dans un dossier sans .git et dépôt factice absent de la cible (INSTALL_LAB_ROOT vidé)."""
        dossier = self.fx.tmp / "ailleurs" / "tools"
        dossier.mkdir(parents=True)
        copie = dossier / AMORCE.name
        shutil.copy(AMORCE, copie)
        shutil.rmtree(self.fx.racine)
        return copie, {"INSTALL_LAB_ROOT": ""}

    def installations(self, p):
        return [a for a in p.appels if a.startswith("brew install")]


class Syntaxe(unittest.TestCase):
    def test_zsh_n(self):
        r = subprocess.run(["zsh", "-n", str(AMORCE)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)


class Plateforme(CasAmorce):
    def test_architecture_refusee(self):
        self.fx.simulacre("uname", 'case "$1" in -m) echo x86_64 ;; *) echo Darwin ;; esac')
        p = self.lancer("--mode", "fresh")
        self.assertEqual(p.code, 3)
        self.assertIn("Apple Silicon", p.texte)
        self.assertEqual(p.appels_de("uv"), [])

    def test_systeme_refuse(self):
        self.fx.simulacre("uname", 'case "$1" in -m) echo arm64 ;; *) echo Linux ;; esac')
        self.assertEqual(self.lancer("--mode", "fresh").code, 3)


class Homebrew(CasAmorce):
    def test_absent(self):
        self.fx.retirer("brew")
        p = self.lancer("--mode", "fresh")
        self.assertEqual(p.code, 3)
        self.assertIn("Homebrew not found", p.texte)
        self.assertIn("https://brew.sh", p.texte)
        self.assertEqual(self.installations(p), [])
        self.assertEqual(p.appels_de("uv"), [])

    def test_environnement_du_prefixe_charge(self):
        self.fx.retirer("brew")
        prefixe = self.fx.tmp / "prefixe"
        (prefixe / "bin").mkdir(parents=True)
        faux = prefixe / "bin" / "brew"
        faux.write_text(f'#!/bin/sh\necho "brew $*" >> "$INSTALL_LAB_APPELS"\n'
                        f'[ "$1" = shellenv ] && echo \'export PATH="{prefixe}/bin:{self.fx.simulacres}:{self.outils}"\'\nexit 0\n')
        faux.chmod(0o755)
        p = self.lancer("--mode", "fresh", env={"INSTALL_LAB_BREW_PREFIX": str(prefixe)})
        self.assertEqual(p.code, 0, p.texte)
        self.assertTrue(any(a.startswith("brew shellenv") for a in p.appels))


class Placement(CasAmorce):
    def test_clone_ailleurs(self):
        autre = self.fx.tmp / "autre"
        (autre / "tools").mkdir(parents=True)
        (autre / ".git").mkdir()
        shutil.copy(AMORCE, autre / "tools" / AMORCE.name)
        avant = self.fx.empreinte()
        p = self.lancer("--mode", "fresh", depuis=autre / "tools" / AMORCE.name, env={"INSTALL_LAB_ROOT": ""})
        self.assertEqual(p.code, 3)
        self.assertIn("clone must be at", p.texte)
        self.assertIn("PMZilla-Lab/workspace", p.texte)
        self.assertEqual(p.appels_de("uv"), [])
        self.assertEqual(self.fx.empreinte(), avant)

    def test_cible_existante_non_clone(self):
        copie, env = self.hors_clone()
        (self.fx.racine / "tools").mkdir(parents=True)   # dossier sans .git
        (self.fx.racine / "note.txt").write_text("a")
        avant = self.fx.empreinte()
        p = self.lancer("--mode", "fresh", "--repo", DEPOT, depuis=copie, env=env, reponses="y\ny\n")
        self.assertEqual(p.code, 3)
        self.assertEqual(p.appels_de("git"), [])
        self.assertEqual(self.fx.empreinte(), avant)

    def test_hors_clone_sans_repo(self):
        copie, env = self.hors_clone()
        p = self.lancer("--mode", "fresh", depuis=copie, env=env)
        self.assertEqual(p.code, 2)
        self.assertIn("--repo", p.texte)
        self.assertEqual(p.appels_de("git"), [])
        self.assertFalse(self.fx.racine.exists())


class Clonage(CasAmorce):
    def test_clone_confirme_puis_remise(self):
        copie, env = self.hors_clone()
        p = self.lancer("--mode", "fresh", "--repo", DEPOT, depuis=copie, env=env, reponses="y\n")
        self.assertEqual(p.code, 0, p.texte)
        self.assertEqual(p.appels_de("git"), [f"git clone {DEPOT} {self.fx.racine}"])
        self.assertEqual(len(p.appels_de("uv")), 1)
        self.assertTrue(p.appels[-1].startswith("uv run "))
        self.assertLess(p.appels.index(f"git clone {DEPOT} {self.fx.racine}"), p.appels.index(p.appels_de("uv")[0]))

    def test_refus_ne_clone_pas(self):
        copie, env = self.hors_clone()
        for reponses in ("n\n", "\n", ""):
            p = self.lancer("--mode", "fresh", "--repo", DEPOT, depuis=copie, env=env, reponses=reponses)
            self.assertEqual(p.code, 4, p.texte)
            self.assertIn("step bootstrap: declined", p.texte)
            self.assertEqual(p.appels_de("git"), [])
            self.assertEqual(p.appels_de("uv"), [])

    def test_reponse_yes_en_toute_casse(self):
        copie, env = self.hors_clone()
        p = self.lancer("--mode", "fresh", "--repo", DEPOT, depuis=copie, env=env, reponses="YES\n")
        self.assertEqual(p.code, 0, p.texte)

    def test_echec_du_clone(self):
        copie, env = self.hors_clone()
        self.fx.simulacre("git", "exit 1")
        p = self.lancer("--mode", "fresh", "--repo", DEPOT, depuis=copie, env=env, reponses="y\n")
        self.assertEqual(p.code, 1)
        self.assertIn("step bootstrap: failed: git clone", p.texte)
        self.assertEqual(p.appels_de("uv"), [])

    def test_passage_a_blanc_hors_clone(self):
        copie, env = self.hors_clone()
        avant = self.fx.empreinte()
        p = self.lancer("--mode", "fresh", "--dry-run", "--repo", DEPOT, depuis=copie, env=env)
        self.assertEqual(p.code, 0, p.texte)
        self.assertIn(f"dry run: would run git clone {DEPOT} {self.fx.racine}", p.texte)
        self.assertIn("dry run: the remaining steps need the clone", p.texte)
        self.assertEqual(self.fx.appels_qui_changent(p.appels), [])
        self.assertEqual(p.appels_de("uv"), [])
        self.assertFalse(self.fx.racine.exists())
        self.assertEqual(self.fx.empreinte(), avant)


class OutilsManquants(CasAmorce):
    def test_git_et_uv_manquants_installation_confirmee(self):
        self.fx.retirer("git")
        self.fx.retirer("uv")
        # l'installation factice de uv le rend disponible pour la remise
        self.fx.simulacre("brew", f'if [ "$*" = "install uv" ]; then printf \'#!/bin/sh\\necho "uv $*" >> "$INSTALL_LAB_APPELS"\\n\' > "{self.fx.simulacres}/uv"; chmod +x "{self.fx.simulacres}/uv"; fi; exit 0')
        p = self.lancer("--mode", "fresh", reponses="y\ny\n")
        self.assertEqual(self.installations(p), ["brew install git", "brew install uv"])
        self.assertEqual(p.code, 0, p.texte)
        self.assertEqual(len(p.appels_de("uv")), 1)

    def test_refus_de_l_installation(self):
        self.fx.retirer("git")
        p = self.lancer("--mode", "fresh", reponses="n\n")
        self.assertEqual(p.code, 4)
        self.assertIn("step bootstrap: declined", p.texte)
        self.assertEqual(self.installations(p), [])
        self.assertEqual(p.appels_de("uv"), [])

    def test_sans_reponse_rien_n_est_installe(self):
        self.fx.retirer("uv")
        p = self.lancer("--mode", "fresh", reponses="")
        self.assertEqual(p.code, 4)
        self.assertEqual(self.installations(p), [])

    def test_echec_de_l_installation(self):
        self.fx.retirer("git")
        self.fx.simulacre("brew", "exit 1")
        p = self.lancer("--mode", "fresh", reponses="y\n")
        self.assertEqual(p.code, 1)
        self.assertIn("step bootstrap: failed: brew install git", p.texte)

    def test_passage_a_blanc_annonce_les_installations(self):
        self.fx.retirer("git")
        self.fx.retirer("uv")
        avant = self.fx.empreinte()
        p = self.lancer("--mode", "fresh", "--dry-run")
        self.assertEqual(p.code, 0, p.texte)
        self.assertIn("dry run: would run brew install git", p.texte)
        self.assertIn("dry run: would run brew install uv", p.texte)
        self.assertEqual(self.fx.appels_qui_changent(p.appels), [])
        self.assertEqual(self.fx.empreinte(), avant)


class Remise(CasAmorce):
    def test_tous_les_arguments_passent(self):
        p = self.lancer("--mode", "fresh", "--dry-run", "--step", "hooks", "--repo", DEPOT)
        self.assertEqual(p.code, 0, p.texte)
        attendu = f"uv run {self.fx.racine}/tools/install_lab.py --mode fresh --dry-run --step hooks --repo {DEPOT}"
        self.assertEqual(p.appels_de("uv"), [attendu])
        self.assertEqual(self.installations(p), [])

    def test_aide_et_liste_directes(self):
        # même sans brew ni git : pas de contrôle d'état
        self.fx.retirer("brew")
        self.fx.retirer("git")
        for option in ("--help", "--list"):
            p = self.lancer(option)
            self.assertEqual(p.code, 0, p.texte)
            self.assertEqual(p.appels_de("uv"), [f"uv run {self.fx.racine}/tools/install_lab.py {option}"])


class Gardes(unittest.TestCase):
    def test_pas_de_yes_ni_de_trousseau(self):
        texte = AMORCE.read_text(encoding="utf-8")
        self.assertNotIn("--yes", texte)
        self.assertNotIn("security", texte)


if __name__ == "__main__":
    unittest.main()
