idf_component_register(SRCS "app_main.c" "family.c"
                       INCLUDE_DIRS "." "../boards/unverified"
                       REQUIRES driver kbdm_core kbdm_idf_hal)
