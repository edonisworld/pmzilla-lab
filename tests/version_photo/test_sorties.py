"""
Date de sortie et drapeau des versions dans le registre de la photo (change version-release-date, tâches 3.1, 3.2 ; spec jira-flow-version-photo
« Release dates filled from the stored current versions »). Magasin en mémoire et fausse connexion : aucune base.
"""
import datetime as dt
import unittest

from aide_version_photo import MARQUES, Espace, MagasinMemoire, defaut, jour, vp
from test_magasin_fausse_base import FausseConnexion
from version_photo_messages import CATALOGS
from messages import check_catalogs

V, W = "zzversion-a", "zzversion-b"
D1, D2 = dt.date(2029, 7, 14), dt.date(2029, 8, 1)


class FonctionPure(unittest.TestCase):
    """Design D5 : même valeur sur chaque ligne, sinon nulle et le nom compte comme divergent."""

    def test_meme_date_et_meme_drapeau_sur_chaque_ligne(self):
        attributs, divergents = vp.attributs_de_sortie([(V, D1, True), (V, D1, True), (V, D1, True)])
        self.assertEqual((attributs, divergents), ({V: (D1, True)}, 0))

    def test_nul_sur_chaque_ligne_reste_nul_sans_divergence(self):
        self.assertEqual(vp.attributs_de_sortie([(V, None, None), (V, None, None)]), ({V: (None, None)}, 0))

    def test_dates_differentes_donnent_une_date_nulle_et_une_divergence(self):
        attributs, divergents = vp.attributs_de_sortie([(V, D1, True), (V, D2, True)])
        self.assertEqual((attributs, divergents), ({V: (None, True)}, 1))

    def test_une_date_et_un_nul_divergent(self):
        self.assertEqual(vp.attributs_de_sortie([(V, D1, None), (V, None, None)]), ({V: (None, None)}, 1))

    def test_drapeaux_differents_donnent_un_drapeau_nul(self):
        self.assertEqual(vp.attributs_de_sortie([(V, D1, True), (V, D1, False)]), ({V: (D1, None)}, 1))

    def test_date_et_drapeau_divergents_comptent_le_nom_une_fois(self):
        attributs, divergents = vp.attributs_de_sortie([(V, D1, True), (V, D2, False), (V, D2, True)])
        self.assertEqual((attributs, divergents), ({V: (None, None)}, 1))

    def test_les_noms_sont_independants(self):
        attributs, divergents = vp.attributs_de_sortie([(V, D1, True), (W, D1, False), (W, D2, False), (V, D1, True)])
        self.assertEqual((attributs, divergents), ({V: (D1, True), W: (None, False)}, 1))

    def test_aucune_ligne(self):
        self.assertEqual(vp.attributs_de_sortie([]), ({}, 0))

    def test_aucune_estimation_une_date_nulle_reste_nulle(self):
        attributs, _ = vp.attributs_de_sortie([(V, None, False)])
        self.assertIsNone(attributs[V][0])


class TicketsHorsExport(unittest.TestCase):
    """Décision de l'auteur du 2026-10-23 (design D5) : une ligne dont le ticket est sorti de l'export (4e valeur vraie) ne compte plus."""

    def test_version_reportee_la_nouvelle_date_remplace_l_ancienne_sans_conflit(self):
        lignes = [(V, D1, False, True), (V, D2, False, False), (V, D2, False, False)]
        self.assertEqual(vp.attributs_de_sortie(lignes), ({V: (D2, False)}, 0))

    def test_drapeau_porte_par_les_tickets_de_l_export_remplace_celui_du_ticket_sorti(self):
        lignes = [(V, D1, False, True), (V, D1, True, False)]
        self.assertEqual(vp.attributs_de_sortie(lignes), ({V: (D1, True)}, 0))

    def test_plus_aucun_ticket_de_l_export_le_nom_n_est_pas_ecrit_donc_garde_sa_derniere_valeur(self):
        self.assertEqual(vp.attributs_de_sortie([(V, D1, True, True), (V, D1, True, True)]), ({}, 0))

    def test_le_conflit_ne_se_declare_qu_entre_tickets_de_l_export(self):
        lignes = [(V, D1, True, True), (V, D2, True, False), (V, D1, True, False)]
        self.assertEqual(vp.attributs_de_sortie(lignes), ({V: (None, True)}, 1))

    def test_un_ticket_sorti_seul_ne_cree_aucun_conflit(self):
        lignes = [(V, D1, True, True), (V, D2, False, True), (W, D1, True, False)]
        self.assertEqual(vp.attributs_de_sortie(lignes), ({W: (D1, True)}, 0))


