# Ddd.cmake
#
# CMake integration of the DDD data dictionary. It provides two functions:
#
# * ddd_add_component(<target> JSON <file>...): registers the DDD description(s) of a component on its target, and
#   creates the on-demand <target>.ddd target checking that component on its own.
# * ddd_generate(<image> ...): collects the descriptions of all components in the link closure of the given image,
#   generates the global definition file, the per-component interface headers and the a2l, writes the resolved data
#   dictionary beside them, and links the result into the image. With ADDRESSES_FROM_IMAGE or ADDRESS_MAP the a2l is
#   written after the link instead, every address it carries read out of the linked image, or out of the map a step
#   of the project's extracts from it.
#
# The collection relies on the custom transitive property DDD_JSON, introduced with the TRANSITIVE_LINK_PROPERTIES
# feature of CMake 3.30: the description files travel through the link graph like usage requirements, so an image
# collects exactly the components it actually links - no more, no less. Only the collecting mode needs 3.30; passing
# a ready made project description with PROJECT works on older CMake as well.
#
# Typical use:
#
#   list(APPEND CMAKE_MODULE_PATH "/path/to/ddd/cmake")   # or: ddd cmake-dir
#   include(Ddd)
#
#   add_library(sensor_hub STATIC sensor_hub.c)
#   ddd_add_component(sensor_hub JSON sensor_hub.ddd.json)
#
#   add_executable(firmware main.c)
#   target_link_libraries(firmware PRIVATE sensor_hub)
#   ddd_generate(firmware)
#
# Any single-config generator does: Ninja, or a Makefile generator.

# The module itself needs CMake 3.20: it relies on cmake_path() and string(JSON) throughout. Checked at include
# time, because an older CMake would otherwise fail on whichever of those commands it reaches first, with a message
# that names the command rather than the actual floor. Collecting descriptions through the link graph needs 3.30 on
# top of this - see _ddd_require_transitive_properties below.
if(CMAKE_VERSION VERSION_LESS 3.20)
    message(FATAL_ERROR "Ddd.cmake requires CMake 3.20 or newer (found ${CMAKE_VERSION}): it relies on cmake_path() "
                        "and string(JSON).")
endif()

# The tool itself. Set -DDDD_EXECUTABLE=<path> to use a specific installation, for example the one of a virtual
# environment, or a wrapper script running "python -m ddd".
find_program(DDD_EXECUTABLE NAMES ddd DOC "The ddd data dictionary tool")

# The release this module belongs to, spelled the way "ddd --version" spells it. Bumped with every other place the
# release states its version; tests/test_documentation.py compares it with the package's own.
set(DDD_MODULE_VERSION "0.11.0")

# The module and the tool it drives have to be one release. "ddd cmake-dir" and the header above invite a project to
# copy this file into its own tree, where it then sits beside whichever ddd the environment happens to have - and the
# two drift apart silently: every option this module passes is checked by argparse at *build* time, so a module newer
# than its tool configures cleanly and then fails on "unrecognized arguments: --dictionary", which names the option
# and not the mismatch behind it, while a module older than its tool builds happily with the option set of a release
# nobody is running. Asked at include time, because it is a property of the pair rather than of anything a call says.
#
# And asked at every include, so at every configure, keeping no answer: the release answering at a path can change
# while the path stays - "pip install -U" into the environment DDD_EXECUTABLE names, or an editable install whose
# checkout moved on - and an answer the cache kept by the path skipped the question there, the one case it exists for,
# until a fresh build tree asked it. "ddd --version" answers without loading the rest of the tool, so the question
# costs next to nothing.
#
# Tolerant where it cannot tell - a tool that does not answer --version at all is broken in a way the next
# execute_process() will say more about - and fatal where it can: a mismatch is a build that fails later, with less
# to go on.
function(_ddd_verify_tool_version)
    execute_process(COMMAND "${DDD_EXECUTABLE}" --version
                    OUTPUT_VARIABLE output
                    RESULT_VARIABLE status
                    ERROR_VARIABLE error
                    OUTPUT_STRIP_TRAILING_WHITESPACE
                    ERROR_STRIP_TRAILING_WHITESPACE)
    if(NOT status EQUAL 0 OR NOT output MATCHES "ddd +([^ \t\r\n]+)")
        message(WARNING "Ddd.cmake: cannot tell which release \"${DDD_EXECUTABLE}\" is (${status}): "
                        "${error}${output}")
        return()
    endif()
    set(found "${CMAKE_MATCH_1}")
    # Spelled rather than compared as versions: a prerelease ("0.10.0rc1") is not a CMake version, and VERSION_EQUAL
    # would read it as the release it precedes.
    if(NOT found STREQUAL DDD_MODULE_VERSION)
        message(FATAL_ERROR "Ddd.cmake is ${DDD_MODULE_VERSION} and \"${DDD_EXECUTABLE}\" is ddd ${found}. The "
                            "module and the tool are one release: this pair configures cleanly and fails at build "
                            "time, on an option one of the two does not know. Point DDD_EXECUTABLE at the ddd of "
                            "this release, or include the Ddd.cmake that ships with the tool - \"ddd cmake-dir\" "
                            "prints the directory it is in.")
    endif()
endfunction()

if(DDD_EXECUTABLE)
    _ddd_verify_tool_version()
endif()

# A keyword whose value expanded to nothing - ddd_generate(... ADDRESS_MAP ${DDD_MAP}) with DDD_MAP unset or empty,
# the ordinary CMake mistake - reads to cmake_parse_arguments() as a keyword that was never given at all, and every
# check below is written as if(arg_X), which cannot tell the two apart. Dropped in silence, each one changes what the
# call does: ADDRESS_MAP writes the a2l before the link, with every ECU_ADDRESS 0x00000000, and adds no step reading
# the map after it; PROJECT falls into the collected mode and generates out of the link closure instead of out of the
# file the caller named. Refused here, once, for both functions.
#
# The bare form is what KEYWORDS_MISSING_VALUES names. The quoted form, ADDRESS_MAP "${DDD_MAP}", which every recipe
# writes, is a value to PARSE_ARGV - an empty string - and is named by nothing it reports, so the arguments are walked
# here: a keyword that takes a value, followed by an empty argument. It is a macro because ARGV<n> belongs to the function that was called,
# not to a helper; it reads them by number, up to the count its caller hands it (ARGV<n> beyond it may be an outer
# function's), and works from CMake 3.20 on. Only the argument right after a keyword says whether the keyword was given:
# an empty one after a value leaves the keyword its values, and each caller drops it from them.
# A macro, so its locals - each spelled _ddd_<name> - are set in the scope of the function calling it.
macro(_ddd_refuse_empty_keywords context argument_count keywords)
    set(_ddd_keywords "${keywords}")
    set(_ddd_empty ${arg_KEYWORDS_MISSING_VALUES})
    set(_ddd_index 1)
    while(_ddd_index LESS ${argument_count})
        math(EXPR _ddd_next "${_ddd_index} + 1")
        if(_ddd_next LESS ${argument_count})
            if("${ARGV${_ddd_index}}" IN_LIST _ddd_keywords AND "${ARGV${_ddd_next}}" STREQUAL "")
                list(APPEND _ddd_empty "${ARGV${_ddd_index}}")
            endif()
        endif()
        set(_ddd_index ${_ddd_next})
    endwhile()
    list(REMOVE_DUPLICATES _ddd_empty)
    if(_ddd_empty)
        list(JOIN _ddd_empty "\", \"" _ddd_spelled)
        message(FATAL_ERROR "${context}: \"${_ddd_spelled}\" was given no value. A variable that expands to nothing "
                            "leaves the keyword with no argument, which reads exactly like a keyword that was "
                            "never given - so the call would quietly have done something else. Give it a value, "
                            "or leave the keyword out.")
    endif()
endmacro()

# A path spelled as the pattern file(GLOB) matches that path with, and nothing else: the glob reads "[", "*" and "?" as
# pattern syntax wherever they are, so a checkout in "pr[1]" would have its own directory read as a character class.
function(_ddd_literal_pattern variable path)
    string(REGEX REPLACE "([[*?])" "[\\1]" literal "${path}")
    set(${variable} "${literal}" PARENT_SCOPE)
endfunction()

# Has the build configure again, before it does anything else, once a file appears where there is none now, or goes
# where there is one: a glob of its own path with CONFIGURE_DEPENDS, which every build checks first. The configure
# dependencies cannot do it, CMake taking none on a file in the build tree, and none on a file that does not exist.
function(_ddd_watch_file path)
    _ddd_literal_pattern(literal "${path}")
    file(GLOB ignored CONFIGURE_DEPENDS "${literal}")
endfunction()

# The transitive property feature is only needed when the component descriptions are collected through the link
# graph; a caller passing PROJECT never reaches this check.
function(_ddd_require_transitive_properties context)
    if(CMAKE_VERSION VERSION_LESS 3.30)
        message(FATAL_ERROR
                "${context}: collecting the DDD descriptions through the link graph requires CMake 3.30 or newer "
                "(found ${CMAKE_VERSION}): it relies on the TRANSITIVE_LINK_PROPERTIES feature. An older CMake would "
                "silently collect an incomplete set of components. Pass a ready made project description with "
                "PROJECT to ddd_generate() instead.")
    endif()
endfunction()

