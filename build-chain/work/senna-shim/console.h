#pragma once
#include <stdint.h>

/*
 * Text console on the ABL splash framebuffer. Geometry is resolved at run
 * time (see senna.c) because the framebuffer base/stride/pixel format of
 * senna are not yet proven.
 */

#define RED	0xffff0000U
#define BLUE	0xff0000a0U
#define WHITE	0xffffffffU
#define YELLOW	0xffffff00U
#define GREEN	0xff00ff00U
#define BLACK	0xff000000U
#define CYAN	0xff00ffffU
#define MAGENTA	0xffff00ffU

extern volatile uint32_t *con_fb;
extern uint32_t con_w, con_h, con_stride;	/* stride in bytes */
extern uint32_t con_swap_rb;			/* 1 => framebuffer is BGR */

void con_setup(volatile uint32_t *fb, uint32_t w, uint32_t h, uint32_t stride_bytes, int swap_rb);
void con_clear(uint32_t bg);
void con_skip(void);
void con_str(const char *label, const char *s);
void con_hex(const char *label, uint64_t v);
void con_hex2(const char *label, const char *a, uint32_t va, const char *b, uint32_t vb);
void con_title(const char *s, uint32_t fg, uint32_t bg);
