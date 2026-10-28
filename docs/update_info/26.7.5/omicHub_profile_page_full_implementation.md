# OmicHub 个人中心完整重构方案（Phase 1-4 全量前端实现）

> 生成日期：2026-07-05
> 目标：一次性完成个人中心全部模块的前端实现，后端未就绪的模块使用 Mock 数据占位

---

## 一、整体页面架构

```
┌─ 个人中心 ───────────────────────────────────────────────────────┐
│                                                                  │
│  ┌─ 用户信息卡片 ───────────────────────────────────────────┐  │
│  │  [头像]  root  [admin]                                   │  │
│  │  ID: cb79a200...  ·  创建于 2026/07/05                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ 使用概览（Phase 2）─────────────────────────────────────┐  │
│  │  [128 次]  [3 个]  [45.2 GB]  [RNA-seq ↗]               │  │
│  │  本月分析  运行中    存储      最近任务                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ 账户信息 ───────────────────────────────────────────────┐  │
│  │  用户名    root                                         │  │
│  │  昵称      未设置                    [编辑]              │  │
│  │  邮箱      1099651528@qq.com         [已验证]           │  │
│  │  角色      管理员                                       │  │
│  │  状态      正常                                         │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ 安全与登录（Phase 1+3）─────────────────────────────────┐  │
│  │  最后登录    2026/07/05 01:44:37                        │  │
│  │  登录 IP     192.168.1.100  (武汉, 湖北)                │  │
│  │  登录设备    Chrome 126 / macOS                         │  │
│  │                                                         │  │
│  │  [查看登录历史 →]  [管理活跃会话 →]                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ 常用流程（Phase 2）────────────────────────────────────┐  │
│  │  🧬 RNA-seq 差异表达    🧪 ATAC-seq 染色质可及性        │  │
│  │  🔬 单细胞分析          🌐 文献检索                     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ 最近任务（Phase 2）────────────────────────────────────┐  │
│  │  ● RNA-seq 差异表达分析          运行中    2h 前         │  │
│  │  ✓ 基因组注释                    成功     1d 前         │  │
│  │  ✗ ChIP-seq 峰值分析             失败     2d 前         │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ 平台偏好（Phase 4）────────────────────────────────────┐  │
│  │  默认首页    [分析中心 ▼]                               │  │
│  │  主题        [跟随系统 ○ 亮色 ○ 深色]                     │  │
│  │  语言        [简体中文 ▼]                                 │  │
│  │  通知        [邮件 ●]  [站内信 ●]  [Webhook ○]          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ 数据与隐私（Phase 3+4）─────────────────────────────────┐  │
│  │  [导出分析历史]  [下载个人数据]  [删除账户]               │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  [前往账号设置 →]                                                │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 二、页面容器与宽度统一

```css
/* 个人中心容器 —— 与系统设置完全一致的宽度策略 */
.profile-page-wrapper {
  width: 100%;
  padding: 24px 32px;
  display: flex;
  justify-content: center;
}

.profile-page-container {
  width: 100%;
  max-width: 720px;           /* 与系统设置表单区对齐 */
}

/* 卡片统一风格 */
.profile-card {
  width: 100%;
  border: 1px solid var(--kimi-color-border);
  border-radius: 12px;
  padding: 24px;
  background: var(--kimi-color-surface-raised);
  margin-bottom: 16px;
  transition: border-color var(--t-fast) var(--ease-out);
}
.profile-card:hover {
  border-color: var(--kimi-color-text-primary);
}

