"""tools/flow_organisation.py : catalogue des équipes Jira (change team-mapping, groupe 3, tâches 3.1 à 3.5).

Lecture stricte du catalogue (clés name, jira_team_ids, type, obsolete), règles entre le référentiel et le catalogue (un identifiant
dans les deux fichiers est accepté, le nom vient du référentiel, le type et le drapeau obsolète du catalogue), clé `type` des deux
fichiers, type déduit et type effectif d'une équipe du référentiel. Données inventées, chaînes distinctives vérifiées absentes des
messages ; aucun accès à Flux-Lab/ : textes et fichiers temporaires.
"""
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flow_organisation as org  # noqa: E402
from yaml_strict import ErreurConfig  # noqa: E402

REFERENTIEL = """source_date: 2026-10-01
sites: [Zorblax-Site]
departments:
  - name: Dept-Wumpa
    site: Zorblax-Site
    headcount: 12
    mission_teams:
      - name: MT-Frobnic
        teams: [Eq-Glimmer, Eq-Snarf]
teams:
  - name: Eq-Glimmer
    headcount: 5
    jira_team_ids: ["100", "101"]
  - name: Eq-Snarf
    headcount: 3
    jira_team_ids: ["200"]
"""

CATALOGUE = """teams:
  - name: Libelle-Quimbo
    jira_team_ids: ["300", "301"]
    type: Development Team
  - name: Libelle-Plinth
    jira_team_ids: ["302"]
    type: Other Team
    obsolete: true
  - name: Libelle-Vexor
    jira_team_ids: ["100"]
    type: Verification Team
    obsolete: true
"""

DISTINCTIFS = ["Quimbo", "Plinth", "Vexor", "Glimmer", "Snarf", "Frobnic", "Wumpa", "Zorblax", '"300"', "301", "302"]


def refus_catalogue(texte: str, **options) -> str:
    with unittest.TestCase().assertRaises(ErreurConfig) as r:
        org.charger_catalogue(texte, **options)
    assert r.exception.code == str(r.exception), r.exception.code      # message affiché, code 1
    return str(r.exception)


