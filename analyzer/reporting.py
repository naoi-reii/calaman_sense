"""Report aggregation over saved scan summaries."""
from collections import Counter
from datetime import timedelta
from django.utils import timezone

RIPENESS = ('unripe', 'ripe', 'overripe')
GRADES = {'Best Quality': 4, 'Good Quality': 3, 'Average': 2, 'Rejected': 1}

def summarize(scans):
    scans = list(scans)
    total = sum(scan.fruit_count_total for scan in scans)
    weights = {key: sum(scan.fruit_count_total * getattr(scan, f'ripeness_{key}_pct') / 100 for scan in scans) for key in RIPENESS}
    classified = sum(weights.values())
    distribution = []
    offset = 0
    for key, color in zip(RIPENESS, ('#279447', '#e9b507', '#ef5350')):
        pct = weights[key] / classified * 100 if classified else 0
        distribution.append({'label': key.capitalize(), 'color': color, 'pct': round(pct, 1), 'start': offset, 'end': offset + pct})
        offset += pct
    scores = [GRADES[s.quality_grade] for s in scans if s.quality_grade in GRADES]
    average = {v: k for k, v in GRADES.items()}.get(round(sum(scores) / len(scores)), 'N/A') if scores else 'N/A'
    daily = Counter(timezone.localtime(s.created_at).date() for s in scans)
    trend = []
    if daily:
        first, last = min(daily), max(daily)
        # Keep long reporting periods readable by grouping into months.
        monthly = (last - first).days > 90
        if monthly:
            counts = Counter()
            for day, count in daily.items():
                counts[day.replace(day=1)] += count
            day, end = first.replace(day=1), last.replace(day=1)
            while day <= end:
                trend.append({'date': day.strftime('%b %Y'), 'count': counts[day]})
                day = (day.replace(day=28) + timedelta(days=4)).replace(day=1)
        else:
            day = first
            while day <= last:
                trend.append({'date': day.strftime('%b %d, %Y'), 'count': daily[day]})
                day += timedelta(days=1)
    maximum = max((point['count'] for point in trend), default=1)
    for index, point in enumerate(trend):
        point['x'] = round(35 + index * 430 / max(len(trend) - 1, 1), 2) if len(trend) > 1 else 250
        point['y'] = round(175 - point['count'] / maximum * 140, 2)
    return {
        'total_scans': len(scans), 'total_fruits': total, 'average_grade': average,
        'defect_rate': round(sum(s.fruit_count_defective for s in scans) / total * 100, 1) if total else None,
        'distribution': distribution, 'has_distribution': classified > 0, 'trend': trend,
        'trend_points': ' '.join(f"{p['x']},{p['y']}" for p in trend), 'trend_max': maximum,
        'multi_image': any(len(s.images.all()) > 1 for s in scans),
        'demo_scans': sum(s.model_version.startswith('mock') for s in scans),
    }
