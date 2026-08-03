# DDD for VS Code

Reports the DDD consistency checks while a `*.ddd.json` is being written, and navigates between
the components that share a variable.

## What it is, and what it is not

This extension is a **launcher**. Everything you see comes from `ddd lsp`, the language server
that ships with the DDD python package, and works the same in any editor that can start a
language server - Neovim, Helix and Emacs need no extension at all. VS Code has no way to start
one without an extension, which is the only reason this exists.

So nothing here adds a feature, and nothing here should grow one that could be served from the
server instead.

## Installing it

It is **not on the marketplace**. Every release attaches a `ddd-<version>.vsix` to its
[GitHub release](https://github.com/Sauci/ddd/releases), which is a permanent link that needs
no account. Download that file, then either:

```bash
code --install-extension ddd-0.2.0.vsix
```

or, in VS Code, open the Extensions view, use the `...` menu at the top of it and pick
**Install from VSIX…**. Reinstalling the same way is how you update it; there is no automatic
update for an extension that did not come from the marketplace, so it is worth reinstalling
when you upgrade the python package.

For a build that has not been released yet, the CI run of any commit uploads the same file as
an artifact named `ddd-vscode-extension`. That one expires and does need a GitHub account, so
it is for trying a change rather than for handing to anybody.

## Requirements

DDD itself, and on the PATH the editor sees:

```bash
pip install ddd-tool
```

If `ddd` is on the PATH of your terminal but not of your editor - a virtual environment,
usually - set `ddd.executable` to its full path rather than fighting the PATH.

The two versions should match. The extension is only a launcher, so a mismatch usually still
works, but nothing checks it at runtime and a server older than the extension is the case
nobody has tried.

## What it gives you

Findings appear on open and on save, for **every** file of the project rather than only the one
on screen: half of a disagreement is always in the other component. What a json schema cannot
see is exactly what this reports - that an `axis` names an axis nobody declares, that two
components disagree about a unit, that nobody produces an input, that a name does not follow the
project's convention.

Both sides of a conflict are marked. Two components declaring the same output are equally part
of it, and a file with no finding on it would otherwise read as the correct one.

Hovering anywhere in a declaration shows what the project made of that variable - on the name,
on the datatype, on the scope, the same answer from all of them. That is the shape a curve took
from its axis, limits derived from a datatype and a conversion, who writes it and who reads it,
what an enum's numbers mean, and the initial values as a sparkline. Those are the values
compiled in at startup, not calibration data, which lives in the calibration tool rather than
here.

The `$schema` binding keeps documenting the keys themselves at the same time, from VS Code's
own json support: an editor shows every hover it is offered, so the schema explains what
`datatype` *is* while the server says what this particular object turned out to be.

Go to definition works from anywhere in a declaration - the same positions the hover answers
from - and lands on the declaration that **writes** that object; an `axis`, `x_axis`, `y_axis`
or `input` naming another object jumps to that one instead. Find references lists every
declaration of it. The same works from a `type` to the structure it nests, and from an
`includes` entry or a project's `naming` to the files they name.

The lightbulb on a `definition-mismatch` offers to reconcile it: put the cursor on the
`unit`, the `conversion` or any other key the declarations must agree on, and every other
declaration of that object is given the same value. VS Code shows the multi-file edit in a
preview first, so nothing changes without being seen. The value is copied as written rather
than re-serialised, and a declaration that never mentioned the key gets it inserted.

`F2` renames a variable across every component that declares it and every `axis`, `x_axis`,
`y_axis` or `input` that names it. A name c reserves, one that is not a usable identifier, or
one the project already declares is refused with the reason rather than half applied. Free text
is left alone, so a `description` mentioning the old name still mentions it.

The published json schemas keep working alongside this: they do structure, the server does
meaning.

## Settings

| setting | what it does |
| --- | --- |
| `ddd.executable` | the `ddd` command; a bare name is looked up on the PATH |
| `ddd.buildDirectories` | directories holding a build, each searched for the `ddd-build.json` that `ddd_generate()` writes. Empty searches the usual names next to the workspace |

Which project a file belongs to is not something the file can say - without `PROJECT`, CMake
collects the project out of the link graph - so the server reads that build record and applies
the same severities the build applies. A file no build claims is still checked, on its own.

## Building it

CI builds and tests this on every push and packages it on every release, so nobody has to
build one to use it. To work on it you need node 20 and DDD installed:

```bash
npm ci
npm test        # compiles, then runs the tests
npm run package # writes ddd-<version>.vsix
```

It is not in the project's docker image on purpose: carrying a second toolchain there would
cost everyone who only wants to compile c or build the documentation, and ci can put python
and node side by side with two actions.

The tests include one that starts the real server through the command this extension builds -
`ddd lsp`, with the `-b` flags the settings produce. That is the half of the agreement neither
side would otherwise notice breaking, which is why it needs DDD installed rather than only
typescript compiled.
