"""
Chargeur des définitions réelles de flux : tools/flow_definitions.py (change flow-definitions-loader, tâches 2.1 et 2.2, conception D1 à D5),
sans base. Données inventées seulement : aucun nom de statut, de type ni de lien réel dans ce fichier.

  - `construire_definitions` sans aucune clé (défauts lus par import), avec chaque clé, la traduction des noms de segments, les drapeaux
    égaux à `definir_statut`, un segment inconnu refusé, un type de lien dans les deux listes, des types non planifiés en double ;
  - `charger_definitions` avec une fausse connexion : une transaction, la garde d'abord, un seul appel d'`ecrire`, aucune écriture si une
    table des cycles contient une ligne, aucune lecture d'une autre table ;
  - la commande `load` : refus de session avant toute lecture, usage, réglages absents (aucun fichier créé), réglages refusés, référentiel
    refusé, garde, base injoignable (le type seul), essai à blanc sans connexion, chargement réel ; aucune valeur inventée dans les sorties.

    bash tests/run_all.sh flow_definitions
"""
from __future__ import annotations

import contextlib
import dataclasses
import io
import re
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import dependencies_jira as dep       # noqa: E402
import flow_definitions as fd          # noqa: E402
import flow_referential as fr          # noqa: E402
import flux_config as cfg              # noqa: E402
import history_common as commun        # noqa: E402

PREFIXE_INVALIDE = fr.MESSAGE_INVALIDE
SESSION = {fd.VARIABLE_CLAUDE_CODE: "1"}
# les sentinelles : jamais dans une sortie
S_STATUT, S_TYPE, S_BLOQUANT, S_ATTENTE = "t-sentinelle-statut", "t-sentinelle-type", "t-sentinelle-bloque", "t-sentinelle-attend"
SENTINELLES = (S_STATUT, S_TYPE, S_BLOQUANT, S_ATTENTE, "sentinelle")


def interne_complet() -> dict:
    """Réglages sous les noms internes, une valeur inventée à chaque clé de définition (point d'engagement : implementation)."""
    return cfg.to_internal({
        "segments": {"definition": ["T-Def A", "T-Def B"], "ready": [S_STATUT.upper()], "implementation": ["T-Impl"],
                     "review_verification": ["T-Rev"], "acceptance": ["T-Acc"]},
        "uncounted_segments": {"todo": ["T-Open"], "done": ["T-Fini", "T-Rejet"]},
        "commitment_point": "implementation", "defect_types": [S_TYPE, " T-Autre "],
        "blocking_link_types": [S_BLOQUANT, "T-Bloque 2"], "waiting_link_types": [S_ATTENTE]}, "flux.yaml")


def reglages_publics() -> dict:
    return {"segments": {"definition": ["T-Def A"], "ready": [S_STATUT], "implementation": ["T-Impl"],
                         "review_verification": ["T-Rev"], "acceptance": ["T-Acc"]},
            "uncounted_segments": {"todo": ["T-Open"], "done": ["T-Fini"]},
            "commitment_point": "ready", "defect_types": [S_TYPE],
            "blocking_link_types": [S_BLOQUANT], "waiting_link_types": [S_ATTENTE]}


