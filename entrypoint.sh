#!/usr/bin/env bash

set -o errexit
set -o pipefail
set -o nounset


cmd="$@"

sleep 5

>&2 echo "Neo4j is up - continuing..."
exec $cmd

