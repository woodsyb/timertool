"""Build script to create executable using PyInstaller."""

import subprocess
import sys
import os

def main():
    # Ensure PyInstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pyinstaller'])

    # Build command
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--name=TimerTool',
        '--onefile',
        '--windowed',
        '--add-data=timer.db;.' if os.name == 'nt' else '--add-data=timer.db:.',
        '--hidden-import=pystray._win32',
        '--hidden-import=PIL._tkinter_finder',
        '--hidden-import=babel.numbers',
        'main.py'
    ]

    print("Building executable...")
    print(" ".join(cmd))
    subprocess.check_call(cmd)

    print("\nBuild complete! Executable is in dist/TimerTool.exe")


if __name__ == '__main__':
    main()
