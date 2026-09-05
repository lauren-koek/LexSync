# Internal Document Ingestion and Semantic Search Design

## Summary

LexSync will add a shared Internal Documents workspace where users can upload PDF documents, browse everything previously uploaded, semantically search the library, and open a document in a split view. Upload processing is synchronous: the API validates and extracts the PDF, stores the original in AWS-compatible object storage, chunks and embeds the extracted text, and persists the document and vectors in PostgreSQL with pgvector before returning success.

The MAS regulatory pipeline will use the same persistent vector index after it processes a regulatory document. It will find relevant internal clauses, generate proposed changes, and save the suggestions. Users can also manually re-run this analysis. Authentication, per-user ownership, and document sharing controls are outside this release; the library is global.

## Goals

- Provide a new `Internal Documents` sidebar destination listing all uploaded documents.
- Let a user upload a PDF and receive a definite indexed result or a specific failure in the same request.
- Retain the original PDF in AWS-compatible object storage configured for Railway.
- Persist document metadata, extracted clauses, and 384-dimension embeddings in PostgreSQL/pgvector.
- Support semantic search across internal documents and return the most relevant excerpts.
- Open a selected document in a split view containing the original PDF and document information, clauses, and suggested changes.
- Automatically analyze newly processed regulatory documents against the internal-document index.
- Allow manual re-analysis and persistent review states for suggestions.

## Non-goals

- Authentication, user ownership, tenants, or access-control rules.
- Background queues, worker services, resumable uploads, or direct browser-to-bucket uploads.
- Non-PDF internal-document formats.
- OCR for image-only uploaded PDFs in the first release.
- Editing the original PDF or applying accepted redlines directly to its binary contents.
- Migrating the existing request-local `/analysis` workflow to this library.

## Architecture

### Components

1. `backend/analysis/internal_documents.py` owns upload validation, extraction, chunking, duplicate detection, and orchestration.
2. `backend/storage/objects.py` defines the object-storage interface and an S3-compatible implementation. It reads `AWS_ENDPOINT_URL`, `S3_BUCKET_NAME`, `AWS_DEFAULT_REGION`, `AWS_ACCESS_KEY_ID`, and `AWS_SECRET_ACCESS_KEY`.
3. `internal_index.py` remains the pgvector boundary and is expanded to index UUID-backed documents and perform general semantic search.
4. `backend/analysis/suggestions.py` vector-matches regulatory clauses, runs structured impact analysis, and persists suggestion rows.
5. FastAPI routes expose internal-document CRUD, PDF access, semantic search, suggestion review, and re-analysis.
6. `backend/pipeline.py` invokes suggestion generation after a regulatory document has OCR text and has been saved.
7. The React app adds an Internal Documents library and a split document-detail view.

The backend receives the multipart upload instead of issuing a direct-to-bucket URL. This keeps immediate validation and ingestion in one API operation and avoids abandoned uploads and a second finalize request. Binary storage remains isolated behind an adapter so the ingestion service does not depend directly on boto3.

### Configuration

Production uses the following required variables:

- `AWS_ENDPOINT_URL`
- `S3_BUCKET_NAME`
- `AWS_DEFAULT_REGION`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

The S3 client uses virtual-hosted addressing supported by Railway Buckets. Tests inject an in-memory fake storage implementation and never contact object storage. Missing production configuration causes an explicit service-configuration error rather than silently storing files on ephemeral disk.

## Persistence Model

### `internal_documents`

- `id`: UUID primary key.
- `title`: user-facing title, defaulting to the filename without its suffix.
- `filename`: sanitized original filename.
- `object_key`: unique, opaque object-storage key.
- `content_type`: must be `application/pdf` after validation.
- `size_bytes`: uploaded byte count.
- `sha256`: lowercase content digest with a unique constraint for deduplication.
- `status`: `indexed` or `failed`. Because processing is synchronous and writes are atomic, normal list results are `indexed`; `failed` is reserved for an explicitly persisted operational failure if introduced later.
- `error_message`: nullable diagnostic field.
- `chunk_count`: number of indexed chunks.
- `created_at`, `updated_at`: timezone-aware timestamps.

### `internal_document_chunks`

