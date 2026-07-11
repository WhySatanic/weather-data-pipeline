from datetime import datetime, timedelta

from airflow.decorators import dag, task
from airflow.operators.python import get_current_context
from src.weather_pipeline import extract_to_minio, load_staging, refresh_mart, validate_staging


@dag(
    dag_id="weather_daily_pipeline",
    schedule="0 6 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args={"owner": "data-team", "retries": 2, "retry_delay": timedelta(minutes=5)},
    tags=["weather", "minio", "warehouse"],
)
def weather_daily_pipeline():
    @task
    def extract():
        return extract_to_minio(get_current_context()["ds"])

    @task
    def stage(keys):
        load_staging(keys)

    @task
    def quality_check():
        validate_staging()

    @task
    def build_mart():
        refresh_mart()

    staging = stage(extract())
    quality = quality_check()
    staging >> quality >> build_mart()


weather_daily_pipeline()
