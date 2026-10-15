"""Rapports de la base et des CSV identiques avec des tickets marqués hors export (R-58, tâche 9.4 ; spec jira-flow-store
« Out-of-export tickets left out of database reads », scénario « Marked open ticket »).

    bash tools/dbtest.sh flow_store          (instance jetable : installation.md, 14.5 ; sautés sans elle)

test_sortis_de_l_export.py compare les STRUCTURES lues par les lecteurs (tickets, liens, historique) à celles des lecteurs de CSV.
Ici on compare les RAPPORTS écrits par `flux_jira.py compute` : la base contient des tickets marqués hors export (ouverts et
résolus), le CSV du jour ne les contient pas, et les deux rapports (Markdown et JSON) doivent être octet pour octet les mêmes ;
le travail en cours du rapport ne compte aucun ticket marqué. Données inventées (PROJ-n).
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import aide_base as base          # noqa: E402
import jeu                        # noqa: E402
import test_sources_scripts as sc  # noqa: E402


class RapportsAvecTicketsMarques(base.AvecBase, sc.AvecDossier):
    def setUp(self):
        super().setUp()
        self.liste = jeu.tickets()
        self.ouverts = [t["cle"] for t in self.liste if not t["resolu"] and t["type"] != "Epic"][:3]
        self.resolus = [t["cle"] for t in self.liste if t["resolu"] and t["type"] != "Epic"][:3]
        self.marques = set(self.ouverts + self.resolus)
        self.assertEqual(len(self.marques), 6)
        self.inserer(self.liste, jeu.liens(), [])
        self.conn.execute("SET ROLE pmzilla_flow")
        self.conn.execute("UPDATE flow.issues SET out_of_export_at = now() WHERE key = ANY(%s)", (sorted(self.marques),))
        self.conn.execute("RESET ROLE")
        self.conn.commit()
        self.csv_ws, self.db_ws = self.dossier(), self.dossier()
        self.export = self.dossier() / "export.csv"
        jeu.ecrire_csv(self.export, [t for t in self.liste if t["cle"] not in self.marques],
                       liens_base=[l for l in jeu.liens() if l[0] not in self.marques])

    def lancer_les_deux(self, *plus: str):
        r_csv = sc.lancer(sc.FLUX, self.csv_ws, "compute", str(self.export), "--name", "marques", "--today", sc.AUJOURDHUI,
                          "--no-comparison", *plus)
        r_db = sc.lancer(sc.FLUX, self.db_ws, "compute", sc.SOURCE_DB, "--name", "marques", "--today", sc.AUJOURDHUI,
                         "--no-comparison", *plus, env=self.env)
        self.assertEqual(r_csv.returncode, 0, r_csv.stdout + r_csv.stderr)
        self.assertEqual(r_db.returncode, 0, r_db.stdout + r_db.stderr)
        return r_csv, r_db

    def test_les_rapports_de_flux_de_la_base_et_du_csv_sont_identiques(self):
        r_csv, r_db = self.lancer_les_deux()
        csv, db = sc.rapports(self.csv_ws), sc.rapports(self.db_ws)
        self.assertEqual(sorted(csv), sorted(db))
        self.assertTrue(csv)
        for nom, texte in csv.items():
            self.assertEqual(db[nom], texte, nom)
        self.assertEqual(r_db.stdout.replace(str(self.db_ws), "WS"), r_csv.stdout.replace(str(self.csv_ws), "WS"))

    def test_le_travail_en_cours_ne_compte_aucun_ticket_marque(self):
        self.lancer_les_deux()
        rapport = json.loads(sc.rapports(self.db_ws)[f"flux-marques-{sc.AUJOURDHUI}.json"])
        en_cours = lambda ecartes: sum(1 for t in self.liste if t["categorie"] == "In Progress" and not t["resolu"]
                                       and t["cle"] not in ecartes)
        self.assertGreater(en_cours(set()), en_cours(self.marques))        # le jeu a bien des tickets en cours marqués
        self.assertEqual(rapport["wip"], en_cours(self.marques))
        csv = json.loads(sc.rapports(self.csv_ws)[f"flux-marques-{sc.AUJOURDHUI}.json"])
        self.assertEqual(rapport["wip"], csv["wip"])
        self.assertEqual(rapport["a_faire"], csv["a_faire"])
        self.assertEqual(rapport["termines"], csv["termines"])

    def test_le_rapport_sans_les_tickets_sans_equipe_reste_identique(self):
        self.lancer_les_deux("--teams-only")
        csv, db = sc.rapports(self.csv_ws), sc.rapports(self.db_ws)
        self.assertEqual(db, csv)


if __name__ == "__main__":
    unittest.main()
