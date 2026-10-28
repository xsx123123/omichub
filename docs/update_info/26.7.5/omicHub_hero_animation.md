# OmicHub 首页 Hero 动态背景动画方案

> 生成日期：2026-07-05
> 目标：替换 Hero 区域静态瓶子符号为动态 Canvas 动画，每次加载随机切换不同动画

---

## 一、设计思路

Hero 区域右侧大片蓝色渐变背景目前只有一个静态的烧瓶轮廓（图 14），视觉上单调且与平台科技感不符。改为 **Canvas 动态动画**后：

- 每次用户打开首页，随机加载一种动画模式
- 动画与蓝色/紫色渐变背景自然融合（`opacity: 0.35`）
- 不干扰左侧文字内容的可读性
- 纯前端实现，零外部依赖

---

## 二、四种动画模式

| 模式 | 名称 | 视觉特征 | 适合场景 |
|------|------|----------|----------|
| `dna` | DNA 双螺旋粒子 | A/T/C/G 碱基字母沿双螺旋轨道浮动 | 强调生物信息学基因属性 |
| `particles` | 浮动粒子网络 | 白色粒子缓慢漂移，近距粒子自动连线 | 科技感、数据流动感 |
| `wave` | 波浪网格 | 点阵网格随正弦波起伏，如测序波形 | 强调数据分析、波形处理 |
| `stars` | 星空粒子 | 白色星点向上飘动，大星带十字光芒 | 呼应"星尘工作站"主题 |

---

## 三、完整实现代码

### 3.1 HTML 结构

```html
<!-- Hero 区域容器 -->
<div class="hero-section">
  <!-- Canvas 动画层：绝对定位，覆盖整个 Hero 背景 -->
  <canvas id="hero-canvas" class="hero-canvas"></canvas>

  <!-- 内容层：文字、按钮，z-index 高于 Canvas -->
  <div class="hero-content">
    <div class="hero-greeting">夜深了，JIAN 👋</div>
    <h1 class="hero-title">OmicHub 星尘工作站 🌌</h1>
    <p class="hero-desc">
      华中农业大学园艺林学学院基因组学实验室出品！数据上传、流程分析、结果交付——像收集星尘一样，一站式攒齐你的组学宝藏 ✨ 让科研变得丝滑起来～
    </p>
    <div class="hero-actions">
      <button class="hero-btn-primary">🚀 开始分析</button>
      <button class="hero-btn-secondary">📊 查看仪表板</button>
    </div>
  </div>
</div>
```

### 3.2 CSS

```css
/* ========================================
   Hero 区域容器
   ======================================== */

.hero-section {
  position: relative;
  width: 100%;
  min-height: 280px;
  border-radius: 16px;
  overflow: hidden;
  background: linear-gradient(135deg, #4f6ef7 0%, #7c5cfc 50%, #a855f7 100%);
  /* 保持现有渐变，动画在其上叠加 */
}

/* ========================================
   Canvas 动画层
   ======================================== */

.hero-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  opacity: 0.35;           /* 半透明，不喧宾夺主 */
  pointer-events: none;    /* 不阻挡点击 */
  z-index: 1;
}

/* ========================================
   内容层（文字 + 按钮）
   ======================================== */

.hero-content {
  position: relative;
  z-index: 2;
  padding: 32px;
  color: white;
}

.hero-greeting {
  font-size: 14px;
  opacity: 0.85;
  margin-bottom: 8px;
}

.hero-title {
  font-size: 28px;
  font-weight: 600;
  margin: 0 0 12px 0;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.hero-desc {
  font-size: 14px;
  line-height: 1.6;
  opacity: 0.9;
  max-width: 520px;
  margin: 0 0 20px 0;
}

.hero-actions {
  display: flex;
  gap: 12px;
}

.hero-btn-primary {
  padding: 10px 20px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.2);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: white;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.hero-btn-primary:hover {
  background: rgba(255, 255, 255, 0.3);
  transform: translateY(-1px);
}

.hero-btn-secondary {
  padding: 10px 20px;
  border-radius: 10px;
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.4);
  color: white;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.hero-btn-secondary:hover {
  background: rgba(255, 255, 255, 0.1);
}

/* 响应式 */
@media (max-width: 768px) {
  .hero-section {
    min-height: 240px;
  }
  .hero-content {
    padding: 20px;
  }
  .hero-title {
    font-size: 22px;
  }
  .hero-desc {
    font-size: 13px;
    max-width: 100%;
  }
}
```

