/* SimGolf Wine 11 compatibility: synchronize GDI DIB and GL at each batch.
 * Freestanding i386 PIC, injected only into the hash-verified Terrain.dll.
 */
#define API __attribute__((stdcall))
typedef unsigned int U32;
typedef unsigned short U16;
typedef unsigned char U8;
typedef void *HANDLE;
typedef struct {int type,width,height,stride; U16 planes,bpp; void *bits;} Bitmap;
typedef struct {U32 size; int width,height; U16 planes,bpp; U32 compression,size_image; int xp,yp; U32 used,important;} Header;
typedef struct {Bitmap bm; Header hdr; U32 masks[3]; HANDLE section; U32 offset;} Dib;
_Static_assert(sizeof(Dib)==84,"32-bit DIBSECTION layout");
static U8 *scratch;
static U32 capacity;
static int ready,batch_active,announced;
static HANDLE batch_dc;
static void *batch_bits;
static HANDLE(API *getdc)(void);
static HANDLE(API *getobj)(HANDLE,U32);
static int(API *describe)(HANDLE,int,void*);
static void(API *readpixels)(int,int,int,int,U32,U32,void*);
static void(API *drawpixels)(int,int,U32,U32,const void*);
static void(API *getint)(U32,int*);
static void(API *pixelstore)(U32,int);
static void(API *pushattrib)(U32);
static void(API *popattrib)(void);
static void(API *pushclient)(U32);
static void(API *popclient)(void);
static void(API *disable)(U32);
static void(API *matrixmode)(U32);
static void(API *pushmatrix)(void);
static void(API *popmatrix)(void);
static void(API *identity)(void);
static void(API *ortho)(double,double,double,double,double,double);
static void(API *viewport)(int,int,int,int);
static void(API *rasterpos)(int,int);
static void(API *pixelzoom)(float,float);
static void(API *pixelf)(U32,float);
static void(API *pixeli)(U32,int);
static void(API *colormask)(U8,U8,U8,U8);
static void(API *original_flush)(void);
static void(API *original_begin)(U32);
static HANDLE(API *getheap)(void);
static void*(API *alloc)(HANDLE,U32,U32);
static int(API *release)(HANDLE,U32,void*);
static void(API *debug)(const char*);
static int(API *gdiflush)(void);
#include "convert.h"
static int init(U8 *base) {
 if(ready) return 1;
 typedef void *(API *GetProc)(HANDLE,const char*);
 typedef HANDLE(API *GetModule)(const char*);
 GetProc gp=*(GetProc*)(base+0x113534);
 GetModule gm=*(GetModule*)(base+0x113554);
 HANDLE gl=gm("opengl32.dll"),gdi=gm("gdi32.dll"),k=gm("kernel32.dll");
 original_flush=*(void(API **)(void))(base+0x113670);
 original_begin=*(void(API **)(U32))(base+0x113660);
 #define LOAD(var,mod,name) do{var=(void*)gp(mod,name);if(!var)return 0;}while(0)
 LOAD(getdc,gl,"wglGetCurrentDC"); LOAD(getobj,gdi,"GetCurrentObject"); LOAD(describe,gdi,"GetObjectA");
 LOAD(readpixels,gl,"glReadPixels"); LOAD(drawpixels,gl,"glDrawPixels");
 LOAD(getint,gl,"glGetIntegerv"); LOAD(pixelstore,gl,"glPixelStorei");
 LOAD(pushattrib,gl,"glPushAttrib"); LOAD(popattrib,gl,"glPopAttrib");
 LOAD(pushclient,gl,"glPushClientAttrib"); LOAD(popclient,gl,"glPopClientAttrib");
 LOAD(disable,gl,"glDisable"); LOAD(matrixmode,gl,"glMatrixMode");
 LOAD(pushmatrix,gl,"glPushMatrix"); LOAD(popmatrix,gl,"glPopMatrix"); LOAD(identity,gl,"glLoadIdentity");
 LOAD(ortho,gl,"glOrtho"); LOAD(viewport,gl,"glViewport"); LOAD(rasterpos,gl,"glRasterPos2i");
 LOAD(pixelzoom,gl,"glPixelZoom"); LOAD(pixelf,gl,"glPixelTransferf"); LOAD(pixeli,gl,"glPixelTransferi");
 LOAD(colormask,gl,"glColorMask"); LOAD(getheap,k,"GetProcessHeap");
 LOAD(alloc,k,"HeapAlloc"); LOAD(release,k,"HeapFree"); LOAD(debug,k,"OutputDebugStringA");
 LOAD(gdiflush,gdi,"GdiFlush");
 ready=1;return 1;
}
static int bitmap(Dib *d,U32 *r,U32 *g,U32 *b) {
 HANDLE dc=getdc();
 if(!dc||describe(getobj(dc,7),sizeof(*d),d)!=sizeof(*d)||!d->bm.bits||d->bm.bpp!=16) return 0;
 int w=d->bm.width,h=d->bm.height;
 if(w<=0||h<=0||w>16384||h>16384||d->bm.stride<w*2)return 0;
 *r=0x7c00;*g=0x3e0;*b=0x1f;
 if(d->hdr.compression==3){*r=d->masks[0];*g=d->masks[1];*b=d->masks[2];}
 if(!((*r==0x7c00&&*g==0x3e0&&*b==0x1f)||(*r==0xf800&&*g==0x7e0&&*b==0x1f)))return 0;
 U32 bytes=(U32)w*h*4;
 if(bytes>capacity){U8 *p=alloc(getheap(),0,bytes);if(!p)return 0;if(scratch)release(getheap(),0,scratch);scratch=p;capacity=bytes;}
 return 1;
}
static void pixel_transfer_identity(void) {
 U32 scales[]={0xd14,0xd18,0xd1a,0xd1c};
 U32 biases[]={0xd15,0xd19,0xd1b,0xd1d};
 for(int i=0;i<4;i++){pixelf(scales[i],1);pixelf(biases[i],0);}
 pixeli(0xd10,0); /* GL_MAP_COLOR */
}
void fix_begin(U8 *base,U32 mode) {
 if(!init(base)){original_begin(mode);return;}
 if(!batch_active){
  Dib d={0};U32 r,g,b;
  if(bitmap(&d,&r,&g,&b)) {
   gdiflush();
   expand_rows(scratch,d.bm.bits,d.bm.stride,d.bm.width,d.bm.height,d.hdr.height<0,g==0x7e0);
   pushattrib(0x000fffff); /* GL_ALL_ATTRIB_BITS, including current raster position */
   pushclient(1); /* GL_CLIENT_PIXEL_STORE_BIT */
   U32 caps[]={0xb71,0xb90,0xbc0,0xbe2,0xbf2,0xbf1,0xb60,0xb50,0xc11,0xbd0,0xde0,0xde1,0x806f,0x8513};
   for(U32 i=0;i<sizeof(caps)/sizeof(caps[0]);i++)disable(caps[i]);
   for(int i=0;i<6;i++)disable(0x3000+i); /* user clip planes */
   colormask(1,1,1,1);
   pixelstore(0xcf5,4);pixelstore(0xcf2,0);pixelstore(0xcf3,0);pixelstore(0xcf4,0);
   pixelstore(0xcf0,0);pixelstore(0xcf1,0);
   pixel_transfer_identity();pixelzoom(1,1);
   viewport(0,0,d.bm.width,d.bm.height);
   matrixmode(0x1701);pushmatrix();identity();ortho(0,d.bm.width,0,d.bm.height,-1,1);
   matrixmode(0x1700);pushmatrix();identity();rasterpos(0,0);
   drawpixels(d.bm.width,d.bm.height,0x80e1,0x1401,scratch);
   popmatrix();matrixmode(0x1701);popmatrix();
   popclient();popattrib();
   batch_active=1;batch_dc=getdc();batch_bits=d.bm.bits;
  }
 }
 original_begin(mode);
}
void fix_flush(U8 *base) {
 if(!init(base)){original_flush();return;}
 Dib d={0};U32 r,g,b;
 if(!bitmap(&d,&r,&g,&b)){original_flush();return;}
 /* Without a new GL batch the DIB is already authoritative. */
 if(!batch_active)return;
 if(batch_dc!=getdc()||batch_bits!=d.bm.bits){batch_active=0;debug("SIMGOLF_FIX_V3: bitmap changed during batch\n");return;}
 pushattrib(0x20); /* GL_PIXEL_MODE_BIT */
 pushclient(1);
 pixel_transfer_identity();
 pixelstore(0xd05,4);pixelstore(0xd02,0);pixelstore(0xd03,0);pixelstore(0xd04,0);
 pixelstore(0xd00,0);pixelstore(0xd01,0);
 readpixels(0,0,d.bm.width,d.bm.height,0x80e1,0x1401,scratch);
 popclient();popattrib();
 gdiflush();
 convert_rows(d.bm.bits,d.bm.stride,d.bm.width,d.bm.height,d.hdr.height<0,scratch,r,g,b);
 batch_active=0;
 if(!announced){debug("SIMGOLF_FIX_V3: GDI/GL batch synchronization active\n");announced=1;}
}
