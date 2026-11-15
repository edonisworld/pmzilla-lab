"""Versions courantes dans la couche brute et leur dérivation (change flow-version-share ; spec jira-flow-import « Current versions
derived », jira-flow-raw-layer « Snapshot only when a ticket changes »), partie sans base : fonctions pures et fausse connexion de
test_reconstruction.py. Les scénarios sur la base jetable sont dans test_versions_courantes_base.py (sautés sans elle).

    uv run --with pyyaml --with "psycopg[binary]" python -m unittest discover -s tests/flow_import -v

Noms de version inventés et distinctifs ; aucun ne doit apparaître dans une sortie.
"""
import datetime as dt
import unittest

import flow_raw
from test_reconstruction import FausseConnexion, instantane, lancer, vivant

SECRET = "VersionSecreteDelta"


DATE_SECRETE = "2029-07-14"          # date de sortie distinctive : elle ne doit apparaître dans aucune sortie


def cv(fix=(), affects=(), release=None):
    """Versions courantes d'un instantané ; `release` : {nom: (date ISO ou None, drapeau ou None)} (change version-release-date)."""
    courantes = {"fix": list(fix), "affects": list(affects)}
    if release is not None:
        courantes["release"] = {nom: {"date": date, "released": sortie} for nom, (date, sortie) in release.items()}
    return courantes


class Empreinte(unittest.TestCase):
    def test_sans_nom_meme_empreinte_que_sans_suivi(self):
        base = instantane()
        self.assertEqual(flow_raw.empreinte({**base, "current_versions": cv()}), flow_raw.empreinte(base))
        self.assertEqual(flow_raw.empreinte({**base, "current_versions": None}), flow_raw.empreinte(base))

    def test_un_nom_change_l_empreinte_selon_le_genre(self):
        base = instantane()
        fix = flow_raw.empreinte({**base, "current_versions": cv(fix=["v1"])})
        affects = flow_raw.empreinte({**base, "current_versions": cv(affects=["v1"])})
        self.assertEqual(len({flow_raw.empreinte(base), fix, affects}), 3)

    def test_l_ordre_est_sans_effet(self):
        base = instantane()
        self.assertEqual(flow_raw.empreinte({**base, "current_versions": cv(fix=["a", "b"])}),
                         flow_raw.empreinte({**base, "current_versions": cv(fix=["b", "a"])}))


class ChampsDifferents(unittest.TestCase):
    def test_versions_comparees_quand_suivies(self):
        snap = instantane(current_versions=cv(fix=["v1"], affects=["v0"]))
        self.assertEqual(flow_raw.champs_differents(snap, vivant(versions={("fix", "v1"), ("affects", "v0")})), [])
        self.assertEqual(flow_raw.champs_differents(snap, vivant(versions={("fix", "v1")})), ["versions"])
        self.assertEqual(flow_raw.champs_differents(snap, vivant(versions=set())), ["versions"])

    def test_snapshot_non_suivi_ne_compare_rien(self):
        self.assertEqual(flow_raw.champs_differents(instantane(current_versions=None), vivant(versions={("fix", "v1")})), [])
        self.assertEqual(flow_raw.champs_differents(instantane(), vivant(versions={("fix", "v1")})), [])

    def test_nom_neutre_dans_la_liste_des_champs(self):
        self.assertIn("versions", flow_raw.CHAMPS)


class EmpreinteDeSortie(unittest.TestCase):
    """Design D3 : la clé `release` entre dans l'empreinte dès qu'il y a un nom de version."""

    def hash(self, **sortie):
        return flow_raw.empreinte({**instantane(), "current_versions": cv(fix=["v1"], release=sortie.get("release"))})

    def test_date_ou_drapeau_change_l_empreinte(self):
        sans, avec = self.hash(), self.hash(release={"v1": (DATE_SECRETE, None)})
        autre_date = self.hash(release={"v1": ("2029-08-01", None)})
        drapeau = self.hash(release={"v1": (DATE_SECRETE, True)})
        self.assertEqual(len({sans, avec, autre_date, drapeau}), 4)

    def test_meme_contenu_meme_empreinte(self):
        self.assertEqual(self.hash(release={"v1": (DATE_SECRETE, True)}), self.hash(release={"v1": (DATE_SECRETE, True)}))

    def test_sans_nom_de_version_les_attributs_ne_comptent_pas(self):
        base = instantane()
        self.assertEqual(flow_raw.empreinte({**base, "current_versions": {"fix": [], "affects": [], "release": {}}}), flow_raw.empreinte(base))


class DifferenceDeSortie(unittest.TestCase):
    def test_une_date_ou_un_drapeau_different_est_une_difference_de_versions(self):
        snap = instantane(current_versions=cv(fix=["v1"], release={"v1": (DATE_SECRETE, True)}))
        self.assertEqual(flow_raw.champs_differents(snap, vivant(versions={("fix", "v1", dt.date(2029, 7, 14), True)})), [])
        self.assertEqual(flow_raw.champs_differents(snap, vivant(versions={("fix", "v1", dt.date(2029, 8, 1), True)})), ["versions"])
        self.assertEqual(flow_raw.champs_differents(snap, vivant(versions={("fix", "v1", dt.date(2029, 7, 14), False)})), ["versions"])
        self.assertEqual(flow_raw.champs_differents(snap, vivant(versions={("fix", "v1")})), ["versions"])       # lignes sans attributs

    def test_un_instantane_sans_la_cle_release_donne_des_attributs_nuls(self):
        snap = instantane(current_versions=cv(fix=["v1"]))
        self.assertEqual(flow_raw.champs_differents(snap, vivant(versions={("fix", "v1")})), [])
        self.assertEqual(flow_raw.champs_differents(snap, vivant(versions={("fix", "v1", dt.date(2029, 7, 14), None)})), ["versions"])


