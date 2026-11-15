"""
Droits de lecture des index BM25 par les fonctions autonomes de pg_search (R-194, passage de ParadeDB 0.26.4 à 0.26.5), sur une base
jetable pmzilla_test_<hex>.

Remplace : rien (premier test de cette famille).
Condition de retrait : permanent (non-régression de #7114, une faille de sécurité de pg_search : sans SELECT sur la table, on ne lit rien
de son index BM25, ni par une fonction autonome, ni par le nom de l'index, ni par son OID numérique).
Source : correctif #7114 de ParadeDB 0.26.5 « enforce permissions on standalone index reads » (rétroportage de #7023) ; décisions de
l'auteur R-20261107-10 ; R-20261107-15 (Q1 b : R-194 garde le correctif seul, image 0.26.5 et ce test ; la migration 0039 est retirée
de la branche et R-20261107-14, USAGE retiré à PUBLIC, est suspendue ; Q2 a : exemptions de l'amont) ; R-20261107-17 (fonctions de cast
contrôlées par identité ; un appel STRICT avec un NULL compte comme non tenté ; rouge si une fonction non exemptée n'est jamais exécutée).

Sous 0.26.4 le test des fonctions autonomes est ROUGE (c'est voulu) ; sous 0.26.5 il est vert.

    bash tests/run_all.sh db   (ou le dbtest de l'auteur)

Les tests avec base ne touchent que la base jetable (créée puis supprimée dans tous les cas, ainsi que le rôle temporaire), jamais les
schémas réels ; ils sont sautés si la base jetable manque (garde_base_jetable via test_db). Aucune donnée réelle : la table knowledge.chunks
reste vide, car la lecture refusée ne dépend pas des lignes.
"""
import contextlib
import re
import secrets
import unittest

import test_db as base          # noqa: E402  (même dossier : connexion, base jetable, mot de passe)
from test_db import db          # noqa: E402

SCHEMAS_PG_SEARCH = ("paradedb", "pdb")
INDEX_CIBLE = "knowledge.chunks_bm25"
SQLSTATE_DROIT_REFUSE = "42501"
# Fonctions exemptées du contrôle de SELECT par l'amont (R-20261107-15, Q2 a). Source, audit de l'amont (commentaire de
# pg_search/tests/pg_regress/sql/permission_access.sql, PR #7114, https://github.com/paradedb/paradedb/pull/7114) :
# "Exceptions: with_index constructs query input; deprecated bgmerger_state, reset_bgworker_state and both force_merge overloads read no
# index data."
# force_merge a deux surcharges : le nom couvre les deux. Schéma : paradedb.
# Règle « aucune donnée » : pour une fonction exemptée, un appel qui réussit n'est PAS une fuite s'il ne rend aucune donnée de l'index, soit
# 0 ligne, soit une seule ligne dont chaque valeur est NULL, vide (void compris) ou un texte qui ne contient pas « chunks » (nom de la table
# et de l'index cibles ; la table est vide, donc aucun contenu) ; plus d'une ligne, ou une fonction qui rend un ensemble avec au moins une ligne,
# est une fuite. Toute autre fonction qui réussit sans SELECT reste une fuite, sans exception.
EXEMPTEES_PAR_L_AMONT = {"with_index", "bgmerger_state", "reset_bgworker_state", "force_merge"}
SCHEMA_EXEMPTEES = "paradedb"
# Fonctions de diagnostic ou de métadonnées qui prennent le nom d'un index en texte (en plus de toutes celles dont le premier argument est un
# regclass ou un oid, découvertes dans pg_proc).
DIAGNOSTICS_TEXTE = {"index_info", "index_layer_info", "index_fields", "layer_sizes", "merge_info", "segments", "verify_index",
                     "verify_all_indexes", "schema", "index_size"}
LITTERAL_PAR_TYPE = {"jsonb": "'{}'::jsonb", "json": "'{}'::json", "text": "'x'", "bool": "false", "int4": "1", "int8": "1::bigint",
                     "int2": "1", "float8": "1.0", "oid": "0",
                     # format_type rend les noms SQL, pas les noms internes
                     "boolean": "false", "integer": "1", "bigint": "1::bigint", "smallint": "1::smallint",
                     "double precision": "1.0::float8", "tid": "'(0,1)'::tid",
                     # requête « tout » de pg_search : aggregate doit s'exécuter jusqu'à la garde, pas s'arrêter sur un NULL
                     # (clé sans schéma : type_court retire le préfixe « paradedb. »)
                     "searchqueryinput": "paradedb.all()"}


