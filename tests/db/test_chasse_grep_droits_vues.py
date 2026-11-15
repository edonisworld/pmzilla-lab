"""Constat A-80 de l'audit #629 (reproduction G-04 de la passe git grep, audit-kraken/lots/grep.md, moyenne, L3) : le rôle sous lequel Mothra lit
les vues ne doit lire que les vues du contrat de Mothra (contrats/vues.json) plus la vue interne que le serveur lit sans la servir
(v_team_weekly_resolved), et toutes.

Historique : la reproduction G-04 est née rouge sur la branche jetable chasse/kraken, contre le rôle `pmzilla_flow_views`, partagé entre Mothra et
`tools/flow_views.py` (il lit plus de vues que le contrat n'en sert). La décision R-20261107-26, décision 3 (a), a donné à Mothra un rôle propre,
`pmzilla_mothra_views` (migration 0039) : ce test porte désormais sur ce rôle, et reste volontairement muet sur `pmzilla_flow_views`, qui garde
ses droits pour `tools/flow_views.py` (ses droits sont fixés par tests/db/test_matrice_droits.py).

Remplace : rien (la reproduction G-04 de la branche jetable, qui ne survit pas à sa suppression).
Condition de retrait : permanent, tant que Mothra a un rôle de lecture des vues propre. La source de la liste est contrats/vues.json ; ce test
détecte un écart entre le contrat et les droits réels, dans les deux sens (vue en trop, vue manquante).

Partie avec base : à lancer par le dbtest de l'auteur, sur la base jetable, données inventées (aucune ligne n'est lue ni écrite, seuls les droits
sont interrogés). Sans base jetable, le test est sauté par la garde de test_db.
"""
import json
import unittest
from pathlib import Path

import test_db as base          # noqa: E402,F401
import test_flow_schema as fs   # noqa: E402

CONTRAT = Path(__file__).resolve().parents[2] / "contrats" / "vues.json"
ROLE = "pmzilla_mothra_views"


# Vue interne que le serveur lit sans la servir (constante VUE_HEBDO de mothra/server/src/service.ts : relation T3 de v_team_lead_time_throughput).
VUES_INTERNES = {"v_team_weekly_resolved"}


def vues_du_contrat() -> set:
    return {v["name"] for v in json.loads(CONTRAT.read_text(encoding="utf-8"))["views"] if v.get("roleKind") == "flow"}


def vues_attendues() -> set:
    return vues_du_contrat() | VUES_INTERNES


class ChasseGrepDroitsVues(unittest.TestCase):
    setUp = fs.SchemaFlow.setUp
    _supprimer = fs.SchemaFlow._supprimer
    conn = fs.SchemaFlow.conn
    essaie = fs.SchemaFlow.essaie

    def vues_lues(self) -> set:
        c = self.conn()
        lignes = c.execute(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'flow' AND c.relkind IN ('v', 'm') AND has_table_privilege(%s, c.oid, 'SELECT')", (ROLE,)).fetchall()
        return {ligne[0] for ligne in lignes}

    def test_G_04_le_role_de_mothra_ne_lit_que_les_vues_du_contrat_et_la_vue_interne(self):
        en_trop = sorted(self.vues_lues() - vues_attendues())
        self.assertEqual(en_trop, [], f"{ROLE} lit {len(en_trop)} vue(s) absente(s) du contrat de Mothra et de ses vues internes")

    def test_G_04_le_role_de_mothra_lit_toutes_les_vues_du_contrat_et_la_vue_interne(self):
        manquantes = sorted(vues_attendues() - self.vues_lues())
        self.assertEqual(manquantes, [], f"{ROLE} ne lit pas {len(manquantes)} vue(s) du contrat de Mothra ou de ses vues internes")

    def test_G_04_le_role_de_mothra_ne_lit_aucune_table_du_schema_flow(self):
        c = self.conn()
        lignes = c.execute(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'flow' AND c.relkind IN ('r', 'p', 'f') AND has_table_privilege(%s, c.oid, 'SELECT')", (ROLE,)).fetchall()
        self.assertEqual(sorted(ligne[0] for ligne in lignes), [])


if __name__ == "__main__":
    unittest.main()
