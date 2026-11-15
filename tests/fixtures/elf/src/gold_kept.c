/* A negative input of two units, linked with --gc-sections and without -fdata-sections: this unit
   holds the entry and what it reads, and gold_unused.c nothing reads. The linker discards that
   unit's whole .data, and gold leaves the DWARF address of each variable in it at its offset in
   the discarded section, where no symbol of its name sits. The static is one the entry reads, so
   the link keeps it. */
#include <stdint.h>

uint32_t Gold_Kept = 0x55667788;
static volatile uint32_t Gold_Static = 0x01020304;

uint32_t entry(void) {
    return Gold_Kept + Gold_Static;
}
