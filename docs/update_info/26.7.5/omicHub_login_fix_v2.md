# OmicHub 登录页修复方案（动画可见性 + 文字对比度 + 背景配色）

> 生成日期：2026-07-05
> 目标：修复登录页动画太淡、文字看不清、背景配色不一致的问题

---

## 一、问题诊断（基于截图）

### 1.1 背景动画几乎看不见（图 16）

| 问题 | 原因 | 修复 |
|------|------|------|
| 动画 opacity 0.2 太淡 | 登录页比 Hero 更暗，0.2 几乎融入背景 | 提升到 **0.4-0.5** |
| 粒子颜色纯白 | 在深蓝紫背景上对比度低 | 粒子改为 **蓝白色 + glow 发光** |
| 粒子数量太少 | 面积/12000 导致稀疏 | 改为 **面积/8000** |
| 缺少连线/网络感 | 连线透明度 0.08 几乎不可见 | 提升到 **0.15-0.2** |

### 1.2 登录卡片文字看不清（图 16）

| 元素 | 现状 | 修复 |
|------|------|------|
| 标签"用户名""密码" | 浅灰 `#c0c0d8` 在玻璃卡片上发虚 | 提升到 **`#e0e0f0`** |
| 输入框 placeholder | 几乎与背景融为一体 | 提升到 **`#8a8aaa`** |
| 输入框背景 | `rgba(255,255,255,0.05)` 太透 | 改为 **`rgba(255,255,255,0.08)` + 1px 边框** |
| 副标题"欢迎登录..." | 灰色发虚 | 提升到 **`#b0b0cc`** |
| 注册按钮 | 边框色太淡，几乎看不见 | 边框提升到 **`rgba(168,180,255,0.5)`** |

### 1.3 背景配色与 Hero 不一致（图 16 vs 图 17）

| | 登录页现状 | 首页 Hero | 目标 |
|--|-----------|----------|------|
| 背景 | `#1a1a3e` → `#2d1b69` → `#1e1e3f` | `#4f6ef7` → `#7c5cfc` → `#a855f7` | 与 Hero 同色系但更淡 |
| 饱和度 | 高（深紫） | 中（蓝紫） | **降低饱和度，偏灰蓝紫** |
| 亮度 | 暗 | 亮 | **暗色模式下保持 Hero 的色相，但明度降低** |

---

## 二、修复后的 CSS

