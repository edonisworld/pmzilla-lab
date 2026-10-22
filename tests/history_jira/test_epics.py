"""Collecte de l'historique des épics (R-89, conception D12, tâche 2.3), sur le faux serveur de test_history_jira.py.

    bash tests/run_all.sh history_jira

Les types d'épic des réglages sont interrogés même quand ce sont des types de niveau portefeuille ; les autres types de niveau
portefeuille et tous les tickets d'un projet exclu (épics compris) ne le sont pas. La ligne « épics interrogés : n » ne porte ni
clé, ni équipe, ni étiquette. Données et noms inventés, faux jeton.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_history_jira as base  # noqa: E402

REGLAGES = ("portfolio_types: [Epic, Initiative]\nepic_types: [Epic]\nexcluded_projects: [BUG]\n"
            "declared_labels:\n  cycle:\n    prefix: cyc-\n    labels: [cyc-a]\n")
ETIQUETTE_DISTINCTIVE = "cyc-a"


class Epics(base.Base):
    def preparer(self, reglages: str = REGLAGES):
        self.ecrire_reglages("scopes", reglages)
        lignes = self.inventer(2)
        for cle, typ in (("EPI-1", "Epic"), ("EPI-2", "Epic"), ("EPI-3", "Epic"), ("INI-1", "Initiative"),
                         ("INI-2", "Initiative"), ("BUG-9", "Epic")):
            self.faux.ajouter(cle)
            lignes.append((cle, typ, "Equipe Distinctive", False))
        return lignes

    def test_epics_interroges_les_autres_types_de_portefeuille_et_les_projets_exclus_non(self):
        lignes = self.preparer()
        code, sortie = self.lancer("collect", self.ecrire_export(lignes))
        self.assertEqual(code, 0, sortie)
        self.assertEqual(set(self.cache()), {"ABC-1", "ABC-2", "EPI-1", "EPI-2", "EPI-3"})
        self.assertIn("épics interrogés : 3", sortie)
        self.assertIn("écartés (types de portefeuille, projets exclus) : 3", sortie)     # 2 initiatives + l'épic du projet exclu
        self.assertLess(sortie.index("épics interrogés : 3"), sortie.index("Tickets lus"))

    def test_ligne_en_anglais(self):
        lignes = self.preparer()
        code, sortie = self.lancer("collect", self.ecrire_export(lignes), "--language", "en")
        self.assertEqual(code, 0, sortie)
        self.assertIn("epics queried: 3", sortie)
        self.assertNotIn("épics interrogés", sortie)

    def test_aucune_cle_equipe_ou_etiquette_dans_la_console(self):
        lignes = self.preparer()
        code, sortie = self.lancer("collect", self.ecrire_export(lignes))
        self.assertEqual(code, 0, sortie)
        for interdit in ("EPI-1", "EPI-2", "EPI-3", "INI-1", "BUG-9", "Equipe Distinctive", ETIQUETTE_DISTINCTIVE):
            self.assertNotIn(interdit, sortie)

    def test_epic_sans_epic_dans_l_export(self):
        self.ecrire_reglages("scopes", REGLAGES)
        code, sortie = self.lancer("collect", self.ecrire_export(self.inventer(2)))
        self.assertEqual(code, 0, sortie)
        self.assertIn("épics interrogés : 0", sortie)

    def test_types_d_epic_hors_portefeuille_pas_de_ligne(self):
        """Quand les épics ne sont pas des types de niveau portefeuille, rien ne change : pas de ligne, pas d'exception."""
        lignes = self.preparer("portfolio_types: [Initiative]\nepic_types: [Epic]\nexcluded_projects: [BUG]\n")
        code, sortie = self.lancer("collect", self.ecrire_export(lignes))
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("épics interrogés", sortie)
        self.assertIn("EPI-1", self.cache())           # un épic ordinaire est déjà interrogé comme tout ticket
        self.assertNotIn("INI-1", self.cache())

    def test_type_d_epic_sans_casse(self):
        lignes = self.preparer(REGLAGES.replace("epic_types: [Epic]", "epic_types: [EPIC]"))
        code, sortie = self.lancer("collect", self.ecrire_export(lignes))
        self.assertEqual(code, 0, sortie)
        self.assertIn("épics interrogés : 3", sortie)

    def test_evenements_d_etiquettes_declarees_de_l_epic_gardes_sans_auteur(self):
        lignes = self.preparer()
        self.faux.tickets["EPI-1"] = ("40001", [
            {"id": "1", "created": "2026-03-01T09:00:00.000+0200", "author": {"displayName": base.AUTEUR},
             "items": [{"field": "labels", "fieldId": "labels", "fromString": "", "toString": ETIQUETTE_DISTINCTIVE},
                       {"field": "status", "fieldId": "status", "fromString": "Open", "toString": "Idea"}]}])
        self.faux.courantes["EPI-1"] = {"fixVersions": [], "labels": [ETIQUETTE_DISTINCTIVE]}
        code, sortie = self.lancer("collect", self.ecrire_export(lignes))
        self.assertEqual(code, 0, sortie)
        entree = self.cache()["EPI-1"]
        periodes = self.magasin.periodes["etiquettes"]["EPI-1"]
        self.assertEqual([(valeur, fin) for (valeur, _), fin in periodes.items()], [(ETIQUETTE_DISTINCTIVE, None)])
        self.assertEqual(len(entree["transitions"]), 1)
        self.assertNotIn(base.AUTEUR, str(entree) + repr(periodes))

    def test_epic_d_un_projet_exclu_compte_avec_les_autres_ecartes_pas_comme_epic(self):
        lignes = self.preparer()
        code, sortie = self.lancer("collect", self.ecrire_export([x for x in lignes if x[0] in ("BUG-9", "ABC-1")]))
        self.assertEqual(code, 0, sortie)
        self.assertIn("épics interrogés : 0", sortie)
        self.assertIn("écartés (types de portefeuille, projets exclus) : 1", sortie)
        self.assertEqual(set(self.cache()), {"ABC-1"})


if __name__ == "__main__":
    unittest.main()
