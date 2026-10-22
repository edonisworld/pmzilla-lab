"""Règles `deny` pour `tools/db_rehearsal.sh` (change flow-rebuild-rehearsal, tâche 4.2, design D11 ; l'ajout est la tâche 8.0).

Le script démarre, inspecte et retire la copie de la base de la répétition (`up`, `status`, `down`). Comme `db_backup.sh` et
`db_restore_test.sh`, seul l'auteur le lance : la session ne le lance sous aucune forme (lanceur, chemin ou sous-commande). Une commande qui
ne fait que citer son nom (grep de la documentation, cat, git log, lanceur de tests) reste permise.

Ce fichier est écrit AVANT l'ajout de l'auteur : REGLES_ATTENDUES est la liste exacte des neuf règles prévues (étape r86-regle-deny, posée par
l'auteur dans .claude/settings.json). Tant qu'aucune n'y figure, les cas contre les vrais réglages sont SAUTÉS ; si l'ajout est partiel, ils
échouent en nommant les règles manquantes ; une fois toutes présentes, ils vérifient chaque forme contre la vraie liste. La classe
ReglesProposees évalue les mêmes cas, avec le même moteur, sur REGLES_ATTENDUES seule : elle est toujours verte. Les formes permises sont
vérifiées contre les vrais réglages dans tous les cas. Aucune commande n'est lancée ; le test ne lit que .claude/settings.json.
"""
import itertools
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_settings_deny import Base, motif_en_regex  # noqa: E402

REGLES_ATTENDUES = [
    "Bash(bash *tools/db_rehearsal.sh*)",
    "Bash(sh *tools/db_rehearsal.sh*)",
    "Bash(zsh *tools/db_rehearsal.sh*)",
    "Bash(uv run *tools/db_rehearsal.sh*)",
    "Bash(tools/db_rehearsal.sh*)",
    "Bash(./tools/db_rehearsal.sh*)",
    "Bash(~/*tools/db_rehearsal.sh*)",
    "Bash($HOME/*tools/db_rehearsal.sh*)",
    "Bash(/*tools/db_rehearsal.sh*)",
]

SCRIPT = "db_rehearsal.sh"
LANCEURS = ("bash", "sh", "zsh", "uv run", "uv run bash", "uv run -q bash")
CHEMINS = ("tools/{s}", "./tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}", "$HOME/PMZilla-Lab/workspace/tools/{s}",
           "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}")
CHEMINS_DIRECTS = CHEMINS
SOUS_COMMANDES = ("up", "up --port 50000", "status", "down", "")

COMMANDES_PERMISES = (
    "bash tests/run_all.sh db_rehearsal", "bash tests/run_all.sh db_scripts", "bash tests/run_all.sh --staged",
    "bash tests/db_scripts/test_db_rehearsal.sh", "bash tests/db_scripts/test_db_scripts.sh",
    "sh -n tests/db_scripts/test_db_scripts.sh", "zsh tools/install_links.sh --verify", "uv run tools/db.py --help",
    "git log --oneline -- tools/db_rehearsal.sh", "./tools/worktree.sh --help", "rg db_rehearsal docs/",
    "git grep db_rehearsal -- openspec/", "grep -n up tools/db_rehearsal.sh", "grep -rn db_rehearsal docs/ openspec/",
    "cat tools/db_rehearsal.sh", "head -n 40 tools/db_rehearsal.sh", "sed -n 1,20p tools/db_rehearsal.sh",
    "git diff -- tools/db_rehearsal.sh", "ls tests/db_scripts",
)


def commandes_du_script():
    for lanceur, chemin, sous in itertools.product(LANCEURS, CHEMINS, SOUS_COMMANDES):
        yield f"{lanceur} {chemin.format(s=SCRIPT)} {sous}".strip()
    for chemin, sous in itertools.product(CHEMINS_DIRECTS, SOUS_COMMANDES):
        yield f"{chemin.format(s=SCRIPT)} {sous}".strip()


class Verifications:
    """Cas communs : `interdite` vient du moteur de la classe qui les mélange."""

    def verifier_formes_interdites(self):
        manquantes = [c for c in commandes_du_script() if not self.interdite(c)]
        self.assertEqual(manquantes[:5], [], f"{len(manquantes)} forme(s) de lancement de db_rehearsal.sh non interdite(s)")

    def verifier_formes_permises(self):
        interdites = [c for c in COMMANDES_PERMISES if self.interdite(c)]
        self.assertEqual(interdites, [], "commande(s) permise(s) interdite(s) : la règle est trop large")


class ReglesProposees(Verifications, unittest.TestCase):
    """REGLES_ATTENDUES seule, avec le moteur de Base : toujours verte."""

    @classmethod
    def setUpClass(cls):
        cls.motifs = [motif_en_regex(r[len("Bash("):-1]) for r in REGLES_ATTENDUES]

    def interdite(self, commande):
        return any(m.fullmatch(commande) for m in self.motifs)

    def test_toute_forme_de_lancement_est_interdite(self):
        self.verifier_formes_interdites()

    def test_citer_le_nom_du_script_reste_permis(self):
        self.verifier_formes_permises()

    def test_il_y_a_neuf_regles_sans_doublon(self):
        self.assertEqual(len(REGLES_ATTENDUES), 9)
        self.assertEqual(len(REGLES_ATTENDUES), len(set(REGLES_ATTENDUES)))


class DansLeFichierDeReglages(Verifications, Base):
    """Tâche 8.0 : l'auteur ajoute les règles. Sauté avant, échoue si l'ajout est partiel, passe si tout y est."""

    def presentes(self):
        return [r for r in REGLES_ATTENDUES if r in self.deny], [r for r in REGLES_ATTENDUES if r not in self.deny]

    def test_les_regles_sont_dans_settings_json(self):
        presentes, manquantes = self.presentes()
        if not presentes:
            self.fail("tâche 8.0 : l'auteur n'a pas encore ajouté les règles de db_rehearsal.sh")
        self.assertEqual(manquantes, [], f"{len(manquantes)} règle(s) de REGLES_ATTENDUES absente(s) de .claude/settings.json")

    def test_toute_forme_de_lancement_est_interdite_par_les_regles_reelles(self):
        presentes, manquantes = self.presentes()
        if not presentes:
            self.fail("tâche 8.0 : l'auteur n'a pas encore ajouté les règles de db_rehearsal.sh")
        if manquantes:
            self.fail("règles manquantes : " + " ; ".join(manquantes))
        self.verifier_formes_interdites()

    def test_citer_le_nom_du_script_est_permis_dans_tous_les_cas(self):
        self.verifier_formes_permises()


if __name__ == "__main__":
    unittest.main()
