# -*- coding: utf-8 -*-
"""江西山河图 · 生成脚本

生成 assets/jiangxi-shanhetu.png：一幅手绘风格（俯视微斜、秋色山林、青蓝水系）的江西地形图。

用法：
    <python> .dev/jiangxi-art.py [--out 路径] [--small]

数据来源：
  · 高程：Mapzen / AWS Terrain Tiles（terrarium），已内嵌于 data/geo-huaxia.js；
          本脚本按江西图幅裁切该 8bit 高程瓦片，并叠加分形细节。
  · 省界：DataV.GeoAtlas（经 data/geo-huaxia.js 简化），仅作方位参照。
  · 河流、湖泊、城市、山峰：据公开地理资料手工编绘，示意性表现。
"""
import base64, io, json, math, os, sys, time
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

t0 = time.time()
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

OUT = os.path.join(ROOT, "assets", "jiangxi-shanhetu.png")
SMALL = "--small" in sys.argv
for i, a in enumerate(sys.argv):
    if a == "--out" and i + 1 < len(sys.argv):
        OUT = sys.argv[i + 1]

# 图幅范围（含省界外的山体余量）
LON0, LAT0, LON1, LAT1 = 113.30, 24.30, 118.75, 30.30
NX, NY = 560, 700
KMX = (LON1 - LON0) * 111.32 * math.cos(math.radians((LAT0 + LAT1) / 2)) / NX
KMY = (LAT1 - LAT0) * 111.32 / NY

FONT_CITY = "C:/Windows/Fonts/msyhbd.ttc"
FONT_SERIF = "C:/Windows/Fonts/NotoSerifSC-VF.ttf"
FONT_SANS = "C:/Windows/Fonts/msyh.ttc"

# ---------------------------------------------------------------- 地理骨架（手工编绘）
RIVERS = [
    {"n": "长江", "w": 4.0, "pts": [(115.30, 29.60), (115.55, 29.67), (115.74, 29.70), (115.92, 29.72),
                                  (116.08, 29.76), (116.22, 29.80), (116.38, 29.88), (116.52, 30.00), (116.64, 30.14)]},
    {"n": "赣江", "w": 3.2, "pts": [(115.02, 25.86), (114.94, 25.83), (114.80, 26.10), (114.76, 26.46),
                                  (114.86, 26.72), (114.99, 27.11), (115.13, 27.30), (115.24, 27.50),
                                  (115.36, 27.68), (115.45, 27.88), (115.55, 28.06), (115.70, 28.16),
                                  (115.82, 28.40), (115.89, 28.62), (116.02, 28.78), (116.18, 28.96)]},
    {"n": "贡水", "w": 1.5, "pts": [(116.03, 25.89), (115.86, 25.72), (115.79, 25.60), (115.62, 25.72),
                                 (115.41, 25.95), (115.02, 25.86)]},
    {"n": "章水", "w": 1.5, "pts": [(114.36, 25.40), (114.48, 25.50), (114.62, 25.55), (114.76, 25.66), (114.94, 25.83)]},
    {"n": "抚河", "w": 2.2, "pts": [(116.33, 26.84), (116.42, 27.02), (116.53, 27.22), (116.64, 27.45),
                                  (116.62, 27.57), (116.50, 27.78), (116.36, 27.98), (116.28, 28.20),
                                  (116.24, 28.37), (116.10, 28.60), (116.22, 28.82)]},
    {"n": "信江", "w": 2.0, "pts": [(118.24, 28.68), (118.10, 28.56), (117.97, 28.45), (117.72, 28.42),
                                  (117.45, 28.40), (117.24, 28.29), (117.07, 28.27), (116.82, 28.20),
                                  (116.72, 28.45), (116.69, 28.69), (116.52, 28.86)]},
    {"n": "饶河", "w": 1.9, "pts": [(117.86, 29.25), (117.72, 29.10), (117.58, 28.95), (117.38, 28.92),
                                  (117.13, 28.97), (116.90, 28.98), (116.70, 29.00), (116.48, 29.05)]},
    {"n": "昌江", "w": 1.4, "pts": [(117.45, 29.42), (117.30, 29.35), (117.18, 29.27), (117.00, 29.15),
                                  (116.86, 29.06), (116.70, 29.00)]},
    {"n": "修河", "w": 1.9, "pts": [(114.37, 28.52), (114.45, 28.78), (114.55, 29.03), (114.82, 29.15),
                                  (115.10, 29.26), (115.35, 29.20), (115.58, 29.12), (115.83, 29.03), (116.02, 29.06)]},
    {"n": "袁水", "w": 1.4, "pts": [(114.17, 27.50), (114.30, 27.66), (114.42, 27.80), (114.56, 27.82),
                                  (114.69, 27.81), (114.93, 27.82), (115.20, 27.92), (115.55, 28.06)]},
    {"n": "锦江", "w": 1.3, "pts": [(114.78, 28.39), (114.92, 28.24), (115.10, 28.20), (115.24, 28.32),
                                  (115.38, 28.42), (115.62, 28.50), (115.85, 28.62)]},
    {"n": "潦河", "w": 1.2, "pts": [(115.36, 28.86), (115.45, 28.92), (115.55, 28.85), (115.68, 28.94),
                                  (115.83, 29.03)]},
    {"n": "梅江", "w": 1.2, "pts": [(116.15, 26.62), (116.05, 26.40), (115.95, 26.20), (115.75, 26.05), (115.41, 25.95)]},
]

