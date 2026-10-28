# OmicHub 节日彩蛋系统 — 调研报告

> 调研日期: 2026-07-09
> 调研目标: 为 OmicHub 平台设计节日彩蛋系统（弹窗/动画/额度赠送/管理配置）
> 平台主题: "We are made of star-stuff"（宇宙星空主题）

---

## 目录

1. [其他平台节日彩蛋案例分析](#一其他平台节日彩蛋案例分析)
2. [前端第三方库调研](#二前端第三方库调研)
3. [中国节假日数据源与配置方案](#三中国节假日数据源与配置方案)
4. [推荐技术架构方案](#四推荐技术架构方案)
5. [YAML配置详细设计](#五yaml配置详细设计)
6. [管理后台设计](#六管理后台设计)
7. [额度赠送系统设计](#七额度赠送系统设计)
8. [与平台主题相符的动画设计建议](#八与平台主题相符的动画设计建议)
9. [实施路线图](#九实施路线图)

---

## 一、其他平台节日彩蛋案例分析

### 1.1 Google Doodle — 全球最成熟的节日彩蛋系统

| 维度 | 详情 |
|------|------|
| **技术演进** | CSS Sprite → CSS3动画 → HTML5 Canvas → 交互游戏 |
| **实现特点** | 所有 Doodle 归档保存在 [doodles.google.com/archive](https://doodles.google.com/archive) |
| **技术选型** | 根据创意需求灵活选择：纯CSS动画到复杂Canvas游戏 |
| **对OmicHub的启示** | 技术选型应随节日重要程度分级：弹窗 → 动画 → 全屏特效 |

### 1.2 GitHub — 低调优雅的彩蛋设计

| 维度 | 详情 |
|------|------|
| **404视差滚动** | 鼠标移动时前景/背景以不同速度移动，创造空间层次感 |
| **Octocat变体** | 圣诞帽版、万圣节版章鱼猫吉祥物 |
| **贡献日历特效** | 万圣节、圣诞节贡献图显示特殊颜色主题 |
| **对OmicHub的启示** | 彩蛋应不强制、不突兀；与品牌IP（星际猫咪）深度结合 |

### 1.3 Ant Design 圣诞彩蛋事件 — 反面教材

| 维度 | 详情 |
|------|------|
| **事件** | 2018年圣诞节，所有 `<Button>` 自动添加"积雪"效果 |
| **后果** | 企业内网、政府网站、中东国家网站出现不合时宜的圣诞元素 |
| **教训** | 节日彩蛋必须**可选、默认关闭**，不应侵入核心代码 |
| **对OmicHub的启示** | 彩蛋必须在展示层实现，提供关闭开关，考虑文化差异 |

### 1.4 Figma 愚人节彩蛋

| 维度 | 详情 |
|------|------|
| **触发方式** | Shift+S 创建 Section 后点击游戏手柄图标 |
| **内容** | 内嵌贪吃蛇游戏 |
| **对OmicHub的启示** | 彩蛋可与产品功能自然结合，仅在特定时间窗口可触发 |

### 1.5 SHOPLINE 弹窗推广系统 — 最完整的弹窗方案

| 维度 | 详情 |
|------|------|
| **弹窗类型** | 8种类型：订阅、折扣券、节日、挽留、转盘、免运费、商品、营销 |
| **推送策略** | 时间延迟、页面滚动深度、退出意图触发 |
| **人群定向** | 登录状态、购买状态、IP国家/地区 |
| **生效时间** | 可设置开始/结束日期，支持"永不过期" |
| **对OmicHub的启示** | 弹窗应支持：时间窗口控制、展示次数限制、可关闭、可跳转 |

### 1.6 阿里云百炼 — 额度赠送弹窗

| 维度 | 详情 |
|------|------|
| **赠送内容** | 新用户注册送 1000 万免费额度（半年有效期） |
| **弹窗结构** | "确认开通"按钮 → 创建 API-KEY 引导 |
| **对OmicHub的启示** | 额度赠送弹窗应清晰展示数值、有效期、行动引导 |

### 1.7 国内电商平台 — 节日弹窗UI设计规律

| 设计元素 | 规范 |
|----------|------|
| **配色** | 红/金/橙色传递喜庆感 |
| **金额展示** | 大字号、高亮颜色 |
| **有效期** | 明确标注，增加紧迫感 |
| **按钮** | 双按钮设计：「立即领取」+「了解详情」 |
| **动效** | 入场 scaleIn + 庆祝撒花 |
| **关闭** | 右上角 X + 遮罩点击 + ESC 键 |

### 1.8 关键结论与最佳实践

| 原则 | 优先级 | 说明 |
|------|--------|------|
| **可选性** | P0 | 彩蛋必须可选，默认关闭或提供关闭方式 |
| **文化敏感** | P0 | 考虑用户文化背景，避免强制展示特定节日 |
| **不干扰业务** | P0 | 不影响核心功能 |
| **时间窗口** | P0 | 明确生效时间，过期自动关闭 |
| **频率控制** | P1 | 同一用户不反复看到同一弹窗 |
| **性能友好** | P1 | 提供减少动效选项 |

---

## 二、前端第三方库调研

### 2.1 推荐库组合（按优先级）

| 优先级 | 库名 | npm包名 | Stars | gzip体积 | 用途 |
|--------|------|---------|-------|----------|------|
| **P0** | **Motion** | `motion` | 32.7k | ~25KB | 弹窗/组件动画 |
| **P0** | **Sonner** | `sonner` | 12.6k | ~10KB | Toast通知（节日提醒） |
| **P0** | **canvas-confetti** | `canvas-confetti` | 12.6k | ~3KB | 庆祝爆炸效果 |
| **P1** | **tsParticles** | `@tsparticles/react` | 8.9k | ~15-40KB | 粒子背景（星星/烟花/雪花） |
| **P1** | **MagicUI** | CLI安装 | 21.5k | 按需 | 流星/粒子/闪光文字 |
| **P2** | **Nebula** | `@flodlc/nebula` | 67 | ~1KB | 宇宙星云背景 |
| **P2** | **Fireworks** | `@fireworks-js/react` | 1.5k | ~3KB | 烟花效果（新年/春节） |
| **P2** | **Snowfall** | `react-snowfall` | 601 | ~5KB | 雪花效果（圣诞/冬至） |

### 2.2 各库详细介绍

#### canvas-confetti（庆祝特效首选）

```bash
npm install canvas-confetti
```

- **零依赖、3KB、12.6k Stars**，最经典的五彩纸屑效果
- 支持自定义形状、颜色、发射角度、物理效果
- `pointer-events: none` 不干扰页面交互
- 支持 `prefers-reduced-motion` 无障碍访问

```typescript
// 基础使用
import confetti from 'canvas-confetti';
confetti({ particleCount: 100, spread: 70, origin: { y: 0.6 } });

// 烟花效果（双发射点）
const end = Date.now() + 15 * 1000;
const interval = setInterval(() => {
  if (Date.now() > end) return clearInterval(interval);
  confetti({ origin: { x: Math.random() * 0.3, y: Math.random() - 0.2 } });
  confetti({ origin: { x: 0.7 + Math.random() * 0.3, y: Math.random() - 0.2 } });
}, 250);
```

#### Motion / Framer Motion（弹窗动画首选）

```bash
npm install motion
```

- **React生态最强动画库**，32.7k Stars
- 声明式API，弹簧物理动画，120fps性能
- `AnimatePresence` 实现流畅的入场/出场动画

```tsx
import { motion, AnimatePresence } from 'motion/react';

<AnimatePresence>
  {isOpen && (
    <motion.div
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.8 }}
      transition={{ type: 'spring', stiffness: 500, damping: 30 }}
    >
      {/* 弹窗内容 */}
    </motion.div>
  )}
</AnimatePresence>
```

#### tsParticles（粒子效果首选）

```bash
npm install @tsparticles/react @tsparticles/slim @tsparticles/engine
```

- **最全面的粒子系统**，内置丰富预设
- 与星空相关的预设：`stars`（星星）、`fireworks`（烟花）、`snow`（雪花）、`firefly`（萤火虫）、`hyperspace`（超空间）
- 支持鼠标交互

```tsx
import Particles, { init } from '@tsparticles/react';
import { loadSlim } from '@tsparticles/slim';

init(async (engine) => { await loadSlim(engine); });

// 星星背景
<Particles options={{
  particles: {
    number: { value: 200 },
    color: { value: '#ffffff' },
    size: { value: { min: 1, max: 3 } },
    move: { enable: true, speed: 0.5 },
    opacity: { value: { min: 0.1, max: 1 } },
  },
}} />
```

#### @flodlc/nebula（宇宙主题完美匹配）

```bash
npm install @flodlc/nebula
```

- **仅1KB压缩体积**，专为宇宙主题设计
- 包含：星星、星云、彗星、行星、太阳
- SSR兼容
- 与 "We are made of star-stuff" 主题**高度契合**

```tsx
import { ReactNebula } from '@flodlc/nebula';

<ReactNebula config={{
  starsCount: 250,
  starsRotationSpeed: 3,
  nebulasIntensity: 8,
  nebulasColors: ['rgb(5,63,157)', 'rgb(42,112,25)', 'rgb(182,41,44)'],
  cometFrequence: 3,
}} />
```

#### MagicUI（流星/粒子效果）

```bash
npx magicui-cli add particles meteors confetti sparkle
```

- 21.5k Stars，shadcn/ui生态兼容
- 可用组件：`particles`（粒子）、`meteors`（流星）、`sparkles-text`（闪光文字）、`neon-gradient-card`（霓虹卡片）

### 2.3 最简快速上线方案

```bash
npm install sonner canvas-confetti motion
```

总计约 **40KB**，功能完整，覆盖弹窗、通知、庆祝效果。

---

## 三、中国节假日数据源与配置方案

### 3.1 推荐npm包组合

| 用途 | 推荐包 | 理由 |
|------|--------|------|
| **农历转换 + 24节气 + 自定义节日** | `lunisolar` | gzip仅11.5KB，TypeScript原生，Markers系统支持自定义节日 |
| **法定假日 + 调休判断** | `chinese-days` | 数据AI自动更新，覆盖2004-2026年 |

### 3.2 lunisolar 核心功能

```typescript
import lunisolar from 'lunisolar';
import { marker } from 'lunisolar/plugins/marker';
lunisolar.extend(marker);

// 获取当日节气
const d = lunisolar('2026-02-17');
console.log(d.solarTerm?.toString()); // "雨水" 或 null

// 查询某年立春日期
const solarTerm = lunisolar.SolarTerm;
const liChun = solarTerm.findDate(2026, 0);
console.log(liChun); // [2026, 2, 4]

// 农历转公历（春节）
const spring = lunisolar.fromLunar({ year: 2026, month: 1, day: 1 });
console.log(spring.format('YYYY-MM-DD')); // "2026-02-17"
```

### 3.3 chinese-days 核心功能

```typescript
import { isHoliday, isWorkday, getFestival } from 'chinese-days';

isHoliday('2026-01-01');     // true (元旦)
isWorkday('2026-02-16');     // true (春节调休上班)
getFestival('2026-02-17');   // "春节" 或 null
```

### 3.4 在线JSON数据（CDN直接访问）

```
https://cdn.jsdelivr.net/npm/chinese-days/dist/chinese-days.json
https://cdn.jsdelivr.net/gh/NateScarlet/holiday-cn@master/2026.json
```

---

## 四、推荐技术架构方案

### 4.1 整体架构

```
┌──────────────────────────────────────────────────────────────┐
│                        前端层 (React)                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐ │
│  │ useFest  │  │ Festival │  │ Animator │  │ ClaimButton  │ │
│  │ ivalHook│  │ Popup    │  │ Component│  │ Component    │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘ │
└───────┼─────────────┼─────────────┼───────────────┼─────────┘
        │             │             │               │
        │ GET /api/   │             │               │ POST /api/
        │ festival/   │             │               │ quota/
        │ today       │             │               │ claim
        ▼             ▼             ▼               ▼
┌──────────────────────────────────────────────────────────────┐
│                      API 网关层                               │
└──────────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────────────────┐
│                      服务层                                   │
│  ┌──────────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ Festival Service │  │ Popup Service│  │Quota Service │   │
│  │ - 节日检测        │  │ - 弹窗管理   │  │ - 额度发放   │   │
│  │ - 农历计算        │  │ - 展示策略   │  │ - 防重复     │   │
│  │ - 配置合并        │  │ - A/B测试   │  │ - 额度流水   │   │
│  └────────┬─────────┘  └──────────────┘  └──────┬───────┘   │
└───────────┼─────────────────────────────────────┼───────────┘
            │                                     │
            ▼                                     ▼
┌──────────────────────┐              ┌──────────────────────┐
│   Config Store       │              │   Data Store         │
│ festival-config.yaml │              │ ┌────────────────┐   │
│ admin-override.yaml  │              │ │  quota_records │   │
│ Redis (缓存+锁)      │              │ │  user_quotas   │   │
│ lunisolar (农历)     │              │ └────────────────┘   │
└──────────────────────┘              └──────────────────────┘
```

### 4.2 核心API设计

```typescript
// GET /api/festival/today
interface FestivalTodayResponse {
  hasFestival: boolean;
  festival: {
    id: string;
    name: string;
    type: 'solar' | 'lunar' | 'solar_term' | 'custom';
    date: string;
    popup?: PopupConfig;
    quotaBonus?: QuotaBonusConfig;
    animation?: AnimationConfig;
  } | null;
}

// POST /api/quota/claim
interface ClaimRequest {
  festivalId: string;
  userId: string;
}

interface ClaimResponse {
  success: boolean;
  amount?: number;
  balance?: number;
  message: string;
}
```

---

## 五、YAML配置详细设计

### 5.1 配置文件结构

```yaml
# ============================================================
# OmicHub 节日彩蛋系统配置文件
# 版本: 1.0
# 说明: 管理员可通过此文件配置节日彩蛋、弹窗、额度赠送
# 路径: /config/festival-config.yaml
# ============================================================

version: "1.0"

# ── 全局配置 ──
global:
  # 系统总开关（紧急情况下可一键关闭）
  enabled: true
  
  # 默认生效时间范围
  defaultActiveWindow:
    start: "00:00:00"
    end: "23:59:59"
  
  # 弹窗全局默认配置
  popupDefaults:
    showOncePerUser: true        # 每个用户只展示一次
    showMaxTimes: 3              # 最多展示次数
    dismissible: true            # 是否可关闭
    backdropClose: true          # 点击遮罩关闭
    escClose: true               # ESC键关闭
  
  # 额度赠送全局限制
  quotaDefaults:
    expiryDays: 30               # 赠送额度有效期（天）

# ── 节日列表 ──
festivals:
  # ═══════════════════════════════════════════════════════════
  # 农历节日
  # ═══════════════════════════════════════════════════════════
  - id: spring_festival
    name: "春节"
    nameEn: "Spring Festival"
    category: "traditional"
    calendarType: "lunar"
    lunarDate: { month: 1, day: 1 }
    activeRange: { offsetDays: -1, durationDays: 7 }
    popup:
      enabled: true
      title: "🎊 新春大吉"
      content: |
        在这辞旧迎新的时刻，愿星光为你指引前路。
        送你 {{bonusAmount}} 额度大礼包！
      primaryButton:
        text: "立即领取 ✨"
        action: "claim_quota"
      secondaryButton:
        text: "了解更多"
        action: "navigate"
        link: "/about"
      animation:
        enabled: true
        type: "fireworks"
        duration: 15
    quotaBonus:
      enabled: true
      amount: 1000
      unit: "token"
      description: "春节特别赠送"
    priority: 100

  - id: lantern_festival
    name: "元宵节"
    nameEn: "Lantern Festival"
    category: "traditional"
    calendarType: "lunar"
    lunarDate: { month: 1, day: 15 }
    popup:
      enabled: true
      title: "🏮 元宵喜乐"
      content: "花灯如昼，月圆人团圆。送你 {{bonusAmount}} 额度！"
      animation:
        enabled: true
        type: "lantern"
        duration: 15
    quotaBonus:
      enabled: true
      amount: 200
      unit: "token"
    priority: 80

  - id: dragon_boat
    name: "端午节"
    nameEn: "Dragon Boat Festival"
    category: "traditional"
    calendarType: "lunar"
    lunarDate: { month: 5, day: 5 }
    popup:
      enabled: true
      title: "🐲 端午安康"
      content: "粽叶飘香，龙舟竞渡。送你 {{bonusAmount}} 额度！"
      animation:
        enabled: true
        type: "confetti"
        duration: 8
    quotaBonus:
      enabled: true
      amount: 300
      unit: "token"
    priority: 80

  - id: qixi
    name: "七夕节"
    nameEn: "Qixi Festival"
    category: "traditional"
    calendarType: "lunar"
    lunarDate: { month: 7, day: 7 }
    popup:
      enabled: true
      title: "💕 七夕快乐"
      content: "星河为证，爱意绵长。在浩瀚宇宙中相遇，是千万分之一的奇迹。送你 {{bonusAmount}} 额度！"
      animation:
        enabled: true
        type: "star_heart"
        duration: 12
    quotaBonus:
      enabled: true
      amount: 520
      unit: "token"
      description: "七夕限定额度"
    priority: 70

  - id: mid_autumn
    name: "中秋节"
    nameEn: "Mid-Autumn Festival"
    category: "traditional"
    calendarType: "lunar"
    lunarDate: { month: 8, day: 15 }
    popup:
      enabled: true
      title: "🌕 中秋团圆"
      content: "月圆人团圆，中秋送福。每一轮明月，都是宇宙送给我们的礼物。送你 {{bonusAmount}} 额度！"
      animation:
        enabled: true
        type: "moon_glow"
        duration: 20
    quotaBonus:
      enabled: true
      amount: 500
      unit: "token"
    priority: 90

  - id: double_ninth
    name: "重阳节"
    nameEn: "Double Ninth Festival"
    category: "traditional"
    calendarType: "lunar"
    lunarDate: { month: 9, day: 9 }
    popup:
      enabled: true
      title: "🍂 重阳登高"
      content: "九九重阳，健康长寿。送你 {{bonusAmount}} 额度！"
    quotaBonus:
      enabled: true
      amount: 200
      unit: "token"
    priority: 60

  # ═══════════════════════════════════════════════════════════
  # 公历节日
  # ═══════════════════════════════════════════════════════════
  - id: new_year
    name: "元旦"
    nameEn: "New Year's Day"
    category: "modern"
    calendarType: "solar"
    solarDate: { month: 1, day: 1 }
    popup:
      enabled: true
      title: "🎉 新年快乐"
      content: "新的一年，愿你在星辰大海中探索无限可能。送你 {{bonusAmount}} 额度开启新一年！"
      animation:
        enabled: true
        type: "confetti"
        duration: 15
    quotaBonus:
      enabled: true
      amount: 500
      unit: "token"
    priority: 90

  - id: labor_day
    name: "劳动节"
    nameEn: "Labor Day"
    category: "modern"
    calendarType: "solar"
    solarDate: { month: 5, day: 1 }
    popup:
      enabled: true
      title: "🛠️ 劳动节快乐"
      content: "劳动最光荣！送你 {{bonusAmount}} 额度！"
    quotaBonus:
      enabled: true
      amount: 300
      unit: "token"
    priority: 70

  - id: national_day
    name: "国庆节"
    nameEn: "National Day"
    category: "modern"
    calendarType: "solar"
    solarDate: { month: 10, day: 1 }
    activeRange: { offsetDays: 0, durationDays: 7 }
    popup:
      enabled: true
      title: "🇨🇳 国庆快乐"
      content: "盛世华诞，举国同庆。送你 {{bonusAmount}} 额度！"
      animation:
        enabled: true
        type: "fireworks"
        duration: 30
    quotaBonus:
      enabled: true
      amount: 1000
      unit: "token"
      description: "国庆黄金周福利"
    priority: 100

  - id: valentine
    name: "情人节"
    nameEn: "Valentine's Day"
    category: "modern"
    calendarType: "solar"
    solarDate: { month: 2, day: 14 }
    popup:
      enabled: true
      title: "❤️ 情人节快乐"
      content: "爱与被爱，都是幸福。送你 {{bonusAmount}} 额度！"
      animation:
        enabled: true
        type: "heart"
        duration: 15
    quotaBonus:
      enabled: true
      amount: 520
      unit: "token"
    priority: 70

  - id: christmas
    name: "圣诞节"
    nameEn: "Christmas"
    category: "modern"
    calendarType: "solar"
    solarDate: { month: 12, day: 25 }
    popup:
      enabled: true
      title: "🎄 圣诞快乐"
      content: "Merry Christmas！送你 {{bonusAmount}} 额度！"
      animation:
        enabled: true
        type: "snow"
        duration: 20
    quotaBonus:
      enabled: true
      amount: 300
      unit: "token"
    priority: 60

  # ═══════════════════════════════════════════════════════════
  # 24节气（精选）
  # ═══════════════════════════════════════════════════════════
  - id: li_chun
    name: "立春"
    category: "solar_term"
    calendarType: "solar_term"
    solarTerm: { name: "立春", index: 0 }
    popup:
      enabled: true
      title: "🌱 立春"
      content: "春回大地，万物复苏。宇宙也开始新一轮的生命循环。送你 {{bonusAmount}} 额度！"
      animation:
        enabled: true
        type: "petal"
        duration: 10
    quotaBonus:
      enabled: true
      amount: 200
      unit: "token"
    priority: 50

  - id: xia_zhi
    name: "夏至"
    category: "solar_term"
    calendarType: "solar_term"
    solarTerm: { name: "夏至", index: 10 }
    popup:
      enabled: true
      title: "☀️ 夏至"
      content: "昼最长，夜最短。恒星也以最炽烈的姿态燃烧。送你 {{bonusAmount}} 额度！"
    quotaBonus:
      enabled: true
      amount: 200
      unit: "token"
    priority: 50

  - id: qiu_fen
    name: "秋分"
    category: "solar_term"
    calendarType: "solar_term"
    solarTerm: { name: "秋分", index: 15 }
    popup:
      enabled: true
      title: "🍁 秋分"
      content: "昼夜均分，秋意渐浓。送你 {{bonusAmount}} 额度！"
    quotaBonus:
      enabled: true
      amount: 200
      unit: "token"
    priority: 50

  - id: dong_zhi
    name: "冬至"
    category: "solar_term"
    calendarType: "solar_term"
    solarTerm: { name: "冬至", index: 22 }
    popup:
      enabled: true
      title: "❄️ 冬至"
      content: "冬至大如年。送你 {{bonusAmount}} 额度！"
      animation:
        enabled: true
        type: "snow"
        duration: 10
    quotaBonus:
      enabled: true
      amount: 300
      unit: "token"
    priority: 60

  # ═══════════════════════════════════════════════════════════
  # 特殊节日
  # ═══════════════════════════════════════════════════════════
  - id: programmers_day
    name: "程序员节"
    nameEn: "Programmers' Day"
    category: "special"
    calendarType: "solar"
    solarDate: { month: 10, day: 24 }
    popup:
      enabled: true
      title: "💻 1024 程序员节"
      content: "Hello World！祝程序员们节日快乐！送你 {{bonusAmount}} 额度！"
      animation:
        enabled: true
        type: "code_rain"
        duration: 15
    quotaBonus:
      enabled: true
      amount: 1024
      unit: "token"
      description: "程序员专属额度"
    priority: 85

  # ═══════════════════════════════════════════════════════════
  # 管理员自定义节日（示例）
  # ═══════════════════════════════════════════════════════════
  - id: omichub_anniversary
    name: "OmicHub 周年庆"
    category: "custom"
    calendarType: "solar"
    solarDate: { month: 6, day: 18 }
    activeRange: { year: 2026, offsetDays: 0, durationDays: 3 }
    popup:
      enabled: true
      title: "🎂 OmicHub 周年庆"
      content: "感恩相伴，共赴未来。周年庆特别福利 {{bonusAmount}} 额度！"
    quotaBonus:
      enabled: true
      amount: 2000
      unit: "token"
    priority: 120

# ── 动画类型定义 ──
animationTypes:
  fireworks:
    name: "烟花"
    description: "全屏烟花动画"
    library: "@fireworks-js/react"
  snow:
    name: "雪花"
    description: "飘雪效果"
    library: "react-snowfall"
  confetti:
    name: "彩纸"
    description: "五彩纸屑庆祝"
    library: "canvas-confetti"
  star_heart:
    name: "星河爱心"
    description: "星星汇聚成爱心"
    library: "@tsparticles/react"
  moon_glow:
    name: "月光"
    description: "月亮发光+星云效果"
    library: "@flodlc/nebula"
  petal:
    name: "花瓣"
    description: "花瓣飘落"
    library: "@tsparticles/react"
  code_rain:
    name: "代码雨"
    description: "黑客帝国风格代码雨"
    library: "canvas-confetti"
  lantern:
    name: "灯笼"
    description: "灯笼飘动"
    library: "@tsparticles/react"
```

### 5.2 配置字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 唯一标识，snake_case |
| `name` | string | 是 | 中文节日名称 |
| `category` | enum | 是 | `traditional`/`modern`/`solar_term`/`custom`/`special` |
| `calendarType` | enum | 是 | `lunar`/`solar`/`solar_term` |
| `lunarDate.month/day` | number | 农历必填 | 农历月/日 |
| `solarDate.month/day` | number | 公历必填 | 公历月/日 |
| `activeRange` | object | 否 | 生效时间窗口 |
| `popup.enabled` | boolean | 是 | 是否启用弹窗 |
| `popup.title` | string | 是 | 弹窗标题 |
| `popup.content` | string | 是 | 弹窗内容（支持 `{{bonusAmount}}` 占位符） |
| `popup.primaryButton` | object | 否 | 主按钮配置 |
| `popup.animation` | object | 否 | 动画配置 |
| `quotaBonus.enabled` | boolean | 是 | 是否赠送额度 |
| `quotaBonus.amount` | number | 是 | 赠送数量 |
| `priority` | number | 否 | 优先级（数字越大越优先） |

---

## 六、管理后台设计

### 6.1 在现有"通知公告管理"页面中添加"节日彩蛋"Tab

基于你的第3张截图（通知公告管理页面），新增一个 **"节日彩蛋"** Tab，与现有的"首页条幅"、"通知提醒"并列。

### 6.2 管理界面布局

```
┌──────────────────────────────────────────────────────────────┐
│  通知公告管理                                                  │
│  ┌──────────┬──────────┬──────────────┐                       │
│  │ 首页条幅  │ 通知提醒  │  节日彩蛋 ✨  │  ← 新增Tab           │
│  └──────────┴──────────┴──────────────┘                       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─ 节日彩蛋开关 ──────────────────────────────────────┐     │
│  │                                                    │     │
│  │  [🟢 系统总开关]  节日彩蛋系统已开启                 │     │
│  │                                                    │     │
│  │  全局设置:                                          │     │
│  │  ☑️ 弹窗默认可关闭    ☑️ ESC关闭    ☑️ 点击遮罩关闭   │     │
│  │  ☑️ 每个用户只展示一次                               │     │
│  │  默认额度有效期: [ 30 ] 天                           │     │
│  │                                                    │     │
│  └────────────────────────────────────────────────────┘     │
│                                                              │
│  ┌─ 节日列表 ─────────────────────────────────────────┐     │
│  │  [+ 添加自定义节日]    [刷新缓存]                    │     │
│  │                                                    │     │
│  │  节日名称    │ 日期    │ 类型  │ 弹窗 │ 额度 │ 状态 │操作│  │
│  │ ───────────────────────────────────────────────── │     │
│  │  🎊 春节      2026-02-17 农历  ✅   ✅   🟢   编辑 │     │
│  │  🎄 圣诞节    2026-12-25 公历  ✅   ✅   🟢   编辑 │     │
│  │  💻 程序员节  2026-10-24 特殊  ✅   ✅   🟢   编辑 │     │
│  │  🎂 周年庆    2026-06-18 自定义 ✅   ✅   🟢   编辑 │     │
│  │  ...                                                │     │
│  │                                                    │     │
│  └────────────────────────────────────────────────────┘     │
│                                                              │
│  ┌─ 添加/编辑节日弹窗 ─────────────────────────────────┐     │
│  │                                                    │     │
│  │  节日名称: [________________]                       │     │
│  │  日期类型: ○ 农历  ○ 公历  ○ 节气  ○ 自定义        │     │
│  │  日期设置: [________________]                       │     │
│  │                                                    │     │
│  │  ── 弹窗设置 ──                                    │     │
│  │  ☑️ 启用弹窗                                        │     │
│  │  弹窗标题: [________________]                       │     │
│  │  弹窗内容: [________________]                       │     │
│  │  （支持 {{bonusAmount}} 变量）                       │     │
│  │  主按钮文字: [立即领取]                             │     │
│  │  跳转链接: [________________]                       │     │
│  │                                                    │     │
│  │  ── 动画设置 ──                                    │     │
│  │  ☑️ 启用动画                                        │     │
│  │  动画类型: [ 烟花 ▼ ]                              │     │
│  │  （烟花/雪花/彩纸/星河爱心/月光/花瓣/代码雨）        │     │
│  │  动画持续: [ 15 ] 秒                                │     │
│  │                                                    │     │
│  │  ── 额度设置 ──                                    │     │
│  │  ☑️ 赠送额度                                        │     │
│  │  赠送数量: [ 1000 ] tokens                          │     │
│  │  有效期: [ 30 ] 天                                  │     │
│  │                                                    │     │
│  │  ── 生效设置 ──                                    │     │
│  │  优先级: [ 100 ]                                    │     │
│  │  提前开始: [ 1 ] 天                                 │     │
│  │  持续: [ 7 ] 天                                     │     │
│  │                                                    │     │
│  │           [取消]  [保存]                            │     │
│  │                                                    │     │
│  └────────────────────────────────────────────────────┘     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 6.3 首页通知条幅联动

基于你的第2张截图（通知提醒页面），节日彩蛋开启时：
- 在通知列表顶部自动添加一条节日通知
- 格式：`🎊 [节日名称] 特别活动进行中 — 点击领取额度`
- 带有一个可点击的链接，跳转到额度领取或活动页面

---

## 七、额度赠送系统设计

### 7.1 赠送触发流程

```
用户打开首页
    │
    ▼
 调用 FestivalService.getTodayFestival()
    │
    ├── 无节日 ──→ 正常流程
    │
    └── 有节日 ──→ 检查弹窗配置 ──→ 展示弹窗
                         │
                         └── 检查额度配置
                                  │
                                  ├── 已领取 ──→ 显示"已领取"
                                  │
                                  └── 未领取 ──→ 显示"立即领取"按钮
                                           │
                                           └── 用户点击 ──→ 调用 claim API
```

### 7.2 防重复赠送（三层防护）

| 层级 | 机制 | 实现方式 |
|------|------|----------|
| **第一层** | 前端缓存 | `localStorage.setItem('festival_claimed_${festivalId}_${userId}', '1')` |
| **第二层** | 服务端幂等 | Redis `SETNX` 锁，60秒过期 |
| **第三层** | 数据库唯一约束 | `(userId, festivalId, year)` 联合唯一索引 |

### 7.3 核心代码示例

```typescript
// 节日检测 Hook
function useTodayFestival() {
  const [festival, setFestival] = useState<FestivalConfig | null>(null);
  
  useEffect(() => {
    fetch('/api/festival/today')
      .then(r => r.json())
      .then(data => {
        if (data.hasFestival) setFestival(data.festival);
      });
  }, []);
  
  return festival;
}

// 弹窗组件
function FestivalPopup({ festival }: { festival: FestivalConfig }) {
  const [isOpen, setIsOpen] = useState(false);
  const [claimed, setClaimed] = useState(false);
  const storageKey = `festival_seen_${festival.id}`;
  
  useEffect(() => {
    const seen = localStorage.getItem(storageKey);
    if (!seen) {
      setIsOpen(true);
      localStorage.setItem(storageKey, '1');
      // 触发庆祝特效
      confetti({ particleCount: 150, spread: 100, origin: { y: 0.6 } });
    }
  }, []);
  
  const handleClaim = async () => {
    const res = await fetch('/api/quota/claim', {
      method: 'POST',
      body: JSON.stringify({ festivalId: festival.id }),
    });
    const data = await res.json();
    if (data.success) {
      setClaimed(true);
      toast.success(`成功领取 ${data.amount} 额度！`);
      confetti({ particleCount: 200, spread: 120 });
    }
  };
  
  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.8 }}
          transition={{ type: 'spring', damping: 25 }}
          className="festival-popup-overlay"
        >
          <div className="festival-popup">
            <h2>{festival.popup.title}</h2>
            <p>{festival.popup.content.replace('{{bonusAmount}}', 
                 `${festival.quotaBonus?.amount || 0}`)}</p>
            
            {festival.quotaBonus?.enabled && !claimed && (
              <button onClick={handleClaim}>
                {festival.popup.primaryButton?.text || '立即领取'}
              </button>
            )}
            
            {claimed && <p>已领取 ✓</p>}
            
            {festival.popup.secondaryButton?.link && (
              <a href={festival.popup.secondaryButton.link}>
                {festival.popup.secondaryButton.text || '了解更多'}
              </a>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
```

---

## 八、与平台主题相符的动画设计建议

### 8.1 动画与节日的对应关系

OmicHub 的平台宗旨是：

> "我们只是借用了宇宙中的这些碳、氢、氧原子几十年，用它们去短暂地体验了一次这个世界。
> 组成我们大脑和身体的每一个原子，都来自几十亿年前远古恒星内部的核聚变爆炸。
> 当生命结束时，我们并没有化为虚无，我们只是回到了那个浩瀚的宇宙中，换了一种方式继续存在。"

因此，所有动画效果都应围绕**宇宙、星空、原子、生命**的主题展开：

| 节日 | 推荐动画 | 主题寓意 | 实现库 |
|------|----------|----------|--------|
| **春节** | 超新星爆发 + 星云扩散 | 恒星诞生，万象更新 | `@fireworks-js/react` + `@flodlc/nebula` |
| **元宵节** | 孔明灯升空 + 萤火虫 | 光点飞向星空，回归宇宙 | `@tsparticles/react` |
| **端午节** | 龙舟划过星河 | 在宇宙中竞渡 | `canvas-confetti` |
| **七夕** | 银河鹊桥 + 双星系统 | 牛郎织女化为双星 | `@tsparticles/react` + 星星连线 |
| **中秋节** | 满月升起 + 月光星云 | 月球只是宇宙的卫星 | `@flodlc/nebula` |
| **圣诞节** | 雪花 + 极光 | 宇宙寒冷而美丽 | `react-snowfall` + CSS渐变 |
| **元旦** | 宇宙大爆炸 | 新年新宇宙 | `canvas-confetti` + `@flodlc/nebula` |
| **程序员节** | 代码雨 + 矩阵数字 | 我们用代码模拟宇宙 | Canvas手写 |
| **立春/夏至/秋分/冬至** | 太阳系运行 | 地球在宇宙中的位置 | `@flodlc/nebula` |
| **周年庆** | 星系碰撞 + 星云汇聚 | OmicHub在宇宙中成长 | `@tsparticles/react` |

### 8.2 星空主题弹窗UI设计建议

基于你的第4张截图（关于页面）的星空主题，节日弹窗也应采用一致的深色星空风格：

```tsx
// 弹窗样式建议
const popupStyle = {
  background: 'linear-gradient(135deg, #0a0e27 0%, #1a1a40 50%, #16213e 100%)',
  border: '1px solid rgba(100, 149, 237, 0.3)',
  borderRadius: '16px',
  boxShadow: '0 25px 50px rgba(0,0,0,0.5), 0 0 30px rgba(65, 105, 225, 0.15)',
  color: '#e0e0ff',
  // 配合星空粒子背景
};

// 按钮样式
const buttonStyle = {
  background: 'linear-gradient(135deg, #4a90d9 0%, #6b5ce7 100%)',
  color: '#fff',
  border: 'none',
  borderRadius: '8px',
  boxShadow: '0 0 15px rgba(75, 108, 183, 0.4)',
};

// 额度展示样式
const quotaStyle = {
  fontSize: '2.5rem',
  fontWeight: 'bold',
  color: '#FFD700',
  textShadow: '0 0 20px rgba(255, 215, 0, 0.5)',
};
```

### 8.3 全屏动画模式（重大节日）

对于春节、国庆、周年庆等重大节日，可启用全屏动画模式：

```tsx
function FullScreenFestivalEffect({ type }: { type: string }) {
  switch (type) {
    case 'fireworks':
      return <Fireworks options={{ ... }} style={{ position: 'fixed', inset: 0, zIndex: 0 }} />;
    case 'nebula':
      return <ReactNebula config={{ ... }} style={{ position: 'fixed', inset: 0, zIndex: 0 }} />;
    case 'snow':
      return <Snowfall style={{ position: 'fixed', inset: 0, zIndex: 0 }} />;
    default:
      return <Particles options={starOptions} style={{ position: 'fixed', inset: 0, zIndex: 0 }} />;
  }
}
```

---

## 九、实施路线图

### Phase 1: 基础功能（1周）

| 任务 | 说明 |
|------|------|
| 安装核心库 | `motion`, `sonner`, `canvas-confetti`, `lunisolar` |
| YAML配置加载 | 实现配置文件解析和热更新 |
| 基础弹窗组件 | FestivalPopup 组件开发 |
| 节日检测API | `/api/festival/today` 接口 |
| 额度领取API | `/api/quota/claim` 接口 |

### Phase 2: 动画与管理（1周）

| 任务 | 说明 |
|------|------|
| 动画效果库 | 集成 tsParticles、nebula、fireworks |
| 动画-节日映射 | 实现不同节日对应不同动画 |
| 管理后台页面 | 在现有通知管理页面添加节日彩蛋Tab |
| 额度管理 | 防重复、有效期、流水记录 |

### Phase 3: 完善与优化（1周）

| 任务 | 说明 |
|------|------|
| 农历自动转换 | lunisolar 农历日期自动转公历 |
| 24节气支持 | 节气自动检测 |
| 自定义节日 | 管理员可添加自定义节日 |
| 性能优化 | 动画性能、首屏加载优化 |
| 测试与上线 | 节日模拟测试、上线 |

### 最小可行产品（MVP）

如果希望最快上线，可先实现：

```bash
npm install motion sonner canvas-confetti lunisolar
```

1. **纯YAML配置**（无需管理后台UI，直接编辑yaml文件）
2. **2种动画**（canvas-confetti彩纸 + 手动Canvas星空背景）
3. **基础弹窗**（Motion动画 + Sonner通知）
4. **额度赠送**（基础领取 + localStorage防重复）

预计 **3-5天** 可完成MVP。

---

## 附录

### A. 推荐安装命令汇总

```bash
# 核心库（必装）
npm install motion sonner canvas-confetti lunisolar

# 粒子效果（推荐）
npm install @tsparticles/react @tsparticles/slim @tsparticles/engine

# 宇宙背景（可选）
npm install @flodlc/nebula

# 烟花效果（可选，新年/国庆用）
npm install @fireworks-js/react

# 雪花效果（可选，圣诞/冬至用）
npm install react-snowfall

# 法定假日判断（可选，如需要调休判断）
npm install chinese-days
```

### B. 2026年重要节日公历日期

| 节日 | 2026年日期 | 类型 |
|------|-----------|------|
| 元旦 | 1月1日 | 公历 |
| 春节 | 2月17日 | 农历 |
| 元宵节 | 3月3日 | 农历 |
| 情人节 | 2月14日 | 公历 |
| 清明节 | 4月5日 | 节气 |
| 端午节 | 6月19日 | 农历 |
| 七夕 | 9月17日 | 农历 |
| 中秋节 | 9月25日 | 农历 |
| 国庆节 | 10月1日 | 公历 |
| 程序员节 | 10月24日 | 特殊 |
| 圣诞节 | 12月25日 | 公历 |
| 冬至 | 12月22日 | 节气 |

### C. 参考资源

- **canvas-confetti**: https://github.com/catdad/canvas-confetti
- **Motion**: https://github.com/motiondivision/motion
- **Sonner**: https://github.com/emilkowalski/sonner
- **tsParticles**: https://github.com/tsparticles/tsparticles
- **Nebula**: https://github.com/flodlc/nebula
- **lunisolar**: https://github.com/waterbeside/lunisolar
- **chinese-days**: https://chinese-days.yaavi.me
- **MagicUI**: https://magicui.design

---

> **报告总结**: 本调研覆盖了国内外平台的节日彩蛋案例、8个前端动画库、6个中国节假日数据源。推荐采用 **Motion + Sonner + canvas-confetti + lunisolar** 作为核心库，配合YAML配置化设计，实现与OmicHub"We are made of star-stuff"宇宙主题高度契合的节日彩蛋系统。MVP版本可在3-5天内完成。
