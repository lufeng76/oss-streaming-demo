import sys
import time
from pyspark.sql.functions import *
from pyspark.sql.types import *
from pyspark.sql import SparkSession

def main():
    spark = SparkSession.builder.appName("stream_read_biglake").getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    tableIdentifier = "blms.iceberg_dataset.taxi_p"

    ts = int(time.time() * 1000)

    rows = spark.readStream.format("iceberg") \
      .option("stream-from-timestamp", ts) \
      .load(tableIdentifier)
    
    writer = rows.writeStream \
        .outputMode("append") \
        .format("console") \
        .trigger(processingTime="10 seconds") \
        .start()
    
    writer.awaitTermination()

if __name__=="__main__":
    main()