class Construire(unittest.TestCase):
    def test_sans_aucune_cle_statuts_et_segments_des_defauts_du_code(self):
        statuts, _, _ = fd.construire_definitions({})
        segment_de, _calcules = commun.table_segments({})
        traduction = {"definition": "definition", "pret": "ready", "implementation": "implementation",
                      "revue_verification": "review_verification", "acceptation": "acceptance", "a_faire": "todo", "termine": "done"}
        self.assertEqual({s.statut: s.segment for s in statuts}, {e: traduction[seg] for e, seg in segment_de.items()})
        self.assertEqual(len(statuts), len(segment_de))

    def test_sans_aucune_cle_point_d_engagement_du_defaut_commun_et_drapeaux_de_la_fonction(self):
        statuts, _, _ = fd.construire_definitions({})
        self.assertEqual(commun.point_engagement({}), commun.POINT_ENGAGEMENT_PAR_DEFAUT)
        point = cfg.SEGMENTS[commun.POINT_ENGAGEMENT_PAR_DEFAUT]
        self.assertEqual(statuts, tuple(fr.definir_statut(s.statut, s.segment, point) for s in statuts))
        self.assertEqual([s.statut for s in statuts if s.engage], [s.statut for s in statuts if s.segment == point])
        self.assertEqual([s.statut for s in statuts if s.file_prete], [s.statut for s in statuts if s.segment == "ready"])

    def test_sans_aucune_cle_aucun_type_non_planifie(self):
        self.assertEqual(fd.construire_definitions({})[1], ())

    def test_sans_aucune_cle_types_de_liens_des_deux_constantes_avec_leur_sens(self):
        liens = fd.construire_definitions({})[2]
        self.assertEqual(tuple(t.type for t in liens if t.sens == "blocks"), cfg.TYPES_BLOQUANTS_PAR_DEFAUT)
        self.assertEqual(tuple(t.type for t in liens if t.sens == "waits_for"), cfg.TYPES_ATTENTE_PAR_DEFAUT)
        self.assertEqual(len(liens), len(cfg.TYPES_BLOQUANTS_PAR_DEFAUT) + len(cfg.TYPES_ATTENTE_PAR_DEFAUT))

    def test_chaque_cle_donnee_les_noms_sont_ceux_des_reglages(self):
        statuts, non_planifies, liens = fd.construire_definitions(interne_complet())
        self.assertEqual({s.statut: s.segment for s in statuts},
                         {"t-def a": "definition", "t-def b": "definition", S_STATUT: "ready", "t-impl": "implementation",
                          "t-rev": "review_verification", "t-acc": "acceptance", "t-open": "todo", "t-fini": "done", "t-rejet": "done"})
        self.assertEqual([(t.type, t.genre) for t in non_planifies], [(S_TYPE, "defect"), ("T-Autre", "defect")])
        self.assertEqual([(t.type, t.sens) for t in liens],
                         [(S_BLOQUANT, "blocks"), ("T-Bloque 2", "blocks"), (S_ATTENTE, "waits_for")])

    def test_les_noms_de_segments_passent_par_les_tables_de_flux_config(self):
        interne = interne_complet()
        statuts, _, _ = fd.construire_definitions(interne)
        segment_de, _ = commun.table_segments(interne)
        for s in statuts:
            self.assertEqual(s.segment, {**cfg.SEGMENTS, **cfg.UNCOUNTED}[segment_de[s.statut]])

    def test_point_d_engagement_donne_les_drapeaux_de_la_fonction(self):
        statuts, _, _ = fd.construire_definitions(interne_complet())
        self.assertEqual(statuts, tuple(fr.definir_statut(s.statut, s.segment, "implementation") for s in statuts))
        self.assertEqual({s.statut for s in statuts if s.engage}, {"t-impl"})
        self.assertEqual({s.statut for s in statuts if s.file_prete}, {S_STATUT})

    def test_segment_inconnu_refuse_sans_le_nommer(self):
        interne = cfg.to_internal({"segments": {"sentinelle_zz": ["t-etat-zz"]}}, "flux.yaml")
        with self.assertRaises(fr.ReferentielInvalide) as refus:
            fd.construire_definitions(interne)
        self.assertEqual(str(refus.exception), PREFIXE_INVALIDE + "flow_status_segment")
        for valeur in ("sentinelle_zz", "t-etat-zz"):
            self.assertNotIn(valeur, str(refus.exception))

    def test_point_d_engagement_inconnu_refuse(self):
        with self.assertRaises(fr.ReferentielInvalide) as refus:
            fd.construire_definitions({"point_engagement": "sentinelle_zz"})
        self.assertEqual(str(refus.exception), PREFIXE_INVALIDE + "commitment_flag")

    def test_point_d_engagement_hors_des_segments_calcules_refuse_comme_le_rapport(self):
        interne = cfg.to_internal({"segments": {"definition": ["t-etat-a"]}, "commitment_point": "implementation"}, "flux.yaml")
        with self.assertRaises(fr.ReferentielInvalide) as refus:
            fd.construire_definitions(interne)
        self.assertEqual(str(refus.exception), PREFIXE_INVALIDE + "commitment_flag")
        # le défaut commun (ready) n'est pas non plus un segment calculé de ces réglages
        with self.assertRaises(fr.ReferentielInvalide):
            fd.construire_definitions(cfg.to_internal({"segments": {"definition": ["t-etat-a"]}}, "flux.yaml"))

    def test_type_de_lien_dans_les_deux_listes_une_fois_bloquant_comme_le_rapport(self):
        interne = {"types_bloquants": ["T-Les-Deux", "T-Bloque"], "types_attente": ["t-les-deux", "T-Attend"]}
        liens = fd.construire_definitions(interne)[2]
        self.assertEqual([(t.type, t.sens) for t in liens],
                         [("T-Les-Deux", "blocks"), ("T-Bloque", "blocks"), ("T-Attend", "waits_for")])
        reglages = {"types_bloquants": interne["types_bloquants"], "types_attente": interne["types_attente"]}
        self.assertEqual(dep.role("T-Les-Deux", reglages), "bloque")
        for t in liens:
            self.assertEqual(dep.role(t.type, reglages), "bloque" if t.sens == "blocks" else "attend")

    def test_types_non_planifies_en_double_de_casse_refuses_par_la_validation(self):
        referentiel = fd.referentiel_des_definitions({"defect_types": ["T-Un", "t-UN"]})
        self.assertEqual(len(referentiel.types_non_planifies), 2)         # le constructeur ne cache pas l'erreur des réglages
        with self.assertRaises(fr.ReferentielInvalide) as refus:
            fd.verifier(referentiel)
        self.assertEqual(str(refus.exception), PREFIXE_INVALIDE + "unplanned_type")

    def test_la_partie_des_cycles_est_vide(self):
        referentiel = fd.referentiel_des_definitions({})
        self.assertEqual((referentiel.cycles, referentiel.etiquettes, referentiel.colonnes, referentiel.statuts, referentiel.valide_le),
                         ((), (), (), (), None))
        self.assertEqual(fr.valider(referentiel, ()), [])


