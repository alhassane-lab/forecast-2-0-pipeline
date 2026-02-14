from datetime import datetime
from pipeline.transformers.data_harmonizer import DataHarmonizer

# Exemple de données brutes simulées
infoclimat_sample = {'source': 'infoclimat', 'station_id': '07015', 'station_name': 'Lille-Lesquin', 'station_type': 'synop', 'latitude': 50.575, 'longitude': 3.092, 'elevation': 47, 'city': 'Lille', 'country': 'France', 'region': 'Hauts-de-France', 'timestamp': '2024-10-05 00:00:00', 'measurements': {'temperature': '7.6', 'pression': '1020.7', 'humidite': '89', 'point_de_rosee': '5.9', 'visibilite': '6000', 'vent_moyen': '3.6', 'vent_rafales': '7.2', 'vent_direction': '90', 'pluie_1h': '0', 'pluie_3h': '0', 'neige_au_sol': None, 'nebulosite': '', 'temps_omm': None}, 'metadata': {'temperature': 'temperature,degC', 'pression': 'mean sea level pressure,hPa', 'humidite': 'relative humidity,%', 'point_de_rosee': 'dewpoint,degC', 'visibilite': 'horizontal visibility,m', 'vent_moyen': 'mean wind speed,km/h', 'vent_rafales': 'wind gust,km/h', 'vent_direction': 'wind direction,deg', 'pluie_3h': 'precipitation over 3h,mm', 'pluie_1h': 'precipitation over 1h,mm', 'neige_au_sol': 'snow depth,cm', 'nebulosite': 'Ncloud cover,octats', 'temps_omm': 'present weather,http://www.infoclimat.fr/stations-meteo/ww.php'}}


wunderground_sample = {'source': 'wunderground', 'station_id': 'IICHTE19', 'station_name': 'WeerstationBS', 'latitude': 51.092, 'longitude': 2.999, 'elevation': 15, 'city': 'Ichtegem', 'country': 'Belgium', 'region': 'West-Vlaanderen', 'hardware': 'other', 'software': 'EasyWeatherV1.6.6', 'timestamp': '00:14:00', 'measurements': {'temperature': 57.0, 'dewpoint': 52.8, 'humidity': 86.0, 'wind_speed': 10.3, 'wind_gust': 12.8, 'wind_direction': 'West', 'pressure': 29.47, 'precip_rate': 0.0, 'precip_accum': 0.0, 'uv_index': 0.0, 'solar_radiation': 0.0}}

# Initialiser le harmonizer
harmonizer = DataHarmonizer(config={})

# Harmoniser les données
harmonized_ic = harmonizer.harmonize_infoclimat(infoclimat_sample)
harmonized_wu = harmonizer.harmonize_wunderground(wunderground_sample)

# Afficher les résultats
print("=== InfoClimat Harmonized ===")
print(harmonized_ic)

print("\n=== Weather Underground Harmonized ===")
print(harmonized_wu)

