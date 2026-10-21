"""Simple one-column row order; no spelling correction or layout inference."""
from statistics import median


def assemble(lines):
    items = []
    for line in lines:
        if not line.text.strip():
            continue
        xs, ys = zip(*line.polygon)
        items.append((min(ys), min(xs), max(ys) - min(ys), line.text.strip()))
    if not items:
        return ''
    tolerance = max(1, median(item[2] for item in items) * .5)
    rows = []
    for item in sorted(items):
        if not rows or item[0] - rows[-1][0][0] > tolerance:
            rows.append([item])
        else:
            rows[-1].append(item)
    return ' '.join(item[3] for row in rows for item in sorted(row, key=lambda x: x[1]))
