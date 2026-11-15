"""
Tâches 2.12 et 2.14 (change finish-train-v1) : les codes de sortie et les messages de tools/finish_train.sh (conception D17, D18, D23 et D24).

2.12 : chaque code de D17 atteint au moins une fois dans la suite (sauf 72 et 77, réservés, jamais rendus : un test d'index les liste) ; chaque code du
script a un seul sens (code 0 : le sens de la bannière, « fusionné » ou « essai », distingue les deux issues) ; chaque phrase de D18 est vérifiée là où
son code est testé ; l'interruption (130) en trois points, sans jamais défaire une avance rapide ni un push ; aucune trace de pile (76).
2.14 : le journal écrit sur interruption (D23) et la bannière de fin (D24), un cas par sens et par état des références.

Codes déclarés par le script (plage 60 à 81, décision de l'auteur du 2026-10-27) : dans son en-tête seulement (toute option, --help comprise, donne 60), une
ligne « <code> <sens> » chacune.
"""
import os
import re
import signal
import subprocess
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "finish_train"))   # l'aide commune est dans tests/finish_train
from aide_train import AvecTrain, PREFIXE, OUTILS, BASH, paris, secondes, E1, E2, E3, E4, E5, E6  # noqa: E402

# la suite de tools/finish_train.sh tient en cinq dossiers (la durée d'une suite est plafonnée par le lanceur) : tous sont lus par les index
DOSSIERS_TESTS = (Path(__file__).resolve().parent,) + tuple(Path(__file__).resolve().parents[1] / n for n in ("finish_train", "finish_train_npm", "finish_train_base", "finish_train_reprise"))
SCRIPT_TEXTE = OUTILS / "finish_train.sh"

CODES = tuple([0] + list(range(60, 85)) + [129, 130, 141, 143])   # 84 : politique automatique refuse (autonomous-trains-merge, D19, R-20261106-28 Q2 (a)) ; 82 : passe de bout en bout (finish-e2e-proof-shared, tâche 2.7, D11) ; 83 : contrôle 6 de l'arbre (finish-single-b3-b6, tâche 5.5, D19 ; tâche 1.1 B6)
RESERVES = (72, 77)
ATTEINTS_ICI_OU_AILLEURS = tuple(c for c in CODES if c not in RESERVES and c != 0)

ETATS = {"E1": E1, "E2": E2, "E3": E3, "E4": E4, "E5": E5, "E6": E6}

# La table de D24 : code -> (sens, états permis). Sert au test statique : chaque ligne tombe dans l'un des six états.
TABLE_D24 = {
    60: ("refusé", {"E1"}), 61: ("refusé", {"E1"}), 62: ("refusé", {"E2", "E3"}), 63: ("refusé", {"E1", "E2"}), 64: ("refusé", {"E2"}),
    65: ("refusé", {"E2", "E3"}), 66: ("refusé", {"E1", "E2", "E3"}), 67: ("refusé", {"E1"}), 68: ("refusé", {"E2", "E3"}),
    69: ("refusé", {"E2"}), 70: ("refusé", {"E2"}), 71: ("refusé", {"E2"}), 73: ("refusé", {"E2", "E5"}), 74: ("refusé", {"E3"}),
    75: ("fusionné", {"E4"}), 76: ("refusé", {"E1", "E2", "E3", "E4", "E5"}), 78: ("refusé", {"E1"}), 79: ("refusé", {"E6"}), 80: ("refusé", {"E2"}), 81: ("refusé", {"E2"}), 82: ("refusé", {"E2"}), 83: ("refusé", {"E2", "E3"}),   # E3 : contrôle 6 rejoué à la reprise au push (R-20261030-48)
    84: ("refusé", {"E2", "E3", "E4"}),   # autonomous-trains-merge, D19 (R-20261106-28 Q2 (a)) : politique automatique refuse, rien n'est fusionné (E2) ; en --auto, une reprise S1 ou S2 est refusée avant tout push (E3, E4)
    129: ("interrompu", {"E1", "E2", "E3", "E4", "E5"}), 130: ("interrompu", {"E1", "E2", "E3", "E4", "E5"}),
    141: ("interrompu", {"E1", "E2", "E3", "E4", "E5"}), 143: ("interrompu", {"E1", "E2", "E3", "E4", "E5"}),
}


def lignes_du_texte(texte: str) -> list:
    return texte.splitlines()


def analyse_codes(lignes) -> dict:
    """{code: [sens...]} lu sur des lignes « # <code> <sens> » (en-tête) ou « <code> <sens> » (aide), pour les seuls codes connus."""
    trouves = {}
    for ligne in lignes:
        m = re.match(r"^\s*#?\s*(\d+)\s+(\S.*?)\s*$", ligne)
        if m and int(m.group(1)) in CODES:
            trouves.setdefault(int(m.group(1)), []).append(m.group(2))
    return trouves


