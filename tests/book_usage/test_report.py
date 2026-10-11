"""Sous-commande report : sections, période, dates, période vide, listes jamais utilisées : tâches 3.2 et 3.3."""
import datetime as dt
import re
import unittest

from fixtures_book_usage import Base, Transcript, hit, simple_turn, BOOKS

SECTIONS = ["## Par livre", "## Par posture", "## Livres jamais cités", "## Livres jamais lus ni cités",
            "## Livres du domaine jamais cités, par posture", "## Lacunes par posture"]


def jour(transcript, ts_day):
    for ligne in transcript.lines:
        if isinstance(ligne, dict):
            ligne["timestamp"] = ligne["timestamp"].replace("2026-10-05", ts_day)
    return transcript


class Rapport(Base):
    def peupler(self):
        a = Transcript("sess-a")
        simple_turn(a, "[Posture: Delivery]\nSelon Flux et valeur. Aussi Ateliers vivants.", files=("flux-et-valeur.md", "ateliers-vivants.md"))
        simple_turn(a, "[Posture: Scaling]\nÉquipes en réseau. hors bibliothèque. hors bibliothèque.", files=("equipes-reseau.md",), read=("equipes-reseau.md",))
        b = Transcript("sess-b")
        simple_turn(b, "[Posture: Facilitation]\nRien.", files=("ateliers-vivants.md",))
        jour(b, "2026-10-09")
        self.put(a, "a.jsonl")
        self.put(b, "b.jsonl")
        self.collect()

    def test_sections_dans_l_ordre(self):
        self.peupler()
        code, out = self.report()
        self.assertEqual(code, 0, out)
        texte = self.report_text()
        positions = [texte.index(s) for s in SECTIONS]
        self.assertEqual(positions, sorted(positions))
        self.assertTrue(texte.startswith("# Usage des livres par les postures\n"))
        self.assertIn("Période : 2026-10-05 à 2026-10-09, 3 tours de posture", texte)
        self.assertIn("Données disponibles depuis le 2026-10-05", texte)

    def test_chemin_imprime_et_nom_du_fichier(self):
        self.peupler()
        code, out = self.report()
        aujourd_hui = dt.date.fromtimestamp(self.NOW).isoformat()
        self.assertRegex(out, r"Rapport écrit : .*_bmad-output/pmzilla/usage-livres/usage-livres-%s\.md" % aujourd_hui)
        chemin = out.split("Rapport écrit : ")[1].strip()
        self.assertTrue(chemin.startswith(str(self.workspace)))

    def test_remplacement_le_meme_jour(self):
        self.peupler()
        self.report()
        premier = self.report_text()
        self.report("--since", "2026-10-09")
        dossier = self.workspace / "_bmad-output" / "pmzilla" / "usage-livres"
        self.assertEqual(len(list(dossier.glob("*.md"))), 1)
        self.assertNotEqual(self.report_text(), premier)

    def test_autre_jour_non_remplace(self):
        self.peupler()
        dossier = self.workspace / "_bmad-output" / "pmzilla" / "usage-livres"
        dossier.mkdir(parents=True)
        ancien = dossier / "usage-livres-2026-01-01.md"
        ancien.write_text("ancien", encoding="utf-8")
        self.report()
        self.assertEqual(ancien.read_text(encoding="utf-8"), "ancien")
        self.assertEqual(len(list(dossier.glob("*.md"))), 2)

    def test_bornes_de_periode(self):
        self.peupler()
        self.report("--since", "2026-10-06", "--until", "2026-10-09")
        texte = self.report_text()
        self.assertIn("Période : 2026-10-06 à 2026-10-09, 1 tours de posture", texte)
        self.assertNotIn("| Delivery |", texte.split("## Par posture")[1].split("##")[0])

    def test_bornes_incluses(self):
        self.peupler()
        self.report("--since", "2026-10-05", "--until", "2026-10-05")
        self.assertIn("2 tours de posture", self.report_text())

    def test_dates_invalides(self):
        self.peupler()
        for valeur in ("2026-13-01", "demain", "2026-10-5", "20261005"):
            code, out = self.report("--since", valeur)
            self.assertEqual(code, 1, valeur)
            self.assertIn(f"Date invalide : {valeur}", out)
        code, out = self.report("--until", "2026-02-30")
        self.assertEqual((code, "Date invalide : 2026-02-30" in out), (1, True))
        self.assertEqual(self.report_text(), "")

    def test_debut_apres_fin(self):
        self.peupler()
        code, out = self.report("--since", "2026-10-09", "--until", "2026-10-05")
        self.assertEqual(code, 1)
        self.assertIn("Période vide : début après fin", out)
        self.assertEqual(self.report_text(), "")

    def test_periode_vide(self):
        self.peupler()
        code, out = self.report("--since", "2027-01-01")
        self.assertEqual(code, 0)
        self.assertIn("Aucun tour de posture dans la période", out + self.report_text())
        texte = self.report_text()
        jamais = texte.split("## Livres jamais cités")[1].split("##")[0]
        for _, (titre, _) in BOOKS.items():
            self.assertIn(titre, jamais)

    def test_registre_absent_donne_un_rapport_vide(self):
        code, out = self.report()
        self.assertEqual(code, 0, out)
        self.assertIn("Aucun tour de posture dans la période", self.report_text())

    def test_par_livre_trie_par_citations_puis_lectures(self):
        self.peupler()
        self.report()
        lignes = [l for l in self.report_text().split("## Par livre")[1].split("##")[0].splitlines() if l.startswith("| ") and "---" not in l][1:]
        titres = [l.split("|")[1].strip() for l in lignes]
        self.assertEqual(titres[0], "Équipes en réseau")        # 1 citation et 1 lecture
        self.assertNotIn("Livre jamais ouvert", titres)          # aucun compte : pas de ligne

    def test_jamais_cites_et_jamais_lus(self):
        self.peupler()
        self.report()
        texte = self.report_text()
        jamais_cites = texte.split("## Livres jamais cités")[1].split("##")[0]
        jamais_lus = texte.split("## Livres jamais lus ni cités")[1].split("##")[0]
        self.assertIn("Livre jamais ouvert", jamais_cites)
        self.assertIn("Découvrir le besoin", jamais_cites)
        self.assertNotIn("Flux et valeur", jamais_cites)
        self.assertIn("Découvrir le besoin", jamais_lus)

    def test_lu_mais_jamais_cite(self):
        t = Transcript()
        simple_turn(t, "[Posture: Delivery]\nTexte sans titre.", files=("flux-et-valeur.md",), read=("flux-et-valeur.md",))
        self.put(t)
        self.collect()
        self.report()
        texte = self.report_text()
        jamais_cites = texte.split("## Livres jamais cités")[1].split("##")[0]
        jamais_lus = texte.split("## Livres jamais lus ni cités")[1].split("##")[0]
        self.assertRegex(jamais_cites, r"Flux et valeur : mesurer sans trahir.*\b1\b")
        self.assertNotIn("Flux et valeur", jamais_lus)

    def test_domaine_d_une_posture(self):
        # Ateliers vivants (facilitation) cité par Delivery seulement : il reste dans les jamais cités de Facilitation
        t = simple_turn(Transcript(), "[Posture: Delivery]\nAteliers vivants.", files=("ateliers-vivants.md",))
        self.put(t)
        self.collect()
        self.report()
        texte = self.report_text()
        domaine = texte.split("## Livres du domaine jamais cités, par posture")[1].split("## Lacunes")[0]
        facilitation = domaine.split("Facilitation")[1].split("###")[0]
        self.assertIn("Ateliers vivants", facilitation)
        delivery = domaine.split("### Delivery")[1].split("###")[0]
        self.assertNotIn("Ateliers vivants", delivery)       # hors de ses domaines (flow, tech)
        self.assertIn("Livre jamais ouvert", delivery)       # tech
        self.assertIn("Flux et valeur", delivery)            # flow, jamais cité

    def test_domaine_flow_partage_scaling_et_delivery(self):
        self.peupler()
        self.report()
        domaine = self.report_text().split("## Livres du domaine jamais cités, par posture")[1].split("## Lacunes")[0]
        scaling = domaine.split("### Scaling")[1].split("###")[0]
        self.assertIn("Flux et valeur", scaling)             # flow : cité par Delivery, jamais par Scaling
        self.assertNotIn("Équipes en réseau", scaling)       # cité par Scaling

    def test_lacunes_par_posture(self):
        self.peupler()
        self.report()
        lacunes = self.report_text().split("## Lacunes par posture")[1]
        ligne = [l for l in lacunes.splitlines() if l.startswith("| Scaling")][0]
        self.assertEqual([c.strip() for c in ligne.strip("|").split("|")], ["Scaling", "1", "2"])
        ligne = [l for l in lacunes.splitlines() if l.startswith("| Delivery")][0]
        self.assertEqual([c.strip() for c in ligne.strip("|").split("|")], ["Delivery", "0", "0"])

    def test_par_posture(self):
        self.peupler()
        self.report()
        par_posture = self.report_text().split("## Par posture")[1].split("##")[0]
        ligne = [l for l in par_posture.splitlines() if l.startswith("| Delivery")][0]
        # tours, renvoyés, lus, citations, livres distincts cités, formules
        self.assertEqual([c.strip() for c in ligne.strip("|").split("|")], ["Delivery", "1", "2", "0", "2", "2", "0"])

    def test_base_injoignable(self):
        self.peupler()

        class Panne(Exception):
            pass

        def lecture():
            raise Panne("détail secret avec /chemin/prive")
        code, out = self.run_tool("report", read_books=lecture)
        self.assertEqual(code, 2)
        self.assertIn("Bibliothèque injoignable (Panne)", out)
        self.assertNotIn("secret", out)
        self.assertEqual(self.report_text(), "")

    def test_registre_illisible(self):
        self.ledger.parent.mkdir(parents=True)
        self.ledger.write_text("{pas du json\n", encoding="utf-8")
        code, out = self.report()
        self.assertEqual(code, 2)
        self.assertRegex(out, r"Registre illisible \(\w+\)")


if __name__ == "__main__":
    unittest.main()
