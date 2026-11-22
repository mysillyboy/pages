# -*- coding: utf-8 -*-
"""生成全国平面总图数据：省界多边形 + 主要河流 + 地名点 + 3D 区域框。

用法：<python> .dev/geo-china-map.py
输出：data/china-map.js（墨卡托投影，归一化到 1000×1000 ）
数据：省界 DataV.GeoAtlas；河流 Natural Earth 10m（公有领域）
"""
import io, json, math, os, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "data", "china-map.js")
CACHE = os.path.join(os.environ.get("TEMP", "."), "geo3d-cache")
os.makedirs(CACHE, exist_ok=True)
UA = {"User-Agent": "geo3d-build/1.0"}

LON0, LON1, LAT0, LAT1 = 73.2, 135.2, 15.0, 54.2
SIZE = 1000.0


def merc(lat):
    return math.degrees(math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)))


Y0, Y1 = merc(LAT1), merc(LAT0)
SCALE = SIZE / (LON1 - LON0)


def proj(lon, lat):
    x = (lon - LON0) * SCALE
    y = (merc(LAT1) - merc(lat)) * SCALE
    return x, y


H = (merc(LAT1) - merc(LAT0)) * SCALE


def get(url, name):
    p = os.path.join(CACHE, name)
    if os.path.exists(p) and os.path.getsize(p) > 32:
        return open(p, "rb").read()
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=180) as r:
        data = r.read()
    open(p, "wb").write(data)
    return data


def rdp(pts, eps):
    if len(pts) < 3:
        return pts
    a = pts[0]; b = pts[-1]
    abx, aby = b[0] - a[0], b[1] - a[1]
    L = math.hypot(abx, aby)
    if L < 1e-9:
        best, idx = 0.0, 0
        for i in range(1, len(pts) - 1):
            d = math.hypot(pts[i][0] - a[0], pts[i][1] - a[1])
            if d > best:
                best, idx = d, i
        if best > eps:
            return rdp(pts[:idx + 1], eps)[:-1] + rdp(pts[idx:], eps)
        return [pts[0], pts[-1]]
    best, idx = 0.0, 0
    for i in range(1, len(pts) - 1):
        p = pts[i]
        d = abs(abx * (p[1] - a[1]) - aby * (p[0] - a[0])) / L
        if d > best:
            best, idx = d, i
    if best > eps:
        return rdp(pts[:idx + 1], eps)[:-1] + rdp(pts[idx:], eps)
    return [pts[0], pts[-1]]


def path_from_rings(rings, eps=0.9):
    out = []
    for ring in rings:
        pts = [proj(p[0], p[1]) for p in ring]
        if len(pts) > 3 and abs(pts[0][0] - pts[-1][0]) < 1e-6 and abs(pts[0][1] - pts[-1][1]) < 1e-6:
            pts = pts[:-1]
        if len(pts) < 4:
            continue
        pts2 = rdp(pts, eps)
        if len(pts2) < 3:
            continue
        d = "M" + "L".join("%.1f,%.1f" % (p[0], p[1]) for p in pts2) + "Z"
        out.append(d)
    return "".join(out)


