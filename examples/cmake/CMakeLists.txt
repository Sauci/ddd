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
add_compile_options(-Wall -Wextra -Wpedantic -Werror)

set(descriptions "${CMAKE_CURRENT_SOURCE_DIR}/../demo")

# A real project keeps its own c templates under version control, next to its sources, because what the generated
# code looks like is its house style. This example borrows the ones DDD ships as an example, which is also what
# `ddd templates-dir` prints.
set(templates "${CMAKE_CURRENT_SOURCE_DIR}/../templates")

add_library(sensor_hub STATIC components/sensor_hub.c)
ddd_add_component(sensor_hub JSON "${descriptions}/components/sensor_hub.ddd.json")

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
ddd_generate(firmware.elf NAME DemoDevice TEMPLATE_DIRECTORY "${templates}")
