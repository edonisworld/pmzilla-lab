# Image de la CI locale de PMZilla Lab (change local-ci-container, design D4).
#
# Construite par `bash tools/ci_local.sh build` (ou `up`), par l'auteur seul, avec réseau, depuis l'arbre de HEAD (git archive) :
# aucun fichier ignoré ni local n'est dans le contexte. Le passage (`run`) n'a pas de réseau (UV_OFFLINE=1, --network none).
# Chaque élément épinglé a son entrée dans docs/pmzilla/composants.yaml (pinned_in: CI Dockerfile) ; tests/composants vérifie
# l'épinglage (étiquette et empreinte sha256 des images, version exacte de la CLI OpenSpec, Python de .python-version).
# Une valeur A_REMPLIR_PAR_L_AUTEUR est lue par l'auteur hors session (registre, docker pull) : tests/composants la nomme.
# Aucun secret, aucun ARG qui en porte un, aucun ADD depuis une adresse. Paquets système de la distribution de la base, non
# épinglés un à un (fiche Q2). La clé de l'image (hash de ce fichier, des entrées de l'inventaire, de .python-version, des
# dépendances du lanceur et des verrous npm déclarés) est posée par tools/ci_local.sh en étiquette et dans le tag.

# Base : image officielle Node, version exacte 26.12.0 (égale à celle de mothra/.node-version, design D4 de mothra-node-lts), variante slim,
# épinglée par l'empreinte de son index multi-architecture.
FROM node:26.12.0-slim@sha256:0d1e33586362bb9e608c4e751e7a9e7edb55c9ac11461ed5666af696cc461dd4

# Outils système des suites (inventaire de la tâche 2.1) : Git, Bash, Zsh, Perl (shasum, repli de durée), lsof, procps (ps, pgrep).
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates git bash zsh perl lsof procps \
 && rm -rf /var/lib/apt/lists/*

# uv copié de son image officielle ; étiquette = version d'uv du Mac de l'auteur (uv --version, 2026-10-20).
COPY --from=ghcr.io/astral-sh/uv:0.13.2@sha256:b9fddcde095a7aeafd499024adb8927df6619c7c5672f5ff7126474715f62ba4 /uv /uvx /usr/local/bin/

# CLI OpenSpec (suites de la voie légère et des lecteurs OpenSpec) ; version = openspec --version du Mac de l'auteur (2026-10-20).
RUN npm install -g @fission-ai/openspec@1.14.1

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

# Dépendances npm (design D10) : une couche `npm ci` par verrou déclaré par la liste npm du lanceur ; aujourd'hui aucun verrou
# déclaré, donc aucune couche npm.

WORKDIR /home/node
