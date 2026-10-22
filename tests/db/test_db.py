"""
Tests de tools/db.py et de db/migrations/ : exécuteur de migrations sur une base jetable.

    uv run --with "psycopg[binary]" python -m unittest discover -s tests/db -v

Les tests sans base (noms de fichiers, empreintes, refus d'une adresse avec mot de passe) tournent toujours. Les autres se
connectent à l'instance JETABLE de bash tools/dbtest.sh (PMZILLA_LAB_DB_PORT, PMZILLA_LAB_DB_PASSWORD), créent une base
pmzilla_test_<hex>, y appliquent les migrations puis la suppriment, dans tous les cas. La garde base_jetable_disponible les saute
(message : base jetable absente) sauf si DBTEST_PORT, posé par ce seul script, est un port de forme décimale simple autre que 5432, égal en nombre au port de connexion :
ni la base de 5432 ni celle du port configuré de la vraie base n'est jamais utilisée. Le vrai Trousseau n'est jamais interrogé :
PMZILLA_LAB_DB_SECURITY_BIN pointe un faux binaire.

psycopg est toujours fourni (le lanceur tests/run_all.sh l'installe, tools/dbtest.sh passe par lui) : les tests sans base qui se
connectent à une adresse fermée pour lire l'erreur ne sautent plus quand psycopg manque (test-speed-2, D24). Un lancement à nu sans
psycopg les fait ÉCHOUER au lieu de les sauter : passer par bash tests/run_all.sh db, ou ajouter --with "psycopg[binary]".
"""
import contextlib
import hashlib
import io
import os
import re
import secrets
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import db  # noqa: E402

MESSAGE_SAUT = "base jetable absente (lancer bash tools/dbtest.sh)"
FAUX_MOT_DE_PASSE = "FauxMotDePasse-7c1e9b42"

# Faux `security` : refuse toute commande autre que la lecture du service attendu, ne renvoie que ce qu'on lui donne.
FAUX_SECURITY = """#!/bin/sh
[ "$1" = "find-generic-password" ] && [ "$2" = "-s" ] && [ "$3" = "pmzilla-lab-db" ] && [ "$4" = "-w" ] || exit 2
[ -n "$FAUX_SECURITY_VALEUR" ] || exit 44
printf '%s\\n' "$FAUX_SECURITY_VALEUR"
"""

_RACCOURCI_SECURITY = tempfile.TemporaryDirectory()
_FAUX_ECHEC = Path(_RACCOURCI_SECURITY.name) / "security_absent"
_FAUX_ECHEC.write_text("#!/bin/sh\nexit 44\n")
_FAUX_ECHEC.chmod(_FAUX_ECHEC.stat().st_mode | stat.S_IXUSR)
os.environ[db.VARIABLE_SECURITY] = str(_FAUX_ECHEC)  # le vrai Trousseau n'est jamais lu par ces tests

URL_BASE = os.environ.get(db.VARIABLE_URL) or db.url_par_defaut()
MOT_DE_PASSE = os.environ.get(db.VARIABLE_MOT_DE_PASSE)

VARIABLE_REPERE = "DBTEST_PORT"   # posée par tools/dbtest.sh : le port de son conteneur jetable (test-speed-2, D1)
PORT_STANDARD = 5432


def _port_valide(texte: str | None) -> int | None:
    """Une seule règle de port (test-db-guards, D1) : forme décimale simple seulement (chiffres ASCII, sans signe, sans espace, sans
    zéro en tête, de 1 à 65535), rendue comme nombre ; toute autre forme rend None. Même règle que tools/dbtest.sh."""
    if texte is None or re.fullmatch(r"[1-9][0-9]{0,4}", texte, re.ASCII) is None:
        return None
    nombre = int(texte)
    return nombre if nombre <= 65535 else None


