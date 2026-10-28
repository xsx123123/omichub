# 🧬 OmicHub 前端优化实施文档

> **版本：** v1.0  
> **日期：** 2026-07-04  
> **范围：** 分析中心卡片 + 系统设置页面  
> **目标：** 提升视觉辨识度、增强交互感、修复布局留白、新增平台级 TOTP 控制

---

## 一、分析中心 — 流程卡片优化

### 1.1 Emoji 图标（YAML 直接定义）

**核心方案：** 不再使用前端映射表，直接在每个分析流程的 YAML `meta.icon` 字段填写 Emoji。前端优先读取该字段，无值时兜底。

**YAML 示例：**

```yaml
meta:
  id: atac_seq
  name: "ATAC-seq 染色质可及性分析"
  category: epigenomics
  version: "0.0.5"
  icon: "🧪"          # ← 直接写 emoji，一目了然，流程作者自治
  docs_url: "https://github.com/xsx123123/ATACFlow"
  author: "OmicsHub Team"
  tags: ["atacseq", "chromatin-accessibility", "Bowtie2", "Chromap", "MACS2", "TOBIAS", "ATACFlow"]
```

**推荐 Emoji 参考表：**

| 流程类型 | 推荐 Emoji | 说明 |
|---------|-----------|------|
| RNA-seq | 🧬 | 双螺旋，经典分子生物学 |
| ATAC-seq | 🧪 | 试管/实验，表观遗传 |
| scRNA-seq | 🔬 | 单细胞显微镜 |
| ChIP-seq | 🧲 | 磁珠/抗体富集 |
| WGS / WES | 🗂️ | 全基因组档案 |
| 基因组浏览器 | 🌐 | 浏览器/地球 |
| Proteomics | 🧫 | 培养皿 |
| Metabolomics | ⚗️ | 蒸馏/代谢 |
| 通用/其他 | ⚙️ | 默认齿轮 |

**前端读取逻辑：**

```typescript
// utils/flowIcon.ts
const FALLBACK_MAP: Record<string, string> = {
  rna: '🧬',
  atac: '🧪',
  scrna: '🔬',
  chip: '🧲',
  wgs: '🗂️',
  wes: '🗂️',
  jbrowse: '🌐',
  proteomics: '🧫',
  metabolomics: '⚗️',
  default: '⚙️',
};

export const getFlowEmoji = (flow: Flow): string => {
  // 优先使用 YAML 中直接配置的 emoji
  if (flow.meta?.icon && flow.meta.icon.length > 0) {
    return flow.meta.icon;
  }
  // 兜底：按 id 或 category 映射
  return FALLBACK_MAP[flow.meta?.id] 
    || FALLBACK_MAP[flow.meta?.category] 
    || FALLBACK_MAP.default;
};
```

**组件样式：**

```jsx
// 根据 category 动态背景色
const CATEGORY_BG_MAP: Record<string, string> = {
  transcriptomics: 'bg-blue-50',
  epigenomics:     'bg-purple-50',
  genomics:        'bg-green-50',
  'single-cell':   'bg-pink-50',
  visualization:   'bg-indigo-50',
  proteomics:      'bg-amber-50',
  metabolomics:    'bg-teal-50',
  default:         'bg-gray-50',
};

<div className={`w-12 h-12 rounded-xl ${bgClass} flex items-center justify-center text-2xl select-none`}>
  {iconEmoji}
</div>
```

---

### 1.2 GitHub 源码图标 + 悬停动画

**数据来源：** 从 YAML `meta.docs_url` 读取，仅当包含 `github.com` 时渲染。

**组件代码：**

```jsx
import { Github } from 'lucide-react'; // 或内联 SVG

const AnalysisCard = ({ flow }) => {
  const iconEmoji = getFlowEmoji(flow);
  const docsUrl   = flow.meta?.docs_url;
  const isGithub  = docsUrl?.includes('github.com');
  const bgClass   = CATEGORY_BG_MAP[flow.meta?.category] || CATEGORY_BG_MAP.default;

  return (
    <div className="group relative bg-white rounded-2xl p-6 border border-gray-100 
                    hover:shadow-lg transition-all duration-300 cursor-pointer">

      {/* Header: Emoji + Title + GitHub */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={`w-12 h-12 rounded-xl ${bgClass} flex items-center justify-center text-2xl`}>
            {iconEmoji}
          </div>
          <h3 className="text-lg font-semibold text-gray-900 leading-tight">
            {flow.meta.name}
          </h3>
        </div>

        {isGithub && (
          <a
            href={docsUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="github-icon mt-1"
            title="查看源码"
            onClick={(e) => e.stopPropagation()} // 阻止冒泡，不触发卡片点击
          >
            <Github className="w-5 h-5" />
          </a>
        )}
      </div>

      {/* 描述 */}
      <p className="text-sm text-gray-500 mb-4 line-clamp-2">
        {flow.meta.description}
      </p>

      {/* Tags + Version */}
      <div className="flex items-center justify-between">
        <div className="flex flex-wrap gap-2">
          {flow.meta.tags.slice(0, 5).map(tag => (
            <span key={tag} className="px-2.5 py-1 bg-blue-50 text-blue-600 
                                       rounded-full text-xs font-medium">
              {tag}
            </span>
          ))}
        </div>
        <span className="text-xs text-gray-400 font-mono ml-2">
          v{flow.meta.version}
        </span>
      </div>
    </div>
  );
};
```

