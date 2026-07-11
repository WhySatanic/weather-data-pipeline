import json
import os
from datetime import datetime, timezone

import boto3
import psycopg2
import requests
from botocore.exceptions import ClientError

LOCATIONS = (
    {"name": "Moscow", "latitude": 55.7558, "longitude": 37.6173},
    {"name": "Saint Petersburg", "latitude": 59.9343, "longitude": 30.3351},
    {"name": "Kazan", "latitude": 55.7964, "longitude": 49.1088},
)
API_URL = "https://api.open-meteo.com/v1/forecast"
HOURLY_FIELDS = "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,wind_speed_10m,weather_code"


def _s3_client():
    return boto3.client(
        "s3",
        endpoint_url=f"http://{os.environ['MINIO_ENDPOINT']}",
        aws_access_key_id=os.environ["MINIO_ACCESS_KEY"],
        aws_secret_access_key=os.environ["MINIO_SECRET_KEY"],
    )


def raw_key(logical_date, location_name):
    return (
        f"weather/year={logical_date[:4]}/month={logical_date[5:7]}/"
        f"day={logical_date[8:10]}/{location_name.lower().replace(' ', '_')}.json"
    )


def hourly_rows(payload, source_key):
    location = payload["location"]
    hourly = payload["data"]["hourly"]
    return [
        (
            location["name"], location["latitude"], location["longitude"], timestamp,
            hourly["temperature_2m"][index], hourly["apparent_temperature"][index],
            hourly["relative_humidity_2m"][index], hourly["precipitation"][index],
            hourly["wind_speed_10m"][index], hourly["weather_code"][index], source_key,
        )
        for index, timestamp in enumerate(hourly["time"])
    ]


def _ensure_bucket(client, bucket):
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError:
        try:
            client.create_bucket(Bucket=bucket)
        except ClientError as exc:
            if exc.response["Error"]["Code"] not in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
                raise


def extract_to_minio(logical_date):
    client = _s3_client()
    bucket = os.environ["MINIO_BUCKET"]
    _ensure_bucket(client, bucket)
    keys = []
    for location in LOCATIONS:
        response = requests.get(
            API_URL,
            params={
                "latitude": location["latitude"],
                "longitude": location["longitude"],
                "hourly": HOURLY_FIELDS,
                "forecast_days": 1,
                "timezone": os.getenv("WEATHER_TIMEZONE", "Europe/Moscow"),
            },
            timeout=30,
        )
        response.raise_for_status()
        key = raw_key(logical_date, location["name"])
        payload = {
            "location": location,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "data": response.json(),
        }
        client.put_object(Bucket=bucket, Key=key, Body=json.dumps(payload).encode(), ContentType="application/json")
        keys.append(key)
    return keys


def load_staging(keys):
    client = _s3_client()
    bucket = os.environ["MINIO_BUCKET"]
    sql = """
        INSERT INTO staging.weather_hourly
        (location_name, latitude, longitude, observed_at, temperature_c, apparent_temperature_c,
         relative_humidity_pct, precipitation_mm, wind_speed_kmh, weather_code, source_key)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (location_name, observed_at) DO UPDATE SET
          latitude = EXCLUDED.latitude, longitude = EXCLUDED.longitude,
          temperature_c = EXCLUDED.temperature_c, apparent_temperature_c = EXCLUDED.apparent_temperature_c,
          relative_humidity_pct = EXCLUDED.relative_humidity_pct, precipitation_mm = EXCLUDED.precipitation_mm,
          wind_speed_kmh = EXCLUDED.wind_speed_kmh, weather_code = EXCLUDED.weather_code,
          source_key = EXCLUDED.source_key, loaded_at = now()
    """
    with psycopg2.connect(os.environ["WAREHOUSE_DSN"]) as connection, connection.cursor() as cursor:
        for key in keys:
            payload = json.loads(client.get_object(Bucket=bucket, Key=key)["Body"].read())
            cursor.executemany(sql, hourly_rows(payload, key))


def validate_staging():
    checks = {
        "duplicate hourly records": """
            SELECT count(*) FROM (
                SELECT location_name, observed_at FROM staging.weather_hourly
                GROUP BY 1, 2 HAVING count(*) > 1
            ) duplicates
        """,
        "incomplete daily records": """
            SELECT count(*) FROM (
                SELECT location_name, observed_at::date FROM staging.weather_hourly
                GROUP BY 1, 2 HAVING count(*) <> 24
            ) incomplete
        """,
        "invalid weather values": """
            SELECT count(*) FROM staging.weather_hourly
            WHERE temperature_c NOT BETWEEN -90 AND 70
               OR precipitation_mm < 0
               OR wind_speed_kmh < 0
        """,
    }
    with psycopg2.connect(os.environ["WAREHOUSE_DSN"]) as connection, connection.cursor() as cursor:
        for check_name, sql in checks.items():
            cursor.execute(sql)
            if cursor.fetchone()[0]:
                raise ValueError(f"Data quality check failed: {check_name}")


def refresh_mart():
    sql = """
        INSERT INTO mart.weather_daily (
          weather_date, location_name, latitude, longitude, avg_temperature_c,
          min_temperature_c, max_temperature_c, total_precipitation_mm,
          avg_wind_speed_kmh, observations_count, refreshed_at
        )
        SELECT observed_at::date, location_name, latitude, longitude,
          round(avg(temperature_c), 2), min(temperature_c), max(temperature_c),
          round(sum(precipitation_mm), 2), round(avg(wind_speed_kmh), 2), count(*), now()
        FROM staging.weather_hourly
        GROUP BY 1, 2, 3, 4
        ON CONFLICT (weather_date, location_name) DO UPDATE SET
          avg_temperature_c = EXCLUDED.avg_temperature_c, min_temperature_c = EXCLUDED.min_temperature_c,
          max_temperature_c = EXCLUDED.max_temperature_c, total_precipitation_mm = EXCLUDED.total_precipitation_mm,
          avg_wind_speed_kmh = EXCLUDED.avg_wind_speed_kmh, observations_count = EXCLUDED.observations_count,
          refreshed_at = EXCLUDED.refreshed_at
    """
    with psycopg2.connect(os.environ["WAREHOUSE_DSN"]) as connection, connection.cursor() as cursor:
        cursor.execute(sql)
