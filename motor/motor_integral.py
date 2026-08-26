#!/usr/bin/env python3
"""Motor de fusión multi-señal — Nivel Operativo Integral (prototipo).

Combina, por objetivo (zona metropolitana o sitio del cliente):
  1. Física pronosticada  — Open-Meteo (lluvia, viento, ráfagas, calor, cielo)
  2. Ciclón               — SIAT-CT estimado desde la trayectoria NHC
  3. Hidrología + terreno — GloFAS vs mediana 31d × vulnerabilidad local
                            (puntos críticos CONAGUA, índice CENAPRED)
  4. Respuesta observada  — eventos institucionales confirmados (refugios,
                            desalojos, declaratorias) — hoy vía archivo manual
                            `motor/observados.json`; mañana vía Aleph Sonar.

Reglas de fusión (no es promedio — el riesgo se compone):
  * la peor señal creíble manda (max)
  * convergencia: lluvia fuerte sobre terreno vulnerable escala un nivel
  * lo observado solo ESCALA (piso mínimo), nunca des-escala
  * toda bandera carga su evidencia (señal, valor, fuente)

Salida: bandera en el vocabulario de Protección Civil
  VERDE (normal) · AMARILLA (vigila) · NARANJA (actúa) · ROJA (emergencia)
  + AZUL como anotación de aviso ciclónico lejano.

Contrato pensado para consumirse después desde Hamilton (tool de Sherlock)
o Sonar: JSON por objetivo con {bandera, señales, evidencia, accion}.
Solo stdlib — sin dependencias.
"""
import json
import math
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "AlephClimometro/0.1 (motor integral; contacto@alephri.com)"}

# ── Umbrales (idénticos a CLIMA_THRESHOLDS del portal) ───────────────────
UMBRALES = {
    "lluvia": (15, 30),      # mm/día  → amarilla, naranja-física
    "viento": (40, 60),      # km/h sostenido
    "rafaga": (60, 85),      # km/h
    "calor":  (42, 46),      # °C
}
GLOFAS_RATIO = (2.0, 4.0)    # descarga/mediana31d → señal 1, señal 2

# ── Matriz SIAT-CT de acercamiento (manual oficial SINAPROC) ─────────────
SIAT_BINS = [72, 60, 48, 36, 24, 18, 12, 6]
SIAT_ACERCAMIENTO = [
    ["A", "V", "V", "V", "V", "Y", "Y", "N", "R"],
    ["A", "V", "V", "V", "Y", "Y", "N", "N", "R"],
    ["A", "V", "V", "Y", "Y", "N", "N", "R", "R"],
    ["A", "V", "Y", "Y", "N", "N", "R", "R", "R"],
    ["A", "Y", "Y", "N", "N", "R", "R", "R", "R"],
    ["A", "Y", "Y", "N", "R", "R", "R", "R", "R"],
]
SIAT_RADIO = [200, 220, 240, 260, 280, 300]  # km por escala
SIAT_NOMBRE = {"A": "AZUL·aviso", "V": "VERDE·prevención", "Y": "AMARILLA·preparación",
               "N": "NARANJA·alarma", "R": "ROJA·afectación"}
# SIAT → nivel integral (0 verde, 1 amarilla, 2 naranja, 3 roja)
SIAT_A_NIVEL = {"A": 0, "V": 0, "Y": 1, "N": 2, "R": 3}

BANDERAS = ["VERDE", "AMARILLA", "NARANJA", "ROJA"]
ACCIONES = {
    0: "Operación normal. Monitoreo de rutina.",
    1: "Vigila: revisa pronóstico antes de despachar; confirma rutas con transportistas.",
    2: "Actúa: activa comité regional, reprograma embarques expuestos, notifica a sitios.",
    3: "Emergencia: suspende operación en zona, resguardo de personal, protocolo de crisis.",
}


