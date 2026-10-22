"""Règles `deny` du verrou de fin de branche (change multi-session-piloting, design D10, tâche 8.1).

La session ne crée, ne retire ni ne déplace le verrou (le dossier `pmzilla-fin-en-cours` du dossier Git commun) : sans règle, une session pressée
pourrait retirer le verrou d'une fin en cours et lever le gel des tests. Cinq règles à ajouter par l'auteur à `permissions.deny` de
.claude/settings.json (tâche 8.2) : `rm`, `rmdir`, `mv`, `mkdir` et `touch` sur toute commande qui contient le nom du verrou, quels que soient
les options, le chemin (relatif, absolu, `~/`, `$HOME/`, entre guillemets, calculé par `git rev-parse`) et le lanceur de la commande.
L'outil de pilotage reste permis : `status`, `freeze` et `note`.

Ce fichier est écrit AVANT l'ajout de l'auteur : REGLES_R75 est la liste exacte des règles à fusionner dans permissions.deny (voir
`python3 tests/settings_deny/test_settings_deny_finish_lock.py --regles` pour les imprimer, une par ligne). Même mécanisme que
test_settings_deny_run_worktree.py : tant qu'aucune n'y figure, les cas contre les vrais réglages sont SAUTÉS (la suite reste verte) ; si l'ajout
est partiel ils échouent en nommant les règles manquantes ; une fois toutes présentes ils vérifient chaque forme contre la vraie liste. La classe
ReglesProposees évalue les mêmes cas sur les règles actuelles complétées de REGLES_R75 : elle est toujours verte. Les formes permises sont aussi
vérifiées contre les vrais réglages dans tous les cas.
Limites : une règle ne voit pas `cd … && rm …` en une seule commande, ni `bash -c '…'`, ni `find … -delete` ; la session n'en écrit jamais.
Aucune commande n'est lancée ; le test ne lit que .claude/settings.json.
"""
import itertools
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_settings_deny import RACINE, motif_en_regex  # noqa: E402

REGLAGES = RACINE / ".claude" / "settings.json"
NOM = "pmzilla-fin-en-cours"
COMMANDES_PROTEGEES = ("rm", "rmdir", "mv", "mkdir", "touch")
REGLES_R75 = [f"Bash({c} *{NOM}*)" for c in COMMANDES_PROTEGEES]

CHEMINS = (
    f".git/{NOM}", f"./.git/{NOM}", f"../espace/.git/{NOM}", f".git/{NOM}/jeton", f"{NOM}",
    f"~/PMZilla-Lab/workspace/.git/{NOM}", f"$HOME/PMZilla-Lab/workspace/.git/{NOM}", f"/Users/quelquun/PMZilla-Lab/workspace/.git/{NOM}",
    f'"$HOME/PMZilla-Lab/workspace/.git/{NOM}"', f"'/Users/quelquun/PMZilla-Lab/workspace/.git/{NOM}/pid'",
    f"$(git rev-parse --git-common-dir)/{NOM}", f'"$(git rev-parse --path-format=absolute --git-common-dir)/{NOM}"',
    f"/Users/quelquun/PMZilla-Lab/wt-feat-x/../workspace/.git/{NOM}/debut",
)
OPTIONS = {
    "rm": ("", "-f", "-r", "-rf", "-fr", "-R", "-r -f", "-v", "--"),
    "rmdir": ("", "-p"),
    "mv": ("", "-f", "-n", "-v"),
    "mkdir": ("", "-p", "-m 755"),
    "touch": ("", "-a", "-t 202601010000"),
}

COMMANDES_PERMISES = (
    "uv run tools/pilot.py status", "uv run tools/pilot.py --language en status", "uv run tools/pilot.py freeze --check",
    "uv run tools/pilot.py freeze --wait 60", "uv run tools/pilot.py note chore/spec-r12 'en attente de revue'",
    "uv run tools/pilot.py note chore/spec-r12 --clear", "uv run tools/pilot.py --language en freeze --check",
    "python3 tools/pilot.py status", "bash tests/run_all.sh pilot", "bash tests/run_all.sh --staged",
    "python3 -W ignore -m unittest discover -s tests/pilot -q",
    "python3 -W ignore -m unittest discover -s tests/settings_deny -p test_settings_deny_finish_lock.py -q",
    "cat tools/pilot.py", "head -n 40 tools/finish_lock.sh", "grep -n lock tools/finish_branch.sh", "wc -l tools/finish_lock.py",
    "git status", "git log --oneline -3", "git worktree list",
    "ls .git", "ls ~/PMZilla-Lab", "cat docs/pmzilla/agent-preamble.md",
    "rm /tmp/fichier-sans-rapport.txt", "rm -rf tests/pilot/__pycache__", "rmdir dossier-vide", "mv a.txt b.txt", "mkdir -p tmp/essai",
    "touch tmp/essai/x.txt", "mkdir ../wt-feat-x", "rm tmp/pmzilla-notes-sans-rapport/x",
)
# Un fichier « pmzilla-… » sans rapport avec le verrou reste effaçable, mais hors de .git : toute écriture dans .git est refusée
# depuis team-names-readable D12 (#398) ; l'ancienne forme « rm .git/pmzilla-notes-sans-rapport/x » est un cas refusé de
# tests/settings_deny/test_settings_deny_git_dir.py.


