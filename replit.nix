{pkgs}: {
  deps = [
    pkgs.chromium
    pkgs.xorg.libXfont2
    pkgs.libxkbcommon
    pkgs.libdrm
    pkgs.mesa
    pkgs.pango
    pkgs.gtk3
    pkgs.glib
    pkgs.dbus
    pkgs.cups
    pkgs.cairo
    pkgs.at-spi2-atk
    pkgs.atk
    pkgs.alsa-lib
    pkgs.xorg.libxcb
    pkgs.xorg.libXrandr
    pkgs.xorg.libXfixes
    pkgs.xorg.libXext
    pkgs.xorg.libXdamage
    pkgs.xorg.libXcomposite
    pkgs.xorg.libX11
    pkgs.expat
    pkgs.nss
    pkgs.nspr
  ];
}
