"""Couverture de l'historique : la base rend les mêmes tickets « avec historique » que le cache de history_jira.py.

    bash tools/dbtest.sh flow_store          (instance jetable : installation.md, 14.5 ; sautés sans elle)

Cause observée sur de vraies données : la lecture de la base rendait une entrée pour TOUS les tickets (liste vide pour ceux sans
transition), alors que le cache n'a une entrée que pour les tickets collectés. flux_jira.py compte la couverture et repère les dormants
d'après ces entrées : 100 % de couverture et beaucoup plus de dormants côté base, 72 % côté CSV. Le jeu inventé ci-dessous a un cache
partiel : des entrées avec transitions, des entrées vides (ticket jamais déplacé) et des tickets sans entrée.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import unittest
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import aide_base as base          # noqa: E402
import jeu                        # noqa: E402
from test_sources_scripts import AvecDossier, FLUX, SOURCE_DB, lancer, rapports  # noqa: E402

AUJOURDHUI = dt.date.today().isoformat()


class CouvertureDeLHistorique(base.AvecBase, AvecDossier):
    def setUp(self):
        super().setUp()
        self.liste = jeu.tickets()
        cles = {t["cle"] for t in self.liste}
        self.transitions = [(c, i, d, a) for c, i, d, a in jeu.transitions() if c in cles]
        avec_transitions = sorted({c for c, *_ in self.transitions})
        self.entrees_vides = [t["cle"] for t in self.liste if t["cle"] not in avec_transitions][:7]      # jamais déplacés
        self.avec_entree = avec_transitions + self.entrees_vides
        self.sans_entree = [t["cle"] for t in self.liste if t["cle"] not in self.avec_entree]
        self.inserer(self.liste, jeu.liens(), self.transitions, avec_historique=self.avec_entree)
        self.cache = self.dossier() / "transitions.json"
        contenu = {c: {"termine": False, "transitions": []} for c in self.avec_entree}
        for cle, instant, depart, arrivee in self.transitions:
            contenu[cle]["transitions"].append([instant.strftime("%Y-%m-%dT%H:%M:%S.000%z"), depart, arrivee])
        self.cache.write_text(json.dumps(contenu), encoding="utf-8")
        self.export = self.dossier() / "export.csv"
        jeu.ecrire_csv(self.export, self.liste)

    def reglages(self):
        import flux_jira
        return {**flux_jira.DEFAULT_CONFIG, "colonnes": dict(flux_jira.DEFAULT_CONFIG["colonnes"])}

    def test_le_jeu_couvre_les_trois_cas(self):
        self.assertTrue(self.entrees_vides and self.sans_entree and self.transitions)

    def test_la_base_rend_les_memes_cles_que_le_cache(self):
        import flow_store
        import flux_jira
        lu = flow_store.lire_historique(self.reglages())
        cache = flux_jira.charger_historique(self.cache)
        self.assertEqual(sorted(lu), sorted(cache))
        self.assertEqual(sorted(k for k, v in lu.items() if not v), sorted(self.entrees_vides))
        self.assertFalse(set(self.sans_entree) & set(lu))

    def test_rapports_avec_historique_identiques_en_csv_et_en_base(self):
        csv_ws, db_ws = self.dossier(), self.dossier()
        commun = ("--name", "h", "--today", AUJOURDHUI, "--no-comparison", "--dormant-from-history", "--scope", "PROJ")
        r_csv = lancer(FLUX, csv_ws, "compute", str(self.export), *commun, "--history", str(self.cache))
        r_db = lancer(FLUX, db_ws, "compute", SOURCE_DB, *commun, "--history", env=self.env)
        self.assertEqual(r_csv.returncode, 0, r_csv.stdout + r_csv.stderr)
        self.assertEqual(r_db.returncode, 0, r_db.stdout + r_db.stderr)
        nom = f"flux-h-{AUJOURDHUI}"
        self.assertEqual(rapports(db_ws)[nom + ".md"], rapports(csv_ws)[nom + ".md"])
        self.assertEqual(rapports(db_ws)[nom + ".json"], rapports(csv_ws)[nom + ".json"])

    def test_la_comparaison_signale_une_couverture_differente(self):
        import flow_compare
        import flux_jira
        from flow_compare_messages import CATALOGS
        from messages import Messages
        cache = flux_jira.charger_historique(self.cache)
        tout = {c: [] for c in (t["cle"].upper() for t in self.liste)}           # l'ancienne lecture : une entrée par ticket
        tout.update(cache)
        e = flow_compare.Ecarts()
        flow_compare.comparer_historiques(cache, tout, set(tout), Messages(CATALOGS, "fr"), e)
        self.assertEqual(e.total, len(self.sans_entree))
        self.assertIn(f"tickets avec historique en base seulement : {len(self.sans_entree)}", "\n".join(e.lignes))


if __name__ == "__main__":
    unittest.main()
