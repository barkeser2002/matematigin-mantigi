"""ML'siz tek-stroke geometri tanıma (numpy). Qt bağımlılığı yok.

recognize(points): Nx2 veya Nx3 (x,y,t). t saklanmaz/kullanılmaz.
Tipler: line, circle, ellipse, triangle, rectangle, polygon, unknown.
Kapalılık, dönüşüm ve uygulama kuralları correct_stroke ile geometry_items içindedir.
Güven skoru sezgiseldir; kalibre edilmiş olasılık DEĞİLDİR.
"""
import numpy as np

CONFIDENCE_THRESHOLD = 0.68
MAX_INPUT_POINTS = 8000
RESAMPLE_POINTS = 192


def _unknown(confidence=0., reason='no_fit'):
    return {'type': 'unknown', 'confidence': float(np.clip(confidence, 0., 1.)),
            'params': {'reason': reason}}


def _resample(p, n=RESAMPLE_POINTS):
    lengths = np.r_[0., np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]
    keep = np.r_[True, np.diff(lengths) > 1e-9]
    p, lengths = p[keep], lengths[keep]
    if len(p) < 2 or lengths[-1] < 1e-9:
        return p
    u = np.linspace(0., lengths[-1], n)
    return np.column_stack([np.interp(u, lengths, p[:, j]) for j in range(2)])


def _smooth(p, radius=2):
    padded = np.pad(p, ((radius, radius), (0, 0)), mode='edge')
    kernel = np.r_[np.arange(1, radius+2), np.arange(radius, 0, -1)].astype(float)
    kernel /= kernel.sum()
    return np.column_stack([np.convolve(padded[:, j], kernel, mode='valid') for j in range(2)])


def _ellipse(p, diag, gap):
    """Normalize edilmiş genel konik en küçük kareleri; pozitif tanımlı elips."""
    origin = p.mean(axis=0)
    z = (p - origin) / diag
    x, y = z.T
    design = np.column_stack([x*x, x*y, y*y, x, y])
    a, _, rank, _ = np.linalg.lstsq(design, np.ones(len(p)), rcond=None)
    if rank < 5:
        return None
    q = np.array([[a[0], a[1]/2], [a[1]/2, a[2]]])
    center = -0.5 * np.linalg.solve(q, a[3:])
    level = 1. + center @ q @ center
    eig, basis = np.linalg.eigh(q / level)
    if np.min(eig) <= 0:
        return None
    radii = 1. / np.sqrt(eig)
    if min(radii) / max(radii) < 0.16 or max(radii) > 1.5:
        return None
    kind = 'circle' if min(radii)/max(radii) > 0.90 else 'ellipse'
    if kind == 'circle':
        circle, _, _, _ = np.linalg.lstsq(np.column_stack([2*x, 2*y, np.ones(len(z))]),
                                          x*x+y*y, rcond=None)
        center = circle[:2]
        radius_squared = float(circle[2] + center@center)
        if radius_squared <= 0:
            return None
        radii = np.repeat(np.sqrt(radius_squared), 2)
        basis = np.eye(2)
    local = (z - center) @ basis
    radial = np.linalg.norm(local / radii, axis=1)
    residual = float(np.sqrt(np.mean((radial - 1.)**2)))
    implicit = np.sum((local/radii)**2, axis=1)-1.
    gradient = 2*np.sqrt(np.sum((local/(radii*radii))**2, axis=1))
    geometric_rmse = float(np.sqrt(np.mean((implicit/np.maximum(gradient, 1e-9))**2)))
    angle = np.unwrap(np.arctan2(local[:, 1]/radii[1], local[:, 0]/radii[0]))
    coverage = abs(float(angle[-1]-angle[0])) / (2*np.pi)
    angular_travel = float(np.sum(np.abs(np.diff(angle)))) / (2*np.pi)
    if residual > 0.048 or not 0.82 <= coverage <= 1.12 or angular_travel > 1.25:
        return None
    confidence = np.exp(-residual / 0.14) * (1 - 0.35 * gap)
    return {'type': kind,
            'confidence': float(confidence), 'params': {
                'center': (origin + center*diag).tolist(),
                'radii': (radii*diag).tolist(),
                'rotation': float(np.arctan2(basis[1, 0], basis[0, 0])),
                'radial_residual': residual, 'relative_rmse': geometric_rmse, 'closure_gap': float(gap)}}


