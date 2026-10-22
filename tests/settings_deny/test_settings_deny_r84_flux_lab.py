"""Règles `deny` de R-84 « Flux-Lab : aligner toutes les protections » (GitHub #332), trois volets.

1. Fichier temporaire du catalogue des équipes (`equipes-jira.tmp`, écrit par migrate-teams avant son renommage) : 3 règles Read et
   34 lecteurs du terminal, mêmes formes que le catalogue (`equipes-jira.yaml`). Le motif `*equipes-jira.yaml*` ne le couvre pas.
2. Dossier d'archive de l'ancienne table des équipes : 42 règles (3 Read, 34 lecteurs, 5 commandes de listage), transférées de
   ~/.claude/settings.json vers .claude/settings.json.
3. Six règles `Write(...)` et `NotebookEdit(...)` sur le dossier d'exécution, ignorées par Claude Code, à retirer : la protection
   tient par les trois règles `Edit(...)` du même chemin.

L'auteur pose les règles des volets 1 et 2 et retire celles du volet 3 (r84-poser-regles.sh, hors dépôt) : la session ne modifie jamais
les fichiers de réglages. Tant qu'aucune règle d'un volet n'est posée (ou, pour le volet 3, tant que les six sont encore là), les cas
contre les vrais réglages sont SAUTÉS ; si la pose est partielle, ils échouent en nommant les règles manquantes. La classe
ReglesProposees évalue les mêmes cas sur les listes ci-dessous seules : elle est toujours verte. Les commandes qui ne font que citer
un nom restent permises, vérifié contre les vrais réglages dans tous les cas. Aucune commande n'est lancée ; le test ne lit que
.claude/settings.json.
"""
import itertools
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_settings_deny import Base, motif_en_regex  # noqa: E402

# Les 34 lecteurs : les 9 de base, puis les 25 autres (même liste que le catalogue des équipes, R-81).
LECTEURS_BASE = ("cat", "head", "tail", "less", "more", "grep", "awk", "sed", "cp")
LECTEURS_ETENDUS = ("rg", "bat", "nl", "tac", "rev", "strings", "xxd", "od", "hexdump", "cut", "sort", "uniq", "diff", "cmp", "base64",
                    "view", "vi", "vim", "nano", "rsync", "ditto", "tar", "zip", "ln", "mv")
LECTEURS = LECTEURS_BASE + LECTEURS_ETENDUS
LISTAGES = ("ls", "/bin/ls", "eza", "find", "tree")

FORMES = ("Flux-Lab/{f}", "./Flux-Lab/{f}", "/Users/quelquun/PMZilla-Lab/workspace/Flux-Lab/{f}",
          "~/PMZilla-Lab/workspace/Flux-Lab/{f}", "$HOME/PMZilla-Lab/workspace/Flux-Lab/{f}", "{f}", "/tmp/copie/{f}")

TMP = "equipes-jira.tmp"
READ_TMP = [f"Read(./Flux-Lab/{TMP})", f"Read(//**/Flux-Lab/{TMP})", f"Read(~/**/Flux-Lab/{TMP})"]
VOLET1 = READ_TMP + [f"Bash({r} *{TMP}*)" for r in LECTEURS]

ARCHIVE = "archives-equipes"
READ_ARCHIVE = [f"Read(~/PMZilla-Lab/{ARCHIVE}/**)", f"Read(//**/PMZilla-Lab/{ARCHIVE}/**)", f"Read(**/{ARCHIVE}/**)"]
VOLET2 = (READ_ARCHIVE + [f"Bash({r} *{ARCHIVE}*)" for r in LECTEURS] + [f"Bash({r} *{ARCHIVE}*)" for r in LISTAGES])

VOLET3_A_RETIRER = [f"{outil}({chemin})" for outil in ("Write", "NotebookEdit")
                    for chemin in ("~/PMZilla-Lab/run/**", "//**/PMZilla-Lab/run/**", "**/PMZilla-Lab/run/**")]
EDIT_RUN = [f"Edit({chemin})" for chemin in ("~/PMZilla-Lab/run/**", "//**/PMZilla-Lab/run/**", "**/PMZilla-Lab/run/**")]

