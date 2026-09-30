/* One of the two units that define a static of one name, share a structure through a header,
   and define two different structures under one tag; unit_b.c is the other. */
#include <stdint.h>

#include "shared.h"

#define USED __attribute__((used))

static uint16_t Twin USED = 0x1111;
Shared_t Shared_A;
struct Clash_s {
    uint8_t a;
} Clash_A;
