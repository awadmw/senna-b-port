/*
 * Minimal text console on the ABL splash framebuffer.
 * MMU is off while the shim runs, so every access is Device memory:
 * keep all stores aligned and word-sized (-mstrict-align).
 */
#include "console.h"
#include "font.h"

#define SCALE		3
#define CH_W		(8 * SCALE)
#define CH_H		(16 * SCALE)
#define MARGIN		24
#define LABEL_COLS	8

volatile uint32_t *con_fb;
uint32_t con_w, con_h, con_stride, con_swap_rb;
static uint32_t con_bg;
static int row;

static inline uint32_t px(uint32_t c)
{
	if (!con_swap_rb)
		return c;
	return (c & 0xff00ff00U) | ((c & 0x00ff0000U) >> 16) | ((c & 0x000000ffU) << 16);
}

void con_setup(volatile uint32_t *fb, uint32_t w, uint32_t h, uint32_t stride_bytes, int swap_rb)
{
	con_fb = fb;
	con_w = w;
	con_h = h;
	con_stride = stride_bytes;
	con_swap_rb = swap_rb ? 1 : 0;
	row = 0;
}

void con_clear(uint32_t bg)
{
	uint32_t c = px(bg);
	for (uint32_t y = 0; y < con_h; y++) {
		volatile uint32_t *line = con_fb + (uint64_t)y * (con_stride / 4);
		for (uint32_t x = 0; x < con_w; x++)
			line[x] = c;
	}
	con_bg = bg;
	row = 0;
}

static void put_char(int col, char ch, uint32_t fg)
{
	if (ch < 0x20 || ch > 0x7e)
		ch = '?';
	const unsigned char *g = font8x16[ch - 0x20];
	uint32_t x0 = MARGIN + (uint32_t)col * CH_W, y0 = MARGIN + (uint32_t)row * CH_H;
	if (x0 + CH_W > con_w || y0 + CH_H > con_h)
		return;
	for (int gy = 0; gy < 16; gy++)
		for (int gx = 0; gx < 8; gx++) {
			uint32_t c = px((g[gy] & (0x80 >> gx)) ? fg : con_bg);
			for (int sy = 0; sy < SCALE; sy++) {
				volatile uint32_t *p = con_fb + (uint64_t)(y0 + gy * SCALE + sy) * (con_stride / 4)
						       + x0 + gx * SCALE;
				for (int sx = 0; sx < SCALE; sx++)
					p[sx] = c;
			}
		}
}

static int put_str(int col, const char *s, uint32_t fg)
{
	while (*s)
		put_char(col++, *s++, fg);
	return col;
}

static void fmt_hex(char *buf, uint64_t v, int digits)
{
	static const char hex[] = "0123456789ABCDEF";
	for (int i = 0; i < digits; i++)
		buf[i] = hex[(v >> (4 * (digits - 1 - i))) & 0xf];
	buf[digits] = 0;
}

void con_skip(void)
{
	row++;
}

void con_title(const char *s, uint32_t fg, uint32_t bg)
{
	con_bg = bg;
	put_str(0, s, fg);
	row++;
}

void con_str(const char *label, const char *s)
{
	put_str(0, label, YELLOW);
	put_str(LABEL_COLS, s, WHITE);
	row++;
}

void con_hex(const char *label, uint64_t v)
{
	char buf[17];
	fmt_hex(buf, v, 16);
	con_str(label, buf);
}

void con_hex2(const char *label, const char *a, uint32_t va, const char *b, uint32_t vb)
{
	char buf[9];
	int col = put_str(0, label, YELLOW);
	col = col < LABEL_COLS ? LABEL_COLS : col + 1;
	col = put_str(col, a, YELLOW);
	fmt_hex(buf, va, 8);
	col = put_str(col, buf, WHITE);
	if (b) {
		col = put_str(col + 1, b, YELLOW);
		fmt_hex(buf, vb, 8);
		put_str(col, buf, WHITE);
	}
	row++;
}
