#pragma once
/*
 * SENNA (RMX3706 / SM8475 / "senna-b") board constants for the boot shim.
 *
 * Every address below is cited from this device's own sources; nothing is
 * copied from another Qualcomm board:
 *   - live DTB decompiled by dtc: build-chain/artifacts/dts-roundtrip/from-binary.dts
 *   - official OTA images:       build-chain/ota-evidence/
 * Line numbers refer to that .dts file.
 */

/* GICv3: interrupt-controller@17100000, from-binary.dts:1323-1339 */
#define SENNA_GICD_BASE		0x17100000UL	/* +0x10000 */
#define SENNA_GICD_SIZE		0x10000UL
#define SENNA_GICR_BASE		0x17180000UL	/* +0x200000, stride 0x40000 */
#define SENNA_GICR_SIZE		0x200000UL
#define SENNA_GICR_STRIDE	0x40000UL	/* redistributor-stride */
#define SENNA_GIC_ITS_BASE	0x17140000UL	/* +0x20000 */

/* arch timer: timer@17420000, from-binary.dts:7481-7487 */
#define SENNA_TIMER_FREQ	19200000UL	/* clock-frequency = 0x124f800 */
#define SENNA_TIMER_CNT_BASE	0x17420000UL

/* splash / framebuffer: splash_region, from-binary.dts:412-416 */
#define SENNA_SPLASH_BASE	0xb8000000UL	/* cont_splash_region */
#define SENNA_SPLASH_SIZE	0x2b00000UL
#define SENNA_PANEL_W		1240		/* from-binary.dts:14186 */
#define SENNA_PANEL_H		2772

/* IMEM: qcom,msm-imem@146aa000, restart_reason@65c (from-binary.dts:12935-12950) */
#define SENNA_IMEM_BASE		0x146aa000UL
#define SENNA_IMEM_RESTART_REASON 0x146aa65cUL

/* GENI console UART: qcom,qup_uart@99c000 (from-binary.dts:13812-13825) */
#define SENNA_UART_BASE		0x99c000UL
#define SENNA_UART_SIZE		0x4000UL

/* UFS host: ufshc@1d84000 (from-binary.dts:12729) */
#define SENNA_UFS_BASE		0x1d84000UL

/* DRAM: /memory reg (from-binary.dts:21-25) */
#define SENNA_DRAM_BASE		0x80000000UL
#define SENNA_DRAM_SIZE		0x6a000000UL

#define SENNA_NR_CPUS		8		/* from-binary.dts:492- */

/* PSCI 1.0 / smc (from-binary.dts:1197-1199) */
#define PSCI_VERSION		0x84000000UL
#define PSCI_CPU_SUSPEND	0xc4000001UL
#define PSCI_CPU_OFF		0x84000002UL
#define PSCI_CPU_ON		0xc4000003UL
#define PSCI_AFFINITY_INFO	0xc4000004UL
#define PSCI_MIGRATE_INFO_TYPE	0x84000006UL
#define PSCI_SYSTEM_RESET	0x84000009UL
#define PSCI_SYSTEM_RESET2	0xc4000012UL
#define PSCI_FEATURES		0x8400000aUL
#define SMCCC_VERSION		0x80000000UL