def etat_fonctions(c):
    """Rend [(schéma, nom, types des arguments, nombre d'arguments obligatoires)] pour les fonctions de paradedb et de pdb."""
    lignes = c.execute(
        "SELECT n.nspname, p.proname, "
        "       COALESCE((SELECT array_agg(format_type(t, NULL) ORDER BY o) FROM unnest(p.proargtypes::oid[]) WITH ORDINALITY AS u(t, o)), "
        "                ARRAY[]::text[]), "
        "       p.pronargs - p.pronargdefaults "
        "FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
        "WHERE n.nspname = ANY(%s) AND p.prokind = 'f' ORDER BY 1, 2, 3", (list(SCHEMAS_PG_SEARCH),)).fetchall()
    return [(s, n, list(types), obligatoires) for s, n, types, obligatoires in lignes]


def fonctions_ensemble(c):
    """Rend {(schéma, nom)} des fonctions de paradedb et de pdb qui rendent un ensemble de lignes (proretset)."""
    lignes = c.execute(
        "SELECT n.nspname, p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
        "WHERE n.nspname = ANY(%s) AND p.prokind = 'f' AND p.proretset", (list(SCHEMAS_PG_SEARCH),)).fetchall()
    return {(s, n) for s, n in lignes}


def fonctions_strictes(c):
    """Rend {(schéma, nom, types)} des fonctions STRICT de paradedb et de pdb : appelées avec un NULL, elles ne s'exécutent pas."""
    lignes = c.execute(
        "SELECT n.nspname, p.proname, "
        "       COALESCE((SELECT array_agg(format_type(t, NULL) ORDER BY o) FROM unnest(p.proargtypes::oid[]) WITH ORDINALITY AS u(t, o)), "
        "                ARRAY[]::text[]) "
        "FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
        "WHERE n.nspname = ANY(%s) AND p.prokind = 'f' AND p.proisstrict", (list(SCHEMAS_PG_SEARCH),)).fetchall()
    return {(s, n, tuple(types)) for s, n, types in lignes}


def fonctions_cast(c):
    """Rend {(schéma, nom)} des fonctions de paradedb et de pdb déclarées comme fonction de cast (pg_cast.castfunc)."""
    lignes = c.execute(
        "SELECT n.nspname, p.proname FROM pg_cast k JOIN pg_proc p ON p.oid = k.castfunc "
        "JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = ANY(%s)", (list(SCHEMAS_PG_SEARCH),)).fetchall()
    return {(s, n) for s, n in lignes}


# Règle de comparaison d'un cast (R-20261107-17). Un cast doit rendre exactement la valeur reçue, retypée : pour pdb.oid_to_alias, l'OID
# d'entrée, sans aucune donnée de l'index. La forme texte de pdb.alias n'étant pas documentée ici, la comparaison est : (1) texte rendu égal
# au texte d'entrée, ou (2) à défaut, le texte rendu est l'entrée habillée par le type : il ne contient pas « chunks » et ses seuls nombres
# sont exactement l'OID d'entrée (un seul groupe de chiffres, égal à l'entrée). Tout autre texte est une fuite.
def cast_est_identite(rendu, entree):
    if rendu is None:
        return False
    rendu, entree = str(rendu).strip(), str(entree).strip()
    if rendu == entree:
        return True
    if "chunks" in rendu.lower():
        return False
    return re.findall(r"\d+", rendu) == [entree]


def type_court(t):
    return t.split(".")[-1].replace('"', "")


def valeur_vide(valeur):
    """NULL, texte vide ou void (psycopg rend void en chaîne vide ou en None selon la version)."""
    return valeur is None or (isinstance(valeur, str) and valeur.strip() == "")


def donnee_de_l_index(valeur):
    """Vrai si la valeur rendue par une fonction exemptée peut porter une donnée de l'index ou de sa table."""
    if valeur_vide(valeur):
        return False
    return "chunks" in str(valeur).lower()


class AvecBase(unittest.TestCase):
    def setUp(self):
        if not base.BASE_DISPONIBLE:
            self.skipTest(base.MESSAGE_SAUT)
        self.nom_base = "pmzilla_test_" + secrets.token_hex(6)
        self.role_test = "pmzilla_test_sans_select_" + secrets.token_hex(4)
        self.admin = db.connect(base.URL_BASE, password=base.MOT_DE_PASSE, autocommit=True)
        self.ouvertes = []
        self.addCleanup(self._supprimer)
        self.admin.execute(f'CREATE DATABASE "{self.nom_base}"')
        self.url = base.url_vers(self.nom_base)
        c = self.conn()
        db.migrer(c, db.lister_migrations(db.DOSSIER_MIGRATIONS))
        c.commit()

    def _supprimer(self):
        for c in self.ouvertes:
            with contextlib.suppress(Exception):
                c.close()
        with contextlib.suppress(Exception):
            self.admin.execute(f'DROP DATABASE IF EXISTS "{self.nom_base}" WITH (FORCE)')
        with contextlib.suppress(Exception):
            self.admin.execute(f'DROP ROLE IF EXISTS "{self.role_test}"')
        self.admin.close()

    def conn(self, autocommit=False):
        c = db.connect(self.url, password=base.MOT_DE_PASSE, autocommit=autocommit)
        self.ouvertes.append(c)
        return c


