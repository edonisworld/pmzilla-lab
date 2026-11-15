"""Versions courantes d'un ticket dans l'export (change flow-version-share, spec jira-flow-export « Current versions stored per ticket »,
« Version names never printed », « No sensitive field requested or printed »; jira-flow-raw-layer « Snapshot only when a ticket changes »).

    bash tests/run_all.sh export_jira_api </dev/null

Faux serveur, faux magasin en mémoire et données inventées de test_export_jira_api.py. Aucune base, aucun Jira réel.
"""
import unittest

from test_export_jira_api import Base

import flow_raw  # noqa: E402  (tools/ est déjà sur le chemin d'import : test_export_jira_api l'y place)

SECRET_A, SECRET_B, SECRET_C = "VersionSecreteAlpha", "VersionSecreteBeta", "VersionSecreteGamma"


def noms(*valeurs):
    return [{"id": str(i), "name": v, "released": False} for i, v in enumerate(valeurs, 1)]


def seulement_les_noms(courantes):
    """Les deux listes de noms : la clé `release` a ses propres tests (test_attributs_de_version.py, change version-release-date)."""
    return {genre: courantes[genre] for genre in ("fix", "affects")}


class VersionsCourantes(Base):
    def setUp(self):
        super().setUp()
        self.faux.tickets["ABC-1"]["fixVersions"] = noms(SECRET_A, SECRET_B)
        self.faux.tickets["ABC-1"]["versions"] = noms(SECRET_C)

    def champs_demandes(self):
        return {f for r in self.faux.requetes for f in r["fields"]}

    def test_champs_demandes_avec_les_deux_champs_de_version(self):
        self.exporter()
        demandes = self.champs_demandes()
        self.assertLessEqual({"fixVersions", "versions"}, demandes)
        self.assertFalse({"labels", "summary", "description", "assignee", "reporter", "creator", "comment"} & demandes)

    def test_les_versions_courantes_sont_dans_l_instantane(self):
        instantanes = self.exporter()
        self.assertEqual(seulement_les_noms(instantanes["ABC-1"]["current_versions"]), {"fix": [SECRET_A, SECRET_B], "affects": [SECRET_C]})

    def test_ticket_sans_version_suivi_sans_nom(self):
        instantanes = self.exporter()
        self.assertEqual(seulement_les_noms(instantanes["ABC-2"]["current_versions"]), {"fix": [], "affects": []})

    def test_nom_vide_ou_repete_ignore(self):
        self.faux.tickets["ABC-3"]["fixVersions"] = [{"name": " "}, {"name": SECRET_A}, {"name": SECRET_A}, {}]
        instantanes = self.exporter()
        self.assertEqual(seulement_les_noms(instantanes["ABC-3"]["current_versions"]), {"fix": [SECRET_A], "affects": []})

    def test_aucun_nom_de_version_dans_la_sortie(self):
        code, sortie = self.lancer("export")
        self.assertEqual(code, 0, sortie)
        for secret in (SECRET_A, SECRET_B, SECRET_C):
            self.assertNotIn(secret, sortie)

    def test_aucun_nom_de_version_dans_la_sortie_en_cas_d_erreur(self):
        self.magasin.echec_ecriture = RuntimeError(SECRET_A)
        code, sortie = self.lancer("export")
        self.assertEqual(code, 1)
        self.assertNotIn(SECRET_A, sortie)

    def test_sans_version_meme_empreinte_qu_avant(self):
        instantane = self.exporter()["ABC-2"]
        ancien = {**instantane, "current_versions": None}
        self.assertEqual(instantane["content_hash"], flow_raw.empreinte(ancien))

    def test_avec_version_empreinte_differente(self):
        instantane = self.exporter()["ABC-1"]
        self.assertNotEqual(instantane["content_hash"], flow_raw.empreinte({**instantane, "current_versions": None}))

    def test_version_ajoutee_ecrit_un_instantane(self):
        self.exporter()
        avant = len(self.magasin.instantanes_de("ABC-2"))
        self.faux.tickets["ABC-2"]["fixVersions"] = noms(SECRET_A)         # même date de mise à jour : seul le contenu change
        self.exporter()
        self.assertEqual(len(self.magasin.instantanes_de("ABC-2")), avant + 1)
        self.assertEqual(seulement_les_noms(self.magasin.dernier("ABC-2")["current_versions"]), {"fix": [SECRET_A], "affects": []})

    def test_deuxieme_export_identique_sans_nouvel_instantane(self):
        self.exporter()
        total = len(self.magasin.instantanes)
        self.exporter()
        self.assertEqual(len(self.magasin.instantanes), total)

    def test_ordre_des_versions_sans_effet_sur_l_empreinte(self):
        self.exporter()
        total = len(self.magasin.instantanes)
        self.faux.tickets["ABC-1"]["fixVersions"] = noms(SECRET_B, SECRET_A)
        self.exporter()
        self.assertEqual(len(self.magasin.instantanes), total)


if __name__ == "__main__":
    unittest.main()
