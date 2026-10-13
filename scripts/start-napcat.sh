#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
app_dir="$project_root/runtime/napcat/squashfs-root"
runtime_dir="$project_root/runtime/data"
isolated_home="$runtime_dir/home"
user_runtime_dir="/run/user/$(id -u)"
app_mount="/mnt/runtime/napcat/squashfs-root"

if [[ ! -x "$app_dir/qq" ]]; then
  echo "NapCat AppImage 尚未解包：$app_dir/qq" >&2
  exit 2
fi
if [[ -z "${DISPLAY:-}" ]]; then
  echo "未找到图形显示会话，无法打开 QQ 登录窗口。" >&2
  exit 2
fi
if ! command -v bwrap >/dev/null 2>&1; then
  echo "未找到 bubblewrap，无法隔离现有 QQ 数据。" >&2
  exit 2
fi

mkdir -p "$runtime_dir/config" "$runtime_dir/logs" "$isolated_home"

sandbox_args=(
  --die-with-parent
  --ro-bind / /
  --dev-bind /dev /dev
  --proc /proc
  --bind /tmp /tmp
  --bind "$project_root" /mnt
  --bind "$isolated_home" /home/sugarybean
  --chdir /mnt/runtime/data
)
if [[ -d "$user_runtime_dir" ]]; then
  sandbox_args+=(--bind "$user_runtime_dir" "$user_runtime_dir")
fi

launch_started="$(date +%s.%N)"
(
  cd "$project_root"
  exec env PYTHONPATH=src python3 -m qq_group_overlap.login_window \
    --qr-path "$runtime_dir/cache/qrcode.png" \
    --not-before "$launch_started"
) &

# AppRun forces QQ through xvfb-run, which hides the login window on a virtual
# display. Reproduce its runtime environment and launch QQ on the inherited
# desktop DISPLAY instead. Bubblewrap remains the outer filesystem sandbox.
exec bwrap "${sandbox_args[@]}" \
  /usr/bin/env \
  APPDIR="$app_mount" \
  NAPCAT_WORKDIR="/mnt/runtime/data" \
  PATH="$app_mount:$app_mount/usr/sbin:/mnt/runtime/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" \
  LD_LIBRARY_PATH="$app_mount/usr/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
  XDG_DATA_DIRS="$app_mount/usr/share:/usr/share/gnome:/usr/local/share:/usr/share" \
  GSETTINGS_SCHEMA_DIR="$app_mount/usr/share/glib-2.0/schemas" \
  XDG_CONFIG_HOME="/home/sugarybean/.config" \
  /mnt/runtime/napcat/squashfs-root/qq \
  --no-sandbox
