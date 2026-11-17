# Manual release testing — images and commands

How to check by hand that a published release installs and runs. Run this
after every release, before announcing it.

`gwyddionpy` is pure Python and will import anywhere. The risk is entirely in
`gwyddionpy-converter`, which ships a compiled `gwyconvert` **plus the
Gwyddion and GTK/glib shared libraries it needs**. What can go wrong, and
what CI does not catch:

1. a library was left out of the bundle,
2. the binary needs a newer glibc than the wheel tag claims,
3. the lockstep pin resolves to the wrong converter version.

Wheels published for 0.0.18:

```text
manylinux_2_28_x86_64   macosx_10_9_x86_64   macosx_11_0_arm64   win_amd64
```

> **Docker covers one of the four.** Every image below is Linux x86_64 and
> exercises `manylinux_2_28_x86_64` only. macOS cannot be containerised on
> non-Apple hardware under Apple's licence, and Windows containers need a
> Windows host. See [Native macOS and Windows](#native-macos-and-windows).

## Use bare images

A wheel with a **missing bundled library still passes** on any machine that
already has that library — your dev box, a CI runner with Homebrew, a Windows
box with Visual Studio. The system quietly supplies what the bundle forgot,
and the release then breaks for a real user.

So: no `-dev` variants, no preinstalled build chains, nothing with Gwyddion,
GTK or glib already present. This is the single biggest way manual
verification gives a false green.

## Images

glibc versions below were measured, not assumed.

### Newest — upper bound

| Image | OS | glibc |
|---|---|---|
| `archlinux:latest` | Arch Linux (rolling) | 2.44 |
| `ubuntu:latest` | Ubuntu 26.04 LTS | 2.43 |
| `fedora:latest` | Fedora 44 | 2.43 |
| `opensuse/tumbleweed` | openSUSE Tumbleweed | 2.43 |
| `debian:latest` | Debian 13 (trixie) | 2.41 |
| `python:3.14-slim` | Debian 13 + Python 3.14 | 2.41 |
| `python:3.13-slim` | Debian 13 + Python 3.13 | 2.41 |
| `almalinux:latest` | AlmaLinux 10.2 | 2.39 |

### Pinned — regression range

| Image | OS | glibc |
|---|---|---|
| `ubuntu:24.04` | Ubuntu 24.04 LTS | 2.39 |
| `debian:12-slim` | Debian 12 (bookworm) | 2.36 |
| `python:3.12-slim-bookworm` | Debian 12 + Python 3.12 | 2.36 |
| `python:3.9-slim-bookworm` | Debian 12 + Python 3.9 — our minimum | 2.36 |
| `ubuntu:22.04` | Ubuntu 22.04 LTS | 2.35 |
| `ubuntu:20.04` | Ubuntu 20.04 LTS | 2.31 |
| **`almalinux:8`** | **AlmaLinux 8 — the `manylinux_2_28` floor** | **2.28** |

### Negative test — pip must refuse

| Image | OS | glibc |
|---|---|---|
| `ubuntu:18.04` | Ubuntu 18.04 | 2.27 — below the floor |

If the install *succeeds* here, the wheel's platform tag is wrong.

### Do not use

| Image | Why |
|---|---|
| `rockylinux/rockylinux:latest` | resolves to Rocky **8.6** (glibc 2.28), not Rocky 10 — pin `:10` |
| `quay.io/pypa/manylinux_2_28_x86_64` | the build image; its toolchain hides missing bundled libraries |

## Starting a container

Mount **only `gwyddionpy/tests/data`, read-only** — never the repo root. If
the source tree is visible, `import gwyddionpy` can pick up
`src/gwyddionpy/` instead of the installed wheel, and you would be testing
your working copy rather than the release.

Only the path syntax changes with the host. Run from the repo root.

**Linux**

```bash
docker run --rm -it --platform linux/amd64 \
  -v "$PWD/gwyddionpy/tests/data:/data:ro" \
  ubuntu:latest bash
```

On Fedora/RHEL hosts SELinux blocks the mount — use `:ro,Z` instead of `:ro`.

**macOS** — identical syntax:

```bash
docker run --rm -it --platform linux/amd64 \
  -v "$PWD/gwyddionpy/tests/data:/data:ro" \
  ubuntu:latest bash
```

The path must be in Docker Desktop's shared-folders list. On Apple Silicon,
`--platform linux/amd64` runs emulated — correct, just slow.

**Windows PowerShell**

```powershell
docker run --rm -it --platform linux/amd64 `
  -v "${PWD}/gwyddionpy/tests/data:/data:ro" `
  ubuntu:latest bash
```

**Windows CMD**

```bat
docker run --rm -it --platform linux/amd64 -v "%cd%/gwyddionpy/tests/data:/data:ro" ubuntu:latest bash
```

**Git Bash on Windows** — the prefix stops MSYS rewriting `/data` into a
Windows path:

```bash
MSYS_NO_PATHCONV=1 docker run --rm -it --platform linux/amd64 \
  -v "$PWD/gwyddionpy/tests/data:/data:ro" ubuntu:latest bash
```

## Environment inside the container

Always Linux, whatever the host. Debian/Ubuntu images ship Python without
`venv`; RPM images and `python:*-slim` include it.

```bash
# Ubuntu / Debian only
apt-get update -qq && apt-get install -y -qq python3-venv
# AlmaLinux / Fedora only
dnf install -y -q python3
```

With `venv`:

```bash
python3 -m venv /tmp/v
. /tmp/v/bin/activate
pip install --only-binary=:all: "gwyddionpy[converter]==0.0.18"
```

With `uv` — no activation needed, `--python` targets the venv directly:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv venv /tmp/v
uv pip install --python /tmp/v/bin/python \
  --only-binary=:all: "gwyddionpy[converter]==0.0.18"
```

`--only-binary=:all:` is deliberate: if no wheel matches the platform, pip
fails loudly instead of silently falling back to a source build — which is
itself part of what we are checking.

## Native macOS and Windows

For the two wheels Docker cannot reach.

| Platform | Where |
|---|---|
| `macosx_10_9_x86_64` | a clean Intel Mac, AWS EC2 `mac1.metal`, or GH Actions `macos-13` (last Intel runner) |
| `macosx_11_0_arm64` | any M-series Mac on macOS 11+, AWS `mac2.metal`, or GH Actions `macos-15` |

**macOS** — same as Linux:

```bash
python3 -m venv ~/gwytest
source ~/gwytest/bin/activate
```

Check you are not under Rosetta, or you will test the Intel wheel by mistake:

```bash
python3 -c "import platform; print(platform.machine())"   # must be arm64
```

**Windows PowerShell**

```powershell
py -m venv $env:USERPROFILE\gwytest
& $env:USERPROFILE\gwytest\Scripts\Activate.ps1
```

If that fails with "running scripts is disabled", it is the execution policy,
not your setup:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Or skip activation entirely and call the interpreter directly:

```powershell
& $env:USERPROFILE\gwytest\Scripts\python.exe -m pip install `
  --only-binary=:all: "gwyddionpy[converter]==0.0.18"
```

**Windows CMD**: `%USERPROFILE%\gwytest\Scripts\activate.bat`

**uv on Windows**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
uv venv $env:USERPROFILE\gwytest
uv pip install --python $env:USERPROFILE\gwytest\Scripts\python.exe `
  --only-binary=:all: "gwyddionpy[converter]==0.0.18"
```

### Activation, by environment

| Environment | Activate |
|---|---|
| Linux / macOS | `source .venv/bin/activate` |
| Windows PowerShell | `.venv\Scripts\Activate.ps1` |
| Windows CMD | `.venv\Scripts\activate.bat` |
| Git Bash on Windows | `source .venv/Scripts/activate` |

`bin` on Unix, `Scripts` on Windows — that is the whole difference.

## The checks

**Versions must match** — this is the lockstep pin:

```bash
pip list | grep gwyddion
```

**The binary must execute.** `list_formats()` shells out to the bundled
`gwyconvert`, so success proves it runs *and* resolves its libraries. A bare
`import gwyddionpy` proves neither and is not a sufficient test.

```bash
python -c "import gwyddionpy; print(gwyddionpy.__version__, len(gwyddionpy.list_formats()), 'formats')"
```

Expect 170 formats.

**A real file must read** — needs the mount above:

```bash
python -c "
import gwyddionpy
d = gwyddionpy.load('/data/bruker_spmlab/B3320_13_061726074638.SIG_TOPO_BKW.FLT')
print(gwyddionpy.__version__, d.source_format, list(d.channels))
"
```

Expect `spmlabf ['Height']`.

## Reading a failure

| Symptom | Meaning |
|---|---|
| `ImportError: lib*.so.N: cannot open shared object file` | a library was left out of the Linux bundle |
| `version 'GLIBC_2.xx' not found` | linked against a newer libc than `manylinux_2_28` claims |
| `dyld: Library not loaded` / `image not found` | missing or badly-pathed dylib in the macOS bundle |
| `DLL load failed while importing` | missing DLL or VC++ runtime on Windows |
| `ERROR: Could not find a version that satisfies` | no wheel for this platform — check the tag matrix |
| `gwyddionpy` and `gwyddionpy-converter` versions differ | the lockstep pin did not hold |

The first four are one class of bug: the wheel is not self-contained. All
four are invisible on a machine that already has the library, which is why
the bare-image rule is not optional.

## Results

| Platform | Image | Installs | `list_formats()` | Reads a file | Versions match |
|---|---|---|---|---|---|
| Linux floor | `almalinux:8` | ✅ | ✅ 170 | | ✅ 0.0.18 / 0.0.18 |
| Linux newest | `ubuntu:latest` | | | | |
| Linux minimum Python | `python:3.9-slim-bookworm` | | | | |
| Negative test | `ubuntu:18.04` | must refuse | — | — | — |
| macOS Intel | | | | | |
| macOS arm64 | | | | | |
| Windows | | | | | |
