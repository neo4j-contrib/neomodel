#!/usr/bin/env bash

# This script allows to run the test suite against all supported Python
# interpreters and neo4j versions on a host that has Docker Compose and
# Docker client installed.
# The script aborts on the first failure of any combination.

clean () {
    docker-compose rm --stop --force -v neo4j
}

for dir in neomodel test; do
    rm -f ${dir}/**/*.pyc
    find ${dir} -name __pycache__ -exec rm -Rf {} \;
done
: "${NEO4J_VERSIONS:=4.4 4.3 4.1}"
: "${PYTHON_VERSIONS:=3.10 3.9 3.8 3.7}"
for NEO4J_VERSION in ${NEO4J_VERSIONS}; do
    for PYTHON_VERSION in ${PYTHON_VERSIONS}; do
        export NEO4J_VERSION
        export PYTHON_VERSION
        docker-compose up -d neo4j
        docker-compose up  --abort-on-container-exit --exit-code-from tests
        RESULT=$?
        if [ ${RESULT} != "0" ]; then
            echo "Tests with Python ${PYTHON_VERSION} against neo4j ${NEO4J_VERSION} failed. Stopping."
            clean
            exit ${RESULT}
        fi
        clean
    done
done

exit 0