# Watches the "includes" wildcards of a project description, so that a file one starts or stops matching is noticed.
# The files "ddd sources" lists are dependencies of the configure, which is a watch over the files there were when it
# ran: one created later is not among them, and one deleted only leaves the generation with fewer inputs and the same
# command. Each include is therefore globbed with CONFIGURE_DEPENDS, as the templates are, and the build looks at it again before it does
# anything else, re-running configure when the files found differ. The result is not used: the tool is the one that
# resolves the includes. A pattern with "**" is watched at every depth of the directory before its first wildcard, by
# its last segment - more than it matches, so a file added anywhere below that directory runs configure, and every
# build scans the whole tree below it, which an include of a large tree should keep in mind.
#
# A relative include is the tool's to read from the directory of the file naming it, whatever characters that
# directory has, so those of the directory are escaped before the include is joined to it: a checkout in "proj [v2]"
# is no character class. An absolute include is read whole as a pattern, by the tool as here. Tolerant like the call
# asking for the list: a file that is missing - the tool lists an include that does not exist, and says so - or is no
# project, or whose "includes" is no list, has nothing to watch, and is no reason to refuse to configure.
function(_ddd_watch_includes description)
    if(NOT EXISTS "${description}" OR IS_DIRECTORY "${description}")
        return()
    endif()
    file(READ "${description}" content)
    string(JSON kind ERROR_VARIABLE error TYPE "${content}" "project" "includes")
    if(error OR NOT kind STREQUAL "ARRAY")
        return()
    endif()
    string(JSON count LENGTH "${content}" "project" "includes")
    if(count EQUAL 0)
        return()
    endif()
    cmake_path(GET description PARENT_PATH base)
    _ddd_literal_pattern(literal_base "${base}")
    math(EXPR last "${count} - 1")
    foreach(index RANGE 0 ${last})
        string(JSON entry GET "${content}" "project" "includes" ${index})
        if(WIN32)
            string(REPLACE "\\" "/" entry "${entry}")
        endif()
        cmake_path(HAS_ROOT_NAME entry rooted)
        cmake_path(HAS_ROOT_DIRECTORY entry has_root_directory)
        if(rooted OR has_root_directory)
            set(where "")
        else()
            set(where "${literal_base}/")
        endif()
        if(entry MATCHES "\\*\\*")
            string(REGEX MATCH "^[^*?[]*/" directory "${entry}")
            string(REGEX REPLACE "^.*/" "" final "${entry}")
            file(GLOB_RECURSE ignored CONFIGURE_DEPENDS "${where}${directory}${final}")
        else()
            file(GLOB ignored CONFIGURE_DEPENDS "${where}${entry}")
        endif()
    endforeach()
endfunction()

# Keeps the list of files a project is made of in the build tree, and rewrites it only when it differs: the generation
# depends on it, so that a list that changed - a file added to a wildcard, or one removed from it, which leaves every
# other input of the generation and its command line as they were - runs it again, and one that did not leaves the
# build with nothing to do.
function(_ddd_write_source_list file sources)
    string(REPLACE ";" "\n" listed "${sources}")
    set(current "")
    if(EXISTS "${file}")
        file(READ "${file}" current)
    endif()
    if(NOT "${current}" STREQUAL "${listed}\n")
        file(WRITE "${file}" "${listed}\n")
    endif()
endfunction()

# Asks the tool which files a project description is built out of. A hand written project pulls its components in
# through "includes" - possibly with wildcards - so the project file alone is a wholly insufficient dependency: edit a
# component and the build would happily link yesterday's globals and a2l. The list is resolved at configure time and
# registered with CMAKE_CONFIGURE_DEPENDS, so that an edit of any of the files re-runs configure; the wildcards
# themselves are globbed with CONFIGURE_DEPENDS (_ddd_watch_includes), which is what notices a file starting or
# stopping to match, and the list is kept in the build tree for the generation to depend on (_ddd_write_source_list).
#
# Tolerant on purpose, and never silent: what the tool lists is what the project names, whether or not it could be read
# - a plugin that stopped importing is listed, and so is one whose model raises - so that the edit repairing it re-runs
# configure. What it has to say about the project (stderr: a plugin that does not import, an include that is missing) is
# printed as a warning, graded by the build's SEVERITY and STRICT, the configure being the one place that reaches a
# developer before the build does. The file exists and parses by now (ddd_generate refuses it otherwise); if the tool
# cannot resolve it all the same - a root failing its schema - or cannot be run, the result is empty, a warning says
# so, and the build falls back to depending on the project file alone, as a configure dependency, rather than failing
# to configure at all.
function(_ddd_project_sources variable project_file)
    # The rest of the arguments are the severity policy of the build (-W, --strict): what the tool says about the
    # project is graded as the build grades it, so that a check the build relaxed is not warned of at every configure.
    execute_process(COMMAND "${DDD_EXECUTABLE}" sources "${project_file}" ${ARGN}
                    OUTPUT_VARIABLE output
                    RESULT_VARIABLE status
                    ERROR_VARIABLE error
                    OUTPUT_STRIP_TRAILING_WHITESPACE
                    ERROR_STRIP_TRAILING_WHITESPACE
                    ENCODING UTF-8)
    if(NOT status EQUAL 0)
        message(WARNING "ddd_generate: cannot resolve the sources of \"${project_file}\" (${error}); the "
                        "generation will depend on that file alone.")
        # The file stays a dependency of the configure, so that its repair is what runs it again.
        set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${project_file}")
        set(${variable} "" PARENT_SCOPE)
        return()
    endif()
    if(NOT "${error}" STREQUAL "")
        message(WARNING "ddd_generate: \"ddd sources ${project_file}\" reported:\n${error}")
    endif()
    string(REPLACE "\r" "" output "${output}")
    string(REPLACE "\n" ";" sources "${output}")
    list(REMOVE_ITEM sources "")
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${sources})
    # Every file listed that is a project, the root and the sub-projects it includes, has wildcards of its own.
    foreach(source IN LISTS sources)
        string(TOLOWER "${source}" spelled)
        if(spelled MATCHES "\\.json$")
            _ddd_watch_includes("${source}")
        endif()
    endforeach()
    set(${variable} "${sources}" PARENT_SCOPE)
endfunction()

# Writes the json schemas of the description file formats into a directory of the project's choosing, at configure
# time, so that an editor can validate a *.ddd.json while it is being written. The project decides where they go and
# points the "$schema" key of each description at the matching file - the same division as everywhere else here: DDD
# owns what the data means, the project owns where things live.
#
# Configure time rather than build time on purpose: the schemas describe the *installed* DDD, so regenerating them
# whenever the build is configured is what keeps them from describing a version that is no longer there. The flip side
# is that they only exist once the project has been configured at least once, which is why a project whose developers
# expect editor support straight after cloning commits them instead and runs "ddd schema all -o <dir>" by hand after
# an upgrade. Both are supported; SCHEMA_DIRECTORY is the choice that cannot go stale.
function(_ddd_write_schemas directory plugins)
    cmake_path(ABSOLUTE_PATH directory BASE_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}" NORMALIZE)
    # Closed over the project's plugins, so that an editor validates a plugin's block as it is typed; a path spec
    # reaches the tool absolute, so the working directory of the configure step does not matter.
    set(plugin_arguments "")
    foreach(spec IN LISTS plugins)
        list(APPEND plugin_arguments --plugin "${spec}")
    endforeach()
    execute_process(COMMAND "${DDD_EXECUTABLE}" schema all --output "${directory}" ${plugin_arguments}
                    RESULT_VARIABLE status
                    ERROR_VARIABLE error
                    OUTPUT_QUIET)
    if(NOT status EQUAL 0)
        # status carries the reason when the tool could not be started at all, in which case
        # stderr is empty and the message would otherwise say nothing.
        message(FATAL_ERROR "ddd_generate: cannot write the json schemas into \"${directory}\" "
                            "using \"${DDD_EXECUTABLE}\" (${status}): ${error}")
    endif()
    message(STATUS "ddd_generate: wrote the json schemas into \"${directory}\".")
endfunction()

# Records how this build runs DDD - the project description in use and the severity policy applied to it - next to the
# generated sources, so that an editor can report what the build reports. Neither is discoverable from the description
# files: without PROJECT the project description is written into the build directory out of the link closure, so which
# components belong together is a property of this build and nothing in the source tree names it at all.
#
# The same bargain as SCHEMA_DIRECTORY above: nothing in the build consumes this file, it exists so that a tool
# outside the build can see what the build sees. "options" is the very list handed to "check" and "generate", so the
# three cannot drift into applying different severities.
#
# Configure time, and the project description is named rather than read - without PROJECT it is produced by
# file(GENERATE) at the end of this configure run, so it does not exist yet while this executes.
function(_ddd_write_build_info directory image project_file options)
    execute_process(COMMAND "${DDD_EXECUTABLE}" build-info "${project_file}"
                            --output "${directory}/ddd-build.json" --image "${image}" ${options}
                    RESULT_VARIABLE status
                    ERROR_VARIABLE error
                    OUTPUT_QUIET)
    # Fatal rather than tolerant, unlike _ddd_project_sources: this reads nothing that might not be ready yet, so a
    # failure means either that the tool is broken or that SEVERITY names a check that does not exist - and the
    # second would fail the build a moment later anyway, with less to go on.
    if(NOT status EQUAL 0)
        message(FATAL_ERROR "ddd_generate: cannot record the build information in \"${directory}\" "
                            "using \"${DDD_EXECUTABLE}\" (${status}): ${error}")
    endif()
endfunction()

# The a2l is named after the project name *inside* the description, which is not necessarily what NAME says. Reading it
# here keeps the declared OUTPUT and the file the tool actually writes in agreement - otherwise the build re-runs the
# generator on every ninja invocation and DDD_A2L points at a file that never appears.
function(_ddd_description_name variable description)
    file(READ "${description}" content)
    string(JSON name ERROR_VARIABLE error GET "${content}" "project" "name")
    if(error)
        string(JSON name ERROR_VARIABLE error GET "${content}" "component" "name")
    endif()
    if(error)
        message(FATAL_ERROR "ddd_generate: \"${description}\" has neither a project nor a component name: ${error}")
    endif()
    set(${variable} "${name}" PARENT_SCOPE)
