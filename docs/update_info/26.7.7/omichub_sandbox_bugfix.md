# OmicHub 沙盒终端问题修复记录

> **日期**: 2026-07-07  
> **问题**: ① oh-my-posh Nerd Font 符号在 xterm.js 中乱码；② 用户 workspace 未正确挂载到宿主机目录。

---

## 1. 问题一：字体乱码（Nerd Font 符号显示为方块）

### 1.1 根因分析

当前容器内配置了 `oh-my-posh` + `oh-my-zsh` 作为 Shell 提示符，主题使用了 Nerd Font 的私有 Unicode 字符（PUA 区域）：

| 符号 | Unicode | 用途 |
|------|---------|------|
|  | U+E0B0 | Powerline 分隔符（右箭头） |
|  | U+E0B2 | Powerline 分隔符（左箭头） |
|  | U+EA83 | 文件夹图标 |
|  | U+EBA2 | 执行时间图标 |
|  | U+E23A | 状态指示器 |
|  | U+F489 | 终端图标 |

xterm.js 在浏览器中运行，默认使用系统自带的等宽字体（如 Menlo、Monaco、Consolas、"Courier New"）。这些字体**不包含** Nerd Font 的 PUA 字符，因此显示为方块或乱码。citeweb_search:2#1web_search:2#12

### 1.2 修复方案对比

| 方案 | 实现位置 | 优点 | 缺点 | 推荐度 |
|------|---------|------|------|--------|
| **A. 前端加载 Nerd Font** | `XTerminal.vue` | 保留 oh-my-posh 完整视觉效果 | 需引入 3-5MB 字体文件，首次加载慢 | ⭐⭐⭐ |
| **B. 后端切换 minimal 主题** | `docker/zshrc` | 零前端改动，轻量 | 失去图标，提示符变纯文本 | ⭐⭐⭐⭐⭐ |
| **C. 自定义 PS1（无 oh-my-posh）** | `docker/zshrc` | 完全可控，零依赖 | 需手动维护配色逻辑 | ⭐⭐⭐⭐ |

> **推荐采用方案 B + 方案 A 作为进阶选项**。先切 minimal 主题解决乱码，后续再考虑前端加载字体提升体验。

---

### 1.3 方案 B：后端切换 oh-my-posh minimal 主题（推荐）

oh-my-posh 官方提供 `minimal` 系列主题，**完全不使用 Nerd Font 图标**，仅通过颜色和基础 ASCII 字符构建提示符。citeweb_search:2#10web_search:2#12

**修改 `docker/zshrc`**：

```bash
# 之前（使用完整主题，依赖 Nerd Font）
eval "$(oh-my-posh init zsh --config /usr/share/oh-my-posh/themes/jandedobbeleer.omp.json)"

# 之后（使用 minimal 主题，无 Nerd Font 依赖）
# 注意：实测 agnoster.minimal 仍包含 Powerline 箭头（U+E0B0），浏览器默认字体仍会乱码，
#       推荐选用 onehalf.minimal / probua.minimal 等真正无 PUA 图标的主题。
eval "$(oh-my-posh init zsh --config /usr/share/oh-my-posh/themes/onehalf.minimal.omp.json)"
```

**可选 minimal 主题清单**：

```bash
# 查看所有 minimal 主题
ls /usr/share/oh-my-posh/themes/*.minimal.omp.json

# 常用推荐（已在容器内验证无 Nerd Font 图标）：
# - onehalf.minimal.omp.json     简洁单色，无图标
# - probua.minimal.omp.json      简洁路径高亮，无图标
```

**效果对比**：

```
# 之前（乱码）
   workspace   5ms    ls

# 之后（onehalf minimal 主题）
@container ~/workspace (0) > ls
```

---

### 1.4 方案 C：彻底移除 oh-my-posh，使用自定义 PS1（最轻量）

如果 minimal 主题仍不理想，可直接用 zsh 原生 `PROMPT` 自定义一个简洁的提示符：

**修改 `docker/zshrc`**：