**CSS 动画（Tailwind + 自定义 Keyframes）：**

```css
/* styles/globals.css */

@keyframes github-wiggle {
  0%, 100% { transform: rotate(0deg) scale(1); }
  20%  { transform: rotate(-15deg) scale(1.2); }
  40%  { transform: rotate(10deg) scale(1.2); }
  60%  { transform: rotate(-8deg) scale(1.15); }
  80%  { transform: rotate(4deg) scale(1.1); }
}

.github-icon {
  color: #9ca3af;      /* gray-400 */
  opacity: 0.6;
  transition: all 0.2s ease;
  display: inline-flex;
}

.github-icon:hover {
  color: #24292f;      /* GitHub 黑 */
  opacity: 1;
  animation: github-wiggle 0.5s ease-in-out;
}

/* 渐变 Banner 中的 GitHub 图标（白色版本） */
.banner-github-icon {
  color: rgba(255, 255, 255, 0.6);
  opacity: 0.8;
  transition: all 0.2s ease;
}

.banner-github-icon:hover {
  color: white;
  opacity: 1;
  animation: github-wiggle 0.5s ease-in-out;
}
```

---

### 1.3 推荐流程 Banner 同步

图3中的蓝色渐变 Banner 卡片同步应用：

```jsx
<div className="relative bg-gradient-to-r from-blue-600 to-purple-600 rounded-2xl p-8 text-white">
  <div className="flex items-start justify-between">
    <div className="flex items-center gap-4">
      <span className="text-4xl select-none">🧬</span>
      <div>
        <h2 className="text-2xl font-bold">RNA-seq 差异表达分析</h2>
        <p className="text-blue-100 mt-1 text-sm">
          基于 RNAFlow 流程（STAR + RSEM + DESeq2）...
        </p>
      </div>
    </div>
    {isGithub && (
      <a href={docsUrl} target="_blank" className="banner-github-icon">
        <Github className="w-6 h-6" />
      </a>
    )}
  </div>
</div>
```

---

## 二、系统设置 — 页面布局与功能优化

### 2.1 平台设置新增「二次验证（TOTP）」全局控制

**修改位置：** `PlatformSettings` 组件 / 平台设置 Tab

**新增配置项：**

```typescript
interface PlatformConfig {
  allow_registration: boolean;  // 已有
  totp_policy: 'off' | 'optional' | 'required';  // 新增
}
```

**UI 实现（分段控制器）：**

```jsx
const TOTPPolicyControl = ({ value, onChange }) => {
  const options = [
    { key: 'off',       label: '关闭', desc: '全平台禁用 TOTP' },
    { key: 'optional',  label: '可选', desc: '用户自行决定是否开启' },
    { key: 'required',  label: '强制', desc: '所有用户必须开启 TOTP' },
  ];

  return (
    <div className="bg-white rounded-2xl p-6 border border-gray-100">
      <div className="flex items-center gap-3 mb-4">
        <span className="text-xl">🔐</span>
        <h3 className="text-lg font-semibold text-gray-900">二次验证（TOTP）</h3>
      </div>

      <div className="flex flex-col gap-3">
        <div className="inline-flex bg-gray-100 rounded-lg p-1 w-fit">
          {options.map((opt) => (
            <button
              key={opt.key}
              onClick={() => onChange(opt.key)}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                value === opt.key
                  ? 'bg-white text-blue-600 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <p className="text-sm text-gray-500">
          {options.find(o => o.key === value)?.desc}
        </p>
      </div>
    </div>
  );
};
```

**保存接口：**

```typescript
// PATCH /api/admin/platform-config
{
  "allow_registration": true,
  "totp_policy": "optional"
}
```

---

### 2.2 用户端「安全设置」联动

**修改位置：** `SecuritySettings` 组件 / 安全设置 Tab

根据平台全局配置动态展示 TOTP 区域：

