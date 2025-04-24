import os
import json
import uuid
import logging
import sys
from confluent_kafka import Consumer, KafkaException, KafkaError
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
from cassandra.query import SimpleStatement, PreparedStatement

REDPANDA_BROKERS = os.getenv('REDPANDA_BROKERS', 'localhost:19092,localhost:29092,localhost:39092')
REDPANDA_TOPIC = os.getenv('REDPANDA_TOPIC', 'entity-graph')
REDPANDA_GROUP_ID = os.getenv('REDPANDA_GROUP_ID', 'entity-payload-processor-group-v2')
REDPANDA_USER = os.getenv('REDPANDA_USER', 'superuser')
REDPANDA_PASS = os.getenv('REDPANDA_PASS', 'secretpassword')

CASSANDRA_CONTACT_POINTS = os.getenv('CASSANDRA_CONTACT_POINTS', 'localhost').split(',')
CASSANDRA_PORT = int(os.getenv('CASSANDRA_PORT', '9042'))
CASSANDRA_KEYSPACE = os.getenv('CASSANDRA_KEYSPACE', 'entity_graph')
CASSANDRA_TABLE = os.getenv('CASSANDRA_TABLE', 'entity_payloads')
CASSANDRA_USER = "cassandra"
CASSANDRA_PASS = "cassandra"


logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def process_messages():
    """Connects to Redpanda, processes messages, and writes to Cassandra."""

    kafka_conf = {
        'bootstrap.servers': REDPANDA_BROKERS,
        'group.id': REDPANDA_GROUP_ID,
        'auto.offset.reset': 'earliest',  # Start from the beginning of the topic
        # 'security.protocol': 'SASL_PLAINTEXT', # Use SASL_SSL if TLS is enabled
        # 'sasl.mechanism': 'SCRAM-SHA-256',     # Or SCRAM-SHA-512 if configured
        # 'sasl.username': REDPANDA_USER,
        # 'sasl.password': REDPANDA_PASS,
        'session.timeout.ms': 45000,
    }
    try:
        consumer = Consumer(kafka_conf)
        consumer.subscribe([REDPANDA_TOPIC])
        logger.info(f"Subscribed to Redpanda topic: {REDPANDA_TOPIC} with group: {REDPANDA_GROUP_ID} on brokers: {REDPANDA_BROKERS}")
    except KafkaException as e:
        logger.error(f"Failed to create Kafka consumer or subscribe: {e}")
        sys.exit(1)

    auth_provider = None
    if CASSANDRA_USER and CASSANDRA_PASS:
        auth_provider = PlainTextAuthProvider(CASSANDRA_USER, CASSANDRA_PASS)

    try:
        cluster = Cluster(
            contact_points=CASSANDRA_CONTACT_POINTS,
            port=CASSANDRA_PORT,
            auth_provider=auth_provider # Pass the auth_provider if uncommented above
        )
        session = cluster.connect()
        logger.info(f"Attempting to connect to Cassandra cluster at {CASSANDRA_CONTACT_POINTS}:{CASSANDRA_PORT}")
        # The actual connection happens lazily or here. Log success *after* connect.
        # A simple query can force connection if not already established
        session.execute("SELECT release_version FROM system.local")
        logger.info(f"Successfully connected to Cassandra cluster.")

    except Exception as e:
         logger.error(f"Failed to connect to Cassandra cluster at {CASSANDRA_CONTACT_POINTS}:{CASSANDRA_PORT}. Error: {e}")
         # Attempt to shutdown cluster even if connect failed partially
         try:
             if 'cluster' in locals() and cluster:
                 cluster.shutdown()
         except Exception as shutdown_e:
             logger.error(f"Error during Cassandra cluster shutdown after connection failure: {shutdown_e}")
         sys.exit(1)

    # Set keyspace (important!)
    try:
        logger.info(f"Setting Cassandra keyspace to: {CASSANDRA_KEYSPACE}")
        session.set_keyspace(CASSANDRA_KEYSPACE)
        logger.info(f"Successfully set Cassandra keyspace: {CASSANDRA_KEYSPACE}")
    except Exception as e:
        logger.error(f"Failed to set Cassandra keyspace '{CASSANDRA_KEYSPACE}': {e}")
        logger.error("Ensure the keyspace exists and the Cassandra node is fully initialized.")
        cluster.shutdown()
        sys.exit(1)

    try:
        # Updated INSERT statement for the new table/schema
        insert_query = f"""
        INSERT INTO {CASSANDRA_TABLE} (entity_id, po_box, postcode)
        VALUES (?, ?, ?)
        """

        prepared_statement = session.prepare(insert_query)
        logger.info(f"Prepared Cassandra statement for table: {CASSANDRA_TABLE}")
    except Exception as e:
        logger.error(f"Failed to prepare Cassandra statement: {e}")
        logger.error(f"Ensure table '{CASSANDRA_TABLE}' exists in keyspace '{CASSANDRA_KEYSPACE}' with the correct schema (columns matching entity_id UUID, po_box TEXT, postcode TEXT).")
        cluster.shutdown()
        sys.exit(1)

    try:
        while True:
            msg = consumer.poll(timeout=1.0)  # Poll for messages

            if msg is None:
                continue  # No message received within timeout

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    logger.info(f'Reached end of partition {msg.topic()} [{msg.partition()}] at offset {msg.offset()}')
                elif msg.error():
                    logger.error(f"Kafka error: {msg.error()}")
                    # Don't raise here, let the loop continue to process other messages
                continue # Continue to the next message if there was a Kafka error

            # --- Process Valid Message ---
            try:
                # 1. Decode message value (assuming UTF-8 encoded JSON payload directly)
                raw_value_str = msg.value().decode('utf-8')

                # 2. Parse the JSON payload directly from the message value
                try:
                    # CORRECTED: Parse the payload directly, not nested
                    payload_data = json.loads(raw_value_str)
                    logger.debug(f"Successfully parsed JSON payload. Offset: {msg.offset()}, Data: {payload_data}") # Optional debug log
                except json.JSONDecodeError:
                    logger.error(f"Failed to decode JSON payload. Offset: {msg.offset()}, Raw Value: {raw_value_str[:200]}...") # Log snippet
                    continue # Skip this message if JSON is invalid

                # 3. Extract fields from the payload data
                # The structure seems to be {'meta': {...}, 'data': {...}}
                actual_data = payload_data.get('data', {}) # Get the 'data' dictionary
                if not actual_data:
                     logger.warning(f"Skipping message - 'data' field missing or empty in payload JSON. Offset: {msg.offset()}, Payload Data: {payload_data}")
                     continue # Skip if 'data' is missing/empty

                # Extract fields from the 'data' dictionary
                entity_uuid_str = actual_data.get('entity')
                po_box = actual_data.get('poBox')
                postcode = actual_data.get('postcode')


                # Basic validation: 'entity' is required as it's the primary key
                if not entity_uuid_str:
                     logger.warning(f"Skipping message - 'entity' UUID missing in payload 'data'. Offset: {msg.offset()}, Data: {actual_data}")
                     continue

                # 4. Convert entity UUID string to Python standard UUID type
                try:
                    entity_uuid = uuid.UUID(entity_uuid_str)
                except ValueError:
                    logger.error(f"Invalid UUID format for 'entity': '{entity_uuid_str}'. Offset: {msg.offset()}, Data: {actual_data}")
                    continue # Skip this message

                # 5. Bind data to prepared statement
                # Ensure the order matches the VALUES clause (entity_id, po_box, postcode)
                bound_statement = prepared_statement.bind([
                    entity_uuid, # Bind the standard uuid.UUID object
                    po_box,      # Can be None if missing
                    postcode     # Can be None if missing
                ])

                # 6. Execute statement
                session.execute(bound_statement)
                logger.info(f"Processed and inserted/updated message. Offset: {msg.offset()}, Entity ID: {entity_uuid}")

            except UnicodeDecodeError:
                 logger.error(f"Failed to decode raw message value as UTF-8. Offset: {msg.offset()}, Raw Value: {msg.value()[:100]}...")
                 # Continue processing other messages
            except Exception as e:
                # Catch any other unexpected errors during processing/writing
                logger.exception(f"Error processing message or writing to Cassandra. Offset: {msg.offset()}. Error: {e}", exc_info=True)
                # Log and continue polling.

    except KeyboardInterrupt:
        logger.info("Processing interrupted by user.")
    except KafkaException as e:
        # This catches errors raised explicitly or by librdkafka during poll
        logger.error(f"Critical Kafka error during poll loop: {e}. Shutting down.")
    except Exception as e:
        logger.exception(f"An unexpected error occurred in the main loop: {e}", exc_info=True)
    finally:
        # Clean up connections
        logger.info("Closing Kafka consumer...")
        if 'consumer' in locals() and consumer:
            consumer.close()
        logger.info("Closing Cassandra connection...")
        if 'cluster' in locals() and cluster:
            cluster.shutdown()
        logger.info("Shutdown complete.")

if __name__ == "__main__":
    process_messages()