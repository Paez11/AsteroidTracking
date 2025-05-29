import json
import uuid
import time
from datetime import datetime
from faker import Faker
import numpy as np

fake = Faker()
PIPE_FILE = "neo_stream.pipe"

def generate_ra_dec():
    # Genera coordenadas celestiales aleatorias
    # RA: 0 a 24 horas, DEC: -90 a 90 grados
    ra = round(np.random.uniform(0, 24), 4)            # horas
    dec = round(np.random.uniform(-90, 90), 4)         # grados
    return ra, dec

def generate_observation():
    ra, dec = generate_ra_dec()
    diameter = round(np.random.uniform(10, 10000), 2)  # en metros
    brightness = round(np.random.uniform(10, 28), 2) # magnitud de brillo del objeto
    image_noise = round(np.random.normal(0.5, 0.1), 3) # ruido de la imagen

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "object_id": str(uuid.uuid4()),
        "celestial_coords": {
            "ra_hours": ra,
            "dec_degrees": dec
        },
        "diameter_m": diameter,
        "brightness_mag": brightness,
        "image_noise_level": image_noise
    }

def stream_to_pipe(n=500, delay=0.5):
    with open(PIPE_FILE, 'w') as pipe:
        for _ in range(n):
            obs = generate_observation()
            pipe.write(json.dumps(obs) + '\n')
            pipe.flush()
            time.sleep(delay)
    print("Generación completa.")

if __name__ == "__main__":
    stream_to_pipe(n=500, delay=0.5)