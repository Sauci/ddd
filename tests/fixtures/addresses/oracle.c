/* oracle.c - written by docker/build_address_fixtures.py out of symbols.json; do not edit.
 *
 * The offset of every symbol the a2l of tests/fixtures/addresses/project/ carries an
 * ECU_ADDRESS for, from the variable it belongs to, as this unit's compiler lays the variable
 * out: one constant per symbol, in the order symbols.json lists them. The build reads them back
 * out of each image and adds the variable's address, which nm gives.
 */
#include <stddef.h>
#include <stdint.h>

#include "ddd_globals.h"

__attribute__((used, section(".address_oracle"))) const uint32_t address_oracle[] = {
    offsetof(struct { __typeof__(Cells) r; }, r[0].raw),
    offsetof(struct { __typeof__(Cells) r; }, r[0].v),
    offsetof(struct { __typeof__(Cells) r; }, r[1].raw),
    offsetof(struct { __typeof__(Cells) r; }, r[1].v),
    offsetof(struct { __typeof__(Cells) r; }, r[2].raw),
    offsetof(struct { __typeof__(Cells) r; }, r[2].v),
    offsetof(struct { __typeof__(Enabled) r; }, r),
    offsetof(struct { __typeof__(Energy) r; }, r),
    offsetof(struct { __typeof__(Gain) r; }, r),
    offsetof(struct { __typeof__(Gear) r; }, r),
    offsetof(struct { __typeof__(Grid) r; }, r[0][0].raw),
    offsetof(struct { __typeof__(Grid) r; }, r[0][0].v),
    offsetof(struct { __typeof__(Grid) r; }, r[0][1].raw),
    offsetof(struct { __typeof__(Grid) r; }, r[0][1].v),
    offsetof(struct { __typeof__(Grid) r; }, r[0][2].raw),
    offsetof(struct { __typeof__(Grid) r; }, r[0][2].v),
    offsetof(struct { __typeof__(Grid) r; }, r[1][0].raw),
    offsetof(struct { __typeof__(Grid) r; }, r[1][0].v),
    offsetof(struct { __typeof__(Grid) r; }, r[1][1].raw),
    offsetof(struct { __typeof__(Grid) r; }, r[1][1].v),
    offsetof(struct { __typeof__(Grid) r; }, r[1][2].raw),
    offsetof(struct { __typeof__(Grid) r; }, r[1][2].v),
    offsetof(struct { __typeof__(Inlet) r; }, r.cells[0].raw),
    offsetof(struct { __typeof__(Inlet) r; }, r.cells[0].v),
    offsetof(struct { __typeof__(Inlet) r; }, r.cells[1].raw),
    offsetof(struct { __typeof__(Inlet) r; }, r.cells[1].v),
    offsetof(struct { __typeof__(Inlet) r; }, r.history),
    offsetof(struct { __typeof__(Inlet) r; }, r.latest.timestamp),
    offsetof(struct { __typeof__(Inlet) r; }, r.latest.value),
    offsetof(struct { __typeof__(Inlet) r; }, r.state),
    offsetof(struct { __typeof__(Limit) r; }, r),
    offsetof(struct { __typeof__(Mixed) r; }, r.after),
    offsetof(struct { __typeof__(Mixed) r; }, r.last),
    offsetof(struct { __typeof__(Mixed) r; }, r.next),
    offsetof(struct { __typeof__(Ratio) r; }, r),
    offsetof(struct { __typeof__(Samples) r; }, r),
    offsetof(struct { __typeof__(Speed) r; }, r),
    offsetof(struct { __typeof__(Status) r; }, r.level),
    offsetof(struct { __typeof__(Status) r; }, r.tail),
    offsetof(struct { __typeof__(Status) r; }, r.word),
    offsetof(struct { __typeof__(Table) r; }, r),
    offsetof(struct { __typeof__(Ticks) r; }, r),
    offsetof(struct { __typeof__(Torque) r; }, r),
    offsetof(struct { __typeof__(Tuning) r; }, r.gain),
    offsetof(struct { __typeof__(Tuning) r; }, r.shift),
    offsetof(struct { __typeof__(Tuning) r; }, r.timeout),
};

/* The image's entry point: the images are read, never run. */
void address_oracle_entry(void) {}
