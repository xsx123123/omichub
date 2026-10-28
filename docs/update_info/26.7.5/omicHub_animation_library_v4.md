# OmicHub Hero & 登录页动态动画库 v4（扩展版）

> 生成日期：2026-07-05
> 目标：移除效果不明显的动画，新增更多视觉冲击力强的抽象动画，Hero 和登录页共用动画库但参数独立

---

## 一、动画库总览

### 1.1 保留的动画（效果明确、视觉冲击力强）

| 编号 | 名称 | 视觉特征 | 抽象隐喻 | 保留原因 |
|------|------|----------|----------|----------|
| A | 粒子网络 | 白点漂移 + 近距自动连线 | 神经网络、数据云 | 连线形成网络，视觉明确 |
| B | 星空粒子 | 星点向上飘 + 十字光芒 + 闪烁 | 星尘、银河 | 飘动+闪烁，动态感强 |
| C | 光晕脉冲 | 同心圆环从中心扩散 + 放射线 | 声波、心跳、能量场 | 几何扩散，节奏感强 |
| E | 轨道环 | 细圆环倾斜旋转 + 轨道白点 | 行星轨道、原子结构 | 几何旋转，科技感足 |

### 1.2 移除的动画（效果不明显）

| 编号 | 名称 | 移除原因 |
|------|------|----------|
| D | 噪点流场 | 线条太细太淡，在渐变背景上几乎不可见，用户感知弱 |
| F | 渐变流光 | 色块变化过于缓慢柔和，没有明确几何形状，像"背景脏了" |

### 1.3 新增动画（视觉冲击力更强）

| 编号 | 名称 | 视觉特征 | 抽象隐喻 |
|------|------|----------|----------|
| G | 流星雨 | 斜向光点从右上到左下划过，拖尾效果 | 流星、数据流、时间流逝 |
| H | 脉冲波纹 | 从中心向外扩散的圆形波纹，如投石入水 | 心跳、信号、能量释放 |
| I | 萤火虫群 | 随机闪烁的光点，忽明忽暗，缓慢漂移 | 夏夜、灵感、思维火花 |
| J | 矩阵雨 | 垂直下落的字符/光点列，类似数字雨 | 数据流、代码、信息瀑布 |
| K | 螺旋星云 | 螺旋臂旋转，粒子沿螺旋轨道运动 | 星系、漩涡、引力场 |
| L | 气泡上升 | 半透明圆形气泡从底部缓慢上升，大小不一 | 深海、化学反应、生命力 |

---

## 二、Hero 页动画参数（装饰性强，可稍明显）

| 参数 | 值 | 说明 |
|------|-----|------|
| opacity | 0.35-0.45 | 比登录页更明显 |
| 粒子数量 | 面积/8000 | 较密集 |
| 运动速度 | ×1.0 | 正常速度 |
| 颜色 | 蓝白色 `rgba(200,210,255,x)` | 与背景融合 |
| glow | 开启 | 粒子带光晕 |

---

## 三、登录页动画参数（氛围感，必须极淡）

| 参数 | 值 | 说明 |
|------|-----|------|
| opacity | 0.25-0.35 | 极淡，不干扰输入 |
| 粒子数量 | 面积/10000 | 较稀疏 |
| 运动速度 | ×0.6 | 更慢，不抢注意力 |
| 颜色 | 蓝白色 `rgba(200,210,255,x)` | 与背景融合 |
| glow | 开启但减弱 | 光晕范围缩小 30% |

---

## 四、完整动画引擎代码