class Verifications:
    """Évalue les cas contre `self.regles` (liste de règles de permissions.deny). Mêlé à un cas de test."""

    regles = ()

    def commande_interdite(self, commande):
        if getattr(self, "_cache_regles", None) is not self.regles:
            self._cache_regles = self.regles
            self._motifs = [motif_en_regex(r[len("Bash("):-1]) for r in self.regles if r.startswith("Bash(")]
        return any(m.fullmatch(commande) for m in self._motifs)

    def verifier_formes_interdites(self):
        for commande, chemin in itertools.product(COMMANDES_PROTEGEES, CHEMINS):
            for option in OPTIONS[commande]:
                lancement = f"{commande} {option} {chemin}".replace("  ", " ")
                if commande == "mv":
                    lancement += " ailleurs"
                self.assertTrue(self.commande_interdite(lancement), lancement)
        # mv vers le nom du verrou : le nom est la destination
        for chemin in CHEMINS:
            c = f"mv /tmp/autre {chemin}"
            self.assertTrue(self.commande_interdite(c), c)

    def verifier_formes_permises(self):
        for commande in COMMANDES_PERMISES:
            self.assertFalse(self.commande_interdite(commande), commande)


class ReglesProposees(Verifications, unittest.TestCase):
    """Les cas, évalués sur REGLES_R75 ajoutées aux règles déjà présentes : toujours verts, ils prouvent que la liste à coller fait ce que la spec demande."""

    @classmethod
    def setUpClass(cls):
        existantes = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.regles = list(dict.fromkeys(existantes + REGLES_R75))

    def test_toutes_les_formes_sont_interdites(self):
        self.verifier_formes_interdites()

    def test_les_formes_permises_restent_permises(self):
        self.verifier_formes_permises()

    def test_pas_de_regle_en_double(self):
        self.assertEqual(len(REGLES_R75), len(set(REGLES_R75)))

    def test_exactement_une_regle_par_commande(self):
        self.assertEqual(len(REGLES_R75), len(COMMANDES_PROTEGEES))
        for c in COMMANDES_PROTEGEES:
            self.assertIn(f"Bash({c} *{NOM}*)", REGLES_R75)

    def test_la_lecture_et_l_outil_de_pilotage_n_ont_pas_de_regle(self):
        self.assertEqual([r for r in REGLES_R75 if r.startswith(("Read(", "Edit(")) or "pilot" in r], [])


class DansLeFichierDeReglages(Verifications, unittest.TestCase):
    """Tâche 8.2 : l'auteur ajoute les règles. Sauté avant, échoue si l'ajout est partiel, passe si tout y est."""

    @classmethod
    def setUpClass(cls):
        cls.deny = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.regles = cls.deny

    def exiger_les_regles(self):
        presentes = [r for r in REGLES_R75 if r in self.deny]
        manquantes = [r for r in REGLES_R75 if r not in self.deny]
        if not presentes:
            self.fail("tâche 8.2 : l'auteur n'a pas encore ajouté les règles du verrou de fin (REGLES_R75)")
        if manquantes:
            self.fail(f"{len(manquantes)} règle(s) de REGLES_R75 absente(s) de .claude/settings.json : " + " ; ".join(manquantes))

    def test_les_regles_sont_dans_settings_json(self):
        self.exiger_les_regles()

    def test_toute_forme_est_interdite_par_les_regles_reelles(self):
        self.exiger_les_regles()
        self.verifier_formes_interdites()

    def test_les_formes_permises_le_sont_avec_les_regles_reelles(self):
        self.verifier_formes_permises()

    def test_aucune_regle_ne_vise_l_outil_de_pilotage(self):
        self.assertEqual([r for r in self.deny if "pilot.py" in r], [])


if __name__ == "__main__":
    if "--regles" in sys.argv:
        print("\n".join(REGLES_R75))
    else:
        unittest.main()
