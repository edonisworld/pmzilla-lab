"""Collecte étendue de history_jira.py (R-58, tâches 6.1 et 6.3 ; change database-only, D5), sur le faux serveur et la base fictive.

    bash tests/run_all.sh history_jira

La collecte lit dans Jira les événements de statut, de versions correctives et, si des étiquettes sont déclarées, d'étiquettes
déclarées, ainsi que les valeurs courantes des versions et des étiquettes (l'export ne les demande plus). Elle écrit dans la base les
transitions et les PÉRIODES d'étiquettes déclarées et de versions (history_common.construire_periodes), jamais l'auteur, les autres champs
ni les étiquettes non déclarées. Les tickets résolus depuis plus que la durée de conservation ne sont pas interrogés. Données inventées,
date du jour figée.
"""
import datetime as dt
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_history_jira as base  # noqa: E402

AUJOURD_HUI = dt.date(2026, 10, 13)
DECLAREES = "declared_labels:\n  cycle:\n    prefix: cyc-\n    labels: [cyc-a, cyc-b]\n"
NON_DECLAREE = "autre-secrete"
VERSION_1, VERSION_2 = "V-ancienne", "V-nouvelle"


def historique(created: str, *items: dict) -> dict:
    return {"id": created, "created": created, "author": {"displayName": base.AUTEUR, "emailAddress": "p@example.org"},
            "items": list(items)}


def statut(de: str, vers: str) -> dict:
    return {"field": "status", "fieldId": "status", "fromString": de, "toString": vers}


def etiquettes(de: str, vers: str) -> dict:
    return {"field": "labels", "fieldId": "labels", "fromString": de, "toString": vers}


def version(de: str | None, vers: str | None) -> dict:
    return {"field": "Fix Version", "fieldId": "fixVersions", "fromString": de, "toString": vers}


def instant(texte: str) -> dt.datetime:
    return dt.datetime.fromisoformat(texte)


CREE = dt.datetime(2026, 1, 2, 9, 0, tzinfo=base.PARIS)       # création des tickets de la base fictive


