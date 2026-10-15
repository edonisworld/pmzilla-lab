"""Groupe 8 de jira-gdpr-alignment, avec la base jetable : marque « sorti de l'export », périodes d'étiquettes déclarées et de
versions, tickets au-delà de la conservation. Sautés sans base (comme test_import.py).

    bash tools/dbtest.sh flow_import

Specs : jira-flow-import (Out-of-export mark, Mark only with a complete export set, Declared labels and fix versions imported,
Tickets past retention not imported). Données inventées (PROJ-n, étiquettes lbl-a et lbl-b, versions 1.0 et 2.0).
Les fonctions pures et les refus avant connexion sont testés sans base dans test_groupe8_sans_base.py.
"""
import datetime as dt
import re
import unittest

import csv_factices as cf
from test_import import ImportBase

UTC = dt.timezone.utc
DECLAREES = {"cycle": {"prefix": "lbl-", "labels": ["lbl-a", "lbl-b"]}}
ENTETE = cf.ENTETE + ["Declared Label", "Fix Version"]
JOUR = "2026-10-13"


def evenements(cle, **champs):
    return {cle: {"termine": False, "transitions": [], **champs}}


class MarqueAbsents(ImportBase):
    def setUp(self):
        super().setUp()
        self.reglages = cf.reglages(jql_exports={"alpha": "a", "beta": "b"})

    def lancer(self, *arguments, langue=None):
        """Les jeux de ces tests marquent un ticket sur trois : le seuil de 20 % est levé, sauf quand le test le règle lui-même."""
        if "--mark-absent" in arguments and "--max-absent-percent" not in arguments:
            arguments = (*arguments, "--max-absent-percent", "100")
        return super().lancer(*arguments, langue=langue)

    def test_part_au_dela_du_seuil_refusee_sans_rien_ecrire(self):
        self.premier_jeu()                                                # trois tickets stockés
        code, sortie, erreur = self.lancer(*self.jeu([cf.ligne("PROJ-1")], [cf.ligne("PROJ-9")], "2026-11-13"), "--mark-absent",
                                           "--max-absent-percent", "20", langue="en")     # 2 absents sur 4 stockés = 50 %
        self.assertEqual(code, 1)
        self.assertIn("too many tickets absent from the files (more than 20% of stored tickets)", sortie + erreur)
        self.assertIsNone(self.marque("PROJ-2"))
        self.assertIsNone(self.marque("PROJ-3"))

    def test_seuil_par_defaut_vingt_pour_cent(self):
        self.premier_jeu()
        code, sortie, erreur = super().lancer(*self.jeu([cf.ligne("PROJ-1")], [cf.ligne("PROJ-3")], "2026-11-13"),
                                              "--mark-absent", langue="en")       # 1 sur 3 = 33 % > 20 %
        self.assertEqual(code, 1)
        self.assertIn("--mark-absent refused", sortie + erreur)
        self.assertIsNone(self.marque("PROJ-2"))

    def test_part_sous_le_seuil_acceptee(self):
        self.premier_jeu()
        code, sortie, erreur = self.lancer(*self.jeu([cf.ligne("PROJ-1")], [cf.ligne("PROJ-3")], "2026-11-13"), "--mark-absent",
                                           "--max-absent-percent", "40", langue="en")
        self.assertEqual(code, 0, erreur)
        self.assertIn("Tickets out of the export: 1 marked, 0 back", sortie.splitlines())

    def jeu(self, alpha, beta, jour=JOUR):
        """Les deux fichiers du jour (un par requête nommée) ; rend leurs chemins."""
        return [self.csv(f"api-alpha-{jour}.csv", alpha), self.csv(f"api-beta-{jour}.csv", beta)]

    def marque(self, cle):
        self.conn.rollback()
        return self.un("SELECT out_of_export_at FROM flow.issues WHERE key = %s", cle)[0]

    def premier_jeu(self):
        self.comptes(*self.jeu([cf.ligne("PROJ-1")], [cf.ligne("PROJ-2"), cf.ligne("PROJ-3")]), "--mark-absent")

    def test_un_ticket_qui_quitte_l_export_est_marque(self):
        self.premier_jeu()
        self.assertIsNone(self.marque("PROJ-2"))
        avant = dt.datetime.now(UTC)
        code, sortie, erreur = self.lancer(*self.jeu([cf.ligne("PROJ-1")], [cf.ligne("PROJ-3")], "2026-11-13"),
                                           "--mark-absent", langue="en")
        self.assertEqual(code, 0, erreur)
        self.assertIn("Tickets out of the export: 1 marked, 0 back", sortie.splitlines())
        instant = self.marque("PROJ-2")
        self.assertIsNotNone(instant)
        self.assertGreaterEqual(instant, avant - dt.timedelta(seconds=5))
        self.assertIsNone(self.marque("PROJ-1"))
        self.assertIsNone(self.marque("PROJ-3"))
        self.assertEqual(self.nombre("issues"), 3)                      # rien n'est supprimé

    def test_phrase_en_francais(self):
        self.premier_jeu()
        _, sortie, _ = self.lancer(*self.jeu([cf.ligne("PROJ-1")], [cf.ligne("PROJ-3")], "2026-11-13"), "--mark-absent")
        self.assertIn("Tickets sortis de l'export : 1 marqués, 0 revenus", sortie.splitlines())

    def test_la_sortie_ne_montre_aucune_cle(self):
        self.premier_jeu()
        _, sortie, erreur = self.lancer(*self.jeu([cf.ligne("PROJ-1")], [cf.ligne("PROJ-3")], "2026-11-13"), "--mark-absent")
        self.assertIsNone(re.search(r"[A-Z][A-Z0-9_]*-\d+", sortie + erreur))

    def test_un_ticket_qui_revient_perd_sa_marque_meme_sans_l_option(self):
        self.premier_jeu()
        self.comptes(*self.jeu([cf.ligne("PROJ-1")], [cf.ligne("PROJ-3")], "2026-11-13"), "--mark-absent")
        self.assertIsNotNone(self.marque("PROJ-2"))
        # un seul fichier, sans l'option : le jeu n'est pas complet, mais la marque du ticket présent est effacée
        code, sortie, erreur = self.lancer(self.csv("autre.csv", [cf.ligne("PROJ-2")]), langue="en")
        self.assertEqual(code, 0, erreur)
        self.assertIn("Tickets out of the export: 0 marked, 1 back", sortie.splitlines())
        self.assertIsNone(self.marque("PROJ-2"))

    def test_sans_l_option_aucune_marque(self):
        self.premier_jeu()
        code, sortie, _ = self.lancer(self.csv("autre.csv", [cf.ligne("PROJ-1")]), langue="en")
        self.assertEqual(code, 0)
        self.assertIn("Tickets out of the export: 0 marked, 0 back", sortie.splitlines())
        self.assertEqual(self.tout("SELECT count(*) FROM flow.issues WHERE out_of_export_at IS NOT NULL"), [(0,)])

    def test_une_marque_existante_n_est_pas_deplacee(self):
        self.premier_jeu()
        self.comptes(*self.jeu([cf.ligne("PROJ-1")], [cf.ligne("PROJ-3")], "2026-11-13"), "--mark-absent")
        premiere = self.marque("PROJ-2")
        code, sortie, _ = self.lancer(*self.jeu([cf.ligne("PROJ-1")], [cf.ligne("PROJ-3")], "2026-12-13"), "--mark-absent",
                                      langue="en")
        self.assertEqual(code, 0)
        self.assertIn("Tickets out of the export: 0 marked, 0 back", sortie.splitlines())
        self.assertEqual(self.marque("PROJ-2"), premiere)

    def test_un_ticket_absent_de_tous_les_fichiers_seulement(self):
        """Un ticket présent dans l'un des deux fichiers n'est pas marqué, même s'il manque à l'autre."""
        self.premier_jeu()
        self.comptes(*self.jeu([cf.ligne("PROJ-3")], [cf.ligne("PROJ-2")], "2026-11-13"), "--mark-absent")
        self.assertEqual(self.tout("SELECT key FROM flow.issues WHERE out_of_export_at IS NOT NULL"), [("PROJ-1",)])

    def test_essai_a_blanc_calcule_sans_marquer(self):
        self.premier_jeu()
        code, sortie, _ = self.lancer(*self.jeu([cf.ligne("PROJ-1")], [cf.ligne("PROJ-3")], "2026-11-13"), "--mark-absent",
                                      "--dry-run", langue="en")
        self.assertEqual(code, 0)
        self.assertIn("Tickets out of the export: 1 marked, 0 back", sortie.splitlines())
        self.assertIsNone(self.marque("PROJ-2"))

    def test_jeu_incomplet_refuse_sans_rien_ecrire(self):
        code, sortie, erreur = self.lancer(self.csv(f"api-alpha-{JOUR}.csv", [cf.ligne("PROJ-1")]), "--mark-absent", langue="en")
        self.assertEqual(code, 1)
        self.assertIn("incomplete export set: --mark-absent refused", sortie + erreur)
        self.assertEqual(self.nombre("issues"), 0)

    def test_fichiers_de_deux_jours_refuses(self):
        a = self.csv("api-alpha-2026-10-13.csv", [cf.ligne("PROJ-1")])
        b = self.csv("api-beta-2026-10-12.csv", [cf.ligne("PROJ-2")])
        code, sortie, erreur = self.lancer(a, b, "--mark-absent", langue="en")
        self.assertEqual(code, 1)
        self.assertIn("incomplete export set: --mark-absent refused", sortie + erreur)
        self.assertEqual(self.nombre("issues"), 0)


