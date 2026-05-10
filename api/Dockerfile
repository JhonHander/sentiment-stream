FROM python:3.11-slim

# Install OpenJDK 21 requerido por PySpark
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-21-jdk wget && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
ENV PATH="${JAVA_HOME}/bin:${PATH}"

WORKDIR /app

COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ ./api/
COPY tests/ ./tests/
COPY pyproject.toml .flake8 .

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
