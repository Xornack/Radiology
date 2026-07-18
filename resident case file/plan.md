# Resident Case File — OHIF on GitHub Pages

**Goal:** a zero-install teaching-file website for the residents. They click a link
(pinned in the existing residency Google Drive folder), a browser-based DICOM viewer
opens with curated, anonymized cases. No server to maintain, no logins to administer.

**Decision (2026-07-17):** use [OHIF Viewer](https://github.com/OHIF/Viewers) as-is —
no fork. It's MIT-licensed ([license](https://github.com/OHIF/Viewers/blob/master/LICENSE)),
actively maintained, and designed to be customized through config files,
[modes](https://docs.ohif.org/platform/modes/), and
[extensions](https://docs.ohif.org/platform/extensions/) without touching core code.
Desktop RustRadStack stays the daily/conference viewer; this is a separate distribution
channel for teaching.

## Architecture

```
┌─ Google Drive folder (residency) ─┐
│  "Case File" doc → just a link    │   ← access/discovery stays where residents already look
└───────────────┬───────────────────┘
                ▼
┌─ GitHub Pages (static site) ──────────────────────────┐
│  /           OHIF build (HTML/JS/WASM, ~tens of MB)   │
│  /dicomweb/  static DICOMweb tree (one per study):    │
│              studies index JSON + per-frame files,    │
│              generated offline by static-wado         │
└───────────────────────────────────────────────────────┘
```

No PACS, no DICOMweb server — [static-wado](https://github.com/RadicalImaging/static-wado)
precomputes everything a DICOMweb client needs as plain files, and OHIF reads them like
any static asset.

## Phases

Each phase ends with a working, verifiable result before starting the next.

### Phase 1 — Prove the pipeline with one case (local)
1. Install Node.js LTS + yarn (OHIF and static-wado are Node tools).
2. Pick ONE case; anonymize it (see PHI checklist below).
3. Run static-wado's `mkdicomweb` on the anonymized study → a folder of DICOMweb files.
4. Clone OHIF, run its dev server, point its data-source config at the local folder.
5. **Verify:** the case opens, scrolls, and window/levels in a browser on your machine.

### Phase 2 — First deployment
1. Create a GitHub repo (`resident-case-file` or similar).
2. Build OHIF for production (static bundle) and commit it + the `dicomweb/` tree.
3. Enable GitHub Pages; set OHIF's `app-config.js` data source to the Pages URL.
4. **Verify:** the case opens on your phone, on hospital Wi-Fi, from the public URL.

### Phase 3 — Case library + worklist
1. Add remaining anonymized cases through the same static-wado step.
2. static-wado maintains the studies index JSON that OHIF's worklist reads — confirm
   the study list shows patient-less, teaching-appropriate labels (use the anonymized
   PatientName field as the case title, e.g. "Case 07 — adrenal incidentaloma").
3. **Verify:** a resident-eye walkthrough — can someone find and open a case in
   under 30 seconds with zero instructions?

### Phase 4 — Share
1. One Google Doc in the residency Drive folder: title, one-line description, link.
2. Optionally a custom domain later (Pages supports it; keeps the link stable forever).

### Phase 5 — Only if needed
- **Cosmetics/workflow:** OHIF config first (logo, default tools), then a custom
  [mode](https://docs.ohif.org/platform/modes/) — still no fork.
- **Library outgrows 1 GB:** keep the viewer on Pages, move `dicomweb/` bulk data to
  [Cloudflare R2](https://developers.cloudflare.com/r2/) (10 GB free storage, free
  egress) behind a custom domain, and repoint the data-source URL. Nothing else changes.
- **Real access control:** GitHub Pages sites are public even when built from a
  private repo (visibility-restricted Pages is an Enterprise feature). If "unlisted
  URL" ever stops being enough, put [Cloudflare Access](https://developers.cloudflare.com/cloudflare-one/policies/access/)
  in front (free tier covers a residency's headcount) — residents authenticate with
  their Google accounts, which loops back to the "controlled by my Google list" idea.

## Hosting limits (the traffic question)

From the official [GitHub Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits):

| Limit | Value | Impact here |
|---|---|---|
| Bandwidth | **100 GB/month (soft)** | ~1,000 full-case views/month at ~100 MB per case — plenty for a residency. Exceeding a soft limit gets a polite email, not an outage. |
| Site/repo size | **~1 GB recommended** | The real constraint. Caps the library at roughly 5–15 curated cases depending on series pruning. Phase 5 (R2) lifts this. |
| Builds | 10/hour (soft) | Irrelevant — cases change rarely. |
| Per-file size | 100 MB hard (git) | Fine — static-wado emits per-frame files, typically well under 1 MB each. |

There is **no per-visit limit**. GitHub Pro's benefit here is minor (Pages from a
private repo — but the published site is public regardless).

**Bandwidth math:** 30 residents × 10 case-views/week × ~100 MB ≈ 52 GB/month —
comfortably inside the soft limit. Curating series (don't ship the whole exam) keeps
both bandwidth and the 1 GB size cap happy, and is good teaching-file practice anyway.

## PHI checklist (non-negotiable, per case)

DICOM tags carry PHI even when the pixels look anonymous. Before a case leaves the
workstation:

- [ ] PatientName / PatientID / PatientBirthDate replaced (name becomes the case title)
- [ ] All dates shifted or blanked (StudyDate, SeriesDate, AcquisitionDate…)
- [ ] AccessionNumber, InstitutionName, ReferringPhysicianName, StationName cleared
- [ ] Private tags stripped; UIDs regenerated
- [ ] Burned-in annotations checked visually (US, secondary captures, dose sheets!)
- [ ] Verified with a tag dump (e.g. `dcmdump` from dcm4che, or a future
      "export anonymized case" feature in RustRadStack) — not just by eyeballing images

The published site is on the open internet; treat every case as if it will be indexed.

## Links

- OHIF Viewer repo: <https://github.com/OHIF/Viewers> (MIT [license](https://github.com/OHIF/Viewers/blob/master/LICENSE))
- OHIF docs: <https://docs.ohif.org/> (modes, extensions, deployment, data sources)
- static-wado (DICOM → static DICOMweb): <https://github.com/RadicalImaging/static-wado>
- GitHub Pages limits: <https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits>
- Cloudflare R2 (growth path): <https://developers.cloudflare.com/r2/>
- Cloudflare Access (auth, if ever needed): <https://developers.cloudflare.com/cloudflare-one/policies/access/>
- dcm4che tools (tag dumps / de-identification): <https://github.com/dcm4che/dcm4che>
