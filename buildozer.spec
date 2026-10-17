[app]
title = MegaFlow
package.name = megaflow
package.domain = org.megaflow
source.dir = .
source.include_exts = py,html
version = 1.0
requirements = python3
orientation = portrait
android.permissions = INTERNET,WAKE_LOCK
android.api = 33
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
p4a.bootstrap = webview
p4a.port = 8000

[buildozer]
log_level = 2
warn_on_root = 1
