import json
from kafka import KafkaProducer

PIPE_FILE = "neo_stream.pipe"
TOPIC = "neo_raw_data"
KAFKA_BROKER = "192.168.11.10:9094"

producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKER,
    value_serializer=lambda v: json.dumps(v).encode("utf-8")
)

def stream_from_pipe():
    with open(PIPE_FILE, 'r') as pipe:
        for i, line in enumerate(pipe):
            try:
                observation = json.loads(line.strip())
                producer.send(TOPIC, observation)
                print(f"[{i+1}] Enviado {observation['object_id']}")
            except json.JSONDecodeError as e:
                print(f"Error decodificando JSON: {e}")

if __name__ == "__main__":
    stream_from_pipe()