def un_defaut(**remplacements):
    base = dict(cree="2026-01-05", resolu="2026-08-12", affects={V}, fix={V}, periodes=[(V, jour("2026-08-12"), None)], type_="zzdefaut",
                equipe="zzequipe-alpha")
    base.update(remplacements)
    return defaut(**base)


class RegistreEcrit(Espace):
    def test_take_ecrit_date_et_drapeau_dans_le_registre(self):
        magasin = MagasinMemoire([un_defaut()], sorties=[(V, D1, True), (V, D1, True)])
        code, _, erreur, _, _ = self.lancer("take", magasin=magasin)
        self.assertEqual(code, 0, erreur)
        self.assertEqual((magasin.etat["versions"][V]["release_date"], magasin.etat["versions"][V]["released"]), (D1, True))

    def test_reconstruct_ecrit_date_et_drapeau_dans_le_registre(self):
        magasin = MagasinMemoire([un_defaut()], sorties=[(V, D1, False)])
        code, _, erreur, _, _ = self.lancer("reconstruct", magasin=magasin)
        self.assertEqual(code, 0, erreur)
        self.assertEqual((magasin.etat["versions"][V]["release_date"], magasin.etat["versions"][V]["released"]), (D1, False))

    def test_une_version_que_seuls_des_tickets_hors_defaut_portent_entre_au_registre(self):
        magasin = MagasinMemoire([un_defaut()], sorties=[(V, D1, True), (W, D2, False)])
        self.lancer("take", magasin=magasin)
        self.assertEqual(magasin.etat["versions"][W], {"no": 2, "release_date": D2, "released": False})

    def test_une_version_purgee_garde_ses_dernieres_valeurs(self):
        magasin = MagasinMemoire([un_defaut()], sorties=[(V, D1, True), (W, D2, True)])
        self.lancer("reconstruct", magasin=magasin)
        magasin.sorties = [(V, D1, True)]                                          # W n'est plus portée par aucun ticket stocké
        self.lancer("take", magasin=magasin)
        self.assertEqual((magasin.etat["versions"][W]["release_date"], magasin.etat["versions"][W]["released"]), (D2, True))

    def test_la_date_se_corrige_et_se_deplace(self):
        magasin = MagasinMemoire([un_defaut()], sorties=[(V, D1, False)])
        self.lancer("reconstruct", magasin=magasin)
        magasin.sorties = [(V, D2, True)]
        self.lancer("take", magasin=magasin)
        self.assertEqual((magasin.etat["versions"][V]["release_date"], magasin.etat["versions"][V]["released"]), (D2, True))

    def test_version_reportee_le_registre_prend_la_nouvelle_date_sans_conflit(self):
        magasin = MagasinMemoire([un_defaut()], sorties=[(V, D1, False, True), (V, D2, False, False), (V, D2, False, False)])
        code, sortie, erreur, _, _ = self.lancer("take", "--language", "en", magasin=magasin)
        self.assertEqual(code, 0, erreur)
        self.assertEqual((magasin.etat["versions"][V]["release_date"], magasin.etat["versions"][V]["released"]), (D2, False))
        self.assertIn("versions with conflicting release attributes: 0", sortie)

    def test_version_dont_tous_les_tickets_ont_quitte_l_export_garde_sa_date(self):
        magasin = MagasinMemoire([un_defaut()], sorties=[(V, D1, True, False)])
        self.lancer("reconstruct", magasin=magasin)
        magasin.sorties = [(V, D1, True, True), (V, D1, True, True)]                # tous sortis de l'export
        code, sortie, _, _, _ = self.lancer("take", "--language", "en", magasin=magasin)
        self.assertEqual(code, 0)
        self.assertEqual((magasin.etat["versions"][V]["release_date"], magasin.etat["versions"][V]["released"]), (D1, True))
        self.assertIn("versions without release date: 0", sortie)

    def test_valeurs_divergentes_donnent_null(self):
        magasin = MagasinMemoire([un_defaut()], sorties=[(V, D1, True), (V, D2, True)])
        self.lancer("take", magasin=magasin)
        self.assertEqual((magasin.etat["versions"][V]["release_date"], magasin.etat["versions"][V]["released"]), (None, True))

    def test_aucune_date_estimee_sans_date_stockee(self):
        magasin = MagasinMemoire([un_defaut()])
        self.lancer("reconstruct", magasin=magasin)
        self.assertEqual(magasin.etat["versions"][V]["release_date"], None)