.profile-card-title {
  font-size: 15px;
  font-weight: 500;
  color: var(--kimi-color-text-primary);
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 响应式 */
@media (max-width: 768px) {
  .profile-page-wrapper {
    padding: 16px 20px;
  }
  .profile-card {
    padding: 16px;
  }
}
```

---

## 三、Phase 1：基础信息 + 安全与登录

### 3.1 用户信息卡片

```tsx
// UserInfoCard.tsx
function UserInfoCard({ user }) {
  return (
    <ProfileCard>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <div style={{
          width: 64, height: 64, borderRadius: '50%',
          background: 'var(--kimi-color-surface-muted)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 28, flexShrink: 0
        }}>
          {user.avatar || '👤'}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
            <span style={{ fontSize: 18, fontWeight: 500, color: 'var(--kimi-color-text-primary)' }}>
              {user.username}
            </span>
            <RoleBadge role={user.role} />
          </div>
          <div style={{ fontSize: 12, color: 'var(--kimi-color-text-quaternary)' }}>
            ID: {user.id} · 创建于 {formatDate(user.created_at)}
          </div>
        </div>
        <Button type="text" size="small" icon={<EditOutlined />}>
          修改头像
        </Button>
      </div>
    </ProfileCard>
  );
}

function RoleBadge({ role }) {
  const colorMap = {
    admin: { bg: 'color-mix(in srgb, var(--kimi-chart-2) 12%, transparent)', text: 'var(--kimi-chart-2)' },
    user: { bg: 'color-mix(in srgb, var(--kimi-chart-1) 12%, transparent)', text: 'var(--kimi-chart-1)' },
    guest: { bg: 'color-mix(in srgb, var(--kimi-color-text-quaternary) 12%, transparent)', text: 'var(--kimi-color-text-quaternary)' }
  };
  const c = colorMap[role] || colorMap.user;
  return (
    <span style={{
      fontSize: 11, fontWeight: 500, padding: '2px 8px', borderRadius: 4,
      background: c.bg, color: c.text, textTransform: 'capitalize'
    }}>
      {role === 'admin' ? '管理员' : role === 'user' ? '用户' : '访客'}
    </span>
  );
}
```

### 3.2 账户信息卡片

```tsx
// AccountInfoCard.tsx
function AccountInfoCard({ user }) {
  return (
    <ProfileCard title="账户信息">
      <InfoRow label="用户名" value={user.username} />
      <InfoRow label="昵称" value={user.nickname || '未设置'} action="编辑" />
      <InfoRow label="邮箱" value={user.email} tag="已验证" />
      <InfoRow label="角色" value={user.role === 'admin' ? '管理员' : '用户'} />
      <InfoRow label="状态" value={<StatusTag status={user.status} />} />
    </ProfileCard>
  );
}

function StatusTag({ status }) {
  const map = {
    active: { text: '正常', color: 'var(--kimi-color-positive)' },
    inactive: { text: '停用', color: 'var(--kimi-color-warning)' },
    banned: { text: '封禁', color: 'var(--kimi-color-danger)' }
  };
  const s = map[status] || map.active;
  return (
    <span style={{
      fontSize: 12, fontWeight: 500, padding: '2px 8px', borderRadius: 4,
      background: `color-mix(in srgb, ${s.color} 12%, transparent)`,
      color: s.color
    }}>
      {s.text}
    </span>
  );
}
```

### 3.3 安全与登录卡片（含 IP 展示）

```tsx
// SecurityCard.tsx
function SecurityCard({ session }) {
  return (
    <ProfileCard title="安全与登录">
      <InfoRow label="最后登录" value={formatTime(session.last_active_at)} />
      <InfoRow 
        label="登录 IP" 
        value={
          <span>
            <code style={{ fontFamily: 'var(--kimi-font-mono)', fontSize: 13 }}>
              {session.ip_address}
            </code>
            {session.location && (
              <span style={{ fontSize: 12, color: 'var(--kimi-color-text-tertiary)', marginLeft: 8 }}>
                {session.location}
              </span>
            )}
          </span>
        } 
      />
      <InfoRow label="登录设备" value={session.user_agent} />

      <div style={{ display: 'flex', gap: 12, marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--kimi-color-border)' }}>
        <Button type="text" size="small" onClick={() => openModal('login-history')}>
          查看登录历史 →
        </Button>
        <Button type="text" size="small" onClick={() => openModal('active-sessions')}>
          管理活跃会话 →
        </Button>
      </div>
    </ProfileCard>
  );
}
```

---

## 四、Phase 2：使用概览 + 最近任务 + 常用流程

### 4.1 使用概览卡片（4 个 KPI）

```tsx
// UsageOverviewCard.tsx
function UsageOverviewCard({ stats }) {
  return (
    <ProfileCard title="使用概览" icon="📊">
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
        <KpiCard 
          label="本月分析" 
          value={stats.analysis_count} 
          unit="次" 
          color="var(--kimi-chart-1)"
        />
        <KpiCard 
          label="运行中" 
          value={stats.running_tasks} 
          unit="个" 
          color="var(--kimi-chart-3)"
          pulse={stats.running_tasks > 0}
        />
        <KpiCard 
          label="存储用量" 
          value={stats.storage_used} 
          unit="GB" 
          total={stats.storage_total}
          color="var(--kimi-chart-4)"
        />
        <KpiCard 
          label="最近任务" 
          value={stats.recent_task_name} 
          unit="" 
          color="var(--kimi-color-text-secondary)"
          isText={true}
        />
      </div>
    </ProfileCard>
  );
}

function KpiCard({ label, value, unit, color, total, pulse, isText }) {
  return (
    <div style={{
      textAlign: 'center', padding: 16, borderRadius: 10,
      background: 'var(--kimi-color-surface)',
      border: '1px solid var(--kimi-color-border)'
    }}>
      <div style={{
        fontSize: isText ? 14 : 24, fontWeight: 500, color: color || 'var(--kimi-color-text-primary)',
        animation: pulse ? 'pulse 2s infinite' : 'none'
      }}>
        {value}
      </div>
      <div style={{ fontSize: 12, color: 'var(--kimi-color-text-tertiary)', marginTop: 4 }}>
        {label} {unit && `(${unit})`}
      </div>
      {total && (
        <div style={{ marginTop: 8 }}>
          <div style={{
            height: 4, borderRadius: 2, background: 'var(--kimi-color-surface-muted)',
            overflow: 'hidden'
          }}>
            <div style={{
              width: `${Math.min((value / total) * 100, 100)}%`,
              height: '100%', background: color, borderRadius: 2,
              transition: 'width 0.5s ease'
            }} />
          </div>
          <div style={{ fontSize: 11, color: 'var(--kimi-color-text-quaternary)', marginTop: 4 }}>
            {value} / {total} GB
          </div>
        </div>
      )}
    </div>
  );
}
```

### 4.2 最近任务列表

```tsx
// RecentTasksCard.tsx
function RecentTasksCard({ tasks }) {
  return (
    <ProfileCard title="最近任务" icon="📝" action={{ text: '查看全部', link: '/tasks' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
        {tasks.map((task, i) => (
          <TaskRow key={task.id} task={task} isLast={i === tasks.length - 1} />
        ))}
        {tasks.length === 0 && (
          <EmptyState message="暂无任务，去分析中心开始你的第一个分析吧" />
        )}
      </div>
    </ProfileCard>
  );
}

function TaskRow({ task, isLast }) {
  const statusMap = {
    running: { dot: 'var(--kimi-chart-3)', text: '运行中', icon: '●' },
    success: { dot: 'var(--kimi-color-positive)', text: '成功', icon: '✓' },
    failed: { dot: 'var(--kimi-color-danger)', text: '失败', icon: '✗' },
    pending: { dot: 'var(--kimi-color-warning)', text: '排队中', icon: '◐' }
  };
  const s = statusMap[task.status] || statusMap.pending;

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 12,
      padding: '12px 0', borderBottom: isLast ? 'none' : '1px solid var(--kimi-color-border)'
    }}>
      <span style={{ fontSize: 12, color: s.dot, width: 16, textAlign: 'center' }}>
        {s.icon}
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: 14, color: 'var(--kimi-color-text-primary)',
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'
        }}>
          {task.name}
        </div>
        <div style={{ fontSize: 12, color: 'var(--kimi-color-text-quaternary)', marginTop: 2 }}>
          {task.flow_name} · {formatRelativeTime(task.created_at)}
        </div>
      </div>
      <span style={{
        fontSize: 11, fontWeight: 500, padding: '2px 8px', borderRadius: 4,
        background: `color-mix(in srgb, ${s.dot} 10%, transparent)`,
        color: s.dot, flexShrink: 0
      }}>
        {s.text}
      </span>
    </div>
  );
}
```

### 4.3 常用流程快捷入口

```tsx
// FavoriteFlowsCard.tsx
function FavoriteFlowsCard({ flows }) {
  return (
    <ProfileCard title="常用流程" icon="⚡" action={{ text: '去分析中心', link: '/analysis' }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: 8 }}>
        {flows.map(flow => (
          <FlowChip key={flow.id} flow={flow} />
        ))}
      </div>
    </ProfileCard>
  );
}

