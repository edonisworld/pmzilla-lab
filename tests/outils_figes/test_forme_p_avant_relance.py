"""
Ce que les enveloppes figées font AVANT leur ligne de relance (bash-sandbox-n2, tâche 19.1, design D13 ; R-20261111-38).

Sur le /bin/bash 3.2.57 du Mac, `-p` ne ferme pas CDPATH (constat M2, suite forme_p_mac). CDPATH est tenu par la relance sous `env -i` des enveloppes
et par la garde de session ; la relance ne tient que si rien n'est exécuté avant elle. Deux tests :

 - statique : aucune enveloppe de tools/outils_figes/liste.txt (les cinq, et toute enveloppe ajoutée) n'exécute de commande nommée ni de `cd` avant sa
   ligne de relance, c'est-à-dire avant le `fi` du bloc `if [[ ${FIGE_RELANCE-} != "$$" ]]` : seuls des commentaires, `[[ … ]]` et
   `exec /usr/bin/env …` y sont admis ; un témoin rouge (une enveloppe factice qui fait un `cd` avant) prouve que le contrôle voit l'écart ;
 - dynamique : CDPATH posé par l'appelant n'a aucun effet sur le `cd` de l'enveloppe relancée.

Remplace : rien. Retrait : avec le bac à sable (R-20261111-38). La source de la liste des enveloppes est tools/outils_figes/liste.txt : un test
vérifie que chaque entrée `E` est lue (jamais un ensemble vide ni une entrée non lue).

    uv run tools/pilot.py freeze --check && bash tests/run_all.sh outils_figes
"""
import re
import subprocess
import unittest

import test_outils_figes as base

BIBLIOTHEQUE = "enveloppe.sh"   # fonctions communes, sourcée par les enveloppes après leur relance : elle n'a pas de ligne de relance
LIGNE_SI = re.compile(r'^if \[\[ \$\{FIGE_RELANCE-\} != "\$\$" \]\]; then$')
PREFIXE_EXEC = "exec /usr/bin/env -i "
INTERDITS_DANS_EXEC = ("$(", "`", ";", "&", "|", "<", ">")


def ligne_exec_admise(ligne):
    """`exec /usr/bin/env -i …` sans substitution, ni redirection, ni enchaînement."""
    reste = ligne.strip()
    return reste.startswith(PREFIXE_EXEC) and not any(m in reste for m in INTERDITS_DANS_EXEC)


def controle_avant_relance(texte):
    """Les écarts d'une enveloppe avec la règle : rien d'exécutable avant le `fi` du bloc de relance, sauf `[[ … ]]` et `exec /usr/bin/env …`."""
    lignes = texte.splitlines()
    ecarts = []
    debut = None
    for i, ligne in enumerate(lignes):
        if LIGNE_SI.match(ligne):
            debut = i
            break
        if ligne.strip() and not ligne.lstrip().startswith("#"):
            ecarts.append(f"ligne {i + 1} exécutée avant la relance : {ligne.strip()[:40]}")
    if debut is None:
        return ecarts + ["bloc de relance absent"]
    fin = None
    for j in range(debut + 1, len(lignes)):
        ligne = lignes[j]
        if ligne == "fi":
            fin = j
            break
        if ligne.strip() and not ligne.lstrip().startswith("#") and not ligne_exec_admise(ligne):
            ecarts.append(f"ligne {j + 1} dans le bloc de relance : {ligne.strip()[:40]}")
    if fin is None:
        ecarts.append("bloc de relance non fermé")
    elif not any(ligne_exec_admise(l) for l in lignes[debut + 1:fin]):
        ecarts.append("le bloc ne relance rien")
    return ecarts


