"""Decode optional provider polylines without exposing malformed coordinates."""


def decode_route_geometry(encoded):
    """Return Singapore-area [latitude, longitude] points, or None.

    OneMap transit legs use encoded polylines with five decimal places.
    Limits bound work and reject incomplete components and implausible routes.
    Geometry failure must not invalidate the separate travel estimate.
    """
    if not isinstance(encoded, str) or not encoded or len(encoded) > 200000:
        return None
    index = 0
    latitude = longitude = 0
    points = []
    while index < len(encoded):
        deltas = []
        for _ in range(2):
            value = 0
            shift = 0
            while True:
                if index >= len(encoded) or shift > 30:
                    return None
                chunk = ord(encoded[index]) - 63
                index += 1
                if chunk < 0 or chunk > 63:
                    return None
                value |= (chunk & 31) << shift
                if chunk < 32:
                    break
                shift += 5
            delta = value >> 1
            if value & 1:
                delta = ~delta
            deltas.append(delta)
        latitude += deltas[0]
        longitude += deltas[1]
        point = [latitude / 100000, longitude / 100000]
        # A generous regional boundary accommodates nearby transit endpoints.
        if not 1.0 <= point[0] <= 1.7 or not 103.4 <= point[1] <= 104.6:
            return None
        points.append(point)
        if len(points) > 20000:
            return None
    if len(points) < 2:
        return None
    return points
