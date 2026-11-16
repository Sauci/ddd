/* A negative input whose linker script, overlay.ld, overlays two sections at one address, as a
   banked or paged memory is linked: Page1_Var and Page2_Var share 0x20000, each in a section of
   its own, and what the image holds at that address is the first section's bytes. */
#include <stdint.h>

__attribute__((section(".page1"))) uint32_t Page1_Var = 0x11111111;
__attribute__((section(".page2"))) uint32_t Page2_Var = 0x22222222;

uint32_t entry(void) {
    return Page1_Var + Page2_Var;
}
