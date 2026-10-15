"""Règles `deny` de la publication de l'édition publique (change edition-publish-tooling, design D16, tâche 2.3).

La session ne lance jamais tools/publish_edition.py (`--help` compris), ne fait ni commit ni push dans la copie locale du dépôt
public (dossier permanent edition-en, ancien nom edition-en-3), et ne lit pas la liste des versions produit
Flux-Lab/versions-produit.txt. Lire le texte de l'outil, lancer sa suite, lancer le lanceur de tests et commiter dans l'espace de
travail privé restent permis.

Aucune commande n'est lancée ; le test ne lit que .claude/settings.json (ou le fichier nommé par la variable
PMZILLA_SETTINGS_POUR_TEST, utile pour vérifier une proposition de règles sur une copie temporaire).

Les règles sont ajoutées à `permissions.deny` par l'utilisateur (tâche 5.1), jamais par la session.
"""
import itertools
import json
import os
import unittest
from pathlib import Path

from test_settings_deny import Base, CHEMINS, LANCEURS, LECTEURS, RACINE, motif_en_regex

SCRIPT = "publish_edition.py"
OPTIONS = ("", " --help", " -h", " --copy ~/PMZilla-Lab/edition-en", " --copy /Users/quelquun/PMZilla-Lab/edition-en --yes")
LANCEMENTS_DIRECTS = ("tools/publish_edition.py", "./tools/publish_edition.py", "~/PMZilla-Lab/workspace/tools/publish_edition.py",
                      "$HOME/PMZilla-Lab/workspace/tools/publish_edition.py",
                      "/Users/quelquun/PMZilla-Lab/workspace/tools/publish_edition.py", "publish_edition.py")

COPIES = ("~/PMZilla-Lab/edition-en", "$HOME/PMZilla-Lab/edition-en", "/Users/quelquun/PMZilla-Lab/edition-en",
          "~/PMZilla-Lab/edition-en-3", "$HOME/PMZilla-Lab/edition-en-3", "/Users/quelquun/PMZilla-Lab/edition-en-3")
GIT_ECRITURES = ("commit -m x", "commit --amend --no-edit", "commit", "push", "push origin main", "push --force-with-lease")

LISTE = "Flux-Lab/versions-produit.txt"
FORMES_LISTE = (LISTE, f"./{LISTE}", f"/Users/quelquun/PMZilla-Lab/workspace/{LISTE}", f"~/PMZilla-Lab/workspace/{LISTE}",
                f"$HOME/PMZilla-Lab/workspace/{LISTE}")
LECTEURS_LISTE = LECTEURS + ("cat -n", "grep -n 1.", "sed -n 1,3p")


