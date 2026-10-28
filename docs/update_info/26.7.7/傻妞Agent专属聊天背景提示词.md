# 傻妞 Agent 专属聊天背景图 —— AI 绘画提示词

> 用途：为 OmicHub 平台「傻妞」智能体生成专属聊天区背景图
> 风格：科幻全息投影 × 魔幻手机怀旧 × 生信平台科技感
> 要求：低透明度、不干扰文字阅读、适配暗色/亮色主题

---

## 一、核心提示词（Prompt）

### 中文提示词

```
一个透明的水晶质感手机娃娃，悬浮在柔和的蓝紫色全息投影光晕中，
娃娃轮廓晶莹剔透，内部有微弱的电路纹理和数字代码流动，
背景是深邃的星空渐变，点缀着稀疏的星云和光尘，
整体色调以深蓝、紫罗兰、淡青色为主，带有轻微的赛博朋克科技感，
画面风格干净简约，没有复杂杂物，
娃娃位于画面右下角偏中位置，只占画面约 25% 面积，
其余区域留白通透，适合作为聊天界面背景，
8K 超高清，矢量插画风格，半透明材质渲染，
无文字，无字幕，无人物面部细节，无复杂前景遮挡
```

### 英文提示词（推荐用于 Midjourney / DALL-E / Stable Diffusion）

```
A transparent crystal doll-shaped futuristic phone, floating in a soft blue-purple holographic projection glow, 
the doll silhouette is crystal clear and translucent with faint circuit patterns and flowing digital code inside, 
background is a deep starry sky gradient with sparse nebulae and light dust particles, 
overall color tone dominated by deep blue, violet, and light cyan with subtle cyberpunk tech aesthetic, 
clean and minimalist style, no clutter or complex objects, 
the doll is positioned at the lower-right quadrant, occupying only about 25% of the frame, 
rest of the area is transparent and breathable, suitable as a chat interface background, 
8K ultra HD, vector illustration style, semi-transparent material rendering, 
no text, no subtitles, no facial details, no complex foreground obstructions, 
subtle holographic flicker effect, soft ambient lighting, futuristic yet nostalgic vibe
```

---

## 二、参数建议

| 工具 | 推荐参数 |
|------|---------|
| **Midjourney** | `--ar 16:9 --style raw --s 50 --q 2` |
| **DALL-E 3** | 直接粘贴英文提示词，选择「 vivid 」风格 |
| **Stable Diffusion** | 推荐模型：`DreamShaper` / `RevAnimated`，CFG: 7-8，Steps: 30-40 |
| **即梦 / 可灵** | 粘贴中文提示词，选择「科幻」或「插画」风格，比例 16:9 |

---

## 三、关键设计约束说明

### 1. 透明度与可读性
- 生成后的图片需叠加 **10% - 15% 透明度**（通过 CSS `opacity: 0.12` 控制）
- 娃娃轮廓要**浅而淡**，不能干扰聊天文字阅读
- 背景区域以**纯色渐变**为主，避免复杂纹理

### 2. 位置布局
- 娃娃主体放在画面 **右下角偏中**（约 `right: 10%; bottom: 15%`）
- 聊天消息区域（左侧和中间）保持**干净无遮挡**
- 给输入框、消息气泡留出足够的视觉呼吸空间

### 3. 色彩适配
- 主色调：**深蓝 (#1a1a2e) → 紫罗兰 (#4a3b6b) → 淡青 (#64c8ff)**
- 与 OmicHub 现有星空主题 banner 的渐变色调保持一致
- 避免高饱和红色/橙色，防止与消息气泡撞色

### 4. 元素清单
- ✅ 透明水晶娃娃轮廓（魔幻手机经典造型）
- ✅ 微弱的全息光晕（蓝紫色呼吸灯效果）
- ✅ 星空/星云背景（呼应平台星空主题）
- ✅ 数字代码/电路纹理（体现 AI + 生信科技感）
- ❌ 不要人物面部（避免肖像权问题，保持抽象感）
- ❌ 不要文字/字幕（由前端 CSS 控制，图片本身纯净）
- ❌ 不要复杂前景（保持聊天区整洁）

---

## 四、后期处理建议

生成图片后，建议进行以下处理：

1. **抠图/去底**：将娃娃主体抠出，保存为 **PNG 透明底**
2. **压缩优化**：使用 `tinypng.com` 压缩至 200KB 以内，保证加载速度
3. **多尺寸导出**：
   - 桌面端：1920×1080（16:9）
   - 平板端：1200×800（3:2）
   - 移动端：750×1200（9:16，竖版适配）
4. **暗色/亮色双版本**：
   - 暗色版：加深背景，降低娃娃亮度
   - 亮色版：提亮背景，增加娃娃边缘发光

---

## 五、前端使用方式（React + Arco Design）

```tsx
// 在傻妞 Agent 专属聊天容器组件中使用
const ShaonuChatBackground = () => {
  return (
    <div className="shaonu-chat-container">
      <div className="shaonu-hologram-bg" />
      <div className="shaonu-chat-messages">
        {/* 消息列表 */}
      </div>
    </div>
  );
};
```

```css
.shaonu-chat-container {
  position: relative;
  background: var(--color-bg-2);
  overflow: hidden;
}

.shaonu-hologram-bg {
  position: absolute;
  right: 8%;
  bottom: 10%;
  width: 300px;
  height: 400px;
  background-image: url('/assets/shaonu-hologram.png');
  background-size: contain;
  background-repeat: no-repeat;
  background-position: center;
  opacity: 0.12;          /* 极低透明度，不抢戏 */
  pointer-events: none;   /* 不阻挡点击 */
  z-index: 0;
  animation: hologram-breathe 4s ease-in-out infinite;
}

.shaonu-chat-messages {
  position: relative;
  z-index: 1;
}

/* 全息呼吸灯动画 */
@keyframes hologram-breathe {
  0%, 100% { opacity: 0.10; filter: brightness(1) drop-shadow(0 0 10px rgba(100,200,255,0.1)); }
  50% { opacity: 0.14; filter: brightness(1.3) drop-shadow(0 0 20px rgba(150,100,255,0.2)); }
}
```

---

## 六、参考灵感图

以下图片为风格参考，非直接使用：

- 透明水晶娃娃 + 全息投影效果
- 蓝紫色科幻光晕 + 星空背景
- 干净通透的聊天界面适配感

---

> 🪄 **彩蛋文案建议**：
> 当用户首次进入傻妞聊天窗口时，可以弹出一段悬浮文字：
> *"华人牌2060款手机傻妞为您服务，请输入开机密码。"*
> 3 秒后淡入全息投影背景，仪式感拉满。

---

*生成时间：2026-07-07*
*适用平台：OmicHub 星尘工作站 —— 傻妞 Agent 专属*
