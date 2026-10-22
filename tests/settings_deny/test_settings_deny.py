"""Règles `deny` de .claude/settings.json : ce que Claude Code ne peut pas lancer ni lire.

Les sous-commandes qui contactent le vrai Jira (history_jira.py test, collect, check --key ; export_jira_api.py
diagnose, fields, export ; teams-table et compare, retirées, restent interdites) et les fichiers sensibles de Flux-Lab/ sont interdits à Claude Code. Pendant la
transition vers les noms anglais (plan de la version anglaise, 7.1), l'ANCIEN ET le NOUVEAU nom doivent être interdits,
avec chaque lanceur et chaque façon d'écrire le chemin du script. Le test applique les règles à des commandes complètes
(le joker * vaut n'importe quelle suite) : il échoue dès qu'un ancien ou un nouveau nom n'est plus interdit.

Aucune commande n'est lancée ; le test ne lit que .claude/settings.json et les noms des sous-commandes dans les scripts.
"""
import itertools
import json
import re
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
TOOLS = RACINE / "tools"
sys.path.insert(0, str(TOOLS))
from watch_paths import OWN_COLLECTION  # noqa: E402

# Sous-commandes qui contactent Jira, ancien et nouveau nom. Un tuple (nom, options) : la commande n'appelle Jira
# qu'avec l'une de ces options (history_jira.py check sans --key compare des fichiers locaux).
SCRIPTS_HISTORIQUE = ("historique_jira.py", "history_jira.py")
SOUS_COMMANDES_HISTORIQUE = [("test", ()), ("collecte", ()), ("collect", ()),
                             ("controle", ("--cle", "--key")), ("check", ("--cle", "--key"))]
SCRIPTS_EXPORT = ("export_jira_api.py",)
# table-equipes, teams-table et compare : sous-commandes supprimées du script, règles deny gardées (compare ajoutée, elle couvre aussi comparer).
SOUS_COMMANDES_EXPORT = [("diagnostic", ()), ("diagnose", ()), ("champs", ()), ("fields", ()),
                         ("table-equipes", ()), ("teams-table", ()), ("compare", ()), ("comparer", ()), ("export", ())]
LANCEURS = ("uv run", "uv run python", "uv run python3", "uv run --with pyyaml --with requests", "uv run -q",
            "python", "python3", "python3 -I")
CHEMINS = ("tools/{s}", "./tools/{s}", "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}",
           "~/PMZilla-Lab/workspace/tools/{s}", "~/PMZilla-Lab/{s}", "$HOME/PMZilla-Lab/{s}",
           "/Users/quelquun/PMZilla-Lab/{s}", "{s}")

# Règles d'avant le lot 3 (anciens noms des scripts Jira), gardées : elles protègent d'éventuelles copies restées sur le disque.
REGLES_ANCIENNES = [
    f"Bash({lanceur} tools/{commande})"
    for lanceur in ("uv run", "python", "python3")
    for commande in ("historique_jira.py test*", "historique_jira.py collecte*", "historique_jira.py controle*--cle*",
                     "export_jira_api.py diagnostic*", "export_jira_api.py champs*",
                     "export_jira_api.py table-equipes*", "export_jira_api.py export*")]

DOSSIERS_SENSIBLES = ("Flux-Lab/exports/a.csv", "Flux-Lab/historique/b.json", "Flux-Lab/equipes-assets.yaml",
                      "Flux-Lab/noms-sensibles.txt", "Flux-Lab/tableaux/c.html")
LECTEURS = ("cat", "head -n 5", "tail -f", "less", "more", "grep -r secret", "awk '{print $1}'", "sed -n 1,5p", "cp")