```jsx
const SecuritySettings = () => {
  const { platformConfig } = usePlatformConfig();
  const totpPolicy = platformConfig?.totp_policy || 'optional';
  const userTOTP = useUserTOTP(); // 用户个人 TOTP 状态

  return (
    <div className="space-y-6">
      {/* 修改密码 — 保持原样 */}
      <PasswordChangeCard />

      {/* TOTP 卡片 — 根据平台配置动态渲染 */}
      {totpPolicy === 'off' ? (
        <div className="bg-gray-50 rounded-2xl p-6 border border-gray-100">
          <div className="flex items-center gap-3">
            <span className="text-xl opacity-50">🔐</span>
            <h3 className="text-lg font-semibold text-gray-400">二次验证（TOTP）</h3>
          </div>
          <p className="mt-3 text-sm text-gray-400">
            平台管理员已关闭二次验证功能，如有需要请联系管理员。
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-2xl p-6 border border-gray-100">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <span className="text-xl">🛡️</span>
              <h3 className="text-lg font-semibold text-gray-900">二次验证（TOTP）</h3>
              <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                userTOTP.enabled 
                  ? 'bg-green-50 text-green-600' 
                  : 'bg-gray-100 text-gray-500'
              }`}>
                {userTOTP.enabled ? '已开启' : '未开启'}
              </span>
            </div>
          </div>

          {/* 强制开启提示 */}
          {totpPolicy === 'required' && !userTOTP.enabled && (
            <div className="mb-4 p-3 bg-orange-50 border border-orange-200 rounded-lg">
              <p className="text-sm text-orange-700">
                ⚠️ 平台要求所有用户必须开启二次验证，请尽快完成绑定。
              </p>
            </div>
          )}

          <p className="text-sm text-gray-500 mb-4">
            绑定 Google Authenticator、Microsoft Authenticator 等 TOTP 验证器后，
            登录时将要求输入 6 位动态验证码，提升账号安全性。
          </p>

          <button
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              userTOTP.enabled
                ? 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                : totpPolicy === 'required'
                  ? 'bg-orange-500 text-white hover:bg-orange-600'
                  : 'bg-blue-600 text-white hover:bg-blue-700'
            }`}
          >
            {userTOTP.enabled ? '关闭二次验证' : '开启二次验证'}
          </button>
        </div>
      )}
    </div>
  );
};
```

---

### 2.3 布局宽度优化（解决左右留白）

**当前问题：** 内容区最大宽度约 768px（`max-w-3xl`），在宽屏下两侧留白过大。

**优化方案：**

```jsx
// SystemSettings.tsx
<div className="min-h-screen bg-gray-50">
  {/* 页面标题 */}
  <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-8 pb-4">
    <h1 className="text-2xl font-bold text-gray-900">系统设置</h1>
  </div>

  {/* Tab 导航 */}
  <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <SettingsTabs />
  </div>

  {/* 内容区 — 关键修改：放宽宽度限制 */}
  <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
    <div className="space-y-6">
      {activeTab === 'profile'    && <ProfileSettings />}
      {activeTab === 'security'   && <SecuritySettings />}
      {activeTab === 'preference' && <PreferenceSettings />}
      {activeTab === 'platform'   && <PlatformSettings />}
    </div>
  </div>
</div>
```

**响应式断点表：**

| 屏幕宽度 | 内容区 class | 实际最大宽度 | 卡片 padding |
|---------|-------------|-----------|-------------|
| < 640px | `w-full px-4` | 100% - 32px | `p-5` |
| 640px - 1024px | `max-w-3xl mx-auto px-6` | 768px | `p-6` |
| 1024px - 1440px | `max-w-5xl mx-auto px-8` | 1024px | `p-8` |
| > 1440px | `max-w-6xl mx-auto px-10` | 1152px | `p-8` |

**卡片统一样式：**

```css
.settings-card {
  background: white;
  border-radius: 1rem;
  border: 1px solid #f3f4f6;
  padding: 2rem; /* 32px */
}

@media (min-width: 1440px) {
  .settings-card {
    padding: 2.5rem; /* 40px */
  }
}
```

---

### 2.4 平台设置两列布局（进阶）

若配置项增多，采用响应式两列网格：

```jsx
<div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
  {/* 左列：开放注册 */}
  <div className="settings-card">
    <div className="flex items-center gap-3 mb-4">
      <span className="text-xl">🌐</span>
      <h3 className="text-lg font-semibold">开放用户注册</h3>
    </div>
    <p className="text-sm text-gray-500 mb-4">
      关闭后新用户将无法自助注册，需由管理员创建账号
    </p>
    <Toggle checked={allowRegistration} onChange={setAllowRegistration} />
  </div>

  {/* 右列：TOTP 策略 */}
  <div className="settings-card">
    <TOTPPolicyControl value={totpPolicy} onChange={setTOTPPolicy} />
  </div>
</div>
```

