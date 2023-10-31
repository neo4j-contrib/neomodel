if [[ "$1" == 4.4* ]]; then
    docker run \
        --name neo4j \
        -p7474:7474 -p7687:7687 \
        -d \
        --env NEO4J_AUTH=neo4j/foobarbaz \
        --env NEO4J_ACCEPT_LICENSE_AGREEMENT=yes \
        --env NEO4JLABS_PLUGINS='["apoc-4.4.0.23-all"]' \
        neo4j:$1
else
    docker run \
        --name neo4j \
        -p7474:7474 -p7687:7687 \
        -d \
        --env NEO4J_AUTH=neo4j/foobarbaz \
        --env NEO4J_ACCEPT_LICENSE_AGREEMENT=yes \
        --env NEO4JLABS_PLUGINS='["apoc"]' \        neo4j:$1

fi
