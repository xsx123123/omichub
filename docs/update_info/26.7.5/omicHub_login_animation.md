# OmicHub 登录页动态背景动画方案（6 种模式）

> 生成日期：2026-07-05
> 目标：将 6 种抽象 Hero 动画应用到登录页背景，提升质感且不干扰表单输入

---

## 一、设计原则

登录页与首页 Hero 的动画需求不同：

| 维度 | 首页 Hero | 登录页 |
|------|----------|--------|
| 动画强度 | 中等（装饰性） | 弱（氛围感） |
| 透明度 | 0.35-0.4 | 0.15-0.25（更淡） |
| 运动速度 | 正常 | 更慢（不分散注意力） |
| 颜色 | 白色为主 | 暗色模式下偏蓝紫微光 |
| 与内容关系 | 偏右，不遮挡文字 | 全幅，但表单卡片在上层 |

**核心原则**：动画是" wallpaper "（壁纸），不是主角。用户应该能忽略它，但关掉它会觉得页面变"死"了。

---

## 二、HTML 结构

```html
<div class="login-page">
  <!-- 动态背景层：最底层 -->
  <canvas id="login-bg-canvas" class="login-bg-canvas"></canvas>

  <!-- 登录卡片：中层，z-index 高于 canvas -->
  <div class="login-card">
    <!-- 猫咪装饰 -->
    <div class="login-cats">
      <img src="cat-orange.png" class="login-cat-orange" alt="" />
      <img src="cat-black.png" class="login-cat-black" alt="" />
    </div>

    <!-- 标题 -->
    <h1 class="login-title">OmicHub</h1>
    <p class="login-subtitle">欢迎登录多组学分析平台</p>

    <!-- 表单 -->
    <form class="login-form">
      <div class="login-field">
        <label class="login-label">用户名 <span class="required">*</span></label>
        <input class="login-input" type="text" placeholder="请输入用户名" />
        <span class="login-error">请输入用户名</span>
      </div>
      <div class="login-field">
        <label class="login-label">密码 <span class="required">*</span></label>
        <input class="login-input" type="password" placeholder="请输入密码" />
      </div>
      <div class="login-actions">
        <button class="login-btn-primary" type="submit">登录</button>
        <button class="login-btn-secondary" type="button">注册</button>
      </div>
    </form>
  </div>
</div>
```

---

## 三、CSS（含亮色/暗色模式）

```css
/* ========================================
   登录页容器
   ======================================== */

.login-page {
  position: relative;
  width: 100vw;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;

  /* 亮色：柔和蓝紫渐变 */
  background: linear-gradient(135deg, #5b7cf5 0%, #7c5cfc 50%, #a855f7 100%);
}

/* ========================================
   Canvas 动态背景层
   ======================================== */

.login-bg-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  opacity: 0.2;           /* 比 Hero 更淡 */
  pointer-events: none;   /* 不阻挡鼠标 */
  z-index: 0;
}

/* ========================================
   登录卡片
   ======================================== */

.login-card {
  position: relative;
  z-index: 1;             /* 高于 canvas */
  width: 420px;
  max-width: 90vw;
  padding: 48px 40px;
  background: #ffffff;
  border-radius: 20px;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.12), 0 0 0 1px rgba(255, 255, 255, 0.1);
}

/* ========================================
   猫咪装饰
   ======================================== */

.login-cats {
  position: absolute;
  top: -40px;
  left: 0;
  right: 0;
  display: flex;
  justify-content: space-between;
  padding: 0 30px;
  pointer-events: none;
}

.login-cat-orange {
  width: 80px;
  height: auto;
}

.login-cat-black {
  width: 60px;
  height: auto;
}

/* ========================================
   标题与表单
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
  color: #6a6a8a;
  margin: 0 0 32px 0;
}

.login-field {
  margin-bottom: 20px;
}

.login-label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: #3a3a5c;
  margin-bottom: 8px;
}

.login-label .required {
  color: #e74c3c;
}

.login-input {
  width: 100%;
  box-sizing: border-box;
  padding: 12px 16px;
  border: 1px solid #d8d8e8;
  border-radius: 10px;
  background: #fafafa;
  font-size: 14px;
  color: #1a1a2e;
  transition: all 0.2s ease;
}

.login-input::placeholder {
  color: #a0a0b8;
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

.login-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 32px;
}

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

/* ========================================
   暗色模式
   ======================================== */

@media (prefers-color-scheme: dark) {
  .login-page {
    background: linear-gradient(135deg, #0f0f2e 0%, #1a1040 50%, #0f0f2e 100%);
  }

  .login-bg-canvas {
    opacity: 0.25;  /* 暗色下动画稍明显 */
  }

  .login-card {
    background: rgba(25, 25, 50, 0.88);
    backdrop-filter: blur(24px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: 0 24px 80px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(255, 255, 255, 0.05);
  }

  .login-cat-orange {
    filter: brightness(0.85);
  }

  .login-cat-black {
    filter: brightness(1.15);  /* 黑猫在暗色下容易消失 */
  }

  .login-title {
    color: #a8b4ff;
  }

  .login-subtitle {
    color: #8a8aaa;
  }

  .login-label {
    color: #c0c0d8;
  }

  .login-input {
    border-color: rgba(255, 255, 255, 0.12);
    background: rgba(255, 255, 255, 0.05);
    color: #e8e8f0;
  }

  .login-input::placeholder {
    color: #5a5a7a;
  }

  .login-input:focus {
    border-color: #7c5cfc;
    background: rgba(255, 255, 255, 0.08);
    box-shadow: 0 0 0 3px rgba(124, 92, 252, 0.18);
  }

  .login-error {
    color: #ff6b6b;
  }

  .login-btn-primary {
    background: linear-gradient(135deg, #5b7cf5, #9b7cf7);
    box-shadow: 0 4px 16px rgba(91, 124, 245, 0.25);
  }

  .login-btn-secondary {
    color: #a8b4ff;
    border-color: rgba(168, 180, 255, 0.3);
  }

  .login-btn-secondary:hover {
    background: rgba(168, 180, 255, 0.08);
  }
}
```

