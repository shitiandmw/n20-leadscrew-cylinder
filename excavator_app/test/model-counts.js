// What the committed complete-machine model holds, for the checks that count it.
export const MODEL_RECORDS = Object.freeze({ parts: 316, module: 105, link: 2 });
// Mesh records the browser reports: the parts, and the two tracks' modules and links.
export const MESHES =
  MODEL_RECORDS.parts + 2 * MODEL_RECORDS.module + 2 * MODEL_RECORDS.link;
