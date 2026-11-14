Name:           python-darkdetect
Version:        0.8.0
Release:        %autorelease
Summary:        Detect whether the desktop uses a dark theme

License:        BSD-3-Clause
URL:            https://github.com/albertosottile/darkdetect
Source:         %{pypi_source darkdetect}

BuildArch:      noarch
BuildRequires:  python3-devel

%global _description %{expand:
darkdetect reports whether the operating system is using a dark or light
theme, and can watch for changes. On Linux it reads the GNOME/GTK color scheme
setting; macOS and Windows are also supported.}

%description %_description


%package -n     python3-darkdetect
Summary:        %{summary}

%description -n python3-darkdetect %_description


%prep
%autosetup -p1 -n darkdetect-%{version}


%generate_buildrequires
%pyproject_buildrequires


%build
%pyproject_wheel


%install
%pyproject_install
%pyproject_save_files -l darkdetect


%check
# The macOS and Windows detectors import platform-only modules; upstream ships
# no test suite.
%pyproject_check_import -e darkdetect._mac_detect -e darkdetect._windows_detect


%files -n python3-darkdetect -f %{pyproject_files}
%doc README.md


%changelog
%autochangelog
