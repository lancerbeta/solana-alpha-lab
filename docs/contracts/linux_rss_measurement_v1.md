# Linux RSS measurement boundary

Status: diagnostic phase; no acceptance yet.

The existing peak_rss_bytes consumer contract is peak resident memory used by
the current executable image. On Windows it is PeakWorkingSetSize; on macOS
ru_maxrss uses bytes. Linux ru_maxrss uses KiB and preserves usage across exec,
so the hypothesis is that it can include inherited pre-exec parent memory.
VmHWM in /proc/self/status measures the current image's resident high water.
Both are kernel RSS accounting, not unique physical allocation or process-tree
memory. Reading HWM must retain positive integer KiB -> bytes and never silently
replace malformed/missing metrics with zero. Do not subtract parent RSS, reset
high-water state, change workload, exclude true child peaks or raise resource caps.

Primary references: [Linux proc](https://docs.kernel.org/filesystems/proc.html),
[getrusage](https://www.man7.org/linux/man-pages/man2/getrusage.2.html).
Actual final behavior and raw before/after evidence will be bound after the Linux
falsifier. Historical PR384 failure is not retroactively relabelled PASS.
