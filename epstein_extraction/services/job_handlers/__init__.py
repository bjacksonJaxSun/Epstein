"""
Job Handlers - Pluggable handlers for different job types in the job pool.
"""

from .general_handler import handle_general_job, JobResult
from .extraction_handler import handle_extraction_job
from .chunk_embed_handler import handle_chunk_embed_job

__all__ = ['handle_general_job', 'handle_extraction_job', 'handle_chunk_embed_job', 'JobResult']
