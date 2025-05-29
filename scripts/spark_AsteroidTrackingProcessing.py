import math
import random
import string
from pyspark.sql import SparkSession, functions as F, types as T

# -------------------- 1. Sesión Spark --------------------
spark = SparkSession.builder \
    .appName("AsteroidTrackingStreamingApp") \
    .config("spark.sql.shuffle.partitions", "4") \
    .getOrCreate()
spark.sparkContext.setLogLevel("WARN")

# -------------------- 2. Esquema RAW ---------------------
raw_schema = T.StructType([
    T.StructField("timestamp",    T.StringType(), True),
    T.StructField("object_id",    T.StringType(), True),
    T.StructField("celestial_coords", T.StructType([
        T.StructField("ra_hours",    T.DoubleType(), True),
        T.StructField("dec_degrees", T.DoubleType(), True)
    ])),
    T.StructField("diameter_m",        T.DoubleType(), True),
    T.StructField("brightness_mag",    T.DoubleType(), True),
    T.StructField("image_noise_level", T.DoubleType(), True)
])

# -------------------- 3. Lectura desde neo_raw_data ------
kafka_raw = (spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", "192.168.11.10:9094")
    .option("subscribe", "neo_raw_data")
    .option("startingOffsets", "earliest")
    .load())

raw_df = (kafka_raw
    .selectExpr("CAST(value AS STRING) as json")
    .select(F.from_json("json", raw_schema).alias("data"))
    .select("data.*"))     # columnas a nivel raíz

# --------------- 4. UDFs auxiliares -------------
@F.udf(returnType=T.StringType())
def make_designation(ts):
    """Convierte 2025-05-29T… → (2025 BY15) – reglas MPC simplificadas"""
    yr = ts[:4]
    first = random.choice(string.ascii_uppercase.replace('I','').replace('Z',''))
    second = random.choice(string.ascii_uppercase.replace('I',''))
    idx = random.randint(1, 99)
    return f"({yr} {first}{second}{idx:02d})"

@F.udf(returnType=T.ArrayType(raw_schema))
def replicate(row, n=5):
    """Replica la fila con pequeñas variaciones en RA/DEC para simular incerteza"""
    base = row.asDict(recursive=True)
    clones = []
    for _ in range(n):
        jitter_ra  = base['celestial_coords']['ra_hours']  + random.uniform(-0.01, 0.01)
        jitter_dec = base['celestial_coords']['dec_degrees'] + random.uniform(-0.01, 0.01)
        new_d = base.copy()
        new_d['celestial_coords'] = {
            'ra_hours':  jitter_ra,
            'dec_degrees': jitter_dec
        }
        clones.append(new_d)
    return clones

# --------------- 5. Pre-procesado ----------------
pre_df = (raw_df
          .withColumn("object_id", make_designation("timestamp"))
          .withColumn("replicated", F.explode(replicate(F.struct("*"))))
          .select("replicated.*"))

# -------------------- 6. UDFs y CONST de enriquecimiento ----------
AU_TO_KM = 149_597_870.7
AU_TO_M  = AU_TO_KM * 1000
G        = 6.67430e-11      # m³ kg⁻¹ s⁻²
DECAY_AU = 0.01             # escala de atenuación de probabilidad (~1,5 M km)

@F.udf(
    returnType=T.StructType([
        T.StructField("x", T.DoubleType()),
        T.StructField("y", T.DoubleType()),
        T.StructField("z", T.DoubleType())
    ])
)
def ra_dec_to_cartesian(ra_hours, dec_deg, distance_km=1e6):
    """Convierte coordenadas RA/DEC → cartesianas (km). Asume distancia fija 1e6 km si no hay parámetro específico."""
    ra_rad  = math.radians(ra_hours * 15)
    dec_rad = math.radians(dec_deg)
    x = distance_km * math.cos(dec_rad) * math.cos(ra_rad)
    y = distance_km * math.cos(dec_rad) * math.sin(ra_rad)
    z = distance_km * math.sin(dec_rad)
    return (round(x, 3), round(y, 3), round(z, 3))

# -------------------- 7. Enriquecimiento columna a columna --------------------
#    probabilidad de impacto determinista basada en distancias y órbita.

