#!/usr/bin/env bash
# TrueRehab-RF Pi set installer. Run it from the unpacked folder (safe to run again, e.g. after an update):
#
#   bash install.sh                  install and start the bridge at boot (Raspberry Pi OS 64-bit)
#   bash install.sh --with-model     also PyTorch, for the model's session check and replays (~200 MB)
#   bash install.sh --dry-run        only show what it would do
#
# Testing on another computer: --no-systemd (no boot service, no dialout group, no apt),
# --system-site-packages (reuse already installed numpy/PyTorch), --copies (drives without symlinks, e.g. exFAT).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$HERE/.venv"
WITH_MODEL=0; SYSTEMD=1; DRY=0; SITE=0; COPIES=0
for arg in "$@"; do
  case "$arg" in
    --with-model) WITH_MODEL=1 ;;
    --no-systemd) SYSTEMD=0 ;;
    --dry-run) DRY=1 ;;
    --system-site-packages) SITE=1 ;;
    --copies) COPIES=1 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "Unknown option: $arg (see --help)"; exit 2 ;;
  esac
done

step() { printf '\n==> %s\n' "$*"; }
note() { printf '    %s\n' "$*"; }
run()  { if [ "$DRY" = 1 ]; then printf '    (dry run) %s\n' "$*"; else "$@"; fi; }
die()  { printf '\nSTOP: %s\n' "$*" >&2; exit 1; }

cd "$HERE"
[ -f VERSION.json ] || die "run this from the unpacked TrueRehab Pi set (VERSION.json is missing here)"

step "Checking this computer"
OS="$(uname -s)"; ARCH="$(uname -m)"
MODEL="$(tr -d '\0' 2>/dev/null </proc/device-tree/model || true)"
note "system: $OS $ARCH ${MODEL:+($MODEL)}"
if [ "$OS" = Linux ] && [ "$ARCH" != aarch64 ]; then
  note "! not 64-bit ARM: flash 'Raspberry Pi OS (64-bit)' on the Pi 5. Continuing anyway."
fi
if [ "$OS" != Linux ] && [ "$SYSTEMD" = 1 ]; then
  die "this isn't Linux: on another computer use --no-systemd (for testing)"
fi
PY="$(command -v python3 || true)"
[ -n "$PY" ] || die "python3 not found (Raspberry Pi OS has it; install with: sudo apt install python3)"
PYV="$("$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
"$PY" -c 'import sys; sys.exit(sys.version_info < (3, 11))' || die "Python $PYV is too old: 3.11 or newer is needed"
note "python: $PY ($PYV)"

step "Making the Python environment ($VENV)"
VENV_OPTS=()
[ "$SITE" = 1 ] && VENV_OPTS+=(--system-site-packages)
if [ "$COPIES" = 0 ]; then                       # drives without symlinks (exFAT, FAT) need copies
  probe="$HERE/.symlink-probe-$$"
  if ! ln -s VERSION.json "$probe" 2>/dev/null; then COPIES=1; note "this drive can't hold symlinks: using --copies"; fi
  rm -f "$probe"
fi
[ "$COPIES" = 1 ] && VENV_OPTS+=(--copies)
if [ -x "$VENV/bin/python" ]; then
  note "already there: keeping it"
elif ! run "$PY" -m venv "${VENV_OPTS[@]+"${VENV_OPTS[@]}"}" "$VENV"; then
  if command -v apt-get >/dev/null 2>&1; then
    note "python3-venv is missing: installing it"
    run sudo apt-get install -y python3-venv
    run rm -rf "$VENV"
    run "$PY" -m venv "${VENV_OPTS[@]+"${VENV_OPTS[@]}"}" "$VENV"
  else
    die "couldn't make the Python environment"
  fi
fi

step "Installing packages"
run "$VENV/bin/python" -m pip install --disable-pip-version-check -r requirements-pi.txt
if [ "$WITH_MODEL" = 1 ]; then
  note "PyTorch for the model tools (large; a few minutes)"
  run "$VENV/bin/python" -m pip install --disable-pip-version-check -r requirements-model.txt
fi

step "Settings"
if [ -f pi-bridge/config.toml ]; then
  note "keeping your pi-bridge/config.toml"
  grep -q '^\[providers\.emg\]' pi-bridge/config.toml ||
    note "it has no [providers.emg] (sEMG, new in v0.2): copy that section from config.pi.toml to use the MyoWare"
else
  run cp config.pi.toml pi-bridge/config.toml
  note "made pi-bridge/config.toml from config.pi.toml (edit the kit name and key there)"
fi

if [ "$SYSTEMD" = 1 ]; then
  step "Serial ports: USER $USER needs the dialout group for the radar's USB ports"
  if id -nG "$USER" | grep -qw dialout; then
    note "already in dialout"
  else
    run sudo usermod -aG dialout "$USER"
    note "added: it takes effect after the next login or reboot (the boot service gets it right away)"
  fi

  step "Starting the bridge at boot (systemd)"
  unit="$(mktemp)"
  sed -e "s|@USER@|$USER|g" -e "s|@DIR@|$HERE|g" truerehab-bridge.service.in >"$unit"
  run sudo install -m 644 "$unit" /etc/systemd/system/truerehab-bridge.service
  rm -f "$unit"
  run sudo systemctl daemon-reload
  run sudo systemctl enable truerehab-bridge
  run sudo systemctl restart truerehab-bridge
  [ "$DRY" = 1 ] || systemctl --no-pager --lines=5 status truerehab-bridge || true
else
  note "no boot service (--no-systemd). Start it by hand:"
  note "  cd \"$HERE/pi-bridge\" && ../.venv/bin/python -m truerehab_bridge --config config.toml"
fi

step "Done"
HOST="$(hostname 2>/dev/null || echo raspberrypi)"
note "Dashboard: http://${HOST%.local}.local:8080   (phone or laptop on the same Wi-Fi)"
note "Check everything:  \"$VENV/bin/python\" \"$HERE/selftest.py\""
[ "$WITH_MODEL" = 1 ] || note "Model tools (session check, replays) need: bash install.sh --with-model"
