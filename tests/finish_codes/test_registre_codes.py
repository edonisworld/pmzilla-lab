"""
Registre des codes de sortie des scripts de fin (R-148/u17, #583) : tools/finish_codes.yaml.

    bash tests/run_all.sh finish_codes

Le registre déclare, pour tools/finish_branch.sh, tools/finish_worktree.sh et tools/finish_train.sh, chaque code (script, code, sens, origine).
Le test refuse : un code avec deux sens, un code qu'un script rend sans qu'il soit déclaré, un code déclaré « utilise » que le script ne rend
pas (sauf « rendu_par: transmission »), un code « jamais_rendu » que le script rend, une réservation dont le change est absent ou archivé (ou
dont la tâche manque dans son tasks.md), un code partagé entre deux scripts hors des partages connus, une sortie calculée (« exit "$…" », ou la
ligne « exec » de l'enveloppe) qui n'est pas déclarée dans « sorties_dynamiques ». Un code « reserve » que le script rend déjà est ACCEPTÉ tant que
le change qui le réserve est ouvert (information dans la sortie), refusé dès que le change est archivé. Un finish_train.sh absent est accepté (il
s'écrit dans un autre change) ; présent, il doit déclarer ses codes.

Finish-single-b7-b9 (B78, D7 ; tâches 1.1 et 3.4) : le registre ne porte plus les sections traductions, transmis, controle_rendus ni
continue_au_controle (le passage des codes de finish_branch.sh par finish_worktree.sh n'existe plus : l'enveloppe rend le code du train) ; leurs
contrôles et leurs tests sont retirés avec elles (précédent R-20261029-31).

Les cas négatifs jouent sur des arbres synthétiques (aide_registre.py n'a aucune règle propre à l'arbre réel) ; la classe ArbreReel joue sur
l'arbre réel (registre sans écart, zone 60 à 83, codes 72 et 77, sorties calculées déclarées, codes de l'enveloppe).
"""
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aide_registre as reg  # noqa: E402

RACINE = Path(__file__).resolve().parents[2]


def entree(script, code, origine="utilise", **autres):
    d = {"script": script, "code": code, "sens": f"sens du {code}", "origine": origine}
    d.update(autres)
    return d


SORTIE_CODE = {"script": "finish_worktree", "motif": 'exit "$CODE"', "raison": "transmission du code de la fin de branche"}


class Arbre:
    """Arbre synthétique : trois scripts de fin minuscules, un registre, des changes OpenSpec."""

    def __init__(self, test):
        self.dossier = tempfile.TemporaryDirectory()
        test.addCleanup(self.dossier.cleanup)
        self.racine = Path(self.dossier.name)
        (self.racine / "tools").mkdir()
        self.registre = {
            "scripts": {
                "finish_branch": {"fichier": "tools/finish_branch.sh"},
                "finish_worktree": {"fichier": "tools/finish_worktree.sh"},
                "finish_train": {"fichier": "tools/finish_train.sh", "facultatif": True, "change": "finish-train-v1"},
            },
            "codes": [entree("finish_branch", 0), entree("finish_branch", 1), entree("finish_worktree", 0), entree("finish_worktree", 21)],
            "sorties_dynamiques": [],
        }
        self.infos = []
        self.ecrire_script("finish_branch", 'refus 1 "tests"\nexit 0\n')
        self.ecrire_script("finish_worktree", 'refus 21 "hors du dépôt"\nexit 0\n')

    def ecrire_script(self, nom, texte):
        (self.racine / "tools" / f"{nom}.sh").write_text(texte, encoding="utf-8")

    def ecrire_change(self, nom, taches="- [ ] 2.12 une tâche\n", archive=False):
        dossier = self.racine / "openspec" / "changes" / ("archive/2026-01-01-" + nom if archive else nom)
        dossier.mkdir(parents=True)
        (dossier / "tasks.md").write_text(taches, encoding="utf-8")

    def ecarts(self):
        (self.racine / "tools" / "finish_codes.yaml").write_text(yaml.safe_dump(self.registre, allow_unicode=True), encoding="utf-8")
        messages, self.infos = reg.analyser(self.racine)
        return messages


