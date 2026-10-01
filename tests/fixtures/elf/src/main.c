/* The fixture of `ddd tool from-elf`: a variable per case of section 4 of
   docs/superpowers/specs/2026-09-30-toolbox-from-elf-design.md, each named for its case.

   No initial value repeats a byte, so that a byte order mistake cannot pass for a right
   answer. FIXTURE_TLS and FIXTURE_FOLDED are the optional cases: a row defines them where its
   toolchain builds them, and tests/fixtures/elf/manifest.json records which it did. */
#include <stdbool.h>
#include <stdint.h>

#include "shared.h"

#define USED __attribute__((used))

/* 4.1 kind */
uint16_t Meas_U16 = 0x1234;
volatile uint32_t Meas_Volatile = 0x12345678;
int16_t Meas_Array[3] = {-2, 0x1234, 7};
uint8_t Meas_Matrix[2][3] = {{1, 2, 3}, {4, 5, 6}};
uint8_t Meas_Fill[4] = {9, 9, 9, 9};
uint32_t Meas_Bss;
const uint16_t Cal_Gain = 300;
const volatile uint8_t Cal_Tunable = 0x5A;
const int32_t Cal_Table[4] = {-2, 0x12345678, 0, 1};
extern const uint16_t Cal_Declared_First;
const uint16_t Cal_Declared_First = 0x1234;

/* 4.2 datatypes */
bool Type_Bool = true;
char Type_Char = 'A';
long Type_Long = -2;
uint64_t Type_U64 = 0x0102030405060708u;
int64_t Type_S64 = -0x0102030405060708;
float Type_F32 = 1.5f;
float Type_F32_Tenth = 0.1f;
double Type_F64 = 0.1;
long double Type_Long_Double = 1.0L;
_Complex float Type_Complex;
uint8_t *Type_Pointer;
union {
    uint8_t a;
    uint16_t b;
} Type_Union;

/* 4.3 enums */
typedef enum { STATE_OFF = 0, STATE_ON = 1, STATE_FAULT = 200 } State_t;
State_t Enum_State = STATE_ON;
enum Signed_e { SIGNED_NEG = -2, SIGNED_POS = 3 };
enum Signed_e Enum_Signed = SIGNED_NEG;
enum { ANON_A = 1, ANON_B = 2 } Enum_Anonymous = ANON_B;
const State_t Enum_Table[2] = {STATE_FAULT, STATE_OFF};

/* 4.4 structures */
typedef enum { MODE_IDLE = 0, MODE_RUN = 1, MODE_STOP = 2 } Mode_t;
typedef struct Inlet_s {
    uint16_t raw[4];
    State_t state;
    struct {
        uint8_t lo;
        uint8_t hi;
    } pair;
    uint8_t flags : 3;
    Mode_t mode : 2;
    bool ready : 1;
} Inlet_t;
Inlet_t Struct_Inlet;
Inlet_t Struct_Inlets[2];
const Inlet_t Struct_Config = {.raw = {1, 2, 3, 4}};
const Inlet_t Struct_Configs[2];
struct {
    uint8_t a;
    uint8_t b;
} Struct_Anonymous;
struct Holder_s {
    uint8_t *ptr;
    uint8_t n;
} Struct_With_Pointer;
struct Qualified_s {
    volatile uint8_t v;
    const uint8_t c;
} Struct_Qualified;

/* 4.5 layout */
struct Gapped_s {
    uint8_t a : 2;
    uint8_t : 3;
    uint8_t b : 2;
    uint16_t c : 9;
};
struct Gapped_s Layout_Gapped;
struct Padded_s {
    uint8_t a : 7;
    uint8_t b : 2;
};
struct Padded_s Layout_Padded;
struct Aligned_s {
    _Alignas(8) uint8_t x;
};
struct Aligned_s Layout_Aligned;

/* 4.7 sections */
__attribute__((section(".calib"))) const uint16_t Section_Calib = 0x1234;

/* storage */
static uint16_t Static_Used USED = 0x0102;
#ifdef FIXTURE_TLS
_Thread_local uint32_t Tls_Counter;
#endif
#ifdef FIXTURE_FOLDED
static const uint32_t Static_Folded = 7;
#endif

/* The probes: tests/fixtures/elf/manifest.json holds their sizes, as the row's readelf reads
   them. */
enum Probe_e { PROBE_ONE = 1 };
enum Probe_e Probe_Enum;
struct {
    char c;
    uint64_t v;
} Probe_Align;

uint32_t fixture_entry(void) {
#ifdef FIXTURE_FOLDED
    return Static_Folded + Meas_Bss;
#else
    return Meas_Bss;
#endif
}

/* Appended after the entry point, so that no line above it moves: the user guide's transcripts
   cite lines of this file. A structure holding an array of structures, a two dimensional array
   and signed bitfields - the member shapes the cases above leave out. */
typedef struct {
    int8_t low : 3;
    int16_t high : 5;
    uint8_t level;
} Sample_t;

typedef struct Frame_s {
    Sample_t samples[3];
    uint16_t grid[2][3];
    int8_t trim : 4;
} Frame_t;

Frame_t Nested_Frame;

/* Appended after Nested_Frame, so that no line above it moves. An array a header declares
   without its size and the definition completes, as tables usually are; and the members
   section 4.4 refuses: a flexible array, a zero length array (a GNU extension) and an
   anonymous structure (C11). */
extern const uint16_t Cal_Curve[];
const uint16_t Cal_Curve[4] = {0x1234, 0x5678, 0x9ABC, 0xDEF0};

struct Flexible_s {
    uint8_t count;
    uint8_t data[];
};
struct Flexible_s Member_Flexible;

struct Zero_s {
    uint8_t count;
    uint8_t none[0];
};
struct Zero_s Member_Zero;

struct Anonymous_s {
    uint8_t before;
    struct {
        uint8_t inner;
    };
};
struct Anonymous_s Member_Anonymous;