def motif_en_regex(motif: str) -> re.Pattern:
    """« Bash(motif) » : le joker * vaut n'importe quelle suite (y compris vide), tout le reste est littéral."""
    return re.compile("".join(".*" if c == "*" else re.escape(c) for c in motif), re.DOTALL)


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reglages = json.loads((RACINE / ".claude" / "settings.json").read_text(encoding="utf-8"))
        cls.deny = reglages["permissions"]["deny"]
        cls.motifs = [motif_en_regex(d[len("Bash("):-1]) for d in cls.deny if d.startswith("Bash(")]

    def interdite(self, commande: str) -> bool:
        return any(m.fullmatch(commande) for m in self.motifs)

    def commandes_jira(self):
        """Toutes les commandes complètes qui contactent Jira : script × sous-commande × lanceur × chemin."""
        for scripts, sous in ((SCRIPTS_HISTORIQUE, SOUS_COMMANDES_HISTORIQUE), (SCRIPTS_EXPORT, SOUS_COMMANDES_EXPORT)):
            for script, (nom, options), lanceur, chemin in itertools.product(scripts, sous, LANCEURS, CHEMINS):
                lancement = f"{lanceur} {chemin.format(s=script)} {nom}"
                if options:
                    for option in options:
                        yield f"{lancement} {option} PROJ-1"
                        yield f"{lancement} {option}=PROJ-1 --dormants x.csv"
                else:
                    yield lancement
                    yield f"{lancement} --scope ABC --since 2026-01-01"


class CommandesJira(Base):
    def test_ancien_et_nouveau_nom_interdits_avec_chaque_lanceur_et_chaque_chemin(self):
        manquantes = [c for c in self.commandes_jira() if not self.interdite(c)]
        self.assertEqual(manquantes[:5], [], f"{len(manquantes)} commandes vers Jira ne sont pas interdites")

    def test_regles_d_avant_le_lot_3_toujours_presentes(self):
        self.assertEqual([r for r in REGLES_ANCIENNES if r not in self.deny], [])

    # Le cas « sous-commande locale non interdite » (history_jira.py check sans clé, sur des fichiers) est retiré avec la voie CSV (change
    # database-only, D12) : `check` lit la base, donc il est interdit avec ou sans clé (tests/settings_deny/test_settings_deny_database_only.py).

    def test_toute_sous_commande_des_scripts_est_classee(self):
        """Une sous-commande ajoutée à un script Jira doit être rangée ici (interdite ou locale), pas oubliée."""
        connues = ({n for n, _ in SOUS_COMMANDES_HISTORIQUE} | {n for n, _ in SOUS_COMMANDES_EXPORT}
                   | {"comparer", "compare"}      # compare : sous-commande retirée, cachée dans export_jira_api.py
                   | {"check-teams", "migrate-teams"}      # sans Jira, interdites à la session par test_settings_deny_equipes.py
                   | {"review-teams"}      # sans Jira, interdite à la session par test_settings_deny_revue_equipes.py (names-and-team-review)
                   | {"extract-teams"})      # sans Jira, interdite à la session par test_settings_deny_team_names.py (team-names-readable, D5)
        for script in SCRIPTS_HISTORIQUE + SCRIPTS_EXPORT:
            chemin = TOOLS / script
            if not chemin.exists():
                continue                                    # script pas encore (ou plus) sous ce nom
            noms = set(re.findall(r'add_parser\(\s*"([^"]+)"', chemin.read_text(encoding="utf-8")))
            self.assertTrue(noms, script)
            self.assertEqual(sorted(noms - connues), [], f"{script} : sous-commande non classée dans les règles deny")


class FichiersSensibles(Base):
    def test_lecture_par_l_outil_read(self):
        for chemin in ("exports/**", "historique/**", "tableaux/**", "equipes-assets.yaml", "noms-sensibles.txt"):
            self.assertIn(f"Read(./Flux-Lab/{chemin})", self.deny)
        for autorise in ("rapports", "flux.yaml"):
            self.assertFalse([d for d in self.deny if autorise in d], autorise)

    def test_lecture_par_les_commandes_du_terminal(self):
        racine = "/Users/quelquun/PMZilla-Lab/workspace"
        for lecteur, chemin in itertools.product(LECTEURS, DOSSIERS_SENSIBLES):
            for forme in (chemin, f"./{chemin}", f"{racine}/{chemin}", f"~/PMZilla-Lab/workspace/{chemin}"):
                self.assertTrue(self.interdite(f"{lecteur} {forme}"), f"{lecteur} {forme}")

    def test_lectures_autorisees_non_interdites(self):
        for commande in ("cat Flux-Lab/rapports/flux-serie-2026-10-06.md", "head Flux-Lab/flux.yaml",
                         "grep -n Débit Flux-Lab/rapports/flux-serie-2026-10-06.md", "sed -n 1,5p README.md",
                         "cp tools/flux_jira.py /tmp/x.py", "ls Flux-Lab"):
            self.assertFalse(self.interdite(commande), commande)

    def test_trousseau(self):
        self.assertIn("Bash(security find-generic-password*)", self.deny)
        self.assertIn("Bash(security *pmzilla-jira*)", self.deny)
        self.assertTrue(self.interdite("security find-generic-password -s pmzilla-jira -w"))


