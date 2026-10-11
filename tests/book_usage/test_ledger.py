"""Registre local : champs seuls, clé à sens unique, droits du propriétaire : tâche 2.5."""
import hashlib
import json
import os
import stat
import unittest

from fixtures_book_usage import Base, Transcript, hit, SENTINELS, SESSION, SENT_AFTER, SENT_ANSWER, FAKE_PERSON, SENT_USER, simple_turn

CHAMPS = {"turn", "day", "bucket", "books", "outside_library", "version"}


def turn_chargé():
    t = Transcript()
    t.user(f"{SENT_USER} {FAKE_PERSON} bloque le projet")
    t.search([hit("flux-et-valeur.md")])
    t.read("flux-et-valeur.md")
    t.say(f"[Posture: Delivery]\n{SENT_ANSWER} {FAKE_PERSON} : Flux et valeur. hors bibliothèque {SENT_AFTER}")
    return t


class Registre(Base):
    def setUp(self):
        super().setUp()
        self.put(turn_chargé())
        self.collect()
        self.brut = self.ledger.read_text(encoding="utf-8")

    def test_sentinelles_absentes(self):
        for sentinelle in SENTINELS:
            self.assertNotIn(sentinelle, self.brut, sentinelle)

    def test_champs_seuls(self):
        record = self.records()[0]
        self.assertEqual(set(record), CHAMPS)
        self.assertEqual(record["day"], "2026-10-05")
        self.assertEqual(record["version"], 1)
        self.assertEqual(set(record["books"]["flux-et-valeur.md"]), {"returned", "read", "cited"})

    def test_pas_d_heure(self):
        self.assertNotIn("09:", self.brut)
        self.assertNotIn("T09", self.brut)

    def test_cle_a_sens_unique(self):
        cle = self.records()[0]["turn"]
        self.assertRegex(cle, r"^[0-9a-f]{64}$")
        self.assertNotEqual(cle, hashlib.sha256(SESSION.encode()).hexdigest())
        self.assertNotIn(SESSION, self.brut)

    def test_droits_du_proprietaire_seul(self):
        self.assertEqual(stat.S_IMODE(os.stat(self.ledger).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(self.ledger.parent).st_mode) & 0o077, 0)

    def test_droits_gardes_apres_un_second_ajout(self):
        t = turn_chargé()
        simple_turn(t, "[Posture: Delivery]\nAutre.")
        self.put(t)
        self.collect()
        self.assertEqual(stat.S_IMODE(os.stat(self.ledger).st_mode), 0o600)

    def test_une_ligne_json_par_enregistrement(self):
        for ligne in self.brut.splitlines():
            json.loads(ligne)

    def test_la_version_future_est_lue_avec_les_anciennes(self):
        with open(self.ledger, "a", encoding="utf-8") as f:
            f.write(json.dumps({"turn": "0" * 64, "day": "2026-10-06", "bucket": "Delivery", "books": {}, "outside_library": 0,
                                "version": 2, "extra": 1}) + "\n")
        self.put(turn_chargé())
        code, out = self.collect()
        self.assertEqual(code, 0, out)
        self.assertIn("déjà comptés : 1", out)

    def test_aucun_enregistrement_sans_livre_perdu(self):
        t = Transcript("sess-vide")
        simple_turn(t, "[Posture: Delivery]\nSans bibliothèque.", files=())
        self.put(t, "vide.jsonl")
        self.collect()
        self.assertEqual(sum(1 for r in self.records() if r["books"] == {}), 1)


if __name__ == "__main__":
    unittest.main()
