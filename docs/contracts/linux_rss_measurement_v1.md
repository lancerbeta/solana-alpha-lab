# Linux RSS measurement boundary

Status: implemented; exact-head delivery validation remains separately gated.

The existing peak_rss_bytes consumer contract is peak resident memory used by
the current executable image. On Windows it is PeakWorkingSetSize; on macOS
ru_maxrss uses bytes. Linux ru_maxrss uses KiB and preserves usage across exec,
so it can include inherited pre-exec parent memory. The unchanged-workload
Actions proof37714107620 confirmed this with a retained600 MiB parent.
VmHWM in /proc/self/status measures the current image's resident high water.
Both are kernel RSS accounting, not unique physical allocation or process-tree
memory. Kernel RSS accounting is approximate; this gate uses the kernel's
current-image high-water value. Reading HWM must retain positive integer KiB -> bytes and never silently
replace malformed/missing metrics with zero. Do not subtract parent RSS, reset
high-water state, change workload, exclude true child peaks or raise resource caps.

Primary references: [Linux proc](https://docs.kernel.org/filesystems/proc.html),
[getrusage](https://www.man7.org/linux/man-pages/man2/getrusage.2.html).
Linux requires the exact VmHWM: field name and a single positive integer in
canonical kB converted to bytes.
Unavailable, unreadable, malformed, duplicate or nonpositive HWM retains the
old conservative getrusage peak; if that fallback is nonpositive, raise
PEAK_RSS_UNAVAILABLE. Windows/macOS behavior and512/768 MiB limits are unchanged.
Raw before/after evidence lives in Actions and the bounded delivery PR.
Historical PR384 failure is not retroactively relabelled PASS.
