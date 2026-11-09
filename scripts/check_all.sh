#!/usr/bin/env bash
# Every check in the repo, with one table at the end. Nothing is installed and no project file changes;
# each suite's output goes to a log folder.
#
#   bash scripts/check_all.sh                    this folder as it is
#   bash scripts/check_all.sh --clean            a fresh copy of what git would commit (tracked files plus new files
#                                                that aren't ignored), so git-ignored local things (recordings, the
#                                                pose model, caches) can't change a result
#   bash scripts/check_all.sh --only model,frontend    only these groups or suites
#
# Groups: model, recorder, radar-lab, pi-bridge, sandbox, frontend, phisit.
# Each Python part runs with its own .venv (from a git worktree: the main checkout's). A suite whose tool or package
# is missing is listed as "skip" with the reason. Exit code 0 when nothing failed. Needs bash (Git Bash on Windows).
set -u

ROOT=$(git -C "$(dirname "$0")" rev-parse --show-toplevel) || exit 2
MAIN=$(git -C "$ROOT" worktree list --porcelain | sed -n '1s/^worktree //p')
CLEAN=0
ONLY=""
while [ $# -gt 0 ]; do
  case $1 in
    --clean) CLEAN=1 ;;
    --only) [ $# -ge 2 ] || { echo "--only needs a list, e.g. --only model,frontend"; exit 2; }
            ONLY=",$2,"; shift ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "unknown option: $1 (see --help)"; exit 2 ;;
  esac
  shift
done

TMP=${TMPDIR:-/tmp}
TMP=${TMP%/}
LOGS="$TMP/truerehab-checks-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$LOGS"
RUN=$ROOT
COPY=""
LINKS=()                      # node_modules links this script makes; removed at the end
cleanup() {
  local l
  for l in ${LINKS[@]+"${LINKS[@]}"}; do [ -L "$l" ] && unlink "$l"; done
  if [ -n "$COPY" ] && [ -d "$COPY" ]; then rm -rf "$COPY"; fi
}
trap cleanup EXIT

BRANCH=$(git -C "$ROOT" rev-parse --abbrev-ref HEAD)
SHA=$(git -C "$ROOT" rev-parse --short HEAD)
CHANGED=""
[ -n "$(git -C "$ROOT" status --porcelain)" ] && CHANGED=" + uncommitted changes"
if [ "$CLEAN" = 1 ]; then
  COPY=$(mktemp -d "$TMP/truerehab-clean.XXXXXX") || exit 2
  ( cd "$ROOT" && git ls-files -z --cached --others --exclude-standard |
      while IFS= read -r -d '' f; do [ -e "$f" ] && printf '%s\0' "$f"; done |
      tar -cf - --null -T - ) | tar -xf - -C "$COPY" || { echo "could not copy the repo"; exit 2; }
  RUN=$COPY
  MODE="clean copy of $BRANCH at $SHA$CHANGED, without git-ignored files"
else
  MODE="this folder: $BRANCH at $SHA$CHANGED"
fi
echo "TrueRehab-RF checks, $MODE"
echo "logs: $LOGS"

# --------------------------------------------------------------------------- helpers
RESULTS=""
FAILED=0

want() {      # want <group> <suite>: is it selected by --only?
  [ -z "$ONLY" ] && return 0
  case $ONLY in *",$1,"*|*",$2,"*) return 0 ;; esac
  return 1
}

py_with() {   # py_with <module> <part>...: the first Python (the parts' .venv, then python3) that can import module
  local need=$1 part p
  shift
  for part in "$@"; do
    for p in "$ROOT/$part/.venv/bin/python" "$MAIN/$part/.venv/bin/python"; do
      if [ -x "$p" ] && "$p" -c "import $need" >/dev/null 2>&1; then echo "$p"; return 0; fi
    done
  done
  p=$(command -v python3 || true)
  if [ -n "$p" ] && "$p" -c "import $need" >/dev/null 2>&1; then echo "$p"; fi
}

summary() {   # summary <log>: the line worth showing
  local f=$1 ran st
  ran=$(grep -E '^Ran [0-9]+ tests? in' "$f" | tail -1 | awk '{print $2}')
  if [ -n "$ran" ]; then
    st=$(grep -E '^(OK|FAILED)' "$f" | tail -1)
    echo "$ran tests, $st"
  else
    grep -E -i 'pass|fail|error|checks|built in' "$f" | tail -1 | cut -c1-90
  fi
}

record() {    # record <suite> <result> <time> <detail>
  RESULTS="$RESULTS$1|$2|$3|$4"$'\n'
  printf '  %-18s %-6s %5s  %s\n' "$1" "$2" "$3" "$4"
}

