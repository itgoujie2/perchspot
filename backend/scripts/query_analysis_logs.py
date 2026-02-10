#!/usr/bin/env python3
"""
CLI tool for querying analysis logs.

Usage:
    docker compose exec backend python scripts/query_analysis_logs.py --recent 20
    docker compose exec backend python scripts/query_analysis_logs.py --failed --days 7
    docker compose exec backend python scripts/query_analysis_logs.py --stats
    docker compose exec backend python scripts/query_analysis_logs.py --detail <id>

On EC2 (production):
    docker compose -f docker-compose.prod.yml exec backend python scripts/query_analysis_logs.py --stats
"""
import argparse
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from tabulate import tabulate

# Add parent directory to path
sys.path.insert(0, '/app')

from sqlalchemy import func, desc, and_
from app.database.connection import SessionLocal
from app.models.database import AnalysisJob
from app.models.analysis_log import AnalysisStepLog
from app.models.user import User


def format_duration(ms):
    """Format milliseconds to human-readable duration."""
    if not ms:
        return 'N/A'
    if ms < 1000:
        return f'{ms}ms'
    elif ms < 60000:
        return f'{ms/1000:.1f}s'
    else:
        return f'{ms/60000:.1f}m'


def format_cost(cost):
    """Format cost to string."""
    if not cost:
        return '$0.00'
    return f'${float(cost):.4f}'


def list_recent(db, limit=20, status=None, days=7):
    """List recent analysis jobs."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    query = db.query(AnalysisJob, User.email).outerjoin(
        User, AnalysisJob.user_id == User.id
    ).filter(AnalysisJob.created_at >= cutoff)

    if status:
        query = query.filter(AnalysisJob.status == status)

    results = query.order_by(desc(AnalysisJob.created_at)).limit(limit).all()

    if not results:
        print("No analyses found.")
        return

    table_data = []
    for job, email in results:
        table_data.append([
            str(job.id)[:8],
            job.address[:40] if job.address else 'Unknown',
            email or 'Anonymous',
            job.status,
            'Yes' if job.is_cached else 'No',
            format_duration(job.total_duration_ms),
            format_cost(job.total_cost_user),
            job.created_at.strftime('%m/%d %H:%M') if job.created_at else 'N/A',
        ])

    headers = ['ID', 'Address', 'User', 'Status', 'Cached', 'Duration', 'Cost', 'Date']
    print(tabulate(table_data, headers=headers, tablefmt='simple'))
    print(f"\nTotal: {len(results)} analyses")


def show_stats(db, days=7):
    """Show aggregate statistics."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Basic counts
    total = db.query(AnalysisJob).filter(AnalysisJob.created_at >= cutoff).count()
    completed = db.query(AnalysisJob).filter(
        AnalysisJob.created_at >= cutoff,
        AnalysisJob.status == 'completed'
    ).count()
    failed = db.query(AnalysisJob).filter(
        AnalysisJob.created_at >= cutoff,
        AnalysisJob.status == 'failed'
    ).count()
    cached = db.query(AnalysisJob).filter(
        AnalysisJob.created_at >= cutoff,
        AnalysisJob.is_cached == True
    ).count()

    # Rates
    success_rate = (completed / total * 100) if total > 0 else 0
    cache_rate = (cached / total * 100) if total > 0 else 0

    # Duration stats
    avg_duration = db.query(func.avg(AnalysisJob.total_duration_ms)).filter(
        AnalysisJob.created_at >= cutoff,
        AnalysisJob.status == 'completed'
    ).scalar()

    # Cost stats
    total_cost = db.query(func.sum(AnalysisJob.total_cost)).filter(
        AnalysisJob.created_at >= cutoff
    ).scalar() or 0
    total_cost_user = db.query(func.sum(AnalysisJob.total_cost_user)).filter(
        AnalysisJob.created_at >= cutoff
    ).scalar() or 0

    print(f"\n=== Analysis Stats (Last {days} days) ===\n")
    print(f"Total Analyses:    {total}")
    print(f"Completed:         {completed}")
    print(f"Failed:            {failed}")
    print(f"Cached:            {cached}")
    print(f"Success Rate:      {success_rate:.1f}%")
    print(f"Cache Rate:        {cache_rate:.1f}%")
    print(f"Avg Duration:      {format_duration(avg_duration)}")
    print(f"Total Cost:        {format_cost(total_cost)}")
    print(f"Total Cost (User): {format_cost(total_cost_user)}")

    # Step stats
    print(f"\n=== Step Performance ===\n")

    step_stats = db.query(
        AnalysisStepLog.step_number,
        AnalysisStepLog.step_name,
        func.count(AnalysisStepLog.id).label('count'),
        func.avg(AnalysisStepLog.duration_ms).label('avg_duration'),
        func.sum(AnalysisStepLog.cost).label('total_cost'),
    ).join(
        AnalysisJob, AnalysisStepLog.analysis_job_id == AnalysisJob.id
    ).filter(
        AnalysisJob.created_at >= cutoff
    ).group_by(
        AnalysisStepLog.step_number,
        AnalysisStepLog.step_name
    ).order_by(
        AnalysisStepLog.step_number
    ).all()

    if step_stats:
        table_data = []
        for s in step_stats:
            table_data.append([
                s.step_number,
                s.step_name,
                s.count,
                format_duration(s.avg_duration),
                format_cost(s.total_cost),
            ])

        headers = ['#', 'Step', 'Count', 'Avg Duration', 'Total Cost']
        print(tabulate(table_data, headers=headers, tablefmt='simple'))