class Index(unittest.TestCase):
    """Tests statiques : ils lisent les textes, ne lancent rien."""

    def test_chaque_code_de_d17_est_atteint_dans_la_suite_sauf_les_reserves(self):
        atteints = set()
        for fichier in sorted(f for d in DOSSIERS_TESTS for f in d.glob("test_*.py")):
            texte = fichier.read_text(encoding="utf-8")
            for ligne in texte.splitlines():
                for m in re.finditer(r"self\.code\(.*?,\s*(\d{2,3})\b", ligne):
                    atteints.add(int(m.group(1)))
                for m in re.finditer(r"assertEqual\((?:r\.)?code,\s*(\d{2,3})\b", ligne):
                    atteints.add(int(m.group(1)))
                for m in re.finditer(r"assertEqual\(r\.code,\s*(\d{2,3})\b", ligne):
                    atteints.add(int(m.group(1)))
        manquants = [c for c in ATTEINTS_ICI_OU_AILLEURS if c not in atteints]
        self.assertEqual(manquants, [], f"codes de D17 jamais atteints par un test : {manquants}")
        for c in RESERVES:
            self.assertNotIn(c, atteints, f"le code {c} est réservé : aucun test ne doit l'attendre")

    def test_les_codes_reserves_sont_listes_et_jamais_rendus_par_le_script(self):
        self.assertEqual(RESERVES, (72, 77))
        texte = SCRIPT_TEXTE.read_text(encoding="utf-8")
        for c in RESERVES:
            self.assertIsNone(re.search(rf"\b(exit|return)\s+{c}\b", texte), f"le script rend le code réservé {c}")
            self.assertIsNone(re.search(rf"\bcode=\$?\(?{c}\b", texte))

    def test_chaque_code_du_script_a_un_seul_sens_dans_l_en_tete(self):
        entete = SCRIPT_TEXTE.read_text(encoding="utf-8").splitlines()[:200]
        trouves = analyse_codes(l for l in entete if l.lstrip().startswith("#"))
        self.assertEqual(sorted(trouves), sorted(CODES), "l'en-tête déclare exactement les codes de D17 (plage 60 à 81, plus 0, 129, 130, 143)")
        for code, sens in trouves.items():
            self.assertEqual(len(sens), 1, f"le code {code} est déclaré {len(sens)} fois dans l'en-tête")
        sens_non_nuls = [s[0].lower() for c, s in trouves.items() if c != 0]
        self.assertEqual(len(sens_non_nuls), len(set(sens_non_nuls)), "aucun sens partagé par deux codes")
        self.assertIn("fusionné", trouves[0][0])
        self.assertIn("essai", trouves[0][0], "seul le code 0 a deux issues, que le sens de la bannière distingue (D24)")
        for c in RESERVES:
            self.assertIn("réservé", trouves[c][0])

    def test_les_refus_du_script_rendent_seulement_des_codes_declares_chacun_avec_son_sens(self):
        # revue de u5, m-15 : le test « un seul sens par code » lit aussi les refus du script, pas seulement son en-tête. Forme imposée par le registre
        # des codes : tout code rendu par « refus <n> "…" » ou « exit <n> » littéral ; « exit "$code" » est la seule sortie calculée (dans refus())
        texte = SCRIPT_TEXTE.read_text(encoding="utf-8")
        corps = "\n".join(l for l in texte.splitlines() if not l.lstrip().startswith("#"))
        declares = set(analyse_codes(l for l in texte.splitlines()[:200] if l.lstrip().startswith("#")))
        rendus = {int(c) for c in re.findall(r"\brefus (\d+)\b", corps)} | {int(c) for c in re.findall(r"\bexit (\d+)\b", corps)}
        self.assertEqual(sorted(rendus - declares), [], "codes rendus par le script mais absents de l'en-tête")
        self.assertEqual(sorted(rendus & set(RESERVES)), [], "codes réservés rendus")
        attendus = declares - set(RESERVES)
        self.assertEqual(sorted(attendus - rendus - {75, 129, 130, 141, 143}), [], "codes déclarés que le script ne rend jamais")
        self.assertEqual(len(re.findall(r'\bexit "\$', corps)), 1, "une seule sortie calculée : exit \"$code\" dans refus()")
        # un même texte de refus ne sert jamais à deux codes
        sens = {}
        for code, msg in re.findall(r'\brefus (\d+) "(.*?)"(?=\s*(?:[;|)&]|$))', corps, re.M):
            cle = re.sub(r"\$\{[^}]*\}|\$\([^)]*\)|\$\w+", "…", msg)
            sens.setdefault(cle, set()).add(int(code))
        partages = {k: sorted(v) for k, v in sens.items() if len(v) > 1}
        self.assertEqual(partages, {}, "un texte de refus partagé par deux codes")

    def test_le_script_n_ignore_jamais_sigpipe_hors_de_son_piege_de_sortie(self):
        # décision du 2026-10-27 (D17, D23, tâche 2.18) : ni « trap '' PIPE » ni équivalent au niveau du script ; seul le piège de sortie l'ignore pour sa
        # propre exécution ; un piège PIPE sort en 141
        texte = SCRIPT_TEXTE.read_text(encoding="utf-8")
        hors_piege = re.sub(r"^on_exit\(\) \{.*?^\}", "", texte, flags=re.M | re.S)
        code = "\n".join(l for l in hors_piege.splitlines() if not l.lstrip().startswith("#"))
        self.assertIsNone(re.search(r"\btrap\s+(?:''|\"\")\s+[^\n]*\bPIPE\b", code), "SIGPIPE ignoré hors du piège de sortie")
        self.assertIsNone(re.search(r"\btrap\s+(?:''|\"\")\s*(?:$|\n)", code), "trap '' sans signal")
        self.assertIsNotNone(re.search(r"^trap 'SIGCODE=PIPE; exec >/dev/null 2>&1; echo; echo >&2; exit 141' PIPE$", code, re.M), "le piège PIPE sort en 141")

    def test_la_table_de_d24_tombe_dans_les_six_etats(self):
        for code, (sens, etats) in TABLE_D24.items():
            self.assertIn(sens, ("refusé", "fusionné", "interrompu"), code)
            self.assertTrue(etats <= set(ETATS), (code, etats))
        for code in CODES:
            if code in RESERVES or code == 0:
                continue
            self.assertIn(code, TABLE_D24, f"le code {code} manque à la table de D24")
        for code in RESERVES:
            self.assertNotIn(code, TABLE_D24)

    def test_les_six_phrases_d_etat_sont_dans_le_script_mot_pour_mot(self):
        texte = SCRIPT_TEXTE.read_text(encoding="utf-8")
        for nom, phrase in ETATS.items():
            self.assertIn(phrase, texte, f"phrase {nom} absente du script")

    def test_les_quatre_sens_et_le_modele_de_bandeau_sont_dans_le_script(self):
        texte = SCRIPT_TEXTE.read_text(encoding="utf-8")
        for sens in ("fusionné", "refusé", "interrompu", "essai"):
            self.assertIn(sens, texte)
        self.assertIn("===== fin du train : code ", texte)
        self.assertIn("===== arrêt à ", texte)
        self.assertIn("TZ=Europe/Paris", texte)
        self.assertIn("heure indisponible", texte)


