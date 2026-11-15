# Image de la CI locale de PMZilla Lab (change local-ci-container, design D4).
#
# Construite par `bash tools/ci_local.sh build` (ou `up`), par l'auteur seul, avec réseau, depuis l'arbre de HEAD (git archive) :
# aucun fichier ignoré ni local n'est dans le contexte. Le passage (`run`) n'a pas de réseau (UV_OFFLINE=1, --network none).
# Chaque élément épinglé a son entrée dans docs/pmzilla/composants.yaml (pinned_in: CI Dockerfile) ; tests/composants vérifie
# l'épinglage (étiquette et empreinte sha256 des images, version exacte de la CLI OpenSpec, Python de .python-version).
# Une valeur A_REMPLIR_PAR_L_AUTEUR est lue par l'auteur hors session (registre, docker pull) : tests/composants la nomme.
# Aucun secret, aucun ARG qui en porte un, aucun ADD depuis une adresse. Paquets système de la distribution de la base, non
# épinglés un à un (fiche Q2). La clé de l'image (hash de ce fichier, des entrées de l'inventaire, de .python-version, des
# dépendances du lanceur, des verrous npm déclarés et de l'engines.npm de chaque suite npm) est posée par tools/ci_local.sh en étiquette et dans le tag.

# Base : image officielle Node, version exacte 26.13.0 (LTS, amendement du 2026-11-04 de l'ADR 0005 ; égale à celle de mothra/.node-version, design D4 de mothra-node-lts), variante slim,
# épinglée par l'empreinte de son index multi-architecture.
FROM node:26.13.0-slim@sha256:e4db4c914bf8ad241bd24804fc25d272d89bad97e68cdc8a1414862790a02c39

