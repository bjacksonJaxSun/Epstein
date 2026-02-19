$env:PATH = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User') + ';C:\Program Files\PostgreSQL\17\bin'
$env:PGPASSWORD = "epstein_secure_pw_2024"

$dumpFile = "C:\Development\EpsteinDownloader\tmp\epstein_db_fresh_20260219.dump"
$tocFile  = "$env:TEMP\epstein_toc_filtered.txt"

Write-Host "=== Step 1: Add missing columns to local schema ==="
psql -h localhost -U epstein_user -d epstein_documents -c "
ALTER TABLE documents ADD COLUMN IF NOT EXISTS video_path text;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS video_transcript text;
ALTER TABLE media_files ADD COLUMN IF NOT EXISTS is_likely_photo boolean DEFAULT false;
"

Write-Host ""
Write-Host "=== Step 2: Truncate all tables ==="
psql -h localhost -U epstein_user -d epstein_documents -c "
TRUNCATE TABLE
    chunk_entity_mentions, chunk_terms,
    communication_recipients, communications,
    document_classifications, document_people, documents,
    entity_cooccurrences, event_participants, events,
    evidence_items, extraction_jobs, extraction_log,
    face_clusters, face_detections, financial_transactions,
    image_analysis, investigation_findings, investigation_sessions,
    location_clusters, locations,
    media_events, media_files, media_location_clusters,
    media_people, organizations, pending_imports,
    people, refresh_tokens, relationships,
    roles, scene_analysis, term_document_frequency,
    user_roles, users, visual_entities
RESTART IDENTITY CASCADE;
"

Write-Host ""
Write-Host "=== Step 3: Build filtered TOC (exclude document_chunks) ==="
pg_restore --list $dumpFile | Where-Object { $_ -notmatch 'document_chunks' } | Set-Content $tocFile
$lineCount = (Get-Content $tocFile).Count
Write-Host "TOC lines after filtering: $lineCount"

Write-Host ""
Write-Host "=== Step 4: Restore data only using filtered TOC ==="
$start = Get-Date
pg_restore `
    -h localhost `
    -U epstein_user `
    -d epstein_documents `
    --no-owner `
    --data-only `
    --no-privileges `
    -L $tocFile `
    "$dumpFile" 2>&1
$end = Get-Date
Write-Host "Restore completed in $(($end-$start).TotalMinutes.ToString('F1')) minutes. Exit: $LASTEXITCODE"

Write-Host ""
Write-Host "=== Step 5: Verify row counts ==="
psql -h localhost -U epstein_user -d epstein_documents -c "
SELECT 'documents' as tbl, COUNT(*) FROM documents
UNION ALL SELECT 'media_files', COUNT(*) FROM media_files
UNION ALL SELECT 'people', COUNT(*) FROM people
UNION ALL SELECT 'events', COUNT(*) FROM events
UNION ALL SELECT 'organizations', COUNT(*) FROM organizations
ORDER BY 1;
"