The existing table is migrated from a free-text `doc_id` to `internal_document_id`, a UUID foreign key referencing `internal_documents.id` with cascade deletion. It retains `title`, `clause_reference`, `content`, `embedding vector(384)`, and `created_at`. The existing HNSW cosine index remains.

### `document_suggestions`

- `id`: UUID primary key.
- `regulatory_document_id`: foreign key to `documents.id`, cascade on regulatory deletion.
- `internal_document_id`: foreign key to `internal_documents.id`, cascade on internal-document deletion.
- `internal_chunk_id`: foreign key to `internal_document_chunks.id`, cascade on internal-document deletion.
- `regulation_clause_reference` and `regulation_content`: snapshot the regulatory clause analyzed.
- `similarity_score`: cosine similarity used to select the match.
- `is_affected`, `impact_score`, `legal_reasoning`, `proposed_amended_clause`, `statutory_citations`, `redline_diff`, and `analysis_source`: persisted analysis output.
- `status`: `pending`, `accepted`, or `dismissed`.
- `created_at`, `updated_at`: timezone-aware timestamps.

A unique key over regulatory document, regulation clause reference, and internal chunk prevents duplicate pending work across repeated batch runs.

## Upload and Ingestion Flow

1. The client submits one PDF and an optional display title to `POST /api/v1/internal-documents` as multipart form data.
2. The API enforces the existing 10 MB limit, requires a `.pdf` filename, verifies both PDF signature and MIME type, and rejects malformed, encrypted, blank, and image-only PDFs with a specific 422 response.
3. The service reads the bytes once, calculates SHA-256, and returns the existing indexed document with `deduplicated: true` when the digest already exists.
4. `pdfplumber` extracts text. The shared legal-aware chunker produces clause-based chunks with word-window fallback.
5. All chunks are embedded using the existing 384-dimension embedding function. An embedding with the wrong dimension fails the request.
6. The original PDF is uploaded using an object key shaped as `internal-documents/<document-uuid>/<sanitized-filename>`.
7. One database transaction inserts the parent document and all chunks. It commits only after every chunk is ready.
8. If database persistence fails after object upload, the service attempts to delete that exact newly created object and returns failure. It never deletes an existing object during compensation.
9. The API returns the complete document summary only after indexing succeeds.

## Internal Document API

- `POST /api/v1/internal-documents`: upload and synchronously index a PDF; returns 201 for a new document and 200 with `deduplicated: true` for identical existing content.
- `GET /api/v1/internal-documents`: list documents newest first, with optional case-insensitive metadata query and pagination.
- `GET /api/v1/internal-documents/{id}`: return metadata, ordered extracted clauses, and persisted suggestions.
- `GET /api/v1/internal-documents/{id}/pdf-url`: return a short-lived presigned GET URL. The database never stores a public URL.
- `DELETE /api/v1/internal-documents/{id}`: delete the S3 object and database record. A missing object is treated as already deleted; other storage failures leave the database intact and return an error.
- `POST /api/v1/internal-documents/search`: embed a non-blank query, run cosine vector search, collapse chunk hits by document, and return best-scoring documents with relevant excerpts.
- `POST /api/v1/internal-documents/{id}/reanalyze`: regenerate pending suggestions for one internal document against saved regulatory documents.
- `PATCH /api/v1/document-suggestions/{id}`: change review status among `pending`, `accepted`, and `dismissed`.
- `POST /api/v1/documents/{id}/reanalyze`: regenerate pending suggestions for one regulatory document against all indexed internal documents.

List and search responses are bounded and paginated. Search defaults to 10 documents and never returns below the configured similarity threshold. Each document result includes at most three excerpts.

## Semantic Retrieval and Suggestions

Semantic search embeds the query once, orders chunk rows using pgvector cosine distance, filters by the similarity threshold, and over-fetches chunks before grouping by internal document. The highest similarity becomes the document score, and its top distinct chunks become excerpts.

Suggestion generation chunks the saved regulatory document's OCR text as `REGULATION`, queries the persistent internal index for each regulatory chunk, and sends qualifying pairs through `analyze_clause_impact`. Only results where `is_affected` is true are saved. Upserts refresh pending suggestions without creating duplicates. Accepted and dismissed suggestions are historical decisions and are not overwritten by automatic or manual re-analysis.

