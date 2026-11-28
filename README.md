# 知识收集 · 站点仓库使用说明

> **这份文档给谁看**：给「另一台电脑上的你」，也给「另一个 AI 会话」。
> 目标只有一个：在任何一台电脑上 `git clone` 之后，得到与当前电脑**完全一致**的页面内容和地理数据，并且用同样的流程修改、发布。

---

## 0. 一句话原理

**仓库就是唯一的事实来源。**

- 页面源码（`.html`）在仓库里；
- 地理数据（`data/*.js`）**也提交在仓库里**，不是发布时才生成的；
- 生成这些数据的脚本（`.dev/*.py`）同样在仓库里。

所以新电脑 `clone` 下来，**不需要重新生成任何数据**，打开就是一样的。两台电脑之所以「逻辑一致」，靠的是这条纪律：**数据文件永远由脚本生成后提交，任何人都不要手改 `data/*.js`。**

---

## 1. 站点信息

| 项目 | 值 |
| --- | --- |
| 线上首页 | <https://mysillyboy.github.io/pages/> |
| 仓库 | <https://github.com/mysillyboy/pages> |
| 本地 remote | `git@github.com:mysillyboy/pages.git`（SSH） |
| 发布分支 | `main`，根目录 |
| 发布方式 | GitHub Pages「从分支发布」，**无构建步骤**，推送后 30～90 秒自动生效 |

> ⚠️ 站点挂在 `/pages/` 路径下。直接访问 `mysillyboy.github.io` 会得到 404「Site not found」，这是**正常的**——根域名只属于名为 `mysillyboy.github.io` 的仓库，而你没有这个仓库。

---

## 2. 目录结构

```
根目录/
├─ index.html                站点首页（五个页面的入口卡片）
├─ weread-dashboard.html     微信读书 · 阅读看板
├─ 国产汽车品牌关系图.html
├─ 中国历代王朝·幻灯片.html
├─ 中国地势3D.html            三维地势图（WebGL2，无第三方库）
├─ 中国历史地理总图.html       全国平面总图（SVG）
├─ robots.txt
├─ _config.yml               Jekyll 配置：把开发文件排除出站点
├─ AGENTS.md                 给 AI 的强制规则（改前校验、改后发布）
├─ README.md                 本文件
├─ data/                     ← 数据层，全部由脚本生成，禁止手改
│  ├─ regions.js             三维图区域清单（手写，新增区域在此登记）
│  ├─ geo-huaxia.js          三维区域数据（terrarium 高程 + OSM 河流 + 省界）
│  └─ china-map.js           全国总图数据（省界 + Natural Earth 河流 + 地名）
└─ .dev/                     ← 工具层，不会被发布到网站
   ├─ check-sync.ps1         改文件前的一致性校验
   ├─ publish.ps1            提交 → 推送 → 等 Pages → 验证线上
   ├─ preview.ps1            本地预览服务器（默认 8000 端口）
   ├─ serve.mjs              preview 在没有 Python 时的兜底服务器
   ├─ wait-pages.mjs         publish 用来等待线上更新的辅助脚本
   ├─ geo-build.py           生成 data/geo-<id>.js
   └─ geo-china-map.py       生成 data/china-map.js
```

`_config.yml` 已经把这些排除出站点，所以 `AGENTS.md`、`README.md`、`.dev/` **不会出现在线上网站**。

---

## 3. 数据是怎么来的（一致性核心）

| 数据文件 | 生成脚本 | 数据来源 | 许可 |
| --- | --- | --- | --- |
| `data/geo-huaxia.js` | `.dev/geo-build.py` | 高程 Mapzen / AWS Terrain Tiles（SRTM）；河流 OpenStreetMap Overpass；省界 阿里云 DataV.GeoAtlas | CC-BY / ODbL / 仅方位参照 |
| `data/china-map.js` | `.dev/geo-china-map.py` | 省界 DataV.GeoAtlas；河流 Natural Earth 10m | 仅方位参照 / 公有领域 |
| `data/regions.js` | 手写 | — | — |