def main():
    js = json.loads(get("https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json",
                        "chinaprovinces.json").decode("utf-8"))
    provinces = []
    for f in js["features"]:
        nm = f["properties"].get("name")
        g = f.get("geometry")
        if not nm or not g:
            continue
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        rings = []
        for poly in polys:
            # 只取外环，忽略内部小洞（湖、飞地），对本图足够
            if poly and len(poly[0]) >= 4:
                rings.append(poly[0])
        d = path_from_rings(rings)
        if d:
            provinces.append({"n": nm, "d": d})
    print("[provinces]", len(provinces))

    # 主要河流（Natural Earth 10m），按名称挑几条主干
    want = {"Yangtze", "Huang", "Zhu Jiang", "Xi Jiang", "Huai", "Han", "Liao", "Amur",
            "Songhua", "Yarlung Zangbo", "Mekong", "Salween", "Tarim"}
    rivers = []
    try:
        ne = json.loads(get("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_rivers_lake_centerlines.geojson",
                            "ne_10m_rivers.geojson").decode("utf-8"))
        for f in ne["features"]:
            nm = (f["properties"].get("name") or "")
            if nm not in want:
                continue
            g = f["geometry"]
            lines = [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"]
            for ln in lines:
                pts = [proj(p[0], p[1]) for p in ln if LON0 <= p[0] <= LON1 and LAT0 <= p[1] <= LAT1]
                if len(pts) < 4:
                    continue
                pts = rdp(pts, 0.7)
                rivers.append({"n": nm, "d": "M" + "L".join("%.1f,%.1f" % (p[0], p[1]) for p in pts)})
    except Exception as e:
        print("[rivers] skipped:", e)
    print("[rivers]", len(rivers))

    # 地名：省会 + 历史重镇 + 边疆节点
    CITIES = [
        ("北京", 116.40, 39.90, "cap"), ("西安", 108.94, 34.34, "his"), ("洛阳", 112.45, 34.62, "his"),
        ("开封", 114.31, 34.80, "his"), ("南京", 118.80, 32.06, "his"), ("杭州", 120.16, 30.27, "his"),
        ("成都", 104.07, 30.66, "his"), ("荆州", 112.24, 30.33, "his"), ("襄阳", 112.14, 32.04, "his"),
        ("太原", 112.55, 37.87, "his"), ("大同", 113.30, 40.09, "his"), ("郑州", 113.63, 34.75, "his"),
        ("安阳", 114.39, 36.10, "his"), ("邯郸", 114.54, 36.63, "his"), ("汉中", 107.03, 33.07, "his"),
        ("天水", 105.72, 34.58, "his"), ("兰州", 103.83, 36.06, "his"), ("敦煌", 94.66, 40.14, "his"),
        ("张掖", 100.45, 38.93, "his"), ("武威", 102.64, 37.93, "his"), ("西宁", 101.78, 36.62, "his"),
        ("银川", 106.23, 38.49, "his"), ("呼和浩特", 111.75, 40.84, "his"), ("沈阳", 123.43, 41.80, "his"),
        ("辽阳", 123.24, 41.27, "his"), ("长春", 125.32, 43.82, "his"), ("哈尔滨", 126.53, 45.80, "his"),
        ("齐齐哈尔", 123.92, 47.35, "his"), ("乌鲁木齐", 87.62, 43.79, "his"), ("喀什", 75.99, 39.47, "his"),
        ("伊宁", 81.32, 43.92, "his"), ("拉萨", 91.11, 29.65, "his"), ("日喀则", 88.88, 29.27, "his"),
        ("广州", 113.26, 23.13, "his"), ("泉州", 118.68, 24.87, "his"), ("福州", 119.30, 26.08, "his"),
        ("南昌", 115.89, 28.68, "his"), ("长沙", 112.94, 28.23, "his"), ("武汉", 114.30, 30.59, "his"),
        ("合肥", 117.28, 31.86, "his"), ("济南", 117.00, 36.65, "his"), ("青岛", 120.38, 36.07, "his"),
        ("徐州", 117.18, 34.26, "his"), ("扬州", 119.42, 32.39, "his"), ("苏州", 120.62, 31.30, "his"),
        ("长沙", 112.94, 28.23, "his"), ("昆明", 102.83, 24.88, "his"), ("贵阳", 106.63, 26.65, "his"),
        ("重庆", 106.55, 29.56, "his"), ("南宁", 108.37, 22.82, "his"), ("海口", 110.20, 20.04, "his"),
        ("台北", 121.52, 25.03, "his")
    ]
    cities = []
    seen = set()
    for n, lon, lat, k in CITIES:
        if n in seen:
            continue
        seen.add(n)
        x, y = proj(lon, lat)
        cities.append({"n": n, "x": round(x, 1), "y": round(y, 1), "k": k})

    REGIONS = [
        ("huaxia", "中国本部 · 三维地形", (97.0, 17.6, 123.2, 42.6)),
    ]
    regions = []
    for rid, name, (a, b, c, d) in REGIONS:
        x0, y0 = proj(a, d)
        x1, y1 = proj(c, b)
        regions.append({"id": rid, "n": name, "x": round(x0, 1), "y": round(y0, 1),
                        "w": round(x1 - x0, 1), "h": round(y1 - y0, 1)})

    payload = {"w": round(SIZE, 1), "h": round(H, 1), "provinces": provinces,
               "rivers": rivers, "cities": cities, "regions": regions}
    body = ("/* 全国平面总图数据 · 省界 DataV.GeoAtlas（仅方位参照）· 河流 Natural Earth 10m\n"
            "   墨卡托投影，坐标已归一化 · 由 .dev/geo-china-map.py 生成，请勿手改 */\n"
            "window.CHINA_MAP=" + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n")
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    print("[write]", OUT, "%.0f KB" % (os.path.getsize(OUT) / 1024), "size", round(SIZE), "x", round(H))


if __name__ == "__main__":
    main()
