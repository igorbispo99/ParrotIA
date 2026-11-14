Name:           python-customtkinter
Version:        5.2.2
Release:        %autorelease
Summary:        Modern, customizable widgets for Tkinter

# The LICENSE file is MIT. setup.cfg's "Creative Commons Zero" metadata
# contradicts it; the license text is authoritative.
# CustomTkinter_shapes_font.otf is the upstream author's own glyph font used to
# draw rounded widget corners, under the same license.
License:        MIT
URL:            https://github.com/TomSchimansky/CustomTkinter
Source:         %{pypi_source customtkinter}

BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  python3-tkinter

%global _description %{expand:
CustomTkinter is a Python UI library based on Tkinter that provides modern,
fully customizable widgets with light and dark appearance modes and HighDPI
scaling. Widgets can be combined with standard Tkinter elements.}

%description %_description


%package -n     python3-customtkinter
Summary:        %{summary}
Requires:       python3-tkinter
# Roboto is unbundled in favor of Fedora's font package (see %%install).
Requires:       google-roboto-fonts

%description -n python3-customtkinter %_description


%prep
%autosetup -p1 -n customtkinter-%{version}
find . -name .DS_Store -delete


%generate_buildrequires
%pyproject_buildrequires


%build
%pyproject_wheel


%install
%pyproject_install
%pyproject_save_files -l customtkinter

# Use the system Roboto instead of the bundled copies. On Linux CustomTkinter
# copies these files into ~/.fonts at startup, which follows the symlinks.
fontdir=%{buildroot}%{python3_sitelib}/customtkinter/assets/fonts/Roboto
for face in Regular Medium; do
    rm "$fontdir/Roboto-$face.ttf"
    ln -s %{_datadir}/fonts/google-roboto/Roboto-$face.ttf "$fontdir/Roboto-$face.ttf"
done


%check
%pyproject_check_import


%files -n python3-customtkinter -f %{pyproject_files}


%changelog
%autochangelog
