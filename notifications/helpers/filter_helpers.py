def parse_optional_bool(value):
    if value is None:
        return None
    return str(value).lower() == 'true'
