"""
Tâche 2.4 (change finish-train-v1) : la base du train (conception D4, code 63). Un fetch, puis main local = origin/main ; jamais de réconciliation
par le script ; chaque plage part d'origin/main.

Position du dossier d'exécution : détaché sur main local OU sur origin/main (dans la reprise S1, main local porte déjà le train et le dossier d'exécution
reste sur l'ancien main) ; décision de l'auteur du 2026-10-27, voir aussi test_lancement.py et test_reprise.py.
"""
import re
import unittest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "finish_train"))   # l'aide commune est dans tests/finish_train
from aide_train import AvecTrain  # noqa: E402


class Base(AvecTrain):
    def test_fetch_en_echec(self):
        self.t.branche("feat/x")
        self.t.git("remote", "set-url", "origin", str(self.t.dossier / "inexistant.git"))
        avant = self.t.instantane()
        r = self.t.lance("feat/x")
        self.code(r, 63, "base non établie : fetch d'origin/main en échec ; rien n'est fusionné")
        self.rien_ne_change(avant)

    def test_main_local_en_avance(self):
        self.t.branche("feat/x")
        local = self.t.commit_main({"tools/avance.sh": "a\n"}, "avance locale")
        distant = self.t.origin_main()
        r = self.t.lance("feat/x")
        self.code(r, 63, f"base non établie : main local {local[:12]} diffère d'origin/main {distant[:12]} ; rapproche-les à la main, puis relance ; rien n'est fusionné")
        self.assertEqual(self.t.main(), local)
        self.assertEqual(self.t.distant_main(), distant)

    def test_main_local_en_avance_par_un_commit_etranger_sans_aucune_fusion_de_la_liste(self):
        # décision du 2026-10-27 (D4) : 63 quand main local ne porte aucune fusion de la liste
        x, y = self.deux_branches()
        local = self.t.commit_main({"tools/etranger.sh": "e\n"}, "commit étranger")
        distant = self.t.origin_main()
        avant = self.t.instantane()
        r = self.t.lance(x, y)
        self.code(r, 63, f"base non établie : main local {local[:12]} diffère d'origin/main {distant[:12]} ; rapproche-les à la main, puis relance ; rien n'est fusionné")
        self.rien_ne_change(avant)

    def test_une_branche_deja_dans_origin_main_est_refusee_a_l_admission_en_62_jamais_en_79(self):
        # main local = origin/main, une branche de la liste déjà contenue dans origin/main et une autre pas : état S0, admission, 62 avec la ligne de relance
        self.t.git("branch", "feat/deja", "main")
        self.t.branche("feat/ok")
        avant = self.t.instantane()
        r = self.t.lance("feat/deja", "feat/ok")
        self.code(r, 62, "branche(s) refusée(s) au train : 1 sur 2 ; rien n'est fusionné", f"ligne sans les branches refusées : {self.t.ligne} feat/ok")
        self.contient(r, "  - feat/deja : déjà contenue dans origin/main")
        self.absent(r, "reprise refusée")
        self.rien_ne_change(avant)

    def test_une_branche_deja_dans_origin_main_avec_main_local_en_avance_n_est_jamais_79(self):
        # un sommet n'est « porté » par main local que s'il en est un ancêtre ET n'est pas un ancêtre d'origin/main : ici il l'est, donc aucune fusion de la
        # liste n'est portée et main local en avance donne 63 (lecture retenue : la tâche 2.15 dit 62 ici, mais 62 suppose main local = origin/main)
        self.t.git("branch", "feat/deja", "main")
        self.t.branche("feat/ok")
        self.t.commit_main({"tools/etranger.sh": "e\n"}, "commit étranger")
        r = self.t.lance("feat/deja", "feat/ok")
        self.assertEqual(r.code, 63, r.texte)
        self.absent(r, "reprise refusée")

    def test_deux_lancements_63_puis_62_branche_contenue_dans_origin_main(self):
        # décision D4, option A (2026-10-27, tâche 2.15) : une branche du train déjà contenue dans origin/main alors que main local est en avance :
        # premier lancement 63 (base non établie), main local remis à origin/main, relancement 62 (branche refusée car déjà contenue)
        self.t.git("branch", "feat/deja", "main")
        self.t.branche("feat/ok")
        local = self.t.commit_main({"tools/etranger.sh": "e\n"}, "commit étranger")
        distant = self.t.origin_main()
        r = self.t.lance("feat/deja", "feat/ok")
        self.code(r, 63, f"base non établie : main local {local[:12]} diffère d'origin/main {distant[:12]}")
        self.absent(r, "reprise refusée")
        self.t.poser_main(distant)
        avant = self.t.instantane()
        r = self.t.lance("feat/deja", "feat/ok")
        self.code(r, 62, "branche(s) refusée(s) au train : 1 sur 2 ; rien n'est fusionné", f"ligne sans les branches refusées : {self.t.ligne} feat/ok")
        self.contient(r, "  - feat/deja : déjà contenue dans origin/main")
        self.absent(r, "reprise refusée")
        self.rien_ne_change(avant)

    def test_main_local_en_retard(self):
        # finish-single-b3-b6, B6 (D20, tâche 1.1 B6, R-20261029-39 Q11) : avant, 63 et main local jamais avancé ; maintenant un main local strictement
        # en retard est avancé en avance rapide sur origin/main, l'espace de travail à jour (voir test_avance_rapide.py pour l'échec et les autres cas)
        self.t.branche("feat/x")
        ancien = self.t.main()
        autre = self.t.cloner_ailleurs()
        nouveau = self.t.valider(autre, {"tools/ailleurs.sh": "a\n"}, "poussé ailleurs")
        self.t.git("push", "-q", "origin", "main", cwd=autre)
        r = self.t.lance("--essai", "feat/x")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, f"finish_train : main local en retard avancé sur origin/main : {ancien[:12]} -> {nouveau[:12]}")
        self.assertEqual(self.t.main(), nouveau)
        self.assertTrue((self.t.contenu / "tools" / "ailleurs.sh").is_file(), "l'espace de travail suit main")

    def test_main_local_et_distant_divergents(self):
        self.t.branche("feat/x")
        local = self.t.commit_main({"tools/avance.sh": "a\n"}, "avance locale")
        autre = self.t.cloner_ailleurs()
        nouveau = self.t.valider(autre, {"tools/ailleurs.sh": "a\n"}, "poussé ailleurs")
        self.t.git("push", "-q", "origin", "main", cwd=autre)
        r = self.t.lance("feat/x")
        self.code(r, 63, f"base non établie : main local {local[:12]} diffère d'origin/main {nouveau[:12]}")
        self.assertEqual(self.t.main(), local)

    def test_pilote_de_fusion_personnalise_refuse_avant_tout_merge_tree(self):
        self.t.branche("feat/x")
        self.t.git("config", "merge.zz.driver", "true")
        avant = self.t.instantane()
        r = self.t.lance("feat/x")
        self.code(r, 63, "base non établie : pilote de fusion personnalisé configuré ; rien n'est fusionné")
        self.assertEqual([l for l in self.t.journal_git() if "merge-tree" in l], [])
        self.rien_ne_change(avant)

    def test_le_fetch_est_fait_une_fois_au_depart(self):
        self.t.branche("feat/x")
        r = self.t.lance("--essai", "feat/x")
        self.assertEqual(r.code, 0, r.texte)
        fetchs = [l for l in self.t.journal_git() if re.search(r"(^| )fetch( |$)", l)]
        self.assertEqual(len(fetchs), 1, fetchs)

    def test_la_base_est_origin_main_meme_quand_main_local_porte_le_train(self):
        # reprise au push (S1) : main local est en avance de tout le train ; la ligne du train, les contrôles par branche et la plage
        # du contenu partent d'origin/main, jamais de main local
        x, y = self.deux_branches()
        self.t.etat_fusionne_localement(x, y)
        local = self.t.main()
        base = self.t.origin_main()
        self.assertNotEqual(local, base)
        r = self.t.lance(x, y, entree="o\n")
        self.contient(r, f"train : 2 branche(s), base origin/main {base[:12]}")
        self.assertIsNone(re.search(rf"base origin/main {local[:12]}", r.texte))
        self.assertEqual(r.code, 0, r.texte)


if __name__ == "__main__":
    unittest.main()
