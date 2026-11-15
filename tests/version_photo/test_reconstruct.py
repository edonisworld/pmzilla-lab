"""
`reconstruct` de tools/version_photo.py (change version-quality-photo, tâches 1.3 ; spec jira-flow-version-photo : reconstruction, une seule
exécution sauf --replace, types de défaut obligatoires, session refusée, sortie et langue, numéro de version opaque, couverture).
Magasin en mémoire : aucune base.
"""
import copy
import datetime as dt
import unittest

from aide_version_photo import AUJOURDHUI, MARQUES, Espace, MagasinMemoire, defaut, jour, vp

V = "zzversion-a"
DEBUT = dt.date(2026, 8, 10)                       # la plus ancienne semaine : dix semaines terminées avant le 2026-10-19
DERNIERE = dt.date(2026, 10, 12)


def un_defaut(**remplacements):
    base = dict(cree="2026-01-05", resolu="2026-08-12", affects={V}, fix={V}, periodes=[(V, jour("2026-08-12"), None)], type_="zzdefaut",
                equipe="zzequipe-alpha")
    base.update(remplacements)
    return defaut(**base)


def etat(magasin):
    return copy.deepcopy(magasin.etat)


class Reconstruction(Espace):
    def test_premiere_reconstruction_dix_semaines(self):
        magasin = MagasinMemoire([un_defaut()])
        code, sortie, erreur, _, _ = self.lancer("reconstruct", "--language", "en", magasin=magasin)
        self.assertEqual(code, 0, erreur)
        self.assertIn("reconstruction: 10 weeks, 1 versions, 0 partial weeks", sortie)
        self.assertIn("defects without fix version history: 0", sortie)
        self.assertEqual(sorted(magasin.reconstruites()), [DEBUT + dt.timedelta(days=7 * i) for i in range(10)])
        self.assertEqual(max(magasin.reconstruites()), DERNIERE)
        self.assertEqual([p["source"] for p in magasin.etat["passages"]], ["reconstructed"])          # un seul passage pour toutes les semaines
        self.assertEqual(magasin.vivantes(), {})
        for marque in MARQUES:
            self.assertNotIn(marque, sortie + erreur)

    def test_les_comptes_de_chaque_semaine(self):
        magasin = MagasinMemoire([un_defaut()])
        self.lancer("reconstruct", magasin=magasin)
        lignes = magasin.lignes_de(DEBUT)
        version = [l for l in lignes if l["version_no"] is not None][0]
        self.assertEqual((version["found"], version["corrected_at_week"], version["corrected_now"]), (1, 1, 1))

    def test_semaines_partielles_avant_la_limite_de_conservation(self):
        self.ecrire_reglages("defect_types: [zzdefaut]\nretention:\n  period_days: 60\n")             # limite : 2026-08-24
        magasin = MagasinMemoire([un_defaut()])
        code, sortie, _, _, _ = self.lancer("reconstruct", "--language", "en", magasin=magasin)
        self.assertEqual(code, 0)
        self.assertIn("10 weeks, 1 versions, 2 partial weeks", sortie)
        couvertures = {l: s["coverage"] for l, s in magasin.reconstruites().items()}
        self.assertEqual([l for l, c in sorted(couvertures.items()) if c == "partial"], [dt.date(2026, 8, 10), dt.date(2026, 8, 17)])
        self.assertEqual(couvertures[dt.date(2026, 8, 24)], "complete")

    def test_sans_historique_signale(self):
        magasin = MagasinMemoire([un_defaut(periodes=[])])
        _, sortie, _, _, _ = self.lancer("reconstruct", "--language", "en", magasin=magasin)
        self.assertIn("defects without fix version history: 1", sortie)
        ligne = [l for l in magasin.lignes_de(DEBUT) if l["version_no"] is not None][0]
        self.assertEqual((ligne["corrected_at_week"], ligne["corrected_now"]), (0, 1))

    def test_aucune_resolution_rien_n_est_ecrit(self):
        magasin = MagasinMemoire([un_defaut(resolu=None)])
        code, sortie, _, _, _ = self.lancer("reconstruct", "--language", "en", magasin=magasin)
        self.assertEqual(code, 0)
        self.assertIn("reconstruction: 0 weeks, 0 versions, 0 partial weeks", sortie)
        self.assertEqual(magasin.etat["passages"], [])


