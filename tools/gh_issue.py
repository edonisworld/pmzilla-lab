# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
PMZilla Lab : seul chemin d'écriture vers GitHub pour la file de travail (change github-roadmap, design D7 à D9).

    uv run tools/gh_issue.py new-feature --title T --theme X --milestone M [--blocked-by R-a,R-b] [--set key=value]... [--product mothra] [--value 1|2|3] [--body-file F]   (--value : étiquette value:N, 1 = haute, 3 = basse ; #512 ; --body-file : le texte de F suit le bloc roadmap dans le corps, mêmes contrôles de fichier que new-idea (code 2) et même garde-fou ; change gh-issue-autonomy, D6)
    uv run tools/gh_issue.py edit R-<n> [--title T] [--milestone M] [--set key=value]... [--product mothra|none] [--value 1|2|3] [--body-file F] [--no-milestone]   (--no-milestone : retire le jalon de la feature puis celui de chacune de ses sous-issues lues (ouvertes ou fermées), sans toucher au jalon lui-même ; exclusif avec --milestone (code 2) ; sortie « removed milestone from R-<n> » et « removed milestone from <k> sub-issue(s) » ; sans jalon : « nothing to do » ; une feature fermée est refusée (code 7, rien d'envoyé, sous-issues comprises) : une feature livrée garde le jalon de sa release, pour le corriger : reopen-feature R-<n> --reason R, puis edit R-<n> --milestone M (ou --no-milestone), puis la fermeture (décision R-20261103-36) ; change gh-issue-autonomy, D5 ; --body-file : remplace le texte qui suit le bloc roadmap, marqueur et bloc gardés, dans la même requête PATCH que les autres champs ; fichier refusé : code 2 ; trouvaille du garde-fou : code 3 ; corps sans marqueur ni bloc : code 7 ; texte identique : « nothing to do » ; change gh-issue-autonomy, D6 ;--value : remplace l'étiquette value:N, une seule par issue ;--product : pose le label product:<valeur> (liste fermée, aujourd'hui mothra) ou, avec none, le retire ; l'absence de label vaut PMZilla ; sync-tasks recopie le label de la feature sur ses tâches ;--title : texte sans clé, la commande ajoute « R-<n> · » ; non vide, refusé s'il commence déjà par une clé)
    uv run tools/gh_issue.py status <R-<n>|n|#n> <Todo|Ready|"In progress"|Done>   (une idée type:idea, désignée par son numéro, prend les mêmes statuts : ni jalon ni started_on ; une issue fermée ou sans type:idea est refusée, code 7 ; #423)
    uv run tools/gh_issue.py block R-<n> --by R-<m>      /      unblock R-<n> --by R-<m>
    uv run tools/gh_issue.py comment (R-<n> | --numero N) --body-file F
    uv run tools/gh_issue.py reopen-step (<clé> | --numero N) --reason R   (rouvre une tâche autonome R-<n>/u<k> fermée : commentaire du motif (marqueur roadmap-reopened, garde-fou) puis réouverture ; une tâche g/t de tasks.md est refusée (code 2) : décocher la case, sync-tasks la rouvrira ; jalon fermé : code 7 avant toute écriture ; déjà ouverte : « nothing to do » ; un close-step --reason posté après une réouverture poste son nouveau motif ; R-20261102-65)
    uv run tools/gh_issue.py sync-tasks R-<n> [--change NAME] [--groups 2-8,11] [--dry-run]   (--change : nom du change quand la feature n'a pas de champ change:, refusé s'il diffère du champ ; --groups : seulement ces groupes de tasks.md, liste et intervalles, un groupe inconnu est refusé (code 7) ; change et groups sont mémorisés dans le bloc de la feature au premier vrai lancement, ensuite sans --groups le bloc fait foi et un --groups contradictoire est refusé (code 7) ; --dry-run : liste ce qui serait créé, n'écrit rien ; pour une feature product:mothra, chaque titre de sous-issue prend « Mothra : » après la clé, une seule fois, et un titre sans ce préfixe est refusé (code 7) avant toute écriture)
    uv run tools/gh_issue.py set-owner R-<n>/<id> --owner user | --owner agent --model opus|sonnet|haiku   (une tâche porte exactement un model:<m> (agent) OU owner:user (utilisateur) ; user pose owner:user et retire tous les model: ; agent pose model:<m> et retire owner:user et tout autre model: ; --model obligatoire avec agent et refusé avec user (code 2) ; seuls les libellés de propriétaire (owner:user, model:*) sont remplacés, tous les autres libellés de l'issue sont gardés (la liste est réécrite : un libellé ajouté par ailleurs entre la lecture et l'écriture serait perdu ; fenêtre courte, choix documenté) ; casse ignorée, comme GitHub (Model:Opus est remplacé) ; tâche ouverte g, t ou u ; liste fermée rm.OWNERS ; refus code 2 d'une feature, d'une idée, d'une clé mal formée, d'une valeur hors liste ou d'une tâche fermée ; clé inconnue code 7 ; idempotente : même propriétaire, rien d'écrit et « nothing to do » ; au plus une création de libellé de dépôt manquant, puis la seule écriture de l'issue (ses libellés) ; une tâche d'agent exige --reason à close-step ; R-148/u11)
    uv run tools/gh_issue.py edit-task (R-<n>/<id> | --numero N) [--milestone M] [--title T] [--body-file F] [--no-milestone] [--nouvelle-cle]   (--no-milestone : retire le jalon de cette seule tâche ouverte (tâche fermée : code 2, comme --milestone), exclusif avec --milestone (code 2), sans jalon : « nothing to do » ; change gh-issue-autonomy, D5 ; --body-file : remplace le texte qui suit le marqueur de la tâche, marqueur gardé, admis sur une tâche fermée comme --title, même garde-fou et mêmes refus de fichier (code 2), texte identique : « nothing to do » ; change gh-issue-autonomy, D6 ; au moins une des quatre options, sinon code 2 ; une écriture par option, le corps et le titre ensemble quand --nouvelle-cle et --title vont ensemble ; tâche fermée admise pour --title et --nouvelle-cle, refusée pour --milestone ; ne remplace rien ; tombe avec R-20261102-66 (--nouvelle-cle) et R-20261102-65 (--numero, --title). --title : change le titre, texte sans clé, la commande ajoute « R-<n> · » avec le n du marqueur de l'issue, non vide, refusé s'il commence déjà par une clé. --nouvelle-cle : donne à la tâche la prochaine clé libre R-<n>/u<k> de sa feature (k = plus grand u<k> de toutes les issues de la feature, ouvertes ou fermées, doublons compris, plus un), réécrit le seul marqueur roadmap-id du corps (le texte réécrit passe par le garde-fou), garde le titre (sauf --title) ; sortie « rekeyed #N : ancienne -> nouvelle » ; clé déjà unique : « nothing to do », rien d'écrit ; avec une clé portée par plusieurs issues : code 2, utiliser --numero ; feature ou idée : code 2. --milestone : change le jalon d'une seule tâche ouverte g, t ou u, sans toucher à la feature ni aux autres tâches (edit R-<n> --milestone déplace la feature et toutes ses sous-issues) ; le déplacement tient jusqu'à ce que la feature bouge : edit R-<n> --milestone et status R-<n> "In progress" (quand la release courante diffère) remettent toutes les sous-issues dans le jalon de la feature, sync-tasks remet les tâches g/t (une tâche u reste où elle est) ; jalon existant et ouvert seulement (inconnu ou fermé : code 7, rien d'écrit, rien créé) ; refus code 2 d'une feature, d'une idée, d'une clé mal formée ou d'une tâche fermée ; clé inconnue code 7 ; idempotente : même jalon, rien d'écrit et « nothing to do » ; une issue par appel, une seule écriture qui ne porte que le jalon, lien de sous-issue à la feature intact ; roadmap.py check n'exige pas qu'une tâche partage le jalon de sa feature (il refuse seulement une issue ouverte dans un jalon fermé) ; R-148/u12)
    uv run tools/gh_issue.py new-task R-<n> --title T --body-file F [--milestone M] [--owner user|agent --model opus|sonnet|haiku]   (owner:user sauf --owner agent --model <m> (alors model:<m>, --model obligatoire avec agent, refusé avec user, code 2 ; jamais une tâche sans l'un ni l'autre) ; tâche autonome, sans tasks.md : issue type:task + owner:user ou model:<m> (+ product: de la feature) de clé R-<n>/u<k>, k = prochain numéro libre, sous-issue de la feature, dans son jalon sauf --milestone (existant) ; --title : texte sans clé, la commande ajoute « R-<n> · » ; relance avec le même titre : rien de recréé et le propriétaire reste inchangé, même avec un autre --owner (« already exists », pour le changer : set-owner) ; garde-fou sur titre et corps)
    uv run tools/gh_issue.py close-step (<clé> | --numero N) [--reason R]   (R-<n>/g<groupe>, R-<n>/t<tâche> ou R-<n>/u<k> ; --reason obligatoire hors étape utilisateur : une tâche d'agent, model:<m>, exige --reason)
    --numero N (R-20261102-65 ; close-step, reopen-step, edit-task, comment) : désigne l'issue par son numéro GitHub à la place de la clé, pour les clés portées par deux issues ou qui ne désignent pas l'issue voulue. La clé et --numero s'excluent (les deux ou aucun : code 2). Le numéro doit être celui d'une issue du dépôt de origin (inconnu : code 7) et du type attendu : type:task pour close-step, reopen-step et edit-task, type:feature pour comment (autre type : code 2). Ces refus ne remplacent rien : ils s'ajoutent à ceux de la clé ; ils tombent avec R-20261102-65 si --numero est retiré.
    uv run tools/gh_issue.py close-feature R-<n> [--edition-public] [--after-merge --comment-file F] | close-feature R-<n> --reason replaced|dropped --comment-file F | close-feature R-<n> --duplicate-of N   (--duplicate-of : ferme la feature en doublon de l'issue N : un commentaire (marqueur roadmap-duplicate et « Duplicate of #N »), puis la fermeture avec la raison « duplicate » et duplicate_issue_id (forme REST de PATCH issues/<n>, state_reason duplicate, vérifiée dans la documentation de GitHub) ; ni Status Done ni done_on ni edition:public ; incompatible avec --reason, --after-merge, --edition-public et --comment-file (code 2 ; le refus de --comment-file ne remplace rien et tombe si --duplicate-of accepte un commentaire) ; refus avant toute écriture : soi-même (2), N inconnue (7), sous-issue ouverte (7, « open sub-issues remain: »), fermée pour une autre raison (7) ; rejeu : « nothing to do », avec le commentaire manquant posté une fois ; sortie « closed R-<n> as duplicate of #N » ; change gh-issue-autonomy, D7 ; --reason : feature remplacée ou abandonnée, travail non fusionné ; ferme « not planned », commentaire de F obligatoire, ni Status Done ni done_on ni edition:public, les features dépendantes restent bloquées ; incompatible avec --after-merge et --edition-public ; #524 ;--edition-public : ajoute l'étiquette edition:public avant la fermeture, ou seule sur une feature déjà fermée ; edition-publish-tooling, D19 ; --after-merge : fermeture après coup d'un travail déjà fusionné, le texte de F, passé par le garde-fou, est posté à la place de la phrase « before the merge », Status Done et done_on gardés ; les deux options vont ensemble, sinon code 2 ; #430)
    uv run tools/gh_issue.py detach-sub-issue <parent> <enfant> [--comment-file F]   (inverse du rattachement : clé R-<n> ou numéro ; refuse, code 7 et rien d'envoyé, si l'enfant n'est pas une sous-issue du parent ; commentaire facultatif posté sur l'enfant après le détachement ; #406)
    uv run tools/gh_issue.py new-idea --title T (--body B | --body-file F) [--milestone M] [--value 1|2|3] [--product mothra]   (idée : étiquette type:idea, marqueur roadmap-idea, jamais de Project ; --body et --body-file s'excluent, l'un des deux est obligatoire, le texte du fichier passe par le même garde-fou ; fichier absent, vide ou non ordinaire : code 2, rien d'envoyé ; jalon existant et étiquette value:N facultatifs ; change single-tracking-github, D7 ; #184)
    uv run tools/gh_issue.py edit-idea <n|#n> [--title T] [--milestone M] [--value 1|2|3] [--product mothra|none] [--body-file F] [--no-milestone]   (--no-milestone : retire le jalon de l'idée, exclusif avec --milestone (code 2), sans jalon : « nothing to do » ; change gh-issue-autonomy, D5 ; change le titre (non vide, marqueur conservé), le jalon, remplace l'étiquette value:N ou remplace le corps d'une idée par le texte de F, marqueur conservé, mêmes contrôles que new-idea ; refuse une issue sans type:idea ; #184)
    uv run tools/gh_issue.py comment-idea <n|#n> --body-file F   (commente une idée ; `comment` reste réservé aux R-<n> ; refuse une issue sans type:idea ; #244, point F)
    uv run tools/gh_issue.py reopen-idea <n|#n> --reason R   /   reopen-feature R-<n> --reason R   (rouvre une idée ou une feature : motif non vide (code 2) et passé par le garde-fou (3), puis un commentaire (marqueur roadmap-reopened et « Reopened: R »), puis la réouverture ; pour une feature, done_on est retiré du bloc, un Status Done revient à Todo, et un rang libre est attribué si le bloc n'en a pas (en attendant la décision de l'auteur ; rang pris : code 7, le message nomme `edit R-<n> --set rank=<libre>`) ; l'état et le corps partent dans une seule requête PATCH, le commentaire n'est pas reposté à la relance, et une feature déjà ouverte dont la réouverture a été coupée est complétée (done_on retiré, Status Done remis à Todo) ; jalon fermé : code 7 « closed milestone: a reopened issue would sit in it; nothing was sent » ; type faux ou clé inconnue : 7 ; déjà ouverte : « nothing to do: <réf> is already open » ; sortie « reopened <réf> » ; change gh-issue-autonomy, D8)
    uv run tools/gh_issue.py horizon <R-<n>|n|#n> [V2|V3|V4|"Plus tard"]   (champ Horizon du Project, à créer par l'auteur avant le premier usage (sélection unique : V2, V3, V4, Plus tard) ; sans valeur : lit et imprime « horizon <réf> <valeur> » ou « horizon <réf> none », sans écriture ; avec une valeur : ajoute l'issue au Project si besoin (une idée), puis fixe la valeur, sortie « horizon <réf> <valeur> » ; même valeur : « nothing to do » ; seulement une feature ou une idée : une tâche est refusée (code 2, « a task follows its feature »), une issue fermée se lit mais ne s'écrit pas (code 7), valeur inconnue : code 2 ; champ ou option absent : code 6 « Project has no Horizon field or its options are incomplete; nothing was sent », sans gêner `status` ; passe par les requêtes GraphQL de l'outil ; change gh-issue-autonomy, D4)
    uv run tools/gh_issue.py edit-milestone M [--description-file F] [--due YYYY-MM-DD | --no-due]   (description et échéance d'un jalon ouvert, en une seule requête PATCH qui ne porte que ces deux champs, jamais le titre ni l'état ; au moins une option, date impossible, --due avec --no-due ou fichier refusé : code 2 ; jalon inconnu ou fermé : code 7 ; description passée par le garde-fou (3) ; mêmes valeurs (échéance comparée au jour) : « nothing to do » ; sortie « edited milestone M » ; change gh-issue-autonomy, D9)
    uv run tools/gh_issue.py close-idea <n|#n> [--comment-file F] | close-idea <n|#n> --duplicate-of N   (--duplicate-of : ferme l'idée en doublon de l'issue N, mêmes règles que close-feature --duplicate-of, incompatible avec --comment-file (code 2 ; ne remplace rien ; tombe si --duplicate-of accepte un commentaire) ; sortie « closed #n as duplicate of #N » ; change gh-issue-autonomy, D7 ; ferme une idée, avec un commentaire facultatif posté avant ; refuse une issue sans type:idea ; #244, point F)
    uv run tools/gh_issue.py promote-idea <n|#n> --theme X [--set key=value]...   (promeut une idée ouverte en feature, même numéro : une seule requête PATCH pose le titre « R-<m> · titre », le corps (marqueur roadmap-id, bloc roadmap, texte de l'idée sans son marqueur roadmap-idea) et les étiquettes (type:idea remplacée par type:feature, theme:X ajoutée, les autres gardées) ; jalon non touché ; puis Project : item ajouté si besoin, Status gardé, Todo sinon ; sortie « promoted #n to R-m » ; une issue déjà feature avec marqueur : « nothing to do: #n is already R-m » après avoir complété le Project ; refus avant toute écriture : pas une idée ou idée fermée (code 7), thème inconnu (2), bloc invalide, rang pris ou clé R-m déjà portée (7), trouvaille du garde-fou sur le titre, le corps ou les étiquettes (3) ; une idée réenregistrée ensuite se ferme en doublon, jamais promue deux fois ; change gh-issue-autonomy, D2)
    uv run tools/gh_issue.py attach-sub-issue <parent> <enfant>   (inverse de detach-sub-issue : clés R-<n> ou numéros ; vérifie d'abord par la lecture des sous-issues : les deux issues existent (7), parent et enfant différents (2), parent ouvert (7), parent non sous-issue de l'enfant (7), clé de l'enfant portée par aucune autre sous-issue du parent (7, « duplicate key ») ; un enfant déjà sous ce parent : « nothing to do » ; aucun texte envoyé, GitHub ne remplace pas un parent existant (refus code 1) ; le jalon n'est jamais déplacé, un écart est rapporté « milestone differs: #c <jalon|none>, #p <jalon|none> » et se corrige par edit R-<p> --milestone M (feature et toutes ses sous-issues), edit-task <clé> --milestone M (une tâche ouverte) ou edit-idea <n> --milestone M (une idée) ; sortie « attached #c to #p » ; change gh-issue-autonomy, D3)
    uv run tools/gh_issue.py sub-issues <R-<n>|n|#n>   (lecture seule, aucune requête d'écriture : une ligne par sous-issue triée par numéro, « #<n> <open|closed> <clé> » ou « #<n> <open|closed> no key », puis « <k> sub-issue(s), <o> open », puis « duplicate key <clé> : #<a>, #<b> » par clé de ces sous-issues portée par deux issues du dépôt ou plus (ouvertes ou fermées), ou « no duplicate key » ; ni titre ni corps imprimés ; code 0 même avec des doublons (la lecture rapporte, les écritures refuseront) ; parent inconnu : code 7 ; référence mal formée : code 2 ; change gh-issue-autonomy, D1)
    uv run tools/gh_issue.py view <n|#n|R-<n>|R-<n>/<id>> [--sortie F]   /   list [--milestone M] [--state open|closed|all] [--label L]... [--sortie F]   (lectures seules, niveau 2 du bac à sable 7.8, R-20261109-12 : le JSON {date, issues, milestones} des issues de la file, mises en forme comme le lit `roadmap.py --issues-json` ; écrit dans le fichier de --sortie (une ligne « wrote <n> issue(s) », jamais le chemin) ou, sans l'option, sur la sortie standard ; aucune requête d'écriture : une seule requête GraphQL de lecture, paginée ; view : inconnue code 7, référence mal formée code 2 ; --sortie illisible à écrire : code 2 ; remplace les lectures directes gh issue view et gh issue list de la session et l'appel de gh du lecteur ; retrait : permanent)
    uv run tools/gh_issue.py ensure-labels
    uv run tools/gh_issue.py ensure-milestone M [--closed]

Le dépôt est celui du remote `origin` (lu par `git remote get-url origin` dans la racine) et figure dans chaque chemin de
requête ; `--repo` ne sert qu'à le confirmer (un autre dépôt : code 2). `gh` tourne dans la racine du dépôt.
Garde-fou avant toute requête (D8) : noms sensibles du hook pre-commit (module partagé, liste locale), identifiants
personnels (scanner), motif de clé de ticket (deux majuscules au moins, un tiret, des chiffres ; les `R-<n>` passent).
Une trouvaille refuse la commande entière, rien n'est envoyé ; la sortie nomme le champ et la ligne, jamais la valeur.

Codes (D9) : 0 fait ou rien à faire ; 1 GitHub a refusé ; 2 usage ; 3 trouvaille du garde-fou ; 4 garde-fou impossible ;
5 GitHub injoignable ou non authentifié ; 6 scope `project` ou Project manquant ; 7 règle de la file ; 8 état inconnu
(une écriture sans réponse, ou GitHub perdu après des écritures confirmées). Sortie en anglais,
chaque ligne préfixée `gh_issue: `. Rien n'est mis en file pour plus tard. Jamais de suppression d'issue, d'étiquette ou de
jalon, jamais de transfert, de release ni de tag.

`gh` est remplaçable par la variable d'environnement PMZILLA_GH (chemin d'un exécutable), pour les tests. Chaque appel a
l'entrée standard fermée (sauf s'il envoie un corps), les invites désactivées (GH_PROMPT_DISABLED), une limite de temps
(PMZILLA_GH_TIMEOUT, 60 s) et une attente totale bornée sur les limites de débit (PMZILLA_GH_MAX_WAIT, 120 s).
Les fonctions de ce module sont la couche d'écriture de l'import initial, retiré depuis. Tests : tests/gh_issue.
"""
import argparse
import datetime
import json
import os
import re
import stat
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import roadmap_model as rm  # noqa: E402
import sensitive_names  # noqa: E402
import identifiants_personnels  # noqa: E402

RACINE_CODE = Path(__file__).resolve().parents[1]     # le dossier du code : réglages et imports ; sous l'enveloppe figée, la copie figée
ENV_RACINE = "PMZILLA_GH_ISSUE_RACINE"                # posée par l'enveloppe figée seulement (niveau 2 du bac à sable, B4)
ENV_BASES_LECTURE = "PMZILLA_GH_ISSUE_BASES_LECTURE"  # idem : dossiers permis aux fichiers lus (--body-file, --comment-file, --description-file), séparés par « : »
ENV_BASES_SORTIE = "PMZILLA_GH_ISSUE_BASES_SORTIE"    # idem : dossiers permis au fichier écrit (--sortie)
# RACINE : le dépôt sur lequel porte la commande (tasks.md des changes, identifiants du garde-fou, remote origin). Sans la variable, c'est le dossier du code,
# comme avant ; l'enveloppe figée la pose (dossier courant de la session s'il est le workspace ou un worktree inscrit, sinon le workspace) parce que le code,
# lui, tourne depuis la copie figée.
# Remplace : l'unique racine déduite de l'emplacement du script (qui, depuis la copie figée, ne désigne plus le dépôt). Retrait : avec le bac à sable.
RACINE = Path(os.environ[ENV_RACINE]) if os.environ.get(ENV_RACINE, "").startswith("/") else RACINE_CODE
PREFIX = "gh_issue: "
ENV_GH = "PMZILLA_GH"
PROJECT_TITLE = "PMZilla Lab roadmap"
TICKET_KEY = re.compile(r"(?<![A-Za-z0-9_])[A-Z]{2,}-\d+")
FENCE = re.compile(r"^```roadmap[ \t]*\n.*?^```[ \t]*$", re.S | re.M)
LABEL_COLORS = {"value": "bfd4f2", "type": "1f6feb", "theme": "0e8a16", "model": "5319e7", "parallel": "fbca04", "owner": "d93f0b", "edition": "c5def5",
                "product": "b60205"}
LABEL_DESCRIPTIONS = {"product:mothra": "Feature, task or idea of the Mothra product (no product: label means PMZilla)"}
PRODUCT_NONE = "none"        # --product none : retire le label product: (edit, edit-idea)
sleep = time.sleep           # remplaçable par les tests
now = time.time              # idem (limite de débit : X-Ratelimit-Reset)
SECONDARY_WAIT = 60          # attente minimale sur une limite secondaire
PAUSE = 1.0                  # secondes entre deux créations (PMZILLA_GH_PAUSE)
TIMEOUT = 60.0               # secondes par appel gh (PMZILLA_GH_TIMEOUT)
MAX_WAIT = 120.0             # secondes d'attente cumulées sur les limites de débit, par commande (PMZILLA_GH_MAX_WAIT)
VISIBILITY_DELAYS = (1, 2, 4, 8)   # écarts entre les 5 lectures qui attendent qu'une feature soit listée
CLOSE_MARKER = "<!-- roadmap-close -->"
REASON_MARKER = "<!-- roadmap-closed-with-reason -->"
REOPEN_MARKER = "<!-- roadmap-reopened -->"                    # réouverture par reopen-step (R-20261102-65) ; tombe avec reopen-step
CLOSE_UNMERGED_MARKER ="<!-- roadmap-close-unmerged -->"      # fermeture non fusionnée (--reason), distincte de CLOSE_MARKER
DUPLICATE_MARKER = "<!-- roadmap-duplicate -->"               # fermeture en doublon (--duplicate-of ; change gh-issue-autonomy, D7)
SHOW_CMD = "uv run --with pyyaml python tools/roadmap.py show"


def env_float(name, default):
    try:
        v = float(os.environ.get(name, default))
    except ValueError:
        return default
    return v if v > 0 else default


class Stop(Exception):
    """Arrêt de la commande : code de sortie et lignes de message (sans préfixe)."""

    node_missing = False   # « Could not resolve to a node » : l'objet qu'on vient de créer n'est pas encore visible

    def __init__(self, code, *lines):
        super().__init__(" / ".join(lines))
        self.code = code
        self.lines = list(lines)


# --- Dépôt d'origine ----------------------------------------------------------------------------------------------

def git_origin_url():
    """URL de `origin` (lecture seule, dans la racine du dépôt) ; chaîne vide si elle manque."""
    try:
        p = subprocess.run(["git", "-C", str(RACINE), "remote", "get-url", "origin"], capture_output=True, text=True,
                           timeout=30, cwd=RACINE)
    except (OSError, subprocess.SubprocessError):
        return ""
    return p.stdout.strip() if p.returncode == 0 else ""


def git_head():
    """(branche courante ou None en tête détachée, commit court ou chaîne vide) ; lecture seule, dans la racine."""
    def run(*args):
        try:
            p = subprocess.run(["git", "-C", str(RACINE), *args], capture_output=True, text=True, timeout=30, cwd=RACINE,
                               stdin=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError):
            return ""
        return p.stdout.strip() if p.returncode == 0 else ""
    branch = run("rev-parse", "--abbrev-ref", "HEAD")
    return (None if branch in ("", "HEAD") else branch), run("rev-parse", "--short", "HEAD")


def racine_reglages():
    """Le dossier où se lisent les réglages de la file : celui du code quand l'enveloppe figée a posé une autre racine (le dépôt de la session ne
    peut pas changer la release), sinon RACINE, qui est alors le dossier du code. Remplace : la lecture des réglages sous RACINE. Retrait : avec le bac à sable."""
    return RACINE_CODE if os.environ.get(ENV_RACINE) else RACINE


def current_release():
    """Release en cours d'après tools/roadmap_settings.yaml (D12) ; chaîne vide si le fichier manque ou si rien n'est réglé.
    Stop(7) si le fichier est invalide (rien n'a été envoyé)."""
    try:
        text = (racine_reglages() / rm.SETTINGS_FILE).read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    except (OSError, UnicodeDecodeError):
        raise Stop(7, f"{rm.SETTINGS_FILE} is unreadable; nothing was sent") from None
    try:
        return rm.parse_settings(text)["current_release"]
    except ValueError:
        raise Stop(7, f"{rm.SETTINGS_FILE} is invalid; nothing was sent") from None


def strip_headers(out):
    """Retire les en-têtes HTTP que `gh api --include` place avant le corps."""
    if out.startswith("HTTP/"):
        mo = re.search(r"\r?\n\r?\n", out)
        return out[mo.end():] if mo else ""
    return out


# --- Garde-fou (D8) -----------------------------------------------------------------------------------------------

class Guard:
    def __init__(self, names, identifiers):
        self.motifs = sensitive_names.patterns(names)
        self.identifiers = [i.lower() for i in identifiers if i]

    @classmethod
    def load(cls, root=None):
        """Charge la liste et les identifiants ; échoue fermé (code 4)."""
        try:
            names = sensitive_names.load_judged_names()   # liste puis extrait des équipes : source unique (A-75, R-20261112-05)
        except sensitive_names.SensitiveNamesUnavailable as e:
            cause = {"missing": "absent", "empty": "empty", "unreadable": "unreadable"}[e.reason]
            raise Stop(4, f"guard could not run: sensitive-names list {cause}") from None
        try:
            ids = identifiants_personnels.identifiants(Path(root) if root else RACINE)
        except BaseException as e:   # SystemExit(2) du scanner compris
            if isinstance(e, KeyboardInterrupt):
                raise
            raise Stop(4, "guard could not run: identifier scanner failed") from None
        return cls(names, ids)

    def scan(self, fields):
        """fields : champ -> texte. Lève Stop(3) à la première trouvaille ; ne cite jamais la valeur ni la ligne."""
        for champ, texte in fields.items():
            for n, ligne in enumerate(str(texte).split("\n"), 1):
                if sensitive_names.line_matches(self.motifs, ligne):
                    kind = "sensitive name"
                elif any(i in ligne.lower() for i in self.identifiers):
                    kind = "personal identifier"
                elif TICKET_KEY.search(ligne):
                    kind = "ticket key"
                else:
                    continue
                raise Stop(3, f"refused: {kind} in {champ}, line {n}; nothing was sent")


# --- Client gh ----------------------------------------------------------------------------------------------------

class Client:
    def __init__(self, guard):
        self.guard = guard
        self._repo = None
        self.writes = 0          # écritures confirmées par GitHub
        self.writing = False     # une écriture est partie et n'a pas encore de réponse
        self.waited = 0          # secondes d'attente cumulées sur les limites de débit
        self.target = None       # feature sur laquelle porte la commande (pour la commande de vérification)
        self._labels = None
        self._milestones = None

    # exécution
    def wait_seconds(self, low, tentative):
        """Attente avant de rejouer après une limite de débit (Retry-After, X-Ratelimit-Reset ; 60 s au moins si secondaire)."""
        m = re.search(r"retry-after:\s*(\d+)", low)
        r = re.search(r"x-ratelimit-reset:\s*(\d+)", low)
        if m:
            wait = int(m.group(1))
        elif r:
            wait = max(0, int(r.group(1)) - int(now())) + 1
        else:
            wait = min(60, 2 ** tentative)
        if "secondary rate limit" in low:
            wait = max(SECONDARY_WAIT, wait)
        return min(wait, 3600)

    def refusal(self, p):
        """Ligne de refus de GitHub : le message passe par le garde ; une trouvaille ou l'absence de garde le retient."""
        brut = (p.stderr or "") + "\n" + strip_headers(p.stdout or "")
        mo = re.search(r"HTTP (\d{3})", brut)
        withheld = f"GitHub refused: HTTP {mo.group(1) if mo else '?'} (message withheld)"
        premiere = next((l.strip() for l in (p.stderr or "").splitlines() if l.strip()), "")
        if not premiere:
            try:
                d = json.loads(strip_headers(p.stdout or ""))
                premiere = str(((d.get("errors") or [{}])[0] or {}).get("message") or d.get("message") or "")
            except (ValueError, AttributeError, IndexError, TypeError):
                premiere = ""
        if self.guard is None:
            return withheld
        try:
            self.guard.scan({"GitHub message": brut})
        except Stop:
            return withheld
        return f"GitHub refused: {(premiere or 'no message')[:200]}"

    def check(self, retry):
        """Fin de message : comment vérifier ce que la commande a fait. `retry` : phrase de rejeu pour une feature."""
        if self.target:
            return f"check with {SHOW_CMD} {self.target}" + retry
        return "run the same command again, it is idempotent"

    def lost(self, note=""):
        """Arrêt quand GitHub ne répond plus : 5 avant toute écriture, 8 dès qu'une écriture est partie (D5)."""
        if self.writing:
            return Stop(8, f"state unknown: {self.writes} write(s) confirmed, the last write got no answer; "
                           + self.check(" before running the command again"))
        if self.writes:
            return Stop(8, f"state unknown: GitHub unreachable after {self.writes} confirmed write(s); "
                           + self.check(", then run the same command again"))
        return Stop(5, f"GitHub unreachable{note}; nothing was sent")

    def confirmed_line(self):
        """Deuxième ligne d'un refus (1) ou d'une erreur de scope (6) venus après des écritures confirmées."""
        return (f"{self.writes} write(s) were confirmed before this failure; "
                + self.check(""))

    def run(self, args, stdin=None):
        exe = os.environ.get(ENV_GH) or "gh"
        if args[:1] == ["api"]:
            args = ["api", "--include", *args[1:]]
        timeout = env_float("PMZILLA_GH_TIMEOUT", TIMEOUT)
        max_wait = env_float("PMZILLA_GH_MAX_WAIT", MAX_WAIT)
        opts = {"input": stdin} if stdin is not None else {"stdin": subprocess.DEVNULL}
        env = {**os.environ, "GH_PROMPT_DISABLED": "1"}
        for tentative in range(5):
            try:
                p = subprocess.run([exe, *args], capture_output=True, text=True, timeout=timeout, cwd=RACINE, env=env,
                                   **opts)
            except FileNotFoundError:
                raise Stop(5, "gh not found; install the GitHub CLI") from None
            except subprocess.TimeoutExpired:
                raise self.lost(f" (no answer within {timeout:g} s)") from None
            if p.returncode == 0:
                return strip_headers(p.stdout) if args[:1] == ["api"] else p.stdout
            stderr = (p.stderr or "").lower()
            raw = stderr + "\n" + (p.stdout or "").lower()                      # les en-têtes ne servent qu'à l'attente
            low = stderr + "\n" + strip_headers(p.stdout or "").lower()         # classement : erreur standard et corps (D4)
            if "gh auth login" in low or "not logged in" in low or "http 401" in low or "bad credentials" in low:
                raise Stop(5, "not authenticated; run gh auth login in the Terminal")
            if "required scopes" in low or "insufficient_scopes" in low:
                raise Stop(6, "missing token scope project; run gh auth refresh -s project in the Terminal")
            if "could not resolve to a node" in low:
                err = Stop(1, self.refusal(p))
                err.node_missing = True
                raise err
            if any(m in stderr for m in ("could not resolve host", "no such host", "dial tcp", "timed out", "timeout",
                                         "connection refused", "network is unreachable", "error connecting")):
                raise self.lost()
            if "rate limit" in low or "http 429" in low:
                wait = self.wait_seconds(raw, tentative)
                if self.waited + wait > max_wait:
                    if self.writes:
                        raise Stop(8, f"state unknown: GitHub unreachable after {self.writes} confirmed write(s); "
                                      + self.check(", then run the same command again"))
                    raise Stop(5, f"GitHub rate limit: {wait} s to wait is over the allowed wait; nothing was sent")
                self.waited += wait
                sleep(wait)
                continue
            raise Stop(1, self.refusal(p))
        raise Stop(1, "GitHub refused: rate limit still active after retries")

    def repo(self):
        if self._repo is None:
            self._repo = rm.repo_from_url(git_origin_url())
            if self._repo is None:
                raise Stop(2, "usage: the origin remote is missing or is not a GitHub repository")
        return self._repo

    def owner(self):
        return self.repo().split("/")[0]

    # lectures (aucun texte envoyé)
    def get(self, path):
        out = self.run(["api", f"repos/{self.repo()}/{path}"])
        return json.loads(out) if out.strip() else None

    def get_all(self, path):
        sep = "&" if "?" in path else "?"
        resultat, page = [], 1
        while True:
            lot = self.get(f"{path}{sep}per_page=100&page={page}") or []
            resultat.extend(lot)
            if len(lot) < 100:
                return resultat
            page += 1

    def graphql_read(self, query, variables):
        out = self.run(["api", "graphql", "--input", "-"], json.dumps({"query": query, "variables": variables}))
        return json.loads(out)

    # écritures : toujours après le garde-fou
    def send(self, method, path, payload, texts):
        if self.guard is None:
            raise Stop(4, "guard could not run: no guard loaded")
        self.guard.scan(texts)
        self.writing = True
        try:
            out = self.run(["api", "-X", method, f"repos/{self.repo()}/{path}", "--input", "-"], json.dumps(payload))
        finally:
            self.writing = False
        self.writes += 1
        self.pace()
        return json.loads(out) if out.strip() else None

    def graphql_write(self, query, variables, texts):
        if self.guard is None:
            raise Stop(4, "guard could not run: no guard loaded")
        self.guard.scan(texts)
        self.writing = True
        try:
            out = self.run(["api", "graphql", "--input", "-"], json.dumps({"query": query, "variables": variables}))
        finally:
            self.writing = False
        self.writes += 1
        self.pace()
        return json.loads(out)

    def pace(self):
        pause = float(os.environ.get("PMZILLA_GH_PAUSE", PAUSE))
        if pause > 0:
            sleep(pause)

    # étiquettes et jalons
    def labels(self):
        if self._labels is None:
            self._labels = {l["name"] for l in self.get_all("labels")}
        return self._labels

    def milestones(self):
        if self._milestones is None:
            self._milestones = {m["title"]: m for m in self.get_all("milestones?state=all")}
        return self._milestones


# --- Instantané des issues ----------------------------------------------------------------------------------------

class Snapshot:
    def __init__(self, issues):
        self.issues = [i for i in issues if "pull_request" not in i]
        self.by_key = {}
        for i in self.issues:
            k = rm.parse_marker(i.get("body") or "")
            if k:
                self.by_key.setdefault(k, []).append(i)
        self.by_number = {i["number"]: i for i in self.issues}

    def get(self, key):
        lst = self.by_key.get(key)
        return lst[0] if lst else None

    def max_id(self):
        best = 0
        for i in self.issues:
            p = rm.parse_title(i.get("title") or "")
            if p:
                best = max(best, p[0])
            k = rm.parse_marker(i.get("body") or "")
            if k:
                best = max(best, rm.parse_key(k)[1])
        return best

    def features(self):
        return [(k, v[0]) for k, v in self.by_key.items() if rm.parse_key(k)[0] == "feature"]

    def add(self, issue):
        self.issues.append(issue)
        self.by_number[issue["number"]] = issue
        k = rm.parse_marker(issue.get("body") or "")
        if k:
            self.by_key.setdefault(k, []).append(issue)


def load_snapshot(client):
    return Snapshot(client.get_all("issues?state=all"))


def label_names(issue):
    return [l["name"] if isinstance(l, dict) else l for l in issue.get("labels", [])]


# --- Opérations d'écriture ----------------------------------------------------------------------------------------

def ensure_label(client, name):
    if name.lower() in {n.lower() for n in client.labels()}:  # GitHub ne distingue pas la casse des libellés
        return False
    color = LABEL_COLORS.get(name.split(":")[0], "ededed")
    payload = {"name": name, "color": color}
    if name in LABEL_DESCRIPTIONS:
        payload["description"] = LABEL_DESCRIPTIONS[name]
    client.send("POST", "labels", payload, {"label": name, **({"description": payload["description"]} if "description" in payload else {})})
    client.labels().add(name)
    return True


def ensure_milestone(client, title, closed=False):
    """Crée le jalon s'il manque (fermé d'emblée si `closed`) ; ne change jamais un jalon existant."""
    if title in client.milestones():
        return False
    m = client.send("POST", "milestones", {"title": title, "state": "closed" if closed else "open"}, {"milestone": title})
    client.milestones()[title] = m
    return True


def milestone_number(client, title):
    m = client.milestones().get(title)
    if m is None:
        raise Stop(7, "unknown milestone")
    return m["number"]


def create_issue(client, snap, key, title, body, labels, milestone=None):
    """(issue, créée). Une issue dont le marqueur existe n'est pas recréée."""
    existing = snap.get(key)
    if existing:
        return existing, False
    for l in labels:
        ensure_label(client, l)
    payload = {"title": title, "body": body, "labels": list(labels)}
    if milestone:
        payload["milestone"] = milestone_number(client, milestone)
    texts = {"title": title, "body": body, "labels": "\n".join(labels)}
    if milestone:
        texts["milestone"] = milestone
    issue = client.send("POST", "issues", payload, texts)
    snap.add(issue)
    return issue, True


def patch_issue(client, number, payload, texts):
    return client.send("PATCH", f"issues/{number}", payload, texts)


def close_issue(client, issue, reason="completed"):
    if issue.get("state") == "closed":
        return False
    patch_issue(client, issue["number"], {"state": "closed", "state_reason": reason}, {})
    issue["state"] = "closed"
    return True


def reopen_issue(client, issue):
    if issue.get("state") != "closed":
        return False
    patch_issue(client, issue["number"], {"state": "open"}, {})
    issue["state"] = "open"
    return True


def issue_comments(client, number):
    return [c.get("body") or "" for c in client.get_all(f"issues/{number}/comments")]


def has_comment(client, number, marker):
    return any(b.lstrip().startswith(marker) for b in issue_comments(client, number))


def issue_milestone(issue):
    return (issue.get("milestone") or {}).get("title")


def set_milestone(client, issue, title):
    """Fixe le jalon de l'issue s'il diffère ; True si une requête est partie. Le texte du jalon passe par le garde."""
    if issue_milestone(issue) == title:
        return False
    number = milestone_number(client, title)
    patch_issue(client, issue["number"], {"milestone": number}, {"milestone": title})
    issue["milestone"] = {"title": title, "number": number}
    return True


def sub_issues(client, parent_number):
    return client.get_all(f"issues/{parent_number}/sub_issues")


def sub_issue_numbers(client, parent_number):
    return {i["number"] for i in client.get_all(f"issues/{parent_number}/sub_issues")}


def sub_issue_states(ctx, parent):
    """Lecture des sous-issues d'une issue (change gh-issue-autonomy, D1) : [{number, state, key}] triée par numéro.
    `key` vient du marqueur d'identité du corps lu dans l'instantané (None sans marqueur). Aucune écriture, aucun titre."""
    states = []
    for sub in sub_issues(ctx.client, parent["number"]):
        known = ctx.snap.by_number.get(sub["number"], sub)
        states.append({"number": sub["number"], "state": known.get("state") or sub.get("state"),
                       "key": rm.parse_marker(known.get("body") or "")})
    return sorted(states, key=lambda s: s["number"])


def duplicate_keys(snap, keys):
    """{clé: numéros triés} pour chaque clé de `keys` portée par deux issues ou plus du dépôt, ouvertes ou fermées (D1)."""
    return {k: sorted(i["number"] for i in snap.by_key[k]) for k in sorted(set(keys)) if len(snap.by_key.get(k, [])) > 1}


def add_sub_issue(client, parent, child):
    client.send("POST", f"issues/{parent['number']}/sub_issues", {"sub_issue_id": child["id"]}, {})


def blocker_numbers(client, number):
    return {i["number"] for i in client.get_all(f"issues/{number}/dependencies/blocked_by")}


def add_blocked_by(client, issue, blocker):
    client.send("POST", f"issues/{issue['number']}/dependencies/blocked_by", {"issue_id": blocker["id"]}, {})


def remove_blocked_by(client, issue, blocker):
    client.send("DELETE", f"issues/{issue['number']}/dependencies/blocked_by/{blocker['id']}", {}, {})


# --- Project (GraphQL) --------------------------------------------------------------------------------------------

Q_PROJECTS = """query($login: String!) { repositoryOwner(login: $login) { ... on ProjectV2Owner { projectsV2(first: 50) {
 nodes { id title fields(first: 30) { nodes { ... on ProjectV2SingleSelectField { id name options { id name } } } } } } } } }"""
Q_ITEMS = """query($project: ID!, $after: String) { node(id: $project) { ... on ProjectV2 { items(first: 100, after: $after) {
 pageInfo { hasNextPage endCursor } nodes { id content { ... on Issue { number } }
 fieldValueByName(name: "Status") { ... on ProjectV2ItemFieldSingleSelectValue { name } } } } } } }"""
Q_HORIZONS = """query($project: ID!, $after: String) { node(id: $project) { ... on ProjectV2 { items(first: 100, after: $after) {
 pageInfo { hasNextPage endCursor } nodes { id content { ... on Issue { number } }
 fieldValueByName(name: "Horizon") { ... on ProjectV2ItemFieldSingleSelectValue { name } } } } } } }"""      # lue par horizon seulement (D4)
HORIZONS = ("V2", "V3", "V4", "Plus tard")      # options du champ Horizon du Project, créé par l'auteur (change gh-issue-autonomy, D4)
HORIZON_MISSING = "Project has no Horizon field or its options are incomplete; nothing was sent"
M_ADD = "mutation($project: ID!, $content: ID!) { addProjectV2ItemById(input: {projectId: $project, contentId: $content}) { item { id } } }"
M_SET = """mutation($project: ID!, $item: ID!, $field: ID!, $option: String!) { updateProjectV2ItemFieldValue(input:
 {projectId: $project, itemId: $item, fieldId: $field, value: {singleSelectOptionId: $option}}) { projectV2Item { id } } }"""


class Project:
    def __init__(self, client, title=PROJECT_TITLE):
        self.client, self.title = client, title
        data = client.graphql_read(Q_PROJECTS, {"login": client.owner()})
        nodes = (((data.get("data") or {}).get("repositoryOwner") or {}).get("projectsV2") or {}).get("nodes") or []
        found = [n for n in nodes if n and n.get("title") == title]
        status = None
        if found:
            status = next((f for f in found[0]["fields"]["nodes"] if f and f.get("name") == "Status"), None)
        if not found or status is None or not set(rm.STATUSES) <= {o["name"] for o in status["options"]}:
            raise Stop(6, "Project not found or Status options incomplete")
        self.id, self.field_id = found[0]["id"], status["id"]
        self.options = {o["name"]: o["id"] for o in status["options"]}
        # champs à sélection unique par nom (D4) : le Status garde son contrôle ci-dessus, Horizon n'est lu que par la commande horizon
        self.single_selects = {f["name"]: (f["id"], {o["name"]: o["id"] for o in f["options"]})
                               for f in found[0]["fields"]["nodes"] if f and f.get("name") and "options" in f}
        self._items = None
        self._horizons = None

    def horizon_field(self):
        """(identifiant du champ Horizon, {option: identifiant}) ; Stop(6) si le champ ou une option manque (D4)."""
        field = self.single_selects.get("Horizon")
        if field is None or not set(HORIZONS) <= set(field[1]):
            raise Stop(6, HORIZON_MISSING)
        return field

    def horizon_of(self, issue):
        """Valeur du champ Horizon de l'issue au Project, ou None (aucun item, ou champ sans valeur)."""
        if self._horizons is None:      # sa propre lecture : les autres commandes ne demandent jamais Horizon
            self._horizons, after = {}, None
            while True:
                d = self.client.graphql_read(Q_HORIZONS, {"project": self.id, "after": after})
                page = d["data"]["node"]["items"]
                for n in page["nodes"]:
                    c = n.get("content") or {}
                    h = (n.get("fieldValueByName") or {}).get("name")
                    if "number" in c and h:
                        self._horizons[c["number"]] = h
                if not page["pageInfo"]["hasNextPage"]:
                    break
                after = page["pageInfo"]["endCursor"]
        return self._horizons.get(issue["number"])

    def ensure_horizon(self, issue, value):
        """Ajoute l'issue au Project si besoin et fixe son Horizon ; True si une requête est partie."""
        field_id, options = self.horizon_field()
        it = self.items().get(issue["number"])
        sent = False
        if it is None:
            d = self.add_item(issue)
            it = (d["data"]["addProjectV2ItemById"]["item"]["id"], None)
            sent = True
        if self.horizon_of(issue) != value:      # horizon_of lit les valeurs une fois
            self.client.graphql_write(M_SET, {"project": self.id, "item": it[0], "field": field_id, "option": options[value]}, {})
            sent = True
        self.items()[issue["number"]] = it
        self._horizons[issue["number"]] = value
        return sent

    def items(self):
        """numéro d'issue -> (identifiant d'item, Status ou None)."""
        if self._items is None:
            self._items, after = {}, None
            while True:
                d = self.client.graphql_read(Q_ITEMS, {"project": self.id, "after": after})
                page = d["data"]["node"]["items"]
                for n in page["nodes"]:
                    c = n.get("content") or {}
                    if "number" in c:
                        v = n.get("fieldValueByName") or {}
                        self._items[c["number"]] = (n["id"], v.get("name"))
                if not page["pageInfo"]["hasNextPage"]:
                    break
                after = page["pageInfo"]["endCursor"]
        return self._items

    def add_item(self, issue):
        """Ajoute l'issue au Project ; rejoue (écarts de VISIBILITY_DELAYS) tant que GitHub ne la résout pas encore."""
        for delay in (*VISIBILITY_DELAYS, None):
            try:
                return self.client.graphql_write(M_ADD, {"project": self.id, "content": issue["node_id"]}, {})
            except Stop as s:
                if not s.node_missing or delay is None:
                    raise
            sleep(delay)

    def ensure_status(self, issue, status):
        """Ajoute l'issue au Project si besoin et fixe le Status ; True si une requête est partie."""
        it = self.items().get(issue["number"])
        sent = False
        if it is None:
            d = self.add_item(issue)
            it = (d["data"]["addProjectV2ItemById"]["item"]["id"], None)
            sent = True
        if it[1] != status:
            self.client.graphql_write(M_SET, {"project": self.id, "item": it[0], "field": self.field_id,
                                              "option": self.options[status]}, {})
            sent = True
        self.items()[issue["number"]] = (it[0], status)
        return sent


# --- Bodies et plans ----------------------------------------------------------------------------------------------

def today():
    brut = os.environ.get("ROADMAP_TODAY")
    return brut if brut else datetime.date.today().isoformat()


def feature_body(key, block, text=None):
    corps = f"{rm.marker(key)}\n\n{rm.render_block(block)}"
    return corps + (f"\n\n{text}" if text else "")


def replace_block(body, block):
    return FENCE.sub(lambda _: rm.render_block(block), body, count=1)


def subissue_plan(n, change, groups):
    """Sous-issues d'après les groupes taggés (D3) : clé, titre, étiquettes, corps, complet, genre."""
    plan = []
    for g in groups:
        key = rm.group_key(n, g.number)
        body = f"{rm.marker(key)}\n\nChange: {change}\nGroup: {g.number}"
        if g.kind == "agent":
            labels = [rm.LABEL_TASK, rm.label_model(g.model)] + ([rm.LABEL_PARALLEL] if g.parallel else [])
            plan.append({"key": key, "title": rm.group_title(n, g.number, g.title), "labels": labels, "body": body,
                         "complete": rm.group_complete(g), "kind": "agent"})
            for t in rm.user_tasks(g):
                tk = rm.task_key(n, t.id)
                plan.append({"key": tk, "title": rm.user_task_title(n, t.id), "labels": [rm.LABEL_TASK, rm.LABEL_USER],
                             "body": f"{rm.marker(tk)}\n\nChange: {change}\nTask: {t.id}", "complete": rm.task_complete(t),
                             "kind": "user-task"})
        else:
            plan.append({"key": key, "title": rm.group_title(n, g.number, g.title), "labels": [rm.LABEL_TASK, rm.LABEL_USER],
                         "body": body, "complete": rm.group_complete(g), "kind": "user-group"})
    return plan


CHANGE_NOM = re.compile(r"[a-z0-9-]+")
CHANGE_ARCHIVE = re.compile(r"openspec/changes/archive/[A-Za-z0-9-]+")


def tasks_path(change):
    """tasks.md d'un change ouvert, ou archivé (chemin d'archive complet ou nom seul) ; None s'il est introuvable.
    Le nom vient du bloc d'une issue ou de --change : il doit être un nom de change (minuscules, chiffres, tirets) ou un chemin d'archive, sans
    remontée `..` ; sinon Stop(7), sans reprendre le texte (B4/R4 de la revue du bac à sable). Remplace : la jonction directe du texte au chemin. Retrait : permanent."""
    if not (CHANGE_NOM.fullmatch(str(change)) or CHANGE_ARCHIVE.fullmatch(str(change))):
        raise Stop(7, "invalid change name: expected lowercase letters, digits and hyphens, or an archive path")
    base = RACINE / "openspec" / "changes"
    for c in (base / change / "tasks.md", RACINE / change / "tasks.md"):
        if c.is_file():
            return c
    trouves = sorted((base / "archive").glob(f"*-{change}/tasks.md"))
    return trouves[-1] if trouves else None


# --- Contexte de commande -----------------------------------------------------------------------------------------

class Ctx:
    def __init__(self, client):
        self.client = client
        self.out = []
        self._snap = None
        self._project = None

    def say(self, line):
        self.out.append(line)

    @property
    def snap(self):
        if self._snap is None:
            self._snap = load_snapshot(self.client)
        return self._snap

    @property
    def project(self):
        if self._project is None:
            self._project = Project(self.client)
        return self._project

    def feature(self, key):
        parse = _parse_feature_key(key)
        issue = self.snap.get(parse)
        if issue is None and rm.parse_key(parse)[1] > self.snap.max_id():
            for delay in VISIBILITY_DELAYS:      # peut-être créée à l'instant : la liste de GitHub a du retard
                sleep(delay)
                self._snap = load_snapshot(self.client)
                issue = self._snap.get(parse)
                if issue is not None:
                    break
        if issue is None or rm.parse_key(parse)[0] != "feature":
            raise Stop(7, f"unknown identifier {key}")
        return issue

    def block_of(self, issue):
        try:
            return rm.parse_block(issue.get("body") or "")
        except rm.BlockError:
            raise Stop(7, f"invalid block: {rm.parse_marker(issue.get('body') or '')}") from None


def _parse_feature_key(key):
    if not re.fullmatch(r"R-\d+", key or ""):
        raise Stop(2, "usage: expected an identifier like R-12")
    return key


# --- Sous-commandes -----------------------------------------------------------------------------------------------

def parse_sets(sets):
    out = {}
    for s in sets or []:
        k, sep, v = s.partition("=")
        if not sep or k not in rm.KEYS:
            raise Stop(2, "usage: --set expects key=value with a known block key")
        out[k] = int(v) if k == "rank" and v.isdigit() else v
    return out


def invalid_block(block, is_open, key=None):
    pb = rm.validate_block(block, is_open=is_open, marker_key=key)
    if pb:
        raise Stop(7, "invalid block: " + ", ".join(sorted({p.split(" :")[0] for p in pb})))


def open_ranks(snap, ignore=None):
    ranks = {}
    for k, i in snap.features():
        if i.get("state") != "open" or k == ignore:
            continue
        try:
            r = rm.parse_block(i.get("body") or "").get("rank")
        except rm.BlockError:
            continue
        if isinstance(r, int):
            ranks[r] = k
    return ranks


def await_listed(client, key, issue):
    """Relit la liste jusqu'à ce que la feature créée y figure (5 lectures espacées) ; sinon code 8 (D6)."""
    for delay in (*VISIBILITY_DELAYS, None):
        issues = client.get_all("issues?state=all")
        if any(rm.parse_marker(i.get("body") or "") == key for i in issues if "pull_request" not in i):
            return
        if delay is not None:
            sleep(delay)
    raise Stop(8, f"state unknown: created {key} (#{issue['number']}) but GitHub does not list it yet; "
                  f"wait before the next new-feature, then check with {SHOW_CMD} {key}")


def with_product(labels, product):
    """Étiquettes avec le label `product:` demandé : `none` le retire, une valeur le pose à la place de tout autre label `product:`."""
    rest = [l for l in labels if not l.startswith(rm.LABEL_PRODUCT_PREFIX)]
    return rest if product == PRODUCT_NONE else rest + [rm.label_product(product)]


def cmd_new_feature(ctx, a):
    snap, client = ctx.snap, ctx.client
    if a.theme not in rm.THEMES:
        raise Stop(2, "usage: --theme must be one of " + ", ".join(rm.THEMES))
    texte = read_body_file(a.body_file).strip() if getattr(a, "body_file", None) is not None else None      # D6
    n = snap.max_id() + 1
    key = rm.feature_key(n)
    client.target = key
    block = {"id": key, "theme": a.theme, "estimate": "tbd", "method": "direct-prompt", "model": "tbd", "conditions": ""}
    block.update(parse_sets(a.set))
    block["id"] = key
    block["theme"] = a.theme
    ranks = open_ranks(snap)
    if "rank" not in block:
        block["rank"] = (max(ranks) if ranks else 0) + 10
    elif block["rank"] in ranks:
        raise Stop(7, f"rank already used by {ranks[block['rank']]}")
    invalid_block(block, True, key)
    blockers = [b for b in (a.blocked_by or "").split(",") if b]
    blocker_issues = [ctx.feature(b) for b in blockers]
    title = rm.feature_title(n, a.title)
    body = feature_body(key, block, texte)
    labels = [rm.LABEL_FEATURE, rm.label_theme(a.theme)]
    if a.product:
        labels.append(rm.label_product(a.product))
    if getattr(a, "value", None):
        labels.append(idea_value_label(a.value))
    client.guard.scan({"title": title, "body": body, "labels": "\n".join(labels), "milestone": a.milestone})
    project = ctx.project
    milestone_number(client, a.milestone)
    issue, _ = create_issue(client, snap, key, title, body, labels, a.milestone)
    await_listed(client, key, issue)
    for b in blocker_issues:
        add_blocked_by(client, issue, b)
    project.ensure_status(issue, "Todo")
    ctx.say(f"created {key} (#{issue['number']})")


def exclusive_no_milestone(a):
    """--no-milestone et --milestone s'excluent (code 2) ; change gh-issue-autonomy, D5."""
    if getattr(a, "no_milestone", False) and a.milestone is not None:
        raise Stop(2, "usage: --no-milestone is incompatible with --milestone")


def clear_milestone(client, issue):
    """Retire le jalon de l'issue s'il y en a un (le jalon lui-même reste) ; True si une requête est partie."""
    if issue_milestone(issue) is None:
        return False
    patch_issue(client, issue["number"], {"milestone": None}, {})
    issue["milestone"] = None
    return True


def cmd_edit(ctx, a):
    exclusive_no_milestone(a)
    texte = read_body_file(a.body_file).strip() if getattr(a, "body_file", None) is not None else None      # D6
    issue = ctx.feature(a.key)
    key, client = a.key, ctx.client
    if a.no_milestone and issue.get("state") != "open":      # décision R-20261103-36 (Q7) : une feature livrée garde le jalon de sa release
        raise Stop(7, f"{key} is closed: a delivered feature keeps its release's milestone; to correct it: reopen-feature {key} "
                      f"--reason R, edit {key} --milestone M, then close it again; nothing was sent")
    n = rm.parse_key(key)[1]
    block = ctx.block_of(issue)
    sets = parse_sets(a.set)
    sets.pop("id", None)
    block.update(sets)
    invalid_block(block, issue.get("state") == "open", key)
    if "rank" in sets and sets["rank"] in open_ranks(ctx.snap, ignore=key):
        raise Stop(7, f"rank already used by {open_ranks(ctx.snap, ignore=key)[sets['rank']]}")
    payload, texts = {}, {}
    if a.title is not None:
        # --title prend le texte sans clé ; la commande ajoute « R-n · » (comme new-feature) ; un titre déjà préfixé est refusé
        if not a.title.strip():
            raise Stop(2, "usage: --title must not be empty")
        if re.match(rf"\s*R-\d+\s*{rm.SEP}", a.title):
            raise Stop(2, f"usage: --title takes the text without the R-<n> {rm.SEP} prefix, the command adds it")
        new_title = rm.feature_title(n, a.title.strip())
        if new_title != issue.get("title"):
            payload["title"] = texts["title"] = new_title
    body = replace_block(issue.get("body") or "", block)
    if texte is not None:      # le texte après le bloc est remplacé, le marqueur et le bloc restent (D6)
        fence = FENCE.search(body)
        if rm.parse_marker(body) is None or fence is None:
            raise Stop(7, f"{key} has no roadmap key in its body")
        body = body[:fence.end()] + "\n\n" + texte
    if body != issue.get("body"):
        payload["body"] = body
        texts["body"] = body
    labels = label_names(issue)
    relabel = False
    if "theme" in sets:
        labels = [l for l in labels if not l.startswith("theme:")] + [rm.label_theme(block["theme"])]
        relabel = True
    if a.product is not None:
        labels = with_product(labels, a.product)
        relabel = relabel or sorted(labels) != sorted(label_names(issue))
    if getattr(a, "value", None):      # une seule étiquette value:N par issue (#512)
        labels = [l for l in labels if not re.fullmatch(r"value:\d+", l)] + [idea_value_label(a.value)]
        relabel = relabel or sorted(labels) != sorted(label_names(issue))
    if relabel:
        payload["labels"] = labels
        texts["labels"] = "\n".join(labels)
    if a.milestone is not None:
        texts["milestone"] = a.milestone
    client.guard.scan(texts)
    if a.milestone is not None:
        if issue.get("state") == "open" and client.milestones().get(a.milestone, {}).get("state") == "closed":
            raise Stop(7, "closed milestone: an open feature cannot move to it")
        payload["milestone"] = milestone_number(client, a.milestone)
    late = []
    if a.no_milestone:      # D5 : le jalon de la feature, puis celui de chaque sous-issue lue (ouverte ou fermée) ; le jalon reste
        late = [s for s in sub_issues(client, issue["number"]) if issue_milestone(s) is not None]
        if issue_milestone(issue) is not None:
            payload["milestone"] = None
    if not payload and not late:
        ctx.say("nothing to do")
        return
    if "labels" in payload:
        for l in payload["labels"]:
            ensure_label(client, l)
    if payload:
        patch_issue(client, issue["number"], payload, texts)
        if a.no_milestone and "milestone" in payload:
            issue["milestone"] = None
            ctx.say(f"removed milestone from {key}")
        if set(payload) != {"milestone"} or not a.no_milestone:
            ctx.say(f"edited {key} (#{issue['number']})")
    if a.no_milestone and late:
        for sub in late:
            clear_milestone(client, sub)
        ctx.say(f"removed milestone from {len(late)} sub-issue(s)")
    if a.milestone is not None:
        moved = sum(set_milestone(client, sub, a.milestone) for sub in sub_issues(client, issue["number"]))
        if moved:
            ctx.say(f"moved {moved} sub-issue(s) to {a.milestone}")


def move_to_release(ctx, issue, key):
    """D12 : la feature et ses sous-issues (ouvertes ou fermées) passent dans la release en cours, avant le Status.
    Refus (7) avant toute écriture si la release n'est pas un jalon ouvert."""
    client = ctx.client
    release = current_release()
    if not release:
        ctx.say("no current release; milestone unchanged")
        return
    if client.milestones().get(release, {}).get("state") != "open":
        raise Stop(7, f"current release {release} is not an open milestone; nothing was sent")
    client.guard.scan({"milestone": release})
    subs = sub_issues(client, issue["number"])
    late = [s for s in subs if issue_milestone(s) != release]
    feature_moved = issue_milestone(issue) != release
    if not feature_moved and not late:
        return
    if feature_moved:
        set_milestone(client, issue, release)
    for sub in late:
        set_milestone(client, sub, release)
    if feature_moved:
        ctx.say(f"moved {key} and {len(late)} sub-issue(s) to {release}")
    else:
        ctx.say(f"moved {len(late)} sub-issue(s) of {key} to {release}")


def is_issue_number(ref):
    return re.fullmatch(r"#?\d+", ref or "") is not None


def cmd_status_idea(ctx, a):
    """Statut d'une idée au tableau (#423) : mêmes statuts qu'une feature, sans jalon ni started_on ; une issue fermée ne bouge pas."""
    if a.status not in rm.STATUSES:
        raise Stop(2, "usage: status must be one of " + ", ".join(rm.STATUSES))
    issue = idea_of(ctx, a.key)
    if issue.get("state") == "closed":
        raise Stop(7, f"#{issue['number']} is closed; its status is not changed")
    sent = ctx.project.ensure_status(issue, a.status)
    ctx.say(f"status #{issue['number']} {a.status}" if sent else "nothing to do")


def cmd_status(ctx, a):
    if is_issue_number(a.key):
        return cmd_status_idea(ctx, a)
    issue = ctx.feature(a.key)
    if a.status not in rm.STATUSES:
        raise Stop(2, "usage: status must be one of " + ", ".join(rm.STATUSES))
    project = ctx.project
    sent = False
    if a.status == "In progress":
        move_to_release(ctx, issue, a.key)
        block = ctx.block_of(issue)
        if "started_on" not in block:
            block["started_on"] = today()
            body = replace_block(issue.get("body") or "", block)
            ctx.client.guard.scan({"body": body})
            patch_issue(ctx.client, issue["number"], {"body": body}, {"body": body})
            issue["body"] = body
            sent = True
    sent = project.ensure_status(issue, a.status) or sent
    ctx.say(f"status {a.key} {a.status}" if sent else "nothing to do")


def reaches(client, snap, start, target, path=None, seen=None):
    """Chemin de `start` à `target` en suivant les relations « blocked by », ou None."""
    path, seen = (path or [start]), (seen if seen is not None else set())
    if start == target:
        return path
    seen.add(start)
    issue = snap.get(start)
    if issue is None:
        return None
    for num in sorted(blocker_numbers(client, issue["number"])):
        nxt = snap.by_number.get(num)
        k = rm.parse_marker((nxt or {}).get("body") or "") if nxt else None
        if k and k not in seen:
            r = reaches(client, snap, k, target, path + [k], seen)
            if r:
                return r
    return None


def cmd_block(ctx, a, remove=False):
    issue, blocker = ctx.feature(a.key), ctx.feature(a.by)
    client = ctx.client
    if a.key == a.by:
        raise Stop(7, f"dependency cycle: {a.key} -> {a.key}")
    have = blocker_numbers(client, issue["number"])
    if remove:
        if blocker["number"] not in have:
            ctx.say("nothing to do")
            return
        remove_blocked_by(client, issue, blocker)
        ctx.say(f"unblocked {a.key} from {a.by}")
        return
    if blocker["number"] in have:
        ctx.say("nothing to do")
        return
    cycle = reaches(client, ctx.snap, a.by, a.key)
    if cycle:
        raise Stop(7, "dependency cycle: " + " -> ".join([a.key] + cycle))
    add_blocked_by(client, issue, blocker)
    ctx.say(f"blocked {a.key} by {a.by}")


def cmd_comment(ctx, a):
    exactly_one_ref(a, "comment")
    if a.numero is not None:
        issue = issue_by_numero(ctx, a.numero, rm.LABEL_FEATURE, "feature issue", "comment")
        ref = f"#{a.numero}"
    else:
        issue, ref = ctx.feature(a.key), a.key
    try:
        texte = lire_texte(a.body_file)
    except (OSError, UnicodeDecodeError):
        raise Stop(2, "usage: --body-file must name a readable text file") from None
    ctx.client.send("POST", f"issues/{issue['number']}/comments", {"body": texte}, {"comment": texte})
    ctx.say(f"commented {ref}")


MOTHRA_PREFIX = "Mothra : "


def parse_groups(text):
    """`--groups 2-8,11` : ensemble de numéros de groupes (liste et intervalles) ; code 2 si la forme est invalide."""
    wanted = set()
    for part in str(text).split(","):
        mo = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+)\s*)?", part)
        if not mo:
            raise Stop(2, f"usage: --groups expects a list and ranges of group numbers such as 2-8,11 (received {text!r})")
        lo, hi = int(mo.group(1)), int(mo.group(2) or mo.group(1))
        if lo > hi:
            raise Stop(2, f"usage: --groups range {part.strip()} is reversed")
        wanted.update(range(lo, hi + 1))
    return wanted


def format_groups(wanted):
    """Forme normalisée d'un ensemble de groupes : {2..11} donne `2-11`, {1,3} donne `1,3`."""
    nums, parts = sorted(wanted), []
    i = 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        parts.append(str(nums[i]) if i == j else f"{nums[i]}-{nums[j]}")
        i = j + 1
    return ",".join(parts)


def mothra_title(title):
    """`R-<n> · texte` devient `R-<n> · Mothra : texte` ; le préfixe n'est jamais doublé (un « Mothra : » déjà présent
    en tête du texte, ou juste après le numéro du groupe de tasks.md, est retiré avant d'être posé une fois en tête)."""
    parsed = rm.parse_title(title)
    if parsed is None:
        return title
    n, rest = parsed
    rest = re.sub(r"^((?:\d+(?:\.\d+)?\.?\s+)?)(?:Mothra : )+", r"\1", rest)
    return rm.feature_title(n, MOTHRA_PREFIX + rest)


def check_mothra_titles(plan):
    """Refus, avant toute écriture, d'une sous-tâche Mothra dont le titre ne commence pas par « Mothra : »."""
    bad = [p["key"] for p in plan if not ((rm.parse_title(p["title"]) or (None, ""))[1]).startswith(MOTHRA_PREFIX)]
    if bad:
        raise Stop(7, f"title of a product:mothra sub-issue must start with '{MOTHRA_PREFIX}': {', '.join(bad)}")


def sync_plan(ctx, feature_issue, key, required=True, change_opt=None, groups_opt=None):
    block = ctx.block_of(feature_issue)
    change = block.get("change")
    if change_opt:
        if change and change != change_opt:
            raise Stop(7, f"--change {change_opt} contradicts the change of {key} ({change})")
        change = change_opt
    if not change:
        if required:
            raise Stop(7, f"no change for {key}")
        return None
    path = tasks_path(change)
    if path is None:
        if required:
            raise Stop(7, f"tasks.md not found for change of {key}")
        return None
    if "archive" in path.parts:
        if required:
            raise Stop(7, f"change archived for {key}; its sub-issues were synchronised before the archiving")
        return None   # change archivé : ses sous-issues ont été synchronisées avant l'archivage (tasks.md sans tags possibles)
    try:
        groups = rm.parse_tasks(path.read_text(encoding="utf-8"), change)
    except rm.PlanError as e:
        raise Stop(7, f"tasks.md groups untagged: {', '.join(str(x) for x in e.untagged)} (change {e.change})") from None
    wanted = effective_groups(block, key, groups_opt)
    if wanted is not None:
        unknown = sorted(wanted - {g.number for g in groups})
        if unknown:
            raise Stop(7, f"unknown group(s) in tasks.md of {change}: {', '.join(str(x) for x in unknown)}")
        groups = [g for g in groups if g.number in wanted]
    return subissue_plan(rm.parse_key(key)[1], change, groups)


def effective_groups(block, key, groups_opt):
    """Groupes à synchroniser : ceux du bloc de la feature, ou ceux de --groups quand le bloc n'en a pas ;
    un --groups qui diffère du bloc est refusé (code 7). None : tous les groupes."""
    stored = block.get("groups")
    if stored is None:
        return groups_opt
    try:
        have = parse_groups(stored) if isinstance(stored, str) else None
    except Stop:
        have = None
    if have is None:
        raise Stop(7, f"invalid block: groups of {key}")
    if groups_opt is not None and groups_opt != have:
        raise Stop(7, f"--groups {format_groups(groups_opt)} contradicts the groups of {key} ({stored})")
    return have


def remembered_block(issue, block, key, change_opt, groups_opt):
    """Bloc de la feature avec `change` et `groups` mémorisés au premier vrai lancement ; None s'il n'y a rien à écrire."""
    new = dict(block)
    if change_opt and "change" not in new:
        new["change"] = change_opt
    if groups_opt is not None and "groups" not in new:
        new["groups"] = format_groups(groups_opt)
    if new == block:
        return None
    invalid_block(new, issue.get("state") == "open", key)
    return new


def do_sync(ctx, key, issue, required=True, change_opt=None, groups_opt=None, dry_run=False):
    plan = sync_plan(ctx, issue, key, required, change_opt, groups_opt)
    if plan is None:
        return 0
    client, snap = ctx.client, ctx.snap
    product = [l for l in label_names(issue) if l in {rm.label_product(x) for x in rm.PRODUCTS}]   # la feature donne son produit à ses tâches
    for p in plan:
        p["labels"] = p["labels"] + product
    if rm.label_product("mothra") in product:      # une sous-tâche Mothra porte « Mothra : » dans son titre
        for p in plan:
            p["title"] = mothra_title(p["title"])
        check_mothra_titles(plan)
    fields = {}
    for p in plan:
        fields[f"{p['key']} title"] = p["title"]
        fields[f"{p['key']} body"] = p["body"]
        fields[f"{p['key']} labels"] = "\n".join(p["labels"])
    block = ctx.block_of(issue)
    new_block = remembered_block(issue, block, key, change_opt, groups_opt)
    new_body = replace_block(issue.get("body") or "", new_block) if new_block else None
    if new_body:
        fields["feature body"] = new_body
    client.guard.scan(fields)
    if dry_run and new_block:
        ctx.say(f"would remember in the block of {key}: " + ", ".join(f"{k}={new_block[k]}" for k in ("change", "groups") if new_block.get(k) != block.get(k)))
    elif new_body:    # change et groups mémorisés avant les créations : un lancement suivant sans option retrouve le même périmètre
        patch_issue(client, issue["number"], {"body": new_body}, {"body": new_body})
        issue["body"] = new_body
        ctx.say(f"remembered in the block of {key}: " + ", ".join(f"{k}: {new_block[k]}" for k in ("change", "groups") if new_block.get(k) != block.get(k)))
    if dry_run:
        ctx.say(f"dry-run {key}: {len(plan)} sub-issue(s), nothing written; feature estimate {block.get('estimate', 'none')}, "
                f"blocked by {', '.join('#' + str(n) for n in sorted(blocker_numbers(client, issue['number']))) or 'none'}")
        for p in plan:
            existing = snap.get(p["key"])
            state = f"exists (#{existing['number']})" if existing else "would create"
            title = existing.get("title", p["title"]) if existing else p["title"]
            warn = ""
            if existing and rm.label_product("mothra") in product and not ((rm.parse_title(title) or (None, ""))[1]).startswith(MOTHRA_PREFIX):
                warn = f" | WARNING: title lacks '{MOTHRA_PREFIX}'"
            ctx.say(f"{state} {p['key']}: {title} | kind {p['kind']} | labels {', '.join(p['labels'])}"
                    f" | {'complete' if p['complete'] else 'open'}{warn}")
        return 0
    linked = sub_issue_numbers(client, issue["number"])
    milestone = issue_milestone(issue)
    changed = 1 if new_body else 0
    for p in plan:
        sub, created = create_issue(client, snap, p["key"], p["title"], p["body"], p["labels"], milestone)
        if created:
            changed += 1
            ctx.say(f"created {p['key']} (#{sub['number']})")
        if sub["number"] not in linked:
            add_sub_issue(client, issue, sub)
            linked.add(sub["number"])
            changed += 0 if created else 1
        if milestone and set_milestone(client, sub, milestone):
            changed += 1
            ctx.say(f"set milestone {milestone} on {p['key']}")
        if p["kind"] == "user-group":
            if p["complete"] and sub.get("state") == "open":
                ctx.say(f"ready to close after your confirmation: {p['key']}")
            continue
        if p["complete"] and close_issue(client, sub):
            changed += 1
            ctx.say(f"closed {p['key']}")
        elif (not p["complete"] and sub.get("state") == "closed" and not has_comment(client, sub["number"], REASON_MARKER)
              and reopen_issue(client, sub)):
            changed += 1
            ctx.say(f"reopened {p['key']}")
    return changed


def cmd_sync_tasks(ctx, a):
    groups = parse_groups(a.groups) if getattr(a, "groups", None) is not None else None
    change = getattr(a, "change", None)
    if change is not None and not re.fullmatch(r"[a-z0-9][a-z0-9-]*", change):
        raise Stop(2, f"usage: --change expects a change name like mothra-slices (received {change!r})")
    issue = ctx.feature(a.key)
    dry = bool(getattr(a, "dry_run", False))
    if do_sync(ctx, a.key, issue, change_opt=change, groups_opt=groups, dry_run=dry) == 0 and not dry:
        ctx.say("nothing to do")


def exactly_one_ref(a, command):
    """Une clé OU --numero, jamais les deux ni aucun (code 2). Remplace le positionnel obligatoire d'argparse ; tombe avec R-20261102-65
    si l'on revient à la clé seule."""
    if (a.key is None) == (a.numero is None):
        raise Stop(2, f"usage: {command} takes either a key or --numero N, exactly one of them")


def issue_by_numero(ctx, numero, label, noun, command):
    """L'issue du dépôt de origin portant ce numéro (R-20261102-65) : code 7 si elle manque, code 2 si elle n'est pas du type attendu
    (`label` : type:task pour une tâche, type:feature pour une feature), comme les refus d'une clé du mauvais type."""
    issue = ctx.snap.by_number.get(numero)
    if issue is None:
        raise Stop(7, f"unknown issue #{numero}")
    if label not in [l.lower() for l in label_names(issue)]:
        raise Stop(2, f"usage: #{numero} is not a {noun}; {command} works on a {noun}")
    return issue


def task_target(ctx, a, command):
    """(issue, désignation) d'une tâche désignée par --numero ; (None, clé) quand c'est la clé, que la commande résout elle-même."""
    exactly_one_ref(a, command)
    if a.numero is not None:
        return issue_by_numero(ctx, a.numero, rm.LABEL_TASK, "task issue", command), f"#{a.numero}"
    return None, a.key


def cmd_close_step(ctx, a):
    issue, ref = task_target(ctx, a, "close-step")
    if issue is None:
        try:
            kind = rm.parse_key(a.key)[0]
        except ValueError:
            raise Stop(2, "usage: close-step expects R-<n>/g<group>, R-<n>/t<task> or R-<n>/u<k>") from None
        if kind == "feature":
            raise Stop(2, "usage: close-step expects R-<n>/g<group>, R-<n>/t<task> or R-<n>/u<k>")
        issue = ctx.snap.get(a.key)
        if issue is None:
            raise Stop(7, f"unknown identifier {a.key}")
    reason = (a.reason or "").strip()
    is_user = rm.LABEL_USER in [l.lower() for l in label_names(issue)]
    if not is_user and not reason:
        raise Stop(7, f"{ref} is an agent sub-issue; close it with --reason after the user's confirmation")
    client = ctx.client
    posted = False
    if reason:
        text = f"{REASON_MARKER}\nClosed with a reason: {reason}"
        client.guard.scan({"comment": text})
        if not reason_after_reopen(client, issue["number"]):
            client.send("POST", f"issues/{issue['number']}/comments", {"body": text}, {"comment": text})
            posted = True
    closed = close_issue(client, issue)
    ctx.say(f"closed {ref}" if closed else ("nothing to do" if not posted else f"reason recorded on {ref}"))


def reason_after_reopen(client, number):
    """Un REASON_MARKER postérieur au dernier REOPEN_MARKER (ou sans réouverture) est déjà posté ; après une réouverture il faut un
    nouveau motif (R-20261102-65). Tombe avec reopen-step."""
    last_reason = last_reopen = -1
    for i, body in enumerate(issue_comments(client, number)):
        head = body.lstrip()
        if head.startswith(REASON_MARKER):
            last_reason = i
        elif head.startswith(REOPEN_MARKER):
            last_reopen = i
    return last_reason > last_reopen


def cmd_reopen_step(ctx, a):
    """Rouvre une tâche fermée (R-20261102-65) : commentaire du motif (marqueur, garde-fou) puis réouverture ; idempotente (déjà ouverte :
    « nothing to do »). Désignée par clé ou par --numero (utile quand une clé est portée par deux issues). Refus code 2 d'une feature,
    d'une idée ou d'un motif vide ; code 7 clé ou numéro inconnu. Seules les tâches autonomes u<k> sont admises : une tâche g/t de
    tasks.md est refusée (code 2), sync-tasks la rouvre en décochant la case. Un jalon fermé est refusé (code 7) avant toute écriture."""
    issue, ref = task_target(ctx, a, "reopen-step")
    if issue is None:
        try:
            kind = rm.parse_key(a.key)[0]
        except ValueError:
            raise Stop(2, "usage: reopen-step expects R-<n>/g<group>, R-<n>/t<task> or R-<n>/u<k>") from None
        if kind == "feature":
            raise Stop(2, "usage: reopen-step expects R-<n>/g<group>, R-<n>/t<task> or R-<n>/u<k>")
        issue = ctx.snap.get(a.key)
        if issue is None:
            raise Stop(7, f"unknown identifier {a.key}")
    own = rm.parse_marker(issue.get("body") or "")
    if own is None or rm.parse_key(own)[0] != "user-task":
        raise Stop(2, f"usage: {ref} is a tasks.md task (or has no task key): uncheck its box, sync-tasks will reopen it; "
                      "reopen-step works on a standalone R-<n>/u<k> task")
    reason = (a.reason or "").strip()
    if not reason:
        raise Stop(2, "usage: --reason must not be empty")
    text = f"{REOPEN_MARKER}\nReopened: {reason}"
    ctx.client.guard.scan({"comment": text})
    if issue.get("state") != "closed":
        ctx.say(f"nothing to do: {ref} (#{issue['number']}) is already open")
        return
    title = issue_milestone(issue)
    if title and ctx.client.milestones().get(title, {}).get("state") == "closed":
        raise Stop(7, "closed milestone: a reopened task would sit in it; nothing was sent")
    ctx.client.send("POST", f"issues/{issue['number']}/comments", {"body": text}, {"comment": text})
    reopen_issue(ctx.client, issue)
    ctx.say(f"reopened {ref} (#{issue['number']})")


def cmd_new_task(ctx, a):
    """Tâche autonome R-<n>/u<k> (sans tasks.md) : type:task + owner:user ou model:<m> (--owner agent --model) (+ produit de la feature), sous-issue de la
    feature, dans son jalon sauf --milestone ; idempotente sur le titre."""
    feature = ctx.feature(a.key)
    n = rm.parse_key(a.key)[1]
    if not a.title.strip():
        raise Stop(2, "usage: --title must not be empty")
    if re.match(rf"\s*R-\d+\s*{rm.SEP}", a.title):
        raise Stop(2, f"usage: --title takes the text without the R-<n> {rm.SEP} prefix, the command adds it")
    texte = read_body_file(a.body_file)
    title = rm.feature_title(n, a.title.strip())
    key = None
    taken = 0
    for k, issues in ctx.snap.by_key.items():
        kind, kn, k_id = rm.parse_key(k)
        if kind == "user-task" and kn == n:
            taken = max(taken, int(k_id))
            if issues[0].get("title") == title and key is None:
                key = k
    new_key = rm.user_task_key(n, taken + 1)
    body = f"{rm.marker(new_key)}\n\n{texte.strip()}"
    labels = [rm.LABEL_TASK] + owner_labels_for(a) + [l for l in label_names(feature) if l in {rm.label_product(x) for x in rm.PRODUCTS}]
    milestone = a.milestone or issue_milestone(feature)
    texts = {"title": title, "body": body, "labels": "\n".join(labels)}
    if milestone:
        texts["milestone"] = milestone
    ctx.client.guard.scan(texts)
    if milestone:
        milestone_number(ctx.client, milestone)
    if key is not None:
        issue = ctx.snap.get(key)
        if issue["number"] not in sub_issue_numbers(ctx.client, feature["number"]):
            add_sub_issue(ctx.client, feature, issue)
            ctx.say(f"linked {key} (#{issue['number']}) to {a.key}")
        else:
            ctx.say(f"already exists: {key} (#{issue['number']}); the owner is unchanged, use set-owner to change it")
        return
    issue, _ = create_issue(ctx.client, ctx.snap, new_key, title, body, labels, milestone)
    add_sub_issue(ctx.client, feature, issue)
    ctx.say(f"created {new_key} (#{issue['number']})")


def owner_labels_for(a):
    """Libellés de propriétaire demandés : `user` = owner:user, `agent` = model:<m> (--model obligatoire) ; jamais les deux ni aucun.
    Refus (code 2) de agent sans --model et de --model avec user."""
    model = getattr(a, "model", None)
    if a.owner == "agent":
        if model is None:
            raise Stop(2, f"usage: --owner agent requires --model {'|'.join(rm.MODELS)} (a task carries model:<m> or owner:user)")
        return [rm.label_model(model)]
    if model is not None:
        raise Stop(2, "usage: --model goes with --owner agent only")
    return [rm.LABEL_USER]


def cmd_set_owner(ctx, a):
    """Pose le propriétaire d'une tâche ouverte R-<n>/<id> : `user` pose owner:user, `agent --model m` pose model:<m> ; les libellés de
    propriétaire (owner:user, model:*) sont les seuls remplacés, tous les autres sont gardés. Une issue par appel, rien d'écrit hors
    libellés, idempotente. Refus (code 2) d'une feature, d'une idée, d'une clé mal formée ou d'une tâche fermée."""
    try:
        kind = rm.parse_key(a.key)[0]
    except ValueError:
        kind = None
    if is_issue_number(a.key) or kind is None or kind == "feature":
        raise Stop(2, "usage: set-owner expects a task key R-<n>/g<group>, R-<n>/t<task> or R-<n>/u<k> (not a feature or an idea)")
    issue = ctx.snap.get(a.key)
    if issue is None:
        raise Stop(7, f"unknown identifier {a.key}")
    if issue.get("state") == "closed":
        raise Stop(2, f"usage: {a.key} is closed; set-owner works on an open task")
    wanted = owner_labels_for(a)
    labels = label_names(issue)
    current = [l for l in labels if l.lower() == rm.LABEL_USER or l.lower().startswith("model:")]  # casse ignorée, comme GitHub
    if sorted(current) == sorted(wanted):
        ctx.say(f"nothing to do: {a.key} (#{issue['number']}) already owned by {a.owner}" + (f" ({wanted[0]})" if a.owner == "agent" else ""))
        return
    new_labels = [l for l in labels if l not in current] + wanted
    texts = {"labels": "\n".join(new_labels)}
    ctx.client.guard.scan(texts)
    for name in wanted:
        ensure_label(ctx.client, name)
    patch_issue(ctx.client, issue["number"], {"labels": new_labels}, texts)
    ctx.say(f"set owner of {a.key} (#{issue['number']}) to {a.owner}" + (f" ({wanted[0]})" if a.owner == "agent" else ""))


def cmd_edit_task(ctx, a):
    """Change le jalon d'une seule tâche ouverte R-<n>/<id> (existant, ouvert) : une issue par appel, une seule écriture qui ne porte que le
    jalon, la feature et les autres tâches intactes, lien de sous-issue inchangé, idempotente. `roadmap.py check` n'exige pas qu'une tâche
    partage le jalon de sa feature (seule une issue ouverte dans un jalon fermé est refusée). Refus (code 2) d'une feature, d'une idée,
    d'une clé mal formée ou d'une tâche fermée ; code 7 clé, jalon inconnu ou fermé.
    R-20261102-65 : la tâche se désigne aussi par --numero (clé et numéro s'excluent) et --title change le titre (texte sans clé, la
    commande ajoute « R-<n> · » avec le n du marqueur de l'issue) ; --title seul est admis sur une tâche fermée, --milestone non."""
    issue, ref = task_target(ctx, a, "edit-task")
    exclusive_no_milestone(a)
    if a.milestone is None and a.title is None and not a.nouvelle_cle and a.body_file is None and not a.no_milestone:
        raise Stop(2, "usage: edit-task needs --milestone and/or --title (or --body-file, --no-milestone, --nouvelle-cle)")
    texte = read_body_file(a.body_file).strip() if a.body_file is not None else None      # D6
    if issue is None:
        try:
            kind = rm.parse_key(a.key)[0]
        except ValueError:
            kind = None
        if is_issue_number(a.key) or kind is None or kind == "feature":
            raise Stop(2, "usage: edit-task expects a task key R-<n>/g<group>, R-<n>/t<task> or R-<n>/u<k> (not a feature or an idea)")
        issue = ctx.snap.get(a.key)
        if issue is None:
            raise Stop(7, f"unknown identifier {a.key}")
    closed = issue.get("state") == "closed"
    if closed and (a.milestone is not None or a.no_milestone):
        raise Stop(2, f"usage: {ref} is closed; edit-task works on an open task")
    new_title = None
    if a.title is not None:
        text = a.title.strip()
        if not text:
            raise Stop(2, "usage: --title must not be empty")
        if re.match(rf"\s*R-\d+\s*{rm.SEP}", text):
            raise Stop(2, f"usage: --title takes the text without the R-<n> {rm.SEP} prefix, the command adds it")
        own = rm.parse_marker(issue.get("body") or "")
        if own is None:
            raise Stop(7, f"{ref} has no roadmap key in its body; its title cannot be built")
        new_title = rm.feature_title(rm.parse_key(own)[1], text)
        ctx.client.guard.scan({"title": new_title})
    if texte is not None:      # D6 : le texte après le marqueur est remplacé, le marqueur reste ; contrôles avant toute écriture
        own = rm.parse_marker(issue.get("body") or "")
        if own is None:
            raise Stop(7, f"{ref} has no roadmap key in its body")
        ctx.client.guard.scan({"body": f"{rm.marker(own)}\n\n{texte}"})
    rekey = None
    if a.nouvelle_cle:
        own = rm.parse_marker(issue.get("body") or "")
        if own is None:
            raise Stop(7, f"{ref} has no roadmap key in its body; it cannot be rekeyed")
        n = rm.parse_key(own)[1]
        if a.numero is None and len(ctx.snap.by_key.get(own, [])) > 1:
            raise Stop(2, f"usage: {ref} is carried by several issues, a key cannot tell which one to rekey; use --numero")
        if len(ctx.snap.by_key.get(own, [])) <= 1:
            ctx.say(f"nothing to do: {ref} (#{issue['number']}) already has a unique key {own}")
            if a.milestone is None and new_title is None and texte is None and not a.no_milestone:
                return
        else:
            taken = 0
            for k in ctx.snap.by_key:
                kind_k, kn, k_id = rm.parse_key(k)
                if kind_k == "user-task" and kn == n:
                    taken = max(taken, int(k_id))
            new_key = rm.user_task_key(n, taken + 1)
            new_body = (issue.get("body") or "").replace(rm.marker(own), rm.marker(new_key), 1)
            if new_body == issue.get("body"):
                raise Stop(7, f"{ref}: the marker is not at the start of the body; it cannot be rekeyed")
            ctx.client.guard.scan({"body": new_body, **({"title": new_title} if new_title is not None else {})})
            rekey = (own, new_key, new_body)
    if a.milestone is not None:
        ctx.client.guard.scan({"milestone": a.milestone})
        milestone_number(ctx.client, a.milestone)
        if issue_milestone(issue) != a.milestone and ctx.client.milestones()[a.milestone].get("state") == "closed":
            raise Stop(7, "closed milestone: an open task cannot move to it")
    if a.milestone is not None:
        if issue_milestone(issue) == a.milestone:
            ctx.say(f"nothing to do: {ref} (#{issue['number']}) is already in {a.milestone}")
        else:
            set_milestone(ctx.client, issue, a.milestone)
            ctx.say(f"moved {ref} (#{issue['number']}) to {a.milestone}")
    if a.no_milestone:      # D5 : le jalon de cette seule tâche ouverte ; le jalon lui-même reste
        if clear_milestone(ctx.client, issue):
            ctx.say(f"removed milestone from {ref} (#{issue['number']})")
        else:
            ctx.say(f"nothing to do: {ref} (#{issue['number']}) has no milestone")
    if rekey is not None:
        old_key, new_key, new_body = rekey
        payload = {"body": new_body}
        if new_title is not None and new_title != issue.get("title"):
            payload["title"] = new_title
        patch_issue(ctx.client, issue["number"], payload, dict(payload))
        issue["body"] = new_body
        if "title" in payload:
            issue["title"] = new_title
        ctx.snap.by_key.get(old_key, []).remove(issue)
        ctx.snap.by_key.setdefault(new_key, []).append(issue)
        ctx.say(f"rekeyed #{issue['number']} : {old_key} -> {new_key}")
    elif new_title is not None:
        if issue.get("title") == new_title:
            ctx.say(f"nothing to do: {ref} (#{issue['number']}) already has this title")
        else:
            patch_issue(ctx.client, issue["number"], {"title": new_title}, {"title": new_title})
            issue["title"] = new_title
            ctx.say(f"retitled {ref} (#{issue['number']})")
    if texte is not None:
        new_body = f"{rm.marker(rm.parse_marker(issue.get('body') or ''))}\n\n{texte}"
        if issue.get("body") == new_body:
            ctx.say(f"nothing to do: {ref} (#{issue['number']}) already has this text")
        else:
            patch_issue(ctx.client, issue["number"], {"body": new_body}, {"body": new_body})
            issue["body"] = new_body
            ctx.say(f"rewrote the text of {ref} (#{issue['number']})")


def close_feature_unmerged(ctx, a):
    """Fermeture d'une feature remplacée ou abandonnée, travail non fusionné (#524) : « not planned », commentaire
    obligatoire, ni Status Done, ni done_on, ni edition:public ; les features qui en dépendent restent bloquées."""
    if getattr(a, "after_merge", False) or getattr(a, "edition_public", False):
        raise Stop(2, "usage: --reason is incompatible with --after-merge and --edition-public")
    if a.comment_file is None:
        raise Stop(2, "usage: --reason needs --comment-file")
    texte = read_text_file(a.comment_file, "--comment-file").strip()
    if not texte:
        raise Stop(2, "usage: --comment-file names an empty file")
    issue = ctx.feature(a.key)
    client = ctx.client
    comment = f"{CLOSE_UNMERGED_MARKER}\n{texte}"
    client.guard.scan({"comment": comment})
    if issue.get("state") == "closed" and issue.get("state_reason") != "not_planned":
        raise Stop(7, f"{a.key} is already closed as completed; --reason applies to an open feature or one closed as not planned")
    subs = client.get_all(f"issues/{issue['number']}/sub_issues")
    open_subs = [rm.parse_marker(s.get("body") or "") or f"#{s['number']}" for s in subs if s.get("state") == "open"]
    if open_subs:
        raise Stop(7, "open sub-issues remain: " + ", ".join(sorted(open_subs)))
    if issue.get("state") == "closed" and has_comment(client, issue["number"], CLOSE_UNMERGED_MARKER):
        ctx.say("nothing to do")
        return
    if not has_comment(client, issue["number"], CLOSE_UNMERGED_MARKER):
        client.send("POST", f"issues/{issue['number']}/comments", {"body": comment}, {"comment": comment})
    close_issue(client, issue, "not_planned")
    ctx.say(f"closed {a.key} as not planned ({a.reason})")
    waiting = []
    for dep in client.get_all(f"issues/{issue['number']}/dependencies/blocking"):
        full = ctx.snap.by_number.get(dep["number"], dep)
        k = rm.parse_marker(full.get("body") or "")
        if full.get("state") == "open" and k:
            waiting.append(k)
    ctx.say("still blocked: " + (", ".join(sorted(waiting, key=lambda x: rm.parse_key(x)[1])) if waiting else "none")
            + " (the blocking relation stays; unblock it by hand once the replacement is decided)")


def close_as_duplicate(ctx, issue, ref, target, feature=False):
    """Ferme `issue` en doublon de `target` (change gh-issue-autonomy, D7). Contrôles avant toute écriture ; puis un commentaire
    (marqueur et lien), puis la fermeture avec la raison « duplicate » et l'identifiant de l'issue visée. Un rejeu ne fait rien,
    et poste une fois le commentaire manquant d'une exécution interrompue."""
    client = ctx.client
    if target == issue["number"]:
        raise Stop(2, "usage: an issue cannot be a duplicate of itself")
    other = ctx.snap.by_number.get(target)
    if other is None:
        raise Stop(7, f"unknown issue #{target}")
    comment = f"{DUPLICATE_MARKER}\nDuplicate of #{target}"
    client.guard.scan({"comment": comment})
    closed = issue.get("state") == "closed"
    if closed and issue.get("state_reason") != "duplicate":
        raise Stop(7, f"{ref} is already closed; nothing was sent")
    if feature and not closed:
        open_subs = [s["key"] or f"#{s['number']}" for s in sub_issue_states(ctx, issue) if s["state"] == "open"]      # lecture de D1
        if open_subs:
            raise Stop(7, "open sub-issues remain: " + ", ".join(sorted(open_subs)))
    if not has_comment(client, issue["number"], DUPLICATE_MARKER):
        client.send("POST", f"issues/{issue['number']}/comments", {"body": comment}, {"comment": comment})
    if closed:
        ctx.say("nothing to do")
        return
    patch_issue(client, issue["number"], {"state": "closed", "state_reason": "duplicate", "duplicate_issue_id": other["id"]}, {})
    issue["state"], issue["state_reason"] = "closed", "duplicate"
    ctx.say(f"closed {ref} as duplicate of #{target}")


def reopen_with_reason(ctx, issue, ref, reason, feature=False):
    """Rouvre une idée ou une feature (change gh-issue-autonomy, D8) : motif non vide, garde, jalon ouvert, puis commentaire
    (marqueur et motif), puis réouverture. Pour une feature : done_on retiré du bloc (même requête que l'état), Status Done remis
    à Todo, rang libre. Le commentaire n'est pas reposté quand le dernier commentaire de l'issue est déjà le même (relance après
    coupure ; limite : le même motif sans autre commentaire entre-temps est tenu pour déjà posté)."""
    client = ctx.client
    reason = (reason or "").strip()
    if not reason:
        raise Stop(2, "usage: --reason must not be empty")
    text = f"{REOPEN_MARKER}\nReopened: {reason}"
    client.guard.scan({"comment": text})
    if issue.get("state") != "closed":      # déjà ouverte : une feature dont la réouverture a été coupée est complétée (comme promote-idea)
        if feature and complete_reopened_feature(ctx, issue):
            ctx.say(f"completed the reopening of {ref}")
        else:
            ctx.say(f"nothing to do: {ref} is already open")
        return
    title = issue_milestone(issue)
    if title and client.milestones().get(title, {}).get("state") == "closed":
        raise Stop(7, "closed milestone: a reopened issue would sit in it; nothing was sent")
    new_body = None
    if feature:
        block = ctx.block_of(issue)
        block.pop("done_on", None)
        if "rank" not in block:
            ranks = open_ranks(ctx.snap)
            block["rank"] = (max(ranks) if ranks else 0) + 10
        elif block["rank"] in open_ranks(ctx.snap, ignore=ref):
            raise Stop(7, f"rank already used by {open_ranks(ctx.snap, ignore=ref)[block['rank']]}; "
                          f"correct it with: edit {ref} --set rank=<free>")
        invalid_block(block, True, ref)
        new_body = replace_block(issue.get("body") or "", block)
        client.guard.scan({"body": new_body})
        project = ctx.project
    last = issue_comments(client, issue["number"])[-1:]      # une relance après coupure ne reposte pas le commentaire déjà parti
    if not (last and last[0].strip() == text):
        client.send("POST", f"issues/{issue['number']}/comments", {"body": text}, {"comment": text})
    if feature and new_body != issue.get("body"):      # l'état et le corps partent ensemble : pas de feature à moitié rouverte
        patch_issue(client, issue["number"], {"state": "open", "body": new_body}, {"body": new_body})
        issue["state"], issue["body"] = "open", new_body
    else:
        reopen_issue(client, issue)
    if feature:
        known = project.items().get(issue["number"])
        if known and known[1] == "Done":
            project.ensure_status(issue, "Todo")
    ctx.say(f"reopened {ref}")


def complete_reopened_feature(ctx, issue):
    """Feature déjà ouverte (réouverture coupée avant la fin) : retire un done_on resté dans le bloc et remet un Status Done à Todo.
    True si quelque chose a été complété."""
    client = ctx.client
    block = ctx.block_of(issue)
    done = False
    if "done_on" in block:
        block.pop("done_on")
        new_body = replace_block(issue.get("body") or "", block)
        client.guard.scan({"body": new_body})
        patch_issue(client, issue["number"], {"body": new_body}, {"body": new_body})
        issue["body"] = new_body
        done = True
    known = ctx.project.items().get(issue["number"])
    if known and known[1] == "Done":
        ctx.project.ensure_status(issue, "Todo")
        done = True
    return done


def cmd_reopen_idea(ctx, a):
    issue = idea_of(ctx, a.number)
    reopen_with_reason(ctx, issue, f"#{issue['number']}", a.reason)


def cmd_reopen_feature(ctx, a):
    reopen_with_reason(ctx, ctx.feature(a.key), a.key, a.reason, feature=True)


def close_feature_duplicate(ctx, a):
    if a.reason or a.after_merge or a.edition_public or a.comment_file is not None:
        raise Stop(2, "usage: --duplicate-of is incompatible with --reason, --after-merge, --edition-public and --comment-file")
    close_as_duplicate(ctx, ctx.feature(a.key), a.key, a.duplicate_of, feature=True)


def cmd_close_feature(ctx, a):
    if getattr(a, "duplicate_of", None) is not None:
        return close_feature_duplicate(ctx, a)
    if getattr(a, "reason", None):
        return close_feature_unmerged(ctx, a)
    after_merge = getattr(a, "after_merge", False)
    comment_file = getattr(a, "comment_file", None)
    if after_merge != (comment_file is not None):
        raise Stop(2, "usage: --after-merge and --comment-file go together")
    texte = None
    if after_merge:
        texte = read_text_file(comment_file, "--comment-file").strip()
        if not texte:
            raise Stop(2, "usage: --comment-file names an empty file")
    issue = ctx.feature(a.key)
    client = ctx.client
    block = ctx.block_of(issue)
    project = ctx.project
    had_done = bool(block.get("done_on"))
    new_body = None
    branch, short = git_head() if not after_merge else (None, None)
    if after_merge:      # travail déjà fusionné (#430) : le commentaire fourni remplace la phrase « before the merge »
        comment = f"{CLOSE_MARKER}\n{texte}"
    elif branch:
        comment = f"{CLOSE_MARKER}\nClosed on branch {branch}, before the merge; the user merges with bash tools/finish_train.sh."
    else:
        comment = f"{CLOSE_MARKER}\nClosed outside a branch (detached HEAD at {short or 'unknown'}), before the merge."
    fields = {"comment": comment}
    labels_now = label_names(issue)
    new_labels = None
    if getattr(a, "edition_public", False) and rm.LABEL_EDITION_PUBLIC not in labels_now:
        new_labels = labels_now + [rm.LABEL_EDITION_PUBLIC]
        fields["labels"] = "\n".join(new_labels)
    if "done_on" not in block:
        block["done_on"] = today()
        new_body = replace_block(issue.get("body") or "", block)
        fields["body"] = new_body
    client.guard.scan(fields)      # le refus du garde précède toute écriture, synchronisation comprise
    do_sync(ctx, a.key, issue, required=False)
    subs = client.get_all(f"issues/{issue['number']}/sub_issues")
    open_subs = [rm.parse_marker(s.get("body") or "") or f"#{s['number']}" for s in subs if s.get("state") == "open"]
    if open_subs:
        raise Stop(7, "open sub-issues remain: " + ", ".join(sorted(open_subs)))
    if new_labels is not None:      # l'étiquette précède l'état, le commentaire et le statut (D19)
        patch_issue(client, issue["number"], {"labels": new_labels}, {"labels": "\n".join(new_labels)})
        issue["labels"] = [{"name": n} for n in new_labels]
        ctx.say(f"label {rm.LABEL_EDITION_PUBLIC} added to {a.key}")
    if issue.get("state") == "closed" and had_done and project.items().get(issue["number"], (0, None))[1] == "Done":
        if has_comment(client, issue["number"], CLOSE_MARKER):
            if new_labels is None:
                ctx.say("nothing to do")
        else:      # rejeu d'une fermeture interrompue avant le commentaire : il est posté une fois, jamais en double
            client.send("POST", f"issues/{issue['number']}/comments", {"body": comment}, {"comment": comment})
            ctx.say(f"closing comment recorded on {a.key}")
        return
    if new_body is not None:
        client.send("PATCH", f"issues/{issue['number']}", {"body": new_body}, {"body": new_body})
        issue["body"] = new_body
    project.ensure_status(issue, "Done")
    if not has_comment(client, issue["number"], CLOSE_MARKER):
        client.send("POST", f"issues/{issue['number']}/comments", {"body": comment}, {"comment": comment})
    close_issue(client, issue)
    ctx.say(f"closed {a.key}")
    unblocked = []
    for dep in client.get_all(f"issues/{issue['number']}/dependencies/blocking"):
        full = ctx.snap.by_number.get(dep["number"], dep)
        k = rm.parse_marker(full.get("body") or "")
        if full.get("state") != "open" or not k:
            continue
        if all(b == issue["number"] or ((ctx.snap.by_number.get(b) or {}).get("state") == "closed"
                                        and (ctx.snap.by_number.get(b) or {}).get("state_reason") != "not_planned")
               for b in blocker_numbers(client, full["number"])):
            unblocked.append(k)
    ctx.say("unblocked: " + (", ".join(sorted(unblocked, key=lambda x: rm.parse_key(x)[1])) if unblocked else "none"))


def cmd_new_idea(ctx, a):
    """Enregistre une idée (D7) : une issue étiquetée type:idea, sans jalon, Project, statut ni bloc ; idempotente sur le slug."""
    slug = rm.idea_slug(a.title)
    texte = read_body_file(a.body_file) if a.body_file is not None else (a.body or "")
    if not a.title.strip() or not texte.strip() or not slug:
        raise Stop(2, "usage: new-idea needs a non-empty --title with letters or digits, and a non-empty --body or --body-file")
    body = f"{rm.idea_marker(slug)}\n\n{texte.strip()}"
    labels = [rm.LABEL_IDEA] + ([idea_value_label(a.value)] if a.value else []) + ([rm.label_product(a.product)] if a.product else [])
    texts = {"title": a.title, "body": body, "labels": "\n".join(labels)}
    if a.milestone:
        texts["milestone"] = a.milestone
    ctx.client.guard.scan(texts)
    for i in ctx.snap.issues:     # ouverte ou fermée : le slug reste pris
        if rm.parse_idea_marker(i.get("body") or "") == slug:
            ctx.say(f"already exists: idea {slug} (#{i['number']})")
            return
    payload = {"title": a.title, "body": body, "labels": labels}
    if a.milestone:
        payload["milestone"] = milestone_number(ctx.client, a.milestone)
    for l in labels:
        ensure_label(ctx.client, l)
    issue = ctx.client.send("POST", "issues", payload, texts)
    ctx.say(f"created idea {slug} (#{issue['number']})")


def read_body_file(path):
    """Texte d'un --body-file d'idée : un fichier ordinaire, lisible et non vide ; sinon Stop(2) (rien n'est envoyé)."""
    p = Path(path)
    if not p.is_file():
        raise Stop(2, "usage: --body-file must name an existing regular file")
    texte = read_text_file(p, "--body-file")
    if not texte.strip():
        raise Stop(2, "usage: --body-file names an empty file")
    return texte


IDEA_VALUES = ("1", "2", "3")


def idea_value_label(value):
    return f"value:{value}"


def idea_of(ctx, ref):
    """L'issue de l'idée désignée par `<n>` ou `#<n>` ; Stop(2) si ce n'est pas un numéro, Stop(7) si l'issue manque ou n'a pas l'étiquette type:idea."""
    m = re.fullmatch(r"#?(\d+)", ref or "")
    if not m:
        raise Stop(2, "usage: expected an issue number like 244 or #244")
    issue = ctx.snap.by_number.get(int(m.group(1)))
    if issue is None or rm.LABEL_IDEA not in label_names(issue):
        raise Stop(7, f"#{m.group(1)} is not an idea (no {rm.LABEL_IDEA} label)")
    return issue


def cmd_edit_idea(ctx, a):
    """Change la valeur (étiquette value:N), le jalon ou le corps (--body-file) d'une idée existante (#184)."""
    exclusive_no_milestone(a)
    if a.value is None and a.milestone is None and a.body_file is None and a.title is None and a.product is None and not a.no_milestone:
        raise Stop(2, "usage: edit-idea needs --title, --value, --milestone, --no-milestone, --product or --body-file")
    if a.title is not None and not a.title.strip():
        raise Stop(2, "usage: --title must not be empty")
    issue = idea_of(ctx, a.number)
    client = ctx.client
    payload, texts = {}, {}
    if a.title is not None and a.title.strip() != issue.get("title"):
        payload["title"] = texts["title"] = a.title.strip()      # le marqueur (slug) ne change pas
    if a.body_file is not None:
        texte = read_body_file(a.body_file).strip()
        slug = rm.parse_idea_marker(issue.get("body") or "")      # le marqueur de l'idée reste en tête du corps
        body = f"{rm.idea_marker(slug)}\n\n{texte}" if slug else texte
        if body != (issue.get("body") or ""):
            payload["body"], texts["body"] = body, body
    if a.value is not None:
        wanted = idea_value_label(a.value)
        labels = [l for l in label_names(issue) if not re.fullmatch(r"value:\d+", l)] + [wanted]
        if sorted(labels) != sorted(label_names(issue)):
            payload["labels"], texts["labels"] = labels, "\n".join(labels)
    if a.product is not None:
        labels = with_product(payload.get("labels", label_names(issue)), a.product)
        if sorted(labels) != sorted(label_names(issue)):
            payload["labels"], texts["labels"] = labels, "\n".join(labels)
    if a.milestone is not None and issue_milestone(issue) != a.milestone:
        texts["milestone"] = a.milestone
    clear = a.no_milestone and issue_milestone(issue) is not None      # D5 : le jalon de l'idée est retiré, le jalon lui-même reste
    if not texts and not clear:
        ctx.say("nothing to do")
        return
    client.guard.scan(texts)
    if "milestone" in texts:
        payload["milestone"] = milestone_number(client, a.milestone)
    if clear:
        payload["milestone"] = None
    for l in payload.get("labels", []):
        ensure_label(client, l)
    patch_issue(client, issue["number"], payload, texts)
    ctx.say(f"edited idea #{issue['number']}")


def bases_permises(variable):
    """Les dossiers physiques que l'enveloppe figée permet pour un fichier ; None hors enveloppe (variable absente : comportement d'avant)."""
    brut = os.environ.get(variable)
    if not brut:
        return None
    return [os.path.realpath(b) for b in brut.split(":") if b.startswith("/")] or [""]


def chemin_du_descripteur(fd):
    """Chemin physique du fichier ouvert (macOS : F_GETPATH ; ailleurs : /proc/self/fd), ou OSError quand il ne se lit pas."""
    import fcntl
    f_getpath = getattr(fcntl, "F_GETPATH", None)
    if f_getpath is not None:
        brut = fcntl.fcntl(fd, f_getpath, b"\0" * 1024)
        return os.fsdecode(brut.split(b"\0", 1)[0])
    return os.readlink(f"/proc/self/fd/{fd}")


def controler_descripteur(fd, bases):
    """Le fichier ouvert est ordinaire, sans autre lien physique, à nous, et se trouve sous une base permise ; sinon OSError.
    Remplace : le seul contrôle du chemin saisi par l'enveloppe (qui ne voit ni un lien physique ni un échange de lien entre le contrôle et l'ouverture).
    Retrait : avec le bac à sable."""
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_uid != os.getuid():
        raise OSError("file refused")
    reel = chemin_du_descripteur(fd)
    if not any(b and (reel + "/").startswith(b.rstrip("/") + "/") for b in bases):
        raise OSError("file outside the permitted folders")


def lire_texte(chemin):
    """Texte d'un fichier. Sous l'enveloppe figée (variable des bases posée) : ouverture sans suivre un lien, contrôle du descripteur, lecture ;
    hors enveloppe : lecture ordinaire, comme avant."""
    bases = bases_permises(ENV_BASES_LECTURE)
    if bases is None:
        return Path(chemin).read_text(encoding="utf-8")
    fd = os.open(chemin, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        controler_descripteur(fd, bases)
        flux = os.fdopen(fd, "r", encoding="utf-8")
    except BaseException:
        os.close(fd)
        raise
    with flux:
        return flux.read()


def ecrire_texte(chemin, texte):
    """Écrit un fichier. Sous l'enveloppe figée : ouverture sans suivre un lien, sans troncature, contrôle du descripteur, puis troncature et écriture ;
    hors enveloppe : écriture ordinaire, comme avant."""
    bases = bases_permises(ENV_BASES_SORTIE)
    if bases is None:
        Path(chemin).write_text(texte, encoding="utf-8")
        return
    fd = os.open(chemin, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        controler_descripteur(fd, bases)
        os.ftruncate(fd, 0)
        flux = os.fdopen(fd, "w", encoding="utf-8")
    except BaseException:
        os.close(fd)
        raise
    with flux:
        flux.write(texte)


def read_text_file(path, option):
    try:
        return lire_texte(path)
    except (OSError, UnicodeDecodeError):
        raise Stop(2, f"usage: {option} must name a readable text file") from None


def cmd_comment_idea(ctx, a):
    """Commente une idée (issue type:idea) ; le texte passe par le garde avant toute requête (#244, point F)."""
    issue = idea_of(ctx, a.number)
    texte = read_text_file(a.body_file, "--body-file")
    ctx.client.send("POST", f"issues/{issue['number']}/comments", {"body": texte}, {"comment": texte})
    ctx.say(f"commented idea #{issue['number']}")


def cmd_close_idea(ctx, a):
    """Ferme une idée (issue type:idea), avec un commentaire facultatif posté avant la fermeture ; rien à faire si elle est fermée (#244, point F)."""
    issue = idea_of(ctx, a.number)
    if getattr(a, "duplicate_of", None) is not None:
        if a.comment_file:
            raise Stop(2, "usage: --duplicate-of is incompatible with --comment-file")
        return close_as_duplicate(ctx, issue, f"#{issue['number']}", a.duplicate_of)
    texte = read_text_file(a.comment_file, "--comment-file") if a.comment_file else None
    if texte is not None:
        ctx.client.guard.scan({"comment": texte})      # le refus du garde précède toute écriture
    if issue.get("state") == "closed":
        ctx.say("nothing to do")
        return
    if texte is not None and texte.strip():
        ctx.client.send("POST", f"issues/{issue['number']}/comments", {"body": texte}, {"comment": texte})
    close_issue(ctx.client, issue)
    ctx.say(f"closed idea #{issue['number']}")


def issue_of_ref(ctx, ref):
    """L'issue désignée par une clé R-<n> ou un numéro (`<n>`, `#<n>`) ; Stop(2) si ni l'un ni l'autre, Stop(7) si elle manque."""
    if is_issue_number(ref):
        issue = ctx.snap.by_number.get(int(ref.lstrip("#")))
        if issue is None:
            raise Stop(7, f"unknown issue {ref}")
        return issue
    return ctx.feature(ref)


def cmd_detach_sub_issue(ctx, a):
    """Détache une sous-issue de son parent (inverse du rattachement, #406) ; refus si ce n'est pas une sous-issue de ce parent."""
    texte = read_text_file(a.comment_file, "--comment-file") if a.comment_file else None
    if texte is not None:
        ctx.client.guard.scan({"comment": texte})      # le refus du garde précède toute écriture
    parent, child = issue_of_ref(ctx, a.parent), issue_of_ref(ctx, a.child)
    if child["number"] not in sub_issue_numbers(ctx.client, parent["number"]):
        raise Stop(7, f"#{child['number']} is not a sub-issue of #{parent['number']}")
    ctx.client.send("DELETE", f"issues/{parent['number']}/sub_issue", {"sub_issue_id": child["id"]}, {})
    ctx.say(f"detached #{child['number']} from #{parent['number']}")
    if texte is not None and texte.strip():
        ctx.client.send("POST", f"issues/{child['number']}/comments", {"body": texte}, {"comment": texte})
        ctx.say(f"commented #{child['number']}")


def cmd_sub_issues(ctx, a):
    """Lit les sous-issues d'une issue : numéro, état, clé ; signale les clés en double (D1). Lecture seule, code 0 même avec des doublons."""
    parent = issue_of_ref(ctx, a.parent)
    states = sub_issue_states(ctx, parent)
    for s in states:
        ctx.say(f"#{s['number']} {s['state']} {s['key'] or 'no key'}")
    ctx.say(f"{len(states)} sub-issue(s), {sum(1 for s in states if s['state'] == 'open')} open")
    dupes = duplicate_keys(ctx.snap, [s["key"] for s in states if s["key"]])
    for key, numbers in dupes.items():
        ctx.say(f"duplicate key {key}: " + ", ".join(f"#{n}" for n in numbers))
    if not dupes:
        ctx.say("no duplicate key")


def read_queue(client):
    """(issues normalisées, jalons {titre: état}) de toute la file, par la requête GraphQL partagée du modèle (une seule lecture, aucune
    écriture : la requête ne contient jamais de mutation). Une erreur dans le corps de la réponse est refusée sans citer son texte."""
    owner, name = client.repo().split("/")
    issues, milestones, after = [], {}, None
    while True:
        body = json.dumps({"query": rm.GRAPHQL_ISSUES_QUERY, "variables": {"owner": owner, "name": name, "after": after}})
        try:
            rep = json.loads(client.run(["api", "graphql", "-H", "GraphQL-Features: sub_issues", "--input", "-"], body))
        except ValueError:
            raise Stop(5, "GitHub answer unreadable; nothing was written") from None
        if rep.get("errors"):
            raise Stop(1, "GitHub refused: GraphQL error (message withheld)")
        repo = ((rep.get("data") or {}).get("repository")) or {}
        page = repo.get("issues")
        if page is None:
            raise Stop(5, "GitHub answer without issues; nothing was written")
        if after is None:
            milestones = {m["title"]: (m.get("state") or "OPEN").lower() for m in (repo.get("milestones") or {}).get("nodes") or [] if m}
        issues += [rm.normalise_node(n, PROJECT_TITLE) for n in page["nodes"] if n]
        if not page["pageInfo"]["hasNextPage"]:
            return issues, milestones
        after = page["pageInfo"]["endCursor"]


def emit_read(a, issues, milestones):
    """Écrit le JSON des lectures (`view`, `list`) dans le fichier de --sortie (une ligne « wrote » sans chemin) ou, sans l'option, sur la
    sortie standard. Forme : {"date", "issues", "milestones"}, celle que lit `roadmap.py --issues-json`."""
    texte = json.dumps({"date": datetime.date.today().isoformat(), "issues": issues, "milestones": milestones}, ensure_ascii=False)
    if not a.sortie:
        print(texte)
        return None
    try:
        ecrire_texte(a.sortie, texte + "\n")
    except OSError:
        raise Stop(2, "usage: --sortie names a file that cannot be written") from None
    return f"wrote {len(issues)} issue(s)"


def cmd_list(ctx, a):
    """Lecture seule : les issues de la file (ouvertes et fermées par défaut), filtrées par jalon, état et libellés, en JSON (niveau 2 du bac à sable, 7.8 ;
    R-20261109-12, réponse 1). Aucune écriture sur GitHub. Remplace : la lecture directe `gh issue list` et l'appel de gh du lecteur de la file.
    Retrait : permanent (l'outil d'écriture est l'unique chemin vers GitHub)."""
    issues, milestones = read_queue(ctx.client)
    if a.milestone:
        issues = [i for i in issues if (i["milestone"] or {}).get("title") == a.milestone]
    if a.state != "all":
        issues = [i for i in issues if i["state"] == a.state]
    for label in a.label or []:
        issues = [i for i in issues if label in i["labels"]]
    ligne = emit_read(a, issues, milestones)
    if ligne:
        ctx.say(ligne)


def cmd_view(ctx, a):
    """Lecture seule : une issue de la file, désignée par son numéro (244 ou #244), sa clé feature (R-12) ou sa clé de tâche (R-12/u3), en
    JSON de la forme de `list`. Inconnue : code 7 ; référence mal formée : code 2. Aucune écriture sur GitHub (niveau 2 du bac à sable, 7.8)."""
    ref = a.ref.strip()
    nombre = re.fullmatch(r"#?(\d+)", ref)
    cle = re.fullmatch(r"R-\d+(?:/(?:g\d+|t\d+\.\d+|u\d+))?", ref)
    if not nombre and not cle:
        raise Stop(2, "usage: expected an issue number (244 or #244) or an identifier like R-12 or R-12/u3")
    issues, milestones = read_queue(ctx.client)
    if nombre:
        trouvees = [i for i in issues if i["number"] == int(nombre.group(1))]
    else:
        trouvees = [i for i in issues if rm.parse_marker(i["body"]) == ref]
    if not trouvees:
        raise Stop(7, f"unknown issue {ref}")
    ligne = emit_read(a, trouvees[:1], milestones)
    if ligne:
        ctx.say(ligne)


def check_key_free(snap, key):
    """Stop(7) si la clé est déjà portée par une issue du dépôt, ouverte ou fermée (lecture de D1 ; change gh-issue-autonomy, D2)."""
    carried = sorted(i["number"] for i in snap.by_key.get(key, []))
    if carried:
        raise Stop(7, f"duplicate key {key}: already carried by #{carried[0]}; nothing was sent")


def cmd_promote_idea(ctx, a):
    """Promeut une idée en feature (change gh-issue-autonomy, D2) : même issue, même numéro, une seule requête PATCH pour le titre,
    le corps et les étiquettes ; le jalon n'est pas touché ; puis le Project (Status gardé, Todo sinon)."""
    snap, client = ctx.snap, ctx.client
    if a.theme not in rm.THEMES:
        raise Stop(2, "usage: --theme must be one of " + ", ".join(rm.THEMES))
    m = re.fullmatch(r"#?(\d+)", a.number or "")
    if not m:
        raise Stop(2, "usage: expected an issue number like 244 or #244")
    issue = snap.by_number.get(int(m.group(1)))
    key = rm.parse_marker((issue or {}).get("body") or "")
    if issue is not None and rm.LABEL_FEATURE in label_names(issue) and key:       # déjà promue : complète le Project
        client.target = key
        if issue.get("state") == "open":      # une feature fermée n'est pas remise au Project
            project = ctx.project
            known = project.items().get(issue["number"])
            project.ensure_status(issue, known[1] if known and known[1] else "Todo")
        ctx.say(f"nothing to do: #{issue['number']} is already {key}")
        return
    issue = idea_of(ctx, a.number)
    if issue.get("state") != "open":
        raise Stop(7, f"#{issue['number']} is closed; reopen it before promoting it")
    n = snap.max_id() + 1
    key = rm.feature_key(n)
    client.target = key
    block = {"id": key, "theme": a.theme, "estimate": "tbd", "method": "direct-prompt", "model": "tbd", "conditions": ""}
    block.update(parse_sets(a.set))
    block["id"], block["theme"] = key, a.theme
    ranks = open_ranks(snap)
    if "rank" not in block:
        block["rank"] = (max(ranks) if ranks else 0) + 10
    elif block["rank"] in ranks:
        raise Stop(7, f"rank already used by {ranks[block['rank']]}")
    invalid_block(block, True, key)
    check_key_free(snap, key)
    text = re.sub(r"\A<!-- roadmap-idea: [a-z0-9-]+ -->", "", issue.get("body") or "").strip()
    title = rm.feature_title(n, (issue.get("title") or "").strip())
    body = feature_body(key, block, text or None)
    labels = [l for l in label_names(issue) if l != rm.LABEL_IDEA] + [rm.LABEL_FEATURE, rm.label_theme(a.theme)]
    labels = [l for i, l in enumerate(labels) if l not in labels[:i]]
    texts = {"title": title, "body": body, "labels": "\n".join(labels)}
    client.guard.scan(texts)
    project = ctx.project
    known = project.items().get(issue["number"])
    status = known[1] if known and known[1] else "Todo"
    for l in labels:
        ensure_label(client, l)
    patch_issue(client, issue["number"], {"title": title, "body": body, "labels": labels}, texts)
    issue.update({"title": title, "body": body, "labels": [{"name": l} for l in labels]})
    snap.by_key.setdefault(key, []).append(issue)
    project.ensure_status(issue, status)
    ctx.say(f"promoted #{issue['number']} to {key}")


def cmd_attach_sub_issue(ctx, a):
    """Rattache une issue existante comme sous-issue (inverse de detach-sub-issue ; change gh-issue-autonomy, D3). Les contrôles
    lisent d'abord l'état (sous-issues, clés en double) ; aucun texte n'est envoyé et aucun jalon ne bouge."""
    parent, child = issue_of_ref(ctx, a.parent), issue_of_ref(ctx, a.child)
    if parent["number"] == child["number"]:
        raise Stop(2, "usage: an issue cannot be its own sub-issue")
    p, c = parent["number"], child["number"]
    if parent.get("state") != "open":
        raise Stop(7, f"#{p} is closed; nothing was sent")
    if p in sub_issue_numbers(ctx.client, c):
        raise Stop(7, f"#{p} is a sub-issue of #{c}; nothing was sent")
    states = sub_issue_states(ctx, parent)
    if any(s["number"] == c for s in states):
        ctx.say(f"nothing to do: #{c} is already a sub-issue of #{p}")
        return
    key = rm.parse_marker(child.get("body") or "")
    twin = next((s["number"] for s in states if key and s["key"] == key), None)
    if twin is not None:
        raise Stop(7, f"duplicate key {key}: already carried by #{twin} under #{p}; nothing was sent")
    add_sub_issue(ctx.client, parent, child)
    ctx.say(f"attached #{c} to #{p}")
    if issue_milestone(child) != issue_milestone(parent):
        ctx.say(f"milestone differs: #{c} {issue_milestone(child) or 'none'}, #{p} {issue_milestone(parent) or 'none'}")


def cmd_ensure_labels(ctx, a):
    made = [l for l in [*rm.all_labels(), rm.LABEL_IDEA] if ensure_label(ctx.client, l)]
    ctx.say(f"created {len(made)} label(s)" if made else "nothing to do")


def cmd_horizon(ctx, a):
    """Lit ou fixe le champ Horizon du Project pour une feature ou une idée (change gh-issue-autonomy, D4). Une tâche suit sa feature
    (code 2) ; une issue fermée n'est pas écrite (code 7) mais se lit ; champ ou option absent : code 6 ; valeur inconnue : code 2.
    Une idée absente du Project y est ajoutée avant la valeur. Même valeur : « nothing to do »."""
    task_msg = "usage: horizon works on a feature or an idea; a task follows its feature"
    if a.value is not None and a.value not in HORIZONS:
        raise Stop(2, "usage: horizon must be one of " + ", ".join(HORIZONS))
    if re.fullmatch(r"R-\d+/\S+", a.ref or ""):
        raise Stop(2, task_msg)
    issue = issue_of_ref(ctx, a.ref)
    labels = label_names(issue)
    if rm.LABEL_TASK in labels:
        raise Stop(2, task_msg)
    if not (rm.LABEL_FEATURE in labels or rm.LABEL_IDEA in labels):
        raise Stop(2, "usage: horizon works on a feature or an idea")
    if a.value is not None and issue.get("state") != "open":
        raise Stop(7, f"{a.ref} is closed; its horizon is not changed")
    project = ctx.project
    project.horizon_field()
    if a.value is None:
        ctx.say(f"horizon {a.ref} {project.horizon_of(issue) or 'none'}")
        return
    ctx.client.guard.scan({"horizon": a.value})
    if project.ensure_horizon(issue, a.value):
        ctx.say(f"horizon {a.ref} {a.value}")
    else:
        ctx.say(f"nothing to do: {a.ref} is already {a.value}")


def open_milestone_of(client, name):
    """Le jalon existant et ouvert de ce nom ; Stop(7) s'il est inconnu ou fermé (lecture seule)."""
    milestone = client.milestones().get(name)
    if milestone is None:
        raise Stop(7, "unknown milestone")
    if milestone.get("state") != "open":
        raise Stop(7, f"closed milestone: {name} is not edited; nothing was sent")
    return milestone


def cmd_edit_milestone(ctx, a):
    """Description et échéance d'un jalon ouvert (change gh-issue-autonomy, D9) : une seule requête PATCH qui ne porte que ces deux
    champs ; ni titre, ni état. Les valeurs identiques ne partent pas ; l'échéance est comparée au jour."""
    if a.description_file is None and a.due is None and not a.no_due:
        raise Stop(2, "usage: edit-milestone needs --description-file, --due or --no-due")
    due = None
    if a.due is not None:
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a.due):
                raise ValueError(a.due)
            datetime.date.fromisoformat(a.due)
        except ValueError:
            raise Stop(2, "usage: --due expects a date YYYY-MM-DD") from None
        due = a.due
    texte = read_body_file(a.description_file).strip() if a.description_file is not None else None
    client = ctx.client
    milestone = open_milestone_of(client, a.name)
    client.guard.scan({"milestone": a.name, **({"description": texte} if texte is not None else {})})
    payload = {}
    if texte is not None and texte != (milestone.get("description") or "").strip():
        payload["description"] = texte
    current_due = (milestone.get("due_on") or "")[:10] or None
    if a.no_due and current_due is not None:
        payload["due_on"] = None
    elif due is not None and due != current_due:
        payload["due_on"] = f"{due}T00:00:00Z"
    if not payload:
        ctx.say("nothing to do")
        return
    client.send("PATCH", f"milestones/{milestone['number']}", payload, {k: v for k, v in payload.items() if k == "description"})
    milestone.update(payload)
    ctx.say(f"edited milestone {a.name}")


def cmd_ensure_milestone(ctx, a):
    ctx.say(f"created milestone {a.name}" if ensure_milestone(ctx.client, a.name, a.closed) else "nothing to do")


# --- Ligne de commande --------------------------------------------------------------------------------------------

class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Stop(2, "usage: " + message.splitlines()[0])


def build_parser():
    p = Parser(prog="gh_issue.py", description="Seul chemin d'écriture vers GitHub pour la file de travail")
    common = Parser(add_help=False)
    common.add_argument("--repo", help="confirme le dépôt de origin (un autre dépôt est refusé)")
    sub = p.add_subparsers(dest="cmd", required=True, parser_class=Parser)

    s = sub.add_parser("new-feature", parents=[common])
    s.add_argument("--title", required=True)
    s.add_argument("--theme", required=True)
    s.add_argument("--milestone", required=True)
    s.add_argument("--blocked-by")
    s.add_argument("--set", action="append")
    s.add_argument("--product", choices=rm.PRODUCTS, help="adds the label product:<value> (no label means PMZilla)")
    s.add_argument("--value", choices=IDEA_VALUES, help="adds the label value:N (1 = high, 3 = low)")
    s.add_argument("--body-file", help="file whose text follows the roadmap block in the body of the feature")
    s.set_defaults(fn=cmd_new_feature)

    s = sub.add_parser("edit", parents=[common])
    s.add_argument("key")
    s.add_argument("--title")
    s.add_argument("--milestone")
    s.add_argument("--no-milestone", action="store_true", help="removes the milestone of the feature and of its sub-issues (the milestone itself stays); exclusive with --milestone")
    s.add_argument("--set", action="append")
    s.add_argument("--product", choices=(*rm.PRODUCTS, PRODUCT_NONE), help="sets the label product:<value>; none removes it")
    s.add_argument("--value", choices=IDEA_VALUES, help="replaces the value:N label (1 = high, 3 = low)")
    s.add_argument("--body-file", help="file whose text replaces the text after the roadmap block (marker and block kept)")
    s.set_defaults(fn=cmd_edit)

    s = sub.add_parser("status", parents=[common])
    s.add_argument("key")
    s.add_argument("status")
    s.set_defaults(fn=cmd_status)

    for name, remove in (("block", False), ("unblock", True)):
        s = sub.add_parser(name, parents=[common])
        s.add_argument("key")
        s.add_argument("--by", required=True)
        s.set_defaults(fn=lambda ctx, a, r=remove: cmd_block(ctx, a, r))

    s = sub.add_parser("comment", parents=[common])
    s.add_argument("key", nargs="?", help="the feature, R-<n> (or --numero)")
    s.add_argument("--numero", type=int, help="issue number of the feature, instead of the key (exclusive with it)")
    s.add_argument("--body-file", required=True)
    s.set_defaults(fn=cmd_comment)

    s = sub.add_parser("new-task", parents=[common])
    s.add_argument("key", help="the feature, R-<n>")
    s.add_argument("--title", required=True, help="text without key; the command adds the prefix R-<n> ·")
    s.add_argument("--body-file", required=True, help="file holding the text of the task")
    s.add_argument("--milestone", help="an existing milestone (default: the milestone of the feature)")
    s.add_argument("--owner", choices=rm.OWNERS, default="user", help="user (default) adds owner:user; agent adds model:<m> (--model required)")
    s.add_argument("--model", choices=rm.MODELS, help="with --owner agent only: the model label model:<m>")
    s.set_defaults(fn=cmd_new_task)

    s = sub.add_parser("set-owner", parents=[common])
    s.add_argument("key", help="the task, R-<n>/g<group>, R-<n>/t<task> or R-<n>/u<k>")
    s.add_argument("--owner", required=True, choices=rm.OWNERS, help="user sets owner:user (removes model:*); agent sets model:<m> (removes owner:user)")
    s.add_argument("--model", choices=rm.MODELS, help="with --owner agent only (required there): the model label model:<m>")
    s.set_defaults(fn=cmd_set_owner)

    s = sub.add_parser("edit-task", parents=[common])
    s.add_argument("key", nargs="?", help="the task, R-<n>/g<group>, R-<n>/t<task> or R-<n>/u<k> (or --numero)")
    s.add_argument("--numero", type=int, help="issue number of the task, instead of the key (exclusive with it)")
    s.add_argument("--milestone", help="an existing open milestone; moves this task only (edit R-<n> moves the feature and all its tasks)")
    s.add_argument("--no-milestone", action="store_true", help="removes the milestone of this open task only (the milestone itself stays); exclusive with --milestone")
    s.add_argument("--title", help="new title text without key; the command adds the prefix R-<n> ·")
    s.add_argument("--body-file", help="file whose text replaces the text after the marker of the task (marker kept; also on a closed task)")
    s.add_argument("--nouvelle-cle", action="store_true", dest="nouvelle_cle",
                   help="gives the task the next free R-<n>/u<k> key of its feature (marker of the body rewritten, title kept); nothing to do when its key is already unique")
    s.set_defaults(fn=cmd_edit_task)

    s = sub.add_parser("reopen-step", parents=[common])
    s.add_argument("key", nargs="?", help="the task, R-<n>/g<group>, R-<n>/t<task> or R-<n>/u<k> (or --numero)")
    s.add_argument("--numero", type=int, help="issue number of the task, instead of the key (exclusive with it)")
    s.add_argument("--reason", required=True, help="why the task is reopened; posted as a comment")
    s.set_defaults(fn=cmd_reopen_step)

    for name, fn in (("sync-tasks", cmd_sync_tasks), ("close-feature", cmd_close_feature), ("close-step", cmd_close_step)):
        s = sub.add_parser(name, parents=[common])
        s.add_argument("key", nargs="?" if name == "close-step" else None)
        if name == "close-step":
            s.add_argument("--numero", type=int, help="issue number of the task, instead of the key (exclusive with it)")
        if name == "sync-tasks":
            s.add_argument("--change", help="change name when the feature block has no change: field (refused if it differs from the field)")
            s.add_argument("--groups", help="only these tasks.md groups, list and ranges such as 2-8,11 (an unknown group is refused)")
            s.add_argument("--dry-run", action="store_true", help="print what would be created, write nothing")
        if name == "close-step":
            s.add_argument("--reason", help="mandatory for an agent sub-issue, optional for a user step")
        if name == "close-feature":
            s.add_argument("--edition-public", action="store_true", help="add the edition:public label (also on a closed feature)")
            s.add_argument("--after-merge", action="store_true", help="work already merged: post --comment-file instead of the 'before the merge' sentence")
            s.add_argument("--comment-file", help="text of the closing comment (with --after-merge or --reason)")
            s.add_argument("--reason", choices=("replaced", "dropped"), help="feature replaced or dropped, work not merged: closes as not planned, needs --comment-file, no Done, dependents stay blocked")
            s.add_argument("--duplicate-of", type=int, metavar="N", help="closes the feature as a duplicate of issue N (comment, then closing; no Done, no done_on; exclusive with --reason, --after-merge, --edition-public, --comment-file)")
        s.set_defaults(fn=fn)

    s = sub.add_parser("new-idea", parents=[common])
    s.add_argument("--title", required=True)
    grp = s.add_mutually_exclusive_group(required=True)
    grp.add_argument("--body", help="text of the idea")
    grp.add_argument("--body-file", help="file holding the text of the idea (exclusive with --body)")
    s.add_argument("--milestone", help="an existing milestone")
    s.add_argument("--value", choices=IDEA_VALUES, help="adds the label value:N")
    s.add_argument("--product", choices=rm.PRODUCTS, help="adds the label product:<value> (no label means PMZilla)")
    s.set_defaults(fn=cmd_new_idea)

    s = sub.add_parser("edit-idea", parents=[common])
    s.add_argument("number", help="issue number of the idea, 244 or #244")
    s.add_argument("--title", help="new title of the idea (not empty)")
    s.add_argument("--value", choices=IDEA_VALUES, help="replaces the value:N label")
    s.add_argument("--product", choices=(*rm.PRODUCTS, PRODUCT_NONE), help="sets the label product:<value>; none removes it")
    s.add_argument("--milestone", help="an existing milestone")
    s.add_argument("--no-milestone", action="store_true", help="removes the milestone of the idea (the milestone itself stays); exclusive with --milestone")
    s.add_argument("--body-file", help="file whose text replaces the body of the idea (its marker is kept)")
    s.set_defaults(fn=cmd_edit_idea)

    s = sub.add_parser("comment-idea", parents=[common])
    s.add_argument("number", help="issue number of the idea, 244 or #244")
    s.add_argument("--body-file", required=True)
    s.set_defaults(fn=cmd_comment_idea)

    s = sub.add_parser("close-idea", parents=[common])
    s.add_argument("number", help="issue number of the idea, 244 or #244")
    s.add_argument("--comment-file", help="text posted as a comment before the closing")
    s.add_argument("--duplicate-of", type=int, metavar="N", help="closes the idea as a duplicate of issue N (comment, then closing; exclusive with --comment-file)")
    s.set_defaults(fn=cmd_close_idea)

    s = sub.add_parser("reopen-idea", parents=[common])
    s.add_argument("number", help="issue number of the idea, 244 or #244")
    s.add_argument("--reason", required=True, help="why the idea is reopened; posted as a comment")
    s.set_defaults(fn=cmd_reopen_idea)

    s = sub.add_parser("reopen-feature", parents=[common])
    s.add_argument("key", help="the feature, R-<n>")
    s.add_argument("--reason", required=True, help="why the feature is reopened; posted as a comment")
    s.set_defaults(fn=cmd_reopen_feature)

    s = sub.add_parser("detach-sub-issue", parents=[common])
    s.add_argument("parent", help="the parent, R-<n> or an issue number")
    s.add_argument("child", help="the sub-issue to detach, R-<n> or an issue number (244 or #244)")
    s.add_argument("--comment-file", help="text posted as a comment on the child after the detaching")
    s.set_defaults(fn=cmd_detach_sub_issue)

    s = sub.add_parser("promote-idea", parents=[common])
    s.add_argument("number", help="issue number of the idea, 244 or #244")
    s.add_argument("--theme", required=True, help="theme of the new feature (theme:<value> label and block)")
    s.add_argument("--set", action="append", help="block key=value, as new-feature")
    s.set_defaults(fn=cmd_promote_idea)

    s = sub.add_parser("attach-sub-issue", parents=[common])
    s.add_argument("parent", help="the parent, R-<n> or an issue number")
    s.add_argument("child", help="the issue to attach as a sub-issue, R-<n> or an issue number (244 or #244)")
    s.set_defaults(fn=cmd_attach_sub_issue)

    s = sub.add_parser("view", parents=[common])
    s.add_argument("ref", help="an issue number (244 or #244) or an identifier: R-<n> or R-<n>/<id>")
    s.add_argument("--sortie", help="file that receives the JSON (default: the standard output)")
    s.set_defaults(fn=cmd_view)

    s = sub.add_parser("list", parents=[common])
    s.add_argument("--milestone", help="only the issues of this milestone")
    s.add_argument("--state", choices=("open", "closed", "all"), default="all", help="only open or closed issues (default: all)")
    s.add_argument("--label", action="append", help="only the issues that carry this label (repeatable: all of them)")
    s.add_argument("--sortie", help="file that receives the JSON (default: the standard output)")
    s.set_defaults(fn=cmd_list)

    s = sub.add_parser("sub-issues", parents=[common])
    s.add_argument("parent", help="the parent, R-<n> or an issue number (244 or #244)")
    s.set_defaults(fn=cmd_sub_issues)

    s = sub.add_parser("horizon", parents=[common])
    s.add_argument("ref", help="a feature or an idea: R-<n>, 244 or #244 (a task follows its feature)")
    s.add_argument("value", nargs="?", help="V2, V3, V4 or \"Plus tard\"; without it, prints the current Horizon")
    s.set_defaults(fn=cmd_horizon)

    s = sub.add_parser("edit-milestone", parents=[common])
    s.add_argument("name", help="an existing open milestone")
    s.add_argument("--description-file", help="file whose text becomes the description of the milestone")
    due = s.add_mutually_exclusive_group()
    due.add_argument("--due", help="due date YYYY-MM-DD")
    due.add_argument("--no-due", action="store_true", help="removes the due date")
    s.set_defaults(fn=cmd_edit_milestone)

    s = sub.add_parser("ensure-labels", parents=[common])
    s.set_defaults(fn=cmd_ensure_labels)
    s = sub.add_parser("ensure-milestone", parents=[common])
    s.add_argument("name")
    s.add_argument("--closed", action="store_true")
    s.set_defaults(fn=cmd_ensure_milestone)
    return p


def emit(code, lines):
    stream = sys.stdout if code == 0 else sys.stderr
    for l in lines:
        print(PREFIX + l, file=stream)


def main(argv=None):
    client = None
    try:
        args = build_parser().parse_args(argv)
        guard = Guard.load()
        client = Client(guard)
        if getattr(args, "key", None) and not is_issue_number(args.key):
            client.target = args.key.split("/")[0]
        if args.repo and args.repo != client.repo():
            raise Stop(2, "usage: the repository is the one of origin; another repository is refused")
        ctx = Ctx(client)
        args.fn(ctx, args)
        emit(0, ctx.out)
        return 0
    except Stop as s:
        lines = list(s.lines)
        if s.code in (1, 6) and client is not None and client.writes:
            lines.append(client.confirmed_line())
        emit(s.code, lines)
        return s.code


if __name__ == "__main__":
    sys.exit(main())
