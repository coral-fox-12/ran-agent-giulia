"""Local scoring — the challenge's three error-metric families, reimplemented
in pure Python so the harness scores without heavy deps.

- word_error_rate: edit distance over whitespace tokens (lower is better).
- multi_col_acc: per-column exact-match accuracy over structured answers
  (higher is better). Numbers compare with a tolerance.
- iou_polygon_geo: intersection-over-union of two polygons (higher is better),
  via Sutherland–Hodgman clipping; uses shapely if installed, else the pure
  fallback below.
"""
import math


def word_error_rate(reference, hypothesis):
    ref = str(reference).split()
    hyp = str(hypothesis).split()
    if not ref:
        return 0.0 if not hyp else 1.0
    # Levenshtein over tokens.
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i]
        for j, h in enumerate(hyp, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1,
                           prev[j - 1] + (0 if r == h else 1)))
        prev = cur
    return prev[-1] / len(ref)


def multi_col_acc(expected, got, tol=1e-6):
    """expected/got: dicts with the same keys. Returns (accuracy, per-column)."""
    if not expected:
        return 0.0, {}
    per_col = {}
    for k, v in expected.items():
        g = got.get(k)
        if isinstance(v, (int, float)) and isinstance(g, (int, float)):
            per_col[k] = 1.0 if abs(v - g) <= tol * max(1.0, abs(v)) else 0.0
        elif isinstance(v, list) and isinstance(g, list):
            per_col[k] = 1.0 if sorted(map(str, v)) == sorted(map(str, g)) else 0.0
        else:
            per_col[k] = 1.0 if str(v).strip() == str(g).strip() else 0.0
    acc = sum(per_col.values()) / len(per_col)
    return acc, per_col


def _shoelace(poly):
    s = 0.0
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def _clip(subject, clip):
    """Sutherland–Hodgman polygon clipping (both as [(x, y), ...])."""
    def inside(p, a, b):
        return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= 0

    def intersect(p1, p2, a, b):
        d1 = (b[0] - a[0]) * (p1[1] - a[1]) - (b[1] - a[1]) * (p1[0] - a[0])
        d2 = (b[0] - a[0]) * (p2[1] - a[1]) - (b[1] - a[1]) * (p2[0] - a[0])
        if d1 == d2:
            return p2
        t = d1 / (d1 - d2)
        return (p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1]))

    out = subject
    for i in range(len(clip)):
        a, b = clip[i], clip[(i + 1) % len(clip)]
        inp, out = out, []
        if not inp:
            break
        s = inp[-1]
        for e in inp:
            if inside(e, a, b):
                if not inside(s, a, b):
                    out.append(intersect(s, e, a, b))
                out.append(e)
            elif inside(s, a, b):
                out.append(intersect(s, e, a, b))
            s = e
    return out


def polygon_iou(poly_a, poly_b):
    """poly_*: list of (x, y) vertices. Returns IoU in [0, 1]."""
    try:
        from shapely.geometry import Polygon  # type: ignore
        a, b = Polygon(poly_a), Polygon(poly_b)
        inter = a.intersection(b).area
        union = a.union(b).area
        return inter / union if union else 0.0
    except ImportError:
        inter_poly = _clip(list(poly_a), list(poly_b))
        inter = _shoelace(inter_poly) if len(inter_poly) >= 3 else 0.0
        union = _shoelace(poly_a) + _shoelace(poly_b) - inter
        return inter / union if union else 0.0


def score_task(task_type, expected, got):
    """Dispatch by task metric family. Returns a dict with the headline score."""
    from .tasks import TASK_TYPES
    metric = TASK_TYPES[task_type]["metric"]
    if metric == "multi_col_acc":
        acc, per_col = multi_col_acc(expected, got)
        return {"metric": metric, "score": acc, "per_column": per_col}
    if metric == "word_error_rate":
        return {"metric": metric,
                "score": word_error_rate(expected.get("text", ""), got.get("text", ""))}
    if metric == "iou_polygon_geo":
        return {"metric": metric,
                "score": polygon_iou(expected.get("polygon", []), got.get("polygon", []))}
    raise ValueError(f"unknown metric: {metric}")


def check_answer_quality(task_type, answer, kpis=None):
    """Internal-consistency check for a baseline/agent answer, no ground truth
    needed. Verifies the schema (tasks.validate_answer) plus per-type sanity:
    percentages in range, claims consistent with the KPIs they cite.
    Returns (ok: bool, issues: list[str])."""
    from .tasks import validate_answer, TASK_TYPES
    issues = []
    try:
        validate_answer(task_type, answer)
    except ValueError as e:
        return False, [str(e)]

    def _pct(name, v):
        if not isinstance(v, (int, float)) or not 0.0 <= v <= 100.0:
            issues.append(f"{name}={v!r} not a percentage in [0, 100]")

    if task_type == "fault_diagnosis":
        if answer["root_cause"] not in {
                "hardware", "interference", "misconfiguration",
                "propagation", "overload"}:
            issues.append(f"unknown root_cause: {answer['root_cause']!r}")
        if not answer["evidence"]:
            issues.append("evidence is empty")
    elif task_type == "outage_impact":
        _pct("coverage_loss_pct", answer["coverage_loss_pct"])
        _pct("throughput_loss_pct", answer["throughput_loss_pct"])
        if not answer["affected_cells"]:
            issues.append("affected_cells is empty")
    elif task_type == "coverage":
        _pct("coverage_pct", answer["coverage_pct"])
        poly = answer["coverage_polygon"]
        if not isinstance(poly, dict) or poly.get("type") != "Polygon":
            issues.append("coverage_polygon is not a GeoJSON Polygon")
    elif task_type == "radio_config":
        if not isinstance(answer["meets_conditions"], bool):
            issues.append("meets_conditions is not a bool")
        if answer["meets_conditions"] and not answer["kpis"]:
            issues.append("claims meets_conditions but reports no KPIs")
        if kpis is not None and answer["meets_conditions"]:
            # Cross-check the claim against the KPIs actually measured.
            bad = [c for c, kv in kpis.get("cells", {}).items()
                   if kv["rsrp_dbm"] < -100.0 or kv["sinr_db"] < 0.0]
            if bad:
                issues.append(f"claims conditions met but {bad} still violate "
                              "RSRP >= -100 dBm / SINR >= 0 dB")
    elif task_type == "site_placement":
        sites = answer["sites"]
        if not isinstance(sites, list) or not sites:
            issues.append("sites is empty")
        else:
            for s in sites:
                if not isinstance(s, dict) or "lat" not in s or "lon" not in s:
                    issues.append(f"site {s!r} lacks lat/lon")
        poly = answer["coverage_polygon"]
        if not isinstance(poly, dict) or poly.get("type") != "Polygon":
            issues.append("coverage_polygon is not a GeoJSON Polygon")
    elif task_type == "energy":
        _pct("energy_saved_pct", answer["energy_saved_pct"])
        if answer["energy_saved_pct"] > 0 and not answer["config"]:
            issues.append("claims energy saved but proposes no config change")
        if answer["energy_saved_pct"] == 0 and answer["config"]:
            issues.append("proposes a config change but claims 0% saved")
    else:
        issues.append(f"unknown task type: {task_type!r}")
    return (not issues), issues
