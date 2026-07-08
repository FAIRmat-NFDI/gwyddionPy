# Troubleshooting Log

Dated record of real problems encountered during development, their diagnosis,
and the fix. **Append an entry every time something non-obvious breaks** — this
file is the institutional memory of the project.

Entry template:

```
## YYYY-MM-DD — short title
**Symptom:** what was observed (exact error message if any)
**Cause:** what was actually wrong
**Fix:** what resolved it
**Prevention:** how to avoid it next time (if applicable)
```

---

## 2026-07-07 — No Gwyddion development headers on dev machine

**Symptom:** `pkg-config --exists gwyddion` fails; so do `gtk+-2.0` and even
`glib-2.0`, although the Gwyddion 2.60 *runtime* is installed at
`/usr/bin/gwyddion`.
**Cause:** Ubuntu splits runtime and development files; only the runtime
packages were installed.
**Fix:** `sudo apt install libgwyddion20-dev` (verified available via
`apt-cache search`); it pulls the GLib/GTK2 dev chain as dependencies.
**Prevention:** BUILD.md lists this as the first prerequisite.

## 2026-07-07 — libgwyddion20-dev installed, but pkg-config still fails

**Symptom:** after `sudo apt install libgwyddion20-dev`, `pkg-config --exists
gwyddion` still fails, although `/usr/lib/x86_64-linux-gnu/pkgconfig/gwyddion.pc`
exists and `pkg-config --list-all` shows gwyddion.
**Cause:** `pkg-config --exists` validates the whole `Requires:` chain of the
.pc file (`glib-2.0 gtk+-2.0 fftw3 pangoft2`), and Ubuntu's
libgwyddion20-dev does not pull those *-dev* packages in. Diagnose with
`pkg-config --print-errors --exists gwyddion` — it names the missing module.
**Fix:** `sudo apt install libgtk2.0-dev libfftw3-dev` (libgtk2.0-dev brings
the GLib/Pango/Cairo dev chain transitively).
**Prevention:** BUILD.md updated to list all three packages in one command.

## 2026-07-07 — pkg-config gwyddion also needs gtkglext (worked around)

**Symptom:** after installing libgtk2.0-dev + libfftw3-dev, `pkg-config
--exists gwyddion` still fails: `Package gtkglext-1.0 ... not found`.
Separately, `<libgwydgets/gwydgets.h>` (pulled by the `<app/gwyapp.h>` and
`<libgwymodule/gwymodule.h>` umbrella headers) fails to compile:
`fatal error: gdk/gdkgl.h: No such file or directory`.
**Cause:** Ubuntu built Gwyddion with OpenGL; its .pc file Requires
gtkglext-1.0, but libgtkglext1-dev is not a dependency of the dev package.
**Fix (chosen):** avoid the umbrella headers in gwyconvert.c — include only
`gwymoduleloader.h`, `gwymodule-file.h`, `app/settings.h`, and declare
`gwy_widgets_type_init()` directly (the symbol is in libgwydgets2, which we
link). The Makefile falls back to manual -I/-l flags when
`pkg-config --exists gwyddion` fails.
**Alternative:** `sudo apt install libgtkglext1-dev` makes the plain
pkg-config route work.

## 2026-07-07 — ALL gcc compiles fail: user's `as` alias shadows the assembler

**Symptom:** every gcc invocation exits 1 with no compiler error, only
`Warning: Input is not a terminal (fd=0).` Even hello-world fails.
**Cause:** `~/.local/bin/as` is a personal shortcut (`exec aws sts "$@"`) and
`~/.local/bin` precedes `/usr/bin` in PATH — gcc finds AWS CLI instead of the
GNU assembler.
**Fix (workaround):** build with `PATH=/usr/bin:$PATH make`. **Real fix
(user decision): rename the alias** — `as` is the GNU assembler's name, and
this silently breaks every C/C++ build on the machine.
**Prevention:** never name personal scripts after toolchain binaries
(`as`, `ld`, `cc`, `cpp`, `ar`, `nm`, ...).

## 2026-07-07 — Sample SPM files vanished after branch switch

**Symptom:** `ExampleFileForPersing/` and the earlier scripts are absent on
branch `PythonWrapper`.
**Cause:** the new branch was created from `main`; the experiment files live
only on `FileParserInPython` (committed there per the user, one commit ahead
of origin).
**Fix:** retrieve specific files without switching branches:
`git show FileParserInPython:PATH > file` or
`git checkout FileParserInPython -- PATH`.
**Prevention:** decide a permanent home for test data (CONTEXT.md OQ3) —
large binary samples generally should not live in git history; consider a
`test-data/` directory fetched by script, or Git LFS.
