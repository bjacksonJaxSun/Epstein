"""
Job Handlers - Pluggable handlers for different job types in the job pool.
"""

from .general_handler import handle_general_job, JobResult
from .extraction_handler import handle_extraction_job

__all__ = ['handle_general_job', 'handle_extraction_job', 'JobResult']
