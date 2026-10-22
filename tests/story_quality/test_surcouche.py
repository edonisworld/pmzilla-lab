"""
Tests de la surcouche de l'organisation de la grille de qualité des stories (change story-quality-audit, tâches 2.9 et 2.10 ; spec
story-quality-grid). Suite : tests/story_quality. À lancer avec `--with jsonschema` (la suite lit le schéma par cette bibliothèque) :

    uv run --with pyyaml --with jsonschema python -m unittest discover -s tests/story_quality -q -f
"""
import json
import unittest
from pathlib import Path

import jsonschema
import yaml

from aide_story_quality import (DISTINCTIFS, EXEMPLE, IDENTIFIANT_FICTIF, IDENTIFIANT_SURCOUCHE, NOM_FICTIF, RAISON, RESUME, SCHEMA, SOCLE,
                                SURCOUCHE, Espace, so, sq)
import lab_paths  # noqa: E402
import story_quality_data as data  # noqa: E402  (TOOLS est ajouté au chemin par l'aide)


class Chemin(Espace):
    def test_lue_dans_le_sous_dossier_regles_du_dossier_de_contexte(self):
        self.ecrire()
        code, sortie, erreur = self.lancer("grid")
        self.assertEqual((code, erreur), (0, ""))
        self.assertIn("2 critères ajoutés", sortie)
        self.assertEqual(so.overlay_path(self.environ), self.contexte / "regles" / "surcouche-qualite-stories.yaml")

    # Le test « sans variable, pas de surcouche » est remplacé : il figeait le défaut corrigé par R-59 (design D16 de organisation-context :
    # sans variable, le dossier de contexte est `contexte` du dossier du lab, résolu par lab_paths.context_folder).
    def environ_sans_variable(self):
        """Faux dossier du lab : le dossier de contenu est un sous-dossier du dossier temporaire ; aucune variable de contexte."""
        contenu = self.contexte.parent / "contenu"
        contenu.mkdir()
        environ = {k: v for k, v in self.environ.items() if k != so.CONTEXT_VARIABLE}
        environ["PMZILLA_LAB_WORKSPACE"] = str(contenu)
        return environ

    def test_sans_variable_le_chemin_vient_du_resolveur_partage(self):
        environ = self.environ_sans_variable()
        attendu = lab_paths.context_folder(Path(environ["PMZILLA_LAB_WORKSPACE"]).resolve(), environ) / "regles" / so.OVERLAY_FILE
        self.assertEqual(so.overlay_path(environ), attendu)
        self.assertEqual(attendu, self.contexte.resolve() / "regles" / so.OVERLAY_FILE)

    def test_sans_variable_la_surcouche_du_dossier_du_lab_est_lue(self):
        self.ecrire()
        code, sortie, _ = self.lancer("grid", environ=self.environ_sans_variable())
        self.assertEqual(code, 0)
        self.assertIn("2 critères ajoutés", sortie)

    def test_la_variable_l_emporte_sur_le_resolveur(self):
        ailleurs = self.contexte.parent / "ailleurs"
        environ = {**self.environ_sans_variable(), so.CONTEXT_VARIABLE: str(ailleurs)}
        self.assertEqual(so.overlay_path(environ), ailleurs / "regles" / so.OVERLAY_FILE)

    def test_sans_variable_ni_dossier_de_contenu_pas_de_surcouche(self):
        environ = {"PMZILLA_LAB_WORKSPACE": str(self.contexte.parent / "absent")}
        self.assertIsNone(so.overlay_path(environ))

    def test_un_bloc_story_quality_qui_nomme_un_chemin_est_refuse(self):
        self.ecrire(SURCOUCHE + "story_quality:\n  overlay: /tmp/autre.yaml\n")
        code, sortie, erreur = self.lancer("grid")
        self.assertEqual(code, 3)
        self.assertIn("surcouche de l'organisation invalide : story_quality", erreur)
        self.assertNotIn("/tmp/autre.yaml", sortie + erreur)


