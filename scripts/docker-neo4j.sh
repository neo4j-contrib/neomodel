docker run \
    --name neo4j \
    -p7474:7474 -p7687:7687 \
    -d \
    --env NEO4J_AUTH=neo4j/foobarbaz \
    neo4j:$1