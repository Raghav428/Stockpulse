from cassandra.cluster import Cluster

cluster = None
session = None

def connect_cassandra():
    global cluster, session
    cluster = Cluster(["my_cassandra"])
    session = cluster.connect()

    session.execute("""
CREATE KEYSPACE IF NOT EXISTS stockpulse
WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1}
""")
    session.set_keyspace("stockpulse")

    session.execute("""
    CREATE TABLE IF NOT EXISTS tick_data(
        symbol text,
        date text,
        ts timestamp,
        price double,
        volume int,
        PRIMARY KEY ((symbol, date), ts)
    )""")

def close_cassandra():
    cluster.shutdown()




