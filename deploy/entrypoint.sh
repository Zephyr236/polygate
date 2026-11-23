#!/bin/sh
# Ensure the data directory exists for the non-root runtime user.
set -eu
mkdir -p "${POLYGATE_DATABASE%/*}"
exec "$@"