class DossiersDeLaVeille(Base):
    """Dossiers de contenu de la veille (plan 7.7) : l'ancien dossier entier et les nouveaux sont interdits à l'outil Read."""

    ANCIENS = ("Read(./Veille-Lab/**)", "Read(./Veille-Ecartes/**)")
    NOUVEAUX = ("Read(./Watch-Lab/watch/**)", f"Read(./Watch-Lab/{OWN_COLLECTION}/**)", "Read(./Watch-Excluded/**)")

    def test_anciens_et_nouveaux_motifs_presents(self):
        self.assertEqual([r for r in self.ANCIENS + self.NOUVEAUX if r not in self.deny], [])


class JiraEnBase(Base):
    """Lot 6 : Jira en base. Claude Code ne lit que les vues (tools/flow_views.py) et les rapports ; il ne lance ni l'import, ni la
    comparaison, ni un calcul qui lit la base (--source db), ni psql, ni docker exec, ni ne lit les sauvegardes."""

    SCRIPTS = ("flow_import.py", "flow_compare.py")
    SOURCES_BASE = ("--source db", "--source=db")
    CALCULS = ("flux_jira.py compute exports.csv", "dependencies_jira.py compute exports.csv --by team",
               "~/PMZilla-Lab/flux_jira.py compute")

    def test_import_et_comparaison_interdits_avec_chaque_lanceur_et_chemin(self):
        for script, lanceur, chemin in itertools.product(self.SCRIPTS, LANCEURS, CHEMINS):
            commande = f"{lanceur} {chemin.format(s=script)} --dry-run"
            self.assertTrue(self.interdite(commande), commande)

    def test_reconstruction_de_la_couche_brute_interdite_avec_chaque_lanceur_et_chemin(self):
        """Change jira-data-architecture (D5, tâche 10.1) : `flow_import.py --rebuild`, `--apply` et `--seed` sont des options de l'outil
        d'import, déjà couvert : aucune règle nouvelle n'est attendue, ces cas le prouvent pour chaque lanceur et chaque chemin."""
        options = ("--rebuild", "--rebuild --apply", "--rebuild --seed", "--rebuild --seed --apply", "--rebuild --language en",
                   "--language en --rebuild --apply")
        for lanceur, chemin, option in itertools.product(LANCEURS, CHEMINS, options):
            commande = f"{lanceur} {chemin.format(s='flow_import.py')} {option}"
            self.assertTrue(self.interdite(commande), commande)

    def test_test_de_restauration_interdit_avec_chaque_lanceur_et_chemin(self):
        for lanceur, chemin in itertools.product(("bash", "sh", "zsh", "uv run", ""), ("tools/{s}", "./tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}",
                                                                                     "$HOME/PMZilla-Lab/workspace/tools/{s}",
                                                                                     "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}")):
            commande = f"{lanceur} {chemin.format(s='db_restore_test.sh')} --backup x".strip()
            self.assertTrue(self.interdite(commande), commande)

    def test_lecture_et_test_du_script_de_restauration_non_interdits(self):
        for commande in ("cat tools/db_restore_test.sh", "bash tests/db_scripts/test_db_scripts.sh", "bash tests/run_all.sh db_scripts"):
            self.assertFalse(self.interdite(commande), commande)

    def test_calcul_depuis_la_base_interdit(self):
        for calcul, option, lanceur in itertools.product(self.CALCULS, self.SOURCES_BASE, ("uv run", "python3", "uv run --with numpy")):
            for commande in (f"{lanceur} tools/{calcul} {option}", f"{lanceur} tools/{calcul} --name x {option} --weeks 26"):
                self.assertTrue(self.interdite(commande), commande)
        # La forme « option avant la sous-commande » (`flux_jira.py --source db compute`) n'était refusée que par les règles à joker
        # initial sur --source, retirées par database-only (D12). Ce n'est pas un lancement : le parseur principal n'a aucune option avant
        # la sous-commande et sort en erreur d'usage avant toute lecture (prouvé par tests/flux_jira/test_lecteur_base.py,
        # test_option_avant_la_sous_commande_est_une_erreur_d_usage).

    # Le cas « calcul depuis des CSV non interdit » est retiré avec la voie CSV (change database-only, D12) : `statuses` et `compute` lisent la
    # base, la session ne les lance plus (tests/settings_deny/test_settings_deny_database_only.py, étape utilisateur 13.2).

    def test_psql_docker_exec_et_sauvegardes(self):
        for commande in ("psql -h 127.0.0.1 pmzilla", "cd x && psql pmzilla", "docker exec pmzilla-lab-db-1 psql -U postgres",
                         "docker compose exec db psql", "docker-compose exec db bash", "docker container exec x ls",
                         "docker run --rm postgres psql -h host", "pg_dump pmzilla", "pg_restore x.dump",
                         "cat ~/.pmzilla-lab/sauvegardes/db-2026-10-08/flow.dump", "strings /Users/x/.pmzilla-lab/sauvegardes/a",
                         "grep -a PROJ ~/.pmzilla-lab/sauvegardes/db-2026-10-08/x", "zcat ~/.pmzilla-lab/sauvegardes/a.gz"):
            self.assertTrue(self.interdite(commande), commande)
        self.assertIn("Read(~/.pmzilla-lab/sauvegardes/**)", self.deny)

    def test_ce_que_la_session_garde(self):
        for commande in ("docker compose ps", "docker compose logs db", "docker compose config",
                         "uv run tools/flow_views.py list", "uv run tools/flow_views.py show v_team_status",
                         "uv run tools/db.py --help", "cat tools/db_backup.sh", "bash tests/db_scripts/test_db_scripts.sh",
                         "git log --oneline -3"):
            self.assertFalse(self.interdite(commande), commande)

    def test_scripts_de_la_base_interdits_a_la_session(self):
        """Audit du 2026-10-08 : db.py (migrate, status, role-password), db_backup.sh, db_up.sh, docker cp ; dbtest.sh (R-21) démarre
        un conteneur et lance les suites avec base : il ne se lance que depuis le Terminal de l'utilisateur."""
        for sous, lanceur in itertools.product(("migrate", "migrate --dry-run", "status", "role-password pmzilla_flow_views"),
                                               ("uv run", "python", "python3", "uv run --with psycopg")):
            for chemin in ("tools/db.py", "~/PMZilla-Lab/workspace/tools/db.py", "/Users/quelquun/PMZilla-Lab/workspace/tools/db.py"):
                commande = f"{lanceur} {chemin} {sous}"
                self.assertTrue(self.interdite(commande), commande)
        for script, lanceur, chemin in itertools.product(("db_backup.sh", "db_up.sh", "dbtest.sh"), ("bash", "sh", "zsh", "uv run", ""),
                                                         ("tools/{s}", "./tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}",
                                                          "$HOME/PMZilla-Lab/workspace/tools/{s}",
                                                          "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}")):
            commande = f"{lanceur} {chemin.format(s=script)} down".strip()
            self.assertTrue(self.interdite(commande), commande)
        for commande in ("docker cp pmzilla-lab-db-1:/var/lib/x ./x", "docker container cp a:/b c", "docker compose cp db:/x ./x"):
            self.assertTrue(self.interdite(commande), commande)

    def test_script_d_installation_interdit_a_la_session(self):
        """Change install-script, design D6 : l'amorce (.sh) et l'orchestrateur (.py) sondent de vrais services (même à blanc) et
        changent la machine ; la sous-commande pack (install-migrate) copie les dossiers de contenu. Aucun lancement depuis la session."""
        chemins = ("tools/{s}", "./tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}", "$HOME/PMZilla-Lab/workspace/tools/{s}",
                   "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}")
        options = ("", " --dry-run", " --help", " --mode fresh", " --mode fresh --dry-run", " --list", " --step database",
                   " --start-at launchd")
        for lanceur, chemin, option in itertools.product(("bash", "sh", "zsh", "uv run", ""), chemins, options):
            commande = f"{lanceur} {chemin.format(s='install_lab.sh')}{option}".strip()
            self.assertTrue(self.interdite(commande), commande)
        for lanceur, chemin, option in itertools.product(
                ("uv run", "uv run --isolated", "python", "python3", "python3 -W ignore", ""), chemins, options + (" pack", " pack --dry-run")):
            commande = f"{lanceur} {chemin.format(s='install_lab.py')}{option}".strip()
            self.assertTrue(self.interdite(commande), commande)
        for commande in ('zsh -c "$(curl -fsSL https://example.org/raw/main/tools/install_lab.sh)" -- --mode fresh',
                         'zsh -c "$(curl -fsSL https://example.org/raw/main/tools/install_lab.sh)" -- --mode fresh --dry-run',
                         'bash -c "$(curl -fsSL https://example.org/raw/main/tools/install_lab.sh)"'):
            self.assertTrue(self.interdite(commande), commande)

    def test_ce_qui_reste_permis_autour_du_script_d_installation(self):
        for commande in ("cat tools/install_lab.sh", "cat tools/install_lab.py", "head -40 tools/install_lab_mcp.py",
                         "grep -n ETAPES tools/install_lab.py", "python3 -W ignore -m unittest discover -s tests/install_lab -q",
                         "python3 -W ignore -m unittest discover -s tests/install_lab -p test_noyau.py -q -f",
                         "bash tests/run_all.sh install_lab", "bash tests/run_all.sh --staged",
                         "python3 tests/install_lab/test_install_lab.py", "uv run python -m unittest tests.install_lab.test_install_lab",
                         "ls tests/install_lab", "git log --oneline -3 -- tools/install_lab.py"):
            self.assertFalse(self.interdite(commande), commande)

    def test_script_de_fin_de_branche_interdit_a_la_session(self):
        """tools/finish_branch.sh fusionne et pousse : il ne se lance que depuis le Terminal de l'utilisateur (design D9)."""
        for lanceur, chemin, option in itertools.product(
                ("bash", "sh", "zsh", "uv run", ""),
                ("tools/{s}", "./tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}", "$HOME/PMZilla-Lab/workspace/tools/{s}",
                 "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}"), ("", " --help")):
            commande = f"{lanceur} {chemin.format(s='finish_branch.sh')}{option}".strip()
            self.assertTrue(self.interdite(commande), commande)
        for commande in ("cat tools/finish_branch.sh", "bash tests/finish_branch/test_finish_branch.sh",
                         "bash tests/run_all.sh finish_branch"):
            self.assertFalse(self.interdite(commande), commande)

    def test_script_de_fin_de_worktree_interdit_a_la_session(self):
        """tools/finish_worktree.sh retire un worktree puis lance tools/finish_branch.sh (fusion, push) : il ne se lance que depuis le Terminal de l'utilisateur (design D12)."""
        for lanceur, chemin, option in itertools.product(
                ("bash", "sh", "zsh", "uv run", ""),
                ("tools/{s}", "./tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}", "$HOME/PMZilla-Lab/workspace/tools/{s}",
                 "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}"), (" feat/ma-branche", " --help")):
            commande = f"{lanceur} {chemin.format(s='finish_worktree.sh')}{option}".strip()
            self.assertTrue(self.interdite(commande), commande)
        for commande in ("cat tools/finish_worktree.sh", "bash tests/finish_worktree/test_finish_worktree.sh",
                         "bash tests/run_all.sh finish_worktree"):
            self.assertFalse(self.interdite(commande), commande)

    def test_import_de_la_bibliotheque_interdit_a_la_session(self):
        """knowledge_import.py import, verify, status (avec ou sans --dry-run) écrivent ou lisent la vraie base : jamais depuis Claude Code."""
        for sous, option, lanceur, chemin in itertools.product(
                ("import", "verify", "status"), ("", " --dry-run", " --deep", " --sqlite x.sqlite"),
                ("uv run", "uv run --with psycopg", "python", "python3", "python3 -I", ""),
                ("tools/{s}", "./tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}", "$HOME/PMZilla-Lab/workspace/tools/{s}",
                 "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}")):
            commande = f"{lanceur} {chemin.format(s='knowledge_import.py')} {sous}{option}".strip()
            self.assertTrue(self.interdite(commande), commande)
        for commande in ("uv run tools/knowledge_import.py --help", "cat tools/knowledge_import.py",
                         "bash tests/run_all.sh knowledge_import"):
            self.assertFalse(self.interdite(commande), commande)

    def test_indexeur_interdit_a_la_session(self):
        """pmzilla_lab_library.py index, rename-collection, probe, status écrivent ou lisent la vraie base (R-37) : jamais depuis Claude Code."""
        for sous, lanceur, chemin in itertools.product(
                ("index Bibliotheque-Lab Watch-Lab", "index x --recompute y", "index x --allow-empty",
                 "rename-collection a b", "rename-collection a b --dry-run", "probe", "status"),
                ("uv run", "uv run --with psycopg", "python", "python3", "python3 -I", ""),
                ("tools/{s}", "./tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}", "$HOME/PMZilla-Lab/workspace/tools/{s}",
                 "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}", "~/PMZilla-Lab/{s}", "$HOME/PMZilla-Lab/{s}",
                 "/Users/quelquun/PMZilla-Lab/{s}")):
            commande = f"{lanceur} {chemin.format(s='pmzilla_lab_library.py')} {sous}".strip()
            self.assertTrue(self.interdite(commande), commande)
        for commande in ("cat tools/pmzilla_lab_library.py", "uv run tools/pmzilla_lab_library.py",
                         "uv run tools/pmzilla_lab_library.py --help", "uv run tools/caption_diagnostic.py",
                         "bash tests/run_all.sh pmzilla_lab_library"):
            self.assertFalse(self.interdite(commande), commande)

    def test_tache_launchd_de_sauvegarde_interdite_a_la_session(self):
        """La tâche com.pmzilla.db-backup et le script qu'elle lance ne se pilotent que depuis le Terminal de l'utilisateur."""
        uid = "$(id -u)"
        for lanceur, action, cible in itertools.product(
                ("launchctl", "/bin/launchctl", "sudo launchctl"),
                ("bootstrap", "bootout", "kickstart", "kickstart -k", "print", "unload", "load", "enable", "disable"),
                (f"gui/{uid}/com.pmzilla.db-backup", "gui/501/com.pmzilla.db-backup",
                 f"gui/{uid} ~/Library/LaunchAgents/com.pmzilla.db-backup.plist")):
            commande = f"{lanceur} {action} {cible}"
            self.assertTrue(self.interdite(commande), commande)
        for commande in ("DB_BACKUP_GARDER=3 bash tools/db_backup.sh", "DB_BACKUP_DATE=2026-10-09 bash tools/db_backup.sh",
                         "DB_BACKUP_NOTIFIER=1 ./tools/db_backup.sh"):
            self.assertTrue(self.interdite(commande), commande)
        # anciens motifs gardés, et la lecture du modèle ou du journal de la veille reste permise
        for commande in ("bash tools/db_backup.sh", "bash ~/PMZilla-Lab/workspace/tools/db_backup.sh"):
            self.assertTrue(self.interdite(commande), commande)
        for commande in ("cat tools/com.pmzilla.db-backup.plist", "plutil -lint tools/com.pmzilla.db-backup.plist",
                         "bash tests/db_scripts/test_db_scripts.sh"):
            self.assertFalse(self.interdite(commande), commande)

    def test_dossiers_de_contenu_refuses_aux_commandes_de_lecture(self):
        """CLAUDE.md : les livres, la veille, les images ne se lisent que par search_library et read_passage."""
        dossiers = ("Bibliotheque-MD", "Bibliotheque-Lab", "Bibliotheque-Images", "Veille-Lab",
                    "Veille-Ecartes", "Watch-Lab/watch", f"Watch-Lab/{OWN_COLLECTION}", "Watch-Excluded")
        for dossier, outil in itertools.product(dossiers, ("cat", "head", "tail", "less", "more", "grep -r x", "awk '{print}'", "sed -n 1p", "cp")):
            for commande in (f"{outil} {dossier}/livre.md", f"{outil} ./{dossier}/a.md", f"{outil} /Users/quelquun/PMZilla-Lab/workspace/{dossier}/a.md"):
                self.assertTrue(self.interdite(commande), commande)
        self.assertFalse(self.interdite("cat tools/watch_lab.py"))


class Outil(unittest.TestCase):
    def test_le_joker_ne_vaut_que_pour_etoile(self):
        m = motif_en_regex("uv run *x.py test*")
        self.assertTrue(m.fullmatch("uv run x.py test"))
        self.assertTrue(m.fullmatch("uv run --with a ~/y/x.py test --z"))
        self.assertFalse(m.fullmatch("uv run x.py tes"))
        self.assertFalse(motif_en_regex("a.b").fullmatch("aXb"))


if __name__ == "__main__":
    unittest.main()
