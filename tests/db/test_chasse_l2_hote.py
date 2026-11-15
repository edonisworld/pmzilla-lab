"""Reproduction du constat L2 sur tools/db.py (audit-kraken/lots/L2-L4.md, partie L2, haute) : l'hôte de PMZILLA_LAB_DB_URL n'est pas contrôlé.

Test de l'audit #629, groupe O4, attendu vert. Aucune base, aucun réseau : psycopg est remplacé par un faux qui
enregistre ses appels. Valeurs fictives seulement.
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import db  # noqa: E402

HOTES_DISTANTS = (
    "postgresql://postgres@db.exemple.invalid:5432/pmzilla",
    "postgresql://postgres@192.0.2.10:5432/pmzilla",
    "postgresql://postgres@/pmzilla?host=db.exemple.invalid",
)


class FauxPsycopg:
    class Error(Exception):
        pass

    def __init__(self):
        self.appels = []

    def connect(self, adresse, **options):
        self.appels.append((adresse, options))
        raise self.Error("faux serveur : arrêt après enregistrement")


class ChasseL2Hote(unittest.TestCase):
    def test_L2_01_host_distant_refuse_par_verifier_url(self):
        for url in HOTES_DISTANTS:
            with self.subTest(url=url):
                with self.assertRaises(db.ErreurBase):
                    db.verifier_url(url)

    def test_L2_01_mot_de_passe_jamais_envoye_a_un_host_distant(self):
        for url in HOTES_DISTANTS:
            with self.subTest(url=url):
                faux = FauxPsycopg()
                with mock.patch.object(db, "psycopg", faux):
                    try:
                        db.connect(url, password="mot-de-passe-fictif")
                    except db.ErreurBase:
                        pass
                self.assertEqual([a for a in faux.appels if a[1].get("password")], [], "le mot de passe a été passé à un hôte distant")

    def test_L2_01_connexion_locale_exige_scram(self):
        faux = FauxPsycopg()
        with mock.patch.object(db, "psycopg", faux):
            try:
                db.connect("postgresql://postgres@127.0.0.1:5432/pmzilla", password="mot-de-passe-fictif")
            except db.ErreurBase:
                pass
        self.assertTrue(faux.appels, "aucun appel enregistré")
        options = faux.appels[0][1]
        adresse = faux.appels[0][0]
        self.assertTrue(options.get("require_auth") == "scram-sha-256" or "require_auth=scram-sha-256" in adresse)


# Contournements du contrôle de l'hôte (revue Opus du commit f8cb0ee4, audit #629, groupe O4). Valeurs fictives seulement.
# Chaque voie : verifier_url refuse, et connect n'appelle jamais psycopg (donc n'envoie aucun mot de passe).
SECRET_FICTIF = "secret-fictif-7d41"
ADRESSE_HORS_FORME = (
    f"host=db.exemple.invalid dbname=pmzilla user=postgres password={SECRET_FICTIF}",     # forme clé=valeur, mot de passe compris
    "host=db.exemple.invalid dbname=pmzilla",                                             # forme clé=valeur, hôte distant
    "host=127.0.0.1 dbname=pmzilla",                                                      # forme clé=valeur, hôte local : refusée aussi
    "  postgresql://postgres@127.0.0.1:5432/pmzilla",                                     # espace en tête : libpq la lit en clé=valeur
    "http://postgres@127.0.0.1:5432/pmzilla",
)
ADRESSE_PARAMETRES = (
    "postgresql://postgres@127.0.0.1:5432/pmzilla?service=distant",
    "postgresql://postgres@127.0.0.1:5432/pmzilla?SERVICE=distant",
    "postgresql://postgres@127.0.0.1:5432/pmzilla?hostaddr=203.0.113.5",
    "postgresql://postgres@127.0.0.1:5432/pmzilla?host=db.exemple.invalid",
    "postgresql://postgres@127.0.0.1:5432/pmzilla?hostaddr=127.0.0.1,203.0.113.5",
    "postgresql://127.0.0.1,db.exemple.invalid/pmzilla",                                  # hôtes multiples dans l'autorité
    "postgresql://postgres@db.exemple.invalid@127.0.0.1/pmzilla",                         # deux arobases dans l'autorité
    "postgres://postgres@db.exemple.invalid/pmzilla",                                     # l'autre préfixe accepté
)
ADRESSE_AVEC_MOT_DE_PASSE = (
    f"postgresql://postgres:{SECRET_FICTIF}@127.0.0.1:5432/pmzilla",
    f"postgres://postgres:{SECRET_FICTIF}@127.0.0.1:5432/pmzilla",
    f"postgresql://postgres@127.0.0.1:5432/pmzilla?password={SECRET_FICTIF}",
    f"postgresql://postgres@127.0.0.1:5432/pmzilla?PASSWORD={SECRET_FICTIF}",
    f"postgresql://postgres@127.0.0.1:5432/pmzilla?passfile=/chemin/{SECRET_FICTIF}",
    f"host=127.0.0.1 dbname=pmzilla password={SECRET_FICTIF}",
)
VARIABLES_REFUSEES = {"PGHOSTADDR": "203.0.113.77", "PGSERVICE": "service-fictif-9b2e", "PGSERVICEFILE": "/chemin/fictif-3c8a/pg_service.conf"}


class ChasseL2ContournementsHote(unittest.TestCase):
    def assertRefuseSansFuite(self, url, *valeurs):
        with self.assertRaises(db.ErreurBase) as refus:
            db.verifier_url(url)
        for valeur in (SECRET_FICTIF, *valeurs):
            self.assertNotIn(valeur, str(refus.exception))
        return str(refus.exception)

    def assertPsycopgJamaisAppele(self, url):
        faux = FauxPsycopg()
        with mock.patch.object(db, "psycopg", faux):
            with self.assertRaises(db.ErreurBase):
                db.connect(url, password=SECRET_FICTIF)
        self.assertEqual(faux.appels, [], "psycopg a été appelé (le mot de passe aurait pu partir)")

    def test_L2_hors_forme_adresse_qui_n_est_pas_une_url_postgres_refusee(self):
        for url in ADRESSE_HORS_FORME:
            with self.subTest(url=url):
                self.assertRefuseSansFuite(url)
                self.assertPsycopgJamaisAppele(url)

    def test_L2_parametres_service_hostaddr_host_distants_refuses(self):
        for url in ADRESSE_PARAMETRES:
            with self.subTest(url=url):
                self.assertRefuseSansFuite(url, "distant", "203.0.113.5")
                self.assertPsycopgJamaisAppele(url)

    def test_L2_parametre_host_ou_hostaddr_local_reste_accepte(self):
        for url in ("postgresql://postgres@/pmzilla?host=/var/run/postgresql", "postgresql://postgres@127.0.0.1/pmzilla?hostaddr=127.0.0.1",
                    "postgres://postgres@localhost:5432/pmzilla"):
            with self.subTest(url=url):
                self.assertEqual(db.verifier_url(url), url)

    def test_L2_mot_de_passe_refuse_dans_toutes_les_formes_sans_l_afficher(self):
        for url in ADRESSE_AVEC_MOT_DE_PASSE:
            with self.subTest(url=url):
                self.assertRefuseSansFuite(url)
                self.assertPsycopgJamaisAppele(url)

    def test_L2_variable_d_environnement_hote_posee_refusee_en_nommant_la_variable_sans_sa_valeur(self):
        for variable, valeur in VARIABLES_REFUSEES.items():
            with self.subTest(variable=variable):
                with mock.patch.dict(db.os.environ, {variable: valeur}):
                    message = self.assertRefuseSansFuite("postgresql://postgres@127.0.0.1:5432/pmzilla", valeur)
                    self.assertIn(variable, message)
                    self.assertPsycopgJamaisAppele("postgresql://postgres@127.0.0.1:5432/pmzilla")

    def test_L2_variable_d_environnement_vide_ou_absente_n_empeche_rien(self):
        propre = {k: v for k, v in db.os.environ.items() if k not in VARIABLES_REFUSEES}
        with mock.patch.dict(db.os.environ, {**propre, "PGHOSTADDR": ""}, clear=True):
            self.assertEqual(db.verifier_url("postgresql://postgres@127.0.0.1:5432/pmzilla"), "postgresql://postgres@127.0.0.1:5432/pmzilla")

    def test_L2_scram_reste_exige_sur_une_connexion_locale(self):
        propre = {k: v for k, v in db.os.environ.items() if k not in VARIABLES_REFUSEES}
        faux = FauxPsycopg()
        with mock.patch.dict(db.os.environ, propre, clear=True), mock.patch.object(db, "psycopg", faux):
            with self.assertRaises(db.ErreurBase):
                db.connect("postgres://postgres@localhost:5432/pmzilla", password=SECRET_FICTIF)
        self.assertEqual(faux.appels[0][1].get("require_auth"), "scram-sha-256")


if __name__ == "__main__":
    unittest.main()
