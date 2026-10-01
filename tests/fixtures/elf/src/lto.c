/* A negative input: linked with gcc's link-time optimisation (-flto). Its variables are
   described twice - named and without an address in the unit of this file, located and without
   a name in an <artificial> unit whose producer is GNU GIMPLE - which ddd tool from-elf refuses
   rather than reads. */
#include <stdint.h>

__attribute__((used)) const uint16_t Cal_Gain = 300;
__attribute__((used)) uint32_t Meas_Count = 7;
volatile uint32_t Meas_Live;

uint32_t entry(void) {
    Meas_Live += 1;
    return Meas_Live;
}