class ArbreReel(unittest.TestCase):
    def test_le_registre_reel_est_sans_ecart(self):
        messages, infos = reg.analyser(RACINE)
        for ligne in infos:
            print(f"information : {ligne}", file=sys.stderr)
        self.assertEqual(messages, [])

    def test_les_codes_72_et_77_du_train_sont_jamais_rendus(self):
        origines = {c["code"]: c["origine"] for c in reg.charger(RACINE)["codes"] if c["script"] == "finish_train"}
        self.assertEqual((origines[72], origines[77]), ("jamais_rendu", "jamais_rendu"))

    def test_les_sorties_calculees_reelles_sont_declarees(self):
        registre = reg.charger(RACINE)
        motifs = {(d["script"], d["motif"]) for d in registre["sorties_dynamiques"]}
        # finish-single-b7-b9, B9 (D8, tâche 1.1 : décision de l'auteur du 2026-10-30, R-20261030-51) : le train est le seul script du registre
        self.assertEqual(motifs, {("finish_train", 'exit "$code"')})

    def test_le_registre_ne_porte_que_le_train_et_n_a_plus_les_sections_du_passage_des_codes(self):
        # finish-single-b7-b9, B9 (D8) : la section scripts ne porte que finish_train ; aucun code des fins unitaires retirées ; D7 : plus de section de passage des codes
        registre = reg.charger(RACINE)
        self.assertEqual(set(registre["scripts"]), {"finish_train"})
        self.assertEqual({c["script"] for c in registre["codes"]}, {"finish_train"})
        for section in ("traductions", "transmis", "controle_rendus", "continue_au_controle"):
            self.assertNotIn(section, registre)

    def test_la_zone_60_a_83_du_train_est_declaree(self):
        # finish-single-b3-b6, tâche 1.1 B6 (R-20261029-39 Q11) : l'index du registre gagne 83 (la zone passe de 60 à 81 à 60 à 83)
        declares = {c["code"] for c in reg.charger(RACINE)["codes"] if c["script"] == "finish_train"}
        self.assertEqual(set(range(60, 84)) - declares, set())


class Extraction(unittest.TestCase):
    def test_refus_et_exit_litteraux(self):
        texte = 'refus 14 "passage"\n  [ x ] || refus 30 "retrait" \\\n    "suite"\nexit 52\ntrap \'exit 129\' HUP\n'
        self.assertEqual(reg.extraire_codes(texte), {14, 30, 52, 129})

    def test_commentaires_et_aide_ne_comptent_pas(self):
        texte = '# refus 98 "dans un commentaire"\n# exit 97\ncat <<EOF\nrefus 3, 4, 19 et 5\n(refus 14)\nEOF\nrefus ci-dessus\n'
        self.assertEqual(reg.extraire_codes(texte), set())

    def test_les_sorties_dynamiques_ne_sont_pas_extraites(self):
        self.assertEqual(reg.extraire_codes('exit "$code"\nexit "$CODE"\nrefus "$code" "x"\n'), set())

    def test_sorties_calculees_reperees(self):
        texte = ('exit "$code"\n  exit $?\nrefus "$c" "x"\n[ a ] || sortir "$c"\ntrap \'exit "${CODE}"\' INT\n# exit "$x"\nexit 3\nrefus 4 "ok"\n'
                 'refus() { :; }\n')
        self.assertEqual(reg.sorties_calculees(texte), ['exit "$code"', "exit $?", 'refus "$c" "x"', '[ a ] || sortir "$c"',
                                                        "trap 'exit \"${CODE}\"' INT"])

    def test_exec_d_une_commande_est_une_sortie_calculee_et_une_redirection_non(self):
        # l'enveloppe passe la main au train par exec (finish-single-b7-b9, D7) ; « exec 3>&1 » ou « exec > fichier » ne passent la main à personne
        texte = 'exec bash tools/finish_train.sh "$B"\n  exec /bin/true\nexec 3>&1 4>&2\nexec > "$LOG" 2>&1\nexec 1>&3 2>&4\n# exec bash x\n'
        self.assertEqual(reg.sorties_calculees(texte), ['exec bash tools/finish_train.sh "$B"', "exec /bin/true"])
        self.assertEqual(reg.extraire_codes(texte), set())

    def test_refus_apres_case_ou_ou_logique(self):
        texte = '  5) refus 32 "x" ;;\n  *) refus 37 "y" ;;\n[ a ] || refus 26 "z"\n'
        self.assertEqual(reg.extraire_codes(texte), {32, 37, 26})


