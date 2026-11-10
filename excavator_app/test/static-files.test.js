import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { gunzipSync } from "node:zlib";
import { createApplication } from "../server/index.js";
import { CONFIG } from "../shared/config.js";
import { MODEL_RECORDS } from "./model-counts.js";

// The model the browser downloads, as committed: the complete X1 / J9 / R12
// machine, with one track module and one chain link drawn as instances.
const model = JSON.parse(
  gunzipSync(await readFile(new URL("../public/model.json.gz", import.meta.url))),
);

test("the model lists every part, and holds one track link's geometry", () => {
  for (const [list, count] of Object.entries(MODEL_RECORDS)) {
    assert.equal(model[list].length, count, list);
    for (const item of model[list])
      assert.ok(item.v && item.t && item.color, `${item.name} has its geometry`);
  }
  assert.equal(model.cfg.j9.pins.length, CONFIG.track_links_per_side);
  assert.equal(model.cfg.O.join(), CONFIG.arm_offset.join());
  assert.equal(model.cfg.pins.T.join(), CONFIG.arm.tip.join());
  const movers = new Set(model.parts.map((part) => part.mover));
  for (const mover of ["ground", "upper", "pinion", "arm:boom", "arm:stick", "arm:bucket"])
    assert.ok(movers.has(mover), mover);
  assert.equal(model.parts.filter((part) => part.mover === "arm:bucket").length, 9);
  assert.ok(model.source.sha256, "the viewer it came from is recorded");
  // The drive meshes are modelled at their own lateral position: the boom pair
  // at y = +-34 mm. The renderer must not add the drive's offset again, or the
  // cylinders hang 34 mm outboard of their mounts.
  const centreY = (item) => {
    const bytes = Buffer.from(item.v, "base64"),
      v = new Float32Array(bytes.buffer, bytes.byteOffset, bytes.byteLength / 4);
    let low = Infinity,
      high = -Infinity;
    for (let k = 1; k < v.length; k += 3) {
      low = Math.min(low, v[k]);
      high = Math.max(high, v[k]);
    }
    return (low + high) / 2;
  };
  for (const drive of model.cfg.drives)
    for (const item of model.parts.filter((part) => part.mover === `arm:${drive.name}_barrel`))
      assert.ok(Math.abs(centreY(item) - drive.y) < 1, `${item.name} sits at y ${drive.y}`);
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
  assert.equal(JSON.parse(gunzipSync(asset.body)).parts.length, MODEL_RECORDS.parts);
  const again = await raw("/model.json", {
    "If-None-Match": asset.response.headers.etag,
  });
  assert.equal(again.response.statusCode, 304);
  assert.equal(again.body.length, 0);
  assert.equal((await raw("/nothing-here.js", {})).response.statusCode, 404);
});