class Periodes(ImportBase):
    def setUp(self):
        super().setUp()
        self.reglages = cf.reglages(declared_labels=DECLAREES)

    def csv_periodes(self, lignes, nom="a.csv"):
        return self.csv(nom, lignes, ENTETE)

    def etiquettes(self):
        self.conn.rollback()
        return self.tout("SELECT issue_key, label, added_at, removed_at FROM flow.issue_label_periods ORDER BY 1, 2, 3")

    def versions(self):
        self.conn.rollback()
        return self.tout("SELECT issue_key, version, added_at, removed_at FROM flow.issue_version_periods ORDER BY 1, 2, 3")

    def test_ajout_puis_retrait_une_periode_fermee(self):
        f = self.csv_periodes([cf.ligne("PROJ-1")])
        cache = self.cache(evenements("PROJ-1", etiquettes=[["2026-02-01T10:00:00.000+0200", "add", "lbl-a"],
                                                            ["2026-03-01T10:00:00.000+0200", "remove", "lbl-a"]]))
        self.comptes(f, "--history", cache)
        self.assertEqual(self.etiquettes(), [("PROJ-1", "lbl-a", dt.datetime(2026, 2, 1, 8, 0, tzinfo=UTC),
                                              dt.datetime(2026, 3, 1, 8, 0, tzinfo=UTC))])

    def test_versions_ajout_puis_retrait_puis_nouvel_ajout(self):
        f = self.csv_periodes([cf.ligne("PROJ-1", **{"Fix Version": "2.0"})])
        cache = self.cache(evenements("PROJ-1", versions=[["2026-02-01T10:00:00.000+0200", "add", "1.0"],
                                                          ["2026-03-01T10:00:00.000+0200", "remove", "1.0"],
                                                          ["2026-03-01T10:00:00.000+0200", "add", "2.0"]]))
        self.comptes(f, "--history", cache)
        self.assertEqual(self.versions(), [
            ("PROJ-1", "1.0", dt.datetime(2026, 2, 1, 8, 0, tzinfo=UTC), dt.datetime(2026, 3, 1, 8, 0, tzinfo=UTC)),
            ("PROJ-1", "2.0", dt.datetime(2026, 3, 1, 8, 0, tzinfo=UTC), None)])

    def test_valeur_de_l_export_sans_evenement_ouvre_une_periode_a_la_creation(self):
        f = self.csv_periodes([cf.ligne("PROJ-1", **{"Declared Label": "lbl-b", "Fix Version": "1.0"})])
        self.comptes(f, "--history", self.cache({}))
        creation = dt.datetime(2026, 1, 2, 8, 30, tzinfo=UTC)
        self.assertEqual(self.etiquettes(), [("PROJ-1", "lbl-b", creation, None)])
        self.assertEqual(self.versions(), [("PROJ-1", "1.0", creation, None)])

    def test_etiquette_non_declaree_refusee_comptee_et_non_stockee(self):
        f = self.csv_periodes([cf.ligne("PROJ-1", **{"Declared Label": "zz-inconnue"}), cf.ligne("PROJ-2", **{"Declared Label": "lbl-a"})])
        code, sortie, erreur = self.lancer(f, "--history", self.cache({}), langue="en")
        self.assertEqual(code, 0, erreur)
        self.assertIn("Label values refused (not declared in the settings): 1.", sortie.splitlines())
        self.assertNotIn("zz-inconnue", sortie + erreur)
        self.assertEqual(self.nombre("issues"), 2)                       # la ligne est importée sans l'étiquette
        self.assertEqual([l[:2] for l in self.etiquettes()], [("PROJ-2", "lbl-a")])
        for table in ("issues", "issue_label_periods", "issue_version_periods"):
            for ligne in self.tout(f"SELECT t::text FROM flow.{table} t"):
                self.assertNotIn("zz-inconnue", ligne[0])

    def test_valeur_refusee_comptee_aussi_sans_history(self):
        f = self.csv_periodes([cf.ligne("PROJ-1", **{"Declared Label": "zz-inconnue", "Fix Version": "1.0"})])
        _, sortie, _ = self.lancer(f, langue="en")
        self.assertIn("Label values refused (not declared in the settings): 1.", sortie.splitlines())
        self.assertEqual(self.nombre("issue_label_periods") + self.nombre("issue_version_periods"), 0)   # rien sans --history

    def test_reimport_idempotent_et_comptes(self):
        f = self.csv_periodes([cf.ligne("PROJ-1", **{"Declared Label": "lbl-a"})])
        cache = self.cache(evenements("PROJ-1", versions=[["2026-02-01T10:00:00.000+0200", "add", "1.0"]]))
        _, sortie, _ = self.lancer(f, "--history", cache, langue="en")
        self.assertIn("Periods added or updated: declared labels: 1; versions: 1.", sortie.splitlines())
        _, sortie, _ = self.lancer(f, "--history", cache, langue="en")
        self.assertIn("Periods added or updated: declared labels: 0; versions: 0.", sortie.splitlines())
        self.assertEqual((self.nombre("issue_label_periods"), self.nombre("issue_version_periods")), (1, 1))

    def test_un_retrait_arrive_dans_un_cache_plus_recent(self):
        f = self.csv_periodes([cf.ligne("PROJ-1", **{"Declared Label": "lbl-a"})])
        self.comptes(f, "--history", self.cache({}))
        self.assertEqual(self.etiquettes()[0][3], None)
        g = self.csv_periodes([cf.ligne("PROJ-1")], "b.csv")                      # l'étiquette n'est plus dans l'export
        cache = self.cache(evenements("PROJ-1", etiquettes=[["2026-03-01T10:00:00.000+0200", "remove", "lbl-a"]]), "b.json")
        self.comptes(g, "--history", cache)
        creation = dt.datetime(2026, 1, 2, 8, 30, tzinfo=UTC)
        self.assertEqual(self.etiquettes(), [("PROJ-1", "lbl-a", creation, dt.datetime(2026, 3, 1, 8, 0, tzinfo=UTC))])

    def test_la_periode_ouverte_a_la_creation_cede_la_place_a_l_evenement(self):
        f = self.csv_periodes([cf.ligne("PROJ-1", **{"Declared Label": "lbl-a"})])
        self.comptes(f, "--history", self.cache({}))
        cache = self.cache(evenements("PROJ-1", etiquettes=[["2026-02-01T10:00:00.000+0200", "add", "lbl-a"]]), "b.json")
        self.comptes(f, "--history", cache)
        self.assertEqual(self.etiquettes(), [("PROJ-1", "lbl-a", dt.datetime(2026, 2, 1, 8, 0, tzinfo=UTC), None)])

    def test_export_sans_colonnes_ne_retire_aucune_periode(self):
        f = self.csv_periodes([cf.ligne("PROJ-1", **{"Declared Label": "lbl-a"})])
        self.comptes(f, "--history", self.cache({}))
        g = self.csv("b.csv", [cf.ligne("PROJ-1", Status="Done", Updated="09/Jan/2026 08:00")])
        self.comptes(g, "--history", self.cache({}, "b.json"))
        self.assertEqual(len(self.etiquettes()), 1)

    def test_evenement_d_une_etiquette_non_declaree_jamais_stocke(self):
        f = self.csv_periodes([cf.ligne("PROJ-1")])
        cache = self.cache(evenements("PROJ-1", etiquettes=[["2026-02-01T10:00:00.000+0200", "add", "zz-inconnue"]]))
        self.comptes(f, "--history", cache)
        self.assertEqual(self.etiquettes(), [])

    def test_ticket_absent_de_la_base_ignore(self):
        f = self.csv_periodes([cf.ligne("PROJ-1")])
        cache = self.cache(evenements("PROJ-9", etiquettes=[["2026-02-01T10:00:00.000+0200", "add", "lbl-a"]]))
        self.comptes(f, "--history", cache)
        self.assertEqual(self.etiquettes(), [])

    def test_aucune_colonne_de_personne_en_base_et_po_ignore(self):
        f = self.csv("a.csv", [cf.ligne("PROJ-1", PO="ZZ-personne-distinctive", **{"Declared Label": "lbl-a"})], ENTETE + ["PO"])
        code, sortie, erreur = self.lancer(f, "--history", self.cache({}))
        self.assertEqual(code, 0, erreur)
        self.assertNotIn("ZZ-personne-distinctive", sortie + erreur)
        self.conn.rollback()
        for table in [t[0] for t in self.tout("SELECT table_name FROM information_schema.tables WHERE table_schema = 'flow'")]:
            for ligne in self.tout(f"SELECT t::text FROM flow.{table} t"):
                self.assertNotIn("ZZ-personne-distinctive", ligne[0], table)
        colonnes = {c[0] for c in self.tout("SELECT column_name FROM information_schema.columns WHERE table_schema = 'flow' "
                                            "AND table_name IN ('issue_label_periods', 'issue_version_periods')")}
        self.assertEqual(colonnes, {"issue_key", "label", "version", "added_at", "removed_at"})

    def test_la_sortie_ne_montre_ni_etiquette_ni_version(self):
        f = self.csv_periodes([cf.ligne("PROJ-1", **{"Declared Label": "lbl-a", "Fix Version": "ZZ-version-distincte"})])
        for options in ((), ("--history", self.cache({})), ("--history", self.cache({}), "--dry-run")):
            _, sortie, erreur = self.lancer(f, *options)
            for chaine in ("lbl-a", "ZZ-version-distincte"):
                self.assertNotIn(chaine, sortie + erreur)


