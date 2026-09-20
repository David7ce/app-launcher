App Launcher — Linux tarball
============================

Contents
  app-launcher          the program
  app-launcher.desktop  menu entry
  app-launcher.png      icon
  LICENSE

Requirements
  GTK 3 and WebKitGTK 4.1 (Debian/Ubuntu: libgtk-3-0 libwebkit2gtk-4.1-0,
  Fedora: gtk3 webkit2gtk4.1, Arch: gtk3 webkit2gtk-4.1).

Run it in place
  ./app-launcher

Install for your user
  install -Dm755 app-launcher      ~/.local/bin/app-launcher
  install -Dm644 app-launcher.desktop ~/.local/share/applications/app-launcher.desktop
  install -Dm644 app-launcher.png  ~/.local/share/icons/hicolor/512x512/apps/app-launcher.png

A Flatpak bundle is published alongside this tarball if you prefer a sandbox.