def _segment_distances(p, a, b):
    v = b - a
    t = np.clip((p-a) @ v / max(float(v@v), 1e-12), 0., 1.)
    return np.linalg.norm(p-a-t[:, None]*v, axis=1)


def _rdp(p, epsilon):
    """RDP indeksleri; iteratif, yüksek nokta sayısında recursion taşması yok."""
    keep = {0, len(p)-1}
    stack = [(0, len(p)-1)]
    while stack:
        lo, hi = stack.pop()
        if hi <= lo+1:
            continue
        distances = _segment_distances(p[lo+1:hi], p[lo], p[hi])
        j = int(np.argmax(distances)) + lo+1
        if distances[j-lo-1] > epsilon:
            keep.add(j)
            stack.extend([(lo, j), (j, hi)])
    return sorted(keep)


def _cross(a, b):
    return float(a[0]*b[1] - a[1]*b[0])


def _self_intersects(v):
    n = len(v)
    for i in range(n):
        a, b = v[i], v[(i+1) % n]
        for j in range(i+2, n):
            if i == 0 and j == n-1:
                continue
            c, d = v[j], v[(j+1) % n]
            if _cross(b-a, c-a)*_cross(b-a, d-a) < 0 and _cross(d-c, a-c)*_cross(d-c, b-c) < 0:
                return True
    return False


