import { initialMachine } from "./world.js";
import { initialTruck } from "./truck.js";

// How many excavators fit in a room unless MAX_PLAYERS says otherwise.
export const DEFAULT_PLAYERS = 16;
export const NAME_LENGTH = 16;

// Places a machine can start: [x, y, heading], on level hard ground, facing the
// sand a scoop away, with room behind for the chase camera and nobody between it
// and the machine. The first is the start position beside the pour zone; the next
// eight line the yard's near edge, and the rest its south and north edges.
const FACING_NORTH = Math.PI / 2,
  FACING_SOUTH = -Math.PI / 2;
export const SPAWNS = Object.freeze(
  [
    [0, 0, 0],
    [420, 800, 0],
    [-110, -1300, 0],
    [420, 1800, 0],
    [-110, -1800, 0],
    [420, 2300, 0],
    [-110, -2300, 0],
    [420, 2800, 0],
    [-110, -2800, 0],
    [1000, -3480, FACING_NORTH],
    [1700, 3480, FACING_SOUTH],
    [1500, -3480, FACING_NORTH],
    [2200, 3480, FACING_SOUTH],
    [2000, -3480, FACING_NORTH],
    [2700, 3480, FACING_SOUTH],
    [2500, -3480, FACING_NORTH],
    [3200, 3480, FACING_SOUTH],
  ].map(Object.freeze),
);

export const spawnMachine = (slot) => {
  const [x, y, heading] = SPAWNS[slot];
  return { ...initialMachine(), x, y, heading };
};

// Where each player's dump truck waits, by seat: [x, y, heading] of the middle of
// its rear tandem. The first stands beside the start position, its cab to the road
// and its body where the first machine's bucket swings over it at about -90
// degrees. The others wait in two stands on the level hard ground west of the
// yard, north and south of the work site, each on the side of its player's start
// position. They face the yard in a single row, so each drives straight out.
const FACING_EAST = 0,
  FACING_WEST = Math.PI,
  NORTH_STAND = [1, 3, 5, 7, 10, 12, 14, 16],
  SOUTH_STAND = [2, 4, 6, 8, 9, 11, 13, 15];
export const TRUCK_BAYS = Object.freeze(
  SPAWNS.map((_, seat) => {
    if (seat === 0) return [60, -455, FACING_WEST];
    const north = NORTH_STAND.indexOf(seat);
    return north >= 0
      ? [-1600, 1650 + 250 * north, FACING_EAST]
      : [-1900, -1700 - 250 * SOUTH_STAND.indexOf(seat), FACING_EAST];
  }).map(Object.freeze),
);

export const parkedTruck = (bay) => {
  const [x, y, heading] = TRUCK_BAYS[bay];
  return { ...initialTruck(), x, y, heading };
};

// Every machine has its own paint, in sRGB, so players can tell them apart in
// the world, on the map and in the list. The first is the CAD model's own yellow.
export const PAINTS = Object.freeze([
  "#e89912",
  "#2b7fd8",
  "#d63c2c",
  "#2ea44f",
  "#8b57d8",
  "#f1ede2",
  "#1fb4c2",
  "#e2559f",
  "#6f7f2f",
  "#34383d",
  "#7fc83f",
  "#25468f",
  "#9c5c2a",
  "#b6bec6",
  "#8d1c40",
  "#f07a1a",
]);

// A display name: printable, one line and short. Names only ever reach a page
// as text, so nothing else needs escaping. Returns "" if nothing usable is left.
export function cleanName(raw) {
  if (typeof raw !== "string") return "";
  const text = raw
    .normalize("NFC")
    .replace(/\s/gu, " ")
    .replace(/\p{C}/gu, "")
    .replace(/ +/g, " ")
    .trim();
  return [...text].slice(0, NAME_LENGTH).join("").trim();
}
