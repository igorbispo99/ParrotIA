#!/usr/bin/bash
# Run on an expendable Ubuntu CI host, as the unprivileged desktop user.
set -euo pipefail
: "${SNAP_FILE:?Built Snap path is required}"
: "${GITHUB_RUN_ID:?An isolated CI run is required}"
: "${RUNNER_TEMP:?An isolated CI temporary directory is required}"
project=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
review="$project/dist/snap-review"
mkdir -p "$review"
qa="$HOME/Documents/ParrotIA Snap QA-$GITHUB_RUN_ID"
mkdir -p "$qa/CLI outputs"
speech="$qa/audio with spaces – café.wav"
espeak-ng -v en-us -s 135 -w "$speech" "Hello. This is a test of local audio transcription. The quick brown fox jumps over the lazy dog."

# No downloads after the explicit tiny-model setup in the earlier workflow step.
export HF_HUB_OFFLINE=1
for extension in wav mp3 flac ogg m4a mp4; do
    input="$speech"
    if [ "$extension" != wav ]; then
        input="$qa/encoded-$extension.$extension"
        if [ "$extension" = mp4 ]; then
            ffmpeg -nostdin -v error -y -f lavfi -i color=size=32x32:rate=1 -i "$speech" -c:v mpeg4 -c:a aac -shortest "$input"
        else
            ffmpeg -nostdin -v error -y -i "$speech" "$input"
        fi
    fi
    parrotia "$input" --model tiny --device cpu --compute int8 --language en \
        --formats txt md srt vtt json --outdir "$qa/CLI outputs"
done
python3 - "$qa/CLI outputs" <<'PY'
import json, pathlib, sys
output = pathlib.Path(sys.argv[1])
for suffix in ["txt", "md", "srt", "vtt", "json"]:
    files = list(output.glob("*." + suffix))
    assert len(files) == 6, (suffix, files)
    assert all(p.stat().st_size for p in files)
for path in output.glob("*.txt"):
    assert "test" in path.read_text().lower(), path.read_text()
for path in output.glob("*.json"):
    assert json.loads(path.read_text())["segments"], path
PY

# Strict home confinement must reject hidden host files.
hidden="$HOME/.parrotia-snap-qa-$GITHUB_RUN_ID"
mkdir -p "$hidden"
cp "$speech" "$hidden/private.wav"
if parrotia "$hidden/private.wav" --model tiny --outdir "$qa/CLI outputs" > "$review/hidden-denial.log" 2>&1; then
    echo "ERROR: hidden host file unexpectedly readable" >&2; exit 1
fi
grep -Ei 'permission denied|file not found' "$review/hidden-denial.log"

# Verify optional external-media access before and after connection.
media="/media/parrotia-snap-qa-$GITHUB_RUN_ID"
sudo mkdir -p "$media"
sudo cp "$speech" "$media/speech.wav"
sudo chmod 755 "$media"
sudo chmod 644 "$media/speech.wav"
if parrotia "$media/speech.wav" --model tiny --outdir "$qa/CLI outputs" > "$review/media-denial.log" 2>&1; then
    echo "ERROR: removable media unexpectedly readable before connection" >&2; exit 1
fi
grep -Ei 'permission denied|file not found' "$review/media-denial.log"
sudo snap connect parrotia:removable-media
parrotia "$media/speech.wav" --model tiny --device cpu --compute int8 --language en --outdir "$qa/CLI outputs"

# Read-only source directories need a writable output destination.
mkdir "$qa/read-only"
cp "$speech" "$qa/read-only/input.wav"
chmod 555 "$qa/read-only"
if parrotia "$qa/read-only/input.wav" --model tiny --device cpu --compute int8 --language en > "$review/read-only.log" 2>&1; then
    echo "ERROR: writing a read-only directory unexpectedly succeeded" >&2; exit 1
fi
grep -i 'permission denied' "$review/read-only.log"
parrotia "$qa/read-only/input.wav" --model tiny --device cpu --compute int8 --language en --outdir "$qa/CLI outputs"
chmod 755 "$qa/read-only"

# Actual GUI buttons, worker threads, exports, batch recovery and cancellation.
timeout 300s xvfb-run -a -s "-screen 0 1280x1024x24 -ac" env XAUTHORITY= \
    parrotia.check --exercise-gui "$speech" | tee "$review/gui-and-provenance.json"
cp "$HOME/snap/parrotia/common/qa-gui.png" "$review/gui.png"

# Exercise refresh/revert with a second *test-only* revision. The original
# artifact is never modified and only the original is preserved for Store upload.
original=$(readlink /snap/parrotia/current)
common="$HOME/snap/parrotia/common"
printf 'cache must survive\n' > "$common/qa-refresh-marker"
refresh_tree="$RUNNER_TEMP/parrotia-refresh-tree"
unsquashfs -d "$refresh_tree" "$SNAP_FILE" > "$review/unsquashfs.log"
sed -i "s/^version:.*/version: '1.3.1-qa-refresh'/" "$refresh_tree/meta/snap.yaml"
mksquashfs "$refresh_tree" "$RUNNER_TEMP/parrotia-refresh.snap" -noappend -comp xz -processors 2 > "$review/repack.log"
sudo snap install --dangerous "$RUNNER_TEMP/parrotia-refresh.snap"
test "$(readlink /snap/parrotia/current)" != "$original"
grep -q 'cache must survive' "$common/qa-refresh-marker"
parrotia.check --model tiny | tee "$review/after-refresh.json"
sudo snap revert parrotia
test "$(readlink /snap/parrotia/current)" = "$original"
grep -q 'cache must survive' "$common/qa-refresh-marker"
parrotia.check --model tiny | tee "$review/after-revert.json"
snap connections parrotia > "$review/connections.log"
printf 'CLI formats/codecs, home/media/read-only access, GUI workflow and local refresh/revert passed\n' > "$review/RESULT.txt"
