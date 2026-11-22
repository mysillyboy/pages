# -*- coding: utf-8 -*-
"""
中国地势 3D · 区域数据构建脚本

用法：
    <python> .dev/geo-build.py                # 构建当前 REGION
    <python> .dev/geo-build.py --preview      # 额外输出二维校验图到临时目录

数据来源（均为公开数据）：
  · 高程：Mapzen / AWS Terrain Tiles (terrarium)，基于 SRTM 等，CC-BY
     https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png
  · 河流：© OpenStreetMap contributors，经 Overpass API 提取（ODbL）
  · 省界：阿里云 DataV.GeoAtlas（仅作方位参照，非精确国界，勿作边界依据）

输出：data/geo-<id>.js，内含
  · height：8bit 灰度 PNG（data URI），h = maxH * (v/255)^gamma
  · rivers / lakes：经纬度折线，已裁剪到区域内并抽稀
  · provinces：今省界折线（虚线显示，仅方位参照）
"""
import io, json, math, os, sys, time, urllib.parse, urllib.request

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(os.path.dirname(HERE), "data")
CACHE = os.path.join(os.environ.get("TEMP", "."), "geo3d-cache")
os.makedirs(CACHE, exist_ok=True)

REGIONS = {
    "huaxia": {
        "id": "huaxia",
        "name": "中国本部 · 山河全图",
        "sub": "从关中到岭南，从巴蜀到江海 —— 一张连续的三维地势图",
        # 中国本部：含关中、中原、山西、山东、江淮、江南、荆楚、巴蜀、云贵、岭南、闽台西缘
        "bbox": (97.0, 17.6, 123.2, 42.6),
        "out_w": 1400,
        "zoom": 8,
        "gamma": 2.0,
        "vex": 9,
    },
}
REGION = REGIONS["huaxia"]

UA = {"User-Agent": "geo3d-build/1.0 (+https://mysillyboy.github.io/pages/)"}


def get(url, name, timeout=180):
    p = os.path.join(CACHE, name)
    if os.path.exists(p) and os.path.getsize(p) > 32:
        return open(p, "rb").read()
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    with open(p, "wb") as f:
        f.write(data)
    return data


# ---------------------------------------------------------------- 高程
def lonlat_to_tilepx(lon, lat, z):
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    s = math.sin(math.radians(lat))
    y = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n
    return x * 256.0, y * 256.0


def build_height(rg):
    lon0, lat0, lon1, lat1 = rg["bbox"]
    z = rg["zoom"]
    x0f, y0f = lonlat_to_tilepx(lon0, lat1, z)
    x1f, y1f = lonlat_to_tilepx(lon1, lat0, z)
    tx0, tx1 = int(math.floor(x0f / 256)), int(math.floor(x1f / 256))
    ty0, ty1 = int(math.floor(y0f / 256)), int(math.floor(y1f / 256))
    W = (tx1 - tx0 + 1) * 256
    H = (ty1 - ty0 + 1) * 256
    mosaic = np.zeros((H, W), dtype=np.float32)
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            url = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/%d/%d/%d.png" % (z, tx, ty)
            im = Image.open(io.BytesIO(get(url, "terr_%d_%d_%d.png" % (z, tx, ty)))).convert("RGB")
            a = np.asarray(im).astype(np.float32)
            h = a[:, :, 0] * 256.0 + a[:, :, 1] + a[:, :, 2] / 256.0 - 32768.0
            py, px = (ty - ty0) * 256, (tx - tx0) * 256
            mosaic[py:py + 256, px:px + 256] = h

    lat_mid = (lat0 + lat1) / 2
    w_km = (lon1 - lon0) * 111.32 * math.cos(math.radians(lat_mid))
    h_km = (lat1 - lat0) * 111.32
    Wt = rg["out_w"]
    Ht = int(round(Wt * h_km / w_km))
    lon = lon0 + (np.arange(Wt) + 0.5) / Wt * (lon1 - lon0)
    lat = lat1 - (np.arange(Ht) + 0.5) / Ht * (lat1 - lat0)
    LON, LAT = np.meshgrid(lon, lat)
    n = 2 ** z
    fx = (LON + 180.0) / 360.0 * n * 256.0 - tx0 * 256.0
    s = np.sin(np.radians(LAT))
    fy = (0.5 - np.log((1 + s) / (1 - s)) / (4 * math.pi)) * n * 256.0 - ty0 * 256.0
    u = np.clip(fx - 0.5, 0, W - 1.001)
    v = np.clip(fy - 0.5, 0, H - 1.001)
    u0 = np.floor(u).astype(np.int32)
    v0 = np.floor(v).astype(np.int32)
    du = (u - u0).astype(np.float32)
    dv = (v - v0).astype(np.float32)
    u0c = np.clip(u0, 0, W - 2); u1c = u0c + 1
    v0c = np.clip(v0, 0, H - 2); v1c = v0c + 1
    h = ((mosaic[v0c, u0c] * (1 - du) + mosaic[v0c, u1c] * du) * (1 - dv)
         + (mosaic[v1c, u0c] * (1 - du) + mosaic[v1c, u1c] * du) * dv)
    h = np.maximum(h, 0.0)

    # 去除孤立尖刺（地形空值造成的“针”）：仅在 3x3 中位数明显偏离且四邻都低时压平
    pad = np.pad(h, 1, mode="edge")
    stack = np.stack([pad[dy:dy + Ht, dx:dx + Wt] for dy in range(3) for dx in range(3)])
    med = np.median(stack, axis=0)
    mx = stack.max(axis=0)
    spike = (h - med > 700) & (mx - np.partition(stack, 8, axis=0)[8] > 700)
    h[spike] = med[spike]
    print("[height] grid %dx%d, %.2f km/px, max %.0f m, spikes fixed %d"
          % (Wt, Ht, w_km / Wt, h.max(), int(spike.sum())))
    return h, Wt, Ht


