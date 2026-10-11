"""
Tests de l'étape mcp du script d'installation (tools/install_lab_mcp.py) : enregistrement du serveur de la bibliothèque.
Simulacre `claude` à état : le fichier $INSTALL_LAB_ETAT/mcp contient la déclaration enregistrée (absent = non enregistré).

    uv run python -W ignore -m unittest discover -s tests/install_lab -p "test_mcp.py" -q -f
"""
import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

from aide_install import TOOLS_REELS, CasDeBase

sys.path.insert(0, str(TOOLS_REELS))
import install_lab_context as c    # noqa: E402
import install_lab_mcp as mcp      # noqa: E402

CORPS_CLAUDE = r'''
E="$INSTALL_LAB_ETAT/mcp"
case "$1 $2" in
  "mcp get") [ -e "$E" ] || { echo "No MCP server found with name: $3"; exit 1; }; echo "pmzilla-library:"; cat "$E"; exit 0 ;;
  "mcp add") echo "$*" > "$E"; exit 0 ;;
  "mcp remove") rm -f "$E"; exit 0 ;;
esac
exit 0
'''


class EtapeMcp(CasDeBase):
    def setUp(self):
        super().setUp()
        self.fx.simulacre("claude", CORPS_CLAUDE)
        self.fx.simulacre("uv")
        self.fx.drapeau("links-ok")
        self.lien = self.fx.maison / "PMZilla-Lab" / "pmzilla_lab_library.py"

    def enregistre(self):
        return (self.fx.etat / "mcp").read_text(encoding="utf-8") if (self.fx.etat / "mcp").exists() else None

    def lancer(self, *extra, reponses=""):
        return self.fx.lancer("--mode", "fresh", "--step", "mcp", *extra, reponses=reponses)

    def test_enregistre_apres_confirmation_avec_le_lanceur_du_path(self):
        p = self.lancer(reponses="y\n")
        self.assertEqual(p.code, 0, p.texte)
        ajouts = p.appels_de("claude mcp add")
        self.assertEqual(len(ajouts), 1, p.appels)
        a = ajouts[0]
        for morceau in ("--scope user", "--transport stdio", "pmzilla-library", "-- uv run", str(self.lien), "serve"):
            self.assertIn(morceau, a)
        self.assertEqual(p.appels_de("claude mcp remove"), [])

    def test_base_non_prete_enregistre_avec_le_fichier(self):
        p = self.lancer(reponses="y\n")           # aucun docker : la base n'est pas prête
        self.assertTrue(p.appels_de("claude mcp add")[0].endswith("serve --backend sqlite"), p.appels)

    def test_base_prete_sans_option_de_secours(self):
        ctx = c.Contexte(racine=self.fx.racine, maison=self.fx.maison, etat={"base_ok": True})
        with mock.patch.dict(os.environ, self.fx.environnement()), mock.patch("builtins.input", return_value="y"), \
                redirect_stdout(io.StringIO()):
            r = mcp.executer_mcp(ctx)
        self.assertEqual(r.etat, c.FAIT)
        ajout = self.fx.lire_appels()[-1]
        self.assertTrue(ajout.startswith("claude mcp add"), ajout)
        self.assertTrue(ajout.endswith("serve"), ajout)
        self.assertNotIn("sqlite", ajout)

    def test_deja_enregistre_saute(self):
        self.lancer(reponses="y\n")
        p = self.lancer()
        self.assertEqual(p.code, 0, p.texte)
        self.assertIn("step mcp: already done, skipped", p.lignes())
        self.assertEqual(self.fx.appels_qui_changent(p.appels), [])

    def test_enregistre_autrement_refus_par_defaut(self):
        (self.fx.etat / "mcp").write_text("command: node /autre/serveur.js\n", encoding="utf-8")
        for reponses in ("", "n\n"):
            p = self.lancer(reponses=reponses)
            self.assertEqual(p.code, 4, p.texte)
            self.assertEqual(self.fx.appels_qui_changent(p.appels), [])
            self.assertEqual(self.enregistre(), "command: node /autre/serveur.js\n")
            self.assertIn("mcp: declined", p.texte)

    def test_enregistre_autrement_remplace_apres_confirmation(self):
        (self.fx.etat / "mcp").write_text("command: node /autre/serveur.js\n", encoding="utf-8")
        p = self.lancer(reponses="y\ny\n")
        self.assertEqual(p.code, 0, p.texte)
        self.assertEqual(len(p.appels_de("claude mcp remove")), 1)
        self.assertIn("claude mcp remove pmzilla-library --scope user", p.appels)
        self.assertIn(str(self.lien), self.enregistre())
        self.assertLess(p.appels.index("claude mcp remove pmzilla-library --scope user"),
                        next(i for i, a in enumerate(p.appels) if a.startswith("claude mcp add")))

    def test_passage_a_blanc_sans_changement(self):
        avant = self.fx.empreinte()
        p = self.lancer("--dry-run")
        self.assertEqual(p.code, 0, p.texte)
        self.assertEqual(self.fx.empreinte(), avant)
        self.assertEqual(self.fx.appels_qui_changent(p.appels), [])
        self.assertTrue(any(l.startswith("dry run: would run claude mcp add") for l in p.lignes()), p.lignes())

    def test_passage_a_blanc_enregistre_autrement_montre_remplacement(self):
        (self.fx.etat / "mcp").write_text("command: node /autre/serveur.js\n", encoding="utf-8")
        p = self.lancer("--dry-run")
        self.assertEqual(self.fx.appels_qui_changent(p.appels), [])
        textes = "\n".join(p.lignes())
        self.assertIn("dry run: would run claude mcp remove pmzilla-library --scope user", textes)
        self.assertIn("dry run: would run claude mcp add", textes)

    def test_uv_introuvable_echoue_clairement(self):
        self.fx.retirer("uv")
        p = self.lancer(reponses="y\n")
        self.assertEqual(p.code, 1, p.texte)
        self.assertIn("uv", p.texte)
        self.assertIn("mcp", p.texte)
        self.assertEqual(p.appels_de("claude mcp add"), [])

    def test_commande_d_ajout_qui_echoue(self):
        self.fx.simulacre("claude", 'case "$1 $2" in "mcp get") exit 1 ;; "mcp add") exit 1 ;; esac; exit 0')
        p = self.lancer(reponses="y\n")
        self.assertEqual(p.code, 1, p.texte)
        self.assertIn("step mcp: failed", p.texte)
        self.assertIn("claude mcp add", p.texte)

    def test_depend_de_links(self):
        self.fx.drapeau("links-ok", False)
        p = self.lancer(reponses="y\n")
        self.assertEqual(p.code, 4, p.texte)
        self.assertEqual(p.appels_de("claude mcp add"), [])


if __name__ == "__main__":
    unittest.main()