endfunction()

# Whether a description file's top level key is "component". The per-component check target may only run "ddd check"
# on component files: a vocabulary file - types, units, sections, constants or rasters - has no interfaces of its
# own, and handing one to "check" is an unrelaxable file-kind error that would break the <target>.ddd target for
# good. Such files still register on the target and are checked in context, through the project of every image that
# links the component.
#
# A file that does not exist yet - one the build writes into the build tree - says nothing about its kind either, and
# is taken to be a component until the configure that finds it reads what it is: the first build to find it there runs
# that configure by itself (ddd_add_component watches the file), so a vocabulary the build writes is checked in context
# from then on, and only a target built before the file is there checks it as a component - which it cannot pass.
#
# So is a file whose json does not parse at all, which is a different answer from "this is not a component": the file
# says nothing about its kind, and the reading it has to be told about is exactly what "ddd check" says. Answering
# FALSE dropped it from the target, so ninja reported "no work to do" over a file that does not parse and went on
# doing so - the target is built at configure time - until somebody configured again, which is not what a developer
# does after fixing a typo in a description.
function(_ddd_is_component_file variable description)
    if(NOT EXISTS "${description}")
        set(${variable} TRUE PARENT_SCOPE)
        return()
    endif()
    file(READ "${description}" content)
    string(JSON kind ERROR_VARIABLE unreadable TYPE "${content}")
    if(unreadable)
        set(${variable} TRUE PARENT_SCOPE)
        return()
    endif()
    string(JSON unused ERROR_VARIABLE error GET "${content}" "component")
    if(error)
        set(${variable} FALSE PARENT_SCOPE)
    else()
        set(${variable} TRUE PARENT_SCOPE)
    endif()
endfunction()

# The name a component description gives its component, read at configure time, or an empty string where none can be
# read: a vocabulary file has none, and neither has a file that does not exist yet or does not parse. A {component}
# template renders one file per component under this name, which is how the generation can declare those files at all
# (see ddd_generate).
function(_ddd_component_name variable description)
    set(name "")
    if(EXISTS "${description}")
        file(READ "${description}" content)
        string(JSON name ERROR_VARIABLE error GET "${content}" "component" "name")
        if(error)
            set(name "")
        endif()
    endif()
    set(${variable} "${name}" PARENT_SCOPE)
endfunction()

# Turns a path into an absolute one and refuses a source file that does not exist. A file below the binary directory
# is accepted unconditionally: it may well be generated later during the build. A project description is not taken
# so, being read when the build is configured (ddd_generate).
function(_ddd_absolute_input variable base context)
    set(path "${${variable}}")
    cmake_path(ABSOLUTE_PATH path BASE_DIRECTORY "${base}" NORMALIZE)
    cmake_path(IS_PREFIX CMAKE_BINARY_DIR "${path}" NORMALIZE path_is_generated)
    if(NOT path_is_generated AND NOT EXISTS "${path}")
        message(FATAL_ERROR "${context}: the file \"${path}\" does not exist.")
    endif()
    set(${variable} "${path}" PARENT_SCOPE)
endfunction()

# Refuses a description whose top level key is "project". ddd_add_component() registers components and vocabulary files,
# whose includes nothing follows: a project file registered here is collected into the generation, but only the file
# itself is a dependency, so an edit to what it includes - or to a plugin it names - builds to "no work to do" over
# generated sources that no longer match the project. PROJECT of ddd_generate() is where a project file goes. A file
# that does not exist yet or does not parse says nothing about its kind, and passes.
function(_ddd_refuse_project_file target description)
    if(NOT EXISTS "${description}")
        return()
    endif()
    file(READ "${description}" content)
    string(JSON unused ERROR_VARIABLE absent GET "${content}" "project")
    if(NOT absent)
        message(FATAL_ERROR "ddd_add_component: \"${description}\" registered on target \"${target}\" describes a "
                            "project, and a component is not one. Name a project file with PROJECT of "
                            "ddd_generate(), which follows what it includes.")
    endif()
endfunction()

# Registers one or more DDD description files (*.ddd.json) on the given component target. The files are attached as
# transitive usage requirements: every image linking the component, directly or transitively, collects them with
# ddd_generate(). Files in the source tree must exist at configure time; files in the build tree may be generated
# later during the build.
function(ddd_add_component target)
    cmake_parse_arguments(PARSE_ARGV 1 arg "" "" "JSON")
    if(arg_UNPARSED_ARGUMENTS)
        message(FATAL_ERROR "ddd_add_component: unknown argument(s) \"${arg_UNPARSED_ARGUMENTS}\".")
    endif()
    _ddd_refuse_empty_keywords("ddd_add_component" ${ARGC} "JSON")
    # An empty argument after a description is none: taken for one, it was the calling directory, refused as a
    # description not named *.ddd.json.
    list(REMOVE_ITEM arg_JSON "")
    if(NOT arg_JSON)
        message(FATAL_ERROR "ddd_add_component: at least one description file is required (JSON <file>...).")
    endif()
    if(NOT TARGET ${target})
        message(FATAL_ERROR "ddd_add_component: \"${target}\" is not a target.")
    endif()
    _ddd_require_transitive_properties("ddd_add_component")

    foreach(description IN LISTS arg_JSON)
        _ddd_absolute_input(description "${CMAKE_CURRENT_SOURCE_DIR}" "ddd_add_component")
        if(NOT description MATCHES "\\.ddd\\.json$")
            message(FATAL_ERROR "ddd_add_component: \"${description}\" registered on target \"${target}\" is a DDD "
                                "description and has to be named \"*.ddd.json\".")
        endif()
        _ddd_refuse_project_file("${target}" "${description}")
        set_property(TARGET ${target} APPEND PROPERTY DDD_JSON "${description}")
        set_property(TARGET ${target} APPEND PROPERTY INTERFACE_DDD_JSON "${description}")
        # DDD_JSON travels through the link graph; the component's own files are recorded separately for the
        # per-component check target, which must not see the files of the components it links.
        set_property(TARGET ${target} APPEND PROPERTY DDD_OWN_JSON "${description}")
        # The name the description gives its component, read now for the headers ddd_generate() declares in the
        # images linking this target (see there). A file that may be a component and names none - its json does not
        # parse, or its component has no name yet - is a dependency of the configure step until it does, so that the
        # configure reading the name comes with the build after the repair: without it, that component's header would
        # be written by a generation that does not declare it until somebody next configured. A file that does not
        # exist yet, written into the build tree by the build, says nothing yet - neither the component it may
        # describe nor its kind - and no configure came by itself once it was there: under Ninja the build after its
        # header changed compiled the readers against the old one, and its .ddd target checked a vocabulary as a
        # component. It is watched instead, so that the first build to find it there configures again before it does
        # anything else, and reads both.
        _ddd_component_name(name "${description}")
        if(NOT "${name}" STREQUAL "")
            set_property(TARGET ${target} APPEND PROPERTY DDD_COMPONENT_NAMES "${name}")
        elseif(EXISTS "${description}")
            _ddd_is_component_file(is_component "${description}")
            if(is_component)
                set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${description}")
            endif()
        else()
            _ddd_watch_file("${description}")
            message(STATUS "ddd_add_component: \"${description}\" does not exist yet, so neither the component it "
                           "may describe nor its kind can be read; the first build to find it there configures "
                           "again, and reads both.")
        endif()
    endforeach()
    set_property(TARGET ${target} APPEND PROPERTY TRANSITIVE_LINK_PROPERTIES DDD_JSON)

    # Remembered so that ddd_generate() can hand the generated interface headers to every component (see
    # PROPAGATE_HEADERS). A target registered twice is listed once.
    set_property(GLOBAL APPEND PROPERTY DDD_COMPONENT_TARGETS ${target})

    # On-demand convenience target (for example `ninja sensor_hub.ddd`) checking this component on its own, before it
    # is integrated into any image. A lone component has no counterpart and no shared vocabulary, so --standalone
    # holds back the checks that need every component of the project - the registry says which ones - and
    # everything else - datatypes, conversions, limits, initial values, bitfields, reserved names - is verified.
    if(NOT TARGET ${target}.ddd)
        if(NOT DDD_EXECUTABLE)
            message(STATUS "ddd_add_component: not creating the ${target}.ddd check target (the ddd tool was not "
                           "found).")
        else()
            add_custom_target(${target}.ddd
                              COMMENT "Checking the DDD description of ${target}"
                              VERBATIM)
            set_property(TARGET ${target} PROPERTY DDD_CHECK_TARGET ${target}.ddd)
        endif()
    endif()
    get_property(check_target TARGET ${target} PROPERTY DDD_CHECK_TARGET)
    if(check_target)
        foreach(description IN LISTS arg_JSON)
            _ddd_absolute_input(description "${CMAKE_CURRENT_SOURCE_DIR}" "ddd_add_component")
            # Only component files are checked on their own; a registered vocabulary file (types, units, sections,
            # constants or rasters) is checked through the image project instead. A target registering only such
            # files keeps its <target>.ddd target as a no-op rather than one that can never pass.
            _ddd_is_component_file(is_component "${description}")
            if(NOT is_component)
                continue()
            endif()
            add_custom_command(TARGET ${check_target} POST_BUILD
                               COMMAND ${DDD_EXECUTABLE} check "${description}" --standalone
                               VERBATIM)
        endforeach()
    endif()
endfunction()

