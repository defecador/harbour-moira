Name:       harbour-moira
Summary:    Privacy-friendly video streaming client
Version:    0.1.0
Release:    1
License:    GPLv3
URL:        https://github.com/defecador/harbour-moira
Source0:    %{name}-%{version}.tar.bz2

Requires:   sailfishsilica-qt5 >= 0.10.9
Requires:   qt5-qtdeclarative-import-multimedia
Requires:   pyotherside-qml-plugin-python3-qt5
Requires:   python3-base >= 3.11
Requires:   gstreamer1.0-plugins-good

BuildRequires:  pkgconfig(sailfishapp) >= 1.0.2
BuildRequires:  pkgconfig(Qt5Core)
BuildRequires:  pkgconfig(Qt5Qml)
BuildRequires:  pkgconfig(Qt5Quick)
BuildRequires:  desktop-file-utils

%description
Moira is a native Sailfish OS client for streaming video and audio without
accounts, ads or tracking. Extraction is handled by a bundled yt-dlp based
service; the interface is native Qt Quick / Silica.

%if 0%{?_chum}
Title: Moira
Type: desktop-application
DeveloperName: Guillermo Torres Belando
Categories:
 - Video
 - Network
Custom:
  Repo: https://github.com/defecador/harbour-moira
PackageIcon: https://github.com/defecador/harbour-moira/raw/main/icons/harbour-moira.svg
Screenshots:
 - https://github.com/defecador/harbour-moira/raw/main/screenshots/01-popular.png
 - https://github.com/defecador/harbour-moira/raw/main/screenshots/02-player.png
 - https://github.com/defecador/harbour-moira/raw/main/screenshots/03-quality.png
Links:
  Homepage: https://github.com/defecador/harbour-moira
  Bugtracker: https://github.com/defecador/harbour-moira/issues
%endif

%prep
%setup -q -n %{name}-%{version}

%build
%qmake5
%make_build

%install
%qmake5_install
desktop-file-install --delete-original \
  --dir %{buildroot}%{_datadir}/applications \
  %{buildroot}%{_datadir}/applications/*.desktop

%files
%defattr(-,root,root,-)
%{_bindir}/%{name}
%{_datadir}/%{name}
%{_datadir}/applications/%{name}.desktop
%{_datadir}/icons/hicolor/*/apps/%{name}.png
