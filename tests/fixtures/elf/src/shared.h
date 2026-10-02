/* Shared by unit_a.c and unit_b.c. DWARF gives each unit its own copy of this structure, and
   `ddd tool from-elf` states it once. */
#ifndef SHARED_H
#define SHARED_H

#include <stdint.h>

typedef struct {
    uint8_t x;
    uint8_t y;
} Shared_t;

#endif