CITY = [
    {"n": "南昌", "x": 115.89, "y": 28.68, "dx": 92, "dy": -46, "tag": "省会"},
    {"n": "九江", "x": 115.99, "y": 29.71, "dx": 66, "dy": 18},
    {"n": "景德镇", "x": 117.18, "y": 29.27, "dx": 74, "dy": -30},
    {"n": "上饶", "x": 117.97, "y": 28.45, "dx": 78, "dy": 6},
    {"n": "鹰潭", "x": 117.07, "y": 28.27, "dx": 84, "dy": -8},
    {"n": "抚州", "x": 116.36, "y": 27.98, "dx": 84, "dy": 10},
    {"n": "宜春", "x": 114.42, "y": 27.80, "dx": -92, "dy": -26},
    {"n": "萍乡", "x": 113.85, "y": 27.62, "dx": -88, "dy": 16},
    {"n": "新余", "x": 114.93, "y": 27.82, "dx": 78, "dy": -20},
    {"n": "吉安", "x": 114.99, "y": 27.11, "dx": 88, "dy": 12},
    {"n": "赣州", "x": 114.94, "y": 25.83, "dx": -96, "dy": 22},
]

PEAK = [
    {"n": "武功山", "x": 114.17, "y": 27.46, "dx": 10, "dy": -56},
    {"n": "三清山", "x": 118.06, "y": 28.91, "dx": 34, "dy": -40},
    {"n": "庐山", "x": 115.98, "y": 29.55, "dx": -34, "dy": -50},
    {"n": "井冈山", "x": 114.17, "y": 26.57, "dx": 96, "dy": 34},
    
    {"n": "龙虎山", "x": 116.98, "y": 28.11, "dx": 30, "dy": 46},
    
    {"n": "九连山", "x": 114.55, "y": 24.60, "dx": 10, "dy": -46},
]

RANGE = [
    {"n": "罗霄山脉", "x": 114.16, "y": 26.98, "angle": -78, "size": 34},
    {"n": "武夷山脉", "x": 116.02, "y": 26.46, "angle": -50, "size": 36},
    {"n": "九岭山", "x": 114.86, "y": 28.90, "angle": -6, "size": 42},
    {"n": "怀玉山", "x": 118.02, "y": 28.72, "angle": 0, "size": 38},
    {"n": "幕阜山", "x": 114.02, "y": 29.10, "angle": 0, "size": 38},
    {"n": "大庾岭", "x": 114.52, "y": 25.30, "angle": 0, "size": 36},
    {"n": "吉泰盆地", "x": 114.86, "y": 26.86, "angle": 0, "size": 34, "kind": "basin"},
    {"n": "鄱阳湖平原", "x": 116.62, "y": 28.52, "angle": 0, "size": 32, "kind": "basin"},
]

LAKE_LABEL = {"n": "鄱阳湖", "x": 116.30, "y": 29.22, "dx": 0, "dy": -8}
RIVER_LABEL = {
    "赣江": (115.28, 27.32, -66), "抚河": (116.32, 27.60, -78), "信江": (117.68, 28.34, -12),
    "饶河": (117.26, 28.90, -20), "修河": (114.94, 29.14, -16), "袁水": (114.58, 27.86, 8),
    "锦江": (115.24, 28.34, -12), "长江": (116.44, 29.90, -20), "贡水": (115.66, 25.70, 32),
}


# ---------------------------------------------------------------- 工具
def sstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def noise(shape, cells, seed):
    rng = np.random.default_rng(seed)
    small = (rng.random((max(2, cells), max(2, cells))) * 65535).astype(np.uint16)
    im = Image.fromarray(small).resize((shape[1], shape[0]), Image.BICUBIC)
    return np.asarray(im).astype(np.float32) / 65535.0


def ridged(shape, base, octaves, seed, gain=0.5):
    acc = np.zeros(shape, np.float32); amp = 1.0; norm = 0.0; c = base
    for o in range(octaves):
        n = noise(shape, int(c), seed + o * 131)
        acc += amp * (1.0 - np.abs(n * 2 - 1)) ** 2.0
        norm += amp; amp *= gain; c *= 2
    return acc / norm


def fbm(shape, base, octaves, seed, gain=0.5):
    acc = np.zeros(shape, np.float32); amp = 1.0; norm = 0.0; c = base
    for o in range(octaves):
        acc += amp * noise(shape, int(c), seed + o * 97)
        norm += amp; amp *= gain; c *= 2
    return acc / norm


def box_blur(a, r, passes=2):
    a = np.asarray(a, np.float32); k = 2 * r + 1
    for _ in range(passes):
        p = np.pad(a, ((r, r), (0, 0)), mode="edge")
        c = np.concatenate([np.zeros((1, p.shape[1]), np.float32), np.cumsum(p, axis=0)], 0)
        a = (c[k:] - c[:-k]) / k
        p = np.pad(a, ((0, 0), (r, r)), mode="edge")
        c = np.concatenate([np.zeros((p.shape[0], 1), np.float32), np.cumsum(p, axis=1)], 1)
        a = (c[:, k:] - c[:, :-k]) / k
    return a


