"""
In-Memory Progress Tracker
Tracks analysis progress for SSE streaming.
"""

import asyncio
from collections import defaultdict
from datetime import datetime, timezone


class ProgressTracker:
    """Thread-safe progress tracking for analysis tasks."""
    
    def __init__(self):
        self._progress = {}
        self._subscribers = defaultdict(list)
    
    def create(self, analysis_id: str):
        """Create a new progress entry."""
        self._progress[analysis_id] = {
            'status': 'queued',
            'progress': 0,
            'message': 'Analysis queued',
            'current_step': 'queued',
            'steps': [],
        }
    
    def update(self, analysis_id: str, status: str, progress: int, message: str, step: str = ''):
        """Update progress and notify subscribers."""
        if analysis_id not in self._progress:
            self.create(analysis_id)
        
        self._progress[analysis_id] = {
            'status': status,
            'progress': progress,
            'message': message,
            'current_step': step or status,
            'steps': self._progress[analysis_id].get('steps', []) + [{
                'step': step,
                'message': message,
                'progress': progress,
                'timestamp': datetime.now(timezone.utc).isoformat(),
            }],
        }
    
    def get(self, analysis_id: str) -> dict:
        """Get current progress."""
        return self._progress.get(analysis_id, {
            'status': 'unknown',
            'progress': 0,
            'message': 'Analysis not found',
            'current_step': 'unknown',
        })
    
    def remove(self, analysis_id: str):
        """Remove progress entry (cleanup)."""
        self._progress.pop(analysis_id, None)
    
    def is_complete(self, analysis_id: str) -> bool:
        """Check if analysis is complete or failed."""
        status = self._progress.get(analysis_id, {}).get('status', '')
        return status in ('complete', 'failed')


# Singleton
progress_tracker = ProgressTracker()
