/* A negative input: its text starts at address 0, as flash does on many microcontrollers, and
   it is linked with -fdata-sections and --gc-sections. The linker discards the variable nothing
   references and keeps its DWARF entry, resolving its address to 0, where the code sits. */
#include <stdint.h>

const uint32_t Cal_Discarded = 0x11223344;
const volatile uint32_t Cal_Kept = 0x55667788;

uint32_t entry(void) {
    return Cal_Kept;
}
