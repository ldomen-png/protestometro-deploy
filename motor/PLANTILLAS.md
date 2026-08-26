# Plantillas del servicio — spec canónica

El producto es el mensaje. Estas cinco plantillas son la interfaz del Climómetro
para el cliente; `corte.py` las implementa y este archivo manda. Cualquier cambio
de copy se decide aquí primero.

## Reglas duras (aplican a todo mensaje)

1. **Segundo lector.** El mensaje se diseña para quien lo recibe *reenviado*
   (gerente regional que no conoce la herramienta): autocontenido, sin links
   obligatorios, sin jerga. Si el remitente tiene que editarlo antes de
   reenviar, la plantilla está mal.
2. **Una pantalla.** Presupuesto: 12 líneas máximo (ficha), 5 líneas (corte verde).
3. **Estructura fija.** Siempre el mismo orden: veredicto → alcance → detalle →
   acción → próxima revisión → fuentes. La escaneabilidad viene de la repetición.
4. **El amarillo no interrumpe pero sí aparece** (línea de vigilancia en el
   corte). Nunca genera mensaje extraordinario.
5. **El silencio está prohibido.** Sin datos → sale la plantilla de falla. Un
   corte que no llega destruye más confianza que cualquier falsa alarma.
6. **Siempre hay "próxima revisión".** Convierte incertidumbre en cadencia. En
   alerta, la cadencia es la del protocolo SIAT-CT (naranja/roja: cada 3 h).
7. **Agregación por las regiones del cliente** (`regiones.json`), nunca por
   nuestras 79 zonas. El cliente piensa en sus 4 regiones y sus canales de Teams.
8. **Confirmación solo cuando hay acción**: la ficha extraordinaria pide
   "Responde RECIBIDO"; el corte verde jamás pide nada.

## 1 · Corte NORMAL (07:00 y 16:00)

Su trabajo no es informar: es demostrar diligencia ("estamos revisando").

```
🟢 *CLIMÓMETRO · mié 26 ago · corte 07:00*
Sin alertas naranja o roja en las 4 regiones.
Vigilancia (sin acción requerida): Sureste: Tapachula (29 mm de lluvia).
Próxima revisión: 16:00.
Fuentes: SMN/Open-Meteo · NHC · USGS · GloFAS, revisadas 06:45.
```

## 2 · Corte con SEGUIMIENTO (ciclón relevante, aún sin naranja)

El caso "aún está lejos pero ya viene": anticipación sin costo de interrupción.
Sigue siendo el corte de siempre + un bloque; no es mensaje extraordinario.

```
🟢 *CLIMÓMETRO · jue 27 ago · corte 07:00*
Sin alertas naranja o roja; ciclón en seguimiento (abajo).
_Seguimiento_: Huracán *Lorena* cat. 1 — punto más cercano La Paz a ~450 km
(~60 h); etapa estimada VERDE. Si el vector se sostiene, probable AMARILLA
mañana.
Próxima revisión: 16:00.
Fuentes: SMN/Open-Meteo · NHC · USGS · GloFAS, revisadas 06:45.
```

## 3 · Ficha de ALERTA (extraordinaria — al cruzar a naranja/roja)

Sale en el momento, no espera al corte. Pide confirmación. Cadencia 3 h.

```
🟠 *CLIMÓMETRO · jue 27 ago · ALERTA*
*Región Sureste — NARANJA*
• Acapulco: SIAT-CT est. NARANJA·alarma — Lorena a 210 km (~20 h)
• Chilpancingo: SIAT-CT est. NARANJA·alarma — Lorena (~20 h)
→ Actúa: activa comité regional, reprograma embarques expuestos, notifica a sitios.
Resto del país sin alerta: Norte, Occidente, Centro.
_Responde RECIBIDO para confirmar._
Próxima actualización: 13:00 o antes si cambia la situación.
Fuentes: SMN/Open-Meteo · NHC · USGS · GloFAS, revisadas 09:58.
```

## 4 · CIERRE de alerta

El mensaje que casi todos olvidan y el que más confianza construye. También es
la defensa ante falsas alarmas: una naranja que no pegó, *explicada*, suma.

```
🟢 *CLIMÓMETRO · vie 28 ago · corte 16:00*
*Cierre de alerta*: Sureste regresa a nivel sin alerta.
Lorena tocó tierra debilitada al sur de Puerto Escondido; sin daños reportados
en activos. Vigilar efectos residuales 24 h (encharcamientos, crecidas menores).
Próxima revisión: 07:00 de mañana.
Fuentes: SMN/Open-Meteo · NHC · USGS · GloFAS, revisadas 15:45.
```

## 5 · FALLA de verificación

```
⚪ *CLIMÓMETRO · corte 07:00*
No pudimos completar la verificación de este corte (falla técnica de fuentes).
Reintentamos a las 07:30 y avisamos.
```

## Métricas de la experiencia

1. **Cero días sin corte** (el SLA sagrado).
2. **Tiempo remitente→reenvío** — si se reenvía sin editar en <2 min, funciona.
3. **% de RECIBIDO en fichas naranja/roja.**
4. **Anticipación**: minutos entre nuestra ficha y el primer aviso oficial del
   mismo evento (se mide con `out/sombra.jsonl`).
