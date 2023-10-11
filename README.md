# Open Source Streaming Demo

As part of the streaming analytics solution, we plan to build an open source based stream data ingestion and visibility demo to showcase how the open source technologies can be integrated with the Google native service.

As shown in the diagram below, we have the streaming data written into the Kafka. Then, we consume the Kafka topic using the Spark Streaming, and then write into a BigLake table with Iceberg table format. A query runs every 10 second from Bigquery against the biglake table and sends the result back to a dashboard in Looker.

<img src="img/architecture.png" width="100%" />

***Figure 1***

## Dataset

We use a real-time stream of simulated taxi telemetry based on historical ride data taken in New York City from the Taxi & Limousine Commission's [trip record datasets](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page). The data is publicly availabe through the Pub/Sub topic.

```json
{
  "ride_id": "7da878a4-37ce-4aa6-a899-07d4054afe96",
  "point_idx": 267,
  "latitude": 40.76561,
  "longitude": -73.96572,
  "timestamp": "2023-07-10T19:00:33.56833-04:00",
  "meter_reading": 11.62449,
  "meter_increment": 0.043537416,
  "ride_status": "enroute",
  "passenger_count": 1
}
```

## Environment variables

Change these varaibles in your environment

```bash
export PROJECT=lufeng-demo
export SUBNET=default
export KAFKA_VM=kafka-2
export CLUSTER_NAME=streaming-demo-cluster
export DATAPROC_BUCKET=lufeng-dataproc-bucket
export WAREHOUSE_DIR=gs://lufeng-us-central1/iceberg
export SA_NAME=lufeng-sa
export CONNECTION=biglake-iceberg
```

## Deploy Kafka and Pub/Sub Kafka connector

We need to install the Kafka service and the Pub/Sub Kafka connector.

### 1. Create a VM 

```bash
gcloud compute instances create ${KAFKA_VM} \
  --project ${PROJECT} \
  --zone us-central1-a \
  --machine-type e2-standard-2 \
  --subnet ${SUBNET} \
  --scopes https://www.googleapis.com/auth/cloud-platform \
  --boot-disk-size 100GB 
```

