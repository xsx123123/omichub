/** Verify the actual runtime image against an isolated OpenAI SSE fixture.
 * node scripts/poc/treasure-runtime-usage.mjs cygnusx-treasure-mouse-chat:<sha>
 * No production account, database, model key or data volume is used.
 */
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { once } from 'node:events';
import { spawn, spawnSync } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { mkdir, writeFile } from 'node:fs/promises';

const image = process.argv[2];
if (!image) throw new Error('Pass the runtime image with its immutable SHA tag');
const output = 'evidence/treasure-platform-stats';
await mkdir(output, { recursive: true });
const upstream = createServer(async (req, res) => {
  let body = '';
  for await (const chunk of req) body += chunk;
  assert.equal(JSON.parse(body).stream_options.include_usage, true);
  res.setHeader('Content-Type', 'text/event-stream');
  res.end([
    { choices: [{ delta: { content: 'Isolated fixture answer.' } }] },
    { choices: [], usage: { prompt_tokens: 37, completion_tokens: 5, total_tokens: 42 } },
  ].map(frame => `data: ${JSON.stringify(frame)}\n\n`).join('') + 'data: [DONE]\n\n');
});
upstream.listen(0, '127.0.0.1'); await once(upstream, 'listening');
const reserve = createServer(); reserve.listen(0, '127.0.0.1'); await once(reserve, 'listening');
const port = reserve.address().port;
await new Promise(resolve => reserve.close(resolve));
const name = 'treasure-stats-test-' + randomUUID();
const args = ['run', '--rm', '--network', 'host', '--name', name,
  '-e', 'CHAT_API_HOST=127.0.0.1', '-e', `CHAT_API_PORT=${port}`,
  '-e', 'TREASURE_MOUSE_PLATFORM_ONLY=true', '-e', 'TREASURE_MOUSE_INTERNAL_TOKEN=isolated-test-token',
  '-e', 'LLM_API_KEY=isolated-fixture-key', '-e', `LLM_BASE_URL=http://127.0.0.1:${upstream.address().port}`,
  '-e', 'DATA_DIR=/tmp/isolated-stats', '-e', 'STATS_FILE=/tmp/isolated-stats/stats.json', image];
const child = spawn('docker', args, { stdio: ['ignore', 'pipe', 'pipe'] });
let logs = '';
child.stdout.on('data', bytes => { logs += bytes; });
child.stderr.on('data', bytes => { logs += bytes; });
try {
  const endpoint = `http://127.0.0.1:${port}`;
  let ready = false;
  for (let i = 0; i < 40; i++) {
    if (child.exitCode !== null) throw new Error('Isolated runtime stopped: ' + logs);
    try { ready = (await fetch(endpoint + '/stats')).ok; } catch { /* starting */ }
    if (ready) break;
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  assert.ok(ready, 'runtime must start');
  const response = await fetch(endpoint + '/cygnusx/discovery', {
    method: 'POST', headers: { 'Content-Type': 'application/json',
      'X-CygnusX-Internal-Token': 'isolated-test-token', 'X-CygnusX-Principal': randomUUID() },
    body: JSON.stringify({ model: 'fixture-model', messages: [{ role: 'user', content: 'fixture' }], lang: 'en' }),
  });
  assert.equal(response.status, 200);
  const frames = (await response.text()).split('\n').filter(line => line.startsWith('data: ') && !line.includes('[DONE]')).map(line => JSON.parse(line.slice(6)));
  const usage = frames.find(frame => frame.event === 'usage');
  assert.deepEqual(usage, { event: 'usage', llm_calls: 1, usage: { prompt_tokens: 37, completion_tokens: 5, total_tokens: 42 } });
  assert.ok(frames.some(frame => frame.event === 'end'));
  const report = { image, checks: ['Actual image starts', 'Trusted endpoint accepts platform identity', 'OpenAI SSE usage parsed', 'Request-local token telemetry emitted before end'], usage };
  await writeFile(`${output}/runtime-usage-result.json`, JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report));
} finally {
  spawnSync('docker', ['rm', '-f', name], { stdio: 'ignore' });
  if (child.exitCode === null) await once(child, 'exit');
  await new Promise(resolve => upstream.close(resolve));
}
