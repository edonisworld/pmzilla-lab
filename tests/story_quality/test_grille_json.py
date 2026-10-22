"""
Tests de la fonction de service `effective_grid` et de `grid --show --json` (change story-quality-audit, tâche 2.15 ; design D15 ;
spec story-quality-grid : « The effective grid is one service result, shown as text or JSON », « grid --show --json prints the
effective-grid contract »). Suite : tests/story_quality. À lancer avec `--with jsonschema`.
"""
import json
import re
import unittest
from pathlib import Path
from unittest import mock

from aide_story_quality import (DISTINCTIFS, IDENTIFIANT_FICTIF, NOM_FICTIF, SOCLE, SURCOUCHE, TOOLS, Espace, so, sq)
import story_quality_data as data  # noqa: E402  (TOOLS est ajouté au chemin par l'aide)

CLES_RACINE = {"contract", "contract_version", "core_version", "overlay_version", "kinds"}
CLES_GENRE = {"criteria", "structure"}
CLES_CRITERE = {"code", "labels", "definition", "engine_question", "not_applicable_condition", "link", "origin", "source"}
CLES_STRUCTURE = {"sections", "definition_of_ready", "vocabulary"}


def toutes_les_cles(valeur):
    if isinstance(valeur, dict):
        for cle, contenu in valeur.items():
            yield cle
            yield from toutes_les_cles(contenu)
    elif isinstance(valeur, list):
        for element in valeur:
            yield from toutes_les_cles(element)


def codes_du_texte(sortie):
    """Codes des critères listés par `grid --show`, dans l'ordre, genre par genre."""
    return re.findall(r"^- (\S+) \|", sortie, re.M)


def codes_du_json(document):
    return [c["code"] for genre in ("story", "epic") for c in document["kinds"][genre]["criteria"]]


class Fonction(Espace):
    def surcouche(self):
        return so.check_overlay(SURCOUCHE, data.core_codes(SOCLE), [NOM_FICTIF], [IDENTIFIANT_FICTIF])

    def test_contrat_avec_surcouche(self):
        grille = data.effective_grid(SOCLE, self.surcouche(), "en")
        self.assertEqual(set(grille), CLES_RACINE)
        self.assertEqual((grille["contract"], grille["contract_version"]), ("story_quality_grid", 1))
        self.assertEqual((grille["core_version"], grille["overlay_version"]), (3, 2))
        self.assertEqual(set(grille["kinds"]), {"story", "epic"})
        for genre in ("story", "epic"):
            self.assertEqual(set(grille["kinds"][genre]), CLES_GENRE)
            self.assertEqual(set(grille["kinds"][genre]["structure"]), CLES_STRUCTURE)
            for critere in grille["kinds"][genre]["criteria"]:
                self.assertEqual(set(critere), CLES_CRITERE)
                self.assertEqual(set(critere["labels"]), {"fr", "en"})
        self.assertEqual(codes_du_json(grille), ["story-un", "story-trois", "orga-role", "epic-un", "epic-deux", "orga-objectif"])
        self.assertEqual(grille["kinds"]["story"]["structure"],
                         {"sections": ["Contexte", "Besoin"], "definition_of_ready": ["Rôle nommé"], "vocabulary": ["Étape de découverte"]})
        self.assertEqual(grille["kinds"]["epic"]["structure"], {"sections": ["Problème", "Mesure"], "definition_of_ready": [], "vocabulary": []})

    def test_sans_surcouche_version_nulle_et_socle_seul(self):
        grille = data.effective_grid(SOCLE, None, "fr")
        self.assertIsNone(grille["overlay_version"])
        self.assertEqual(codes_du_json(grille), ["story-un", "story-deux", "story-trois", "epic-un", "epic-deux"])
        self.assertEqual({c["origin"] for g in grille["kinds"].values() for c in g["criteria"]}, {"core"})
        self.assertEqual(grille["kinds"]["story"]["structure"], {"sections": [], "definition_of_ready": [], "vocabulary": []})

    def test_la_marque_suit_la_langue_et_la_fonction_ne_depend_que_de_ses_arguments(self):
        for langue, marque in (("en", "organisation rule"), ("fr", "règle de l'organisation")):
            grille = data.effective_grid(SOCLE, self.surcouche(), langue)
            self.assertEqual(grille["kinds"]["story"]["criteria"][-1]["source"], marque)
        self.assertEqual(data.effective_grid(SOCLE, self.surcouche(), "en"), data.effective_grid(SOCLE, self.surcouche(), "en"))

    def test_rien_de_prive_dans_le_resultat(self):
        texte = json.dumps(data.effective_grid(SOCLE, self.surcouche(), "en"), ensure_ascii=False)
        for chaine in DISTINCTIFS:
            self.assertNotIn(chaine, texte)

    def test_le_module_ne_touche_ni_base_ni_jira_ni_cle(self):
        for nom in ("story_quality_data.py", "story_quality_overlay.py", "story_quality.py"):
            source = (TOOLS / nom).read_text(encoding="utf-8")
            # story_quality.py est le répartiteur des cinq sous-commandes (R-94) : son en-tête `# /// script` déclare les dépendances
            # de collect et review (tests/script_dependencies), chargés seulement quand ils sont lancés. Le code, lui, reste vérifié.
            source = re.sub(r"\A# /// script\n(?:#.*\n)+?# ///\n", "", source)
            for interdit in ("psycopg", "keyring", "find-generic-password", "import requests", "import httpx", "subprocess"):
                self.assertNotIn(interdit, source, f"{nom} : {interdit}")


