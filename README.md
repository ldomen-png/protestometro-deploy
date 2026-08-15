# Protestómetro MX · Climómetro

Portal público de riesgo operativo para las 75 zonas metropolitanas de México, desarrollado por [Aleph](https://alephri.com). Dos modos sobre el mismo mapa:

- **Protestas** — semáforo semanal de conflictividad social (actualización manual por equipo Aleph).
- **Clima (Climómetro)** — pronóstico de riesgo climático-operativo a 7 días, con datos en vivo.

## Modo Clima

**Semáforo logístico multi-variable** por zona y por día, con atribución (la app dice *por qué* una zona está en alerta): lluvia acumulada, viento sostenido, ráfagas, calor extremo y condición del cielo (código WMO). Umbrales centralizados en `CLIMA_THRESHOLDS`.

Capas y señales:

- **Malla nacional de lluvia** — 660 celdas a 1°, raster interpolado en GPU (Mapbox canvas source).
- **Partículas de viento** — campo u/v advectado en tiempo real (hasta 1,400 partículas).
- **Corredores con pronóstico propio** — los 30 corredores federales se evalúan punto a punto (196 waypoints); el nivel toma el peor tramo de la ruta.
- **Ciclones tropicales** — cono de incertidumbre, trayectoria y puntos de pronóstico del NHC/NOAA (ArcGIS REST con CORS), sondeando los slots AT1–AT5 y EP1–EP5.
- **Sismos** — M4.5+ de los últimos 7 días vía USGS (GeoJSON con CORS).
- **Crecidas fluviales** — descarga GloFAS (Open-Meteo Flood API); señal cuando el pronóstico supera 2× la mediana de los últimos 31 días.

## Fuentes de datos

| Fuente | Uso | Endpoint |
|---|---|---|
| Open-Meteo Forecast | Pronóstico ZMs, corredores y malla | `api.open-meteo.com/v1/forecast` |
| Open-Meteo Flood (GloFAS) | Señal de crecida fluvial | `flood-api.open-meteo.com/v1/flood` |
| NHC / NOAA | Ciclones tropicales (cono, track, puntos) | `mapservices.weather.noaa.gov/tropical/.../NHC_tropical_weather/MapServer` |
| USGS | Sismos M4.5+ | `earthquake.usgs.gov/fdsnws/event/1/query` |

Todas con CORS abierto — el cliente estático las consume sin backend ni API keys (salvo el token público de Mapbox).

## Stack

Single-file HTML (`index.html`), sin build, sin dependencias de Node. Carga:
- [Mapbox GL JS 3.8](https://www.mapbox.com/mapbox-gljs) (estilo `light-v11`)
- [Inter](https://fonts.google.com/specimen/Inter) desde Google Fonts

Caches del cliente: malla de lluvia en `localStorage` (por día calendario), ciclones NHC en `sessionStorage` (30 min).

## Deploy

Drop-in en cualquier static host. Para Vercel: importar el repo y ya. No requiere variables de entorno ni build step.

```bash
# Local preview (cualquier static server funciona)
python3 -m http.server 8000
# Abrir http://localhost:8000
```

## Datos

- **ZMs**: catálogo INEGI (75 zonas, 418 municipios; el Valle de México se desagrega en 5 sub-zonas)
- **Semáforo de protestas**: actualización semanal por equipo Aleph
- **Clima y riesgo**: fuentes en vivo listadas arriba

## Roadmap

- Proxy ligero en Vercel Functions: cachear Open-Meteo (plan comercial), parsear avisos SMN/CONAGUA
- Capa estática de peligro por inundación municipal (CENAPRED, extracción offline del Atlas Nacional de Riesgos)
- Incendios forestales (NASA FIRMS vía pipeline cron)
- Semáforo probabilístico (Open-Meteo Ensemble API)

## Licencia

© 2026 Aleph. Todos los derechos reservados. Datos: Open-Meteo (CC BY 4.0), NOAA/USGS (dominio público), GloFAS (Copernicus).
