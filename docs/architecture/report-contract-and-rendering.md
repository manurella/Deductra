# Report Contract and Rendering

Last reviewed: 2026-07-16

`ReportModel` is the sole authoritative report representation. HTML, PDF, visuals, and
attachments are derived delivery artifacts; renderers cannot add claims, change evidence, or
exercise solver authority.

## Evidence closure

Every factual `ReportClaim` references accepted evidence present in the same model. Narrative
claims cannot masquerade as evidence-backed facts. Informative `VisualSpec` instances reference
known provenance events and provide alternative text; complex graphs also require a long
description. Attachments carry a safe filename, media type, relationship, description, content
hash, schema version, and evidence references.

The canonical section catalog is always complete and ordered. A section without relevant content
is explicitly `not_applicable`; omission is invalid.

## Theme isolation

`facts_hash` excludes `ReportTheme`, so changing styles or assets cannot change the identity of
claims, evidence, visuals, sections, attachments, or provenance. `report_hash` covers the theme
and every other field. Both hashes are verified during construction.

## HTML boundary

The packaged Jinja template uses strict undefined-value handling and automatic escaping. It
produces semantic HTML with declared language, one main landmark, a heading hierarchy, internal
evidence links, captions, and text alternatives. A structural audit rejects duplicate identifiers,
dangling links, skipped headings, incomplete figure captions, and remote resources.

## PDF boundary

`PdfRenderer` is the stable port. The WeasyPrint adapter derives standard, accessibility-targeted
PDF/UA-2, or archival PDF/A-4f output from the same HTML. Only the archive profile embeds declared,
hash-verified evidence attachments. External resource fetching is denied.

Selecting a renderer profile does not prove standards conformance. Results remain `not_checked`
until an independent validator supplies evidence. Release claims must distinguish a target profile
from verified conformance.
