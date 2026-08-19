# Ddd.cmake
#
# CMake integration of the DDD data dictionary. It provides two functions:
#
# * ddd_add_component(<target> JSON <file>...): registers the DDD description(s) of a component on its target, and
#   creates the on-demand <target>.ddd target checking that component on its own.
# * ddd_generate(<image> ...): collects the descriptions of all components in the link closure of the given image,
#   generates the global definition file, the per-component interface headers and the a2l, and links the result into
#   the image.
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

# Asks the tool which files a project description is built out of. A hand written project pulls its components in
# through "includes" - possibly with wildcards - so the project file alone is a wholly insufficient dependency: edit a
# component and the build would happily link yesterday's globals and a2l. The list is resolved at configure time and
# also registered with CMAKE_CONFIGURE_DEPENDS, so that adding a component to an "includes" wildcard re-runs configure
# and picks up the new file as well.
#
# Tolerant on purpose: if the tool is missing or the project cannot be read yet, the result is empty and the build
# falls back to depending on the project file alone, rather than failing to configure at all.
function(_ddd_project_sources variable project_file)
    execute_process(COMMAND "${DDD_EXECUTABLE}" sources "${project_file}"
                    OUTPUT_VARIABLE output
                    RESULT_VARIABLE status
                    ERROR_VARIABLE error
                    OUTPUT_STRIP_TRAILING_WHITESPACE)
    if(NOT status EQUAL 0)
        message(STATUS "ddd_generate: cannot resolve the sources of \"${project_file}\" yet "
                       "(${error}); the generation will depend on that file alone.")
        set(${variable} "" PARENT_SCOPE)
        return()
    endif()
    string(REPLACE "\r" "" output "${output}")
    string(REPLACE "\n" ";" sources "${output}")
    list(REMOVE_ITEM sources "")
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${sources})
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
function(_ddd_write_schemas directory)
    cmake_path(ABSOLUTE_PATH directory BASE_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}" NORMALIZE)
    execute_process(COMMAND "${DDD_EXECUTABLE}" schema all --output "${directory}"
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
# on component files: a vocabulary file - types, units, sections, constants - has no interfaces of its own, and handing one to "check" is an
# unrelaxable file-kind error that would break the <target>.ddd target for good. Such files still register on the
# target and are checked in context, through the project of every image that links the component.
#
# A file that does not exist yet - generated into the build tree later - is taken to be a component, because that is
# the only kind worth generating there; nothing can be read off it at configure time either way.
function(_ddd_is_component_file variable description)
    if(NOT EXISTS "${description}")
        set(${variable} TRUE PARENT_SCOPE)
        return()
    endif()
    file(READ "${description}" content)
    string(JSON unused ERROR_VARIABLE error GET "${content}" "component")
    if(error)
        set(${variable} FALSE PARENT_SCOPE)
    else()
        set(${variable} TRUE PARENT_SCOPE)
    endif()
endfunction()

# Turns a path into an absolute one and refuses a source file that does not exist. A file below the binary directory
# is accepted unconditionally: it may well be generated later during the build.
function(_ddd_absolute_input variable base context)
    set(path "${${variable}}")
    cmake_path(ABSOLUTE_PATH path BASE_DIRECTORY "${base}" NORMALIZE)
    cmake_path(IS_PREFIX CMAKE_BINARY_DIR "${path}" NORMALIZE path_is_generated)
    if(NOT path_is_generated AND NOT EXISTS "${path}")
        message(FATAL_ERROR "${context}: the file \"${path}\" does not exist.")
    endif()
    set(${variable} "${path}" PARENT_SCOPE)
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
        set_property(TARGET ${target} APPEND PROPERTY DDD_JSON "${description}")
        set_property(TARGET ${target} APPEND PROPERTY INTERFACE_DDD_JSON "${description}")
        # DDD_JSON travels through the link graph; the component's own files are recorded separately for the
        # per-component check target, which must not see the files of the components it links.
        set_property(TARGET ${target} APPEND PROPERTY DDD_OWN_JSON "${description}")
    endforeach()
    set_property(TARGET ${target} APPEND PROPERTY TRANSITIVE_LINK_PROPERTIES DDD_JSON)

    # Remembered so that ddd_generate() can hand the generated interface headers to every component (see
    # PROPAGATE_HEADERS). A target registered twice is listed once.
    set_property(GLOBAL APPEND PROPERTY DDD_COMPONENT_TARGETS ${target})

    # On-demand convenience target (for example `ninja sensor_hub.ddd`) checking this component on its own, before it
    # is integrated into any image. A lone component has no counterpart, so the two checks about the other side of
    # the interface are switched off; everything else - datatypes, conversions, limits, initial values, axis
    # references, reserved names - is verified.
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
            # Only component files are checked on their own; a registered vocabulary file (types, units, sections, constants) is
            # checked through the image project instead. A target registering only such files keeps its
            # <target>.ddd target as a no-op rather than one that can never pass.
            _ddd_is_component_file(is_component "${description}")
            if(NOT is_component)
                continue()
            endif()
            add_custom_command(TARGET ${check_target} POST_BUILD
                               COMMAND ${DDD_EXECUTABLE} check "${description}"
                                       -W missing-producer=ignore -W unused-output=ignore
                               VERBATIM)
        endforeach()
    endif()
endfunction()

# Writes the project description that ties the collected component descriptions together. The list of components is
# a generator expression - only at generate time is the link graph of the image known - so the file is produced with
# file(GENERATE) rather than being written here. An image without any registered component yields an empty
# "includes" list, which DDD accepts and reports as a project without variables.
function(_ddd_write_project_file output name description components)
    # $<COMMA> keeps the comma of the json separator out of the argument splitting of $<JOIN>.
    set(entries "$<$<BOOL:${components}>:\n      \"$<JOIN:${components},\"$<COMMA>\n      \">\"\n    >")
    file(GENERATE
         OUTPUT "${output}"
         CONTENT "{
  \"project\": {
    \"name\": \"${name}\",
    \"description\": \"${description}\",
    \"includes\": [${entries}]
  }
}
")
endfunction()

