#!/bin/bash

FLINK_VERSION=1.15
ICEBERG_VERSION=1.2.0
SPARK_VERSION=3.3
PROJECT=$(/usr/share/google/get_metadata_value attributes/PROJECT)
DATAPROC_BUCKET=$(/usr/share/google/get_metadata_value attributes/DATAPROC_BUCKET)
WAREHOUSE_DIR=$(/usr/share/google/get_metadata_value attributes/WAREHOUSE_DIR)
CONNECTION=$(/usr/share/google/get_metadata_value attributes/CONNECTION)

# Install libraries required
apt install wget -y
cd /usr/lib/flink
wget -c https://repo1.maven.org/maven2/org/apache/iceberg/iceberg-flink-runtime-${FLINK_VERSION}/${ICEBERG_VERSION}/iceberg-flink-runtime-${FLINK_VERSION}-${ICEBERG_VERSION}.jar -P lib
wget -c https://github.com/knaufk/flink-faker/releases/download/v0.5.3/flink-faker-0.5.3.jar -P lib
cp /usr/lib/spark/jars/libthrift-0.12.0.jar lib/
cp /usr/lib/hive/lib/hive-common-3.1.3.jar lib/
gsutil cp gs://spark-lib/biglake/biglake-catalog-iceberg${ICEBERG_VERSION}-0.1.0-with-dependencies.jar lib/

# Disable ipv6
cat <<EOF > /etc/sysctl.d/90-disable-ipv6.conf
net.ipv6.conf.all.disable_ipv6=1
net.ipv6.conf.default.disable_ipv6=1
net.ipv6.conf.lo.disable_ipv6=1
EOF
sysctl -p -f /etc/sysctl.d/90-disable-ipv6.conf

# Export HADOOP_CLASSPATH
export HADOOP_CLASSPATH=$(hadoop classpath)

# Config flink-conf.yaml
cat <<EOF >> conf/flink-conf.yaml
# user supplied properties
execution.checkpointing.interval: 1min
execution.checkpointing.externalized-checkpoint-retention: DELETE_ON_CANCELLATION
execution.checkpointing.mode: EXACTLY_ONCE
execution.checkpointing.unaligned: true
state.backend: hashmap
state.checkpoints.dir: hdfs:///flink/checkpoints
state.savepoints.dir: hdfs:///flink/savepoints
parallelism.default: 1
EOF

# Create SQL file for Spark SQL to create iceberg catalog and table
cat <<EOF >> create_tables.sql
CREATE NAMESPACE IF NOT EXISTS blms;
CREATE DATABASE IF NOT EXISTS blms.iceberg_dataset;

CREATE TABLE IF NOT EXISTS blms.iceberg_dataset.taxi_p (
  ride_id STRING,
  point_idx STRING,
  latitude STRING,
  longitude STRING,
  timestamp STRING,
  meter_reading STRING,
  meter_increment STRING,
  ride_status STRING,
  passenger_count STRING,
  publish TIMESTAMP not null
)
USING iceberg 
TBLPROPERTIES (
  'format-version'='2',
  'write.parquet.compression-codec'='ZSTD',
  'write.metadata.delete-after-commit.enabled'='true',
  'write.metadata.previous-versions-max'='100',
  'bq_table'='iceberg_dataset.taxi', 
  'bq_connection'='projects/${PROJECT}/locations/us-central1/connections/${CONNECTION}');
EOF


# Run Spark SQL
spark-sql -f create_tables.sql \
  --packages org.apache.iceberg:iceberg-spark-runtime-${SPARK_VERSION}_2.12:${ICEBERG_VERSION} \
  --jars lib/biglake-catalog-iceberg${ICEBERG_VERSION}-0.1.0-with-dependencies.jar \
  --conf spark.sql.iceberg.handle-timestamp-without-timezone=true \
  --conf spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions \
  --conf spark.sql.catalog.blms=org.apache.iceberg.spark.SparkCatalog \
  --conf spark.sql.catalog.blms.catalog-impl=org.apache.iceberg.gcp.biglake.BigLakeCatalog \
  --conf spark.sql.catalog.blms.gcp_project=${PROJECT} \
  --conf spark.sql.catalog.blms.gcp_location=us-central1 \
  --conf spark.sql.catalog.blms.blms_catalog=iceberg \
  --conf spark.sql.catalog.blms.warehouse=${WAREHOUSE_DIR}