# ---------------------------------------------------------------- 高程裁切
raw = open(os.path.join(ROOT, "data", "geo-huaxia.js"), encoding="utf-8").read()
geo = json.loads(raw[raw.index("=", raw.index('regions["huaxia"]')) + 1:].rstrip().rstrip(";"))
_gq = np.asarray(Image.open(io.BytesIO(base64.b64decode(geo["height"].split(",", 1)[1])))).astype(np.float32)
GHGT = geo["maxH"] * (_gq / 255.0) ** geo["gamma"]
GW, GH = geo["w"], geo["h"]
GLON0, GLAT0, GLON1, GLAT1 = geo["bbox"]

lon = LON0 + (np.arange(NX) + 0.5) / NX * (LON1 - LON0)
lat = LAT1 - (np.arange(NY) + 0.5) / NY * (LAT1 - LAT0)
LON, LAT = np.meshgrid(lon, lat)
fx = np.clip((LON - GLON0) / (GLON1 - GLON0) * GW - 0.5, 0, GW - 1.001)
fy = np.clip((GLAT1 - LAT) / (GLAT1 - GLAT0) * GH - 0.5, 0, GH - 1.001)
x0 = np.floor(fx).astype(np.int32); y0 = np.floor(fy).astype(np.int32)
dx = fx - x0; dy = fy - y0
x1 = np.minimum(x0 + 1, GW - 1); y1 = np.minimum(y0 + 1, GH - 1)
BASE = ((GHGT[y0, x0] * (1 - dx) + GHGT[y0, x1] * dx) * (1 - dy)
        + (GHGT[y1, x0] * (1 - dx) + GHGT[y1, x1] * dx) * dy).astype(np.float32)
BASE = np.maximum(BASE, 0)

shape = BASE.shape
r1 = ridged(shape, 4, 3, 11)
H = BASE + (r1 - 0.62) * 160.0 * sstep(100, 500, BASE) + (fbm(shape, 70, 2, 77) - 0.5) * 12.0
H = np.maximum(H, 0)
H = box_blur(H, 1, 2)


def carve(H, rivers, depth, width):
    ny, nx = H.shape
    for r in rivers:
        pts = [((lo - LON0) / (LON1 - LON0) * nx, (LAT1 - la) / (LAT1 - LAT0) * ny) for lo, la in r["pts"]]
        for (px0, py0), (px1, py1) in zip(pts[:-1], pts[1:]):
            m = int(max(abs(px1 - px0), abs(py1 - py0)) * 3) + 1
            for t in np.linspace(0, 1, m):
                cx = px0 + (px1 - px0) * t; cy = py0 + (py1 - py0) * t
                R = int(width * 2.6) + 1
                ix, iy = int(cx), int(cy)
                xa, xb = max(0, ix - R), min(nx, ix + R + 1)
                ya, yb = max(0, iy - R), min(ny, iy + R + 1)
                if xa >= xb or ya >= yb:
                    continue
                yy, xx = np.mgrid[ya:yb, xa:xb]
                d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
                f = np.clip(1 - (d / (width * 1.7)) ** 2, 0, 1) ** 2
                H[ya:yb, xa:xb] -= depth * f
    return np.maximum(H, 0)


H = carve(H, [r for r in RIVERS if r["w"] >= 1.4], 110.0, 2.4)
H = box_blur(H, 1, 2)

HS = box_blur(H, 7, 2)
gy, gx = np.gradient(HS, KMY * 1000.0, KMX * 1000.0)
GS = 4.6
nrm = np.sqrt((gx * GS) ** 2 + (gy * GS) ** 2 + 1.0)
az, alt = math.radians(315), math.radians(30)
Lx, Ly, Lz = math.cos(alt) * math.sin(az), -math.cos(alt) * math.cos(az), math.sin(alt)
dot = np.clip((-gx * GS * Lx - gy * GS * Ly + Lz) / nrm, 0, 1)
shade = 0.05 + 1.55 * dot ** 1.05

blur = box_blur(H, 10, 3)
ao = np.clip(0.6 + 0.95 * sstep(-30, 180, H - blur), 0.6, 1.2)

shadow = np.zeros_like(H)
tan_alt = math.tan(alt)
for k in range(1, 40):
    dr = int(round(math.cos(az) * k * 150.0 / (KMY * 1000.0)))
    dc = int(round(-math.sin(az) * k * 150.0 / (KMX * 1000.0)))
    if dr == 0 and dc == 0:
        continue
    hs = np.roll(np.roll(H, dr, axis=0), dc, axis=1)
    shadow = np.maximum(shadow, np.clip((hs - H - k * 150.0 * tan_alt) / 140.0, 0, 1))
shadow = box_blur(shadow, 2, 2)
shadow = np.clip(shadow * 1.05, 0, 1)

# ---------------------------------------------------------------- 省界
ring = max([p for p in geo["provinces"] if p["n"] == "江西省"], key=lambda r: len(r["pts"]))["pts"]