def base_jetable_disponible(env=None, connecter=None) -> bool:
    """Garde des tests avec base (test-speed-2, D1) : vrai seulement si toutes les conditions tiennent, dans cet ordre, et sans
    aucune connexion avant la dernière : psycopg importable ; DBTEST_PORT et le port de connexion (PMZILLA_LAB_DB_PORT) sont tous deux
    de forme décimale simple (chiffres ASCII, sans signe, sans espace, sans zéro en tête, de 1 à 65535, test-db-guards D1) ; le repère
    n'est pas 5432 ; le port de connexion lui est égal en nombre ; l'adresse (PMZILLA_LAB_DB_URL), si elle existe, vise ce port en
    nombre ; le mot de passe est non vide ; la connexion (délai de deux secondes) réussit. La vraie base, sur 5432 ou sur son port
    configuré, n'est donc jamais utilisée."""
    env = os.environ if env is None else env
    connecter = db.connect if connecter is None else connecter
    if db.psycopg is None:
        return False
    repere = _port_valide(env.get(VARIABLE_REPERE))
    if repere is None or repere == PORT_STANDARD or _port_valide(env.get("PMZILLA_LAB_DB_PORT")) != repere:
        return False
    adresse = env.get(db.VARIABLE_URL)
    if adresse:
        try:
            port_adresse = urlsplit(adresse).port
        except ValueError:
            return False
        if port_adresse is None or port_adresse != repere:
            return False
    mot_de_passe = env.get(db.VARIABLE_MOT_DE_PASSE)
    if not mot_de_passe:
        return False
    try:
        connecter(adresse or db.url_par_defaut(), password=mot_de_passe, timeout=2, autocommit=True).close()
        return True
    except db.ErreurBase:
        return False


BASE_DISPONIBLE = base_jetable_disponible()


def url_vers(nom_base: str) -> str:
    morceaux = urlsplit(URL_BASE)
    return urlunsplit(morceaux._replace(path="/" + nom_base))


def ecrire(dossier: Path, nom: str, contenu: str = "SELECT 1;") -> Path:
    chemin = dossier / nom
    chemin.write_text(contenu, encoding="utf-8")
    return chemin