class UneSeuleExecution(Espace):
    def test_seconde_reconstruction_refusee_sans_rien_ecrire(self):
        magasin = MagasinMemoire([un_defaut()])
        self.lancer("reconstruct", magasin=magasin)
        avant = etat(magasin)
        code, sortie, _, _, _ = self.lancer("reconstruct", "--language", "en", magasin=magasin)
        self.assertEqual(code, 3)
        self.assertIn("reconstruction already done: use --replace", sortie)
        self.assertNotIn("reconstruction:", sortie)
        self.assertEqual(magasin.etat, avant)

    def test_seconde_reconstruction_refusee_en_francais(self):
        magasin = MagasinMemoire([un_defaut()])
        self.lancer("reconstruct", magasin=magasin)
        code, sortie, _, _, _ = self.lancer("reconstruct", magasin=magasin)
        self.assertEqual(code, 3)
        self.assertIn("reconstruction déjà faite : utiliser --replace", sortie)

    def test_replace_reecrit_les_semaines_reconstruites_et_garde_les_photos_vivantes(self):
        magasin = MagasinMemoire([un_defaut()])
        self.lancer("reconstruct", magasin=magasin)
        self.lancer("take", magasin=magasin, maintenant=jour("2026-10-23", 14))                      # semaine du 2026-10-19
        self.lancer("take", magasin=magasin, maintenant=jour("2026-10-30", 14))                      # semaine du 2026-10-26
        vivantes = copy.deepcopy(magasin.vivantes())
        lignes_vivantes = {l: copy.deepcopy(magasin.lignes_de(l)) for l in vivantes}
        self.assertEqual(len(vivantes), 2)
        code, sortie, erreur, _, _ = self.lancer("reconstruct", "--replace", "--language", "en", magasin=magasin, maintenant=jour("2026-11-06", 14))
        self.assertEqual(code, 0, erreur)
        premiere_ligne = sortie.splitlines()[0]
        self.assertEqual(premiere_ligne, "warning: a reconstruction run again is more partial, the purge has moved on")
        self.assertEqual(magasin.vivantes(), vivantes)                                               # les deux photos vivantes, intactes
        for lundi, lignes in lignes_vivantes.items():
            self.assertEqual(magasin.lignes_de(lundi), lignes)
        self.assertEqual(sorted(magasin.reconstruites()), [DEBUT + dt.timedelta(days=7 * i) for i in range(10)])          # réécrites
        self.assertIn("reconstruction: 10 weeks", sortie)
        actifs = [p for p in magasin.etat["passages"] if p["source"] == "reconstructed" and not p.get("supprime")]
        self.assertEqual([p["instant"] for p in actifs], [jour("2026-11-06", 14)])                    # l'ancien passage n'a plus de semaine : supprimé

    def test_replace_ne_remplace_que_les_semaines_recalculables_depuis_les_donnees_presentes(self):
        """Décision B du 2026-10-23 : les semaines reconstruites plus anciennes, que la purge rend non recalculables, gardent leurs lignes."""
        ancien = un_defaut()                                                                          # résolu le 2026-08-12 (semaine du 08-10)
        recent = un_defaut(resolu="2026-09-02", periodes=[(V, jour("2026-09-02"), None)])             # semaine du 2026-08-31
        magasin = MagasinMemoire([ancien, recent])
        self.lancer("reconstruct", magasin=magasin)
        avant = {lundi: copy.deepcopy(magasin.lignes_de(lundi)) for lundi in magasin.reconstruites()}
        self.assertEqual(len(avant), 10)
        magasin.tickets = [recent]                                                                    # purge simulée : le défaut ancien a disparu
        code, sortie, erreur, _, _ = self.lancer("reconstruct", "--replace", "--language", "en", magasin=magasin)
        self.assertEqual(code, 0, erreur)
        lignes = sortie.splitlines()
        self.assertEqual(lignes[0], "warning: a reconstruction run again is more partial, the purge has moved on")
        self.assertEqual(lignes[1], "warning: 3 older reconstructed weeks kept as they are, no longer recomputable")
        self.assertIn("reconstruction: 7 weeks", sortie)
        gardees = [dt.date(2026, 8, 10), dt.date(2026, 8, 17), dt.date(2026, 8, 24)]
        for lundi in gardees:
            self.assertEqual(magasin.lignes_de(lundi), avant[lundi], lundi)                           # intactes
        for lundi in sorted(avant)[3:]:
            self.assertNotEqual(magasin.lignes_de(lundi), avant[lundi], lundi)                        # recalculées sans le défaut purgé
        trouve = [l["found"] for l in magasin.lignes_de(dt.date(2026, 8, 31)) if l["version_no"] is not None]
        self.assertEqual(trouve, [1])
        self.assertEqual(sorted(magasin.reconstruites()), sorted(avant))
        # décision 2 du 2026-10-23 : le recalcul est un NOUVEAU passage ; l'ancien garde ses trois semaines non recalculables et son instant
        actifs = [p for p in magasin.etat["passages"] if p["source"] == "reconstructed" and not p.get("supprime")]
        self.assertEqual([p["instant"] for p in actifs], [AUJOURDHUI, AUJOURDHUI])
        numeros = [i for i, p in enumerate(magasin.etat["passages"]) if p["source"] == "reconstructed" and not p.get("supprime")]
        par_passage = {n: sorted(l for l, s in magasin.etat["semaines"].items() if s["passage"] == n) for n in numeros}
        self.assertEqual(sorted(len(v) for v in par_passage.values()), [3, 7])
        self.assertEqual(par_passage[numeros[0]], gardees)                                            # l'ancien passage : les semaines gardées seules

    def test_replace_repete_ecrit_a_chaque_fois_un_nouveau_passage_sans_garder_de_vide(self):
        magasin = MagasinMemoire([un_defaut()])
        self.lancer("reconstruct", magasin=magasin, maintenant=jour("2026-10-23", 14))
        premier = magasin.etat["passages"][0]["instant"]
        self.lancer("reconstruct", "--replace", magasin=magasin, maintenant=jour("2026-10-30", 14))
        self.lancer("reconstruct", "--replace", magasin=magasin, maintenant=jour("2026-11-06", 14))
        actifs = [p["instant"] for p in magasin.etat["passages"] if p["source"] == "reconstructed" and not p.get("supprime")]
        self.assertEqual(actifs, [jour("2026-11-06", 14)])
        self.assertNotIn(premier, actifs)

    def test_replace_sans_semaine_gardee_le_dit(self):
        magasin = MagasinMemoire([un_defaut()])
        self.lancer("reconstruct", magasin=magasin)
        _, sortie, _, _, _ = self.lancer("reconstruct", "--replace", "--language", "en", magasin=magasin)
        self.assertIn("warning: 0 older reconstructed weeks kept as they are, no longer recomputable", sortie)

    def test_replace_en_francais_avertit_d_abord(self):
        magasin = MagasinMemoire([un_defaut()])
        self.lancer("reconstruct", magasin=magasin)
        _, sortie, _, _, _ = self.lancer("reconstruct", "--replace", magasin=magasin)
        self.assertEqual(sortie.splitlines()[0], "avertissement : une reconstruction relancée est plus partielle, la purge a avancé")

    def test_une_semaine_deja_photographiee_en_direct_n_est_jamais_reconstruite(self):
        magasin = MagasinMemoire([un_defaut()])
        self.lancer("take", magasin=magasin, maintenant=jour("2026-10-23", 14))                      # semaine du 2026-10-19
        avant = copy.deepcopy(magasin.lignes_de(dt.date(2026, 10, 19)))
        code, sortie, _, _, _ = self.lancer("reconstruct", "--language", "en", magasin=magasin, maintenant=jour("2026-11-06", 14))
        self.assertEqual(code, 0)
        semaines = sorted(magasin.reconstruites())
        self.assertNotIn(dt.date(2026, 10, 19), semaines)
        self.assertIn(dt.date(2026, 10, 26), semaines)
        self.assertEqual(magasin.lignes_de(dt.date(2026, 10, 19)), avant)
        self.assertIn("reconstruction: 11 weeks", sortie)                                             # douze semaines terminées moins la semaine vivante

    def test_une_reconstruction_vide_puis_une_autre_ne_se_confondent_pas_avec_un_refus(self):
        magasin = MagasinMemoire([])
        self.assertEqual(self.lancer("reconstruct", magasin=magasin)[0], 0)
        self.assertEqual(self.lancer("reconstruct", magasin=magasin)[0], 0)                          # rien n'avait été écrit : pas de refus