The regular MAS pipeline triggers suggestion generation only after a saved document has usable OCR text. Failures are logged per regulatory document and do not roll back the regulatory ingestion itself. A later manual re-run can recover. Re-analysis replaces stale pending rows within its requested scope after the new analysis completes successfully; if analysis fails, existing suggestions remain.

## User Experience

### Document Library

The sidebar gains an `Internal Documents` item. Its page includes:

- An upload button and file picker accepting PDF files.
- An upload state that remains active until extraction and indexing finish.
- A semantic-search input, with a clear affordance to return to the normal inventory.
- A responsive table/list showing title, filename, upload date, size, chunk count, and indexed status.
- Empty, loading, error, no-results, and duplicate-document feedback.

Selecting a document opens its detail screen while preserving the library state for the back action.

### Split Document View

The desktop detail layout is split into two resizable areas:

- Left: an embedded PDF viewer sourced from a newly requested presigned URL.
- Right: metadata, extracted clauses with local text filtering, re-analysis controls, and suggestion cards containing regulatory source, match score, reasoning, proposed redline, citations, and review controls.

On narrow screens the panels stack, with document information before the PDF viewer. Expired PDF URLs are refreshed once. A PDF-viewer failure shows a download/open-original action without hiding extracted text or suggestions.

Deleting requires explicit confirmation. After success the app returns to the library and removes the entry from local state.

## Error Handling and Consistency

- Unsupported extension or MIME, oversized input, invalid PDF signature, malformed/encrypted PDF, and no extractable text have distinct client-readable errors.
- Upload, extraction, and embedding happen before database writes. Object upload happens before the database transaction, with exact-key compensation on database failure.
- Duplicate uploads do not upload another object or re-embed existing chunks.
- S3 download URL failures affect only PDF display; metadata, clauses, and suggestions remain usable.
- S3 deletion must succeed or establish that the object is absent before database deletion commits.
- Suggestion-generation failures do not fail regulatory ingestion and do not erase the last good suggestions.
- API errors contain safe messages; secrets, endpoints with credentials, extracted document text, and raw provider exceptions are not exposed.

## Migration and Compatibility

A numbered migration creates `internal_documents` and `document_suggestions`, then adapts `internal_document_chunks`. Because existing chunks have no reliable parent metadata or object, the migration deletes existing demo/internal chunk rows before adding the non-null foreign key. Regulatory `documents` rows are preserved.

The current request-local analysis API and in-memory Qdrant store remain operational for compatibility, but the new upload library and scheduled analysis use PostgreSQL/pgvector exclusively. Documentation will stop describing the persistent index as planned.

## Testing and Verification

Backend tests cover:

- Every PDF validation and extraction result.
- Legal chunk creation and embedding dimension validation.
- Duplicate detection without repeated storage or embedding.
- Successful S3 upload plus atomic document/chunk persistence.
- Exact-object cleanup after database failure.
- Delete ordering and missing-object idempotence.
- Cosine ranking, thresholds, document grouping, and excerpt limits.
- Suggestion uniqueness, pending replacement, preservation of reviewed states, and analysis failure safety.
- Automatic batch invocation and manual re-analysis.
- API schemas, status codes, pagination, and presigned URL behavior.

Frontend tests cover:

- Sidebar navigation and preservation of the existing regulatory-document state.
- Inventory loading, upload progress, success, duplicate, and failure states.
- Metadata and semantic search behavior.
- Opening and returning from the split view.
- PDF URL loading, one refresh after expiry, and viewer fallback.
- Clause filtering, suggestion rendering, status updates, re-analysis, and confirmed deletion.

Completion requires the full Python test suite, frontend Vitest suite, and production Vite build to pass.

## Deployment

- Add `boto3` to runtime dependencies.
- Provision a private Railway Bucket and reference its credentials into the API service using the five agreed environment-variable names.
- Keep the PostgreSQL service on a pgvector-enabled image and run numbered migrations during application startup.
- The existing scheduler continues to invoke the regulatory pipeline; no new worker service is required.