def chaikin(pts, it=3, closed=True):
    pts = np.asarray(pts, float)
    for _ in range(it):
        if closed:
            q = 0.75 * pts + 0.25 * np.roll(pts, -1, 0)
            r = 0.25 * pts + 0.75 * np.roll(pts, -1, 0)
        else:
            q = 0.75 * pts[:-1] + 0.25 * pts[1:]
            r = 0.25 * pts[:-1] + 0.75 * pts[1:]
        pts = np.empty((len(q) * 2, 2)); pts[0::2] = q; pts[1::2] = r
    return pts


RING = chaikin(ring, 3)


def poly_mask(nx, ny):
    im = Image.new("L", (nx, ny), 0)
    ImageDraw.Draw(im).polygon(
        [((lo - LON0) / (LON1 - LON0) * nx, (LAT1 - la) / (LAT1 - LAT0) * ny) for lo, la in RING], fill=255)
    return np.asarray(im) > 127


CORE = poly_mask(NX, NY)
MASK = CORE.copy()
for _ in range(2):
    MASK = MASK | np.roll(MASK, 1, 0) | np.roll(MASK, -1, 0) | np.roll(MASK, 1, 1) | np.roll(MASK, -1, 1)

# ---------------------------------------------------------------- 配色
slope = np.sqrt(gx * gx + gy * gy)


def lerp(c0, c1, t):
    t = np.asarray(t, np.float32)[..., None]
    return np.array(c0, np.float32) * (1 - t) + np.array(c1, np.float32) * t


veg = lerp((118, 156, 64), (22, 56, 32), sstep(30, 560, H))
veg = veg * (0.88 + 0.24 * fbm(shape, 16, 3, 201)[..., None])
aut = fbm(shape, 13, 4, 311) * 0.7 + fbm(shape, 44, 3, 407) * 0.3
autumn = sstep(0.55, 0.68, aut) * sstep(50, 200, H) * (1 - sstep(1600, 2000, H))
aco = lerp((208, 112, 30), (148, 40, 20), fbm(shape, 20, 3, 509))
veg = veg * (1 - 0.85 * autumn[..., None]) + aco * (0.85 * autumn[..., None])

rock = np.clip(sstep(0.85, 1.6, slope) * 0.7 + sstep(1400, 1800, H) * 0.9, 0, 1)
rock = np.clip(rock * (0.5 + 0.8 * fbm(shape, 42, 3, 601)), 0, 1)
rco = lerp((104, 94, 82), (206, 198, 184), fbm(shape, 26, 3, 703))
veg = veg * (1 - rock[..., None]) + rco * rock[..., None]

plain = sstep(80, 22, H) * sstep(0.04, 0.01, slope)
fco = lerp((230, 210, 116), (178, 188, 90), fbm(shape, 20, 3, 913))
veg = veg * (1 - 0.92 * plain[..., None]) + fco * (0.92 * plain[..., None])

b3 = box_blur(H, 4, 2)
crest = np.clip((H - b3) / 50.0, 0, 1) ** 0.9
valley = np.clip((b3 - H) / 40.0, 0, 1) ** 0.9
lit = np.clip(shade * (1 - shadow * 0.85) * ao, 0.0, 1.7)
lit = lit * (1.0 + 0.7 * crest - 0.5 * valley)
rgb = veg * (0.06 + 1.55 * lit[..., None])
warm = np.array([1.10, 1.03, 0.90], np.float32)
cool = np.array([0.58, 0.68, 0.94], np.float32)
rgb = rgb * (warm * (1 - shadow[..., None]) + cool * shadow[..., None])

# ---------------------------------------------------------------- 地表贴图（田块）
TW, TH = NX * 2, NY * 2
img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).resize((TW, TH), Image.LANCZOS)
dr = ImageDraw.Draw(img, "RGBA")
rng = np.random.default_rng(7)
plain2 = np.asarray(Image.fromarray((plain * 255).astype(np.uint8)).resize((TW, TH), Image.NEAREST)) > 55
mask2 = np.asarray(Image.fromarray((MASK * 255).astype(np.uint8)).resize((TW, TH), Image.NEAREST)) > 127
ys, xs = np.where(mask2 & plain2)
if len(xs):
    for i in rng.integers(0, len(xs), 9000):
        cx, cy = xs[i] + rng.uniform(-2, 2), ys[i] + rng.uniform(-2, 2)
        w = rng.uniform(5, 12); h = rng.uniform(4, 9); rot = rng.uniform(-0.6, 0.6)
        ca, sa = math.cos(rot), math.sin(rot)
        quad = [(cx + qx * ca - qy * sa, cy + qx * sa + qy * ca)
                for qx, qy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))]
        col = [(232, 214, 120, 115), (204, 206, 100, 115), (180, 192, 90, 108),
               (216, 200, 104, 108), (194, 200, 112, 100)][rng.integers(0, 5)]
        dr.polygon(quad, fill=col, outline=(118, 114, 60, 55))
tex_np = np.asarray(img)
tex_col = (tex_np[:, 0::2].astype(np.float32) + tex_np[:, 1::2].astype(np.float32)) * 0.5

