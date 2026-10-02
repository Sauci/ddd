/* A negative input: built with -fdebug-types-section, its structures and enums sit in DWARF type
   units - a .debug_types section of their own at DWARF 4, units of .debug_info at DWARF 5 - which
   ddd tool from-elf refuses rather than reads. */
#include <stdint.h>

typedef enum Mode_e { MODE_IDLE = 0, MODE_RUN = 1 } Mode_t;

typedef struct Inlet_s {
    uint16_t raw[4];
    Mode_t mode;
} Inlet_t;

Inlet_t Struct_Inlet;
const Mode_t Cal_Mode = MODE_RUN;
const uint16_t Cal_Gain = 300;

uint32_t entry(void) {
    return Cal_Gain;
}
