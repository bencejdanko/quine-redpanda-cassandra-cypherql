import os
import json
import uuid
import logging
import sys
from confluent_kafka import Consumer, KafkaException, KafkaError
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
from cassandra.query import SimpleStatement, PreparedStatement

# --- Configuration ---
# Use environment variables or default values suitable for running OUTSIDE Docker
# If running INSIDE a Docker container on the same network, use container names.

# Corrected Redpanda Brokers for host access
REDPANDA_BROKERS = os.getenv('REDPANDA_BROKERS', 'localhost:19092,localhost:29092,localhost:39092')
REDPANDA_TOPIC = os.getenv('REDPANDA_TOPIC', 'entity-graph')
REDPANDA_GROUP_ID = os.getenv('REDPANDA_GROUP_ID', 'address-processor-group')
REDPANDA_USER = os.getenv('REDPANDA_USER', 'superuser') # Default user for many Redpanda examples
REDPANDA_PASS = os.getenv('REDPANDA_PASS', 'secretpassword') # Default password for many Redpanda examples

# Corrected Cassandra Contact Point for host access
CASSANDRA_CONTACT_POINTS = os.getenv('CASSANDRA_CONTACT_POINTS', 'localhost').split(',') # Use localhost for host access
CASSANDRA_PORT = int(os.getenv('CASSANDRA_PORT', '9042')) # Default Cassandra port
CASSANDRA_KEYSPACE = os.getenv('CASSANDRA_KEYSPACE', 'entity_graph')
CASSANDRA_TABLE = os.getenv('CASSANDRA_TABLE', 'processed_addresses')
# Optional Cassandra Auth (if configured on your Cassandra instance)
# CASSANDRA_USER = os.getenv('CASSANDRA_USER')
# CASSANDRA_PASS = os.getenv('CASSANDRA_PASS')

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# --- Main Processing Logic ---
def process_messages():
    """Connects to Redpanda, processes messages, and writes to Cassandra."""

    # --- Configure Kafka Consumer ---
    kafka_conf = {
        'bootstrap.servers': REDPANDA_BROKERS,
        'group.id': REDPANDA_GROUP_ID,
        'auto.offset.reset': 'earliest',  # Start from the beginning of the topic
        # Security settings (Ensure these match your Redpanda setup)
        'security.protocol': 'SASL_PLAINTEXT', # Use SASL_SSL if TLS is enabled
        'sasl.mechanism': 'SCRAM-SHA-256',     # Or SCRAM-SHA-512 if configured
        'sasl.username': REDPANDA_USER,
        'sasl.password': REDPANDA_PASS,
        # Increase session timeout for stability if needed, especially during debugging
        'session.timeout.ms': 45000,
        # Add debug logging from librdkafka if needed
        # 'debug': 'all',
    }
    try:
        consumer = Consumer(kafka_conf)
        consumer.subscribe([REDPANDA_TOPIC])
        logger.info(f"Subscribed to Redpanda topic: {REDPANDA_TOPIC} with group: {REDPANDA_GROUP_ID} on brokers: {REDPANDA_BROKERS}")
    except KafkaException as e:
        logger.error(f"Failed to create Kafka consumer or subscribe: {e}")
        sys.exit(1)


    # --- Configure Cassandra Connection ---
    # auth_provider = None
    # if CASSANDRA_USER and CASSANDRA_PASS:
    #     auth_provider = PlainTextAuthProvider(username=CASSANDRA_USER, password=CASSANDRA_PASS)

    try:
        cluster = Cluster(
            contact_points=CASSANDRA_CONTACT_POINTS,
            port=CASSANDRA_PORT,
            # auth_provider=auth_provider
        )
        session = cluster.connect()
        logger.info(f"Attempting to connect to Cassandra cluster at {CASSANDRA_CONTACT_POINTS}:{CASSANDRA_PORT}")
        # The actual connection happens lazily or here. Log success *after* connect.
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


    # --- Prepare Cassandra Statement ---
    # Using an UPSERT (UPDATE) statement. Since address_id is always new (uuid4), this acts like an INSERT.
    try:
        insert_query = f"""
        INSERT INTO {CASSANDRA_TABLE} (address_id, original_address, addressee, house_part, po_box, city, state, postcode)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        # Note: Changed to INSERT for clarity, as UPDATE with a new UUID PK is functionally an INSERT.
        # If you intended to truly UPDATE based on address_id, you'd need a way to get an *existing* address_id.

        prepared_statement = session.prepare(insert_query)
        logger.info(f"Prepared Cassandra statement for table: {CASSANDRA_TABLE}")
    except Exception as e:
        logger.error(f"Failed to prepare Cassandra statement: {e}")
        logger.error(f"Ensure table '{CASSANDRA_TABLE}' exists in keyspace '{CASSANDRA_KEYSPACE}' with the correct schema (columns matching the INSERT statement).")
        cluster.shutdown()
        sys.exit(1)


    # --- Processing Loop ---
    try:
        while True:
            msg = consumer.poll(timeout=1.0)  # Poll for messages

            if msg is None:
                continue  # No message received within timeout

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    # End of partition event - not an error
                    logger.info(f'Reached end of partition {msg.topic()} [{msg.partition()}] at offset {msg.offset()}')
                elif msg.error():
                    # Treat other Kafka errors as potentially critical
                    logger.error(f"Kafka error: {msg.error()}")
                    raise KafkaException(msg.error()) # Raise to potentially stop processing
                continue # Continue if it wasn't _PARTITION_EOF but also not raised

            # --- Process Valid Message ---
            try:
                # 1. Decode message value (assuming UTF-8 encoded JSON)
                message_value_str = msg.value().decode('utf-8')
                # 2. Parse JSON
                data = json.loads(message_value_str)

                # 3. Generate unique ID for this processed record
                address_id = uuid.uuid4() # Generate a new UUID for each record

                # 4. Extract fields (handle potential missing keys gracefully)
                original_address = data.get('original') # Assuming 'original' field exists in your JSON
                addressee = data.get('addressee')
                parts = data.get('parts', {}) # Default to empty dict if 'parts' is missing
                house_part = parts.get('house')
                po_box = parts.get('poBox') # Note CamelCase from JSON
                city = parts.get('city')
                state = parts.get('state')
                postcode = parts.get('postcode')

                # Basic validation (adjust as needed)
                # Example: Ensure at least some core parts exist
                if not original_address or not city or not state:
                     logger.warning(f"Skipping message - missing essential fields (original_address, city, or state). Offset: {msg.offset()}, Data: {data}")
                     continue

                # 5. Bind data to prepared statement
                # Ensure the order matches the VALUES clause in the prepared statement
                bound_statement = prepared_statement.bind([
                    address_id, # First value in VALUES clause
                    original_address,
                    addressee,
                    house_part,
                    po_box,
                    city,
                    state,
                    postcode
                ])

                # 6. Execute statement
                session.execute(bound_statement)
                logger.info(f"Processed and inserted message. Offset: {msg.offset()}, New Address ID: {address_id}")

            except json.JSONDecodeError:
                logger.error(f"Failed to decode JSON. Offset: {msg.offset()}, Raw Value: {msg.value()[:100]}...") # Log snippet
            except KeyError as e:
                logger.error(f"Missing expected key in data. Offset: {msg.offset()}, Key: {e}, Data: {data}")
            except UnicodeDecodeError:
                 logger.error(f"Failed to decode message value as UTF-8. Offset: {msg.offset()}, Raw Value: {msg.value()[:100]}...")
            except Exception as e:
                logger.exception(f"Error processing message or writing to Cassandra. Offset: {msg.offset()}. Error: {e}", exc_info=True)
                # Depending on the error, you might want to stop, or just log and continue.
                # For now, we log and continue polling.

    except KeyboardInterrupt:
        logger.info("Processing interrupted by user.")
    except KafkaException as e:
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