class Schema(Espace):
    def test_le_schema_est_un_schema_valide_et_l_exemple_le_respecte(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(yaml.safe_load(EXEMPLE.read_text(encoding="utf-8")), schema)

    def test_exemple_ajoute_une_story_et_une_epic_porte_un_resume_et_aucun_nom_fictif(self):
        texte = EXEMPLE.read_text(encoding="utf-8")
        exemple = so.check_overlay(texte, data.core_codes(SOCLE), [NOM_FICTIF], [IDENTIFIANT_FICTIF])
        self.assertGreaterEqual(len(exemple["criteria"]["story"]), 1)
        self.assertGreaterEqual(len(exemple["criteria"]["epic"]), 1)
        self.assertTrue(exemple["product_context_summary"].strip())
        self.assertNotIn(NOM_FICTIF.lower(), texte.lower())

    def test_l_exemple_passe_par_grid(self):
        self.fichier.write_text(EXEMPLE.read_text(encoding="utf-8"), encoding="utf-8")
        code, sortie, erreur = self.lancer("grid", "--language", "en")
        self.assertEqual((code, erreur), (0, ""))
        self.assertIn("grid valid: core 3, overlay 1, 2 criteria added, 0 disabled", sortie)

    def refuse(self, texte, chemin, code_attendu=3):
        self.ecrire(texte)
        code, sortie, erreur = self.lancer("grid", "--language", "en")
        self.assertEqual(code, code_attendu, sortie + erreur)
        self.assertIn(f"organisation overlay invalid: {chemin}", erreur)
        for chaine in DISTINCTIFS + ("zzvaleur",):
            self.assertNotIn(chaine, sortie + erreur)

    def test_cles_hors_de_l_ensemble_ferme(self):
        for cle in ("masking", "scrubbing", "review_gate", "cap", "retention"):
            with self.subTest(cle=cle):
                self.refuse(SURCOUCHE + f"{cle}: zzvaleur\n", cle)

    def test_cle_hors_ensemble_dans_un_critere(self):
        self.refuse(SURCOUCHE.replace("      link: ticket_template\n", "      link: ticket_template\n      verdict_codes: zzvaleur\n"),
                    "criteria.story[0].verdict_codes")

    def test_critere_du_socle_desactive_sans_raison(self):
        self.refuse(SURCOUCHE.replace(f'    reason: "{RAISON}"\n', ""), "disabled[0].reason")

    def test_critere_du_socle_desactive_avec_un_code_inconnu(self):
        self.refuse(SURCOUCHE.replace("code: story-deux", "code: inconnu-du-socle"), "disabled[0].code")

    def test_critere_du_socle_reformule_relie_ou_renomme(self):
        self.refuse(SURCOUCHE.replace("code: orga-role", "code: story-un"), "criteria.story[0].code")

    def test_code_repete_dans_la_surcouche(self):
        self.refuse(SURCOUCHE.replace("code: orga-objectif", "code: orga-role"), "criteria.epic[0].code")

    def test_lien_inconnu(self):
        self.refuse(SURCOUCHE.replace("link: discovery_workflow_step", "link: zzvaleur"), "criteria.epic[0].link")

    def test_resume_de_contexte_au_dessus_de_la_borne(self):
        self.refuse(SURCOUCHE.replace(RESUME, "x" * 1201), "product_context_summary")

    def test_resume_a_la_borne_est_accepte(self):
        self.ecrire(SURCOUCHE.replace(RESUME, "x" * 1200))
        self.assertEqual(self.lancer("grid")[0], 0)

    def test_version_qui_n_est_pas_un_entier(self):
        self.refuse(SURCOUCHE.replace("version: 2", "version: zzvaleur"), "version")

    def test_yaml_illisible_ou_cle_repetee(self):
        self.refuse("identifier: [\n", "(yaml)")
        self.refuse(SURCOUCHE + "version: 9\n", "(yaml)")


class NomsSensibles(Espace):
    def refuse_ligne(self, texte, ligne):
        self.ecrire(texte)
        code, sortie, erreur = self.lancer("grid", "--language", "en")
        self.assertEqual(code, 3)
        self.assertIn(f"organisation overlay refused: sensitive name or identifier in line {ligne}", erreur)
        for chaine in (NOM_FICTIF, NOM_FICTIF.lower(), IDENTIFIANT_FICTIF, "a@b.test") + DISTINCTIFS:
            self.assertNotIn(chaine, sortie + erreur)

    def test_nom_dans_une_definition(self):
        self.refuse_ligne(SURCOUCHE.replace("La story nomme un rôle.", f"La story de {NOM_FICTIF}."), 16)

    def test_nom_dans_l_identifiant(self):
        self.refuse_ligne(SURCOUCHE.replace(IDENTIFIANT_SURCOUCHE, "zorglub-surcouche"), 1)

    def test_nom_dans_le_resume(self):
        self.refuse_ligne(SURCOUCHE.replace(RESUME, f"{RESUME} {NOM_FICTIF}"), 3)

    def test_identifiant_personnel_dans_le_resume(self):
        self.refuse_ligne(SURCOUCHE.replace(RESUME, f"{RESUME} {IDENTIFIANT_FICTIF}"), 3)

    def test_adresse_electronique_dans_le_resume(self):
        self.refuse_ligne(SURCOUCHE.replace(RESUME, f"{RESUME} a@b.test"), 3)

    # Revue 4.1, E1 : le contrôle ligne par ligne ne voit ni un nom coupé dans un bloc YAML, ni un échappement \u… ; chaque chaîne lue
    # (valeurs et clés) est contrôlée aussi, et le refus nomme le chemin de la clé, jamais la valeur.
    def refuse_chemin(self, texte, chemin):
        self.ecrire(texte)
        code, sortie, erreur = self.lancer("grid", "--language", "en")
        self.assertEqual(code, 3, sortie + erreur)
        self.assertIn(f"organisation overlay refused: sensitive name or identifier in {chemin}", erreur)
        for chaine in ("Zorglub", "zorglub", "Quarante", "a@b.test", "exemple.test") + DISTINCTIFS:
            self.assertNotIn(chaine, sortie + erreur)

    def test_nom_coupe_dans_un_bloc_plie_ou_litteral(self):
        self.noms.write_text(f"{NOM_FICTIF}\n", encoding="utf-8")       # le mot seul n'est pas listé : aucune ligne ne correspond
        for bloc in (">", "|"):
            with self.subTest(bloc=bloc):
                self.refuse_chemin(SURCOUCHE.replace("      definition: La story nomme un rôle.\n",
                                                     f"      definition: {bloc}\n        La story de Zorglub\n        Quarante.\n"),
                                   "criteria.story[0].definition")

    def test_nom_ecrit_avec_un_echappement(self):
        self.refuse_chemin(SURCOUCHE.replace("      definition: La story nomme un rôle.\n",
                                             '      definition: "La story de \\u005Aorglub Quarante."\n'),
                           "criteria.story[0].definition")

    def test_adresse_electronique_dans_une_cle(self):
        self.refuse_chemin(SURCOUCHE.replace("    vocabulary: [Étape de découverte]\n",
                                             '    vocabulary: [Étape de découverte]\n    "zz\\u0040exemple.test": [x]\n'),
                           "structure.story.(key)")

    def test_message_par_chemin_en_francais(self):
        self.noms.write_text(f"{NOM_FICTIF}\n", encoding="utf-8")
        self.ecrire(SURCOUCHE.replace("      definition: La story nomme un rôle.\n",
                                      "      definition: >\n        La story de Zorglub\n        Quarante.\n"))
        code, sortie, erreur = self.lancer("grid", "--language", "fr")
        self.assertEqual(code, 3)
        self.assertIn("surcouche de l'organisation refusée : nom sensible ou identifiant dans criteria.story[0].definition", erreur)
        self.assertNotIn("Zorglub", sortie + erreur)

    def test_liste_des_noms_indisponible(self):
        self.ecrire()
        self.noms.unlink()
        code, _, erreur = self.lancer("grid", "--language", "en")
        self.assertEqual(code, 3)
        self.assertIn("sensitive-names list unavailable", erreur)


class GrilleEffective(Espace):
    def surcouche(self):
        return so.check_overlay(SURCOUCHE, data.core_codes(SOCLE), [NOM_FICTIF], [IDENTIFIANT_FICTIF])

    def test_socle_non_desactive_puis_criteres_de_la_surcouche_avec_la_marque(self):
        for langue, marque in (("en", "organisation rule"), ("fr", "règle de l'organisation")):
            with self.subTest(langue=langue):
                story = data.effective_criteria(SOCLE, self.surcouche(), "story", langue)
                self.assertEqual([c["code"] for c in story], ["story-un", "story-trois", "orga-role"])
                self.assertEqual([c["origin"] for c in story], ["core", "core", "organisation_rule"])
                self.assertEqual(story[0]["source"], "hors bibliothèque")
                self.assertEqual(story[2]["source"], marque)
                epic = data.effective_criteria(SOCLE, self.surcouche(), "epic", langue)
                self.assertEqual([c["code"] for c in epic], ["epic-un", "epic-deux", "orga-objectif"])

    def test_sans_surcouche_le_socle_seul(self):
        self.assertEqual([c["code"] for c in data.effective_criteria(SOCLE, None, "story")], ["story-un", "story-deux", "story-trois"])
        self.assertEqual(data.disabled_codes(None), [])


class Sorties(Espace):
    def test_sans_surcouche_socle_seul_et_phrase(self):
        for langue, phrase, valide in (("en", "no organisation overlay: core grid only", "grid valid: core 3, overlay none, 0 criteria added, 0 disabled"),
                                       ("fr", "pas de surcouche de l'organisation : socle seul", "grille valide : socle 3, surcouche aucune, 0 critères ajoutés, 0 désactivés")):
            with self.subTest(langue=langue):
                code, sortie, erreur = self.lancer("grid", "--language", langue)
                self.assertEqual((code, erreur), (0, ""))
                self.assertIn(phrase, sortie)
                self.assertIn(valide, sortie)

    def test_grid_n_ecrit_que_versions_et_effectifs(self):
        self.ecrire()
        code, sortie, erreur = self.lancer("grid", "--language", "en")
        self.assertEqual((code, erreur), (0, ""))
        self.assertEqual(sortie.strip(), "grid valid: core 3, overlay 2, 2 criteria added, 1 disabled")
        for chaine in DISTINCTIFS + ("orga-role", "Named role", "story-un"):
            self.assertNotIn(chaine, sortie)

    def test_show_en_tete_criteres_effectifs_et_structure(self):
        self.ecrire()
        code, sortie, erreur = self.lancer("grid", "--show", "--language", "en")
        self.assertEqual((code, erreur), (0, ""))
        self.assertTrue(sortie.startswith("Effective grid: core 3, overlay 2; criteria only, never the disabling reasons\n"), sortie)
        self.assertIn("- orga-role | Named role | link: ticket_template | source: organisation rule", sortie)
        self.assertIn("- story-un | Label story-un | link: ticket_template | source: hors bibliothèque", sortie)
        self.assertIn("not applicable: Sans objet pour une story technique", sortie)
        self.assertNotIn("story-deux", sortie)                       # désactivé
        self.assertIn("structure, sections: Contexte; Besoin", sortie)
        self.assertIn("structure, Definition of Ready: Rôle nommé", sortie)
        self.assertIn("structure, vocabulary: Étape de découverte", sortie)
        self.assertIn("structure, sections: Problème; Mesure", sortie)

    def test_show_n_ecrit_ni_raison_ni_identifiant_ni_resume(self):
        self.ecrire()
        for langue in ("en", "fr"):
            _, sortie, erreur = self.lancer("grid", "--show", "--language", langue)
            for chaine in DISTINCTIFS:
                self.assertNotIn(chaine, sortie + erreur)

    def test_show_en_francais_et_marque_francaise(self):
        self.ecrire()
        _, sortie, _ = self.lancer("grid", "--show", "--language", "fr")
        self.assertTrue(sortie.startswith("Grille effective : socle 3, surcouche 2 ;"), sortie)
        self.assertIn("source : règle de l'organisation", sortie)

    def test_show_sans_surcouche_socle_seul_avec_la_phrase(self):
        code, sortie, _ = self.lancer("grid", "--show", "--language", "en")
        self.assertEqual(code, 0)
        self.assertIn("no organisation overlay: core grid only", sortie)
        self.assertNotIn("organisation rule", sortie)
        for code_critere in ("story-un", "story-deux", "story-trois", "epic-un", "epic-deux"):
            self.assertIn(code_critere, sortie)

    def test_socle_absent_ou_invalide(self):
        self.socle.unlink()
        self.assertEqual(self.lancer("grid", "--language", "en")[0::2], (3, "core grid missing\n"))
        self.socle.write_text(json.dumps({**SOCLE, "story": [{**SOCLE["story"][0], "source": ""}]}), encoding="utf-8")
        self.assertEqual(self.lancer("grid", "--language", "en")[0::2], (3, "core grid invalid\n"))

    def test_usage(self):
        for argv in ((), ("inconnue",), ("grid", "--language", "de"), ("grid", "--zz")):
            with self.subTest(argv=argv):
                self.assertEqual(self.lancer(*argv)[0], 2)


class Catalogues(unittest.TestCase):
    def test_catalogues_coherents(self):
        from messages import check_catalogs
        from story_quality_messages import CATALOGS
        self.assertEqual(check_catalogs(CATALOGS), [])

    def test_le_script_porte_jsonschema_et_son_verrou(self):
        """Le script déclare jsonschema et le verrou tools/story_quality.py.lock existe (ce test le nomme : un verrou modifié
        sélectionne cette suite au lancement ciblé)."""
        script = Path(sq.__file__)
        self.assertIn('"jsonschema"', script.read_text(encoding="utf-8")[:300])
        self.assertTrue(script.with_name("story_quality.py.lock").is_file())


if __name__ == "__main__":
    unittest.main()