class BasePublication(Base):
    @classmethod
    def setUpClass(cls):
        autre = os.environ.get("PMZILLA_SETTINGS_POUR_TEST")
        chemin = Path(autre) if autre else RACINE / ".claude" / "settings.json"
        cls.deny = json.loads(chemin.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.motifs = [motif_en_regex(d[len("Bash("):-1]) for d in cls.deny if d.startswith("Bash(")]


class LancementDeLOutil(BasePublication):
    def test_chaque_lancement_avec_un_lanceur_est_refuse(self):
        for lanceur, chemin, option in itertools.product(LANCEURS, CHEMINS, OPTIONS):
            commande = f"{lanceur} {chemin.format(s=SCRIPT)}{option}"
            self.assertTrue(self.interdite(commande), commande)

    def test_lancement_direct_du_fichier(self):
        for chemin, option in itertools.product(LANCEMENTS_DIRECTS, OPTIONS):
            commande = f"{chemin}{option}"
            self.assertTrue(self.interdite(commande), commande)

    def test_lanceurs_avec_options_de_l_interpreteur(self):
        for commande in ("uv run --isolated tools/publish_edition.py --help", "uv run --with pyyaml python tools/publish_edition.py",
                         "python3 -W ignore tools/publish_edition.py --copy ~/PMZilla-Lab/edition-en",
                         "python -I ~/PMZilla-Lab/workspace/tools/publish_edition.py --help",
                         "uv run -q $HOME/PMZilla-Lab/workspace/tools/publish_edition.py"):
            self.assertTrue(self.interdite(commande), commande)


class CommitEtPushDansLaCopiePublique(BasePublication):
    def test_git_c_sur_la_copie_est_refuse(self):
        for copie, action in itertools.product(COPIES, GIT_ECRITURES):
            for commande in (f"git -C {copie} {action}", f"git -C {copie}/ {action}", f"git -C '{copie}' {action}"):
                self.assertTrue(self.interdite(commande), commande)

    def test_cd_dans_la_copie_puis_commit_ou_push_est_refuse(self):
        for copie, action in itertools.product(COPIES, GIT_ECRITURES):
            commande = f"cd {copie} && git {action}"
            self.assertTrue(self.interdite(commande), commande)

    def test_cd_dans_la_copie_puis_point_virgule_est_refuse(self):
        for copie, action in itertools.product(COPIES, GIT_ECRITURES):
            commande = f"cd {copie}; git {action}"
            self.assertTrue(self.interdite(commande), commande)

    def test_git_dir_sur_la_copie_est_refuse(self):
        for copie, action in itertools.product(COPIES, GIT_ECRITURES):
            for commande in (f"git --git-dir={copie}/.git {action}", f"git --git-dir {copie}/.git {action}",
                             f"git --git-dir={copie}/.git --work-tree={copie} {action}"):
                self.assertTrue(self.interdite(commande), commande)


class ListeDesVersionsProduit(BasePublication):
    def test_lecture_par_l_outil_read(self):
        self.assertIn(f"Read(./{LISTE})", self.deny)

    def test_lecture_par_les_commandes_du_terminal(self):
        for lecteur, forme in itertools.product(LECTEURS_LISTE, FORMES_LISTE):
            self.assertTrue(self.interdite(f"{lecteur} {forme}"), f"{lecteur} {forme}")


class CeQuiResteAutorise(BasePublication):
    def test_lire_le_texte_de_l_outil_et_lancer_ses_tests(self):
        for commande in ("cat tools/publish_edition.py", "head -60 tools/publish_edition.py", "grep -n 'def ' tools/publish_edition.py",
                         "sed -n 1,40p tools/publish_edition.py", "wc -l tools/publish_edition.py",
                         "git log --oneline -3 -- tools/publish_edition.py", "ls tests/publish_edition",
                         "bash tests/run_all.sh publish_edition", "bash tests/run_all.sh settings_deny",
                         "uv run python -m unittest discover tests/publish_edition",
                         "uv run python -m unittest discover -s tests/publish_edition -q -f"):
            self.assertFalse(self.interdite(commande), commande)

    def test_commit_et_push_dans_l_espace_de_travail_prive(self):
        for commande in ("git commit -m x", "git push", "git push origin feat/edition-publish-tooling",
                         "git -C /Users/quelquun/PMZilla-Lab/workspace commit -m x",
                         "git -C ~/PMZilla-Lab/workspace push", "git -C $HOME/PMZilla-Lab/workspace commit -m x",
                         "cd /Users/quelquun/PMZilla-Lab/workspace && git commit -m x",
                         "cd ~/PMZilla-Lab/workspace && git push", "cd ~/PMZilla-Lab/workspace; git commit -m x",
                         "git --git-dir=/Users/quelquun/PMZilla-Lab/workspace/.git push",
                         "git --git-dir=~/PMZilla-Lab/edition-en/.git log --oneline -3"):
            self.assertFalse(self.interdite(commande), commande)

    def test_lectures_dans_la_copie_publique_et_autres_listes(self):
        """Seuls commit et push dans la copie sont refusés : l'état de la copie se lit (status, log, diff)."""
        for copie in COPIES:
            for commande in (f"git -C {copie} status --short", f"git -C {copie} log --oneline -3", f"git -C {copie} diff --stat",
                             f"ls {copie}"):
                self.assertFalse(self.interdite(commande), commande)
        for commande in ("cat Flux-Lab/flux.yaml", "cat Flux-Lab/rapports/flux-serie-2026-10-06.md", "ls Flux-Lab"):
            self.assertFalse(self.interdite(commande), commande)


if __name__ == "__main__":
    unittest.main()
