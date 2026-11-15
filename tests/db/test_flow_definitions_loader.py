"""Chargeur des définitions réelles de flux sur la base jetable (change flow-definitions-loader, tâche 2.4, conception D3, D4 et D8 ; spec
flow-cycle-referential, exigences « Real definitions are written through the referential's writing function » et « A definitions load
never empties a loaded cycle referential »).

    bash tools/dbtest.sh db

Même base jetable que test_flow_schema.py (même fixture) ; sautée sans elle. Écrite sans être lancée par un agent : passe de l'auteur
(tâche 10.1). Réglages et noms inventés ; le chargeur est appelé par sa fonction de service, sous le rôle d'import.
"""
import sys
import unittest
from datetime import date
from pathlib import Path

import test_db as base          # noqa: E402,F401
from test_db import db          # noqa: E402
import test_flow_schema as fs   # noqa: E402
import test_flow_referential as tfr   # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import flow_definitions as fd   # noqa: E402
import flow_referential as fr   # noqa: E402
import flux_config as cfg       # noqa: E402

TABLES_DEFINITIONS = ("ref_flow_statuses", "ref_unplanned_types", "ref_blocking_link_types")
TABLES_CYCLES = ("ref_cycles", "ref_labels", "ref_dw_columns", "ref_dw_statuses")


def reglages(statuts: int = 3) -> dict:
    """Réglages internes inventés : `statuts` statuts dans le segment « definition », un type non planifié, deux types de liens."""
    return cfg.to_internal({"segments": {"definition": [f"t-etat-{i}" for i in range(statuts)]},
                            "uncounted_segments": {"todo": [], "done": []}, "commitment_point": "definition",
                            "defect_types": ["t-defaut"], "blocking_link_types": ["t-bloque"], "waiting_link_types": ["t-attend"]},
                           "flux.yaml")


class ChargeurAvecBase(unittest.TestCase):
    """Même base jetable que SchemaFlow (migrations appliquées, base supprimée à la fin)."""
    setUp = fs.SchemaFlow.setUp
    _supprimer = fs.SchemaFlow._supprimer
    conn = fs.SchemaFlow.conn
    essaie = fs.SchemaFlow.essaie
    inserer = tfr.ReferentielAvecBase.inserer
    cycle = tfr.ReferentielAvecBase.cycle

    def charger(self, c, interne):
        c.execute("SET ROLE pmzilla_flow")
        try:
            comptes = fd.charger_definitions(c, interne)
            c.commit()
            return comptes
        except BaseException:
            c.rollback()
            raise
        finally:
            c.execute("RESET ROLE")
            c.commit()

    def compte(self, c, table):
        return c.execute(f"SELECT count(*) FROM flow.{table}").fetchone()[0]

    def test_un_chargement_remplit_les_trois_tables_et_laisse_les_cycles_vides(self):
        c = self.conn()
        self.assertEqual(self.charger(c, reglages(3)), (3, 1, 2))
        self.assertEqual([self.compte(c, t) for t in TABLES_DEFINITIONS], [3, 1, 2])
        self.assertEqual([self.compte(c, t) for t in TABLES_CYCLES], [0, 0, 0, 0])
        self.assertEqual(self.compte(c, "ref_state"), 1)

    def test_un_second_chargement_avec_moins_de_statuts_remplace_et_date_la_ligne_d_etat(self):
        c = self.conn()
        self.charger(c, reglages(3))
        premier = c.execute("SELECT loaded_at FROM flow.ref_state").fetchone()[0]
        self.charger(c, reglages(1))
        self.assertEqual(self.compte(c, "ref_flow_statuses"), 1)
        self.assertEqual(self.compte(c, "ref_state"), 1)
        self.assertGreater(c.execute("SELECT loaded_at FROM flow.ref_state").fetchone()[0], premier)

    def test_un_chargement_refuse_garde_les_lignes_precedentes(self):
        c = self.conn()
        self.charger(c, reglages(3))
        refuse = {**reglages(3), "defect_types": ["t-un", "T-UN"]}
        with self.assertRaises(fr.ReferentielInvalide):
            self.charger(c, refuse)
        self.assertEqual([self.compte(c, t) for t in TABLES_DEFINITIONS], [3, 1, 2])
        self.assertEqual([self.compte(c, t) for t in TABLES_CYCLES], [0, 0, 0, 0])

    def test_le_role_des_vues_de_flux_ne_lit_pas_les_tables_de_definitions(self):
        c = self.conn()
        self.charger(c, reglages(2))
        for table in TABLES_DEFINITIONS:
            self.assertFalse(self.essaie(c, "pmzilla_flow_views", f"SELECT * FROM flow.{table}"), table)

    def test_un_cycle_present_refuse_le_chargement_sans_rien_ecrire_et_le_cycle_reste(self):
        c = self.conn()
        self.cycle(c)
        with self.assertRaises(fd.CyclesDejaCharges) as refus:
            self.charger(c, reglages(3))
        self.assertEqual(str(refus.exception), fd.MESSAGE_CYCLES_PRESENTS)
        self.assertEqual([self.compte(c, t) for t in TABLES_DEFINITIONS], [0, 0, 0])
        self.assertEqual(self.compte(c, "ref_state"), 0)
        self.assertEqual(c.execute("SELECT cycle_key FROM flow.ref_cycles").fetchall(), [("2099-C1",)])

    def test_la_garde_ne_depend_pas_de_la_ligne_d_etat(self):
        c = self.conn()
        self.charger(c, reglages(2))                      # écrit la ligne d'état : un second chargement n'est pas refusé
        self.charger(c, reglages(2))
        self.assertEqual(self.compte(c, "ref_flow_statuses"), 2)


if __name__ == "__main__":
    unittest.main()
