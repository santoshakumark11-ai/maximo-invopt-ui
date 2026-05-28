"""
APScheduler wrapper for the nightly orchestrator.

Activated only when:
    settings.scheduler_enabled == True
    AND APScheduler is installed.

Both conditions are off by default so the first batch is always operator-
initiated via POST /v1/recommendations:run.  The cron format is the standard
5-field one (min hour dom month dow); the scheduler runs in UTC by default
but converts to the host timezone when /etc/timezone is set.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)

_scheduler = None  # type: ignore[var-annotated]


def start() -> Optional[object]:
    """Start the scheduler if enabled.  Returns the scheduler object or None."""
    settings = get_settings()
    if not settings.scheduler_enabled:
        return None
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
    except Exception as exc:
        logger.warning("APScheduler not installed (%s) — scheduler disabled", exc)
        return None

    global _scheduler
    if _scheduler is not None:
        return _scheduler

    parts = settings.scheduler_cron.split()
    if len(parts) != 5:
        logger.warning(
            "scheduler_cron=%r is not a 5-field expression — scheduler disabled",
            settings.scheduler_cron,
        )
        return None

    trigger = CronTrigger(
        minute=parts[0], hour=parts[1], day=parts[2],
        month=parts[3], day_of_week=parts[4],
    )

    async def _job() -> None:
        try:
            from app.orchestration.nightly import run_batch
            res = await run_batch(
                history_months=settings.scheduler_history_months,
                run_backtest=True,
            )
            logger.info(
                "Scheduler: nightly run produced %d recommendations in %.1fs",
                res.recommendations, res.elapsed_seconds,
            )
        except Exception as exc:
            logger.error("Scheduler: nightly run failed: %s", exc)

    sched = AsyncIOScheduler()
    sched.add_job(_job, trigger, id="invopt-nightly", replace_existing=True)
    sched.start()
    _scheduler = sched
    logger.info("Scheduler started with cron %r", settings.scheduler_cron)
    return _scheduler


async def stop() -> None:
    global _scheduler
    if _scheduler is None:
        return
    try:
        _scheduler.shutdown(wait=False)
    except Exception:
        pass
    _scheduler = None
