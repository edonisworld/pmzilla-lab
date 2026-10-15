"""Collecte étendue de history_jira.py (R-58, tâches 6.1 et 6.3), sur le faux serveur de test_history_jira.py.

    bash tests/run_all.sh history_jira

Le cache garde le drapeau terminé, la date de résolution (colonne Resolved de l'export), le dernier jour vu (le jour de la
collecte), les transitions, les événements de fix versions et, si des étiquettes sont déclarées, ceux des étiquettes déclarées.
Les autres champs, les étiquettes non déclarées et l'auteur ne sont jamais gardés. Les tickets résolus depuis plus que la
durée de conservation ne sont pas interrogés. Données inventées, date du jour figée.
"""
import datetime as dt
import json
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
        return [(cle, "Story", "Equipe Test", True)]

    # --- Grouped mode -------------------------------------------------------------------------------------------

    def test_mode_groupe_drapeau_deux_dates_et_transitions_a_trois_elements(self):
        lignes = self.inventer(3, termines={"ABC-1"})
        code, sortie = self.lancer("collect", self.ecrire_export(lignes))
        self.assertEqual(code, 0, sortie)
        self.assertIn("Mode : groupé", sortie)
        cache = self.cache()
        for cle, entree in cache.items():
            self.assertEqual(set(entree), {"termine", "resolu", "vu_le", "transitions"}, cle)   # ni version ni étiquette
            self.assertEqual(entree["vu_le"], "2026-10-13")
            self.assertTrue(all(len(t) == 3 for t in entree["transitions"]))
            self.assertNotIn("assignee", json.dumps(entree))
        self.assertTrue(cache["ABC-1"]["termine"])
        self.assertEqual(cache["ABC-1"]["resolu"], "2026-09-13T10:00:00")      # colonne Resolved de l'export (30 jours avant)
        self.assertFalse(cache["ABC-2"]["termine"])
        self.assertIsNone(cache["ABC-2"]["resolu"])

    def test_la_requete_groupee_demande_statut_etiquettes_et_fix_versions(self):
        corps = []
        original = base.hj.Client.json

        def espion(client, methode, chemin, **kwargs):
            if chemin == "/rest/api/3/changelog/bulkfetch":
                corps.append(kwargs.get("json"))
            return original(client, methode, chemin, **kwargs)
        with mock.patch.object(base.hj.Client, "json", espion):
            code, sortie = self.lancer("collect", self.ecrire_export(self.inventer(2)))
        self.assertEqual(code, 0, sortie)
        self.assertEqual(sorted(corps[0]["fieldIds"]), ["fixVersions", "labels", "status"])

    # --- Étiquettes déclarées et fix versions --------------------------------------------------------------------

    def test_evenements_d_etiquette_declaree_et_de_fix_version(self):
        self.ecrire_reglages("scopes", extra=DECLAREES)
        lignes = self.historique_riche()
        code, sortie = self.lancer("collect", self.ecrire_export(lignes))
        self.assertEqual(code, 0, sortie)
        entree = self.cache()["ABC-1"]
        self.assertEqual(entree["etiquettes"], [["2026-03-01T09:00:00.000+0200", "add", "cyc-a"],
                                                ["2026-03-03T09:00:00.000+0200", "remove", "cyc-a"]])
        self.assertEqual(entree["versions"], [["2026-03-02T09:00:00.000+0200", "remove", VERSION_1],
                                              ["2026-03-02T09:00:00.000+0200", "add", VERSION_2]])
        self.assertEqual(len(entree["transitions"]), 1)
        self.assertNotIn(NON_DECLAREE, json.dumps(entree))

    def test_cache_ajout_non_declare_et_retrait_declare(self):
        """Scénario « Cache events » de jira-flow-labels : seul le retrait de l'étiquette déclarée est gardé."""
        self.ecrire_reglages("scopes", extra=DECLAREES)
        self.faux.tickets["ABC-1"] = ("30001", [
            historique("2026-04-01T09:00:00.000+0200", etiquettes("cyc-b", f"cyc-b {NON_DECLAREE}")),
            historique("2026-04-02T09:00:00.000+0200", etiquettes(f"cyc-b {NON_DECLAREE}", NON_DECLAREE))])
        code, sortie = self.lancer("collect", self.ecrire_export([("ABC-1", "Story", "Equipe Test", False)]))
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.cache()["ABC-1"]["etiquettes"], [["2026-04-02T09:00:00.000+0200", "remove", "cyc-b"]])
        self.assertNotIn(NON_DECLAREE, json.dumps(self.cache()))

    def test_etiquettes_remplacees_difference_d_ensembles(self):
        self.ecrire_reglages("scopes", extra=DECLAREES)
        self.faux.tickets["ABC-1"] = ("30001", [
            historique("2026-04-01T09:00:00.000+0200", etiquettes("cyc-a x", "cyc-b x"))])
        self.lancer("collect", self.ecrire_export([("ABC-1", "Story", "Equipe Test", False)]))
        self.assertEqual(self.cache()["ABC-1"]["etiquettes"], [["2026-04-01T09:00:00.000+0200", "remove", "cyc-a"],
                                                               ["2026-04-01T09:00:00.000+0200", "add", "cyc-b"]])

    def test_sans_etiquette_declaree_aucune_etiquette_n_est_gardee(self):
        lignes = self.historique_riche()
        code, sortie = self.lancer("collect", self.ecrire_export(lignes))
        self.assertEqual(code, 0, sortie)
        entree = self.cache()["ABC-1"]
        self.assertNotIn("etiquettes", entree)
        self.assertEqual(len(entree["versions"]), 2)                          # les fix versions restent gardées
        self.assertNotIn("cyc-a", json.dumps(entree))
        self.assertNotIn(NON_DECLAREE, json.dumps(entree))

    def test_mode_ticket_par_ticket_garde_les_memes_evenements(self):
        self.faux.groupe = False
        self.ecrire_reglages("scopes", extra=DECLAREES)
        lignes = self.historique_riche()
        code, sortie = self.lancer("collect", self.ecrire_export(lignes))
        self.assertEqual(code, 0, sortie)
        self.assertIn("Mode : ticket par ticket", sortie)
        entree = self.cache()["ABC-1"]
        self.assertEqual([e[1:] for e in entree["etiquettes"]], [["add", "cyc-a"], ["remove", "cyc-a"]])
        self.assertEqual([e[1:] for e in entree["versions"]], [["remove", VERSION_1], ["add", VERSION_2]])
        self.assertNotIn(NON_DECLAREE, json.dumps(entree))

    def test_rien_de_sensible_dans_la_console_ni_les_fichiers(self):
        self.ecrire_reglages("scopes", extra=DECLAREES)
        lignes = self.historique_riche()
        code, sortie = self.lancer("collect", self.ecrire_export(lignes), "--team", "Equipe Test")
        self.assertEqual(code, 0, sortie)
        self.assertIn("transitions de statut : 1 ;", sortie)
        ecrit = self.tous_les_fichiers()
        for texte in (sortie, ecrit):
            for interdit in (base.JETON, base.AUTEUR, "p@example.org", "assignee", base.EMAIL, NON_DECLAREE):
                self.assertNotIn(interdit, texte)
        for interdit in ("ABC-", "Equipe Test", "cyc-a", VERSION_1, VERSION_2, self.url):
            self.assertNotIn(interdit, sortie)

    # --- Cache existant -----------------------------------------------------------------------------------------

    def test_ticket_en_cache_et_termine_garde_son_entree_et_son_dernier_jour_vu_est_mis_a_jour(self):
        lignes = self.inventer(2, termines={"ABC-1"})
        export = self.ecrire_export(lignes)
        self.lancer("collect", export)
        cache = self.cache()
        cache["ABC-1"]["vu_le"] = "2026-09-01"
        cache["ABC-1"]["versions"] = [["2026-03-02T09:00:00.000+0200", "add", VERSION_1]]
        (self.ws / "Flux-Lab" / "historique" / "transitions.json").write_text(json.dumps(cache), encoding="utf-8")
        self.faux.appels.clear()
        self.assertEqual(self.lancer("collect", export)[0], 0)
        entree = self.cache()["ABC-1"]
        self.assertEqual(entree["vu_le"], "2026-10-13")
        self.assertEqual(entree["versions"], [["2026-03-02T09:00:00.000+0200", "add", VERSION_1]])
        self.assertEqual(entree["transitions"], cache["ABC-1"]["transitions"])

    def test_tout_en_cache_et_termine_aucun_appel_meme_avec_un_ancien_cache(self):
        lignes = self.inventer(2, termines={"ABC-1", "ABC-2"})
        export = self.ecrire_export(lignes)
        self.lancer("collect", export)
        cache = {cle: {"termine": v["termine"], "transitions": v["transitions"]} for cle, v in self.cache().items()}
        (self.ws / "Flux-Lab" / "historique" / "transitions.json").write_text(json.dumps(cache), encoding="utf-8")
        self.faux.appels.clear()
        code, sortie = self.lancer("collect", export)
        self.assertEqual(code, 0, sortie)
        self.assertEqual(self.faux.appels, [])
        self.assertEqual(self.cache()["ABC-1"]["resolu"], "2026-09-13T10:00:00")   # complété sans interroger Jira

    # --- Conservation (6.3) ---------------------------------------------------------------------------------------

    def export_ancien(self, jours: int, cles=("ABC-1",)) -> str:
        """Tickets résolus il y a `jours` jours (plus un ticket ouvert)."""
        resolu = (AUJOURD_HUI - dt.timedelta(days=jours)).strftime("%d/%b/%Y") + " 10:00"
        chemin = self.ws / "ancien.csv"
        chemin.write_text("Issue key,Issue Type,Status,Resolved,Team\n" + "".join(
            f"{c},Story,Done,{resolu},Equipe Test\n" for c in cles) + "ABC-9,Story,Open,,Equipe Test\n", encoding="utf-8")
        return str(chemin)

    def test_ticket_au_dela_de_la_conservation_n_est_pas_interroge_et_est_compte(self):
        for cle in ("ABC-1", "ABC-9"):
            self.faux.ajouter(cle)
        code, sortie = self.lancer("collect", self.export_ancien(400))
        self.assertEqual(code, 0, sortie)
        self.assertIn("tickets au-delà de la conservation, ignorés : 1", sortie)
        self.assertEqual(set(self.cache()), {"ABC-9"})                    # seul le ticket ouvert est collecté
        self.assertIn("Tickets traités : 1 ;", sortie)
        self.assertNotIn("ABC-", sortie)

    def test_ticket_au_dela_de_la_conservation_en_anglais(self):
        self.faux.ajouter("ABC-9")
        code, sortie = self.lancer("collect", self.export_ancien(400), "--language", "en")
        self.assertIn("tickets past retention, skipped: 1", sortie)

    def test_aucun_appel_quand_tous_les_tickets_sont_au_dela(self):
        chemin = self.export_ancien(400, cles=("ABC-1", "ABC-2"))
        texte = Path(chemin).read_text(encoding="utf-8").replace("ABC-9,Story,Open,,Equipe Test\n", "")
        Path(chemin).write_text(texte, encoding="utf-8")
        code, sortie = self.lancer("collect", chemin)
        self.assertEqual(code, 0, sortie)
        self.assertIn("ignorés : 2", sortie)
        self.assertEqual(self.faux.appels, [])
        self.assertFalse((self.ws / "Flux-Lab" / "historique" / "transitions.json").exists())

    def test_ticket_dans_la_conservation_est_interroge(self):
        for cle in ("ABC-1", "ABC-9"):
            self.faux.ajouter(cle)
        code, sortie = self.lancer("collect", self.export_ancien(300))
        self.assertIn("ignorés : 0", sortie)
        self.assertEqual(set(self.cache()), {"ABC-1", "ABC-9"})

    def test_duree_reglable(self):
        self.ecrire_reglages("scopes", extra="retention:\n  period_days: 100\n")
        for cle in ("ABC-1", "ABC-9"):
            self.faux.ajouter(cle)
        code, sortie = self.lancer("collect", self.export_ancien(150))
        self.assertIn("ignorés : 1", sortie)

    def test_entree_de_cache_existante_d_un_ticket_hors_regle_n_est_pas_supprimee(self):
        for cle in ("ABC-1", "ABC-9"):
            self.faux.ajouter(cle)
        (self.ws / "Flux-Lab" / "historique").mkdir()
        (self.ws / "Flux-Lab" / "historique" / "transitions.json").write_text(
            json.dumps({"ABC-1": {"termine": True, "transitions": []}}), encoding="utf-8")
        self.lancer("collect", self.export_ancien(400))
        self.assertIn("ABC-1", self.cache())                              # la suppression est le fait de la purge

    def test_duree_au_dela_d_un_an_refusee_avant_tout_appel(self):
        self.ecrire_reglages("scopes", extra="retention:\n  period_days: 400\n")
        self.faux.ajouter("ABC-9")
        code, sortie = self.lancer("collect", self.export_ancien(10))
        self.assertEqual(code, 1, sortie)
        self.assertIn("retention.period_days", sortie)
        self.assertNotIn("400", sortie)
        self.assertEqual(self.faux.appels, [])
        self.assertNotIn("Traceback", sortie)


if __name__ == "__main__":
    unittest.main()
