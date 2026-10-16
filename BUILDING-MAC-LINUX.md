# Building Mario Kart Wii for PS Vita with Python (macOS / Linux / Windows)

## Setting up the build environment (macOS / Linux / Windows)

This guide covers preparing a machine to build the **game files only**
(`build/vita/data/mkw`) with `build-game-files.py` — the path that needs no
VitaSDK. The project's own `BUILDING.md` covers the full VPK build.

You need **Python 3.14.5** ([recommended by the project](README.md#troubleshooting)),
[Node.js LTS](https://nodejs.org), [Git](https://git-scm.com), and the
`tex3ds` texture converter from devkitPro (see [below](#3-tex3ds)). OS versions:

| OS | Route to Python | tex3ds |
|---|---|---|
| macOS | pyenv, compiled from source | build from source (this guide) |
| Linux | pyenv or distro packages | devkitPro `dkp-pacman` or source |
| Windows | `py -3` (the `.bat` still works) | auto-fetched by the build |

---

## 1. Python 3.14.5 with pyenv

### Install pyenv

**macOS (Homebrew):**

```sh
brew install pyenv
echo 'eval "$(pyenv init -)"' >> ~/.zshrc   # or ~/.bashrc / ~/.profile
```

**macOS (MacPorts):**

```sh
sudo port install pyenv
# add the same `eval "$(pyenv init -)"` line to your shell rc file
```

**Linux:** use the [pyenv installer](https://github.com/pyenv/pyenv#automatic-installer):

```sh
curl https://pyenv.run | bash
```

then add the `eval "$(pyenv init -)"` line to your shell rc file. Keep pyenv
up to date (`git -C "$(pyenv root)" pull` or `pyenv update`) so new Python
versions are available.

### python-build dependencies

pyenv compiles CPython itself, so the C toolchain and key libraries must be
installed first:

| OS | Packages |
|---|---|
| macOS | Command Line Tools: `xcode-select --install`. A package manager for libs is not strictly required but helps (Homebrew: `brew install openssl readline sqlite3 xz zlib`; MacPorts: `sudo port install openssl readline sqlite3 xz zlib`) |
| Debian/Ubuntu | `sudo apt install build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev libffi-dev liblzma-dev` |
| Fedora | `sudo dnf install gcc make openssl-devel bzip2-devel readline-devel sqlite-devel libffi-devel xz-devel` |

### Install 3.14.5 and pin it

```sh
pyenv install 3.14.5
```

This compiles from source and takes **10–40 minutes** on a typical machine
(do not abort it — the log lines scrolling past are normal progress). The
repository already contains a `.python-version` file with `3.14.5`, so from
inside the repo `python` resolves to exactly that version:

```sh
cd <repo>
python --version     # Python 3.14.5
pyenv version        # 3.14.5 (set by <repo>/.python-version)
```

---

## 2. The virtualenv

Create the environment with the pinned Python and install the requirements:

```sh
cd <repo>
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt    # .venv\Scripts\python.exe on Windows
```

First-time note: `tools/bootstrap.py` must have cloned `vendor/gclib` and the
other pinned sources, or `pip install -r requirements.txt` fails. `build-game-files.py`
runs it automatically; by hand it is:

```sh
python tools/bootstrap.py
```

**Switching the Python version later** works without losing any build work:

```sh
rm -rf .venv
python -m venv .venv                 # now uses the new pyenv version
.venv/bin/python -m pip install -r requirements.txt
```

Cooked outputs (`build/`, `sd-card/`) and the step stamps in
`build/release/cook/` are independent of the interpreter, so nothing re-cooks.

---

## 3. tex3ds

`tex3ds` (devkitPro's texture converter) is required even for the
assets-only build. The cook scripts locate it through
`tools/devkitpro.py`, which resolves either

1. `$DEVKITPRO/tools/bin/tex3ds` (a system devkitPro install), or
2. `<repo>/.toolchain/devkitpro/tools/bin/tex3ds`

`tools/vita/build.py` checks both and, when it finds the second one, exports
`DEVKITPRO` for its own subprocesses. So a local copy in `.toolchain/` is all
that is needed (`.toolchain/` is gitignored).

### Windows

Automatic. `build.py` downloads devkitPro's `tex3ds-2.3.0` package
(checksum-verified) and unpacks it into `.toolchain/devkitpro/tools/bin/tex3ds.exe`.

### Linux

Install the devkitPro toolchain package manager, then the tool itself:

```sh
# one-time: install dkp-pacman and register the repos
# (see https://devkitpro.org/wiki/Getting_Started)
dkp-pacman -S tex3ds          # installs /opt/devkitpro/tools/bin/tex3ds
export DEVKITPRO=/opt/devkitpro
```

Verify with `tex3ds --version`. If you'd rather not install devkitPro, build
from source as on macOS and copy the binary into
`<repo>/.toolchain/devkitpro/tools/bin/`.

### macOS

devkitPro ships no macOS binary and their pacman repo has none, so build it
from source once. It is a small C++ program needing **ImageMagick
(Magick++)**, **FreeType**, and an autotools toolchain — on this machine
those come from MacPorts. (Homebrew equivalents of each package can be used
instead; adjust `PKG_CONFIG_PATH`.)

```sh
# deps (adapt for Homebrew: brew install imagemagick freetype autoconf automake libtool)
sudo port install ImageMagick freetype autoconf automake libtool

cd "$(mktemp -d)"
git clone --depth 1 --branch v2.3.0 https://github.com/devkitPro/tex3ds.git
cd tex3ds
./autogen.sh
PKG_CONFIG_PATH=/opt/local/lib/pkgconfig ./configure
make -j"$(sysctl -n hw.ncpu)" tex3ds

# place it where the build looks for it
mkdir -p <repo>/.toolchain/devkitpro/tools/bin
cp tex3ds <repo>/.toolchain/devkitpro/tools/bin/
```

The resulting binary links against the MacPorts/Homebrew libraries, so keep
the package manager's libraries installed. Verify: run
`<repo>/.toolchain/devkitpro/tools/bin/tex3ds --version`.

---

## 4. Building the game files

`build-game-files.py` is the cross-platform replacement for the Windows
`Build Game Files.bat`. It checks the tool versions, bootstraps the vendor
sources, creates/refills `.venv` when missing, then runs
`tools/vita/build.py --assets-only`, displaying the output while also
writing it to `build-assets-log.txt` (UTF-8).

Run it from the repository root:

```sh
# with the disc path as an argument (no prompt)
python build-game-files.py /path/to/RMCE01.wbfs

# or interactively: it asks you to drag/paste the disc image in
python build-game-files.py
```

On macOS it runs the cook under `caffeinate -d -i` so idle/display sleep
cannot stall the hour-long build.

### Resuming after an interruption

Every cook step stamps `build/release/cook/` when it finishes. If the build
is interrupted (Ctrl+C, power loss, shutdown), rerun the **same command**:
finished steps are skipped and only the interrupted step (and everything
after it) restarts. Nothing gets corrupted. Ctrl+C is handled cleanly and
prints:

```
Interrupted. Rerun the same command to resume; all finished steps are kept.
```

### After the build finishes

`build-game-files.py` prints `done:` for `build/vita/data/mkw`. Copy the
**contents** of that folder to `ux0:data/mkw/` on the Vita (the VPK itself
comes from the [releases](https://github.com/boomannotjeff/mkwiita/releases/latest)
on the same commit as these sources). The full console log is in
`build-assets-log.txt`.

### Troubleshooting

| Symptom | Fix |
|---|---|
| `Python 3.11 or newer is needed` | activate pyenv in the shell (`eval "$(pyenv init -)"`), then `python --version` |
| `Missing ...tex3ds` / `Install tex3ds from devkitPro...` | [section 3](#3-tex3ds) — build or install tex3ds into `$DEVKITPRO/tools/bin` or `.toolchain/devkitpro/tools/bin` |
| `Node.js LTS is needed` / `Git is needed` | install them and restart the shell |
| `This is an NKit image` | convert to a normal ISO in Dolphin first (right-click the game → Convert File → ISO) |
| `This is <region>... Only the USA version` | only Mario Kart Wii (USA), game ID `RMCE01`, is supported |
| `No disc image at: ...` | the path was not found (drag into the terminal keeps any spaces/quotes intact) |