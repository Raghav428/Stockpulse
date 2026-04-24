from kafka import KafkaConsumer
import redis
from cassandra.cluster import Cluster
import datetime
import json


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
        open double,
        high double,
        low double,
        close double,
        volume int,
        PRIMARY KEY ((symbol, date), ts)
    )""")

connect_cassandra()

redis_client = redis.Redis(host='my_redis', port=6379)
consumer = KafkaConsumer(
    'ticks',
    bootstrap_servers='my_kafka:29092',
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    auto_offset_reset='earliest',
    group_id='debug-group'
)

for message in consumer:
    dt = datetime.datetime.fromtimestamp(message.value["timestamp"])
    session.execute("""
        INSERT INTO stockpulse.tick_data (symbol, date, ts, open, high, low, close, volume) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        message.value["symbol"], str(dt.date()), dt, 
        message.value["open"], message.value["high"], message.value["low"], 
        message.value["close"], message.value["volume"]))
    redis_client.set(message.value["symbol"], json.dumps(message.value))
