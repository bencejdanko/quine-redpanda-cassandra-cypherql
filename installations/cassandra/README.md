docker exec -it cass_cluster bash

cqlsh 127.0.0.1 -u cassandra -p cassandra

DESCRIBE KEYSPACES;

DESCRIBE TABLES;

SELECT * FROM entity_payloads LIMIT 5;