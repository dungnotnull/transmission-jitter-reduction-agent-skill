# references/rfc-index.md -- authoritative RFC/IEEE standard index

The authoritative standards grounding the domain metrics. Each `tjr` function
traces to one or more of these. The crawl pipeline (`tjr.knowledge_updater`)
and `SECOND-KNOWLEDGE-BRAIN.md` cite these as Tier 1.

## IETF RFCs

| RFC | Title | Grounds |
|-----|-------|---------|
| RFC 3550 | RTP: A Transport Protocol for Real-Time Applications | Interarrival jitter (gain 1/16) -- `rtp_jitter` |
| RFC 3393 | IP Packet Delay Variation | PDV range form -- `packet_delay_variation` |
| RFC 8289 | CoDel: Controlled-Delay Active Queue Management | Bufferbloat grading scale -- `bufferbloat_grade` |
| RFC 8290 | FQ-CoDel: Fair Queuing + CoDel | AQM recommendation (FQ-CoDel) -- `aqm_recommend` |
| RFC 8033 | PIE: Proportional Integral Controller Enhanced AQM | AQM alternative -- `aqm_recommend` rationale |
| RFC 8325 | Using DSCP for Real-Time Traffic (CAKE guidance) | Diffserv-aware AQM tiering |
| RFC 8888 | FQ-PIE | Low-latency AQM variant |
| RFC 9330 | L4S: Low Latency, Low Loss, Scalable Throughput | SOTA dual-queue (PIE/FQ-CoDel) |
| RFC 2474 | DSCP field definition | DSCP base classes -- `dscp_marking` |
| RFC 3246 | Expedited Forwarding (EF) | Voice marking DSCP 46 -- `dscp_marking` |
| RFC 2597 | Assured Forwarding (AF) | Game marking AF41 (DSCP 34) -- `dscp_marking` |

## IEEE standards

| Standard | Title | Grounds |
|----------|-------|---------|
| IEEE 802.11e | WMM QoS for Wi-Fi | WMM access categories (AC_VO/AC_VI/AC_BE/AC_BK) -- `dscp_marking`, `wifi_channel_recommend` |
| IEEE 802.11ax (Wi-Fi 6) | High-efficiency WLAN | 5/6 GHz channel selection, WMM-AC |
| IEEE 802.11be (Wi-Fi 7) | EHT / multi-link operation | SOTA Wi-Fi tuning |

## Key academic references (Tier 2)

| Authors | Year | Venue | Topic |
|---------|------|-------|-------|
| Nichols & Jacobson | 2012 | ACM Queue | Controlling Queue Delay (CoDel) |
| Hoeiland-Jorgensen et al. | 2018 | ACM Queue / IETF | FQ-CoDel scheduler |
| Cardwell et al. | 2016 | ACM Queue | BBR congestion control |
| Claypool & Claypool | 2005 | Commun. ACM / NetGames | Latency & player actions in online games |
| Hollot, Misra, Towsley, Gong | 2001 | IEEE/ACM ToN | Queueing-theoretic AQM model |

## Measurement tool references (Tier 3)

- Wireshark, iputils `ping`, `mtr`, `tcpdump`, OONI Probe, `iperf3`
  (latency under load), DSLReports speedtest/bufferbloat grade.
- Router firmware: OpenWrt (`sqm-scripts`), DD-WRT, Asuswrt-Merlin,
  pfSense/OPNsense.
- ISP/peering: PeeringDB, RIPE Atlas, MTR path analysis.