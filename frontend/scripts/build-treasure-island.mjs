/** Build only the original display island with its own locked dependencies. */
import { spawnSync } from 'node:child_process';
import { access, cp, mkdtemp, rm, symlink } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import { tmpdir } from 'node:os';
const frontend = fileURLToPath(new URL('..', import.meta.url));
const source = resolve(frontend, '../pipelines/Treasure-Seeking_Mouse');
const vite = resolve(source, 'node_modules/vite/bin/vite.js');
try { await access(vite); }
catch { throw new Error('Missing Treasure Mouse build dependencies. Install the child repository dependencies with its frozen lockfile before building the frontend.'); }
const output = resolve(frontend, 'public/treasure-island');
let staging;
try {
  let buildRoot = source;
  try { await access(resolve(source, 'vite.island.config.ts')); }
  catch {
    // Reuse the frozen adapter with today's shared components. Platform-owned
    // presentation overrides live here, rather than changing the child archive.
    const archive = resolve(source, 'archive/island');
    await access(resolve(archive, 'vite.island.config.ts'));
    staging = await mkdtemp(resolve(tmpdir(), 'cygnusx-treasure-island-'));
    await cp(resolve(source, 'src'), resolve(staging, 'src'), { recursive: true });
    await cp(resolve(source, 'shared'), resolve(staging, 'shared'), { recursive: true });
    await cp(resolve(archive, 'src/island'), resolve(staging, 'src/island'), { recursive: true });
    for (const name of ['FullPresentation.tsx', 'index.tsx']) {
      await cp(resolve(frontend, 'treasure-island', name), resolve(staging, 'src/island', name));
    }
    for (const name of ['vite.island.config.ts', 'tsconfig.island.json']) {
      await cp(resolve(archive, name), resolve(staging, name));
    }
    await cp(resolve(source, 'tsconfig.json'), resolve(staging, 'tsconfig.json'));
    await symlink(resolve(source, 'node_modules'), resolve(staging, 'node_modules'), 'dir');
    buildRoot = staging;
  }
  for (const [entry, args] of [
    [resolve(source, 'node_modules/typescript/bin/tsc'), ['--noEmit', '-p', 'tsconfig.island.json']],
    [vite, ['build', '--config', 'vite.island.config.ts', '--outDir', output]],
  ]) {
    const result = spawnSync(process.execPath, [entry, ...args], { cwd: buildRoot, stdio: 'inherit' });
    if (result.error) throw result.error;
    if (result.status !== 0) throw new Error(`Treasure Island build failed (exit ${result.status})`);
  }
} finally {
  if (staging) await rm(staging, { recursive: true, force: true });
}
// The diagnostic inventory contains local filesystem paths; never serve it publicly.
await rm(resolve(output, 'module-inventory.json'), { force: true });
