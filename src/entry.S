.section .text.entry,"ax"
.global entry
entry:
    call 1f
1:  pop %eax
    sub $(1b+0x119000),%eax
    push %eax
    call fix_flush
    add $4,%esp
    ret
.global begin_entry
begin_entry:
    mov 4(%esp),%edx
    call 2f
2:  pop %eax
    sub $(2b+0x119000),%eax
    push %edx
    push %eax
    call fix_begin
    add $8,%esp
    ret $4
.section .note.GNU-stack,"",@progbits
