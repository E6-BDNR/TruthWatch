"""Prueba de conexión: Spark lee de MongoDB, escribe en Cassandra y en Neo4j.

docker exec tw-spark-master /opt/spark/bin/spark-submit /jobs/check.py
"""
import os

from pyspark.sql import SparkSession, functions as F

env = os.environ
spark = SparkSession.builder.appName("check").getOrCreate()

# MongoDB (usuario spark: solo lectura en raw)
edits = (
    spark.read.format("mongodb")
    .option("connection.uri", f"mongodb://spark:{env['MONGO_SPARK_PASSWORD']}@mongo-router:27017/?authSource=admin")
    .option("database", "raw")
    .option("collection", "wikimedia")
    .load()
)
top = edits.groupBy(F.col("data.wiki").alias("wiki")).count().orderBy(F.desc("count")).limit(5)
top.show()

# Cassandra (usuario spark_writer)
(
    top.select(
        F.col("wiki").alias("topic"),
        F.current_date().alias("day"),
        F.current_timestamp().alias("window_start"),
        F.lit("check").alias("source"),
        F.col("count").cast("int").alias("events"),
    )
    .write.format("org.apache.spark.sql.cassandra")
    .option("spark.cassandra.auth.username", "spark_writer")
    .option("spark.cassandra.auth.password", env["CASSANDRA_SPARK_PASSWORD"])
    .options(keyspace="truthwatch", table="metrics_by_topic")
    .mode("append")
    .save()
)

# Neo4j
(
    top.write.format("org.neo4j.spark.DataSource")
    .option("url", "bolt://neo4j:7687")
    .option("authentication.basic.username", "neo4j")
    .option("authentication.basic.password", env["NEO4J_PASSWORD"])
    .option("labels", ":Wiki")
    .option("node.keys", "wiki")
    .mode("overwrite")
    .save()
)

print("MongoDB -> Spark -> Cassandra y Neo4j: ok")