class Derivation(unittest.TestCase):
    def appliquer(self, instantanes, vivants, versions_instantanes):
        connexion = FausseConnexion(instantanes, vivants)
        connexion.versions_instantanes = versions_instantanes
        code, sortie, erreur = lancer("--rebuild", "--apply", "--language", "en", connexion=connexion)
        self.assertEqual(code, 0, erreur)
        return connexion, sortie

    def ecritures_de_versions(self, connexion):
        return [(s, p) for s, p in connexion.ecritures if "flow.issue_current_versions" in s]

    def test_derivation_des_versions(self):
        snap = instantane("PROJ-1", current_versions=cv(fix=[SECRET, "autre"], affects=["aff"]))
        connexion, sortie = self.appliquer([snap], [vivant("PROJ-1", versions={("fix", "ancienne")})],
                                           {"PROJ-1": snap["current_versions"]})
        ecrites = self.ecritures_de_versions(connexion)
        self.assertEqual(len([e for e in ecrites if e[0].startswith("DELETE")]), 1)
        inserees = sorted(p[1:] for s, p in ecrites if s.startswith("INSERT"))
        self.assertEqual(inserees, sorted([("affects", "aff", None, None), ("fix", "autre", None, None), ("fix", SECRET, None, None)]))
        self.assertIn("rebuild: versions differs: 1", sortie)

    def test_derivation_de_la_date_et_du_drapeau(self):
        snap = instantane("PROJ-1", current_versions=cv(fix=[SECRET, "autre"], affects=[SECRET],
                                                        release={SECRET: (DATE_SECRETE, True), "autre": (None, False)}))
        connexion, sortie = self.appliquer([snap], [vivant("PROJ-1", versions={("fix", SECRET, None, None)})],
                                           {"PROJ-1": snap["current_versions"]})
        inserees = sorted(p[1:] for s, p in self.ecritures_de_versions(connexion) if s.startswith("INSERT"))
        self.assertEqual(inserees, sorted([("affects", SECRET, dt.date(2029, 7, 14), True), ("fix", "autre", None, False),
                                           ("fix", SECRET, dt.date(2029, 7, 14), True)], key=str))
        self.assertIn("rebuild: versions differs: 1", sortie)

    def test_un_changement_de_date_est_compte_comme_une_difference_de_versions(self):
        snap = instantane("PROJ-1", current_versions=cv(fix=["v1"], release={"v1": ("2029-08-01", True)}))
        connexion, sortie = self.appliquer([snap], [vivant("PROJ-1", versions={("fix", "v1", dt.date(2029, 7, 14), True)})],
                                           {"PROJ-1": snap["current_versions"]})
        self.assertIn("rebuild: versions differs: 1", sortie)
        self.assertEqual([p for s, p in self.ecritures_de_versions(connexion) if s.startswith("INSERT")],
                         [("PROJ-1", "fix", "v1", dt.date(2029, 8, 1), True)])

    def test_un_instantane_sans_release_donne_des_attributs_nuls(self):
        snap = instantane("PROJ-1", current_versions=cv(fix=["v1"]))
        connexion, _ = self.appliquer([snap], [vivant("PROJ-1", versions={("fix", "v1", dt.date(2029, 7, 14), True)})],
                                      {"PROJ-1": snap["current_versions"]})
        self.assertEqual([p for s, p in self.ecritures_de_versions(connexion) if s.startswith("INSERT")],
                         [("PROJ-1", "fix", "v1", None, None)])

    def test_la_date_n_apparait_dans_aucune_sortie(self):
        snap = instantane("PROJ-1", current_versions=cv(fix=[SECRET], release={SECRET: (DATE_SECRETE, True)}))
        _, sortie = self.appliquer([snap], [vivant("PROJ-1", versions=set())], {"PROJ-1": snap["current_versions"]})
        for valeur in (DATE_SECRETE, "2029", SECRET, "True"):
            self.assertNotIn(valeur, sortie)

    def test_instantane_ancien_laisse_les_lignes(self):
        snap = instantane("PROJ-1")                                     # current_versions absent : non suivi
        connexion, sortie = self.appliquer([snap], [vivant("PROJ-1", versions={("fix", "v1")})], {})
        self.assertEqual(self.ecritures_de_versions(connexion), [])
        self.assertIn("0 would change", sortie)

    def test_ticket_nouveau_ecrit_ses_versions(self):
        snap = instantane("PROJ-1", current_versions=cv(fix=["v1"]))
        connexion, _ = self.appliquer([snap], [], {"PROJ-1": snap["current_versions"]})
        self.assertEqual([p for s, p in self.ecritures_de_versions(connexion) if s.startswith("INSERT")], [("PROJ-1", "fix", "v1", None, None)])

    def test_aucun_nom_dans_la_sortie(self):
        snap = instantane("PROJ-1", current_versions=cv(fix=[SECRET]))
        _, sortie = self.appliquer([snap], [vivant("PROJ-1", versions=set())], {"PROJ-1": snap["current_versions"]})
        self.assertNotIn(SECRET, sortie)
        self.assertNotIn("PROJ-", sortie)


if __name__ == "__main__":
    unittest.main()