class RunRefuseNEcritRien(Espace):
    def registre(self, magasin):
        return {nom: dict(v) for nom, v in magasin.etat["versions"].items()}

    def test_seconde_reconstruction_refusee(self):
        magasin = MagasinMemoire([un_defaut()], sorties=[(V, D1, True)])
        self.lancer("reconstruct", magasin=magasin)
        magasin.sorties = [(V, D2, False), (W, D2, False)]
        avant = self.registre(magasin)
        code, _, _, _, _ = self.lancer("reconstruct", magasin=magasin)
        self.assertEqual(code, 3)
        self.assertEqual(self.registre(magasin), avant)

    def test_seconde_photo_refusee(self):
        magasin = MagasinMemoire([un_defaut()], sorties=[(V, D1, True)])
        self.lancer("take", magasin=magasin)
        magasin.sorties = [(V, D2, False), (W, D2, False)]
        avant = self.registre(magasin)
        self.assertEqual(self.lancer("take", magasin=magasin)[0], 3)
        self.assertEqual(self.registre(magasin), avant)

    def test_types_de_defaut_non_regles(self):
        self.ecrire_reglages("jira_site: x\n")
        magasin = MagasinMemoire([un_defaut()], sorties=[(V, D1, True)])
        self.assertEqual(self.lancer("take", magasin=magasin)[0], 3)
        self.assertEqual(self.lancer("reconstruct", magasin=magasin)[0], 3)
        self.assertEqual(magasin.etat["versions"], {})

    def test_session_claude_code(self):
        magasin = MagasinMemoire([un_defaut()], sorties=[(V, D1, True)])
        environ = {**self.environ, "CLAUDECODE": "1"}
        self.assertEqual(self.lancer("take", magasin=magasin, environ=environ)[0], 3)
        self.assertEqual(magasin.etat["versions"], {})

    def test_echec_en_cours_d_ecriture_annule_le_registre(self):
        class Echoue(MagasinMemoire):
            def ecrire_registre(self, attributs):
                super().ecrire_registre(attributs)
                raise RuntimeError("zz")
        magasin = Echoue([un_defaut()], sorties=[(V, D1, True)])
        self.assertEqual(self.lancer("take", magasin=magasin)[0], 1)
        self.assertEqual((magasin.etat["versions"], magasin.etat["passages"]), ({}, []))


class DeuxLignesDeCompte(Espace):
    def test_lignes_en_anglais_apres_les_lignes_existantes(self):
        magasin = MagasinMemoire([un_defaut()], sorties=[(V, D1, True), (W, None, None), (W, None, None)])
        _, sortie, _, _, _ = self.lancer("take", "--language", "en", magasin=magasin)
        self.assertEqual(sortie.splitlines()[-2:], ["versions without release date: 1", "versions with conflicting release attributes: 0"])
        self.assertEqual(len(sortie.splitlines()), 4)

    def test_lignes_en_francais(self):
        magasin = MagasinMemoire([un_defaut()], sorties=[(V, D1, True)])
        _, sortie, _, _, _ = self.lancer("reconstruct", magasin=magasin)
        self.assertEqual(sortie.splitlines()[-2:], ["versions sans date de sortie : 0", "versions aux attributs de sortie divergents : 0"])

    def test_la_ligne_des_divergents_est_imprimee_a_zero_et_compte_les_noms(self):
        magasin = MagasinMemoire([un_defaut()], sorties=[(V, D1, True), (V, D2, True), (W, D1, False), (W, D1, True)])
        _, sortie, _, _, _ = self.lancer("take", "--language", "en", magasin=magasin)
        self.assertEqual(sortie.splitlines()[-1], "versions with conflicting release attributes: 2")
        self.assertEqual(sortie.splitlines()[-2], "versions without release date: 1")          # V a une date nulle (divergente), W en a une

    def test_les_versions_sans_date_comptent_tout_le_registre_apres_le_lancement(self):
        magasin = MagasinMemoire([un_defaut()], sorties=[(V, D1, True)])
        magasin.etat["versions"]["zzversion-ancienne"] = {"no": 9, "release_date": None, "released": None}         # purgée, jamais datée
        _, sortie, _, _, _ = self.lancer("take", "--language", "en", magasin=magasin)
        self.assertIn("versions without release date: 1", sortie)

    def test_aucun_nom_numero_date_ni_drapeau_dans_aucune_sortie(self):
        sorties = [(V, D1, True), (V, D2, False), (W, D1, True), ("zzversion-c", None, None)]
        for langue in ("fr", "en"):
            magasin = MagasinMemoire([un_defaut()], sorties=sorties)
            textes = [self.lancer("reconstruct", "--language", langue, magasin=magasin)[1:3],
                      self.lancer("take", "--language", langue, magasin=magasin)[1:3],
                      self.lancer("take", "--language", langue, magasin=magasin)[1:3]]
            texte = "\n".join(s + e for s, e in textes)
            for valeur in MARQUES + ("2029", "True", "False"):
                self.assertNotIn(valeur, texte)

    def test_catalogues_a_jour(self):
        self.assertEqual(check_catalogs(CATALOGS), [])
        self.assertEqual(CATALOGS["en"]["versions_no_release_date"].format(n=3), "versions without release date: 3")
        self.assertEqual(CATALOGS["fr"]["versions_no_release_date"].format(n=3), "versions sans date de sortie : 3")
        self.assertEqual(CATALOGS["en"]["versions_conflicting_release"].format(n=0), "versions with conflicting release attributes: 0")
        self.assertEqual(CATALOGS["fr"]["versions_conflicting_release"].format(n=0), "versions aux attributs de sortie divergents : 0")