def _get(url, timeout=45, intentos=3):
    for i in range(intentos):
        try:
            req = urllib.request.Request(url, headers=UA)
            return json.loads(urllib.request.urlopen(req, timeout=timeout).read())
        except Exception as e:
            if i == intentos - 1:
                raise
            time.sleep(2 * (i + 1))


def km(lat1, lng1, lat2, lng2):
    kx = 111 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot((lng2 - lng1) * kx, (lat2 - lat1) * 111)


def pt_seg_km(plat, plng, alat, alng, blat, blng):
    lat_avg = (alat + blat + plat) / 3
    kx = 111 * math.cos(math.radians(lat_avg)); ky = 111
    px, py = plng * kx, plat * ky
    ax, ay = alng * kx, alat * ky
    bx, by = blng * kx, blat * ky
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def punto_en_geom(lat, lng, geom):
    def en_anillo(ring):
        dentro = False
        j = len(ring) - 1
        for i in range(len(ring)):
            xi, yi = ring[i][0], ring[i][1]
            xj, yj = ring[j][0], ring[j][1]
            if (yi > lat) != (yj > lat) and lng < (xj - xi) * (lat - yi) / (yj - yi) + xi:
                dentro = not dentro
            j = i
        return dentro
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    for poly in polys:
        if en_anillo(poly[0]) and all(not en_anillo(h) for h in poly[1:]):
            return True
    return False


# ── Fuentes en vivo ──────────────────────────────────────────────────────

def cargar_open_meteo(objetivos):
    lats = ",".join(f"{o['lat']:.4f}" for o in objetivos)
    lngs = ",".join(f"{o['lng']:.4f}" for o in objetivos)
    url = ("https://api.open-meteo.com/v1/forecast?latitude=" + lats + "&longitude=" + lngs
           + "&daily=precipitation_sum,precipitation_probability_max,wind_speed_10m_max,"
             "wind_gusts_10m_max,temperature_2m_max,weather_code"
           + "&timezone=America%2FMexico_City&forecast_days=7")
    d = _get(url)
    return d if isinstance(d, list) else [d]


def cargar_glofas(objetivos):
    lats = ",".join(f"{o['lat']:.4f}" for o in objetivos)
    lngs = ",".join(f"{o['lng']:.4f}" for o in objetivos)
    url = ("https://flood-api.open-meteo.com/v1/flood?latitude=" + lats + "&longitude=" + lngs
           + "&daily=river_discharge&past_days=31&forecast_days=7")
    try:
        d = _get(url)
        return d if isinstance(d, list) else [d]
    except Exception:
        return [None] * len(objetivos)


NHC_BASE = ("https://mapservices.weather.noaa.gov/tropical/rest/services/tropical/"
            "NHC_tropical_weather/MapServer")


def _nhc_layer(bin_):  # points layer id por slot
    cuenca, n = bin_[:2], int(bin_[2:]) - 1
    base = 6 if cuenca == "AT" else 136
    return base + 26 * n


def cargar_nhc():
    """Tormentas activas: CurrentStorms.json (sin CORS server-side) → puntos
    de pronóstico por slot del MapServer."""
    tormentas = []
    try:
        cur = _get("https://www.nhc.noaa.gov/CurrentStorms.json")
        activos = cur.get("activeStorms", [])
    except Exception:
        activos = None
    bins = ([s.get("binNumber") for s in activos if s.get("binNumber")]
            if activos is not None else
            [c + str(i) for c in ("AT", "EP") for i in range(1, 6)])
    for b in bins:
        if not (b.startswith("AT") or b.startswith("EP")):
            continue
        try:
            fc = _get(NHC_BASE + f"/{_nhc_layer(b)}/query?where=1%3D1&outFields=*&f=geojson")
        except Exception:
            continue
        feats = fc.get("features", [])
        if not feats:
            continue
        pts = sorted([f for f in feats if f["properties"].get("tau") is not None],
                     key=lambda f: f["properties"]["tau"])
        p0 = pts[0]["properties"] if pts else {}
        tormentas.append({
            "bin": b,
            "nombre": p0.get("stormname", "Ciclón"),
            "tipo": p0.get("stormtype", ""),
            "categoria": max((f["properties"].get("ssnum") or 0) for f in pts) if pts else 0,
            "puntos": [{"tau": f["properties"]["tau"],
                        "lat": f["geometry"]["coordinates"][1],
                        "lng": f["geometry"]["coordinates"][0],
                        "ss": f["properties"].get("ssnum") or 0} for f in pts],
        })
    return tormentas


