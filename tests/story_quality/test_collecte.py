"""
Tests de `story_quality.py collect` (change story-quality-audit, tâches 3.1 et 3.3 ; design D3, D4, D9, D14 ; spec story-quality-collect).

Faux serveur Jira local, faux jeton, faux magasin du schéma quality (aide_story_quality.py) : aucune vraie base, aucun vrai Jira, aucun
Trousseau. Le SQL du vrai magasin est essayé sur une fausse connexion (test_magasin.py) et sur la base jetable (test_magasin_base.py).
Données inventées ; les chaînes « zz » / « ZZ » sont distinctives et ne doivent jamais sortir de l'outil.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

from aide_story_quality import (CHAMP_CRITERES, CHAMP_EQUIPE, CHAMP_PERSONNE, CHAMP_PERSONNES, EQUIPE_A, EQUIPE_B, REFERENTIEL,
                                REQUETE_A, REQUETE_B, EspaceCollecte, adf, ticket)

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import flow_organisation  # noqa: E402
import story_quality_collect as collect  # noqa: E402

ATTENDUS = ["summary", "description", CHAMP_CRITERES, "issuetype", "status", CHAMP_EQUIPE, "parent", "created", "updated",
            "resolutiondate"]
INTERDITS = {"assignee", "reporter", "creator", "watches", "watchers", "votes", "comment", "attachment", "worklog", "changelog",
             CHAMP_PERSONNE, CHAMP_PERSONNES}


class ChampsDemandes(EspaceCollecte):
    def test_liste_exacte_des_champs(self):
        self.faux.ajouter(REQUETE_A, ticket("ZZA-1"))
        code, _, erreur = self.lancer("collect", "--language", "en")
        self.assertEqual(code, 0, erreur)
        recherches = self.faux.recherches()
        self.assertEqual(len(recherches), 2)                         # une recherche par requête nommée
        for corps in recherches:
            self.assertEqual(corps["fields"], ATTENDUS)

    def test_aucun_champ_de_personne_ni_a_cote_avec_tous_les_reglages(self):
        self.faux.ajouter(REQUETE_A, ticket("ZZA-1"))
        self.lancer("collect")
        for corps in self.faux.recherches():
            self.assertEqual(set(corps["fields"]) & INTERDITS, set())
            self.assertFalse(any(c.startswith("*") for c in corps["fields"]))
        self.assertNotIn("assignee", str(self.magasin.contenus) + str(self.magasin.elements))

    def test_sans_champ_d_equipe_ni_de_criteres(self):
        self.ecrire_reglages(equipe=None, bloc="""story_quality:
  queries: {alpha: "project = ZZA"}
  issue_types: {story: [Story]}
  engine: {model: m, keychain_service: s, input_price_per_token: 0, output_price_per_token: 0, cap_per_launch: 1}
