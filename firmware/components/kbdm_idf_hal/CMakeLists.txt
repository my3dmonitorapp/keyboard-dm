idf_component_register(
    SRCS "kbdm_idf_hal.c"
    INCLUDE_DIRS "include"
    REQUIRES bt driver esp_timer kbdm_core nvs_flash)
