"""
Tests du socle de la grille d'audit et de son jumeau (change story-quality-audit, tâche 2.2 ; design D6 ; spec story-quality-grid :
« A versioned core grid », « Each criterion is fully described », « Every core criterion is sourced in the library or marked outside it »).
Suite : tests/story_quality. Ils lisent le VRAI socle suivi (tools/story_quality_grid.json et docs/pmzilla/grille-qualite-stories.md) :
ils ne touchent ni base, ni Jira, ni clé, ni surcouche.
"""
import json
import re
import unittest
from pathlib import Path

from aide_story_quality import IDENTIFIANT_FICTIF, NOM_FICTIF, TOOLS, so
import story_quality_data as data  # noqa: E402  (TOOLS est ajouté au chemin par l'aide)
import sensitive_names  # noqa: E402

RACINE = TOOLS.parent
JUMEAU = TOOLS / "story_quality_grid.json"
DOCUMENT = RACINE / "docs" / "pmzilla" / "grille-qualite-stories.md"
# Le socle et son document citent les livres de la bibliothèque : le manifeste les exclut de l'édition, comme tools/build_edition.py.
SOCLE_HORS_EDITION = not (TOOLS / "build_edition.py").is_file() and not JUMEAU.is_file()
RAISON_EDITION = "socle de la grille absent : arbre de l'édition (il cite les livres)"

CODES_STORY = ["story-valeur", "story-role", "story-independante", "story-negociable", "story-estimable", "story-petite",
               "story-tranche-verticale", "story-criteres-presents", "story-criteres-testables", "story-exemples-concrets"]
CODES_EPIC = ["epic-probleme", "epic-resultat", "epic-mesure", "epic-decoupee"]  # quatre critères : epic-hypothese-unique retiré du socle (validation du 2026-10-18)
CHAMPS_CRITERE = {"code", "label_fr", "label_en", "definition", "engine_question", "not_applicable_condition", "link", "source"}

HORS_BIBLIOTHEQUE = "hors bibliothèque"
TRANSPOSITION = "transposition par analogie, non portée par l'auteur"

# Livres dont un passage a été relu avec read_passage pour la tâche 2.1 (auteur et titre tels que le catalogue les renvoie). Une source
# du socle qui cite un autre ouvrage est une source non lue.
OUVRAGES_LUS = {
    "Mike Cohn, User Stories Applied",
    "Mike Cohn, Agile Estimating and Planning",
    "Robert C. Martin, Clean Agile: Back to Basics",
    "Stacia Viscardi, The Professional ScrumMaster's Handbook",
    "James Shore, The Art of Agile Development",
    "Jeff Patton, User Story Mapping",
    "Gáspár Nagy, Seb Rose, BDD Books: Discovery",
    "Darren Wilmshurst, Lindy Quick, SAFe Coaches Handbook",
    "OCTO Technology, Culture Scaling Kaizen",
    "Evgeny Tkachenko, Hyper-Agile Testing",
    "Em Campbell-Pretty, Adrienne Wilson, The ART of Avoiding a Train Wreck: Practical Tips and Tricks for Launching and Operating "
    "SAFe Agile Release Trains",
    "Jeff Gothelf, Josh Seiden, Lean UX: Applying Lean Principles to Improve User Experience",
    "Teresa Torres, Continuous Discovery Habits",
    "Tristan Charvillat, Rémi Guyot, Discovery Discipline : la méthode radicale pour exceller en Product Discovery",
}
REFERENCE = re.compile(r"\*([^*]+)\*, ")
CITATION = re.compile(r"“([^”]*)”")
CLE_JIRA = re.compile(r"\b[A-Z][A-Z0-9]{1,9}-\d{1,6}\b")
ADRESSE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
MOTS_PAR_CITATION = 30


def lire_jumeau():
    return json.loads(JUMEAU.read_text(encoding="utf-8"))


def criteres(grille):
    return [c for genre in data.KINDS for c in grille[genre]]


def sections_du_document():
    """{code: texte de sa section} du document lisible, et l'ordre des codes par genre."""
    texte = DOCUMENT.read_text(encoding="utf-8")
    par_code, ordre, genre = {}, {"story": [], "epic": []}, None
    courant = None
    for ligne in texte.splitlines():
        if ligne.startswith("## Stories"):
            genre, courant = "story", None
        elif ligne.startswith("## Epics"):
            genre, courant = "epic", None
        elif ligne.startswith("## "):
            genre, courant = None, None
        trouve = re.match(r"### `([a-z0-9-]+)`", ligne)
        if trouve and genre:
            courant = trouve.group(1)
            par_code[courant] = []
            ordre[genre].append(courant)
        elif courant:
            par_code[courant].append(ligne)
    return {code: "\n".join(lignes) for code, lignes in par_code.items()}, ordre, texte


