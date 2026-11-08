"""Utility for estimating outdoor vendor shelf life of calamansi by ripeness and season."""
from datetime import datetime


# Seasonal baseline for ambient / outdoor market storage in the Philippines:
# Cool Dry Season (Nov - Feb): 24°C - 28°C
# Hot Dry Season (Mar - May): 29°C - 34°C (accelerated ripening & dehydration)
# Rainy Season (Jun - Oct): 26°C - 29°C + high humidity
SEASONS = {
    'cool_dry': {
        'name': 'Cool Dry Season',
        'tagalog': 'Malamig na Panahon',
        'badge': 'Cool season (Nov–Feb)',
        'temp_range': '24°C–28°C',
        'unripe': '5–7 days',
        'ripe': '2–3 days',
        'overripe': '1–2 days',
        'overripe_tagalog': '1–2 araw',
    },
    'hot_dry': {
        'name': 'Hot Dry Season',
        'tagalog': 'Tag-init',
        'badge': 'Hot season (Mar–May)',
        'temp_range': '29°C–34°C',
        'unripe': '3–5 days',
        'ripe': '1–2 days',
        'overripe': '0–1 day',
        'overripe_tagalog': '0–1 araw',
    },
    'rainy': {
        'name': 'Rainy Season',
        'tagalog': 'Tag-ulan',
        'badge': 'Rainy season (Jun–Oct)',
        'temp_range': '26°C–29°C',
        'unripe': '4–6 days',
        'ripe': '2–3 days',
        'overripe': '1 day',
        'overripe_tagalog': '1 araw',
    },
}


def get_season_key(month: int) -> str:
    """Return the season key based on scan month (1-12)."""
    if month in (11, 12, 1, 2):
        return 'cool_dry'
    elif month in (3, 4, 5):
        return 'hot_dry'
    else:
        return 'rainy'


def get_shelf_life_estimates(created_at=None, ripeness_rows=None, ambient_temp=None, location_name=None):
    """
    Compute estimated shelf life data based on scan timestamp, optional live temperature/location,
    and ripeness counts.
    
    If ambient_temp is provided (e.g. 31.5), it dynamically maps to the appropriate
    temperature tier (Cool: <28°C, Moderate/Rainy: 28°C-30°C, Hot: >30°C), while displaying
    the location badge (e.g. "Quezon City • 32°C").
    """
    if ambient_temp is not None:
        try:
            temp_val = float(ambient_temp)
            if temp_val > 30.0:
                season_key = 'hot_dry'
            elif temp_val >= 28.0:
                season_key = 'rainy'
            else:
                season_key = 'cool_dry'
            is_live_temp = True
        except (ValueError, TypeError):
            is_live_temp = False
            temp_val = None
    else:
        is_live_temp = False
        temp_val = None

    if not is_live_temp:
        if created_at is None:
            month = datetime.now().month
        elif hasattr(created_at, 'month'):
            month = created_at.month
        else:
            month = datetime.now().month
        season_key = get_season_key(month)

    base_season_info = SEASONS[season_key]
    season_info = dict(base_season_info)

    if is_live_temp:
        loc = (location_name or 'Current Location').strip()
        season_info['badge'] = f"{loc} ({temp_val:.1f}°C)"
        season_info['temp_range'] = f"{temp_val:.1f}°C"
        season_info['is_live'] = True
    else:
        season_info['is_live'] = False

    # Map counts by ripeness key
    counts = {}
    if ripeness_rows:
        for row in ripeness_rows:
            key = row.get('key')
            count = row.get('count')
            if key:
                counts[key] = count

    estimates = [
        {
            'key': 'unripe',
            'label': 'Unripe',
            'label_tagalog': 'Hilaw',
            'count': counts.get('unripe'),
            'shelf_life': season_info['unripe'],
            'status_class': 'shelf-life-unripe',
        },
        {
            'key': 'ripe',
            'label': 'Ripe',
            'label_tagalog': 'Hinog',
            'count': counts.get('ripe'),
            'shelf_life': season_info['ripe'],
            'status_class': 'shelf-life-ripe',
        },
        {
            'key': 'overripe',
            'label': 'Overripe',
            'label_tagalog': 'Sobrang Hinog',
            'count': counts.get('overripe'),
            'shelf_life': season_info['overripe'],
            'shelf_life_tagalog': season_info['overripe_tagalog'],
            'status_class': 'shelf-life-overripe',
        },
    ]

    return {
        'season': season_info,
        'estimates': estimates,
        'ambient_storage_note': 'Assumes shaded storage, no refrigerator.',
        'ambient_storage_note_tagalog': 'Nakalagay sa lilim, walang refrigerator.',
        'advisory': 'Heat and direct sunlight may shorten shelf life.',
        'advisory_tagalog': 'Maaaring umikli ang tagal kung mainit o naarawan.',
        'disclaimer': 'Sample values only — not a validated prediction.',
        'disclaimer_tagalog': 'Tantiya lamang — hindi garantisadong prediksiyon.',
    }