```bash
# 禁用 oh-my-posh（注释掉或删除）
# eval "$(oh-my-posh init zsh ...)"

# 自定义 PS1：显示 [user@host] path $ 
# 颜色：路径青色，提示符绿色（成功）/红色（失败）
autoload -Uz colors && colors

PROMPT='%{$fg[cyan]%}[%n@%m] %~%{$reset_color%} %(?.%{$fg[green]%}.%{$fg[red]%})%#%{$reset_color%} '

# 可选：添加时间戳到右侧 RPROMPT
RPROMPT='%{$fg[grey]%}%D{%H:%M:%S}%{$reset_color%}'
```

**效果**：
```
[omichub@sandbox] /home/omichub/workspace $ ls
```

---

### 1.5 方案 A：前端加载 Nerd Font（进阶）

如果希望保留完整的 oh-my-posh 视觉效果，需要在前端加载 Nerd Font。

**步骤 1：下载 Nerd Font 到前端静态目录**

```bash
# 下载 JetBrainsMono Nerd Font（推荐，清晰度高）
cd frontend/public/fonts
wget https://github.com/ryanoasis/nerd-fonts/releases/download/v3.2.1/JetBrainsMono.zip
unzip JetBrainsMono.zip
# 保留 JetBrainsMonoNerdFont-Regular.ttf 等必需文件
```

**步骤 2：在 `XTerminal.vue` 中配置字体**

```typescript
// 加载字体 CSS（可在 index.html 或组件内引入）
// @font-face {
//   font-family: 'JetBrainsMono NF';
//   src: url('/fonts/JetBrainsMonoNerdFont-Regular.ttf') format('truetype');
//   font-weight: 400;
//   font-style: normal;
// }

const term = new Terminal({
  fontFamily: '"JetBrainsMono NF", "Fira Code", "Cascadia Code", Menlo, Monaco, "Courier New", monospace',
  fontSize: 14,
  // 确保 WebGL 渲染器启用，提升字体渲染质量
  rendererType: 'dom', // 或 'canvas'，如果 addon-webgl 已加载
});
```

> ⚠️ 注意：Nerd Font 完整版 TTF 文件约 3-5MB，建议仅加载 Regular 字重，或采用 `font-display: swap` 避免阻塞渲染。

---

## 2. 问题二：用户目录挂载失败

### 2.1 现象

容器内 `pwd` 返回 `/home/omichub/workspace`，但 `df -h` 显示：

```
overlay  1.8T  1.1T  588G  65% /
```

说明容器根文件系统仍是镜像自身的 `overlay`，用户宿主机目录 `/data/omichub/users/81427715-6aba-4335-9533-1f78e23686c1` **没有被挂载进来**。容器内看到的 `workspace` 目录只是镜像构建时创建的空白目录。

### 2.2 根因分析

检查 `docker_manager.py` 中的容器创建逻辑，常见错误：

1. ** volumes 参数格式错误**：Docker SDK 的 `volumes` 参数格式与命令行 `-v` 不同
2. **宿主机路径不存在**：Docker 不会自动创建宿主机目录（与 CLI 行为不同）
3. **权限问题**：宿主机目录权限与容器内 `user=1000:1000` 不匹配，导致挂载后无法写入
4. **路径变量未正确拼接**：`uid` 变量未传入或格式错误

### 2.3 正确挂载方式

**Docker SDK (`docker-py`) 正确写法**：