class RequetesDuMagasinBase(unittest.TestCase):
    def test_lecture_des_lignes_de_versions_courantes_sans_cle_de_ticket_avec_le_drapeau_hors_export(self):
        conn = FausseConnexion({"SELECT v.name, v.release_date, v.released": [(V, D1, True, False), (V, D1, None, True)]})
        lignes = vp.MagasinBase(conn).lire_sorties_stockees()
        self.assertEqual(lignes, [(V, D1, True, False), (V, D1, None, True)])
        (sql, params), = conn.sql("SELECT v.name, v.release_date, v.released")
        self.assertIn("flow.issue_current_versions", sql)
        self.assertIn("out_of_export_at IS NOT NULL", sql)
        self.assertNotRegex(sql.split(" FROM ")[0], "issue_key")                   # la clé n'est jamais lue, seulement jointe
        self.assertEqual(params, ())

    def test_ecriture_du_registre_dans_la_transaction_sans_validation(self):
        conn = FausseConnexion()
        vp.MagasinBase(conn).ecrire_registre({W: (None, None), V: (D1, True)})
        misesajour = conn.sql("UPDATE flow.version_photo_versions")
        ecrites = conn.sql("INSERT INTO flow.version_photo_versions")
        self.assertEqual([p for _, p in misesajour], [(D1, True, V), (None, None, W)])          # ordre déterministe par nom
        self.assertEqual([p for _, p in ecrites], [(V, D1, True, V), (W, None, None, W)])
        for sql, _ in ecrites:
            self.assertIn("WHERE NOT EXISTS", sql)
            self.assertNotIn("ON CONFLICT", sql)                                    # pas de numéro consommé pour un nom connu
        for sql, _ in misesajour:
            self.assertRegex(sql, r"SET release_date = %s, released = %s WHERE name = %s")
        self.assertEqual((conn.commits, conn.rollbacks), (0, 0))                   # la validation est celle du lancement

    def test_toutes_les_mises_a_jour_precedent_toutes_les_insertions(self):
        conn = FausseConnexion()
        vp.MagasinBase(conn).ecrire_registre({V: (D1, True), W: (None, None)})
        verbes = [sql.split()[0] for sql, _ in conn.appels]
        self.assertEqual(verbes, ["UPDATE", "UPDATE", "INSERT", "INSERT"])

    def test_registre_vide_n_ecrit_rien(self):
        conn = FausseConnexion()
        vp.MagasinBase(conn).ecrire_registre({})
        self.assertEqual(conn.appels, [])

    def test_compte_des_versions_sans_date(self):
        conn = FausseConnexion({"SELECT count(*) FROM flow.version_photo_versions": [(4,)]})
        self.assertEqual(vp.MagasinBase(conn).compter_versions_sans_date(), 4)
        (sql, _), = conn.sql("SELECT count(*) FROM flow.version_photo_versions")
        self.assertIn("release_date IS NULL", sql)


if __name__ == "__main__":
    unittest.main()
