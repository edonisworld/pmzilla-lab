"""Messages de tools/train_auto.py par langue (change autonomous-trains-observe, design D11). Le français est la langue de référence.

Les libellés de raison (`reason:<code>`) sont aussi ceux de tools/train_ready.py (importés de ce module : une seule source).
"""

REASONS_FR = {
    "hors-fenetre": "hors fenêtre",
    "matin": "veille ou sauvegarde du jour en cours",   # R-20261102-3 et R-20261102-5 (D4) : le contrôle 4 ne refuse plus que pour cela
    "verrou-fin": "verrou de fin tenu",   # le libellé « runner-session » est retiré avec le verrou de session (tooling-proof-in-container, T2)
    "espace-de-travail": "espace de travail pas sur main ou pas propre",
    "distant": "distant injoignable",
    "main-different": "main local différent du distant",
    "dossier-execution": "dossier d'exécution pas à jour",
    "crochets": "crochets non vérifiés",
    "identite": "identité Git absente",
    "liste-illisible": "liste prête illisible",
    "garde-noms": "garde des noms impossible",
    "arret-disparu": "arrêt disparu sans « reprendre »",
    "sommet-change": "sommet changé depuis l'inscription",
    "empreinte": "empreinte du runner différente de l'arbre",
    "branche-absente": "branche introuvable",
    "deja-fusionnee": "déjà dans origin/main",
    # D16 (autonomous-trains-merge, tâche 9.5) remplace les libellés d'autonomous-trains-observe D4/P3 (R-20261101-61) : « train de l'auteur » pour l'outillage et les postures,
    # « revue Opus requise » pour la base et l'interface (refus de `add --revue non-requise`)
    "outillage-protege": "outillage de fin, runner, preuve, .claude/ ou CLAUDE.md : train de l'auteur",
    "postures": "arbre lu par les postures : train de l'auteur",
    "base": "code de la base ou migration : revue Opus requise",
    "front": "chemin d'interface de Mothra : revue Opus requise",
    "session-active": "session active dans son worktree",
    "revue": "revue non requise déclarée pour une branche de code",
    "plafond": "au-delà du plafond : fenêtre suivante",
    "controle-impossible": "contrôles de fin impossibles",
    "nom": "nom refusé par la garde",
    # raisons propres à la décision du passage ou à l'inscription (train_ready.py add)
    "arret": "arrêt d'urgence actif",
    "session": "session Claude Code",
    "liste-vide": "liste prête vide",
    "toutes-ecartees": "toutes les lignes sont écartées",
    "essai": "essai de fin",
    "sans-worktree": "branche sans worktree",
    "worktree-sale": "worktree pas propre",
    "sans-empreinte": "aucune preuve dans le worktree (runner complet ou --branch)",
    "liste-pleine": "liste pleine (plafond atteint)",
}

REASONS_EN = {
    "hors-fenetre": "outside the window",
    "matin": "today's watch or backup running",   # R-20261102-3 and R-20261102-5 (D4)
    "verrou-fin": "finish lock held",
    "espace-de-travail": "workspace not on main or not clean",
    "distant": "remote unreachable",
    "main-different": "local main differs from the remote",
    "dossier-execution": "run tree not up to date",
    "crochets": "hooks not verified",
    "identite": "Git identity missing",
    "liste-illisible": "ready list unreadable",
    "garde-noms": "names guard unavailable",
    "arret-disparu": "stop vanished without \"reprendre\"",
    "sommet-change": "tip changed since the addition",
    "empreinte": "runner fingerprint differs from the tree",
    "branche-absente": "branch not found",
    "deja-fusionnee": "already in origin/main",
    "outillage-protege": "finish tooling, runner, proof, .claude/ or CLAUDE.md: the author's train",
    "postures": "tree read by the postures: the author's train",
    "base": "database code or migration: Opus review required",
    "front": "Mothra interface path: Opus review required",
    "session-active": "session active in its worktree",
    "revue": "review declared not required for a code branch",
    "plafond": "beyond the cap: next window",
    "controle-impossible": "finish checks impossible",
    "nom": "name refused by the guard",
    "arret": "emergency stop active",
    "session": "Claude Code session",
    "liste-vide": "ready list empty",
    "toutes-ecartees": "every line is excluded",
    "essai": "finish trial",
    "sans-worktree": "branch without a worktree",
    "worktree-sale": "worktree not clean",
    "sans-empreinte": "no proof in the worktree (complete runner or --branch)",
    "liste-pleine": "list full (cap reached)",
}

