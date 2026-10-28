# 🌌 OmicHub 登录页「星尘之境」视觉升级方案

> **文档版本**：v1.0  
> **目标页面**：`/login` 登录页  
> **设计主题**：星空粒子 · 星尘哲学 · 治愈交互  
> **交付形态**：React 组件 + CSS 样式 + 文案配置

---

## 一、设计概述

当前登录页背景为静态紫色渐变，视觉重心单一，大面积留白未得到有效利用。本次升级以 **"We are made of star-stuff"** 为核心意象，通过三层视觉叠加（星空背景层 → 登录卡片层 → 底部文案层），将平台哲学融入用户第一眼看到的界面，同时保持功能区域的清晰聚焦。

### 1.1 设计原则

| 原则 | 说明 |
|------|------|
| **宇宙感，不喧宾夺主** | 背景动画是氛围，登录卡片永远是视觉焦点 |
| **文案即装饰** | 将星尘之语作为底部视觉元素，而非纯文本堆砌 |
| **微交互有温度** | 猫咪探头、卡片漂浮、输入框呼吸光，处处有反馈 |
| **性能优先** | Canvas 动画在移动端自动降级，保证首屏加载速度 |

---

## 二、三层视觉架构

```
┌─────────────────────────────────────────────┐
│  Layer 1: StarField (Canvas 星空粒子层)      │  ← 最底层，全屏动态
│  · 120颗呼吸星星                              │
│  · 40个自动连线粒子                           │
│  · 随机流星拖尾                               │
├─────────────────────────────────────────────┤
│  Layer 2: LoginCard (登录卡片层)              │  ← 视觉焦点，居中浮动
│  · 猫咪探头装饰                               │
│  · 微浮动动画                                 │
│  · 表单输入区                                 │
├─────────────────────────────────────────────┤
│  Layer 3: StardustQuote (底部文案层)          │  ← 底部居中，哲学收尾
│  · 英文标语                                   │
│  · 中文精简版 + hover 展开完整版               │
└─────────────────────────────────────────────┘
```

---

## 三、Layer 1：StarField 星空粒子背景

### 3.1 组件定位

- **层级**：`position: absolute; z-index: 0`
- **尺寸**：`width: 100%; height: 100vh`
- **技术**：HTML5 Canvas 2D，不依赖任何第三方库

### 3.2 动画规格

#### 3.2.1 呼吸星星（Background Stars）

| 参数 | 值 | 说明 |
|------|-----|------|
| 数量 | 120 颗 | 桌面端；移动端降级为 60 颗 |
| 半径范围 | 0.3px ~ 1.8px | 大小不一，模拟真实星空 |
| 透明度波动 | 0.2 ~ 1.0 | 正弦波呼吸，每颗星独立相位 |
| 波动速度 | 0.005 ~ 0.025 /帧 | 随机差异，避免同步闪烁 |

#### 3.2.2 网络粒子（Network Particles）

| 参数 | 值 | 说明 |
|------|-----|------|
| 数量 | 40 个 | 桌面端；移动端降级为 20 个 |
| 运动速度 | ±0.4 px/帧 | 随机方向，匀速漂移 |
| 连线阈值 | 100px | 两粒子距离 < 100px 时绘制连线 |
| 连线透明度 | 随距离衰减 | `opacity = 0.15 * (1 - dist/100)` |
| 鼠标交互 | 150px 引力半径 | 鼠标靠近时粒子被轻微吸引 |
| 阻尼系数 | 0.99 | 防止速度无限累积 |

#### 3.2.3 流星（Shooting Star）

| 参数 | 值 | 说明 |
|------|-----|------|
| 触发间隔 | 4 ~ 8 秒随机 | 避免机械感 |
| 运动轨迹 | 左上 → 右下 | `vx: 3~5, vy: 1~2.5` |
| 拖尾长度 | 15 个历史点 | 线性渐变透明度 |
| 生命周期 | 1.0 → 0 | 每帧衰减 0.015 |