```javascript
/**
 * OmicHub 动态背景动画引擎 v4
 * 支持 10 种动画模式，Hero 和登录页共用
 * 使用方式：initHeroAnimation(canvas) 或 initLoginAnimation(canvas)
 */

(function() {
  // ========== 导出接口 ==========
  window.initHeroAnimation = function(canvas) {
    return initAnimation(canvas, 'hero');
  };

  window.initLoginAnimation = function(canvas) {
    return initAnimation(canvas, 'login');
  };

  // ========== 核心引擎 ==========
  function initAnimation(canvas, context) {
    const ctx = canvas.getContext('2d');
    let w, h, dpr, animationId;

    // 配置参数
    const CONFIG = {
      hero: { opacity: 0.4, density: 8000, speed: 1.0, glow: true },
      login: { opacity: 0.3, density: 10000, speed: 0.6, glow: true }
    }[context] || CONFIG.hero;

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

    // 随机选择动画
    const MODES = ['particles', 'stars', 'aura', 'orbitals', 'meteor', 'ripple', 'firefly', 'matrix', 'spiral', 'bubbles'];
    const currentMode = MODES[Math.floor(Math.random() * MODES.length)];
    console.log(`[Animation:${context}] Mode:`, currentMode);

    // ========== 工具函数 ==========
    function random(min, max) { return Math.random() * (max - min) + min; }

    // ========== A. 粒子网络 ==========
    function initParticles() {
      const particles = [];
      const count = Math.floor((w * h) / CONFIG.density);
      for (let i = 0; i < count; i++) {
        particles.push({
          x: Math.random() * w, y: Math.random() * h,
          vx: (Math.random() - 0.5) * 0.4 * CONFIG.speed,
          vy: (Math.random() - 0.5) * 0.4 * CONFIG.speed,
          size: 1.5 + Math.random() * 2.5,
          opacity: 0.15 + Math.random() * 0.35,
          pulse: Math.random() * Math.PI * 2,
          pulseSpeed: (0.012 + Math.random() * 0.018) * CONFIG.speed
        });
      }
      return { particles };
    }

    function drawParticles(state) {
      ctx.clearRect(0, 0, w, h);
      const connectDist = 130;
      const maxConnections = 3;
      ctx.lineWidth = 0.6;

      for (let i = 0; i < state.particles.length; i++) {
        let connections = 0;
        for (let j = i + 1; j < state.particles.length; j++) {
          if (connections >= maxConnections) break;
          const dx = state.particles[i].x - state.particles[j].x;
          const dy = state.particles[i].y - state.particles[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < connectDist) {
            const alpha = (1 - dist / connectDist) * 0.18 * CONFIG.opacity;
            ctx.strokeStyle = `rgba(200, 210, 255, ${alpha})`;
            ctx.beginPath();
            ctx.moveTo(state.particles[i].x, state.particles[i].y);
            ctx.lineTo(state.particles[j].x, state.particles[j].y);
            ctx.stroke();
            connections++;
          }
        }
      }

      state.particles.forEach(p => {
        p.x += p.vx; p.y += p.vy; p.pulse += p.pulseSpeed;
        if (p.x < -10) p.x = w + 10; if (p.x > w + 10) p.x = -10;
        if (p.y < -10) p.y = h + 10; if (p.y > h + 10) p.y = -10;

        const alpha = p.opacity * (0.6 + 0.4 * Math.sin(p.pulse)) * CONFIG.opacity;
        const size = p.size * (0.85 + 0.15 * Math.sin(p.pulse));

        if (CONFIG.glow) {
          ctx.globalAlpha = alpha * 0.3;
          ctx.fillStyle = 'rgba(180, 190, 255, 0.5)';
          ctx.beginPath();
          ctx.arc(p.x, p.y, size * 2.5, 0, Math.PI * 2);
          ctx.fill();
        }

        ctx.globalAlpha = alpha;
        ctx.fillStyle = 'rgba(220, 225, 255, 0.95)';
        ctx.beginPath();
        ctx.arc(p.x, p.y, size, 0, Math.PI * 2);
        ctx.fill();
      });
      ctx.globalAlpha = 1;
    }

    // ========== B. 星空粒子 ==========
    function initStars() {
      const stars = [];
      const count = Math.floor((w * h) / (CONFIG.density * 0.7));
      for (let i = 0; i < count; i++) {
        const x = Math.random() * w;
        const densityBias = x / w;
        if (Math.random() > densityBias * 0.5 + 0.3) continue;
        stars.push({
          x, y: Math.random() * h,
          size: 0.8 + Math.random() * 2.2,
          speed: (0.06 + Math.random() * 0.2) * CONFIG.speed,
          twinkle: Math.random() * Math.PI * 2,
          twinkleSpeed: (0.012 + Math.random() * 0.022) * CONFIG.speed,
          driftX: (Math.random() - 0.5) * 0.1
        });
      }
      return { stars };
    }

    function drawStars(state) {
      ctx.clearRect(0, 0, w, h);
      state.stars.forEach(s => {
        s.y -= s.speed; s.x += s.driftX; s.twinkle += s.twinkleSpeed;
        if (s.y < -5) { s.y = h + 5; s.x = Math.random() * w; }
        if (s.x < 0) s.x = w; if (s.x > w) s.x = 0;

        const alpha = (0.25 + 0.45 * Math.sin(s.twinkle)) * CONFIG.opacity;

        if (CONFIG.glow && s.size > 1.0) {
          ctx.globalAlpha = alpha * 0.25;
          ctx.fillStyle = 'rgba(200, 210, 255, 0.6)';
          ctx.beginPath();
          ctx.arc(s.x, s.y, s.size * 3, 0, Math.PI * 2);
          ctx.fill();
        }

        ctx.globalAlpha = alpha;
        ctx.fillStyle = 'rgba(230, 235, 255, 0.95)';
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.size, 0, Math.PI * 2);
        ctx.fill();

        if (s.size > 1.3) {
          ctx.strokeStyle = `rgba(220, 225, 255, ${alpha * 0.35})`;
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

    // ========== C. 光晕脉冲 ==========
    function initAura() {
      const rings = [];
      for (let i = 0; i < 4; i++) {
        rings.push({
          radius: 0, maxRadius: Math.max(w, h) * 0.7,
          speed: (0.3 + Math.random() * 0.25) * CONFIG.speed,
          delay: i * 70, age: -i * 70,
          opacity: (0.2 + Math.random() * 0.15) * CONFIG.opacity
        });
      }
      const rays = [];
      for (let i = 0; i < 10; i++) {
        rays.push({
          angle: (i / 10) * Math.PI * 2 + Math.random() * 0.5,
          length: 0, maxLength: Math.max(w, h) * 0.45,
          speed: (0.5 + Math.random() * 0.35) * CONFIG.speed,
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
        ctx.strokeStyle = `rgba(200, 210, 255, ${alpha})`;
        ctx.lineWidth = 1.5 * (1 - progress * 0.5);
        ctx.stroke();
      });

      state.rays.forEach(ray => {
        ray.delay--;
        if (ray.delay > 0) return;
        ray.length += ray.speed;
        if (ray.length > ray.maxLength) {
          ray.length = 0; ray.delay = 100 + Math.random() * 150;
          ray.angle += (Math.random() - 0.5) * 0.6;
        }
        const progress = ray.length / ray.maxLength;
        const alpha = 0.12 * (1 - progress) * CONFIG.opacity;
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

    // ========== E. 轨道环 ==========
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
          rotSpeed: (Math.random() - 0.5) * 0.0025 * CONFIG.speed,
          opacity: (0.15 + Math.random() * 0.1) * CONFIG.opacity,
          dotAngle: Math.random() * Math.PI * 2,
          dotSpeed: (0.004 + Math.random() * 0.004) * CONFIG.speed
        });
      }
      return { rings };
    }

    function drawOrbitals(state) {
      ctx.clearRect(0, 0, w, h);
      state.rings.forEach(r => {
        r.rotation += r.rotSpeed; r.dotAngle += r.dotSpeed;
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

    // ========== G. 流星雨（新增）==========
    function initMeteor() {
      const meteors = [];
      const count = Math.floor((w * h) / (CONFIG.density * 1.5));
      for (let i = 0; i < count; i++) {
        meteors.push({
          x: Math.random() * w + w * 0.3,
          y: -Math.random() * h * 0.5,
          length: 30 + Math.random() * 60,
          speed: (2 + Math.random() * 3) * CONFIG.speed,
          angle: Math.PI * 0.7 + Math.random() * 0.3, // 斜向
          opacity: 0,
          maxOpacity: (0.3 + Math.random() * 0.4) * CONFIG.opacity,
          life: 0,
          maxLife: 80 + Math.random() * 60,
          delay: Math.random() * 200
        });
      }
      return { meteors };
    }

    function drawMeteor(state) {
      ctx.clearRect(0, 0, w, h);
      state.meteors.forEach(m => {
        m.delay--;
        if (m.delay > 0) return;
        m.life++;
        if (m.life > m.maxLife) {
          m.life = 0; m.delay = Math.random() * 150;
          m.x = Math.random() * w + w * 0.2;
          m.y = -Math.random() * 50;
        }

        // 生命周期：淡入 -> 最亮 -> 淡出
        let alpha = m.maxOpacity;
        if (m.life < 20) alpha = m.maxOpacity * (m.life / 20);
        else if (m.life > m.maxLife - 20) alpha = m.maxOpacity * ((m.maxLife - m.life) / 20);

        m.x += Math.cos(m.angle) * m.speed;
        m.y += Math.sin(m.angle) * m.speed;

        // 绘制拖尾
        const tailX = m.x - Math.cos(m.angle) * m.length;
        const tailY = m.y - Math.sin(m.angle) * m.length;

        const gradient = ctx.createLinearGradient(m.x, m.y, tailX, tailY);
        gradient.addColorStop(0, `rgba(220, 230, 255, ${alpha})`);
        gradient.addColorStop(0.3, `rgba(200, 210, 255, ${alpha * 0.6})`);
        gradient.addColorStop(1, `rgba(180, 190, 255, 0)`);

        ctx.strokeStyle = gradient;
        ctx.lineWidth = 1.5;
        ctx.lineCap = 'round';
        ctx.beginPath();
        ctx.moveTo(m.x, m.y);
        ctx.lineTo(tailX, tailY);
        ctx.stroke();

        // 头部光点
        ctx.fillStyle = `rgba(240, 245, 255, ${alpha})`;
        ctx.beginPath();
        ctx.arc(m.x, m.y, 1.5, 0, Math.PI * 2);
        ctx.fill();
      });
    }

    // ========== H. 脉冲波纹（新增）==========
    function initRipple() {
      const ripples = [];
      for (let i = 0; i < 5; i++) {
        ripples.push({
          x: w * 0.5 + (Math.random() - 0.5) * w * 0.6,
          y: h * 0.5 + (Math.random() - 0.5) * h * 0.6,
          radius: 0,
          maxRadius: 80 + Math.random() * 120,
          speed: (0.5 + Math.random() * 0.5) * CONFIG.speed,
          opacity: 0,
          maxOpacity: (0.25 + Math.random() * 0.15) * CONFIG.opacity,
          life: 0,
          maxLife: 120,
          delay: i * 40
        });
      }
      return { ripples };
    }

    function drawRipple(state) {
      ctx.clearRect(0, 0, w, h);
      state.ripples.forEach(r => {
        r.delay--;
        if (r.delay > 0) return;
        r.life++;
        if (r.life > r.maxLife) {
          r.life = 0; r.delay = Math.random() * 80;
          r.radius = 0;
          r.x = w * 0.5 + (Math.random() - 0.5) * w * 0.6;
          r.y = h * 0.5 + (Math.random() - 0.5) * h * 0.6;
        }

        r.radius += r.speed;
        const progress = r.life / r.maxLife;
        const alpha = r.maxOpacity * (1 - progress) * Math.sin(progress * Math.PI);

        ctx.beginPath();
        ctx.arc(r.x, r.y, r.radius, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(200, 210, 255, ${alpha})`;
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // 内圈
        if (r.radius > 20) {
          ctx.beginPath();
          ctx.arc(r.x, r.y, r.radius * 0.6, 0, Math.PI * 2);
          ctx.strokeStyle = `rgba(200, 210, 255, ${alpha * 0.5})`;
          ctx.lineWidth = 1;
          ctx.stroke();
        }
      });
    }

    // ========== I. 萤火虫群（新增）==========
    function initFirefly() {
      const fireflies = [];
      const count = Math.floor((w * h) / (CONFIG.density * 1.2));
      for (let i = 0; i < count; i++) {
        fireflies.push({
          x: Math.random() * w, y: Math.random() * h,
          vx: (Math.random() - 0.5) * 0.3 * CONFIG.speed,
          vy: (Math.random() - 0.5) * 0.3 * CONFIG.speed,
          size: 1.5 + Math.random() * 2,
          baseOpacity: (0.1 + Math.random() * 0.2) * CONFIG.opacity,
          blinkPhase: Math.random() * Math.PI * 2,
          blinkSpeed: (0.008 + Math.random() * 0.015) * CONFIG.speed,
          wanderPhase: Math.random() * Math.PI * 2
        });
      }
      return { fireflies };
    }

    function drawFirefly(state) {
      ctx.clearRect(0, 0, w, h);
      state.fireflies.forEach(f => {
        f.x += f.vx + Math.sin(f.wanderPhase) * 0.2;
        f.y += f.vy + Math.cos(f.wanderPhase) * 0.2;
        f.wanderPhase += 0.01;
        f.blinkPhase += f.blinkSpeed;

        if (f.x < -10) f.x = w + 10; if (f.x > w + 10) f.x = -10;
        if (f.y < -10) f.y = h + 10; if (f.y > h + 10) f.y = -10;

        const blink = 0.3 + 0.7 * Math.sin(f.blinkPhase); // 0.3 ~ 1.0
        const alpha = f.baseOpacity * blink;

        // Glow
        if (CONFIG.glow) {
          ctx.globalAlpha = alpha * 0.4;
          ctx.fillStyle = 'rgba(200, 220, 150, 0.4)'; // 淡黄绿，萤火虫色
          ctx.beginPath();
          ctx.arc(f.x, f.y, f.size * 4, 0, Math.PI * 2);
          ctx.fill();
        }

        ctx.globalAlpha = alpha;
        ctx.fillStyle = 'rgba(230, 240, 200, 0.95)';
        ctx.beginPath();
        ctx.arc(f.x, f.y, f.size, 0, Math.PI * 2);
        ctx.fill();
      });
      ctx.globalAlpha = 1;
    }

    // ========== J. 矩阵雨（新增）==========
    function initMatrix() {
      const columns = [];
      const colCount = Math.floor(w / 15);
      const chars = '01';
      for (let i = 0; i < colCount; i++) {
        columns.push({
          x: i * 15 + 7,
          y: Math.random() * h,
          speed: (1 + Math.random() * 2) * CONFIG.speed,
          chars: [],
          length: 5 + Math.floor(Math.random() * 15),
          opacity: (0.1 + Math.random() * 0.3) * CONFIG.opacity,
          delay: Math.random() * 100
        });
        for (let j = 0; j < columns[i].length; j++) {
          columns[i].chars.push(chars[Math.floor(Math.random() * chars.length)]);
        }
      }
      return { columns };
    }

    function drawMatrix(state) {
      ctx.clearRect(0, 0, w, h);
      ctx.font = '10px monospace';
      ctx.textAlign = 'center';

      state.columns.forEach(col => {
        col.delay--;
        if (col.delay > 0) return;
        col.y += col.speed;
        if (col.y > h + col.length * 12) {
          col.y = -col.length * 12;
          col.delay = Math.random() * 50;
          col.length = 5 + Math.floor(Math.random() * 15);
          col.chars = [];
          for (let j = 0; j < col.length; j++) col.chars.push('01'[Math.floor(Math.random() * 2)]);
        }

        for (let i = 0; i < col.chars.length; i++) {
          const y = col.y - i * 12;
          if (y < -10 || y > h + 10) continue;
          const headFade = i === 0 ? 1 : Math.max(0, 1 - i / col.length * 1.5);
          const alpha = col.opacity * headFade;
          ctx.fillStyle = `rgba(180, 200, 255, ${alpha})`;
          ctx.fillText(col.chars[i], col.x, y);
        }

        // 头部光点
        ctx.fillStyle = `rgba(220, 230, 255, ${col.opacity})`;
        ctx.beginPath();
        ctx.arc(col.x, col.y, 1.5, 0, Math.PI * 2);
        ctx.fill();
      });
    }

    // ========== K. 螺旋星云（新增）==========
    function initSpiral() {
      const arms = 3;
      const particles = [];
      const count = Math.floor((w * h) / (CONFIG.density * 0.8));
      for (let i = 0; i < count; i++) {
        const arm = i % arms;
        const t = (i / count) * Math.PI * 6;
        particles.push({
          arm, t,
          baseR: 10 + (i / count) * Math.min(w, h) * 0.35,
          speed: (0.002 + Math.random() * 0.003) * CONFIG.speed,
          size: 1 + Math.random() * 2.5,
          opacity: (0.2 + Math.random() * 0.3) * CONFIG.opacity,
          pulse: Math.random() * Math.PI * 2
        });
      }
      return { particles, cx: w * 0.5, cy: h * 0.5, rotation: 0 };
    }

    function drawSpiral(state) {
      ctx.clearRect(0, 0, w, h);
      state.rotation += 0.003 * CONFIG.speed;

      state.particles.forEach(p => {
        p.t += p.speed;
        p.pulse += 0.02;
        const r = p.baseR + Math.sin(p.t * 2) * 5;
        const angle = p.t + p.arm * (Math.PI * 2 / 3) + state.rotation;
        const x = state.cx + Math.cos(angle) * r;
        const y = state.cy + Math.sin(angle) * r;

        const alpha = p.opacity * (0.6 + 0.4 * Math.sin(p.pulse));

        if (CONFIG.glow) {
          ctx.globalAlpha = alpha * 0.3;
          ctx.fillStyle = 'rgba(180, 190, 255, 0.5)';
          ctx.beginPath();
          ctx.arc(x, y, p.size * 3, 0, Math.PI * 2);
          ctx.fill();
        }

        ctx.globalAlpha = alpha;
        ctx.fillStyle = 'rgba(220, 225, 255, 0.9)';
        ctx.beginPath();
        ctx.arc(x, y, p.size, 0, Math.PI * 2);
        ctx.fill();
      });
      ctx.globalAlpha = 1;
    }

    // ========== L. 气泡上升（新增）==========
    function initBubbles() {
      const bubbles = [];
      const count = Math.floor((w * h) / (CONFIG.density * 1.5));
      for (let i = 0; i < count; i++) {
        bubbles.push({
          x: Math.random() * w,
          y: h + Math.random() * h * 0.5,
          radius: 3 + Math.random() * 12,
          speed: (0.3 + Math.random() * 0.8) * CONFIG.speed,
          wobble: Math.random() * Math.PI * 2,
          wobbleSpeed: (0.01 + Math.random() * 0.02) * CONFIG.speed,
          opacity: (0.1 + Math.random() * 0.2) * CONFIG.opacity,
          pulse: Math.random() * Math.PI * 2
        });
      }
      return { bubbles };
    }

    function drawBubbles(state) {
      ctx.clearRect(0, 0, w, h);
      state.bubbles.forEach(b => {
        b.y -= b.speed;
        b.wobble += b.wobbleSpeed;
        b.pulse += 0.015;
        b.x += Math.sin(b.wobble) * 0.3;

        if (b.y < -b.radius * 2) {
          b.y = h + b.radius * 2;
          b.x = Math.random() * w;
        }

        const alpha = b.opacity * (0.7 + 0.3 * Math.sin(b.pulse));
        const radius = b.radius * (0.95 + 0.05 * Math.sin(b.pulse));

        // 气泡本体（半透明圆）
        ctx.globalAlpha = alpha * 0.3;
        ctx.fillStyle = 'rgba(200, 210, 255, 0.3)';
        ctx.beginPath();
        ctx.arc(b.x, b.y, radius, 0, Math.PI * 2);
        ctx.fill();

        // 气泡边框（高光）
        ctx.globalAlpha = alpha * 0.6;
        ctx.strokeStyle = 'rgba(220, 230, 255, 0.5)';
        ctx.lineWidth = 0.8;
        ctx.beginPath();
        ctx.arc(b.x, b.y, radius, 0, Math.PI * 2);
        ctx.stroke();

        // 高光点
        ctx.globalAlpha = alpha * 0.8;
        ctx.fillStyle = 'rgba(240, 245, 255, 0.7)';
        ctx.beginPath();
        ctx.arc(b.x - radius * 0.3, b.y - radius * 0.3, radius * 0.2, 0, Math.PI * 2);
        ctx.fill();
      });
      ctx.globalAlpha = 1;
    }

    // ========== 调度器 ==========
    let state = null;

    function animate() {
      switch (currentMode) {
        case 'particles': if (!state) state = initParticles(); drawParticles(state); break;
        case 'stars': if (!state) state = initStars(); drawStars(state); break;
        case 'aura': if (!state) state = initAura(); drawAura(state); break;
        case 'orbitals': if (!state) state = initOrbitals(); drawOrbitals(state); break;
        case 'meteor': if (!state) state = initMeteor(); drawMeteor(state); break;
        case 'ripple': if (!state) state = initRipple(); drawRipple(state); break;
        case 'firefly': if (!state) state = initFirefly(); drawFirefly(state); break;
        case 'matrix': if (!state) state = initMatrix(); drawMatrix(state); break;
        case 'spiral': if (!state) state = initSpiral(); drawSpiral(state); break;
        case 'bubbles': if (!state) state = initBubbles(); drawBubbles(state); break;
      }
      animationId = requestAnimationFrame(animate);
    }

    animate();

    // 性能优化
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) { if (animationId) cancelAnimationFrame(animationId); }
      else { animate(); }
    });

    // 清理函数
    return () => {
      if (animationId) cancelAnimationFrame(animationId);
      window.removeEventListener('resize', resize);
    };
  }
})();
```

---

## 五、使用方式

### 5.1 Hero 页

```html
<canvas id="hero-canvas"></canvas>
<script>
  // 页面加载后初始化
  const cleanup = initHeroAnimation(document.getElementById('hero-canvas'));
  // 页面卸载时清理
  // cleanup();