class DroitsIndexAutonomes(AvecBase):
    """#7114 : un rôle sans SELECT sur la table ne lit rien de son index BM25 par une fonction autonome."""

    def setUp(self):
        super().setUp()
        self.admin.execute(f'CREATE ROLE "{self.role_test}" NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE')
        self.c = self.conn(autocommit=True)
        # Test fort : le rôle a USAGE sur paradedb, pdb et sur les schémas knowledge et cases, mais aucun droit sur leurs tables.
        for schema in (*SCHEMAS_PG_SEARCH, "knowledge", "cases"):
            self.c.execute(f'GRANT USAGE ON SCHEMA {schema} TO "{self.role_test}"')
        self.assertFalse(self.c.execute("SELECT has_table_privilege(%s, 'knowledge.chunks', 'SELECT')", (self.role_test,)).fetchone()[0])
        self.oid_index = self.c.execute("SELECT %s::regclass::oid", (INDEX_CIBLE,)).fetchone()[0]
        self.fonctions = etat_fonctions(self.c)
        self.ensembles = fonctions_ensemble(self.c)
        self.strictes = fonctions_strictes(self.c)
        self.casts = fonctions_cast(self.c)

    def sous_role(self):
        c = self.conn(autocommit=True)
        c.execute(f'SET ROLE "{self.role_test}"')
        return c

    def litteral_index(self, type_premier, voie):
        t = type_court(type_premier)
        if voie == "oid":
            return f"{self.oid_index}::oid::regclass" if t == "regclass" else (f"{self.oid_index}::oid" if t == "oid" else f"'{self.oid_index}'")
        return f"'{INDEX_CIBLE}'::regclass" if t == "regclass" else (f"'{INDEX_CIBLE}'::regclass::oid" if t == "oid" else f"'{INDEX_CIBLE}'")

    def est_exemptee(self, schema, nom):
        return schema == SCHEMA_EXEMPTEES and nom in EXEMPTEES_PAR_L_AMONT

    def donnees_rendues(self, schema, nom, lignes):
        """Pour une fonction exemptée dont l'appel a réussi : rend None si aucune donnée de l'index, sinon le détail de la fuite."""
        if not lignes:
            return None
        if (schema, nom) in self.ensembles:
            return f"fonction exemptée qui rend un ensemble de {len(lignes)} ligne(s)"
        if len(lignes) > 1:
            return f"fonction exemptée scalaire qui rend {len(lignes)} lignes"
        if any(donnee_de_l_index(v) for v in lignes[0]):
            return f"fonction exemptée dont la valeur évoque l'index ou sa table : {lignes[0]!r}"
        return None

    def appel(self, c, schema, nom, types, obligatoires, voie):
        """Tente l'appel avec les seuls arguments obligatoires. Rend ('refus' | 'fuite' | 'exemptee' | 'autre', détail)."""
        arguments = [self.litteral_index(types[0], voie)]
        for t in types[1:obligatoires]:
            arguments.append(LITTERAL_PAR_TYPE.get(type_court(t), f"NULL::{t}"))
        if (schema, nom, tuple(types)) in self.strictes and any(a.startswith("NULL::") for a in arguments):
            return "non_tentee", "STRICT avec un argument NULL, non exécutée : " + ", ".join(arguments)
        if (schema, nom) in self.casts:
            # Cast (R-20261107-17) : le résultat retypé en texte est comparé à l'entrée (OID pour regclass et oid), voir cast_est_identite.
            t = type_court(types[0])
            entree = f"({arguments[0]})::oid::text" if t in ("regclass", "oid") else f"({arguments[0]})::text"
            try:
                rendu, attendu = c.execute(f"SELECT ({schema}.{nom}({', '.join(arguments)}))::text, {entree}").fetchone()
            except Exception as erreur:  # noqa: BLE001
                if getattr(erreur, "sqlstate", None) == SQLSTATE_DROIT_REFUSE and "permission denied for table" in str(erreur):
                    return "refus", str(erreur)
                return "autre", f"{type(erreur).__name__} : {erreur}"
            if cast_est_identite(rendu, attendu):
                return "cast_identite", f"rend l'entrée : {rendu!r}"
            return "fuite", f"cast qui ne rend pas l'entrée : rendu {rendu!r}, entrée {attendu!r}"
        try:
            lignes = c.execute(f"SELECT * FROM {schema}.{nom}({', '.join(arguments)})").fetchall()
        except Exception as erreur:  # noqa: BLE001  (toute erreur de la base est classée ci-dessous)
            if getattr(erreur, "sqlstate", None) == SQLSTATE_DROIT_REFUSE and "permission denied for table" in str(erreur):
                return "refus", str(erreur)
            return "autre", f"{type(erreur).__name__} : {erreur}"
        if self.est_exemptee(schema, nom):
            fuite = self.donnees_rendues(schema, nom, lignes)
            return ("exemptee", f"{len(lignes)} ligne(s), aucune donnée de l'index") if fuite is None else ("fuite", fuite)
        return "fuite", f"{len(lignes)} ligne(s) : {lignes[:3]!r}"

    def candidates(self):
        """Fonctions qui prennent un index en premier argument : aggregate, et les diagnostics ou métadonnées (regclass, oid, ou texte listé)."""
        retenues = []
        for schema, nom, types, obligatoires in self.fonctions:
            if not types or obligatoires < 1:
                continue
            premier = type_court(types[0])
            if nom == "aggregate" or premier in ("regclass", "oid") or (premier == "text" and nom in DIAGNOSTICS_TEXTE):
                retenues.append((schema, nom, types, obligatoires))
        return retenues

    def test_aggregate_existe(self):
        noms = {(s, n) for s, n, _, _ in self.fonctions}
        self.assertTrue(any(n == "aggregate" for _, n in noms), "fonction absente : aggregate (schémas paradedb et pdb)")

    def test_fonctions_autonomes_refusees_par_le_nom_et_par_l_oid(self):
        self.maxDiff = None
        sorties = {"nom": [], "oid": []}
        fuites = []
        retenues = self.candidates()
        self.assertTrue(any(n == "aggregate" for _, n, _, _ in retenues), "fonction absente : aggregate n'est pas appelable avec un index")
        for voie in ("nom", "oid"):
            for schema, nom, types, obligatoires in retenues:
                c = self.sous_role()
                try:
                    verdict, detail = self.appel(c, schema, nom, types, obligatoires, voie)
                finally:
                    c.close()
                sorties[voie].append((schema, nom, verdict, detail))
                if verdict == "fuite":
                    fuites.append((voie, schema, nom, detail))
        # le message liste toutes les fuites en entier
        self.assertEqual(fuites, [], "lecture sans SELECT possible (#7114), %d fuite(s) :\n%s" % (len(fuites), "\n".join(map(repr, fuites))))
        non_tentees = [(voie, s, n, d) for voie in sorties for s, n, v, d in sorties[voie]
                       if v == "non_tentee" and not self.est_exemptee(s, n)]
        self.assertEqual(non_tentees, [], "fonction non exemptée jamais exécutée (type absent de LITTERAL_PAR_TYPE), test sans preuve :\n%s"
                         % "\n".join(map(repr, non_tentees)))
        # Revue Opus finale, C1 : une erreur autre que le refus de droit sur la table veut dire que la fonction n'a pas atteint
        # la garde ; elle n'a donc rien prouvé (R-20261107-17 : rouge si une fonction non exemptée n'est jamais exécutée).
        autres = [(voie, s, n, d) for voie in sorties for s, n, v, d in sorties[voie]
                  if v == "autre" and not self.est_exemptee(s, n)]
        self.assertEqual(autres, [], "fonction non exemptée arrêtée par une autre erreur que le refus de droit, test sans preuve :\n%s"
                         % "\n".join(map(repr, autres)))
        for voie in ("nom", "oid"):
            tentees = [s for s in sorties[voie]]
            self.assertTrue(tentees, f"aucun appel tenté par la voie {voie} : le test serait vide")
            refus_aggregate = [s for s in tentees if s[1] == "aggregate" and s[2] == "refus"]
            self.assertTrue(refus_aggregate, f"aggregate n'est pas refusée par la voie {voie} : {tentees}")
            self.assertTrue([s for s in tentees if s[2] == "refus"], f"aucun refus par la voie {voie} : {tentees}")

    def test_pdb_indexes_masque_l_index_ou_refuse(self):
        trouvees = [(s, n, t, o) for s, n, t, o in self.fonctions if n == "indexes" and o == 0]
        self.assertTrue(trouvees, "fonction absente : indexes() sans argument (schémas paradedb et pdb)")
        for schema, nom, _, _ in trouvees:
            c = self.sous_role()
            try:
                try:
                    lignes = [str(l) for l in c.execute(f"SELECT t::text FROM {schema}.{nom}() AS t").fetchall()]
                except Exception as erreur:  # noqa: BLE001
                    self.assertEqual(getattr(erreur, "sqlstate", None), SQLSTATE_DROIT_REFUSE, f"{schema}.{nom}() : {erreur}")
                    continue
            finally:
                c.close()
            self.assertFalse([l for l in lignes if "chunks_bm25" in l], f"{schema}.{nom}() montre knowledge.chunks_bm25 à un rôle sans SELECT : {lignes}")


if __name__ == "__main__":
    unittest.main()
