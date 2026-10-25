declare module '@treasure-island-poc' {
  export type TreasureIslandProps = import('../../src/types/treasureIsland').TreasureIslandProps;
  export type TreasureIslandHandle = import('../../src/types/treasureIsland').TreasureIslandHandle;
  export function mount(container: HTMLElement, props: TreasureIslandProps): TreasureIslandHandle;
}