</script>
```

### 5.2 登录页

```html
<canvas id="login-bg-canvas"></canvas>
<script>
  const cleanup = initLoginAnimation(document.getElementById('login-bg-canvas'));
</script>
```

---

## 六、10 种动画效果速查

| 编号 | 名称 | 核心视觉 | 适合场景 | 明显程度 |
|------|------|----------|----------|----------|
| A | 粒子网络 | 白点 + 连线网络 | 科技感首页 | ⭐⭐⭐⭐ |
| B | 星空粒子 | 星点向上飘 + 十字光芒 | 星尘主题 | ⭐⭐⭐⭐⭐ |
| C | 光晕脉冲 | 圆环扩散 + 放射线 | 能量感 | ⭐⭐⭐⭐ |
| E | 轨道环 | 倾斜圆环旋转 + 轨道点 | 原子/行星 | ⭐⭐⭐⭐ |
| G | 流星雨 | 斜向光点 + 拖尾 | 动态感强 | ⭐⭐⭐⭐⭐ |
| H | 脉冲波纹 | 圆形波纹扩散 | 心跳/信号 | ⭐⭐⭐⭐ |
| I | 萤火虫 | 随机闪烁 + 漂移 | 温暖氛围 | ⭐⭐⭐⭐ |
| J | 矩阵雨 | 垂直字符流 | 数据/代码 | ⭐⭐⭐⭐⭐ |
| K | 螺旋星云 | 螺旋臂旋转 | 星系/引力 | ⭐⭐⭐⭐⭐ |
| L | 气泡上升 | 半透明气泡 + 高光 | 生命力 | ⭐⭐⭐⭐ |

---

## 七、移除动画说明

| 移除 | 名称 | 原因 |
|------|------|------|
| D | 噪点流场 | 线条太细（0.5px）、透明度太低（0.08），在蓝紫渐变背景上几乎不可见，用户需要仔细看才能发现，感知价值低 |
| F | 渐变流光 | 色块变化过于缓慢柔和，没有明确的几何边界，在暗色背景下像"背景脏了"而不是"有动画"，用户难以区分是设计意图还是 bug |

---

*方案由 Kimi 生成，10 种动画全部纯 Canvas 实现，零外部依赖，Hero 和登录页共用引擎但参数独立。*