class Bandeau(AvecTrain):
    """Vérifications communes de la bannière de fin (D24) sur les lignes d'un journal."""

    def lignes_log(self):
        return self.t.journaux()[-1].read_text(encoding="utf-8").splitlines()

    def bandeau(self, lignes, code, sens, etape=None, etat=None):
        premieres = [l for l in lignes if l.startswith("===== fin du train")]
        self.assertEqual(len(premieres), 1, premieres)
        self.assertRegex(premieres[0], rf"^===== fin du train : code {code} \({sens}\), \d{{4}}-\d\d-\d\d \d\d:\d\d:\d\d Paris =====$")
        secondes_ = [l for l in lignes if l.startswith("===== arrêt à")]
        if code == 0:
            self.assertEqual(secondes_, [], "pas de seconde ligne pour le code 0, quel que soit le sens")
            self.assertEqual(lignes[-1], premieres[0])
        else:
            self.assertEqual(secondes_, [f"===== arrêt à {etape} : {etat} ====="])
            self.assertEqual(lignes[-1], secondes_[0])
            self.assertEqual(lignes[-2], premieres[0])

    def interrompu(self, lignes, code, etape, etat, phrase):
        self.assertEqual(lignes.count(PREFIXE + phrase), 1, "la ligne d'interruption est écrite une fois")
        self.assertEqual(lignes[-3], PREFIXE + phrase)
        self.bandeau(lignes, code, "interrompu", etape, etat)


class Erreurs(AvecTrain):
    def test_76_worktree_d_integration_non_cree_sans_trace_de_pile(self):
        self.t.branche("feat/x")
        avant = self.t.instantane()
        r = self.t.lance("feat/x", extra={"FAKE_WORKTREE_ADD_CODE": "128"}, entree="o\n")
        self.code(r, 76, "calcul impossible (worktree d'intégration non créé)")
        self.contient(r, f"===== arrêt à worktree d'intégration : {E2} =====")
        self.absent(r, "arrêt à dbtest", "Traceback", "erreur inattendue")
        self.assertIsNone(re.search(r"\.sh: line \d+", r.texte), "aucun texte d'erreur du shell")
        self.rien_ne_change(avant)

    def test_aucune_trace_de_pile_sur_une_erreur_de_git(self):
        self.t.branche("feat/a", {"tools/a.sh": "a\n"})
        self.t.branche("feat/b", {"tools/b.sh": "b\n"})
        r = self.t.lance("feat/a", "feat/b", extra={"FAKE_MERGE_TREE_CODE": "128"})
        self.assertEqual(r.code, 64, r.texte)
        self.assertIsNone(re.search(r"Traceback|\.sh: line \d+", r.texte))


