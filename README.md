# Open Source Streaming Demo

As part of the streaming analytics solution, we plan to build an open source based stream data ingestion and visibility demo to showcase how the open source technologies can be integrated with the Google native service.

As shown in the diagram below, we have streaming data written into the Kafka. Then, we consume the Kafka topic using the Spark Streaming, and then write into a BigLake table with Iceberg table format. A query runs every 1 second from Bigquery against the biglake table and sends the result back to a dashboard in Looker.
