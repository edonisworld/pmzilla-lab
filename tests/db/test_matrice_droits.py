"""
Matrice des droits en base (audit #629, décision de l'auteur R-20261107-26, décision 11 ; cadrage : questions de détection des failles du 2026-11-07,
point 3a) : pour chaque rôle et chaque objet, les droits attendus, PUBLIC compris, déclarés dans tests/db/matrice_droits.json et comparés au catalogue
réel de la base jetable, une fois toutes les migrations appliquées.

    bash tools/dbtest.sh db        (passe de l'auteur : les modules de tests/db ne sont pas lancés par une session)

Remplace : rien. Les tests de droits par schéma de tests/db/ (test_flow_schema, test_quality_schema, test_mothra_schema, test_knowledge_schema,
test_cases_schema, test_watch_schema, test_flow_*, test_team_name_views...) restent en place : chacun vérifie un comportement par un essai sous
SET ROLE. La matrice donne la vue d'ensemble. Quand elle et un test par schéma divergent, la matrice fait foi pour l'inventaire des droits, le test
par schéma pour le comportement, et l'écart est un constat à trancher par l'auteur (pas une raison de modifier l'un pour suivre l'autre).
Condition de retrait : permanent. Les exceptions de PUBLIC portent chacune la leur (dont pdb : « tombe avec #727 »), lue dans le fichier JSON.

STATUT : validée par l'auteur le 2026-11-12 (R-20261112-03, R-20261112-10) après un passage vert, non sauté, de DroitsReels sur la base jetable ;
un écart futur est une erreur à trancher par l'auteur.

Deux classes :
  - SansBase tourne toujours : cohérence de la matrice avec db.py, avec le contrat de Mothra (contrats/vues.json) et avec la migration 0039 ;
  - DroitsReels utilise une base jetable pmzilla_test_<hex> (sautée sans DBTEST_PORT) : aucune ligne n'est lue ni écrite, seuls les catalogues sont
    interrogés. Le message d'échec liste tous les écarts, pas le premier.
"""
import contextlib
import json
import re
import secrets
import unittest
from pathlib import Path

import test_db as base          # noqa: E402
from test_db import db          # noqa: E402

RACINE = Path(__file__).resolve().parents[2]
MATRICE = Path(__file__).with_name("matrice_droits.json")
CONTRAT = RACINE / "contrats" / "vues.json"
PUBLIC = "PUBLIC"
PRIVILEGES_TABLE = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")
PRIVILEGES_SEQUENCE = ("USAGE", "SELECT", "UPDATE")
PRIVILEGES_SCHEMA = ("USAGE", "CREATE")
PRIVILEGES_BASE = ("CONNECT", "CREATE", "TEMPORARY")
GENRE_PAR_RELKIND = {"r": "table", "p": "table", "f": "table", "v": "vue", "m": "vue", "S": "sequence"}
SCHEMAS_DU_PROJET = ("flow", "quality", "cases", "knowledge", "mothra")


def charger() -> dict:
    return json.loads(MATRICE.read_text(encoding="utf-8"))


def privileges_du_genre(genre: str) -> tuple:
    return PRIVILEGES_SEQUENCE if genre == "sequence" else PRIVILEGES_TABLE


def vues_du_contrat() -> set:
    return {v["name"] for v in json.loads(CONTRAT.read_text(encoding="utf-8"))["views"] if v.get("roleKind") == "flow"}


# Vue interne que le serveur lit sans la servir (constante VUE_HEBDO de mothra/server/src/service.ts : relation T3 de v_team_lead_time_throughput).
VUES_INTERNES = {"v_team_weekly_resolved"}


def vues_attendues() -> set:
    return vues_du_contrat() | VUES_INTERNES


