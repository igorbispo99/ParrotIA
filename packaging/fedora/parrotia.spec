%global appid io.github.igorbispo99.ParrotIA

Name:           parrotia
Version:        1.3.1
Release:        1%{?dist}
Summary:        Local audio and video transcription
License:        AGPL-3.0-or-later AND CC0-1.0
URL:            https://github.com/igorbispo99/ParrotIA
# Publish this sdist with the upstream release before requesting Fedora review.
Source0:        %{url}/releases/download/v%{version}/%{name}-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  pyproject-rpm-macros
BuildRequires:  desktop-file-utils
BuildRequires:  appstream
BuildRequires:  python3-tkinter
BuildRequires:  xorg-x11-server-Xvfb
BuildRequires:  xorg-x11-xauth
Requires:       python3-tkinter

%description
ParrotIA transcribes audio and video locally using faster-whisper. It provides
both a desktop application and a command-line interface, batch processing,
language detection, and text, Markdown, subtitle and JSON output.

Speech models are downloaded separately on first use. Once a model is cached,
transcription can run offline. Audio is processed on the local computer.

%prep
%autosetup

%generate_buildrequires
# Includes runtime dependencies and the test extra; never resolves from PyPI.
%pyproject_buildrequires -x dev

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files parrotia

desktop-file-install --dir=%{buildroot}%{_datadir}/applications \
    packaging/fedora/%{appid}.desktop
install -Dpm 0644 packaging/fedora/%{appid}.metainfo.xml \
    %{buildroot}%{_metainfodir}/%{appid}.metainfo.xml
install -Dpm 0644 src/parrotia/assets/parrotia.png \
    %{buildroot}%{_datadir}/icons/hicolor/256x256/apps/%{appid}.png

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/%{appid}.desktop
appstreamcli validate --no-net %{buildroot}%{_metainfodir}/%{appid}.metainfo.xml
%{py3_test_envvars} xvfb-run -a %{__pytest}

%files -f %{pyproject_files}
%license LICENSE packaging/fedora/CC0-1.0.txt
%doc README.md CHANGELOG.md
%{_bindir}/parrotia
%{_bindir}/parrotia-gui
%{_bindir}/parrotia-explorer
%{_datadir}/applications/%{appid}.desktop
%{_metainfodir}/%{appid}.metainfo.xml
%{_datadir}/icons/hicolor/256x256/apps/%{appid}.png

%changelog
* Fri Nov 13 2026 Igor Bispo <igor.rabbit99@gmail.com> - 1.3.1-1
- Initial native Fedora packaging candidate