class TestSansBase(unittest.TestCase):
    def test_aucune_migration_ne_cree_de_role_avec_connexion_ni_mot_de_passe(self):
        """Statique, donc indépendant des rôles déjà présents dans l'instance : toute création de rôle est NOLOGIN, aucun mot de passe
        n'est posé, aucun rôle n'est modifié ni supprimé (les rôles sont partagés par toute l'instance)."""
        import re
        for migration in db.lister_migrations():
            texte = migration.chemin.read_text(encoding="utf-8")
            sans_commentaires = "\n".join(l.split("--")[0] for l in texte.splitlines())
            for creation in re.findall(r"CREATE ROLE[^;']*", sans_commentaires):
                self.assertIn("NOLOGIN", creation, f"{migration.nom} : {creation.strip()}")
            self.assertNotRegex(sans_commentaires, r"(?<!NO)LOGIN", migration.nom)
            self.assertNotRegex(sans_commentaires.upper(), r"PASSWORD|ALTER\s+ROLE|DROP\s+ROLE", migration.nom)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dossier = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_migrations_du_depot_bien_nommees(self):
        migrations = db.lister_migrations()
        self.assertEqual(migrations[0].nom, "0001_schemas_roles_extensions.sql")
        for migration in migrations:
            self.assertRegex(migration.chemin.read_text(encoding="utf-8").splitlines()[0], r"^-- Schéma touché")

    def test_suite_continue_triee(self):
        for nom in ("0002_b.sql", "0001_a.sql", "0003_c.sql"):
            ecrire(self.dossier, nom)
        self.assertEqual([m.numero for m in db.lister_migrations(self.dossier)], [1, 2, 3])

    def test_noms_mal_formes_refuses(self):
        for nom in ("1_court.sql", "00001_long.sql", "0001_Majuscule.sql", "0001-tiret.sql", "0001_.sql", "0001_a b.sql", "0001.sql"):
            with self.subTest(nom=nom):
                ecrire(self.dossier, nom)
                with self.assertRaisesRegex(db.ErreurBase, "mal formé"):
                    db.lister_migrations(self.dossier)
                (self.dossier / nom).unlink()

    def test_fichiers_non_sql_ignores(self):
        ecrire(self.dossier, "0001_a.sql")
        ecrire(self.dossier, "README.md")
        self.assertEqual(len(db.lister_migrations(self.dossier)), 1)

    def test_numero_en_double_refuse(self):
        ecrire(self.dossier, "0001_a.sql")
        ecrire(self.dossier, "0001_b.sql")
        with self.assertRaisesRegex(db.ErreurBase, "en double"):
            db.lister_migrations(self.dossier)

    def test_trou_refuse(self):
        ecrire(self.dossier, "0001_a.sql")
        ecrire(self.dossier, "0003_c.sql")
        with self.assertRaisesRegex(db.ErreurBase, "Trou"):
            db.lister_migrations(self.dossier)

    def test_suite_qui_ne_commence_pas_a_un_refusee(self):
        ecrire(self.dossier, "0002_b.sql")
        with self.assertRaisesRegex(db.ErreurBase, "Trou"):
            db.lister_migrations(self.dossier)

    def test_empreinte_sha256_du_fichier(self):
        chemin = ecrire(self.dossier, "0001_a.sql", "SELECT 1;")
        self.assertEqual(db.empreinte_fichier(chemin), hashlib.sha256(b"SELECT 1;").hexdigest())
        premiere = db.lister_migrations(self.dossier)[0].empreinte
        chemin.write_text("SELECT 2;", encoding="utf-8")
        self.assertNotEqual(db.lister_migrations(self.dossier)[0].empreinte, premiere)

    def test_url_avec_mot_de_passe_refusee_sans_l_afficher(self):
        for url in (f"postgresql://postgres:{FAUX_MOT_DE_PASSE}@127.0.0.1:5432/pmzilla",
                    f"postgresql://postgres@127.0.0.1:5432/pmzilla?password={FAUX_MOT_DE_PASSE}"):
            with self.subTest(url=url.split("@")[0][:20]):
                with self.assertRaises(db.ErreurBase) as ctx:
                    db.verifier_url(url)
                self.assertNotIn(FAUX_MOT_DE_PASSE, str(ctx.exception))
                self.assertIn("mot de passe", str(ctx.exception))

    def test_connect_refuse_url_avec_mot_de_passe(self):
        with self.assertRaises(db.ErreurBase) as ctx:
            db.connect(f"postgresql://postgres:{FAUX_MOT_DE_PASSE}@127.0.0.1:1/pmzilla")
        self.assertNotIn(FAUX_MOT_DE_PASSE, str(ctx.exception))

    def test_parametre_de_mot_de_passe_vide_ou_fichier_de_mots_de_passe_refuse(self):
        # masking-mutation-tests 6.2, mutant tué : `keep_blank_values=True` devenu `False` (verifier_url) : un paramètre vide compte
        for url in ("postgresql://postgres@127.0.0.1:5432/pmzilla?password=",
                    "postgresql://postgres@127.0.0.1:5432/pmzilla?PassWord=",
                    "postgresql://postgres@127.0.0.1:5432/pmzilla?passfile=",
                    "postgresql://postgres@127.0.0.1:5432/pmzilla?sslmode=disable&passfile=/chemin/invente"):
            with self.subTest(url=url.split("?")[1][:12]):
                with self.assertRaises(db.ErreurBase):
                    db.verifier_url(url)

    def test_url_sans_mot_de_passe_acceptee(self):
        self.assertEqual(db.verifier_url("postgresql://postgres@127.0.0.1:5432/pmzilla"), "postgresql://postgres@127.0.0.1:5432/pmzilla")

    def test_url_par_defaut_suit_le_port(self):
        ancien = os.environ.get("PMZILLA_LAB_DB_PORT")
        os.environ["PMZILLA_LAB_DB_PORT"] = "6543"
        try:
            self.assertEqual(db.url_par_defaut(), "postgresql://postgres@127.0.0.1:6543/pmzilla")
        finally:
            if ancien is None:
                del os.environ["PMZILLA_LAB_DB_PORT"]
            else:
                os.environ["PMZILLA_LAB_DB_PORT"] = ancien

    def _faux_security(self, valeur=None):
        chemin = self.dossier / "security"
        chemin.write_text(FAUX_SECURITY)
        chemin.chmod(chemin.stat().st_mode | stat.S_IXUSR)
        if valeur is None:
            os.environ.pop("FAUX_SECURITY_VALEUR", None)
        else:
            os.environ["FAUX_SECURITY_VALEUR"] = valeur
        self.addCleanup(os.environ.pop, "FAUX_SECURITY_VALEUR", None)
        return str(chemin)

    def test_voie_trousseau_via_faux_security(self):
        self.assertEqual(db.mot_de_passe_trousseau(self._faux_security(FAUX_MOT_DE_PASSE)), FAUX_MOT_DE_PASSE)

    def test_trousseau_prioritaire_sur_la_variable(self):
        os.environ[db.VARIABLE_MOT_DE_PASSE] = "autre-valeur"
        self.addCleanup(os.environ.pop, db.VARIABLE_MOT_DE_PASSE, None)
        self.assertEqual(db.lire_mot_de_passe(self._faux_security(FAUX_MOT_DE_PASSE)), FAUX_MOT_DE_PASSE)

    def test_repli_sur_la_variable_si_trousseau_vide(self):
        os.environ[db.VARIABLE_MOT_DE_PASSE] = "valeur-de-repli"
        self.addCleanup(os.environ.pop, db.VARIABLE_MOT_DE_PASSE, None)
        self.assertEqual(db.lire_mot_de_passe(self._faux_security(None)), "valeur-de-repli")

    def test_ni_trousseau_ni_variable(self):
        os.environ.pop(db.VARIABLE_MOT_DE_PASSE, None)
        self.assertIsNone(db.lire_mot_de_passe(self._faux_security(None)))
        self.assertIsNone(db.lire_mot_de_passe(str(self.dossier / "inexistant")))

    def test_erreur_de_connexion_sans_le_mot_de_passe(self):
        with self.assertRaises(db.ErreurBase) as ctx:
            db.connect("postgresql://postgres@127.0.0.1:1/pmzilla", password=FAUX_MOT_DE_PASSE, timeout=2)
        self.assertNotIn(FAUX_MOT_DE_PASSE, str(ctx.exception))
        self.assertIsNone(ctx.exception.__cause__)