class Declarations(unittest.TestCase):
    def test_arbre_sain(self):
        self.assertEqual(Arbre(self).ecarts(), [])

    def test_doublon_un_code_deux_sens(self):
        a = Arbre(self)
        a.registre["codes"].append(entree("finish_branch", 1))
        ecarts = a.ecarts()
        self.assertTrue(any("deux sens" in m and "finish_branch" in m and "1" in m for m in ecarts), ecarts)

    def test_code_utilise_non_declare(self):
        a = Arbre(self)
        a.ecrire_script("finish_branch", 'refus 1 "tests"\nrefus 99 "nouveau"\nexit 0\n')
        ecarts = a.ecarts()
        self.assertTrue(any("99" in m and "non déclaré" in m and "finish_branch" in m for m in ecarts), ecarts)

    def test_exit_non_declare(self):
        a = Arbre(self)
        a.ecrire_script("finish_worktree", 'refus 21 "hors"\nexit 0\ntrap \'exit 88\' TERM\n')
        self.assertTrue(any("88" in m and "non déclaré" in m for m in a.ecarts()))

    def test_code_declare_utilise_mais_absent_du_script(self):
        a = Arbre(self)
        a.registre["codes"].append(entree("finish_branch", 2))
        ecarts = a.ecarts()
        self.assertTrue(any("2" in m and "ne le rend pas" in m and "finish_branch" in m for m in ecarts), ecarts)

    def test_code_reserve_deja_rendu_change_ouvert_est_accepte_avec_information(self):
        a = Arbre(self)
        a.ecrire_change("mothra-slices", taches="- [ ] 8.4 refus 16\n")
        a.registre["codes"].append(entree("finish_branch", 16, "reserve", change="mothra-slices", tache="8.4"))
        a.ecrire_script("finish_branch", 'refus 1 "tests"\nrefus 16 "preuve"\nexit 0\n')
        self.assertEqual(a.ecarts(), [])
        self.assertTrue(any("16" in m and "mothra-slices" in m and "ouvert" in m for m in a.infos), a.infos)

    def test_code_reserve_rendu_change_archive_passer_a_utilise(self):
        a = Arbre(self)
        a.ecrire_change("mothra-slices", archive=True, taches="- [x] 8.4 fait\n")
        a.registre["codes"].append(entree("finish_branch", 16, "reserve", change="mothra-slices", tache="8.4"))
        a.ecrire_script("finish_branch", 'refus 1 "tests"\nrefus 16 "preuve"\nexit 0\n')
        ecarts = a.ecarts()
        self.assertTrue(any("16" in m and "archivé" in m and "passer à utilise" in m for m in ecarts), ecarts)

    def test_code_reserve_non_rendu_change_archive_propose_jamais_rendu(self):
        a = Arbre(self)
        a.ecrire_change("mothra-slices", archive=True, taches="- [x] 8.4 fait\n")
        a.registre["codes"].append(entree("finish_branch", 16, "reserve", change="mothra-slices", tache="8.4"))
        ecarts = a.ecarts()
        self.assertTrue(any("16" in m and "mothra-slices" in m and "archivé" in m and "jamais_rendu" in m for m in ecarts), ecarts)

    def test_reservation_valide(self):
        a = Arbre(self)
        a.ecrire_change("mothra-slices", taches="- [ ] 8.4 refus 16\n")
        a.registre["codes"].append(entree("finish_branch", 16, "reserve", change="mothra-slices", tache="8.4"))
        self.assertEqual(a.ecarts(), [])

    def test_reservation_d_un_change_absent(self):
        a = Arbre(self)
        a.registre["codes"].append(entree("finish_branch", 16, "reserve", change="n-existe-pas", tache="8.4"))
        ecarts = a.ecarts()
        self.assertTrue(any("n-existe-pas" in m and "absent" in m for m in ecarts), ecarts)

    def test_reservation_d_une_tache_absente(self):
        a = Arbre(self)
        a.ecrire_change("mothra-slices", taches="- [ ] 8.5 autre\n")
        a.registre["codes"].append(entree("finish_branch", 16, "reserve", change="mothra-slices", tache="8.4"))
        ecarts = a.ecarts()
        self.assertTrue(any("8.4" in m and "tâche" in m for m in ecarts), ecarts)

    def test_une_tache_n_est_pas_un_prefixe_d_une_autre(self):
        a = Arbre(self)
        a.ecrire_change("mothra-slices", taches="- [ ] 8.41 autre\n")
        a.registre["codes"].append(entree("finish_branch", 16, "reserve", change="mothra-slices", tache="8.4"))
        self.assertTrue(any("8.4" in m and "tâche" in m for m in a.ecarts()))

    def test_jamais_rendu_est_accepte_et_refuse_s_il_est_rendu(self):
        a = Arbre(self)
        a.registre["codes"].append(entree("finish_worktree", 39, "jamais_rendu"))
        self.assertEqual(a.ecarts(), [])
        a.ecrire_script("finish_worktree", 'refus 21 "hors"\nrefus 39 "oups"\nexit 0\n')
        self.assertEqual(a.ecarts(), ["finish_worktree : code 39 déclaré jamais rendu, mais tools/finish_worktree.sh le rend déjà : passer l'entrée à utilise"])

    def test_jamais_rendu_est_accepte_pour_un_script_absent(self):
        a = Arbre(self)
        a.registre["codes"].append(entree("finish_train", 72, "jamais_rendu"))
        self.assertEqual(a.ecarts(), [])