# Writes the project description that ties the collected component descriptions together. The list of components is
# a generator expression - only at generate time is the link graph of the image known - so the file is produced with
# file(GENERATE) rather than being written here. An image without any registered component yields an empty
# "includes" list, which DDD accepts and reports as a project without variables.
function(_ddd_write_project_file output name description components plugins)
    # $<COMMA> keeps the comma of the json separator out of the argument splitting of $<JOIN>.
    set(entries "$<$<BOOL:${components}>:\n      \"$<JOIN:${components},\"$<COMMA>\n      \">\"\n    >")
    # The plugins are known at configure time, so they need no generator expression: a plain json list of strings,
    # in the order the call gave them, which is the order the tool runs their hooks in.
    set(plugin_entries "")
    if(plugins)
        list(JOIN plugins "\", \"" joined)
        set(plugin_entries "\"${joined}\"")
    endif()
    file(GENERATE
         OUTPUT "${output}"
         CONTENT "{
  \"project\": {
    \"name\": \"${name}\",
    \"description\": \"${description}\",
    \"plugins\": [${plugin_entries}],
    \"includes\": [${entries}]
  }
}
")
endfunction()

# Resolves the PLUGINS of a ddd_generate() call: a spec ending in .py is a path, made absolute against the calling
# directory and required to exist, and is also a file the generation depends on; any other spec is a dotted module
# name the tool imports from its environment, passed through as written.
function(_ddd_plugin_specs specs_variable files_variable specs base)
    set(resolved "")
    set(files "")
    foreach(spec IN LISTS specs)
        if(spec MATCHES "\\.py$")
            _ddd_absolute_input(spec "${base}" "ddd_generate")
            list(APPEND files "${spec}")
        endif()
        list(APPEND resolved "${spec}")
    endforeach()
    set(${specs_variable} "${resolved}" PARENT_SCOPE)
    set(${files_variable} "${files}" PARENT_SCOPE)
endfunction()

# The plugins a hand written project description names, read off its "plugins" array, a .py path resolved against the
# directory of the file the way the tool resolves it. Nothing here imports anything: the list only closes the schemas.
function(_ddd_project_plugins variable project_file)
    file(READ "${project_file}" content)
    set(specs "")
    string(JSON count ERROR_VARIABLE error LENGTH "${content}" "project" "plugins")
    if(NOT error AND count GREATER 0)
        cmake_path(GET project_file PARENT_PATH base)
        math(EXPR last "${count} - 1")
        foreach(index RANGE 0 ${last})
            string(JSON spec GET "${content}" "project" "plugins" ${index})
            if(spec MATCHES "\\.py$")
                cmake_path(ABSOLUTE_PATH spec BASE_DIRECTORY "${base}" NORMALIZE)
            endif()
            list(APPEND specs "${spec}")
        endforeach()
    endif()
    set(${variable} "${specs}" PARENT_SCOPE)
endfunction()

# The components a hand written project is made of, by name: read off the files "ddd sources" lists for it, since only
# the tool resolves the includes - their wildcards and sub-projects among them - and each component file then names
# its own. Only a json file is read: the others the listing holds are a plugin's modules, which name no component and
# may be many - every file of a package plugin. A vocabulary names none either. The files are dependencies of the
# configure step already (_ddd_project_sources), so a component renamed in one of them is read again by the configure
# that edit runs, and one that does not parse names nothing until it does.
function(_ddd_project_component_names variable sources)
    set(names "")
    foreach(source IN LISTS sources)
        string(TOLOWER "${source}" spelled)
        if(NOT spelled MATCHES "\\.json$")
            continue()
        endif()
        _ddd_component_name(name "${source}")
        list(APPEND names ${name})
    endforeach()
    set(${variable} "${names}" PARENT_SCOPE)
endfunction()

# Reads each $<$<CONFIG:...>:...> of a link list holding no other expression for the build type the tree is configured
# for, as CMake reads it: its content where CMAKE_BUILD_TYPE is one of the configurations it names, in any case, and
# nothing where it is not. The module takes no multi-config generator, so that build type is the one configuration
# there is. Any other expression is left as it is, to be taken whatever it comes to - one inside such a $<CONFIG:...>
# included, or one around it once that is read, such as a static library's $<LINK_ONLY:...>.
function(_ddd_for_this_configuration variable text)
    string(TOUPPER "${CMAKE_BUILD_TYPE}" build_type)
    while(text MATCHES "\\$<\\$<CONFIG:([^<>]*)>:([^<>]*)>")
        set(expression "${CMAKE_MATCH_0}")
        set(content "${CMAKE_MATCH_2}")
        string(TOUPPER "${CMAKE_MATCH_1}" configurations)
        string(REPLACE "," ";" configurations "${configurations}")
        if(NOT "${build_type}" IN_LIST configurations)
            set(content "")
        endif()
        string(REPLACE "${expression}" "${content}" text "${text}")
    endwhile()
    set(${variable} "${text}" PARENT_SCOPE)
endfunction()

# The components an image links, by name: the image's own registrations and those of every target in its link
# closure - its LINK_LIBRARIES and, from each target found there, that target's INTERFACE_LINK_LIBRARIES, where a static
# library's private links appear as $<LINK_ONLY:...>. That is the closure DDD_JSON is collected over, walked here by
# hand because BYPRODUCTS cannot take the generator expression that collects it: CMake evaluates an output before it
# knows any target, and refuses an expression naming one. Nor can an expression in a link list be evaluated here, but
# for a $<CONFIG:...> around names alone, which is read for the build type (_ddd_for_this_configuration), so every
# target any other one names is taken: a header declared and never written costs a generation at every build under
# Ninja, which the build log shows, where a header written and never declared is a reader compiled against the old
# one, with nothing to show for it. Each target is visited once, since two static libraries may link each other; one
# met under an alias and under its own name is visited twice, and names its components twice. A third argument, where
# given, is the variable the visited targets are returned in.
function(_ddd_linked_component_names variable image)
    set(visited "")
    set(pending "${image}")
    set(names "")
    while(NOT "${pending}" STREQUAL "")
        list(POP_FRONT pending target)
        if("${target}" IN_LIST visited)
            continue()
        endif()
        list(APPEND visited "${target}")
        get_property(own TARGET "${target}" PROPERTY DDD_COMPONENT_NAMES)
        list(APPEND names ${own})
        if("${target}" STREQUAL "${image}")
            get_property(linked TARGET "${target}" PROPERTY LINK_LIBRARIES)
        else()
            get_property(linked TARGET "${target}" PROPERTY INTERFACE_LINK_LIBRARIES)
        endif()
        _ddd_for_this_configuration(linked "${linked}")
        # Whatever in the list spells a target - a namespaced one included - is a target it may link: an entry is a
        # target's name, a path, a flag or an expression.
        string(REGEX MATCHALL "[A-Za-z0-9_.+-]+(::[A-Za-z0-9_.+-]+)*" candidates "${linked}")
        foreach(candidate IN LISTS candidates)
            if(TARGET "${candidate}")
                list(APPEND pending "${candidate}")
            endif()
        endforeach()
    endwhile()
    set(${variable} "${names}" PARENT_SCOPE)
    if(ARGC GREATER 2)
        set(${ARGV2} "${visited}" PARENT_SCOPE)
    endif()
endfunction()

# Under a Makefile generator, a rule for each file a stamped step writes and a step of the project's may read by its
# path: the a2l, the dictionary and the files the template names give away. Make knows a file only as the output of a
# rule, and a stamp's files were the output of none: a step depending on one by its path - a copy of the dictionary, a
# delivery's archive of the a2l - had no rule to make it with in a fresh tree, ran before the step under -j, and after
# an edit read what the build before had left. Each rule does nothing and depends on the step's target, so that a step
# depending on the file depends on that target, in the directory calling ddd_generate(), and runs once the step has. A
# rule apiece, because CMake touches every output but the first of one rule once it has run, and ddd_types.h among them
# would compile every component again.
function(_ddd_files_of_a_step files target)
    foreach(file IN LISTS files)
        add_custom_command(OUTPUT "${file}" DEPENDS ${target} COMMENT "" VERBATIM)
    endforeach()
endfunction()

# The generation of an image, added at the end of the directory that called ddd_generate() rather than in the call:
# its byproducts are the files of the {component} templates for every component the image links, and in the collected
# mode the link graph is only whole once the directory is done - an image may well be linked after the call that
# generates it, and a link the walk missed would leave a reader compiled against the old header. Everything else was
# decided by the call and is read off the image's properties. With PROJECT, the components are the project's, which
# the call already asked the tool for.
function(_ddd_add_generation image)
    get_property(outputs TARGET ${image} PROPERTY DDD_GENERATION_OUTPUTS)
    get_property(command TARGET ${image} PROPERTY DDD_GENERATION_COMMAND)
    get_property(touch TARGET ${image} PROPERTY DDD_GENERATION_TOUCH)
    get_property(depends TARGET ${image} PROPERTY DDD_GENERATION_DEPENDS)
    get_property(component_files TARGET ${image} PROPERTY DDD_COMPONENT_FILES)
    get_property(rendered_by_templates TARGET ${image} PROPERTY DDD_TEMPLATE_OUTPUTS)
    get_property(listed TARGET ${image} PROPERTY DDD_PROJECT_COMPONENTS SET)
    if(listed)
        get_property(names TARGET ${image} PROPERTY DDD_PROJECT_COMPONENTS)
    else()
        _ddd_linked_component_names(names "${image}" reached)
        # Kept for _ddd_refuse_late_links, which tells a target reached too late from one reached in time.
        set_property(TARGET ${image} PROPERTY DDD_REACHED_TARGETS "${reached}")
    endif()
    # A name met twice - a component reached under two names of its target, or two files naming one component, which
    # the generation reports - is one file: ninja refuses to load a build that declares an output twice.
    list(REMOVE_DUPLICATES names)
    # Kept for _ddd_refuse_late_links, which walks the graph again once every directory is done.
    set_property(TARGET ${image} PROPERTY DDD_DECLARED_COMPONENTS "${names}")
    set_property(TARGET ${image} PROPERTY DDD_GENERATION_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}")
    set(byproducts "")
    foreach(component_file IN LISTS component_files)
        cmake_path(GET component_file PARENT_PATH directory)
        cmake_path(GET component_file FILENAME pattern)
        foreach(name IN LISTS names)
            string(REPLACE "{component}" "${name}" rendered "${pattern}")
            if("${directory}/${rendered}" IN_LIST rendered_by_templates)
                message(FATAL_ERROR "ddd_generate: the component \"${name}\" of \"${image}\" would have "
                                    "\"${pattern}.jinja2\" render \"${rendered}\", which \"${rendered}.jinja2\" "
                                    "renders already: ninja refuses a build that declares one file twice. Rename "
                                    "the component, or one of the templates.")
            endif()
            list(APPEND byproducts "${directory}/${rendered}")
        endforeach()
    endforeach()
    add_custom_command(OUTPUT ${outputs}
                       BYPRODUCTS ${byproducts}
                       COMMAND ${command}
                       ${touch}
                       DEPENDS ${depends}
                       COMMENT "Generating the data dictionary of ${image}"
                       COMMAND_EXPAND_LISTS
                       VERBATIM)
