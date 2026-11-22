/*
 * senna-b diagnostic boot shim.
 *
 * ABL loads this image via fastboot boot, enters at EL1 with MMU and
 * D-cache off, x0 = DTB. We probe the platform, then hand the device back
 * with PSCI SYSTEM_RESET.
 *
 * Output channel (v0.4): the panel is a DSI command-mode panel
 * (nt37705 ..._dsc_cmd), so the ABL splash framebuffer is not scanned out
 * continuously -- painting it is invisible (v0.2/v0.3 left the screen on
 * the ABL logo for the whole run). Results are therefore written as plain
 * text into the ramoops console zone, which the next Linux boot exposes as
 * /sys/fs/pstore/console-ramoops-0. dmesg on this device prints
 * "ramoops: using 0x240000@0xa7a5c0000, ecc: 0", i.e. no ECC and a stable
 * base, so a plain persistent_ram header is enough.
 *
 * Deliberate limits: no IMEM/PMIC/UFS writes; the side effects are the
 * invisible framebuffer pixels, the ramoops text and the PSCI reset.
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

/* probe results, filled by probe_all() */
static uint64_t g_dtb;
static uint64_t g_dtbmagic;
static uint64_t g_psci;
static uint64_t g_gicd_pidr2, g_gicd_typer;
static uint64_t g_gicr0_typer_lo, g_gicr0_typer_hi;
static uint64_t g_rd_1000, g_rd_1040;
static uint64_t g_imem;
static uint64_t g_fbrw;

/* ---- ramoops text channel ---------------------------------------- */

#define SENNA_RAMOOPS_BASE	0x0a7a5c0000UL	/* dmesg "ramoops: using ...", stable over 2 boots */
#define RAMOOPS_MAGIC		0x43474244U	/* persistent_ram_buffer.sig */
#define RAMOOPS_SMEAR		0x200000L	/* +/- 2 MiB around the base, 4 KiB steps */

static char rb[1200];
static uint32_t rblen;

static void rb_ch(char c)
{
	if (rblen < sizeof(rb) - 1)
		rb[rblen++] = c;
}

static void rb_s(const char *s)
{
	while (*s)
		rb_ch(*s++);
}

static void rb_hexn(uint64_t v, int digits)
{
	static const char d[] = "0123456789ABCDEF";
	for (int i = digits - 1; i >= 0; i--)
		rb_ch(d[(v >> (4 * i)) & 0xf]);
}

static void rb_line(const char *tag, const char *sep, uint64_t a, uint64_t b)
{
	rb_s(tag);
	rb_ch(' ');
	rb_hexn(a, 16);
	if (sep) {
		rb_ch(' ');
		rb_s(sep);
		rb_ch(' ');
		rb_hexn(b, 16);
	}
	rb_ch('\n');
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

static void draw_info(void)
{
	char b[17];

	con_clear(0xff101418U);
	con_title(" SENNA SHIM v0.4  (diag, RAM only) ", WHITE, 0xff003060U);

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

	con_title(" results -> ramoops console zone ",
		  WHITE, 0xff007040U);
	con_str("NOTE", "panel is cmd-mode: this page is invisible");
	con_str("TEXT", "written to pstore, read back after boot");
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

static void payload_build(void)
{
	rblen = 0;
	rb_s("SENNA SHIM v0.4 RAMOOPS PROBE (RAM-only, fastboot boot)\n");
	rb_line("DTB", "MAGIC", g_dtb, g_dtbmagic);
	rb_line("EL", "MPIDR", rd_currentel(), rd_mpidr());
	rb_line("SCTLR", "PFR0", rd_sctlr(), rd_pfr0());
	rb_line("CNTFRQ", "CNTPCT", rd_cntfrq(), rd_cntpct());
	rb_line("CNTVCTL", "PSCI", rd_cntv_ctl(), g_psci);
	rb_line("GICD_PIDR2", "GICD_TYPER", g_gicd_pidr2, g_gicd_typer);
	rb_line("GICR_TYPER0", "GICR_TYPER0_HI", g_gicr0_typer_lo, g_gicr0_typer_hi);
	rb_line("ICC_SRE", "ICC_CTLR", rd_icc_sre(), rd_icc_ctlr());
	rb_line("RD_1000000", "RD_1040000", g_rd_1000, g_rd_1040);
	rb_line("IMEM_RR_146AA65C", "FB_RW", g_imem, g_fbrw);
	rb_line("PSCI_SYSTEM_RESET_ID", "PSCI_SYSTEM_RESET2_ID",
		PSCI_SYSTEM_RESET, PSCI_SYSTEM_RESET2);
	rb_line("SPLASH_BASE", "SPLASH_SIZE", SENNA_SPLASH_BASE, SENNA_SPLASH_SIZE);
	rb_s("RAMOOPS_BASE ");
	rb_hexn(SENNA_RAMOOPS_BASE, 16);
	rb_s("\nEND\n");
}

/*
 * persistent_ram_buffer = { u32 sig; u32 start; u32 size; u8 data[]; }
 * The console zone starts at the ramoops base and no ECC is configured.
 * Because the base is chosen by Linux at boot (the DT node has no reg), we
 * stamp the same header on every 4 KiB page in a +/- 2 MiB window and let
 * the next boot pick the page it actually reserved.
 */
static void ramoops_write(void)
{
	for (int64_t off = -RAMOOPS_SMEAR; off <= RAMOOPS_SMEAR; off += 0x1000) {
		volatile uint32_t *h = (volatile uint32_t *)(SENNA_RAMOOPS_BASE + off);
		volatile char *d = (volatile char *)(SENNA_RAMOOPS_BASE + off + 12);
		for (uint32_t i = 0; i < rblen; i++)
			d[i] = rb[i];
		h[0] = RAMOOPS_MAGIC;
		h[1] = 0;
		h[2] = rblen;
	}
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

	if (con_ready)
		draw_info();

	payload_build();
	ramoops_write();

	/* give the store time to drain before we reset */
	wait_ms(3000);

	psci(PSCI_SYSTEM_RESET);
	psci(PSCI_SYSTEM_RESET2);
	for (;;)
		__asm__ volatile("wfe");
}
