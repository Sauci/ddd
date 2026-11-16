/* A negative input of two units, only this one built with -g: it describes a common symbol and a
   weak definition as two bytes, and the unit without debug information, undescribed_b.c, gives
   the image's symbol table the four bytes each really is. The one description then says less
   than the symbol does. */
#include <stdint.h>

uint16_t Undescribed_Common;
__attribute__((weak)) uint16_t Undescribed_Weak;

uint32_t entry(void) {
    return Undescribed_Common + Undescribed_Weak;
}
