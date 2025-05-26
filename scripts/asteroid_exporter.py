from prometheus_client import start_http_server, Gauge
from hdfs import InsecureClient
import json
import time

# Conexión al NameNode vía WebHDFS
HDFS_URL = 'http://192.168.56.10:9870'  # Cambia si tu puerto o IP es diferente
HDFS_PATH = '/bda/kafka/AsteroidTracking'
HDFS_USER = 'victor11'

client = InsecureClient(HDFS_URL, user=HDFS_USER)

# --- gauge agregados ---
asteroid_total            = Gauge("asteroid_total", "Número total de asteroides")
asteroid_threat_high      = Gauge("asteroid_threat_high_total", "Amenazas ALTO")
asteroid_threat_medium    = Gauge("asteroid_threat_medium_total", "Amenazas MEDIO")
asteroid_threat_low       = Gauge("asteroid_threat_low_total", "Amenazas BAJO")

# --- gauges por-asteroide (label object_id, threat_level) ---
mass_g      = Gauge("asteroid_mass_kg",              "Masa",              ["object_id", "threat_level"])
density_g   = Gauge("asteroid_density_kg_m3",        "Densidad",          ["object_id", "threat_level"])
distance_g  = Gauge("asteroid_min_distance_au",      "Distancia mínima",  ["object_id", "threat_level"])
impact_g    = Gauge("asteroid_impact_probability",   "Impact prob.",      ["object_id", "threat_level"])
period_g    = Gauge("asteroid_orbital_period_days",  "Periodo orbital",   ["object_id", "threat_level"])


# =================== FUNCIONES ===================

def list_jsons(path):
    out = []
    for name, meta in client.list(path, status=True):
        full = f"{path.rstrip('/')}/{name}"
        if meta['type'] == 'DIRECTORY':
            out.extend(list_jsons(full))
        elif full.endswith('.json'):
            out.append(full)
    return out

# --- lectura, actualización de métricas ---
def update_metrics():
    threat_cnt = {"ALTO": 0, "MEDIO": 0, "BAJO": 0}
    total = 0

    for fpath in list_jsons(HDFS_PATH):
        with client.read(fpath, encoding='utf-8') as reader:
            for line in reader:
                try:
                    d = json.loads(line)
                except:          # línea corrupta
                    continue

                oid   = d["object_id"]
                level = d.get("threat_level", "BAJO")
                total += 1
                threat_cnt[level] += 1

                mass_g     .labels(oid, level).set(d.get("mass_kg", 0))
                density_g  .labels(oid, level).set(d.get("density_kg_m3", 0))
                distance_g .labels(oid, level).set(d.get("min_distance_au", 0))
                impact_g   .labels(oid, level).set(d.get("impact_probability", 0))
                period_g   .labels(oid, level).set(d.get("orbital_period_days", 0))

    asteroid_total        .set(total)
    asteroid_threat_high  .set(threat_cnt["ALTO"])
    asteroid_threat_medium.set(threat_cnt["MEDIO"])
    asteroid_threat_low   .set(threat_cnt["BAJO"])

# --- loop exporter ---
if __name__ == "__main__":
    start_http_server(9091)
    print("Exporter listo en :9091/metrics")
    while True:
        update_metrics()
        time.sleep(30)