class Train(unittest.TestCase):
    def test_finish_train_absent_est_accepte_avec_ses_reservations(self):
        a = Arbre(self)
        a.ecrire_change("finish-train-v1", taches="- [ ] 2.12 codes\n")
        a.registre["codes"] += [entree("finish_train", c, "reserve", change="finish-train-v1", tache="2.12") for c in (60, 61, 79)]
        self.assertEqual(a.ecarts(), [])

    def test_finish_train_present_doit_declarer_ses_codes(self):
        a = Arbre(self)
        a.ecrire_script("finish_train", 'refus 60 "usage"\nexit 0\n')
        ecarts = a.ecarts()
        self.assertTrue(any("60" in m and "non déclaré" in m and "finish_train" in m for m in ecarts), ecarts)

    def test_finish_train_present_avec_codes_declares_utilises(self):
        a = Arbre(self)
        a.ecrire_script("finish_train", 'refus 60 "usage"\nexit 0\n')
        a.registre["codes"] += [entree("finish_train", 60), entree("finish_train", 0)]
        self.assertEqual(a.ecarts(), [])

    def test_finish_train_present_dont_les_codes_restent_reserves_change_ouvert(self):
        a = Arbre(self)
        a.ecrire_change("finish-train-v1")
        a.ecrire_script("finish_train", 'refus 60 "usage"\nexit 0\n')
        a.registre["codes"] += [entree("finish_train", 60, "reserve", change="finish-train-v1", tache="2.12"), entree("finish_train", 0)]
        self.assertEqual(a.ecarts(), [])
        self.assertTrue(any("60" in m and "finish-train-v1" in m for m in a.infos), a.infos)

    def test_finish_train_present_dont_le_change_est_archive(self):
        a = Arbre(self)
        a.ecrire_change("finish-train-v1", archive=True)
        a.ecrire_script("finish_train", 'refus 60 "usage"\nexit 0\n')
        a.registre["codes"] += [entree("finish_train", 60, "reserve", change="finish-train-v1", tache="2.12"), entree("finish_train", 0)]
        self.assertTrue(any("60" in m and "archivé" in m and "passer à utilise" in m for m in a.ecarts()))

    def test_un_script_obligatoire_absent_est_signale(self):
        a = Arbre(self)
        (a.racine / "tools" / "finish_worktree.sh").unlink()
        ecarts = a.ecarts()
        self.assertTrue(any("finish_worktree" in m and "absent" in m for m in ecarts), ecarts)