class FausseConnexion:
    """Note chaque instruction et les évènements de transaction. `cycle_present` : réponse de la requête de la garde ; `utilisateur` : rôle."""

    def __init__(self, cycle_present: bool = False, utilisateur: str = "pmzilla_flow"):
        self.cycle_present, self.utilisateur = cycle_present, utilisateur
        self.instructions: list[str] = []
        self.evenements: list[str] = []
        self.fermee = self.validee = False

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
        self._derniere = texte
        return self

    def fetchone(self):
        return (self.cycle_present,) if self._derniere.startswith("SELECT EXISTS") else (self.utilisateur,)

    def commit(self):
        self.validee = True

    def close(self):
        self.fermee = True

    def ecritures(self) -> list[str]:
        return [s for s in self.instructions if re.match(r"(INSERT|DELETE|UPDATE)\b", s)]


class Charger(unittest.TestCase):
    def test_une_transaction_la_garde_d_abord_puis_ecrire_etat_en_dernier(self):
        conn = FausseConnexion()
        comptes = fd.charger_definitions(conn, interne_complet())
        self.assertEqual(comptes, (9, 2, 3))
        self.assertEqual(conn.evenements[0], "BEGIN")
        self.assertTrue(conn.evenements[1].startswith("LOCK TABLE"))
        self.assertTrue(conn.evenements[2].startswith("SELECT EXISTS"))
        self.assertEqual(conn.instructions[2], "SELECT current_user")
        self.assertEqual(conn.evenements[-1], "COMMIT")
        self.assertNotIn("ROLLBACK", conn.evenements)
        ecritures = conn.ecritures()
        self.assertTrue(ecritures[-1].startswith("INSERT INTO flow.ref_state"))
        self.assertEqual([s for s in ecritures if s.startswith("DELETE")],
                         [f"DELETE FROM flow.{t}" for t in fr.TABLES_A_VIDER])
        inseres = {m.group(1) for s in ecritures if (m := re.match(r"INSERT INTO flow\.(\w+)", s))}
        self.assertEqual(inseres, {"ref_flow_statuses", "ref_unplanned_types", "ref_blocking_link_types", "ref_state"})
        self.assertEqual(sum(1 for s in ecritures if s.startswith("INSERT")), 9 + 2 + 3 + 1)
        self.assertFalse(any(s.startswith("UPDATE") for s in conn.instructions))

    def test_la_garde_lit_les_quatre_tables_des_cycles_et_aucune_autre(self):
        conn = FausseConnexion()
        fd.charger_definitions(conn, {})
        lectures = [s for s in conn.instructions if not re.match(r"(INSERT|DELETE)\b", s)]
        quatre = {"ref_cycles", "ref_labels", "ref_dw_columns", "ref_dw_statuses"}
        self.assertEqual(lectures[0], "LOCK TABLE " + ", ".join(f"flow.{t}" for t in fd.TABLES_CYCLES) + " IN SHARE ROW EXCLUSIVE MODE")
        self.assertEqual(set(re.findall(r"flow\.(\w+)", lectures[0])), quatre)
        self.assertEqual(lectures[1].count("EXISTS"), 4)
        self.assertEqual(set(re.findall(r"FROM flow\.(\w+)", lectures[1])), quatre)
        self.assertEqual(lectures[2:], ["SELECT current_user"])

    def test_une_ligne_de_cycle_refuse_sans_aucune_ecriture(self):
        conn = FausseConnexion(cycle_present=True)
        with self.assertRaises(fd.CyclesDejaCharges) as refus:
            fd.charger_definitions(conn, interne_complet())
        self.assertEqual(str(refus.exception), "définitions de flux : référentiel des cycles déjà chargé (cycle_referential_present), "
                                               "rien n'est écrit")
        self.assertEqual(conn.ecritures(), [])
        self.assertEqual(len(conn.instructions), 2)              # le verrou, puis la requête de la garde
        self.assertEqual(conn.evenements[-1], "ROLLBACK")

    def test_un_referentiel_refuse_n_envoie_aucune_instruction(self):
        conn = FausseConnexion()
        with self.assertRaises(fr.ReferentielInvalide):
            fd.charger_definitions(conn, {"defect_types": ["a", "A"]})
        self.assertEqual(conn.instructions, [])

    def test_autre_role_refuse_avant_toute_ecriture(self):
        conn = FausseConnexion(utilisateur="postgres")
        with self.assertRaises(fr.ReferentielInvalide) as refus:
            fd.charger_definitions(conn, {})
        self.assertEqual(str(refus.exception), fr.MESSAGE_ROLE)
        self.assertEqual(conn.ecritures(), [])
        self.assertEqual(conn.evenements[-1], "ROLLBACK")


