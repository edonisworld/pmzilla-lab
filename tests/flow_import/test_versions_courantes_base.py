"""Versions courantes sur la base jetable (change flow-version-share ; spec jira-flow-import « Current versions derived »). Sautée sans base
(bash tools/dbtest.sh flow_import), écrite pour être exécutée par l'auteur.

    bash tools/dbtest.sh flow_import

Le passage d'export est rejoué sans Jira (flow_raw.MagasinBase sous le rôle d'import), puis flow_raw.deriver dérive les lignes
vivantes de flow.issue_current_versions. Données inventées.
"""
import datetime as dt
import unittest

import db
import flow_raw
from test_derivation_base import MAINTENANT, aide, instantane


def avec_versions(cle, fix=(), affects=(), **valeurs):
    base = instantane(cle, **valeurs)
    base["current_versions"] = {"fix": list(fix), "affects": list(affects)}
    base["content_hash"] = flow_raw.empreinte(base)
    return base


class VersionsEnBase(aide.AvecBase):
    def setUp(self):
        aide.AvecBase.setUp(self)
        self.role = db.connect(self.url, password=aide.MOT_DE_PASSE)
        self.role.execute("SET ROLE pmzilla_flow")
        self.addCleanup(self.role.close)

    def exporter(self, *instantanes):
        flow_raw.MagasinBase(self.role).enregistrer(genre="export", nb_requetes=1, toutes=True, vus=[i["issue_key"] for i in instantanes],
                                                    instantanes={i["issue_key"]: i for i in instantanes})
        flow_raw.deriver(self.role, maintenant=MAINTENANT)

    def lignes(self, cle):
        self.conn.rollback()
        return self.conn.execute("SELECT kind, name FROM flow.issue_current_versions WHERE issue_key = %s ORDER BY kind, name", (cle,)).fetchall()

    def test_derivation_des_versions(self):
        self.exporter(avec_versions("PROJ-1", fix=["v2", "v1"], affects=["v0"]))
        self.assertEqual(self.lignes("PROJ-1"), [("affects", "v0"), ("fix", "v1"), ("fix", "v2")])

    def test_version_retiree_dans_jira(self):
        self.exporter(avec_versions("PROJ-1", fix=["v1", "v2"]))
        self.exporter(avec_versions("PROJ-1", fix=["v1"], updated_at=MAINTENANT))
        self.assertEqual(self.lignes("PROJ-1"), [("fix", "v1")])

    def test_instantane_ancien_laisse_les_lignes(self):
        self.exporter(avec_versions("PROJ-1", fix=["v1"]))
        self.exporter(instantane("PROJ-1", status="Done", updated_at=MAINTENANT))          # sans suivi des versions
        self.assertEqual(self.lignes("PROJ-1"), [("fix", "v1")])

    def attributs(self, cle):
        self.conn.rollback()
        return self.conn.execute("SELECT kind, name, release_date, released FROM flow.issue_current_versions WHERE issue_key = %s "
                                 "ORDER BY kind, name", (cle,)).fetchall()

    def avec_sortie(self, cle, release, **valeurs):
        base = avec_versions(cle, fix=list(release), **valeurs)
        base["current_versions"]["release"] = {nom: {"date": d, "released": s} for nom, (d, s) in release.items()}
        base["content_hash"] = flow_raw.empreinte(base)
        return base

    def test_date_et_drapeau_derives_du_dernier_instantane(self):
        self.exporter(self.avec_sortie("PROJ-1", {"v1": ("2029-07-14", True), "v2": (None, False)}))
        self.assertEqual(self.attributs("PROJ-1"), [("fix", "v1", dt.date(2029, 7, 14), True), ("fix", "v2", None, False)])

    def test_date_deplacee_dans_jira(self):
        self.exporter(self.avec_sortie("PROJ-1", {"v1": ("2029-07-14", False)}))
        self.exporter(self.avec_sortie("PROJ-1", {"v1": ("2029-08-01", False)}, updated_at=MAINTENANT))
        self.assertEqual(self.attributs("PROJ-1"), [("fix", "v1", dt.date(2029, 8, 1), False)])

    def test_instantane_sans_release_donne_des_attributs_nuls(self):
        self.exporter(self.avec_sortie("PROJ-1", {"v1": ("2029-07-14", True)}))
        self.exporter(avec_versions("PROJ-1", fix=["v1"], updated_at=MAINTENANT))
        self.assertEqual(self.attributs("PROJ-1"), [("fix", "v1", None, None)])

    def test_cascade_avec_le_ticket(self):
        self.exporter(avec_versions("PROJ-1", fix=["v1"]))
        self.role.execute("DELETE FROM flow.issues WHERE key = 'PROJ-1'")
        self.role.commit()
        self.assertEqual(self.lignes("PROJ-1"), [])


if __name__ == "__main__":
    unittest.main()