```css
/* ========================================
   登录页背景 —— 与 Hero 同色系但更淡
   ======================================== */

.login-page {
  position: relative;
  width: 100vw;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;

  /* 亮色模式：Hero 同款渐变，但饱和度降低 30% */
  background: linear-gradient(
    135deg,
    #6b7fd4 0%,      /* 蓝，比 Hero 的 #4f6ef7 更灰 */
    #8b7fd4 35%,     /* 蓝紫过渡 */
    #a080d4 65%,     /* 紫 */
    #b080c8 100%     /* 粉紫，更淡 */
  );
}

/* 暗色模式：Hero 同款色相，但明度大幅降低 */
@media (prefers-color-scheme: dark) {
  .login-page {
    background: linear-gradient(
      135deg,
      #2a3a6e 0%,      /* 深蓝，Hero 蓝色的暗版 */
      #3a2a6e 35%,     /* 蓝紫 */
      #4a2a6e 65%,     /* 紫 */
      #3a2a5e 100%     /* 深紫 */
    );
  }
}

/* ========================================
   Canvas 动画层 —— 提升可见性
   ======================================== */

.login-bg-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  opacity: 0.45;        /* 从 0.2 提升到 0.45 */
  pointer-events: none;
  z-index: 0;
}

@media (prefers-color-scheme: dark) {
  .login-bg-canvas {
    opacity: 0.5;       /* 暗色下 0.5，更明显 */
  }
}

/* ========================================
   登录卡片 —— 玻璃质感增强，文字对比度提升
   ======================================== */

.login-card {
  position: relative;
  z-index: 1;
  width: 420px;
  max-width: 90vw;
  padding: 48px 40px;
  border-radius: 20px;

  /* 亮色模式 */
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.5);
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.1), 0 0 0 1px rgba(255, 255, 255, 0.3);
}

@media (prefers-color-scheme: dark) {
  .login-card {
    /* 暗色模式：玻璃质感 */
    background: rgba(30, 30, 60, 0.75);
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
    border: 1px solid rgba(255, 255, 255, 0.12);
    box-shadow: 0 24px 80px rgba(0, 0, 0, 0.35), 0 0 0 1px rgba(255, 255, 255, 0.06);
  }
}

/* ========================================
   文字对比度修复（重点！）
   ======================================== */

.login-title {
  text-align: center;
  font-size: 32px;
  font-weight: 700;
  color: #4f6ef7;
  margin: 16px 0 8px 0;
  letter-spacing: -0.5px;
}

.login-subtitle {
  text-align: center;
  font-size: 14px;
  margin: 0 0 32px 0;
  color: #5a5a7a;       /* 亮色：加深 */
}

.login-label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: #3a3a5c;       /* 亮色：加深 */
  margin-bottom: 8px;
}

.login-label .required {
  color: #e74c3c;
}

.login-input {
  width: 100%;
  box-sizing: border-box;
  padding: 12px 16px;
  border-radius: 10px;
  font-size: 14px;
  transition: all 0.2s ease;

  /* 亮色 */
  border: 1px solid #d0d0e0;
  background: #f5f5f8;
  color: #1a1a2e;
}

.login-input::placeholder {
  color: #9a9ab0;       /* 亮色 placeholder */
}

.login-input:focus {
  border-color: #4f6ef7;
  background: #ffffff;
  outline: none;
  box-shadow: 0 0 0 3px rgba(79, 110, 247, 0.12);
}

.login-error {
  display: block;
  font-size: 12px;
  color: #e74c3c;
  margin-top: 6px;
}

/* ---------- 暗色模式文字对比度（重点修复）---------- */

@media (prefers-color-scheme: dark) {
  .login-title {
    color: #b8c4ff;       /* 从 #a8b4ff 提升亮度 */
  }

  .login-subtitle {
    color: #a0a0c0;       /* 从 #8a8aaa 提升 */
  }

  .login-label {
    color: #e0e0f0;       /* 从 #c0c0d8 大幅提升，确保可读 */
  }

  .login-input {
    border: 1px solid rgba(255, 255, 255, 0.18);  /* 边框加亮 */
    background: rgba(255, 255, 255, 0.07);         /* 背景稍亮 */
    color: #f0f0f8;                               /* 输入文字更白 */
  }

  .login-input::placeholder {
    color: #7a7a9a;       /* 从 #5a5a7a 提升，placeholder 必须可见 */
  }

  .login-input:focus {
    border-color: #9b7cf7;
    background: rgba(255, 255, 255, 0.1);
    box-shadow: 0 0 0 3px rgba(155, 124, 247, 0.2);
  }

  .login-error {
    color: #ff7b7b;       /* 错误提示更亮 */
  }
}

/* ========================================
   按钮
   ======================================== */

.login-btn-primary {
  padding: 12px 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, #4f6ef7, #7c5cfc);
  color: white;
  border: none;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.login-btn-primary:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(79, 110, 247, 0.3);
}

.login-btn-secondary {
  padding: 12px 36px;
  border-radius: 10px;
  background: transparent;
  color: #4f6ef7;
  border: 1px solid #4f6ef7;
  font-size: 15px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.login-btn-secondary:hover {
  background: rgba(79, 110, 247, 0.06);
}

@media (prefers-color-scheme: dark) {
  .login-btn-primary {
    background: linear-gradient(135deg, #5b7cf5, #9b7cf7);
    box-shadow: 0 4px 16px rgba(91, 124, 245, 0.3);
  }

  .login-btn-secondary {
    color: #c0c8ff;                         /* 从 #a8b4ff 提升 */
    border: 1px solid rgba(192, 200, 255, 0.45);  /* 边框加亮 */
  }

  .login-btn-secondary:hover {
    background: rgba(192, 200, 255, 0.1);
  }
}
```

---

## 三、修复后的 JavaScript（动画可见性提升）

