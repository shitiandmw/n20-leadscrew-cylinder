#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose config --quiet
docker build -t arm60-sand-lab:test .
# Finite integration check: no published port or detached container.
docker run --rm --read-only --cap-drop=ALL --security-opt=no-new-privileges -i arm60-sand-lab:test node --input-type=module <<'JS'
import assert from 'node:assert/strict';
import { once } from 'node:events';
import WebSocket from 'ws';
import { createApplication } from './server/index.js';
const app = createApplication();
await new Promise(resolve => app.server.listen(0, '127.0.0.1', resolve));
try {
  const origin = `http://127.0.0.1:${app.server.address().port}`;
  assert.equal(process.getuid(), 1000);
  assert.equal((await fetch(origin + '/api/health')).status, 200);
  assert.equal((await fetch(origin + '/remote')).status, 200);
  const model = await (await fetch(origin + '/model.json')).json();
  assert.equal(model.meshes.length, 644);
  const { room } = await (await fetch(origin + '/api/rooms', { method: 'POST' })).json();
  const ws = new WebSocket(origin.replace('http', 'ws') + '/ws?room=' + room + '&role=remote');
  await once(ws, 'open');
  ws.send(JSON.stringify({ type: 'claim' }));
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('WebSocket timeout')), 5000);
    ws.on('message', data => {
      const message = JSON.parse(data);
      if (message.type === 'state' && message.owner) { clearTimeout(timer); resolve(); }
    });
  });
  ws.close();
  console.log('PASS: non-root read-only Docker container, health, remote page, 644 model meshes and WebSocket control.');
} finally { await app.close(); }
JS
