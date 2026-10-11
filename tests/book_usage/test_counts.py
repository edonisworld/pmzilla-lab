"""Unités de compte par livre et formules « hors bibliothèque » : tâche 2.4."""
import unittest

from fixtures_book_usage import ARTICLE_FILES, Base, Transcript, hit, simple_turn, SENT_AFTER


class Counts(Base):
    def one(self, transcript):
        self.put(transcript)
        self.collect()
        records = self.records()
        self.assertEqual(len(records), 1, records)
        return records[0]

    def test_lu_et_cite(self):
        t = Transcript()
        t.user()
        t.search([hit("flux-et-valeur.md", 1), hit("flux-et-valeur.md", 2), hit("flux-et-valeur.md", 3)])
        t.read("flux-et-valeur.md")
        t.say("[Posture: Delivery]\nSelon Flux et valeur, section X.")
        book = self.one(t)["books"]["flux-et-valeur.md"]
        self.assertEqual(book, {"returned": 3, "read": 1, "cited": 1})

    def test_nomme_sans_usage(self):
        t = simple_turn(Transcript(), "[Posture: Delivery]\nVoir aussi Ateliers vivants.", files=("flux-et-valeur.md",))
        books = self.one(t)["books"]
        self.assertNotIn("ateliers-vivants.md", books)
        self.assertEqual(books["flux-et-valeur.md"]["cited"], 0)

    def test_renvoye_sans_etre_cite(self):
        t = simple_turn(Transcript(), "[Posture: Delivery]\nRien de cité.", files=("flux-et-valeur.md",))
        self.assertEqual(self.one(t)["books"]["flux-et-valeur.md"], {"returned": 1, "read": 0, "cited": 0})

    def test_accents_casse_et_sous_titre(self):
        t = simple_turn(Transcript(), "[Posture: Delivery]\nVoir FLUX ET VALEUR et DECOUVRIR LE BESOIN, et equipes en reseau.",
                        files=("flux-et-valeur.md", "decouvrir-le-besoin.md", "equipes-reseau.md"))
        books = self.one(t)["books"]
        self.assertEqual({f: b["cited"] for f, b in books.items()},
                         {"flux-et-valeur.md": 1, "decouvrir-le-besoin.md": 1, "equipes-reseau.md": 1})

    def test_une_citation_par_tour(self):
        t = simple_turn(Transcript(), "[Posture: Delivery]\nFlux et valeur ici, Flux et valeur là, Flux et valeur encore.")
        self.assertEqual(self.one(t)["books"]["flux-et-valeur.md"]["cited"], 1)

    def test_lecture_seule_sans_recherche(self):
        t = Transcript()
        t.user()
        t.read("ateliers-vivants.md")
        t.say("[Posture: Facilitation]\nAteliers vivants dit autre chose.")
        self.assertEqual(self.one(t)["books"]["ateliers-vivants.md"], {"returned": 0, "read": 1, "cited": 1})

    def test_resultat_en_un_seul_tableau_json(self):
        t = Transcript()
        t.user()
        t.search([hit("flux-et-valeur.md"), hit("flux-et-valeur.md")], as_array=True)
        t.say("[Posture: Delivery]\nTexte.")
        self.assertEqual(self.one(t)["books"]["flux-et-valeur.md"]["returned"], 2)

    def test_erreur_de_la_bibliotheque_ignoree(self):
        t = Transcript()
        t.user()
        t.search({"error": "Unknown collections"})
        t.say("[Posture: Delivery]\nTexte.")
        self.assertEqual(self.one(t)["books"], {})

    def test_figures_comptees_comme_passages_renvoyes(self):
        t = Transcript()
        t.user()
        t.search([hit("flux-et-valeur.md", kind="figure"), hit("flux-et-valeur.md")])
        t.say("[Posture: Delivery]\nTexte.")
        self.assertEqual(self.one(t)["books"]["flux-et-valeur.md"]["returned"], 2)

    def test_articles_ecartes(self):
        t = Transcript()
        t.user()
        t.search([hit("flux-et-valeur.md"), hit("billet-veille.md"), hit("billet-perso.md")])
        t.read("billet-veille.md")
        t.read("billet-perso.md", article=True)
        t.say("[Posture: Delivery]\nFlux et valeur, Billet de la veille, Billet personnel.")
        record = self.one(t)
        self.assertEqual(list(record["books"]), ["flux-et-valeur.md"])
        brut = self.ledger.read_text(encoding="utf-8")
        for f in ARTICLE_FILES:
            self.assertNotIn(f, brut)
        for titre in ("Billet de la veille", "Billet personnel"):
            self.assertNotIn(titre, brut)

    def test_article_lu_seul_reconnu_par_son_url(self):
        t = Transcript()
        t.user()
        t.read("billet-veille.md", article=True)
        t.say("[Posture: Delivery]\nBillet de la veille.")
        self.assertEqual(self.one(t)["books"], {})

    def test_formules_hors_bibliotheque_deux_langues(self):
        fr = simple_turn(Transcript("s-fr"), f"[Posture : Scaling]\nhors bibliothèque {SENT_AFTER}, puis hors bibliothèque encore.")
        en = simple_turn(Transcript("s-en"), f"[Posture: Scaling]\nThis is outside the library {SENT_AFTER}.")
        self.put(fr, "fr.jsonl")
        self.put(en, "en.jsonl")
        self.collect()
        records = self.records()
        self.assertEqual(sorted(r["outside_library"] for r in records), [1, 2])
        self.assertNotIn(SENT_AFTER, self.ledger.read_text(encoding="utf-8"))

    def test_formule_absente(self):
        t = simple_turn(Transcript(), "[Posture: Scaling]\nTout est dans la bibliothèque.")
        self.assertEqual(self.one(t)["outside_library"], 0)


if __name__ == "__main__":
    unittest.main()