class TexteEtJson(Espace):
    def lancer_json(self, *argv):
        return self.lancer("grid", "--show", "--json", *argv)

    def test_le_json_est_le_contrat_sur_la_sortie_standard_seule(self):
        self.ecrire()
        code, sortie, erreur = self.lancer_json("--language", "en")
        self.assertEqual((code, erreur), (0, ""))
        document = json.loads(sortie)
        self.assertEqual(set(document), CLES_RACINE)
        self.assertEqual((document["core_version"], document["overlay_version"]), (3, 2))

    def test_meme_criteres_dans_le_meme_ordre_en_texte_et_en_json(self):
        self.ecrire()
        for langue in ("en", "fr"):
            with self.subTest(langue=langue):
                _, texte, _ = self.lancer("grid", "--show", "--language", langue)
                _, brut, _ = self.lancer_json("--language", langue)
                document = json.loads(brut)
                self.assertEqual(codes_du_texte(texte), codes_du_json(document))
                self.assertEqual(codes_du_json(document), ["story-un", "story-trois", "orga-role", "epic-un", "epic-deux", "orga-objectif"])
                self.assertNotIn("story-deux", texte + brut)
                marque = {"en": "organisation rule", "fr": "règle de l'organisation"}[langue]
                self.assertEqual([c["source"] for c in document["kinds"]["story"]["criteria"]][-1], marque)
                self.assertIn(marque, texte)

    def test_le_texte_met_en_forme_le_resultat_de_la_fonction_sans_rien_construire(self):
        faux = {"contract": "story_quality_grid", "contract_version": 1, "core_version": 7, "overlay_version": None,
                "kinds": {"story": {"criteria": [{"code": "zz-code-fonction", "labels": {"fr": "zz fr", "en": "zz en"}, "definition": "zz def",
                                                  "engine_question": "zz question", "not_applicable_condition": None,
                                                  "link": "refinement", "origin": "core", "source": "zz source"}],
                                    "structure": {"sections": ["zz section"], "definition_of_ready": [], "vocabulary": []}},
                          "epic": {"criteria": [], "structure": {"sections": [], "definition_of_ready": [], "vocabulary": []}}}}
        self.ecrire()
        with mock.patch.object(data, "effective_grid", return_value=faux) as appel:
            code, texte, _ = self.lancer("grid", "--show", "--language", "en")
            code_json, brut, _ = self.lancer_json("--language", "en")
        self.assertEqual((code, code_json), (0, 0))
        self.assertEqual(appel.call_count, 2)
        self.assertEqual(json.loads(brut), faux)
        self.assertIn("- zz-code-fonction | zz en | link: refinement | source: zz source", texte)
        self.assertIn("Effective grid: core 7, overlay none;", texte)
        self.assertIn("structure, sections: zz section", texte)
        self.assertNotIn("story-un", texte)

    def test_aucune_raison_aucun_identifiant_aucun_resume_ni_cle_hors_contrat(self):
        self.ecrire()
        _, brut, erreur = self.lancer_json("--language", "en")
        for chaine in DISTINCTIFS:
            self.assertNotIn(chaine, brut + erreur)
        document = json.loads(brut)
        permises = CLES_RACINE | CLES_GENRE | CLES_CRITERE | CLES_STRUCTURE | {"fr", "en", "story", "epic"}
        self.assertEqual(set(toutes_les_cles(document)) - permises, set())
        for interdite in ("reason", "disabled", "identifier", "product_context_summary", "summary"):
            self.assertNotIn(interdite, set(toutes_les_cles(document)))

    def test_sans_surcouche_version_nulle_phrase_sur_la_sortie_d_erreur(self):
        code, sortie, erreur = self.lancer_json("--language", "en")
        self.assertEqual(code, 0)
        document = json.loads(sortie)
        self.assertIsNone(document["overlay_version"])
        self.assertEqual({c["origin"] for g in document["kinds"].values() for c in g["criteria"]}, {"core"})
        self.assertEqual(erreur.strip(), "no organisation overlay: core grid only")
        self.assertNotIn("no organisation overlay", sortie)

    def test_codes_de_sortie_inchanges(self):
        self.ecrire(SURCOUCHE + "cap: zzvaleur\n")
        code, sortie, erreur = self.lancer_json("--language", "en")
        self.assertEqual((code, sortie), (3, ""))
        self.assertIn("organisation overlay invalid: cap", erreur)
        self.ecrire(SURCOUCHE.replace("La story nomme un rôle.", f"{NOM_FICTIF}"))
        code, sortie, erreur = self.lancer_json("--language", "en")
        self.assertEqual((code, sortie), (3, ""))
        self.assertIn("organisation overlay refused", erreur)
        self.socle.unlink()
        self.assertEqual(self.lancer_json("--language", "en")[0], 3)

    def test_chaque_critere_porte_son_lien_de_chaine_statique(self):
        """2.11 (D18, O9) : le lien est un attribut statique, un des quatre codes, copié tel quel du socle ou de la surcouche."""
        self.ecrire()
        _, brut, _ = self.lancer_json("--language", "en")
        liens_attendus = {c["code"]: c["link"] for g in ("story", "epic") for c in SOCLE[g]}
        liens_attendus.update({"orga-role": "ticket_template", "orga-objectif": "discovery_workflow_step"})
        trouves = {c["code"]: c["link"] for g in json.loads(brut)["kinds"].values() for c in g["criteria"]}
        self.assertEqual(trouves, {k: v for k, v in liens_attendus.items() if k in trouves})
        self.assertTrue(set(trouves.values()) <= set(data.LINKS))
        self.assertIn("orga-role", trouves)

    def test_json_sans_show_est_une_erreur_d_usage(self):
        self.assertEqual(self.lancer("grid", "--json")[0], 2)


if __name__ == "__main__":
    unittest.main()