class Interruptions(Bandeau):
    def test_130_avant_la_construction_rien_n_est_fusionne(self):
        self.t.branche("feat/x")
        avant_main = self.t.main()
        proc = self.t.demarre("feat/x", extra={"FAKE_MORNING_MODE": "dort"})
        self.t.attend_fichier("matin-demarre")
        os.killpg(proc.pid, signal.SIGINT)
        self.t.reveille()
        code, _ = self.t.termine(proc)
        self.assertEqual(code, 130)
        self.assertEqual(self.t.main(), avant_main)
        self.assertEqual(self.t.distant_main(), avant_main)
        self.assertFalse((self.t.commun() / "pmzilla-fin-en-cours").exists())

    def test_130_pendant_le_runner_rien_n_est_fusionne(self):
        self.t.branche("feat/x")
        avant_main = self.t.main()
        proc = self.t.demarre("feat/x", extra={"FAKE_RUNNER_MODE": "dort"})
        self.t.attend_fichier("runner-demarre")
        os.killpg(proc.pid, signal.SIGINT)
        self.t.reveille()
        code, _ = self.t.termine(proc)
        self.assertEqual(code, 130)
        self.assertEqual(self.t.main(), avant_main)
        self.assertEqual(self.t.distant_main(), avant_main)
        self.assertEqual(self.t.worktrees_train(), [], "le worktree d'intégration est retiré à la sortie")

    def test_130_apres_l_avance_rapide_main_reste_avance_et_la_relance_pousse(self):
        x, y = self.deux_branches()
        ancien = self.t.main()
        (self.t.etat / "prepush-dort").write_text("x", encoding="utf-8")
        proc = self.t.demarre(x, y, entree="o\n")
        self.t.attend_fichier("prepush-demarre")
        os.killpg(proc.pid, signal.SIGINT)
        self.t.reveille()
        code, sortie = self.t.termine(proc)
        self.assertEqual(code, 130, sortie)
        self.assertIn(PREFIXE + "interrompu (code 130) : main avancé sur le train, push non fait : relancer la même ligne", sortie)
        self.assertEqual(len(self.t.chaine_premiers_parents("main", ancien)), 2, "l'avance rapide n'est jamais défaite")
        self.assertEqual(self.t.distant_main(), ancien, "rien n'est poussé")
        (self.t.etat / "prepush-dort").unlink()
        r = self.t.lance(x, y)
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual(self.t.main(), self.t.distant_main())

    def test_130_apres_le_push_le_train_reste_pousse_et_la_relance_nettoie(self):
        x, y = self.deux_branches()
        ancien = self.t.main()
        (self.t.etat / "lsof-arme-sur-push").write_text("x", encoding="utf-8")
        proc = self.t.demarre(x, y, entree="o\n")
        self.t.attend_fichier("lsof-demarre")
        os.killpg(proc.pid, signal.SIGINT)
        self.t.reveille()
        code, sortie = self.t.termine(proc)
        self.assertEqual(code, 130, sortie)
        self.assertIn(PREFIXE + "interrompu (code 130) : train poussé : relancer la même ligne pour finir le nettoyage", sortie)
        self.assertNotEqual(self.t.distant_main(), ancien, "le push n'est jamais défait")
        self.assertEqual(self.t.main(), self.t.distant_main())
        for nom in ("lsof-arme-sur-push", "lsof-arme", "lsof-demarre"):
            fichier = self.t.etat / nom
            if fichier.exists():
                fichier.unlink()
        r = self.t.lance(x, y)
        self.assertEqual(r.code, 0, r.texte)
        self.assertFalse(self.t.dossier_worktree(x).exists())