def declares_relation(matrice: dict, schema: str, nom: str, genre: str) -> dict:
    """{rôle : droits} déclarés pour une relation : l'entrée nommée de « objets » si elle existe, sinon le défaut du genre ; le propriétaire du schéma
    a tous les droits du genre."""
    config = matrice["relations"][schema]
    declares = config["objets"][nom] if nom in config["objets"] else config[genre + "_defaut"]
    droits = {role: set(valeurs) for role, valeurs in declares.items()}
    if config.get("proprietaire"):
        droits[config["proprietaire"]] = set(privileges_du_genre(genre))
    return droits


def declares_schema(matrice: dict, schema: str) -> dict:
    config = matrice["schemas"][schema]
    droits = {}
    for privilege in PRIVILEGES_SCHEMA:
        for role in config.get(privilege, []):
            droits.setdefault(role, set()).add(privilege)
    if config.get("proprietaire"):
        droits[config["proprietaire"]] = set(PRIVILEGES_SCHEMA)
    return droits


def declares_fonction(matrice: dict, schema: str, nom: str) -> dict:
    cle = f"{schema}.{nom}"
    declares = matrice["fonctions"].get(cle, matrice["fonctions_optionnelles"].get(cle))
    droits = {role: set(valeurs) for role, valeurs in (declares or {}).items()}
    proprietaire = matrice["relations"].get(schema, {}).get("proprietaire")
    if proprietaire:
        droits[proprietaire] = {"EXECUTE"}
    return droits


def toleres(matrice: dict, genre: str, cle: str) -> set:
    """Droits que PUBLIC peut avoir sur la cible, par une exception nommée de la matrice (présents ou non)."""
    droits = set()
    for exception in matrice["exceptions_public"]:
        cible = exception["cible"]
        if cible["genre"] != genre:
            continue
        if cible.get("nom") == cle or cle in cible.get("noms", []):
            droits |= set(exception["droits"])
    return droits


def attendu(declares: dict, role: str) -> set:
    """Le droit effectif attendu d'un rôle : ce qui lui est déclaré, plus ce que PUBLIC reçoit (PostgreSQL les additionne)."""
    pour_public = declares.get(PUBLIC, set())
    return set(pour_public) if role == PUBLIC else set(declares.get(role, set())) | set(pour_public)


def comparer(sujet: str, role: str, reel: set, minimum: set, toleres_public: set, ecarts: list) -> None:
    en_trop = sorted(reel - minimum - toleres_public)
    manquants = sorted(minimum - reel)
    if en_trop:
        ecarts.append(f"{sujet} : {role} a en trop {en_trop}")
    if manquants:
        ecarts.append(f"{sujet} : {role} n'a pas {manquants}")


