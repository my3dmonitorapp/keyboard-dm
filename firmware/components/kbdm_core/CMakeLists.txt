set(KBDM_SHARED "${CMAKE_CURRENT_LIST_DIR}/../../shared")

idf_component_register(
    SRCS
        "${KBDM_SHARED}/src/kb_actions.c"
        "${KBDM_SHARED}/src/kb_boot.c"
        "${KBDM_SHARED}/src/kb_config.c"
        "${KBDM_SHARED}/src/kb_crc32.c"
        "${KBDM_SHARED}/src/kb_events.c"
        "${KBDM_SHARED}/src/kb_hid.c"
        "${KBDM_SHARED}/src/kb_protocol.c"
        "${KBDM_SHARED}/src/kb_runtime.c"
        "${KBDM_SHARED}/src/kb_scanner.c"
    INCLUDE_DIRS "${KBDM_SHARED}/include")

target_compile_features(${COMPONENT_LIB} PUBLIC c_std_11)