### 3.3 JavaScript（核心动画引擎）

```javascript
/**
 * OmicHub Hero 动态背景动画引擎
 * 支持 4 种模式随机切换，纯 Canvas 实现
 */

(function() {
  const canvas = document.getElementById('hero-canvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  let w, h, dpr, animationId;

  // ========== 工具函数 ==========

  function resize() {
    const rect = canvas.parentElement.getBoundingClientRect();
    dpr = window.devicePixelRatio || 1;
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    w = canvas.width / dpr;
    h = canvas.height / dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0); // 重置变换矩阵
  }

  resize();
  window.addEventListener('resize', resize);

  // ========== 随机选择动画模式 ==========

  const MODES = ['dna', 'particles', 'wave', 'stars'];
  const currentMode = MODES[Math.floor(Math.random() * MODES.length)];

  console.log('[HeroAnimation] Current mode:', currentMode);

  // ========== 模式 1: DNA 双螺旋粒子 ==========

  function initDNA() {
    const particles = [];
    const count = 40;
    const bases = ['A', 'T', 'C', 'G'];
    for (let i = 0; i < count; i++) {
      particles.push({
        t: i / count * Math.PI * 4,
        speed: 0.003 + Math.random() * 0.002,
        base: bases[Math.floor(Math.random() * 4)],
        size: 2 + Math.random() * 3,
        opacity: 0.3 + Math.random() * 0.5,
        offset: Math.random() * 100
      });
    }
    return { particles, phase: 0 };
  }

  function drawDNA(state) {
    ctx.clearRect(0, 0, w, h);

    const cx = w * 0.75;  // 偏右侧，不遮挡左侧文字
    const cy = h / 2;
    const radius = Math.min(w, h) * 0.12;
    const stretch = Math.min(w, h) * 0.18;

    state.phase += 0.008;

    ctx.strokeStyle = 'rgba(255,255,255,0.15)';
    ctx.lineWidth = 1;

    for (let i = 0; i < state.particles.length; i++) {
      const p = state.particles[i];
      p.t += p.speed;

      const y = cy + Math.sin(p.t + state.phase) * stretch;
      const x1 = cx + Math.cos(p.t + state.phase) * radius;
      const x2 = cx - Math.cos(p.t + state.phase) * radius;

      // 碱基配对连线
      ctx.beginPath();
      ctx.moveTo(x1, y);
      ctx.lineTo(x2, y);
      ctx.stroke();

      // 左链粒子
      ctx.globalAlpha = p.opacity * (0.5 + 0.5 * Math.sin(p.t + state.phase));
      ctx.fillStyle = 'rgba(255,255,255,0.7)';
      ctx.beginPath();
      ctx.arc(x1, y, p.size, 0, Math.PI * 2);
      ctx.fill();

      // 右链粒子
      ctx.beginPath();
      ctx.arc(x2, y, p.size, 0, Math.PI * 2);
      ctx.fill();

      // 大粒子显示碱基字母
      if (p.size > 3) {
        ctx.font = `${Math.floor(p.size + 4)}px monospace`;
        ctx.fillStyle = 'rgba(255,255,255,0.85)';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(p.base, x1, y);
      }
    }
    ctx.globalAlpha = 1;
  }

  // ========== 模式 2: 浮动粒子网络 ==========

  function initParticles() {
    const particles = [];
    const count = Math.floor((w * h) / 8000); // 根据面积自适应数量
    for (let i = 0; i < count; i++) {
      particles.push({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.5,
        vy: (Math.random() - 0.5) * 0.5,
        size: 1 + Math.random() * 4,
        opacity: 0.2 + Math.random() * 0.4,
        pulse: Math.random() * Math.PI * 2
      });
    }
    return { particles, time: 0 };
  }

  function drawParticles(state) {
    ctx.clearRect(0, 0, w, h);
    state.time += 0.016;

    // 更新并绘制粒子
    state.particles.forEach(p => {
      p.x += p.vx;
      p.y += p.vy;
      p.pulse += 0.02;

      // 边界循环
      if (p.x < -10) p.x = w + 10;
      if (p.x > w + 10) p.x = -10;
      if (p.y < -10) p.y = h + 10;
      if (p.y > h + 10) p.y = -10;

      const alpha = p.opacity * (0.6 + 0.4 * Math.sin(p.pulse));
      ctx.globalAlpha = alpha;
      ctx.fillStyle = 'rgba(255,255,255,0.8)';
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size * (0.8 + 0.2 * Math.sin(p.pulse)), 0, Math.PI * 2);
      ctx.fill();
    });

    // 近距粒子连线
    ctx.strokeStyle = 'rgba(255,255,255,0.12)';
    ctx.lineWidth = 0.5;
    const connectDist = 100;

    for (let i = 0; i < state.particles.length; i++) {
      for (let j = i + 1; j < state.particles.length; j++) {
        const dx = state.particles[i].x - state.particles[j].x;
        const dy = state.particles[i].y - state.particles[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < connectDist) {
          ctx.globalAlpha = (1 - dist / connectDist) * 0.15;
          ctx.beginPath();
          ctx.moveTo(state.particles[i].x, state.particles[i].y);
          ctx.lineTo(state.particles[j].x, state.particles[j].y);
          ctx.stroke();
        }
      }
    }
    ctx.globalAlpha = 1;
  }

  // ========== 模式 3: 波浪网格 ==========

  function initWave() {
    const density = Math.min(w, h) < 400 ? 15 : 30;
    return { time: 0, cols: density, rows: Math.floor(density * 0.5) };
  }

  function drawWave(state) {
    ctx.clearRect(0, 0, w, h);
    state.time += 0.02;

    const cellW = w / state.cols;
    const cellH = h / state.rows;

    for (let i = 0; i < state.cols; i++) {
      for (let j = 0; j < state.rows; j++) {
        const x = i * cellW + cellW / 2;
        const y = j * cellH + cellH / 2;
        const dist = Math.sqrt((x - w/2) ** 2 + (y - h/2) ** 2);
        const wave = Math.sin(dist * 0.03 - state.time * 2) * 0.5 + 0.5;
        const size = 1 + wave * 3;
        const alpha = 0.1 + wave * 0.35;

        ctx.globalAlpha = alpha;
        ctx.fillStyle = 'rgba(255,255,255,0.9)';
        ctx.beginPath();
        ctx.arc(x, y, size, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    ctx.globalAlpha = 1;
  }

  // ========== 模式 4: 星空粒子 ==========

  function initStars() {
    const stars = [];
    const count = Math.floor((w * h) / 5000);
    for (let i = 0; i < count; i++) {
      stars.push({
        x: Math.random() * w,
        y: Math.random() * h,
        size: 0.5 + Math.random() * 2,
        speed: 0.1 + Math.random() * 0.3,
        twinkle: Math.random() * Math.PI * 2,
        twinkleSpeed: 0.02 + Math.random() * 0.03
      });
    }
    return { stars, time: 0 };
  }

  function drawStars(state) {
    ctx.clearRect(0, 0, w, h);
    state.time += 0.016;

    state.stars.forEach(s => {
      s.y -= s.speed;  // 向上飘动
      s.twinkle += s.twinkleSpeed;

      if (s.y < -5) {
        s.y = h + 5;
        s.x = Math.random() * w;
      }

      const alpha = 0.3 + 0.5 * Math.sin(s.twinkle);
      ctx.globalAlpha = alpha;
      ctx.fillStyle = 'rgba(255,255,255,0.95)';

      // 星点
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.size, 0, Math.PI * 2);
      ctx.fill();

      // 大星十字光芒
      if (s.size > 1.5) {
        ctx.strokeStyle = `rgba(255,255,255,${alpha * 0.4})`;
        ctx.lineWidth = 0.5;
        const r = s.size * 3;
        ctx.beginPath();
        ctx.moveTo(s.x - r, s.y);
        ctx.lineTo(s.x + r, s.y);
        ctx.moveTo(s.x, s.y - r);
        ctx.lineTo(s.x, s.y + r);
        ctx.stroke();
      }
    });
    ctx.globalAlpha = 1;
  }

  // ========== 动画调度器 ==========

  let state = null;

  function animate() {
    switch (currentMode) {
      case 'dna':
        if (!state) state = initDNA();
        drawDNA(state);
        break;
      case 'particles':
        if (!state) state = initParticles();
        drawParticles(state);
        break;
      case 'wave':
        if (!state) state = initWave();
        drawWave(state);
        break;
      case 'stars':
        if (!state) state = initStars();
        drawStars(state);
        break;
    }
    animationId = requestAnimationFrame(animate);
  }

  // 启动
  animate();

  // 页面卸载时清理
  window.addEventListener('beforeunload', () => {
    if (animationId) cancelAnimationFrame(animationId);
  });

  // 可见性变化时暂停/恢复（性能优化）
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      if (animationId) cancelAnimationFrame(animationId);
    } else {
      animate();
    }
  });
})();
```