# Chemins d'exemple (fictifs) : fichier du dossier d'archive, dossier lui-même.
ARCHIVES_CHEMINS = (f"~/PMZilla-Lab/{ARCHIVE}/2026-10-18/table.yaml", f"~/PMZilla-Lab/{ARCHIVE}", f"$HOME/PMZilla-Lab/{ARCHIVE}/x",
                    f"/Users/quelquun/PMZilla-Lab/{ARCHIVE}/2026-10-18/table.yaml", f"{ARCHIVE}/x", f"../{ARCHIVE}/x")

COMMANDES_PERMISES = (
    f"git grep {TMP} -- docs/", f"git grep -n {TMP} -- tools/export_jira_api_equipes.py", f"git grep {ARCHIVE} -- docs/",
    f"git log --oneline -3 -- docs/ # {ARCHIVE}", "rg migrate-teams openspec/", "grep -n migrate-teams tools/export_jira_api_equipes.py",
    "cat tools/export_jira_api_equipes.py", "/bin/ls ~/PMZilla-Lab/etapes", "/bin/ls tests/settings_deny", "ls tests/composants",
    "find tests -name '*.py'", "tree -L 1 tests", "eza tests", "head -n 40 README.md", "bat README.md", "mv /tmp/a.txt /tmp/b.txt",
    "uv run --with pyyaml python -W ignore -m unittest discover -s tests/settings_deny -q -f", "bash tests/run_all.sh settings_deny",
)


def commandes_tmp():
    for lecteur, forme in itertools.product(LECTEURS, FORMES):
        yield f"{lecteur} {forme.format(f=TMP)}"
        yield f"{lecteur} -x {forme.format(f=TMP)}"


def commandes_archive():
    for lecteur, chemin in itertools.product(LECTEURS + LISTAGES, ARCHIVES_CHEMINS):
        yield f"{lecteur} {chemin}"
        yield f"{lecteur} -la {chemin}"
    yield f"find ~/PMZilla-Lab/{ARCHIVE} -type f"


class Verifications:
    """Cas communs : `deny` (liste de règles) et `interdite` viennent de la classe qui les mélange."""

    def verifier_volet1(self):
        manquantes = [c for c in commandes_tmp() if not self.interdite(c)]
        self.assertEqual(manquantes[:5], [], f"{len(manquantes)} lecture(s) de {TMP} non interdite(s)")
        for regle in READ_TMP:
            self.assertIn(regle, self.deny)

    def verifier_volet2(self):
        manquantes = [c for c in commandes_archive() if not self.interdite(c)]
        self.assertEqual(manquantes[:5], [], f"{len(manquantes)} accès au dossier d'archive non interdit(s)")
        for regle in READ_ARCHIVE:
            self.assertIn(regle, self.deny)

    def verifier_permises(self):
        interdites = [c for c in COMMANDES_PERMISES if self.interdite(c)]
        self.assertEqual(interdites, [], "commande(s) permise(s) interdite(s)")


class ReglesProposees(Verifications, unittest.TestCase):
    """Les listes VOLET1 et VOLET2 seules, avec le moteur de Base : toujours verte."""

    @classmethod
    def setUpClass(cls):
        cls.deny = VOLET1 + VOLET2
        cls.motifs = [motif_en_regex(r[len("Bash("):-1]) for r in cls.deny if r.startswith("Bash(")]

    def interdite(self, commande):
        return any(m.fullmatch(commande) for m in self.motifs)

    def test_comptes(self):
        self.assertEqual((len(VOLET1), len(VOLET2)), (37, 42))
        self.assertEqual((len(LECTEURS), len(LISTAGES), len(READ_TMP), len(READ_ARCHIVE)), (34, 5, 3, 3))
        self.assertEqual(len(VOLET1 + VOLET2), len(set(VOLET1 + VOLET2)))
        self.assertEqual(len(VOLET3_A_RETIRER), 6)

    def test_fichier_temporaire_du_catalogue(self):
        self.verifier_volet1()

    def test_dossier_d_archive(self):
        self.verifier_volet2()

    def test_les_motifs_actuels_du_catalogue_ne_couvraient_pas_le_temporaire(self):
        """Pourquoi le volet 1 existe : `*equipes-jira.yaml*` ne reconnaît pas `equipes-jira.tmp`."""
        ancien = motif_en_regex("*equipes-jira.yaml*")
        self.assertIsNone(ancien.fullmatch(f"cat Flux-Lab/{TMP}"))
        self.assertIsNotNone(ancien.fullmatch("cat Flux-Lab/equipes-jira.yaml.tmp"))

    def test_les_noms_cites_sans_lecteur_restent_permis(self):
        self.verifier_permises()


