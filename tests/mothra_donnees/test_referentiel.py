"""
Tests du référentiel synthétique des cycles de Mothra (change cycle-referential-schema, tâche 2.3, conception D6 ; spec flow-cycle-referential,
deux dernières exigences). La partie pure ne demande aucune base : quatre cycles autour du jour du chargement, déterminisme, deux variantes,
validité contre l'ensemble d'étiquettes déclaré par le jeu, valeurs inventées préfixées, aucun fichier du dossier de contenu des flux ouvert.
La partie base est sautée sans DBTEST_PORT (bash tools/dbtest.sh mothra_donnees) : référentiel chargé avec le jeu, rôle des vues refusé.

    bash tests/run_all.sh mothra_donnees
"""
from __future__ import annotations

import ast
import builtins
import io
import os
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

DOSSIER = Path(__file__).resolve().parent
RACINE = DOSSIER.parents[1]
sys.path.insert(0, str(DOSSIER))
sys.path.insert(0, str(RACINE / "tools"))
sys.path.insert(0, str(RACINE / "tests" / "flow_store"))
import jeu_synthetique as jeu  # noqa: E402
import referentiel_synthetique as rs  # noqa: E402
import flow_referential as fr  # noqa: E402
import aide_base  # noqa: E402

SOURCE = DOSSIER / "referentiel_synthetique.py"
JOUR = date(2026, 1, 15)
JOURS = [JOUR + timedelta(days=i) for i in range(0, 400, 1)]       # chaque jour de la semaine, plusieurs années
ROLES = ("up_merge", "cycle", "epic_review", "pilot_domain", "ready", "confirmation")


def contenant(ref: fr.Referentiel, jour: date):
    return [c for c in ref.cycles if c.debut <= jour <= c.fin]


class CyclesAutourDuJour(unittest.TestCase):
    def test_quatre_cycles_dont_un_termine_un_en_cours_et_deux_a_venir_pour_chaque_jour(self):
        for jour in JOURS:
            ref = rs.construire(jour)
            self.assertEqual(len(ref.cycles), 4, jour)
            self.assertEqual(len(contenant(ref, jour)), 1, jour)
            self.assertEqual(sum(1 for c in ref.cycles if c.fin < jour), 1, jour)
            self.assertEqual(sum(1 for c in ref.cycles if c.debut > jour), 2, jour)

    def test_lundi_au_vendredi_huit_semaines_contigus(self):
        for jour in JOURS[:60]:
            cycles = rs.construire(jour).cycles
            for c in cycles:
                self.assertEqual(c.debut.weekday(), 0, (jour, c))          # lundi
                self.assertEqual(c.fin.weekday(), 4, (jour, c))            # vendredi
                self.assertEqual((c.fin - c.debut).days, 53, (jour, c))    # huit semaines, du lundi au vendredi
            for avant, apres in zip(cycles, cycles[1:]):
                self.assertEqual(apres.debut, avant.fin + timedelta(days=3), jour)   # le lundi suivant

    def test_cles_de_la_forme_annee_cn_dans_l_ordre(self):
        for jour in JOURS[:60]:
            cles = [c.cle for c in rs.construire(jour).cycles]
            self.assertEqual(len(set(cles)), 4)
            for cle in cles:
                self.assertRegex(cle, r"^[0-9]{4}-C[1-6]$")
            self.assertEqual(cles, sorted(cles))

    def test_le_dernier_cycle_a_venir_est_le_dernier(self):
        ref = rs.construire(JOUR)
        self.assertEqual(max(ref.cycles, key=lambda c: c.debut), ref.cycles[-1])

    def test_deterministe_pour_un_jour(self):
        self.assertEqual(rs.construire(JOUR), rs.construire(JOUR))
        self.assertEqual(rs.construire(JOUR, "validated"), rs.construire(JOUR, "validated"))
        self.assertEqual(rs.etiquettes_declarees(JOUR), rs.etiquettes_declarees(JOUR))

    def test_ne_depend_ni_de_l_horloge_ni_de_l_environnement(self):
        avant = rs.construire(JOUR)
        with mock.patch.dict(os.environ, {"TZ": "Pacific/Kiritimati"}):
            self.assertEqual(rs.construire(JOUR), avant)

    def test_un_autre_jour_decale_les_dates(self):
        self.assertNotEqual(rs.construire(JOUR).cycles, rs.construire(JOUR + timedelta(days=60)).cycles)