_FR = {
    "observation": "train_auto : observation : {n} branche(s) retenue(s), {k} écartée(s) ; essai code {c}",
    "waiting": "train_auto : attente : {label}",
    "nothing": "train_auto : rien à faire",
    "stopped": "train_auto : arrêté (arrêt d'urgence actif)",
    "discarded": "train_auto : écartée : {branch} : {label}",
    "session_refused": "train_auto : session Claude Code, lancement refusé",
    "already_running": "train_auto : un autre passage est en cours",
    "stop_set": "train_auto : arrêt posé",
    "stop_lifted": "train_auto : arrêt levé",
    "stop_armed": "train_auto : arrêt armé après le code {c}",
    "stop_vanished": "train_auto : arrêt disparu sans « reprendre » : recréé",
    "folders": "train_auto : dossiers du lab ou dossier de données inutilisables",
    "not_writable": "train_auto : journal ou état non inscriptible, rien n'est décidé",
    "unexpected": "train_auto : erreur inattendue ({kind})",
    "masked_branch": "branche masquée",
    "stop_active": "actif",
    "stop_absent": "absent",
    "status_none": "train_auto : aucun passage enregistré ; arrêt {stop}",
    # revue de contrôle 10.2, point A : ne remplace rien ; tombe avec le passage automatique (R-166), comme `etat-illisible`
    "status_unreadable": "train_auto : état du train automatique illisible : le réparer ou le retirer ; arrêt {stop}",
    "status_line": "train_auto : dernier passage {date} Paris : {decision} ({reason}) ; arrêt {stop} ; liste : {n} ligne(s), {k} valide(s)",
    "obs_header": "train_auto : observation sur {days} jour(s) : {passes} passage(s), {observed} jour(s) observé(s)",
    "obs_decision": "train_auto :   décision {name} : {n}",
    "obs_reason": "train_auto :   raison {name} : {n}",
    "obs_day": "train_auto :   {date} : {n} passage(s)",
    "obs_merged": "train_auto :   fusionnée après observation : {branch} (retenue le {date} Paris, délai {delay} min)",
    "obs_excluded": "train_auto :   fusionnée alors qu'elle était écartée : {branch} ({label})",
    "obs_unlisted": "train_auto :   fusionnée sans avoir été listée : {branch}",
    "obs_counts": "train_auto :   bilan : {merged} fusionnée(s) après observation, {excluded} écartée(s) puis fusionnée(s), {unlisted} non listée(s)",
    "usage_language": "train_auto : langue inconnue",
    # tranche 3 d'autonomous-trains-merge (D5, D6, D19) : l'activation de la fusion automatique
    "activation_head": "train_auto : activation : {k} train(s) de suite sur {n} requis",
    "activation_missing": "train_auto : activation : manque {label}",
    "activation_refused": "train_auto : activation refusée : condition non remplie",
    "activated": "train_auto : fusion automatique activée",
    "deactivated": "train_auto : fusion automatique désactivée",
    "already_deactivated": "train_auto : fusion automatique déjà désactivée",
    "record_unreadable": "train_auto : journal des trains illisible",
    # tranche 3 (D9, D14, D15, D19) : le mode de fusion
    "merge_line": "train_auto : fusion automatique : {n} branche(s) ; train code {c} ({sens}), {m} min",
    "for_author": "train_auto : pour l'auteur : {suite}",
    "activation_invalid": "train_auto : activation invalide : mode observation",
    "report_not_written": "train_auto : compte rendu non écrit (écriture impossible)",
    "notification_failed": "train_auto : notification non envoyée",
    # faux 65 du train automatique (D2) : `plist` refusé (code 8)
    "plist_old_python": "train_auto : modèle refusé : python3 3.10 ou plus requis pour le générer (version {version})",
    "plist_no_python3": "train_auto : modèle refusé : le dossier de l'interpréteur n'a pas de python3 identique",
}

