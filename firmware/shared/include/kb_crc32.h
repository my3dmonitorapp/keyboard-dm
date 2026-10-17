#ifndef KB_CRC32_H
#define KB_CRC32_H

#include <stddef.h>
#include <stdint.h>

/* IEEE 802.3 CRC-32 (polynomial 0x04c11db7, reflected). */
uint32_t kb_crc32(const void *data, size_t length);

#endif
