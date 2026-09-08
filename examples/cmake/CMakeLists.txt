# Example integration of DDD into a CMake build.
#
# The four components live in the demo project; each is a library of its own here, registering its DDD description
# and including the interface header DDD generates for it. The image collects the descriptions through the link
# graph, so it gets exactly the components it links.
#
#   cmake -G Ninja -S examples/cmake -B build/cmake
#   cmake --build build/cmake
cmake_minimum_required(VERSION 3.30)
project(DddCMakeExample LANGUAGES C)

list(APPEND CMAKE_MODULE_PATH "${CMAKE_CURRENT_SOURCE_DIR}/../../cmake")
include(Ddd)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
# The warning flags are compiler-specific: MSVC rejects the GNU spellings outright (D8021).
if(NOT MSVC)
    add_compile_options(-Wall -Wextra -Wpedantic -Werror)
else()
    add_compile_options(/W4)
endif()

set(descriptions "${CMAKE_CURRENT_SOURCE_DIR}/../demo")

# A real project keeps its own c templates under version control, next to its sources, because what the generated
# code looks like is its house style. This example borrows the ones DDD ships as an example, which is also what
# `ddd templates-dir` prints.
set(templates "${CMAKE_CURRENT_SOURCE_DIR}/../templates")

# sensor_hub owns the sensor driver, so it is the component that publishes the vendor header
# declaring the driver's state type, and the flag that header's layout depends on. Its types file
# names that type, which puts the header's include line in ddd_types.h - and every component's
# generated header includes ddd_types.h, event_logger's among them, although event_logger does not
# link sensor_hub. Nothing here wires that up: ddd_generate() hands the registered components the
# compile usage it collected, which is what makes the include and the flag reach all of them.
add_library(sensor_hub STATIC components/sensor_hub.c)
target_include_directories(sensor_hub PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}/vendor")
target_compile_definitions(sensor_hub PUBLIC SENSOR_HUB_DRIVER_V2=1)
ddd_add_component(sensor_hub JSON "${descriptions}/components/sensor_hub.ddd.json"
                                  "${CMAKE_CURRENT_SOURCE_DIR}/sensor_hub_types.ddd.json")

add_library(controller STATIC components/controller.c)
target_link_libraries(controller PRIVATE sensor_hub)
ddd_add_component(controller JSON "${descriptions}/components/controller.ddd.json")

add_library(user_interface STATIC components/user_interface.c)
target_link_libraries(user_interface PRIVATE controller)
ddd_add_component(user_interface JSON "${descriptions}/components/user_interface.ddd.json")

add_library(event_logger STATIC components/event_logger.c)
ddd_add_component(event_logger JSON "${descriptions}/subsystems/logging/event_logger.ddd.json")

add_executable(firmware.elf main.c)
target_link_libraries(firmware.elf PRIVATE user_interface event_logger)

# Collects sensor_hub, controller, user_interface and event_logger through the link graph, generates
# ddd_globals.c/.h, ddd_types.h, one header per component and DemoDevice.a2l, and links the definitions in.
# SCHEMA_DIRECTORY is what a real project would use: the schemas are rewritten every time the build is configured,
# so they always describe the installed DDD rather than whichever version wrote them last. This example points it at
# the build tree, because the schemas this repository commits under schemas/ are the ones its examples are bound to and
# must not be overwritten by configuring.
ddd_generate(firmware.elf
             NAME DemoDevice
             TEMPLATE_DIRECTORY "${templates}"
             SCHEMA_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/schemas")
