-- Apply to an already-created warehouse. Fresh installations receive this
-- definition directly from warehouse_init.sql.
DELETE FROM staging.weather_hourly older
USING staging.weather_hourly newer
WHERE older.location_name = newer.location_name
  AND older.observed_at = newer.observed_at
  AND older.ctid < newer.ctid;

ALTER TABLE staging.weather_hourly DROP CONSTRAINT IF EXISTS weather_hourly_pkey;
ALTER TABLE staging.weather_hourly
    ADD PRIMARY KEY (location_name, observed_at);
