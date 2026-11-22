# 项目规则 · GitHub Pages 静态站

本目录是 <https://github.com/mysillyboy/pages> 的本地克隆。站点通过 **GitHub Pages 从 `main` 分支根目录直接发布**，没有构建步骤、没有后端。

- 线上首页：<https://mysillyboy.github.io/pages/>
- 远程仓库：`origin` → `git@github.com:mysillyboy/pages.git`（SSH）
- 发布分支：`main`

## 运行环境

- 本机同时装有 Windows PowerShell 5.1 与 PowerShell 7.7（`pwsh`）。`.dev/` 下的脚本一律按 5.1 语法编写，**两个版本都能运行**。
- **在 DSH 会话里请用 `powershell`（5.1）执行脚本**：沙箱不允许创建命名管道，而 PowerShell 7 捕获原生命令输出正需要它，用 `pwsh` 跑会出现 `Access to the path '\\.\pipe\LOCAL\dotnet_...' is denied`。这是沙箱限制，不是脚本问题。
- 推送走 SSH：`~/.ssh/config` 已把 `github.com` 转发到 `ssh.github.com:443`（绕开常被干扰的 443 HTTPS）；仓库的 `core.sshCommand` 指向 Windows 原生 OpenSSH，避免 Git 自带的 msys ssh 在沙箱里起不来。

## 铁律一：改任何文件之前，先确认本地与 GitHub 完全一致

**任何文件修改之前（新建、编辑、删除、批量替换都算），必须先证明本地代码与 GitHub 上 `main` 的最新代码是一致的。**

执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .dev/check-sync.ps1
```

按下表的退出码行事：

| 退出码 | 含义 | 必须怎么做 |
| --- | --- | --- |
| `0` | 本地干净且与 `origin/main` 完全一致 | ✅ 可以开始修改 |
| `1` | 拉不到远端（网络/凭据问题）或不是 git 仓库 | ⛔ 停止，先解决连接问题，不要改文件 |
| `2` | 本地落后（GitHub 上有你还没拉下来的提交） | ⛔ 先 `git pull --ff-only origin main`，重新校验通过后再改 |
| `3` | 本地领先（有未推送提交，远端内容已全部包含在本地） | ⚠️ 可以继续，但收尾时必须推送 |
| `4` | 本地与远端已分叉 | ⛔ 立刻停止，向用户说明情况并征求意见，禁止自行 rebase / merge / 强推 |
| `5` | 工作区有未提交的改动 | ⛔ 先提交或先处理干净，再继续 |

**校验不通过就不许动文件。** 不允许“先把改动写进去、之后再想办法同步”。也不要为了让校验通过而使用 `git stash`、`git reset --hard`、`git push --force` 这类会丢代码的操作；需要这么做时先问用户。

## 铁律二：改完之后必须推送并确认已发布

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .dev/publish.ps1 -Message "简短说明本次改动"
```

脚本依次完成：同步校验 →（有改动则）提交 → 推送到 `origin/main` → 等待 GitHub Pages 重新构建 → 校验线上地址。

推送完成后向用户报告三件事：**提交哈希**、**线上地址**、**发布是否已确认**。

## 编辑约定

- 纯静态站：只有 HTML / CSS / JS，文件中直接内嵌样式与脚本，不做打包。
- 新增页面放到仓库根目录，并在 `index.html` 的卡片列表里补一条链接（编号、标题、描述、文件名四件套）。
- 页面文件名可以是中文，链接里直接写中文文件名即可（Pages 支持）。
- 站点已加 `noindex`，不要再引入统计脚本、外部字体等追踪资源。
- 改动 HTML 后建议本地预览：`powershell -NoProfile -ExecutionPolicy Bypass -File .dev/preview.ps1`

## 安全约定

- 推送凭据只存放在 **Windows 凭据管理器（Git Credential Manager）** 里，由 git 自动取用。
- **绝对不要**把 token、密码写进任何仓库文件、脚本、注释或提交信息。
- 不要修改 `.git/config` 里的 remote 地址；不要给仓库加 `--force` 推送习惯。
- 不要提交 `.dev/` 之外的临时文件；不要提交系统生成物。

## 目录说明

```
.dev/check-sync.ps1    本地与 GitHub 一致性校验（改文件前必跑）
.dev/publish.ps1       提交 + 推送 + 等待 Pages 发布
.dev/preview.ps1       本地预览服务器（默认 http://127.0.0.1:8000/）
.dev/serve.mjs         preview.ps1 在没有 python 时使用的静态服务器
.dev/wait-pages.mjs    publish.ps1 用来等待线上更新的辅助脚本
.dev/geo-build.py      生成 data/geo-*.js（高程瓦片 + OSM 河流 + 省界），需要 numpy/Pillow 与联网
.dev/geo-china-map.py  生成 data/china-map.js（全国平面总图：省界 + 河流 + 地名）
index.html             站点首页（五个页面的入口卡片）
weread-dashboard.html  微信读书阅读看板
国产汽车品牌关系图.html
中国历代王朝·幻灯片.html
中国地势3D.html        中国本部三维地势图（WebGL2，无第三方库）
中国历史地理总图.html  全国平面总图（SVG，省界/河流/重镇）
data/geo-*.js          各区域地形与河流数据，由 .dev/geo-build.py 生成，不要手改
data/regions.js        三维图区域清单（新增区域在此登记）
data/china-map.js      全国总图数据，由 .dev/geo-china-map.py 生成
```
