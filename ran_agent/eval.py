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