### 2. Install and configure the Kafka service
You can follow the instruction [here](https://kafka.apache.org/quickstart) or below script to install the Kafka service

SHH into the Kafka VM, and execute the following script
```bash
# install openjdk
sudo apt install default-jre

# download the kafka package
wget https://dlcdn.apache.org/kafka/3.5.0/kafka_2.13-3.5.0.tgz
tar -xzf kafka_2.13-3.5.0.tgz

cd kafka_2.13-3.5.0/

# Start the ZooKeeper service
nohup bin/zookeeper-server-start.sh config/zookeeper.properties > zk.log 2>&1 &

# Start the Kafka broker service
nohup bin/kafka-server-start.sh config/server.properties > broker.log 2>&1 &

# Create a Topic 
bin/kafka-topics.sh --create --topic taxi-events --bootstrap-server localhost:9092
```

you can test the kafka using the following script(optional)
```bash
# Create a Topic 
bin/kafka-topics.sh --create --topic quickstart-events --bootstrap-server localhost:9092

# Publish some message
bin/kafka-console-producer.sh --topic quickstart-events --bootstrap-server localhost:9092

# Consume the message
bin/kafka-console-consumer.sh --topic quickstart-events --from-beginning --bootstrap-server localhost:9092
```

### 3. Install and configure the Pub/Sub Kafka connector

SSH into the Kafka VM, and execute the following script
```bash
export PROJECT=lufeng-demo
export KAFKA_HOME=~/kafka_2.13-3.5.0

# your user account
export EMAIL_ADDRESS=admin@lufengsh.altostrat.com

# set up authentication
gcloud config set project ${PROJECT}
gcloud auth application-default login
gcloud projects add-iam-policy-binding ${PROJECT} --member="user:${EMAIL_ADDRESS}" --role=roles/pubsub.admin

cd $KAFKA_HOME

# download the connector JAR
wget https://repo1.maven.org/maven2/com/google/cloud/pubsub-group-kafka-connector/1.2.0/pubsub-group-kafka-connector-1.2.0.jar

# get the Kafka Connect configuration files
sudo apt-get install git
git clone https://github.com/googleapis/java-pubsub-group-kafka-connector.git
cd java-pubsub-group-kafka-connector

cp config/* ${KAFKA_HOME}/config/
```

Following the below instruction to update the Kafka connector configuration file
1. Navigate to your Kafka directory.
2. Open the file named `config/connect-standalone.properties` in a text editor.
3. Make the following changes in the text editor, and save
```bash
key.converter=org.apache.kafka.connect.json.JsonConverter
value.converter=org.apache.kafka.connect.json.JsonConverter

offset.storage.file.filename=/tmp/connect.offsets

# Specify the path to the connector JAR
# example: plugin.path=/home/PubSubKafkaConnector/pubsub-group-kafka-connector-1.0.0.jar
plugin.path=MODIFY_YOUR_PATH/pubsub-group-kafka-connector-1.2.0.jar
```
4. Open the file named `config/cps-source-connector.properties` in a text editor. Add values for the following properties.
```bash
# Set the key converter for the Pub/Sub source connector.
key.converter=org.apache.kafka.connect.storage.StringConverter
# Set the value converter for the Pub/Sub source connector.
# value.converter=org.apache.kafka.connect.converters.ByteArrayConverter
value.converter=org.apache.kafka.connect.json.JsonConverter

kafka.topic=taxi-events
cps.project=YOUR_PROJECT_ID
cps.subscription=taxi-sub
```

After the configuration ,you can start the Kafka connector.
```bash
bin/connect-standalone.sh \
  config/connect-standalone.properties \
  config/cps-source-connector.properties
```
**Make sure stop the Kafka connector after demo. Otherwise the Kafka will use a large amount storage**

## Create a Dataproc cluster and the Biglake iceberg table

Following the below instructions:
1. Setup service account for dataproc
```bash
gcloud iam service-accounts create "${SA_NAME}" \
--project ${PROJECT} \
--description "Service account for Dataproc."

gcloud projects add-iam-policy-binding "${PROJECT}" \
--role roles/dataproc.worker \
--member "serviceAccount:${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding "${PROJECT}" \
--role roles/bigquery.connectionAdmin \
--member "serviceAccount:${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding "${PROJECT}" \
--role roles/bigquery.jobUser \
--member "serviceAccount:${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding "${PROJECT}" \
--role roles/bigquery.dataEditor \
--member "serviceAccount:${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding "${PROJECT}" \
--role roles/biglake.admin \
--member "serviceAccount:${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"
```
2. Create BigQuery connection for BigLake table
```bash
bq mk --connection --location=us-central1 --project_id=${PROJECT} \
  --connection_type=CLOUD_RESOURCE ${CONNECTION}

bq show --connection ${PROJECT}.us-central1.${CONNECTION}

SA_CONNECTION=$(bq show --format json --connection ${PROJECT}.us-central1.${CONNECTION}|jq -r '.cloudResource.serviceAccountId')

gcloud projects add-iam-policy-binding "${PROJECT}" \
--role roles/biglake.admin \
--member "serviceAccount:${SA_CONNECTION}"

gcloud projects add-iam-policy-binding "${PROJECT}" \
--role roles/storage.objectViewer \
--member "serviceAccount:${SA_CONNECTION}"
```
3. Create the dataset for the Biglake iceberg table
```bash
bq mk --dataset --location=us-central1 --project_id=${PROJECT} iceberg_dataset
```
4. Enable the BigQuery Connection, BigQuery Reservation, and BigLake APIs
```bash
gcloud services enable biglake.googleapis.com
gcloud services enable bigqueryconnection.googleapis.com
gcloud services enable bigqueryreservation.googleapis.com
```

5. Create a one node Dataproc cluster
```bash
gsutil cp init_iceberg.sh gs://${DATAPROC_BUCKET}/init_scripts/

gcloud dataproc clusters create ${CLUSTER_NAME} \
--project ${PROJECT} \
--single-node \
--scopes cloud-platform \
--region us-central1 \
--enable-component-gateway \
--subnet ${SUBNET} \
--bucket ${DATAPROC_BUCKET} \
--temp-bucket ${DATAPROC_BUCKET} \
--service-account ${SA_NAME}@${PROJECT}.iam.gserviceaccount.com \
--master-machine-type n2d-highmem-8 \
--master-boot-disk-size 100 \
--master-boot-disk-type pd-balanced \
--image-version 2.1-debian11 \
--optional-components "Flink" \
--initialization-actions gs://${DATAPROC_BUCKET}/init_scripts/init_iceberg.sh \
--metadata DATAPROC_BUCKET=${DATAPROC_BUCKET} \
--metadata WAREHOUSE_DIR=${WAREHOUSE_DIR} \
--metadata CONNECTION=${CONNECTION} \
--metadata PROJECT=${PROJECT}
```

## Demo Steps for biglake iceberg
1. SSH into the master node of the Dataproc cluster, and then start the streaming write job
```bash
git clone https://github.com/lufeng76/oss-streaming-demo.git
cd oss-streaming-demo

export ICEBERG_VERSION=1.2.0
export SPARK_VERSION=3.3
export PROJECT=lufeng-demo
export SUBNET=default
export CLUSTER_NAME=streaming-demo-cluster
export DATAPROC_BUCKET=lufeng-dataproc-bucket
export WAREHOUSE_DIR=gs://lufeng-us-central1/iceberg
export SA_NAME=lufeng-sa
export CONNECTION=biglake-iceberg

export KAFKA_IP_ADDRESS=YOUR_KAFKA_VM_IP
export KAFKA_TOPIC=taxi-events

spark-submit --packages \
org.apache.spark:spark-sql-kafka-0-10_2.12:3.3.0,\
org.apache.spark:spark-streaming-kafka-0-10_2.12:3.1.3,\
org.apache.iceberg:iceberg-spark-runtime-${SPARK_VERSION}_2.12:${ICEBERG_VERSION} \
 --jars /usr/lib/flink/lib/biglake-catalog-iceberg${ICEBERG_VERSION}-0.1.0-with-dependencies.jar \
 --conf spark.sql.iceberg.handle-timestamp-without-timezone=true \
 --conf spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions \
 --conf spark.sql.catalog.blms=org.apache.iceberg.spark.SparkCatalog \
 --conf spark.sql.catalog.blms.catalog-impl=org.apache.iceberg.gcp.biglake.BigLakeCatalog \
 --conf spark.sql.catalog.blms.gcp_project=${PROJECT} \
 --conf spark.sql.catalog.blms.gcp_location=us-central1 \
 --conf spark.sql.catalog.blms.blms_catalog=iceberg \
 --conf spark.sql.catalog.blms.warehouse=${WAREHOUSE_DIR} \
 streaming_write_iceberg.py $KAFKA_IP_ADDRESS $KAFKA_TOPIC
```
2. You can go to the BigQuery Console, and run the following query
```sql
select count(*) from iceberg_dataset.taxi_p;
```
Or, you can run the spark streaming job to read the latest data from the Biglake iceberg table
```
spark-submit --packages \
org.apache.spark:spark-sql-kafka-0-10_2.12:3.3.0,\
org.apache.spark:spark-streaming-kafka-0-10_2.12:3.1.3,\
org.apache.iceberg:iceberg-spark-runtime-${SPARK_VERSION}_2.12:${ICEBERG_VERSION} \
 --jars /usr/lib/flink/lib/biglake-catalog-iceberg${ICEBERG_VERSION}-0.1.0-with-dependencies.jar \
 --conf spark.sql.iceberg.handle-timestamp-without-timezone=true \
 --conf spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions \
 --conf spark.sql.catalog.blms=org.apache.iceberg.spark.SparkCatalog \
 --conf spark.sql.catalog.blms.catalog-impl=org.apache.iceberg.gcp.biglake.BigLakeCatalog \
 --conf spark.sql.catalog.blms.gcp_project=${PROJECT} \
 --conf spark.sql.catalog.blms.gcp_location=us-central1 \
 --conf spark.sql.catalog.blms.blms_catalog=iceberg \
 --conf spark.sql.catalog.blms.warehouse=${WAREHOUSE_DIR} \
 streaming_read_iceberg.py
```

## (Optional) Setup a looker real time dashboard
1. Go to the BigQuery console and create a View.
```sql
create view iceberg_dataset.v_taxi as
select
  ride_id,
  point_idx,
  ROUND(CAST(latitude as FLOAT64),5) AS latitude,
  ROUND(CAST(longitude as FLOAT64),5) AS longitude,
  CAST(timestamp as timestamp) as ps_timestamp,
  CAST(meter_reading as FLOAT64) AS meter_reading,
  CAST(meter_increment as FLOAT64) AS meter_increment,
  ride_status,
  passenger_count,
  publish,
  TIMESTAMP_ADD(publish, INTERVAL 8 HOUR) AS sg_publish
from iceberg_dataset.taxi_p
```
2. Fork your own LookML github repo from this [link](https://github.com/lufeng76/looker-stream-demo/tree/master)
3. Build your own dash board by copying this [link](https://cloudceapac.cloud.looker.com/dashboards/210)