run() {       # run <group> <suite> <folder> <command...>
  local group=$1 name=$2 dir=$3 log t0 rc res detail
  shift 3
  want "$group" "$name" || return 0
  log="$LOGS/$name.log"
  t0=$SECONDS
  ( cd "$RUN/$dir" && "$@" ) >"$log" 2>&1
  rc=$?
  res=pass
  if [ $rc -ne 0 ]; then res=FAIL; FAILED=$((FAILED + 1)); fi
  detail=$(summary "$log")
  [ -z "$detail" ] && detail=$([ $rc -eq 0 ] && echo "ok" || echo "exit code $rc, see $log")
  record "$name" "$res" "$((SECONDS - t0))s" "$detail"
}

skip() {      # skip <group> <suite> <reason>
  want "$1" "$2" || return 0
  record "$2" skip - "$3"
}

# --------------------------------------------------------------------------- Python parts
py=$(py_with torch model)
if [ -n "$py" ]; then run model model model "$py" -m unittest discover -s tests
else skip model model "no Python with PyTorch (model/.venv, see model/README.md)"; fi

py=$(py_with numpy recorder)
if [ -n "$py" ]; then run recorder recorder recorder "$py" -m unittest discover -s tests
else skip recorder recorder "no Python with numpy"; fi

py=$(py_with numpy radar-lab)
if [ -n "$py" ]; then run radar-lab radar-lab radar-lab "$py" -m unittest discover -s tests
else skip radar-lab radar-lab "no Python with numpy"; fi

py=$(py_with numpy pi-bridge)
if [ -n "$py" ]; then run pi-bridge pi-bridge pi-bridge "$py" -m unittest discover -s tests
else skip pi-bridge pi-bridge "no Python with numpy"; fi

# --------------------------------------------------------------------------- sandbox demos
py=$(py_with torch model)
if [ -n "$py" ]; then run sandbox encoder sandbox/Encoder_0.1 "$py" check_encoder.py
else skip sandbox encoder "no Python with PyTorch"; fi

py=$(py_with serial radar-lab recorder pi-bridge)
if [ -n "$py" ]; then run sandbox lv-packets sandbox/radar-live-viewer "$py" test_packets.py
else skip sandbox lv-packets "no Python with pyserial"; fi
skip sandbox lv-http "needs the Windows viewer running on 127.0.0.1:8766"

if command -v node >/dev/null; then
  run sandbox lv-roommap sandbox/radar-live-viewer node test_room_map.js
  run sandbox car-geometry sandbox/radar-car-demo node test_geometry.js
else
  skip sandbox lv-roommap "node not installed"
  skip sandbox car-geometry "node not installed"
fi

# --------------------------------------------------------------------------- dashboard
NODE_MODULES=""
for d in "$ROOT/frontend/node_modules" "$MAIN/frontend/node_modules"; do
  if [ -d "$d" ]; then NODE_MODULES=$d; break; fi
done
FE_SUITES="fe-typecheck fe-i18n fe-session-report fe-hmac fe-auth fe-playout fe-build"
if ! command -v node >/dev/null; then
  for s in $FE_SUITES; do skip frontend "$s" "node not installed"; done
elif [ -z "$NODE_MODULES" ]; then
  for s in $FE_SUITES; do skip frontend "$s" "no node_modules: run npm ci in frontend/"; done
else
  if [ ! -e "$RUN/frontend/node_modules" ]; then
    ln -s "$NODE_MODULES" "$RUN/frontend/node_modules" && LINKS+=("$RUN/frontend/node_modules")
  fi
  run frontend fe-typecheck frontend npm run -s typecheck
  run frontend fe-i18n frontend node scripts/check-i18n.cjs
  run frontend fe-session-report frontend node scripts/check-session-report.cjs
  run frontend fe-hmac frontend node scripts/check-hmac.ts
  if command -v lsof >/dev/null && lsof -nP -iTCP:18765 -sTCP:LISTEN >/dev/null 2>&1; then
    skip frontend fe-auth "port 18765 is in use (the check starts its own mock bridge there)"
  else
    run frontend fe-auth frontend node scripts/check-auth.ts
  fi
  if [ -f "$RUN/frontend/scripts/check-playout.ts" ]; then
    run frontend fe-playout frontend node scripts/check-playout.ts
  fi
  run frontend fe-build frontend npm run -s build
fi

# --------------------------------------------------------------------------- teammate's demo, firmware
py=$(py_with fastapi Phisit)
if [ -n "$py" ]; then run phisit phisit-backend Phisit/backend "$py" -m unittest discover -s tests
else skip phisit phisit-backend "no Python with fastapi (see Phisit/README.md)"; fi
skip firmware firmware "compile the sketches in the Arduino IDE"

# --------------------------------------------------------------------------- table
echo
printf '%-18s %-6s %5s  %s\n' suite result time detail
printf '%s' "$RESULTS" | while IFS='|' read -r n r t d; do
  [ -n "$n" ] && printf '%-18s %-6s %5s  %s\n' "$n" "$r" "$t" "$d"
done
echo
if [ "$FAILED" -eq 0 ]; then
  echo "Nothing failed. Logs: $LOGS"
  exit 0
fi
echo "$FAILED suite(s) FAILED. Logs: $LOGS"
exit 1
