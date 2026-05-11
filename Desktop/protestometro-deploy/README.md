# Protestómetro MX

Portal público semanal de monitoreo de protestas y manifestaciones en las 75 Zonas Metropolitanas de México. Desarrollado por [Aleph](https://alephri.com).

## Características

- **75 ZMs canónicas** del catálogo INEGI con población y municipios
- **17 semanas** de datos históricos (ene–may 2026)
- **Hexágonos de alerta** con difusión de calor por nivel
- **30 corredores federales** identificados con sus ZMs afectadas
- **Glassmorphism UI** sobre mapa interactivo (Leaflet + OpenStreetMap)
- **Mobile-first** con headline flotante siempre visible

## Stack

Single-file HTML, sin build, sin dependencias de Node. Carga:
- [Leaflet 1.9.4](https://leafletjs.com) desde cdnjs
- [Inter](https://fonts.google.com/specimen/Inter) desde Google Fonts
- Tiles de OpenStreetMap

## Deploy

Drop-in en cualquier static host. Para Vercel: importar el repo y ya. No requiere variables de entorno ni build step.

```bash
# Local preview (cualquier static server funciona)
python3 -m http.server 8000
# Abrir http://localhost:8000
```

## Datos

- **ZMs**: catálogo INEGI 2015 (75 zonas, 418 municipios)
- **Semáforo**: actualización semanal por equipo Aleph
- **Tiles**: © OpenStreetMap contributors

## Licencia

© 2026 Aleph. Todos los derechos reservados.
