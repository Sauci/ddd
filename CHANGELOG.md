# Changelog

Notable changes per release, newest first.  Versions follow
[semantic versioning](https://semver.org): while the major version is `0`, a minor bump may
change the file formats, and this file says how.

The check identifiers, the command names and their options, the json file formats - the
description files and, beside them, the address map, the dumped dictionary, the `--renames`
file and the `ddd-build.json` - the `ddd_generate()` and `ddd_add_component()` signatures and
the names a c template renders from are the tool's public interface, and a release that
changes one of them says here what the migration costs.  Anything else - the layout of the
generated c, the wording of a diagnostic - is not, and the templates a project provides are
its own.  A check identifier is the one entry of that list a release only ever adds to: a
name a project has written into a severity override does not change once it has been
published, as the specification requires ([section 4](SPEC.md#4-consistency-checks)).

## Unreleased

What the entries below ask of a user, grouped by who meets it: each item names the entry that asks
it and says what that entry says, and the entry has the rest.  An entry that says there is nothing
to migrate asks nothing and is not named.

A project built with CMake:

  - "Under Ninja, a build after a description change compiles the components whose header it
    changed": a component the image reaches only through a link made, or a library defined, after
    the directory calling `ddd_generate()` is done, or registered after it, now fails the configure,
    naming it: link it, define it or register it before the end of that directory; in the collected
    mode a renamed component needs a reconfigure, until then every build runs the generation and a
    change of that component's header reaches the components reading it a build late; and nothing in
    the calling directory can `APPEND` to the generation's command earlier, it being added at the
    end of that directory.
  - "With `ADDRESS_MAP`, the a2l carries the addresses of the image just linked": a project
    following the build page's recipe, whose extractor is a `POST_BUILD` command of the image,
    migrates nothing; a map written by any other step is written before `<stem>_ddd_a2l` runs; a
    build naming its targets builds `<stem>_ddd_a2l` too, and a target that depended on the
    generation for the a2l depends on `<stem>_ddd_a2l`; a project that defined a target of that name
    renames it; a `POST_BUILD` command of the image reading `DDD_A2L` reads the a2l of the build
    before; an a2l written with no address source says so in a comment under `ASAP2_VERSION`, so a
    step comparing a2l files byte for byte sees that line where it applies; under `STRICT` a map
    that leaves out a member of a structure now stops the first build, where it stopped the second;
    and a file named by `DEPENDS` still reruns the generation before the link, and no longer the a2l
    written after it.
  - "A call the module cannot honour fails the configure, naming why": a project file is given to
    `ddd_generate(... PROJECT <file>)` and not to `ddd_add_component()`; a value keyword is given a
    value, or the keyword and its value wrapped in `if()`; the `PROJECT` file is written before
    configuring; and C is enabled where `ddd_generate()` is called, by `project(<name> LANGUAGES C
    CXX)` or `enable_language(C)`.
  - "The configure follows the tool and the templates it renders with": a step that recovered a
    deleted output directory by hand can go, the configure reconfiguring by itself where a Ninja
    build stopped on the missing description; and `DDD_VERSION_HANDSHAKE` is no longer cached, the
    module asking `ddd --version` at every configure.
  - "Makefile generators leave a build that changed nothing with nothing to do": a step in another
    directory, or one reading a `{component}` header, depends on `<stem>_ddd_generation`, or on
    `<stem>_ddd_a2l` for the linked a2l, and not on a generated file's path; a file of the step
    deleted by hand is not written again until the step's stamp is deleted or the tree cleaned.

A description, a template and what the tool writes from them:

  - "`ddd id --assign` writes a description the way `ddd gui` does": a description that spells a key
    twice has to be corrected first, as `ddd check` has always asked; a read-only file is reported
    as one that cannot be written and left as it was, a link is written through to the file it names
    and stays a link, and a file `ddd check` would refuse to read is reported as not readable as
    json and left alone, each reported while the other files are stamped, and the run exits 1.
  - "A name that is a keyword of ASAP2 is an error, and a string or a name past the format's limits
    is named": the error costs a rename, and `-W a2l-keyword=ignore` relaxes it for a name the
    target's tool accepts; the warning stops a `--strict` or `STRICT` build, and `-W
    a2l-unrepresentable=ignore` lets it through.
  - "A size past 65,535 is named, once, where it is declared": a `--strict` or `STRICT` build with
    such a size stops; the cost is a smaller object, or `-W a2l-unrepresentable=ignore`.
  - "`--const-inputs` and `CONST_INPUTS` are gone, and a header that adds `const` is named": the
    option or the keyword, and any template line using `.const` on a header entry or
    `declaration(const=...)`, are deleted, and nothing replaces them; a `STRICT` build whose
    hand-written header adds `const` stops, until the header is fixed or `-W elf-mismatch=ignore`
    lets it through.
  - "`ddd generate a2l --image` warns where the image holds a variable otherwise than its
    description says": a `STRICT` build whose image disagrees with its description stops and writes
    no a2l, until it is fixed, or `-W elf-mismatch=ignore`, or `SEVERITY` in cmake, lets it through.
  - "An address the linker left meaningless is not placed": a variable with such an address has its
    a2l record at address 0 with a warning, where it had a wrong address, and a `--strict` or
    `STRICT` build now stops at it.
  - "An object the build compiled out is left out of the a2l, and a reference across conditions is
    checked": an `address-missing=info` lowering kept for this is dropped; a tool that expected the
    record, or its comment, finds none; a curve or a map over an axis so left out goes too, as the
    new warning `reference-left-out`, which stops a `--strict` build; and a project with a reference
    across conditions meets `condition-mismatch`, an error under `--strict`.
  - "A member's `SYMBOL_LINK` is where a linker map can find it": a script that matched a record by
    the spelling of its path in `SYMBOL_LINK` reads the variable and the offset instead.
  - "A structure member's `export: false`, `format` and `display_identifier` reach the records below
    it": a project that relied on the ignored block sees fewer records in the a2l, and a display
    identifier that was ignored now renames the records it stands for.
  - "The a2l's records, groups and methods are named and ordered the same way on every run": a
    project with two conversions in one unit, whose first holder changed, sees the two names swap
    between the records, which a tool that addresses a method by its name sees, and a `GROUP` lists
    the elements of an array of structures in the dictionary's order, `SA[1].v` before `SA[10].v`.
  - "Every component has an include guard of its own": a hand written reference to a guard that
    moved, such as an `#ifdef` on it, is changed; a template that builds a component's guard with
    `model.guard()` keeps the old collision.
  - "The example `ddd_globals.c` template keeps a definition through `--gc-sections`": a project
    that links with `--gc-sections` on ELF defines `DDD_RETAIN`, with `-D` or in a header the build
    includes first, and one that copied the example templates before copies the template to gain the
    macro.
  - "A reader of a variable's scale can follow its rescale": a project that copied the example
    templates earlier copies the `scale` macro of `_macros.jinja2` and its call to gain it.
  - "The a2l's addresses out of the linked image: `ddd generate a2l --image`": the a2l takes the
    byte order the image states, and a `--byte-order` that contradicts it is refused; `ADDRESS_MAP`
    and `--address-map` stay as they were, for an image without debug information.

A delivery comparison:

  - "A delivery that moves what a precompiled reader was built against is `changed-interface`": a
    released structure that has to grow grows at the end of a single variable's structure, or the
    finding is accepted for that delivery by relaxing `changed-interface`; a nested array whose size
    a constant names where a number did, or the other way, is accepted the same way, or keeps the
    spelling of the baseline; a `-W changed-storage=...` kept to let `volatile` turned on pass no
    longer reaches it; and a script that matched the old reorder message, said once at the
    structure, follows the new one, said at each variable.
  - "A constant that is gone stops a comparison, one that is new does not": a project that changes a
    constant between two deliveries relaxes `changed-interface` or `removed-constant`, or takes a
    new baseline; and a raster whose event or cycle changed is `changed-storage`, a warning and so
    an error under `--strict`, where it was no finding.
  - "A rename, or a narrowing by condition, of an object a component reads is an error": a project
    that relaxed `-W renamed-object=ignore` or `-W changed-condition=ignore` to accept such a
    delivery names `-W renamed-read-object=...` or `-W narrowed-condition=...` for that delivery.
  - "The limits of a measurement a component reads are graded by what its readers meet": a project
    that relaxed `-W narrowed-limits=ignore` for a measurement a component reads no longer has it
    reach it, and a `--strict` run now stops on a widened measurement; a delivery that moved a
    member's limits and changed its variable's kind, locality, type, shape or where its members lie
    meets the `changed-interface` alone, the limits told again once it is resolved.
  - "An output a component drops or changes is graded as one somebody reads": a project that relaxed
    `-W removed-object=...` to let an input go can drop it; one that relied on
    `removed-unused-object` for a dropped output names `removed-object` now; and a supplier whose
    gate passed the rename, the condition, the `volatile` or the wider range of an output relaxes
    the new id for that delivery; and `ddd compare`, `ddd check --baseline` without `--standalone`
    and the Compare tab read a component file given as the candidate as a project's file, so a
    supplier comparing two versions of a component with inputs uses `ddd check --baseline
    --standalone`, the command that takes the option.
  - "A broken baseline withholds nothing, a description baseline takes the project's relaxations": a
    baseline error a project relaxes no longer appears in its comparisons, and a script that matched
    the lone refusal of a broken baseline now finds the rest of the report after it; and a json that
    states no `format`, no `project` and no `component`, such as one holding only a `name`, is
    refused as `schema` wherever it is given as a delivery to compare, where it was compared as the
    removal of everything.
  - "A producer lost is `missing-producer`, said once, where the baseline had one": a project's own
    `-W missing-producer=ignore` silences it on every path, and a relaxation of `changed-owner` no
    longer reaches this pair; a component that turns an output into an input exits 1 under `ddd
    check --baseline --standalone` with or without `--strict`, as it exited 0 with a `changed-owner`
    warning.
  - "An initial value is compared as the bytes it stores, and one no double holds is refused": a
    `1e-400` written to mean zero is written `0`, and a comparison that was clean over a changed
    table, a square map and its transpose, or over `-0.0` against `0.0`, reports it.
  - "A structured variable's changes are told once, in order, and a variable with no leaf is
    compared": the new errors are relaxed by the ids they carry; and a structure variable with no
    leaf, one holding only members of external types, that is removed, renamed or reused is now
    `removed-object`, `removed-unused-object`, `renamed-read-object`, `renamed-object` or
    `reused-name`, where no finding was made.
  - "A structure member's `export: false`, `format` and `display_identifier` reach the records below
    it": `ddd compare` against a baseline 0.11.0 archived reports `changed-a2l` for every such leaf,
    and `ddd check --baseline --strict` of a project unchanged since exits 1 after the upgrade,
    until the baseline is dumped again with this version; the dumped dictionary is format 10, which
    0.11.0 refuses as the dictionary of a newer DDD, and a format 9 dictionary reads back unchanged.

A script or a client reading what the tool prints:

  - "`ddd check`'s count line agrees in number": a script matching the old line changes; and
    `--dictionary` naming `.ddd-manifest.json`, the file the run keeps its manifest under, is
    refused.
  - "`ddd sources` lists every file a build depends on, and a plugin's defect no longer hides them":
    the listing grows, and a script that took its length for something else changes; a plugin whose
    model raised, which ended the command with exit 2 and no listing, is the finding
    `plugin-invalid` beside the listing, exit 0.
  - "The a2l's `MOD_COMMON` states the image's alignments, and a run that defaults the byte order
    says so": a script that read the count of diagnostics from `--format json`, expecting none, now
    finds `byte-order-defaulted`, which `-W byte-order-defaulted=ignore` silences, as does stating
    the byte order.
  - "A position independent image, an unreadable map and two debug options say what they are": a
    build that counts its findings sees `image-load-relative`, which `-W image-load-relative=ignore`
    silences; and a map that is not UTF-8, one nested deeper than the interpreter reads and one
    holding an address of more digits than it converts are a usage error naming the file, exit 2,
    where they were Python's own words or a traceback with exit 1.
  - "A size past 65,535 is named, once, where it is declared": a script that read the text of such a
    warning, and its location, reads the new.
  - "A derived limit no longer stops short of the largest raw value": a script comparing the limits
    of an archived a2l or dictionary as text, or without a tolerance, sees the difference in the
    digits after the twelfth.
  - "A reader of a variable's scale can follow its rescale": a script that matched the title of the
    fix a `ddd gui` finding offers for a `definition-mismatch` matches the new one, which `GET
    /api/fix` returns.
  - "The Compare tab's verdict counts the project's own errors, and `GET /api/compare` says how
    many": the reply gains `own_errors`, an integer that is required, so that a client typed from
    the contract adds it, and one that reads the json ignores it.
  - "`ddd gui` says what to do when a launch code is presented again": a tool that matched the
    earlier text of the line `ddd gui` prints on stderr matches the new.
  - "An edit through `ddd gui` is held to what the reader could do by hand": a client that scripted
    `POST /api/edit` to change which plugins the project's descriptions name, or to create a file
    that is not a description, now gets the `409`; the page's own flows need nothing changed.
  - "`ddd gui --host` takes the two addresses `ddd gui` listens on": a `--host` naming any address
    but `127.0.0.1`, `0.0.0.0` or a name resolving to either is refused, exit 2, and a build script
    or a CI job that passed one gives `--host 0.0.0.0` instead.
  - "A types, units, constants, sections or rasters file may declare nothing, and `empty-vocabulary`
    says so": a tool that validates against the schemas of an earlier version refuses an empty list
    as the loader did, and a build that counts the findings it prints sees one info per such file,
    which `-W empty-vocabulary=ignore` silences.
  - "An include through a loop of links is a finding on python 3.12 too": `ddd check` reports the
    file it cannot read, at the entry naming it, where it ended in a traceback, and `ddd gui`
    answers a request naming a path through such a loop as one naming no file it can read, where it
    answered `500`.
  - "Every route of `ddd gui` reads its query through one typed model": a hostile or malformed value
    in a query, a body or a page's path is refused with a plain `400`, `404` or `409` and never a
    `500`, and an answer carrying json nested more than 99 levels deep is refused `409` rather than
    sent.
  - "`ddd gui` answers at most sixty-four connections at once": the sixty-fifth is refused
    immediately, `503`.
  - "`ddd gui`'s token is no longer a cookie": the page keeps the token in the browser's storage for
    its own address and sends it as a header, a cookie being no credential any more; a browser too
    old to send `Sec-Fetch-Site` lets any site open the page itself at an address it chooses, and
    the security page says what that allows.
  - "`ddd gui` refuses a request that says it came from somewhere else": in a browser that sends
    `Sec-Fetch-Site`, a page served from another port of `127.0.0.1` is refused rather than
    answered.
  - "`ddd gui` edits the value of a scalar and the description of a variable": `GET
    /api/description-plan` and `GET /api/value-plan`, like the rest of the api, are a preview's and
    change with the package.
  - "Six small edges of the edit engine are settled": a pointer's element is spelled with its
    brackets: `at` without them is refused, where `1` planned a key of its own.
  - "A constant's rename rewrites a condition that spells it, and its uses count conditions": a
    client of `GET /api/constant` reads a condition among a constant's `uses`, after the shapes, as
    a use of the variable whose declaration it guards.
  - "A plugin saved while `ddd gui` runs is told, by `plugin-changed`": a script that counts what
    `ddd checks` lists finds one more; a project that edits a plugin while `ddd gui` is open
    restarts the server, or relaxes `plugin-changed` with `-W`, `SEVERITY` in cmake or a build
    record; and a DDD from before declines a build record naming it, so a team on mixed versions
    that relaxes it upgrades its editors first.
  - "A plugin whose file cannot be read is `plugin-invalid` in every command": a project carrying a
    plugin that its build's account cannot read, with a valid bytecode cache beside it, makes the
    file readable.
  - "A refusal a page can mend is a refusal, and it names the file": a client that scripted `POST
    /api/edit` and answered the `500` of a read-only file answers the `409` `unwritable`, and one
    that read `stale` for a plan asked while the page's own edit waited meets `analysing` first and
    asks again once that analysis has landed.
  - "A finding leads to a panel that lists it, shows its place where it leads nowhere, and is
    counted once": a client typed from the page's contract adds `statements` to `State` and to `GET
    /api/compare`'s reply, and `line` and `column`, `null` where the loader gave none, to a finding,
    each required; one that reads the json ignores them.
  - "A read says why a declared name has no grid, and reads a type saved since the analysis": a
    client that matched the `404` of `GET /api/values` for a declared name, a structured variable or
    a dropped object, matches the `409` `invalid`.
  - "The state says why the last analysis failed, and which build record cannot be used": a client
    typed from the page's contract adds `failed` and `refused` to `State`, each required; one that
    reads the json ignores them.
  - "What did not load is said once, under the masthead of every page, with what to do next": a
    client typed from the page's contract adds `unreadable`, required, to the reply of `GET
    /api/projects`; one that reads the json ignores it.
  - "Compare names the baseline it was asked for, keeps it from tab to tab, and refuses one in plain
    sentences": a script that matched the refusal sentences of `GET /api/compare` for a baseline,
    `is unreadable:` and the system's words, or `outside the session root`, matches `is unreadable`
    and `outside the directory ddd gui was started in`.
  - "The page asks again where the server could not answer, and refuses before sending what the
    server would not read": a script that matched the text of the page the server serves to a
    browser that is not signed in matches the new.
  - "An edit whose file changed on disk leaves the undo stack, and a refused undo is offered again":
    `GET /api/undo` takes `at`, the number of the edit `State.undoable` names, and answers `400`
    without it.

An editor, or a client of `ddd lsp`:

  - "A file is checked under the outermost project that includes it, as `ddd check` checks it": a
    sub-project that is to be answered as itself in the editor has its build record name it; and
    opening a file imports the plugins of every description at or above it, up to its folder, so a
    repository is opened only when its build would be run.
  - "A rename reaches every project that holds a file it rewrites, or is refused naming the image":
    a name another image already uses, a type another image declares external, or a file of another
    image that did not load, or loaded with an error that stops the project being analysed, is dealt
    with there first, or the new name differs.
  - "A rename is refused where the editor could not see what it would change": an open document that
    differs from its file is saved, a project file is put above a component no record claims, or the
    build is configured, and a description a plugin stops is mended, and the rename is asked again;
    a closed file changed on disk is read again at the next open or save, or when the editor reports
    the change.
  - "An external type is not renamed, from the editor or from the page's Types tab": the c type in
    its header, and every entry and `typename` in the descriptions, are renamed by hand, together.
  - "A unit's rename is made over every image it reaches, or refused, naming the file": where the
    images it reaches share a units file and only one of them lists the unit renamed onto, the unit
    is listed in both or in neither, and the rename asked again.
  - "A request of another shape is refused, naming the field": a client that sent a field of another
    shape than the protocol gives it sends that shape, a capability or a `rootUri` among them, the
    handshake with one having been taken and now refused.
  - "The fixes of a `definition-mismatch` say what they leave alone, and the preferred one is the
    owner's": a client that matched a fix by its title matches the new, and a reader who applied the
    preferred fix of a variable that two components write, or none, picks one.
  - "An edit that reaches several files asks the client to confirm it": a client that announced both
    `documentChanges` and `changeAnnotationSupport` meets a prompt where the edit applied at once,
    and a reader may leave a file out, which applies it in part.
  - "A fix is offered once across the images it reaches, and not past a buffer that moved": a
    buffer that moved a declaration a fix writes is saved, and where the fix that respells an
    unknown unit is withheld because Rename Symbol is refused, the step that refusal names is taken,
    and the fix is offered again.
  - "The server asks the client to watch the descriptions and the build records": a client that
    announces the dynamic registration of watched files drops any watcher of its own for the server,
    which would send every change twice; one that does not is asked for nothing, and a file changed
    behind it is read again at the next open or save.
  - "A relative `ddd lsp -b` is read against each workspace folder": an editor that starts `ddd
    lsp -b <dir>` from a directory that is none of its workspace folders, meaning that directory,
    names it absolute.
  - "A change of `ddd.executable` or `ddd.buildDirectories` says it takes a restart": a change of
    either is followed by **DDD: Restart Language Server**.

A user of `ddd tool from-elf`:

  - "`ddd tool from-elf` reads a positive enumerator of a signed enum as positive": a component file
    or an interface written from an image with such an enumerator holds the wrong values, and is
    written again by `ddd tool from-elf` and the project generated again.
  - "`ddd tool from-elf` warns where a structure is laid out otherwise than the generated C would
    lay it out": a script that counts the findings, or a project that turns warnings into errors on
    its output, meets the new ones, and the only way to silence one is to change the source; two
    structures of one name that differ in a member's offset or in size are an `elf-type-conflict`
    error, where they were one entry.
  - "`ddd tool from-elf` refuses a debug-only file": a script that ran it over a companion file
    passes the linked image.
  - "`ddd tool from-elf` says where an image answers twice": a variable that was described silently
    from the first unit's answer is now an error naming both answers, and the units have to agree;
    one name at one address that two units give two sizes is `elf-type-conflict` and the variable is
    left out; two sections a linker script overlays that hold an address, with a symbol naming
    neither, are the error `elf-section-ambiguous`; a script that matched `duplicate-declaration`
    for a name asked for twice matches `elf-symbol-ambiguous` instead.
  - "`ddd tool from-elf` refuses the C++ it does not read": a project that relied on the wrong
    description describes those by hand.
  - "A name no unit gave storage is `elf-no-storage`, once": a script that matches the old
    identifier for such a name matches the new one.
  - "`ddd tool from-elf` writes no conversion it cannot know": the output pasted into a component is
    a `schema` error until its author states what raw is to physical, or runs with
    `--identity-conversions`.

`ddd gui`, and what its page takes:

  - "An edit of `ddd gui` is written whole, or refused, however many people write at once": a reader
    may meet a `stale` where the edit used to be written, and reads the project again and asks once
    more.
  - "`ddd gui` edits a hand-written project whose build record sits beside it": a record of a
    `PROJECT` build is stamped `format` 2, which a DDD from 0.11.0 on declines as written by a newer
    DDD and an older one skips in silence, so a team on mixed versions upgrades its editors with the
    module; a `PROJECT` with an older module's record beside it stays refused until the build is
    configured again.
  - "A float's values are written as floats, and a boolean's as booleans": a table pasted over a
    float array whose file spells whole numbers, or a cell typed or a table pasted over a boolean
    the file spells `1` or `0`, rewrites that spelling, and the diff shows it.
  - "A whole number a double cannot hold is never shown, or written, as another": a value or a limit
    at or past 2^53 is set in the file, in the editor.
  - "Every number the page takes is read in decimal notation, and in no other": a person who typed
    `0x1F` types 31.
  - "A unit with spaces around it is refused on a variable's panel and a type's": a unit typed that
    way is typed without them, and the route that settles a key and the type route answer 409 for
    one.
  - "A plan made over a file saved during the analysis is refused as `stale`": a plan whose file
    reads differently, or whose recorded place no longer names what was asked about, is refused as
    `stale`, and a settled value is refused as `unreadable` when its declaration moved.
  - "`ddd gui` writes nothing under the build tree of a generated project": a change of any file
    under the build tree that holds the record naming the description is refused as `generated`, and
    a new file is offered instead beside the first description outside the build tree that has a
    `CMakeLists.txt` beside it, with the `ddd_add_component()` line to add to it.
  - "A build record's `project` is read under the rule a request's path meets": a project whose
    record names a `project` that is not a path a request may name, or is not named `*.ddd.json`, is
    read as no record: it is not offered on the start page and its builds do not feed it when it is
    open; it is opened by its path on the command line, its records' severities still not applying
    to it.
  - "`localhost` is `ddd gui` itself, whichever of its two addresses a browser tries": a page opened
    at `localhost` is signed out until the address `ddd gui` printed is opened there; a fixed
    `--port` on which another program already listens at `[::1]` is refused before `ddd gui` starts,
    naming the port, and `--port 0` tries another.
  - "A file that cannot be written is refused before anything is, on every system, and what is
    written is synced": a file that is read-only, another user's, on a read-only mount, or to be
    written by root over a file nobody can write is refused as `unwritable`, naming it, with nothing
    written, where on Linux a read-only file was written through, silently.
  - "A rename, a removal or a declaration that produces a name is refused while a file of the
    project does not load": each is refused as `unreadable`, naming every file that did not load,
    until the file is repaired.
  - "A fix or a value that would leave a file unable to load is withheld, or said so": a fix is
    offered in the editor only for the declarations it leaves loadable, and on the page only where
    it leaves every one of them loadable; a value the variable's panel would write that leaves one
    unable to load is planned with a sentence naming the declaration and the file that would not
    load, drawn above Apply.
  - "A name another component keeps local is no longer offered to read": a name any component
    declares local is left out of what a component may read, and reading it is refused, saying whose
    it is.
  - "The Files tab's Remove panel waits when a row arrives from elsewhere": a row the page was
    loaded with - from a link, a bookmark, a typed address, a reload or a new tab - says that its
    removal is planned once asked, behind a button.
  - "A sign-in that gets no answer at all is retried once": a launch code whose first answer was
    lost is already spent, so that one case still ends signed out, with the terminal's reused-code
    line printed as a false alarm.
  - "The browser `ddd gui` opens for the reader is no longer launched on the long-lived token": it
    is launched on a one-time code, good for sixty seconds or one use.
  - "An external type is not renamed, from the editor or from the page's Types tab": a type renamed
    on the Types tab that is external is renamed by hand, in its header and in the descriptions, the
    page refusing it in the sentence the editor does.
  - "A constant's rename rewrites a condition that spells it, and its uses count conditions": a
    constant that only a condition spells, which the Shared files tab let go, is refused removal
    until the condition is changed.
  - "A type's change that the loader would refuse is refused, and a range is written as typed": a
    type changed to a datatype that is none, a maximum below its minimum or a conversion of factor 0
    is corrected before it is written, and a client that scripted one meets the `409` `invalid`.
  - "A description beside a build record that does not read is refused, and a description added to a
    generated project is offered its line": a description refused beside a record cut short waits
    for a configure of the build, which writes the record, and a description added to a generated
    project has the `ddd_add_component()` line the offer gives put in the `CMakeLists.txt` beside
    it.
  - "An edit may be as large as a large project's rename, and a plan too long for its address says
    so": a values table past about 10,000 counts is set cell by cell, or in its file in an editor;
    `POST /api/edit` takes a body of up to 8 MiB, and every other request keeps its 1 MiB.
  - "The page asks again where the server could not answer, and refuses before sending what the
    server would not read": an edit whose body passes 8 MiB is refused by the page before it is
    sent, in a sentence naming the edit and the limit: it is made in parts, or in an editor.
  - "An optional key emptied in its field is taken away, so that a raster is made acyclic from its
    panel": a description emptied in a raster's, a section's or a constant's panel is written as no
    key, where the empty text was written; a project that wants the key present with no text writes
    it in its file.
  - "An edit whose file changed on disk leaves the undo stack, and a refused undo is offered again":
    an edit whose file the reader put back by hand, byte for byte, after it changed on disk is not
    put back by the page, which has taken it off the stack; one whose file only could not be read or
    written stays.

An install and the tool's python:

  - "A toolbox, and its first tool: `ddd tool from-elf`": `pyelftools` 0.32 or newer is a new
    runtime dependency, which an air-gapped install brings with the wheel.
  - "`--const-inputs` and `CONST_INPUTS` are gone, and a header that adds `const` is named": code
    that builds `DeclarationView` or `COptions` by position or by the keyword breaks, they having
    lost `const` and `const_inputs`, and the `compile-const` service of `docker-compose.yml` is
    gone.
  - "`ddd generate a2l --a2l-module-fragment FILE` puts a project's own text at the head of the
    `MODULE`": code that builds `A2lOptions` by position meets its new fields: `alignment_cap`
    stands second, after `byte_order`, and `links`, `has_address_source`, `left_out` and
    `module_fragment` after `addresses`.
  - "The a2l's addresses out of the linked image: `ddd generate a2l --image`": a caller of
    `load_address_map` or `ADDRESS_PATTERN` takes them from `ddd.addresses` and not `ddd.backends`,
    `load_address_map` takes no `carried` any more, and a caller reading a map checks the 32-bit
    range of the addresses with `ddd.backends.weigh_addresses`.
  - "Every wheel ci builds and uploads says it is a development build": a job or a script that
    installed the artifact of a run and expected the last release's version, a requirement pinned to
    it, or a comparison of what `ddd --version` prints with it, meets the development version,
    `<next patch>.dev<run number>`, or after a release candidate the next candidate's; a wheel built
    from master's source with `python -m build` still carries the last release's.
  - "A release's page on PyPI links that release's own documentation": a tool that selects packages
    by the classifier `Operating System :: OS Independent` finds `Operating System :: Microsoft ::
    Windows` and `Operating System :: POSIX :: Linux` instead; and the links of a release's page
    into `v<version>/` do not resolve until Publish's run for it has succeeded and its documentation
    is published.

A build of DDD from its sources, and a release of it:

  - "The licences the wheel ships list every package its pages bundle": a build of the pages in a
    tree whose `node_modules` was not installed from the lock file, and holds a package or a version
    it does not, exits 1 naming each, and `npm ci` makes the two agree.
  - "A release is built only once every job of ci has passed on its commit, and its wheel is
    installed and run before anything is uploaded": a release waits for the whole of ci, and a
    failing gate fails Publish's run, to be run again as *Re-run failed jobs*, or, where the fault
    is in the tagged commit and nothing has reached pypi.org, its release deleted and created
    again; a build of the project from its sources by any frontend that isolates its build takes
    `hatchling` 1.33.0 and `hatch-requirements-txt` 0.4.1, so one with no index to reach has those
    two versions in what it reaches; and an environment installing `requirements-docs.txt`, or the
    `docs` extra, has its sphinx replaced by 9.1.1.
  - "A release's documentation is published once Publish's run for it has succeeded, and a push to
    master no longer cancels it": a release's documentation appears once Publish's run for it has
    succeeded; a release whose Publish reached PyPI and then failed is published by *Re-run failed
    jobs* of that run, and one no re-run can finish by a dispatch of Documentation from master
    naming the release's tag as `tag`, which refuses a version pypi.org holds no file of; a release
    that never reached pypi.org is deleted with its tag and created again.

* **`ddd id --assign` writes a description the way `ddd gui` does.**  It staged its text beside
  the file and renamed it into place by a writer of its own, which lacked what the page's has.  On
  Linux a file kept `0600` came out with the mode a new file gets, a file kept read-only was
  rewritten and left writable, and a symbolic link was replaced by a regular file holding the id,
  while the file it named stayed as it was, so a description shared between projects by a link was
  forked in silence; and a description was read by python's parser, so one that spells a key twice
  in an object, or holds `NaN`, which `ddd check` refuses as `json-syntax`, was stamped - `wrote 1
  id`, exit 0.  It now writes by the engine `ddd gui` writes with: the file keeps its mode, a
  read-only file is reported as one that cannot be written and left as it was, a link is written
  through to the file it names and stays a link, and a file `ddd check` would refuse to read is
  reported as not readable as json and left alone, whether or not it had an id to give.  Each is
  reported while the other files are stamped, and the run exits 1, as for any file it could not
  stamp.  The key goes right after the declaration's `name`, as it always did, and so now does the
  key the `missing-id` fix of `ddd gui` writes, which went after the object's last key.  A
  description that spells a key twice has to be corrected first, as `ddd check` has always asked.
  The time a file takes to stamp grows with the file, where it grew with its square.  No file
  format changes.

* **An edit of `ddd gui` is written whole, or refused, however many people write at once.**  Each
  write staged its files under a name every other write could take too, so two writers at the
  same moment could remove each other's stage and a description lost its text.  Every write now
  stages under a name of its own, beside the file.  And a file saved from outside while an edit
  was being written, between the moment the page last read it and the rename, was overwritten
  and the edit answered as written; each file is now read once more right before it replaces the
  file, and a change since the analysis is refused as `stale`, with every file as it was - all but
  a save landing in the instant between that last read and the rename, which is still written
  over.  An undo, and the rollback of an edit that is refused, put back only the files that still
  hold what the edit wrote: a file saved since is left as it was saved, and named.  A reader may
  now meet a `stale` where the edit used to be written; the answer is to read the project again
  and ask once more.  No file format changes.

* **A plan made over a file saved during the analysis is refused as `stale`.**  The plan of an
  edit, a rename or a settled value took the places the analysis recorded, and when a file had
  been saved while that analysis ran, those places were where the old text had been: the plan
  rewrote another declaration, value or entry than the one asked about, and applying it wrote
  the wrong one.  The analysis now records a fingerprint of the bytes it read, and a plan
  whose file reads differently, or whose recorded place no longer names what was asked about -
  an entry of a type put in above it or taken out since - is refused as `stale`, and a settled
  value is refused as `unreadable` when its declaration moved.  No file format changes.

* **A refused `stale` edit or undo asks for the analysis that clears it.**  A file saved with
  the size and the modification time it had before is a change the project's poll cannot see,
  so no analysis was asked for, every plan kept the fingerprint of the old bytes, and every
  edit was refused as `stale` for good while the revision never moved.  The refusal now asks
  for the analysis itself, as the poll does for a change it sees, so that the next plan is made
  over the bytes on disk.  The refusal stands whether or not that analysis succeeds, and one
  that fails is printed as any other, and asked for again by the next poll.  On the page, the
  sentence saying a file changed on disk now stays until the reader chooses again in its panel,
  as every other refusal does, where it went with the next revision, which now comes at once.
  No file format changes.

* **`ddd gui` writes nothing under the build tree of a generated project.**  Where
  `ddd_generate()` writes the project's description at every configure, `ddd gui` took it for
  one somebody wrote: New file and Add a file, and Remove, changed it or created files beside it
  in the build tree, were answered as done, and the next configure undid them, or the build
  tree took them away.  It now refuses a change of any file under the build tree that holds the
  record naming the description, as `generated`, whichever file it is, and the sentence says
  that which files belong to the project is `ddd_add_component()`'s to say.  A new file is
  offered instead beside the first description outside the build tree that has a
  `CMakeLists.txt` beside it, with the `ddd_add_component()` line to add to it.  The
  components themselves are edited as before.  A build record written by a newer DDD no longer
  hides that the description is generated.  No file format changes.

* **Under Ninja, a build after a description change compiles the components whose header it
  changed.**  The per-component headers a description change rewrites were not declared as
  outputs of the generation, so a component reading one was compiled against the old header and
  linked with the new globals: the build exited 0, and only a second build compiled it again.
  `ddd_generate()` now declares the header of every component the image links, named at
  configure from `ddd_add_component()`, or from `ddd sources` with `PROJECT`, so the build
  recompiles exactly the components whose header changed, and `ninja -t clean` removes those
  headers too.  A plugin's files are still declared by nothing, their names being the plugin's,
  so a component compiling one meets a change of it a build late; the build page says how a
  project has a description change reach such a component in one build.  Migrating costs
  three things.  A component the image reaches only through a link made, or a library defined, after
  the directory calling `ddd_generate()` is done, or registered after it, now fails the configure,
  naming each such component and what to do; link it, define it or register it before the end of
  that directory.  In the collected mode a renamed component needs a reconfigure: until then every
  build runs the generation, and a change of that component's header reaches the components
  reading it a build late.  And the generation's command is now added at the end of the
  calling directory, so nothing there can `APPEND` to it earlier.  A generator expression in a link
  list counts whatever it comes to, except `$<CONFIG:...>` around plain names, which is read for
  `CMAKE_BUILD_TYPE`.  Under Makefile generators the generation is built as the entry on them below
  says.  No file format changes.

* **With `ADDRESS_MAP`, the a2l carries the addresses of the image just linked.**  The generation
  before the link read the map the previous link had extracted, so the a2l of a build held the
  addresses of the image linked before it - every one 0 on the first build of a clean tree, the old
  address of a variable an edit moved - with no finding, `STRICT` or not, and under `STRICT` an
  object added to a description stopped every build.  The generation before the link now leaves the
  a2l out, and `<stem>_ddd_a2l`, built by default, writes it once the image is linked, from the
  image and the map, as `ADDRESSES_FROM_IMAGE` has always done; `BYTE_ORDER` goes to that step.  A
  project following the build page's recipe, whose extractor is a `POST_BUILD` command of the image,
  migrates nothing.  A map written by any other step has to be written before `<stem>_ddd_a2l` runs;
  `--target <image>` and `<stem>_ddd_generation` no longer write the a2l, so a build naming its
  targets builds `<stem>_ddd_a2l` too, and a target that depended on the generation for the a2l
  depends on `<stem>_ddd_a2l`; a project that defined a target of that name renames it; a
  `POST_BUILD` command of the image reading `DDD_A2L` reads the a2l of the build before.  Under
  `STRICT`, a map that leaves out a member of a structure now stops the first build, where it
  stopped the second.  An a2l written with no address source now says so in a comment under
  `ASAP2_VERSION`, so a step comparing a2l files byte for byte sees that line where it applies.
  `A2lOptions` also gains `has_address_source`, for the comment under `ASAP2_VERSION`.  A
  file named by `DEPENDS` still reruns the generation before the link, and no longer the a2l written
  after it.

* **`ddd sources` lists every file a build depends on, and a plugin's defect no longer hides
  them.**  It listed a plugin only when the plugin imported, and a package plugin only by the
  files it had imported, so a file that stopped importing, or that nothing had yet imported, was
  no dependency of the configure; and a plugin whose model raised ended the command with exit 2
  and no listing at all.  It now lists every `.py` file of each plugin a project names, a module
  plugin by the files the finder locates, in the json `sources` too, and reports a plugin's
  defect as the finding `plugin-invalid`, printed next to the listing by `sources` and by
  `artefacts`, with exit 0.
  `ddd check`, `list`, `dump` and `generate` print the findings gathered before such a defect,
  and `check --format json` prints its document, still with exit 2.  `ddd sources` takes `-W` and
  `--strict`, which grade what it reports on stderr and never the listing or the exit code, and
  the module passes the call's `SEVERITY` and `STRICT`, so the configure's warning is graded as
  the build is.  The listing grows; a script that took its length for something else has to
  change.

* **A file that a wildcard include gains or loses re-runs the build.**  A project's `includes`
  wildcards were read at configure only, so a file one began to match touched nothing the build
  watched, and a file one stopped matching left the generation's inputs the same or fewer: both
  ended in `no work to do` over a stale dictionary.  The module now watches every wildcard, those of
  the projects included as well, so such a file re-runs the configure, and the generation and the
  a2l step when a file leaves.  The configure writes `<stem>_ddd_sources.txt`, new, in the call's
  binary directory, rewriting it only when it differs.  A `**` include is scanned at every build.
  Nothing to migrate.

* **A call the module cannot honour fails the configure, naming why.**  `ddd_add_component()` took a
  project file for a component's description, and the next configure found no components; it now
  refuses a description whose top-level key is `project`, naming `PROJECT` of `ddd_generate()`.  A
  call that gave a value keyword an empty variable in quotes, `ADDRESS_MAP "${DDD_MAP}"`,
  configured with the keyword dropped - every address 0 for `ADDRESS_MAP`, the collected mode for
  `PROJECT` - the bare form being refused since 0.10.0, and an empty value among several was
  dropped, or stopped the configure or the build on words that did not name it; each now fails
  the configure, naming the keyword, for every empty value of a value keyword of `ddd_generate()`
  or `ddd_add_component()`.  A `PROJECT` has to exist, parse and name its project when the
  configure runs, where a missing one in the build tree, or one that did not parse, was warned of
  and then stopped the configure on CMake's own words, which name neither cause; and C has to be
  enabled in the directory calling `ddd_generate()` by the time it is done, where a project that
  had not enabled it failed at CMake's generate step, which could not determine the linker
  language of a target of the module's.  Migrating costs a line each.  Pass a project file to
  `ddd_generate(... PROJECT <file>)`, not to `ddd_add_component()`.  Give a value keyword a value,
  or wrap the keyword and its value in `if()`.  Write the project file before configuring.
  Declare `project(<name> LANGUAGES C CXX)`, or call `enable_language(C)` there or above.  The
  advice of the refusal of a late link and the reason of the one for `PROJECT` are reworded.
  `ddd sources` is read as UTF-8, so a Windows checkout under a non-ASCII path builds.

* **Makefile generators leave a build that changed nothing with nothing to do, and `make clean`
  cleans it.**  Under a Makefile generator a generation that changed nothing ran again at every
  build, and an edit that left a component's header as it was recompiled the component all the same,
  since every file of the step after the first was touched by each run, `ddd_types.h` among them;
  and the a2l step after the link, which `ADDRESSES_FROM_IMAGE` alone had, read the image again at
  every build.  Each step now has a stamp of its own as its one output - `ddd-generation.stamp`
  and `ddd-a2l.stamp` - touched by each run that succeeds, and a rule per shared file depending on
  the step, so a step that depends on the dictionary's or the pre-link a2l's path in the calling
  directory still runs after the generation; `make clean` removes the step's files, a plugin's
  apart, which nothing declares.  Migrating costs a line for a step in another directory, or one
  reading a `{component}` header: it depends on `<stem>_ddd_generation`, or on `<stem>_ddd_a2l`
  for the linked a2l, and not on a generated file's path.  A file of the step deleted by hand is
  not written again until the step's stamp is deleted or the tree cleaned.

* **The configure follows the tool and the templates it renders with.**  The module asked
  `ddd --version` once and cached the answer as `DDD_VERSION_HANDSHAKE`, so a tool upgraded in
  place was met only by a fresh build tree; it now asks at every configure, once, and the
  variable is no longer cached.  A template directory whose path holds `[`, `*` or `?` is found;
  every `*.jinja2` below it is a dependency, listed in `<stem>_ddd_templates.txt`, new, in the
  call's binary directory; and a removed template's file is taken back.  A deleted output
  directory reconfigures by itself, where a Ninja build stopped on the missing description until
  somebody configured by hand, so such a step can go.  A description the build itself writes,
  which does not exist yet at configure, is watched, so the first build to find it there
  configures again; a status line says so, where the configure said nothing of such a file.

* **`ddd check`'s count line agrees in number, and a dictionary cannot take the manifest's name.**
  The line read "1 variable in 1 component are consistent" for a single one, and now reads "1
  variable in 1 component is consistent"; a script matching the old line has to change.
  `--dictionary` naming the file the run keeps its manifest under, `.ddd-manifest.json`, is refused
  for that.  The page of `<target>.ddd` now says what the behaviour already was: it checks a
  component under the default policy, not the image's, so the promise that the image's checks cannot
  drift apart covers `ddd build-info`, `ddd check` and `ddd generate`.

* **`ddd gui` edits a hand-written project whose build record sits beside it.**  A record in the
  build tree made the project look generated, so a description written by hand under `PROJECT`
  was refused as `generated`.  `ddd-build.json` now says where its description came from:
  `origin: "given"`, written only for a description given as `PROJECT`, and `ddd gui` edits a
  project only where its record says so.  A record without the key reads as collected, and one of
  a collected build is unchanged, format 1 with no key; `ddd build-info` gains `--origin
  {collected,given}`, default `collected`.  Migrating concerns records of `PROJECT` builds alone,
  which are stamped `format` 2: a DDD from 0.11.0 on declines such a record as written by a newer
  DDD, and says so, and an older one skips it in silence, so a team on mixed versions upgrades its
  editors with the module.  A `PROJECT` with an older module's record beside it stays refused
  until the build is configured again.

* **`ddd gui` edits the value of a scalar and the description of a variable.**  A plain
  calibration parameter or measurement, the commonest value in a project, had no control on the
  page and no sentence saying so: its row had no Shape button, its panel listed neither its
  `init` nor its description, and its values page answered that it had no cell for a value to sit
  in.  A scalar's Shape column now reads `scalar` and opens its values page as a grid of one
  cell - physical or raw by the toggle, its value one `set` at the declaration's own `init`,
  added where the file states none - with no table to paste and no picture of one point.  A
  variable's panel, opened from a component's page, holds that component's own description of it
  as a text field, planned, previewed, applied and undone like the panel's other keys; emptying
  the field takes the key away.  Renaming a variable and changing its scope stay in the file, in
  the editor, and the panel says so.  `GET /api/description-plan` is the plan of the description,
  and `GET /api/value-plan` takes a blank `at` for a scalar; the api is a preview's and changes
  with the package.  No file format changes.

* **A whole number a double cannot hold is never shown, or written, as another.**  The page holds
  a number as a double, which past 2^53 no longer holds every whole number, so a `uint64` block of
  9007199254740993 and 18446744073709551615 was drawn as ...992 and 18446744073709552000, and a
  mask such as 0x8000000000000001, typed or pasted, was written into the file as
  9223372036854776000 - another number than the one asked for.  Such a number is now refused where
  it is typed or pasted, in one sentence, whatever its spelling; the values reply marks a block
  whose values or axis hold one (`unshown`), and the grid says it cannot show it where it drew a
  rounded number; a limit stated past 2^53 shows in its file's own digits, and the page refuses a
  limit typed past it; and the server refuses a whole value at or past 2^53 for a `uint64` or a
  `sint64`, and a limit at or past it however it is written, in digits or as a float.  A value or a
  limit that large is set in the file, in the editor.  No file format changes.

* **Every number the page takes is read in decimal notation, and in no other.**  The grid's cells
  and a paste took what the browser's parser takes, so `0x10` set 16 and `Infinity` was sent on,
  while a range's two fields, a size, a dimension, a constant's Value, a section's alignment and a
  raster's event each read a number their own way, and left a number written otherwise to the
  server or to json to refuse in their words.  All of them now read an optional sign, digits with
  an optional fraction or a fraction alone, and an optional exponent, the white space around it
  ignored; hexadecimal, binary, octal, `Infinity`, `NaN` and digits parted by underscores are
  refused in one sentence, the same in every field, and nothing is sent for them, but a size and a
  dimension, which may name a constant, read `Infinity` and `NaN` as names, as they read any name.
  A boolean takes 0 and 1 alone, in Raw and in Physical, where Physical rounded 0.6 to 1.  A
  person who typed `0x1F` types 31.  No file format changes.

* **A decimal comma is read as one where it cannot group thousands.**  A block pasted from a
  spreadsheet of a comma locale, `0,125 0,250 0,500`, was refused, and the page's advice was to
  paste the column unformatted; that advice is gone.  A comma is now a decimal point where it
  cannot group thousands, after a first group of 0 or of more than three digits or before anything
  but exactly three, and groups thousands where it cannot be a decimal point; text holding both
  has its decimal point last.  Values read together, a pasted block or the cells typed into a
  grid, read a comma that could be either as the others show theirs, and a pasted block that shows
  both readings is refused, in a sentence saying what it mixes.  In the grid a comma that could be
  either, `1,500` alone, is asked about with a choice of one press, "A decimal point: 1.5" or "A
  thousands separator: 1500", and the answer given stands whatever is typed after it; the other
  fields refuse such a comma in the same sentence, a range's naming the field it is about.
  Nothing to migrate.

* **A number typed in the grid is written as the nearest the datatype holds, and shown with the
  digits it needs.**  A physical value was worked out in double arithmetic, so 0.7 at a factor of
  0.1 was written into a float as 6.999999999999999, a value of more than twelve digits was shown
  cut (1234567890123 as 1234567890120), and a `float32` the file spells at double precision showed
  the digits of the double.  A physical value now comes to the nearest count, worked out on the
  decimals typed and the conversion's own, an exact half going to the even count as the server
  rounds it; a physical value typed into a float is planned as the shortest float that comes back,
  so 0.3 at a factor of 0.1 writes `3.0`; and a `float32` reads as the float32 its file's number
  rounds to, so a file's 0.10000000149011612 reads 0.1.  FLT_MAX is planned, and read in Raw, as
  its own double, 3.4028234663852886e+38: its shortest spelling, 3.4028235e+38, is a double past
  it, which the server and `ddd check` refuse a `float32`; so a `float32` cell's Raw entry is
  planned as the float32 it rounds to, and C's `3.4028235e38` plans FLT_MAX's own double.  Physical shows the exact product of
  the count and the factor for a whole datatype, 255 counts of 0.03 as 7.65, and the shortest
  decimal for a float, never cut at twelve significant digits.  A number past what a double
  holds is refused on the page, and so is one that rounds to zero in its float, typed in Physical;
  in Raw the page refuses one only where its double is zero, so a `float32` cell's `1e-50` is sent
  and the server refuses it.  No file format changes.

* **A float's values are written as floats, and a boolean's as booleans.**  The grid wrote a
  float's whole value as `3`, which spells an integer, and a boolean's as the count the page
  sends, so a `false` set to 1 and back was written `1` and then `0`.  It now writes `3.0`, the
  zeros it fills out an array with `0.0`, a float variable's or type's limits `-50.0` and
  `90.0`, and a boolean's value `true` or `false`, the zeros of a boolean array `false`.
  Migrating costs a diff: a table pasted over a float array whose file spells whole numbers, or
  spells a `float32` at double precision, rewrites that spelling, and so does a cell typed, or a
  table pasted, over a boolean the file spells `1` or `0`, which is rewritten `true` or `false`;
  the diff shows it.  The values mean the same.

* **The values grid takes several cells at once, and draws what the file states.**  The 0.11.0
  notes say "One cell is changed at a time", and that no longer holds: the cells typed into are
  held together, each showing what was typed, and planned as one change with one sentence, one
  Apply and one undo, each written at its own element where the array is long enough, so cells
  nobody typed keep their spelling; where the file states one value for every cell, states none
  or writes too short an array, the whole `init` is written, as the preview shows.  The page asks
  `GET /api/cells-plan` for them.  A cell typed back to its file's value offers nothing, and a
  plan whose edit would change no byte, a table pasted over the values the file spells, offers
  no Apply and answers `changes: []`.  A cell is sized to its text, and the offer stays at the
  window's foot while a cell is open, instead of below the grid.  Columns and rows come from the
  object's shape, a breakpoint labelling its own column.  A cell the file does not state, past a
  short `init` or any cell of a declaration with no `init`, is drawn hollow and named so, where
  the second read as greyed zeros.  A grid that states nothing draws no picture, and where an
  axis states fewer breakpoints than the shape the picture lies over indices, its ticks reading
  them and no axis named under them.  A cell keeps the reading it was typed in when the toggle
  is turned.  No file format changes.

* **A value chosen for one key of a variable's panel is never applied to another.**  The panel
  carried what was chosen, typed or edited for one key to the key it moved to by itself, so Apply
  could write one key's value under another's name.  It now holds each value for its own key and
  drops it when another is on screen.  A chooser whose text is not the value settled, its Apply
  and the declare form's Add are withheld, with a sentence saying whether Enter takes the text or
  the list must; a scroll that closes the list keeps what was typed, and only Escape and leaving
  the field end the text.  Nothing to migrate.

* **A number typed into a grid cell reaches the cell.**  The table's type-to-find took the
  digits of a number typed key by key, so typing 20 over 12 could leave 2 or 2012, and the focused
  cell did not follow the field that had the focus.  A key naming one character stays with the
  cell, and the grid's focused cell follows its field.  Nothing to migrate.

* **A unit with spaces around it is refused on a variable's panel and a type's.**  It was planned
  and written with the spaces kept.  It is now refused in the words of the Units tab, and the route
  that settles a key and the type route answer 409.  A unit typed that way has to be typed without
  them.

* **An undo label is cut on a whole character.**  A label long enough to be cut was cut through
  the pair of a character outside the basic plane, an emoji, and the edit was refused as invalid
  json.  The page now counts and cuts in whole characters, so the edit is applied.  Nothing to
  migrate.

* **Typing in a grid of thousands of cells no longer stalls.**  A key pressed in a grid of 4,096
  cells took 728 ms, measured on the development PC, because the picture's extremes were found
  for every point and every cell was drawn again.  The picture is now worked out in time linear in
  its cells and a key press draws only the cell typed into: 27 ms a key at 4,096 cells, under the
  100 ms the design for large projects allows.  Nothing to migrate.

* **`ddd tool from-elf` reads a positive enumerator of a signed enum as positive.**  In a signed
  enum an enumerator written in a constant narrower than the enum was read as negative, so gcc's 200
  came out -56 and 40000 came out -25536, and the generated header, the a2l's value table and the
  limits worked out from them carried the wrong values, while the image itself was right; so did
  2^31 and up written as four bytes in an eight-byte enum.  Only a fixed-width constant as wide as
  its signed enum, with its top bit set, is negative now.  Migrating costs a run: a component file
  or an interface written from an image with such an enumerator holds the wrong values, and has to
  be written again by `ddd tool from-elf` and the project generated again.

* **An address the linker left meaningless is not placed.**  A variable gold dropped under
  `--gc-sections` keeps its debug information with its address as an offset into the section it
  discarded, so `--image` wrote that offset into the a2l as an address and `from-elf` could read
  code as the variable's initial value.  An external variable is now placed only where the image's
  symbol table holds an object of its name at the address its debug information gives, and a section
  of the image holds that address; a static is checked against the image's local symbols where it
  keeps any, and read by its address alone where the link dropped them all.  What fails is
  `address-missing` for `--image`, which now also refuses an address no section holds, and
  `elf-no-storage` for `from-elf`, in new words; an image with debug information and no symbol table
  places nothing.  GNU ld 2.44, gold 2.44 and lld 19 are the linkers the specification names as
  tested.  Migrating costs a build that has such a variable: its a2l record is at address 0 with a
  warning where it had a wrong address, and a `--strict` or `STRICT` build now stops at it.

* **`ddd tool from-elf` warns where a structure is laid out otherwise than the generated C would lay
  it out.**  The image states where each member sits and how large the structure is, and the tool
  read neither, so a packed structure, `#pragma pack(2)`, a packed member and an unnamed or
  zero-width bitfield became an ordinary structure in silence.  Each structure is now laid out as
  the generated C would lay it out, under the alignment cap of the image's machine, and a difference
  is the new warning `elf-layout`, once per structure.  Only x86-64, i386, 32-bit PowerPC, S/390,
  ARM under an EABI, AArch64 and RISC-V other than RV32E are checked; for any other image the new
  info `elf-layout-unchecked` says so once.  Two structures of one name that differ in a member's
  offset or in size are an `elf-type-conflict` error, where they were one entry.  `elf-alignment`
  also reports an alignment a variable states, with `_Alignas`, and a GNU vector that is a variable
  or a member, which drew nothing before; a vector member also draws `elf-layout`.  `from-elf` takes
  no `--strict`, so no warning stops it and the exit status of a run is as before; a script that
  counts the findings, or a project that turns warnings into errors on its output, meets the new
  ones, and the only way to silence one is to change the source.

* **`ddd tool from-elf` refuses a debug-only file.**  An `objcopy --only-keep-debug` file keeps the
  DWARF of the image it was split from and leaves every section without its bytes, and `from-elf`
  printed each variable without its initial value, with no finding and exit 0.  A file none of whose
  sections of the program, code and data alike, has contents is now a usage error, exit 2, naming
  the linked image to give.  `ddd generate a2l --image` still reads such a file, the addresses in it
  being the image's, and an image whose code alone is left out of the file is still read by both.
  Migrating costs a script that ran `from-elf` over a companion file: it passes the linked image.

* **A damaged image is refused where it hung, and an image of many types opens faster.**  The
  reader followed each `DW_AT_sibling` pointer unchecked, so an entry aimed at itself sent the walk
  round in a circle and no run finished.  It now walks a unit's entries forward only and refuses a
  sibling that does not advance, at once, naming the offset.  A variable's type, and the line table
  its declaration needs, are read only for the variables a run asks about: an image of 60,000
  variables, each of a structure of its own, opens in 3.3 s where it took 7.0 s, and one of 60,000
  plain scalars, whose types are few, costs a little more, 2.8 s where it took 2.4 s, measured on
  the development PC.  How far a damaged line table is bounded is still open, and this does not
  claim that every damaged image is refused.  No output changes for a well-formed image.  Nothing
  to migrate.

* **`ddd tool from-elf` says where an image answers twice.**  It took the first of several answers
  and said nothing of the rest.  One name at one address that two units, or a unit and the symbol
  table, give two sizes - a common symbol, an array of two lengths, a weak definition over a strong
  one of another type - is now `elf-type-conflict`, naming each size, and the variable is left out;
  an ambiguity beside it is still reported.  Where two sections a linker script overlays hold an
  address and the symbol names neither, the new error `elf-section-ambiguous` replaces the first
  section's bytes, which every variable there took.  A name two arguments reach from two units,
  which DDD's own check reported as `duplicate-declaration` of the tool's internal component, is
  now `elf-symbol-ambiguous`, in the words the user typed, and that component's name no longer
  appears in a message.  Migrating costs a variable that was described silently from the first
  unit's answer: it is now an error naming both answers, and the units have to agree.  A script
  that matched `duplicate-declaration` for a name asked for twice matches `elf-symbol-ambiguous`
  instead, at the same exit status.

* **`ddd tool from-elf` refuses the C++ it does not read.**  A structure with a base class, one with
  a static member where the debug information writes it as a member, and a variable whose definition
  belongs to a namespace or a class were described wrongly, without the base members, with the
  static as a value member, or under the short name of a variable in another scope.  Each is now
  refused in a sentence of its own, as `elf-type-unsupported` or `elf-no-storage`.  A project that
  relied on the wrong description has to describe those by hand.

* **A `float32` of FLT_MAX is written as the double it is.**  `ddd tool from-elf` wrote its shortest
  spelling, which lies past the range a `float32` holds, and DDD refused it as out of range.
  FLT_MAX and its negative are now written as 3.4028234663852886e+38, which it accepts.  Nothing to
  migrate.

* **A name no unit gave storage is `elf-no-storage`, once.**  A name every unit left without an
  address, as a header's `static const` each folded, was `elf-symbol-ambiguous`, and the unit prefix
  it offered only earned a refusal for want of storage.  It is now reported once as
  `elf-no-storage`, naming the units: a script that matches the old identifier for such a name has
  to match the new one.  The build page also says that `--image` refuses an image gcc linked with
  `-flto`, and five pages that spoke of the address map alone now name `--image`.

* **`ddd tool from-elf` writes no conversion it cannot know.**  Every scalar and every structure
  member carried the identity conversion, which says that raw is physical, a claim an image says
  nothing of.  An entry or member that is not an enum is now printed without a conversion, and an
  enum keeps its `enum` conversion.  Migrating costs an edit: the output pasted into a component is
  a `schema` error, a `datatype` coming with a `conversion`, until its author states what raw is to
  physical; `--identity-conversions` writes the identity on every such entry and member, on the
  author's word for all of them, and `elf-not-inferred` says which of the two the run was.

* **An object the build compiled out is left out of the a2l, and a reference across conditions is
  checked.**  With an image, or a map that has entries, an object stating a condition that the image
  defines no variable of, nor holds a symbol of, or that the map names neither it nor a member of,
  was written at address 0 and warned as `address-missing`, which a `--strict` build could only get
  past by lowering that check, so hiding a real hole too.  It is now left out of the file, and the
  new info `condition-left-out` says so, once per condition; every other reason an image gives stays
  `address-missing`.  A curve or a map over an axis so left out goes too, as the new warning
  `reference-left-out`, which stops a `--strict` build; an axis over a left-out input is written
  with no input quantity.  `condition-mismatch` also compares a reference, a curve over an axis or
  an axis over its input stating a condition the referrer does not, so `-W
  condition-mismatch=ignore` silences both.  Migrating costs a look: drop an `address-missing=info`
  lowering kept for this, and a tool that expected the record, or its comment, finds none.  A
  project with such a reference meets `condition-mismatch`, and under `--strict` an error.
  `A2lOptions` gains `left_out`, and `ddd.backends` gains `conditional_objects`, `dragged_with` and
  `ConditionalObject`.

* **A position independent image, an unreadable map and two debug options say what they are.**  An
  image linked position independent holds offsets from where it loads, and the a2l took them for
  addresses without a word.  It is still read, and the new info `image-load-relative` says that its
  addresses are load relative: right for a project that adds its base, wrong for one that does not.
  A map that is not UTF-8, as PowerShell's redirection writes, one nested deeper than the
  interpreter reads, and one holding an address of more digits than it converts, were Python's own
  words or a traceback with exit 1; each is now a usage error naming the file, exit 2.  An image
  built with `-gsplit-dwarf` places nothing and said its units had no `-g`; it now says the debug
  information is in `.dwo` files the reader does not read, and a `-g1` image says the variable has
  no type, and is still placed.  `ddd tool from-elf` now says the same of both, where it gave a
  split image that advice too and called a `-g1` variable `void`.  Nothing to migrate; a build
  that counts its findings sees `image-load-relative`, which `-W image-load-relative=ignore`
  silences.

* **`ddd generate a2l --image` warns where the image holds a variable otherwise than its description
  says.**  The linked image is the only place a run sees the C that was compiled, and the addresses
  were taken without a look at what sat there, so a definition of another width, or a template that
  dropped a qualifier its kind carries, went through unremarked.  Each variable placed is now
  compared with its object on the size and encoding of an element, its shape and the qualifiers the
  generated C gives its kind, and a member on the first three; the difference is the new warning
  `elf-mismatch`, naming what the description states and what the image holds.  A consumer's
  declaration of the variable is held to the qualifiers too, where the compiler records it, which
  gcc does for a variable a unit reads and clang does not, so a header that drops `volatile`, or
  adds it or `const`, is named.  A one-byte unsigned
  integer agrees with a `boolean`.  Migrating costs a fix or a silence: a `STRICT` build whose image
  disagrees with its description stops and writes no a2l, and `-W elf-mismatch=ignore`, or
  `SEVERITY` in cmake, lets it through; a run that is not stopped writes the a2l from the
  description.

* **`--const-inputs` and `CONST_INPUTS` are gone, and a header that adds `const` is named.**  The
  option wrote an input's declaration `const` while the input's definition, in the producer, is not.
  C leaves such a pair of declarations undefined (C11 6.2.7p2 and 6.7.3p10), and an optimising
  compiler may hand a reader a stale value, so a build that passed was not one that was right.  `ddd
  generate c|all --const-inputs` now exits `2` and `ddd_generate()` stops at configure time with
  `CONST_INPUTS`, each in a sentence saying the option was removed in 0.12.0 and why; nothing is
  written.  A template's `.const` on a header entry, and `declaration(const=...)` on an object, are
  removed from the names a template renders from and refused at generation in a sentence naming the
  same release; `DeclarationView` loses its `const` field, and `COptions` its `const_inputs`, so
  code that builds either by position or by that keyword breaks, and the `compile-const` service of
  `docker-compose.yml` is gone.  Migrating costs the deletion of the option or the keyword and of
  any template line using either, and nothing replaces them: `entry.line` is the declaration, and
  `declaration()` refuses a `const=` and says why.  `elf-mismatch` now also names a consumer's
  declaration that adds `const`, where the compiler records the qualifier, so a `STRICT` build whose
  hand-written header did that stops, until the header is fixed or `-W elf-mismatch=ignore` lets it
  through.

* **`ddd generate a2l --a2l-module-fragment FILE` puts a project's own text at the head of the
  `MODULE`.**  DDD models none of what describes the target rather than the data: the `A2ML`
  metalanguage the `IF_DATA` blocks it writes are described by, the protocol layer of the XCP stack,
  an `EPK` with its `ADDR_EPK`, a `MEMORY_SEGMENT` for each memory.  A project that needed one had
  to add it to the a2l after every run.  The file, read as UTF-8 text, goes in once, right after
  `/begin MODULE`, before the first `IF_DATA` of the a2l, with a final newline added if it has none
  and its line endings made the a2l's own; DDD does not read its keywords.  `ddd generate all` takes
  the option too, and `ddd_generate()` takes `A2L_MODULE_FRAGMENT <file>` in both its a2l runs, the
  one before the link and the one after it, so that an edit of the file writes the a2l again.  A
  file that cannot be read or is not UTF-8, a fragment beside `--without a2l` or `NO_A2L`, and a
  fragment holding a `MOD_PAR` in a project that declares named constants, which DDD writes a
  `MOD_PAR` for, are usage errors, exit `2`.  Where a project declares none, the fragment's
  `MOD_PAR` is the module's, so an `EPK` can only be carried through the fragment there.  Nothing is
  migrated for the option, which is new.  `A2lOptions`, public through `ddd.backends`, gains five
  fields in this release: `module_fragment`, `links`, which a member's `SYMBOL_LINK` below is
  written from, `alignment_cap`, which `MOD_COMMON`'s alignments below are, `left_out`, named
  above, and `has_address_source`, which says whether the run had a source of addresses.
  `alignment_cap` stands second, after `byte_order`, and `links`, `has_address_source`, `left_out`
  and `module_fragment` after `addresses`, so code that builds the options by position meets them
  there: in `A2lOptions(ByteOrder.BIG, "1 61")` the version 0.11.0 took second is taken for
  `alignment_cap`, in a third position the addresses 0.11.0 took there are taken for `version`, and
  in a fourth, which 0.11.0 refused, they are the `addresses`.

* **A member's `SYMBOL_LINK` is where a linker map can find it.**  With `ddd generate a2l --image`,
  the record of a structure member, at any depth and in an element of an array of structures, said
  `SYMBOL_LINK "Inlet.cells[1].v" 0`: the path of a name no linker map holds, so a patcher that
  resolves a record's symbol through the map found nothing for it.  It now says `SYMBOL_LINK "Inlet"
  26`, the variable the linker knows and the byte offset of the member in it, taken from the image's
  own placement of it.  The offsets measured on the address fixtures' members agree on every image
  of them.  A script that matched a record by the spelling of its path in `SYMBOL_LINK` must read
  the variable and the offset instead.  Before the link, and with `--address-map`, the record is as
  it was, the path at offset 0: a map holds no member's offset, and a debug information reader may
  resolve the path, which was not tried.

* **A name that is a keyword of ASAP2 is an error, and a string or a name past the format's limits
  is named.**  A project whose variable, member, component or display identifier is `MAP`, `VALUE`,
  `ROOT` or `MODULE` was written to an a2l that a tool reading it refuses or misparses, and DDD said
  nothing.  The new check `a2l-keyword`, an error, names every name that reaches the a2l and is one
  of the keywords or enumeration values of ASAP2 1.6.1, by an exact, case sensitive match, so `map`
  is fine; it skips what the a2l keeps out and holds what the closure over references brings in, so
  an object or a member that states `export: false` for the a2l is skipped unless an exported object
  names it, an axis under an exported curve or a measurement an exported axis names as its `input`;
  but the check cannot see which objects a run
  leaves out of the a2l (`condition-left-out`, or the symbols a build compiled out), so a name only
  such a run drops still draws the error, and `-W a2l-keyword=ignore` relaxes it for that run.
  `a2l-unrepresentable`, a warning, now also names a description or a unit past 255 characters, the
  longest path of a structure variable's records past 255 characters, which a string of the a2l
  carries, or past 1024, which an identifier does, and a part of a name past 128 characters with its
  array index counted; a unit under an identity conversion is held to 237 characters, since the
  method's description repeats it after 18 more. The file is written whole all the same, and the
  finding names which of the limits it passes. Like the keyword check, it skips what the a2l keeps
  out and holds what the closure over references brings in. It cannot see a run's left-out objects either, so an
  object only such a run drops is still named, and `-W a2l-unrepresentable=ignore` relaxes it for
  that run. Migrating costs a rename for the error, which stops
  `ddd check`, `ddd generate` and a build that passed, and `-W a2l-keyword=ignore` relaxes it for a
  name the target's tool accepts; the warning stops a `--strict` or `STRICT` build, and `-W
  a2l-unrepresentable=ignore` lets it through.  The list of keywords is DDD's own, written without a
  copy of the standard to check it against, so a word may be missing from it or held that the
  standard does not hold.

* **A size past 65,535 is named, once, where it is declared.**  An array or a string of more than
  65,535 elements, or a curve or map axis of more than 65,535 points, was written to the a2l's
  `MATRIX_DIM`, `NUMBER` or `MaxAxisPoints` without a word, though the a2l's datatype for each
  cannot hold it.  The record is still written, the number whole, and `a2l-unrepresentable` now
  warns of it, naming the number and the field, once per object; a curve or a map is not named, its
  axis is.  A member of a structure is named once at its type, in the types file, whatever the
  number of variables and array elements that carry it, in the words "member 'v' of structure
  'S_t'"; a member of more than three dimensions is named the same way, once at its type, where a
  warning for each element and each variable came before, at the variable's declaration and in the
  words "'X.hyper' has".  A script that read the text of such a warning, and its location, must read
  the new.  A `--strict` or `STRICT` build with such a size stops, and so does one whose object only
  a run drops because its build holds none of it, since the check reads neither the image nor the
  map; the cost is a smaller object, or `-W a2l-unrepresentable=ignore`.

* **The example `ddd_globals.c` template keeps a definition through `--gc-sections`, and the pages
  say where `const volatile` lies.**  The pages said that `volatile` takes a `const volatile`
  calibration object out of `.rodata` and into RAM; it does not, on any toolchain measured.
  Measured in the ELF images the test suite is built on, gcc 14.2.0 for x86_64, i686, aarch64 and
  s390x, arm-none-eabi-gcc 14.2.1 and clang 19.1.7 held every such object in `.rodata`, which is not
  writable, except on powerpc, where the small ones lie in `.sdata` as the plain `const` ones of
  their size do; where a compiler places one depends on the target and its version.  And a link with
  `--gc-sections` drops a definition no code references, so a calibration object nothing reads left
  the image and reached the a2l at address 0: on the demo linked by gcc 15.2.0 and GNU ld 2.46, with
  `-fdata-sections` and without it, none of the 23 objects stayed, and `ddd generate a2l --image`
  warned `address-missing` for 20 objects.  The example `ddd_globals.c.jinja2` now writes
  `DDD_RETAIN` before each definition, an empty macro unless the build defines it; defined as
  `__attribute__((used, retain))`, it kept all 23 on that host.  A project that links with
  `--gc-sections` on ELF defines it, with `-D` or in a header the build includes first; on PE gcc
  ignores `retain`, so a reference to the object or a linker script that keeps its section is what
  keeps it there.  A project that copied the example templates before does not gain the macro, and
  has to copy it.  The page that said a program storing through a `const` object prints the new
  value back is corrected as well: on that host the store ended the program with a segmentation
  fault at -O0, -O2 and -Os, and no target's flash was measured.

* **A reader of a variable's scale can follow its rescale: templates see `unit`, `conversion` and
  `limits`, and the example header writes the factor.**  A project that read `ddd check` as proof
  its readers agree with the descriptions had no warning, and no compile error, when a unit's
  conversion changed from 0.1 to 0.01 and the code that multiplied by 0.1 was left behind: `ddd
  check` compares the descriptions of a variable's declarations, never the code, and a variable
  whose type is shared in a types file has nothing to compare.  An object a template renders now has
  `.unit`, `.conversion` (`kind`, `factor`, `offset`, `name`, `enumerators`, `coefficients` and the
  literals of the numbers) and `.limits` (`min`, `max` and their literals), the fields the a2l is
  written from, and the example component header writes, after an input or an output that has a
  linear conversion, `#define ValueE__FACTOR (0.25)` and `#define ValueE__OFFSET (0.0)`.  A reader
  that multiplies by the macro is built again when the conversion changes; one that wrote the number
  itself is not, which the pages now say.  A double underscore is refused in every name of a
  project, so no accepted name can be one of the macros.  Another kind of conversion writes nothing,
  and a header with none changes not at all.  A project that copied the example templates earlier
  gains no macro until it copies the `scale` macro of `_macros.jinja2` and its call.  The fix a `ddd
  gui` finding offers for a `definition-mismatch` now ends its title with "(the code of the readers
  is not touched)", and `GET /api/fix` returns that title; a script that matched the old title must
  match the new.

* **A structure member's `export: false`, `format` and `display_identifier` reach the records below
  it.**  Stated on a member that names a structure, the block was ignored: `export: false` left
  every record under the member in the a2l, and a `format` or a display identifier changed none.
  The member's `export: false` now leaves every record below it out of the a2l; a `format` reaches
  every number record below, the innermost member's winning, and a display identifier stands for
  that member's own segment of each record's path, so `j` displayed `J` writes `V[1].J.b` where the
  record was `V[1].j.b`, and a display identifier of a deeper member or of a leaf below it is
  written as stated.  `a2l-keyword` and `a2l-unrepresentable` hold a display identifier at the
  member that states it, in the types file, and the whole identifier made of the segments at the
  innermost one, once.  Two members of a structure displayed alike are not warned of, as two leaves
  displayed alike never were.  A project that relied on the ignored block sees fewer records in the
  a2l, and a display identifier that was ignored now renames the records it stands for.  The
  dumped dictionary records the block on each leaf below such a member, where one dumped by 0.11.0
  records each without it, so `ddd compare` against a baseline 0.11.0 archived reports
  `changed-a2l` once for every such leaf: four where one member of a structure, over two leaves,
  gives them its format and display identifier, and another, over two, leaves them out with
  `export: false`.
  It is a warning, so `ddd check --baseline --strict` of a project unchanged since passes with
  0.11.0 and exits 1 after the upgrade, its four warnings made errors; dumping the baseline again
  with this version clears them.  The dumped dictionary is format 10, for the display identifier a
  leaf takes from a member above it, a path of identifiers where format 9 held one; a format 9
  dictionary reads back unchanged, and 0.11.0, which reads up to format 9, refuses a format 10 one
  as the dictionary of a newer DDD.

* **A derived limit no longer stops short of the largest raw value, and never passes the largest a
  float holds.**  A limit written from a datatype and a conversion was rounded to twelve significant
  digits, so it could sit outside the values the description's own raw counts read as, and a tool
  holding data to the range refused them: `uint64` under a factor of 1 stated `1.84467440737e+19`,
  and `float32` and `float64` under the identity stated a number past what the type holds.  An end
  within four units in the last place of its twelve digit decimal keeps the decimal, so `uint8`
  under a factor of 0.03 still states 7.65 and `sint16` under 0.1 still states 3276.7, which may sit
  up to four units inside the product; any other end is the float it is, written in the shortest
  form that reads back as itself, as `1.8446744073709552e+19` for the `uint64`, `4194303.9990234375`
  for a `uint32` under 2^-10 and `FLT_MAX` and `DBL_MAX` exactly for the two identities.  Only an
  a2l or a dumped dictionary with an end of more than twelve digits changes, in the digits after the
  twelfth, and an archived one compares as the same limit in `ddd compare` and in the check on
  stated limits, which weigh two limits with one relative tolerance; a script comparing the numbers
  as text, or without a tolerance, sees the difference.  The examples' a2l files hold no such end.

* **The a2l's `MOD_COMMON` states the image's alignments, and a run that defaults the byte order
  says so.**  `ALIGNMENT_INT64` and `ALIGNMENT_FLOAT64_IEEE` were always 8, though a 64 bit value is
  aligned to 4 on i386.  With `--image` of an i386 machine they are now 4, from the table the
  image's machine is held to; with another machine, one the tool holds no table for, or no image,
  they stay 8.  And an a2l written with neither `--byte-order` nor an image states little endian
  only because something has to be stated, so a big endian target that forgot to say so got a file
  whose every multi byte value a tool read swapped, and nothing said so.  Such a run now prints the
  new info `byte-order-defaulted`, which is most of the runs of a project that gives neither, and
  says to state it with `--byte-order big` or `BYTE_ORDER` in cmake.  It stops nothing.  A cmake
  build with no `BYTE_ORDER` prints it from the generation of a build of one step and from the
  step that writes the a2l after the link with `ADDRESS_MAP`, and from no step of a build with
  `ADDRESSES_FROM_IMAGE`, whose a2l takes the image's byte order; the run before the link of
  either writes no a2l.  A script that read the count of diagnostics from `--format json`,
  expecting none, now finds one; `-W byte-order-defaulted=ignore` silences it, and so does stating
  the byte order.

* **The a2l's records, groups and methods are named and ordered the same way on every run.**  A
  `GROUP` listed the elements of an array of structures sorted by their path as text, so `SA[10].v`
  came before `SA[1].v`, while the records were already in the dictionary's order, an index counted
  as a number; the `GROUP` now lists them in that order too, so only the order of a `GROUP`'s
  members changes.  The compu method name with no suffix, `CM_LIN_V` for a unit `V`, went to the
  first object the dictionary met that used it, and `CM_LIN_V_2` to the second; it now goes to the
  first record the file writes, measurements first, then axes, then the other calibration objects,
  parameters, value blocks, curves and maps together in the dictionary's order, a member's after a
  plain object's.  A project that has two conversions in one unit, and whose first holder
  changed, sees the two names swap between the records, which a tool that addresses a method by its
  name sees.  And the naming of the methods took time quadratic in their count: measured by timing
  that naming alone, over objects that each had a factor of their own in one unit, so each needed a
  method and a name of its own, 2,000 objects took 0.20 s before and 0.01 s after, and 16,000 took
  13.00 s before and 0.07 s after; the names it gives are the same.

* **Every component has an include guard of its own, and a description that ends in a trigraph does
  not break the build.**  Two components `Valve` and `Valve_`, or `Valve` and `_valve`, were given
  the same guard, `DDD_COMPONENT_VALVE_H`, so a file that included both lost the second's
  declarations.  A component whose name begins or ends with an underscore now has
  `DDD_COMPONENTS_LEADING_VALVE_H`, `DDD_COMPONENTS_TRAILING_VALVE_H` or
  `DDD_COMPONENTS_BOTH_VALVE_H`, and any other name keeps `DDD_COMPONENT_VALVE_H`, `DDD_TYPES_H` and
  `DDD_GLOBALS_H` as they were.  A description that ends in the opening of a trigraph, `??/` among
  them, left one in the generated comment, and a build with `-Werror=trigraphs` stopped on it; the
  two question marks of any of the nine are now separated, `? ?`.  Migrating costs a hand written
  reference to a guard that moved, such as an `#ifdef` on it; `header.guard` in the example
  component template follows the rule, but `model.guard()` is unchanged, so a template that builds a
  component's guard with it keeps the old collision.

* **`address-missing` no longer names a measurement that only a left-out axis pulled in.**  An
  `export: false` measurement that only a curve's or map's axis, left out of the a2l by a build that
  did not compile it, pulled into the a2l was still named as missing from the address map, and a
  `--strict` run stopped over a record the file did not hold.  The coverage is taken under the same
  left-out objects the a2l is, so the finding names only what the file holds, and the measurement is
  not named at all.

* **A delivery that moves what a precompiled reader was built against is `changed-interface`, once,
  and "cannot replace".**  A component that reads an object may be a binary built against the
  baseline's headers, and three changes left it reading the wrong storage while the comparison
  passed: a structured variable whose layout moved (a member of its structure inserted, removed,
  renamed or reordered, a nested structure grown or rearranged, a nested array of another size or
  of its size spelled another way, `[2]` as `["N"]` where `N` is 2, an external member of another
  type, another header or other dimensions), a constant whose value changed, and `volatile` turned
  on for an object a component reads.  Each is now the error
  `changed-interface`, so `ddd compare`, `ddd check --baseline` and the Compare tab of `ddd gui` say
  the candidate cannot replace the baseline, with or without `--strict`.  A layout is said at each
  variable it changes, naming the structure and where the two layouts part; a constant at the
  constant; `volatile` once, at the variable for a structured one, where it was `changed-storage`.
  A reorder used to be said once, at the structure, by a `changed-interface` that named none of the
  variables; it is now said at each variable, so a structure of three variables is three findings,
  and a structure no variable uses gives none, where it was an error.  A nested structure renamed
  with the same layout gives none either, and the variable's own type renamed stays
  `changed-interface`; a member added after every member of the structure of a single variable stays
  `added-object` alone; a baseline of dictionary format 3 or older compares dimensions by value
  alone.  Migrating costs the delivery: a released structure that has to grow grows at the end of a
  single variable's structure, or the finding is accepted for that delivery by relaxing
  `changed-interface`.  A nested array whose size a constant names where a number did, or the other
  way, is accepted the same way, or keeps the spelling of the baseline.  A `-W changed-storage=...`
  kept to let `volatile` turned on pass no longer reaches it, and a script that matched the old
  reorder message follows the new one.  No file format changes; the dictionary stays format 10.

* **A constant that is gone stops a comparison, one that is new does not, and a constant's size is
  told as the number.**  `removed-constant` is a new error, since a reader that uses the macro no
  longer builds whether or not an object is dimensioned by it, and a constant renamed is it for the
  old name and the new info `added-constant` for the new one.  A changed value is
  `changed-interface` at the constant, and an object it dimensions says its own shape as well, now
  with the size each constant gives, `[N=8] != [N=4]`, where it said `[N] != [N]` of two sizes of
  one name.  A raster whose event or cycle changed is `changed-storage` at the raster, a warning and
  so an error under `--strict`, where it was no finding; a raster that came or went still says
  nothing.  Constants are compared only when both dictionaries are format 4 or newer, since an older
  one recorded none, and sections are still not compared.  Migrating costs a project that changes a
  constant between two deliveries a relaxation of `changed-interface` or `removed-constant`, or a
  new baseline.

* **A rename, or a narrowing by condition, of an object a component reads is an error under an id of
  its own.**  Both were warnings, `renamed-object` and `changed-condition`, and a delivery that
  renamed an object a component reads, or added a condition to it, "could replace" the baseline: a
  reader built against the old headers looks for a spelling that is gone, or for an object absent
  from a build where the new condition is false.  The rename of a read object is now
  `renamed-read-object` and a condition added to a read object, or one replaced by another, is
  `narrowed-condition`, both errors that name the readers; a structured variable's rename is said
  under each leaf's path, and one that has no leaf at the variable.  The same changes on an object
  nobody reads, and a condition going away, keep `renamed-object` and `changed-condition`, which
  stay warnings.  A check has one severity, so a project that relaxed `-W renamed-object=ignore` or
  `-W changed-condition=ignore` to accept such a delivery finds that no longer reaches a read
  object, and has to name `-W renamed-read-object=...` or `-W narrowed-condition=...` for that
  delivery.  The `--renames` file lists the same pairs as before.

* **The limits of a measurement a component reads are graded by what its readers meet.**  A reader
  may hold a lookup or a clamp sized for the range the producer stated, so widening that range was
  silent and narrowing it a warning that said the opposite of what mattered.  Widening the limits of
  a measurement somebody reads is now the warning `widened-limits`, and narrowing them the info
  `narrowed-read-limits`, which stops nothing, since a reader still gets values inside the range it
  was written for; a range that moved both ways is a widening.  Calibration data, and a measurement
  nobody reads, keep `narrowed-limits` and a silent widening, and a measurement of a structured
  variable takes the variable's kind and readers.  The tolerance and the rule that limits are not
  told beside a changed interface are as they were, and this release holds a member's limits back
  beside a change to its variable's interface as well: its kind, whether it is local, its type, its
  shape or where its members lie, which is told once, at the variable, as a `changed-interface`.
  A delivery that moved a member's limits and changed one of those meets the `changed-interface`
  alone, and the limits are told again once it is resolved.  A project that relaxed `-W
  narrowed-limits=ignore` for a measurement a component reads no longer has it reach it, and a
  `--strict` run now stops on a widened measurement; the worked example of the comparing page prints
  a `widened-limits` of `SupplyVoltage` and a `narrowed-read-limits` of `ValveDuty` where it printed
  one `narrowed-limits`, five findings for its five changes.

* **An output a component drops or changes is graded as one somebody reads, an input it stops
  reading stops nothing, and a component is read the same way by every command.**  A baseline that
  is one component file is a component read alone, so who read its objects is not known, and every
  grade that waits on a reader takes an output of it as read, with a message that does not claim to
  know a reader.  Gone, such an output is now `removed-object`, an error, where it was the warning
  `removed-unused-object`.  Renamed with its id kept, given a condition or another one, or turned
  `volatile`, it is now `renamed-read-object`, `narrowed-condition` or `changed-interface`, each an
  error, where it was the warning `renamed-object`, `changed-condition` or `changed-storage`; a
  measurement's limits widened are now the warning `widened-limits`, where they were silent, and
  narrowed the info `narrowed-read-limits`, where they were the warning `narrowed-limits`.  An
  object it declares `local` keeps the grades of an object nobody reads, and an input it stopped
  reading is the new info `removed-input`, where it was a `removed-object` error stopping a
  component that reads less.  `ddd compare`, `ddd check --baseline` without `--standalone` and the
  Compare tab now read such a baseline under the floor `ddd check --standalone` reads a component
  under, as `check --baseline --standalone` did, so an input nobody produces is no longer carried as
  an error of the baseline: a project checked against a component file with an input exited 1 on
  it, and exits 0.  A component file given as the candidate is read as a project's file, so a
  supplier comparing two versions of a component with inputs uses `ddd check --baseline
  --standalone`, the command that takes the option.  An archived `ddd dump --standalone` carries no
  mark of how it was read, and is graded as the dictionary of a whole project, as before.  A project
  that relaxed `-W removed-object=...` to let an input go can drop it, one that relied on
  `removed-unused-object` for a dropped output names `removed-object` now, and a supplier whose gate
  passed the rename, the condition, the `volatile` or the wider range of an output, and stops or
  warns on it now, relaxes the new id for that delivery.

* **A producer lost is `missing-producer`, said once, where the baseline had one.**  A dictionary
  dumped from a project that failed is written all the same, and an object it holds with readers and
  no producer compared as a `changed-owner` warning, so a delivery that had lost a producer "could
  replace" one that had it.  Where the baseline's object had a producer and the candidate, still
  read, has none, the comparison now says `missing-producer`, the id `ddd check` gives the fault, in
  place of that pair's `changed-owner`: an error with a dumped candidate, and under `ddd check
  --baseline --standalone` as well, where the floor silences the analysis for what a component read
  alone was never shown but not for a producer the baseline had, so a component that turns an output
  into an input exits 1 with or without `--strict`, as it exited 0 with a `changed-owner` warning.
  An object with no producer on both sides is no change, since a dump of a component read alone
  holds every input it reads so, and an input that arrived with none is `added-object` alone.  With
  a description candidate the analysis says it, and `changed-owner` is no longer filed beside it.  A
  project's own `-W missing-producer=ignore` silences it on every path, which is the migration for a
  project that holds such objects, and a relaxation of `changed-owner` no longer reaches this pair.

* **An initial value is compared as the bytes it stores, and one no double holds is refused.**  A
  table was reduced level by level, so two tables that differ, such as a square map and its
  transpose, could compare identical, and `-0.0` against `0.0`, which differ in the sign bit, was no
  change.  A scalar now stands for the array it fills only when every element holds it, two tables
  that differ are a change, a float's `-0.0` is not `0.0`, and the finding names the first index at
  which the two part, the elements taken in the order C lays them out.  An object that states no
  `init` stores zeros, so adding `0`, `[0, 0]` or `""` to it is no change, in either direction,
  where it was a `changed-storage` warning and an error under `--strict`.  A non-zero number that no
  double holds, such as `1e-400`, was read as `0` before anything looked at it, so `ddd check` was
  clean over an `init` the rule calls `init-invalid`; it is now refused as `json-syntax`, naming it,
  wherever DDD reads a json document, a description or a dumped dictionary, and `1e400` stays
  refused as ever.  Migrating costs a `1e-400` written to mean zero, which is written `0`, and a
  comparison that was clean over a changed table reports it.

* **A structured variable's changes are told once, in order, and a variable with no leaf is compared
  as an object is.**  A change of the variable's `kind` was one `changed-interface` per member, and
  per member of every element of an array, for one edit; it is now one, at the variable.  A member's
  own change is told at every path that reaches it, the paths, the removals, the additions and the
  entries of `--renames` in the order `ddd list` gives them, `[2]` before `[10]`, where plain text
  put `[10]` first.  A structure that holds only members of external types has no leaf, and its
  variable could be removed, renamed or reused with no finding while every reader's header lost it:
  its removal is now `removed-object`, or `removed-unused-object` where nobody read it, its rename
  `renamed-read-object` or `renamed-object`, listed in `--renames` under the variable's own `id`,
  another `id` under its name is `reused-name` with the removal and the addition an object gets, and
  its arrival is `added-object`.  A variable that has leaves is not said a second time.  A script
  that counted the findings of a changed `kind` or matched them by their paths finds fewer, and the
  new errors are relaxed by the ids they carry.

* **A broken baseline withholds nothing, a description baseline takes the project's relaxations, and
  a file with no delivery in it is refused.**  A baseline that carried an error of its own made the
  run stop before the candidate's findings and before the comparison, so the candidate's
  `unused-output` was not printed and `--renames` was not written; the comparison is now made, the
  candidate's findings are reported at their own severities, the renames are written, and the
  verdict is still that it cannot replace, with a baseline that cannot be read at all leaving the
  candidate's findings reported as well.  A baseline given as a description is analysed in its own
  right, and now under the relaxations of the run's `-W`, an override that grades a check below its
  default or `ignore`, a plugin's check only as `ignore`, so that a project that builds with `-W
  missing-producer=ignore` can compare its branch against its trunk, as `ddd check` of either is
  clean; promotions and `--strict` still do not reach it.  The Compare tab reads it under the
  relaxations every build record of the project makes.  A json that states no `format`, no `project`
  and no `component`, such as one holding only a `name`, was read as an empty dictionary and
  compared as the removal of everything; it is refused as `schema` wherever it is given as a
  delivery to compare: either side of `ddd compare`, the baseline of `ddd check --baseline` and the
  tab's baseline; as the file `ddd check` itself reads it stays refused as `file-kind`, the refusal
  it always met.  A baseline error a project relaxes no longer appears in its comparisons, and a
  script that matched the lone refusal of a broken baseline now finds the rest of the report after
  it.

* **The Compare tab's verdict counts the project's own errors, and `GET /api/compare` says how
  many.**  `ddd compare` and `ddd check --baseline` have always refused a candidate whose own
  project has errors, and the tab called such a project able to replace the baseline whenever the
  comparison itself found nothing.  The verdict now counts them, under the strictest reading of the
  build records that grade them, so one pair has one verdict whichever way it is asked, and the
  reply gains `own_errors`, an integer that is `0` for a project with none and is required, so that
  a client typed from the contract adds it, and one that reads the json ignores it.  The page itself
  says, under the verdict, how many errors the project has of its own and that the Findings tab
  lists them.  The tab also stamps a baseline before it reads it and keeps the read only if every
  file it was made of carries the same stamp afterwards, so a baseline saved during a read is read
  again instead of served stale, and a description baseline that is one flat file is kept from its
  first read: measured on a description of 20,000 declarations, the second ask took 0.92 s before
  and 0.14 s after.  A write that keeps a file's time and size exactly is not told, as the session's
  own watch does not tell it.

* **An edit through `ddd gui` is held to what the reader could do by hand.**  An edit cannot change
  which plugins the project's descriptions name: `POST /api/edit` answers it `409`, saying what to
  change in a text editor, and the Files tab refuses such a plan before the reader presses.  A file
  an edit creates is a description, named `*.ddd.json`, as every create flow of the page names one;
  any other name is refused.  The security page, and the warning `ddd gui` prints for a `--host`
  beyond loopback, say what the token amounts to: whoever holds it acts as the reader, since
  `ddd gui` runs what the project names, as `make` does, and a process of the same user is outside
  what the page defends.  A client that scripted `POST /api/edit` to change which plugins the
  project's descriptions name, or to create a file that is not a description, now gets the `409`;
  the page's own flows need nothing changed.

* **A build record's `project` is read under the rule a request's path meets.**  The start page's
  listing, its open and the builds that feed an open project read a `ddd-build.json` alike: a record
  whose `project` is not a path a request may name, or is not named `*.ddd.json`, is read as no
  record, so the project it names is not offered on the start page, and its builds do not feed it
  when it is open.  Opened by its path, on the command line, instead, such a project opens, but its
  records' severities still do not apply to it.

* **`localhost` is `ddd gui` itself, whichever of its two addresses a browser tries.**  When `ddd
  gui` listens on loopback, as it does by default, it listens on `[::1]` as well as `127.0.0.1`, on
  the same port, and answers on both alike, on every system.  `localhost` is an origin of its own,
  so a page opened there is signed out until the address `ddd gui` printed is opened there.  A fixed
  `--port` on which another program already listens at `[::1]` is refused before `ddd gui` starts,
  naming the port, and `--port 0` tries another port instead; a program that is merely bound there,
  and does not listen, does not take `localhost` from `ddd gui`.  A fixed port the previous run of
  `ddd gui` served on is served on again at once when it is started again.  Beyond loopback, as in a
  container, `ddd gui` does not listen on `[::1]`.  Nothing to migrate.

* **`ddd gui` says what to do when a launch code is presented again.**  A launch code signs one
  browser in, once; when it is presented a second time, `ddd gui` prints on stderr `ddd gui: a
  launch code that already signed a browser in was presented again. If the browser ddd gui opened
  is signed in, nothing more is needed; if it says it is signed out, stop ddd gui (Ctrl+C), start
  it again and open the address it prints then: this run's address, opened since, does not take
  the token back`.  A tool that matched the line's earlier text must match this one.

* **The Compare tab refuses a baseline that cannot be opened as unreadable, on every system.**  `GET
  /api/compare` answers `400` for a baseline whose path cannot be opened, on Windows as on every
  other system.  Nothing to migrate.

* **The page's wait for the state to change gives its connection back as soon as the page is gone.**
  The wait is still up to 25 s, but it looks every second whether the page is still there, and gives
  its connection back within a second of the page reloading or closing, so a tab that reloads never
  fills the sixty-four connections `ddd gui` answers at once.  Nothing to migrate.

* **`ddd gui --port 80` prints and opens an address a browser can use.**  The address it prints, and
  the one it opens the browser on, name no port, as HTTP's own does,
  `http://127.0.0.1/open?token=...`, and `ddd gui` answers the `Host` and `Origin` a browser sends
  there.  Nothing to migrate.

* **`ddd gui --host` takes the two addresses `ddd gui` listens on.**  `--host` takes `127.0.0.1`,
  the default, `0.0.0.0`, or a name resolving to either; any other host is refused, exit 2, before
  anything binds, saying what to give instead: `ddd gui` listens on `127.0.0.1` alone or on every
  interface.  `--help` and the command line page say so.  A `--host` naming any other address, a
  single interface of the container's own among them, gives `--host 0.0.0.0` instead, its port
  published on the host's loopback, as the security page's section on a container says, though in
  a container attached to several networks `0.0.0.0` listens on all of them; a build script or a
  CI job that passed one must change.

* **Every answer of `ddd gui` carries its content security policy, `nosniff` and no referrer, and
  every refusal is `no-store`.**  The standard library's own refusals of a request `ddd gui` cannot
  read - `400`, `414`, `431`, `501` and `505` - carry them too, each with a status line.  Nothing to
  migrate.

* **The licences the wheel ships list every package its pages bundle.**  The build of the pages
  wrote `third-party-licenses.txt` from the walk of `npm ls`, which prints a package's dependencies
  once, below the first entry it meets for that package, and shows the later entries for it bare.  A
  package first met below another was so neither listed nor held to the licences the project
  accepts: `scheduler` and `csstype` were left out.  The walk now visits every entry, and the build
  checks itself against `package-lock.json` before it writes the licences: it compares its list with
  every installed production package of the lock file, and exits 1 naming each one it did not list,
  and each installed package the lock file does not hold.  The directory of each package came from
  the paths `npm ls` prints, which npm stars out where one looks like a token, so a build under a
  path holding a uuid failed reading the first manifest, once Vite had built the pages; the
  directories now come from the lock file's own keys, and such a build works.  Migrating costs a
  clean install: a build of the pages in a tree whose `node_modules` was not installed from the lock
  file, and holds a package or a version it does not, stops, and `npm ci` makes the two agree.  No
  file format changes.

* **The source archive carries `SECURITY.md`, `.dockerignore` and `.gitattributes`.**  The archive
  is what an evaluator is sent, and it carries `docker/`, the compose file and the pages compiled
  into the package, but its list named none of the three files at its root that say how that tree is
  built and reported on.  Without `.dockerignore`, an image built from the unpacked archive copied
  the archive's pages in beside the ones its own stage compiles; without `.gitattributes`, the
  archive put under git on Windows checked the image's scripts out with CRLF line endings; and
  without `SECURITY.md` its reader had no private way to report a vulnerability.  It carries
  `requirements-release.txt` too, the file the release's tools are installed from.  Nothing to
  migrate: an image built from the unpacked archive is now the one a checkout builds.

* **A release is built only once every job of ci has passed on its commit, and its wheel is
  installed and run before anything is uploaded.**  Publish ran the python suite on one of ci's
  cells before it built a release, and took one look at the wheel it uploads, a listing of its names
  for `index.html`: no browser test, no Windows cell, and a wheel never installed.  It now calls
  `ci.yml` whole, on the release's commit, and builds only once every job of it has passed, the
  development builds apart, which a release never runs.  After the build, a fresh environment
  installs the wheel the upload jobs are handed, and `tools/installed_wheel.py` runs the installed
  `ddd` in an empty directory: `ddd --version` has to answer the tag's version, `ddd templates-dir`
  and `ddd cmake-dir` directories holding what the wheel carries, and `ddd gui` the wheel's
  `index.html` at the address it prints.  The tools that build and check a release are each at one
  version: `build` and `twine` in `requirements-release.txt`, which Publish installs them from,
  without upgrading pip first; `hatchling` and `hatch-requirements-txt` in the `[build-system]`
  table of `pyproject.toml`; `@vscode/vsce` where the extension is packaged; and `sphinx`, exactly,
  in `requirements-docs.txt`.  Migrating costs three things.  A release waits for the whole of ci,
  its Windows cells and journeys included, and a failing gate fails Publish's run, to be run again
  as *Re-run failed jobs*, or, where the fault is in the tagged commit and nothing has reached
  pypi.org, its release deleted and created again; the developer page lists the steps of a release
  in order.  A build of the project from its sources, a source archive among them, by any frontend
  that isolates its build, takes `hatchling` 1.33.0 and `hatch-requirements-txt` 0.4.1, so a build
  that has no index to reach needs those two versions in what it reaches.  And an environment that
  installs `requirements-docs.txt`, or the `docs` extra, has its sphinx replaced by 9.1.1, the
  release the documentation is built with.

* **Every wheel ci builds and uploads says it is a development build.**  The `gui` job of ci uploads
  the wheel of every run as `ddd-tool-<commit>`, and between releases master states the last
  release's version, so that wheel, though it held every commit since, said it was that release: to
  `ddd --version`, to the banner of every file it generated, to the module's handshake and to pip.
  Only the wheel `dev-build` puts on TestPyPI was numbered as a development build.  The `gui` job's
  wheel is now numbered as it is, `<next patch>.dev<run number>`: after 0.11.0, run 57 builds
  `0.11.1.dev57`; and after a release candidate the next candidate's development build,
  `0.12.0rc2.dev57` after `0.12.0rc1`, which sorts after the candidate and before both of what can
  follow it, the next candidate and the release.  The commit the wheel was built from is named in
  its metadata, and for a pull request it is the merge ci tests.  Master's source keeps the last
  release's version, so a wheel built from it locally, with `python -m build`, carries that version;
  and a release's own build is never stamped, so a release says it is itself.  Migrating costs a
  version: a job or a script that installed the artifact of a run and expected the last release's
  version, a requirement pinned to it, or a comparison of what `ddd --version` prints with it, now
  meets the development version, which pip counts a pre-release.

* **A release's page on PyPI links that release's own documentation.**  The README is the
  description PyPI shows for a release, and its links into the documentation point into `latest/`,
  which follows master: the right pages for the tree, and for the reader of a release, pages of what
  it may not have, beside a `Documentation` url naming the site's root, which lands on whichever
  release is newest.  0.11.0's page links `latest/` and never `v0.11.0/`.  Publish's build now
  points every one of them, the link to the root of the site among them, and the `Documentation`
  url, at `v<version>/`, in its own checkout, before it builds and with nothing committed, so the
  README and `pyproject.toml` the source archive carries are pointed too; the check of the installed
  wheel refuses one whose description links the documentation anywhere else, or nothing of it, or
  whose url is not that directory.  The classifiers name the systems the tests run on, Windows and
  Linux, in place of `Operating System :: OS Independent`; macOS is not claimed.  Migrating costs a
  wait and a filter.  The directory of a release is written only once Publish's run has succeeded,
  so a release's links do not resolve until its documentation is published, longer where a run waits
  on a reviewer or a re-run; and a tool that selects packages by the classifier `OS Independent`
  finds Windows and Linux instead, the wheel being pure python and installing on macOS all the same.

* **A release's documentation is published once Publish's run for it has succeeded, and a push to
  master no longer cancels it.**  The release event started Documentation beside Publish, and
  neither waited for the other: a release that Publish then refused or failed was published all the
  same, and the root of the site, which lands on the newest release, followed it to a version PyPI
  never received.  The release event now starts nothing there.  Publish's run completing does, and
  the run goes on only if it was a release's and succeeded, every job of it, the extension's `.vsix`
  included; it builds the commit the release's tag names and publishes it under that tag.  Each such
  run is alone in a concurrency group of its own, where a release's run waiting behind master's was
  cancelled by the next merge, with nothing red and no directory published.  A release's deploy and
  master's may now run at once, so a push that `gh-pages` refuses takes the branch as it stands,
  puts the build's directory back on it, rewrites the index and pushes again, and fails after five
  refusals.  A release tagged on a commit from before this still has that commit's own `docs.yml`
  publish it on the release event, GitHub running a release's workflows from its tag, and master's
  publishes it again once Publish succeeds.  Migrating costs one habit.  A release whose Publish
  reached PyPI and then failed has its documentation published by *Re-run failed jobs* of that run,
  *Re-run all jobs* not passing once the index holds the version; and one no re-run can finish,
  where what failed is in the tagged commit, by a dispatch of Documentation from master naming the
  release's tag as `tag`, which builds the commit the tag names, refuses a tag that is not `v` and
  the version `pyproject.toml` states there, as Publish does, and refuses, before anything is
  built, a version pypi.org holds no file of.  A release that never reached pypi.org is not
  published so: it is deleted with its tag and created again, as the developer page's steps of a
  release say.  A dispatch naming no tag is what it was.

* **`SECURITY.md` says where an advisory appears, and which versions it names.**  The policy said
  which release is supported and how to report a vulnerability privately, and nothing of an
  advisory.  It now says that an advisory names the versions it covers, supported or not, and that
  advisories appear on this repository's Security tab, as GitHub security advisories, and, for a
  release that fixes one, in that release's entries in the changelog.  Nothing to migrate.

* **The README and getting started say what runs from the sources before the dependencies are
  installed.**  Both had the reader run the tool out of a checkout with nothing installed, and the
  getting started page said that every command it shows works so.  Without `pydantic`, `jinja2` and
  `pyelftools`, `--version` and `--help` answer, and `check` fails at its first import, naming
  `pydantic`.  Both pages now have the reader install `requirements.txt` first, which installs
  nothing of ddd itself, and say what answers without it.  The getting started page also named
  `pydantic` and `jinja2` as the only runtime dependencies, and so as the only two an offline
  install has to reach; `pyelftools` has been a third since the toolbox, and the page now says so.
  Nothing to migrate.

* **A file is checked under the outermost project that includes it, as `ddd check` checks it.**  The
  server stopped at the first directory above a file that held a description including it, so a
  component of a sub-project was checked under the sub-project alone, which does not know what the
  rest of the outer project produces: a clean project showed `missing-producer` errors the build
  never reports, and a rename from there edited that file alone and left `ddd check` of the outer
  project failing.  It now walks up to the workspace folder holding the file and answers from the
  descriptions of the outermost directory that include it; a description nearer that includes it too
  is a sub-project of the outer one, and is dropped.  A build record is still asked first, and a
  project description that no description above includes is checked as itself.  Migrating costs two
  things.  A sub-project that is to be answered as itself in the editor is configured, so that its
  build record names it.  And to find the outermost, the server reads every description at or above
  the file, up to its folder, and imports the plugins each names, where it stopped at the first:
  opening a file runs the python of every description above it, as `ddd check` of the outer project
  would, so a repository is opened only when its build would be run.  No file format changes.

* **A file's findings are withdrawn only by a run that reported on it.**  A refresh published an
  empty list for every file it had published before and its run did not name, so opening a file of
  another project, or a watched change with several documents open, erased findings that `ddd check`
  still reports; and a file deleted since was read again from its path, which published a finding
  about a file that does not exist.  A check now withdraws the files a run of it reports on and
  finds nothing wrong with, and the files a run from the same project or document reported on the
  last time and no run reports on now: a component taken out of its project's `includes` leaves the
  screen, as it leaves what `ddd check` reports.  Any other file keeps its findings.  A description
  the editor reports changed is checked again where its findings are on screen or a check ran from
  it, whatever is open, so a pull that mends a project nobody has open mends what is shown of it.  A
  file that was deleted has its findings emptied once and is not refreshed from its path, and an
  open document that is not on disk, a new file not yet saved, keeps its findings.  Nothing to
  migrate.

* **A file reached through a junction or a link has its findings under one spelling.**  A file has
  two spellings, the one the client opens it under and the resolved one the loader reads it by, and
  the server published under the resolved one until the client opened the file and under the
  client's from then on, withdrawing nothing under the first: the old findings stayed on screen
  beside the new, and stayed once the file was fixed.  It now keeps the uri each file's findings
  went out under, and withdraws them there when they go out under another.  A quick fix asked at a
  producer opened through a link took the declaration under the client's spelling, which equalled no
  place of the project's index: the producer was read as a reader of its own variable, its own value
  was offered back to it, its removal was lost, and its fixes were ordered as a reader's.  It is now
  the declaration at the resolved path.  Nothing to migrate.

* **An open document's findings are drawn in the text the editor holds.**  The findings are the
  disk's, checked as the file was last saved, and each was drawn where the file on disk has its key:
  with lines added above that key and not saved, a save of another file, or the open of a buffer the
  editor restored unsaved, drew the squiggle over whatever the buffer held at that line, and a
  client asking for the quick fixes where it had drawn the finding was offered none.  They, and the
  notes of any finding that point into the document, are now drawn over the key where the text the
  client holds has it, over the nearest key around it where it does not, and at the top of a text
  that is not json.  What a document declares itself to be, which decides how it is checked, is
  still read from the disk.  A finding names its key by its place in the file, so a declaration
  typed above the one it is about, in the same list, takes the finding's place until the file is
  saved.  A document closed without saving, its findings drawn in a buffer whose lines are not its
  file's, is checked again, so that they are drawn where the file holds their keys, where they
  stayed at the buffer's lines.  Nothing to migrate.

* **The hover speaks for every project holding the file, and names the ones it cannot.**  It said
  who writes a variable and who reads it from the first project holding the document alone: a writer
  linked into two images was read by the first image's reader, while find references listed the
  second's too; of two components writing one variable it named the one the analysis builds the
  object from; and where a file did not load it said that nobody reads the variable, or that no
  component produces it, with nothing saying why that might not be so.  It now resolves each project
  holding the document, and names the writers and the readers of all of them, each component once,
  and both where two write one variable.  Where it says that no component produces the variable, or
  that none reads it, a line under it names the files of those projects that did not load; and where
  a plugin stops a project holding the file, a line names that project, by its image or by its
  description where no build record names an image, since who writes and reads the variable there is
  in no answer.  The rest of the summary, the shape and the limits, is the first project's.  It says
  a value spans the whole range of its datatype only where it does: an enumeration whose table runs
  from the datatype's lowest value to its highest is told so, and a table of 0 and 1 over a `uint8`
  is not.  Nothing to migrate.

* **A rename reaches every project that holds a file it rewrites, or is refused naming the image.**
  A rename visited only the projects holding the document it started from: started from the reader
  of one image, it rewrote that reader and the writer the two images share, and left the other
  image's reader naming an object that no longer exists, where the same rename started from the
  writer rewrote all three.  It now takes the projects of the document it starts from, then every
  project holding a file their edits rewrite, until none is new, whatever is renamed: a variable, a
  type, a constant, a section, a raster or a unit.  The images are those the server finds for the
  file, by their build records or, where none claims it, by the search above it.  Each project
  reached is asked every refusal a rename makes before anything is written.  Where a project the
  document is not in already uses the name, declares the type an external one or holds a file that
  did not load, or loaded with an error that stops the project being analysed, the refusal names its
  image, or its description, by its path in its workspace folder, where no build record names an
  image; an unsaved change is refused naming the file that holds it, wherever it is.  Migrating
  costs what a refusal asks: where the name is taken in another image, it is renamed there first, or
  the new name differs.

* **A rename is refused where the editor could not see what it would change.**  A rename is planned
  from the files on disk and the project read from them, and several states of the editor are not
  that.  It is refused, naming the document, while an open document of a project it reaches parses
  to something other than its file, a mention typed and not saved being one it cannot see; a CRLF
  file does not differ from the buffer the editor sends for it, and a buffer that does not parse
  does.  It is refused for a closed file changed on disk since the project was read, as that and not
  as unsaved changes, until the server reads the project again, at the next open or save or when the
  editor reports the change.  It is refused where it would rewrite nothing, which an editor applies
  without a word.  With no project known, a component that no build record claims, that no
  description above includes and that declares no project itself, every rename but a local
  variable's is refused, saying so, where it rewrote that one file and said nothing, leaving every
  other file spelling the name holding it.  And where a description it needs cannot be read, because
  a plugin of its own stops it, whether a build record names it or the search above a file found it,
  every rename but a local variable's is refused, naming the description and why, since the files
  it holds would be rewritten for no image, where a local variable is spelled in its own file
  alone, whichever image holds it.  Each costs a step and the rename asked again: save the file,
  put a project file above the component that includes it or configure the build, or mend the
  plugin.

* **An external type is not renamed, from the editor or from the page's Types tab.**  An external
  type names a c type that the header beside it defines: no typedef is generated for it, only the
  include of that header, so its name is the header's and not the description's.  Rename Symbol
  rewrote its entry and every `typename` naming it, as did the Types tab, while the header went on
  defining the old name: every check stayed clean and the build stopped at its first compile.  Both
  are now refused, in one sentence naming the header, and the editor names the image as well where a
  project the rename reaches declares the type so; `prepareRename` still opens the box on an
  external type, and the rename refuses it.  A variable spelled like an external type is still
  renamed, and no quick fix renames a type.  Migrating costs a rename by hand, of the c type in its
  header and of every entry and `typename` in the descriptions, together.

* **A unit's rename is made over every image it reaches, or refused, naming the file.**  A unit is
  renamed from any place it is stated, or from its entry in a units file, and merges into a unit
  that exists.  Two images sharing a units file, the one listing the unit renamed onto and the other
  not, would rewrite one entry two ways, merging the old spelling into the other for one and
  respelling it for the other; such a rename is refused, naming both images and the one that lists
  the unit.  The edit engine can also refuse an operation of the plan in a text other than the one
  the project was read from, a file spelling a key like a list's position, which the loader takes no
  file for: that was answered as a defect of the server, and the lightbulb with it, and a batch of
  sets sent unread was written over that key's value, leaving the list as it was.  The plan is now
  rendered file by file, and read back once per file before it is sent, and a file the engine cannot
  make it in, or whose edits would read back otherwise, refuses the rename naming the file: an open
  document as one that differs from its file, a closed file as one changed on disk since the project
  was read.  Migrating costs a step where the images a rename reaches share a units file and only
  one of them lists the unit renamed onto: the unit is listed in both or in neither, as the refusal
  says, and the rename asked again.

* **A new name is written as json spells it.**  A raster's name may hold a quote or a backslash, and
  the editor's rename wrote the new name between the quotes as it was typed: a quote ended the
  string, so no file the rename rewrote parsed, and a backslash began an escape, so the name read
  back was another.  Every rename now writes the new name as json spells it there.  Nothing to
  migrate.

* **A constant's rename rewrites a condition that spells it, and its uses count conditions.**  The
  shipped templates define each constant as a macro in the types header, so a `condition` may spell
  one, and `#if` reads a name nothing defines as 0.  A constant's rename left such a condition
  spelling the old name, and the object it guards was compiled out with every check clean; and the
  Shared files tab counted a constant's uses by its shapes alone, so a constant only a condition
  spells read as used by nothing, and its removal went through with the same result.  The editor's
  rename and the tab's now rewrite the constant's word in each condition spelling it, and nothing
  else of it: every other word, and every longer identifier holding the constant, is left as
  written; both refuse while a condition they read no longer spells it.  The tab's count, the uses
  its panel lists and its refusal to remove a constant read conditions too, the refusal counting
  uses where it counted shapes, and `GET /api/constant` lists a condition among a constant's `uses`,
  after the shapes, as a use of the variable whose declaration it guards.  Migrating costs a step
  where a constant only a condition spells was removed through the tab: the condition is changed
  first.

* **A request the server fails on is answered, and the session goes on.**  Three inputs raised out
  of the server and ended the session, with every finding on screen, and a client stops restarting a
  server that the next hover ends again: a hover on a parameter whose `init` is `[]`, a hover on a
  `float64` block whose `init` runs from -1.7e308 to 1.7e308 in a project `ddd check` passes, and a
  build record naming its project by a relative path.  Each message is now answered inside a net: a
  request the server fails on through a defect of its own is answered with the protocol's internal
  error, `-32603`, naming the method and the fault, a notification is answered with nothing, as
  ever, and the trace goes to the server's standard error, which is its log and which VS Code shows
  in the **DDD** output channel; only an interrupt still ends the run.  The three inputs are mended
  as well, so the net is not what answers them: an `init` that holds no values draws no rows, a
  sparkline whose span is more than a float holds is drawn against a halved span, and the server
  skips a record that names its project by a relative path, or by a path with no root, which a
  build never writes, announcing why as it does for any record it cannot use.  A client shows a
  request that fails as a failed request, VS Code with a notification.  Nothing to migrate.

* **While a file of the project does not load, no quick fix is offered, and the log says why once.**
  A quick-fix request was answered with an error while a file of the project did not load.  A client
  asks for the quick fixes at every move of the caret, and VS Code shows a failed request as an
  error notification, so a reader mending a schema error was shown one at each move, naming no file.
  The request is now answered with an empty list, and the reason, naming the file, is written once
  with `window/logMessage`: at the first request the unread file empties, and again only once the
  project has been read whole and is found broken anew.  A file that breaks two images is said once.
  The reason is the unread file's own finding as well, and an empty lightbulb in such a project has
  its reason there and in the log.  A file that did not load is said not to have loaded, and one
  that loaded with an error that stops the project being analysed, such as a block for a plugin that
  does not import, to have that error; two unread files of one name are told apart by as much of
  their path as it takes.  Nothing to migrate.

* **A request of another shape is refused, naming the field.**  The server read several fields of a
  request without checking them, so a client sending one of another shape was answered as if the
  server had failed through a defect of its own, with the internal error and a trace on stderr: the
  findings a code action is asked about, when they were `null` or a number, or held an entry that
  was no object or a code that was neither a number nor a string; a position before the start of the
  document; an `initialize` whose params, root or folders were of another type; and a uri whose path
  or host holds a null character or a lone surrogate, which no file system takes and which every
  notification naming it met as well.  Each is now refused with the invalid-parameters error,
  `-32602`, naming the field, and nothing goes to stderr; a notification is answered with nothing.
  The client capabilities `initialize` reads are checked the same way: a step of them in another
  shape refuses the handshake, where it was taken for no announcement, and a step left out still
  announces nothing; a `rootUri` of another shape is refused, beside named folders too, and a
  refused handshake keeps no folder it named.  A boolean is no longer taken for a number.  Migrating
  costs a client that sent such a field the shape the protocol gives it.

* **The fixes of a `definition-mismatch` say what they leave alone, and the preferred one is the
  owner's.**  The title of each editor fix reconciling a `definition-mismatch` now ends with the
  sentence the page's carry, that the code of the readers is not touched.  The fix an editor applies
  by itself, the one marked preferred, is the first fix only where it goes the owner's way, a reader
  taking its producer's value or the producer sending its own: where that way is not offered, none
  is marked, where the next in the list took its place; and none is marked where two components
  write the variable, or none does, since the tool has no standing to pick a winner among two or for
  nobody.  Both ways are still offered there, in the same order.  Migrating costs a client that
  matched a fix by its title the new title, and a reader who applied the preferred fix of such a
  variable by itself picks one.

* **A fix reads a declaration's keys through the type it names.**  A declaration naming a declared
  type states, in its own file, none of the keys the type fixes, and the fixes read that file alone.
  A reader of a writer naming a type was offered one fix, and it was the preferred one: take its own
  unit out, under a title saying the writer declares none, after which the reader stated no unit
  against the unit the writer's type states; a writer whose reader names a type stating another unit
  was offered the same removal of its own unit, and the reader's type went on stating its unit
  whichever was taken.  What a declaration states for such a key is now what it resolves to, as the
  checks read it.  The producer's value is read through its type, so the reader is offered the unit
  the writer's type states; a declaration whose type states the key counts as stating it, so no
  removal is offered beside it, nor of a key a type that one of the other declarations names states;
  readers naming types that state two units are two answers, and nothing is offered; and a type
  whose entry has moved, in a types buffer with another type inserted above it, say, is taken for
  unknown and not for silence, nothing being offered then either.  `ddd gui`'s button for a
  `definition-mismatch` reads the same way: the reader of a writer naming a type is offered the
  type's unit, where it offered nothing, and a removal beside a type that states the key is dropped.
  Nothing to migrate.

* **An edit that reaches several files asks the client to confirm it.**  A client applies a code
  action's edit and saves every file it touched, so a fix or a rename across files rewrote
  components the reader had not seen.  An edit reaching two files or more, a rename's or a quick
  fix's, is now sent with one change annotation marked `needsConfirmation`, named by every text edit
  of it, to a client that announced both `documentChanges` and `changeAnnotationSupport`: the client
  shows it first, and the reader may leave a file out, which applies it in part, by the reader's
  choice.  A client that announced only one of the two gets the edit as before, and applies it at
  once.  Migrating costs a client that announced both a prompt where the edit applied at once; VS
  Code shows the edit in a preview.

* **A fix is offered once across the images it reaches, and not past a buffer that moved.**  A quick
  fix sending a declaration's value out to the others, or taking a key out of them, left out a
  declaration whose unsaved buffer had moved it and wrote the rest, so it was applied in part where
  the rename beside it was refused whole.  It is now not offered while that buffer stands.  A
  component linked into two images is in two projects, and each project offered its own fixes: where
  both images offered one it came twice, each copy preferred, and at a writer the two images share,
  one fix per image reached that image's reader under one title, none reaching both.  The fixes of
  every project holding the document are now put together, each once.  A fix taking another
  declaration's answer in is offered where the projects offering it write one edit under one title,
  and not where two write different edits; a fix sending this declaration's answer out is one fix
  over every declaration of the variable in each of those projects, and in every project holding a
  file it writes, until none is new, as a rename reaches them, so the fix pressed at one image's
  reader reaches the other image's through the writer.  Every fix is withheld where one reaches a
  project holding a file that did not load, or loaded with an error that stops the project being
  analysed, or a description beyond the document's own that cannot be read; the preferred fix is the
  one every project offering a fix leads with, where it was chosen before a fix reaching another
  image could be withheld there.  The fix that respells an unknown unit is the rename `F2` makes,
  over every image it reaches, and is not offered wherever that rename is refused; the unit is added
  to the vocabulary only where every image planning it adds it to the same file.  Migrating costs a
  step where a fix is now not offered: a buffer that moved a declaration the fix writes is saved,
  and where the fix that respells an unknown unit is withheld because Rename Symbol is refused, an
  unsaved document of a project it reaches among the reasons, the step that refusal names is taken;
  the fix is then offered again.

* **Each fix carries only the findings it settles.**  A fix reconciling a `definition-mismatch`
  carried every mismatch finding of its declaration though it settles one key, so a client listed as
  settled a finding that was still there.  It now carries the findings that name its key alone: a
  declaration that differs in two keys is settled in two steps, and the fix of each is still
  offered; a finding naming both is carried by neither, one naming references carried by the fix of
  the reference that differs, and none by a map's, whose finding names no axis; a finding a client
  sends that names no key is carried by all, as it always was.  Nothing to migrate.

* **An edit the server builds ends its lines as the file it goes into does, and the id fix writes
  what `ddd id` writes.**  A closed file is read through universal newlines, so an edit built for
  one said a line feed wherever it had a line to end: a quick fix's, a unit plan's and the id fix's,
  into a file that ends its lines with a carriage return and a line feed or with a bare carriage
  return.  Every edit now ends its lines as the document it goes into does, the first ending it
  uses, from an open buffer or into one: a value copied over lines ends them as the closed file
  does, and one into an open buffer as the buffer.  A file that mixes line endings gets the first
  spelling for every edit.  The fix that gives a declaration an identity is made by the edit engine,
  as `ddd id --assign` makes it, so it writes the same bytes, for an object written on one line or a
  file of bare carriage returns, and lays out the one declaration it is asked of where it laid out
  every declaration of the file.  Nothing to migrate.

* **A save is analysed once per project, and a unit's plan is rendered from the text as it was
  read.**  A save reaches the server twice, as a `didSave` and as the change the client's watcher
  reports for the file the editor wrote, and the event checked every open document on its own: with
  several documents of one project open, the project was analysed again for each, every hover
  resolved it again, and the hovers and the renames waited behind those analyses.  Opens, saves and
  watched changes that arrive together are now checked together, once the server has handled every
  message already waiting behind the first of them and before it answers a request that came after
  them, never waiting for a message not yet sent; one check analyses each project once however many
  of its documents are open, reads each description once, and keeps the hover's dictionary for each
  project until what was read is dropped.  A unit's rename, Rename Symbol's and the quick fix's that
  respells an unknown unit, was rendered by making the plan's operations one after another, a
  document of the whole file built after each, so a rename over a file stating the unit N times
  built N documents of it, and a code action at an unknown unit did the same at every move of the
  caret.  A batch none of whose operations can depend on another, which a rename's sets are, is now
  made against the text as it was read, as `ddd gui` makes such a batch, and the entries a merge
  takes out, each moving the ones after it, are still made in turn.  A file written on one line
  still pays more for each edit than one written a line to a member.  Nothing to migrate.

* **The extension starts the server once a description is open or the workspace holds one.**  The
  extension is activated by any json document, as well as by a workspace holding a description, and
  it started the server at once, so a trusted workspace that opened a json file of any name ran `ddd
  lsp`, and where `ddd` is not installed showed its error there.  It is still activated by a json
  document, since a description opened outside a folder, or created after the window opened, is
  announced by nothing else, but it starts the server only once a `*.ddd.json` is open or a
  workspace folder holds one, asking again as documents are opened and folders change, and once
  started the server stays.  Nothing to migrate.

* **The server asks the client to watch the descriptions and the build records.**  The watcher was
  the extension's, so an editor that launched the server itself heard of no file changed behind it,
  and a configure that rewrote only a build record left the old severities on screen until the next
  save, the record being no description.  Once the client says it is initialized, and where it
  announced `workspace.didChangeWatchedFiles.dynamicRegistration`, the server now registers a
  watcher for `**/*.ddd.json` and `**/ddd-build.json`; a client that did not is asked for nothing,
  and a file changed behind it is read again at the next open or save.  A change of a build record
  forgets what was found and checks again, under the records as they now read, the open documents
  and every file whose findings are on screen; a record, or any other file that is no description,
  is never checked as one, which had given it a finding of its own.  A change reported for a
  description named in capitals, which the loader reads, is checked with nothing open as well.  The
  client's answer to the registration, a message carrying an id and no method, is answered with
  nothing, where it was refused as a request of a method named `None`.  The extension makes no
  watcher of its own any more.  Migrating costs a client author one thing: a client that announces
  the dynamic registration needs no watcher of its own for the server, and one that keeps its own
  sends every change twice.

* **The workspace folders the client adds or removes while the session runs are followed.**  The
  server announced no support for workspace folders, so a client sent no change of them: a document
  of a folder added after the start was checked as one outside every folder, on its own, though its
  project was there to be found.  It now announces that it follows them.  A folder added is searched
  as one named at initialize, its build records found and the open documents checked again; a folder
  removed is answered as if it had never been named: what was published under it alone is withdrawn,
  and the open documents and what is on screen are checked again, so a file outside it keeps no
  finding only its checks gave.  With every folder removed the server answers in the directory it
  was started in, as for a session that named none.  Nothing to migrate.

* **A relative `ddd lsp -b` is read against each workspace folder.**  It was read against the
  directory the server was started in, which VS Code makes the first workspace folder: in a
  workspace of several folders the builds beside the others went unfound, as did the build of a
  folder added later, and a server an editor started elsewhere searched beside that directory
  rather than beside its folders.  The server now reads a relative `-b` against each folder the
  client names, those it adds while the session runs among them, and against the directory it
  was started in only while the client names none; a record two folders reach is counted once.
  An editor that starts `ddd lsp -b <dir>` from a directory that is none of its workspace folders,
  meaning that directory, names it absolute.  A relative entry of the extension's
  `ddd.buildDirectories` means what it did in a workspace of one folder, and in one of several
  finds the build beside each.

* **A change of `ddd.executable` or `ddd.buildDirectories` says it takes a restart.**  The extension
  reads both when it starts the server, and listens for neither changing, which no setting or page
  said, so a changed setting looked as if it had not taken.  The settings' descriptions, the
  extension's page and the editor page now say that a change takes effect once the server is
  restarted, with **DDD: Restart Language Server**, the command for it.  Migrating costs that
  command after a change of either, as it always did.

* **A type's change that the loader would refuse is refused, and a range is written as typed.**  The
  Types tab planned whatever a key was set to: a datatype that names none, limits whose maximum is
  below their minimum and a linear conversion of factor 0 were each previewed, and Apply wrote them
  into a types file that then failed to load, with every type the file declares.  Each is now
  refused as `invalid` before it is planned, in the words `ddd check` files it in, naming the type
  and its file, and the route answers it 409.  A type that `ddd check` refuses already, derived
  limits past the largest float among them, is not refused again for it: a change that leaves that
  refusal as it was is planned, the value a row holds among them, and so is one that mends it, while
  one that brings another is refused; a key taken out is asked of the entry without it.  A range
  typed into a type's Min or Max, or a variable's, reaches the file in the digits it was typed in,
  `1e3` as `1e3` and `12.50` as `12.50`, a float's given a point where it was typed whole, where the
  file took the shortest spelling of the double the page had weighed it as.  Migrating costs nothing
  but the correction of a type that was to be written in a state the loader refuses, and a client
  that scripted such a change meets the 409.

* **Limits that no declaration states are written on the producer.**  A reader may leave its limits
  to whoever states them, which `ddd check` counts as agreement, and the settlement of a variable's
  panel applied that to every declaration that states none: a range typed into the panel's two
  fields reached none of them, the panel said there was nothing to change, and a declaration made in
  `ddd gui` could never be given limits.  The producers take them now, every declaration of a
  producing scope, on each of two where two produce the variable, and the readers go on leaving them
  to them; a variable no declaration produces is refused `invalid`, saying that no declaration
  produces it, since none is the one to state them.  A reader naming a scalar type that fixes no
  limits is no longer refused in a sentence untrue of that type.  The two bounds of a range are
  compared as the exact numbers `ddd check` compares, so two maxima past 2^53 that it files as a
  `definition-mismatch` are two values on the panel, and the finding carries its fix, in the page
  and in the editor, where a rounding made them one.  Nothing to migrate.

* **A variable's panel reads a type and what it fixes as `ddd check` does.**  The `typename` row
  said the declarations disagreed wherever one named a type and another stated nothing there, though
  `ddd check` files nothing when the other spells what the type fixes: a tinted row that no
  settlement could clear, on a project the tool calls consistent.  The row now disagrees only where
  two declarations name different types, and a unit of no text beside none is no disagreement
  either.  Two types of one meaning are still told apart by name, and an external type beside a
  scalar is still `type-kind`.  The graph draws a structured variable's arrow, where a structure
  whose modules it joins showed them joined by nothing and a mismatch over it coloured no arrow, and
  names the object of a disagreement by the declaration its finding points into, where a declaration
  the analysis dropped moved the name to the next one.  The key chooser of a variable's panel, and
  the choosers of the add form, offer no local another component keeps, which only its owner may use
  and which wrote a `local-conflict`; a form for a declaration no file holds yet has no component to
  compare, and still lists them all.  Nothing to migrate.

* **`ddd gui` notices a change it missed, and analyses again.**  The poll stamped the files an
  analysis had read and nothing else, so some changes made no new revision until another file moved,
  and the page went on showing findings `ddd check` no longer reports: a component saved where a
  pattern of `includes` matches, a plugin a description names by its path where another plugin's
  model had ended the read, and a build record written or mended, its severities being the
  analysis's own.  A revision now names what it watches beside its files: the directory each
  wildcard of the project's descriptions expands in, and those a `**` walks, though no directory a
  pattern only passes through; every file a `plugins` list names by its path, loaded or not, and not
  a plugin named as a module; and every build record the search finds, one that is refused among
  them.  A record beside a description that cannot be read as one is refused, and watched, so that
  mending it makes a revision.  Each file's fingerprint is the one of the run the revision's index
  came from, as that run read it, so that a description saved between the runs of two builds and put
  back no longer lets a plan pass the `stale` check against bytes it does not describe.  The records
  that feed an open project are read under the project's own directory too, as the record beside its
  description is, and the start page's listing keeps the directory `ddd gui` was started in.
  Nothing to migrate.

* **A description beside a build record that does not read is refused, and a description added to a
  generated project is offered its line.**  A record beside a project description that did not read
  as one - a write of it cut short, an empty file, a document that is no object - was read as no
  record, so the description that the build writes again at every configure was open to edits that
  configure undoes.  `ddd gui` now takes that description for the build's: every change under its
  build tree is refused `generated`, in one sentence naming the record and the tree, until the
  record reads.  An empty `CMAKE_HOME_DIRECTORY` in the cache above a record names no source tree,
  as no entry does, where it was read as the directory `ddd gui` was started in, which decided how
  much of the build tree around the description was refused.  Add a file, for an existing
  description in a project a build generates, was refused `generated` with the build's membership
  alone, where New file offers the `ddd_add_component()` line that registers the file it creates: it
  now offers that line too, to add to the `CMakeLists.txt` beside the description, and passes over a
  description lying under the build tree, which goes with the tree.  Migrating costs, for a
  description refused beside a record cut short, a configure of the build, which writes the record,
  and for one added, the line the offer gives in the `CMakeLists.txt`.

* **A plugin saved while `ddd gui` runs is told, by `plugin-changed`.**  A module is imported once
  per process, and a plugin named by its path is one module for every later load, so a plugin saved
  while `ddd gui` runs went on running its old code, with every finding after the edit its, and
  nothing said so.  `ddd gui` now files `plugin-changed` on the plugin's file when it holds other
  bytes than the module was run from: an error by default, since every finding after the edit is the
  old code's, and relaxable, since nothing of the project went unread.  Only `ddd gui` files it,
  `ddd check` and `ddd compare` import afresh and the language server does not file it; a restart of
  the server, or the file holding the bytes it was imported from again, ends it, and the same bytes
  saved again are no change.  A module a plugin imports is not watched and a plugin named as a
  module is not compared, so an edit of either takes the restart unsaid, as it did.  No plan or edit
  is refused for it.  The Compare tab counts it among the project's own errors, as it counts any, so
  its verdict is a refusal while the error stands, where `ddd compare` never files it.  A check
  identifier is only ever added to, and this is one: `ddd checks` and the check reference list one
  more, which a script that counts them finds, and `-W plugin-changed=...`, `SEVERITY` in cmake or a
  build record's `severities` relax it; a DDD from before this one declines a build record that
  names it, as it declines any check it has not got, so a team on mixed versions that relaxes it
  upgrades its editors first.  Migrating costs a restart of `ddd gui` after a plugin is edited, or
  that relaxation.

* **A plugin whose file cannot be read is `plugin-invalid` in every command.**  A `.py` plugin whose
  file the process could not read, but whose bytecode cache was valid, was loaded from the cache by
  every command, as though nothing were wrong.  The loader now reads the file's bytes before it runs
  the module, so that it is imported from the bytes it can say it was run from, and a file it cannot
  read fails to import as `plugin-invalid`, naming the file, in every command that loads plugins,
  and not only in `ddd gui`.  Migrating costs, for a project carrying such a plugin - a checkout
  whose permissions the build's account lacks, with a `__pycache__` beside it - the permission to
  read it.

* **A plan in a large file answers at once, and a large project opens quickly.**  A plan's preview
  found the lines its edit changed by comparing the whole file before and after it, which cost more
  the larger the file.  A plan's lines are now read off the spans its operations replace, however
  long the file, and one span of several lines whose middle line is unchanged is one hunk where the
  page drew two; the preview of an undo, which holds two texts and no operation, compares them as
  before.  The panel that offers a name to declare names the component producing each from the
  index, as the analysis loaded it, and reads no producer's file, so a producer renamed in its file
  since the analysis is named as it was until the next one reads it.  A project held already is
  opened without walking for every project first: the open project, and one the last listing found,
  each where the walk would still find it, and the one named on the command line wherever it lies,
  where it walked the start directory for every project first; a path that is none of those, or
  that the walk would not find now, is walked for as before.  A change to a shared file's entry, a
  constant's value among them, no longer looks for the vocabulary's files, which only adding one
  needs.  Nothing to migrate.

* **A refusal a page can mend is a refusal, and it names the file.**  A file this process may not
  write was refused before anything was staged, as `unwritable`, and answered with the status of the
  server failing on the request: it is a `409` now, as every refusal the page can act on is, from an
  edit, an undo and the undo's preview, and the page shows the server's sentence while nothing is
  written.  A plan asked while an edit of the page's own that moved its place has not been analysed
  is answered `analysing`, and not `stale`, a sentence saying a file was saved from elsewhere: a
  plan that reads a file such an edit wrote, whichever file its place is in, asks once that analysis
  has landed, where a place moved by a save from elsewhere is `stale` still.  The sentence saying a
  file did not load names it - a change of a component's interface refused for a project that did
  not load named no file - and tells two of one name in different folders apart, by as much of their
  paths as tells them, on the server and on the Types and Shared files tabs' line.  Declaring a name
  that a component keeps `local` as a new object is refused, naming that component, where it was
  told the name is already declared.  Migrating costs a client that scripted `POST /api/edit` and
  answered a read-only file's `500` the `409`, and one that read `stale` for a plan asked while the
  page's own edit waited meets `analysing` first, and asks again once that analysis has landed.

* **An edit may be as large as a large project's rename, and a plan too long for its address says
  so.**  An Apply posts every change of its plan, each file's path, fingerprint and operations, and
  the rename of a unit stated in many files of a large project outgrew the 1 MiB every request was
  read up to: it was refused `413`, and the browser, meeting the close while it was still sending,
  said `ddd gui` was not answering.  `POST /api/edit` takes a body of up to 8 MiB now, read only
  once the request has shown the token and this server's own origin, and every other request keeps
  the 1 MiB it had, the drain of a refused body among them.  A plan the page asks by `GET` carries
  what it plans in its address, and the server reads a request line of a limit: any ask whose
  address is longer than that is refused before it is sent, in a sentence naming its route, where
  only the values plan was and the others showed the standard library's own `414`.  A values table
  past about 10,000 counts is not one `ddd gui` takes: one whose counts outgrow the address is
  refused as it is pasted, in a sentence saying to set its values cell by cell, or in its file in an
  editor.  The answers the standard library's server gives a request it cannot read, `400`, `414`,
  `431`, `501` and `505`, are drained before the close as `ddd gui`'s own are.  Migrating costs a
  table past that size its cell by cell, or its editor.

* **A finding leads to a panel that lists it, shows its place where it leads nowhere, and is counted
  once.**  A finding with no route to offer shows where it is, `file:line:column` or its pointer,
  and a file that did not parse shows the line and column the loader stopped at.  Each finding leads
  to a panel that lists it, and the row counts it: a finding at a producing declaration's init opens
  the values grid, which lists what is filed at the init of every declaration producing the object,
  a reader's finding falls through to the variable's panel, a constant, a section or a raster
  declared twice and a type declared twice are listed and counted at both places, and a missing
  include leads where the description holding it does.  The lines above the Findings, Table and
  Compare tables count each finding once, as `ddd check` and `ddd compare` print it, where a
  disagreement, filed on each file it concerns, was counted at each and a baseline's disagreement
  was too: a finding a run files twice is counted twice, as `ddd check` prints it, and builds alike
  count as one.  Migrating costs a client typed from the page's contract the fields it gains:
  `State` and `GET /api/compare`'s reply say `statements`, the findings counted once, beside the
  `counts` that stay the rows, and a finding says `line` and `column`, `null` where the loader gave
  none, which are required; one that reads the json ignores them.

* **A read says why a declared name has no grid, and reads a type saved since the analysis.**  `GET
  /api/values` told a variable of a structure type, a dropped object and a curve over a dropped axis
  that the project declares no such name, though `GET /api/variable` answers every one of them.  It
  now refuses them `409` as `invalid` and says why: a structured variable's values are its members',
  and a dropped object is told by the finding that dropped it, or by the one of the axis it follows;
  a name nothing declares keeps its `404`.  `GET /api/type` answered a type saved since the
  analysis, and still json, with a server error where a member lacked its `name` or its `bits` was
  no integer: it is read as it is saved, the keys that read listed and the others empty, until the
  next analysis files what is wrong with it.  A file an `includes` entry names by a plain path that
  no file answers is the file that did not load, and the description holding the entry, which
  parsed, loads, so that every refusal naming the files that did not load sends the reader to the
  missing file; the finding stays filed at the entry, and an entry that is a pattern keeps its error
  on the description.  Migrating costs a client that matched the `404` of `GET /api/values` for a
  declared name the `409`.

* **The state says why the last analysis failed, and which build record cannot be used.**  An
  analysis that raises, a plugin failing while the project is read, published nothing, and the
  reason went to the terminal alone: before the first revision the page read a project that was
  analysing for as long as every analysis failed, and later the last revision as current.  The state
  now says why, as `failed`, in the words the terminal prints or the exception's class where it has
  none, until an analysis succeeds; the revision before it stands meanwhile, and opening another
  project lets it go.  A build record this DDD cannot use, written by a newer DDD or naming a check
  this one has not got, is refused and its project analysed without its severities, which the start
  page listed but a project opened on the command line did not: the state says it, as `refused`,
  beside the open project's revision, and the terminal is told once, and again whenever its reason
  changes, as the language server logs one.  An undo of an edit no longer on top is refused `stale`
  without asking for an analysis, since no file is in doubt, where it moved every page's version for
  nothing; a write refused `stale` whose analysis fails and cannot be printed stays that refusal,
  where the print's error was answered.  Migrating costs a client typed from the page's contract the
  two fields `State` gains, `failed` and `refused`, which are required; one that reads the json
  ignores them.

* **The page keeps asking its server, names the project the server has open, and leaves the masthead
  in reach when a page cannot be drawn.**  A browser that believed the network lost held back the
  page's reads and writes, though `ddd gui` answers on this computer: an Apply sent nothing, and the
  long poll waited for a network that was not in its way.  The page now sends them whatever the
  browser says of the network.  The server has one project open at a time, and every page now names
  the one the state it follows is of, by its description's file until the server has said its name,
  asks for its session again where the session names another project, and files the arrangement of
  its canvas under the project it shows, where a page whose project another page had replaced went
  on naming the first.  A page that failed while it was drawn left the browser's own blank page, the
  masthead with it: one boundary now sits under the masthead and the banners, which stay, and says
  "This page could not be drawn" and why, with "Reload the page" while `ddd gui` answers, and a
  finding leading to a name no address can carry is drawn without a link, in the words that say
  where it is.  Nothing to migrate.

* **The Declare button stays above the Shared files table, and the declare form says what it still
  needs.**  The Shared files tab drew its Declare button only while it listed nothing, so a project
  that listed an entry could declare no other from the tab.  The button is now drawn above the table
  whenever the tab lists any.  The declare form says under its sentence what it still needs, `Still
  needs datatype or typename.` or the keys the kind requires that nothing states, and which text
  typed into a field is not taken yet, where a required key's field read "state nothing" as an
  optional key's does and is now empty; and the sentence for a name the project already lists says
  by the scope chosen what the declaration does, `Produces` it, `Reads` it or `Keeps` it to itself,
  naming the component that declares it.  Nothing to migrate.

* **A large project's lists are narrowed, windowed and searched, and each says how many rows it
  leaves.**  The declare form's Name list narrows by what is typed, draws at most fifty names and
  says how many more hold the text; Compare's table draws only the rows in view, as every other long
  table does, and none where a comparison files nothing; the Graph's search says under its box how
  many modules it found of how many, or that none matches; and a plan that changes more than four
  files names three of them and counts the rest, saying `Planning…` while it is asked for, where a
  rename through a large project named every file.  The component table, a component's own
  declarations, a unit's own places and the Findings tab each take a filter, which leaves the rows
  holding the text typed, whatever its case, and says how many it leaves of how many.  The Findings
  tab's is asked of the server, `GET /api/findings` taking `text`, and matches a finding's check,
  its words or its file's name as the File column draws it.  The masthead goes to a variable by a
  part of its name, listing at most fifty of the names holding it and saying how many more do, from
  `GET /api/names`, and opens its panel on the page of the component producing it, or of the first
  declaring it where none does.  Both routes, like the rest of the api, are a preview's and change
  with the package.  Nothing to migrate.

* **What did not load is said once, under the masthead of every page, with what to do next.**  One
  banner under the masthead of every page of the open project, a component's among them, now says
  why the last analysis failed and, while `ddd gui` runs, that it tries again about every second
  until one succeeds; which files did not load, past four three of them and a count of the rest,
  each leading to the Findings tab filtered to the finding that says why and the count to the Files
  tab; and each build record this DDD cannot use, with its reason.  A panel says that no file that
  loaded declares a name where a file did not load, and not that no file does, and a removal and the
  masthead's go-to say it too; the Graph says that no module is drawn where the project's own
  description did not load; a project that includes no component says, in the Graph and the Table,
  that New file writes one; and the start page lists a project description it could not read,
  because it cannot be opened, is not UTF-8 text or does not parse, with why, from the `unreadable`
  of `GET /api/projects`.  Migrating costs a client typed from the page's contract the field that
  reply gains, which is required; one that reads the json ignores it.

* **The page can be used by keyboard and screen reader, in forced colours, in a narrow window and
  with reduced motion.**  Every button draws a focus outline of two pixels in the accent colour, in
  forced colours too, a chooser rings its field, its arrow and the choice its keys are on, and a
  selected row has an outline of its own; an arrow whose ends agree is drawn in the quiet ink, where
  it was too faint to read; and a finding's severity is toned one way wherever it is drawn and said
  in a word, `error`, `warning` or `info`, as `ddd check` says it, so that colour is never its only
  sign.  The Graph moves its view in no time where the browser asks for reduced motion.  After a
  change of page the focus goes to the page's heading, until the reader's own key, pointer, wheel or
  touch takes it elsewhere; Close gives it back to the control the panel was opened from, Apply
  leaves it in the panel and Put back on the page; every page is titled by its name and the
  project's; and the heading's line says what an edit or an undo wrote, and where, which a screen
  reader hears, a second write that says what the first said as well.  A grid's field keeps the
  focus a screen reader gives it.  A narrow window fits the page: a panel opened out of view is
  scrolled into it, and a panel's table scrolls sideways in a box of its own.  Nothing to migrate.

* **Compare names the baseline it was asked for, keeps it from tab to tab, and refuses one in plain
  sentences.**  The Compare tab keeps its Baseline field and the comparison last asked for above the
  tabs, so that leaving the tab and coming back finds them, its verdict names the baseline it was
  asked for, and the field gets the focus back once what its Enter asked has answered.  A path
  copied with the quotes a system puts round it, double or single, is read as the path.  A baseline
  the page refuses is refused as `is unreadable`, and no more, where the system's own words, which
  differ from one system to another, were added, and as outside the directory `ddd gui` was started
  in, naming it, where the sentence said the session root.  Under the verdict the page says how many
  errors the project has of its own, and that the Findings tab lists them.  Migrating costs a script
  that matched the refusal's old sentences the new.

* **The page keeps the reader's place and what they typed, and tells two files of one name apart.**
  The Findings tab keeps its place above the tabs, the filter's text, the scroll and the finding
  open, so that Back, or pressing the tab again, returns to where it was left, and a component's
  page leads back to the tab it came from.  A type's description and rename, typed into their
  fields, are kept when a key row is selected, and previewed again when the row is let go.  A row of
  the Files tab leads to its component, to its findings, or to why its file did not load; the words
  in a table's cells can be selected without opening what their row leads to; a pressed key row
  gives its chooser the focus, its list closed, by mouse as by Enter; and a finding's own place is
  drawn under its message, above its related lines.  Two files of one name in different folders are
  told apart by as much of their paths as tells them apart wherever the page names a file, in the
  Findings tab's File column, in a plan's consequence and the lines a change prints, and in the
  banner's links and the Files tab's, each leading to its own findings, and the filter matches the
  name as the column draws it.  A long name wraps in a panel, in the masthead and in the heading, so
  that Close stays in view and the page is never wider than the window.  Nothing to migrate.

* **The Graph and the values grid take the window, and what the Graph cannot draw says why.**  The
  Graph and a component's values grid take the width of the window, where every page keeps 1,100
  pixels, and a narrow window is as it was.  An arrow's tooltip is drawn outside the canvas's zoomed
  layer, so that it keeps its size at every zoom, and is hidden while its arrow is out of the
  canvas; a plot's margin grows to hold its longest reading, so that none loses a digit; and a
  layout worker that cannot start says to reload the page only while `ddd gui` answers, and says
  nothing of it once it has stopped.  Nothing to migrate.

* **The page asks again where the server could not answer, and refuses before sending what the
  server would not read.**  The long poll and the session, answered with a failure of the server's,
  a `5xx` or a body cut half way, or not at all, are asked again after a short delay, the first
  failure said nowhere and, from the second in a row, the server's own words or that `ddd gui` has
  stopped; a refusal a repetition cannot mend, a `4xx`, still ends the ask.  A page waiting for its
  first analysis promises none once `ddd gui` has stopped, and the page the server serves a browser
  that is not signed in says, where the address was opened already, to stop `ddd gui` with Ctrl+C,
  start it again and open the address it prints then.  A request is held to the limit of its own
  route before it is sent, as the server holds it: an edit's body to 8 MiB and any other to 1 MiB,
  the refusal naming the edit by its label, or the route, and the limit.  Migrating costs an edit
  past 8 MiB its parts, made one at a time, or an editor; and a script that matched the text of the
  page served to a browser that is not signed in matches the new.

* **Opening the project already open goes to it, and keeps its undo.**  The start page offered the
  open project as it offered any other, and pressing it opened it again, which put the undo stack
  away.  Its button now says `Already open`, is marked as the current one, and goes to the project's
  Graph as the masthead's project button does, asking nothing of the server; a page that followed
  another page's opening marks that project, from the state, before the session says so.  Every
  other project opens as before.  Nothing to migrate.

* **A panel offers what a refusal leaves it, says why it draws nothing, and holds no answer a
  refused read has left.**  One rule says what a panel offers beside a refusal: under a refusal held
  of its Apply, the plan its revision answers, with its Apply, and beside its plan's own refusal, no
  plan and no Apply; the sentences of a refused Apply and of a refused undo are chosen in one place
  for every screen.  The variable panel's Remove alone stays withdrawn under any refusal.  A finding
  whose place in its file alone moved keeps its panel, found again by its file, its severity, its
  check and its words where its key moved; a panel whose read of the units failed says why it draws
  nothing; an answer a screen kept is dropped once a read of it is refused, rather than drawn as
  current; a settle's refusal keeps open the key it was of where the panel had opened it by itself;
  the start page's list comes back once the project it opened is open; and a Files tab press made
  while a revision lands applies the plan on screen.  Nothing to migrate.

* **An optional key emptied in its field is taken away, so that a raster is made acyclic from its
  panel.**  A raster's cycle and description, a section's description and a constant's description,
  emptied in their fields, are sent as no key, and the key leaves the file, where the field's empty
  text was sent as the key's value: a field of spaces alone is as empty as none, and the required
  keys, access, alignment and event, are as they were.  A raster is made acyclic from its panel by
  emptying its cycle.  Migrating costs a project that wants a key present with no text its file,
  since the page now writes none.

* **An edit whose file changed on disk leaves the undo stack, and a refused undo is offered again.**
  An undo refused because a file it would put back changed on disk stayed on top of the stack for as
  long as the server ran, so that every edit under it was out of reach.  An edit whose file is gone,
  or holds other bytes than the edit left, now leaves the stack once the strip has said so, naming
  the edit and that it can no longer be undone with nothing put back, and the edit beneath it comes
  within reach; the strip says every edit taken off while it is open, and reads `Nothing left to
  undo` where none is left, until it is closed.  An edit whose file only cannot be read or written,
  a permission, a handle another program holds or a full disk, stays, its refusal said beside it and
  its Put back offered again in the strip without closing it, with `Read the files again` where the
  preview was refused.  The strip counts a file an undo removes apart from the files it puts back,
  as the heading's line does: `Puts back 1 file: demo.ddd.json, and removes 1 file: units.ddd.json`.
  `GET /api/undo` takes `at`, the number of the edit the state names, and refuses one that is no
  longer on top as `stale`, so that a window reads and takes off no edit of another's.  Migrating
  costs an edit whose file the reader put back by hand, byte for byte, after it changed, which the
  page has taken off and no longer puts back, and a client that previewed an undo gives `GET
  /api/undo` the `at` of the state's `undoable`, answered `400` without it.

* **Home, End, PageUp and PageDown walk the whole Findings listing.**  The Findings tab draws only
  the rows in view, and its keys walked only those.  Home and End now go to the first and the last
  finding of the listing and PageUp and PageDown by a page, the row focused once it is drawn.  The
  tab's type-to-find still matches the rows drawn alone; its filter, asked of the server, finds a
  name in the whole listing.  Nothing to migrate.

* **A pasted table says its header is not written, and one value pasted into a cell sets that
  cell.**  A table pasted into the values grid whose first row and column were taken for a header
  discarded them without a word, so one naming a different axis went unseen until the preview; the
  preview's sentence now says that the first row and column pasted are taken for a header and not
  written.  One value pasted into a focused cell, a single cell of text with a trailing line break
  aside, was read as a table, and refused unless it was the object's whole shape; it now sets that
  cell as if typed there, with the reading of white space, of a comma that could be either and of
  text that is no number that a typed cell has, and joins the cells typed before it in one plan, and
  an empty paste empties the field.  A scalar's one cell takes a value so too.  Anything more,
  pasted into a cell or elsewhere in the grid, is a table as before.  Nothing to migrate.

* **A file that cannot be written is refused before anything is, on every system, and what is
  written is synced.**  On Windows a read-only file was staged, refused at the rename after
  a second of tries, and left a read-only stage beside it for each refusal; on Linux the rename
  asks the folder and not the file, so a read-only file was written through, silently.  Every
  file an edit changes or an undo puts back is now asked whether this process may write it
  before any is staged, and one it may not - read-only, another user's, on a read-only mount,
  or to be written by root over a file nobody can write - is refused as `unwritable`, naming
  it and saying nothing was written; on Windows the read-only flag is the one thing asked first,
  so a file its permissions forbid this process passes, and is refused when its stage cannot
  replace it, once the tries are spent, with the files renamed before it put back.  A stage is
  created `0600` where it will take its file's mode, and a name already taken is tried sixteen
  times, no more.  Every stage is synced to the disk before any file is replaced, at once for all
  of them, so that an edit of hundreds of files and its undo still take a fraction of a second on
  the NVMe disk of a Linux desktop, where that was measured, and a power cut leaves a file as it
  was or as the edit made it, never empty, on a journaling file system that has a sync to offer.
  A refusal leaves every file as it was or names those it could not put back; a server killed
  while it writes can still leave part of an edit and the stages it was writing.  No file format
  changes.

* **A rename, a removal or a declaration that produces a name is refused while a file of the
  project does not load.**  A project is indexed from the files that loaded, so a file saved
  half way is in no index, and a rename, a removal or a key settled on every declaration of a
  variable was planned over the others and answered as done: once the file was repaired, the
  project failed `ddd check` for the old name it still held, or for a name it used that no
  longer was declared.  Each is now refused as `unreadable`, naming every file that did not
  load, before any file is read; so is a declaration that produces its name - an object
  declared, a variable read as an output or a local - while one of those files may produce or
  declare it already.  What only reads, writes only where it points, or takes the file that does
  not load out of the project is answered as before.  A refusal that a name was declared nowhere,
  said of a name only such a file declares, now says that the file did not load.  No file
  format changes.

* **A fix or a value that would leave a file unable to load is withheld, or said so.**  A quick
  fix of the editor, and the button of the page for a definition mismatch, wrote one key into
  every declaration of a variable without asking whether the result was a declaration the
  loader accepts - an enumeration on a float32, a string beside a unit, limits that are not
  finite, a shape past the caps.  The project then counted as not loaded and every further
  fix was refused until the file was mended by hand.  A fix is now offered in the editor only
  for the declarations it leaves loadable, and on the page only where it leaves every one of
  them loadable, and a value the variable's panel would write that leaves one unable to load is
  planned all the same, as the reader may mean it, with a sentence saying which declaration of
  which file would not load and why, which the panel draws above Apply - all but a value that
  would leave a declaration's storage named twice or a datatype without its conversion, or one
  its kind does not take or cannot go without, which the panel refuses as it did.  A value that
  is not json, an open buffer in the editor with a key typed twice, is answered with the loader's
  own sentence rather than ending the language server.  What needs more of the project - a
  constant a dimension names, a structure's leaves, a map's axes - is still a finding of the next
  analysis.  No file format changes.

* **A name another component keeps local is no longer offered to read.**  The add panel offered
  a component every name of the project, including a local of another component, and reading
  one wrote a declaration that is a `local-conflict` in a project that had reported nothing.  A
  name any component declares local is now left out of what a component may read, and reading
  it is refused, saying whose it is; the values grid and the editor still read it as the
  producer.  No file format changes.

* **`ddd gui`'s edits take time that grows with the file.**  A member added to a file written on
  one line looked through every entry of the file to find its indentation, each by searching
  back to the start of the text, so it took 1.7 s at 1.5 MB and 37 s at 6.1 MB; a file written
  with bare carriage returns was searched in full for a line break for every id.  A line is now
  looked for only as far as the nearest break, the layout of the lines around a place is read
  only when the edit needs it, and the walk for the indentation unit searches between two
  entries once.  No file format changes.

* **Six small edges of the edit engine are settled.**  A pointer's element is spelled with its
  brackets: `at` without them is refused, where `1` planned a key of its own.  A cell past the
  end of a short init is set, filled out with zeros, as the grid promises.  A conditional object
  is read with its producer's condition, so the two sides agree.  A bare carriage return ends a
  line, an edit where no line break follows takes the file's own ending rather than a line
  feed, and a file created takes the newline and the indentation the project uses.  The Files
  tab writes an include with `/` and relative to the project, as a project is checked out on
  more than one system, and a path typed through a link keeps the link's name where it resolves
  to the file that was checked, and is refused where it does not.  A description holding a key
  that spells no pointer, which ended an edit in a server error, is edited and laid out as any
  other.  No file format changes.

* **A toolbox, and its first tool: `ddd tool from-elf`.**  It reads a linked ELF image and its
  DWARF debug information and prints the DDD declarations of the C variables named or matched
  on the command line - kind, datatype, shape, enumerators, structure members, initial value
  and section, as the image states them - as a list of interface entries or, with `--component
  NAME`, a component file holding the types its structures need.  DDD itself checks every
  entry before it is printed, as `ddd check --standalone` checks a component; what an image
  does not state, a unit or a scaling, is left out and said once.  It reads images with
  pyelftools 0.32 or newer, which joins pydantic and jinja2 as a runtime dependency; every command
  but it and `ddd generate` given `--image` runs without importing it.  No file format changes.

* **`ddd gui` stays responsive on large projects.**  An edit shows at once and its findings
  follow once the project has been analysed again; a change replacing many plain values in one
  large file, as renaming a unit its declarations state does, or giving many of its objects a
  plain value they lack, is planned and written from one reading of that file rather than one per
  value, and a key added to a file written on one line costs a time that grows with the file,
  where it grew with its square; its Findings tab reads its findings a page
  at a time as the reader scrolls it, rather than every one at once; and its component table,
  Types, Units, Shared files and Files tabs, a component's own declarations, a unit's own
  places and a variable's keys draw only the rows in view.

* **The a2l's addresses out of the linked image: `ddd generate a2l --image`.**  Every address
  the a2l carries is read out of the linked ELF image's DWARF - an object by its name, a
  structure member by its access path, at the offset the compiler gave it - and the a2l takes
  the byte order the image states, which a contradicting `--byte-order` is refused for.  A
  build needs no extraction script and works out no member offset by hand.  What the image
  cannot place keeps address 0 and is reported as `address-missing`, each reason a note of
  the finding.  In cmake, `ddd_generate(... ADDRESSES_FROM_IMAGE)` writes the a2l in a step
  after the link, so that one build gives the complete a2l; `ADDRESS_MAP` and `--address-map`
  stay as they were, for an image without debug information.  The map's reader has moved,
  `load_address_map` and its `ADDRESS_PATTERN`, from `ddd.backends` to `ddd.addresses`, and
  takes no `carried` any more: the 32-bit range of the addresses the a2l carries is checked by
  `ddd.backends.weigh_addresses`, which a caller reading a map calls itself; and a map that is
  both malformed and out of range for a symbol the a2l carries is now refused for the
  malformed entry, still exit 2.  No file format changes.

* **The Files tab's Remove panel waits when a row arrives from elsewhere.**  Selecting a row
  still asks its removal plan at once, as does one reached by the page's own links; a row the
  page was loaded with instead - from a link, a bookmark, a typed address, a reload, or a new
  tab - no longer does.  Its panel instead says what removing it would change is planned once
  asked, behind a button, so an address someone else sent the reader to can no longer run the
  project's plugins without their own press.

* **A refusal to a `POST` drains its body instead of risking a reset.**  Windows resets a
  connection it closes while part of a request's body is still arriving, which can erase the
  answer already written there before it is read.  `ddd gui` now reads and discards the body
  of a `POST` it refuses unread.  Where the `POST` declares a length of at most 1,048,576
  bytes, and no `Transfer-Encoding`, the body is read whole before the answer, and the
  connection kept; otherwise it is read after the answer, until the client closes, two seconds
  pass, or 1,048,576 bytes are read, whichever is first, and the connection then closed.
  Measured in CI on Windows, on a longer body: a script sending past the answer read it whole
  on all three Python versions after this fix, where two of three had lost it before.

* **A sign-in that gets no answer at all is retried once.**  Opening the address `ddd gui`
  printed, or a launch's one-time address, could still land on the signed-out page: the first
  request behind the scenes sometimes failed before any answer came back at all - measured in
  CI, in Edge on Windows, where the browser was briefly refused a socket
  (`net::ERR_NO_BUFFER_SPACE`).  The page now sends that request once more, at once, rather
  than telling the reader to open the very address they had just opened.  An answer that did
  arrive, a refusal included, is never retried.  A launch code whose first answer was lost is
  already spent, though, so that one case still ends signed out, with the terminal's
  reused-code line printed as a false alarm.

* **A stylesheet or a request the network drops once is asked for again.**  The page could
  come up unstyled, or say that `ddd gui` was not answering, when the network failed one of
  its requests before any answer came back - measured in CI, in Edge on Windows, where the
  browser was briefly refused a socket for the page's stylesheet (`net::ERR_NO_BUFFER_SPACE`).
  The page now asks once more, before it is drawn, for any of its stylesheets the network
  failed, and sends a request that only reads once more, at once, when it got no answer at all:
  one lost request goes unnoticed.  A request that changes something - an edit, an undo, a
  project opened from the start page - is never sent again, since its change may already have
  been made, and neither is one that got any answer, a refusal included.  The project's canvas
  likewise starts its layout worker once more when the worker did not start, rather than
  saying at once that the layout worker stopped and drawing no modules.  A second failure
  reads as one did before: the page drawn unstyled, saying that `ddd gui` is not answering, or
  saying that the layout worker stopped.

* **A type's unit chosen as "no unit" is now taken off the type.**  On the Types tab, choosing
  "no unit" for a type's unit read as no choice at all: the field went back to the unit the
  type states, the preview offered a change that changed nothing, and Apply left the unit in
  the file.  The choice now stands: the field reads "no unit", the preview takes the `unit`
  line out, and Apply writes the type without it.  Stating a type's limits as nothing, and
  choosing no unit for a variable, already worked.

* **A shared entry's panel no longer turns into the form that declares it.**  On the Shared
  files tab, the panel of a constant, a section or a raster gave way to the form declaring one,
  pre-filled with its name, whenever the table stopped listing the entry: when its file was
  saved half-written, where the panel was meant to stay and name the file; when the entry went,
  if the table heard of it before the panel did, where the tab was meant to say it had gone;
  and for a moment on every rename from the panel.  The panel now stays until its own answer
  says why: it names the file that did not load and shows the entry again once the file loads,
  it closes with the tab saying the entry is no longer declared, or it moves straight onto the
  new name.

* **A screen whose next read fails keeps what it showed.**  The Files, Units, Types and Shared
  files tabs, the project's canvas, a component's page and a values grid showed the error
  alone when their read of the project's next revision failed - the server failing on it, or
  the network dropping it twice - and dropped what they had drawn, a component's page taking
  an open panel with it, and what the reader had chosen there but not applied.  They now keep
  what they showed, with the error above it, and an open panel keeps what the reader chose in
  it.  A refusal, such as a grid whose object was renamed away, is still shown alone, and so
  is an error before anything was drawn.

* **The page's own script the network drops once is asked for again.**  The page stayed blank
  when the network failed the one request that loads its own code - measured in CI, in
  Chromium on Windows, where the browser was briefly refused a socket
  (`net::ERR_NO_BUFFER_SPACE`).  The page now asks for it once more and is drawn as if nothing
  had happened; dropped twice, it says to reload it.  What asks is a short script the page
  holds inline, which the content security policy allows by its SHA-256 alone.  It asks again
  for no script of another origin, and never writes over a page already drawn.

* **The start page's list stays held until the project it opened has replaced it.**  Once the
  server had opened the project chosen, the page asked it which project was open, and until
  that answer came it drew the list again with every project's button enabled: a second press
  in that moment opened another project in place of the first.  The buttons now stay disabled
  from the press until the start page goes; a project the server refuses to open gives them
  back.

* **The start page no longer says "built as" with nothing after it.**  A build record written
  without an image, as `ddd build-info` writes one when `--image` is left out, listed an image
  called nothing: the project's button on the start page read "built as" and stopped there.
  Two build trees configured for one image listed it twice, as "built as firmware, firmware".
  A record that names no image now offers its project and lists none, and each image a
  project's records name is listed once, in the order of the records.

* **The component table's buttons are disabled when `ddd gui` has stopped.**  On a component's
  page, the buttons in the table's Shape and Unit cells, which open a variable's values and its
  panel, stayed enabled after the page said that `ddd gui` had stopped, while the page's other
  buttons that write were disabled.  They are now disabled with the rest, and enabled again
  once `ddd gui` answers.

* **A fix the server failed on can be chosen again.**  On the Findings tab, after the server
  failed on applying a finding's fix - an error of its own, not a file changed on disk - the
  panel went on saying so and drew no Apply, whichever fix was chosen next, until the finding
  was pressed again.  Choosing a fix now takes that refusal away and offers its Apply, and it
  takes a refusal because a file changed on disk away too.

* **A baseline's finding names its file as the baseline's in its panel too.**  On the Compare
  tab, the table names the file of a finding the baseline itself reports as "the baseline's
  sensor_hub.ddd.json", so that it is not taken for the open project's own file of that name.
  The panel opened from that row named the file plainly, in its heading line and in its notes.
  It now names it as the baseline's, as the table does.

* **Compare asks again when it is asked again.**  On the Compare tab, pressing Compare, or
  Enter, for the baseline just asked for sent nothing: the answer already on the page stayed -
  a refusal for a file that did not exist yet, or "can replace" for a baseline written over
  since - until the path or the project changed.  Every press now asks the server, which reads
  the baseline file as it stands.

* **`ddd gui` reads a field's note with the field.**  The note under a field that offers
  choices - "Not one of this project's units", under a unit typed that the project's units file
  does not list - is now the field's description however late it appears.  It was tied to the
  field only if it was already there as the field first drew, so a note that came as the
  reader typed was on screen and not read with the field by a screen reader.  Nothing changes
  on screen.

* **`ddd gui` prints its address on stdout, whatever a plugin is doing.**  For a project
  naming a plugin, the address could go to stderr instead: the first analysis runs a
  plugin's hooks on a thread of its own as the address is printed, and a hook runs with
  stdout bound to stderr for the whole process.  A program reading the address from
  `ddd gui`'s stdout then waited for it in vain; in a terminal both look alike.  The address
  now goes to the stdout `ddd gui` was started with.

* **`ddd gui`'s token is no longer a cookie.**  A browser sends a cookie to every port of
  `127.0.0.1`, so any other server there that the reader's browser visited was sent the token.
  The page now keeps the token in the browser's storage for its own address, port included, and
  sends it as a header; a page elsewhere cannot send that header at all, in any browser.  The
  pages themselves need no credential, and a cookie is no credential any more.  A browser too
  old to send `Sec-Fetch-Site` lets any site open the page itself at an address it chooses;
  the security page says what that allows.

* **`ddd gui` refuses a request that says it came from somewhere else.**  In a browser that
  sends `Sec-Fetch-Site` (Chrome 76, Firefox 90, Safari 16.4 and later), every request says
  through it, and through `Origin`, where it came from, checked before the token.  A page
  served from another port of `127.0.0.1` is refused rather than answered.

* **Every route of `ddd gui` reads its query through one typed model.**  A hostile value - a
  path with a NUL character or a lone surrogate, a number thousands of digits long, json nested
  more than 64 levels deep or holding a number too large to be finite (an edit's own value among
  it), a network path outside what `ddd gui` serves, on Windows a path holding a name Windows
  keeps for a device, a file to create under a name longer than 234 bytes, holding a character
  Windows keeps out of a file's name, ending in a dot or a space, or one Windows keeps for a
  device - is refused with a plain `400`, `404` or `409`, the long poll's `?after=` excepted,
  which answers at once whatever else it is given.  No malformed input - in a query, a body or a
  page's path - is answered with a `500` any more, and an answer carrying json nested more than
  99 levels deep - a file's contents, or a part of the project's dictionary - is refused `409`
  rather than sent: naming the file, for a file that deep or one stating an extension block too
  deep, and no file otherwise.

* **An include through a loop of links is a finding on python 3.12 too.**  `ddd check` ended
  there in a traceback, where 3.13 and later report the file it cannot read, at the entry
  naming it; and `ddd gui` answered a request naming a path through such a loop with a `500`,
  where it now answers it as one naming no file it can read.

* **`ddd gui` answers at most sixty-four connections at once.**  The sixty-fifth is refused
  immediately, `503`, rather than given a thread of its own: a local process that floods the
  port can no longer exhaust the machine's threads.

* **The browser `ddd gui` opens for the reader is no longer launched on the long-lived
  token.**  It is launched on a one-time code instead, good for sixty seconds or one use, so
  the token no longer sits on a command line any local user could read.

* **`SECURITY.md`.**  How to report a vulnerability in `ddd gui`, privately, through this
  repository's Security tab.

* **A security page, `docs/gui_security.rst`.**  What `ddd gui` defends against, what it
  trusts instead, and what it leaves open - including when run in a container - with a table
  of every route.

* **A Files tab: the project's own includes, and the three things that change them.**  `ddd gui`
  lists the root project's `includes` one row per entry, in the description's own order, a
  pattern's row followed by every file it matched, with each file's kind, the findings filed on it
  and its state: blank for a file that loaded, `did not load`, `names no file` for an entry that
  names nothing, and `not read by the last analysis` for a file the page has not yet had an
  analysis of.  A finding of a whole file leads there.  New file creates a component, types, units,
  constants, sections or rasters file beside the project description, in its newline and
  indentation, and adds it to the includes in the same edit; a first units file lists every unit
  the project states, so that one click cannot fail a passing project with `unknown-unit`, and is
  created empty where a file of the tree has opted the project in already.  Add a file appends a
  path, written from the description's directory, to the includes, and previews the errors it
  brings rather than refusing for them; it refuses, in the server's own words, a path outside what
  `ddd gui` serves, one naming no file, the project's own description, a python file, a file the
  project has already, and on Windows a file on another drive.  Remove takes every entry of the
  selected row's key out of the includes, the files staying on disk, and is refused where the
  analysis counts an error more at some place than the project has there now.  Each is previewed,
  written to every file or none, and undone like every other change.  The tab is not part of the
  public interface, and the includes it writes are the ones a person would write by hand.  No file
  format changes; nothing to migrate.

* **A types, units, constants, sections or rasters file may declare nothing, and `empty-vocabulary`
  says so.**  The list of each of the five files had to hold an entry, so a file emptied of its last
  constant, section, raster, unit or type stopped loading and was refused as `schema`, and `ddd
  gui`, which cannot delete a file, could never take a project from one entry to none.  An empty
  list now loads, and the new check `empty-vocabulary`, an info, is filed once for it, at the list,
  naming the file and its kind; it can be graded as any check can.  A structure's members, an
  enumeration's enumerators, a shape's dimensions and a component's own inline types and constants
  still need an entry, the spelling of none being to leave the key out.  The five published schemas
  no longer require an item.  An empty units file still opts the project into its vocabulary, which
  the file decides rather than what it lists: every unit a declaration, member or scalar type then
  states is `unknown-unit`, where a project with no units file keeps its units free.  Migrating
  costs nothing: a file that loaded before loads as it did.  A tool that validates against the
  schemas of an earlier version refuses an empty list as the loader did, and a build that counts the
  findings it prints sees one info per such file, which `-W empty-vocabulary=ignore` silences.

* **A Shared files tab: the constants, the sections and the rasters a project declares.**  `ddd
  gui` lists every constant, from a constants file or a component's own list, every memory section
  and every measurement raster, a row saying which vocabulary an entry belongs to, what it
  states - a constant its value, a section its access and alignment, a raster its event and
  cycle - and what names it.  What an entry states is changed there, and renaming one rewrites
  every place that names it in one edit: for a constant every shape spelling it; for a section
  every definition placing data in it; for a raster every definition measured in it and a
  component's own default naming it.  A section's name is judged as the linker string it is and a
  raster's as the short name of an XCP event, so a leading dot is an ordinary spelling for the
  first and eight printable characters the most the second holds; a name the project already
  declares as a section or a raster is refused, since merging two would move data into memory with
  other properties or sample one signal on another's channel, and so is an event another raster
  claims.  A new constant, section or raster is declared there too, writing `constants.ddd.json`,
  `sections.ddd.json` or `rasters.ddd.json` beside the project description and adding it to
  `includes` where the project has no file of its kind, and a removal is refused while anything
  still names the entry, counting what does.  The last entry of a file removed leaves a file that
  declares nothing, which is `empty-vocabulary` above.  A finding naming a constant, a section or
  a raster leads to the tab.  Every change is previewed, written to every file or none, and undone
  like every other.  The tab is not part of the public interface, and what it writes is what a
  person would write by hand.  No file format changes; nothing to migrate.

* **A table copied from a spreadsheet is pasted into the values grid.**  Anywhere in the grid, a
  table copied from a spreadsheet replaces every value of the object in one change, previewed and
  undone the same way as every other change.  The pasted block must be the object's own shape - a
  one-dimensional object is one row, as the grid already draws it - or exactly one row and one
  column larger, with the header a reader selects along with the grid's own cells; a comma is read
  as the decimal separator where the block states no point, and one that mixes `.` and `,` is
  refused rather than guessed at - as is a comma that could be a thousands separator, `1,200` being
  twelve hundred to one spreadsheet and one and a fifth to another, which names the cell and says
  so.  The header itself is discarded without being read, so a block whose header names a different
  axis is not caught here; the preview, which shows the lines each file will change, is what catches
  it before anything is written.  Nothing to migrate.

* **The values grid is drawn as a picture under it.**  Under the grid, the object's values are drawn
  as a picture: a marker at each point and a line joining them where a row holds more than one, laid
  against an axis's own breakpoints - unevenly spaced, exactly as those breakpoints are - or over
  plain indices where there is none, with the declared limits ruled across it wherever they fall
  inside the range it draws and left off it where they do not, the one place a value stored outside
  them can be seen.  It follows the same toggle between physical values and raw counts, offers no
  control of its own, changes nothing, and is drawn under a read-only grid exactly as under a
  writable one, left undrawn only where there is no grid to begin with.  The toggle always rescales
  to its own range: for a positive conversion the same numbers in a different unit draw the very
  same picture, only the readings along its edges changing; a negative one - legal here - mirrors
  the curve instead of leaving it alone.  Nothing to migrate.

* **A Compare tab says whether the open project can stand in for a delivery.**  It answers the
  question `ddd check` was never asked: can the open project stand in for a delivery the reader
  names.  The baseline is a dumped dictionary, or a project or component description, at a path
  under the directory `ddd gui` was started in - refused, and told why, when it is outside that
  directory, unreadable, not valid json, a description or a dictionary this DDD could not read, or
  json that is neither.  Its verdict counts only the comparison and the baseline's own errors, never
  the open project's own consistency errors - the Findings tab's own question - so a project the
  Findings tab still shows full of errors can be told here that it can replace its baseline.  A
  finding that names a place in this project leads there, as on the Findings tab: a plugin's
  comparison rule files at the declaration it is about.  The comparison's own findings name the
  whole delivery rather than a place in one file, and the baseline's own errors marked `in the
  baseline:` name a place in the baseline's files rather than in this project's; for those the panel
  says so rather than offering to go anywhere.  The renames the comparison finds - objects the two
  sides agree are one and the same, called differently now - are drawn here as a table, exactly what
  `ddd compare --renames` would write to a file, and the tab does not write it.  Nothing to migrate:
  it reads the files it is given and writes none.

* **A `definition-mismatch` finding now carries a button for each key its declarations
  disagree about.**  Opened from a consumer, it takes the producing component's value;
  opened from the producer's own row - the same disagreement, filed there too - it sends
  that value outward, and the reader never chooses a direction.  Either way the value may
  be silence: a producer stating no `unit` where its readers state one is settled by taking
  it out of all of them, from either row.  Previewed first, it
  settles every declaration of the variable at once, not only the one the finding names;
  the apply button reads "Apply to 2 files" where two have to move.  Nothing is offered
  where the variable has no single producer - several components writing it, or none,
  leaves no owner to take a direction from; the variable's own panel, one click from the
  finding, still settles any value the reader chooses, unless it would leave the file
  unable to load.  A key is offered only where one change settles it for every
  declaration: never `kind`, the one key no edit may carry between declarations, and not a
  key some declaration could neither take nor drop - one its named type fixes, one its
  kind does not allow, or the `datatype`, `conversion` or `typename` its own storage is
  made of.  Nothing to migrate.

* **The editor no longer offers to unname a declaration's storage, or to name it twice.**  A
  definition states either a `datatype` with the `conversion` that goes with it or the `typename` of
  a type fixing both, and the loader refuses a file that states neither or both.  "Remove the
  datatype from N other declarations", the same for a `conversion`, and "Apply this typename" into a
  declaration already stating a `datatype` each wrote one of those files; none of them is offered
  any more, and an action reaching several declarations leaves out whichever of them could not take
  it.  The same holds for a `datatype`: a declaration naming a type takes it from the type as it
  takes its `unit`, `conversion` and `limits`, so the fix that offered the producer's `datatype` to
  it, and "Apply this datatype" from another declaration, are not offered either, and the action
  leaves it out of the declarations it counts and changes.  Nothing to migrate.

## 0.11.0

* **A browser interface, as a preview.**  `ddd gui` serves a browser interface over one
  project's description files on the developer's own computer and opens the browser on it:
  the project opens on a canvas of its modules, an arrow per producing-consuming pair
  coloured by the worst disagreement between its ends, and the component table one tab
  away.  A declaration's unit is no longer changed in the table; selecting a declaration
  opens a panel for its variable - every declaration of it, who produces and who reads it,
  and the unit each states - where one unit is chosen for the variable and applied to every
  declaration at once, with the lines each file will change shown on request, under Show
  changes; a red or orange arrow on the canvas opens the same panel.  A unit a declared type
  fixes is shown with its type and left to the type.  It is the first step of a GUI for
  developers who would rather not edit JSON, and its options are not yet part of the public
  interface.  Installing it needs no Node.js: a release carries the compiled pages, and so do
  the wheel ci builds for every branch it runs on and the development build it publishes to
  TestPyPI of the last commit of every push to `master` and to this repository's pull
  requests, once its checks pass - `0.10.1.dev57` for run 57, the commit it was built from
  named in its metadata.  `--host` can also serve it from a container: published on the
  host's loopback alone, with the token in the address as the only guard beyond it.

  A third tab, Units, is a table of every unit the project states or its vocabulary lists -
  its description, how many variables, types and structure members state it, and its
  findings; selecting one opens its panel beside the table, every place it is stated
  included.  A unit is renamed everywhere at once - every declaration, structure member and
  scalar type stating it, and its vocabulary entry - and renaming onto a unit that exists
  merges the two spellings.  A vocabulary's description is edited from a unit's panel, a unit
  outside the vocabulary is added to it, and a unit nothing states any more is removed from
  it; a project with no units file adopts one, writing every unit already in use into it, so
  that adopting reports nothing it did not report before.  Every change is previewed - which
  files, and the exact lines on request - and written to every file or none, as every change
  here is.

  A variable's panel now carries every key its declarations share rather than the unit alone:
  a row per key - what the variable is made of, what it means, what shape it has and which
  declarations it points at - a column per declaration, and the rows they disagree about
  first.  Selecting a row offers the values already in play, each naming the components
  stating it and marking the producer's, and the field the key takes: one of the eleven
  datatypes, a type, an axis, a measurement or a declared constant the project has, true or
  false, a minimum and a maximum, or the unit picker with the project's vocabulary behind
  it.  A conversion and a list of dimensions are carried from the declaration that states
  them rather than composed here, and `kind` is shown and never settled, since it decides
  which other keys a declaration may carry at all.  What is chosen is applied to every
  declaration at once, with the lines each file will change shown on request, exactly as a
  unit already was.

  A fourth tab, Findings, is a table of every finding of the project, worst first, each leading
  to what it names - the variable's panel, the unit's, the type's, or the component's page - or
  saying plainly when there is nowhere to go, as for a file that did not load.  A producing
  declaration without an identity is given one from there, previewed like every other change.

  Every change the interface writes can be undone while the server runs, one change at a time,
  from a button beside the project's name saying what it would put back - "Undo the unit of
  ValueA", "Undo the vocabulary adopted".  Pressing it shows which files would be put back and,
  on request, the exact lines; pressing again writes them, a file the change created taken away
  with the rest.  The interface holds what each change replaced rather than a way to invert it,
  so a file comes back exactly as its author wrote it; a file changed on disk since is refused
  and named, and its change stays on the list to be undone once the file is put back.  The list
  lives in the running server, is capped at fifty changes and ends when `ddd gui` does, which is
  the one thing it leaves behind: nothing is written into the project for it.

  A fifth tab, Types, is every type the project declares - scalars, structures and the
  external ones a vendor's header defines - with what each fixes, what it is used by, and
  the findings filed on it.  What a scalar type fixes is changed from there, previewed like
  every other change and undone the same way; a type is renamed everywhere it is named, its
  own entry and every declaration and member spelling it, in one all-or-nothing edit, and a
  name that c or the project has already spent is refused before anything is written, in the
  same words the editor refuses it with.  A finding filed on a type's entry now leads to the
  type it is about, and a declaration whose datatype, unit, conversion or limits a type
  fixes says which type, and takes the reader there.

  A component's page can now add a declaration to its interface.  Choosing a variable
  another component already declares adds it with the producer's definition where there is
  one, and the project's existing declaration where there is not, less its `id` and its
  `init`, so the new reader agrees with it by construction.  Choosing a name nothing
  declares instead adds a new object of one of the six kinds, asking for what a loadable
  declaration needs - the kind's required keys, and exactly one of `datatype` or
  `typename`, with the identity `conversion` written in once a `datatype` is chosen; a
  scope of `output` stamps it with a fresh `id`.  A unit, limits or a richer conversion
  are left for the variable's own panel afterwards, where a reader already knows to find
  them.  Removing a declaration is offered from that panel too, first naming what else
  declares it, or that nothing does any longer.  All three are previewed before anything
  is written, and undone the same way as every other change.

  A component's table now gains a Shape column between Type and Unit, a button wherever
  there is a grid to open and plain text or nothing where there is not.  A curve, a map,
  an axis and any declaration shaped in one or two dimensions show their values there as
  a grid, laid against their axes' breakpoints, each edge named with its axis and, where
  the readings are physical, that axis's unit; an object with no axis is laid over plain
  indices instead.  A curve, a map and an axis are offered whatever type they name,
  their shape following from their axes; anything else has to state both its own
  dimensions and its own datatype, so a dimensioned declaration naming a structured
  type is shown and not offered, and so is a shape of more dimensions than two: a
  structure holds no values of its own, and a grid draws rows of cells and nothing
  deeper.  The readings switch between physical values and raw counts with a toggle.
  One cell is changed at a time: type a value, see what it would set and which file
  that lands in, apply it, and put it back with the undo control already there -
  except an object that has no one
  producing declaration, because nothing produces it or because more than one thing
  does, whose grid opens read-only rather than being refused.  A physical value no raw count
  represents is stored as the count nearest it and then shown as what was
  stored - typing `12.004` into a `uint16` at ×0.01 stores `1200`, and the grid then
  reads `12`.  A value outside the object's declared limits - shown beside its kind and
  datatype - is stored rather than refused: `limits-out-of-range` weighs the limits
  against the storage and nothing in the analysis weighs an init against them, so
  refusing here would make the grid stricter than `ddd check` and leave cells a person
  wrote by hand that the interface could not edit.  A value the datatype itself
  cannot hold is refused in the tool's own words instead, and so is what is not wholly a
  number, and nothing is written.  An
  object initialised with text shows a sentence saying so rather than a grid; one stated
  once draws that value in every cell with a note, and one stating nothing draws greyed
  zeros with a note.  A finding filed on an object's `init` now leads to this grid, the
  way every other finding already leads to what it names.

* **The editor's reconcile quick fix is no longer offered for a value that already means what
  it would be set to.**  Taking the producing component's value, or spreading one declaration's
  value to the rest, now writes nothing to a declaration that already states it, however
  differently spelled: a conversion written over four lines and the same conversion written on
  one are one value, as the checks have always counted them.

* **The editor offers no unit to a declaration whose type fixes it.**  A declaration naming a
  declared type takes its `unit`, `conversion` and `limits` from the type, and the loader
  refuses one of them stated beside the `typename`.  A `definition-mismatch` on such a
  declaration was offered the producer's `unit` or `conversion` all the same, or the one
  every other declaration states, and "Apply this unit to N other declarations" from another
  declaration wrote into it too: each fix left a file that no longer loaded.  None of the
  three is offered to a declaration naming a type any longer, and "Apply this unit", or the
  same action for a `conversion` or `limits`, leaves it out of the declarations it counts and
  changes.

* **Renaming a unit from the editor, and quick fixes for an unknown one.**  `F2` on a unit -
  from any place it is stated, or from its entry in a units file - renames it everywhere at
  once, the vocabulary included, and merges the two spellings where the new one is listed
  there already, as the Units tab's rename does; it is refused, naming the file, while a file
  of the project does not load.  An `unknown-unit` finding offers "Add 'RPM' to the
  vocabulary", and, for each spelling close enough to suggest, "Rename 'RPM' to 'rpm'
  everywhere".

* **`unknown-unit` suggests a spelling that only differs in case.**  Its did-you-mean scored
  a candidate as written, so `RPM` for the declared `rpm` shared no character with it and
  suggested nothing - the likeliest near miss going unmentioned.  Spellings are now compared
  lowercased first, so `RPM` suggests `rpm`; the vocabulary itself still tells the two apart,
  and `mV` and `MV` remain two units.  The language server's rename-everywhere quick fix,
  which offers exactly what the finding suggests, gains the same spellings.

* **Tables that keep their point counts in front.**  A project states `"point_counts":
  "leading"` - once, in a project file, and a component may state otherwise for the curves,
  maps and axes it defines - when its firmware stores each table's number of axis points ahead
  of its data, in the table's own type.  The c declares such a table flat, counts first
  (`M[2 + (11) * (8)] = { 8, 11, ... }`), and the a2l describes it with `NO_AXIS_PTS_X` and
  `NO_AXIS_PTS_Y` ahead of `FNC_VALUES` or `AXIS_PTS_X` in a record layout of its own.  Two
  checks come with it: `point-counts-unrepresentable` refuses a table whose type cannot hold
  its counts, and `point-counts-mismatch` warns when a table and its axis disagree; `ddd
  compare` reports a changed convention as `changed-interface`.  The c templates are offered
  each object's `dimensions` and `point_counts`.  The dumped dictionary is format 9, adding
  `point_counts` to every object; a format 8 dictionary reads back unchanged.  The address map
  recipe of the build integration page now runs `nm --extern-only`, so two file-local statics
  sharing a name no longer make the map refuse to load.

## 0.10.0

This release is two things at once.  It finishes what 0.9.0 started - constants that hold any
number, string data, the dumped dictionary written as a file rather than redirected, a
component listed and dumped on its own - and it carries the answer to a review of the whole
tool, which read every page, ran every command and weighed every file DDD writes: the seven
entries that follow are what that review found, area by area.

An entry that costs a project anything ends with **Migration:** what, and read together
those come to five things.  A description is refused in a handful of spellings it used to be
accepted in, each of which broke something further along - the compiler, a calibration tool,
an a2l field - and each named where it is written.  Three edits a delivery comparison used to
pass now say "cannot replace", and each is a change of what a consumer compiles against.  A
`ddd generate` run owns the directory it writes into and takes back what it no longer writes.
The a2l, the dumped dictionary and - for a project whose wildcard includes match names
differing in case - the generated c come out once with a diff nobody wrote: shorter derived
limits, a byte order mark, another component order, and identical bytes ever after.  And a
script reading what DDD prints sees one new exit code, absolute paths where a comparison used
to print the path as typed, and a plugin's own output on stderr.  Nothing else that was valid
stops being valid.

* **The editor answers about the project, and about the document you have open.**  Fifteen
  defects of the language server, found by a review of the whole tool, most of them on the
  most ordinary setup there is - a checkout nobody has built yet.

  *What is checked.*  A project description opened in a tree with no build record was read as
  "a component on its own", so the nine checks that need every component of a project were
  silenced for the whole project - and because opening a file republishes everything it
  covers, opening
  `project.ddd.json` **withdrew** the missing producers and unused outputs from the components
  that were already showing them.  A project file is now checked as the project it is; the
  thinner policy stays for a component read alone.  The containing-project stage applies the
  default severities, which no page said and every page now does.  A component linked into two
  images is drawn once rather than once per image, unless the two disagree about how loudly to
  report it.

  *What ends the session.*  A build record naming a check this version has not got ended the
  server on the first document opened - the client restarts it five times and gives up - and
  is now skipped and announced like a record that cannot be read.  So are a code action whose
  `context` is null, an `initialize` naming a workspace folder without a `uri`, a document
  nested deeper than a position in it can be located (which also ended `ddd id --assign` in a
  traceback; it now reports the file and exits with the findings code), and a
  `Content-Length` spelled the way python reads a number rather than the way the protocol
  writes one - `1_2` was twelve, and the frame ended in the middle of the body.  A request
  arriving before `initialize` or after `shutdown` is refused with the code the protocol
  reserves for it, a second `initialize` with the invalid-request error, and `exit` without
  `shutdown` now ends the run with 1 rather than 0.

  *Where the answer lands.*  Everything published, answered and edited is now spelled the way
  the client spelled the document it opened, and resolved for every file it never opened.  A
  workspace opened through a junction, a `subst` or mapped drive, a symlink or with a
  different case had its findings published against a resource the editor was not showing, and
  its renames applied to a document that was not on screen; through such a spelling the open
  file was also found as its own containing project and reported three missing producers the
  project does produce.  A document under a scheme other than `file:` is refused instead of
  being read as a relative path - `untitled:Untitled-1` used to publish `file-not-found` for a
  phantom file in the workspace.  A note with no place of its own is published at the first
  line of the file its finding is on, where it used to carry an empty uri that a client reads
  as `file:///`.

  *What the editor offers.*  `F2` on an enum name or an enumerator opened a rename box whose
  rename returned an empty edit - and, where a variable of that name existed elsewhere, renamed
  *that* instead; the rename subjects are now matched where they are declared.  A rename and
  the quick fixes are refused, naming the file, while a file of the project did not load, for
  the reason a drifted buffer is already refused: a project is indexed from what loaded, so the
  edit would rewrite every other file and leave that one behind.  Hovering a declared type
  where it is declared, or a `typename` inside a types file, answered nothing at all and now
  describes the type.  A unit or a condition holding a backtick or a pipe - `defined(A) ||
  defined(B)` is an ordinary condition - broke the hover's table; both are now escaped.

  *What the server hears and looks at.*  The extension's file watcher has fed
  `workspace/didChangeWatchedFiles` since it was written and the server had no branch for it,
  so a file rewritten by a build or a branch switch changed nothing on screen until somebody
  saved; the server now checks again on it.  A junction inside a build tree turned one record
  into a record per level of the loop - twenty-two announcements and every finding published
  twenty-two times - and records are now counted resolved.  A record whose severities name a
  plugin's check that nothing registers is reported as `plugin-invalid` on the project file,
  which is what `ddd check` refuses the same `-W` for.  And the log no longer says that every
  file is checked on its own, which denied exactly the findings the next message published.

  *What it costs per save.*  A document no build record claims is checked through the project
  above it, and finding that project means loading every candidate and asking it - an answer
  that was then thrown away, so the project was read a second time to be checked, and twice
  more by the first hover or jump after the save.  The read is now handed on rather than
  dropped: one read of the project per refresh, and one per request that has to look above
  the document, where each of the two cost two.

  **Migration:** none for a description file, a build record or a command.  An editor
  extension other than the shipped one sees three protocol changes: `exit` without `shutdown`
  exits 1, requests outside the session are refused rather than served, and a non-`file:`
  document is refused.  The shipped VS Code extension sends `shutdown` first; its launch test
  no longer pins the lenient exit, and its handshake has a timeout.

* **The generated artefacts.**  Everything a review of the whole tool found between a
  description and the files written from it: four ways the c or the a2l was not what the
  description said, four inputs that passed every check and reached a compiler, and the
  example templates a project copies as its starting point.

  *A description may say `/*`.*  The generated c defused the marker that ends a comment and
  not the one that opens another inside it, so a description, a unit, a member, an enumerator
  or a constant carrying `/*` rendered `/** opens a comment /* inside */` into the definition
  file, the shared header, the types header and the component's own header at once - and
  `-Wcomment`, which `-Wall` turns on, reports `"/*" within comment`, so the warning set this
  repository verifies the generated code with stopped the build on all four.  Both markers are
  now spaced apart: `/*` renders as `/ *`, beside the `*/` that already rendered as `* /`.

  *The a2l says what it is encoded in.*  The file is utf-8, as every artefact is, and said
  so nowhere: ASAP2 1.6.1 has no `ENCODING` keyword - that arrives with 1.7 - and section 1.5
  of the standard tells a reader to detect the encoding from a byte order mark and to read the
  file as ISO-8859-1 where there is none.  A unit as ordinary as `°C` therefore reached a
  calibration tool as `Â°C`, or stopped its parser.  The a2l now opens with a utf-8 byte order
  mark.  It is the one generated file that carries one: the c sources and the dumped
  dictionary stay utf-8 with lf and no mark, because a compiler and a json reader already know
  what they are reading.

  *A derived limit is the number the description implies.*  Limits nobody states are
  derived by running the raw ends of the datatype through the conversion, and the product was
  written out as the binary arithmetic left it: a `uint8` under `{"factor": 0.03}` stated an
  upper limit of `7.6499999999999995` - below `7.65`, the value its own largest raw count
  stands for - and an `sint16` under `0.1` stated `3276.7000000000003`, one step past the raw
  range.  A calibration tool that holds data to the limits it reads was refusing the value the
  description implies, and the engineer reading the a2l saw a number nobody wrote.  Both ends
  are now rounded to twelve significant digits, the width a reading has always been spelled
  at, wherever they are derived: the a2l, the dumped dictionary, the hover in the editor and
  the checks.  A delivery comparison weighs a narrowing with the same relative tolerance
  `limits-out-of-range` already weighed a stated limit with, because rounding alone would
  only move the problem: every dictionary archived before this release carries the unrounded
  end, and a candidate that states the limits its datatype implies was tightening it by
  3e-13 - a `narrowed-limits` warning, and under `--strict` a "cannot replace", on every
  rescaled object of every old baseline.

  *Two names the generated files could not carry.*  An axis whose `input` named a
  structured variable passed every check, because an instance of a structure is of kind
  `measurement` and only its declared type says that it is not one quantity.  The a2l then
  bound the axis - and the `COM_AXIS` of every curve over it - to `Inst`, while the only
  records in the file were `Inst.a` and the other members: the dangling reference the export
  closure exists to prevent, which an ASAP2 checker reports and a calibration tool answers by
  dropping the reference or refusing the module.  It is now `reference-kind`, and the axis is
  dropped as every wrong-kind reference is.  Beside it the backend now writes
  `NO_INPUT_QUANTITY` for any input quantity the dictionary it is rendering does not carry, so
  a dictionary read back from a dump, written by another producer or edited by a hook still
  renders a module that loads.  Separately, `name-collision` weighed a declared constant
  against data objects, enums, enumerators and types but not against the members of a
  structure - and the example templates emit every constant as a `#define` above the
  structures, so a constant `raw` beside a member `raw` wrote `#define raw 4` a few lines
  above `uint16_t raw;` and no compiler accepted the header.  That pair is now compared too,
  reported at the constant with a note at the member.

  *Two initial values and shapes that reached the compiler.*  An `init` of `1e-50` on a
  `float32` is inside the range that datatype states and past the precision it has: nothing
  reported it, and the generated c carried `1e-50F`, which gcc refuses outright - `floating
  constant truncated to zero`, an error under the same warning set - because the value the
  storage would hold is not the value the description states.  A non-zero initial value a
  floating point datatype rounds to zero is now `init-invalid`.  And a declaration's own
  shape states at most 64 dimensions: six hundred of one element each were under every cap
  there was - they multiply out to one - and ended `ddd generate c` in a `RecursionError`
  where a finding was owed, the walks that expand a shape descending once per dimension.  It
  is `schema` at the `dimensions` that state it, and the declaration is dropped, as for
  every other shape past a limit.

  *A template renders a constant as a literal.*  A `ConstantView` offers `.literal` beside
  `.value`: the value as a c literal of the narrowest type that holds it.  The two differ only
  at the ends of the 64 bit range, where there is no literal to write out bare -
  `-9223372036854775808` is a unary minus over a literal too large for any signed type, and
  `18446744073709551615` has no signed type at all, so a compiler reads it as unsigned and
  says so - and the example types header renders `.literal` now.  `.value` is unchanged and
  stays the number, for a template that does its own formatting.

  *The example templates compile what they generate.*  `docker/compile.sh` compiles every
  generated header on its own, the header included twice and nothing before it, which is what
  proves each is self contained; three legitimate projects ended there with `ISO C forbids an
  empty translation unit`.  The example types header included `<stdint.h>` only when a
  datatype of the project asked for it, and every other generated header includes that one and
  nothing else, so a project whose objects are all floating point and one that declares no
  object at all generated a guard around nothing and two empty translation units out of it;
  it is included unconditionally now, and `model.needs_stdint` still answers the question for
  a project's own templates.  The definition file, which an image registering no component
  left holding one comment, carries a typedef that declares a name and no storage.  And the
  example plugin's table of addresses and sizes includes `ddd_globals.h`, without which the
  one artefact that example exists to show was the one the shipped harness could not compile.

  *Four messages that named the wrong thing.*  A template error gave the line of the file the
  failing frame belongs to under the name of the file being rendered, so a macro imported from
  a helper reported a line of the importing template - usually a blank one; the helper is named
  beside the line now.  A `-t` that does not exist, and a `-t` naming one template rather than
  the directory holding it, both read as a directory holding no template.  A path longer than
  the platform accepts came back as `No such file or directory` about a directory that is
  sitting there, and now says that the path itself was refused and how long it is.  And the
  a2l transliterates `²` and `³`, without which `m/s²` and `m/s` asked for one method name and
  whichever was met second was pushed onto `_2`.

  **Migration:** three descriptions that used to check clean are now errors, and each is a
  line to change.  An axis whose `input` names a structured variable: point it at the plain
  measurement that indexes it, or leave the `input` out, which reads `NO_INPUT_QUANTITY` as it
  always did.  A constant sharing a name with a structure member: rename either.  An `init` a
  `float32` rounds to zero: it was never that value.  A shape of more than 64 dimensions is
  refused, which no description states.  a2l and dictionary files regenerate with the shorter
  derived limits and the a2l with three bytes in front of it, so a diff against an archived
  artefact shows both; no stated limit changes and no check turns into a finding, because
  `limits-out-of-range` weighs a stated limit against the derived range with a relative
  tolerance of 1e-9, which spans the rounding.  A tool that reads the a2l as ASCII or as
  ISO-8859-1 without looking at the first three bytes sees them; every reader that follows the
  standard's own rule, and every one that already read the file as utf-8, is unaffected.
  Nothing that reads a file *back* into DDD is: the a2l is the one artefact DDD never reads,
  and the files it does - a description, a dumped dictionary, a build record - are read with a
  mark tolerated and are still written without one.  Prose carrying neither comment marker
  renders exactly as it did.  Templates a project wrote are untouched: `.literal` is a name
  added beside `.value`, and the changes to the example templates are changes to the copy
  `ddd templates-dir` hands out, not to anything a project already has - a project that took
  that copy and generates for a float-only or object-less image wants the same two edits.
* **The verdict on a delivery.**  Everything a review of the whole tool found in the answer
  to "can this delivery replace the one before it?": three changes it did not see at all, a
  name it did not see reused, a note that cost more than the comparison it annotates, four
  findings that said the wrong thing about an initial value, and an archived dictionary read
  more loosely than the description it was dumped from.

  *An `init` compares as the bytes it stores.*  DDD offers two spellings of one array - a
  scalar fills every element of it, and a string's text is the character codes it stands for -
  and the comparison read the spelling.  Respelling `7` on a `uint8[4]` as `[7, 7, 7, 7]`, or
  a list of character codes as the text it spells, was a `changed-storage` warning and, under
  the `--strict` gate the comparison page recommends, a delivery that "cannot replace" its
  predecessor over generated code that is byte for byte the same file.  The two spellings now
  reduce to one before they meet; the dumped dictionary is untouched and still carries the
  init as the description wrote it, so an archive says what was stated.

  *The layout a released structure fixed for its consumers.*  Swapping two members of a
  structure moves every address after the first of them and narrowing a bitfield changes the
  value every reader takes out of the word - and every member of the edited type compared
  identical to the byte, so the comparison reported nothing at all and the delivery that had
  moved every offset of every variable of that type "can replace" its predecessor, `--strict`
  or not.  This is what the `Member` docstring published in two schemas had always promised a
  comparison reports.  A member's `bits` is a compared interface field now, and the order of
  the members is compared once at the structure, where the edit is - one line of one types
  file, however many variables of that type a project declares.

  *A structured variable is compared as the variable it is.*  The dictionary offers the plain
  objects and the members, never the variables, so two things fell between them.  Renaming
  `Sensor_t` to `Sensor2_t` with the members untouched changes what every consumer's header
  declares - `extern Sensor2_t Inlet` - and was silent, while inside one project the same
  disagreement is a `definition-mismatch`.  And the volatility, section, raster, producer and
  condition a member carries only because its variable states them were compared under every
  member: one edit on one declaration was three findings for a three member structure, and
  one per member of every element of an array of them.  The variable is now paired and
  compared like any other object - its `type`, array shape and locality as interface, the
  rest as storage - and each of those is reported once, where it is written.

  *A name freed by a removal and taken by a rename.*  `reused-name` is the failure that
  compiles, links, runs and reads the wrong storage, and it proved the reuse from one end
  only: it caught a rename landing on a name the baseline's own object had left, and not the
  mirror case - an unstamped `A` removed and a stamped `B` renamed onto the spelling it freed
  - which was two warnings and "can replace", although a dataset keyed by `A` now binds to
  what was `B`'s storage.  A rename proves the reuse from either end now, and the finding
  carries a note naming what the baseline called the object standing under the name.

  *The note under a removal, and what it cost.*  A `removed-object` carries a note when
  exactly one addition is identical to it, which is the only help a project that never adopts
  `id` gets.  It asked that of every removal against every addition of the same kind,
  datatype and unit, so the naming-convention sweep `--renames` exists for - a project without
  ids renaming everything at once - was quadratic: 5 000 objects took three minutes and 53 000
  never finished.  Candidates are grouped on everything the note compares now, and a crowd of
  additions alike in all of it is given up on rather than worked through; 5 000 objects compare
  in a tenth of a second.

  *Four findings about an initial value.*  `changed-storage` printed both inits whole, in
  python's spelling: a `uint8[100000]` block with one element changed was one warning of
  600 017 characters, in the text report and in the json, and the reader still had to find the
  element that moved; a list read `(7, 7, 7, 8)` where the description file, `ddd list` and
  the hover all write `[7, 7, 7, 8]`.  Both sides are json now, cut short past a few elements,
  with the first index they part at named beside them.  Beside those, a list nested one level
  too deep was refused as "init is a list but the object is a scalar" of an object declaring
  `"dimensions": [2]` two lines above - the shape checks name the element they are judging now
  - and `2.0` on a `boolean` was refused as "init value 2", a complaint about a whole number
  nobody had written.

  *An archived dictionary is held to what a description is held to.*  A dump's `format` was
  read as whatever coerced to a number, so one stamped `"9"` or `9.0` went past the check that
  refuses a dictionary from a newer DDD - there was nothing there to compare - and was then
  coerced into the very 9 that check exists to refuse, comparing clean and "can replace"; `0`
  and `-3` were accepted the same way.  It is a strict whole number of at least 1 now.  And
  the dump was handed to a json parser with no hook for a key spelled twice, where every
  description file goes through one that refuses it, so a baseline carrying `"name": "P",
  "name": "Q"` read back as a delivery of a project the line above says it is not.  Both go
  through one reader now.

  **Migration:** three deliveries that used to compare clean now report an error, and each of
  the three is a real change of what a consumer compiles against: a structure whose members
  were reordered, a bitfield whose width changed, and a structured variable whose type was
  renamed.  A project that means one of them accepts it the way it accepts any other, with
  `-W changed-interface=warning` on that run.  `reused-name` fires in one arrangement more,
  and relaxes with `-W reused-name=warning` as before.  In the other direction a comparison
  reports less: a respelled `init` is no longer a change, and an edit to a structured
  variable is one finding instead of one per member, so a script counting findings sees fewer
  of them.  A dumped dictionary is unchanged and still format 8 - nothing DDD writes carries a
  `format` that is not a number, or a key twice - but a file edited by hand into either is now
  refused where it used to be read.  The `--renames` file is unchanged; the specification
  spelled a member's id `<id>` followed by `.` and the member path, where the tool has always
  written the access path, `abcdefghjkmn[0].a` with no `.` before the index, so a migration
  script written from that sentence matched nothing and now has the spelling to key on.

* **The command line, and what a plugin may reach from it.**  What a review of the whole tool
  found at the boundary between the commands, the plugins they run, the paths they are given
  and the streams they write to.

  *A plugin prints on stderr.*  A hook, and the backend a `backend` hook returns, now runs
  with standard output bound to standard error - the arrangement `ddd lsp` has always made
  before a plugin could reach the protocol wire.  Standard output is a document on the command
  line too: a `print` left in a check hook wrote its line in front of the `--format json`
  report of `check`, `generate` and `list`, so a job's `json.loads` failed on it, and in front
  of the dictionary of `ddd dump > baseline.json`, so what a build archived was not json; a
  plugin's backend did the same to `generate --format json`, and both wrote onto the stdout
  `dump -o` promises empty.  What a plugin prints is redirected rather than swallowed: it is
  read on stderr, beside everything else DDD says about a run.

  *An output file is never a source file.*  `ddd dump -o`, `ddd compare --renames` and
  `ddd generate --dictionary` each name a file on the command line, and the obvious way to
  get one wrong is to complete the name of a description sitting in the same directory:
  `ddd dump components/sensor_hub.ddd.json -o components/sensor_hub.ddd.json` replaced the
  hand-written component with the dictionary, said `wrote ... (updated)` and exited 0.  All
  three now refuse a target that resolves to a file the run read - a description of the
  project, one of its includes, a plugin module, or an archived dictionary being compared -
  as a usage error naming it, before anything is written.

  *A finding says where the file is.*  A `location` is "an absolute, forward-slashed path
  together with the json pointer", and every finding of an analysis was one, because the
  loader resolves what it reads.  The findings the command line places itself were not: a
  comparison's own findings, the ones `check --baseline` adds, the note about an address map
  and everything reported about an archived dictionary carried the path as it was typed, so
  `--format json` handed a dashboard a `location.path` of `work/p.ddd.json` that nobody can
  resolve without knowing the working directory of the run - beside absolute paths in the
  same document.  In text they also sorted apart: within one severity the findings sort by
  path, so a relative one landed after every absolute one instead of beside the findings of
  the file it is about, which is not what the comparison page says.  All of them are built
  from the resolved path now.

  *An option is spelled in full.*  `argparse` accepts any unambiguous prefix of a long option
  unless it is told not to, so `ddd check p.ddd.json --stand` and `ddd generate all ... --dict
  d.json` worked - and would break the day a second option starts with those letters, with
  "ambiguous option" as the whole of the explanation.  Every command and every artefact now
  takes its options spelled out.

  *Ctrl-C, and what a plugin cannot be blamed for.*  A hook that raised a `BaseException`
  which is neither `Exception` nor `SystemExit` - `asyncio.CancelledError`, or one a plugin
  declared itself - escaped as a traceback under the findings exit code; it is the plugin's
  failure like any other, named as one.  A `KeyboardInterrupt` inside a hook is not: it still
  stops the run, and the run now ends with `ddd: interrupted` and **exit code 130**, the code
  a shell reports for a command killed by `SIGINT`, instead of thirty lines of python.  A
  plugin's own model is held to the same rule as its hooks, as it already was for the other
  two.

  *A closed pipe is not an error.*  `ddd schema component | head -1` ended with
  `ddd: [Errno 32] Broken pipe` and exit 2, which fails a paging script on the tool's side
  under `set -o pipefail`; the run now ends at 0 and in silence.

  *`-o .` names a directory.*  `ddd dump p.ddd.json -o .` and `generate --dictionary .` ended
  with `WindowsPath('.') has an empty name` - python's words about pathlib, printed as the
  whole of what the run had to say about a missing file name.  Both now say which option
  needs a file.

  *Six messages that said too little.*  `ddd id --assign` stopped at the first file it could
  not write, with `[Errno 13] Permission denied: 'ro.ddd.json'` and no total, the files after
  it unstamped - where a file that cannot be *parsed* has always been reported while the
  others are stamped; a file that cannot be written is now reported the same way and the run
  goes on.  `--address-map`, `ddd schema -o` and `ddd build-info -o` handed back the bare
  errno text, naming neither the option nor what the run was doing with the file; they say
  `cannot read the address map '...'` and `cannot write '...'` now, as `compare` and
  `generate` already did.  The verdict line printed two file names, which for two deliveries
  of one project kept in a directory each read `pressure.ddd.json can replace
  pressure.ddd.json`; where the names coincide it now prints the paths as they were typed.  A
  dumped dictionary handed to `check`, `list` or `dump` was refused as a vocabulary file
  stating three kinds at once - "file has 'types' and 'constants' and 'rasters' at the top
  level" - and is now recognised and pointed at `ddd compare`.  And `missing-plugin` for the
  baseline was located at the candidate, which does not record the plugin it is about, and
  said the run "has not loaded" a plugin the run had loaded to analyse that very baseline: it
  sits at the file that records the plugin now and says the plugin is not among the
  candidate's, which is what did not run.  A `-W` naming a check of such a plugin is accepted
  for the same reason, instead of being refused as naming a check nothing registers.

  *A redirected run reads in the order it happened.*  `ddd list p.ddd.json > log 2>&1` put the
  two errors of the run at the top of the file and the table at the bottom: redirected, stdout
  is block buffered and stderr is not, so the table arrived when the process ended.  `list`
  and `dump` now flush before their findings, as `sources` and `artefacts` already did.  The
  table also padded its columns to a count of code points, which is not a count of columns: a
  unit such as `温度` is two code points and four columns wide, so every cell after it on that
  row started two columns right of its header.  It is measured by display width now.

  *Every row of `ddd list --format json` carries a `name`.*  A member of a structured variable
  was published as a row carrying `path` and no `name` at all - `name` being a property of the
  model rather than a field of it - while a plain object carried `name` and no `path`, so a
  script keying the rows on `name` dropped every member of every structure in silence.  Both
  shapes now open with `name`, a member's being its access path.  And the json payloads
  themselves are documented for the first time: `list`, `artefacts`, `checks` and the
  `generated` key of `generate` and `dump -o` are on the CLI page with an example each, and
  their shapes are stated in the specification beside the commands.

  *The address map is read like every other file, and its grammar is the documented one.*
  The map `--address-map` names was read as plain utf-8 where the description files, the
  dumped dictionaries and the build records are all read `utf-8-sig`, so a map a Windows tool
  or Notepad wrote came back as `Unexpected UTF-8 BOM (decode using utf-8-sig)` - python's
  advice to a programmer, for a file nobody writes by hand.  Its addresses were parsed with
  python's `int()`, which took `0x1_0000` as `0x00010000`, `+5` as `5` and the Arabic-Indic
  `١٢` as `12`; a string address is now written in decimal or behind a `0x` prefix and in no
  other way, whatever whitespace surrounds it.  And a symbol the map states twice is refused,
  where the second address used to win in silence, as the description loader already refuses
  a repeated key.  Every complaint about a map spells its path forward-slashed, as the rest
  of the tool does.

  *What a check hook changes is what everything after it sees.*  A hook is handed the
  resolved dictionary itself, and the `extensions` blocks inside its frozen models are
  ordinary dictionaries, so a hook that writes into one has changed what the backends render,
  what `ddd dump` prints and what `ddd compare` reads back.  Nothing said so.  The plugins
  page now does, in both directions: a hook that reports does not assign, and a value a
  plugin computes for its own artefact belongs to that artefact rather than to a block.
  Read-only views were the alternative and were not taken: they would copy every block on
  every run against something no plugin has a reason to do, change the type every plugin
  already written against the api sees, and still leave `object.__setattr__` one line away -
  a guarantee that reads as complete and is not.

  *A `-W` is held to the plugins of the run, and grades this run alone.*  An override naming a
  plugin's check is verified once the project has been read, and the run used to return before
  verifying it whenever the read reported an error: `ddd check p.ddd.json -W layout/x=error`
  over a project with a missing include reported the missing file and never a word about
  `layout/x`, so a typo on the command line surfaced only on the first run that happened to
  load cleanly - the run that no longer needed telling.  The plugins are loaded by the time an
  include goes missing, so the override is now held to them either way.  With `--baseline` the
  plugins of the run include the baseline's own, which were loaded to analyse it, so a `-W`
  naming one of their checks is accepted there as `ddd compare` already accepts it.  And a
  `-W` no longer reaches the baseline's own analysis at all: `-W unused-output=error`, a run
  asking to be told about *its own* unread outputs, promoted a predecessor's into an error,
  carried it over as `in the baseline:` and refused a verdict on a delivery that is fine -
  where `--strict`, which says the same thing in one word, had always left the baseline alone.
  The errors that analysis does produce are carried at the severity it gave them, so the one
  line saying the dictionary the comparison rests on cannot be trusted is not relaxed away by
  this run's policy.  `--standalone` still reaches it: that says how the file was handed over,
  and the baseline was handed over the same way.

  *What the pages had wrong about all of this.*  `ddd compare --plugin` is refused beside a
  project *candidate*, which names its own plugins - not "beside a description", which is what
  section 7 and the CLI page said while 3.11 and the code said the other thing.  The build
  page now says that configuring imports the plugins a project names, so `cmake` runs that
  python before it has built anything, and that the published pre-commit hook needs Python
  3.12 - which a machine with an older `python3` used to learn from pip, in a message naming
  nothing of the project's.  The CLI page no longer says a component "generates on its own":
  `ddd generate` has no `--standalone`, and a component whose inputs nobody produces generates
  under `--force` or under a `-W` it has decided about.  The templates page says that a
  template directory is code, rendered in an unsandboxed environment, which had been stated
  for plugins alone - a template reads as data and is not.  The plugins page's list of what a
  plugin's artefact accepts was missing `--dictionary`.  And two of the tool's own texts had
  fallen behind the pages that quote them as authoritative: `ddd checks` describes
  `init-invalid` as it fires - an enumerator, a shape and a string init included, as the
  specification, the checks page and the README already said - and `ddd sources --help` says
  it lists the plugin modules as well as the descriptions.

  **Migration:** a script spelling an option by a prefix - `--stand`, `--dict` - now fails
  with "unrecognized arguments" and needs the option's full name; nothing else on any command
  line changes.  The text report of the findings is unchanged - every path is still rendered
  against the directory the command ran in.  A reader of `--format json` that resolved
  `location.path` against the working directory gets the same file; one that compared it with
  a path as typed no longer matches, and should compare resolved paths.  The message of a
  finding about a baseline that cannot be read now spells the file out in full, as the same
  message about a description has always done.  A caller that reads exit codes sees one more:
  130, for a run stopped by hand.  A plugin that printed to standard output on purpose - to
  produce a document of its own there - writes a file instead.  A script that matched the
  wording of `missing-plugin`, or the verdict line of two deliveries whose file names
  coincide, matches new text; no check identifier, option or file format changes.  A run that
  relaxed or silenced a check so that its *baseline* would resolve - `-W
  file-extension=warning` over a tree that does not follow the naming convention - now reports
  that check as `in the baseline:` and attempts no comparison: give the run a baseline that
  checks clean on its own, or the archived `ddd dump` of it, which is what a delivery
  comparison has always asked for.  A `-W` that named a check of a plugin the project does not
  name, and went unnoticed because the project happened not to load, is now the usage error it
  always was.  An address map whose writer spelled an address `+5` or `0x1_0000`, or that
  states one symbol twice, is now refused instead of read: both come from a generator, and
  the message names the symbol.  A reader of `ddd list --format json` that keyed its rows on
  `name` now sees the members of every structured variable it used to drop; one that keyed on
  `path` is unaffected, since the key is still there.

* **The build that runs the generator.**  What a review of the whole tool found between DDD
  and the build system driving it: what a run leaves behind in the directory it writes to,
  the project description the cmake module assembles, the keywords it is called with, and the
  address map the linker hands back.

  *`ddd generate` owns its output directory.*  A run wrote what it rendered and removed
  nothing, and what it renders follows from the descriptions - so a component dropped from an
  image's link graph stopped being rendered and **left its header where it was**, on the
  include path of every other component, where a translation unit went on compiling against
  the interface of a component the image no longer links.  The build system could not clean
  it either: a per-component header is named from inside a description file, so it is not
  among the outputs `ddd_generate()` declares, and `ninja -t clean` left it behind with the
  rest.  A run now records the files it wrote, and the artefact each came from, in
  `.ddd-manifest.json` beside them, and the next run removes the recorded files it no longer
  writes, reporting each as `removed`.  Only files DDD itself wrote are ever removed - a file
  the manifest does not name is left alone - and only the artefacts the run produced are
  weighed, so `ddd generate a2l` into the directory a `generate all` filled still regenerates
  the a2l without touching the c sources the image was built from, and so does a
  `--without`.  The record is written in the same all-or-nothing step as the artefacts and
  renamed after them, so a run that fails, or that changes nothing, changes nothing; a
  `--dry-run` says what it would remove and removes nothing.

  *An include that names a file is that file.*  An entry of `includes` holding one of `*`,
  `?` or `[` was a pattern, and the cmake module writes the includes of a collected project as
  literal absolute paths - so a checkout under a directory somebody named `proj [v2]` turned
  every one of them into a character class that matches nothing, and **every build failed**
  with `include-empty` on a project whose files were all there, the message calling a pattern
  what the module had written as a path.  A literal reading is now tried first: an entry
  naming an existing file is that file, whatever is in its name, and an entry naming none is
  expanded as before.

  *An address map may carry what the a2l never addresses.*  Every entry was held to the
  `0 .. 0xFFFFFFFF` an `ECU_ADDRESS` holds, "whether or not DDD knows the symbol" - and the
  recipe the build page documents extracts *every* defined symbol of the image, so on a 64 bit
  host the hundred entries of the c runtime sitting above 4 GB stopped the generation with a
  usage error.  **Every build after the first failed**, on the very host the page tells the
  reader to try the two-run flow on, and the a2l kept `ECU_ADDRESS 0x00000000` for ever.  Only
  the symbols the a2l states an address for are weighed now; the rest are counted among the
  entries the a2l does not carry and named in the note under `address-missing`, where a stale
  or renamed symbol is already read beside the object it belongs to.

  *A keyword given no value is refused, and named.*  `ddd_generate(fw.elf ... ADDRESS_MAP
  ${DDD_MAP})` with `DDD_MAP` unset or empty - the ordinary CMake mistake - reads to
  `cmake_parse_arguments()` exactly like a keyword nobody gave, and neither call looked at
  `KEYWORDS_MISSING_VALUES`.  So the a2l was generated with every `ECU_ADDRESS 0x00000000`,
  no map was seeded and none was a dependency, and the two-run flow the map was configured for
  never happened - in silence, under a `cmake_minimum_required(VERSION 3.31)` project without
  so much as an author warning.  `PROJECT` without a value fell into the collected mode and
  generated out of the link graph instead of out of the file the caller meant.  Both calls now
  stop the configure step, naming the keyword.

  *The module and the tool are one release.*  Nothing compared them, and `ddd cmake-dir`
  invites a project to copy `Ddd.cmake` into its own tree, where it sits beside whichever
  `ddd` the environment has.  Every option the module passes is checked by the tool's
  argument parser when the build runs it, so a module newer than its tool configured cleanly
  and then failed with `generate: error: unrecognized arguments: --dictionary`, which names
  the option and not the mismatch behind it, while a module older than its tool built quietly
  under the option set of a release nobody was running.  Including the module now runs `ddd
  --version` once and refuses the pair, naming both versions and the tool.

  *A description that does not parse is still checked.*  A component whose file was not valid
  json at configure time was read as a file of some other kind and dropped from its own
  `<target>.ddd` target - so `ninja comp.ddd` answered `no work to do` about a file that does
  not parse, and went on answering it, the target being built at configure time, until
  somebody configured again.  Fixing the typo and asking again therefore reported success
  without having checked anything.  Such a file is now checked like a component, which is the
  command that has something to say about it.

  *The build page does not promise an isolation the module does not build.*  It said the
  header generated for a component "is the only one on its include path"; the module puts the
  whole output directory on every component's include path, so `#include "Controller.h"` from
  another component's source compiles.  The page and the README now say what is built - one
  directory, holding the headers of that image and no others - and what the isolation rests
  on.

  *A generation reads the project once rather than once per component.*  Three phases of a
  run walked the whole project again for every component in it, which a large project pays
  for quadratically: the c model asked the dictionary for the objects of each component, a
  scan of every object there is; the a2l looked for the members of each component's
  structured variables by walking every member of the project; and the alignment of a placed
  structure was worked out once per route through the type graph, which doubles per level of
  a structure holding two of the next one.  A build with an address map also built the whole
  a2l model a second time, to read off it which symbols the file carries.  Measured on one
  machine over a synthetic project of a thousand components and fifty-three thousand
  variables: the c model 7.7 s to 0.9 s, rendering the c sources 7.4 s to 1.1 s, the a2l
  model 3.1 s to 0.4 s, rendering the a2l 3.3 s to 0.7 s, and the symbols an address map is
  weighed against 2.8 s to 0.1 s; twenty-two levels of a structure holding two of the next
  went from 0.7 s to nothing.  Nothing about what is generated changes.

  **Migration:** a directory that a `ddd generate` run is pointed at now belongs to that run:
  its own files are untouched, but a file DDD wrote there and no longer writes is deleted at
  the next run, where it used to accumulate.  Two runs generating into one directory - which
  already overwrote each other's artefacts - now also take each other's files back, and want
  a directory each.  A `.ddd-manifest.json` appears beside the artefacts; a build that lists
  its output directory, or archives it as a delivery, sees one more file, and a run into a
  directory that has none removes nothing, so the first run after this upgrade cleans nothing
  up.  `ddd generate --format json` can report a fourth `status`, `removed`, beside `created`,
  `updated` and `unchanged`.  A project whose `includes` holds an entry spelled exactly like
  a file beside it - `a[12].ddd.json`, with a file of that very name - now reads that file
  instead of expanding the class; renaming either one is what keeps the class.  A
  `ddd_generate()` or `ddd_add_component()` call whose keyword expanded to nothing now fails
  the configure step where it used to be ignored: give the keyword a value, or leave it out.
  An address map entry outside `0 .. 0xFFFFFFFF` for a symbol the a2l never names is read
  where it used to be refused; a build that relied on that refusal to catch a wrong map reads
  the `address-missing` note instead, which names every entry the a2l does not carry.  A
  project whose `Ddd.cmake` is a copy of another release's now fails the configure step
  instead of the build step or nothing at all: copy the module of the tool being used, which
  is what `ddd cmake-dir` prints, or point `DDD_EXECUTABLE` at the matching tool.  A target
  registering a description that does not parse now fails its `<target>.ddd` target, with the
  syntax error, where it used to report nothing to do.

* **What a file says, and what it is told it says.**  What a review of the whole tool found
  in the reader of a description: a spelling that meant something its author did not write,
  and three ways a finding about it named the wrong place or was printed more times than
  there were mistakes.

  *A number in a list `init` is written as a number.*  A quoted value nested inside a list
  was read as whatever it looked like: `["1", "2"]` on a `uint8[2]` was accepted and dumped
  as `[1, 2]`, and `["on", "off"]` - words a lax boolean reading turns into truth values -
  reached the generated c as `{ 1U, 0U }`.  The specification, the type's own contract and
  the published schema agree that a quoted number is text and that text does not belong
  inside a list; only the reader disagreed, because the arm that claims a quoted value at the
  top level - a string object's init is its text - has no counterpart one level down, and the
  lax pass below it parsed `"1"`, `" 1 "`, `"1_0"`, `"1e2"`, `"on"`, `"off"`, `"yes"` and
  `"true"` into numbers.  Every arm of a nested init value is now held to the spelling.  What
  is written as a number still reads as one wherever it stands: a whole number on a float
  object, a fraction, a json `true`.

  *One mistake in a nested `init` is one finding.*  A value inside a list failed again at
  every level above it, because a list is not a number either: `[[1, 2], [3, null]]` on a
  `[2][2]` map was three `schema` errors, two of them saying that a list should have been a
  valid integer, and an init nested a hundred deep was a hundred errors.  The count told the
  reader to go looking for problems that were not there, and reading stops the run, so that
  was the whole answer.  A place that holds what failed is now reported only where nothing
  under it is, so the finding sits on the element that is wrong.

  *A finding under a definition names the key it is about.*  A definition is a tagged union,
  and the reader lost the document on the tag: every segment below it was then judged by its
  spelling alone, so a malformed `extensions` block whose plugin is named with punctuation,
  or named after one of the variants - `map`, `axis`, `enum`, `string`, `linear` and `curve`
  are all legal plugin names - was reported at `definition.extensions` with the key gone, and
  the editor underlined the whole block.  Two such blocks in one definition, or in one
  project, were even one finding: the reader fixed the first, ran again and met the second.
  Each now names its key and is counted apart.

  *A table typed one datatype too narrow is one mistake.*  It was one `init-invalid` per
  element: a `uint8[4096]` initialised with 300 printed 4096 identical lines at one pointer -
  half a megabyte of text - carried 4096 diagnostics in `--format json`, and put 4096 of them
  on one range in the editor, where they can only be read one on top of another.  The values
  of one initialiser that are wrong in the same way are now one finding, which names how many
  there are and, where they differ, the first few of them.  A declaration with one wrong
  value reads exactly as it did.

  *A spelling that reaches the compiler is spelled the way the compiler reads it.*  Five
  places where a description was accepted and something downstream then refused it, or
  quietly took it to mean something else.  A variable, type, constant or enumerator named
  `size_t`, `NULL`, `wchar_t`, `ptrdiff_t`, `max_align_t` or `offsetof` passed
  `reserved-identifier` and stopped the build in the generated header, because the
  `<stdint.h>` a types header includes brings `<stddef.h>` in with it; those six and the C23
  `_WIDTH` macros - `UINT8_WIDTH`, `SIZE_WIDTH` and the rest of the family the check already
  promised to cover - are now reserved with the rest.  An `a2l.format` was matched by an
  engine in which `\d` is every decimal digit Unicode has, so `"%٣.٢"` in Arabic-Indic
  digits was written into the a2l as a `FORMAT` string no calibration tool parses, while the
  published schema, where `\d` is `[0-9]`, refused it; both now say `[0-9]`.  A raster name
  was capped at eight *characters* where the a2l field it is sized for is nine *bytes*, so
  eight letters outside ASCII would have overrun it; a name is now printable ASCII.  A
  `condition` ending in `\` spliced the declaration generated below it into the `#if` and
  the compiler stopped there; it is refused where the other ways out of an expression are.
  And a root file whose name begins with `~` was looked for in a home directory: `ddd check
  ~x.ddd.json` reported `C:/Users/x.ddd.json: file-not-found`, a path nobody wrote.
  Expanding a tilde is the shell's business, and the tool no longer does it a second time.

  *`ddd id --assign` writes into the file it was given, or into none of it.*  The new key
  used to be written straight onto the description, so a kill or a full disk between the
  truncation and the write left a hand-authored file truncated or empty, with nothing left
  to put back; the text is now staged in a sibling and renamed onto the file, the way every
  artefact DDD writes already is.  Two more things it did to a file it was pointed at: a
  declaration whose `name` key carried a json escape - `"name"`, which is `name` - was
  skipped without a word, `wrote 0 ids` and exit 0, while `ddd check` went on reporting
  `missing-id` for it; and a file written with bare carriage returns was given one line
  ending of a kind the rest of it does not use, the search for the file's own having looked
  for a line feed only.

  *A reference is spelled the way the thing it names is.*  A `raster` on a definition or a
  component was free text where the declaration it points at is eight printable characters
  without a space, so `"raster": ""` was answered with `unknown-raster: 'V' is measured in
  ''`, sending the reader after a declaration no rasters file could have carried; it is now
  refused where it is written, as a `section` reference always has been, and the
  specification says so about both.  An `extensions` block is keyed by a plugin's name and
  is now spelled like one: a key such as `a.b` or `c[1]` also made a pointer no consumer can
  split - an editor underlined two keys, or an array element - for a block that could never
  have named a plugin.

  *What the file says, where the file says it.*  The mapping form of `enumerators` is
  rewritten into the list the model holds before it is validated, so a mistake inside it was
  reported at `enumerators[0].value`, a key and an index the file has not got; it is now
  reported at the key that holds it.  The same shorthand published neither the bound on a
  value nor the pattern a name is held to, where the list form publishes both, so an editor
  bound to the schema accepted `{"1bad": 0}` and a value past 64 bits and `ddd check` then
  refused them.  Five keys the loader reads as whole numbers - `dimensions`, `size`, an
  enumerator's `value`, `event` and `alignment` - now say in their published description
  that the number is written without a decimal point, which is a rule json schema cannot
  carry: its `integer` admits `4.0`, and the loader does not.

  *Two answers a run should not have.*  A `cycle` written with five thousand digits was
  answered with python's advice about `sys.set_int_max_str_digits`; a count that long is no
  period, and the tool now says so in its own words.  And a description file larger than the
  memory left to the run ended it with a `MemoryError` traceback, where every other way the
  read can fail - missing, unreadable, not utf-8, a directory - is a located finding and the
  rest of the tree is still read.

  *Read once, and answer without reading at all.*  A dumped dictionary handed to `compare` or
  to `check -b` was read and parsed twice per side - once to find out what kind of file it is
  and once to validate it - which on the 45 MB dump of a thousand-object project is about a
  third of a second thrown away per pass.  It is now read once and handed on.  And `ddd
  --version` and `ddd --help` used to build every contract in the package before answering,
  0.40 s for a line of text that looks at none of them; the command line now reaches each
  layer from the handler that needs it, and answers in 0.12 s.  A cmake configure step asks
  for the version once per project and a pre-commit hook once per file.  Reading a dumped
  dictionary also gained what a description already had: a finding inside it names the key it
  is about, so two malformed `extensions` blocks in a dump are two findings rather than one
  about the whole block.

  *A finding sits where the mistake is written, and names the bound it is about.*  An
  enumerator no storage can hold was reported at the `conversion` of a declared type and at
  the whole `definition` of a declaration, so an editor underlined the name, the datatype and
  the limits of a declaration to say something about one enumerator; both now point at the
  conversion.  A bitfield names itself there: two bits of a `uint8` hold 0 to 3, and the
  finding said that 5 does "not fit into uint8" - a claim about a byte the reader knows to be
  false, about a bound written two keys away - where it now says "the 2-bit field of uint8",
  as the member's limits do; a value past both the field and the c `int` every enumerator has
  to be representable in is one finding rather than two.  The note of an `enum-conflict` said
  "first defined as" and pointed at the best documented copy rather than the first one,
  because the better documented spelling replaces the registered one; the spelling is what
  the types header takes, and the place now stays where the enum was first written.  And
  `duplicate-id` is read over every declaration rather than the surviving ones: a copied
  declaration whose type nobody declares hid the copied id along with itself, so the second
  half of one edit's mistake surfaced only once the first half was fixed.

  *What is reported, and when.*  Five places where a run said less than it knew, or said it
  twice.  `incomplete-project` - the trace a declaration leaves when the finding that dropped
  it is silenced - was held back with the checks that need every component of a project, so a
  component checked on its own with any *other* check relaxed lost a variable from `ddd list`
  and `ddd dump` with nothing said at all, which is the one outcome the trace exists to
  prevent.  It is no longer one of that set: a run handed a single file weighs the cause
  instead and stays quiet only where it is itself the reason nobody reported it - a constant
  declared in a file nobody handed over is not an omission, a `-W dimension-value=ignore`
  is.  Two of its other appearances were wrong the other way round.  A declaration whose own
  reference was refused *and reported* earned the trace as well, an info saying that the
  cause is not reported filed beside the error that is the cause; it now says nothing, and
  the object that did go in silence keeps the trace of its own.  And a text `init` on an
  object that is not a string was refused only once the declaration resolved, so silencing
  the unknown constant that sizes it silenced that too - it is a rule about the conversion,
  and is now answered where the conversion is read, whatever the shape turns out to be.  The
  second copy of a `duplicate-declaration` is finally what the checks page says it is,
  ignored for the rest of the run: its unit, its section and its raster were still read, and
  answered with findings the reader can only fix by deleting the copy the first finding
  already names.  And a conflicting second copy of an enum screens the enumerators it adds,
  which take an identifier in the shared types header like any others and used to take one
  unscreened.

  *What the dictionary carries.*  Three claims about it that were not true of it, and one
  answer that depended on the include order.  A structure member naming a type nobody
  declares carried no storage at all - no `datatype`, no `type`, no `external` - which read
  back out of a dump, compared clean against a member that holds a value, and reached a
  `--force` types header as `None ghost;`.  The contract now asks every member to hold
  something, and such a member records the name it was declared as, which is what the
  `unknown-type` finding beside it is about and what the compiler then asks for.  The leaves
  of an instance, and the rows the tool lists from them, are ordered with every `[n]` read as
  the number it is, so an instance of twelve reads `[0], [1], [2]` where it read `[0], [10],
  [11], [1]`.  Under a silenced `local-conflict` or `multiple-producers` the owning
  declaration - whose unit, conversion and `init` reach every consumer's header - was
  whichever one the project happened to include first; it is now the `local` declaration,
  else the first producer by component name, so two files generate the same bytes whatever
  order a third lists them in.  And the ordering walk over the declared structures no longer
  claims that the structures of a `type-cycle` are left out of the dictionary: they are in it
  like any others, and the error is what stops anything being generated from them.

  *One rule, one place.*  Four rules were written out twice between the analysis and the
  comparison - the raw range a bitfield member holds, how a finding spells what an object
  refers to, what an absent condition is called, and what makes a variable local - and one
  pair had already drifted: an absent condition read "no condition" in a project report and
  "none" in a delivery comparison, which put "uses condition no condition" into one sentence.
  Each is written once now, and `condition-mismatch` says `none`, the way every other
  unstated value in a finding does.

  **Migration:** a list `init` holding a quoted number or one of those words is now refused
  with a `schema` finding at the element that holds it, where it used to load, generate and
  dump.  Write the value without the quotes: `["1", "2"]` becomes `[1, 2]`.  A string object
  is untouched - its init is its text, written as one string rather than as a list of them.
  The other three change what a run says about a file it already refused, not what it
  accepts: a file with one of these mistakes now reports fewer findings than before - one
  where there was one per enclosing list, one per block and one per element - so a build that
  counts findings rather than reading them counts differently.  Four more spellings are
  refused where they used to load: a name reserved by `<stddef.h>` or by the `_WIDTH` family,
  an `a2l.format` written in non-ASCII digits, a raster name outside printable ASCII, and a
  `condition` ending in a backslash.  Each of them broke something further along - the
  compiler, the calibration tool, the a2l event field - so the description that carried one
  had to change anyway; the finding now names it.  And a path beginning with `~` is read as
  the name it is: a project that relied on the tool expanding it passes the expansion from
  its shell instead.  Three more spellings join them: a `raster` reference outside what a
  rasters file may declare, an `extensions` key outside `[a-z][a-z0-9_]*`, and - on Windows
  only - a wildcard `includes` entry spelled with a bare drive, `C:*.ddd.json`, which used
  to expand in the directory the process happened to be in and now expands in the project's,
  the way the same spelling without the wildcard always did.  Each of the first two was
  already reported at the end of the run, as `unknown-raster` or `unknown-extension`; the
  finding moves to where it is written and becomes a `schema` error.  The reader refuses
  nothing else it used to accept, and nothing in this entry changes an exit code: what does
  change is the number of findings a run prints.  A component read on its own - `ddd check
  --standalone`, a build's per-component target, a file no build claims in an editor -
  reports one `incomplete-project` info per declaration a relaxed check of the caller's own
  took out of the dictionary, where it used to report none; a run that relaxes none is
  untouched.  A project run reports one fewer wherever the object's own reference was refused
  and reported, and one more wherever a text `init` sits on an object that is not a string and
  never resolved.  An archived dump is read back as it always was, with one exception: one
  carrying a structure member with no `datatype`, no `type` and no `external` - which only a
  dump taken from a project with an `unknown-type` error can hold - is now a `schema` error
  naming the member, where it used to load and compare as though the member held something.
  Re-dump it from the project it came from, with the type declared.

* **The same project generates the same bytes on any machine.**  The one promise of the
  generated output that the tool did not keep, and the last thing a review of the whole tool
  found: the matches of a wildcard `includes` entry
  were sorted as the platform compares two paths, which is case insensitively on Windows and
  by code point on Linux.  A project whose `components/*.ddd.json` matched `Zeta.ddd.json`
  and `alpha.ddd.json` therefore loaded them in one order here and the other order there, and
  since the components keep their include order, the definition file, every component header
  and the a2l `GROUP`s came out differently on the two machines - a diff nobody wrote, in
  files a build compares to decide whether to recompile.  The matches now sort by the code
  point of their POSIX spelling, which is what every name in a generated file already sorts
  by; whether two paths are the *same* file still follows the platform, that being a property
  of the file system rather than of the output.

  **Migration:** a project whose wildcard includes match file names differing in case class -
  an upper case initial beside a lower case one - regenerates its c and its a2l once, with
  the components in a different order; the content of each is unchanged, and nothing about
  what the project *means* depends on the order.  A project whose matched names sort alike in
  both readings, which is every project whose files follow one convention, is untouched.

* **Constants hold any number.**  A constant's `value` was an integer of at least 1, because
  a constant was thought of as a size; but every declared constant is emitted - a `#define`
  through the c templates, a `SYSTEM_CONSTANT` in the a2l - whether or not a shape names it,
  so an offset, a gain or a count of zero was refused for no reason it had.  The value is now
  a whole number of either sign a 64 bit target holds, or a finite number written with a
  fraction, and the spelling decides which: `2` is whole, anything with a point or an
  exponent is not, and a template emits the number in its shortest spelling that reads back
  as the same one - `2.50` as `2.5`, `1e3` as `1000.0` - which keeps the type the author
  picked and not the format.  The size rule moves to where it applies: a shape naming a
  constant that is zero, negative or fractional is the new check `dimension-value`, an error
  reported at the `dimensions` entry or the `size` that names it, and the declaration is
  dropped as for `unknown-constant`.  Unlike that check it needs only the file in front of it,
  so `--standalone` and the language server report it too.  **Migration:** none for a
  description file - every value that was valid still is, and means the same.  A template
  that assumed a constant is a positive integer - formatting it with an unsigned suffix, say
  - should now expect any number.  The dumped dictionary stays format 8, whose other changes
  are listed below; a reader that only knows format 7 refuses a format 8 file as it refuses
  any newer one.

* **Strings.**  A fourth conversion kind, `{"kind": "string"}`, reads a one dimensional
  `uint8` or `sint8` array as text, on a measurement, a value block, a structure member or a
  scalar type; its `init` may be written as a string, printable ASCII shorter than the
  dimension, and the generated c carries it as a string literal.  A calibration string
  reaches the a2l as a `CHARACTERISTIC` of type `ASCII` with a `NUMBER`; a string measurement
  stays the byte array it is, with an `ANNOTATION` saying so, because no version of the
  format has a string measurement.  A string states no unit, limits or display format, and
  the rules are `schema` where they are broken; a wrong string init is `init-invalid`.
  Between deliveries a string `init` compares as the bytes it stores - its text padded with
  zeros to the dimension - so `"Hi"` and `[72, 105, 0, 0]` on a `uint8[4]` are the same
  initial value and neither spelling is reported as a change of the other.
  **Migration:** one spelling changes meaning, see the end of this entry; otherwise none for
  a description file - no existing file carries the kind, and `{}` is the identity it always
  was.  The dumped dictionary is format 8, for the new kind and the
  string `init`; a format 7 dictionary reads back unchanged, and a reader that only knows 7
  refuses a format 8 file as it refuses any newer one.  One spelling changes meaning: a
  quoted number as an `init`, `"12"`, used to be read as the number and is now text, refused
  on anything but a string object as `init-invalid` - spell the number as a number.

* **A delivery comparison spells an enum change out.**  `changed-interface` printed a
  reordered or revalued enumeration as `enum(Mode_t) != enum(Mode_t)`, the name being all
  the description of an enum said; the finding now lists the enumerators on both sides, in
  the spelling `enum-conflict` already uses inside a project.

* **The sdist no longer carries `docs/superpowers/`.**  The design and planning records of
  each feature were shipped beside the documentation, and nothing an sdist is sent to reads
  them.

* **`ddd dump -o FILE` writes the dictionary into a file.**  Archiving the dictionary meant
  redirecting stdout, which leaves the bytes to the shell - the `>` of Windows PowerShell 5.1
  re-encodes them as UTF-16, which `ddd compare` refuses to read back - and empties the
  target before the tool has even started.  `-o` writes the text stdout would have carried
  the way `generate` writes an artefact: utf-8 with lf on every platform, staged, and left
  untouched when its content would not change.  Unlike `generate`, a finding does not hold it
  back - the dictionary is what the project resolved to, errors and all, which is what makes
  it the thing to archive beside a delivery that failed - so only a root that cannot be read
  leaves the file as it was, there being no dictionary then.  A build gates on the exit code,
  which stays what it was, as do the findings on stderr; the json report there names the file
  written, as `generate`'s does.  A target that resolves to a file the run read is refused,
  as it is for `--renames` and `--dictionary`.
  **Migration:** none.

* **`ddd generate --dictionary FILE` writes the dictionary beside the artefacts, and the
  cmake build does.**  Every artefact takes it: the resolved dictionary, the text `ddd dump`
  prints, goes into the same write as the artefacts - all of them or none, a file whose
  content would not change left untouched - and a path an artefact of the run is written to
  is refused.  `ddd_generate()` passes it, so a build now writes `<project name>.dictionary.json`
  into its output directory - the name the a2l takes, which beside `PROJECT` is the one
  written inside that file - which is what a template author reads and what a delivery
  archives for a later `ddd compare`; its path is the image's `DDD_DICTIONARY` property.
  **Migration:** a cmake build gains one file in its output directory; `NO_DICTIONARY` leaves
  it out.

* **A component lists and dumps on its own.**  `ddd list` and `ddd dump` take the
  `--standalone` of `ddd check`, holding back the checks that need every component of a
  project, `-W` still applying on top.  Without it a component carrying a plugin's
  `extensions` block was refused by both with `unknown-extension`, because only a project
  names its plugins.
  **Migration:** none.

* **An image lists from the build.**  `ddd_generate()` adds a `<stem>_ddd_list` target
  printing the table of the image's variables - `ddd list` on the image's project, under the
  build's severities, with its plugins loaded and every producer and consumer resolved.
  **Migration:** none.

## 0.9.0

* **A reference into another component's local object is a use.**  A curve, map or axis of one
  component that named an axis or a measurement another component declared `local` was
  accepted: `local-conflict` compared declarations alone, so the referring object compiled,
  linked and reached the a2l bound to that private object, which is exactly the coupling
  `local` forbids.  Such a reference - an `axis`, an `x_axis`, a `y_axis` or the `input` of an
  axis - is now `local-conflict` too, reported at the reference rather than at a declaration,
  with a note at the local declaration.  The object is not dropped: the mistake is the
  ownership violation, not a missing object, and a component that declares the object as well
  as referring to it gets one finding for each, where it wrote each of them.
  **Migration:** a project whose build turns red on the new finding either declares the object
  `output` in its owning component, so that the reference is a legitimate shared use, or moves
  the referring object into that component.

* **Every integer a description states fits 64 bits.**  A `limits` bound or an enumerator's
  value too large for a float ended the run in an `OverflowError` traceback, because both are
  converted to a float before they are weighed against the range of a datatype; a constant, a
  bare dimension or a section's `alignment` of the same size was accepted in silence, with no
  finding of any kind; and a whole number between `2**64` and the largest float - past every
  datatype, but small enough to survive the conversion - was quietly read as a float, so an
  oversized `limits.max` was answered with `limits-out-of-range` and an oversized `init` as a
  number written fractionally, neither of which is what the author wrote.  Every integer a
  description states - a limit, an initial value, an enumerator's value, a constant, a
  dimension, a section's `alignment` - is now bounded to `-2**63 .. 2**64-1`, what a `sint64`
  and a `uint64` span together, and a wider one is `schema` where it is written, "does not fit
  64 bits", before any arithmetic sees it.
  **Migration:** a limit or an initial value written as a whole number between `2**64` and the
  largest float used to be accepted as a float and answered, if at all, several passes later;
  it is refused now, at the key that states it.  No datatype DDD offers holds such a value, so
  the number itself is the mistake: state one the object's datatype can carry.

* **A json document nested too deeply to read is a finding, not a traceback.**  The reader
  that loads description files already reported `json-syntax` for a document nested deeper
  than python's parser goes; four other paths ran that parser without catching what it raises
  there, so `ddd compare` on a dumped dictionary, the sniff that decides whether a side of a
  comparison is a project, a component or a dictionary, the language server's document reader
  and `ddd id --assign` each ended in a `RecursionError`, at whatever line the stack happened
  to run out on.  Each now
  answers the way an unreadable file already was answered: `json-syntax`, "the json is nested
  too deeply to read", from `ddd compare`; "not readable as json, skipped" from
  `ddd id --assign`; no spans, and the rest of the workspace still served, in the language
  server.  A `ddd compare` side that is not valid utf-8 was a usage error - exit 2, as though
  the command line were wrong - because the sniff let the decoding error out; the file now
  reaches the reader that has a message for it, and is a finding, exit 1, like any other
  unreadable file.

* **An include tree and a structure nest at most 64 levels.**  Five hundred projects each
  including the next ended in a `RecursionError`, two frames a level; a thousand structures
  nesting each other did the same in the walks over the type graph, and five hundred were
  enough when a variable of the outermost sat in a declared section, which walks the chain a
  third time.  Includes now nest at most 64 levels - the root of the run is the first, and a
  component file counts as a level like any other - and a deeper entry is the new check
  `include-depth`, at the entry that crosses the limit; that entry is not followed, the rest
  of the project is read as usual, and the severity is fixed, because the entry is left out
  whatever the finding is called.  It is reported once the whole tree has loaded, and only for
  a file no shallower route read, so which of two includes was written first cannot decide
  whether it is reported.  A structure nests at most 64 levels too - one level is one
  structure, a member naming a scalar or an external type adding none - and a deeper one is
  `schema` at the innermost type that crosses the limit, with every type nesting it unusable
  for the same reason and every declaration naming one of them dropped.  The walks over the
  type graph are iterative now, and each type is walked once a pass rather than once per route
  into it: a diamond - a type that two members of one structure both nest - used to be
  re-entered from every branch, so seventy-two types took more than two minutes to answer and
  now take milliseconds.
  **Migration:** an include tree deeper than 64 levels, or a structure nesting deeper than
  that, was read before if the interpreter's stack happened to hold, and is refused now:
  flatten the tree, or the type, to stay inside the limit.

* **An array, a map and a structure are capped before anything expands them.**  Nothing
  bounded a shape.  A `uint8` array of `[1000000000]` with a scalar `init` passed the check in
  half a second and was then broadcast into one c literal per element: `ddd generate c` had
  written nothing after three minutes.  A two member structure over `[100000, 1000]` was still
  being flattened when it was killed after two and a half minutes, and twenty rungs of types
  each nesting the rung below twice - 1 048 576 leaves - were reported consistent after 39
  seconds.  A 5000 by 5000 map with a scalar `init` wrote 125 MB of `ddd_globals.c` in 19
  seconds.  An array now holds at most 10 000 000 elements, a map at most 10 000 000 over the
  product of its two axes, a structure type at most 100 000 leaves - whether or not anything
  declares a variable of it - and an array of structures at most 100 000 leaves in total, a
  leaf being one value member of one element, which the dictionary, the a2l and the generated
  code each carry an entry of.  Each is `schema` where the shape is written: at `dimensions`,
  at the `size` of an axis, at the whole declaration of a map, which states no shape of its
  own, and at the innermost type that crosses it for a structure.  The declaration is dropped,
  so each of the runs above is one finding in half a second now, with nothing written.
  **Migration:** a project declaring an array, a map or a structure past one of these limits
  used to be analysed and generated, slowly, and is refused now.  A shape that large is
  usually a constant that resolved to the wrong number; one that is meant needs splitting into
  objects a calibration tool can carry.

* **A finding on a key that only looks numeric is reported.**  The findings of one file are
  ordered by their json pointer, so that `interface[10]` follows `interface[2]` rather than
  preceding it, and whether a part of a pointer was an index was decided by `str.isdigit`,
  which is true of a superscript two and of every other unicode digit `int` refuses.  A
  document with such a key has a finding of its own to report - an extra top-level key is
  `schema` - and sorting the findings for display raised instead: the run printed
  `ddd: invalid literal for int() with base 10: '²'` and exited 2, the code for a mistyped
  command line.  A part is an index by its position in the split now, not by what it looks
  like, so the finding is reported at the key it belongs to and the run exits 1.

* **A scalar type is checked where it is declared.**  The `limits` and the enumerators of a
  declared scalar type were checked once per declaration naming it, and each finding was
  rendered at `component.interface[N].definition.limits` - a pointer into a file that does not
  contain a `limits` key, and may not state one, since a declaration naming a type restates
  none of what the type fixes.  A type no declaration named was not checked at all.  Both are
  checked where the type is declared now, once and whether or not anything names it:
  `limits-out-of-range` at its `limits`, the names and values of its enum at its `conversion`;
  a declaration naming a type is still checked for what it adds of its own, its `init`.  The
  enum of a declared type reaches the types header on the same terms as a structure member's:
  a member naming a scalar enum type used to give the a2l a `COMPU_VTAB` for a name the
  generated `ddd_types.h` declared no `typedef enum` for, two artefacts of one run disagreeing
  about what the name means.  An inline enum that disagrees with a declared type's enum of the
  same name is `enum-conflict`, with a note at the type, even when nothing names that type.
  **Migration:** two spellings of one enum name, one on a declared type nobody names and one
  written inline on a declaration, were silent before and are `enum-conflict` now.  The header
  carries the type's spelling, so either make the declaration agree with it or give one of the
  two enums a name of its own.

* **A dangling reference drops the referring object.**  With `unknown-reference` or
  `reference-kind` relaxed, a curve whose axis nobody declares was kept anyway: the c
  backend declared it as a scalar, and the a2l backend wrote no `CHARACTERISTIC` for it
  while its component's `GROUP` still named it.  An axis whose `input` nobody declares was
  kept whole instead: the a2l backend wrote its `AXIS_PTS` with an input quantity naming a
  measurement that does not exist, a file a calibration tool refuses whole.  The referring
  object is now dropped the way an object referring to a dropped declaration already was,
  transitively, and `incomplete-project` reports the absence when the finding is silenced.
  **Migration:** a project relaxing either check, or simply reading the dictionary with
  `ddd list` or `ddd dump`, now gets a smaller, consistent result instead; an unforced
  `ddd generate` left at error severity already wrote nothing and still does.  A baseline
  dumped by an older DDD that still carries such an object compares against the same
  project as a removal - `removed-object` where another component read the object,
  `removed-unused-object` where none did - which is the honest verdict, since the object
  is gone.

* **A failed step after the analysis no longer discards the findings.**  A plugin hook
  that raised, an address map that could not be read, a `--renames` file or an artefact
  that could not be written, a `--plugin` refused beside a description, or a run that
  would write nothing turned the whole run into one usage error line, and the findings
  of the analysis - the ones the reader of a failed run needs - were gone with it.
  They are now printed first, in the requested format, and the usage error follows;
  the exit code is still 2.  The `--renames` failure names the option, and a write
  failure names the file rather than its directory.

* **A dropped declaration is still a declaration.**  A producer naming an unknown type made
  every consumer a `missing-producer`, and a consumer dimensioned by an unknown constant made
  its producer an `unused-output`, each finding pointing at the file the mistake was not in.
  Ownership is now decided over every declaration, dropped ones included; an object whose
  producing declaration was dropped is left out of the dictionary whole, with every
  declaration of it; where one producer resolved and another was dropped, the object is
  built from the one that resolved, whichever file the project lists first; a second
  declaration of a dropped name is a `duplicate-declaration`.
  `incomplete-project`, which fires when the finding explaining a drop is silenced, now
  reaches every declaration the dictionary omits on that account: a variable of a poisoned
  type, the consumers of a dropped producer, a curve over a dropped axis - it used to name
  only the dropped declaration itself, so most of what a silenced check removed went
  unmentioned.  Its message says what is missing: the component whose declaration went, or,
  for an object that went with what it refers to, the reference that pulled it down.

* **The specification catches up with the tool.**  `SPEC.md` now states what 0.8.0 and this
  release do: `ddd check --standalone` and the per-component `<target>.ddd` target, the empty
  address map that raises no `address-missing`, the `COMPU_METHOD` sharing key and the display
  format rule, the closure over an exported axis's input, the A2L file name and record order,
  the `<stem>_ddd_headers` and `<stem>_ddd_globals` targets and `DDD_A2L`, the plugin name
  grammar and its reserved names, the shape of the `--renames` file, the verdict of a
  comparison, the orders of the listings, and a section describing the data dictionary.  It
  defines "instance" and "leaf" and uses "storage" for the key group alone.  No behaviour
  changed.

* **The published schemas refuse a base datatype's name in any case, as the loader does.**  A
  declared type may not be called after the storage it is not, and the loader refused
  `UINT16` as readily as `uint16`; the type name pattern published in the schemas refused
  only the lower-case spelling, so an editor bound to a schema called a file good that
  `ddd check` then rejected.  The pattern now spells every letter of every base datatype as a
  two-letter character class - a json schema pattern carries no flags, and the inline
  `(?i:...)` form is recent enough that an editor's engine may not have it - and the two
  agree, so `UINT16` is underlined where it is typed instead of at the next build.
  **Migration:** nothing the tool itself accepts or refuses has changed, and no description
  file that used to load stops loading.  What changes is what an editor says while the file
  is being written, so a project that keeps a copy of the schemas in its own tree regenerates
  it - `ddd schema all -o <directory>`, or a configure run where `ddd_generate()` writes them
  through `SCHEMA_DIRECTORY`.

* **The sdist carries what its own tests and its documentation build read.**  The archive
  ships the tests and the documentation on purpose - it is what an evaluator is sent - but
  not what either of them reads outside `src/`: from an unpacked archive the documentation
  tests stopped at collection on `.github/workflows/docs.yml`, and the documentation build,
  which takes its logo and its favicon from `assets/logo/`, failed on the two missing images
  under `-W`.  It now carries `assets/`, the editor extension's sources under
  `editors/vscode/`, `.github/workflows/` and `.pre-commit-hooks.yaml`.  A test derives the
  paths the suite and the docs build spell as `ROOT / ...`, and the images `docs/conf.py`
  names, from the sources themselves and holds the include list to them, so the next path
  added that way is answered in the ordinary test run rather than by whoever installs from the
  archive.

* **The language server decodes the uri VS Code sends on Windows.**  A client spells a
  Windows file as `file:///c%3A/...`, drive lower-cased and colon escaped, and the server read
  that as the relative path `/c:/...`: it analysed a file that does not exist and exited on
  the first `didOpen`, trying to publish under a uri it could not form.  The escaped drive
  colon is now restored before the path is decoded, and the server no longer dies on the uri
  a Windows client sends.

* **Edits are computed against the editor's buffer.**  Rename and the quick fixes read
  positions from, and wrote edits for, the file on disk, while the client applies an edit to
  what is on screen; one unsaved line above a declaration was enough to rewrite an unrelated
  line.  The server now keeps the text of every open document (`textDocumentSync.change` is
  `1`, full content), computes positions and edits against it, refuses a rename that an open
  buffer with unsaved changes would leave half applied, naming the file, withholds a quick
  fix it cannot check against every other declaration, and answers a client that takes
  `documentChanges` with the version each edit was computed for.  The analysis still reads
  the disk on open and save, as before.

* **Opening a repository runs its plugins, and the pages now say so.**  A description names
  the plugins the server runs, and the server runs the plugins of every project it finds above
  an opened file.  The VS Code extension declines a workspace that has not been trusted
  (Restricted Mode), and the editor page, the extension's README, the plugins page and the
  specification state the boundary.

* **Renaming a type or a constant from the editor.**  `F2` on the `name` of a declared type
  or on any `typename` spelling it rewrites the declaration and every definition and member
  naming it; on a declared constant or any dimension or axis `size` spelling it, the
  declaration and every dimension.  The refusals are the variables' - a reserved or unusable
  name, one the project already uses - plus a type name spelling a base datatype.

* **Plugins in the build.**  `ddd sources` lists the modules of the plugins a project names
  beside its description files, each by the file it was imported from, so a build re-runs the
  generation when a plugin changes.  `ddd generate all` produces the artefact of every plugin
  the project names that provides one, after the built-in artefacts and in the order the
  project names the plugins; a path two backends claim is refused before anything is written.
  `ddd_generate` takes `PLUGINS <spec>...`, writes them into the project description it
  generates, closes the schemas of `SCHEMA_DIRECTORY` over them - or over the plugins a
  `PROJECT` file names - and depends on the ones that are files; the plugins' artefacts
  arrive beside the built-in ones.

* **The registered components' compile usage travels with `<stem>_ddd_headers`.**  In the
  collected mode, `ddd_generate()` used to apply the interface include directories, compile
  definitions and compile options of every registered component privately to
  `<stem>_ddd_globals`, the object library compiling the definition file.  It now carries them
  as interface usage on `<stem>_ddd_headers`, which `<stem>_ddd_globals` links for them.
  Only the definition file could be compiled before: `ddd_types.h` includes the headers
  declaring the external types, so the include directory alone never sufficed, and a component
  including its own generated header had to find those headers by itself.  Linking
  `<stem>_ddd_headers` is enough now.  The price is that every registered component compiles
  under the union of those compile definitions and compile options, including ones belonging to
  components it does not link; `ddd_types.h` holds the external includes of the whole project
  and every component header includes it, so all of them have to read those headers alike, and
  a project whose components disagree about such a flag has to settle it itself.
  **Migration:** a component that wired up an external type's header by hand, only so that its
  own generated header would compile, can drop that wiring.

* **`NO_A2L` no longer silently drops the plugins' artefacts.**  In the cmake integration it
  selected the `c` artefact instead of `all`, and `all` is the only run that produces a
  plugin's artefact, so a build that asked for no a2l quietly got no plugin output either -
  quietly because a plugin's files are its own and are not declared as outputs, so nothing
  failed until a consumer looked for one.  `ddd generate all` now takes a repeatable
  `--without c|a2l`, which leaves that built-in artefact out of the run and produces
  everything else, and `NO_A2L` passes `--without a2l` rather than narrowing the run.  A run
  that `--without` leaves with nothing to write is refused instead of reporting success.
  **Migration:** none for a build using `NO_A2L`; it now gets the plugin artefacts it asked
  for.  A command line spelling `ddd generate c` to avoid the a2l keeps its meaning, and
  should become `ddd generate all --without a2l` if the project names a plugin.

* **`ddd artefacts` reports what a project can be asked to generate.**  It prints the built-in
  `c` and `a2l` and the name of every plugin the project names that provides one, in text or
  json, and is tolerant the way `ddd sources` is: which artefacts exist follows from the
  plugins a project names, not from whether its interfaces agree.  Given `--plugin` instead of
  a project it answers the same question for a build that has not assembled its project
  description yet, which is the spelling the CMake integration can use at configure time.
  What each artefact *writes* is deliberately not reported: a plugin's file names follow from
  the resolved dictionary, and `ddd generate all --dry-run` already lists them.  A plugin that
  provides no backend is no artefact of its own; it is named in a note rather than passed over,
  since an unexplained absence reads as a plugin that failed to load.  The note says where its
  output does come from: the block such a plugin contributes is part of the vocabulary the
  project's own templates read, and those are rendered by the `c` artefact.

* **`ddd-compile` counts a structured variable as the one symbol it is.**  The symbol check
  behind it read `ddd list --format json`, which reports what can be *described*: the leaves of
  a structured variable, and none at all for an external member.  Those leaves carry no `name`,
  only the path and the instance they belong to, so the check crashed on the first project that
  declared a structure; and a structure whose members are all external had real storage, a real
  symbol and no entry at all, so the check called its definition stray and failed a correct
  project.  It reads `ddd dump --format json` now, whose `objects` and `instances` are exactly
  what the definition file defines - one symbol each, however many leaves a structure has.

* **`--without` subtracts an artefact's options along with the artefact.**  `--without a2l`
  beside an `--address-map` used to load and validate the map, and could abort the run over a
  file it would never read - the two-run flow the option exists for, where the map does not
  exist before the link.  Options belonging to an artefact that was left out are now refused,
  `--byte-order` among them, and the address map is not opened at all.  `--without c` no longer
  demands `-t`: the template directory is asked for once the subtraction is known, so a run
  producing only the a2l and the plugins' artefacts needs no templates it will not read.

* **A run that would write nothing is refused the same way whatever the project.**  The check
  sat after the findings gate, so the identical command line was a usage error on a consistent
  project and a list of that project's findings on any other.  It now runs before the gate.

* **`ddd-compile` finds the headers of external types more reliably.**  It searches for an
  `include` directory from the description upwards, so pointing it at one component of a
  project reaches the project's own; `INCLUDES` now adds to that rather than replacing it; and
  a path containing a space is no longer split into two compiler arguments.

* **`NO_A2L` stops making the address map a dependency of the generation.**  A map named beside
  it was still seeded and still depended on, so a post-link step rewriting it re-rendered every
  c source on every build, for a file the run no longer passes to the generator.

* **The demo declares an external type.**  `SensorHub` declares `DriverState_t`, whose header
  the demo keeps beside its descriptions in `examples/demo/include`, and a `SensorDiagnosis_t`
  structure that carries it next to an ordinary member; `Diagnosis` is a variable of that
  structure.  The generated `ddd_types.h` therefore includes the vendor header, which is what
  the feature looks like in the generated code, and the demo now shows the rest of it too: an
  external member reaches no a2l record, contributes no leaf to `ddd list`, and is storage DDD
  carries without describing.  The shipped cmake example publishes the directory holding that
  header from `sensor_hub` alone, so `event_logger`, which does not link `sensor_hub`, compiles
  the generated headers only because `ddd_generate()` hands the registered components the
  compile usage it collected - the cmake test that builds the example now fails if it stops.
  `ddd-compile` takes an `INCLUDES` variable for the same reason, defaulting to the project's
  own `include` directory when it has one.

* **A plugin module is registered before its body runs.**  A plugin loaded from a `.py` path
  reached `sys.modules` only once its body had finished, so a module that looks itself up
  while it runs - a `@dataclass` under `from __future__ import annotations`, resolving its own
  forward references through `sys.modules` - found nothing there, and the plugin was refused as
  `plugin-invalid` with "failed to import: 'NoneType' object has no attribute '__dict__'", a
  reason naming neither the dataclass nor anything its author could act on.  The module is
  registered before it runs now, the way importlib's own recipe does it, and a body that fails
  is no longer left cached half-run: one that raises, and one that calls `sys.exit` - which
  used to end the process with the code it named - are both `plugin-invalid`, the second
  "exited during import: SystemExit(3)", and the entry is removed again, so the next load in
  the same process - the language server re-analysing after a keystroke - reports that failure
  again instead of "exposes no PLUGIN".

* **A backend's files stay inside the output directory.**  A path a backend handed back was
  compared with the other artefacts' exactly as it was spelled, and then written exactly as it
  said.  A plugin could therefore claim `ddd_globals.h` under a spelling the clash check did
  not recognise - `<output>/sub/../ddd_globals.h`, or the same directory reached through a
  junction - and overwrite the c backend's header in silence; and a path never anchored to the
  output directory at all - a bare `ddd_globals.c`, or one climbing above what `-o` named - was
  written wherever it pointed, beside the process's working directory or a level above the
  directory the reader asked for.  The output directory is resolved once now, before any
  backend runs, so every backend is handed an absolute directory; every path one returns is
  anchored there when it is relative, resolved, and measured against it.  One that lands
  outside is a usage error naming the backend and the path, exit 2, before anything is written,
  and two that resolve to one file are the refusal two artefacts claiming one path always got,
  whichever spelling each of them used.  What a run reports, and the `path` of each entry of
  `--format json`, still reads as the `-o` the reader typed: a relative one stays relative, and
  a junction is named as typed rather than as the directory its files land in.
  **Migration:** a plugin backend returning a path outside `-o`, or a bare relative path that
  used to land beside the process rather than in the output directory, is refused now.  Build
  every path from the `output_dir` the hook is handed, which arrives resolved.

* **A hook that exits the interpreter is the plugin's failure, not the run's verdict.**
  `sys.exit()` in a hook is not an `Exception`, so it escaped the guard every other mistake in
  a hook goes through: `ddd check` ended with the code the hook named, printed none of the
  findings the run had already gathered, and the language server died with it - a hook exiting
  0 answered a run whose findings were already in the bag with a silent success.  A hook that
  exits is now reported exactly as one that raises: `ddd: plugin 'layout' failed in its check
  hook: SystemExit(0)`, exit 2, after the findings; the language server reports it as
  `plugin-invalid` and keeps serving the workspace.  `KeyboardInterrupt` is not caught and
  still interrupts.  The models a plugin declares are held to the same rule, because a
  validator on one of them is plugin code that runs on every `extensions` block DDD reads: a
  `ValueError` or an `AssertionError` from one is the block's finding, as it always was, but
  anything else it raises - and a `sys.exit` - is now `ddd: plugin 'layout' failed validating
  an 'extensions' block: SystemExit(9)`, exit 2, or `plugin-invalid` in the language server,
  instead of a pydantic traceback or a silent exit.  The server says so wherever it meets the
  failure: a project read only to find out whether it contains an opened file is reported at
  that project's description, and the file is still checked for what one file settles, so a
  broken plugin is never the unexplained reason a reader is given the thinner answer.
  **Migration:** a hook calling `sys.exit` used to end the run with its own code, which a build
  script could read as success; it is a usage error now.  A hook reports through the bag and
  returns, and a validator on a plugin's own model raises `ValueError` to refuse a block.

* **What a plugin's backend returns, and what a template raises, are usage errors.**  A
  `backend` hook returning `None` - the shape a hook that reads its settings and forgets to
  build one takes - or returning something that is not a backend crashed later, as
  `AttributeError: 'NoneType' object has no attribute 'name'`, out of a frame naming neither
  the plugin nor the hook; a `generate` returning a string was iterated over its characters
  before failing the same way.  Both are checked where they are returned now: a backend needs a
  `name` that is a string and a `generate` that is callable, and `generate` needs a list whose
  every entry carries a `Path` and a `str`, each failure one line naming the plugin and the
  hook it came from, exit 2.  A template raising what jinja does not wrap as an error of its
  own - `{{ 1 / 0 }}`, a filter handed the wrong type - escaped as a python traceback through a
  library the template's author never imported; it is now the one line every other template
  mistake already was, `ddd: cannot render template 'ddd_globals.c.jinja2', line 2: division by
  zero`.

* **A generation writes every file or none.**  Each file was written straight onto its target
  in turn, so a failure on the third - a target that is a directory, a permission problem, a
  full disk - left the first two replaced with the new render, the third as it was and the rest
  untouched: an output directory holding half of one run and half of another, which may not
  compile together, and nothing saying which file was which.  Every file's status is decided
  first, against the bytes on disk; each file that needs writing is then staged as a sibling
  `<name>.ddd-staging` - a suffix no artefact carries and nobody hand-writes, so a file of the
  reader's own sitting beside a target, `ddd_globals.c.tmp` say, is never staged over and then
  deleted - and only once all of them are staged is each renamed onto its target.  A
  failure removes the temporaries and the targets that run had created, and the `cannot write`
  line names the real target rather than the temporary that could not be moved onto it; a
  target the run had already updated keeps its new content, the bytes it held being gone once
  its own rename went through.  An unchanged file is still left alone and keeps its mtime, so a
  build that watches mtimes still skips what a rerun did not change.
  **Migration:** the rename is `os.replace`, which fails where writing straight onto the file
  used to go through.  On Windows, replacing a file another process holds open raises
  `PermissionError` instead of overwriting it, so a build that regenerates while a compiler or
  an editor holds a generated header open has to close it first; and where a target is one name
  of a hard link, the other name keeps the old bytes rather than seeing the update.

* **`ddd sources` says what it found beside what it listed.**  A missing include was silent in
  text mode: the command printed the listing, exited `0`, and dropped the `file-not-found` its
  loader had already recorded.  A hand-written build asking it for a dependency list therefore
  configured without a word about the mistake and met it later, from whichever DDD command the
  build ran next, rather than from the run that had already found it.  The findings now follow
  the listing on stderr, the way `--format json` has always carried them in its `diagnostics`
  and the way `ddd artefacts` already ended its own listing.  The exit code is untouched: `0`
  whatever the findings, `1` only when the root file cannot be read at all - the contract `ddd
  artefacts` has too, and the exit code table of the command line page names both commands now.
  **Migration:** a script reading `ddd sources` in text form sees findings on stderr that were
  not there before; stdout and the exit code are unchanged.  `--format json` is the parseable
  form, and has carried the same findings all along.

* **`ddd checks` says which checks a single component cannot answer.**  The listing marked a
  check whose severity cannot be relaxed `(fixed)` and said nothing else about any of them, so
  nothing the tool printed distinguished the checks `ddd check --standalone` holds back - the
  ones that need every component of the project - from the ones a single file settles, and a
  build writing a per-component target had to take that list from the documentation.  A check
  that needs the whole project is marked `(project)` now, one that grades a delivery comparison
  rather than a project `(comparison)`, beside the existing `(fixed)`; no check in the registry
  carries two today, and one that did would share a single parenthetical, `(fixed, project)`.
  Every entry of `--format json` carries the same two facts, as `needs_every_component` and
  `comparison`, beside the `overridable` it already had.
  **Migration:** a script parsing the text listing meets the new markers at the end of a line
  that used to end with the check's description, and `--format json` gained two keys.  Read the
  two booleans from the json form, which is the parseable one, rather than matching the markers.

* **Two declarations of one object whose enums disagree are one finding.**  A producer and a
  consumer stating the same enum with its enumerators in a different order, or with one of them
  on a different value, were reported twice: `enum-conflict`, which owns that disagreement and
  names the enumerators of both sides, and `definition-mismatch` as well, because the comparison
  of two declarations folded the enumerator table into the conversion it compares.  The second
  finding could not even say what differed - that comparison explains a conversion by naming it,
  so the message read `conversion: enum(Mode) != enum(Mode)`, the same text on both sides.  An
  enum is compared by its name there now: a reordering or a changed value is `enum-conflict`
  alone, and `-W enum-conflict=ignore` silences it outright where it used to leave
  `definition-mismatch` behind - the check being silenced is the one that owns the mistake -
  while two declarations naming different enums are the `definition-mismatch` they always were,
  `conversion: enum(OtherMode) != enum(Mode)`.  Identity and linear conversions are still
  compared in full, and the delivery comparison, which runs no `enum-conflict` of its own, still
  compares the enumerators itself - and still describes the difference as `enum(Mode) !=
  enum(Mode)` under `changed-interface`, because `EnumConversion.describe` names the enum and
  nothing else; that message is a known follow-up rather than part of this change.

## 0.8.0

* **Checking a component on its own.**  `ddd check --standalone` holds back the checks that
  need every component of a project, derived from the registry the way the language server
  derives them, and an explicit `-W` on the same run still wins.  The CMake module's
  per-component target uses it instead of naming two checks by hand, so a component that
  takes a type, a unit, a section, a constant or a raster from the project's vocabulary checks
  clean alone.  An empty address map is a first run rather than a map with holes: it raises no
  `address-missing`, so a strict two-run flow passes the seeded first build.
* **The published schemas accept what the loader accepts.**  An empty conversion, the
  enumerators of an enum as a `{"NAME": value}` mapping and a unit as a bare spelling were
  read by `ddd check` and refused by the schemas `ddd schema` publishes, so an editor bound to
  them underlined every recommended shorthand; the conversion union is published as `anyOf`
  and the two shorthands beside their object forms.  The example projects carry identities,
  and the tests re-run every command the documentation shows over them.
* **Quick fixes follow the checker on `limits`.**  A declaration that leaves the limits out
  defers to the one that states them, which `definition-mismatch` counts as agreement; the
  editor no longer offers to spread or strip a range in that case, and only two stated ranges
  that differ are offered a fix.

* **Fixes from a whole-project review.**  A section name is spelled with letters, digits,
  `.`, `_` and `$`, since the generated C writes it into a string literal; an enumerator
  value, a raster event and a section alignment are integers rather than quoted numbers, as
  the published schemas already said; a raster `cycle` is matched whole.  Findings at one
  place are listed in the order they were reported, so `reused-name` precedes the removal
  it explains; a plain object's consumers are sorted, as the dictionary documents; a spelled
  dimension has to agree with the numeric one in an archived dictionary.  `ddd id --assign`
  fills an explicit `"id": null` and keeps each line's own ending.  In `--renames`, a member
  of a renamed structured variable is listed under the instance's id followed by its member
  path.  A baseline is analysed without `--strict` and the comparison runs on whatever
  resolved.  The a2l keeps one `COMPU_METHOD` per display format, caps every synthesised
  identifier at 128 characters, leaves out a curve whose axis is unknown rather than writing
  it incomplete, and `a2l-unrepresentable` follows the file's own export closure; a
  structure member's enumerators and limits are held to its storage like a declaration's.
  The language server survives a plugin that raises during a hover, keeps its wire clean of
  whatever a plugin prints, refuses a negative `Content-Length`, matches a symlinked
  document to its build, keeps every workspace folder, and keeps the host of a `file://`
  uri.  The CMake module passes the a2l options only when the a2l is generated.  A plugin
  cannot be named `c`, `a2l` or `all`, and two plugin files whose paths differ only in
  punctuation are two plugins.  The example plugin reports a key claimed twice in an
  archived baseline and honours an object's condition in the header it writes.

* **Plugins.**  A project names python modules under `plugins`, each owning an `extensions`
  block on a definition and on the project that DDD validates against the plugin's own
  pydantic model, carries into the dictionary in resolved form and never interprets.  A plugin
  contributes checks, reported and policed like the built-in ones under identifiers spelled
  `<plugin>/<check>`; comparison rules, run after the built-in comparison; and an artefact,
  selected as `ddd generate <name>`.  Five built-in checks arrive with it: `plugin-not-found`
  and `plugin-invalid`, with a fixed severity, `unknown-extension`, `consumer-extension`,
  and `missing-plugin`, which says when a compared dictionary was produced with a plugin the
  run has not loaded.  `ddd schema --plugin` publishes a schema closed over a project's
  plugins, `ddd compare --plugin` loads them for an archived candidate, and
  `ddd checks --plugin` lists their checks.  `examples/plugins/ddd_layout.py` is a worked
  example.  **Migration:** none for an existing project - no key is required and nothing is
  stamped.  The dictionary format moves from 6 to 7: every object, every instance and the
  dictionary itself carry `extensions`, and the dictionary records `plugins`; a dictionary
  dumped by an older DDD reads back with all of them empty.
* **`id` on a producing declaration: the identity of a data object, which survives a
  rename.**  Twelve lowercase base32 characters, opaque, written by `ddd id --assign` rather
  than typed by hand.  `duplicate-id` refuses two objects of one project sharing one, and
  `consumer-identity` refuses it on an `input` declaration, the same reasoning that already
  refuses `init` and `section` there; `missing-id` reports a producing declaration that states
  none, at `info`, so an unmigrated project sees it without being held to it.  `ddd compare`
  now pairs objects on the id before falling back to the name, so a rename is one
  `renamed-object` finding with the ordinary interface comparison still run across it, rather
  than a removal and an addition that never meet; a name freed by a rename and claimed by a
  different object is `reused-name`, an error, because a calibration dataset or a recording
  keyed by that spelling binds to the new object exactly as readily as it did to the old one.
  **Migration:** the dictionary format is 6, and every object of a freshly dumped dictionary
  now carries `id`, `null` where nothing was stamped, exactly like `section` or `raster`; a
  leaf of a structured object carries the same thing under `instance_id`.  Run
  `ddd id --assign` over the description files once and commit the result; until then
  `missing-id` reports at info, which a migrated project turns into its gate with
  `-W missing-id=error`.  A baseline archived at format 5 or older carries neither key at all,
  which is not the same as having none stated - its objects pair by name and no rename is ever
  inferred against it.
* **`ddd id --assign FILE...`** writes an id into every producing declaration and instance
  that has none, editing the files in place; a declaration that already carries one is left
  alone, so a second run changes nothing.
* **`ddd compare --renames PATH`** writes the old-to-new name pairs of the comparison - each
  object's id, its old name and its new name - so a calibration dataset, a recording or a test
  script keyed by the old spelling can be migrated without parsing the comparison's own
  findings.

## 0.7.0

* **Seventh description file kind: measurement rasters.**  A `rasters` file names the DAQ
  events a target's XCP configuration offers - a short name, an event channel number and,
  optionally, a cyclic period - and a definition or its producing component names the one a
  measurement is updated in, resolved exactly like a memory section: the declaration's own
  `raster`, else its component's default, else nothing.  Five checks keep the vocabulary
  honest: `duplicate-raster` and `duplicate-event` catch two rasters sharing a name or an
  event channel, `unknown-raster` catches naming one nothing declares, `consumer-raster`
  catches an `input` declaration claiming an event it does not own, and `raster-kind` catches
  one stated on a calibration object, which no DAQ list ever carries.  An exported measurement
  with a raster now reaches the generated a2l with an `IF_DATA XCP` block naming its event
  channel, so a calibration tool preselects the right one instead of an engineer guessing
  which task moves the signal.  **Migration:** none for existing description files - a
  measurement naming no raster, whose component names none either, reaches the a2l exactly as
  before.  The archived dictionary format moves from 4 to 5; a dictionary dumped by an older
  DDD still reads back, with every object's raster resolving to `null`.
* **The documentation deployment reads back what it published.**  The archive branch is a git
  push and the site is an artifact handed to Pages, and nothing made the two agree: 0.6.0
  reached `gh-pages` with a version index naming it while the site went on serving a build
  assembled before the release existed - a complete set of documentation at a url that
  answered 404, offered by no menu, with every step of every job reporting success.  The
  deploy job now ends by fetching the published `versions.json` and the directory it just
  wrote, and fails if the site is not serving them.  Re-running the workflow republishes the
  archive branch as it stands, which is the fix when it does fail.
* **The editor extension is no longer published to the Visual Studio Marketplace.**  It never
  was: the step needed a personal access token from an Azure DevOps organisation owning a
  `sauci` publisher, neither was ever created, and it failed on every release it ran on while
  the rest of the pipeline reported success around it - with four pages meanwhile telling a
  customer to search the Extensions view for an item that answers 404.
  **Migration:** install the `ddd-<version>.vsix` attached to the
  [GitHub release](https://github.com/Sauci/ddd/releases), which is what every page now says
  and what the release has always carried.  Building, testing, packaging and attaching the
  extension are unchanged; only the marketplace upload is gone.

## 0.6.0

* **The docker development image builds and its services run again.**  `docker/Dockerfile`
  still copied a `completion` directory that was removed before 0.5.0, so `docker compose
  build` failed on the first `COPY` and every service with it; and the `generate` service
  still used the pre-artefact command line, so it exited with a usage error.  Both are the
  local equivalents of ci jobs, which is where the breakage stayed invisible: ci installs the
  package itself and never builds this image.
* **A structure kept out of the a2l is now a change `ddd compare` can see.**  The export
  decision of a structured variable reaches its members: the resolved dictionary records on
  each leaf what the variable's `a2l.export` and the member's own together come to, where it
  used to record only the member's half and leave the a2l backend to put the two together at
  render time.  Everything else read one half and believed it, so a delivery that stopped
  exporting a structure compared clean against its predecessor while every one of its members
  left the file.  The comparison now reports one `changed-a2l` per member.
  **Migration:** none for the description files.  A dictionary dumped by 0.5.0 states the
  member's half alone; compared against a new one, the leaves of a variable that was never
  exported report `changed-a2l` once, on the delivery that re-dumps them.
* **New check `address-missing` (warning).**  An object the a2l carries with no entry in the
  `--address-map` the run was given is now reported instead of silently written at address
  zero.  It fires only when a map is supplied - without one every address is zero by
  construction, which is the run a build makes before it has linked anything.  The entries of
  the map that match no object are named in a note, because a renamed object usually loses
  its address and leaves its old spelling behind in the same file.  `--strict` makes it fatal,
  which is what a post-link build wants.
* **New check `incomplete-project` (info).**  Relaxing a check that *drops* a declaration -
  `unknown-type`, `unknown-constant`, `type-kind` - never put the variable back; it only hid
  why it went.  With the cause silenced, `ddd list` printed a table one row short and exited
  zero and `ddd dump` archived a dictionary an object was missing from, with nothing said.
  The consequence is now reported when its cause is not.  Like the other checks that need the
  whole project to be right about anything, it stays quiet for a file the language server
  reads on its own.
* **The language server survives a badly shaped message, and reads a byte order mark.**  A
  correctly framed request missing the `params` an editor always sends used to raise out of
  the loop and end the session; it is now refused with json-rpc `InvalidParams` (-32602) and
  the conversation goes on.  Description files are read as `utf-8-sig`, the encoding the
  loader has always used: read as plain utf-8 a file carrying a byte order mark - what several
  Windows editors and PowerShell redirection write - did not parse, so every finding collapsed
  onto the first character and hover, go to definition, rename and the code actions all
  answered nothing, on a file `ddd check` called perfectly good.  A `file://` uri is no longer
  unescaped twice, which made `a%20b.ddd.json` name `a b.ddd.json`.
* **The language server reads the project once per save rather than once per keypress.**  The
  build records and the loaded projects are kept between requests and dropped at every open,
  save and rename.  A hover used to walk every configured build directory looking for
  `ddd-build.json` and then re-read and re-validate every description file of every image the
  component is linked into, twice over.
* **`ddd generate` names its artefact: `c`, `a2l` or `all`.**  The artefact is part of the
  command and each carries only the options of what it produces: `-t/--template-dir`
  (required) and `--const-inputs` exist on `c` and `all`, `--byte-order` and
  `--address-map` on `a2l` and `all`.  `ddd generate a2l` is the second run of a build
  stated as such: the first run generates the c the image is built from, the linker decides
  the addresses, and the second writes only the a2l with `--address-map` carrying them -
  instead of re-rendering every source and reporting each unchanged.
  **Migration:** `ddd generate PROJECT ...` becomes `ddd generate all PROJECT ...`, and
  `--no-a2l` becomes the `c` artefact.  `ddd_generate()` in the CMake integration emits the
  new form itself; a build calling the tool directly changes its command lines.
* **The generated definition file is compiled with the full interface compile usage of the
  registered components.**  In the collected mode, `ddd_generate()` used to hand
  `<image>_ddd_globals` only the *include directories* of the registered components; it now
  forwards their interface compile definitions and compile options as well, resolved through
  each component's public link closure, still without creating any link edge.  Includes
  alone were a trap: a hand written header named by an external type may change its layout
  under the component's interface defines, and the definition file then found every header,
  compiled cleanly, and laid the variables out differently than the image using them.
  A `LINK_LIBRARIES` entry that only re-stated a registered component's own usage can be
  dropped; the option remains for the hand written `PROJECT` mode and for what no
  description implies, such as a header the project's own c templates include.
* **The c views spell types in the description's vocabulary too, and boolean initialisers
  need no header.**  Every view offering `c_type` (the ISO spelling, `uint16_t`) now offers
  `datatype` beside it - the type as the description spells it: `uint16`, `boolean`, or the
  declared name of a structure or external type.  A platform whose header already provides
  those names (AUTOSAR's `Platform_Types.h` spells them exactly) renders `datatype` and
  drops the per-template mapping tables.  A `boolean` initial value is now emitted as `1`/`0`
  rather than `true`/`false`: the words need `<stdbool.h>` before C23 and do not exist on
  AUTOSAR platforms at all, while the numerals mean the same thing everywhere - and the
  initialiser is the one c fragment a template cannot respell.

## 0.5.0

Initial release.

DDD describes the global variables of a component based embedded software project in json
description files, checks that every component agrees on them, and generates the artefacts a
build and a calibration tool consume.

* **Six description file kinds.**  A *project* file names the components and the shared
  vocabularies of an image; a *component* file declares that component's data interface -
  measurements, parameters, curves, maps, axes and value blocks, each stating its `kind`,
  its storage (`datatype` or `typename`), its `conversion` and its `volatile` qualifier
  explicitly - and may declare the types and constants it publishes inline, entries exactly
  those of the standalone files and names in the same project wide namespace; a *types*
  file declares scalar types, structures and external types a project shares by name, an
  external type naming a c type a hand written header defines, carried verbatim by a
  structure member and included by the generated types header;
  a *units* file pins the unit spellings a project allows; a *sections* file declares the
  linker sections a definition may place its object in; a *constants* file declares the
  named integer constants a shape may state instead of a number, carried into the generated
  c by name and into the a2l as `SYSTEM_CONSTANT`s.  Every format is published as a json
  schema (`ddd schema component|constants|dictionary|project|sections|types|units|all`).
* **Consistency checks with stable identifiers.**  `ddd check` verifies the description as
  a whole - one producer per variable, agreeing declarations, resolvable types, units,
  sections and constants, representability in the a2l - and reports each finding under a
  stable check id with a default severity a project can raise, lower or silence per check (`-W`,
  `SEVERITY` in CMake).  `ddd checks` lists them all.
* **C generation from project owned templates.**  `ddd generate` renders the jinja2
  templates of the project - DDD ships a working example set behind `ddd templates-dir`,
  never a built in fallback - producing the variable definitions, per component `extern`
  headers and the types header.
* **A2L generation** following ASAM MCD-2 MC (ASAP2) 1.6.1, structures flattened into one
  record per member, with `--address-map` supplying the addresses a build reports.
* **Deliveries.**  `ddd dump` archives the resolved dictionary (format 4) and
  `ddd compare` reports whether one delivery can replace another; against a baseline from
  format 3 or older, which recorded no dimension spellings, dimensions compare by value.
* **CMake integration.**  `cmake/Ddd.cmake` (behind `ddd cmake-dir`) provides
  `ddd_add_component()` and `ddd_generate()`, collecting the project from the c link graph
  or taking an explicit `PROJECT`, wiring the checks into the build and recording the
  build's configuration in a `ddd-build.json` for editors to pick up (`ddd build-info`).
* **Editor support.**  `ddd lsp` is a language server that reports the checks while a file
  is written, navigates between the components that share a variable, and renames across a
  project; `editors/vscode` holds the VS Code extension that launches it.

The requirements are stated in [`SPEC.md`](SPEC.md), the authoritative contract for the
behaviour of the tool.