# ---------------------------------------------------------------- 斜视投影
CW, CH = 3, 3
KZ = 0.80
VS = 0.052
OW = NX * CW
OY0 = 210
SLAB = 8
yplane = OY0 + (np.arange(NY) + 0.5) * CH * KZ
OH = int(yplane[-1] + SLAB + 26)
out = np.zeros((OH, OW, 3), np.uint8)
alpha = np.zeros((OH, OW), np.uint8)
ids = np.full((OH, OW), -1, np.int16)

for u in range(NX):
    x0 = u * CW
    ymin = float(OH)
    first = True
    jprev = NY - 1
    for j in range(NY - 1, -1, -1):
        if not MASK[j, u]:
            continue
        y = yplane[j] - H[j, u] * VS
        if y >= ymin:
            continue
        if first:
            a = int(max(0, math.floor(y))); b = int(min(OH, math.ceil(y + SLAB)))
            if b > a:
                kk = np.linspace(0, 1, b - a)[:, None]
                col = np.array([120, 106, 88], np.float32) * (1 - kk) + np.array([58, 48, 40], np.float32) * kk
                out[a:b, x0:x0 + CW] = col[:, None, :].astype(np.uint8)
                alpha[a:b, x0:x0 + CW] = 255
                ids[a:b, x0:x0 + CW] = j
            first = False
        else:
            a = int(max(0, math.floor(y))); b = int(min(OH, math.ceil(ymin)))
            if b > a:
                v0 = max(0, min(TH - 1, int(round((j + 0.6) * 2 - 1))))
                v1 = max(0, min(TH - 1, int(round((jprev + 0.6) * 2 - 1))))
                if v1 == v0:
                    strip = np.repeat(tex_col[v0, u][None, :], b - a, axis=0)
                else:
                    vs = np.linspace(v0, v1, b - a).astype(np.int32)
                    strip = tex_col[vs, u]
                out[a:b, x0:x0 + CW] = strip[:, None, :].astype(np.uint8)
                alpha[a:b, x0:x0 + CW] = 255
                ids[a:b, x0:x0 + CW] = j
        ymin = y
        jprev = j

print("[oblique] %.1fs  %dx%d" % (time.time() - t0, OW, OH))
terr = Image.fromarray(np.dstack([out, alpha])).convert("RGBA")
d2 = ImageDraw.Draw(terr, "RGBA")


def screen_y(j, h):
    return yplane[j] - h * VS


# 林木
dens = np.clip(sstep(6, 90, H) * (1 - plain * 0.95) * (0.45 + 1.0 * fbm(shape, 21, 3, 1201)), 0, 1)
dens = np.where(MASK, dens, 0)
flat = dens.ravel()
nclump = 34000
idx = rng.choice(len(flat), size=nclump, replace=False, p=flat / flat.sum())
jj = idx // NX; ii = idx % NX
greens = np.array([(16, 40, 24), (24, 54, 28), (32, 66, 32), (42, 80, 36), (52, 92, 40)], np.int16)
auts = np.array([(186, 84, 22), (156, 44, 16), (206, 130, 34), (170, 58, 18)], np.int16)
for k in range(nclump):
    j0, i0 = jj[k], ii[k]
    aut_w = min(1.0, autumn[j0, i0] * 1.9)
    cx = i0 * CW + rng.uniform(0, CW); cy = screen_y(j0, H[j0, i0])
    f = 0.32 + 0.85 * min(1.8, shade[j0, i0]) * (1 - 0.55 * shadow[j0, i0])
    for m in range(rng.integers(5, 14)):
        x = cx + rng.normal(0, 5.0); y = cy + rng.normal(0, 3.2) - rng.uniform(0, 1.5)
        yi, xi = int(y), int(x)
        if yi < 0 or yi >= OH or xi < 0 or xi >= OW:
            continue
        if ids[yi, xi] < 0 or abs(ids[yi, xi] - j0) > 2:
            continue
        c = auts[rng.integers(0, 4)] if rng.random() < 0.07 + 0.7 * aut_w else greens[rng.integers(0, 5)]
        c = np.clip(c * f, 0, 255)
        r = rng.uniform(0.7, 1.6)
        d2.ellipse([x - r, y - r, x + r, y + r], fill=(int(c[0]), int(c[1]), int(c[2]), 210))
print("[trees] %.1fs" % (time.time() - t0))


# ---------------------------------------------------------------- 水系
def sample_h(u, j):
    u = int(max(0, min(NX - 1, round(u)))); j = int(max(0, min(NY - 1, round(j))))
    return H[j, u]


def densify(pts, step_km=0.8, wob=0.0, seed=0):
    r = np.random.default_rng(seed)
    out_ = []
    for (lo0, la0), (lo1, la1) in zip(pts[:-1], pts[1:]):
        d = math.hypot((lo1 - lo0) * 100.0, (la1 - la0) * 111.0)
        n = max(1, int(d / step_km))
        dx, dy = lo1 - lo0, la1 - la0
        L = math.hypot(dx, dy) or 1e-9
        nx_, ny_ = -dy / L, dx / L
        ph = r.uniform(0, 6.28)
        for t in np.linspace(0, 1, n, endpoint=False):
            w = wob * math.sin(t * 9.0 + ph) * 0.004
            out_.append((lo0 + dx * t + nx_ * w, la0 + dy * t + ny_ * w))
    out_.append(tuple(pts[-1]))
    return out_


