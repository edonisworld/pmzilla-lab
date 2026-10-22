"""
Tests de la garde des tests avec base (test-speed-2, D1) : tests/db/test_db.py décide si une base peut être utilisée.

    uv run --with "psycopg[binary]" python -m unittest discover -s tests/db -v

Sans base, sans réseau : la connexion est un double qui fait échouer le test s'il est appelé là où aucune connexion ne doit avoir lieu.
La garde ne rend vrai que si DBTEST_PORT (posé par tools/dbtest.sh) et le port de connexion (PMZILLA_LAB_DB_PORT) sont de forme
décimale simple (test-db-guards, D1), si le repère n'est pas 5432 et égale en nombre le port de connexion, si l'adresse éventuelle vise
ce port, si le mot de passe est non vide et si la connexion réussit.
"""
import unittest
from unittest import mock

import test_db as base          # noqa: E402  (même dossier)
from test_db import db          # noqa: E402

FAUX_MOT_DE_PASSE = "faux-mot-" + "de-passe"   # fabriqué à l'exécution : aucun littéral pour la garde des secrets
BON = {"DBTEST_PORT": "55432", "PMZILLA_LAB_DB_PORT": "55432", "PMZILLA_LAB_DB_PASSWORD": FAUX_MOT_DE_PASSE}


class Connexion:
    """Double de db.connect : note les appels ; échoue ou lève à la demande."""

    def __init__(self, leve=None):
        self.appels = []
        self.leve = leve

    def __call__(self, *args, **kwargs):
        self.appels.append((args, kwargs))
        if self.leve:
            raise self.leve
        return mock.Mock()


class GardeBase(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.object(db, "psycopg", object())   # psycopg « importable » pour tous les cas, sauf celui qui le retire
        patch.start()
        self.addCleanup(patch.stop)

    def garde(self, env, connexion=None):
        self.connexion = connexion or Connexion()
        return base.base_jetable_disponible(env, self.connexion)

    def refuse_sans_connexion(self, env, pourquoi):
        with self.subTest(pourquoi=pourquoi):
            self.assertFalse(self.garde(env), pourquoi)
            self.assertEqual(self.connexion.appels, [], f"{pourquoi} : aucune connexion ne doit être tentée")

    def test_vraie_avec_repere_port_et_mot_de_passe_et_connexion_reussie(self):
        self.assertTrue(self.garde(BON))
        self.assertEqual(len(self.connexion.appels), 1)
        self.assertEqual(self.connexion.appels[0][1].get("timeout"), 2)

    def test_vraie_avec_une_adresse_qui_vise_le_port_du_repere(self):
        env = dict(BON, PMZILLA_LAB_DB_URL="postgresql://postgres@127.0.0.1:55432/pmzilla")
        self.assertTrue(self.garde(env))

    def test_fausse_sans_repere(self):
        sans = {k: v for k, v in BON.items() if k != "DBTEST_PORT"}
        self.refuse_sans_connexion(sans, "repère absent")
        self.refuse_sans_connexion(dict(BON, DBTEST_PORT=""), "repère vide")

    def test_fausse_si_le_repere_est_le_port_standard_ou_n_est_pas_un_nombre(self):
        self.refuse_sans_connexion(dict(BON, DBTEST_PORT="5432", PMZILLA_LAB_DB_PORT="5432"), "port standard")
        self.refuse_sans_connexion(dict(BON, DBTEST_PORT="abc", PMZILLA_LAB_DB_PORT="abc"), "repère non numérique")
        self.refuse_sans_connexion(dict(BON, DBTEST_PORT="55432 ", PMZILLA_LAB_DB_PORT="55432 "), "repère avec espace")

    def test_fausse_si_le_port_de_connexion_differe_du_repere(self):
        self.refuse_sans_connexion(dict(BON, PMZILLA_LAB_DB_PORT="55433"), "autre port")
        self.refuse_sans_connexion(dict(BON, PMZILLA_LAB_DB_PORT="5432"), "port standard de connexion")
        sans = {k: v for k, v in BON.items() if k != "PMZILLA_LAB_DB_PORT"}
        self.refuse_sans_connexion(sans, "port de connexion absent")

    def test_fausse_si_l_adresse_vise_un_autre_port_ou_le_port_standard(self):
        self.refuse_sans_connexion(dict(BON, PMZILLA_LAB_DB_URL="postgresql://postgres@127.0.0.1:5432/pmzilla"), "adresse sur 5432")
        self.refuse_sans_connexion(dict(BON, PMZILLA_LAB_DB_URL="postgresql://postgres@127.0.0.1:55433/pmzilla"), "adresse sur un autre port")
        self.refuse_sans_connexion(dict(BON, PMZILLA_LAB_DB_URL="postgresql://postgres@127.0.0.1/pmzilla"), "adresse sans port")

    def test_fausse_si_une_forme_de_port_n_est_pas_la_forme_decimale_simple(self):
        # test-db-guards, D1 : chiffres ASCII seulement, sans signe, sans espace, sans zéro en tête, de 1 à 65535
        for forme in ("05432", "+55432", "-55432", " 55432", "55432 ", "55432\n", "65536", "99999", "0", "00", "٥٥٤٣٢", "5e4"):
            self.refuse_sans_connexion(dict(BON, DBTEST_PORT=forme, PMZILLA_LAB_DB_PORT=forme), f"repère {forme!r}")
            self.refuse_sans_connexion(dict(BON, PMZILLA_LAB_DB_PORT=forme), f"port de connexion {forme!r}")
        self.refuse_sans_connexion(dict(BON, DBTEST_PORT="05432", PMZILLA_LAB_DB_PORT="5432"), "repère 05432 contre 5432")

    def test_fausse_si_le_port_de_l_adresse_differe_du_repere_comme_nombre(self):
        for adresse in ("postgresql://postgres@127.0.0.1:55433/pmzilla", "postgresql://postgres@127.0.0.1:5432/pmzilla",
                        "postgresql://postgres@127.0.0.1:0/pmzilla", "postgresql://postgres@127.0.0.1:65536/pmzilla"):
            self.refuse_sans_connexion(dict(BON, PMZILLA_LAB_DB_URL=adresse), adresse)

    def test_vraie_pour_les_bornes_de_la_forme_simple(self):
        for port in ("1", "65535"):
            with self.subTest(port=port):
                self.assertTrue(self.garde(dict(BON, DBTEST_PORT=port, PMZILLA_LAB_DB_PORT=port)))

    def test_fausse_si_le_mot_de_passe_est_vide_ou_absent(self):
        self.refuse_sans_connexion(dict(BON, PMZILLA_LAB_DB_PASSWORD=""), "mot de passe vide")
        sans = {k: v for k, v in BON.items() if k != "PMZILLA_LAB_DB_PASSWORD"}
        self.refuse_sans_connexion(sans, "mot de passe absent")

    def test_fausse_sans_psycopg(self):
        with mock.patch.object(db, "psycopg", None):
            self.refuse_sans_connexion(BON, "psycopg absent")

    def test_fausse_si_la_connexion_echoue(self):
        self.assertFalse(self.garde(BON, Connexion(leve=db.ErreurBase("refusée"))))
        self.assertEqual(len(self.connexion.appels), 1)

    def test_message_de_saut_de_la_decision_d29(self):
        self.assertEqual(base.MESSAGE_SAUT, "base jetable absente (lancer bash tools/dbtest.sh)")


if __name__ == "__main__":
    unittest.main()
