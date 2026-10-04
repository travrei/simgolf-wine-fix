#include <assert.h>
#include <string.h>
#include <stdio.h>
typedef unsigned int U32;
typedef unsigned short U16;
typedef unsigned char U8;
#include "convert.h"
int main(void) {
 const U8 bgra[]={0,0,255,255, 0,255,0,255, 255,0,0,255, 255,255,255,255};
 U16 out[6]; memset(out,0xaa,sizeof(out));
 convert_rows((U8*)out,6,2,2,0,bgra,0x7c00,0x3e0,0x1f);
 assert(out[0]==0x7c00&&out[1]==0x3e0&&out[2]==0xaaaa);
 assert(out[3]==0x1f&&out[4]==0x7fff&&out[5]==0xaaaa);
 memset(out,0xaa,sizeof(out));
 convert_rows((U8*)out,6,2,2,1,bgra,0xf800,0x7e0,0x1f);
 assert(out[0]==0x1f&&out[1]==0xffff&&out[2]==0xaaaa);
 assert(out[3]==0xf800&&out[4]==0x7e0&&out[5]==0xaaaa);
 U8 expanded[16]; U16 roundtrip[6];
 expand_rows(expanded,(U8*)out,6,2,2,1,1);
 memset(roundtrip,0xaa,sizeof(roundtrip));
 convert_rows((U8*)roundtrip,6,2,2,1,expanded,0xf800,0x7e0,0x1f);
 assert(!memcmp(out,roundtrip,sizeof(out)));
 for(unsigned int v=0;v<65536;v++) {
  U16 src=v,dst;U8 px[4];
  expand_rows(px,(U8*)&src,2,1,1,0,1);
  convert_rows((U8*)&dst,2,1,1,0,px,0xf800,0x7e0,0x1f);
  assert(src==dst);
  expand_rows(px,(U8*)&src,2,1,1,0,0);
  convert_rows((U8*)&dst,2,1,1,0,px,0x7c00,0x3e0,0x1f);
  assert((src&0x7fff)==dst);
 }
 puts("PASS: exhaustive 16-bit roundtrip; RGB555/RGB565, vertical orientation, stride and padding");
}