def project(lo, la, lift=0.0):
    u = (lo - LON0) / (LON1 - LON0) * NX - 0.5
    jf = (LAT1 - la) / (LAT1 - LAT0) * NY - 0.5
    h = sample_h(u, jf)
    return (u * CW + CW / 2, OY0 + (jf + 0.5) * CH * KZ - h * VS - lift, jf)


def water_line(pts, width, col, alpha_=255):
    for p0, p1 in zip(pts[:-1], pts[1:]):
        x0, y0, j0 = p0; x1, y1, j1 = p1
        n = int(max(abs(x1 - x0), abs(y1 - y0)) * 1.2) + 1
        for t in np.linspace(0, 1, n):
            x = x0 + (x1 - x0) * t; y = y0 + (y1 - y0) * t; j = j0 + (j1 - j0) * t
            yi, xi = int(round(y)), int(round(x))
            if yi < 0 or yi >= OH or xi < 0 or xi >= OW:
                continue
            if ids[yi, xi] < 0 or abs(ids[yi, xi] - j) > 2:
                continue
            d2.ellipse([x - width / 2, y - width / 2, x + width / 2, y + width / 2], fill=col + (alpha_,))


LAKE_PTS = None
for l in [l for l in geo["lakes"] if l["n"] == "Poyang Hu"]:
    poly = chaikin(l["pts"], 4)
    LAKE_PTS = [project(lo, la, 0.6) for lo, la in poly]
    lay = Image.new("RGBA", (OW, OH), (0, 0, 0, 0))
    dl = ImageDraw.Draw(lay)
    dl.polygon([(p[0], p[1]) for p in LAKE_PTS], fill=(30, 132, 186, 246))
    dl.line([(p[0], p[1]) for p in LAKE_PTS] + [(LAKE_PTS[0][0], LAKE_PTS[0][1])],
            fill=(18, 96, 142, 255), width=3)
    terr = Image.alpha_composite(terr, lay)
    d2 = ImageDraw.Draw(terr, "RGBA")

for ri, r in enumerate(RIVERS):
    dpts = densify(r["pts"], 0.8, wob=1.0 if r["w"] >= 2 else 0.4, seed=ri)
    pts = [project(lo, la, 0.6) for lo, la in dpts]
    w = r["w"] * 2.0
    water_line(pts, w + 3.2, (12, 78, 122), 235)
    water_line(pts, w, (40, 148, 200), 245)
    water_line(pts, max(1.2, w * 0.34), (162, 232, 252), 200)
print("[water] %.1fs" % (time.time() - t0))

# ---------------------------------------------------------------- 天空、投影、云边
sk = np.zeros((OH, OW, 3), np.float32)
yy = np.linspace(0, 1, OH)[:, None, None]
sk[:] = np.array([226, 233, 235], np.float32) * (1 - yy) + np.array([252, 253, 252], np.float32) * yy
cl = fbm((OH, OW), 6, 4, 9001)
cl2 = fbm((OH, OW), 20, 3, 9101)
ca = sstep(0.40, 0.60, cl * 0.75 + cl2 * 0.25)
ca2 = sstep(0.46, 0.66, np.roll(cl, 22, axis=0) * 0.75 + np.roll(cl2, 22, 0) * 0.25)
sk = sk * (1 - 0.10 * ca2[..., None])
sk = sk * (1 - ca[..., None]) + np.array([255, 255, 255], np.float32) * ca[..., None]
bg = Image.fromarray(np.clip(sk, 0, 255).astype(np.uint8))

am = Image.fromarray(alpha)
sh_l = Image.new("L", (OW, OH), 0)
sh_l.paste(am, (16, 52))
sh_l = sh_l.filter(ImageFilter.GaussianBlur(22))
bg = Image.composite(Image.new("RGB", (OW, OH), (138, 140, 148)), bg, sh_l.point(lambda v: int(v * 0.45)))

scene = bg.convert("RGBA")
scene.alpha_composite(terr)

# 云带：仅在山体轮廓之外
halo = am.filter(ImageFilter.GaussianBlur(30))
ha = np.asarray(halo).astype(np.float32) / 255.0
ha = np.clip((ha - 0.22) / 0.5, 0, 1) ** 1.2
inside = np.asarray(am).astype(np.float32) / 255.0
ha = ha * np.clip(1.0 - inside * 1.4, 0, 1)
clouds = Image.new("RGBA", (OW, OH), (255, 255, 255, 0))
clouds.putalpha(Image.fromarray((ha * 235).astype(np.uint8)))
scene.alpha_composite(clouds)

# 额外的雾气团，贴边外扩
fog = Image.new("RGBA", (OW, OH), (0, 0, 0, 0))
fd = ImageDraw.Draw(fog)
for i in range(0, len(RING), 2):
    lo, la = RING[i]
    u = (lo - LON0) / (LON1 - LON0) * NX - 0.5
    j = (LAT1 - la) / (LAT1 - LAT0) * NY - 0.5
    jj_ = int(max(0, min(NY - 1, round(j)))); uu = int(max(0, min(NX - 1, round(u))))
    x, y = u * CW, OY0 + (j + 0.5) * CH * KZ - H[jj_, uu] * VS
    if rng.random() < 0.55:
        rr = rng.uniform(20, 56)
        fd.ellipse([x - rr * 1.8, y - rr * 0.55, x + rr * 1.8, y + rr * 1.0],
                   fill=(255, 255, 255, int(rng.uniform(35, 85))))