class Variantes(unittest.TestCase):
    def test_non_validee_par_defaut(self):
        self.assertEqual(rs.VARIANTE_DEFAUT, "not_validated")
        self.assertIsNone(rs.construire(JOUR).valide_le)
        self.assertEqual(rs.construire(JOUR), rs.construire(JOUR, "not_validated"))

    def test_variante_validee_date_avant_le_jour_et_le_reste_egal(self):
        sans, avec = rs.construire(JOUR), rs.construire(JOUR, "validated")
        self.assertIsNotNone(avec.valide_le)
        self.assertLess(avec.valide_le, JOUR)
        self.assertEqual(dataclass_sans_date(sans), dataclass_sans_date(avec))

    def test_variante_inconnue_refusee(self):
        with self.assertRaises(ValueError):
            rs.construire(JOUR, "autre")


def dataclass_sans_date(ref: fr.Referentiel):
    return (ref.cycles, ref.etiquettes, ref.colonnes, ref.statuts)


class ValideEtInvente(unittest.TestCase):
    def setUp(self):
        self.ref = rs.construire(JOUR)

    def test_valide_contre_l_ensemble_declare_du_jeu(self):
        for jour in JOURS[:30]:
            ref = rs.construire(jour)
            for variante in rs.VARIANTES:
                ref = rs.construire(jour, variante)
                self.assertEqual(list(fr.valider(ref, rs.etiquettes_declarees(jour))), [], (jour, variante))

    def test_toute_etiquette_du_referentiel_est_dans_l_ensemble_declare(self):
        declarees = rs.etiquettes_declarees(JOUR)
        for e in self.ref.etiquettes:
            self.assertIn(e.etiquette, declarees)

    def test_l_ensemble_declare_refuse_une_etiquette_etrangere(self):
        etrangere = fr.Etiquette("etiquette-hors-jeu", "up_merge", None, None)
        ref = fr.Referentiel(self.ref.cycles, (*self.ref.etiquettes, etrangere), self.ref.colonnes, self.ref.statuts, None)
        self.assertEqual(list(fr.valider(ref, rs.etiquettes_declarees(JOUR))), ["label_undeclared"])

    def test_etiquettes_colonnes_et_statuts_portent_le_prefixe_du_jeu(self):
        prefixe = rs.PREFIXE
        self.assertEqual(prefixe, jeu.PREFIXE_CLE)                 # le préfixe du jeu synthétique (clés SYN-<n>)
        for e in self.ref.etiquettes:
            self.assertTrue(e.etiquette.startswith(prefixe), e.etiquette)
        for c in self.ref.colonnes:
            self.assertTrue(c.nom.startswith(prefixe), c.nom)
        for s in self.ref.statuts:
            self.assertTrue(s.statut.startswith(prefixe), s.statut)
            self.assertTrue(s.colonne.startswith(prefixe), s.colonne)
        for e in rs.etiquettes_declarees(JOUR):
            self.assertTrue(e.startswith(prefixe), e)
        self.assertTrue(rs.STATUT_NON_ASSOCIE.startswith(prefixe))

    def test_composition_des_etiquettes(self):
        roles = [e.role for e in self.ref.etiquettes]
        for role in ROLES:
            self.assertIn(role, roles)
        self.assertEqual(roles.count("up_merge"), 2)
        self.assertEqual(roles.count("pilot_domain"), 1)
        self.assertEqual(roles.count("ready"), 1)
        self.assertEqual(roles.count("epic_review"), 1)
        self.assertEqual(roles.count("confirmation"), 2)
        self.assertEqual(sorted(e.sens for e in self.ref.etiquettes if e.role == "confirmation"), ["not_taken_in", "taken_in"])
        etiquettes_de_cycle = [e for e in self.ref.etiquettes if e.role == "cycle"]
        self.assertEqual(sorted(e.cycle_cle for e in etiquettes_de_cycle), sorted(c.cle for c in self.ref.cycles))
        for e in etiquettes_de_cycle:
            self.assertIn(e.cycle_cle, e.etiquette)                 # l'étiquette de cycle nomme sa clé

    def test_composition_des_colonnes_et_statuts(self):
        colonnes = self.ref.colonnes
        self.assertEqual(sum(1 for c in colonnes if c.depart), 1)
        self.assertEqual(sum(1 for c in colonnes if c.pret), 1)
        self.assertEqual(sum(1 for c in colonnes if c.revue_passee), 1)
        self.assertTrue(any(c.active for c in colonnes))
        self.assertFalse(any(c.pret and c.active for c in colonnes))
        self.assertEqual(sorted(c.position for c in colonnes), list(range(1, len(colonnes) + 1)))
        mappees = {s.colonne for s in self.ref.statuts}
        self.assertEqual(mappees, {c.nom for c in colonnes})        # au moins un statut par colonne

    def test_un_statut_du_jeu_n_est_associe_a_aucune_colonne(self):
        self.assertNotIn(rs.STATUT_NON_ASSOCIE, {s.statut for s in self.ref.statuts})

    def test_aucune_valeur_du_referentiel_ne_vient_des_reglages_de_flux(self):
        # chaînes inventées : jamais une clé de version, un nom de projet ou d'équipe : le préfixe du jeu et rien d'autre
        for e in self.ref.etiquettes:
            self.assertRegex(e.etiquette, r"^SYN-[A-Za-z0-9_.-]+$")