def cargar_usgs(dias=7, minmag=4.5):
    fin = datetime.now(timezone.utc)
    url = ("https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson"
           f"&starttime={(fin.timestamp() - dias*86400):.0f}"
           "&minlatitude=14&maxlatitude=33&minlongitude=-118&maxlongitude=-86"
           f"&minmagnitude={minmag}&orderby=time")
    # starttime como epoch no es válido en USGS — usar ISO
    ini = datetime.fromtimestamp(fin.timestamp() - dias * 86400, tz=timezone.utc)
    url = ("https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson"
           f"&starttime={ini.date().isoformat()}"
           "&minlatitude=14&maxlatitude=33&minlongitude=-118&maxlongitude=-86"
           f"&minmagnitude={minmag}&orderby=time")
    try:
        return _get(url).get("features", [])
    except Exception:
        return []


# ── Contexto estático ────────────────────────────────────────────────────

def cargar_estaticos():
    est = {}
    est["puntos"] = json.load(open(RAIZ / "data/puntos_inundacion.json"))["features"]
    est["cenapred"] = json.load(open(RAIZ / "data/inundacion.json"))["features"]
    return est


def contexto_terreno(lat, lng, est, radio_km=15):
    cerca = 0
    cuerpo = None
    mejor = 1e9
    for f in est["puntos"]:
        lo, la = f["geometry"]["coordinates"]
        if abs(la - lat) > 0.3 or abs(lo - lng) > 0.3:
            continue
        d = km(lat, lng, la, lo)
        if d <= radio_km:
            cerca += 1
            if d < mejor:
                mejor = d
                cuerpo = f["properties"].get("CUERPO_AGU")
    peligro = None
    rango = {"Medio": 1, "Alto": 2, "Muy alto": 3}
    for f in est["cenapred"]:
        if punto_en_geom(lat, lng, f["geometry"]):
            r = rango.get(f["properties"].get("PELIGRO_IN"), 0)
            if peligro is None or r > rango.get(peligro, 0):
                peligro = f["properties"]["PELIGRO_IN"]
    return {"puntos_criticos": cerca, "cuerpo_cercano": cuerpo,
            "cenapred": peligro,
            "vulnerable": cerca > 0 or (peligro in ("Alto", "Muy alto"))}


# ── Señales ──────────────────────────────────────────────────────────────

def senal_fisica(daily, dia=0):
    """Nivel 0/1/2 + razones, día `dia` del pronóstico."""
    if not daily:
        return {"nivel": 0, "razones": [], "causa": None}
    g = lambda k: (daily.get(k) or [None] * 7)[dia]
    lluvia, viento = g("precipitation_sum") or 0, g("wind_speed_10m_max") or 0
    rafaga, tmax, code = g("wind_gusts_10m_max"), g("temperature_2m_max"), g("weather_code")
    razones, nivel, causa = [], 0, None

    def sube(n, txt, c):
        nonlocal nivel, causa
        razones.append(txt)
        if n > nivel:
            nivel, causa = n, c
    for val, (a, r), fmt, c in [
        (lluvia, UMBRALES["lluvia"], "{:.0f} mm de lluvia", "lluvia"),
        (viento, UMBRALES["viento"], "viento {:.0f} km/h", "viento"),
        (rafaga, UMBRALES["rafaga"], "ráfagas {:.0f} km/h", "viento"),
        (tmax, UMBRALES["calor"], "calor {:.0f}°C", "calor"),
    ]:
        if val is None:
            continue
        if val >= r:
            sube(2, fmt.format(val), c)
        elif val >= a:
            sube(1, fmt.format(val), c)
    if code is not None and nivel == 0:
        if code >= 95:
            sube(1, "tormenta eléctrica", "visibilidad")
        elif 45 <= code < 51:
            sube(1, "niebla", "visibilidad")
    return {"nivel": nivel, "razones": razones, "causa": causa}


