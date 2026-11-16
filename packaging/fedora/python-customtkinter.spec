Name:           python-customtkinter
Version:        6.0.0
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
# CTkImage, the usual way to show images in widgets, needs Pillow, but upstream
# does not declare it.
Recommends:     python3dist(pillow)

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

# CustomTkinter_shapes_font.otf deliberately stays inside the module instead of
# going into %%{_fontdir}. It contains no text glyphs, only the circles,
# checkmark and arrow shapes that CustomTkinter draws its rounded widgets with,
# and only CustomTkinter refers to it by family name. A system-wide install
# would put a font that cannot render text in every application's font menu,
# and the loader would have to be patched to stop copying it into ~/.fonts.


%check
# Upstream's test/ directory is not in the sdist and holds manual GUI scripts
# (windows and sleeps, no assertions), so an import smoke test is used instead.
%pyproject_check_import


%files -n python3-customtkinter -f %{pyproject_files}


%changelog
%autochangelog