""")
        self.faux.ajouter(REQUETE_A, ticket("ZZA-1"))
        code, _, erreur = self.lancer("collect")
        self.assertEqual(code, 0, erreur)
        self.assertEqual(self.faux.recherches()[0]["fields"],
                         ["summary", "description", "issuetype", "status", "parent", "created", "updated", "resolutiondate"])
        self.assertEqual(self.faux.appels[0], ("POST", "/rest/api/3/search/jql"))     # aucun champ configuré : pas de contrôle à faire

    def test_la_liste_de_la_garde_reprend_les_champs_interdits(self):
        self.assertTrue({"assignee", "reporter", "creator", "watches", "votes", "comment", "attachment", "worklog",
                         "changelog"} <= collect.CHAMPS_INTERDITS)


class ChampDePersonneRefuse(EspaceCollecte):
    def verifier_refus(self, cle, **reglages):
        self.ecrire_reglages(**reglages)
        self.faux.ajouter(REQUETE_A, ticket("ZZA-1"))
        code, sortie, erreur = self.lancer("collect", "--language", "en")
        self.assertEqual(code, 3)
        self.assertIn(f"person field refused in the story quality settings: {cle}", erreur)
        self.assertEqual(self.faux.recherches(), [])                 # aucun ticket demandé
        self.assertNotIn(("POST", "/rest/api/3/search/jql"), self.faux.appels)
        for valeur in (CHAMP_PERSONNE, CHAMP_PERSONNES, "Zz"):
            self.assertNotIn(valeur, sortie + erreur)
        self.assertEqual(self.magasin.ecritures, 0)

    def test_criteres_d_acceptation_sur_un_champ_utilisateur(self):
        self.verifier_refus("story_quality.acceptance_criteria_field", criteres=CHAMP_PERSONNE)

    def test_criteres_d_acceptation_sur_une_liste_d_utilisateurs(self):
        self.verifier_refus("story_quality.acceptance_criteria_field", criteres=CHAMP_PERSONNES)

    def test_champ_d_equipe_utilisateur(self):
        self.verifier_refus("export_team_field", equipe=CHAMP_PERSONNE)

    def test_champ_systeme_de_personne(self):
        self.verifier_refus("story_quality.acceptance_criteria_field", criteres="assignee")

    def test_en_francais(self):
        self.ecrire_reglages(criteres=CHAMP_PERSONNE)
        code, _, erreur = self.lancer("collect")
        self.assertEqual(code, 3)
        self.assertIn("champ de personne refusé dans les réglages de qualité des stories : story_quality.acceptance_criteria_field",
                      erreur)


class TypesEtReferentiel(EspaceCollecte):
    def test_seules_les_stories_et_les_epics_sont_stockees(self):
        self.faux.ajouter(REQUETE_A, ticket("ZZA-1"), ticket("ZZA-2", type_="Epic"), ticket("ZZA-3", type_="Bug"),
                          ticket("ZZA-4", type_="Sub-task"))
        code, sortie, _ = self.lancer("collect", "--language", "en")
        self.assertEqual(code, 0)
        self.assertEqual(sorted(self.magasin.elements), ["ZZA-1", "ZZA-2"])
        self.assertEqual(self.magasin.elements["ZZA-2"]["kind"], "epic")
        self.assertIn("story content collected: 2 items, 0 replacements", sortie)

    def test_le_drapeau_un_seul_po_est_copie_et_rien_d_autre(self):
        self.ecrire_referentiel()
        self.faux.ajouter(REQUETE_A, ticket("ZZA-1", equipe=EQUIPE_A), ticket("ZZA-2", equipe=EQUIPE_B))
        code, _, erreur = self.lancer("collect")
        self.assertEqual(code, 0, erreur)
        self.assertEqual(self.magasin.attributs, {EQUIPE_A: True, EQUIPE_B: False})
        stocke = str(self.magasin.elements) + str(self.magasin.contenus) + str(self.magasin.attributs)
        for valeur in ("Site Zz", "Departement Zz", "headcount"):
            self.assertNotIn(valeur, stocke)

    def test_les_equipes_et_le_parent_sont_stockes(self):
        self.faux.ajouter(REQUETE_A, ticket("ZZA-1", equipe=EQUIPE_B, parent="ZZA-9"))
        self.lancer("collect")
        self.assertEqual(self.magasin.equipes["ZZA-1"], [EQUIPE_B])
        self.assertEqual(self.magasin.elements["ZZA-1"]["parent_key"], "ZZA-9")
        self.assertEqual(self.magasin.elements["ZZA-1"]["status_category"], "indeterminate")


class ReferentielUnSeulPo(unittest.TestCase):
    def test_drapeau_facultatif_booleen(self):
        referentiel = flow_organisation.charger(REFERENTIEL)
        self.assertTrue(referentiel.teams[EQUIPE_A].single_po)
        self.assertFalse(referentiel.teams[EQUIPE_B].single_po)

    def test_drapeau_non_booleen_refuse_sans_valeur(self):
        from yaml_strict import ErreurConfig
        with self.assertRaises(ErreurConfig) as contexte:
            flow_organisation.charger(REFERENTIEL.replace("single_po: true", "single_po: zzoui"))
        self.assertIn("teams[0].single_po", str(contexte.exception))
        self.assertNotIn("zzoui", str(contexte.exception))


class Nettoyage(EspaceCollecte):
    def test_trois_mentions_comptees_jamais_montrees(self):
        self.faux.ajouter(REQUETE_A, ticket("ZZA-1", description=adf("Voir ", ("mention", "zzcompte-un"), " puis ",
                                                                      ("mention", "zzcompte-deux"), ("mention", "zzcompte-trois"))))
        code, sortie, erreur = self.lancer("collect", "--language", "en")
        self.assertEqual(code, 0, erreur)
        self.assertIn("story content collected: 1 items, 3 replacements", sortie)
        description = self.magasin.contenus["ZZA-1"][1]
        self.assertEqual(description.count("[person]"), 3)
        self.assertNotIn("zzcompte", description + sortie + erreur)
        self.assertEqual(self.magasin.contenus["ZZA-1"][4], 3)

    def test_noms_sensibles_et_adresses_dans_les_trois_textes(self):
        self.faux.ajouter(REQUETE_A, ticket("ZZA-1", titre="Écran de Zorglub", description=adf("Écrire à zz@exemple.org"),
                                            criteres="Validé par ZORGLUB QUARANTE"))
        _, sortie, _ = self.lancer("collect", "--language", "en")
        titre, description, criteres, empreinte, remplacements = self.magasin.contenus["ZZA-1"]
        self.assertEqual((titre, description, criteres), ("Écran de [name]", "Écrire à [email]", "Validé par [name]"))
        self.assertEqual(remplacements, 3)
        self.assertEqual(len(empreinte), 64)
        self.assertIn("1 items, 3 replacements", sortie)
        self.assertNotIn("Zorglub", sortie)

    def test_liste_des_noms_absente_rien_n_est_collecte(self):
        self.noms.unlink()
        self.faux.ajouter(REQUETE_A, ticket("ZZA-1"))
        code, _, erreur = self.lancer("collect", "--language", "en")
        self.assertEqual(code, 3)
        self.assertIn("sensitive-names list unavailable: nothing is collected", erreur)
        self.assertEqual(self.faux.appels, [])
        self.assertEqual(self.ouvertures, 0)


class Ecriture(EspaceCollecte):
    def test_une_seule_ecriture_par_passage(self):
        self.faux.ajouter(REQUETE_A, ticket("ZZA-1"), ticket("ZZA-2"))
        self.faux.ajouter(REQUETE_B, ticket("ZZB-1", equipe=EQUIPE_B))
        self.lancer("collect")
        self.assertEqual(self.magasin.ecritures, 1)
        self.assertFalse(self.magasin.ouvert)                        # le magasin est refermé

    def test_aucun_fichier_ecrit(self):
        self.faux.ajouter(REQUETE_A, ticket("ZZA-1", titre="zzsentinelle-titre", description=adf("zzsentinelle-description"),
                                            criteres="zzsentinelle-criteres"))
        code, _, _ = self.lancer("collect")
        self.assertEqual(code, 0)
        self.assertEqual(self.fichiers_ecrits(), [])

    def test_panne_de_la_base_rien_ne_reste_et_le_type_seul(self):
        self.magasin.echec = RuntimeError("ZZA-1 zzsecret Equipe Zzalpha")
        self.faux.ajouter(REQUETE_A, ticket("ZZA-1"))
        code, sortie, erreur = self.lancer("collect", "--language", "en")
        self.assertEqual(code, 1)
        self.assertIn("database error, nothing is written: RuntimeError", erreur)
        for valeur in ("ZZA-1", "zzsecret", "Zzalpha"):
            self.assertNotIn(valeur, sortie + erreur)
        self.assertEqual(self.magasin.elements, {})
        self.assertNotIn("story content collected", sortie)

    def test_base_injoignable(self):
        import story_quality_store as store
        from unittest import mock

        def injoignable():
            raise store.ErreurMagasin()
        with mock.patch.object(store, "ouvrir", injoignable):
            code, _, erreur = self.lancer("collect", "--language", "en")
        self.assertEqual(code, 1)
        self.assertIn("database unreachable", erreur)
        self.assertEqual(self.faux.appels, [])                       # la base est ouverte avant tout appel à Jira

    def test_une_nouvelle_collecte_remplace_le_texte(self):
        self.faux.ajouter(REQUETE_A, ticket("ZZA-1", titre="Premier"))
        self.lancer("collect")
        self.faux.par_requete[REQUETE_A] = [ticket("ZZA-1", titre="Second")]
        self.lancer("collect")
        self.assertEqual(self.magasin.contenus["ZZA-1"][0], "Second")


class Conservation(EspaceCollecte):
    def test_story_resolue_avant_la_duree_ignoree_et_comptee(self):
        self.faux.ajouter(REQUETE_A, ticket("ZZA-1", resolu_il_y_a=400), ticket("ZZA-2", resolu_il_y_a=30))
        code, sortie, _ = self.lancer("collect", "--language", "en")
        self.assertEqual(code, 0)
        self.assertEqual(list(self.magasin.elements), ["ZZA-2"])
        self.assertIn("items past retention, skipped: 1", sortie)

    def test_duree_configuree(self):
        texte = (self.flux / "flux.yaml").read_text(encoding="utf-8")
        (self.flux / "flux.yaml").write_text(texte + "retention:\n  period_days: 20\n", encoding="utf-8")
        self.faux.ajouter(REQUETE_A, ticket("ZZA-2", resolu_il_y_a=30))
        _, sortie, _ = self.lancer("collect", "--language", "en")
        self.assertIn("items past retention, skipped: 1", sortie)

    def test_marques_de_sortie_sur_un_passage_complet(self):
        self.faux.ajouter(REQUETE_A, ticket("ZZA-1"), ticket("ZZA-2"))
        self.lancer("collect")
        self.faux.par_requete[REQUETE_A] = [ticket("ZZA-1")]
        _, sortie, _ = self.lancer("collect", "--language", "en")
        self.assertIn("items out of collection: 1 marked, 0 back", sortie)
        self.assertTrue(self.magasin.elements["ZZA-2"]["out_of_collection"])
        self.faux.par_requete[REQUETE_A] = [ticket("ZZA-1"), ticket("ZZA-2")]
        _, sortie, _ = self.lancer("collect", "--language", "en")
        self.assertIn("items out of collection: 0 marked, 1 back", sortie)
        self.assertFalse(self.magasin.elements["ZZA-2"]["out_of_collection"])

    def test_une_seule_requete_ne_marque_rien(self):
        self.faux.ajouter(REQUETE_A, ticket("ZZA-1"))
        self.faux.ajouter(REQUETE_B, ticket("ZZB-1"))
        self.lancer("collect")
        code, sortie, _ = self.lancer("collect", "--query", "alpha", "--language", "en")
        self.assertEqual(code, 0)
        self.assertFalse(self.magasin.elements["ZZB-1"]["out_of_collection"])
        self.assertNotIn("items out of collection", sortie)
        self.assertEqual([c["jql"] for c in self.faux.recherches()][-1:], [REQUETE_A])

    def test_requete_inconnue(self):
        code, _, _ = self.lancer("collect", "--query", "inconnue")
        self.assertEqual(code, 2)
        self.assertEqual(self.faux.appels, [])


class SortieEtSession(EspaceCollecte):
    def test_refus_en_session_avant_toute_lecture(self):
        (self.flux / "flux.yaml").write_text("story_quality: [illisible\n", encoding="utf-8")   # prouverait une lecture
        code, sortie, erreur = self.lancer("collect", "--language", "en", environ={**self.environ, "CLAUDECODE": "1"})
        self.assertEqual(code, 3)
        self.assertIn("Refused inside a Claude Code session", sortie + erreur)
        self.assertEqual(self.faux.appels, [])
        self.assertEqual(self.ouvertures, 0)

    def test_refus_en_session_en_francais_par_defaut(self):
        code, sortie, erreur = self.lancer("collect", environ={**self.environ, "CLAUDECODE": "1"})
        self.assertEqual(code, 3)
        self.assertIn("Refusé dans une session Claude Code", sortie + erreur)

    def test_francais_par_defaut_et_langue_inconnue(self):
        self.faux.ajouter(REQUETE_A, ticket("ZZA-1"))
        code, sortie, _ = self.lancer("collect")
        self.assertEqual(code, 0)
        self.assertIn("contenu des stories collecté : 1 éléments, 0 remplacements", sortie)
        self.assertIn("éléments au-delà de la conservation, ignorés : 0", sortie)
        self.assertIn("éléments sortis de la collecte : 0 marqués, 0 revenus", sortie)
        self.assertEqual(self.lancer("collect", "--language", "de")[0], 2)

    def test_chaines_distinctives_absentes_de_la_sortie(self):
        self.ecrire_referentiel()
        self.faux.ajouter(REQUETE_A, ticket("ZZKEY-77", equipe="Equipe Zzdistinct", titre="zztitre-distinct",
                                            description=adf("zzdescription-distincte"), criteres="zzcriteres-distincts",
                                            parent="ZZKEY-1"))
        code, sortie, erreur = self.lancer("collect", "--language", "en")
        self.assertEqual(code, 0, erreur)
        for valeur in ("ZZKEY", "Zzdistinct", "zztitre", "zzdescription", "zzcriteres", "Zzalpha", "faux-jeton"):
            self.assertNotIn(valeur, sortie + erreur)

    def test_bloc_absent(self):
        self.ecrire_reglages(bloc="")
        code, _, erreur = self.lancer("collect", "--language", "en")
        self.assertEqual(code, 3)
        self.assertIn("story_quality block missing from flux.yaml", erreur)
        self.assertEqual(self.faux.appels, [])

    def test_plafond_invalide(self):
        self.ecrire_reglages(bloc="""story_quality:
  queries: {alpha: "project = ZZA"}
  issue_types: {story: [Story]}
  engine: {model: m, keychain_service: s, input_price_per_token: 0, output_price_per_token: 0, cap_per_launch: 0}
