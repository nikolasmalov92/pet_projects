# -*- mode: python ; coding: utf-8 -*-

# RegDevice.spec
# Сборка: pyinstaller RegDevice.spec

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        # === Selenium: Chrome ===
        'selenium.webdriver.chrome.webdriver',
        'selenium.webdriver.chrome.options',
        'selenium.webdriver.chrome.service',

        # === Selenium: Common ===
        'selenium.webdriver.common.by',
        'selenium.webdriver.common.keys',
        'selenium.webdriver.common.service',
        'selenium.webdriver.common.desired_capabilities',
        'selenium.webdriver.common.timeouts',
        'selenium.webdriver.common.actions.action_builder',
        'selenium.webdriver.common.actions.pointer_input',
        'selenium.webdriver.common.actions.wheel_input',

        # === Selenium: Support ===
        'selenium.webdriver.support.ui',
        'selenium.webdriver.support.expected_conditions',
        'selenium.webdriver.support.wait',

        # === Selenium: Remote ===
        'selenium.webdriver.remote.webdriver',
        'selenium.webdriver.remote.command',
        'selenium.webdriver.remote.webelement',
        'selenium.webdriver.remote.switch_to',
        'selenium.webdriver.remote.utils',

        # === Зависимости ===
        'chromedriver_autoinstaller',
        'urllib3',
        'certifi',
        'pkg_resources',
        'pkg_resources.py2_warn',
        'setuptools',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='RegDevice',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # False = windowed-режим (без консоли)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)