---

## 四、JavaScript（6 种动画完整代码）

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

  // ========== 随机选择动画模式 ==========
  const MODES = ['particles', 'stars', 'aura', 'noise', 'orbitals', 'gradient'];
  const currentMode = MODES[Math.floor(Math.random() * MODES.length)];
  console.log('[LoginAnimation] Mode:', currentMode);

  // ========== 模式 A: 粒子网络 ==========
  function initParticles() {
    const particles = [];
    const count = Math.floor((w * h) / 12000);  // 比 Hero 更少
    for (let i = 0; i < count; i++) {
      particles.push({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.3,
        size: 1 + Math.random() * 2,
        opacity: 0.1 + Math.random() * 0.25,
        pulse: Math.random() * Math.PI * 2,
        pulseSpeed: 0.01 + Math.random() * 0.015
      });
    }
    return { particles };
  }

  function drawParticles(state) {
    ctx.clearRect(0, 0, w, h);
    const connectDist = 100;
    const maxConnections = 2;

    ctx.lineWidth = 0.5;
    for (let i = 0; i < state.particles.length; i++) {
      let connections = 0;
      for (let j = i + 1; j < state.particles.length; j++) {
        if (connections >= maxConnections) break;
        const dx = state.particles[i].x - state.particles[j].x;
        const dy = state.particles[i].y - state.particles[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < connectDist) {
          const alpha = (1 - dist / connectDist) * 0.08;
          ctx.strokeStyle = `rgba(255, 255, 255, ${alpha})`;
          ctx.beginPath();
          ctx.moveTo(state.particles[i].x, state.particles[i].y);
          ctx.lineTo(state.particles[j].x, state.particles[j].y);
          ctx.stroke();
          connections++;
        }
      }
    }

    state.particles.forEach(p => {
      p.x += p.vx;
      p.y += p.vy;
      p.pulse += p.pulseSpeed;
      if (p.x < -10) p.x = w + 10;
      if (p.x > w + 10) p.x = -10;
      if (p.y < -10) p.y = h + 10;
      if (p.y > h + 10) p.y = -10;

      const alpha = p.opacity * (0.6 + 0.4 * Math.sin(p.pulse));
      ctx.globalAlpha = alpha;
      ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size * (0.85 + 0.15 * Math.sin(p.pulse)), 0, Math.PI * 2);
      ctx.fill();
    });
    ctx.globalAlpha = 1;
  }

  // ========== 模式 B: 星空粒子 ==========
  function initStars() {
    const stars = [];
    const count = Math.floor((w * h) / 6000);
    for (let i = 0; i < count; i++) {
      const x = Math.random() * w;
      const densityBias = x / w;
      if (Math.random() > densityBias * 0.5 + 0.3) continue;

      stars.push({
        x, y: Math.random() * h,
        size: 0.5 + Math.random() * 1.8,
        speed: 0.06 + Math.random() * 0.2,
        twinkle: Math.random() * Math.PI * 2,
        twinkleSpeed: 0.012 + Math.random() * 0.02,
        driftX: (Math.random() - 0.5) * 0.08
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

      const alpha = 0.2 + 0.4 * Math.sin(s.twinkle);
      ctx.globalAlpha = alpha;
      ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.size, 0, Math.PI * 2);
      ctx.fill();

      if (s.size > 1.2) {
        ctx.strokeStyle = `rgba(255, 255, 255, ${alpha * 0.25})`;
        ctx.lineWidth = 0.4;
        const r = s.size * 2.5;
        ctx.beginPath();
        ctx.moveTo(s.x - r, s.y); ctx.lineTo(s.x + r, s.y);
        ctx.moveTo(s.x, s.y - r); ctx.lineTo(s.x, s.y + r);
        ctx.stroke();
      }
    });
    ctx.globalAlpha = 1;
  }

  // ========== 模式 C: 光晕脉冲 ==========
  function initAura() {
    const rings = [];
    for (let i = 0; i < 4; i++) {
      rings.push({
        radius: 0,
        maxRadius: Math.max(w, h) * 0.7,
        speed: 0.3 + Math.random() * 0.25,
        delay: i * 80,
        age: -i * 80,
        opacity: 0.2 + Math.random() * 0.15
      });
    }
    const rays = [];
    for (let i = 0; i < 8; i++) {
      rays.push({
        angle: (i / 8) * Math.PI * 2 + Math.random() * 0.4,
        length: 0,
        maxLength: Math.max(w, h) * 0.4,
        speed: 0.5 + Math.random() * 0.3,
        width: 0.4 + Math.random() * 0.6,
        delay: Math.random() * 250
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
      ctx.strokeStyle = `rgba(255, 255, 255, ${alpha})`;
      ctx.lineWidth = 1.2 * (1 - progress * 0.5);
      ctx.stroke();
    });

    state.rays.forEach(ray => {
      ray.delay--;
      if (ray.delay > 0) return;
      ray.length += ray.speed;
      if (ray.length > ray.maxLength) {
        ray.length = 0;
        ray.delay = 120 + Math.random() * 180;
        ray.angle += (Math.random() - 0.5) * 0.6;
      }
      const progress = ray.length / ray.maxLength;
      const alpha = 0.1 * (1 - progress);
      const x2 = state.cx + Math.cos(ray.angle) * ray.length;
      const y2 = state.cy + Math.sin(ray.angle) * ray.length;

      ctx.beginPath();
      ctx.moveTo(state.cx, state.cy);
      ctx.lineTo(x2, y2);
      ctx.strokeStyle = `rgba(255, 255, 255, ${alpha})`;
      ctx.lineWidth = ray.width;
      ctx.stroke();
    });
  }

  // ========== 模式 D: 噪点流场 ==========
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
    const count = Math.floor((w * h) / 8000);
    for (let i = 0; i < count; i++) {
      lines.push({
        x: Math.random() * w, y: Math.random() * h,
        length: 15 + Math.random() * 30,
        speed: 0.15 + Math.random() * 0.2,
        opacity: 0.06 + Math.random() * 0.1,
        width: 0.4 + Math.random() * 0.6,
        noiseScale: 0.002 + Math.random() * 0.002,
        time: Math.random() * 100
      });
    }
    return { lines, time: 0 };
  }

  function drawNoiseField(state) {
    ctx.clearRect(0, 0, w, h);
    state.time += 0.005;

    state.lines.forEach(line => {
      line.time += line.speed * 0.008;
      const angle = PERLIN.noise(line.x * line.noiseScale, line.y * line.noiseScale + state.time) * Math.PI * 2;
      const x2 = line.x + Math.cos(angle) * line.length;
      const y2 = line.y + Math.sin(angle) * line.length;

      ctx.beginPath();
      ctx.moveTo(line.x, line.y);
      ctx.lineTo(x2, y2);
      ctx.strokeStyle = `rgba(255, 255, 255, ${line.opacity})`;
      ctx.lineWidth = line.width;
      ctx.lineCap = 'round';
      ctx.stroke();

      line.x += Math.cos(angle) * 0.2;
      line.y += Math.sin(angle) * 0.2;
      if (line.x < -50) line.x = w + 50;
      if (line.x > w + 50) line.x = -50;
      if (line.y < -50) line.y = h + 50;
      if (line.y > h + 50) line.y = -50;
    });
  }

  // ========== 模式 E: 轨道环 ==========
  function initOrbitals() {
    const rings = [];
    const count = 3 + Math.floor(Math.random() * 2);
    for (let i = 0; i < count; i++) {
      rings.push({
        cx: w * 0.5 + (Math.random() - 0.5) * 50,
        cy: h * 0.5 + (Math.random() - 0.5) * 40,
        radius: 50 + i * 40 + Math.random() * 25,
        tilt: (Math.random() - 0.5) * 0.35,
        rotation: Math.random() * Math.PI * 2,
        rotSpeed: (Math.random() - 0.5) * 0.002,
        opacity: 0.12 + Math.random() * 0.08,
        dotAngle: Math.random() * Math.PI * 2,
        dotSpeed: 0.004 + Math.random() * 0.004
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
      ctx.strokeStyle = `rgba(255, 255, 255, ${r.opacity})`;
      ctx.lineWidth = 1;
      ctx.stroke();

      const dotX = Math.cos(r.dotAngle) * r.radius;
      const dotY = Math.sin(r.dotAngle) * r.radius;
      ctx.fillStyle = 'rgba(255, 255, 255, 0.6)';
      ctx.beginPath();
      ctx.arc(dotX, dotY, 2, 0, Math.PI * 2);
      ctx.fill();

      ctx.restore();
    });

    ctx.fillStyle = 'rgba(255, 255, 255, 0.4)';
    ctx.beginPath();
    ctx.arc(w * 0.5, h * 0.5, 2.5, 0, Math.PI * 2);
    ctx.fill();
  }

  // ========== 模式 F: 渐变流光 ==========
  function initGradientFlow() {
    const blobs = [];
    const colors = [
      ['rgba(100, 150, 255, 0.12)', 'rgba(100, 150, 255, 0)'],
      ['rgba(180, 100, 255, 0.1)', 'rgba(180, 100, 255, 0)'],
      ['rgba(255, 120, 200, 0.08)', 'rgba(255, 120, 200, 0)']
    ];
    for (let i = 0; i < 3; i++) {
      blobs.push({
        x: w * (0.2 + Math.random() * 0.6),
        y: h * (0.2 + Math.random() * 0.6),
        radius: 120 + Math.random() * 180,
        vx: (Math.random() - 0.5) * 0.12,
        vy: (Math.random() - 0.5) * 0.12,
        colorStart: colors[i][0],
        colorEnd: colors[i][1],
        pulse: Math.random() * Math.PI * 2,
        pulseSpeed: 0.004 + Math.random() * 0.004
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
      case 'particles':
        if (!state) state = initParticles();
        drawParticles(state);
        break;
      case 'stars':
        if (!state) state = initStars();
        drawStars(state);
        break;
      case 'aura':
        if (!state) state = initAura();
        drawAura(state);
        break;
      case 'noise':
        if (!state) state = initNoiseField();
        drawNoiseField(state);
        break;
      case 'orbitals':
        if (!state) state = initOrbitals();
        drawOrbitals(state);
        break;
      case 'gradient':
        if (!state) state = initGradientFlow();
        drawGradientFlow(state);
        break;
    }
    animationId = requestAnimationFrame(animate);
  }

  animate();

  // 性能优化
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

## 五、登录页 vs 首页动画差异

| 参数 | 登录页 | 首页 Hero | 原因 |
|------|--------|-----------|------|
| 透明度 | 0.2-0.25 | 0.35-0.4 | 登录页需要更淡，不干扰输入 |
| 粒子数量 | 面积/12000 | 面积/9000 | 更少粒子，更简洁 |
| 连线透明度 | 0.08 | 0.12 | 更若隐若现 |
| 运动速度 | ×0.6 | ×1.0 | 更慢，不抢注意力 |
| 最大连线数 | 2 | 3 | 更稀疏 |
| 色块透明度 | 0.08-0.12 | 0.1-0.15 | 更淡的流光 |

---

## 六、实施检查清单

- [ ] 登录页添加 `<canvas id="login-bg-canvas">` 作为最底层
- [ ] 登录卡片 `position: relative; z-index: 1` 确保在 canvas 之上
- [ ] Canvas `opacity: 0.2` + `pointer-events: none`
- [ ] 暗色模式下 canvas `opacity: 0.25`（稍明显，因为背景更暗）
- [ ] 6 种动画随机加载，每次打开登录页不同
- [ ] 页面不可见时暂停动画（`visibilitychange`）
- [ ] 暗光环境下测试：屏幕亮度最低，确保表单文字清晰可读

---

*方案由 Kimi 生成，6 种抽象动画全部纯 Canvas 实现，零外部依赖。*