---

## 四、与现有代码集成

### 4.1 React 集成方式

```tsx
// components/HeroAnimation.tsx
import { useEffect, useRef } from 'react';

export default function HeroAnimation() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    // 将上面的 IIFE 代码封装为函数调用
    const cleanup = initHeroAnimation(canvas);

    return cleanup;
  }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'absolute',
        top: 0, left: 0,
        width: '100%', height: '100%',
        opacity: 0.35,
        pointerEvents: 'none',
        zIndex: 1
      }}
    />
  );
}
```

### 4.2 Vue 集成方式

```vue
<!-- HeroAnimation.vue -->
<template>
  <canvas
    ref="canvasRef"
    class="hero-canvas"
  />
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';

const canvasRef = ref(null);
let cleanup = null;

onMounted(() => {
  cleanup = initHeroAnimation(canvasRef.value);
});

onUnmounted(() => {
  if (cleanup) cleanup();
});
</script>

<style scoped>
.hero-canvas {
  position: absolute;
  top: 0; left: 0;
  width: 100%; height: 100%;
  opacity: 0.35;
  pointer-events: none;
  z-index: 1;
}
</style>
```

---

## 五、性能优化

| 优化点 | 实现 |
|--------|------|
| Retina 适配 | `devicePixelRatio` 自动缩放，避免模糊 |
| 页面不可见暂停 | `visibilitychange` 监听，切后台停止渲染 |
| 自适应粒子数量 | 根据画布面积计算粒子数，避免小屏幕过载 |
| 无外部依赖 | 纯 Canvas API，不引入任何库 |
| 内存清理 | `beforeunload` 取消 `requestAnimationFrame` |

