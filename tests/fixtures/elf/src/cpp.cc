/* A negative input in C++, which the reader is not for: it reads the C of gcc and clang. A
   structure with a base class, a structure with a static data member, a variable the debug
   information places in a namespace, and a plain C variable beside them. gcc writes the
   namespace's definition at the top of the unit, beside the C variables, with a reference to
   its declaration inside the namespace. */
#include <stdint.h>

struct Base {
    uint16_t base_member;
};

struct Derived : Base {
    uint16_t own;
};

struct WithStatic {
    uint16_t value;
    static uint16_t counted;
};

uint16_t WithStatic::counted = 7;

namespace ns {
uint16_t OnlyInNs = 5;
}

Derived Cpp_Derived = {{1}, 2};
WithStatic Cpp_Static = {3};
uint16_t Cpp_Plain = 4;

extern "C" void entry(void) {
}
