"""Attributs de sortie des versions courantes dans l'export (change version-release-date, R-140 branche 2 ; spec jira-flow-export « Release
attributes of current versions », jira-flow-raw-layer « Snapshot keeps the release attributes »).

    bash tests/run_all.sh export_jira_api </dev/null

Faux serveur, faux magasin en mémoire et données inventées de test_export_jira_api.py. Aucune base, aucun Jira réel.
Les objets de version portent tous les attributs que Jira renvoie, chacun avec une valeur distinctive : seuls le nom, `releaseDate` et
`released` sont lus (design D1) ; aucune de ces valeurs n'est affichée.
"""
import copy
import unittest

from test_export_jira_api import Base, ex

import flow_raw  # noqa: E402  (tools/ est déjà sur le chemin d'import : test_export_jira_api l'y place)

NOM = "VersionSecreteOmega"
DATE = "2029-07-14"
AUTRES = ("IdentifiantDistinctif98765", "DescriptionDistinctive", "2031-02-03", "UserDateDistinctive", "http://zz.example/AdresseDistinctive",
          "ProjetDistinctif424242")


def objet(nom=NOM, date=DATE, sortie=True, **autres):
    version = {"self": AUTRES[4], "id": AUTRES[0], "description": AUTRES[1], "archived": True, "startDate": AUTRES[2],
               "userReleaseDate": AUTRES[3], "projectId": 424242, "name": nom}
    if date is not None:
        version["releaseDate"] = date
    if sortie is not None:
        version["released"] = sortie
    version.update(autres)
    return version


class AttributsDeVersion(Base):
    def setUp(self):
        super().setUp()
        self.faux.tickets["ABC-1"]["fixVersions"] = [objet()]
        self.faux.tickets["ABC-1"]["versions"] = []

    def champs_demandes(self):
        return [r["fields"] for r in self.faux.requetes]

    def test_le_nom_la_date_et_le_drapeau_seuls_sont_gardes(self):
        courantes = self.exporter()["ABC-1"]["current_versions"]
        self.assertEqual(courantes, {"fix": [NOM], "affects": [], "release": {NOM: {"date": DATE, "released": True}}})

    def test_aucune_autre_valeur_dans_l_instantane(self):
        self.exporter()
        texte = repr(self.magasin.instantanes)
        for valeur in AUTRES:
            self.assertNotIn(valeur, texte)
        self.assertNotIn("424242", texte)

    def test_la_version_d_affects_est_lue_de_la_meme_facon(self):
        self.faux.tickets["ABC-1"]["fixVersions"] = []
        self.faux.tickets["ABC-1"]["versions"] = [objet(date="2030-01-02", sortie=False)]
        courantes = self.exporter()["ABC-1"]["current_versions"]
        self.assertEqual(courantes["release"], {NOM: {"date": "2030-01-02", "released": False}})
        self.assertEqual((courantes["fix"], courantes["affects"]), ([], [NOM]))

    def test_champs_demandes_et_nombre_de_requetes_inchanges(self):
        for ticket in self.faux.tickets.values():              # d'abord des objets réduits au nom : l'export d'avant ce change
            ticket["fixVersions"] = [{"name": NOM}] if ticket is self.faux.tickets["ABC-1"] else []
        self.exporter()
        avant = copy.deepcopy(self.champs_demandes())
        self.faux.requetes.clear()
        self.faux.tickets["ABC-1"]["fixVersions"] = [objet()]
        self.exporter()
        self.assertEqual(self.champs_demandes(), avant)
        self.assertEqual(len(self.faux.requetes), len(avant))
        for champs in self.champs_demandes():
            self.assertLessEqual(set(ex.CHAMPS_DE_BASE), set(champs))
            self.assertNotIn("fixVersions.releaseDate", champs)          # aucune expansion ni sous-champ

    def test_aucune_valeur_dans_la_sortie(self):
        code, sortie = self.lancer("export")
        self.assertEqual(code, 0, sortie)
        for valeur in (NOM, DATE, "VersionSecrete", "True", "False", "true", "false") + AUTRES:          # le drapeau, sous toutes ses formes
            self.assertNotIn(valeur, sortie)

    def test_aucune_valeur_dans_la_sortie_en_cas_d_erreur(self):
        self.magasin.echec_ecriture = RuntimeError(f"{NOM} {DATE} released=True")
        code, sortie = self.lancer("export")
        self.assertEqual(code, 1)
        for valeur in (NOM, DATE, "released=True", "True", "False", "true", "false") + AUTRES:
            self.assertNotIn(valeur, sortie)


