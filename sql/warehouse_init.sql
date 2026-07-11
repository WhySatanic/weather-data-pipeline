CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS mart;

CREATE TABLE IF NOT EXISTS staging.weather_hourly (
    location_name text NOT NULL,
    latitude numeric(9, 6) NOT NULL,
    longitude numeric(9, 6) NOT NULL,
    observed_at timestamptz NOT NULL,
    temperature_c numeric(6, 2),
    apparent_temperature_c numeric(6, 2),
    relative_humidity_pct numeric(5, 2),
    precipitation_mm numeric(8, 2),
    wind_speed_kmh numeric(8, 2),
    weather_code integer,
    source_key text NOT NULL,
    loaded_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (location_name, observed_at)
);

CREATE TABLE IF NOT EXISTS mart.weather_daily (
    weather_date date NOT NULL,
    location_name text NOT NULL,
    latitude numeric(9, 6) NOT NULL,
    longitude numeric(9, 6) NOT NULL,
    avg_temperature_c numeric(6, 2),
    min_temperature_c numeric(6, 2),
    max_temperature_c numeric(6, 2),
    total_precipitation_mm numeric(10, 2),
    avg_wind_speed_kmh numeric(8, 2),
    observations_count integer NOT NULL,
    refreshed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (weather_date, location_name)
);
