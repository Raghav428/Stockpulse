from kafka import KafkaProducer
import json
import websocket

symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
streams = ('@kline_1m/'.join(symbols) + '@kline_1m').lower()
url = f"wss://stream.binance.com:9443/stream?streams={streams}"

producer = KafkaProducer(
    bootstrap_servers='my_kafka:29092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

def on_message(ws, message):
    data = json.loads(message)
    kline = data['data']['k']
    
    tick_data = {
        'symbol': kline['s'],
        'open': float(kline['o']),
        'high': float(kline['h']),
        'low': float(kline['l']),
        'close': float(kline['c']),
        'volume': int(float(kline['v'])), # Volume can be fractional in Binance, cast to float then int
        'timestamp': kline['t'] / 1000.0 # Convert ms to seconds to align with test_producer
    }
    
    print("tick_data", tick_data)
    producer.send('ticks', tick_data)

ws = websocket.WebSocketApp(url, on_message=on_message)

ws.run_forever()