fog = fog.filter(ImageFilter.GaussianBlur(16))
fa = np.asarray(fog).astype(np.float32)
inside = np.asarray(am).astype(np.float32) / 255.0
fa[..., 3] *= np.clip(1.0 - inside * 0.85, 0, 1)
scene.alpha_composite(Image.fromarray(fa.astype(np.uint8)))

# ---------------------------------------------------------------- 注记
d3 = ImageDraw.Draw(scene, "RGBA")


def fnt(size, serif=False):
    return ImageFont.truetype(FONT_SERIF if serif else FONT_CITY, size)


def spaced(d, xy, text, font, fill, stroke=None, sw=0, anchor="mm", gap=3, shadow=None):
    """带字距的文字。xy 为 anchor 指定位置。"""
    widths = [d.textlength(ch, font=font) for ch in text]
    total = sum(widths) + gap * (len(text) - 1)
    if anchor[0] == "m":
        x = xy[0] - total / 2
    elif anchor[0] == "r":
        x = xy[0] - total
    else:
        x = xy[0]
    y = xy[1]
    for ch, w in zip(text, widths):
        if shadow:
            d.text((x + shadow[0], y + shadow[1]), ch, font=font, fill=shadow[2], anchor="lm",
                   stroke_width=sw, stroke_fill=shadow[2])
        d.text((x, y), ch, font=font, fill=fill, anchor="lm", stroke_width=sw, stroke_fill=stroke or fill)
        x += w + gap
    return total


def rot_text(img, xy, text, font, fill, stroke, sw, angle, gap=3):
    tmp = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    dd = ImageDraw.Draw(tmp)
    widths = [dd.textlength(ch, font=font) for ch in text]
    total = int(sum(widths) + gap * (len(text) - 1)) + 2 * sw + 8
    h = int(font.size * 1.5) + 2 * sw + 8
    tmp = Image.new("RGBA", (total, h), (0, 0, 0, 0))
    dd = ImageDraw.Draw(tmp)
    x = sw + 4
    for ch, w in zip(text, widths):
        dd.text((x + 1, h / 2 + 2), ch, font=font, fill=(0, 0, 0, 90), anchor="lm", stroke_width=sw,
                stroke_fill=(0, 0, 0, 90))
        dd.text((x, h / 2), ch, font=font, fill=fill, anchor="lm", stroke_width=sw, stroke_fill=stroke)
        x += w + gap
    tmp = tmp.rotate(angle, resample=Image.BICUBIC, expand=True)
    img.alpha_composite(tmp, (int(xy[0] - tmp.width / 2), int(xy[1] - tmp.height / 2)))


def pin(d, x, y, s=1.0):
    r = 13 * s
    d.ellipse([x - r, y - 2.6 * r, x + r, y - 0.6 * r], fill=(34, 44, 58, 255))
    d.polygon([(x - r * 0.72, y - 1.35 * r), (x + r * 0.72, y - 1.35 * r), (x, y)], fill=(34, 44, 58, 255))
    d.ellipse([x - r * 0.42, y - 2.3 * r, x + r * 0.42, y - 1.45 * r], fill=(245, 248, 250, 255))


def city(d, x, y, name, dx, dy, tag=None):
    pin(d, x, y)
    size = 46
    f = fnt(size)
    tw = d.textlength(name, font=f)
    w = tw + 40
    h = 62
    bx = x + dx - w / 2
    by = y + dy - h / 2
    # 引线
    if abs(dx) > 40 or abs(dy) > 40:
        d.line([(x, y - 6), (bx + w / 2, by + h / 2)], fill=(60, 56, 50, 120), width=2)
    d.rounded_rectangle([bx + 2, by + 4, bx + w + 2, by + h + 4], radius=14, fill=(60, 50, 40, 55))
    d.rounded_rectangle([bx, by, bx + w, by + h], radius=14, fill=(255, 253, 250, 246),
                        outline=(206, 198, 184, 255), width=2)
    d.text((bx + w / 2, by + h / 2 + 1), name, font=f, fill=(190, 40, 32, 255), anchor="mm")
    return (bx, by, bx + w, by + h)


d3 = ImageDraw.Draw(scene, "RGBA")

# 山脉名（白字深描边，字距宽）
for rg in RANGE:
    x, y, jf = project(rg["x"], rg["y"])
    size = rg.get("size", 40) * (0.85 if SMALL else 1.0)
    f = fnt(size, serif=False)
    if rg.get("kind") == "basin":
        spaced(d3, (x, y), rg["n"], f, (255, 252, 240, 210), (94, 78, 44, 200), 4, "mm", gap=6)
    elif abs(rg.get("angle", 0)) > 20:
        rot_text(scene, (x, y), rg["n"], f, (255, 255, 255, 250), (44, 40, 34, 255), 5,
                 rg["angle"], gap=5)
        d3 = ImageDraw.Draw(scene, "RGBA")
    else:
        spaced(d3, (x, y), rg["n"], f, (255, 255, 255, 250), (44, 40, 34, 255), 5, "mm", gap=6)