class DansLeFichierDeReglages(Verifications, Base):
    """L'auteur pose (volets 1 et 2) et retire (volet 3). Sauté avant, échoue si partiel, passe si tout y est."""

    def etat(self, voulues):
        return [r for r in voulues if r in self.deny], [r for r in voulues if r not in self.deny]

    def exiger(self, voulues, nom):
        presentes, manquantes = self.etat(voulues)
        if not presentes:
            self.fail(f"R-84 {nom} : l'auteur n'a pas encore posé les règles (r84-poser-regles.sh)")
        if manquantes:
            self.fail(f"{len(manquantes)} règle(s) absente(s) de .claude/settings.json : " + " ; ".join(manquantes[:5]))

    def test_volet1_les_regles_sont_dans_settings_json(self):
        self.exiger(VOLET1, "volet 1")

    def test_volet1_toute_lecture_du_temporaire_est_interdite(self):
        self.exiger(VOLET1, "volet 1")
        self.verifier_volet1()

    def test_volet2_les_regles_sont_dans_settings_json(self):
        self.exiger(VOLET2, "volet 2")

    def test_volet2_tout_acces_au_dossier_d_archive_est_interdit(self):
        self.exiger(VOLET2, "volet 2")
        self.verifier_volet2()

    def test_volet2_une_regle_par_lecteur_et_par_listage(self):
        self.exiger(VOLET2, "volet 2")
        for r in LECTEURS + LISTAGES:
            self.assertIn(f"Bash({r} *{ARCHIVE}*)", self.deny)

    def test_volet3_les_six_regles_write_et_notebookedit_sont_retirees(self):
        presentes, _ = self.etat(VOLET3_A_RETIRER)
        if len(presentes) == len(VOLET3_A_RETIRER):
            self.fail("R-84 volet 3 : l'auteur n'a pas encore retiré les six règles Write et NotebookEdit du dossier d'exécution")
        self.assertEqual(presentes, [], "règle(s) Write/NotebookEdit du dossier d'exécution encore présente(s)")

    def test_volet3_aucune_regle_write_ou_notebookedit_ne_reapparait(self):
        presentes, _ = self.etat(VOLET3_A_RETIRER)
        if len(presentes) == len(VOLET3_A_RETIRER):
            self.fail("R-84 volet 3 : les six règles ne sont pas encore retirées")
        autres = [d for d in self.deny if d.startswith(("Write(", "NotebookEdit("))]
        self.assertEqual(autres, [], "une règle Write(chemin) ou NotebookEdit(chemin) ne protège pas : Claude Code l'ignore ; utiliser Edit(chemin)")

    def test_garde_complementaire_le_dossier_d_execution_a_ses_trois_regles_edit(self):
        """Vaut avant comme après le retrait : la protection du dossier d'exécution tient par Edit(...)."""
        for regle in EDIT_RUN:
            self.assertIn(regle, self.deny)

    def test_garde_complementaire_toute_regle_write_ou_notebookedit_a_son_edit(self):
        for d in self.deny:
            for outil in ("Write(", "NotebookEdit("):
                if d.startswith(outil):
                    self.assertIn("Edit(" + d[len(outil):], self.deny, d)

    def test_les_noms_cites_sans_lecteur_restent_permis_avec_les_vrais_reglages(self):
        self.verifier_permises()


if __name__ == "__main__":
    unittest.main()
