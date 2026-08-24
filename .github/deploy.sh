#!/bin/bash
# =============================================================================
# gunlinux.ru — deploy the Rust container image from Docker Hub.
#
# Runs ON the server, invoked by .github/workflows/deploy.yaml over SSH with
# DEPLOY_TAG=<commit short SHA> exported. The image is built and pushed in CI
# (public repo gunlinuxloki/gunlinux.ru — no docker login needed here); this
# script pulls that exact tag, installs the systemd unit with the tag baked
# in, and restarts the service. Idempotent: safe to re-run.
#
# Replaces the pre-cutover script that built the binary on the server; the
# server no longer needs a Rust toolchain or a local docker build.
# =============================================================================
set -euo pipefail

REPO_DIR="/home/loki/youtube_consumer"
BRANCH="main"
IMAGE="gunlinuxloki/youtube_consumer"
NEW_UNIT="youtube_consumer"

cd "$REPO_DIR" || exit 1

TAG="${DEPLOY_TAG:?DEPLOY_TAG is required (commit short SHA)}"

# The server's git remote historically pointed at the wrong repo
# (gunlinux.org); enforce the real one so `git fetch` always pulls this repo.
git remote set-url origin git@github.com:gunlinux/youtube_consumer.git

# --- 1. Pull the deployed commit ----------------------------------------------
git fetch --all
git reset --hard "origin/$BRANCH"

# docker --env-file does NOT strip quotes (unlike systemd EnvironmentFile);
# normalize any remaining KEY="value" lines so the container gets clean env
# (a quoted DATABASE_URL made sqlx fail to parse the connection string).
sed -i -E 's/^([A-Z_]+)="(.*)"$/\1=\2/' .env || true

# --- 2. Install the unit with the commit-hash tag baked in --------------------
sed -e "s|@IMAGE_TAG@|$TAG|g" deploy/youtube_consumer.service \
    | sudo tee "/etc/systemd/system/$NEW_UNIT.service" >/dev/null
sudo systemctl daemon-reload

# --- 5. Swap services ---------------------------------------------------------
# Stop+disable the legacy Python app (`|| true`: idempotent — fine if it is
# already stopped/disabled on a re-run).
sudo systemctl enable --now "$NEW_UNIT"

# `enable --now` does not restart an already-active unit; restart explicitly
# when the running image differs from the deployed tag (idempotent no-op when
# the tag is unchanged).
CURRENT="$(docker inspect --format '{{.Config.Image}}' "$NEW_UNIT" 2>/dev/null || true)"
if [ "$CURRENT" != "$IMAGE:$TAG" ]; then
    sudo systemctl restart "$NEW_UNIT"
fi

echo "Deployment completed: $IMAGE:$TAG"
