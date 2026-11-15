/* The unit nothing references: see gold_kept.c. Its variables are initialised, so that they sit
   in .data, which the link discards whole. */
#include <stdint.h>

typedef struct {
    uint16_t a;
    uint16_t b;
} Pair_s;

uint32_t First_Unused = 0x11111111;
uint32_t Second_Unused = 0x22222222;
Pair_s Struct_Unused = {0x3333, 0x4444};
