"""Cross-platform setup without activating a shell or opening applications."""
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

root=Path(__file__).resolve().parents[1]
if sys.version_info<(3,10):raise SystemExit('Python 3.10+ is required')
env=root/'.venv';python=env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
if not python.is_file():venv.EnvBuilder(with_pip=True).create(env)
npm=shutil.which('npm.cmd' if os.name=='nt' else 'npm')
if not npm:raise SystemExit('Install Node.js 20+ (including npm), then run this script again.')
subprocess.check_call([str(python),'-m','pip','install','-r',str(root/'requirements-lock.txt'),'-e',str(root)])
subprocess.check_call([npm,'ci','--no-audit','--no-fund'],cwd=root)
subprocess.check_call([str(python),'-m','math_testpaper','doctor'],cwd=root)
print('\nReady. Python for this repository: '+str(python))
