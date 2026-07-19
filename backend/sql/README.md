# Khojo SQL migrations

Run these files in numeric order with a migration role against PostgreSQL 16:

1. `0001_khojo_core.sql` creates the permanent graph, crawl, content, search,
   and media schemas and seeds the initial vocabulary.
2. `0002_nullable_unique_indexes.sql` corrects nullable unique constraints from
   the bootstrap so optional source domains, external IDs, location codes, and
   media hashes do not collide merely because they are absent.

Do not execute either file from the FastAPI process. First apply the full set
to an empty disposable PostgreSQL 16 database and keep the output with the
release verification evidence.

