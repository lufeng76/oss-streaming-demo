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
`Make sure stop the Kafka connector after demo. Otherwise the Kafka will use a large amount storage`

