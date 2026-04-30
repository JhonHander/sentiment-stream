FROM python:3.12-slim

# Install Java 21 required by PySpark + wget for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-21-jdk wget && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
ENV PATH="${JAVA_HOME}/bin:${PATH}"

WORKDIR /app

# Install Python dependencies (PySpark 4.0.2 includes full Spark distribution)
COPY spark/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application code and data
COPY spark/ /app/spark/
COPY data/ /app/data/

# Environment defaults
ENV PYTHONUNBUFFERED=1
ENV SPARK_HOME=/usr/local/lib/python3.12/site-packages/pyspark
# Symlink Spark jars to where spark-class expects them
RUN mkdir -p /usr/local/assembly/target/scala-2.12 && \
    ln -s /usr/local/lib/python3.12/site-packages/pyspark/jars /usr/local/assembly/target/scala-2.12/jars
ENV MONGO_URI=mongodb://mongodb:27017/sentiment_stream
ENV CSV_PATH=/app/data/dataset_sentimientos_500.csv
ENV MODEL_PATH=/app/model

# Ensure model directory is writable
RUN mkdir -p /app/model

# No CMD — command is set in docker-compose.yml
# Master: spark-class org.apache.spark.deploy.master.Master
# Worker: spark-class org.apache.spark.deploy.worker.Worker spark://spark-master:7077
# Train:  python -m spark.train
