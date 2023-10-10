# Open Source Streaming Demo

As part of the streaming analytics solution, we plan to build an open source based stream data ingestion and visibility demo to showcase how the open source technologies can be integrated with the Google native service.

As shown in the diagram below, we have streaming data written into the Kafka. Then, we consume the Kafka topic using the Spark Streaming, and then write into a BigLake table with Iceberg table format. A query runs every 1 second from Bigquery against the biglake table and sends the result back to a dashboard in Looker.

<img src="img/architecture.png" width="50%" />

***Figure 1***

## Dataset

We use a real-time stream of simulated taxi telemetry based on historical ride data taken in New York City from the Taxi & Limousine Commission's [trip record datasets](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)

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

## Deploy Kafka and PubSub Kafka connector

