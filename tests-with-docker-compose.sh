#!/usr/bin/env bash

# This script allows to run the test suite against all supported Python
# interpreters and neo4j versions on a host that has Docker Compose and
# Docker client installed.
# The script aborts on the first failure of any combination.
# It is not intended


write_compose_file () {
    cat > docker-compose.yml <<EOL
version: "3"

services:
  tests:
    image: "python:${PYTHON_VERSION}-alpine"
    volumes:
      - .:/src
      - pip-cache:/root/.cache/pip
    working_dir: /src
    command: sh -c "echo "http://mirror.leaseweb.com/alpine/edge/testing" >> /etc/apk/repositories; apk add --no-cache gcc libc-dev geos-dev; pip install shapely; while ! nc neo4j 7687; do  sleep 1; done; python -B setup.py test"
    links:
      - neo4j
    environment:
      NEO4J_BOLT_URL: bolt://neo4j:foobar@neo4j:7687
      NEO4J_VERSION: ${NEO4J_VERSION}
  neo4j:
    image: "neo4j:${NEO4J_VERSION}"
    environment:
      NEO4J_AUTH: none

volumes:
  pip-cache:
    driver: local
EOL
}


clean () {
    docker-compose rm --stop --force -v neo4j
    rm -f docker-compose.myl
}


for dir in neomodel test; do
    rm -f ${dir}/**/*.pyc
    find ${dir} -name __pycache__ -exec rm -Rf {} \;
done

for NEO4J_VERSION in 3.0 3.1 3.2 3.3 3.4 3.5; do
    for PYTHON_VERSION in 2.7 3.4 3.5 3.6; do
        write_compose_file
        docker-compose up -d neo4j
        docker-compose up tests
        RESULT=$?
        if [ ${RESULT} != "0" ]; then
            echo "Tests with Python ${PYTHON_VERSION} against neo4j ${NEO4J_VERSION} failed. Stopping."
            clean
            exit ${RESULT}
        fi
    done
    clean
done

exit 0
