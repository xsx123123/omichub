# OmicHub 登录页金色光效修复方案（v2）

> 生成日期：2026-07-05
> 目标：修复流光边框方向、避免侵入卡片内部、降低强度、放慢速度

---

## 一、问题诊断

| 问题 | 原因 | 修复方向 |
|------|------|----------|
| 流光从左到右，不是绕边框 | `linear-gradient(90deg)` 是水平渐变 | 改用 `conic-gradient` 锥形渐变，真正绕边框旋转 |
| 流光侵入卡片内部 | 伪元素覆盖整个卡片区域 | 用 `mask` 只保留边框 2px 区域 |
| 太明显 | 透明度峰值 0.25，glow 层太强 | 整体降低 40%，峰值不超过 0.15 |
| 速度太快 | 3s 周期太急促 | 延长到 **6-8s**，更优雅 |

---

## 二、核心修复：conic-gradient + mask 实现真正绕边框流光

### 2.1 原理

```
┌─────────────────────────────┐
│  mask 镂空区域（透明）       │  ← 内部被 mask 挖空，流光不显示
│   ┌─────────────────────┐   │
│   │                     │   │
│   │    卡片内容区域      │   │
│   │                     │   │
│   └─────────────────────┘   │
│                             │
└─────────────────────────────┘
     ↑ 只有这一圈 2px 边框
       显示 conic-gradient 流光
```

### 2.2 完整 CSS（暗色模式）

```css
/* ========================================
   登录页暗色模式背景
   ======================================== */

@media (prefers-color-scheme: dark) {
  .login-page {
    background: linear-gradient(135deg, #2a3a6e 0%, #3a2a6e 50%, #2a2a5e 100%);
  }

  .login-bg-canvas {
    opacity: 0.5;
  }

  /* ========================================
     登录卡片容器
     ======================================== */

  .login-card-wrapper {
    position: relative;
    width: 420px;
    max-width: 90vw;
    /* 留出 3px 给流光边框 */
    padding: 3px;
    border-radius: 23px;
  }

  /* ========================================
     流光边框层（::before）
     ======================================== */

  .login-card-wrapper::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; bottom: 0;
    border-radius: 23px;

    /* 锥形渐变：金色从 0deg 开始，绕一圈 */
    background: conic-gradient(
      from 0deg,
      transparent 0deg,
      rgba(255, 210, 130, 0) 60deg,
      rgba(255, 210, 130, 0.08) 100deg,    /* 淡金色开始 */
      rgba(255, 220, 160, 0.14) 140deg,    /* 最亮处 */
      rgba(255, 210, 130, 0.08) 180deg,    /* 淡金色结束 */
      transparent 220deg,
      transparent 360deg
    );

    /* 关键：用 mask 只保留边框区域，内部完全镂空 */
    -webkit-mask: 
      linear-gradient(#fff 0 0) content-box, 
      linear-gradient(#fff 0 0);
    -webkit-mask-composite: xor;
    mask-composite: exclude;

    /* mask 的 content-box 配合 padding 形成边框宽度 */
    padding: 2px;
    box-sizing: border-box;

    /* 旋转动画 */
    animation: golden-orbit 8s linear infinite;

    z-index: 0;
    pointer-events: none;
  }

  /* ========================================
     呼吸光晕层（::after）
     ======================================== */

  .login-card-wrapper::after {
    content: '';
    position: absolute;
    top: -2px; left: -2px; right: -2px; bottom: -2px;
    border-radius: 25px;
    background: transparent;
    box-shadow: 
      0 0 16px rgba(255, 200, 100, 0.06),   /* 内层淡 */
      0 0 32px rgba(255, 180, 80, 0.03);     /* 外层更淡 */
    animation: golden-breathe 6s ease-in-out infinite;
    z-index: -1;
    pointer-events: none;
  }

  /* ========================================
     卡片本体
     ======================================== */

  .login-card {
    position: relative;
    z-index: 1;
    padding: 48px 40px;
    border-radius: 20px;
    background: rgba(30, 30, 60, 0.78);
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
    /* 卡片本身无边框，边框由 wrapper::before 流光承担 */
    border: 1px solid rgba(255, 255, 255, 0.06);
  }

  /* ========================================
     动画定义
     ======================================== */

  @keyframes golden-orbit {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }

  @keyframes golden-breathe {
    0%, 100% {
      box-shadow: 
        0 0 16px rgba(255, 200, 100, 0.05),
        0 0 32px rgba(255, 180, 80, 0.025);
    }
    50% {
      box-shadow: 
        0 0 20px rgba(255, 210, 120, 0.09),
        0 0 40px rgba(255, 190, 90, 0.045);
    }
  }

  /* ========================================
     文字对比度（保持修复）
     ======================================== */

  .login-title { color: #b8c4ff; }
  .login-subtitle { color: #a0a0c0; }
  .login-label { color: #e0e0f0; }
  .login-input {
    border: 1px solid rgba(255, 255, 255, 0.18);
    background: rgba(255, 255, 255, 0.07);
    color: #f0f0f8;
    border-radius: 10px;
    padding: 12px 16px;
    font-size: 14px;
    width: 100%;
    box-sizing: border-box;
  }
  .login-input::placeholder { color: #7a7a9a; }
  .login-input:focus {
    border-color: #9b7cf7;
    background: rgba(255, 255, 255, 0.1);
    outline: none;
    box-shadow: 0 0 0 3px rgba(155, 124, 247, 0.15);
  }
  .login-error { color: #ff7b7b; font-size: 12px; margin-top: 6px; }
  .login-btn-primary {
    background: linear-gradient(135deg, #5b7cf5, #9b7cf7);
    color: white;
    border: none;
    border-radius: 10px;
    padding: 12px 36px;
    font-size: 15px;
    font-weight: 500;
    cursor: pointer;
  }
  .login-btn-secondary {
    color: #c0c8ff;
    border: 1px solid rgba(192, 200, 255, 0.45);
    background: transparent;
    border-radius: 10px;
    padding: 12px 36px;
    font-size: 15px;
    cursor: pointer;
  }

  /* 猫咪 */
  .login-cat-orange { filter: brightness(0.85); }
  .login-cat-black { filter: brightness(1.15); }
}
```

