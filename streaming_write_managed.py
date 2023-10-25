

import sys
from pyspark.sql.functions import *
from pyspark.sql.types import *
from pyspark.sql import SparkSession

def main(ip_address, topic):
    spark = SparkSession.builder.appName("stream_write_biglake").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    rows = spark.readStream.format("kafka") \
      .option("kafka.bootstrap.servers", ip_address).option("subscribe", topic) \
      .option("startingOffsets", "latest") \
      .option("failOnDataLoss", "false") \
      .load()


# {
#  "ride_id":"fafde05e-49a6-4449-b0f5-994138e2aff1",
#  "point_idx":233,"latitude":40.64546,
#  "longitude":-73.79955000000001,
#  "timestamp":"2023-08-13T16:26:32.75826-04:00",
#  "meter_reading":4.152008,
#  "meter_increment":0.017819777,
#  "ride_status":"enroute",
#  "passenger_count":1
# }

    schema = StructType([ 
        StructField("ride_id",StringType(),True), 
        StructField("point_idx",StringType(),True), 
        StructField("latitude",StringType(),True), 
        StructField("longitude", StringType(), True),
        StructField("timestamp",StringType(),True), 
        StructField("meter_reading",StringType(),True), 
        StructField("meter_increment",StringType(),True), 
        StructField("ride_status", StringType(), True),     
        StructField("passenger_count", StringType(), True)              
    ])


    query = rows.select(json_tuple(col("value").cast("string"),"payload")) \
            .select(json_tuple(col("c0"),"message")) \
            .select(unbase64(col("c0")).cast("string").alias("ride")) \
            .select(from_json(col("ride"),schema).alias("json")) \
            .select("json.*").withColumn("publish",current_timestamp())            

    query.printSchema()

    tableIdentifier = "lufeng-demo:biglake_managed.taxi"
    gcsTempBucket = "gs://lufeng-us-central1/tmp"


    writer = query.writeStream.format("bigquery") \
                .option("temporaryGcsBucket",gcsTempBucket) \
                .option("checkpointLocation", "/tmp/biglake") \
                .option("table", tableIdentifier) \
                .start()
    
    '''
    writer = query.writeStream.format("iceberg") \
               .outputMode("append") \
               .trigger(processingTime="10 second") \
               .option("path", tableIdentifier) \
               .option("checkpointLocation", "/tmp/iceberg") \
               .start()  

    df.writeStream \
        .format("bigquery") \
        .option("temporaryGcsBucket","some-bucket") \
        .option("checkpointLocation", "some-location") \
        .option("table", "dataset.table")                
    '''
 

    writer.awaitTermination()

if __name__=="__main__":
    if len(sys.argv) < 2:
        print ("Invalid number of arguments passed ", len(sys.argv))
        print ("Usage: ", sys.argv[0], " Kafka_ip_address  kafka_topic")
    main(sys.argv[1], sys.argv[2])

'''
from pyspark.sql import SparkSession

spark = SparkSession \
  .builder \
  .master('yarn') \
  .appName('spark-bigquery-demo') \
  .getOrCreate()

# Use the Cloud Storage bucket for temporary BigQuery export data used
# by the connector.
bucket = "[bucket]"
spark.conf.set('temporaryGcsBucket', bucket)

# Load data from BigQuery.
words = spark.read.format('bigquery') \
  .option('table', 'bigquery-public-data:samples.shakespeare') \
  .load()
words.createOrReplaceTempView('words')

# Perform word count.
word_count = spark.sql(
    'SELECT word, SUM(word_count) AS word_count FROM words GROUP BY word')
word_count.show()
word_count.printSchema()

# Save the data to BigQuery
word_count.write.format('bigquery') \
  .option('table', 'wordcount_dataset.wordcount_output') \
  .save()
'''