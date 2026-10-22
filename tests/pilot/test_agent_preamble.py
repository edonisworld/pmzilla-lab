"""Préambule des agents (change multi-session-piloting, design D9 et D12, tâche 4.3) : docs/pmzilla/agent-preamble.md porte la commande du
gel, la règle de commit par genre d'agent, les trois règles de D12, et aucun chemin absolu, dossier personnel ni nom d'utilisateur.
Écrit avant le document.

    python3 -W ignore -m unittest discover -s tests/pilot -q
"""
import getpass
import re
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
PREAMBULE = RACINE / "docs" / "pmzilla" / "agent-preamble.md"


def lignes_minuscules():
    return [l.lower() for l in PREAMBULE.read_text(encoding="utf-8").splitlines()]


class Preambule(unittest.TestCase):
    def test_existe_et_commande_du_gel(self):
        self.assertTrue(PREAMBULE.is_file(), PREAMBULE)
        self.assertIn("uv run tools/pilot.py freeze --wait 60", PREAMBULE.read_text(encoding="utf-8"))

    def test_regle_de_commit_par_genre_d_agent(self):
        lignes = lignes_minuscules()

        def regle(genre):
            trouvees = [l for l in lignes if genre in l and "commit" in l]
            self.assertTrue(trouvees, f"aucune règle de commit pour : {genre}")
            return " ".join(trouvees)

        implementation = regle("implementation agent")
        self.assertNotIn("never commit", implementation)
        self.assertIn("own branch", implementation)
        self.assertIn("freeze", implementation)
        self.assertIn("never commit", regle("framing agent"))
        self.assertIn("orchestrating session", regle("framing agent"))
        self.assertIn("never commit", regle("review agent"))
        self.assertIn("never commit", regle("search agent"))

    def test_aucun_agent_ne_termine_ne_fusionne_ne_pousse(self):
        texte = " ".join(lignes_minuscules())
        for mot in ("finishing script", "merge", "push", "remove a worktree"):
            self.assertIn(mot, texte, mot)

    def test_regle_d12_pas_de_tube_vers_python3_ou_grep(self):
        trouvees = [l for l in lignes_minuscules() if "pipe" in l and "python3" in l and "grep" in l]
        self.assertTrue(trouvees, "règle sur les commandes envoyées par tube dans python3 ou grep absente")
        self.assertTrue(any("never" in l for l in trouvees))

    def test_deny_rules_tube_vers_tail_et_exception_du_lanceur_de_tests(self):
        """Change deny-rules-review (D4, Q3 option B) : le tube vers tail est interdit sauf juste après le lanceur ciblé ou unittest."""
        trouvees = [l for l in lignes_minuscules() if "pipe" in l and "python3" in l and "grep" in l and "tail" in l]
        self.assertTrue(trouvees, "règle de tube vers python3, grep ou tail absente")
        ligne = trouvees[0]
        self.assertIn("never", ligne)
        for morceau in ("exception", "tests/run_all.sh", "unittest"):
            self.assertIn(morceau, ligne, morceau)

    def test_deny_rules_ligne_des_regles_deny_declarees(self):
        """Change deny-rules-review (D4) : un change qui touche des règles deny les déclare par --json, la garde partagée passe."""
        trouvees = [l for l in lignes_minuscules() if "deny rules" in l and "--json" in l]
        self.assertTrue(trouvees, "ligne sur les règles deny déclarées absente")
        ligne = trouvees[0]
        for morceau in ("write(path)", "notebookedit(path)", "edit(path)", "guard", "empty permission key", "duplicate"):
            self.assertIn(morceau, ligne, morceau)

    def test_regle_d12_edit_pour_toute_modification(self):
        trouvees = [l for l in lignes_minuscules() if "edit" in l and "sed -i" in l and "redirection" in l]
        self.assertTrue(trouvees, "règle sur l'outil Edit, sed -i et les redirections absente")
        ligne = trouvees[0]
        self.assertIn("write", ligne)
        self.assertIn("never", ligne)
        for forme in ("tee", "heredoc"):
            self.assertIn(forme, ligne, forme)

    def test_regle_d12_seulement_les_commandes_permises(self):
        trouvees = [l for l in lignes_minuscules() if "only the commands" in l and "read-only" in l]
        self.assertTrue(trouvees, "règle sur les commandes permises, recherches en lecture seule comprises, absente")

    def test_autres_regles_permanentes(self):
        texte = " ".join(lignes_minuscules())
        for morceau in ("permission refusal", "exact message", "content folders", "no person, team or project name"):
            self.assertIn(morceau, texte, morceau)

    def test_aucun_chemin_absolu_ni_dossier_personnel_ni_utilisateur(self):
        texte = PREAMBULE.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"(?<![\w.:])/(Users|home|private|tmp|var|etc|opt)/", texte))
        self.assertIsNone(re.search(r"(?<![\w.])~/", texte))
        self.assertNotIn("$HOME", texte)
        self.assertNotIn("${HOME}", texte)
        for nom in {getpass.getuser(), Path.home().name}:
            if len(nom) >= 3:
                self.assertNotIn(nom.lower(), texte.lower(), "nom d'utilisateur")

    def test_ecrit_en_anglais_sans_emoji(self):
        texte = PREAMBULE.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"[\U0001F300-\U0001FAFF☀-➿]", texte))
        self.assertIsNone(re.search(r"[éèàùç]", texte), "préambule en anglais")


if __name__ == "__main__":
    unittest.main()
