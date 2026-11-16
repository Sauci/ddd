/* The linker script of overlay.c: two sections at one address, kept apart by where they load. */
SECTIONS
{
  OVERLAY 0x20000 : AT (0x8000)
  {
    .page1 { *(.page1) }
    .page2 { *(.page2) }
  }
}
INSERT AFTER .data;