function FlowChip({ flow }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px',
      borderRadius: 8, background: 'var(--kimi-color-surface)',
      border: '1px solid var(--kimi-color-border)',
      cursor: 'pointer', transition: 'all var(--t-fast)',
      fontSize: 13, color: 'var(--kimi-color-text-primary)'
    }} className="flow-chip">
      <span style={{ fontSize: 16 }}>{flow.icon}</span>
      <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
        {flow.name}
      </span>
    </div>
  );
}
```

---

## 五、Phase 3：安全增强（登录历史 + 活跃会话 + 审计日志 + API 密钥）

### 5.1 登录历史弹窗/抽屉

```tsx
// LoginHistoryModal.tsx
function LoginHistoryModal({ visible, onClose }) {
  const { data: history } = useSWR('/api/user/login-history', { fallbackData: MOCK_LOGIN_HISTORY });

  return (
    <Drawer title="登录历史" width={520} open={visible} onClose={onClose}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
        {history.map((record, i) => (
          <div key={i} style={{
            display: 'flex', alignItems: 'flex-start', gap: 12,
            padding: '12px 0', borderBottom: i === history.length - 1 ? 'none' : '1px solid var(--kimi-color-border)'
          }}>
            <div style={{
              width: 32, height: 32, borderRadius: 8,
              background: 'var(--kimi-color-surface-muted)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 14, flexShrink: 0
            }}>
              {record.device_type === 'desktop' ? '💻' : record.device_type === 'mobile' ? '📱' : '🌐'}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 14, color: 'var(--kimi-color-text-primary)' }}>
                {record.browser} / {record.os}
              </div>
              <div style={{ fontSize: 12, color: 'var(--kimi-color-text-tertiary)', marginTop: 2 }}>
                <code style={{ fontFamily: 'var(--kimi-font-mono)' }}>{record.ip_address}</code>
                {record.location && ` · ${record.location}`}
              </div>
              <div style={{ fontSize: 12, color: 'var(--kimi-color-text-quaternary)', marginTop: 2 }}>
                {formatTime(record.login_at)}
                {record.is_current && (
                  <span style={{
                    marginLeft: 8, fontSize: 11, color: 'var(--kimi-color-positive)',
                    background: 'color-mix(in srgb, var(--kimi-color-positive) 10%, transparent)',
                    padding: '1px 6px', borderRadius: 4
                  }}>
                    当前会话
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </Drawer>
  );
}

// Mock 数据（后端未就绪时使用）
const MOCK_LOGIN_HISTORY = [
  { login_at: '2026-07-05T01:44:37+08:00', ip_address: '192.168.1.100', location: '武汉, 湖北', browser: 'Chrome 126', os: 'macOS', device_type: 'desktop', is_current: true },
  { login_at: '2026-07-04T18:22:15+08:00', ip_address: '192.168.1.100', location: '武汉, 湖北', browser: 'Chrome 126', os: 'macOS', device_type: 'desktop', is_current: false },
  { login_at: '2026-07-03T09:15:00+08:00', ip_address: '10.0.0.55', location: '北京', browser: 'Safari', os: 'iOS', device_type: 'mobile', is_current: false },
];
```

### 5.2 活跃会话管理

```tsx
// ActiveSessionsModal.tsx
function ActiveSessionsModal({ visible, onClose }) {
  const { data: sessions } = useSWR('/api/user/sessions', { fallbackData: MOCK_SESSIONS });

  const handleRevoke = async (sessionId) => {
    await api.delete(`/api/user/sessions/${sessionId}`);
    mutate('/api/user/sessions');
    message.success('已踢出该设备');
  };

  return (
    <Drawer title="活跃会话" width={520} open={visible} onClose={onClose}>
      <p style={{ fontSize: 13, color: 'var(--kimi-color-text-secondary)', marginBottom: 16 }}>
        以下设备当前已登录你的账号。如发现有异常设备，请立即踢出。
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {sessions.map(s => (
          <div key={s.id} style={{
            padding: 16, borderRadius: 10, border: '1px solid var(--kimi-color-border)',
            background: s.is_current ? 'color-mix(in srgb, var(--kimi-chart-1) 3%, transparent)' : 'var(--kimi-color-surface)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 20 }}>{s.device_type === 'desktop' ? '💻' : '📱'}</span>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 500 }}>
                    {s.browser} / {s.os}
                    {s.is_current && <span style={{ marginLeft: 8, fontSize: 12, color: 'var(--kimi-chart-1)' }}>(当前设备)</span>}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--kimi-color-text-tertiary)', marginTop: 2 }}>
                    {s.ip_address} · {s.location} · 登录于 {formatTime(s.login_at)}
                  </div>
                </div>
              </div>
              {!s.is_current && (
                <Button size="small" danger onClick={() => handleRevoke(s.id)}>
                  踢出
                </Button>
              )}
            </div>
          </div>
        ))}
      </div>
    </Drawer>
  );
}

const MOCK_SESSIONS = [
  { id: 'sess_1', browser: 'Chrome 126', os: 'macOS', ip_address: '192.168.1.100', location: '武汉, 湖北', login_at: '2026-07-05T01:44:37+08:00', device_type: 'desktop', is_current: true },
  { id: 'sess_2', browser: 'Safari', os: 'iOS', ip_address: '10.0.0.55', location: '北京', login_at: '2026-07-03T09:15:00+08:00', device_type: 'mobile', is_current: false },
];
```

### 5.3 审计日志卡片

```tsx
// AuditLogCard.tsx
function AuditLogCard() {
  const { data: logs } = useSWR('/api/user/audit-logs', { fallbackData: MOCK_AUDIT_LOGS });

  return (
    <ProfileCard title="操作审计" icon="🔒" action={{ text: '查看全部', link: '/audit-logs' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
        {logs.slice(0, 5).map((log, i) => (
          <div key={i} style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '10px 0', borderBottom: i === 4 ? 'none' : '1px solid var(--kimi-color-border)'
          }}>
            <span style={{
              fontSize: 11, fontWeight: 500, padding: '2px 6px', borderRadius: 4,
              background: AUDIT_TYPE_COLORS[log.type]?.bg || 'var(--kimi-color-surface-muted)',
              color: AUDIT_TYPE_COLORS[log.type]?.text || 'var(--kimi-color-text-secondary)',
              flexShrink: 0
            }}>
              {log.type_label}
            </span>
            <span style={{ flex: 1, fontSize: 13, color: 'var(--kimi-color-text-primary)' }}>
              {log.description}
            </span>
            <span style={{ fontSize: 12, color: 'var(--kimi-color-text-quaternary)', flexShrink: 0 }}>
              {formatRelativeTime(log.created_at)}
            </span>
          </div>
        ))}
      </div>
    </ProfileCard>
  );
}

const AUDIT_TYPE_COLORS = {
  password: { bg: 'color-mix(in srgb, var(--kimi-color-warning) 10%, transparent)', text: 'var(--kimi-color-warning)' },
  email: { bg: 'color-mix(in srgb, var(--kimi-chart-1) 10%, transparent)', text: 'var(--kimi-chart-1)' },
  delete: { bg: 'color-mix(in srgb, var(--kimi-color-danger) 10%, transparent)', text: 'var(--kimi-color-danger)' },
  security: { bg: 'color-mix(in srgb, var(--kimi-chart-2) 10%, transparent)', text: 'var(--kimi-chart-2)' }
};

const MOCK_AUDIT_LOGS = [
  { type: 'password', type_label: '密码', description: '修改了登录密码', created_at: '2026-07-01T10:00:00+08:00' },
  { type: 'email', type_label: '邮箱', description: '绑定邮箱 1099651528@qq.com', created_at: '2026-06-28T15:30:00+08:00' },
  { type: 'security', type_label: '安全', description: '开启二次验证 (TOTP)', created_at: '2026-06-25T09:00:00+08:00' },
  { type: 'delete', type_label: '删除', description: '删除了任务 #1283', created_at: '2026-06-20T14:00:00+08:00' },
  { type: 'password', type_label: '密码', description: '重置了 API 密钥', created_at: '2026-06-15T11:00:00+08:00' },
];
```

### 5.4 API 密钥管理

```tsx
// ApiKeysCard.tsx
function ApiKeysCard() {
  const [keys, setKeys] = useState(MOCK_API_KEYS);
  const [showCreate, setShowCreate] = useState(false);
  const [newKey, setNewKey] = useState(null);

  const handleCreate = async () => {
    // 调用后端创建 API Key
    const res = await api.post('/api/user/api-keys', { name: '新密钥' });
    setNewKey(res.data.key);  // 只展示一次
    setKeys([...keys, res.data]);
    setShowCreate(false);
  };

  const handleRevoke = async (keyId) => {
    await api.delete(`/api/user/api-keys/${keyId}`);
    setKeys(keys.filter(k => k.id !== keyId));
    message.success('密钥已撤销');
  };

  return (
    <ProfileCard title="API 密钥" icon="🔑" action={{ text: '新建密钥', onClick: () => setShowCreate(true) }}>
      <p style={{ fontSize: 12, color: 'var(--kimi-color-text-tertiary)', marginBottom: 12 }}>
        用于通过 API 访问 OmicHub 服务。请妥善保管，不要泄露给他人。
      </p>

      {newKey && (
        <div style={{
          padding: 12, borderRadius: 8, background: 'color-mix(in srgb, var(--kimi-chart-3) 8%, transparent)',
          border: '1px solid color-mix(in srgb, var(--kimi-chart-3) 20%, transparent)',
          marginBottom: 12
        }}>
          <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--kimi-chart-3)', marginBottom: 4 }}>
            ⚠️ 请立即复制保存，此密钥只显示一次
          </div>
          <code style={{
            display: 'block', padding: 8, borderRadius: 4,
            background: 'var(--kimi-color-surface)', fontFamily: 'var(--kimi-font-mono)',
            fontSize: 12, wordBreak: 'break-all'
          }}>
            {newKey}
          </code>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
        {keys.map((key, i) => (
          <div key={key.id} style={{
            display: 'flex', alignItems: 'center', gap: 12,
            padding: '12px 0', borderBottom: i === keys.length - 1 ? 'none' : '1px solid var(--kimi-color-border)'
          }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 14, color: 'var(--kimi-color-text-primary)' }}>{key.name}</div>
              <div style={{ fontSize: 12, color: 'var(--kimi-color-text-quaternary)', marginTop: 2 }}>
                {key.masked_key} · 创建于 {formatDate(key.created_at)}
                {key.last_used_at && ` · 最后使用 ${formatRelativeTime(key.last_used_at)}`}
              </div>
            </div>
            <Button type="text" size="small" danger onClick={() => handleRevoke(key.id)}>
              撤销
            </Button>
          </div>
        ))}
        {keys.length === 0 && <EmptyState message="暂无 API 密钥" />}
      </div>
    </ProfileCard>
  );
}

const MOCK_API_KEYS = [
  { id: 'key_1', name: '开发测试', masked_key: 'oh-****-3f2a', created_at: '2026-06-01', last_used_at: '2026-07-04T12:00:00' },
];
```

---

## 六、Phase 4：偏好设置

### 6.1 平台偏好卡片

```tsx
// PreferencesCard.tsx
function PreferencesCard() {
  const [prefs, setPrefs] = useState({
    default_page: 'analysis',
    theme: 'system',
    language: 'zh-CN',
    notifications: { email: true, in_app: true, webhook: false }
  });

  const handleSave = async () => {
    await api.put('/api/user/preferences', prefs);
    message.success('偏好已保存');
  };

  return (
    <ProfileCard title="平台偏好" icon="⚙️">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

        {/* 默认首页 */}
        <div className="pref-row">
          <label className="pref-label">默认首页</label>
          <select 
            className="pref-select"
            value={prefs.default_page}
            onChange={e => setPrefs({...prefs, default_page: e.target.value})}
          >
            <option value="dashboard">控制台</option>
            <option value="analysis">分析中心</option>
            <option value="tasks">任务中心</option>
            <option value="data">数据管理</option>
          </select>
        </div>

        {/* 主题 */}
        <div className="pref-row">
          <label className="pref-label">主题</label>
          <div className="segmented-control">
            {['system', 'light', 'dark'].map(opt => (
              <button
                key={opt}
                className={`segment-btn ${prefs.theme === opt ? 'active' : ''}`}
                onClick={() => setPrefs({...prefs, theme: opt})}
              >
                {opt === 'system' ? '跟随系统' : opt === 'light' ? '亮色' : '深色'}
              </button>
            ))}
          </div>
        </div>

        {/* 语言 */}
        <div className="pref-row">
          <label className="pref-label">语言</label>
          <select 
            className="pref-select"
            value={prefs.language}
            onChange={e => setPrefs({...prefs, language: e.target.value})}
          >
            <option value="zh-CN">简体中文</option>
            <option value="en-US">English</option>
          </select>
        </div>

        {/* 通知偏好 */}
        <div className="pref-row">
          <label className="pref-label">通知渠道</label>
          <div style={{ display: 'flex', gap: 16 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontSize: 14 }}>
              <input 
                type="checkbox" 
                checked={prefs.notifications.email}
                onChange={e => setPrefs({...prefs, notifications: {...prefs.notifications, email: e.target.checked}})}
              />
              邮件通知
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontSize: 14 }}>
              <input 
                type="checkbox" 
                checked={prefs.notifications.in_app}
                onChange={e => setPrefs({...prefs, notifications: {...prefs.notifications, in_app: e.target.checked}})}
              />
              站内消息
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontSize: 14 }}>
              <input 
                type="checkbox" 
                checked={prefs.notifications.webhook}
                onChange={e => setPrefs({...prefs, notifications: {...prefs.notifications, webhook: e.target.checked}})}
              />
              Webhook
            </label>
          </div>
        </div>

        <Button type="primary" size="small" onClick={handleSave} style={{ alignSelf: 'flex-start', marginTop: 8 }}>
          保存偏好
        </Button>
      </div>
    </ProfileCard>
  );
}
```

### 6.2 数据与隐私卡片

```tsx
// DataPrivacyCard.tsx
function DataPrivacyCard() {
  const [exporting, setExporting] = useState(false);

  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await api.get('/api/user/export', { responseType: 'blob' });
      downloadBlob(res.data, `omicHub_data_${formatDate(new Date())}.json`);
      message.success('数据导出成功');
    } finally {
      setExporting(false);
    }
  };

  const handleDelete = () => {
    Modal.confirm({
      title: '确认删除账户？',
      content: '此操作不可撤销，将删除你的所有数据、任务和历史记录。',
      okText: '确认删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        await api.delete('/api/user/account');
        message.success('账户已删除');
        logout();
      }
    });
  };

  return (
    <ProfileCard title="数据与隐私" icon="🛡️">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 0', borderBottom: '1px solid var(--kimi-color-border)' }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 500 }}>导出分析历史</div>
            <div style={{ fontSize: 12, color: 'var(--kimi-color-text-tertiary)', marginTop: 2 }}>下载包含所有任务、设置和数据的 JSON 文件</div>
          </div>
          <Button size="small" onClick={handleExport} loading={exporting}>
            导出
          </Button>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 0', borderBottom: '1px solid var(--kimi-color-border)' }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 500 }}>下载个人数据</div>
            <div style={{ fontSize: 12, color: 'var(--kimi-color-text-tertiary)', marginTop: 2 }}>符合 GDPR 要求的数据副本</div>
          </div>
          <Button size="small" onClick={handleExport}>
            下载
          </Button>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 0' }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--kimi-color-danger)' }}>删除账户</div>
            <div style={{ fontSize: 12, color: 'var(--kimi-color-text-tertiary)', marginTop: 2 }}>永久删除账户和所有关联数据</div>
          </div>
          <Button size="small" danger onClick={handleDelete}>
            删除
          </Button>
        </div>
      </div>
    </ProfileCard>
  );
}
```

---

## 七、通用组件汇总

### 7.1 ProfileCard

```tsx
function ProfileCard({ title, icon, action, children }) {
  return (
    <div className="profile-card">
      <div className="profile-card-title">
        {icon && <span style={{ fontSize: 16 }}>{icon}</span>}
        {title}
        {action && (
          <Button 
            type="text" 
            size="small" 
            style={{ marginLeft: 'auto', fontSize: 12 }}
            onClick={action.onClick || (() => router.push(action.link))}
          >
            {action.text} →
          </Button>
        )}
      </div>
      {children}
    </div>
  );
}
```

### 7.2 InfoRow

```tsx
function InfoRow({ label, value, action, tag }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 12,
      padding: '10px 0', borderBottom: '1px solid var(--kimi-color-border)'
    }}>
      <span style={{ width: 80, fontSize: 13, color: 'var(--kimi-color-text-secondary)', flexShrink: 0 }}>
        {label}
      </span>
      <span style={{ flex: 1, fontSize: 14, color: 'var(--kimi-color-text-primary)', wordBreak: 'break-all' }}>
        {value}
      </span>
      {tag && (
        <span style={{
          fontSize: 11, padding: '2px 8px', borderRadius: 4,
          background: 'color-mix(in srgb, var(--kimi-color-positive) 10%, transparent)',
          color: 'var(--kimi-color-positive)', fontWeight: 500, flexShrink: 0
        }}>
          {tag}
        </span>
      )}
      {action && (
        <Button type="text" size="small" style={{ marginLeft: 'auto', flexShrink: 0 }}>
          {action}
        </Button>
      )}
    </div>
  );
}
```

### 7.3 EmptyState

```tsx
function EmptyState({ message }) {
  return (
    <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--kimi-color-text-quaternary)', fontSize: 13 }}>
      {message}
    </div>
  );
}
```

---

## 八、完整页面组装

```tsx
// ProfilePage.tsx
export default function ProfilePage() {
  const { data: user } = useSWR('/api/user/profile', { fallbackData: MOCK_USER });
  const { data: session } = useSWR('/api/user/session', { fallbackData: MOCK_SESSION });
  const { data: stats } = useSWR('/api/user/stats', { fallbackData: MOCK_STATS });

  const [showLoginHistory, setShowLoginHistory] = useState(false);
  const [showActiveSessions, setShowActiveSessions] = useState(false);

  return (
    <div className="profile-page-wrapper">
      <div className="profile-page-container">
        <h1 style={{ fontSize: 20, fontWeight: 500, marginBottom: 24, color: 'var(--kimi-color-text-primary)' }}>
          个人中心
        </h1>

        {/* Phase 1 */}
        <UserInfoCard user={user} />

        {/* Phase 2 */}
        <UsageOverviewCard stats={stats} />
        <FavoriteFlowsCard flows={MOCK_FLOWS} />
        <RecentTasksCard tasks={stats.recent_tasks || []} />

        {/* Phase 1 */}
        <AccountInfoCard user={user} />
        <SecurityCard 
          session={session} 
          onShowHistory={() => setShowLoginHistory(true)}
          onShowSessions={() => setShowActiveSessions(true)}
        />

        {/* Phase 3 */}
        <AuditLogCard />
        <ApiKeysCard />

        {/* Phase 4 */}
        <PreferencesCard />
        <DataPrivacyCard />

        {/* 操作入口 */}
        <div style={{ marginTop: 24, textAlign: 'center' }}>
          <Button type="primary" size="large" onClick={() => router.push('/settings')}>
            前往账号设置
          </Button>
          <p style={{ fontSize: 12, color: 'var(--kimi-color-text-quaternary)', marginTop: 8 }}>
            可在「账号设置」中修改用户名、邮箱与密码
          </p>
        </div>
      </div>

      {/* Modals */}
      <LoginHistoryModal visible={showLoginHistory} onClose={() => setShowLoginHistory(false)} />
      <ActiveSessionsModal visible={showActiveSessions} onClose={() => setShowActiveSessions(false)} />
    </div>
  );
}

