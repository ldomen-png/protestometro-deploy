#!/usr/bin/env python3
"""El corte — genera el mensaje de WhatsApp del servicio, 2×/día.

Este script ES el producto según el caso de uso del cliente: dos mensajes al
día (mañana y tarde) con la situación agregada por SUS 4 regiones, y mensajes
extraordinarios solo cuando algo cruza a NARANJA/ROJA. Máquina de estados:

  NORMAL      → corte verde de 3 líneas (su trabajo es existir: diligencia)
  SEGUIMIENTO → hay ciclón relevante aún sin naranja: el corte gana un bloque
  ALERTA      → algo cruzó a naranja/roja: ficha extraordinaria + cadencia SIAT
  CIERRE      → una alerta previa se degradó: se comunica el regreso a verde

Reglas duras (ver PLANTILLAS.md):
  * el mensaje se diseña para el SEGUNDO lector (el gerente que lo recibe
    reenviado): autocontenido, sin links obligatorios, una pantalla
  * el amarillo aparece en el corte pero JAMÁS genera mensaje extraordinario
  * el silencio está prohibido: si el motor falla, sale el mensaje de falla
  * siempre se anuncia la próxima revisión

Uso:
  python3 motor/corte.py                      # corte en vivo (detecta 07/16 h)
  python3 motor/corte.py --simulacro huracan  # ensayo con ciclón sintético
  python3 motor/corte.py --reset              # borra memoria de estado (pruebas)

Salidas: mensaje a stdout (formato WhatsApp), motor/out/corte_<ts>.txt,
memoria en motor/out/estado_corte.json y bitácora en motor/out/sombra.jsonl.
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import motor_integral as M
from ejercicio import tormenta_sintetica, OBSERVADOS_SIM

RAIZ = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "out"
ESTADO = OUT / "estado_corte.json"
CDMX = timezone(timedelta(hours=-6))

EMOJI = {0: "🟢", 1: "🟢", 2: "🟠", 3: "🔴"}   # el amarillo no cambia el veredicto del corte
NOMBRE = {0: "VERDE", 1: "VERDE con vigilancia", 2: "NARANJA", 3: "ROJA"}


def cargar_objetivos():
    html = open(RAIZ / "index.html", encoding="utf-8").read()
    zonas = json.loads(re.search(r"const ZONAS=(\[.*?\]);", html, re.S).group(1))
    reg_map = json.load(open(Path(__file__).resolve().parent / "regiones.json"))
    estado_a_region = {e: r for r, ests in reg_map.items() if not r.startswith("_")
                       for e in ests}
    objetivos = []
    for z in zonas:
        objetivos.append({"nombre": z["zm"], "lat": z["lat"], "lng": z["lng"],
                          "region": estado_a_region.get(z["estado"], "Centro")})
    return objetivos, [r for r in reg_map if not r.startswith("_")]


def agregar_por_region(resultados, regiones):
    agg = {r: {"nivel": 0, "alertas": [], "vigilancia": [], "seguimiento": []}
           for r in regiones}
    for r in resultados:
        reg = agg[r["region"]]
        reg["nivel"] = max(reg["nivel"], r["nivel"])
        razon = r["evidencia"][0]["detalle"] if r["evidencia"] else ""
        if r["nivel"] >= 2:
            reg["alertas"].append((r["objetivo"], r["nivel"], razon, r["accion"]))
        elif r["nivel"] == 1:
            reg["vigilancia"].append((r["objetivo"], razon))
        siat = r["senales"].get("siat")
        if siat and r["nivel"] < 2:
            reg["seguimiento"].append((r["objetivo"], siat))
    return agg


def fase_seguimiento(agg, tormentas):
    """Hay ciclón que ya toca algún objetivo (aunque sea azul/amarilla)."""
    return bool(tormentas) and any(reg["seguimiento"] for reg in agg.values())


# ── Plantillas (PLANTILLAS.md es la spec canónica) ───────────────────────

def encabezado(nivel_max, ahora, extraordinario=False):
    dias = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
    fecha = f"{dias[ahora.weekday()]} {ahora.day} {['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'][ahora.month-1]}"
    etiqueta = "ALERTA" if extraordinario else f"corte {ahora:%H:%M}"
    return f"{EMOJI[nivel_max]} *CLIMÓMETRO · {fecha} · {etiqueta}*"


def proxima_revision(ahora, nivel_max):
    if nivel_max >= 2:
        return f"Próxima actualización: {(ahora + timedelta(hours=3)):%H:%M} o antes si cambia la situación."
    prox = "16:00" if ahora.hour < 15 else "07:00 de mañana"
    return f"Próxima revisión: {prox}."


def pie(ahora):
    return f"Fuentes: SMN/Open-Meteo · NHC · USGS · GloFAS, revisadas {ahora:%H:%M}."


def mensaje_normal(agg, ahora, seguimiento_bloques):
    lineas = [encabezado(0, ahora)]
    lineas.append("Sin alertas naranja o roja en las 4 regiones."
                  if not seguimiento_bloques else
                  "Sin alertas naranja o roja; ciclón en seguimiento (abajo).")
    vig = [(reg, v) for reg, d in agg.items() for v in d["vigilancia"]]
    if vig:
        por_region = {}
        for reg, (obj, razon) in vig:
            por_region.setdefault(reg, []).append(f"{obj} ({razon})")
        partes = []
        for reg, objs in por_region.items():
            extra = f" +{len(objs)-3}" if len(objs) > 3 else ""
            partes.append(f"{reg}: " + ", ".join(objs[:3]) + extra)
        lineas.append("Vigilancia (sin acción requerida): " + " · ".join(partes) + ".")
    lineas += seguimiento_bloques
    lineas.append(proxima_revision(ahora, 0))
    lineas.append(pie(ahora))
    return "\n".join(lineas)


def bloque_seguimiento(agg, tormentas):
    if not tormentas:
        return []
    bloques = []
    for t in tormentas:
        afectados = [(obj, s) for reg in agg.values() for obj, s in reg["seguimiento"]
                     if s["tormenta"] == t["nombre"]]
        if not afectados:
            continue
        obj, s = min(afectados, key=lambda x: x[1]["dist_km"])
        tipo = {"HU": "Huracán", "TS": "Tormenta tropical", "TD": "Depresión tropical"}.get(t["tipo"], "Ciclón")
        bloques.append(f"_Seguimiento_: {tipo} *{t['nombre']}*"
                       + (f" cat. {t['categoria']}" if t["categoria"] else "")
                       + f" — punto más cercano {obj} a ~{s['dist_km']} km"
                       + (f" (~{s['horas']} h); etapa estimada {s['nombre'].split('·')[0].strip()}." if s.get("horas") is not None else "."))
    return bloques


def mensaje_alerta(agg, ahora, extraordinario):
    nivel_max = max(d["nivel"] for d in agg.values())
    lineas = [encabezado(nivel_max, ahora, extraordinario)]
    for reg, d in sorted(agg.items(), key=lambda x: -x[1]["nivel"]):
        if d["nivel"] < 2:
            continue
        lineas.append(f"*Región {reg} — {NOMBRE[d['nivel']]}*")
        for obj, nivel, razon, _ in d["alertas"][:4]:
            lineas.append(f"• {obj}: {razon}")
        if len(d["alertas"]) > 4:
            lineas.append(f"• … y {len(d['alertas']) - 4} zonas más")
        lineas.append(f"→ {d['alertas'][0][3]}")
    tranquilas = [reg for reg, d in agg.items() if d["nivel"] < 2]
    if tranquilas:
        lineas.append("Resto del país sin alerta: " + ", ".join(tranquilas) + ".")
    if extraordinario:
        lineas.append("_Responde RECIBIDO para confirmar._")
    lineas.append(proxima_revision(ahora, nivel_max))
    lineas.append(pie(ahora))
    return "\n".join(lineas)


def mensaje_cierre(previas, agg, ahora):
    lineas = [encabezado(0, ahora)]
    nombres = ", ".join(sorted(previas))
    lineas.append(f"*Cierre de alerta*: {nombres} regresa{'n' if len(previas) > 1 else ''} a nivel sin alerta.")
    lineas.append("Vigilar efectos residuales 24 h (encharcamientos, cortes de energía, crecidas menores).")
    lineas.append(proxima_revision(ahora, 0))
    lineas.append(pie(ahora))
    return "\n".join(lineas)


def mensaje_falla(ahora, error):
    return "\n".join([
        f"⚪ *CLIMÓMETRO · corte {ahora:%H:%M}*",
        "No pudimos completar la verificación de este corte (falla técnica de fuentes).",
        f"Reintentamos a las {(ahora + timedelta(minutes=30)):%H:%M} y avisamos.",
        f"_Detalle interno: {error}_",
    ])


# ── Orquestación ─────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--simulacro", choices=["huracan", "observado"])
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    if args.reset:
        ESTADO.unlink(missing_ok=True)
        print("memoria de estado borrada")
        return

    ahora = datetime.now(CDMX)
    objetivos, regiones = cargar_objetivos()
    tormentas = tormenta_sintetica() if args.simulacro else None
    observados = OBSERVADOS_SIM if args.simulacro == "observado" else None

    try:
        res = M.evaluar(objetivos, tormentas=tormentas, observados=observados)
    except Exception as e:
        texto = mensaje_falla(ahora, str(e)[:120])
        print("\n" + texto + "\n")
        return
    # re-inyectar región en los resultados (evaluar no la conoce)
    reg_de = {o["nombre"]: o["region"] for o in objetivos}
    for r in res["resultados"]:
        r["region"] = reg_de.get(r["objetivo"], "Centro")

    agg = agregar_por_region(res["resultados"], regiones)
    nivel_max = max(d["nivel"] for d in agg.values())
    en_alerta = sorted(reg for reg, d in agg.items() if d["nivel"] >= 2)

    previo = {}
    if ESTADO.exists():
        previo = json.load(open(ESTADO))
    previas = set(previo.get("regiones_alerta", []))
    nuevas = [r for r in en_alerta if r not in previas]
    cerradas = sorted(previas - set(en_alerta))

    if nivel_max >= 2:
        fase = "ALERTA"
        texto = mensaje_alerta(agg, ahora, extraordinario=bool(nuevas))
    elif cerradas:
        fase = "CIERRE"
        texto = mensaje_cierre(cerradas, agg, ahora)
    else:
        seg = bloque_seguimiento(agg, tormentas if tormentas is not None else _tormentas_reales(res))
        fase = "SEGUIMIENTO" if seg else "NORMAL"
        texto = mensaje_normal(agg, ahora, seg)

    print(f"\n[fase: {fase}"
          + (f" · extraordinario: regiones nuevas en alerta {nuevas}" if nuevas else "")
          + "]\n")
    print(texto + "\n")

    ts = ahora.strftime("%Y%m%dT%H%M")
    (OUT / f"corte_{ts}.txt").write_text(texto)
    json.dump({"ts": ahora.isoformat(), "fase": fase, "nivel_max": nivel_max,
               "regiones_alerta": en_alerta}, open(ESTADO, "w"))
    with open(OUT / "sombra.jsonl", "a") as fh:
        fh.write(json.dumps({"t": ahora.isoformat(), "tipo": "corte", "fase": fase,
                             "nivel_max": nivel_max, "regiones_alerta": en_alerta,
                             "mensaje": texto}, ensure_ascii=False) + "\n")
    print(f"[guardado: out/corte_{ts}.txt · estado y sombra actualizados]")


def _tormentas_reales(res):
    """Reconstruye la lista mínima de tormentas desde los resultados (para el
    bloque de seguimiento cuando evaluar() las cargó internamente)."""
    vistas = {}
    for r in res["resultados"]:
        s = r["senales"].get("siat")
        if s:
            vistas.setdefault(s["tormenta"], {"nombre": s["tormenta"], "tipo": "",
                                              "categoria": 0, "puntos": [1, 2]})
    return list(vistas.values())


if __name__ == "__main__":
    main()
