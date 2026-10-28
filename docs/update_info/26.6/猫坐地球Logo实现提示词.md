# 🐱🌍 登录页 Logo 组件优化提示词

## 目标
将登录页原有的「纯猫咪图标」替换为「猫咪坐在旋转地球上」的组合 Logo，适配当前紫色星空背景主题。

---

## 效果示意

```
        🐱  ← 猫咪（静态 SVG，轻微浮动动画）
       ╱ ╲
      ╱   ╲
     ┌─────┐
     │ 🌍  │  ← 地球（Lottie 无限循环旋转）
     └─────┘
   OmicHub
```

---

## 具体实现要求

### 1. 地球动画（Lottie）

- **文件**：使用已下载的 `Earth globe rotating with Seamless loop animation.json`
- **库**：`lottie-react`
- **行为**：
  - 自动播放、循环播放、无交互
  - 尺寸约 `80px ~ 100px`（根据整体比例调整）
  - 作为底层，位于猫咪下方

```bash
npm install lottie-react
```

```jsx
import Lottie from 'lottie-react';
import globeAnimation from './assets/Earth globe rotating.json';

<Lottie 
  animationData={globeAnimation}
  loop={true}
  autoplay={true}
  style={{ width: 90, height: 90 }}
/>
```

### 2. 猫咪图标（SVG）

- **来源**：沿用当前登录页已有的猫咪 SVG
- **行为**：
  - 叠加在地球 **正上方**，猫咪前爪搭在地球顶部
  - 尺寸约 `60px ~ 70px`
  - 使用 **绝对定位** 精确控制位置
  - 颜色保持当前深色系（`#1a1a2e` 或 `#2d2d44`）

### 3. 组合布局（核心）

使用一个相对定位的容器包裹两者：

```jsx
<div className="logo-container">
  {/* 底层：旋转地球 */}
  <div className="globe-wrapper">
    <Lottie animationData={globeAnimation} loop autoplay />
  </div>

  {/* 上层：猫咪 */}
  <div className="cat-wrapper">
    <CatSVG />  {/* 当前已有的猫咪 SVG */}
  </div>
</div>
```

```css
.logo-container {
  position: relative;
  width: 120px;
  height: 140px;
  display: flex;
  justify-content: center;
  align-items: flex-end;
  margin: 0 auto 16px;
}

.globe-wrapper {
  position: absolute;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 90px;
  height: 90px;
  z-index: 1;
}

.cat-wrapper {
  position: absolute;
  bottom: 55px;  /* 根据地球大小微调，让猫爪搭在球顶 */
  left: 50%;
  transform: translateX(-50%);
  width: 65px;
  height: 80px;
  z-index: 2;
}
```

### 4. 整体悬浮动画

给 `.logo-container` 添加轻微上下浮动，营造太空失重感：

```css
@keyframes float {
  0%, 100% { transform: translateY(0px); }
  50% { transform: translateY(-6px); }
}

.logo-container {
  animation: float 4s ease-in-out infinite;
}
```

### 5. 外发光效果（可选但推荐）

在地球外层添加紫色光晕，与星空背景呼应：

```css
.globe-wrapper::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 120px;
  height: 120px;
  background: radial-gradient(circle, rgba(139, 92, 246, 0.2) 0%, transparent 70%);
  border-radius: 50%;
  z-index: 0;
  pointer-events: none;
}
```

### 6. 响应式适配

```css
@media (max-width: 480px) {
  .logo-container {
    width: 100px;
    height: 115px;
  }
  .globe-wrapper {
    width: 70px;
    height: 70px;
  }
  .cat-wrapper {
    width: 50px;
    height: 65px;
    bottom: 42px;
  }
}
```

---

## 完整组件代码参考

```jsx
import React from 'react';
import Lottie from 'lottie-react';
import globeAnimation from './assets/Earth globe rotating.json';
import CatSVG from './CatSVG';  // 当前已有的猫咪 SVG 组件
import './LogoAnimation.css';

const LogoAnimation = ({ size = 'default' }) => {
  const isSmall = size === 'small';

  return (
    <div className={`logo-container ${isSmall ? 'logo-small' : ''}`}>
      <div className="globe-wrapper">
        <Lottie 
          animationData={globeAnimation}
          loop={true}
          autoplay={true}
        />
      </div>
      <div className="cat-wrapper">
        <CatSVG />
      </div>
    </div>
  );
};

export default LogoAnimation;
```

---

## 注意事项

1. **层级关系**：猫咪 `z-index` 必须高于地球，确保猫咪在地球上方
2. **定位微调**：`bottom` 和 `transform` 的值需要根据实际 SVG 的锚点微调，确保猫咪前爪「搭」在地球顶部，而不是悬空
3. **Lottie 性能**：地球动画文件较大，建议懒加载或放在登录页非首屏区域时延迟 200ms 渲染
4. **颜色统一**：如果地球 Lottie 的默认颜色（深蓝海洋 + 绿色大陆）与紫色星空背景不够协调，可以通过 Lottie 的 `rendererSettings` 或 CSS `filter: hue-rotate()` 微调色调，或保持原样（对比色也好看）
5. **替代方案**：如果 Lottie 文件过大导致加载慢，可降级为之前提供的纯 SVG 地球 + CSS 旋转方案

---

## 验收标准

- [ ] 地球持续缓慢旋转，无卡顿
- [ ] 猫咪稳定坐在地球上方，不随地球旋转而移动
- [ ] 整体有轻微上下浮动动画
- [ ] 紫色光晕与背景融合自然
- [ ] 移动端尺寸适配正常
- [ ] 登录页加载速度无明显下降
