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
from aide_scripts import AvecDossier  # noqa: E402

sys.path.append(str(ICI.parents[1] / "tests" / "flux_jira"))
import chargeur_csv as chargeur  # noqa: E402


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
        lu = flow_store.lire_historique(self.reglages())
        cache = chargeur.lire_historique(self.reglages(), str(self.cache))
        self.assertEqual(sorted(lu), sorted(cache))
        self.assertEqual(sorted(k for k, v in lu.items() if not v), sorted(self.entrees_vides))
        self.assertFalse(set(self.sans_entree) & set(lu))


if __name__ == "__main__":
    unittest.main()