class JournalSurInterruption(Bandeau):
    LIGNE_RIEN = "interrompu (code {c}) : rien n'est fusionné"

    def demarre_au_runner(self):
        self.t.branche("feat/x")
        proc = self.t.demarre("feat/x", extra={"FAKE_RUNNER_MODE": "dort"})
        self.t.attend_fichier("runner-demarre")
        return proc

    def verifie_runner(self, code):
        # Q232 (a), R-20261101-118 : l'étape de la passe Mac s'appelle « passe Mac » (ex « runner ») : valeur attendue changée par cette réponse de l'auteur
        self.interrompu(self.lignes_log(), code, "passe Mac", E2, self.LIGNE_RIEN.format(c=code))

    def test_sigint_sur_tout_le_groupe_pendant_le_runner(self):
        proc = self.demarre_au_runner()
        os.killpg(proc.pid, signal.SIGINT)
        self.t.reveille()
        code, _ = self.t.termine(proc)
        self.assertEqual(code, 130)
        self.verifie_runner(130)

    def test_sighup_sur_tout_le_groupe(self):
        proc = self.demarre_au_runner()
        os.killpg(proc.pid, signal.SIGHUP)
        self.t.reveille()
        code, _ = self.t.termine(proc)
        self.assertEqual(code, 129)
        self.verifie_runner(129)

    def test_sigterm_apres_la_mort_du_processus_de_copie(self):
        proc = self.demarre_au_runner()
        copies = [pid for pid, nom in self.t.descendants(proc.pid) if nom == "tee"]
        self.assertTrue(copies, "le processus de copie (tee) du script est introuvable")
        for pid in copies:
            os.kill(pid, signal.SIGKILL)
        time.sleep(0.2)
        os.kill(proc.pid, signal.SIGTERM)
        self.t.reveille()
        code, _ = self.t.termine(proc)
        self.assertEqual(code, 143, self.t.journaux()[-1].read_text(encoding="utf-8"))
        self.verifie_runner(143)

    def test_chaque_ligne_une_fois_quand_le_processus_de_copie_vit_encore(self):
        proc = self.demarre_au_runner()
        os.kill(proc.pid, signal.SIGINT)   # au script seul : le processus de copie n'est pas touché
        self.t.reveille()
        code, _ = self.t.termine(proc)
        self.assertEqual(code, 130)
        self.verifie_runner(130)


class SigPipe(Bandeau):
    """Décision du 2026-10-27 (D17, D23, tâche 2.18) : le lecteur de la sortie disparaît, le script sort en 141 par son piège de sortie ; les processus
    qu'il lance gardent l'action par défaut de SIGPIPE."""

    def test_tube_ferme_pendant_le_runner_sort_en_141_avec_le_journal(self):
        self.t.branche("feat/x")
        avant_main = self.t.main()
        proc = self.t.demarre("feat/x", extra={"FAKE_RUNNER_MODE": "pipe_ferme"})
        self.t.attend_fichier("runner-demarre")
        proc.stdout.close()   # le bout de lecture du tube est fermé pendant le runner
        (self.t.etat / "pipe-ferme").write_text("x", encoding="utf-8")
        try:
            code = proc.wait(timeout=60)
        finally:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        self.assertEqual(code, 141)
        lignes = self.lignes_log()
        m = re.match(r"^===== arrêt à (.*) : ", lignes[-1])
        self.assertIsNotNone(m, lignes[-3:])
        self.assertEqual(lignes.count(PREFIXE + "interrompu (code 141) : rien n'est fusionné"), 1, "\n".join(lignes))
        # Q232 (a), R-20261101-118 : l'étape « runner » devient « passe Mac » (valeur attendue changée par cette réponse de l'auteur)
        self.assertIn(m.group(1), ("passe Mac", "question"), "la sortie échoue juste après le runner, avant toute écriture dans main")
        self.interrompu(lignes, 141, m.group(1), E2, "interrompu (code 141) : rien n'est fusionné")
        self.assertEqual(self.t.main(), avant_main)
        self.assertEqual(self.t.distant_main(), avant_main)
        self.assertEqual(self.t.worktrees_train(), [], "le worktree d'intégration est retiré à la sortie")
        self.assertFalse((self.t.commun() / "pmzilla-fin-en-cours").exists(), "le verrou est libéré")

    def test_les_processus_enfants_gardent_sigpipe_par_defaut(self):
        self.t.branche("feat/x")
        r = self.t.lance("feat/x", extra={"FAKE_RUNNER_MODE": "pipe_enfant"}, entree="n\n")
        self.assertEqual(r.code, 0, r.texte)
        statut = (self.t.etat / "yes-status").read_text(encoding="utf-8").strip()
        self.assertEqual(statut, "141", "yes meurt de SIGPIPE (141), il n'échoue pas sur une erreur d'écriture")


ETAPES = ["usage", "lancement", "dossiers du lab", "verrou", "garde du matin", "base", "état des références", "admission", "construction",
          "contrôle des noms", "contrôle 14", "contrôle 6", "worktree d'intégration", "paquets npm", "dbtest", "passe e2e", "runner", "question", "relecture des références", "avance rapide", "push", "nettoyage",
          "vérification finale", "mise à jour du dossier d'exécution"]