def _polygon(p, diag, gap):
    epsilon = max(2.5, 0.037 * diag)
    # Kapalı RDP iki zincire ayrılır; başlangıçtaki yapay köşe sonradan elenir.
    start = int(np.argmax(np.linalg.norm(p-p.mean(axis=0), axis=1)))
    ring = np.roll(p, -start, axis=0)
    opposite = int(np.argmax(np.linalg.norm(ring-ring[0], axis=1)))
    if opposite < 2 or opposite > len(ring)-3:
        return None
    chain = np.vstack([ring, ring[0]])
    indices = _rdp(chain[:opposite+1], epsilon)[:-1]
    indices += [opposite+i for i in _rdp(chain[opposite:], epsilon)[:-1]]
    vertices = chain[indices].copy()
    while len(vertices) > 3:
        deviations = np.array([_segment_distances(vertices[i:i+1], vertices[(i-1) % len(vertices)],
                               vertices[(i+1) % len(vertices)])[0] for i in range(len(vertices))])
        k = int(np.argmin(deviations))
        prev = vertices - np.roll(vertices, 1, axis=0)
        nxt = np.roll(vertices, -1, axis=0) - vertices
        alignment = np.sum(prev*nxt, axis=1) / np.maximum(np.linalg.norm(prev, axis=1)*np.linalg.norm(nxt, axis=1), 1e-9)
        almost_collinear = np.where((alignment > .86) & (deviations < 1.8*epsilon))[0]
        short_edge = np.where(np.linalg.norm(nxt, axis=1) < .085*diag)[0]
        if len(almost_collinear):
            k = int(almost_collinear[np.argmin(deviations[almost_collinear])])
        elif len(short_edge):
            i = int(short_edge[0])
            k = i if deviations[i] < deviations[(i+1) % len(vertices)] else (i+1) % len(vertices)
        elif deviations[k] >= epsilon:
            break
        vertices = np.delete(vertices, k, axis=0)
    n = len(vertices)
    if not 3 <= n <= 10 or _self_intersects(vertices):
        return None
    # Kenar iç kısımlarına TLS uydur, komşu doğruları kesiştir: yuvarlak köşeleri toparla.
    distances = np.column_stack([_segment_distances(p, a, b) for a, b in zip(vertices, np.roll(vertices, -1, axis=0))])
    assignment = np.argmin(distances, axis=1)
    lines = []
    for i, (a, b) in enumerate(zip(vertices, np.roll(vertices, -1, axis=0))):
        t = (p-a) @ (b-a) / max(float((b-a)@(b-a)), 1e-12)
        samples = p[(assignment == i) & (t > 0.15) & (t < 0.85)]
        if len(samples) < 3:
            return None
        center = samples.mean(axis=0)
        _, _, vt = np.linalg.svd(samples-center, full_matrices=False)
        lines.append((center, vt[0]))
    refined = []
    for i in range(n):
        a, u = lines[i-1]
        b, v = lines[i]
        system = np.column_stack([u, -v])
        if abs(np.linalg.det(system)) < 0.12:
            return None
        intersection = a + np.linalg.solve(system, b-a)[0] * u
        if np.linalg.norm(intersection - vertices[i]) > 0.12 * diag:
            return None
        refined.append(intersection)
    vertices = np.array(refined)
    if _self_intersects(vertices):
        return None
    edges = np.roll(vertices, -1, axis=0)-vertices
    lengths = np.linalg.norm(edges, axis=1)
    if lengths.min() < 0.075*diag:
        return None
    area = abs(np.sum(vertices[:, 0]*np.roll(vertices[:, 1], -1) - vertices[:, 1]*np.roll(vertices[:, 0], -1))) / 2
    if area / diag**2 < 0.035:
        return None
    residuals = np.min(np.column_stack([_segment_distances(p, a, b) for a, b in zip(vertices, np.roll(vertices, -1, axis=0))]), axis=1)
    residual = float(np.sqrt(np.mean(residuals**2)) / diag)
    if residual > 0.022 or np.quantile(residuals, .95) > max(3., .045*diag):
        return None
    unit = edges / lengths[:, None]
    angles = np.abs(np.sum(unit*np.roll(unit, -1, axis=0), axis=1))
    kind = 'triangle' if n == 3 else 'polygon'
    if n == 4 and max(angles) < 0.24:
        kind = 'rectangle'
        # Dört dik açı/karşı kenar paralelliği zorlanmış yeni dikdörtgen geometrisi.
        theta = np.arctan2(np.mean(np.sin(4*np.arctan2(unit[:, 1], unit[:, 0]))),
                           np.mean(np.cos(4*np.arctan2(unit[:, 1], unit[:, 0])))) / 4
        basis = np.array([[np.cos(theta), np.sin(theta)], [-np.sin(theta), np.cos(theta)]]).T
        local = vertices @ basis
        low, high = local.min(axis=0), local.max(axis=0)
        vertices = np.array([[low[0], low[1]], [high[0], low[1]], [high[0], high[1]], [low[0], high[1]]]) @ basis.T
    confidence = float(np.exp(-residual / 0.06) * (1-0.35*gap))
    return {'type': kind, 'confidence': confidence, 'vertices': vertices.tolist(),
            'params': {'corners': n, 'relative_rmse': residual, 'closure_gap': float(gap)}}


