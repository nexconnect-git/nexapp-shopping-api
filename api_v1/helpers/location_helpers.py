def parse_lat_lng(query_params):
    try:
        return float(query_params['lat']), float(query_params['lng'])
    except (KeyError, TypeError, ValueError):
        return None, None
