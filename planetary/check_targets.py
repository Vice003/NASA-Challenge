"""
Prueft eine Zielsignatur-Datei (planetary/targets.json) gegen die Spezifikation in ZIELSIGNATUREN.md.
Braucht nur Python, keine Zusatzpakete.

Aufruf:  python check_targets.py planetary/targets.json
Ausgabe: FEHLER (muss behoben werden), WARNUNG (pruefen), Uebersicht welche Werte noch fehlen.
Exit-Code 1, wenn es Fehler gibt.
"""

import json
import math
import sys

FEATURES = {
    # Schluessel: (Einheit, Methode, erlaubter Bereich)
    "slope_p50": ("deg", "direct", (0, 90)),
    "slope_p90": ("deg", "direct", (0, 90)),
    "relief": ("m", "direct", (0, 30000)),
    "albedo": ("1", "direct", (0, 1)),
    "thermal_inertia": ("J m-2 K-1 s-1/2", "quantile", (0, 5000)),
    "dust_opacity": ("1", "quantile", (0, 20)),
    "dust_storm_days": ("d/yr", "quantile", (0, 700)),
    "surface_temp_mean": ("K", "direction", (20, 400)),
    "surface_temp_min": ("K", "direction", (10, 400)),
    "diurnal_range": ("K", "direction", (0, 400)),
    "pressure": ("hPa", "direction", (0, 2000)),
    "wind_mean": ("m/s", "direction", (0, 100)),
    "precip": ("mm/yr", "direction", (0, 20000)),
    "humidity": ("g/kg", "direction", (0, 50)),
    "ndvi": ("1", "direction", (-1, 1)),
    "ground_ice": ("1", "direction", (0, 1)),
    "sun_elevation_max": ("deg", "direct", (0, 90)),
}
TERRAIN = {"slope_p50", "slope_p90", "relief"}
BASELINE = {"Moon": 100, "Mars": 463}
TARGET_IDS = {"shackleton": "Moon", "jezero": "Mars", "arcadia": "Mars"}
FIELDS = {"value", "p10", "p90", "unit", "baseline_m", "body_percentile", "source", "notes"}

errors, warnings = [], []
err = lambda m: errors.append(m)
warn = lambda m: warnings.append(m)


def num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def main(path):
    try:
        data = json.load(open(path, encoding="utf-8"))
    except FileNotFoundError:
        sys.exit(f"Datei nicht gefunden: {path}")
    except json.JSONDecodeError as e:
        sys.exit(f"FEHLER: Kein gueltiges JSON ({e}). Datei in einem JSON-Validator pruefen.")

    if data.get("schema_version") != 1:
        err("schema_version muss 1 sein")
    targets = data.get("targets")
    if not isinstance(targets, dict) or not targets:
        err("'targets' fehlt oder ist leer")
        return report({})

    summary = {}
    for tid, t in targets.items():
        where = f"[{tid}]"
        if tid not in TARGET_IDS:
            err(f"{where} unbekannte Ziel-ID. Erlaubt: {', '.join(TARGET_IDS)}")
            continue
        body = t.get("body")
        if body != TARGET_IDS[tid]:
            err(f"{where} body muss '{TARGET_IDS[tid]}' sein, ist '{body}'")
        for k in ("center_lat", "center_lon"):
            if not num(t.get(k)):
                err(f"{where} {k} fehlt oder ist keine Zahl")
        if num(t.get("center_lat")) and not -90 <= t["center_lat"] <= 90:
            err(f"{where} center_lat ausserhalb -90..90")
        if "Koordinaten der Ecken hier eintragen" in str(t.get("region", "")):
            warn(f"{where} region noch nicht beschrieben (Polygon-Ecken eintragen)")

        feats = t.get("features", {})
        filled, missing = [], []
        for key, f in feats.items():
            w = f"{where} {key}:"
            if key not in FEATURES:
                err(f"{w} unbekannter Merkmalsschluessel. Erlaubt: {', '.join(FEATURES)}")
                continue
            unit, method, (lo, hi) = FEATURES[key]
            extra = set(f) - FIELDS
            if extra:
                err(f"{w} unbekannte Felder {sorted(extra)}")
            if f.get("unit") != unit:
                err(f"{w} unit muss '{unit}' sein, ist '{f.get('unit')}'")
            v = f.get("value")
            if v is None:
                missing.append(key)
                continue
            if not num(v):
                err(f"{w} value muss eine Zahl oder null sein")
                continue
            if not lo <= v <= hi:
                err(f"{w} value {v} ausserhalb des plausiblen Bereichs {lo}..{hi} {unit}")
            if not str(f.get("source", "")).strip():
                err(f"{w} value gesetzt, aber source leer. Quelle angeben oder value auf null setzen")
            if "Quelle offen" in str(f.get("source", "")):
                warn(f"{w} Wert aus pipeline.py vorbelegt, Quelle noch offen")
            p10, p90 = f.get("p10"), f.get("p90")
            if (p10 is None) != (p90 is None):
                err(f"{w} p10 und p90 nur gemeinsam angeben")
            elif p10 is not None:
                if not (num(p10) and num(p90)):
                    err(f"{w} p10/p90 muessen Zahlen sein")
                elif not p10 <= v <= p90:
                    err(f"{w} erwartet p10 <= value <= p90, ist {p10} / {v} / {p90}")
            if key in TERRAIN:
                b = f.get("baseline_m")
                if not num(b):
                    err(f"{w} baseline_m fehlt (Gelaende braucht die Basislaenge in Metern)")
                elif body in BASELINE and b != BASELINE[body]:
                    warn(f"{w} baseline_m {b} weicht vom Teamplan ab ({BASELINE[body]} m fuer {body}); "
                         f"ohne passendes Erdmerkmal wird es uebersprungen")
            if method == "quantile":
                bp = f.get("body_percentile")
                if not num(bp) or not 0 <= bp <= 1:
                    err(f"{w} Methode 'quantile' braucht body_percentile zwischen 0 und 1 "
                        f"(flaechengewichtet ueber den ganzen Himmelskoerper)")
            filled.append(key)
        summary[tid] = (filled, missing)
    return report(summary)


def report(summary):
    for tid, (filled, missing) in summary.items():
        print(f"{tid:11s} {len(filled):2d} Werte gesetzt, {len(missing):2d} offen"
              + (f": {', '.join(missing)}" if missing else ""))
    print()
    for m in errors:
        print("FEHLER  ", m)
    for m in warnings:
        print("WARNUNG ", m)
    print(f"\n{len(errors)} Fehler, {len(warnings)} Warnungen")
    return 1 if errors else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Aufruf: python check_targets.py planetary/targets.json")
    sys.exit(main(sys.argv[1]))