def encode_height(h, maxh, gamma):
    q = np.clip(np.round(255.0 * np.power(np.clip(h / maxh, 0, 1), 1.0 / gamma)), 0, 255).astype(np.uint8)
    img = Image.fromarray(q, mode="L")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    png = buf.getvalue()
    print("[height] png %.0f KB, base64 %.0f KB" % (len(png) / 1024, len(png) * 4 / 3 / 1024))
    import base64
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii"), q


# ---------------------------------------------------------------- 河流
def rdp(pts, eps):
    if len(pts) < 3:
        return pts
    a = np.array(pts[0], float); b = np.array(pts[-1], float)
    P = np.array(pts, float)
    ab = b - a
    L = math.hypot(ab[0], ab[1])
    if L < 1e-12:
        d = np.hypot(P[:, 0] - a[0], P[:, 1] - a[1])
    else:
        d = np.abs(ab[0] * (P[:, 1] - a[1]) - ab[1] * (P[:, 0] - a[0])) / L
    i = int(np.argmax(d))
    if d[i] > eps:
        return rdp(pts[:i + 1], eps)[:-1] + rdp(pts[i:], eps)
    return [pts[0], pts[-1]]


RIVER_GROUPS = [
    # 北方
    ("黄河|渭河|泾河|北洛河|汾河|洛河|伊河|沁河|漳河|清漳河|浊漳河|滹沱河|桑干河|永定河|"
     "拒马河|淮河|汉江|汉水|丹江|白河|唐河|无定河|延河|清水河|大汶河|滁河|秦淮河|青弋江|"
     "水阳江|新安江|富春江|钱塘江|曹娥江|椒江|瓯江|黄浦江|京杭运河|江南运河|胥江|苏北灌溉总渠"),
    # 长江中上游与荆楚
    ("长江|金沙江|岷江|大渡河|雅砻江|嘉陵江|涪江|渠江|沱江|乌江|赤水河|清江|沅江|湘江|资江|"
     "澧水|赣江|抚河|信江|修水|饶河|乌江|汉北河|堵河|南河|溇水|酉水|锦江|袁水|潇水|耒水|"
     "洣水|渌水|浏阳河|汨罗江|昌江|乐安江|信江|渌江"),
    # 东南与华南
    ("珠江|西江|北江|东江|韩江|闽江|晋江|九龙江|汀江|木兰溪|鉴江|漠阳江|郁江|柳江|桂江|"
     "红水河|南盘江|北盘江|右江|左江|贺江|连江|绥江|万泉河|南渡江|昌化江|澜沧江|怒江|"
     "元江|李仙江|盘龙江|牛栏江|以礼河|灵渠|浙东运河"),
]
RIVER_NAMES = "|".join(RIVER_GROUPS)
RIVER_WIDTH = {"黄河": 3.4, "长江": 3.8, "金沙江": 2.8, "汉江": 2.6, "汉水": 2.6, "淮河": 2.4,
               "渭河": 2.4, "汾河": 2.4, "珠江": 3.2, "西江": 3.0, "湘江": 2.4, "赣江": 2.4,
               "闽江": 2.4, "岷江": 2.4, "嘉陵江": 2.4, "乌江": 2.2, "北江": 2.2, "东江": 2.0,
               "沅江": 1.9, "洛河": 1.8, "泾河": 1.8, "钱塘江": 2.4, "京杭运河": 2.0, "江南运河": 1.8,
               "漳河": 1.6, "清漳河": 1.2, "浊漳河": 1.2, "沁河": 1.6, "伊河": 1.5, "滹沱河": 1.6,
               "桑干河": 1.6, "永定河": 1.6, "北洛河": 1.5, "无定河": 1.5, "丹江": 1.5, "唐河": 1.3,
               "白河": 1.3, "拒马河": 1.3, "延河": 1.2, "清水河": 1.2, "大汶河": 1.3, "滁河": 1.4,
               "秦淮河": 1.4, "青弋江": 1.4, "水阳江": 1.3, "新安江": 1.5, "富春江": 1.8,
               "黄浦江": 1.8, "曹娥江": 1.2, "椒江": 1.2, "瓯江": 1.5, "韩江": 1.8, "九龙江": 1.5,
               "晋江": 1.5, "汀江": 1.3, "郁江": 1.6, "柳江": 1.6, "桂江": 1.5, "红水河": 1.8,
               "南盘江": 1.5, "北盘江": 1.4, "澜沧江": 2.0, "怒江": 2.0, "元江": 1.6, "雅砻江": 1.8,
               "大渡河": 1.8, "涪江": 1.4, "渠江": 1.3, "沱江": 1.4, "赤水河": 1.3, "清江": 1.3}