### 3.3 React 组件代码

```tsx
// src/components/StarField/index.tsx
import React, { useEffect, useRef } from 'react';
import './index.css';

interface Star {
  x: number; y: number; r: number;
  alpha: number; speed: number; dir: number;
}

interface Particle {
  x: number; y: number;
  vx: number; vy: number; r: number;
}

interface ShootingStar {
  x: number; y: number;
  vx: number; vy: number;
  life: number;
  tail: { x: number; y: number }[];
}

const StarField: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const animRef = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const isMobile = window.innerWidth < 768;
    const STAR_COUNT = isMobile ? 60 : 120;
    const PARTICLE_COUNT = isMobile ? 20 : 40;
    const CONNECTION_DIST = 100;

    let w = 0, h = 0;
    const stars: Star[] = [];
    const particles: Particle[] = [];
    let shootingStar: ShootingStar | null = null;
    const mouse = { x: -1000, y: -1000 };

    const resize = () => {
      w = canvas.width = container.offsetWidth;
      h = canvas.height = container.offsetHeight;
    };
    resize();

    // 初始化星星
    for (let i = 0; i < STAR_COUNT; i++) {
      stars.push({
        x: Math.random() * w,
        y: Math.random() * h,
        r: Math.random() * 1.5 + 0.3,
        alpha: Math.random(),
        speed: Math.random() * 0.02 + 0.005,
        dir: Math.random() > 0.5 ? 1 : -1
      });
    }

    // 初始化粒子
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      particles.push({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.4,
        vy: (Math.random() - 0.5) * 0.4,
        r: Math.random() * 2 + 1
      });
    }

    // 鼠标事件
    const onMouseMove = (e: MouseEvent) => {
      const rect = container.getBoundingClientRect();
      mouse.x = e.clientX - rect.left;
      mouse.y = e.clientY - rect.top;
    };
    const onMouseLeave = () => { mouse.x = -1000; mouse.y = -1000; };

    container.addEventListener('mousemove', onMouseMove);
    container.addEventListener('mouseleave', onMouseLeave);
    window.addEventListener('resize', resize);

    // 流星定时器
    let shootTimer: ReturnType<typeof setTimeout>;
    const spawnShootingStar = () => {
      if (!shootingStar) {
        shootingStar = {
          x: Math.random() * w * 0.5,
          y: Math.random() * h * 0.3,
          vx: 3 + Math.random() * 2,
          vy: 1 + Math.random() * 1.5,
          life: 1,
          tail: []
        };
      }
      shootTimer = setTimeout(spawnShootingStar, 4000 + Math.random() * 4000);
    };
    spawnShootingStar();

    const animate = () => {
      ctx.clearRect(0, 0, w, h);

      // 1. 绘制呼吸星星
      stars.forEach(s => {
        s.alpha += s.speed * s.dir;
        if (s.alpha > 1 || s.alpha < 0.2) s.dir *= -1;
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255, 255, 255, ${s.alpha * 0.8})`;
        ctx.fill();
      });

      // 2. 更新并绘制网络粒子
      particles.forEach((p, i) => {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0 || p.x > w) p.vx *= -1;
        if (p.y < 0 || p.y > h) p.vy *= -1;

        // 鼠标引力
        const dx = mouse.x - p.x;
        const dy = mouse.y - p.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 150) {
          p.vx += dx * 0.0003;
          p.vy += dy * 0.0003;
        }
        p.vx *= 0.99;
        p.vy *= 0.99;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(255, 255, 255, 0.6)';
        ctx.fill();

        // 连线
        for (let j = i + 1; j < particles.length; j++) {
          const p2 = particles[j];
          const d = Math.sqrt((p.x - p2.x) ** 2 + (p.y - p2.y) ** 2);
          if (d < CONNECTION_DIST) {
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(p2.x, p2.y);
            ctx.strokeStyle = `rgba(255, 255, 255, ${0.15 * (1 - d / CONNECTION_DIST)})`;
            ctx.lineWidth = 0.8;
            ctx.stroke();
          }
        }
      });

      // 3. 绘制流星
      if (shootingStar) {
        shootingStar.x += shootingStar.vx;
        shootingStar.y += shootingStar.vy;
        shootingStar.life -= 0.015;
        shootingStar.tail.push({ x: shootingStar.x, y: shootingStar.y });
        if (shootingStar.tail.length > 15) shootingStar.tail.shift();

        ctx.beginPath();
        for (let i = 0; i < shootingStar.tail.length - 1; i++) {
          const t = shootingStar.tail[i];
          const t2 = shootingStar.tail[i + 1];
          ctx.moveTo(t.x, t.y);
          ctx.lineTo(t2.x, t2.y);
        }
        ctx.strokeStyle = `rgba(255, 255, 255, ${shootingStar.life * 0.6})`;
        ctx.lineWidth = 2;
        ctx.stroke();

        ctx.beginPath();
        ctx.arc(shootingStar.x, shootingStar.y, 2, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255, 255, 255, ${shootingStar.life})`;
        ctx.shadowBlur = 10;
        ctx.shadowColor = 'white';
        ctx.fill();
        ctx.shadowBlur = 0;

        if (shootingStar.life <= 0) shootingStar = null;
      }

      animRef.current = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      cancelAnimationFrame(animRef.current);
      clearTimeout(shootTimer);
      container.removeEventListener('mousemove', onMouseMove);
      container.removeEventListener('mouseleave', onMouseLeave);
      window.removeEventListener('resize', resize);
    };
  }, []);

  return (
    <div ref={containerRef} className="starfield-container">
      <canvas ref={canvasRef} className="starfield-canvas" />
    </div>
  );
};

export default StarField;
```

```css
/* src/components/StarField/index.css */
.starfield-container {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
  overflow: hidden;
  background: linear-gradient(135deg, #9B7EC8 0%, #7B5AA6 50%, #6B4B96 100%);
}

.starfield-canvas {
  display: block;
  width: 100%;
  height: 100%;
}
```

---

## 四、Layer 2：LoginCard 登录卡片优化

### 4.1 猫咪装饰增强

现有猫咪为静态 emoji，增加 hover 反馈：

```css
.cat-peek {
  position: absolute;
  top: -28px;
  font-size: 44px;
  filter: drop-shadow(0 4px 8px rgba(0,0,0,0.15));
  transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  cursor: pointer;
}

.cat-peek:hover {
  transform: scale(1.2) rotate(-8deg) translateY(-4px);
}

.cat-left { left: 30px; }
.cat-right { right: 30px; }
```

> 💡 **彩蛋建议**：点击橘猫 🐱 时，可以触发一次额外的流星动画；点击黑猫 🐈‍⬛ 时，卡片轻微抖动一下。作为隐藏彩蛋，不在文档中明示给用户。

### 4.2 卡片微浮动动画

让卡片产生「漂浮在宇宙中」的轻盈感：

```css
@keyframes floatCard {
  0%, 100% { transform: translateY(0px); }
  50% { transform: translateY(-6px); }
}

.login-card {
  animation: floatCard 6s ease-in-out infinite;
  /* 保持你现有的其他样式 */
}
```

参数说明：
- 振幅：6px（极轻微，不引起眩晕）
- 周期：6s（缓慢，符合宇宙节奏）
- 缓动：`ease-in-out`（平滑无突变）

### 4.3 输入框聚焦优化

现有输入框聚焦态较生硬，升级为「呼吸光晕」：

```css
.input-field {
  width: 100%;
  padding: 11px 14px;
  border: 1px solid #E0E0E0;
  border-radius: 10px;
  font-size: 14px;
  background: #FAFAFA;
  outline: none;
  transition: all 0.25s ease;
  box-sizing: border-box;
}

.input-field:focus {
  border-color: #4A6CF7;
  background: #FFFFFF;
  box-shadow: 0 0 0 3px rgba(74, 108, 247, 0.12),
              0 0 20px rgba(74, 108, 247, 0.08);
}
```

### 4.4 登录按钮增强

```css
.btn-login {
  background: linear-gradient(135deg, #4A6CF7 0%, #6B4B96 100%);
  color: white;
  border: none;
  padding: 12px 0;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.25s ease;
  box-shadow: 0 4px 12px rgba(74, 108, 247, 0.3);
}

.btn-login:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(74, 108, 247, 0.4);
}

.btn-login:active {
  transform: translateY(0);
  box-shadow: 0 2px 8px rgba(74, 108, 247, 0.3);
}
```

---

## 五、Layer 3：StardustQuote 底部文案层

### 5.1 文案内容

| 类型 | 内容 |
|------|------|
| **英文标语** | "We are made of star-stuff" |
| **中文精简版**（默认显示） | 我们只是借用了宇宙中的这些原子，短暂地体验了一次这个世界。 |
| **中文完整版**（hover 展开） | 我们只是借用了宇宙中的这些碳、氢、氧原子几十年，用它们去短暂地体验了一次这个世界。组成我们大脑和身体的每一个原子，都来自几十亿年前远古恒星内部的核聚变爆炸。当生命结束时，我们并没有化为虚无，我们只是回到了那个浩瀚的宇宙中，换了一种方式继续存在。 |

### 5.2 组件代码

```tsx
// src/components/StardustQuote/index.tsx
import React, { useState } from 'react';
import './index.css';

const StardustQuote: React.FC = () => {
  const [expanded, setExpanded] = useState(false);

  return (
    <div 
      className="stardust-quote"
      onMouseEnter={() => setExpanded(true)}
      onMouseLeave={() => setExpanded(false)}
    >
      <div className="quote-en">"We are made of star-stuff"</div>
      <div className="quote-cn-short">
        我们只是借用了宇宙中的这些原子，短暂地体验了一次这个世界。
      </div>
      <div className={`quote-cn-full ${expanded ? 'expanded' : ''}`}>
        我们只是借用了宇宙中的这些碳、氢、氧原子几十年，用它们去短暂地体验了一次这个世界。
        组成我们大脑和身体的每一个原子，都来自几十亿年前远古恒星内部的核聚变爆炸。
        当生命结束时，我们并没有化为虚无，我们只是回到了那个浩瀚的宇宙中，换了一种方式继续存在。
      </div>
    </div>
  );
};

export default StardustQuote;
```

```css
/* src/components/StardustQuote/index.css */
.stardust-quote {
  position: absolute;
  bottom: 32px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10;
  text-align: center;
  max-width: 680px;
  padding: 0 24px;
  opacity: 0.85;
  transition: opacity 0.4s ease;
  cursor: default;
}

.stardust-quote:hover {
  opacity: 1;
}

.quote-en {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.75);
  font-style: italic;
  letter-spacing: 1.5px;
  margin-bottom: 10px;
  font-family: Georgia, 'Times New Roman', serif;
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
}

.quote-cn-short {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  line-height: 1.8;
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
  transition: all 0.3s ease;
}

.quote-cn-full {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.55);
  line-height: 1.9;
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
  max-height: 0;
  opacity: 0;
  overflow: hidden;
  transition: max-height 0.6s ease, opacity 0.4s ease, margin-top 0.3s ease;
  margin-top: 0;
}

.quote-cn-full.expanded {
  max-height: 200px;
  opacity: 1;
  margin-top: 10px;
}

/* 移动端适配：隐藏完整版，精简版字号稍大 */
@media (max-width: 768px) {
  .stardust-quote {
    bottom: 16px;
    max-width: 90%;
  }
  .quote-cn-short {
    font-size: 11px;
  }
  .quote-cn-full {
    display: none;
  }
}
```

---

## 六、页面组装：LoginPage 整合

```tsx
// src/pages/Login/index.tsx
import React from 'react';
import StarField from '@/components/StarField';
import StardustQuote from '@/components/StardustQuote';
import LoginForm from './LoginForm'; // 你现有的登录表单
import './index.css';

const LoginPage: React.FC = () => {
  return (
    <div className="login-page">
      <StarField />
      <div className="login-content">
        <LoginForm />
      </div>
      <StardustQuote />
    </div>
  );
};

export default LoginPage;
```

```css
/* src/pages/Login/index.css */
.login-page {
  position: relative;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.login-content {
  position: relative;
  z-index: 10;
}
```

---

## 七、响应式适配策略

### 7.1 断点规则

| 断点 | 范围 | 主要调整 |
|------|------|----------|
| **桌面端** | ≥ 1024px | 完整体验，120星/40粒子，完整文案 |
| **平板端** | 768px ~ 1023px | 80星/30粒子，文案正常显示 |
| **移动端** | < 768px | 60星/20粒子，隐藏完整文案，卡片宽度 85% |

### 7.2 性能降级

在 `StarField` 组件中，通过 `window.innerWidth` 在 `useEffect` 初始化时判断设备类型，自动调整粒子数量。同时建议：

- 为 `requestAnimationFrame` 添加 `document.visibilityState` 监听，页面不可见时暂停动画
- 低端设备（`navigator.hardwareConcurrency <= 4`）可进一步将粒子数量减半

```tsx
// 在 useEffect 中添加
const handleVisibility = () => {
  if (document.hidden) {
    // 暂停动画逻辑
  } else {
    // 恢复动画
  }
};
document.addEventListener('visibilitychange', handleVisibility);
```

---

## 八、验收清单

### 8.1 视觉验收

- [ ] 背景为动态紫色渐变 + 星空粒子，无静态感
- [ ] 星星有呼吸闪烁，不机械同步
- [ ] 粒子间自动连线，鼠标靠近时有轻微引力反馈
- [ ] 每 4~8 秒有流星划过，带拖尾效果
- [ ] 登录卡片有缓慢上下浮动（6s 周期，6px 振幅）
- [ ] 猫咪 hover 时有放大 + 旋转反馈
- [ ] 输入框聚焦时有蓝色光晕
- [ ] 底部文案默认显示英文 + 中文精简版
- [ ] 鼠标 hover 底部文案区域时，完整版平滑展开

### 8.2 交互验收

- [ ] 登录表单功能不受背景动画影响，可正常输入
- [ ] 页面切换/后台运行时，动画不占用 CPU
- [ ] 移动端访问时，文案不溢出，卡片不挤压
- [ ] 窗口 resize 时，Canvas 自动重绘，无拉伸变形

### 8.3 性能验收

- [ ] 桌面端 FPS 稳定在 55~60
- [ ] 移动端 FPS 稳定在 30 以上
- [ ] 首屏加载时间增加 < 100ms（Canvas 无外部依赖）

---

## 九、文件结构

```
src/
├── components/
│   ├── StarField/
│   │   ├── index.tsx      # Canvas 星空组件
│   │   └── index.css      # 容器样式
│   └── StardustQuote/
│       ├── index.tsx      # 底部文案组件
│       └── index.css      # 文案动画样式
├── pages/
│   └── Login/
│       ├── index.tsx      # 登录页组装
│       ├── index.css      # 页面布局
│       └── LoginForm.tsx  # 现有登录表单（复用）
```

---

## 十、备注与彩蛋建议

1. **猫咪彩蛋**：点击橘猫触发流星，点击黑猫触发卡片抖动，作为隐藏惊喜
2. **文案彩蛋**：在英文标语上快速点击 3 次，可以切换为拉丁语版 "Ex astris, ad astra"（从星辰中来，到星辰中去）
3. **背景色微调**：如果未来想换季节主题，只需修改 `StarField/index.css` 中的 `background: linear-gradient(...)` 即可

---

*文档由 OmicHub 设计委员会（阿姨）编制*  
*「我们只是借用了宇宙中的这些原子，短暂地体验了一次这个世界。」*