# Generates the data dictionary of an image out of the component descriptions collected from its link closure, and
# links the result into the image. Must be called in the CMakeLists.txt which defines the image target, and after the
# components have been added (add_subdirectory), so that PROPAGATE_HEADERS reaches all of them.
#
# ddd_generate(<image>
#              [PROJECT <file>]              # use this project description instead of collecting the link closure
#              [NAME <name>]                 # project name in the a2l, defaults to the image name
#              [OUTPUT_DIRECTORY <dir>]      # defaults to ${CMAKE_CURRENT_BINARY_DIR}/ddd/<image>
#              TEMPLATE_DIRECTORY <dir>      # jinja2 templates of the c sources, provided by the project
#              [SCHEMA_DIRECTORY <dir>]      # write the json schemas here, for editor validation
#              [ADDRESS_MAP <file>]          # symbol to address map filling in the a2l addresses
#              [BYTE_ORDER little|big]       # byte order reported in the a2l
#              [SEVERITY <check=level>...]   # severity overrides, like -W on the command line
#              [LINK_LIBRARIES <target>...]  # usage requirements for compiling the generated definition file
#              [DEPENDS <file>...]           # additional dependencies retriggering the generation
#              [CONST_INPUTS]                # declare input variables const in the consumer headers
#              [NO_A2L]                      # do not generate the a2l file
#              [STRICT]                      # treat DDD warnings as errors
#              [NO_PROPAGATE_HEADERS])       # do not hand the generated headers to the registered components
#
# It creates:
#
# * <image>_ddd_generation  custom target running the generator
# * <image>_ddd_headers     interface library exposing the generated headers; linked into every registered component
#                           unless NO_PROPAGATE_HEADERS is given
# * <image>_ddd_globals     object library compiling the single definition file, linked into the image
#
# The helper names are derived from the image name without its extension, so an image named firmware.elf yields
# firmware_ddd_headers. The path of the generated a2l is available as the DDD_A2L property of the image.
#
# Only the three shared files are declared as outputs of the generator; the per-component headers are written next to
# them, but their names come from inside the description files and are therefore unknown at configure time. That is
# what <image>_ddd_headers is for: a consumer depends on the generation step, not on an individual header path.
function(ddd_generate image)
    cmake_parse_arguments(PARSE_ARGV 1 arg
                          "CONST_INPUTS;NO_A2L;STRICT;NO_PROPAGATE_HEADERS"
                          "PROJECT;NAME;OUTPUT_DIRECTORY;TEMPLATE_DIRECTORY;SCHEMA_DIRECTORY;ADDRESS_MAP;BYTE_ORDER"
                          "SEVERITY;LINK_LIBRARIES;DEPENDS")
    if(arg_UNPARSED_ARGUMENTS)
        message(FATAL_ERROR "ddd_generate: unknown argument(s) \"${arg_UNPARSED_ARGUMENTS}\".")
    endif()
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
    if(arg_SCHEMA_DIRECTORY)
        _ddd_write_schemas("${arg_SCHEMA_DIRECTORY}")
    endif()
    if(arg_ADDRESS_MAP)
        _ddd_absolute_input(arg_ADDRESS_MAP "${CMAKE_CURRENT_SOURCE_DIR}" "ddd_generate")
        # The two-run flow: the map is typically extracted from the linked image by a build step, so on the very
        # first build it does not exist yet - and ninja would refuse to run the generation for want of a file no
        # rule produces. An absent map inside the build tree is therefore seeded empty at configure time; the
        # first build runs with every address 0 and the second, once the extractor has written the real map,
        # regenerates the a2l with the addresses filled in. A map in the source tree is not touched: there,
        # a missing file is a mistake _ddd_absolute_input has already refused.
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
        message(STATUS "ddd_generate: NAME is ignored with PROJECT - the a2l is named after the project name inside "
                       "\"${arg_PROJECT}\".")
    endif()
    if(NOT arg_NAME)
        # The project name ends up as the a2l project and module name, which DDD requires to be a c identifier.
        string(REGEX REPLACE "[^A-Za-z0-9_]" "_" arg_NAME "${image_stem}")
        string(REGEX REPLACE "^([0-9])" "N\\1" arg_NAME "${arg_NAME}")
    endif()

    set(descriptions "")
    if(arg_PROJECT)
        _ddd_absolute_input(arg_PROJECT "${CMAKE_CURRENT_SOURCE_DIR}" "ddd_generate")
        set(project_file "${arg_PROJECT}")
        # A hand written project includes its components itself, so the files to watch have to be asked for.
        _ddd_project_sources(descriptions "${project_file}")
        # The tool names the a2l after the project name in the description; NAME does not rename it.
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
                                "Collected from the link closure of ${image} by ddd_generate()" "${descriptions}")
    endif()

    # The severity policy applies to both subcommands; everything else only makes sense for "generate", and
    # "check" would reject an unknown option.
    set(common_options "")
    if(arg_STRICT)
        list(APPEND common_options --strict)
    endif()
    foreach(severity IN LISTS arg_SEVERITY)
        list(APPEND common_options -W ${severity})
    endforeach()

    _ddd_write_build_info("${arg_OUTPUT_DIRECTORY}" "${image}" "${project_file}" "${common_options}")

    set(generate_options ${common_options})
    if(arg_CONST_INPUTS)
        list(APPEND generate_options --const-inputs)
    endif()
    if(arg_NO_A2L)
        list(APPEND generate_options --no-a2l)
    endif()
    if(arg_BYTE_ORDER)
        list(APPEND generate_options --byte-order ${arg_BYTE_ORDER})
    endif()
    if(arg_ADDRESS_MAP)
        list(APPEND generate_options --address-map "${arg_ADDRESS_MAP}")
    endif()

    # The templates are collected with a glob which the build system re-evaluates
    # (CONFIGURE_DEPENDS), so that adding or removing a template is noticed without a manual
    # re-configuration.
    file(GLOB template_files CONFIGURE_DEPENDS "${arg_TEMPLATE_DIRECTORY}/*.jinja2")
    if(NOT template_files)
        message(FATAL_ERROR "ddd_generate: no *.jinja2 template in \"${arg_TEMPLATE_DIRECTORY}\". The c sources are "
                            "rendered from templates the project provides; \"ddd templates-dir\" prints a set to "
                            "copy from.")
    endif()

    # Each template renders to a file named like it without the .jinja2 extension, so the
    # templates are the single source of truth for what is generated. Two of them produce no
    # output that can be named here: a helper (leading underscore) renders nothing at all,
    # and a {component} template renders once per component - names that are only known once
    # the description files have been read, which is why the per-component headers reach
    # their consumers through the interface library below rather than as declared outputs.
    set(generated_outputs "")
    set(definition_files "")
    foreach(template_file IN LISTS template_files)
        cmake_path(GET template_file FILENAME generated_name)
        if(generated_name MATCHES "^_" OR generated_name MATCHES "{component}")
            continue()
        endif()
        cmake_path(REMOVE_EXTENSION generated_name LAST_ONLY)
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

    if(NOT arg_NO_A2L)
        set(a2l_file "${arg_OUTPUT_DIRECTORY}/${arg_NAME}.a2l")
        list(APPEND generated_outputs "${a2l_file}")
        set_property(TARGET ${image} PROPERTY DDD_A2L "${a2l_file}")
    endif()

    add_custom_command(OUTPUT ${generated_outputs}
                       COMMAND ${DDD_EXECUTABLE} generate "${project_file}"
                               --output-dir "${arg_OUTPUT_DIRECTORY}"
                               --template-dir "${arg_TEMPLATE_DIRECTORY}" ${generate_options}
                       DEPENDS "${project_file}" ${descriptions} ${arg_ADDRESS_MAP} ${arg_DEPENDS}
                               ${template_files} "${DDD_EXECUTABLE}"
                       COMMENT "Generating the data dictionary of ${image}"
                       COMMAND_EXPAND_LISTS
                       VERBATIM)
    add_custom_target(${image_stem}_ddd_generation DEPENDS ${generated_outputs})

    # The generated headers are exposed through an interface library, so that a component can include its interface
    # header without knowing where the image put it. The custom target bridges the build order across directories: a
    # consumer never compiles before the generation ran. There is no cycle to fear here - unlike a tool reading the
    # compiled objects, DDD only reads the description files, so a component may depend on the generation and still
    # be part of the link closure that produced it.
    add_library(${image_stem}_ddd_headers INTERFACE)
    target_include_directories(${image_stem}_ddd_headers INTERFACE "${arg_OUTPUT_DIRECTORY}")
    add_dependencies(${image_stem}_ddd_headers ${image_stem}_ddd_generation)

    # The single definition file is compiled as an object library, so that every variable really ends up in the
    # image: a static library would drop the members whose symbols nobody references, and a measurement written only
    # by the calibration tool has no referencing code at all.
    add_library(${image_stem}_ddd_globals OBJECT ${definition_files})
    # In the collected mode the definition file is compiled with the interface include directories of every
    # registered component - include paths only, never link edges - so that a header an external type names is
    # found without further wiring: the component that publishes the type already publishes the directory its
    # header lives in. The plain $<TARGET_PROPERTY:...> is exactly right here, because a component without
    # interface include directories expands to an empty entry, which INCLUDE_DIRECTORIES drops at generate time.
    # LINK_LIBRARIES remains for the hand written PROJECT mode and for headers the link graph does not carry.
    if(NOT arg_PROJECT)
        get_property(ddd_registered_components GLOBAL PROPERTY DDD_COMPONENT_TARGETS)
        list(REMOVE_DUPLICATES ddd_registered_components)
        foreach(component IN LISTS ddd_registered_components)
            target_include_directories(${image_stem}_ddd_globals PRIVATE
                                       "$<TARGET_PROPERTY:${component},INTERFACE_INCLUDE_DIRECTORIES>")
        endforeach()
    endif()
    if(arg_LINK_LIBRARIES)
        target_link_libraries(${image_stem}_ddd_globals PRIVATE ${arg_LINK_LIBRARIES})
    endif()
    target_link_libraries(${image_stem}_ddd_globals PUBLIC ${image_stem}_ddd_headers)
    target_link_libraries(${image} PRIVATE ${image_stem}_ddd_globals)

    # Every component registered so far gets the generated headers, which is what makes the integration a two-liner
    # on the component side: add the library, register its description, include "<Component>.h". Components
    # registered after this call are not reached - call ddd_generate() last.
    #
    # "Registered so far" is wider than the link closure of this image: a component that this image does not link
    # still receives the include directory. That is harmless for a single image - an unused include path changes
    # nothing - and it is why a second image has to opt out rather than being silently merged into the first.
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
                    "link the wanted <image>_ddd_headers into each component explicitly - propagating from only one "
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
endfunction()