OVERPASS_HOSTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]


def overpass(q, attempts=6):
    data = urllib.parse.urlencode({"data": q}).encode()
    last = None
    for attempt in range(attempts):
        host = OVERPASS_HOSTS[attempt % len(OVERPASS_HOSTS)]
        try:
            req = urllib.request.Request(host, data=data, headers=UA)
            with urllib.request.urlopen(req, timeout=240) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last = e
            print("[overpass] %s 失败(%s)，重试…" % (host, e))
            time.sleep(3 + attempt * 4)
    raise last


def join_ways(ways, tol=3e-5):
    segs = [list(w) for w in ways]
    out = []
    while segs:
        cur = segs.pop(0)
        changed = True
        while changed and segs:
            changed = False
            for i, s in enumerate(segs):
                if abs(cur[-1][0] - s[0][0]) < tol and abs(cur[-1][1] - s[0][1]) < tol:
                    cur += s[1:]; segs.pop(i); changed = True; break
                if abs(cur[-1][0] - s[-1][0]) < tol and abs(cur[-1][1] - s[-1][1]) < tol:
                    cur += s[::-1][1:]; segs.pop(i); changed = True; break
                if abs(cur[0][0] - s[-1][0]) < tol and abs(cur[0][1] - s[-1][1]) < tol:
                    cur = s[:-1] + cur; segs.pop(i); changed = True; break
                if abs(cur[0][0] - s[0][0]) < tol and abs(cur[0][1] - s[0][1]) < tol:
                    cur = s[::-1][:-1] + cur; segs.pop(i); changed = True; break
        out.append(cur)
    return out