// ========== Mock 数据 ==========
const MOCK_USER = {
  id: 'cb79a200-b2ca-441f-9a42-d3417fbfa89d',
  username: 'root',
  nickname: '',
  email: '1099651528@qq.com',
  role: 'admin',
  status: 'active',
  avatar: '',
  created_at: '2026-07-05T01:04:59+08:00'
};

const MOCK_SESSION = {
  last_active_at: '2026-07-05T01:44:37+08:00',
  ip_address: '192.168.1.100',
  location: '武汉, 湖北',
  user_agent: 'Chrome 126 / macOS'
};

const MOCK_STATS = {
  analysis_count: 128,
  running_tasks: 3,
  storage_used: 45.2,
  storage_total: 100,
  recent_task_name: 'RNA-seq',
  recent_tasks: [
    { id: 't1', name: 'RNA-seq 差异表达分析', flow_name: 'RNA-seq', status: 'running', created_at: '2026-07-04T23:44:37+08:00' },
    { id: 't2', name: '基因组注释', flow_name: 'Genome Annotation', status: 'success', created_at: '2026-07-03T18:00:00+08:00' },
    { id: 't3', name: 'ChIP-seq 峰值分析', flow_name: 'ChIP-seq', status: 'failed', created_at: '2026-07-02T14:00:00+08:00' },
  ]
};