def senal_siat(lat, lng, tormentas):
    mejor = None
    for t in tormentas:
        pts = t["puntos"]
        if len(pts) < 2:
            continue
        escala = max(0, min(5, t["categoria"]))
        d0, minD, minTau = None, 1e9, None
        for p in pts:
            d = km(lat, lng, p["lat"], p["lng"])
            if p["tau"] == 0:
                d0 = d
            if d < minD:
                minD, minTau = d, p["tau"]
        if minD > 500:
            continue
        acercandose = d0 is None or minTau > 0
        if not acercandose:
            code = "Y" if d0 <= 150 else ("V" if d0 <= 300 else "A")
        elif minD > SIAT_RADIO[escala]:
            code = "A"
        else:
            col = 0
            while col < len(SIAT_BINS) and minTau < SIAT_BINS[col]:
                col += 1
            col = 0 if minTau >= 72 else col
            code = SIAT_ACERCAMIENTO[escala][min(col, 8)]
        cand = {"code": code, "nombre": SIAT_NOMBRE[code], "nivel": SIAT_A_NIVEL[code],
                "tormenta": t["nombre"], "dist_km": round(minD), "horas": minTau,
                "acercandose": acercandose}
        if mejor is None or cand["nivel"] > mejor["nivel"]:
            mejor = cand
    return mejor