def recognize(points):
    """Gürültülü (x,y[,t]) noktalarını JSON uyumlu şekil sözlüğüne dönüştür.

    Geçersiz/sıfır boyutlu girişler unknown; Nx4 gibi belirsiz girdiler reddedilir.
    Kapalılık eşiği: uç uzaklığı / bbox köşegeni <= 0.18.
    """
    try:
        p = np.asarray(points, dtype=float)
        if p.ndim != 2 or p.shape[1] not in (2, 3) or len(p) < 2:
            return _unknown(reason='invalid_input')
        p = p[:, :2]
        if not np.isfinite(p).all():
            return _unknown(reason='nonfinite')
        if len(p) > MAX_INPUT_POINTS:
            p = p[np.linspace(0, len(p)-1, MAX_INPUT_POINTS).astype(int)]
        diag = float(np.linalg.norm(np.ptp(p, axis=0)))
        if diag < 10:
            return _unknown(reason='too_small')
        raw_endpoints = p[[0, -1]].copy()
        p = _smooth(_resample(_smooth(p, radius=max(1, min(8, len(p)//65)))))
        center = p.mean(axis=0)
        _, _, vt = np.linalg.svd(p - center, full_matrices=False)
        projection = (p - center) @ vt[0]
        residual = float(np.sqrt(np.mean(((p - center) @ vt[1]) ** 2)))
        extent = float(np.ptp(projection))
        endpoint_ratio = np.linalg.norm(raw_endpoints[1]-raw_endpoints[0]) / max(extent, 1e-9)
        projection_travel = float(np.sum(np.abs(np.diff(projection))) / max(extent, 1e-9))
        if extent > 8 and residual < max(1.5, diag * 0.018) and endpoint_ratio > 0.85 and projection_travel < 1.30:
            confidence = float(np.exp(-residual / max(2., diag * 0.05)))
            ends = center + np.array([[projection.min()], [projection.max()]]) * vt[0]
            if confidence >= CONFIDENCE_THRESHOLD:
                return {'type': 'line', 'confidence': confidence, 'vertices': ends.tolist(),
                        'params': {'rmse_px': residual}}
        gap = float(np.linalg.norm(raw_endpoints[1]-raw_endpoints[0]) / diag)
        if gap > 0.18:
            return _unknown(reason='open_non_line')
        ellipse = _ellipse(p, diag, gap)
        polygon = _polygon(p, diag, gap)
        if ellipse and polygon:
            # Geometrik artıkları aynı bbox biriminde karşılaştır; model parametre cezası.
            ellipse_score = ellipse['params']['relative_rmse'] + .0015
            polygon_score = polygon['params']['relative_rmse'] + .0005*polygon['params']['corners']
            result = polygon if polygon_score < ellipse_score else ellipse
        else:
            result = polygon or ellipse
        if result is not None and result['confidence'] >= CONFIDENCE_THRESHOLD:
            return result
        return _unknown(result['confidence'] if result else 0.)
    except (ValueError, TypeError, np.linalg.LinAlgError, FloatingPointError):
        return _unknown(reason='invalid_or_degenerate')


# --- Uygulama katmanı -------------------------------------------------------------------------------
# Tanıyıcı yalnız geometriyi söyler; düzeltmenin uygulanıp uygulanmayacağına burada karar verilir.

MIN_SIDE_PX = 40.0          # kısa kenar (kapalılar) / uzunluk (çizgi) bu değerin altındaysa dokunulmaz
SAMPLES_PER_ELLIPSE = 96    # döndürülmüş elips, kapalı çokgen olarak örneklenir


def correct_stroke(points):
    """Tanınan şekli döndürür; düzeltme uygulanmamalıysa None.

    Kurallar: güven eşiği (CONFIDENCE_THRESHOLD), kısa kenar/uzunluk MIN_SIDE_PX altındaysa dokunma.
    """
    try:
        p = np.asarray(points, dtype=float)
        if p.ndim != 2 or p.shape[1] < 2 or len(p) < 2:
            return None
        result = recognize(p)
    except (ValueError, TypeError):
        return None
    if result['type'] == 'unknown':
        return None
    xy = p[:, :2]
    if result['type'] == 'line':
        a, b = np.asarray(result['vertices'], float)
        if float(np.linalg.norm(b - a)) < MIN_SIDE_PX:
            return None
    else:
        width, height = np.ptp(xy, axis=0)
        if min(width, height) < MIN_SIDE_PX:
            return None
    return result


def geometry_items(result):
    """correct_stroke sonucunu core.shapes öğelerine (Poly/Oval) çevirir; tuval bunları boyar."""
    from matematigin_mantigi.core.shapes import Oval, Poly

    kind = result['type']
    if kind == 'circle':
        cx, cy = result['params']['center']
        r = float(result['params']['radii'][0])
        return [Oval(float(cx), float(cy), r, r)]
    if kind == 'ellipse':
        cx, cy = result['params']['center']
        rx, ry = result['params']['radii']
        rot = float(result['params']['rotation'])
        u = np.array([np.cos(rot), np.sin(rot)])
        v = np.array([-np.sin(rot), np.cos(rot)])
        t = np.linspace(0, 2 * np.pi, SAMPLES_PER_ELLIPSE, endpoint=False)
        pts = (np.array([cx, cy]) + rx * np.cos(t)[:, None] * u + ry * np.sin(t)[:, None] * v)
        return [Poly(tuple((float(x), float(y)) for x, y in pts), closed=True)]
    vertices = tuple((float(x), float(y)) for x, y in result['vertices'])
    if kind == 'line':
        return [Poly(vertices, closed=False)]
    return [Poly(vertices, closed=True)]
