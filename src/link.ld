SECTIONS {
 . = 0;
 .payload : { *(.text.entry) *(.text*) *(.rodata*) *(.data*) *(.got*) }
 .bss : { *(.bss*) *(COMMON) }
 ASSERT(. <= 0x1000, "Payload including BSS exceeds the injected section")
 /DISCARD/ : { *(.comment) *(.eh_frame*) *(.note*) }
}
