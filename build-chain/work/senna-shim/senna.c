/*
 * senna-b diagnostic boot shim.
 *
 * ABL loads this image via fastboot boot, enters at EL1 with MMU and
 * D-cache off, x0 = DTB. We probe the platform, paint the results on the
 * ABL splash framebuffer, then hand the device back with PSCI SYSTEM_RESET.
 *
 * Deliberate limits:
 *   - No writes to IMEM/PMIC/UFS; the only side effects are framebuffer
 *     pixels and the final PSCI reset.
 *   - Every probe value is printed as raw hex so it can be cited as
 *     evidence for build-chain/boot-chain/DESIGN.md.
 */
#include <stdint.h>
#include "board.h"
#include "console.h"

void secondary_main(uint64_t cpu);

static volatile int con_ready;

static void hex(char *o, uint64_t v, int n)
{
	static const char d[] = "0123456789ABCDEF";
	for (int i = 0; i < n; i++)
		o[i] = d[(v >> (4 * (n - 1 - i))) & 0xf];
	o[n] = 0;
}

static void line(const char *label, const char *s)
{
	con_str(label, s);
}

#define RDSYS(fn, reg) \
static inline uint64_t fn(void) \
{ \
	uint64_t v; \
	__asm__ volatile("isb; mrs %0, " reg : "=r"(v) :: "memory"); \
	return v; \
}

RDSYS(rd_cntfrq,   "cntfrq_el0")
RDSYS(rd_cntpct,   "cntpct_el0")
RDSYS(rd_cntvct,   "cntvct_el0")
RDSYS(rd_cntv_ctl, "cntv_ctl_el0")
RDSYS(rd_mpidr,    "mpidr_el1")
RDSYS(rd_currentel, "currentel")
RDSYS(rd_sctlr,    "sctlr_el1")
RDSYS(rd_spsr,     "spsr_el1")
RDSYS(rd_esr,      "esr_el1")
RDSYS(rd_far,      "far_el1")
RDSYS(rd_elr,      "elr_el1")
RDSYS(rd_icc_sre,  "icc_sre_el1")
RDSYS(rd_icc_ctlr, "icc_ctlr_el1")
RDSYS(rd_pfr0,     "id_aa64pfr0_el1")

static uint64_t psci(uint64_t fn)
{
	register uint64_t x0 __asm__("x0") = fn;
	register uint64_t x1 __asm__("x1") = 0;
	register uint64_t x2 __asm__("x2") = 0;
	register uint64_t x3 __asm__("x3") = 0;
	__asm__ volatile("smc #0" : "+r"(x0), "+r"(x1), "+r"(x2), "+r"(x3)
			 : : "x4", "x5", "x6", "x7", "x8", "x9", "x10", "x11",
			     "x12", "x13", "x14", "x15", "x16", "x17", "memory");
	return x0;
}

static inline uint32_t rd32(uint64_t p)
{
	return *(volatile uint32_t *)p;
}

static void wait_ms(uint32_t ms)
{
	uint64_t f = rd_cntfrq();
	uint64_t t = rd_cntpct() + f / 1000 * ms;
	while (rd_cntpct() < t)
		;
}

struct fbcand {
	uint32_t stride;
	uint32_t w;
	uint32_t swap;
	const char *name;
};

static const struct fbcand cands[] = {
	{ SENNA_PANEL_W * 4, SENNA_PANEL_W, 0, "rgba/4960" },
	{ SENNA_PANEL_W * 4, SENNA_PANEL_W, 1, "bgra/4960" },
	{ 5120,		  SENNA_PANEL_W, 0, "rgba/5120" },
	{ 4992,		  SENNA_PANEL_W, 0, "rgba/4992" },
};
#define NCAND ((int)(sizeof(cands) / sizeof(cands[0])))

static void fb_use(int i)
{
	con_setup((volatile uint32_t *)SENNA_SPLASH_BASE, cands[i].w,
		  SENNA_PANEL_H, cands[i].stride, cands[i].swap);
}

static void bar(uint32_t y, uint32_t h, uint32_t rgb)
{
	volatile uint32_t *fb = con_fb;
	uint32_t c = rgb;
	for (uint32_t yy = y; yy < y + h && yy < con_h; yy++) {
		volatile uint32_t *p = fb + (uint64_t)yy * (con_stride / 4);
		for (uint32_t x = 0; x < con_w; x++)
			p[x] = c;
	}
}

static uint64_t g_dtb;
static uint64_t g_dtbmagic;
static uint64_t g_psci;
static uint64_t g_gicd_pidr2, g_gicd_typer;
static uint64_t g_gicr0_typer_lo, g_gicr0_typer_hi;
static uint64_t g_rd_1000, g_rd_1040;
static uint64_t g_imem;
static uint64_t g_fbrw;

static void probe_all(void)
{
	g_psci = psci(PSCI_VERSION);
	g_gicd_pidr2 = rd32(SENNA_GICD_BASE + 0xffe8);
	g_gicd_typer = rd32(SENNA_GICD_BASE + 0x0004);
	g_gicr0_typer_lo = *(volatile uint64_t *)(SENNA_GICR_BASE + 0x0008);
	g_gicr0_typer_hi = *(volatile uint64_t *)(SENNA_GICR_BASE + 0x0010);
	g_rd_1000 = *(volatile uint64_t *)0x1000000UL;
	g_rd_1040 = *(volatile uint64_t *)0x1040000UL;
	g_imem = rd32(SENNA_IMEM_RESTART_REASON);
}