---

## 三、HTML 结构（需要 wrapper）

```html
<div class="login-page">
  <canvas id="login-bg-canvas" class="login-bg-canvas"></canvas>

  <!-- 新增 wrapper 层，承载流光和光晕 -->
  <div class="login-card-wrapper">
    <div class="login-card">
      <!-- 猫咪 -->
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
</div>
```

> **关键改动**：增加了 `.login-card-wrapper` 层，流光和光晕由 wrapper 承载，卡片本体保持干净。这样流光只出现在 wrapper 的边框区域，不会侵入卡片内部。

---

## 四、参数对比（修复前后）

| 参数 | 修复前（v1） | 修复后（v2） | 说明 |
|------|-------------|-------------|------|
| 渐变类型 | `linear-gradient(90deg)` | `conic-gradient(from 0deg)` | 真正绕边框旋转 |
| 流光方向 | 从左到右 | 顺时针绕圈 | 符合"围绕边框"预期 |
| 侵入内部 | 是（伪元素覆盖全卡片） | **否**（mask 镂空内部） | 内部完全干净 |
| 流光最亮透明度 | 0.25 | **0.14** | 降低 44% |
| 流光周期 | 3s | **8s** | 更优雅缓慢 |
| 呼吸 glow 最亮 | 0.16 | **0.09** | 降低 44% |
| 呼吸周期 | 4s | **6s** | 更舒缓 |
| 边框宽度 | 2px | **2px** | 保持一致 |

---

## 五、如果浏览器不支持 mask-composite（降级方案）

部分旧版浏览器可能不支持 `mask-composite`，提供降级：

```css
/* 降级：用 border-image 实现类似效果（无法旋转，但至少有金色边框） */
@supports not (mask-composite: exclude) {
  .login-card-wrapper::before {
    /* 去掉 mask，改用 border-image */
    -webkit-mask: none;
    mask: none;
    padding: 0;
    border: 2px solid transparent;
    border-image: conic-gradient(
      from 0deg,
      rgba(255, 210, 130, 0.1),
      rgba(255, 220, 160, 0.18),
      rgba(255, 210, 130, 0.1)
    ) 1;
    animation: golden-orbit 8s linear infinite;
  }
}
```

---

## 六、更极简版（只保留呼吸光晕，无流光）

如果流光始终调不到满意，可以只保留呼吸光晕：

```css
@media (prefers-color-scheme: dark) {
  .login-card {
    position: relative;
    background: rgba(30, 30, 60, 0.78);
    backdrop-filter: blur(24px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 20px;
    padding: 48px 40px;
    /* 只有淡淡的金色外发光 */
    box-shadow: 
      0 0 0 1px rgba(255, 255, 255, 0.05),
      0 0 20px rgba(255, 200, 100, 0.06),
      0 0 40px rgba(255, 180, 80, 0.03);
    animation: golden-breathe 6s ease-in-out infinite;
  }

  @keyframes golden-breathe {
    0%, 100% {
      box-shadow: 
        0 0 0 1px rgba(255, 255, 255, 0.05),
        0 0 20px rgba(255, 200, 100, 0.05),
        0 0 40px rgba(255, 180, 80, 0.025);
    }
    50% {
      box-shadow: 
        0 0 0 1px rgba(255, 255, 255, 0.05),
        0 0 24px rgba(255, 210, 120, 0.09),
        0 0 48px rgba(255, 190, 90, 0.045);
    }
  }
}
```

---

## 七、推荐最终方案

| 场景 | 推荐 |
|------|------|
| 追求极致精致 | **v2 组合版**（conic-gradient 流光 + 呼吸光晕） |
| 稳妥不翻车 | **极简版**（只有呼吸光晕，无流光） |
| 需要兼容旧浏览器 | **极简版** 或 **border-image 降级版** |

---

*方案由 Kimi 生成，修复了流光方向、侵入内部、强度过强、速度过快的问题。*