def senal_hidro(flood):
    if not flood or not flood.get("daily", {}).get("river_discharge"):
        return {"nivel": 0, "ratio": None}
    serie = flood["daily"]["river_discharge"]
    pasado = sorted(v for v in serie[:31] if v is not None)
    if len(pasado) < 10:
        return {"nivel": 0, "ratio": None}
    mediana = pasado[len(pasado) // 2]
    futuro = [v for v in serie[31:] if v is not None]
    fmax = max(futuro) if futuro else 0
    if mediana <= 0.5 or fmax <= 5:
        return {"nivel": 0, "ratio": None}
    ratio = fmax / mediana
    nivel = 2 if ratio >= GLOFAS_RATIO[1] else (1 if ratio >= GLOFAS_RATIO[0] else 0)
    return {"nivel": nivel, "ratio": round(ratio, 1), "max_m3s": round(fmax, 1)}


def senal_observada(lat, lng, observados, radio_km=40):
    """Respuesta institucional confirmada cerca del objetivo. Hoy: archivo
    manual motor/observados.json; mañana: query a Sonar (misma forma)."""
    PISO = {"aviso_pc": 1, "comite": 2, "refugio": 2, "desalojo": 2,
            "declaratoria": 3, "evacuacion": 3}
    mejor = None
    for ev in observados:
        if km(lat, lng, ev["lat"], ev["lng"]) > ev.get("radio_km", radio_km):
            continue
        piso = PISO.get(ev.get("tipo"), 1)
        if mejor is None or piso > mejor["piso"]:
            mejor = {"piso": piso, "tipo": ev["tipo"],
                     "detalle": ev.get("detalle", ""), "fuente": ev.get("fuente", "manual")}
    return mejor


# ── Fusión ───────────────────────────────────────────────────────────────

def fusionar(objetivo, daily, flood, tormentas, est, observados, dia=0):
    fis = senal_fisica(daily, dia)
    siat = senal_siat(objetivo["lat"], objetivo["lng"], tormentas)
    hid = senal_hidro(flood)
    terr = contexto_terreno(objetivo["lat"], objetivo["lng"], est)
    obs = senal_observada(objetivo["lat"], objetivo["lng"], observados)

    evidencia = []
    nivel = fis["nivel"]
    if fis["razones"]:
        evidencia.append(("física", " · ".join(fis["razones"]), "Open-Meteo"))
    if siat:
        nivel = max(nivel, siat["nivel"])
        evidencia.append(("ciclón", f"SIAT-CT est. {siat['nombre']} — {siat['tormenta']}"
                          f" a {siat['dist_km']} km (~{siat['horas']} h)", "NHC"))
    if hid["nivel"] > 0:
        nivel = max(nivel, hid["nivel"] if hid["nivel"] >= 2 else 1)
        evidencia.append(("hidrología", f"descarga {hid['ratio']}× la mediana 31d", "GloFAS"))

    # convergencia: lluvia relevante sobre terreno vulnerable escala un nivel
    convergio = False
    if terr["vulnerable"] and fis["causa"] == "lluvia" and fis["nivel"] >= 1 and nivel < 3:
        extra = hid["nivel"] > 0
        if fis["nivel"] == 2 or extra:
            nivel += 1
            convergio = True
            det = []
            if terr["puntos_criticos"]:
                det.append(f"{terr['puntos_criticos']} puntos críticos CONAGUA a <15 km"
                           + (f" ({terr['cuerpo_cercano']})" if terr["cuerpo_cercano"] else ""))
            if terr["cenapred"]:
                det.append(f"peligro municipal {terr['cenapred']} (CENAPRED)")
            evidencia.append(("convergencia", "lluvia sobre terreno vulnerable: "
                              + " · ".join(det), "CONAGUA/CENAPRED"))

    # lo observado solo escala — piso institucional. Si corrobora el nivel
    # ya alcanzado, también cuenta como evidencia (refuerza la confianza).
    if obs:
        nivel = max(nivel, obs["piso"])
        evidencia.append(("observado", f"{obs['tipo']}: {obs['detalle']}", obs["fuente"]))

    nivel = max(0, min(3, nivel))
    return {
        "objetivo": objetivo["nombre"],
        "lat": objetivo["lat"], "lng": objetivo["lng"],
        "bandera": BANDERAS[nivel],
        "nivel": nivel,
        "accion": ACCIONES[nivel],
        "senales": {"fisica": fis, "siat": siat, "hidrologia": hid,
                    "terreno": terr, "observado": obs},
        "convergencia": convergio,
        "evidencia": [{"senal": s, "detalle": d, "fuente": f} for s, d, f in evidencia],
    }


def evaluar(objetivos, dia=0, tormentas=None, observados=None, verbose=False):
    """Corre el motor completo sobre una lista de objetivos [{nombre,lat,lng}]."""
    est = cargar_estaticos()
    if verbose:
        print(f"· estáticos: {len(est['puntos'])} puntos críticos, {len(est['cenapred'])} municipios CENAPRED")
    daily = cargar_open_meteo(objetivos)
    if verbose:
        print(f"· Open-Meteo: {len(daily)} pronósticos")
    flood = cargar_glofas(objetivos)
    if tormentas is None:
        tormentas = cargar_nhc()
    if verbose:
        print(f"· NHC: {len(tormentas)} ciclones activos: {[t['nombre'] for t in tormentas]}")
    if observados is None:
        p = RAIZ / "motor/observados.json"
        observados = json.load(open(p)) if p.exists() else []
    resultados = []
    for i, o in enumerate(objetivos):
        d = daily[i].get("daily") if i < len(daily) and daily[i] else None
        f = flood[i] if i < len(flood) else None
        resultados.append(fusionar(o, d, f, tormentas, est, observados, dia))
    return {"generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "dia": dia, "tormentas": [t["nombre"] for t in tormentas],
            "resultados": resultados}