def add_ne_rivers(rg, rivers, have_names):
    """OSM 拿不到时用 Natural Earth 10m 补主干河道（英文名）。"""
    try:
        js = json.loads(get("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_rivers_lake_centerlines.geojson",
                            "ne_10m_rivers.geojson").decode("utf-8"))
    except Exception as e:
        print("[rivers] NE 兜底失败：", e)
        return rivers
    lon0, lat0, lon1, lat1 = rg["bbox"]
    W = {"Yangtze": 3.8, "Huang": 3.4, "Zhu Jiang": 3.2, "Xi Jiang": 3.0, "Huai": 2.4,
         "Han": 2.4, "Liao": 2.2, "Songhua": 2.4, "Amur": 2.6, "Yarlung Zangbo": 2.4,
         "Mekong": 2.2, "Salween": 2.0, "Tarim": 1.8}
    added = 0
    for f in js["features"]:
        nm = f["properties"].get("name") or ""
        if nm not in W or nm in have_names:
            continue
        g = f.get("geometry")
        if not g:
            continue
        lines = [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"]
        for ln in lines:
            inside = [p for p in ln if lon0 <= p[0] <= lon1 and lat0 <= p[1] <= lat1]
            if len(inside) < 4:
                continue
            simp = rdp(inside, 0.004)
            rivers.append({"n": nm, "w": W[nm],
                           "pts": [[round(p[0], 4), round(p[1], 4)] for p in simp]})
            added += 1
    print("[rivers] NE 兜底补入 %d 条" % added)
    return rivers


def add_ne_lakes(rg):
    """用 Natural Earth 10m 湖泊补多边形（含洞庭、鄱阳、太湖等大湖）。"""
    try:
        js = json.loads(get("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_lakes.geojson",
                            "ne_10m_lakes.geojson").decode("utf-8"))
    except Exception as e:
        print("[lakes] NE 失败：", e)
        return []
    lon0, lat0, lon1, lat1 = rg["bbox"]
    out = []
    for f in js["features"]:
        g = f.get("geometry")
        if not g:
            continue
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        nm = f["properties"].get("name") or "湖"
        for poly in polys:
            ring = poly[0]
            xs = [p[0] for p in ring]; ys = [p[1] for p in ring]
            if max(xs) < lon0 or min(xs) > lon1 or max(ys) < lat0 or min(ys) > lat1:
                continue
            pts = rdp([(p[0], p[1]) for p in ring], 0.01)
            if len(pts) < 4:
                continue
            out.append({"n": nm, "pts": [[round(p[0], 4), round(p[1], 4)] for p in pts]})
    print("[lakes] NE 补入", len(out), "个")
    return out


def build_rivers(rg):
    lon0, lat0, lon1, lat1 = rg["bbox"]
    # 名称太多、范围太大，按 2×2 子区域分批查询，避免超时；按 way id 去重
    ways = {}
    nsplit = 2
    for gi, grp in enumerate(RIVER_GROUPS):
        for a in range(nsplit):
            for b in range(nsplit):
                la0 = lat0 + (lat1 - lat0) * a / nsplit
                la1 = lat0 + (lat1 - lat0) * (a + 1) / nsplit + 0.05
                lo0 = lon0 + (lon1 - lon0) * b / nsplit
                lo1 = lon0 + (lon1 - lon0) * (b + 1) / nsplit + 0.05
                q = ('[out:json][timeout:120];'
                     'way["waterway"="river"]["name"~"^(%s)$"](%.3f,%.3f,%.3f,%.3f);out geom;'
                     % (grp, la0, lo0, la1, lo1))
                tag = "组%d-%d%d" % (gi + 1, a, b)
                try:
                    js = overpass(q, attempts=1)
                except Exception as e:
                    print("[rivers] %s 失败：%s" % (tag, e))
                    continue
                n0 = len(ways)
                for e in js["elements"]:
                    if e.get("type") == "way" and "geometry" in e and e.get("tags", {}).get("name"):
                        ways[e["id"]] = e
                print("[rivers] %s 新增 %d 条" % (tag, len(ways) - n0))
    byname = {}
    for e in ways.values():
        nm = e["tags"]["name"]
        pts = [(p["lon"], p["lat"]) for p in e["geometry"]]
        if len(pts) >= 2:
            byname.setdefault(nm, []).append(pts)
    rivers = []
    for nm, ways in byname.items():
        for ln in join_ways(ways):
            inside = [p for p in ln if lon0 - 0.06 <= p[0] <= lon1 + 0.06 and lat0 - 0.06 <= p[1] <= lat1 + 0.06]
            if len(inside) < 3:
                continue
            simp = rdp(inside, 0.0022)
            if len(simp) < 2:
                continue
            rivers.append({"n": nm, "w": RIVER_WIDTH.get(nm, 1.3),
                           "pts": [[round(p[0], 4), round(p[1], 4)] for p in simp]})
    rivers.sort(key=lambda r: r["w"])
    print("[rivers] %d lines, %d pts, names: %s"
          % (len(rivers), sum(len(r["pts"]) for r in rivers), ", ".join(sorted(byname))))
    return add_ne_rivers(rg, rivers, set(byname))


def build_lakes(rg):
    lon0, lat0, lon1, lat1 = rg["bbox"]
    names = "白洋淀|密云水库|官厅水库|太湖|巢湖|洪泽湖|高邮湖|阳澄湖|淀山湖|千岛湖|洞庭湖|鄱阳湖|滇池|洱海|青海湖|洪湖|梁子湖|抚仙湖|西湖|东湖"
    try:
        q = ('[out:json][timeout:120];'
             '('
             'way["natural"="water"]["name"~"^(%s)$"](%.3f,%.3f,%.3f,%.3f);'
             'relation["natural"="water"]["name"~"^(%s)$"](%.3f,%.3f,%.3f,%.3f);'
             ');out geom;' % (names, lat0, lon0, lat1, lon1, names, lat0, lon0, lat1, lon1))
        js = overpass(q)
    except Exception as e:
        print("[lakes] skipped:", e)
        return []
    lakes = []
    for e in js["elements"]:
        nm = e.get("tags", {}).get("name")
        if not nm:
            continue
        rings = []
        if e.get("type") == "way" and "geometry" in e:
            rings.append([(p["lon"], p["lat"]) for p in e["geometry"]])
        elif e.get("type") == "relation":
            # 关系体（多部件湖）：把 outer 成员首尾相接成环，取面积最大的一个
            segs = []
            for m in e.get("members", []):
                if m.get("role") != "outer" or "geometry" not in m:
                    continue
                segs.append([(p["lon"], p["lat"]) for p in m["geometry"]])
            for chain in join_ways(segs, tol=5e-5):
                if len(chain) >= 4 and abs(chain[0][0] - chain[-1][0]) < 5e-4 and abs(chain[0][1] - chain[-1][1]) < 5e-4:
                    rings.append(chain)
        for ring in rings:
            if len(ring) < 4:
                continue
            xs = [p[0] for p in ring]; ys = [p[1] for p in ring]
            if max(xs) < lon0 or min(xs) > lon1 or max(ys) < lat0 or min(ys) > lat1:
                continue
            simp = rdp(ring, 0.002)
            if len(simp) < 4:
                continue
            lakes.append({"n": nm, "pts": [[round(p[0], 4), round(p[1], 4)] for p in simp]})
    print("[lakes]", sorted(set(l["n"] for l in lakes)))
    return lakes


# ---------------------------------------------------------------- 省界
PROV = ["陕西省", "山西省", "河南省", "河北省", "山东省", "北京市", "天津市",
        "内蒙古自治区", "甘肃省", "宁夏回族自治区", "青海省", "湖北省", "安徽省",
        "江苏省", "浙江省", "上海市", "江西省", "福建省", "湖南省", "广东省",
        "广西壮族自治区", "海南省", "重庆市", "四川省", "贵州省", "云南省",
        "台湾省", "辽宁省"]


def build_provinces(rg):
    lon0, lat0, lon1, lat1 = rg["bbox"]
    try:
        js = json.loads(get("https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json",
                            "chinaprovinces.json").decode("utf-8"))
    except Exception as e:
        print("[provinces] skipped:", e)
        return []
    out = []
    names = set()
    for f in js.get("features", []):
        nm = f["properties"].get("name")
        if nm not in PROV:
            continue
        g = f.get("geometry")
        if not g:
            continue
        polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        for poly in polys:
            for ring in poly:
                pts = [(p[0], p[1]) for p in ring]
                xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
                if max(xs) < lon0 or min(xs) > lon1 or max(ys) < lat0 or min(ys) > lat1:
                    continue
                s = rdp(pts, 0.02)
                if len(s) < 3:
                    continue
                out.append({"n": nm, "pts": [[round(p[0], 3), round(p[1], 3)] for p in s]})
                names.add(nm)
    print("[provinces] %d rings, %s" % (len(out), ", ".join(sorted(names))))
    return out


# ---------------------------------------------------------------- 预览
def preview(h, rivers, path, rg):
    Ht, Wt = h.shape
    lon0, lat0, lon1, lat1 = rg["bbox"]
    kx = (lon1 - lon0) * 111.32 * math.cos(math.radians((lat0 + lat1) / 2)) / Wt * 1000
    kz = (lat1 - lat0) * 111.32 / Ht * 1000
    dzdx = np.gradient(h, axis=1) / kx
    dzdy = np.gradient(h, axis=0) / kz
    n = np.sqrt(dzdx ** 2 + dzdy ** 2 + 1)
    az, alt = math.radians(315), math.radians(42)
    Lx, Ly, Lz = math.cos(alt) * math.sin(az), -math.cos(alt) * math.cos(az), math.sin(alt)
    dot = np.clip((-dzdx * Lx - dzdy * Ly + Lz) / n, 0, 1)
    stops = [(0, (168, 187, 154)), (150, (190, 198, 161)), (500, (208, 199, 160)),
             (900, (212, 189, 147)), (1400, (199, 167, 121)), (2100, (174, 141, 104)),
             (3000, (147, 122, 104)), (3700, (178, 170, 162)), (4600, (236, 235, 230))]
    xs = np.array([s[0] for s in stops], float)
    col = np.stack([np.interp(h, xs, np.array([s[1][k] for s in stops], float)) for k in range(3)], axis=2)
    col *= (0.42 + 0.7 * dot)[..., None]
    img = Image.fromarray(np.clip(col, 0, 255).astype(np.uint8))
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    for r in rivers:
        d.line([((p[0] - lon0) / (lon1 - lon0) * (Wt - 1),
                 (lat1 - p[1]) / (lat1 - lat0) * (Ht - 1)) for p in r["pts"]],
               fill=(66, 102, 128), width=max(1, int(r["w"])))
    img.save(path)
    print("[preview]", path)


def main():
    FAST = "--fast" in sys.argv
    rg = REGION
    for i, a in enumerate(sys.argv):
        if a.startswith("--region="):
            rg = REGIONS[a.split("=", 1)[1]]
        elif a == "--region" and i + 1 < len(sys.argv):
            rg = REGIONS[sys.argv[i + 1]]
    print("[region]", rg["id"], rg["name"])
    h, Wt, Ht = build_height(rg)
    maxh = float(math.ceil(h.max() / 50.0) * 50)
    data_uri, q = encode_height(h, maxh, rg["gamma"])
    rivers = [] if FAST else build_rivers(rg)
    lakes = [] if FAST else build_lakes(rg)
    provinces = build_provinces(rg)
    if FAST:
        rivers = add_ne_rivers(rg, rivers, set())
        lakes = add_ne_lakes(rg)

    if "--preview" in sys.argv:
        preview(h, rivers, os.path.join(CACHE, "preview-%s.png" % rg["id"]), rg)

    os.makedirs(OUT_DIR, exist_ok=True)
    payload = {
        "id": rg["id"], "name": rg["name"], "sub": rg["sub"],
        "bbox": list(rg["bbox"]), "w": Wt, "h": Ht,
        "maxH": maxh, "gamma": rg["gamma"], "vex": rg.get("vex", 9),
        "height": data_uri, "rivers": rivers, "lakes": lakes, "provinces": provinces,
    }
    body = ("/* 中国地势 3D 区域数据 · %s\n"
            "   高程 Mapzen/AWS Terrain Tiles (SRTM) · 河流 © OpenStreetMap contributors (ODbL)\n"
            "   省界 DataV.GeoAtlas，仅方位参照 · 由 .dev/geo-build.py 生成，请勿手改 */\n"
            "(window.GEO3D=window.GEO3D||{regions:{}}).regions[%s]=%s;\n"
            % (rg["name"], json.dumps(rg["id"]), json.dumps(payload, ensure_ascii=False, separators=(",", ":"))))
    out = os.path.join(OUT_DIR, "geo-%s.js" % rg["id"])
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(body)
    print("[write] %s  %.0f KB" % (out, os.path.getsize(out) / 1024))


if __name__ == "__main__":
    main()
