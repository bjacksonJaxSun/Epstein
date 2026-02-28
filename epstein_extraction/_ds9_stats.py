from sqlalchemy import text
from config import SessionLocal
db = SessionLocal()

rows = db.execute(text("""
    SELECT
      COUNT(*) FILTER (WHERE photos_checked_at > '1970-01-02') AS completed,
      COUNT(*) FILTER (WHERE photos_checked_at <= '1970-01-02') AS in_progress,
      COUNT(*) FILTER (WHERE photos_checked_at IS NULL) AS remaining,
      COUNT(*) AS total
    FROM documents WHERE r2_key LIKE 'DataSet_9/%'
""")).fetchone()
print(f"Completed:   {rows[0]:,}")
print(f"In-progress: {rows[1]:,}  (claimed, being processed)")
print(f"Remaining:   {rows[2]:,}  (not yet claimed)")
print(f"Total:       {rows[3]:,}")
print(f"Pct done:    {rows[0]/rows[3]*100:.1f}%")

rows2 = db.execute(text("""
    SELECT ocr_status, COUNT(*) FROM documents
    WHERE r2_key LIKE 'DataSet_9/%'
    GROUP BY ocr_status ORDER BY COUNT(*) DESC
""")).fetchall()
print()
print("OCR status:")
for r in rows2:
    print(f"  {str(r[0])}: {r[1]:,}")

rows3 = db.execute(text("""
    SELECT COUNT(*) FROM media_files WHERE file_path LIKE 'DataSet_9/%'
""")).fetchone()
print()
print(f"Photos uploaded to R2: {rows3[0]:,}")
db.close()