class AucunFichierDeFlux(unittest.TestCase):
    def test_la_construction_n_ouvre_aucun_fichier(self):
        ouverts: list[str] = []
        ouvrir = builtins.open

        def espion(chemin, *args, **kwargs):
            ouverts.append(str(chemin))
            return ouvrir(chemin, *args, **kwargs)

        with mock.patch.object(builtins, "open", espion), mock.patch.object(io, "open", espion), \
                mock.patch.object(Path, "open", lambda self, *a, **k: ouverts.append(str(self)) or ouvrir(self, *a, **k)), \
                mock.patch.object(Path, "read_text", lambda self, *a, **k: ouverts.append(str(self)) or ""), \
                mock.patch.object(os, "scandir", lambda *a, **k: ouverts.append(str(a)) or iter(())), \
                mock.patch.object(os, "listdir", lambda *a, **k: ouverts.append(str(a)) or []):
            for variante in rs.VARIANTES:
                rs.construire(JOUR, variante)
            rs.etiquettes_declarees(JOUR)
        sous_le_dossier_de_flux = [chemin for chemin in ouverts if "Flux-Lab" in chemin]
        self.assertEqual(sous_le_dossier_de_flux, [])
        self.assertEqual(ouverts, [])

    def test_source_sans_lecture_de_fichier_ni_chemin_de_flux(self):
        source = SOURCE.read_text(encoding="utf-8")
        for nom in ("Flux-Lab", "flux.yaml", "equipes-lisibles", "noms-sensibles", "organisation.yaml"):
            self.assertNotIn(nom, source, nom)
        interdits = {"open", "read_text", "read_bytes", "glob", "rglob", "listdir", "scandir", "iterdir", "walk", "load", "safe_load"}
        for noeud in ast.walk(ast.parse(source)):
            if isinstance(noeud, ast.Call):
                f = noeud.func
                nom = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
                self.assertNotIn(nom, interdits, f"ligne {noeud.lineno}")

    def test_imports_en_liste_blanche(self):
        autorises = {"__future__", "datetime", "flow_referential", "sys", "pathlib"}
        for noeud in ast.walk(ast.parse(SOURCE.read_text(encoding="utf-8"))):
            if isinstance(noeud, ast.Import):
                modules = [a.name for a in noeud.names]
            elif isinstance(noeud, ast.ImportFrom):
                modules = [noeud.module or ""]
            else:
                continue
            for module in modules:
                self.assertIn(module.split(".")[0], autorises, f"ligne {noeud.lineno} : import hors liste blanche : {module}")


