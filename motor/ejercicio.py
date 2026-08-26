#!/usr/bin/env python3
"""Ejercicios del motor integral — para probar y calibrar el algoritmo.

  python3 motor/ejercicio.py --hoy                # snapshot en vivo (79 ZMs + sitios demo)
  python3 motor/ejercicio.py --hoy --solo-sitios  # solo los sitios demo
  python3 motor/ejercicio.py --simulacro huracan  # ciclón sintético cat.4 → Acapulco
  python3 motor/ejercicio.py --simulacro observado# + refugios abiertos (piso institucional)
  python3 motor/ejercicio.py --sombra             # corre y APPENDEA al log de modo sombra

Cada corrida escribe motor/out/ejercicio_<ts>.json (evidencia completa) y el
modo sombra appendea motor/out/sombra.jsonl — el registro con el que después
mediremos precisión y anticipación contra lo que realmente ocurrió.
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import motor_integral as M

RAIZ = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "out"

COLOR = {"VERDE": "\033[32m", "AMARILLA": "\033[33m", "NARANJA": "\033[38;5;208m",
         "ROJA": "\033[31m"}
RESET = "\033[0m"

# Sitios demo con perfil de cliente (tipo Coppel/PMI): costa Pacífico, Golfo,
# sureste, norte y centro — deliberadamente contrastantes en vulnerabilidad.
SITIOS_DEMO = [
    {"nombre": "SITIO·Planta Monterrey", "lat": 25.68, "lng": -100.31},
    {"nombre": "SITIO·CEDIS Cuautitlán", "lat": 19.67, "lng": -99.18},
    {"nombre": "SITIO·CEDIS Villahermosa", "lat": 17.99, "lng": -92.93},
    {"nombre": "SITIO·Sucursal Acapulco", "lat": 16.86, "lng": -99.88},
    {"nombre": "SITIO·CEDIS Mérida", "lat": 20.97, "lng": -89.62},
    {"nombre": "SITIO·Oficina La Paz", "lat": 24.14, "lng": -110.31},
]


def cargar_zonas():
    html = open(RAIZ / "index.html", encoding="utf-8").read()
    zonas = json.loads(re.search(r"const ZONAS=(\[.*?\]);", html, re.S).group(1))
    return [{"nombre": z["zm"], "lat": z["lat"], "lng": z["lng"]} for z in zonas]


def tormenta_sintetica():
    """Huracán cat. 4 sintético con trayectoria a Acapulco, impacto ~30 h."""
    tray = [(0, 13.0, -95.4, 4), (12, 14.4, -97.0, 4), (24, 15.8, -98.6, 4),
            (36, 17.0, -99.9, 3), (48, 18.0, -100.8, 1)]
    return [{
        "bin": "EP9", "nombre": "Simulacro", "tipo": "HU", "categoria": 4,
        "puntos": [{"tau": t, "lat": la, "lng": lo, "ss": ss} for t, la, lo, ss in tray],
    }]


OBSERVADOS_SIM = [
    {"tipo": "refugio", "lat": 16.86, "lng": -99.88, "radio_km": 50,
     "detalle": "PC Guerrero abre 12 refugios en Acapulco", "fuente": "PC Guerrero (sim)"},
    {"tipo": "declaratoria", "lat": 17.55, "lng": -99.5, "radio_km": 60,
     "detalle": "Declaratoria de emergencia en 5 municipios", "fuente": "CNPC (sim)"},
]


def imprimir(res, solo_alertas=False):
    orden = sorted(res["resultados"], key=lambda r: -r["nivel"])
    print(f"\n{'='*74}")
    print(f"  NIVEL OPERATIVO INTEGRAL · {res['generado']} · día +{res['dia']}")
    print(f"  ciclones activos: {', '.join(res['tormentas']) or 'ninguno'}")
    print(f"{'='*74}")
    conteo = {}
    for r in orden:
        conteo[r["bandera"]] = conteo.get(r["bandera"], 0) + 1
    print("  " + " · ".join(f"{COLOR[b]}{b} {n}{RESET}" for b, n in
                            sorted(conteo.items(), key=lambda x: -BANDERA_NIVEL[x[0]])))
    print(f"{'-'*74}")
    for r in orden:
        if solo_alertas and r["nivel"] == 0:
            continue
        c = COLOR[r["bandera"]]
        print(f"  {c}{'●'} {r['bandera']:<9}{RESET} {r['objetivo']}")
        for ev in r["evidencia"]:
            print(f"      · [{ev['senal']}] {ev['detalle']}  ({ev['fuente']})")
        if r["nivel"] >= 2:
            print(f"      → {r['accion']}")
    verdes = sum(1 for r in orden if r["nivel"] == 0)
    if solo_alertas and verdes:
        print(f"  … y {verdes} objetivos en VERDE")


BANDERA_NIVEL = {b: i for i, b in enumerate(M.BANDERAS)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hoy", action="store_true")
    ap.add_argument("--dia", type=int, default=0, help="día del pronóstico (0=hoy)")
    ap.add_argument("--solo-sitios", action="store_true")
    ap.add_argument("--solo-alertas", action="store_true")
    ap.add_argument("--simulacro", choices=["huracan", "observado"])
    ap.add_argument("--sombra", action="store_true")
    args = ap.parse_args()

    objetivos = SITIOS_DEMO if args.solo_sitios else cargar_zonas() + SITIOS_DEMO
    tormentas = None
    observados = None
    etiqueta = "hoy"
    if args.simulacro:
        tormentas = tormenta_sintetica()
        etiqueta = f"simulacro-{args.simulacro}"
        if args.simulacro == "observado":
            observados = OBSERVADOS_SIM
    print(f"Motor integral · ejercicio '{etiqueta}' · {len(objetivos)} objetivos …")
    res = M.evaluar(objetivos, dia=args.dia, tormentas=tormentas,
                    observados=observados, verbose=True)
    res["ejercicio"] = etiqueta
    imprimir(res, solo_alertas=args.solo_alertas)

    OUT.mkdir(exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    destino = OUT / f"ejercicio_{ts}_{etiqueta}.json"
    json.dump(res, open(destino, "w"), ensure_ascii=False, indent=1)
    print(f"\n  evidencia completa → {destino.relative_to(RAIZ)}")
    if args.sombra:
        with open(OUT / "sombra.jsonl", "a") as fh:
            for r in res["resultados"]:
                fh.write(json.dumps({"t": res["generado"], "o": r["objetivo"],
                                     "b": r["bandera"],
                                     "ev": [e["detalle"] for e in r["evidencia"]]},
                                    ensure_ascii=False) + "\n")
        print(f"  modo sombra: appendeado a {(OUT / 'sombra.jsonl').relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
