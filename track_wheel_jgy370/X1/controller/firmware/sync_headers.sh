#!/bin/sh
# Copies the shared link header (common/x1_link.h, the master) into each sketch's src/, because the
# Arduino build copies only the sketch folder. Add the handle sketch here when it exists.
# The pin header is not copied here: main_board/source/pinmap.py writes both of its copies.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
for sketch in x1_main; do
  cp "$here/common/x1_link.h" "$here/$sketch/src/x1_link.h"
  echo "copied common/x1_link.h -> $sketch/src/x1_link.h"
done