class SansDateEtEmpreinte(Base):
    def setUp(self):
        super().setUp()
        for cle in ("ABC-1", "ABC-2", "ABC-3"):
            self.faux.tickets[cle]["fixVersions"] = [{"name": NOM}]

    def test_version_sans_date_date_nulle(self):
        courantes = self.exporter()["ABC-1"]["current_versions"]
        self.assertEqual(courantes["release"], {NOM: {"date": None, "released": None}})

    def test_date_absente_et_drapeau_present(self):
        self.faux.tickets["ABC-1"]["fixVersions"] = [objet(date=None, sortie=False)]
        self.assertEqual(self.exporter()["ABC-1"]["current_versions"]["release"], {NOM: {"date": None, "released": False}})

    def test_valeurs_de_forme_inattendue_donnent_null(self):
        self.faux.tickets["ABC-1"]["fixVersions"] = [objet(date="pas une date", sortie="oui")]
        self.assertEqual(self.exporter()["ABC-1"]["current_versions"]["release"], {NOM: {"date": None, "released": None}})
        self.faux.tickets["ABC-2"]["fixVersions"] = [objet(date=20290714, sortie=1)]
        self.assertEqual(self.exporter()["ABC-2"]["current_versions"]["release"], {NOM: {"date": None, "released": None}})

    def test_ticket_sans_version_meme_empreinte_qu_avant(self):
        instantane = self.exporter()["ABC-9"]
        self.assertEqual(instantane["current_versions"], {"fix": [], "affects": [], "release": {}})
        self.assertEqual(instantane["content_hash"], flow_raw.empreinte({**instantane, "current_versions": None}))

    def test_date_posee_sur_trois_tickets_trois_instantanes_et_aucun_ancien_modifie(self):
        self.exporter()
        avant = copy.deepcopy(self.magasin.instantanes)
        for cle in ("ABC-1", "ABC-2", "ABC-3"):
            self.faux.tickets[cle]["fixVersions"] = [objet()]          # même date de mise à jour : seul le contenu change
        self.exporter()
        apres = self.magasin.instantanes
        self.assertEqual(len(apres), len(avant) + 3)
        self.assertEqual(apres[:len(avant)], avant)                   # aucun instantané existant n'est touché
        self.assertEqual(sorted(i["issue_key"] for i in apres[len(avant):]), ["ABC-1", "ABC-2", "ABC-3"])

    def test_date_deplacee_ecrit_un_instantane_par_ticket(self):
        for cle in ("ABC-1", "ABC-2", "ABC-3"):
            self.faux.tickets[cle]["fixVersions"] = [objet()]
        self.exporter()
        total = len(self.magasin.instantanes)
        for cle in ("ABC-1", "ABC-2", "ABC-3"):
            self.faux.tickets[cle]["fixVersions"] = [objet(date="2029-08-01")]
        self.exporter()
        self.assertEqual(len(self.magasin.instantanes), total + 3)

    def test_deuxieme_export_identique_sans_nouvel_instantane(self):
        for cle in ("ABC-1", "ABC-2", "ABC-3"):
            self.faux.tickets[cle]["fixVersions"] = [objet()]
        self.exporter()
        total = len(self.magasin.instantanes)
        self.exporter()
        self.assertEqual(len(self.magasin.instantanes), total)

    def test_premier_export_apres_le_change_ecrit_un_instantane_par_ticket_avec_version(self):
        """Le dernier instantané d'avant le change porte les noms sans clé `release` : l'empreinte d'alors diffère de l'actuelle."""
        instantane = self.exporter()["ABC-1"]
        ancien = {**instantane, "current_versions": {"fix": [NOM], "affects": []}}
        self.assertNotEqual(flow_raw.empreinte(ancien), instantane["content_hash"])


if __name__ == "__main__":
    unittest.main()