@unittest.skipIf(SOCLE_HORS_EDITION, RAISON_EDITION)
class Socle(unittest.TestCase):
    def setUp(self):
        self.grille = lire_jumeau()

    def test_le_jumeau_est_lu_par_l_outil(self):
        grille = data.load_core_grid(JUMEAU)
        self.assertEqual(data.core_codes(grille), set(CODES_STORY + CODES_EPIC))

    def test_identifiant_version_et_deux_listes(self):
        self.assertEqual(set(self.grille), {"identifier", "version", "story", "epic"})
        self.assertIsInstance(self.grille["identifier"], str)
        self.assertTrue(self.grille["identifier"].strip())
        self.assertIs(type(self.grille["version"]), int)
        self.assertGreaterEqual(self.grille["version"], 1)
        self.assertGreaterEqual(len(self.grille["story"]), 1)
        self.assertGreaterEqual(len(self.grille["epic"]), 1)

    def test_codes_stables_et_ordre(self):
        self.assertEqual([c["code"] for c in self.grille["story"]], CODES_STORY)
        self.assertEqual([c["code"] for c in self.grille["epic"]], CODES_EPIC)

    def test_chaque_critere_est_decrit_en_entier(self):
        for critere in criteres(self.grille):
            with self.subTest(code=critere["code"]):
                self.assertEqual(set(critere), CHAMPS_CRITERE)
                for champ in ("code", "label_fr", "label_en", "definition", "engine_question", "source"):
                    self.assertIsInstance(critere[champ], str)
                    self.assertTrue(critere[champ].strip(), champ)
                self.assertRegex(critere["code"], r"^(story|epic)-[a-z0-9-]+$")
                self.assertIn(critere["link"], data.LINKS)
                condition = critere["not_applicable_condition"]
                self.assertTrue(condition is None or (isinstance(condition, str) and condition.strip()))
                self.assertTrue(critere["engine_question"].rstrip().endswith("?"))

    def test_les_codes_commencent_par_leur_genre(self):
        for genre in data.KINDS:
            for critere in self.grille[genre]:
                self.assertTrue(critere["code"].startswith(genre + "-"), critere["code"])

    def test_les_quatre_maillons_sont_tous_utilises(self):
        self.assertEqual({c["link"] for c in criteres(self.grille)}, set(data.LINKS))

    def test_la_source_est_une_reference_lue_ou_la_formule_hors_bibliotheque(self):
        for critere in criteres(self.grille):
            source = critere["source"]
            with self.subTest(code=critere["code"]):
                if HORS_BIBLIOTHEQUE in source:
                    self.assertTrue(source.startswith(HORS_BIBLIOTHEQUE), "la formule ouvre la ligne")
                    continue
                references = REFERENCE.findall(source)
                self.assertTrue(references, "ni référence *Auteur, Titre*, ni formule hors bibliothèque")
                for reference in references:
                    self.assertIn(reference, OUVRAGES_LUS, "ouvrage non relu pour la tâche 2.1")

    def test_une_transposition_porte_la_formule_complete(self):
        for critere in criteres(self.grille):
            if "transposition" in critere["source"]:
                self.assertIn(TRANSPOSITION, critere["source"], critere["code"])

    def test_la_premiere_reference_d_une_source_est_toujours_suivie_d_une_section(self):
        for critere in criteres(self.grille):
            for morceau in REFERENCE.split(critere["source"])[2::2]:
                self.assertRegex(morceau.strip(), r"^\S", critere["code"])
                self.assertGreater(len(morceau.strip()), 8, critere["code"])

    def test_aucun_extrait_long_dans_les_sources(self):
        for critere in criteres(self.grille):
            for citation in CITATION.findall(critere["source"]):
                self.assertLessEqual(len(citation.split()), MOTS_PAR_CITATION, critere["code"])
            self.assertLessEqual(len(critere["source"]), 900, critere["code"])

    def test_aucune_cle_adresse_nom_ni_identifiant_dans_le_jumeau_et_le_document(self):
        textes = {"jumeau": JUMEAU.read_text(encoding="utf-8"), "document": DOCUMENT.read_text(encoding="utf-8")}
        noms = [NOM_FICTIF]
        try:
            noms += sensitive_names.load_names()
        except sensitive_names.SensitiveNamesUnavailable:
            pass  # liste réelle absente de ce poste : la liste fictive et les motifs de clés et d'adresses restent contrôlés
        for nom, texte in textes.items():
            with self.subTest(fichier=nom):
                self.assertIsNone(CLE_JIRA.search(texte))
                self.assertIsNone(ADRESSE.search(texte))
                self.assertIsNone(so.line_with_sensitive_content(texte, noms, [IDENTIFIANT_FICTIF]))

    def test_le_controle_de_noms_repere_une_entree_sans_l_imprimer(self):
        ligne = so.line_with_sensitive_content("une ligne\nun critère qui cite " + NOM_FICTIF, [NOM_FICTIF], [])
        self.assertEqual(ligne, 2)


@unittest.skipIf(SOCLE_HORS_EDITION, RAISON_EDITION)
class Document(unittest.TestCase):
    def setUp(self):
        self.grille = lire_jumeau()
        self.sections, self.ordre, self.texte = sections_du_document()

    def test_memes_codes_dans_le_meme_ordre_pour_la_meme_version(self):
        self.assertEqual(self.ordre["story"], [c["code"] for c in self.grille["story"]])
        self.assertEqual(self.ordre["epic"], [c["code"] for c in self.grille["epic"]])
        self.assertIn(f"Identifiant : `{self.grille['identifier']}`", self.texte)
        self.assertRegex(self.texte, rf"(?m)^Version : {self.grille['version']}$")

    def test_chaque_section_porte_les_champs_du_jumeau(self):
        for critere in criteres(self.grille):
            section = self.sections[critere["code"]]
            with self.subTest(code=critere["code"]):
                for champ in ("label_fr", "label_en", "definition", "engine_question", "source"):
                    self.assertIn(critere[champ], section, champ)
                self.assertIn(f"`{critere['link']}`", section)
                condition = critere["not_applicable_condition"]
                self.assertIn(condition if condition else "Aucune", section)

    def test_le_document_donne_le_sens_des_verdicts_et_les_limites(self):
        for titre in ("## Limites de la démarche", "## Hors bibliothèque", "## Verdicts"):
            self.assertIn(titre, self.texte)
        for code in ("met", "not_met", "not_applicable", "undetermined"):
            self.assertIn(f"`{code}`", self.texte)

    def test_aucune_image_ni_figure_copiee(self):
        self.assertNotIn("![", self.texte)
        self.assertNotIn("Bibliotheque-Images", self.texte)


if __name__ == "__main__":
    unittest.main()