# 山峰名
for p in PEAK:
    x, y, jf = project(p["x"], p["y"])
    f = fnt(30)
    spaced(d3, (x + p["dx"], y + p["dy"]), p["n"], f, (255, 255, 255, 235), (52, 48, 40, 230), 3.5, "mm", gap=2)

# 河名
for nm, (lo, la, ang) in RIVER_LABEL.items():
    x, y, jf = project(lo, la)
    f = fnt(30)
    rot_text(scene, (x, y - 14), nm, f, (196, 240, 255, 250), (10, 62, 96, 255), 4, ang, gap=2)
    d3 = ImageDraw.Draw(scene, "RGBA")

# 湖名
lx, ly, _ = project(LAKE_LABEL["x"], LAKE_LABEL["y"])
f = fnt(44)
spaced(d3, (lx + LAKE_LABEL["dx"], ly + LAKE_LABEL["dy"]), LAKE_LABEL["n"], f,
       (228, 248, 255, 255), (8, 62, 100, 255), 5, "mm", gap=7)

# 城市
for c in CITY:
    x, y, jf = project(c["x"], c["y"])
    city(d3, x, y, c["n"], c["dx"], c["dy"])

print("[labels] %.1fs" % (time.time() - t0))

# ---------------------------------------------------------------- 题签 / 图例 / 指北
d4 = d3
# 题签
bx, by, bw, bh = 64, 58, 470, 190
d4.rounded_rectangle([bx, by, bx + bw, by + bh], radius=10, fill=(252, 250, 244, 226),
                     outline=(150, 140, 120, 190), width=2)
d4.rectangle([bx + 14, by + 14, bx + 22, by + bh - 14], fill=(158, 44, 34, 255))
f_title = ImageFont.truetype(FONT_SERIF, 88)
d4.text((bx + 46, by + 22), "江西", font=f_title, fill=(40, 36, 30, 255))
f_sub = ImageFont.truetype(FONT_SERIF, 26)
d4.text((bx + 48, by + 128), "山河图", font=f_sub, fill=(96, 82, 64, 255))
d4.text((bx + 168, by + 128), "J I A N G X I", font=ImageFont.truetype(FONT_SANS, 20), fill=(150, 138, 118, 255))
# 印
d4.rounded_rectangle([bx + bw - 92, by + 46, bx + bw - 28, by + 110], radius=6, fill=(158, 44, 34, 235))
d4.text((bx + bw - 60, by + 78), "赣", font=ImageFont.truetype(FONT_SERIF, 46), fill=(255, 246, 238, 255),
        anchor="mm")

# 比例尺
sx, sy = 90, OH - 96
km50 = 50 / (KMX * NX) * OW
d4.line([(sx, sy), (sx + km50 * 2, sy)], fill=(60, 56, 48, 220), width=4)
for i in range(3):
    d4.line([(sx + km50 * i, sy - 9), (sx + km50 * i, sy + 9)], fill=(60, 56, 48, 220), width=4)
d4.text((sx, sy + 26), "0", font=fnt(22), fill=(60, 56, 48, 230), anchor="ma")
d4.text((sx + km50, sy + 26), "50", font=fnt(22), fill=(60, 56, 48, 230), anchor="ma")
d4.text((sx + km50 * 2, sy + 26), "100 km", font=fnt(22), fill=(60, 56, 48, 230), anchor="ma")

# 指北针
nx_, ny_ = OW - 120, OH - 150
d4.ellipse([nx_ - 46, ny_ - 46, nx_ + 46, ny_ + 46], fill=(252, 250, 244, 210), outline=(60, 56, 48, 160), width=2)
d4.polygon([(nx_, ny_ - 34), (nx_ + 15, ny_ + 12), (nx_, ny_ + 2), (nx_ - 15, ny_ + 12)], fill=(158, 44, 34, 255))
d4.text((nx_, ny_ - 56), "N", font=fnt(24), fill=(60, 56, 48, 230), anchor="mm")

# 注记
f_note = fnt(22)
d4.text((OW - 40, OH - 44), "高程 SRTM · 省界 DataV.GeoAtlas · 河流示意",
        font=f_note, fill=(120, 116, 108, 220), anchor="rs")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
final = scene.convert("RGB")
arr = np.asarray(final).astype(np.float32) / 255.0
arr = np.clip((arr - 0.46) * 1.09 + 0.47, 0, 1)          # 轻微 S 曲线
arr = np.clip(arr ** 0.94, 0, 1)                          # 提亮中间调
lum = arr.mean(axis=2, keepdims=True)
arr = np.clip(lum + (arr - lum) * 1.16, 0, 1)             # 加饱和
final = Image.fromarray((arr * 255).astype(np.uint8))
final.save(OUT, optimize=True)
print("[save] %s  %.1f MB  %.1fs" % (OUT, os.path.getsize(OUT) / 1e6, time.time() - t0))
