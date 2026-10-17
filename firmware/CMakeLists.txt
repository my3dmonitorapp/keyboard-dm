cmake_minimum_required(VERSION 3.16)

# Reference SDK: ESP-IDF v5.1.6 (the final v5.1 bug-fix release).  v5.1 is
# deliberately frozen for F2 compatibility; see framework-decision.md for its
# lifecycle status and the required upgrade review.
set(KBDM_REFERENCE_IDF_VERSION "5.1.6")

if(NOT DEFINED IDF_TARGET)
    set(IDF_TARGET "esp32" CACHE STRING "ESP-IDF chip target")
endif()
if(NOT IDF_TARGET STREQUAL "esp32" AND NOT IDF_TARGET STREQUAL "esp32c3")
    message(FATAL_ERROR "Keyboard DM supports IDF_TARGET=esp32 or esp32c3")
endif()

set(EXTRA_COMPONENT_DIRS
    "${CMAKE_CURRENT_LIST_DIR}/components/kbdm_core"
    "${CMAKE_CURRENT_LIST_DIR}/components/kbdm_idf_hal"
    "${CMAKE_CURRENT_LIST_DIR}/targets/${IDF_TARGET}/main")
set(SDKCONFIG_DEFAULTS
    "${CMAKE_CURRENT_LIST_DIR}/sdkconfig.defaults;${CMAKE_CURRENT_LIST_DIR}/targets/${IDF_TARGET}/sdkconfig.defaults")

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(kbdm_${IDF_TARGET})

if(NOT IDF_VERSION_MAJOR EQUAL 5 OR NOT IDF_VERSION_MINOR EQUAL 1 OR
   NOT IDF_VERSION_PATCH EQUAL 6)
    message(FATAL_ERROR
        "Expected ESP-IDF ${KBDM_REFERENCE_IDF_VERSION}; found ${IDF_VERSION}. "
        "Use the reference checkout or explicitly update the reviewed pin/BLE APIs.")
endif()
