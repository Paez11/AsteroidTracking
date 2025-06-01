# ☄️ Asteroid Tracking

Este proyecto implementa un sistema completo de procesamiento en tiempo real para la detección y análisis de asteroides cercanos a la Tierra (NEOs), con cálculo físico y orbital avanzado, utilizando Apache Spark y Kafka.

---

## 🚀 Objetivo

Analizar flujos de datos astronómicos en tiempo real para:

- Estimar la probabilidad de impacto de asteroides
- Clasificar su nivel de amenaza (**BAJO**, **MEDIO**, **ALTO**)
- Generar datos enriquecidos exportables para ciencia, defensa o divulgación

---

## 🧠 Funcionalidades clave

- 📡 **Lectura desde Kafka**: ingesta continua de observaciones astronómicas simuladas.
- 🧮 **Conversión RA/DEC a coordenadas cartesianas**
- 🌌 **Cálculo de propiedades físicas**: masa, volumen, velocidad de escape, etc.
- 🛰️ **Cálculo de parámetros orbitales**: semieje mayor, excentricidad, periapsis, período, etc.
- ☢️ **Modelo determinista de riesgo de impacto**: basado en distancia mínima, sincronía orbital y cruce con la órbita terrestre.
- 📤 **Salida en HDFS en formato JSON** para visualización con Grafana o análisis externo.

---

## 📂 Estructura del proyecto

📁 /src
└── spark_AsteroidTrackingProcessing.py # Lógica de enriquecimiento y streaming
📁 /data
└── /output # Datos enriquecidos en HDFS

---

## 📊 Business Intelligence

- Seguimiento y clasificación de amenazas en tiempo real
- Estadísticas de riesgo acumulado y distribución de objetos por categoría
- Base para simulación de trayectorias y estudios científicos sobre NEOs

---

## 🧪 Aplicaciones científicas

- Análisis poblacional de asteroides
- Priorización de observación astronómica
- Simulación de incertidumbre observacional
- Entrenamiento de modelos predictivos

---

## ⚙️ Tecnologías usadas

- Apache Spark (Structured Streaming)
- Apache Kafka
- HDFS
- Python 3
- Grafana + Prometheus (para visualización de métricas)

---

## ✅ Requisitos previos

- Cluster con Spark, Kafka y HDFS funcionando
- Topics de Kafka configurados (ej. `neo_raw_data`)
- Habilitado `delete.topic.enable=true` en Kafka para reiniciar pruebas

---

## 📝 Licencia

MIT License © 2025 — *Desarrollado para análisis espacial y defensa planetaria*

---

## Video demostrativo

https://drive.google.com/file/d/13vKx5eSw3hLBqD2dmviFjOQSFpeHfB5I/view?usp=drive_link