endfunction()

# Stops the configure, once the top directory is done, at a component the image links that the generation does not
# declare: one reached only through a link made after the directory calling ddd_generate() was done - from a
# directory processed later, or through a library defined later - or registered on a target it reached in time only
# once that directory was done, either of which the walk of _ddd_add_generation could not see. The generation cannot
# be told about it any more: its command belongs to that directory, and BYPRODUCTS cannot be added to a command once
# it exists. Left alone, the build after the component's header changed would compile the components reading it
# against the old one, with nothing to show for it.
function(_ddd_refuse_late_links image)
    get_property(declared TARGET ${image} PROPERTY DDD_DECLARED_COMPONENTS)
    get_property(reached TARGET ${image} PROPERTY DDD_REACHED_TARGETS)
    get_property(directory TARGET ${image} PROPERTY DDD_GENERATION_DIRECTORY)
    _ddd_linked_component_names(ignored "${image}" visited)
    set(linked_late "")
    set(registered_late "")
    foreach(target IN LISTS visited)
        get_property(own TARGET "${target}" PROPERTY DDD_COMPONENT_NAMES)
        foreach(name IN LISTS own)
            if("${name}" IN_LIST declared)
                continue()
            endif()
            if("${target}" IN_LIST reached)
                list(APPEND registered_late "${name}")
            else()
                list(APPEND linked_late "${name}")
            endif()
        endforeach()
    endforeach()
    set(refusals "")
    if(NOT "${linked_late}" STREQUAL "")
        list(REMOVE_DUPLICATES linked_late)
        list(SORT linked_late)
        list(JOIN linked_late "\", \"" spelled)
        string(APPEND refusals
               "ddd_generate: \"${image}\" reaches the component(s) \"${spelled}\" through a link made, or a library "
               "defined, after \"${directory}\" - where ddd_generate() is called - was done. Their headers are not "
               "declared as outputs of the generation, so the build after one of them changed would compile the "
               "components reading it against the old one. Link the image's components, and define every library "
               "on the way to them, before that directory is done - or call ddd_generate() where they are. A link "
               "behind a generator expression is taken whatever the expression comes to, the names being read when "
               "the build is configured, before CMake evaluates any; one behind $<CONFIG:...> alone is read for the "
               "CMAKE_BUILD_TYPE configured.\n")
    endif()
    if(NOT "${registered_late}" STREQUAL "")
        list(REMOVE_DUPLICATES registered_late)
        list(SORT registered_late)
        list(JOIN registered_late "\", \"" spelled)
        string(APPEND refusals
               "ddd_generate: the component(s) \"${spelled}\" of \"${image}\" were registered after \"${directory}\" "
               "- where ddd_generate() is called - was done, on targets the image links in time. Their headers are "
               "not declared as outputs of the generation, so the build after one of them changed would compile the "
               "components reading it against the old one. Register the image's components before ddd_generate() "
               "is called, which is also what hands them its headers.\n")
    endif()
    if(NOT "${refusals}" STREQUAL "")
        message(FATAL_ERROR "${refusals}")
    endif()
endfunction()