class LectureDuCatalogue(unittest.TestCase):
    def test_structure_lue(self):
        cat = org.charger_catalogue(CATALOGUE)
        self.assertEqual([e.nom for e in cat.entrees], ["Libelle-Quimbo", "Libelle-Plinth", "Libelle-Vexor"])
        self.assertEqual(cat.entrees[0].jira_ids, ("300", "301"))
        self.assertEqual(cat.entrees[0].type, "Development Team")
        self.assertFalse(cat.entrees[0].obsolete)

    def test_drapeau_obsolete_lu_et_equipe_connue(self):
        cat = org.charger_catalogue(CATALOGUE)
        self.assertTrue(cat.entrees[1].obsolete)
        self.assertEqual(cat.entree_pour("302").nom, "Libelle-Plinth")           # connue : une entrée obsolète reste connue
        self.assertTrue(cat.est_obsolete("302"))
        self.assertFalse(cat.est_obsolete("300"))
        self.assertIsNone(cat.entree_pour("999"))

    def test_identifiant_entier_non_guillemete(self):
        cat = org.charger_catalogue("teams:\n  - name: Libelle-A\n    jira_team_ids: [12, 13]\n")
        self.assertEqual(cat.entree_pour("12").nom, "Libelle-A")

    def test_fichier_absent_lu_comme_vide(self):
        with tempfile.TemporaryDirectory() as tmp:
            cat = org.charger_catalogue_si_present(Path(tmp) / "equipes-jira.yaml")
        self.assertEqual(cat.entrees, ())
        self.assertIsNone(cat.entree_pour("1"))

    def test_fichier_present_lu(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "equipes-jira.yaml"
            chemin.write_text(CATALOGUE, encoding="utf-8")
            self.assertEqual(len(org.charger_catalogue_si_present(chemin).entrees), 3)

    def test_cle_d_effectif_refusee_avec_chemin_et_ligne_sans_valeur(self):
        message = refus_catalogue(CATALOGUE + "  - name: Libelle-Zed\n    jira_team_ids: ['400']\n    headcount: 7\n")
        self.assertIn("teams[3].headcount", message)
        self.assertIn("L15", message)
        for interdit in DISTINCTIFS + ["Libelle-Zed", "400"]:
            self.assertNotIn(interdit, message)

    def test_cle_a_confirmer_refusee_comme_cle_inconnue(self):
        message = refus_catalogue(CATALOGUE.replace("    obsolete: true\n  - name: Libelle-Vexor",
                                                    "    obsolete_to_confirm: true\n  - name: Libelle-Vexor"))
        self.assertIn("clé inconnue", message)
        self.assertIn("teams[1].obsolete_to_confirm", message)
        self.assertIn("L8", message)

    def test_cle_de_statut_refusee(self):
        self.assertIn("teams[0].status", refus_catalogue(CATALOGUE.replace("    type: Development Team", "    status: active", 1)))

    def test_cle_inconnue_a_la_racine_refusee(self):
        self.assertIn("clé inconnue", refus_catalogue(CATALOGUE + "owner: quelqu-un\n"))

    def test_nom_vide_refuse(self):
        message = refus_catalogue("teams:\n  - name: ''\n    jira_team_ids: ['1']\n")
        self.assertIn("teams[0].name", message)

    def test_nom_en_double_refuse_sans_valeur(self):
        message = refus_catalogue(CATALOGUE.replace("Libelle-Plinth", "Libelle-Quimbo"))
        self.assertIn("teams[0].name", message)
        self.assertIn("teams[1].name", message)
        self.assertNotIn("Quimbo", message)

    def test_identifiant_en_double_refuse_sans_valeur(self):
        message = refus_catalogue(CATALOGUE.replace('["302"]', '["301"]'))
        self.assertIn("teams[0].jira_team_ids", message)
        self.assertIn("teams[1].jira_team_ids", message)
        self.assertNotIn("301", message)

    def test_drapeau_obsolete_non_booleen_refuse(self):
        self.assertIn("teams[1].obsolete", refus_catalogue(CATALOGUE.replace("obsolete: true", "obsolete: oui", 1)))

    def test_yaml_illisible_refuse_sans_reprendre_le_texte(self):
        message = refus_catalogue("teams: [Libelle-Quimbo, ")
        self.assertNotIn("Quimbo", message)


class TypeDEquipe(unittest.TestCase):
    """3.4 : clé `type` facultative du catalogue et du référentiel, quatre noms exacts, jamais devinée."""

    def test_quatre_noms_acceptes_dans_le_catalogue(self):
        for nom in org.TYPES_EQUIPE:
            cat = org.charger_catalogue(f"teams:\n  - name: Libelle-A\n    jira_team_ids: ['1']\n    type: {nom}\n")
            self.assertEqual(cat.entrees[0].type, nom)
        self.assertEqual(org.TYPES_EQUIPE, ("Development Team", "Verification Team", "Product Management Team", "Other Team"))

    def test_type_absent_lu_comme_aucun_type(self):
        cat = org.charger_catalogue("teams:\n  - name: Libelle-A\n    jira_team_ids: ['1']\n")
        self.assertIsNone(cat.entrees[0].type)

    def test_type_hors_des_quatre_noms_refuse_avec_la_phrase_de_la_conception(self):
        for valeur in ("development team", "Other", "Platform Team", "''"):
            with self.subTest(valeur=valeur):
                message = refus_catalogue(f"teams:\n  - name: Libelle-A\n    jira_team_ids: ['1']\n    type: {valeur}\n")
                self.assertIn("type d'équipe autre que les quatre sous-types de Team : ", message)
                self.assertIn("teams[0].type", message)
                self.assertIn("L4", message)
                if valeur != "''":
                    self.assertNotIn(valeur, message)                              # jamais la valeur lue

    def test_phrase_en_anglais(self):
        message = refus_catalogue("teams:\n  - name: Libelle-A\n    jira_team_ids: ['1']\n    type: Nope\n", language="en")
        self.assertIn("team type other than the four Team sub-types: ", message)
        self.assertNotIn("Nope", message)

    def test_cle_type_acceptee_dans_le_referentiel(self):
        ref = org.charger(REFERENTIEL.replace('jira_team_ids: ["200"]', 'jira_team_ids: ["200"]\n    type: Other Team'))
        self.assertEqual(ref.teams["Eq-Snarf"].type, "Other Team")
        self.assertIsNone(ref.teams["Eq-Glimmer"].type)

    def test_type_du_referentiel_hors_des_quatre_noms_refuse(self):
        with self.assertRaises(ErreurConfig) as r:
            org.charger(REFERENTIEL.replace('jira_team_ids: ["200"]', 'jira_team_ids: ["200"]\n    type: Nope'))
        message = str(r.exception)
        self.assertIn("type d'équipe autre que les quatre sous-types de Team : ", message)
        self.assertIn("teams[1].type", message)
        self.assertNotIn("Nope", message)
        with self.assertRaises(ErreurConfig) as r:
            org.charger(REFERENTIEL.replace('jira_team_ids: ["200"]', 'jira_team_ids: ["200"]\n    type: Nope'), language="en")
        self.assertIn("team type other than the four Team sub-types: ", str(r.exception))


class RegleEntreLesDeuxSources(unittest.TestCase):
    """3.2 : un identifiant dans les deux fichiers est accepté ; un nom du catalogue égal à celui d'une équipe du référentiel avec un
    identifiant qu'aucune équipe du référentiel ne liste est refusé."""

    def verifier(self, catalogue: str, referentiel: str = REFERENTIEL, **options):
        return org.verifier_sources(org.charger(referentiel), org.charger_catalogue(catalogue), **options)

    def test_identifiant_partage_accepte_nom_du_referentiel_type_et_drapeau_du_catalogue(self):
        ref, cat = org.charger(REFERENTIEL), org.charger_catalogue(CATALOGUE)
        org.verifier_sources(ref, cat)                                       # « 100 » est dans les deux, libellé différent
        self.assertEqual(ref.team_for_jira_id("100"), "Eq-Glimmer")
        self.assertEqual(cat.entree_pour("100").type, "Verification Team")
        self.assertTrue(cat.est_obsolete("100"))
        self.assertEqual(org.nom_traduit("100", ref, cat), "Eq-Glimmer")      # le nom vient du référentiel
        self.assertEqual(org.nom_traduit("300", ref, cat), "Libelle-Quimbo")  # sinon le libellé du catalogue
        self.assertIsNone(org.nom_traduit("999", ref, cat))

    def test_nom_du_referentiel_avec_identifiant_hors_referentiel_refuse(self):
        catalogue = CATALOGUE.replace("Libelle-Quimbo", "Eq-Snarf")
        with self.assertRaises(ErreurConfig) as r:
            self.verifier(catalogue)
        message = str(r.exception)
        self.assertIn("équipe du catalogue nommée comme une équipe du référentiel : ", message)
        self.assertIn("teams[0].name", message)                              # catalogue
        self.assertIn("teams[1].name", message)                              # référentiel (Eq-Snarf)
        self.assertIn("L", message)
        for interdit in ("Snarf", "300", "301", "Quimbo"):
            self.assertNotIn(interdit, message)

    def test_phrase_en_anglais(self):
        with self.assertRaises(ErreurConfig) as r:
            self.verifier(CATALOGUE.replace("Libelle-Quimbo", "Eq-Snarf"), language="en")
        self.assertIn("catalogue team named like a referential team: ", str(r.exception))

    def test_meme_nom_accepte_quand_l_equipe_liste_tous_les_identifiants(self):
        catalogue = 'teams:\n  - name: Eq-Glimmer\n    jira_team_ids: ["100", "101"]\n    type: Development Team\n'
        self.verifier(catalogue)

    def test_meme_nom_avec_identifiant_liste_par_une_autre_equipe_du_referentiel_accepte(self):
        catalogue = 'teams:\n  - name: Eq-Glimmer\n    jira_team_ids: ["100", "200"]\n'
        self.verifier(catalogue)                  # « 200 » est listé par une équipe du référentiel : pas un identifiant hors référentiel

    def test_noms_differents_aucune_sortie_ni_refus(self):
        ref, cat = org.charger(REFERENTIEL), org.charger_catalogue(CATALOGUE)
        self.assertIsNone(org.verifier_sources(ref, cat))                     # ni refus ni avertissement sur un libellé différent

    def test_catalogue_vide_accepte(self):
        org.verifier_sources(org.charger(REFERENTIEL), org.charger_catalogue_si_present(Path("/nonexistent/equipes-jira.yaml")))


class CatalogueEtGroupes(unittest.TestCase):
    """3.3 : un identifiant du catalogue qu'aucune équipe du référentiel ne liste est « hors référentiel » ; le catalogue ne change
    aucun résumé de structure."""

    def setUp(self):
        self.ref = org.charger(REFERENTIEL)
        self.cat = org.charger_catalogue(CATALOGUE)

    def test_identifiant_hors_referentiel_groupe_hors_referentiel_libelle_inchange(self):
        nom = org.nom_traduit("300", self.ref, self.cat)
        self.assertEqual(self.ref.group_of(nom, "mission-team"), "hors référentiel")
        self.assertEqual(self.ref.group_of(nom, "mission-team", "en"), "outside the referential")
        self.assertEqual(org.outside_label("fr"), "hors référentiel")

    def test_identifiant_des_deux_fichiers_reste_dans_le_groupe_de_son_equipe(self):
        nom = org.nom_traduit("100", self.ref, self.cat)
        self.assertEqual(self.ref.group_of(nom, "mission-team"), "MT-Frobnic")

    def test_le_catalogue_ne_change_aucun_resume_de_structure(self):
        avant = (self.ref.structure_summary("mission-team"), self.ref.structure_summary("site"), self.ref.groups("site"))
        org.verifier_sources(self.ref, self.cat)
        self.assertEqual(avant, (self.ref.structure_summary("mission-team"), self.ref.structure_summary("site"),
                                 self.ref.groups("site")))
        self.assertEqual(sorted(self.ref.teams), ["Eq-Glimmer", "Eq-Snarf"])          # aucune entrée du catalogue parmi les équipes
        self.assertEqual(self.ref.jira_ids_count, 3)


class TypeDeduitEtEffectif(unittest.TestCase):
    """3.5 : type déduit du catalogue, type effectif = forcé, sinon déduit, sinon aucun ; le référentiel jamais écrit."""

    def cat(self, *entrees):
        lignes = ["teams:"]
        for i, (ids, type_) in enumerate(entrees):
            lignes += [f"  - name: Libelle-{i}", f"    jira_team_ids: {ids}"] + ([f"    type: {type_}"] if type_ else [])
        return org.charger_catalogue("\n".join(lignes) + "\n")

    def test_type_deduit_du_catalogue_sans_cle(self):
        ref = org.charger(REFERENTIEL)
        cat = self.cat((["100"], "Development Team"), (["101"], "Development Team"))
        self.assertEqual(org.type_deduit(ref.teams["Eq-Glimmer"], cat), "Development Team")
        self.assertEqual(org.type_effectif(ref.teams["Eq-Glimmer"], cat), "Development Team")

    def test_type_force_l_emporte_sur_un_type_different_du_catalogue(self):
        ref = org.charger(REFERENTIEL.replace('jira_team_ids: ["200"]', 'jira_team_ids: ["200"]\n    type: Other Team'))
        cat = self.cat((["200"], "Development Team"))
        self.assertEqual(org.type_deduit(ref.teams["Eq-Snarf"], cat), "Development Team")
        self.assertEqual(org.type_effectif(ref.teams["Eq-Snarf"], cat), "Other Team")

    def test_force_sans_aucun_identifiant_dans_le_catalogue(self):
        ref = org.charger(REFERENTIEL.replace('jira_team_ids: ["200"]', 'jira_team_ids: ["200"]\n    type: Other Team'))
        self.assertIsNone(org.type_deduit(ref.teams["Eq-Snarf"], self.cat()))
        self.assertEqual(org.type_effectif(ref.teams["Eq-Snarf"], self.cat()), "Other Team")

    def test_pas_de_deduction_sur_des_types_differents(self):
        ref = org.charger(REFERENTIEL)
        cat = self.cat((["100"], "Development Team"), (["101"], "Verification Team"))
        self.assertIsNone(org.type_deduit(ref.teams["Eq-Glimmer"], cat))
        self.assertIsNone(org.type_effectif(ref.teams["Eq-Glimmer"], cat))
        self.assertTrue(org.types_differents(ref.teams["Eq-Glimmer"], cat))

    def test_aucun_identifiant_dans_le_catalogue_aucun_type(self):
        ref = org.charger(REFERENTIEL)
        self.assertIsNone(org.type_effectif(ref.teams["Eq-Glimmer"], self.cat((["999"], "Other Team"))))

    def test_jamais_de_type_tire_du_nom(self):
        ref = org.charger(REFERENTIEL.replace("Eq-Snarf", "Verification Team Eq-Snarf").replace("Eq-Glimmer, Verification",
                                                                                                "Eq-Glimmer, Verification"))
        equipe = next(e for e in ref.teams.values() if "Verification" in e.nom)
        self.assertIsNone(org.type_effectif(equipe, self.cat()))

    def test_une_entree_sans_type_est_ignoree_le_type_des_autres_identifiants_est_deduit(self):
        # renommé (names-and-team-review, tâche 5.1, décision D11) : l'ancien nom disait le contraire de l'assertion
        ref = org.charger(REFERENTIEL)
        cat = self.cat((["100"], None), (["101"], "Other Team"))
        self.assertEqual(org.type_deduit(ref.teams["Eq-Glimmer"], cat), "Other Team")       # l'entrée sans type ne dit rien
        self.assertFalse(org.types_differents(ref.teams["Eq-Glimmer"], cat))

    def test_aucune_liste_assets_n_est_ouverte_et_le_referentiel_reste_intact(self):
        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "organisation.yaml"
            chemin.write_text(REFERENTIEL, encoding="utf-8")
            ouverts = []
            vrai = Path.read_text

            def espion(self, *a, **k):
                ouverts.append(self.name)
                return vrai(self, *a, **k)
            Path.read_text = espion
            try:
                ref = org.charger_fichier(chemin)
                org.type_effectif(ref.teams["Eq-Glimmer"], self.cat((["100"], "Other Team")))
            finally:
                Path.read_text = vrai
            self.assertEqual(ouverts, ["organisation.yaml"])
            self.assertEqual(chemin.read_text(encoding="utf-8"), REFERENTIEL)


if __name__ == "__main__":
    unittest.main()
