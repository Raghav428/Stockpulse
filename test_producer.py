from kafka import KafkaProducer
import json, time

producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)


for i in range(5):
    tick = {
        'symbol' : 'AAPL',
        'open' : 140 + i,
        'high' : 145 + i,
        'low' : 138 + i,
        'close' : 141 + i,
        'volume' : 100000 + 4057 * i,
        'timestamp' : time.time()
    }

    producer.send(
        topic = 'ticks',
        key = tick['symbol'].encode('utf-8'),
        value=tick
    )

    print(f"Sent: {tick}")
    time.sleep(1)


producer.flush()
producer.close()