class Partages(unittest.TestCase):
    def test_un_code_declare_par_deux_scripts_est_refuse(self):
        a = Arbre(self)
        a.registre["codes"].append(entree("finish_worktree", 1))
        a.ecrire_script("finish_worktree", 'refus 21 "hors"\nrefus 1 "x"\nexit 0\n')
        ecarts = a.ecarts()
        self.assertTrue(any("finish_branch" in m and "finish_worktree" in m and "1" in m for m in ecarts), ecarts)

    def test_les_partages_connus_sont_acceptes(self):
        a = Arbre(self)
        for script in ("finish_branch", "finish_worktree"):
            a.registre["codes"] += [entree(script, c) for c in (129, 130, 143)]
        a.registre["codes"] += [entree("finish_branch", 20), entree("finish_worktree", 20)]
        a.ecrire_script("finish_branch", 'refus 1 "t"\nrefus 20 "npm"\ntrap \'exit 129\' HUP\ntrap \'exit 130\' INT\ntrap \'exit 143\' TERM\nexit 0\n')
        a.ecrire_script("finish_worktree", 'refus 21 "h"\nrefus 20 "usage"\ntrap \'exit 129\' HUP\ntrap \'exit 130\' INT\n'
                                           'trap \'exit 143\' TERM\nexit 0\n')
        self.assertEqual(a.ecarts(), [])

    def test_le_20_est_limite_aux_deux_scripts_de_fin_de_branche(self):
        a = Arbre(self)
        a.ecrire_change("finish-train-v1")
        a.registre["codes"].append(entree("finish_train", 20, "reserve", change="finish-train-v1", tache="2.12"))
        a.registre["codes"].append(entree("finish_branch", 20))
        a.ecrire_script("finish_branch", 'refus 1 "t"\nrefus 20 "npm"\nexit 0\n')
        ecarts = a.ecarts()
        self.assertTrue(any("20" in m and "finish_train" in m and "partages permis" in m for m in ecarts), ecarts)


class Forme(unittest.TestCase):
    def test_origine_inconnue(self):
        a = Arbre(self)
        a.registre["codes"][1]["origine"] = "peut-etre"
        self.assertTrue(any("origine" in m for m in a.ecarts()))

    def test_reserve_sans_change_ni_tache(self):
        a = Arbre(self)
        a.registre["codes"].append(entree("finish_branch", 16, "reserve"))
        self.assertTrue(any("16" in m and "change" in m for m in a.ecarts()))

    def test_utilise_avec_un_change_est_refuse(self):
        a = Arbre(self)
        a.registre["codes"][1]["change"] = "mothra-slices"
        self.assertTrue(any("1" in m and "change" in m for m in a.ecarts()))

    def test_script_inconnu_ou_code_hors_bornes(self):
        a = Arbre(self)
        a.registre["codes"].append(entree("finish_inconnu", 5))
        a.registre["codes"].append(entree("finish_branch", 300))
        ecarts = a.ecarts()
        self.assertTrue(any("finish_inconnu" in m for m in ecarts), ecarts)
        self.assertTrue(any("300" in m for m in ecarts), ecarts)

    def test_sens_vide(self):
        a = Arbre(self)
        a.registre["codes"][1]["sens"] = " "
        self.assertTrue(any("sens" in m for m in a.ecarts()))

    def test_registre_illisible_ou_absent(self):
        a = Arbre(self)
        (a.racine / "tools" / "finish_codes.yaml").write_text("codes: [", encoding="utf-8")
        self.assertTrue(any("illisible" in m for m in reg.ecarts(a.racine)))
        (a.racine / "tools" / "finish_codes.yaml").unlink()
        self.assertTrue(any("absent" in m for m in reg.ecarts(a.racine)))


class Signaux(unittest.TestCase):
    def test_un_signal_declare_et_rendu_est_accepte(self):
        a = Arbre(self)
        a.registre["codes"].append(entree("finish_branch", 130))
        a.ecrire_script("finish_branch", 'refus 1 "tests"\ntrap \'exit 130\' INT\nexit 0\n')
        self.assertEqual(a.ecarts(), [])

    def test_un_code_sans_section_de_traduction_n_est_pas_un_ecart(self):
        # finish-single-b7-b9 D7 : un code de finish_branch n'a plus à être transmis ni traduit par un autre script
        a = Arbre(self)
        self.assertNotIn("traductions", a.registre)
        self.assertNotIn("transmis", a.registre)
        self.assertEqual(a.ecarts(), [])


