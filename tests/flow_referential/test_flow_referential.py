"""
Tests de tools/flow_referential.py (change cycle-referential-schema, tâche 2.1, conception D5 et D7), sans base de données :
`valider` rend chaque code de D5 sur un référentiel minimal qui casse une seule règle, et rien sur un référentiel valide ;
`ecrire`, avec une fausse connexion, vérifie le rôle d'abord, ne fait aucun UPDATE, supprime puis insère dans une seule
transaction, l'état en dernier, et annule sur un insert qui échoue ; aucun message de refus ne porte une valeur (chaînes sentinelles).

    bash tests/run_all.sh flow_referential
"""
from __future__ import annotations

import dataclasses
import re
import sys
import unittest
from datetime import date
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flow_referential as fr  # noqa: E402

SOURCE = RACINE / "tools" / "flow_referential.py"
CODES = ("cycle_key_form", "cycle_dates", "cycle_duplicate", "label_role", "label_duplicate", "label_undeclared",
         "label_cycle_key", "confirmation_meaning", "single_label_role", "column_duplicate", "start_column", "ready_column",
         "status_column",
         # ajout d'éléments nommés à une liste fermée (R-20261028-106) : les six codes du change flow-definitions-referential, conception D4
         "flow_status_duplicate", "flow_status_segment", "commitment_flag", "ready_flag", "unplanned_type", "blocking_link_type")
PREFIXE_MESSAGE = "référentiel des cycles invalide : "
MESSAGE_ROLE = "référentiel des cycles : rôle d'écriture inattendu"
SENTINELLES = ("SENTINELLE-CLE", "SENTINELLE-ETIQUETTE", "SENTINELLE-STATUT", "SENTINELLE-COLONNE", "2099-01-05", "2099-03-02")


def valide() -> fr.Referentiel:
    """Un référentiel valide, de valeurs inventées : deux cycles, une étiquette par rôle (deux up_merge, une par cycle, deux confirmations),
    quatre colonnes (départ actif, revue passée active, Ready non active, une colonne simple), des statuts dont un par colonne."""
    return fr.Referentiel(
        cycles=(fr.Cycle("2099-C1", date(2099, 1, 5), date(2099, 3, 2)),
                fr.Cycle("2099-C2", date(2099, 3, 9), date(2099, 5, 4))),
        etiquettes=(fr.Etiquette("t-up-1", "up_merge", None, None),
                    fr.Etiquette("t-up-2", "up_merge", None, None),
                    fr.Etiquette("t-cycle-1", "cycle", "2099-C1", None),
                    fr.Etiquette("t-cycle-2", "cycle", "2099-C2", None),
                    fr.Etiquette("t-revue", "epic_review", None, None),
                    fr.Etiquette("t-domaine", "pilot_domain", None, None),
                    fr.Etiquette("t-pret", "ready", None, None),
                    fr.Etiquette("t-conf-oui", "confirmation", None, "taken_in"),
                    fr.Etiquette("t-conf-non", "confirmation", None, "not_taken_in")),
        colonnes=(fr.Colonne("t-col-a", 1, True, False, False, True),
                  fr.Colonne("t-col-b", 2, False, True, False, True),
                  fr.Colonne("t-col-c", 3, False, False, True, False),
                  fr.Colonne("t-col-d", 4, False, False, False, False)),
        statuts=(fr.Statut("t-st-a", "t-col-a"), fr.Statut("t-st-b", "t-col-b"), fr.Statut("t-st-c", "t-col-c"),
                 fr.Statut("t-st-d", "t-col-d")),
        valide_le=None)


def declarees(ref: fr.Referentiel) -> set[str]:
    return {e.etiquette for e in ref.etiquettes}


def remplacer(ref: fr.Referentiel, champ: str, indice: int, **changements):
    liste = list(getattr(ref, champ))
    liste[indice] = dataclasses.replace(liste[indice], **changements)
    return dataclasses.replace(ref, **{champ: tuple(liste)})


def ajouter(ref: fr.Referentiel, champ: str, element):
    return dataclasses.replace(ref, **{champ: (*getattr(ref, champ), element)})


