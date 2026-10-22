"""Enveloppe {"result": [...]} du résultat de search_library, relevée sur de vraies transcriptions le 2026-10-17 (R-52)."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import book_usage_transcripts  # noqa: E402
from fixtures_book_usage import Base, Transcript, hit, SENT_QUERY


def envelope_turn(payload, as_string):
    """Un tour dont la recherche renvoie `payload` : texte JSON en chaîne, ou liste d'un bloc text."""
    t = Transcript()
    t.user()
    identifier = t.call("mcp__pmzilla-library__search_library", {"query": SENT_QUERY})
    text = json.dumps(payload)
    content = text if as_string else [{"type": "text", "text": text}]
    t._add("user", [{"type": "tool_result", "tool_use_id": identifier, "content": content}])
    return t


class Enveloppe(Base):
    def books(self, transcript):
        self.put(transcript)
        self.collect()
        records = self.records()
        self.assertEqual(len(records), 1, records)
        return records[0]["books"]

    def check_returned_and_cited(self, as_string):
        t = envelope_turn({"result": [hit("flux-et-valeur.md", 1), hit("flux-et-valeur.md", 2), hit("ateliers-vivants.md", 3)]}, as_string)
        t.say("[Posture: Delivery]\nSelon Flux et valeur, section X.")
        books = self.books(t)
        self.assertEqual(books["flux-et-valeur.md"], {"returned": 2, "read": 0, "cited": 1})
        self.assertEqual(books["ateliers-vivants.md"], {"returned": 1, "read": 0, "cited": 0})

    def test_enveloppe_en_chaine(self):
        self.check_returned_and_cited(True)

    def test_enveloppe_en_liste_d_un_bloc_text(self):
        self.check_returned_and_cited(False)

    def test_objet_a_plusieurs_cles_reste_un_objet(self):
        value = json.dumps({"book": "x", "file": "flux-et-valeur.md", "result": [{"file": "ateliers-vivants.md"}], "passages": []})
        found = book_usage_transcripts._objects(value)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["file"], "flux-et-valeur.md")

    def test_result_qui_n_est_pas_une_liste_reste_un_objet(self):
        found = book_usage_transcripts._objects(json.dumps({"result": "texte"}))
        self.assertEqual(found, [{"result": "texte"}])

    def test_erreur_ne_donne_aucun_livre(self):
        t = envelope_turn({"error": "library unavailable"}, True)
        t.say("[Posture: Delivery]\nSelon Flux et valeur, section X.")
        self.assertEqual(self.books(t), {})


if __name__ == "__main__":
    unittest.main()
