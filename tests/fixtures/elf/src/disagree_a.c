/* A negative input of two units that state one name at one address in two ways, linked with
   -fcommon so that the tentative definitions merge. This unit is the first: the common symbol
   Disagree_Cal is two bytes here and four in disagree_b.c, Disagree_Shared holds two elements
   here and four there, Disagree_Weak is a weak definition of two bytes that the other unit's
   strong one of four bytes replaces, and Disagree_Agreed is the same in both. */
#include <stdint.h>

uint16_t Disagree_Cal;
uint32_t Disagree_Shared[2];
uint32_t Disagree_Agreed;
__attribute__((weak)) uint16_t Disagree_Weak;

uint32_t entry(void) {
    return Disagree_Cal + Disagree_Shared[1] + Disagree_Agreed + Disagree_Weak;
}
