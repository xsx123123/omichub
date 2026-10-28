/** Platform DTOs. Vue owns authentication and I/O; React only receives callbacks. */
export interface PlatformStatRow {
  key: string; name: string; treasures: number; digs: number; chats: number;
  updated_at: string; isGuest: boolean;
  weekTreasures: number; weekDigs: number; weekChats: number;
}
export interface PlatformLeaderboard {
  users: PlatformStatRow[]; guests: PlatformStatRow[];
  ownKey: string; nickname: string; totalTreasures: number; weekTreasures: number;
}
export interface PlatformUsageStats {
  chats: number; llmCalls: number; promptTokens: number; completionTokens: number;
  totalTokens: number; toolCalls: number; toolErrors: number; actors: number;
  tools: { name: string; label: string; count: number; errors: number; empties: number }[];
  since: string; updatedAt: string; usageRecordedChats: number;
}
export interface PlatformStatsProps {
  loadLeaderboard?: (period: 'all' | 'week') => Promise<PlatformLeaderboard>;
  loadUsage?: () => Promise<PlatformUsageStats | null>;
  updateNickname?: (nickname: string) => Promise<{ ok: boolean; message?: string }>;
}