# tranche 3 d'autonomous-trains-merge : raisons du passage en fusion (D9, D11, D17) et suites « pour l'auteur » du train réel (D10, libellés mot pour mot)
REASONS_FR.update({
    "depart-limite": "départ limite du train dépassé",
    "crochets-doctor": "contrôle doctor du crochet reference-transaction rouge ou absent",
    "etat-illisible": "état du train automatique illisible : le réparer ou le retirer",
    "echec-au-sommet": "train refusé sur ce sommet : nouveau commit ou retrait attendu",
    "fusion-auto": "fusion automatique",
    "suite-rien": "rien",
    "suite-anomalie": "anomalie : examiner le journal du train, puis reprendre",
    "suite-refusee": "branche refusée : la retirer de la liste ou la corriger",
    "suite-conflit": "conflit : rebaser la branche en conflit",
    "suite-garde-matin": "garde du matin : le passage suivant réessaie",
    "suite-verrou-fin": "verrou de fin tenu : le passage suivant réessaie",
    "suite-base-rouge": "phase base rouge : corriger la branche en cause",
    "suite-train-rouge": "train rouge : corriger la branche en cause",
    "suite-runner": "runner non concluant : examiner le journal du train",
    "suite-e2e-rouge": "phase de bout en bout rouge : corriger la branche en cause",
    "suite-jeu-essai": "jeu d'essai validant absent : train de l'auteur",
    "suite-politique": "politique : {labels}",
    "suite-incomplete": "fusionné, fin incomplète : voir les causes",
    "suite-environnement": "environnement : examiner le journal du train",
    "suite-arret-arme": "arrêt armé : examiner, puis reprendre",
})

# libellés des conditions manquantes de l'activation (D5), rangés comme les raisons (même préfixe, même accès par label())
REASONS_FR.update({
    "serie": "trains verts de suite sur le conteneur",
    "deux-branches": "un train de deux branches ou plus",
    "base-ou-front": "un train qui touche la base ou l'interface de Mothra",
    "python-ancien": "python3 3.10 ou plus requis",   # R-20261110-34 : le passage sous un interpréteur plus ancien attend, sans armer l'arrêt
    "arret-actif": "arrêt d'urgence actif (reprendre d'abord)",   # faux 65 (D9)
    "essai-launchd": "un essai à 0 lancé par launchd depuis le dernier chargement du modèle",   # faux 65 (D10)
})

_EN = {
    "observation": "train_auto: observation: {n} branch(es) retained, {k} excluded; trial code {c}",
    "waiting": "train_auto: waiting: {label}",
    "nothing": "train_auto: nothing to do",
    "stopped": "train_auto: stopped (emergency stop active)",
    "discarded": "train_auto: excluded: {branch}: {label}",
    "session_refused": "train_auto: Claude Code session, launch refused",
    "already_running": "train_auto: another pass is running",
    "stop_set": "train_auto: stop set",
    "stop_lifted": "train_auto: stop lifted",
    "stop_armed": "train_auto: stop armed after code {c}",
    "stop_vanished": "train_auto: stop vanished without \"reprendre\": recreated",
    "folders": "train_auto: lab folders or data folder unusable",
    "not_writable": "train_auto: journal or state not writable, nothing decided",
    "unexpected": "train_auto: unexpected error ({kind})",
    "masked_branch": "masked branch",
    "stop_active": "active",
    "stop_absent": "absent",
    "status_none": "train_auto: no pass recorded; stop {stop}",
    "status_unreadable": "train_auto: automatic train state unreadable: repair or remove it; stop {stop}",
    "status_line": "train_auto: last pass {date} Paris: {decision} ({reason}); stop {stop}; list: {n} line(s), {k} valid",
    "obs_header": "train_auto: observation over {days} day(s): {passes} pass(es), {observed} day(s) observed",
    "obs_decision": "train_auto:   decision {name}: {n}",
    "obs_reason": "train_auto:   reason {name}: {n}",
    "obs_day": "train_auto:   {date}: {n} pass(es)",
    "obs_merged": "train_auto:   merged after observation: {branch} (retained on {date} Paris, delay {delay} min)",
    "obs_excluded": "train_auto:   merged while excluded: {branch} ({label})",
    "obs_unlisted": "train_auto:   merged without having been listed: {branch}",
    "obs_counts": "train_auto:   total: {merged} merged after observation, {excluded} excluded then merged, {unlisted} unlisted",
    "usage_language": "train_auto: unknown language",
    "activation_head": "train_auto: activation: {k} train(s) in a row out of {n} required",
    "activation_missing": "train_auto: activation: missing {label}",
    "activation_refused": "train_auto: activation refused: condition not met",
    "activated": "train_auto: automatic merge activated",
    "deactivated": "train_auto: automatic merge deactivated",
    "already_deactivated": "train_auto: automatic merge already deactivated",
    "record_unreadable": "train_auto: train record unreadable",
    "merge_line": "train_auto: automatic merge: {n} branch(es); train code {c} ({sens}), {m} min",
    "for_author": "train_auto: for the author: {suite}",
    "activation_invalid": "train_auto: activation invalid: observation mode",
    "report_not_written": "train_auto: report not written (write impossible)",
    "notification_failed": "train_auto: notification not sent",
    # faux 65 du train automatique (D2): `plist` refused (code 8)
    "plist_old_python": "train_auto: template refused: python3 3.10 or newer required to generate it (version {version})",
    "plist_no_python3": "train_auto: template refused: the interpreter's folder has no identical python3",
}