class Etendue(base.Base):
    def setUp(self):
        super().setUp()
        p = mock.patch.object(base.hj, "aujourd_hui", lambda: AUJOURD_HUI)
        p.start()
        self.addCleanup(p.stop)

    def historique_riche(self, cle: str = "ABC-1"):
        """Un ticket dont le changelog ajoute une étiquette déclarée et une non déclarée, change l'assigné et la fix version."""
        self.faux.tickets[cle] = ("30001", [
            historique("2026-03-01T09:00:00.000+0200", statut("Open", "In Progress"),
                       etiquettes("", f"cyc-a {NON_DECLAREE}"),
                       {"field": "assignee", "fieldId": "assignee", "fromString": None, "toString": base.AUTEUR}),
            historique("2026-03-02T09:00:00.000+0200", version(VERSION_1, None), version(None, VERSION_2)),
            historique("2026-03-03T09:00:00.000+0200", etiquettes(f"cyc-a {NON_DECLAREE}", NON_DECLAREE))])
        self.faux.courantes[cle] = {"fixVersions": [VERSION_2], "labels": [NON_DECLAREE]}
        return [(cle, "Story", "Equipe Test", True)]

    def periodes(self, nature: str, cle: str = "ABC-1") -> dict:
        return self.magasin.periodes[nature].get(cle, {})

    # --- Mode groupé -----------------------------------------------------------------------------------------------

    def test_mode_groupe_transitions_a_trois_elements_et_aucune_periode_sans_valeur(self):
        self.ecrire_export(self.inventer(3, termines={"ABC-1"}))
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 0, sortie)
        self.assertIn("Mode : groupé", sortie)
        for cle, entree in self.cache().items():
            self.assertEqual(set(entree), {"transitions"}, cle)
            self.assertTrue(all(len(t) == 3 for t in entree["transitions"]))
            self.assertNotIn("assignee", repr(entree))
        self.assertEqual(self.periodes("versions"), {})                       # aucune version courante, aucun événement
        self.assertEqual(self.periodes("etiquettes"), {})                     # étiquettes non suivies sans bloc declared_labels

    def test_la_requete_groupee_demande_statut_etiquettes_et_fix_versions(self):
        self.ecrire_export(self.inventer(2))
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 0, sortie)
        corps = next(c for api, c in self.faux.corps if api == "/rest/api/3/changelog/bulkfetch")
        self.assertEqual(sorted(corps["fieldIds"]), ["fixVersions", "labels", "status"])

    # --- Valeurs courantes et périodes ---------------------------------------------------------------------------------

    def test_les_valeurs_courantes_sont_demandees_a_la_recherche(self):
        self.ecrire_reglages("scopes", extra=DECLAREES)
        self.ecrire_export(self.inventer(2))
        self.lancer("collect")
        champs = [c["fields"] for api, c in self.faux.corps if api == "/rest/api/3/search/jql" and c["fields"] != ["key"]]
        self.assertEqual(champs, [["fixVersions", "labels"]])
        self.faux.corps.clear()
        self.ecrire_reglages("scopes")                                         # sans étiquette déclarée : les étiquettes ne sont pas demandées
        self.lancer("collect", "--refresh")
        champs = [c["fields"] for api, c in self.faux.corps if api == "/rest/api/3/search/jql" and c["fields"] != ["key"]]
        self.assertEqual(champs, [["fixVersions"]])

    def test_periodes_d_etiquette_declaree_et_de_fix_version(self):
        self.ecrire_reglages("scopes", extra=DECLAREES)
        self.ecrire_export(self.historique_riche())
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.periodes("etiquettes"),
                         {("cyc-a", instant("2026-03-01T09:00:00+02:00")): instant("2026-03-03T09:00:00+02:00")})
        self.assertEqual(self.periodes("versions"),
                         {(VERSION_1, CREE): instant("2026-03-02T09:00:00+02:00"),             # retirée sans ajout connu : posée à la création
                          (VERSION_2, instant("2026-03-02T09:00:00+02:00")): None})            # ajoutée, toujours posée
        self.assertEqual(len(self.cache()["ABC-1"]["transitions"]), 1)
        self.assertNotIn(NON_DECLAREE, repr(self.magasin.periodes))
        self.assertIn("historique écrit : 1 transitions ajoutées, 3 périodes écrites", sortie)

    def test_valeur_courante_sans_evenement_ouvre_une_periode_a_la_creation(self):
        self.ecrire_reglages("scopes", extra=DECLAREES)
        self.faux.ajouter("ABC-1")
        self.faux.courantes["ABC-1"] = {"fixVersions": [VERSION_2], "labels": ["cyc-b", NON_DECLAREE]}
        self.ecrire_export([("ABC-1", "Story", "Equipe Test", False)])
        self.lancer("collect")
        self.assertEqual(self.periodes("etiquettes"), {("cyc-b", CREE): None})
        self.assertEqual(self.periodes("versions"), {(VERSION_2, CREE): None})

    def test_une_periode_qui_n_est_plus_dans_jira_est_retiree(self):
        self.ecrire_reglages("scopes", extra=DECLAREES)
        self.faux.ajouter("ABC-1")
        self.faux.courantes["ABC-1"] = {"fixVersions": [VERSION_1], "labels": []}
        self.ecrire_export([("ABC-1", "Story", "Equipe Test", False)])
        self.lancer("collect")
        self.assertEqual(self.periodes("versions"), {(VERSION_1, CREE): None})
        self.faux.courantes["ABC-1"] = {"fixVersions": [VERSION_2], "labels": []}
        self.lancer("collect", "--refresh")
        self.assertEqual(self.periodes("versions"), {(VERSION_2, CREE): None})          # l'ensemble construit fait foi

    def test_cache_ajout_non_declare_et_retrait_declare(self):
        """Scénario « Cache events » de jira-flow-labels : seul le retrait de l'étiquette déclarée compte."""
        self.ecrire_reglages("scopes", extra=DECLAREES)
        self.faux.tickets["ABC-1"] = ("30001", [
            historique("2026-04-01T09:00:00.000+0200", etiquettes("cyc-b", f"cyc-b {NON_DECLAREE}")),
            historique("2026-04-02T09:00:00.000+0200", etiquettes(f"cyc-b {NON_DECLAREE}", NON_DECLAREE))])
        self.faux.courantes["ABC-1"] = {"fixVersions": [], "labels": [NON_DECLAREE]}
        self.ecrire_export([("ABC-1", "Story", "Equipe Test", False)])
        self.lancer("collect")
        self.assertEqual(self.periodes("etiquettes"), {("cyc-b", CREE): instant("2026-04-02T09:00:00+02:00")})
        self.assertNotIn(NON_DECLAREE, repr(self.magasin.periodes))

    def test_etiquettes_remplacees_difference_d_ensembles(self):
        self.ecrire_reglages("scopes", extra=DECLAREES)
        self.faux.tickets["ABC-1"] = ("30001", [historique("2026-04-01T09:00:00.000+0200", etiquettes("cyc-a x", "cyc-b x"))])
        self.faux.courantes["ABC-1"] = {"fixVersions": [], "labels": ["cyc-b", "x"]}
        self.ecrire_export([("ABC-1", "Story", "Equipe Test", False)])
        self.lancer("collect")
        self.assertEqual(self.periodes("etiquettes"),
                         {("cyc-a", CREE): instant("2026-04-01T09:00:00+02:00"),
                          ("cyc-b", instant("2026-04-01T09:00:00+02:00")): None})

    def test_sans_etiquette_declaree_aucune_etiquette_n_est_gardee(self):
        self.ecrire_export(self.historique_riche())
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.periodes("etiquettes"), {})
        self.assertEqual(len(self.periodes("versions")), 2)                   # les fix versions restent gardées
        self.assertNotIn("cyc-a", repr(self.magasin.periodes))
        self.assertNotIn(NON_DECLAREE, repr(self.magasin.periodes))

    def test_mode_ticket_par_ticket_donne_les_memes_periodes(self):
        self.faux.groupe = False
        self.ecrire_reglages("scopes", extra=DECLAREES)
        self.ecrire_export(self.historique_riche())
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 0, sortie)
        self.assertIn("Mode : ticket par ticket", sortie)
        self.assertEqual([(valeur, fin is None) for (valeur, _), fin in self.periodes("versions").items()],
                         [(VERSION_1, False), (VERSION_2, True)])
        self.assertEqual(list(self.periodes("etiquettes")), [("cyc-a", instant("2026-03-01T09:00:00+02:00"))])

    def test_rien_de_sensible_dans_la_console_ni_la_base(self):
        self.ecrire_reglages("scopes", extra=DECLAREES)
        self.ecrire_export(self.historique_riche())
        code, sortie = self.lancer("collect", "--team", "Equipe Test")
        self.assertEqual(code, 0, sortie)
        self.assertIn("transitions de statut : 1 ;", sortie)
        ecrit = self.tous_les_fichiers() + repr(self.magasin.transitions) + repr(self.magasin.periodes)
        for texte in (sortie, ecrit):
            for interdit in (base.JETON, base.AUTEUR, "p@example.org", "assignee", base.EMAIL, NON_DECLAREE):
                self.assertNotIn(interdit, texte)
        for interdit in ("ABC-", "Equipe Test", "cyc-a", VERSION_1, VERSION_2, self.url):
            self.assertNotIn(interdit, sortie)

    def test_l_ensemble_des_periodes_se_remplace_dans_la_meme_ecriture(self):
        self.ecrire_reglages("scopes", extra=DECLAREES)
        self.ecrire_export(self.historique_riche())
        self.magasin.echec = RuntimeError("base")
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 1, sortie)
        self.assertEqual((self.magasin.periodes, self.cache()), ({"etiquettes": {}, "versions": {}}, {}))

    # --- Conservation (6.3) ---------------------------------------------------------------------------------------

    def tickets_anciens(self, jours: int, cles=("ABC-1",)):
        """Tickets résolus il y a `jours` jours (plus un ticket ouvert ABC-9)."""
        for cle in (*cles, "ABC-9"):
            self.faux.ajouter(cle)
        self.ecrire_export([(c, "Story", "Equipe Test", True) for c in cles] + [("ABC-9", "Story", "Equipe Test", False)])
        resolu = dt.datetime.combine(AUJOURD_HUI - dt.timedelta(days=jours), dt.time(10, 0), tzinfo=base.PARIS)
        for cle in cles:
            self.magasin.stock[cle]["resolu"] = resolu

    def test_ticket_au_dela_de_la_conservation_n_est_pas_interroge_et_est_compte(self):
        self.tickets_anciens(400)
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 0, sortie)
        self.assertIn("tickets au-delà de la conservation, ignorés : 1", sortie)
        self.assertEqual(set(self.cache()), {"ABC-9"})                    # seul le ticket ouvert est collecté
        self.assertIn("Tickets traités : 1 ;", sortie)
        self.assertNotIn("ABC-", sortie)

    def test_ticket_au_dela_de_la_conservation_en_anglais(self):
        self.tickets_anciens(400)
        code, sortie = self.lancer("collect", "--language", "en")
        self.assertIn("tickets past retention, skipped: 1", sortie)

    def test_aucun_appel_quand_tous_les_tickets_sont_au_dela(self):
        self.tickets_anciens(400, cles=("ABC-1", "ABC-2"))
        del self.magasin.stock["ABC-9"]                                    # plus de ticket ouvert
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 0, sortie)
        self.assertIn("ignorés : 2", sortie)
        self.assertEqual(self.faux.appels, [])
        self.assertEqual(self.cache(), {})

    def test_ticket_dans_la_conservation_est_interroge(self):
        self.tickets_anciens(300)
        code, sortie = self.lancer("collect")
        self.assertIn("ignorés : 0", sortie)
        self.assertEqual(set(self.cache()), {"ABC-1", "ABC-9"})

    def test_duree_reglable(self):
        self.ecrire_reglages("scopes", extra="retention:\n  period_days: 100\n")
        self.tickets_anciens(150)
        code, sortie = self.lancer("collect")
        self.assertIn("ignorés : 1", sortie)

    def test_historique_deja_stocke_d_un_ticket_hors_regle_n_est_pas_supprime(self):
        self.tickets_anciens(400)
        self.magasin.transitions["ABC-1"] = [(instant("2026-01-05T10:00:00+01:00"), "Open", "Done")]
        self.magasin.stock["ABC-1"]["a_historique"] = True
        self.lancer("collect")
        self.assertIn("ABC-1", self.cache())                              # la suppression est le fait de la purge de flow_retention.py

    def test_duree_au_dela_d_un_an_refusee_avant_tout_appel(self):
        self.ecrire_reglages("scopes", extra="retention:\n  period_days: 400\n")
        self.tickets_anciens(10)
        code, sortie = self.lancer("collect")
        self.assertEqual(code, 1, sortie)
        self.assertIn("retention.period_days", sortie)
        self.assertNotIn("400", sortie)
        self.assertEqual(self.faux.appels, [])
        self.assertNotIn("Traceback", sortie)


if __name__ == "__main__":
    unittest.main()