```javascript
(function() {
  const canvas = document.getElementById('login-bg-canvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  let w, h, dpr, animationId;

  function resize() {
    const rect = canvas.parentElement.getBoundingClientRect();
    dpr = window.devicePixelRatio || 1;
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    w = canvas.width / dpr;
    h = canvas.height / dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  resize();
  window.addEventListener('resize', resize);

  const MODES = ['particles', 'stars', 'aura', 'noise', 'orbitals', 'gradient'];
  const currentMode = MODES[Math.floor(Math.random() * MODES.length)];
  console.log('[LoginAnimation] Mode:', currentMode);

  // ========== 模式 A: 粒子网络（修复版）==========

  function initParticles() {
    const particles = [];
    const count = Math.floor((w * h) / 8000);  // 从 12000 提升到 8000，更多粒子

    for (let i = 0; i < count; i++) {
      particles.push({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.4,
        vy: (Math.random() - 0.5) * 0.4,
        size: 1.5 + Math.random() * 3,          // 粒子稍大
        opacity: 0.2 + Math.random() * 0.4,     // 基础透明度提升
        pulse: Math.random() * Math.PI * 2,
        pulseSpeed: 0.012 + Math.random() * 0.018
      });
    }
    return { particles };
  }

  function drawParticles(state) {
    ctx.clearRect(0, 0, w, h);
    const connectDist = 130;                    // 从 100 提升到 130
    const maxConnections = 3;                     // 从 2 提升到 3

    // 绘制连线（更亮）
    ctx.lineWidth = 0.6;                        // 从 0.5 加粗
    for (let i = 0; i < state.particles.length; i++) {
      let connections = 0;
      for (let j = i + 1; j < state.particles.length; j++) {
        if (connections >= maxConnections) break;
        const dx = state.particles[i].x - state.particles[j].x;
        const dy = state.particles[i].y - state.particles[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < connectDist) {
          const alpha = (1 - dist / connectDist) * 0.18;  // 从 0.08 提升到 0.18
          ctx.strokeStyle = `rgba(200, 210, 255, ${alpha})`; // 偏蓝白，不是纯白
          ctx.beginPath();
          ctx.moveTo(state.particles[i].x, state.particles[i].y);
          ctx.lineTo(state.particles[j].x, state.particles[j].y);
          ctx.stroke();
          connections++;
        }
      }
    }

    // 绘制粒子（带 glow 效果）
    state.particles.forEach(p => {
      p.x += p.vx;
      p.y += p.vy;
      p.pulse += p.pulseSpeed;

      // 边界循环
      if (p.x < -10) p.x = w + 10;
      if (p.x > w + 10) p.x = -10;
      if (p.y < -10) p.y = h + 10;
      if (p.y > h + 10) p.y = -10;

      const alpha = p.opacity * (0.6 + 0.4 * Math.sin(p.pulse));
      const size = p.size * (0.85 + 0.15 * Math.sin(p.pulse));

      // Glow 光晕（新增）
      ctx.globalAlpha = alpha * 0.3;
      ctx.fillStyle = 'rgba(180, 190, 255, 0.5)';
      ctx.beginPath();
      ctx.arc(p.x, p.y, size * 2.5, 0, Math.PI * 2);
      ctx.fill();

      // 粒子本体
      ctx.globalAlpha = alpha;
      ctx.fillStyle = 'rgba(220, 225, 255, 0.95)';
      ctx.beginPath();
      ctx.arc(p.x, p.y, size, 0, Math.PI * 2);
      ctx.fill();
    });

    ctx.globalAlpha = 1;
  }

  // ========== 模式 B: 星空粒子（修复版）==========

  function initStars() {
    const stars = [];
    const count = Math.floor((w * h) / 5000);   // 从 6000 提升到 5000

    for (let i = 0; i < count; i++) {
      const x = Math.random() * w;
      const densityBias = x / w;
      if (Math.random() > densityBias * 0.5 + 0.3) continue;

      stars.push({
        x, y: Math.random() * h,
        size: 0.8 + Math.random() * 2.2,          // 稍大
        speed: 0.08 + Math.random() * 0.22,
        twinkle: Math.random() * Math.PI * 2,
        twinkleSpeed: 0.015 + Math.random() * 0.025,
        driftX: (Math.random() - 0.5) * 0.1
      });
    }
    return { stars };
  }

  function drawStars(state) {
    ctx.clearRect(0, 0, w, h);

    state.stars.forEach(s => {
      s.y -= s.speed;
      s.x += s.driftX;
      s.twinkle += s.twinkleSpeed;
      if (s.y < -5) { s.y = h + 5; s.x = Math.random() * w; }
      if (s.x < 0) s.x = w;
      if (s.x > w) s.x = 0;

      const alpha = 0.3 + 0.5 * Math.sin(s.twinkle);  // 从 0.2+0.4 提升

      // Glow 光晕（新增）
      if (s.size > 1.0) {
        ctx.globalAlpha = alpha * 0.25;
        ctx.fillStyle = 'rgba(200, 210, 255, 0.6)';
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.size * 3, 0, Math.PI * 2);
        ctx.fill();
      }

      // 星点本体
      ctx.globalAlpha = alpha;
      ctx.fillStyle = 'rgba(230, 235, 255, 0.95)';
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.size, 0, Math.PI * 2);
      ctx.fill();

      // 十字光芒（更亮）
      if (s.size > 1.3) {
        ctx.strokeStyle = `rgba(220, 225, 255, ${alpha * 0.35})`; // 从 0.25 提升
        ctx.lineWidth = 0.5;
        const r = s.size * 3;
        ctx.beginPath();
        ctx.moveTo(s.x - r, s.y); ctx.lineTo(s.x + r, s.y);
        ctx.moveTo(s.x, s.y - r); ctx.lineTo(s.x, s.y + r);
        ctx.stroke();
      }
    });

    ctx.globalAlpha = 1;
  }

  // ========== 模式 C: 光晕脉冲（修复版）==========

  function initAura() {
    const rings = [];
    for (let i = 0; i < 4; i++) {
      rings.push({
        radius: 0,
        maxRadius: Math.max(w, h) * 0.65,
        speed: 0.35 + Math.random() * 0.3,
        delay: i * 70,
        age: -i * 70,
        opacity: 0.25 + Math.random() * 0.2       // 从 0.2 提升
      });
    }
    const rays = [];
    for (let i = 0; i < 10; i++) {
      rays.push({
        angle: (i / 10) * Math.PI * 2 + Math.random() * 0.5,
        length: 0,
        maxLength: Math.max(w, h) * 0.45,
        speed: 0.6 + Math.random() * 0.4,
        width: 0.5 + Math.random() * 0.8,
        delay: Math.random() * 200
      });
    }
    return { rings, rays, cx: w * 0.5, cy: h * 0.5 };
  }

  function drawAura(state) {
    ctx.clearRect(0, 0, w, h);

    state.rings.forEach(r => {
      r.age++;
      if (r.age < 0) return;
      r.radius += r.speed;
      if (r.radius > r.maxRadius) { r.radius = 0; r.age = -r.delay; }

      const progress = r.radius / r.maxRadius;
      const alpha = r.opacity * (1 - progress) * (1 - progress);

      ctx.beginPath();
      ctx.arc(state.cx, state.cy, r.radius, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(200, 210, 255, ${alpha})`; // 偏蓝白
      ctx.lineWidth = 1.5 * (1 - progress * 0.5);
      ctx.stroke();
    });

    state.rays.forEach(ray => {
      ray.delay--;
      if (ray.delay > 0) return;
      ray.length += ray.speed;
      if (ray.length > ray.maxLength) {
        ray.length = 0;
        ray.delay = 100 + Math.random() * 150;
        ray.angle += (Math.random() - 0.5) * 0.6;
      }
      const progress = ray.length / ray.maxLength;
      const alpha = 0.15 * (1 - progress);  // 从 0.1 提升
      const x2 = state.cx + Math.cos(ray.angle) * ray.length;
      const y2 = state.cy + Math.sin(ray.angle) * ray.length;

      ctx.beginPath();
      ctx.moveTo(state.cx, state.cy);
      ctx.lineTo(x2, y2);
      ctx.strokeStyle = `rgba(200, 210, 255, ${alpha})`;
      ctx.lineWidth = ray.width;
      ctx.stroke();
    });
  }

  // ========== 模式 D: 噪点流场（修复版）==========

  const PERLIN = {
    p: new Uint8Array(512),
    init() {
      for (let i = 0; i < 256; i++) this.p[i] = this.p[i + 256] = Math.floor(Math.random() * 256);
    },
    fade(t) { return t * t * t * (t * (t * 6 - 15) + 10); },
    lerp(t, a, b) { return a + t * (b - a); },
    grad(hash, x, y) {
      const h = hash & 15;
      const u = h < 8 ? x : y;
      const v = h < 4 ? y : h === 12 || h === 14 ? x : 0;
      return ((h & 1) === 0 ? u : -u) + ((h & 2) === 0 ? v : -v);
    },
    noise(x, y) {
      const X = Math.floor(x) & 255, Y = Math.floor(y) & 255;
      x -= Math.floor(x); y -= Math.floor(y);
      const u = this.fade(x), v = this.fade(y);
      const A = this.p[X] + Y, B = this.p[X + 1] + Y;
      return this.lerp(v, this.lerp(u, this.grad(this.p[A], x, y), this.grad(this.p[B], x - 1, y)),
                            this.lerp(u, this.grad(this.p[A + 1], x, y - 1), this.grad(this.p[B + 1], x - 1, y - 1)));
    }
  };
  PERLIN.init();

  function initNoiseField() {
    const lines = [];
    const count = Math.floor((w * h) / 6000);     // 从 8000 提升
    for (let i = 0; i < count; i++) {
      lines.push({
        x: Math.random() * w, y: Math.random() * h,
        length: 18 + Math.random() * 35,
        speed: 0.18 + Math.random() * 0.25,
        opacity: 0.08 + Math.random() * 0.14,      // 从 0.06 提升
        width: 0.5 + Math.random() * 0.7,
        noiseScale: 0.002 + Math.random() * 0.002,
        time: Math.random() * 100
      });
    }
    return { lines, time: 0 };
  }

  function drawNoiseField(state) {
    ctx.clearRect(0, 0, w, h);
    state.time += 0.006;

    state.lines.forEach(line => {
      line.time += line.speed * 0.01;
      const angle = PERLIN.noise(line.x * line.noiseScale, line.y * line.noiseScale + state.time) * Math.PI * 2;
      const x2 = line.x + Math.cos(angle) * line.length;
      const y2 = line.y + Math.sin(angle) * line.length;

      ctx.beginPath();
      ctx.moveTo(line.x, line.y);
      ctx.lineTo(x2, y2);
      ctx.strokeStyle = `rgba(200, 210, 255, ${line.opacity})`; // 偏蓝白
      ctx.lineWidth = line.width;
      ctx.lineCap = 'round';
      ctx.stroke();

      line.x += Math.cos(angle) * 0.25;
      line.y += Math.sin(angle) * 0.25;
      if (line.x < -50) line.x = w + 50;
      if (line.x > w + 50) line.x = -50;
      if (line.y < -50) line.y = h + 50;
      if (line.y > h + 50) line.y = -50;
    });
  }

  // ========== 模式 E: 轨道环（修复版）==========

  function initOrbitals() {
    const rings = [];
    const count = 3 + Math.floor(Math.random() * 2);
    for (let i = 0; i < count; i++) {
      rings.push({
        cx: w * 0.5 + (Math.random() - 0.5) * 60,
        cy: h * 0.5 + (Math.random() - 0.5) * 50,
        radius: 55 + i * 45 + Math.random() * 30,
        tilt: (Math.random() - 0.5) * 0.4,
        rotation: Math.random() * Math.PI * 2,
        rotSpeed: (Math.random() - 0.5) * 0.0025,
        opacity: 0.18 + Math.random() * 0.12,    // 从 0.12 提升
        dotAngle: Math.random() * Math.PI * 2,
        dotSpeed: 0.005 + Math.random() * 0.005
      });
    }
    return { rings };
  }

  function drawOrbitals(state) {
    ctx.clearRect(0, 0, w, h);

    state.rings.forEach(r => {
      r.rotation += r.rotSpeed;
      r.dotAngle += r.dotSpeed;

      ctx.save();
      ctx.translate(r.cx, r.cy);
      ctx.rotate(r.rotation);
      ctx.scale(1, Math.cos(r.tilt));

      ctx.beginPath();
      ctx.arc(0, 0, r.radius, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(200, 210, 255, ${r.opacity})`;
      ctx.lineWidth = 1;
      ctx.stroke();

      const dotX = Math.cos(r.dotAngle) * r.radius;
      const dotY = Math.sin(r.dotAngle) * r.radius;
      ctx.fillStyle = 'rgba(220, 225, 255, 0.7)';
      ctx.beginPath();
      ctx.arc(dotX, dotY, 2.5, 0, Math.PI * 2);
      ctx.fill();

      ctx.restore();
    });

    ctx.fillStyle = 'rgba(220, 225, 255, 0.5)';
    ctx.beginPath();
    ctx.arc(w * 0.5, h * 0.5, 3, 0, Math.PI * 2);
    ctx.fill();
  }

  // ========== 模式 F: 渐变流光（修复版）==========

  function initGradientFlow() {
    const blobs = [];
    const colors = [
      ['rgba(120, 160, 255, 0.18)', 'rgba(120, 160, 255, 0)'],     // 更亮的蓝
      ['rgba(180, 120, 255, 0.15)', 'rgba(180, 120, 255, 0)'],     // 更亮的紫
      ['rgba(255, 140, 220, 0.12)', 'rgba(255, 140, 220, 0)']     // 更亮的粉
    ];
    for (let i = 0; i < 3; i++) {
      blobs.push({
        x: w * (0.2 + Math.random() * 0.6),
        y: h * (0.2 + Math.random() * 0.6),
        radius: 130 + Math.random() * 200,
        vx: (Math.random() - 0.5) * 0.14,
        vy: (Math.random() - 0.5) * 0.14,
        colorStart: colors[i][0],
        colorEnd: colors[i][1],
        pulse: Math.random() * Math.PI * 2,
        pulseSpeed: 0.005 + Math.random() * 0.005
      });
    }
    return { blobs };
  }

  function drawGradientFlow(state) {
    ctx.clearRect(0, 0, w, h);

    state.blobs.forEach(b => {
      b.x += b.vx; b.y += b.vy; b.pulse += b.pulseSpeed;
      if (b.x < -b.radius) b.vx = Math.abs(b.vx);
      if (b.x > w + b.radius) b.vx = -Math.abs(b.vx);
      if (b.y < -b.radius) b.vy = Math.abs(b.vy);
      if (b.y > h + b.radius) b.vy = -Math.abs(b.vy);

      const radius = b.radius * (0.9 + 0.1 * Math.sin(b.pulse));
      const gradient = ctx.createRadialGradient(b.x, b.y, 0, b.x, b.y, radius);
      gradient.addColorStop(0, b.colorStart);
      gradient.addColorStop(1, b.colorEnd);

      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, w, h);
    });
  }

  // ========== 调度器 ==========
  let state = null;

  function animate() {
    switch (currentMode) {
      case 'particles': if (!state) state = initParticles(); drawParticles(state); break;
      case 'stars': if (!state) state = initStars(); drawStars(state); break;
      case 'aura': if (!state) state = initAura(); drawAura(state); break;
      case 'noise': if (!state) state = initNoiseField(); drawNoiseField(state); break;
      case 'orbitals': if (!state) state = initOrbitals(); drawOrbitals(state); break;
      case 'gradient': if (!state) state = initGradientFlow(); drawGradientFlow(state); break;
    }
    animationId = requestAnimationFrame(animate);
  }

  animate();

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) { if (animationId) cancelAnimationFrame(animationId); }
    else { animate(); }
  });
})();
```

---

## 四、关键修复点总结

| 问题 | 修复前 | 修复后 |
|------|--------|--------|
| **动画 opacity** | 0.2（几乎看不见） | **0.45-0.5**（明显但不过分） |
| **粒子数量** | 面积/12000（稀疏） | **面积/8000**（更密集） |
| **粒子颜色** | 纯白 `rgba(255,255,255,x)` | **蓝白 `rgba(200,210,255,x)`**（与背景融合更好） |
| **粒子 glow** | 无 | **新增光晕效果**（size*2.5 的淡色圆） |
| **连线透明度** | 0.08（几乎不可见） | **0.18**（若隐若现） |
| **连线颜色** | 纯白 | **蓝白**（与背景融合） |
| **背景亮色** | 不相关 | **Hero 同款蓝紫，饱和度降低 30%** |
| **背景暗色** | `#2d1b69` 深紫 | **Hero 蓝紫色相，明度降低** `#2a3a6e` → `#3a2a6e` |
| **标签颜色** | `#c0c0d8`（发虚） | **`#e0e0f0`**（清晰可读） |
| **placeholder** | `#5a5a7a`（几乎消失） | **`#7a7a9a`**（可见） |
| **输入框边框** | `rgba(255,255,255,0.12)` | **`rgba(255,255,255,0.18)`**（更明显） |
| **注册按钮边框** | `rgba(168,180,255,0.3)` | **`rgba(192,200,255,0.45)`**（可见） |

---

## 五、效果预期

**亮色模式**：
- 背景：柔和蓝紫渐变（比 Hero 淡 30%）
- 动画：蓝白色粒子/星点，带 glow 光晕，opacity 0.45，清晰可见
- 卡片：纯白，文字深蓝/深灰，对比度充足

**暗色模式**：
- 背景：深蓝紫（Hero 同款色相，明度降低），不刺眼
- 动画：蓝白色粒子，opacity 0.5，在暗背景上更明显
- 卡片：深色玻璃，标签 `#e0e0f0` 清晰可读，placeholder `#7a7a9a` 可见

---

*方案由 Kimi 生成，修复动画可见性和文字对比度问题。*
