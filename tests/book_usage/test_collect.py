"""tools/book_usage.py collect : tâche 2.2 (transcriptions synthétiques, horloge injectée, aucune vraie transcription)."""
import os
import unittest

from fixtures_book_usage import Base, Transcript, simple_turn, BOOKS


def two_turns(session="sess-a"):
    t = Transcript(session)
    simple_turn(t, "[Posture: Delivery]\nPremière réponse sur Flux et valeur.")
    simple_turn(t, "[Posture: Delivery]\nDeuxième réponse sur Flux et valeur.")
    return t


class Collect(Base):
    def test_nouveaux_tours(self):
        self.put(two_turns())
        code, out = self.collect()
        self.assertEqual(code, 0, out)
        self.assertIn("Transcriptions lues : 1, tours ajoutés : 2, déjà comptés : 0, illisibles : 0", out)
        self.assertEqual(len(self.records()), 2)

    def test_relecture_idempotente(self):
        self.put(two_turns())
        self.collect()
        avant = self.ledger.read_text(encoding="utf-8")
        code, out = self.collect()
        self.assertEqual(code, 0)
        self.assertIn("tours ajoutés : 0, déjà comptés : 2", out)
        self.assertEqual(self.ledger.read_text(encoding="utf-8"), avant)

    def test_ajout_sans_reecriture(self):
        t = Transcript("sess-a")
        simple_turn(t, "[Posture: Delivery]\nUn.")
        self.put(t)
        self.collect()
        avant = self.ledger.read_text(encoding="utf-8")
        simple_turn(t, "[Posture: Delivery]\nDeux.")
        self.put(t)
        self.collect()
        apres = self.ledger.read_text(encoding="utf-8")
        self.assertTrue(apres.startswith(avant))
        self.assertEqual(len(self.records()), 2)

    def test_tour_sans_reponse_finale_collecte_plus_tard(self):
        t = Transcript("sess-a")
        simple_turn(t, "[Posture: Delivery]\nTerminé.")
        t.user("suite")
        t.search([])
        self.put(t)
        code, out = self.collect()
        self.assertIn("tours ajoutés : 1", out)
        t.say("[Posture: Delivery]\nFinie maintenant.")
        self.put(t)
        code, out = self.collect()
        self.assertIn("tours ajoutés : 1, déjà comptés : 1", out)

    def test_transcription_modifiee_dans_le_delai(self):
        self.put(two_turns(), age=5)
        code, out = self.collect()
        self.assertEqual(code, 0)
        self.assertIn("tours ajoutés : 0", out)
        self.assertFalse(self.ledger.exists() and self.records())

    def test_delai_configurable(self):
        self.put(two_turns(), age=5)
        code, out = self.run_tool("collect", "--delay", "1")
        self.assertIn("tours ajoutés : 2", out)

    def test_copies_du_jeu_d_essai_non_lues(self):
        self.put(two_turns("sess-a"))
        self.put(two_turns("sess-b"), folder=self.other)
        code, out = self.collect()
        self.assertIn("Transcriptions lues : 1, tours ajoutés : 2", out)

    def test_fichier_et_ligne_illisibles(self):
        t = two_turns()
        t.raw("{ceci n'est pas du JSON")
        t.raw(["pas", "un", "objet"])
        self.put(t)
        (self.projects / "binaire.jsonl").write_bytes(b"\xff\xfe\x00\xd8 pas de l'utf-8\n")
        os.utime(self.projects / "binaire.jsonl", (self.NOW - 86400, self.NOW - 86400))
        code, out = self.collect()
        self.assertEqual(code, 0, out)
        self.assertIn("tours ajoutés : 2", out)
        self.assertIn("illisibles : 3", out)

    def test_dossier_introuvable(self):
        code, out = self.collect()
        self.assertEqual(code, 2)
        self.assertIn("Dossier des transcriptions introuvable", out)
        self.assertFalse(self.ledger.exists())

    def test_sessions_distinctes_pas_de_collision(self):
        self.put(two_turns("sess-a"), "a.jsonl")
        self.put(two_turns("sess-b"), "b.jsonl")
        self.collect()
        self.assertEqual(len({r["turn"] for r in self.records()}), 4)

    def test_sous_dossier_du_projet_lu(self):
        t = Transcript("sess-a")
        simple_turn(t, "[Posture: Delivery]\nUn.")
        self.put(t, "sess-a/subagents/agent-1.jsonl")
        code, out = self.collect()
        self.assertIn("Transcriptions lues : 1", out)

    def test_registre_illisible(self):
        self.put(two_turns())
        self.ledger.parent.mkdir(parents=True)
        self.ledger.write_text("pas du json\n", encoding="utf-8")
        code, out = self.collect()
        self.assertEqual(code, 2)
        self.assertRegex(out, r"Registre illisible \(\w+\)")
        self.assertNotIn("pas du json", out)

    def test_aide_et_option_inconnue(self):
        code, out = self.run_tool("collect", "--help")
        self.assertEqual(code, 0)
        code, out = self.run_tool("collect", "--inconnue")
        self.assertEqual(code, 1)
        code, out = self.run_tool("--help")
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