class HorsConservation(ImportBase):
    def test_ligne_resolue_avant_la_conservation_ni_inseree_ni_mise_a_jour(self):
        f = self.csv("a.csv", [cf.ligne("PROJ-1", Resolved="10/Jan/2020 10:00", Resolution="Done", Status="Done"),
                               cf.ligne("PROJ-2")])
        code, sortie, erreur = self.lancer(f, langue="en")
        self.assertEqual(code, 0, erreur)
        self.assertIn("tickets past retention, skipped: 1", sortie.splitlines())
        self.assertEqual(self.tout("SELECT key FROM flow.issues"), [("PROJ-2",)])

    def test_phrase_en_francais(self):
        f = self.csv("a.csv", [cf.ligne("PROJ-1", Resolved="10/Jan/2020 10:00", Status="Done")])
        _, sortie, _ = self.lancer(f)
        self.assertIn("tickets au-delà de la conservation, ignorés : 1", sortie.splitlines())

    def test_un_ticket_deja_stocke_n_est_pas_mis_a_jour(self):
        f = self.csv("a.csv", [cf.ligne("PROJ-1", Resolved="10/Jan/2020 10:00", Status="Done", Updated="07/Jan/2026 08:00")])
        self.conn.execute("INSERT INTO flow.issues (key, project, type, status, created_at, updated_at) "
                          "VALUES ('PROJ-1', 'PROJ', 'Story', 'Open', '2020-01-01', '2026-01-01')")
        self.conn.commit()
        self.assertEqual(self.comptes(f)[:5], [1, 0, 0, 0, 0])               # lu : 1 ; rien d'inséré, de modifié ni d'inchangé
        self.assertEqual(self.un("SELECT status FROM flow.issues WHERE key = 'PROJ-1'"), ("Open",))

    def test_la_duree_est_celle_des_reglages(self):
        self.reglages = cf.reglages(retention={"period_days": 30})
        f = self.csv("a.csv", [cf.ligne("PROJ-1", Resolved="10/Jan/2026 10:00", Status="Done")])
        _, sortie, _ = self.lancer(f, langue="en")
        self.assertIn("tickets past retention, skipped: 1", sortie.splitlines())
        self.assertEqual(self.nombre("issues"), 0)

    def test_duree_au_dela_d_un_an_refusee(self):
        self.reglages = cf.reglages(retention={"period_days": 400})
        code, sortie, erreur = self.lancer(self.csv("a.csv", [cf.ligne("PROJ-1")]))
        self.assertEqual(code, 1)
        self.assertEqual(self.nombre("issues"), 0)

    def test_une_ligne_ecartee_ne_marque_pas_son_ticket_comme_absent(self):
        """Le ticket résolu depuis longtemps est présent dans l'export : sa marque (s'il en avait une) est effacée."""
        self.reglages = cf.reglages(jql_exports={"alpha": "a"})
        self.conn.execute("INSERT INTO flow.issues (key, project, type, status, created_at, updated_at, out_of_export_at) "
                          "VALUES ('PROJ-1', 'PROJ', 'Story', 'Open', '2020-01-01', '2026-01-01', now())")
        self.conn.commit()
        f = self.csv("api-alpha-2026-10-13.csv", [cf.ligne("PROJ-1", Resolved="10/Jan/2020 10:00", Status="Done")])
        self.comptes(f, "--mark-absent")
        self.assertIsNone(self.un("SELECT out_of_export_at FROM flow.issues")[0])


if __name__ == "__main__":
    unittest.main()