SEGMENTS = ("definition", "ready", "implementation", "review_verification", "acceptance", "todo", "done")


def noms_du_jeu() -> dict:
    """Ce que `jeu_synthetique.main` passe au référentiel : les statuts de GROUPES avec leur catégorie, le type de défaut du jeu."""
    return {"statuts": {statut: categorie for _, _, categorie, statut, _ in jeu.GROUPES}, "type_defaut": jeu.TYPE_DEFAUT}


class DefinitionsDeFlux(unittest.TestCase):
    """Change flow-definitions-referential, tâche 2.3, conception D8 : les définitions synthétiques, pures, sans base.
    Les noms du jeu sont des paramètres (décision R-20261029-15) : les tests les construisent depuis le module du jeu."""

    def setUp(self):
        self.noms = noms_du_jeu()

    def test_les_deux_variantes_portent_les_memes_definitions(self):
        sans, avec = rs.construire(JOUR, noms_du_jeu=self.noms), rs.construire(JOUR, "validated", self.noms)
        for champ in ("statuts_flux", "types_non_planifies", "types_liens_bloquants"):
            self.assertTrue(getattr(sans, champ), champ)
            self.assertEqual(getattr(sans, champ), getattr(avec, champ), champ)

    def test_deterministes_pour_un_jour_et_valides(self):
        for jour in JOURS[:30]:
            for variante in rs.VARIANTES:
                for noms in (None, self.noms):
                    ref = rs.construire(jour, variante, noms)
                    self.assertEqual(ref, rs.construire(jour, variante, noms))
                    self.assertEqual(list(fr.valider(ref, rs.etiquettes_declarees(jour))), [], (jour, variante))

    def test_au_moins_un_statut_par_segment_avec_et_sans_les_noms_du_jeu(self):
        for noms in (None, self.noms):
            self.assertEqual({s.segment for s in rs.construire(JOUR, noms_du_jeu=noms).statuts_flux}, set(SEGMENTS))

    def test_drapeaux_egaux_a_ceux_de_definir_statut_avec_le_point_ready(self):
        for s in rs.construire(JOUR, noms_du_jeu=self.noms).statuts_flux:
            self.assertEqual(s, fr.definir_statut(s.statut, s.segment, "ready"))
            self.assertEqual((s.engage, s.file_prete), (s.segment == "ready", s.segment == "ready"))

    def test_un_type_non_planifie_de_genre_defaut_pris_dans_les_noms_du_jeu(self):
        ref = rs.construire(JOUR, noms_du_jeu=self.noms)
        self.assertEqual(ref.types_non_planifies, (fr.TypeNonPlanifie(jeu.TYPE_DEFAUT, "defect"),))
        self.assertIn(jeu.TYPE_DEFAUT, {t[1] for t in jeu.GROUPES})
        self.assertEqual(rs.construire(JOUR).types_non_planifies, (fr.TypeNonPlanifie(rs.TYPE_DEFAUT_INVENTE, "defect"),))

    def test_un_type_de_lien_par_sens_inventes_avec_le_prefixe(self):
        liens = rs.construire(JOUR, noms_du_jeu=self.noms).types_liens_bloquants
        self.assertEqual(sorted(t.sens for t in liens), ["blocks", "waits_for"])
        for t in liens:
            self.assertTrue(t.type.startswith(rs.PREFIXE), t.type)

    def test_statuts_du_jeu_gardes_et_noms_inventes_prefixes(self):
        noms = {s.statut for s in rs.construire(JOUR, noms_du_jeu=self.noms).statuts_flux}
        statuts_du_jeu = {g[3] for g in jeu.GROUPES}
        self.assertTrue(statuts_du_jeu <= noms)
        for nom in noms - statuts_du_jeu:
            self.assertTrue(nom.startswith(rs.PREFIXE), nom)
        for nom in {s.statut for s in rs.construire(JOUR).statuts_flux}:
            self.assertTrue(nom.startswith(rs.PREFIXE), nom)

    def test_chargement_ecrit_les_trois_tables_avant_la_ligne_d_etat(self):
        conn = FausseConnexion()
        rs.charger(conn, JOUR, noms_du_jeu=self.noms)
        ref = rs.construire(JOUR, noms_du_jeu=self.noms)
        tables = [s.split()[2] for s in conn.instructions if s.startswith("INSERT")]
        self.assertEqual(tables.count("flow.ref_flow_statuses"), len(ref.statuts_flux))
        self.assertEqual(tables.count("flow.ref_unplanned_types"), 1)
        self.assertEqual(tables.count("flow.ref_blocking_link_types"), 2)
        self.assertEqual(tables[-1], "flow.ref_state")