---

## 六、扩展建议

### 6.1 增加更多动画模式

在 `MODES` 数组中添加新模式，例如：

- `flow`: 数据流管道（模拟测序数据流动）
- `hex`: 六边形蜂窝网格（蜂巢结构，生物学隐喻）
- `orbit`: 轨道行星（多个小球围绕中心旋转）

### 6.2 用户可切换动画

在平台偏好设置中增加"首页动画"选项：

```yaml
preferences:
  hero_animation: "random"  # random | dna | particles | wave | stars | off
```

### 6.3 时间感知动画

根据当前时间自动选择动画：

```javascript
const hour = new Date().getHours();
let mode;
if (hour >= 6 && hour < 18) {
  mode = 'wave';      // 白天：活跃波形
} else if (hour >= 18 && hour < 22) {
  mode = 'particles'; // 傍晚：浮动粒子
} else {
  mode = 'stars';     // 深夜：星空
}
```

---

## 七、效果预览

刷新页面可看到 4 种动画之一随机加载：

- **DNA 模式**: 双螺旋轨道上 A/T/C/G 碱基字母浮动，强调生物信息学基因属性
- **粒子模式**: 白色粒子缓慢漂移，近距自动连线，科技感十足
- **波浪模式**: 点阵网格随正弦波起伏，如测序仪波形
- **星空模式**: 白色星点向上飘动，大星带十字光芒，呼应"星尘工作站"主题

---

*方案由 Kimi 生成，纯前端实现，零依赖，可直接集成到现有 Hero 组件。*
