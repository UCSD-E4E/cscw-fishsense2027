"""Production's expected-laser region (fishsense-services contracts laser_region.py LASER_REGION_POLYGON at db0b895,
rectified px), and its point test. Dependency-free, so it imports in any environment."""
REGION = [(1580, 570), (1700, 465), (2335, 395), (2455, 525), (2470, 1610), (2185, 1890), (1920, 1905), (1625, 1365)]


def in_region(x, y):
    """Inside the convex region, edges included (same side of every directed edge)."""
    pos = neg = False
    for i, (ax, ay) in enumerate(REGION):
        bx, by = REGION[(i + 1) % len(REGION)]
        c = (bx - ax) * (y - ay) - (by - ay) * (x - ax)
        pos |= c > 0; neg |= c < 0
    return not (pos and neg)