def show_detail(db, analysis_id):
    """Show detailed analysis with step breakdown."""
    # Find by partial ID match
    job = db.query(AnalysisJob).filter(
        AnalysisJob.id.cast(db.bind.dialect.name == 'mysql' and 'CHAR(36)' or 'TEXT').like(f'{analysis_id}%')
    ).first()

    if not job:
        # Try by request_id
        job = db.query(AnalysisJob).filter(
            AnalysisJob.request_id.like(f'{analysis_id}%')
        ).first()

    if not job:
        print(f"Analysis not found: {analysis_id}")
        return

    # Get user email
    user = db.query(User).filter(User.id == job.user_id).first() if job.user_id else None

    print(f"\n=== Analysis Detail ===\n")
    print(f"ID:            {job.id}")
    print(f"Request ID:    {job.request_id}")
    print(f"Address:       {job.address or 'Unknown'}")
    print(f"User:          {user.email if user else 'Anonymous'}")
    print(f"Client IP:     {job.client_ip or 'N/A'}")
    print(f"Status:        {job.status}")
    print(f"Cached:        {'Yes' if job.is_cached else 'No'}")
    print(f"Duration:      {format_duration(job.total_duration_ms)}")
    print(f"Cost:          {format_cost(job.total_cost)}")
    print(f"Cost (User):   {format_cost(job.total_cost_user)}")
    print(f"Created:       {job.created_at}")
    print(f"Started:       {job.started_at or 'N/A'}")
    print(f"Completed:     {job.completed_at or 'N/A'}")

    if job.error_message:
        print(f"\nError Step:    {job.error_step}")
        print(f"Error:         {job.error_message}")

    # Get step logs
    steps = db.query(AnalysisStepLog).filter(
        AnalysisStepLog.analysis_job_id == job.id
    ).order_by(AnalysisStepLog.step_number).all()

    if steps:
        print(f"\n=== Step Breakdown ===\n")
        table_data = []
        for s in steps:
            tokens = f'{s.input_tokens or 0}/{s.output_tokens or 0}' if s.input_tokens or s.output_tokens else '-'
            table_data.append([
                s.step_number,
                s.step_name,
                s.step_type,
                s.status,
                format_duration(s.duration_ms),
                format_cost(s.cost),
                tokens,
                s.model or '-',
            ])

        headers = ['#', 'Step', 'Type', 'Status', 'Duration', 'Cost', 'Tokens', 'Model']
        print(tabulate(table_data, headers=headers, tablefmt='simple'))

        # Show failed steps
        failed_steps = [s for s in steps if s.status == 'failed']
        if failed_steps:
            print(f"\n=== Failed Steps ===\n")
            for s in failed_steps:
                print(f"Step {s.step_number} ({s.step_name}): {s.error_message}")


def list_failed(db, days=7):
    """List failed analyses."""
    list_recent(db, limit=50, status='failed', days=days)


def main():
    parser = argparse.ArgumentParser(description='Query analysis logs')
    parser.add_argument('--recent', type=int, metavar='N', help='List N most recent analyses')
    parser.add_argument('--failed', action='store_true', help='List failed analyses')
    parser.add_argument('--stats', action='store_true', help='Show aggregate statistics')
    parser.add_argument('--detail', type=str, metavar='ID', help='Show detail for analysis ID')
    parser.add_argument('--days', type=int, default=7, help='Number of days to look back (default: 7)')

    args = parser.parse_args()

    if not any([args.recent, args.failed, args.stats, args.detail]):
        parser.print_help()
        return

    db = SessionLocal()
    try:
        if args.stats:
            show_stats(db, args.days)
        elif args.detail:
            show_detail(db, args.detail)
        elif args.failed:
            list_failed(db, args.days)
        elif args.recent:
            list_recent(db, args.recent, days=args.days)
    finally:
        db.close()


if __name__ == '__main__':
    main()
