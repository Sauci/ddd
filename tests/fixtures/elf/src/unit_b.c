/* The other of the two units unit_a.c describes. */
#include <stdint.h>

#include "shared.h"

#define USED __attribute__((used))

static uint16_t Twin USED = 0x2222;
Shared_t Shared_B;
struct Clash_s {
    uint16_t a;
    uint16_t b;
} Clash_B;

/* Appended: the other half of unit_a.c's common pair. */
__attribute__((common)) uint32_t Common_Counter;