class Commande(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.addCleanup(self.dossier.cleanup)
        self.fichier = Path(self.dossier.name) / "flux.yaml"
        self.environ = {fd.VARIABLE_REGLAGES: str(self.fichier), "PATH": ""}
        self.ouvertures = 0
        self.base = FausseConnexion()

    def ouvrir(self):
        self.ouvertures += 1
        return self.base

    def ecrire(self, contenu: dict | str | None = None):
        self.fichier.write_text(contenu if isinstance(contenu, str) else yaml.safe_dump(contenu or reglages_publics()), encoding="utf-8")

    def lancer(self, *argv, environ=None, ouvrir=None):
        sortie, erreur = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
            code = fd.main(list(argv), self.environ if environ is None else environ, ouvrir or self.ouvrir)
        self.assertFalse([s for s in SENTINELLES if s in sortie.getvalue().lower() + erreur.getvalue().lower()],
                         "une sentinelle est dans une sortie")
        return code, sortie.getvalue(), erreur.getvalue()

    def test_session_refusee_avant_toute_lecture(self):
        self.ecrire()
        for argv in (("load",), ("load", "--dry-run"), ()):
            with self.subTest(argv=argv):
                code, sortie, erreur = self.lancer(*argv, environ={**self.environ, **SESSION})
                self.assertEqual((code, sortie), (3, ""))
                self.assertEqual(erreur.strip(), "définitions de flux : à lancer par l'utilisateur seul, dans le Terminal")
        self.assertEqual(self.ouvertures, 0)

    def test_session_refusee_meme_sans_reglages_et_sans_toucher_au_dossier(self):
        code, _, erreur = self.lancer("load", environ={**self.environ, **SESSION})
        self.assertEqual(code, 3)
        self.assertFalse(self.fichier.exists())

    def test_usage_option_inconnue_ou_sous_commande_absente(self):
        self.ecrire()
        for argv in (("load", "--inconnue"), (), ("autre",)):
            with self.subTest(argv=argv):
                code, _, erreur = self.lancer(*argv)
                self.assertEqual(code, 2)
                self.assertIn("usage", erreur.lower())
        self.assertEqual(self.ouvertures, 0)

    def test_reglages_absents_aucun_fichier_cree(self):
        code, sortie, erreur = self.lancer("load")
        self.assertEqual((code, sortie), (1, ""))
        self.assertEqual(erreur.strip(), "définitions de flux : réglages de flux absents")
        self.assertEqual(list(Path(self.dossier.name).iterdir()), [])
        self.assertEqual(self.ouvertures, 0)

    def test_reglages_illisibles_phrase_fixe_sans_chemin(self):
        self.fichier.write_bytes(b"\xff\xfe\x00invalide")                    # pas de l'UTF-8
        for argv in (("load", "--dry-run"), ("load",)):
            with self.subTest(argv=argv, cas="encodage"):
                code, sortie, erreur = self.lancer(*argv)
                self.assertEqual((code, sortie), (1, ""))
                self.assertEqual(erreur.strip(), "définitions de flux : réglages de flux illisibles")
        self.fichier.unlink()
        self.fichier.mkdir()                                                  # un dossier à la place du fichier
        code, sortie, erreur = self.lancer("load", "--dry-run")
        self.assertEqual((code, sortie), (1, ""))
        self.assertEqual(erreur.strip(), "définitions de flux : réglages de flux illisibles")
        self.assertNotIn(self.dossier.name, erreur)
        self.assertEqual(self.ouvertures, 0)

    def test_reglages_refuses_par_le_lecteur_strict(self):
        self.ecrire("segments: {}\nsegments: {}\n")
        code, sortie, erreur = self.lancer("load", "--dry-run")
        self.assertEqual((code, sortie), (1, ""))
        self.assertIn("segments", erreur)
        self.assertEqual(self.ouvertures, 0)

    def test_referentiel_refuse_par_la_validation(self):
        self.ecrire({**reglages_publics(), "defect_types": [S_TYPE, S_TYPE.upper()]})
        for argv in (("load", "--dry-run"), ("load",)):
            with self.subTest(argv=argv):
                code, sortie, erreur = self.lancer(*argv)
                self.assertEqual((code, sortie), (1, ""))
                self.assertEqual(erreur.strip(), PREFIXE_INVALIDE + "unplanned_type")
        self.assertEqual(self.ouvertures, 0)

    def test_referentiel_refuse_par_le_role(self):
        self.ecrire()
        self.base = FausseConnexion(utilisateur="postgres")
        code, sortie, erreur = self.lancer("load")
        self.assertEqual((code, sortie), (1, ""))
        self.assertEqual(erreur.strip(), fr.MESSAGE_ROLE)
        self.assertTrue(self.base.fermee)

    def test_garde_refus_code_1_phrase_fixe_rien_ecrit(self):
        self.ecrire()
        self.base = FausseConnexion(cycle_present=True)
        code, sortie, erreur = self.lancer("load")
        self.assertEqual((code, sortie), (1, ""))
        self.assertEqual(erreur.strip(), fd.MESSAGE_CYCLES_PRESENTS)
        self.assertEqual(self.base.ecritures(), [])
        self.assertTrue(self.base.fermee)

    def test_base_injoignable_le_type_seulement(self):
        self.ecrire()

        class Secret(Exception):
            pass

        def ouvrir():
            raise Secret("mot de passe sentinelle-secret")

        code, sortie, erreur = self.lancer("load", ouvrir=ouvrir)
        self.assertEqual((code, sortie), (1, ""))
        self.assertEqual(erreur.strip(), "définitions de flux : base injoignable (Secret)")

    def test_essai_a_blanc_sans_connexion(self):
        self.ecrire()
        code, sortie, erreur = self.lancer("load", "--dry-run")
        self.assertEqual(code, 0)
        self.assertEqual(sortie.strip(), "définitions de flux, essai à blanc : 7 statuts, 1 types non planifiés, "
                                         "2 types de liens bloquants ; rien n'est écrit")
        self.assertEqual(self.ouvertures, 0)

    def test_chargement_reel_affiche_les_comptes_et_la_ligne_des_cycles(self):
        self.ecrire()
        code, sortie, erreur = self.lancer("load")
        self.assertEqual(code, 0)
        self.assertEqual(sortie.splitlines(), ["définitions de flux chargées : 7 statuts, 1 types non planifiés, 2 types de liens bloquants",
                                               "référentiel des cycles : non chargé, ses tables restent vides"])
        self.assertEqual(self.ouvertures, 1)
        self.assertTrue(self.base.validee and self.base.fermee)
        self.assertEqual(sum(1 for s in self.base.ecritures() if s.startswith("INSERT INTO flow.ref_flow_statuses")), 7)

    def test_les_reglages_sont_lus_une_seule_fois(self):
        self.ecrire()
        lectures = []
        original = fd.lire_reglages
        fd.lire_reglages = lambda chemin: lectures.append(chemin) or original(chemin)
        try:
            self.lancer("load")
        finally:
            fd.lire_reglages = original
        self.assertEqual(len(lectures), 1)


class ColonneDeDepart(unittest.TestCase):
    """La composition « définitions seules » (conception D4) n'a aucune colonne : `valider` n'exige pas de colonne de départ sans colonne,
    et en exige toujours une seule quand il y a des colonnes (la règle de cycle-referential-schema reste entière pour un référentiel réel)."""

    def test_aucune_colonne_aucun_constat(self):
        self.assertEqual(fr.valider(fd.referentiel_des_definitions({}), ()), [])

    def test_des_colonnes_sans_depart_ou_avec_deux_departs_restent_refusees(self):
        colonnes = (fr.Colonne("t-a", 1, False, False, False, False), fr.Colonne("t-b", 2, False, False, False, False))
        referentiel = fd.referentiel_des_definitions({})
        self.assertEqual(fr.valider(dataclasses.replace(referentiel, colonnes=colonnes), ()), ["start_column"])
        deux = tuple(dataclasses.replace(c, depart=True) for c in colonnes)
        self.assertEqual(fr.valider(dataclasses.replace(referentiel, colonnes=deux), ()), ["start_column"])

    def test_une_partie_des_cycles_non_vide_sans_colonne_de_depart_reste_refusee(self):
        referentiel = fd.referentiel_des_definitions({})
        autres = {"cycles": (fr.Cycle("2099-C1", date(2099, 1, 5), date(2099, 2, 27)),),
                  "etiquettes": (fr.Etiquette("t-up", "up_merge", None, None),),
                  "statuts": (fr.Statut("t-st", "t-col"),),
                  "valide_le": date(2099, 1, 1)}
        for champ, valeur in autres.items():
            with self.subTest(champ=champ):
                constats = fr.valider(dataclasses.replace(referentiel, **{champ: valeur}), {"t-up"})
                self.assertIn("start_column", constats)


class Source(unittest.TestCase):
    def setUp(self):
        self.texte = (Path(fd.__file__)).read_text(encoding="utf-8")

    def test_aucune_instruction_update_ni_ecriture_hors_ecrire(self):
        code = re.sub(r'""".*?"""', "", self.texte, flags=re.S).replace("sys.path.insert(", "")
        self.assertNotRegex(code, r"(?i)\b(INSERT|UPDATE|DELETE)\b")

    def test_aucun_drapeau_calcule_ici(self):
        self.assertNotRegex(self.texte, r"StatutFlux\(")
        self.assertIn("definir_statut", self.texte)


if __name__ == "__main__":
    unittest.main()
