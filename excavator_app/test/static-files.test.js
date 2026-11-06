import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { gunzipSync } from "node:zlib";
import { createApplication } from "../server/index.js";

// The model the browser downloads, as committed.
const model = JSON.parse(
  gunzipSync(await readFile(new URL("../public/model.json.gz", import.meta.url))),
);
const LINK = /^(?:shoe_|track_pin_|track_bushing_|pin_clip_)([LR])(\d{2})/;

test("the model lists every part, and holds one track link's geometry", () => {
  assert.equal(model.meshes.length, 644);
  const links = model.meshes.filter((mesh) => LINK.test(mesh.name));
  assert.equal(links.length, 2 * 34 * 5, "five parts, 34 links, two tracks");
  const drawn = links.filter((mesh) => mesh.v);
  assert.deepEqual(drawn.map((mesh) => mesh.name).sort(), [
    "pin_clip_R00_0",
    "pin_clip_R00_1",
    "shoe_R00",
    "track_bushing_R00",
    "track_pin_R00",
  ]);
  for (const mesh of model.meshes.filter((mesh) => !LINK.test(mesh.name)))
    assert.ok(mesh.v && mesh.t, `${mesh.name} has its geometry`);
});

test("files are compressed, and an unchanged one is not sent again", async (t) => {
  const app = createApplication();
  await new Promise((resolve) => app.server.listen(0, "127.0.0.1", resolve));
  t.after(() => app.close());
  const origin = `http://127.0.0.1:${app.server.address().port}`;

  const page = await fetch(origin + "/", {
    headers: { "Accept-Encoding": "gzip" },
  });
  assert.equal(page.status, 200);
  assert.equal(page.headers.get("content-encoding"), "gzip");
  const script = /assets\/[^"]+\.js/.exec(await page.text())[0],
    tag = page.headers.get("etag");
  assert.ok(tag);
  const unchanged = await fetch(origin + "/", {
    headers: { "If-None-Match": tag },
  });
  assert.equal(unchanged.status, 304);
  assert.equal(await unchanged.text(), "");

  // Node's fetch decompresses, so ask for the raw size without it.
  const { get } = await import("node:http"),
    raw = (path, headers) =>
      new Promise((resolve, reject) =>
        get(origin + path, { headers }, (response) => {
          const parts = [];
          response.on("data", (part) => parts.push(part));
          response.on("end", () =>
            resolve({ response, body: Buffer.concat(parts) }),
          );
        }).on("error", reject),
      );
  const plain = await raw("/" + script, {}),
    small = await raw("/" + script, { "Accept-Encoding": "gzip" });
  assert.equal(plain.response.headers["content-encoding"], undefined);
  assert.equal(small.response.headers["content-encoding"], "gzip");
  assert.ok(small.body.length < plain.body.length / 2);
  assert.deepEqual(gunzipSync(small.body), plain.body);
  assert.match(small.response.headers["cache-control"], /immutable/);

  const asset = await raw("/model.json", { "Accept-Encoding": "gzip" });
  assert.equal(asset.response.headers["content-encoding"], "gzip");
  assert.equal(JSON.parse(gunzipSync(asset.body)).meshes.length, 644);
  const again = await raw("/model.json", {
    "If-None-Match": asset.response.headers.etag,
  });
  assert.equal(again.response.statusCode, 304);
  assert.equal(again.body.length, 0);
  assert.equal((await raw("/nothing-here.js", {})).response.statusCode, 404);
});
