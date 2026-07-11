FROM apache/airflow:2.10.4-python3.12

COPY requirements.txt requirements-dev.txt /
RUN pip install --no-cache-dir -r /requirements-dev.txt
