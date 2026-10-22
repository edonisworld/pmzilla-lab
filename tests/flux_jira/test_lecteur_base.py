"""flux_jira.py lit la base seule (change database-only, D6) : lecture, refus d'usage, session, historique absent.

    uv run --with pyyaml --with numpy python -m unittest discover -s tests/flux_jira -v

Lancements dans le processus (aide_espace.py) avec un faux flow_store : aucune base, aucune connexion. Les lignes de commande sont données
telles quelles (brut=True) pour les refus.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
from aide_espace import AvecEspace, faux_store, fj  # noqa: E402


class ErreurBase(Exception):            # le script reconnaît l'erreur de la base à son nom de classe
    pass


def tickets_et_colonnes():
    return [], {"cle": "Issue key", "type": "Issue Type", "etat": "Status", "cree": "Created", "resolu": "Resolved", "debut": None,
                "equipe": None}, 0, 0


class Lecture(AvecEspace):
    def test_lire_tickets_lit_la_base_avec_les_reglages(self):
        lecture = mock.Mock(return_value=([], {}, 0, 0))
        with mock.patch.dict(sys.modules, {"flow_store": faux_store(lire_tickets_flux=lecture)}):
            self.assertEqual(fj.lire_tickets({"export_timezone": "Europe/Paris"}), ([], {}, 0, 0))
        lecture.assert_called_once_with({"export_timezone": "Europe/Paris"})

    def test_base_injoignable_message_clair_code_1(self):
        store = faux_store(lire_tickets_flux=mock.Mock(side_effect=ErreurBase("refusée")))
        for commande in ("statuses", "compute"):
            code, _, _ = self.lancer(commande, store=store)
            self.assertEqual(code, "Base de données : lecture impossible. refusée")

    def test_autre_erreur_non_masquee(self):
        store = faux_store(lire_tickets_flux=mock.Mock(side_effect=KeyError("x")))
        with self.assertRaises(KeyError):
            self.lancer("statuses", store=store)

    def test_aucun_module_de_lecture_de_fichier_d_export(self):
        for nom in ("read_export", "read_exports", "verifier_exports", "lire_source", "charger_historique", "SOURCES",
                    "HISTORIQUE_DEFAUT", "CODE_ENTREE_MANQUANTE"):
            self.assertFalse(hasattr(fj, nom), nom)


class Refus(AvecEspace):
    """Avant toute lecture des réglages et de la base, sans nommer ni fichier ni valeur."""

    def refus(self, *argv, langue="fr"):
        boum = faux_store(lire_tickets_flux=mock.Mock(side_effect=AssertionError("connexion")),
                          lire_historique=mock.Mock(side_effect=AssertionError("connexion")))
        code, console, erreur = self.lancer(*argv, "--language", langue, store=boum, brut=True)
        self.assertFalse((self.flux / "flux.yaml").exists())            # aucun réglage lu ni créé
        return code, console + erreur

    def test_source_retiree_quelle_que_soit_la_valeur(self):
        for commande in ("statuses", "compute"):
            for valeur in ("db", "csv", "ftp"):
                code, sortie = self.refus(commande, "--source", valeur)
                self.assertEqual(code, 2, (commande, valeur))
                self.assertIn("--source est retirée : la base est la seule source", sortie)
                self.assertNotIn("ftp", sortie)

    def test_option_avant_la_sous_commande_est_une_erreur_d_usage(self):
        """Prémisse de D12 (retrait des règles deny à joker initial sur --source) : le parseur principal n'a aucune option avant la
        sous-commande, donc `flux_jira.py --source db compute` sort en erreur d'usage avant toute lecture des réglages et de la base ;
        seules les formes « sous-commande puis options », couvertes par les règles ancrées, lancent un calcul."""
        for valeur in ("db", "=db"):
            argv = ("--source=db", "compute") if valeur == "=db" else ("--source", "db", "compute")
            code, sortie = self.refus(*argv)
            self.assertEqual(code, 2, argv)
            self.assertIn("usage:", sortie)

    def test_source_retiree_en_anglais(self):
        code, sortie = self.refus("compute", "--source", "db", langue="en")
        self.assertEqual(code, 2)
        self.assertIn("--source is retired: the database is the only source", sortie)

    def test_fichier_d_export_refuse_sans_le_nommer(self):
        for commande in ("statuses", "compute"):
            for langue, phrase in (("fr", "les fichiers d'export ne sont plus lus : la base est la seule source"),
                                   ("en", "export files are no longer read: the database is the only source")):
                code, sortie = self.refus(commande, "secret-nom.csv", langue=langue)
                self.assertEqual(code, 2)
                self.assertIn(phrase, sortie)
                self.assertNotIn("secret-nom", sortie)

    def test_chemin_donne_a_history_refuse(self):
        for langue, phrase in (("fr", "--history ne prend aucun fichier : l'historique est lu dans la base"),
                               ("en", "--history takes no file: the history is read from the database")):
            code, sortie = self.refus("compute", "--history", "cache-secret.json", langue=langue)
            self.assertEqual(code, 2)
            self.assertIn(phrase, sortie)
            self.assertNotIn("cache-secret", sortie)

    def test_session_claude_code_refusee_code_3_avant_le_reste(self):
        for commande in ("statuses", "compute"):
            for langue, phrase in (("fr", "Refusé dans une session Claude Code"), ("en", "Refused inside a Claude Code session")):
                with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}):
                    code, sortie = self.refus(commande, "--source", "db", "a.csv", langue=langue)
                self.assertEqual(code, 3)
                self.assertIn(phrase, sortie)

    def test_session_variable_vide_refuse_aussi(self):
        with mock.patch.dict(os.environ, {"CLAUDECODE": ""}):
            code, _ = self.refus("compute")
        self.assertEqual(code, 3)

    def test_compare_et_config_restent_possibles_en_session(self):
        """Seuls statuses et compute (qui lisent la base) sont refusés : compare lit des rapports, config des réglages."""
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}):
            code, _, _ = self.lancer("compare", "--name", "x", brut=True)
        self.assertNotEqual(code, 3)


class HistoriqueAbsent(AvecEspace):
    def setUp(self):
        super().setUp()
        self.ecrire("flux.yaml", "")
        self.store = faux_store(lire_tickets_flux=lambda settings: tickets_et_colonnes(),
                                lire_historique=mock.Mock(return_value={}))

    def test_history_sans_historique_code_1_et_une_phrase(self):
        for langue, phrase in (("fr", "aucun historique dans la base : lancez d'abord la collecte de l'historique"),
                               ("en", "no history in the database: run the history collection first")):
            code, console, erreur = self.lancer("compute", "--history", "--language", langue, store=self.store)
            self.assertEqual(code, 1)
            self.assertIn(phrase, console + erreur)
        self.assertFalse(self.rapports.exists() and list(self.rapports.glob("flux-*")))

    def test_dormants_depuis_l_historique_sans_historique_code_1(self):
        code, console, erreur = self.lancer("compute", "--dormant-from-history", store=self.store)
        self.assertEqual(code, 1)
        self.assertIn("aucun historique dans la base", console + erreur)


if __name__ == "__main__":
    unittest.main()