static void draw_info(int final, int secs)
{
	char b[17];

	con_clear(0xff101418U);
	con_title(" SENNA SHIM v0.3  (diag, RAM only) ", WHITE, 0xff003060U);

	con_str("BUILD", "senna-shim running at EL1, MMU off");
	line("DTB", "x0 / magic:");
	con_hex("", g_dtb);
	con_hex("", g_dtbmagic);
	con_skip();
	con_str("EL", "currentel / mpidr / sctlr:");
	con_hex("", rd_currentel());
	con_hex("", rd_mpidr());
	con_hex("", rd_sctlr());
	con_skip();
	con_str("TIMER", "cntfrq / cntpct / cntvctl:");
	con_hex("", rd_cntfrq());
	con_hex("", rd_cntpct());
	con_hex("", rd_cntv_ctl());
	con_skip();
	con_str("PSCI", "version / system-reset id:");
	con_hex("", g_psci);
	con_hex("", PSCI_SYSTEM_RESET);
	con_skip();
	con_str("GICD", "pidr2 / typer:");
	con_hex("", g_gicd_pidr2);
	con_hex("", g_gicd_typer);
	con_str("GICR0", "typer lo / hi:");
	con_hex("", g_gicr0_typer_lo);
	con_hex("", g_gicr0_typer_hi);
	con_str("ICC", "sre / ctlr:");
	con_hex("", rd_icc_sre());
	con_hex("", rd_icc_ctlr());
	con_skip();
	con_str("RAMDISK", "@0x1000000 / @0x1040000:");
	con_hex("", g_rd_1000);
	con_hex("", g_rd_1040);
	con_str("IMEM", "restart_reason @146aa65c:");
	con_hex("", g_imem);
	con_skip();
	con_str("FB", "base, stride, readback:");
	con_hex("", SENNA_SPLASH_BASE);
	hex(b, cands[0].stride, 8);
	con_str("", b);
	con_str("", g_fbrw ? "readback=OK" : "readback=MISMATCH");
	con_skip();

	if (final) {
		con_title(" ALL PROBES DONE - reboot in 30s ",
			  BLACK, 0xffffff00U);
		hex(b, (uint64_t)secs, 2);
		con_str("COUNTDOWN", b);
	} else {
		con_title(" PHASE 1: FB CANDIDATES - watch screen colours ",
			  WHITE, 0xff007040U);
		con_str("NEXT", "4 framebuffer groups, 45s each");
		con_str("CAPTURE", "photo this page now");
	}
}

static void draw_group(int i)
{
	char b[8];
	int col = i == 0 ? 0xff200000U : (i == 1 ? 0xff002000U
		 : (i == 2 ? 0xff202000U : 0xff200020U));

	fb_use(i);
	con_clear(col);
	con_title(" FB GROUP PROBE ", WHITE, 0xff000000U);
	hex(b, (uint64_t)(i + 1), 2);
	con_str("GROUP", b);
	hex(b, cands[i].stride, 4);
	con_str("STRIDE", b);
	con_str("FORMAT", cands[i].name);
	con_skip();
	con_str("BARS", "RED GREEN BLUE WHITE");

	bar(con_h - 240, 60, 0x00ff0000U);
	bar(con_h - 180, 60, 0x0000ff00U);
	bar(con_h - 120, 60, 0x000000ffU);
	bar(con_h - 60,  60, 0x00ffffffU);

	con_str("NOTE", "stop when a group is legible");
	con_str("", "then take a photo");
}

void exc_handler(uint64_t slot, uint64_t *regs)
{
	char b[17];

	con_ready = 1;
	fb_use(0);
	con_clear(0xff300000U);
	con_title(" !! SENNA SHIM PANIC !! ", WHITE, 0xff600000U);
	hex(b, slot, 2);
	con_str("SLOT", b);
	con_hex("ESR ", rd_esr());
	con_hex("FAR ", rd_far());
	con_hex("ELR ", rd_elr());
	con_hex("SPSR", rd_spsr());
	con_hex("SP  ", (uint64_t)(uintptr_t)regs);
	con_skip();
	for (int i = 0; i < 8; i++) {
		hex(b, regs[i], 16);
		con_str(i == 0 ? "x0.." : "", b);
	}
	con_str("HALT", "wfe loop (power-cycle to exit)");
	for (;;)
		__asm__ volatile("wfe");
}

void secondary_main(uint64_t cpu)
{
	(void)cpu;
	for (;;)
		__asm__ volatile("wfe");
}

void shim_main(uint64_t dtb)
{
	g_dtb = dtb;
	g_dtbmagic = (dtb && (dtb & 7) == 0) ? rd32(dtb) : 0;

	con_ready = 1;
	fb_use(0);
	con_clear(0xff101418U);

	probe_all();

	con_fb[0] = 0x00a5a5a5U;
	g_fbrw = (con_fb[0] == 0x00a5a5a5U);

	draw_info(0, 0);
	wait_ms(60000);

	for (int i = 0; i < NCAND; i++) {
		draw_group(i);
		wait_ms(45000);
	}

	fb_use(0);
	for (int s = 30; s > 0; s--) {
		/* a full-screen clear costs ~0.1 s uncached, so only redraw
		 * every 5 s; the countdown stays readable either way */
		if (s == 30 || s % 5 == 0 || s == 1)
			draw_info(1, s);
		wait_ms(1000);
	}

	psci(PSCI_SYSTEM_RESET);
	psci(PSCI_SYSTEM_RESET2);
	for (;;)
		__asm__ volatile("wfe");
}