class Valider(unittest.TestCase):
    def constats(self, ref: fr.Referentiel, declare=None) -> list[str]:
        return list(fr.valider(ref, declarees(ref) if declare is None else declare))

    def test_les_codes_et_leur_ordre_sont_ceux_de_la_conception(self):
        self.assertEqual(tuple(fr.CODES), CODES)

    def test_referentiel_valide_ne_donne_rien(self):
        self.assertEqual(self.constats(valide()), [])

    def test_referentiel_vide_de_cycles_n_est_pas_refuse_par_les_regles_de_cycle(self):
        # sans cycle, rien de la table des cycles n'est cassé ; les étiquettes de cycle n'ont alors aucune clé à citer
        ref = dataclasses.replace(valide(), cycles=(), etiquettes=tuple(e for e in valide().etiquettes if e.role != "cycle"))
        self.assertEqual(self.constats(ref), [])

    def test_cycle_key_form(self):
        for cle in ("12.3", "2099-C7", "2099-C0", "99-C1", "2099-eoy", "2099-C10", "", "2099-C1 "):
            with self.subTest(cle=cle):
                ref = remplacer(valide(), "cycles", 0, cle=cle)
                ref = remplacer(ref, "etiquettes", 2, cycle_cle=cle)
                self.assertEqual(self.constats(ref), ["cycle_key_form"])

    def test_cycle_key_form_acceptee(self):
        for cle in ("2099-C1", "2099-C6", "2099-EOY"):
            with self.subTest(cle=cle):
                ref = remplacer(valide(), "cycles", 0, cle=cle)
                ref = remplacer(ref, "etiquettes", 2, cycle_cle=cle)
                self.assertEqual(self.constats(ref), [])

    def test_cycle_dates(self):
        ref = remplacer(valide(), "cycles", 0, fin=date(2098, 12, 31))
        self.assertEqual(self.constats(ref), ["cycle_dates"])

    def test_cycle_d_un_seul_jour_accepte(self):
        ref = remplacer(valide(), "cycles", 0, fin=date(2099, 1, 5))
        self.assertEqual(self.constats(ref), [])

    def test_cycle_duplicate(self):
        ref = ajouter(valide(), "cycles", fr.Cycle("2099-C1", date(2099, 6, 1), date(2099, 7, 1)))
        self.assertEqual(self.constats(ref), ["cycle_duplicate"])

    def test_label_role(self):
        ref = remplacer(valide(), "etiquettes", 4, role="inconnu")
        self.assertEqual(self.constats(ref), ["label_role"])

    def test_label_duplicate(self):
        ref = ajouter(valide(), "etiquettes", fr.Etiquette("t-up-1", "up_merge", None, None))
        self.assertEqual(self.constats(ref), ["label_duplicate"])

    def test_label_undeclared(self):
        ref = valide()
        self.assertEqual(self.constats(ref, declare=declarees(ref) - {"t-revue"}), ["label_undeclared"])

    def test_label_undeclared_une_seule_fois_par_etiquette_hors_ensemble(self):
        ref = valide()
        self.assertEqual(self.constats(ref, declare=set()), ["label_undeclared"])

    def test_label_cycle_key_sur_un_autre_role(self):
        ref = remplacer(valide(), "etiquettes", 4, cycle_cle="2099-C1")
        self.assertEqual(self.constats(ref), ["label_cycle_key"])

    def test_label_cycle_key_absente_des_cycles(self):
        ref = remplacer(valide(), "etiquettes", 2, cycle_cle="2099-C5")
        self.assertEqual(self.constats(ref), ["label_cycle_key"])

    def test_confirmation_meaning_absent(self):
        ref = remplacer(valide(), "etiquettes", 7, sens=None)
        self.assertEqual(self.constats(ref), ["confirmation_meaning"])

    def test_confirmation_meaning_invalide(self):
        ref = remplacer(valide(), "etiquettes", 7, sens="autre")
        self.assertEqual(self.constats(ref), ["confirmation_meaning"])

    def test_confirmation_meaning_sur_un_autre_role(self):
        ref = remplacer(valide(), "etiquettes", 6, sens="taken_in")
        self.assertEqual(self.constats(ref), ["confirmation_meaning"])

    def test_single_label_role_domaine(self):
        ref = ajouter(valide(), "etiquettes", fr.Etiquette("t-domaine-bis", "pilot_domain", None, None))
        self.assertEqual(self.constats(ref), ["single_label_role"])

    def test_single_label_role_ready(self):
        ref = ajouter(valide(), "etiquettes", fr.Etiquette("t-pret-bis", "ready", None, None))
        self.assertEqual(self.constats(ref), ["single_label_role"])

    def test_column_duplicate_nom(self):
        ref = ajouter(valide(), "colonnes", fr.Colonne("t-col-d", 5, False, False, False, False))
        self.assertEqual(self.constats(ref), ["column_duplicate"])

    def test_column_duplicate_position(self):
        ref = remplacer(valide(), "colonnes", 3, position=1)
        self.assertEqual(self.constats(ref), ["column_duplicate"])

    def test_column_duplicate_position_sous_1(self):
        ref = remplacer(valide(), "colonnes", 3, position=0)
        self.assertEqual(self.constats(ref), ["column_duplicate"])

    def test_start_column_aucune(self):
        ref = remplacer(valide(), "colonnes", 0, depart=False)
        self.assertEqual(self.constats(ref), ["start_column"])

    def test_start_column_deux(self):
        ref = remplacer(valide(), "colonnes", 3, depart=True)
        self.assertEqual(self.constats(ref), ["start_column"])

    def test_ready_column_deux(self):
        ref = remplacer(valide(), "colonnes", 3, pret=True)
        self.assertEqual(self.constats(ref), ["ready_column"])

    def test_ready_column_active(self):
        ref = remplacer(valide(), "colonnes", 2, active=True)
        self.assertEqual(self.constats(ref), ["ready_column"])

    def test_status_column_colonne_non_declaree(self):
        ref = remplacer(valide(), "statuts", 3, colonne="t-col-z")
        self.assertEqual(self.constats(ref), ["status_column"])

    def test_status_column_statut_donne_deux_fois(self):
        ref = ajouter(valide(), "statuts", fr.Statut("t-st-a", "t-col-b"))
        self.assertEqual(self.constats(ref), ["status_column"])

    def test_aucun_constat_ne_porte_une_valeur(self):
        ref = remplacer(valide(), "cycles", 0, cle="SENTINELLE-CLE")
        for constat in self.constats(ref, declare=set()):
            self.assertIn(constat, CODES)

    def test_plusieurs_constats_dans_l_ordre_de_la_table(self):
        ref = remplacer(valide(), "cycles", 0, cle="12.3")
        ref = remplacer(ref, "etiquettes", 2, cycle_cle="12.3")
        ref = ajouter(ref, "etiquettes", fr.Etiquette("t-pret-bis", "ready", None, None))
        ref = remplacer(ref, "colonnes", 0, depart=False)
        ref = ajouter(ref, "statuts", fr.Statut("t-st-a", "t-col-b"))
        self.assertEqual(self.constats(ref), ["cycle_key_form", "single_label_role", "start_column", "status_column"])

    def test_chaque_code_n_apparait_qu_une_fois(self):
        ref = ajouter(valide(), "cycles", fr.Cycle("2099-C1", date(2099, 6, 1), date(2099, 7, 1)))
        ref = ajouter(ref, "cycles", fr.Cycle("2099-C1", date(2099, 8, 1), date(2099, 9, 1)))
        self.assertEqual(self.constats(ref), ["cycle_duplicate"])


