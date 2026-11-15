"""Collecte complète de l'historique : jamais une fiche fausse quand la lecture groupée est tronquée (R-20261113-31, décision R-20261113-36,
couche 1 « collecteur » du dossier 2026-11-13-fiches-sans-historique). Tests T1 à T5 ; T6 (magasin, base jetable) est dans test_magasin_base.py.

    bash tests/run_all.sh history_jira

Un ticket rendu par la recherche des clés mais absent de la réponse groupée du changelog n'est plus noté « sans transition » : il est relu
par le repli par ticket ; si le repli échoue, il n'est pas noté (indicateur « avec historique » faux, erreur passagère comptée, ticket
réinterrogé au passage suivant). Un jeton de page répété est une erreur passagère du lot, jamais une fin silencieuse. Une transition à
date illisible est comptée (le nombre seul est affiché). Faux serveur, base fictive, données inventées, faux jeton.
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_history_jira as base  # noqa: E402

DECLAREES = "declared_labels:\n  cycle:\n    prefix: cyc-\n    labels: [cyc-a, cyc-b]\n"
UUID = "0123456789abcdef-0123456789abcdef-01"
UUID_B = "fedcba9876543210-fedcba9876543210-01"


def historique(created: str, *items: dict) -> dict:
    return {"id": created, "created": created, "author": {"displayName": base.AUTEUR}, "items": list(items)}


def element(champ: str, de, vers, de_texte=None, vers_texte=None) -> dict:
    return {"field": "Zz libellé", "fieldId": champ, "from": de, "to": vers, "fromString": de_texte, "toString": vers_texte}


class CollecteComplete(base.Base):
    def lancer_collecte(self, *options):
        return self.lancer("collect", *options)

    def appels_changelog_de(self, cle):
        return [a for a in self.faux.appels if a[0] == "GET" and a[1].startswith(f"/rest/api/3/issue/{cle}/changelog")]

    # --- T1 --------------------------------------------------------------------------------------------------------------

    def test_t1_un_ticket_absent_de_la_reponse_groupee_est_relu_par_le_repli_par_ticket(self):
        self.ecrire_export(self.inventer(3))
        self.faux.tickets["ABC-3"] = (self.faux.tickets["ABC-3"][0], [])          # ABC-3 n'a aucun historique
        self.faux.absents_groupe = {"ABC-1", "ABC-3"}
        code, sortie = self.lancer_collecte()
        self.assertEqual(code, 0, sortie)
        self.assertTrue(self.appels_changelog_de("ABC-1"))                     # relu par ticket
        self.assertTrue(self.appels_changelog_de("ABC-3"))
        self.assertFalse(self.appels_changelog_de("ABC-2"))                    # présent dans la réponse groupée : pas relu
        self.assertEqual([t[2] for t in self.magasin.transitions["ABC-1"]], ["In Progress", "Done"])     # l'historique est écrit
        self.assertEqual(self.magasin.transitions["ABC-3"], [])                # [] confirmé par la relecture
        self.assertTrue(self.magasin.stock["ABC-3"]["a_historique"])
        self.assertEqual(self.magasin.passages_en_erreur, [])
        self.assertEqual(len(self.magasin.passages), 1)
        self.assertIn("tickets relus par ticket : 2", sortie)                   # le nombre seul, jamais une clé
        self.assertNotIn("ABC-", sortie)

    # --- T2 --------------------------------------------------------------------------------------------------------------

    def test_t2_repli_en_erreur_le_ticket_n_est_pas_note_et_le_passage_compte_une_erreur(self):
        self.ecrire_export(self.inventer(2))
        self.faux.absents_groupe = {"ABC-1"}
        self.faux.erreurs_ticket = {"ABC-1": 503}
        code, sortie = self.lancer_collecte()
        self.assertEqual(code, 0, sortie)                                       # sans --strict : sortie inchangée (Q-H7)
        self.assertFalse(self.magasin.stock["ABC-1"]["a_historique"])
        self.assertNotIn("ABC-1", self.magasin.transitions)
        self.assertTrue(self.magasin.stock["ABC-2"]["a_historique"])
        self.assertEqual([erreurs for _, erreurs in self.magasin.passages_en_erreur], [1])
        self.assertEqual(self.magasin.passages, [])                             # n'avance pas la dernière collecte réussie
        self.assertIn("503", sortie)
        self.assertNotIn("ABC-", sortie)
        self.assertNotIn("Nom Fictif", sortie)

    # --- T3 --------------------------------------------------------------------------------------------------------------

    def test_t3_un_jeton_de_page_repete_est_une_erreur_passagere_du_lot_entier(self):
        self.ecrire_export(self.inventer(2))
        self.faux.jeton_repete = True
        code, sortie = self.lancer_collecte()
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.magasin.transitions, {})                          # rien noté pour le lot
        self.assertFalse(any(t["a_historique"] for t in self.magasin.stock.values()))
        self.assertEqual([erreurs for _, erreurs in self.magasin.passages_en_erreur], [2])     # le lot entier est compté
        self.assertEqual(self.magasin.passages, [])

    def test_t3_le_jeton_repete_a_son_propre_libelle_en_francais_et_en_anglais(self):
        self.ecrire_export(self.inventer(2))
        self.faux.jeton_repete = True
        code, sortie = self.lancer_collecte()
        self.assertIn("pagination répétée : 2", sortie)
        self.assertNotIn("réseau", sortie)
        self.assertNotIn("HTTP 0", sortie)
        code, sortie = self.lancer("collect", "--language", "en")
        self.assertIn("repeated pagination: 2", sortie)
        self.assertNotIn("network", sortie)

    def test_t3_un_jeton_repete_de_la_recherche_des_cles_est_une_erreur_du_lot_et_jamais_un_404(self):
        self.ecrire_export(self.inventer(2))
        self.faux.jeton_repete_recherche = True
        code, sortie = self.lancer_collecte()
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.magasin.transitions, {})                          # rien noté pour le lot
        self.assertFalse(any(t["a_historique"] for t in self.magasin.stock.values()))
        self.assertEqual([erreurs for _, erreurs in self.magasin.passages_en_erreur], [2])     # le lot entier est compté en erreur
        self.assertEqual(self.magasin.nombres_introuvables, [0])                # aucun 404 compté
        self.assertEqual(self.magasin.compteurs, {})
        self.assertEqual(self.magasin.passages, [])

    def test_t3_le_jeton_repete_reste_une_erreur_avec_strict(self):
        self.ecrire_export(self.inventer(2))
        self.faux.jeton_repete = True
        code, sortie = self.lancer_collecte("--strict")
        self.assertEqual(code, 3, sortie)

    # --- T4 --------------------------------------------------------------------------------------------------------------

    def test_t4_une_reponse_groupee_tronquee_ne_supprime_aucune_periode_existante(self):
        self.ecrire_reglages("scopes", extra=DECLAREES)
        self.ecrire_export(self.inventer(1))
        self.faux.tickets["ABC-1"] = ("30001", [
            historique("2026-03-01T09:00:00.000+0200", element("fixVersions", None, "9", None, "v1")),
            historique("2026-03-02T09:00:00.000+0200", element("labels", None, None, "", "cyc-a")),
            historique("2026-02-01T09:00:00.000+0200", element("customfield_99001", None, "5")),
            historique("2026-03-03T09:00:00.000+0200", element(
                "customfield_99002", f"[{UUID}:101]", f"[{UUID}:101, {UUID_B}:102]", "ZzA", "ZzA, ZzB"))])
        self.faux.courantes["ABC-1"] = {"fixVersions": ["v1"], "labels": ["cyc-a"], "champs": {
            "customfield_99001": [{"id": 5, "name": "ZzSprint"}],
            "customfield_99002": [{"objectId": "101"}, {"objectId": "102"}]}}
        code, sortie = self.lancer_collecte()
        self.assertEqual(code, 0, sortie)
        avant = copy.deepcopy(self.magasin.periodes)
        for nature in ("etiquettes", "versions", "sprints", "actifs"):
            self.assertTrue(avant.get(nature, {}).get("ABC-1"), nature)         # des vraies périodes, datées après la création
        # deuxième passage : la réponse groupée omet le ticket et le repli échoue ; l'ancien code le notait « sans historique »
        # et réécrivait ses périodes depuis la création
        self.faux.absents_groupe = {"ABC-1"}
        self.faux.erreurs_ticket = {"ABC-1": 503}
        code, sortie = self.lancer_collecte()
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.magasin.periodes, avant)

    # --- T5 --------------------------------------------------------------------------------------------------------------

    def preparer_date_illisible(self):
        self.ecrire_export(self.inventer(1))
        statut = {"field": "status", "fieldId": "status", "fromString": "Open", "toString": "Done"}
        self.faux.tickets["ABC-1"] = ("30001", [
            historique("pas-une-date", dict(statut)),
            historique("2026-03-01T09:00:00.000+0200", {**statut, "fromString": "Open", "toString": "In Progress"})])

    def test_t5_une_transition_a_date_illisible_est_comptee_et_le_nombre_affiche(self):
        self.preparer_date_illisible()
        code, sortie = self.lancer_collecte()
        self.assertEqual(code, 0, sortie)
        self.assertIn("transitions de statut à date illisible écartées : 1", sortie)
        self.assertEqual([t[2] for t in self.magasin.transitions["ABC-1"]], ["In Progress"])      # l'illisible n'est pas écrite
        self.assertNotIn("ABC-1", sortie)
        self.assertNotIn("pas-une-date", sortie)

    def test_t5_la_ligne_existe_en_anglais(self):
        self.preparer_date_illisible()
        code, sortie = self.lancer("collect", "--language", "en")
        self.assertEqual(code, 0, sortie)
        self.assertIn("status transitions with an unreadable date set aside: 1", sortie)

    def test_t5_aucune_ligne_sans_date_illisible(self):
        self.ecrire_export(self.inventer(1))
        code, sortie = self.lancer_collecte()
        self.assertEqual(code, 0, sortie)
        self.assertNotIn("date illisible", sortie)
        self.assertNotIn("relus par ticket", sortie)                            # aucune relecture : aucune ligne


if __name__ == "__main__":
    unittest.main()