class Prerequis(Espace):
    def test_types_de_defaut_non_regles(self):
        for reglages in ("jira_site: x\n", "portfolio_types: [zzepic]\n"):
            self.ecrire_reglages(reglages)
            magasin = MagasinMemoire([un_defaut()])
            avant = etat(magasin)
            code, sortie, _, _, ouvertures = self.lancer("reconstruct", "--language", "en", magasin=magasin)
            self.assertEqual(code, 3)
            self.assertIn("defect types not set", sortie)
            self.assertEqual((ouvertures, magasin.etat), (0, avant))                                 # aucune connexion, rien d'écrit

    def test_fichier_de_reglages_absent(self):
        self.reglages.unlink()
        code, sortie, _, _, ouvertures = self.lancer("reconstruct")
        self.assertEqual((code, ouvertures), (3, 0))
        self.assertIn("types de défaut non réglés", sortie)

    def test_reglages_invalides_sans_la_valeur(self):
        self.ecrire_reglages("defect_types: zzvaleurdistinctive\n")
        code, sortie, erreur, _, ouvertures = self.lancer("reconstruct", "--language", "en")
        self.assertEqual((code, ouvertures), (3, 0))
        self.assertIn("defect_types", sortie)
        self.assertNotIn("zzvaleurdistinctive", sortie + erreur)

    def test_session_claude_code_refusee_avant_toute_lecture(self):
        self.reglages.unlink()
        environ = {**self.environ, "CLAUDECODE": "1", "VERSION_PHOTO_SETTINGS": str(self.racine / "absent" / "flux.yaml")}
        for argv in (("reconstruct",), ("take",), ("adopt-n", "--weeks", "6", "--adopted-on", "2026-11-20")):
            for langue, phrase in (("fr", "Refusé dans une session Claude Code"), ("en", "Refused inside a Claude Code session")):
                code, sortie, erreur, magasin, ouvertures = self.lancer(*argv, "--language", langue, environ=environ)
                self.assertEqual((code, ouvertures), (3, 0), argv)
                self.assertIn(phrase, sortie)
                self.assertEqual(magasin.etat["passages"], [])

    def test_aucune_option_ne_contourne_la_session(self):
        environ = {**self.environ, "CLAUDECODE": "1"}
        code, _, _, _, ouvertures = self.lancer("reconstruct", "--force", environ=environ)
        self.assertEqual(code, 2)                                                                    # option inconnue : usage, jamais un contournement
        self.assertEqual(ouvertures, 0)