class FausseConnexion:
    """Enregistre les instructions et les bornes de la transaction ; répond le rôle d'import à SELECT current_user."""

    def __init__(self, utilisateur="pmzilla_flow"):
        self.utilisateur = utilisateur
        self.instructions: list[str] = []
        self.evenements: list[str] = []

    def transaction(self):
        conn = self

        class Transaction:
            def __enter__(self):
                conn.evenements.append("BEGIN")
                return self

            def __exit__(self, type_, valeur, trace):
                conn.evenements.append("ROLLBACK" if type_ else "COMMIT")
                return False

        return Transaction()

    def execute(self, sql, params=None):
        texte = " ".join(sql.split())
        self.instructions.append(texte)
        self.evenements.append(texte)
        return self

    def fetchone(self):
        return (self.utilisateur,)


class ChargementSansBase(unittest.TestCase):
    """Le chargement passe par la fonction d'écriture, sous le rôle d'import ; aucune connexion réelle."""

    def test_ecrit_le_referentiel_par_la_fonction_d_ecriture_sous_le_role_d_import(self):
        conn = FausseConnexion()
        rs.charger(conn, JOUR)
        ecritures = [s for s in conn.instructions if s.startswith(("INSERT", "DELETE", "UPDATE"))]
        self.assertTrue(ecritures)
        for sql in ecritures:
            self.assertRegex(sql, r"flow\.ref_(cycles|labels|dw_columns|dw_statuses|state|flow_statuses|unplanned_types|blocking_link_types)\b", sql)   # R-20261028-106
            self.assertFalse(sql.startswith("UPDATE"), sql)
        self.assertEqual(sum(1 for s in conn.instructions if s.startswith("INSERT INTO flow.ref_cycles")), 4)

    def test_variante_choisie_par_argument(self):
        for variante in rs.VARIANTES:
            conn = FausseConnexion()
            rs.charger(conn, JOUR, variante)
            self.assertTrue(conn.instructions)

    def test_sans_role_d_import_rien_n_est_ecrit(self):
        conn = FausseConnexion(utilisateur="postgres")
        with self.assertRaises(fr.ReferentielInvalide):
            rs.charger(conn, JOUR)
        self.assertEqual([s for s in conn.instructions if s.startswith(("INSERT", "DELETE"))], [])

    def test_etiquette_hors_de_la_liste_declaree_du_jeu_refusee_sans_ecriture(self):
        # décision R-20261028-108 : le chargeur passe à `ecrire` la liste déclarée du jeu (jamais vide, jamais les étiquettes du référentiel)
        normal = rs.construire(JOUR)
        etrangere = fr.Etiquette("SENTINELLE-ETIQUETTE", "up_merge", None, None)
        piege = fr.Referentiel(normal.cycles, (*normal.etiquettes, etrangere), normal.colonnes, normal.statuts, None)
        conn = FausseConnexion()
        with mock.patch.object(rs, "construire", return_value=piege):
            with self.assertRaises(fr.ReferentielInvalide) as refus:
                rs.charger(conn, JOUR)
        self.assertEqual(str(refus.exception), "référentiel des cycles invalide : label_undeclared")
        self.assertNotIn("SENTINELLE-ETIQUETTE", str(refus.exception))
        self.assertEqual([s for s in conn.instructions if s.startswith(("INSERT", "DELETE", "UPDATE"))], [])