class FonctionEtat(AvecTrain):
    """La fonction d'état de D24 elle-même (tâche 2.14, décision du 2026-10-27), pas le texte de la table : le script est lu sans son dernier appel
    (main) et prolongé d'un harnais qui appelle compute_banner pour chaque code et chaque étape, une fois avec main local égal au main lu au début et
    une fois avec main local déplacé hors du train testé."""

    def harnais(self) -> str:
        texte = SCRIPT_TEXTE.read_text(encoding="utf-8")
        fin = 'main "$@"\nexit 76\n'
        self.assertTrue(texte.endswith(fin), "le script finit par main puis exit 76")
        codes = " ".join(str(c) for c in sorted(set(TABLE_D24) - {0}))
        etapes = "\n".join(ETAPES)
        return texte[: -len(fin)] + f'''
# --- harnais de test : appelle la fonction de bannière, rien d'autre
FINISHED=1
WS="$H_WS"
cas() {{ # nom code étape ref_lu ff push départ main_au_début sommet
  REF_READ=$4; FF_DONE=$5; PUSH_DONE=$6; START_STATE=$7; MAIN_START=$8; TRAIN_TIP=$9; STEP="$3"
  compute_banner "$2"
  printf '%s|%s|%s|%s|%s\\n' "$1" "$2" "$STEP" "$SENS" "$ETAT"
}}
while IFS= read -r etape; do
  for code in {codes}; do
    cas intact "$code" "$etape" 1 0 0 S0 "$H_MAIN" "$H_AUTRE"
    cas deplace "$code" "$etape" 1 0 0 S0 "$H_AUTRE" "$H_AUTRE"
    cas avance_rapide "$code" "$etape" 1 1 0 S0 "$H_MAIN" "$H_MAIN"
    cas avance_rapide_deplace "$code" "$etape" 1 1 0 S0 "$H_MAIN" "$H_AUTRE"
    cas pousse "$code" "$etape" 1 1 1 S0 "$H_MAIN" "$H_MAIN"
    cas non_lu "$code" "$etape" 0 0 0 S0 "$H_MAIN" "$H_AUTRE"
  done
done <<'ETAPES'
{etapes}
ETAPES
exit 0
'''

    def lignes(self):
        harnais = self.t.run / "tools" / "harnais_train.sh"
        harnais.write_text(self.harnais(), encoding="utf-8")
        env = self.t.env({"H_WS": str(self.t.contenu), "H_MAIN": self.t.main(), "H_AUTRE": "f" * 40})
        fait = subprocess.run([BASH, str(harnais)], cwd=self.t.lab, env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(fait.returncode, 0, fait.stdout + fait.stderr)
        return [l.split("|") for l in fait.stdout.splitlines() if l.count("|") == 4]

    def test_e2_n_est_jamais_rendu_quand_main_local_a_quitte_le_train_teste(self):
        self.t.branche("feat/x")
        lignes = self.lignes()
        self.assertEqual(len(lignes), len(ETAPES) * (len(TABLE_D24)) * 6)
        for nom, code, etape, sens, etat in lignes:
            code = int(code)
            if code == 75 and nom not in ("pousse", "non_lu"):
                continue   # le code 75 n'existe qu'après le push
            if nom == "non_lu":
                self.assertEqual(etat, E1, (nom, code, etape))
            elif code == 79:
                self.assertEqual(etat, E6, (nom, code, etape))
            elif nom == "pousse":
                self.assertEqual(etat, E4, (nom, code, etape))
            elif nom == "intact":
                self.assertEqual(etat, E2, (nom, code, etape))
            elif nom == "deplace":
                self.assertNotEqual(etat, E2, f"E2 rendu avec main déplacé : code {code}, étape {etape}")
                self.assertEqual(etat, E5, (nom, code, etape))
            elif nom == "avance_rapide":
                self.assertEqual(etat, E3, (nom, code, etape))
            elif nom == "avance_rapide_deplace":
                self.assertEqual(etat, E5, (nom, code, etape))
            self.assertIn(etat, ETATS.values())
        # le cas courant de la décision : 73 à la relecture des références
        cas = {(nom, int(code)): etat for nom, code, etape, sens, etat in lignes if etape == "relecture des références"}
        self.assertEqual(cas[("intact", 73)], E2)
        self.assertEqual(cas[("deplace", 73)], E5)

    def test_le_sens_suit_le_code(self):
        self.t.branche("feat/x")
        for nom, code, etape, sens, etat in self.lignes():
            code = int(code)
            attendu = "fusionné" if code == 75 else "interrompu" if code in (129, 130, 141, 143) else "refusé"
            self.assertEqual(sens, attendu, (code, etape))


class BandeauParSens(Bandeau):
    def test_fusionne_heure_de_paris_quel_que_soit_le_fuseau(self):
        self.t.branche("feat/x")
        avant = secondes(paris())
        r = self.t.lance("feat/x", extra={"TZ": "America/Los_Angeles"}, entree="o\n")
        apres = secondes(paris())
        self.assertEqual(r.code, 0, r.texte)
        lignes = self.t.log().splitlines()
        self.bandeau(lignes, 0, "fusionné")
        m = re.search(r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) Paris =====$", lignes[-1])
        self.assertTrue(avant - 1 <= secondes(m.group(1)) <= apres + 1, (avant, m.group(1), apres))
        self.assertIn(lignes[-1], r.texte, "la bannière est aussi à l'écran")

    def test_refuse_runner_rouge(self):
        self.t.branche("feat/x")
        main = self.t.main()
        r = self.t.lance("feat/x", extra={"FAKE_RUNNER_MODE": "rouge"}, entree="o\n")
        self.assertEqual(r.code, 70, r.texte)
        self.bandeau(self.t.log().splitlines(), 70, "refusé", "passe Mac", E2)   # Q232 (a), R-20261101-118 (ex « runner »)
        self.assertEqual(self.t.main(), main)

    def test_interrompu_pendant_le_nettoyage_apres_le_push(self):
        x, y = self.deux_branches()
        (self.t.etat / "lsof-arme-sur-push").write_text("x", encoding="utf-8")
        proc = self.t.demarre(x, y, entree="o\n")
        self.t.attend_fichier("lsof-demarre")
        os.killpg(proc.pid, signal.SIGINT)
        self.t.reveille()
        code, _ = self.t.termine(proc)
        self.assertEqual(code, 130)
        self.bandeau(self.lignes_log(), 130, "interrompu", "nettoyage", E4)

    def test_essai_rapide_et_reponse_autre_que_o(self):
        self.t.branche("feat/x")
        r = self.t.lance("--essai", "feat/x")
        self.assertEqual(r.code, 0, r.texte)
        self.bandeau(self.lignes_log(), 0, "essai")
        for f in self.t.journaux():
            f.unlink()
        r = self.t.lance("feat/x", entree="n\n")
        self.assertEqual(r.code, 0, r.texte)
        self.bandeau(self.lignes_log(), 0, "essai")

    def test_reprise_au_push_apres_un_push_refuse(self):
        self.t.branche("feat/x")
        self.t.refuser_le_push()
        r = self.t.lance("feat/x", entree="o\n")
        self.assertEqual(r.code, 74, r.texte)
        self.bandeau(self.lignes_log(), 74, "refusé", "push", E3)

    def test_reprise_au_push_refusee_par_la_garde_du_matin(self):
        self.t.branche("feat/x")
        self.t.etat_fusionne_localement("feat/x")
        # la garde laisse passer au départ et refuse juste avant le push : l'état est E3 (D24)
        (self.t.etat / "matin.n").unlink()   # le compteur de la fausse garde repart de zéro
        r =self.t.lance("feat/x", extra={"FAKE_MORNING_MODE": "refuse_des_le_second"})
        self.assertEqual(r.code, 66, r.texte)
        self.bandeau(self.lignes_log(), 66, "refusé", "garde du matin", E3)

    def test_main_inchange_apres_un_refus_a_l_admission(self):
        # R-20261028-96 (données d'entrée) : le refus par le contrôle 6 à l'admission est retiré par D19 ; la cause est maintenant un worktree pas propre
        self.t.branche("feat/x")
        (self.t.dossier_worktree("feat/x") / "sale.txt").write_text("x\n", encoding="utf-8")
        main = self.t.main()
        r = self.t.lance("feat/x", entree="o\n")
        self.assertEqual(r.code, 62, r.texte)
        self.bandeau(self.lignes_log(), 62, "refusé", "admission", E2)
        self.assertEqual(self.t.main(), main)

    def test_relecture_des_references_donne_e5_quand_main_local_a_bouge(self):
        # décision du 2026-10-27 (D24, tâche 2.14) : 73 à la relecture des références donne E5 quand un commit étranger a déplacé main local
        self.t.branche("feat/x")
        r = self.t.lance("feat/x", extra={"FAKE_RUNNER_MAIN": "1"}, entree="o\n")
        self.assertEqual(r.code, 73, r.texte)
        self.bandeau(self.lignes_log(), 73, "refusé", "relecture des références", E5)

    def test_relecture_des_references_donne_e2_quand_main_local_n_a_pas_bouge(self):
        # une branche a bougé pendant le runner : main local est toujours le main lu au début
        self.t.branche("feat/x")
        r = self.t.lance("feat/x", extra={"FAKE_RUNNER_BRANCHE_DANS": str(self.t.dossier_worktree("feat/x"))}, entree="o\n")
        self.assertEqual(r.code, 73, r.texte)
        self.bandeau(self.lignes_log(), 73, "refusé", "relecture des références", E2)

    def test_avance_rapide_en_echec_main_inchange_donne_e2(self):
        # revue de u5, m-2 : l'avance rapide échoue (un fichier non suivi de l'espace de travail serait écrasé), main n'a pas bougé : E2, jamais E5
        self.t.branche("feat/x")
        main = self.t.main()
        r = self.t.lance("feat/x", extra={"FAKE_RUNNER_ECRIT_ESPACE": "tools/feat_x.sh"}, entree="o\n")
        self.code(r, 73, "avance rapide de main en échec, main inchangé (", "l'espace de travail n'est pas propre")
        self.bandeau(self.lignes_log(), 73, "refusé", "avance rapide", E2)
        self.assertEqual(self.t.main(), main)
        self.assertEqual(self.t.distant_main(), main)

    def test_un_fichier_non_suivi_sous_bmad_output_ecrit_pendant_le_runner_ne_donne_pas_75(self):
        # R-20261102-6 : un livrable de posture non suivi écrit pendant le contrôle final ne fait plus finir le train en 75
        self.t.branche("feat/x")
        r = self.t.lance("feat/x", extra={"FAKE_RUNNER_ECRIT_ESPACE": "_bmad-output/pmzilla/livrable.md"}, entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        self.bandeau(self.lignes_log(), 0, "fusionné")

    def test_un_non_suivi_sous_bmad_output_au_chemin_d_un_fichier_du_train_donne_73_avec_la_cause(self):
        # revue Opus du 2026-11-02 : le runner écrit, dans l'espace de travail, le chemin que la fusion apporte ; l'avance rapide échoue (73), la cause est dite
        self.t.branche("feat/x", {"_bmad-output/pmzilla/livrable.md": "branche\n"})
        main = self.t.main()
        r = self.t.lance("feat/x", extra={"FAKE_RUNNER_ECRIT_ESPACE": "_bmad-output/pmzilla/livrable.md"}, entree="o\n")
        self.code(r, 73, "avance rapide de main en échec, main inchangé (",
                  "fichier non suivi de l'espace de travail au chemin d'un fichier du train : 1 ; le retirer de l'espace de travail puis relancer")
        self.contient(r, "\n_bmad-output/pmzilla/livrable.md\n")   # chemin seul sur sa ligne, comme les chemins en conflit
        self.assertEqual(self.t.main(), main)

    def test_un_fichier_suivi_modifie_sous_bmad_output_pendant_le_runner_donne_75(self):
        # R-20261102-6 : l'exception ne couvre pas un fichier suivi ; la vérification finale le constate
        self.t.commit_main({"_bmad-output/pmzilla/suivi.md": "a\n"}, "livrable suivi", pousser=True)
        self.t.mettre_a_jour_run()
        self.t.branche("feat/x")
        r = self.t.lance("feat/x", extra={"FAKE_RUNNER_ECRIT_ESPACE": "_bmad-output/pmzilla/suivi.md"}, entree="o\n")
        self.assertEqual(r.code, 75, r.texte)
        # une cause de fin incomplète est listée « - … » sous la phrase du 75, sans préfixe (comme dans test_nettoyage)
        self.contient(r, "train fusionné et poussé, fin incomplète :", "  - vérification finale : l'espace de travail n'est pas propre")

    def test_relecture_impossible_a_une_phrase_distincte(self):
        # revue de u5, m-3 : le fetch de la relecture échoue : une phrase propre, et E2 puisque main n'a pas bougé
        self.t.branche("feat/x")
        r = self.t.lance("feat/x", extra={"FAKE_RUNNER_ORIGIN_CASSE": str(self.t.dossier / "inexistant.git")}, entree="o\n")
        self.code(r, 73, "relecture des références impossible : fetch d'origin/main en échec ; rien n'est fusionné")
        self.bandeau(self.lignes_log(), 73, "refusé", "relecture des références", E2)

    def test_premier_etat_avant_la_lecture_des_references(self):
        # usage : l'écran porte la bannière, la seconde ligne dit E1
        r = self.t.lance()
        self.assertEqual(r.code, 60, r.texte)
        self.assertIn(f"===== arrêt à usage : {E1} =====", r.texte)
        self.assertRegex(r.texte, r"===== fin du train : code 60 \(refusé\), \d{4}-\d\d-\d\d \d\d:\d\d:\d\d Paris =====")

    def test_references_dans_aucun_etat_connu(self):
        x, y = self.deux_branches()
        self.t.etat_fusionne_localement(x, y)
        self.t.commit_main({"tools/etranger.sh": "e\n"}, "commit étranger")
        r = self.t.lance(x, y)
        self.assertEqual(r.code, 79, r.texte)
        self.bandeau(self.lignes_log(), 79, "refusé", "état des références", E6)


if __name__ == "__main__":
    unittest.main()
