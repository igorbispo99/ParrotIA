#!/usr/bin/bash
# Run in a Fedora development environment with official RPM build tools.
set -euo pipefail
project_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$project_root"
output=$(realpath -m "${1:-dist/fedora}")
mkdir -p "$output" "$output/rpmbuild"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}

appid=io.github.igorbispo99.ParrotIA
desktop-file-validate "packaging/fedora/$appid.desktop"
appstreamcli validate --pedantic --no-net "packaging/fedora/$appid.metainfo.xml"
rpmspec -P packaging/fedora/parrotia.spec > "$output/spec-expanded.log"
python3 -m build --sdist --no-isolation --outdir "$output/rpmbuild/SOURCES"
install -m 0644 packaging/fedora/parrotia.spec "$output/rpmbuild/SPECS/parrotia.spec"
rpmbuild -bs --define "_topdir $output/rpmbuild" "$output/rpmbuild/SPECS/parrotia.spec"
rpmlint packaging/fedora/parrotia.spec "$output"/rpmbuild/SRPMS/*.src.rpm | tee "$output/rpmlint.log"
(cd "$output" && sha256sum rpmbuild/SOURCES/*.tar.gz rpmbuild/SRPMS/*.src.rpm) > "$output/SHA256SUMS"
