# Enviroment Setup

## Quine

Recipe: https://quine.io/recipes/entity-resolution/

```
cd installations/quine && ./start.sh
```

Connect at http://127.0.0.1:8080.

## Cassandra

```
cd installations/cassandra && ./start.sh
```

## Start Redpanda

```bash
# Hint: https://docs.redpanda.com/current/get-started/quick-start/

cd insallations/redpanda
docker compose up -d
```

- Username
  - `superuser`
- Password
  - `secretpassword`

# Set up Keyspace


```bash
docker exec -it cass_cluster cqlsh

CREATE KEYSPACE entity_graph WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1};

USE entity_graph;

CREATE TABLE processed_addresses (
    address_id uuid PRIMARY KEY,  -- Generated unique ID for this address entry
    original_address text,      -- The raw, original address string
    addressee text,             -- The parsed addressee
    house_part text,            -- The parsed 'house' part (might be company name, etc.)
    po_box text,                -- The parsed 'poBox' part
    city text,                  -- The parsed city
    state text,                 -- The parsed state
    postcode text,              -- The parsed postcode (using text accommodates formats like 84409-0000)
    -- Optional: Add a timestamp for when it was processed/inserted
    -- processed_at timestamp
);

DESCRIBE TABLE processed_addresses;

```

# Feed data to redpanda topic

```bash
cd installations/quine

cat public-record-addresses-2021.ndjson | docker exec -i redpanda-0 \
  rpk topic produce entity-data \
  -X user=superuser \
  -X pass=secretpassword \
  -X sasl.mechanism=SCRAM-SHA-256 \
  -X brokers=redpanda-0:9092
```