# Generates the data dictionary of an image out of the component descriptions collected from its link closure, and
# links the result into the image. Must be called in the CMakeLists.txt which defines the image target, and after the
# components have been added (add_subdirectory), so that PROPAGATE_HEADERS reaches all of them; in the collected mode,
# the image has to be linked to its components by the time that directory is done (_ddd_refuse_late_links).
#
# ddd_generate(<image>
#              [PROJECT <file>]              # use this project description instead of collecting the link closure
#              [NAME <name>]                 # project name in the a2l and the dictionary, defaults to the image name
#              [OUTPUT_DIRECTORY <dir>]      # defaults to ${CMAKE_CURRENT_BINARY_DIR}/ddd/<image>
#              TEMPLATE_DIRECTORY <dir>      # jinja2 templates of the c sources, provided by the project
#              [SCHEMA_DIRECTORY <dir>]      # write the json schemas here, for editor validation
#              [PLUGINS <spec>...]           # the collected project's plugins: a .py path or a module name
#              [ADDRESS_MAP <file>]          # write the a2l after the link, its addresses read out of this map
#              [ADDRESSES_FROM_IMAGE]        # write the a2l after the link, its addresses read out of the image
#              [BYTE_ORDER little|big]       # byte order reported in the a2l
#              [SEVERITY <check=level>...]   # severity overrides, like -W on the command line
#              [LINK_LIBRARIES <target>...]  # usage requirements for compiling the generated definition file
#              [DEPENDS <file>...]           # additional dependencies retriggering the generation
#              [CONST_INPUTS]                # declare input variables const in the consumer headers
#              [NO_A2L]                      # do not generate the a2l file
#              [NO_DICTIONARY]               # do not write the resolved data dictionary
#              [STRICT]                      # treat DDD warnings as errors
#              [NO_PROPAGATE_HEADERS])       # do not hand <stem>_ddd_headers to the registered components
#
# It creates:
#
# * <stem>_ddd_generation  custom target running the generator
# * <stem>_ddd_headers     interface library exposing the generated headers, and in the collected mode the compile
#                          usage - include directories, compile definitions and compile options - of every
#                          registered component; linked into every registered component unless
#                          NO_PROPAGATE_HEADERS is given
# * <stem>_ddd_globals     object library compiling the single definition file, linked into the image; links
#                          <stem>_ddd_headers, which is where its compile usage comes from
# * <stem>_ddd_check       custom target running the consistency check alone, for a ci job that wants the verdict
#                          without the artefacts
# * <stem>_ddd_list        custom target printing the table of the image's variables - producer, consumers,
#                          datatype, unit - for a developer asking who writes what, without generating anything
# * <stem>_ddd_a2l         with ADDRESSES_FROM_IMAGE or ADDRESS_MAP, custom target writing the a2l once the image is
#                          linked, out of the image's debug information or out of the map; built by default
#
# <stem> is the image name without its extension, so an image named firmware.elf yields firmware_ddd_headers. The
# path of the generated a2l is available as the DDD_A2L property of the image, and that of the dictionary written beside
# it as its DDD_DICTIONARY property.
#
# The shared files - the ones the template names give away, the a2l and the dictionary - are the outputs of the
# generator, and the files a {component} template renders, one per component, are its byproducts, named at configure
# time: ddd_add_component() reads the component name of each registered description, and with PROJECT the names are
# read off the files "ddd sources" lists. Under Ninja a header no step declares is looked at once, before the
# generation rewrites it, so the build after a description change compiled the components reading it against the old
# header and linked them with the new globals; declared, each header is looked at again after the generation, and the
# components whose header changed are recompiled, and no others. A component renamed in its description therefore
# needs a reconfigure in the collected mode: until then its header is not declared under the new name, and the
# generation runs at every build for the one under the old name, which it no longer writes. <stem>_ddd_headers is what
# carries the include directory, and what orders every consumer after the generation. With ADDRESSES_FROM_IMAGE or
# ADDRESS_MAP the a2l is the output of <stem>_ddd_a2l's step instead, which runs after the link. Under a Makefile
# generator each of the two steps has a stamp for its one output, and each shared file a rule of its own, depending on
# the step's target (_ddd_files_of_a_step); the {component} files stay byproducts, with no rule under make.
function(ddd_generate image)
    cmake_parse_arguments(PARSE_ARGV 1 arg
                          "CONST_INPUTS;NO_A2L;NO_DICTIONARY;STRICT;NO_PROPAGATE_HEADERS;ADDRESSES_FROM_IMAGE"
                          "PROJECT;NAME;OUTPUT_DIRECTORY;TEMPLATE_DIRECTORY;SCHEMA_DIRECTORY;ADDRESS_MAP;BYTE_ORDER"
                          "SEVERITY;LINK_LIBRARIES;DEPENDS;PLUGINS")
    if(arg_UNPARSED_ARGUMENTS)
        message(FATAL_ERROR "ddd_generate: unknown argument(s) \"${arg_UNPARSED_ARGUMENTS}\".")
    endif()
    set(keywords_with_values PROJECT NAME OUTPUT_DIRECTORY TEMPLATE_DIRECTORY SCHEMA_DIRECTORY ADDRESS_MAP BYTE_ORDER
                             SEVERITY LINK_LIBRARIES DEPENDS PLUGINS)
    _ddd_refuse_empty_keywords("ddd_generate" ${ARGC} "${keywords_with_values}")
    # An empty argument after a value is none: taken for one, it was a -W with nothing after it, or a plugin named
    # nothing. LINK_LIBRARIES and DEPENDS drop theirs wherever they are expanded.
    list(REMOVE_ITEM arg_SEVERITY "")
    list(REMOVE_ITEM arg_PLUGINS "")
    # The a2l takes its addresses from one place, and ADDRESSES_FROM_IMAGE is that place being the image: beside a map
    # the call would name two, and beside NO_A2L it would read addresses for a file nobody writes.
    if(arg_ADDRESSES_FROM_IMAGE AND arg_ADDRESS_MAP)
        message(FATAL_ERROR "ddd_generate: ADDRESSES_FROM_IMAGE cannot be given together with ADDRESS_MAP: the a2l "
                            "takes its addresses from one of the two.")
    endif()
    if(arg_ADDRESSES_FROM_IMAGE AND arg_NO_A2L)
        message(FATAL_ERROR "ddd_generate: ADDRESSES_FROM_IMAGE cannot be given together with NO_A2L: the addresses "
                            "it reads out of the image are the a2l's.")
    endif()
    # A hand written project names its own plugins, so a second list here would be a second source of truth.
    if(arg_PLUGINS AND arg_PROJECT)
        message(FATAL_ERROR "ddd_generate: PLUGINS cannot be given together with PROJECT: the project description "
                            "names its own plugins.")
    endif()
    # A .py spec is a path, made absolute and required to exist like a description; anything else is a module name
    # the tool imports, passed through as written. The paths are dependencies of the generation, module names cannot be.
    _ddd_plugin_specs(plugin_specs plugin_files "${arg_PLUGINS}" "${CMAKE_CURRENT_SOURCE_DIR}")
    if(NOT TARGET ${image})
        message(FATAL_ERROR "ddd_generate: \"${image}\" is not a target.")
    endif()
    if(NOT DDD_EXECUTABLE)
        message(FATAL_ERROR "ddd_generate: the ddd tool was not found. Install it, or point DDD_EXECUTABLE at it.")
    endif()
    # Multi-config generators are not supported: the project description and the generated sources are written to
    # configuration-agnostic paths, which the configurations would fight over in a cryptic file(GENERATE) error.
    get_property(is_multi_config GLOBAL PROPERTY GENERATOR_IS_MULTI_CONFIG)
    if(is_multi_config)
        message(FATAL_ERROR "ddd_generate: multi-config generators are not supported, use a single-config generator "
                            "such as Ninja.")
    endif()

    if(NOT arg_OUTPUT_DIRECTORY)
        set(arg_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/ddd/${image}")
    endif()
    cmake_path(ABSOLUTE_PATH arg_OUTPUT_DIRECTORY BASE_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}" NORMALIZE)
    if(NOT arg_TEMPLATE_DIRECTORY)
        message(FATAL_ERROR "ddd_generate: TEMPLATE_DIRECTORY is required. The c sources are rendered from jinja2 "
                            "templates the project provides, so that their house style is the project's own; "
                            "\"ddd templates-dir\" prints a working set to copy from.")
    endif()
    _ddd_absolute_input(arg_TEMPLATE_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}" "ddd_generate")
    # Only the a2l reads the map, so a call that subtracts the a2l neither seeds it nor reads it. Otherwise the step
    # writing the a2l after the link reads it (below), and nothing else does: the run before the link leaves the a2l
    # out, and a dependency of that run on the map would re-render every c source after every link for a file it
    # does not read.
    if(arg_ADDRESS_MAP AND NOT arg_NO_A2L)
        _ddd_absolute_input(arg_ADDRESS_MAP "${CMAKE_CURRENT_SOURCE_DIR}" "ddd_generate")
        # The map is typically extracted from the linked image by a step of the project's after the link, so on the
        # very first build it does not exist yet - and ninja refuses to run a step for want of an input no rule
        # produces, before it has run anything. An absent map inside the build tree is therefore seeded empty at
        # configure time; the step reading it runs after the link, by when the project's step has written the real
        # one. A map in the source tree is not touched: there, a missing file is a mistake _ddd_absolute_input has
        # already refused.
        cmake_path(IS_PREFIX CMAKE_BINARY_DIR "${arg_ADDRESS_MAP}" NORMALIZE map_is_generated)
        if(map_is_generated AND NOT EXISTS "${arg_ADDRESS_MAP}")
            file(WRITE "${arg_ADDRESS_MAP}" "{}\n")
        endif()
    endif()
    if(arg_BYTE_ORDER AND NOT arg_BYTE_ORDER MATCHES "^(little|big)$")
        message(FATAL_ERROR "ddd_generate: BYTE_ORDER must be little or big, got \"${arg_BYTE_ORDER}\".")
    endif()

    # The helper targets are named after the image without its file extension: an image is typically named like its
    # artifact (firmware.elf), and firmware_ddd_headers is what a consumer naturally writes.
    cmake_path(GET image STEM LAST_ONLY image_stem)
    if(arg_NAME AND arg_PROJECT)
        message(STATUS "ddd_generate: NAME is ignored with PROJECT - the a2l and the dictionary are named after the "
                       "project name inside \"${arg_PROJECT}\".")
    endif()
    if(NOT arg_NAME)
        # The project name ends up as the a2l project and module name, which DDD requires to be a c identifier.
        string(REGEX REPLACE "[^A-Za-z0-9_]" "_" arg_NAME "${image_stem}")
        string(REGEX REPLACE "^([0-9])" "N\\1" arg_NAME "${arg_NAME}")
    endif()

    # The severity policy applies to every subcommand; everything else only makes sense for "generate", and
    # "check" would reject an unknown option.
    set(common_options "")
    if(arg_STRICT)
        list(APPEND common_options --strict)
    endif()
    foreach(severity IN LISTS arg_SEVERITY)
        list(APPEND common_options -W ${severity})
    endforeach()

    set(descriptions "")
    set(source_list "")
    if(arg_PROJECT)
        # Read now - the files it is made of, its plugins and its name - so it has to exist, and parse, now. A file in
        # the build tree that a step would write later, as a description may be, was let through, and so was one that
        # does not parse: each was warned of as a project the generation would depend on alone, and each then stopped
        # the configure on a reading of CMake's own, which names neither cause.
        cmake_path(ABSOLUTE_PATH arg_PROJECT BASE_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}" NORMALIZE)
        string(CONCAT read_when_configured
               "The project description is read when the build is configured - the files it is made of, its "
               "plugins and its name - so it has to exist, and parse, by then")
        if(NOT EXISTS "${arg_PROJECT}")
            message(FATAL_ERROR "ddd_generate: PROJECT names \"${arg_PROJECT}\", which does not exist. "
                                "${read_when_configured}: a file the build has yet to write is no project "
                                "description.")
        endif()
        file(READ "${arg_PROJECT}" content)
        string(JSON kind ERROR_VARIABLE unparsed TYPE "${content}")
        if(unparsed)
            message(FATAL_ERROR "ddd_generate: PROJECT names \"${arg_PROJECT}\", which does not parse as json. "
                                "${read_when_configured}: ${unparsed}")
        endif()
        set(project_file "${arg_PROJECT}")
        # A hand written project includes its components itself, so the files to watch have to be asked for; its
        # plugins are read off it for the schemas below, and reach the dependencies through the sources as well.
        _ddd_project_sources(descriptions "${project_file}" ${common_options})
        # The list itself is an input of the generation, so that it runs again for a file that left the list.
        set(source_list "${CMAKE_CURRENT_BINARY_DIR}/${image_stem}_ddd_sources.txt")
        _ddd_write_source_list("${source_list}" "${descriptions}")
        _ddd_project_plugins(plugin_specs "${project_file}")
        # Whose per-component files the generation declares: the project's components, which it names itself.
        _ddd_project_component_names(project_components "${descriptions}")
        set_property(TARGET ${image} PROPERTY DDD_PROJECT_COMPONENTS "${project_components}")
        # The tool names the a2l after the project name in the description, and the dictionary is named alike; NAME
        # renames neither.
        _ddd_description_name(arg_NAME "${project_file}")
    else()
        # The component descriptions travel through the link graph as a transitive property (see
        # ddd_add_component). The property is resolved at generate time, when the link graph is known but nothing is
        # compiled yet - the generation therefore never waits for a single object file.
        _ddd_require_transitive_properties("ddd_generate")
        set_property(TARGET ${image} APPEND PROPERTY TRANSITIVE_LINK_PROPERTIES DDD_JSON)
        set(descriptions "$<REMOVE_DUPLICATES:$<TARGET_PROPERTY:${image},DDD_JSON>>")
        set(project_file "${arg_OUTPUT_DIRECTORY}/${arg_NAME}.ddd.json")
        _ddd_write_project_file("${project_file}" "${arg_NAME}"
                                "Collected from the link closure of ${image} by ddd_generate()" "${descriptions}"
                                "${plugin_specs}")
    endif()
    if(arg_SCHEMA_DIRECTORY)
        _ddd_write_schemas("${arg_SCHEMA_DIRECTORY}" "${plugin_specs}")
    endif()

    _ddd_write_build_info("${arg_OUTPUT_DIRECTORY}" "${image}" "${project_file}" "${common_options}")
    # The output directory holds what the configure writes - the record above and, in the collected mode, the project
    # description - which no step of the build writes again: deleted, the build stopped under Ninja on that description,
    # missing and with no rule to make it, and only a configure by hand mended it. Watched, the record's deletion runs
    # the configure, which writes both again, before the build generates the rest.
    _ddd_watch_file("${arg_OUTPUT_DIRECTORY}/ddd-build.json")

    # The run always asks for every artefact the project has, and NO_A2L subtracts the a2l from
    # that rather than selecting the c artefact instead: 'all' is the only run that produces the
    # plugins' artefacts, so selecting c would silently drop them along with the a2l.
    set(artefact all)
    set(generate_options ${common_options})
    # The image, and a map extracted from it, are there once the image is linked, so with either source the run
    # before the link subtracts the a2l as well, and a step after the link writes it (below). Written before the link
    # out of the map, the a2l was one link behind the image: it held the addresses of the image the build before had
    # linked, and under STRICT an object new to a description stopped every build, the map lacking it being one only
    # a link rewrites.
    set(a2l_after_the_link FALSE)
    if(NOT arg_NO_A2L AND (arg_ADDRESSES_FROM_IMAGE OR arg_ADDRESS_MAP))
        set(a2l_after_the_link TRUE)
    endif()
    if(arg_NO_A2L OR a2l_after_the_link)
        list(APPEND generate_options --without a2l)
    endif()
    if(arg_CONST_INPUTS)
        list(APPEND generate_options --const-inputs)
    endif()
    # The byte order belongs to the a2l, so a run that subtracts it has no use for it.
    if(arg_BYTE_ORDER AND NOT arg_NO_A2L AND NOT a2l_after_the_link)
        list(APPEND generate_options --byte-order ${arg_BYTE_ORDER})
    endif()

    # The templates are collected with a glob which the build system re-evaluates (CONFIGURE_DEPENDS), so that adding or
    # removing a template is noticed without a manual re-configuration. The directory is read as a directory, whatever
    # characters it has: a checkout in "pr[1]" is no character class, which found no template at all.
    _ddd_literal_pattern(template_pattern "${arg_TEMPLATE_DIRECTORY}")
    file(GLOB template_files CONFIGURE_DEPENDS "${template_pattern}/*.jinja2")
    if(NOT template_files)
        message(FATAL_ERROR "ddd_generate: no *.jinja2 template in \"${arg_TEMPLATE_DIRECTORY}\". The c sources are "
                            "rendered from templates the project provides; \"ddd templates-dir\" prints a set to "
                            "copy from.")
    endif()
    # A template in a subdirectory is never rendered, and may be imported or included by one that is, so it is an input
    # of the generation as much as they are: its edit built to "no work to do" over the text it used to have.
    file(GLOB_RECURSE every_template CONFIGURE_DEPENDS "${template_pattern}/*.jinja2")
    # Which templates there are is an input as well. A template removed leaves every other input and the command as
    # they were, and only a run of the generation takes back the file it rendered, which stayed on the include path
    # otherwise. The list is kept in the build tree, rewritten only when it differs, as a project's files are.
    set(template_list "${CMAKE_CURRENT_BINARY_DIR}/${image_stem}_ddd_templates.txt")
    _ddd_write_source_list("${template_list}" "${every_template}")

    # Each template renders to a file named like it without the .jinja2 extension, so the
    # templates are the single source of truth for what is generated. A helper (leading
    # underscore) renders nothing at all, and a {component} template renders once per
    # component, under names only the descriptions give: its file is kept here with the
    # placeholder in it, and becomes a byproduct per component once the components are known
    # (_ddd_add_generation).
    set(generated_outputs "")
    set(definition_files "")
    set(component_files "")
    foreach(template_file IN LISTS template_files)
        cmake_path(GET template_file FILENAME generated_name)
        if(generated_name MATCHES "^_")
            continue()
        endif()
        cmake_path(REMOVE_EXTENSION generated_name LAST_ONLY)
        if(generated_name MATCHES "{component}")
            list(APPEND component_files "${arg_OUTPUT_DIRECTORY}/${generated_name}")
            continue()
        endif()
        list(APPEND generated_outputs "${arg_OUTPUT_DIRECTORY}/${generated_name}")
        if(generated_name MATCHES "\\.c$")
            list(APPEND definition_files "${arg_OUTPUT_DIRECTORY}/${generated_name}")
        endif()
    endforeach()
    if(NOT generated_outputs)
        message(FATAL_ERROR "ddd_generate: every template in \"${arg_TEMPLATE_DIRECTORY}\" is a helper or a "
                            "{component} template, so no file can be declared as an output of the generation.")
    endif()
    if(NOT definition_files)
        message(FATAL_ERROR "ddd_generate: no template in \"${arg_TEMPLATE_DIRECTORY}\" renders a .c file. The "
                            "definitions of the global variables have to be compiled into the image, so one "
                            "template must produce a source file (for example ddd_globals.c.jinja2).")
    endif()
    # The definitions are C, compiled by the object library below, which a project that enables no C - project(<name>
    # LANGUAGES CXX) - cannot build: CMake stopped at it, unable to determine its linker language, naming a target of
    # this module's and not the language the project left out.
    get_property(enabled_languages GLOBAL PROPERTY ENABLED_LANGUAGES)
    if(NOT "C" IN_LIST enabled_languages)
        set(rendered_c "")
        foreach(definition_file IN LISTS definition_files)
            cmake_path(GET definition_file FILENAME rendered)
            list(APPEND rendered_c "${rendered}")
        endforeach()
        list(JOIN rendered_c "\", \"" rendered_c)
        message(FATAL_ERROR "ddd_generate: the templates in \"${arg_TEMPLATE_DIRECTORY}\" render C - \"${rendered_c}\" "
                            "- the definitions of the image's variables, and the project does not enable C. Enable "
                            "it beside the project's own languages - project(<name> LANGUAGES C CXX) - or with "
                            "enable_language(C) in the top directory.")
    endif()
    # What the templates render under names known now, so that a component whose file would be one of them is
    # refused by name (_ddd_add_generation), rather than by ninja, which only says that a file is declared twice.
    set_property(TARGET ${image} PROPERTY DDD_TEMPLATE_OUTPUTS "${generated_outputs}")

    if(NOT arg_NO_A2L)
        set(a2l_file "${arg_OUTPUT_DIRECTORY}/${arg_NAME}.a2l")
        # Written before the link, or after it by the step below; the property names it either way.
        if(NOT a2l_after_the_link)
            list(APPEND generated_outputs "${a2l_file}")
        endif()
        set_property(TARGET ${image} PROPERTY DDD_A2L "${a2l_file}")
    endif()

    # The dictionary every artefact above is generated from, written beside them: what a template author reads to see
    # what the templates receive, and what a delivery archives for a later "ddd compare". "generate" writes it itself,
    # in the same write as the artefacts: one analysis and one report of its findings, and a run failing its checks
    # writes none of them, which leaves the last dictionary describing the artefacts still beside it. A file whose
    # content did not change is left untouched, as the artefacts are, so nothing depending on it runs again for nothing.
    # It is named like the a2l, after NAME or, with PROJECT, after the name inside that file.
    if(NOT arg_NO_DICTIONARY)
        set(dictionary_file "${arg_OUTPUT_DIRECTORY}/${arg_NAME}.dictionary.json")
        list(APPEND generated_outputs "${dictionary_file}")
        list(APPEND generate_options --dictionary "${dictionary_file}")
        set_property(TARGET ${image} PROPERTY DDD_DICTIONARY "${dictionary_file}")
    endif()

    # What a step is declared to produce. Under Ninja the files themselves: ninja looks at each again once the step has
    # run, so a file the run left as it was is no newer than before, and nothing compiled from it is compiled again.
    # A Makefile generator has nothing of the kind. There a run that changed nothing left the first file older than the
    # description that ran it, so every build after ran the generation again, and after each run CMake touched every
    # other file - ddd_types.h among them, which every component header includes, so every component compiled again.
    # So there a stamp in the output directory is the step's one output, touched by each run that succeeds, and each of
    # the files has a rule of its own (_ddd_files_of_a_step); a step that fails leaves the stamp as it was, and runs
    # again at the next build.
    set(stamped FALSE)
    if(NOT CMAKE_GENERATOR MATCHES "^Ninja")
        set(stamped TRUE)
    endif()
    if(stamped)
        set(generation_outputs "${arg_OUTPUT_DIRECTORY}/ddd-generation.stamp")
        set(generation_touch COMMAND "${CMAKE_COMMAND}" -E touch "${generation_outputs}")
    else()
        set(generation_outputs ${generated_outputs})
        set(generation_touch "")
    endif()

    # The command is added once this directory is done, when the components the image links are known by name; what it
    # runs, produces and depends on is settled here.
    set_property(TARGET ${image} PROPERTY DDD_GENERATION_OUTPUTS ${generation_outputs})
    set_property(TARGET ${image} PROPERTY DDD_GENERATION_COMMAND
                 ${DDD_EXECUTABLE} generate ${artefact} "${project_file}"
                 --output-dir "${arg_OUTPUT_DIRECTORY}"
                 --template-dir "${arg_TEMPLATE_DIRECTORY}" ${generate_options})
    set_property(TARGET ${image} PROPERTY DDD_GENERATION_TOUCH ${generation_touch})
    set_property(TARGET ${image} PROPERTY DDD_GENERATION_DEPENDS
                 "${project_file}" ${source_list} ${descriptions} ${plugin_files} ${arg_DEPENDS}
                 ${every_template} "${template_list}" "${DDD_EXECUTABLE}")
    set_property(TARGET ${image} PROPERTY DDD_COMPONENT_FILES "${component_files}")
    cmake_language(EVAL CODE "cmake_language(DEFER CALL _ddd_add_generation [==[${image}]==])")
    # And once the top directory is done, every link of the image known, the collected mode checks that the image
    # reaches no component the generation was added without.
    if(NOT arg_PROJECT)
        cmake_language(EVAL CODE "cmake_language(DEFER DIRECTORY [==[${CMAKE_SOURCE_DIR}]==] CALL "
                                 "_ddd_refuse_late_links [==[${image}]==])")
    endif()
    add_custom_target(${image_stem}_ddd_generation DEPENDS ${generation_outputs})
    if(stamped)
        _ddd_files_of_a_step("${generated_outputs}" ${image_stem}_ddd_generation)
    endif()

    # ADDRESSES_FROM_IMAGE and ADDRESS_MAP: the a2l is written once the image is linked, by a second run reading every
    # address it carries out of the image's debug information, or out of the map - which a step of the project's
    # extracts from the image after the link, a POST_BUILD command running before anything that depends on the image
    # - so that one build gives the complete a2l of the image it linked, and no second build has to read it. The run
    # depends on the image and on what the project is read from, and on the map as well, which a project may write
    # otherwise - not on the templates or DEPENDS, which are the c's inputs, not the a2l's - so it runs again whenever
    # the image relinks or a description changes, and never otherwise: under a Makefile generator a stamp is its one
    # output, as it is the generation's, and the a2l has a rule of its own. It writes into the directory the run before
    # the link wrote, whose manifest keeps each run from taking back the files of the other. STRICT and SEVERITY apply
    # to it as to that run, so that under STRICT a symbol the image cannot place, or the map leaves out, stops the build
    # rather than shipping an a2l with an address of 0; and BYTE_ORDER is its alone, held to the byte order an image
    # states.
    if(a2l_after_the_link)
        set(a2l_options ${common_options})
        if(arg_BYTE_ORDER)
            list(APPEND a2l_options --byte-order ${arg_BYTE_ORDER})
        endif()
        if(arg_ADDRESSES_FROM_IMAGE)
            set(address_source --image "$<TARGET_FILE:${image}>")
            set(map_dependency "")
            set(reading "Reading the addresses of the a2l out of ${image}")
        else()
            set(address_source --address-map "${arg_ADDRESS_MAP}")
            set(map_dependency "${arg_ADDRESS_MAP}")
            set(reading "Reading the addresses of the a2l out of the address map of ${image}")
        endif()
        if(stamped)
            set(a2l_outputs "${arg_OUTPUT_DIRECTORY}/ddd-a2l.stamp")
            set(a2l_touch COMMAND "${CMAKE_COMMAND}" -E touch "${a2l_outputs}")
        else()
            set(a2l_outputs "${a2l_file}")
            set(a2l_touch "")
        endif()
        add_custom_command(OUTPUT ${a2l_outputs}
                           COMMAND ${DDD_EXECUTABLE} generate a2l "${project_file}"
                                   --output-dir "${arg_OUTPUT_DIRECTORY}"
                                   ${address_source} ${a2l_options}
                           ${a2l_touch}
                           DEPENDS ${image} ${map_dependency} "${project_file}" ${source_list} ${descriptions}
                                   ${plugin_files}
                                   "${DDD_EXECUTABLE}"
                           COMMENT "${reading}"
                           COMMAND_EXPAND_LISTS
                           VERBATIM)
        add_custom_target(${image_stem}_ddd_a2l ALL DEPENDS ${a2l_outputs})
        if(stamped)
            _ddd_files_of_a_step("${a2l_file}" ${image_stem}_ddd_a2l)
        endif()
    endif()

    # The generated headers are exposed through an interface library, so that a component can include its interface
    # header without knowing where the image put it. The custom target bridges the build order across directories: a
    # consumer never compiles before the generation ran. There is no cycle to fear here - unlike a tool reading the
    # compiled objects, DDD only reads the description files, so a component may depend on the generation and still
    # be part of the link closure that produced it.
    add_library(${image_stem}_ddd_headers INTERFACE)
    target_include_directories(${image_stem}_ddd_headers INTERFACE "${arg_OUTPUT_DIRECTORY}")
    add_dependencies(${image_stem}_ddd_headers ${image_stem}_ddd_generation)

    # ddd_types.h includes the headers declaring the external types, so the generated headers cannot be compiled by
    # the include directory alone: in the collected mode this target also carries the interface compile usage of
    # every registered component - include directories, compile definitions and compile options, but never link
    # edges - so that a header an external type names is found *and read the way the component reads it* without
    # further wiring. The includes alone would not be safe: a hand written header may change its layout under the
    # component's interface flags, and a file compiled without them finds every header, compiles cleanly, and lays
    # the variables out differently than the image using them - the failure that compiles. Carrying this here rather
    # than on each consumer is what keeps the integration a two-liner: linking <stem>_ddd_headers is enough, and a
    # file including a generated header never has to mirror the flags of a component it does not otherwise know
    # about. Each $<TARGET_PROPERTY:...> resolves transitively over the component's own interface link closure, and
    # a component publishing nothing expands to an empty entry, which every one of these properties drops at
    # generate time. PROPAGATE_HEADERS below links this target back into the components, so the reference runs both
    # ways; that is not a cycle, because the transitive evaluation visits each target once. LINK_LIBRARIES remains
    # for the hand written PROJECT mode and for what no description implies, such as a header the project's own
    # templates include.
    if(NOT arg_PROJECT)
        get_property(ddd_registered_components GLOBAL PROPERTY DDD_COMPONENT_TARGETS)
        list(REMOVE_DUPLICATES ddd_registered_components)
        foreach(component IN LISTS ddd_registered_components)
            target_include_directories(${image_stem}_ddd_headers INTERFACE
                                       "$<TARGET_PROPERTY:${component},INTERFACE_INCLUDE_DIRECTORIES>")
            target_compile_definitions(${image_stem}_ddd_headers INTERFACE
                                       "$<TARGET_PROPERTY:${component},INTERFACE_COMPILE_DEFINITIONS>")
            target_compile_options(${image_stem}_ddd_headers INTERFACE
                                   "$<TARGET_PROPERTY:${component},INTERFACE_COMPILE_OPTIONS>")
        endforeach()
    endif()

    # The single definition file is compiled as an object library, so that every variable really ends up in the
    # image: a static library would drop the members whose symbols nobody references, and a measurement written only
    # by the calibration tool has no referencing code at all.
    add_library(${image_stem}_ddd_globals OBJECT ${definition_files})
    # The compile usage the definition file needs - the external type headers, read under the flags of the component
    # that declares them - reaches it through <stem>_ddd_headers, which it links below like any other consumer of
    # the generated headers.
    if(arg_LINK_LIBRARIES)
        target_link_libraries(${image_stem}_ddd_globals PRIVATE ${arg_LINK_LIBRARIES})
    endif()
    target_link_libraries(${image_stem}_ddd_globals PUBLIC ${image_stem}_ddd_headers)
    target_link_libraries(${image} PRIVATE ${image_stem}_ddd_globals)

    # Every component registered so far gets the generated headers, and the compile usage they need to be read,
    # which is what makes the integration a two-liner on the component side: add the library, register its
    # description, include "<Component>.h". Components registered after this call are not reached - call
    # ddd_generate() last.
    #
    # "Registered so far" is wider than the link closure of this image: a component that this image does not link
    # still receives <stem>_ddd_headers, and with it the compile usage collected above. That is deliberate rather
    # than harmless. ddd_types.h carries the external includes of the whole project and every component header
    # includes it, so a component parses every external type header whether it declares one or not; reading those
    # headers under other flags than the image does would lay the types out differently - the failure that compiles.
    # The price is that a component also compiles under compile definitions and compile options it never asked for,
    # and unlike an unused include path those are not inert. A project whose components disagree about such a flag
    # has to settle it itself, because this call cannot. It is also why a second image has to opt out rather than
    # being silently merged into the first.
    if(NOT arg_NO_PROPAGATE_HEADERS)
        # Two images would hand two different sets of headers to the same components: a component's interface header
        # depends on the link closure it was generated for, so whichever include directory came first would silently
        # win. A project with several images has to say which headers each component is compiled against.
        get_property(propagated_by GLOBAL PROPERTY DDD_HEADERS_PROPAGATED)
        if(propagated_by)
            message(FATAL_ERROR
                    "ddd_generate: the components already compile against the headers generated for "
                    "\"${propagated_by}\"; \"${image}\" cannot hand them a second set without making their include "
                    "order ambiguous. Give NO_PROPAGATE_HEADERS to *both* \"${propagated_by}\" and \"${image}\", and "
                    "link the wanted <stem>_ddd_headers into each component explicitly - propagating from only one "
                    "of the two leaves that same ambiguity in place, because the automatic set still reaches every "
                    "registered component rather than the ones this image links.")
        endif()
        set_property(GLOBAL PROPERTY DDD_HEADERS_PROPAGATED "${image}")
        get_property(component_targets GLOBAL PROPERTY DDD_COMPONENT_TARGETS)
        list(REMOVE_DUPLICATES component_targets)
        foreach(component IN LISTS component_targets)
            get_target_property(component_type ${component} TYPE)
            if(component_type STREQUAL "INTERFACE_LIBRARY")
                target_link_libraries(${component} INTERFACE ${image_stem}_ddd_headers)
            else()
                target_link_libraries(${component} PRIVATE ${image_stem}_ddd_headers)
            endif()
        endforeach()
    endif()

    # Checking is part of generating - the generator refuses to write anything when the interfaces disagree - but a
    # separate target lets a ci job run the check without producing artefacts.
    add_custom_target(${image_stem}_ddd_check
                      COMMAND ${DDD_EXECUTABLE} check "${project_file}" ${common_options}
                      DEPENDS "${project_file}" ${descriptions}
                      COMMENT "Checking the data dictionary of ${image}"
                      COMMAND_EXPAND_LISTS
                      VERBATIM)

    # The table of the image's variables, out of the same project description and under the same severity policy as the
    # generation: the project names the plugins its components' blocks belong to and knows every producer and consumer,
    # which a component listed on its own cannot. USES_TERMINAL puts the table straight on the console rather than
    # through the build tool's buffered output.
    add_custom_target(${image_stem}_ddd_list
                      COMMAND ${DDD_EXECUTABLE} list "${project_file}" ${common_options}
                      DEPENDS "${project_file}" ${descriptions}
                      COMMENT "Listing the data dictionary of ${image}"
                      USES_TERMINAL
                      COMMAND_EXPAND_LISTS
                      VERBATIM)
endfunction()