class StatiqueAvantRelance(unittest.TestCase):
    def enveloppes(self):
        return [chemin for genre, chemin in base.liste_figee() if genre == "E" and chemin != BIBLIOTHEQUE]

    def test_la_liste_est_lue_et_n_est_pas_vide(self):
        noms = self.enveloppes()
        self.assertGreaterEqual(len(noms), 5, noms)
        for nom in ("ci_local.sh", "gh_issue.sh", "flow_views.sh", "worktree.sh", "npm_ci.sh"):
            self.assertIn(nom, noms)
        self.assertTrue(any(g == "E" and c == BIBLIOTHEQUE for g, c in base.liste_figee()), "la bibliothèque commune a quitté la liste : revoir le test")

    def test_aucune_enveloppe_n_execute_quoi_que_ce_soit_avant_sa_relance(self):
        for nom in self.enveloppes():
            with self.subTest(enveloppe=nom):
                texte = (base.SOURCE / nom).read_text(encoding="utf-8")
                self.assertEqual(controle_avant_relance(texte), [])

    def test_la_bibliotheque_n_est_pas_une_enveloppe_et_n_a_pas_de_relance(self):
        """Elle est sourcée après la relance : l'exclusion du test ci-dessus est fondée sur ce fait."""
        texte = (base.SOURCE / BIBLIOTHEQUE).read_text(encoding="utf-8")
        self.assertNotIn("FIGE_RELANCE-", texte)
        for nom in self.enveloppes():
            self.assertIn('\n. "$FIGES/enveloppe.sh"\n', (base.SOURCE / nom).read_text(encoding="utf-8"), nom)

    # --- témoins rouges : le contrôle voit l'écart -----------------------------------------------------------------------------------
    def test_temoin_rouge_un_cd_avant_la_relance(self):
        factice = ('#!/bin/bash\n# en-tête\ncd /un/dossier\n'
                   'if [[ ${FIGE_RELANCE-} != "$$" ]]; then\n  exec /usr/bin/env -i "FIGE_RELANCE=$$" /bin/bash --noprofile --norc "$0" "$@"\nfi\n')
        self.assertTrue(any("cd /un/dossier" in e for e in controle_avant_relance(factice)), controle_avant_relance(factice))

    def test_temoin_rouge_une_commande_nommee_avant_la_relance(self):
        factice = ('#!/bin/bash\nPATH=/usr/bin:/bin\ndirname "$0" > /dev/null\n'
                   'if [[ ${FIGE_RELANCE-} != "$$" ]]; then\n  exec /usr/bin/env -i "FIGE_RELANCE=$$" /bin/bash --noprofile --norc "$0" "$@"\nfi\n')
        self.assertGreaterEqual(len(controle_avant_relance(factice)), 2)

    def test_temoin_rouge_un_cd_dans_le_bloc_de_relance(self):
        factice = ('#!/bin/bash\nif [[ ${FIGE_RELANCE-} != "$$" ]]; then\n  cd /un/dossier\n'
                   '  exec /usr/bin/env -i "FIGE_RELANCE=$$" /bin/bash --noprofile --norc "$0" "$@"\nfi\n')
        self.assertTrue(any("cd /un/dossier" in e for e in controle_avant_relance(factice)))

    def test_temoin_rouge_une_substitution_dans_la_ligne_de_relance(self):
        factice = ('#!/bin/bash\nif [[ ${FIGE_RELANCE-} != "$$" ]]; then\n  exec /usr/bin/env -i "FIGE_RELANCE=$(pwd)" /bin/bash "$0"\nfi\n')
        self.assertNotEqual(controle_avant_relance(factice), [])

    def test_temoin_rouge_pas_de_bloc_de_relance(self):
        self.assertIn("bloc de relance absent", controle_avant_relance("#!/bin/bash\n# rien\n"))
        self.assertIn("bloc de relance absent", controle_avant_relance("#!/bin/bash\n# rien\nexit 0\n"))

    def test_temoin_vert_l_enveloppe_conforme(self):
        conforme = ('#!/bin/bash\n# en-tête\n\nif [[ ${FIGE_RELANCE-} != "$$" ]]; then\n'
                    '  exec /usr/bin/env -i "FIGE_RELANCE=$$" /bin/bash --noprofile --norc "$0" "$@"\nfi\nunset FIGE_RELANCE\n')
        self.assertEqual(controle_avant_relance(conforme), [])


class CdpathSansEffetSurLEnveloppeRelancee(base.Dossier):
    """CDPATH posé par l'appelant n'a aucun effet sur le `cd` de l'enveloppe relancée (R-20261111-38)."""

    def decor(self):
        """Un dossier de leurre portant le nom du dossier des outils figés, en CDPATH ; l'enveloppe est appelée par un chemin RELATIF."""
        leurre = self.base / "leurre"
        (leurre / self.figes.name).mkdir(parents=True)
        return leurre

    def appelle(self, leurre, avec_cdpath=True):
        environ = {"PATH": "/usr/bin:/bin", "HOME": str(self.base)}
        if avec_cdpath:
            environ["CDPATH"] = str(leurre)
        return subprocess.run(["/bin/bash", f"{self.figes.name}/ci_local.sh", "places", "--json"], capture_output=True, text=True,
                              cwd=str(self.base), env=environ)

    def test_controle_de_sensibilite_cdpath_detourne_un_cd_relatif(self):
        """Dans ce montage, un `cd` relatif sous CDPATH va bien dans le leurre : sinon le test suivant ne prouverait rien."""
        leurre = self.decor()
        r = subprocess.run(["/bin/bash", "-c", f"cd -P -- {self.figes.name} && pwd -P"], capture_output=True, text=True, cwd=str(self.base),
                           env={"PATH": "/usr/bin:/bin", "HOME": str(self.base), "CDPATH": str(leurre)})
        self.assertEqual(r.stdout.strip().split("\n")[-1], str((leurre / self.figes.name).resolve()), r.stderr)

    def test_cdpath_n_a_aucun_effet_sur_le_cd_de_l_enveloppe_relancee(self):
        leurre = self.decor()
        sans = self.appelle(leurre, avec_cdpath=False)
        self.assertEqual(sans.returncode, 0, sans.stderr)
        arguments_sans = self.args_ci()
        for fichier in self.aux.glob("trace-*"):
            fichier.unlink()
        avec = self.appelle(leurre)
        self.assertEqual(avec.returncode, 0, avec.stderr)
        self.assertEqual(avec.stderr, sans.stderr)
        self.assertEqual(self.args_ci(), arguments_sans)
        self.assertEqual(self.args_ci()[1:], ["places", "--json"])


if __name__ == "__main__":
    unittest.main()