---

## 三、数据接口变更

### 3.1 后端新增/修改接口

| 接口 | 方法 | 权限 | 说明 |
|------|------|------|------|
| `GET /api/platform/config` | GET | 公开 | 返回平台全局配置（含 `totp_policy`） |
| `PATCH /api/admin/platform-config` | PATCH | 管理员 | 修改平台配置 |
| `GET /api/flows` | GET | 用户 | 已有，确保返回 `meta.icon` 和 `meta.docs_url` |

### 3.2 响应格式示例

```json
// GET /api/platform/config
{
  "allow_registration": true,
  "totp_policy": "optional",
  "platform_name": "OmicHub",
  "version": "1.0.0"
}

// GET /api/flows（单个流程）
{
  "id": "atac_seq",
  "meta": {
    "name": "ATAC-seq 染色质可及性分析",
    "icon": "🧪",
    "category": "epigenomics",
    "version": "0.0.5",
    "docs_url": "https://github.com/xsx123123/ATACFlow",
    "tags": ["atacseq", "chromatin-accessibility", "Bowtie2", "Chromap", "MACS2", "TOBIAS", "ATACFlow"]
  }
}
```

---

## 四、样式变量汇总

```css
/* styles/globals.css */

/* ========== GitHub 图标动画 ========== */
@keyframes github-wiggle {
  0%, 100% { transform: rotate(0deg) scale(1); }
  20%  { transform: rotate(-15deg) scale(1.2); }
  40%  { transform: rotate(10deg) scale(1.2); }
  60%  { transform: rotate(-8deg) scale(1.15); }
  80%  { transform: rotate(4deg) scale(1.1); }
}

.github-icon {
  color: #9ca3af;
  opacity: 0.6;
  transition: all 0.2s ease;
  display: inline-flex;
}

.github-icon:hover {
  color: #24292f;
  opacity: 1;
  animation: github-wiggle 0.5s ease-in-out;
}

/* 渐变 Banner 中的 GitHub 图标 */
.banner-github-icon {
  color: rgba(255, 255, 255, 0.6);
  opacity: 0.8;
  transition: all 0.2s ease;
}

.banner-github-icon:hover {
  color: white;
  opacity: 1;
  animation: github-wiggle 0.5s ease-in-out;
}

/* ========== 设置卡片 ========== */
.settings-card {
  background: white;
  border-radius: 1rem;
  border: 1px solid #f3f4f6;
  padding: 2rem;
}

@media (min-width: 1440px) {
  .settings-card {
    padding: 2.5rem;
  }
}

/* ========== 状态标签 ========== */
.tag-inactive {
  background-color: #f3f4f6;
  color: #6b7280;
}

.tag-active {
  background-color: #f0fdf4;
  color: #16a34a;
}

.tag-required {
  background-color: #fff7ed;
  color: #ea580c;
}
```

---

## 五、交付检查清单

### 分析中心
- [ ] YAML `meta.icon` 字段直接填写 Emoji（如 `icon: "🧪"`）
- [ ] 前端优先读取 `flow.meta.icon`，无值时按 `id/category` fallback
- [ ] Emoji 容器 `w-12 h-12 rounded-xl`，字体 `text-2xl`，背景色按 `category` 动态
- [ ] GitHub 图标从 `meta.docs_url` 读取，非 GitHub 链接不显示
- [ ] GitHub 图标悬停 wiggle 动画（0.5s），点击新标签页打开，不触发卡片点击
- [ ] 推荐流程 Banner 中 Emoji 放大至 `text-4xl`，GitHub 图标白色
- [ ] 移动端 Emoji 和动画正常降级

### 系统设置
- [ ] 平台设置新增 TOTP 分段控制器（关闭 / 可选 / 强制）
- [ ] `PATCH /api/admin/platform-config` 支持保存 `totp_policy`
- [ ] 用户端安全设置根据 `totp_policy` 动态展示：
  - `off`：隐藏或显示禁用提示
  - `optional`：保持当前逻辑
  - `required`：显示橙色强制提示横幅，按钮变橙色
- [ ] 内容区宽度从 `max-w-3xl` 放宽至 `max-w-5xl`（1024px）
- [ ] 输入框在宽屏下 `width: 100%`，不再右侧留空
- [ ] 卡片 padding 统一为 `32px`（`p-8`）
- [ ] 响应式适配：`< 1024px` 单列，`< 640px` padding 缩小
- [ ] 状态标签（未开启/已开启）颜色对比度优化

---

*文档完毕，可直接交付开发。*
