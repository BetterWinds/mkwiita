#!/usr/bin/env python3
"""Build only the game files (build/vita/data/mkw).

Cross-platform replacement for Build Game Files.bat:
Use filename path as query parameter or drag your Mario Kart Wii (USA) ISO or WBFS into the prompt (or just press
Enter if the game files are already cooked), and this script sets up the
environment, builds the assets and writes a copy of the log to
build-assets-log.txt (UTF-8).

Needs Python 3.11+, Node.js LTS and Git (no VitaSDK); see BUILDING.md.
"""
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / '.venv'
VENV_PYTHON = VENV / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def fail(msg, url=None):
    print(msg + (f': {url}' if url else ''))
    sys.exit(1)


def run(cmd, **kw):
    print('$', ' '.join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], cwd=ROOT, check=True, **kw)


def build_command(disc):
    cmd = [VENV_PYTHON, 'tools/vita/build.py', '--assets-only']
    if disc:
        cmd.append(disc)
    # Keep the Mac awake while the cook runs (it can take over an hour).
    if sys.platform == 'darwin' and shutil.which('caffeinate'):
        cmd = ['caffeinate', '-d', '-i', '--'] + cmd
    return cmd


def tee_build(cmd, env, log_file):
    """Run the build, echoing to the console and writing the log at the same
    time. Interrupts (Ctrl+C, shutdown) are forwarded to the build and end
    cleanly: the cook stamps each finished step, so rerunning the same
    command resumes from where it stopped."""
    interrupted = []
    log_file.unlink(missing_ok=True)
    log = log_file.open('w', encoding='utf-8')
    proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, errors='replace')

    def forward(signum, frame):
        interrupted.append(signum)
        try:
            proc.send_signal(signum)
        except OSError:
            pass

    old_int = signal.signal(signal.SIGINT, forward)
    old_term = signal.signal(signal.SIGTERM, forward)
    try:
        for line in proc.stdout:
            print(line, end='', flush=True)
            log.write(line)
        proc.wait()
    finally:
        signal.signal(signal.SIGINT, old_int)
        signal.signal(signal.SIGTERM, old_term)
        log.close()
    if interrupted:
        print('\nInterrupted. Rerun the same command to resume; all finished steps are kept.')
        sys.exit(130)
    return proc.returncode


def main():
    os.chdir(ROOT)

    if sys.version_info < (3, 11):
        fail('Python 3.11 or newer is needed', 'https://www.python.org/downloads/')
    for tool in ('git', 'node'):
        if not shutil.which(tool):
            urls = {'git': 'https://git-scm.com/download/win', 'node': 'https://nodejs.org'}
            fail(f'{tool} is needed', urls[tool])

    if len(sys.argv) > 1:
        disc = sys.argv[1]
    else:
        disc = input('Drag your Mario Kart Wii (USA) disc image here and press Enter (or just Enter if already built): ').strip()
    disc = disc.strip('"')
    if disc:
        disc_path = Path(disc).expanduser()
        if not disc_path.is_file():
            fail(f'No disc image at: {disc}')
        disc = str(disc_path)

    if not (ROOT / 'vendor' / 'gclib').exists():
        run([sys.executable, 'tools/bootstrap.py'])

    if not VENV_PYTHON.exists():
        run([sys.executable, '-m', 'venv', VENV])
        run([VENV_PYTHON, '-m', 'pip', 'install', '-r', 'requirements.txt'])

    cmd = build_command(disc)
    env = dict(os.environ, PYTHONUTF8='1', PYTHONUNBUFFERED='1')
    log_file = ROOT / 'build-assets-log.txt'
    code = tee_build(cmd, env, log_file)
    print(f'Log: {log_file}')
    sys.exit(code)


if __name__ == '__main__':
    main()