class SortieEtLangue(Espace):
    def test_francais_par_defaut(self):
        _, sortie, _, _, _ = self.lancer("reconstruct", magasin=MagasinMemoire([un_defaut()]))
        self.assertEqual(sortie.splitlines(), ["reconstruction : 10 semaines, 1 versions, 0 semaines partielles",
                                               "défauts sans historique de fix version : 0",
                                               "versions sans date de sortie : 1",                       # change version-release-date, design D9
                                               "versions aux attributs de sortie divergents : 0"])

    def test_langue_inconnue_ou_option_inconnue(self):
        for argv in (("reconstruct", "--language", "de"), ("reconstruct", "--inconnue"), ("inconnue",), ()):
            code, sortie, erreur, _, ouvertures = self.lancer(*argv)
            self.assertEqual((code, ouvertures), (2, 0), argv)
            self.assertEqual(sortie, "")

    def test_aucun_nom_distinctif_dans_aucune_sortie(self):
        tickets = [un_defaut(), un_defaut(type_="zzdefaut", equipe="zzequipe-beta", affects={"zzversion-b"}, fix={"zzversion-b"},
                                          periodes=[])]
        for langue in ("fr", "en"):
            magasin = MagasinMemoire(tickets)
            sorties = [self.lancer("reconstruct", "--language", langue, magasin=magasin)[1:3],
                       self.lancer("reconstruct", "--replace", "--language", langue, magasin=magasin)[1:3],
                       self.lancer("take", "--language", langue, magasin=magasin)[1:3],
                       self.lancer("take", "--language", langue, magasin=magasin)[1:3]]            # la seconde est refusée : aussi sans nom
            texte = "\n".join(s + e for s, e in sorties)
            for marque in MARQUES:
                self.assertNotIn(marque, texte)

    def test_erreur_de_base_nom_du_type_seul(self):
        def ouvrir():
            raise RuntimeError("zzcle-secrete zzequipe zzversion")
        import contextlib
        import io
        sortie, erreur = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
            code = vp.main(["reconstruct", "--language", "en"], self.environ, ouvrir_magasin=ouvrir)
        self.assertEqual(code, 1)
        self.assertEqual(erreur.getvalue().strip(), "Error: RuntimeError")
        self.assertEqual(sortie.getvalue(), "")

    def test_echec_en_cours_d_ecriture_annule_tout(self):
        class Echoue(MagasinMemoire):
            def ecrire_passage(self, *args):
                super().ecrire_passage(*args)
                raise RuntimeError("zz")
        magasin = Echoue([un_defaut()])
        code, _, erreur, _, _ = self.lancer("reconstruct", magasin=magasin)
        self.assertEqual(code, 1)
        self.assertEqual(magasin.etat["passages"], [])                                               # la fermeture sans validation annule