const MOCK_FLOWS = [
  { id: 'rna', name: 'RNA-seq', icon: '🧬' },
  { id: 'atac', name: 'ATAC-seq', icon: '🧪' },
  { id: 'scrna', name: '单细胞', icon: '🔬' },
  { id: 'lit', name: '文献检索', icon: '🌐' },
];
```

---

## 九、后端接口清单（按优先级）

| 接口 | 方法 | 用途 | 优先级 | 备注 |
|------|------|------|--------|------|
| `/api/user/profile` | GET | 获取用户信息 | P0 | 已有 |
| `/api/user/session` | GET | 当前会话（IP/UA/地点） | P0 | 需扩展 UserSession 表 |
| `/api/user/stats` | GET | 使用统计 + 最近任务 | P1 | 新增 |
| `/api/user/login-history` | GET | 登录历史列表 | P1 | 新增 |
| `/api/user/sessions` | GET | 活跃会话列表 | P1 | 新增 |
| `/api/user/sessions/:id` | DELETE | 踢出指定会话 | P1 | 新增 |
| `/api/user/audit-logs` | GET | 审计日志 | P2 | 新增 |
| `/api/user/api-keys` | GET/POST/DELETE | API 密钥管理 | P2 | 新增 |
| `/api/user/preferences` | GET/PUT | 偏好设置 | P2 | 新增 |
| `/api/user/export` | GET | 数据导出 | P3 | 新增 |
| `/api/user/account` | DELETE | 删除账户 | P3 | 新增 |

**后端未就绪时的处理：** 所有 `useSWR` 调用均提供 `fallbackData`（Mock 数据），前端可独立开发、独立演示。

---

## 十、设计 Token 速查

| 元素 | Token | 值 |
|------|-------|-----|
| 卡片背景 | `var(--kimi-color-surface-raised)` | 浅色模式 `#fff`，深色模式 `#1e1e1e` |
| 卡片边框 | `var(--kimi-color-border)` | 浅色 `#e5e5e5`，深色 `#333` |
| 主文字 | `var(--kimi-color-text-primary)` | 浅色 `#000`，深色 `#fff` |
| 次文字 | `var(--kimi-color-text-secondary)` | 灰色 |
| 三级文字 | `var(--kimi-color-text-tertiary)` | 更浅灰 |
| 四级文字 | `var(--kimi-color-text-quaternary)` | 最浅灰 |
| 成功色 | `var(--kimi-color-positive)` | 绿 |
| 危险色 | `var(--kimi-color-danger)` | 红 |
| 警告色 | `var(--kimi-color-warning)` | 橙黄 |
| 图表色 | `var(--kimi-chart-1~4)` | 蓝/红/绿/紫 |
| 等宽字体 | `var(--kimi-font-mono)` | 代码字体 |
| 无衬线字体 | `var(--kimi-font-sans)` | UI 字体 |
| 微动效 | `var(--t-fast)` | 约 150ms |
| 缓动 | `var(--ease-out)` | ease-out |

---

*方案由 Kimi 生成，包含全部 4 个 Phase 的前端实现代码，后端未就绪的模块均已提供 Mock 数据，可直接交付开发。*
