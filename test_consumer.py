from kafka import KafkaConsumer
import json

consumer = KafkaConsumer(
    'ticks',
    bootstrap_servers='localhost:9092',
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    auto_offset_reset='earliest',
    group_id='test-group'
)

print("Listening for messages...")
for message in consumer:
    print(f"Received: {message}")