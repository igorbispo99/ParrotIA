%global app_id io.github.igorbispo99.ParrotIA

Name:           parrotia
Version:        1.3.1
Release:        %autorelease
Summary:        Private, local audio and video transcription with Whisper

License:        AGPL-3.0-or-later
URL:            https://github.com/igorbispo99/ParrotIA
Source:         %{url}/archive/v%{version}/ParrotIA-%{version}.tar.gz

BuildArch:      noarch
# The whisper.cpp bindings (python3-pywhispercpp) are built for x86_64 only.
ExclusiveArch:  x86_64 noarch

BuildRequires:  python3-devel
BuildRequires:  desktop-file-utils
BuildRequires:  appstream
BuildRequires:  python3dist(pytest)
BuildRequires:  python3dist(numpy)

# Inference engine. Fedora does not package faster-whisper/CTranslate2/PyAV,
# so ParrotIA uses its whisper.cpp backend here.
Requires:       python3dist(pywhispercpp) >= 1.4
# Audio decoding (ffmpeg-free, or any other provider of the ffmpeg CLI).
Requires:       /usr/bin/ffmpeg
# GUI: Tk and Pillow's Tk bridge are not expressed in Python metadata.
Requires:       python3-tkinter
Requires:       python3-pillow-tk
Requires:       hicolor-icon-theme

%description
ParrotIA transcribes speech in audio and video files to text and subtitles
(TXT, Markdown, SRT, WebVTT, JSON) with Whisper models, running entirely on
the local computer. It provides a desktop application and a command-line tool
for batch jobs.

Speech models are downloaded on first use from Hugging Face, pinned to a
fixed revision and verified by SHA-256, into the user's data directory.


%prep
%autosetup -p1 -n ParrotIA-%{version}
# Requirements of the faster-whisper backend, which Fedora does not ship.
sed -i -e '/"faster-whisper>=/d' -e '/"av>=/d' pyproject.toml


%generate_buildrequires
%pyproject_buildrequires


%build
%pyproject_wheel


%install
%pyproject_install
%pyproject_save_files -l parrotia

# The Explorer queue integrates with Windows Explorer only.
rm %{buildroot}%{_bindir}/parrotia-explorer

desktop-file-install --dir=%{buildroot}%{_datadir}/applications \
    packaging/linux/%{app_id}.desktop
install -Dpm 0644 packaging/linux/%{app_id}.metainfo.xml \
    %{buildroot}%{_metainfodir}/%{app_id}.metainfo.xml
install -Dpm 0644 src/parrotia/assets/parrotia.png \
    %{buildroot}%{_datadir}/icons/hicolor/256x256/apps/%{app_id}.png


%check
desktop-file-validate %{buildroot}%{_datadir}/applications/%{app_id}.desktop
appstreamcli validate --no-net --explain %{buildroot}%{_metainfodir}/%{app_id}.metainfo.xml
# Mocked-model tests only: no network or model downloads. GUI tests skip
# without a display; faster-whisper-specific tests skip when it is absent.
%pytest -m "not slow"


%files -f %{pyproject_files}
%doc README.md CHANGELOG.md
%{_bindir}/parrotia
%{_bindir}/parrotia-gui
%{_datadir}/applications/%{app_id}.desktop
%{_metainfodir}/%{app_id}.metainfo.xml
%{_datadir}/icons/hicolor/256x256/apps/%{app_id}.png


%changelog
%autochangelog