class SansBase(unittest.TestCase):
    def setUp(self):
        self.matrice = charger()

    def test_les_roles_de_la_matrice_sont_ceux_de_db_py(self):
        """Source : les deux listes de tools/db.py (elles-mêmes gardées contre les migrations par test_status_roles). Un écart se détecte ici."""
        self.assertEqual(set(self.matrice["roles"]), set(db.ROLES_AVEC_MOT_DE_PASSE) | set(db.ROLES_SANS_MOT_DE_PASSE))
        self.assertEqual(len(self.matrice["roles"]), len(set(self.matrice["roles"])))

    def test_chaque_droit_declare_est_valide_et_chaque_role_est_connu(self):
        roles = set(self.matrice["roles"]) | {PUBLIC}
        valides = {"table": PRIVILEGES_TABLE, "vue": PRIVILEGES_TABLE, "sequence": PRIVILEGES_SEQUENCE}

        def verifie(declares, privileges, ou):
            for role, droits in declares.items():
                self.assertIn(role, roles, f"{ou} : rôle inconnu {role}")
                for droit in droits:
                    self.assertIn(droit, privileges, f"{ou} : droit inconnu {droit}")

        for schema, config in self.matrice["relations"].items():
            for genre, privileges in valides.items():
                verifie(config[genre + "_defaut"], privileges, f"{schema}.{genre}_defaut")
            for nom, declares in config["objets"].items():
                genre = "sequence" if nom.endswith("_seq") else None
                verifie(declares, privileges_du_genre(genre or "table"), f"{schema}.{nom}")
        for privilege, liste in self.matrice["base"].items():
            self.assertIn(privilege, PRIVILEGES_BASE)
            for role in liste:
                self.assertIn(role, roles)
        for schema, config in self.matrice["schemas"].items():
            for privilege in PRIVILEGES_SCHEMA:
                for role in config.get(privilege, []):
                    self.assertIn(role, roles, f"schéma {schema}")
        for cle, declares in {**self.matrice["fonctions"], **{k: v for k, v in self.matrice["fonctions_optionnelles"].items() if not k.startswith("_")}}.items():
            verifie(declares, ("EXECUTE",), f"fonction {cle}")

    def test_les_schemas_du_projet_sont_tous_declares(self):
        for schema in SCHEMAS_DU_PROJET:
            self.assertIn(schema, self.matrice["schemas"])
            self.assertIn(schema, self.matrice["relations"])

    def test_chaque_exception_de_public_a_un_nom_une_raison_et_une_condition_de_retrait(self):
        noms = set()
        for exception in self.matrice["exceptions_public"]:
            for champ in ("nom", "cible", "droits", "raison", "retrait"):
                self.assertTrue(exception.get(champ), f"exception {exception.get('nom')} : champ {champ} manquant")
            self.assertNotIn(exception["nom"], noms)
            noms.add(exception["nom"])
            if exception["cible"].get("nom") in ("pdb", "paradedb"):
                self.assertIn("#727", exception["retrait"], exception["nom"])

    def test_le_role_de_mothra_lit_exactement_les_vues_du_contrat_et_la_vue_interne_dans_la_matrice(self):
        """La matrice n'est pas une copie libre : les vues de pmzilla_mothra_views sont celles de contrats/vues.json plus la vue interne, avec SELECT seul."""
        lues = {nom: droits["pmzilla_mothra_views"] for nom, droits in self.matrice["relations"]["flow"]["objets"].items()
                if "pmzilla_mothra_views" in droits}
        self.assertEqual(set(lues), vues_attendues())
        for nom, droits in lues.items():
            self.assertEqual(set(droits), {"SELECT"}, nom)
        for schema, config in self.matrice["relations"].items():
            for defaut in ("table_defaut", "vue_defaut", "sequence_defaut"):
                self.assertNotIn("pmzilla_mothra_views", config[defaut], f"{schema}.{defaut}")
            if schema != "flow":
                for nom, droits in config["objets"].items():
                    self.assertNotIn("pmzilla_mothra_views", droits, f"{schema}.{nom}")
        for cle, droits in self.matrice["fonctions"].items():
            if "pmzilla_mothra_views" in droits:
                self.assertTrue(cle.startswith("flow."), cle)

    def test_la_migration_0039_accorde_les_vues_du_contrat_et_la_vue_interne_seules(self):
        """Statique : la liste de GRANT SELECT de la migration du rôle de Mothra est celle du contrat plus la vue interne (le test de la base jetable la vérifie aux droits réels)."""
        chemin = RACINE / "db" / "migrations" / "0039_mothra_views_role.sql"
        code = "\n".join(ligne.split("--", 1)[0] for ligne in chemin.read_text(encoding="utf-8").splitlines())
        accorde = re.search(r"GRANT SELECT ON (.*?) TO pmzilla_mothra_views\s*;", code, flags=re.S)
        self.assertIsNotNone(accorde)
        vues = {morceau.strip().removeprefix("flow.") for morceau in accorde.group(1).split(",")}
        self.assertEqual(vues, vues_attendues())
        self.assertEqual(len(re.findall(r"GRANT SELECT", code)), 1)
        self.assertNotRegex(code, r"(?i)GRANT[^;]*\b(INSERT|UPDATE|DELETE|TRUNCATE|CREATE|ALL)\b[^;]*TO[^;]*pmzilla_mothra_views")


