from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from redis import Redis
from rq import Queue, Worker

from .engine import DoclingParsingEngine
from .indexing import WhooshIndexer
from .repository import SqlAlchemyParsingRepository
from .storage import LocalBookStorage, StoragePaths
from .worker import ParsingWorker


@dataclass
class WorkerConfig:
    database_url: str
    book_storage_root: str
    whoosh_index_dir: str
    perform_ocr: bool = True
    engine_version: str = "docling-latest"
    batch_size: int = 50
    persist_engine_output: bool = False


def run_parse_job(job_id: str, config: WorkerConfig) -> None:
    """
    RQ task entrypoint. Creates all required components and executes a parse job.
    """
    repo = SqlAlchemyParsingRepository(config.database_url)
    storage = LocalBookStorage(StoragePaths(Path(config.book_storage_root)))
    engine = DoclingParsingEngine(perform_ocr=config.perform_ocr, engine_version=config.engine_version)
    indexer = WhooshIndexer(Path(config.whoosh_index_dir))
    worker = ParsingWorker(
        repository=repo,
        storage=storage,
        engine=engine,
        indexer=indexer,
        batch_size=config.batch_size,
        persist_engine_output=config.persist_engine_output,
    )
    worker.run_job(job_id)


class RQJobQueue:
    """
    Redis-backed job queue using RQ. The queue pushes jobs to Redis and workers
    can be started by calling `work()` in a dedicated process.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0", queue_name: str = "parse-jobs"):
        self.redis = Redis.from_url(redis_url)
        self.queue = Queue(queue_name, connection=self.redis)

    def enqueue_parse_job(self, job_id: str, config: WorkerConfig):
        """
        Enqueue a parsing job. RQ job_id is set to parse job id for idempotency.
        """
        return self.queue.enqueue(run_parse_job, job_id, config, job_id=job_id, retry=None)

    def work(self):
        worker = Worker([self.queue], connection=self.redis)
        worker.work(with_scheduler=True)