""")
        code, _, erreur = self.lancer("collect", "--language", "en")
        self.assertEqual(code, 3)
        self.assertIn("cap per launch missing or invalid", erreur)

    def test_reglage_inconnu_nomme_sans_valeur(self):
        texte = (self.flux / "flux.yaml").read_text(encoding="utf-8")
        (self.flux / "flux.yaml").write_text(texte + "  overlay_path: /chemin/zzsurcouche.yaml\n", encoding="utf-8")
        code, _, erreur = self.lancer("collect", "--language", "en")
        self.assertEqual(code, 1)
        self.assertIn("story_quality.overlay_path", erreur)
        self.assertNotIn("zzsurcouche", erreur)

    def test_acces_refuse_par_jira_sans_jeton_ni_message_de_jira(self):
        self.faux.refus = 401
        code, sortie, erreur = self.lancer("collect", "--language", "en")
        self.assertEqual(code, 1)
        self.assertIn("Jira error, nothing is written", erreur)
        self.assertNotIn("faux-jeton", sortie + erreur)
        self.assertNotIn("Zzrefus", sortie + erreur)
        self.assertEqual(self.magasin.ecritures, 0)


class UnSeulPoEtEquipesInconnues(EspaceCollecte):
    def test_drapeau_apparie_sans_casse_ni_espaces_ni_forme_unicode(self):
        self.ecrire_referentiel()
        self.faux.ajouter(REQUETE_A, ticket("ZZA-1", equipe="EQUIPE  zzalpha "), ticket("ZZA-2", equipe="Equipe  Zzbeta"))
        code, _, erreur = self.lancer("collect")
        self.assertEqual(code, 0, erreur)
        self.assertEqual(sorted(self.magasin.attributs.values()), [False, True])
        self.assertTrue(self.magasin.attributs["EQUIPE  zzalpha"])

    def test_forme_decomposee_du_nom_du_referentiel(self):
        self.ecrire_referentiel(REFERENTIEL.replace(EQUIPE_A, "Equipe Zzalé"))
        self.faux.ajouter(REQUETE_A, ticket("ZZA-1", equipe="Equipe Zzalé"))
        self.lancer("collect")
        self.assertEqual(list(self.magasin.attributs.values()), [True])

    def test_equipes_absentes_du_referentiel_comptees_sans_nom(self):
        self.ecrire_referentiel()
        self.faux.ajouter(REQUETE_A, ticket("ZZA-1", equipe=EQUIPE_A), ticket("ZZA-2", equipe="Equipe Zzinconnue"),
                          ticket("ZZA-3", equipe="Equipe Zzautre"), ticket("ZZA-4", equipe="Equipe Zzautre"))
        code, sortie, erreur = self.lancer("collect", "--language", "en")
        self.assertEqual(code, 0, erreur)
        self.assertIn("teams absent from the referential: 2", sortie)
        self.assertNotIn("Zzinconnue", sortie + erreur)
        self.assertNotIn("Zzautre", sortie + erreur)

    def test_equipe_inconnue_comptee_et_jamais_ecrite(self):
        self.ecrire_referentiel()
        self.faux.ajouter(REQUETE_A, ticket("ZZA-1", equipe="999"), ticket("ZZA-2", equipe=EQUIPE_A))
        code, sortie, _ = self.lancer("collect", "--language", "en")
        self.assertEqual(code, 0)
        self.assertEqual(self.magasin.equipes["ZZA-1"], [])
        self.assertEqual(self.magasin.equipes["ZZA-2"], [EQUIPE_A])
        self.assertNotIn("(équipe inconnue)", str(self.magasin.equipes) + str(self.magasin.attributs))
        self.assertIn("teams absent from the referential: 1", sortie)

    def test_en_francais(self):
        self.ecrire_referentiel()
        self.faux.ajouter(REQUETE_A, ticket("ZZA-1", equipe="Equipe Zzinconnue"))
        _, sortie, _ = self.lancer("collect")
        self.assertIn("équipes absentes du référentiel : 1", sortie)


class DatesIllisibles(EspaceCollecte):
    def test_elements_ecartes_comptes(self):
        illisible = ticket("ZZA-1")
        illisible["fields"]["created"] = "zz-pas-une-date"
        autre = ticket("ZZA-2")
        autre["fields"]["updated"] = "zz-pas-une-date"
        self.faux.ajouter(REQUETE_A, illisible, autre, ticket("ZZA-3"))
        code, sortie, erreur = self.lancer("collect", "--language", "en")
        self.assertEqual(code, 0, erreur)
        self.assertEqual(list(self.magasin.elements), ["ZZA-3"])
        self.assertIn("story content collected: 1 items", sortie)
        self.assertIn("items skipped for unreadable dates: 2", sortie)
        self.assertNotIn("zz-pas-une-date", sortie + erreur)

    def test_en_francais(self):
        illisible = ticket("ZZA-1")
        illisible["fields"]["created"] = "zz-pas-une-date"
        self.faux.ajouter(REQUETE_A, illisible)
        _, sortie, _ = self.lancer("collect")
        self.assertIn("éléments ignorés pour dates illisibles : 1", sortie)


class TypesDePersonne(unittest.TestCase):
    def test_champ_de_approbations_est_un_champ_de_personne(self):
        champ = {"schema": {"type": "array", "items": "sd-approvals", "custom": "com.atlassian.servicedesk:sd-approvals"}}
        self.assertTrue(collect.est_champ_de_personne(champ))
        self.assertIn("sd-approvals", collect.TYPES_DE_PERSONNE)


if __name__ == "__main__":
    unittest.main()
