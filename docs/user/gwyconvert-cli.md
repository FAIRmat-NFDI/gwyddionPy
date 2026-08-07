# The `gwyconvert` command-line interface

`gwyconvert` is the helper binary that reads a vendor file and writes a
Gwyddion-native `.gwy`. `gwyddionpy` runs it as a subprocess, but it is a
normal command-line program and can be used on its own — in a shell script,
a Makefile, or a workflow that has no Python in it.

This page is the written form of that contract. It matters more than it
looks: `gwyddionpy` and `gwyddionpy-converter` are released separately, so
an older Python package regularly runs against a newer binary. Anything
described here should be treated as an interface, not an implementation
detail free to change.

## Usage

```bash
gwyconvert INPUT OUTPUT.gwy    # convert one file
gwyconvert --list-formats      # report the formats this build can read
```

There are no other options. `--help` and `--version` are **not** supported
and are treated as a bad invocation (see below).

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success. The conversion was written, or the format list was printed. |
| `1` | The converter ran but could not do the job: the input could not be read, or the output could not be written. |
| `2` | The command was called wrongly — wrong number of arguments, or an unrecognised option. |

Note that `1` covers **both** an unreadable input and an unwritable
destination, so the exit code alone does not separate those two; the message
on stderr does (`cannot load` vs `cannot write`).

```bash
gwyconvert scan.spm scan.gwy && echo "converted"
case $? in
  0) : ;;                                  # fine
  1) echo "could not read or write" ;;
  2) echo "wrong invocation - fix the command" ;;
esac
```

## Output streams

**stdout carries the result and nothing else**, so it can be parsed
directly without filtering.

A conversion prints one JSON object naming the Gwyddion module that read
the file:

```console
$ gwyconvert sample.top sample.gwy
{"module": "wsxmfile"}
```

`--list-formats` prints a JSON array, one entry per format, each with the
keys `name`, `description`, `can_load`, `can_save` and `detectable`:

```console
$ gwyconvert --list-formats | head -3
[
  {"name": "accurell", "description": "Accurion exported ellipsometry data (.txt)", "can_load": true, "can_save": false, "detectable": true},
  {"name": "accurexii-txt", "description": "Accurex II text files (.txt)", "can_load": true, "can_save": false, "detectable": true},
```

**stderr carries diagnostics only**, and is silent on success:

```console
$ gwyconvert notes.txt out.gwy
gwyconvert: cannot load 'notes.txt': No module can load this file type.

$ gwyconvert scan.spm missing-directory/out.gwy
gwyconvert: cannot write 'missing-directory/out.gwy': Cannot open file for writing: No such file or directory.
```

### One caveat about stderr

Older bundles are noisy. GTK tries to load its accessibility modules and
GdkPixbuf looks for a loader cache at the path baked in by the build
container, producing several warnings on *every* run — successful ones
included — ending with advice to run a command as root that does not help:

```
Gtk-Message: Failed to load module "gail"
(gwyconvert.real): GdkPixbuf-WARNING **: Cannot open pixbuf loader module
file '/usr/lib64/gdk-pixbuf-2.0/2.10.0/loaders.cache': No such file...
```

None of it is a real diagnostic: `gwyconvert` draws nothing and the bundle
ships no pixmap module. Bundles built after this was fixed clear the two
variables in the wrapper script. If you are on an older bundle, or calling
the binary in an unusual environment, you can silence it yourself:

```bash
GTK_MODULES= GDK_PIXBUF_MODULE_FILE=/dev/null gwyconvert scan.spm scan.gwy
```

`gwyddionpy` sets both automatically, so nothing is needed when going
through the Python package.

## Other behaviour worth relying on

- **An existing output file is overwritten**, without prompting.
- **The input file is never modified.**
- **Relative and absolute paths both work.** The path you pass is recorded
  inside the resulting container, so converting the same measurement by
  relative and by absolute path produces files that differ in length while
  describing identical data.
- **Paths may contain spaces and non-ASCII characters.**
- **Numeric output does not follow the machine's locale** when invoked via
  `gwyddionpy`, which pins `LC_NUMERIC=C`. Calling the binary directly on a
  machine configured for German or French numbers will produce metadata
  values such as `0,881` instead of `0.881`; set `LC_NUMERIC=C` yourself if
  you intend to parse them.

## How gwyddionpy uses this

`gwyddionpy._run.run_converter` treats any non-zero exit as a failure and
then chooses the exception by looking for the phrase `cannot load` in
stderr: present means `UnsupportedFormatError`, absent means the more
general `ConversionError`.

> **Known weakness.** That is a match on diagnostic *text*, not on the exit
> code. Rewording the `cannot load` message in `gwyconvert.c` would silently
> reclassify every unsupported file as a generic `ConversionError`. The exit
> code cannot replace the check outright, because `1` covers unreadable
> input and unwritable output alike — but it could carry the part it does
> know: exit `2` means gwyddionpy built the command wrongly, which is a bug
> in gwyddionpy rather than anything about the user's file.

## Where this is enforced

`gwyddionpy/tests/converter/test_cli_contract.py` exercises every statement
on this page against the real binary — each exit code, stdout parsed as
JSON with nothing else in it, stderr silent on success, awkward path names,
overwrite behaviour and the input being left untouched. If you change the
CLI, that file is what should change with it.
