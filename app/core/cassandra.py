from cassandra.cluster import Cluster
from cassandra.policies import DCAwareRoundRobinPolicy

# Connect to the Cassandra container (matches the service name in compose.yml)
cluster = Cluster(
    contact_points=["my_cassandra"],
    load_balancing_policy=DCAwareRoundRobinPolicy(local_dc="datacenter1"),
    protocol_version=5,
)

session = cluster.connect()

# Create the keyspace if it doesn't exist
session.execute("""
    CREATE KEYSPACE IF NOT EXISTS stockpulse
    WITH replication = {
        'class': 'SimpleStrategy',
        'replication_factor': 1
    }
""")

# Switch to that keyspace
session.set_keyspace("stockpulse")

# Create the tick_data table if it doesn't exist
# Partition key: (symbol, date) — keeps each symbol+day in one partition
# Clustering key: ts — sorts ticks within a partition by time
session.execute("""
    CREATE TABLE IF NOT EXISTS tick_data (
        symbol TEXT,
        date DATE,
        ts TIMESTAMP,
        price DOUBLE,
        volume BIGINT,
        PRIMARY KEY ((symbol, date), ts)
    ) WITH CLUSTERING ORDER BY (ts ASC)
""")


def get_cassandra_session():
    return session