class DroitsReels(unittest.TestCase):
    """Base jetable migrée (toutes les migrations du dépôt), supprimée à la fin. Rien n'est écrit : seuls les catalogues sont lus."""

    def setUp(self):
        if not base.BASE_DISPONIBLE:
            self.skipTest(base.MESSAGE_SAUT)
        self.matrice = charger()
        self.nom_base = "pmzilla_test_" + secrets.token_hex(6)
        self.admin = db.connect(base.URL_BASE, password=base.MOT_DE_PASSE, autocommit=True)
        self.addCleanup(self._supprimer)
        self.admin.execute(f'CREATE DATABASE "{self.nom_base}"')
        self.url = base.url_vers(self.nom_base)
        self.ouvertes = []
        c = self.conn()
        db.migrer(c, db.lister_migrations(db.DOSSIER_MIGRATIONS))
        c.commit()
        self.c = c
        self.sujets = list(self.matrice["roles"]) + [PUBLIC]

    def _supprimer(self):
        for c in self.ouvertes:
            with contextlib.suppress(Exception):
                c.close()
        with contextlib.suppress(Exception):
            self.admin.execute(f'DROP DATABASE IF EXISTS "{self.nom_base}" WITH (FORCE)')
        self.admin.close()

    def conn(self):
        c = db.connect(self.url, password=base.MOT_DE_PASSE)
        self.ouvertes.append(c)
        return c

    @staticmethod
    def nom_sql(role: str) -> str:
        return "public" if role == PUBLIC else role

    def verifie(self, ecarts: list) -> None:
        self.assertEqual(ecarts, [], f"{len(ecarts)} écart(s) entre la matrice des droits et la base jetable (matrice à valider par l'auteur) :\n" + "\n".join(ecarts))

    def test_attributs_des_roles_et_appartenances(self):
        ecarts = []
        for ligne in self.c.execute("SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls FROM pg_roles "
                                    "WHERE rolname = ANY(%s)", (self.matrice["roles"],)).fetchall():
            for colonne, valeur in zip(("rolsuper", "rolcreatedb", "rolcreaterole", "rolreplication", "rolbypassrls"), ligne[1:]):
                if valeur:
                    ecarts.append(f"rôle {ligne[0]} : attribut interdit {colonne}")
        presents = {r[0] for r in self.c.execute("SELECT rolname FROM pg_roles WHERE rolname = ANY(%s)", (self.matrice["roles"],)).fetchall()}
        for manquant in sorted(set(self.matrice["roles"]) - presents):
            ecarts.append(f"rôle {manquant} : absent de la base (créé par aucune migration ?)")
        membres = sorted(tuple(r) for r in self.c.execute(
            "SELECT m.rolname, r.rolname FROM pg_auth_members a JOIN pg_roles m ON m.oid = a.member JOIN pg_roles r ON r.oid = a.roleid "
            "WHERE m.rolname LIKE 'pmzilla\\_%'").fetchall())
        declares = sorted(tuple(p) for p in self.matrice["appartenances"])
        if membres != declares:
            ecarts.append(f"appartenances (membre, rôle) des rôles pmzilla : {membres}, attendu {declares}")
        self.verifie(ecarts)

    def test_droits_sur_la_base(self):
        ecarts = []
        for privilege in PRIVILEGES_BASE:
            declares = {}
            for role in self.matrice["base"].get(privilege, []):
                declares.setdefault(role, set()).add(privilege)
            for sujet in self.sujets:
                reel = {privilege} if self.c.execute("SELECT has_database_privilege(%s::name, current_database()::text, %s::text)",
                                                     (self.nom_sql(sujet), privilege)).fetchone()[0] else set()
                comparer(f"base {privilege}", sujet, reel, attendu(declares, sujet) & {privilege}, set(), ecarts)
        self.verifie(ecarts)

    def test_droits_sur_les_schemas(self):
        ecarts = []
        presents = {r[0] for r in self.c.execute("SELECT nspname FROM pg_namespace").fetchall()}
        for schema, config in self.matrice["schemas"].items():
            if schema not in presents:
                if config.get("optionnel"):
                    continue
                ecarts.append(f"schéma {schema} : absent")
                continue
            declares = declares_schema(self.matrice, schema)
            tolere = toleres(self.matrice, "schema", schema)
            for sujet in self.sujets:
                reel = {p for p in PRIVILEGES_SCHEMA
                        if self.c.execute("SELECT has_schema_privilege(%s::name, %s::text, %s::text)",
                                       (self.nom_sql(sujet), schema, p)).fetchone()[0]}
                comparer(f"schéma {schema}", sujet, reel, attendu(declares, sujet), tolere, ecarts)
        self.verifie(ecarts)

    def test_droits_sur_les_relations(self):
        ecarts = []
        lignes = self.c.execute(
            "SELECT n.nspname, c.relname, c.relkind, c.oid FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = ANY(%s) AND c.relkind IN ('r', 'p', 'f', 'v', 'm', 'S') ORDER BY 1, 2",
            (list(self.matrice["relations"]),)).fetchall()
        vues_trouvees = set()
        for schema, nom, relkind, oid in lignes:
            config = self.matrice["relations"][schema]
            if config.get("seulement_nommes") and nom not in config["objets"]:
                continue
            genre = GENRE_PAR_RELKIND[relkind]
            vues_trouvees.add((schema, nom))
            declares = declares_relation(self.matrice, schema, nom, genre)
            fonction = "has_sequence_privilege" if genre == "sequence" else "has_table_privilege"
            for sujet in self.sujets:
                reel = {p for p in privileges_du_genre(genre)
                        if self.c.execute(f"SELECT {fonction}(%s::name, %s::oid, %s::text)", (self.nom_sql(sujet), oid, p)).fetchone()[0]}
                comparer(f"{schema}.{nom} ({genre})", sujet, reel, attendu(declares, sujet), set(), ecarts)
        for schema, config in self.matrice["relations"].items():
            for nom in config["objets"]:
                if (schema, nom) not in vues_trouvees:
                    ecarts.append(f"{schema}.{nom} : déclaré dans la matrice, absent de la base (renommé ou retiré ?)")
        self.verifie(ecarts)

    def test_droits_sur_les_fonctions_des_schemas_du_projet(self):
        ecarts = []
        lignes = self.c.execute(
            "SELECT n.nspname, p.proname, p.oid FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE n.nspname = ANY(%s) AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = p.oid AND d.deptype = 'e') ORDER BY 1, 2",
            (list(SCHEMAS_DU_PROJET),)).fetchall()
        trouvees = set()
        for schema, nom, oid in lignes:
            cle = f"{schema}.{nom}"
            trouvees.add(cle)
            if cle not in self.matrice["fonctions"] and cle not in self.matrice["fonctions_optionnelles"]:
                ecarts.append(f"{cle} : fonction non déclarée dans la matrice (à déclarer avec ses droits)")
                continue
            declares = declares_fonction(self.matrice, schema, nom)
            tolere = toleres(self.matrice, "fonction", cle)
            for sujet in self.sujets:
                reel = {"EXECUTE"} if self.c.execute("SELECT has_function_privilege(%s::name, %s::oid, 'EXECUTE'::text)",
                                                     (self.nom_sql(sujet), oid)).fetchone()[0] else set()
                comparer(f"fonction {cle}", sujet, reel, attendu(declares, sujet), tolere, ecarts)
        for cle in self.matrice["fonctions"]:
            if cle not in trouvees:
                ecarts.append(f"fonction {cle} : déclarée dans la matrice, absente de la base")
        self.verifie(ecarts)


if __name__ == "__main__":
    unittest.main()
