from botocore.exceptions import ClientError

from src.weather_pipeline import _ensure_bucket, hourly_rows, raw_key


def test_raw_key_is_date_partitioned():
    assert raw_key("2026-07-11", "Saint Petersburg") == "weather/year=2026/month=07/day=11/saint_petersburg.json"


def test_hourly_rows_preserve_location_and_metrics():
    payload = {
        "location": {"name": "Moscow", "latitude": 55.7558, "longitude": 37.6173},
        "data": {
            "hourly": {
                "time": ["2026-07-11T00:00"],
                "temperature_2m": [20.1],
                "apparent_temperature": [19.7],
                "relative_humidity_2m": [65],
                "precipitation": [0.2],
                "wind_speed_10m": [8.4],
                "weather_code": [3],
            }
        },
    }
    assert hourly_rows(payload, "weather/test.json") == [
        ("Moscow", 55.7558, 37.6173, "2026-07-11T00:00", 20.1, 19.7, 65, 0.2, 8.4, 3, "weather/test.json")
    ]


def test_existing_bucket_does_not_raise():
    class Client:
        def head_bucket(self, **_):
            raise ClientError({"Error": {"Code": "404"}}, "HeadBucket")

        def create_bucket(self, **_):
            raise ClientError({"Error": {"Code": "BucketAlreadyOwnedByYou"}}, "CreateBucket")

    _ensure_bucket(Client(), "weather-raw")