class FausseConnexion:
    """Enregistre chaque instruction (`instructions`) et, à part, le début et la fin de la transaction (`evenements`).
    `utilisateur` : ce que répond SELECT current_user ; `echec_sur` : motif d'une instruction qui lève."""

    def __init__(self, utilisateur: str = "pmzilla_flow", echec_sur: str | None = None):
        self.utilisateur = utilisateur
        self.echec_sur = echec_sur
        self.instructions: list[str] = []
        self.parametres: list = []
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
        self.parametres.append(params)
        self.evenements.append(texte)
        if self.echec_sur and re.search(self.echec_sur, texte):
            raise RuntimeError("insert refusé (faux)")
        self._derniere = texte
        return self

    def fetchone(self):
        return (self.utilisateur,)

    def ecritures(self) -> list[str]:
        return [sql for sql in self.instructions if re.match(r"(INSERT|DELETE|UPDATE)\b", sql)]


class Ecrire(unittest.TestCase):
    def test_role_verifie_d_abord_et_refus_d_un_autre_role_avant_toute_ecriture(self):
        conn = FausseConnexion(utilisateur="postgres")
        ref = valide()
        with self.assertRaises(fr.ReferentielInvalide) as refus:
            fr.ecrire(conn, ref, declarees(ref))
        self.assertEqual(str(refus.exception), MESSAGE_ROLE)
        self.assertEqual(conn.instructions, ["SELECT current_user"])
        self.assertEqual(conn.ecritures(), [])

    def test_le_role_d_ecriture_est_celui_de_l_import(self):
        self.assertEqual(fr.ROLE_ECRITURE, "pmzilla_flow")

    def test_referentiel_invalide_refuse_sans_aucune_instruction(self):
        conn = FausseConnexion()
        ref = remplacer(valide(), "cycles", 0, cle="12.3")
        ref = remplacer(ref, "etiquettes", 2, cycle_cle="12.3")
        ref = ajouter(ref, "etiquettes", fr.Etiquette("t-pret-bis", "ready", None, None))
        with self.assertRaises(fr.ReferentielInvalide) as refus:
            fr.ecrire(conn, ref, declarees(ref))
        self.assertEqual(str(refus.exception), PREFIXE_MESSAGE + "cycle_key_form, single_label_role")
        self.assertEqual(conn.instructions, [])
        self.assertEqual(conn.evenements, [])

    def test_etiquette_hors_de_l_ensemble_declare_refusee_sans_instruction_et_sans_son_texte(self):
        ref = ajouter(valide(), "etiquettes", fr.Etiquette("SENTINELLE-ETIQUETTE", "up_merge", None, None))
        conn = FausseConnexion()
        with self.assertRaises(fr.ReferentielInvalide) as refus:
            fr.ecrire(conn, ref, declarees(valide()))
        self.assertEqual(str(refus.exception), PREFIXE_MESSAGE + "label_undeclared")
        self.assertNotIn("SENTINELLE-ETIQUETTE", str(refus.exception))
        self.assertEqual(conn.instructions, [])

    def test_etiquettes_toutes_declarees_aucun_constat_et_ecriture(self):
        ref = valide()
        self.assertNotIn("label_undeclared", fr.valider(ref, declarees(ref)))
        conn = FausseConnexion()
        fr.ecrire(conn, ref, declarees(ref))
        self.assertTrue(conn.ecritures())

    def test_refus_sans_aucune_valeur_dans_le_message(self):
        ref = fr.Referentiel(
            cycles=(fr.Cycle("SENTINELLE-CLE", date(2099, 3, 2), date(2099, 1, 5)),),
            etiquettes=(fr.Etiquette("SENTINELLE-ETIQUETTE", "up_merge", None, None),),
            colonnes=(fr.Colonne("SENTINELLE-COLONNE", 1, True, False, False, True),),
            statuts=(fr.Statut("SENTINELLE-STATUT", "SENTINELLE-COLONNE-ABSENTE"),),
            valide_le=date(2099, 3, 2))
        with self.assertRaises(fr.ReferentielInvalide) as refus:
            fr.ecrire(FausseConnexion(), ref, set())
        message = str(refus.exception)
        self.assertTrue(message.startswith(PREFIXE_MESSAGE), message)
        for sentinelle in SENTINELLES + ("SENTINELLE-COLONNE-ABSENTE",):
            self.assertNotIn(sentinelle, message)
        codes = message[len(PREFIXE_MESSAGE):].split(", ")
        self.assertEqual(codes, [c for c in CODES if c in codes])      # dans l'ordre de la table, sans doublon
        self.assertEqual(len(codes), len(set(codes)))
        self.assertTrue(set(codes) <= set(CODES))

    def test_aucun_update_supprime_puis_insere_dans_une_transaction_l_etat_en_dernier(self):
        conn = FausseConnexion()
        ref = valide()
        fr.ecrire(conn, ref, declarees(ref))
        ecritures = conn.ecritures()
        for sql in conn.instructions:
            self.assertNotRegex(sql, r"(?i)\bUPDATE\b", sql)
        suppressions = [i for i, sql in enumerate(ecritures) if sql.startswith("DELETE")]
        insertions = [i for i, sql in enumerate(ecritures) if sql.startswith("INSERT")]
        self.assertTrue(suppressions and insertions)
        self.assertLess(max(suppressions), min(insertions))               # toutes les suppressions avant la première insertion
        tables_supprimees = {re.search(r"flow\.(ref_\w+)", ecritures[i]).group(1) for i in suppressions}
        # ajout d'éléments nommés à une liste fermée (R-20261028-106) : les trois tables de flow-definitions-referential
        self.assertEqual(tables_supprimees, {"ref_cycles", "ref_labels", "ref_dw_columns", "ref_dw_statuses", "ref_state",
                                             "ref_flow_statuses", "ref_unplanned_types", "ref_blocking_link_types"})
        ordre_sup = [re.search(r"flow\.(ref_\w+)", ecritures[i]).group(1) for i in suppressions]
        self.assertLess(ordre_sup.index("ref_dw_statuses"), ordre_sup.index("ref_dw_columns"))       # les enfants d'abord
        self.assertLess(ordre_sup.index("ref_labels"), ordre_sup.index("ref_cycles"))
        ordre_ins = [re.search(r"flow\.(ref_\w+)", ecritures[i]).group(1) for i in insertions]
        self.assertEqual(ordre_ins[-1], "ref_state")
        self.assertEqual(ordre_ins.count("ref_state"), 1)
        self.assertLess(ordre_ins.index("ref_cycles"), ordre_ins.index("ref_labels"))               # les parents d'abord
        self.assertLess(ordre_ins.index("ref_dw_columns"), ordre_ins.index("ref_dw_statuses"))
        self.assertEqual(len(insertions), 1 + len(ref.cycles) + len(ref.etiquettes) + len(ref.colonnes) + len(ref.statuts))
        # une seule transaction : tout se passe entre BEGIN et COMMIT, le rôle a été lu avant
        self.assertEqual(conn.instructions[0], "SELECT current_user")
        self.assertEqual(conn.evenements.count("BEGIN"), 1)
        self.assertEqual(conn.evenements[-1], "COMMIT")
        debut = conn.evenements.index("BEGIN")
        self.assertEqual([e for e in conn.evenements[debut + 1:-1] if re.match(r"(INSERT|DELETE)", e)], ecritures)

    def test_instant_de_chargement_pris_sur_l_horloge_de_la_base(self):
        conn = FausseConnexion()
        ref = valide()
        fr.ecrire(conn, ref, declarees(ref))
        etat = [sql for sql in conn.instructions if sql.startswith("INSERT INTO flow.ref_state")]
        self.assertEqual(len(etat), 1)
        self.assertRegex(etat[0], r"(?i)\bnow\(\)")

    def test_la_date_de_validation_est_ecrite_dans_l_etat(self):
        conn = FausseConnexion()
        ref = dataclasses.replace(valide(), valide_le=date(2099, 2, 2))
        fr.ecrire(conn, ref, declarees(ref))
        indice = next(i for i, sql in enumerate(conn.instructions) if sql.startswith("INSERT INTO flow.ref_state"))
        self.assertIn(date(2099, 2, 2), tuple(conn.parametres[indice]))

    def test_insert_qui_echoue_annule_tout_et_n_ecrit_pas_l_etat(self):
        conn = FausseConnexion(echec_sur=r"^INSERT INTO flow\.ref_labels")
        ref = valide()
        with self.assertRaises(RuntimeError):
            fr.ecrire(conn, ref, declarees(ref))
        self.assertEqual(conn.evenements[-1], "ROLLBACK")
        self.assertNotIn("COMMIT", conn.evenements)
        self.assertFalse([sql for sql in conn.instructions if sql.startswith("INSERT INTO flow.ref_state")])


class Source(unittest.TestCase):
    """Garde statique : pas de ligne de commande en partie 1, aucune instruction UPDATE, aucune lecture de fichier."""

    def setUp(self):
        self.texte = SOURCE.read_text(encoding="utf-8")

    def test_aucune_ligne_de_commande(self):
        self.assertNotIn("__main__", self.texte)
        self.assertNotIn("argparse", self.texte)

    def test_aucune_instruction_update(self):
        self.assertNotRegex(self.texte, r"(?i)['\"]\s*UPDATE\b")

    def test_aucune_lecture_de_fichier_ni_connexion(self):
        for mot in ("open(", "read_text", "psycopg", "subprocess", "yaml"):
            self.assertNotIn(mot, self.texte, mot)


if __name__ == "__main__":
    unittest.main()
