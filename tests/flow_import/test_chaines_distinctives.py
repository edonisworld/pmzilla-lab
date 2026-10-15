"""Chaînes distinctives de flow_import.py et de son lecteur (change jira-gdpr-alignment, tâche 2.4).

    uv run --with numpy --with pyyaml python -m unittest discover -s tests/flow_import -v

Spécifications : jira-flow-labels (« Only declared labels are stored »), jira-flow-organisation (« Names stay in the flow
folder »). Les CSV portent des colonnes « Declared Label » et « Fix Version » aux valeurs distinctives, une clé, une équipe
et un nom de fichier distinctifs.
- Lecteur (sans base) : le résultat de la lecture ne garde ni étiquette ni version (le code actuel ne les lit pas ; le test
  verrouille la régression pour les groupes qui ne garderont que les périodes d'étiquettes déclarées).
- Import (avec la base jetable, sauté sans Docker) : la sortie et les erreurs ne montrent ni étiquette, version, clé, équipe
  ni nom de fichier, et aucune ligne de la base ne porte l'étiquette ou la version.
Écarté faute de mode sans base : l'import réel sans base ; l'essai à blanc se connecte aussi.
"""
import contextlib
import re
import tempfile
import unittest
from pathlib import Path

import csv_factices as cf
import flow_export_reader as lecteur
from test_import import ImportBase

ETIQUETTE = "ZZDISTINCT-ETIQUETTE"
VERSION = "ZZDISTINCT-VERSION"
CLE = "ZZKEY-77"
EQUIPE = "ZZDISTINCT-EQUIPE"
FICHIER = "zzdistinct-fichier.csv"
ENTETE = cf.ENTETE + ["Declared Label", "Fix Version"]


def lignes_distinctives():
    return [cf.ligne(f"{CLE}-{i}", Team=EQUIPE, **{"Declared Label": ETIQUETTE, "Fix Version": VERSION}) for i in (1, 2)]


class Lecteur(unittest.TestCase):
    def test_la_lecture_ne_garde_ni_etiquette_ni_version(self):
        with tempfile.TemporaryDirectory() as temp:
            chemin = cf.ecrire(Path(temp) / FICHIER, lignes_distinctives(), ENTETE)
            resultat = lecteur.lire_exports([str(chemin)], cf.reglages())
        self.assertEqual(len(resultat["tickets"]), 2)
        tout = repr(resultat)
        for chaine in (ETIQUETTE, VERSION, "Declared Label", "Fix Version"):
            self.assertNotIn(chaine, tout)
        for ticket in resultat["tickets"]:
            self.assertEqual(ticket["equipes"], [EQUIPE])          # l'équipe est lue : elle va dans la base, jamais en console


class Import(ImportBase):
    def lancer_import(self, *options):
        chemin = self.csv(FICHIER, lignes_distinctives(), ENTETE)
        return chemin, self.lancer(chemin, *options)

    def test_sortie_sans_etiquette_version_cle_equipe_ni_nom_de_fichier(self):
        for options in ((), ("--dry-run",), ("--language", "en")):
            chemin, (code, sortie, erreur) = self.lancer_import(*options)
            self.assertEqual(code, 0, erreur)
            tout = sortie + erreur
            for chaine in (ETIQUETTE, VERSION, CLE, EQUIPE, FICHIER, chemin):
                self.assertNotIn(chaine, tout, options)
            self.assertIsNone(re.search(r"[A-Z][A-Z0-9_]*-\d+", tout), tout)

    def test_la_base_ne_garde_ni_etiquette_ni_version(self):
        self.lancer_import()
        self.conn.rollback()
        tables = [t[0] for t in self.tout("SELECT table_name FROM information_schema.tables WHERE table_schema = 'flow'")]
        for table in tables:
            for ligne in self.tout(f"SELECT t::text FROM flow.{table} t"):
                self.assertNotIn(ETIQUETTE, ligne[0], table)
                self.assertNotIn(VERSION, ligne[0], table)

    def test_cache_d_historique_avec_etiquettes_ignore(self):
        """Un cache dont une entrée porterait des champs d'étiquette : sortie muette, base sans la chaîne."""
        cache = self.cache({f"{CLE}-1": {"termine": False, "labels": [ETIQUETTE], "fixVersions": [VERSION],
                                         "transitions": [["2026-03-01T09:00:00.000+0200", "Open", "Done"]]}})
        chemin = self.csv(FICHIER, lignes_distinctives(), ENTETE)
        code, sortie, erreur = self.lancer(chemin, "--history", cache)
        self.assertEqual(code, 0, erreur)
        for chaine in (ETIQUETTE, VERSION, CLE, EQUIPE, FICHIER):
            self.assertNotIn(chaine, sortie + erreur)

    def test_seules_les_etiquettes_declarees_sont_stockees(self):
        """Avec --history, une étiquette déclarée est stockée (table des périodes), une non déclarée jamais."""
        autre = "ZZDISTINCT-AUTRE"
        self.reglages = cf.reglages(declared_labels={"cycle": {"prefix": "ZZDISTINCT-", "labels": [ETIQUETTE]}})
        lignes = [cf.ligne(f"{CLE}-1", Team=EQUIPE, **{"Declared Label": ETIQUETTE}),
                  cf.ligne(f"{CLE}-2", Team=EQUIPE, **{"Declared Label": autre})]
        chemin = self.csv(FICHIER, lignes, ENTETE)
        code, sortie, erreur = self.lancer(chemin, "--history", self.cache({}))
        self.assertEqual(code, 0, erreur)
        self.conn.rollback()
        self.assertEqual(self.tout("SELECT issue_key, label FROM flow.issue_label_periods"), [(f"{CLE}-1", ETIQUETTE)])
        for table in [t[0] for t in self.tout("SELECT table_name FROM information_schema.tables WHERE table_schema = 'flow'")]:
            for ligne in self.tout(f"SELECT t::text FROM flow.{table} t"):
                self.assertNotIn(autre, ligne[0], table)
        for chaine in (ETIQUETTE, autre, CLE, EQUIPE, FICHIER):
            self.assertNotIn(chaine, sortie + erreur)


if __name__ == "__main__":
    unittest.main()
