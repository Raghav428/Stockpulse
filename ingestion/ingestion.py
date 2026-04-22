from kafka import KafkaProducer
import json
import websocket

symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
streams = ('@trade/'.join(symbols) + '@trade').lower()
url = f"wss://stream.binance.com:9443/stream?streams={streams}"

producer = KafkaProducer(
    bootstrap_servers='kafka:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

def on_message(ws, message):
    data = json.loads(message)
    symbol, price, quantity, timestamp = data['data']['s'],data['data']   ['p'],data['data']['q'],data['data']['T']
    tick_data = {'symbol':symbol,     'price':price,'quantity':quantity,'timestamp':timestamp}
    print(tick_data)
    producer.send('ticks',tick_data)

ws = websocket.WebSocketApp(url,on_message=on_message)

ws.run_forever()