REASONS_EN.update({
    "depart-limite": "latest start of the train exceeded",
    "crochets-doctor": "doctor check of the reference-transaction hook red or absent",
    "etat-illisible": "automatic train state unreadable: repair or remove it",
    "echec-au-sommet": "train refused on this tip: new commit or removal awaited",
    "fusion-auto": "automatic merge",
    "suite-rien": "nothing",
    "suite-anomalie": "anomaly: examine the train log, then resume",
    "suite-refusee": "branch refused: remove it from the list or fix it",
    "suite-conflit": "conflict: rebase the conflicting branch",
    "suite-garde-matin": "morning guard: the next pass retries",
    "suite-verrou-fin": "finish lock held: the next pass retries",
    "suite-base-rouge": "base phase red: fix the branch at fault",
    "suite-train-rouge": "train red: fix the branch at fault",
    "suite-runner": "runner inconclusive: examine the train log",
    "suite-e2e-rouge": "end-to-end phase red: fix the branch at fault",
    "suite-jeu-essai": "validating evaluation set missing: the author's train",
    "suite-politique": "policy: {labels}",
    "suite-incomplete": "merged, finish incomplete: see the causes",
    "suite-environnement": "environment: examine the train log",
    "suite-arret-arme": "stop armed: examine, then resume",
})

REASONS_EN.update({
    "serie": "green trains in a row on the container",
    "deux-branches": "a train of two branches or more",
    "base-ou-front": "a train that touches Mothra's database or interface",
    "python-ancien": "python3 3.10 or newer required",   # R-20261110-34
    "arret-actif": "emergency stop active (resume first)",   # faux 65 (D9)
    "essai-launchd": "a trial at 0 launched by launchd since the template was last loaded",   # faux 65 (D10)
})


DECISIONS_FR = {"observe": "observé", "attente": "attente", "arrete": "arrêté", "rien": "rien à faire", "refuse": "refusé", "train": "train lancé"}
DECISIONS_EN = {"observe": "observed", "attente": "waiting", "arrete": "stopped", "rien": "nothing to do", "refuse": "refused", "train": "train launched"}


def _with_reasons(base, reasons, decisions):
    texte = dict(base)
    for code, libelle in reasons.items():
        texte["reason:" + code] = libelle
    for code, libelle in decisions.items():
        texte["decision:" + code] = libelle
    return texte


CATALOGS = {"fr": _with_reasons(_FR, REASONS_FR, DECISIONS_FR), "en": _with_reasons(_EN, REASONS_EN, DECISIONS_EN)}


def decision_label(code, language="fr"):
    """Libellé d'un code de décision (observe, attente, arrete, rien, refuse) ; un code inconnu est rendu tel quel."""
    return CATALOGS.get(language, CATALOGS["fr"]).get("decision:" + str(code)) or str(code)


def label(code, language="fr"):
    """Libellé d'un code de raison ; un code inconnu est rendu tel quel."""
    return CATALOGS.get(language, CATALOGS["fr"]).get("reason:" + str(code)) or CATALOGS["fr"].get("reason:" + str(code)) or str(code)