# Outils système des suites (inventaire de la tâche 2.1) : Git, Bash, Zsh, Perl (shasum, repli de durée), lsof, procps (ps, pgrep).
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates git bash zsh perl lsof procps \
 && rm -rf /var/lib/apt/lists/*

# uv copié de son image officielle ; étiquette = version d'uv du Mac de l'auteur (uv --version, 2026-10-20) ; montée en 0.13.6 le 2026-11-02 (lot A, R-20261102-4), puis en 0.13.7 le 2026-11-04 (R-20261104-64, mises à jour groupées avec Node 26.13.0).
COPY --from=ghcr.io/astral-sh/uv:0.13.7@sha256:96f40d3904aad8d0bd010539001d36c8e2188b981e1334471a90c4a1d93bb490 /uv /uvx /usr/local/bin/

# CLI OpenSpec (suites de la voie légère et des lecteurs OpenSpec) ; version = celle du Mac de l'auteur (openspec --version), alignée le 2026-11-02 sur 1.16.0 (lot A, R-20261102-4 ; précédemment 2026-10-22, idée #450).
RUN npm install -g @fission-ai/openspec@1.16.0

# Python et cache uv hors du dossier personnel, lisibles par l'utilisateur non root de la base (node).
ENV UV_PYTHON_INSTALL_DIR=/opt/uv/python \
    UV_CACHE_DIR=/opt/uv/cache \
    UV_LINK_MODE=copy \
    UV_NO_PROGRESS=1
RUN mkdir -p /opt/uv /opt/ci && chown node:node /opt/uv /opt/ci

USER node
WORKDIR /opt/ci
# Python à la version de .python-version (lue par uv dans le dossier courant).
COPY --chown=node:node .python-version ./
RUN uv python install

USER root
# Sans cache, et /opt/uv rendu à node : lancé en root, uv python find écrivait dans /opt/uv/cache des fichiers que node ne pouvait
# plus modifier (« Permission denied » à l'étape suivante, premier up du 2026-10-20).
RUN ln -s "$(cd /opt/ci && UV_NO_CACHE=1 uv python find)" /usr/local/bin/python3 && chown -R node:node /opt/uv
# R-20261109-04 : les crochets lancent /Library/Developer/CommandLineTools/usr/bin/python3 -IS (R-20261108-10), chemin du Mac absent de cette
# image ; les tests du train copient le vrai crochet dans leurs dépôts jetables. Le lien n'existe que dans l'image, vers le même Python que
# /usr/local/bin/python3 ; aucun repli par PATH ni par variable. Remplace : rien. Retrait : permanent, tant que les crochets lancent cet interpréteur.
RUN mkdir -p /Library/Developer/CommandLineTools/usr/bin && ln -s "$(readlink -f /usr/local/bin/python3)" /Library/Developer/CommandLineTools/usr/bin/python3

USER node
# Dépendances résolues dans le cache de l'image (le passage est hors ligne) : celles du lanceur (DEPS de tests/run_all.sh) et les
# en-têtes PEP 723 des scripts que les suites lancent par uv run (tâche 2.2 : `uv sync --script`, qui installe sans lancer).
COPY --chown=node:node . /opt/ci/prep/
RUN cd /opt/ci/prep \
 && deps=$(sed -n 's/^DEPS="\${RUN_ALL_DEPS-\(.*\)}"$/\1/p' tests/run_all.sh) \
 && test -n "$deps" \
 && eval "uv run --no-project $deps python -c 0" \
 && for script in $(grep -rl --include='*.py' '^# /// script' tools tests .claude/skills); do \
      uv sync --script "$script" || exit 1; \
    done \
 && rm -rf /opt/ci/prep

# Dépendances npm (design D10) : une couche `npm ci` par suite npm déclarée par la ligne SUITES_NPM de tests/run_all.sh (aujourd'hui : mothra),
# faite à la construction, avec réseau. Le passage (`run`) extrait l'archive git dans $HOME/depot SANS node_modules : tools/ci_local.sh y copie
# /opt/ci/npm/<dossier>/node_modules avant de lancer les suites (jamais d'installation au passage). Seuls les manifestes sont copiés, un COPY
# ciblé chacun (package.json et package-lock.json de la racine, .npmrc s'il existe, .node-version, package.json de contract/, server/ et front/) :
# aucune source de mothra/ n'entre dans l'image. La version de Node de l'image doit être celle de <dossier>/.node-version : la construction
# s'arrête sinon (la ligne FROM ci-dessus ne peut pas lire ce fichier).
COPY --chown=node:node mothra/package.json mothra/package-lock.json mothra/.node-version mothra/.npmr[c] /opt/ci/npm/mothra/
COPY --chown=node:node mothra/contract/package.json /opt/ci/npm/mothra/contract/
COPY --chown=node:node mothra/server/package.json /opt/ci/npm/mothra/server/
COPY --chown=node:node mothra/front/package.json /opt/ci/npm/mothra/front/
# npm de l'image (R-20261104-67, C2 (a)) : l'image Node fournit la version exigée par engines.npm de mothra/package.json (Node 26.13.0 livre
# npm 11.20.0) ; on la VÉRIFIE ici, LUE à la construction (jamais recopiée dans ce fichier : une seule source), sans rien installer ; la
# construction s'arrête bruyamment si le champ est absent ou si le npm de l'image diffère. Remplace : l'installation de npm@<engines.npm>
# (R-20261101-112), retirée parce que sa condition de retrait est remplie. Retrait : quand engines.npm disparaît.
RUN want=$(node -p "((require('/opt/ci/npm/mothra/package.json').engines || {}).npm) || ''") \
 && { test -n "$want" || { echo "ci/Dockerfile : engines.npm absent de mothra/package.json, construction arrêtée" >&2; exit 1; }; } \
 && { test "$(npm --version)" = "$want" || { echo "ci/Dockerfile : npm de l'image $(npm --version), engines.npm $want : construction arrêtée" >&2; exit 1; }; }
RUN dest=/opt/ci/npm/mothra \
 && test "$(node --version)" = "v$(tr -d '[:space:]' < "$dest/.node-version")" \
 && cd "$dest" \
 && npm ci

# Chromium de Playwright pour la phase e2e (change ci-local-runner, tranche 2, tâche 9.3 ; R-20261101-113). Le navigateur est celui de la version de
# @playwright/test du verrou de mothra (une seule source : mothra/package-lock.json, qui entre déjà dans la clé de l'image), installé par la CLI
# Playwright du node_modules de l'image : jamais npx, jamais une version libre. Les dépendances système (bibliothèques et polices) sont installées en
# root par la même CLI (install-deps) ; le navigateur va dans PLAYWRIGHT_BROWSERS_PATH, hors du dossier personnel, lisible par l'utilisateur node.
# Le passage, sans réseau, ne télécharge rien : ci/passage.sh refuse la phase e2e (« navigateur absent de l'image ») si ce dossier n'a pas de chromium*.
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/ci/ms-playwright
USER root
RUN cd /opt/ci/npm/mothra \
 && ./node_modules/.bin/playwright install-deps chromium \
 && rm -rf /var/lib/apt/lists/*
USER node
RUN cd /opt/ci/npm/mothra \
 && ./node_modules/.bin/playwright install chromium \
 && test -n "$(find "$PLAYWRIGHT_BROWSERS_PATH" -maxdepth 1 -name 'chromium*' | head -1)"

WORKDIR /home/node