class SortiesDynamiques(unittest.TestCase):
    def test_sortie_calculee_non_declaree(self):
        a = Arbre(self)
        a.ecrire_script("finish_worktree", 'refus 21 "hors"\nexit "$CODE"\n')
        ecarts = a.ecarts()
        self.assertTrue(any("finish_worktree" in m and "calculée" in m and "sorties_dynamiques" in m for m in ecarts), ecarts)

    def test_sortie_calculee_declaree_acceptee(self):
        a = Arbre(self)
        # le vrai finish_worktree.sh garde un « exit 0 » littéral (l'aide) à côté de « exit "$CODE" » : le 0 reste rendu littéralement
        a.ecrire_script("finish_worktree", 'refus 21 "hors"\nexit 0\nexit "$CODE"\n')
        a.registre["sorties_dynamiques"] = [dict(SORTIE_CODE)]
        self.assertEqual(a.ecarts(), [])

    def test_une_declaration_ne_couvre_que_son_script(self):
        a = Arbre(self)
        a.ecrire_script("finish_branch", 'refus 1 "t"\nexit "$CODE"\nexit 0\n')
        a.registre["sorties_dynamiques"] = [dict(SORTIE_CODE)]
        ecarts = a.ecarts()
        self.assertTrue(any("finish_branch" in m and "calculée" in m for m in ecarts), ecarts)
        self.assertTrue(any("finish_worktree" in m and "absente" in m for m in ecarts), ecarts)

    def test_declaration_sans_sortie_correspondante(self):
        a = Arbre(self)
        a.registre["sorties_dynamiques"] = [dict(SORTIE_CODE)]
        ecarts = a.ecarts()
        self.assertTrue(any("finish_worktree" in m and "absente" in m and 'exit "$CODE"' in m for m in ecarts), ecarts)

    def test_declaration_mal_formee(self):
        a = Arbre(self)
        a.registre["sorties_dynamiques"] = [{"script": "finish_worktree", "motif": 'exit "$CODE"'}, {"script": "finish_inconnu", "motif": "x", "raison": "y"}]
        ecarts = a.ecarts()
        self.assertTrue(any("sorties_dynamiques" in m and "raison" in m for m in ecarts), ecarts)
        self.assertTrue(any("sorties_dynamiques" in m and "finish_inconnu" in m for m in ecarts), ecarts)

    def test_refus_calcule_et_exit_sans_guillemets_sont_refuses(self):
        for ligne in ('refus "$c" "x"', "exit $?", 'sortir "$c"'):
            a = Arbre(self)
            a.ecrire_script("finish_worktree", f'refus 21 "hors"\n{ligne}\n')
            ecarts = a.ecarts()
            self.assertTrue(any("calculée" in m for m in ecarts), (ligne, ecarts))

    def test_utilise_rendu_par_transmission_n_a_pas_besoin_d_un_exit_litteral(self):
        a = Arbre(self)
        a.ecrire_script("finish_worktree", 'refus 21 "hors"\nexit 0\nexit "$CODE"\n')
        a.registre["sorties_dynamiques"] = [dict(SORTIE_CODE)]
        a.registre["codes"].append(entree("finish_worktree", 5, rendu_par="transmission"))
        self.assertEqual(a.ecarts(), [])

    def test_utilise_sans_rendu_par_reste_exige_litteral(self):
        a = Arbre(self)
        a.ecrire_script("finish_worktree", 'refus 21 "hors"\nexit "$CODE"\n')
        a.registre["sorties_dynamiques"] = [dict(SORTIE_CODE)]
        a.registre["codes"].append(entree("finish_worktree", 5))
        self.assertTrue(any("5" in m and "ne le rend pas" in m for m in a.ecarts()))

    def test_rendu_par_transmission_sans_sortie_dynamique_declaree(self):
        a = Arbre(self)
        a.registre["codes"].append(entree("finish_worktree", 5, rendu_par="transmission"))
        ecarts = a.ecarts()
        self.assertTrue(any("5" in m and "rendu_par" in m for m in ecarts), ecarts)

    def test_rendu_par_inconnu_ou_hors_utilise(self):
        a = Arbre(self)
        a.registre["codes"].append(entree("finish_worktree", 5, rendu_par="magie"))
        a.registre["codes"].append(entree("finish_worktree", 6, "jamais_rendu", rendu_par="transmission"))
        ecarts = a.ecarts()
        self.assertTrue(any("5" in m and "rendu_par" in m and "magie" in m for m in ecarts), ecarts)
        self.assertTrue(any("6" in m and "rendu_par" in m for m in ecarts), ecarts)


if __name__ == "__main__":
    unittest.main()
