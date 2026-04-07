# -*- mode: python ; coding: utf-8 -*-
block_cipher = None

a = Analysis(
    ['launcher.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('fiji_scripts', 'fiji_scripts'),  # lands in _MEIPASS/fiji_scripts/
    ],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtNetwork',
        'cv2',
        'numpy.core._methods',
        'numpy.lib.format',
        'dotenv',
        'sqlite3',
        'src',
        'src.main',
        'src.config',
        'src.store',
        'src.frame_ingest',
        'src.fiji_runner',
        'src.parse_trackmate_outputs',
        'src.stitcher',
        'src.export',
        'src.visualize',
        'src.capture_controller',
        'src.frame_capture_models',
        'src.frame_capture_overlays',
    ],
    excludes=['pytest', 'black', 'flake8', 'mypy', 'tkinter'],
    hookspath=[],
    runtime_hooks=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='OncoTrack',
    debug=False,
    strip=False,
    upx=False,      # MUST be False — UPX corrupts PySide6/Qt DLLs
    console=False,  # No terminal window; change to True to debug startup errors
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='OncoTrack',  # Output folder: dist/OncoTrack/
)