# 7.1 Coordenadas y distancia mínima
cartesian_df = (pre_df
    .withColumn("cartesian_coords_km",
                ra_dec_to_cartesian(F.col("celestial_coords.ra_hours"),
                                    F.col("celestial_coords.dec_degrees")))
    .withColumn("x_km", F.col("cartesian_coords_km.x"))
    .withColumn("y_km", F.col("cartesian_coords_km.y"))
    .withColumn("z_km", F.col("cartesian_coords_km.z"))
    .withColumn("min_distance_km",
                F.sqrt(F.pow("x_km", 2) + F.pow("y_km", 2) + F.pow("z_km", 2)))
    .withColumn("min_distance_au", F.col("min_distance_km") / F.lit(AU_TO_KM))
)

# 7.2 Propiedades físicas y orbitales básicas
phys_df = (cartesian_df
    .withColumn("radius_m", F.col("diameter_m") / 2)
    .withColumn("density_kg_m3", F.lit(2600))                 # densidad roca típica
    .withColumn("volume_m3", (4/3) * math.pi * F.pow("radius_m", 3))
    .withColumn("surface_area_m2", 4 * math.pi * F.pow("radius_m", 2))
    .withColumn("mass_kg", F.col("volume_m3") * F.col("density_kg_m3"))
    .withColumn("escape_velocity_m_s",
                F.sqrt(2 * F.lit(G) * F.col("mass_kg") / F.col("radius_m")))
    .withColumn("semi_major_axis_m", F.col("min_distance_au") * F.lit(AU_TO_M))
    .withColumn("eccentricity", F.round(F.lit(0.3), 6))       # placeholder fijo
    .withColumn("orbital_period_sec",
                2 * math.pi *
                F.sqrt(F.pow("semi_major_axis_m", 3) / (F.lit(G) * F.col("mass_kg"))))
    .withColumn("orbital_period_days", F.col("orbital_period_sec") / 86400)
    .withColumn("inclination_degrees", F.round(F.lit(10.0), 2))
)

# 7.3 Variables orbitales derivadas
orb_df = (phys_df
    .withColumn("periapsis_m", F.round(F.col("semi_major_axis_m") * (1 - F.col("eccentricity")), 2))
    .withColumn("apoapsis_m",  F.round(F.col("semi_major_axis_m") * (1 + F.col("eccentricity")), 2))
    .withColumn("orbital_period_years", F.round(F.col("orbital_period_days") / 365.25, 2))

    # Indicador de cruce con órbita terrestre (0,983–1,017 AU)
    .withColumn("crosses_earth_orbit",
                F.when((F.col("periapsis_m") < F.lit(AU_TO_M * 1.017)) &
                       (F.col("apoapsis_m")  > F.lit(AU_TO_M * 0.983)), 1).otherwise(0))

    # Factor de sincronía temporal Tierra-asteroide
    .withColumn("temporal_sync_factor",
                1 / F.greatest(F.lit(1.0), F.abs(F.col("orbital_period_days") - F.lit(365.25))))
)

# 7.4 Probabilidad de impacto determinista
risk_df = (orb_df
    .withColumn(
        "impact_probability",
        F.round(
            F.when(F.col("crosses_earth_orbit") == 1,
                    # (area proporcional) / (distancia² + amortiguador) × sincronía × 0,01
                    (F.pow(F.col("diameter_m") / 1000.0, 2) /
                     (F.pow(F.col("min_distance_au"), 2) + 0.1)) *
                    F.col("temporal_sync_factor") * 0.01)
             .otherwise(0.0),
            6))

    # Clasificación de amenaza
    .withColumn("threat_level",
                F.when(F.col("impact_probability") > 0.05,  "ALTO")
                 .when(F.col("impact_probability") > 0.01, "MEDIO")
                 .otherwise("BAJO"))
)

# 7.5 Limpieza de columnas intermedias
enriched_df = (risk_df
    .drop("radius_m", "orbital_period_sec", "temporal_sync_factor", "crosses_earth_orbit"))

# -------------------- 8. Escritura en Kafka ---------------
# Serializamos todo el registro enriquecido como JSON string
out_df = enriched_df \
    .withColumn("topic", F.lit("asteroid-events")) \
    .withColumn("date", F.to_date("timestamp")) \
    .withColumn("partition", F.spark_partition_id())  # partición lógica usada en Spark

query = (out_df
    .writeStream
    .format("json")
    .partitionBy("topic", "partition", "date")  # ← genera carpetas topic=..., partition=...
    .option("path", "hdfs://cluster-bda:9000/bda/kafka/AsteroidTracking")
    .outputMode("append")
    .start())

# -------------------- 9. Esperar a que termine el streaming
query.awaitTermination()