class TestAvecBase(unittest.TestCase):
    """Base jetable pmzilla_test_<hex>, supprimée en tearDown dans tous les cas."""

    def setUp(self):
        if not BASE_DISPONIBLE:
            self.skipTest(MESSAGE_SAUT)
        self.nom_base = "pmzilla_test_" + secrets.token_hex(6)
        self.temp = tempfile.TemporaryDirectory()
        self.dossier = Path(self.temp.name)
        self.admin = db.connect(URL_BASE, password=MOT_DE_PASSE, autocommit=True)
        self.addCleanup(self._supprimer_base)
        self.admin.execute(f'CREATE DATABASE "{self.nom_base}"')
        self.url = url_vers(self.nom_base)
        self.ouvertes = []

    def _supprimer_base(self):
        for conn in self.ouvertes:
            with contextlib.suppress(Exception):
                conn.close()
        with contextlib.suppress(Exception):
            self.admin.execute(f'DROP DATABASE IF EXISTS "{self.nom_base}" WITH (FORCE)')
        self.admin.close()
        self.temp.cleanup()

    def conn(self):
        c = db.connect(self.url, password=MOT_DE_PASSE)
        self.ouvertes.append(c)
        return c

    def migrer(self, dossier=None, **kw):
        migrations = db.lister_migrations(dossier or self.dossier)
        c = self.conn()
        try:
            return db.migrer(c, migrations, **kw)
        finally:
            c.close()

    def suivies(self):
        c = self.conn()
        try:
            return [r[0] for r in c.execute("SELECT nom FROM public.schema_migrations ORDER BY numero").fetchall()]
        finally:
            c.close()

    def test_migration_0001_du_depot(self):
        # Seulement la 0001, dans une base vierge : `migrer(db.DOSSIER_MIGRATIONS)` appliquait TOUTES les migrations du dépôt, donc les tables
        # de knowledge (0004 : 4 tables et 3 séquences = 7 objets) et de flow (0002) existaient déjà pour l'assertion « 0 table ».
        shutil.copy(db.DOSSIER_MIGRATIONS / "0001_schemas_roles_extensions.sql", self.dossier)
        self.migrer(self.dossier)
        c = self.conn()
        extensions = {r[0] for r in c.execute("SELECT extname FROM pg_extension")}
        self.assertLessEqual({"vector", "pg_search"}, extensions)
        schemas = {r[0] for r in c.execute("SELECT nspname FROM pg_namespace")}
        self.assertLessEqual({"knowledge", "cases", "flow"}, schemas)
        attendus = {f"pmzilla_{s}{suffixe}" for s in ("knowledge", "cases", "flow") for suffixe in ("", "_ro")} | {"pmzilla_owner"}
        # Les rôles sont ceux de TOUTE l'instance : l'attribut de connexion d'un rôle réel (posé par role-password) n'est pas
        # celui de la migration. On vérifie leur existence ici, et dans SansBase que la migration ne les crée qu'en NOLOGIN.
        roles = {r[0] for r in c.execute("SELECT rolname FROM pg_roles WHERE rolname LIKE 'pmzilla\\_%'")}
        self.assertLessEqual(attendus, roles)
        tables = c.execute("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                           "WHERE n.nspname IN ('knowledge', 'cases') AND c.relkind IN ('r','p','v','m','S')").fetchone()[0]
        self.assertEqual(tables, 0)        # flow reçoit ses tables à la migration 0002 (tests/db/test_flow_schema.py)
        self.assertEqual(self.suivies()[0], "0001_schemas_roles_extensions.sql")

    def test_droits_des_roles(self):
        self.migrer(db.DOSSIER_MIGRATIONS)
        c = self.conn()
        c.execute("SET ROLE pmzilla_owner")
        c.execute("CREATE TABLE knowledge.t (id int)")
        c.execute("CREATE TABLE cases.t (id int)")
        c.execute("RESET ROLE")
        c.commit()

        def essaie(role, sql):
            try:
                with c.transaction():
                    c.execute(f"SET LOCAL ROLE {role}")
                    c.execute(sql)
                return True
            except db.psycopg.errors.InsufficientPrivilege:
                return False

        self.assertTrue(essaie("pmzilla_knowledge", "INSERT INTO knowledge.t VALUES (1)"))
        self.assertTrue(essaie("pmzilla_knowledge", "SELECT * FROM knowledge.t"))
        self.assertTrue(essaie("pmzilla_knowledge_ro", "SELECT * FROM knowledge.t"))
        self.assertFalse(essaie("pmzilla_knowledge_ro", "INSERT INTO knowledge.t VALUES (2)"))
        self.assertFalse(essaie("pmzilla_knowledge", "SELECT * FROM cases.t"))
        self.assertFalse(essaie("pmzilla_cases_ro", "SELECT * FROM knowledge.t"))
        self.assertFalse(essaie("pmzilla_flow", "SELECT * FROM cases.t"))
        self.assertFalse(essaie("pmzilla_knowledge", "CREATE TABLE knowledge.interdit (id int)"))
        self.assertFalse(essaie("pmzilla_knowledge", "DROP TABLE knowledge.t"))
        self.assertFalse(essaie("pmzilla_flow", "CREATE TABLE public.interdit (id int)"))

    def test_deuxieme_passage_sans_effet(self):
        self.migrer(db.DOSSIER_MIGRATIONS)
        c = self.conn()
        avant = c.execute("SELECT numero, nom, empreinte, appliquee_le FROM public.schema_migrations").fetchall()
        sortie = io.StringIO()
        etat = self.migrer(db.DOSSIER_MIGRATIONS, sortie=sortie)
        self.assertEqual(etat.en_attente, [])
        self.assertIn("Rien à appliquer", sortie.getvalue())
        self.assertEqual(c.execute("SELECT numero, nom, empreinte, appliquee_le FROM public.schema_migrations").fetchall(), avant)

    def test_empreinte_modifiee_arrete_tout(self):
        ecrire(self.dossier, "0001_a.sql", "CREATE TABLE public.a (id int);")
        self.migrer()
        ecrire(self.dossier, "0001_a.sql", "CREATE TABLE public.a (id bigint);")
        ecrire(self.dossier, "0002_b.sql", "CREATE TABLE public.b (id int);")
        with self.assertRaisesRegex(db.ErreurBase, "modifié depuis son application"):
            self.migrer()
        self.assertEqual(self.suivies(), ["0001_a.sql"])
        self.assertIsNone(self.conn().execute("SELECT to_regclass('public.b')").fetchone()[0])

    def test_fichier_applique_disparu_arrete_tout(self):
        ecrire(self.dossier, "0001_a.sql")
        self.migrer()
        (self.dossier / "0001_a.sql").unlink()
        ecrire(self.dossier, "0001_autre.sql")
        with self.assertRaisesRegex(db.ErreurBase, "manque ou a changé de nom"):
            self.migrer()

    def test_migration_invalide_annulee(self):
        ecrire(self.dossier, "0001_ok.sql", "CREATE TABLE public.ok (id int);")
        ecrire(self.dossier, "0002_ko.sql", "CREATE TABLE public.demi (id int);\nSELECT * FROM table_inexistante;")
        ecrire(self.dossier, "0003_suite.sql", "CREATE TABLE public.suite (id int);")
        with self.assertRaisesRegex(db.ErreurBase, "0002_ko.sql a échoué et a été annulée"):
            self.migrer()
        c = self.conn()
        self.assertEqual(self.suivies(), ["0001_ok.sql"])
        self.assertIsNone(c.execute("SELECT to_regclass('public.demi')").fetchone()[0])
        self.assertIsNone(c.execute("SELECT to_regclass('public.suite')").fetchone()[0])
        # corrigée en nouvelle migration impossible sans retirer le fichier fautif : la reprise applique la suite
        ecrire(self.dossier, "0002_ko.sql", "CREATE TABLE public.demi (id int);")
        self.migrer()
        self.assertEqual(self.suivies(), ["0001_ok.sql", "0002_ko.sql", "0003_suite.sql"])

    def test_dry_run_n_ecrit_rien(self):
        ecrire(self.dossier, "0001_a.sql", "CREATE TABLE public.a (id int);")
        sortie = io.StringIO()
        etat = self.migrer(dry_run=True, sortie=sortie)
        self.assertEqual([m.nom for m in etat.en_attente], ["0001_a.sql"])
        self.assertIn("En attente : 0001_a.sql", sortie.getvalue())
        c = self.conn()
        self.assertIsNone(c.execute("SELECT to_regclass('public.schema_migrations')").fetchone()[0])
        self.assertIsNone(c.execute("SELECT to_regclass('public.a')").fetchone()[0])

    def test_verrou_empeche_deux_executeurs(self):
        ecrire(self.dossier, "0001_a.sql")
        autre = self.conn()
        autre.execute("SELECT pg_advisory_lock(%s)", (db.CLE_VERROU,))
        autre.commit()
        with self.assertRaisesRegex(db.ErreurBase, "autre exécuteur"):
            self.migrer()
        autre.execute("SELECT pg_advisory_unlock(%s)", (db.CLE_VERROU,))
        autre.commit()
        self.migrer()
        self.assertEqual(self.suivies(), ["0001_a.sql"])

    def test_verrou_libere_apres_passage(self):
        ecrire(self.dossier, "0001_a.sql")
        self.migrer()
        self.migrer()

    def test_mot_de_passe_absent_des_erreurs_de_connexion(self):
        with self.assertRaises(db.ErreurBase) as ctx:
            db.connect(self.url, password=FAUX_MOT_DE_PASSE, timeout=2)
        self.assertNotIn(FAUX_MOT_DE_PASSE, str(ctx.exception))
        self.assertIsNone(ctx.exception.__cause__)

    def test_connexion_par_la_voie_trousseau(self):
        faux = Path(self.temp.name) / "security"
        faux.write_text(FAUX_SECURITY)
        faux.chmod(faux.stat().st_mode | stat.S_IXUSR)
        os.environ["FAUX_SECURITY_VALEUR"] = MOT_DE_PASSE or ""
        self.addCleanup(os.environ.pop, "FAUX_SECURITY_VALEUR", None)
        c = db.connect(self.url, security=str(faux))
        self.ouvertes.append(c)
        self.assertEqual(c.execute("SELECT current_database()").fetchone()[0], self.nom_base)

    def _cli(self, *args, mot_de_passe=MOT_DE_PASSE):
        """Lance db.main dans le processus ; renvoie (code, sortie, erreurs)."""
        env = {db.VARIABLE_URL: self.url, db.VARIABLE_MOT_DE_PASSE: mot_de_passe}
        anciens = {k: os.environ.get(k) for k in env}
        for k, v in env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        sortie, erreurs = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreurs):
                code = db.main(list(args), self.dossier)
        finally:
            for k, v in anciens.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        return code, sortie.getvalue(), erreurs.getvalue()

    def test_cli_status_et_migrate_sans_mot_de_passe_dans_la_sortie(self):
        ecrire(self.dossier, "0001_a.sql")
        ecrire(self.dossier, "0002_b.sql")
        code, sortie, erreurs = self._cli("status")
        # Depuis db-roles-status, status contrôle aussi les rôles et pg_search : sur cette base jetable aux migrations factices,
        # l'extension manque, donc le code est 3 (au moins un problème) et non plus 0. Les lignes de migrations sont inchangées.
        self.assertEqual((code in (0, 3), "En attente : 0001_a.sql" in sortie), (True, True))
        code, sortie, erreurs = self._cli("migrate")
        self.assertEqual(code, 0)
        self.assertIn("Appliquée : 0002_b.sql", sortie)
        code, sortie, erreurs = self._cli("status")
        self.assertIn("Appliquée  : 0001_a.sql", sortie)
        self.assertTrue(sortie.rstrip("\n").splitlines()[-1].startswith("État : "))     # la ligne de synthèse est la dernière
        for texte in (sortie, erreurs):
            self.assertNotIn(MOT_DE_PASSE or "\0", texte)

    def test_cli_erreur_de_connexion_sans_mot_de_passe(self):
        code, sortie, erreurs = self._cli("migrate", mot_de_passe=FAUX_MOT_DE_PASSE)
        self.assertEqual(code, 1)
        self.assertIn("Erreur", erreurs)
        self.assertNotIn(FAUX_MOT_DE_PASSE, sortie + erreurs)


if __name__ == "__main__":
    unittest.main()
