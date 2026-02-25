"""
Job Handlers - Pluggable handlers for different job types in the job pool.
"""

from .general_handler import handle_general_job, JobResult

__all__ = ['handle_general_job', 'JobResult']
