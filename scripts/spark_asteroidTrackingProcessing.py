import math
import random
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

# -------------------- 4. UDFs de enriquecimiento ----------
AU_TO_KM = 149_597_870.7
G        = 6.67430e-11      # m³ kg⁻¹ s⁻²

@F.udf(
    returnType=T.StructType([
        T.StructField("x", T.DoubleType()),
        T.StructField("y", T.DoubleType()),
        T.StructField("z", T.DoubleType())
    ])
)
def ra_dec_to_cartesian(ra_hours, dec_deg, distance_km=1e6):
    import math
    ra_rad  = math.radians(ra_hours * 15)
    dec_rad = math.radians(dec_deg)
    x = distance_km * math.cos(dec_rad) * math.cos(ra_rad)
    y = distance_km * math.cos(dec_rad) * math.sin(ra_rad)
    z = distance_km * math.sin(dec_rad)
    return (round(x, 3), round(y, 3), round(z, 3))

# Enriquecimiento columna a columna para facilitar depuración
enriched_df = (raw_df
    # Coordenadas cartesianas
    .withColumn("cartesian_coords_km",
                ra_dec_to_cartesian(F.col("celestial_coords.ra_hours"),
                                    F.col("celestial_coords.dec_degrees")))
    # Propiedades físicas y orbitales
    .withColumn("radius",  F.col("diameter_m") / 2)
    .withColumn("density_kg_m3",      F.round(F.rand() * 2000 + 1000, 2))
    .withColumn("volume_m3",          (4/3)*math.pi*F.pow("radius", 3))
    .withColumn("surface_area_m2",    4*math.pi*F.pow("radius", 2))
    .withColumn("mass_kg",            F.col("volume_m3") * F.col("density_kg_m3"))
    .withColumn("escape_velocity_m_s",
                F.sqrt((2 * G * F.col("mass_kg")) / (F.col("radius"))))  # r en m, ok
    .withColumn("min_distance_au",    F.round(F.rand() * 0.4999 + 0.0001, 6))
    .withColumn("semi_major_axis_m",  F.col("min_distance_au") * AU_TO_KM * 1000)
    .withColumn("eccentricity",       F.round(F.rand(), 6))
    .withColumn("orbital_period_sec",
                2 * math.pi *
                F.sqrt(F.pow("semi_major_axis_m", 3) / (G * F.col("mass_kg"))))
    .withColumn("orbital_period_days",  F.col("orbital_period_sec") / 86400)
    .withColumn("impact_probability",   F.round(F.rand() * 0.049999 + 0.000001, 6))
    .withColumn("inclination_degrees",  F.round(F.rand() * 180, 2))
    # Derivadas
    .withColumn("periapsis_m",
                F.round(F.col("semi_major_axis_m") *
                        (1 - F.col("eccentricity")), 2))
    .withColumn("semi_minor_axis_m",
                F.round(F.col("semi_major_axis_m") *
                        F.sqrt(1 - F.pow("eccentricity", 2)), 2))
    .withColumn("orbital_period_years",
                F.round(F.col("orbital_period_days") / 365.25, 2))
    # Clasificación amenaza
    .withColumn("threat_level",
                F.when(F.col("impact_probability") > 0.01,  "ALTO")
                 .when(F.col("impact_probability") > 0.001, "MEDIO")
                 .otherwise("BAJO"))
    .drop("radius", "orbital_period_sec")      # columnas intermedias
)

# -------------------- 5. Escritura en Kafka ---------------
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
    .option("checkpointLocation", "hdfs://cluster-bda:9000/bda/kafka/AsteroidTracking/checkpoints/asteroid-stream")
    .outputMode("append")
    .start())

query.awaitTermination()