**两条铁律：**

1. **`data/*.js` 一律不要手改。** 它们是构建产物，改了下一次重跑就丢。
2. **改了脚本就要重跑并把产物一起提交**，否则两台电脑的数据会不一致。

> 省界数据仅作方位参照，**不是精确国界，不要当作边界依据**。

---

## 4. 新电脑第一次拉取（照做即可）

### 4.1 需要装什么

| 工具 | 是否必需 | 用途 |
| --- | --- | --- |
| Git for Windows | ✅ 必需 | 拉取、提交、推送 |
| PowerShell 5.1+ | ✅ 必需 | Windows 自带，跑 `.dev/*.ps1` |
| Python 3 + numpy + pillow | ⬜ 可选 | **只在要重新生成地理数据时需要** |
| Node.js | ⬜ 可选 | 预览服务器兜底；`publish.ps1` 用它校验线上更准 |

只要改页面、发布，前两个就够了。

### 4.2 配置 GitHub 访问

**方案 A：SSH（推荐，当前这台电脑用的就是它）**

```powershell
# 1. 生成密钥（一路回车，不要设密码）
ssh-keygen -t ed25519 -C "pages-另一台电脑" -f $env:USERPROFILE\.ssh\id_ed25519_pages

# 2. 打印公钥，整行复制
Get-Content $env:USERPROFILE\.ssh\id_ed25519_pages.pub
```

打开 <https://github.com/settings/ssh/new>，Title 随便写，Key 粘贴整行，点 **Add SSH key**。

然后编辑 `C:\Users\<你>\.ssh\config`（没有就新建），写入：

```
Host github.com
    HostName ssh.github.com
    Port 443
    User git
    IdentityFile ~/.ssh/id_ed25519_pages
    IdentitiesOnly yes
```

> **为什么要拐到 443**：在国内网络下 `github.com:443` 的 HTTPS 会被间歇性重置（表现为 `Failed to connect ... port 443` 或 `Connection was reset`），而 `ssh.github.com:443` 稳定。这个配置就是为此存在的。

验证：

```powershell
ssh -T git@github.com
# 期望看到：Hi mysillyboy! You've successfully authenticated...
```

第一次连接会问是否信任主机指纹，输入 `yes`。

**方案 B：HTTPS + Personal Access Token**

不配 SSH 的话，直接 `git clone https://github.com/mysillyboy/pages.git`，推送时用户名填 `mysillyboy`、密码填 PAT。缺点是这条链路在当前网络下不稳定。

### 4.3 拉取并验证

```powershell
git clone git@github.com:mysillyboy/pages.git
cd pages

# 校验：本地是否与 GitHub 完全一致（期望退出码 0）
powershell -NoProfile -ExecutionPolicy Bypass -File .dev/check-sync.ps1
```

看到 `[SYNC] 本地与远端完全一致，可以开始修改文件。` 就说明环境对了，**数据和当前电脑完全一样，不需要跑任何生成脚本**。

### 4.4 本地预览

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .dev/preview.ps1
# 然后打开 http://127.0.0.1:8000/
```

---

## 5. 日常改动流程

```
① check-sync 必须返回 0     →  改文件  →  ② publish 一键发布
```

```powershell
# ① 动手前
powershell -NoProfile -ExecutionPolicy Bypass -File .dev/check-sync.ps1