class ChargementAvecBase(aide_base.AvecBase):
    """Sur la base jetable de bash tools/dbtest.sh (sautés sans DBTEST_PORT) : le référentiel chargé après le jeu, le rôle des vues refusé."""

    def charger(self, variante=rs.VARIANTE_DEFAUT):
        self.conn.commit()          # le chargeur veut une connexion au repos
        jeu.charger(self.conn, jeu.INSTANT_FIXE)
        rs.charger(self.conn, jeu.INSTANT_FIXE.date(), variante)
        self.conn.commit()

    def test_les_quatre_cycles_et_la_ligne_d_etat_sont_ecrits(self):
        self.charger()
        self.assertEqual(self.conn.execute("SELECT count(*) FROM flow.ref_cycles").fetchone()[0], 4)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM flow.ref_state").fetchone()[0], 1)
        self.assertIsNone(self.conn.execute("SELECT mapping_validated_on FROM flow.ref_state").fetchone()[0])
        attendu = len(rs.construire(jeu.INSTANT_FIXE.date()).etiquettes)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM flow.ref_labels").fetchone()[0], attendu)

    def test_variante_validee_porte_une_date(self):
        self.charger("validated")
        self.assertIsNotNone(self.conn.execute("SELECT mapping_validated_on FROM flow.ref_state").fetchone()[0])

    def test_deux_chargements_laissent_un_seul_referentiel(self):
        self.charger()
        self.charger("validated")
        self.assertEqual(self.conn.execute("SELECT count(*) FROM flow.ref_cycles").fetchone()[0], 4)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM flow.ref_state").fetchone()[0], 1)

    def test_les_definitions_sont_chargees_avec_le_jeu(self):
        self.charger()
        ref = rs.construire(jeu.INSTANT_FIXE.date())
        self.assertEqual(self.conn.execute("SELECT count(*) FROM flow.ref_flow_statuses").fetchone()[0], len(ref.statuts_flux))
        self.assertEqual(self.conn.execute("SELECT count(*) FROM flow.ref_unplanned_types").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM flow.ref_blocking_link_types").fetchone()[0], 2)

    def test_le_role_des_vues_ne_lit_aucune_table_des_definitions(self):
        self.charger()
        for table in ("ref_flow_statuses", "ref_unplanned_types", "ref_blocking_link_types"):
            with self.assertRaises(aide_base.db.psycopg.errors.InsufficientPrivilege):
                with self.conn.transaction():
                    self.conn.execute("SET LOCAL ROLE pmzilla_flow_views")
                    self.conn.execute(f"SELECT * FROM flow.{table}")

    def test_le_role_des_vues_ne_lit_aucune_table_du_referentiel(self):
        self.charger()
        for table in ("ref_cycles", "ref_labels", "ref_dw_columns", "ref_dw_statuses", "ref_state"):
            with self.assertRaises(aide_base.db.psycopg.errors.InsufficientPrivilege):
                with self.conn.transaction():
                    self.conn.execute("SET LOCAL ROLE pmzilla_flow_views")
                    self.conn.execute(f"SELECT * FROM flow.{table}")


if __name__ == "__main__":
    unittest.main()
