WITH ranked_days AS (
    SELECT *, rank() OVER (PARTITION BY location_name ORDER BY total_precipitation_mm DESC) AS precipitation_rank
    FROM mart.weather_daily
)
SELECT weather_date, location_name, total_precipitation_mm
FROM ranked_days
WHERE precipitation_rank = 1
ORDER BY location_name;

SELECT weather_date, location_name, avg_temperature_c,
       avg_temperature_c - avg(avg_temperature_c) OVER (PARTITION BY location_name) AS temperature_deviation
FROM mart.weather_daily
ORDER BY weather_date DESC, location_name;
