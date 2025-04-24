docker exec -it cass_cluster bash

cqlsh 127.0.0.1 -u cassandra -p cassandra

DESCRIBE KEYSPACES;