class NumeroDeVersionOpaque(Espace):
    def test_meme_numero_dans_la_reconstruction_et_dans_la_photo_vivante(self):
        magasin = MagasinMemoire([un_defaut()])
        self.lancer("reconstruct", magasin=magasin)
        self.lancer("take", magasin=magasin)
        numeros = {l["version_no"] for lundi in list(magasin.reconstruites()) + list(magasin.vivantes()) for l in magasin.lignes_de(lundi)
                   if l["version_no"] is not None}
        self.assertEqual(numeros, {1})
        self.assertEqual(list(magasin.etat["versions"]), [V])
        self.assertEqual(magasin.etat["versions"][V], {"no": 1, "release_date": None, "released": None})

    def test_numeros_dans_l_ordre_de_premiere_rencontre(self):
        tickets = [un_defaut(affects={"zzversion-b"}, fix={"zzversion-b"}, periodes=[]), un_defaut(affects={"zzversion-c"}, fix=(), periodes=[])]
        magasin = MagasinMemoire(tickets)
        self.lancer("reconstruct", magasin=magasin)
        self.assertEqual({nom: v["no"] for nom, v in magasin.etat["versions"].items()}, {"zzversion-b": 1, "zzversion-c": 2})


if __name__ == "__main__":
    unittest.main()