```python
import os
from docker import DockerClient

client = DockerClient.from_env()

uid = "81427715-6aba-4335-9533-1f78e23686c1"
host_workspace = f"/data/omichub/users/{uid}/workspace"
container_workspace = "/home/omichub/workspace"

# 确保宿主机目录存在（Docker SDK 不会自动创建）
os.makedirs(host_workspace, exist_ok=True)

# 设置目录权限与容器内用户一致（1000:1000）
os.chown(host_workspace, 1000, 1000)  # 或 shutil.chown

container = client.containers.run(
    image="omichub/sandbox-terminal:latest",
    name=f"ttyd-{session_id}",
    network="omichub-sandbox-net",  # 如已 Swarm 化

    # 正确格式：字典，key 为宿主机绝对路径，value 为挂载配置
    volumes={
        host_workspace: {
            "bind": container_workspace,
            "mode": "rw",
        },
    },

    # 安全参数
    user="1000:1000",
    read_only=True,
    cap_drop=["ALL"],
    security_opt=["no-new-privileges:true"],
    mem_limit="512m",
    memswap_limit="512m",
    pids_limit=100,

    # 临时目录用 tmpfs
    tmpfs={
        "/tmp": "rw,noexec,nosuid,size=100m",
        "/home/omichub/.cache": "rw,noexec,nosuid,size=50m",
    },

    # 自动销毁
    auto_remove=True,
    detach=True,
    tty=True,
)
```

**命令行等效验证**：

```bash
# 手动测试挂载是否正确
docker run -it --rm \
  -v /data/omichub/users/81427715-6aba-4335-9533-1f78e23686c1/workspace:/home/omichub/workspace:rw \
  -u 1000:1000 \
  --read-only \
  --cap-drop ALL \
  omichub/sandbox-terminal:latest \
  bash -c "pwd && ls -la && touch /home/omichub/workspace/test.txt && echo 'OK'"
```

### 2.4 常见问题排查

| 现象 | 排查命令 | 解决方案 |
|------|---------|---------|
| 容器内 `workspace` 为空，但宿主机有文件 | `docker inspect <container_id> | grep -A 10 Mounts` | 检查 volumes 字典格式是否正确 |
| 容器内无法写入 workspace | `ls -la /data/omichub/users/{uid}/workspace` | 宿主机目录权限改为 `1000:1000` |
| 宿主机目录不存在导致启动失败 | `ls -d /data/omichub/users/{uid}` | 在 `create_container()` 前加 `os.makedirs()` |
| 挂载后文件显示但内容不对 | `mount | grep workspace` | 确认没有重复挂载或覆盖 |

---

## 3. 修复检查清单

### 3.1 字体修复

- [ ] 修改 `tools/terminal/docker/zshrc`，将 oh-my-posh 主题切换为 `onehalf.minimal.omp.json`（或自定义 PS1）
- [ ] 重新构建镜像：`docker build -t omichub/sandbox-terminal:latest tools/terminal/docker/`
- [ ] 启动新容器，验证提示符无乱码
- [ ] （可选）前端加载 Nerd Font，恢复完整图标体验

### 3.2 挂载修复

- [ ] 检查 `docker_manager.py` 中 `volumes` 参数格式是否为字典形式
- [ ] 在创建容器前添加 `os.makedirs(host_workspace, exist_ok=True)`
- [ ] 确保宿主机目录权限为 `1000:1000`（与容器内用户一致）
- [ ] 手动运行测试命令验证挂载和读写
- [ ] 检查 `df -h` 在容器内是否显示宿主机挂载点

---

## 4. 相关文件路径

| 文件 | 作用 | 修改内容 |
|------|------|---------|
| `tools/terminal/docker/zshrc` | 容器内 Shell 环境 | oh-my-posh 主题切换 / 自定义 PS1 |
| `tools/terminal/docker/Dockerfile` | 镜像构建 | 如需更换主题文件，确保 COPY 正确 |
| `src/omichub/infrastructure/terminal/docker_manager.py` | 容器生命周期管理 | 修正 volumes 参数、添加目录预创建逻辑 |
| `frontend/src/components/terminal/XTerminal.vue` | xterm.js 前端组件 | （可选）配置 Nerd Font fontFamily |

---

> **验证命令**：启动容器后执行以下命令，确认两项问题均已修复：
> ```bash
> # 检查字体
> echo $PS1
> # 应显示无乱码的提示符
> 
> # 检查挂载
> df -h | grep -E "workspace|/data/omichub"
> touch /home/omichub/workspace/test_$(date +%s).txt
> ls -la /home/omichub/workspace/
> ```

---

*文档生成时间: 2026-07-07*
