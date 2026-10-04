static void convert_rows(U8 *dst_bits,int stride,int w,int h,int topdown,const U8 *rgba,U32 red,U32 green,U32 blue) {
    int rshift=green==0x7e0?11:10, gdrop=green==0x7e0?2:3;
    (void)red; (void)blue;
    for(int y=0;y<h;y++) {
        int row=topdown?h-1-y:y;
        U16 *dst=(U16*)(dst_bits+row*stride);
        const U8 *src=rgba+y*w*4;
        for(int x=0;x<w;x++,src+=4) dst[x]=(U16)(((src[2]>>3)<<rshift)|((src[1]>>gdrop)<<5)|(src[0]>>3));
    }
}
static void expand_rows(U8 *bgra,const U8 *src_bits,int stride,int w,int h,int topdown,int rgb565) {
 for(int y=0;y<h;y++) {
  int row=topdown?h-1-y:y;
  const U16 *src=(const U16*)(src_bits+row*stride);
  U8 *dst=bgra+y*w*4;
  for(int x=0;x<w;x++,dst+=4) {
   U32 p=src[x],r=(p>>(rgb565?11:10))&31,g=(p>>5)&(rgb565?63:31),b=p&31;
   dst[0]=(b<<3)|(b>>2);dst[1]=rgb565?((g<<2)|(g>>4)):((g<<3)|(g>>2));dst[2]=(r<<3)|(r>>2);dst[3]=255;
  }
 }
}