# ② 改完之后
powershell -NoProfile -ExecutionPolicy Bypass -File .dev/publish.ps1 -Message "说明这次改了什么"
```

`publish.ps1` 会依次：一致性校验 → 提交 → 推送 `origin/main` → 等待 Pages 重新构建 → 校验线上 `Last-Modified` 已更新。成功会打印提交哈希和线上地址。

`check-sync.ps1` 的退出码含义见 [AGENTS.md](AGENTS.md)，简版：

| 码 | 含义 | 该做什么 |
| --- | --- | --- |
| 0 | 完全一致 | ✅ 可以改 |
| 2 | 落后 | 先 `git pull --ff-only` |
| 3 | 领先（有未推送提交） | 可以改，收尾要推 |
| 4 | 已分叉 | ⛔ 停下，问人 |
| 5 | 有未提交改动 | 先处理干净 |

---

## 6. 重新生成地理数据

### 6.1 什么时候才需要

平时改页面**完全不需要**。只有这几种情况：

- 新增一个三维区域
- 调整区域的 `bbox` / 分辨率 `out_w` / 高程夸张 `vex` / `gamma`
- 上游数据源更新，想刷新数据

### 6.2 装依赖

```powershell
python -m pip install numpy pillow
```

（当前这台机器：Python 3.12.4、numpy 2.3.4 已装，Pillow 需按上面命令补装。）

### 6.3 跑脚本

```powershell
python .dev/geo-build.py --region=huaxia          # 生成 data/geo-huaxia.js
python .dev/geo-build.py --region=huaxia --preview # 额外输出二维校验图到临时目录
python .dev/geo-china-map.py                      # 生成 data/china-map.js
```

`geo-build.py` 支持的参数：`--region=<id>` 或 `--region <id>`、`--fast`（跳过 Overpass，用 Natural Earth 兜底）、`--preview`。

需要联网，访问这些域名：S3 高程瓦片、`overpass-api.de`（及两个镜像）、`geo.datav.aliyun.com`、`raw.githubusercontent.com`。下载内容缓存在 `%TEMP%\geo3d-cache`，**删掉这个目录可强制重新下载**。

### 6.4 新增一个三维区域：四处都要改（最容易漏）

1. `.dev/geo-build.py` 的 `REGIONS` 字典加一条（`id` / `name` / `sub` / `bbox` / `out_w` / `zoom` / `gamma` / `vex`）
2. `.dev/geo-china-map.py` 里的 `REGIONS` 列表加一条（决定全国总图上那个定位框）
3. `data/regions.js` 登记一条（`id` / `name` / `file`）
4. 跑两个脚本生成产物

**四处缺一，两台电脑或两个页面就会对不上。** 生成完把 `data/*.js` 一起提交。

---

## 7. 排错速查

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `mysillyboy.github.io` 打不开 / 404 | 根域名没有对应的仓库 | 用 `https://mysillyboy.github.io/pages/` |
| 推送报 `Permission denied (publickey)` | 密钥没加到 GitHub，或 `~/.ssh/config` 没配 | 重做 4.2 |
| `Failed to connect to github.com port 443` / `Connection was reset` | HTTPS 链路被干扰 | 用 SSH 方案；或检查 `hosts` 里 `github.com` 是否被钉到失效 IP（`140.82.121.4` 已失效） |
| 发布成功但页面没变 | 浏览器缓存 | `Ctrl+F5` 强刷 |
| 中文显示成乱码 | 文件存成了 GBK | 一律保存为 **UTF-8 无 BOM** |
| `pwsh` 报 `Access to the path '\\.\pipe\LOCAL\dotnet_...' is denied` | 在 DSH 沙箱里跑 PowerShell 7，沙箱禁止命名管道 | 改用 `powershell`（5.1） |
| Git 报 `couldn't create signal pipe` | Git 自带的 msys ssh 在沙箱里起不来 | `git config --local core.sshCommand 'C:/Windows/System32/OpenSSH/ssh.exe'` |

---

## 8. 约定

- 纯静态站：HTML/CSS/JS 内联，无打包、无后端、无第三方库。
- 全站 `noindex`，不要引入统计/追踪脚本。
- 不要 `git push --force`，不要改写已推送的历史。
- 不要把 token、密码写进任何文件。
- 新增页面后记得在 `index.html` 的卡片列表里补一条。

---

## 9. 相关文档

- [AGENTS.md](AGENTS.md) —— 强制规则全文，AI 会话每次都会读它
- 站点首页：<https://mysillyboy.github.io/pages/>
